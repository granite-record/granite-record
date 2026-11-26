#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.61
"""
preflight's checks of the bill pages, versions, requests and topics (build_site_v2.py).

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

from pf_core import (_in_suite, _parsed, _run, _sealed_run, _source, check, imp)
from pf_fixture import (CHAIN_NEEDS, _fixture_site_shared, _fixture_site_v2, _site_fixture)
from pf_harness import (_app_js, _node_app, _with_components)
from pf_shared import (LSR_LISTLIKE, _BALLOTPEDIA, _CHIP_FINISHED, _CHIP_LIVE,
                       _DOCKET_OVERTAKEN, _MANUAL_1993, _MANUAL_1999, _RAIL_FACE, _SOS_2024,
                       _STATUSCAT_HARNESS, _STATUS_CATEGORY, _STATUS_CATS, _STATUS_REAL_PAIRS,
                       _ev, _hearing_fixture, _json3_cues, _mk, _nar, _narratives, _site_bills,
                       _site_gen, _site_records, _told_from_rows, _voters_row)


@check("site", "a notice a later row cancelled or moved keeps the calendar it cites among its "
               "bill's documents, and a row the docket cancelled adds none",
       needs=("build_site_v2", "narrative"))
def _overtaken_notice_documents(B, N):
    """The calendar that printed a notice printed the bill. Carried as
    cancelled so that nothing reads it as a sitting, a notice a later row
    cancelled or moved (narrative.overtaken) was skipped by bill_documents as
    a row the docket cancelled is, and 59 bills' Documents tabs lost 62
    calendars: SB 339 of 2006 lost Senate Calendar 1A, which printed its
    hearing of 19 January. Built from SB 339's real rows (_DOCKET_OVERTAKEN),
    whose voided notice of 19 January cites SC1A and nothing else does; the
    rows the docket cancelled cite SC1, SC2 and SC4, which stay off as before."""
    n = _told_from_rows(N, "2005-2006", "SB339", _DOCKET_OVERTAKEN[("SB339", "2005-2006")])
    cites = {e.get("cite") for e in n["events"]}
    url = "https://gc.nh.gov/calendars/2006/sc{}.pdf"
    sources = {f"{c} 2006": url.format(c.split()[-1].lower()) for c in cites if c}
    docs, _text = B.bill_documents({"journal": {"from": "fixture"}}, "SB339", {}, n,
                                   sources, [], [])
    got = sorted(d["label"] for d in docs if d.get("kind") == "record")
    assert any(lab.startswith("SC 1A") for lab in got), (
        f"SB 339's Documents tab does not list Senate Calendar 1A, which printed the notice "
        f"a later row cancelled: {got} (cited {sorted(c for c in cites if c)})")
    off = [e.get("cite") for e in n["events"]
           if e.get("cancelled") and not e.get("overtaken") and e.get("cite")]
    assert not any(lab.split(",")[0] in off for lab in got), (
        f"a calendar only a row the docket cancelled cites is listed: {got}, {off}")
    # And a notice the history leaves untold for another reason -- set for
    # after the bill was withdrawn (decision 59e) -- keeps its calendar too:
    # the event as narrative.build carries HB 1512 of 2012's, with a cite.
    withdrawn = {"events": [
        {"date": "2012-01-04", "type": "withdrawn", "body": "H", "cancelled": False,
         "raw": "Withdrawn", "cite": "", "cite_page": ""},
        {"date": "2012-01-12", "type": "hearing", "body": "H", "cancelled": True,
         "raw": "Public Hearing: 1/12/2012 10:30 AM LOB 207", "cite": "HC 3", "cite_page": "",
         "notice": True, "row_note": "A notice. The bill was withdrawn before the day it names."}]}
    docs, _text = B.bill_documents({"journal": {"from": "fixture"}}, "HB1512", {}, withdrawn,
                                   {"HC 3 2012": "https://gc.nh.gov/calendars/2012/hc3.pdf"}, [], [])
    assert any(d["label"].startswith("HC 3") for d in docs if d.get("kind") == "record"), (
        f"a withdrawn bill's notice drops the calendar that printed it: {docs}")
    return "ok", (f"SB 339 of 2006 lists {', '.join(got)}; {', '.join(off)} stay off; a withdrawn "
                  "bill's notice keeps its calendar")


# =============================================================== code: status ==

def _narr(lines, body="H"):
    return {"events": [{"raw": x, "type": "other", "date": "2026-08-19",
                        "body": body} for x in lines]}


@check("status", "a sustained veto beats an overridden one", needs=("build_site_v2",))
def _veto_status(build_site_v2):
    B = build_site_v2
    # The chambers, as the real docket has them: the Senate overrode and the
    # House sustained, on the same day. An override needs both.
    both = _narr(["Vetoed by Governor 07/15/2026",
                  "Veto Sustained 08/19/2026: RC 165-140 Lacking Necessary "
                  "Two-Thirds Vote"])
    both["events"] += _narr(["Notwithstanding the Governor's Veto, Shall SB 434 "
                             "Become Law: RC 16Y-8N, Veto Overridden by "
                             "necessary two-thirds vote; 08/19/2026"],
                            body="S")["events"]
    # And one chamber reconsidering its own vote: sustained, then overridden.
    same = _narr(["Vetoed By Governor 07/13/2011",
                  "Shall HB 542 Become Law: Veto Sustained, RC 244-130",
                  "Veto Overridden: RC 255-112 By Required Two-Thirds Vote"])
    assert B.classify(same, [])[0] == "law", "a chamber may reconsider"
    assert B.docket_outcome(same)[0] == "law", "a chamber may reconsider"
    kind, label = B.classify(both, [])
    assert kind == "veto", f"SB 434 shape came out as {kind}/{label}"
    step = B.next_step(both, {})
    assert "dead" in step.lower(), step
    return "ok", f"{label} / {step}"


@check("status", "a stated override in one chamber and sustained veto in the other is a veto",
       needs=("build_site_v2",))
def _veto_split_stated(build_site_v2):
    """The same rule as the check above, for the status fields rather than
    the docket. HB 503 of 2003: VETOED BY GOVERNOR, House VETO OVERRIDDEN,
    Senate VETO SUSTAINED -- published as "Veto overridden, became law"
    until 11 September, with ten others like it."""
    B = build_site_v2
    for house, senate in (("VETO OVERRIDDEN", "VETO SUSTAINED"),
                          ("VETO SUSTAINED", "VETO OVERRIDDEN")):
        got = B.classify_stated({"gen_status": "VETOED BY GOVERNOR",
                                 "house_status": house,
                                 "senate_status": senate}, "HB")
        assert got and got[0] == "veto", (
            f"House {house}, Senate {senate} came out as {got}")
    both = B.classify_stated({"gen_status": "VETOED BY GOVERNOR",
                              "house_status": "VETO OVERRIDDEN",
                              "senate_status": "VETO OVERRIDDEN"}, "HB")
    assert both and both[0] == "law", f"overridden in both came out as {both}"
    return "ok", "sustained in either chamber is a veto; overridden in both is law"


@check("status", "a bill with no narrated docket is read from its signature line and its fields' own stage",
       needs=("build_site_v2",))
def _unnarrated_status(build_site_v2):
    """Two rules for the twelve terms whose dockets are not narrated.

    HB 1075 of 1998 was signed (\"SIGNED BY GOVERNOR 10/01/98 ... CHAP.0389\")
    and read "In committee", its fields stopping at CONFERENCE REPORT
    ADOPTED: the signature line extract_chapters keeps now settles it. And
    495 bills read "In committee" or "In progress" -- this site's guess --
    over fields naming a stage; the field's stage replaces the guess, but
    never a docket's own outcome."""
    B = build_site_v2
    conf = {"gen_status": "SENATE", "house_status": "CONFERENCE REPORT ADOPTED",
            "senate_status": "CONFERENCE REPORT ADOPTED"}
    d = B.bill_disposition({}, "HB1075", conf, None, [], "1997-1998",
                           "2025-2026", law_line="SIGNED BY GOVERNOR  10/01/98 "
                           "EFF: 10/01/98* CHAP.0389")
    assert (d.kind, d.status) == ("law", "Signed into law"), d
    d = B.bill_disposition({}, "HB42", conf, None, [], "1989-1990", "2025-2026")
    assert d.status == "Conference committee report adopted", d.status
    filed = {"gen_status": "HOUSE", "house_status": "REPORT FILED",
             "senate_status": ""}
    d = B.bill_disposition({}, "HB190", filed, None, [], "1989-1990", "2025-2026")
    assert (d.kind, d.status) == ("done", "Committee report filed"), d
    killed = _narr(["Inexpedient to Legislate: MA VV 03/06/2024"])
    killed["events"][0].update(type="floor", motion="MA",
                               action="Inexpedient to Legislate")
    d = B.bill_disposition({}, "HB1", filed, killed, [], "2023-2024", "2025-2026")
    assert d.status == "Killed", f"a docket's kill gave way to a field: {d.status}"
    # A veto in a closed term: the docket's failed override where there is
    # one, and never "awaiting an override vote" twenty-eight years on.
    vetoed = {"gen_status": "VETOED BY GOVERNOR", "house_status": "",
              "senate_status": ""}
    d = B.bill_disposition({}, "HB149", vetoed, None, [], "1997-1998",
                           "2025-2026", override_failed="OVERRIDE GOV VETO, "
                           "ML RC(17-299)")
    assert d.status == "Vetoed, override failed", d.status
    d = B.bill_disposition({}, "HB1407", vetoed, None, [], "1991-1992",
                           "2025-2026")
    assert d.status == "Vetoed", d.status
    d = B.bill_disposition({}, "HB9", vetoed, None, [], "2025-2026",
                           "2025-2026")
    assert d.status == "Vetoed, awaiting an override vote", d.status
    return "ok", ("signed from the line; the field's stage, never over the "
                  "docket; a closed term's veto awaits nothing")


@check("status", "law without a signature reads as law", needs=("build_site_v2",))
def _unsigned_status(build_site_v2):
    n = _narr(["Enacted in accordance with Article 44 PartII of the N.H. "
               "Constitution without the signature of the governor. Chapter 343"])
    kind, label = build_site_v2.classify(n, [])
    assert kind == "law", f"came out as {kind}/{label}"
    return "ok", f"{label} / {build_site_v2.next_step(n, {})}"


@check("status", "the status box never claims another kind of status than the chip",
       needs=("build_site_v2",))
def _next_step_agrees(build_site_v2):
    """next_step() reads the last docket event, and that is often not the one
    that decided the bill. HB 691 of 2025's last row is the House killing it,
    190-156 -- a floor row, so the box read "Pending action in the other
    chamber" under "Killed"; HB 675 of 2026's is a failed motion to
    reconsider its kill; HR 24 of 2000's is a rules suspension, read as
    "Adopted" under "In committee"; HB 542 of 2011, overridden and Chapter
    271, read "The override failed". 130 records of 2025-2026 and two of
    closed terms. The General Court's own field wording, and a line that
    says the same thing as the chip in other words, are left as they are."""
    B = build_site_v2
    now = "2025-2026"
    hb691 = _nar(_ev("H", "Committee Report: Inexpedient to Legislate 02/12/2025 (Vote 14-1; CC)",
                     "report"),
                 _ev("H", "Inexpedient to Legislate: MA RC 190-156 03/06/2025", "floor", "MA",
                     "Inexpedient to Legislate"))
    step = B.next_step(hb691, {}, "HB")
    assert step.startswith("Pending"), (
        f"HB 691's last row no longer reads as pending ({step!r}), so this "
        "check no longer exercises the case it was written for")
    bad = []
    for step, status, term, kind, want in (
            (step, "Killed", now, "done", "Killed"),
            ("In progress", "In a committee of conference", now, "done",
             "In a committee of conference"),
            ("Adopted. A resolution of one chamber goes no further", "In committee",
             "1999-2000", "done", "In committee"),
            ("Vetoed. The override failed and the bill is dead",
             "Veto overridden, became law", "2011-2012", "law", "Veto overridden, became law"),
            # Left alone: the same claim in other words, the fields, a live bill.
            ("Vetoed. The override failed and the bill is dead", "Vetoed, override failed",
             now, "veto", None),
            ("Became law without the governor's signature", "Became law unsigned", now, "law", None),
            ("Died when the session ended", "Died on the table", now, "done", None),
            ("House: INEXPEDIENT TO LEGISLATE", "Killed", now, "done", None),
            ("Pending action in the other chamber", "Passed one chamber", now, "active", None)):
        got = B.settled_step(step, status, term, now, kind)
        if got != (want or step):
            bad.append(f"{step[:30]!r} under {status!r}: {got!r}")
    assert not bad, "; ".join(bad)
    return "ok", "a pending, adopted or vetoed line gives way to a chip of another kind"


@check("status", "a CACR's voters ratify it only with two thirds of the votes cast",
       needs=("build_site_v2",))
def _ballot_two_thirds(build_site_v2):
    """An amendment needs two thirds of the votes cast on it (Part II,
    Article 100), and a majority is not that: CACR 6 of 2024 won 452,307 to
    237,221 -- 65.6% -- and was not ratified. The eight CACRs sent to the
    voters since 2006 read "went to the voters" because their dockets stop at
    the second chamber; ballot_results.json gives them the answer (5 October
    2026).

    Fails on an outcome read off a majority; on exactly two thirds read as
    short; on a ballot row overriding a referendum line of the docket's own;
    on an election still to come given an answer; on the voters' line, the
    rail's Voters stop or the list card's copy of it saying anything but the
    election's day and its outcome; on a docket tally that disagrees with
    the source going unsaid; and on a ballot file naming a bill the record
    does not hold, or one that is not a CACR, being read without a word."""
    B = build_site_v2
    bad = []

    def want(label, got, what):
        if got != label:
            bad.append(f"{what}: wanted {label!r}, got {got!r}")

    for y, n, ok, what in ((452307, 237221, False, "CACR 6 of 2024, 65.6%"),
                           (329157, 194291, False, "CACR 21 of 2022, 62.9%"),
                           (294164, 308094, False, "CACR 26 of 2012, a majority against"),
                           (316005, 52893, True, "CACR 30 of 2006, 85.7%"),
                           (199229, 26336, True, "CACR 23 of 1990, 88.3%"),
                           (2, 1, True, "exactly two thirds"),
                           (200000, 100001, False, "a vote short of two thirds"),
                           (0, 0, False, "no votes")):
        want(ok, B.ratified(y, n), what)

    st = {"gen_status": "PASSED", "house_status": "PASSED/ADOPTED",
          "senate_status": "PASSED/ADOPTED", "body": "H"}
    n6 = _nar(_ev("H", "Ought to Pass : MA RC 321-27 By Necessary Three-Fifths Vote 02/23/2023",
                  "floor", "MA", "Ought to Pass", "2023-02-23"),
              _ev("S", "Ought to Pass, RC 22Y-1N, MA, by Necessary 3/5; OT3rdg; 03/30/2023 SJ 12",
                  date="2023-03-30"),
              hands=("H:committee", "H:floor", "S:committee", "S:floor"))
    row6 = _voters_row("2023-2024", "CACR6", "2024-11-05", 452307, 237221, "Question No. 1")
    d = B.bill_disposition({}, "CACR6", st, n6, [], "2023-2024", "2025-2026")
    want("Passed both chambers, went to the voters", d.status, "CACR6 2024 with no ballot row")
    d = B.bill_disposition({}, "CACR6", st, n6, [], "2023-2024", "2025-2026", ballot=row6)
    want(B.NOT_RATIFIED, d.status, "CACR6 2024, 65.6% yes")
    want("adopted", d.kind, "CACR6 2024's kind")
    row30 = _voters_row("2005-2006", "CACR30", "2006-11-07", 316005, 52893)
    d = B.bill_disposition({}, "CACR30", st, n6, [], "2005-2006", "2025-2026", ballot=row30)
    want(B.RATIFIED, d.status, "CACR30 2006, 85.7% yes")
    # The docket's own referendum line is the docket's answer, and a ballot
    # row does not overrule it (where the two disagree, the data check says so).
    n7 = _nar(*n6["events"], _ev("H", "AMENDMENT FAILED REFERENDUM(249,759-204,475); 1993 RED "
                                 "BOOK,P442", date="1992-11-03"), hands=())
    row7 = _voters_row("1991-1992", "CACR7", "1992-11-03", 249759, 204475, "Question No. 4",
                       _MANUAL_1993)
    d = B.bill_disposition({}, "CACR7", st, n7, [], "1991-1992", "2025-2026",
                           ballot=_voters_row("1991-1992", "CACR7", "1992-11-03", 9, 1))
    want(B.NOT_RATIFIED, d.status, "CACR7 1992: the docket's referendum line against a row")
    # An election still to come stays to come: CACR 13 of 2026.
    pending = _voters_row("2025-2026", "CACR13", "2026-11-03", None, None,
                          "Eliminate Office of Register of Probate Amendment", _BALLOTPEDIA,
                          "2026-10-05")
    text = ("submitted to the qualified voters of the state at the state general "
            "election to be held in November, 2026.")
    d = B.bill_disposition({}, "CACR13", st, n6, [], "2025-2026", "2025-2026", term_over=True,
                           text=text, today=B._date(2026, 10, 5), ballot=pending)
    want("Passed both chambers, goes to the voters in November 2026", d.status,
         "CACR13 2026, before its election")
    want({"date": "2026-11-03", "label": "Eliminate Office of Register of Probate Amendment",
          "pending": True, "source": _BALLOTPEDIA[0], "read": "2026-10-05",
          "by": "Ballotpedia", "whose": "Ballotpedia's", "cite": _BALLOTPEDIA[1]},
         B.ballot_card(pending, n6, today=B._date(2026, 10, 5)), "CACR13 2026's card")
    # On the day itself it is still to come; the day after, with no count in
    # the file, it is over and still pending -- the card says the vote was,
    # as the status says it went, and draws no outcome it does not have.
    want(None, B.ballot_card(pending, n6, today=B._date(2026, 11, 3)).get("over"),
         "CACR13 2026's card on election day")
    want((True, True), tuple(B.ballot_card(pending, n6, today=B._date(2026, 11, 4)).get(k)
                             for k in ("pending", "over")),
         "CACR13 2026's card the day after, with no count")

    # The voters' line, the rail's last stop and the list card's copy of it.
    # The line names whose count it is: How it got here is the docket's list,
    # and this line is the row's source's -- the Secretary of State's.
    step = B.ballot_step(row6)
    want(("2024-11-05", "V", "not_ratified", "x",
          "Not ratified, 452,307–237,221 (the Secretary of State's count)", "not ratified"),
         tuple(step[k] for k in ("date", "body", "act", "mark", "text", "short")),
         "CACR6 2024's voters' line")
    intro, steps = B.journey(n6, "CACR6", [], "", "", "2023-2024")
    steps.append(step)
    passed = {c for c in "HS" if B.journey_state(steps, c) == "p"}
    acted = list(dict.fromkeys(s_["body"] for s_ in steps if s_["body"] in "HS"))
    rail = B.passage(n6["stages"], "adopted", B.NOT_RATIFIED, "CACR6", passed, acted)
    want("", B.journey_disagrees(steps, "adopted", B.NOT_RATIFIED, rail, "CACR6"),
         "CACR6 2024's journey against its status")
    jrail = B.journey_rail(intro, steps, rail, "CACR6", B.NOT_RATIFIED)
    want({"stop": "Voters", "mark": "x", "date": "2024-11-05", "short": "not ratified",
          "say": "Not ratified, 452,307–237,221 (the Secretary of State's count)"},
         jrail[-1] if jrail else None, "CACR6 2024's Voters stop")
    want(["Vx", "2024-11-05", "not ratified"], (B.index_rail(jrail) or [None])[-1],
         "CACR6 2024's Voters stop on the list card")

    # The card: the counts, the outcome, and the docket's own pair where it is
    # not the source's -- CACR 22 of 1998's 159,439 against the Secretary of
    # State's 169,439. CACR 7 of 1992's docket says 204,475, which is the
    # Secretary of State's count too since 7 October 2026 (the file's 204,457
    # was Ballotpedia's), so its card carries no second pair.
    card = B.ballot_card(row7, n7)
    want((249759, 204475, False, None),
         (card.get("yes"), card.get("no"), card.get("ratified"), card.get("docket")),
         "CACR7 1992's card")
    n22 = _nar(*n6["events"], _ev("H", "AMENDMENT FAILED REFERENDUM  (119,104 - 159,439);  1998 "
                                  "RED BOOK, P350", date="1998-11-03"), hands=())
    row22 = _voters_row("1997-1998", "CACR22", "1998-11-03", 119104, 169439, "Question 1",
                        _MANUAL_1999)
    card = B.ballot_card(row22, n22)
    want((119104, 169439, False, [119104, 159439]),
         (card.get("yes"), card.get("no"), card.get("ratified"), card.get("docket")),
         "CACR22 1998's card")
    n23 = _nar(_ev("H", "AMENDMENT ADOPTED BY 2/3 REF(199,229-26,336); 1991 RED BOOK,P294",
                   date="1990-11-06"))
    card = B.ballot_card(_voters_row("1989-1990", "CACR23", "1990-11-06", 199229, 26336), n23)
    want((True, None), (card.get("ratified"), card.get("docket")), "CACR23 1990's card")

    # The file: read where it is sound, refused where it is not.
    bills = {"2023-2024": {"CACR6": {}, "HB1": {}}, "2025-2026": {"CACR13": {}}}
    root = Path(tempfile.mkdtemp())
    try:
        f = root / "ballot_results.json"
        f.write_text(json.dumps({"rows": [row6, pending]}), encoding="utf-8")
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            got = B.load_ballots(f, bills)
        want({("2023-2024", "CACR6"), ("2025-2026", "CACR13")}, set(got), "the rows read")
        for rows, what in (([{**row6, "bill": "CACR7"}], "a bill the record does not hold"),
                           ([{**row6, "bill": "HB1"}], "a bill that is not a CACR"),
                           ([row6, row6], "a bill named twice"),
                           ([{**row6, "no": None}], "a yes with no no"),
                           ([{**row6, "yes": "452,307"}], "a count written as words"),
                           ([{**row6, "election": "November 5, 2024"}], "a day not a day")):
            f.write_text(json.dumps({"rows": rows}), encoding="utf-8")
            try:
                B.load_ballots(f, bills)
                bad.append(f"ballot_results.json with {what} was read without a word")
            except SystemExit:
                pass
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert not bad, "; ".join(bad)
    return "ok", ("two thirds of the votes cast, not a majority: 65.6% is not ratified and "
                  "exactly two thirds is; the docket's own referendum line stands; an "
                  "election to come stays to come; the voters' line, the Voters stop and "
                  "the list card's copy carry the day and the outcome; a docket tally that "
                  "is not the source's is kept to be said; a file naming no CACR is refused")


@check("frontend", "the voters' card and How it got here name the source their ballot row gives",
       needs=("build_site_v2",))
def _ballot_source_named(build_site_v2):
    """Whose the voters' count is, said from the row's own source
    (ballot_source.py), never in words of the page's own: the Votes tab card
    said "Ballotpedia, List of New Hampshire ballot measures" on every CACR
    and How it got here "(Ballotpedia's count)", and on 7 October 2026 the
    person made the Secretary of State every decided row's source, keeping
    Ballotpedia for the election still to come.

    Built here from rows shaped as ballot_results.json's (build_site_v2's
    ballot_card, ballot_step and docket_count_differs) and drawn in node by
    app.js. Fails on a decided row's card, history line or differing-docket
    note naming anyone but the source its row gives -- the Secretary of State
    for sos.nh.gov and NHPR's scan of its Manual alike, Ballotpedia for its
    list, and a host ballot_source.py does not list by that host -- or
    leaving out where the count is printed; on the row to come naming anyone
    but Ballotpedia; and on a label in parentheses, the file's description of
    how the source lists it, quoted as though it were the source's words."""
    B = build_site_v2
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "app.js, dom_stub.js or node is not here"
    import html as _html
    bad = []
    row24 = _voters_row("2023-2024", "CACR6", "2024-11-05", 452307, 237221, "Question No. 1")
    row22 = _voters_row("1997-1998", "CACR22", "1998-11-03", 119104, 169439, "Question 1",
                        _MANUAL_1999)
    row00 = _voters_row("1999-2000", "CACR6", "2000-11-07", 202367, 218875,
                        "(the only question; unnumbered)",
                        ("https://electiondatabase.nhpr.org/document/689?page=260",
                         "Manual for the General Court 2001, p. 423 (NHPR's scan)"))
    pending = _voters_row("2025-2026", "CACR13", "2026-11-03", None, None,
                          "Eliminate Office of Register of Probate Amendment", _BALLOTPEDIA,
                          "2026-10-05")
    # DECIDED ROWS FROM ANOTHER SOURCE (the review of 7 October 2026). Every
    # decided row above is the Secretary of State's, and the only Ballotpedia
    # row is still to come, with no voters' line and no docket note -- so a
    # page that wrote "the Secretary of State's" in words of its own passed
    # here. CACR 22 of 1998 as the file held it until that day, Ballotpedia's
    # with the docket's 159,439 beside it, and a row from a host
    # ballot_source.py does not list, which is named by its host.
    rowbp = _voters_row("1997-1998", "CACR22", "1998-11-03", 119104, 169439, "Question 1",
                        _BALLOTPEDIA, "2026-10-05")
    rowx = _voters_row("2023-2024", "CACR6", "2024-11-05", 452307, 237221, "Question No. 1",
                       ("https://results.example.org/2024", "2024 general election results"))
    n22 = _nar(_ev("H", "AMENDMENT FAILED REFERENDUM  (119,104 - 159,439);  1998 RED BOOK, P350",
                   date="1998-11-03"))
    # How it got here: the voters' line, and the docket's where it differs.
    for row, what, whose in ((row24, "CACR 6 of 2024 (sos.nh.gov)", "the Secretary of State's"),
                             (row22, "CACR 22 of 1998 (NHPR's scan of the Manual)",
                              "the Secretary of State's"),
                             (rowbp, "CACR 22 of 1998 (Ballotpedia's)", "Ballotpedia's"),
                             (rowx, "CACR 6 of 2024 (results.example.org)",
                              "results.example.org's")):
        t = B.ballot_step(row)["text"]
        if not t.endswith(f"({whose} count)"):
            bad.append(f"{what}'s voters' line reads {t!a}")
    for row, whose in ((row22, "the Secretary of State's"), (rowbp, "Ballotpedia's")):
        said = B.docket_count_differs(row)
        if said != f" (the docket's count; {whose} is 119,104–169,439)":
            bad.append(f"CACR 22 of 1998's docket line, its row {whose}, adds {said!a}")
    recs = {"row24": B.ballot_card(row24, None), "row22": B.ballot_card(row22, n22),
            "row00": B.ballot_card(row00, None), "rowbp": B.ballot_card(rowbp, n22),
            "rowx": B.ballot_card(rowx, None),
            "pending": B.ballot_card(pending, None, today=B._date(2026, 10, 5))}
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "recs.json").write_text(json.dumps(recs), encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
globalThis.fetch = async u => ({ok: true, status: 200, json: async () => ({H: [], S: []}),
  text: async () => "{}"});
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({renderVotes})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const recs = JSON.parse(fs.readFileSync("./recs.json", "utf8"));
const out = {};
for (const [k, v] of Object.entries(recs)) out[k] = s.renderVotes({id: "CACR6"}, {rollcalls: [], ballot: v});
process.stdout.write("\\n@@" + JSON.stringify(out));
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not draw the voters' card under node: "
            + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    def card(k):
        h = got[k]
        h = h[h.find('<section class="rc ballot"'):]
        return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h))).replace(" ,", ",")

    for k, want, other in (
            ("row24", "Source: Secretary of State, 2024 general election results, sos.nh.gov, "
                      "read Oct 7, 2026, which lists it as “Question No. 1”.", "Ballotpedia"),
            ("row22", "Source: Secretary of State, Manual for the General Court 1999, p. 350 "
                      "(NHPR's scan), read Oct 7, 2026, which lists it as “Question 1”.",
             "Ballotpedia"),
            ("row00", "which lists it as the only question, unnumbered.", "Ballotpedia"),
            ("rowbp", "Source: Ballotpedia, List of New Hampshire ballot measures, read "
                      "Oct 5, 2026, which lists it as “Question 1”.", "Secretary of State"),
            ("rowx", "Source: results.example.org, 2024 general election results, read "
                     "Oct 7, 2026, which lists it as “Question No. 1”.", "Secretary of State"),
            ("pending", "Source: Ballotpedia, List of New Hampshire ballot measures, read "
                        "Oct 5, 2026, which lists it as “Eliminate Office of Register of "
                        "Probate Amendment”.", "Secretary of State")):
        text = card(k)
        if want not in text or other in text:
            bad.append(f"the {k} card reads {text[-260:]!a}")
    if "Ballotpedia" in card("rowx"):
        bad.append(f"a row from a host of its own is credited to Ballotpedia: {card('rowx')!a}")
    for k, whose in (("row22", "the Secretary of State's"), ("rowbp", "Ballotpedia's")):
        if f"The counts above are {whose}, and How it got here gives the docket's." \
                not in card(k):
            bad.append(f"CACR 22 of 1998's card, its row {whose}, does not say whose its counts "
                       f"are: {card(k)[-400:]!a}")
    assert not bad, "; ".join(bad[:4])
    return "ok", ("a decided row's card, voters' line and differing-docket note name the "
                  "source its row gives -- the Secretary of State with where it is printed, "
                  "Ballotpedia, or a host of its own -- and the row to come, Ballotpedia; "
                  "a label in parentheses said as a description")


@check("status", "what the two chambers did with each other's version is read from the docket",
       needs=("build_site_v2",))
def _between_chambers(build_site_v2):
    """Every line below is a real docket row, quoted from Docket.txt,
    Docket_2023-2024.txt, Docket_2021-2022.txt, Docket_db_* or the narrated
    record built from them.

    The status fields name one chamber's last stage and stop: CACR 13 of
    2026 read "Passed one chamber" beside its own "Senate: PASSED/ADOPTED";
    HB 1215 of 2024 read "Conference committee report adopted" over the
    House voting that report down 102-261; SB 34 of 2026 read "Passed one
    chamber" after the Senate refused to concur; HB 589 of 2002 read
    "Retained in committee" after passing both chambers. This fails on a
    return to any of them, on a reconsidered report read as rejected, and on
    a CACR said to be going to an election that has passed.
    """
    B = build_site_v2
    bad = []

    def want(label, got, what):
        if got != label:
            bad.append(f"{what}: wanted {label!r}, got {got!r}")

    # CACR 13 of 2026: both chambers by three fifths, and its own text names
    # the election -- future tense before it, past tense after.
    st = {"gen_status": "SENATE", "senate_status": "PASSED/ADOPTED", "body": "H"}
    n = _nar(_ev("H", "Introduced 01/07/2026 and referred to Judiciary", "introduced"),
             _ev("H", "Ought to Pass: MA DV 325-15 By Necessary Three-Fifths Vote 02/05/2026",
                 "floor", "MA", "Ought to Pass"),
             _ev("S", "Ought to Pass, RC 23Y-1N, MA, by Necessary 3/5; OT3rdg; 03/26/2026"))
    text = ("submitted to the qualified voters of the state at the state general "
            "election to be held in November, 2026.")
    d = B.bill_disposition({}, "CACR13", st, n, [], "2025-2026", "2025-2026",
                           term_over=True, text=text, today=B._date(2026, 9, 23))
    want("Passed both chambers, goes to the voters in November 2026", d.status, "CACR13 before the election")
    want("adopted", d.kind, "CACR13's kind")
    d = B.bill_disposition({}, "CACR13", st, n, [], "2025-2026", "2025-2026",
                           term_over=True, text=text, today=B._date(2026, 11, 4))
    want("Passed both chambers, went to the voters in November 2026", d.status, "CACR13 after the election")
    d = B.bill_disposition({}, "CACR13", st, n, [], "2025-2026", "2027-2028")
    want("Passed both chambers, went to the voters", d.status, "a closed term's CACR")
    # The voters' own answer, where the docket records it.
    for raw, label in (("Amendment Failed Referendum (271,091 - 205,589); 2005 Red Book, p.___",
                        "Passed both chambers, not ratified by the voters"),
                       ("AMENDMENT ADOPTED BY 2/3 REF(199,229-26,336); 1991 RED BOOK,P294",
                        "Passed both chambers, ratified by the voters")):
        n2 = _nar(*n["events"], _ev("H", raw))
        d = B.bill_disposition({}, "CACR5", st, n2, [], "2003-2004", "2025-2026")
        want(label, d.status, raw[:30])
    # HCR 10 of 2024: gen_status PASSED and a House-only docket -- not both.
    st = {"gen_status": "PASSED", "house_status": "PASSED/ADOPTED", "senate_status": "", "body": "H"}
    n = _nar(_ev("H", "Ought to Pass : MA VV 02/01/2024", "floor", "MA", "Ought to Pass"))
    want("Passed one chamber", B.bill_disposition({}, "HCR10", st, n, [], "2023-2024",
                                                  "2025-2026").status, "HCR10 2024")
    # HCR 6 of 1990: the Senate's adoption is in the docket, not the fields.
    st = {"gen_status": "", "house_status": "PASSED/ADOPTED", "senate_status": ""}
    n = _nar(_ev("H", "REPS PALUMBO & CHAMBERS SUSP RULES TO CONSIDER, MA 2/3VV, ADOPTED HJ24, P399",
                 "floor", "MA", "Adopted"),
             _ev("S", "INTRODUCED AND ADOPTED", "floor", "MA"))
    d = B.bill_disposition({}, "HCR6", st, n, [], "1989-1990", "2025-2026")
    want("Adopted by both chambers", d.status, "HCR6 1990")
    # HB 1215 of 2024: the Senate adopted the report and the House voted it down.
    st = {"gen_status": "SENATE", "house_status": "CONFERENCE REPORT FAILED",
          "senate_status": "CONFERENCE REPORT ADOPTED"}
    n = _nar(_ev("H", "Ought to Pass with Amendment 2024-1080h: MA VV 03/28/2024", "floor", "MA",
                 "Ought to Pass with Amendment"),
             _ev("H", "House Concurs with Senate Amendment 2024-1961s (Rep. Alexander Jr.): MF RC 172-180 05/30/2024",
                 "floor", "MF"),
             _ev("H", "House Non-Concurs with Senate Amendment 2024-1961s and Requests CofC (Rep. Alexander Jr.): MA VV 05/30/2024",
                 "floor", "MA"),
             _ev("S", "Conference Committee Report #2024-2273c , Adopted, VV; 06/13/2024"),
             _ev("H", "Conference Committee Report 2024-2273c: Failed, RC 102-261 06/13/2024"))
    d = B.bill_disposition({}, "HB1215", st, n, [], "2023-2024", "2025-2026")
    want(B.CONF_REJECTED, d.status, "HB1215 2024")
    if not d.between:
        bad.append("HB1215 2024: decided by the docket but not marked so for status_source")
    # The older dockets' words for a report voted down, and a new conference
    # the other chamber refused (HB 381 of 2006, HB 252 of 2000, HB 1211 of 1992).
    for raws in (["Committee of Conference Report {2101}, Division 14Y-9N, Adopted",
                  "Conf Comm Report lost RC(154-175)"],
                 ["Conf Comm Report, Sen Trombly, MA, VV",
                  "Conf Comm Report Fails DIV(76-210); HJ77, p2079"],
                 ["CONF COMM REPORT ADOPTED VV; SJ21,P618-619",
                  "CONF COMM REPORT LOST RC(117-206); HOUSE DISCHARGE CONF COMM, REQ NEW CONF COMM, REP GROSS MA VV; HJ82,P2121-2124",
                  "SEN REFUSED TO ACCEDE TO REQ FOR NEW CONF COMM, SEN W. KING MA VV; SJ21,P670"]):
        got = B.between_chambers(_nar(*[_ev("H" if i % 2 else "S", r) for i, r in enumerate(raws)]),
                                 "Conference committee report adopted")
        want(("done", B.CONF_REJECTED), got, raws[-1][:34])
    # SB 14 of 2025: failed 183-186, reconsidered, adopted 185-182 -- not rejected.
    n = _nar(_ev("H", "Conference Committee Report 2025-2850c: Failed, RC 183-186 06/26/2025"),
             _ev("H", "Reconsider Adopt CofC Report (Rep. Litchfield): MA RC 184-182 06/26/2025"),
             _ev("H", "Conference Committee Report 2025-2850c: Adopted, RC 185-182 06/26/2025"))
    got = B.between_chambers(n, "In a committee of conference")
    if got and got[1] == B.CONF_REJECTED:
        bad.append("SB14 2025: a report adopted on reconsideration read as rejected")
    # SB 135 of 2013: a failed motion to RECONSIDER an adopted report, on a
    # bill that went to the governor, is not the report failing. In the
    # docket's own order (10:53:04, then 10:53:40) the reconsideration is the
    # House's last word, so only the skip keeps it from reading as rejected;
    # same-day rows are not reliably in order, so both orders are tried.
    adopt = _ev("H", "Conference Committee Report #2089c Adopted, VV; HJ52, PG.1675")
    recon = _ev("H", "Reconsideration, Conference Committee Report #2089c (Rep Lambert): MF RC 108-247; HJ52, PG.1678-1680", "floor", "MF")
    senate = _ev("S", "Conference Committee Report 2089c; Adopted, VV")
    for order in ((adopt, recon, senate), (recon, adopt, senate)):
        got = B.between_chambers(_nar(*order), "Passed, awaiting the governor")
        if got:
            bad.append(f"SB135 2013: a failed reconsideration moved an enrolled bill to {got}")
    # The report's own clause decides, not the row: HB 170 of 2001's failed
    # motion to reconsider follows the report on the same row, and HB 50 of
    # 1997's failed motion to table comes before it.
    for raws in (("Conference Committee Report, , RC 15Y-9N, Adopted; SJ 19, Pg.592-623",
                  "Conf Comm Report Adopted RC(190-181);  Rep Herman moved to Reconsider, ML RC(177-192);"),
                 ("CONF COMM REPORT ADOPTED RC(22-2); SJ23(I),P5527-532",
                  "REP K SMITH MOVED LOT, ML RC(112-252); CONF COMM REPORT ADOPTED")):
        got = B.between_chambers(_nar(_ev("S", raws[0]), _ev("H", raws[1])),
                                 "Conference committee report adopted")
        if got:
            bad.append(f"{raws[1][:30]}: another motion's ML read as the report failing ({got})")
    # SB 34 of 2026: the House passed it amended, the Senate refused to concur.
    st = {"house_status": "PASSED/ADOPTED WITH AMENDMENT", "senate_status": None}
    n = _nar(_ev("S", "Ought to Pass: RC 16Y-8N, MA; OT3rdg; 03/06/2025"),
             _ev("H", "Ought to Pass with Amendment 2025-3056h: MA RC 186-155 01/07/2026", "floor",
                 "MA", "Ought to Pass with Amendment"),
             _ev("S", "Sen. Ward Moved Nonconcur with the House Amendment, MA, VV; 02/05/2026",
                 "floor", "MA"))
    d = B.bill_disposition({}, "SB34", st, n, [], "2025-2026", "2025-2026")
    want("One chamber did not concur", d.status, "SB34 2026, in session")
    # And once the session is over, that is how it died (17 October 2026).
    d = B.bill_disposition({}, "SB34", st, n, [], "2025-2026", "2025-2026", term_over=True)
    want("Died: the chambers did not agree on a version", d.status, "SB34 2026")
    # HB 549 of 1991: both chambers' fields say PASSED/ADOPTED, the Senate's
    # WITH AMENDMENT, and the House never took the amendment up -- not
    # "Passed one chamber". A House resolution the docket shows "Introduced
    # and Adopted" (HR 13 of 2007) is not "In committee".
    st = {"gen_status": "SENATE", "house_status": "PASSED/ADOPTED WITH AMENDMENT",
          "senate_status": "PASSED/ADOPTED WITH AMENDMENT"}
    n = _nar(_ev("H", "APPROP AM, AA VV; PASSED WITH AM VV; HJ65,P1476 + 1480", "floor", "MA",
                 "Passed with Am"),
             _ev("S", "FL AM (NEW TITLE), AA VV; SEN W. KING FL AM (NEW TITLE), AA VV; PASSED WITH "
                      "AM VV; SJ34,P696-697 + 699", "floor", "MA", "Passed with Am"))
    want("Died when the session ended", B.bill_disposition({}, "HB549", st, n, [], "1991-1992",
                                                           "2025-2026").status, "HB549 1991")
    want("Adopted by the House", B.bill_disposition(
        {}, "HR13", {"gen_status": "HOUSE", "house_status": "", "senate_status": ""},
        _nar(_ev("H", "Introduced and Adopted")), [], "2007-2008", "2025-2026").status, "HR13 2007")
    # HB 1432 of 2022: the conference asked for was refused, so none sat.
    n = _nar(_ev("H", "House Non-Concurs with Senate Amendment 2022-1837s and Requests CofC (Reps. McConkey, Milz, B. Boyd, Fedolfi): MA VV 05/05/2022", "floor", "MA"),
             _ev("S", "Sen. Birdsell Refused to Accede to House Request for Committee of Conference, MA, VV; 05/12/2022", "floor", "MA"))
    want(("active", "One chamber did not concur; a committee of conference was asked for"),
         B.between_chambers(n, "In a committee of conference"), "HB1432 2022")
    # And its term over, that refusal is how it died, as HB 191 of 2026's
    # was (the language sweep of 17 October 2026): not a conference pending.
    d = B.bill_disposition({}, "HB1432", {"gen_status": "HOUSE",
                                          "house_status": "CONFERENCE COMMITTEE",
                                          "senate_status": "CONFERENCE COMMITTEE"},
                           n, [], "2021-2022", "2025-2026")
    want(("done", "Died: the chambers did not agree on a version"), (d.kind, d.status),
         "HB1432 2022, its term over")
    # HB 589 of 2002: retained, then passed both chambers and went to conference.
    n = _nar(_ev("H", "Retained in Committee", "retained"),
             _ev("H", "Comm Am{2307}, AA VV; Passed with Am VV", "floor", "MA", "Ought to Pass with Amendment"),
             _ev("S", "Ought to Pass with Amendment, MA, VV", "floor", "MA", "Ought to Pass with Amendment"),
             _ev("H", "House Nonconc with Sen Am req Conf Comm, Rep Gilman MA VV", "floor", "MA"),
             _ev("H", "(Conf Comm Report Not Signed)"))
    d = B.bill_disposition({}, "HB589", {}, n, [], "2001-2002", "2025-2026")
    if d.status == "Retained in committee" or B.classify(n, [], "HB")[1] == "Retained in committee":
        bad.append("HB589 2002: still 'Retained in committee' after passing both chambers")
    # 2020: laid on the table in the Senate, killed at adjournment by Rule 3-23.
    st = {"senate_status": "LAID ON TABLE"}
    n = _nar(_ev("S", "Vacated from Committee and Laid on Table, MA, VV; 06/16/2020", "floor", "MA"),
             _ev("S", "Inexpedient to Legislate, Senate Rule 3-23, Adjournment 09/16/2020"))
    want("Died on the table", B.bill_disposition({}, "CACR20", st, n, [], "2019-2020",
                                                 "2025-2026").status, "CACR20 2020")
    # The rails: no governor on a resolution, both chambers passed on one
    # both adopted, and two stops for a special session's House resolution.
    rail = B.passage([{"hand": "H:floor"}, {"hand": "S:floor"}, {"hand": "G:governor"}],
                     "adopted", "Passed both chambers, went to the voters", "CACR5")
    want("Hpp--", rail, "CACR5 2004's rail")
    want("Hpp", B.passage([{"hand": "H:floor"}], "adopted", "Adopted by the House", "SSHR1"),
         "SSHR1 2008's rail")
    # Both chambers decided, and the docket's first row is the second
    # chamber's: the bill's number says where it started. HB 1650 of 2022's
    # House rows were entered after the Senate's; HB 652 of 2011's Senate
    # introduction is dated before the House passed it.
    want("Hpppp", B.passage([{"hand": "S:floor"}, {"hand": "G:governor"}], "law",
                            "Signed into law", "HB1650", {"H", "S"}, ["S", "H"]),
         "HB1650 2022's rail")
    want("Hpx-x", B.passage([{"hand": "S:committee"}, {"hand": "H:floor"}, {"hand": "S:floor"}],
                            "done", "Killed", "HB652", {"H"}, ["H", "S"]), "HB652 2011's rail")
    assert not bad, "; ".join(bad)
    return "ok", ("both chambers adopted, a report voted down, a refusal to concur, "
                  "a retention moved past, the voters' answer, each from the docket")


@check("data", "a database dump on this disk holds each of the two newest terms that has a "
               "status page stating nothing")
def _a_dump_holds_the_terms_it_fills():
    """Where a bill's status page states nothing and the docket gives only a
    guess, the General Court's own code answers, from db/Legislation.psv or,
    once the General Court has turned its views over to the next term, from
    the copy frozen at the term's end (db/term/<term>/Legislation.psv). If
    neither holds the term, HB 1708 and HB 1824 of 2026 and HCR 1, HCR 4 and
    HCR 9 of 2025 go back to "In committee" and "In progress" and nothing
    fails: the build says so in one line, and this says it where a person
    making preflight green will see it.

    A data check and not a code one, on purpose: nightly.py gates itself on
    preflight --code, and a missing dump must not stop a night's build."""
    B = imp("build_site_v2")
    if B is None:
        return "skip", "build_site_v2 will not import"
    import proceedings as P
    try:
        bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
        pages = json.loads(Path("bill_status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "skip", "no data/bills.json or bill_status.json here"
    if not bills:
        return "skip", "data/bills.json holds no term"
    current = max(bills)
    fields = ("gen_status", "house_status", "senate_status")
    problems, said = [], []
    for term in sorted(bills)[-2:]:
        page = P.per_term(pages, term, current)
        blank = [b for b, rec in bills[term].items()
                 if not any(((page.get(b) or {}).get(f) or rec.get(f) or "").strip()
                            for f in fields)]
        held = B.db_statuses(term)
        said.append(f"{term}: {len(blank):,} with nothing stated, {len(held):,} in a dump")
        if blank and not held:
            problems.append(
                f"no database dump holds {term}, and {len(blank):,} of its measures have a "
                f"status page that states nothing (e.g. {', '.join(sorted(blank)[:4])}): each "
                "reads whatever the docket alone gives it. The dump is db/Legislation.psv "
                f"(python3 src/fetch/gc_db/fetch_status_db.py, a person's to start) or db/term/{term}/"
                "Legislation.psv, the copy frozen at the term's end")
    assert not problems, "\n".join(problems)
    return "ok", "; ".join(said)


@check("status", "conferees who could not agree end the bill, and nothing says their report was adopted",
       needs=("build_site_v2",))
def _conferees_could_not_agree(build_site_v2):
    """69 bills of 1989-2010 read "Conference committee report adopted", the
    status fields' CONFERENCE REPORT ADOPTED, where every one's docket says
    the conferees were unable to agree and the bill died: HB 42 of 1989, "CONF
    COMM REPORT ADOPTED VV, UNABLE TO AGREE"; HB 431 of 2010, whose "Unable to
    Reach Agreement" is on the row that files the report and not the one that
    adopts it. The rows below are theirs. A report adopted where the
    conferees agreed keeps its label, and so does one a new conference
    replaced (HB 1210 of 2002, Chapter 230); one the other chamber refused to
    replace does not (SB 69 of 2001)."""
    B = build_site_v2
    bad = []
    conf = {"gen_status": "SENATE", "house_status": "CONFERENCE REPORT ADOPTED",
            "senate_status": "CONFERENCE REPORT ADOPTED"}
    otpa = "Ought to Pass with Amendment"
    ask = _ev("H", "HOUSE NONCONCUR WITH SEN AM, REQ CONF COMM, REP WARD MA VV", "floor", "MA",
              "Nonconcur", date="1989-05-12")
    hb42 = _nar(_ev("H", "PASSED/ADOPTED WITH AM; HJ21, P337-338 + 347", "floor", "MA", otpa,
                    date="1989-02-09"),
                _ev("S", "PASSED/ADOPTED WITH AM", "floor", "MA", otpa, date="1989-05-09"),
                ask, _ev("S", "SENATE ACCEDED TO REQ FOR CONF COMM", date="1989-05-16"),
                _ev("S", "CONFEREES UNABLE TO AGREE", date="1989-05-23"),
                _ev("H", "CONF COMM REPORT ADOPTED VV, UNABLE TO AGREE; HJ93, P2789", "floor",
                    "MA", "Conference Committee Report", date="1989-05-23"))
    hb431 = _nar(_ev("H", "Ought to Pass: MA DIV 251-92", "floor", "MA", "Ought to Pass",
                     date="2010-03-24"),
                 _ev("S", "Ought to Pass with Amendment 2063s, MA, VV; OT3rdg", "floor", "MA",
                     "Ought to Pass with Amendment 2063s", date="2010-05-13"),
                 _ev("H", "House Non-Concurs with Senate AM and Requests Comm of Conf (Rep Hess): MA VV",
                     "floor", "MA", "House Non-Concurs with Senate AM and Requests Comm of Conf "
                     "(Rep Hess)", date="2010-05-19"),
                 _ev("H", "Conference Committee Report 2246; Unable to Reach Agreement, Filed",
                     date="2010-05-27"),
                 _ev("S", "Conference Committee Report 2246; Adopted, VV", date="2010-06-02"),
                 _ev("H", "Conference Committee Report #2246 Adopted, VV", date="2010-06-02"))
    for bid, term, n in (("HB42", "1989-1990", hb42), ("HB431", "2009-2010", hb431)):
        d = B.bill_disposition({}, bid, conf, n, [], term, "2025-2026")
        if (d.kind, d.status) != ("done", B.CONF_UNABLE) or not d.between:
            bad.append(f"{bid} of {term}: {(d.kind, d.status, d.between)}")
            continue
        end = B.closing_stage(d.status, n) or {}
        if not end.get("text") or "adopted" in end["text"].lower():
            bad.append(f"{bid}: How it ended reads {end.get('text')!r}")
        _intro, steps = B.journey(n, bid, [], "", "", term)
        said = [s["text"] for s in steps if s["act"] == "conf_adopted"]
        if not said or any("could not agree" not in t for t in said):
            bad.append(f"{bid}: How it got here reads {said!r}")
        # Never "...could not agree on a voice vote": it reads as though the
        # voice vote were what they could not agree on.
        if any(t.rstrip().endswith("could not agree on a voice vote") for t in said):
            bad.append(f"{bid}: How it got here reads {said!r}, which puts the vote "
                       "after 'could not agree'")
        rail = B.passage(n.get("stages"), d.kind, d.status, bid, {"H", "S"}, ["H", "S"])
        why = B.journey_disagrees(steps, d.kind, d.status, rail, bid)
        if why:
            bad.append(f"{bid}: the journey disagrees with its status: {why}")
    # Agreed, and a report replaced by a new conference: the label stands.
    agreed = _nar(ask, _ev("S", "Conference Committee Report #2089c Adopted, VV; SJ 19"),
                  _ev("H", "Conference Committee Report #2089c Adopted, VV; HJ52, PG.1675"))
    renewed = _nar(ask, _ev("S", "Conference Committee Report [Not Signed]"),
                   _ev("H", "CONF COMM REPORT (UNABLE TO AGREE) FILED"),
                   _ev("H", "Rep Goulet Susp Rules for New Conf Comm, MA 2/3DIV(256-44); House Acceded to req"),
                   _ev("H", "New Conf Comm Report{3763} Adopted VV; HJ40, p1487"))
    for what, n in (("an agreed report", agreed), ("a report a new conference replaced", renewed)):
        d = B.bill_disposition({}, "HB1210", conf, n, [], "2001-2002", "2025-2026")
        if d.status != "Conference committee report adopted":
            bad.append(f"{what}: {d.status!r}")
    refused = [_ev("S", "Conf Comm Report (UNABLE TO AGREE) Filed"),
               _ev("S", "Sen. Pignatelli Motion to Request New Committee of Conference MA, VV"),
               _ev("H", "House Refused to Accede to req for New Conf Comm, Rep Mock MA VV; HJ61, p1797")]
    if not B.conferees_disagreed(refused):
        bad.append("SB69 of 2001: a new conference the House refused undid the report of no agreement")
    assert not bad, "; ".join(bad)
    return "ok", (f"{B.CONF_UNABLE!r}, with a closing paragraph and a journey that say so; "
                  "an agreed or replaced report keeps its label")


@check("status", "a kill the chamber reconsidered and then passed the bill over is not a kill",
       needs=("build_site_v2",))
def _reconsidered_kill(build_site_v2):
    """HB 323 of 2005 read "Killed". The House adopted Inexpedient to
    Legislate on 23 March 2005, 164-153; on 30 March it reconsidered, 153-150,
    voted the kill down and passed the bill, which the Senate passed and a
    committee of conference never signed a report on. classify() read
    "inexpedient to legislate" anywhere among the motions carried, so the
    kill the House had undone was the answer (approved to fix, 25 September).

    It still reads a kill that stood: HB 1267 of 2012, where a SPECIAL ORDER
    for a reconsideration carried and the reconsideration itself then failed;
    and HB 666 of 1997, reconsidered and killed again in a row the parser reads
    in two halves. Every row below is the bill's own, from its docket.
    """
    B = build_site_v2
    hb323 = _nar(
        _ev("H", "ITL MA RC(164-153)", "floor", "MA", "Inexpedient to Legislate",
            date="2005-03-23"),
        _ev("H", "Rep Norelli moved to Reconsider, MA RC(153-150); ITL ML DIV(149-151); "
                 "Rep Kurk Fl Am{0867}, AA", "floor", "MA", "Reconsider", date="2005-03-30"),
        _ev("H", "DIV(182-116); Passed with Am VV", "floor", "MA",
            "Ought to Pass with Amendment", date="2005-03-30"))
    hb1267 = _nar(
        _ev("H", "Inexpedient to Legislate: MA VV", "floor", "MA", "Inexpedient to Legislate",
            date="2012-03-15"),
        _ev("H", "Special Order (Reconsideration Motion) to Next Session Day (Rep Jasper): MA VV",
            "floor", "MA",
            "Special Order (Reconsideration Motion) to Next Session Day (Rep Jasper)",
            date="2012-03-21"),
        _ev("H", "Reconsideration (Rep DeLemus): MF DIV 103-233", "floor", "MF",
            "Reconsideration (Rep DeLemus)", date="2012-03-28"))
    hb666 = _nar(
        _ev("H", "ITL REPORT ADOPTED VV; HJ33,P798", "floor", "MA", "Inexpedient to Legislate",
            date="1997-03-05"),
        _ev("H", "REP GIBBONS MOVED TO RECONSIDER, MA DIV(213-116); ITL REPORT", "floor", "MA",
            "Reconsider", date="1997-03-05"),
        _ev("H", "ADOPTED RC(233-114); HJ33,P798-800", "floor", "MA", "Adopt",
            date="1997-03-05"))
    # The 30 March entry as docket_era_1999.join_rows hands it over since 1
    # October: one line, told by its last carried question, the passage.
    hb323_whole = _nar(
        _ev("H", "ITL MA RC(164-153)", "floor", "MA", "Inexpedient to Legislate",
            date="2005-03-23"),
        _ev("H", "Rep Norelli moved to Reconsider, MA RC(153-150); ITL ML DIV(149-151); "
                 "Rep Kurk Fl Am{0867}, AA DIV(182-116); Passed with Am VV", "floor", "MA",
            "Ought to Pass with Amendment", date="2005-03-30"))
    # And as it has been told since the joined line was split into its
    # questions again (docket_vocab.questions): the reconsideration, the kill
    # voted down, the amendment and the passage, each its own event.
    hb323_split = _nar(
        _ev("H", "ITL MA RC(164-153)", "floor", "MA", "Inexpedient to Legislate",
            date="2005-03-23"),
        _ev("H", "Rep Norelli moved to Reconsider, MA RC(153-150)", "floor", "MA", "Reconsider",
            date="2005-03-30"),
        _ev("H", "ITL ML DIV(149-151)", "floor", "ML", "Inexpedient to Legislate",
            date="2005-03-30"),
        _ev("H", "Rep Kurk Fl Am{0867}, AA DIV(182-116)", "amendment", "AA", date="2005-03-30"),
        _ev("H", "Passed with Am VV", "floor", "MA", "Ought to Pass with Amendment",
            date="2005-03-30"))
    got = {bid: B.classify(n, [], "HB") for bid, n in
           (("HB323", hb323), ("HB323 read whole", hb323_whole),
            ("HB323 by question", hb323_split), ("HB1267", hb1267), ("HB666", hb666))}
    bad = []
    if got["HB323"] == ("done", "Killed"):
        bad.append("HB 323 of 2005 is 'Killed' by a kill the House reconsidered and passed it over")
    if got["HB323 read whole"] == ("done", "Killed"):
        bad.append("HB 323 of 2005, its 30 March entry read whole, is 'Killed': the "
                   "reconsideration in the passage's own line was not read")
    if got["HB323 by question"] == ("done", "Killed"):
        bad.append("HB 323 of 2005, its 30 March entry told question by question, is "
                   "'Killed' by the kill its own reconsideration undid")
    if len(set(got[k] for k in ("HB323", "HB323 read whole", "HB323 by question"))) != 1:
        bad.append("HB 323 of 2005 reads differently by how its 30 March entry is cut: "
                   + repr({k: got[k] for k in got if k.startswith("HB323")}))
    for bid in ("HB1267", "HB666"):
        if got[bid] != ("done", "Killed"):
            bad.append(f"{bid}'s kill stood and it reads {got[bid]}")
    assert not bad, "; ".join(bad)
    return "ok", ("HB 323 of 2005 is not killed by the kill it was reconsidered out of, "
                  "its 30 March entry cut in two or read whole; HB 1267 of 2012 and "
                  "HB 666 of 1997, whose kills stood, are")


@check("status", "a failed reconsideration does not take a re-referral down with it on the "
       "rail or in the Reports tab", needs=("build_site_v2",))
def _rail_reconsider_own_outcome(build_site_v2):
    """SB 135 of 1999 on 22 June: "Re-Referred to Res, Rec & Dev committee
    RC(158-154); Rep Royce moved to reconsider, ML RC(156-157)", one line the
    database cut in two and the 1999-2006 reader now reads whole
    (Docket_db_1999-2000.txt). The rail lent the reconsideration's ML to the
    re-referral before it, which has no outcome word of its own, and the
    bill's step "Sent back to committee, 158-154" left its page. Measured
    over every history, SB 135 is the one rail this moves."""
    B = build_site_v2
    sb135 = _nar(_ev("H", "Re-Referred to Res, Rec & Dev committee RC(158-154); Rep Royce "
                          "moved to reconsider, ML RC(156-157)", "rereferred",
                     date="1999-06-22"))
    _intro, steps = B.journey(sb135, "SB135", [], "", "", "1999-2000")
    got = [(s["date"], s["act"], s.get("text")) for s in steps]
    assert got == [("1999-06-22", "recommitted", "Sent back to committee, 158–154")], (
        f"SB 135's re-referral of 22 June 1999 is not on its rail as carried: {got}")
    assert B._j_segments("Rep X moved to reconsider; MA VV") == [
        "Rep X moved to reconsider; MA VV"], (
        "an outcome alone no longer joins the reconsideration it decides")
    # The Reports tab reads the same line for why there is a second report,
    # and lent the ML the same way: it gave a cancelled subcommittee session
    # of 27 September 1999 as the reason. Measured over every history, SB 135
    # is the one line this moves; a reconsideration that CARRIED is left be.
    line = ("Re-Referred to Res, Rec & Dev committee RC(158-154); Rep Royce moved "
            "to reconsider, ML RC(156-157); HJ73, p1926-1930")
    assert B._again_carried(line) is True, (
        "the Reports tab reads SB 135's re-referral of 22 June 1999 as failed, "
        "from its failed reconsideration's ML")
    assert B._again_carried("Recommitted, Rep X MA VV; Rep Y moved to reconsider, ML VV") is True
    assert B._again_carried("Rep X moved Recommit, ML RC(100-200); Rep Y moved to "
                            "reconsider, ML VV") is False, (
        "a recommittal that failed in its own clause reads as carried")
    # The same line as the history has held it since it was told question by
    # question (docket_vocab.questions): the re-referral, carrying the whole
    # line, and the failed reconsideration as an event of its own. The rail
    # joins a row to the one before it where the first names a motion and the
    # second its outcome, and read these two clauses as that: a re-referral
    # that failed. It reads the line, once; and the page lists it once.
    whole = line
    split = _nar(
        {**_ev("H", "Re-Referred to Res, Rec & Dev committee RC(158-154)", "rereferred",
               date="1999-06-22"), "line": whole},
        {**_ev("H", "Rep Royce moved to reconsider, ML RC(156-157); HJ73, p1926-1930",
               "floor", "ML", "reconsider", date="1999-06-22"), "in_line": True})
    _intro, steps = B.journey(split, "SB135", [], "", "", "1999-2000")
    assert [(s["date"], s["act"], s.get("text")) for s in steps] == got, (
        "SB 135's re-referral, told as its own question beside the failed motion to "
        f"reconsider it, is not on its rail: {[(s['date'], s['act'], s.get('text')) for s in steps]}")
    assert [raw for _e, raw in B._j_rows(split["events"])] == [whole], (
        "the rail reads a line told question by question more than once, or in pieces: "
        f"{[raw for _e, raw in B._j_rows(split['events'])]}")
    assert [B.docket_line(e) for e in B.docket_lines(split)] == [whole], (
        "a line told question by question is not listed once, whole, among the "
        f"bill's docket lines: {[B.docket_line(e) for e in B.docket_lines(split)]}")
    # And the Reports tab quotes the line, not a clause of it: HB 278 of
    # 1999's failed motion to recommit, read as an event of its own, was
    # given alone as what the docket records between the bill's two reports.
    hb278 = ("Comm Am, AA VV; Rep Soltani moved to recommit, ML VV; Passed with Am and ref "
             "to Finance VV; HJ29, p633-634")
    told = _nar(
        {**_ev("H", "Maj Report OTP/AM for Mar 18 (vote 14-2;CC)", "report",
               date="1999-03-10"), "recommendation": "Ought to Pass with Amendment"},
        {**_ev("H", "Comm Am, AA VV", date="1999-03-18"), "in_line": True},
        {**_ev("H", "Rep Soltani moved to recommit, ML VV", "floor", "ML",
               "Rerefer to Committee", date="1999-03-18"), "in_line": True},
        {**_ev("H", "Passed with Am and ref to Finance VV; HJ29, p633-634", "floor", "MA",
               "Ought to Pass with Amendment", date="1999-03-18"), "line": hb278},
        {**_ev("H", "Fin Maj Report OTP for Apr 8 (vote 20-1;Reg)", "report",
               date="1999-03-31"), "recommendation": "Ought to Pass"})
    _out, _docket, between = B.committee_reports([], told, {}, "Judiciary", "")
    assert [x["text"] for x in between] == [hb278], (
        f"the note between HB 278's two reports quotes a clause, not the docket's line: {between}")
    return "ok", ("SB 135 is sent back 158-154 on the rail and in the Reports tab, its line "
                  "read whole or question by question; its failed reconsideration keeps "
                  "its own ML; HB 278's note between reports quotes the whole line")


# =============================================================== code: naming ==

@check("naming", "members are named the same way everywhere",
       needs=("build_site_v2",))
def _naming(build_site_v2):
    m = build_site_v2.member_labels
    cases = [
        (dict(chamber="H", party="R", district="13", county="Rockingham"),
         "Nelson, Jodi", "Rep. Jodi Nelson (R)", "Rep. Jodi Nelson (R - Rock 13)"),
        (dict(chamber="S", party="D", district="24"),
         "Altschiller, Debra", "Sen. Debra Altschiller (D)",
         "Sen. Debra Altschiller (D - SD24)"),
        (dict(chamber="H", party="R", district="13", county="Rockingham"),
         "Rep. Jodi Nelson (R)", "Rep. Jodi Nelson (R)",
         "Rep. Jodi Nelson (R - Rock 13)"),
        # build_data's composite label keeps its own punctuation; what the
        # site draws does not. The abbreviation lost its trailing point so
        # that a member named from the roster and one named from
        # former_members.json read alike -- the difference used to track
        # exactly who had left office.
        (dict(chamber="H", party="R", district="13", county="Rockingham"),
         "Nelson, Jodi(R) Rock 13", "Rep. Jodi Nelson (R)",
         "Rep. Jodi Nelson (R - Rock 13)"),
        (dict(chamber="H", district="7", county="Merrimack"),
         "Doe, Pat", "Rep. Pat Doe", "Rep. Pat Doe (Merr 7)"),
        (dict(chamber="H", party="R"),
         "Doe, Pat", "Rep. Pat Doe (R)", "Rep. Pat Doe (R)"),
    ]
    wrong = []
    for kw, name, want_short, want_full in cases:
        lab = m(name, **kw)
        if lab["display"] != want_short or lab["display_full"] != want_full:
            wrong.append(f"{name!r} -> {lab['display']} / {lab['display_full']}")
    assert not wrong, "; ".join(wrong)
    assert m("Nelson, Jodi", chamber="H")["sort"] == "nelson, jodi"
    return "ok", "6 shapes including the composite label and the missing party"


@check("naming", "an unnamed member is not dressed up as a person",
       needs=("build_site_v2",))
def _placeholder(build_site_v2):
    lab = build_site_v2.member_labels("Member #377204", chamber="H", party="R")
    assert lab["display"] == "Member #377204", lab["display"]
    return "ok", "no honorific, no party letter"


@check("naming", "a roll call's member is labelled once for each name, chamber and party: what "
       "is kept is what labelling afresh gives, the unnamed are noted on every ballot, and a "
       "caller's change to an entry stays its own", needs=("build_site_v2",))
def _vote_member_kept(build_site_v2):
    """vote_member keeps the label pair it draws -- the name shown and the
    name sorted -- by the name it settles on, the chamber and the party (16
    October 2026, private/SITE_DATA_PROFILE.md, P3): bill_rollcalls asks it
    for 2.2 million ballots of a few thousand people. Held here against the
    plain path, member_labels asked for every ballot as vote_member did
    before, on the fixture's ballots and roster and on the shapes a ballot's
    name comes in: the roster's name where the vote has none, a placeholder
    noted as unnamed, the roster's chamber over the vote's, a member who
    changed party, a party in lower case or missing. Each ballot is asked
    cold and again warm. A member who names nobody is noted in whatever set
    the caller passes, kept pair or not; a caller that changes the entry it
    was given does not change the next caller's; a chamber no dict can hold
    fails as member_labels fails; and a member asked three times is labelled
    once. Undone, the step is slower and nothing else would say so."""
    B = build_site_v2
    tmp = Path(tempfile.mkdtemp(prefix="gr-vote-member-"))
    try:
        _site_fixture(tmp)
        votes = json.loads((tmp / "data" / "member_votes.json").read_text(encoding="utf-8"))
        roster = json.loads((tmp / "data" / "legislators.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    legs = {str(r["id"]): r for r in roster}
    legs["377299"] = {"name": "Barnes, Jr., John", "chamber": "S"}
    ballots = [(v, v.get("body") or "H") for v in votes]
    jodi = {"member_id": "377204", "name": "Nelson, Jodi", "vote": "Yea"}
    ballots += [
        ({**jodi, "party": "D"}, "H"),                       # the same member, another party
        ({**jodi, "party": "r"}, "H"),
        ({**jodi, "party": None}, "H"),
        ({**jodi, "party": "R", "name": "  Rep. Jodi  Nelson (R) "}, "H"),
        ({**jodi, "party": "R"}, "S"),                       # the roster's chamber over the vote's
        ({"member_id": "377207", "name": "", "party": "D", "vote": "Nay"}, "H"),
        ({"member_id": "377299", "name": None, "party": "R", "vote": "Nay"}, "H"),
        ({"member_id": "377299", "name": "Former Member", "party": "R", "vote": "Yea"}, "S"),
        ({"member_id": "990001", "name": "Member #990001", "party": "R", "vote": "Yea"}, "H"),
        ({"member_id": "990002", "name": "", "party": "", "vote": "Excused"}, "S"),
        ({"member_id": "990003", "name": "Smith, John, Jr.", "party": "I", "vote": "Yea"}, "S"),
        ({"member_id": "990003", "name": "Smith, John, Jr.", "party": "I", "vote": "Yea"}, "H"),
    ]

    def plain(m, body, legs, unnamed):
        # vote_member as it read before 16 October 2026: member_labels asked
        # for every ballot.
        raw = (m.get("name") or "").strip()
        if not raw or raw.lower().startswith(("member #", "former member")):
            raw = (legs.get(m.get("member_id"), {}).get("name") or raw or "").strip()
        if not raw or raw.lower().startswith(("member #", "former member")):
            unnamed.add(str(m.get("member_id")))
            raw = f"Member #{m.get('member_id')}"
        lab = B.member_labels(raw, chamber=(legs.get(m.get("member_id"), {})
                                            .get("chamber") or body), party=m.get("party"))
        return {"n": lab["display"], "s": lab["sort"] or B.sort_name(raw),
                "p": m.get("party") or "X", "v": m.get("vote")}
    want_unnamed = set()
    want = [plain(m, body, legs, want_unnamed) for m, body in ballots]
    bad = []
    B._VOTE_LABELS.clear()
    for when in ("cold", "warm"):
        unnamed = set()
        got = [B.vote_member(m, body, legs, unnamed) for m, body in ballots]
        for (m, body), g, w in zip(ballots, got, want):
            if g != w:
                bad.append(f"{when}: {m.get('name')!r} ({m.get('party')!r}, {body}) is {g}, "
                           f"labelled afresh {w}")
        if unnamed != want_unnamed:
            bad.append(f"{when}: the unnamed are {sorted(unnamed)}, labelled afresh "
                       f"{sorted(want_unnamed)}")
    # Noted in every set it is handed, the pair kept or not.
    for m, body in ballots:
        mine, theirs = set(), set()
        B.vote_member(m, body, legs, mine)
        plain(m, body, legs, theirs)
        if mine != theirs:
            bad.append(f"{m.get('name')!r} asked again notes {sorted(mine)} as unnamed, not "
                       f"{sorted(theirs)}")
    # A caller's change to its entry stays its own.
    for (m, body), w in zip(ballots, want):
        entry = B.vote_member(m, body, legs, set())
        entry.update(n="a name the caller changed", s="zz", p="Q")
        again = B.vote_member(m, body, legs, set())
        if again != w or again is entry:
            bad.append(f"a caller that changes its entry changes the next caller's: "
                       f"{m.get('name')!r} now reads {again}")
            break
    # A chamber no dict can hold fails as member_labels fails, not as a key.
    odd = {"x": {"name": "Odd, Pat", "chamber": ["H"]}}
    for fn in (plain, B.vote_member):
        try:
            fn({"member_id": "x", "name": "", "party": "R", "vote": "Yea"}, "H", odd, set())
            bad.append(f"{fn.__name__} labels a chamber of ['H'] without complaint")
        except AttributeError:
            pass
        except TypeError as e:
            bad.append(f"a chamber no dict can hold is refused as a key: {e}")
    asked = []
    # Counted where vote_member reads member_labels: its own module's (sponsors.py's since
    # 20 November 2026), which build_site_v2.vote_member is.
    space = B.vote_member.__globals__
    labels = space["member_labels"]
    space["member_labels"] = lambda *a, **k: (asked.append(a), labels(*a, **k))[1]
    try:
        B._VOTE_LABELS.clear()
        for _ in range(3):
            B.vote_member(dict(jodi, party="R"), "H", legs, set())
    finally:
        space["member_labels"] = labels
    if len(asked) != 1:
        bad.append(f"a member asked three times is labelled by member_labels {len(asked)} "
                   "times, not once: vote_member keeps no pair, or labels some other way, and "
                   "bill_rollcalls labels 2.2 million ballots")
    assert not bad, "\n".join(bad[:6])
    return "ok", (f"{len(ballots)} ballots labelled cold and warm as afresh, {len(want_unnamed)} "
                  "unnamed noted in every set; a caller's change to its entry stays its own; "
                  "a member asked three times labelled once")


@check("status", "the bill-text cache keeps each term's pages apart",
       needs=("fetch_bill_text",))
def _text_cache_by_term(fetch_bill_text):
    """fetch_bill_text cached bill_text/<BILL>.html, a name with no term in
    it, so a 2027 run would have found 2025's HB 1 "already fetched" and
    published its text under the new bill. The cache is
    bill_text/<term>/<BILL>.html now, and the flat files -- every one of them
    2025-2026's -- answer for that term and no other."""
    FB = fetch_bill_text
    tmp = Path(tempfile.mkdtemp(prefix="gr-textcache-"))
    try:
        (tmp / "HB1.html").write_text("2025's", encoding="utf-8")
        assert FB.cache_path(tmp, FB.LEGACY_TERM, "HB1") == tmp / "HB1.html"
        for term in ("2027-2028", "2023-2024"):
            got = FB.cache_path(tmp, term, "HB1")
            assert got == tmp / term / "HB1.html", f"{term} reads {got}"
        (tmp / FB.LEGACY_TERM).mkdir()
        (tmp / FB.LEGACY_TERM / "HB1.html").write_text("refetched", encoding="utf-8")
        assert FB.cache_path(tmp, FB.LEGACY_TERM, "HB1") == tmp / FB.LEGACY_TERM / "HB1.html", \
            "a term's own folder is not preferred to the flat file"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = _source(_paths.locate("fetch_bill_text.py"))
    assert "f = cache_path(cache, term, bid)" in src and 'cache / f"{bid}.html"' not in src, \
        "fetch_bill_text reads or writes its cache by the bill number alone again"
    return "ok", "2027's HB1 is not 2025's; the flat pages answer for 2025-2026 only"


@check("status", "stripping the page furniture never deletes a line of the bill")
def _chrome_spares_statute():
    """682 words of statute were deleted from five bills by a menu heading.

    bill_page.CHROME (fetch_bill_text's until 16 October 2026) lists the
    General Court's page furniture so a bill
    can be told apart from a navigation page, and strip_chrome drops any LINE
    that contains one of those phrases. The body of a bill is rendered a
    paragraph to a line, so a paragraph containing one of them went entirely.

    "other resources" is the phrase that did it -- a menu heading on their
    site, and also ordinary English. Across the 2,234 cached pages of the
    current term it cut 9 lines and every one was the bill's own words: HB2,
    HB1606, SB127, SB193 and SB551, 682 words in all. HB1606 lost the
    definition of "real property", and the published page then used the term
    26 times without ever defining it. The other ten phrases matched nothing
    on any of those pages, so the list was doing none of its intended work and
    all of this.

    The fix is a length test rather than a shorter list, because the bug is
    the class and not the phrase: "redistricting information" sitting in an
    election bill would be the same fault again. Furniture is a menu item of
    two to five words; the shortest line this wrongly cut was 20.

    No data on disk and no network: the samples below are the real sentences,
    so this runs under --code.
    """
    f = imp("bill_page")
    if f is None:
        return "skip", "bill_page will not import"
    statute = (
        'II. "Real property" means property consisting of land, buildings, '
        "crops, or other resources still attached to or within the land or "
        "improvements or fixtures permanently attached to the land or a "
        "structure on it."
    )
    kept = f.strip_chrome(statute)
    assert statute in kept, (
        "strip_chrome deleted a section of statute because it contains the "
        "words 'other resources'. That is how HB1606 came to use the term "
        "'real property' 26 times and never define it")

    # Every phrase in the list, in a sentence long enough to be the bill.
    for phrase in ("other resources", "redistricting information",
                   "quick links", "helpful links", "contact a senator",
                   "documents & media", "chaptered final version"):
        line = ("IV. The department shall publish a report describing the "
                f"{phrase} which it maintains for the several towns and the "
                "manner in which each may be obtained upon written request.")
        assert line in f.strip_chrome(line), (
            f"a section of statute containing {phrase!r} was deleted whole")

    # And the furniture it is actually for still goes.
    for junk in ("Quick Links", "Other Resources", "Skip to main content",
                 "My GCNH Portal", "Documents & Media"):
        assert f.strip_chrome(junk) == "", (
            f"{junk!r} survived: the page furniture is no longer removed, so "
            "a navigation page could be mistaken for a bill")
    return "ok", "9 lines, 682 words, five bills -- and the furniture still goes"


@check("status", "a bill's version is read from its own heading, not its fiscal note")
def _version_is_not_the_fiscal_note():
    """SB139 and SB290 were published as fiscal notes. They are not.

    bill_page.parse_text, which fetch_bill_text and bill_text_from_db both
    read printings with, takes the FIRST line matching VERSION_RE as the version,
    so a heading shape the pattern does not accept is not a missing version --
    it is the wrong one. A bill carrying a fiscal note prints a section
    heading like "SB 290-FN- FISCAL NOTE" partway down, and that line matches
    when the bill's own heading did not.

    Both bills' text was the introduced bill and only the label was wrong,
    which is the worse way round: the tab told a reader they were looking at a
    fiscal note while showing them the bill. The record agrees -- the database
    holds one printing of each, "Introduced", and no bill of this term has a
    "Fiscal Note" printing at all.

    The two headings are printed "SB - AS INTRODUCED", carrying no number, and
    "SB 139 -FN - AS INTRODUCED", with a space before the -FN. Measured over
    all 2,234 cached pages: 2,232 read exactly as before and no page lost a
    version it had.

    The samples are the real lines, so this needs nothing on disk.
    """
    f = imp("bill_page")
    if f is None:
        return "skip", "bill_page will not import"
    for line, want in (("SB - AS INTRODUCED", "AS INTRODUCED"),
                       ("SB 139 -FN - AS INTRODUCED", "AS INTRODUCED"),
                       ("HB 1442-FN - AS AMENDED BY THE HOUSE",
                        "AS AMENDED BY THE HOUSE"),
                       ("CACR 19 - AS INTRODUCED", "AS INTRODUCED"),
                       ("HB 2 - FINAL VERSION", "FINAL VERSION")):
        m_ = f.VERSION_RE.search(line)
        assert m_, f"VERSION_RE no longer matches the heading {line!r}"
        got = f.WS.sub(" ", m_.group("v")).strip()
        assert got == want, f"{line!r} read as {got!r}, wanted {want!r}"

    # The fiscal note's own heading must lose to the bill's, which comes first.
    page = ("SB 290 - AS INTRODUCED\n2025 SESSION\nSENATE BILL 290-FN\n"
            "AN ACT relative to a thing.\n\nSB 290-FN- FISCAL NOTE\n")
    got = f.WS.sub(" ", f.VERSION_RE.search(page).group("v")).strip()
    assert got == "AS INTRODUCED", (
        f"the fiscal note's section heading was read as the bill's version "
        f"({got!r}), which is how SB139 and SB290 came to be published as "
        "fiscal notes")
    return "ok", "the bill's own heading wins, in all five printed shapes"


@check("build", "a member who sat in both chambers and has left has one page, the later "
       "chamber's, as the person register joins them, and the earlier page's address "
       "answers with a 301", needs=("build_site_v2", "build_pages"))
def _former_movers_one_page(build_site_v2, build_pages):
    """build_site_v2.former_movers (30 October 2026): Shannon Chandley voted
    as 568 in the House and 9404 in the Senate and had a page for each,
    because member_links joins a mover's numbers only while they sit. The
    register's join -- the one the public data API publishes -- is taken for
    those who have left: the page that voted last keeps every chamber's
    votes, and build_pages answers the other's address with a 301. A number
    a sitting member holds or is joined to, and a person with one number
    that voted, are left as they were."""
    V, BP = build_site_v2, build_pages
    reg = {"people": [
        {"person": "568", "numbers": ["209104", "376802"]},    # moved and left
        {"person": "515", "numbers": ["209077", "376503"]},    # sits now (member_links has her)
        {"person": "900", "numbers": ["200001", "300001"]},    # only one number voted
        {"person": "27", "numbers": ["209015"]}]}
    e2p = {"209104": "9404", "376802": "568", "209077": "9406", "376503": "515",
           "200001": "901", "300001": "900"}
    # The record's own date form, m/d/Y, which sorts by the day only through
    # vote_date: as text, 9/13/2018 would come after 10/10/2018.
    v = lambda y, b, md="3/1": {"year": y, "date": f"{md}/{y}", "body": b}
    votes = {"568": [v("2009", "H"), v("2018", "H")], "9404": [v("2019", "S"), v("2024", "S")],
             "515": [v("2009", "H")], "9406": [v("2023", "S")], "900": [v("2005", "H")],
             "209015": [v("2001", "S")]}
    got = V.former_movers(reg, e2p, {"9406": {}}, {"9406": ["515"]}, votes)
    assert got == {"9404": ["568"]}, f"former_movers joined {got}"
    # A move within one year: the later day keeps the page, read as a day.
    same = dict(votes, **{"568": [v("2018", "H", "9/13")], "9404": [v("2018", "S", "10/10")]})
    assert V.former_movers(reg, e2p, {}, {}, same).get("9404") == ["568"], \
        "a move within a year kept the earlier page: dates compared as text"
    # The page kept says the years of every chamber (former_roster's served).
    fr = V.former_roster({}, votes, {"9404": ["568"]}, {}, "2025-2026")
    assert fr["9404"]["served"]["first"] == "3/1/2009" and "2009-2010" in fr["9404"]["served"]["terms"], \
        f"the page kept gives only its own chamber's years: {fr['9404']['served']}"
    assert V.former_movers(None, {}, {}, {}, votes) == {}, "no register still joined someone"
    # The pairs the owner confirmed (same_person): joined as the register's
    # are; one whose id a register join holds already is left as it is.
    conf = dict(votes, **{"374827": [v("2001", "H")], "36": [v("2012", "S")]})
    got = V.former_movers(reg, e2p, {"9406": {}}, {"9406": ["515"]}, conf,
                          confirmed=[["374827", "36"], ["568", "36"]])
    assert got == {"9404": ["568"], "36": ["374827"]}, f"the confirmed pairs joined {got}"
    root = Path(tempfile.mkdtemp(prefix="gr-moved-"))
    try:
        (root / "mc.json").write_text(json.dumps({"members": {}, "same_person": [
            {"house": "374827", "senate": "36", "confirmed": "2026-11-02, owner"},
            {"house": "862", "senate": "44", "confirmed": "no, two people"},
            {"house": "1", "senate": "2", "confirmed": ""}]}), encoding="utf-8")
        assert V.same_person(root / "mc.json") == [["374827", "36"]], V.same_person(root / "mc.json")
        assert V.same_person(root / "nowhere.json") == []
    finally:
        shutil.rmtree(root, ignore_errors=True)
    src = _source(_paths.locate("build_site_v2.py"))
    assert "confirmed=same_person()" in src, "build_site_v2 no longer takes the pairs the owner confirmed"
    root = Path(tempfile.mkdtemp(prefix="gr-moved-"))
    try:
        (root / "former.json").write_text(json.dumps([
            {"id": "9404", "slug": "shannon-chandley-sd-11",
             "moved_from": ["/legislator/shannon-chandley-hills-22"]},
            {"id": "27", "slug": "someone-sd-1"}]), encoding="utf-8")
        lines = BP.moved_members(root)
        old, new = "/legislator/shannon-chandley-hills-22", "/legislator/shannon-chandley-sd-11"
        assert lines == "".join(sorted([f"{old} {new} 301\n", f"{old}.html {new} 301\n",
                                        f"{old}/ {new} 301\n"]
                                       + [f"{old}/{s} {new}/{s} 301\n" for s in BP.MEMBER_TAB_SLUGS])), \
            lines
        assert BP.moved_members(root / "nowhere") == "", "no former.json still wrote a rule"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    src = _source(_paths.locate("build_site_v2.py"))
    assert "former_movers(register, e2p or {}" in src, "build_site_v2 no longer joins the movers who left"
    src = _source(_paths.locate("build_pages.py"))
    assert "want = redirects_file(out)" in src, (
        "build_pages no longer writes their 301s ahead of the tab rules, where the first match is served")
    return "ok", ("a mover who left is joined to the later page, by the term and then the day of the "
                  "last vote, with every chamber's years; a sitting one and a one-number one are not; their 301s "
                  "ahead of the tab rules, tabs included")


@check("build", "each bill request has a page of its own, noindex, until its bill is introduced or filing "
                "is complete, and from then its address forwards; never a page and a 301 at once")
def _request_pages():
    """Alice, 8 November 2026: a page for each request of the session the
    site lists, to share; noindex, out of the sitemap; once a request is a
    bill its address forwards to the bill's page, and once filing is
    complete the rest forward to their prime sponsor's; a withdrawn one
    keeps its page. And New Hampshire's specifics stay in the source's
    reader (build_lsrs), not in the page writer."""
    import tempfile
    import build_lsrs as L
    import build_pages as BPG
    import build_request_pages as RP
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "relative to tides.",
             "sponsor": "Jodi Nelson", "withdrawn": False},
            {"lsr": "2027-0002", "session": 2027, "body": "SB", "title": "relative to dunes.",
             "sponsor": "Pat Moore", "withdrawn": True},
            {"lsr": "2027-0003", "session": 2027, "body": "HB", "title": "relative to roads.",
             "sponsor": "Jodi Nelson", "withdrawn": False}]
    # The row's label carries no seat, as every real sitting row's does (the
    # roster's "Rep. Ellen Read (D)"); the page draws the seat from the roster.
    who = {"jodinelson": ("Rep. Jodi Nelson (R)", "jodi-nelson-rock-13")}
    # Filed as HB 45 and introduced (17 November 2026: a request filed and not
    # yet introduced keeps its page, _request_stays_until_introduced).
    rows, _ = L.rows_from(lsrs, who, {"2027-0003": "HB 45"}, 2027,
                          introduced_on={"2027-0003": "2027-01-06"})
    by = {r["n"]: r for r in rows}
    assert by["LSR 2027-0001"]["address"] == "request/2027-0001" \
        and "moved_to" not in by["LSR 2027-0001"], by["LSR 2027-0001"]
    assert by["LSR 2027-0003"]["moved_to"] == "bill/2027/hb45", (
        f"a request introduced as HB 45 moves to {by['LSR 2027-0003'].get('moved_to')}")
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "idx").mkdir()
        (site / "request").mkdir()
        # A page an earlier night wrote for the request now a bill.
        (site / "request" / "2027-0003.html").write_text("old", encoding="utf-8")
        (site / "bills.html").write_text(_source("src/pages/bills.html"),
                                         encoding="utf-8")
        (site / "legislators.json").write_text(json.dumps([
            {"slug": "jodi-nelson-rock-13", "party": "R",
             "display_full": "Rep. Jodi Nelson (R - Rock 13)"}]), encoding="utf-8")
        req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027}
        (site / "meta.json").write_text(json.dumps({"requests": req}), encoding="utf-8")
        (site / "idx" / "2027-requests.json").write_text(json.dumps(rows), encoding="utf-8")
        n, gone, moved = RP.write(site, "https://x")
        pages = sorted(p.name for p in (site / "request").glob("*.html"))
        assert pages == ["2027-0001.html", "2027-0002.html"] and gone == 1 and moved == 1, (
            f"request pages {pages}, {gone} taken away: one for each still a request, the withdrawn "
            "one kept, and the one now a bill taken away")
        page = (site / "request" / "2027-0001.html").read_text(encoding="utf-8")
        assert '<meta name="robots" content="noindex,follow">' in page \
            and "Requests, not bills yet." in page \
            and "numbered 2027 bill" in page and 'href="legislator/jodi-nelson-rock-13"' in page, (
            "a request's page is not noindex, explained, or its sponsor's chip linked")
        sd = re.search(r"<dt>Prime Sponsor</dt><dd>(.*?)</dd>", page, re.S)
        assert sd and '<span class="mtag">(R - Rock 13)</span>' in sd.group(1), (
            f"a sitting sponsor's page does not draw the roster's seat: {sd and sd.group(1)!r}")
        # THE BILL PAGE'S FRAME (Alice, 11 November 2026: "so that information
        # fills in more naturally rather than reformatting the whole layout"):
        # the record head with the trail Bills > the requests > the number, the
        # number and the status chip, the field grid, the action column with
        # Cite, Share and Report and no Testify or Print, the rail starting at
        # Requested and then every stop a bill passes, the Summary tab alone;
        # Follow's key and the report's record named for the scripts.
        frame = ('<header class="rhead rh-bill">', '<nav class="rtrail"', '>2027 Bill Requests</a>',
                 '<li aria-current="page">LSR 2027-0001</li>', 'chip chip-m cstat',
                 'Requested</span>', '<dl class="rfacts">', "<dt>Prime Sponsor</dt>",
                 "<dt>Kind</dt>", '<div class="racts"><div class="pageacts" id="pageacts"><details class="pcite"', "data-share",
                 '<i>Requested</i>', "<i>Filed</i>", "<i>Introduced</i>", 'class="pane sspane"',
                 'window.GR_FOLLOW="lsr:2027-0001";', 'window.GR_REPORT="request:2027-0001";',
                 'window.GR_REQUEST="2027-0001";')
        gone_ = [x for x in frame if x not in page]
        assert not gone_, f"a request's page lacks the bill page's frame: {gone_}"
        # A REQUEST'S RAIL IS THREE STOPS (Alice, 12 November 2026: a bill's six
        # ran into one another on a phone): Requested, Filed, Introduced, in
        # that order and nothing a bill passes after; the label text fits a
        # third of the narrowest phone's rail in the wider face
        # (_RAIL_FACE); withdrawn is a cross; Filed is reached only where the
        # row says the text is public.
        def stops_of(html):
            rail = re.search(r'<span class="rail dated".*?</span></span>(?=\s*<|$)', html, re.S)
            assert rail, "a request's page has no rail"
            return re.findall(r'<span class="stop s-(\w+)"><b>(.*?)</b><i>(.*?)</i>', rail.group(0), re.S)
        wd = (site / "request" / "2027-0002.html").read_text(encoding="utf-8")
        got = stops_of(page)
        assert [g[2] for g in got] == ["Requested", "Filed", "Introduced"], (
            f"a request's rail draws {[g[2] for g in got]}, not Requested, Filed, Introduced")
        assert [g[0] for g in got] == ["p", "o", "o"], f"a request's rail is reached as {[g[0] for g in got]}"
        assert [g[0] for g in stops_of(wd)] == ["p", "x", "o"] and "\u2715" in stops_of(wd)[1][1], (
            "a withdrawn request's rail does not show Requested reached and the cross on Filed")
        # WHAT IT SAYS TO A READER WHO HEARS IT OR HOVERS (15 November 2026): a stop a pending request
        # has not reached is "not yet", never the bill rail's "never reached", and a bare "Introduced"
        # is a bill's, always reached; a withdrawn request's Introduced was never reached.
        assert 'aria-label="Requested: made; Filed: not yet; Introduced: not yet"' in page \
            and 'aria-label="Requested: made; Filed: withdrawn; Introduced: never reached"' in wd, (
            "a request's rail says a pending stop is never reached, or a bare Introduced: "
            + str(re.findall(r'aria-label="(Requested[^"]*)"', page + wd)))
        # The stops are the row's (build_lsrs.rail_stops, written as `rail`),
        # which the page and the card both draw; a filed day is shown on Filed,
        # and Requested carries none (no source gives the day a request is made).
        filed_html = RP.rail_of({"rail": L.rail_stops({**by["LSR 2027-0001"], "filed": "2026-12-01"})})
        assert [g[0] for g in stops_of(filed_html)] == ["p", "p", "o"], "a filed request's rail does not reach Filed"
        cells = filed_html.split('<span class="stop ')[1:]
        assert by["LSR 2027-0001"]["rail"] == L.rail_stops(by["LSR 2027-0001"]) and len(cells) == 3 \
            and "<small>" not in cells[0] and "<small>" in cells[1], (
            "a request's row does not carry its own stops, or Requested shows a day, or Filed hides its day")
        slot = 296 / 3  # the rail of a 320px phone, three stops
        wide = max(sum(_RAIL_FACE.get(c, 1000) for c in w) * 14 / 1000 for w in ("Requested", "Filed", "Introduced"))
        assert wide + 2 * 4 <= slot, (
            f"a request's widest stop name is {wide:.0f}px in a {slot:.0f}px slot on a 320px phone")
        for no in ("Testify", "data-print", 'id="tab_LSR20270001_1"', "Committee</dt>"):
            assert no not in page, f"a request's page carries {no!r}, which a request has not"
        # THE SUMMARY TAB A BILL'S PAGE HAS (the owner, 16 November 2026: "LSR
        # pages should at least show the summary tab on the full page"), where
        # until then there was no strip; and since 17 November 2026 the Bill
        # Text tab beside it on every request (_request_bill_text_tab).
        assert re.findall(r'<button[^>]*role="tab"[^>]*>([^<]*)<', page) == ["Summary", "Bill Text"], (
            "a request's page with no co-sponsor and no History does not draw Summary and Bill Text, "
            "as a bill's page has them")
        wd = (site / "request" / "2027-0002.html").read_text(encoding="utf-8")
        assert ">Withdrawn</span>" in wd and "Status:" not in wd \
            and "window.GR_FOLLOW" not in wd, (
            "a withdrawn request's page does not say so, or offers Follow")
        # Its route, by kind (build_lsrs.route).
        assert L.route("HR") == ["House", "Adopted"] and L.route("SCR") == ["Senate", "House"] \
            and L.route("CACR") == ["Voters"] and L.route("SB")[-2:] == ["Governor", "Law"], (
            "build_lsrs.route's stops are not a bill's route")
        red = BPG.moved_requests(site)
        assert "/request/2027-0003 /bill/2027/hb45 301\n" in red and "2027-0001" not in red, (
            f"the 301s for the requests read {red!r}")
        # ONE RULE A REQUEST: Cloudflare's 2,000 static rules would not hold
        # three spellings for a session's thousand-odd requests (the review
        # of 8 November 2026).
        assert red.count("\n") == 1, f"a moved request takes {red.count(chr(10))} rules: {red!r}"
        # Every address is a page or a 301, never both.
        both = [p for p in pages if f"/request/{p[:-5]} " in red]
        assert not both, f"a page and a 301 at one address: {both}"
        # A RETURNING FORMER MEMBER HOLDS NO SEAT (13 November 2026): a request
        # whose sponsor's slug is in former.json only is drawn as the row's own
        # "Ben Baroody (D)", linked, never as former.json's "Rep. ... (D - Hills
        # 39)", the seat others hold now; so is a co-sponsor. A sitting member
        # keeps the seat.
        (site / "former.json").write_text(json.dumps([
            {"slug": "benjamin-baroody-hills-39", "party": "D",
             "display_full": "Rep. Benjamin Baroody (D - Hills 39)"}]), encoding="utf-8")
        fr = {**by["LSR 2027-0001"], "n": "LSR 2027-0004", "id": "LSR20270004",
              "address": "request/2027-0004", "sponsor_slug": "benjamin-baroody-hills-39",
              "sponsor_label": "Ben Baroody (D)", "sponsor_party": "D",
              "cosponsors": [{"label": "Ben Baroody (D)", "slug": "benjamin-baroody-hills-39"},
                             {"label": "Rep. Jodi Nelson (R)", "slug": "jodi-nelson-rock-13"}]}
        (site / "idx" / "2027-requests.json").write_text(json.dumps(rows + [fr]), encoding="utf-8")
        RP.write(site, "https://x")
        fp = (site / "request" / "2027-0004.html").read_text(encoding="utf-8")
        dd = re.search(r"<dt>Prime Sponsor</dt><dd>(.*?)</dd>", fp, re.S)
        assert dd and 'Ben Baroody <span class="mtag">(D)</span>' in dd.group(1) \
            and 'href="legislator/benjamin-baroody-hills-39"' in dd.group(1) \
            and "Hills 39" not in dd.group(1) and "Rep." not in dd.group(1) \
            and "mchip p-D" in dd.group(1), (
            f"a returning former member's request page draws the sponsor as {dd and dd.group(1)!r}, "
            "not as the row's own 'Ben Baroody (D)', linked, with no old seat")
        # EVERY PLACE A REQUEST'S PAGE DRAWS A PERSON: the head's Prime
        # Sponsor, and the Summary's Sponsors, as a bill's (24 November 2026:
        # until the co-sponsors came, the head's Co-Sponsors and a Sponsors
        # tab) -- three chips of the former member, each linked, none with the
        # old seat, and the sitting co-sponsor's with hers.
        sec = re.search(r'<section class="w4" id="sponsors">(.*?)</section>', fp, re.S)
        assert sec, "a request with co-sponsors has no Sponsors at the top of its Summary"
        grp = re.findall(r'<div class="chosen">(.*?)</div>', sec.group(1), re.S)
        assert len(grp) == 1, f"the Sponsors draw {len(grp)} groups of people, where no chamber is on file"
        link = 'href="legislator/benjamin-baroody-hills-39"'
        assert fp.count("Hills 39") == 0 \
            and grp[0].count('Ben Baroody <span class="mtag">(D)</span>') == 2 and grp[0].count(link) == 2 \
            and "Rep. Ben" not in fp and "Rep. Benjamin" not in fp \
            and 'Rep. Jodi Nelson <span class="mtag">(R - Rock 13)</span>' in grp[0] \
            and fp.count(link) == 3 \
            and fp.count('Rep. Jodi Nelson <span class="mtag">(R - Rock 13)</span>') == 1, (
            "a former member on a request's page is drawn with the old seat or unlinked in the head or the "
            f"Sponsors, or a sitting co-sponsor loses hers (links to the former member: {fp.count(link)}, not 3)")
    # Filing complete: the rest forward to their sponsor; a withdrawn one stays.
    old = dict(L.FILING_COMPLETE)
    try:
        L.FILING_COMPLETE[2027] = "2026-11-20"
        rs, _ = L.rows_from(lsrs, who, {}, 2027)
        assert L.retire(rs, 2027, "2026-11-19") == 0, "requests retired before filing is complete"
        assert L.retire(rs, 2027, "2026-11-20") == 2 \
            and rs[0]["moved_to"] == "legislator/jodi-nelson-rock-13" and "moved_to" not in rs[1], (
            f"once filing is complete the requests move to {[r.get('moved_to') for r in rs]}")
    finally:
        L.FILING_COMPLETE.clear()
        L.FILING_COMPLETE.update(old)
    # The links, and New Hampshire kept out of the page writer.
    assert 'const to=b.moved_to||b.address||"request/"' in _source("src/pages/find.js") \
        and '<a href="${esc(b.moved_to||b.address)}">${esc(b.n)}</a>' in _source("src/pages/app.js"), (
        "the header search's request row or the request card does not link the request's page")
    src = _source("src/pages/build_request_pages.py")
    assert not re.search(r"LSR|gc\.nh\.gov|\\d\{4\}-\\d", src), (
        "build_request_pages knows how a state numbers its requests or where they come from")
    return "ok", ("pages for the requests still requests, the withdrawn kept, the one now a bill "
                  "taken away and forwarded; filing complete forwards the rest to their sponsor; "
                  "no address is both; a sitting member keeps today's seat, and a returning "
                  "former member is drawn from the row, linked, with no old seat, as sponsor "
                  "and co-sponsor")


@check("build", "a request page's tabs switch: its pane ids are its own and unique on the page, each tab's "
       "aria-controls names its own pane, Summary and Bill Text at least on the page and the card, and "
       "the card and the page do not say twice what the chip and the byline say",
       needs=("build_lsrs",))
def _request_tabs_switch(build_lsrs):
    """The review of 14 November 2026: on /request/2027-0001 History was
    marked selected and the Summary stayed on screen above it. The pane was
    id="summary" and bills.html already carries <p class="count"
    id="summary">; app.js's ssPaneOf finds a pane by getElementById, found the
    <p>, and never took data-on off the pane. The panes are a bill's,
    pane_<id>_<key> (0 Summary, 6 Bill Text, 7 History) since 16 November
    2026, and no Sponsors tab since 24 November 2026, as a bill has none: the
    co-sponsors open the Summary. And the owner's "just let the pages speak for themselves":
    no Status, Kind, Prime Sponsor or Topic said again in the Summary under the
    chip and the byline. Every request has a Bill Text tab beside its Summary
    since 17 November 2026 (_request_bill_text_tab), so the page and the card
    always draw a strip; before then a lone Summary drew its tab on the page
    and no strip on the card."""
    import collections
    import tempfile
    import build_request_pages as RP
    L = build_lsrs
    earlier = {L.title_key("relative to tides"): [
        {"id": "HB7", "n": "HB 7", "year": 2024, "term": "2023-2024", "word": "Died", "cls": "s-done"}]}
    who = {"annlee": ("Rep. Ann Lee (D - Rock 1)", "ann-lee-rock-1"),
           "bobroe": ("Bob Roe (R)", "bob-roe-elect", "H")}
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "Relative to Tides.",
             "sponsor": "Ann Lee", "cosponsors": ["Bob Roe"], "withdrawn": False},
            {"lsr": "2027-0002", "session": 2027, "body": "HB", "title": "Relative to the dunes.",
             "sponsor": "Ann Lee", "withdrawn": False},
            {"lsr": "2027-0003", "session": 2027, "body": "HB", "title": "relative to tides",
             "sponsor": "Ann Lee", "withdrawn": False}]
    rows, _ = L.rows_from(lsrs, who, {}, 2027, None, earlier)
    by = {r["n"]: r for r in rows}
    assert by["LSR 2027-0001"].get("history") and by["LSR 2027-0001"].get("cosponsors") \
        and not by["LSR 2027-0002"].get("history") and not by["LSR 2027-0002"].get("cosponsors"), (
        "the fixture lost the request with three tabs or the one with one")
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "idx").mkdir()
        (site / "bills.html").write_text(_source("src/pages/bills.html"),
                                         encoding="utf-8")
        (site / "legislators.json").write_text(json.dumps([
            {"slug": "ann-lee-rock-1", "party": "D", "display_full": "Rep. Ann Lee (D - Rock 1)"}]),
            encoding="utf-8")
        (site / "elect_pages.json").write_text(json.dumps({"pages": [
            {"slug": "bob-roe-elect", "name": "Bob Roe", "party": "R"}]}), encoding="utf-8")
        req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "abbr": L.ABBR}
        (site / "meta.json").write_text(json.dumps({"requests": req}), encoding="utf-8")
        (site / "idx" / "2027-requests.json").write_text(json.dumps(rows), encoding="utf-8")
        RP.write(site, "https://x")
        many = (site / "request" / "2027-0001.html").read_text(encoding="utf-8")
        one = (site / "request" / "2027-0002.html").read_text(encoding="utf-8")
    for label, html in (("three tabs", many), ("one", one)):
        ids = re.findall(r'\sid="([^"]+)"', html)
        dup = sorted(i for i, c in collections.Counter(ids).items() if c > 1)
        assert not dup, f"a request page ({label}) carries an id twice: {dup}"
    tabs = re.findall(r'<button[^>]*role="tab"[^>]*aria-controls="([^"]+)"', many)
    assert tabs == ["pane_LSR20270001_0", "pane_LSR20270001_6", "pane_LSR20270001_7"], (
        f"a request page with co-sponsors and a History has tabs controlling {tabs}")
    for t in tabs:
        own = re.findall(r'<div class="pane sspane"[^>]*\sid="%s"' % re.escape(t), many)
        assert len(own) == 1 and many.count('id="%s"' % t) == 1, (
            f"the tab controlling {t!r} does not point at its own pane, or at one only: "
            f"{len(own)} panes, {many.count('id=%s' % chr(34) + t + chr(34))} elements with the id")
    assert many.count(" data-on") == 1 and re.search(
        r'<div class="pane sspane"[^>]*id="pane_LSR20270001_0"[^>]*data-on', many), (
        "a request page opens on more than its Summary, or not on it")
    assert re.findall(r'<button[^>]*role="tab"[^>]*aria-controls="([^"]+)"', one) == [
        "pane_LSR20270002_0", "pane_LSR20270002_6"] \
        and one.count('role="tablist"') == 1 and one.count(" data-on") == 1 \
        and re.search(r'<div class="pane sspane"[^>]*id="pane_LSR20270002_0"[^>]*data-on', one), (
        "a request page with no co-sponsor and no History does not draw Summary and Bill Text, or its Summary "
        "is not chosen")
    for html in (many, one):
        assert "Status:" not in html and "The Request" not in html, (
            "a request page says its status again under the chip")
    # THE CARD, in node.
    js = ("(() => { scope.setMeta({requests: {term: '2027-requests', year: 2027, abbr: " + json.dumps(L.ABBR)
          + "}}); const r = " + json.dumps(by["LSR 2027-0001"]) + "; const one = "
          + json.dumps(by["LSR 2027-0002"]) + "; scope.openCards.add(r.id); scope.openCards.add(one.id); "
          "return {many: scope.lsrCardHtml(r), one: scope.lsrCardHtml(one)}; })()")
    got = _app_js(js, names=("lsrCardHtml", "openCards", "openTab", "setMeta: x => (META = x)"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    for label, html in (("three tabs", got["many"]), ("one", got["one"])):
        ids = re.findall(r'\sid="([^"]+)"', html)
        dup = sorted(i for i, c in collections.Counter(ids).items() if c > 1)
        assert not dup, f"a request's card ({label}) carries an id twice: {dup}"
        for bad in ("<b>Status:</b>", "<b>Kind:</b>", "<b>Prime Sponsor:</b>", "<b>Topic (from the title):</b>"):
            assert bad not in html, f"a request's card says {bad!r} again under its chip and byline"
    for c in re.findall(r'aria-controls="([^"]+)"', got["many"]):
        assert got["many"].count('id="%s"' % c) == 1, f"a card tab controls {c!r}, which is not one pane"
    for c in re.findall(r'aria-controls="([^"]+)"', got["one"]):
        assert got["one"].count('id="%s"' % c) == 1, f"a card tab controls {c!r}, which is not one pane"
    assert got["one"].count('role="tablist"') == 1 and got["one"].count('role="tab"') == 2, (
        "a request's card with no co-sponsor and no History does not draw Summary and Bill Text")
    assert got["many"].count('role="tab"') == 3, "a request's card with co-sponsors and a History lost a tab"
    return "ok", ("a request page's three panes have their own ids, unique on the page, each tab pointing at "
                  "its pane, on the page and the card; Summary and Bill Text at least on both; the Summary "
                  "does not repeat the chip or the byline")


@check("build", "a request's card, opened, says what a request is as its own page's Summary does: About "
                "Requests in the page's words, after the co-sponsors and the bill it was filed as and "
                "before the way on to the page", needs=("build_lsrs",))
def _request_card_summary_explains(build_lsrs):
    """The owner, 17 November 2026: "Can you make it so that opening the LSR
    pages shows the same summary of what LSRs are that the full page does
    since right now it just shows the link to the page and almost doesn't
    look like the card has expanded?" Held on build_lsrs' rows for a request
    with a co-sponsor, a withdrawn one and one filed as a bill: the page
    build_request_pages writes for each carries About Requests in its
    Summary (explain, with what LSR stands for), and the card app.js draws
    for the same row, opened, carries that section in its Summary's pane
    byte for byte but for the page's id, once, after the co-sponsor and the
    Filed As line and before the link to the page (app.js lsrAbout)."""
    import tempfile
    import components as C
    import build_request_pages as RP
    L = build_lsrs
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "relative to dunes.", "sponsor": "Ann Lee",
             "cosponsors": ["Bob Roe"]},
            {"lsr": "2027-0002", "session": 2027, "body": "SB", "title": "relative to coves.", "sponsor": "Ann Lee",
             "withdrawn": True},
            {"lsr": "2027-0003", "session": 2027, "body": "HB", "title": "relative to capes.", "sponsor": "Ann Lee"}]
    rows, _ = L.rows_from(lsrs, {}, {"2027-0003": "HB 5"}, 2027, None, {})
    by = {r["n"][4:]: r for r in rows}
    assert [by[n]["status"] for n in ("2027-0001", "2027-0002", "2027-0003")] == ["Requested", "Withdrawn", "Filed"] \
        and by["2027-0001"].get("cosponsors") and by["2027-0003"].get("introduced") == "HB 5", (
        "the fixture's three requests are not what they were")
    req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "abbr": L.ABBR}
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "idx").mkdir()
        (site / "bills.html").write_text(_source("src/pages/bills.html"), encoding="utf-8")
        (site / "meta.json").write_text(json.dumps({"requests": req}), encoding="utf-8")
        (site / "idx" / "2027-requests.json").write_text(json.dumps(rows), encoding="utf-8")
        RP.write(site, "https://x")
        pages = {n: (site / "request" / f"{n}.html").read_text(encoding="utf-8") for n in by}
    words = f'<p class="lsrnote">{RP.explain(2027, L.ABBR)}</p>'
    assert "LSR stands for Legislative Service Request." in words, words
    about, on_page = C.section("About Requests", words), C.section("About Requests", words, "about")
    for n, page in pages.items():
        summary = page[page.index(f'id="pane_{by[n]["id"]}_0"'):]
        nxt = summary.find('<div class="pane sspane"')
        assert on_page in (summary[:nxt] if nxt >= 0 else summary), (
            f"/request/{n}'s Summary does not carry About Requests in explain's words")
    js = ("(() => { scope.setMeta({requests: " + json.dumps(req) + "}); const rows = "
          + json.dumps([by[n] for n in sorted(by)]) + "; rows.forEach(r => scope.openCards.add(r.id));"
          " return rows.map(r => scope.lsrCardHtml(r, '')); })()")
    got = _app_js(js, names=("lsrCardHtml", "openCards", "setMeta: x => (META = x)"))
    if got is None:
        return "skip", "the pages carry About Requests; node, app.js or the stub is not here for the card"
    for n, card in zip(sorted(by), got):
        start = re.search(r'<div class="pane"[^>]*data-t="0"[^>]*>', card)
        assert start and 'aria-expanded="true"' in card, f"{n}'s card did not open onto a Summary: {card[:400]!r}"
        pane = card[start.end():]
        pane = pane[:pane.find('<div class="pane"')] if '<div class="pane"' in pane else pane
        assert card.count(about) == 1 and about in pane, (
            f"{n}'s opened card does not say what a request is as its page does, in its Summary: {pane[:900]!r}")
        link = pane.find("Open the request’s own page")
        assert 0 <= pane.find(about) < link, f"{n}'s card puts About Requests after the link to its page"
        # The co-sponsors as a bill's Summary opens with its sponsors (24 November 2026).
        for said in ('<h2 class="w4h">Sponsors</h2>', "<b>Filed As:</b>"):
            assert said not in pane or pane.find(said) < pane.find(about), (
                f"{n}'s card puts {said!r} under About Requests")
    assert '<h2 class="w4h">Sponsors</h2>' in got[0] and "<b>Filed As:</b>" in got[2], (
        "the card lost its co-sponsor or the bill it was filed as")
    return "ok", ("three requests' pages (requested with a co-sponsor, withdrawn, filed as HB 5) carry About "
                  "Requests in their Summary, and each one's opened card the same section in its Summary, "
                  "byte for byte, after the sponsors and Filed As and before the link to the page")


@check("frontend", "a bill's page and card and a request's card draw their tabs with the record's one "
                   "strip, components.record_tabs and recordTabs, byte for byte as Python draws it")
def _one_record_tab_strip():
    """16 November 2026: a request's page is to show its Summary tab as a
    bill's page does, drawn by the same component and not a copy. The strip
    a bill's page and card hang from the head (app.js renderDetail) and a
    request's card's (lsrBody) were each written out by hand; they are
    components.recordTabs now, which components.record_tabs draws the same
    in Python (held to it by _components_agree). Held: neither function
    writes a tab of its own, and drawn in node on a bill with a roll call, a
    bill with a text and an open request card with co-sponsors and a
    History, each strip is record_tabs' answer in Python for those tabs,
    byte for byte -- Summary chosen and first, Bill Text second where there
    is a text, the badge only where there is a count."""
    import components as C
    src = _source("src/pages/app.js")
    for fn in ("renderDetail", "lsrBody"):
        m = re.search(r"\nfunction " + fn + r"\(.*?\n\}\n", src, re.S)
        assert m and "recordTabs(" in m.group(0) and 'role="tab"' not in m.group(0), (
            f"app.js's {fn} writes a tab strip of its own, not components.js's recordTabs")
    rc = {"question": "Ought to Pass", "date": "2026-03-05", "body": "H", "vote_kind": "VV", "passed": True}
    row = {"id": "HB1", "n": "HB 1", "term": "2025-2026", "year": 2026}
    req = {"id": "LSR20279999", "n": "LSR 2027-9999", "year": 2027, "title": "relative to tides.",
           "sponsor": "Ann Lee", "sponsor_label": "Ann Lee (D)", "sponsor_slug": "", "body": "HB",
           "body_label": "House bill request", "status": "Requested", "lsr": True,
           "term": "2027-requests", "address": "request/2027-9999",
           "cosponsors": [{"label": "Bob Roe (R)", "slug": ""}, {"label": "Cy Doe", "slug": ""}],
           "history": [{"id": "HB7", "n": "HB 7", "year": 2024, "word": "Died", "cls": "s-done"}],
           "rail": [{"stop": "Requested", "mark": "p", "say": "made"}]}
    js = ("(() => { scope.setMeta({requests: {term: '2027-requests', year: 2027}}); const r = "
          + json.dumps(req) + "; scope.openCards.add(r.id); scope.openTab[r.id] = '7'; return {"
          "bill: scope.renderDetail(" + json.dumps(row) + ", {rollcalls: [" + json.dumps(rc) + "]}), "
          "texted: scope.renderDetail(" + json.dumps(row) + ", {billtext: {body: 'AN ACT relative to tides.'}}), "
          "card: scope.lsrCardHtml(r)}; })()")
    got = _app_js(js, names=("renderDetail", "lsrCardHtml", "openCards", "openTab",
                             "setMeta: x => (META = x)"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    # Videos, and no Sponsors tab (the owner, 19 November 2026): the
    # sponsors are the Summary's top (_bill_tabs_one_line).
    rest = [["2", "Videos", 0], ["3", "Reports", 0], ["5", "Documents", 0],
            ["7", "History", 0]]
    want = {"bill": C.record_tabs("HB1", [["0", "Summary", 0], ["1", "Votes", 1]] + rest, "0"),
            "texted": C.record_tabs("HB1", [["0", "Summary", 0], ["6", "Bill Text", 0], ["1", "Votes", 0]]
                                    + rest, "0"),
            # A request's card has no Sponsors tab either (24 November 2026): its co-sponsors
            # open its Summary (_request_sponsors_as_a_bills).
            "card": C.record_tabs("LSR20279999", [["0", "Summary", 0], ["6", "Bill Text", "0"],
                                                  ["7", "History", 1]], "7")}
    for k, w in want.items():
        assert w in got[k], f"the {k} strip is not record_tabs' answer: {got[k][:500]!r}, not {w!r}"
    assert got["bill"].startswith(want["bill"]) and got["texted"].startswith(want["texted"]), (
        "a bill's tabs no longer open its detail")
    return "ok", ("a bill's page and card (with and without a text) and a request's open card draw "
                  "components.record_tabs' strip, byte for byte, and app.js writes none of its own")


@check("frontend", "a bill's strip is Summary, Bill Text, Votes, Videos, Reports, Documents and History: "
                   "its sponsors open the Summary, prime first, as the Sponsors tab drew them, and "
                   "/sponsors and /hearings still open the bill")
def _bill_tabs_one_line():
    """The owner, 19 November 2026, on 2025's HB 57: the strip -- Summary,
    Bill Text, Votes, Hearings, Reports, Sponsors, Documents, History --
    wrapped History onto a second line. The Sponsors tab is gone and its
    chips are the Summary's first section, the prime sponsor first, then the
    co-sponsors, each chamber's names under an h3 where they are of both;
    the Hearings tab is Videos. Measured on the built pages with this branch's
    app.js: the strip took 795 to 804px at 1280 and takes 664 (its labels'
    widths, not this check's). A bill with no sponsors says so, unless it is of
    an earlier term, whose About This Record says it. An address made before
    -- /sponsors, /hearings -- still opens the bill: /hearings the Videos tab,
    /sponsors the Summary (syncCards opens the Summary for a tab the bill
    does not draw), and a tab chosen now writes /videos."""
    sp = [{"name": "Ann Lee", "chamber": "S", "party": "D", "display_full": "Sen. Ann Lee (D - SD1)",
           "slug": "ann-lee-sd-1", "prime": True, "sequence": 0},
          {"name": "Bob Roe", "chamber": "H", "party": "R", "display_full": "Rep. Bob Roe (R - Hills 2)",
           "slug": "bob-roe-hills-2", "sequence": 1},
          {"name": "Cy Doe", "chamber": "S", "party": "R", "display_full": "Sen. Cy Doe (R - SD3)",
           "slug": "cy-doe-sd-3", "sequence": 2}]
    row = {"id": "SB5", "n": "SB 5", "term": "2025-2026", "year": 2025}
    js = ("(() => { const b = " + json.dumps(row) + ";"
          " return {detail: scope.renderDetail(b, " + json.dumps({"sponsors": sp, "nver": 2,
                                                                   "billtext": {"body": "AN ACT"}}) + "),"
          " lone: scope.renderSummary(b, " + json.dumps({"sponsors": sp[:1]}) + "),"
          " none: scope.renderSummary(b, {}),"
          " old: scope.renderSummary(b, {archived: {docket: true}}),"
          " slugs: [scope.slugOf(scope.BILL_TABS, '2'), scope.BILL_TABS.sponsors,"
          " scope.BILL_TABS.hearings, scope.BILL_TABS.videos]}; })()")
    got = _app_js(js, names=("renderDetail", "renderSummary", "slugOf", "BILL_TABS"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    det = got["detail"]
    strip = det[:det.index("</div>")]
    tabs = re.findall(r'data-t="(\d)">([A-Z][A-Za-z ]*)', strip)
    assert tabs == [("0", "Summary"), ("6", "Bill Text"), ("1", "Votes"), ("2", "Videos"), ("3", "Reports"),
                    ("5", "Documents"), ("7", "History")], f"the bill's strip is {tabs}"
    assert 'data-t="4"' not in det and "Hearings" not in det, "a Sponsors pane or a Hearings word is still drawn"
    summ = det[det.index('id="pane_SB5_0"'):det.index('id="pane_SB5_6"')]
    first = re.search(r'<section class="w4"( id="[^"]*")?><h2 class="w4h">([^<]*)</h2>', summ)
    assert first and first.groups() == (' id="sponsors"', "Sponsors"), (
        f"the Summary does not open with its Sponsors: {first.groups() if first else summ[:200]}")
    sec = summ[:summ.index("</section>")]
    chips = re.findall(r'class="mchip p-(\w)" translate="no"><a href="legislator/([^"]+)"', sec)
    assert chips == [("D", "ann-lee-sd-1"), ("R", "cy-doe-sd-3"), ("R", "bob-roe-hills-2")], (
        f"the Summary's sponsors are not the prime, then the co-sponsors, the prime's chamber first: {chips}")
    # The count under the chips (the owner, 19 November 2026), not over them.
    assert re.search(r'</div>\s*<p class="spcount">3 Sponsors \u00b7 <span title="Democrat">1 D</span>', sec) \
        and sec.index("spcount") > sec.rindex('class="chosen"'), "the sponsors' count is not under their chips"
    assert '<i translate="yes">Prime</i>' in sec.split("cy-doe-sd-3")[0] and \
        re.findall(r'<h3 class="spch">(\w+)', sec) == ["Senators", "Representatives"], (
            "the prime is not labelled, or the chambers are not split under h3s")
    lone, none, old = got["lone"], got["none"], got["old"]
    assert 'id="sponsors"' in lone and "spch" not in lone and "ann-lee-sd-1" in lone, (
        "one chamber's sponsors are headed by their chamber, or missing")
    assert 'id="sponsors"' in none and "No sponsors on file." in none and 'id="sponsors"' not in old, (
        "a bill with no sponsors does not say so, or an earlier term's says it twice")
    assert got["slugs"] == ["videos", "4", "2", "2"], f"the tab addresses are {got['slugs']}"
    app = _source("src/pages/app.js")
    sync = re.search(r"\nfunction syncCards\(.*?\n\}\n", app, re.S)
    assert sync and re.search(r'if\(!c\.querySelector\(`\.pane\[data-t="\$\{t\}"\]`\)\)\{t="0";openTab\[id\]="0";\}',
                              sync.group(0)), "a tab the bill does not draw (/sponsors) no longer opens its Summary"
    return "ok", ("seven tabs, Videos and no Sponsors; the Summary opens with the sponsors' chips, the "
                  "prime labelled and first, Senators then Representatives under h3s, one chamber's "
                  "unheaded, none said, an earlier term's left to About This Record; /videos written, "
                  "/hearings and /sponsors kept")


@check("build", "a request's page has a bill page's Summary tab, drawn by the record's strip, its Summary "
                "About Requests alone and its Bill Text tab saying the text is not public yet while the "
                "request is drafted, that a withdrawn one was withdrawn, and that a filed one's is public; "
                "readable with no script",
       needs=("build_lsrs",))
def _request_page_summary(build_lsrs):
    """The owner, 16 November 2026: a request's full page ended after the
    rail and an About Requests box and "looks cut off": "LSR pages should at
    least show the summary tab on the full page and the summary should
    explain that the bill text is not yet available as it is still being
    drafted so that the format doesn't look cut off." Held on pages
    build_request_pages writes from build_lsrs' rows: every page's strip is
    components.record_tabs' for its tabs at its own address, byte for byte,
    the strip a bill's page draws (_one_record_tab_strip); a request still
    requested says its text "will be public when it is filed as a numbered
    2027 bill"; a withdrawn one says it was withdrawn before it was filed and
    nothing of drafting; one filed says neither. Since 17 November 2026 (the
    owner: "move the text about the bill text into a bill text tab ... and
    leave the summary as the about section") that is said in the Bill Text
    tab, and the Summary is About Requests and nothing else, its words
    explain's. With no script, app.css hides the strip and shows every pane, and
    each pane carries its own heading and no hidden; the pane sits under the
    strip's rule as a bill's does."""
    import tempfile
    import components as C
    import build_request_pages as RP
    L = build_lsrs
    earlier = {L.title_key("relative to tides"): [
        {"id": "HB7", "n": "HB 7", "year": 2024, "term": "2023-2024", "word": "Died", "cls": "s-done"}]}
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "relative to dunes.", "sponsor": "Ann Lee"},
            {"lsr": "2027-0002", "session": 2027, "body": "HB", "title": "relative to tides.", "sponsor": "Ann Lee"},
            {"lsr": "2027-0003", "session": 2027, "body": "SB", "title": "relative to coves.", "sponsor": "Ann Lee",
             "withdrawn": True},
            {"lsr": "2027-0004", "session": 2027, "body": "HB", "title": "relative to capes.", "sponsor": "Ann Lee",
             "filed": "2026-12-01"}]
    rows, _ = L.rows_from(lsrs, {}, {}, 2027, None, earlier)
    by = {r["n"][4:]: r for r in rows}
    assert [by[n]["status"] for n in ("2027-0001", "2027-0002", "2027-0003", "2027-0004")] == [
        "Requested", "Requested", "Withdrawn", "Filed"] and by["2027-0002"].get("history") \
        and not any(r.get("moved_to") for r in rows), "the fixture's four requests are not what they were"
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "idx").mkdir()
        (site / "bills.html").write_text(_source("src/pages/bills.html"), encoding="utf-8")
        req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "abbr": L.ABBR}
        (site / "meta.json").write_text(json.dumps({"requests": req}), encoding="utf-8")
        (site / "idx" / "2027-requests.json").write_text(json.dumps(rows), encoding="utf-8")
        RP.write(site, "https://x")
        pages = {n: (site / "request" / f"{n}.html").read_text(encoding="utf-8") for n in by}
    drafting = ("<b>Not public yet.</b> This request is still being drafted into a bill. Its text will be "
                "public when it is filed as a numbered 2027 bill.")
    gone = "<b>Withdrawn.</b> This request was withdrawn before it was filed as a bill, so it has no text."
    for n, page in pages.items():
        r = by[n]
        tabs = [["0", "Summary", 0], ["6", "Bill Text", "0"]] + (
            [["7", "History", len(r["history"])]] if r.get("history") else [])
        strip = C.record_tabs(r["id"], tabs, "0", f"/request/{n}")
        assert strip in page and page.count('role="tablist"') == 1, (
            f"/request/{n} does not draw the record's strip for {[t[1] for t in tabs]}: "
            + (re.search(r'<div class="tabs[^"]*" role="tablist".*?</div>', page) or [""])[0][:400])
        assert 'class="tabs sstabs"' in strip, "a request page's strip is not one a page built ahead hides with no script"
        panes = re.findall(r'<div class="pane sspane"[^>]*>', page)
        assert len(panes) == len(tabs) and not any(" hidden" in p for p in panes) \
            and page.count('<h2 class="ssph">') == len(tabs), (
            f"/request/{n}'s panes are not each on the page under a heading of its own: {panes}")
        own = {re.search(r'data-t="(\d)"', s).group(1): s for s in page.split('<div class="pane sspane"')[1:]}
        about = C.section("About Requests", f'<p class="lsrnote">{RP.explain(2027, L.ABBR)}</p>', "about")
        assert own["0"].endswith(f'<h2 class="ssph">Summary</h2>{about}</div>'), (
            f"/request/{n}'s Summary is not About Requests alone: {own['0'][:600]!r}")
        want = {"2027-0001": drafting, "2027-0002": drafting, "2027-0003": gone, "2027-0004": None}[n]
        if want:
            assert want in own["6"] and want not in own["0"], (
                f"/request/{n} ({r['status']}) does not say {want!r} in its Bill Text tab alone")
        for other in {drafting, gone} - {want}:
            assert other not in page, f"/request/{n} ({r['status']}) says {other!r}"
        assert "still being drafted" not in page or want == drafting, f"/request/{n} says it is being drafted"
    css = _source("src/pages/app.css")
    for rule in ("html:not(.js) .sstabs{display:none}", "html.js .sspane:not([data-on]){display:none}"):
        assert rule in css, f"app.css no longer has {rule!r}, which keeps a request's page readable with no script"
    under = re.search(r"\.card\.focus\.rec > \.cbody > \.tabs,\.rhead\.rh-bill ~ \.tabs\{([^}]*)\}", css)
    assert under and "margin-bottom:0" in under.group(1), (
        "a request page's pane does not sit under its strip's rule in the bill page's own rule")
    return "ok", ("four requests' pages: the record's strip, Summary and Bill Text alone or with History; the "
                  "Summary About Requests alone; drafted, withdrawn and filed each say what their row says of "
                  "the text in the Bill Text tab, and nothing else; every pane on the page under its heading "
                  "with no script, and under the rule with one")


@check("build", "every request has a Bill Text tab, second, on its page and its card: (0) and \"Not public "
                "yet\" while it is drafted, the withdrawn note when withdrawn, where it is when filed and not "
                "read, and the text with (1) once read; the card's words the page's",
       needs=("build_lsrs",))
def _request_bill_text_tab(build_lsrs):
    """The owner, 17 November 2026: "You can also move the text about the
    bill text into a bill text tab and just list it as 0 until the text is
    published and leave the summary as the about section: Bill Text / Not
    public yet. This request is still being drafted into a bill. Its text
    will be public when it is filed as a numbered 2027 bill." Held on four
    requests from build_lsrs' rows -- one requested, one withdrawn, one filed
    whose text the night has read and one filed whose text it has not -- on
    the page build_request_pages writes and the card app.js draws: the
    strip is components.record_tabs' with Bill Text second, keyed 6, its
    count the text "0", drawn "(0)", until the text is read and 1 once it
    is; the tab says the owner's sentence exactly for the one requested,
    the withdrawn note for the withdrawn one and that the text is public,
    with the PDF, for the one filed and not read -- the card's pane the
    page's byte for byte -- and the text in its block for the one read."""
    import tempfile
    import components as C
    import build_request_pages as RP
    L = build_lsrs
    pdf = "https://gc.nh.gov/x/2027-000%d.pdf"
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "relative to dunes.", "sponsor": "Ann Lee"},
            {"lsr": "2027-0002", "session": 2027, "body": "SB", "title": "relative to coves.", "sponsor": "Ann Lee",
             "withdrawn": True},
            {"lsr": "2027-0003", "session": 2027, "body": "HB", "title": "relative to capes.", "sponsor": "Ann Lee"},
            {"lsr": "2027-0004", "session": 2027, "body": "HB", "title": "relative to bays.", "sponsor": "Ann Lee"}]
    rows, _ = L.rows_from(lsrs, {}, {"2027-0003": "HB 5", "2027-0004": "HB 6"}, 2027, None, {})
    by = {r["n"][4:]: r for r in rows}
    # What the night adds once the list links a request's text, and once it has read it (build_lsrs).
    by["2027-0003"].update(text_pdf=pdf % 3, text_on_file=True)
    by["2027-0004"].update(text_pdf=pdf % 4)
    assert [by[n]["status"] for n in sorted(by)] == ["Requested", "Withdrawn", "Filed", "Filed"], (
        "the fixture's four requests are not what they were")
    saved = L.REQUEST_TEXTS
    req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "abbr": L.ABBR}
    try:
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            (site / "idx").mkdir()
            L.REQUEST_TEXTS = site / "lsr_text"
            L.REQUEST_TEXTS.mkdir()
            (L.REQUEST_TEXTS / "2027-0003.txt").write_text("  HB 5 - AS INTRODUCED\n\n  AN ACT relative to capes.\n",
                                                           encoding="utf-8")
            (site / "bills.html").write_text(_source("src/pages/bills.html"), encoding="utf-8")
            (site / "meta.json").write_text(json.dumps({"requests": req}), encoding="utf-8")
            (site / "idx" / "2027-requests.json").write_text(json.dumps(rows), encoding="utf-8")
            RP.write(site, "https://x")
            pages = {n: (site / "request" / f"{n}.html").read_text(encoding="utf-8") for n in by}
            bodies = {n: RP.text_pane(by[n], 2027) for n in by}
    finally:
        L.REQUEST_TEXTS = saved
    said = {"2027-0001": "Not public yet. This request is still being drafted into a bill. Its text will be public "
                         "when it is filed as a numbered 2027 bill.",
            "2027-0002": "Withdrawn. This request was withdrawn before it was filed as a bill, so it has no text.",
            "2027-0004": "Filed. Its text is public, and is added here once this site has read it. The PDF at the "
                         "General Court."}
    plain = lambda h: re.sub(r"<[^>]+>", "", h).strip()
    for n, page in pages.items():
        r = by[n]
        count = 1 if n == "2027-0003" else "0"
        strip = C.record_tabs(r["id"], [["0", "Summary", 0], ["6", "Bill Text", count]], "0", f"/request/{n}")
        assert strip in page, (f"/request/{n} does not draw Summary and Bill Text ({count}) as the record's strip: "
                               + (re.search(r'<div class="tabs[^"]*" role="tablist".*?</div>', page) or [""])[0][:500])
        assert f'Bill Text<span class="tn"><span class="tnp"> (</span>{count}<span class="tnp">)</span></span>' in strip, (
            f"the Bill Text tab of /request/{n} does not show ({count})")
        assert f'data-t="6"><h2 class="ssph">Bill Text</h2>{bodies[n]}</div>' in page, (
            f"/request/{n}'s Bill Text pane is not text_pane's")
        if n in said:
            assert plain(bodies[n]) == said[n] and "vtext" not in bodies[n], (
                f"/request/{n}'s Bill Text tab says {plain(bodies[n])!r}, not {said[n]!r}")
    assert '<pre class="vtext" translate="no">HB 5 - AS INTRODUCED\n\nAN ACT relative to capes.</pre>' in bodies["2027-0003"] \
        and "read by machine" in bodies["2027-0003"] and f'href="{pdf % 3}"' in bodies["2027-0003"] \
        and "Not public yet" not in pages["2027-0003"], "the request whose text is read does not show it"
    assert f'href="{pdf % 4}"' in bodies["2027-0004"], "the filed request's tab does not link its PDF"
    # THE CARD, in node: the same strip and, for the three with no text here, the page's pane.
    js = ("(() => { globalThis.fetch = () => new Promise(() => {}); scope.setMeta({requests: " + json.dumps(req)
          + "}); const rows = " + json.dumps([by[n] for n in sorted(by)]) + "; return rows.map(r => {"
          " scope.openCards.add(r.id); scope.openTab[r.id] = '6'; return {tabs: scope.lsrTabs(r),"
          " card: scope.lsrCardHtml(r, '')}; }); })()")
    got = _app_js(js, names=("lsrCardHtml", "lsrTabs", "openCards", "openTab", "setMeta: x => (META = x)"))
    if got is None:
        return "skip", "the pages hold; node, app.js or the stub is not here for the card"
    for n, x in zip(sorted(by), got):
        count = 1 if n == "2027-0003" else "0"
        assert x["tabs"][:2] == [["0", "Summary", 0], ["6", "Bill Text", count]], (
            f"{n}'s card's tabs are {x['tabs']}")
        assert C.record_tabs(by[n]["id"], x["tabs"], "6") in x["card"], f"{n}'s card does not draw its strip"
        summ = x["card"][x["card"].index(f'id="pane_{by[n]["id"]}_0"'):x["card"].index(f'id="pane_{by[n]["id"]}_6"')]
        assert not [w for w in ("Not public yet", "<b>Withdrawn.</b>", "<b>Filed.</b>", "vtext") if w in summ], (
            f"{n}'s card's Summary says something of the text")
        if n in said:
            assert f'data-t="6">{bodies[n]}</div>' in x["card"], (
                f"{n}'s card's Bill Text pane is not its page's: {x['card'][x['card'].find('data-t=' + chr(34) + '6' + chr(34) + '>'):][:500]!r}")
    assert "Loading the text" in got[2]["card"] and pdf % 3 in got[2]["card"], (
        "the card of the request whose text is read does not fetch it into its tab")
    return "ok", ("requested, withdrawn, filed and read, filed and not read: Bill Text second on the page and "
                  "the card, (0) until read and (1) after; the owner's sentence, the withdrawn note and the "
                  "filed note each exact, the card's pane the page's; the read text in its block")


@check("frontend", "a request's Bill Text tab asks for no versions file, which no build writes for a request; "
                   "a bill's still does")
def _request_text_tab_asks_no_versions():
    """17 November 2026: once every request had a Bill Text tab, keyed 6 as a
    bill's, a press on it in the bill search ran the bill's path for that
    tab (app.js's tab handler calls needVersions for tab 6) and asked
    /versions/2027/LSR20270001.json, which answered 404 for every request
    -- seen in the screenshots' server log, four 404s for each request whose
    card was turned to Bill Text. needVersions now asks nothing for a row
    that is a request (`lsr`). Held in node: needVersions on a request's row
    makes no request and leaves nothing in the cache; on a bill's row with
    no record yet it asks /versions/2026/HB1.json, as before."""
    js = ("(() => { const asked = []; globalThis.fetch = u => { asked.push(String(u));"
          " return new Promise(() => {}); };"
          " scope.needVersions({id: 'LSR20270001', n: 'LSR 2027-0001', year: 2027, term: '2027-requests', lsr: true});"
          " const lsr = asked.slice();"
          " scope.needVersions({id: 'HB1', n: 'HB 1', year: 2026, term: '2025-2026'});"
          " return {lsr, bill: asked.slice(lsr.length)}; })()")
    got = _app_js(js, names=("needVersions",))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    assert got["lsr"] == [], f"a request's Bill Text tab asks {got['lsr']}"
    assert len(got["bill"]) == 1 and got["bill"][0].endswith("versions/2026/HB1.json"), (
        f"a bill's Bill Text tab no longer asks its versions file: {got['bill']}")
    return "ok", "a request's row asks nothing; a bill's asks versions/2026/HB1.json"


@check("build", "a request's sponsor the roster misses is matched to a winner of the election only where certain: "
                "same chamber, a middle initial, a tabled nickname or a whole middle name the other side lacks, "
                "a surname and initial no rival shares",
       needs=("build_lsrs",))
def _request_sponsor_winner(build_lsrs):
    """Alice, 13 November 2026: "as accurate as possible and not guess if we
    aren't confident." 29 of 492 requests got no party because the whole-name
    match misses "Lee Nyquist" for "Lee C. Nyquist", "Jim" for "James", a winner
    of a race under recount and a member elected to the other chamber. The
    second step (build_lsrs.winner_finder) matches only a winner of the
    request's own chamber, and says nothing where two could be meant."""
    L = build_lsrs
    results = {"races": {
        "H|Strafford|1": {"candidates": [  # a recount: drawn nowhere, still elected on the ballot
            {"name": "W. Packy Campbell", "party": "r", "elected": True}]},
        "H|Hillsborough|42": {"candidates": [
            {"name": "Lee C. Nyquist", "party": "d", "elected": True},
            {"name": "Sam Loser", "party": "r", "elected": False}]},
        "S|8": {"candidates": [{"name": "Jim Creighton", "party": "r", "elected": True}]},
        "H|Hillsborough|16": {"candidates": [{"name": "Ben Baroody", "party": "d", "elected": True}]},
        "H|Rockingham|13": {"candidates": [{"name": "Brian K. Chirichiello", "party": "r", "elected": True}]},
        "H|Rockingham|30": {"candidates": [
            {"name": "James Smith", "party": "r", "elected": True},
            {"name": "John Smith", "party": "d", "elected": True},
            {"name": "Jason A. Janvrin", "party": "r", "elected": True}]},
        "H|Coos|1": {"candidates": [{"name": "Rob Tied", "party": "r", "elected": None}]},
        "S|20": {"candidates": [{"name": "Dana Senator", "party": "d", "elected": True}]}}}
    drawn = {"S|8": {"elected": [{"n": "Jim Creighton", "p": "R", "k": "sitting", "id": "9917",
                                  "s": "james-creighton-hills-30"}]},
             "H|Hillsborough|42": {"elected": [{"n": "Lee C. Nyquist", "p": "D", "k": "new"}]}}
    pages = [{"slug": "lee-c-nyquist-hills-42", "name": "Lee C. Nyquist", "race": "H|Hillsborough|42"}]
    people = [{"name": "Campbell, W Packy", "county": "Straf", "slug": "w-packy-campbell-straf-3"},
              {"name": "Campbell, David", "county": "Hills", "slug": "david-campbell-hills-33"}]
    ws = L.election_winners(results, drawn, pages, people)
    find = L.winner_finder(ws)
    got = lambda n, b: find(n, b)
    assert got("W Packy Campbell", "HR") == ("W. Packy Campbell (R)", "w-packy-campbell-straf-3", "H"), (
        "a winner of a race under recount: the ballot's party, and the member's page where they have one")
    assert got("Lee Nyquist", "HB") == ("Lee C. Nyquist (D)", "lee-c-nyquist-hills-42", "H"), (
        "a middle initial on the winner's side is dropped")
    assert got("Jim Creighton", "SB") == ("Jim Creighton (R)", "james-creighton-hills-30", "S"), (
        "a sitting member elected to the Senate: the request's chamber decides, the person's page is theirs")
    assert got("Jim Creighton", "HB") is None, "his Senate win is not a House winner"
    assert got("Benjamin Baroody", "HB")[0] == "Ben Baroody (D)", "Benjamin is Ben"
    assert got("Brian Chirichiello", "HB")[0] == "Brian K. Chirichiello (R)"
    assert got("Jason Janvrin", "HB")[0] == "Jason A. Janvrin (R)"
    assert got("Jason Janvrin", "HB")[1] == "", "a winner with no page links nowhere, and still has a party"
    # The refusals.
    assert got("Jim Smith", "HB") is None, "Jim is no tabled nickname of James: nobody"
    assert got("James Q. Smith", "HB") is None, (
        "James Smith fits (a middle initial on one side), but John Smith also won with the same initial: "
        "not certain")
    assert got("James Smith", "HB")[0] == "James Smith (R)", "the whole name is the same: certain"
    assert got("Dana Senator", "HB") is None, "a winner of the other chamber only"
    assert got("Dana Senator", "SB")[0] == "Dana Senator (D)"
    assert got("Pat Moore", "HB") is None and got("Rob Tied", "HB") is None, (
        "a name that is no winner, and a tie, are nobody")
    assert got("Lee Nyquist", "CACR") is None, "a request with no chamber is not resolved here"
    assert not any(a in L.NICKNAMES[0] for a in ("pat", "chris", "sam")), "an ambiguous nickname is tabled"
    assert not any("pat" in g or "chris" in g or "sam" in g for g in L.NICKNAMES), (
        "Pat, Chris and Sam each stand for more than one name: not in the table")
    assert not L.same_first("tom", "tim") and not L.same_first("jack", "jim")
    assert L.same_first("ben", "benjamin") and not L.same_first("w", "walter"), (
        "an initial is only equal to itself")
    # A WHOLE MIDDLE NAME on the winner's side (24 November 2026: "Germano Martins",
    # "Mary Raven" and "Nathan Riggs" filed, the results print their middle names), still
    # refused where a rival winner shares the surname and first initial.
    whole = L.winner_finder(L.election_winners({"races": {
        "H|Merrimack|10": {"candidates": [{"name": "Germano Mendes Martins", "party": "d", "elected": True}]},
        "H|Hillsborough|12": {"candidates": [{"name": "Mary Beth Raven", "party": "d", "elected": True}]},
        "H|Rockingham|29": {"candidates": [{"name": "Nathan Andrew Riggs", "party": "d", "elected": True}]},
        "H|Belknap|2": {"candidates": [{"name": "Ann Marie Foss", "party": "r", "elected": True},
                                       {"name": "Arthur Foss", "party": "d", "elected": True}]}}}, {}, [], []))
    assert whole("Germano Martins", "HB")[0] == "Germano Mendes Martins (D)", "a whole middle name on one side"
    assert whole("Mary Raven", "HB")[0] == "Mary Beth Raven (D)"
    assert whole("Nathan Riggs", "HB")[0] == "Nathan Andrew Riggs (D)"
    assert whole("Ann Foss", "HB") is None, (
        "Ann Marie Foss fits, but Arthur Foss shares the surname and first initial: not certain")
    assert whole("Mary Raven", "SB") is None, "still only the request's own chamber"
    assert L.compatible("Mary Raven", "Mary Beth Raven") == (False, False), (
        "linking a winner to a member's page keeps the initials-only rule")
    assert L.compatible("Mary Raven", "Mary Beth Raven", whole_middles=True) == (True, False)
    assert L.compatible("Mary Ann Raven", "Mary Beth Raven", whole_middles=True) == (False, False), (
        "two middle names that differ are two people")
    # Two winners of one whole name are nobody.
    twin = L.winner_finder(L.election_winners({"races": {
        "H|A|1": {"candidates": [{"name": "Al Roe", "party": "r", "elected": True}]},
        "H|B|2": {"candidates": [{"name": "Al Roe", "party": "d", "elected": True}]}}}, {}, [], []))
    assert twin("Al Roe", "HB") is None, "two winners of the same name cannot be told apart"
    # The roster still wins where it matched, and a row's other fields are untouched.
    who = {"ellenread": ("Rep. Ellen Read (D)", "ellen-read-rock-10")}
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "a.", "sponsor": "Ellen Read"},
            {"lsr": "2027-0002", "session": 2027, "body": "HB", "title": "b.", "sponsor": "Lee Nyquist"},
            {"lsr": "2027-0003", "session": 2027, "body": "SB", "title": "c.", "sponsor": "Nobody Known"}]
    rows, unmatched = L.rows_from(lsrs, who, {}, 2027, ws)
    by = {r["n"]: r for r in rows}
    assert by["LSR 2027-0001"]["sponsor_label"] == "Rep. Ellen Read (D)", "the roster comes first"
    assert (by["LSR 2027-0002"]["sponsor_party"], by["LSR 2027-0002"]["sponsor_slug"]) == (
        "D", "lee-c-nyquist-hills-42")
    assert by["LSR 2027-0002"]["sponsor"] == "Lee Nyquist", "the source's own words are kept"
    assert "sponsor_party" not in by["LSR 2027-0003"] and unmatched == ["Nobody Known"]
    base, _ = L.rows_from(lsrs, who, {}, 2027)
    assert base[0] == rows[0], "a row the roster matched is identical with or without winners"
    return "ok", ("winners match only in the request's chamber; initials and tabled nicknames; "
                  "a rival of the same surname and initial, a twin, a tie and the other chamber refuse")


@check("build", "a constitutional amendment request's sponsor is matched by the whole name where one "
                "person alone has it, and a winner by the name their member's record is under where "
                "the owner tied the two", needs=("build_lsrs",))
def _request_sponsor_cacr_and_record(build_lsrs):
    """The owner, 17 November 2026: three of the 619 requests on the live list matched nobody
    and read "Party not on file". LSR 2027-0646 and 2027-0592, constitutional amendment
    requests of the members-elect Colin Mitchell (Carroll 8, whose House requests were his)
    and W. Gordon Allen (Hillsborough 30): a member-elect's match held only for a request of
    their chamber, and a CACR has none. And LSR 2027-0556, "Jeffrey Goley", re-elected on a
    ballot that printed "Jeff Goley": a short form is never taken on a name alone, but the
    owner matched that winner to former member 460, "Goley, Jeffrey" (corrections/
    members_elect.json), and that record ties the two names.

    build_lsrs, on those rows: a CACR's sponsor is the one sitting member, member-elect or
    winner of either chamber with the whole name, and nobody where another winner, or two
    sitting members, have it; the record's name counts only where the owner or the step
    linked the winner ("s"), so without it Jeffrey is not Jeff."""
    L = build_lsrs
    results = {"races": {
        "H|Carroll|8": {"candidates": [{"name": "Colin Mitchell", "party": "r", "elected": True}]},
        "H|Hillsborough|30": {"candidates": [{"name": "W. Gordon Allen", "party": "d", "elected": True}]},
        "H|Hillsborough|21": {"candidates": [{"name": "Jeff Goley", "party": "d", "elected": True}]},
        "H|Cheshire|1": {"candidates": [{"name": "Dale Twin", "party": "r", "elected": True}]},
        "S|5": {"candidates": [{"name": "Dale Twin", "party": "d", "elected": True}]}}}
    drawn = {"H|Carroll|8": {"elected": [{"n": "Colin Mitchell", "p": "R", "k": "new",
                                          "e": "colin-mitchell-carr-8"}]},
             "H|Hillsborough|30": {"elected": [{"n": "W. Gordon Allen", "p": "D", "k": "new",
                                                "e": "w-gordon-allen-hills-30"}]},
             "H|Hillsborough|21": {"elected": [{"n": "Jeff Goley", "p": "D", "k": "former", "id": "460",
                                                "s": "jeffrey-goley-hills-21"}]}}
    pages = [{"slug": "colin-mitchell-carr-8", "name": "Colin Mitchell", "race": "H|Carroll|8"},
             {"slug": "w-gordon-allen-hills-30", "name": "W. Gordon Allen", "race": "H|Hillsborough|30"}]
    people = [{"name": "Goley, Jeffrey", "county": "Hills", "slug": "jeffrey-goley-hills-21"}]
    ws = L.election_winners(results, drawn, pages, people)
    find = L.winner_finder(ws)
    goley = ("Jeff Goley (D)", "jeffrey-goley-hills-21", "H")
    assert find("Jeffrey Goley", "HB") == goley, (
        f"the name the owner's match's record is under: {find('Jeffrey Goley', 'HB')}")
    unlinked = L.winner_finder(L.election_winners(
        results, {k: v for k, v in drawn.items() if k != "H|Hillsborough|21"}, pages, people))
    assert unlinked("Jeffrey Goley", "HB") is None, "a short form taken on a name alone"
    assert find("Colin Mitchell", "CACR") == ("Colin Mitchell (R)", "colin-mitchell-carr-8", "H")
    assert find("Jeffrey Goley", "CACR") == goley, "a CACR by the record's whole name"
    assert find("Col Mitchell", "CACR") is None and find("Gordon Allen", "CACR") is None, (
        "a CACR matched by less than the whole name")
    assert find("Dale Twin", "CACR") is None, "two winners of one name, one in each chamber: nobody"
    # rows_from, with the members-elect's provisional pages on the roster's map as roster() puts
    # them, and two sitting members of one name (None).
    who = {"colinmitchell": ("Colin Mitchell (R)", "colin-mitchell-carr-8", "H"),
           "wgordonallen": ("W. Gordon Allen (D)", "w-gordon-allen-hills-30", "H"),
           "daletwin": ("Dale Twin (R)", "dale-twin-ches-1", "H"),
           "patsame": None}
    req = lambda n, body, who_: {"lsr": f"2027-{n}", "session": 2027, "body": body, "title": "t.",
                                 "sponsor": who_}
    lsrs = [req("0646", "CACR", "Colin Mitchell"), req("0651", "HB", "Colin Mitchell"),
            req("0592", "CACR", "W. Gordon Allen"), req("0556", "HB", "Jeffrey Goley"),
            req("0901", "SB", "Colin Mitchell"), req("0902", "CACR", "Dale Twin"),
            req("0903", "CACR", "Pat Same"), req("0904", "CACR", "Jeff Goley")]
    ws.append({"name": "Pat Same", "party": "R", "chamber": "S", "race": "S|9", "slug": "",
               "label": "Pat Same (R)", "names": ["Pat Same"]})
    rows, unmatched = L.rows_from(lsrs, who, {}, 2027, ws)
    by = {r["n"][4:]: (r["sponsor_slug"], r.get("sponsor_party", "")) for r in rows}
    want = {"2027-0646": ("colin-mitchell-carr-8", "R"), "2027-0651": ("colin-mitchell-carr-8", "R"),
            "2027-0592": ("w-gordon-allen-hills-30", "D"), "2027-0556": ("jeffrey-goley-hills-21", "D"),
            "2027-0901": ("", ""), "2027-0902": ("", ""), "2027-0903": ("", ""),
            "2027-0904": ("jeffrey-goley-hills-21", "D")}
    bad = [f"{n}: {by.get(n)}, not {w}" for n, w in want.items() if by.get(n) != w]
    assert not bad, "a request's sponsor matched otherwise than the rule says: " + "; ".join(bad)
    assert sorted(unmatched) == ["Colin Mitchell", "Dale Twin", "Pat Same"], unmatched
    return "ok", ("Colin Mitchell's and W. Gordon Allen's constitutional amendment requests are "
                  "theirs, by the whole name no one else has; Jeffrey Goley's is the winner Jeff "
                  "Goley's, whom the owner matched to his record, and is nobody's without it; a "
                  "CACR by less than the whole name, by a name two winners or two sitting "
                  "members share, and a member-elect's Senate request match nobody")


@check("build", "a request's sponsor written in a form the owner confirmed (corrections/"
                "name_forms.json) is the person the other form names; any other form, nobody",
       needs=("build_lsrs",))
def _request_sponsor_name_forms(build_lsrs):
    """The owner, 18 November 2026: LSR 2027-0708, a House resolution request filed by "Samuel
    Hoehn", is the Coos 1 member-elect the results print as "Sam Hoehn" -- "Yes, same person".
    Sam serves two names, so no table guesses it; the owner's word, in her hand file, ties the
    two forms of this one person's name.

    build_lsrs: name_forms reads the hand file, and its Hoehn entry carries the owner's words,
    the day and the evidence; rows_from matches "Samuel Hoehn" to Sam Hoehn's page with it and
    to nobody without it; a form the file does not hold ("Samuel Twin" beside a member-elect
    "Sam Twin") still matches nobody, so short forms stay unguessed; a confirmed form whose
    other form names two people matches nobody; an entry missing the owner's word stops the
    build."""
    L = build_lsrs
    forms = L.name_forms()
    assert forms.get("samuelhoehn") == "Sam Hoehn", f"the owner's Hoehn entry is not read: {forms}"
    raw = json.loads(_source("corrections/name_forms.json"))
    hoehn = [e for e in raw["forms"] if e["form"] == "Samuel Hoehn"]
    assert hoehn and hoehn[0]["said"] == "Yes, same person" and hoehn[0]["on"] == "2026-11-18" \
        and "2027-0708" in hoehn[0]["evidence"], f"the entry is not the owner's word: {hoehn}"
    who = {"samhoehn": ("Sam Hoehn (R)", "sam-hoehn-coos-1", "H"),
           "samtwin": ("Sam Twin (D)", "sam-twin-ches-2", "H"),
           "patsame": None}
    req = lambda n, body, who_: {"lsr": f"2027-{n}", "session": 2027, "body": body, "title": "t.",
                                 "sponsor": who_}
    lsrs = [req("0708", "HR", "Samuel Hoehn"), req("0901", "HB", "Samuel Twin"),
            req("0902", "HB", "Patrick Same"), req("0903", "SB", "Samuel Hoehn")]
    mine = dict(forms, patricksame="Pat Same")
    rows, unmatched = L.rows_from(lsrs, who, {}, 2027, forms=mine)
    by = {r["n"][4:]: r["sponsor_slug"] for r in rows}
    want = {"2027-0708": "sam-hoehn-coos-1", "2027-0901": "", "2027-0902": "", "2027-0903": ""}
    assert by == want, f"a sponsor matched otherwise than the owner's forms say: {by}"
    assert sorted(unmatched) == ["Patrick Same", "Samuel Hoehn", "Samuel Twin"], unmatched
    bare, _ = L.rows_from(lsrs[:1], who, {}, 2027)
    assert bare[0]["sponsor_slug"] == "", "Samuel Hoehn matched with no confirmed form"
    tmp = Path(tempfile.mkdtemp(prefix="gr-name-forms-"))
    try:
        (tmp / "f.json").write_text(json.dumps({"forms": [{"form": "Samuel Roe", "is": "Sam Roe"}]}),
                                    encoding="utf-8")
        try:
            L.name_forms(tmp / "f.json")
        except AssertionError:
            pass
        else:
            raise AssertionError("an entry without the owner's word, day and evidence was read")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("LSR 2027-0708's \"Samuel Hoehn\" is Sam Hoehn's, by the owner's confirmed form, "
                  "and nobody's without it or in the other chamber; \"Samuel Twin\", a form not in "
                  "the file, and a confirmed form naming two people match nobody; an entry without "
                  "the owner's word is refused")


@check("build", "a request's member-elect sponsor is drawn Rep.-elect or Sen.-elect "
                "on its card and its page until the day after they take office, and Rep. or Sen. "
                "from it, a sitting member elected to the other chamber among them; a sitting member "
                "re-elected as ever",
       needs=("build_lsrs", "build_request_pages"))
def _request_member_elect_title(build_lsrs, build_request_pages):
    """The owner, 17 November 2026: on a request's card a member-elect's chip reads Rep.-elect
    Colin Mitchell (R), the title the search already gives them (Sen.-elect
    for the Senate), until 2 December, when the members-elect take office.
    On the live list of that day 54 requests of 18 members-elect read "Colin Mitchell (R)".

    build_lsrs gives the label the title (elect_title) while elect_window is open -- the build's
    day before members_elect.json's "takes_office" -- to a member-elect matched by their
    provisional page (roster) or as a winner the file draws new or returning (Jeff Goley, a
    former member); never to a sitting member re-elected to the chamber they sit in; and the
    search still reads the name (label_name). build_request_pages draws a member-elect's
    chip on the request's page the same way (sponsors). From the day they take office, none.

    A SITTING MEMBER ELECTED TO THE OTHER CHAMBER is that chamber's member-elect (24 November
    2026), as the search's row (build_indexes.elect_rows) and their own page (the owner's Q3 of
    17 November 2026: 'Sen. "Elect" Laura Telerski', joined to her House record) title them: a
    Senate request of Jim Creighton's, matched as a winner, read "Jim Creighton (R)" with no title
    at all, and Laura Telerski's, matched by the House roster, "Rep. Laura Telerski (D)". Both
    read Sen.-elect now, linked to the record they have; a House request of theirs keeps the
    roster's label.

    FROM THE DAY AFTER THEY TAKE OFFICE THE "-ELECT" GOES AND THE TITLE STAYS (25 November 2026;
    build_lsrs.took_office, office_title; the day after, 3 December, the owner's of the same day:
    Organization Day's night publishes before they are sworn in, and reads as the days before).
    Until then the title went with it: on 2 December
    "Colin Mitchell (R)" and "Jim Creighton (R)", and the Senate requests' page chips went back to
    the old roster's "Rep. James Creighton (R - Hills 30)", a seat he no longer holds. Now every
    label and chip reads as on 17 November with the "-elect" taken off, "Rep. Colin Mitchell
    (R)", "Sen. Jim Creighton (R)", linked as before, and the search reads the same names; and
    Laura Telerski's House request, which the House roster matches, reads "Sen. Laura Telerski
    (D)" from that day too, when she sits in the Senate (build_lsrs.chamber_moves)."""
    L, RP = build_lsrs, build_request_pages
    tmp = Path(tempfile.mkdtemp(prefix="gr-elect-title-"))
    was = os.environ.get("GRANITE_BUILD_DATE")
    try:
        (tmp / "elect_pages.json").write_text(json.dumps({"takes_office": "2026-12-02", "pages": [
            {"slug": "colin-mitchell-carr-8", "name": "Colin Mitchell", "party": "R", "chamber": "H",
             "race": "H|Carroll|8"},
            {"slug": "kurt-webber-sd-2", "name": "Kurt Webber", "party": "D", "chamber": "S",
             "race": "S|2"}]}), encoding="utf-8")
        (tmp / "legislators.json").write_text(json.dumps([
            {"name": "Read, Ellen", "slug": "ellen-read-rock-10", "display": "Rep. Ellen Read (D)",
             "display_full": "Rep. Ellen Read (D - Rock 10)", "party": "D", "chamber": "H"},
            {"name": "Telerski, Laura", "slug": "laura-telerski-hills-11",
             "display": "Rep. Laura Telerski (D)", "display_full": "Rep. Laura Telerski (D - Hills 11)",
             "party": "D", "chamber": "H"},
            {"name": "Creighton, James", "slug": "james-creighton-hills-30",
             "display": "Rep. James Creighton (R)", "display_full": "Rep. James Creighton (R - Hills 30)",
             "party": "R", "chamber": "H"}]), encoding="utf-8")
        results = {"races": {
            "H|Hillsborough|21": {"candidates": [{"name": "Jeff Goley", "party": "d", "elected": True}]},
            "S|8": {"candidates": [{"name": "Jim Creighton", "party": "r", "elected": True}]},
            "S|13": {"candidates": [{"name": "Laura Telerski", "party": "d", "elected": True}]},
            "H|Rockingham|10": {"candidates": [{"name": "Ellen Read", "party": "d", "elected": True}]}}}
        drawn = {"H|Hillsborough|21": {"elected": [{"n": "Jeff Goley", "p": "D", "k": "former", "id": "460",
                                                    "s": "jeffrey-goley-hills-21"}]},
                 "S|8": {"elected": [{"n": "Jim Creighton", "p": "R", "k": "sitting", "id": "9917",
                                      "s": "james-creighton-hills-30"}]},
                 "S|13": {"elected": [{"n": "Laura Telerski", "p": "D", "k": "sitting", "id": "9117",
                                       "s": "laura-telerski-hills-11"}]},
                 "H|Rockingham|10": {"elected": [{"n": "Ellen Read", "p": "D", "k": "sitting",
                                                  "s": "ellen-read-rock-10"}]}}
        # The members-elect file, with the races, which the roster reads from the day they take
        # office for a member the election sent to the other chamber (chamber_moves).
        (tmp / "members_elect.json").write_text(json.dumps(
            {"election": "2026-11-03", "takes_office": "2026-12-02", "races": drawn}), encoding="utf-8")
        people = [{"name": "Goley, Jeffrey", "slug": "jeffrey-goley-hills-21"},
                  {"name": "Creighton, James", "slug": "james-creighton-hills-30", "chamber": "H"},
                  {"name": "Telerski, Laura", "slug": "laura-telerski-hills-11", "chamber": "H"},
                  {"name": "Read, Ellen", "slug": "ellen-read-rock-10", "chamber": "H"}]
        req = lambda n, body, who_: {"lsr": f"2027-{n}", "session": 2027, "body": body, "title": "t.",
                                     "sponsor": who_}
        lsrs = [req("0646", "CACR", "Colin Mitchell"), req("0651", "HB", "Colin Mitchell"),
                req("0700", "SB", "Kurt Webber"), req("0556", "HB", "Jeffrey Goley"),
                req("0800", "SB", "Jim Creighton"), req("0001", "HB", "Ellen Read"),
                req("0898", "SB", "Laura Telerski"), req("0899", "HB", "Laura Telerski")]
        got = {}
        for day in ("2026-11-17", "2026-12-02", "2026-12-03"):
            os.environ["GRANITE_BUILD_DATE"] = day
            who = L.roster(tmp, str(tmp / "no-results"))
            ws = L.election_winners(results, drawn, [], people, titled=L.elect_window(tmp),
                                    took=L.took_office(tmp))
            rows, _ = L.rows_from(lsrs, who, {}, 2027, ws)
            L.with_sponsor_names(rows, {})
            chips = RP.sponsors(tmp)
            got[day] = ({r["n"][4:]: r["sponsor_label"] for r in rows},
                        {r["n"][4:]: r.get("sponsor_names") for r in rows},
                        {s: chips[s]["display_full"] for s in chips},
                        # The chip the request's own page draws (person_chip), for the
                        # two sitting Representatives elected to the Senate.
                        {r["n"][4:]: RP.person_chip(chips, r["sponsor_slug"], r["sponsor_label"],
                                                    r.get("sponsor_party") or "")
                         for r in rows if r["n"][4:] in ("2027-0800", "2027-0898", "2027-0899")})
    finally:
        if was is None:
            os.environ.pop("GRANITE_BUILD_DATE", None)
        else:
            os.environ["GRANITE_BUILD_DATE"] = was
        shutil.rmtree(tmp, ignore_errors=True)
    rep, sen = "Rep.-elect ", "Sen.-elect "
    # ORGANIZATION DAY ITSELF READS AS THE DAYS BEFORE (the owner, 25 November 2026: "wait until
    # December 3rd to switch to the new titles since the swearing in ceremony happens on the
    # morning of December 2nd"): its night publishes before they are sworn in.
    assert got["2026-12-02"] == got["2026-11-17"], (
        f"on Organization Day the requests read otherwise than before it: {got['2026-12-02'][0]}")
    labels, names, chips, page = got["2026-11-17"]
    # THE REQUEST'S OWN PAGE (the owner, 24 November 2026: "Yes, fix it"): a Senate request of a
    # sitting Representative elected Senator draws its chip as the row titles them, linked to the
    # page they have; a House request of theirs keeps the roster's chip, their seat today.
    for n, who_, slug in (("2027-0800", "Jim Creighton", "james-creighton-hills-30"),
                          ("2027-0898", "Laura Telerski", "laura-telerski-hills-11")):
        assert (sen + who_ in page[n] and f'href="legislator/{slug}"' in page[n] and "Hills" not in page[n]), (
            f"{n}'s page chip is not the Senate member-elect's: {page[n]}")
    assert "Rep. Laura Telerski" in page["2027-0899"] and "Hills 11" in page["2027-0899"], (
        f"a House request of hers lost the roster's chip: {page['2027-0899']}")
    want = {"2027-0646": rep + "Colin Mitchell (R)", "2027-0651": rep + "Colin Mitchell (R)",
            "2027-0700": sen + "Kurt Webber (D)", "2027-0556": rep + "Jeff Goley (D)",
            "2027-0800": sen + "Jim Creighton (R)", "2027-0001": "Rep. Ellen Read (D)",
            "2027-0898": sen + "Laura Telerski (D)", "2027-0899": "Rep. Laura Telerski (D)"}
    bad = [f"{n}: {labels.get(n)!r}, not {w!r}" for n, w in want.items() if labels.get(n) != w]
    assert not bad, "a request's sponsor label before the day they take office: " + "; ".join(bad)
    assert names["2027-0646"] is None and names["2027-0556"] == ["Jeff Goley"], (
        f"the search reads the title as part of the name: {names}")
    assert (chips["colin-mitchell-carr-8"], chips["kurt-webber-sd-2"], chips["ellen-read-rock-10"]) == (
        rep + "Colin Mitchell (R)", sen + "Kurt Webber (D)", "Rep. Ellen Read (D - Rock 10)"), chips
    labels2, names2, chips, page = got["2026-12-03"]
    # THE DAY AFTER THEY TAKE OFFICE: the 17 November labels with the "-elect" taken off, the same
    # names for the search, the provisional pages' chips titled as their rows are, and the two
    # elected to the Senate drawn as senators on their Senate requests' pages, linked to the
    # record they have, not under the House seat they left -- and on Laura Telerski's House
    # request too, which the House roster matched: she sits in the Senate from that day.
    took = {n: w.replace(".-elect ", ". ", 1) for n, w in want.items()}
    took["2027-0899"] = "Sen. Laura Telerski (D)"
    bad = [f"{n}: {labels2.get(n)!r}, not {w!r}" for n, w in took.items() if labels2.get(n) != w]
    assert not bad, "a request's sponsor label on the day they take office: " + "; ".join(bad)
    assert names2 == names, f"the search's names changed with the title: {names2}, not {names}"
    assert (chips["colin-mitchell-carr-8"], chips["kurt-webber-sd-2"], chips["ellen-read-rock-10"]) == (
        "Rep. Colin Mitchell (R)", "Sen. Kurt Webber (D)", "Rep. Ellen Read (D - Rock 10)"), chips
    for n, who_, slug in (("2027-0800", "Jim Creighton", "james-creighton-hills-30"),
                          ("2027-0898", "Laura Telerski", "laura-telerski-hills-11"),
                          ("2027-0899", "Laura Telerski", "laura-telerski-hills-11")):
        assert ("Sen. " + who_ in page[n] and f'href="legislator/{slug}"' in page[n]
                and "Hills" not in page[n] and "-elect" not in page[n]), (
            f"{n}'s page chip on the day they take office is not the senator's: {page[n]}")
    assert L.label_name(rep + "Colin Mitchell (R)") == "Colin Mitchell" == L.label_name("Rep. Colin Mitchell (R)")
    return "ok", ("before 3 December, Organization Day included, Colin Mitchell's House and CACR "
                  "requests read Rep.-elect "
                  "Colin Mitchell (R), Kurt Webber's Sen.-elect, and Jeff Goley, a former "
                  "member returning, Rep.-elect, on the card's label and the page's chip; a "
                  "sitting member re-elected as before, and the two elected to the Senate Sen.-elect "
                  "on their Senate requests' cards and pages, as a winner or by the House roster, and "
                  "as before on a House one; the search reads the name alone; on 3 December the same "
                  "with the -elect taken off, Rep. Colin Mitchell (R) and Sen. Jim Creighton (R), the "
                  "senators' chips linked and, with no seat_switch.json here, seatless, Laura "
                  "Telerski's House request among them")


@check("build", "from the day after Organization Day each member a request names reads the office they "
                "hold: the titles of 1 and 2 December with the -elect taken off -- a match by "
                "nickname, sitting members elected to the Senate, co-sponsors and new members with no "
                "id among them -- on the row, the page's head and its Sponsors; everyone else as the "
                "days before",
       needs=("build_lsrs", "build_request_pages", "build_members_elect"))
def _request_labels_on_organization_day(L, RP, BME):
    """Organization Day, 2 December 2026: the members elected on 3 November take office. The day
    after, 3 December (the owner, 25 November 2026: "wait until December 3rd to switch to the new
    titles since the swearing in ceremony happens on the morning of December 2nd"; Organization
    Day's night publishes before they are sworn in, and reads as 1 December), the members-elect
    file retires and the provisional pages stay (build_members_elect, build_elect_pages). The
    seats the switch gives the two elected to the Senate on their chips are site/seat_switch.json's,
    which this does not write, and _seat_switch_by_day holds. Until 25 November 2026 a request's member-elect lost the title with the
    "-elect": on the list of 24 November, 290 of 1,313 requests would have read "Ben Baroody (D)"
    or "Jim Creighton (R)" from that day, no title on the card or the chip and no chamber for the
    Sponsor filter (app.js spChamber), and Jim Creighton's and Laura Telerski's Senate requests'
    pages the old roster's "Rep. James Creighton (R - Hills 30)", a seat he no longer holds. A
    request labels a member as the office they hold that day: Rep. or Sen., the party they were
    elected under, and a link to their page where there is one (build_lsrs.took_office,
    office_title).

    Over a fixture election, as the nights build it -- 1 December with the members-elect file, 2
    December without it and the roster still the old term's, so election_races works the races
    out again -- through load_winners, roster, rows_from, with_sponsor_names and the pages
    build_request_pages writes, each person on the two days beside each other:

      - a match by nickname: "Benjamin Baroody", the former member the results print "Ben
        Baroody" (NICKNAMES), returning: Rep.-elect, then Rep. Ben Baroody (D), linked to his page;
      - sitting members elected to the Senate, Jim Creighton (a winner, as the list spells him)
        and Laura Telerski (the House roster has her; a Senate request goes to the winners):
        Sen.-elect, then Sen., each page's chip linked to their record and never the House seat;
        and where the House roster matches her -- a House request of hers, her name as a
        co-sponsor -- Rep. Laura Telerski (D) with her House seat on 1 December, Sen. Laura
        Telerski (D) on 2 December, seatless and among the Senators (build_lsrs.chamber_moves);
      - a new member with a provisional page and no id, Colin Mitchell: Rep.-elect, then Rep.,
        linked to that page, his CACR the same; and Dana New, with no page: no link, and the title
        and party all the same;
      - co-sponsors of Ellen Read's request, the same on the row, and its Sponsors section on 2
        December is 1 December's with the "-elect" taken off;
      - as they were: Ellen Read, re-elected, with the roster's label, chip and seat; Nora North,
        the winner of a race not final, who has no page, the name and party alone on both days,
        since the record does not say yet who holds the seat; and the names the search reads."""
    seat = {"H": "Rep.", "S": "Sen."}
    mem = lambda i, last, first, ch, county, dist, party, tag, slug, **k: {
        "id": i, "name": f"{last}, {first}", "chamber": ch, "county": county, "district": dist,
        "party": party, "party_code": party, "slug": slug, "display": f"{seat[ch]} {first} {last} ({party})",
        "display_plain": f"{seat[ch]} {first} {last}",
        "display_full": f"{seat[ch]} {first} {last} ({party} - {tag})", **k}
    cand = lambda n, p, won=True: {"name": n, "party": p, "votes": 100 if won else 90, "write_in": False,
                                   "elected": won}
    race = lambda towns, seats, *cs: {"seats": seats, "floterial": False, "towns": towns, "scatter": 0,
                                      "candidates": list(cs)}
    results = {"_source": [{"url": "https://www.sos.nh.gov/elections/election-results", "saved": "2026-11-05"}],
               "election": "2026-11-03", "term": "2027-2028", "races": {
                   "H|Rockingham|10": race(["Rye"], 1, cand("Ellen Read", "d"), cand("Rob Rival", "r", False)),
                   "H|Hillsborough|16": race(["Weare"], 1, cand("Ben Baroody", "d")),
                   "H|Carroll|8": race(["Conway"], 2, cand("Colin Mitchell", "r"), cand("Dana New", "d")),
                   "H|Coos|2": race(["Gorham"], 1, cand("Nora North", "d")),
                   "S|8": race(["Conway", "Rye"], 1, cand("Jim Creighton", "r")),
                   "S|13": race(["Gorham", "Weare"], 1, cand("Laura Telerski", "d"))}}
    hand = {"2026-11-03": {"recount_deadline": "2026-11-13",
                           "matches": {"S|8": {"Jim Creighton": "102"}, "S|13": {"Laura Telerski": "103"},
                                       "H|Hillsborough|16": {"Ben Baroody": "201"},
                                       "H|Carroll|8": {"Colin Mitchell": None, "Dana New": None}},
                           "not_final": {"H|Coos|2": {"seats": 1, "recount": True}}}}
    town = lambda senate, county, dist, seats: {"0": {"congress": 1, "council": 1, "senate": senate, "house": [
        {"county": county, "district": dist, "floterial": False, "seats": seats}]}}
    districts = {"Rye": town(8, "Rockingham", 10, 1), "Conway": town(8, "Carroll", 8, 2),
                 "Weare": town(13, "Hillsborough", 16, 1), "Gorham": town(13, "Coos", 2, 1)}
    sitting = [mem("101", "Read", "Ellen", "H", "Rockingham", "10", "D", "Rock 10", "ellen-read-rock-10"),
               mem("102", "Creighton", "James", "H", "Hillsborough", "30", "R", "Hills 30",
                   "james-creighton-hills-30"),
               mem("103", "Telerski", "Laura", "H", "Hillsborough", "11", "D", "Hills 11", "laura-telerski-hills-11")]
    former = [mem("201", "Baroody", "Benjamin", "H", "Hillsborough", "39", "D", "Hills 39",
                  "benjamin-baroody-hills-39", former=True,
                  served={"first": "12/5/2018", "last": "12/1/2020", "terms": ["2019-2020"]})]
    # Colin Mitchell's provisional page, as build_elect_pages writes it on both days (nobody is
    # numbered until the roster is the new term's); Dana New has none (an address taken, say).
    pages = {"election": "2026-11-03", "takes_office": "2026-12-02", "sources": [], "moved": {}, "pages": [
        {"slug": "colin-mitchell-carr-8", "name": "Colin Mitchell", "party": "R", "chamber": "H",
         "county": "Carroll", "district": "8", "race": "H|Carroll|8", "towns": ["Conway"]}]}
    req = lambda n, body, who_, co=(): {"lsr": f"2027-{n}", "session": 2027, "body": body,
                                        "title": f"relative to item {n}.", "sponsor": who_,
                                        "withdrawn": False, "cosponsors": list(co)}
    lsrs = [req("0001", "HB", "Ellen Read", ("Colin Mitchell", "Jim Creighton", "Dana New")),
            req("0002", "HB", "Benjamin Baroody", ("Laura Telerski",)), req("0003", "SB", "Jim Creighton"),
            req("0004", "SB", "Laura Telerski"), req("0005", "HB", "Colin Mitchell"),
            req("0006", "HB", "Dana New"), req("0007", "HB", "Nora North"),
            req("0008", "CACR", "Colin Mitchell"), req("0009", "HB", "Laura Telerski", ("Ellen Read",))]
    meta = {"terms": ["2025-2026"], "requests": {"term": "2027-requests", "label": "2027 Bill Requests",
                                                 "year": 2027, "abbr": L.ABBR}}
    was_day, was_cwd = os.environ.get("GRANITE_BUILD_DATE"), os.getcwd()
    got = {}
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        site, coll = root / "site", root / "collected"
        for p in (site / "idx", coll, root / "corrections"):
            p.mkdir(parents=True)

        def put(path, obj):
            path.write_text(json.dumps(obj), encoding="utf-8")
        put(coll / "election_2026.json", results)
        put(root / "corrections" / "members_elect.json", hand)
        for name, obj in (("districts.json", districts), ("legislators.json", sitting),
                          ("former.json", former), ("elect_pages.json", pages), ("meta.json", meta)):
            put(site / name, obj)
        (site / "bills.html").write_text(_source("src/pages/bills.html"), encoding="utf-8")
        try:
            os.chdir(root)
            settled, _note = BME.read_hand(root / "corrections" / "members_elect.json", "2026-11-03")
            races, _report = BME.members_elect(results, sitting, former, districts, settled, "2026-12-01")
            put(site / "members_elect.json", {"election": "2026-11-03", "takes_office": "2026-12-02",
                                              "term": "2027-2028", "races": races})
            for day in ("2026-12-01", "2026-12-02", "2026-12-03"):
                os.environ["GRANITE_BUILD_DATE"] = day
                if day == "2026-12-03":
                    # The day after Organization Day: the step deletes the file; the
                    # provisional pages stay. (On Organization Day the file is still written.)
                    (site / "members_elect.json").unlink()
                winners, _said = L.load_winners(site, str(coll))
                rows, unmatched = L.rows_from(lsrs, L.roster(site, str(coll), 2027), year=2027,
                                              winners=winners)
                L.with_sponsor_names(rows, L.page_names(site))
                put(site / "idx" / "2027-requests.json", rows)
                RP.write(site, "https://x")
                got[day] = ({r["n"][4:]: r for r in rows}, unmatched,
                            {p.stem: p.read_text(encoding="utf-8") for p in (site / "request").glob("*.html")})
        finally:
            os.chdir(was_cwd)
            if was_day is None:
                os.environ.pop("GRANITE_BUILD_DATE", None)
            else:
                os.environ["GRANITE_BUILD_DATE"] = was_day
    # ORGANIZATION DAY READS AS THE DAY BEFORE (the owner, 25 November 2026: "wait until December
    # 3rd to switch to the new titles since the swearing in ceremony happens on the morning of
    # December 2nd"), its pages but for the day each carries.
    o_rows, o_unmatched, o_pages = got["2026-12-02"]
    assert o_rows == got["2026-12-01"][0] and o_unmatched == got["2026-12-01"][1] \
        and sorted(o_pages) == sorted(got["2026-12-01"][2]), (
        "on Organization Day the requests read otherwise than the day before")
    (r1, u1, h1), (r2, u2, h2) = got["2026-12-01"], got["2026-12-03"]
    assert not u1 and not u2, f"a name matched nobody: {u1} {u2}"
    off = lambda s: s.replace(".-elect ", ". ")
    want = {"2027-0001": ("Rep. Ellen Read (D)", "ellen-read-rock-10", "D"),
            "2027-0002": ("Rep.-elect Ben Baroody (D)", "benjamin-baroody-hills-39", "D"),
            "2027-0003": ("Sen.-elect Jim Creighton (R)", "james-creighton-hills-30", "R"),
            "2027-0004": ("Sen.-elect Laura Telerski (D)", "laura-telerski-hills-11", "D"),
            "2027-0005": ("Rep.-elect Colin Mitchell (R)", "colin-mitchell-carr-8", "R"),
            "2027-0006": ("Rep.-elect Dana New (D)", "", "D"),
            "2027-0007": ("Nora North (D)", "", "D"),
            "2027-0008": ("Rep.-elect Colin Mitchell (R)", "colin-mitchell-carr-8", "R"),
            "2027-0009": ("Rep. Laura Telerski (D)", "laura-telerski-hills-11", "D")}
    co = [("Rep.-elect Colin Mitchell (R)", "colin-mitchell-carr-8", "R", "H"),
          ("Sen.-elect Jim Creighton (R)", "james-creighton-hills-30", "R", "S"),
          ("Rep.-elect Dana New (D)", "", "D", "H")]
    prime = lambda r: (r["sponsor_label"], r["sponsor_slug"], r.get("sponsor_party", ""))
    cos = lambda r: [(c["label"], c["slug"], c.get("party", ""), c.get("chamber", "")) for c in r.get("cosponsors") or []]
    # The same people on 3 December, each label with the "-elect" taken off and nothing else;
    # Laura Telerski, where the House roster matched her, the Senate's member from that day.
    took = {n: (off(v[0]),) + v[1:] for n, v in want.items()}
    took["2027-0009"] = ("Sen. Laura Telerski (D)", "laura-telerski-hills-11", "D")
    her = {"1 December": [("Rep. Laura Telerski (D)", "laura-telerski-hills-11", "D", "H")],
           "3 December": [("Sen. Laura Telerski (D)", "laura-telerski-hills-11", "D", "S")]}
    for day, rs, w, wc, ch in (("1 December", r1, want, co, "H"),
                               ("3 December", r2, took, [(off(c[0]),) + c[1:] for c in co], "S")):
        bad = [f"{n}: {prime(rs[n])}, not {v}" for n, v in w.items() if prime(rs[n]) != v]
        assert not bad, f"on {day} a request's prime sponsor reads otherwise: " + "; ".join(bad)
        assert cos(rs["2027-0001"]) == wc, f"on {day} the co-sponsors read {cos(rs['2027-0001'])}, not {wc}"
        assert cos(rs["2027-0002"]) == her[day] and rs["2027-0009"].get("sponsor_chamber") == ch, (
            f"on {day} Laura Telerski as the House roster matched her: {cos(rs['2027-0002'])}, "
            f"her House request's chamber {rs['2027-0009'].get('sponsor_chamber')}")
    assert {n: r.get("sponsor_names") for n, r in r1.items()} == {n: r.get("sponsor_names") for n, r in r2.items()}, (
        "the names the search reads changed with the title")

    def head(html):
        return re.search(r'<dl class="rfacts">.*?</dl>', html, re.S).group(0)

    def sponsors(html):
        m = re.search(r'<section class="w4" id="sponsors">.*?</section>', html, re.S)
        return m.group(0) if m else ""
    text = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h))
    assert sorted(h1) == sorted(h2) == sorted(want), f"the request pages written: {sorted(h1)} {sorted(h2)}"
    bad = [n for n in want if n != "2027-0009" and head(h2[n]) != off(head(h1[n]))]
    assert not bad, ("on 3 December a page's head is not 1 December's with the -elect taken off: "
                     + "; ".join(f"{n}: {text(head(h2[n]))!r}" for n in bad))
    t1, t2 = (head(h["2027-0009"]) for h in (h1, h2))
    assert "Rep. Laura Telerski (D - Hills 11)" in text(t1) and "Sen. Laura Telerski (D)" in text(t2) \
        and 'href="legislator/laura-telerski-hills-11"' in t2 and "Hills" not in t2, (
        f"her House request's chip: {text(t1)!r}, then {text(t2)!r}")
    spch = lambda s: re.findall(r'<h3 class="spch">(\w+) <span class="sechn">(\d+)</span>', s)
    b1, b2 = sponsors(h1["2027-0002"]), sponsors(h2["2027-0002"])
    assert spch(b1) == [] and "Hills 11" in b1 and spch(b2) == [("Representatives", "1"), ("Senators", "1")] \
        and "Sen. Laura Telerski (D)" in text(b2) and "Hills" not in b2, (
        f"Laura Telerski as a co-sponsor is not among the Senators on 3 December alone: {text(b2)!r}")
    assert spch(sponsors(h2["2027-0009"])) == [("Senators", "1"), ("Representatives", "1")], (
        f"her House request's Sponsors do not open with the Senators on 3 December: {spch(sponsors(h2['2027-0009']))}")
    for n, who_, slug in (("2027-0003", "Jim Creighton (R)", "james-creighton-hills-30"),
                          ("2027-0004", "Laura Telerski (D)", "laura-telerski-hills-11")):
        for day, h in (("1 December", h1[n]), ("3 December", h2[n])):
            assert (f'href="legislator/{slug}"' in head(h) and "Hills" not in head(h)
                    and f"{'Sen.-elect' if day[0] == '1' else 'Sen.'} {who_}" in text(head(h))), (
                f"{n}'s chip on {day} is not the senator's, linked to their record: {text(head(h))!r}")
    assert "Rep.-elect Dana New (D)" in text(head(h1["2027-0006"])) \
        and "Rep. Dana New (D)" in text(head(h2["2027-0006"])) and "href=" not in head(h2["2027-0006"]), (
        f"a new member with no page: {text(head(h2['2027-0006']))!r}")
    assert "Rep. Ellen Read (D - Rock 10)" in text(head(h2["2027-0001"])) \
        and head(h1["2027-0001"]) == head(h2["2027-0001"]), "a member re-elected does not keep the roster's chip"
    s1, s2 = sponsors(h1["2027-0001"]), sponsors(h2["2027-0001"])
    assert s1 and "-elect" in s1 and s2 == off(s1) and "Hills 30" not in s2, (
        f"on 3 December the Sponsors are not 1 December's with the -elect taken off: {s2[:600]!r}")
    # THE SPONSOR FILTER'S CHAMBER, which app.js reads off the label's title (spChamber): each member
    # under the chamber they sit in that day, on both days; Nora North, with none, under none.
    order = sorted(want)
    chambers = _app_js("(() => " + json.dumps([[rs[n]["sponsor_label"] for n in order] for rs in (r1, r2)])
                       + ".map(ls => ls.map(l => scope.spChamber(l))))()", names=("spChamber",))
    if chambers is None:
        return "skip", ("the rows, the heads and the Sponsors hold on both days; node, app.js or the stub "
                        "is not here for the Sponsor filter's chamber")
    sits = {"2027-0003": "S", "2027-0004": "S", "2027-0007": ""}
    assert chambers == [[sits.get(n, "H") for n in order],
                        [sits.get(n, "S" if n == "2027-0009" else "H") for n in order]], (
        f"the Sponsor filter's chamber by the label, 1 and 3 December: {chambers}")
    return "ok", ("on 1 December Rep.-elect and Sen.-elect, on 3 December Rep. Ben Baroody (D) by his "
                  "nickname, Sen. Jim Creighton (R) and Sen. Laura Telerski (D) linked to their records with "
                  "no House seat, on a House request and as a co-sponsor too, among the Senators; Rep. Colin "
                  "Mitchell (R) linked to his provisional page, Rep. Dana New (D) with no page and no link, "
                  "and the co-sponsors the same, on the row, the head and the Sponsors; Ellen Read and Nora "
                  "North, of a race not final, as they were; the search's names unchanged")


# app.js's cardSponsor in node, on an English page and a Spanish one (window.GR_WORDS as
# i18n.page_words gives it, from lang/es.json).
_CARD_ELECT_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({cardSponsor})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const labels = ["Rep.-elect Colin Mitchell (R)", "Sen.-elect Kurt Webber (R)",
                "Rep. Ellen Read (D)"];
const out = {en: labels.map(l => s.cardSponsor({sponsor_label: l}).display_full)};
globalThis.window.GR_WORDS = JSON.parse(fs.readFileSync("./words.json", "utf8"));
out.es = labels.map(l => s.cardSponsor({sponsor_label: l}).display_full);
out.party = s.cardSponsor({sponsor_label: labels[0]}).party;
console.log("@@" + JSON.stringify(out));
"""


@check("frontend", "on a Spanish page a request card's member-elect sponsor is titled in Spanish, from "
                   "lang/es.json")
def _request_card_elect_title_es():
    """The owner, 18 November 2026: on /es/ pages a member-elect sponsor's chip on a request card
    read "Rep.-elect", in English. The row carries the English title (build_lsrs.elect_title);
    app.js's cardSponsor now puts the page's words for it in its place, the keys elect.title_rep
    and elect.title_sen that find.js already draws. Run in node: on an English page the labels
    are as the row has them; on a Spanish page, with lang/es.json's words, "Rep. electo/a
    Colin Mitchell (R)" and "Sen. electo/a Kurt Webber (R)", and a sitting member's label
    unchanged; the party still read from the label."""
    es = json.loads(_source("src/pages/lang/es.json"))
    es = es.get("strings", es)
    words = {k: es[k]["es"] for k in ("elect.title_rep", "elect.title_sen") if es.get(k, {}).get("es")}
    assert len(words) == 2, f"lang/es.json lacks the Spanish member-elect titles: {words}"
    got = _node_app(_CARD_ELECT_HARNESS, {"words.json": json.dumps(words)})
    if got is None:
        return "skip", "node, app.js or the DOM stub is not here"
    rep, sen = "Rep.-elect ", "Sen.-elect "
    assert got["en"] == [rep + "Colin Mitchell (R)", sen + "Kurt Webber (R)", "Rep. Ellen Read (D)"], got["en"]
    assert got["es"] == [words["elect.title_rep"] + " Colin Mitchell (R)",
                         words["elect.title_sen"] + " Kurt Webber (R)", "Rep. Ellen Read (D)"], got["es"]
    assert got["party"] == "R", got
    return "ok", (f"a Spanish page titles a member-elect sponsor {words['elect.title_rep']} and "
                  f"{words['elect.title_sen']}; an English page and a sitting member as before")


@check("build", "a withdrawn request of a member who is not returning is dropped and its address forwards; "
                "decided by the member's slug, never the name; a request still on the list is kept")
def _requests_not_returning():
    """Alice, 12 November 2026: requests of members who lost reelection are
    removed, not labelled withdrawn. build_lsrs.not_returning reads the
    election's winners by slug; drop_unreturned drops only a request that left
    the list; build_pages.moved_requests forwards its address."""
    import inspect
    import tempfile
    import build_lsrs as L
    import build_pages as BPG
    import build_request_pages as RP
    mem = lambda slug, ch, county, dist: {"slug": slug, "chamber": ch, "county": county,
                                          "district": dist}
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "idx").mkdir()
        (site / "request").mkdir()
        (site / "bills.html").write_text(_source("src/pages/bills.html"),
                                         encoding="utf-8")
        (site / "legislators.json").write_text(json.dumps([
            mem("ann-lost-rock-1", "H", "Rockingham", "1"),
            mem("bo-stays-rock-2", "H", "Rockingham", "2"),
            mem("cy-open-rock-3", "H", "Rockingham", "3"),
            mem("di-gone-sd-4", "S", "Merrimack", "4"),
            mem("ed-norace-rock-9", "H", "Rockingham", "9")]), encoding="utf-8")
        # Ann Lost's name is on a winner of her district, with no slug of hers:
        # a name match would keep her, the slug rule does not.
        (site / "members_elect.json").write_text(json.dumps({"races": {
            "H|Rockingham|1": {"seats": 1, "not_final": 0, "held": 0, "elected": [
                {"n": "Ann Lost", "p": "R", "k": "new"}]},
            "H|Rockingham|2": {"seats": 1, "not_final": 0, "held": 0, "elected": [
                {"n": "Bo Stays", "k": "sitting", "s": "bo-stays-rock-2"}]},
            "H|Rockingham|3": {"seats": 1, "not_final": 1, "held": 0, "elected": []},
            "S|4": {"seats": 1, "not_final": 0, "held": 0, "elected": [
                {"n": "Di Other", "k": "new"}]}}}), encoding="utf-8")
        gone, undecided = L.not_returning(site)
        assert sorted(gone) == ["ann-lost-rock-1", "di-gone-sd-4"], gone
        assert sorted(undecided) == ["cy-open-rock-3", "ed-norace-rock-9"], undecided
        lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "a.",
                 "sponsor": "Ann Lost", "withdrawn": True},
                {"lsr": "2027-0002", "session": 2027, "body": "SB", "title": "b.",
                 "sponsor": "Di Gone", "withdrawn": True},
                {"lsr": "2027-0003", "session": 2027, "body": "HB", "title": "c.",
                 "sponsor": "Bo Stays", "withdrawn": True},
                {"lsr": "2027-0004", "session": 2027, "body": "HB", "title": "d.",
                 "sponsor": "Ann Lost", "withdrawn": False},
                {"lsr": "2027-0005", "session": 2027, "body": "HB", "title": "e.",
                 "sponsor": "Cy Open", "withdrawn": True},
                {"lsr": "2027-0006", "session": 2027, "body": "HB", "title": "f.",
                 "sponsor": "Nobody Known", "withdrawn": True}]
        who = {"annlost": ("Rep. Ann Lost (R)", "ann-lost-rock-1"),
               "digone": ("Sen. Di Gone (R)", "di-gone-sd-4"),
               "bostays": ("Rep. Bo Stays (D)", "bo-stays-rock-2"),
               "cyopen": ("Rep. Cy Open (D)", "cy-open-rock-3")}
        rows, _ = L.rows_from(lsrs, who, {}, 2027)
        kept, dropped = L.drop_unreturned(rows, gone)
        assert [r["n"] for r in dropped] == ["LSR 2027-0001", "LSR 2027-0002"], (
            "a withdrawn request of a member not returning is not dropped, or another is")
        assert [r["n"] for r in kept] == ["LSR 2027-0003", "LSR 2027-0004", "LSR 2027-0005",
                                          "LSR 2027-0006"], (
            "kept: a returning member's withdrawn, a not-returning member's standing, a withdrawn "
            "one whose race is undecided, a withdrawn one whose sponsor has no slug")
        assert [r["withdrawn"] for r in kept] == [True, False, True, True]
        req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027,
               "dropped": sorted(r["address"] for r in dropped)}
        (site / "meta.json").write_text(json.dumps({"requests": req}), encoding="utf-8")
        (site / "idx" / "2027-requests.json").write_text(json.dumps(kept), encoding="utf-8")
        (site / "legislators.json").write_text("[]", encoding="utf-8")
        # A page an earlier night wrote for a dropped request goes; its address forwards.
        (site / "request" / "2027-0001.html").write_text("old", encoding="utf-8")
        RP.write(site, "https://x")
        pages = sorted(p.name for p in (site / "request").glob("*.html"))
        assert pages == ["2027-0003.html", "2027-0004.html", "2027-0005.html", "2027-0006.html"], pages
        red = BPG.moved_requests(site)
        assert red == ("/request/2027-0001 /bills?term=2027-requests 301\n"
                       "/request/2027-0002 /bills?term=2027-requests 301\n"), red
    # No file of results: nobody is dropped.
    with tempfile.TemporaryDirectory() as d:
        assert L.not_returning(Path(d)) == ({}, {})
    src = inspect.getsource(L.not_returning) + inspect.getsource(L.drop_unreturned)
    code = re.sub(r'""".*?"""', "", src, flags=re.S)
    assert "_fold" not in code and "name" not in code and '"n"' not in code, (
        "the not-returning rule reads a name")
    return "ok", ("dropped by slug and forwarded; a returning member's withdrawn, a standing request, "
                  "an undecided race and an unidentified sponsor all kept")


@check("build", "a withdrawn request of a member not returning stays dropped from Organization Day, when "
                "the members-elect file retires: its races worked out again while the roster is the old "
                "term's, and after the New term run the roster says who came back; a returning member's, "
                "a member's moved to the Senate and a standing request are kept",
       needs=("build_lsrs", "build_members_elect"))
def _requests_not_returning_from_organization_day(L, BME):
    """The rehearsal of 17 November 2026. build_members_elect retires
    site/members_elect.json -- on Organization Day then, the day after it,
    3 December 2026, since the owner's word of 25 November -- and
    not_returning read nothing else, so the night it retired published
    every withdrawn request of a member not returning as "Withdrawn" again --
    on the live site request/2027-0320 -- with its 301 to the list gone,
    against the owner's rule of 12 November. Over a fixture election, as the
    nights build it: 1 and 2 December with the file; 3 December with none and
    the old roster (election_races works the races out again); 4 December
    after the New term run, the new roster sitting and the member who lost,
    and the representative now in the Senate under a new number, in
    former.json."""
    import tempfile
    mem = lambda i, last, first, ch, county, dist, party, slug, **k: {
        "id": i, "name": f"{last}, {first}", "chamber": ch, "county": county, "district": dist,
        "party": party, "party_code": party, "slug": slug,
        "display": f"{'Rep.' if ch == 'H' else 'Sen.'} {first} {last} ({party})", **k}
    cand = lambda n, p, won: {"name": n, "party": p, "votes": 100 if won else 90,
                              "write_in": False, "elected": won}
    results = {"_source": [{"url": "https://www.sos.nh.gov/elections/election-results",
                            "saved": "2026-11-05"}],
               "election": "2026-11-03", "term": "2027-2028", "races": {
                   "H|Belknap|1": {"seats": 2, "floterial": False, "towns": ["Alton"], "scatter": 0,
                                   "candidates": [cand("Bo Stays", "r", True),
                                                  cand("Nan New", "d", True),
                                                  cand("Ann Lost", "r", False)]},
                   "H|Belknap|2": {"seats": 1, "floterial": False, "towns": ["Barnstead"],
                                   "scatter": 0, "candidates": [cand("Dee Next", "d", True)]},
                   "S|1": {"seats": 1, "floterial": False, "towns": ["Alton", "Barnstead"],
                           "scatter": 0, "candidates": [cand("Cy Mover", "d", True),
                                                        cand("Opp One", "r", False)]}}}
    hand = {"2026-11-03": {"recount_deadline": "2026-11-13", "matches": {
        "H|Belknap|1": {"Nan New": None}, "H|Belknap|2": {"Dee Next": None}}}}
    old = [mem("11", "Lost", "Ann", "H", "Belknap", "1", "R", "ann-lost-belk-1"),
           mem("12", "Stays", "Bo", "H", "Belknap", "1", "R", "bo-stays-belk-1"),
           mem("13", "Mover", "Cy", "H", "Belknap", "2", "D", "cy-mover-belk-2"),
           mem("14", "Seat", "Sy", "S", "", "1", "R", "sy-seat-sd-1")]
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "a.", "sponsor": "Ann Lost",
             "withdrawn": True},
            {"lsr": "2027-0002", "session": 2027, "body": "HB", "title": "b.", "sponsor": "Bo Stays",
             "withdrawn": True},
            {"lsr": "2027-0003", "session": 2027, "body": "HB", "title": "c.", "sponsor": "Ann Lost",
             "withdrawn": False},
            {"lsr": "2027-0004", "session": 2027, "body": "SB", "title": "d.", "sponsor": "Cy Mover",
             "withdrawn": True}]
    was_day, was_cwd = os.environ.get("GRANITE_BUILD_DATE"), os.getcwd()
    got = {}
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        site, coll = root / "site", root / "collected"
        for p in (site, coll, root / "corrections"):
            p.mkdir(parents=True)
        (coll / "election_2026.json").write_text(json.dumps(results), encoding="utf-8")
        (root / "corrections" / "members_elect.json").write_text(json.dumps(hand), encoding="utf-8")
        town = lambda dist, seats: {"0": {"congress": 1, "council": 1, "senate": 1, "house": [
            {"county": "Belknap", "district": dist, "floterial": False, "seats": seats}]}}
        (site / "districts.json").write_text(json.dumps({"Alton": town(1, 2), "Barnstead": town(2, 1)}),
                                             encoding="utf-8")

        def put(name, obj):
            (site / name).write_text(json.dumps(obj), encoding="utf-8")

        def night(day):
            os.environ["GRANITE_BUILD_DATE"] = day
            gone, undecided = L.not_returning(site, str(coll))
            rows, _ = L.rows_from(lsrs, L.roster(site, str(coll)), {}, 2027)
            kept, dropped = L.drop_unreturned(rows, gone)
            return sorted(gone), [r["n"] for r in dropped], {r["n"]: r for r in kept}
        try:
            os.chdir(root)
            put("meta.json", {"terms": ["2025-2026"]})
            put("legislators.json", old)
            put("former.json", [])
            # 1 December: the members-elect file as the step writes its races.
            settled, _note = BME.read_hand(root / "corrections" / "members_elect.json", "2026-11-03")
            races, _report = BME.members_elect(results, old, [], json.loads(
                (site / "districts.json").read_text(encoding="utf-8")), settled, "2026-12-01")
            put("members_elect.json", {"election": "2026-11-03", "takes_office": "2026-12-02",
                                       "term": "2027-2028", "races": races})
            got["1 Dec"] = night("2026-12-01")
            # 2 December, Organization Day: the file is still written, until the day after.
            got["2 Dec"] = night("2026-12-02")
            # 3 December: the file retired, the roster still the old term's.
            (site / "members_elect.json").unlink()
            got["3 Dec"] = night("2026-12-03")
            # 4 December: the New term run has seated the next House; Ann Lost and
            # Cy Mover's House number are former members of 2025-2026.
            put("meta.json", {"terms": ["2027-2028", "2025-2026"]})
            put("legislators.json", [
                mem("12", "Stays", "Bo", "H", "Belknap", "1", "R", "bo-stays-belk-1"),
                mem("21", "New", "Nan", "H", "Belknap", "1", "D", "nan-new-belk-1"),
                mem("22", "Next", "Dee", "H", "Belknap", "2", "D", "dee-next-belk-2"),
                mem("31", "Mover", "Cy", "S", "", "1", "D", "cy-mover-sd-1")])
            served = {"served": {"first": "1/8/2025", "last": "6/30/2026", "terms": ["2025-2026"]},
                      "former": True}
            put("former.json", [mem("11", "Lost", "Ann", "H", "Belknap", "1", "R", "ann-lost-belk-1",
                                    **served),
                                mem("13", "Mover", "Cy", "H", "Belknap", "2", "D", "cy-mover-belk-2",
                                    **served),
                                mem("14", "Seat", "Sy", "S", "", "1", "R", "sy-seat-sd-1", **served)])
            got["4 Dec"] = night("2026-12-04")
            # Requests of the session after (2028's, filed from September 2027) are
            # sitting members' alone: a name only a member gone in 2026 has links nobody.
            got["2028"] = (sorted(L.not_returning(site, str(coll), year=2028)[0]),
                           L._fold("Ann Lost") in L.roster(site, str(coll), 2028),
                           L._fold("Ann Lost") in L.roster(site, str(coll), 2027))
        finally:
            os.chdir(was_cwd)
            if was_day is None:
                os.environ.pop("GRANITE_BUILD_DATE", None)
            else:
                os.environ["GRANITE_BUILD_DATE"] = was_day
    for day in ("1 Dec", "2 Dec", "3 Dec"):
        gone, dropped, kept = got[day]
        assert gone == ["ann-lost-belk-1", "sy-seat-sd-1"], (day, "not returning", gone)
        assert dropped == ["LSR 2027-0001"], (day, "dropped", dropped)
        assert sorted(kept) == ["LSR 2027-0002", "LSR 2027-0003", "LSR 2027-0004"], (day, sorted(kept))
    gone, dropped, kept = got["4 Dec"]
    assert dropped == ["LSR 2027-0001"], ("after the New term run the withdrawn request of a member who "
                                          "lost is not dropped", dropped, gone)
    assert "ann-lost-belk-1" in gone and "cy-mover-sd-1" not in gone, gone
    assert sorted(kept) == ["LSR 2027-0002", "LSR 2027-0003", "LSR 2027-0004"], sorted(kept)
    assert kept["LSR 2027-0004"]["sponsor_slug"] == "cy-mover-sd-1", (
        "the request of the representative now in the Senate is not his Senate page's",
        kept["LSR 2027-0004"]["sponsor_slug"])
    standing = kept["LSR 2027-0003"]
    assert standing["sponsor_slug"] == "ann-lost-belk-1" and standing["sponsor_label"] == "Ann Lost (R)", (
        "a departed member's standing request is not linked to their page, or names a seat they left",
        standing["sponsor_slug"], standing["sponsor_label"])
    assert got["2028"] == ([], False, True), (
        "a member gone in 2026 is matched to, or dropped from, the requests of 2028", got["2028"])
    return "ok", ("LSR 2027-0001 of a member who lost dropped on 1 and 2 December with the file, on 3 "
                  "December without it, and on 4 December by the new roster; the returning member's and the new "
                  "senator's withdrawn and the standing one kept, the last linked to the member who "
                  "left by name and party")


@check("build", "the request list's Sponsors column is read as a prime sponsor and co-sponsors: the one "
                "marked Prime first, each other name a co-sponsor, wherever it stands")
def _lsr_sponsors_split():
    """The owner, 15 November 2026: the site must stay up to date through the refactor, "including
    adding bill text from LSR drafts and co-sponsors once those are public". Every request carries one
    name today, so fetch_lsrs.split_sponsors has never met a list; it splits the column on semicolons
    and takes the name marked (Prime) as the prime sponsor. Held: one name; a prime and two
    co-sponsors; the prime written last; no mark at all (the first name is the prime); and no name
    keeps its role mark. The data check below says, on the night, when a list is not split."""
    FL = imp("fetch_lsrs")
    cases = {"Ellen Read (Prime)": ("Ellen Read", []),
             "Ellen Read (Prime); Bob Roe; Jane Doe": ("Ellen Read", ["Bob Roe", "Jane Doe"]),
             "Bob Roe; Jane Doe (Prime)": ("Jane Doe", ["Bob Roe"]),
             "Bob Roe;Jane Doe": ("Bob Roe", ["Jane Doe"]), "": ("", [])}
    got = {k: FL.split_sponsors(k) for k in cases}
    bad = {k: v for k, v in got.items() if tuple(v) != cases[k] and list(v) != list(cases[k])}
    assert not bad, f"split_sponsors reads {bad}"
    assert not any(LSR_LISTLIKE.search(n) for p, co in got.values() for n in [p, *co] if n), (
        f"a name kept a separator or its role mark: {got}")
    return "ok", "one name; a prime and co-sponsors, in either order; no mark; no name keeps a separator"


@check("build", "a request's text is read from the list where it links one: a link column of the CSV, "
                "or a link in the request's own row of the page of every request, the General Court's "
                "own address only; and co-sponsors parted by commas or with the role first are split")
def _lsr_text_links():
    """The owner, 17 November 2026: "the bill text shows as a PDF on the lsr search page along with
    the co-sponsors". Until then fetch_lsrs read no link at all: the CSV's four columns carry none,
    and the results page was read only where the CSV failed. Nobody has seen the link yet, so both
    places are read and nothing is constructed (fetch_lsrs, THE TEXT, ONCE IT IS PUBLIC). Held, on a
    page made here in the shape the fallback's reader was written from (a table row a request):
    a row with one link that names the text gives it -- by its address (billText.aspx with
    txtFormat=pdf) or its words (Bill Text) -- and a sponsor's link in the same row is not one; a
    row with no link gives none; another host's PDF is not taken; a row with two such links, or
    naming two requests, gives none. The search page's own link to the page of every request is
    the one asked for (on the page saved on 18 September where it is here), never the withdrawn
    list's. A CSV with a link column carries it, the General Court's alone. And the Sponsors forms
    nobody has seen: commas after a role mark, a Jr. kept with its name, the role before the
    name; a comma with no role mark parts nothing."""
    FL = imp("fetch_lsrs")
    row = "<tr><td>{n}</td><td>HB</td><td>Title: t. Sponsors: (Prime) {who}{links}</td></tr>"
    me = '<a href="/house/members/member.aspx?member=1">Ellen Read</a>'
    # Words before the table naming another request belong to no row.
    page = "<p>The newest request is 2027-0312.</p><table>" + "".join([
        row.format(n="2027-0001", who=me, links=' <a href="/lsr_search/billText.aspx?sy=2027&amp;id=11'
                                              '&amp;txtFormat=pdf&amp;v=current">View</a>'),
        row.format(n="2027-0002", who="Bob Roe", links=' <a href="view.aspx?lsr=2027-0002">Bill Text</a>'),
        row.format(n="2027-0003", who="Bob Roe", links=""),
        row.format(n="2027-0004", who="Bob Roe", links=' <a href="https://example.org/x.pdf">PDF</a>'),
        row.format(n="2027-0005", who="Bob Roe", links=' <a href="/a.pdf">PDF</a> <a href="/b.pdf">PDF</a>'),
        row.format(n="2027-0006 and 2027-0007", who="Bob Roe", links=' <a href="/c.pdf">PDF</a>'),
        row.format(n="2027-0008", who="Bob Roe", links=' <a href="javascript:__doPostBack(&#39;x&#39;)">PDF</a>'),
    ]) + "</table>"
    links, twice = FL.text_links(page, "https://gc.nh.gov/lsr_search/LSR_Results.aspx")
    assert links == {
        "2027-0001": "https://gc.nh.gov/lsr_search/billText.aspx?sy=2027&id=11&txtFormat=pdf&v=current",
        "2027-0002": "https://gc.nh.gov/lsr_search/view.aspx?lsr=2027-0002"}, f"text_links read {links}"
    assert twice == ["2027-0005"], f"a row with two links to a text was not set aside: {twice}"
    assert FL.text_links("<p>2027-0001 <a href='/a.pdf'>PDF</a></p>")[0] == {}, \
        "a page with no table rows gave a link"
    search = ('<a href="LSR_Results.aspx" class="link-primary">Click here</a> to see all Bill Requests | '
              '<a href="lsr_results.aspx?i=1">View Withdrawn LSRs</a>')
    assert FL.results_link(search) == "https://gc.nh.gov/lsr_search/LSR_Results.aspx", \
        FL.results_link(search)
    assert FL.results_link('<a href="lsr_results.aspx?i=1">View Withdrawn LSRs</a>') is None, \
        "the withdrawn list was taken for the page of every request"
    saved = Path("archive/lsr_search.html")
    real = ""
    if saved.is_file():
        assert FL.results_link(saved.read_text(encoding="utf-8", errors="replace")) == \
            "https://gc.nh.gov/lsr_search/LSR_Results.aspx", "the saved search page's own link is not found"
        real = "; the saved search page's own link found"
    csv_text = ("LSR Number,Bill Type,LSR Title,Sponsors,Bill Text PDF\n"
                "2027-0001,HB,t.,Ellen Read (Prime),https://gc.nh.gov/x/1.pdf\n"
                "2027-0002,HB,u.,Bob Roe (Prime),\n"
                "2027-0003,HB,v.,Bob Roe (Prime),https://example.org/y.pdf\n")
    got = {r["lsr"]: r.get("text_pdf", "") for r in FL.parse_csv(csv_text)}
    assert got == {"2027-0001": "https://gc.nh.gov/x/1.pdf", "2027-0002": "", "2027-0003": ""}, got
    four = FL.parse_csv("LSR Number,Bill Type,LSR Title,Sponsors\n2027-0001,HB,t.,Ellen Read (Prime)\n")
    assert "text_pdf" not in four[0], f"the CSV of four columns gave a link: {four}"
    cases = {"Ellen Read (Prime), Bob Roe, Jane Doe": ("Ellen Read", ["Bob Roe", "Jane Doe"]),
             "Ellen Read (Prime), Bob Roe, Jr., Jane Doe (Co-sponsor)": ("Ellen Read", ["Bob Roe Jr.", "Jane Doe"]),
             "(Prime) Ellen Read; (Co) Bob Roe": ("Ellen Read", ["Bob Roe"]),
             "(Co) Bob Roe; (Prime) Ellen Read": ("Ellen Read", ["Bob Roe"]),
             "Roe, Bob (Prime)": ("Roe, Bob", [])}
    split = {k: FL.split_sponsors(k) for k in cases}
    bad = {k: v for k, v in split.items() if (v[0], list(v[1])) != (cases[k][0], list(cases[k][1]))}
    assert not bad, f"split_sponsors reads {bad}"
    return "ok", ("a row's one link to its text taken, by its address or its words; none for a row without, "
                  "another host, two links or two requests; the page of every request is the search page's "
                  f"own link{real}; a CSV link column read; commas after a role mark and a role first split")


# The page of every request in the shape of the owner's printout of 23 November 2026 (fetch_lsrs,
# AND THE REQUESTS THE CSV DOES NOT HOLD): (number, kind, title, prime, [co-sponsors]) a row.
_LSR_PAGE = [
    ("2027-0001", "HB", "relative to required Holocaust and genocide study requirements for an adequate "
                        "public education.", "Ellen Read", []),
    ("2027-0008", "HB", "relative to PFAS facility liability.", "Nancy Murphy",
     ["David Watters", "Rosemarie Rung", "Wendy Thomas"]),
    ("2027-0400", "HJR", "urging Congress to keep the Old Man's profile on the quarter.", "Bob Roe Jr.",
     ["Jane Doe"]),
    ("2027-1570", "HB", "relative to the scope and disclosure requirements of the state right-to-know law.",
     "Jake Abuhav", []),
]


def _lsr_page(rows, count=None, markup="grid", head=True):
    """The page of every request made here from `rows` (_LSR_PAGE's shape): "LSR's Found: N" (`count`,
    else as many as there are; none where `head` is false), then the rows, then the page's foot. A
    grid of linked names, the prime's comma set apart as the printout prints it (" Nancy Murphy ,
    David Watters"), a link to a text after one title; a table of plain words; or each row twice,
    for a phone and for a desktop."""
    import html as _h

    def who(n):
        # "Bob Roe Jr." is printed with its comma, as a name of that form would be.
        n = n.replace(" Jr.", ", Jr.")
        return f'<a href="/house/members/member.aspx?pid={len(n)}">{_h.escape(n)}</a>'
    out = []
    for num, kind, title, prime, co in rows:
        if markup == "table":
            names = "(Prime) " + ", ".join([prime.replace(" Jr.", ", Jr."), *co])
            out.append(f"<tr><td>{num}</td><td>{kind}</td><td>Title: {_h.escape(title)}<br>"
                       f"Sponsors: {_h.escape(names)}</td></tr>")
            continue
        text = (' <a href="/lsr_search/billText.aspx?sy=2027&amp;id=1&amp;txtFormat=pdf">PDF</a>'
                if num == "2027-0001" else "")
        names = who(prime) + (" , " + ", ".join(who(c) for c in co) if co else "") if prime else ""
        out.append(f'<div class="row border-top py-3">\n  <div class="col-md-2">{num}</div>\n'
                   f'  <div class="col-md-1">{kind}</div>\n  <div class="col-md-9">\n'
                   f'    <div class="row"><div class="col-2"><b>Title:</b></div>\n'
                   f'      <div class="col-10">{_h.escape(title)}{text}</div></div>\n'
                   f'    <div class="row"><b>Sponsors:</b> <b>(Prime)</b> {names}</div>\n  </div>\n</div>')
    body = "\n".join(out)
    if markup == "table":
        body = f"<table>{body}</table>"
    if markup == "twice":
        body = f'<div class="d-md-none">{body}</div><div class="d-none d-md-block">{body}</div>'
    found = (f'<div>LSR&#39;s Found:&nbsp; <b><span id="pageBody_lblCount">'
             f'{len(rows) if count is None else count}</span></b></div>' if head else "")
    return (f'<html><head><script>var x = "2027-0001 HB Title: none";</script></head><body>'
            f'<a href="LSR_Search.aspx">New Query</a>{found}\n{body}\n'
            '<footer><a class="footer-link" href="/committee_of_conference/">Committees of Conference</a>\n'
            '<a class="footer-link" href="/downloads/">Downloads</a> Session 2027-2028 &copy; 2026</footer>'
            '</body></html>')


@check("build", "the page of every request is read for its rows: the number, the kind, the title, the "
                "prime sponsor first and the co-sponsors after, up to the page's foot; and used only "
                "when as many are read as the page says it lists, each whole",
       needs=("fetch_lsrs",))
def _lsr_page_rows(FL):
    """AND THE REQUESTS THE CSV DOES NOT HOLD (fetch_lsrs; the night of 23 November 2026: the CSV
    held 908 requests, the page of every request listed 1,264). Nobody here has seen the page's
    HTML: the owner printed it, and its reader (page_listed) was written from the printout. Held,
    on pages made here in the printout's shape (_lsr_page) -- "LSR's Found: 4", then rows of the
    number, the kind, "Title:" and the title, "Sponsors: (Prime)" and the names parted by commas
    -- in three markups, a grid of linked names, a table of plain words, and each row printed
    twice for a phone and a desktop: the four rows read exactly, an HJR among them, the
    co-sponsors after the prime, a Jr. kept with its name, a link to a text kept out of the
    title, and the last row's names stopping at the page's foot. And never a page misread: one
    saying 5 with 4 read, one stating no count, a row with no sponsor, a request printed twice
    differently, and a page of no rows each give no rows, and say why."""
    want = [{"lsr": n, "session": 2027, "body": k, "title": t, "sponsor": p, "cosponsors": co,
             "withdrawn": False} for n, k, t, p, co in _LSR_PAGE]
    for markup in ("grid", "table", "twice"):
        got, why = FL.page_listed(_lsr_page(_LSR_PAGE, markup=markup))
        assert (got, why) == (want, ""), f"the {markup} page read as {got or why}"
    assert FL.parse_results_html(_lsr_page(_LSR_PAGE)) == want, "the fallback's reader is not page_listed"
    for page, said in (
            (_lsr_page(_LSR_PAGE, count=5), "it says 5 and 4 could be read"),
            (_lsr_page(_LSR_PAGE, head=False), "it states no count to check its rows against"),
            (_lsr_page([*_LSR_PAGE[:1], ("2027-0008", "HB", "t.", "", []), *_LSR_PAGE[2:]]),
             "1 of its rows could not be read: 2027-0008"),
            (_lsr_page([*_LSR_PAGE, ("2027-0001", "HB", "another title.", "Ellen Read", [])], count=4),
             "1 of its rows could not be read: 2027-0001"),
            ("<html><body><p>No LSRs were found.</p></body></html>", "no request could be read off it")):
        got, why = FL.page_listed(page)
        assert (got, why) == ([], said), f"a page misread was used, or said otherwise: {got[:1]} {why!r}"
        assert FL.parse_results_html(page) == [], "the fallback took the rows of a page misread"
    return "ok", ("4 rows read exactly in three markups, an HJR, co-sponsors after the prime, a Jr., "
                  "a text's link out of the title, the last row's names ending at the foot; a page "
                  "saying 5, stating no count, with a row of no sponsor or a request twice differently, "
                  "or of no rows, gives none and says why")


@check("build", "the night takes each request the page of every request lists and the CSV does not, "
                "keeps every CSV row as the CSV gives it but for the page's co-sponsors, takes nothing "
                "from a page that does not add up, keeps a request taken from the page as it stood on a "
                "night the page cannot be used, and says how many the CSV held, the page listed and "
                "were taken from it",
       needs=("fetch_lsrs",))
def _lsr_page_rows_taken(FL):
    """AND THE REQUESTS THE CSV DOES NOT HOLD (fetch_lsrs). Driven through main() in a throwaway
    folder, the search page, the CSV and the page of every request answered here (get and post
    replaced, urlopen raising), each night from the lsrs.json the last left:

      - a CSV of 3 and a page of 5 holding them, one printed otherwise than the CSV prints it: 5
        requests, the 2 the CSV lacks taken from the page with their co-sponsors and "from_page",
        the CSV's 3 as the CSV gives them but for the page's co-sponsors (AND THE CO-SPONSORS THE
        PAGE NAMES, _lsr_page_cosponsors_taken); the line says 3, 5, 2 and the 2 with co-sponsors;
      - a CSV with a column linking a text: the page is read all the same;
      - a page listing fewer, all of them in the CSV: the CSV's list, none taken;
      - a page misread (it says 6): the CSV's 3, the 2 taken the night before kept as they stood
        and not withdrawn, and the line says why; a page read that no longer lists one of the 2
        withdraws it; a CSV that lists the other makes it the CSV's, "from_page" gone;
      - a page of no rows on a first night: the CSV's list exactly, and said.
    """
    import contextlib
    import io
    import time
    import types
    import urllib.request
    import refusal
    here = os.getcwd()
    saved = (refusal.MARK, refusal.LOCK, FL.get, FL.post, FL.time, sys.argv, urllib.request.urlopen)
    tmp = Path(tempfile.mkdtemp(prefix="gr-lsrpage-"))
    search = ('<a href="LSR_Results.aspx" class="link-primary">Click here</a> to see all Bill Requests '
              '<a id="pageBody_lnkCVS" href="javascript:__doPostBack(&#39;ctl00$pageBody$lnkCVS&#39;,'
              '&#39;&#39;)">Download CSV File</a>'
              + "".join(f'<input type="hidden" name="{f}" id="{f}" value="x" />' for f in FL.HIDDEN))
    csv3 = ("LSR Number,Bill Type,LSR Title,Sponsors\n2027-0001,HB,t one.,Ellen Read (Prime)\n"
            "2027-0002,HB,t two.,Bob Roe (Prime)\n2027-0003,SB,t three.,Jane Doe (Prime)\n")
    page5 = [("2027-0001", "HB", "t one.", "Ellen Read", []),
             ("2027-0002", "HB", "t two, as the page prints it.", "Bob Roe", ["Ann Two"]),
             ("2027-0003", "SB", "t three.", "Jane Doe", []),
             ("2027-0004", "HB", "t four.", "Nancy Murphy", ["David Watters", "Wendy Thomas"]),
             ("2027-0005", "CACR", "t five.", "Ann Lee", [])]
    night = {}

    def get(url, timeout=60):
        return (search if url == FL.SEARCH else night["page"]).encode("utf-8"), "utf-8"

    def post(url, fields, timeout=90):
        return night["csv"].encode("utf-8"), "utf-8", "text/csv", "attachment; filename=lsr.csv"

    def run(csv_text, page):
        night.update(csv=csv_text, page=page)
        sys.argv = ["fetch_lsrs.py"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = FL.main()
        rows = {r["lsr"]: r for r in json.loads(Path("lsrs.json").read_text(encoding="utf-8"))}
        said = [ln.strip()[len(FL.LISTED):] for ln in out.getvalue().splitlines()
                if ln.strip().startswith(FL.LISTED)]
        return rc, rows, said[-1] if said else ""

    def raiser(*a, **k):
        raise AssertionError("the request list's fetch opened a connection")
    csv_rows = {r["lsr"]: r for r in FL.parse_csv(csv3)}
    # The CSV's rows as the night keeps them: the page's co-sponsors on the one it names some for.
    paged = {k: dict(r, cosponsors=["Ann Two"]) if k == "2027-0002" else r for k, r in csv_rows.items()}
    try:
        os.chdir(tmp)
        Path("archive").mkdir()
        refusal.MARK, refusal.LOCK = tmp / "archive" / "refused.json", tmp / "archive" / ".lock"
        FL.get, FL.post = get, post
        FL.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time, strftime=time.strftime)
        urllib.request.urlopen = raiser
        rc, rows, said = run(csv3, _lsr_page(page5))
        assert rc == 0 and said == ("the CSV held 3, the page listed 5, 2 taken from the page, 2 with "
                                    "co-sponsors from it"), (rc, said)
        assert sorted(rows) == [f"2027-000{n}" for n in range(1, 6)] and \
            not any(r["withdrawn"] for r in rows.values()), f"not the 5 requests of CSV and page: {sorted(rows)}"
        assert {k: r for k, r in rows.items() if k in csv_rows} == paged, \
            "a CSV row was dropped, or changed for the page in more than its co-sponsors"
        assert rows["2027-0004"] == {"lsr": "2027-0004", "session": 2027, "body": "HB", "title": "t four.",
                                     "sponsor": "Nancy Murphy", "cosponsors": ["David Watters", "Wendy Thomas"],
                                     "withdrawn": False, "from_page": True}, rows["2027-0004"]
        Path("lsrs.json").unlink()
        rc, rows, said = run(csv3.replace("Sponsors\n", "Sponsors,Bill Text PDF\n")
                             .replace("(Prime)\n2027-0002", "(Prime),https://gc.nh.gov/x/1.pdf\n2027-0002"),
                             _lsr_page(page5))
        assert said == ("the CSV held 3, the page listed 5, 2 taken from the page, 2 with co-sponsors "
                        "from it") and len(rows) == 5, ("with a text linked in the CSV the page was not read", said)
        Path("lsrs.json").unlink()
        rc, rows, said = run(csv3, _lsr_page(page5[:2]))
        assert rows == paged and said == ("the CSV held 3, the page listed 2, 0 taken from the page, 1 with "
                                          "co-sponsors from it"), (rows, said)
        Path("lsrs.json").unlink()
        run(csv3, _lsr_page(page5))
        rc, rows, said = run(csv3, _lsr_page(page5, count=6))
        assert said == ("the CSV held 3, the page could not be used (it says 6 and 5 could be read), none "
                        "taken from it; 2 taken from it before kept as they stood; 1 kept their co-sponsors "
                        "as they stood"), said
        assert not rows["2027-0004"]["withdrawn"] and not rows["2027-0005"]["withdrawn"] and \
            rows["2027-0004"]["from_page"], ("a request taken from the page was withdrawn on a night "
                                             "the page could not be used", rows["2027-0004"])
        rc, rows, said = run(csv3, _lsr_page([*page5[:3], page5[4]]))
        assert rows["2027-0004"]["withdrawn"] and not rows["2027-0005"]["withdrawn"], \
            "a request the page read no longer lists was not withdrawn"
        rc, rows, said = run(csv3 + "2027-0005,CACR,t five from the CSV.,Ann Lee (Prime)\n",
                             _lsr_page([*page5[:3], page5[4]]))
        assert rows["2027-0005"]["title"] == "t five from the CSV." and "from_page" not in rows["2027-0005"], \
            ("a request the CSV lists is not the CSV's", rows["2027-0005"])
        assert said == "the CSV held 4, the page listed 4, 0 taken from the page, 1 with co-sponsors from it", said
        Path("lsrs.json").unlink()
        rc, rows, said = run(csv3, "<html><body><p>No LSRs were found.</p></body></html>")
        assert rows == csv_rows and said == ("the CSV held 3, the page could not be used (no request could "
                                             "be read off it), none taken from it"), (rows, said)
    finally:
        os.chdir(here)
        (refusal.MARK, refusal.LOCK, FL.get, FL.post, FL.time, sys.argv, urllib.request.urlopen) = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a CSV of 3 and a page of 5: 5, the 2 from the page with co-sponsors, the CSV's 3 as it "
                  "gives them but for the page's co-sponsors, said 3, 5, 2 and 2 with co-sponsors; the page "
                  "read beside a CSV linking a text; a page of fewer leaves the CSV's list; a page misread "
                  "takes none and keeps the 2 taken before and the co-sponsors; a page read withdraws one "
                  "it dropped; the CSV's row wins; a page of no rows said")


@check("build", "a request the CSV holds takes the co-sponsors the page of every request names for it, in "
                "the page's order, and keeps them on a night the page says nothing of it; one the page "
                "names none for has none, and the page naming the CSV's prime among them gives none",
       needs=("fetch_lsrs",))
def _lsr_page_cosponsors_taken(FL):
    """AND THE CO-SPONSORS THE PAGE NAMES (fetch_lsrs; the owner, 24 November 2026: "Yes, take
    them"). The CSV's Sponsors column names a request's prime sponsor alone; the page names the
    co-sponsors of 95 on the owner's printout of 23 November, 2027-0008 Nancy Murphy's with David
    Watters, Rosemarie Rung and Wendy Thomas (_LSR_PAGE, the fixture's rows). Driven through
    main() as _lsr_page_rows_taken drives it, on a CSV holding the fixture's four requests, each
    night from the lsrs.json the last left:

      - a first night with no page (the search page links none): every row as the CSV gives it,
        no co-sponsor anywhere;
      - the page read: 2027-0008 has its three, in the page's order, the HJR its one, 2027-0001
        none, every other field the CSV's; the line says 2 with co-sponsors;
      - the page not read, then misread: each keeps its co-sponsors, and the line says so;
      - the page read naming 2027-0008 with none: it has none; and a page whose row names the
        CSV's prime sponsor among the co-sponsors: that request keeps the CSV's none, said."""
    import contextlib
    import io
    import time
    import types
    import urllib.request
    import refusal
    here = os.getcwd()
    saved = (refusal.MARK, refusal.LOCK, FL.get, FL.post, FL.time, sys.argv, urllib.request.urlopen)
    tmp = Path(tempfile.mkdtemp(prefix="gr-lsrco-"))
    form = ('<a id="pageBody_lnkCVS" href="javascript:__doPostBack(&#39;ctl00$pageBody$lnkCVS&#39;,'
            '&#39;&#39;)">Download CSV File</a>'
            + "".join(f'<input type="hidden" name="{f}" id="{f}" value="x" />' for f in FL.HIDDEN))
    linked = '<a href="LSR_Results.aspx" class="link-primary">Click here</a> to see all Bill Requests ' + form
    csv4 = "LSR Number,Bill Type,LSR Title,Sponsors\n" + "".join(
        f'{n},{k},"{t}",{p} (Prime)\n' for n, k, t, p, _co in _LSR_PAGE)
    night = {}

    def get(url, timeout=60):
        return (night["search"] if url == FL.SEARCH else night["page"]).encode("utf-8"), "utf-8"

    def post(url, fields, timeout=90):
        return csv4.encode("utf-8"), "utf-8", "text/csv", "attachment; filename=lsr.csv"

    def run(page, search=linked):
        night.update(search=search, page=page)
        sys.argv = ["fetch_lsrs.py"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = FL.main()
        assert rc == 0, out.getvalue()[-400:]
        rows = {r["lsr"]: r for r in json.loads(Path("lsrs.json").read_text(encoding="utf-8"))}
        said = [ln.strip()[len(FL.LISTED):] for ln in out.getvalue().splitlines()
                if ln.strip().startswith(FL.LISTED)]
        return rows, said[-1] if said else ""

    def raiser(*a, **k):
        raise AssertionError("the request list's fetch opened a connection")
    csv_rows = {r["lsr"]: r for r in FL.parse_csv(csv4)}
    co = {n: list(c) for n, _k, _t, _p, c in _LSR_PAGE}
    try:
        os.chdir(tmp)
        Path("archive").mkdir()
        refusal.MARK, refusal.LOCK = tmp / "archive" / "refused.json", tmp / "archive" / ".lock"
        FL.get, FL.post = get, post
        FL.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time, strftime=time.strftime)
        urllib.request.urlopen = raiser
        assert all(r["cosponsors"] == [] for r in csv_rows.values()) and len(csv_rows) == 4, (
            "the fixture's CSV names a co-sponsor, or not its four requests")
        rows, said = run(None, search=form)
        assert rows == csv_rows and "the page was not read" in said and "kept their co-sponsors" not in said, (
            "a first night with no page is not the CSV's list exactly", said)
        rows, said = run(_lsr_page(_LSR_PAGE))
        assert rows["2027-0008"]["cosponsors"] == ["David Watters", "Rosemarie Rung", "Wendy Thomas"], (
            f"2027-0008's co-sponsors read {rows['2027-0008']['cosponsors']}, not the page's three in its order")
        assert {k: r["cosponsors"] for k, r in rows.items()} == co and \
            {k: {f: v for f, v in r.items() if f != "cosponsors"} for k, r in rows.items()} == \
            {k: {f: v for f, v in r.items() if f != "cosponsors"} for k, r in csv_rows.items()}, (
            "the page's co-sponsors are not each request's, or the page changed more of a CSV row")
        assert said == "the CSV held 4, the page listed 4, 0 taken from the page, 2 with co-sponsors from it", said
        for page, why in ((None, "the page was not read"), (_lsr_page(_LSR_PAGE, count=9),
                                                             "the page could not be used")):
            rows, said = run(page, search=form if page is None else linked)
            assert {k: r["cosponsors"] for k, r in rows.items()} == co and why in said \
                and said.endswith("; 2 kept their co-sponsors as they stood"), (
                f"on a night {why}, a request lost its co-sponsors, or the line did not say it kept them", said)
        none = [(n, k, t, p, [] if n == "2027-0008" else c) for n, k, t, p, c in _LSR_PAGE]
        rows, said = run(_lsr_page(none))
        assert rows["2027-0008"]["cosponsors"] == [] and rows["2027-0400"]["cosponsors"] == ["Jane Doe"] \
            and said.endswith(", 1 with co-sponsors from it"), (
            "a request the page lists with no co-sponsors kept the ones it had", rows["2027-0008"], said)
        odd = [(n, k, t, "Ann Other", [p]) if n == "2027-1570" else (n, k, t, p, c) for n, k, t, p, c in _LSR_PAGE]
        rows, said = run(_lsr_page(odd))
        assert rows["2027-1570"]["cosponsors"] == [] and rows["2027-1570"]["sponsor"] == "Jake Abuhav" \
            and "(1 naming the CSV's prime sponsor among them left as the CSV gives them: 2027-1570)" in said, (
            "a page naming the CSV's prime sponsor as a co-sponsor gave that request co-sponsors", said)
    finally:
        os.chdir(here)
        (refusal.MARK, refusal.LOCK, FL.get, FL.post, FL.time, sys.argv, urllib.request.urlopen) = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("no page, the CSV's four exactly; the page read, 2027-0008's three in the page's order and "
                  "the HJR's one, nothing else of a row changed, said; not read and misread, both kept and "
                  "said; listed with none, none; the CSV's prime among them, none taken and said")


@check("build", "a request's co-sponsors are matched by the prime sponsor's rules in either chamber: each "
                "one certain is a person with their label, party, chamber and page, in the page's order; a "
                "name matching nobody, or two people, is kept as printed; a request with none is unchanged",
       needs=("build_lsrs",))
def _request_cosponsors_matched(build_lsrs):
    """build_lsrs.rows_from, co_match (the owner, 24 November 2026: "Yes, take them", of the
    co-sponsors the results page names). A request is filed in its prime sponsor's chamber and
    co-sponsored from both: on the owner's printout, 58 of the 345 co-sponsor names were of the
    other chamber (Sen. David Watters on 2027-0008, a House request), and the prime sponsor's rule,
    which looks for a sponsor in the request's chamber alone, matched none of them. Held on the
    fixture's rows (_LSR_PAGE) and one request more, with a roster and two elections' winners of the
    shapes roster() and election_winners give:

      - 2027-0008: David Watters a sitting senator, Rosemarie Rung and Wendy Thomas sitting
        representatives, in the page's order, each with label, page, party and chamber, the names
        as printed in `cosp`, and the prime sponsor's chamber on the row;
      - the HJR's Jane Doe, whom nobody has, as printed: no page, no party, no chamber;
      - a winner the roster has not (Jim Creighton, a sitting representative elected senator) by
        the whole name; a winner by the prime sponsor's middle-name rule in the one chamber that
        has her (Mary Raven, printed Mary Beth Raven); and Sam Lee, whom that rule finds in both
        chambers, and Pat Moore, two sitting members, are nobody;
      - 2027-0001, with none, is the row it was: no co-sponsor key and no chamber."""
    L = build_lsrs
    who = {"nancymurphy": ("Rep. Nancy Murphy (D)", "nancy-murphy-hills-12", "H"),
           "davidwatters": ("Sen. David Watters (D)", "david-watters-sd-4", "S"),
           "rosemarierung": ("Rep. Rosemarie Rung (D)", "rosemarie-rung-hills-12", "H"),
           "wendythomas": ("Rep. Wendy Thomas (D)", "wendy-thomas-hills-12", "H"),
           "ellenread": ("Rep. Ellen Read (D)", "ellen-read-rock-10", "H"),
           "jakeabuhav": ("Rep. Jake Abuhav (R)", "jake-abuhav-rock-21", "H"),
           # Two sitting members of one name: roster() keeps neither.
           "patmoore": None}
    winners = [{"name": "Jim Creighton", "names": ["Jim Creighton", "James Creighton"], "party": "R",
                "chamber": "S", "race": "S|8", "slug": "james-creighton-hills-30",
                "label": "Sen.-elect Jim Creighton (R)"},
               {"name": "Mary Beth Raven", "names": ["Mary Beth Raven"], "party": "D", "chamber": "H",
                "race": "H|Hillsborough|1", "slug": "", "label": "Rep.-elect Mary Beth Raven (D)"},
               {"name": "Sam Q. Lee", "names": ["Sam Q. Lee"], "party": "R", "chamber": "H",
                "race": "H|Belknap|2", "slug": "sam-lee-belk-2", "label": "Rep.-elect Sam Q. Lee (R)"},
               {"name": "Sam R. Lee", "names": ["Sam R. Lee"], "party": "D", "chamber": "S",
                "race": "S|3", "slug": "sam-lee-sd-3", "label": "Sen.-elect Sam R. Lee (D)"}]
    lsrs = [{"lsr": n, "session": 2027, "body": k, "title": t, "sponsor": p, "cosponsors": list(c),
             "withdrawn": False} for n, k, t, p, c in _LSR_PAGE]
    lsrs.append({"lsr": "2027-0900", "session": 2027, "body": "SB", "title": "relative to coves.",
                 "sponsor": "David Watters", "withdrawn": False,
                 "cosponsors": ["Jim Creighton", "Mary Raven", "Sam Lee", "Pat Moore"]})
    rows, _ = L.rows_from(lsrs, who, year=2027, winners=winners)
    by = {r["n"][4:]: r for r in rows}
    want = [{"label": "Sen. David Watters (D)", "slug": "david-watters-sd-4", "name": "David Watters",
             "party": "D", "chamber": "S"},
            {"label": "Rep. Rosemarie Rung (D)", "slug": "rosemarie-rung-hills-12", "name": "Rosemarie Rung",
             "party": "D", "chamber": "H"},
            {"label": "Rep. Wendy Thomas (D)", "slug": "wendy-thomas-hills-12", "name": "Wendy Thomas",
             "party": "D", "chamber": "H"}]
    r8 = by["2027-0008"]
    assert r8.get("cosponsors") == want, f"2027-0008's co-sponsors are {r8.get('cosponsors')}"
    assert r8.get("cosp") == ["David Watters", "Rosemarie Rung", "Wendy Thomas"] \
        and r8.get("sponsor_chamber") == "H" and r8["sponsor_slug"] == "nancy-murphy-hills-12", (
        f"2027-0008's names or its prime sponsor's chamber: {r8.get('cosp')} {r8.get('sponsor_chamber')}")
    assert by["2027-0400"]["cosponsors"] == [{"label": "Jane Doe", "slug": "", "name": "Jane Doe"}], (
        f"a name nobody has is not kept as printed: {by['2027-0400']['cosponsors']}")
    got = {c["name"]: (c["label"], c["slug"], c.get("party"), c.get("chamber")) for c in by["2027-0900"]["cosponsors"]}
    assert got == {"Jim Creighton": ("Sen.-elect Jim Creighton (R)", "james-creighton-hills-30", "R", "S"),
                   "Mary Raven": ("Rep.-elect Mary Beth Raven (D)", "", "D", "H"),
                   "Sam Lee": ("Sam Lee", "", None, None), "Pat Moore": ("Pat Moore", "", None, None)} \
        and by["2027-0900"].get("sponsor_chamber") == "S", (
        f"a winner by the whole name, one by the middle-name rule in one chamber, and two names of two "
        f"people: {got}, the prime's chamber {by['2027-0900'].get('sponsor_chamber')}")
    one = by["2027-0001"]
    bare, _ = L.rows_from([{k: v for k, v in lsrs[0].items() if k != "cosponsors"}], who, year=2027,
                          winners=winners)
    assert one == bare[0] and not {"cosponsors", "cosp", "sponsor_chamber"} & set(one), (
        f"a request with no co-sponsor carries something new: {sorted(set(one) & {'cosponsors', 'cosp', 'sponsor_chamber'})}")
    return "ok", ("2027-0008's three, a senator and two representatives, in the page's order with label, page, "
                  "party and chamber; Jane Doe as printed; a winner by the whole name and one by the middle-name "
                  "rule in her one chamber; a name of two people nobody; a request with none unchanged")


@check("build", "a request's co-sponsors open its page's and its card's Summary as a bill's sponsors open "
                "its Summary: the prime labelled and first, each chamber under its heading where they are of "
                "both, the count under the chips, no Sponsors tab; a request with none draws as before",
       needs=("build_lsrs", "build_request_pages"))
def _request_sponsors_as_a_bills(build_lsrs, build_request_pages):
    """The owner, 24 November 2026 ("Yes, take them"): a request lists its co-sponsors "as a bill
    does". A bill's page has drawn its sponsors at the top of its Summary since 19 November 2026
    (app.js renderSponsors, _bill_tabs_one_line), with no Sponsors tab; a request's page and card
    had a Sponsors tab and a Co-Sponsors line in the head, drawn for a list that named none until
    now. Held on build_lsrs' rows for the fixture's 2027-0008 (Nancy Murphy, with David Watters,
    a senator, Rosemarie Rung and Wendy Thomas), its HJR (Bob Roe Jr. and Jane Doe, whom nobody
    has) and 2027-0001 (none), on the page build_request_pages writes and the card app.js draws:

      - the page's Summary opens with "Sponsors" (the bill's heading and anchor), then About
        Requests; the chips are Nancy Murphy, labelled Prime, Rosemarie Rung and Wendy Thomas
        under "Representatives 3", then David Watters under "Senators 1", and "4 Sponsors · 4 D"
        under them; Jane Doe drawn as printed, with no party and no link, under "Chamber Not on
        File"; the head names the prime sponsor alone and there is no Sponsors tab;
      - the card's Summary opens with the same section, byte for byte but the anchor, drawn by
        the bill's own renderSponsors, and has no Sponsors tab;
      - 2027-0001's page has Summary and Bill Text, its Summary About Requests alone, and is the
        same page whether its row says no co-sponsor or says nothing of them."""
    import tempfile
    import components as C
    L, RP = build_lsrs, build_request_pages
    who = {"nancymurphy": ("Rep. Nancy Murphy (D)", "nancy-murphy-hills-12", "H"),
           "davidwatters": ("Sen. David Watters (D)", "david-watters-sd-4", "S"),
           "rosemarierung": ("Rep. Rosemarie Rung (D)", "rosemarie-rung-hills-12", "H"),
           "wendythomas": ("Rep. Wendy Thomas (D)", "wendy-thomas-hills-12", "H"),
           "ellenread": ("Rep. Ellen Read (D)", "ellen-read-rock-10", "H")}
    lsrs = [{"lsr": n, "session": 2027, "body": k, "title": t, "sponsor": p, "cosponsors": list(c),
             "withdrawn": False} for n, k, t, p, c in _LSR_PAGE[:3]]
    rows, _ = L.rows_from(lsrs, who, year=2027)
    by = {r["n"][4:]: r for r in rows}
    req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "abbr": L.ABBR}

    def pages(rs):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            (site / "idx").mkdir()
            (site / "bills.html").write_text(_source("src/pages/bills.html"), encoding="utf-8")
            (site / "meta.json").write_text(json.dumps({"requests": req}), encoding="utf-8")
            (site / "idx" / "2027-requests.json").write_text(json.dumps(rs), encoding="utf-8")
            RP.write(site, "https://x")
            return {p.stem: p.read_text(encoding="utf-8") for p in (site / "request").glob("*.html")}
    got = pages(rows)

    def summary(html, rid):
        s = html[html.index(f'id="pane_{rid}_0"'):]
        return s[:s.find('<div class="pane', 10)] if '<div class="pane' in s[10:] else s
    pg, hj, one = got["2027-0008"], got["2027-0400"], got["2027-0001"]
    s8 = summary(pg, "LSR20270008")
    secs = re.findall(r'<section class="w4"( id="[^"]*")?><h2 class="w4h">([^<]*)</h2>', s8)
    assert secs == [(' id="sponsors"', "Sponsors"), (' id="about"', "About Requests")], (
        f"2027-0008's Summary is {secs}, not its Sponsors and then About Requests")
    sec = s8[:s8.index("</section>")]
    chips = re.findall(r'class="mchip p-(\w)" translate="no"><a href="legislator/([^"]+)"', sec)
    assert chips == [("D", "nancy-murphy-hills-12"), ("D", "rosemarie-rung-hills-12"),
                     ("D", "wendy-thomas-hills-12"), ("D", "david-watters-sd-4")], (
        f"the sponsors are not the prime, then the page's order by chamber, the prime's first: {chips}")
    assert re.findall(r'<h3 class="spch">(\w+) <span class="sechn">(\d+)</span>', sec) == [
        ("Representatives", "3"), ("Senators", "1")] \
        and '<i translate="yes">Prime</i>' in sec.split("rosemarie-rung")[0] and sec.count(">Prime</i>") == 1, (
        "the chambers are not headed, or the prime sponsor is not the one labelled Prime")
    assert re.search(r'</div>\s*<p class="spcount">4 Sponsors · <span title="Democrat">4 D</span></p>', sec), (
        "the sponsors' count is not under their chips, as a bill's is")
    hsec = summary(hj, "LSR20270400")
    assert '<span class="mchip p-X" translate="no">Jane Doe</span>' in hsec \
        and re.search(r'<h3 class="spch">Chamber Not on File <span class="sechn">1</span></h3>', hsec), (
        f"a co-sponsor nobody has is not drawn as printed: {hsec[:900]!r}")
    for n, html in got.items():
        head = re.search(r'<dl class="rfacts">.*?</dl>', html, re.S).group(0)
        tabs = re.findall(r'<button[^>]*role="tab"[^>]*>([^<]*)<', html)
        assert "Co-Sponsor" not in head and "Prime Sponsor" in head and tabs == ["Summary", "Bill Text"] \
            and not re.search(r'id="(?:tab|pane)_LSR\d+_4"', html), (
            f"/request/{n} names its co-sponsors in its head, or keeps a Sponsors tab: {tabs}")
    s1 = summary(one, "LSR20270001")
    assert re.findall(r'<section class="w4"( id="[^"]*")?>', s1) == [' id="about"'] and "spcount" not in one \
        and "spch" not in one, "a request with no co-sponsor draws a Sponsors section"
    bare = {k: v for k, v in by["2027-0001"].items() if k not in ("cosponsors", "cosp", "sponsor_chamber")}
    assert pages([bare])["2027-0001"] == one, "a request's page with no co-sponsor depends on how its row says so"
    # THE CARD, in node: the bill's renderSponsors, under the bill's heading, with no anchor.
    js = ("(() => { scope.setMeta({requests: " + json.dumps(req) + "}); const rows = "
          + json.dumps([by["2027-0008"], by["2027-0400"], by["2027-0001"]]) + ";"
          " rows.forEach(r => scope.openCards.add(r.id)); return rows.map(r => scope.lsrCardHtml(r, '')); })()")
    cards = _app_js(js, names=("lsrCardHtml", "openCards", "setMeta: x => (META = x)"))
    if cards is None:
        return "skip", "the pages hold; node, app.js or the stub is not here for the card"
    for (n, rid), card in zip((("2027-0008", "LSR20270008"), ("2027-0400", "LSR20270400"),
                               ("2027-0001", "LSR20270001")), cards):
        page_sec = re.search(r'<section class="w4" id="sponsors">.*?</section>', summary(got[n], rid), re.S)
        card_sec = re.search(r'<section class="w4"><h2 class="w4h">Sponsors</h2>.*?</section>',
                             summary(card, rid), re.S)
        if n == "2027-0001":
            assert not page_sec and not card_sec and 'class="spcount"' not in card, (
                "a card with no co-sponsor draws a Sponsors section")
        else:
            assert page_sec and card_sec and page_sec.group(0).replace(' id="sponsors"', "", 1) == card_sec.group(0), (
                f"{n}'s card does not draw its page's Sponsors: {card_sec and card_sec.group(0)[:700]!r} != "
                f"{page_sec and page_sec.group(0)[:700]!r}")
        assert 'data-t="4"' not in card and C.record_tabs(rid, [["0", "Summary", 0], ["6", "Bill Text", "0"]], "0") \
            in card, f"{n}'s card keeps a Sponsors tab, or not the strip its page has"
    return "ok", ("2027-0008's Summary opens with its Sponsors, the prime labelled and first, Representatives 3 "
                  "then Senators 1, 4 Sponsors · 4 D under them; Jane Doe as printed; no Sponsors tab and the "
                  "head the prime's alone; the card's section the page's byte for byte; a request with none "
                  "drawn as before")


@check("frontend", "in the requests' term, a member's Co-sponsored tab lists the requests that name them "
                   "a co-sponsor, as it lists the bills they co-sponsor, and their Prime sponsored tab their own",
       needs=("build_lsrs",))
def _member_cosponsored_requests(build_lsrs):
    """app.js renderMemberRequests. Until 24 November 2026 a request named its prime sponsor alone,
    and a member's Co-sponsored tab in the requests' term said "A request names only its prime
    sponsor, so none is co-sponsored". Now a request names the co-sponsors the results page names
    (fetch_lsrs), and that sentence would be untrue on the page of every member who co-sponsors
    one. Held on build_lsrs' rows for the fixture's 2027-0008, in node: Wendy Thomas's Co-sponsored
    tab lists its card and says 1 co-sponsored for 2027, her Prime sponsored tab none for 2027;
    Nancy Murphy's Prime sponsored tab lists it as before and her Co-sponsored tab says none is
    co-sponsored for 2027; and the old sentence is nowhere."""
    L = build_lsrs
    who = {"nancymurphy": ("Rep. Nancy Murphy (D)", "nancy-murphy-hills-12", "H"),
           "davidwatters": ("Sen. David Watters (D)", "david-watters-sd-4", "S"),
           "rosemarierung": ("Rep. Rosemarie Rung (D)", "rosemarie-rung-hills-12", "H"),
           "wendythomas": ("Rep. Wendy Thomas (D)", "wendy-thomas-hills-12", "H")}
    n, k, t, p, c = _LSR_PAGE[1]
    rows, _ = L.rows_from([{"lsr": n, "session": 2027, "body": k, "title": t, "sponsor": p,
                            "cosponsors": list(c), "withdrawn": False}], who, year=2027)
    req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "abbr": L.ABBR}
    js = ("(() => { scope.setMeta({requests: " + json.dumps(req) + "}); scope.IDX.length = 0; "
          + "".join(f"scope.IDX.push({json.dumps(r)}); " for r in rows)
          + "scope.LOADED.add('2027-requests'); const her = {slug: 'wendy-thomas-hills-12'}, "
          "prime = {slug: 'nancy-murphy-hills-12'}; return {co: scope.renderMemberRequests(her, false), "
          "own: scope.renderMemberRequests(her, true), filed: scope.renderMemberRequests(prime, true), "
          "none: scope.renderMemberRequests(prime, false)}; })()")
    got = _app_js(js, names=("renderMemberRequests", "IDX", "LOADED", "setMeta: x => (META = x)"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    plain = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()
    assert 'data-id="LSR20270008"' in got["co"] and "1 co-sponsored for 2027." in plain(got["co"]), (
        f"a co-sponsor's Co-sponsored tab does not list the request: {plain(got['co'])[:300]!r}")
    assert plain(got["own"]) == "No bill requests for 2027." and 'data-id="LSR20270008"' in got["filed"] \
        and "1 filed for 2027." in plain(got["filed"]) and plain(got["none"]) == "No bill requests co-sponsored for 2027.", (
        f"the prime sponsor's tabs, or a member's with none: {[plain(got[x])[:120] for x in ('own', 'filed', 'none')]}")
    assert not any("names only its prime sponsor" in v for v in got.values()) \
        and "names only its prime sponsor" not in _source("src/pages/app.js"), (
        "a member's page still says a request names only its prime sponsor")
    return "ok", ("a co-sponsor's Co-sponsored tab lists the request, 1 co-sponsored for 2027; the prime sponsor's "
                  "tab lists it as before; each member's other tab says none; the old sentence gone")


@check("build", "the request texts' drain asks for what the list links and this disk has not settled, "
                "--budget at most, paced, under the lock, a refusal or two dropped connections ending it; "
                "--read-texts writes each text beside its PDF and asks nobody",
       needs=("fetch_lsrs", "extract_calendar_text"))
def _lsr_text_drain(FL, ET):
    """fetch_lsrs.py --texts (THE TEXT, ONCE IT IS PUBLIC), driven through main() in a throwaway
    folder on fake answers, as _calendar_drain drives the calendars' drain: so refusal.check() and
    refusal.hold() are the ones the night meets, and nothing asks the network (urlopen raises).

      - three linked, a budget of two: two asked, in order, each saved with its address in the
        record, the third left for tomorrow; the run after asks the third alone;
      - a text held at the address the list gives is not asked again, and is at a new one;
      - a 404 is "gone" and not asked again; something not a PDF is an attempt, and the third
        attempt leaves it ("failed");
      - one 403, the block page served with HTTP 200, and two dropped connections each end the run
        with status 2 and the refusal recorded; somebody else's lock is status 3 with nothing asked;
      - --read-texts writes the text beside each PDF held, records a PDF with none as "none", and
        asks nobody, a refusal on file or not.
    """
    import contextlib
    import http.client
    import io
    import time
    import types
    import urllib.error
    import urllib.request
    import refusal
    here = os.getcwd()
    saved = (refusal.MARK, refusal.LOCK, FL._fetch, FL.time, sys.argv, urllib.request.urlopen,
             ET.extract)
    PDF = b"%PDF-1.4 a bill"
    tmp = Path(tempfile.mkdtemp(prefix="gr-lsrtexts-"))

    def lsrs(n, url=lambda i: f"https://gc.nh.gov/t/{i}.pdf"):
        Path("lsrs.json").write_text(json.dumps([
            {"lsr": f"2027-{i:04d}", "session": 2027, "body": "HB", "title": "t.", "sponsor": "A B",
             "cosponsors": [], "withdrawn": False, **({"text_pdf": url(i)} if url(i) else {})}
            for i in range(1, n + 1)]), encoding="utf-8")

    def run(answers, budget=2, lock=None, args=("--texts",)):
        refusal.LOCK.unlink(missing_ok=True)
        if lock is not None:
            refusal.LOCK.write_text(str(lock), encoding="utf-8")
        answers, asked = iter(answers), []

        def fake(url, timeout=60):
            asked.append(url)
            a = next(answers)
            if isinstance(a, BaseException):
                raise a
            return a
        FL._fetch = fake
        sys.argv = ["fetch_lsrs.py", *args, "--budget", str(budget), "--delay", "1"]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                rc = FL.main()
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
        return rc, asked, FL.load_state()

    def raiser(*a, **k):
        raise AssertionError("the request texts' drain opened a connection")
    try:
        os.chdir(tmp)
        Path("archive").mkdir()
        refusal.MARK, refusal.LOCK = tmp / "archive" / "refused.json", tmp / "archive" / ".lock"
        FL.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time, strftime=time.strftime)
        urllib.request.urlopen = raiser
        lsrs(3)
        rc, asked, st = run([PDF, PDF])
        assert rc == 0 and asked == ["https://gc.nh.gov/t/1.pdf", "https://gc.nh.gov/t/2.pdf"], (rc, asked)
        assert [st[k]["state"] for k in sorted(st)] == ["held", "held"] and \
            st["2027-0001"]["url"] == "https://gc.nh.gov/t/1.pdf", st
        assert (FL.TEXTS / "2027-0001.pdf").read_bytes() == PDF, "the PDF was not saved at its request"
        assert FL.texts_wanted() == [("2027-0003", "https://gc.nh.gov/t/3.pdf")], FL.texts_wanted()
        rc, asked, st = run([PDF])
        assert rc == 0 and asked == ["https://gc.nh.gov/t/3.pdf"], (rc, asked)
        rc, asked, st = run([])
        assert rc == 0 and not asked, f"a text held at its address was asked again: {asked}"
        lsrs(1, url=lambda i: "https://gc.nh.gov/t/1-revised.pdf")
        rc, asked, st = run([PDF])
        assert asked == ["https://gc.nh.gov/t/1-revised.pdf"] and st["2027-0001"]["state"] == "held", (asked, st)
        # Not served, and not a PDF three times.
        shutil.rmtree("archive/lsr_text")
        Path(FL.TEXT_STATE).unlink()
        lsrs(2)
        nf = urllib.error.HTTPError("u", 404, "Not Found", http.client.HTTPMessage(), io.BytesIO(b""))
        rc, asked, st = run([nf, b"<html>a page</html>"])
        assert rc == 0 and st["2027-0001"]["state"] == "gone" and \
            st["2027-0002"]["state"] == "wanted" and st["2027-0002"]["attempts"] == 1, (rc, st)
        for n in (2, 3):
            rc, asked, st = run([b"<html>a page</html>"])
            assert asked == ["https://gc.nh.gov/t/2.pdf"], asked
        assert st["2027-0002"]["state"] == "failed" and st["2027-0002"]["attempts"] == 3, st
        rc, asked, st = run([])
        assert not asked, f"a text left after three attempts, or one not served, was asked again: {asked}"
        # The refusals, and somebody else's lock.
        for what, answers, n in (
                ("a 403", [urllib.error.HTTPError("u", 403, "Forbidden", http.client.HTTPMessage(),
                                                  io.BytesIO(b"")), PDF], 1),
                ("the block page", [b"<h1>Web Page Blocked</h1> Attack ID: 9", PDF], 1),
                ("two dropped connections", [urllib.error.URLError(ConnectionResetError(10054, "r")),
                                             http.client.RemoteDisconnected("x"), PDF], 2)):
            shutil.rmtree("archive/lsr_text", ignore_errors=True)
            Path(FL.TEXT_STATE).unlink(missing_ok=True)
            refusal.MARK.unlink(missing_ok=True)
            lsrs(3)
            rc, asked, st = run(answers, budget=3)
            assert rc == 2 and len(asked) == n and refusal.MARK.exists(), (what, rc, asked)
        rc, asked, st = run([PDF], budget=3)
        assert rc == 2 and not asked, f"with a refusal on file the drain ran: {rc} {asked}"
        refusal.MARK.unlink()
        rc, asked, st = run([PDF], lock=99999999)
        assert rc == 3 and not asked and refusal.LOCK.read_text().strip() == "99999999", (rc, asked)
        refusal.LOCK.unlink()
        # The text, beside each PDF held; a PDF with none recorded so. Asks nobody, refusal or none.
        rc, asked, st = run([PDF, PDF, PDF], budget=3)
        assert rc == 0 and len(asked) == 3, (rc, asked)
        refusal.MARK.write_text(json.dumps({"at": "2026-12-01T09:00:00Z", "where": "x", "why": "y"}),
                                encoding="utf-8")
        ET.extract = lambda pdf, layout_only=False: (("AN ACT relative to things.\n", "pdftotext -layout")
                                                     if Path(pdf).stem != "2027-0002" else (None, "no text"))
        rc, asked, st = run([], args=("--read-texts",))
        assert rc == 0 and not asked, (rc, asked)
        assert (FL.TEXTS / "2027-0001.txt").read_text(encoding="utf-8").startswith("AN ACT"), \
            "--read-texts wrote no text beside the PDF"
        assert st["2027-0001"]["text"] == "pdftotext -layout" and st["2027-0002"]["text"] == "none" \
            and not (FL.TEXTS / "2027-0002.txt").exists(), st
    finally:
        os.chdir(here)
        (refusal.MARK, refusal.LOCK, FL._fetch, FL.time, sys.argv, urllib.request.urlopen,
         ET.extract) = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("two of three asked on a budget of two and the third the night after; a held text not "
                  "asked again, a new link asked; a 404 gone, three bad answers failed; a 403, the block "
                  "page and two drops each end it with status 2; another's lock 3; --read-texts writes "
                  "the text and asks nobody")


@check("frontend", "the stream date is one constant, and a sitting with no recording is never offered one",
       needs=("build_site_v2", "about_figures"))
def _stream_start(build_site_v2, about_figures):
    """Where the recordings this site links begin, said once and drawn right.

    The date was two literals: "2020-03-01" in station_for_proceeding and in
    about_figures, which the About page states as "March 2020". The General
    Court's YouTube channels begin on 14 May 2020, so 385 committee sittings
    of March to May 2020 read "No recording matched" when nothing could have
    been, and changing the constant alone would have moved the prose and left
    the builder where it was. build_site_v2 imports it now.

    And a floor or conference appearance with no recording came out as
    "floor_dated", which app.js draws as a player: 1,613 committee-of-
    conference sittings from 1990 on offered an embed of an empty id and an
    "Open on YouTube" link to watch?v=. They take the committee states now.

    The page's own sentence is held to the same constant, because app.js
    cannot import it: the month it names is STREAM_START_WORDS.
    """
    import inspect
    B, AF = build_site_v2, about_figures
    assert getattr(B, "STREAM_START", None) == AF.STREAM_START, (
        f"build_site_v2 splits on {getattr(B, 'STREAM_START', 'a literal of its own')!r} "
        f"and the About page on {AF.STREAM_START!r}; import the one constant")
    for fn in (B.station_for_proceeding, B.station_for_floor):
        lit = re.findall(r"(?:19|20)\d\d-\d\d-\d\d", inspect.getsource(fn))
        assert not lit, (f"{fn.__name__} carries the date literal {lit[0]}; the "
                         "stream date is about_figures.STREAM_START and nowhere else")
    # WHERE THE CHANNELS BEGIN, from the index of both of them. Tracked, so
    # this runs on a fresh clone; a date the index does not bear out is a
    # claim about the General Court's recordings that nothing supports.
    idx = Path("collected/videos/channel_index_full.json")
    first = None
    if idx.exists():
        d = json.loads(idx.read_text(encoding="utf-8"))
        first = min((v.get("published") or "")[:10]
                    for ch in ("house", "senate")
                    for v in ((d.get(ch) or {}).get("videos") or [])
                    if v.get("published"))
        assert first == AF.STREAM_START, (
            f"the earliest recording on either channel is {first}, and "
            f"STREAM_START says {AF.STREAM_START}")

    def sitting(date):
        return {"bill": "HB1", "body": "H", "committee": "Judiciary",
                "proceeding": "public hearing", "sched_date": date,
                "sched_time": "10:00", "venue": "LOB 206", "video_id": "",
                "candidate_ids": ""}
    for date, want in (("2020-03-02", "prestream"), (AF.STREAM_START, "novideo"),
                       ("2021-01-06", "novideo"), ("1995-04-01", "prestream")):
        got = B.station_for_proceeding(sitting(date), "HB1", {}, {})["state"]
        assert got == want, f"a committee sitting of {date} with no recording is {got!r}, not {want!r}"

    def conference(date, vid=""):
        return {"date": date, "body": "H", "video_id": vid, "motions": [],
                "tallies": [], "kind": "committee of conference",
                "debate_end": None, "window_start": None, "precise": False,
                "whole_video": False, "title": "", "time": "10:00",
                "venue": "RM 102,LOB"}
    PLAYED = {"floor_dated", "floor_precise", "floor_stated", "whole_video", "consent"}
    for date, want in (("1995-04-01", "prestream"), ("2025-06-17", "novideo")):
        st = B.station_for_floor(conference(date), "HB1", {})
        assert st["state"] == want, (
            f"a conference sitting of {date} with no recording is {st['state']!r}, "
            f"not {want!r}; {'floor_dated draws a player for an empty id' if st['state'] in PLAYED else ''}")
        assert not st.get("watch") and not st.get("video_id"), (
            f"a conference sitting with no recording links {st.get('watch')!r}")
        assert (st.get("time"), st.get("venue")) == ("10:00", "RM 102,LOB"), (
            "a conference sitting with no recording lost the time and room the "
            f"docket gives: {st.get('time')!r}, {st.get('venue')!r}")
    rec = B.station_for_floor(conference("2025-06-17", "VIDX"), "HB1", {})
    assert rec["state"] == "floor_dated" and "VIDX" in (rec.get("watch") or ""), (
        f"a conference sitting WITH a recording no longer offers it: {rec}")

    # THE PAGE. Both no-recording states draw no player and no YouTube link,
    # and the tab names the month the constant does -- ONCE, above its
    # sittings, however many came before it (the audit of 25 October 2026,
    # S4: it was a box on every one), and not at all where none did.
    stations = [B.station_for_floor(conference("1995-04-01"), "HB1", {}),
                B.station_for_proceeding(sitting("1995-03-01"), "HB1", {}, {}),
                B.station_for_proceeding(sitting("2021-01-06"), "HB1", {}, {})]
    drawn = _app_js("[scope.renderHearings({id:'HB1', n:'HB 1'}, {stations:"
                    + json.dumps(stations) + "}), scope.renderHearings({id:'HB1', n:'HB 1'}, {stations:"
                    + json.dumps(stations[-1:]) + "})]")
    if drawn is None:
        return "ok", (f"one constant, {AF.STREAM_START}"
                      + (", the channels' first day" if first else "")
                      + "; no-recording sittings take the committee states (node not here, page not drawn)")
    html_, later = drawn
    assert "youtube.com" not in html_ and "data-embed" not in html_, (
        "a sitting with no recording is drawn with a player or a YouTube link")
    assert html_.count(AF.STREAM_START_WORDS) == 1 and \
        html_.index(AF.STREAM_START_WORDS) < html_.index('class="stn'), (
            f"the Hearings tab does not name {AF.STREAM_START_WORDS!r}, the month "
            "about_figures.STREAM_START_WORDS says the channels begin, once above its sittings "
            f"({html_.count(AF.STREAM_START_WORDS)} times)")
    assert AF.STREAM_START_WORDS not in later, (
        "a Hearings tab with no sitting before the channels says when they begin")
    for bad in ("No recording exists", "livestreamed"):
        assert bad not in html_, f"the page still says {bad!r}, which the House Calendars contradict"
    return "ok", (f"one constant, {AF.STREAM_START}"
                  + (", the channels' first day" if first else "")
                  + "; no-recording sittings are prestream or novideo, keep their time and room, "
                    "and draw no player")


@check("frontend", "a committee of conference noticed and recorded is one station, with the notice's time and room",
       needs=("build_site_v2",))
def _conference_folded(build_site_v2):
    """HB 485's conference of 16 June 2025 was two stations on its page.

    proceedings.csv holds a noticed and recorded conference twice: the
    docket's row, 09:30 in LOB 206-208 with no recording, and the floor
    index's, the recording dIumWRhMDrY with no time. station_for_floor drew
    each, so the page said "No recording matched to this proceeding." over
    the one sitting it then played -- and HB 1709's of 26 May 2026, which is
    on two recordings, three times. 61 Senate bill-days were drawn so, SB
    108's of 13 June 2025 among them, and reading the House's notices made it
    159. fold_conference_notices folds the notice into the recording.

    The rows are proceedings.csv's own, as build_site_v2 shapes them.
    """
    B = build_site_v2
    fold = getattr(B, "fold_conference_notices", None)
    assert fold, "build_site_v2 has no fold_conference_notices"
    C, D = "committee of conference", "floor debate"

    def row(date, kind, vid="", time="", venue="", whole=False, body="H"):
        return {"date": date, "body": body, "video_id": vid, "motions": [],
                "tallies": [], "kind": kind, "debate_end": None,
                "window_start": None, "precise": False, "whole_video": whole,
                "title": "", "time": time, "venue": venue}
    cases = {
        # (bill, its floor rows) -> what its conference stations should be
        "HB485": [row("2025-06-05", D, "B747DpYcc9E"),
                  row("2025-06-16", C, time="09:30", venue="LOB 206-208"),
                  row("2025-06-16", C, "dIumWRhMDrY")],
        "HB1709": [row("2026-05-14", D, "xkUhsgh3skk"),
                   row("2026-05-26", C, time="14:45", venue="GP 234"),
                   row("2026-05-26", C, "Pm-qXemJrHw"),
                   row("2026-05-26", C, "F590FEiqVoA", whole=True),
                   row("2026-06-04", D, "l_01QWYdAiw")],
        "SB108": [row("2025-06-13", C, time="09:00", venue="SH 103", body="S"),
                  row("2025-06-13", C, "OCmDvpG_NSg", body="S")],
        # Noticed twice and recorded never: both stay, and say so.
        "HB1541": [row("2026-05-27", C, time="10:40", venue="GP 228"),
                   row("2026-05-28", C, time="10:00", venue="GP 228")],
    }
    want = {
        "HB485": [("2025-06-16", "09:30", "LOB 206-208", "dIumWRhMDrY", "floor_dated")],
        "HB1709": [("2026-05-26", "14:45", "GP 234", "Pm-qXemJrHw", "floor_dated"),
                   ("2026-05-26", "14:45", "GP 234", "F590FEiqVoA", "whole_video")],
        "SB108": [("2025-06-13", "09:00", "SH 103", "OCmDvpG_NSg", "floor_dated")],
        "HB1541": [("2026-05-27", "10:40", "GP 228", "", "novideo"),
                   ("2026-05-28", "10:00", "GP 228", "", "novideo")],
    }
    drawn = {}
    for bid, rows in cases.items():
        before = [dict(r) for r in rows]
        sts = [B.station_for_floor(f, bid, {}) for f in fold(rows)]
        assert rows == before, f"fold_conference_notices changed {bid}'s rows in place"
        got = [(s["when"], s.get("time"), s.get("venue"), s.get("video_id") or "", s["state"])
               for s in sts if s["what"] == C]
        assert got == want[bid], f"{bid}'s conference stations are {got}; wanted {want[bid]}"
        # A floor debate is never folded, and takes no time from a notice.
        deb = [(s["when"], s.get("time"), s.get("venue")) for s in sts if s["what"] == D]
        assert deb == [(r["date"], None, None) for r in rows if r["kind"] == D], (
            f"{bid}'s floor debates came out as {deb}")
        drawn[bid] = sts
    # THE BUILDER CALLS IT. A fold nothing calls folds nothing.
    src = _source(B.__file__)
    assert re.search(r"station_for_floor\(f, bid, marks\)\s+for f in "
                     r"fold_conference_notices\(floor\.get\(\(term, bid\)", src), (
        "build_bills no longer draws its floor stations through fold_conference_notices")
    # THE PAGE. HB 485's one conference is drawn once, timed, and never as
    # "No recording matched".
    # (The view opens on the bill's first recording, so the conference is
    # drawn alone here: its detail is under the player only while chosen.)
    html_ = _app_js("scope.renderHearings({id:'HB485', n:'HB 485'}, {stations:"
                    + json.dumps([s for s in drawn["HB485"] if s["what"] == C]) + "})")
    if html_ is not None:
        assert "No recording matched" not in html_, (
            "HB 485's page still says no recording matched its conference of 16 June 2025")
        # The room as the Documents tab names it (the person, approved 17
        # October 2026).
        # Each fact once (the owner, 19 November 2026): the day in the
        # recording's row, the time and the room under the player.
        flat = re.sub(r"<[^>]+>", "", html_)
        assert "Jun 16, 2025" in flat and re.search(
            r"9:30\sAM, &middot;&nbsp;Legislative Office Building 206-208", flat), (
            "HB 485's conference is not headed with the time and room its notice gives")
    return "ok", ("HB 485's conference of 16 June 2025 is one station, 09:30 in LOB 206-208, "
                  "playing its recording; HB 1709's is one per recording and SB 108's one; "
                  "HB 1541's two notices with no recording stand")


@check("markers", "a roll call that day overrules the consent calendar, and a committee "
       "of conference takes the chair's convening", needs=("build_site_v2",))
def _floor_station_rules(build_site_v2):
    """Two rules of station_for_floor, both of 17 October 2026.

    The consent calendar is inferred from the captions never naming the bill,
    and the captions garble numbers: HB 1002 (EXjvgzYBkb8, 12 February 2026,
    tabled 187-157) and HB 1602 (V8T49pbn0UU, 19 February 2026, two roll
    calls) were drawn as passed on consent. A roll call on the day is the
    chamber's own record that the bill was voted on by itself.

    And a committee of conference's convening is a marker of its own kind,
    "committee of conference", which the floor accepted only as "" or "floor
    debate": 25 conference sittings drew no time, and HB 710 on dIumWRhMDrY
    the chair's "open the door" at 1:20:08 instead of the convening at 0:16:39.
    """
    B = build_site_v2

    def row(kind, tallies=(), precise=False, debate_end=None):
        return {"date": "2026-02-12", "body": "H", "video_id": "VIDX",
                "motions": ["Table"] if tallies else [], "tallies": list(tallies),
                "kind": kind, "debate_end": debate_end, "window_start": 0.0,
                "precise": precise, "whole_video": False, "title": "",
                "time": "", "venue": ""}
    absent = {"_absent": {"VIDX": ["HB1002"]}}
    st = B.station_for_floor(row("floor debate"), "HB1002", absent)
    assert st["state"] == "consent", (
        f"a bill never named with no roll call is {st['state']!r}, not the consent calendar")
    st = B.station_for_floor(row("floor debate", ["187-157"], True, 18914.0),
                             "HB1002", absent)
    assert st["state"] == "floor_precise" and st["what"] == "floor debate", (
        f"a bill tabled 187-157 by roll call is drawn as {st['state']!r} {st['what']!r}; "
        "a roll call overrules the consent calendar")
    st = B.station_for_floor(row("floor debate", ["84-254"]), "HB1002", absent)
    assert st["state"] != "consent", (
        "a roll call stamped with the date alone (the Senate's) still drew the consent calendar")
    # Nor a concurrence or a conference (after review, 17 October 2026):
    # HB 250's non-concurrence of 22 May 2025 on YobZAwJsSQo drew consent.
    for motion in ("House Non-Concurs with Senate Amendment 2025-1234s and Requests C of C",
                   "Accedes to House Request for Committee of Conference",
                   "Nonconcur with the House Amendment; Requests C of C"):
        st = B.station_for_floor(dict(row("floor debate"), motions=[motion]), "HB1002", absent)
        assert st["state"] == "floor_dated", (
            f"{motion!r}, never named on the recording, drew {st['state']!r}; "
            "business between the chambers is never the consent calendar")
    st = B.station_for_floor(dict(row("floor debate"), motions=["Ought to Pass"]), "HB1002", absent)
    assert st["state"] == "consent", f"an Ought to Pass never named drew {st['state']!r}"

    def mk(start, what):
        return {"start": start, "end": None, "how": "number", "what": what, "said": "x"}
    marks = {"VIDX": {"HB710": [mk(999.8, "committee of conference"), mk(4808.6, "")]}}
    st = B.station_for_floor(row("committee of conference"), "HB710", marks)
    assert st.get("start") == 999.8, (
        f"a conference sitting took {st.get('start')} over the chair's convening at 999.8")
    st = B.station_for_floor(row("floor debate"), "HB710", marks)
    assert st.get("start") == 4808.6, (
        f"a floor debate took a committee of conference's convening: {st.get('start')}")
    # The first spoken, not its own kind first: "We'll open a COC on Senate
    # Bill 96" (89R50nnQFrE 0:02:48) opens the sitting that "convene the
    # committee of conference on Senate Bill 96" resumes at 2:31:27.
    marks = {"VIDX": {"SB96": [mk(168.2, ""), mk(9087.8, "committee of conference")]}}
    st = B.station_for_floor(row("committee of conference"), "SB96", marks)
    assert st.get("start") == 168.2, f"SB 96's conference opened at {st.get('start')}, not 168.2"
    return "ok", ("a roll call overrules the consent calendar, clocked or not; a conference "
                  "takes its own convening, and the first opening spoken")


@check("markers", "a clustering placement with no mention of the bill inside is not published",
       needs=("build_site_v2",))
def _cluster_needs_a_mention(build_site_v2):
    """Of the 1,099 clustered placements the site published on 15 October
    2026, 399 had no mention of their bill inside the span, 321 of them the
    aligner's 30-second minimum; the four a person had timed were 4, 30, 77
    and 202 minutes out (17 October 2026). Such a placement gives neither a
    start, an end beside a stated start, nor a suggested time."""
    B = build_site_v2
    p = {"bill": "HB152", "body": "H", "committee": "Judiciary",
         "proceeding": "executive session", "sched_date": "2026-02-03",
         "sched_time": "10:00", "venue": "LOB 206", "video_id": "VIDX",
         "predicted_offset": 600, "candidate_ids": ""}

    def seg(inside):
        return {"VIDX": [{"bill": "HB152", "kind": "executive session", "located": True,
                          "short": True, "tolerance": 1800, "start": 2520.0,
                          "end": 2550.0, "mentions_inside": inside, "mentions_total": 4}]}
    st = B.station_for_proceeding(p, "HB152", seg(0), {})
    assert st["state"] == "approximate" and st["start"] is None, (
        f"a placement with no mention inside is published: {st['state']} at {st['start']}")
    assert st.get("candidate") is None and st.get("end") is None, (
        f"a placement with no mention inside is still suggested: {st.get('candidate')}")
    st = B.station_for_proceeding(p, "HB152", seg(2), {})
    assert st["state"] == "located" and st["start"] == 2520.0, (
        f"a placement with two mentions inside is withheld: {st['state']}")
    said = {"VIDX": {"HB152": [{"start": 2530.0, "end": None, "how": "number",
                                "what": "executive session", "said": "x"}]}}
    st = B.station_for_proceeding(p, "HB152", seg(0), said)
    assert st["start"] == 2530.0 and st["end"] is None, (
        f"a stated start took its end from a placement with no mention inside: {st['end']}")
    # Named in the minute before the span counts as inside (after review):
    # segment_markers lists those under _named_before.
    before = {"_named_before": {"VIDX": ["HB152|executive session"]}}
    st = B.station_for_proceeding(p, "HB152", seg(0), before)
    assert st["state"] == "located" and st["start"] == 2520.0, (
        f"a placement whose bill was named just before it was withheld: {st['state']}")
    assert st["end"] is None, (
        f"a placement named only before it published the aligner's minimum as its end: {st['end']}")
    other = {"_named_before": {"VIDX": ["HB152|public hearing"]}}
    st = B.station_for_proceeding(p, "HB152", seg(0), other)
    assert st["start"] is None, "another proceeding's mention kept this placement"
    return "ok", "no mention inside: no start, no end, no suggestion; two mentions: placed"


@check("markers", "a sitting whose recording never names its bill says so once, under its one "
       "button, and only there",
       needs=("build_site_v2", "segment_markers"))
def _station_not_named(build_site_v2, segment_markers):
    """222 committee sittings drew "Matching proceedings to the moment they
    begin is ongoing work, and this one is not done" where the
    recording's captions never name the bill at all, so no moment could ever
    be marked (17 October 2026; the person approved the new words).
    segment_markers lists such bills under _not_named; station_for_proceeding
    sets not_named on a sitting drawn with no start, and app.js says the
    captions never name the bill, keeps the player at the scheduled time,
    and keeps the old words where the bill is named but no opening found.
    Said once since 26 October 2026 (the owner): one button, "Play from
    00:05:00 · scheduled 10:00 AM", over the note "bill not named in the
    captions", as the other recording cards are -- a paragraph under the
    note said it a second time. The same where a not-named sitting's state
    is one app.js does not know and it still offers the recording."""
    B = build_site_v2
    p = {"bill": "HB152", "body": "H", "committee": "Judiciary",
         "proceeding": "public hearing", "sched_date": "2026-02-03",
         "sched_time": "10:00", "venue": "LOB 206", "video_id": "VIDX",
         "predicted_offset": 600, "candidate_ids": ""}
    nn = {"_not_named": {"VIDX": ["HB152"]}}
    st = B.station_for_proceeding(p, "HB152", {}, nn)
    assert st["state"] == "approximate" and st.get("not_named") is True, (
        f"a sitting whose recording never names its bill is not marked so: {st}")
    plain = B.station_for_proceeding(p, "HB152", {}, {"_not_named": {"VIDX": ["HB153"]}})
    assert "not_named" not in plain, "another bill's entry marked this sitting not named"
    assert "not_named" not in B.station_for_proceeding(p, "HB152", {}, {"_not_named": {"VIDY": ["HB152"]}}), (
        "another recording's entry marked this sitting not named")
    said = dict(nn, VIDX={"HB152": [{"start": 700.0, "end": None, "how": "number",
                                     "what": "public hearing", "said": "x"}]})
    st2 = B.station_for_proceeding(p, "HB152", {}, said)
    assert st2["state"] == "stated" and "not_named" not in st2, (
        "a sitting with a stated start is marked not named")
    assert "_not_named" in segment_markers.SIDES, (
        "_not_named is not one of segment_markers.SIDES, so the late-caption withholding keeps it")
    odd = dict(st, state="unheard-of")
    html_ = _app_js("[" + ", ".join("scope.renderHearings({id:'HB152', n:'HB 152'}, {stations:"
                                    + json.dumps([s]) + "})" for s in (st, plain, odd)) + "]")
    if html_ is not None:
        named, other, fallback = (re.sub(r"\s+", " ", h) for h in html_)
        # ONE BUTTON WITH ITS NOTE (the owner, 26 October 2026), as the other
        # recording cards are: where Play starts and the time set, over "bill
        # not named in the captions" -- said once. A paragraph under the note
        # said it again ("The recording's captions never name this bill ...").
        # Since 10 November 2026 (the owner) the Hearings tab is a committee's
        # Videos tab for one bill: one player, the sitting's day and time in
        # the line under it, and the note once, under the player.
        # Each fact once (the owner, 19 November 2026): the day in the
        # recording's row, the time under the player, a time as YouTube's.
        for want in ('<p class="vwnone">Bill not named in the captions.</p>',
                     "Play from 5:00", "Feb 3, 2026", "10:00", 'data-embed="VIDX|300|'):
            assert want in named, f"the not-named sitting does not say {want!r}"
        for k, h in (("the not-named sitting", named),
                     ("a not-named sitting of a state app.js does not know", fallback)):
            said = re.sub(r"<[^>]+>", " ", h)
            assert len(re.findall(r"not named|never name", said)) == 1 \
                and 'class="note"' not in h and h.count('class="pstub"') == 1, (
                    f"{k} says its bill is not named other than once, under its one player: "
                    + said[:400])
        assert 'data-embed="VIDX|0|' in fallback, (
            "a not-named sitting of a state app.js does not know is not offered from the start")
        assert "ongoing work" not in named and "not identified" not in named, (
            "the not-named sitting still says the matching is unfinished")
        # One button since 25 October 2026 (S2): "Play from 00:05:00 ·
        # scheduled 10:00 AM (exact moment not found)".
        assert "Exact moment not found." in other and "not named" not in other, (
            "a sitting whose bill is named lost the words for an opening not found")
    return "ok", ("marked only where its recording never names it and no start is drawn; one "
                  "player, \"Play from 5:00\", over \"Bill not named in the captions.\", said once")


@check("frontend", "a bill's recording cards say each thing once: two recordings in one line, "
       "an unfound moment in one button, a floor card's start, vote and motion in the Votes tab's "
       "words", needs=("build_site_v2",))
def _recording_cards_once(build_site_v2):
    """The audit of 25 October 2026 (S2), on HB 131 of 2026's Hearings tab,
    in the owner's words. A day with two recordings was 108 words; it is
    "Two recordings that day; the record doesn't say which covers this bill:
    Recording 1 · Recording 2". A sitting whose moment was not found said
    "start time not identified yet" in its button and again under it, and a
    note said it a third time; it is one button, "Play from the start ·
    scheduled 10:00 AM (exact moment not found)". A floor card is "Play from
    05:13:45 · vote at 05:23:18 · Open on YouTube": no "window opens" jump,
    no "timed to the second", and the motion as the Votes tab names it, not
    the clerk's "OTPA". Only the words changed: Play opens where it did, and
    an inferred opening still carries "approximate".

    The stations are build_site_v2's own, made from the rows as
    proceedings.csv and the floor index hold them; the page is app.js in
    node."""
    B = build_site_v2

    def sitting(**kw):
        return dict({"bill": "HB131", "body": "H", "committee": "Education Policy and Administration",
                     "proceeding": "executive session", "sched_date": "2025-03-12",
                     "sched_time": "10:00", "venue": "LOB 205-207", "video_id": "73sLapY1jRw",
                     "predicted_offset": 69, "candidate_ids": ""}, **kw)

    def floor(**kw):
        return dict({"date": "2026-01-07", "body": "H", "video_id": "itJRViVSJqk",
                     "motions": ["OTPA"], "tallies": ["190-149"], "kind": "floor debate",
                     "debate_end": 19398.0, "window_start": 18769.0, "precise": True,
                     "whole_video": False, "title": "", "time": "", "venue": ""}, **kw)
    said = {"itJRViVSJqk": {"HB131": [{"start": 18825.0, "end": None, "how": "number",
                                       "what": "floor debate", "said": "x"}]}}
    weak = {"itJRViVSJqk": {"HB131": [{"start": 18825.0, "end": None, "what": "",
                                       "how": "title read, then the sponsor welcomed (weak marker)"}]}}
    sts = {
        "two": B.station_for_proceeding(sitting(proceeding="subcommittee work session",
                                                sched_date="2025-03-03", video_id="",
                                                candidate_ids="IIea0XVXPOQ | sm2z5yQ-XKQ"),
                                        "HB131", {}, {}),
        "start": B.station_for_proceeding(sitting(), "HB131", {}, {}),
        "later": B.station_for_proceeding(sitting(sched_time="09:35", predicted_offset=1288,
                                                  video_id="FL8-GWBu5wk"), "HB131", {}, {}),
        "vote": B.station_for_floor(floor(), "HB131", said),
        "weak": B.station_for_floor(floor(), "HB131", weak),
        "chair": B.station_for_floor(floor(motions=["Ought to Pass with Amendment # 2026-1396s"],
                                           tallies=[], precise=False, debate_end=None,
                                           window_start=None, body="S", video_id="Pa_qxMZlvQ0"),
                                     "HB131", {"Pa_qxMZlvQ0": {"HB131": [
                                         {"start": 1477.8, "end": 1857.0, "how": "number",
                                          "what": "floor debate", "said": "x"}]}}),
        "day": B.station_for_floor(floor(motions=["House Concurs with Senate Amendment 2026-1396s"],
                                         tallies=[], precise=False, debate_end=None,
                                         window_start=None, video_id="n7W5L0CAVE4"), "HB131", {}),
    }
    states = {k: s["state"] for k, s in sts.items()}
    assert states == {"two": "candidates", "start": "approximate", "later": "approximate",
                      "vote": "floor_precise", "weak": "floor_precise", "chair": "floor_stated",
                      "day": "floor_dated"}, f"the stations are not the ones drawn here: {states}"
    assert sts["vote"].get("mks") == [{"mk": "otpa"}], (
        f"the floor station carries {sts['vote'].get('mks')!r} for the clerk's OTPA, not its key")
    keys = list(sts)
    html_ = _app_js("[" + ", ".join(f"scope.renderHearings({{id:'HB131', n:'HB 131'}}, "
                                    f"{{stations:[{json.dumps(sts[k])}]}})" for k in keys) + "]",
                    names=("renderHearings",))
    if html_ is None:
        return "skip", "node, app.js or the stub is not here"
    page = {k: re.sub(r"\s+", " ", h) for k, h in zip(keys, html_)}
    # A tag is a space, but not inside a bracket: "(OTPA, ...)" is marked
    # for its popover.
    text = {k: re.sub(r"\(\s+", "(", re.sub(r"\s+([,)])", r"\1", re.sub(r"\s+", " ", re.sub(
                r"<[^>]+>", " ", h)))).replace("&rsquo;", "’").strip()
            for k, h in page.items()}
    bad = []

    def need(k, *words):
        for w in words:
            if w not in text[k]:
                bad.append(f"{k}: no {w!r} in {text[k][:200]!r}")

    def never(k, *words):
        for w in words:
            if w in text[k]:
                bad.append(f"{k}: still says {w!r}")
    need("two", "Two recordings that day; the record doesn’t say which covers this bill: "
                "Recording 1 · Recording 2")
    box = re.search(r'<div class="vbox">(.*?)</div>', page["two"], re.S)
    words = len(re.sub(r"<[^>]+>", " ", box.group(1)).split()) if box else 0
    if not 0 < words <= 20:
        bad.append(f"two: {words} words")
    # The clock's no-break space is a space here (\s above). One player, the
    # sitting's day and time in the line under it, and the unfound moment said
    # once (the Hearings tab as a committee's Videos tab, 10 November 2026).
    # Each fact once (the owner, 19 November 2026): the day in the row, the
    # time under the player; a time in the recording as YouTube writes one.
    need("start", "Play the recording", "Mar 12, 2025", "10:00 AM", "Exact moment not found.")
    need("later", "Play from 16:28", "Mar 12, 2025", "9:35 AM", "Exact moment not found.")
    for k in ("start", "later", "day"):
        never(k, "not identified", "Not yet matched", "automatic pass")
        if 'class="tolnote"' in page[k] or 'class="note"' in page[k]:
            bad.append(f"{k}: says it again under the button")
    if 'data-embed="73sLapY1jRw|0|' not in page["start"] or \
            'data-embed="FL8-GWBu5wk|988|' not in page["later"]:
        bad.append("an unfound moment's Play no longer opens where it did")
    need("vote", "Play from 5:13:45", "Where this bill is in the recording 5:13:45 to 5:23:18 vote", "On YouTube",
         "Motion: Ought to Pass with Amendment (OTPA, Pass the bill with changes)")
    never("vote", "window opens", "timed to the second", "Motions: OTPA", "approximate",
          "where the clerk takes it up")
    if 'data-embed="itJRViVSJqk|18825|' not in page["vote"]:
        bad.append("the floor card's Play no longer opens at the clerk's opening")
    need("weak", "Play from 5:13:45", "5:13:45 to 5:23:18 vote approximate")
    need("chair", "Play from 24:37", "24:37 to 30:57",
         "Motion: Ought to Pass with Amendment (OTPA, Pass the bill with changes) 2026-1396s")
    never("chair", "no roll call on this one", "approximate")
    need("day", "Play the recording", "Exact moment not found.")
    never("day", "moment not identified", "nothing to point at")
    assert not bad, "; ".join(bad[:6])
    return "ok", ("HB 131 of 2026's cards: two recordings in one line, an unfound moment in one "
                  "button, the floor's start, vote and motion in the Votes tab's words, "
                  "approximate where the opening is inferred, Play where it was")


@check("markers", "a marker naming no proceeding serves one sitting of the bill, the first "
       "in docket order", needs=("build_site_v2",))
def _ambiguous_marker_once(build_site_v2):
    """341 moments were published on two proceedings of one bill on 15
    October 2026 (687 stations): a marker that names no proceeding was the
    fallback of every sitting of the bill on the recording that had none of
    its own (17 October 2026). It goes to the first in docket order now, and
    the later ones take no such marker -- not the next one along, which read
    mostly as the same hearing a minute on."""
    B = build_site_v2

    def sitting(kind, time):
        return {"bill": "HB1040", "body": "H", "committee": "Public Works",
                "proceeding": kind, "sched_date": "2026-01-20", "sched_time": time,
                "venue": "LOB 201", "video_id": "VIDX", "predicted_offset": 0,
                "candidate_ids": ""}

    def mk(start, what):
        return {"start": start, "end": None, "how": "number", "what": what, "said": "x"}
    procs = {("2025-2026", "HB1040"): [sitting("executive session", "13:00"),
                                       sitting("public hearing", "09:30")]}
    marks = {"VIDX": {"HB1040": [mk(93.0, ""), mk(161.0, "")]}}
    sts = {s["what"]: s for s in B.bill_stations("HB1040", "2025-2026", procs, {}, marks)}
    assert sts["public hearing"]["start"] == 93.0, (
        f"the first sitting in docket order took {sts['public hearing']['start']}, not 93.0")
    assert sts["executive session"]["start"] is None, (
        f"a later sitting took a marker naming no proceeding: {sts['executive session']['start']}; "
        "one such marker serves one sitting")
    marks = {"VIDX": {"HB1040": [mk(93.0, ""), mk(4000.0, "executive session")]}}
    sts = {s["what"]: s for s in B.bill_stations("HB1040", "2025-2026", procs, {}, marks)}
    assert (sts["public hearing"]["start"], sts["executive session"]["start"]) == (93.0, 4000.0), (
        "a sitting with a marker of its own lost it, or the other lost the fallback: "
        f"{sts['public hearing']['start']}, {sts['executive session']['start']}")
    return "ok", "the first sitting in docket order takes it, a later one none; own markers kept"


@check("markers", "an end a minute after the only mention of the bill is not published",
       needs=("build_site_v2",))
def _invented_end_withheld(build_site_v2):
    """761 published ends were the bill's last mention plus 60 seconds where
    that mention was within 30 seconds of the opening (17 October 2026): the
    three a person timed ran 809, 142 and 227 seconds against 62, 62 and 89.
    segment_markers no longer writes them; the station functions refuse one
    from an older candidate file, on a committee sitting and on the floor."""
    B = build_site_v2
    p = {"bill": "HB122", "body": "H", "committee": "Ways and Means",
         "proceeding": "public hearing", "sched_date": "2026-01-20",
         "sched_time": "10:00", "venue": "LOB 202", "video_id": "VIDX",
         "predicted_offset": 0, "candidate_ids": ""}

    def mk(end, end_from, what="public hearing"):
        return {"VIDX": {"HB122": [{"start": 976.0, "end": end, "end_from": end_from,
                                    "how": "number", "what": what, "said": "x"}]}}
    st = B.station_for_proceeding(p, "HB122", {}, mk(1038.0, "last mention of the bill"))
    assert st["start"] == 976.0 and st["end"] is None, (
        f"an end 62 s after the only mention of the bill was published: {st['end']}")
    assert st["end_from"] == "last mention of the bill", st["end_from"]
    for end, frm in ((1763.0, "last mention of the bill"), (1050.0, "unnamed close")):
        st = B.station_for_proceeding(p, "HB122", {}, mk(end, frm))
        assert st["end"] == end, f"an end {frm} at {end} was withheld: {st['end']}"
    # A hearing takes no vote, so a vote result does not end one; an
    # executive session's does (after review, 17 October 2026).
    st = B.station_for_proceeding(p, "HB122", {}, mk(1100.0, "vote result"))
    assert st["end"] is None, f"a vote result ended a hearing: {st['end']}"
    ex = dict(p, proceeding="executive session")
    st = B.station_for_proceeding(ex, "HB122", {}, mk(1100.0, "vote result", "executive session"))
    assert st["end"] == 1100.0, f"a vote result did not end an executive session: {st['end']}"
    f = {"date": "2026-01-20", "body": "H", "video_id": "VIDX", "motions": [],
         "tallies": [], "kind": "floor debate", "debate_end": None, "window_start": None,
         "precise": False, "whole_video": False, "title": "", "time": "", "venue": ""}
    st = B.station_for_floor(f, "HB122", mk(1038.0, "last mention of the bill", ""))
    assert st["start"] == 976.0 and st["state"] == "floor_dated" and st["debate_end"] is None, (
        f"the floor published an end 62 s after the only mention: {st['state']} {st['debate_end']}")
    return "ok", "a last mention within 30 s of the opening gives no end, committee or floor"


@check("frontend", "a Senate hearing report draws closed on the Reports tab, among the committees' "
       "reports, speakers under their names", needs=("build_site_v2", "senate_hearing_reports"))
def _hearing_report_drawn(build_site_v2, senate_hearing_reports):
    """app.js in node, on two real reports as the build hands them over.

    What a reader must be able to rely on: the report is closed until asked
    for and says how big it is; it says whose summary it is and of what date;
    a legislator is drawn with the site's chip and everybody else as the
    report names them; each section heading and each speaker is a heading
    over their own points; and a report that could not be split is drawn as
    the text it is, with no name put over anything.

    ON THE REPORTS TAB SINCE 19 NOVEMBER 2026 (the owner): among the
    committees' reports, as a "Public Hearing Report" under its committee's
    h2, counted in the tab's count, and no longer on the Videos tab, which
    says where it went where the report dates a sitting itself. Its sections
    are h3s and its speakers h4s.
    """
    ext, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    if not (ext.exists() and stub.exists()):
        return "skip", "app.js or dom_stub.js not here"
    if not shutil.which("node"):
        return "skip", "node is not installed"
    if not Path("tests/senate_hearing_reports.json").exists():
        return "skip", "tests/senate_hearing_reports.json not here"
    B, S = build_site_v2, senate_hearing_reports
    idx = B.speaker_index([{"id": "S23", "name": "Gannon, Bill",
                            "last": "Gannon", "first": "Bill", "chamber": "S",
                            "party_code": "R", "district": "23"}])
    got = _hearing_fixture(S)
    sb11 = B.hearing_report_for_page(got["SB11"][0], idx, S.name_part)[0]
    sb160 = B.hearing_report_for_page(got["SB160"][0], idx, S.name_part)[0]
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(ext)),
                                      encoding="utf-8")
        (root / "stub.js").write_text(_source(stub),
                                      encoding="utf-8")
        (root / "reps.json").write_text(json.dumps([sb11, sb160]),
                                        encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
const src = fs.readFileSync("./page.js", "utf8");
let scope;
try { scope = (0, eval)(src + "; ({hearingReport, renderHearings, renderReports, reportCount});"); }
catch (e) { console.log("LOAD " + e.message); process.exit(1); }
const [a, b] = JSON.parse(fs.readFileSync("./reps.json", "utf8"));
const st = {when:"2025-01-14", time:"09:30", what:"hearing", body:"S",
  committee:"Election Law and Municipal Affairs", state:"located", start:600,
  end:1800, video_id:"VID1", reports:[a]};
// The same hearing with no recording matched to it.
const bare = {when:"2025-01-14", time:"09:30", what:"hearing", body:"S",
  committee:"Election Law and Municipal Affairs", state:"none", reports:[a]};
// A report dated a day the docket has no Senate hearing on: report_station.
const dated = {when:"2025-01-30", time:null, what:"hearing", body:"S",
  committee:"Election Law and Municipal Affairs", state:"novideo",
  video_id:"", dated_by:"report", docket_heard:["2025-01-14"], reports:[a]};
let out;
try {
  out = {one: scope.hearingReport(a), prose: scope.hearingReport(b),
         tab: scope.renderHearings({id:"SB11", n:"SB 11"}, {stations:[st]}),
         novid: scope.renderHearings({id:"SB11", n:"SB 11"},
                                     {stations:[bare]}),
         dated: scope.renderHearings({id:"SB11", n:"SB 11"},
                                     {stations:[dated]}),
         rep: scope.renderReports({id:"SB11", n:"SB 11"}, {stations:[st]}, x => x),
         repbare: scope.renderReports({id:"SB11", n:"SB 11"}, {stations:[bare]}, x => x),
         count: scope.reportCount({stations:[st, dated]})};
} catch (e) { console.log("RENDER " + e.message); process.exit(1); }
fs.writeFileSync("./out.json", JSON.stringify(out));
""", encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True, text=True,
                 timeout=90)
        assert r.returncode == 0, (r.stdout + r.stderr).strip()[:200]
        out = json.loads((root / "out.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    one, prose, tab = out["one"], out["prose"], out["tab"]
    assert re.match(r'\s*<details class="hrep">', one), (
        "the report is not a closed disclosure: " + one[:80])
    summ = re.search(r"<summary>(.*?)</summary>", one, re.S).group(1)
    summ = re.sub(r"<[^>]+>|\s+", " ", summ)
    assert "hearing report" in summ and "4 spoke: 1 for, 3 against" in summ, (
        "the summary does not say what it is and its size: " + summ.strip())
    assert ("Senate Election Law and Municipal Affairs Committee’s hearing "
            "report of") in re.sub(r"\s+", " ", one), (
        "the attribution to the committee's report is missing")
    assert re.search(r'<h4><span class="mchip p-R" translate="no"><a href="legislator/[^"]+">'
                     r'Senator Gannon</a></span><span class="hrrole">Prime '
                     r'Sponsor</span>', one), (
        "Senator Gannon is not drawn with the member chip, in the report's "
        "own words")
    assert "<h4>Liz Tentarelli, League of Women Voters N.H.</h4>" in one, (
        "a member of the public is not named as the report names her")
    # h3 then h4: on the Reports tab the report is under its committee's h2,
    # so its sections are h3s and its speakers h4s, and the outline never
    # skips a level.
    assert one.count("<h3>") >= 3 and one.count("<h4>") == 4 and \
        not re.search(r"<h[25][ >]", one), (
        f"{one.count('<h3>')} section headings and {one.count('<h4>')} "
        "speaker headings, not 3+ and 4")
    assert "<h4>" not in prose and 'class="hrpara"' in prose and \
        "does not make clear who said which part" in prose, (
        "a report kept as text was drawn as speakers, or without saying why")
    # THE REPORTS TAB'S, NOT THE VIDEOS TAB'S: the player alone on Videos,
    # the report a Public Hearing Report on Reports, and counted there.
    rep, repbare = re.sub(r"\s+", " ", out["rep"]), re.sub(r"\s+", " ", out["repbare"])
    assert 'class="player vwplay"' in tab and 'class="hrep"' not in tab, (
        "the Videos tab still draws the hearing report")
    assert re.search(r'<h2 class="sech">Senate Election Law and Municipal Affairs Committee</h2>\s*'
                     r'<p class="repkind"><span class="chip calkind k-hearing">Public Hearing Report</span></p>.*'
                     r'class="hrep"', rep), "the report is not a Public Hearing Report on the Reports tab"
    assert out["count"] == 2, f"the Reports tab counts {out['count']} hearing reports, not 2"
    # "The recording ... is on the Videos tab" is true only where there is
    # one; fifteen reported hearings have none.
    novid = out["novid"]
    assert "the recording of the hearing is on the Videos tab" in rep, (
        "the report of a recorded hearing no longer says where the recording is")
    assert "No recording matched" in novid and 'class="hrep"' not in novid and \
        'class="hrep"' in repbare and "Videos tab" not in repbare, (
        "a report with no recording says there is one, or stayed on the Videos tab")
    # A report under its own date says the date is the report's, gives the
    # docket's, and does not call itself a recording that failed to match.
    dated = re.sub(r"\s+", " ", out["dated"])
    assert "Dated by the committee’s own report" in dated.replace("&rsquo;", "’") \
        and "records one on January 14, 2025" in dated and 'class="hrep"' not in dated \
        and "on the Reports tab" in dated and "No recording matched" not in dated, (
        "a report under its own date does not say where the date came from: "
        + dated[:300])
    return "ok", ("closed, sized, attributed; a member in the chip, the "
                  "public as named; prose kept as prose; on the Reports tab as a "
                  "Public Hearing Report and counted, pointing at the recording only "
                  "where there is one; a report the docket has no hearing for under "
                  "its own date on the Videos tab, saying where the report is")


_SOS_URL = ("https://gc.nh.gov/bill_status/legacy/bs2016/sos_archives.aspx?lsr=21&sy=2025"
            "&sortoption=billnumber&txtsessionyear=2025&txtbillnumber=hb57")


@check("frontend", "a bill's Reports tab is one list, oldest first, a day's public hearing report before its "
                   "executive session report, each saying which it is, all counted, a writer a chip only where "
                   "the build named one, and the committee files linked once under them; a tab with no report "
                   "still links them, counting none")
def _report_groups():
    """The owner, 19 November 2026. The Senate's hearing reports, which the
    Videos tab drew under the player, are the Reports tab's with the
    committees' reports, and the tab counts both. After the first
    screenshots: "one chronological list, oldest at the top and newest at the
    bottom, whatever the type", each report saying what it is -- a chip,
    "Public Hearing Report" or "Executive Session Report", in the colours the
    Videos tab's rows give those meetings -- and on one day the public hearing
    before the executive session. The reporting member is a chip where
    build_site_v2.report_author named one for certain (author_m), else the
    report's words. And once a bill, under the list, the Secretary of State's
    archive of the committee files (sos_archives), marked as leaving the
    site; with no report at all the tab still has it, and its count is none."""
    hr = {"committee": "Senate Judiciary Committee", "heard": "2025-05-15",
          "sections": [{"label": "Testimony", "text": ["Said."]}]}
    d = {"stations": [
            {"when": "2025-01-22", "what": "public hearing", "body": "H", "video_id": "V0",
             "state": "stated", "start": 5, "start_stated": True},
            {"when": "2025-05-15", "what": "hearing", "body": "S", "video_id": "V1", "state": "located",
             "start": 5, "reports": [hr]},
            {"when": "2025-05-20", "what": "hearing", "body": "S", "video_id": "", "state": "novideo",
             "reports": [dict(hr, heard="2025-05-20", subject="AMENDMENT #2025-2183s")]}],
         "reports": [
            {"date": "2025-01-29", "dated": "signed", "majority_recommendation": "OUGHT TO PASS",
             "cite": "HC 11", "source": "House Calendar 11, 2025",
             "reports": [{"side": "Committee", "author": "Rep. David Meuse", "vote_yeas": 16, "vote_nays": 0,
                          "committee": "Criminal Justice and Public Safety", "text": "Reasons.",
                          "author_m": {"label": "Rep. David Meuse (D - Rock 37)", "slug": "david-meuse-rock-37",
                                       "party_code": "D"}}]},
            {"date": "2025-05-20", "dated": "signed", "body": "S", "cite": "SC 22A",
             "majority_recommendation": "OUGHT TO PASS WITH AMENDMENT",
             "reports": [{"side": "Committee", "author": "Senator Smith", "committee": "Judiciary",
                          "vote_yeas": 3, "vote_nays": 2, "text": ""}]}],
         "docket_reports": [{"date": "2025-03-04", "body": "H", "committee": "Criminal Justice and Public Safety",
                             "recommendation": "OUGHT TO PASS", "vote_yeas": 12, "vote_nays": 3}],
         "sos_archives": _SOS_URL}
    b = {"id": "HB57", "n": "HB 57", "term": "2025-2026", "year": 2025}
    js = ("(() => { const b = " + json.dumps(b) + ", d = " + json.dumps(d) + ", u = " + json.dumps(_SOS_URL) + ";"
          " return {full: scope.renderReports(b, d, x => x), count: scope.reportCount(d),"
          " bare: scope.renderReports(b, {sos_archives: u}, x => x), bareCount: scope.reportCount({sos_archives: u}),"
          " nolink: scope.renderReports(b, {reports: d.reports}, x => x),"
          " strip: scope.renderDetail(b, {sos_archives: u})}; })()")
    got = _app_js(js, names=("renderReports", "reportCount", "renderDetail"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    full = re.sub(r"\s+", " ", got["full"])
    # One list: each report's kind and its committee, oldest first; the
    # written report of 29 January before the docket's of 4 March, and on 20
    # May the public hearing's report before the executive session's. Each
    # head reads the committee, its kind's chip, then the date and the
    # calendar (the owner's approval, 19 November 2026).
    said = [(k, w, c) for c, k, w in re.findall(
        r'<h2 class="sech">([^<]+)</h2>\s*<p class="repkind"><span class="chip calkind (k-\w+)">([^<]+)</span></p>'
        r'\s*<div class="repmeta"><span class="secsub">', full)]
    assert said == [("k-exec", "Executive Session Report", "House Criminal Justice and Public Safety Committee"),
                    ("k-exec", "Executive Session Report", "House Criminal Justice and Public Safety Committee"),
                    ("k-hearing", "Public Hearing Report", "Senate Judiciary Committee"),
                    ("k-hearing", "Public Hearing Report", "Senate Judiciary Committee"),
                    ("k-exec", "Executive Session Report", "Senate Judiciary Committee")], (
        f"the reports are not one list, oldest first, each with its kind: {said}")
    days = [full.find(w) for w in ("Jan 29, 2025", "Mar 4, 2025", "May 15, 2025", "Secretary of State&rsquo;s archive")]
    assert -1 not in days and days == sorted(days) and "repgrp" not in full \
        and "Public Hearing Reports" not in full and "Executive Session Reports" not in full, (
            "the tab still draws the two groups, or the days are out of order")
    assert got["count"] == 5, f"the tab counts {got['count']}, not the 3 committee and 2 hearing reports"
    links = re.findall(r'<a href="([^"]+)" target="_blank" rel="noopener">Secretary of State&rsquo;s archive</a>', full)
    assert links == [_SOS_URL.replace("&", "&amp;")] and full.count("sos_archives.aspx") == 1 \
        and full.rindex("</article>") < full.index("sos_archives.aspx"), (
        f"the committee files are not linked once, under the reports, as a link that leaves the site: {links}")
    assert re.search(r'<p class="repby">[^<]*<span class="mchip p-D" translate="no"><a href="legislator/'
                     r'david-meuse-rock-37">Rep\. David Meuse <span class="mtag">\(D - Rock 37\)</span></a></span>', full) \
        and re.search(r'<p class="repby">\s*Senator Smith</p>', full), (
            "a named writer is not a chip, or an unnamed one is not the report's words")
    bare = re.sub(r"\s+", " ", got["bare"])
    assert "No committee report on file." in bare and _SOS_URL.replace("&", "&amp;") in bare and "<h2" not in bare \
        and got["bareCount"] == 0, "a bill with no report lost its link, or counts it as a report"
    assert "Secretary of State" not in got["nolink"], "a bill with no archive address links one"
    assert re.search(r'data-t="3">Reports</button>', got["strip"]), "the Reports tab of a bill with only the link is counted, or gone"
    return "ok", ("one list of five, oldest first, each the committee, its kind's chip, the date and the "
                  "calendar, a day's hearing report before its "
                  "executive session's; 5 counted; the named writer a chip and the unnamed one words; the "
                  "archive linked once under them, and alone, uncounted, on a bill with no report")


@check("build", "a committee report's writer is a member's chip only where one member of the report's "
                "chamber can be meant, with the seat held then; otherwise the report's words",
       needs=("build_site_v2",))
def _report_author_chip(B):
    """The owner, 19 November 2026: "Rep. David Meuse" and "Senator Daryl
    Abbas", the reporting members, were plain text; they are chips "on a
    certain match only. A wrong chip is a factual error; a missing chip is
    not." build_site_v2.report_author takes the movers' rule (mover_member)
    among the same members (mover_pool): the report's chamber's own title, one
    member of that chamber the name can mean, the seat of the term. A shared
    surname, a name of the other chamber, a name without its title and a
    member with no page stay the report's words. After the turn a finished
    term's writer keeps the seat of that term and links to the page as it is
    now."""
    def mem(i, last, first, ch, county, abbr, dist, party):
        return {"id": i, "name": f"{last}, {first}", "chamber": ch, "county": county,
                "county_abbr": abbr, "district": dist, "party_code": party}
    legs = {m["id"]: m for m in (
        mem("1", "Meuse", "David", "H", "Rockingham", "Rock", "37", "D"),
        mem("2", "Abbas", "Daryl", "S", "", "", "22", "R"),
        mem("3", "Lee", "Ann", "H", "Hillsborough", "Hills", "1", "D"),
        mem("4", "Lee", "Bo", "H", "Hillsborough", "Hills", "2", "R"))}
    now = {"1": dict(legs["1"], district="40")}
    keep_slugs, keep_spell = dict(B._OWN_SLUG), list(B._SPELLINGS)
    try:
        B._SPELLINGS[:] = [{}]
        B._OWN_SLUG.clear()
        said = {a: B.report_author(a, ch, legs) for a, ch in (
            ("Rep. David Meuse", "H"), ("Senator Daryl Abbas", "S"), ("Rep. Lee", "H"),
            ("Rep. Ann Lee", "H"), ("Senator Meuse", "S"), ("David Meuse", "H"), ("Rep. Nobody", "H"))}
        B._OWN_SLUG.clear()
        later = B.report_author("Rep. David Meuse", "H", legs, pages=now)
        gone = B.report_author("Senator Daryl Abbas", "S", legs, pages=now)
        written = [{"body": "S", "reports": [{"author": "Senator Daryl Abbas"}]},
                   {"reports": [{"author": "Rep. David Meuse"}, {"author": "Rep. Lee"}]}]
        B._OWN_SLUG.clear()
        B.report_authors(written, legs)
    finally:
        B._OWN_SLUG.clear()
        B._OWN_SLUG.update(keep_slugs)
        B._SPELLINGS[:] = keep_spell
    want = {"Rep. David Meuse": {"label": "Rep. David Meuse (D - Rock 37)", "slug": "david-meuse-rock-37",
                                 "party_code": "D"},
            "Senator Daryl Abbas": {"label": "Sen. Daryl Abbas (R - SD22)", "slug": "daryl-abbas-sd-22",
                                    "party_code": "R"},
            "Rep. Lee": None, "Rep. Ann Lee": {"label": "Rep. Ann Lee (D - Hills 1)", "slug": "ann-lee-hills-1",
                                               "party_code": "D"},
            "Senator Meuse": None, "David Meuse": None, "Rep. Nobody": None}
    bad = [f"{a!r} is {said[a]!r}, not {w!r}" for a, w in want.items() if said[a] != w]
    assert not bad, "; ".join(bad)
    assert later == {"label": "Rep. David Meuse (D - Rock 37)", "slug": "david-meuse-rock-40",
                     "party_code": "D"} and gone is None, (
        f"after the turn the writer is {later} and one with no page {gone}")
    sides = [e.get("author_m", {}).get("slug") for r in written for e in r["reports"]]
    assert sides == ["daryl-abbas-sd-22", "david-meuse-rock-37", None], f"report_authors named {sides}"
    src = _source(_paths.locate("build_site_v2.py"))
    assert "report_authors(rep_written, _mpool, _mpages)" in src, (
        "build_bills no longer names a report's writer among the term's own members")
    return "ok", ("Meuse and Abbas named with the seat of the term, Ann Lee by her full name; a shared "
                  "surname, the other chamber's title, no title and nobody stay words; after the turn "
                  "the seat of the term and the page as it is now, none where there is no page")


@check("build", "the committee files' address is the one the General Court's own page printed, built "
                "only for a year that has ended and no saved page reads, and never fetched")
def _sos_archives_link():
    """The owner, 19 November 2026 ("Link now, trimmed PDFs later"): a bill's
    Reports tab links the Secretary of State's archive page listing its
    committee files. sos_archives.address keeps the manager's rule: a year
    whose saved pages were read after it ended (2016 to 2025 in
    collected/sos_archives.json) gives the address its page printed, or none;
    a later year, once it has ended, the address built by the same scheme
    from the bill's LSR; before then, and before 2016, none. Every address
    in the file is the scheme with the bill's own LSR, year and number, and
    nothing here or in the build asks for one (the parser and build_site_v2
    only write the string)."""
    import sos_archives as SA
    data = {"read": {"2016": "2026-09-11", "2025": "2026-09-03"},
            "links": {"2016": {"SB237": "1002"}, "2025": {"HB57": "21"}}}
    base = "https://gc.nh.gov/bill_status/legacy/bs2016/sos_archives.aspx?"
    cases = {(2016, "SB237", "1002", "2026-11-19"): "lsr=1002&sy=2016&sortoption=billnumber&txtsessionyear=2016&txtbillnumber=sb237",
             (2016, "SB238", "1022", "2026-11-19"): "",
             (2025, "HB57", "0021", "2026-11-19"): "lsr=21&sy=2025&sortoption=billnumber&txtsessionyear=2025&txtbillnumber=hb57",
             (2025, "HB58", "0022", "2026-11-19"): "",
             (2026, "HB1", "2026-0001", "2026-12-31"): "",
             (2026, "HB1", "2026-0001", "2027-01-01"): "lsr=1&sy=2026&sortoption=billnumber&txtsessionyear=2026&txtbillnumber=hb1",
             (2015, "HB1", "0001", "2026-11-19"): "", (2026, "HB1", "", "2027-01-01"): ""}
    bad = [f"{k} gives {SA.address(data, *k)!r}" for k, w in cases.items()
           if SA.address(data, *k) != (base + w if w else "")]
    assert not bad, "; ".join(bad)
    filed = SA.load()
    if not filed:
        return "skip", "collected/sos_archives.json is not here"
    links = filed.get("links") or {}
    per = {y: len(v) for y, v in sorted(links.items())}
    assert set(filed.get("read") or {}) >= {str(y) for y in range(2016, 2026)} and per.get("2016", 0) > 900 \
        and all(re.fullmatch(r"[A-Z]+\d+", b) and re.fullmatch(r"\d+", l) for v in links.values() for b, l in v.items()), (
            f"collected/sos_archives.json is not the saved pages' links of 2016 to 2025: {per}")
    src = _source(_paths.locate("build_site_v2.py"))
    assert re.search(r'"sos_archives": _sos\} if \(_sos := \(""\s+if b\.get\("journal"\) else SA\.address\(\s*'
                     r'sos_files, b\.get\("lsr_year"\), bid, b\.get\("lsr_num"\), sos_day\)\)\)', src), (
        "build_bills no longer gives a bill's record the archive's address by sos_archives.address")
    pages = Path("docket_pages")
    if pages.is_dir():
        r = _run([sys.executable, str(_paths.locate("sos_archives.py")), "--check"], capture_output=True,
                 text=True, timeout=300)
        assert r.returncode == 0, "collected/sos_archives.json no longer agrees with the saved pages: " + r.stdout[-300:]
    return "ok", ("the rule's eight cases; " + ", ".join(f"{y} {n:,}" for y, n in per.items())
                  + " bills linked" + ("; the file agrees with the saved pages" if pages.is_dir()
                                       else "; no saved pages here to read it again from"))


def _journey_bills(B):
    """Three bills of 2025-2026, from their own docket lines: HB 57, signed
    into law; HB 68, killed in the Senate; CACR 13, on its way to the voters.
    Each is put through the builder's own journey, passage and rail, and
    returned as (index row, record) the way build_bills writes them."""
    def ev(date, typ, body, raw):
        return {"date": date, "type": typ, "body": body, "cancelled": False, "raw": raw}

    def hands(*hs):
        return [{"hand": h} for h in hs]
    hb57 = {"stages": hands("H:committee", "H:floor", "S:committee", "S:floor",
                            "H:floor", "G:governor"),
            "events": [
                ev("2025-01-08", "introduced", "H", "Introduced 01/08/2025 and referred to "
                   "Criminal Justice and Public Safety"),
                ev("2025-02-13", "floor", "H", "Ought to Pass: MA VV 02/13/2025"),
                ev("2025-03-06", "introduced", "S", "Introduced 03/06/2025 and Referred to Judiciary"),
                ev("2025-05-22", "amendment", "S", "Committee Amendment # 2025-2308s, RC 16Y-8N, AA; "
                   "05/22/2025"),
                ev("2025-05-22", "floor", "S", "Ought to Pass with Amendment #2025-2308s, RC 16Y-8N, "
                   "MA; OT3rdg; 05/22/2025"),
                ev("2025-06-12", "floor", "H", "Lay HB57 on Table (Rep. Scherr): MF DV 153-190 "
                   "06/12/2025"),
                ev("2025-06-12", "floor", "H", "House Concurs with Senate Amendment 2025-2308s "
                   "(Rep. Roy): MA DV 192-153 06/12/2025"),
                ev("2025-06-26", "enrolled", "S", "Enrolled Adopted, VV, (In recess 06/26/2025)"),
                ev("2025-07-15", "governor", "H", "Signed by Governor Ayotte 07/15/2025; Chapter "
                   "160; eff. 01/11/2026"),
            ]}
    hb68 = {"stages": hands("H:committee", "H:floor", "S:committee", "S:floor",
                            "S:committee", "S:floor"),
            "events": [
                ev("2025-01-08", "introduced", "H", "Introduced 01/08/2025 and referred to "
                   "Education Policy and Administration"),
                ev("2025-03-20", "amendment", "H", "Amendment # 2025-0103h: AA DV 201-160 03/20/2025"),
                ev("2025-03-20", "floor", "H", "Ought to Pass with Amendment 2025-0103h: MA RC "
                   "217-156 03/20/2025"),
                ev("2025-03-20", "introduced", "S", "Introduced 03/20/2025 and Referred to Education"),
                ev("2025-05-01", "floor", "S", "Rereferred to Committee, MA, VV; 05/01/2025"),
                ev("2026-01-07", "floor", "S", "Inexpedient to Legislate, MA, VV ; 01/07/2026"),
            ]}
    cacr13 = {"stages": hands("H:committee", "H:floor", "S:committee"),
              "events": [
                  ev("2026-01-07", "introduced", "H", "Introduced 01/07/2026 and referred to Judiciary"),
                  ev("2026-02-05", "floor", "H", "Ought to Pass: MA DV 325-15 By Necessary "
                     "Three-Fifths Vote 02/05/2026"),
                  ev("2026-02-05", "introduced", "S", "Introduced 02/05/2026 and Referred to "
                     "Executive Departments and Administration"),
                  # Typed "other" by narrative.py, as it is on the site: the
                  # journey reads the line, not the type.
                  ev("2026-03-26", "other", "S", "Ought to Pass, RC 23Y-1N, MA, by Necessary 3/5; "
                     "OT3rdg; 03/26/2026"),
              ]}
    out = []
    for bid, narr, kind, status, chapter in (
            ("HB57", hb57, "law", "Signed into law", "160"),
            ("HB68", hb68, "done", "Killed", ""),
            ("CACR13", cacr13, "adopted",
             "Passed both chambers, goes to the voters in November 2026", "")):
        intro, steps = B.journey(narr, bid, [], chapter, "")
        passed = {c for c in "HS" if B.journey_state(steps, c) == "p"}
        acted = list(dict.fromkeys(s["body"] for s in steps if s["body"] in "HS"))
        rail = B.passage(narr["stages"], kind, status, bid, passed, acted)
        why = B.journey_disagrees(steps, kind, status, rail, bid)
        assert not why, f"{bid}: the journey and the rail {rail!r} disagree: {why}"
        jrail = B.journey_rail(intro, steps, rail, bid, status)
        for s in steps:
            s.pop("short", None)
            s.pop("effective", None)
        row = {"id": bid, "n": re.sub(r"(\d)", r" \1", bid, count=1), "title": "a bill",
               "year": 2025, "term": "2025-2026", "kind": kind, "status": status,
               "passage": rail, "committees": [], "sponsor": "",
               "rail": B.index_rail(jrail)}
        # The record's stops carry no words once the row has them, as
        # build_bills writes it: the page says each in its `say`.
        for s in jrail:
            s.pop("short", None)
        # The status page's per-chamber fields, which the records still
        # carry: the page must not draw them. Without them here, a page that
        # drew the House Status and Senate Status rows again passed.
        out.append((row, {"journey": {"steps": steps, "rail": jrail},
                          "chapter": chapter, "next_step": status,
                          "facts": {"house_status": "PASSED/ADOPTED WITH AMENDMENT",
                                    "senate_status": "INEXPEDIENT TO LEGISLATE"}}))
    return out


@check("status", "the journey reads each decision as the docket records it",
       needs=("build_site_v2",))
def _journey_reads(build_site_v2):
    """Every line below is a real docket row. Each case is a line the
    journey once read as the opposite of what the docket says, or with a day
    the docket does not give -- found in review on 24 September, when How it
    got here was still a branch."""
    B = build_site_v2

    def ev(body, date, raw, typ="floor", **kw):
        return {"body": body, "date": date, "raw": raw, "type": typ, "cancelled": False, **kw}

    def run(bid, *evs, chapter="", law="", term=""):
        intro, steps = B.journey({"events": list(evs)}, bid, [], chapter, law, term)
        return intro, [(s["date"], s["body"], s["act"], s["text"]) for s in steps]

    bad = []

    def want(got, expect, what):
        if got != expect:
            bad.append(f"{what}: {got!a}")

    # A SECOND COMMITTEE, ANY SECOND COMMITTEE. HB 493 of 2025 was approved
    # and sent on; the House never passed it.
    want(run("HB493",
             ev("H", "2025-03-13", "Amendment # 2025-0715h: AA VV 03/13/2025", "amendment"),
             ev("H", "2025-03-13", "Ought to Pass with Amendment 2025-0715h: MA VV 03/13/2025"),
             ev("H", "2025-03-13", "Referred to Executive Departments and Administration "
                "03/13/2025", "rereferred"),
             ev("H", "2025-04-10", "Inexpedient to Legislate: MA DV 193-177 04/10/2025"))[1],
         [("2025-03-13", "H", "referred", "Approved with an amendment and sent to Executive "
           "Departments and Administration on a voice vote"),
          ("2025-04-10", "H", "killed", "Killed, 193–177")], "HB493 2025")
    # THE AMENDMENT GOES TO FINANCE WITH THE BILL. SB 538 of 2026's House
    # stop read "voice vote" beside the Senate refusing the House amendment.
    want(run("SB538",
             ev("H", "2026-04-23", "Amendment # 2026-1453h: AA VV 04/23/2026", "amendment"),
             ev("H", "2026-04-23", "FLAM # 2026-1578h (Rep. Vose): AA VV 04/23/2026", "other"),
             ev("H", "2026-04-23", "Ought to Pass with Amendment 2026-1453h and 2026-1578h: MA "
                "VV 04/23/2026"),
             ev("H", "2026-04-23", "Referred to Finance 04/23/2026", "rereferred"),
             ev("H", "2026-05-14", "Ought to Pass: MA VV 05/14/2026"))[1],
         [("2026-04-23", "H", "referred", "Approved with an amendment and sent to Finance on a "
           "voice vote"),
          ("2026-05-14", "H", "passed", "Passed with an amendment on a voice vote")],
         "SB538 2026")
    # And an amendment in the clause that passes the bill, before the third
    # reading or after the motion, or in a row entered after the passage's.
    want(run("HB117", ev("S", "1999-04-22", "Sen. Larsen Floor Amendment {0965}, AA, VV, "
                                            "OT3rdg, RC 14Y-8N, MA", "amendment"))[1],
         [("1999-04-22", "S", "passed", "Passed with an amendment, 14–8")], "HB117 1999")
    want(run("HB626", ev("S", "1999-06-29", "Ought to Pass, MA, VV, Sen. Brown Floor Amendment, "
                                            "{1865}, RC 14Y-8N, AA"))[1],
         [("1999-06-29", "S", "passed", "Passed with an amendment, 14–8")], "HB626 1999")
    want(run("SB336", ev("S", "2002-02-20", "Sen. Fernald Moved Ought to Pass, RC 22y - 1n, MA"),
             ev("S", "2002-02-20", "Sen. Francoeur Floor Amendment {2837}, (New Title), RC 13y "
                "- 10n, AA", "amendment"))[1],
         [("2002-02-20", "S", "passed", "Passed with an amendment, 22–1")], "SB336 2002")
    # But not the count of the Ought to Pass where a passage of the day names
    # the amendment and its own vote: HB 723 of 1997 passed the Senate amended
    # on a voice vote, after the 19-5 that came before the floor amendment
    # (Docket_db_1997-1998.txt 8365-8367, as the history holds them).
    want(run("HB723", ev("S", "1997-05-20", "OTP MA RC(19-5); SEN F KING FL AM<1494>, "
                         "WITHDRAWN; SEN SQUIRES", motion="MA"),
             ev("S", "1997-05-20", "FL AM<1504>, AA VV; SEN RUBENS MOVED LOT, ML VV; PASSED "
                "WITH AM VV; SJ19,P373-377 + 387", motion="MA"))[1],
         [("1997-05-20", "S", "passed", "Passed with an amendment on a voice vote")],
         "HB723 1997")
    # Not a motion to pass it amended that failed before the one that carried.
    want(run("HB546", ev("S", "1999-06-22", "Ought to Pass W/Amendment, {1683}, RC 6Y-16N, AF, "
                                            "Ought to Pass, MA, VV, OT3rdg, RC 22Y-1N, MA"))[1],
         [("1999-06-22", "S", "passed", "Passed, 22–1")], "HB546 1999")
    # Unless its chair waived the referral: HB 243 of 2025 passed the House.
    want(run("HB243",
             ev("H", "2025-02-20", "Ought to Pass: MA VV 02/20/2025"),
             ev("H", "2025-02-20", "Referred to Criminal Justice and Public Safety 02/20/2025",
                "rereferred"),
             ev("H", "2025-02-20", "Referral Waived by Committee Chair per House Rule 47(f) "
                "02/20/2025", "other"))[1],
         [("2025-02-20", "H", "passed", "Passed on a voice vote")], "HB243 2025")
    # 1989's clerks wrote the referral before the passage, or days after.
    want([x[2] for x in run("HB115",
                            ev("S", "1989-03-16", "REFERRED TO FINANCE/APPROP", "rereferred"),
                            ev("S", "1989-03-16", "PASSED/ADOPTED"),
                            ev("S", "1989-05-04", "PASSED/ADOPTED"))[1]],
         ["referred", "passed"], "HB115 1989")
    want([x[2] for x in run("HB396",
                            ev("S", "1989-04-21", "PASSED/ADOPTED"),
                            ev("S", "1989-04-25", "REFERRED TO APPROP/FINANCE", "rereferred"),
                            ev("S", "1989-05-09", "PASSED/ADOPTED"))[1]],
         ["referred", "passed"], "HB396 1989")
    # AN ENROLMENT'S "ADOPTED" IS THE ENROLMENT'S, not a committee report's:
    # HB 1243 of 2006, killed by that reading on the bill that became law.
    want(run("HB1243",
             ev("H", "2006-02-23", "Maj Rprt: ITL for March 8 (vote 12-7; RC)", "report",
                recommendation="Inexpedient to Legislate", side="Majority"),
             ev("H", "2006-03-09", "Passed with AM, MA, VV"),
             ev("H", "2006-05-31", "Enrolled Bill Amendment{2230}; Adopted", "amendment"))[1],
         [("2006-03-09", "H", "passed", "Passed with an amendment on a voice vote")],
         "HB1243 2006")
    want(run("HB235", ev("S", "2000-03-13", "Committee Report Inexpedient to Legislate; SC17, "
                         "Pg.5", "report", recommendation="Inexpedient to Legislate", side=""),
             ev("S", "2000-03-16", "Sen Below Floor Amendment{3818} RC 15Y- 8N, MA; "
                "OT3rdg, MA,VV", "other"),
             ev("S", "2000-05-11", "Enrolled Bill; Adopted", "enrolled"))[1],
         [("2000-03-16", "S", "passed", "Passed with an amendment on a voice vote")],
         "HB235 2000")
    # A VOTE TO SUSPEND THE RULES decides that the rules are suspended.
    want(run("CACR21", ev("H", "2020-06-12", "Rules Suspension to consider at the present time "
                          "without required referral to commmittee, public hearing and report "
                          "from committee, and if passed, allow for immediate third reading MF "
                          "lacking necessary 2/3 RC 197-143 06/11/2020", "other"))[1],
         [], "CACR21 2020")
    want(run("HB1", ev("H", "1997-06-10", "REPS WHEELER & BURLING MOVED TO SUSP RULES FOR CONF "
                       "COMM REPORT, ML RC(221-135)"))[1], [], "HB1 1997")
    # ...except where what it allowed is a second committee.
    want([x[2:] for x in run("HB1162", ev("H", "1996-02-21", "COMM AM, AA VV; PASSED WITH AM "
                                           "VV; REPS A TORR & TROMBLY SUSP"),
                              ev("H", "1996-02-21", "RULES TO REF TO FINANCE, MA 2/3VV; "
                                 "HJ30,P1078", "other"))[1]],
         [("referred", "Approved with an amendment and sent to Finance on a voice vote")],
         "HB1162 1996")
    # A LAW WITH SEVERAL EFFECTIVE DATES HAS NO ONE DATE TO STATE, and states
    # each, part by part (the audit of 7 October 2026, cause 12): 92 of the
    # 649 laws of 2025-2026 stated none at all.
    want(run("HB131", ev("H", "2026-07-02", "Signed by Governor Ayotte 07/02/2026; Chapter 205; "
                         "eff. I. Sec 3 1/1/2027 II. Rem eff 8/1/2026", "governor"),
             chapter="205")[1][-1][3],
         "Chapter 205, in effect in parts: section 3 on Jan 1, 2027, the rest on Aug 1, 2026",
         "HB131 2026")
    want(run("HB337", ev("H", "2007-07-20", "Signed by the Governor on 07/13/07; Chapter 0296; "
                         "I. Sections 5 & 6 Eff. 07/01/2011", "governor"),
             ev("H", "2007-07-20", "II. Remainder Eff. 08/12/2007", "other"),
             chapter="296")[1][-1][3],
         "Chapter 296, in effect in parts: sections 5 and 6 on Jul 1, 2011, the rest on Aug 12, "
         "2007", "HB337 2007")
    # Docket.txt's own rows: HB 1300's line, SB 56's three rows, and a part
    # that waits on another section.
    want(run("HB1300", ev("H", "2026-07-15", "Signed by Governor Ayotte 07/15/2026; Chapter 324; "
                          "eff. I. Sec 3 eff 01/01/2032 II. Rem eff 09/01/2026", "governor"),
             chapter="324")[1][-1][3],
         "Chapter 324, in effect in parts: section 3 on Jan 1, 2032, the rest on Sep 1, 2026",
         "HB1300 2026")
    want(run("SB56", ev("S", "2026-07-15", "Signed by the Governor on 07/15/2026; Chapter 335",
                        "governor"),
             ev("S", "2026-07-15", "I. Section 24 Effective 07/01/2031", "other"),
             ev("S", "2026-07-15", "II. Remainder Effective 07/01/2026", "other"),
             chapter="335")[1][-1][3],
         "Chapter 335, in effect in parts: section 24 on Jul 1, 2031, the rest on Jul 1, 2026",
         "SB56 2026")
    want(run("HB557", ev("H", "2025-08-01", "Signed by Governor Ayotte 08/01/2025; Chapter 281; "
                         "eff. I. Sec 1 & 2 eff as provided in Sec 3 II. Rem eff 08/01/2025",
                         "governor"), chapter="281")[1][-1][3],
         "Chapter 281, in effect in parts: sections 1 and 2 as section 3 provides, the rest on "
         "Aug 1, 2025", "HB557 2025")
    # The day straight after the chapter, with no "eff" (HB 227 of 2025).
    want(run("HB227", ev("H", "2025-06-02", "Signed by Governor Ayotte 06/02/2025; Chapter 59; "
                         "08/01/2025", "governor"), chapter="59")[1][-1][3],
         "Chapter 59, in effect Aug 1, 2025", "HB227 2025")
    # A part that does not say plainly what it covers states none of them:
    # "I Sec 1-3-5" (HB 655 of 2025). "Sec I" is section 1 (HB 1584 of 2026,
    # "I. Section 1 effective October 13, 2026" in its chaptered text); the
    # rest of what the effective dates review of 8 October 2026 taught is
    # in _effective_parts_read below.
    want(run("HB655", ev("H", "2025-07-15", "Signed by Governor Ayotte 07/15/2025; Chapter 202; "
                         "eff. I Sec 1-3-5 eff 09/13/2025 II. Rem eff 07/15/2025  HJ 18",
                         "governor"), chapter="202")[1][-1][3], "Chapter 202", "HB655 2025")
    want(run("HB1584", ev("H", "2026-07-15", "Signed by Governor Ayotte 07/15/2026; Chapter 328; "
                          "eff. I. Sec I eff 10/13/2026 II. Rem eff 01/01/2027", "governor"),
             chapter="328")[1][-1][3],
         "Chapter 328, in effect in parts: section 1 on Oct 13, 2026, the rest on Jan 1, 2027",
         "HB1584 2026")
    # EVERY ROW THAT CARRIES THE GOVERNOR'S ON, not the first seven (the
    # review of 8 October 2026). HB 2 of 2007's row and the fifteen after it
    # in Docket_db_2007-2008.txt run to part XVI; read to part VIII, the stop
    # stated eight parts as though they were all of it and left out the
    # remainder's 1 Jul 2007. Part IV also names Sections 50-51 after its RSA,
    # which a label of the RSA alone would have left to "the rest".
    hb2 = ["II. Sections 14-22, 24, and 45-47 Eff 07/01/08",
           "III. Sections 25, 67, and 112-116 Eff 06/30/07",
           "IV. RSA 485-A:17,II(b) as inserted by Section 30 and Sections 50-51 Eff 01/01/08",
           "V. Section 33 Eff 07/01/10", "VI. Section 37 Eff 07/01/09",
           "VII. Sections 49, 65-66, and 117-119 Eff 06/29/07", "VIII. Section 48 Eff 07/01/18",
           "IX. Section 98 Eff 06/30/11", "X. Section 123 Eff 07/01/11",
           "XI. Sections 128, 131, 134, 137, 140, 143, 146, 150, and 154 Eff 07/06/07",
           "XII. Sections 129, 132, 135, 138, 141, 144, 147, 151, and 155 Eff 01/04/08",
           "XIII. Sections 130, 133, 136, 139, 142, 145, 148, 152, and 156 Eff 01/02/09",
           "XIV. Section 166 Eff 04/01/08", "XV. Section 26 Eff 07/01/13",
           "XVI. Remainder Eff 07/01/07"]
    want(run("HB2", ev("H", "2007-07-05", "Signed by the Governor on 06/29/07; Chapter 0263; "
                       "I. Section 5 Eff 07/01/09 at 12:01 a.m.", "governor"),
             *[ev("H", "2007-07-05", x, "other") for x in hb2], chapter="263")[1][-1][3],
         "Chapter 263", "HB2 2007")
    want(run("HB2", ev("H", "2007-07-05", "Signed by the Governor on 06/29/07; Chapter 0263; "
                       "I. Section 5 Eff 07/01/09 at 12:01 a.m.", "governor"),
             ev("H", "2007-07-05", hb2[2], "other"),
             ev("H", "2007-07-05", "II. Remainder Eff 07/01/07", "other"),
             chapter="263")[1][-1][3], "Chapter 263", "HB2 2007, part IV")
    want(run("SB151", ev("S", "2025-07-15", "Signed by the Governor on 07/15/2025; Chapter 0238; "
                         "Effective 01/01/2026", "governor"), chapter="238")[1][-1][3],
         "Chapter 238, in effect Jan 1, 2026", "SB151 2025")
    # THE DAY THE LINE GIVES, not the day it was entered.
    want(run("HB101", ev("H", "2007-06-12", "Signed by the Governor on 06/11/07; Eff. Date "
                         "08/10/07; Chapter 0069", "governor"))[1][0][0], "2007-06-11",
         "HB101 2007's signature")
    want(run("HR17", ev("H", "2025-02-25", "Introduced pursuant to Rule 36c 02/20/2025", "other"),
             ev("H", "2025-03-06", "Ought to Pass: MA VV 03/06/2025"))[0], "2025-02-20",
         "HR17 2025's introduction")
    want(run("SCR1", ev("S", "2023-02-09", "Sen. Birdsell Moved Introduction; 2/3 necessary, MA, "
                        "VV; 02/09/2023"),
             ev("S", "2023-02-09", "Ought to Pass : MA, VV; OT3rdg; 02/09/2023"),
             ev("H", "2023-03-16", "Introduced (in recess of) 03/16/2023 and referred to "
                "Election Law", "introduced"))[0], "2023-02-09", "SCR1 2023's introduction")
    want(run("HB1650", ev("S", "2022-01-05", "Ought to Pass : MA, VV; OT3rdg; Read a Third Time, "
                          "and Final Passage in the early session, MA, VV; 01/05/2022"),
             ev("H", "2022-01-10", "Adopted and read a 3rd time MA VV 01/05/22", "other"))[1],
         # The House first: the bill's number names it, whatever order the
         # two rows of that day were entered in.
         [("2022-01-05", "H", "passed", "Passed on a voice vote"),
          ("2022-01-05", "S", "passed", "Passed on a voice vote")], "HB1650 2022")
    # And the sitting a row was entered ahead of: HB 1573 of 2024's Senate
    # adopted the report on 13 June (Senate Journal 17), not the 12th, when
    # it did not sit. Not a weekend: SB 152 of 2017's row states a Sunday.
    want(run("HB1573", ev("S", "2024-06-12", "Conference Committee Report #2024-2290c , Adopted, "
                                             "VV; 06/13/2024", "other"), term="2023-2024")[1],
         [("2024-06-13", "S", "conf_adopted", "Adopted the conference report on a voice vote")],
         "HB1573 2024")
    want(run("SB152", ev("S", "2017-03-16", "Ought to Pass with Amendment 2017-0797s, MA, VV; "
                                            "OT3rdg; 03/19/2017"), term="2017-2018")[1][0][0],
         "2017-03-16", "SB152 2017")
    # Nor after the governor acted: HB 377 of 2025's Senate adoption of 26
    # June was entered on 3 November, three months after the signature.
    want([x[:3] for x in run(
        "HB377", ev("H", "2025-06-26", "Conference Committee Report 2025-2809c: Adopted, RC "
                                       "202-161 06/26/2025", "other"),
        ev("H", "2025-08-01", "Signed by Governor Ayotte 08/01/2025", "governor"),
        ev("S", "2025-11-03", "Conference Committee Report # 2025-2809c; RC 16Y-8N, Adopted; "
                              "06/26/2025", "other"), term="2025-2026")[1]],
         [("2025-06-26", "H", "conf_adopted"), ("2025-06-26", "S", "conf_adopted"),
          ("2025-08-01", "G", "signed")], "HB377 2025")
    # THE OPPOSITE OF THE DOCKET. The chair's ruling sustained is no veto.
    want([x[1:3] for x in run("HB1075", ev("H", "1998-05-14", "RULING OF CHR", "amendment"),
                              ev("H", "1998-05-14", "SUSTAINED VV; PASSED WITH AM RC(233-122); "
                                 "REP ROOT MOVED TO RECONSIDER, ML VV"))[1]],
         [("H", "passed")], "HB1075 1998")
    want(run("SB69", ev("S", "2001-06-26", "Sen. Pignatelli Moved Non Adopt Conference Committee "
                        "Report RC 17Y-7N, Non Adopt", "other"))[1],
         [("2001-06-26", "S", "conf_rejected", "Rejected the conference report, 17–7")],
         "SB69 2001")
    # AN ANSWER DONE IN RECESS goes after the amendment it answers, with no
    # day, where the docket dates it by the sitting the chamber recessed: HB
    # 2 of 2015's House refused the Senate's amendments a day before the
    # Senate made them. HB 25 of 1999's refusal, dated the day of the House's
    # own passage, took that passage's place.
    want(run("HB2", ev("H", "2015-04-01", "Ought to Pass with Amendment #1163h, 1224h, 1162h, "
                                          "1196h: MA RC 194-179"),
             ev("H", "2015-06-03", "House Non-Concurs and Requests Committee of Conference (Rep "
                "Hinch): MA VV (in recess of 6/3/2015)"),
             ev("S", "2015-06-04", "Ought to Pass with Amendments 1986s, 2005, and 2076s, RC "
                "14Y-10N, MA; OT3rdg"))[1],
         [("2015-04-01", "H", "passed", "Passed with an amendment, 194–179"),
          ("2015-06-04", "S", "passed", "Passed with an amendment, 14–10"),
          ("", "H", "nonconcurred", "Refused the Senate's amendment and asked for a committee "
           "of conference on a voice vote")], "HB2 2015")
    want([x[:3] for x in run(
        "HB25", ev("H", "1999-06-23", "Fin Comm Am, AA VV; Passed with Am RC(273-18)"),
        ev("S", "1999-06-24", "Senator Larsen offered a floor amendment (1818), AA, VV; OT3rdg, "
           "RC 17Y - 4N, MA"),
        ev("H", "1999-06-23", "6/23/1999 House Nonc with Sen Am req Conf Comm, Rep French MA"))[1]],
         [("1999-06-23", "H", "passed"), ("1999-06-24", "S", "passed"),
          ("", "H", "nonconcurred")], "HB25 1999")
    # Not a week or more before the passage: HB 109 of 1999's refusal of 30
    # March answers a Senate passage of 25 March, not the one of October.
    want([x[:3] for x in run(
        "HB109", ev("H", "1999-03-30", "Rep Kurk moved to nonconcur with Sen Am, MA RC(211-168)"),
        ev("S", "1999-10-22", "Sen. Below Floor Amendment {2166} New Title RC, (15-8) AA, OT3rdg, "
           "MA, VV", "amendment"))[1]],
         [("1999-03-30", "H", "nonconcurred"), ("1999-10-22", "S", "passed")], "HB109 1999")
    # One made in recess answers the passage the other chamber made again
    # after reconsidering the first: HB 1409 of 2014.
    want([x[:3] for x in run(
        "HB1409", ev("S", "2014-05-15", "Ought to Pass with Amendment 1733s, NT, MA, RC 23-1; "
                                        "OT3rdg"),
        ev("H", "2014-05-15", "Rep. Chandler moved to Non-Concur with Senate AM and request C of "
           "C; MA VV (In recess of 5/15/2014)"),
        ev("S", "2014-05-16", "Sen. Bradley Moved Reconsideration on Ought to Pass with "
           "Amendment, MA, VV"),
        ev("S", "2014-05-16", "Ought to Pass with Amendment 1733s, NT, MA, RC 24-0; OT3rdg"))[1]],
         [("2014-05-15", "S", "passed"), ("2014-05-16", "S", "passed"),
          ("", "H", "nonconcurred")], "HB1409 2014")
    # A DECISION RECONSIDERED ON A LATER DAY says so. HB 628 of 1994's Senate
    # refused a conference and, five days later, reconsidered and acceded;
    # SCR 6 of 2006's House killed it 149-147 and a week later reconsidered.
    want(run("HB628", ev("S", "1994-05-12", "SEN REFUSED TO ACCEDE TO REQ FOR CONF COMM, SEN "
                                            "MACDONALD MA VV", "other"),
             ev("S", "1994-05-17", "SEN MACDONALD MOVED TO RECONSIDER REQ TO ACCEDE, MA VV"),
             ev("S", "1994-05-17", "SEN ACCEDED TO REQ FOR CONF COMM, SEN MACDONALD MA VV"))[1],
         [("1994-05-12", "S", "conf_refused", "Refused a committee of conference on a voice "
           "vote, reconsidered on May 17")], "HB628 1994")
    want(run("SCR6", ev("H", "2006-04-12", "ITL, MA, RC (149-147)"),
             ev("H", "2006-04-19", "(Rep. Graham) Reconsideration, MA, Div (174-160)", "other"),
             ev("H", "2006-04-19", "ITL, ML, RC (144-190)"),
             ev("H", "2006-04-19", "Passed with AM {1725h}, MA, RC (198-140)"))[1],
         [("2006-04-12", "H", "killed", "Killed, 149–147, reconsidered on Apr 19"),
          ("2006-04-19", "H", "passed", "Adopted with an amendment, 198–140")], "SCR6 2006")
    # Not a decision the motion does not name, nor, where it names none, one
    # the chamber has voted past: HB 1025 of 1992's House reconsidered its
    # request for a new conference, and HR 1 of 1997's an amendment to its
    # rules.
    want([x[3] for x in run("HB1025", ev("H", "1992-05-06", "CONF COMM REPORT ADOPTED VV"),
                            ev("H", "1992-05-07", "REP GROSS MOVED TO RECONSIDER REQ FOR NEW "
                               "CONF COMM, MA VV; REP GROSS MOVED TO DISCHARGE CONF COMM & REQ "
                               "NEW CONF COMM, ML VV"))[1]],
         ["Adopted the conference report on a voice vote"], "HB1025 1992")
    want([x[3] for x in run("HR1", ev("H", "1996-12-04", "29(B), AA VV; AM ADOPTED VV; PASSED WITH "
                                                         "AM VV"),
                            ev("H", "1997-01-08", "RULES COMM AM<0024>, AA VV", "amendment"),
                            ev("H", "1997-01-29", "SEC 35(B), AL VV; SEC 45(C), AL RC(186-186); "
                               "REP CHAMPAGNE MOVED TO RECONSIDER, MA RC(211-160)"))[1]],
         ["Adopted with an amendment on a voice vote"], "HR1 1997")
    # Nor one the chamber took something else up ahead of that day: a
    # suspension of the rules it refused (HB 322 of 1991), a motion with no
    # vote beside it (SB 796 of 1994), a concurrence in the same clause (SB
    # 326 of 2000). Each marked a decision of weeks before as reconsidered.
    want(run("HB322", ev("S", "1991-05-28", "COMM AM, AA VV; PASSED WITH AM VV; SJ28,P467-468 + 479"),
             ev("H", "1991-05-29", "HOUSE NONC WITH SEN AM REQ CONF COMM, REP D. SYTEK MA VV; HJ86"),
             ev("H", "1991-06-27", "REPS GROSS & CHAMBERS MOVED TO SUSP RULES, ML DIV(213-115); "
                "HJ96, P2092"),
             ev("H", "1991-06-27", "REP KURK MOVED TO RECONSIDER, MA VV; REPS GROSS & CHAMBERS SUSP"),
             ev("H", "1991-06-27", "RULES TO CONSIDER, MA DIV(230-105); CONF COMM REPORT ADOPTED VV; "
                "HJ96,P2092"))[1],
         [("1991-05-28", "S", "passed", "Passed with an amendment on a voice vote"),
          ("1991-05-29", "H", "nonconcurred", "Refused the Senate's amendment and asked for a "
           "committee of conference on a voice vote"),
          ("1991-06-27", "H", "conf_adopted", "Adopted the conference report on a voice vote")],
         "HB322 1991")
    want([x[3] for x in run("SB796", ev("H", "1994-04-14", "COMM AM, AA VV; PASSED WITH AM AND REF "
                                                           "TO APPROP VV; HJ49,P1592"),
                            ev("H", "1994-05-11", "REP LARSON SUBST ITL; VOTE TAKEN, INCORRECTLY, "
                               "ON COMM AM; REP D HALL MOVED TO RECONSIDER, MA VV; REP LARSON SUBST "
                               "ITL, MA VV; ITL REPORT ADOPTED VV; HJ64,P2054-2055"))[1]],
         ["Approved with an amendment and sent to Appropriations on a voice vote",
          "Killed on a voice vote"], "SB796 1994")
    want([x[3] for x in run("SB326", ev("S", "2000-03-23", "Ought to Pass with Amendment{3829},"
                                                           "[New Title], AA, VV; OT3rdg, MA, VV"),
                            ev("S", "2000-05-18", "Sen. Squires Concur with House Amendment{4347}; "
                               "Sen. Squires Motion Reconsideration, MA,VV"),
                            ev("S", "2000-05-18", "Sen. Squires Non Concur with House Amt{4347},"
                               "Request C of C; MA, VV"))[1]],
         ["Passed with an amendment on a voice vote", "Refused the House's amendment and asked "
          "for a committee of conference on a voice vote"], "SB326 2000")
    # But a suspension refused on an earlier day is not what is reconsidered:
    # HB 462 of 1989's House had its rules suspended on 25 April and
    # reconsidered the recommittal of 16 March.
    want([x[3] for x in run("HB462", ev("H", "1989-03-16", "RE-REFERRED TO CON & STAT; HJ47, P1266; "
                                                           "DUE 11/23/89"),
                            ev("H", "1989-04-13", "REPS PHELPS & CHAMBERS MOVED SUSP JNT RULES, ML "
                               "DIV(200-145)"),
                            ev("H", "1989-04-25", "REPS PALUMBO & CHAMBERS SUSP OF RULES MA VV BY "
                               "NEC 2/3"),
                            ev("H", "1989-04-25", "REP FLANAGAN RECONSIDER MA VV; REP FLANAGAN SUB "
                               "OTP/AM MA VV"))[1]][:1],
         ["Sent back to committee, reconsidered on Apr 25"], "HB462 1989")
    # A THIRD READING RECONSIDERED AND READ AGAIN THAT DAY is the passage it
    # was: HB 1282 of 2012 kept its 180-133 and no "reconsidered". HB 1659,
    # divided out of that third reading and sent to a second committee, was
    # not passed by the vote on the bills that remained. And a referral after
    # a passage the chamber reconsidered is not that passage's (HB 1331 of
    # 1990).
    want(run("HB1282", ev("H", "2012-03-14", "Ought to Pass (Rep L.Ober): MA RC 180-133"),
             ev("H", "2012-03-15", "Reconsider Third Reading Motion of March 14 (Reps Jasper and "
                "Norelli): MA VV"),
             ev("H", "2012-03-15", "Third Reading: MA VV"))[1],
         [("2012-03-14", "H", "passed", "Passed, 180–133")], "HB1282 2012")
    want(run("HB1659", ev("H", "2012-03-14", "Ought to Pass with Amendment #0089h: MA RC 189-151"),
             ev("H", "2012-03-15", "Reconsider Third Reading Motion of March 14 (Reps Jasper and "
                "Norelli): MA VV"),
             ev("H", "2012-03-15", "Divide Third Reading Motion to Remove HB1659 (Reps Jasper and "
                "Norelli): Speaker Ordered", "other"),
             ev("H", "2012-03-15", "Remaining Bills to Third Reading (Reps Jasper and Norelli): "
                "MA VV"),
             ev("H", "2012-03-15", "HB1659 Referred to Criminal Justice and Public Safety: Without "
                "Objection", "other"),
             ev("H", "2012-03-28", "Ought to Pass with Amendment #1482h: MA RC 185-138"))[1],
         [("2012-03-14", "H", "passed", "Passed with an amendment, 189–151, reconsidered on "
           "Mar 15"),
          ("2012-03-28", "H", "passed", "Passed with an amendment, 185–138")], "HB1659 2012")
    want(run("HB1331", ev("S", "1990-03-29", "PASSED/ADOPTED"),
             ev("S", "1990-04-03", "MOTION OF RECONSIDERATION/ADOPTED", "other"),
             ev("S", "1990-04-03", "REFERRED TO FINANCE (RULE 24)", "rereferred"))[1],
         [("1990-03-29", "S", "passed", "Passed, reconsidered on Apr 3")], "HB1331 1990")
    # A semicolon in a list of amendments is not the end of the motion: HB
    # 1636 of 2018's refusal lost its count, and the failed motion before it
    # read as a refusal too.
    want(run("HB1636", ev("H", "2018-05-10", "House Non-Concurs with Senate Amendment 1427s; "
                          "1851s; 1898s; and 1925s and Requests CofC (Rep. Ladd): MF RC 168-173 "
                          "05/10/2018"),
             ev("H", "2018-05-10", "House Non-Concurs with Senate Amendment 1427s; 1851s; 1898s; "
                "and 1925s (Rep. Kurk): MA RC 180-163 05/10/2018"))[1],
         [("2018-05-10", "H", "nonconcurred", "Refused the Senate's amendment, 180–163")],
         "HB1636 2018")
    want([x[2] for x in run("HB705",
                            ev("H", "2003-06-24", "Conf Comm Report Defeated RC(159-172)", "other"),
                            ev("H", "2003-06-24", "Rep Mock moved to Reconsider, MA VV"),
                            ev("H", "2003-06-24", "Conf Comm Report Adopted VV"))[1]],
         ["conf_adopted"], "HB705 2003")
    # The journal a row cites names the chamber: the Senate's passage of HB
    # 1113 of 1994, filed under the House. But not a chamber the bill had
    # not reached: HB 366 of 1995 was killed by the House, whatever its
    # row cites.
    want(run("HB1113", ev("H", "1994-02-08", "PASSED WITH AM; HJ19,P553 + 587", cite="HJ 19"),
             ev("S", "1994-02-10", "INTRODUCED AND REF TO JUDICIARY; SJ5,P123", "introduced",
                cite="SJ 5"),
             ev("H", "1994-04-21", "PASSED VV; SJ12,P305 + 318", cite="SJ 12"))[1],
         [("1994-02-08", "H", "passed", "Passed with an amendment"),
          ("1994-04-21", "S", "passed", "Passed on a voice vote")], "HB1113 1994")
    want(run("HB366", ev("H", "1995-01-05", "INTRODUCED AND REF TO JUDICIARY & F L; HJ11,P152",
                         "introduced", cite="HJ 11"),
             ev("H", "1995-02-15", "ITL REPORT ADOPTED; SJ25,P532", cite="SJ 25"))[1],
         [("1995-02-15", "H", "killed", "Killed")], "HB366 1995")
    # The citation is the typo here: filed under the Senate, the day of the
    # Senate committee's report, and cited to the House Journal.
    want(run("HB426", ev("H", "1993-03-03", "PASSED WITH AM; HJ31,P697-699 + 735", cite="HJ 31"),
             ev("S", "1993-03-11", "INTRODUCED AND REF TO ENVIRONMENT; SJ9,P201", "introduced",
                cite="SJ 9"),
             ev("S", "1993-03-24", "COMM REPORT  OTP  MAR25", "report"),
             ev("S", "1993-03-25", "PASSED VV; HJ46,P217 + 221", cite="HJ 46"))[1],
         [("1993-03-03", "H", "passed", "Passed with an amendment"),
          ("1993-03-25", "S", "passed", "Passed on a voice vote")], "HB426 1993")

    # A BILL KILLED BY RULE AT ADJOURNMENT DIED THE DAY THE ROW STATES, not
    # the day it was entered: 427 of 2019-2020's were entered in September
    # 2021 and read as killed a year after the term ended. HB 201's row
    # states 2021 too, and neither day is in the term, so it goes undated.
    died = "Killed under Senate Rule 3-23, still on the table at adjournment"
    want(run("HB1496", ev("S", "2020-06-16", "Introduced 06/16/2020, and Laid on Table, MA, VV; "
                                             "06/16/2020"),
             ev("S", "2021-09-09", "Inexpedient to Legislate, Senate Rule 3-23, Adjournment "
                                   "09/16/2020", "other"), term="2019-2020")[1],
         [("2020-06-16", "S", "tabled", "Laid on the table on a voice vote"),
          ("2020-09-16", "S", "died", died)], "HB1496 2020")
    want(run("HB201", ev("S", "2020-06-16", "Vacated from Committee and Laid on Table, MA, VV; "
                                            "06/16/2020"),
             ev("S", "2021-09-09", "Inexpedient to Legislate, Senate Rule 3-23, Adjournment "
                                   "09/16/2021", "other"), term="2019-2020")[1][-1],
         ("", "S", "died", died), "HB201 2020")
    # And an introduction whose row states the clerk's year is dated in the
    # year the row was entered, where that is in the term and not after the
    # row: each of these is the day of the Journal the row cites.
    want(run("SB53", ev("S", "1999-01-28", "Introduction and referring Public Institutions, "
                                           "Health and Human Services 1/28/98", "introduced"),
             term="1999-2000")[0], "1999-01-28", "SB53 1999 introduced")
    want(run("HR6", ev("H", "2021-01-07", "Introduced and Adopted VV 01/06/2020", "other"),
             term="2021-2022"),
         ("2021-01-06", [("2021-01-06", "H", "passed", "Adopted on a voice vote")]),
         "HR6 2021")
    # And the adoption the same row records, where the day is a clause of
    # its own: SR 8 of 2017, Senate Journal 5 of 9 February 2017.
    want(run("SR8", ev("S", "2017-02-15", "Introduced and Adopted, VV; 02/09/2016", "other"),
             term="2017-2018"),
         ("2017-02-09", [("2017-02-09", "S", "passed", "Adopted on a voice vote")]), "SR8 2017")
    # Not a day after the row, nor one it cannot be: HB 214 of 2019's
    # "Introduced 01/02/2014", entered on 27 December 2018, is no day of 2018.
    want(run("HB214", ev("H", "2018-12-27", "Introduced 01/02/2014 and referred to Legislative "
                                            "Administration", "introduced"),
             term="2019-2020")[0], "", "HB214 2019 as entered")

    # A CONFERENCE REPORT FILED IS NOT A VOTE, and "As Passed by the House
    # {2199}" names the version it proposes. SB 32 of 2008 read as the House
    # passing the bill; HB 429 of 2007 as the Senate passing it twice.
    want(run("SB32", ev("H", "2008-05-30", "Conference Committee Report #2084, As Passed by "
                                           "the Senate: Filed", "other"),
             ev("H", "2008-06-04", "Conference Committee Report #2084 Failed, VV", "other"))[1],
         [("2008-06-04", "H", "conf_rejected", "Rejected the conference report on a voice vote")],
         "SB32 2008")
    want(run("HB429", ev("S", "2007-06-21", "Conference Committee Report; As Passed by the "
                                            "House {2199}, Filed", "other"),
             ev("S", "2007-06-27", "As Passed by the House {2199} RC 13Y-11N, Adopted",
                "other"))[1],
         [("2007-06-27", "S", "conf_adopted", "Adopted the conference report, 13–11")],
         "HB429 2007")
    want(run("SB103", ev("H", "2021-06-16", "Conference Committee Report #2021-1946c Filed "
                                            "06/10/2021; Version Adopted by Senate", "other"))[1],
         [], "SB103 2021")
    # A conference line no passage precedes is no conference: SB 200 of 1989
    # was killed in February, and its docket has one adopted in May.
    want(run("SB200", ev("S", "1989-02-08", "COMMITTEE REPORT ITL", "report",
                         recommendation="Inexpedient to Legislate", side=""),
             ev("S", "1989-02-09", "ITL REPORT ADOPTED"),
             ev("S", "1989-05-24", "CONF COMM REPORT ADOPTED"))[1],
         [("1989-02-09", "S", "killed", "Killed")], "SB200 1989")
    # A vote the clerk wrote in the same row as the filing is still a vote.
    want(run("HB25", ev("S", "1991-06-26", "CONF COMM REPORT (S AM + NEW AM) FILED; CONF COMM "
                                           "REPORT ADOPTED RC(19-3); SJ33,P661-665"))[1],
         [("1991-06-26", "S", "conf_adopted", "Adopted the conference report, 19–3")],
         "HB25 1991")

    # THE CHAPTER IS NOT A THIRD VOTE ON THE VETO. HB 455 of 2019's House
    # overrode once, 247-123.
    want([s[:3] for s in run(
        "HB455", ev("H", "2019-05-03", "Vetoed by Governor Sununu 05/03/2019", "governor"),
        ev("H", "2019-05-23", "Veto Overridden 05/23/2019: RC 247-123 by Required Two-Thirds "
                              "Vote", "veto_override"),
        ev("S", "2019-05-30", "Notwithstanding the Governor's Veto, Shall HB 455-FN Become Law: "
                              "RC 16Y-8N, Veto Overridden by necessary two-thirds vote; "
                              "05/30/2019", "other"),
        ev("H", "2019-05-30", "Veto Overriden 05/30/2019: Eff: 05/30/2019; Chapter 42",
           "other"), chapter="42")[1]],
         [("2019-05-03", "G", "vetoed"), ("2019-05-23", "H", "override"),
          ("2019-05-30", "S", "override"), ("", "L", "law")], "HB455 2019")

    # AN ANSWER AFTER WHAT IT ANSWERS, whichever chamber's row was entered
    # first that day: HB 10 of 2025's House concurrence (1:52) and the
    # Senate's passage with that amendment (2:48).
    want([s[1:3] for s in run(
        "HB10", ev("H", "2025-06-05", "House Concurs with Senate Amendment 2025-2150s (Rep. "
                                      "DeSimone): MA RC 210-160 06/05/2025"),
        ev("S", "2025-06-05", "Ought to Pass with Amendments #2025-2150s and #2025-2646s, MA, "
                              "VV; OT3rdg; 06/05/2025"))[1]],
         [("S", "passed"), ("H", "concurred")], "HB10 2025 order")

    # A VOTE TO OVERRIDE IS COUNTED FOR THE OVERRIDE, and a failed
    # supermajority says what it fell short of.
    want(run("HB358", ev("H", "2025-12-17", "Veto Sustained 12/17/2025: RC 176-175 Lacking "
                                            "Necessary Two-Thirds Vote"))[1][-1][3],
         "Veto sustained, 176–175 to override, short of two thirds", "HB358 2025")
    want(run("CACR4", ev("H", "2026-01-07", "Ought to Pass with Amendment 2025-2937h: MF RC "
                                            "184-157 Lacking Necessary Three-Fifths Vote "
                                            "01/07/2026"))[1][-1][3],
         "Failed to pass, 184–157, short of three fifths", "CACR4 2026")
    assert not bad, "; ".join(bad)
    return "ok", ("second committees, a waived referral, enrolments, rules suspensions, "
                  "several effective dates, the day a line states, a chair's ruling, a "
                  "motion not to adopt, a reconsidered defeat, a kill at adjournment, a "
                  "conference report filed and a chaptered override, each as the docket "
                  "has it")


@check("status", "a law's Law stop is dated by its chaptered text's own Effective Date lines before "
                 "the docket's line, which can be another bill's, and by the docket's where the "
                 "text has none it reads", needs=("build_site_v2",))
def _law_stop_from_chaptered_text(build_site_v2):
    """HB 1184 of 2026's page said its sections took effect on 1 January 2027
    and 2028: its docket row is HB 1102's, overridden the same day, and its
    chaptered text says section 3 on August 19, 2027 and the rest on October
    18, 2026, as RSA 635:2-a's source note does (found 24 October 2026 by
    the Laws pages, which read the text first: build_rsa, Bills.effect).
    journey() reads the text's last lines first now, with the Laws pages'
    reader (law_effect.chaptered_parts), and the docket's line where the
    text has no such lines or one the reader does not read. Measured on the
    laws of 2023-2024 and 2025-2026 that day: 1,223 of 1,273 read the same
    either way, and 42 change, among them 19 dates the docket's line had
    wrong and 9 laws that stated no date at all.

    Held here: a record shaped like HB 1184's, a law in effect on one day,
    a part that names a statute in the law's own words (HB 464 of 2025) and
    one that names sections of the act beside it (HB 318 of 2024), and the
    three cases where the docket's reading stays: no text, a text with no
    such lines, and a line the reader does not read. And the build hands
    journey() the bill's text."""
    B = build_site_v2

    def law(bid, raw, chapter, text):
        ev = {"body": "H", "date": "2026-07-02", "raw": raw, "type": "governor", "cancelled": False}
        steps = B.journey({"events": [ev]}, bid, [], chapter, "", "", text=text)[1]
        st = [s for s in steps if s["body"] == "L"][-1]
        return st["text"], st.get("effective", "")

    bad = []

    def want(got, expect, what):
        if got != expect:
            bad.append(f"{what}: {got!a}, not {expect!a}")

    other = ("Signed by Governor Ayotte 07/02/2026; Chapter 339;eff.I. Sec 2 eff 1/1/27 II. Sec 3 "
             "eff 1/1/27 III. Rem eff 1/1/28")
    want(law("HB1184", other, "339", "x\nVETOED July 10, 2026 / Veto Overridden August 19, 2026.\n"
             "Effective:\nI. Section 3 effective August 19, 2027\nII. Remainder effective "
             "October 18, 2026"),
         ("Chapter 339, in effect in parts: section 3 on Aug 19, 2027, the rest on Oct 18, 2026", ""),
         "HB1184's own lines, not HB1102's")
    one = "Signed by Governor Ayotte 05/14/2025; Chapter 17; eff. 07/13/2025"
    want(law("HB140", one, "17", "17:2 Effective Date. This act shall take effect January 1, 2026.\n"
             "Approved: May 14, 2025\nEffective Date: January 01, 2026"),
         ("Chapter 17, in effect Jan 1, 2026", "2026-01-01"), "HB140's one day")
    want(law("HB464", "Signed by Governor Ayotte 08/01/2025; Chapter 277", "277",
             "x\nApproved: August 01, 2025\nEffective Date:\nI. Sections 9 & 10 effective December "
             "31, 2025\nII. RSA 654:12 VI as inserted by section 5 effective February 1, 2026\nIII. "
             "Remainder effective September 30, 2025"),
         ("Chapter 277, in effect in parts: sections 9 and 10 on Dec 31, 2025, RSA 654:12 VI as "
          "inserted by section 5 on Feb 1, 2026, the rest on Sep 30, 2025", ""), "HB464's statute part")
    want(law("HB318", "Signed by Governor Sununu 08/01/2024; Chapter 317", "317",
             "x\nApproved: August 01, 2024\n\nEffective Date:\n\nI. RSA 597:2-b, I-a & Sections "
             "16-17 effective July 1, 2024\n\nII. Section 11 effective July 1, 2025\n\nIII. "
             "Remainder effective January 1, 2025"),
         ("Chapter 317, in effect in parts: RSA 597:2-b, I-a and sections 16 and 17 on Jul 1, 2024, "
          "section 11 on Jul 1, 2025, the rest on Jan 1, 2025", ""), "HB318's statute and sections")
    docket = "Signed by Governor Ayotte 07/02/2026; Chapter 205; eff. I. Sec 3 1/1/2027 II. Rem eff 8/1/2026"
    kept = ("Chapter 205, in effect in parts: section 3 on Jan 1, 2027, the rest on Aug 1, 2026", "")
    want(law("HB131", docket, "205", ""), kept, "no text: the docket's")
    want(law("HB131", docket, "205", "3 Effective Date. This act shall take effect 60 days after its "
             "passage."), kept, "a text with no Effective Date lines: the docket's")
    want(law("HB131", docket, "205", "x\nEffective Date:\nI. Sec 20, except RSA 275:82 eff July 1, "
             "2025\nII. RSA 275:82 eff July 1, 2026"), kept, "a line not read: the docket's")
    want(law("HB131", docket, "205", "x\nEffective Date:\nI. Section 3 effective January 1, 2027"),
         kept, "one part that is not the whole act: the docket's")
    import build_rsa as BR
    import law_effect as LE
    want([BR.part_name(p_) for p_ in LE.chaptered_parts(
        "x\nEffective Date:\nI. RSA 597:2-b, I-a & Sections 16-17 effective July 1, 2024\nII. "
        "Remainder effective January 1, 2025")],
         ["RSA 597:2-b and sections 16 and 17 of the act", "the rest"], "the Laws pages' HB318")
    src = _source("src/pages/build_site_v2.py")
    if not re.search(r"journey\(narr, bid, rcs, chapter,.{0,300}?text=\(btext or \{\}\)\.get\(\"body\"",
                     src, re.S):
        bad.append("the build no longer hands journey() the bill's text")
    assert not bad, "; ".join(bad)
    return "ok", ("the chaptered text's lines first (HB 1184's own, not HB 1102's), the law's own "
                  "words for a statute, and the docket's where the text has none it reads")


@check("status", "a law's dates in effect are read part by part, and only where its lines "
                 "give each", needs=("build_site_v2",))
def _effective_parts_read(build_site_v2):
    """The effective dates review of 8 October 2026: seven laws of 2025-2026
    stated no date in effect, and of the forms they showed, the ones the
    line itself settles are read, each checked against the law's chaptered
    text, while the ones it does not settle state none, as before.

    Read: parts past VIII (HB 282 of 2025 runs to XII), a range written with
    spaces ("27 - 33"), "Sec I" alone as section 1, and the governor's row in
    full beside chapters.json's copy of it, which keeps 200 characters. Not
    read, on purpose: "Sec 1-3-5" (one range or two numbers), "20256" (a
    year the line does not give), the glued "PIIIII." (HB 307 of 2025), and
    the Article 44 line's "June 6", which is the day HB 1256 of 2026 became
    law, not the day it took effect -- its text says 60 days after.

    And what the same review found the reader had been stating wrongly: a
    part it could not split was left before the first one it could and
    dropped, so SB 530 of 2008, SB 313 of 2018 and SB 91 of 2021 told
    sections in effect on other days as "the rest"; and the same row read
    twice, once with the docket's double spaces, made SB 21 of 2011's one
    part into two and dated it by the other's day."""
    B = build_site_v2

    def ev(body, date, raw, typ="other"):
        return {"body": body, "date": date, "raw": raw, "type": typ, "cancelled": False}

    def law(bid, *evs, chapter, line=""):
        steps = B.journey({"events": list(evs)}, bid, [], chapter, line, "")[1]
        return [s["text"] for s in steps if s["body"] == "L"][-1]

    bad = []

    def want(got, expect, what):
        if got != expect:
            bad.append(f"{what}: {got!a}")

    # Docket.txt line 10744, as the docket writes it; narratives.json keeps
    # the row with its spaces closed up, and chapters.json its first 200
    # characters, which end "V. Sec 13 21 &".
    hb282 = ("Signed by Governor Ayotte 06/27/2025; Chapter 142; I. Sec 4 8 9 & 43 eff 1/1/26.  "
             "II. Sec 2 10 18 & 44 eff 7/1/26.  III. Sec 3 11 19 40 & 45 eff 7/1/27.  IV. Sec 12 "
             "20 & 46 eff 7/1/28.  V. Sec 13 21 & 47 eff 7/1/29.  VI. Sec 14 22 & 48 eff 7/1/30.  "
             "VII. Sec 15 23 & 49 eff 7/1/31.  VIII. Sec 16 24 & 50 eff 7/1/32.  IX. Sec 17 25 27 "
             "& 51 eff 7/1/33.  X. Sec 26 27 - 33 35 - 38 & 52 eff 7/1/34.  XI. Sec 1 eff "
             "8/26/25.  XII. Rem eff 7/1/25.")
    want(law("HB282", ev("H", "2025-06-27", " ".join(hb282.split()), "governor"),
             chapter="142", line=hb282[:200]),
         "Chapter 142, in effect in parts: sections 4, 8, 9 and 43 on Jan 1, 2026, sections 2, "
         "10, 18 and 44 on Jul 1, 2026, sections 3, 11, 19, 40 and 45 on Jul 1, 2027, sections "
         "12, 20 and 46 on Jul 1, 2028, sections 13, 21 and 47 on Jul 1, 2029, sections 14, 22 "
         "and 48 on Jul 1, 2030, sections 15, 23 and 49 on Jul 1, 2031, sections 16, 24 and 50 "
         "on Jul 1, 2032, sections 17, 25, 27 and 51 on Jul 1, 2033, sections 26, 27 to 33, 35 "
         "to 38 and 52 on Jul 1, 2034, section 1 on Aug 26, 2025, the rest on Jul 1, 2025",
         "HB282 2025")
    # The 200 characters alone are a line cut short, and state none.
    want(law("HB282", chapter="142", line=hb282[:200]), "Chapter 142", "HB282 2025, cut short")
    # "Section I" on a row of its own: Docket_db_2007-2008.txt lines 22435-22437.
    want(law("HB1508", ev("H", "2008-06-06", "Signed by the Governor 06/03/2008; Chapter 0118",
                          "governor"),
             ev("H", "2008-06-06", "I. Section I Effective 07/01/2008"),
             ev("H", "2008-06-06", "II. Remainder Effective 06/03/2008"), chapter="118"),
         "Chapter 118, in effect in parts: section 1 on Jul 1, 2008, the rest on Jun 3, 2008",
         "HB1508 2008")
    # Docket_2019-2020.txt line 4889, past its first 200 characters: the RSA
    # part ends at its date, not at "13/".
    hb1558 = ("Signed by Governor Sununu 07/29/2020; Chapter 38; I. RSA 193:13/ I-X as inserted "
              "by Sec. 1 Eff: 07/01/2021 II. Sec. 3-5 & 8-10 Eff: 07/01/2020 III.Sec 6 & 7 Eff: "
              "06/30/2020 IV. Sec. 17 and 31-36 Eff: 01/01/2021 V. Sec. 11-16 and 18-30 Eff: "
              "09/27/2020 VI. Rem. Eff: 07/29/2020")
    want(law("HB1558", ev("H", "2020-07-29", hb1558, "governor"), chapter="38",
             line=hb1558[:200]),
         "Chapter 38, in effect in parts: RSA 193:13/ I-X on Jul 1, 2021, sections 3 to 5 and 8 "
         "to 10 on Jul 1, 2020, sections 6 and 7 on Jun 30, 2020, sections 17 and 31 to 36 on "
         "Jan 1, 2021, sections 11 to 16 and 18 to 30 on Sep 27, 2020, the rest on Jul 29, 2020",
         "HB1558 2020")

    # A PART NOT READ IS NOT "THE REST". Docket_2021-2022.txt line 11477,
    # Docket_db_2007-2008.txt lines 26882-26887, Docket_2021-2022.txt lines
    # 19464-19469.
    want(law("HB481", ev("H", "2022-06-24", "Signed by Governor Sununu 06/24/2022; Chapter 250; "
                         "eff. I. Sec4 eff 6/24/22 II. Sec 5 and 6 eff 7/1/25 III Rem eff 7/1/22",
                         "governor"), chapter="250"), "Chapter 250", "HB481 2022")
    want(law("SB530", ev("S", "2008-07-16", "Signed by the Governor On 07/11/08", "governor"),
             ev("S", "2008-07-16", "I. Paragraph I of Section 6 Eff. 06/30/08"),
             ev("S", "2008-07-16", "II. Paragraph II of Section 6 Eff. 07/01/13"),
             ev("S", "2008-07-16", "III. Section 5 Eff. 07/01/09 at 12:01 a.m"),
             ev("S", "2008-07-16", "IV. Remainder Eff. 07/11/08"), chapter="384",
             line="Chapter 0384"), "Chapter 384", "SB530 2008")
    want(law("SB91", ev("S", "2021-08-26", "Signed by the Governor on 08/26/2021; Chapter 0228",
                        "governor"),
             *[ev("S", "2021-08-30", x) for x in (
                 "Part I Effective 10/25/2021", "Part II Effective 08/26/2021",
                 "Part III Effective 10/25/2021", "Part IV. I. Section 2 Effective 11/01/2021",
                 "Part IV. II. Remainder Effective 08/26/2021")], chapter="228"),
         "Chapter 228", "SB91 2021")
    # ONE ROW, ONE READING, whatever its spaces. Docket_db_2011-2012.txt line
    # 6805 writes "0195I.  Section"; narratives.json closes the space up.
    sb21 = ("Signed by the Governor on 06/14/10; Chapter 0195I.  Section 2 & 3 Effective as Prov. "
            "in Sec. 4II. Remainder Effective 08/13/11")
    want(law("SB21", ev("S", "2011-06-14", " ".join(sb21.split()), "governor"), chapter="195",
             line=sb21), "Chapter 195", "SB21 2011")
    # And one part is not parts: HB 25 of 2023's row names part I alone
    # (Docket_2023-2024.txt line 10300).
    want(law("HB25", ev("H", "2023-06-30", "Signed by Governor Sununu 06/30/2023; Chapter 113; "
                        "Eff: I. Sec 24 eff 6/30/23", "governor"), chapter="113",
             line="Signed by Governor Sununu 06/30/2023; Chapter 113; Eff: I. Sec 24 eff "
                  "6/30/23 HJ 17"), "Chapter 113", "HB25 2023")
    # The same part again on a row of its own, which is no copy of the
    # governor's row by its start, is still the one part (the review of the
    # effective dates fix, 8 October 2026).
    want(law("HB25", ev("H", "2023-06-30", "Signed by Governor Sununu 06/30/2023; Chapter 113; "
                        "Eff: I. Sec 24 eff 6/30/23", "governor"),
             ev("H", "2023-06-30", "I. Sec 24 eff 6/30/23"), chapter="113"),
         "Chapter 113", "HB25 2023, its part on a row of its own")

    # WHAT THE LINE DOES NOT SETTLE states none: Docket.txt lines 24269, 9567
    # and 24272, the rows as the docket has them.
    want(law("HB1388", ev("H", "2026-06-05", "Signed by Governor Ayotte 06/05/2026; Chapter 121; "
                          "eff.06/05/20256", "governor"), chapter="121"),
         "Chapter 121", "HB1388 2026")
    want(law("HB307", ev("H", "2025-05-29", "Signed by Governor Ayotte 05/29/2025; Chapter 46; "
                         "I. Sec 1 & 3 eff. as in sec 5 P I   II. Sec 2 & 4 eff as in sec 5 "
                         "PIIIII. Rem eff 07/28/2025", "governor"), chapter="46"),
         "Chapter 46", "HB307 2025")
    want(law("HB1256", ev("H", "2026-06-05", "Law Without Signature 06/05/2026; Chapter 128; "
                          "eff.Enacted in accordance with Article 44 Part II of the N.H. "
                          "Constitutionwithout the signature of the governor June 6",
                          "unsigned_law"), chapter="128"),
         "Chapter 128", "HB1256 2026")

    # The narrow edges, on the list reader itself: "Sec I" is section 1
    # alone, and a dash between three numbers is not read.
    for s, expect in (("I", "section 1"), ("II", ""), ("I-3", ""), ("1-3-5", ""),
                      ("26 27 - 33 35 - 38 & 52", "sections 26, 27 to 33, 35 to 38 and 52"),
                      ("4 8 9 & 43", "sections 4, 8, 9 and 43"), ("5 - 8", "sections 5 to 8")):
        want(B._j_sections(s), expect, f"_j_sections({s!r})")
    assert not bad, "; ".join(bad)
    return "ok", ("parts to XII, spaced ranges, \"Sec I\" and a row read whole are read; a "
                  "part not read, a row read twice, a typed year, a glued numeral and the "
                  "Article 44 day state none")


@check("status", "a law in effect in many stages is one line on its page and on its rail, and "
                 "the Laws pages still read every part", needs=("build_site_v2", "build_rsa"))
def _law_in_stages_shown(build_site_v2, build_rsa):
    """The audit of 25 October 2026 (S7): HB 282 of 2025's Law stop was 117
    words of section numbers in How it got here and in the rail's label. It
    reads "Chapter 142, in effect in stages from Jul 1, 2025 to Jul 1, 2034"
    now (law_in_stages, the step's `shown`), and only what is displayed
    changed: the step's `text` keeps every part, which build_rsa reads to
    say when each section of a statute changes. Two parts, and a part dated
    only "as section 3 provides", stay as they were. Fails if the long line
    comes back on the page or the rail, or if the Laws pages lose a part."""
    B = build_site_v2
    hb282 = ("Signed by Governor Ayotte 06/27/2025; Chapter 142; I. Sec 4 8 9 & 43 eff 1/1/26. "
             "II. Sec 2 10 18 & 44 eff 7/1/26. III. Sec 3 11 19 40 & 45 eff 7/1/27. IV. Sec 12 "
             "20 & 46 eff 7/1/28. V. Sec 13 21 & 47 eff 7/1/29. VI. Sec 14 22 & 48 eff 7/1/30. "
             "VII. Sec 15 23 & 49 eff 7/1/31. VIII. Sec 16 24 & 50 eff 7/1/32. IX. Sec 17 25 27 "
             "& 51 eff 7/1/33. X. Sec 26 27 - 33 35 - 38 & 52 eff 7/1/34. XI. Sec 1 eff "
             "8/26/25. XII. Rem eff 7/1/25.")
    ev = {"body": "H", "date": "2025-06-27", "raw": hb282, "type": "governor", "cancelled": False}
    steps = B.journey({"events": [ev]}, "HB282", [], "142", hb282[:200], "")[1]
    law = [s for s in steps if s["body"] == "L"][-1]
    want = "Chapter 142, in effect in stages from Jul 1, 2025 to Jul 1, 2034"
    assert law.get("shown") == want, f"HB 282 of 2025's Law step is shown as {law.get('shown')!r}"
    assert law["text"].startswith("Chapter 142, in effect in parts: sections 4, 8, 9 and 43 on Jan 1, "
                                  "2026,") and law["text"].endswith("the rest on Jul 1, 2025"), (
        f"the Law step's own words changed, and the Laws pages read them: {law['text'][:120]!r}")
    parts = build_rsa.journey_parts({"journey": {"steps": steps}})
    assert parts and len(parts) == 12, (
        f"the Laws pages read {len(parts or ())} parts of HB 282's law, not its twelve")
    rail = B._journey_rail("2025-01-08", steps, "Hpppp", "HB282")
    said = [s["say"] for s in rail if s["stop"] == "Law"]
    assert said == [want], f"the rail's Law stop says {said!r}"
    for chapter, parts_, expect in (
            ("118", "section 1 on Jul 1, 2008, the rest on Jun 3, 2008", ""),
            ("281", "sections 1 and 2 as section 3 provides, sections 4 and 5 on Jul 1, 2009, "
                    "section 6 on Jan 1, 2010, the rest on Jun 3, 2008", ""),
            ("38", "RSA 193:13/ I-X on Jul 1, 2021, sections 3 to 5 and 8 to 10 on Jul 1, 2020, "
                   "sections 6 and 7 on Jun 30, 2020, the rest on Jul 29, 2020",
             "Chapter 38, in effect in stages from Jun 30, 2020 to Jul 1, 2021")):
        got = B.law_in_stages(chapter, parts_)
        assert got == expect, f"Chapter {chapter}'s parts are shown as {got!r}, not {expect!r}"
    for name in ("src/pages/app.js", "src/pages/print.js"):
        src = _source(name)
        assert "esc(s.shown||s.text||\"\")" in src, (
            f"{name} draws How It Got Here from the step's full text, not the line it is shown as")
    return "ok", (f"HB 282 of 2025: \"{want}\" on the page and the rail, its twelve parts still "
                  "the Laws pages'; two parts, and a part with no day, as they were")


@check("status", "an amendment offered before it was adopted keeps its outcome",
       needs=("build_site_v2",))
def _amendment_offered_first(build_site_v2):
    """The Senate enters a floor amendment when it is offered and again when
    it carries. HB 266 of 2026 (Chapter 4), in the order the clerk entered
    them: "Sen. Birdsell Floor Amendment # 2026-0720s; 02/19/2026" at 10:23,
    then "... # 2026-0720s, AA, VV" at 10:26. Keeping only the first row that
    names a number, as bill_amendments did, the Bill Text tab lost "adopted"
    and "Voice Vote" on three amendments the Senate adopted -- once the
    history kept the clerk's order of a day's rows. HB 718 of 2025's was
    offered on 15 May and adopted on 5 June, and the day beside "adopted" is
    the day it was."""
    B = build_site_v2

    def ev(date, raw, motion="", vote_kind=""):
        return {"type": "amendment", "body": "S", "date": date, "raw": raw,
                "amendment": "", "amend_kind": "Floor Amendment", "motion": motion,
                "vote_kind": vote_kind, "mover": "Sen. Birdsell", "cancelled": False}

    got = B.bill_amendments({"events": [
        ev("2026-02-19", "Sen. Birdsell Floor Amendment # 2026-0720s; 02/19/2026"),
        ev("2026-02-19", "Sen. Birdsell Floor Amendment # 2026-0720s, AA, VV; 02/19/2026",
           "AA", "VV")]}, {})
    assert [(a["num"], a["adopted"], a["vote_kind"], a["date"]) for a in got] == [
        ("2026-0720s", True, "VV", "2026-02-19")], f"HB 266's 2026-0720s reads {got!a}"
    got = B.bill_amendments({"events": [
        ev("2025-05-15", "Sen. Innis Floor Amendment # 2025-2080s; 05/15/2025"),
        ev("2025-06-05", "Sen. Innis Floor Amendment # 2025-2080s, AA, VV; 06/05/2025",
           "AA", "VV")]}, {})
    assert [(a["adopted"], a["date"]) for a in got] == [(True, "2025-06-05")], (
        f"HB 718's 2025-2080s reads {got!a}")
    return "ok", "an offered amendment takes the outcome, and the day, of the row that decided it"


@check("frontend", "the Law line of How it got here has its day in the date column, like every other line",
       needs=("build_site_v2",))
def _law_line_dated(B):
    """The owner, 10 November 2026: HB 1's Law line read "Chapter 140, in
    effect Jul 1, 2025" with its date column empty. The build gives a
    single-day law's step its date and the words "Chapter 140, in effect"
    (law_line_dated); `text` keeps the day for the Laws pages, a law in parts
    or stages keeps no day, and app.js draws the date column from `date`."""
    day = "2025-07-01"
    one = B.law_line_dated({"act": "law", "date": "", "effective": day, "short": "Chapter 140",
                            "text": "Chapter 140, in effect Jul 1, 2025"})
    assert one["date"] == day and one["shown"] == "Chapter 140, in effect", f"a law line is not dated: {one}"
    assert one["text"] == "Chapter 140, in effect Jul 1, 2025", "the Laws pages' own text changed"
    parts = B.law_line_dated({"act": "law", "date": "", "effective": "", "short": "Chapter 142",
                              "text": "Chapter 142, in effect in parts: ..."})
    assert parts["date"] == "" and "shown" not in parts, "a law in parts was given a day"
    staged = B.law_line_dated({"act": "law", "date": "", "effective": "", "short": "Chapter 142",
                               "shown": "Chapter 142, in effect in stages", "text": "..."})
    assert staged["date"] == "" and staged["shown"] == "Chapter 142, in effect in stages", "a staged law changed"
    html = _app_js("scope.journeyList({id: 'HB1'}, {journey: {steps: [" + json.dumps(one) + "]}})",
                   names=("journeyList",))
    if html is None:
        return "skip", "node or app.js is not here"
    assert '<span class="jt">Chapter 140, in effect</span>' in html, (
        f"the line's words are not Chapter 140, in effect: {html!a}")
    assert re.search(r'<span\s+class="jd">Jul 1, 2025</span>', html), f"the day is not in the date column: {html!a}"
    return "ok", "a single-day law's line says Chapter N, in effect with its day in the date column; parts and stages unchanged"


@check("frontend", "the History tab of a bill number with a standing note lists the same number in the other "
                   "terms it holds for, newest first, and no other bill's History tab changes",
       needs=("build_site_v2",))
def _history_same_number(B):
    """The owner, 10 November 2026: "the history tab should match prior bills
    for standard ones like HB1, HB2". corrections/bill_notes.json says which
    numbers have a standing meaning and from which term (HB 1 is the budget from
    1993-1994; the HB 1 of 1989-1990 is another bill). same_number_rows gives
    such a bill the same number in its other terms, newest first, never in a
    term before `from`; any other bill nothing. renderRelated draws it under
    "HB 1 in other terms", each row linked to its term's bill with its title and
    outcome chip."""
    notes = {"every_term": {"HB1": {"from": "1993-1994", "label": "The state budget", "note": "x"}}}
    index = [{"term": t, "year": t[:4], "id": b, "n": b[:2] + " " + b[2:], "title": f"title {t}", "chip": "Became Law"}
             for t in ("1989-1990", "1993-1994", "2023-2024", "2025-2026") for b in ("HB1", "HB7")]
    rows = B.same_number_rows(notes, index)
    assert set(rows) == {("1993-1994", "HB1"), ("2023-2024", "HB1"), ("2025-2026", "HB1")}, (
        f"the standing-note bills are not exactly the HB 1s from 1993: {sorted(rows)}")
    assert [r["term"] for r in rows[("2025-2026", "HB1")]] == ["2023-2024", "1993-1994"], (
        "the other terms are not newest first, or one before the note's `from` is listed")
    assert all(r["id"] == "HB1" for rs in rows.values() for r in rs) and ("2025-2026", "HB7") not in rows
    mine = {"id": "HB1", "n": "HB 1", "year": "2025"}
    d = {"same_number": rows[("2025-2026", "HB1")]}
    html = _app_js("(() => { const D = " + json.dumps({"b": mine, "d": d, "e": {}}) + "; return {"
                   "yes: scope.renderRelated(D.b, [], D.d), no: scope.renderRelated(D.b, [], D.e)}; })()",
                   names=("renderRelated",))
    if html is None:
        return "skip", "node or app.js is not here"
    yes = html["yes"]
    assert "HB 1 in other terms" in yes, f"the heading is missing: {yes[:300]!a}"
    assert yes.index('href="bill/2023/hb1"') < yes.index('href="bill/1993/hb1"'), "the rows are not newest first"
    assert "HB 1 of 2023–2024" in yes and "title 2023-2024" in yes and "Became Law" in yes, (
        "a row lacks its term, its title or its outcome chip")
    assert "in other terms" not in html["no"], "a bill with no same-number list has the heading"
    return "ok", "HB 1 lists its other terms from 1993-1994, newest first, linked, with title and chip; HB 7 and bills with no note none"


@check("build", "a CACR with a ballot row is built with the voters' vote, its outcome and its source",
       needs=("build_site_v2",))
def _ballot_built(build_site_v2):
    """build_site_v2 over the fixture with one CACR both chambers passed and a
    ballot_results.json naming it (the review of 5 October 2026): the night
    runs --code alone, and nothing under --code built a page from that file,
    so build_bills could stop attaching the voters' card and every code check
    still passed. Its record must carry the card, its status the two-thirds
    answer and the file it came from, its How it got here end at the voters
    with whose count it is, and its index row's rail at the Voters stop.

    WHOSE, BY THE ROW (7 October 2026): the card carries the row's source's
    name and cite, and How it got here says "(the Secretary of State's
    count)" for a row read from sos.nh.gov. A second CACR whose docket prints
    a referendum count of its own that is not the row's -- CACR 22 of 1998's
    159,439 against the Manual's 169,439, read through NHPR's scan -- ends
    with the docket's line, saying it is the docket's and what the
    Secretary of State's is."""
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py is not here"
    root = Path(tempfile.mkdtemp(prefix="gr-ballot-"))
    try:
        _site_fixture(root)

        def edit(name, fn):
            p = root / name
            o = json.loads(p.read_text(encoding="utf-8"))
            fn(o)
            p.write_text(json.dumps(o), encoding="utf-8")

        both = [_ev("H", "Ought to Pass : MA RC 321-27 By Necessary Three-Fifths Vote "
                    "02/12/2026", "floor", "MA", "Ought to Pass", "2026-02-12"),
                _ev("S", "Ought to Pass, RC 22Y-1N, MA, by Necessary 3/5; OT3rdg; "
                    "03/26/2026 SJ 7", date="2026-03-26")]
        for bid, lsr, extra in (("CACR5", "0950", []),
                                ("CACR7", "0951", [_ev("H", "AMENDMENT FAILED REFERENDUM  "
                                                   "(119,104 - 159,439);  1998 RED BOOK, P350",
                                                   date="2026-11-03")])):
            edit("data/bills.json", lambda o, bid=bid, lsr=lsr: o["2025-2026"].update({bid: {
                "designation": bid.replace("CACR", "CACR "), "title": "relating to the judiciary",
                "lsr_num": lsr, "lsr_year": "2026", "subject": "Courts", "chamber": "H",
                "house_committee": "Judiciary", "senate_committee": "Judiciary",
                "lsr": f"2026-{lsr}"}}))
            edit("bill_status.json", lambda o, bid=bid, lsr=lsr: o.update({bid: {
                "gen_status": "PASSED", "house_status": "PASSED/ADOPTED",
                "senate_status": "PASSED/ADOPTED", "text_pdf": "", "chapter": "",
                "lsr": f"2026-{lsr}", "body": "H"}}))
            edit("narratives.json", lambda o, bid=bid, extra=extra: o["2025-2026"].update({bid: {
                "narrative": "Both chambers passed it.", "notes": [], "unrecognised": [],
                "stages": [{"hand": h} for h in ("H:committee", "H:floor", "S:committee",
                                                 "S:floor")],
                "events": both + extra}}))
        _mk(root / "corrections" / "ballot_results.json").write_text(json.dumps({"rows": [
            _voters_row("2025-2026", "CACR5", "2026-11-03", 452307, 237221),
            _voters_row("2025-2026", "CACR7", "2026-11-03", 119104, 169439, "Question 1",
                        _MANUAL_1999)]}),
            encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_site_v2.py"), "--data", "data",
                  "--out", "site", "--segments", "work"],
                 cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, ("build_site_v2 failed on the fixture with a ballot row: "
                                   + (r.stderr or r.stdout or "")[-400:])
        # build_site_v2 alone writes each record beside the index, for
        # build_bill_pages to fold into its page.
        f = root / "site" / "bills" / "2026" / "CACR5.json"
        assert f.exists(), "the fixture's CACR has no record"
        rec = json.loads(f.read_text(encoding="utf-8"))
        f7 = root / "site" / "bills" / "2026" / "CACR7.json"
        assert f7.exists(), "the fixture's second CACR has no record"
        rec7 = json.loads(f7.read_text(encoding="utf-8"))
        rows = json.loads((root / "site" / "idx" / "2025-2026.json").read_text(encoding="utf-8"))
        row = next((x for x in rows if x.get("id") == "CACR5"), {})
    finally:
        shutil.rmtree(root, ignore_errors=True)
    card = rec.get("ballot") or {}
    assert (card.get("date"), card.get("yes"), card.get("no"), card.get("ratified")) == (
        "2026-11-03", 452307, 237221, False), f"the CACR's record carries no voters' card: {card!a}"
    assert (card.get("by"), card.get("cite"), card.get("whose")) == (
        "Secretary of State", _SOS_2024[1], "the Secretary of State's"), (
        f"the CACR's card does not name its row's source: {card!a}")
    B = build_site_v2
    assert row.get("status") == B.NOT_RATIFIED, (
        f"65.6% yes reads {row.get('status')!a}, not {B.NOT_RATIFIED!a}")
    assert rec.get("status_source") == B.BALLOT_SOURCE, (
        f"the voters' answer is credited to {rec.get('status_source')!a}")
    last = (((rec.get("journey") or {}).get("steps")) or [{}])[-1]
    assert (last.get("body"), last.get("text")) == (
        "V", "Not ratified, 452,307–237,221 (the Secretary of State's count)"), (
        f"How it got here ends {last!a}")
    assert (row.get("rail") or [None])[-1] == ["Vx", "2026-11-03", "not ratified"], (
        f"the card's rail ends {(row.get('rail') or [None])[-1]!a}")
    card7 = rec7.get("ballot") or {}
    assert (card7.get("docket"), card7.get("by"), card7.get("whose")) == (
        [119104, 159439], "Secretary of State", "the Secretary of State's"), (
        f"the second CACR's card reads {card7!a}")
    last7 = (((rec7.get("journey") or {}).get("steps")) or [{}])[-1]
    assert (last7.get("body"), last7.get("text")) == (
        "V", "Not ratified, 119,104–159,439 (the docket's count; the Secretary of State's is "
             "119,104–169,439)"), f"the second CACR's How it got here ends {last7!a}"
    return "ok", ("the record carries the voters' card naming the Secretary of State, the "
                  "status says not ratified from ballot_results.json, How it got here ends at "
                  "the voters with the Secretary of State's count, and the card's rail at the "
                  "Voters stop; a docket's own differing count is the docket's, beside the "
                  "Secretary of State's")


@check("frontend", "a bill's own rail is dated from its journey, and How it got here lists it",
       needs=("build_site_v2",))
def _journey_drawn(build_site_v2):
    """Option A and C of 24 September, drawn in node the way the page draws them.

    The rail on a bill's own view gains Introduced and, under each stop, its
    day -- and since 5 October 2026 ("One rail, always detailed") so does the
    rail on a card in a list, from the index row's stops before anything is
    fetched, and the same rail once the card is opened: opening a card changes
    nothing about its rail. Under each stop the day and nothing else, from the
    same evening ("only have dates for the actions under each of the items"):
    no "voice vote", "16–8, amended", "signed" or "Chapter 160", and nothing
    under a stop with no day. A row with no stops keeps the bare rail. On the
    record's House Status and Senate Status rows
    give way to How it got here, one line per decision, the same lines the
    rail is dated from. A signed bill, a bill killed in the second chamber and
    a CACR, whose route ends at the voters rather than the governor."""
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    if not (js.exists() and stub.exists() and shutil.which("node")):
        return "skip", "app.js, dom_stub.js or node is not here"
    bills = _journey_bills(build_site_v2)
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "bills.json").write_text(json.dumps(bills), encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
const scope = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({cardHtml, renderDetail, journeyList, detail, dkey, IDX, jOpen, openCards,"
  + " setFocused:(x)=>{focused=x;}})");
const out = {};
for (const [row, d] of JSON.parse(fs.readFileSync("./bills.json", "utf8"))) {
  scope.IDX.push(row);
  scope.detail[scope.dkey(row.id)] = d;
  scope.setFocused(row.id);
  const page = scope.cardHtml(row, true);
  const summary = scope.renderDetail(row, d);
  scope.setFocused(null);
  scope.openCards.add(row.id);
  const opened = scope.cardHtml(row, false);
  scope.openCards.delete(row.id);
  delete scope.detail[scope.dkey(row.id)];
  out[row.id] = {page, summary, opened, card: scope.cardHtml(row, false),
                 bare: scope.cardHtml(Object.assign({}, row, {rail: undefined}), false)};
}
const many = {journey: {steps: Array.from({length: 9}, (_, i) =>
  ({date: "2025-03-0" + (i + 1), body: i % 2 ? "S" : "H", act: "passed", mark: "p",
    text: "Line " + i}))}};
out.many = scope.journeyList({id: "HB2"}, many);
// The fold only where it hides two rows or more: 6 and 7 steps draw whole.
const some = n => ({journey: {steps: Array.from({length: n}, (_, i) =>
  ({date: "2025-03-0" + (i + 1), body: "H", act: "passed", mark: "p", text: "Line " + i}))}});
out.six = scope.journeyList({id: "HB3"}, some(6));
out.seven = scope.journeyList({id: "HB4"}, some(7));
out.eight = scope.journeyList({id: "HB5"}, some(8));
scope.jOpen.add(scope.dkey("HB2"));
out.manyOpen = scope.journeyList({id: "HB2"}, many);
process.stdout.write("\\n@@" + JSON.stringify(out));
""", encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True, text=True, timeout=90)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not draw the journey under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    def rail_of(html):
        # The rail closes the card's head, and the record head's rail its
        # own box, since 10 October 2026 (C5, C6): no longer a button.
        m = re.search(r'<span class="rail dated"[^>]*aria-label="([^"]*)"[^>]*>(.*?)</span>\s*</div>',
                      html, re.S)
        assert m, "the bill's own view drew no dated rail"
        return m.group(1), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2))).strip()

    def listed(html):
        m = re.search(r'<ul class="jl">(.*?)</ul>', html, re.S)
        assert m, "On the record has no How it got here list"
        return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", li)).strip()
                for li in re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S)]

    # The glyph is drawn before the words, so it is read first here too. The
    # messages below print with !a: a check or a cross is not in the Windows
    # console's code page, and a failure that cannot be printed stops the run.
    want = {
        # The Law stop's day: the day the law took effect, and the day a bill
        # was killed under a Law it never reached (F13, 7 October 2026).
        # Month first, and every stop with its year (D6, 8 October 2026).
        "HB57": ("✓ Introduced Jan 8, 2025 ✓ House Feb 13, 2025 ✓ Senate May 22, 2025 "
                 "✓ Governor Jul 15, 2025 ✓ Law Jan 11, 2026",
                 ["✓ House Passed on a voice vote Feb 13, 2025",
                  "✓ Senate Passed with an amendment, 16–8 May 22, 2025",
                  "✓ House Agreed to the Senate's amendment, 192–153 Jun 12, 2025",
                  "✓ Governor Signed Jul 15, 2025",
                  "✓ Law Chapter 160, in effect Jan 11, 2026"],
                 "Introduced January 8, 2025; House: passed on a voice vote, February 13, 2025; "
                 "Senate: passed with an amendment, 16 to 8, May 22, 2025; Governor: signed, "
                 "July 15, 2025; Law: chapter 160, in effect January 11, 2026"),
        "HB68": ("✓ Introduced Jan 8, 2025 ✓ House Mar 20, 2025 ✕ Senate Jan 7, 2026 Governor "
                 "✕ Law Jan 7, 2026",
                 ["✓ House Passed with an amendment, 217–156 Mar 20, 2025",
                  "↺ Senate Sent back to committee on a voice vote May 1, 2025",
                  "✕ Senate Killed on a voice vote Jan 7, 2026"], None),
        "CACR13": ("✓ Introduced Jan 7, 2026 ✓ House Feb 5, 2026 ✓ Senate Mar 26, 2026 Voters",
                   ["✓ House Passed, 325–15 Feb 5, 2026", "✓ Senate Passed, 23–1 Mar 26, 2026"],
                   None),
    }
    for bid, (rail_text, lines, aria) in want.items():
        g = got[bid]
        said, drawn = rail_of(g["page"])
        assert drawn == rail_text, f"{bid}'s rail reads {drawn!a}, not {rail_text!a}"
        if aria:
            assert said == aria, f"{bid}'s rail says {said!a} to a reader who hears it"
        assert listed(g["summary"]) == lines, (
            f"{bid}'s How it got here lists {listed(g['summary'])!a}")
        assert "House Status" not in g["summary"] and "Senate Status" not in g["summary"], (
            f"{bid} still draws the status page's per-chamber rows")
        # Across the panel, not in the value column: beside the analysis that
        # column left the words about 66px (24 September).
        assert '<section class="w4" id="journey"><h2 class="w4h">How It Got Here</h2>' \
               '<div class="w4b"><ul class="jl">' in g["summary"], (
            f"{bid}'s How it got here is drawn in the value column, not across the panel")
        # ONE RAIL (5 October 2026): the list card, closed and with nothing
        # fetched, draws the rail the bill's own view draws, from the index
        # row's stops; opened, the same again. The bill's own view says each
        # stop in the record's fuller words; the card says its row's, closed
        # and opened alike -- opening it changed what a screen reader heard
        # until the review of 5 October 2026, while what was drawn stood still.
        assert rail_of(g["card"])[1] == rail_text, (
            f"{bid}'s list card draws {rail_of(g['card'])[1]!a}, not its own view's rail")
        assert rail_of(g["opened"])[1] == rail_text, (
            f"{bid}'s card, opened, draws {rail_of(g['opened'])[1]!a}")
        assert rail_of(g["opened"])[0] == rail_of(g["card"])[0], (
            f"{bid}'s card says {rail_of(g['card'])[0]!a} closed and "
            f"{rail_of(g['opened'])[0]!a} opened")
        assert "Introduced" in rail_of(g["card"])[0], (
            f"{bid}'s list card says {rail_of(g['card'])[0]!a} to a reader who hears it")
        # THE DAY ALONE under every stop, on the page, the card and the card
        # opened: a word back under any of them fails here as well as above.
        for where in ("page", "card", "opened"):
            m = re.search(r'<span class="rail dated".*?</span>\s*</div>', g[where], re.S)
            under = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
                     for s in re.findall(r"<small>(.*?)</small>", m.group(0) if m else "", re.S)]
            words = [u for u in under if not re.fullmatch(r"[A-Z][a-z]{2} \d{1,2}, \d{4}", u)]
            assert under and not words, (
                f"{bid}'s rail on its {where} draws {words or under!a} under its stops, "
                "where it draws a day and nothing else")
        # A row with no stops to date keeps the bare rail: no Introduced, no
        # dates, the index's four marks.
        assert 'class="rail"' in g["bare"] and "<small>" not in g["bare"] \
            and "Introduced" not in g["bare"], f"{bid}'s stopless row drew a dated rail"
    # The same rail closed as open, so the same width: and its labels on one
    # line from the top, which centring each stop's words in the tallest
    # stop's height did not give (app.css, .rail.dated .stop).
    css = _source("src/pages/app.css") if Path("src/pages/app.css").exists() else ""
    assert re.search(r"(?:^|[,}\s])\.rail\.dated\{max-width:560px", css), (
        "app.css does not give the dated rail one width on every card (.rail.dated)")
    assert re.search(r"\.rail\.dated \.stop\{[^}]*justify-content:flex-start", css), (
        "app.css centres each stop's words in the tallest stop, so the labels are ragged")
    # What the card says from its row: the mark's word where the stop's own
    # words do not already say how it went -- "Governor: signed", not
    # "Governor: passed, signed" -- and every date in full, "November 2026"
    # with the rest.
    for bid, said in (("HB57", "Introduced January 8, 2025; House: passed, voice vote, "
                               "February 13, 2025; Senate: passed, 16 to 8, amended, May 22, "
                               "2025; Governor: signed, July 15, 2025; Law: chapter 160, in "
                               "effect January 11, 2026"),
                      ("CACR13", "Introduced January 7, 2026; House: passed, 325 to 15, "
                                 "February 5, 2026; Senate: passed, 23 to 1, March 26, 2026; "
                                 "Voters: is here now, November 2026")):
        assert rail_of(got[bid]["card"])[0] == said, (
            f"{bid}'s list card says {rail_of(got[bid]['card'])[0]!a}, not {said!a}")
    assert "Governor" not in rail_of(got["CACR13"]["page"])[1], (
        "a CACR's rail draws a governor, who never sees a constitutional amendment")
    assert 'class="stop s-h"><b></b><i>Voters' in got["CACR13"]["page"], (
        "CACR 13's Voters stop is not ringed while it waits for the election")
    # Nine decisions: six shown and three held back IN THE LIST, behind a
    # button that opens them there. Not a link to the Votes tab, which has no
    # card for a voice vote -- 473 capped bills hid a line it does not have.
    many, opened = got["many"], got["manyOpen"]
    shown = [li for li in re.findall(r"<li[^>]*>", many) if " hidden" not in li]
    assert many.count("<li") == 10 and len(shown) == 7 and "data-jmore=" in many \
        and "Show 3 more" in many and "Votes tab" not in many, (
            f"nine decisions are not six lines and three held back in place: {many[:200]!a}")
    assert [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", li)).strip().split(" ", 2)[-1][:6]
            for li in re.findall(r"<li[^>]*>(.*?)</li>", opened, re.S)] == \
        [f"Line {i}" for i in range(9)] and "data-jmore" not in opened \
        and " hidden" not in opened, (
            f"opened, the nine decisions are not all there in order: {opened[:200]!a}")
    # A fold that hides one row saves nothing (it is a row itself): seven steps
    # draw all seven, eight fold two behind "Show 2 more".
    for n in ("six", "seven"):
        assert "data-jmore" not in got[n] and " hidden" not in got[n], (
            f"{n} steps are folded, and the fold hides at most one row: {got[n][:160]!a}")
    assert got["seven"].count("<li") == 7, "seven steps are not seven rows"
    assert "Show 2 more" in got["eight"] and got["eight"].count(" hidden") == 2, (
        "eight steps do not fold exactly two rows behind Show 2 more")
    return "ok", ("HB 57, HB 68 and CACR 13: one dated rail on their own view and on the "
                  "list card, closed and opened, a day and no words under each stop, the "
                  "bare rail only for a row without stops, "
                  "How it got here in place of the status rows, six lines until the rest "
                  "are opened in place")


@check("build", "a bill's statute citations open the site's own statute pages where the table holds "
       "them, and leave the site only without it", needs=("build_site_v2", "rsa"))
def _rsa_links_own_pages(B, RSA):
    """The person, 11 October 2026: "the RSA pages should be linked throughout
    the site to the Granite Record pages as an interlinked system". With the
    statute table loaded, build_site_v2.rsa_url gives /laws/<chapter>#s<section>
    for a section the table holds, the chapter's page for one it does not
    (a new section a bill writes), and nothing for a chapter it does not hold
    -- never a gc.nh.gov address built for a page that may not exist. The
    app's two link writers open the site's own pages in the same tab."""
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA"]
    t = RSA.Table([dict(zip(cols, ["1", "VI", "91-A", "91-A-4", "T", "CHAPTER 91-A X",
                                   "Section 91-A:4 Minutes.", "", "", "<codesect>x</codesect>"]))])
    keep = list(B._STATUTES)
    try:
        B._STATUTES[:] = [t]
        got = (B.rsa_url("91-A", "4"), B.rsa_url("91-a", "33-h"), B.rsa_url("91-A"), B.rsa_url("999", "1"))
        amends = B.bill_amends("1 Records. Amend RSA 91-A:4, IV to read as follows: IV. x")
    finally:
        B._STATUTES[:] = keep
    assert got == ("/laws/91-a#s4", "/laws/91-a", "/laws/91-a", ""), got
    assert amends == {"RSA 91-A:4": "/laws/91-a#s4"}, amends
    keep_e = list(B._ENACTED)
    try:
        B._ENACTED[:] = [{"2019-2020/HB286": ["91-A:4", "6:12", "91-A:1-a"]}]
        changed = B.statutes_enacted("2019-2020", "HB286")
    finally:
        B._ENACTED[:] = keep_e
    assert changed == ["6:12", "91-A:1-a", "91-A:4"], f"Changed these statutes is not in statute order: {changed}"
    app = _source("src/pages/app.js")
    assert app.count('charAt(0)==="/"') >= 3, "an app link writer sends the site's own statute page to a new tab"
    assert "function changedLine(d)" in app and "+changedLine(d)" in app, \
        "the bill page does not draw Changed these statutes"
    return "ok", "91-A:4 to its anchor, a new section to its chapter, chapter 999 to nothing; same tab"


# What each of the old copies said of an interim study report, typed out in
# a renderer, before study_report.json (23 October 2026). None comes back.
_STUDY_WORDS_GONE = ("did not recommend the subject for future legislation",
                     "made no recommendation for future legislation",
                     "reported without a recommendation", '"without a recommendation"',
                     '"not recommended for "', '"recommended for "')


@check("frontend", "an interim study report is said in study_report.json's words wherever it is "
       "said: the docket's plain line, How it got here, a bill's closing note, a committee's "
       "meeting card and the emails", needs=("build_site_v2", "plain_action"))
def _study_report_said_once(B, PA):
    """The person, 23 October 2026: one source for each thing the site words
    several ways. What an interim study committee reported -- it recommends
    future legislation, does not, or makes no recommendation -- was said in
    five sets of words: plain_action.py's, build_site_v2's How it got here
    line, app.js's closing note on a bill (STUDY_SAID) and a committee's
    meeting card (STUDY_WORDS), and mail.js's copy, with a fifth copy in the
    email tests. A report without a recommendation "made no recommendation
    for future legislation" on a committee's page, which reads as one that did
    not recommend it.

    Now the words are src/pages/words/study_report.json, plain_action's of the
    sample the person reviewed on 14 October 2026, held here to those words;
    the build, the pages and How it got here draw them from it, each keeping
    its own sentence around the phrase, and the Worker takes them from
    site.gen.js, which follow_site.py writes from the file (23 October 2026;
    _follow_site_current holds it current). Each place is drawn here on the
    three readings, and none of them types the words out again."""
    sr = json.loads(_source("src/pages/words/study_report.json"))
    head, said = sr.get("head"), sr.get("said")
    assert (head, said) == ("Interim study report", {
        "rec": "recommends future legislation", "not": "does not recommend future legislation",
        "without": "makes no recommendation"}), f"study_report.json says {head!r}: {said}"
    bad = []
    # The docket's plain line: the emails' items and the Documents tab.
    rows = {"rec": "Interim Study Report: Recommended for Future Legislation 09/28/2026 (Vote 9-0; RC)",
            "not": "Interim Study Report: Not Recommended for Future Legislation 09/29/2026 (Vote 8-2; RC)",
            "without": "Interim Study Report: Without Recommendation 10/31/2014 (Vote 10-10)"}
    votes = {"rec": "9–0", "not": "8–2", "without": "10–10"}
    for k, raw in rows.items():
        if PA.plain(raw) != f"{head}: {said[k]}, {votes[k]}":
            bad.append(f"plain_action says {PA.plain(raw)!r} for {raw!r}")
    # How it got here: the report's own line, the next term's year after it.
    for k, raw in list(rows.items()) + [("rec", "Interim Study Report: Recommended for Future "
                                               "Legislation in 2027 (Vote 11-0)")]:
        lines = B.study_ending({"events": [{"raw": raw, "date": "2026-09-28", "body": "H"}]},
                               [{"body": "H", "act": "study", "date": "2026-05-14"}], "", "2025-2026",
                               {("H", "2026"): ["2026-08-19"]})
        text = (lines[-1] if lines else {}).get("text")
        year = " in 2027" if "2027" in raw else ""
        want = f"{head}: {said[k]}{year}, {'11–0' if year else votes[k]}"
        if text != want:
            bad.append(f"How it got here says {text!r}, not {want!r}")
    # The bill's closing note and the committee's meeting card, in node.
    drew = "node is not here to draw app.js"
    got = _app_js("[" + ",".join(
        f"scope.endNote({{study_report: {{date: '2026-09-28', rec: {json.dumps(k)}, vote: '9–0'}}}}),"
        f"scope.actSaid({{act: 'study report', said: {json.dumps(k)}, yeas: 9, nays: 0}}, "
        "'The committee', '')" for k in said) + "]", names=("endNote", "actSaid"))
    if got is not None:
        for (k, note, card) in zip(said, got[0::2], got[1::2]):
            if f"the committee {said[k]}, 9–0." not in note:
                bad.append(f"a bill's closing note for {k!r} reads {note!r}")
            if f"interim study report{':' if k == 'rec' else ''} {said[k]}, 9–0." not in card:
                bad.append(f"a committee's meeting card for {k!r} reads {card!r}")
        drew = "app.js's closing note and meeting card draw them"
    app = _source("src/pages/app.js")
    if "const STUDY_SAID=WORDBOOK.study_report.said;" not in app:
        bad.append("app.js does not take its study report words from WORDBOOK.study_report")
    # The Worker's: site.gen.js's STUDY_REPORT, as committed, and mail.js's
    # three sentences made of it, the head before each reading.
    mail = _source("workers/follow/mail.js")
    sent = _site_gen().get("STUDY_REPORT")
    if sent != {"head": head, "said": said}:
        bad.append(f"site.gen.js's STUDY_REPORT {sent} is not study_report.json's words")
    m = re.search(r"\nconst STUDY = \{(.*?)\n\};", mail, re.S)
    made = dict(re.findall(r"(true|false|null): `\$\{STUDY_REPORT\.head\}: \$\{STUDY_REPORT\.said\.(\w+)\}`",
                           m.group(1))) if m else {}
    if made != {"true": "rec", "false": "not", "null": "without"}:
        bad.append(f"mail.js's STUDY is not the head and rec, not and without of site.gen.js's "
                   f"STUDY_REPORT: {made}")
    # Typed out again nowhere else, and the old copies gone.
    typed = [said["rec"], said["not"], f"{head}: {said['without']}"]
    for f in ("src/pages/app.js", "src/pages/components.js", "src/pages/build_site_v2.py",
              "src/pages/journey.py", "src/pages/endings.py", "src/pages/hearing_reports.py",
              "src/pages/build_committees.py", "src/parse/plain_action.py", "tests/follow/sender.test.js"):
        text = _source(f)
        again = [w for w in typed + list(_STUDY_WORDS_GONE) if w in text]
        if f.endswith("sender.test.js"):
            # The tests read the file for the test that holds the words, and
            # name the words only where a line of an email is read whole.
            again = [w for w in again if w in _STUDY_WORDS_GONE]
        if again:
            bad.append(f"{f} types {again} out again")
    if any(w in mail for w in typed):
        bad.append("mail.js types the study report's words; they are site.gen.js's STUDY_REPORT")
    assert not bad, "; ".join(bad[:4])
    return "ok", (f"\"{head}: {said['rec']}\", \"{said['not']}\" and \"{said['without']}\" from the "
                  f"one file in the plain line, How it got here and the emails (site.gen.js); {drew}")


@check("build", "related bills: a sentence says which way the text went, and the judged sample's "
       "rules hold", needs=("related_bills", "review"))
def _related_judged(RB, R):
    """The judged sample of 11 October 2026 (tests/related_judged_2026-10-11.json,
    357 pairs judged at the person's request): a one-sided share called HB 2
    "most of the text" of SB 124; a law passed before a bill "became law as
    part of" it; amendments decades apart, short appropriations and the
    decade's district tables read as the same language. Where
    related_bills.json is on disk, no pair judged wrong in a stratum the
    rules cover may be back."""
    it = {"kind": "language", "a": "2023-2024/HB2", "b": "2023-2024/SB124", "share": 0.85,
          "mine": 0.0, "theirs": 0.85}
    assert R.related_sentence(it) == "It contains the text of SB 124 (2023-2024), a shorter bill.", \
        R.related_sentence(it)
    it = dict(it, a="2023-2024/SB124", b="2023-2024/HB2", mine=0.85, theirs=0.0)
    assert R.related_sentence(it).startswith("Its text is also in HB 2 (2023-2024), a longer bill"), it
    am = {"kind": "amendment", "direction": "bill_in_amendment", "order": "before", "amendment": "2016-0920h",
          "b": "2015-2016/HB1696", "fate": "failed", "fate_body": "H", "fate_vote": "126-233"}
    assert "had been offered before, as amendment 2016-0920h" in R.related_sentence(am)
    assert RB.LAW_GAP == 2 and RB.AMEND_GAP == 3 and RB.REFILE_BIG_SHARE == 0.10
    assert RB.APPROP.search("there is hereby appropriated to the department the sum of $1")
    assert RB.DISTRICTS.search("1 state senate districts rsa 662:3 is repealed and reenacted")
    judged = json.loads(_source("tests/related_judged_2026-10-11.json"))["pairs"]
    assert len(judged) >= 300 and sum(p["verdict"] == "correct" for p in judged) >= 250
    rb = Path("related_bills.json")
    if not rb.is_file():
        return "ok", f"the sentences and the rules; {len(judged)} judged pairs, no related_bills.json here"
    data = json.loads(rb.read_text(encoding="utf-8"))

    def shown(p):
        t, _, b = p["a"].partition("/")
        for r in (data.get(t) or {}).get(b, []):
            if r.get("band") != "line":
                continue
            if p["kind"] == "amendment" and r["kind"] == "amendment" and r.get("amendment") == p["amendment"]:
                return True
            if p["kind"] != "amendment" and r["kind"] == p["kind"] and r.get("other") == p["b"]:
                return True
        return False
    right = [p for p in judged if p["verdict"] == "correct"]
    kept = sum(shown(p) for p in right)
    back = [p for p in judged if p["verdict"] == "wrong" and shown(p)]
    assert kept >= 0.97 * len(right), f"only {kept} of {len(right)} pairs judged right are still found"
    assert len(back) <= 4, f"{len(back)} pairs judged wrong are shown again: {back[:3]}"
    return "ok", f"{kept} of {len(right)} judged right still found; {len(back)} judged wrong still shown"


@check("build", "related bills on a bill's page: only what the judged sample let through, each other "
       "bill once, the specific first", needs=("build_site_v2", "related_bills"))
def _related_tab(B, RB):
    """build_site_v2.add_related, the Related tab's data (RELATED_BILLS.md §6).
    SB 184 of 2025's real relations: its text became law in HB 377, which the
    same text also links as language, and it was filed before as SB 479. An
    entry below the line, an amendment whose fate the docket does not
    record, the bill itself and a bill the index does not hold are left out."""
    by_key = {"2025-2026/HB377": {"n": "HB 377-FN", "title": "relative to x", "year": 2025, "chip": "Became Law"},
              "2023-2024/SB479": {"n": "SB 479", "title": "relative to y", "year": 2024, "chip": "Died"},
              "2025-2026/HB2": {"n": "HB 2", "title": "z", "year": 2025, "chip": "Became Law"},
              "2025-2026/SB184": {"n": "SB 184", "title": "w", "year": 2025, "chip": "Died"}}
    rows = [{"kind": "amendment", "other": "2025-2026/HB2", "amendment": "2025-1333h", "band": "line",
             "direction": "bill_in_amendment", "order": "same", "share": 0.9, "fate": "unknown"},
            {"kind": "amendment", "other": "2025-2026/HB2", "amendment": "2025-1247h", "band": "line",
             "direction": "bill_in_amendment", "order": "same", "share": 0.9, "fate": "failed",
             "fate_vote": "72-300", "fate_body": "H"},
            {"kind": "inside_law", "other": "2025-2026/HB377", "share": 0.97, "band": "line"},
            {"kind": "language", "other": "2023-2024/SB479", "share": 0.98, "mine": 0.98, "theirs": 0.97,
             "band": "line"},
            {"kind": "language", "other": "2025-2026/HB377", "share": 0.97, "mine": 0.97, "theirs": 0.2,
             "band": "line"},
            {"kind": "language", "other": "2025-2026/SB184", "share": 1.0, "band": "line"},
            {"kind": "language", "other": "2021-2022/SB9", "share": 0.9, "band": "line"},
            {"kind": "language", "other": "2025-2026/HB2", "share": 0.7, "band": "below"}]
    got = B.related_entries("2025-2026", "SB184", rows, by_key)
    said = [(e["g"], e["o"], e["s"]) for e in got]
    assert said == [
        (0, "2025-2026/HB377", "Nearly all of its text became law as part of {b}."),
        (0, "2025-2026/HB2", "Its language was offered as amendment 2025-1247h to {b}; the House rejected it, 72-300."),
        (1, "2023-2024/SB479", "Filed before as {b}, with the same text.")], said
    assert got[0]["n"] == "HB 377-FN" and got[0]["c"] == "Became Law" and got[2]["y"] == 2024, got
    # An amendment's row carries what the History tab needs to say it again
    # beside the same bill's text row (the owner's walk of dry run 8).
    assert (got[1]["m"], got[1]["f"], got[1]["fb"], got[1]["fv"]) == ("2025-1247h", "failed", "H", "72-300"), got[1]
    assert "m" not in got[0] and "m" not in got[2], got
    assert not RB.shown({"kind": "amendment", "band": "line", "fate": "recommended"}), \
        "an amendment no vote is on record for would be shown"
    app = _source("src/pages/app.js")
    assert "function renderRelated(b,relRows,d)" in app and 'replace("{b}",name)' in app and 'related:"7"' in app, \
        "the page does not draw the Related tab from d.related"
    return "ok", ("SB 184: rejected amendment, HB 377 once, SB 479 filed before; below the line, "
                  "no fate, itself and an unknown bill left out")


@check("build", "related bills: which shingles two texts share is intersect1d's answer, and each "
       "text's words are read once", needs=("related_bills",))
def _related_bills_shared_in(RB):
    """relate() asked np.intersect1d which of one text's shingles another
    holds, for each of a quarter of a million pairs, and read every text's
    words twice (29 October 2026: 26 s and 9 s of a two-minute step under a
    profiler). shared_in() answers with one binary search a shingle, since
    every set is np.unique's, filtered: sorted, no repeats. This holds it to
    intersect1d's own positions on sets like those -- empty, one shingle,
    disjoint, the same, nested, overlapping, and the largest and smallest
    64-bit values -- and holds relate() to one read of each text."""
    try:
        import numpy as np
    except ImportError:
        return "skip", "numpy will not import"
    import inspect
    import random
    rnd = random.Random(20261029)
    top = np.iinfo(np.uint64).max
    u = lambda xs: np.unique(np.array(xs, dtype=np.uint64))
    pairs = [(u([]), u([])), (u([]), u([1])), (u([1]), u([])), (u([1]), u([1])),
             (u([1]), u([2])), (u([0, top]), u([top])), (u([top]), u([0, top])),
             (u(range(10)), u(range(5, 15))), (u(range(10)), u(range(3, 6))),
             (u(range(3, 6)), u(range(10))), (u([5]), u(range(10)))]
    for _ in range(3000):
        pool = [rnd.randrange(0, 2 ** 64) for _ in range(rnd.randint(0, 40))] + [0, top]
        a = u(rnd.sample(pool, rnd.randint(0, len(pool))))
        b = u(rnd.sample(pool, rnd.randint(0, len(pool))))
        pairs.append((a, b))
    for a, b in pairs:
        _, ia, _jb = np.intersect1d(a, b, assume_unique=True, return_indices=True)
        mask = RB.shared_in(a, b)
        assert mask.dtype == bool and len(mask) == len(a) and \
            np.flatnonzero(mask).tolist() == sorted(ia.tolist()), (
                f"shared_in({a.tolist()[:6]}, {b.tolist()[:6]}) is not intersect1d's answer")
    # And relate()'s own sets are the kind shared_in needs: the Shingler's,
    # boilerplate taken out as relate() takes it, sorted with no repeats.
    sh = RB.Shingler(np)
    made = [sh(RB.words_of(t)) for t in (
        "", "too short", "Section 1 of RSA 21-J:1 is amended by striking out the word and "
        "inserting in place thereof the following new paragraph about the state",
        " ".join(rnd.choice(("the", "state", "shall", "rsa", "section", "amended"))
                 for _ in range(400)))]
    allh = np.concatenate(made)
    u, cnt = np.unique(allh, return_counts=True)
    made = [s[~np.isin(s, u[cnt > 1], assume_unique=True)] if len(s) else s for s in made]
    assert all(s.dtype == np.uint64 and bool((np.diff(s.astype(object)) > 0).all())
               for s in made), "a set relate() builds is not sorted with no repeats"
    src = inspect.getsource(RB.relate)
    assert "intersect1d" not in src and src.count("words_of(") == 1, (
        "relate() sorts each pair together again, or reads a text's words twice")
    return "ok", f"{len(pairs):,} pairs of sets, every one intersect1d's answer"


@check("build", "related bills: the same text hashes the same everywhere, quoted law is not shared "
       "language, and an amendment's fate is the docket's", needs=("related_bills",))
def _related_bills(RB):
    """src/parse/related_bills.py (RELATED_BILLS.md). Three things a page
    built on it relies on, each from the record:

    - an amendment's fate is read off its bill's docket, line by line, and the
      last decisive line wins. HB 2 of 2023's own lines: 2023-1247h adopted
      351-38, 2023-1333h failed 72-300 -- the case RELATED_BILLS.md §2.2
      names, where "HB 1499's language was added to HB 2" through 1333h
      would be false;
    - the shingles are the same on every machine and under every
      PYTHONHASHSEED, so a night and a laptop find the same relations;
    - a run of statute text both bills reprint is not shared language unless
      only the later one could have put it into the law."""
    nar = {"2023-2024": {"HB2": {"events": [
        {"date": "2023-03-30", "type": "report", "body": "H", "raw": "Majority Committee Report: Ought "
         "to Pass with Amendment #2023-1247h 03/30/2023 (Vote 14-11; RC)"},
        {"date": "2023-04-06", "type": "amendment", "body": "H",
         "raw": "Amendment #2023-1247h : AA DV 351-38 04/06/2023"},
        {"date": "2023-04-06", "type": "amendment", "body": "H",
         "raw": "FLAM #2023-1333h (Reps. Hoell, Prout, Comtois): AF DV 72-300 04/06/2023"}]}}}
    f = RB.amendment_fates(nar)
    assert f["2023-1247h"]["outcome"] == "adopted" and f["2023-1247h"]["vote"] == "351-38", f
    assert f["2023-1333h"]["outcome"] == "failed" and f["2023-1333h"]["vote"] == "72-300", f
    import numpy as np
    sh = RB.Shingler(np)
    words = RB.words_of("This act shall take effect 60 days after its passage [and not before].")
    assert "before" not in words, "bracketed old law was read as proposed"
    got = [int(x) for x in sh(words)]
    # Six runs of five words, pinned: any machine that hashes them otherwise
    # finds other relations than the night does.
    assert got == [1501139938635658474, 1924498122979730118, 2445867956418451481,
                   4083973422708187706, 5799543022023669206, 8824611947269029673], got
    assert int(sh(RB.words_of("the commissioner shall adopt rules under RSA 541-A"))[0]) == \
        int(RB.Shingler(np)(RB.words_of("the commissioner shall adopt rules under RSA 541-A"))[0])
    body = RB.bill_body("AN ACT relative to X. Be it Enacted by the Senate and House of "
                        "Representatives in General Court convened: 1 New Paragraph. Amend RSA 1:1.")
    assert body.strip().startswith("1 New Paragraph"), body
    return "ok", "2023-1247h adopted 351-38 and 2023-1333h failed 72-300, from HB 2's own docket"


@check("frontend", "the Status filter files every word a chip can say under one of seven "
                   "categories -- In Progress, Passed, Tabled, Interim Study, Died, Withdrawn, "
                   "Vetoed -- by its word or its kind, and an address naming a chip's word "
                   "finds its category", needs=("build_site_v2",))
def _status_categories(B):
    """The person, 8 October 2026, and their answers the same evening: the
    Status filter and the Status sort's headings use categories, and a card's
    chip keeps its own word. Held here: every word build_site_v2.chip_word
    gives, for every ending this file's chip table names, in session and
    after it, every adopted resolution's and constitutional amendment's word,
    and every (chip, kind) the nineteen terms carried on 8 October
    (_STATUS_REAL_PAIRS), is filed by app.js's statusCat where
    _STATUS_CATEGORY says, and decided by its word or its kind -- never by
    the last line, which a word and a kind statusCat had never seen would
    reach; a request is in none. And ?status= in an address, read through
    catOfWord: a category in any case, every chip word -- what the filter
    offered before 8 October, so an address written then still finds its
    bills -- and nothing for a word that is neither, "constructor" among
    them."""
    pairs = set(_STATUS_REAL_PAIRS)
    tables = list(_CHIP_FINISHED.items()) + list(_CHIP_LIVE.items())
    for kind, table in tables:
        for status in table:
            for live in (False, True):
                pairs.add((B.chip_word(kind, status, live), kind))
    for w in ("Adopted by the House", "Adopted by the Senate", "Adopted by both chambers",
              "Passed both chambers, goes to the voters",
              "Passed both chambers, went to the voters",
              "Passed both chambers, went to the voters in November 2026",
              "Passed both chambers, ratified by the voters",
              "Passed both chambers, not ratified by the voters"):
        for live in (False, True):
            pairs.add((B.chip_word("adopted", w, live), "adopted"))
    unknown = sorted({c for c, _k in pairs if c not in _STATUS_CATEGORY})
    assert not unknown, (f"chip_word gives words this check files nowhere: {unknown}; "
                         "add each to _STATUS_CATEGORY with the category the person would "
                         "put it in")
    words = sorted(_STATUS_CATEGORY) + _STATUS_CATS + [c.lower() for c in _STATUS_CATS] \
        + ["IN PROGRESS", "  Passed ", "", "Killed", "constructor", "__proto__", "toString",
           "Filed as a request", "nonsense", "in committee", "became law",
           "adopted by the house", "passed both chambers, goes to the voters in november 2030",
           "passed both chambers, went to the voters in november 2030"]
    lower = {k.lower(): v for k, v in _STATUS_CATEGORY.items()}
    lower["passed both chambers, goes to the voters in november 2030"] = "In Progress"
    lower["passed both chambers, went to the voters in november 2030"] = "In Progress"
    got = _node_app(_STATUSCAT_HARNESS, {
        "pairs.json": json.dumps(sorted(pairs)), "words.json": json.dumps(words)})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"statusCat threw {got['threw']}"
    bad = []
    if got["cats"] != _STATUS_CATS:
        bad.append(f"the categories run {got['cats']}, not {_STATUS_CATS}")
    for chip, kind, cat, by_word, by_kind in got["pairs"]:
        want = _STATUS_CATEGORY[chip]
        if cat != want:
            bad.append(f"{chip!r} ({kind}) is filed under {cat!r}, not {want!r}")
        if not (by_word or by_kind):
            bad.append(f"{chip!r} ({kind}) is filed by statusCat's last line: neither its "
                       "word nor its kind is known to it")
    if got["request"] != "":
        bad.append(f"a request is filed under {got['request']!r}: it is not a bill yet")
    read = dict((w, c) for w, c in got["words"])
    for w in words:
        want = (_STATUS_CATEGORY.get(w) or next((c for c in _STATUS_CATS
                                                if c.lower() == w.strip().lower()), "")
                or lower.get(w.strip().lower(), ""))
        if read.get(w) != want:
            bad.append(f"?status={w!r} reads as {read.get(w)!r}, not {want!r}")
    assert not bad, "; ".join(bad[:8]) + (f"; and {len(bad) - 8} more" if len(bad) > 8 else "")
    return "ok", (f"{len(got['pairs'])} chip words and kinds, every ending in and out of "
                  "session and every pair the nineteen terms carry, are each filed by word or "
                  f"kind under one of the seven; ?status= reads {len(words)} words as it should")


@check("frontend", "a constitutional amendment whose election has passed, and whose count is not "
                   "in yet, keeps the category and the card's word it had the day before: In "
                   "Progress, To the Voters", needs=("build_site_v2", "member_figures"))
def _cacr_went_to_the_voters(B, MF):
    """THE NIGHT OF 4 NOVEMBER 2026 (a finding of the release review of 16
    October 2026, confirmed). CACR 13 of 2025-2026 goes to the voters on 3
    November 2026; from the next day build_site_v2.cacr_to_the_voters says it
    "went to the voters in November 2026", and says so until a person types
    the count into corrections/ballot_results.json. Two checks the night runs
    on its built site did not know those words: _status_categories_built
    found no category written down for them, and app.js filed them by the
    kind, adopted, under Passed, whatever two thirds of the voters said;
    _card_words_short found the card saying them in nine words. Both hold the
    night, so every night from the 4th would have held for approval and
    every dry run said NOT CLEAN.

    Held as the night builds it: bill_disposition, as build_bills calls it
    with no day of its own, over CACR 13's own docket rows (Docket.txt, as
    _between_chambers quotes them), its own text's election and its own row
    of ballot_results.json with no count in it, the build's day stated as
    build_date reads one. On election day the line goes; on the day after it
    went; once its term has closed it went with no November named. Each
    line's chip, in session and out, must be filed by app.js's statusCat by
    its word, not its kind, under the category of the day before
    (_STATUS_CATEGORY), as member_figures files it, and come out of
    components.card_word as To the Voters: what _status_categories_built and
    _card_words_short ask of every chip the built site carries."""
    import build_date
    import components as C
    rows = json.loads(Path(B.BALLOTS).read_text(encoding="utf-8"))["rows"]
    own = next((r for r in rows if (r.get("term"), r.get("bill")) == ("2025-2026", "CACR13")),
               None)
    assert own, f"{B.BALLOTS} no longer holds CACR 13 of 2025-2026"
    assert own["election"] == "2026-11-03" == B.election_day(2026).isoformat(), (
        f"CACR 13's row says its election is {own['election']}, not 3 November 2026")
    # Until the count is typed in; the row as it stands may hold it by now.
    ballot = {**own, "yes": None, "no": None}
    st = {"gen_status": "SENATE", "senate_status": "PASSED/ADOPTED", "body": "H"}
    n = _nar(_ev("H", "Introduced 01/07/2026 and referred to Judiciary", "introduced"),
             _ev("H", "Ought to Pass: MA DV 325-15 By Necessary Three-Fifths Vote 02/05/2026",
                 "floor", "MA", "Ought to Pass"),
             _ev("S", "Ought to Pass, RC 23Y-1N, MA, by Necessary 3/5; OT3rdg; 03/26/2026"))
    text = ("That the above amendments proposed to the constitution be submitted to the "
            "qualified voters of the state at the state general election to be held in "
            "November, 2026.")
    goes = "Passed both chambers, goes to the voters in November 2026"
    want = {("2026-11-03", "2025-2026"): goes,
            ("2026-11-04", "2025-2026"): "Passed both chambers, went to the voters in November 2026",
            ("2027-01-06", "2027-2028"): "Passed both chambers, went to the voters"}
    was = os.environ.get(build_date.ENV)
    got = {}
    try:
        for (day, current), _w in want.items():
            os.environ[build_date.ENV] = day
            d = B.bill_disposition({}, "CACR13", st, n, [], "2025-2026", current,
                                   term_over=True, text=text, ballot=ballot)
            got[(day, current)] = (d.kind, d.status)
    finally:
        if was is None:
            os.environ.pop(build_date.ENV, None)
        else:
            os.environ[build_date.ENV] = was
    bad = [f"on {day} (current term {cur}) CACR 13 says {g!r}, not {('adopted', w)!r}"
           for (day, cur), w in want.items() for g in [got[(day, cur)]] if g != ("adopted", w)]
    assert not bad, "; ".join(bad)
    chips = sorted({B.chip_word(k, s, live) for k, s in got.values() for live in (False, True)})
    pairs = [[c, "adopted"] for c in chips]
    day_before = _STATUS_CATEGORY[goes]
    for c in chips:
        if _STATUS_CATEGORY.get(c) != day_before:
            bad.append(f"{c!r} is filed under {_STATUS_CATEGORY.get(c)!r} here, not "
                       f"{day_before!r} as the day before")
        if MF.status_category({"chip": c, "kind": "adopted"}) != day_before:
            bad.append(f"member_figures files {c!r} under "
                       f"{MF.status_category({'chip': c, 'kind': 'adopted'})!r}")
        if C.card_word(c, "Hpp--") != C.card_word(goes, "Hpp--") or \
                C.card_word(c, "Hpp--") != "To the Voters":
            bad.append(f"a card says {c!r} as {C.card_word(c, 'Hpp--')!r}, not 'To the Voters'")
    ran = _node_app(_STATUSCAT_HARNESS, {"pairs.json": json.dumps(pairs), "words.json": "[]"})
    if ran is not None:
        assert "threw" not in ran, f"statusCat threw {ran['threw']}"
        for chip, _kind, cat, by_word, _by_kind in ran["pairs"]:
            if not by_word:
                bad.append(f"app.js files {chip!r} by its kind, as {cat!r}, not by its word")
            elif cat != day_before:
                bad.append(f"app.js files {chip!r} under {cat!r}, not {day_before!r}")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"CACR 13 goes on 3 November 2026 and went from the 4th; {len(chips)} lines, "
                  f"each {day_before} by its word in app.js and member_figures and To the Voters "
                  "on its card" + ("" if ran is not None else " (app.js or node is not here)"))


# A member's Votes tab, as renderMemberVotes draws it (option A, 23 October
# 2026), in node: the shared index set by hand, and each filter in turn.
_MEMBER_VOTES_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
globalThis.fetch = async () => ({ok: false, status: 404, text: async () => "", json: async () => null});
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({renderMemberVotes, voteHead, voteChip, BILL_RECS, IDX,"
  + "   setRCX: v => { RCX = v; }, setPage: p => { PAGE = p; },"
  + "   setMeta: m => { META = Object.assign(META || {}, m); }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
s.IDX.length = 0; fx.rows.forEach(r => s.IDX.push(r));
s.setRCX(fx.rcx);
s.setMeta({terms: ["2025-2026"]});
const out = {};
const page = extra => s.setPage(Object.assign({kind: "member", terms: ["2025-2026"],
  term: "2025-2026", data: fx.member, vfilter: "", vside: "", vq: "", vopen: {}, vshow: 0}, extra));
try {
  for (const [k, extra] of Object.entries(fx.cases)) { page(extra); out[k] = s.renderMemberVotes(fx.member); }
  out.head = s.voteHead("otp", "", {});
  out.chip = s.voteChip("override_first", false, "HB12", {Chamber: "House"});
  Object.assign(s.BILL_RECS, fx.recs);
  page({vopen: {"2026-H-1": true}}); out.ringed = s.renderMemberVotes(fx.member);
  page({vopen: {"2026-H-3": true}}); out.nobill = s.renderMemberVotes(fx.member);
  delete fx.member.rcx; s.setRCX(Object.assign({}, fx.rcx, {"2026-H-3": {"q": "adjourn", "y": 10,
    "n": 300, "p": 0}})); out.counted = s.renderMemberVotes(fx.member);
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").split("\n")[1]; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a member's Votes tab says whether each vote was on the prevailing side, by "
                   "the recorded outcome, names no party's side, and draws everyone's votes "
                   "from the bill's record", needs=("build_site_v2",))
def _member_votes_prevailing_side(V):
    """The person, 23 October 2026: "I'd rather categorize votes by whether or
    not the member voted on the prevailing side of the motion since I don't
    want to label either party as taking a position on a bill", and option A:
    the bill page's words for the motion and its result, and its ring under
    each vote. The side is the clerk's outcome's, never the larger number's:
    a failed veto override with more yeas than nays has its noes prevailing.
    No side for an absence, nor where record and ballots disagree. The shared
    index the tab reads carries the motion's key and the card's place, and no
    party split."""
    import tempfile as _tf
    rc = lambda n, q, y, nn, p, **k: {"year": "2026", "body": "H", "number": n, "question": q,
                                      "question_plain": q.lower(), "yeas": y, "nays": nn,
                                      "passed": p, "procedural": False, **k}
    rollcalls = {"2025-2026": {"HB12": [rc(1, "Ought to Pass", 200, 150, True),
                                        rc(2, "Override Veto", 220, 160, False,
                                           threshold_needed=254)],
                               "_procedural": [rc(3, "Adjourn", 10, 300, False)]}}
    # A roll call on no bill has its card too, made by the bill's own code from
    # its ballots, wherever build_data filed them ("" here), into
    # nobill/<term>.json (write_nobill_cards).
    ballot = lambda i, p_, v: {"member_id": str(i), "name": f"Pat Member{i}", "party": p_,
                               "vote": v, "body": "H"}
    votes_by_bill = {("2025-2026", ""): {"2026-H-3": [ballot(1, "R", "Yea"), ballot(2, "D", "Nay"),
                                                      ballot(3, "D", "Nay")]}}
    with _tf.TemporaryDirectory() as td:
        (Path(td) / "nobill").mkdir()
        (Path(td) / "nobill" / "1999-2000.json").write_text("{}", encoding="utf-8")
        nobill = V.write_nobill_cards(Path(td), rollcalls, votes_by_bill, {}, set())
        nb_file = json.loads((Path(td) / "nobill" / "2025-2026.json").read_text(encoding="utf-8"))
        stale_left = (Path(td) / "nobill" / "1999-2000.json").exists()
        V.write_rollcall_index(Path(td), rollcalls, {"2025-2026": {"HB12": {"2026-H-1": 0,
                                                                           "2026-H-2": 1}}},
                               nobill)
        ix = json.loads((Path(td) / "rollcalls_index.json").read_text(encoding="utf-8"))
    assert nobill == {"2025-2026": {"2026-H-3": 0}}, nobill
    nbc = nb_file["rollcalls"][0]
    assert nbc["tally"] == {"R": {"Yea": 1}, "D": {"Nay": 2}} and len(nbc["members"]) == 3 \
        and nbc["yeas"] == 10 and "_rc" not in nbc and "_ord" not in nbc, nbc
    assert not stale_left, "a term's nobill/ file an earlier build wrote outlived its votes"
    assert ix["2026-H-1"].get("mk") == "otp" and ix["2026-H-1"].get("c") == 0, ix["2026-H-1"]
    assert ix["2026-H-2"].get("mk") == "override_first" and ix["2026-H-2"].get("nd") == 254 \
        and ix["2026-H-2"].get("c") == 1, ix["2026-H-2"]
    assert ix["2026-H-3"].get("c") == 0 and ix["2026-H-3"].get("ct") == "2025-2026", (
        f"a roll call on no bill does not name its card in nobill/: {ix['2026-H-3']}")
    assert not any("s" in e for e in ix.values()), "the shared index carries a party split"

    vote = lambda n, v, b="HB12", q="": {"k": f"2026-H-{n}", "d": f"3/{n}/2026", "b": b,
                                        "y": "2026" if b else "", "q": q, "v": v}
    member = {"party_code": "D", "service": [{"b": "H"}],
              "votes": [vote(1, "Yea"), vote(2, "Yea"), vote(3, "Nay", "", "Adjourn"),
                        vote(4, "Nay", "HB40"), vote(5, "Excused", "HB40")]}
    rcx = dict(ix)
    rcx["2026-H-4"] = {"q": "itl", "y": 170, "n": 190, "p": 0, "mk": "itl",
                       "oc": "The record and the ballots disagree."}
    rcx["2026-H-5"] = {"q": "otp", "y": 300, "n": 10, "p": 1, "mk": "otp"}
    rows = [{"id": b, "n": re.sub(r"^([A-Z]+)", r"\1 ", b), "title": t, "term": "2025-2026",
             "year": 2026} for b, t in (("HB12", "relative to the twelfth thing"),
                                       ("HB40", "relative to the fortieth thing"))]
    card = {"yeas": 200, "nays": 150, "passed": True, "threshold_needed": 176, "body": "H",
            "date": "2026-03-01", "tally": {"R": {"Yea": 150, "Nay": 30}, "D": {"Yea": 50, "Nay": 120}},
            "members": [{"n": "Rep. A (R)", "p": "R", "v": "Yea", "s": "a"},
                        {"n": "Rep. B (D)", "p": "D", "v": "Nay", "s": "b"}]}
    cases = {"all": {}, "won": {"vside": "won"}, "lost": {"vside": "lost"},
             "find": {"vq": "HB 12"}, "words": {"vq": "adjourn"}, "none": {"vq": "HB 999"}}
    got = _node_app(_MEMBER_VOTES_HARNESS, {"fx.json": json.dumps(
        {"member": member, "rcx": rcx, "rows": rows, "cases": cases,
         "recs": {"2026/HB12": {"rollcalls": [card]},
                  # Its ballots add up to its count, as every real card's
                  # do, or the ring is the count's alone (ballotsAddUp).
                  "nobill/2025-2026": {"rollcalls": [dict(
                      card, yeas=10, nays=300, passed=False,
                      tally={"R": {"Yea": 6, "Nay": 150}, "D": {"Yea": 4, "Nay": 150}})]}}})})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"the Votes tab threw {got['threw']}"
    rows_of = lambda h: len(re.findall(r'<td class="d"', h))
    allh = got["all"]
    assert allh.count("On the prevailing side") == 2 and allh.count("On the losing side") == 1, (
        "the sides are not yes-carried, no-failed: the failed override's yea must lose, the failed "
        "adjournment's nay prevail, and a disputed record and an absence carry no side")
    assert "Prevailing side (2)" in allh and "Losing side (1)" in allh, "the Side select's counts"
    party = re.search(r"\b(?:with|against) (?:Republicans|Democrats)\b|Their party", allh)
    assert not party, f"the tab still names a party's side: {party.group(0)}"
    assert got["head"] and got["head"] in allh, "the motion is not in the bill page's words"
    assert got["chip"] and got["chip"] in allh, "the result is not the bill page's chip"
    for k, n in (("won", 2), ("lost", 1), ("find", 2), ("words", 1), ("none", 0)):
        assert rows_of(got[k]) == n, f"{k}: {rows_of(got[k])} rows, not {n}"
    assert rows_of(allh) == 5 and allh.count("<details data-vring=") == 5 \
        and " open>" not in allh, "every vote does not carry its ring, folded"
    # The bill page's ring has its party rows to press (data-seg), which list
    # the members; the ring of the counts alone has none.
    assert 'class="donut"' in got["ringed"] and 'data-seg="HB12|0|' in got["ringed"] \
        and "Rep. A" not in got["ringed"] \
        and "Every vote on HB 12, on its Votes tab" in got["ringed"], (
        "an opened ring is not the bill page's, drawn from the bill's record")
    # ONE DISPLAY (the person, 23 October 2026: "every vote on a rep's page
    # should be a roll call ... The two displays should not be structured
    # differently"): a roll call on no bill opens the same ring with party
    # rows, from its term's nobill/ file, and links no bill.
    assert 'data-seg="NB-2025-2026|0|' in got["nobill"] \
        and "Every vote on" not in got["nobill"].split('data-vring="2026-H-3"')[1][:4000], (
        "a roll call on no bill does not open the bill page's ring from nobill/")
    # Only an older build's index, with no card named, falls back to the counts.
    assert 'class="donut"' in got["counted"] and "data-seg=" not in got["counted"], (
        "a roll call with no card named is not drawn from its counts")
    return "ok", ("prevailing by the outcome, no party's side, the bill page's words, filters and "
                  "search, and the bill page's ring, party rows and all, under every roll call, "
                  "on a bill or on none")


@check("build", "without the caption files, their summary withholds the same times")
def _caption_summary_fixture():
    """The nightly's machine is given caption_spans.json and none of the 20 GB
    of caption files. On the laptop 156 times on 13 recordings are withheld
    because their tracks run an hour late, and before the summary a build
    without the files compared nothing and withheld nothing -- 89 stated and
    67 clustered starts, most an hour early, under one printed line.

    So the fixture of the check above has its summary written by
    caption_span.py --write and then its caption files taken away: VID4 must
    still lose its times, VID1 keep them, and the build say the summary
    answered. A recording with times and no entry must lose them as well -- a
    summary that fell behind costs a "start not identified", never a start an
    hour early -- and a summary that will not read must stop the build rather
    than be passed over.
    """
    here = Path(".").resolve()
    if not (_paths.locate("build_site_v2.py").exists()
            and _paths.locate("caption_span.py").exists()):
        return "skip", "build_site_v2.py or caption_span.py not here"
    root = Path(tempfile.mkdtemp(prefix="gr-spans-"))
    try:
        _site_fixture(root)
        (root / "work" / "VID4" / "captions.en.json3").write_text(_json3_cues([
            (300000, "will open the executive session on House Bill 1442"),
            (1196000, "we are adjourned")]), encoding="utf-8")
        (root / "work" / "VID1" / "captions.en.json3").write_text(_json3_cues([
            (150000, "I am opening the hearing on House Bill 1442"),
            (892000, "thank you all")]), encoding="utf-8")
        with open(root / "videos_house_fixture.csv", "w", newline="",
                  encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["video_id", "title", "duration_iso"])
            wr.writerow(["VID1", "House Commerce", "PT15M30S"])
            wr.writerow(["VID4", "House Commerce", "PT2H"])
        r = _run([sys.executable, _paths.script("caption_span.py"), "--write"],
                 cwd=root, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]
        summary = root / "caption_spans.json"
        doc = json.loads(summary.read_text(encoding="utf-8"))
        assert {"VID1", "VID4"} <= set(doc["recordings"]), (
            f"caption_span.py --write summarised {sorted(doc['recordings'])}, "
            "not both recordings with captions")
        for v in ("VID1", "VID4"):
            (root / "work" / v / "captions.en.json3").unlink()
        # And a second --write where the captions are not must keep what the
        # first one read, not replace it with nothing.
        r = _run([sys.executable, _paths.script("caption_span.py"), "--write"],
                 cwd=root, capture_output=True, text=True, timeout=120)
        again = json.loads(summary.read_text(encoding="utf-8"))["recordings"]
        assert again == doc["recordings"], (
            "caption_span.py --write on a machine without the captions changed "
            "the entries made where they were")

        def build():
            r = _run([sys.executable, _paths.script("build_site_v2.py"),
                      "--data", "data", "--out", "site", "--segments", "work"],
                     cwd=root, capture_output=True, text=True, timeout=180)
            if r.returncode != 0:
                return r, {}
            rec = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                             .read_text(encoding="utf-8"))
            return r, {s.get("video_id"): s for s in rec.get("stations") or []}

        r, by = build()
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]
        late, kept = by.get("VID4") or {}, by.get("VID1") or {}
        assert late.get("start") is None and late.get("state") == "approximate", (
            "with only the summary, VID4 -- whose captions stop 100 minutes short "
            f"-- still reads {late.get('state')} at {late.get('start')}")
        assert kept.get("start") is not None, (
            "with only the summary, VID1 lost the start its in-step track gives it")
        assert "answered by caption_spans.json" in r.stdout, (
            "the build did not say the summary answered for the missing captions")

        doc["recordings"].pop("VID1")
        summary.write_text(json.dumps(doc), encoding="utf-8")
        r, by = build()
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]
        assert (by.get("VID1") or {}).get("start") is None, (
            "VID1 has times, no caption file and no entry in the summary, and its "
            "start was published unchecked")
        assert "neither a caption file" in r.stdout and "VID1" in r.stdout, (
            "the build withheld a recording the summary does not know without "
            "saying so")

        summary.write_text("{", encoding="utf-8")
        r, _ = build()
        assert r.returncode != 0 and "caption_spans.json" in (r.stderr + r.stdout), (
            "a caption summary that will not read was passed over and the build "
            "went on as though nothing needed checking")
        # And one that knows almost none of the recordings is the wrong one,
        # not one that fell behind: forty recordings, an empty summary.
        import build_site_v2 as B
        empty = root / "empty_spans.json"
        empty.write_text('{"recordings": {}}', encoding="utf-8")
        forty = {f"V{i:03d}": [{"located": True}] for i in range(40)}
        try:
            B.withhold_late_captions(forty, {}, str(root / "work"), str(empty))
            raise AssertionError("an empty caption summary withdrew every time "
                                 "and the build went on")
        except SystemExit as e:
            assert "wrong summary or an empty one" in str(e), str(e)
        return "ok", ("with the caption files gone, the summary withholds VID4 and "
                      "keeps VID1; a recording it does not know loses its times; "
                      "one that will not read, or knows almost nothing, stops the "
                      "build; --write keeps what it cannot see")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the site build's load() stops on a JSON input that is there and cannot be read, "
       "and _redirects' movers do the same", needs=("build_site_v2", "build_pages"))
def _load_stops_on_corrupt_input(B2, BP):
    """Bug hunt of 11 November 2026, findings 1 and 11. load() returned its
    default for every failure, so a narratives.json cut off mid-array (or a
    MemoryError reading it) built a site with no journeys and nothing said.
    Only a file that is not there is empty; a file that is there and is not
    JSON stops the build, naming the file. The same for the moved-member and
    moved-request 301s in build_pages, which dropped them from _redirects."""
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-load-"))
    try:
        os.chdir(tmp)
        good = tmp / "good.json"
        good.write_text('{"a": 1}', encoding="utf-8")
        assert B2.load(good, {}) == {"a": 1}, "load() no longer reads a good file"
        assert B2.load(tmp / "absent.json", {"d": 1}) == {"d": 1}, "an absent file is the default"
        for name, text in (("cut.json", '{"HB1": [{"x": 1}, {"y"'), ("empty.json", ""),
                           ("junk.json", "not json")):
            p = tmp / name
            p.write_text(text, encoding="utf-8")
            try:
                got = B2.load(p, {})
            except SystemExit as e:
                assert name in str(e), f"the message does not name {name}: {e}"
            else:
                raise AssertionError(f"load({name}) returned {got!r} instead of stopping the build")
        site = tmp / "site"
        site.mkdir()
        assert BP.moved_members(site) == "", "no former.json is no moved members"
        (site / "former.json").write_text('[{"slug": "x", "moved_fr', encoding="utf-8")
        try:
            BP.moved_members(site)
        except SystemExit as e:
            assert "former.json" in str(e), e
        else:
            raise AssertionError("an unreadable former.json dropped the moved members' 301s silently")
        (site / "meta.json").write_text('{"requests": {"term": "2027"}}', encoding="utf-8")
        assert BP.moved_requests(site) == "", "no index file is no moved requests"
        (site / "idx").mkdir()
        (site / "idx" / "2027.json").write_text("[{", encoding="utf-8")
        try:
            BP.moved_requests(site)
        except SystemExit:
            pass
        else:
            raise AssertionError("an unreadable requests index dropped their 301s silently")
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", "a cut-off, empty or junk input stops load(); only an absent file is the default"


@check("build", "a withdrawn bill says Withdrawn, from the journal or the docket",
       needs=("build_site_v2", "build_bill_pages", "build_feeds"))
def _withdrawn_status(B, BP, BF):
    """A bill the House Journal alone carries reads Withdrawn, kind done,
    credited to the House Journal -- never to the General Court's status page
    -- with a dated rail of introduction then withdrawal, no docket row of its
    own invented, and no docket or status-page address, which would be built
    from an LSR it does not have. Its journal is linked where the drain
    fetched it.

    And a withdrawal the DOCKET records as adopted is an ending too: HB 641 of
    2013, "Withdrawn Under House Rule 38(e) (Rep Cebrowski): MA VV", read "In
    committee". One that failed changes nothing: HB 431 of 2025, "Persuant to
    House Rule 39(e), Withdrawn: MF RC 160-207", which the House then passed.

    Its note says only what was looked at -- the General Court's data files,
    the docket among them -- and nothing of a status page nobody asked for.
    A reader without JavaScript is given the journals, not an empty list; and
    its sponsors' feeds date the sponsorship by its introduction, where a
    bill with no docket event used to be dated afresh every night.
    """
    jrec = {"bill": "HB476", "lsr": "", "lsr_year": "2025", "lsr_num": "",
            "title": "relative to restrictions on elective abortion.", "chamber": "H",
            "house_committee": "Judiciary", "senate_committee": "",
            "designation": "HB 476-FN", "suffix": "-FN",
            "journal": {"introduced": {"date": "2025-01-09", "journal": "HJ 3", "page": 12},
                        "withdrawn": {"date": "2025-02-06", "journal": "HJ 4", "page": 1,
                                      "how": "motion", "vote": "335-18, division",
                                      "reconsideration": "failed, 15-340"}}}
    d = B.bill_disposition(jrec, "HB476", {}, None, [], "2025-2026", "2025-2026")
    assert (d.kind, d.status, d.source) == ("done", "Withdrawn", "House Journal"), d

    def narr(raw, motion):
        return {"events": [
            {"date": "2013-01-03", "type": "introduced", "body": "H", "cancelled": False,
             "raw": "Introduced 1/3/2013 and Referred to Municipal and County Government"},
            {"date": "2013-02-06", "type": "floor", "body": "H", "cancelled": False,
             "raw": raw, "action": raw.split(":")[0], "motion": motion}]}
    ma = narr("Withdrawn Under House Rule 38(e) (Rep Cebrowski): MA VV", "MA")
    mf = narr("Persuant to House Rule 39(e), Withdrawn: MF RC 160-207", "MF")
    arch = {"gen_status": "HOUSE", "house_status": "MISCELLANEOUS", "senate_status": ""}
    d = B.bill_disposition({}, "HB641", arch, ma, [], "2013-2014", "2025-2026")
    assert (d.kind, d.status) == ("done", "Withdrawn"), (
        f"a withdrawal the docket records as adopted reads {d.status!r}")
    d = B.bill_disposition({}, "HB641", {}, ma, [], "2025-2026", "2025-2026")
    assert (d.kind, d.status) == ("done", "Withdrawn"), d
    d = B.bill_disposition({}, "HB431", {}, mf, [], "2025-2026", "2025-2026")
    assert d.status != "Withdrawn", "a withdrawal motion that FAILED withdrew the bill"
    assert B.classify(mf, [], "HB")[1] == "In committee", B.classify(mf, [], "HB")
    for not_a_bill in ("REP. HEALY SUB ITL,WITHDRAWN; PASSED VV",
                       "Withdraw From Joint Committee (Reps Wallner and Hess)",
                       "Withdrawn from Consent Calendar",
                       "Per House Rule 38, Withdrawn from Committee"):
        assert not B.WITHDRAWN_ACT.search(not_a_bill), not_a_bill
    # The rule cited without "to" -- SB 78 of 2025's docket -- is the same act.
    for spelled in ("Persuant House Rule 39(e), Withdrawn: MF DV 2025-1713h",
                    "Pursuant to House Rule 39(e), Withdrawn"):
        assert B.WITHDRAWN_ACT.search(spelled), spelled
    mf_dv = narr("Persuant House Rule 39(e), Withdrawn: MF DV 2025-1713h", "MF")
    d = B.bill_disposition({}, "SB78", {}, mf_dv, [], "2025-2026", "2025-2026")
    assert d.status != "Withdrawn", "a withdrawal motion that FAILED withdrew the bill"

    here = Path(".").resolve()
    root = Path(tempfile.mkdtemp())
    try:
        # A journal the drain fetched, for the citation's link.
        (root / "archive").mkdir()
        (root / "archive" / "queue.csv").write_text(
            "chamber,kind,year,name,url,path,state,attempts,error,bytes,fetched\n"
            "H,journal,2025,HJ 04 February 6 2025.pdf,https://example.invalid/hj4.pdf,"
            "\"journals\\2025\\HJ 04 February 6, 2025.pdf\",held,0,,1,\n", encoding="utf-8")
        out = root / "site"
        out.mkdir()
        bills = {"2025-2026": {"HB476": jrec},
                 "2013-2014": {"HB641": {"bill": "HB641", "lsr": "2013-0123",
                                         "lsr_year": "2013", "lsr_num": "0123",
                                         "title": "relative to penalties", "chamber": "H",
                                         "archived": True, **arch}}}
        os.chdir(root)
        try:
            with open(os.devnull, "w") as quiet:
                import contextlib
                with contextlib.redirect_stdout(quiet):
                    idx, *_ = B.build_bills(out, bills, {"2013-2014": {"HB641": ma}},
                                            {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {},
                                            {}, {}, {}, {}, {})
        finally:
            os.chdir(here)
        row = {r["id"]: r for r in idx}
        j = row["HB476"]
        assert (j["status"], j["kind"], j["passage"], j["last_action"]) == (
            "Withdrawn", "done", "Hx--x", "2025-02-06"), j
        assert (row["HB641"]["status"], row["HB641"]["kind"]) == ("Withdrawn", "done"), (
            row["HB641"])
        page = json.loads((out / "bills" / "2025" / "HB476.json").read_text(encoding="utf-8"))
        assert page["status_source"] == "House Journal", page["status_source"]
        assert page["docket_url"] == "" and page["events"] == [] and page["lsr"] == "", (
            "a journal record carries a docket address or docket rows")
        kinds = [x["kind"] for x in page["documents"]]
        assert "status" not in kinds and "docket" not in kinds, page["documents"]
        assert any(x["url"] == "https://example.invalid/hj4.pdf" for x in page["documents"]), (
            f"the journal that withdrew it is not linked: {page['documents']}")
        rail = page["journey"]["rail"]
        assert [(s["stop"], s["date"]) for s in rail[:2]] == [
            ("Introduced", "2025-01-09"), ("House", "2025-02-06")], rail
        assert page["journey"]["steps"][0]["act"] == "withdrawn"
        assert page["next_step"] == "Withdrawn", page["next_step"]
        assert len(page["notes"]) == 1 and "House Journal" in page["notes"][0], page["notes"]
        assert "do not list this bill" in page["notes"][0] and (
            "status page" not in page["notes"][0]), (
            f"the note speaks for more than was looked at: {page['notes']}")
        # The record a reader without scripts reads (static_record, which
        # replaced the noscript block on 12 October 2026) offers it too.
        html = BP.static_record(j, page)
        assert "https://example.invalid/hj4.pdf" in html and "<ul></ul>" not in html, (
            f"a reader without JavaScript is offered no journal: {html[-300:]}")
        assert BF.filed_date(page) == "2025-01-09", (
            f"a sponsorship with no docket is dated {BF.filed_date(page)!r}, not by its "
            "introduction")
        assert BF.filed_date({"events": [{"date": "2013-02-06"}, {"date": "2013-01-03"},
                                         {"date": ""}]}) == "2013-01-03"
        old = json.loads((out / "bills" / "2013" / "HB641.json").read_text(encoding="utf-8"))
        assert old["docket_url"] and any(x["kind"] == "docket" for x in old["documents"]), (
            "a bill with an LSR lost its docket address")
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("a journal record: Withdrawn, done, Hx--x, credited to the House "
                  "Journal, no docket or status-page address; a docket's adopted "
                  "withdrawal is Withdrawn, a failed one is not")


@check("naming", "a bill whose ending is only on the status page says so once",
       needs=("build_site_v2",))
def _closing(build_site_v2):
    cs = build_site_v2.closing_stage
    stage = lambda t: {"stages": [{"label": "x", "text": t}]}
    # The docket records actions, and a session ending is not one -- it just
    # stops. 117 bills end with a committee report and a red headline the
    # status page alone knows about.
    got = cs("Died when the session ended",
             stage("The committee met in executive session to vote on its "
                   "recommendation."))
    assert got and "died when the session ended" in got["text"].lower(), got
    # Said once. These narratives already carry the ending, in the site's own
    # words, and a second paragraph repeating it reads as a stutter.
    for told in ("The bill died on the table when the session ended on "
                 "August 19, 2026, having been set aside and never taken back up.",
                 "It died when the session ended."):
        assert cs("Died when the session ended", stage(told)) is None, told
    # And not confused with a committee RECOMMENDING interim study, which is
    # the phrase "after the session ends" and is not an ending at all. An
    # earlier guard tested for "kill it" anywhere and matched every bill whose
    # committee recommended the chamber kill it -- suppressing the paragraph
    # on all 111 of them.
    rec = stage("The majority recommended that the House study it after the "
                "session ends, and the minority recommended that the House "
                "kill it, by a vote of 11-7.")
    assert cs("Died when the session ended", rec),         "a committee's recommendation was read as the bill's ending"
    # Killed is deliberately absent: the status page reports it for bills whose
    # docket already says what ended them.
    assert cs("Killed", stage("anything")) is None,         "Killed is back in the table, and it misfires on bills laid on the table"
    assert cs("Signed into law", stage("anything")) is None
    return "ok", "the ending is added when it is missing and not when it is not"


@check("data", "a hearing's sign-in count says whether it is that hearing's",
       needs=("build_site_v2",))
def _testimony_dated(build_site_v2):
    """30,108 people signed in against HB283. On which day matters.

    The database carries the hearing date with each sign-in, so the count can
    sit with the hearing it belongs to. Where it has the bill but not that
    date -- 50 of 2,122 docket hearing lines -- the whole-bill total is still
    true of the bill and is not true of that hearing, and the page has to say
    which of the two it is showing.
    """
    f = getattr(build_site_v2, "hearing_testimony", None)
    assert f, "build_site_v2 has no hearing_testimony"
    tdb = {"total": 300, "support": 100, "oppose": 200, "neutral": 0,
           "hearings": [{"date": "2026-02-03", "total": 120, "support": 40,
                         "oppose": 80, "neutral": 0}]}
    hear = {"raw": "Public Hearing: 02/03/2026 10:00 am LOB 302",
            "date": "2026-02-03"}
    got = f(hear, tdb, None)["testimony"]
    assert got["total"] == 120, f"the hearing shows {got['total']}, not its own 120"
    assert got.get("dated") is True, "a count for this hearing does not say so"

    other = {"raw": "Public Hearing: 05/05/2026 10:00 am LOB 302",
             "date": "2026-05-05"}
    got2 = f(other, tdb, None)["testimony"]
    assert got2["total"] == 300, got2["total"]
    assert not got2.get("dated"), (
        "a whole-bill total is presented as this hearing's count")

    # And a line that is not a hearing carries none of it.
    assert f({"raw": "Ought to Pass: MA VV 03/06/2026", "date": "2026-03-06"},
             tdb, None) == {}, "a floor vote was given a sign-in count"
    return "ok", "the hearing's own count, or the bill's, and it says which"


@check("naming", "a hearing report lands on its own Senate hearing, legislators as members",
       needs=("build_site_v2", "senate_hearing_reports"))
def _hearing_report_attach(build_site_v2, senate_hearing_reports):
    """The report goes on the Senate public hearing of that bill and that
    date, and nowhere else; a legislator who testified is drawn as the member
    only where exactly one member can be meant.

    A wrong member in a chip is a factual error on a page General Court staff
    read. A missing chip is not, so every doubt resolves to plain text.
    """
    B, S = build_site_v2, senate_hearing_reports
    for f in ("speaker_index", "resolve_speaker", "attach_hearing_reports"):
        assert hasattr(B, f), f"build_site_v2 has no {f}"
    if not Path("tests/senate_hearing_reports.json").exists():
        return "skip", "tests/senate_hearing_reports.json not here"
    people = [
        {"id": "S23", "name": "Gannon, Bill", "last": "Gannon", "first": "Bill",
         "chamber": "S", "party_code": "R", "district": "23"},
        {"id": "H26", "name": "See, Alvin", "last": "See", "first": "Alvin",
         "chamber": "H", "party_code": "D", "district": "26",
         "county": "Merrimack", "county_abbr": "Merr"},
        {"id": "H1", "name": "Smith, Ann", "last": "Smith", "first": "Ann",
         "chamber": "H", "party_code": "R"},
        {"id": "H2", "name": "Smith, Bob", "last": "Smith", "first": "Bob",
         "chamber": "H", "party_code": "D"},
        {"id": "H13", "name": "Prudhomme-O'Brien, Katherine",
         "last": "Prudhomme-O'Brien", "first": "Katherine", "chamber": "H",
         "party_code": "R"}]
    idx = B.speaker_index(people)

    def who(line):
        m = B.resolve_speaker(line, idx, S.name_part)
        return m and m["id"]
    assert who("Senator Gannon, Prime Sponsor") == "S23"
    assert who("Senator Bill Gannon") == "S23"
    assert who("Representative Alvin See, Merrimack 26") == "H26"
    assert who("Representative Bob Smith") == "H2"
    # The report's typeset apostrophe against the roster's plain one.
    assert who("Representative Katherine Prudhomme-O’Brien, Rockingham "
               "– District 13") == "H13"
    for line in ("Rep. Smith",                 # two of them
                 "Senator Alvin See",           # the wrong chamber
                 "Senator Tim Gannon",          # a first name that disagrees
                 "Liz Tentarelli, League of Women Voters N.H.",
                 "Senators Bill Gannon and Tim McGough",
                 # Two people's heading, cut at the bracket: HB 1766's shape.
                 "Representatives Alvin See (Merr. 26) and Ann Smith"):
        assert who(line) is None, f"{line!r} was drawn as member {who(line)}"

    rec = _hearing_fixture(S)["SB11"][0]
    stations = [{"body": "H", "what": "hearing", "when": "2025-01-14"},
                {"body": "S", "what": "floor debate", "when": "2025-01-14"},
                {"body": "S", "what": "hearing", "when": "2025-01-14"}]
    tally, un = Counter(), []
    # A report dated a day the docket has no Senate hearing on, twice: the
    # bill's and an amendment's, filed the same afternoon.
    late = {**rec, "heard": "2025-01-30"}
    B.attach_hearing_reports(stations, [rec, late, late],
                             "SB11", idx, S.name_part, tally, un)
    assert [bool(s.get("reports")) for s in stations[:3]] == [False, False, True], (
        "the report went on another sitting: "
        + json.dumps([bool(s.get("reports")) for s in stations]))
    assert un == ["SB11 2025-01-30"] * 2 and tally["unmatched"] == 2 \
        and tally["matched"] == 1, (
        f"a report with no hearing that day was not named: {un}, {dict(tally)}")
    # 20 REPORTS OF 1,293 WERE ON NO PAGE, their date one the docket does not
    # carry. The person decided on 24 September that they are shown under the
    # report's own date. One station for the date, which says where the date
    # came from and what the docket has instead, and offers no recording.
    assert len(stations) == 4, f"{len(stations)} stations, not the docket's 3 and one for the report"
    own = stations[3]
    assert (own.get("when"), own.get("body"), own.get("dated_by")) == (
        "2025-01-30", "S", "report"), own
    assert len(own.get("reports") or []) == 2, "the amendment's report did not share its date's station"
    assert own.get("docket_heard") == ["2025-01-14"], own.get("docket_heard")
    assert not own.get("video_id") and own.get("start") is None \
        and own.get("state") == "novideo", own
    assert own.get("committee") == "Election Law and Municipal Affairs", own.get("committee")
    page = stations[2]["reports"][0]
    first = page["sections"][0]["speakers"][0]
    assert first.get("member", {}).get("label") == "Senator Gannon", first
    assert first["member"].get("slug"), "a resolved member carries no page"
    assert "member" not in page["sections"][1]["speakers"][0], (
        "a member of the public was drawn as a member")
    assert not ({"filed", "bill"} & set(page)), sorted(page)
    # The parser's reasons for keeping a report as text are its own, not the
    # reader's, and do not travel in the page.
    prose = B.hearing_report_for_page(_hearing_fixture(S)["SB160"][0], idx,
                                      S.name_part)[0]
    assert "fallback" not in prose and all(
        "text" in s for s in prose["sections"]), sorted(prose)
    return "ok", ("on its own hearing only, the rest named; members only "
                  "where one is meant")


@check("data", "every bill's chip on the built site is the word chip_word gives its status, "
               "wherever it is written, and no chip shows how a bill ended",
       needs=("build_site_v2",))
def _site_chips(B):
    """The data half of _chip_words. Each term's index (site/idx/<term>.json,
    which the bill list, the member and committee pages and the downloads all
    read) against build_site_v2.chip_word: every row of a bill carries a
    chip; it is the word chip_word gives the row's own kind and status, live
    only in the current term and only where status/status.txt names no
    session_over for it; and it is one of the six words, or a still-moving
    bill's stage, an adopted resolution's or a CACR's word, or a word the
    person has not yet given one of the six -- never "Killed", "Died on the
    table", "Vetoed, override failed" or any other ending, which stay in the
    status. bills.csv's chip column, a committee's rows and the directory's
    lists say the same."""
    idx = Path("site/idx")
    files = sorted(p for p in idx.glob("*.json")) if idx.exists() else []
    if not files:
        return "skip", "no site/idx/ -- build the site first"
    rows = []
    for f in files:
        rows += [r for r in json.loads(f.read_text(encoding="utf-8")) if not r.get("lsr")]
    terms = sorted({r.get("term") or "" for r in rows} - {""})
    current = terms[-1] if terms else ""
    over = B.session_over_in(B.session_over("corrections/status/status.txt"), current)
    six = set(B.CHIP_WORDS)
    bad, n, per = [], Counter(), Counter()
    unbuilt = [f"{r.get('term')} {r.get('id')}" for r in rows if "chip" not in r]
    assert not unbuilt, (f"{len(unbuilt):,} index rows carry no chip, {unbuilt[0]} among them: "
                         "the site was built by code older than chip_word -- rebuild it")
    for r in rows:
        live = r.get("term") == current and not over
        kind, status, chip = r.get("kind") or "", r.get("status") or "", r["chip"]
        want = B.chip_word(kind, status, live)
        if chip != want:
            bad.append(f"{r.get('term')} {r.get('id')}: {chip!r} for {kind} {status!r}, "
                       f"not {want!r}")
        elif chip not in six and not (chip == status and (
                (kind == "active" and live) or kind == "adopted" or status in B.CHIP_KEEPS)):
            bad.append(f"{r.get('term')} {r.get('id')}: the chip says {chip!r}, an ending")
        elif chip in ("Tabled", "Vetoed") and not live:
            bad.append(f"{r.get('term')} {r.get('id')}: {chip} with its session over")
        n[chip] += 1
        if chip not in six:
            per[f"{kind} {chip}"] += 1
    csvf = Path("site/data/bills.csv")
    if csvf.exists():
        said = {(r.get("term"), r.get("id")): r["chip"] for r in rows}
        with csvf.open(encoding="utf-8", newline="") as fh:
            got = {(x["term"], x["bill"]): x.get("chip") for x in csv.DictReader(fh)}
        off = [f"{t} {b}: {got.get((t, b))!r}, not {c!r}" for (t, b), c in said.items()
               if (t, b) in got and got[(t, b)] != c]
        if off:
            bad.append(f"bills.csv's chip column disagrees with the index on {len(off):,}: "
                       + "; ".join(off[:3]))
    # AND THE TWO OTHER PLACES THE WORD IS WRITTEN, each from its own copy of
    # the row: a committee's bills (site/committee/<code>.json), which its page
    # draws cards and its select from, and the directory's lists
    # (site/directory/bills-<term>.html), which print the word beside each
    # bill. Either could print the status while the index said the chip.
    import html as _html
    said = {(r.get("term"), r.get("id")): r["chip"] for r in rows}
    n_cmte = n_dir = 0
    off = []
    for f in sorted(Path("site/committee").glob("*.json")):
        for term, items in (json.loads(f.read_text(encoding="utf-8")).get("bills") or {}).items():
            for r in items:
                key = (r.get("term") or term, r.get("id"))
                if key in said:
                    n_cmte += 1
                    if r.get("chip") != said[key]:
                        off.append(f"committee {f.stem} {key[0]} {key[1]}: "
                                   f"{r.get('chip')!r}, not {said[key]!r}")
    li = re.compile(r'<li><a href="[^"]*?bill/\d{4}/([a-z0-9]+)[^"]*">[^<]*</a>[^<]*'
                    r'(?:<span class="dirstatus">([^<]*)</span>)?</li>')
    for term in terms:
        page = Path(f"site/directory/bills-{term}.html")
        if not page.exists():
            continue
        for bid, word in li.findall(page.read_text(encoding="utf-8")):
            key = (term, bid.upper())
            if key in said:
                n_dir += 1
                if _html.unescape(word) != said[key]:
                    off.append(f"directory {term} {key[1]}: {word!r}, not {said[key]!r}")
    if off:
        bad.append(f"{len(off):,} committee or directory rows say another word than the "
                   "index's chip: " + "; ".join(off[:3]))
    elif Path("site/directory").exists() and not n_dir:
        bad.append("no bill read off the directory's lists: their markup has changed under "
                   "this check")
    assert not bad, f"{len(bad):,} chips: " + "; ".join(bad[:5])
    return "ok", (f"{len(rows):,} bills across {len(terms)} terms: "
                  + ", ".join(f"{w} {n[w]:,}" for w in B.CHIP_WORDS)
                  + f"; {sum(per.values()):,} keep a word that is not one of the six "
                  + f"({', '.join(f'{k} {v:,}' for k, v in per.most_common(3))}"
                  + (", ..." if len(per) > 3 else "") + ")"
                  + f"; {n_cmte:,} committee rows and {n_dir:,} directory entries agree"
                  + (f"; the session of {current} ended {over}" if over else ""))


@check("data", "a bill the governor signed says so")
def _signed():
    if not (Path("narratives.json").exists() and _paths.locate("build_site_v2.py").exists()):
        return "skip", "narratives.json or build_site_v2.py not here"
    bs = imp("build_site_v2")
    assert bs, "build_site_v2.py will not import"
    nvf = _narratives()
    # {term: {bill: record}}. This is a check on the whole record, so it reads
    # every term rather than one.
    nv = {b: r for byb in nvf.values() for b, r in byb.items()}
    # The clerk writes it two ways -- "Signed by Governor Ayotte 7/10/2026" and
    # "Signed by the Governor on 7/10/2026" -- and the pattern knew only the
    # first. 233 of the 632 signatures on the record went unrecognised, and the
    # status page carries no governor field at all for those bills, so they
    # kept whatever they had been before: "Passed one chamber" for 137,
    # "Passed, awaiting the governor" for 82, "In committee" for nine and
    # "Killed" for five bills that are law.
    signed = getattr(bs, "SIGNED_RE", None)
    assert signed is not None, ("build_site_v2 has no SIGNED_RE, so the two "
                               "spellings of the signature are not both read")
    both = {"signed by governor": 0, "signed by the governor": 0}
    missed = []
    for bill, v in nv.items():
        text = " ".join(e.get("raw", "") for e in v.get("events", []))
        m = re.search(r"signed by (?:the )?governor", text, re.I)
        if not m:
            continue
        both[m.group(0).lower()] = both.get(m.group(0).lower(), 0) + 1
        if not signed.search(text.lower()):
            missed.append(bill)
    assert not missed, (f"{len(missed):,} bills the docket says were signed are "
                        f"not matched, e.g. {missed[:5]}")
    assert all(both.values()), (
        f"only one spelling is present, so this check proves nothing: {both}")
    return "ok", (f"{sum(both.values()):,} signatures, "
                  + " and ".join(f"{v:,} {k!r}" for k, v in both.items()))


@check("data", "a sponsor is named the same way whether or not they still serve")
def _sponsor_names():
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    bs = imp("build_site_v2")
    assert bs, "build_site_v2.py will not import"
    # The three ways a sponsor's name reaches the join. The status page writes
    # the party letter in lower case, and surnames are not always one word.
    for raw, want in (("Howard Pearl (r)", "pearl, howard"),
                      ("Rep. Jodi Nelson (R - Rock 13)", "nelson, jodi"),
                      ("Nelson, Jodi", "nelson, jodi")):
        got = bs.sort_name(raw)
        assert got == want, f"sort_name({raw!r}) is {got!r}, expected {want!r}"
    # name_key pairs the first and last word, so a surname of any length meets
    # its own "Last, First" spelling.
    for a, b in (("Rebecca Perkins Kwoka", "Perkins Kwoka, Rebecca"),
                 ("Erica de Vries", "de Vries, Erica"),
                 ("Matt Sabourin dit Choiniere", "Sabourin dit Choiniere, Matt"),
                 ("Howard Pearl (r)", "Pearl, Howard")):
        ka, kb = bs.name_key(a), bs.name_key(b)
        assert ka and ka == kb, f"name_key({a!r})={ka!r} != name_key({b!r})={kb!r}"
    # Both spellings of a county abbreviation would let a reader tell which
    # members had left, because only they took the second one.
    assert not [v for v in bs.COUNTY_ABBR.values() if v.endswith(".")],         f"county abbreviations still carry a trailing point: {bs.COUNTY_ABBR}"
    return "ok", ("surnames of any length, either spelling, and the party letter "
                  "in either case")


# THE WORDS A RENDERER USED TO TYPE FOR ITSELF, as the copy would be written
# again: (what it is, a pattern made from the words that finds it). Read over
# every builder, script and template in src/pages/, the words' own files aside.
def _word_copies(W):
    pats = []
    for k, (word, cls) in W["meeting_kinds"]["kinds"].items():
        pats.append((f"the meeting kind {k!r}",
                     rf'"{re.escape(k)}"\s*:\s*[\[(]\s*"{re.escape(word)}"\s*,\s*"{re.escape(cls)}"'))
    for cls, word in W["meeting_kinds"]["legend"]:
        pats.append((f"the key's {word!r}",
                     rf'[\[(]\s*"{re.escape(cls)}"\s*,\s*"{re.escape(word)}"\s*[\])]'))
    pats.append(("the small words of a meeting's title",
                 r'\s*,\s*'.join(f'"{re.escape(w)}"' for w in W["meeting_kinds"]["small"][:4])))
    for table in ("chip", "category"):
        for word, cls in W["chips"][table].items():
            pats.append((f"the {table} {word!r}",
                         rf'"{re.escape(word)}"\s*:\s*"{re.escape(cls)}"'))
    for kind, cls in W["chips"]["kind"].items():
        pats.append((f"the kind {kind!r}'s class",
                     rf'(?<![\w"]){re.escape(kind)}\s*:\s*"{re.escape(cls)}"|"{re.escape(kind)}"\s*:\s*"{re.escape(cls)}"'))
    for table, what in (("chip", "the six chip words"), ("category", "the Status filter's categories")):
        pats.append((what, r'[\[(]\s*' + r'\s*,\s*'.join(f'"{re.escape(w)}"' for w in W["chips"][table])))
    return [(what, re.compile(p)) for what, p in pats]


@check("frontend", "the words are written once: src/pages/words/ read by Python, written into "
                   "components.js between its markers by the build, and copied by no renderer",
       needs=("build_site_v2",))
def _words_written_once(B):
    """The component plan's C3 (approved 9 October 2026; step 2): the chip's
    words and classes, the kinds of meeting, the vote words and the glossary
    are JSON in src/pages/words/. components.py reads them as WORDBOOK for the
    builders, and the build writes the same into site/components.js between
    its WORDBOOK markers (build_pages.with_words), where app.js reads them.

    IT REPLACED _meet_kind_agrees, which held two copies alike: MEET_KIND
    was typed in build_pages.py and again in app.js, the calendar card drawn
    by both, and a copy left behind would have shown "Executive session" on
    one page and "executive session", uncoloured, on another, for the same
    meeting. There is one copy now, so this holds that it stays one:

      - every words file is a JSON object with notes ("_about"), and
        components.WORDBOOK is each of them by name, the notes left out;
      - the builders read them: build_pages.MEET_KIND, MEET_LEGEND and the
        small words of kind_title, and build_site_v2's six chip words;
      - app.js reads its chip classes and meeting kinds from WORDBOOK, and no
        builder, script or template in src/pages/ types any of these words
        out again as a table (_word_copies);
      - components.js in src/pages/ carries one WORDBOOK:START line and one
        WORDBOOK:END line after it with nothing between, so the words are not
        typed into it either;
      - with_words writes them between the markers in the file's own line
        ending and changes nothing else, and refuses -- a ValueError, which
        stops the build -- a marker missing, doubled, reversed or not
        beginning its line;
      - the run's fixture build put exactly that into site/components.js.

    That the browser's WORDBOOK equals Python's, byte for byte, is
    _components_agree's, which runs the file in node.
    """
    import build_pages as BP
    import components as C
    wd = Path("src/pages/words")
    files = sorted(wd.glob("*.json"))
    assert files, f"{wd.as_posix()}/ holds no words"
    bad, read = [], {}
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            bad.append(f"{f.name} is not JSON: {e}")
            continue
        if not isinstance(d, dict) or not d.get("_about"):
            bad.append(f"{f.name} is not an object with its notes under _about")
            continue
        read[f.stem] = {k: v for k, v in d.items() if not k.startswith("_")}
    missing = {"chips", "meeting_kinds", "votes", "glossary"} - set(read)
    if missing:
        bad.append(f"no words file for {', '.join(sorted(missing))}")
    if C.WORDBOOK != read or list(C.WORDBOOK) != list(read):
        differ = [k for k in set(C.WORDBOOK) | set(read) if C.WORDBOOK.get(k) != read.get(k)]
        bad.append(f"components.WORDBOOK is not the words files as they stand, the notes left "
                   f"out: it holds {list(C.WORDBOOK)}, the folder {list(read)}, and they differ "
                   f"in {sorted(differ) or 'their order'}")
    assert not bad, " | ".join(bad)
    W = C.WORDBOOK

    # The builders read them.
    if BP.MEET_KIND != {k: tuple(v) for k, v in W["meeting_kinds"]["kinds"].items()}:
        bad.append("build_pages.MEET_KIND is not meeting_kinds.json's kinds")
    if BP.MEET_LEGEND != tuple(tuple(x) for x in W["meeting_kinds"]["legend"]):
        bad.append("build_pages.MEET_LEGEND is not meeting_kinds.json's legend")
    if set(BP._SMALL) != set(W["meeting_kinds"]["small"]):
        bad.append("build_pages.kind_title's small words are not meeting_kinds.json's")
    if tuple(B.CHIP_WORDS) != tuple(W["chips"]["chip"]):
        bad.append(f"build_site_v2.CHIP_WORDS is {B.CHIP_WORDS}, not chips.json's "
                   f"{tuple(W['chips']['chip'])}")
    # The session days' closing line (5 November 2026): its tables are
    # closing.json's own, which the live session page reads too.
    import build_session_pages as BSP
    for name, key in (("CLOSING", "sentences"), ("CLOSING_WHO", "who"), ("CLOSING_AFTER", "after"),
                      ("CLOSING_LEFT", "left"), ("NARRATIVE_KEY", "narrative_key"),
                      ("VOTE_SAID", "vote_said"), ("NUANCE_OF", "nuance_of")):
        if getattr(BSP, name) is not W.get("closing", {}).get(key):
            bad.append(f"build_session_pages.{name} is not closing.json's {key}")

    # The browser reads them, and nothing types them again.
    app = _source("src/pages/app.js")
    for want in ("const KIND=WORDBOOK.chips.kind;", "const CHIPCLASS=WORDBOOK.chips.chip;",
                 "const STATUSCATS=Object.keys(WORDBOOK.chips.category);",
                 "const CATCLASS=Object.assign(Object.create(null),WORDBOOK.chips.category);",
                 "const MEET_KIND=WORDBOOK.meeting_kinds.kinds;",
                 "const KIND_SMALL=new Set(WORDBOOK.meeting_kinds.small);"):
        if want not in app:
            bad.append(f"app.js does not read its words from components.js: no {want!r}")
    pats = _word_copies(W)
    srcs = sorted(p for p in Path("src/pages").iterdir()
                  if p.is_file() and p.suffix in (".py", ".js", ".html")) + sorted(Path("src/pages/inline").glob("*.js"))
    copies = [f"{p.name}: {what}" for p in srcs
              for what, pat in pats if pat.search(p.read_text(encoding="utf-8"))]
    if copies:
        bad.append(f"{len(copies)} words typed out again, which src/pages/words/ holds: "
                   + "; ".join(copies[:6]))
    # ...and the patterns would find a copy, were one typed: the tables as
    # they stood in app.js and build_pages.py until 9 October 2026.
    old = ('const MEET_KIND={"public hearing":["Public Hearing","k-hearing"],\n'
           '                 "hearing":["Public Hearing","k-hearing"]};\n'
           'MEET_LEGEND = (("k-hearing", "Public Hearing"),\n               ("k-exec", "Executive Session"))\n'
           '_SMALL = {"a", "an", "and", "at", "by"}\n'
           'const KIND={active:"s-active",law:"s-law",done:"s-done"};\n'
           'const CHIPCLASS={"Became Law":"s-law","Died":"s-done","Interim Study":"s-study",\n'
           '  "Tabled":"s-table","Vetoed":"s-veto","Withdrawn":"s-done"};\n'
           'const STATUSCATS=["In Progress","Passed","Tabled","Interim Study","Died","Withdrawn","Vetoed"];\n'
           'const CATCLASS=Object.assign(Object.create(null),{"In Progress":"s-active",\n'
           '  "Passed":"s-law"});\n'
           'BECAME_LAW, DIED, INTERIM_STUDY, TABLED, VETOED, WITHDRAWN = (\n'
           '    "Became Law", "Died", "Interim Study", "Tabled", "Vetoed", "Withdrawn")\n'
           'MEET_KIND = {"public hearing": ("Public Hearing", "k-hearing")}\n')
    unfound = [what for what, pat in pats
               if what in ("the meeting kind 'public hearing'", "the key's 'Public Hearing'",
                           "the small words of a meeting's title", "the chip 'Tabled'",
                           "the category 'In Progress'", "the kind 'active''s class",
                           "the six chip words", "the Status filter's categories")
               and not pat.search(old)]
    if len([w for w, _p in pats if w in ("the meeting kind 'public hearing'", "the chip 'Tabled'",
                                         "the category 'In Progress'", "the six chip words",
                                         "the Status filter's categories")]) != 5:
        bad.append("the search for copies no longer looks for a meeting kind, a chip, a "
                   "category and the two lists by the names this check tries them by")
    if unfound:
        bad.append("the search for copies misses the old tables: " + ", ".join(unfound))

    # The markers, and nothing typed between them.
    src = _source("src/pages/components.js")
    a, b = src.find(BP.WORDBOOK_START), src.find(BP.WORDBOOK_END)
    if (src.count(BP.WORDBOOK_START), src.count(BP.WORDBOOK_END)) != (1, 1) or not -1 < a < b:
        bad.append(f"components.js does not hold one {BP.WORDBOOK_START} and one {BP.WORDBOOK_END} "
                   "after it")
    elif src[a + len(BP.WORDBOOK_START):b].strip():
        bad.append("components.js in src/pages/ has words typed between its markers, which the "
                   "build writes there from src/pages/words/: "
                   + src[a + len(BP.WORDBOOK_START):b].strip()[:80])

    # with_words: the words in, nothing else moved, in either line ending.
    for nl in ("\n", "\r\n"):
        text = src.replace("\n", nl)
        try:
            got = BP.with_words(text)
        except ValueError as e:
            bad.append(f"with_words refused components.js itself: {e}")
            continue
        block = BP.words_js(nl)
        s = text.index(BP.WORDBOOK_START)
        if got != text[:text.index(nl, s) + len(nl)] + block + text[text.index(BP.WORDBOOK_END):]:
            bad.append(f"with_words did not write the words alone between the markers ({nl!r})")
        if not block.startswith("const WORDBOOK={" + nl) or (nl == "\n" and "\r" in block):
            bad.append(f"with_words wrote {block[:40]!r}, not one const WORDBOOK in the file's line "
                       f"ending ({nl!r})")
    broken = {
        "no START": src.replace(BP.WORDBOOK_START, "// WORDBOOK"),
        "no END": src.replace(BP.WORDBOOK_END, "// WORDBOOK"),
        "START twice": src.replace(BP.WORDBOOK_START, BP.WORDBOOK_START + "\n" + BP.WORDBOOK_START),
        "END twice": src.replace(BP.WORDBOOK_END, BP.WORDBOOK_END + "\n" + BP.WORDBOOK_END),
        "END before START": src.replace(BP.WORDBOOK_START, "@@").replace(BP.WORDBOOK_END, BP.WORDBOOK_START)
                                .replace("@@", BP.WORDBOOK_END),
        "END inside a line": src.replace("\n" + BP.WORDBOOK_END, " " + BP.WORDBOOK_END),
        "START inside a line": src.replace("\n" + BP.WORDBOOK_START, " " + BP.WORDBOOK_START),
    }
    took = []
    for what, text in broken.items():
        try:
            BP.with_words(text)
            took.append(what)
        except ValueError:
            pass
    if took:
        bad.append("with_words wrote the words into a components.js with "
                   + ", ".join(took) + ", where it should stop the build")

    # The build wrote them.
    shared, _base, _ran, _days = _fixture_site_shared()
    built = shared / "site" / "components.js"
    if not built.exists():
        bad.append("the fixture build wrote no site/components.js")
    elif built.read_bytes().decode("utf-8").replace("\r\n", "\n") != BP.published_js(
            "components.js", src).replace("\r\n", "\n"):
        bad.append("the fixture build's site/components.js is not src/pages/components.js with "
                   "the words written between its markers, without its comments "
                   "(build_pages.published_js)")
    assert not bad, " | ".join(bad)
    n = {k: len(v) for k, v in W.items()}
    return "ok", (f"{len(W)} files of words ({', '.join(f'{k} {v}' for k, v in n.items())} "
                  f"entries) read by components.py, build_pages and build_site_v2 and by app.js "
                  f"from components.js; none typed again in {len(srcs)} files of src/pages/; "
                  f"the markers hold, and the build wrote the words between them")


@check("build", "a former member's page takes the seat their last term's bills print over the "
                "record's, the person's correction stands, and the old address is kept for a 301",
       needs=("build_site_v2",))
def _former_seat_from_bills(B2):
    """date_former_seats (5 November 2026): Rebecca Hutchinson's page read
    "Rock 73", in a county the 1992 map numbered to 36, where the bills she
    sponsored in 1999-2000 print Rockingham 8."""
    def row(mid, name, county, dist, chamber="H"):
        return {"id": mid, "name": name, "chamber": chamber, "party": "D", "party_code": "D",
                "county": county, "district": dist, "county_abbr": "", "former": True}
    def ballot(mid, year):
        return {"member_id": mid, "year": str(year), "date": f"3/1/{year}", "body": "H"}
    former = {"376132": row("376132", "Hutchinson, Rebecca", "Rock", "73"),
              "9237": row("9237", "Chase, Wendy", "Strafford", "18"),
              "500": row("500", "Same, Sam", "Hillsborough", "4"),
              "600": row("600", "Taken, Tom", "Merrimack", "2"),
              "601": row("601", "Taken, Tom", "Merrimack", "9"),
              # the county abbreviated, the seat the bills' own: nothing moves
              "700": row("700", "Short, Sue", "Rock", "8"),
              # onto a sitting member's address: not made
              "800": row("800", "Sitting, Sid", "Coos", "1")}
    votes = {k: [ballot(k, 1999)] for k in former}
    printed = {("1999-2000", "376132"): ("H", "Rockingham", "8"),
               ("1999-2000", "9237"): ("H", "Belknap", "5"),       # the person's seat stands
               ("1999-2000", "500"): ("H", "Hillsborough", "4"),   # already the bills'
               ("1999-2000", "600"): ("H", "Merrimack", "9"),      # another page's address
               ("1999-2000", "700"): ("H", "Rockingham", "8"),
               ("1999-2000", "800"): ("H", "Coos", "2")}
    legs = {"1": {"name": "Sitting, Sid", "chamber": "H", "party_code": "D", "county": "Coos",
                  "district": "2", "county_abbr": "Coos"},
            "2": {"county": "Rockingham", "county_abbr": "Rock"}}
    import copy
    got, redated = B2.date_former_seats(copy.deepcopy(former), votes, printed, {"9237"}, legs)
    h = got["376132"]
    assert (h["county"], h["district"], h["county_abbr"]) == ("Rockingham", "8", "Rock") and \
        h.get("moved_from") == ["/legislator/rebecca-hutchinson-rock-73"], h
    assert B2._member_address(h) == "/legislator/rebecca-hutchinson-rock-8", B2._member_address(h)
    for k in ("9237", "500", "600", "700", "800"):
        assert got[k] == former[k], f"{k} changed: {got[k]} from {former[k]}"
    assert set(redated) == {"376132"}, redated
    assert B2.corrected_seats(Path("no-such-file.json")) == set()
    # KEPT FOR GOOD: a recorded address answers though nothing moves the page
    # from it any more, and a move the record lacks is said
    root = Path(tempfile.mkdtemp(prefix="gr-moves-"))
    try:
        rec = root / "moved.json"
        rec.write_text(json.dumps({"/legislator/wendy-chase-belknap-5": "9237"}), encoding="utf-8")
        kept, unrecorded = B2.keep_moved(got, rec)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert kept == 1 and got["9237"]["moved_from"] == ["/legislator/wendy-chase-belknap-5"] and \
        unrecorded == ["/legislator/rebecca-hutchinson-rock-73"], (kept, unrecorded, got["9237"])
    import importlib.util
    spec = importlib.util.spec_from_file_location("record_moves", "src/ops/record_moves.py")
    RM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RM)
    merged = RM.merge({"/a": "1"}, {"/a": "2", "/b": "3"})
    assert merged == {"/a": "1", "/b": "3"}, f"record_moves re-pointed or dropped: {merged}"
    return "ok", ("Hutchinson Rock 73 -> Rockingham 8 with a 301 from the old address; the person's "
                  "seat, a seat already right, an abbreviated county, and moves onto another page's "
                  "or a sitting member's address left alone; a recorded address kept for good")


@check("build", "a former member's label names the seat they held in their last term on record, or no district where that is not known, and their page does not move",
       needs=("build_site_v2", "parse_districts", "state_settings"))
def _former_label_is_the_last_terms_seat(B2, PDIST, ST):
    """last_term_labels (19 November 2026). Carlos E. Gonzalez's page read "Rep. Carlos E.
    Gonzalez (R - Hills 48)": the person's correction gives him the seat the journals print in
    2001-2002, and his last term, 2015-2016, was on the 2012 lines, which number Hillsborough's
    districts to 45. And three corrected members of 2015-2016 (Andrew Christie Jr., Robert H.
    Rowe, John L. Balcom) were labelled with their 1999-2002 seats where their last term's bills
    print another. Held, on made-up members against the district table of the tracked files:
    the last term's bills' one seat over a corrected one; no district where the record's seat is
    no district of the last term's lines, House or Senate; the record's seat kept where it is a
    district of those lines, where the bills print two seats, and before 2013, when no table of
    the lines is on file; and no page address moves. And the build applies it, and the row keeps
    the address it is given."""
    import ast
    import copy
    def row(mid, name, county, dist, chamber="H"):
        return {"id": mid, "name": name, "chamber": chamber, "party": "R", "party_code": "R",
                "county": county, "district": dist, "county_abbr": "Hills" if county == "Hillsborough" else "",
                "former": True}
    def ballots(mid, *years):
        return [{"member_id": mid, "year": str(y), "date": f"3/1/{y}", "body": "H"} for y in years]
    former = {"376341": row("376341", "Gonzalez, Carlos E.", "Hillsborough", "48"),
              "374900": row("374900", "Christie, Andrew, Jr.", "Rockingham", "22"),
              "1": row("1", "Kept, Kay", "Hillsborough", "22"),
              "2": row("2", "Early, Ed", "Hillsborough", "48"),
              "3": row("3", "Two, Tess", "Hillsborough", "14"),
              "4": row("4", "Senator, Sal", "", "30", chamber="S"),
              "5": row("5", "Today, Tim", "Hillsborough", "48")}
    votes = {"376341": ballots("376341", 2001, 2015, 2016), "374900": ballots("374900", 1999, 2015),
             "1": ballots("1", 2017), "2": ballots("2", 2001), "3": ballots("3", 2015),
             "4": ballots("4", 2019), "5": ballots("5", 2025)}
    record = ({("2015-2016", "374900"): ("H", "Rockingham", "37"),
               ("2001-2002", "376341"): ("H", "Hillsborough", "48")}, {("2015-2016", "3")}, {})
    table = PDIST.table(_paths.ROOT, ST.SETTINGS)
    was = {k: B2._member_address(m) for k, m in former.items()}
    got, changed = B2.last_term_labels(copy.deepcopy(former), votes, record, table)

    def label(m):
        return B2.member_labels(m.get("name"), chamber=m.get("chamber"), party=m.get("party_code"),
                                district=m.get("district"), county=m.get("county"),
                                county_abbr=m.get("county_abbr"))["display_full"]
    said = {k: label(m) for k, m in got.items()}
    assert said["376341"] == "Rep. Carlos E. Gonzalez (R)", said["376341"]
    assert said["374900"] == "Rep. Andrew Christie Jr. (R - Rock 37)", said["374900"]
    assert said["4"] == "Sen. Sal Senator (R)" and got["4"]["district"] == "", got["4"]
    for k in ("1", "2", "3"):
        assert got[k] == former[k], f"{k} changed: {got[k]}"
    assert said["5"] == "Rep. Tim Today (R)", "a seat that is no district of today's lines was kept"
    assert set(changed) == {"376341", "374900", "4", "5"} and changed["376341"] == ("Hillsborough 48", "no district"), changed
    assert {k: B2._member_address(m) for k, m in got.items()} == was, "a former member's page moved"
    assert got["376341"]["slug"] == "carlos-e-gonzalez-hills-48" and got["376341"]["county"] == "Hillsborough"
    # The build applies it, after the seats are dated and the addresses kept, and a row keeps its address.
    text = _source(_paths.locate("build_site_v2.py"))
    tree = _parsed(_paths.locate("build_site_v2.py"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n.func.id for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "last_term_labels" in calls and calls.index("keep_moved") < calls.index("last_term_labels") \
        and calls.index("last_term_labels") < calls.index("build_legislators"), "main does not label former members by their last term"
    text = _source(_paths.locate("members.py"))
    tree = _parsed(_paths.locate("members.py"))
    bl = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_legislators")
    assert '"slug": m.get("slug") or member_slug(m, lab)}' in ast.get_source_segment(text, bl), (
        "build_legislators does not keep the address a former member's row is given")
    return "ok", ("Gonzalez's Hills 48 of 2001-2002, no district of 2015-2016's lines, is no district; a corrected "
                  "Rock 22 is the Rock 37 the last term's bills print; a Senate 30 and today's Hills 48, no "
                  "district of their lines, none; a seat of the lines, two printed seats and a term before 2013 "
                  "as they were; no page moves; main applies it before the pages are written")


def _lines_of(EN, ST, house, senate):
    """A made-up district table (entities.district_table's) of the 2012 and 2022 lines: `house`
    {county: districts numbered 1 to n}, `senate` districts 1 to n, a town apiece."""
    era = lambda e: {"house": {(c, k): {"seats": 1, "floterial": False, "towns": [(f"{c} Town {k}", 0)]}
                               for c, n in house.items() for k in range(1, n + 1)},
                     "senate": {k: [(f"Senate Town {e} {k}", 0)] for k in range(1, senate + 1)}}
    return EN.district_table({"2012": era("2012"), "2022": era("2022")}, ST.SETTINGS)


@check("session", "a term's seat is named only where it is a district of the lines the term sat on, "
                  "else the member is named alone; the build reads the district table for it",
       needs=("build_site_v2", "build_session_pages", "entities", "state_settings"))
def _term_seats_of_the_terms_lines(B2, BSP, EN, ST):
    """term_seats and the district table (20 November 2026). Carlos E. Gonzalez's 2015-2016
    session days named him "Rep. Carlos E. Gonzalez (R - Hills 48)": his bills of 2015-2016 print
    no seat, so the seat was his ballots' in his last term, which is the record's one seat for him
    (a correction whose evidence is the 2001-2002 journals), and 2015-2016 sat on the 2012 lines,
    which number Hillsborough's districts to 45. Held, on made-up ballots against a made-up table
    of the 2012 and 2022 lines (Hillsborough 1-45, Grafton 1-18, Senate 1-24): a last term's
    ballot seat and a printed seat that are no district of the term's lines are refused, House and
    Senate, and said; a seat of the lines is kept, in either era; a term before 2013, with no lines
    on file, keeps its seat as before; the ballots map, which links and shows no seat, is as it
    was; the session day names him alone, with the chamber's honorific; and main reads the
    district table once and hands it to term_seats."""
    import ast
    import contextlib
    import io

    def ballot(year, label, member, name, vote="Yea"):
        return {"year": str(year), "body": "H" if label.startswith(("Rep. ", "Gonz", "Kept", "Two")) else "S",
                "vote_number": 1, "member_id": member, "name": name, "party": "R", "label": label,
                "date": f"3/1/{year}", "vote": vote, "bill": "HB1"}
    lines = _lines_of(EN, ST, {"Hillsborough": 45, "Grafton": 18}, 24)
    gonzalez = [ballot(y, "Gonzalez, Carlos E.(R) Hillsborough 48", "376341", "Gonzalez, Carlos E.")
                for y in (2001, 2015, 2016)]
    kept = [ballot(y, "Kept, Kay(R) Hillsborough 22", "1", "Kept, Kay") for y in (2015, 2017)]
    sen = [ballot(2015, "Sen. Sal Senator (R - SD30)", "4", "Senator, Sal"),
           ballot(2016, "Sen. Sal Senator (R - SD30)", "4", "Senator, Sal")]
    two = [ballot(2015, "Two, Tess(R) Grafton 5", "3", "Two, Tess"),
           ballot(2023, "Two, Tess(R) Grafton 5", "3", "Two, Tess")]
    votes = {"376341": gonzalez, "1": kept, "4": sen, "3": two}
    one = {("2001-2002", "376341"): ("H", "Hillsborough", "48"),
           # printed seats: one of the lines, one that is none of 2015-2016's
           ("2015-2016", "3"): ("H", "Grafton", "5"),
           ("2015-2016", "1"): ("H", "Hillsborough", "47")}
    refused = []
    seats = B2.term_seats(votes, record=(one, set(), {}), lines=lines, refused=refused)
    got = {(t, m): lab for t, ms in seats.items() for m, lab in ms.items()}
    want = {("2001-2002", "376341"): "Rep. Carlos E. Gonzalez (R - Hills 48)",
            ("2017-2018", "1"): "Rep. Kay Kept (R - Hills 22)",
            ("2015-2016", "3"): "Rep. Tess Two (R - Graf 5)",
            ("2023-2024", "3"): "Rep. Tess Two (R - Graf 5)"}
    assert got == want, f"term_seats gives {got}, not {want}"
    assert sorted(refused) == [("2015-2016", "1", "Rep. Kay Kept (R - Hills 47)"),
                               ("2015-2016", "376341", "Rep. Carlos E. Gonzalez (R - Hills 48)"),
                               ("2015-2016", "4", "Sen. Sal Senator (R - SD30)")], (
        f"the seats refused are said as {refused}")
    # With no lines on file the rule is the old one: every seat kept, the ballots map unchanged.
    balls_a, balls_b = {}, {}
    old = B2.term_seats(votes, record=(one, set(), {}), lines=([], []), ballots=balls_b)
    B2.term_seats(votes, record=(one, set(), {}), lines=lines, ballots=balls_a)
    assert old["2015-2016"]["376341"] == "Rep. Carlos E. Gonzalez (R - Hills 48)" and balls_a == balls_b, (
        "with no lines on file a seat was refused, or the ballots map moved with the lines")
    assert B2.seat_of_the_lines("2015-2016", "Rep. A B (D - Hills 45)", EN.district_index({"district": lines[0]}),
                                {(d["kind"], d["era"]) for d in lines[0]})
    # The session day names him alone, with the chamber's honorific.
    root = Path(tempfile.mkdtemp(prefix="gr-lines-"))
    try:
        (root / "legislators.json").write_text("[]", encoding="utf-8")
        (root / "former.json").write_text(json.dumps([
            {"id": "376341", "slug": "carlos-e-gonzalez-hills-48", "name": "Gonzalez, Carlos E.",
             "chamber": "H", "party": "R", "display_full": "Rep. Carlos E. Gonzalez (R - Hills 48)"}]),
            encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            m = BSP.Members(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    m.seats, m.current = seats, "2025-2026"
    m.term = "2015-2016"
    day = m.label("carlos-e-gonzalez-hills-48", "H")
    assert day == "Rep. Carlos E. Gonzalez", f"his 2015-2016 days name him {day!r}"
    m.term = "2001-2002"
    assert m.label("carlos-e-gonzalez-hills-48", "H") == "Rep. Carlos E. Gonzalez (R - Hills 48)"
    # main reads the table once, for the former members' labels and the terms' seats.
    tree = _parsed(_paths.locate("build_site_v2.py"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "term_seats"]
    assert calls and all(any(k.arg == "lines" and isinstance(k.value, ast.Name) and k.value.id == "district_lines"
                             for k in c.keywords) for c in calls), "main's term_seats is not given the district table"
    tl = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == "last_term_labels"]
    assert tl and all(isinstance(a, ast.Name) and a.id == "district_lines" for a in tl[0].args[3:4]), (
        "the former members' labels and the terms' seats read the district table apart")
    return "ok", ("Gonzalez's Hills 48 and a Senate 30 in 2015-2016, no districts of the 2012 lines, refused and "
                  "said, and his days name him alone; a printed Hills 47 refused; seats of the lines in both eras "
                  "and 2001-2002's kept; with no lines on file the old rule; the ballots map unmoved; main hands "
                  "term_seats the district table")


@check("data", "every seat the last build names a member by on a term's session days is a district of the lines that term sat on",
       needs=("build_site_v2", "parse_districts", "state_settings"))
def _term_seats_built_of_their_lines(B2, PDIST, ST):
    """data/floor_record.json's seats (term_seats, as the build wrote them) against the district
    table read from the files here: each seat of a term the table holds the lines of (2013-2014
    on) names one of its districts. Against the record, so on the night it warns (RECORD_CHECKS):
    a seat outside its term's lines is the record's (a correction or a ballot's undated seat) or
    the table's, and the site goes on. Measured on 20 November 2026 against the build of 9
    November: 2,869 seats of 2013-2026, one not of its lines (Carlos E. Gonzalez, Hills 48 in
    2015-2016); 2,810 of 1999-2012, with no lines on file."""
    f = Path("data") / "floor_record.json"
    if not f.is_file():
        return "skip", "no data/floor_record.json here: no build has run"
    seats = json.loads(f.read_text(encoding="utf-8")).get("seats") or {}
    said = []
    lines = PDIST.table(".", ST.SETTINGS, said)
    import entities as EN
    index = EN.district_index({"district": lines[0]})
    held = {(d["kind"], d.get("era")) for d in lines[0]}
    if not held:
        return "skip", "no district table here: " + "; ".join(said or ["records/districts is not here"])
    bad, checked, open_ = [], 0, 0
    for term, ms in sorted(seats.items()):
        era = EN.era_of(term)
        for mid, lab in sorted(ms.items()):
            if era is None or not any(e == era for _k, e in held):
                open_ += 1
                continue
            checked += 1
            if not B2.seat_of_the_lines(term, lab, index, held):
                bad.append(f"{lab} in {term}")
    assert not bad, (f"{len(bad)} seat(s) on the session days name no district of their term's lines, e.g. "
                     + "; ".join(bad[:5]) + ": rebuild, or see where the seat comes from (term_seats)")
    return "ok", (f"{checked:,} seats of terms whose lines are on file, each a district of them; {open_:,} "
                  "of terms before every era on file" + (f" ({'; '.join(said)})" if said else ""))


@check("build", "a former member's last vote is the last of their last term, whatever day the "
                "clerk wrote: a mover's one page is the chamber they sat in last, their seat their "
                "last term's, a recorded address follows them onto a joined page, a joined "
                "number's data answers from the page's, and a joined page's description, "
                "directory line and search entry name each chamber with its years",
       needs=("build_site_v2", "build_legislator_pages", "build_pages", "build_indexes"))
def _movers_by_term(B2, BL, BP, BI):
    """THE DEEP WALK OF 6 NOVEMBER 2026, on dry run 181's preview. Roll call
    1999-S-109 (CACR 17) is dated 22 October 2009 between two of 22 October
    1999: the only ballot of 2,303,047 dated outside its term. Each former
    member's last vote was taken by its day, so it was the last vote of every
    senator of 1999 who cast it.

    Frederick King (Senate 1999-2000, House 2003-2008) and Leo Fraser
    (Senate 1999-2000, House 2001-2004) were kept as the Senate's page when
    their two numbers were joined (former_movers), though both sat in the
    House after: their live House addresses answered with a 301 to "Former
    Sen. Frederick King (R - SD1)". Carl Johnson's seat was taken from
    1999-2000's bills, SD3, not from 2005-2006's, SD2, which print him 118
    times (date_former_seats), and his right address answered with a 301 to
    the wrong one. And the 34 joined pages' search descriptions put the whole
    record in the page's chamber: "Sen. Jeb Bradley (R - SD3) served in the
    New Hampshire Senate, 1999 to 2024", of a senator who sat in the House in
    1999-2002.

    So a member's last vote is the last of the term the roll call belongs
    to, by its session year (service_order), and then by its day. The
    addresses the night recorded for the Senate numbers
    (generated/moved_addresses.json, which only grows) follow those numbers
    onto the page that carries their record now (keep_moved's links). Each
    chamber of a joined page is named with its years in its description, as
    the page's own "Votes on record" line names them."""
    def ballot(year, date, body):
        return {"year": str(year), "date": date, "body": body,
                "label": "", "name": "King, Frederick", "party": "R"}
    # Frederick King: the Senate number with the misdated roll call among its
    # 1999 ballots, and the House number of 2003-2008.
    king = {"205005": [ballot(1999, "2/11/1999", "S"), ballot(1999, "10/22/1999", "S"),
                       ballot(1999, "10/22/2009", "S")],
            "376486": [ballot(2003, "3/1/2003", "H"), ballot(2008, "6/4/2008", "H")]}
    got = B2.former_movers(None, {}, {}, {}, king, confirmed=[["376486", "205005"]])
    assert got == {"376486": ["205005"]}, (
        f"former_movers kept {got}: the misdated 1999 Senate ballot outranked 2008's House votes")
    # As the day alone would have it, for the record: the Senate page.
    by_day = max(("205005", "376486"), key=lambda i: max(B2.vote_date(v["date"]) for v in king[i]))
    assert by_day == "205005", "the case no longer tells the term from the day"
    fr = B2.former_roster({}, king, {"376486": ["205005"]}, {}, "2025-2026")
    k = fr["376486"]
    assert k["chamber"] == "H" and k["served"]["first"] == "2/11/1999" and \
        k["served"]["last"] == "6/4/2008", f"King's joined page: {k['chamber']}, {k['served']}"
    assert {"1999-2000", "2007-2008"} <= set(k["served"]["terms"]), k["served"]["terms"]
    # One number, no join: the misdated ballot names neither the party nor
    # the end of a record that runs on to 2004.
    one_no = {"205020": [dict(ballot(1999, "10/22/2009", "S"), party="D", name="Turn, Tess"),
                         dict(ballot(2003, "6/1/2004", "S"), party="R", name="Turn, Tess")]}
    t = B2.former_roster({}, one_no, {}, {}, "2025-2026")["205020"]
    assert t["party"] == "R" and t["served"]["last"] == "6/1/2004" and \
        t["served"]["terms"] == ["1999-2000", "2003-2004"], (
        f"the misdated ballot took the party or the last day: {t['party']}, {t['served']}")
    # Carl Johnson: one number, the Senate's, SD3 in 1999-2002 and SD2 after;
    # the record's seat is SD2, as 2005-2006's bills print it.
    cj = {"205015": [ballot(1999, "10/22/2009", "S"), ballot(2001, "3/1/2001", "S"),
                     ballot(2005, "5/4/2006", "S")]}
    row = {"id": "205015", "name": "Johnson, Carl", "chamber": "S", "party": "R",
           "party_code": "R", "county": "", "district": "2", "county_abbr": "", "former": True}
    printed = {("1999-2000", "205015"): ("S", "", "3"), ("2001-2002", "205015"): ("S", "", "3"),
               ("2005-2006", "205015"): ("S", "", "2")}
    import copy
    seats, redated = B2.date_former_seats({"205015": copy.deepcopy(row)}, cj, printed, set(), {})
    assert not redated and seats["205015"]["district"] == "2" and \
        not seats["205015"].get("moved_from"), (
        f"Carl Johnson was moved by 1999-2000's bills: {seats['205015']}, {redated}")
    # The address the night recorded for King's Senate number is his House
    # page's own now: nothing to add, and nothing said. One recorded for a
    # joined number whose page has another address is answered from it.
    import contextlib
    import io
    page = dict(k, id="376486", name="King, Frederick", county="Coos", district="1",
                county_abbr="Coos", slug="frederick-king-coos-1")
    former = {"376486": page}
    root = Path(tempfile.mkdtemp(prefix="gr-moves-"))
    try:
        rec = root / "moved.json"
        rec.write_text(json.dumps({"/legislator/frederick-king-coos-1": "205005",
                                   "/legislator/frederick-king-sd-9": "205005"}), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            kept, unrecorded = B2.keep_moved(former, rec, links={"376486": ["205005"]})
        said = out.getvalue()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            B2.keep_moved({"376486": dict(page, moved_from=[])}, rec)
        unjoined = out.getvalue()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert B2._member_address(page) == "/legislator/frederick-king-coos-1", B2._member_address(page)
    assert kept == 1 and page.get("moved_from") == ["/legislator/frederick-king-sd-9"] and \
        "WARNING" not in said, (kept, page.get("moved_from"), said)
    assert "205005, who has no former page now" in unjoined, (
        "the case no longer shows a recorded number lost without the joins")
    src = _source(_paths.locate("build_site_v2.py"))
    assert "keep_moved(former, links=links,\n" in src and \
        "sitting={_member_address(m) for m in legs.values()" in src, (
        "build_site_v2 no longer hands keep_moved the joins and the sitting members' addresses: a "
        "recorded address of a joined number would stop answering, or a live page's would be "
        "answered with a 301")
    # A pair joined and then parted: each page's address recorded for the
    # other's number. Neither live page answers the other's address with a
    # 301, nor a sitting member's; both said.
    sen = dict(page, id="205005", chamber="S", county="", district="1", county_abbr="",
               slug="frederick-king-sd-1", moved_from=[])
    house = dict(page, id="376486", moved_from=[])
    root = Path(tempfile.mkdtemp(prefix="gr-moves-"))
    try:
        rec = root / "moved.json"
        rec.write_text(json.dumps({"/legislator/frederick-king-coos-1": "205005",
                                   "/legislator/frederick-king-sd-1": "376486",
                                   "/legislator/seth-king-coos-1": "376486"}), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            crossed, _ = B2.keep_moved({"205005": sen, "376486": house}, rec, links={},
                                       sitting={"/legislator/seth-king-coos-1"})
        said = out.getvalue()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert crossed == 0 and sen["moved_from"] == [] and house["moved_from"] == [] and \
        said.count("is the address of another page now") == 3, (
        f"a live page's address answered with a 301: {crossed}, {sen['moved_from']}, "
        f"{house['moved_from']}, {said!r}")
    # Each chamber of a joined page named with its years; one chamber's page
    # and a sitting member's as they were.
    m = {"former": True, "display_full": "Sen. Jeb Bradley (R - SD3)", "chamber": "S",
         "served": {"first": "3/1/1999", "last": "6/1/2024"}}
    two = {"service": [{"chamber": "H", "spans": [[1999, 2002]]},
                       {"chamber": "S", "spans": [[2009, 2024]]}]}
    d = BL.describe(m, two)
    assert d.startswith("Sen. Jeb Bradley (R - SD3) served in the New Hampshire House of "
                        "Representatives, 1999 to 2002, and Senate, 2009 to 2024. "), d
    split = {"service": [{"chamber": "H", "spans": [[1999, 2000], [2003, 2008]]},
                         {"chamber": "S", "spans": [[2001, 2002]]}]}
    assert "House of Representatives, 1999 to 2000 and 2003 to 2008, and Senate, 2001 to 2002." \
        in BL.describe(dict(m, chamber="H"), split), BL.describe(dict(m, chamber="H"), split)
    three = {"service": [{"chamber": "H", "spans": [[1999, 2002], [2009, 2014], [2017, 2018]]},
                         {"chamber": "S", "spans": [[2003, 2004]]}]}
    assert "House of Representatives, 1999 to 2002, 2009 to 2014 and 2017 to 2018, and Senate, " \
        "2003 to 2004." in BL.describe(dict(m, chamber="H"), three), \
        BL.describe(dict(m, chamber="H"), three)
    one = {"service": [{"chamber": "S", "spans": [[2009, 2024]]}]}
    for r in (one, {}, None):
        assert BL.describe(m, r) == BL.describe(m), (r, BL.describe(m, r))
    assert "served in the New Hampshire Senate, 1999 to 2024." in BL.describe(m), BL.describe(m)
    sitting = {"display_full": "Sen. Cindy Rosenwald (D - SD13)", "chamber": "S", "towns": ["Nashua"]}
    assert BL.describe(sitting, two) == BL.describe(sitting), BL.describe(sitting, two)
    src = _source(_paths.locate("build_legislator_pages.py"))
    assert "description=describe(m, rec)" in src, (
        "the member pages no longer hand describe their own record: a joined page's description "
        "names one chamber")
    # The directory's line and the site search's entry: the seat with its own
    # chamber's years, then the other chamber's; one chamber's as before.
    jeb = {"id": "36", "slug": "jeb-bradley-sd-3", "name": "Bradley, Jeb", "chamber": "S",
           "party": "R", "district_label": "SD3", "display_plain": "Sen. Jeb Bradley",
           "served": {"first": "3/1/1999", "last": "6/1/2024",
                      "terms": ["1999-2000", "2001-2002", "2009-2010", "2023-2024"]},
           "member_ids": ["36", "374827"], **two}
    assert BI.chamber_years(jeb, "SD3") == ["SD3", "Senate 2009–2024", "House 1999–2002"], \
        BI.chamber_years(jeb, "SD3")
    # The page's own chamber first, whichever the record lists first; every
    # span of a chamber, and no seat where none is known.
    rep = dict(jeb, chamber="H", service=three["service"])
    assert BI.chamber_years(rep, "Rock 6") == [
        "Rock 6", "House 1999–2002, 2009–2014, 2017–2018", "Senate 2003–2004"], \
        BI.chamber_years(rep, "Rock 6")
    assert BI.chamber_years(dict(rep, service=three["service"][::-1]), "") == [
        "House 1999–2002, 2009–2014, 2017–2018", "Senate 2003–2004"], \
        BI.chamber_years(dict(rep, service=three["service"][::-1]), "")
    assert BI.chamber_years(dict(jeb, service=one["service"]), "SD3") is None
    assert BI.chamber_years({k: v for k, v in jeb.items() if k != "service"}, "SD3") is None
    root = Path(tempfile.mkdtemp(prefix="gr-movers-"))
    try:
        site = root / "site"
        (site / "legislator").mkdir(parents=True)
        (site / "legislator" / "jeb-bradley-sd-3.html").write_text("x", encoding="utf-8")
        alone = {"id": "41", "slug": "nancy-alone-sd-24", "name": "Alone, Nancy", "chamber": "S",
                 "party": "R", "district_label": "SD24", "display_plain": "Sen. Nancy Alone",
                 "served": {"terms": ["2011-2012", "2015-2016"], "last": "6/1/2016"}}
        (site / "legislator" / "nancy-alone-sd-24.html").write_text("x", encoding="utf-8")
        (site / "former.json").write_text(json.dumps([jeb, alone]), encoding="utf-8")
        BI.former_page(site, "https://x", [])
        page = next(site.rglob("former-legislators.html")).read_text(encoding="utf-8")
        rules = BP.moved_members(site)
        found = {r[3].rsplit("/", 1)[-1].removesuffix(".html"): r[2]
                 for r in BI.find_index(site, [], {}) if r and r[0] == "former"}
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "R, SD3 · Senate 2009–2024 · House 1999–2002</span>" in page and \
        "R, SD24, 2011–2016</span>" in page, re.findall(r'class="dirstatus">([^<]*)<', page)
    # A PERSON WHO SAT IN BOTH IS UNDER EACH (the deep walk of dry run 183):
    # Jeb Bradley in the Senate list and in the House's, with the House's
    # title there and the House's years first, and no party or seat, which
    # are the page's chamber's (the review of 7 November 2026: "Sen. Leo
    # Fraser R, Merr 37"); each chamber's count counts everyone who sat in it.
    lists = {h: re.findall(r'<a href="[^"]*">([^<]*)</a> <span class="dirstatus">([^<]*)<', ul)
             for h, ul in re.findall(r'<h2 id="(s|h)">.*?</h2><ul class="dirpeople">(.*?)</ul>',
                                     page, re.S)}
    assert lists == {"s": [("Sen. Nancy Alone", "R, SD24, 2011–2016"),
                           ("Sen. Jeb Bradley", "R, SD3 · Senate 2009–2024 · House 1999–2002")],
                     "h": [("Rep. Jeb Bradley", "House 1999–2002 · Senate 2009–2024")]}, (
        f"a person who sat in both chambers is not under each in the directory, as that "
        f"chamber's: {lists}")
    assert "2 former senators and 1 former representative on record" in page and \
        "The one who sat in both chambers is under each." in page, (
        "the directory's counts do not count everyone who sat in each chamber: "
        + (re.search(r'<p class="src">([^<]*)<', page) or [None, page[:200]])[1])
    assert rules == "/legislators/374827.json /legislators/36.json 301\n", (
        f"a joined number's data has no 301 to the page's: moved_members wrote {rules!r}")
    # The site search groups former members by the chamber their line starts
    # with: a joined row's starts with its page's, as a one-chamber row's does.
    assert found.get("jeb-bradley-sd-3") == "Senate · SD3 · 2009–2024 · House 1999–2002" \
        and found.get("nancy-alone-sd-24") == "Senate · SD24 · 2011–2016", found
    import inline_js as IJ
    # The builder and its scripts, in inline/ since 20 November 2026.
    grouped = _source(_paths.locate("build_pages.py")) + "".join(_source(p) for n, p in IJ.files().items() if n.split(".")[0] == "build_pages")
    assert 'k:r=>r[0]==="former"&&/^Senate/.test(r[2])' in grouped and \
        'k:r=>r[0]==="former"&&/^House/.test(r[2])' in grouped, (
        "the site search no longer groups former members by the chamber their line starts with; "
        "say here what it groups by now")
    src = _source(_paths.locate("members.py"))
    assert 'row["service"] = ML.service(mv)' in src, (
        "former.json's rows no longer carry each chamber's years for a joined page")
    assert re.search(r"mv = sorted\(\[v for x in \(mid, \*joined\)[^\n]*\n\s*key=service_order, "
                     r"reverse=True\)", src), (
        "a member's vote list is no longer newest by term: 1999-S-109, dated 2009, would head the "
        "votes of every senator of 1999 who cast it")
    return "ok", ("a misdated 1999 Senate ballot no longer makes King's page the Senate's or moves "
                  "Carl Johnson to SD3; a recorded address follows its number onto the joined page "
                  "without a warning; a joined number's JSON answers with the page's; a joined "
                  "page's description and directory line name the House and the Senate with "
                  "their years; the directory lists a joined person under each chamber, and "
                  "the site search under its page's")


@check("session", "the seat of a term is the one its bills print, else the ballots' in the "
                  "member's last term only, else none: never a later record's seat on an "
                  "earlier term", needs=("build_site_v2", "build_session_pages"))
def _term_seats_printed_first(B2, BSP):
    """term_seats' order (5 November 2026). A ballot's label is not dated: a
    former member's is built from one record of the seat they last held, so
    Shannon Chandley read "Hills 22" on her 2009-2010 ballots, the seat she
    took in 2016, where the bills she sponsored in 2010 print "Hills 6". The
    seat of a term is the one its bills print; else, in the member's last
    term only, the one their ballots give; else none -- never a later
    record's seat on an earlier term (the manager's condition: no source, no
    seat). And who presided is named the same way."""
    def ballot(year, label, member, name, vote="Yea"):
        return {"year": str(year), "body": "H", "vote_number": 1, "member_id": member,
                "name": name, "party": "D", "label": label, "date": f"3/1/{year}",
                "vote": vote, "bill": "HB1"}
    chandley = [ballot(y, "Chandley, Shannon(D) Hillsborough 22", "568", "Chandley, Shannon")
                for y in (2009, 2010, 2013, 2017)]
    ham = [ballot(y, "Ham, Bonnie(D) Grafton 5", "7439", "Ham, Bonnie") for y in (2011, 2015)]
    # the last term's record refused where that term's bills say otherwise:
    # an unplaced sponsor line of the surname at another seat, or two seats
    mccarty = [ballot(1999, "McCarty, Winston(D) Merrimack 10", "375883", "McCarty, Winston")]
    king = [ballot(1999, "King, John(D) Coos 1", "500", "King, John")]
    one = {("2009-2010", "568"): ("H", "Hillsborough", "6"),
           ("2013-2014", "568"): ("H", "Hillsborough", "22"),
           # a seat in the other chamber is not this number's
           ("2011-2012", "7439"): ("S", "", "5")}
    two = {("1999-2000", "500")}
    named = {("1999-2000", "H", "mccarty"): {("Hillsborough", "38")},
             ("2017-2018", "H", "chandley"): {("Hillsborough", "22")}}
    votes = {"568": chandley, "7439": ham, "375883": mccarty, "500": king}
    seats = B2.term_seats(votes, record=(one, two, named))
    got = {(t, m): lab for t, ms in seats.items() for m, lab in ms.items()}
    want = {("2009-2010", "568"): "Rep. Shannon Chandley (D - Hills 6)",
            ("2013-2014", "568"): "Rep. Shannon Chandley (D - Hills 22)",
            ("2017-2018", "568"): "Rep. Shannon Chandley (D - Hills 22)",
            ("2015-2016", "7439"): "Rep. Bonnie Ham (D - Graf 5)"}
    assert got == want, f"term_seats gives {got}, not {want}"
    assert B2.printed_seats(Path("no-such-file.json")) == {}, "no file, no printed seats"
    # printed_record off a text_sponsors.json: a line nobody was placed on
    # doubts the member of the surname; a namesake's placed seat does not,
    # nor that seat printed again unplaced; "Barnes Jr." is a Barnes
    def rec(name, county, dist, mid=""):
        return {"member_id": mid, "name": name, "chamber": "H", "county": county, "district": dist}
    root = Path(tempfile.mkdtemp(prefix="gr-printed-"))
    try:
        (root / "t.json").write_text(json.dumps({"1999-2000": {
            "HB1": [rec("McCarty", "Hillsborough", "38"), rec("Flanders", "Rockingham", "18", "371948")],
            "HB2": [rec("Flanders", "Rockingham", "18"), rec("John Barnes Jr.", "Belknap", "4")]}}),
            encoding="utf-8")
        one2, two2, named2 = B2.printed_record(root / "t.json")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert named2 == {("1999-2000", "H", "mccarty"): {("Hillsborough", "38")},
                      ("1999-2000", "H", "barnes"): {("Belknap", "4")}} and \
        one2 == {("1999-2000", "371948"): ("H", "Rockingham", "18")}, (one2, named2)
    flanders = [ballot(1999, "Flanders, David(D) Rockingham 20", "376001", "Flanders, David")]
    kept = B2.term_seats({"376001": flanders, "375883": mccarty}, record=(one2, two2, named2))
    assert kept == {"1999-2000": {"376001": "Rep. David Flanders (D - Rock 20)"}}, (
        f"a namesake's seat refused a member's own, or McCarty's doubted one was kept: {kept}")
    # who presided: the term's seat, else the name alone -- never a later
    # record's seat, never the party letter alone
    chair = [dict(ballot(y, "Ham, Bonnie(D) Grafton 5", "7439", "Ham, Bonnie", "Presiding"),
                  vote_number=9) for y in (2011, 2015)]
    root = Path(tempfile.mkdtemp(prefix="gr-seats-"))
    try:
        f = B2.write_floor_record(root, {"7439": chair}, {}, record=({}, set(), {}))
        # as the session-day step reads it: floor_record() hands on the keys
        # it names, and once left the ballots behind (5 November 2026)
        rec = BSP.floor_record(f)
        pres = rec["presiding"]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    labs = sorted(lab for rows in pres.values() for _mid, lab in rows)
    assert labs == ["Rep. Bonnie Ham", "Rep. Bonnie Ham (D - Graf 5)"], (
        f"who presided reads {labs}: 2011's must be the name alone, 2015's the last term's seat")
    # who voted, for linking a name, is every term's, whatever seat is shown
    assert (rec.get("ballots") or {}).get("2011-2012", {}).get("7439") == "Rep. Bonnie Ham (D - Graf 5)" \
        and "2011-2012" not in rec["seats"], (
        f"the floor record's ballots {rec.get('ballots')} and seats {rec['seats']}: 2011-2012's "
        "voter is linked by her ballots and shown with no seat")
    return "ok", ("Chandley Hills 6 in 2009-2010 as printed, Hills 22 where printed and in her last "
                  "term; Ham's 2011-2012 seatless, as chair too; McCarty's and King's last-term "
                  "records refused where their term's bills say otherwise")


@check("build", "a House report is dated by its calendar's filename however the clerk spaced it",
       needs=("build_site_v2",))
def _cal_date_spaced(SV):
    """The walk of 31 October 2026: every interim study report House
    Calendar 39 of 2018 printed had no date on its card, because the
    calendar's filename has two spaces before the year
    ("November%2009%20%202018") and CAL_DATE allowed one. Held on the shapes
    the addresses on file take: escaped, doubled, and typed as spaces."""
    base = "https://gc.nh.gov/house/calendars_journals/viewer.aspx?fileName=calendars%5C"
    cases = {base + "2026%5CNo10%20March%206%202026.pdf": "2026-03-06",
             base + "2018%5CNo%2039%20November%2009%20%202018.pdf": "2018-11-09",
             base + "2026%5CNo10 March 6 2026.pdf": "2026-03-06",
             base + "2018%5CNo%2039.pdf": ""}
    wrong = {u.rsplit("%5C", 1)[1]: SV._cal_date(u) for u, want in cases.items() if SV._cal_date(u) != want}
    assert not wrong, f"a calendar's filename gives the wrong date: {wrong}"
    return "ok", f"{len(cases)} calendar filenames, each dated as printed or not at all"


@check("build", "a start a weak marker found is drawn approximate, on the bill page, the floor "
                "and the committee page, and one the chair stated is not", needs=("build_site_v2",))
def _weak_marker_approximate(B):
    """CLAUDE.md, Timestamps: "a stated boundary is shown plainly, and an
    inferred one carries one word, approximate." segment_markers calls a
    marker weak where the phrase names no proceeding or is not the chair
    framing an opening -- the bill's title read and then a motion, the
    sponsor welcomed (the timestamp study of 23 October 2026) -- and says so
    in its "how". The station took any marker as stated, so a weak one was
    drawn as the chair's own opening (found by that study: said_how was never
    read). Held on both station builders with a stated and a weak marker, on
    the committee page's line, and on app.js's words for each."""
    p = {"bill": "HB1", "body": "H", "committee": "Judiciary", "proceeding": "public hearing",
         "sched_date": "2026-02-03", "sched_time": "10:00", "venue": "LOB 206",
         "video_id": "VIDW", "candidate_ids": ""}
    f = {"date": "2026-02-12", "body": "H", "video_id": "VIDX", "motions": [], "tallies": [],
         "kind": "floor debate", "debate_end": None, "window_start": 0.0, "precise": False,
         "whole_video": False, "title": "", "time": "", "venue": ""}
    for how, stated in (("open the hearing on", True),
                        ("title read, then the sponsor welcomed (weak marker)", False)):
        m = {"VIDW": {"HB1": [{"start": 600.0, "end": 900.0, "how": how,
                                "what": "public hearing" if stated else ""}]}}
        st = B.station_for_proceeding(p, "HB1", {}, m)
        assert st["start"] == 600.0 and st["start_stated"] is stated, (
            f"a committee start found by {how!r} is drawn start_stated={st.get('start_stated')}")
        m = {"VIDX": {"HB1002": [{"start": 1200.0, "end": 1500.0, "what": "floor debate",
                                  "how": how}]}}
        st = B.station_for_floor(f, "HB1002", m)
        assert st["start"] == 1200.0 and st["start_stated"] is stated, (
            f"a floor start found by {how!r} is drawn start_stated={st.get('start_stated')}")
    app = _source(_paths.locate("src/pages/app.js"))
    for need, why in (('h.approx=!s.start_stated', "the bill page's player"),
                      # "approximate", one word, on a floor card too since
                      # 25 October 2026 (S2), where it said "about where the
                      # clerk takes it up".
                      ('const floorApprox=s=>s.debate_start==null||s.start_stated===false;',
                       "the floor player"),
                      ('&&!i.inferred', "the committee page's line")):
        assert need in app, f"app.js: {why} no longer says an inferred start is one ({need})"
    cm = _source(_paths.locate("src/pages/build_committees.py"))
    assert '{"inferred": True}' in cm and 'st.get("start_stated") is False' in cm, (
        "build_committees no longer carries a weak marker's inference to the committee page")
    return "ok", ("a stated opening drawn plainly and a weak marker's start drawn approximate, "
                  "on a committee sitting and on the floor; the committee page and the floor "
                  "player say so too")


@check("build", "build_version_links numbers each amendment from its own text and names every statute a "
                "bill's texts cite, writes the same again on a second run, and build_all runs it after "
                "build_bill_versions", needs=("build_version_links",))
def _version_links_step(VL):
    """The Bill Text tab's two needs from the version indexes (8 November
    2026): an amendment's number, to find the docket's word on it, and the
    statutes the texts cite, to link them. On a bill of two versions and
    three amendments: the number is the first of its shape in the text as
    printed (a committee of conference's keeps its case), none where the text
    prints none; a citation of a statute becomes a link and a session law
    ("RSA 2025, 141:1") does not; the index's other fields are untouched; a
    second pass changes nothing; and the step stands after build_bill_versions
    in build_all, which writes the files it merges into."""
    root = Path(tempfile.mkdtemp())
    try:
        f = root / "versions" / "2026"
        f.mkdir(parents=True)
        (f / "HB9.0.txt").write_text("Amend RSA 91-A:2, II by adding", encoding="utf-8")
        (f / "HB9.1.txt").write_text("and RSA 2025, 141:1 and RSA 999", encoding="utf-8")
        (f / "HB9.a0.txt").write_text("March 3, 2026 2026-0695h 11/08 Amendment to HB 9", encoding="utf-8")
        (f / "HB9.a1.txt").write_text("June 2, 2026 2026-2109-CofC 08/07 Committee of Conference Report",
                                      encoding="utf-8")
        (f / "HB9.a2.txt").write_text("An amendment that prints no number", encoding="utf-8")
        old = {"bill": "HB9", "year": "2026",
               "versions": [{"title": "A"}, {"title": "B"}],
               "amendments": [{"date": "d", "chars": 1, "text_url": f"/versions/2026/HB9.a{j}.txt"}
                              for j in range(3)], "steps": []}
        new = VL.linked(old, f, "HB9")
        nums = [a.get("num") for a in new["amendments"]]
        assert nums == ["2026-0695h", "2026-2109-CofC", None], f"the numbers read from the texts: {nums}"
        cites = new.get("rsa") or {}
        assert "RSA 91-A:2" in cites and cites["RSA 91-A:2"].endswith(("#s2", "-2.htm")), f"the citations: {cites}"
        assert not any("2025" in k for k in cites), f"a session law was linked as a statute: {cites}"
        assert new["versions"] == old["versions"] and new["steps"] == [] and new["bill"] == "HB9", (
            "a field this step does not own changed")
        assert VL.linked(new, f, "HB9") == new, "a second pass changed the index"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    steps = [s for s in re.findall(r'\["(build_bill_versions\.py|build_version_links\.py)"',
                                   _source("build_all.py"))]
    assert steps == ["build_bill_versions.py", "build_version_links.py"], (
        f"build_all does not run build_version_links straight after build_bill_versions: {steps}")
    return "ok", ("amendments numbered from their own text, statutes cited named and linked, a second run "
                  "writes nothing, and the step follows build_bill_versions")


@check("frontend", "the Speaker's own page says he is Speaker", needs=("build_site_v2",))
def _speaker_page_says_so(B):
    """Rep. Sherman Packard's page listed House Rules and his presiding
    counts, and the seating chart labels the Speaker's chair, while nothing
    on his page named the office (the survey of 7 October 2026). The member
    the roster seats in the Speaker's chair, seat 6002 on the rostrum, carries
    "Speaker of the House" in his own file, and his page's line under his
    name says it where it said "House of Representatives". A member who has
    left, a senator, and a member of the floor carry no office."""
    speaker = {"id": "425", "name": "Packard, Sherman", "chamber": "H", "seat": "6002",
               "district": "16", "county": "Rockingham",
               "display_full": "Rep. Sherman Packard (R - Rock 16)", "towns": ["Londonderry"]}
    assert B.member_office(speaker) == "Speaker of the House", B.member_office(speaker)
    for other in ({**speaker, "former": True}, {**speaker, "seat": "1002"},
                  {**speaker, "chamber": "S", "seat": ""}):
        assert B.member_office(other) == "", other
    import inspect
    assert '**({"office": office} if office else {})' in inspect.getsource(B.build_legislators), (
        "build_legislators does not write a member's office into their own file")
    got = _app_js("[scope.renderMemberHead(" + json.dumps({**speaker,
                                                         "office": "Speaker of the House"})
                  + "), scope.renderMemberHead(" + json.dumps({**speaker, "seat": "1002"}) + ")]",
                  names=("renderMemberHead",))
    if got is None:
        return "ok", "seat 6002's member is Speaker of the House; node is not here to draw it"
    head, floor = got
    # The record head's line (C6, 10 October 2026): the office first, then
    # the party and the seat in words; the heading says the chamber.
    assert re.search(r'<p class="rline"><b>Speaker of the House</b>&nbsp;&middot; Republican'
                     r'&nbsp;&middot; Rockingham District&nbsp;16', head), (
        "the Speaker's page does not say he is Speaker: " + re.sub(r"\s+", " ", head)[:300])
    assert '<p class="rline">Republican&nbsp;&middot; Rockingham District&nbsp;16' in floor and \
        '<h1 class="rh1">Representative Sherman Packard</h1>' in floor, (
        "a member of the floor lost the chamber's name: " + re.sub(r"\s+", " ", floor)[:300])
    return "ok", "seat 6002's member is Speaker of the House on his own page; nobody else is"


@check("frontend", "a member's page heads with their title in full, and names the office "
                   "the record gives them; a presiding ballot names it too",
       needs=("build_site_v2", "build_legislator_pages", "build_session_pages", "officers"))
def _officers_on_the_page(B, BLP, BSP, OF):
    """The person, 9 October 2026: "Sharon Carson is the Senate President
    and should also have some indicator similar to how you did the Speaker
    of the House. Member pages should list their title along with their
    name at the top like Senator Sharon Carson or Representative James
    Spillane." Their own rows: Sen. Sharon Carson (R - SD14), President of
    the Senate; Rep. James Spillane (R - Rock 2), who holds no office; a
    member who has left is "Former Representative". On a vote card, Rep.
    Steven Smith presiding over a roll call of 8 May 2025 is named Deputy
    Speaker of the House, and nobody voting is named anything; in a
    printed debate his turn in the chair is "Deputy Speaker Steven Smith"
    and is still not counted as a speech."""
    carson = {"id": "35", "name": "Carson, Sharon", "chamber": "S", "seat": "",
              "district": "14", "county": "Rockingham",
              "display_full": "Sen. Sharon Carson (R - SD14)", "towns": ["Londonderry"]}
    spillane = {"id": "905", "name": "Spillane, James", "chamber": "H", "seat": "3024",
                "district": "2", "county": "Rockingham",
                "display_full": "Rep. James Spillane (R - Rock 2)", "towns": ["Deerfield"]}
    offices = {"35": "President of the Senate"}
    assert B.member_office(carson, offices) == "President of the Senate"
    assert B.member_office(spillane, offices) == ""
    assert B.member_office({**carson, "former": True}, offices) == ""
    gone = {"id": "1", "former": True, "display_full": "Rep. Michael Gunski (R - Hills 6)"}
    assert BLP.head_name(spillane) == "Representative James Spillane (R - Rock 2)"
    assert BLP.head_name(carson) == "Senator Sharon Carson (R - SD14)"
    assert BLP.head_name(gone) == "Former Representative Michael Gunski (R - Hills 6)"
    assert BLP.heading(spillane) == "Rep. James Spillane (R - Rock 2)", (
        "the page's title and link card lost the short form")
    assert "<h1>Senator Sharon Carson (R - SD14)</h1>" in BLP.static_record(carson, {})

    import html as _html
    deb = {"bill": "SB62", "speeches": [
        ("Speaker Steven Smith", "The bill is on second reading and open to further amendment."),
        ("Rep. Roy", "The safety for themselves and their families to continue to do the job.")]}
    tens = [{"body": "H", "title": "Speaker", "office": "Speaker of the House",
             "name": "Sherman Packard", "from": "2024-12-04", "to": "2026-12-02"},
            {"body": "H", "title": "Deputy Speaker", "office": "Deputy Speaker of the House",
             "name": "Steven Smith", "from": "2024-12-04", "to": "2026-12-02"}]
    nobody = BSP.Members(Path("no-such-site"))
    page = BSP._debate_html(deb, "H", nobody, _html.escape,
                            chair=lambda who: OF.chair_label(who, "2025-05-08", tens))
    assert "<span>Deputy Speaker Steven Smith</span>" in page and "1 speech<" in page, page[:600]
    plain = BSP._debate_html(deb, "H", nobody, _html.escape)
    assert "<span>Speaker Steven Smith</span>" in plain, "without the officers, the heading moved"

    off = [{"b": "H", "s": "smith, steven", "from": "2024-12-04", "to": "2026-12-02",
            "office": "Deputy Speaker of the House"}]
    rc = {"date": "2025-05-08", "body": "H"}
    got = _app_js("[scope.renderMemberHead(" + json.dumps({**carson, "office": offices["35"]})
                  + "), scope.renderMemberHead(" + json.dumps(spillane) + "), "
                  "scope.renderMemberHead(" + json.dumps(gone) + "), "
                  "(scope.setOff(" + json.dumps(off) + "), "
                  "[scope.ballotCell(" + json.dumps(rc) + ", {n:'Rep. Steven Smith (R)', "
                  "s:'smith, steven', v:'Presiding'}), "
                  "scope.ballotCell(" + json.dumps(rc) + ", {n:'Rep. Steven Smith (R)', "
                  "s:'smith, steven', v:'Yea'}), "
                  "scope.ballotCell({date:'2025-04-10', body:'H'}, {n:'Rep. Jim Kofalt (R)', "
                  "s:'kofalt, jim', v:'Presiding'}), "
                  # The same member presiding on a day the record gives him no
                  # office (10 March 2022, the term before), and a ballot of the
                  # other chamber under the same key: neither is named anything.
                  "scope.ballotCell({date:'2022-03-10', body:'H'}, {n:'Rep. Steven Smith (R)', "
                  "s:'smith, steven', v:'Presiding'}), "
                  "scope.ballotCell({date:'2025-05-08', body:'S'}, {n:'Sen. Steven Smith (R)', "
                  "s:'smith, steven', v:'Presiding'})])]",
                  names=("renderMemberHead", "ballotCell", "setOff: x => (OFFICERS = x)"))
    if got is None:
        return "ok", "the offices and the headings hold in Python; node is not here to draw them"
    head_c, head_s, head_g, cells = got
    # The record head (C6, 10 October 2026), as the approved prototype
    # draws it: the title in full and the name, and the office, the party
    # and the seat in words on the line under it.
    assert '<h1 class="rh1">Senator Sharon Carson</h1>' in head_c, head_c[:300]
    assert ('<p class="rline"><b>President of the Senate</b>&nbsp;&middot; Republican'
            '&nbsp;&middot; Senate District&nbsp;14') in head_c, (
        "the President of the Senate's page does not say so: " + re.sub(r"\s+", " ", head_c)[:300])
    assert '<h1 class="rh1">Representative James Spillane</h1>' in head_s, head_s[:300]
    assert '<p class="rline">Republican&nbsp;&middot; Rockingham District&nbsp;2' in head_s, head_s[:400]
    assert '<h1 class="rh1">Former Representative Michael Gunski</h1>' in head_g, head_g[:300]
    # A member's name is not translated, the office beside it is (23 October 2026).
    assert cells == ['<div class="m" translate="no">Rep. Steven Smith (R)<span class="p mo" translate="yes">Deputy '
                     'Speaker of the House</span></div>',
                     '<div class="m" translate="no">Rep. Steven Smith (R)</div>',
                     '<div class="m" translate="no">Rep. Jim Kofalt (R)</div>',
                     '<div class="m" translate="no">Rep. Steven Smith (R)</div>',
                     '<div class="m" translate="no">Sen. Steven Smith (R)</div>'], cells
    return "ok", ("\"Senator Sharon Carson (R - SD14)\", President of the Senate; "
                  "\"Representative James Spillane (R - Rock 2)\"; the Deputy Speaker named "
                  "on his presiding ballot and in the chair")


@check("data", "the member in the Speaker's chair is Speaker of the House in his own file, "
               "and every other sitting member's office is one the record gives them",
       needs=("build_site_v2", "officers"))
def _speaker_page_built(B, OF):
    """Seat 6002's member is Speaker of the House, and nobody else is. Since
    9 October 2026 the other officers' own pages name their offices too --
    the President of the Senate, the Deputy Speaker, the Speaker Pro Tempore
    (build_officers) -- and each must be an office site/officers.json says
    that member holds on the day the site was built, and no two members may
    hold one office.

    ON THAT DAY, NOT ON ANY (the review of 9 October 2026): the first form of
    this check held an office to any tenure of it in officers.json, so a page
    still calling Rep. Steven Smith Deputy Speaker in a term whose record
    names nobody -- on the strength of 2023-2024 -- passed. A tenure covers
    the build's day (site/build.json) from its first day to the day before
    `to`; a "day" tenure, where the record named two people in one office in
    one term, covers it as officers.holders does -- the latest so named in
    the build's term, on or before the day."""
    d, lp = Path("site/legislators"), Path("site/legislators.json")
    if not (d.is_dir() and lp.exists()):
        return "skip", "site/legislators is not here"
    rows = json.loads(lp.read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else list(rows.values())
    chair = [r for r in rows if str(r.get("seat")) == str(B.SPEAKER_SEAT)]
    assert len(chair) == 1, f"{len(chair)} sitting members are seated in the Speaker's chair"
    offices = {}
    for r in rows:
        f = d / f"{r['id']}.json"
        if f.exists():
            o = json.loads(f.read_text(encoding="utf-8")).get("office")
            if o:
                offices[r["id"]] = o
    speaker = {k for k, o in offices.items() if o == "Speaker of the House"}
    # FROM THE DAY AFTER ORGANIZATION DAY UNTIL THE ROSTER TURNS (members.read_switch; the
    # owner, 25 November 2026): a member the election did not return is drawn as a former
    # member, and a former member's file names no office (members.member_office) -- the Speaker
    # of 2025-2026, Sherman Packard, from 3 December 2026, while legislators.json, the roster's,
    # still seats him in the chair. The chair's member is then nobody's Speaker on the site
    # until the roster seats the next one there (_speaker_page_through_the_switch).
    import members as MEM
    gone = str(chair[0]["id"]) in MEM.read_switch(Path("site"))["leaving"]
    assert speaker == (set() if gone else {str(chair[0]["id"])}), (
        f"{chair[0].get('name')} sits in the Speaker's chair"
        + (", drawn as not returning (site/seat_switch.json)," if gone else ",")
        + f" and the offices on file are {offices}: rebuild the site data")
    others = {k: o for k, o in offices.items() if k not in speaker}
    assert len(set(others.values())) == len(others), f"one office, two members: {others}"
    of = Path("site/officers.json")
    if others:
        assert of.exists(), f"offices on file and no site/officers.json: {others}"
        tens = json.loads(of.read_text(encoding="utf-8")).get("officers") or []
        try:
            built = str(json.loads(Path("site/build.json").read_text(encoding="utf-8"))
                        .get("finished") or "")[:10]
        except (OSError, ValueError, AttributeError):
            built = ""

        def holds(t):
            if not built:
                return True
            if t["from"] > built:
                return False
            if t.get("kind") != "day":
                return built < t["to"]
            term = OF.term_of(built)
            later = [u for u in tens if (u["b"], u["title"]) == (t["b"], t["title"])
                     and u.get("kind") == "day" and t["from"] < u["from"] <= built
                     and OF.term_of(u["from"]) == term]
            return OF.term_of(t["from"]) == term and not later
        held = {(t["id"], t["office"]) for t in tens if holds(t)}
        stray = {k: o for k, o in others.items() if (k, o) not in held}
        assert not stray, (f"offices on file that officers.json gives nobody"
                           f"{' on ' + built if built else ''}: {stray}")
    return "ok", ((f"{chair[0].get('name')}, in seat {B.SPEAKER_SEAT}, is not returning, and no "
                   "file names the Speaker until the roster turns" if gone else
                   f"{chair[0].get('name')}, in seat {B.SPEAKER_SEAT}, is Speaker of the House")
                  + "".join(f"; {next(r.get('name') for r in rows if r['id'] == k)}, {o}"
                            for k, o in sorted(others.items(), key=lambda x: x[1])))


@check("build", "the night's Speaker check holds through the switch: from the day after Organization "
                "Day until the roster turns, a Speaker not returning is nobody's Speaker on file, and "
                "any other file naming the office, or theirs, still fails it",
       needs=("build_site_v2", "officers", "members"))
def _speaker_page_through_the_switch(B, OF, MEM):
    """The night runs _speaker_page_built on its built site (preflight --built; a check that holds
    the night), and on 3 December 2026 the Speaker of 2025-2026, Sherman Packard, is among the
    members not returning: from that day his own file is the former member's
    (members.seat_switched), which names no office (members.member_office), while the roster's
    legislators.json still seats him in the chair until the General Court's roster turns. Held
    on made-up sites of two members, the chair's (425) and Steven Smith (656): the chair's file
    naming the office and no switch passes; the chair's member drawn as leaving by
    site/seat_switch.json, no file naming the office, passes; no file naming it and no switch
    fails; the leaving member's file still naming it fails; and another member's file naming it
    while the chair's member leaves fails."""
    here = Path(".").resolve()
    root = Path(tempfile.mkdtemp(prefix="gr-speaker-switch-"))
    rows = [{"id": "425", "name": "Packard, Sherman", "chamber": "H", "seat": str(B.SPEAKER_SEAT)},
            {"id": "656", "name": "Smith, Steven", "chamber": "H", "seat": "1001"}]

    def run(chair_office, leaving, other_office=None):
        s = root / "site"
        shutil.rmtree(s, ignore_errors=True)
        (s / "legislators").mkdir(parents=True)
        (s / "legislators.json").write_text(json.dumps(rows), encoding="utf-8")
        for r, o in ((rows[0], chair_office), (rows[1], other_office)):
            (s / "legislators" / f"{r['id']}.json").write_text(
                json.dumps({**r, **({"office": o} if o else {})}), encoding="utf-8")
        if leaving:
            (s / MEM.SEAT_SWITCH).write_text(json.dumps(
                {"day": "2026-12-03", "election": "2026-11-03", "term": "2027-2028",
                 "leaving": [{"id": "425", "former": True}], "moved": []}), encoding="utf-8")
        os.chdir(root)
        try:
            return _speaker_page_built(B, OF)[0]
        except AssertionError:
            return "fails"
        finally:
            os.chdir(here)

    try:
        got = {"the chair's, no switch": run("Speaker of the House", False),
               "leaving, none named": run(None, True),
               "none named, no switch": run(None, False),
               "leaving and still named": run("Speaker of the House", True),
               "leaving, another named": run(None, True, "Speaker of the House")}
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)
    assert got == {"the chair's, no switch": "ok", "leaving, none named": "ok",
                   "none named, no switch": "fails", "leaving and still named": "fails",
                   "leaving, another named": "fails"}, f"_speaker_page_built says {got}"
    return "ok", ("the chair's Speaker passes; the chair's member leaving with no Speaker on file "
                  "passes; no Speaker and no switch, the leaving member still Speaker, and another "
                  "member Speaker while the chair's leaves each fail")


@check("status", "the rail's last stop carries a day: the day a law took effect, or the day the bill was killed",
       needs=("build_site_v2",))
def _rail_law_stop_dated(build_site_v2):
    """"Rail: under Law, the effective date when it became law; when killed,
    the day it was killed under that last stop" (the person, 7 October 2026,
    F13). The Law stop was the one stop reached that carried no day.

    HB 57 of 2025, signed on 15 July and "eff. 01/11/2026", dates its Law
    stop 11 January 2026, on the list card's row and on the bill's own rail
    alike; HB 68, killed in the Senate on 7 January 2026, dates its Law stop
    that day. law_day itself: a law in effect on several dates states none,
    a stop not reached has none, and a bill stopped by a veto sustained after
    a chamber's kill takes the later day. The day under a stop is all a rail
    draws (_rail_drawn), and what it says aloud of a law says "in effect"
    once (_rail_dated holds the sentence)."""
    B = build_site_v2
    rows = {row["id"]: (row, rec) for row, rec in _journey_bills(B)}
    for bid, want in (("HB57", "2026-01-11"), ("HB68", "2026-01-07")):
        row, rec = rows[bid]
        card = row["rail"][-1]
        own = rec["journey"]["rail"][-1]
        assert card[0][0] == "L" and (card + [""])[1] == want, (
            f"{bid}'s list card dates its Law stop {card}, not {want}")
        assert own["stop"] == "Law" and own["date"] == want, (
            f"{bid}'s own rail dates its Law stop {own}, not {want}")
    stops = [{"stop": "House", "mark": "x", "date": "2025-03-01"},
             {"stop": "Governor", "mark": "x", "date": "2025-07-10"}]
    steps = [{"body": "H", "mark": "x", "date": "2025-03-01"},
             {"body": "S", "mark": "x", "date": "2025-09-16"}]
    assert B.law_day("x", None, stops, steps) == "2025-09-16", (
        "a bill stopped twice is dated by the earlier stop, not the day that ended it")
    assert B.law_day("p", {"effective": ""}, [], []) == "" and B.law_day("p", None, [], []) == "", (
        "a law in effect on several dates, or with no line, is given a day")
    assert B.law_day("-", None, stops, steps) == "" and B.law_day("h", None, stops, steps) == "", (
        "a Law stop not reached is given a day")
    assert B.law_day("x", None, [], []) == "", "a kill with no day on record is given one"
    return "ok", ("HB 57's Law stop on 11 January 2026, when it took effect, and HB 68's on "
                  "7 January 2026, when it was killed, on the card and the page alike")


@check("frontend", "a bill whose session has ended is not shown as still in committee",
       needs=("build_bill_pages",))
def _dead_bill_status_shown(BBP):
    """The audit of 25 October 2026 (S4): HB 520 of 2017 showed the chip
    "Died" over "Status: In committee". Once a session has ended the chip says
    Died (build_site_v2.chip_word), and the record keeps the stage the bill
    stood at where the record does not settle how it ended. The page says
    that stage -- "In committee", "Committee report filed" -- as "Died when
    the session ended", the build's words for the same end on the bills
    beside it, and the record is unchanged. billHead is drawn in node; the
    page without scripts (static_record) and the sentence a search engine
    shows (describe) say it the same way."""
    def bill(status, chip):
        return {"id": "HB520", "n": "HB 520", "term": "2017-2018", "year": 2017,
                "status": status, "chip": chip}
    cases = [bill("In committee", "Died"), bill("Committee report filed", "Died"),
             bill("Killed", "Died"), bill("In committee", "In committee")]
    got = _app_js("[" + ",".join("scope.billHead(" + json.dumps(b) + ", null)" for b in cases) + "]",
                  names=("billHead",))
    drew = "node is not here to draw billHead"
    if got is not None:
        rows = [dict(re.findall(r"<dt>([^<]*)</dt>\s*<dd>(.*?)</dd>", h, re.S)) for h in got]
        status = [" ".join(re.sub(r"<[^>]+>", " ", r.get("Status", "")).split()) for r in rows]
        assert status == ["Died when the session ended", "Died when the session ended", "Killed", ""], (
            f"the head's Status reads {status} for In committee and Committee report filed under Died, "
            "Killed under Died, and In committee while the session sits")
        drew = "the head says it"
    plain = [BBP.static_record(b, {}) for b in cases]
    assert "<b>Status:</b> Died when the session ended" in plain[0] and \
        "<b>Status:</b> Died when the session ended" in plain[1] and "In committee" not in plain[0], (
            "the page without scripts still says a dead bill is in committee")
    assert "<b>Status:</b> In committee" in plain[3] and "<b>Status:</b> Killed" in plain[2], (
        "the page without scripts changed a status it should keep")
    assert BBP.describe(cases[0]).endswith("Died when the session ended.") and \
        BBP.describe(cases[3]).endswith("In committee."), (
            f"the search engine's sentence reads {BBP.describe(cases[0])!r}")
    return "ok", (f"In committee and Committee report filed under Died read \"Died when the session "
                   f"ended\"; {drew}, as do the page without scripts and its description")


@check("frontend", "a member the story names is linked where one sitting member is meant, "
       "and left as words where two are", needs=("build_site_v2",))
def _story_people(B):
    """The person, 10 October 2026: movers named in a bill's story were not
    linked. build_site_v2.story_people ties "Rep. Jane Smith" and "Sen.
    Bradley" to one sitting member each (mover_member), takes "Rep. Smith
    Amendment" as "Rep. Smith", and leaves "Rep. Lee", whom two members
    could be, as the words it was; app.js's storyPeople links the first two
    where the story names them and nothing inside another link."""
    legs = {"1": {"name": "Smith, Jane", "chamber": "H", "party": "R", "slug": "jane-smith-rock-13",
                  "label": "Rep. Jane Smith (R - Rock 13)"},
            "2": {"name": "Bradley, Jeb", "chamber": "S", "party": "R", "slug": "jeb-bradley-s3",
                  "label": "Sen. Jeb Bradley (R - 3)"},
            "3": {"name": "Lee, Ann", "chamber": "H", "party": "D", "slug": "ann-lee"},
            "4": {"name": "Lee, Bo", "chamber": "H", "party": "R", "slug": "bo-lee"}}
    text = ("A floor amendment, offered by Rep. Jane Smith, failed. Sen. Bradley moved to table it. "
            "Rep. Lee spoke.")
    got = B.story_people([text, "Rep. Jane Smith Amendment was withdrawn."], legs)
    said = {p["text"]: p["slug"] for p in got}
    assert said == {"Rep. Jane Smith": "jane-smith-rock-13", "Sen. Bradley": "jeb-bradley-s3"}, said
    html = _app_js("scope.storyPeople(" + json.dumps(text) + ", " + json.dumps({"story_people": got})
                   + ")", names=("storyPeople",))
    if html is None:
        return "ok", "story_people ties two of three names; node is not here for the page"
    assert html.count('class="psent"') == 2 and 'href="legislator/jane-smith-rock-13"' in html \
        and "Rep. Lee spoke." in html, html
    return "ok", "Rep. Jane Smith and Sen. Bradley linked; Rep. Lee, two members, left as words"


@check("build", "a finished term's movers stay linked after the turn, by the seat held in that term",
       needs=("build_site_v2",))
def _movers_of_a_finished_term(B):
    """The rehearsal of the turn (19 November 2026): a roll call's mover was
    linked only while its term was the current one, against the sitting
    roster, so the night 2027-2028 became the current term 2025-2026 lost
    "Moved by <linked person>" on 843 roll calls of 647 bills. mover_pool
    gives a term whose own roster is frozen and is not the sitting one that
    roster, the seat each member held in it, linked to the person's page as
    it is now (build_bills' `_people`, as the sponsors are); the current term
    the sitting roster, as before; any other term nobody. Here a fake turn:
    Joe Alexander moved to Hills 69, Pat Gone left at the election and a
    Newcomer Gone took a seat, two Lees sat in 2025-2026, and Kim Nopage sat
    then and has no page now. And between Organization Day and the switch,
    with the next House installed and 2025-2026 still current, the same."""
    def mem(i, last, first, ch, county, abbr, dist, party):
        return {"id": i, "name": f"{last}, {first}", "chamber": ch, "county": county,
                "county_abbr": abbr, "district": dist, "party_code": party}
    then = {m["id"]: m for m in (
        mem("1", "Alexander", "Joe", "H", "Hillsborough", "Hills", "29", "R"),
        mem("2", "Carson", "Sharon", "S", "", "", "14", "R"),
        mem("3", "Lee", "Ann", "H", "Hillsborough", "Hills", "1", "D"),
        mem("4", "Lee", "Bo", "H", "Hillsborough", "Hills", "2", "R"),
        mem("5", "Gone", "Pat", "H", "Belknap", "Belk", "3", "D"),
        mem("6", "Nopage", "Kim", "H", "Coos", "Coos", "1", "R"))}
    now = {m["id"]: m for m in (
        mem("1", "Alexander", "Joe", "H", "Hillsborough", "Hills", "69", "R"),
        mem("2", "Carson", "Sharon", "S", "", "", "14", "R"),
        mem("3", "Lee", "Ann", "H", "Hillsborough", "Hills", "1", "D"),
        mem("9", "Gone", "Newcomer", "H", "Belknap", "Belk", "4", "R"))}
    former = {"4": {**then["4"], "former": True}, "5": {**then["5"], "former": True}}
    people = {**now, **former}
    rosters = {"2025-2026": then}
    said = ("Rep. Alexander Jr.", "Sen. Carson", "Rep. Gone", "Rep. Lee", "Rep. Ann Lee",
            "Rep. Nopage")
    keep_slugs, keep_spell = dict(B._OWN_SLUG), list(B._SPELLINGS)
    try:
        B._SPELLINGS[:] = [{}]

        def linked(term, current, legs, term_rosters):
            B._OWN_SLUG.clear()
            pool, pages = B.mover_pool(term, current, legs, term_rosters, people)
            return {s: (B.mover_member(s, "S" if s.startswith("Sen") else "H", pool, pages=pages)
                        if pool is not None else None) for s in said}
        after = linked("2025-2026", "2027-2028", now, rosters)
        window = linked("2025-2026", "2025-2026", now, rosters)
        today = linked("2025-2026", "2025-2026", then, {})
        older = linked("2023-2024", "2025-2026", then, {})
        B._OWN_SLUG.clear()
        plain = {s: B.mover_member(s, "S" if s.startswith("Sen") else "H", then) for s in said}
    finally:
        B._OWN_SLUG.clear()
        B._OWN_SLUG.update(keep_slugs)
        B._SPELLINGS[:] = keep_spell
    want = {"Rep. Alexander Jr.": {"label": "Rep. Joe Alexander (R - Hills 29)",
                                   "slug": "joe-alexander-hills-69"},
            "Sen. Carson": {"label": "Sen. Sharon Carson (R - SD14)", "slug": "sharon-carson-sd-14"},
            "Rep. Gone": {"label": "Rep. Pat Gone (D - Belk 3)", "slug": "pat-gone-belk-3"},
            "Rep. Lee": None, "Rep. Ann Lee": {"label": "Rep. Ann Lee (D - Hills 1)",
                                               "slug": "ann-lee-hills-1"},
            "Rep. Nopage": None}
    bad = [f"{s!r} is {after.get(s)!r}, not {w!r}" for s, w in want.items() if after.get(s) != w]
    assert not bad, "a 2025-2026 mover after the turn: " + "; ".join(bad)
    assert window == after, f"between Organization Day and the switch the movers read {window}"
    # the current term with its own roster sitting: exactly as before the fix
    assert today == plain and today["Rep. Alexander Jr."]["slug"] == "joe-alexander-hills-29" \
        and today["Rep. Nopage"], f"the current term's movers moved: {today}"
    assert not any(older.values()), f"a term with no frozen roster linked a mover: {older}"
    src = _source(_paths.locate("build_site_v2.py"))
    assert "mover_pool(term, current, legs, term_rosters, _people,\n" in src and \
        'mover_member(r["mover"], r.get("body"), _mpool, pages=_mpages)' in src, (
            "build_bills no longer looks for a roll call's mover among the term's own members")
    return "ok", ("after the turn and between Organization Day and the switch, 2025-2026's movers "
                  "keep the seat of the term (Alexander's Hills 29, linked to his Hills 69 page), "
                  "Pat Gone is not the Newcomer Gone, two Lees and a member with no page stay "
                  "words; the current term as before; a term with no frozen roster links none")


@check("build", "the members a finished term's story names stay linked after the turn, by the "
                "seat held in that term", needs=("build_site_v2",))
def _story_people_of_a_finished_term(B):
    """The same fault as a roll call's mover (_movers_of_a_finished_term):
    a bill's story linked the members it names only in the current term,
    against the sitting roster, so at the turn 2025-2026's records would lose
    their story_people (1,164 of them in the records of 7 November). The
    story looks names up where the roll calls' movers are looked up
    (mover_pool): after the turn, Rep. Joe Alexander with his Hills 29 of the
    term, linked to his page as it is now; Rep. Gone the Pat Gone who left,
    not the newcomer of that surname."""
    def mem(i, last, first, dist, party):
        return {"id": i, "name": f"{last}, {first}", "chamber": "H", "county": "Hillsborough",
                "county_abbr": "Hills", "district": dist, "party_code": party}
    then = {"1": mem("1", "Alexander", "Joe", "29", "R"), "5": mem("5", "Gone", "Pat", "3", "D")}
    now = {"1": mem("1", "Alexander", "Joe", "69", "R"), "9": mem("9", "Gone", "Newcomer", "4", "R")}
    people = {**now, "5": {**then["5"], "former": True}}
    text = "Rep. Alexander moved to table; Rep. Gone offered a floor amendment."
    keep_slugs, keep_spell = dict(B._OWN_SLUG), list(B._SPELLINGS)
    try:
        B._SPELLINGS[:] = [{}]
        B._OWN_SLUG.clear()
        pool, pages = B.mover_pool("2025-2026", "2027-2028", now, {"2025-2026": then}, people)
        got = {p["text"]: (p["label"], p["slug"]) for p in B.story_people([text], pool, pages=pages)}
        B._OWN_SLUG.clear()
        today = B.story_people([text], then)
    finally:
        B._OWN_SLUG.clear()
        B._OWN_SLUG.update(keep_slugs)
        B._SPELLINGS[:] = keep_spell
    want = {"Rep. Alexander": ("Rep. Joe Alexander (R - Hills 29)", "joe-alexander-hills-69"),
            "Rep. Gone": ("Rep. Pat Gone (D - Hills 3)", "pat-gone-hills-3")}
    assert got == want, f"a 2025-2026 story after the turn names {got}, not {want}"
    assert [p["slug"] for p in today] == ["joe-alexander-hills-29", "pat-gone-hills-3"], (
        f"the current term's story moved: {today}")
    src = _source(_paths.locate("build_site_v2.py"))
    assert "_mpool, pages=_mpages) if _mpool is not None else [])" in src, (
        "build_bills no longer looks for the story's members among the term's own members")
    return "ok", ("after the turn a 2025-2026 story names Alexander by Hills 29, linked to his "
                  "page now, and Pat Gone, not the newcomer; the current term as before")


@check("build", "a mover of 1999-2024 is linked among that term's own voters, by the seat the "
                "term gives them", needs=("build_site_v2",))
def _movers_of_older_terms(B):
    """The owner, 19 November 2026: "Yes, link them". A roll call's mover in a
    term before the current one, and with no frozen roster, is looked for
    among the members whose own ballots of that term were cast in that
    chamber (term_voters), named by the seat the term gives them (term_seats,
    the seat a session day names them by) and linked to the page their
    ballots are on (`people`). Here, in the shape of the real record: Robert
    Letourneau, a Representative of Rock 77 in 2003-2004 under one number and
    a Senator of SD19 in 2005-2006 under another, one page; Andy Sanborn,
    SD7 and then SD9 across the 2012 redistricting; two Eatons voting in the
    House of 2013-2014, so "Rep. Eaton" stays words
    while "Rep. Richard Eaton" links; David Boutin, who moved to the Senate in
    2010 and whom the term gives a House seat only, unlinked as a Senator; no
    one in 1989-1990, which has no ballots; and the current term still the
    sitting roster's, whatever its ballots say. And floor_record.json is the
    same whether main works the seats out before the bills or it does."""
    def ballot(mid, name, body, year, label):
        return {"member_id": mid, "name": name, "body": body, "year": year,
                "date": f"{year}-03-01", "party": "R", "label": label, "vote": "Yea",
                "bill": "HB1", "vote_number": "1"}
    votes = {
        "376142": [ballot("376142", "Letourneau, Robert", "H", "2003",
                          "Rep. Robert Letourneau (R - Rock 77)")],
        "209060": [ballot("209060", "Letourneau, Robert", "S", "2005",
                          "Sen. Robert Letourneau (R - SD19)")],
        "39": [ballot("39", "Sanborn, Andy", "S", "2011", "Sen. Andy Sanborn (R - SD7)"),
               ballot("39", "Sanborn, Andy", "S", "2013", "Sen. Andy Sanborn (R - SD9)")],
        "101": [ballot("101", "Eaton, Daniel", "H", "2013", "Rep. Daniel Eaton (D - Ches 9)")],
        "102": [ballot("102", "Eaton, Richard", "H", "2013", "Rep. Richard Eaton (D - Hills 38)")],
        "37": [ballot("37", "Boutin, David", "H", "2009", "Rep. David Boutin (R - Merr 9)"),
               ballot("37", "Boutin, David", "S", "2010", "Sen. David Boutin (R - SD16)")],
        "201": [ballot("201", "Smith, Ann", "H", "2025", "Rep. Ann Smith (R - Rock 1)")],
        "202": [ballot("202", "Smith, Jane", "H", "2025", "Rep. Jane Smith (R - Rock 13)")]}
    seats = {"2003-2004": {"376142": "Rep. Robert Letourneau (R - Rock 77)"},
             "2005-2006": {"209060": "Sen. Robert Letourneau (R - SD19)"},
             "2011-2012": {"39": "Sen. Andy Sanborn (R - SD7)"},
             "2013-2014": {"39": "Sen. Andy Sanborn (R - SD9)",
                           "101": "Rep. Daniel Eaton (D - Ches 9)",
                           "102": "Rep. Richard Eaton (D - Hills 38)"},
             "2009-2010": {"37": "Rep. David Boutin (R - Merr 9)"}}
    letourneau = {"id": "209060", "slug": "robert-letourneau-sd-19"}
    people = {"376142": letourneau, "209060": letourneau,
              "39": {"id": "39", "slug": "andy-sanborn-sd-9"},
              "101": {"id": "101", "slug": "daniel-eaton-ches-9"},
              "102": {"id": "102", "slug": "richard-eaton-hills-38"},
              "37": {"id": "37", "slug": "david-boutin-sd-16"}}
    legs = {"202": {"id": "202", "name": "Smith, Jane", "chamber": "H", "party_code": "R",
                    "county": "Rockingham", "county_abbr": "Rock", "district": "13"}}
    voters = B.term_voters(votes, seats)
    asked = (("2003-2004", "H", "Rep Letourneau"), ("2005-2006", "S", "Sen. Letourneau"),
             ("2003-2004", "S", "Sen. Letourneau"),
             ("2011-2012", "S", "Sen. Sanborn"), ("2013-2014", "S", "Sen. Sanborn"),
             ("2013-2014", "H", "Rep. Eaton"), ("2013-2014", "H", "Rep. Richard Eaton"),
             ("2009-2010", "S", "Sen. Boutin"), ("2009-2010", "H", "Rep. Boutin"),
             ("1989-1990", "H", "Rep. Letourneau"), ("2025-2026", "H", "Rep. Smith"))
    keep_slugs, keep_spell = dict(B._OWN_SLUG), list(B._SPELLINGS)
    got = {}
    try:
        B._SPELLINGS[:] = [{}]
        for term, body, said in asked:
            B._OWN_SLUG.clear()
            pool, pages = B.mover_pool(term, "2025-2026", legs, {}, people, voters)
            got[(term, said)] = (B.mover_member(said, body, pool, pages=pages)
                                 if pool is not None else None)
    finally:
        B._OWN_SLUG.clear()
        B._OWN_SLUG.update(keep_slugs)
        B._SPELLINGS[:] = keep_spell
    L = "robert-letourneau-sd-19"
    want = {("2003-2004", "Rep Letourneau"): {"label": "Rep. Robert Letourneau (R - Rock 77)",
                                              "slug": L},
            ("2005-2006", "Sen. Letourneau"): {"label": "Sen. Robert Letourneau (R - SD19)",
                                               "slug": L},
            ("2003-2004", "Sen. Letourneau"): None,
            ("2011-2012", "Sen. Sanborn"): {"label": "Sen. Andy Sanborn (R - SD7)",
                                            "slug": "andy-sanborn-sd-9"},
            ("2013-2014", "Sen. Sanborn"): {"label": "Sen. Andy Sanborn (R - SD9)",
                                            "slug": "andy-sanborn-sd-9"},
            ("2013-2014", "Rep. Eaton"): None,
            ("2013-2014", "Rep. Richard Eaton"): {"label": "Rep. Richard Eaton (D - Hills 38)",
                                                  "slug": "richard-eaton-hills-38"},
            ("2009-2010", "Sen. Boutin"): None,
            ("2009-2010", "Rep. Boutin"): {"label": "Rep. David Boutin (R - Merr 9)",
                                           "slug": "david-boutin-sd-16"},
            ("1989-1990", "Rep. Letourneau"): None,
            ("2025-2026", "Rep. Smith"): {"label": "Rep. Jane Smith (R - Rock 13)",
                                          "slug": "jane-smith-rock-13"}}
    bad = [f"{t} {s!r} is {got.get((t, s))!r}, not {w!r}" for (t, s), w in want.items()
           if got.get((t, s)) != w]
    assert not bad, "a mover of an older term: " + "; ".join(bad)
    # floor_record.json, the seats worked out by main beforehand or by itself
    root = Path(tempfile.mkdtemp(prefix="gr-older-movers-"))
    try:
        (root / "a").mkdir()
        (root / "b").mkdir()
        import contextlib
        import io
        rec = ({}, set(), {})
        balls = {}
        worked = (B.term_seats(votes, record=rec, ballots=balls), balls)
        with contextlib.redirect_stdout(io.StringIO()):
            a = B.write_floor_record(root / "a", votes, {}, record=rec).read_bytes()
            b = B.write_floor_record(root / "b", votes, {}, record=rec, worked=worked).read_bytes()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert a == b, "floor_record.json differs when main works the seats out before the bills"
    src = _source(_paths.locate("build_site_v2.py"))
    assert "mover_pool(term, current, legs, term_rosters, _people,\n" in src and \
        "voters = term_voters(votes_by_member, floor_seats)" in src and \
        "tagging=tagging, voter_pools=voters)" in src and "worked=(floor_seats, floor_ballots))" in src, (
            "build_bills is not handed each term's voters, or the session days another seat")
    return "ok", ("Letourneau linked as Rep. of Rock 77 and Sen. of SD19 to his one page, Sanborn "
                  "by SD7 and then SD9, Rep. Eaton (two that term) and Sen. Boutin (no Senate "
                  "seat of the term) left as words, 1989-1990 none, the current term the "
                  "sitting roster's; floor_record.json the same either way")


# A SAMPLE OF THE OLDER TERMS' MOVERS AS THE BUILT RECORDS MUST CARRY THEM (19 November 2026),
# each read beside the member's own ballots of that term and the seat floor_record gives them:
# (term, bill, the docket's mover) -> (label, page), or None where the name must stay words.
OLDER_MOVERS = {
    ("1999-2000", "SB224", "Sen. Cohen"): ("Sen. Burton Cohen (D - SD24)", "burton-cohen-sd-24"),
    ("1999-2000", "HB331", "Sen. Gordon"): ("Sen. Edward (Ned) Gordon (R - SD2)",
                                            "edward-gordon-graf-9"),
    ("2021-2022", "HB236", "Rep. Gordon"): ("Rep. Edward Gordon (R - Graf 9)", "edward-gordon-graf-9"),
    ("2003-2004", "SB427", "Rep Letourneau"): ("Rep. Robert Letourneau (R - Rock 77)",
                                               "robert-letourneau-sd-19"),
    ("2005-2006", "HB84", "Sen. Letourneau"): ("Sen. Robert Letourneau (R - SD19)",
                                               "robert-letourneau-sd-19"),
    ("2011-2012", "HB187", "Sen. Sanborn"): ("Sen. Andy Sanborn (R - SD7)", "andy-sanborn-sd-9"),
    ("2013-2014", "HB253", "Sen. Sanborn"): ("Sen. Andy Sanborn (R - SD9)", "andy-sanborn-sd-9"),
    ("2017-2018", "HB84", "Sen. Giuda"): ("Sen. Bob Giuda (R - SD2)", "bob-giuda-sd-2"),
    ("2023-2024", "HB221", "Sen. Howard Pearl"): ("Sen. Howard Pearl (R - SD17)",
                                                  "howard-pearl-sd-17"),
    ("2013-2014", "HB350", "Rep. Eaton"): None,
    ("2009-2010", "HB1201", "Sen. Boutin"): None,
}


@check("data", "the built records link a sample of 1999-2024's movers by the seat of the term, "
               "and none of 1989-1998's")
def _older_movers_sample():
    """The built records of the terms in OLDER_MOVERS (site/data/bills-<term>.jsonl.gz): each
    roll call of the bill with that mover carries the label and the page the sample holds --
    a member of both chambers (Gordon, Letourneau, Pearl) by the chamber and seat of the
    term, a member across the 2012 redistricting (Sanborn) by each term's district -- or none,
    where two voters of the term share the name (Eaton) or the term gives no seat in that
    chamber (Boutin, 2010); and 1993-1994, with no ballots, links no mover at all."""
    data = Path("site/data")
    terms = sorted({t for t, _b, _m in OLDER_MOVERS} | {"1993-1994"})
    missing = [t for t in terms if not (data / f"bills-{t}.jsonl.gz").is_file()]
    if missing:
        return "skip", f"site/data has no bills-{missing[0]}.jsonl.gz: the site is not built here"
    import gzip
    got, linked_93 = {}, 0
    for t in terms:
        with gzip.open(data / f"bills-{t}.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                for rc in r.get("rollcalls") or []:
                    k = (t, r.get("id"), rc.get("mover"))
                    if t == "1993-1994":
                        linked_93 += bool(rc.get("mover_m"))
                    elif k in OLDER_MOVERS:
                        m = rc.get("mover_m")
                        got.setdefault(k, set()).add((m["label"], m["slug"]) if m else None)
    bad = [f"{t} {b} {mv!r}: {sorted(got.get((t, b, mv), []), key=str) or 'no such roll call'}, "
           f"not {w!r}" for (t, b, mv), w in OLDER_MOVERS.items() if got.get((t, b, mv)) != {w}]
    assert not bad, "the built records' movers of older terms: " + "; ".join(bad)
    assert not linked_93, f"{linked_93} mover(s) of 1993-1994 linked, a term with no ballots"
    return "ok", (f"{sum(1 for w in OLDER_MOVERS.values() if w)} movers of 1999-2024 linked as the "
                  f"sample holds, {sum(1 for w in OLDER_MOVERS.values() if not w)} left as words, "
                  "none of 1993-1994")


@check("build", "the members a 1999-2024 story names are linked among that term's own voters, "
                "by the seat the term gives them", needs=("build_site_v2",))
def _story_people_of_older_terms(B):
    """The owner, 19 November 2026, "Yes, link them", of a bill's written history as well
    as its roll calls: story_people looks the names up where the term's movers are looked
    up (mover_pool), so a story of 2003-2004 names Rep. Robert Letourneau by Rock 77,
    linked to his one page, though he sat in the Senate after; "Rep. Eaton", two voters
    of 2013-2014, stays words, and "Rep. Richard Eaton" links; build_bills hands the
    story the movers' pool (_story_people_of_a_finished_term holds the call)."""
    def ballot(mid, name, body, year):
        return {"member_id": mid, "name": name, "body": body, "year": year,
                "date": f"{year}-03-01", "party": "R"}
    votes = {"376142": [ballot("376142", "Letourneau, Robert", "H", "2003")],
             "209060": [ballot("209060", "Letourneau, Robert", "S", "2005")],
             "101": [ballot("101", "Eaton, Daniel", "H", "2013")],
             "102": [ballot("102", "Eaton, Richard", "H", "2013")]}
    seats = {"2003-2004": {"376142": "Rep. Robert Letourneau (R - Rock 77)"},
             "2005-2006": {"209060": "Sen. Robert Letourneau (R - SD19)"},
             "2013-2014": {"101": "Rep. Daniel Eaton (D - Ches 9)",
                           "102": "Rep. Richard Eaton (D - Hills 38)"}}
    page = {"id": "209060", "slug": "robert-letourneau-sd-19"}
    people = {"376142": page, "209060": page, "101": {"id": "101", "slug": "daniel-eaton-ches-9"},
              "102": {"id": "102", "slug": "richard-eaton-hills-38"}}
    voters = B.term_voters(votes, seats)
    keep_slugs, keep_spell = dict(B._OWN_SLUG), list(B._SPELLINGS)
    got = {}
    try:
        B._SPELLINGS[:] = [{}]
        for term, text in (("2003-2004", "Rep. Letourneau moved to table; Sen. Letourneau spoke."),
                           ("2013-2014", "Rep. Eaton moved; Rep. Richard Eaton offered an amendment.")):
            B._OWN_SLUG.clear()
            pool, pages = B.mover_pool(term, "2025-2026", {}, {}, people, voters)
            got[term] = {p["text"]: (p["label"], p["slug"])
                         for p in B.story_people([text], pool, pages=pages)}
    finally:
        B._OWN_SLUG.clear()
        B._OWN_SLUG.update(keep_slugs)
        B._SPELLINGS[:] = keep_spell
    want = {"2003-2004": {"Rep. Letourneau": ("Rep. Robert Letourneau (R - Rock 77)",
                                              "robert-letourneau-sd-19")},
            "2013-2014": {"Rep. Richard Eaton": ("Rep. Richard Eaton (D - Hills 38)",
                                                 "richard-eaton-hills-38")}}
    assert got == want, f"an older term's story names {got}, not {want}"
    return "ok", ("a story of 2003-2004 names Rep. Letourneau by Rock 77 and no Senator of that "
                  "term; of 2013-2014 Rep. Richard Eaton, and Rep. Eaton, two of them, as words")


@check("build", "build_site_v2.py itself links an older term's mover and story name, through "
                "main() and build_bills", needs=("build_site_v2",))
def _older_movers_through_main(B):
    """The dry run of 20 November 2026 built the whole site and linked no mover of 1999-2024,
    though every check of the functions passed: build_bills took the pools as `voters`, and
    its loop binds `voters` to a CACR's ballot card on every bill, None on all the rest. So
    this runs the script, main() and all, over the fixture project with one bill of
    2023-2024 added -- HB1442 of that term, a voice vote Rep. Quill moved, and Quill's one
    ballot of 2024, his last -- and reads the record it writes: the roll call and the story
    name Rep. Joe Quill (R - Hills 9), linked to his page. And no name build_bills hands
    mover_pool as the pools is bound again in its body."""
    import ast
    tree = ast.parse(_source(B.__file__))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_bills")
    call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call)
                and getattr(n.func, "id", "") == "mover_pool")
    pools = call.args[5].id if len(call.args) > 5 and isinstance(call.args[5], ast.Name) else ""
    assert pools in [a.arg for a in fn.args.args + fn.args.kwonlyargs], (
        f"build_bills hands mover_pool {pools or 'no pools'} for the voters, not a parameter")
    bound = sorted({getattr(t, "lineno", 0) for n in ast.walk(fn)
                    for t in ((n.targets if isinstance(n, ast.Assign) else
                               [n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign, ast.For,
                                                            ast.NamedExpr)) else []))
                    for x in ast.walk(t) if isinstance(x, ast.Name) and x.id == pools})
    assert not bound, f"build_bills binds {pools}, the voters' pools, again at line(s) {bound}"
    root = Path(tempfile.mkdtemp(prefix="gr-older-main-"))
    try:
        _site_fixture(root)
        d = root / "data"
        bills = json.loads((d / "bills.json").read_text(encoding="utf-8"))
        bills["2023-2024"] = {"HB1442": {
            "designation": "HB 1442", "title": "an entirely different bill", "lsr_num": "0411",
            "lsr_year": "2024", "subject": "Insurance", "chamber": "H",
            "house_committee": "Commerce", "senate_committee": "", "lsr": "2024-0411"}}
        (d / "bills.json").write_text(json.dumps(bills), encoding="utf-8")
        votes = json.loads((d / "member_votes.json").read_text(encoding="utf-8"))
        votes.append({"member_id": "9001", "name": "Quill, Joe", "party": "R",
                      "label": "Quill, Joe(R) Hills 9", "year": "2024", "body": "H",
                      "vote_number": "310", "bill": "HB1442",
                      "question": "Inexpedient to Legislate", "date": "2024-03-06", "vote": "Yea"})
        (d / "member_votes.json").write_text(json.dumps(votes), encoding="utf-8")
        narr = json.loads((root / "narratives.json").read_text(encoding="utf-8"))
        narr["2023-2024"] = {"HB1442": {
            "narrative": "Rep. Quill moved to table it.", "stages": [], "notes": [],
            "unrecognised": [],
            "events": [{"date": "2024-03-06", "type": "floor", "body": "H", "cancelled": False,
                        "action": "Laid on Table", "motion": "MA", "vote_kind": "VV",
                        "mover": "Rep. Quill",
                        "raw": "Rep. Quill Moved Laid on Table, MA VV 03/06/2024"}]}}
        (root / "narratives.json").write_text(json.dumps(narr), encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_site_v2.py"), "--data", "data",
                  "--out", "site", "--segments", "work"], cwd=root, capture_output=True,
                 text=True, timeout=300)
        assert r.returncode == 0, f"build_site_v2.py failed on the fixture: {r.stderr[-600:]}"
        p = root / "site" / "bills" / "2024" / "HB1442.json"
        assert p.is_file(), "the build wrote no record of HB1442 of 2023-2024"
        rec = json.loads(p.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    quill = {"label": "Rep. Joe Quill (R - Hills 9)", "slug": "joe-quill-hills-9"}
    moved = [x.get("mover_m") for x in rec.get("rollcalls") or [] if x.get("mover") == "Rep. Quill"]
    assert moved == [quill], f"the built record's mover of 2023-2024 is {moved}, not [{quill}]"
    told = rec.get("story_people") or []
    assert told == [{"text": "Rep. Quill", **quill}], f"the built story names {told}"
    return "ok", (f"build_bills hands mover_pool its parameter {pools}, never bound again; the "
                  "script's own build links 2023-2024's Rep. Quill on the roll call and in the "
                  "story as Rep. Joe Quill (R - Hills 9)")


@check("build", "the bill-text fetch saves only the bill it asked for, and stops when told no",
       needs=("fetch_legislation",))
def _legislation_fetch(FL):
    """Thirty-one thousand requests to an address that has blocked us twice.

    Every behaviour here was missing from fetch_legislation.py on 10
    September, found by reading it before the full run rather than during:
    2023-2024 addresses that named another bill for 615 bills, a dropped
    connection that crashed the run with no refusal recorded, 404s asked for
    again on every run, and the firewall's block page saved as a bill. None
    of it can be tested against the real server without being the problem
    it guards against, so a fake server stands in: no request leaves here.

    What each run tells the person is read here, not left in preflight's own
    log: on the weekly of 23 November 2026 this check passed, and its fake
    run's "Stopping; refusal.py holds it." stood among the lines GitHub's
    public log showed of the failed step, as if the General Court had
    refused a fetch that never ran.
    """
    import contextlib
    import http.client
    import io
    import urllib.error
    import refusal
    here = Path(".").resolve()
    root = Path(tempfile.mkdtemp())
    saved = (os.getcwd(), FL.urlopen, FL.time.sleep)
    try:
        os.chdir(root)
        FL.time.sleep = lambda s: None
        # --- where each era's text lives
        u, how = FL.address(2023, "HB42", {"text_pdf": "billText.aspx?id=32&sy=2023"})
        assert how == "billText" and "id=32&" in u and "sy=2023" in u, u
        assert FL.address(1996, "HB1025", {})[0].endswith("/1996/HB1025.htm")
        assert FL.address(2014, "HB1101", {})[0].endswith("/2014/HB1101.html")
        floor = {"lsr_year": "1990", "lsr_num": "9055"}
        assert FL.is_floor_resolution("HR55", floor)
        assert not FL.is_floor_resolution("HB1", {"lsr_year": "1989", "lsr_num": "9100"})

        asked = []

        def server(answers):
            def op(req, timeout=30):
                asked.append(req.full_url)
                a = answers.pop(0)
                if isinstance(a, Exception):
                    raise a
                return io.BytesIO(a.encode("utf-8"))
            return op

        # Longer than 200 bytes, which is where a saved page counts as held.
        page = lambda lsr: (f"<html>2019 SESSION {lsr} 10/04 HOUSE BILL 5 "
                            "AN ACT relative to things. SPONSORS: Rep. A "
                            "ANALYSIS This bill does a thing. " + "x " * 120
                            + "</html>")
        rec = {"lsr_year": "2019", "lsr_num": "789"}
        # Right bill: saved.
        FL.urlopen = server([page("19-0789")])
        assert FL.fetch(2019, "HB5", 0, rec)[0] == "saved"
        assert (root / "legislation" / "2019" / "HB0005.html").exists()
        assert FL.fetch(2019, "HB5", 0, rec)[0] == "cached"
        # Another bill's page: not saved, and not asked for twice.
        FL.urlopen = server([page("19-0123")])
        assert FL.fetch(2019, "HB6", 0, rec)[0] == "wrong bill"
        assert not (root / "legislation" / "2019" / "HB0006.html").exists()
        # A 404: on the gone-list, and the next run does not ask.
        n = len(asked)
        FL.urlopen = server([urllib.error.HTTPError("u", 404, "nf", {}, None)])
        assert FL.fetch(2019, "HB7", 0, rec)[0] == "missing"
        assert FL.fetch(2019, "HB7", 0, rec)[0] == "gone"
        assert len(asked) == n + 1, "a 404 was asked for twice"
        # The refusals.
        FL.urlopen = server([http.client.RemoteDisconnected("closed")])
        assert FL.fetch(2019, "HB8", 0, rec)[0] == "dropped"
        FL.urlopen = server(["<h1>Web Page Blocked</h1> Attack ID: 1234"])
        assert FL.fetch(2019, "HB9", 0, rec)[0] == "refused"
        assert not (root / "legislation" / "2019" / "HB0009.html").exists()
        FL.urlopen = server([urllib.error.HTTPError("u", 403, "no", {}, None)])
        assert FL.fetch(2019, "HB10", 0, rec)[0] == "refused"
        # A floor resolution is never asked.
        n = len(asked)
        assert FL.fetch(1990, "HR55", 0, floor)[0] == "floor" and len(asked) == n

        # A run: two dropped connections end it, and the refusal outlives it.
        class A:
            lo, hi, note, delay, budget, stop_refused = 2019, 2019, "", 0, 50, 2
            newest_first = False
        # Newest first, when asked: a run over 2018 and 2019 with room for one
        # request asks 2019's bill.
        class B(A):
            budget, newest_first = 1, True

        def ran(*a):
            """FL.run's status and what it said, which stays out of preflight's log."""
            said = io.StringIO()
            with contextlib.redirect_stdout(said):
                rc = FL.run(*a)
            return rc, said.getvalue()
        FL.urlopen = server([page("19-0041")])
        rc, said = ran(B, {2018: ["HB40"], 2019: ["HB41"]},
                       {(2018, "HB40"): {"lsr_year": "2018", "lsr_num": "40"},
                        (2019, "HB41"): {"lsr_year": "2019", "lsr_num": "41"}}, 2)
        assert "/2019/HB0041" in asked[-1], f"newest first asked {asked[-1]}"
        assert rc == 0 and "budget of 1 reached" in said, (
            f"a run that met its budget gave {rc} and said {said!r}")
        by = {(2019, f"HB{i}"): {"lsr_year": "2019", "lsr_num": str(i)}
              for i in range(20, 26)}
        FL.urlopen = server([http.client.RemoteDisconnected("x")] * 2)
        rc, said = ran(A, {2019: [f"HB{i}" for i in range(20, 26)]}, by, 6)
        assert rc == 2, f"two dropped connections gave status {rc}, not 2"
        assert "2 dropped connections" in said and "refusal.py holds it" in said, (
            f"two dropped connections said {said!r}")
        assert refusal.MARK.exists(), "the refusal was not recorded"
        # And with a refusal on file, nothing more is asked -- and the record
        # is left as it is, not overwritten with this run's name.
        n = len(asked)
        before = refusal.MARK.read_text(encoding="utf-8")
        assert FL.fetch(2019, "HB30", 0, rec)[0] == "halted" and len(asked) == n
        assert refusal.MARK.read_text(encoding="utf-8") == before
        refusal.MARK.unlink()
        # What urllib actually raises. A reset at connect time arrives WRAPPED
        # in a URLError, and was an ordinary failure until the 11th.
        import socket
        for exc, want in [
                (urllib.error.URLError(ConnectionResetError(10054, "reset")), "dropped"),
                (urllib.error.URLError(socket.timeout("timed out")), "dropped"),
                (TimeoutError("read timed out"), "dropped"),
                (urllib.error.HTTPError("u", 503, "busy", {}, None), "refused"),
                (urllib.error.HTTPError("u", 302, "moved", {}, None), "failed")]:
            FL.urlopen = server([exc])
            got = FL.fetch(2019, f"HB{50 + len(asked)}", 0, rec)[0]
            assert got == want, f"{exc!r} read as {got}, not {want}"
        # An empty 200 is not a bill, and is not saved.
        FL.urlopen = server(["<html><body></body></html>"])
        assert FL.fetch(2019, "HB90", 0, rec)[0] == "empty"
        assert not (root / "legislation" / "2019" / "HB0090.html").exists()
        # The lane gone: nothing asked.
        class Gone:
            def still(self):
                return False
        FL.HOLD, n = Gone(), len(asked)
        assert FL.fetch(2019, "HB91", 0, rec)[0] == "halted" and len(asked) == n
        FL.HOLD = None
        # A gone-list that will not read stops the run rather than being
        # rewritten from nothing.
        good = FL.GONE.read_text(encoding="utf-8")
        FL.GONE.write_text("{not json", encoding="utf-8")
        try:
            FL.fetch(2019, "HB92", 0, rec)
            raise AssertionError("an unreadable gone-list was read as empty")
        except SystemExit:
            pass
        FL.GONE.write_text(good, encoding="utf-8")
        # Two wrong bills in a run end it.
        FL.urlopen = server([page("19-0001"), page("19-0002")])
        by = {(2019, f"HB{i}"): {"lsr_year": "2019", "lsr_num": "700"}
              for i in range(40, 44)}
        rc, said = ran(A, {2019: [f"HB{i}" for i in range(40, 44)]}, by, 4)
        assert rc == 3, f"two wrong bills gave status {rc}, not 3"
        assert said.count("WRONG BILL: 2019 HB4") == 2 and "Stopping for a person to look" in said, (
            f"two wrong bills said {said!r}")
        return "ok", ("right bill saved, wrong bill refused, 404 asked once, "
                      "dropped/403/block page stop it, floor resolutions skipped; each run says why "
                      "it stopped, and none of it reaches preflight's log")
    finally:
        os.chdir(saved[0])
        FL.urlopen, FL.time.sleep = saved[1], saved[2]
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a sponsor label is read even where the page mistypes its colon",
       needs=("fetch_legislation",))
def _sponsor_label(FL):
    """2022 HB 52's page prints "SPONSORSF", and its sponsor was read as none.

    Two of the 7,761 saved pages mistype the label the sponsor line hangs off,
    and both printed a sponsor nobody could see: 2020 SB 222 drops the colon
    and 2022 HB 52 puts an F where it belongs -- "SPONSORSF<tab>Rep. B.
    Griffin, Hills. 6", which is the General Court's own document and not a
    decoding fault. The parser required the colon, so both bills showed no
    sponsor at all. A fixture and not the real pages, so this holds wherever
    preflight runs; the markup is copied from 2022 HB 52's bytes.
    """
    body = ('<p class="x"><span>AN ACT\tapportioning congressional districts.'
            '</span></p><p class="x"><span>{lab}\tRep. B. Griffin, Hills. 6'
            '</span></p><p class="x"><span>COMMITTEE:\tSpecial Committee on '
            'Redistricting</span></p><p class="x"><span>ANALYSIS</span></p>'
            '<p class="x"><span>This bill apportions the districts.</span></p>')
    seen = []
    for lab in ("SPONSORS:", "SPONSORS", "SPONSORSF"):
        got = FL.parse(body.format(lab=lab))
        assert got.get("sponsors") == "Rep. B. Griffin, Hills. 6", \
            f"{lab!r} gave sponsors {got.get('sponsors')!r}"
        assert got.get("committee") == "Special Committee on Redistricting", \
            f"{lab!r} gave committee {got.get('committee')!r}"
        seen.append(lab)
    # AND NOT ANY WORD THAT STARTS THAT WAY. The label is the word, an optional
    # colon or single stray letter, and then the whitespace the field begins
    # after -- so a longer word swallowing the next sentence is what the
    # whitespace rules out, and lower case is what keeps a title's own
    # "sponsors" from being read as a label.
    for hay in ('<p>AN ACT\trelative to SPONSORSHIP of legislation.</p>',
                '<p>HOUSE RESOLUTION NO. 1</p>'
                '<p>RESOLVED, that the House thank its sponsors and adjourn.</p>'):
        assert not FL.parse(hay).get("sponsors"), hay
    return "ok", ", ".join(seen) + " all read; SPONSORSHIP and lower case do not"


@check("build", "a vote on an amendment names it only when the pairing is certain",
       needs=("build_site_v2",))
def _amendment_votes(BS):
    """vote_chronology pairs a day's roll calls with the docket's, in order.

    "Adopt Amendment" is what 196 of the 420 amendment votes say, and the
    number is in none of them: 0 of 420 question_raw values carry one. The
    docket lists floor actions in the order they happened and names the
    amendment in each, and the roll call file numbers its votes in that same
    order, so the two are paired within a chamber and a day.

    THE RULE THIS GUARDS IS THE REFUSAL. Where the docket shows fewer roll
    calls that day than the roll call file does, something is missing from one
    of them and lining them up would put the wrong number beside the wrong
    vote -- so nothing is claimed.

    It is guarded because a weaker rule was written on top of it on the 12th
    and had to come out. On 8 January 2026 the House took three amendment roll
    calls on HB 675 (numbers 35, 36 and 37) against one docket line, so this
    function named 35 and 37 from a day where the counts DID agree and left 36
    alone. The addition saw 36 as "the only unnamed amendment vote that day",
    found a single candidate, and gave it 2025-3013h -- which 35 already had.
    One amendment, two votes, and nothing on the page would have looked wrong.

    Naming the wrong amendment is worse than naming none: the page cites a
    document that is not what was voted on.
    """
    def ev(date, body, raw, vk="RC"):
        return {"date": date, "body": body, "raw": raw, "vote_kind": vk}

    def rc(number, date, body, q="Adopt Amendment"):
        return {"number": number, "date": date, "body": body, "question": q}

    # Counts agree: paired in order, and each vote gets its own amendment.
    rcs = [rc(1, "01/08/2026", "H"), rc(2, "01/08/2026", "H")]
    narr = {"events": [ev("01/08/2026", "H", "Amendment # 2026-0001h, RC 200-100"),
                       ev("01/08/2026", "H", "Amendment # 2026-0002h, RC 190-110")]}
    _order, names = BS.vote_chronology(rcs, narr)
    got = [names.get(("H", 1)), names.get(("H", 2))]
    assert got == ["2026-0001h", "2026-0002h"], got
    assert len(set(x for x in got if x)) == len(
        [x for x in got if x]), ("one amendment named twice", got)

    # HB 675: three votes, one docket line. Nothing is claimed for any of them.
    rcs = [rc(35, "01/08/2026", "H"), rc(36, "01/08/2026", "H"),
           rc(37, "01/08/2026", "H")]
    narr = {"events": [ev("01/08/2026", "H", "Amendment # 2025-3013h, RC 184-168")]}
    _order, names = BS.vote_chronology(rcs, narr)
    assert not names, ("the counts disagree, so nothing may be claimed", names)

    # A voice vote in the docket is not a roll call and is not paired with one.
    rcs = [rc(9, "02/05/2026", "H")]
    narr = {"events": [ev("02/05/2026", "H", "Amendment # 2026-0009h, VV", vk="VV"),
                       ev("02/05/2026", "H", "Amendment # 2026-0010h, RC 5-4")]}
    _order, names = BS.vote_chronology(rcs, narr)
    assert names.get(("H", 9)) == "2026-0010h", names

    # The other chamber's business that day is not this chamber's.
    rcs = [rc(4, "03/03/2026", "S")]
    narr = {"events": [ev("03/03/2026", "H", "Amendment # 2026-0500h, RC 1-2")]}
    _order, names = BS.vote_chronology(rcs, narr)
    assert not names, names
    return "ok", ("paired in order where the counts agree, and nothing claimed "
                  "where they do not -- the HB 675 case")


@check("build", "a guessed topic is withheld rather than guessed twice",
       needs=("topics",))
def _topic_model(TP):
    """29,449 bills have no topic and this guesses one, which makes the way it
    DECLINES the part worth guarding.

    Scored on a held-out half of the only term the General Court labelled, it
    is right 60.9% of the time over 46 topics. At the threshold it publishes
    at, it is right 74.2% of the time on the bills it places and says
    Miscellaneous for the rest. A wrong topic is worse than none: a reader
    filtering by Elections and not finding an elections bill has been misled
    rather than underserved.

    Two ways that goes wrong silently. A bill whose words the model has never
    seen would otherwise be handed the commonest topic, because with no
    evidence the prior alone decides -- and the answer would look exactly like
    a real one. And the split that produces the score has to be the same split
    every run, or the number moves on its own and nobody can tell tuning from
    noise.
    """
    rows = [
        ("HB1", {"bill": "HB1", "title": "relative to school district funding "
                 "for pupils", "house_committee": "Education Funding",
                 "subject": "Education - Finance"}),
        ("HB2", {"bill": "HB2", "title": "relative to absentee ballots and "
                 "voter registration", "house_committee": "Election Law",
                 "subject": "Elections"}),
        ("HB3", {"bill": "HB3", "title": "relative to the registration of "
                 "motor vehicles", "house_committee": "Transportation",
                 "subject": "Motor Vehicles"}),
        ("HB4", {"bill": "HB4", "title": "relative to ballots cast by voters "
                 "at an election", "house_committee": "Election Law",
                 "subject": "Elections"}),
    ]
    model = TP.train(rows)

    # Evidence it has seen, and plenty of it: placed, and placed correctly.
    clear = {"bill": "HB9", "title": "relative to absentee ballots for voters",
             "house_committee": "Election Law"}
    topic, margin, _second = TP.classify(model, clear, threshold=0.5)
    assert topic == "Elections", (topic, margin)
    assert margin > 0

    # THE SAME BILL, WITH THE BAR RAISED ABOVE ITS MARGIN: withheld.
    topic, _m, _s = TP.classify(model, clear, threshold=margin + 1)
    assert topic == TP.MISC, topic

    # NOTHING THE MODEL HAS EVER SEEN. Not the commonest topic -- which is what
    # the prior alone would give, and it would be indistinguishable from a real
    # answer on the page.
    unseen = {"bill": "HB99", "title": "zzzq wibblefish quonked",
              "house_committee": "Committee On Nothing At All"}
    topic, margin, _s = TP.classify(model, unseen, threshold=0.0)
    assert topic == TP.MISC, ("no evidence must mean Miscellaneous", topic)
    assert margin == 0.0, margin

    # The split is a function of the bill id and nothing else, so the score is
    # the same score every run.
    assert TP.split_half("HB1442") == TP.split_half("HB1442")
    halves = {TP.split_half(f"HB{i}") for i in range(400)}
    assert halves == {0, 1}, "the split puts every bill in one half"

    # Miscellaneous is not one of the General Court's topics and must never be
    # confused for one; the model may only ever answer a topic it was taught.
    assert TP.MISC not in model["logprior"]
    for rec in (clear, unseen, rows[0][1]):
        t, _m, _s = TP.classify(model, rec, threshold=0.0)
        assert t == TP.MISC or t in model["logprior"], t
    return "ok", ("placed on evidence, withheld above its margin, and "
                  "Miscellaneous where it has seen nothing")


@check("build", "a title rule answers only where the General Court's own convention does",
       needs=("topic_model",))
def _topic_title_rules(TM):
    """The title rules of 23 October 2026 (topic_model's rules section), and
    the proposals beside them.

    Each rule is a convention the General Court follows in the term it
    labelled, and each is allowed exactly as far as that convention goes. A
    constitutional amendment is no longer CACR before the model asks anything
    (CACR is retired, 18 November 2026: _cacr_takes_its_subject); a
    commemoration is Memorials ONLY where the model would have said
    Miscellaneous -- never over an answer it gave. Three ways that goes wrong
    quietly: a rule that fires over a confident answer and moves a bill the
    model had right; a pattern that reads "designated caregivers", a "3-year
    term" or a bill about "adopting rules" as a commemoration or as the
    chamber's business; and "memorializing Congress", the older sense of
    petitioning it, read as a memorial.

    And the proposals are the owner's to turn on: each must name a topic that
    either the General Court's list has or that carries its own code, and
    while one is off it must change nothing -- a retired "Regular Meeting"
    stays retired.
    """
    rows = [
        ("HB1", {"bill": "HB1", "title": "relative to absentee ballots for voters",
                 "house_committee": "Election Law"}, "", "Elections"),
        ("HB2", {"bill": "HB2", "title": "relative to the registration of motor vehicles",
                 "house_committee": "Transportation"}, "", "Motor Vehicles"),
        ("CACR1", {"bill": "CACR1", "title": "relating to the governor"}, "", "CACR"),
        ("HR1", {"bill": "HR1", "title": "honoring a retiring clerk"}, "", "Memorials"),
        ("HR2", {"bill": "HR2", "title": "urging Congress to fund roads"}, "",
         "State Government"),
    ]
    model = TM.Model(rows, {}, seed_names=0.0)
    W = {f: 1.0 for f in TM.FAMILIES}
    placed = {"m": {}, "P": {}, "floors": {"text": 0.0, "notext": 0.0},
              "regimes": {r: {"W": W, "lp": 1.0, "temp": 1.0} for r in ("text", "notext")}}
    declined = dict(placed, floors={"text": 1.01, "notext": 1.01})

    # No rule for a CACR since 18 November 2026: the model answers it as any other bill.
    cacr = {"bill": "CACR9", "title": "relating to absentee ballots for voters",
            "house_committee": "Election Law"}
    assert TM.answer(model, cacr, "", placed) == TM.answer(model, cacr, "", placed, rules=False), \
        TM.answer(model, cacr, "", placed)
    assert TM.answer(model, cacr, "", placed)[2] == "notext", "a rule answered a CACR"

    # Below the floor only. Placed, the model's answer stands.
    hon = {"bill": "HR9", "title": "honoring the absentee ballot clerks of Concord",
           "house_committee": "Election Law"}
    got = TM.answer(model, hon, "", placed)
    assert got[2] == "notext" and got[0] == TM.answer(model, hon, "", placed, rules=False)[0], got
    assert TM.answer(model, hon, "", declined)[:3] == ("Memorials", 1.0, "rule:ceremony")
    wash = {"bill": "HCR3", "title": "memorializing Congress to fund roads"}
    assert not TM.is_ceremony(wash["title"]), "memorializing Congress is a petition"
    assert TM.is_to_washington(wash["title"])
    plain = {"bill": "HB7", "title": "relative to the registration of motor vehicles"}
    assert TM.answer(model, plain, "", declined)[0] == TM.MISC, "no rule, no answer"
    for t in ("naming a bridge in the city of Keene after Charles Redfern.",
              "recognizing the second Thursday in October as children's environmental health day.",
              "memorializing former Representative Ronald R. Laurion of Rochester."):
        assert TM.is_ceremony(t), t
    for t in ("permitting qualifying patients and designated caregivers to cultivate cannabis.",
              "enabling towns to establish a 3-year term for town moderators.",
              "allowing municipalities to designate sections of state highways for all terrain vehicles.",
              "establishing a 4-year pilot program to improve rail trails."):
        assert not TM.is_ceremony(t), t

    assert TM.justices_bill("requesting an opinion of the justices concerning the "
                            "constitutionality of HB 1135.") == "HB1135"
    assert TM.justices_bill("requesting an opinion of the justices on HB 536, as amended.") == "HB536"
    assert TM.justices_bill("requesting an opinion of the justices on the scope of part II") == ""

    # THE PROPOSALS. Each a topic the site can file under, and each inert while
    # off. A proposal with no code of its own must name one of the site's
    # additions or a name of the General Court's list (SubjectCodes.txt: LEG,
    # FED and STG), whose code apply() reads from data/subjects.json.
    gc_names = {"Legislature", "Federal and International Relations", "State Government"}
    assert set(TM.ENABLED) <= set(TM.PROPOSALS), set(TM.ENABLED) - set(TM.PROPOSALS)
    for key, p in TM.PROPOSALS.items():
        assert p["where"] in ("first", "decline"), (key, p["where"])
        assert p.get("code") or p["topic"] in TM.ADDED_CODES or p["topic"] in gc_names, \
            f"{key}: {p['topic']} would be filed under no code"
    rm = {"bill": "HR1", "title": "Adopting the rules of the 2024 session for the 2025-2026 biennium."}
    vet = {"bill": "HB291", "title": "removing veterinarians from the requirements of adopting "
                                     "rules for prescribing opioids."}
    saved = set(TM.ENABLED)
    try:
        TM.ENABLED.clear()
        assert TM.remap_gold("Regular Meeting", rm) == "Regular Meeting", "off must be off"
        assert TM.proposal_for(rm, "first") == ""
        assert TM.answer(model, wash, "", declined)[0] == TM.MISC, "off must be off"
        # A "decline" proposal answers below the floor, and only there.
        TM.ENABLED.add("resolutions to Washington")
        assert TM.answer(model, wash, "", declined)[:3] == (
            "State Government", 1.0, "rule:resolutions to Washington")
        assert TM.answer(model, hon, "", placed)[2] == "notext"
        TM.ENABLED.clear()
        TM.ENABLED.add("legislative organization")
        assert TM.remap_gold("Regular Meeting", rm) == TM.LEGISLATIVE_ORGANIZATION
        assert TM.LEGISLATIVE_ORGANIZATION in TM.new_vocabulary()
        assert TM.proposal_for(vet, "first") == "", "a bill about rules is not the chamber's business"
    finally:
        TM.ENABLED.clear()
        TM.ENABLED.update(saved)
    return "ok", ("no rule for a CACR; a commemoration only below the floor; the proposals inert "
                  "while off")


@check("build", "Constitutional Amendments is no topic: a CACR, bill or request, takes the topic its "
                "subject gives, and the site's topics do not name it",
       needs=("topic_model", "build_site_v2", "request_topics", "tag_rules"))
def _cacr_takes_its_subject(TM, B, RT, TR):
    """The owner, 18 November 2026: constitutional amendments "are inherently covered by the CACR
    title and it prevents them from being searchable by their individual topics." CACR is
    retired (topic_model.RETIRED): the topic model learns no CACR class and a CACR it answers
    takes the topic of its subject; the General Court's CACR on a bill names no site topic
    (vocabulary_of, unify_vocabulary), so the model's answer stands in for it
    (merge_guessed_topics, as for Regular Meeting); the request model (request_topics.train_on)
    learns no CACR either; and tag_rules' list of the site's topics does not name it."""
    import contextlib
    import io
    assert "CACR" in TM.RETIRED, "CACR is a topic again"
    words = {"Elections": ["ballot", "voter", "election", "polling"],
             "Motor Vehicles": ["vehicle", "driver", "registration", "license"]}
    lab = {}
    for i in range(12):
        for t, w in words.items():
            lab[f"HB{len(lab) + 1}"] = {"bill": f"HB{len(lab) + 1}", "subject": t,
                                         "title": f"relative to {w[i % 4]} {w[(i + 1) % 4]} matters."}
    for i in range(12):
        lab[f"CACR{i + 1}"] = {"bill": f"CACR{i + 1}", "subject": "CACR",
                               "title": "relating to ballot voter election. Providing that the constitution."}
    W = {f: 1.0 for f in TM.FAMILIES}
    cfg = {"m": {}, "P": {}, "seed_names": 0.0, "floors": {"text": 0.0, "notext": 0.0},
           "regimes": {r: {"W": W, "lp": 1.0, "temp": 1.0} for r in ("text", "notext")}}
    model = TM.fit({TM.base.LABELLED_TERM: lab}, {}, cfg, "B")
    assert "CACR" not in model.tix, f"the model learned CACR: {model.topics}"
    got = TM.answer(model, {"bill": "CACR40", "title": "relating to the registration of vehicles."}, "", cfg)
    assert got[0] == "Motor Vehicles", f"a CACR about vehicles was answered {got}"
    assert B.vocabulary_of("CACR", {"title": "relating to the governor."}, "CACR1") is None
    bills = {"2025-2026": {"CACR1": {"title": "relating to the governor.", "subject": "CACR",
                                     "subject_code": "CACR"}}}
    with contextlib.redirect_stdout(io.StringIO()):
        B.unify_vocabulary(bills)
    assert bills["2025-2026"]["CACR1"]["subject"] == "", bills
    rt = RT.train_on({"2025-2026": lab}, subjects={}, codes={})
    assert "CACR" not in rt["logprior"] and rt["n"] == 24 * RT.CURRENT_WEIGHT, (
        f"the request model learned CACR: {sorted(rt['logprior'])}, {rt['n']} rows")
    assert "Constitutional Amendments" not in TR.SITE_TOPICS, "tag_rules lists the retired topic"
    if TM.base.codes():
        assert "CACR" not in TM.new_vocabulary(), "the model's vocabulary names CACR"
    return "ok", ("CACR retired: the model and the request model learn no CACR, a CACR about vehicles "
                  "is Motor Vehicles, the General Court's CACR names no site topic, and the list of "
                  "the site's topics does not name Constitutional Amendments")


@check("build", "an archived bill takes the General Court's own subject code as its topic, through the "
                "site's categories: a folded or retired name goes where the current term's goes, an "
                "unnamed code is left to the model, and the current term is not touched",
       needs=("build_site_v2", "official_topics"))
def _official_codes_for_the_archive(B, OT):
    """Stage 0 of reports/topics-as-tags-design-2026-11.md. Eighteen terms showed
    the topic model's guess although the General Court's own code is on disk;
    official_topics.adopt gives the code's name, and unify_vocabulary then does
    to it what it does to 2025-2026's labels, so there is one mapping."""
    subjects = {"PAR": {"name": "Parks and Recreation"}, "ELE": {"name": "Elections"},
                "AGE": {"name": "Agency Appropriations"}, "CCP": {"name": "Crimes, Crim.Proc. & Corr."}}
    codes = {(2001, 1): ("PAR", "HB1"), (2001, 2): ("ELE", "HB2"), (2001, 3): ("PUP", "HB3"),
             (2001, 4): ("ELE", "HB999"), (2001, 5): ("AGE", "HB5"), (2001, 6): ("", "HB6"),
             (2001, 7): ("CCP", "HB7"), (2025, 1): ("ELE", "HB1")}

    def rec(n, title, **kw):
        return {"title": title, "lsr_year": "2001", "lsr_num": str(n), **kw}
    bills = {"2001-2002": {"HB1": rec(1, "relative to the state park fee"),
                           "HB2": rec(2, "relative to voter checklists"),
                           "HB3": rec(3, "relative to wells"),
                           "HB4": rec(4, "relative to ballots"),
                           "HB5": rec(5, "making an appropriation for the agency"),
                           "HB6": rec(6, "relative to nothing in particular"),
                           "HB7": rec(7, "relative to theft"),
                           "HB8": rec(8, "relative to already labelled", subject="Animals")},
             "2025-2026": {"HB1": {"title": "t", "lsr_year": "2025", "lsr_num": "1"}}}
    before = json.dumps(bills["2025-2026"], sort_keys=True)
    tally = OT.adopt(bills, subjects, codes=codes)
    old = bills["2001-2002"]
    assert old["HB1"]["subject"] == "Parks and Recreation" and old["HB1"]["subject_source"] == "general court"
    assert not old["HB3"].get("subject"), "a code with no name on disk was guessed at"
    assert not old["HB4"].get("subject"), "a code the database files under another bill number was taken"
    assert not old["HB6"].get("subject"), "a bill with no code was given one"
    assert old["HB8"]["subject"] == "Animals", "a subject already on the record was written over"
    assert json.dumps(bills["2025-2026"], sort_keys=True) == before, "the current term was touched"
    assert tally["filled"] == 4 and tally["a code with no name on disk"] == 1, dict(tally)
    import contextlib
    import io
    # The split of a topic in two reads the statutes a bill changes off this disk's
    # rsa_citations.json by its term and number: none, for these made-up records.
    saved = list(B._CHANGES)
    B._CHANGES[:] = [{}]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            B.unify_vocabulary(bills)
    finally:
        B._CHANGES[:] = saved
    got = {b: r.get("subject") for b, r in old.items()}
    assert got["HB1"] == "Environment - Conservation", "Parks and Recreation was revived, not folded"
    assert got["HB5"] == "State Government", "Agency Appropriations was revived, not folded"
    assert got["HB7"] == "Crimes and Criminal Procedure", got["HB7"]
    assert got["HB2"] == "Elections" and got["HB8"] == "Animals", got
    return "ok", "named codes fill, folds and wording apply, unnamed, mismatched and current-term bills are left alone"


@check("data", "every official subject code on disk maps to a site category or is listed as unnamed, and "
               "the current term's topics are what the General Court gave", needs=("build_site_v2", "official_topics"))
def _official_codes_total(B, OT):
    """The mapping is total over the data on disk: each code in PastLegislation
    is named in data/subjects.json and lands in a category the site has, or is
    one of the older codes OT.unnamed lists for the General Court to name. A new
    code in a later dump is neither, and fails here until it is one or the
    other."""
    import contextlib
    import io
    codes = OT.read_codes()
    if not codes or not Path("data/bills.json").exists() or not Path("data/subjects.json").exists():
        return "skip", "no db/past dump or data/bills.json here"
    subjects = json.loads(Path("data/subjects.json").read_text(encoding="utf-8"))
    names = OT.names_of(subjects)
    site = ((set(B.TM.new_vocabulary()) - set(B.TM.SPLITS)) | set(B.TOPIC_WORDS.values())
            | B.TM.split_names())
    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    cur = max(bills)
    unmapped, unnamed = [], set()
    for code in {c for c, _n in codes.values() if c}:
        if not names.get(code):
            unnamed.add(code)
            continue
        for title in ("relative to something", "establishing a committee to study it",
                      "relative to rental housing"):
            cat = B.vocabulary_of(names[code], {"title": title}, "HB1")
            if cat is not None and cat not in site:
                unmapped.append((code, names[code], cat))
    assert not unmapped, f"official codes that land in no site category: {unmapped[:5]}"
    listed = set(OT.unnamed(bills, subjects, codes=codes))
    carried = {OT.official_of(r, b, codes) for t, d in bills.items() if t != cur for b, r in d.items()}
    missing = sorted((unnamed & carried) - listed)
    assert not missing, f"codes with no name that unnamed() does not list: {missing}"
    kept = {b: (r.get("subject"), r.get("subject_code")) for b, r in bills[cur].items()}
    with contextlib.redirect_stdout(io.StringIO()):
        OT.adopt(bills, subjects, codes=codes)
    assert kept == {b: (r.get("subject"), r.get("subject_code")) for b, r in bills[cur].items()}, \
        f"{cur}'s topics changed"
    return "ok", f"{len(codes):,} LSRs, {len(unnamed)} unnamed codes listed, {cur} unchanged"


@check("build", "the topic proposals the owner turned on reach the General Court's own labels "
                "too: this term's housekeeping resolutions under Legislature, a study commission "
                "under Study", needs=("build_site_v2", "topic_model"))
def _proposals_reach_labelled_bills(B, TM):
    """The owner's review of 24 October 2026 turned on three proposals
    (topic_model.ENABLED). The preview built from it had them in every
    archived term and not in 2025-2026: HR 1-4 and SR 5 of this term carry
    the General Court's "Regular Meeting", which the site retires, and
    build_site_v2.unify_vocabulary asked the housekeeping rule about a record
    keyed by its number but not carrying it, so the rule, which reads the
    number, never matched and the label was blanked. It fails if a labelled
    bill of the current term is asked without its number again, on the real
    titles of that day."""
    if "housekeeping into Legislature" not in TM.ENABLED:
        return "skip", "the housekeeping proposal is off"
    bills = {"2025-2026": {
        "HR1": {"title": "Adopting the rules of the 2024 session for the 2025-2026 biennium.",
                "subject": "Regular Meeting"},
        "SR5": {"title": "RESOLVED, that the Senate meet in Joint Convention with the House of "
                         "Representatives for the purpose of electing a Secretary of State.",
                "subject": "Regular Meeting"},
        "HB291": {"title": "removing veterinarians from the requirements of adopting rules for "
                           "prescribing opioids.", "subject": "Regular Meeting"},
        "HB106": {"title": "establishing a commission to determine the monetary costs of climate "
                           "damage to the state of New Hampshire and making an appropriation therefor.",
                  "subject": "Environment - Conservation"}}}
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        B.unify_vocabulary(bills)
    got = {b: r.get("subject") for b, r in bills["2025-2026"].items()}
    want = {"HR1": "Legislature", "SR5": "Legislature", "HB291": "",
            "HB106": "Study Committees and Commissions"}
    if "study committees, wider" not in TM.ENABLED:
        want.pop("HB106")
        got.pop("HB106")
    assert got == want, f"the proposals on this term's labelled bills: {got}, not {want}"
    assert "bill" not in bills["2025-2026"]["HR1"], "the vocabulary step wrote a number into the record"
    return "ok", "HR 1 and SR 5 under Legislature, a bill about rules not, HB 106 under Study"


# THE TWO TOPICS SPLIT IN TWO (the owner, 16 November 2026), on real bills: each
# case is a bill of the record of 7 November 2026, its title and the chapters
# rsa_citations.json says it changes, with what the rule makes of it and why.
_SPLIT_CASES = (
    # Crimes, Crim.Proc. & Corr.: the chapters first, then the title
    ("2009-2010/HB1658", "C", "relative to the adult parole board.", ("21-H", "651-A"), "Corrections", "chapters"),
    ("1989-1990/HB276", "C", "relative to the penalty for assaulting a law enforcement officer.", ("631", "651"),
     "Crimes and Criminal Procedure", "chapters"),
    ("2009-2010/HB1680", "C", "establishing the crime of aggravated harassment by an inmate.", ("642",),
     "Crimes and Criminal Procedure", "chapters"),
    ("2011-2012/HB1654", "C", "relative to earned time credits for inmates participating in rehabilitative "
     "programming.", ("651", "651-A"), "Corrections", "chapters"),
    ("2025-2026/HB1236", "C", "relative to the use of body-worn cameras in county departments of corrections.",
     ("30-B",), "Corrections", "chapters"),
    ("2017-2018/HB282", "C", "relative to a prisoner's participation in the work release program.", ("651",),
     "Corrections", "title"),
    ("2013-2014/HB447", "C", "relative to annulment of criminal records.", ("651",), "Crimes and Criminal Procedure",
     "title"),
    ("1995-1996/HB316", "C", "relative to probation and parole officers.", ("504-A", "541-B", "642", "651"),
     "Corrections", "title"),
    ("1997-1998/HB730", "C", "relative to aggravated felonious sexual assault.", ("504-A", "632-A"),
     "Crimes and Criminal Procedure", "title"),
    ("1991-1992/HB61", "C", "repealing the prospective repeal of the victims' assistance fund and making technical "
     "corrections in the distribution of penalty assessment funds.", ("188-F", "21-M"),
     "Crimes and Criminal Procedure", "title"),
    ("1989-1990/HBI2001", "C", "relating to mandatory prison sentences for certain felons.", (),
     "Crimes and Criminal Procedure", "title"),
    ("2009-2010/HB1602", "C", "relative to the secure psychiatric unit.", (), "Corrections", "title"),
    # Property - Real and Personal: a personal-property chapter, then the title, else Real Estate
    ("1999-2000/SB93", "P", "relative to self-service storage facility liens.", ("451-C",), "Personal Property",
     "chapters"),
    ("1989-1990/HB1259", "P", "relative to the unclaimed and abandoned property act.", ("471-C",), "Personal Property",
     "chapters"),
    ("2005-2006/HB1759", "P", "relative to liens for labor and materials.", ("447",), "Real Estate", "title"),
    ("2019-2020/SB262", "P", "relative to the property interest in abandoned personal materials.", ("644",),
     "Personal Property", "title"),
    ("2023-2024/HB117", "P", "relative to the termination of tenancy at the expiration of the tenancy or lease "
     "term.", ("540",), "Real Estate", "title"),
    ("2023-2024/HB1180", "P", "relative to the scope of the homestead exemption.", ("480",), "Real Estate", "title"))


@check("build", "two topics are split in two by the statutes a bill changes and then its title -- Crimes and "
                "Criminal Procedure or Corrections, Real Estate or Personal Property -- after the model, a "
                "request by its title, and each half's feed where the owner's readers follow it",
       needs=("build_site_v2", "topic_model", "build_feeds", "tag_rules"))
def _topic_split_rule(B, TM, F, TR):
    """topic_model.SPLITS (the owner, 16 November 2026: "Split up Crimes, Criminal
    Procedure and Corrections into Crimes and Criminal Procedure ... and Corrections
    separately", and Property - Real and Personal "is a bit of a confusing topic").
    Held, on real bills (_SPLIT_CASES): a prison, jail, probation or parole chapter
    with none of the criminal code or procedure is Corrections, and the reverse is
    Crimes and Criminal Procedure whatever the title says ("the crime of aggravated
    harassment by an inmate"); where the chapters do not settle it the title does,
    and "technical corrections" and "prison sentences" are not corrections; liens on
    goods, unclaimed property and the like are Personal Property and every other
    bill of Property is Real Estate, mechanics' liens (RSA 447) among them.
    vocabulary_of applies it with the chapters of the bill's own term and number,
    a request by its title (LSR 2027-0154's); unify_vocabulary files every
    record by it and writes nothing else into one; the model still answers the
    General Court's names, which never reach the site; a split topic's feed and
    follow address stays with the half that holds most of its bills; and the tag
    engine's list of the site's topics has the four names and not the two."""
    import contextlib
    import io
    name = {"C": TM.CCP_NAME, "P": TM.PRP_NAME}
    for key, k, title, chapters, want, how in _SPLIT_CASES:
        got = TM.split_rule(name[k], title, chapters)
        assert got == (want, how), f"{key} ({title[:60]}): {got}, not {(want, how)}"
    assert TM.split_names() == {"Crimes and Criminal Procedure", "Corrections", "Real Estate", "Personal Property"}
    assert TM.split_rule("Elections", "relative to prisons.", ("622",)) == ("Elections", ""), "another topic was split"
    # the model is untouched: it is measured in the General Court's names and still answers them
    assert TM.remap_gold(TM.CCP_NAME, {"title": "relative to prisons."}) == TM.CCP_NAME
    assert TM.remap_gold(TM.PRP_NAME, {"title": "relative to unclaimed property."}) == TM.PRP_NAME
    if TM.base.codes():     # data/subjects.json, which a bare clone lacks
        assert {TM.CCP_NAME, TM.PRP_NAME} <= set(TM.new_vocabulary()), "the model's vocabulary lost a General Court name"
    assert not TM.split_names() & set(TM.new_vocabulary()), "the model's vocabulary took a split name"
    # vocabulary_of: with a term, the chapters the bill's own text changes; a request, its title
    saved = list(B._CHANGES)
    B._CHANGES[:] = [{"2021-2022": {"HB1105": {"changes": ["651-A:3"]}}}]
    try:
        rec = {"title": "relative to earned time credits."}
        assert B.vocabulary_of(TM.CCP_NAME, rec, "HB1105", "2021-2022") == "Corrections", (
            "vocabulary_of did not read the chapters the bill changes")
        assert B.vocabulary_of(TM.CCP_NAME, rec, "HB1105") == "Crimes and Criminal Procedure", (
            "without a term the split read chapters it cannot have")
        req = {"title": "relative to parole eligibility for persons convicted of first degree murder.",
               "subject": "", "bill": ""}
        assert B.vocabulary_of(TM.CCP_NAME, req, "") == "Corrections", "a request's title did not split it"
        assert B.vocabulary_of(TM.PRP_NAME, {"title": "repealing certain disclosure requirements for "
                                             "homeowners' associations.", "subject": "", "bill": ""}, "") == \
            "Real Estate", "LSR 2027-0132 is not Real Estate"
        assert B.vocabulary_of(TM.CCP_NAME, {"title": "establishing a committee to study prison overcrowding."},
                               "HB9") == TM.STUDY, "a study committee was split rather than filed under Study"
        bills = {"2021-2022": {"HB1105": {"title": "relative to earned time credits.", "subject": TM.CCP_NAME,
                                          "subject_code": "CCP"},
                               "HB1101": {"title": "relative to a forfeiture of personal property.",
                                          "subject": TM.PRP_NAME, "subject_code": "PRP"},
                               "HB1133": {"title": "prohibiting the termination of a lease during the sale of "
                                                   "real property.", "subject": TM.PRP_NAME, "subject_code": "PRP"},
                               "HB2": {"title": "relative to theft.", "subject": TM.CCP_NAME, "subject_code": "CCP"}}}
        before = {b: set(r) for b, r in bills["2021-2022"].items()}
        with contextlib.redirect_stdout(io.StringIO()):
            B.unify_vocabulary(bills)
    finally:
        B._CHANGES[:] = saved
    got = {b: (r["subject"], r["subject_code"]) for b, r in bills["2021-2022"].items()}
    assert got == {"HB1105": ("Corrections", "CCP"), "HB1101": ("Personal Property", "PRP"),
                   "HB1133": ("Real Estate", "PRP"), "HB2": ("Crimes and Criminal Procedure", "CCP")}, got
    assert before == {b: set(r) for b, r in bills["2021-2022"].items()}, "the vocabulary step wrote a field"
    for t in ("relative to something.", "relative to prisons.", "relative to unclaimed property.", ""):
        for s in (TM.CCP_NAME, TM.PRP_NAME):
            assert B.vocabulary_of(s, {"title": t}, "HB1") in TM.split_names(), (s, t)
    assert "Crimes, Criminal Procedure and Corrections" not in B.TOPIC_WORDS.values()
    # the feeds: the larger half keeps the old topic's address, the smaller has its own
    assert F.topic_slug("Crimes and Criminal Procedure") == F.slug("Crimes, Crim.Proc. & Corr.") == "crimes-crim-proc-corr"
    assert F.topic_slug("Real Estate") == F.slug("Property - Real and Personal") == "property-real-and-personal"
    assert (F.topic_slug("Corrections"), F.topic_slug("Personal Property")) == ("corrections", "personal-property")
    assert F.topic_slug("Constitutional Amendments") == "cacr", "the renamed topic lost its feed's address"
    # the tag engine's own list of the site's topics, for a disk with no built site
    assert TM.split_names() <= set(TR.SITE_TOPICS), "tag_rules.SITE_TOPICS lacks a split name"
    assert not {"Crimes, Criminal Procedure and Corrections", "Property - Real and Personal"} & set(TR.SITE_TOPICS)
    return "ok", (f"{len(_SPLIT_CASES)} real bills split as the rule says, a request by its title, the model's "
                  "names kept and never shown, the old feed addresses on the larger halves")


@check("data", "every bill of the two topics split in two is filed under one of its halves on the record on "
               "this disk, and no bill keeps the old names", needs=("build_site_v2", "official_topics", "topic_model"))
def _topic_split_on_disk(B, OT, TM):
    """The data half of _topic_split_rule: the build's own path to a topic -- the
    General Court's code (official_topics.adopt), the model's answer for the rest
    (merge_guessed_topics), then unify_vocabulary -- over data/bills.json, with the
    statutes each bill changes from rsa_citations.json. Every bill the General Court
    or the model files under Crimes, Crim.Proc. & Corr. or Property - Real and
    Personal and no other rule claims (a study, a housing title) ends under one of
    the two halves, both halves of each are used, and no record keeps an old name.
    Says the counts: 1,568 and 227, 73 and 27 on the record of 7 November 2026."""
    import contextlib
    import io
    if not Path("data/bills.json").exists() or not Path("data/subjects.json").exists():
        return "skip", "no data/bills.json here"
    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    subjects = json.loads(Path("data/subjects.json").read_text(encoding="utf-8"))
    with contextlib.redirect_stdout(io.StringIO()):
        OT.adopt(bills, subjects)
        B.merge_guessed_topics(bills)
    split = {}
    for term, by in bills.items():
        for bid, rec in by.items():
            s = (rec.get("subject") or "").strip()
            if s in TM.SPLITS and TM.remap_gold(s, {**rec, "bill": bid}) == s:
                split[(term, bid)] = s
    with contextlib.redirect_stdout(io.StringIO()):
        B.unify_vocabulary(bills)
    if not split:
        return "skip", "no bill of the two split topics on this disk"
    old = {"Crimes, Criminal Procedure and Corrections", TM.CCP_NAME, TM.PRP_NAME, "Property - Real and Personal"}
    kept = [f"{t} {b}" for t, by in bills.items() for b, r in by.items() if (r.get("subject") or "") in old]
    assert not kept, f"{len(kept)} bills keep an old topic name, {kept[:3]}"
    tally = Counter()
    for (term, bid), s in split.items():
        got = bills[term][bid].get("subject")
        # a cannabis bill of either is Cannabis (topic_model.cannabis_topic, _topic_cannabis_rule)
        assert got in TM.SPLITS[s] or got == TM.CANNABIS, f"{term} {bid}, filed under {s}, is now {got!r}"
        tally[got] += 1
    empty = [n for n in TM.split_names() if not tally[n]]
    assert not empty, f"no bill on this disk is filed under {empty}: the split is not reaching the record"
    (a, z), (c, d) = TM.SPLITS[TM.CCP_NAME], TM.SPLITS[TM.PRP_NAME]
    return "ok", (f"{tally[a] + tally[z]:,} bills of Crimes: {tally[a]:,} {a}, {tally[z]:,} {z}; "
                  f"{tally[c] + tally[d]:,} of Property: {tally[c]:,} {c}, {tally[d]:,} {d}; no old name kept")


# Real titles (topic_model.cannabis_topic): (bill, the name the General Court or the model files it under, its
# title, the site's topic). The first seven are Cannabis from five topics; the rest keep theirs.
_CANNABIS_CASES = (
    ("1997-1998/HB118", "Crimes, Crim.Proc. & Corr.", "relative to penalties for marijuana possession.", "Cannabis"),
    ("2025-2026/SB264", "Public and Mental Health", "relative to the therapeutic cannabis program.", "Cannabis"),
    ("2019-2020/HB1581", "Agriculture", "relative to the labeling and sale of hemp products containing CBD.",
     "Cannabis"),
    ("2025-2026/SB485", "Agriculture", "relative to the licensure, regulation and taxation of hemp-based derivative "
     "products.", "Cannabis"),
    ("2019-2020/HB174", "Public and Mental Health", "relative to alternative treatment center licenses.", "Cannabis"),
    ("2023-2024/SB426", "Motor Vehicles", "relative to the transportation of marijuana in a motor vehicle or OHRV.",
     "Cannabis"),
    ("2009-2010/HB1652", "Taxes - State", "allowing purchase and use of marijuana by adults, regulating the purchase "
     "and use of marijuana, and imposing taxes on the wholesale and retail sale of marijuana.", "Cannabis"),
    ("2001-2002/HB293", "Agriculture", "authorizing the production of industrial hemp.", "Agriculture"),
    ("2013-2014/HB1446", "Public and Mental Health", "relative to synthetic marijuana.", "Public and Mental Health"),
    ("2021-2022/SB299", "Crimes, Crim.Proc. & Corr.", "relative to the penalty for escape and relative to home "
     "cultivation of cannabis plants and the possession of certain cannabis-infused products.",
     "Crimes and Criminal Procedure"),
    ("2025-2026/CACR19", "CACR", "relative to the personal possession of cannabis. Providing that adults 21 years of "
     "age or older shall have the right to possess a modest amount of cannabis intended for their personal "
     "consumption.", None),
    ("2015-2016/HB150", "Crimes, Crim.Proc. & Corr.", "establishing a commission to study the legalization, "
     "regulation, and taxation of marijuana.", "Study Committees and Commissions"),
    ("2023-2024/HB1240", "Public and Mental Health", "relative to eating disorders as a qualifying condition for the "
     "therapeutic cannabis program.", "Cannabis"))


@check("build", "a bill whose title is about cannabis is filed under Cannabis whichever topic the General Court or "
                "the model gives it -- but a constitutional amendment and a study -- and a request by its title",
       needs=("build_site_v2", "topic_model", "build_feeds", "tag_rules"))
def _topic_cannabis_rule(B, TM, F, TR):
    """topic_model.cannabis_topic (the owner, 17 November 2026: "Cannabis makes more sense as a topic to me than a
    tag"). On real titles (_CANNABIS_CASES): marijuana penalties from Crimes, therapeutic cannabis and its
    alternative treatment centers from Public and Mental Health, hemp products with CBD and hemp-based derivative
    products from Agriculture, carrying marijuana in a car from Motor Vehicles, legalization and its taxes from
    Taxes - State are Cannabis; industrial hemp alone, synthetic marijuana, a title whose first subject is
    something else (escape, before "and relative to" cannabis), a constitutional amendment and a study keep their
    topics. vocabulary_of files a bill and a request alike, before the splits; unify_vocabulary writes the name
    and the code CAN and nothing else, and a second pass moves nothing; the model never answers Cannabis; the
    topic's feed is /feed/topic/cannabis.xml; the tag engine's list of the site's topics has it."""
    import contextlib
    import io
    for key, name, title, want in _CANNABIS_CASES:
        term, bid = key.split("/")
        got = B.vocabulary_of(name, {"title": title}, bid, term)
        assert got == want, f"{key} ({title[:60]}): {got!r}, not {want!r}"
        named = TM.remap_gold(name, {"title": title, "bill": bid})      # a study is Study before this rule
        assert (TM.cannabis_topic(named, title) == TM.CANNABIS) == (want == TM.CANNABIS), key
    req = {"title": "relative to the therapeutic cannabis program.", "subject": "", "bill": ""}
    assert B.vocabulary_of("Public and Mental Health", req, "") == "Cannabis", "a request's title did not file it"
    assert TM.cannabis_title("relative to the sale of hemp products containing certain levels of THC.")
    assert not TM.cannabis_title("relative to the thc of things."), "THC read in lower case"
    assert TM.cannabis_topic("Constitutional Amendments", "relating to cannabis.") == "Constitutional Amendments"
    assert TM.ADDED_CODES.get(TM.CANNABIS) == "CAN"
    assert TM.CANNABIS not in set(TM.new_vocabulary()), "the model's vocabulary took Cannabis"
    bills = {"2025-2026": {"SB264": {"title": "relative to the therapeutic cannabis program.",
                                     "subject": "Public and Mental Health", "subject_code": "PMH"},
                           "CACR19": {"title": _CANNABIS_CASES[10][2], "subject": "CACR", "subject_code": "CACR"},
                           "HB1": {"title": "relative to penalties for marijuana possession.",
                                   "subject": TM.CCP_NAME, "subject_code": "CCP"}}}
    before = {b: set(r) for b, r in bills["2025-2026"].items()}
    with contextlib.redirect_stdout(io.StringIO()):
        B.unify_vocabulary(bills)
        once = {b: (r["subject"], r["subject_code"]) for b, r in bills["2025-2026"].items()}
        B.unify_vocabulary(bills)
    assert once == {"SB264": ("Cannabis", "CAN"), "CACR19": ("", ""),
                    "HB1": ("Cannabis", "CAN")}, once
    assert once == {b: (r["subject"], r["subject_code"]) for b, r in bills["2025-2026"].items()}, (
        "a second pass moved a bill")
    assert before == {b: set(r) for b, r in bills["2025-2026"].items()}, "the vocabulary step wrote a field"
    assert F.topic_slug("Cannabis") == "cannabis"
    assert "Cannabis" in TR.SITE_TOPICS
    return "ok", (f"{len(_CANNABIS_CASES)} real titles filed as the rule says: Cannabis from five topics; hemp alone, "
                  "synthetic marijuana, a second subject, an amendment and a study keep theirs; a request by its "
                  "title; the code CAN; a second pass moves nothing")


@check("data", "every bill on this disk whose title is about cannabis is filed under Cannabis, and nothing else is",
       needs=("build_site_v2", "official_topics", "topic_model"))
def _topic_cannabis_on_disk(B, OT, TM):
    """The data half of _topic_cannabis_rule: the build's own path to a topic -- the General Court's code
    (official_topics.adopt), the model's answer for the rest (merge_guessed_topics), then unify_vocabulary -- over
    data/bills.json. Every bill under Cannabis has a cannabis title and came from no constitutional amendment or
    study; every bill with a cannabis title and neither of those is under Cannabis. Says the count and the topics it
    came from: 174 bills on the record of 17 November 2026, 89 from Public and Mental Health and 64 from Crimes."""
    import contextlib
    import io
    if not Path("data/bills.json").exists() or not Path("data/subjects.json").exists():
        return "skip", "no data/bills.json here"
    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    subjects = json.loads(Path("data/subjects.json").read_text(encoding="utf-8"))
    with contextlib.redirect_stdout(io.StringIO()):
        OT.adopt(bills, subjects)
        B.merge_guessed_topics(bills)
    was = {(t, b): (r.get("subject") or "").strip() for t, by in bills.items() for b, r in by.items()}
    with contextlib.redirect_stdout(io.StringIO()):
        B.unify_vocabulary(bills)
    came, wrong, missed = Counter(), [], []
    for term, by in bills.items():
        for bid, rec in by.items():
            s, title = was[(term, bid)], rec.get("title") or ""
            kept = TM.remap_gold(s, {**rec, "bill": bid}) in TM.CANNABIS_KEEP if s else True
            if rec.get("subject") == TM.CANNABIS:
                came[B.vocabulary_of(s, {"title": "relative to something.", "bill": bid}) or s] += 1
                if kept or not TM.cannabis_title(title):
                    wrong.append(f"{term} {bid}")
            elif s and not kept and TM.cannabis_title(title):
                missed.append(f"{term} {bid}")
    assert not wrong, f"{len(wrong)} bills under Cannabis that the rule does not give it: {wrong[:3]}"
    assert not missed, f"{len(missed)} bills with a cannabis title filed elsewhere: {missed[:3]}"
    if not came:
        return "skip", "no bill with a cannabis title on this disk"
    return "ok", (f"{sum(came.values()):,} bills under Cannabis, from " + ", ".join(f"{n} {k}" for k, n in
                                                                               came.most_common(4)))


@check("status", "between two reports, the Reports tab quotes the motion that sent the bill back",
       needs=("build_site_v2",))
def _reports_between(build_site_v2):
    """"Between these reports the docket records" names why a committee
    reported twice, and quoted the first line that mentioned it: HB 75 of
    1999 showed a motion its mover withdrew, HB 450 of 2009 the motion with
    no outcome, SB 96 of 2003 one "[Not Voted On]" -- each over the line
    that carried. Real rows."""
    B = build_site_v2

    def ev(date, raw, typ="floor"):
        return {"body": "S", "date": date, "raw": raw, "type": typ, "cancelled": False}

    def rep(date):
        return ev(date, "Committee Report, Ought to Pass", "report") | {
            "recommendation": "Ought to Pass", "side": ""}

    bad = []
    for bid, rows, want in (
            ("HB75", ["Sen. Russman moved Rerefer, Sen. Russman Withdrew Motion to Rerefer",
                      "Sen D'Allesandro Moved Rerefer, MA, VV"],
             "Sen D'Allesandro Moved Rerefer, MA, VV"),
            ("HB450", ["Ought to Pass, MF, VV", "Sen. Kelly moved to Rereferred to Committee",
                       "Rereferred to Committee, MA, VV"], "Rereferred to Committee, MA, VV"),
            ("SB96", ["Rerefer to Committee [Not Voted On]", "Sen. O'Hearn Moved Recommit, MA, VV"],
             "Sen. O'Hearn Moved Recommit, MA, VV"),
            ("HB679", ["Rereferred to Committee, MF, VV; Sen. McCarley Moved Ought to Pass, MA, VV",
                       "Sen. McCarley sub-motion Rereferred to Committee, MA, VV"],
             "Sen. McCarley sub-motion Rereferred to Committee, MA, VV")):
        narr = {"events": [rep("2009-05-01")] + [ev("2009-05-13", r) for r in rows]
                + [rep("2010-01-07")]}
        got = B.committee_reports([], narr, {}, "", "Judiciary")[2]
        if [g["text"] for g in got] != [want]:
            bad.append(f"{bid}: {[g['text'] for g in got]}")
    # Withdrawn or unvoted in a clause of its own before the recommittal is
    # another motion, and the recommittal carried; in its own clause it is
    # the recommittal's.
    for raw, want in (("Inexpedient to Legislate [not voted on]; Sen. Boyce moved to Recommit, "
                       "MA, VV; SJ 5, Pg.53", True),
                      ("REP FLANAGAN WITHDREW OTP/AM MOTION; RE-REFERRED TO CON & STAT,", True),
                      ("REP BUCKLEY WITHDREW RECOMMIT MOTION; ADOPTED VV", False)):
        if B._again_carried(raw) is not want:
            bad.append(f"{raw[:40]!r} read {B._again_carried(raw)}")
    assert not bad, "; ".join(bad)
    return "ok", "a withdrawn, unvoted, failed or outcome-less motion gives way to the one that carried"


# THE OLDER TERMS' DISAGREEMENTS, recounted on 24 September after review found
# that the first count of 78 held journey mistakes as well as docket gaps (HB
# 1075 of 1998's phantom veto among them). Each of the 36 left was read
# against its docket, and none is the journey misreading a line:
#   13 where the docket does not record a decision the status or the rail
#      stands on -- no signature line (HB 768 of 1989), a passage recorded
#      only as amendment votes (HB 119 of 1993), as a divided question's
#      parts (HB 2018 of 2018) or with no motion code (SB 119 of 2009), no
#      override vote (HB 396 of 2024);
#   11 where the docket files a row under the other chamber, or two measures
#      share a number, and the rail's stops are drawn from that filing (SB
#      187 of 1991, SR 1 of 1995, CACR 9 of 1995, CACR 20 of 2007);
#   12 where the status word says what the docket does not -- HB 1141 of
#      2022 "Referred for interim study" over "Inexpedient to Legislate: MA
#      VV 03/15/2022", HR 13 of 2007 "In committee" over "Introduced and
#      Adopted".
# Five of those were then fixed rather than explained, which leaves 31: HR
# 13's chip now reads its adoption; HB 549 of 1991, SB 1 of 2005 and HB 1534
# of 2016, whose status fields say both chambers passed them, no longer read
# "Passed one chamber"; and SB 200 of 1989's "CONF COMM REPORT ADOPTED", three
# months after the Senate killed it, is not read as a conference no passage
# could have called.
# ON 2 OCTOBER 2026 THE COUNT STOOD AT 28, and eight more were fixed rather
# than explained, which leaves 20. Three went with statuses a sweep of all
# nineteen terms corrected: HBI 2011 of 1990, a bill of intent drawn as a
# bill; SB 27 of 1994, whose referral to interim study no pattern read; HB
# 1674 of 1998, a report adopted on the row after the one naming it. Five
# were rails the record contradicts, and each now stops where its docket
# does: CACR 9 of 1995 in the House that returned it, HB 613 and HB 614 of
# 1993 in the Senate that killed them, HB 1371 and HB 1188 of 1992 in the
# House they never left (_rail_against_the_record).
# None is in the current term, which is held to none. A ceiling rather than a
# list, so a regression anywhere in the archive fails.
_JOURNEY_EXPLAINED = 20


def _journey_story(records, rows, B):
    """(counts, the current term's disagreements, the older terms') for
    records [(term, bid, record)] against index rows {(term, bid): row}.
    The dated rail's marks are held to the index's too: the list card and
    the bill's own view draw one rail."""
    n, now, old = Counter(), [], []
    current = max((t for t, _b in rows), default="")
    for term, bid, rec in records:
        row = rows.get((term, bid))
        if not row or not row.get("kind"):
            continue
        j = rec.get("journey") or {}
        steps, rail = j.get("steps") or [], j.get("rail") or []
        p = row.get("passage") or ""
        why = B.journey_disagrees(steps, row["kind"], row.get("status"), p, bid)
        marks = {s.get("stop"): s.get("mark") for s in rail}
        if not why and p and rail:
            other = "Senate" if p[0] == "H" else "House"
            own = "House" if p[0] == "H" else "Senate"
            # The rail's own marks for interim study and the table now refine
            # the passage letter they stand in for (B.RAIL_REFINES), and
            # only on the chip that draws them (B.RAIL_MARK_OF_CHIP) -- and
            # the pause on a Died bill, where it died on the table, refines
            # the cross (B.RAIL_DEAD_TABLE; the person, 8 October 2026: "Show
            # the body it was tabled in with the yellow pause, and show the
            # red x mark on the law once it died when the session ended").
            mine = {v: k for k, v in B.RAIL_MARK_OF_CHIP.items()}
            for stop, m in zip((own, other, "Governor", "Law"), p[1:]):
                drawn = marks.get(stop)
                dead = ((drawn, m) == B.RAIL_DEAD_TABLE and row.get("chip") == "Died"
                        and stop in ("House", "Senate"))
                if drawn in mine and not dead and (row.get("chip") != mine[drawn]
                                                   or stop not in ("House", "Senate")):
                    why = (f"the bill's own rail marks {stop} {drawn!r} on a bill whose "
                           f"chip is {row.get('chip')!r}")
                    break
                if stop in marks and not dead and B.RAIL_REFINES.get(drawn, drawn) != m:
                    why = f"the bill's own rail marks {stop} {marks[stop]!r} and the list card {m!r}"
                    break
        n["empty" if not steps else "disagree" if why else "agree"] += 1
        if why:
            (now if term == current else old).append(f"{term} {bid}: {why}")
    return n, now, old


@check("data", "a bill's journey, its status and its rail tell one story",
       needs=("build_site_v2",))
def _journey_agrees(build_site_v2):
    """How it got here, the status chip and the rail are three claims about
    one bill, and the page draws all three within a screen of each other. A
    journey that ends in a kill under a chip saying "Signed into law", or a
    rail that crosses the House beside a list saying the House passed it, is
    the site contradicting itself -- which is how CACR 1 of 2025 came to say
    "No vote was ever taken on it" over the House's vote to kill it.

    Read from the built pages and the index, so it is about what a reader sees.
    """
    every = _site_bills() if Path("site/bill").is_dir() else None
    if every is None:
        return "skip", "no built index and bill pages"
    rows = {(r.get("term"), r.get("id")): r for r in every}
    recs = ((rec.get("term") or "", bid, rec) for _y, bid, rec in _site_records())
    n, now, old = _journey_story(recs, rows, build_site_v2)
    if not (n["agree"] or n["disagree"]):
        return "skip", "no bill record carries a journey yet"
    assert not now, (f"{len(now)} bills of the current term tell two stories: "
                     f"{'; '.join(now[:3])!a}")
    assert len(old) <= _JOURNEY_EXPLAINED, (
        f"{len(old)} bills of the older terms disagree, and {_JOURNEY_EXPLAINED} were "
        f"explained: {'; '.join(old[:3])!a}")
    return "ok", (f"{n['agree']:,} bills agree; {len(old)} of the older terms do not, "
                  f"each a gap, a misfiled row or a status word in the docket itself; "
                  f"{n['empty']:,} have no floor decision on record")


@check("data", "every bill that died on the table is paused where it was tabled and crossed at Law "
               "on the day it died, and every interim study bill of a finished session is "
               "crossed at Law with a line saying why",
       needs=("build_site_v2",))
def _rail_endings_on_the_site(B):
    """THE RAIL'S ENDINGS ON EVERY BILL (the person, 8 and 9 October 2026),
    read from the built pages and the index, as _rail_endings holds them on
    real rows:

      * A Died bill whose rail pauses a chamber has that chamber's tabling
        line with the pause in How it got here, a line of the death with the
        cross after it, and a Law stop crossed on a day no earlier than the
        tabling.
      * No Died bill whose chamber's last line is a tabling keeps the cross
        there on the day it was tabled: on 7 October 2026, 1,449 of the 2,170
        that died on a table did.
      * An Interim Study bill whose session is over -- every archived term,
        and the current one once corrections/status/status.txt names its
        session_over -- has Law crossed, on the day of its line "Still in
        interim study when the ... last sat"; while the session sits, Law is
        not reached and no such line is drawn.
      * A report's line is the orange arrow exactly where the report
        recommended the subject for future legislation.
      * THE DAY A SESSION'S END IS DATED BY (the review of the rail's
        endings, 9 October 2026) is never a Saturday or a Sunday -- 82
        interim study bills of 1989-1990 were dated Sunday 1 July 1990, the
        day Joint Rule 24(b)'s postponements were entered -- and a line
        saying the Senate last sat, in a year its journals are on disk, is
        dated no earlier than the last sitting they open outside a special
        session's journal and a December of the second year (B.
        journal_sittings): 45 bills of 2004 read 25 May 2004 where SJ 17 has
        the Senate adjourn on 17 June with them on its table."""
    every = _site_bills() if Path("site/bill").is_dir() else None
    if every is None:
        return "skip", "no built index and bill pages"
    rows = {(r.get("term"), r.get("id")): r for r in every}
    current = max((t for t, _b in rows if re.fullmatch(r"\d{4}-\d{4}", t or "")), default="")
    over_now = bool(B.session_over_in(B.session_over("corrections/status/status.txt"), current))
    from datetime import date as _date
    n, bad, senate = Counter(), [], {}
    for _y, bid, rec in _site_records():
        term = rec.get("term") or ""
        row = rows.get((term, bid)) or {}
        j = rec.get("journey") or {}
        steps, stops = j.get("steps") or [], {s.get("stop"): s for s in j.get("rail") or []}
        law = stops.get("Law") or {}
        chip = row.get("chip")
        if chip == "Died":
            paused = [c for c in ("House", "Senate") if (stops.get(c) or {}).get("mark") == "t"]
            hs = [s for s in steps if s.get("body") in ("H", "S")]
            if paused:
                n["paused"] += 1
                b = paused[0][0]
                at = next((i for i in range(len(hs) - 1, -1, -1)
                           if hs[i].get("body") == b and hs[i].get("act") == "tabled"), None)
                if at is None or hs[at].get("mark") != "t" or not any(
                        s.get("act") == "died" and s.get("mark") == "x" for s in hs[at + 1:]):
                    bad.append(f"{term} {bid}: the {paused[0]} is paused with no tabling line "
                               "paused and no death after it")
                elif law and (law.get("mark") != "x" or (law.get("date") or "9")
                              < (hs[at].get("date") or "")):
                    bad.append(f"{term} {bid}: Law is {law.get('mark')!r} {law.get('date')!r}, "
                               f"before its tabling of {hs[at].get('date')}")
            elif hs and hs[-1].get("act") == "tabled":
                tab = hs[-1]
                own = stops.get({"H": "House", "S": "Senate"}.get(tab.get("body")))
                if own and own.get("mark") == "x" and own.get("date") == tab.get("date"):
                    bad.append(f"{term} {bid}: the {own['stop']} is crossed on the day it was "
                               "tabled")
        elif chip == "Interim Study":
            over = term != current or over_now
            said = [s for s in steps if s.get("act") == "died"
                    and (s.get("text") or "").startswith("In interim study:")]
            n["study over" if over else "study sitting"] += 1
            if not over:
                if said or law.get("mark") not in (None, "-"):
                    bad.append(f"{term} {bid}: held for interim study while the session sits, "
                               f"and Law is {law.get('mark')!r} beside {len(said)} line of its death")
            elif law and (law.get("mark") != "x" or not said
                          or (law.get("date") or "") != (said[-1].get("date") or "")):
                bad.append(f"{term} {bid}: held for interim study in a session that is over, "
                           f"and Law is {law.get('mark')!r} {law.get('date')!r} beside "
                           f"{[s.get('date') for s in said]}")
            rep = [s for s in steps if s.get("act") == "study_report"]
            sr = rec.get("study_report") or {}
            if rep and (rep[-1].get("mark") == "f") != (sr.get("rec") == "rec"):
                bad.append(f"{term} {bid}: the report's line is {rep[-1].get('mark')!r} and "
                           f"the report {sr.get('rec')!r}")
            n["reports"] += bool(rep)
        for s in steps:
            if not B.session_end_line(s) or s.get("act") != "died" or not s.get("date"):
                continue
            d = s["date"]
            try:
                weekday = _date.fromisoformat(d).weekday()
            except ValueError:
                bad.append(f"{term} {bid}: a session's end dated {d!r}")
                continue
            if weekday >= 5:
                bad.append(f"{term} {bid}: a session's end dated on a {('Saturday', 'Sunday')[weekday - 5]}, {d}")
            if s.get("body") == "S" and "the Senate last sat" in (s.get("text") or ""):
                senate.setdefault(d[:4], []).append((term, bid, d))
    if senate:
        days = B.journal_sittings()
        for y, said in senate.items():
            opened = [d for d in days.get(("S", y), ()) if d[:4] == y
                      and not (d[5:7] == "12" and int(y) % 2 == 0)]
            for term, bid, d in said:
                if opened and d < max(opened):
                    bad.append(f"{term} {bid}: the Senate last sat on {d}, and its journal opens "
                               f"a sitting on {max(opened)}")
    if not (n["paused"] or n["study over"] or n["study sitting"]):
        return "skip", "no bill record carries a rail's ending yet"
    assert not bad, f"{len(bad)} bills: {'; '.join(bad[:4])!a}"
    return "ok", (f"{n['paused']:,} bills that died on a table paused where tabled and crossed "
                  f"at Law; {n['study over']:,} interim study bills of a finished session crossed "
                  f"at Law, {n['reports']:,} with the report's line; {n['study sitting']:,} "
                  "still sitting, Law not reached")


@check("data", "the list card's rail is the bill's own rail, stop for stop",
       needs=("build_site_v2",))
def _rail_on_the_card(build_site_v2):
    """One rail, always detailed (the person, 5 October 2026): a card in a
    list draws the dated rail from its index row's stops before the record is
    fetched, and the record's own once it is. The two are written by one
    line of build_bills from one journey_rail, and this is the test that
    what idx/<term>.json carries is what the bill's page carries -- every
    stop, its mark and its day, which is all either draws -- on every bill of
    every term. A row with no stops is a record with none; a record with stops
    and a row without would draw the bare rail on the card and the dated one
    opened, which is the shape-change the decision removed.

    The row's words beside each day are what its card says to a reader who
    hears it; the record's stops carry none (the person, 5 October 2026: the
    rail draws dates only), since the page says each stop in its `say`."""
    idx = Path("site/idx")
    if not (idx.is_dir() and Path("site/bill").is_dir()):
        return "skip", "no built idx/ and bill pages"
    code = {v: k for k, v in build_site_v2.RAIL_CODE.items()}
    rows = {}
    for f in idx.glob("*.json"):
        if not re.match(r"\d{4}-\d{4}$", f.stem):
            continue
        for r in json.loads(f.read_text(encoding="utf-8")):
            rows[(r.get("term"), r.get("id"))] = r
    n, bad, worded = 0, [], []
    for _y, bid, rec in _site_records():
        row = rows.get((rec.get("term") or "", bid))
        if not row:
            continue
        stops = (rec.get("journey") or {}).get("rail") or []
        own = [(s_.get("stop"), s_.get("mark"), s_.get("date") or "") for s_ in stops]
        card = [(code.get(c[0][:1], "?"), c[0][1:], (c + [""])[1])
                for c in (row.get("rail") or [])]
        n += 1
        if own != card:
            bad.append(f"{rec.get('term')} {bid}: the card {card[:2]!a}..., the page {own[:2]!a}...")
        if any("short" in s_ for s_ in stops):
            worded.append(f"{rec.get('term')} {bid}")
    if not n:
        return "skip", "no bill page matched an index row"
    assert not bad, f"{len(bad)} bills draw one rail on the card and another opened: " + (
        "; ".join(bad[:3]))
    assert not worded, (f"{len(worded)} records' rails carry words to draw under a stop, "
                        f"which draws its day alone: {worded[:3]}")
    with_stops = sum(1 for r in rows.values() if r.get("rail"))
    return "ok", (f"{n:,} bills: the card's rail is the page's, stop for stop, mark and day, "
                  f"and no record's stop carries words to draw; {with_stops:,} index rows "
                  "carry stops, the rest have no rail to draw")


@check("data", "every CACR with a ballot row shows the voters' vote, and its outcome by two thirds",
       needs=("build_site_v2",))
def _ballots_shown(build_site_v2):
    """Each row of ballot_results.json (5 October 2026) is a CACR whose page
    must show the voters' card, whose status must say what two thirds of the
    votes cast decided, and whose rail must end at the Voters stop with the
    election's day and that outcome. An election still to come shows its day
    and no outcome. Where the docket records a referendum of its own, its
    answer and the two-thirds answer from the source's figures must be the
    same answer -- and the card says so wherever the docket's figures are
    not the source's. No page shows a voters' card the file does not have.

    AND WHOSE IT IS, BY THE ROW (7 October 2026): each card names the
    source its row gives and where the count is printed, and How it got
    here's voters' line names it too -- "(the Secretary of State's count)",
    or beside a docket's own differing count "(the docket's count; the
    Secretary of State's is ...)" -- for the seventeen the voters decided;
    the election still to come names Ballotpedia."""
    B = build_site_v2
    names = {"sos.nh.gov": "Secretary of State", "electiondatabase.nhpr.org": "Secretary of State",
             "ballotpedia.org": "Ballotpedia"}
    whose = {"Secretary of State": "the Secretary of State's", "Ballotpedia": "Ballotpedia's"}
    f = Path(B.BALLOTS)
    idx = Path("site/idx")
    if not (f.exists() and idx.is_dir() and Path("site/bill").is_dir()):
        return "skip", "no ballot_results.json, or no built idx/ and bill pages"
    want = {(r["term"], r["bill"]): r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}
    rows = {}
    for t in {t for t, _b in want}:
        p = idx / f"{t}.json"
        if p.exists():
            rows.update({(t, r.get("id")): r for r in json.loads(p.read_text(encoding="utf-8"))})
    recs = {(rec.get("term") or "", bid): rec for _y, bid, rec in _site_records()}
    bad, decided, docket_differs, named_by = [], 0, [], Counter()
    for key, r in sorted(want.items()):
        rec, row = recs.get(key), rows.get(key)
        name = f"{key[0]} {key[1]}"
        if not rec or not row:
            bad.append(f"{name} has no page or no index row")
            continue
        card = rec.get("ballot") or {}
        if card.get("date") != r["election"]:
            bad.append(f"{name}'s page shows no voters' card for {r['election']}: {card!a}")
            continue
        status = row.get("status") or ""
        stop = ((rec.get("journey") or {}).get("rail") or [{}])[-1]
        host = re.sub(r"^https?://(?:www\.)?([^/?#]+).*$", r"\1", r.get("source") or "")
        by = names.get(host, host)
        named_by[by] += 1
        if (card.get("by"), card.get("cite"), card.get("whose")) != (
                by, r.get("cite"), whose.get(by, f"{by}'s")):
            bad.append(f"{name}'s card names {card.get('by')!a}, {card.get('cite')!a} where its "
                       f"row's source is {by!a}, {r.get('cite')!a}")
        if r.get("yes") is None:
            if not card.get("pending") or "ratified" in status or stop.get("stop") != "Voters" \
                    or stop.get("mark") in ("p", "x"):
                bad.append(f"{name}'s election is to come and reads {status!a}, {stop!a}")
            continue
        line = next((s_.get("text") or "" for s_ in reversed(
            (rec.get("journey") or {}).get("steps") or []) if s_.get("body") == "V"), "")
        # The docket's own referendum line where it has one (the status is
        # then the docket's), and the row's line where it has none.
        if card.get("docket"):
            said = f"(the docket's count; {whose.get(by, by)} is {r['yes']:,}–{r['no']:,})"
        elif rec.get("status_source") == B.BALLOT_SOURCE:
            said = f"({whose.get(by, by)} count)"
        else:
            said = ""     # the docket's line, and its count is the row's: nothing to name
        if said and not line.endswith(said):
            bad.append(f"{name}'s How it got here ends {line!a}, not naming {said!a}")
        decided += 1
        ok = B.ratified(r["yes"], r["no"])
        if (card.get("yes"), card.get("no"), card.get("ratified")) != (r["yes"], r["no"], ok):
            bad.append(f"{name}'s card reads {card!a}")
        if status != (B.RATIFIED if ok else B.NOT_RATIFIED):
            bad.append(f"{name} reads {status!a} where two thirds of the votes cast "
                       f"({r['yes']:,} to {r['no']:,}) {'ratified' if ok else 'did not ratify'} it")
        if (stop.get("stop"), stop.get("mark"), stop.get("date")) != (
                "Voters", "p" if ok else "x", r["election"]):
            bad.append(f"{name}'s rail ends {stop!a}")
        if card.get("docket"):
            docket_differs.append(f"{name} ({card['docket'][0]:,} to {card['docket'][1]:,})")
    extra = [f"{k[0]} {k[1]}" for k, rec in recs.items() if rec.get("ballot") and k not in want]
    if extra:
        bad.append("a voters' card on pages the file names no row for: " + ", ".join(extra[:5]))
    assert not bad, "; ".join(bad[:5])
    return "ok", (f"{decided} CACRs show the voters' vote and the outcome two thirds gives, "
                  f"{len(want) - decided} an election to come; the docket prints other "
                  f"figures for {len(docket_differs)}, and the card says so: "
                  + (", ".join(docket_differs) or "none") + "; the cards name "
                  + ", ".join(f"{b} on {k}" for b, k in named_by.most_common()))


@check("rollcalls", "a member's attendance counts the days and roll calls held while they sat, on their own page only",
       needs=("build_site_v2",))
def _member_attendance(build_site_v2):
    """build_site_v2.member_attendance on the cases the real ballots hold.

    The person's definition (23-24 September): a day is a day the chamber held
    at least one roll call while the member held the seat, attended if they
    voted on any of that day's roll calls; and, apart from that, the roll calls
    they voted on out of those held while they sat. The cases are the ones read
    off RollCallHistory before this was written: a day voted on once and
    excused for the rest is attended; a day of excused ballots is not; a
    Speaker who presided all day and voted on nothing was there (Terie Norelli,
    98 such days, would otherwise be the House's worst attender); a code 7
    ballot is no vote; an arrival by special election is counted from their
    first ballot; and a senator's House years land in their own term.

    And the cases the review of 25 September found the first version wrong on,
    each a member shown absent from a day they were there or a day that never
    was: a declared conflict of interest (code 5) was counted an absence, where
    the journal has the member in the room standing aside; a seat the record
    went on listing after its holder had gone was counted as absences, 134 of
    them; a Speaker coded Excused on every roll call of a day on which the
    record names nobody in the chair was counted absent, where the journal
    has them presiding; and a roll call misdated between two of one day --
    10/22/2009 among 10/22/1999 -- made a sitting of its own.

    Then build_legislators, because where the figure goes is half the rule: in
    the member's own file, and in no listing -- legislators.json and
    former.json are what the roster, town and committee pages read.
    """
    from collections import defaultdict
    B = build_site_v2

    def v(mid, year, body, n, day, vote, **more):
        return {"member_id": mid, "name": "Example, Ann", "label": "Rep. Ann Example (D - Coos 4)",
                "party": "D", "year": year, "body": body, "vote_number": str(n), "bill": "HB1",
                "question": "Ought to Pass", "date": day, "vote": vote, **more}

    rows = [
        # 2023-2024 in the House: four days, one attended in part, one
        # excused whole, one presided with a roll call between that recorded
        # nothing, and one on which a conflict was all they declared.
        v("1", "2023", "H", 1, "1/4/2023", "Yea"),
        v("1", "2023", "H", 2, "1/4/2023", "Not Voting/Excused"),
        v("1", "2023", "H", 3, "2/8/2023", "Not Voting/Excused"),
        v("1", "2023", "H", 4, "2/8/2023", "Not Voting/Not Excused"),
        v("1", "2024", "H", 1, "1/3/2024", "Presiding"),
        v("1", "2024", "H", 2, "1/3/2024", "No vote recorded"),
        v("1", "2024", "H", 3, "1/3/2024", "Presiding"),
        v("1", "2024", "H", 4, "3/7/2024", "No vote recorded", conflict=True),
        # 2025-2026 under a Senate number, joined: two roll calls on one day.
        v("2", "2025", "S", 7, "3/6/2025", "Nay"),
        v("2", "2025", "S", 8, "3/6/2025", "Yea"),
    ]
    got = B.member_attendance(rows)
    assert got == {
        "2023-2024": {"chambers": "H", "days": 4, "attended": 3, "roll_calls": 8, "voted": 1,
                      "presided": 2, "conflict": 1, "excused": 2, "not_excused": 1,
                      "no_vote": 1},
        "2025-2026": {"chambers": "S", "days": 1, "attended": 1, "roll_calls": 2, "voted": 2,
                      "presided": 0, "conflict": 0, "excused": 0, "not_excused": 0,
                      "no_vote": 0},
    }, f"attendance counted {got}"
    # An arrival at a special election has no ballot before they sat, and is
    # counted from their first: 2 days of 2, not 2 of the term's 4.
    late = B.member_attendance(rows[4:8])
    assert late["2023-2024"]["days"] == 2 and late["2023-2024"]["attended"] == 2 \
        and late["2023-2024"]["roll_calls"] == 4, f"an arrival was counted as {late}"
    # Ballots recording nothing that END a term are a seat outliving its
    # holder, not absences; the excused ballots before them are absences.
    gone = B.member_attendance(rows[:4] + [v("1", "2023", "H", n, d, "No vote recorded")
                                           for n, d in ((5, "3/1/2023"), (6, "3/8/2023"))])
    assert (gone["2023-2024"]["days"], gone["2023-2024"]["roll_calls"],
            gone["2023-2024"]["no_vote"]) == (2, 4, 0), (
        f"a run of empty ballots after the member had gone was counted: {gone}")

    # THE WHOLE RECORD'S PART. S is the Speaker, in the chair on three of
    # 2023's roll calls; D presides once when S is away. 2/8/2023's two roll
    # calls name nobody in the chair and code S absent on both: S presided.
    # 3/1/2023 names D, and S's excusal that day stands. Roll call 6 is dated
    # ten years out between two of 3/1/2023, and roll call 8 a week late
    # between 3/1 and 3/29: the first is read on 3/1, the second on no day.
    rec = [("1", "1/4/2023", "S", "Presiding"), ("2", "1/4/2023", "S", "Presiding"),
           ("3", "2/8/2023", "S", "Not Voting/Excused"),
           ("4", "2/8/2023", "S", "Not Voting/Not Excused"),
           ("5", "3/1/2023", "D", "Presiding"), ("5", "3/1/2023", "S", "Not Voting/Excused"),
           ("6", "3/1/2033", "S", "Not Voting/Excused"),
           ("7", "3/1/2023", "S", "Not Voting/Excused"),
           ("8", "4/5/2023", "S", "Yea"), ("9", "3/29/2023", "S", "Presiding")]
    whole = defaultdict(list)
    for n, d, who, what in rec:
        whole[who].append(v(who, "2023", "H", n, d, what))
    ctx = B.attendance_context(whole)
    assert ctx["chair"] == {"2023-H-3": "S", "2023-H-4": "S"}, (
        f"the chair was read into {ctx['chair']}: only a day on which the record names "
        "nobody in it, and only the member it puts there most")
    assert (ctx["dates"]["2023-H-6"], ctx["dates"]["2023-H-8"]) == ((2023, 3, 1), (0, 0, 0)), (
        f"misdated roll calls read as {ctx['dates']['2023-H-6']} and {ctx['dates']['2023-H-8']}")
    sp = B.member_attendance(whole["S"], ctx)["2023-2024"]
    assert (sp["days"], sp["attended"], sp["roll_calls"], sp["presided"], sp["excused"]) \
        == (4, 3, 9, 5, 3), f"the Speaker was counted as {sp}"

    root = Path(tempfile.mkdtemp(prefix="gr-attend-"))
    try:
        (root / "legislators").mkdir()
        legs = {"1": {"id": "1", "last": "Example", "first": "Ann", "name": "Example, Ann",
                      "chamber": "S", "party_code": "D", "party": "D", "district": "1",
                      "county": "Coos"}}
        by = {"1": rows[:8], "2": rows[8:]}
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            B.build_legislators(root, legs, by, {}, set(), {}, {}, {"1": ["2"]})
        own = json.loads((root / "legislators" / "1.json").read_text(encoding="utf-8"))
        assert own.get("attendance") == got, (
            "the member's own file does not carry both chambers' attendance: "
            + str(own.get("attendance")))
        for f in ("legislators.json", "former.json"):
            listed = json.loads((root / f).read_text(encoding="utf-8"))
            assert not any("attendance" in m for m in listed), (
                f"{f} carries attendance: it is read by every listing of members, and the "
                "figure belongs on the member's own page, not in a column anyone is sorted by")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("a part day attended, an excused day absent, a presiding or conflict day there, "
                  "a vacated seat's empty ballots not counted, the chair read where the record names "
                  "nobody, a misdated roll call on its neighbours' day; both chambers in the member's "
                  "file, none in a listing")


@check("build", "the longest pairs of versions, compared in processes of their own, give what the "
       "loop gives, keyed as the loop meets them, and the loop refuses one it never took",
       needs=("build_bill_versions", "bill_blocks"))
def _bill_versions_early(BV, BB):
    """compare_early hands the few pairs whose words multiply past BIG_PAIR --
    HB 2 of 2025's four, 3.3 to 8.9 billion, against 0.27 billion for the next
    pair of the term -- to a pool of processes, and main() takes each where it
    would have compared it. Here BIG_PAIR is lowered so a fixture's pairs
    qualify: the pool's answers must be compare()'s for the same two versions,
    keyed by the order the loop meets them in (the amendment set aside, the
    versions sorted), and at the real mark the fixture's pairs stay in the
    loop. Marks are exercised too: each version carries its blocks."""
    def v(label, sort, date, words):
        return {"label": label, "sort": sort, "date": date, "text": " ".join(words),
                "blocks": BB.blocks("".join(f'<p class="csABCDEF12"><span class="csABCDEF12">'
                                            f"{w} of the act</span></p>" for w in words))}
    base = [f"word{i}" for i in range(60)]
    per = {("HB9", "2025"): [v("As Amended by the House", 2, "03/01/2025",
                               base[:40] + ["new"] + base[40:]),
                             v("OLS Release", 0, "02/01/2025", ["amend"] * 30),
                             v("Introduced", 1, "01/01/2025", base),
                             v("As Amended by the Senate", 3, "05/01/2025", base[:10] + base[20:])],
           ("SB3", "2026"): [v("Introduced", 1, "01/01/2026", base),
                             v("As Amended by the Senate", 3, "02/01/2026", base[5:])]}
    want = {}
    for (bill, year), vs in per.items():
        vs, _ = BV.ordered(vs)
        assert all(x["label"] != "OLS Release" for x in vs), "an amendment was diffed as a version"
        for i in range(len(vs) - 1):
            want[(bill, year, i)] = BV.compare(vs[i], vs[i + 1])
    assert len(want) == 3 and any(r[1] for r in want.values()), \
        "the fixture's pairs have no marks to compare"
    assert BV.compare_early(per) == {}, "a short pair was sent to the pool at the real mark"
    # THE POOL IS STARTED IN A PROCESS OF ITS OWN (11 November 2026). Windows
    # starts a pool's workers by importing the starting process's main
    # script, which here was this file -- eight megabytes, compiled and run
    # again by every worker, a hundred seconds of the code checks. As
    # build_bill_versions.py starts it, the main script is that small one, so
    # this starts it as that does: a few lines that call compare_early with
    # BIG_PAIR lowered and hand its answer back.
    import pickle
    tmp = Path(tempfile.mkdtemp(prefix="gr-early-"))
    try:
        (tmp / "pool.py").write_text(
            "import pickle, sys\n"
            "if __name__ == '__main__':\n"
            "    sys.path.insert(0, sys.argv[1])\n"
            "    import build_bill_versions as BV\n"
            "    BV.BIG_PAIR = 1\n"
            "    per = pickle.load(open(sys.argv[2], 'rb'))\n"
            "    pickle.dump(BV.compare_early(per), open(sys.argv[3], 'wb'))\n", encoding="utf-8")
        with open(tmp / "per.pickle", "wb") as f:
            pickle.dump(per, f)
        r = _run([sys.executable, str(tmp / "pool.py"),
                  str(_paths.locate("build_bill_versions.py").parent), str(tmp / "per.pickle"),
                  str(tmp / "early.pickle")], capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, ("compare_early with the mark lowered failed: "
                                   + ((r.stderr or r.stdout).strip().splitlines() or ["?"])[-1][:200])
        with open(tmp / "early.pickle", "rb") as f:
            early = pickle.load(f)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = _source(_paths.locate("build_bill_versions.py"))
    assert "early.pop((bill, year, i), None)" in src and "were not met by the" in src, \
        "main() no longer takes the early pairs where it meets them, or no longer refuses a left one"
    if (os.cpu_count() or 1) < 2:
        assert early == {}, "a pool was started on one processor"
        return "ok", "one processor: nothing compared ahead, and the loop does it all as before"
    assert early == want, ("the pool's answers are not the loop's", sorted(early), sorted(want))
    return "ok", ("three pairs of two bills compared in a pool equal compare()'s, keyed as the "
                  "loop meets them, marks and all; at the real mark nothing short is sent")


@check("build", "a past term's bill versions outlive the database's current views",
       needs=("build_bill_versions",))
def _versions_keep_terms(build_bill_versions):
    """build_bill_versions writes every Versions tab and its manifest from the
    dump of LegislationText and Legislation, which are current-term views:
    the first dump after they turn over to 2027-2028 holds no 2025-2026 bill.
    It reads each term frozen under db/term/<term>/ after the current dump
    now -- each with its own Legislation, because a LegislationID restarts
    every term -- and a bill-year the current dump holds comes from it.
    Driven end to end on a small tree."""
    BBV = build_bill_versions
    tmp = Path(tempfile.mkdtemp(prefix="gr-versions-"))
    try:
        cols = {"LegislationText": ["LegislationID", "DocumentVersion", "Text",
                                    "DateTimeStamp", "HTMLText"],
                "Legislation": ["legislationID", "CondensedBillNo", "sessionyear"]}

        def dump(folder, bills, texts):
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "_columns.json").write_text(json.dumps(cols), encoding="utf-8")
            (folder / "Legislation.psv").write_text(
                "".join(f"{i}|{b}|{y}\n" for i, b, y in bills), encoding="utf-8")
            (folder / "LegislationText.psv").write_text(
                "".join(f"{i}|{lab}|{t}|01/05/2027 10:00:00|<p>{t}</p>\n" for i, lab, t in texts),
                encoding="utf-8")
        two = lambda i, word: [(i, "Introduced", f"{word} as introduced"),
                               (i, "As Amended by the House", f"{word} as amended")]
        # The current views: 2027's HB1, and -- before the turn -- 2025's HB2.
        dump(tmp / "db", [("1", "HB1", "2027"), ("3", "HB2", "2025")],
             two("1", "2027 HB1") + two("3", "current HB2"))
        # The frozen term: the same LegislationID 1 is a different bill there.
        dump(tmp / "db" / "term" / "2025-2026", [("1", "HB1", "2025"), ("2", "HB2", "2025")],
             two("1", "2025 HB1") + two("2", "frozen HB2"))
        (tmp / "db" / "document_versions.json").write_text(json.dumps(
            {"Introduced": {"sort": 20}, "As Amended by the House": {"sort": 30}}), encoding="utf-8")
        r = _run([sys.executable, str(Path(BBV.__file__).resolve()), "--site", "site",
                  "--manifest", "m.json"], cwd=tmp, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        man = json.loads((tmp / "m.json").read_text(encoding="utf-8"))
        assert {y: sorted(b) for y, b in man.items()} == {"2025": ["HB1", "HB2"], "2027": ["HB1"]}, man
        words = {p.relative_to(tmp / "site" / "versions").as_posix(): p.read_text(encoding="utf-8")
                 for p in (tmp / "site" / "versions").rglob("*.txt")}
        hb2 = " ".join(t for k, t in words.items() if k.startswith("2025/HB2."))
        hb1 = " ".join(t for k, t in words.items() if k.startswith("2025/HB1."))
        assert "current HB2" in hb2 and "frozen HB2" not in hb2, \
            f"2025's HB2 should come from the current dump while it holds it: {hb2!r}"
        assert "2025 HB1" in hb1 and "2027" not in hb1, \
            f"2025's HB1 should be the frozen term's own LegislationID 1: {hb1!r}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("2025-2026 kept from its frozen dump, joined to its own ids; the current dump "
                  "wins a bill-year it still holds")


@check("build", "a kept comparison is the comparison: the bill versions built with no cache, "
       "with the last run's, with a broken one and with another code's are the same files",
       needs=("build_bill_versions", "build_cache"))
def _versions_kept(build_bill_versions, build_cache):
    """build_bill_versions keeps every pair it compares in .build_cache/ (KEPT,
    build_cache.py, 23 October 2026), and the night takes that cache from the
    kit, so nothing about it may change a file. Driven end to end on a small
    tree: cold; warm; with the cache cut short; with a wrong answer planted
    under another code's signature; and with one under this code's in a shape
    compare() never gives -- the versions and the manifest come out the same
    each time, and only the warm run takes a kept answer. A run stopped by
    --limit leaves the cache as it was. And the signature reads code, not
    comments: a note changed is the same signature, a statement changed is
    not."""
    import gzip
    import hashlib
    BBV, BC = build_bill_versions, build_cache
    tmp = Path(tempfile.mkdtemp(prefix="gr-versions-kept-"))
    try:
        cols = {"LegislationText": ["LegislationID", "DocumentVersion", "Text",
                                    "DateTimeStamp", "HTMLText"],
                "Legislation": ["legislationID", "CondensedBillNo", "sessionyear"]}
        db = tmp / "db"
        db.mkdir()
        (db / "_columns.json").write_text(json.dumps(cols), encoding="utf-8")
        (db / "Legislation.psv").write_text("1|HB1|2025\n2|HB2|2025\n3|SB3|2026\n",
                                            encoding="utf-8")
        rows = []
        for i, word in (("1", "fees"), ("2", "roads"), ("3", "schools")):
            for lab, t in (("Introduced", f"An act relative to {word}. The fee is ten dollars."),
                           ("As Amended by the House",
                            f"An act relative to {word}. The fee is twelve dollars, paid yearly."),
                           ("As Amended by the Senate",
                            f"An act relative to {word} and towns. The fee is twelve dollars.")):
                rows.append(f"{i}|{lab}|{t}|01/05/2026 10:00:00|<p>{t}</p>\n")
        (db / "LegislationText.psv").write_text("".join(rows), encoding="utf-8")
        (db / "document_versions.json").write_text(json.dumps(
            {"Introduced": {"sort": 20}, "As Amended by the House": {"sort": 30},
             "As Amended by the Senate": {"sort": 40}}), encoding="utf-8")
        cache = tmp / ".build_cache" / f"{BBV.KEPT}.json.gz"

        def run(*extra):
            shutil.rmtree(tmp / "site", ignore_errors=True)
            (tmp / "m.json").unlink(missing_ok=True)
            r = _run([sys.executable, str(Path(BBV.__file__).resolve()), "--site", "site",
                      "--manifest", "m.json", *extra], cwd=tmp, capture_output=True, text=True,
                     timeout=180)
            assert r.returncode == 0, (r.stdout or "")[-300:] + (r.stderr or "")[-600:]
            got = {p.relative_to(tmp).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted((tmp / "site").rglob("*")) if p.is_file()}
            if (tmp / "m.json").exists():
                got["m.json"] = hashlib.sha256((tmp / "m.json").read_bytes()).hexdigest()
            return got, r.stdout

        def plant(sig, entries):
            cache.write_bytes(gzip.compress(json.dumps(
                {"format": BC.FORMAT, "sig": sig, "entries": entries}).encode("utf-8")))

        cold, said = run()
        assert "0 of 6 pairs compared before" in said and cache.exists(), said[-400:]
        assert sum(k.endswith(".json") and "-" in k.rsplit("/", 1)[-1] for k in cold) == 6, \
            f"the fixture wrote {sorted(cold)}, not six comparisons"
        doc = json.loads(gzip.decompress(cache.read_bytes()))
        assert len(doc["entries"]) == 6, f"{len(doc['entries'])} pairs kept of 6 compared"
        first = cache.read_bytes()
        warm, said = run()
        assert "6 of 6 pairs compared before and kept" in said, said[-400:]
        assert warm == cold, ("a kept comparison wrote another file: "
                              + ", ".join(k for k in cold if warm.get(k) != cold[k]))
        # The same answers, the same bytes: a night whose answers did not
        # change sends the kit nothing (the temporary file's name, with its
        # process id, once went into the gzip header).
        assert cache.read_bytes() == first, "the same answers were kept as other bytes"
        cache.write_bytes(cache.read_bytes()[:40])
        broken, said = run()
        assert broken == cold and "0 of 6" in said, "a cache cut short changed a file"
        wrong = {k: [[["+", "planted"]], [], 99, 99] for k in doc["entries"]}
        plant("0" * 64, wrong)
        other, said = run()
        assert other == cold and "0 of 6" in said, "another code's answer was taken"
        plant(doc["sig"], {k: [["+", "planted"], [], 1] for k in doc["entries"]})
        shaped, said = run()
        assert shaped == cold and "0 of 6" in said, "an answer not of compare()'s shape was taken"
        kept = cache.read_bytes()
        run("--limit", "1")
        assert cache.read_bytes() == kept, "a run stopped by --limit rewrote the cache"
        a, b, c = tmp / "a.py", tmp / "b.py", tmp / "c.py"
        a.write_text("x = 1  # one\n\n\ndef f():\n    return x\n", encoding="utf-8")
        b.write_text("# a note\nx = 1  # one, said otherwise\n\ndef f():\n    return x\n",
                     encoding="utf-8")
        c.write_text("x = 2  # one\n\n\ndef f():\n    return x\n", encoding="utf-8")
        assert BC._tokens(a) == BC._tokens(b) and BC._tokens(a) != BC._tokens(c), \
            "the signature reads comments, or misses a statement"
        assert BC.load("nothing-here", doc["sig"], folder=tmp) == {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("six pairs of three bills: cold, warm, cut short, another code's and a wrong "
                  "shape all write the same files, only the warm run takes a kept answer, and "
                  "--limit keeps nothing; a comment is not code to the signature")


@check("build", "a bill request that became a bill reads as introduced, not withdrawn",
       needs=("build_lsrs",))
def _request_became_bill(build_lsrs):
    """fetch_lsrs marks a request that leaves its list withdrawn, because the
    list cannot tell a withdrawal from an introduction, and in December and
    January that would have put "Withdrawn" on every request filed as a bill.
    build_lsrs reads the bills: a request whose number a bill carries as its
    LSR -- the year and the number, the list padding it and the bills not --
    reads Filed (and not Requested): the owner's words of 13 November 2026."""
    L = build_lsrs
    req = lambda n, gone: {"lsr": f"2027-{n:04d}", "session": 2027, "body": "HB",
                           "title": "t", "sponsor": "", "withdrawn": gone}
    lsrs = [req(1, True), req(2, True), req(3, False)]
    bills = {"2025-2026": {"HB45": {"lsr_year": "2025", "lsr_num": "1"}},
             "2027-2028": {"HB45": {"lsr_year": "2027", "lsr_num": "1"},
                           "SB7": {"lsr_year": "2027", "lsr_num": "0003"}}}
    became = L.became_bills(bills, lsrs)
    assert became == {"2027-0001": "HB 45", "2027-0003": "SB 7"}, became
    rows, _ = L.rows_from(lsrs, {}, became)
    got = {r["n"]: (r["status"], r["withdrawn"], r.get("introduced")) for r in rows}
    assert got == {"LSR 2027-0001": ("Filed", False, "HB 45"),
                   "LSR 2027-0002": ("Withdrawn", True, None),
                   "LSR 2027-0003": ("Filed", False, "SB 7")}, got
    rows, _ = L.rows_from(lsrs[2:], {}, {})
    assert rows[0]["status"] == "Requested" and "introduced" not in rows[0], rows[0]
    src = _source(_paths.locate("build_lsrs.py"))
    assert "rows_from(lsrs, roster(site, a.collected, year), became, year, winners," in src, \
        "build_lsrs no longer gives rows_from the bills"
    return "ok", "a request a bill carries reads as that bill; one that only left the list is withdrawn"


@check("build", "a bill request's Filed stop carries the day its bill was made one, on its row's rail, "
       "the page's and the card's; none where the bill gives none, and Requested never one",
       needs=("build_lsrs",))
def _request_filed_day(build_lsrs):
    """The owner, 15 November 2026: Filed is dated by the day the text was
    published, approved as the day the General Court's database says the
    request was made a numbered bill (Legislation.DateLSRBill), which
    build_data keeps on the bill's record as made_bill (_status_made_bill).
    Held, on build_lsrs.py run as the build runs it on a data/bills.json: a
    request whose bill gives the day is "filed" that day and its row's
    `rail` has it on Filed, reached; a request whose bill gives none, or
    something that is not a day, is Filed reached with no day; another
    term's bill of the request's LSR number lends nothing; no row dates
    Requested, which no source gives a day for. The page's rail
    (build_request_pages.rail_of) and the card's (app.js lsrCardHtml) draw
    the day under Filed and say it, and nothing under Requested. A request
    filed as a bill keeps its page until the bill is introduced
    (_request_stays_until_introduced), so the page shows the day too."""
    import build_request_pages as RP
    L = build_lsrs
    req = lambda n, **k: {"lsr": f"2027-{n:04d}", "session": 2027, "body": "HB", "title": f"t{n}",
                          "sponsor": "", "withdrawn": False, **k}
    bills = {"2025-2026": {"HB45": {"lsr_year": "2025", "lsr_num": "1", "made_bill": "2024-12-19"},
                           "HB60": {"lsr_year": "2025", "lsr_num": "3", "made_bill": "2024-12-20"}},
             "2027-2028": {"HB45": {"lsr_year": "2027", "lsr_num": "1", "made_bill": "2026-12-01"},
                           "SB7": {"lsr_year": "2027", "lsr_num": "0002"},
                           "HB9": {"lsr_year": "2027", "lsr_num": "4", "made_bill": "12/1/2026"}}}
    tmp = Path(tempfile.mkdtemp(prefix="gr-request-filed-day-"))
    try:
        (tmp / "site" / "idx").mkdir(parents=True)
        (tmp / "data").mkdir()
        (tmp / "site" / "meta.json").write_text(json.dumps({"terms": ["2027-2028"]}), encoding="utf-8")
        (tmp / "lsrs.json").write_text(json.dumps([req(1), req(2, withdrawn=True), req(3), req(4)]),
                                       encoding="utf-8")
        (tmp / "data" / "bills.json").write_text(json.dumps(bills), encoding="utf-8")
        r = _sealed_run([sys.executable, _paths.script("build_lsrs.py"), "--site", "site"],
                        cwd=str(tmp), capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        rows = json.loads((tmp / "site" / "idx" / "2027-requests.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    by = {x["n"]: x for x in rows}
    one, two, three, four = (by[f"LSR 2027-000{i}"] for i in (1, 2, 3, 4))

    def stops(x):
        return [(s["stop"], s["mark"], s.get("date")) for s in x["rail"]]
    assert one.get("filed") == "2026-12-01" and stops(one) == [
        ("Requested", "p", None), ("Filed", "p", "2026-12-01"), ("Introduced", "-", None)], (
        f"a request whose bill was made one on 1 December 2026: filed {one.get('filed')!r}, rail {stops(one)}")
    assert two.get("filed") is True and four.get("filed") is True \
        and stops(two)[1] == stops(four)[1] == ("Filed", "p", None), (
        "a request whose bill gives no day, or no day that is one, is not Filed reached with no day: "
        f"{two.get('filed')!r} {stops(two)}, {four.get('filed')!r} {stops(four)}")
    assert three["status"] == "Requested" and "filed" not in three \
        and stops(three)[1] == ("Filed", "-", None), (
        f"a request another term's bill shares an LSR number with reads {three['status']}, "
        f"filed {three.get('filed')!r}, rail {stops(three)}")
    assert not [x["n"] for x in rows for s in x["rail"] if s["stop"] != "Filed" and "date" in s], (
        "a request's rail dates a stop other than Filed")
    # The page's rail, as a page draws it.
    page = RP.rail_of(one)
    cells = page.split('<span class="stop ')[1:]
    assert len(cells) == 3 and "<small>" not in cells[0] + cells[2] \
        and '<small>Dec 1,<span class="ry"> 2026</span></small>' in cells[1] \
        and 'aria-label="Requested: made; Filed: text public, December 1, 2026; Introduced: not yet"' in page, (
        f"the page's rail does not put 1 December 2026 under Filed alone: {page}")
    assert "<small>" not in RP.rail_of(two) + RP.rail_of(four), (
        "the page's rail shows a day for a request whose bill gives none")
    # The card's, in node: the page's rail, the same stops and the same day.
    js = ("(() => { scope.setMeta({requests: {term: '2027-requests', year: 2027, abbr: "
          + json.dumps(L.ABBR) + "}}); return [" + ", ".join(
              "scope.lsrCardHtml(" + json.dumps(x) + ")" for x in (one, two)) + "]; })()")
    got = _app_js(js, names=("lsrCardHtml", "setMeta: x => (META = x)"))
    if got is None:
        return "skip", ("the rows and the page's rail hold; node, app.js or the stub is not here "
                        "for the card")
    assert page in got[0] and RP.rail_of(two) in got[1], (
        f"a request's card does not draw the page's rail, its Filed day with it: {got[0][:900]!r}")
    return "ok", ("Filed carries the day the bill was made one on the row, the page's rail and the "
                  "card, and none where the bill gives none or another term's bill shares the "
                  "number; Requested is never dated")


@check("build", "a bill request stays a request until its bill is introduced: filed, it keeps its page and "
       "card, says the bill it was filed as and follows it, and has a Bill Text tab once the night has read "
       "its text, which its file in the data API carries; introduced, it reads Introduced and forwards",
       needs=("build_lsrs", "build_request_pages", "build_pages", "api_records"))
def _request_stays_until_introduced(L, RP, BPG, AR):
    """The owner, 17 November 2026: "Officially LSRs do not become bills until the first session in
    January when they are introduced and referred to committees ... the bill text shows as a PDF on
    the lsr search page along with the co-sponsors". Until then a request forwarded to its bill's page
    the night its bill was on file, weeks before the bill was introduced, and no text of a request
    reached the site. Held on build_lsrs.py run as the build runs it, two nights of a fixture:

      - 20 December 2026: HB 45, made a bill on 19 December, its own rail's Introduced stop dated 6
        January 2027, is Filed, keeps its page, which says "Filed As HB 45" linked to the bill's page
        and follows bill:2027/HB45; SB 7, whose rail has an undated Introduced (a "To Be Introduced"
        plan), is Filed; a request whose text the list links and the night has read is Filed, with a
        Bill Text tab after the Summary holding the text with its margin off, said to be read by
        machine, the PDF linked, and the text in its API file and not in its row; one filed and not
        read says so; meta.json counts none introduced;
      - 7 January 2027: HB 45's request reads Introduced, its rail's last stop reached and dated 6
        January, its page gone and its address a 301 to the bill's; SB 7's is still Filed.

    And the card, in node: the same tabs, the text fetched once from the request's API file, and the
    bill it was filed as on its Summary."""
    import contextlib
    import io
    tmp = Path(tempfile.mkdtemp(prefix="gr-request-stays-"))
    saved = L.REQUEST_TEXTS
    pdf = "https://gc.nh.gov/x/2027-0003.pdf"
    req = lambda n, **k: {"lsr": f"2027-{n:04d}", "session": 2027, "body": "HB", "title": f"relative to {n}.",
                          "sponsor": "Ann Lee", "cosponsors": [], "withdrawn": False, **k}

    def night(day):
        r = _sealed_run([sys.executable, _paths.script("build_lsrs.py"), "--site", "site"], cwd=str(tmp),
                        capture_output=True, text=True, timeout=120,
                        env=dict(os.environ, GRANITE_BUILD_DATE=day))
        assert r.returncode == 0, (r.stderr or r.stdout)[-400:]
        rows = json.loads((tmp / "site" / "idx" / "2027-requests.json").read_text(encoding="utf-8"))
        meta = json.loads((tmp / "site" / "meta.json").read_text(encoding="utf-8"))["requests"]
        return {x["n"]: x for x in rows}, meta, r.stdout

    def stops(x):
        return [(s["stop"], s["mark"], s.get("date")) for s in x["rail"]]
    try:
        site = tmp / "site"
        (site / "idx").mkdir(parents=True)
        (tmp / "data").mkdir()
        (tmp / "archive" / "lsr_text").mkdir(parents=True)
        (site / "meta.json").write_text(json.dumps({"terms": ["2027-2028", "2025-2026"]}), encoding="utf-8")
        (site / "idx" / "2027-2028.json").write_text(json.dumps([
            {"id": "HB45", "rail": [["Ip", "2027-01-06"], ["Ho"]]}, {"id": "SB7", "rail": [["Ip"], ["So"]]}]),
            encoding="utf-8")
        (tmp / "data" / "bills.json").write_text(json.dumps({"2027-2028": {
            "HB45": {"lsr_year": "2027", "lsr_num": "1", "made_bill": "2026-12-19"},
            "SB7": {"lsr_year": "2027", "lsr_num": "2"}}}), encoding="utf-8")
        (tmp / "lsrs.json").write_text(json.dumps([req(1), req(2, body="SB"), req(3, text_pdf=pdf), req(4),
                                                   req(5, text_pdf=pdf.replace("0003", "0005"))]),
                                       encoding="utf-8")
        (tmp / "archive" / "lsr_text" / "2027-0003.txt").write_text(
            "      HB 1 - AS INTRODUCED\n\n\n      AN ACT relative to 3.\f\n      1 Section one.   \n",
            encoding="utf-8")
        by, meta, said = night("2026-12-20")
        one, two, three, four, five = (by[f"LSR 2027-000{i}"] for i in (1, 2, 3, 4, 5))
        assert one["status"] == "Filed" and "moved_to" not in one and one.get("introduced") == "HB 45" \
            and one.get("bill_at") == "bill/2027/hb45" and stops(one) == [
                ("Requested", "p", None), ("Filed", "p", "2026-12-19"), ("Introduced", "-", None)], (
            f"a request filed as HB 45 and not yet introduced: {one}")
        assert two["status"] == "Filed" and "moved_to" not in two and "introduced_on" not in two, (
            f"a bill whose introduction is only planned forwarded its request: {two}")
        assert three["status"] == "Filed" and three.get("filed") is True and three.get("text_pdf") == pdf \
            and three.get("text_on_file") is True and stops(three)[1] == ("Filed", "p", None), three
        assert five["status"] == "Filed" and "text_on_file" not in five, five
        assert four["status"] == "Requested" and "text_on_file" not in four and "text_pdf" not in four, four
        assert meta.get("introduced") == 0, meta
        text = L.request_text("2027-0003", tmp / "archive" / "lsr_text")
        assert text == "HB 1 - AS INTRODUCED\n\nAN ACT relative to 3.\n\n1 Section one.", repr(text)
        # The pages, the text read where the night put it.
        L.REQUEST_TEXTS = tmp / "archive" / "lsr_text"
        (site / "bills.html").write_text(_source("src/pages/bills.html"), encoding="utf-8")
        req_meta = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027}
        (site / "meta.json").write_text(json.dumps({"terms": ["2027-2028"], "requests": req_meta}),
                                        encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            n, _gone, moved = RP.write(site, "https://x")
        assert n == 5 and moved == 0, (n, moved)
        page = lambda k: (site / "request" / f"2027-000{k}.html").read_text(encoding="utf-8")
        tabs = lambda html: re.findall(r'<button[^>]*role="tab"[^>]*>([^<]*)<', html)
        p1, p3, p5 = page(1), page(3), page(5)
        assert '<dt>Filed As</dt><dd><a href="bill/2027/hb45">HB 45</a></dd>' in p1 \
            and 'window.GR_FOLLOW="bill:2027/HB45";' in p1, "a filed request's page does not say its bill"
        assert tabs(p3) == ["Summary", "Bill Text"] and 'id="pane_LSR20270003_6"' in p3 \
            and '<pre class="vtext" translate="no">HB 1 - AS INTRODUCED\n\nAN ACT relative to 3.' in p3 \
            and "read by machine" in p3 and f'href="{pdf}"' in p3 and "Not public yet" not in p3, (
            f"a request whose text is in has no Bill Text tab with it: {tabs(p3)}")
        assert tabs(p5) == ["Summary", "Bill Text"] and "<b>Filed.</b> Its text is public, and is added here once this " \
            "site has read it." in p5, "a filed request whose text is not read does not say so"
        assert "Not public yet" in page(4) and 'window.GR_FOLLOW="lsr:2027-0004";' in page(4), \
            "a request still requested lost its Summary's note or its own Follow"
        row3, rec3 = AR.request_record(three, "2027-0003", 2027)
        _row, rec4 = AR.request_record(four, "2027-0004", 2027)
        assert rec3["text"] == text and rec3["text_pdf"] == pdf and "text" not in row3 \
            and rec4["text"] is None and rec4["text_pdf"] == "", (row3, rec3, rec4)
        # The card: the same tabs, the text fetched once from the API file, the bill it was filed as.
        L.REQUEST_TEXTS = saved
        # The answer arrives only when go() says, as a fetch's does later: a tab drawn again while it
        # is on its way asks nothing more.
        js = ("(() => { const asked = [], pend = [];"
              " const later = () => { let cbs = [], val, done = false; const p = {then(f) {"
              " const q = later(); cbs.push(v => q.resolve(f(v))); if (done) flush(); return q.p; },"
              " catch() { return p; }}; const flush = () => { const c = cbs; cbs = []; c.forEach(f => f(val)); };"
              " return {p, resolve(v) { val = v; done = true; flush(); }}; };"
              " globalThis.fetch = u => { asked.push(u); const d = later(); pend.push(() => d.resolve({ok: true,"
              " json: () => ({text: " + json.dumps(text) + "})})); return d.p; };"
              " const b = " + json.dumps(three) + ";"
              " const first = scope.lsrPane(b, '6'), again = scope.lsrPane(b, '6');"
              " pend.splice(0).forEach(f => f());"
              " const second = scope.lsrPane(b, '6');"
              " return {tabs: scope.lsrTabs(b), first, again, second, asked, plain: scope.lsrTabs("
              + json.dumps(four) + "), summary: scope.lsrPane(" + json.dumps(one) + ", '0'),"
              " status: Object.keys(scope.REQ_STATUS)}; })()")
        card = _app_js(js, names=("lsrPane", "lsrTabs", "REQ_STATUS"))
        if card is not None:
            assert card["tabs"] == [["0", "Summary", 0], ["6", "Bill Text", 1]] \
                and card["plain"] == [["0", "Summary", 0], ["6", "Bill Text", "0"]], card["tabs"]
            assert "Loading the text" in card["first"] and "Loading the text" in card["again"] \
                and len(card["asked"]) == 1 \
                and card["asked"][0].endswith("/api/requests/2027/0003.json") \
                and '<pre class="vtext" translate="no">HB 1 - AS INTRODUCED' in card["second"] \
                and "read by machine" in card["second"] and pdf in card["second"], card
            assert '<b>Filed As:</b> <a href="bill/2027/hb45">HB 45</a>' in card["summary"], card["summary"]
            assert card["status"] == ["Requested", "Filed", "Introduced", "Withdrawn"], card["status"]
        # Introduced: the request says so, its rail reaches the stop, and its address forwards.
        (site / "meta.json").write_text(json.dumps({"terms": ["2027-2028", "2025-2026"]}), encoding="utf-8")
        by, meta, said = night("2027-01-07")
        one, two = by["LSR 2027-0001"], by["LSR 2027-0002"]
        assert one["status"] == "Introduced" and one.get("introduced_on") == "2027-01-06" \
            and one.get("moved_to") == "bill/2027/hb45" and stops(one)[2] == ("Introduced", "p", "2027-01-06"), one
        assert two["status"] == "Filed" and "moved_to" not in two, two
        assert meta.get("introduced") == 1, meta
        (site / "meta.json").write_text(json.dumps({"terms": ["2027-2028"], "requests": req_meta}),
                                        encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            n, gone, moved = RP.write(site, "https://x")
        assert n == 4 and moved == 1 and gone == 1 and not (site / "request" / "2027-0001.html").exists(), \
            (n, gone, moved)
        assert "/request/2027-0001 /bill/2027/hb45 301\n" in BPG.moved_requests(site), BPG.moved_requests(site)
    finally:
        L.REQUEST_TEXTS = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("filed and not introduced: its page and card, Filed As HB 45, the bill's Follow, a Bill "
                  "Text tab with the text read (in the API file, not the row); introduced: Introduced, "
                  "dated, forwarding; an undated introduction is not one" + ("" if card is not None else
                                                                             "; node not here for the card"))


@check("build", "meta.json counts the requests introduced on a day of their own year apart from those "
       "introduced before it, and the bill search opens on the requests until one of the first is",
       needs=("build_lsrs",))
def _requests_first_until_introduced(L):
    """The owner, 17 November 2026: requests "do not become bills until the first session in January
    when they are introduced and referred to committees", read by the manager as: the bill search
    keeps opening on the 2027 requests through December, until bills are introduced in January.
    build_lsrs.py, run as the build runs it on a fixture: an Organization Day resolution introduced
    and adopted on 2 December 2026 and a bill introduced on 6 January 2027, each a request's.
    On 5 December meta.requests counts one introduced and none in the session, and app.js's
    requestsFirst opens the search on the requests though 2027-2028 is published; on 7 January it
    counts two and one, and the search opens on 2027-2028."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-requests-first-"))
    req = lambda n, body: {"lsr": f"2027-{n:04d}", "session": 2027, "body": body, "title": f"t{n}.",
                           "sponsor": "Ann Lee", "cosponsors": [], "withdrawn": False}
    metas = {}
    try:
        (tmp / "site" / "idx").mkdir(parents=True)
        (tmp / "data").mkdir()
        (tmp / "site" / "idx" / "2027-2028.json").write_text(json.dumps([
            {"id": "HR1", "rail": [["Ip", "2026-12-02"], ["Hp", "2026-12-02"]]},
            {"id": "HB45", "rail": [["Ip", "2027-01-06"], ["Ho"]]}]), encoding="utf-8")
        (tmp / "data" / "bills.json").write_text(json.dumps({"2027-2028": {
            "HR1": {"lsr_year": "2027", "lsr_num": "1"}, "HB45": {"lsr_year": "2027", "lsr_num": "2"}}}),
            encoding="utf-8")
        (tmp / "lsrs.json").write_text(json.dumps([req(1, "HR"), req(2, "HB"), req(3, "HB")]),
                                       encoding="utf-8")
        for day in ("2026-12-05", "2027-01-07"):
            (tmp / "site" / "meta.json").write_text(json.dumps({"terms": ["2027-2028", "2025-2026"]}),
                                                    encoding="utf-8")
            r = _sealed_run([sys.executable, _paths.script("build_lsrs.py"), "--site", "site"], cwd=str(tmp),
                            capture_output=True, text=True, timeout=120,
                            env=dict(os.environ, GRANITE_BUILD_DATE=day))
            assert r.returncode == 0, (r.stderr or r.stdout)[-400:]
            metas[day] = json.loads((tmp / "site" / "meta.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    dec, jan = (metas[d]["requests"] for d in ("2026-12-05", "2027-01-07"))
    assert (dec.get("introduced"), dec.get("introduced_in_session")) == (1, 0), dec
    assert (jan.get("introduced"), jan.get("introduced_in_session")) == (2, 1), jan
    js = ("(() => [" + ", ".join(
        f"scope.defaultTerm({json.dumps(metas[d])}, new Date('{d}T17:00:00Z'))" for d in metas) + "])()")
    got = _app_js(js, names=("defaultTerm", "requestsFirst", "electionDayOf", "nhDay"))
    if got is None:
        return "skip", "meta.json's counts hold; node, app.js or the stub is not here for the search"
    assert got == ["2027-requests", "2027-2028"], (
        f"the search opens on {got[0]} on 5 December and {got[1]} on 7 January")
    return "ok", ("an Organization Day resolution introduced on 2 December counts as introduced and not "
                  "in the session, and the search stays on the requests; a bill introduced on 6 January "
                  "counts in it, and the search opens on 2027-2028")


@check("build", "a bill request's status is Requested or Filed (or Withdrawn); its History is the earlier "
       "bills of exactly its title; its accepted co-sponsors are shown as person chips on the card and "
       "the page; its LSR is explained on its page by the glossary's popover and not on the card's link; its "
       "topic is printed by name, and Miscellaneous not at all; its card has no Follow and has its rail",
       needs=("build_lsrs",))
def _request_cards_like_bills(build_lsrs):
    """The owner, 13 November 2026: tabs and an expanded view on the cards,
    Requested and Filed as the Status filter, History from earlier bills of
    the same title ("certain matches only"), co-sponsors shown once the
    source lists them, the same chips as a bill's, a tooltip for LSR.

    And 14 November 2026: "remove the topic from title label, remove the LSR
    tooltip from the hyperlink on the card and just show it on the lsr page,
    and assign topics not yet assigned to misc". Held: the card's number is a
    plain link, with no <abbr> and no "Legislative Service Request"; the page
    keeps both; the card's byline and the page's Subject give the topic by its
    name with no "(from the title)"; a request that is Miscellaneous (the
    title placed it nowhere) prints the word on neither, as a bill's card and
    page do not print the topic model's.

    And 15 November 2026: "The LSR tooltip does not appear to use the same
    mechanism as the other tooltip definitions like -FN ... removing the follow
    button on the unexpanded cards, adding the rail on the card". Held: the
    page's head marks LSR for the term popover (glossary.json's LSR entry) and
    carries no <abbr>; no card carries a Follow, shut or open, withdrawn or a
    bill; every card draws the row's three stops in its head (Requested
    reached, Filed open, crossed when withdrawn, reached once a bill), and a
    row with none draws no rail at all."""
    import tempfile
    import build_request_pages as RP
    L = build_lsrs
    # The status rule and the exact-title rule.
    assert L.title_key("  Relative  to TIDES. ") == L.title_key("relative to tides") \
        and L.title_key("relative to tides") != L.title_key("relative to the tides"), (
        "a title is compared after case, spacing and final punctuation only")
    earlier = {L.title_key("relative to tides"): [
        {"id": "HB7", "n": "HB 7", "year": 2024, "term": "2023-2024", "word": "Died", "cls": "s-done"},
        {"id": "HB9", "n": "HB 9", "year": 2028, "term": "2027-2028", "word": "In Committee", "cls": "s-active"}]}
    who = {"annlee": ("Rep. Ann Lee (D - Rock 1)", "ann-lee-rock-1"),
           "bobroe": ("Bob Roe (R)", "bob-roe-elect", "H")}
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "Relative to Tides.",
             "sponsor": "Ann Lee", "cosponsors": ["Bob Roe", "Zed Nobody"], "withdrawn": False},
            {"lsr": "2027-0002", "session": 2027, "body": "HB", "title": "relative to the tides.",
             "sponsor": "Ann Lee", "withdrawn": False},
            {"lsr": "2027-0003", "session": 2027, "body": "HB", "title": "x", "sponsor": "Ann Lee",
             "withdrawn": True},
            {"lsr": "2027-0004", "session": 2027, "body": "HB", "title": "y", "sponsor": "Ann Lee",
             "withdrawn": True}]
    rows, _ = L.rows_from(lsrs, who, {"2027-0004": "HB 5"}, 2027, None, earlier)
    by = {r["n"]: r for r in rows}
    assert [by[f"LSR 2027-000{i}"]["status"] for i in (1, 2, 3, 4)] == [
        "Requested", "Requested", "Withdrawn", "Filed"], "Requested: no bill; Filed: its bill exists"
    assert [h["n"] for h in by["LSR 2027-0001"]["history"]] == ["HB 7"], (
        "History is the bills of an earlier session with exactly the title (not a later term's)")
    assert "history" not in by["LSR 2027-0002"], "a title that differs by a word has no History"
    co = by["LSR 2027-0001"]["cosponsors"]
    assert [c["label"] for c in co] == ["Bob Roe (R)", "Zed Nobody"] and co[0].get("party") == "R" \
        and "party" not in co[1], f"co-sponsors: a member-elect with a party, a stranger as typed: {co}"
    # A topic the title gave, and one it did not (request_topics.assign writes both so).
    by["LSR 2027-0001"].update(topic="Education - General", topic_by="title")
    by["LSR 2027-0002"].update(topic="Miscellaneous", topic_by="title")
    # earlier_bills reads the search's own rows, titles compared the same way.
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "idx").mkdir()
        (site / "idx" / "2023-2024.json").write_text(json.dumps([
            {"id": "HB7", "n": "HB 7", "year": 2024, "term": "2023-2024", "title": "RELATIVE TO TIDES",
             "chip": "Died", "kind": "done", "status": "Killed"}]), encoding="utf-8")
        got = L.earlier_bills(site, ["2023-2024", "2021-2022"])
        assert [b["word"] for b in got[L.title_key("relative to tides")]] == ["Died"] \
            and got[L.title_key("relative to tides")][0]["cls"] == "s-done", got
        # THE PAGE: tabs, chips, the abbreviation.
        (site / "bills.html").write_text(_source("src/pages/bills.html"),
                                         encoding="utf-8")
        (site / "legislators.json").write_text(json.dumps([
            {"slug": "ann-lee-rock-1", "party": "D", "display_full": "Rep. Ann Lee (D - Rock 1)"}]),
            encoding="utf-8")
        (site / "elect_pages.json").write_text(json.dumps({"pages": [
            {"slug": "bob-roe-elect", "name": "Bob Roe", "party": "R"}]}), encoding="utf-8")
        req = {"term": "2027-requests", "label": "2027 Bill Requests", "year": 2027, "abbr": L.ABBR}
        (site / "meta.json").write_text(json.dumps({"requests": req}), encoding="utf-8")
        (site / "idx" / "2027-requests.json").write_text(json.dumps(rows), encoding="utf-8")
        RP.write(site, "https://x")
        page = (site / "request" / "2027-0001.html").read_text(encoding="utf-8")
        plain = (site / "request" / "2027-0002.html").read_text(encoding="utf-8")
    # The co-sponsors open the Summary, as a bill's sponsors do (24 November 2026): no Sponsors tab.
    for want in ('<h1 class="rh1"><span data-term="LSR">LSR</span> 2027-0001',
                 '<section class="w4" id="sponsors">', 'id="tab_LSR20270001_7"', 'href="bill/2024/hb7"', ">Died</span>",
                 "LSR stands for Legislative Service Request.", '<li aria-current="page">LSR 2027-0001</li>',
                 'class="mchip p-R"', 'class="mchip p-D"'):
        assert want in page, f"a request's page lacks {want!r}"
    # WHAT LSR STANDS FOR, BY THE SITE'S TERM POPOVER (the owner, 15 November
    # 2026: "the same mechanism as the other tooltip definitions like -FN"):
    # the head's number marked for components.js, which glossary.json answers;
    # no <abbr>, whose title only a mouse could read.
    assert "<abbr" not in page and page.count('data-term="LSR"') == 1 \
        and (RP.C.WORDBOOK.get("glossary") or {}).get("LSR", {}).get("name") == "Legislative Service Request", (
        "a request's page explains LSR otherwise than by the glossary's popover, or the glossary has no LSR")
    assert 'id="tab_LSR20270002_7"' not in plain and 'id="sponsors"' not in plain \
        and 'id="tab_LSR20270001_4"' not in page, (
        "a request with no earlier bill and no co-sponsor has a tab or a section for them, or one with "
        "co-sponsors a Sponsors tab")
    assert "<dt>Subject</dt><dd>Education - General" in page and "(from the title)" not in page, (
        "a request's page does not give its topic by name as a bill's page gives its subject")
    assert "<dt>Subject</dt>" not in plain and "Miscellaneous" not in plain, (
        "a request's page prints Miscellaneous, which a bill's page does not print for the topic model's")
    # THE CARD, in node: the bill card's tabs inside, the same chips, no abbreviation.
    js = ("(() => { scope.setMeta({requests: {term: '2027-requests', year: 2027, abbr: " + json.dumps(L.ABBR)
          + "}}); const r = " + json.dumps(by["LSR 2027-0001"]) + "; const plain = "
          + json.dumps(by["LSR 2027-0002"]) + "; const gone = " + json.dumps(by["LSR 2027-0003"])
          + "; const billed = " + json.dumps(by["LSR 2027-0004"]) + "; const shut = scope.lsrCardHtml(r); "
          "scope.openCards.add(r.id); scope.openTab[r.id] = '7'; return {shut, open: scope.lsrCardHtml(r), "
          "plain: scope.lsrCardHtml(plain), gone: scope.lsrCardHtml(gone), billed: scope.lsrCardHtml(billed), "
          "bare: scope.lsrCardHtml(Object.assign({}, plain, {rail: []}))}; })()")
    got = _app_js(js, names=("lsrCardHtml", "openCards", "openTab", "setMeta: x => (META = x)"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    shut, op, pl = got["shut"], got["open"], got["plain"]
    # NO FOLLOW ON THE CARD, AND THE RAIL A BILL'S CARD HAS (the owner, 15
    # November 2026: "removing the follow button on the unexpanded cards,
    # adding the rail on the card"): the row's three stops in the card's head,
    # as the request's page draws them; Follow is the page's, after Cite.
    def card_stops(html):
        rail = re.search(r'<span class="rail dated".*?</span></span>(?=\s*<|$)', html, re.S)
        return re.findall(r'<span class="stop s-(\w+)"><b>.*?</b><i>(.*?)</i>', rail.group(0), re.S) if rail else []
    for label, html in (("shut", shut), ("open", op), ("plain", pl), ("withdrawn", got["gone"]),
                        ("a bill now", got["billed"])):
        assert "followbox" not in html and "data-fkey" not in html and ">Follow<" not in html, (
            f"a request's card ({label}) still carries a Follow")
    assert card_stops(shut) == [("p", "Requested"), ("o", "Filed"), ("o", "Introduced")] \
        and shut.index('class="rail dated"') < shut.index('class="cbody"'), (
        f"a request's card does not draw its three stops in its head: {card_stops(shut)}")
    assert [s for s, _ in card_stops(got["gone"])] == ["p", "x", "o"] \
        and [s for s, _ in card_stops(got["billed"])] == ["p", "p", "o"], (
        f"the card's rail: withdrawn {card_stops(got['gone'])}, filed {card_stops(got['billed'])}")
    assert 'class="rail' not in got["bare"], "a request's card with no stops draws a rail (a bill's four?)"
    assert 'class="mchip p-D"' in shut \
        and 'class="ctitle"' in shut and 'aria-expanded="false"' in shut and "<div class=\"cbody\" hidden>" in shut, (
        f"a request's card is not a bill card with a person chip: {shut[:600]!r}")
    # The card's head, that is: opened, its Summary says what LSR stands for in About Requests, as
    # the page's does (the owner, 17 November 2026; _request_card_summary_explains).
    assert '<a href="request/2027-0001">LSR 2027-0001</a></span>' in shut and "<abbr" not in shut \
        and "Legislative Service Request" not in shut[:shut.index('class="cbody"')], (
        f"a request's card links its number with a tooltip, or not plainly: {shut[:600]!r}")
    assert "Education - General" in shut and "(from the title)" not in shut, (
        "a request's card does not print its topic by name alone")
    assert "Miscellaneous" not in pl and "<abbr" not in pl, (
        "a request's card prints Miscellaneous, or its number has a tooltip")
    assert 'data-t="4"' not in shut and 'data-t="7"' in shut and 'data-t="0"' in shut \
        and '<h2 class="w4h">Sponsors</h2>' in shut, (
        "a request with co-sponsors and a History has not its Summary, opening with them, and its History")
    assert 'aria-expanded="true"' in op and '<div class="cbody">' in op \
        and 'id="pane_LSR20270001_7" aria-labelledby="tab_LSR20270001_7" tabindex="0" data-t="7">' in op \
        and 'href="bill/2024/hb7"' in op and 'class="mchip p-R"' in op, (
        "the open card does not show its History tab and the co-sponsors' chips")
    assert 'data-t="7"' not in pl and 'data-t="4"' not in pl, "a plain request has a Sponsors or a History tab"
    return "ok", ("Requested/Filed/Withdrawn by the bill's existence; History by exact title and an earlier "
                  "session; co-sponsors as chips on the card and the page; LSR explained on the page by the "
                  "glossary's popover, the card's number a plain link; the topic by name, Miscellaneous "
                  "printed on neither; no Follow on the card, and its three stops in its head")


@check("build", "next session's bill requests are listed under the year they name, whichever year "
       "that is", needs=("build_lsrs",))
def _requests_year_their_own(build_lsrs):
    """private/UNATTENDED_AUDIT_2026-10-18.md, section 4.3.2: build_lsrs named
    the requests' term "2027-requests" and its label "2027 Bill Requests" in
    two literals, build_all named its file, and app.js said "for 2027" and
    "replaced by the 2027 bills", so the requests for 2028, filed from
    September 2027, would have been listed as 2027's. The year is now the
    newest session the requests name. Held here: build_lsrs run on a list of
    2027's requests and 2028's writes idx/2028-requests.json alone, meta.json
    naming its term, label and year, every row 2028's -- one with no session
    field by its number -- and the earlier session's left out and counted;
    and app.js and build_all name no requests' year of their own."""
    import json as _json
    tmp = Path(tempfile.mkdtemp(prefix="gr-requests-year-"))
    try:
        (tmp / "site" / "idx").mkdir(parents=True)
        (tmp / "site" / "meta.json").write_text(_json.dumps({"terms": ["2027-2028"]}), encoding="utf-8")
        (tmp / "site" / "idx" / "2027-requests.json").write_text("[]", encoding="utf-8")
        req = lambda n, **k: {"lsr": n, "body": "HB", "title": "t", "sponsor": "", "withdrawn": False, **k}
        (tmp / "lsrs.json").write_text(_json.dumps([
            req("2027-0001", session=2027, withdrawn=True), req("2028-0001", session=2028),
            req("2028-0002")]), encoding="utf-8")
        r = _sealed_run([sys.executable, _paths.script("build_lsrs.py"), "--site", "site"],
                        cwd=str(tmp), capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        files = sorted(p.name for p in (tmp / "site" / "idx").glob("*-requests.json"))
        meta = _json.loads((tmp / "site" / "meta.json").read_text(encoding="utf-8"))["requests"]
        rows = _json.loads((tmp / "site" / "idx" / "2028-requests.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert files == ["2028-requests.json"], f"build_lsrs left {files}"
    assert (meta["term"], meta["label"], meta["year"], meta["n"]) == (
        "2028-requests", "2028 Bill Requests", 2028, 2), meta
    assert {(x["n"], x["year"], x["term"]) for x in rows} == {
        ("LSR 2028-0001", 2028, "2028-requests"), ("LSR 2028-0002", 2028, "2028-requests")}, rows
    assert "1 request(s) of an earlier session left out" in r.stdout, r.stdout
    app = _source(_paths.locate("app.js"))
    plan = _source(_paths.locate("build_all.py"))
    stuck = [s for s in ('"for 2027"', "the 2027 bills", '"2027-requests"') if s in app] + \
            [s for s in ("2027-requests.json", '"the 2027 bill requests"') if s in plan]
    assert not stuck, f"a requests' year written in by hand: {stuck}"
    assert "for ${reqYear()}" in app and "a numbered {year} bill." in app \
        and '{year:esc(reqYear())});' in app, \
        "app.js no longer takes the requests' year from meta.json"
    return "ok", ("2028's requests listed as 2028's, alone, the 2027 file gone and its request "
                  "counted; app.js and build_all name no year of their own")


@check("naming", "a sponsorship is filed under the member its bill page links, and a name is that member only where they sat",
       needs=("build_site_v2", "member_links"))
def _sponsor_filing(build_site_v2, member_links):
    """bill_sponsor_list linked a sponsor's page by roster id or by name, and
    filed the bill under the record's own id -- an employee number or nothing on
    every 2023-2024 record -- so 349 of 406 members' Sponsored tabs missed
    11,855 bills their bill pages credited them with. Filed under the member
    the page links now, once per bill, and a record matched on a name is that
    member only if they sat in that chamber that term: Rep. Patrick Long of
    Hillsborough 23 sponsored in 2023-2024 and is not the Rep. Patrick Long who
    sits for Hillsborough 26 now.
    """
    from collections import defaultdict
    B, ML = build_site_v2, member_links
    legs = {"43": {"id": "43", "name": "Watters, David", "chamber": "S", "party_code": "D",
                   "district": "4", "county": "Strafford"},
            "11177": {"id": "11177", "name": "Long, Patrick", "chamber": "H", "party_code": "D",
                      "district": "26", "county": "Hillsborough"}}
    by_sort = {B.sort_name(m["name"]): m for m in legs.values()}
    by_name = {B.name_key(m["name"]): m for m in legs.values()}
    votes = {"43": [{"year": "2024", "body": "S"}], "11177": [{"year": "2025", "body": "H"}],
             "376885": [{"year": "2012", "body": "H"}]}
    seats = ML.seats_held(legs.values(), votes, {"43": ["376885"]}, "2025-2026")
    assert seats["43"] == {("2011-2012", "H"), ("2023-2024", "S"), ("2025-2026", "S")}, seats["43"]
    sponsors = {"2023-2024": {"CACR13": [
        {"member_id": "", "name": "David Watters", "chamber": "S", "prime": True},
        {"member_id": "376885", "name": "David Watters", "chamber": "S", "prime": False},
        {"member_id": "376696", "name": "Patrick Long", "chamber": "H", "prime": False}]}}
    sponsored = defaultdict(list)
    sp = B.bill_sponsor_list("CACR13", {"designation": "CACR 13", "title": "a resolution"},
                             "2024", "2023-2024", "2025-2026", sponsors, legs, by_sort, by_name,
                             sponsored, seats)
    assert [(x["bill"], x["prime"]) for x in sponsored["43"]] == [("CACR13", True)], (
        f"Watters's CACR 13 filed as {sponsored['43']}: wanted once, under his roster id, as prime")
    assert "11177" not in sponsored and sponsored.get("376696"), (
        "the 2023-2024 Patrick Long's sponsorship went to the Rep. Patrick Long sitting now")
    assert [bool(s["slug"]) for s in sp] == [True, True, False], (
        "the bill page links " + str([s["slug"] for s in sp]))
    return "ok", ("a record with no id or an employee number filed once under the member its page links; "
                  "a same-named member who did not sit that term neither linked nor credited")


@check("naming", "a bill filed under a member's earlier number links their page and keeps the seat it prints",
       needs=("build_site_v2",))
def _sponsor_numbers_join_their_person(build_site_v2):
    """9 November 2026: Sen. David Rochefort's 2025 House bills, filed as Rep.
    for Grafton 1, name the employee number of that seat (409162), which the
    sitting roster does not answer; the register (person_numbers.json) gives it
    to the person the site already joins to the senator. build_bills now reads
    the register's numbers, and a row whose chamber is not the member's now
    keeps the seat the record prints, linked to the page they have.
    """
    import contextlib
    import io
    B = build_site_v2
    T = "2025-2026"
    sen = {"id": "11458", "name": "Doe, Dana", "chamber": "S", "party_code": "R",
           "district": "1", "county": "", "county_abbr": ""}
    legs = {"11458": sen}
    sponsors = {T: {"HB10": [
        {"member_id": "409162", "name": "Dana Doe", "chamber": "H", "prime": True,
         "source": "bill status page", "party": "R", "county": "Graf", "district": "01"}]}}
    bills = {T: {"HB10": {"bill": "HB10", "lsr": "2025-0010", "lsr_year": "2025",
                          "title": "relative to a fixture.", "chamber": "H",
                          "designation": "HB 10"}}}
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-numbers-"))
    got = []
    try:
        os.chdir(tmp)
        for numbers in ({"409162": "10614"}, None):
            out = tmp / ("site" + str(len(got)))
            out.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                B.build_bills(out, bills, {}, {}, {}, sponsors, {}, {}, {}, {}, {}, {}, {}, {}, {},
                              legs, {B.sort_name(sen["name"]): sen}, {B.name_key(sen["name"]): sen},
                              {}, seats={"11458": [("2025-2026", "S")]}, former={}, links={"11458": ["10614"]},
                              numbers=numbers)
            page = json.loads((out / "bills" / "2025" / "HB10.json").read_text(encoding="utf-8"))
            got.append((page["sponsors"][0].get("display_full"), page["sponsors"][0].get("slug")))
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    assert got[0] == ("Rep. Dana Doe (R - Graf 1)", B.own_slug(sen)), (
        f"a bill filed under a member's earlier House number reads {got[0]}")
    assert not got[1][1], "with no register the number linked anyway (the fixture is stale)"
    return "ok", ("a bill status page's employee number is its person through the register: "
                  "linked to their page, at the seat it prints")


@check("build", "the Sponsor filter's members, a file a term (site/sponsors/<term>.json): keyed as the index and "
       "app.js key them, each once, House then Senate by surname; the sitting term's every sitting member and "
       "every member who left, marked, with their district's towns; a stale term's file removed",
       needs=("build_site_v2", "sponsor_roster"))
def _sponsor_roster_file(build_site_v2, sponsor_roster):
    """The owner, 19 November 2026: the Sponsor filter lists the term's members (app.js spPicker). On a
    fixture: build_bills, given `people`, fills it with everyone the term's rows name, under the keys the
    row's `sponsor` (as app.js spKey reads it) and `cosp` carry, a co-sponsor by the label their own record
    gives; add_sitting adds the sitting member who filed nothing and the member who left having filed
    nothing, marks the members who left (f) and gives each their district's towns, the padded "Belk 06" the
    roster's "Belk 6"; a former member of another term is not listed; write() lists the House and then the
    Senate by surname and removes a term's file an earlier build left. sp_key and app.js's spKey agree on
    every shape a row takes, a 1989-1998 sponsor left as printed among them."""
    import contextlib
    import io
    B, SR = build_site_v2, sponsor_roster
    T = "2025-2026"
    mem = lambda i, name, ch, party, dist, county, towns: {
        "id": i, "name": name, "chamber": ch, "party_code": party, "district": dist, "county": "",
        "county_abbr": county, "towns": towns}
    nancy = mem("1", "Murphy, Nancy", "H", "D", "12", "Hills", ["Bedford"])
    ann = mem("2", "Lee, Ann", "H", "R", "3", "Rock", ["Rye"])
    zed = mem("3", "Quiet, Zed", "H", "R", "6", "Belk", ["Gilford"])
    sam = mem("4", "Senn, Sam", "S", "R", "4", "", ["Dover"])
    for m in (nancy, ann, zed, sam):
        m.update(B.member_labels(m["name"], chamber=m["chamber"], party=m["party_code"],
                                 district=m["district"], county_abbr=m["county_abbr"]))
        m["slug"] = B.own_slug(m)
    legs = {m["id"]: m for m in (nancy, ann, zed, sam)}
    gone = dict(mem("5", "Gone, Joe", "H", "D", "6", "Belk", []), served={"terms": ["2023-2024", T]})
    quit_ = dict(mem("6", "Left, Lou", "S", "D", "9", "", []), served={"terms": [T]})
    old = dict(mem("7", "Hand, Old", "H", "R", "1", "Coos", []), served={"terms": ["2019-2020"]})
    for m in (gone, quit_, old):
        m.update(B.member_labels(m["name"], chamber=m["chamber"], party=m["party_code"],
                                 district=m["district"], county_abbr=m["county_abbr"]))
        m["slug"] = B.own_slug(m)
        m["former"] = True
    former = {m["id"]: m for m in (gone, quit_, old)}
    rec = lambda i, name, prime, ch, party, dist, county: {
        "member_id": i, "name": name, "prime": prime, "chamber": ch, "party": party, "district": dist,
        "county": county, "source": "bill status page"}
    sponsors = {T: {"HB1": [rec("1", "Nancy Murphy", True, "H", "D", "12", "Hills"),
                            rec("2", "Ann Lee", False, "H", "R", "3", "Rock"),
                            rec("4", "Sam Senn", False, "S", "R", "4", "")],
                    "HB2": [rec("5", "Joe Gone", True, "H", "D", "06", "Belk"),
                            rec("99", "Pat Visitor", False, "H", "R", "2", "Straf")]}}
    bills = {T: {b: {"bill": b, "lsr": f"2025-000{b[-1]}", "lsr_year": "2025", "title": "a fixture.",
                     "chamber": "H", "designation": b.replace("HB", "HB ")} for b in ("HB1", "HB2")}}
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-roster-"))
    people = {}
    try:
        os.chdir(tmp)
        out = tmp / "site"
        out.mkdir()
        by_sort = {B.sort_name(m["name"]): m for m in legs.values()}
        by_key = {B.name_key(m["name"]): m for m in legs.values()}
        with contextlib.redirect_stdout(io.StringIO()):
            index, *_ = B.build_bills(out, bills, {}, {}, {}, sponsors, {}, {}, {}, {}, {}, {}, {}, {}, {},
                                      legs, by_sort, by_key, {},
                                      seats={m["id"]: [(T, m["chamber"])] for m in (*legs.values(), gone)},
                                      former=former, links={}, people=people)
            SR.add_sitting(people, T, legs, former, B.own_slug, B.person_name)
            (out / "sponsors").mkdir()
            (out / "sponsors" / "2001-2002.json").write_text("{}", encoding="utf-8")
            SR.write(out, people)
        files = sorted(p.name for p in (out / "sponsors").glob("*.json"))
        listed = json.loads((out / "sponsors" / f"{T}.json").read_text(encoding="utf-8"))
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    named = {r["sponsor"] for r in index} | {c for r in index for c in r.get("cosp", [])}
    rows = listed["members"]
    keys = [r["k"] for r in rows]
    assert named <= set(keys), f"a name the index files a bill under is not listed: {sorted(named - set(keys))}"
    assert keys == ["Joe Gone", "Ann Lee", "Nancy Murphy", "Zed Quiet", "Pat Visitor", "Lou Left", "Sam Senn"], (
        f"not each member once, House then Senate by surname: {keys}")
    by = {r["k"]: r for r in rows}
    assert [k for k in keys if by[k].get("f")] == ["Joe Gone", "Lou Left"], (
        f"the members who left are not the ones marked: {[k for k in keys if by[k].get('f')]}")
    assert "Old Hand" not in keys, "a former member of another term is listed in this one"
    assert by["Nancy Murphy"].get("t") == ["Bedford"] and by["Joe Gone"].get("t") == ["Gilford"] \
        and by["Zed Quiet"].get("t") == ["Gilford"], (
        f"towns: {by['Nancy Murphy'].get('t')}, Joe Gone's (Belk 06) {by['Joe Gone'].get('t')}")
    assert by["Ann Lee"]["l"] == "Rep. Ann Lee (R - Rock 3)" and by["Ann Lee"].get("p") == "R" \
        and by["Sam Senn"].get("c") == "S", f"a co-sponsor's label, party or chamber: {by['Ann Lee']}, {by['Sam Senn']}"
    assert by["Nancy Murphy"]["o"] == "murphy, nancy", by["Nancy Murphy"]
    assert files == [f"{T}.json"], f"a term's file an earlier build left is not removed: {files}"
    assert by["Pat Visitor"].get("c") == "H" and not by["Pat Visitor"].get("f"), (
        f"a co-sponsor no roster names is not listed by their record's chamber: {by['Pat Visitor']}")
    # The seat a bill status page pads ("Belk 06") is the roster's ("Belk 6"): the towns of the district.
    padded = {}
    SR.note_bill(padded, T, {"sponsor": "Joe Gone", "sponsor_label": "Rep. Joe Gone (D - Belk 06)",
                             "sponsor_slug": gone["slug"], "sponsor_party": "D"}, [], None, B.person_name)
    SR.add_sitting(padded, T, legs, former, B.own_slug, B.person_name)
    assert padded[T]["Joe Gone"]["t"] == ["Gilford"], (
        f"a padded seat is not its district: Joe Gone (Belk 06) gets {padded[T]['Joe Gone']['t']}")
    shapes = [{"sponsor": "Nancy Murphy", "sponsor_label": "Rep. Nancy Murphy (D - Hills 12)", "sponsor_slug": "x"},
              {"sponsor": "Allen", "sponsor_label": "Rep. Allen (Hills 1)"},
              {"sponsor": "Allen", "sponsor_label": "Rep. Allen (R - Hills 1)", "sponsor_party": "R"},
              {"sponsor": "Dana Moore", "sponsor_label": "Rep. Dana Moore (Graf 5)", "sponsor_person": 1},
              {"sponsor": "Keough", "sponsor_label": "Sen. Keough (SD23)"},
              {"sponsor": "Smith", "sponsor_label": "Rep. Smith"},
              {"sponsor": "", "sponsor_label": ""}]
    js = _app_js("(%s).map(b => scope.spKey(b))" % json.dumps(shapes), names=("spKey",))
    py = [SR.sp_key(r) for r in shapes]
    assert js is None or js == py, f"sponsor_roster.sp_key and app.js spKey disagree: {py} against {js}"
    src = _source(Path("src/pages/build_site_v2.py"))
    assert "SR.note_bill(people, term, row, sp_list, prime, person_name)" in src \
        and "SR.write(out, sponsor_people)" in src and "people=sponsor_people" in src, (
        "build_site_v2's main no longer collects and writes the Sponsor filter's members")
    return "ok", ("7 members, House then Senate by surname, the two who left marked, towns by district (Belk 06 too), "
                  "an unmatched co-sponsor by their record's chamber, the old term's "
                  "file removed; the keys are the index's" + ("" if js is None else " and app.js spKey's"))

@check("build", "the Sponsor filter's list labels every sitting member and every member who left as their own page "
       "does, from the roster as build_site_v2 reads it, a member no bill names among them",
       needs=("build_site_v2", "sponsor_roster"))
def _sponsor_roster_from_the_raw_roster(build_site_v2, sponsor_roster):
    """The dry run of 19 November 2026 (44575335108): _sponsor_roster_data found 31 sitting members not listed
    as their pages label them. The roster build_site_v2 reads (data/legislators.json, and former_roster's members)
    has no display_full or district_label -- the built site/legislators.json gains them later -- so every member
    no bill names was listed by their bare name, under no chamber, and a member who left had no towns.
    add_sitting now labels them with sitting_labels, as build_legislators labels their pages. Held on members in
    that raw shape: a sitting member who filed and signed nothing ("Boudman, Bobbi") is listed once as "Rep. Bobbi
    Boudman (D - Carr 7)" in the House, with her towns; a senator likewise; a member who left and filed nothing
    is labelled and marked, with the towns of the district a sitting member holds; one already listed by a bill
    keeps that row; and main hands add_sitting sitting_labels."""
    B, SR = build_site_v2, sponsor_roster
    T = "2025-2026"
    raw = lambda i, name, ch, code, dist, county, abbr, towns: {
        "id": i, "name": name, "chamber": ch, "party": {"D": "Democratic", "R": "Republican"}[code],
        "party_code": code, "district": dist, "county": county, "county_abbr": abbr, "towns": towns,
        "label": ""}
    boudman = raw("1", "Boudman, Bobbi", "H", "D", "7", "Carroll", "Carr", ["Ossipee", "Wolfeboro"])
    abbas = raw("2", "Abbas, Daryl", "S", "R", "22", "Rockingham", "Rock", ["Salem"])
    murphy = raw("3", "Murphy, Nancy", "H", "D", "12", "Hillsborough", "Hills", ["Bedford"])
    neighbour = raw("4", "Gilford, Gil", "H", "R", "2", "Belknap", "Belk", ["Meredith"])
    legs = {m["id"]: m for m in (boudman, abbas, murphy, neighbour)}
    lunney = dict(raw("5", "Lunney, Matthew", "H", "R", "2", "Belknap", "Belk", []),
                  former=True, served={"terms": [T]})
    del lunney["label"]
    people = {T: {}}
    SR.note_bill(people, T, {"sponsor": "Nancy Murphy", "sponsor_label": "Rep. Nancy Murphy (D - Hills 12)",
                             "sponsor_slug": B.own_slug(murphy), "sponsor_party": "D"}, [], None, B.person_name)
    SR.add_sitting(people, T, legs, {"5": lunney}, B.own_slug, B.person_name, labels=B.sitting_labels)
    rows = {r["k"]: r for r in SR.rows(people[T])}
    want = {m["id"]: B.sitting_labels(m)["display_full"] for m in (boudman, abbas, murphy, neighbour, lunney)}
    assert rows["Bobbi Boudman"]["l"] == want["1"] == "Rep. Bobbi Boudman (D - Carr 7)" \
        and rows["Bobbi Boudman"].get("c") == "H" and rows["Bobbi Boudman"].get("t") == ["Ossipee", "Wolfeboro"], (
        f"a sitting member no bill names is not listed as her page labels her: {rows.get('Bobbi Boudman')}")
    assert rows["Daryl Abbas"]["l"] == want["2"] == "Sen. Daryl Abbas (R - SD22)" and rows["Daryl Abbas"].get("c") == "S", (
        f"a senator no bill names: {rows.get('Daryl Abbas')}")
    assert rows["Matthew Lunney"]["l"] == "Rep. Matthew Lunney (R - Belk 2)" and rows["Matthew Lunney"].get("f") == 1 \
        and rows["Matthew Lunney"].get("t") == ["Meredith"], (
        f"a member who left and filed nothing is not labelled, marked and given his district's towns: "
        f"{rows.get('Matthew Lunney')}")
    assert len(rows) == 5 and rows["Nancy Murphy"]["l"] == "Rep. Nancy Murphy (D - Hills 12)", (
        f"a member a bill lists is listed twice or relabelled: {sorted(rows)}")
    assert not [r for r in rows.values() if r["l"] == r["k"] or not r.get("c")], (
        f"a member is listed by a bare name or under no chamber: {[r for r in rows.values() if not r.get('c')]}")
    src = _source(Path("src/pages/build_site_v2.py"))
    assert "labels=sitting_labels)" in src, "build_site_v2's main does not hand add_sitting the members' own labels"
    return "ok", ("from the raw roster: Rep. Bobbi Boudman (D - Carr 7) and Sen. Daryl Abbas (R - SD22), no bill "
                  "naming them, once each in their chamber with their towns; Rep. Matthew Lunney (R - Belk 2), who "
                  "left, marked with Belk 2's towns; Nancy Murphy's bill row kept")


@check("data", "the built Sponsor filter's file for the sitting term lists every sitting member once, House then Senate",
       needs=())
def _sponsor_roster_data():
    """site/sponsors/<newest term>.json against site/legislators.json, where both are on this disk: every
    sitting member's label is one row's, and only one, not marked as having left; the House's rows all come
    before the Senate's; no key is listed twice; the members who left are marked and nobody sitting is."""
    site = _paths.ROOT / "site"
    terms = sorted(p.stem for p in (site / "sponsors").glob("*.json")) if (site / "sponsors").is_dir() else []
    legs_f = site / "legislators.json"
    if not terms or not legs_f.is_file():
        return "skip", "no site/sponsors/ or site/legislators.json here (build_site_v2 writes them)"
    newest = max(t for t in terms if "-" in t)
    rows = json.loads((site / "sponsors" / f"{newest}.json").read_text(encoding="utf-8"))["members"]
    legs = json.loads(legs_f.read_text(encoding="utf-8"))
    keys = [r["k"] for r in rows]
    assert len(keys) == len(set(keys)), f"a key is listed twice: {[k for k, n in Counter(keys).items() if n > 1][:5]}"
    ch = [r.get("c", "") for r in rows]
    assert ch == sorted(ch, key=lambda c: {"H": 0, "S": 1}.get(c, 2)), "the House's rows are not all before the Senate's"
    labels = Counter(r["l"] for r in rows if not r.get("f"))
    missing = [m["display_full"] for m in legs if labels.get(m["display_full"], 0) != 1]
    assert not missing, (f"{len(missing)} sitting member(s) not listed exactly once in sponsors/{newest}.json: "
                         f"{missing[:5]}")
    sitting = {m["display_full"] for m in legs}
    marked = [r["l"] for r in rows if r.get("f") and r["l"] in sitting]
    assert not marked, f"a sitting member is marked as having left: {marked[:5]}"
    return "ok", (f"sponsors/{newest}.json: {len(legs)} sitting members once each, {sum(1 for r in rows if r.get('f'))} "
                  f"who left marked, {len(rows)} rows, House then Senate")


@check("naming", "a member who resigned mid-term keeps the link on every bill they sponsored",
       needs=("build_site_v2", "member_links"))
def _resigned_sponsors_keep_their_link(build_site_v2, member_links):
    """Alice, 9 November 2026: Rep. Glenn Cordelli's HB 121 linked to his page
    and his HB 137 did not, reading "Carr 07". HB 137's sponsor came from the
    bill status page, which names him by an employee number the sitting roster
    no longer answers once he resigned; the name was looked for among former
    members only for a finished term. The sitting term looks there too now,
    under the same rule (only someone who sat in that chamber that term), and
    a padded district reads as people say it.
    """
    import contextlib
    import io
    B, ML = build_site_v2, member_links
    T = "2025-2026"
    legs = {"990100": {"id": "990100", "name": "Smith, Ann", "chamber": "H", "party_code": "D",
                       "district": "5", "county": "Rockingham", "county_abbr": "Rock"}}
    former = {"990866": {"id": "990866", "name": "Terry, Paul", "chamber": "H", "party_code": "R",
                         "district": "7", "county": "Carroll", "county_abbr": "Carr",
                         "former": True}}
    votes = {"990100": [{"year": "2025", "body": "H"}], "990866": [{"year": "2025", "body": "H"}]}
    seats = ML.seats_held([*legs.values(), *former.values()], votes, {}, T)
    sponsors = {T: {"HB10": [
        {"member_id": "377085", "name": "Paul Terry", "chamber": "H", "prime": True,
         "source": "bill status page", "county": "Carr", "district": "07"},
        {"member_id": "990100", "name": "Smith, Ann", "chamber": "H", "prime": False}]}}
    bills = {T: {"HB10": {"bill": "HB10", "lsr": "2025-0010", "lsr_year": "2025",
                          "title": "relative to a fixture.", "chamber": "H",
                          "designation": "HB 10"}}}
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-resigned-"))
    try:
        os.chdir(tmp)
        out = tmp / "site"
        out.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            B.build_bills(out, bills, {}, {}, {}, sponsors, {}, {}, {}, {}, {}, {}, {}, {}, {},
                          legs, {B.sort_name(m["name"]): m for m in legs.values()},
                          {B.name_key(m["name"]): m for m in legs.values()}, {},
                          seats=seats, former=former)
        page = json.loads((out / "bills" / "2025" / "HB10.json").read_text(encoding="utf-8"))
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    terry = page["sponsors"][0]
    assert terry.get("slug") == B.own_slug(former["990866"]), (
        "a member who resigned this term is unlinked on a bill the status page names "
        f"him on: slug {terry.get('slug')!r}")
    assert terry.get("district_label") == "Carr 7", (
        f"the resigned member's seat reads {terry.get('district_label')!r}, not 'Carr 7'")
    assert page["sponsors"][1].get("slug") == B.own_slug(legs["990100"]),         "the sitting co-sponsor lost her link"
    assert B.district_tag("H", "07", "Carroll") == "Carr 7" and         B.district_tag("S", "03") == "SD3", "a padded district number is drawn as printed"
    return "ok", ("a member who resigned this term is linked on a bill the status page names "
                  "them on, at their seat as people say it (Carr 7)")


@check("naming", "after the turn a finished term's sponsors who left at the election keep their link",
       needs=("build_site_v2", "member_links"))
def _finished_term_sponsors(build_site_v2, member_links):
    """The rehearsal of the turn, 5 October 2026: once the roster was the next
    House, 900 sponsor names on 491 of 2025-2026's bills -- the members who left
    at the election -- lost their link and read their seat as the record pads
    it ("Belk 07"), because a bill status page's sponsor carries a web member id
    and was found by name on the sitting roster alone. Each has a page under
    `former`. For a term frozen and finished, bill_sponsor_list now looks for
    the name there too (`left`), under the rule a name is that member only
    where they sat that term; for every other term `left` is None and nothing
    moves.
    """
    from collections import defaultdict
    B, ML = build_site_v2, member_links
    legs = {"990100": {"id": "990100", "name": "Smith, Ann", "chamber": "H", "party_code": "D",
                       "district": "5", "county": "Rockingham", "county_abbr": "Rock"}}
    # Two former members of one name: the first sat in 2001-2002 only.
    former = {"990500": {"id": "990500", "name": "Terry, Paul", "chamber": "H", "party_code": "D",
                         "district": "3", "county": "Hillsborough", "county_abbr": "Hills",
                         "former": True},
              "990866": {"id": "990866", "name": "Terry, Paul", "chamber": "H", "party_code": "R",
                         "district": "7", "county": "Belknap", "county_abbr": "Belk",
                         "former": True}}
    votes = {"990100": [{"year": "2025", "body": "H"}], "990500": [{"year": "2001", "body": "H"}],
             "990866": [{"year": "2026", "body": "H"}]}
    seats = ML.seats_held([*legs.values(), *former.values()], votes, {}, "2027-2028")
    by_sort = {B.sort_name(m["name"]): m for m in legs.values()}
    by_name = {B.name_key(m["name"]): m for m in legs.values()}
    left = (defaultdict(list), defaultdict(list))
    for m in former.values():
        left[0][B.sort_name(m["name"])].append(m)
        left[1][B.name_key(m["name"])].append(m)
    sponsors = {"2025-2026": {"HB10": [
        {"member_id": "409053", "name": "Paul Terry", "chamber": "H", "prime": True,
         "county": "Belk", "district": "07"},
        {"member_id": "409000", "name": "Ann Smith", "chamber": "H", "prime": False}]}}
    people = {**legs, **former}

    def run(with_left):
        sponsored = defaultdict(list)
        sp = B.bill_sponsor_list("HB10", {"designation": "HB 10", "title": "a bill"}, "2025",
                                 "2025-2026", "2027-2028", sponsors, people, by_sort, by_name,
                                 sponsored, seats, left=left if with_left else None)
        return sp, sponsored

    sp, sponsored = run(True)
    terry = sp[0]
    assert terry["slug"] == B.own_slug(former["990866"]) and terry["district_label"] == "Belk 7", (
        f"the finished term's Paul Terry reads {terry['district_label']!r}, linked to {terry['slug']!r}: "
        "wanted the one who sat in 2025-2026, at Belk 7")
    assert sponsored.get("990866") and "990500" not in sponsored, (
        "HB 10 filed under " + ", ".join(sponsored))
    assert sp[1]["slug"] == B.own_slug(legs["990100"]), "the member re-elected lost her link"
    sp, _ = run(False)
    assert not sp[0]["slug"], "with no finished term the name was looked for among former members"
    # A TERM'S OWN ROSTER LABELS ITS MEMBERS AS THEY SAT (the review of 5
    # October 2026): a Representative elected to the Senate under a new id,
    # whom member_links joins to the sitting senator once he votes, read
    # "Sen. ... (R - SD23)" on every one of his House bills of the term. The
    # term's frozen roster (`term_roster`) gives the seat; the link is still
    # his own page, the senator's.
    senator = {"id": "11460", "name": "Doe, Matt", "chamber": "S", "party_code": "R",
               "district": "23", "county": "Rockingham", "county_abbr": "Rock"}
    as_sat = {"id": "11420", "name": "Doe, Matt", "chamber": "H", "party_code": "R",
              "district": "30", "county": "Rockingham", "county_abbr": "Rock"}
    joined = {**people, "11460": senator, "11420": senator}
    his = {"2025-2026": {"HB20": [{"member_id": "11420", "name": "Doe, Matt", "chamber": "H",
                                   "prime": True}]}}

    def label(roster):
        return B.bill_sponsor_list("HB20", {"designation": "HB 20", "title": "a bill"}, "2025",
                                   "2025-2026", "2027-2028", his, joined, by_sort, by_name,
                                   defaultdict(list), None, term_roster=roster)[0]
    got = label({"11420": as_sat})
    assert got["display_full"] == "Rep. Matt Doe (R - Rock 30)" and \
        got["slug"] == B.own_slug(senator), ("a term's own roster did not label its member as he "
                                            "sat", got["display_full"], got["slug"])
    assert label(None)["display_full"].startswith("Sen."), \
        "with no term roster the sitting record no longer labels the sponsor (the fixture is stale)"
    # And through build_bills, as main hands it the term rosters: the page's
    # own record reads the seat he sat in.
    import contextlib
    import io
    T = "2025-2026"
    bills = {T: {"HB20": {"bill": "HB20", "lsr": "2025-0020", "lsr_year": "2025",
                          "title": "relative to a fixture.", "chamber": "H",
                          "designation": "HB 20"}}}
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-termroster-"))
    try:
        os.chdir(tmp)
        out = tmp / "site"
        out.mkdir()
        got = []
        for rosters in ({T: {"11420": as_sat}}, None):
            with contextlib.redirect_stdout(io.StringIO()):
                B.build_bills(out, bills, {}, {}, {}, his, {}, {}, {}, {}, {}, {}, {}, {}, {},
                              {"11460": senator}, {B.sort_name(senator["name"]): senator},
                              {B.name_key(senator["name"]): senator}, {},
                              links={"11460": ["11420"]}, former={}, term_rosters=rosters)
            page = json.loads((out / "bills" / "2025" / "HB20.json").read_text(encoding="utf-8"))
            got.append(page["sponsors"][0]["display_full"])
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    assert got == ["Rep. Matt Doe (R - Rock 30)", "Sen. Matt Doe (R - SD23)"], \
        ("build_bills does not label a term's sponsors from the term roster main gives it", got)
    # A Senate hearing report's speaker, resolved among the term's own roster:
    # the party they sat with, the link to their page as it is now, and none
    # where they have no page.
    import senate_hearing_reports as SHR
    sat = {**as_sat, "last": "Doe", "first": "Matt", "party_code": "D"}
    now = {**as_sat, "last": "Doe", "first": "Matt", "party_code": "R", "district": "70"}
    rep = {"sections": [{"speakers": [{"who": "Rep. Matt Doe, Rock. 30"}]}]}
    chips = [B.hearing_report_for_page(rep, B.speaker_index([who]), SHR.name_part, pages)[0]
             ["sections"][0]["speakers"][0].get("member")
             for who, pages in ((sat, {"11420": now}), (now, None), (sat, {}))]
    assert [(c["party_code"], c["slug"]) for c in chips] == \
        [("D", B.own_slug(now)), ("R", B.own_slug(now)), ("D", "")], chips
    # ... and through build_bills: a Representative of the term who sits in
    # the Senate now is found among the term's own roster, and linked to the
    # page he has; the sitting roster alone does not know him as a Rep.
    rep["heard"], rep["committee"] = "2025-04-23", "Senate Fixture Committee"
    tmp = Path(tempfile.mkdtemp(prefix="gr-termspeaker-"))
    try:
        os.chdir(tmp)
        out = tmp / "site"
        out.mkdir()
        heard = []
        for rosters in ({T: {"11420": sat}}, None):
            with contextlib.redirect_stdout(io.StringIO()):
                B.build_bills(out, bills, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {},
                              {"11460": senator}, {}, {}, {}, links={"11460": ["11420"]},
                              former={}, term_rosters=rosters,
                              hearing_reports={T: {"HB20": [rep]}})
            page = json.loads((out / "bills" / "2025" / "HB20.json").read_text(encoding="utf-8"))
            heard.append([s.get("member") for st in page.get("stations") or []
                          for r in st.get("reports") or [] for sec in r.get("sections") or []
                          for s in sec.get("speakers") or []])
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    assert heard[0] == [{"label": "Rep. Matt Doe", "party_code": "D",
                         "slug": B.own_slug(senator)}] and heard[1] == [None], \
        ("build_bills does not resolve a term's hearing speakers among its own roster", heard)
    return "ok", ("a finished term's sponsor named by a web id is found among the members who left, the "
                  "one who sat that term, and reads their seat as before; with no finished term, as it "
                  "was; and a term's own frozen roster labels a member now in the Senate as he sat")


@check("data", "every motion the docket puts on an amendment has an outcome")
def _amend_motions_mapped():
    """FAILED was missing from the outcome map, and a missing key is silent.

    build_site_v2.ADOPTED turns the docket's abbreviation into adopted /
    not adopted, and it is read with .get -- so an abbreviation it does not
    know returns None, the page reads that as "the record does not say", and
    no chip is drawn. That is indistinguishable on screen from an amendment
    that really was only filed and never voted on, which is why 153 events
    saying "Failed, RC 131-221" sat on the site for months claiming the
    outcome was unknown.

    The map had AA, ADOPTED, AF and AL: three quarters of a pair. The docket
    writes the outcome either abbreviated or spelled out, and it had the
    abbreviated form of both and the spelled-out form of only one.

    SO THE CHECK IS AGAINST THE DATA, NOT A LIST. Every distinct motion that
    occurs on an amendment event has to be a key in the map, or be blank --
    blank is the honest unknown and there are 1,075 of those, every one a
    docket line the parser could not read a motion out of. A new abbreviation
    appearing in a later term fails here rather than publishing silence.

    Counted when this was written: AA 12,249, ADOPTED 4,583, AF 997, AL 48,
    FAILED 153, blank 1,075, over 19,105 amendment events. LOST and WITHDRAWN
    occur in docket PROSE and never in this field, so they are deliberately
    not in the map -- putting them there would be guessing at data rather than
    reading it, and this check would not have asked for them.
    """
    src = Path("narratives.json")
    if not src.exists():
        return "skip", "no narratives.json here"
    bsv = imp("build_site_v2")
    if bsv is None:
        return "skip", "build_site_v2 will not import"

    n = _narratives()
    seen, example = {}, {}
    for term, bills in n.items():
        if not isinstance(bills, dict):
            continue
        for bid, rec in bills.items():
            for e in (rec or {}).get("events") or []:
                if e.get("type") != "amendment" or e.get("cancelled"):
                    continue
                m = (e.get("motion") or "").upper()
                seen[m] = seen.get(m, 0) + 1
                if m:
                    example.setdefault(m, f"{term} {bid}: {(e.get('raw') or '')[:90]}")

    if not seen:
        return "skip", "no amendment events in narratives.json"

    unknown = sorted(m for m in seen if m and m not in bsv.ADOPTED)
    assert not unknown, (
        "the docket puts a motion on an amendment that build_site_v2.ADOPTED "
        "does not map, so every one of these is published with NO OUTCOME -- "
        "which a reader cannot tell apart from an amendment that was never "
        "voted on:\n  "
        + "\n  ".join(f"{m} on {seen[m]:,} events -- {example[m]}"
                       for m in unknown))

    named = sum(c for m, c in seen.items() if m)
    return "ok", (f"{named:,} of {sum(seen.values()):,} amendment events name a "
                  f"motion and every one is mapped; {seen.get('', 0):,} name none")


@check("data", "a member is named the same way by both namers")
def _one_naming():
    """names.legislator and build_site_v2.member_labels must agree.

    Two functions compose a member's name because data/legislators.json is
    written by build_data.py, which runs first and cannot import the builder.
    They agreed on all 406 members the day the second one was written, and the
    only way to keep that true is to ask.
    """
    try:
        import names
        import build_site_v2 as B
    except ImportError as e:
        return "skip", f"cannot import: {e}"
    src = Path("data/legislators.json")
    if not src.exists():
        return "skip", "data/legislators.json is not built"
    recs = json.loads(src.read_text(encoding="utf-8"))
    recs = list(recs.values()) if isinstance(recs, dict) else recs
    bad = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        mine = names.legislator(r)
        theirs = B.member_labels(
            r.get("name"), chamber=r.get("chamber"), party=r.get("party_code"),
            district=r.get("district"), county=r.get("county"),
            county_abbr=r.get("county_abbr"))["display_full"]
        if mine != theirs:
            bad.append(f"{r.get('name')}: {mine!r} vs {theirs!r}")
    assert not bad, (f"{len(bad)} of {len(recs)} members are named two ways: "
                     + "; ".join(bad[:3]))
    return "ok", f"{len(recs):,} members, one name each"


@check("naming", "a 1989-1998 sponsor placed on a person with a page takes the party the page gives, "
                 "where every record of them gives that one, else the party the bill's term's Manual "
                 "gives them: on the row, the label and the Sponsors list",
       needs=("build_site_v2", "past_sponsors"))
def _early_sponsors_take_their_page_party(B, PSP):
    """The owner's decisions, 15 November 2026 (build_site_v2.early_party): show on a 1989-1998
    chip the party the person's own page gives, and leave it off for anyone the record shows in
    more than one party; and for such a person, a 1989-1998 bill shows the party that bill's
    term's Manual for the General Court gives them, where it settles the term with a single
    letter -- a cross-nomination ("d&r") settles nothing, and a term the Manual does not seat
    them in gives nothing. Rep. Donna Sytek, R on her page, was drawn with no party on the 34
    bills of 1993-1994 she is prime sponsor of, and so was every sponsor of those terms placed on
    a page: the live index of 15 November had 4,160 prime sponsors of 1989-1998 with a page and
    no party. Held on a fixture run through build_bills, with the records party_ids reads:

    - Dee Speaker, R on her page, her ballots and her 2001 bill, prime on 1993 HB 108 at the seat
      it prints (Rock 26; her page is Rock 30): R on the index row (sponsor_party), the label
      ("Rep. Dee Speaker (R - Rock 26)") and her chip on the bill's Sponsors list; and on the
      General Court's own row filling 1993 HB 104 (past_sponsors.filled), which has no seat;
    - Sam Switch, R on his page, whose 2001 bill draws him D: none, and as prime of 1993 HB 7 the
      index row has no party and the party filter puts it under "Party not on file";
    - Gil Grid, whose 2023 row carries D under a label the roster draws R: none;
    - Manny Manual, R on his page, whom the 1993 Manual's returns print "d" and the 1995 Manual's
      "d&r": D on his bills of 1993-1994, co-sponsor of HB 108 and prime of HB 109 (the index
      row's sponsor_party and his chip too); none on 1995 HB 20, a term of two nominations, and
      none on 1997 HB 30, a term the Manual does not seat him in. Rae Ross, R, whom the 1993
      returns print "d&r", two nominations and no one party, is of one party: R;
    - Carl Careers, R, whom the legislators table (generated/careers.json) calls D, and Bo Ballot,
      R, a ballot of whose reads D: none;
    - Ann Nopage, placed by the bill's own rows on a number no page answers: none, and no link;
    - the bills of 1999 on as before; with no record read at all (main passes none where the
      Manual's seat list is not on this disk) nobody of 1989-1998 takes a party; and the build
      says who took it and who did not.
    app.js draws the same: the chip's party class, the card's party and the party filter."""
    import contextlib
    import io
    TERM = "1993-1994"
    page = lambda mid, name, county, abbr, d, **kw: dict(
        {"id": mid, "name": name, "chamber": "H", "party": "Republican", "party_code": "R",
         "county": county, "county_abbr": abbr, "district": d}, **kw)
    dee = page("800101", "Speaker, Dee", "Rockingham", "Rock", "30")
    legs = {m["id"]: m for m in (
        dee, page("800102", "Switch, Sam", "Hillsborough", "Hills", "5"),
        page("800103", "Grid, Gil", "Merrimack", "Merr", "8"))}
    former = {m["id"]: m for m in (
        page("800104", "Manual, Manny", "Strafford", "Straf", "3", party="R", former=True),
        page("800105", "Careers, Carl", "Belknap", "Belk", "4", party="R", former=True),
        page("800106", "Ross, Rae", "Coos", "Coos", "2", party="R", former=True),
        page("800107", "Ballot, Bo", "Sullivan", "Sull", "1", party="R", former=True))}
    printed = lambda name, mid, emp, county, d, prime=False: {
        "member_id": mid, "employee": emp, "name": name, "party": "", "chamber": "H",
        "county": county, "district": d, "label": f"Rep. {name}", "prime": prime,
        "source": "bill text", "prime_inferred": True, "matched": B.PAST_ROSTER_MATCH,
        "as_printed": f"Rep. {name.split()[-1]}, {county} {d}"}
    sponsors = {
        TERM: {"HB108": [printed("Dee Speaker", "800101", "375001", "Rockingham", "26", prime=True),
                         printed("Sam Switch", "800102", "375002", "Hillsborough", "5"),
                         printed("Ann Nopage", "", "375009", "Cheshire", "3"),
                         printed("Manny Manual", "800104", "375004", "Strafford", "3"),
                         printed("Carl Careers", "800105", "375005", "Belknap", "4"),
                         printed("Rae Ross", "800106", "375006", "Coos", "2"),
                         printed("Gil Grid", "800103", "375003", "Merrimack", "8"),
                         printed("Bo Ballot", "800107", "375007", "Sullivan", "1")],
               "HB104": [{"member_id": "800101", "employee": "375001", "name": "Dee Speaker",
                          "party": "", "chamber": "H", "prime": True, "prime_inferred": False,
                          "label": "Rep. Dee Speaker", "source": PSP.SOURCE,
                          "seat_source": PSP.SOURCE}],
               "HB7": [printed("Sam Switch", "800102", "375002", "Hillsborough", "5", prime=True)],
               "HB109": [printed("Manny Manual", "800104", "375004", "Strafford", "3", prime=True)]},
        "1995-1996": {"HB20": [printed("Manny Manual", "800104", "375004", "Strafford", "3", prime=True)]},
        "1997-1998": {"HB30": [printed("Manny Manual", "800104", "375004", "Strafford", "3", prime=True)]},
        "2001-2002": {"HB5": [
            {"member_id": "800101", "name": "Dee Speaker", "party": "R", "chamber": "H",
             "county": "Rockingham", "district": "30", "prime": True, "source": "bill text"},
            {"member_id": "800102", "name": "Sam Switch", "party": "D", "chamber": "H",
             "county": "Hillsborough", "district": "5", "prime": False, "source": "bill text"}]},
        "2023-2024": {"HB9": [{"member_id": "800103", "name": "Grid, Gil", "party": "D",
                               "chamber": "H", "prime": True}]}}
    bill = lambda bid, y: {"bill": bid, "lsr": f"{y}-0001", "lsr_year": y, "chamber": "H",
                           "title": "relative to a fixture.", "designation": bid.replace("HB", "HB ")}
    bills = {TERM: {"HB108": bill("HB108", "1993"), "HB104": bill("HB104", "1993"),
                    "HB7": bill("HB7", "1993"), "HB109": bill("HB109", "1993")},
             "1995-1996": {"HB20": bill("HB20", "1995")}, "1997-1998": {"HB30": bill("HB30", "1997")},
             "2001-2002": {"HB5": bill("HB5", "2001")}, "2023-2024": {"HB9": bill("HB9", "2023")},
             "2025-2026": {}}
    # The other records: the 1993 and 1995 Manuals' returns (manual_parties, by the id each
    # number's ballots are cast under), the legislators table (careers.json) and the ballots.
    people = PSP.People([{"Employeeno": e, "PersonID": p, "LastName": n.split(", ")[0],
                          "FirstName": n.split(", ")[1], "LegislativeBody": "H"}
                         for e, p, n in (("375004", "800104", "Manual, Manny"),
                                         ("375006", "800106", "Ross, Rae"))],
                        {"375004": {"name": "Manual, Manny", "chamber": "H"},
                         "375006": {"name": "Ross, Rae", "chamber": "H"}})
    row = lambda name, county, d, party: {"name": name, "county": county, "district": d,
                                          "party": party, "status": "elected", "district_check": "clean"}
    table = {"terms": {
        TERM: {"edition": "1993", "senate": [], "house": [
            row("Manny Manual", "Strafford", "3", "d"), row("Rae Ross", "Coos", "2", "d&r")]},
        "1995-1996": {"edition": "1995", "senate": [], "house": [
            row("Manny Manual", "Strafford", "3", "d&r")]}}}
    manual = B.manual_parties(table, people)
    assert manual == {"800104": {TERM: {"D"}}}, (
        f"the Manual's returns give {manual}: wanted Manny Manual's 'd' of 1993 alone, a line of "
        "two nominations naming no party")
    assert B.manual_parties(None, people) is None, "no seat list read is not said as none"
    ids = B.party_ids({"800101": [{"party": "R"}], "800107": [{"party": "R"}, {"party": "D"}]},
                      {"375005": {"party": "d", "person_id": "800105", "employee_nos": ["375005"]}},
                      manual)
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-early-party-"))
    said, unsaid = io.StringIO(), io.StringIO()
    try:
        os.chdir(tmp)
        people_ = [*legs.values(), *former.values()]
        for into, kw in ((said, {"id_parties": ids}), (unsaid, {})):
            out = tmp / ("site" if kw else "site-none")
            out.mkdir()
            with contextlib.redirect_stdout(into):
                got_index, *_ = B.build_bills(
                    out, bills, {}, {}, {}, sponsors, {}, {}, {}, {}, {}, {}, {}, {}, {},
                    legs, {B.sort_name(m["name"]): m for m in people_},
                    {B.name_key(m["name"]): m for m in people_}, {}, former=former, **kw)
            if kw:
                index = got_index
                pages = {f"{y}/{b}": json.loads((out / "bills" / y / f"{b}.json").read_text(encoding="utf-8"))
                         for y, b in (("1993", "HB108"), ("1993", "HB104"), ("1993", "HB7"),
                                      ("1993", "HB109"), ("1995", "HB20"), ("1997", "HB30"),
                                      ("2001", "HB5"))}
            else:
                # NO RECORD READ, NO PARTY: main passes no id_parties where the Manual's seat list
                # is not on this disk, and then nobody's 1989-1998 chip is given one.
                bare = json.loads((out / "bills" / "1993" / "HB108.json").read_text(encoding="utf-8"))
                assert not any(s.get("party") for s in bare["sponsors"]) and not any(
                    r.get("sponsor_party") for r in got_index if r["term"] == TERM), (
                    "with no record of anyone's party read, a 1993 sponsor was given one: "
                    + ", ".join(s.get("display_full", "") for s in bare["sponsors"] if s.get("party")))
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    assert "early_party" not in unsaid.getvalue(), (
        "the build says 1989-1998 sponsors took a party where none was given")
    rows = {(r["term"], r["id"]): r for r in index}
    r108, r104, r7, r5 = (rows[(TERM, "HB108")], rows[(TERM, "HB104")], rows[(TERM, "HB7")],
                          rows[("2001-2002", "HB5")])
    assert (r108.get("sponsor_party"), r108.get("sponsor_label"), r108.get("sponsor_slug")) == (
        "R", "Rep. Dee Speaker (R - Rock 26)", B.own_slug(dee)), (
        "a 1993 prime sponsor whose every record is R is not R on the index row at the seat the "
        f"bill prints: {r108.get('sponsor_party')!r}, {r108.get('sponsor_label')!r}")
    sp = {s["name"]: s for s in pages["1993/HB108"]["sponsors"]}
    d = sp["Dee Speaker"]
    assert (d.get("party"), d.get("display"), d.get("display_full"), d.get("district_label"),
            d.get("slug")) == ("R", "Rep. Dee Speaker (R)", "Rep. Dee Speaker (R - Rock 26)",
                               "Rock 26", B.own_slug(dee)), (
        f"her row on the bill's Sponsors list: {d.get('party')!r}, {d.get('display_full')!r}, "
        f"{d.get('district_label')!r}")
    filled = pages["1993/HB104"]["sponsors"][0]
    assert (filled.get("party"), filled.get("display_full"), filled.get("district_label"),
            r104.get("sponsor_party")) == ("R", "Rep. Dee Speaker (R)", "", "R"), (
        "the General Court's own 1993 row on her page did not take her party, or took a seat: "
        f"{filled.get('display_full')!r}, {filled.get('district_label')!r}")
    assert (sp["Rae Ross"].get("party"), sp["Rae Ross"].get("display_full")) == (
        "R", "Rep. Rae Ross (R - Coos 2)"), (
        f"a Manual line of two nominations kept Rae Ross's party off: {sp['Rae Ross']}")
    for who, why in (("Sam Switch", "a 2001 bill draws him D and the 1993 Manual seats him nowhere"),
                     ("Gil Grid", "a 2023 row carries D under a label drawn R"),
                     ("Carl Careers", "the legislators table calls him D"),
                     ("Bo Ballot", "a ballot of his reads D"),
                     ("Ann Nopage", "no page")):
        s = sp[who]
        assert not s.get("party") and "(R" not in s.get("display_full", "") \
            and "(D" not in s.get("display_full", ""), (
            f"{who} took a party on a 1993 bill though {why}: {s.get('display_full')!r}")
    # THE TERM'S OWN MANUAL FOR A PERSON OF TWO PARTIES (the owner, 15 November 2026): Manny
    # Manual is R on his page and "d" in the 1993 returns, so 1993-1994's bills read D, as
    # co-sponsor and as prime; 1995's "d&r" settles nothing, and 1997's Manual seats him nowhere.
    m108, r109 = sp["Manny Manual"], rows[(TERM, "HB109")]
    m109 = pages["1993/HB109"]["sponsors"][0]
    assert (m108.get("party"), m108.get("display_full"), m109.get("party"), m109.get("display_full"),
            r109.get("sponsor_party"), r109.get("sponsor_label")) == (
        "D", "Rep. Manny Manual (D - Straf 3)", "D", "Rep. Manny Manual (D - Straf 3)",
        "D", "Rep. Manny Manual (D - Straf 3)"), (
        "a person of two parties whom the 1993 Manual prints 'd' is not D on his 1993-1994 bills, "
        f"at the printed seat: {m108.get('display_full')!r}, {m109.get('display_full')!r}, "
        f"{r109.get('sponsor_party')!r}")
    for key, why in (("1995/HB20", "the 1995 Manual's line is two nominations"),
                     ("1997/HB30", "the 1997 Manual does not seat him")):
        s, r = pages[key]["sponsors"][0], rows[("1995-1996" if key[:4] == "1995" else "1997-1998",
                                                 key.split("/")[1])]
        assert not s.get("party") and s.get("display_full") == "Rep. Manny Manual (Straf 3)" \
            and "sponsor_party" not in r, (
            f"Manny Manual took a party on {key} though {why}: {s.get('display_full')!r}, "
            f"{r.get('sponsor_party')!r}")
    assert not sp["Ann Nopage"].get("slug") and sp["Sam Switch"]["display_full"] == \
        "Rep. Sam Switch (Hills 5)", (sp["Ann Nopage"], sp["Sam Switch"])
    assert "sponsor_party" not in r7 and r7.get("sponsor_slug") == B.own_slug(legs["800102"]), (
        f"a 1993 prime sponsor the record shows in two parties has a party on the index: {r7}")
    assert (r5.get("sponsor_party"), r5.get("sponsor_label")) == (
        "R", "Rep. Dee Speaker (R - Rock 30)") and [
        s["display_full"] for s in pages["2001/HB5"]["sponsors"]] == [
        "Rep. Dee Speaker (R - Rock 30)", "Rep. Sam Switch (D - Hills 5)"], (
        f"a bill of 2001 moved: {[s['display_full'] for s in pages['2001/HB5']['sponsors']]}")
    words = said.getvalue()
    assert ("2 people with a page take its party on 3 of their 1989-1998 bills" in words
            and "5 the record shows in more than one party take the party their bill's term's "
                "Manual gives on 2 bills and none on 7" in words
            and "Manual, Manny (D, R): 1993-1994 D on 2, 1995-1996 none on 1, 1997-1998 none on 1"
                in words
            and all(f"{n} (D, R): 1993-1994 none on {k}" in words
                    for n, k in (("Switch, Sam", 2), ("Grid, Gil", 1), ("Careers, Carl", 1),
                                 ("Ballot, Bo", 1)))), (
        "the build does not say who took a party, whose term's Manual gave one and who took none: "
        + " | ".join(l for l in words.splitlines() if "sponsors: " in l and "party" in l))
    got = _app_js(
        "[scope.renderSponsors({id: 'HB108'}, " + json.dumps({"term": TERM, "sponsors": pages["1993/HB108"]["sponsors"]})
        + "), scope.cardSponsor(" + json.dumps(r108) + "), scope.partyOfSponsor(" + json.dumps(r108)
        + "), scope.partyOfSponsor(" + json.dumps(r7) + ")]",
        names=("renderSponsors", "cardSponsor", "partyOfSponsor"))
    if got is None:
        return "ok", ("R on the 1993 row, label and Sponsors list of a person every record gives R, "
                      "at the printed seat; for one of two parties the bill's term's Manual's letter "
                      "(D on 1993's bills), none on a term of two nominations or one the Manual does "
                      "not seat them in, none where no Manual of the term seats them, for no page, "
                      "or with no record read; 1999 on unchanged; said (app.js not run: node or the "
                      "stub not here)")
    html, card, party, party7 = got
    chips = {n.strip(): c for c, n in re.findall(r'class="mchip p-([A-Z])"[^>]*>(?:<a [^>]*>)?([^<]+)', html)}
    assert chips.get("Rep. Dee Speaker") == "R" and chips.get("Rep. Rae Ross") == "R" \
        and chips.get("Rep. Manny Manual") == "D" \
        and chips.get("Rep. Sam Switch") == "X" and chips.get("Rep. Ann Nopage") == "X", (
        f"the Sponsors list's chips draw the parties {chips}")
    assert (card.get("party"), party, party7) == ("R", "Republican", "Party not on file"), (
        f"the card's party {card.get('party')!r} and the filter's groups {party!r}, {party7!r}")
    return "ok", ("R on the 1993 index row, label, Sponsors list chip and card, and in the party "
                  "filter, for a person every record gives R, at the seat the bill prints; for a "
                  "person of two parties, the bill's term's Manual's letter (D on 1993's bills, "
                  "chip included), none on a term of two nominations and none on a term the Manual "
                  "does not seat them in; none for two parties seen on a 2001 bill, a 2023 row, the "
                  "legislators table or a ballot with no Manual of the term, for no page, or with "
                  "no record read; 1999 on unchanged; the build says who took what")


@check("code", "the topic model answers the labelled term's bills the General Court gave no "
               "topic, and does not treat a retired 'Regular Meeting' as one",
       needs=("topic_model",))
def _topic_labelled_term_answered(TM):
    """9 November 2026: 2025-2026's Topic column read 99% because the model
    skipped the whole term it learns from, so nine early-withdrawn House bills
    and thirteen housekeeping resolutions had none."""
    import inspect
    src = inspect.getsource(TM.apply)
    assert "if term == LABELLED_TERM" not in src, "apply() skips the labelled term whole again"
    assert "RETIRED" in src, "apply() takes a retired subject for a label"
    return "ok", "apply() answers the labelled term's unlabelled bills"


@check("build", "a bill's sitemap date stays put from one night to the next: a meeting to come does "
       "not date it, a bill with no date has none, and three standing pages carry none",
       needs=("build_bill_pages",))
def _bill_lastmod_stays_put(B):
    """The sitemap audit's fifth finding (16 October 2026): about 27 dates
    moved every night with nothing changed. 17 bills of the sitting term with
    a meeting still to come took the build's day, as did the three whose
    docket names no date, and /about, /bills and /officials took it as
    standing pages. lastmod() now dates a bill with a meeting to come by the
    latest day in its docket that has happened, gives none where there is no
    such day, and leaves every bill whose last action is past as it was; and
    the fixture site's sitemap carries no date for those three pages while
    the home page and /data, which do change every night, keep the build's."""
    built = "2026-10-16"
    ev = {"events": [{"date": "2026-03-11"}, {"date": "2026-10-15"}, {"date": "2026-10-22"}]}
    cases = [({"last_action": "2026-03-11"}, None, "2026-03-11"),
             ({"last_action": "2003-05-08"}, ev, "2003-05-08"),
             ({"last_action": "2026-10-16"}, ev, "2026-10-16"),
             ({"last_action": "2026-10-22"}, ev, "2026-10-15"),
             ({"last_action": "2026-10-22"}, {"events": [{"date": "2026-10-22"}]}, None),
             ({"last_action": "2026-10-22"}, None, None),
             ({"last_action": ""}, ev, None), ({}, None, None)]
    for b, d, want in cases:
        got = B.lastmod(b, built, d)
        assert got == want, f"lastmod({b}, {built}, {d}) is {got!r}, not {want!r}"
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "ok", f"{len(cases)} cases; the fixture site was not built: not here, " + ", ".join(absent)
    shared, base, _ran, days = _fixture_site_shared()
    sm = (shared / "site" / "sitemap.xml").read_text(encoding="utf-8")
    on = {m.group(1): m.group(2) for m in
          re.finditer(r"<url><loc>([^<]*)</loc>(?:<lastmod>([^<]*)</lastmod>)?</url>", sm)}
    for addr in ("/about", "/bills", "/officials"):
        assert base + addr in on and on[base + addr] is None, (
            f"{addr} is not listed, or carries a date that moves every night: {on.get(base + addr)}")
    for addr in ("/", "/data"):
        assert on.get(base + addr) in {d.isoformat() for d in days}, (
            f"{addr} does not carry the build's day: {on.get(base + addr)}")
    late = [u for u, m in on.items() if m and m > max(days).isoformat()]
    assert not late, f"sitemap dates after the build's day: {late[:3]}"
    return "ok", (f"{len(cases)} cases of lastmod(); on the fixture, /about, /bills and /officials "
                  "undated and / and /data dated by the build")


@check("frontend", "the bill requests' search finds a request by its sponsor's name as the list, the card or their "
       "page prints it (prime or co-sponsor, sitting, member-elect or former), the Sponsor filter has the party, "
       "and the Topic filter is named as every term's")
def _requests_search_by_name():
    """The owner, 12 November 2026: "you can't search by legislator name, by party affiliation of returning
    or new members". A bill's sponsor is found through the Sponsor filter and a name typed in the box lists
    nothing (17 October); a request has a title and a sponsor and nothing else, so for it the box reads the
    name too (requestByName): every word typed a word of the prime sponsor's or a co-sponsor's name, a title
    typed ("rep", "sen") agreeing with the label's, and a single word a WHOLE word -- "bail" is not Rep.
    Bailey. A request whose title has the words lists as it did. Held, on a fixture of requests: a full name
    lists the sponsor's requests and the ones they co-sponsor; "bail" lists the bail request and not
    Bailey's; "sen" before a Rep.'s name lists none; a member-elect, whose label is titled "Rep.-elect"
    since 17 November 2026 (build_lsrs.elect_title), is found by "rep jane doe" and not by "sen jane doe", and
    the Sponsor list names them without the title, as it names a sitting member without "Rep."; the party filter counts a sitting member's and a member-elect's party; the Sponsor list
    names a sponsor with the party their label gives (a request's label has no seat); the Topic group of the
    requests is named "Topic", as another term's is (the owner, 14 November 2026: "remove the topic from title
    label"; it said "(from the title)" until then); a bill's own search still lists no bill for a name.

    AND BY EVERY NAME THE SITE PRINTS FOR THE SPONSOR (the pre-release review of 13 November 2026): "Lee C.
    Nyquist", the name on his cards and his page, and "James Creighton", the name on his page, found none
    of their requests, which the list spells "Lee Nyquist" and "Jim Creighton". Held on two rows that
    build_lsrs makes from the list, a winner and a page, as the build does (rows_from, then
    with_sponsor_names, which writes `sponsor_names`); each name finds its request in the box, in the
    Sponsor filter's offer and in that filter's own box; the surname and the list's own spelling still
    do; the page drawn for "Lee C. Nyquist" lists his request and offers no "'c' alone"; and "c" alone
    does not list him by his initial. The filter's box also lists a sponsor typed as the card prints them
    ("W. Packy Campbell", whom the list calls "W Packy Campbell") or with an initial's full stop left off
    ("lee c nyquist"), as the search box does; and a spelling that differs by a hyphen or a space is a
    name of its own, one that differs by a full stop alone is not."""
    def req(n, title, who, label, slug, party, cosp=()):
        row = {"id": f"LSR2027000{n}", "n": f"LSR 2027-000{n}", "title": title, "sponsor": who,
               "sponsor_label": label, "sponsor_slug": slug, "lsr": True, "term": "2027-requests",
               "year": 2027, "kind": "", "status": "Filed as a request", "committees": [],
               "committee": "", "topic": "", "votedays": [], "nrc": 0, "last_action": "",
               "hayT": f"lsr2027000{n} lsr 2027-000{n} " + title.lower()}
        if party:
            row["sponsor_party"] = party
        if cosp:
            row["cosp"] = list(cosp)
        return row
    rows = [req(1, "relative to school funding.", "Ellen Read", "Rep. Ellen Read (D)", "ellen-read-rock-10", "D"),
            req(2, "relative to the state flag.", "Pat Bailey", "Rep. Pat Bailey (R)", "pat-bailey-hills-1", "R",
                ["Ellen Read"]),
            req(3, "relative to dog licensing.", "Jane Doe", "Rep.-elect Jane Doe (R)", "jane-doe-elect",
                "R"),
            req(4, "relative to fishing licences.", "Sam Senn", "Sen. Sam Senn (D)", "sam-senn-sd-1", "D"),
            dict(req(5, "relative to the budget.", "Nobody Known", "Nobody Known", "", ""),
                 topic="Taxes - State", topic_by="title"),
            req(6, "relative to bail reform.", "Chris Moore", "Rep. Chris Moore (D)", "chris-moore-hills-2", "D")]
    rows[0]["topic"], rows[0]["topic_by"] = "Education - General", "title"
    # AND TWO SPONSORS THE SITE PRINTS OTHERWISE THAN THE LIST, made as the build makes them: the list's
    # "Lee Nyquist" is the winner "Lee C. Nyquist" with a member-elect's page, and its "Jim Creighton" the
    # winner of that name, whose page is a sitting member's, "Rep. James Creighton".
    import build_lsrs as L
    with tempfile.TemporaryDirectory() as d:
        site = Path(d)
        (site / "legislators.json").write_text(json.dumps([{
            "name": "Creighton, James", "slug": "james-creighton-hills-30", "display": "Rep. James Creighton (R)",
            "display_plain": "Rep. James Creighton"}]), encoding="utf-8")
        (site / "elect_pages.json").write_text(json.dumps({"pages": [{
            "name": "Lee C. Nyquist", "slug": "lee-c-nyquist-hills-42", "party": "D", "chamber": "H",
            "race": "H|Hillsborough|42"}]}), encoding="utf-8")
        who, names = L.roster(site), L.page_names(site)
    ws = L.election_winners(
        {"races": {"H|Hillsborough|42": {"candidates": [{"name": "Lee C. Nyquist", "party": "d", "elected": True}]},
                   "S|8": {"candidates": [{"name": "Jim Creighton", "party": "r", "elected": True}]}}},
        {"S|8": {"elected": [{"n": "Jim Creighton", "p": "R", "s": "james-creighton-hills-30"}]}},
        [{"slug": "lee-c-nyquist-hills-42", "name": "Lee C. Nyquist", "race": "H|Hillsborough|42"}], [])
    # Lee Nyquist's title has no word in c, and Creighton's does: "c" alone lists Creighton's by its title.
    built, _ = L.rows_from(
        [{"lsr": "2027-0007", "session": 2027, "body": "HB", "title": "relative to trout stocking.",
          "sponsor": "Lee Nyquist"},
         {"lsr": "2027-0008", "session": 2027, "body": "SB", "title": "relative to county conservation districts.",
          "sponsor": "Jim Creighton"}], who, {}, 2027, ws)
    L.with_sponsor_names(built, names)
    assert [(r["sponsor_label"], r.get("sponsor_names")) for r in built] == [
        ("Lee C. Nyquist (D)", ["Lee C. Nyquist"]), ("Jim Creighton (R)", ["James Creighton"])], (
        "build_lsrs does not give a request the names its card and its sponsor's page print: "
        f"{[(r['sponsor_label'], r.get('sponsor_names')) for r in built]}")
    # A spelling that differs by a full stop alone is the same words; by a hyphen or a space it is not,
    # since the search splits a name on both.
    odd = [{"sponsor": "W Packy Campbell", "sponsor_label": "W. Packy Campbell (R)", "sponsor_slug": ""},
           {"sponsor": "Maryjane Smith", "sponsor_label": "Mary-Jane Smith (D)", "sponsor_slug": ""},
           {"sponsor": "Tom McDonald", "sponsor_label": "Tom Mc Donald (R)", "sponsor_slug": ""}]
    L.with_sponsor_names(odd, {})
    assert [r.get("sponsor_names") for r in odd] == [None, ["Mary-Jane Smith"], ["Tom Mc Donald"]], (
        "a spelling that differs by a full stop alone is added, or one that differs by a hyphen or a space "
        f"is not: {[r.get('sponsor_names') for r in odd]}")
    for r in built:
        r["hayT"] = f"{r['id'].lower()} {r['n'].lower()} {r['title'].lower()}"
    rows += built
    # And a sponsor whose card differs from the list by a full stop, for the Sponsor filter's box.
    rows.append(req(9, "relative to boating.", "W Packy Campbell", "W. Packy Campbell (R)",
                    "w-packy-campbell-straf-3", "R"))
    old = [{"id": "HB1", "n": "HB 1", "title": "a bill", "sponsor": s, "sponsor_label": lab, "term": "1995-1996",
            "year": 1995, "kind": "done", "status": "Killed", "chip": "Died", "committees": [], "committee": "",
            "topic": "", "votedays": [], "nrc": 0, "last_action": "", "hayT": "hb1 hb 1 a bill"}
           for s, lab in (("Allen", "Rep. Allen (Hills 1)"), ("Allen", "Rep. Allen (Rock 3)"),
                          ("F. Riley", "Rep. F. Riley (Hills 44)"))]
    # AND TWO OF ONE SURNAME: one the General Court's record for the bill names (sponsor_person: the
    # full name, theirs alone) and one still as printed (the surname and the seat).
    old += [dict(old[0], sponsor="Dana Moore", sponsor_label="Rep. Dana Moore (Graf 5)", sponsor_person=1),
            dict(old[0], sponsor="Moore", sponsor_label="Rep. Moore (Hills 2)")]
    for i, r in enumerate(old):
        r["id"], r["n"] = f"HB{i + 1}", f"HB {i + 1}"
    meta = {"terms": ["1995-1996"], "committee_codes": {}, "topics": [],
            "requests": {"term": "2027-requests", "year": 2027, "n": 9, "withdrawn": 0, "label": "2027 Bill Requests"}}
    got = _app_js("""(() => {
  const norm = (s) => scope.hintWords(s).join(" ");
  // Each Sponsor row's key and the words its chip reads (the picker of 19 November 2026 draws a
  // term's members as their chips, spPicker; All Terms the name alone).
  const rowsOf = (h) => [...h.matchAll(/data-f="sponsor"\\s+value="([^"]*)"[^>]*>\\s*(?:<span class="spn">([\\s\\S]*?)|<span>([^<]*))<\\/span>\\s*<span class="c"/g)]
    .map(m => [m[1], (m[2] || m[3] || "").replace(/<[^>]+>/g, "").replace(/\\s+/g, " ").trim()]);
  const out = {};
  scope.setState("2027-requests", %s, %s);
  const listed = (q) => { scope.setQuery(q); return scope.IDX().filter(b => scope.matches(b)).map(b => b.id.slice(-1)); };
  out.full = listed("ellen read"); out.surname = listed("read"); out.rep = listed("rep ellen read");
  out.sen = listed("sen ellen read"); out.bail = listed("bail"); out.bailey = listed("bailey");
  out.elect = listed("rep jane doe"); out.title = listed("dog"); out.senator = listed("senator sam senn");
  out.none = listed("xyzzy"); out.electSen = listed("sen jane doe");
  // A sponsor by the card's and the page's spelling, and by the list's own; never by an initial alone.
  out.nyquist = listed("Lee C. Nyquist"); out.nyquistRep = listed("Rep. Lee C. Nyquist");
  out.nyquistSur = listed("Nyquist"); out.creighton = listed("James Creighton");
  out.creightonOwn = listed("Jim Creighton"); out.initial = listed("c");
  // Drawn as the page draws it once the requests' text index is in (were nothing listed, past "Reading").
  scope.setText("2027-requests", "ready"); scope.setQuery("Lee C. Nyquist");
  try { scope.render(); out.nyquistPage = document.querySelector("#results").innerHTML; }
  catch (e) { out.nyquistPage = "RENDER " + e.message; }
  out.hintNyquist = scope.sponsorHint("lee c nyquist", scope.IDX()).map(p => [p.name, p.label]);
  out.hintCreighton = scope.sponsorHint("james creighton", scope.IDX()).map(p => [p.name, p.label]);
  out.hintInitial = scope.sponsorHint("c", scope.IDX()).map(p => p.name);
  const box = (v) => { scope.setSponsorBox(v); scope.renderFacets();
    return rowsOf(document.querySelector("#facets").innerHTML); };
  out.boxLeeC = box("lee c"); out.boxJames = box("james");
  out.boxPacky = box("W. Packy Campbell"); out.boxLeeCNyquist = box("lee c nyquist");
  scope.setSponsorBox("");
  scope.setQuery("");
  scope.renderFacets();
  const f = document.querySelector("#facets").innerHTML;
  out.topicHead = /data-g="topic"[^>]*><span>([^<]*)</.exec(f)[1];
  out.party = [...f.matchAll(/data-f="party"\\s+value="([^"]*)"[\\s\\S]*?<span class="c">([\\d,]+)</g)].map(m => [m[1], +m[2]]);
  out.cosp = /<span>(Include co-sponsored [a-z]+)</.exec(f)[1];
  scope.setSponsorBox("read"); scope.renderFacets();
  out.sponsors = rowsOf(document.querySelector("#facets").innerHTML);
  scope.setSponsorBox("");
  scope.setSponsorBox("doe"); scope.renderFacets();
  out.does = rowsOf(document.querySelector("#facets").innerHTML);
  scope.setSponsorBox("");
  scope.sel.party.add("Republican"); out.republican = scope.IDX().filter(b => scope.matches(b)).map(b => b.id.slice(-1));
  scope.sel.party.clear();
  scope.sel.topic.add("Taxes - State"); out.topicTicked = scope.IDX().filter(b => scope.matches(b)).map(b => b.id.slice(-1));
  scope.sel.topic.clear();
  // A bill's own search: the name lists none of its bills, and is offered the filter.
  scope.setState("1995-1996", %s, %s);
  scope.renderFacets();
  out.oldTopicHead = /data-g="topic"[^>]*><span>([^<]*)</.exec(document.querySelector("#facets").innerHTML)[1];
  out.billsByName = listed("allen");
  out.hintAllen = scope.sponsorHint("allen", scope.IDX()).map(p => [p.name, p.label]);
  out.hintFrank = scope.sponsorHint("frank riley", scope.IDX()).map(p => [p.name, p.label]);
  out.hintRiley = scope.sponsorHint("riley", scope.IDX()).map(p => [p.name, p.label]);
  scope.setSponsorBox("allen"); scope.renderFacets();
  out.allens = rowsOf(document.querySelector("#facets").innerHTML);
  scope.setSponsorBox("");
  out.hintDana = scope.sponsorHint("dana moore", scope.IDX()).map(p => [p.name, p.label]);
  scope.setSponsorBox("moore"); scope.renderFacets();
  out.moores = rowsOf(document.querySelector("#facets").innerHTML);
  scope.setSponsorBox("");
  scope.setQuery(""); scope.sel.sponsor.add("Allen (Rock 3)"); out.rock3 = scope.IDX().filter(b => scope.matches(b)).map(b => b.id);
  return out;
})()""" % (json.dumps(meta), json.dumps(rows), json.dumps(meta), json.dumps(old)),
        names=("hintWords", "matches", "render", "renderFacets", "sel", "sponsorHint", "IDX: () => IDX",
               "setText: (t, v) => { TEXT[t] = v; }",
               "setQuery: (q) => { query = q; }", "setSponsorBox: (v) => { sponsorFilter = v; }",
               "setState: (t, m, rs) => { term = t; META = m; IDX = rs; for (const k in SP_LABELS) delete SP_LABELS[k]; noteSponsors(t, rs); }"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert got["full"] == ["1", "2"], f"'ellen read' lists {got['full']}: her request and the one she co-sponsors"
    assert got["surname"] == ["1", "2"] and got["rep"] == ["1", "2"], (got["surname"], got["rep"])
    assert got["sen"] == ["2"], (f"'sen' before a Rep.'s name lists {got['sen']}: her own request is ruled "
                                 "out, the one she co-sponsors (a name alone) is not")
    assert got["bail"] == ["6"], f"'bail' lists {got['bail']}: the bail request, and not Rep. Bailey's"
    assert got["bailey"] == ["2"], got["bailey"]
    assert got["elect"] == ["3"], f"a member-elect is not found by name: {got['elect']}"
    assert got["title"] == ["3"] and got["none"] == [], (got["title"], got["none"])
    assert got["senator"] == ["4"], got["senator"]
    assert got["topicHead"] == "Topic", f"the requests' Topic filter says {got['topicHead']!r}"
    assert got["party"] == [["Republican", 4], ["Democrat", 4], ["Party not on file", 1]], (
        f"the party filter counts {got['party']}: sitting and elect members alike")
    assert got["cosp"] == "Include co-sponsored requests", got["cosp"]
    assert ["Ellen Read", "Rep. Ellen Read (D)"] in got["sponsors"], f"the Sponsor list shows {got['sponsors']}"
    assert got["does"] == [["Jane Doe", "Rep.-elect Jane Doe (R)"]] and got["electSen"] == [], (
        f"a member-elect's title: the Sponsor list shows {got['does']}, 'sen jane doe' lists {got['electSen']}")
    assert got["republican"] == ["2", "3", "8", "9"], f"the party filter lists {got['republican']}"
    # The names the site prints. Lee C. Nyquist's request is 7, Jim (James) Creighton's 8.
    assert got["nyquist"] == ["7"] and got["nyquistRep"] == ["7"], (
        f"'Lee C. Nyquist', the name his card prints, lists {got['nyquist']} (with 'Rep.' {got['nyquistRep']})")
    assert got["creighton"] == ["8"], f"'James Creighton', the name his page prints, lists {got['creighton']}"
    assert got["nyquistSur"] == ["7"] and got["creightonOwn"] == ["8"], (
        f"the surname and the list's own spelling no longer find them: {got['nyquistSur']}, {got['creightonOwn']}")
    assert got["initial"] == ["8"], (
        f"'c' alone lists {got['initial']}: Creighton's request by its title, and never Nyquist's by his initial")
    page = got["nyquistPage"]
    assert "LSR 2027-0007" in page and "No bills match" not in page and "alone matches" not in page, (
        "the page drawn for 'Lee C. Nyquist' does not list his request, or offers a word of his name alone "
        "('c' alone): " + re.sub(r"<[^>]+>", " ", page)[:240])
    assert got["hintNyquist"] == [["Lee Nyquist", "Lee C. Nyquist"]] and got["hintCreighton"] == [
        ["Jim Creighton", "Jim Creighton"]] and got["hintInitial"] == [], (
        f"the Sponsor filter's offer for the printed names: {got['hintNyquist']}, {got['hintCreighton']}; "
        f"for 'c' alone {got['hintInitial']}")
    assert got["boxLeeC"] == [["Lee Nyquist", "Lee C. Nyquist (D)"]] and got["boxJames"] == [
        ["Jim Creighton", "Jim Creighton (R)"]], (
        f"the Sponsor filter's box: 'lee c' lists {got['boxLeeC']}, 'james' {got['boxJames']}")
    assert got["boxPacky"] == [["W Packy Campbell", "W. Packy Campbell (R)"]] and got["boxLeeCNyquist"] == [
        ["Lee Nyquist", "Lee C. Nyquist (D)"]], (
        f"the Sponsor filter's box: 'W. Packy Campbell', as his card prints it, lists {got['boxPacky']}; "
        f"'lee c nyquist', the initial typed without its full stop, {got['boxLeeCNyquist']}")
    assert got["topicTicked"] == ["5"], got["topicTicked"]
    assert got["oldTopicHead"] == "Topic", got["oldTopicHead"]
    assert got["billsByName"] == [], f"a name typed lists bills: {got['billsByName']}"
    assert sorted(n for n, _ in got["hintAllen"]) == ["Allen (Hills 1)", "Allen (Rock 3)"], (
        f"two people of one surname are one: {got['hintAllen']}")
    assert got["hintFrank"] == [["F. Riley (Hills 44)", "Rep. F. Riley (Hills 44)"]], (
        f"'frank riley' does not fit 'F. Riley': {got['hintFrank']}")
    assert [n for n, _ in got["hintRiley"]] == ["F. Riley (Hills 44)"], got["hintRiley"]
    assert [v for v, _ in got["allens"]] == ["Allen (Hills 1)", "Allen (Rock 3)"], (
        f"the Sponsor list joins two Allens: {got['allens']}")
    assert got["rock3"] == ["HB2"], f"the second Allen's filter lists {got['rock3']}"
    assert got["hintDana"] == [["Dana Moore", "Rep. Dana Moore"]], (
        f"a sponsor the General Court's record names is not their full name alone: {got['hintDana']}")
    assert sorted(got["moores"]) == [["Dana Moore", "Rep. Dana Moore (Graf 5)"], ["Moore (Hills 2)", "Rep. Moore (Hills 2)"]], (
        f"a named sponsor and one left as printed are not two choices: {got['moores']}")
    return "ok", ("a request is found by name, prime or co-sponsor, a title agreeing, a whole word for a "
                  "single one, and by the names its card and its sponsor's page print ('Lee C. Nyquist', "
                  "'James Creighton'), never by an initial alone; party counts are in the Sponsor filter; its "
                  "Topic filter is named as every term's; an older term tells two Allens apart and 'frank riley' fits "
                  "'F. Riley'")


@check("build", "a bill request gets its sponsor's party and, where its title says enough, a topic of the "
       "site's own, marked as the title's, learned from every term's official code; Miscellaneous where the "
       "title does not")
def _requests_party_and_topic():
    """The owner, 12 November 2026. build_lsrs writes `sponsor_party` from the roster's label (a sitting
    member's and a member-elect's alike) and `cosp`, and request_topics gives each request a topic from its
    title: the title half of topics.py's classifier, trained on the labelled bills, the site's category
    through vocabulary_of, `topic_by` "title". A request below the confidence threshold is Miscellaneous
    (the owner, 14 November 2026: "assign topics not yet assigned to misc"; it had no topic until then), never
    a guess at a named topic, and a request already a bill keeps the bill's. Held on a fixture: a title with
    a study or housing phrase gets that category by the exact rules; the words of a labelled topic get it; a
    title nothing in the model has seen is Miscellaneous, as is every request where no labelled bill leaves
    a model to ask, a study or housing title apart; the answer is the same under another hash seed."""
    import build_lsrs as L
    import request_topics as RT
    who = {"ellenread": ("Rep. Ellen Read (D)", "ellen-read-rock-10"),
           "janedoe": ("Jane Doe (R)", "jane-doe-elect", "H")}
    lsrs = [{"lsr": "2027-0001", "session": 2027, "body": "HB", "title": "t", "sponsor": "Ellen Read",
             "withdrawn": False, "cosponsors": []},
            {"lsr": "2027-0002", "session": 2027, "body": "HB", "title": "t", "sponsor": "Jane Doe",
             "withdrawn": False, "cosponsors": ["Ellen Read"]},
            {"lsr": "2027-0003", "session": 2027, "body": "HB", "title": "t", "sponsor": "Nobody Known",
             "withdrawn": False, "cosponsors": []}]
    rows, _ = L.rows_from(lsrs, who, {}, 2027)
    got = {r["n"]: (r.get("sponsor_party"), r.get("cosp")) for r in rows}
    assert got == {"LSR 2027-0001": ("D", None), "LSR 2027-0002": ("R", ["Ellen Read"]),
                   "LSR 2027-0003": (None, None)}, got
    assert L.party_of("Rep. Ellen Read (D)") == "D" and L.party_of("Jane Doe") == "" \
        and L.party_of("Sen. X (R - SD 1)") == "", "party_of reads something that is no party letter"
    # A ballot's two-letter label, kept as the results print it (George Randell, Carroll 8, 2026,
    # whose request carried no party at all): the search and the chip read its first letter.
    assert L.party_of("Rep.-elect George Randell (I/D)") == "I/D" and L.party_of("X (I/)") == "" \
        and L.party_of("X (DR)") == "", "party_of misreads a two-letter ballot label"
    bills = {"2025-2026": {}}
    topics = ["Elections", "Taxes - State", "Education - General"]
    words = {"Elections": ["ballot", "voter", "election", "polling"],
             "Taxes - State": ["tax", "revenue", "rate", "business"],
             "Education - General": ["school", "pupil", "teacher", "district"]}
    for i in range(30):
        for t in topics:
            w = words[t]
            bills["2025-2026"][f"HB{len(bills['2025-2026']) + 1}"] = {
                "title": f"relative to {w[i % 4]} {w[(i + 1) % 4]} {w[(i + 2) % 4]} matters.", "subject": t}
    model = RT.train_on(bills, subjects={}, codes={})
    assert model is not None and RT.train_on({"2023-2024": {"HB1": {"title": "x", "subject": "Elections"}}},
                                             subjects={}, codes={}) is None, (
        "no labelled term should leave no model")
    reqs = [{"title": "relative to voter ballot election procedures.", "n": "a"},
            {"title": "relative to business tax rate revenue.", "n": "b"},
            {"title": "establishing a commission to study the use of drones.", "n": "c"},
            {"title": "relative to quartz flamingo xylophone.", "n": "d"},
            {"title": "relative to tax rate revenue.", "n": "e", "introduced": "HB 5", "topic": "Kept"},
            {"title": "relative to affordable housing development.", "n": "f"}]
    fake = lambda s, rec: {"Elections": "Elections", "Taxes - State": "Taxes - State"}.get(s, s)
    RT.assign(reqs, model, fake)
    by = {r["n"]: (r["topic"], r.get("topic_by", "")) for r in reqs}
    assert by["a"] == ("Elections", "title") and by["b"] == ("Taxes - State", "title"), by
    assert by["c"] == ("Study Committees and Commissions", "title"), f"a study title: {by['c']}"
    assert by["f"] == ("Housing", "title"), f"a housing title: {by['f']}"
    assert by["d"] == ("Miscellaneous", "title"), (
        f"a title the model has never seen got {by['d']}: Miscellaneous, from the title")
    assert by["e"] == ("Kept", ""), "a request already a bill had its topic taken"
    bare = [{"title": "relative to voter ballot election procedures.", "n": "a"},
            {"title": "establishing a commission to study the use of drones.", "n": "c"}]
    RT.assign(bare, None, fake)
    assert [(r["topic"], r["topic_by"]) for r in bare] == [
        ("Miscellaneous", "title"), ("Study Committees and Commissions", "title")], (
        f"with no model to ask, a request is not Miscellaneous or a study title loses its rule: {bare}")
    # FROM EVERY TERM'S OFFICIAL CODE (15 November 2026): an archived bill whose LSR the General Court's
    # code names (official_topics.adopt) teaches the model what the current term alone does not; the
    # current term counts CURRENT_WEIGHT times; an LSR the database files under another bill number, or a
    # code with no name, teaches nothing; and the caller's bills are never changed.
    arch = {"2025-2026": bills["2025-2026"],
            "2001-2002": {f"HB{900 + i}": {"title": "relative to snowmobile trail grooming.", "lsr_year": 2001,
                                           "lsr_num": 100 + i} for i in range(12)}}
    good = {(2001, 100 + i): ("FGA", f"HB{900 + i}") for i in range(12)}
    names = {"FGA": {"name": "Fish & Game"}}
    m2 = RT.train_on(arch, subjects=names, codes=good)
    assert m2["from"] == {"current": 90, "archived": 12} and RT.CURRENT_WEIGHT == 3, m2.get("from")
    assert m2["n"] == 90 * RT.CURRENT_WEIGHT + 12, f"the model learned from {m2['n']} rows"
    def asked(m):
        r = {"title": "relative to snowmobile trail grooming.", "n": "g"}
        RT.assign([r], m, fake)
        return r["topic"]
    assert asked(m2) == "Fish & Game" and asked(model) == "Miscellaneous", (
        f"an archived term's official code does not place a title only it knows: {asked(m2)}, {asked(model)}")
    elsewhere = {(2001, 100 + i): ("FGA", "HB1") for i in range(12)}
    assert RT.train_on(arch, subjects=names, codes=elsewhere)["from"]["archived"] == 0 \
        and RT.train_on(arch, subjects={"FGA": {"name": ""}}, codes=good)["from"]["archived"] == 0, (
        "an LSR filed under another bill, or a code with no name, taught the model")
    assert "subject" not in arch["2001-2002"]["HB900"], "training changed the caller's bills"
    prog = ("import sys, json; sys.path.insert(0, '.'); import _paths, request_topics as R; "
            "b = {'2025-2026': {'HB%d' % i: {'title': 'relative to %s %s matters.' % (w, v), 'subject': t} "
            "for i, (t, w, v) in enumerate([('Elections', 'ballot', 'voter'), ('Taxes - State', 'tax', 'rate'), "
            "('Elections', 'election', 'ballot'), ('Taxes - State', 'revenue', 'tax')] * 8)}}; "
            "m = R.train_on(b, subjects={}, codes={}); r = [{'title': t} for t in ('relative to ballot voter.', 'relative to tax rate.', "
            "'relative to zzz.')]; R.assign(r, m, lambda s, rec: s); print(json.dumps(r))")
    outs = []
    for seed in ("1", "2"):
        res = _run([sys.executable, "-c", prog], capture_output=True, text=True, timeout=120,
                   env={**os.environ, "PYTHONHASHSEED": seed})
        assert res.returncode == 0, (res.stderr or res.stdout)[-300:]
        outs.append(res.stdout.strip().splitlines()[-1])
    assert outs[0] == outs[1], "the topics differ under another hash seed"
    return "ok", ("party read from the roster's label for sitting and elect members; a title gets the "
                  "study or housing category, a labelled topic by its words, or Miscellaneous, with or without "
                  "a model; the model learns from every term's official code, the current term x3, and never "
                  "from an LSR filed under another bill or a nameless code; the same under two hash seeds")


@check("build", "the request topic score says what the bills beneath its threshold would give: their accuracy by "
                "margin band and the official topic of an identical earlier title, counted as the docstring says")
def _request_topics_below_threshold():
    """The matcher polish of 16 November 2026 measured whether anything the title gives could place the 178
    Miscellaneous requests as well as the 314 are placed; nothing could, and request_topics.score() now prints
    the evidence beside its table (below, same_title), so the claim in its docstring is a command's output.
    Held on a fixture: a band counts only the answers inside it and under the threshold, a title the model
    does not know is in none; the identical-title rule keeps the newest training bill of a title, compares in
    the site's categories, and counts only bills beneath the threshold; and score() prints both."""
    import inspect
    import request_topics as RT
    got = [(6.5, True), (5.5, True), (5.2, False), (4.1, False), (3.0, True), (0.5, False), (-1.0, True), (6.0, False)]
    assert RT.below(got) == [(5, 6, 1, 2), (4, 5, 0, 1), (2, 4, 1, 1), (0, 2, 0, 1)], RT.below(got)
    assert RT.below(got, threshold=5.0)[0] == (5, 5.0, 0, 0), "a band reached above the threshold"
    rows = [("HB1", {"title": "relative to x.", "subject": "Elections"}),
            ("HB2", {"title": "Relative to  X", "subject": "Taxes - State"}),
            ("HB3", {"title": "relative to y", "subject": "Insurance"})]
    test = [("HB9", {"title": "relative to x", "subject": "Taxes - State"}),
            ("HB8", {"title": "relative to y.", "subject": "Insurance"}),
            ("HB7", {"title": "relative to z", "subject": "Elections"})]
    site = lambda s, rec: {"Taxes - State": "Taxes - State", "Insurance": "Insurance", "Elections": "Elections"}.get(s)
    assert RT.same_title(rows, test, [(2.0, False), (7.0, True), (1.0, False)], site) == (1, 1), (
        "the identical-title rule: the newest of a title, only beneath the threshold, in the site's categories")
    assert RT.same_title(list(reversed(rows)), test, [(2.0, False), (7.0, True), (1.0, False)], site) == (0, 1), (
        "the identical-title rule did not keep the last (newest) bill of a title")
    src = inspect.getsource(RT.score)
    assert "below(" in src and "same_title(" in src, "score() no longer prints what beneath the threshold would give"
    assert "WHAT COULD PLACE THEM" in (RT.__doc__ or ""), "the docstring no longer records the measurement"
    return "ok", ("margin bands beneath the threshold counted, an unknown title in none; the identical-title "
                  "rule keeps the newest, counts only beneath the threshold, in the site's categories; score() "
                  "prints both")


@check("build", "a request's topic is the owner's where she judged its topic card on the bench: the guess she "
                "called right, the topic she named for one she called wrong; never a guess by itself, nor "
                "anyone's answer but hers")
def _request_topics_owner_word():
    """The owner, 24 November 2026: put the requests the title leaves Miscellaneous "in the bench with your
    best guess so I can judge them". The assistant's guess is a topic card's claim (key "topic|2027
    requests|LSR 2027-0123"); her verdict, merged into review/checked.jsonl, becomes the request's topic
    (request_topics.owner_topics, owner_assign; topic_by "owner").

    Held on a fixture ledger read by bench_ledger's rules: correct takes the claim; wrong takes the better
    topic she named; a General Court name is read through the site's vocabulary with the request's title
    (Crimes, Crim.Proc. & Corr. for a parole title is Corrections); a retired name changes nothing; unsure,
    wrong with nothing named, and a contributor's line change nothing; her later line beats her earlier
    one, and her line beats a contributor's merged after it; a bill's topic card is not a request's; a
    request already a bill keeps its own topic; and with no ledger nothing changes."""
    import request_topics as RT
    tmp = Path(tempfile.mkdtemp(prefix="gr-owner-topics-"))
    try:
        def line(n, verdict, claim, by="hand", better=None, key=None):
            d = {"kind": "topic", "key": key or f"topic|2027 requests|LSR 2027-{n}", "verdict": verdict,
                 "note": "", "by": by, "shown": {"topic": claim, "guess_by": "assistant"}, "at": "2026-11-25T10:00",
                 "via": "bench"}
            if better is not None:
                d["fields"] = {"better_topic": better}
            return d
        led = [line("0001", "correct", "Elections"),
               line("0002", "wrong", "Elections", better="Housing"),
               line("0003", "wrong", "Courts and Procedure", better="Crimes, Crim.Proc. & Corr."),
               line("0004", "correct", "Insurance", by="link:abc123"),
               line("0005", "unsure", "Animals"),
               line("0006", "wrong", "Gambling"),
               line("0007", "correct", "Retirement"), line("0007", "wrong", "Retirement", better="Taxes - State"),
               line("0008", "correct", "Elections"), line("0008", "wrong", "Elections", by="link:abc123",
                                                          better="Insurance"),
               line("0009", "wrong", "Legislature", better="CACR"),
               line("0010", "correct", "Agriculture"),
               line("0", "correct", "Elections", key="topic|2025-2026|HB1")]
        p = tmp / "checked.jsonl"
        p.write_text("".join(json.dumps(d) + "\n" for d in led), encoding="utf-8")
        judged = RT.owner_topics(p)
        assert judged == {"LSR 2027-0001": "Elections", "LSR 2027-0002": "Housing",
                          "LSR 2027-0003": "Crimes, Crim.Proc. & Corr.", "LSR 2027-0007": "Taxes - State",
                          "LSR 2027-0008": "Elections", "LSR 2027-0009": "CACR",
                          "LSR 2027-0010": "Agriculture"}, judged
        assert RT.owner_topics(tmp / "none.jsonl") == {}, "a ledger that is not there gave topics"
        titles = {"0003": "relative to the parole of inmates"}
        rows = [{"n": f"LSR 2027-{n}", "title": titles.get(n, "t"), "topic": "Miscellaneous", "topic_by": "title"}
                for n in ("0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009")]
        rows.append({"n": "LSR 2027-0010", "title": "t", "topic": "Elections", "topic_by": "title",
                     "introduced": "2027-01-04"})
        n = RT.owner_assign(rows, judged)
        got = {r["n"][4:]: (r["topic"], r["topic_by"]) for r in rows}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    misc = ("Miscellaneous", "title")
    want = {"2027-0001": ("Elections", "owner"), "2027-0002": ("Housing", "owner"),
            "2027-0003": ("Corrections", "owner"), "2027-0004": misc, "2027-0005": misc, "2027-0006": misc,
            "2027-0007": ("Taxes - State", "owner"), "2027-0008": ("Elections", "owner"),
            "2027-0009": misc, "2027-0010": ("Elections", "title")}
    bad = [f"{k}: {got.get(k)}, not {v}" for k, v in want.items() if got.get(k) != v]
    assert not bad, "a request's topic from the owner's verdicts: " + "; ".join(bad)
    assert n == 5, f"owner_assign counted {n} rows, not 5"
    return "ok", ("her right takes the guess, her wrong the topic she named (a General Court name in the site's "
                  "category, a retired one nothing); unsure, wrong alone and a contributor's line change "
                  "nothing; her last line counts and beats a contributor's; a bill's card and a request "
                  "already a bill are left alone")


@check("build", "the bug hunt of 11 November 2026: the sitting term rolls on Organization Day in the browser "
       "and in unh_extract, a report is filed by the day it is dated, and a month word is a whole month")
def _bug_hunt_terms_and_dates():
    """#3 sittingTerm said 2027-2028 on 1 December 2026 and the Python rule says 2025-2026 until the
    first Wednesday (2 December). #4 unh_extract.term_of rolled all of December. #5 fetch_reports_db
    filed a report by its year alone (term_of) where term_on knows Organization Day. #6 J_MONTH_DAY
    read "Decision 3, 2021" as December 3."""
    import datetime as dt
    import proceedings as P
    import unh_extract as U
    import build_site_v2 as B
    for y, m, d, want in ((2008, 12, 1, "2007-2008"), (2008, 12, 2, "2007-2008"),
                          (2008, 12, 3, "2009-2010"), (2026, 12, 1, "2025-2026"),
                          (2026, 12, 2, "2027-2028"), (1996, 12, 4, "1997-1998"),
                          (2007, 12, 1, "2007-2008")):
        got = U.term_of(y, m, d)
        assert got == want and got == P.term_on(f"{y}-{m:02d}-{d:02d}"), (
            f"unh_extract.term_of({y}, {m}, {d}) is {got}, Organization Day's rule says {want}")
    assert U.term_of(2008, 12) == "2009-2010", "a sitting known only to its month still rolls in December"
    src = _source("src/fetch/gc_db/fetch_reports_db.py")
    assert "P.term_on(rec[" in src and "P.term_of(rec[" not in src, (
        "fetch_reports_db files a report by its year alone, not by the day it is dated")
    for text, want in (("Decision 3, 2021", None), ("Mayor 4, 2020", None), ("Marginal 12, 2019", None),
                       ("Octopus 5, 2019", None), ("Dec. 3, 2021", "Dec"), ("Sept 4, 2020", "Sept"),
                       ("March 5, 2019", "March"), ("adopted Jan 9, 2021", "Jan"), ("May 4, 2020", "May")):
        m = B.J_MONTH_DAY.search(text)
        assert (m.group(1) if m else None) == want, f"J_MONTH_DAY read {text!r} as {m and m.group(0)!r}"
    assert B._j_stated_day("Decision 3, 2021") == "", "a docket line's day was read out of the word Decision"
    assert B._j_stated_day("Referred Dec 3, 2021") == "2021-12-03", "a month, a day and a year no longer read"
    days = []
    d = dt.date(2024, 11, 20)
    while d <= dt.date(2024, 12, 10):
        days.append(d)
        d += dt.timedelta(days=1)
    d = dt.date(2026, 11, 20)
    while d <= dt.date(2026, 12, 10):
        days.append(d)
        d += dt.timedelta(days=1)
    js = json.dumps([f"{x.isoformat()}T17:00:00Z" for x in days])
    got = _app_js("%s.map(s => scope.sittingTerm(new Date(s)))" % js, names=("sittingTerm",))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here (the Python rule was held)"
    for x, g in zip(days, got):
        assert g == P.term_on(x.isoformat()), (
            f"app.js sittingTerm says {g} on {x}, the build's rule says {P.term_on(x.isoformat())}")
    return "ok", "1 December 2026 is still 2025-2026 everywhere, Organization Day opens 2027-2028"


@check("build", "the term rules, the escapes and the sitting roster's name keys each have one home, and a "
       "copy of one is a failure")
def _shared_helpers_one_home():
    """The foundation survey of November 2026 found term_of written twelve times and esc six. The term
    rules are src/lib/terms.py (by year: term_of_year) and proceedings.term_on (by date, Organization
    Day the next term's); the exact escape is src/lib/htmlesc.py. A definition of term_of, term_of_year,
    esc or _home_esc outside src/lib, or the by-year arithmetic written out into a term string again,
    fails and names the file (ALLOWED says why each other one is a different rule). Then the rules are
    held to each other over 1985-2030, and a name two sitting members share is left out of the
    roster's keys (bug hunt #10) and fails on data/legislators.json."""
    import ast
    import datetime as dt
    import proceedings as P
    import terms as T
    import htmlesc as HE
    import build_site_v2 as B
    ALLOWED = {
        "src/parse/unh_extract.py": "knows a month without a day, said in its docstring",
        "src/parse/rsa.py": "the quoted term of an RSA, not a term of years",
        "src/parse/score_members_elect.py": "a ballot's day, through proceedings.vote_term",
        "src/parse/officers.py": "a day, through proceedings.vote_term",
        "src/pages/legislative_year.py": "a date, through proceedings.term_on",
        "nightly.py": "the workflow-command escape, not HTML",
        "src/pages/components.py": "esc is a one-line call of htmlesc.esc, named for the parity check",
    }
    # these read the odd year as a number, never as a term string
    START_YEAR = {"src/parse/member_links.py", "src/parse/narrative.py"}
    names = {"term_of", "term_of_year", "esc", "_home_esc"}
    odd = re.compile(r"\b(\w+) if \1 % 2 else \1 - 1\b")
    stray = []
    for f in sorted(list(Path("src").rglob("*.py")) + [Path("nightly.py")]):
        posix = f.as_posix()
        # The suite's own modules write the rules out as the samples they hold
        # the code to (they were in preflight.py, outside src/, until 16
        # November 2026): a check is not a second home.
        if f.parent.as_posix() == "src/lib" or _in_suite(f):
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        if posix not in ALLOWED:
            for node in ast.walk(_parsed(f)):
                if isinstance(node, ast.FunctionDef) and node.name in names:
                    stray.append(f"{posix}:{node.lineno} defines {node.name}")
            lines = txt.splitlines()
            for i, line in enumerate(lines):
                if odd.search(line) and posix not in START_YEAR \
                        and re.search(r'\+ 1\}"|\}-\{', " ".join(lines[i:i + 3])):
                    stray.append(f"{posix}:{i + 1} writes the by-year term rule out again")
    assert not stray, ("a helper that has one home was written again: " + "; ".join(stray)
                       + ". Import terms.term_of_year or htmlesc.esc (src/lib/terms.py says which rule is which).")
    for y in range(1985, 2031):
        assert T.term_of_year(y) == T.term_of_year(str(y)) == P.term_of(f"{y}-06-15") == P.term_on(f"{y}-06-15")
        assert P.term_on(f"{y}-01-01") == T.term_of_year(y)
        if y % 2 == 0:
            org = P.organization_day(y)
            assert P.term_on((org - dt.timedelta(days=1)).isoformat()) == T.term_of_year(y)
            assert P.term_on(org.isoformat()) == T.term_of_year(y + 1)
    assert HE.esc(None) == "" and HE.esc(0) == "0" and HE.esc_blank(0) == "" \
        and HE.esc("a&b<c>\"'") == "a&amp;b&lt;c&gt;&quot;'"
    ms = [{"id": "1", "name": "Smith, John"}, {"id": "2", "name": "Jones, Ann"},
          {"id": "3", "name": "Smith, John"}]
    a, b, clash = B.roster_name_keys(ms)
    assert "smith, john" not in a and ("john", "smith") not in b and "jones, ann" in a \
        and len(clash) == 2, "a name two members share must not go to the first of them"
    f = Path("data/legislators.json")
    if not f.exists():
        return "ok", "one home each for the term rules and the escapes; the roster keys held on a pair (no data/legislators.json here)"
    legs = json.loads(f.read_text(encoding="utf-8"))
    legs = list(legs.values()) if isinstance(legs, dict) else legs
    _, _, clash = B.roster_name_keys(legs)
    # A namesake in the official roster is a source quirk: it warns, naming both
    # members, and never fails (the build leaves the sponsor unlinked and says so).
    shared = "; ".join(f"{h} {k!r}: " + " and ".join(f"{m.get('name')} ({m.get('id')})" for m in ms)
                       for h, k, ms in clash)
    if clash:
        print(f"  WARNING: two sitting members share a name key, so a sponsor named by it alone "
              f"is left unlinked: {shared}")
        return "ok", f"WARNING: {len(clash)} name key(s) shared by sitting members, left unlinked: {shared}"
    return "ok", f"one home each for the term rules and the escapes; {len(legs)} sitting members, no name key shared"


@check("build", "a term's key is made, read and printed by terms.py from the state's settings, as the code "
       "wrote every key and label before; nothing of its shape that is no term is taken for one; every key "
       "sorts in time order as text; and the build's term is read in one place")
def _term_keys_from_settings():
    """THE KEY (src/lib/terms.py, 16 November 2026, the refactor's build design, step S1). A term's
    key and label are the state's settings ("key" and "label" under "term" in state_settings.json),
    and terms.py makes, reads and validates one. With New Hampshire's settings every answer is the
    one the code gave before, so no key, address or file name moves: term_of_year against the
    old arithmetic for every year 1001-3000, by number and by text; key_on against
    proceedings.term_on for every day of 1985-2030; label against components.term_words for keys
    and for what is not one. is_key takes a key and nothing else of its shape -- an LSR number
    (2027-0001), a pair that begins in an even year or spans three, one padded, spaced or
    dashed -- and years() refuses the same. THE RULE the code's sorts rely on: the keys of every
    term from 1001 to 9997, sorted as text, are in time order. And THE BUILD'S TERM: GRANITE_TERM
    is named in terms.py alone, and GRANITE_COLD in build_cache.py alone, as GRANITE_BUILD_DATE
    is in build_date.py; sitting() takes a stated term, stops on one that is no term, and
    otherwise reads the installed files once a process."""
    import datetime as dt
    import components as C
    import proceedings as P
    import state_settings as ST
    import terms as T
    assert set(ST.TERM) >= {"key", "label"} and "{first}" in T.KEY and "{last}" in T.KEY, \
        f"the state's settings give a term no key shape: {ST.TERM}"
    for y in range(1001, 3001):
        s = y if y % 2 else y - 1
        assert T.term_of_year(y) == T.term_of_year(str(y)) == T.key_of_year(y) == f"{s}-{s + 1}", \
            f"terms.term_of_year({y}) is {T.term_of_year(y)!r}, and the code wrote {s}-{s + 1}"
        assert T.years(f"{s}-{s + 1}") == (s, s + 1) and T.is_key(f"{s}-{s + 1}")
    day = dt.date(1985, 1, 1)
    while day <= dt.date(2030, 12, 31):
        assert T.key_on(day.isoformat()) == P.term_on(day.isoformat()), day
        day += dt.timedelta(days=1)
    assert T.key_on("2026-12-01") == "2025-2026" and T.key_on("2026-12-02") == "2027-2028"
    for s in ("2025-2026", "1989-1990", "2027-requests", "", None, 2025, "1989-1998", "2000-2001",
              "123-456", "2025-2026 ", "x2025-2026", "2025–2026"):
        assert T.label(s) == C.term_words(s), (
            f"terms.label({s!r}) is {T.label(s)!r} and components.term_words writes {C.term_words(s)!r}")
    assert T.label("2025-2026") == "2025–2026"
    for s in ("2027-0001", "2026-2027", "2025-2027", "02025-2026", " 2025-2026", "2025-2026 ",
              "2025–2026", "2025_2026", "2027-requests", "2025", "", None, 2025, ["2025-2026"]):
        assert not T.is_key(s), f"terms.is_key({s!r}) takes it for a term"
        try:
            T.years(s)
            raise AssertionError(f"terms.years({s!r}) answered for what is not a term")
        except ValueError:
            pass
    assert T.next_key("2025-2026") == "2027-2028" and T.previous_key("2025-2026") == "2023-2024"
    keys = [T.key(f) for f in range(1001, 9998, 2)]
    assert sorted(keys) == keys and len(set(keys)) == len(keys), \
        "the state's term keys do not sort in time order as text: about a hundred sorts rely on it"

    # ONE READER for each of the build's words to its steps: the name, as a
    # string the code could read the environment by, in its own module only
    # (a sentence that mentions it is no read).
    import ast
    own = {"GRANITE_TERM": "terms.py", "GRANITE_COLD": "build_cache.py"}
    assert (T.ENV, imp("build_cache").COLD) == tuple(own), (T.ENV, imp("build_cache").COLD)
    stray = [f"{p.relative_to(_paths.ROOT).as_posix()}:{n.lineno} names {n.value}"
             for p in _paths.code_files("*.py") if not _in_suite(p)
             for n in ast.walk(_parsed(p))
             if isinstance(n, ast.Constant) and n.value in own and p.name != own[n.value]]
    assert not stray, ("the build's term and its cold word are each read in one place (terms.py, "
                       "build_cache.py), and other code names them: " + "; ".join(stray))

    here, saved = os.getcwd(), os.environ.get(T.ENV)
    tmp = Path(tempfile.mkdtemp(prefix="gr-term-keys-"))
    asked = []
    real = T.decide
    try:
        os.chdir(tmp)
        os.environ.pop(T.ENV, None)
        T._decided.cache_clear()
        Path("Docket.txt").write_text("2025|0001|1/5/2025 10:00:00 AM|HB1|H|Introduced|x\n"
                                      "2026|0002|1/6/2026 10:00:00 AM|HB1001|H|Introduced|x\n",
                                      encoding="utf-8")
        T.decide = lambda folder=".": (asked.append(folder), real(folder))[1]
        assert T.sitting() == T.sitting() == "2025-2026" == P.session_term(".") and len(asked) == 1, (
            f"sitting() read {T.sitting()!r} off the installed files, asking {len(asked)} times")
        os.environ[T.ENV] = "2027-2028"
        assert T.sitting() == "2027-2028", "a term the build handed down is not the step's term"
        for bad in ("2027", "2027-0001", "next term"):
            os.environ[T.ENV] = bad
            try:
                T.sitting()
                raise AssertionError(f"{T.ENV}={bad!r} was taken for a term")
            except SystemExit as e:
                assert T.ENV in str(e), str(e)
    finally:
        T.decide = real
        T._decided.cache_clear()
        if saved is None:
            os.environ.pop(T.ENV, None)
        else:
            os.environ[T.ENV] = saved
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("term_of_year as the code wrote it for 2,000 years, key_on as term_on for every day "
                  "of 1985-2030, label as term_words; no LSR number or other shape taken for a term; "
                  f"{len(keys):,} keys in time order as text; GRANITE_TERM and GRANITE_COLD each named in "
                  "one module; sitting() takes a stated term, stops on one that is no term, and reads "
                  "the files once")


@check("code", "the tag engine: tiers, exclusions, the topic-redundancy drop, determinism, the opposite-aim pairs "
               "and the bench kind, on a small fixture registry",
       needs=("tag_rules", "tag_counts", "review"))
def _tag_engine(TR, TC, RV):
    """src/parse/tag_rules.py (stage 1 of reports/topics-as-tags-design-2026-11.md), on
    tests/tags_fixture.json. Nothing here reads corrections/tags.json: the check is of the
    engine, and a clone without that file must pass it.

    Held: the registry's own form (validate); a phrase is a whole word, so "environmental
    health" is no "mental health"; a title attaches alone, an analysis only at two mentions or
    once where it is short, a dedicated chapter only when the bill amends three at most; an
    exclusion blanks the phrase and leaves the rest of the text; a tag equal to the bill's topic
    is dropped and said to be; both bills of every neutrality pair attach; the same answer under
    two PYTHONHASHSEEDs; a bill over five tags is counted; and the bench's tag kind draws,
    shows and reports without writing a judgment of its own."""
    import inspect
    fx = json.loads(_source("tests/tags_fixture.json"))
    reg = fx["registry"]
    bad = TR.validate(reg)
    assert not bad, "the fixture registry is not well formed: " + "; ".join(bad)
    rules = TR.compile_registry(reg)
    assert len(rules) == len(reg), "a registry entry compiled to no rule"
    bills = {f"{b['term']}/{b['bill']}": b for b in fx["bills"]}
    for key, want in fx["expect"].items():
        got = list(TR.tag_bill(rules, bills[key])["tags"])
        assert got == want, f"{key}: tags {got}, expected {want}"
    one = lambda k, tid: TR.tag_bill(rules, bills[k])["tags"][tid]
    assert one("2001-2002/HB11", "mental-health")["tier"] == "T", "a title phrase is not the T tier"
    assert one("2001-2002/HB12", "mental-health")["tier"] == "A", "two mentions in an analysis are not the A tier"
    assert one("2001-2002/HB15", "mental-health")["tier"] == "R", "a dedicated chapter alone is not the R tier"
    assert one("2013-2014/HB25", "medicaid-assistance")["tier"] == "R", "a chapter with its word is not the R tier"
    assert one("2001-2002/HB11", "mental-health")["why"] == "T:mental health", "the evidence is not the phrase"
    assert len(bills["2001-2002/HB13"]["analysis"]) > 500 and len(bills["2001-2002/HB14"]["analysis"]) < 500, (
        "the fixture's two analyses no longer straddle the 500-character line")
    # the topic-redundancy drop is said, not silent
    r = TR.tag_bill(rules, bills["2013-2014/HB22"])
    assert not r["tags"] and "medicaid-assistance" in r["dropped"], "a tag equal to the bill's topic was attached"
    r = TR.tag_bill(rules, bills["2019-2020/HB6"])
    assert not r["tags"] and "policing" in r["dropped"], "the Police topic did not drop the policing tag"
    # a Study Committees bill takes the tags of what the committee studies: the redundancy
    # drop is for a topic that IS the subject, and Study Committees is none
    st = TR.tag_bill(rules, bills["2023-2024/HB40"])
    assert "mental-health" in st["tags"] and not st["dropped"], "a Study Committees bill lost its subject's tag"
    assert not any("study" in t.lower() for e in reg.values() for t in e.get("same_as_topic", [])), (
        "a tag is dropped for the Study Committees topic")
    # whole words, a plural, a prefix, case, a chapter family
    cp = TR.compile_phrase
    assert not cp("mental health").search("children's environmental health day"), "environmental health matched"
    assert cp("mental health").search("Mental-Health services"), "a hyphen and a capital broke a phrase"
    assert cp("vaccin*").search("vaccination") and not cp("vaccin").search("vaccination"), "the open end is wrong"
    assert cp("=AI").search("regulating AI.") and not cp("=AI").search("ai") and not cp("=AI").search("AIR"), (
        "a case-sensitive phrase is wrong")
    assert cp("workers' compensation").search("workers compensation"), "an optional apostrophe is not optional"
    assert TR.chapter_matches("159*", "159-D") and TR.chapter_matches("159*", "159") and not TR.chapter_matches(
        "159*", "1591"), "a chapter family matches wrongly"
    # a form that argues, an unsupported pair, a phrase that does not compile
    worse = {"x": {**reg["mental-health"], "name": "Gun reform"},
             "y": {**reg["cannabis"], "pair": None},
             "z": {**reg["mental-health"], "rule": {"title": ["re:("]}}}
    found = " | ".join(TR.validate(worse))
    assert "reform" in found and "no opposite-aim pair" in found and "does not compile" in found, found
    allowed = TR.validate({"x": {**reg["mental-health"], "name": "Civil rights", "stance_ok": ["rights"]}})
    assert not allowed, f"stance_ok did not allow a word: {allowed}"
    # the synonym table: every word leads somewhere, and none leads to two places
    syn = fx["synonyms"]
    topics = TR.known_topics("tests/no-such-root")
    assert "Discrimination" in topics and "Study Committees and Commissions" in topics, "the site's topics are not known"
    assert not TR.validate(reg, topics, syn), "the fixture's synonyms do not all lead somewhere: " + "; ".join(
        TR.validate(reg, topics, syn))
    table, conflicts = TR.synonym_table(reg, syn)
    assert not conflicts and table["weed"] == "tag:cannabis" and table["marijuana legalization"] == "tag:cannabis" \
        and table["absentee ballot"] == "topic:Elections" and table["mental health"] == "tag:mental-health", table
    worse_syn = TR.validate(reg, topics, {"x": "tag:no-such-tag", "y": "topic:No Such Topic", "z": "nowhere",
                                          "weed": "tag:mental-health"})
    found = " | ".join(worse_syn)
    assert "no-such-tag" in found and "No Such Topic" in found and "leads nowhere" in found and "'weed' leads to" in found, found
    assert any("same_as_topic" in x for x in TR.validate(
        {"p": {**reg["policing"], "same_as_topic": ["Workers' Comp and Unemployment"]}}, topics)), (
        "a same_as_topic that is no topic of the site was not found")
    # both bills of every pair attach
    pairs = 0
    for tid, e in reg.items():
        for k in e.get("pair") or []:
            assert tid in TR.tag_bill(rules, bills[k])["tags"], f"{tid}: {k} of its opposite-aim pair does not attach"
            pairs += 1
    assert pairs >= 4, "the fixture has no pairs to test"
    # determinism: two hash seeds, one answer
    prog = ("import sys, json; sys.path.insert(0, '.'); import _paths, tag_rules as T; "
            "fx = json.load(open('tests/tags_fixture.json', encoding='utf-8')); "
            "rules = T.compile_registry(fx['registry']); "
            "print(json.dumps({'%s/%s' % (b['term'], b['bill']): T.tag_bill(rules, b) for b in fx['bills']}, sort_keys=False))")
    outs = []
    for seed in ("1", "977"):
        p = _run([sys.executable, "-c", prog], env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True)
        assert p.returncode == 0, p.stderr[-400:]
        outs.append(p.stdout)
    assert outs[0] == outs[1] and outs[0], "the engine's answer depends on the hash seed"
    # a bill over five tags is counted, not capped
    results, c = TC.count(rules, list(bills.values()), reg)
    assert c["bills_over_guide"] == 1 and c["over_guide_examples"][0]["bill"] == "2019-2020/HB5", (
        f"the bill over five tags was not counted: {c['over_guide_examples']}")
    assert len(results["2019-2020/HB5"]["tags"]) == 6, "a bill's tags were capped"
    assert c["bills_title_tier"] <= c["bills_any_tier"] <= c["bills"], "the counts do not nest"
    # the bench: a draw, a page and a report, and not one judgment of its own
    texts = {"2001-2002": {"HB10": "mental health. The mental health of the mental health system. Other words."}}
    samples, ncand = TC.draw(reg, rules, list(bills.values()), results, texts)
    mh = samples["mental-health"]
    assert [x["bill"] for x in mh["title"]] == ["HB11", "HB40"], "the title sample is not the title-tier bills"
    assert {x["bill"] for x in mh["other"]} == {"HB12", "HB14", "HB15"}, "the analysis/chapter sample is wrong"
    assert [x["bill"] for x in mh["miss"]] == ["HB10"] and mh["miss"][0]["sentences"], (
        "a bill whose text names the subject three times was not offered as a possible miss")
    assert len(samples["cannabis"]["pair"]) == 2 and all(x["attached"] for x in samples["cannabis"]["pair"]), (
        "the pair was not drawn attached")
    assert samples == TC.draw(reg, rules, list(bills.values()), results, texts)[0], "the draw is not deterministic"
    assert "tag" in RV.KINDS and set(RV.KINDS["tag"]) >= {"label", "blurb", "sample", "show", "fields", "verdicts"}
    base = {"kind": "tag", "tag": "mental-health", "order": 0, "tag_name": "Mental health", "definition": "d.",
            "hard": False}
    shown = [{**base, **mh["title"][0], "sample": "title"}, {**base, **mh["miss"][0], "sample": "miss"},
             {**base, "sample": "pair", "a": samples["cannabis"]["pair"][0], "b": samples["cannabis"]["pair"][1]}]
    for it in shown:
        page = RV.show_tags(it)
        assert "Mental health" in page and "<script" not in page, "the tag page did not draw"
    assert RV.form_html("tag", {**shown[0], "key": "tag|mental-health|title|2001-2002/HB11"}), "no form"
    saved_load = TR.load_registry
    TR.load_registry = lambda path=None: (reg, "fixture")
    try:
        assert RV.sample_tags() == [], "the bench drew samples from the fixture registry"
    finally:
        TR.load_registry = saved_load
    for fn in (RV.sample_tags, RV.show_tags, TC.draw, TC.count, TR.tag_bill, TR.load_bills):
        src = inspect.getsource(fn)
        assert "record(" not in src and "checked.jsonl" not in src and ".write_text" not in src and "open(" not in src, (
            f"{fn.__name__} writes something: a bench sample may only be drawn, never judged by a machine")
    import io
    from contextlib import redirect_stdout
    seen = {("tag", f"tag|mental-health|title|2001-2002/HB{i}"): [{"verdict": "yes", "shown": {"hard": False}}]
            for i in range(10)}
    out = io.StringIO()
    with redirect_stdout(out):
        RV.tag_report(seen)
    assert "mental-health" in out.getvalue() and "title 10/10" in out.getvalue(), out.getvalue()
    return "ok", (f"{len(fx['expect'])} bills, {len(reg)} tags, {pairs} pair bills; two hash seeds agree; "
                  f"the bench draws, shows and reports")


@check("code", "a bench judgment no phrase can reach is honoured by hand: a hand list attaches its bills as tier H "
               "with the reason and takes others off and says so, the topic drop still holds, a malformed list is "
               "refused, and the bench never draws a hand bill to ask again",
       needs=("tag_rules", "tag_counts"))
def _tag_hand_lists(TR, TC):
    """The owner's bench of 15 November 2026 judged three possible misses of the mental-health tag
    "partly"; two of them (2019-2020 SB290, 2021-2022 SB140) name the subject only in their text,
    which never attaches a tag, so tag_rules.py takes an entry's "hand" list: {"attach": {bill: why},
    "detach": {bill: why}}. Held on tests/tags_fixture.json, a copy given hand lists: a bill no
    phrase reaches attaches as H with "H:" and the reason; a bill a phrase reaches keeps the phrase's
    tier first and lists H after it; a bill taken off loses the tag whatever fires, and dropped says
    so; a hand attach on a bill whose topic is the tag's own is still dropped for the topic; no other
    tag's answer moves; validate() refuses a key that is no bill, a reason left empty, a bill on both
    lists and a list of another shape; the counts carry an H column; and the bench's draw leaves the
    hand bill out of the sample it asks about."""
    fx = json.loads(_source("tests/tags_fixture.json"))
    reg = json.loads(json.dumps(fx["registry"]))
    bills = {f"{b['term']}/{b['bill']}": b for b in fx["bills"]}
    plain = TR.compile_registry(reg)
    before = {k: TR.tag_bill(plain, b) for k, b in bills.items()}
    assert "mental-health" not in before["2001-2002/HB13"]["tags"], "the fixture's HB13 already carries the tag"
    reg["mental-health"]["hand"] = {"attach": {"2001-2002/HB13": "the bench: partly", "2001-2002/HB11": "the bench: yes"},
                                    "detach": {"2001-2002/HB12": "the bench: no"}}
    reg["medicaid-assistance"]["hand"] = {"attach": {"2013-2014/HB22": "the bench: yes"}}
    assert not TR.validate(reg), "a well-formed hand list was refused: " + "; ".join(TR.validate(reg))
    rules = TR.compile_registry(reg)
    after = {k: TR.tag_bill(rules, b) for k, b in bills.items()}
    got = after["2001-2002/HB13"]["tags"].get("mental-health")
    assert got == {"tier": "H", "why": "H:the bench: partly", "fired": ["H"]}, f"a hand bill no phrase reaches: {got}"
    got = after["2001-2002/HB11"]["tags"]["mental-health"]
    assert got["tier"] == "T" and got["fired"] == ["T", "H"], f"a phrase's tier did not come first: {got}"
    assert "mental-health" not in after["2001-2002/HB12"]["tags"] and \
        after["2001-2002/HB12"]["dropped"].get("mental-health") == "taken off by hand: the bench: no", (
        f"a bill taken off by hand: {after['2001-2002/HB12']}")
    assert "medicaid-assistance" not in after["2013-2014/HB22"]["tags"] and \
        "medicaid-assistance" in after["2013-2014/HB22"]["dropped"], "a hand attach escaped the topic drop"
    for k in bills:
        for tid in reg:
            if tid in ("mental-health", "medicaid-assistance") and k in ("2001-2002/HB11", "2001-2002/HB12",
                                                                         "2001-2002/HB13", "2013-2014/HB22"):
                continue
            assert after[k]["tags"].get(tid) == before[k]["tags"].get(tid), f"{k} {tid} moved without a hand list"
    found = " | ".join(TR.validate({"x": {**reg["mental-health"], "hand": {
        "attach": {"HB13": "why", "2001-2002/HB14": " ", "2001-2002/HB15": "why"},
        "detach": {"2001-2002/HB15": "why"}}}, "y": {**reg["mental-health"], "hand": ["2001-2002/HB13"]}}))
    assert "no bill key" in found and "says no reason" in found and "both attaches and takes off" in found \
        and "y: hand is" in found, found
    results, c = TC.count(rules, list(bills.values()), reg)
    assert c["by_tag"]["mental-health"]["best"]["H"] == 1 and "| H |" in TC.markdown(c, "fixture"), (
        "the counts have no hand column")
    samples, _n = TC.draw(reg, rules, list(bills.values()), results, {})
    asked = {x["bill"] for s in ("title", "other") for x in samples["mental-health"][s]}
    assert "HB13" not in asked and "HB11" in asked, f"the bench would ask again about a hand bill: {sorted(asked)}"
    return "ok", ("a hand bill attaches as H with its reason and a phrase's tier comes first; a bill taken off "
                  "loses the tag and is said to be; the topic drop holds; no other answer moves; four malformed "
                  "lists refused; the counts' H column; the bench never draws a hand bill")


@check("code", "a tag phrase's last word ending in a consonant and y matches its -ies plural, one ending so in -ies its "
               "-y singular, and every form it matched before; a vowel's y, the words series and species, the other "
               "words of a phrase, an open end and a regular expression are as they were",
       needs=("tag_rules",))
def _tag_plural_y(TR):
    """tag_rules.compile_phrase gave a phrase's last word "-s" or "-es" and never turned "y" into "ies", so
    "jury" missed "juries" and "public utility" "public utilities" (the polish of 15 November 2026 found it;
    the owner queued the fix for this release). Held: each pair matches as it should, each non-pair does not,
    and on a list of words every text a phrase matched under the old rule (rebuilt here as it was) it matches
    still, so the change only adds."""
    cp = TR.compile_phrase
    hits = [("public utility", "regulating public utilities"), ("jury", "juries"), ("juries", "jury"),
            ("pharmacies", "the pharmacy"), ("brain injury", "brain-injuries"), ("=AGENCY", "AGENCIES"),
            ("university", "universities"), ("water supply", "water supplies"), ("public body", "public bodies"),
            ("sky", "skies"), ("delinquency", "delinquencies"), ("county", "counties"), ("day", "days"),
            ("attorney", "attorneys"), ("public utility", "public utilitys")]
    misses = [("day", "daies"), ("attorney", "attornies"), ("alien species", "alien specy"), ("series", "sery"),
              ("=AGENCY", "agencies"), ("county commission", "counties commission"), ("by", "bies"),
              ("lies", "ly"), ("mental health", "environmental health"), ("money", "monies")]
    wrong = [f"{p!r} should find {t!r}" for p, t in hits if not cp(p).search(t)]
    wrong += [f"{p!r} should not find {t!r}" for p, t in misses if cp(p).search(t)]
    assert not wrong, "; ".join(wrong)
    assert cp("re:juries").search("juries") and not cp("re:jury").search("juries"), "a regular expression was changed"

    def old(p):
        """The phrase as the engine compiled it until 16 November 2026."""
        flags = re.I
        if p.startswith("="):
            p, flags = p[1:], 0
        open_end = p.endswith("*")
        p = p[:-1] if open_end else p
        body = (TR._HY + "+").join((TR._AP + "?").join(re.escape(x) for x in tok.split("'"))
                                   for tok in re.split(r"[\s\-]+", p.strip()))
        return re.compile(TR._LEFT + body + ("" if open_end else "(?:s|es)?" + TR._RIGHT), flags)
    phrases = ["public utility", "jury", "juries", "day", "series", "species", "vaccin*", "=AGENCY", "workers' compensation",
               "county", "mental health", "e-verify", "ies", "y"]
    texts = ["public utility", "public utilitys", "public utilityes", "jury", "jurys", "juries", "juriess", "day", "days",
             "dayes", "series", "species", "vaccine", "vaccination", "AGENCY", "AGENCYS", "agency", "workers compensation",
             "workers' compensations", "county", "countys", "mental health", "mental-health", "e-verify", "everify",
             "e verify", "ies", "iess", "y", "ys", "yes"]
    lost = [f"{p!r} no longer finds {t!r}" for p in phrases for t in texts if old(p).search(t) and not cp(p).search(t)]
    assert not lost, "; ".join(lost)
    for p in ("utilit*", "nursing facilit*", "county commission", "=TANF", "ballot access", "adult day"):
        assert cp(p).pattern == old(p).pattern, f"{p!r} changed, but its last word is open, no -y word or none"
    return "ok", (f"{len(hits)} plural pairs found, {len(misses)} non-pairs not; a regular expression as written; "
                  f"{len(phrases)} phrases over {len(texts)} texts find everything they found before")


@check("code", "a tag can rest on the provision of law a bill writes -- the heading of a new chapter of the RSA or "
               "of an article of the constitution -- and never on a title's words alone",
       needs=("tag_rules",))
def _tag_provisions(TR):
    """tag_rules.provisions (17 November 2026; the owner: a state income tax tag "only for bills that change
    that particular provision of law -- whether adding an income tax or banning one", by "the statute chapter
    or the Constitution article such bills amend", "never by title words alone"). On the real wording of
    2007-2008 HB 1373 (CHAPTER 76-A INCOME TAX), 2005-2006 CACR 13 (Part II, [Art.] 5-c [Income Tax
    Prohibited.]) and 1997-1998 HB 1668, whose first new chapter 76-A is a school property tax and whose
    second, 76-B, the personal income tax: a chapter's heading is read up to its own first section, the
    Part is the one the text names, a section 76-A:10 is no first section, a text that only amends an
    existing chapter writes nothing; a rule of provisions alone is well formed and attaches as R by the
    heading, and the same title and analysis with no such provision attach nothing."""
    hb1373 = ("AN ACT establishing an income tax. Be it Enacted by the Senate and House of Representatives in General "
              "Court convened: 1 New Chapter; Income. Amend RSA by inserting after chapter 76 the following new "
              "chapters: CHAPTER 76-A INCOME TAX 76-A:1 Definitions. In this chapter: I. \"Consumer price index\" "
              "means the consumer price index. 76-A:10 Rate.")
    cacr13 = ("that the Constitution of New Hampshire be amended as follows: I. That the second part of the "
              "constitution be amended by inserting after article 5-B the following new article: [Art.] 5-c "
              "[Income Tax Prohibited.] No tax shall be levied, directly or indirectly, upon a person's income")
    hb1668 = ("2 New Chapters; Proportional Statewide School Property Tax; Personal Income Tax. Amend RSA by "
              "inserting after chapter 76 the following new chapters: CHAPTER 76-A PROPORTIONAL STATEWIDE SCHOOL "
              "PROPERTY TAX 76-A:1 Definitions. I. \"Assessing official\" means x. CHAPTER 76-B PERSONAL INCOME TAX "
              "76-B:1 Definitions.")
    assert TR.provisions(hb1373) == ["RSA 76-A Income Tax"], TR.provisions(hb1373)
    assert TR.provisions(cacr13) == ["Part II, Art. 5-c Income Tax Prohibited"], TR.provisions(cacr13)
    assert TR.provisions(hb1668) == ["RSA 76-A Proportional Statewide School Property Tax",
                                     "RSA 76-B Personal Income Tax"], TR.provisions(hb1668)
    assert TR.provisions("Amend RSA 77:4 to read as follows: 77:4 Taxation of Incomes.") == []
    assert TR.provisions("CHAPTER 76-A INCOME TAX 76-A:10 Rate.") == [], "a later section read as a chapter's first"
    reg = {"state-income-tax": {"name": "State income tax", "definition": "Bills that would establish or prohibit "
                                "a state tax on personal income.",
                                "rule": {"provisions": ["income tax", "personal income"]}}}
    assert not TR.validate(reg), TR.validate(reg)
    assert TR.validate({"x": {"name": "X", "definition": "Bills.", "rule": {"provisions": ["re:("]}}}), (
        "a provisions phrase that does not compile passed")
    rules = TR.compile_registry(reg)
    title = "establishing an income tax."
    got = {}
    for key, text in (("HB1373", hb1373), ("CACR13", cacr13), ("HB1668", hb1668)):
        b = {"term": "t", "bill": key, "title": title, "analysis": "This bill establishes an income tax.",
             "chapters": [], "provisions": TR.provisions(text)}
        got[key] = TR.tag_bill(rules, b)["tags"].get("state-income-tax", {}).get("why")
    assert got == {"HB1373": "R:RSA 76-A Income Tax", "CACR13": "R:Part II, Art. 5-c Income Tax Prohibited",
                   "HB1668": "R:RSA 76-B Personal Income Tax"}, got
    bare = {"term": "t", "bill": "HB9", "title": title, "analysis": "This bill establishes an income tax.",
            "chapters": [], "provisions": []}
    assert not TR.tag_bill(rules, bare)["tags"], "the title's words alone attached a provisions tag"
    assert not TR.tag_bill(rules, {**bare, "provisions": ["RSA 76-A Proportional Statewide School Property Tax"]})[
        "tags"], "a chapter that is no income tax attached"
    return "ok", ("a new chapter's heading, a constitution article's with its Part, nothing for an amended section; "
                  "a provisions rule attaches by the heading and never by the title's words")


@check("code", "an office's tag can rest on a duty or a power the bill gives the office -- \"the attorney general "
               "shall\", \"requiring the secretary of state to\" -- and never on a mention of it",
       needs=("tag_rules",))
def _tag_duties(TR):
    """tag_rules.duties (17 November 2026; the owner: tags "for the position like attorney general, secretary
    of state, governor, etc for positions that are referenced in the bill text like an obligation that the role
    must do"). On the real wording of bills' texts: the subject of a "shall" or a "may" back to its clause, an
    aside between commas and a designee set aside (2025-2026 SB 627's commissioner acts "with the approval of
    the governor and council", which gives the governor nothing); a "shall be" gives nothing ("shall be subject
    to", "may be removed", "shall be paid", "shall be the same") but "shall be responsible", nor an office after
    a preposition ("the commission after consultation with the attorney general may"); "and" read whole, in
    parts and from each joint; the drafters' "requiring the secretary of state to" and "is hereby authorized
    to"; load_bills carries them. A rule of duties alone is well formed and attaches as R when its phrase is
    the whole subject ("the deputy attorney general shall", never "the representatives of the governor shall");
    the same title and analysis with no duty attach nothing; a `not` phrase blanks every CACR's "the secretary
    of state shall print the question" and an appropriation's "the governor is authorized to draw a warrant"."""
    d = TR.duties
    assert d("Upon receipt of a properly completed election law complaint form, the attorney general may "
             "investigate the complaint") == ["the attorney general may investigate the complaint"], "2025-2026 HB 1462"
    sb627 = d("I. The commissioner of transportation, with the approval of the governor and council, shall establish "
              "toll rates")
    assert sb627 == ["the commissioner of transportation shall establish toll rates"], sb627
    assert d("657:30 Voter Notification and Education. I. The secretary of state shall notify all registered") == [
        "the secretary of state shall notify all registered"], "2025-2026 HB 1382"
    assert d("II. An intentional violation of this section in connection with a filing with the secretary of state "
             "shall be subject to a penalty") == [], "an office acted on, 2025-2026 HB 406"
    assert d("Any member appointed by the governor with the consent of the executive council may be removed from "
             "office") == [], "2025-2026 SB 302"
    assert d("Notwithstanding the provisions of RSA 181:15, the commission after consultation with the attorney "
             "general may in its discretion") == ["the commission may in its discretion"], "a preposition's object"
    hb639 = d("II. The governor, with the consent of the executive council, may appoint the first presiding judge")
    assert hb639 == ["the governor may appoint the first presiding"], hb639
    both = d("such terms and conditions as the authority and the governor and council may impose")
    assert {"the governor may impose", "council may impose", "authority and the governor and council may impose",
            "the governor and council may impose"} <= set(both), both
    assert d("Each member of the board shall be paid $50 a day") == [], "a shall be paid read as a duty"
    assert d("the qualifications of electors of the governor shall be the same as those") == [], (
        "a shall be the same read as a duty")
    assert d("III. The sheriff shall be responsible for the custody") == [
        "the sheriff shall be responsible for the"], "shall be responsible is a duty"
    assert d("AN ACT requiring the secretary of state to create and maintain a uniform") == [
        "the secretary of state shall"], "2025-2026 HB 1163's title"
    assert d("The attorney general is hereby authorized to hire an assistant attorney general") == [
        "the attorney general may hire an assistant attorney"], "is hereby authorized to"
    assert d("The commissioner or designee shall approve or disapprove of the") == [
        "the commissioner shall approve or disapprove of"], "a designee, 2025-2026"
    assert d("3 Effective Date. This act shall take effect May 1, 2026.") == ["this act shall take effect may 1"], (
        "the month of May read as a may")
    assert d("the attorney general's office") == [] and d("") == [], "a mention read as a duty"
    reg = {"office-attorney-general": {"name": "Attorney General", "definition": "Bills that give the attorney "
                                       "general a duty or a power.", "rule": {"duties": ["attorney general"]}},
           "office-secretary-of-state": {"name": "Secretary of State", "definition": "Bills that give the secretary "
                                         "of state a duty or a power.",
                                         "rule": {"duties": ["secretary of state"],
                                                  "not": ["shall print the question"]}},
           "office-governor": {"name": "Governor", "definition": "Bills that give the governor a duty or a power.",
                               "rule": {"duties": ["governor"], "not": ["may draw", "shall draw"]}}}
    assert not TR.validate(reg), TR.validate(reg)
    assert TR.validate({"x": {"name": "X", "definition": "Bills.", "rule": {"duties": ["re:("]}}}), (
        "a duties phrase that does not compile passed")
    rules = TR.compile_registry(reg)

    def tags(title, analysis, text):
        b = {"term": "t", "bill": "HB9", "title": title, "analysis": analysis, "chapters": [],
             "duties": d(f"{title}. {text}")}
        return {k: v["why"] for k, v in TR.tag_bill(rules, b)["tags"].items()}
    assert tags("relative to election law complaints.", "This bill involves the attorney general.",
                "Upon receipt of a complaint form, the attorney general may investigate the complaint") == {
        "office-attorney-general": "R:the attorney general may"}
    assert tags("relative to the attorney general.", "This bill names the attorney general and the secretary of "
                "state.", "The commission after consultation with the attorney general may act.") == {}, (
        "a mention attached an office")
    assert tags("relative to commissions.", "", "the representatives of the governor shall serve for the balance of "
                "their elected terms") == {}, "an office ending the subject, not being it, attached (2025-2026)"
    assert tags("relative to the deputy.", "", "The deputy attorney general shall act") == {
        "office-attorney-general": "R:the deputy attorney general shall"}
    assert tags("relative to the governor.", "", "the governor is authorized to draw a warrant for said sum") == {}, (
        "the appropriation's boilerplate gave the governor a tag")
    assert tags("relative to cannabis.", "", "V. That the secretary of state shall print the question to be "
                "submitted to the voters") == {}, "every CACR's boilerplate gave the secretary of state a tag"
    assert tags("requiring the secretary of state to create a uniform form.", "", "") == {
        "office-secretary-of-state": "R:the secretary of state shall"}
    root = Path(tempfile.mkdtemp())
    try:
        (root / "data").mkdir()
        (root / "data" / "bills.json").write_text(json.dumps({"2025-2026": {"HB1462": {
            "title": "relative to election law complaints."}}}), encoding="utf-8")
        (root / "bill_text.json").write_text(json.dumps({"2025-2026": {"HB1462": {
            "text": "1 New Section. Upon receipt of a properly completed election law complaint form, the attorney "
                    "general may investigate the complaint."}}}), encoding="utf-8")
        got = TR.load_bills(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert got and got[0].get("duties") == ["the attorney general may investigate the complaint"], got
    return "ok", ("a duty's subject read to its clause, asides, designees, objects and passives set aside, parts of "
                  "an \"and\", the drafters' \"requiring ... to\"; a duties rule attaches by the duty, never by a "
                  "mention, and load_bills carries them")


@check("code", "the site's tags are switched on by corrections/tags.json alone (never the fixture, never GRANITE_TAGS), "
               "each bill read by the engine as it stands and kept in the build's cache by its inputs, meta.json's "
               "list in the registry's own words; with no registry no record, index row or meta.json key changes",
       needs=("tag_rules", "build_site_v2", "build_bill_pages"))
def _tag_site_data(TR, B, BBP):
    """Topics as tags, stages 3 and 4, the data (17 November 2026; reports/topics-as-tags-design-2026-11.md
    sections 2.2 and 7.1), switched off until the owner approves the list. tag_rules.in_force reads
    corrections/tags.json under the folder the build runs in and nothing else: absent, or holding no tag, it
    answers None, whatever GRANITE_TAGS says and with the fixture beside it; a registry with a problem stops the
    build and names it. site_tags answers what tag_bill answers for each bill, from the cache on a second run
    and afresh once the registry moves. site_meta lists only the tags some bill carries, each by the registry's
    own name and definition and nothing else, and leads a word only to such a tag or to a topic of the site.
    build_site_v2 over the fixture with a registry puts the tags in the bill's record (id, name, evidence), its
    index row (places in meta.json's list) and meta.json; without one, the shared build of the fixture carries
    none of them, and site_tagging answers {}. The no-script record lists them last, as searches."""
    fx = json.loads(_source("tests/tags_fixture.json"))
    reg, syn = fx["registry"], fx["synonyms"]
    tmp = Path(tempfile.mkdtemp())
    try:
        # ---- in_force: corrections/tags.json under the build's folder, and only it.
        here = str(Path(".").resolve())
        prog = ("import sys; sys.path.insert(0, %r); import _paths, tag_rules as T; d = T.in_force(); "
                "print('NONE' if d is None else len(d['tags']))" % here)
        env = {**os.environ, "GRANITE_TAGS": str(Path("tests/tags_fixture.json").resolve())}
        said = []
        for what, doc in (("absent", None), ("empty", {"tags": {}, "synonyms": {}}),
                          ("in force", {"about": "x", "tags": reg, "synonyms": syn})):
            folder = tmp / what.replace(" ", "_")
            (folder / "corrections").mkdir(parents=True)
            if doc is not None:
                (folder / "corrections" / "tags.json").write_text(json.dumps(doc), encoding="utf-8")
            r = _run([sys.executable, "-c", prog], cwd=folder, capture_output=True, text=True, timeout=120, env=env)
            assert r.returncode == 0, f"in_force with the registry {what}: {(r.stderr or r.stdout)[-300:]}"
            said.append(r.stdout.strip().splitlines()[-1])
        assert said == ["NONE", "NONE", str(len(reg))], (
            f"in_force read absent / empty / in force as {said}: only corrections/tags.json, with a tag in it, "
            "puts tags on the pages -- never GRANITE_TAGS, never the fixture")
        bad_reg = tmp / "bad.json"
        bad_reg.write_text(json.dumps({"tags": {"Bad Id": {"name": "x", "definition": "x.", "rule": {"title": ["x"]}}}}),
                           encoding="utf-8")
        try:
            TR.in_force(bad_reg)
            raise AssertionError("a registry with a malformed id was put in force")
        except SystemExit as e:
            assert "Bad Id" in str(e), f"the build's refusal does not name the problem: {e}"

        # ---- site_tags: the engine's answer, kept by its inputs.
        reg_path = tmp / "reg.json"
        reg_path.write_text(json.dumps({"tags": reg, "synonyms": syn}), encoding="utf-8")
        doc = TR.in_force(reg_path)
        rules = TR.compile_registry(reg)
        rows = [(b["term"], b["bill"], b["title"], "", b.get("topic") or "") for b in fx["bills"]]
        want = {}
        for term, bid, title, text, topic in rows:
            got = TR.tag_bill(rules, TR.engine_bill(term, bid, title, text, topic))["tags"]
            if got:
                want[(term, bid)] = {t: v["why"] for t, v in got.items()}
        cache = tmp / "cache"
        cold = TR.site_tags(rows, doc, folder=cache)
        assert cold == want and list(cold) == list(want), "site_tags is not tag_bill's answer, bill by bill"
        assert len(want) >= 5, f"the fixture's titles attach only {len(want)} bills: the check proves little"
        real_tag = TR.tag_bill
        TR.tag_bill = lambda *a, **k: (_ for _ in ()).throw(AssertionError("worked out again"))
        try:
            warm = TR.site_tags(rows, doc, folder=cache)
            moved = dict(doc, digest="0" * 64)
            try:
                TR.site_tags(rows, moved, folder=cache)
                raise AssertionError("a registry that moved was answered from the cache")
            except AssertionError as e:
                assert "worked out again" in str(e), str(e)
        finally:
            TR.tag_bill = real_tag
        assert warm == cold, "the cache's answer is not the engine's"

        # ---- site_meta: the registry's words, the carried tags, words that lead somewhere real.
        topics = {"Public and Mental Health", "Elections"}
        meta = TR.site_meta(doc, cold, topics)
        carried = {t for v in cold.values() for t in v}
        assert [t["id"] for t in meta["tags"]] == [t for t in reg if t in carried], (
            "meta.json's tags are not the carried ones in the registry's order")
        for t in meta["tags"]:
            e = reg[t["id"]]
            assert t == {"id": t["id"], "name": e["name"], "group": e.get("group") or "",
                         "definition": e["definition"]}, f"{t['id']}: not the registry's own words, or more than them"
        assert all((to[4:] in carried) if to.startswith("tag:") else (to[6:] in topics)
                   for to in meta["tag_words"].values()), "a word leads to a tag no bill carries or to no topic"
        assert meta["tag_words"].get("absentee ballot") == "topic:Elections", "a synonym to a topic is lost"
        assert "absentee ballot" not in TR.site_meta(doc, cold, set())["tag_words"], (
            "a word leads to a topic the site does not have")
        assert TR.site_meta(doc, {}, topics) == {}, "meta.json gains keys where no bill carries a tag"
        assert B.site_tagging({}, {}, registry=tmp / "none.json") == {}, "no registry, and site_tagging answers"

        # ---- build_site_v2 over the fixture, with a registry and (shared) without.
        root = tmp / "with"
        _site_fixture(root)
        (root / "corrections").mkdir(exist_ok=True)
        (root / "corrections" / "tags.json").write_text(json.dumps({"tags": {
            "insurance-cover": {"name": "Insurance coverage", "definition": "Bills about insurance coverage.",
                                "rule": {"title": ["insurance coverage"]}},
            "school-materials": {"name": "School materials", "definition": "Bills about what schools use.",
                                 "rule": {"title": ["school materials"]}},
            "nothing": {"name": "Nothing", "definition": "Bills about nothing.", "rule": {"title": ["zzzz"]}}},
            "synonyms": {"school books": "tag:school-materials", "coverage": "topic:Insurance",
                         "lost": "topic:No Such Topic"}}), encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_site_v2.py"), "--data", "data", "--out", "site",
                  "--segments", "work"], cwd=root, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, "build_site_v2 with a registry: " + (r.stderr or r.stdout)[-400:]
        m = json.loads((root / "site" / "meta.json").read_text(encoding="utf-8"))
        assert [t["id"] for t in m.get("tags", [])] == ["insurance-cover", "school-materials"], (
            f"meta.json's tags: {m.get('tags')}")
        assert m.get("tag_words") == {"coverage": "topic:Insurance", "insurance coverage": "tag:insurance-cover",
                                      "school books": "tag:school-materials",
                                      "school materials": "tag:school-materials"}, f"tag_words: {m.get('tag_words')}"
        rows_ = {b["id"]: b for f in (root / "site" / "idx").glob("2*.json")
                 for b in json.loads(f.read_text(encoding="utf-8"))}
        assert rows_["HB1442"].get("tags") == [0] and rows_["SB434"].get("tags") == [1], (
            f"index rows: HB1442 {rows_['HB1442'].get('tags')}, SB434 {rows_['SB434'].get('tags')}")
        assert "tags" not in rows_["HR10"], "a bill no tag attaches to carries a tags field"
        rec = json.loads(next((root / "site" / "bills").rglob("HB1442.json")).read_text(encoding="utf-8"))
        assert rec.get("tags") == [{"id": "insurance-cover", "name": "Insurance coverage",
                                    "why": "T:insurance coverage"}], f"HB1442's record: {rec.get('tags')}"
        page = BBP.static_record(rows_["HB1442"], rec)
        assert ('<h2>Related searches</h2><ul><li><a href="/bills?term=all&amp;tag=insurance-cover">'
                'Insurance coverage</a></li></ul></div>') in page, "the no-script record does not list the tag last"
        assert "Related searches" not in BBP.static_record(rows_["HR10"], {}), "a bill with no tag lists searches"
        # Without: the run's one build of the fixture, which has no registry.
        plain = tmp / "without"
        plain.mkdir()
        r = _fixture_site_v2(plain)
        assert r.returncode == 0, "the fixture's build: " + (r.stderr or r.stdout)[-300:]
        m = json.loads((plain / "site" / "meta.json").read_text(encoding="utf-8"))
        assert "tags" not in m and "tag_words" not in m, "meta.json gains a tags key with no registry"
        held = [f.name for f in (plain / "site").rglob("*.json")
                if f.parent.name in ("idx",) or f.parent.parent.name == "bills"
                if '"tags"' in f.read_text(encoding="utf-8")]
        assert not held, f"with no registry these carry a tags field: {held}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"in force by corrections/tags.json alone; {len(want)} fixture bills tagged as the engine tags them, "
                  "warm from the cache and afresh once the registry moves; meta.json in the registry's words; the "
                  "fixture built with a registry carries the tags in record, row and meta.json, and without one none")


@check("code", "a bill shows at most ten tags, its best-matched: a person's word, then the title, the analysis, a "
               "provision, a chapter with a word, a chapter and a duty, kinds of evidence and the bill's own words "
               "breaking a tie; site_tags applies it, so the record, the index row and meta.json agree",
       needs=("tag_rules",))
def _tag_cap(TR):
    """THE CAP in tag_rules.py (the owner, 17 November 2026: "cap the number of total tags that a bill can have
    since 17 seems a bit excessive so maybe something like 10 that are the best matches"). A made-up bill the
    rules give twelve tags, each on different evidence, in a registry whose order is neither the answer's nor
    the alphabet's: ranked puts them in the order of THE CAP (a hand list's word; then a title, the one more
    kinds of evidence attach first and then the one whose words the bill says more often; an analysis, two
    alike in the registry's order; a provision; a chapter with a word; a chapter; a duty, the one the bill
    names more often first, by its words in the analysis and by the duties its text gives the office), and
    site_tags keeps the ten best, in the registry's order, leaving off two duties -- one of them the
    registry's first tag. A bill of fewer tags keeps all of them, and a tag left off one bill stays in
    meta.json's list where another bill carries it. The setting is ten, in one place (MAX_TAGS)."""
    assert TR.MAX_TAGS == 10, f"the cap is {TR.MAX_TAGS}, not the owner's ten"
    key = "2025-2026/HB9999"
    reg = {}
    for tid, rule in (
            ("office-ag", {"duties": ["attorney general"]}),
            ("zoning-chapter", {"chapters_alone": ["996"]}),
            ("toys", {"analysis": ["gadget"]}),
            ("office-sos", {"duties": ["secretary of state"], "title": ["secretary of state"]}),
            ("widget", {"title": ["widget"]}),
            ("sprocket", {"provisions": ["sprocket"]}),
            ("gizmo", {"analysis": ["gizmo"]}),
            ("permits", {"title": ["permit fee"], "chapters_with_words": {"chapters": ["997"], "words": ["permit"]}}),
            ("inspection", {"title": ["inspection"]}),
            ("labor-commissioner", {"duties": ["commissioner of labor"]}),
            ("licensing", {"title": ["licensing"], "analysis": ["licensing"], "chapters_alone": ["998-A"]}),
            ("bench-only", {"title": ["zzqx"]})):
        reg[tid] = {"name": tid.replace("-", " ").title(), "definition": f"Bills about {tid}.", "rule": rule}
    reg["bench-only"]["hand"] = {"attach": {key: "the bench: yes"}}
    assert not TR.validate(reg), TR.validate(reg)
    bill = {"term": "2025-2026", "bill": "HB9999", "topic": "",
            "title": "relative to widget inspection and licensing",
            "analysis": ("This bill requires a permit for each gadget and gizmo, sets licensing rules, and has the "
                         "secretary of state publish them. A gadget, a gadget, a gadget, a gizmo, a gizmo and a gizmo; an inspection, "
                         "an inspection and an inspection; licensing. The secretary of state keeps the list."),
            "chapters": ["996", "997", "998-A"], "provisions": ["RSA 999-Q Sprocket Licensing"],
            "duties": ["the attorney general shall investigate", "the secretary of state shall publish them",
                       "the commissioner of labor may adopt rules", "the commissioner of labor shall enforce it"]}
    small = {"term": "2025-2026", "bill": "HB9998", "topic": "", "title": "relative to wages", "analysis": "",
             "chapters": [], "provisions": [], "duties": ["the commissioner of labor shall enforce"]}
    rules = TR.compile_registry(reg)
    tags = TR.tag_bill(rules, bill)["tags"]
    assert list(tags) == list(reg), f"the made-up bill does not carry all twelve: {sorted(set(reg) - set(tags))}"
    kinds = {t: TR.evidence(rules[t], bill, tags[t])[0] for t in tags}
    assert kinds == {"office-ag": "duty", "zoning-chapter": "chapter", "toys": "analysis",
                     "office-sos": "duty", "widget": "title", "sprocket": "provision", "gizmo": "analysis",
                     "permits": "chapter with a word", "inspection": "title", "labor-commissioner": "duty",
                     "licensing": "title", "bench-only": "hand"}, f"the evidence is misread: {kinds}"
    order = ["bench-only", "licensing", "inspection", "widget", "toys", "gizmo", "sprocket", "permits",
             "zoning-chapter", "office-sos", "labor-commissioner", "office-ag"]
    got = TR.ranked(rules, bill, tags)
    assert got == order, f"ranked: {got}, where THE CAP gives {order}"
    kept = [t for t in reg if t in order[:10]]
    assert list(TR.best_tags(rules, bill, tags)) == kept, f"best_tags kept {list(TR.best_tags(rules, bill, tags))}"
    assert TR.best_tags(rules, small, TR.tag_bill(rules, small)["tags"]) == TR.tag_bill(rules, small)["tags"], (
        "a bill under the cap lost a tag")
    # site_tags is where the site takes them: the engine's reading of the made-up bills, the cap applied.
    real_engine = TR.engine_bill
    made = {b["bill"]: b for b in (bill, small)}
    TR.engine_bill = lambda term, bid, title, text, topic: made[bid]
    tmp = Path(tempfile.mkdtemp())
    try:
        doc = {"tags": reg, "synonyms": {}, "digest": "c" * 64}
        rows = [(b["term"], b["bill"], b["title"], "", "") for b in (bill, small)]
        site = TR.site_tags(rows, doc, folder=tmp / "cache")
        warm = TR.site_tags(rows, doc, folder=tmp / "cache")
    finally:
        TR.engine_bill = real_engine
        shutil.rmtree(tmp, ignore_errors=True)
    assert list(site[("2025-2026", "HB9999")]) == kept, f"site_tags: {list(site[('2025-2026', 'HB9999')])}"
    assert site[("2025-2026", "HB9998")] == {"labor-commissioner": "R:the commissioner of labor shall"}, site
    assert warm == site, "the cache's answer is not the capped one"
    meta = [t["id"] for t in TR.site_meta(doc, site, set())["tags"]]
    assert meta == [t for t in reg if t != "office-ag"], f"meta.json's list: {meta}"
    return "ok", ("twelve tags of mixed evidence ranked hand, title (more kinds, then more of the bill's words), "
                  "analysis, provision, chapter with a word, chapter, duty (more duties first); site_tags keeps the "
                  "ten best in the registry's order, a bill of fewer keeps all, and meta.json lists a tag another "
                  "bill still carries")
