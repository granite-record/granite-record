#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
preflight's checks of session days and their pages, and the journals.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import ast
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (CHECKS, _check_outcome, _run, _source, check, imp)
from pf_fixture import (CHAIN_NEEDS, _fixture_site_shared, _fixture_videos)
from pf_harness import (_app_js, _node_app, _with_components)
from pf_shared import (_CONSENT_REMOVAL_LOOSE, _CONSENT_REMOVAL_NOT, _DOCKET_CUT_1999,
                       _JOURNAL_MOTION_AFTER, _VW_DOT_HEAD, _WRITTEN_DAY, _card_events,
                       _css_decls, _css_rules, _docket_rows, _narratives, _one_roll_call_each,
                       _rc, _site_bills, _sitting_fixture, _sittings_on_disk,
                       _speakers_against_journal, _vw_loose_dots)


@check("data", "no sitting lists a bill on its consent calendar on a day its chamber's docket "
               "records it taken off")
def _sitting_consent_on_disk():
    """The sitting pages, asked the question the histories are.

    A sitting page lists under "On the consent calendar" the bills it says
    the chamber "disposed of together, in one motion and without debate".
    On 2 October 2026 it listed 86 on the very day the docket records the
    bill taken off that calendar: session_days read a removal with a pattern
    of its own that the Senate's "Sen. D'Allesandro Moved to Remove SB 58
    from the Consent Calendar" (2011 to 2024) and the House's "REMOVED FROM
    CON CAL" of 1992 defeated, and read the rows in order, so that "SB 74-FN
    was Removed from the Consent Calendar; 03/20/2025", entered after the
    Senate passed it amended, came too late. A removal is found here by the
    loose search above, not by either reader, on the day the row is of and
    the day it writes.
    """
    SD = imp("session_days")
    if SD is None:
        return "skip", "session_days will not import"
    fn = Path("narratives.json")
    if not fn.exists():
        return "skip", "no narratives.json here"
    narr = _narratives()
    off = set()
    for term, byb in narr.items():
        for bill, n in byb.items():
            for e in n.get("events", []):
                raw = e.get("raw") or ""
                if e.get("cancelled") or not (
                        e.get("type") == "consent_off"
                        or (_CONSENT_REMOVAL_LOOSE.search(raw)
                            and not _CONSENT_REMOVAL_NOT.search(raw))):
                    continue
                days = {(e.get("date") or "")[:10]} | {
                    f"{y}-{int(m):02d}-{int(d):02d}" for m, d, y in _WRITTEN_DAY.findall(raw)}
                off |= {(e.get("body"), day, term, bill) for day in days}
    del narr
    sittings = _sittings_on_disk(SD, fn)
    listed = []
    for body, day, term, bill in sorted(off):
        sitting = sittings.get((body, day))
        if sitting and any(i.consent and i.term == term and i.bill == bill
                           for i in sitting.items):
            listed.append(f"{bill} of {term} ({body} {day})")
    assert not listed, (
        f"{len(listed)} sittings list a bill on the consent calendar the docket records it "
        "taken off that day: " + ", ".join(listed[:10]))
    return "ok", (f"{len(off):,} removal days read, and no sitting of them lists its bill on "
                  "the consent calendar")


# The Journals' own words around the votes on no bill of 2025-2026, cut short
# (journal_motions.py, 23 October 2026). Each file is the passage that
# Journal prints, with its running heads and page breaks where the PDF's text
# has them, and around it only what the reader has to cut away.
_JM_HJ = {
    "journals/2026/HJ 04 February 12, 2026.txt": (
        "                                 HOUSE JOURNAL No. 4\n\n"
        "                              Thursday, February 12, 2026\n\n"
        "\f32                                12FEBRUARY2026HOUSERECORD\n\n"
        "                                MOTION TO REPRIMAND\n\n"
        "Rep. Simpson moved that Representative Paige Beauchemin be reprimanded by the House of\n"
        "Representatives.\n\n"
        "The question being should Representative Paige Beauchemin be reprimanded by the House of\n"
        "Representatives?\n"
        "On a division vote, with 264 members having voted in the affirmative, and 89 in the negative, "
        "the motion\nwas adopted.\n"
        "Representative Paige Beauchemin was reprimanded by the House of Representatives.\n"),
    "journals/2026/HJ 06 March 5, 2026.txt": (
        "                                 HOUSE JOURNAL No. 6\n\n"
        "                              Thursday, March 5, 2026\n\n"
        "\f142                               5MARCH2026HOUSERECORD\n\n"
        "                                 UNANIMOUS CONSENT\n\n"
        "Rep. Wheeler requested Unanimous Consent of the House regarding Legislative Observations "
        "and addressed\nthe House.\n\n"
        "                                 UNANIMOUS CONSENT\n\n"
        "Rep. Beauchemin requested Unanimous Consent of the House regarding the war in Iran and "
        "addressed the\nHouse.\n\n"
        "                                     OBJECTION\n\n"
        "An objection was raised to the unanimous consent given by Rep. Beauchemin; withdrawing "
        "unanimous consent.\n\n"
        "The question being shall the member continue.\n"
        "Rep. Wheeler requested a roll call; sufficiently seconded.\n\n"
        "                                              YEAS 91 - NAYS 82\n\n"
        "Comtois, Barbara            Freeman, Lisa\n\n"
        "The motion failed lacking the necessary three-fifths vote and with a quorum not being "
        "reached, the House\nwas adjourned.\n"),
    "journals/2026/HJ 07 March 11, 2026.txt": (
        "                                 HOUSE JOURNAL No. 7\n\n"
        "                              Wednesday, March 11, 2026\n\n"
        "\f94                                 11MARCH2026HOUSERECORD\n\n"
        "and the majority committee report was adopted.\n\n"
        "                              MOTION TO SPECIAL ORDER\n\n"
        "Rep. Alissandra Murray moved that HB 1142, relative to requirements for law enforcement "
        "officers assisting\nin immigration enforcement, be made a Special Order to the next order "
        "of business.\n\nThe Speaker ruled the motion dilatory.\n\n"
        "                        CHALLENGE TO THE RULING OF THE CHAIR\n"
        "Rep. Heath Howard challenged the ruling of the Chair whereby the Chair ruled the motion to "
        "Special Order\nHB 1142, dilatory.\n\n"
        "The question being shall the ruling of the Chair be upheld?\n"
        "Rep. Comtois requested a roll call; sufficiently seconded.\n\n"
        "                                              YEAS 199 - NAYS 134\n\n"
        "Bay, Luz            Bixby, Peter\n\nand the ruling of the Chair was upheld.\n\n"
        "\f168                                11MARCH2026HOUSERECORD\n\n"
        "                              MOTION TO SPECIAL ORDER\n"
        "Rep. Heath Howard moved that HB 1609-FN, limiting the use of state, county, and municipal "
        "funds and\nproperty for construction and operation of certain immigrant detention "
        "facilities be made a Special Order to\nthe next order of business.\n\n"
        "Speaker Kofalt ruled the motion dilatory.\n\n"
        "                        CHALLENGE TO THE RULING OF THE CHAIR\n"
        "Rep. Heath Howard challenged the ruling of the Chair whereby the Chair ruled the motion to "
        "Special Order\nHB 1142, dilatory.\n\n"
        "The question being shall the ruling of the Chair be upheld?\n"
        "Rep. Belcher requested a roll call; sufficiently seconded.\n\n"
        "                                              YEAS 223 - NAYS 96\n\n"
        "and the ruling was upheld.\n\n"
        # The gates: a count whose outcome the Journal says otherwise, and a
        # roll call the file calls a suspension printed under a printing.
        "                               MOTION TO PRINT DEBATE\n\n"
        "Rep. Roesener moved that the debate on HB 1464-FN, relative to discrimination, be printed "
        "in the Permanent Journal.\nRep. Damon requested a roll call; sufficiently seconded.\n\n"
        "                                              YEAS 150 - NAYS 140\n\n"
        "and the motion failed.\n\n"
        "                               MOTION TO PRINT REMARKS\n\n"
        "Rep. Weber moved that the remarks made by Rep. Altschiller be printed in the Permanent "
        "Journal.\n\n"
        "                                              YEAS 120 - NAYS 130\n\n"
        "and the motion failed.\n\n"
        # A suspension of the rules for one bill, decided on a division: the
        # bill's (the owner's second review), as Rep. Phillips's for HB
        # 1000-FN-A's non-germane amendments was on 16 June 2016.
        "                           MOTION TO SUSPEND HOUSE RULES\n\n"
        "Rep. Phillips moved that House Rules be so far suspended as to allow consideration of "
        "floor amendments\nto HB 1000-FN-A that are non-germane.\n"
        "On a division vote, with 190 members having voted in the affirmative, and 110 in the "
        "negative, the motion\nfailed lacking the necessary two-thirds vote.\n"),
    "journals/2026/HJ 14 May 21, 2026.txt": (
        "                                 HOUSE JOURNAL No. 14\n\n"
        "                              Thursday, May 21, 2026\n\n"
        "\f23  21MAY2026HOUSERECORD\n\n"
        "                    REPORT OF THE COMMITTEE ON LEGISLATIVE ADMINISTRATION\n\n"
        "On March 5 and March 10, Representative Travis Corcoran made two posts on the social media "
        "platform X.\nCurrently, the majority of the committee recommends a formal censure of "
        "Representative Travis Corcoran by\nthe entire House of Representatives in light of the "
        "seriousness of the transgressions. Rep.\nGregory Hill for the Committee. Vote: 10-2\n"
        "\f24                                      21MAY2026HOUSERECORD\n\n"
        "The question was to affirm the report of the committee on Legislative Administration.\n"
        "Rep. Corcoran spoke against.\n"
        "Rep. McFarlane spoke against and requested a roll call; sufficiently seconded.\n\n"
        "                                              YEAS 288 - NAYS 54\n\n"
        "Bordes, Mike            Comtois, Barbara\n\n"
        "and the motion to affirm the report of the Committee on Legislative Administration was "
        "adopted.\n\n"
        "                                                                    CENSURE\n\n"
        "The Speaker informed Rep. Corcoran of the censure by the House.\n\n"
        "                               MOTION TO ADJOURN\n\n"
        "Rep. Sylvia moved that the House adjourn.\n\n"
        "                                              YEAS 41 - NAYS 247\n\n"
        "and the motion failed.\n"),
    # HJ 07 of 6 March 2025 prints the House's tallies a roll call out of
    # step: 190-156 stands where 2025-H-60's 171-89 belongs, printed nowhere.
    "journals/2025/HJ 07 March 6, 2025.txt": (
        "                                 HOUSE JOURNAL No. 7\n\n"
        "                              Thursday, March 6, 2025\n\n"
        "\f40                                 6MARCH2025HOUSERECORD\n\n"
        "The question now being shall the member be allowed to continue speaking.\n\n"
        "                                              YEAS 190 - NAYS 156\n\n"
        "and the member was allowed to continue with a three-fifths vote.\n"),
    # The Senate's remote sitting of 6 January 2021: two counts of 24-0 a
    # vote apart, each paired with the other's words.
    "journals_senate/2021/SJ002.txt": (
        "                       SENATE JOURNAL\n\nJanuary 6, 2021\n"
        "The Senate met at 10:00 a.m.\n"
        "\f32  SENATEJOURNAL6JANUARY2021\n\n"
        "Senator Bradley moved that the Senate adjourn from the Early Session.\n\n"
        "The question is on the adoption of the motion to adjourn from the Early Session.\n\n"
        "A roll call is required.\n\n"
        "The following Senators voted Yes: Hennessey, Giuda, Bradley.\n\n"
        "The following Senators voted No: (None)\n\n"
        "Roll Call, Yeas: 24 - Nays: 0. Adopted.\n\n"
        "The question is on the adoption of the Consent Calendar.\n\n"
        "A roll call is required.\n\n"
        "Roll Call, Yeas: 24 - Nays: 0. Adopted.\n"),
    # MOTIONS ON A BILL'S OWN DEBATE (the owner's review, 23 October 2026).
    # HB 1601's previous question, carried on a division after motions to
    # table it and to postpone it, both on HB 1601 (12 March 2014); then a
    # motion to limit debate under its own heading, naming no bill, which is
    # the day's and no one bill's.
    "journals/2014/HJ022.txt": (
        "                                 HOUSE JOURNAL No. 22\n\n"
        "                              Wednesday, March 12, 2014\n\n"
        "\f1254                               12march2014HOUSERECORD\n\n"
        "HB 1601, relative to mandatory headlamp use. MAJORITY: OUGHT TO PASS WITH AMENDMENT.\n"
        "MINORITY: INEXPEDIENT TO LEGISLATE.\n\n"
        "                                                 MOTION TO LAY ON THE TABLE\n\n"
        "Rep. James Webb moved that HB 1601, relative to mandatory headlamp use, be laid on the "
        "table.\nOn a division vote, 161 members having voted in the affirmative and 169 in the "
        "negative, the motion failed.\n\n"
        "The question now being adoption of the majority committee report of Ought to Pass with "
        "Amendment.\nRep. Beaudoin spoke against.\n\n"
        "                                            MOTION TO INDEFINITELY POSTPONE\n"
        "Rep. Michael Garcia moved that HB 1601, relative to mandatory headlamp use, be "
        "Indefinitely Postponed.\n\n"
        "Rep. Gary Richardson moved the previous question.\n"
        "On a division vote, 255 members having voted in the affirmative and 78 in the negative, "
        "the motion was\nadopted.\n\n"
        "                                              MOTION TO LIMIT DEBATE\n\n"
        "Rep. Janvrin moved to limit debate to 3 minutes on each side.\n"
        "On a division vote, with 166 members having voted in the affirmative, and 120 in the "
        "negative, the motion\nwas adopted.\n"),
    # A roll call the file files under no bill, "Divide 3rd Reading", that
    # moved to divide HB 1570-FN out of a motion (20 March 2014): HB 1570's.
    "journals/2014/HJ028.txt": (
        "                                 HOUSE JOURNAL No. 28\n\n"
        "                              Thursday, March 20, 2014\n\n"
        "\f1422                               20march2014HOUSERECORD\n\n"
        "                                      MOTION TO DIVIDE\n"
        "Rep. Jasper moved to divide the question to remove HB 1570-FN, establishing a paint "
        "stewardship\nprogram, from the Third Reading Motion.\n"
        "Rep. Shurtleff requested a roll call; sufficiently seconded.\n\n"
        "                                              YEAS 105 - NAYS 159\n\n"
        "Burchell, Richard     Cormier, Jane\n\nand the motion failed.\n"),
    # A MOTION AND ITS DECISION WITH AN APPEAL BETWEEN (16 September 2015):
    # the 286-89 upheld the Chair on Rep. William O'Brien's appeal, and the
    # 285-93 after it adopted the motion to suspend House Rules for SB 9,
    # which its own sentence names only as "the motion to suspend House
    # Rules". Both are SB 9's; the ten speakers are the 285-93's.
    "journals/2015/HJ057.txt": (
        "                Concord,N.H.  Wednesday,September16,2015  No.57X\n\n"
        "        HOUSE JOURNAL No. 18 (Cont.)\n\n"
        "\f                             16september2015HOUSERECORD                       2179\n\n"
        "                                             SENATE MESSAGE\n\n"
        "The Senate has passed a Bill with the following title, in the passage of which it asks "
        "the concurrence of the\nHouse of Representatives:\n"
        "SB 9-FN-A-L, relative to salary increases for state employees and making appropriations "
        "therefor.\n\n"
        "                                             MOTION TO SUSPEND HOUSE RULES\n\n"
        "Reps. Flanagan and Shurtleff moved that all necessary House Rules be so far suspended as "
        "to permit\nintroduction and consideration of Senate Bill 9, without the required referral "
        "to committee, public hearing or\nreport from committee, and if passed, allow for immediate "
        "third reading.\n\n"
        "                                          APPEAL OF THE RULING OF THE CHAIR\n"
        "Rep. William O'Brien appealed the ruling of the Chair on the ruling that introduction of "
        "a new bill does not\nviolate any constitutional provision or statute regarding "
        "appropriation of money bills originating in the House.\n\n"
        "The question being shall the ruling of the Chair be upheld?\n"
        "Rep. Hinch requested a roll call; sufficiently seconded.\n\n"
        "                                           YEAS 286 - NAYS 89\n\n"
        "Dumais, Russell      Fields, Dennis\n\n"
        "\f2180                    16september2015HOUSERECORD\n\n"
        "and the ruling of the Chair was upheld.\n\n"
        "The question now being adoption of the motion to suspend House Rules.\n"
        "Reps. Burt, Stepanek, Hoell and William O'Brien spoke against.\n"
        "Reps. Shurtleff and Hinch spoke in favor.\n"
        "Rep. Hinch requested a roll call; sufficiently seconded.\n\n"
        "                                              YEAS 285 - NAYS 93\n\n"
        "Dumais, Russell         Fields, Dennis\n\n"
        "and the motion was adopted by the necessary two-thirds vote.\n"),
    # The Senate calls the question by voice in a bill's debate, and divides
    # a question by the Chair's ruling, with no vote at all (3 May 2018).
    "journals_senate/2018/SJ016.txt": (
        "                       SENATE JOURNAL\n\nMay 3, 2018\n"
        "The Senate met at 10:00 a.m.\n"
        "\f1320  SENATEJOURNAL3MAY2018\n\n"
        "HB 1458, relative to exempting certain rules governing marine species.\n"
        "Ought to Pass with Amendment, Vote 4-1.\nSenator Avard for the committee.\n\n"
        "SENATOR FELTES: Thank you, Mister President. Don't vote for this.\n\n"
        "Senator Birdsell moved to call the question. Adopted.\n\n"
        "The question is on the adoption of the Floor Amendment.\n\n"
        "Senator Feltes moved to divide the question: Section 8 and Section 13.\n"
        "The Chair ruled the question divisible.\n\n"
        # BY THE JOURNAL'S OWN WORDS (the owner's second review): the same
        # motion "without objection" is no voice vote.
        "HB 1476, permitting qualifying patients and designated caregivers to cultivate cannabis.\n"
        "Ought to Pass, Vote 3-2.\nSenator Avard for the committee.\n\n"
        "SENATOR AVARD: Yes, it is. Unless you have a permit.\n\n"
        "Without objection, Senator Birdsell moved to call the question. Adopted.\n\n"
        "The question is on the adoption of the motion of Interim Study.\n"),
}


def _jm_rc(year, body, n, day, words, y, nn, passed):
    return {"year": year, "body": body, "number": n, "date": day, "bill": None,
            "procedural": True, "question": words, "question_raw": words, "yeas": y, "nays": nn,
            "passed": passed}


_JM_ROLLS = {"2025-2026": {"_procedural": [
    _jm_rc("2026", "H", 132, "2026-03-05", "Shall Member Continue", 91, 82, False),
    _jm_rc("2026", "H", 147, "2026-03-11", "Uphold Ruling of chair", 199, 134, True),
    _jm_rc("2026", "H", 166, "2026-03-11", "Uphold Ruling of the Chair", 223, 96, True),
    _jm_rc("2026", "H", 170, "2026-03-11", "Print Remarks", 150, 140, True),
    _jm_rc("2026", "H", 171, "2026-03-11", "Rules Suspension", 120, 130, False),
    _jm_rc("2026", "H", 290, "2026-05-21", "Affirm The Report", 288, 54, True),
    _jm_rc("2026", "H", 300, "2026-05-30", "Adjourn", 41, 247, False),
    _jm_rc("2025", "H", 60, "2025-03-06", "Shall Member Continue", 171, 89, True)]},
    "2021-2022": {"_procedural": [
        _jm_rc("2021", "S", 11, "2021-01-06", "Introduction of Senate Bills", 24, 0, True),
        _jm_rc("2021", "S", 12, "2021-01-06", "To Adjourn the Early Session", 24, 0, True)]},
    "2013-2014": {"_procedural": [
        _jm_rc("2014", "H", 167, "2014-03-20", "Divide 3rd Reading", 105, 159, False)]},
    "2015-2016": {"_procedural": [
        _jm_rc("2015", "H", 188, "2015-09-16", "Uphold Ruling of the Chair", 286, 89, True),
        _jm_rc("2015", "H", 189, "2015-09-16", "Rules Suspension", 285, 93, True)]}}


@check("rollcalls", "the Journal's sentences are found in one pass, and they are the pattern's own",
       needs=("journal_motions",))
def _journal_sentences_one_pass(JM):
    """last_decision read each passage's sentences with SENTENCE.finditer,
    which restarts one character on after every failed start: five and a half
    minutes of every build, in a step that took six (29 October 2026). It
    asks sentence_spans() now, which reads each stretch between full stops
    once. This holds the two to each other: on the ends of the pattern (a
    stop alone, a stop at the start, four line ends before a stop and three),
    on 20,000 strings made of the characters that decide a match, and on the
    Journal fixtures as written and cleaned. And it holds last_decision to the
    one pass: undone, the step is six minutes again and nothing else says so."""
    import inspect
    import random
    want = lambda s: [m.span() for m in JM.SENTENCE.finditer(s)]
    got = lambda s: list(JM.sentence_spans(s))
    texts = ["", ".", "..", "...", ".a", "a.", "\n.", "\n\n\n.", "\n\n\n\n.", "\n\n\n\n\n\n.",
             "a\nb\nc\nd\ne.", "x\n\n\n\n\ny.z.", "no stop at all\n\n\n", "a.\n\n\n\n\nb.",
             "\n" * 9 + "." + "\n" * 9 + ".", ". \n. \n\n\n\n\n.", "\f\r\n.\r\n\r\n\r\n\r\n."]
    rnd = random.Random(20261029)
    texts += ["".join(rnd.choice("a.\n \n.\r") for _ in range(rnd.randint(0, 60)))
              for _ in range(20000)]
    journal = [_JOURNAL_RECONSIDER, _JOURNAL_MOTION_AFTER, _JOURNAL_DECIDED, _JOURNAL_WALK,
               _JOURNAL_WALK_MORE]
    texts += journal + ["\n".join(journal)]
    texts += [t.replace(".", "") + "." for t in journal]
    bad = [t for t in texts if got(t) != want(t)]
    assert not bad, (f"sentence_spans and SENTENCE.finditer disagree on {len(bad)} text(s), "
                     f"the first {bad[0][:80]!r}: {got(bad[0])[:4]} against {want(bad[0])[:4]}")
    src = inspect.getsource(JM.last_decision)
    assert "sentence_spans(" in src and "finditer(r\"[^.\\n]" not in src \
        and "SENTENCE.finditer" not in src, (
        "last_decision reads its sentences with finditer again: six minutes of every build")
    return "ok", (f"{len(texts):,} texts, every one the same spans both ways; last_decision "
                  "reads them in one pass")


@check("rollcalls", "a vote on no bill is shown in the Journal's own words only where its tally, "
       "page date, question and outcome agree, a summary never names two bills, a vote that names "
       "a member is summed up only by a person, a report is kept whole only where it is bounded, "
       "and a motion on one bill's debate is that bill's", needs=("journal_motions",))
def _journal_motions(JM):
    """The owner, 23 October 2026: "Those are often important votes that
    sometimes get reported on, but it's very hard to find that information
    on GenCourt since the vote is just labeled something like voting whether
    to approve the committee report with no other context." The censure of
    Rep. Corcoran was "Affirm The Report", 288-54. journal_motions.py reads
    the passage above each such roll call's tally in the Journal and keeps
    what was put, verbatim; this holds it to the passages the research of
    that day read, cut short, and holds every gate.

    It fails if the passage reaches past the question it ends on (Rep.
    Wheeler's consent above Rep. Beauchemin's; a speaker's attribution),
    if a heading or a running head is read into a sentence, if 2025-H-60's
    171-89 is placed where HJ 07 of 2025 prints another count, if a vote
    printed a week from its date or under another kind of question or with
    another outcome is shown, if the Senate's twin 24-0s are shown under each
    other's words, if the special order of HB 1609-FN challenged as "HB 1142"
    gets a summary or a bill, if a censure gets a summary no person approved
    or an approval for another page, if the division that reprimanded Rep.
    Beauchemin is not read, if a year that yields nothing goes unremarked,
    or if a run over some years takes the others' entries away."""
    d = Path(tempfile.mkdtemp())
    keep = JM.APPROVED
    try:
        for name, text in _JM_HJ.items():
            (d / name).parent.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(text, encoding="utf-8")
        (d / "rollcalls.json").write_text(json.dumps(_JM_ROLLS), encoding="utf-8")
        (d / "lines.json").write_text(json.dumps({"lines": {"2026-H-290": {
            "line": "Censure Rep. Travis Corcoran", "file": "journals/2026/HJ 14 May 21, 2026.txt",
            "page": 24, "approved": "2026-10-23"}}}), encoding="utf-8")
        JM.APPROVED = d / "nowhere.json"
        entries, only, years, stats, on_bills = JM.build(d / "rollcalls.json", d)
        JM.APPROVED = d / "lines.json"
        approved, _o, _y, _s, _b = JM.build(d / "rollcalls.json", d)
        bad = []
        uc = entries.get("2026-H-132") or {}
        said = [x["t"] for x in uc.get("said") or []]
        if uc.get("held") or said[:3] != [
                "Rep. Beauchemin requested Unanimous Consent of the House regarding the war in Iran "
                "and addressed the House.",
                "An objection was raised to the unanimous consent given by Rep. Beauchemin; "
                "withdrawing unanimous consent.",
                "The question being shall the member continue."]:
            bad.append(f"2026-H-132 reads {said} (held {uc.get('held')})")
        if (uc.get("kind"), uc.get("page"), uc.get("member"), uc.get("heading")) != (
                "member_continue", 142, "Beauchemin", "OBJECTION") or "war in Iran" not in (
                uc.get("line") or ""):
            bad.append(f"2026-H-132: {uc.get('kind')}, page {uc.get('page')}, "
                       f"{uc.get('member')!r}, {uc.get('heading')!r}, {uc.get('line')!r}")
        if any("Wheeler" in s or "spoke" in s or "HOUSERECORD" in s or "OBJECTION" in s
               for s in said):
            bad.append(f"2026-H-132's quote reaches past its question: {said}")
        ok = entries.get("2026-H-147") or {}
        if ok.get("held") or ok.get("bill") != "HB1142" or ok.get("line") != (
                "Uphold the ruling that the motion to Special Order HB 1142 was dilatory"):
            bad.append(f"2026-H-147: {ok.get('held')}, {ok.get('bill')!r}, {ok.get('line')!r}")
        two = entries.get("2026-H-166") or {}
        if two.get("held") or two.get("line") or two.get("bill") or \
                sorted(two.get("bills") or []) != ["HB1142", "HB1609"]:
            bad.append(f"2026-H-166, HB 1609-FN challenged as HB 1142, has a line "
                       f"{two.get('line')!r} or a bill {two.get('bill')!r}")
        cen = entries.get("2026-H-290") or {}
        if cen.get("held") or cen.get("kind") != "reprimand" or cen.get("line") or \
                cen.get("member") != "Travis Corcoran" or "informed Rep. Corcoran" not in (
                cen.get("after") or "") or not any(
                x["k"] == "report" and "formal censure of Representative Travis Corcoran" in x["t"]
                for x in cen.get("said") or []):
            bad.append(f"2026-H-290 the censure: {cen.get('kind')}, line {cen.get('line')!r}, "
                       f"{cen.get('member')!r}, {[x['k'] for x in cen.get('said') or []]}")
        if (approved.get("2026-H-290") or {}).get("line") != "Censure Rep. Travis Corcoran":
            bad.append("a person's approved line for the censure is not used")
        for key, why in (("2026-H-170", "outcome"), ("2026-H-171", "question"),
                         ("2026-H-300", "date"), ("2021-S-11", "question"),
                         ("2021-S-12", "question")):
            got = (entries.get(key) or {}).get("held") or []
            if not any(h.startswith(why) for h in got):
                bad.append(f"{key} is not held back for its {why}: {got}")
        if "2025-H-60" in entries:
            bad.append("2025-H-60's 171-89, printed nowhere, was placed at 190-156")
        rep = [x for x in only if x.get("kind") == "reprimand"]
        if len(rep) != 1 or (rep[0].get("yeas"), rep[0].get("nays"), rep[0].get("passed"),
                             rep[0].get("member"), rep[0].get("how")) != (
                264, 89, True, "Paige Beauchemin", "division"):
            bad.append(f"the reprimand by division of 12 February 2026 reads {rep}")
        # MISC VOTES (the owner, 23 October 2026): no kind a reader sees says
        # "discipline", and a reprimand is filtered with every question that
        # has no name of its own.
        if any("discipl" in w.lower() for w in JM.KINDS.values()) or \
                {JM.KINDS[k] for k in ("reprimand", "privileges", "motion", "other")} != {"Misc vote"} \
                or {JM.GROUPS.get(k) for k in ("reprimand", "privileges", "motion", "other")} != {"misc"} \
                or JM.GROUP_WORDS.get("misc") != "Misc votes":
            bad.append("a kind a reader sees still frames a vote as discipline, or Misc votes is "
                       "not the reprimand's group")
        # VIEW THE REPORT: the Legislative Administration Committee's report,
        # whole, from its heading to where the question is put, on its page.
        r = cen.get("report") or {}
        paras = r.get("paras") or []
        if (r.get("heading"), r.get("page_from"), r.get("page_to")) != (
                "REPORT OF THE COMMITTEE ON LEGISLATIVE ADMINISTRATION", 23, 23) or len(paras) != 1 \
                or not paras[0].startswith("On March 5 and March 10, Representative Travis Corcoran") \
                or not paras[0].endswith("Rep. Gregory Hill for the Committee. Vote: 10-2"):
            bad.append(f"the censure's report reads {r}")
        # A report not bounded for certain is not shown: another heading
        # between it and its question, or a question naming another committee.
        loose = ("\f9  1JANUARY2026HOUSERECORD\n\n      REPORT OF THE COMMITTEE ON RULES\n\n"
                 + "The committee met and recommends the rule. " * 6
                 + "\n\n        MOTION TO RECESS\n\nRep. Smith moved to recess.\n"
                 "The question was to affirm the report of the committee on Rules.\n\n"
                 "        YEAS 100 - NAYS 90\n")
        got, why = JM.report_of(loose, loose.index("YEAS 100"))
        other = loose.replace("        MOTION TO RECESS\n\nRep. Smith moved to recess.\n", "") \
                     .replace("committee on Rules.", "committee on Legislative Ethics.")
        got2, why2 = JM.report_of(other, other.index("YEAS 100"))
        if got or "another heading" not in why or got2 or "not the report's" not in why2:
            bad.append(f"a report not bounded for certain is kept: {why!r}, {why2!r}")
        # Its paragraphs as the page reads them: a numbered section opens one
        # only where the last ended, a page break is not a paragraph, a word
        # the press broke is mended -- with its hyphen ("Mem-" "ber") or
        # without ("com" "plaints", where "complaints" stands elsewhere), and
        # a range keeps its hyphen ("2027-" "2036").
        chunk = ("I. Introduction\n     The Committee received three complaints, regarding the conduct "
                 "of\n\nRepresentative Spillane. The com\nplaints were made by a fellow Mem-\nber of "
                 "the House about the 2027-\n2036 plan, under Paragraph\nIV. Principle of Conduct.\n"
                 "\f64            19AUGUST2026HOUSERECORD\n\nand the conduct of individuals.\n"
                 "II. Charges\n     The conduct alleged is as follows.\n")
        got = JM._paragraphs(chunk, 0, len(chunk), JM._vocab(chunk + " complaints "))
        want = ["I. Introduction",
                "The Committee received three complaints, regarding the conduct of Representative "
                "Spillane. The complaints were made by a fellow Member of the House about the "
                "2027-2036 plan, under Paragraph IV. Principle of Conduct. and the conduct of "
                "individuals.",
                "II. Charges", "The conduct alleged is as follows."]
        if got != want:
            bad.append(f"a report's paragraphs read {got}")
        # LIMITING DEBATE ON A BILL IS THE BILL'S: the roll call "Divide 3rd
        # Reading" on HB 1570-FN; HB 1601's previous question by division; the
        # Senate's call of the question by voice in HB 1458's debate; and not
        # the day's limit on debate under its own heading, nor a division the
        # Chair ruled, nor a roll call, nor a reconsideration or an amendment
        # of a motion to limit debate.
        div = entries.get("2014-H-167") or {}
        if (div.get("on_bill"), div.get("bill_motion")) != ("HB1570", "divide"):
            bad.append(f"2014-H-167, dividing HB 1570-FN, is not that bill's: {div.get('on_bill')!r}")
        got = sorted((e["date"], e["body"], e["bill"], e["motion"], e["how"], e["yeas"], e["nays"],
                      e["passed"], e["bill_from"]) for e in on_bills)
        if got != [("2014-03-12", "H", "HB1601", "previous_question", "division", 255, 78, True,
                    "debate"),
                   ("2018-05-03", "S", "HB1458", "previous_question", "voice", None, None, True,
                    "debate"),
                   # By the Journal's own words: "Without objection, ...".
                   ("2018-05-03", "S", "HB1476", "previous_question", "without objection", None,
                    None, True, "debate"),
                   # A suspension of the rules for one bill, on a division.
                   ("2026-03-11", "H", "HB1000", "suspend_rules", "division", 190, 110, False,
                    "named")]:
            bad.append(f"the motions on a bill's debate read {got}")
        # THE OWNER'S SECOND REVIEW: a ruling on a motion about one bill is
        # that bill's (HB 1142's special order, 11 March 2026); the slip that
        # names HB 1609-FN and HB 1142 ties to neither and stays a misc vote;
        # a rules suspension, an appeal left on no bill and a member going on
        # under unanimous consent are misc votes, each keeping its own kind.
        if (ok.get("on_bill"), ok.get("bill_motion"), ok.get("on_bill_from")) != (
                "HB1142", "appeal", "named"):
            bad.append(f"the ruling on HB 1142's special order is not HB 1142's: {ok.get('on_bill')!r}")
        if two.get("on_bill") or two.get("group") != "misc" or \
                two.get("on_bill_held") != "the passage names more than one bill":
            bad.append(f"the HB 1609-FN/HB 1142 slip is tied to a bill or not a misc vote: "
                       f"{two.get('on_bill')!r}, {two.get('group')!r}")
        if (uc.get("group"), uc.get("kind")) != ("misc", "member_continue") or uc.get("on_bill"):
            bad.append(f"a member going on under unanimous consent is not a misc vote: {uc.get('group')}")
        if JM.KINDS["suspend_rules"] != "Rules suspension" or \
                {JM.group_of(k) for k in ("suspend_rules", "appeal")} != {"misc"} or \
                JM.group_of("member_continue", [{"k": "question", "t": "The question now being shall "
                                                 "the member be allowed to continue speaking."}]) \
                != "member_continue" or JM.group_of("member_continue", [
                    {"k": "question", "t": "The question being shall the member be permitted to "
                                           "continue speaking with the consent of the House?"}]) != "misc":
            bad.append("a rules suspension or an appeal is not a misc vote, or a member going on is "
                       "grouped by anything but the consent they spoke by")
        if [x["t"] for x in JM.tied_subject("suspend_rules", [
                {"k": "moved", "t": "Rep. Horn moved that the debate on HB 1640-FN be printed."},
                {"k": "moved", "t": "Rep. Leishman moved that House Rules be so far suspended as to "
                                    "allow the remaining bills to be taken up later."}])] != [
                "Rep. Leishman moved that House Rules be so far suspended as to allow the remaining "
                "bills to be taken up later."]:
            bad.append("a suspension is tied by a bill another motion of its passage named")
        if JM.bills_in([{"t": "to permit introduction and consideration of Senate Bill 9"}]) != ["SB9"]:
            bad.append("\"Senate Bill 9\" is not read as SB 9")
        # THE MOTION A QUESTION PUTS AGAIN BY ITS KIND (16 September 2015):
        # the appeal between SB 9's suspension and its decision is SB 9's, and
        # so is the decision, "the motion to suspend House Rules", read as
        # the motion Reps. Flanagan and Shurtleff moved above the appeal --
        # and never as a motion on that motion, nor across another heading.
        ap, su = entries.get("2015-H-188") or {}, entries.get("2015-H-189") or {}
        if (ap.get("kind"), ap.get("on_bill"), su.get("kind"), su.get("on_bill"),
                su.get("on_bill_from")) != ("appeal", "SB9", "suspend_rules", "SB9", "named") \
                or not (su.get("said") or [{}])[0].get("t", "").startswith(
                    "Reps. Flanagan and Shurtleff moved that all necessary House Rules") \
                or su.get("held"):
            bad.append(f"SB 9's appeal and suspension of 16 September 2015 are not SB 9's: "
                       f"{ap.get('kind')} {ap.get('on_bill')!r}, {su.get('kind')} "
                       f"{su.get('on_bill')!r} {[x['t'][:40] for x in su.get('said') or []]}")
        motion = ("            MOTION TO PRINT IN HOUSE CALENDAR\n\nRep. Verville moved that the "
                  "remonstrances be printed in the House Calendar.\n\n")
        on_it = ("            MOTION TO LIMIT DEBATE\n\nRep. Callum moved to limit debate on the "
                 "motion to print remonstrances in the House Calendar.\nOn a division vote, with "
                 "173 members having voted in the affirmative, and 171 in the negative, the motion "
                 "was adopted.\n\n")
        q = "The question now being adoption of the motion to print the remonstrances."
        for text, want_t in ((motion + on_it, "Rep. Verville moved"),
                             (motion + "            INTRODUCTION OF GUESTS\n\nRep. Ames moved to "
                                       "welcome the guests.\n\n", None)):
            got = JM.put_again(text + q, len(text), q)
            if (got[0]["t"][:19] if got else None) != want_t:
                bad.append(f"the motion put again by its kind reads {got and got[0]['t']!r}, "
                           f"not {want_t!r}")
        for want_k in ("bill motions: held: a heading of its own (MOTION TO LIMIT DEBATE) stands "
                       "between it and the bill's entry",
                       "bill motions: held: the Chair ruled on it, and no vote was taken",
                       "bill motions: a roll call: the roll-call file's"):
            if not stats.get(want_k):
                bad.append(f"no motion was held or left as {want_k[14:]!r}")
        for s, want_k in (("Rep. Gary Richardson moved the previous question.", "previous_question"),
                          ("Senator Birdsell moved to call the question.", "previous_question"),
                          ("Rep. Weber moved that section two of HB 724-FN be divided from the "
                           "bill.", "divide"),
                          ("Rep. MacKay moved that the House reconsider its action whereby it "
                           "adopted the motion to limit debate on HB 162.", ""),
                          ("Rep. Vaillancourt moved to amend the motion to limit debate to 2 "
                           "hours.", "")):
            if JM.bill_motion_of(s) != want_k:
                bad.append(f"{s!r} is read as {JM.bill_motion_of(s)!r}")
        # The hand-check of 23 October 2026: "Adjourn Late Session" paired
        # with a motion to adjourn from the Early Session (18 March 2021);
        # "Consent was withdrawn." as the objection it is (26 March 2025); a
        # finding of disorderly speech as its own kind (27 February 2019); a
        # recess "until noon and spoke in favor" (27 June 2002).
        if not JM.contradicts("Adjourn Late Session", [
                {"k": "question", "t": "The question is on the adoption of the motion to adjourn "
                                       "from the Early Session."}]):
            bad.append("an early session's adjournment is shown for the late session's")
        if not dict(JM.SAY)["objection"].search("Consent was withdrawn."):
            bad.append("\"Consent was withdrawn.\" is not read as the objection")
        if JM.classify("DISORDERLY SPEECH MOTION", [
                {"k": "moved", "t": "Rep. DiLorenzo moved that the debate by Rep. Burt was "
                                    "disorderly speech."}], "Disorderly Speech") != "disorderly":
            bad.append("a finding of disorderly speech is not its own kind")
        recess = JM.one_line("adjourn", [{"k": "moved", "t": "Rep. Clemons moved that the House "
                                                            "recess until noon and spoke in favor."}],
                             ("", ""))[0]
        if recess != "To recess until noon":
            bad.append(f"a recess motion's summary reads {recess!r}")
        # SILENCE: a year whose Journals are here and whose roll calls were
        # placed, with not one sentence read.
        quiet = {"2026-H-1": {"key": "2026-H-1", "body": "H", "said": [{"k": "outcome", "t": "x"}]}}
        if JM.silence(quiet, {("2026", "H")}) != ["2026"]:
            bad.append("a year that yields nothing is not named by the silence guard")
        # A WRITER RUN ON A SUBSET: the years not read are kept as they were.
        out = d / "jm.json"
        out.write_text(json.dumps({"rollcalls": {"2019-H-5": {"key": "2019-H-5", "body": "H"},
                                                 "2026-H-9": {"key": "2026-H-9", "body": "H"}},
                                   "journal_only": [{"date": "2019-01-02", "body": "H"}],
                                   "bill_votes": [{"date": "2019-01-03", "body": "H"},
                                                  {"date": "2014-01-03", "body": "H"}]}),
                       encoding="utf-8")
        doc = JM.write(entries, only, {("2026", "H"), ("2021", "S"), ("2025", "H"), ("2014", "H")},
                       out, on_bills)
        if "2019-H-5" not in doc["rollcalls"] or "2026-H-9" in doc["rollcalls"] or \
                not any(x.get("date") == "2019-01-02" for x in doc["journal_only"]) or \
                not any(x.get("date") == "2019-01-03" for x in doc["bill_votes"]) or \
                any(x.get("date") == "2014-01-03" for x in doc["bill_votes"]):
            bad.append("a run over some years took the others' entries, or kept a year it read")
        assert not bad, "; ".join(bad)
        shown = sum(1 for e in entries.values() if not e["held"])
        return "ok", (f"{shown} of {len(entries)} placed votes shown in the Journal's words, "
                      f"{len(entries) - shown} held back for their date, question or outcome; "
                      "two bills, no summary; a censure summed up only by a person, its report "
                      "kept whole; the reprimand by division read, a Misc vote, as a rules "
                      "suspension, an appeal and a member going on by consent are; "
                      f"{len(on_bills)} votes on a bill's debate or arising on it found, the "
                      "ruling on HB 1142 tied to it and the two-bill slip to neither, without "
                      "objection by the Journal's words; the silent year named; other years kept")
    finally:
        JM.APPROVED = keep
        shutil.rmtree(d, ignore_errors=True)

# THE MOTION BY NAME AND THE RULING (the owner, 23 October 2026), each case
# a passage the House or Senate Journal printed, as journal_motions.py read
# it that day: (roll call, kind, chamber, member gate 7 named, the Journal's
# line after the vote, the bills named, [(what, sentence)], what it is headed).
_NAMED_VOTES = [
    ("2026-H-290", "reprimand", "H", "Travis Corcoran",
     "The Speaker informed Rep. Corcoran of the censure by the House.", [],
     [("moved", "Following the letter, Rep. Simpson moved to reprimand the member and the Speaker "
                "referred the matter to this committee for review and report."),
      ("question", "The question was to affirm the report of the committee on Legislative "
                   "Administration.")],
     "Affirm the Committee Report (Censure Rep. Corcoran)"),
    # The same passage where gate 7 named no member: the member goes unnamed.
    ("2026-H-290", "reprimand", "H", "", "", [],
     [("question", "The question was to affirm the report of the committee on Legislative "
                   "Administration.")],
     "Affirm the Committee Report"),
    ("2020-H-56", "reprimand", "H", "", "", [],
     [("moved", "Therefore, I move that Representative Charlie Burns be reprimanded by the House "
                "of Representatives."),
      ("question", "The question being should Representative Charlie Burns be reprimanded by the "
                   "House of Representatives?"),
      ("moved", "Rep. Sylvia moved that the motion to reprimand Representative Charlie Burns, be "
                "laid on the table.")],
     "Lay the Motion on the Table (Motion to Reprimand)"),
    ("2020-H-57", "reprimand", "H", "Charlie Burns",
     "Representative Charlie Burns was reprimanded by the House of Representatives.", [],
     [("moved", "Therefore, I move that Representative Charlie Burns be reprimanded by the House "
                "of Representatives."),
      ("question", "The question now being should Representative Charlie Burns be reprimanded by "
                   "the House of Representatives?")],
     "Reprimand the Member (Rep. Charlie Burns)"),
    ("2020-H-59", "reprimand", "H", "", "", [],
     [("question", "The question now being should Representative Andrew Prout be reprimanded by "
                   "the House of Representatives?")],
     "Reprimand the Member"),
    ("2026-H-291", "privileges", "H", "Read", "", [],
     [("moved", "Rep. McGhee moved that the motion to remove the sanctions on Rep. Read be removed "
                "from the table.")],
     "Remove from the Table (Motion to Remove the Sanctions on Rep. Read)"),
    ("2017-H-117", "motion", "H", "", "", [],
     [("question", "The question being adoption of the motion to send to Committee.")],
     "Refer to Committee"),
    ("2022-H-9", "motion", "H", "", "", ["HB50"],
     [("moved", "Having voted with the prevailing side, Rep. Steven Smith moved that the House "
                "reconsider its action whereby, on a roll call vote of 186-168, the House adopted "
                "the majority committee report of Ought to Pass with Amendment on HB 50, "
                "apportioning state representative districts.")],
     "Reconsider (Majority Committee Report)"),
    ("2010-S-70", "motion", "S", "", "", ["SSSB2"],
     [("moved", "Sen. Janeway moved to table SS SB 2-FN Draft, LSR 2977."),
      ("question", "The question is on motion to table SS SB 2-FN Draft, LSR 2977.")],
     "Lay on the Table"),
    ("2006-H-213", "motion", "H", "", "", [],
     [("moved", "Rep. Pepino offered floor amendment (2410h)."),
      ("ruled", "The Speaker ruled the amendment was germane."),
      ("question", "The question being adoption of floor amendment (2410h)")],
     "Adopt the Floor Amendment (2410h)"),
    ("2021-S-328", "motion", "S", "", "", [],
     [("moved", "Senator Bradley moved that the following Bills be special ordered to Thursday, "
                "May 6, 2021.")],
     "Special Order (to Thursday, May 6, 2021)"),
    ("2024-05-23-H-d541865", "reprimand", "H", "", "", [],
     [("moved", "Rep. Yokela moved to reprimand Rep. Aures."),
      ("moved", "Rep. Hoell moved that the motion to reprimand Rep. Aures, be laid on the table.")],
     "Lay the Motion on the Table (Motion to Reprimand)"),
    # No motion here fits a member's continuing put as a "motion": no head.
    ("2026-H-132", "motion", "H", "", "", [],
     [("question", "The question being shall the member continue.")], ""),
]
# (roll call, bills named, [(what, sentence)], what the chair ruled).
_RULINGS = [
    ("2026-H-147", ["HB1142"],
     [("ruled", "The Speaker ruled the motion dilatory."),
      ("challenge", "Rep. Heath Howard challenged the ruling of the Chair whereby the Chair ruled "
                    "the motion to Special Order HB 1142, dilatory.")],
     "The chair ruled the motion to Special Order HB 1142 dilatory."),
    # HB 1609-FN challenged as "HB 1142": two bills, no ruling (gate 6).
    ("2026-H-166", ["HB1609", "HB1142"],
     [("ruled", "Speaker Kofalt ruled the motion dilatory."),
      ("challenge", "Rep. Heath Howard challenged the ruling of the Chair whereby the Chair ruled "
                    "the motion to Special Order HB 1142, dilatory.")], ""),
    ("2015-H-188", ["SB9"],
     [("challenge", "Rep. William O'Brien appealed the ruling of the Chair on the ruling that "
                    "introduction of a new bill does not violate any constitutional provision or "
                    "statute regarding appropriation of money bills originating in the House.")],
     "The chair ruled that introduction of a new bill does not violate any constitutional "
     "provision or statute regarding appropriation of money bills originating in the House."),
    ("2013-H-7", [],
     [("moved", "Rep. Lambert moved to refer a Petition to a House Committee."),
      ("ruled", "The Speaker ruled the motion out of order."),
      ("challenge", "Rep. Lambert appealed the ruling of the Chair whereby the Chair, pursuant to "
                    "House Rule 18, ruled the motion out of order.")],
     "The chair ruled the motion to refer a Petition to a House Committee out of order."),
    ("2020-H-172", [],
     [("challenge", "Rep. Marsh challenged the ruling of the Chair on House Rule 65, the Speaker "
                    "has the authority to set meetings of the House.")],
     "The ruling was on House Rule 65, the Speaker has the authority to set meetings of the "
     "House."),
    ("2011-02-16-H-t84566", [],
     [("challenge", "Rep. Gary Richardson appealed the ruling of the Chair for declaring that a "
                    "motion to Lay on the Table was in order on HB 37-FN-A, reestablishing the "
                    "initial monthly gross charge exemption to the communications services tax.")],
     "The chair declared that a motion to Lay on the Table was in order on HB 37-FN-A, "
     "reestablishing the initial monthly gross charge exemption to the communications "
     "services tax."),
    ("2014-01-22-H-d36132", [],
     [("moved", "Rep. Carol McGuire moved that the House stand in recess."),
      ("ruled", "Speaker ruled the motion out of order."),
      ("challenge", "Rep. Carol McGuire appealed the ruling of the Chair on the motion to recess "
                    "being out of order.")],
     "The chair ruled the motion to recess out of order."),
    # The Journal says only that the ruling was appealed: nothing to say.
    ("2008-05-15-H-d136009", [],
     [("challenge", "Rep. Vaillancourt appealed the ruling of the Chair.")], ""),
]

_RULING_VOTES_JS = r"""
require("./stub.js");
const fs = require("fs");
globalThis.fetch = async u => ({ok: true, status: 200, json: async () => ({H: [], S: []}),
  text: async () => "{}"});
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({renderVotes})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const rc = JSON.parse(fs.readFileSync("./rc.json", "utf8"));
const out = {with: s.renderVotes({id: "SB9"}, {rollcalls: [rc]}),
             without: s.renderVotes({id: "SB9"}, {rollcalls: [Object.assign({}, rc, {ruling: ""})]})};
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("rollcalls", "a Misc vote is headed by the motion the Journal says was put, a member named "
       "only where gate 7 names them; an appeal is \"Uphold the Ruling of the Chair\" with no gloss, "
       "and what the chair ruled where the Journal says, on the session day and the bill's Votes tab",
       needs=("journal_motions", "vote_passage", "build_session_pages", "session_days",
              "build_nobill_votes", "components"))
def _motion_named_and_ruling_said(JM, VP, BSP, SD, NB, C):
    """The owner, 23 October 2026: "Could the actual vote on the Travis
    Corcoran censure for example be something along the lines of 'Affirm the
    Committee Report (Censure Rep. Corcoran)' rather than Misc Vote? It's
    fine for that to be the general category, but I'd like it to be more
    specific on the actual display showing the specific motion. Also listing
    Back the presiding officer is honestly more confusing than just listing
    uphold the ruling of the chair by itself. An alternative might be if it's
    possible to include what the ruling of the chair was for context, but if
    that isn't available, just leave it as 'Uphold the Ruling of the Chair'."

    It fails if a passage the Journal printed is headed otherwise than the
    table above says -- a member named where gate 7 did not name them, a
    motion on a motion headed as the motion it is on, a head guessed where no
    motion fits -- or a ruling is said otherwise, or said where the passage
    names two bills or only "the motion"; if a word of either is not in the
    passage; if "Back the presiding officer" or any gloss is back on the
    head; if the session day, the term's list or the member tab's few words
    head a named vote "Misc vote", or the session day or the bill's Votes tab
    leaves the ruling out from under an appeal on a bill, or draws one where
    there is none."""
    import html
    bad = []

    def entry(key, kind, body, member, after, bills, said):
        return {"key": key, "kind": kind, "body": body, "member": member, "after": after,
                "bills": list(bills), "held": [],
                "said": [{"k": k, "t": t} for k, t in said] + [{"k": "outcome", "t": "Adopted."}]}

    for key, kind, body, member, after, bills, said, want in _NAMED_VOTES:
        e = JM.name_entry(entry(key, kind, body, member, after, bills, said))
        if (e.get("title") or "") != want:
            bad.append(f"{key} ({member or 'no member'}) is headed {e.get('title')!r}, not {want!r}")
    for key, bills, said, want in _RULINGS:
        e = JM.name_entry(entry(key, "appeal", "H", "", "", bills, said))
        if (e.get("ruling") or "") != want:
            bad.append(f"{key}'s ruling reads {e.get('ruling')!r}, not {want!r}")
        if e.get("title"):
            bad.append(f"{key}, an appeal, carries a head of its own: {e['title']!r}")
    held = JM.name_entry(dict(entry(*_NAMED_VOTES[0][:7]), held=["outcome: not the record's"]))
    if held.get("title"):
        bad.append("a vote held back is named")
    # THE GLOSS: none on Uphold the Ruling of the Chair, wherever it is drawn.
    m = C.WORDBOOK["votes"]["motions"]["uphold_ruling"]
    head = C.vote_head("uphold_ruling", "Uphold Ruling of the Chair", {})
    if m.get("gloss") or "presiding officer" in head or "(" in head:
        bad.append(f"Uphold the Ruling of the Chair is glossed: {head!r}")
    # THE PAGES. The session day, the term's list and the member tab's few
    # words, from vote_passage as journal_motions.json says.
    named = JM.name_entry(entry(*_NAMED_VOTES[0][:7]))
    named.update(passed=True, yeas=288, nays=54, how="division", date="2026-05-21",
                 journal="House Journal 14", page=24)
    plain = dict(named, title="")
    if VP.title(named) != "Affirm the Committee Report (Censure Rep. Corcoran)" \
            or VP.title(plain) != VP.kind_label(plain):
        bad.append(f"vote_passage heads the censure {VP.title(named)!r}, or one the parser did "
                   f"not name {VP.title(plain)!r} rather than by its kind")
    if not VP.short(named).startswith("Affirm the Committee Report"):
        bad.append(f"the member tab's few words for the censure are {VP.short(named)!r}")
    # (no member index here: the head is what is read)
    jo = BSP.journal_only_html(dict(named, member=""), "H", None, html.escape, [])
    if '<p class="dvh">Affirm the Committee Report (Censure Rep. Corcoran)' not in jo:
        bad.append("the session day does not head the censure by its motion")
    row = NB.row_html({"kind": "reprimand", "title": named["title"], "line": "", "heading": "",
                       "words": "", "shown": True, "member": "", "body": "H", "date": "2026-05-21",
                       "link": "", "how": "division", "yeas": 288, "nays": 54, "passed": True})
    if "Affirm the Committee Report (Censure Rep. Corcoran)" not in row or "Misc vote" in row:
        bad.append("the term's list does not head the censure by its motion")
    # An appeal on a bill: the session day, from journal_motions.json.
    src = str(VP.SOURCE)
    kept = VP._CACHE.pop(src, None)
    rul = _RULINGS[2][3]
    VP._CACHE[src] = {"rollcalls": {"2015-H-188": {"key": "2015-H-188", "held": [], "ruling": rul}},
                      "journal_only": [], "kinds": {}, "groups": {}, "group_words": {},
                      "bill_votes": []}
    try:
        it = SD.Item("SB9", "2015-2016", {"date": "2015-09-16", "body": "H", "type": "floor",
                                          "action": "Uphold Ruling of the Chair", "motion": "MA",
                                          "vote_kind": "RC", "yeas": 286, "nays": 89}, 0)
        it.rc = {"year": "2015", "body": "H", "number": 188}
        day = BSP.vote_html(it, "SB9", "H", "2015", {}, None, html.escape, [])
        it2 = SD.Item("SB9", "2015-2016", {"date": "2015-09-16", "body": "H", "type": "floor",
                                           "action": "Uphold Ruling of the Chair", "motion": "MA",
                                           "vote_kind": "RC", "yeas": 286, "nays": 89}, 0)
        it2.rc = {"year": "2015", "body": "H", "number": 999}
        none = BSP.vote_html(it2, "SB9", "H", "2015", {}, None, html.escape, [])
    finally:
        VP._CACHE.pop(src, None)
        if kept is not None:
            VP._CACHE[src] = kept
    if f'<p class="dvh">Uphold the Ruling of the Chair<span class="nbl">{html.escape(rul)}</span>' \
            not in day:
        bad.append(f"the session day does not say the ruling under the appeal: {day[:300]!r}")
    if "nbl" in none or "presiding officer" in none:
        bad.append(f"the session day draws a ruling or a gloss where there is none: {none[:200]!r}")
    # The bill's Votes tab (app.js renderVotes), under node.
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        if bad:
            raise AssertionError("; ".join(bad))
        return "skip", "app.js, dom_stub.js or node is not here; the parser and the session day held"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "rc.json").write_text(json.dumps({
            "question": "Uphold Ruling of the Chair", "mk": "uphold_ruling", "mf": {},
            "date": "2015-09-16", "body": "H", "vote_kind": "DV", "yeas": 286, "nays": 89,
            "passed": True, "ruling": rul}), encoding="utf-8")
        (root / "go.js").write_text(_RULING_VOTES_JS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not draw the Votes tab under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    if '<h2 class="rcq">Uphold the Ruling of the Chair</h2>' not in got["with"] \
            or f'<p class="rcrul">{html.escape(rul, quote=True)}</p>' not in got["with"]:
        bad.append("the bill's Votes tab does not head the appeal plainly with the ruling under it: "
                   + re.sub(r"\s+", " ", got["with"])[:300])
    if "rcrul" in got["without"] or "presiding officer" in got["without"]:
        bad.append("the bill's Votes tab draws a ruling or a gloss where there is none")
    assert not bad, "; ".join(bad)
    return "ok", (f"{len(_NAMED_VOTES)} Journal passages headed by their motion, a member named "
                  f"only where gate 7 named them; {len(_RULINGS)} appeals' rulings said or, where "
                  "the Journal does not say, not; no gloss; the session day, the term's list, the "
                  "member tab and the bill's Votes tab agree")


@check("build", "the House seating diagram lays out exactly 400 seats",
       needs=("seating",))
def _seating(seating):
    """The arithmetic that says the seat numbering was decoded correctly.

    A member's seat number is division * 1000 + seat, and the Clerk's plan
    gives five divisions whose highest seats are 43, 101, 119, 99 and 43. That
    is 405 positions, and no division has a seat 13 -- which brings it to
    exactly the 400 the New Hampshire House has. The agreement with a number
    nobody chose is the evidence the decoding is right, so it is asserted here
    rather than left in a comment to rot.

    Also that no two seats are drawn on top of each other: an overlap in a
    diagram of who sits where does not look like a rendering fault, it hides
    one member behind another.
    """
    floor = sum(len(seating.seats_in(d)) for d in seating.HIGHEST)
    assert floor == 400, f"the diagram lays out {floor} seats; the House has 400"
    pos = seating.layout()
    assert len(pos) == floor + 1, (
        f"{len(pos)} placed, wanted {floor} floor seats plus the Speaker")
    assert seating.SPEAKER_SEAT in pos, "the Speaker's chair is not placed"
    import math as _m
    pts = sorted(pos.items())
    for i, (s1, (x1, y1)) in enumerate(pts):
        for s2, (x2, y2) in pts[i + 1:]:
            assert _m.hypot(x1 - x2, y1 - y2) >= seating.SEAT_R * 1.6, (
                f"seats {s1} and {s2} overlap, which would hide a member")
    # EVERY MEMBER GIVEN A SEAT IS REACHABLE FROM THE CHART. The Speaker's
    # chair is on the rostrum rather than on the floor, and the drawing used
    # to `continue` past it after painting a grey box labelled "Speaker": so
    # the one representative whose seat is 6002 -- Sherman Packard, the 382nd
    # of 382 members holding a seat -- was on the chart as a word and could
    # not be opened from it. A count is what catches that; looking at the
    # picture does not, because the box was there.
    who = {s: {"name": f"Member {s}", "slug": f"m{s}", "party_code": "R"}
           for s in seating.all_seats() + [seating.SPEAKER_SEAT]}
    drawn = seating.svg(who)
    for s in (seating.SPEAKER_SEAT, seating.all_seats()[0], seating.all_seats()[-1]):
        assert f'data-slug="m{s}"' in drawn, (
            f"seat {s} has a member but the chart gives no way to open them")
    assert drawn.count("data-slug=") == len(who), (
        f"{drawn.count('data-slug=')} of {len(who)} seated members are "
        "reachable from the chart")
    return "ok", (f"{floor} seats in {len(seating.HIGHEST)} divisions, none "
                  f"overlapping, all {len(who)} openable")


@check("frontend", "the small things of the audit of 2 October stay fixed: targets, the wordmark, "
                   "pointers, the address of a search, Escape, a player's name, commas and the seat map",
       needs=("build_session_pages", "seating", "build_pages"))
def _audit_minor(BSP, seating, BP):
    """Nine minor findings of the navigation and accessibility audit of
    2 October 2026, each small enough to return unnoticed.

    M1   a person's chip is its link to the edges, and on a phone a control
         whose own rule sets its size is 44px all the same.
    M3   the wordmark is the size of its words: it grew to push the header's
         controls right, and was a 974px link whose ring went round the tabs.
    M10  a pointing hand and a hover only on a ring or a legend row that can
         be pressed: a division's and a sitting day's only show a count.
    M13  opening a long analysis leaves the keyboard at the start of the text.
    M16  a search run with Return is in the address, and an emptied box takes
         it out again; an address that named none is still left alone.
    M17  Escape shuts the phone's filter panel.
    M18  a player's frame is named for the sitting it shows.
    M20  a name and the comma after it are one item of a speaker line.
    M22  the seat map is a group with one Tab stop and arrow keys within it.
    """
    css = _source("src/pages/app.css")
    bare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    js = _source("src/pages/app.js")
    bad = []

    # M1
    chip = re.search(r"\.mchip\{[^}]*padding:([^;}]+)", bare)
    link = re.search(r"\.mchip > a\{padding:([^;}]+);\s*margin:([^;}]+)\}", bare)
    if not (chip and link and link.group(1).split() == chip.group(1).split()):
        bad.append("a chip's link does not take the chip's padding as its own, so only "
                   "the line of the name can be pressed")
    elif re.findall(r"calc\(-1 \* (var\(--sp-\d+\))\)", link.group(2)) != chip.group(1).split():
        bad.append("a chip's link does not give its padding back as margin, so the chip grows")
    phone = re.search(r"ON A PHONE, A CONTROL IS A 44px TARGET.*?@media \(max-width:45em\)\{(.*?)\n\}\n",
                      css, re.S)
    if not phone:
        bad.append("the block that makes a phone's controls 44px is gone")
    else:
        for sel in (".cmbtn", ".calviews button", ".calfold", ".calcat", "#sort",
                    ".bfilt select", ".docket summary", "a.cnum::before", ".offhow a"):
            if not re.search(r"(^|[,\s}])" + re.escape(sel) + r"\s*[,{][^}]*44px", phone.group(1)):
                bad.append(f"{sel} is not held to 44px on a phone")
            base = [m.start() for m in re.finditer(r"(^|\n)" + re.escape(sel) + r"\{", css)]
            if base and max(base) > phone.start(1):
                bad.append(f"{sel}'s own rule comes after the phone block and outranks it")

    # M3
    if re.search(r"nav\.top \.brand\{[^}]*flex:\s*1\b", bare):
        bad.append("the wordmark grows to fill the header again: the link is the width of "
                   "the bar and its focus ring goes round the tabs")

    # M10
    if re.search(r"(^|\})\.lrow\{[^}]*cursor:pointer", bare) or \
            re.search(r"\.donut circle\{[^}]*cursor:pointer", bare):
        bad.append("every legend row or ring segment takes a pointing hand, pressable or not")
    if "button.lrow{cursor:pointer}" not in bare or ".donut circle[data-seg]{cursor:pointer}" not in bare:
        bad.append("a roll call's legend rows and segments, which can be pressed, lost their pointer")

    # M13, M17: read, because both are a key press in a browser.
    an = js[js.find('const an=e.target.closest(".anmore");'):][:1600]
    if "text.focus({preventScroll:true})" not in an or "scrollIntoView" not in an:
        bad.append("\"Show more\" on an analysis leaves focus on a button the text has "
                   "carried off the screen")
    esc_ = js[js.find('if(e.key==="Escape"&&e.target.closest'):][:400]
    if 'closest("#facets,#ftoggle")' not in esc_ or 'classList.remove("fopen")' not in esc_ \
            or "ftb.focus()" not in esc_:
        bad.append("Escape no longer shuts the phone's filter panel and returns to its button")

    # M16, M18: run.
    got = _app_js("""(() => {
      const wrote = []; history.replaceState = (s, t, u) => wrote.push(u);
      location.pathname = "/bills"; location.hash = "";
      const at = (search, q, always) => { location.search = search; wrote.length = 0;
        scope.addressSearch(q, always); return wrote.length ? wrote[0] : null; };
      return {run: at("", "HB 2", true), same: at("?q=HB+2", "HB 2", true),
              typed: at("", "HB 2"), kept: at("?q=budget&sort=recent", "housing"),
              emptied: at("?q=budget&sort=recent", "", true), emptiedOnly: at("?q=budget", ""),
              hearing: scope.renderHearings({id: "HB1", n: "HB 1"}, {stations: [
                {video_id: "abc", state: "whole_video", what: "public hearing",
                 committee: "Finance", body: "H", when: "2025-03-12"}]}),
              title: scope.recTitle("House Finance", "2026-05-05"),
              undated: scope.recTitle("House Finance", "")};
    })()""", names=("addressSearch", "renderHearings", "recTitle"))
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    want = {"run": "/bills?q=HB+2", "same": None, "typed": None,
            "kept": "/bills?q=housing&sort=recent", "emptied": "/bills?sort=recent",
            "emptiedOnly": "/bills"}
    off = [f"{k}: {got.get(k)!r}, not {v!r}" for k, v in want.items() if got.get(k) != v]
    if off:
        bad.append("the address of a search: " + "; ".join(off))
    if 'data-title="Recording of HB 1 - House Finance Public Hearing, Mar 12, 2025"' \
            not in got["hearing"]:
        bad.append("Play on a bill's sitting does not carry the name its player takes")
    if got["title"] != "Recording of House Finance, May 5, 2026" or \
            got["undated"] != "Recording of House Finance":
        bad.append(f"a player is named {got['title']!r} and, undated, {got['undated']!r}")
    # The home page's two players (Recent Session Days, back on 26 October
    # 2026) are named for their chamber and day at build time, and its
    # handler run in _home_says_each_once.
    if 'title="Hearing recording"' in js or 'title="Floor session"' in js:
        bad.append("app.js still gives every player one title")
    if "dataset.title" not in js:
        bad.append("app.js's player does not take its title from the button it replaces")

    # M20
    # Since 10 October 2026 a member the name can mean is the person chip
    # (D14), which needs no comma; a name left as words keeps its own.
    class _M:
        by_slug = {"x": {"label": "Rep. Pat Hunt (R - Hills 1)", "party": "R"}}

        def slug(self, body, name):
            return "x" if name == "Hunt" else ""
    row = BSP.members_row("H", ["Hunt", "Roy", "Muns"], _M(), lambda s: s)
    if row != ('<span class="swho1"><span class="mchip p-R" translate="no"><a href="legislator/x">'
               'Rep. Pat Hunt <span class="mtag">(R - Hills 1)</span></a></span></span> '
               '<span class="swho1"><span>Rep. Roy</span>,</span> '
               '<span class="swho1"><span>Rep. Muns</span></span>'):
        bad.append("a speaker line's names are not each one item with its comma: " + row[:260])
    page = _source(_paths.locate("build_session_pages.py"))
    if re.search(r'", "\.join\(member_html', page):
        bad.append("build_session_pages.py joins members with a bare comma again, which a "
                   "flex row draws as an item of its own with a gap before it")

    # M22
    who = {s: {"name": f"Member {s}", "slug": f"m{s}", "party_code": "R"}
           for s in seating.all_seats() + [seating.SPEAKER_SEAT]}
    drawn = seating.svg(who)
    if 'class="seatmap" role="group" aria-label="' not in drawn:
        bad.append("the seat map is not a labelled group: role=\"img\" promises a screen "
                   "reader no children, and it holds 382 buttons")
    if 'tabindex="0"' in drawn or drawn.count('tabindex="-1" role="button"') != len(who):
        bad.append("a seat is written into the Tab order: 382 stops between the chart's "
                   "controls and the list under it")
    sj = BP.SEATING_JS
    if "stopAt(seats[0])" not in sj or 'e.key==="ArrowRight"' not in sj \
            or 'setAttribute("tabindex",s===c?"0":"-1")' not in sj:
        bad.append("the seat map's script no longer keeps one Tab stop and walks the "
                   "seats with the arrow keys")
    assert not bad, "; ".join(bad[:5])
    return "ok", ("a chip is its link; nine phone controls at 44px; the wordmark does not grow; "
                  "pointers only on what can be pressed; a search run is in the address; a "
                  "player is named for its sitting; a name carries its comma; the seat map is "
                  "one Tab stop")


@check("frontend", "every opener's mark points right while shut and down while open, the journal's "
       "debate among them, and the debate's opening sentences stand while it is shut")
def _openers_turn_right_to_down():
    """The R2 polish batch, 30 October 2026: "every opener turns right to
    down". The House journal's debates ("Debate printed in the permanent
    journal ▸") drew the shared triangle and no rule turned it, so it pointed
    right open and shut; and three openers pointed down while shut and up
    when open -- the Learn pages' and The Data's "On this page" and the
    Resources topics -- where the other eighteen go right to down.

    Here, from app.css: every rule that turns a summary's mark under [open]
    (or a .open class) is read with the rule for the same mark shut, and with
    how the mark is drawn -- the shared triangle (a left border), the
    chevron mask --l-chev and the ▸ glyph point right; a box with only its
    right and bottom borders is a corner pointing down and right -- and the
    mark must point right shut and down open. And every <details> the pages
    write with a mark in its summary has a rule that turns it. The debate's
    opening sentences sit after its fold, so they show while it is shut, and
    hide once it is open."""
    import glob
    css = _source("src/pages/app.css")
    rules = _css_rules(css)
    mark = re.compile(r"(summary\s*::?(?:before|after)|\.caret|\.chev|\.cmcaret)$")
    opened = re.compile(r"\[open\]|\.open\b")

    def norm(sel):
        return re.sub(r"\s*([>+~])\s*", r" \1 ", " ".join(sel.split())).strip()

    def turn(v):
        return sum(float(x) for x in re.findall(r"rotate\((-?[\d.]+)deg\)", v or ""))

    def drawn(parts, cls):
        if cls == ".chev":       # the ▸ glyph in the markup, held below
            return 0
        ds = {}
        for at, sel, body, _line in rules:
            if not at and any(norm(p) in parts for p in sel.split(",")):
                ds.update(dict(_css_decls(body)))
        width = ds.get("border-width", "").split()
        if ("border-right" in ds and "border-bottom" in ds) or (
                len(width) == 4 and width[0] == width[3] == "0" and width[1] != "0" and width[2] != "0"):
            return 45
        if "border-left" in ds or "--l-chev" in ds.get("mask", "") + ds.get("-webkit-mask", ""):
            return 0
        return None

    bad, seen, turned = [], 0, set()
    for at, sel, body, line in rules:
        d = dict(_css_decls(body))
        if "transform" not in d or (at and not all(a.startswith(("@media", "@container")) for a in at)):
            continue
        for part in sel.split(","):
            p = norm(part)
            m = mark.search(p)
            if not opened.search(p) or not m:
                continue
            cls, shut = m.group(1), norm(opened.sub("", p))
            parts = {shut} | ({norm(x) for _a, s0, _b, _l in rules for x in s0.split(",")
                               if not opened.search(x) and norm(x).endswith(cls)
                               and (norm(x).split(" ")[-1] == cls or ":where(" in x)}
                              if cls in (".caret", ".cmcaret") else set())
            base = drawn(parts, cls)
            if base is None:
                bad.append(f"app.css:{line} {p}: no rule says how its mark is drawn")
                continue
            shut_t = 0.0
            for a2, s2, b2, _l2 in rules:
                if not a2 and any(norm(x) == shut for x in s2.split(",")):
                    t2 = dict(_css_decls(b2)).get("transform")
                    if t2:
                        shut_t = turn(t2)
            was, now = (base + shut_t) % 360, (base + turn(d["transform"])) % 360
            seen += 1
            turned.update(re.findall(r"\.([\w-]+)(?:\[open\]|\.open\b)", p))
            if (was, now) != (0, 90):
                bad.append(f"app.css:{line} {p} points {was:g}° shut and {now:g}° open, "
                           "where right (0°) and down (90°) are every opener's")
    # Every <details> written with a mark in its summary has its turn.
    pat = re.compile(r'<details class=\\?"([\w-]+)[^"\\]*\\?"[^>]*>(?:(?!</summary>|<details).){0,900}?'
                     r'class=\\?"(caret|chev|cmcaret)\b', re.S)
    written = set()
    for f in sorted(glob.glob("src/pages/*.py") + glob.glob("src/pages/*.js") + glob.glob("src/pages/*.html")):
        for mm in pat.finditer(Path(f).read_text(encoding="utf-8")):
            written.add((mm.group(1), Path(f).name))
    for x, f in sorted(written):
        if x not in turned:
            bad.append(f"{f} writes <details class=\"{x}\"> with a mark in its summary, and no rule "
                       f"turns it when it is open")
    for f in sorted(glob.glob("src/pages/*.py") + glob.glob("src/pages/*.js") + glob.glob("src/pages/*.html")):
        for mm in re.finditer(r'class=\\?"chev\\?"[^>]*>([^<]{0,12})<', Path(f).read_text(encoding="utf-8")):
            if mm.group(1) not in ("▸", "&#9656;", "${", ""):
                bad.append(f"{Path(f).name}: a .chev draws {mm.group(1)!r}, which this check reads as ▸")
    assert len(written) >= 8 and seen >= 20, (
        f"only {seen} turns and {len(written)} written openers were found; the reading has broken")
    # The journal's debate: its sentences after the fold, shown shut and hidden open.
    import build_session_pages as BSP
    if not re.search(r"\.sdebate\[open\] \+ \.sdopen\{display:none\}", css):
        bad.append("app.css does not hide a debate's opening sentences once it is open")
    # And they are its argument: a title does not end a sentence, and thanks to the chair are
    # passed over (every debate of 14 May 2026 opened "Thank you, Mr. Speaker.…").
    for said, want in (
            ("Thank you, Mr. Speaker. I rise today in opposition of Senate Bill 430 as amended. "
             "Education is not simply about academics. Schools are places of trust.",
             "I rise today in opposition of Senate Bill 430 as amended. Education is not simply about academics."),
            ("Thank you very much, Mr. Speaker. Mr. Speaker, you and I have a lot in common. More than that.",
             "Mr. Speaker, you and I have a lot in common. More than that."),
            ("Thank you, Madam Speaker.", "Thank you, Madam Speaker."),
            ("I rise in support. Thank you, Mr. Speaker.", "I rise in support. Thank you, Mr. Speaker."),
            ("Rep. Smith and Dr. Jones agree. So do I. And so does the committee.",
             "Rep. Smith and Dr. Jones agree. So do I."),
            ("THANK YOU, MR. SPEAKER. I RISE IN SUPPORT. IT IS SOUND. MORE.", "I RISE IN SUPPORT. IT IS SOUND."),
            ("Thank you, Mr Speaker. Gov. Ayotte signed it. We should too.", "Gov. Ayotte signed it. We should too.")):
        if BSP.debate_opening(said) != want:
            bad.append(f"a debate opening {said[:40]!r} reads {BSP.debate_opening(said)!r}")
    page = BSP._debate_html({"bill": "HB1", "speeches": [
        ("Rep. Wade", "Thank you, Mr. Speaker. I rise in support of the committee report. It is sound.")]},
        "H", BSP.Members(Path("no-such-site")), __import__("html").escape)
    if not page.endswith('</details><p class="sdopen">I rise in support of the committee report. It is sound.</p>'):
        bad.append(f"a debate's opening is not after its fold, in its own words: {page[-160:]!r}")
    empty = BSP._debate_html({"bill": "HB1", "speeches": [("Rep. Wade", "")]}, "H",
                             BSP.Members(Path("no-such-site")), __import__("html").escape)
    if "sdopen" in empty:
        bad.append("a debate whose first speech is empty shows a bare ellipsis under its fold")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"{seen} turns of a summary's mark, each right to down; {len(written)} openers the "
                  "pages write, each turned; the debate's opening stands while it is shut")


@check("session", "a member a Journal names is given the site's member id, the PersonID where "
       "the record has one, never careers.json's Employeeno key", needs=("journal_motions",))
def _journal_member_site_id(JM):
    """journal_motions.resolve_member returned careers.json's key, an
    Employeeno, as the site's member id (30 October 2026): all 25 it named on
    the kit were numbers no member page answers to. The site's id is the
    PersonID where the record has one, else the Employeeno."""
    careers = {
        "376171": {"named": True, "first": "Steve", "last": "Vaillancourt", "person_id": "453",
                   "by_term": {"2011-2012": {"chambers": ["H"]}}},
        "408864": {"named": True, "first": "Wendy", "last": "Thomas", "person_id": "",
                   "by_term": {"2023-2024": {"chambers": ["H"]}}},
        "377001": {"named": True, "first": "Pat", "last": "Long", "person_id": "700",
                   "by_term": {"2023-2024": {"chambers": ["H"]}}},
        "377002": {"named": True, "first": "Patricia", "last": "Long", "person_id": "701",
                   "by_term": {"2023-2024": {"chambers": ["H"]}}},
        "218745": {"named": True, "first": "Bill", "last": "Gannon", "person_id": "8745",
                   "by_term": {"2023-2024": {"chambers": ["S"]}}},
    }
    got = {
        "a PersonID": JM.resolve_member("Vaillancourt", "H", "2011-2012", careers),
        "no PersonID": JM.resolve_member("Wendy Thomas", "H", "2023-2024", careers),
        "two of the name": JM.resolve_member("Long", "H", "2023-2024", careers),
        "by first name": JM.resolve_member("Patricia Long", "H", "2023-2024", careers),
        "another chamber": JM.resolve_member("Gannon", "H", "2023-2024", careers),
        "a senator": JM.resolve_member("Gannon", "S", "2023-2024", careers),
    }
    want = {"a PersonID": "453", "no PersonID": "408864", "two of the name": "",
            "by first name": "701", "another chamber": "", "a senator": "8745"}
    assert got == want, f"resolve_member gave {got}, not {want}"
    return "ok", "the PersonID where there is one, the Employeeno where not, and nobody when two fit"


@check("session", "a surname on a session day links to the one member serving that term who bears it, "
                   "never to a member who had left, and never where two serving members share it",
       needs=("build_session_pages",))
def _surname_links_serving_members(BSP):
    """The person, 9 October 2026, of the House's 19 August 2026 excused list:
    Rep. Daniels, Dunn, Rice and Turcotte had no link, because former members
    who left years before share each surname (Members: ONLY THE MEMBERS WHO
    SERVED THAT TERM COUNT). Built on a small site: a sitting Kimberly Rice, a
    former Thomas Rice of 1999-2000 only, and two sitting Smiths."""
    import proceedings as PR
    root = Path(tempfile.mkdtemp(prefix="gr-surnames-"))
    try:
        (root / "legislators.json").write_text(json.dumps([
            {"slug": "kimberly-rice", "name": "Rice, Kimberly", "chamber": "H"},
            {"slug": "a-smith", "name": "Smith, Anne", "chamber": "H"},
            {"slug": "b-smith", "name": "Smith, Bob", "chamber": "H"},
            {"slug": "mark-pearson-rock-34", "name": "Pearson, Mark", "chamber": "H"}]),
            encoding="utf-8")
        (root / "former.json").write_text(json.dumps([
            {"slug": "thomas-rice", "name": "Rice, Thomas", "chamber": "H",
             "served": {"terms": ["1999-2000", "2001-2002"]}},
            {"slug": "mark-pearson-rock-4", "name": "Pearson, Mark", "chamber": "H",
             "served": {"terms": ["2007-2008"]}}]), encoding="utf-8")
        m = BSP.Members(root)
        got, pearson = {}, {}
        for term in ("2025-2026", "1999-2000", "2007-2008", ""):
            m.term = term
            got[term] = (m.slug("H", "Rice"), m.slug("H", "Smith"), m.slug("H", "Kimberly Rice"))
            pearson[term] = m.slug("H", "Mark Pearson")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    bad = []
    if got["2025-2026"] != ("kimberly-rice", None, "kimberly-rice"):
        bad.append(f"in 2025-2026 Rice, Smith and Kimberly Rice link to {got['2025-2026']}, not "
                   "the sitting Kimberly Rice, nobody, and Kimberly Rice")
    if got["1999-2000"][0] is not None or got["1999-2000"][1] is not None:
        bad.append(f"in 1999-2000, when a Rice who has since left also served, Rice links to "
                   f"{got['1999-2000'][0]!r}: two serving members bear it, so it must stay unlinked")
    if got[""][0] is not None:
        bad.append("with no term set Rice links, which is the old all-time match changed silently")
    # A FULL NAME too: the live site sent every 2026 "Rep. Mark Pearson" to the
    # Mark Pearson of 2007-2008.
    if pearson["2025-2026"] != "mark-pearson-rock-34" or pearson["2007-2008"] is not None:
        bad.append(f"Mark Pearson links to {pearson['2025-2026']!r} in 2025-2026 and "
                   f"{pearson['2007-2008']!r} in 2007-2008, not the sitting member and nobody")
    # Organization Day belongs to the next term, as everywhere else.
    if PR.vote_term("2026", "2026-12-02") != "2027-2028" or PR.vote_term("2026", "2026-08-19") != "2025-2026":
        bad.append("a session day's term is not its biennium's (Organization Day the next term's)")
    src = Path(_paths.locate("build_session_pages.py")).read_text(encoding="utf-8")
    if "members.term = proceedings.vote_term(" not in src:
        bad.append("the day loop no longer sets the day's term before drawing names")
    assert not bad, "; ".join(bad)
    return "ok", ("a surname links only among the members serving that day's term: the sitting "
                  "Rice in 2026, nobody where two serving members share it")


@check("session", "a vote's date leads to that chamber's sitting where the sitting has a page, and nowhere else",
       needs=("build_session_pages",))
def _sitting_links(BSP):
    """The audit of 2 October 2026, B3: a past sitting could be reached only
    from the sitting next to it. A roll call on a bill and a row of a member's
    votes name the day and the chamber and did not link it.

    app.js links the date now, and only to a page that was built: it asks
    session/days.json, which build_session_pages.py writes from the pages it
    wrote. Held here, in node against dom_stub.js: before the list lands a
    date is text and the list is asked for once; a day on the list is a link
    to session/<body>/<date>; a day that is not on it, or the other chamber's,
    stays text; and a member's row reads its chamber out of the vote's key
    and its day out of the m/d/yyyy the roll call file carries.

    AT THE BILL, WITH NO ".html" (the audit of 25 October 2026, M1): the
    date opened the day's top, and HB 282 was some 36,700px below it on a
    phone. A vote on a bill links the bill's card, "#HB282", the id
    build_session_pages.card_anchor gives it (held to it here), and the
    address is the page's own, not the one a redirect turns it into.

    NO ANCHOR NO PAGE HAS (the preview check of 25 October 2026): the House's
    two votes on Rule 64 of 8 January 2025 are filed under "HRULE64" with no
    bill, and their dates linked "#HRULE64", which no card is; their row
    said "HRULE64" where the Journal says what they were, and the link to
    their own "#rc-<key>" went only to a vote filed under nothing. And
    "#rc-<key>" was linked wherever the Journal described a vote, though a
    page gives that id only to a roll call it draws on no bill: 2022-H-4 and
    -5 are drawn on HB 50's card on 5 January 2022, and their links opened
    the day at its top. Held here: a vote on a code links its day bare, or at
    "#rc-<key>" where days.json's `rc` says that day's page carries it, and
    says the Journal's words before the code; a vote the Journal describes
    links its words only where `rc` names a page for it, and at that page's
    day where the file dates it on another; and the builder lists each
    chamber's roll calls with its days, the other chamber's kept, read off
    the ids the pages carry (rollcall_ids).

    And the builder's half, without a build: the days a page is written for
    are the days up to today and no later; the list of them is written a
    chamber at a time and the other chamber's is kept (a writer run on a
    subset destroys the rest); a page leads up to its chamber's list, and to
    its week only where it is handed that week.
    """
    built, later = BSP.sittings({("H", "2026-05-21"): 1, ("S", "2026-05-14"): 1,
                                 ("H", "2026-12-31"): 1}, today="2026-10-02")
    assert built == [("H", "2026-05-21"), ("S", "2026-05-14")] and \
        later == [("H", "2026-12-31")], (
        f"sittings() builds {built} and holds back {later}: a sitting after "
        "the build is not a day to publish")
    root = Path(tempfile.mkdtemp())
    try:
        (root / "session").mkdir()
        BSP.write_days_index(root, "S", ["2026-05-14"], {"2026-S-9": "2026-05-14"})
        BSP.write_days_index(root, "H", ["2026-05-21", "2025-01-08"],
                             {"2025-H-2": "2025-01-08", "2025-H-1": "2025-01-08"})
        BSP.write_days_index(root, "S", ["2026-05-14", "2026-06-04"], {"2026-S-12": "2026-06-04"})
        got = json.loads((root / "session" / "days.json").read_text(encoding="utf-8"))
        assert got == {"H": ["2025-01-08", "2026-05-21"],
                       "S": ["2026-05-14", "2026-06-04"],
                       "rc": {"H": {"2025-H-1": "2025-01-08", "2025-H-2": "2025-01-08"},
                              "S": {"2026-S-12": "2026-06-04"}}}, (
            f"session/days.json, written a chamber at a time, holds {got}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # The ids read off a page are the roll calls it anchors, not the links to
    # one, nor a Journal-only vote's "jv-".
    page_ids = BSP.rollcall_ids('<div class="dvote nbvote" id="rc-2025-H-1" data-motion="x">'
                                '<a href="#rc-2025-H-9">x</a><div class="dvote" id="jv-2026-03-06-H-d1">'
                                '<div class="dvote" id="rc-2025-H-2" data-motion="">')
    assert page_ids == ["2025-H-1", "2025-H-2"], (
        f"build_session_pages.rollcall_ids reads {page_ids} off a page anchoring 2025-H-1 and -2")

    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "app.js, dom_stub.js or node is not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
const asked = [];
// 2026-05-20 has a page too, so that a roll call the file dates then and the
// 21st's page draws (2026-H-4) tests the date's own guard: its date is the
// 20th bare, never "#rc-" at a page that lacks it (the preview check of 25
// October 2026: 2009-H-89 is filed 8 April 2009 and drawn on 26 March, and
// both days have pages).
globalThis.fetch = async u => { asked.push(String(u)); return {ok: true, status: 200,
  json: async () => String(u).endsWith("session/days.json")
    ? {H: ["2026-05-20", "2026-05-21"], S: ["2026-05-14"],
       rc: {H: {"2026-H-1": "2026-05-21", "2026-H-4": "2026-05-21", "2026-H-5": "2026-05-21",
                "2026-H-6": "2026-05-22"}, S: {}}} : [], text: async () => "[]"}; };
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({sittingLink, voteIso, voteChamber, renderVotes, voteRow})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
(async () => {
  const out = {};
  const before = asked.filter(u => u.endsWith("session/days.json")).length;
  out.early = s.sittingLink("H", "2026-05-21", "May 21, 2026");
  s.sittingLink("H", "2026-05-21", "x"); s.sittingLink("S", "2026-05-14", "x");
  out.asked = asked.filter(u => u.endsWith("session/days.json")).length - before;
  for (let i = 0; i < 20; i++) await null;
  out.link = s.sittingLink("H", "2026-05-21", "May 21, 2026");
  out.other = s.sittingLink("S", "2026-05-21", "May 21, 2026");
  out.absent = s.sittingLink("H", "2026-05-22", "May 22, 2026");
  out.none = s.sittingLink("", "", "no date");
  out.iso = [s.voteIso({d: "8/19/2026"}), s.voteIso({d: "12/3/2025"}), s.voteIso({d: ""}),
             s.voteIso({d: "2026-08-19"})];
  out.ch = [s.voteChamber({k: "2026-H-302"}), s.voteChamber({k: "2026-S-7"}), s.voteChamber({})];
  out.rc = s.renderVotes({id: "HB1"}, {rollcalls: [{question: "Ought to Pass",
    date: "2026-05-21", body: "H", vote_kind: "VV", passed: true}]});
  out.row = s.voteRow({x: {d: "5/14/2026", b: "", q: "Adopt", v: "Yea", k: "2026-S-7",
    y: "2026"}, rc: null, b: null, mark: null, ch: ""});
  out.rowBill = s.voteRow({x: {d: "5/14/2026", b: "HB1442", q: "Adopt", v: "Yea", k: "2026-S-7",
    y: "2026"}, rc: null, b: null, mark: null, ch: ""});
  out.anchor = s.sittingLink("H", "2026-05-21", "x", "cacr 13");
  out.rowOff = s.voteRow({x: {d: "5/15/2026", b: "", q: "Adopt", v: "Yea", k: "2026-S-8",
    y: "2026"}, rc: null, b: null, mark: null, ch: ""});
  // NO ANCHOR NO PAGE HAS: a vote filed under a rule's code, which the day
  // draws at its own id, with the Journal's words and without; a vote on no
  // bill the day draws on a bill's card (no rc- id), one the next day's page
  // draws though the file's day has a page of its own, one listed at a day
  // with no page, and one on a bill the day draws as a vote of its own.
  const w = (k, d, b, y, words) => s.voteRow({x: {d, b, q: "Adopt", v: "Yea", k, y},
    rc: words === null ? null : {y: 216, n: 164, p: 1, pr: 1, q: "", w: words},
    b: null, mark: null, ch: ""});
  out.rule = w("2026-H-1", "5/21/2026", "HRULE64", "", "Adopt a floor amendment to House Rule 64");
  out.code = w("2026-H-2", "5/21/2026", "HR", "", null);
  out.onCard = w("2026-H-3", "5/21/2026", "", "", "Lay on the Table");
  out.moved = w("2026-H-4", "5/20/2026", "", "", "Reconsider");
  out.stale = w("2026-H-6", "5/21/2026", "", "", "Recess");
  out.plain = w("2026-H-5", "5/21/2026", "SB457", "2026", null);
  process.stdout.write("\\n@@" + JSON.stringify(out));
})();
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not run under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert got["early"] == "May 21, 2026", (
        "before the list of sittings has landed a date is drawn as a link: " + got["early"])
    assert got["asked"] == 1, (
        f"session/days.json was asked for {got['asked']} times by three dates, not once")
    assert got["link"] == '<a href="session/H/2026-05-21">May 21, 2026</a>', (
        "a day the House sat, with a page, is drawn as: " + got["link"])
    for k in ("other", "absent", "none"):
        assert "<a" not in got[k], (
            f"a date with no sitting page behind it is a link ({k}): {got[k]}")
    assert got["iso"] == ["2026-08-19", "2025-12-03", "", ""] and got["ch"] == ["H", "S", ""], (
        f"a member's vote reads as day {got['iso']} and chamber {got['ch']}")
    # The card's id as the sitting page gives it, from the builder itself.
    assert BSP.card_anchor("HB1", set()) == "HB1" and BSP.card_anchor("cacr 13", set()) == "CACR13", (
        "build_session_pages.card_anchor no longer gives a card the bill's number upper-cased "
        "with anything else dropped, which app.js's sittingLink writes after the #")
    assert '<a href="session/H/2026-05-21#HB1">May 21, 2026</a>' in got["rc"], (
        "a roll call on a bill does not link its day to the bill on the sitting's page")
    assert '<a href="session/S/2026-05-14">May 14, 2026</a>' in got["row"], (
        "a row of a member's votes on no bill does not link its day to the sitting")
    assert '<a href="session/S/2026-05-14#HB1442">May 14, 2026</a>' in got["rowBill"], (
        "a row of a member's votes on a bill does not link its day to the bill on the sitting's page")
    assert got["anchor"] == '<a href="session/H/2026-05-21#CACR13">x</a>', (
        "a bill's number is not written as the card's id after the #: " + got["anchor"])
    sat = re.findall(r'href="(session/[^"]*)"', got["rc"] + got["row"] + got["rowBill"])
    assert sat and not [h for h in sat if ".html" in h], (
        f"a vote's date links the sitting's .html, which costs a redirect: {sat}")
    assert "session/" not in got["rowOff"] and "May 15, 2026" in got["rowOff"], (
        "a row of a member's votes links a day with no sitting page")
    # NO ANCHOR NO PAGE HAS.
    rows = {k: got[k] for k in ("rule", "code", "onCard", "moved", "stale", "plain")}
    dates = {k: re.search(r'<td class="d"[^>]*>(.*?)</td>', v, re.S).group(1) for k, v in rows.items()}
    links = {k: re.findall(r'<a class="nbwa" href="([^"]*)"', v) for k, v in rows.items()}
    bad = []
    if not dates["rule"].startswith('<a href="session/H/2026-05-21#rc-2026-H-1">May 21, 2026</a>'):
        bad.append(f"a vote on House Rule 64 the day draws at rc-2026-H-1 dates as {dates['rule']}")
    if not dates["code"].startswith('<a href="session/H/2026-05-21">May 21, 2026</a>'):
        bad.append(f"a vote filed under the code HR dates as {dates['code']}, not the bare day")
    if re.search(r"#(HRULE64|HR)\b", rows["rule"] + rows["code"]):
        bad.append("a vote filed under a rule's code links its code as a card's id")
    if links["rule"] != ["session/H/2026-05-21#rc-2026-H-1"] or \
            "Adopt a floor amendment to House Rule 64</span>" not in rows["rule"]:
        bad.append("a vote on House Rule 64 the Journal describes does not say so, linked to its "
                   f"roll call: {links['rule']}")
    if links["onCard"] or "#rc-" in rows["onCard"] or \
            '<span class="nbw">Lay on the Table</span>' not in rows["onCard"]:
        bad.append("a vote on no bill the day draws on a bill's card links an rc- id the page "
                   f"does not carry: {links['onCard']}")
    # The date links its own day bare, and the words the day that draws it:
    # "#rc-" on the date only where the date's own page carries the id. The
    # 20th has a page, so a date that skipped that test would link
    # session/H/2026-05-20#rc-2026-H-4, an id that page lacks (2009-H-89 on
    # 8 April 2009, the preview check of 25 October 2026).
    if links["moved"] != ["session/H/2026-05-21#rc-2026-H-4"] or \
            dates["moved"] != '<a href="session/H/2026-05-20">May 20, 2026</a>':
        bad.append("a vote on no bill the file dates the 20th and the 21st's page draws is not "
                   "linked at the 21st, or its date is not the 20th's page bare: "
                   f"{links['moved']}, {dates['moved']}")
    if links["stale"] or "#rc-" in rows["stale"]:
        bad.append(f"a vote listed at a day with no page links it: {links['stale']}")
    if not dates["plain"].startswith('<a href="session/H/2026-05-21#rc-2026-H-5">'):
        bad.append("a vote on a bill the day draws as a vote of its own does not date at it: "
                   + dates["plain"])
    assert not bad, "; ".join(bad)
    return "ok", ("a date is a link to session/<body>/<date> where days.json lists the day, "
                  "text otherwise, at the bill's card where the vote is on one and at the roll "
                  "call's own id where days.json says a page carries it, never at a code or an "
                  "id the page lacks; the list is asked once; pages are built up to "
                  "today, the list is merged a chamber at a time, and a page leads up to "
                  "its list and to its week only where the calendar has it")


@check("session", "a sitting page links each bill to its own term's bill",
       needs=("build_session_pages", "session_days", "shell"))
def _session_bill_term(BSP, SD, shell):
    """73,268 of the 79,508 bill links on the sitting pages went to a bill
    of another term, and printed that other bill's title.

    The titles and years were keyed on the bill number alone, and a number
    starts again every two years, so whichever term's index was read last
    owned it: the House page for 9 March 2016 linked HB 1102 to the 2026 bill
    of that number and printed "increasing the research and development tax
    credit cap", and 3,688 of 4,207 House "who voted which way" pointers
    reached the wrong bill's roll calls. The fixture below holds the same
    number in two terms, with different years and titles, on all three kinds
    of link the page writes -- the bill's heading, its consent-calendar line
    and the roll call pointer -- plus a bill its term's index does not hold,
    which must get no link rather than someone else's.
    """
    root = Path(tempfile.mkdtemp())
    try:
        idx = root / "site" / "idx"
        idx.mkdir(parents=True)
        (idx / "2015-2016.json").write_text(json.dumps([
            {"id": "HB1102", "term": "2015-2016", "year": 2016,
             "title": "relative to the 2016 bill"},
            {"id": "HB1300", "term": "2015-2016", "year": 2016,
             "title": "relative to a consent item"},
            {"id": "HR1", "term": "2015-2016", "year": 2015,
             "title": "the older resolution"}]), encoding="utf-8")
        (idx / "2025-2026.json").write_text(json.dumps([
            {"id": "HB1102", "term": "2025-2026", "year": 2026,
             "title": "increasing the research and development tax credit cap"},
            {"id": "HB1300", "term": "2025-2026", "year": 2026,
             "title": "a 2026 bill of the same number"},
            {"id": "HR1", "term": "2025-2026", "year": 2025,
             "title": "the newer resolution"},
            {"id": "HB9999", "term": "2025-2026", "year": 2026,
             "title": "held by the other term only"}]), encoding="utf-8")
        titles, years = BSP.load_titles(root / "site")

        def item(bill, term, seq, **e):
            ev = {"type": "floor", "body": "H", "action": "Ought to Pass",
                  "motion": "MA", "raw": "Ought to Pass: MA"}
            ev.update(e)
            return SD.Item(bill, term, ev, seq)

        rc = item("HB1102", "2015-2016", 1, vote_kind="RC", yeas="200",
                  nays="150", cite_page="10")
        # the roll call on record it is: a motion the docket alone states has
        # no ballots anywhere, and no pointer
        rc.rc = {"year": "2016", "body": "H", "number": 1, "bill": "HB1102",
                 "yeas": 200, "nays": 150}
        cons = item("HB1300", "2015-2016", 2, vote_kind="VV", cite_page="11")
        cons.consent = True
        gone = item("HB9999", "2015-2016", 3, vote_kind="VV", cite_page="12")
        day = SD.Day("H", "2016-03-09", [rc, cons, gone])
        blank = {"attributions": [], "debates": [], "unanimous_consent": []}
        html, _ = BSP.render(day, blank, titles, years,
                             BSP.Members(root / "site"), shell.E)
        hrefs = re.findall(r'href="(bill/[^"]+)"', html)
        assert hrefs, "the fixture day wrote no bill link at all"
        wrong = [h for h in hrefs if not h.startswith("bill/2016/")]
        assert not wrong, ("a 2016 sitting links to another term's bill: "
                           + ", ".join(wrong))
        # The card's number is HB 1102's one link since 10 October 2026: its
        # roll call is drawn with the Votes tab's own display, where a line
        # pointed at the bill's page (v2: no new link).
        assert hrefs.count("bill/2016/hb1102.html") == 1, (
            "HB 1102's card should reach bill/2016/hb1102.html, once; "
            f"the links are {hrefs}")
        assert 'class="brnum" href="bill/2016/hb1300.html"' in html, (
            "the consent-calendar line does not reach the 2016 HB 1300")
        assert "relative to the 2016 bill" in html and \
            "research and development" not in html and \
            "a 2026 bill of the same number" not in html, (
            "the page prints another term's title beside a 2016 bill")
        assert "/bills#" not in html and "hb9999" not in html, (
            "a bill its own term's index does not hold was linked anyway; "
            "it must be printed without a link")
        assert '<span class="cnum" translate="no">HB 9999</span>' in html, (
            "the unindexed bill's number is not printed as plain text")

        # One number from two terms on one day is two bills: the House
        # organization day of 1 December 2004 took up HR 1 of both terms.
        a = item("HR1", "2015-2016", 4, cite_page="1")
        b = item("HR1", "2025-2026", 5, cite_page="2")
        two = SD.Day("H", "2016-12-07", [a, b])
        assert len(two.bills) == 2, "two terms' HR 1 counted as one bill"
        html2, _ = BSP.render(two, blank, titles, years,
                              BSP.Members(root / "site"), shell.E)
        assert html2.count('<article class="card"') == 2 and \
            "bill/2015/hr1.html" in html2 and "bill/2025/hr1.html" in html2, (
            "HR 1 of two terms was drawn as one card, or linked to one term")
        return "ok", ("heading, consent line and roll call pointer all reach "
                      "the sitting's own term; an unindexed bill is not "
                      "linked; one number from two terms is two cards")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _day_index_faults(page, where, own):
    """What is wrong with one built session day's sidebar and index
    (_session_day_index): [] where nothing is. `own` is the page's address,
    "session/H/2026-03-06": every page carries <base href="/">, so the index
    links a place on the page by it, and a bare "#hb1442" would go home."""
    from html import unescape
    bad = []
    to = r'href="' + re.escape(own) + r'(?:\.html)?#([^"]+)"'
    if "move this player" in page or 'class="tolnote"' in page:
        bad.append(f"{where}: the sentence under the player is back")
    m = re.search(r'<section class="w4 wday" id="order"><div class="wside">(.*?)</div><div class="w4b">',
                  page, re.S)
    if not m:
        return bad + [f"{where}: the Day in Order has no sidebar holding its heading"]
    side = m.group(1)
    if not side.startswith('<h2 class="w4h">'):
        bad.append(f"{where}: the sidebar does not open with the section's heading")
    if 'class="player"' in page and 'class="player"' not in side:
        bad.append(f"{where}: the day's player is not in the sidebar")
    nav = re.search(r'<nav class="dayidx" id="dayidx" aria-label="On this page"><details class="difold">'
                    r'<summary>.*?</summary><ol class="dilist">(.*)</ol></details></nav>$', side, re.S)
    if not nav:
        return bad + [f"{where}: the sidebar has no index, or it is not a labelled nav ending it"]
    lst = nav.group(1)
    ids = set(re.findall(r'\bid="([^"]+)"', page))
    hrefs = re.findall(r'href="([^"]*)"', lst)
    if len(re.findall(to, lst)) != len(hrefs):
        bad.append(f"{where}: the index links somewhere other than a place on its own page: "
                   + ", ".join(h for h in hrefs if not re.fullmatch(to[6:-1], h))[:200])
    for href in re.findall(to, lst):
        if href not in ids:
            bad.append(f"{where}: the index links #{href}, which nothing on the page is")
    # THE SECTIONS, each once, in the page's order and in its heading's words.
    secs = [(i, unescape(h)) for i, h in re.findall(
        r'<section class="w4(?: wday)?" id="([^"]+)">(?:<div class="wside">)?<h2 class="w4h">([^<]+)</h2>',
        page)]
    tops = [(i, unescape(h)) for i, h in re.findall(r'(?:^|</li>)<li><a ' + to + r'>([^<]+)</a>', lst)]
    if tops != secs:
        bad.append(f"{where}: the index's sections {tops} are not the page's {secs}")
    # ONE LINE A BILL, in the order of the bills' first cards, each linking
    # its first card and saying what one of its cards' vote chips says.
    cards = re.findall(r'<article class="card[^"]*" id="([^"]+)"( data-at="[^"]+")? data-id="[^"]+">(.*?)</article>',
                       page, re.S)
    chips = {}
    for cid, at, body in cards:
        key = at[10:-1] if at else cid
        chips[key] = chips.get(key, []) + [unescape(t) for t in re.findall(r'<span class="chip rcres (?:pass|fail)">([^<]+)</span>', body)]
    firsts = [cid for cid, at, _b in cards if not at]
    bills = re.search(r'<ol class="dibills">(.*?)</ol>', lst, re.S)
    lines = re.findall(r'<li><a ' + to + r'><span class="dinum" translate="no">([^<]+)</span>'
                       r'(?: <span class="chip dichip [^"]+">([^<]+)</span>)?</a></li>',
                       bills.group(1) if bills else "")
    if [a for a, _n, _w in lines] != firsts:
        bad.append(f"{where}: the index's bills {[a for a, _n, _w in lines]} are not the cards' {firsts}")
    for a, _n, w in lines:
        said = set()
        for t in chips.get(a, []):
            tail = t.split(": ", 1)[1] if ": " in t else t
            said |= {tail, tail.split(" ", 1)[-1]}
        w = unescape(w or "")
        if (w or said) and w not in said:
            bad.append(f"{where}: #{a}'s line says {w!r}, which none of its card's chips "
                       f"({chips.get(a)}) says")
    return bad


@check("session", "a session day's heading, player and index stand in a sidebar held beside the cards: "
       "each section, then a line a bill in the day's order linking its card and saying its "
       "card's outcome (the owner, 24 October 2026)",
       needs=("build_session_pages", "session_days", "shell"))
def _session_day_index(BSP, SD, shell):
    """THE DAY'S INDEX (the owner, 24 October 2026: "On session day pages, it
    would be nice to have some sort of index on the left side below the video
    for each action and bill so you can more quickly look for the bill you're
    trying to find. It could be something brief for each bill like just the
    number and the vote outcome of whether it passed or not along with other
    section titles like how the day began, excused for the day, unanimous
    consent, and so on. The header above the embedded video player 'The Day
    in Order' should also remain on the sidebar as you scroll down. You can
    remove the sentence below the video player: 'the times on the cards move
    this player'.")

    On every session day the fixture's site builds, it fails if the Day in
    Order's heading and player are not in one sidebar with the index; if the
    index is not a labelled nav; if its sections are not the page's, in their
    order and words; if it does not give one line a bill in the order of the
    bills' first cards, each linking an id the page has; if a line's word is
    not one a vote chip on that bill's cards says; or if the sentence under
    the player is back. It fails if the stylesheet no longer holds the
    sidebar in view on a wide screen, or app.js no longer opens the index
    there and marks the line being read.

    And on a day made here, where the record is known, it fails if a bill
    whose Inexpedient to Legislate failed before its Ought to Pass carried,
    and whose reconsideration then failed, is said other than "Passed"; if a
    killed bill is said "Passed" (the motion passing is not the bill
    passing); or if a bill tabled and later taken off the table and passed,
    in two cards, has two lines, or its one line says other than its last
    outcome of the day."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    pages = sorted((shared / "site" / "session").glob("[HS]/*.html"))
    bad, drawn, with_player = [], 0, 0
    for p in pages:
        text = p.read_text(encoding="utf-8")
        if '<section class="w4 wday"' not in text:
            continue
        drawn += 1
        with_player += 'class="player"' in text
        rel = p.relative_to(shared / "site").as_posix()
        bad += _day_index_faults(text, rel, rel[:-len(".html")])
    assert drawn >= 3 and with_player, (
        f"the fixture's site drew {drawn} days in order, {with_player} with a player: too few to hold")
    css = _source("src/pages/app.css")
    wide = re.search(r"@media \(min-width:60em\)\{[^@]*?\.wday > \.wside\{[^}]*position:sticky", css)
    if not wide:
        bad.append("app.css no longer holds the sidebar (.wday > .wside) in view on a wide screen")
    if not re.search(r"\.wday > \.wside\{display:contents\}", css):
        bad.append("app.css no longer undoes the sidebar on a phone, so its index cannot be held "
                   "at the top of the screen")
    js = _source("src/pages/app.js")
    hook = js[js.find('getElementById("dayidx")'):][:3000]
    if not hook or "fold.open=true" not in hook or 'setAttribute("aria-current","location")' not in hook:
        bad.append("app.js no longer opens the day's index on a wide screen and marks the line being read")

    # A DAY MADE HERE, where what the card should say is known.
    def item(bill, seq, action, motion):
        return SD.Item(bill, "2025-2026", {"type": "floor", "body": "H", "action": action,
                                           "motion": motion, "vote_kind": "VV",
                                           "raw": f"{action}: {motion}",
                                           "cite_page": str(10 + seq)}, seq)

    class Nobody:
        def slug(self, body, name):
            return None
    day = SD.Day("H", "2026-03-11", [
        item("HB1", 1, "Inexpedient to Legislate", "MF"), item("HB1", 2, "Ought to Pass", "MA"),
        item("HB1", 3, "Reconsider", "MF"), item("HB2", 4, "Inexpedient to Legislate", "MA"),
        item("HB3", 5, "Lay on the Table", "MA"), item("HB4", 6, "Interim Study", "MA"),
        item("HB3", 7, "Remove from the Table", "MA"),
        item("HB3", 8, "Ought to Pass with Amendment", "MA")])
    told = {"attributions": [], "debates": [],
            "unanimous_consent": [{"name": "Rep. Hill", "about": "the flood in Keene"}]}
    page, _ = BSP.render(day, told, {}, {}, Nobody(), shell.E)
    bad += _day_index_faults(page, "the day made here", "session/H/2026-03-11")
    got = re.findall(r'<li><a href="session/H/2026-03-11\.html#([^"]+)"><span class="dinum" translate="no">([^<]+)</span> '
                     r'<span class="chip dichip ([^"]+)">([^<]+)</span>', page)
    want = [("HB1", "HB 1", "s-law", "Passed"), ("HB2", "HB 2", "s-done", "Killed"),
            ("HB3", "HB 3", "pass", "Passed with Changes"),
            ("HB4", "HB 4", "s-study", "Sent to Interim Study")]
    if got != want:
        bad.append(f"the day made here is indexed {got}, where it should be {want}")
    if '<article class="card" id="HB3-2" data-at="HB3" data-id="HB3">' not in page:
        bad.append("HB 3's second card of the day does not name its first (data-at)")
    if '<li><a href="session/H/2026-03-11.html#consent-uc">Under Unanimous Consent</a></li>' \
            not in page or \
            'class="player"' in page:
        bad.append("the day made here, with no recording, does not index its unanimous consent")
    assert not bad, f"{len(bad)} faults in the session days' index: " + "; ".join(bad[:6])
    return "ok", (f"{drawn} fixture days ({with_player} with a player) and one made here: heading, "
                  "player and index in the sidebar, held in view; each section and a line a bill, "
                  "each saying what its card says")


# A vote's parts on a session day's card, in the order the owner asked for
# (24 October 2026): the head, the count's line, the mover, the speakers,
# the ring, the notes, and the clerk's words.
CARD_VOTE_ORDER = ("dvh", "dvr", "dvby", "sspoke", "svote", "swho", "rcrec")


def _card_faults(page, where, BSP):
    """What is out of place on a built session day's bill cards
    (_session_card_order): [] where nothing is."""
    bad = []
    for card in re.findall(r'<article class="card[^"]*"[^>]*>.*?</article>', page, re.S):
        cid = re.search(r'data-id="([^"]+)"', card).group(1)
        rail, well = card.find('<span class="rail dated'), card.find('<div class="cline">')
        if rail != -1 and (well == -1 or rail > well):
            bad.append(f"{where} {cid}: the rail is drawn under the day's votes")
        if "In the record:" in card:
            bad.append(f"{where} {cid}: a bill's vote is still headed \"In the record\"")
        for v in re.findall(r'<div class="dvote"[^>]*>(.*?)(?=<div class="dvote"|<p class="dsum"|'
                            r'<details class="sdebate"|<p class="sspoke sother"|$)', card, re.S):
            seen = re.findall(r'class="(' + "|".join(CARD_VOTE_ORDER) + r')"', v)
            ranks = [CARD_VOTE_ORDER.index(c) for c in seen]
            if ranks != sorted(ranks):
                bad.append(f"{where} {cid}: a vote's parts come as {seen}")
            for lab in re.findall(r'<p class="sspoke"><span class="slab">([^<]*)</span>', v):
                if lab not in BSP.SPOKE.values():
                    bad.append(f"{where} {cid}: speakers labelled {lab!r}, not by the vote they urged")
            for said in re.findall(r'<p class="rcrec">([^<]*)', v):
                if not said.startswith(BSP.CLERK_LABEL + " "):
                    bad.append(f"{where} {cid}: the clerk's words are not labelled as theirs: {said!r}")
    return bad


@check("session", "a session day's card draws the rail above its votes, and each vote its head, "
       "count, mover, who spoke on each side and which vote they urged, the ring, and last the "
       "clerk's own words, only where they say more (the owner, 24 October 2026)",
       needs=("build_session_pages", "session_days", "shell"))
def _session_card_order(BSP, SD, shell):
    """THE CARD, TOP TO FOOT (the owner, 24 October 2026): "The rail on the
    session day pages should show above the votes as it would on a bill page
    or card"; "spoke for the motion and spoke against the motion should show
    above the vote chart as well, but below the motion. One thing that may
    help for clarity is identifying which speaker supported the yes vote and
    which supported the no vote, rather than solely saying they spoke for or
    against the motion"; and, of "In the record: House Concurs with Senate
    Amendment 2026-1622s", "currently it's somewhat redundant or in the wrong
    place".

    On every session day the fixture's site builds, and on a day made here
    with members speaking on both sides of a roll call, it fails if a card's
    rail is under its well of votes; if a vote's head, its count's line, its
    mover, its speakers, its ring, its notes and the clerk's words come in
    another order (CARD_VOTE_ORDER); if a side is labelled other than by the
    vote it urged (build_session_pages.SPOKE); or if a bill's vote carries an
    "In the record" line or a clerk's line not labelled as one. And on the
    rule for the clerk's words (clerk_adds), over the clerk's own phrasings
    of the build of 24 October 2026, it fails if they are kept where they say
    only the head's motion in the clerk's spelling -- "House Concurs with
    Senate Amendment 2026-1622s", "Laid on Table", "Lay HB1 on Table",
    "Accedes to House Request for Committee of Conference" -- or dropped
    where they say a day, a purpose, what was reconsidered, a step the head
    does not name, or a member the card does not name as the mover."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    bad, cards = [], 0
    for p in sorted((shared / "site" / "session").glob("[HS]/*.html")):
        text = p.read_text(encoding="utf-8")
        cards += text.count('<article class="card')
        bad += _card_faults(text, p.relative_to(shared / "site").as_posix(), BSP)
    assert cards >= 3, f"the fixture's site drew {cards} cards on its session days: too few to hold"

    def item(bill, seq, action, motion, kind="VV", y=None, n=None, mover=""):
        return SD.Item(bill, "2025-2026", {"type": "floor", "body": "H", "action": action,
                                           "motion": motion, "vote_kind": kind, "yeas": y,
                                           "nays": n, "mover": mover,
                                           "raw": f"{action}: {motion} {kind}",
                                           "cite_page": str(10 + seq)}, seq)

    class Nobody:
        def slug(self, body, name):
            return None
    day = SD.Day("H", "2026-05-21", [
        item("HB1", 1, "Inexpedient to Legislate", "MA", "RC", 200, 150),
        item("HB2", 2, "House Concurs with Senate Amendment 2026-1622s", "MA", "DV", 205, 160),
        item("HB3", 3, "Special Order to next order of business", "MA"),
        item("HB5", 5, "Reconsider ITL", "MF", "DV", 100, 200)])
    said = {"attributions": [
        {"bill": "HB1", "side": "for", "names": ["Smith"], "tally": (200, 150),
         "inline_motion": None, "moved_since": []},
        {"bill": "HB1", "side": "against", "names": ["Jones"], "tally": (200, 150),
         "inline_motion": None, "moved_since": []}]}
    page, _ = BSP.render(day, said, {}, {}, Nobody(), shell.E)
    bad += _card_faults(page, "the day made here", BSP)
    hb1 = page.split('data-id="HB1"', 1)[1].split("</article>", 1)[0]
    spoke = re.findall(r'<p class="sspoke"><span class="slab">([^<]+)</span>(.*?)</p>', hb1)
    if [(lab, re.sub(r"<[^>]+>", "", who).strip()) for lab, who in spoke] != [
            ("Spoke for the motion, urging a yes vote", "Rep. Smith"),
            ("Spoke against the motion, urging a no vote", "Rep. Jones")] \
            or not (hb1.index('class="dvr"') < hb1.index('class="sspoke"')
                    < hb1.index('class="svote"')):
        bad.append(f"HB 1's speakers are not between its count and its ring, each by the vote "
                   f"they urged: {spoke}")
    for bill, words in (("HB2", None), ("HB3", "Special Order to next order of business"),
                        ("HB5", "Reconsider ITL")):
        card = page.split(f'data-id="{bill}"', 1)[1].split("</article>", 1)[0]
        got = re.findall(r'<p class="rcrec">([^<]*)</p>', card)
        want = [f"{BSP.CLERK_LABEL} {words}"] if words else []
        if got != want:
            bad.append(f"{bill}'s clerk's words are {got}, where they should be {want}")
    # The rule itself, over the clerk's own phrasings.
    rule = (("House Concurs with Senate Amendment 2026-1622s", "", False), ("Concur", "", False),
            ("Laid on Table", "", False), ("Lay HB1 on Table", "", False),
            ("Accedes to House Request for Committee of Conference", "", False),
            ("Refer to Interim Study", "", False), ("Ought to Pass W/Amendment", "", False),
            ("Rereferred to Committee", "", False), ("Take from Table", "", False),
            ("Special Order to 03/11/1993", "", True), ("Suspend Rules for hearing", "", True),
            ("Reconsider ITL", "", True), ("Vacated from Committee and Laid on Table", "", True),
            ("Reconsideration (Rep Vaillancourt)", "", True),
            ("Reconsideration (Rep Vaillancourt)", "Rep. Vaillancourt", False))
    for words, mover, keep in rule:
        it = item("HB1", 1, words, "MA", mover=mover)
        got = 'class="rcrec"' in BSP.vote_html(it, "HB1", "H", "", {}, Nobody(), shell.E, [])
        if got != keep:
            bad.append(f"the clerk's words {words!r}" + (f" moved by {mover}" if mover else "")
                       + (" are dropped, and say more than the head" if keep
                          else " are kept, and say nothing the head does not"))
    css = _source("src/pages/app.css")
    if not re.search(r"\.cline \.dvote > \.rcrec\{[^}]*font-size:var\(--t-sm\)", css):
        bad.append("app.css no longer sets the clerk's words small at the foot of the vote")
    assert not bad, f"{len(bad)} faults on the session days' cards: " + "; ".join(bad[:6])
    return "ok", (f"{cards} fixture cards and a day made here: rail above the votes; head, count, "
                  "mover, speakers by the vote they urged, ring, then the clerk's words; the "
                  f"clerk's words kept or dropped as the rule says on {len(rule)} of their phrasings")


@check("session", "a mover who was the motion's one speaker is said in one line, and any other "
       "speaker keeps the rows", needs=("build_session_pages", "session_days", "shell"))
def _mover_spoke_once(BSP, SD, shell):
    """The audit of 25 October 2026 (S2): a card said "Moved by Rep. John
    Hunt (R - Ches 14)." and under it "Spoke for the motion, urging a yes
    vote: Rep. John Hunt (R - Ches 14)" -- the same member twice, on nine
    bills of 21 May 2026. Where the mover is the one member named on the
    motion, and on its side, the card says "Moved by Rep. John Hunt (R -
    Ches 14), who spoke for it, urging a yes vote." and draws no row; where
    anyone else spoke, the rows stand with their labels (SPOKE), the mover
    among them, as the owner chose on 24 October. A mover who spoke against
    their own motion, or a name only the mover's or the speaker's resolves,
    is never folded into the line."""
    def item(bill, seq, mover):
        return SD.Item(bill, "2025-2026", {"type": "floor", "body": "H",
                                           "action": "House Concurs with Senate Amendment 2026-1718s",
                                           "motion": "MA", "vote_kind": "VV", "mover": mover,
                                           "raw": "x", "cite_page": str(10 + seq)}, seq)

    class Roster:
        # Hunt and J. Hunt are one member; Smith is nobody the roster knows.
        def slug(self, body, name):
            return "john-hunt-ches-14" if name in ("Hunt", "J. Hunt") else None
    day = SD.Day("H", "2026-05-21", [item("HB1207", 1, "Rep. Hunt"), item("HB1236", 2, "Rep. Hunt"),
                                     item("HB1491", 3, "Rep. Hunt"), item("HB1348", 4, "Rep. Smith"),
                                     item("HB1500", 5, "Rep. Hunt")])

    def said(bill, side, names):
        return {"bill": bill, "side": side, "names": names, "tally": None,
                "inline_motion": None, "moved_since": []}
    attrs = [said("HB1207", "for", ["J. Hunt"]),
             said("HB1236", "for", ["Hunt", "Roy"]),
             said("HB1491", "against", ["Hunt"]),
             said("HB1348", "for", ["Smith"]),
             said("HB1500", "for", ["Smith"])]
    page, _ = BSP.render(day, {"attributions": attrs}, {}, {}, Roster(), shell.E)

    def card(bill):
        c = page.split(f'data-id="{bill}"', 1)[1].split("</article>", 1)[0]
        by = re.search(r'<p class="dvby">(.*?)</p>', c, re.S)
        rows = re.findall(r'<p class="sspoke"><span class="slab">([^<]+)</span>', c)
        return re.sub(r"<[^>]+>", "", by.group(1)) if by else "", rows
    tail = ", " + BSP.MOVER_SPOKE + "."
    bad = []
    by, rows = card("HB1207")
    if not by.endswith(tail) or rows:
        bad.append(f"HB 1207, moved by its one speaker: {by!r} over {rows}")
    for bill, why in (("HB1236", "another member spoke too"),
                      ("HB1491", "the mover spoke against it"),
                      ("HB1500", "another member spoke, and the mover did not")):
        by, rows = card(bill)
        if by.endswith(tail) or not rows or not all(r in BSP.SPOKE.values() for r in rows):
            bad.append(f"{bill}, where {why}: {by!r} over {rows}")
    by, rows = card("HB1348")
    if not by.endswith(tail) or rows:
        bad.append(f"HB 1348, moved by its one speaker whom no roster names: {by!r} over {rows}")
    bad += _card_faults(page, "the day made here", BSP)
    assert not bad, "; ".join(bad)
    return "ok", ("the mover as the one speaker for it in the mover's line; another speaker, a "
                  "speech against, or a different member keeps the labelled rows")


def _closing_text(card):
    """A card's closing line as words, or None where it has none."""
    import html as _html
    m = re.search(r'<p class="dsum"><span class="dsumlab">In short</span>(.*?)</p>', card, re.S)
    return _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))) if m else None


@check("session", "every bill card of a session day closes with its votes as the bill's history "
       "says them and what they mean for the bill (the owner, 24 October 2026)",
       needs=("build_session_pages", "session_days", "shell", "narrative"))
def _session_closing_line(BSP, SD, shell, N):
    """THE CLOSING LINE (the owner, 24 October 2026: "There should be a line
    at the bottom of every bill card on session day pages that explains all
    of the votes that were held and what that means for the bill, similar to
    what is in the narrative summary tab for bills, but isolated to the
    specific actions from that day").

    On every session day the fixture's site builds it fails if a card has no
    closing line, more than one, or one above any of its votes. On the days
    preflight's real docket rows make (_DOCKET_CUT_1999: the House's of 1999
    and 2006, the Senate's of 1999, 2000 and 2005), each told by
    narrative.build as a bill's history tells it, it fails if a reading the
    history makes of the day's floor votes -- "the House voted to pass it
    with changes", "rejected a motion to send it back to committee" -- is
    not the card's, or if the card does not say where HB 278 of 1999 and HB
    317 of 2006 went next (Finance, Ways and Means) or the history's own note
    on HB 1240's interim study. And on days made here, where the record is
    known, it fails if a bill the second chamber passed unchanged is not said
    to go to the Governor; one it changed, to go back to the first; one its
    own chamber passed, to go to the other; one passed and referred the next
    day, to that committee; if a concurrence is not said to send the bill to
    the Governor; if a failed motion to take a bill off the table does not
    leave it there; if a CACR that failed with more yeas than nays is not
    said to have needed three fifths; or if a motion the record names only in
    shorthand, or does not name, is said as anything but what the record
    says."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    bad, cards = [], 0
    for p in sorted((shared / "site" / "session").glob("[HS]/*.html")):
        text = p.read_text(encoding="utf-8")
        for card in re.findall(r'<article class="card[^"]*"[^>]*>.*?</article>', text, re.S):
            cards += 1
            n = card.count('<p class="dsum">')
            if n != 1 or card.rfind('<p class="dsum">') < card.rfind('<div class="dvote"'):
                bad.append(f"{p.name}: a card with {n} closing lines, or one above a vote")
            elif re.search(r"\{|\bNone\b", _closing_text(card) or ""):
                bad.append(f"{p.name}: a closing line with a place left unfilled: {_closing_text(card)}")
    assert cards >= 3, f"the fixture's site drew {cards} cards on its session days: too few to hold"

    class Nobody:
        def slug(self, body, name):
            return None

    # THE HISTORY'S OWN SENTENCES, from rows of the record.
    terms = {"1999": "1999-2000", "2000": "1999-2000", "2005": "2005-2006", "2006": "2005-2006"}
    narr, told = {}, {}
    saved = (N.CORRECTIONS, N.TERM)
    try:
        for bill, lines in _DOCKET_CUT_1999.items():
            term = terms[lines[0].split("|")[0]]
            N.CORRECTIONS, N.TERM = [], term
            rec = N.build(bill, _docket_rows(lines))
            narr.setdefault(term, {})[bill] = rec["events"]
            told[(term, bill)] = rec["stages"]
    finally:
        N.CORRECTIONS, N.TERM = saved
    days = _sitting_fixture(SD, narr, {})
    data = {t: {b: {"events": e} for b, e in bs.items()} for t, bs in narr.items()}
    amds = {b: BSP.amendments_on_sittings(days, data, b)[0] for b in "HS"}
    verbs = "|".join(re.escape(v) for v in sorted(set(N.RECOMMENDATION.values()), key=len,
                                                  reverse=True))
    lines, readings = {}, 0
    for (body, date), day in sorted(days.items()):
        page, _ = BSP.render(day, {}, {}, {}, Nobody(), shell.E,
                             ctx={"data": data, "amendments": amds[body]})
        when = N.fdate(f"{date[5:7]}/{date[8:]}/{date[:4]}")
        chamber = {"H": "House", "S": "Senate"}[body]
        for card in re.findall(r'<article class="card[^"]*"[^>]*>.*?</article>', page, re.S):
            bill = re.search(r'data-id="([^"]+)"', card).group(1)
            line = _closing_text(card) or ""
            lines[(date, bill)] = line
            term = next(t for t in narr if bill in narr[t])
            for st in told.get((term, bill)) or ():
                if not str(st.get("hand") or "").startswith(body):
                    continue
                for s in re.split(r"(?<=\.)\s+(?=[A-Z])", st.get("text") or ""):
                    m = re.search(rf"the {chamber} (?:again )?(voted to|rejected a motion to) "
                                  rf"({verbs})\b", s)
                    if when in s and m:
                        readings += 1
                        if f"{m.group(1)} {m.group(2)}" not in line:
                            bad.append(f"{bill} of {date}: the history says {s!r}, the card "
                                       f"{line!r}")
    assert readings >= 12, f"only {readings} of the history's readings were compared"
    for key, end in ((("1999-03-18", "HB278"), "It goes to the House Finance committee, and the "
                                               "House votes on it again once that committee reports."),
                     (("2006-02-15", "HB317"), "It goes to the House Ways and Means committee, and the "
                                               "House votes on it again once that committee reports."),
                     (("2006-02-15", "HB1240"), N.NUANCE["interim study"])):
        if not lines.get(key, "").endswith(end):
            bad.append(f"{key[1]} of {key[0]} closes {lines.get(key)!r}, where it should end {end!r}")

    # DAYS MADE HERE, where what each vote meant is known.
    T = "2025-2026"

    def item(bill, seq, action, motion, kind="VV", y=None, n=None, body="H", raw=None):
        return SD.Item(bill, T, {"type": "floor", "body": body, "action": action,
                                 "motion": motion, "vote_kind": kind, "yeas": y, "nays": n,
                                 "raw": raw or f"{action}: {motion} {kind}",
                                 "cite_page": str(10 + seq)}, seq)
    rail = [["Ip", "2026-01-07"], ["Hp", "2026-03-05"], ["S-"], ["G-"], ["L-"]]
    rows = {(T, b): {"passage": "Hp---", "rail": rail} for b in ("HB2", "HB10", "HB11", "HB13")}
    rows[(T, "SB12")] = {"passage": "S----",
                         "rail": [["Ip", "2026-01-07"], ["S-"], ["H-"], ["G-"], ["L-"]]}
    rows[(T, "CACR6")] = {"passage": "H----",
                          "rail": [["Ip", "2026-01-07"], ["H-"], ["S-"], ["V-"]]}
    house = SD.Day("H", "2026-05-21", [
        item("HB2", 1, "House Concurs with Senate Amendment 2026-1622s", "MA", "DV", 205, 160),
        item("CACR6", 2, "Ought to Pass", "MF", "RC", 181, 156,
             raw="Ought to Pass, Lacking Necessary Three-Fifths Vote: MF RC 181-156"),
        item("HB7", 3, "Conf Comm Report", "MA"), item("HB8", 4, "03/05/2026", "MA"),
        item("HB9", 5, "Ought to Pass", "MA")])
    later = {T: {"HB9": {"events": [
        {"type": "floor", "date": "2026-05-21", "body": "H", "action": "Ought to Pass",
         "motion": "MA", "vote_kind": "VV", "raw": "Ought to Pass: MA VV 05/21/2026"},
        {"type": "rereferred", "date": "2026-05-22", "body": "H", "raw": "Referred to Finance"}]}}}
    senate = SD.Day("S", "2026-05-07", [
        item("HB10", 1, "Ought to Pass", "MA", body="S",
             raw="Ought to Pass, MA, VV; OT3rdg; 05/07/2026"),
        item("HB11", 2, "Ought to Pass with Amendment 2026-1700s", "MA", body="S"),
        item("SB12", 3, "Ought to Pass", "MA", "RC", 16, 8, body="S"),
        item("HB13", 4, "Remove from Table", "MF", body="S")])
    made = {}
    for d in (house, senate):
        page, _ = BSP.render(d, {}, {}, {}, Nobody(), shell.E, ctx={"rows": rows, "data": later})
        for card in re.findall(r'<article class="card[^"]*"[^>]*>.*?</article>', page, re.S):
            made[re.search(r'data-id="([^"]+)"', card).group(1)] = _closing_text(card)
    want = {
        "HB2": "The House voted to agree to the other chamber's changes on a division vote "
               "205–160. Both chambers have passed it in the same form, so it goes to the Governor.",
        "CACR6": "The House rejected a motion to pass it on a roll call 181–156, short of the "
                 "three-fifths majority it needed.",
        "HB7": "The House adopted “Conf Comm Report” on a voice vote.",
        "HB8": "The House voted on a question the record does not name on a voice vote, and the "
               "motion carried.",
        "HB9": "The House voted to pass it on a voice vote. It goes to the House Finance "
               "committee, and the House votes on it again once that committee reports.",
        "HB10": "The Senate voted to pass it on a voice vote and ordered it to a third reading. "
                "Both chambers have passed it in the same form, so it goes to the Governor.",
        "HB11": "The Senate voted to pass it with changes on a voice vote. It goes back to the "
                "House, which can accept or reject the Senate's changes.",
        "SB12": "The Senate voted to pass it on a roll call 16–8. That sends it to the House.",
        "HB13": "The Senate rejected a motion to take it off the table on a voice vote. It stays "
                "on the table."}
    for bill, line in want.items():
        if made.get(bill) != line:
            bad.append(f"{bill}'s closing line is {made.get(bill)!r}, where it should be {line!r}")
    assert not bad, f"{len(bad)} faults in the cards' closing lines: " + "; ".join(bad[:5])
    return "ok", (f"{cards} fixture cards each closed once; {readings} of the history's readings of "
                  f"{len(lines)} days' cards made from rows of the record, each the card's; and "
                  f"{len(want)} made days' meanings, each as the record settles it")


@check("session", "a roll call the Journal put under a bill is the docket row's vote only where "
       "the row states its count and kind of question, and is drawn before the decision it "
       "preceded", needs=("session_days",))
def _journal_pairing_wins(SD):
    """THE JOURNAL'S PAIRING WINS (16 September 2015; the dry run of
    ebcea38). Reps. Flanagan and Shurtleff moved to suspend the House Rules
    for SB 9; Rep. William O'Brien appealed a ruling of the Chair on it, and
    the Chair was upheld 286-89 (2015-H-188); the House then suspended the
    rules 285-93 (2015-H-189), the count SB 9's docket gives the motion,
    after ten members spoke on it. Once the Journal's reading put the appeal
    under SB 9, the day held as many roll calls of SB 9 as docket tallies,
    and _pair matched them by place: the page drew "Rules Suspended 286-89"
    with the ten speakers under it, and the 285-93 among the votes on no
    bill. A roll call the Journal put under a bill is now a row's vote only
    on the row's own count and kind of question, and is drawn before the
    bill's next roll call by number, the decision it preceded. Both ways the
    Journal may read the day are held: the appeal alone under SB 9, and the
    appeal and the suspension both."""
    def rc(n, bill, q, y, nn, passed=True):
        return {"year": "2015", "body": "H", "number": n, "date": "2015-09-16", "bill": bill,
                "procedural": not bill, "question": q, "question_raw": q, "yeas": y,
                "nays": nn, "passed": passed}

    def row(kind, raw, y, nn, **kw):
        e = {"date": "2015-09-16", "type": kind, "body": "H", "cancelled": False, "raw": raw,
             "cite": "HJ 57", "cite_page": "", "vote_kind": "RC", "yeas": str(y),
             "nays": str(nn), "mover": ""}
        e.update(kw)
        return e

    events = [row("floor", "Suspend House Rules to Allow Present Action After Deadline (Reps "
                  "Flanagan and Shurtleff): MA RC 285-93 By Required Two-Thirds Vote", 285, 93,
                  action="Suspend House Rules to Allow Present Action After Deadline (Reps "
                         "Flanagan and Shurtleff)", motion="MA"),
              row("amendment", "Floor Amendment #2015-2391h (Rep Itse): AF RC 94-264", 94, 264,
                  amendment="2015-2391h", amend_kind="Floor Amendment", motion="AF"),
              row("floor", "Ought to Pass: MA RC 291-73", 291, 73, action="Ought to Pass",
                  motion="MA")]
    rolls = {"2015-2016": {
        "_procedural": [rc(188, None, "Uphold Ruling of the Chair", 286, 89),
                        rc(189, None, "Rules Suspension", 285, 93)],
        "SB9": [rc(190, "SB9", "Adopt Amendment", 94, 264, False),
                rc(194, "SB9", "Ought to Pass", 291, 73)]}}
    journals = {("H", "2015-09-16"): {"rc": [(286, 89), (285, 93), (94, 264), (291, 73)],
                                      "div": [], "bills": ["SB9"]}}
    root = Path(tempfile.mkdtemp())
    try:
        for n_, tied in enumerate((("2015-H-188",), ("2015-H-188", "2015-H-189"))):
            # a folder each: vote_passage keeps what it read by the path
            here = root / str(n_)
            here.mkdir()
            path = here / "narratives.json"
            path.write_text(json.dumps({"2015-2016": {"SB9": {"events": events}}}),
                            encoding="utf-8")
            (here / "rollcalls.json").write_text(json.dumps(rolls), encoding="utf-8")
            (here / "journal_motions.json").write_text(json.dumps({"rollcalls": {
                k: {"on_bill": "SB9", "on_bill_from": "named", "held": []} for k in tied}}),
                encoding="utf-8")
            days = SD.load(path, journals=journals)
            d = days.get(("H", "2015-09-16"))
            assert d, "the fixture's sitting of 16 September 2015 was not built"
            sb9 = [i for i in d.items if i.bill == "SB9"]
            told = [(i.action[:22], i.yeas, i.nays, i.rc and i.rc["number"]) for i in sb9]
            sus = [i for i in sb9 if i.action.startswith("Suspend House Rules")]
            assert len(sus) == 1 and (sus[0].yeas, sus[0].nays) == (285, 93) \
                and (sus[0].rc or {}).get("number") == 189, (
                f"with {', '.join(tied)} under SB 9 by the Journal, SB 9's suspension is not "
                f"drawn as 2015-H-189's 285-93: {told}")
            up = [n for n, i in enumerate(sb9) if (i.yeas, i.nays) == (286, 89)]
            assert len(up) == 1 and not sb9[up[0]].action.startswith("Suspend") \
                and up[0] < sb9.index(sus[0]), (
                f"the appeal's 286-89 is not drawn as its own question, before the suspension "
                f"it arose on: {told}")
            on_none = [(i.yeas, i.nays) for i in d.others]
            assert not on_none, f"SB 9's votes are drawn among the votes on no bill: {on_none}"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("SB 9's suspension keeps its own 285-93 and the appeal's 286-89 is drawn "
                  "before it as its own question, whether the Journal puts the appeal alone or "
                  "both under SB 9")


@check("session", "the consent list holds only what the calendar disposed of",
       needs=("session_days",))
def _session_consent_only_the_calendar(SD):
    """A bill's last committee report saying CC marked EVERY later floor
    action on it as a consent item, in either chamber.

    The veto day of 19 August 2026 listed a motion to reconsider HB 396 as
    "disposed of together, in one motion and without debate"; 2,852 actions
    were listed because the OTHER chamber's report said CC, and 2,109 came
    after the docket recorded the bill being removed from the calendar.
    Against the consent sections the House and Senate Journals print, the
    pages named 3,132 bills as consent items that the journal does not, and
    now name 397. The rows below are real docket wording, one case each, and
    the day-level rule is checked through load() so that it cannot be dropped
    from the path the pages use.
    """
    def ev(date, body, kind, raw, **kw):
        e = {"date": date, "body": body, "type": kind, "raw": raw}
        e.update(kw)
        return e

    def floor(date, body, raw, action, motion="MA", kind="VV", **kw):
        return ev(date, body, "floor", raw, action=action, motion=motion,
                  vote_kind=kind, **kw)

    rep_h = "Committee Report: Ought to Pass 03/13/2024 (Vote 20-0; CC)"
    bills = {
        # the calendar's own item, then everything after it on the bill
        "HB396": [ev("2026-01-06", "H", "report", rep_h),
                  floor("2026-01-08", "H", "Ought to Pass: MA VV 01/08/2026",
                        "Ought to Pass"),
                  floor("2026-03-05", "S", "Ought to Pass, MA, VV; OT3rdg; "
                        "03/05/2026", "Ought to Pass"),
                  ev("2026-08-19", "H", "veto_override", "Veto Sustained "
                     "08/19/2026: RC 204-116 Lacking Necessary Two-Thirds Vote"),
                  floor("2026-08-19", "H", "Reconsider HB396 (Rep. Comtois): "
                        "MA RC 187-120 08/19/2026", "Reconsider HB396",
                        kind="RC", yeas="187", nays="120",
                        mover="Rep. Comtois")],
        # the House's report, and the Senate's is the next floor action
        "HB9": [ev("2026-01-06", "H", "report", rep_h),
                floor("2026-03-05", "S", "Ought to Pass, MA, VV; OT3rdg; "
                      "03/05/2026", "Ought to Pass")],
        # "Removed from Consent (Rep. Stone)" arrives typed "other"
        "HB1543": [ev("2018-03-06", "H", "report", "Committee Report: "
                      "Inexpedient to Legislate for 03/06/2018 (Vote 20-0; CC)"),
                   ev("2018-03-06", "H", "other",
                      "Removed from Consent (Rep. Stone) 03/06/2018"),
                   floor("2018-03-22", "H", "Inexpedient to Legislate: MA VV "
                         "03/22/2018", "Inexpedient to Legislate")],
        # a suspension the same day leaves the report in place...
        "HB785": [ev("2003-03-19", "H", "report",
                     "Maj Report OTP for Mar 25 (Vote 19-0;CC)"),
                  floor("2003-03-25", "H", "Reps Hess & Nordgren Susp Rules for "
                        "late ref to Finance, MA 2/3VV",
                        "Susp Rules for late ref to Finance"),
                  floor("2003-03-25", "H", "Passed and ref to Finance",
                        "Ought to Pass")],
        # ...but not across days: the bill came back on its own
        "HB158": [ev("2005-03-24", "H", "report",
                     "Comm Report OTP/AM for Mar 30 (vote 16-0;CC)"),
                  floor("2005-03-30", "H", "Reps O'Neil & Craig Susp Rules for "
                        "Action Deadline, MA 2/3VV", "Susp Rules for Action Deadline"),
                  floor("2005-04-06", "H", "Passed with Am VV",
                        "Ought to Pass with Amendment")],
        # a named member's motion is not the calendar
        "HB1555": [ev("2022-03-01", "H", "report", "Committee Report: Refer for "
                      "Interim Study (Vote 21-1; CC)"),
                   floor("2022-03-10", "H", "Lay HB1555 on Table (Rep. Renzullo): "
                         "MA RC 199-131 03/10/2022", "Lay HB1555 on Table",
                         kind="RC", yeas="199", nays="131", mover="Rep. Renzullo")],
        # the Senate dates its report row the day after the vote
        "HB1526": [ev("2024-03-13", "H", "report", rep_h),
                   floor("2024-03-28", "H", "Ought to Pass : MA VV 03/28/2024",
                         "Ought to Pass"),
                   floor("2024-05-15", "S", "Ought to Pass with Amendment "
                         "2024-1848s, MA, VV; OT3rdg; 05/15/2024",
                         "Ought to Pass with Amendment"),
                   ev("2024-05-16", "S", "report", "Committee Report: Ought to "
                      "Pass with Amendment #2024-1848s , 05/16/2024; Vote 5-0; CC")],
        # a bill of address is reported Ought Not to Pass
        "HA1": [ev("2018-02-27", "H", "report", "Committee Report: Ought Not to "
                   "Pass for 03/06/2018 (Vote 20-0; CC)"),
                floor("2018-03-06", "H", "Ought Not to Pass: MA VV 03/06/2018",
                      "Ought Not to Pass")],
        # the Senate took its calendar by one roll call: shared tallies stay,
        # a tally of one bill's own does not
        "SB11": [ev("2021-04-15", "S", "report", "Committee Report: Ought to "
                    "Pass, 04/22/2021; Vote 5-0; CC"),
                 floor("2021-04-22", "S", "Ought to Pass : RC 23Y-1N, MA; OT3rdg; "
                       "04/22/2021", "Ought to Pass", kind="")],
        "SB12": [ev("2021-04-15", "S", "report", "Committee Report: Ought to "
                    "Pass, 04/22/2021; Vote 5-0; CC"),
                 floor("2021-04-22", "S", "Ought to Pass : RC 23Y-1N, MA; OT3rdg; "
                       "04/22/2021", "Ought to Pass", kind="")],
        "SB13": [ev("2021-04-15", "S", "report", "Committee Report: Ought to "
                    "Pass, 04/22/2021; Vote 5-0; CC"),
                 floor("2021-04-22", "S", "Ought to Pass : RC 16Y-8N, MA; OT3rdg; "
                       "04/22/2021", "Ought to Pass", kind="")],
        # The Senate's wording of 2011 to 2024, the bill between the verb and
        # the calendar (SB 58 of 2013, Docket_db_2013-2014.txt)...
        "SB58": [ev("2013-02-07", "S", "report", "Committee Report: Ought to Pass, "
                    "2/14/13; Vote 5-0; CC; SC8"),
                 ev("2013-02-14", "S", "other", "Sen. D’Allesandro Moved to Remove "
                    "SB 58 from the Consent Calendar"),
                 floor("2013-02-14", "S", "Ought to Pass: MA, VV; OT3rdg",
                       "Ought to Pass")],
        # ...a removal entered after the bill's own disposition (SB 74 of
        # 2025, Docket.txt 6196-6202)...
        "SB74": [ev("2025-03-20", "S", "report", "Committee Report: Ought to Pass, "
                    "03/20/2025; Vote 6-0; CC"),
                 floor("2025-03-20", "S", "Ought to Pass with Amendment #2025-0975s, MA, "
                       "VV; OT3rdg; 03/20/2025", "Ought to Pass with Amendment #2025-0975s"),
                 ev("2025-03-20", "S", "other", "SB 74-FN was Removed from the Consent "
                    "Calendar; 03/20/2025")],
        # ...and one entered weeks later, dated in its words (HB 703 of 2019,
        # entered 4 June) -- but never a removal of an earlier report, after
        # which the committee reported again: HB 442 of 1989 came off in
        # April and passed on the calendar of 4 January 1990.
        "HB703": [ev("2019-05-15", "S", "report", "Committee Report: Rereferred to "
                     "Committee, 05/15/2019; Vote 5-0; CC"),
                  floor("2019-05-15", "S", "Rereferred to Committee, MA, VV; 05/15/2019",
                        "Rereferred to Committee"),
                  ev("2019-06-04", "S", "other", "Sen. Sherman Moved to Remove HB 703-FN "
                     "from the Consent Calendar; 05/15/2019")],
        "HB442": [ev("1989-04-05", "H", "report", "MAJ REPORT RE-REF TO RES, REC & DEV FOR: "
                     "4/11 VOTE(18-0;CC)"),
                  ev("1989-04-11", "H", "rereferred", "REMOVED FROM CC, REP DICKINSON; "
                     "RE-REF TO RR&D VV; HJ69, P2081"),
                  ev("1989-11-08", "H", "report", "RE-REF MAJ REPORT OTP/AM FOR JAN04,1990 "
                     "(VOTE 16-0;CC)"),
                  floor("1990-01-04", "H", "PASSED WITH AM AND REF TO APPROP; HJ8,P266-269",
                        "Ought to Pass with Amendment", kind="")],
    }
    root = Path(tempfile.mkdtemp())
    try:
        path = root / "narratives.json"
        path.write_text(json.dumps({"2025-2026": {
            b: {"events": e} for b, e in bills.items()}}), encoding="utf-8")
        days = SD.load(path, journals={})

        def consent(body, date, bill):
            d = days.get((body, date))
            assert d, f"the fixture's sitting {body} {date} was not built"
            return [i.consent for i in d.items if i.bill == bill]

        assert consent("H", "2026-01-08", "HB396") == [True], (
            "the calendar's own disposition of HB 396 is not a consent item")
        assert consent("H", "2026-08-19", "HB396") == [False, False], (
            "the veto vote or the reconsideration of HB 396 on 19 August 2026 "
            "is listed as a consent item")
        assert consent("S", "2026-03-05", "HB396") == [False] and \
            consent("S", "2026-03-05", "HB9") == [False], (
            "a House report's CC made a Senate action a consent item")
        assert consent("H", "2018-03-22", "HB1543") == [False], (
            "a bill the docket says was 'Removed from Consent' is still listed "
            "on the calendar")
        assert consent("H", "2003-03-25", "HB785") == [False, True], (
            "a same-day suspension of the rules either became a consent item or "
            "used up the report before the bill passed on the calendar")
        assert consent("H", "2005-04-06", "HB158") == [False], (
            "a report outlived a suspension taken on an earlier day")
        assert consent("H", "2022-03-10", "HB1555") == [False], (
            "a named member's motion to table was listed as consent")
        assert consent("S", "2024-05-15", "HB1526") == [True], (
            "the Senate report row dated the day after its vote was missed")
        assert consent("H", "2018-03-06", "HA1") == [True], (
            "an Ought Not to Pass report on the calendar was missed")
        got = {b: consent("S", "2021-04-22", b) for b in ("SB11", "SB12", "SB13")}
        assert got == {"SB11": [True], "SB12": [True], "SB13": [False]}, (
            "a calendar taken by one roll call keeps the bills that share its "
            f"tally and drops a bill with a tally of its own; got {got}")
        assert consent("S", "2013-02-14", "SB58") == [False], (
            "the Senate's 'Moved to Remove SB 58 from the Consent Calendar' is "
            "not read, and the bill is listed on the calendar it came off")
        assert consent("S", "2025-03-20", "SB74") == [False], (
            "a removal entered after the bill's disposition left it listed on "
            "the calendar it came off")
        assert consent("S", "2019-05-15", "HB703") == [False], (
            "a removal entered weeks later, for the day it writes, left the bill "
            "listed on that day's calendar")
        assert consent("H", "1990-01-04", "HB442") == [True], (
            "a removal of an earlier report took the bill off a calendar its "
            "committee's next report put it on")
        return "ok", ("the calendar's item only, in its own chamber: no veto "
                      "day reconsideration, other chamber, removed bill (in "
                      "the Senate's words, or entered after), named mover or "
                      "lone tally; same-day suspensions, a late Senate report "
                      "row, Ought Not to Pass and a later report's calendar kept")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# The 14 April 1999 House Journal, as journal_days reads it: Part II of the
# consent calendar under a heading CONSENT_HEAD does not take, with HB 605's
# removal on it; and, for the rule that a stray line cannot ADD a bill, a
# "removed by" paragraph under another heading for a bill the calendar did
# not hold that day (HB 9999).
_JOURNAL_1999 = """
                                                  HOUSE JOURNAL NO. 23

                                               Wednesday, April 14, 1999

                                                   COMMITTEE REPORTS

                                              CONSENT CALENDAR - Part II

Rep. Chandler moved that the Consent Calendar with the relevant amendments as
printed in the day's House Record be adopted.

HB 605-FN, affirming sovereign immunity as it relates to the state's computers and
computer software and programs and granting the state board of claims jurisdiction over
claims against the state arising out of computer-related problems, removed by Rep. Mock.

Consent Calendar adopted.

                                                   MOTION TO VACATE

HB 9999, relative to nothing in particular, removed by Rep. Nobody.
"""
_JOURNAL_2026 = """
                                                  HOUSE JOURNAL NO. 5

                                              Thursday, February 19, 2026

                                                   CONSENT CALENDAR

HB 1602-FN: relative to the thing the House took off, removed by Reps. Able and
Baker.

Consent Calendar was adopted.

                                                   COMMITTEE REPORTS
"""


@check("session", "a removal from the consent calendar is read wherever the day prints "
       "it, and can only take a bill off", needs=("journal_days", "session_days",
                                                   "build_session_pages"))
def _session_consent_removed_anywhere(JD, SD, BSP):
    """The 14 April 1999 House sitting listed HB 605 among the bills adopted
    together without debate; the House took it off the calendar and sent it
    back to committee. The journal
    prints its removal under "CONSENT CALENDAR - Part II", a heading the
    consent segment is not read from. And 19 February 2026 printed HB 1602's
    removal with a colon. A removal printed outside the segment counts only
    for a bill on that day's consent list, so it can take one off and never
    put one on -- the House prints 143 of them, under a motion to vacate or to
    withdraw, a guests' heading. The page is drawn through render(), the path
    the pages use."""
    import html as _html
    blocks = {iso: b for iso, b in JD.day_blocks(JD.clean(_JOURNAL_1999))}
    assert "1999-04-14" in blocks, "the fixture's sitting was not found"
    c = JD.consent(blocks["1999-04-14"])
    assert c.get("removed_elsewhere") == ["HB605-FN", "HB9999"], (
        f"the removals printed outside the consent segment were not read: {c}")
    found = {"consent": c}
    assert JD.taken_off(found, {"HB605", "HB522"}) == ["HB605-FN"], (
        "HB 605's removal did not count for a bill on the day's consent list")
    assert JD.taken_off(found, {"HB522"}) == [], (
        "a removal printed outside the segment counted for a bill not on the list")
    blocks = {iso: b for iso, b in JD.day_blocks(JD.clean(_JOURNAL_2026))}
    assert JD.consent(blocks["2026-02-19"]).get("removed") == ["HB1602-FN"], (
        "a removal written with a colon after the bill was not read")

    def ev(date, raw, typ, **kw):
        return {"date": date, "body": "H", "type": typ, "raw": raw, **kw}
    rep = "Maj Report ITL for Apr 14 (Vote 16-0;CC)"
    narr = {"1999-2000": {
        b: {"events": [ev("1999-04-07", rep, "report"),
                       ev("1999-04-14", "ITL VV", "floor", action="Inexpedient to Legislate",
                          motion="MA", vote_kind="VV")]}
        for b in ("HB605", "HB522")}}
    root = Path(tempfile.mkdtemp())
    try:
        (root / "narratives.json").write_text(json.dumps(narr), encoding="utf-8")
        day = SD.load(root / "narratives.json", journals={})[("H", "1999-04-14")]
        assert sorted(i.bill for i in day.items if i.consent) == ["HB522", "HB605"], (
            "the fixture's two bills are not both on the day's consent list")
        page = BSP.render(day, found, {}, {}, {}, _html.escape)[0]
        cons = page.split('<section class="w4" id="consent">', 1)[-1].split("</section>", 1)[0]
        listed = cons.split("<details", 1)[-1]
        assert "HB 522" in listed and "HB 605" not in listed and \
            "HB 605-FN was removed from the consent calendar" in cons, (
            "the 14 April 1999 page still lists HB 605 as adopted without debate: "
            + re.sub(r"<[^>]+>", " ", cons)[:200])
        assert "HB 9999" not in page, "a stray removal put a bill into the consent note"
        # Without HB 605 on the list, the same journal changes nothing.
        narr["1999-2000"].pop("HB605")
        (root / "narratives.json").write_text(json.dumps(narr), encoding="utf-8")
        day = SD.load(root / "narratives.json", journals={})[("H", "1999-04-14")]
        assert BSP.render(day, found, {}, {}, {}, _html.escape)[0] == \
            BSP.render(day, {}, {}, {}, {}, _html.escape)[0], (
            "removals printed outside the segment, for bills not on the list, changed the page")
        # HB 605 as its 14 April line is read since 1 October 2026: whole, a
        # recommittal on Rep. Mock's motion and no consent item at all. The
        # line itself says the bill came off the calendar, in a clause of its
        # own, and that puts it on the day's list for the journal's removal to
        # count; a special order naming "the bills removed from the Consent
        # Calendar" does not.
        whole = ("ITL Report adopted; Consent Cal reconsidered, Rep Mock MA VV; Removed from "
                 "Consent Cal, req Rep Mock; Recommitted to committee, Rep Mock MA VV; HJ40, p943")
        narr["1999-2000"]["HB605"] = {"events": [
            ev("1999-04-07", rep, "report"),
            ev("1999-04-14", whole, "floor", action="Rerefer to Committee", motion="MA",
               vote_kind="VV")]}
        narr["1999-2000"]["HB9999"] = {"events": [
            ev("1999-04-14", "Special Order to after the bills removed from the Consent "
               "Calendar, Without Objection, MA", "floor", action="Special Order", motion="MA")]}
        (root / "narratives.json").write_text(json.dumps(narr), encoding="utf-8")
        day = SD.load(root / "narratives.json", journals={})[("H", "1999-04-14")]
        assert sorted(i.bill for i in day.items if i.consent) == ["HB522"], (
            "HB 605's recommittal, read whole, is a consent item")
        page = BSP.render(day, found, {}, {}, {}, _html.escape)[0]
        cons = page.split('<section class="w4" id="consent">', 1)[-1].split("</section>", 1)[0]
        assert "HB 605-FN was removed from the consent calendar" in cons and "HB 9999" not in cons, (
            "the 14 April 1999 page does not say HB 605 was taken off the consent "
            "calendar, which its own docket line and the journal both say: "
            + re.sub(r"<[^>]+>", " ", cons)[:200])
        assert "Rerefer to Committee" in page, (
            "HB 605's recommittal is not among the day's motions")
        return "ok", ("HB 605 comes off 14 April 1999's list, as a consent item or as the "
                      "recommittal its line is read as whole; a colon is read; a stray "
                      "removal for a bill not on the list changes nothing")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# HB 605 as the 14 April 1999 House Journal prints it once it came off the
# consent calendar, and the reconsideration of HB 737 that follows it with no
# bill heading between (journals/1999/HJ012.txt; the committee's report is cut
# to its first sentence). Then HB 1-A and its own reconsideration, from
# journals/1999/HJ021.txt, the budget's report cut to its heading.
_JOURNAL_RECONSIDER = """
HB 605-FN, affirming sovereign immunity as it relates to the state's computers and
computer software and programs and granting the state board of claims jurisdiction over
claims against the state arising out of computer-related problems. INEXPEDIENT TO
LEGISLATE

Rep. Sandra B. Keans for Judiciary: This bill immunizes the state in perpetuity for any
and all computer problems whether they relate to the Y2K problem or not. Vote 13-1.

Rep. Mock moved Re-commit to Committee and spoke in favor.

Adopted.

                                                          reconsideration

Having voted with the prevailing side, Rep. Bickford moved that the House reconsider its
action whereby it voted HB 737, declaring the New Hampshire supreme court's Claremont
II decision to be an unconstitutional violation of the separation of powers mandate under
part I, article 37 of the New Hampshire constitution, Inexpedient to Legislate.
Reps. Nancy Wall, and Dickinson spoke in favor.
Rep. Weber spoke in favor and yielded to questions.
Reps. Belvin and MacGillivray spoke against.
Rep. Dickinson requested a roll call; sufficiently seconded.
The question being the motion to reconsider.

                                 YEAS 120 NAYS 225

HB 1-A, making appropriations for the expenses of certain departments of the state for the fiscal
years ending June 30, 2000, and June 30, 2001. MAJORITY: OUGHT TO PASS WITH
AMENDMENT. MINORITY: OUGHT TO PASS.

                                                          reconsideration
Having voted with the prevailing side, Rep. Hager moved that the House reconsider its action
whereby it ordered to third reading HB 1-A, making appropriations for the expenses of certain
departments of the state for the fiscal years ending June 30, 2000 and June 30, 2001.

Rep. Hager spoke against.

Reconsideration failed.
"""


# Cut from House Journals 5, 7, 14, 15 and 16 of 2025-2026 and 27 of 2016,
# each as it stands in the file (journal_days reads a block of them).
_JOURNAL_DECIDED = """HB 334-FN, relative to the comprehensive state development plan. MAJORITY: INEXPEDIENT TO LEG-
ISLATE. MINORITY: OUGHT TO PASS.

The question being adoption of the majority committee report of Inexpedient to Legislate.
Rep. Granger requested a roll call; sufficiently seconded.
28                            13FEBRUARY2025HOUSERECORD

Aldrich, Glen                 Bean, Harry           YEAS 199 - NAYS 171                  Coker, Matthew

and the majority committee report was adopted.
\f30                  13FEBRUARY2025HOUSERECORD

HB 422-FN, increasing penalties for violations of the shoreland and water quality protection act. MAJORITY:
INEXPEDIENT TO LEGISLATE. MINORITY: OUGHT TO PASS.

The question being adoption of the majority committee report of Inexpedient to Legislate.
Rep. Donnelly spoke in favor.
Rep. Rung spoke against and requested a roll call; sufficiently seconded.

                                      YEAS 196 - NAYS 175

and the majority committee report was adopted.

HB 94-FN, relative to coverage of circumcision under the state Medicaid plan. MAJORITY: OUGHT TO
PASS. MINORITY: INEXPEDIENT TO LEGISLATE.

The question being adoption of floor amendment (0786h).
Rep. Read spoke in favor.
Floor amendment (0786h) failed.

The question now being adoption of the majority committee report of Ought to Pass.
Reps. Nagel and Berch spoke against.
Rep. Soti spoke in favor and yielded to questions.
Rep. Granger requested a roll call; sufficiently seconded.

                                        YEAS 184 - NAYS 183

SB 14-FN, relative to the penalty for certain fentanyl-related offenses. MAJORITY: OUGHT TO PASS
WITH AMENDMENT. MINORITY: INEXPEDIENT TO LEGISLATE.

The question being adoption of the majority committee amendment.
Rep. Scherr spoke against.
Rep. Verville spoke in favor.
Rep. Roy spoke in favor and requested a roll call; sufficiently seconded.

                                             YEAS 217 - NAYS 164

The question being adoption of floor amendment (2641h).
Rep. Verville spoke against.
On a division vote, with 181 members having voted in the affirmative, and 202 in the negative, floor amend-
ment (2641h) failed.

The question now being adoption of the majority committee report of Ought to Pass with Amendment.
Rep. Harriott-Gathright spoke against.
Rep. Verville spoke in favor.
Rep. Roy spoke in favor and requested a roll call; sufficiently seconded.

                                    YEAS 214 - NAYS 167

SB 294-FN, relative to lab fees for career and technical education courses. MAJORITY: INEXPEDIENT
TO LEGISLATE. MINORITY: OUGHT TO PASS.

The question being adoption of the majority committee report of Inexpedient to Legislate.
Rep. Ladd spoke in favor.

                                                 MOTION TO LAY ON THE TABLE

Rep. Luneau moved that SB 294-FN, relative to lab fees for career and technical education courses, be laid
on the table.
Motion was adopted.

HB 1194-FN, relative to credits for assessments paid by insurers and relative to the application of criminal
gambling statutes. (Amendment printed SJ 5/7/26)
Rep. Janigian moved that the House nonconcur and request a Committee of Conference.
Motion was adopted.
The Speaker appointed Reps. Janigian, Ulery, Almy and Ford.

                    REPORT OF THE COMMITTEE ON LEGISLATIVE ADMINISTRATION
The question was to affirm the report of the committee on Legislative Administration.
Rep. Corcoran spoke against.
Rep. Simpson spoke in favor.
Rep. McFarlane spoke against and requested a roll call; sufficiently seconded.

                                              YEAS 288 - NAYS 54

HB 1153, prohibiting a political subdivision from adopting residency restrictions on sex offenders. OUGHT
TO PASS.
The question now being adoption of the committee report of Ought to Pass.         Bordenet, John
Rep. Prudhomme-O'Brien spoke against.                                             Hunt, John
Rep. Cushing spoke in favor and yielded to questions.                             Parkhurst, Henry
Rep. Sweeney Rep. spoke in favor and requested a roll call; sufficiently seconded.
"""


@check("session", "a speech is placed only on the motion whose count or decision the journal prints after it",
       needs=("journal_days", "session_days", "build_session_pages"))
def _session_speech_decided(JD, SD, BSP):
    """The reviews of 3 October 2026 read 1,127 speakers on 35 House pages
    against their journals, and 76 were named on a motion the journal
    contradicts: on another bill, on a censure or a reprimand, on a motion
    to suspend the rules, or on an amendment's failure set down as a speech
    on the report. Four causes, each cut here from the journal it was found
    in:

      - a running head taken out with the line breaks around it, which put a
        page's first bill heading mid-line (HB 422 of 13 February 2025, read
        as HB 334's) -- journal_days.clean(lines=True);
      - a speech found again by its first forty characters, which is the
        first sentence that begins the same way (Rep. Verville's second
        "spoke in favor" on SB 14 of 5 June 2025, read at his first);
      - a speech closed only by a roll call, where the journal decides its
        question first by division or by voice ("Floor amendment (0786h)
        failed.", HB 94 of 6 March 2025) -- journal_days' `decided`;
      - and one motion on the day claiming every speech on the bill, even
        one the journal ties to another count (the 288-54 on censuring Rep.
        Corcoran, printed after HB 1194's nonconcurrence of 21 May 2026).

    And a speaker's name holds no verb or title: "Rep. Prudhomme-O'Brien
    spoke against." with a roll call's column beside it was the speaker
    "Prudhomme-O'Brien spoke against. Hunt", and "Rep. Sweeney Rep. spoke"
    a Rep. "Sweeney Rep"."""
    glued = {a["bill"] for a in JD.attributions(JD.clean(_JOURNAL_DECIDED))
             for n in a["names"] if n == "Donnelly"}
    attrs = JD.attributions(JD.clean(_JOURNAL_DECIDED, lines=True))
    by = {}
    for a in attrs:
        for n in a["names"]:
            by.setdefault(n, []).append(a)
    assert glued == {"HB334-FN"} and [a["bill"] for a in by["Donnelly"]] == ["HB422-FN"], (
        "a bill heading after a running head is not read as the start of its bill: "
        f"Rep. Donnelly is on {[a['bill'] for a in by['Donnelly']]} (glued: {glued})")
    assert sorted((a["side"], a["tally"], a["decided"]) for a in by["Verville"]) == [
        ("against", (214, 167), {"count": (181, 202)}),
        ("for", (214, 167), None), ("for", (217, 164), None)], (
        f"SB 14's three speeches by Rep. Verville are not each where the journal prints "
        f"them: {by['Verville']}")
    read, = by["Read"]
    assert read["decided"] == {"words": "Floor amendment (0786h) failed."} and \
        BSP.journal_count(read) is None and BSP.journal_count(by["Soti"][0]) == (184, 183), (
        f"HB 94's speech on the failed floor amendment is not closed by it: {read}")
    assert "Hunt" not in " ".join(n for a in attrs for n in a["names"]) and \
        {n for a in attrs if a["bill"] == "HB1153" for n in a["names"]} == \
        {"Prudhomme-O'Brien", "Cushing", "Sweeney"}, (
        "a speaker's name runs on into a verb, a title or the roll call's column: "
        f"{[a['names'] for a in attrs if a['bill'] == 'HB1153']}")

    def item(bill, action, kind, y=None, n=None):
        return SD.Item(bill, "2025-2026", {"type": "floor", "body": "H", "action": action,
                                           "motion": "MA", "vote_kind": kind, "yeas": y,
                                           "nays": n, "raw": action}, 0)
    otp = item("HB94", "Ought to Pass", "RC", "184", "183")
    mine, _rest = BSP.speakers_for(attrs, "HB94", otp, sole=True)
    assert mine == {"for": ["Soti"], "against": ["Nagel", "Berch"]} and \
        BSP.unplaced(attrs, "HB94", [otp]) == ["Read"], (
        f"HB 94's report claims {mine}; Rep. Read spoke on the floor amendment")
    nonc = item("HB1194", "House Non-Concurs with Senate Amendment and Requests CofC", "VV")
    assert BSP.speakers_for(attrs, "HB1194", nonc, sole=True)[0] == \
        {"for": [], "against": []} and BSP.unplaced(attrs, "HB1194", [nonc]) == [], (
        "the speeches on censuring Rep. Corcoran are named on HB 1194, whose one "
        "motion that day was decided by voice")
    table = item("SB294", "Lay SB294 on Table", "VV")
    assert BSP.speakers_for(attrs, "SB294", table, sole=True)[0] == \
        {"for": [], "against": []} and BSP.unplaced(attrs, "SB294", [table]) == ["Ladd"], (
        "Rep. Ladd, who spoke for killing SB 294, is credited to the motion to table it "
        "that was made after he spoke")
    amend = item("SB14", "Adopt Majority Committee Amendment", "RC", "217", "164")
    report = item("SB14", "Ought to Pass with Amendment", "RC", "214", "167")
    assert BSP.speakers_for(attrs, "SB14", report)[0] == \
        {"for": ["Verville", "Roy"], "against": ["Harriott-Gathright"]} and \
        BSP.speakers_for(attrs, "SB14", amend)[0] == \
        {"for": ["Verville", "Roy"], "against": ["Scherr"]} and \
        BSP.unplaced(attrs, "SB14", [amend, report]) == [], (
        "SB 14's report or amendment names a speaker of another question, or the "
        "speech on the floor amendment 2641h, whose division the page does not draw, "
        "is named at all")
    return "ok", ("a heading after a running head starts its bill; each speech is read "
                  "where it stands, closed by the division or voice vote the journal "
                  "prints, and claimed only by the motion of its own count")


# Cut from House Journals 8 of 2012, 12 of 2005, 14 of 2006, 2 of 2024, 12 of
# 2002, 18 of 2007, 5 of 1998, 2 and 17 of 2000, each as it stands in the file;
# the text of an amendment is cut to its first line.
_JOURNAL_WALK = """HB 1670, apportioning executive council districts. MAJORITY: OUGHT TO PASS WITH
AMENDMENT. MINORITY: INEXPEDIENT TO LEGISLATE.
Rep. Rowe spoke in favor.
Rep. Vaillancourt spoke against.

                                               CALL OF THE HOUSE

Rep. Bettencourt moved a Call of the House.
With 271 members having answered the Call, a quorum was declared present and Chamber
doors were secured.

The question now being adoption of the majority committee amendment.
On a division vote, 177 members having voted in the affirmative and 99 in the negative, the
majority committee amendment was adopted.
\fThe question now being adoption of the majority committee report of Ought to Pass with
Amendment.
Rep. Vaillancourt offered floor amendment (0725h).

                                             Floor Amendment (0725h)
Amend the bill by replacing section 1 with the following:
Rep. Vaillancourt spoke in favor.
Rep. Hess spoke against.
Rep. Jasper requested a roll call; sufficiently seconded.

                                                YEAS 96 NAYS 179

HB 2-FN-A, relative to state fees, funds, revenue and expenditures. OUGHT TO PASS
WITH AMENDMENT
Rep. Wendelboe spoke in favor and yielded to questions.
Rep. Ryan spoke against.
Rep. Hagan spoke in favor.
Rep. John Flanders moved the previous question.
Adopted.
Floor amendment (1206h) failed.

The question being adoption of the committee report.
On a division vote, 155 members having voted in the affirmative and 197 in the negative, the
committee report failed.
The question now being adoption of the committee report.
Reps. Robert Wheeler and Weyler spoke in favor and yielded to questions.
Reps. Mirski and Soltani spoke in favor.

Rep. Vaillancourt offered floor amendment (1211h).

                                             Floor Amendment (1211h)
Reps. Jasper and Soltani spoke against.
Reps. Vaillancourt and Kennedy spoke in favor.
Rep. Biundo requested a roll call; sufficiently seconded.
The question being adoption of floor amendment (1211h).

                                                YEAS 90 NAYS 276

SB 24, relative to disposition upon death of patient accounts in nursing homes. OUGHT TO
PASS
Reps. Soltani and Rowe spoke in favor.
Rep. Sorg and Espiefs spoke against.
Rep. Boyce moved the previous question.
Adopted.
and floor amendment (1950h) failed.
\fRep. Rowe challenged the Chair's ruling on the voice vote on floor amendment (1950h).
Rep. Vaillancourt spoke against.
Reps. Rowe and Soltani spoke in favor.
Rep. Dokmo requested a roll call; sufficiently seconded.
The question being should the ruling of the Chair be upheld.

                                                YEAS 274 NAYS 17

HB 264-FN, relative to amendments and corrections to birth records. WITHOUT RECOMMENDATION
Statement in support of Ought to Pass: Currently, RSA 5-C:87, V allows transgender individuals to change
                                                                             Rep. Gerri Cannon
Statement in support of Inexpedient to Legislate: Birth certificates serve as documents of the facts of the
to Legislate.

                                                                             Rep. Leah Cushman

Rep. Cannon moved Ought to Pass and spoke in favor.
Rep. Cushman spoke against.
On a division vote, with 186 members having voted in the affirmative, and 190 in the negative, the motion
of Ought to Pass failed.

HB 1268-FN, establishing a net operating loss deduction in computing the business profits tax.
(Amendments printed in SJ 04/11/02 and 04/18/02)

Rep. Alukonis moved that the House concur, spoke in favor and yielded to questions.

Rep. Konys spoke in favor.

Adopted.

SB 197, relative to continuation of group health insurance in the event of divorce or legal
separation. MAJORITY: OUGHT TO PASS WITH AMENDMENT. MINORITY:
INEXPEDIENT TO LEGISLATE.
Majority amendment adopted.

The question now being adoption of the majority committee report of Ought to Pass with
Amendment.
Reps. Hunt and Martin spoke against.
\fReps. DeStefano and McLeod spoke in favor.
Rep. Wallner requested a roll call; sufficiently seconded.

                                               YEAS 227 NAYS 121

HB 1563, prohibiting physicians from prescribing or administering cannabis-
type drugs. MAJORITY: OUGHT TO PASS WITH AMENDMENT. MINORITY: OUGHT TO PASS
WITH AMENDMENT.
Rep. Emerton spoke against the Majority amendment.

The amendment failed.

Rep. Emerton offered a floor amendment.

Floor Amendment (0929h)

Amend the title of the bill by replacing it with the following:
Rep. Emerton spoke in favor and yielded to questions.

Rep. Boyce spoke in favor.

Adopted.

Report adopted and ordered to third reading.

SB 228-FN, relative to spousal benefits upon the death of certain retired group II members of the
New Hampshire retirement system. MAJORITY: OUGHT TO PASS WITH AMENDMENT.
MINORITY: INEXPEDIENT TO LEGISLATE.
Reps. Dyer and O'Neil spoke against.

The amendment failed.

Rep. Dyer offered a floor amendment.

                                                   Floor Amendment (3072h)

Amend the bill by replacing all after the enacting clause with the following:
Rep. Dyer spoke in favor.
\fAdopted.

Rep. Dyer spoke in favor of the report and yielded to questions.

Report adopted and referred to Finance.

                                       committee of conference report on scr 6
Committee of Conference Report on SCR 6, a resolution urging the President and Congress to
address the challenge of high prescription medication prices.
Recommendation:
Rep. Quandt spoke against.

Rep. Fields spoke in favor.

Adopted.
"""


# Cut from House Journals 10 of 2006, 16 of 2016, 4 and 11 of 2007, 28 of
# 2014 and 14 of 2012, as they stand in the file, a bill's heading cut to its
# first line.
_JOURNAL_WALK_MORE = """HB 1692-FN, establishing the New Hampshire sexual predators act. MAJORITY:
Reps. Batula and Wendelboe spoke in favor.
Reps. Knowles, Dowling and Soltani spoke against.

Rep. John Flanders moved the previous question.
\fMotion adopted.
Rep. Batula requested a roll call; sufficiently seconded.
The question being adoption of floor amendment (1487h).

                                                YEAS 86 NAYS 254

HB 1696-FN, requesting a modification of the New Hampshire health protection program. MAJORITY:
The question now being adoption of the majority committee report of Ought to Pass with Amendment.
Reps. Edelblut and Dan McGuire spoke against.
Reps. Lachance and Kotowski spoke in favor and yielded to questions.
Rep. Fromuth spoke against and yielded to questions.

                                                 MOTION TO LAY ON THE TABLE
Rep. Spillane moved that HB 1696-FN, requesting a modification of the New Hampshire health protection
program, be laid on the table.
Rep. Umberger requested a roll call; sufficiently seconded.
Rep. Spillane withdrew his motion.

The question now being adoption of the majority committee report of Ought to Pass with Amendment.

                                                     (Speaker Jasper in the Chair)

Rep. Joanne Ward spoke against.
Rep. Umberger spoke in favor and yielded to questions.

                                                    MOTION TO PRINT REMARKS

Rep. William O'Brien moved that the Parliamentary Inquiry made by Rep. Hoell and the answer by Speaker
Jasper be printed in the Permanent Journal.
Without objection, the Speaker so ordered.
The question now being adoption of the majority committee report of Ought to Pass with Amendment.
Rep. Comeau spoke against.
Rep. Stephen Schmidt spoke in favor.
Rep. Timothy Smith requested a roll call; sufficiently seconded.

                                             YEAS 207 - NAYS 136

HB 87, relative to the exceptions to compulsory school attendance. OUGHT TO PASS.
Rep. Sorg spoke against.
Rep. Dunn spoke in favor and yielded to questions.

Committee report adopted.
Ordered to third reading.

                                                      RESOLUTION
Reps. Wallner and Whalley offered the following: RESOLVED, that the House adopt
amendments to House Rules 30 and 64.
Reps. Wallner and Whalley spoke in favor.
\fAdopted.

HB 1570-FN, establishing a paint stewardship program.
The question now being adoption of floor amendment (1053h).
Rep. O'Connor spoke against and yielded to questions.

                                             MOTION TO SUSPEND HOUSE RULES
Rep. Vaillancourt moved that House Rules be so far suspended as to allow HB 1570-FN, establishing a paint
stewardship program, to be referred to the Committee on Ways and Means past the deadline.
Rep. Vaillancourt spoke in favor and yielded to questions.

Rep. Dumaine moved the previous question.
Rep. Gary Richardson requested a roll call; sufficiently seconded.

                                                   YEAS 188 NAYS 112

HB 235, relative to the recognition of out-of-state marriages. MAJORITY: OUGHT TO
The question being adoption of the majority committee report of Ought to Pass with
Amendment.
Reps. Garcia and Sorg spoke against.
Reps. Rowe and Lasky yielded to questions.
Reps. Pierce and Shurtleff spoke in favor.
Rep. DeChane moved the previous question.
On a division vote, 179 members having voted in the affirmative and 131 in the negative, the
motion to limit debate was adopted.
\f                                                         PROTEST
Under Article 24, Part 2 of the constitution, I protest these kinds of tactics which shut off
debate especially when some controversy seems to have been engendered.

                                                                          Rep. Vaillancourt

The question now being adoption of the majority committee report of Ought to Pass with
Amendment.
Rep. Dumaine requested a roll call; sufficiently seconded.

                                               YEAS 169 NAYS 171

HB 437-FN, relative to the definition of marriage. OUGHT TO PASS WITH
Rep. Simmons moved Inexpedient to Legislate.

Rep. Vaillancourt spoke in favor.

                                      MOTION TO LAY ON THE TABLE
Rep. LaCasse moved that the motion of Inexpedient to Legislate on HB 437-FN, relative to
definition of marriage, be laid on the table.
The Speaker ruled the motion out of order because the House was already in the voting mode
on the motion of Inexpedient to Legislate.

The question now being adoption of the motion of Inexpedient to Legislate.
Rep. Bates requested a roll call; sufficiently seconded.

                                               YEAS 211 NAYS 116
"""


@check("session", "a speech is tied to the decision of its own question, read past a "
       "Call of the House, the previous question and a failed motion to set it aside",
       needs=("journal_days", "session_days", "build_session_pages"))
def _session_speech_walk(JD, SD, BSP):
    """The third review of 3 October 2026 read every speaker the second pass
    put on a motion against the journal. A speech whose question was decided
    after another motion was moved fell through to the next roll call in the
    bill: Rep. Rowe spoke for HB 1670's committee amendment on 15 February
    2012, a Call of the House was moved, the amendment carried 177-99 on a
    division, and the roll call on Rep. Vaillancourt's floor amendment that
    followed, 96-179, named him; on HB 2 of 20 April 2005 and SB 24 of 26
    April 2006 the previous question and an appeal of the chair's ruling did
    the same. journal_days now reads what comes between (its walk): a Call of
    the House, and the previous question with its own decision, are read
    through; a motion to set the question aside is read past where it fails;
    anything else -- a motion, an amendment offered, an appeal -- ties the
    speech to nothing, and its speaker is named as having spoken during the
    bill.

    And four smaller readings, each from a name lost or garbled: a speaker's
    name that ran back over the committee statement's right-aligned signature
    ("Leah Cushman Rep. Cannon", HB 264 of 4 January 2024); "moved that the
    House concur, spoke in favor" (HB 1268, 25 April 2002), read by neither
    pattern; a bare "Adopted." deciding the amendment just offered, not the
    report (HB 1563, 5 March 1998); and a conference report's own heading,
    which opens its bill's stretch (SCR 6, 31 May 2000). The clerk's count a
    roll call is printed under can be one vote off its ballots, and the
    speeches before it still the roll call's (SB 197, 6 June 2007)."""
    attrs = JD.attributions(JD.clean(_JOURNAL_WALK, lines=True))
    by = {}
    for a in attrs:
        for n in a["names"]:
            by.setdefault((a["bill"], n, a["side"]), []).append(a)

    def one(bill, name, side):
        got = by.get((bill, name, side)) or []
        assert len(got) == 1, f"{name} ({side}) on {bill}: {got}"
        return got[0]

    def item(bill, action, kind, y=None, n=None, motion="MA", term="2011-2012"):
        return SD.Item(bill, term, {"type": "floor", "body": "H", "action": action,
                                    "motion": motion, "vote_kind": kind, "yeas": y, "nays": n,
                                    "raw": action}, 0)
    # HB 1670: a Call of the House is read through, to the division.
    assert one("HB1670", "Rowe", "for")["decided"] == {"count": (177, 99)} and \
        one("HB1670", "Vaillancourt", "against")["decided"] == {"count": (177, 99)}, (
        f"Rep. Rowe's speech on HB 1670's committee amendment is not closed by its "
        f"division: {one('HB1670', 'Rowe', 'for')}")
    fa = item("HB1670", "Adopt Floor Amendment 2012-0725h", "RC", "96", "179", "MF")
    report = item("HB1670", "Ought to Pass with Amendment #0518h", "RC", "180", "95")
    assert BSP.speakers_for(attrs, "HB1670", fa)[0] == {"for": ["Vaillancourt"],
                                                         "against": ["Hess"]} and \
        BSP.unplaced(attrs, "HB1670", [fa, report]) == [], (
        "HB 1670's floor amendment names a speaker of its committee amendment: "
        f"{BSP.speakers_for(attrs, 'HB1670', fa)[0]}")
    # HB 2 of 2005: the previous question and its "Adopted." are read
    # through to the amendment's failure; an amendment offered after a
    # speech ties it to nothing.
    for n, side in (("Wendelboe", "for"), ("Ryan", "against"), ("Hagan", "for")):
        assert one("HB2-FN-A", n, side)["decided"] == {"words": "Floor amendment (1206h) failed."}, (
            f"Rep. {n}'s speech on floor amendment 1206h is not closed by its failure: "
            f"{one('HB2-FN-A', n, side)}")
    for n in ("Robert Wheeler", "Weyler", "Mirski"):
        assert one("HB2-FN-A", n, "for")["decided"] == {"untied": True}, (
            f"Rep. {n} spoke on HB 2's report before floor amendment 1211h was offered, "
            f"and is tied to {one('HB2-FN-A', n, 'for')}")
    fa = item("HB2", "Adopt Floor Amendment 1211", "RC", "90", "276", "MF", "2005-2006")
    rep = item("HB2", "Ought to Pass with Amendment", "", motion="MF", term="2005-2006")
    assert BSP.speakers_for(attrs, "HB2", fa)[0] == {"for": ["Vaillancourt", "Kennedy"],
                                                     "against": ["Jasper", "Soltani"]} and \
        BSP.unplaced(attrs, "HB2", [fa, rep]) == ["Hagan", "Mirski", "Robert Wheeler", "Ryan",
                                                   "Soltani", "Wendelboe", "Weyler"], (
        f"HB 2's floor amendment 1211h: {BSP.speakers_for(attrs, 'HB2', fa)[0]}; "
        f"also spoke {BSP.unplaced(attrs, 'HB2', [fa, rep])}")
    # SB 24 of 2006: an appeal of the chair's ruling is a question of its own.
    ruling = item("SB24", "Sustain Ruling of Chair: Result", "RC", "274", "17", term="2005-2006")
    otp = item("SB24", "Ought to Pass", "VV", term="2005-2006")
    assert one("SB24", "Sorg", "against")["decided"] == {"untied": True} and \
        BSP.speakers_for(attrs, "SB24", ruling)[0] == {"for": ["Rowe", "Soltani"],
                                                       "against": ["Vaillancourt"]} and \
        BSP.unplaced(attrs, "SB24", [ruling, otp]) == ["Espiefs", "Rowe", "Soltani", "Sorg"], (
        "the speeches on SB 24's floor amendment 1950h are named on the ruling of the chair: "
        f"{BSP.speakers_for(attrs, 'SB24', ruling)[0]}")
    # HB 264 of 2024: no name runs back over a signature; HB 1268 of 2002:
    # the comma form is read.
    names = [n for a in attrs for n in a["names"]]
    assert {n for a in attrs if a["bill"] == "HB264-FN" for n in a["names"]} == \
        {"Cannon", "Cushman"} and not [n for n in names if "Rep" in n or n.endswith(" and")], (
        f"a speaker's name holds another member's: {[n for n in names if 'Rep' in n]}")
    alu = one("HB1268-FN", "Alukonis", "for")
    assert alu["inline_motion"] == "that the House concur" and \
        alu["decided"] == {"words": "Adopted."}, f"Rep. Alukonis's motion is not read: {alu}"
    assert JD._names("Abramson and Comtois and") == ["Abramson", "Comtois"] and \
        JD._names("W. Douglas Scamman, Jr") == ["W. Douglas Scamman"], (
        "a dangling 'and', or a 'Jr', is read as a name")
    # SB 197 of 2007: the journal's 227-121 over roll call 140, 227-122.
    rc = item("SB197", "Ought to Pass with Amendment #1911h", "RC", "227", "122",
              term="2007-2008")
    rc.rc = {"year": "2007", "body": "H", "number": 140, "yeas": 227, "nays": 122}
    want = {"for": ["DeStefano", "McLeod"], "against": ["Hunt", "Martin"]}
    assert BSP.speakers_for(attrs, "SB197", rc)[0] == {"for": [], "against": []} and \
        BSP.speakers_for(BSP.clerk_counts(attrs, [rc]), "SB197", rc)[0] == want, (
        "the speeches before SB 197's roll call, which the journal prints one vote off its "
        f"ballots, are not its: {BSP.speakers_for(BSP.clerk_counts(attrs, [rc]), 'SB197', rc)[0]}")
    # HB 1563 of 1998 and SB 228 of 2000: a bare "Adopted." after an
    # amendment is offered is the amendment's; a failed amendment is not
    # the report's.
    assert one("HB1563", "Emerton", "for")["decided"] == {"words": "Adopted.", "amendment": True}
    rep = item("HB1563", "Ought to Pass with Amendment", "VV", term="1997-1998")
    assert BSP.speakers_for(attrs, "HB1563", rep, sole=True)[0] == {"for": [], "against": []} \
        and BSP.unplaced(attrs, "HB1563", [rep]) == ["Boyce", "Emerton"], (
        "the speeches on HB 1563's floor amendment are named on the report: "
        f"{BSP.speakers_for(attrs, 'HB1563', rep, sole=True)[0]}")
    rep = item("SB228", "Ought to Pass with Amendment", "VV", term="1999-2000")
    assert BSP.speakers_for(attrs, "SB228", rep, sole=True)[0] == {"for": ["Dyer"],
                                                                    "against": []} and \
        BSP.unplaced(attrs, "SB228", [rep]) == ["Dyer", "O'Neil"], (
        "SB 228's report names a speaker of its amendments: "
        f"{BSP.speakers_for(attrs, 'SB228', rep, sole=True)[0]}")
    # SCR 6 of 2000: the conference report's heading opens its stretch, and
    # a bare "Adopted." decides it.
    q = one("SCR6", "Quandt", "against")
    assert q["decided"] == {"words": "Adopted."}, f"SCR 6's conference report: {q}"
    # And read through read_year, as the build reads it: a bill heading after
    # a running head starts its bill (HB 422 of 13 February 2025).
    root = Path(tempfile.mkdtemp())
    try:
        (root / "2025").mkdir()
        (root / "2025" / "HJ 05 February 13, 2025.txt").write_text(
            "HOUSE JOURNAL NO. 5\n\nThursday, February 13, 2025\n\n"
            + _JOURNAL_DECIDED.split("HB 94-FN")[0], encoding="utf-8")
        got = JD.read_year("2025", root).get("2025-02-13") or {}
    finally:
        shutil.rmtree(root, ignore_errors=True)
    don = [a["bill"] for a in got.get("attributions", []) if "Donnelly" in a["names"]]
    assert don == ["HB422-FN"], f"read_year puts Rep. Donnelly on {don}"
    more = JD.attributions(JD.clean(_JOURNAL_WALK_MORE, lines=True))
    dec = {(a["bill"], n): a["decided"] for a in more for n in a["names"]}
    # HB 1692 of 2006: the previous question's "Motion adopted." after a page
    # break is its own, and the roll call after it the amendment's.
    assert dec[("HB1692-FN", "Batula")] is None and dec[("HB1692-FN", "Soltani")] is None, (
        f"the speeches on HB 1692's floor amendment are not its roll call's: {dec}")
    # HB 1696 of 2016: a tabling withdrawn, and remarks ordered printed, leave
    # the report the question; the roll call after them is the report's.
    for n in ("Edelblut", "Lachance", "Fromuth", "Joanne Ward", "Umberger", "Comeau"):
        assert dec[("HB1696-FN", n)] is None, (
            f"Rep. {n}'s speech on HB 1696's report is not tied to its roll call: "
            f"{dec[('HB1696-FN', n)]}")
    # HB 87 of 2007: the resolution offered after it is no part of the bill.
    assert {a["bill"] for a in more if "Wallner" in a["names"]} == {None} and \
        dec[("HB87", "Dunn")] == {"words": "Committee report adopted."}, (
        "the speeches on a resolution offered from the floor are read as HB 87's")
    # HB 1570 of 2014: what decides a previous question the journal does not
    # say, so the roll call after it ties no speech made before it.
    assert dec[("HB1570-FN", "Vaillancourt")] == {"untied": True}, (
        f"a speech before an unlabelled roll call after the previous question is "
        f"tied: {dec[('HB1570-FN', 'Vaillancourt')]}")
    # HB 1417 of 5 March 1998: "Rep. Daniels spoke against the Majority
    # report. The report failed." is no speech on the Ought to Pass with
    # Amendment the House then adopted, its one motion that day.
    rep = item("HB1417", "Ought to Pass with Amendment", "VV", term="1997-1998")
    against = [{"bill": "HB1417", "side": "against", "names": ["Daniels"], "tally": None,
                "inline_motion": None, "moved_since": [], "decided": {"words": "The report failed."}}]
    assert BSP.speakers_for(against, "HB1417", rep, sole=True)[0] == {"for": [], "against": []}, (
        "a speech the journal closes with a verdict the other way is put on the one motion")
    # HB 235 of 2007: the previous question's division says after its count
    # that it was the motion to limit debate; HB 437 of 2012: a tabling the
    # chair ruled out of order was never put.
    assert dec[("HB235", "Pierce")] is None and dec[("HB437-FN", "Vaillancourt")] is None, (
        f"a speech is untied by a motion decided or ruled out of order before its own "
        f"roll call: {dec[('HB235', 'Pierce')]}, {dec[('HB437-FN', 'Vaillancourt')]}")
    # And the readings of the journal's own words these rest on.
    assert [(int(m.group("yeas")), int(m.group("nays"))) for m in JD.DIVISION.finditer(
        "On a division vote, 185 members having voted in the affirmative, 107 in the negative, "
        "the majority report was adopted. On a division vote,273 members having voted in the "
        "affirmative and 65 in the negative. On a division vote, 268 members having spoken in the "
        "affirmative and 42 in the negative")] == [(185, 107), (273, 65), (268, 42)] and \
        [m.groups() for m in SD.JOURNAL_DIVISION.finditer(
            "division vote, 185 members having voted in the affirmative, 107 in the negative")] \
        == [("185", "107")], "a division the journal prints in a rarer wording is not read"
    assert JD.NOT_DECIDED.search("Osgood, Philip Sr    Converse, Larry    Donovan, Thomas and "
                                 "the committee report was adopted.") and \
        JD.NOT_DECIDED.search("Jillette, Arthur Jr and the motion failed.") and \
        JD.SUBSIDIARY.search("moved that HR 26, expressing regret ..., be special ordered to the "
                             "next session day in its Regular Calendar order.") and \
        BSP._motion_kind("House Refuses to Accede to Senate Request for C of C (Rep Bates)") == \
        BSP._motion_kind("that the House refuse to accede") == "accede" and \
        not JD.NOT_DECIDED.search("Adopted and the bill ordered to third reading.") and \
        not JD.NOT_DECIDED.search("Majority committee report adopted and ordered to third "
                                  "reading."), (
        "a roll call's names are read as a decision, \"special ordered\" as no motion to set "
        "aside (HR 26, 13 February 2008), or a refusal to accede as a conference motion (SB 193, "
        "8 June 2011)")
    return "ok", ("a Call of the House and the previous question are read through, a "
                  "question put after a speech unties it, a name is one member's, a bare "
                  "verdict after an amendment is offered is the amendment's, a conference "
                  "report opens its bill, and the clerk's count one off still ties")


@check("session", "a speech is placed on a bill's motion only where the journal puts it there",
       needs=("journal_days", "session_days", "build_session_pages"))
def _session_speech_on_its_motion(JD, SD, BSP):
    """When HB 605 came off 14 April 1999's consent calendar its page entry
    said Reps. Nancy Wall, "and Dickinson", Weber and Mock spoke for killing
    it and Belvin and MacGillivray against. Five of them spoke on HB 737's
    reconsideration, which follows HB 605 in the journal with no bill heading
    between; Mock spoke for his own motion to recommit, which the record does
    not hold, under the one motion it does. A reconsideration of another bill
    now ends the bill before it; a speaker's own "moved ..." of a different
    kind of motion is named as speaking during the bill and no more; and a
    comma before "and" is one separator. A bill's reconsideration of itself
    stays its own."""
    import html as _html
    attrs = JD.attributions(JD.clean(_JOURNAL_RECONSIDER))
    by = {n: a["bill"] for a in attrs for n in a["names"]}
    assert all(by.get(n) is None for n in ("Nancy Wall", "Dickinson", "Weber", "Belvin",
                                           "MacGillivray")), (
        f"the speeches on HB 737's reconsideration were read as another bill's: {by}")
    assert not any(n.lower().startswith("and ") for n in by), (
        f"a comma before 'and' left a member called {[n for n in by if n.lower().startswith('and ')]}")
    assert by.get("Mock") == "HB605-FN" and by.get("Hager") == "HB1-A", (
        f"a bill lost its own speeches, or its own reconsideration's: {by}")
    assert BSP._same_motion("Ought to Pass", "Ought to Pass with Amendment") and \
        BSP._same_motion("that the House concur", "House Concurs with Senate Amendment 2024") and \
        BSP._same_motion("Recommit to Committee", "Recommitted to Finance") and \
        BSP._same_motion("something unread", "Inexpedient to Legislate") and \
        not BSP._same_motion("that the House nonconcur", "House Concurs with Senate Amendment") and \
        not BSP._same_motion("Re-commit to Committee", "Inexpedient to Legislate"), (
        "motions of one kind read as different, or different kinds as one")

    def ev(date, raw, typ, **kw):
        return {"date": date, "body": "H", "type": typ, "raw": raw, **kw}
    narr = {"1999-2000": {"HB605": {"events": [
        ev("1999-04-06", "Maj Report ITL for Apr 14 (vote 13-1)", "report"),
        ev("1999-04-14", "ITL Report adopted", "floor", action="Inexpedient to Legislate",
           motion="MA", vote_kind="VV")]}}}
    root = Path(tempfile.mkdtemp())
    try:
        (root / "narratives.json").write_text(json.dumps(narr), encoding="utf-8")
        day = SD.load(root / "narratives.json", journals={})[("H", "1999-04-14")]
        nobody = type("Nobody", (), {"slug": lambda self, body, name: None})()
        page = BSP.render(day, {"attributions": attrs}, {}, {}, nobody, _html.escape)[0]
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
        claimed = " ".join(re.findall(r"Spoke (?:for|against) the motion(.*?)(?:Spoke|The motion|Taken|$)", txt))
        assert not any(n in txt for n in ("Wall", "Dickinson", "Weber", "Belvin", "MacGillivray")), (
            "HB 605's entry names members who spoke on HB 737: " + txt[:300])
        assert "Mock" not in claimed and re.search(r"Also spoke during this bill\s+Rep\. Mock", txt), (
            "Rep. Mock, who moved to recommit, is listed as speaking on the motion to kill: "
            + txt[:300])
        return "ok", ("HB 737's speakers are on no other bill; Mock's recommittal is not "
                      "the motion to kill; HB 1-A keeps its own reconsideration")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("session", "a motion the docket records as lost (ML) says it failed on its sitting page",
       needs=("session_days", "build_session_pages"))
def _session_motion_lost(SD, BSP):
    """ML is "motion lost", the House docket's usual word where the Senate's
    is MF, and session_days read only MA and MF. Every ML motion -- 260 on 1
    October 2026, 2006's HB 1240 among them, whose passage failed 141-181 on
    15 February -- was drawn with "On the motion: Ought to Pass with
    Amendment" and no outcome at all, and the 1999-2006 reader had just moved
    29 House motions from a wrong "adopted" to ML."""
    e = {"type": "floor", "action": "Ought to Pass with Amendment", "motion": "ML",
         "vote_kind": "RC", "yeas": "141", "nays": "181",
         "raw": "Passed with AM {0795h},  ML,  RC (141-181)   HJ 19, pg 1154-1156"}
    it = SD.Item("HB1240", "2005-2006", e, 0)
    assert it.carried is False, f"a House ML is read as {it.carried!r}, not as failed"
    assert it.outcome_words.startswith("The motion failed on a roll call"), it.outcome_words
    assert BSP.vote_payload(it)["passed"] is False
    assert SD.Item("HB1", "2005-2006", {**e, "motion": "MA"}, 0).carried is True
    assert SD.Item("HB1", "2005-2006", {**e, "motion": "MF"}, 0).carried is False
    return "ok", "ML, MF and MA each say what happened to the motion"


@check("session", "a motion to suspend the rules is drawn against two thirds, not a majority",
       needs=("session_days", "build_session_pages", "motions"))
def _session_suspend_two_thirds(SD, BSP, MO):
    """The person, 10 October 2026: "Suspend the Rules for transmittal",
    failed 181-121 on a roll call, drawn with its mark at half, so the ring
    said the losing side had won. Its head says "needs two thirds", and the
    ring now marks 202 of 302. A line that names its own fraction keeps it,
    and another motion keeps a majority."""
    e = {"type": "floor", "action": "Suspend the Rules for transmittal", "motion": "MF",
         "vote_kind": "RC", "yeas": "181", "nays": "121",
         "raw": "Suspend the Rules for transmittal, MF, RC 181-121"}
    it = SD.Item("HB1", "2023-2024", e, 0)
    mk = MO.classify(it.action, "HB1", "H")["mk"]
    assert mk == "suspend_rules", f"the motion reads as {mk!r}"
    got = BSP.vote_payload(it, mk)["threshold_needed"]
    assert got == 202, f"a suspension 181-121 is drawn needing {got}, not 202 (two thirds of 302)"
    assert BSP.vote_payload(it)["threshold_needed"] == 152, "without its kind it is a majority"
    ot = SD.Item("HB1", "2023-2024", {**e, "action": "Ought to Pass", "raw": "OTP, MF, RC 181-121"}, 0)
    assert BSP.vote_payload(ot, MO.classify("Ought to Pass", "HB1", "H")["mk"])["threshold_needed"] == 152
    return "ok", "a suspension 181-121 needs 202; Ought to Pass on the same count needs 152"


def _motions(day, bill):
    return [(i.action, i.mover, i.kind, i.yeas, i.nays, i.carried)
            for i in day.items if i.bill == bill]


@check("session", "a vote is drawn as the question its own clause names, with the result its own words give",
       needs=("session_days", "build_session_pages"))
def _session_clause_names_question(SD, BSP):
    """The review of 3 October 2026 found votes drawn under a question their
    line does not give them, each from rows of the record:

      - nine failed veto overrides of 1997-1998 drawn as overridden, because
        "OVERRIDE GOV VETO, ML RC(17-299)" (HB 149, 25 June 1997) was read
        for "overrid" and the motion's own name matched;
      - a count before 1999 bound to the line's final disposition: "OTP/AM
        ML RC(45-241); ITL REPORT ADOPTED" (HB 386, 3 January 1996) drawn as
        the report of Inexpedient to Legislate adopted 45 to 241;
      - a Senate row about an amendment holding another question's roll
        call: "Sen. Larsen Floor Amendment {0965}, AA, VV, OT3rdg, RC
        14Y-8N, MA" (HB 117, 22 April 1999), the file's "Third Reading Final
        Passage", drawn as the amendment adopted on the roll call;
      - a motion to divide drawn as the amendment it would divide: "Rep
        Vaillancourt moved to Div ? on Maj Am, ML RC(20-338)" (HB 375, 3 May
        2001), the file's "REP VAILLANCOURT: DIVIDE THE QUESTION";
      - a division the line counts drawn as a voice vote with a count:
        "Ought to Pass: Div. 16Y-8N, MA, VV; OT3rdg" (HB 1723, 2 May 2012)."""
    def veto(raw):
        return SD.Item("HB1", "1997-1998", {"type": "veto_override", "body": "H",
                                            "raw": raw}, 0).carried
    rows = {"OVERRIDE GOV VETO, ML RC(17-299); HJ79,P2183-2186": False,
            "OVERRIDE GOV VETO, ML <FAILED 2/3> RC(14-10); SJ24,P629-631": False,
            "OVERRIDE GOV'S VETO, FAILED 2/3RC(195-132); HJ60,P2215-2218": False,
            "OVERRIDE GOVERNOR'S VETO FAILS 2/3 RC(18-306); HJ64,P2275-2278": False,
            "VETO OVERRIDDEN (BECAME LAW WITHOUT SIGNATURE) 09/15/93": True,
            "Veto Overridden 08/19/2026: RC 257-44 by Required Two-Thirds Vote": True,
            "Notwithstanding the Governor's Veto, Shall SB 468 Become Law: RC 16Y-8N, "
            "Veto Overridden by necessary 2/3 vote": True,
            "Notwithstanding the Governor's Veto, Shall SB 213 Become Law: RC 0Y-24N, "
            "Veto Sustained, lacking necessary 2/3 vote": False}
    wrong = {r: veto(r) for r, want in rows.items() if veto(r) is not want}
    assert not wrong, f"a veto override's result is read from the wrong words: {wrong}"
    assert SD.Item("HB1723", "2011-2012", {"type": "floor", "body": "S",
                                           "action": "Ought to Pass", "motion": "MA",
                                           "vote_kind": "VV", "yeas": "16", "nays": "8",
                                           "raw": "Ought to Pass: Div. 16Y-8N, MA, VV; OT3rdg"},
                   0).kind == "DV", "a division the line counts is drawn as a voice vote"
    # The Senate's "DIV" and "DIV.", read as a division and taken out of the
    # words (SB 284, 20 March 2025; SB 468, 26 March 2026).
    for action, raw, want in (
            ("Ought to Pass: DIV 15Y-8N", "Ought to Pass: DIV 15Y-8N, MA; OT3rdg; 03/20/2025",
             ("DV", 15, 8, "Ought to Pass")),
            ("Refer to Interim Study, DIV. 6Y-18N",
             "Refer to Interim Study, DIV. 6Y-18N, MF; 03/26/2026",
             ("DV", 6, 18, "Refer to Interim Study"))):
        it = SD.Item("SB284", "2025-2026", {"type": "floor", "body": "S", "action": action,
                                            "motion": "MA", "vote_kind": "", "raw": raw}, 0)
        got = (it.kind, it.yeas, it.nays, it.action)
        assert got == want, f"the Senate's division is not read from {raw!r}: {got}"

    def floor(date, body, raw, **e):
        return dict({"type": "floor", "date": date, "body": body, "raw": raw}, **e)
    narr = {"1995-1996": {"HB386": [floor(
                "1996-01-03", "H", "COMM AM, AA VV; OTP/AM ML RC(45-241); ITL REPORT ADOPTED, REP A",
                action="Inexpedient to Legislate", motion="MA", vote_kind="")]},
            # the same with the count in the row's fields, as the reader
            # gives a line whose one count it took for the line's motion
            "1989-1990": {"HB216": [floor(
                "1990-02-01", "H", "REP HAYNES SUBST OTP/A, ML RC(125-222); REFERRED TO INTERIM STUDY",
                action="Refer for Interim Study", motion="MA", vote_kind="RC", yeas="125",
                nays="222")]},
            "1999-2000": {
                "HB117": [floor("1999-04-22", "S", "Sen. Trombly Suspended Rules to Consider MA, "
                                "2/3 nec. VV", action="Sen. Trombly Suspended Rules to Consider",
                                motion="MA", vote_kind="VV"),
                          {"type": "amendment", "date": "1999-04-22", "body": "S", "motion": "AA",
                           "vote_kind": "VV", "amend_kind": "Floor Amendment",
                           "raw": "Sen. Larsen Floor Amendment {0965}, AA, VV, OT3rdg, RC 14Y-8N, MA"}]},
            "2001-2002": {"HB375": [
                {"type": "other", "date": "2001-05-03", "body": "H",
                 "raw": "Rep Vaillancourt moved to Div ? on Maj Am, ML RC(20-338)"},
                {"type": "amendment", "date": "2001-05-03", "body": "H", "motion": "AL",
                 "vote_kind": "RC", "amend_kind": "Maj Am", "raw": "Maj Am{1054}, AL RC(174-185)"},
                floor("2001-05-03", "H", "Rep Dokmo moved OTP, Passed RC(228-132)",
                      action="Ought to Pass", motion="MA", vote_kind="RC", yeas="228", nays="132")]}}
    rolls = {"1999-2000": {"HB117": [_rc("1999", "S", 39, "1999-04-22", "HB117",
                                         "Third Reading Final PassageRoberge/Krueger", 14, 8, True)]},
             "2001-2002": {"HB375": [
                 _rc("2001", "H", 104, "2001-05-03", "HB375", "REP VAILLANCOURT:  DIVIDE THE QUESTION",
                     20, 338, False),
                 _rc("2001", "H", 105, "2001-05-03", "HB375", "COMMITTEE MAJORITY AMENDMENT {1054}",
                     174, 185, False),
                 _rc("2001", "H", 107, "2001-05-03", "HB375", "REP DOKMO:  OTP", 228, 132, True)]}}
    days = _sitting_fixture(SD, narr, rolls)
    h386 = [m for m in _motions(days[("H", "1996-01-03")], "HB386")]
    assert ("Ought to Pass with Amendment", "", "RC", 45, 241, False) in h386 and \
        ("Inexpedient to Legislate", "", "", None, None, True) in h386, (
        f"HB 386's 45-241 is not the failed Ought to Pass with Amendment its clause names: {h386}")
    h216 = [(a, k, y, n, c) for a, _m, k, y, n, c in _motions(days[("H", "1990-02-01")], "HB216")]
    assert ("Refer for Interim Study", "", None, None, True) in h216 and \
        any(k == "RC" and (y, n, c) == (125, 222, False) for a, k, y, n, c in h216), (
        f"HB 216's 125-222, its substitute motion's, is drawn under the interim study: {h216}")
    h117 = [(a, k, y, n, c) for a, _m, k, y, n, c in _motions(days[("S", "1999-04-22")], "HB117")]
    assert ("Order to Third Reading", "RC", 14, 8, True) in h117 and \
        not any(a.startswith("Adopt") for a, *_ in h117), (
        f"HB 117's third reading is drawn as its floor amendment: {h117}")
    h375 = [(a, k, y, n, c) for a, _m, k, y, n, c in _motions(days[("H", "2001-05-03")], "HB375")]
    assert ("Divide the question", "RC", 20, 338, False) in h375 and \
        sum(1 for a, *_ in h375 if "Amendment" in a) == 1, (
        f"HB 375's motion to divide is drawn as the amendment: {h375}")

    # The third review's: the motion to divide worded as the part divided
    # (HB 544, 8 January 2014); the Senate's re-referral after an amendment
    # adopted by voice (HB 625, 3 November 1999); the 1989-1998 clerk's
    # "FAILS 3/5" in the clause that holds the count (CACR 20, 11 February
    # 1992); and an override carried in one chamber is not a law.
    narr2 = {"2013-2014": {"HB544": [
                {"type": "amendment", "date": "2014-01-08", "body": "H", "motion": "",
                 "vote_kind": "DV", "amend_kind": "Floor Amendment",
                 "raw": "Floor Amendment #2014-0025h, Divide Sections 1-8 (Rep. Jasper) MF RC 160-183"},
                {"type": "amendment", "date": "2014-01-08", "body": "H", "motion": "",
                 "vote_kind": "", "amend_kind": "Floor Amendment",
                 "raw": "Floor Amendment #2014-0025h (New Title) MA RC 186-155"}]},
            "1999-2000": {"HB625": [
                {"type": "amendment", "date": "1999-11-03", "body": "S", "motion": "AA",
                 "vote_kind": "VV", "amend_kind": "Floor Amendment", "mover": "Sen Johnson",
                 "raw": "Sen Johnson Floor Amendment, {2227}, AA, VV, Sen Below Moved Rerefer, "
                        "RC 8Y-14N, MF"}]},
            "1991-1992": {"CACR20": [floor(
                "1992-02-11", "H", "COMM AM, AA DIV(173-141); 3RD READING FAILS 3/5 RC(197-126)",
                action="Adopt Committee Amendment", motion="AA", vote_kind="")]}}
    rolls2 = {"2013-2014": {"HB544": [
                _rc("2014", "H", 4, "2014-01-08", "HB544", "Divide Sect 1-8", 160, 183, False),
                _rc("2014", "H", 6, "2014-01-08", "HB544", "Adopt #14-0025h", 186, 155, True)]},
             "1999-2000": {"HB625": [_rc("1999", "S", 113, "1999-11-03", "HB625",
                                         "Re-Refer Disnard/Francouer", 8, 14, False)]}}
    days2 = _sitting_fixture(SD, narr2, rolls2)
    h544 = [(a, m, k, y, n, c) for a, m, k, y, n, c in _motions(days2[("H", "2014-01-08")], "HB544")]
    assert ("Divide the question", "Rep. Jasper", "RC", 160, 183, False) in h544 and \
        sum(1 for a, *_ in h544 if a.startswith("Adopt")) == 1, (
        f"HB 544's motion to divide is drawn as sections of the amendment: {h544}")
    h625 = _motions(days2[("S", "1999-11-03")], "HB625")
    assert any((m, y, n, c) == ("Sen. Below", 8, 14, False) for a, m, k, y, n, c in h625) and \
        not any(a.startswith("Adopt") and y for a, m, k, y, n, c in h625), (
        f"HB 625's re-referral is drawn as its floor amendment: {h625}")
    third = [i for i in days2[("H", "1992-02-11")].items if (i.yeas, i.nays) == (197, 126)]
    assert third and third[0].fifths and third[0].threshold_unknown, (
        "CACR 20's third reading, which failed for want of three fifths, is drawn at a majority")
    once = SD.Item("SB434", "2025-2026", {"type": "veto_override", "body": "S",
                                          "raw": "Veto Overridden 08/19/2026: RC 16Y-8N by "
                                                 "Required Two-Thirds Vote"}, 0)
    assert once.carried and "in this chamber" in once.outcome_words and \
        "became law" not in once.outcome_words, (
        f"one chamber's override is said to make the bill law: {once.outcome_words}")

    # And on the page: a vote no roll call on record is tied to has no
    # ballots anywhere, and a bill taken off the consent calendar is said to
    # have come off and no more.
    import html as _html
    nobody = type("Nobody", (), {"slug": lambda self, body, name: None})()
    page = BSP.render(days[("H", "1996-01-03")], {"attributions": []}, {},
                      {("1995-1996", "HB386"): 1996}, nobody, _html.escape)[0]
    assert "Who voted which way" not in page, (
        "a roll call the docket alone states points at ballots no page holds")
    cons = SD.Item("HB189", "2013-2014", {"type": "floor", "body": "H", "action": "Ought to Pass",
                                          "motion": "MA", "vote_kind": "VV", "raw": "OTP"}, 0)
    note = BSP.consent_html([cons], ["HB679"], {}, {}, _html.escape)
    assert "HB 679 was removed from the consent calendar." in note and "debated" not in note \
        and "request" not in note and "told below" not in note, (
            f"the consent calendar's note says more than the record: {note}")
    return "ok", ("veto results read from the result words; a count bound to its own "
                  "clause; a Senate amendment row's third reading and a motion to divide "
                  "drawn as themselves; a counted division never a voice vote; no ballots "
                  "pointer without a roll call; a removal said and no more")


# Real rows, as narrative.py reads them (body, date, the type the reader gives
# the row, raw): Docket.txt 25128 and 25153 (HB 1102 of 2026), 25146 and 25149
# (SB 434); Docket_db_2011-2012.txt 2320-2321 (SB 88), 6971-6972 (SB 57) and
# 5920 (HB 542, which puts the House's sitting of 30 November 2011 on the
# record); Docket_2019-2020.txt 9956-9958 (HB 455). The reader types the
# Senate's row of HB 455 and the House's of SB 57 "other", and each reaches its
# sitting through the roll call on record (_OVERRIDE_ROLLS, rollcalls.json).
_OVERRIDES = {
    ("HB1102", "2025-2026"): [
        ("H", "2026-08-19", "veto_override", "Veto Overridden 08/19/2026: RC 231-88 by Required Two-Thirds Vote"),
        ("S", "2026-08-19", "veto_override", "Notwithstanding the Governor's Veto, Shall HB 1102 Become Law: "
                                             "RC 24Y-0N, Veto Overridden by necessary two-thirds vote; 08/19/2026")],
    ("SB434", "2025-2026"): [
        ("H", "2026-08-19", "veto_override", "Veto Sustained 08/19/2026: RC 165-140 Lacking Necessary Two-Thirds Vote"),
        ("S", "2026-08-19", "veto_override", "Notwithstanding the Governor's Veto, Shall SB 434 Become Law: "
                                             "RC 16Y-8N, Veto Overridden by necessary two-thirds vote; 08/19/2026")],
    ("SB88", "2011-2012"): [
        ("S", "2011-09-07", "veto_override", "Notwithstanding the Governor’s Veto, Shall SB 88 Become Law: "
                                             "RC 17Y-7N, Veto Overridden by required two-thirds vote"),
        ("H", "2011-09-14", "veto_override", "Veto Overridden: RC 251-111 by Required Two-Thirds")],
    ("HB455", "2019-2020"): [
        ("H", "2019-05-23", "veto_override", "Veto Overridden 05/23/2019: RC 247-123 by Required Two-Thirds Vote"),
        ("S", "2019-05-30", "other", "Notwithstanding the Governor's Veto, Shall HB 455-FN Become Law: RC 16Y-8N, "
                                     "Veto Overridden by necessary two-thirds vote; 05/30/2019"),
        ("H", "2019-05-30", "other", "Veto Overriden 05/30/2019: Eff: 05/30/2019; Chapter 42")],
    ("SB57", "2011-2012"): [
        ("S", "2011-09-07", "veto_override", "Notwithstanding the Governor’s Veto, Shall SB 57 Become Law:  "
                                             "RC 17Y-7N, Veto Overridden by required two-thirds vote"),
        # Dated by its own "done during 1/4/2012" (docket_vocab, decision 59h),
        # the day of its roll call 270.
        ("H", "2012-01-04", "other", "Veto Overriden: RC 248-123 By Required Two-Thirds Vote, [done during "
                                     "1/4/2012 morning veto session]")],
    ("HB542", "2011-2012"): [
        ("H", "2011-11-30", "veto_override", "Shall HB542 Become Law: Veto Sustained, RC 244-130, Lacking "
                                             "Required Two-Thirds Vote")],
}
# rollcalls.json's roll calls of those two (year, body, number, date, question,
# yeas, nays): SB 57's House vote is of 4 January 2012, as its row says.
_OVERRIDE_ROLLS = {
    ("HB455", "2019-2020"): [("2019", "H", 201, "2019-05-23", "Veto Override", 247, 123),
                             ("2019", "S", 163, "2019-05-30", "Veto Override", 16, 8)],
    ("SB57", "2011-2012"): [("2011", "S", 101, "2011-09-07",
                             "Notwithstanding the Governor's veto shall the bill become law?", 17, 7),
                            ("2011", "H", 270, "2012-01-04", "SHALL SB 57 BECOME LAW", 248, 123)],
}
_OVERRIDES_SAID = {
    ("HB1102", "H"): "the veto was overridden in this chamber and, the same day, in the Senate, "
                     "so the bill became law.",
    ("HB1102", "S"): "the veto was overridden in this chamber and, the same day, in the House, "
                     "so the bill became law.",
    ("SB434", "H"): "the veto was sustained, so the bill did not become law.",
    ("SB434", "S"): "the veto was overridden in this chamber.",
    ("SB88", "S"): "the veto was overridden in this chamber and, on September 14, 2011, in the House, "
                   "so the bill became law.",
    ("SB88", "H"): "the veto was overridden in this chamber and, on September 7, 2011, in the Senate, "
                   "so the bill became law.",
    ("HB455", "H"): "the veto was overridden in this chamber and, on May 30, 2019, in the Senate, "
                    "so the bill became law.",
    ("HB455", "S"): "the veto was overridden in this chamber and, on May 23, 2019, in the House, "
                    "so the bill became law.",
    # The House's row and its roll call agree on 4 January 2012, the day the
    # row says the vote was done (decision 59h), so both pages say the day.
    ("SB57", "H"): "the veto was overridden in this chamber and, on September 7, 2011, in the Senate, "
                   "so the bill became law.",
    ("SB57", "S"): "the veto was overridden in this chamber and, on January 4, 2012, in the House, "
                   "so the bill became law.",
}


@check("session", "a veto override the other chamber carried too says the bill became law, on "
                  "both chambers' sitting pages", needs=("session_days",))
def _session_both_overrides(SD):
    """Decision 46, the person's word of 6 October 2026. A sitting page says
    of a carried override "the veto was overridden in this chamber" and no
    more, because one chamber's override does not make a law (SB 434 of 2026:
    overridden 16-8 by the Senate, sustained 165-140 by the House). Where the
    other chamber's override is on record too it made the bill law, and no
    page said so of any of the 39 bills: HB 1102 of 2026, overridden by both
    chambers on 19 August 2026, and SB 88 of 2011, by the Senate on 7 September
    and the House on 14 September.

    And not only where both are the docket's veto rows. 17 of the 39 have one
    chamber's override on a row the reader types "other", drawn on its sitting
    from the roll call on record, and the first pairing, among the veto rows
    alone, missed every one: HB 455 of 2019, overridden by the House on 23 May
    and the Senate on 30 May 2019, said only "overridden in this chamber" on
    both pages. Paired over the sittings (session_days._became_law), and the
    day said only where the row and its roll call agree on it -- as SB 57 of
    2011's House row now does, dated by its own "[done during 1/4/2012 morning
    veto session]" and not by the 30 November it was entered (decision 59h)."""
    bad = []
    narr = {}
    for (bill, term), rows in _OVERRIDES.items():
        narr.setdefault(term, {})[bill] = [
            {"type": t, "body": b, "date": d, "raw": raw, "cancelled": False}
            for b, d, t, raw in rows]
    rolls = {}
    for (bill, term), rr in _OVERRIDE_ROLLS.items():
        rolls.setdefault(term, {})[bill] = [
            _rc(y, b, n, d, bill, q, yy, nn, True, need=(2 * (yy + nn) + 2) // 3)
            for y, b, n, d, q, yy, nn in rr]
    days = _sitting_fixture(SD, narr, rolls)
    seen = set()
    for (body, date), d in days.items():
        for it in d.items:
            if not it.veto:
                continue
            seen.add((it.bill, body))
            want = _OVERRIDES_SAID.get((it.bill, body))
            if want and not (it.outcome_words or "").endswith(want):
                bad.append(f"{it.bill}'s {body} override of {date} reads {it.outcome_words!r}")
    bad += [f"{b}'s {c} override is on no sitting" for b, c in _OVERRIDES_SAID if (b, c) not in seen]
    # And the row that records the law is no second motion: HB 143 of 2018's
    # House page drew "Veto Overridden 09/13/2018: Eff. 09/13/2018; Chapter
    # 378" as a second override beside the vote (Docket_2017-2018.txt 3206, 3208).
    hb143 = [{"type": "veto_override", "body": "H", "date": "2018-09-13",
              "raw": "Veto Overridden 09/13/2018: RC 255-89 by Required Two-Thirds Vote"},
             {"type": "veto_override", "body": "H", "date": "2018-09-13",
              "raw": "Veto Overridden 09/13/2018: Eff. 09/13/2018; Chapter 378"}]
    got = [it for _e, it in SD.floor_items("HB143", "2017-2018", hb143) if it.veto]
    if len(got) != 1 or (got[0].yeas, got[0].nays) != (255, 89):
        bad.append(f"HB 143 of 2018's House override is drawn as {len(got)} motion(s): "
                   f"{[i.raw for i in got]}")
    assert not bad, "\n".join(bad)
    return "ok", ("HB 1102 of 2026, SB 88 of 2011 and HB 455 of 2019, whose Senate override is on "
                  "a row the reader types \"other\", became law on both chambers' pages, the day "
                  "of the other's override said where it is another, SB 57 of 2011's on the 4 "
                  "January 2012 its own row and roll call give; SB 434's one override did not")


# Real rows: Docket_db_2011-2012.txt 5920-5924 (HB 542) and 6972 (SB 57), as
# narrative.py dates them -- the House's reconsideration and override "[done
# during 1/4/2012 morning veto session]" on that day -- and the Senate's
# override of HB 542 of 7 September 2011 (roll call 100).
_SUSTAINED_THEN = [
    ("H", "2011-11-30", "veto_override", "Shall HB542 Become Law: Veto Sustained, RC 244-130, Lacking "
                                         "Required Two-Thirds Vote"),
    ("H", "2012-01-04", "floor", "Reconsideration (Rep Kurk): MA DIV 256-115, [done during 1/4/2012 "
                                 "morning veto session]"),
    ("H", "2012-01-04", "veto_override", "Veto Overridden: RC 255-112 By Required Two-Thirds Vote, [done "
                                         "during 1/4/2012 morning veto session]"),
    ("S", "2011-09-07", "veto_override", "Notwithstanding the Governor's Veto, Shall HB 542 Become Law: "
                                         "RC 17Y-5N, Veto Overridden by required two-thirds vote"),
]


@check("session", "a veto a chamber sustained and overrode at a later sitting is not said to have "
                  "killed the bill, and a row is drawn on the day it says it was done",
       needs=("session_days", "docket_vocab"))
def _session_sustained_then_overridden(SD, V):
    """Decision 59h. The House sustained HB 542 of 2011's veto 244-130 on 30
    November 2011, reconsidered, and overrode it 255-112 on 4 January 2012;
    the Senate had overridden it on 7 September, and the bill became law
    (Chapter 271). The House's page of 30 November said "the veto was
    sustained, so the bill did not become law". It now says the chamber
    overrode it on 4 January 2012 and the bill became law; and SB 434 of
    2026's sustained veto, which nothing later overrode, still killed it.

    And the same page drew SB 57's override of 4 January 2012: "Veto
    Overriden: RC 248-123 By Required Two-Thirds Vote, [done during 1/4/2012
    morning veto session]", entered on 30 November, which the reader types no
    vote for its spelling and so dated by its stamp. docket_vocab dates such a
    row by its own "done during", as it does a floor row."""
    import datetime as _dt
    bad = []
    narr = {"2011-2012": {"HB542": [{"type": t, "body": b, "date": d, "raw": raw, "cancelled": False,
                                     **({"action": "Reconsideration", "motion": "MA", "vote_kind": "DV",
                                         "yeas": "256", "nays": "115"} if t == "floor" else {})}
                                    for b, d, t, raw in _SUSTAINED_THEN]},
            "2025-2026": {"SB434": [{"type": t, "body": b, "date": d, "raw": raw, "cancelled": False}
                                    for b, d, t, raw in _OVERRIDES[("SB434", "2025-2026")]]}}
    days = _sitting_fixture(SD, narr, {})
    said = {(it.bill, key): it.outcome_words for key, d in days.items() for it in d.items if it.veto}
    want = {("HB542", ("H", "2011-11-30")):
            "the veto was sustained that day; the chamber overrode it on January 4, 2012, "
            "and the bill became law.",
            ("HB542", ("H", "2012-01-04")):
            "the veto was overridden in this chamber and, on September 7, 2011, in the Senate, "
            "so the bill became law.",
            ("SB434", ("H", "2026-08-19")): "the veto was sustained, so the bill did not become law."}
    for k, w in want.items():
        if not (said.get(k) or "").endswith(w):
            bad.append(f"{k[0]}'s {k[1][0]} veto vote of {k[1][1]} reads {said.get(k)!r}")
    ev = V.classify("Veto Overriden: RC 248-123 By Required Two-Thirds Vote, [done during 1/4/2012 "
                    "morning veto session]; HJ 76, PG.2302-2305",
                    _dt.datetime(2011, 11, 30, 10, 48, 20), "2011")
    if (ev or {}).get("date") != "01/04/2012":
        bad.append(f"SB 57 of 2011's House override is dated {(ev or {}).get('date')!r}, not 4 January 2012")
    other = V.classify("Copy to Chairman [12/01/2011]", _dt.datetime(2011, 11, 30, 10, 0), "2011")
    if (other or {}).get("date"):
        bad.append(f"a bare date in brackets dates a row the reader types nothing: {other!r}")
    assert not bad, "\n".join(bad)
    return "ok", ("HB 542 of 2011's sustained veto is drawn as overridden on 4 January 2012 and the "
                  "bill law; SB 434's still killed it; SB 57's House override is dated 4 January 2012")


@check("session", "a division is held to the House journal, and counted once however many bills it is drawn under",
       needs=("session_days",))
def _session_division_held(SD):
    """The docket copies a division onto the wrong row as it copies a roll
    call, and the page drew every count it stated: HB 1516's "MA DV 176-160"
    of 12 March 2026 is HB 1355's division, HB 1114's "Remove from Table
    (Rep. Wade): MF DV 123-207" of 11 March 2026 is HB 1814's motion -- a bill
    the day's journal never names -- and HB 578's report of 6 March 2025 is
    entered 338-28 where the journal prints 338-25. And the opening of
    30 April 2014 said 38 divisions where the House took four: the
    resolution that read 35 Senate bills a third time, "Third Reading MA
    Div, 184-155", was entered on each and counted on each, its count
    unread. Two divisions of one count are two where the journal prints two:
    HB 1194's and HB 1660's reconsiderations of 7 March 2024, each 171-192."""
    def floor(date, raw, action, kind, y=None, n=None, motion="MA"):
        return {"type": "floor", "date": date, "body": "H", "raw": raw, "action": action,
                "motion": motion, "vote_kind": kind, "yeas": y, "nays": n}
    term = "2025-2026"
    narr = {term: {
        "HB1355": [floor("2026-03-12", "Ought to Pass with Amendment 2026-0695h: MA DV 176-160 03/12/2026",
                         "Ought to Pass with Amendment 2026-0695h", "DV", "176", "160")],
        "HB1516": [floor("2026-03-12", "Ought to Pass with Amendment 2026-0610h: MA DV 176-160 03/12/2026",
                         "Ought to Pass with Amendment 2026-0610h", "DV", "176", "160")],
        "HB1814": [floor("2026-03-11", "Remove from Table (Rep. Wade): MF DV 123-207 03/11/2026",
                         "Remove from Table", "DV", "123", "207", "MF")],
        "HB1114": [floor("2026-03-11", "Remove from Table (Rep. Wade): MF DV 123-207 03/11/2026",
                         "Remove from Table", "DV", "123", "207", "MF")],
        "HB578": [floor("2025-03-06", "Inexpedient to Legislate: MA DV 338-28 03/06/2025",
                        "Inexpedient to Legislate", "DV", "338", "28")]},
        "2013-2014": {b: [floor("2014-04-30", "Third Reading MA Div, 184-155", "Third Reading", "DV")]
                      for b in ("SB141", "SB204")},
        "2023-2024": {b: [floor("2024-03-07", f"Reconsider {b} (Rep. Sweeney): MF DV 171-192 03/07/2024",
                                f"Reconsider {b}", "DV", "171", "192", "MF")]
                      for b in ("HB1194", "HB1660")},
        # and with no journal on disk, rows citing different pages are two
        # votes: the Senate's third readings of 20 February 1997
        "1997-1998": {b: [dict(floor("1997-02-20", "3RD READING ML RC(10-14); SEN PATENAUDE MOVED ITL, "
                                     "ITL REPORT", "Third Reading", "RC", "10", "14", "ML"), body="S"),
                          dict(floor("1997-02-20", f"ADOPTED VV; SJ6,{p}", "Inexpedient to Legislate",
                                     "VV"), body="S")]
                      for b, p in (("SB45", "P83"), ("SB57", "P82-83"))}}
    journals = {
        ("H", "2026-03-12"): {"div": [(176, 160)], "bills": ["HB1355", "HB1516"],
                              "under": {"HB1355": [(176, 160)]}},
        ("H", "2026-03-11"): {"div": [(123, 207)], "bills": ["HB1814", "CACR21"],
                              "under": {"CACR21": [(123, 207)]}},
        ("H", "2025-03-06"): {"div": [(338, 25)], "bills": ["HB578"],
                              "under": {"HB578": [(338, 25)]}},
        ("H", "2014-04-30"): {"div": [(184, 155)], "bills": ["SB141", "SB204"], "under": {}},
        ("H", "2024-03-07"): {"div": [(171, 192), (171, 192)], "bills": ["HB1194", "HB1660"],
                              "under": {"HB1194": [(171, 192)], "HB1660": [(171, 192)]}}}
    days = _sitting_fixture(SD, narr, {}, journals=journals)
    mar12 = days[("H", "2026-03-12")]
    assert [(i.bill, i.yeas) for i in mar12.items] == [("HB1355", 176), ("HB1516", None)] and \
        mar12.counts() == {"division": 1}, (
        f"HB 1355's division is drawn again under HB 1516: {[(i.bill, i.yeas) for i in mar12.items]}")
    mar11 = days[("H", "2026-03-11")]
    assert [i.bill for i in mar11.items] == ["HB1814"], (
        f"HB 1814's motion is drawn under HB 1114, which the journal never names: "
        f"{[i.bill for i in mar11.items]}")
    assert [(i.yeas, i.nays, i.kind) for i in days[("H", "2025-03-06")].items] == \
        [(338, 25, "DV")], (
        "HB 578's division is not drawn with the count the journal prints under its "
        f"heading: {[(i.yeas, i.nays, i.kind) for i in days[('H', '2025-03-06')].items]}")
    apr30 = days[("H", "2014-04-30")]
    assert apr30.counts() == {"division": 1} and \
        {(i.yeas, i.nays, i.shared) for i in apr30.items} == {(184, 155, 2)}, (
        f"one division on two bills is counted {apr30.counts()}: "
        f"{[(i.yeas, i.nays, i.shared) for i in apr30.items]}")
    mar7 = days[("H", "2024-03-07")]
    assert mar7.counts() == {"division": 2} and {i.shared for i in mar7.items} == {0}, (
        f"two divisions the journal prints twice are counted as one: {mar7.counts()}")
    feb20 = days[("S", "1997-02-20")]
    assert feb20.counts().get("roll call") == 2, (
        f"two third readings of one count, with no journal to say otherwise, are one: "
        f"{feb20.counts()}")

    # The third review's cases, each cut from the record it was found in.
    narr = {
        "2025-2026": {
            # HB 446's report, entered with HB 557's count; the journal prints
            # 204-166 after HB 446's heading (HJ 11 March 27, 2025.txt:733)
            "HB446": [floor("2025-03-27", "Ought to Pass with Amendment 2025-0042h: MA DV 202-166 "
                            "03/27/2025", "Ought to Pass with Amendment 2025-0042h", "DV", "202",
                            "166")],
            "HB557": [floor("2025-03-27", "Ought to Pass: MA DV 202-166 03/27/2025",
                            "Ought to Pass", "DV", "202", "166")],
            # HB 1134's tabling "adopted" 154-167, which the journal says
            # failed (HJ 06 March 5, 2026.txt:9413)
            "HB1134": [floor("2026-03-05", "Lay HB1134 on Table (Rep. Wood): MA DV 154-167 "
                             "03/05/2026", "Lay HB1134 on Table", "DV", "154", "167")]},
        "2023-2024": {
            # CACR 4's tabling 153-29, where the journal prints 153-229
            "CACR4": [floor("2023-03-23", "Lay CACR4 on Table: MF DV 153-29 03/23/2023",
                            "Lay CACR4 on Table", "DV", "153", "29", "MF")]},
        "2005-2006": {
            # HB 1398's 174-91, on a day whose journal on disk names it only
            # among the consent calendar's removals
            "HB1398": [floor("2006-02-15", "Inexpedient to Legislate, MA, DIV 174-91",
                             "Inexpedient to Legislate", "DV", "174", "91")]},
        "2013-2014": {
            # the consent calendar of 25 March 2014: 282-9, and 289-9 on two
            # bills, a count the journal does not print
            b: [floor("2014-03-25", f"Ought to Pass: MA Div {c} (Consent Calendar)",
                      "Ought to Pass", "DV", c.split("-")[0], c.split("-")[1])]
            for b, c in (("HB1001", "282-9"), ("HB1002", "282-9"), ("HB1286", "289-9"),
                         ("HB1348", "289-9"))}}
    journals = {
        ("H", "2025-03-27"): {"div": [(204, 166), (202, 166)], "bills": ["HB446", "HB557"],
                              "under": {"HB446": [(204, 166)], "HB557": [(202, 166)]}},
        ("H", "2026-03-05"): {"div": [(154, 167)], "bills": ["HB1134"],
                              "under": {"HB1134": [(154, 167)]}},
        ("H", "2023-03-23"): {"div": [(153, 229)], "bills": ["CACR4"],
                              "under": {"CACR4": [(153, 229)]}, "decided": ["CACR4"]},
        ("H", "2006-02-15"): {"div": [], "bills": ["HB1398"], "under": {}, "decided": []},
        ("H", "2014-03-25"): {"div": [(282, 9)], "bills": ["HB1001", "HB1002", "HB1286",
                                                            "HB1348"], "under": {}}}
    days = _sitting_fixture(SD, narr, {}, journals=journals)
    got = {i.bill: (i.yeas, i.nays, i.kind) for i in days[("H", "2025-03-27")].items}
    assert got == {"HB446": (204, 166, "DV"), "HB557": (202, 166, "DV")}, (
        f"HB 446's division is not drawn with the count the journal prints for it: {got}")
    t, = days[("H", "2026-03-05")].items
    assert (t.yeas, t.kind, t.carried, t.outcome_words) == (None, "", None, ""), (
        "HB 1134's tabling is drawn adopted on a count of fewer yeas than nays: "
        f"{(t.yeas, t.nays, t.carried, t.outcome_words)}")
    c, = days[("H", "2023-03-23")].items
    assert (c.yeas, c.kind, c.carried) == (None, "", False), (
        f"CACR 4's 153-29, which the journal prints nowhere, is drawn: {(c.yeas, c.nays)}")
    h, = days[("H", "2006-02-15")].items
    assert (h.yeas, h.nays, h.kind) == (174, 91, "DV"), (
        "HB 1398's division is taken off on a day whose journal names it only in a list: "
        f"{(h.yeas, h.nays, h.kind)}")
    # A two-thirds the clerk writes after the word: HB 296's "MF DIV 161-91,
    # Lacking Necessary 2/3" (5 April 2007) failed with more yeas, and is
    # drawn so, with its threshold, not as a count its outcome contradicts.
    h296 = SD.Item("HB296", "2007-2008", {"type": "floor", "body": "H", "action": "Ought to Pass",
                                          "motion": "MF", "vote_kind": "DV", "yeas": "161",
                                          "nays": "91", "raw": "Ought to Pass: MF DIV 161-91, "
                                          "Lacking Necessary 2/3; HJ 35, pg.1252"}, 0)
    assert h296.need == 168 and not SD._against_its_count(h296), (
        f"HB 296's two thirds is not read: need {h296.need}")
    # The removals a consent calendar prints with a period in the title, and
    # not a committee's report that says "removed by" (16 March 2023).
    import journal_days as JD
    seg = ("HB 1446, providing that an individual's use of therapeutic cannabis shall not "
           "disqualify the individual from the purchase, ownership, or possession of a firearm. "
           "Removed by Reps. H. Howard, Wheeler, Butler. HB 123, enabling municipalities to tax "
           "standing wood and timber on land used for carbon sequestration., removed by Reps. "
           "Kuttab, Popovici-Muller. HB 286, relative to the removal of political advertising. "
           "OUGHT TO PASS. Rep. Katherine Prudhomme-O'Brien for Election Law. This is a bipartisan "
           "bill that allows members of a campaign or local political committee to retrieve "
           "campaign items removed by the state, city, or town.")
    assert [g.group("bill") for g in JD.REMOVED.finditer(seg)] == ["HB 1446", "HB 123"], (
        f"the consent calendar's removals are read as {[g.group('bill') for g in JD.REMOVED.finditer(seg)]}")
    cal = days[("H", "2014-03-25")]
    assert cal.counts() == {"division": 1} and \
        {i.bill: i.yeas for i in cal.items} == {"HB1001": 282, "HB1002": 282,
                                                 "HB1286": None, "HB1348": None}, (
        f"the consent calendar of 25 March 2014 is adopted twice: {cal.counts()}, "
        f"{[(i.bill, i.yeas, i.consent) for i in cal.items]}")
    return "ok", ("a copied division comes off, or goes with a bill the journal never names; "
                  "a count the journal prints within three under the bill's heading is drawn "
                  "as the journal prints it, and one it prints nowhere comes off; a count "
                  "and an outcome that contradict are neither drawn; a consent calendar's "
                  "count is the journal's; one division on 35 bills counts once, and two of "
                  "one count stay two")


@check("session", "a roll call on an amendment, a conference report, a member's "
       "motion or a veto row the reader types otherwise is drawn on its sitting",
       needs=("session_days", "build_session_pages"))
def _session_rollcalls_other_rows(SD, BSP):
    """The House's page for 26 June 2025 drew 5 of its 14 roll calls and the
    Senate's said "1 roll call" of eleven: a vote on an amendment, on a
    committee of conference report, on a previous question worded without
    "MA" before its count, and a veto "Overriden" are docket rows typed
    amendment or other, and only floor rows were read. Rows and roll calls
    as the record holds them: HB 2 and HB 115 of 2025 (Docket.txt lines
    10574-10658, 10620-10649), HB 1's Senate report (line 10647), and SB 406's
    override of 27 June 2012 (Docket_db_2011-2012.txt line 22530)."""
    narr = {"2025-2026": {
        "HB2": [
            {"type": "floor", "date": "2025-06-26", "body": "H", "raw": "Lay HB2 on Table (Rep. Osborne): MA VV 06/26/2025", "action": "Lay HB2 on Table", "motion": "MA", "vote_kind": "VV", "mover": "Rep. Jason Osborne", "cite": "HJ 18", "cite_page": "32"},
            {"type": "floor", "date": "2025-06-26", "body": "H", "raw": "Remove from Table (Rep. Osborne): MA RC 185-180 06/26/2025", "action": "Remove from Table", "motion": "MA", "vote_kind": "RC", "yeas": "185", "nays": "180", "mover": "Rep. Jason Osborne", "cite": "HJ 18", "cite_page": "38"},
            {"type": "other", "date": "2025-06-26", "body": "H", "raw": "Rep. Sweeney moves Previous Question MA RC 193-173 06/26/2025", "cite": "HJ 18", "cite_page": "40"},
            {"type": "other", "date": "2025-06-26", "body": "H", "raw": "Conference Committee Report 2025-2871c: Adopted, RC 184-183 06/26/2025", "cite": "HJ 18", "cite_page": "42"}],
        "HB115": [
            {"type": "floor", "date": "2025-06-26", "body": "S", "raw": "Ought to Pass with Amendment #2025-2880s, MA, VV; OT3rdg; Read a Third Time and Final Passage in the Early Session; 06/26/2025", "action": "Ought to Pass with Amendment #2025-2880s", "motion": "MA", "vote_kind": "VV", "cite": "SJ 17"},
            {"type": "amendment", "date": "2025-06-26", "body": "S", "raw": "Sen. Gray Floor Amendment # 2025-2880s, AA, VV; 06/26/2025", "motion": "AA", "vote_kind": "VV", "mover": "Sen. Gray", "cite": "SJ 17", "amendment": "2025-2880s", "amend_kind": "Floor Amendment"},
            {"type": "amendment", "date": "2025-06-26", "body": "S", "raw": "Sen. Rosenwald Floor Amendment # 2025-2893s, RC 8Y-16N, AF; 06/26/2025", "motion": "AF", "vote_kind": "RC", "mover": "Sen. Rosenwald", "cite": "SJ 17", "amendment": "2025-2893s", "amend_kind": "Floor Amendment"}],
        "HB1": [
            {"type": "other", "date": "2025-06-26", "body": "S", "raw": "Conference Committee Report # 2025-2865c; RC 16Y-8N, Adopted; 06/26/2025", "cite": "SJ 17"}]},
        "2011-2012": {"SB406": [
            {"type": "other", "date": "2012-06-27", "body": "H", "raw": "Shall SB 406 Become Law: Veto Overriden, RC 247-111 By Necessary Two-Thirds Vote; HJ 53, PG.2631-2634", "cite": "HJ 53"}]}}
    rolls = {"2025-2026": {
        "HB2": [_rc("2025", "H", 249, "2025-06-26", "HB2", "Remover From Table", 185, 180, True),
                _rc("2025", "H", 250, "2025-06-26", "HB2", "Limit Debate", 193, 173, True),
                _rc("2025", "H", 251, "2025-06-26", "HB2", "Adopt Conference Committee Report", 184, 183, True)],
        "HB115": [_rc("2025", "S", 116, "2025-06-26", "HB115", "Adopt Floor Amendment", 8, 16, False)],
        "HB1": [_rc("2025", "S", 114, "2025-06-26", "HB1", "Adopt Conference Committee Report", 16, 8, True)]},
        "2011-2012": {"SB406": [_rc("2012", "H", 305, "2012-06-27", "SB406", "SHALL SB 406 BECOME LAW", 247, 111, True, 240)]}}
    days = _sitting_fixture(SD, narr, rolls)
    house, senate = days[("H", "2025-06-26")], days[("S", "2025-06-26")]
    assert _motions(house, "HB2") == [
        ("Lay HB2 on Table", "Rep. Jason Osborne", "VV", None, None, True),
        ("Remove from Table", "Rep. Jason Osborne", "RC", 185, 180, True),
        ("Previous Question", "Rep. Sweeney", "RC", 193, 173, True),
        ("Adopt the Conference Committee Report 2025-2871c", "", "RC", 184, 183, True)], (
        f"HB 2's sitting of 26 June 2025 draws {_motions(house, 'HB2')}")
    assert house.counts() == {"roll call": 3, "voice vote": 1}, house.counts()
    rep = [i for i in house.items if i.action.startswith("Adopt the Conference")][0]
    assert rep.outcome_words == "The motion was adopted on a roll call.", rep.outcome_words
    assert _motions(senate, "HB115")[-1] == (
        "Adopt Floor Amendment 2025-2893s", "Sen. Rosenwald", "RC", 8, 16, False), (
        _motions(senate, "HB115"))
    assert _motions(senate, "HB1") == [
        ("Adopt the Conference Committee Report 2025-2865c", "", "RC", 16, 8, True)], (
        _motions(senate, "HB1"))
    assert senate.counts() == {"roll call": 2, "voice vote": 1}, (
        f"the Senate's opening for 26 June 2025 counts {senate.counts()}: the Gray "
        "amendment's voice vote is not a floor motion and was never counted")
    veto = days[("H", "2012-06-27")].items[0]
    assert (veto.action, veto.veto, veto.carried, veto.need) == (
        "Override the Governor's veto", True, True, 240), (veto.action, veto.carried)
    assert "the veto was overridden" in veto.outcome_words, veto.outcome_words
    assert not days.left and len(SD.drawn(days)) == 6, (days.left, SD.drawn(days))
    return "ok", ("HB 2's previous question and conference report, HB 115's floor "
                  "amendment, HB 1's Senate report and SB 406's override are drawn, "
                  "and counted, on their sittings")


@check("session", "a line of several questions draws each roll call it states, "
       "under its own question, and a roll call is never told as a voice vote",
       needs=("session_days", "build_session_pages"))
def _session_rollcalls_one_line(SD, BSP):
    """The 1999-2006 clerk wrote a bill's floor passage on one line, which is
    one motion here; the line's other roll calls had nowhere to go, or were
    drawn under the wrong question or as a voice vote. Each from the record:
    HB 296's special order of 10 February 1999, lost 65-269 before the voice
    vote to kill it; HB 229's passage, failed 8-14 in the Senate on 31 May
    2001 after the tabling by voice; SB 52's committee amendment adopted by
    voice and its third reading failed 12-12 (6 May 1999), which the page
    called "Ought to Pass with Amendment" failing; HCR 10's 21-3 drawn as "A
    voice vote"; and two counts the line states in a shape the reader did
    not take: CACR 34's "RC (207-125)" (2006) and SB 203's "RC 12Y-12F"
    (2023)."""
    narr = {
        "1999-2000": {
            "HB296": [{"type": "floor", "date": "1999-02-10", "body": "H", "raw": "Rep Rubin moved Spec Order to Feb16, ml RC(65-269); ITL report adopted vv; HJ18, p294-297", "action": "Inexpedient to Legislate", "motion": "MA", "vote_kind": "VV", "cite": "HJ 18"}],
            "SB52": [{"type": "floor", "date": "1999-05-06", "body": "S", "raw": "Ought to Pass W/Amendment, {1066}, AA, VV, OT3rdg, RC 12Y-12N, MF", "action": "Ought to Pass W/Amendment", "motion": "MF", "vote_kind": "RC", "yeas": "12", "nays": "12"},
                     {"type": "floor", "date": "1999-05-06", "body": "S", "raw": "Sen. Trombly Moved Laid on Table, MA, VV", "action": "Lay on Table", "motion": "MA", "vote_kind": "VV", "cite": "SJ 17"}]},
        "2001-2002": {
            "HB229": [{"type": "floor", "date": "2001-05-31", "body": "S", "raw": "Sen. Francoeur Moved Laid on Table, MF, VV; Ought to Pass, RC 8Y-14N, MF", "action": "Lay on Table", "motion": "MF", "vote_kind": "VV", "cite": "SJ 15"},
                      {"type": "floor", "date": "2001-05-31", "body": "S", "raw": "Inexpedient to Legislate, MA, VV", "action": "Inexpedient to Legislate", "motion": "MA", "vote_kind": "VV", "cite": "SJ 15"}],
            "HCR10": [{"type": "floor", "date": "2001-05-17", "body": "S", "raw": "Ought to Pass, RC 21Y-3N, MA; OT3rdg, MA, VV", "action": "Ought to Pass", "motion": "MA", "vote_kind": "VV", "yeas": "21", "nays": "3", "cite": "SJ 13"}]},
        "2005-2006": {
            "CACR34": [{"type": "floor", "date": "2006-03-21", "body": "H", "raw": "Maj Rprt: ITL, MA, RC (207-125)", "action": "Maj Rprt: ITL", "motion": "MA", "vote_kind": "RC", "cite": "HJ 27"}]},
        "2023-2024": {
            "SB203": [{"type": "floor", "date": "2023-03-16", "body": "S", "raw": "Sen. Pearl Moved Laid on Table, RC 12Y-12F, MF; 03/16/2023", "action": "Laid on Table, RC 12Y-12F", "motion": "MF", "mover": "Sen. Howard Pearl", "cite": "SJ 10"}]}}
    rolls = {
        "1999-2000": {"HB296": [_rc("1999", "H", 10, "1999-02-10", "HB296", "REP RUBIN:  SPECIAL ORDER TO FEB 16", 65, 269, False)],
                      "SB52": [_rc("1999", "S", 43, "1999-05-06", "SB52", "Order to 3rd ReadingFrancoeur/Roberge", 12, 12, False)]},
        "2001-2002": {"HB229": [_rc("2001", "S", 67, "2001-05-31", "HB229", "Ought to pass Sen. McCarley/Sen. Wheeler", 8, 14, False)],
                      "HCR10": [_rc("2001", "S", 56, "2001-05-17", "HCR10", "Ought to pass Sen. Francoeur/Sen. Gatsas", 21, 3, True)]},
        "2005-2006": {"CACR34": [_rc("2006", "H", 142, "2006-03-21", "CACR34", "MAJORITY COMMITTEE REPORT:  ITL", 207, 125, True)]},
        "2023-2024": {"SB203": [_rc("2023", "S", 26, "2023-03-16", "SB203", "Lay on Table", 12, 12, False)]}}
    days = _sitting_fixture(SD, narr, rolls)
    got = _motions(days[("H", "1999-02-10")], "HB296")
    assert got == [("Special Order to Feb16", "Rep. Rubin", "RC", 65, 269, False),
                   ("Inexpedient to Legislate", "", "VV", None, None, True)], got
    got = _motions(days[("S", "2001-05-31")], "HB229")
    assert got[:2] == [("Lay on Table", "", "VV", None, None, False),
                       ("Ought to Pass", "", "RC", 8, 14, False)], got
    got = _motions(days[("S", "1999-05-06")], "SB52")
    assert got[:2] == [("Adopt Committee Amendment 1066", "", "VV", None, None, True),
                       ("Order to Third Reading", "", "RC", 12, 12, False)], got
    hcr = days[("S", "2001-05-17")].items[0]
    assert (hcr.kind, hcr.yeas, hcr.nays) == ("RC", 21, 3) and \
        BSP.vote_payload(hcr)["kind"] == "RC", (hcr.kind, hcr.yeas)
    cacr = days[("H", "2006-03-21")].items[0]
    assert (cacr.kind, cacr.yeas, cacr.nays, cacr.carried) == ("RC", 207, 125, True), (
        cacr.kind, cacr.yeas, cacr.nays)
    sb = days[("S", "2023-03-16")].items[0]
    assert (sb.kind, sb.yeas, sb.nays, sb.carried) == ("RC", 12, 12, False), (sb.kind, sb.yeas)
    assert not days.left and len(SD.drawn(days)) == 6, days.left
    return "ok", ("HB 296's special order, HB 229's failed passage, SB 52's third "
                  "reading, HCR 10's roll call and the counts of CACR 34 and SB 203 "
                  "are drawn as the record holds them")


@check("session", "a roll call is drawn with the ballots' count and the record's "
       "outcome, once, on its sitting, wherever the docket says less",
       needs=("session_days", "build_session_pages"))
def _session_rollcalls_reconciled(SD, BSP):
    """The docket says voice vote of HB 1149's kill, 283-43 on a roll call
    (10 March 2022); enters HB 435's report as adopted on 129-156 (8 January
    2014: the Journal says it failed, and rollcall_outcomes follows the
    count); and gives SB 442's passage as 218-94 where the ballots and the
    Journal say 201-103 (4 May 2022). The House's roll calls of 24 February
    2021 are dated the 26th in the roll-call file and drawn on the 24th, as
    the docket and the Journal have them. One motion to reconsider the third
    reading of 35 Senate bills, 133-202 on 30 April 2014, is one roll call
    however many bills it is drawn under; the Senate's consent calendar of 22
    April 2021, 23-1, is one roll call however many bills it carried. A rules
    vote on no bill is drawn among the day's votes on no bill; a quorum call
    is not a vote; and a day only the roll-call file knows is a sitting only
    where the journal opens one."""
    narr = {
        "2021-2022": {
            "HB1149": [{"type": "floor", "date": "2022-03-10", "body": "H", "raw": "Inexpedient to Legislate: MA VV 03/10/2022", "action": "Inexpedient to Legislate", "motion": "MA", "vote_kind": "VV", "cite": "HJ 5"}],
            "SB442": [{"type": "floor", "date": "2022-05-04", "body": "H", "raw": "Ought to Pass : MA RC 218-94 05/04/2022", "action": "Ought to Pass", "motion": "MA", "vote_kind": "RC", "yeas": "218", "nays": "94", "cite": "HJ 11"}],
            "HB63": [{"type": "floor", "date": "2021-02-24", "body": "H", "raw": "Lay on Table (Rep. Conley): MF RC 156-196 02/24/2021", "action": "Lay on Table", "motion": "MF", "vote_kind": "RC", "yeas": "156", "nays": "196", "mover": "Rep. Conley", "cite": "HJ 3", "cite_page": "23"}],
            "HB100": [{"type": "report", "date": "2021-04-22", "body": "S", "raw": "Committee Report: Ought to Pass with Amendment #2021-1130s , 04/22/2021; Vote 5-0; CC", "cite": "SC 20"},
                      {"type": "floor", "date": "2021-04-22", "body": "S", "raw": "Ought to Pass with Amendment 2021-1130s, RC 23Y-1N, MA; OT3rdg; 04/22/2021", "cite": "SJ 12", "action": "Ought to Pass with Amendment 2021-1130s, RC 23Y-1N", "motion": "MA"}],
            "HB101": [{"type": "report", "date": "2021-04-22", "body": "S", "raw": "Committee Report: Ought to Pass with Amendment #2021-1146s , 04/22/2021; Vote 5-0; CC", "cite": "SC 20"},
                      {"type": "floor", "date": "2021-04-22", "body": "S", "raw": "Ought to Pass with Amendment 2021-1146s, RC 23Y-1N, MA; OT3rdg; 04/22/2021", "cite": "SJ 12", "action": "Ought to Pass with Amendment 2021-1146s, RC 23Y-1N", "motion": "MA"}]},
        "2013-2014": {
            "HB435": [{"type": "floor", "date": "2014-01-08", "body": "H", "raw": "Inexpedient to Legislate MA RC 129-156", "action": "Inexpedient to Legislate", "motion": "MA", "vote_kind": "RC", "yeas": "129", "nays": "156"}],
            "SB91": [{"type": "floor", "date": "2014-04-30", "body": "H", "raw": "Reconsideration Third Reading (Rep. Lambert) MF RC 133-202", "action": "Reconsideration Third Reading", "mover": "Rep. Lambert", "motion": "MF", "vote_kind": "RC", "yeas": "133", "nays": "202"}],
            "SB141": [{"type": "floor", "date": "2014-04-30", "body": "H", "raw": "Reconsideration Third Reading (Rep. Lambert) MF RC 133-202", "action": "Reconsideration Third Reading", "mover": "Rep. Lambert", "motion": "MF", "vote_kind": "RC", "yeas": "133", "nays": "202"}]},
        "2025-2026": {
            "SB15": [{"type": "floor", "date": "2026-01-07", "body": "H", "raw": "Ought to Pass with Amendment 2025-3096h: MA RC 179-159 01/07/2026", "action": "Ought to Pass with Amendment 2025-3096h", "motion": "MA", "vote_kind": "RC", "yeas": "179", "nays": "159", "cite": "HJ 1"}]}}
    rolls = {
        "2021-2022": {
            "HB1149": [_rc("2022", "H", 68, "2022-03-10", "HB1149", "Inexpedient to Legislate", 283, 43, True)],
            "SB442": [_rc("2022", "H", 231, "2022-05-04", "SB442", "Ought to Pass", 201, 103, True)],
            "HB63": [_rc("2021", "H", 14, "2021-02-26", "HB63", "Lay on Table", 156, 196, False)],
            "_procedural": [_rc("2021", "S", 311, "2021-04-22", None, "Consent Calendar", 23, 1, True)]},
        "2013-2014": {
            "HB435": [_rc("2014", "H", 15, "2014-01-08", "HB435", "Inexpedient to Legislate", 129, 156, False)],
            "_procedural": [_rc("2014", "H", 222, "2014-04-30", None, "Reconsider 3rd Reading", 133, 202, False)]},
        "2025-2026": {
            "SB15": [_rc("2026", "H", 3, "2026-01-07", "SB15", "Ought to Pass with Amendment", 179, 159, True)],
            "_procedural": [_rc("2026", "H", 1, "2026-01-07", None, "Call of the Roll", 321, 2, True),
                            _rc("2026", "H", 2, "2026-01-07", None, "Rules Suspension", 57, 280, False, 225),
                            _rc("2025", "H", 1, "2025-01-08", None, "Amend H Rule 64", 200, 150, True)]}}
    days = _sitting_fixture(SD, narr, rolls)
    kill = days[("H", "2022-03-10")].items[0]
    assert (kill.kind, kill.yeas, kill.nays) == ("RC", 283, 43), (kill.kind, kill.yeas)
    itl = days[("H", "2014-01-08")].items[0]
    assert itl.carried is False and "failed on a roll call" in itl.outcome_words, itl.outcome_words
    otp = days[("H", "2022-05-04")].items[0]
    assert (otp.yeas, otp.nays, otp.said) == (201, 103, (218, 94)), (otp.yeas, otp.said)
    assert SD.drawn(days)[("2021", "H", 14)] == ("H", "2021-02-24"), SD.drawn(days)
    shared = days[("H", "2014-04-30")]
    assert shared.counts() == {"roll call": 1} and \
        {i.shared for i in shared.items} == {2}, (shared.counts(), [i.shared for i in shared.items])
    cal = days[("S", "2021-04-22")]
    seq, cons = cal.split()
    assert len(cons) == 2 and cal.counts() == {"roll call": 1}, (len(cons), cal.counts())
    assert BSP.calendar_vote(cons) == [("roll call", 23, 1, True)], BSP.calendar_vote(cons)
    jan = days[("H", "2026-01-07")]
    assert [(i.action, i.yeas, i.nays, i.carried, i.need) for i in jan.others] == [
        ("Rules Suspension", 57, 280, False, 225)], jan.others
    assert jan.counts() == {"roll call": 2}, jan.counts()
    why = {SD.rollcall_key(r): w for r, w in days.left}
    assert set(why) == {("2026", "H", 1), ("2025", "H", 1)} and \
        why[("2026", "H", 1)].startswith("a quorum call"), why
    assert ("H", "2025-01-08") not in days
    sat = _sitting_fixture(SD, narr, rolls, sat=lambda body, date: date == "2025-01-08")
    rules = sat[("H", "2025-01-08")]
    assert not rules.items and [i.action for i in rules.others] == ["Amend H Rule 64"], (
        rules.items, rules.others)
    html, payloads = BSP.render(rules, {}, {}, {}, BSP.Members(Path("no-such-site")), str)
    lead = BSP._lead(rules, {}, "2025-01-08")
    assert "Votes on No Bill" in html and len(payloads) == 1 and lead.startswith("1 roll call."), (
        lead, html[:300])
    html, _ = BSP.render(shared, {}, {}, {}, BSP.Members(Path("no-such-site")), str)
    assert html.count("One roll call on 2 bills") == 2, html[:600]
    # The clerk's 207-141 on three bills for the suspension the roll-call file
    # holds as 206-141 (21 March 2007); Sen. Bradley's suspension for four
    # House bills, entered on 4 January 2012 and voted on 7 September 2011.
    susp = "Rules Susp: Permit Ref 2nd Comm after Deadline: MF RC 207-141 lacking necessary 2/3; HJ28 pg851-853"
    brad = ("Sen. Bradley Moved to Suspend all Rules necessary to allow the consideration of HB {} "
            "and further allow it to be reported out of policy committee in the 2012 Senate "
            "Session by the adopted Senate deadline for HBs. 2/3 necessary, MA, RC 16Y-6N")
    narr2 = {"2007-2008": {b: [{"type": "floor", "date": "2007-03-21", "body": "H", "raw": susp, "action": "Rules Susp: Permit Ref 2nd Comm after Deadline", "motion": "MF", "vote_kind": "RC", "yeas": "207", "nays": "141", "cite": "HJ 28"}]
                           for b in ("HB283", "HB440")},
             "2011-2012": {b: [{"type": "floor", "date": "2012-01-04", "body": "S", "raw": brad.format(b[2:]), "action": "Suspend all Rules necessary", "motion": "MA", "vote_kind": "RC", "yeas": "16", "nays": "6", "mover": "Sen. Bradley"}]
                           for b in ("HB652", "HB654")}}
    rolls2 = {"2007-2008": {"_procedural": [_rc("2007", "H", 34, "2007-03-21", None, "ADOPT MOTION TO SUSPEND RULES", 206, 141, False, 232)]},
              "2011-2012": {"_procedural": [_rc("2011", "S", 109, "2011-09-07", None, "Suspension of Senate Rules", 16, 6, True, 15)]}}
    late = _sitting_fixture(SD, narr2, rolls2)
    for key in (("H", "2007-03-21"), ("S", "2012-01-04")):
        assert late[key].counts() == {"roll call": 1} and not late.left and \
            all(i.rc is not None for i in late[key].items), (key, late[key].counts(), late.left)
    assert [(i.yeas, i.nays, i.said) for i in late[("H", "2007-03-21")].items] == \
        [(206, 141, (207, 141))] * 2
    return "ok", ("HB 1149, HB 435 and SB 442 are drawn as the ballots and the record "
                  "have them; HB 63's misdated roll call is on 24 February 2021; one "
                  "reconsideration on two bills and one consent calendar are each one "
                  "roll call; the rules vote is among the votes on no bill, the quorum "
                  "call is set aside, and a day only the roll-call file knows is a "
                  "sitting only where the journal opens one")


# A SITTING FIXTURE READS ONLY WHAT IT IS GIVEN (29 October 2026). The check
# above builds its own record (_sitting_fixture), and it failed on every tree
# that had run a build: the page drew the build's journal_motions.json from
# the working folder, so the fixture's House day of 8 January 2025 gained a
# real "Votes on No Bill", and load() read the working folder's House
# Journals for a CACR's division though it was given journals of its own. On
# GitHub's night it passed only because the code checks run before the build.
@check("session", "a sitting fixture draws the same from any working folder, a built tree's "
       "files beside it or none", needs=("session_days", "build_session_pages", "vote_passage",
                                         "rollcall_outcomes"))
def _session_fixture_hermetic(SD, BSP, VP, RO):
    """A cut of the record's sittings, drawn and rendered from an empty
    working folder and again from one holding what a built tree holds, each
    file saying something of the fixture's own days that would change what
    is drawn if it were read: journal_motions.json, with a vote on no bill on
    every sitting and a title, a line and a ruling for every roll call; the
    House and Senate Journals of the fixture's years, printing every count as
    a roll call and as a division adopted by the necessary three-fifths;
    data/bills.json, which holds none of the fixture's bills; and
    rollcalls.json. The two must be the same, day for day and byte for
    byte, and a day made by hand from a fixture's must read nothing either.
    And every decoy must be read by the readers that do take the working
    folder (vote_passage's, rollcall_outcomes.journal_division_words,
    session_days' journals, _held_bills, _read_rollcalls), or it proves
    nothing."""
    import datetime as _dt
    import html as _html

    def floor(date, body, raw, action, kind, y=None, n=None, **more):
        e = {"type": "floor", "date": date, "body": body, "raw": raw, "action": action,
             "motion": "MA", "vote_kind": kind, **more}
        if y is not None:
            e.update(yeas=str(y), nays=str(n))
        return e
    narr = {
        "2025-2026": {"SB15": [floor("2026-01-07", "H", "Ought to Pass with Amendment 2025-3096h: "
                                     "MA RC 179-159 01/07/2026", "Ought to Pass with Amendment "
                                     "2025-3096h", "RC", 179, 159, cite="HJ 1")]},
        # A CACR's division whose docket line names no fraction, where the
        # Journal's sentence would (rollcall_outcomes.journal_division_words).
        "1999-2000": {"CACR2": [floor("2000-04-13", "H", "Taken from the Table, Rep Mock MA "
                                      "DIV(251-87)", "Taken from the Table", "DV", 251, 87)]},
        # An appeal on a bill, under which the page says what the chair ruled.
        "2015-2016": {"SB9": [floor("2015-09-16", "H", "Uphold Ruling of the Chair: MA RC 286-89",
                                    "Uphold Ruling of the Chair", "RC", 286, 89, cite="HJ 57")]},
        "2021-2022": {"HB100": [floor("2021-04-22", "S", "Ought to Pass, RC 23Y-1N, MA; OT3rdg; "
                                      "04/22/2021", "Ought to Pass, RC 23Y-1N", "", cite="SJ 12")]}}
    rolls = {
        "2025-2026": {
            "SB15": [_rc("2026", "H", 3, "2026-01-07", "SB15", "Ought to Pass with Amendment",
                         179, 159, True)],
            # A bill the docket holds no rows for: named, unless the term's
            # list of bills (data/bills.json) holds no such bill.
            "HB476": [_rc("2026", "H", 4, "2026-01-07", "HB476", "Reconsider", 15, 340, False)],
            "_procedural": [_rc("2026", "H", 2, "2026-01-07", None, "Rules Suspension", 57, 280,
                                False, 225),
                            _rc("2025", "H", 1, "2025-01-08", None, "Amend H Rule 64", 200, 150,
                                True)]},
        "1999-2000": {"_procedural": [_rc("2000", "H", 60, "2000-04-13", None, "Call of the Roll",
                                          380, 2, True, seated=398)]},
        "2015-2016": {"SB9": [_rc("2015", "H", 188, "2015-09-16", "SB9",
                                  "Uphold Ruling of the Chair", 286, 89, True)]},
        "2021-2022": {"HB100": [_rc("2021", "S", 311, "2021-04-22", "HB100", "Ought to Pass",
                                    23, 1, True)]}}
    keys = {f'{r["year"]}-{r["body"]}-{r["number"]}': r
            for bills in rolls.values() for rs in bills.values() for r in rs}
    sittings = sorted({(r["body"], r["date"]) for r in keys.values()})
    counts = sorted({(r["yeas"], r["nays"]) for r in keys.values()} | {(251, 87)})

    def drawn():
        days = _sitting_fixture(SD, narr, rolls, sat=lambda body, date: date == "2025-01-08")
        out = {"left": sorted((SD.rollcall_key(r), w) for r, w in days.left)}
        for key in sorted(days):
            d = days[key]
            by_hand = SD.Day(d.body, d.date, d.items, d.others)
            out[key] = (d.printed, [
                (i.bill, i.action, i.kind, i.yeas, i.nays, i.carried, i.need, i.fifths,
                 i.outcome_words, i.rc and SD.rollcall_key(i.rc))
                for i in list(d.items) + list(d.others)]) + tuple(
                BSP.render(x, {}, {}, {}, BSP.Members(Path("no-such-site")), _html.escape)
                for x in (d, by_hand))
        return out

    caches = (VP._CACHE, RO._DIVISIONS, SD._SAT)
    kept = [dict(c) for c in caches]
    here = os.getcwd()
    root = Path(tempfile.mkdtemp(prefix="sitting-decoys-"))
    try:
        empty, built = root / "empty", root / "built"
        empty.mkdir()
        (built / "data").mkdir(parents=True)
        said = [{"k": "outcome", "t": "The decoy carried."}]
        (built / "journal_motions.json").write_text(json.dumps({
            "rollcalls": {k: {"key": k, "body": r["body"], "date": r["date"], "held": [],
                              "kind": "motion", "title": "A Decoy Motion", "line": "a decoy",
                              "ruling": "A decoy ruling", "said": said}
                          for k, r in keys.items()},
            "journal_only": [{"key": f"{d}-{b}-decoy", "body": b, "date": d, "how": "division",
                              "yeas": 7, "nays": 3, "passed": True, "kind": "motion",
                              "title": "A Decoy Division", "said": said, "member": "", "bill": "",
                              "bills": []} for b, d in sittings],
            "kinds": {"motion": "A decoy kind"}, "groups": {}, "group_words": {},
            "bill_votes": []}), encoding="utf-8")
        for b, d in sittings:
            on = _dt.date.fromisoformat(d)
            dateline = f"{on:%B} {on.day}, {on.year}"
            if b == "H":
                f = built / "journals" / str(on.year) / f"HJ 1 {dateline}.txt"
                text = (f"HOUSE JOURNAL NO. 1\n\n{on:%A}, {dateline}\n\nThe House met at 10:00 "
                        "a.m.\n\nHB 9999, relative to a decoy.\n\n" + "\n\n".join(
                            f"YEAS {y} - NAYS {n}\n\nOn a division vote, {y} members having "
                            f"voted in the affirmative and {n} in the negative, the motion was "
                            "adopted by the necessary three-fifths." for y, n in counts))
            else:
                f = built / "journals_senate" / str(on.year) / "SJ 1.txt"
                text = (f"{dateline}\n\nThe Senate met at 10:00 a.m.\n\nSB 9999, relative to a "
                        "decoy.\n\n" + "\n\n".join(
                            f"The following Senators voted Yes: Sen. Decoy.\n\nYeas: {y} - Nays: "
                            f"{n}\n\nA division vote was requested.\n\nYeas: {y} - Nays: {n}"
                            for y, n in counts))
            f.parent.mkdir(parents=True, exist_ok=True)
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(text + "\n\n")
        (built / "data" / "bills.json").write_text(json.dumps(
            {t: {"HB9999": {}} for t in rolls}), encoding="utf-8")
        (built / "rollcalls.json").write_text(json.dumps(
            {t: {"_procedural": [_rc(r["year"], r["body"], 900, r["date"], None, "A Decoy Vote",
                                     7, 3, True) for r in keys.values()]} for t in rolls}),
            encoding="utf-8")

        def from_(where, what):
            # Each from nothing remembered: a reader that keeps what it read
            # by a relative path would otherwise answer from another folder.
            for c in caches:
                c.clear()
            os.chdir(where)
            try:
                return what()
            finally:
                os.chdir(here)
        bare, beside = from_(empty, drawn), from_(built, drawn)
        live = from_(built, lambda: {
            "journal_motions.json": bool(VP.journal_only("H", "2025-01-08"))
            and VP.ruling("2015-H-188") == "A decoy ruling",
            "the House Journals": "three-fifths" in RO.journal_division_words(
                ".", "H", "2000-04-13", 251, 87)
            and (200, 150) in (SD._journal_day("H", "2025-01-08") or {}).get("rc", {}),
            "the Senate Journals": (23, 1) in (SD._journal_day("S", "2021-04-22") or {}).get(
                "rc", {}),
            "data/bills.json": SD._held_bills(".") == {t: {"HB9999"} for t in rolls},
            "rollcalls.json": bool(SD._read_rollcalls())})
    finally:
        os.chdir(here)
        for c, k in zip(caches, kept):
            c.clear()
            c.update(k)
        shutil.rmtree(root, ignore_errors=True)
    dead = [k for k, v in live.items() if not v]
    assert not dead, f"decoys the working folder's readers do not read, which prove nothing: {dead}"
    assert len(bare) == len(sittings) + 1, sorted(bare)
    moved = [k for k in bare if bare[k] != beside.get(k)]
    if moved:
        k = moved[0]
        a, b = (repr(x[k]) for x in (bare, beside))
        at = next((n for n, (p, q) in enumerate(zip(a, b)) if p != q), min(len(a), len(b)))
        raise AssertionError(
            f"the fixture's sittings change with the working folder's files: {moved}; "
            f"{k} from an empty folder ...{a[max(0, at - 60):at + 120]!r}, beside a built "
            f"tree's ...{b[max(0, at - 60):at + 120]!r}")
    return "ok", (f"{len(sittings)} sittings, a vote on no bill, a CACR's division, an appeal's "
                  "ruling and a bill no row names are drawn the same beside a built tree's "
                  "journal_motions.json, Journals, data/bills.json and rollcalls.json as from "
                  "an empty folder, and each of those is live")


# NOR DOES A CHECK THAT CALLS load() ITSELF (29 October 2026). Seven checks
# draw their sittings with session_days.load() on a narratives.json of their
# own, not through _sitting_fixture, and gave it no journals, so
# _journal_day read the working folder's journals/ and journals_senate/ for
# each of their days: the owner's laptop holds every year of them, GitHub's
# machine none. Nothing those checks assert changed with what it read, which
# is why none of them failed; they now give load() journals={}, as the
# fixture does.
@check("session", "a check that draws sittings with load() on a record of its own reads none "
       "of the Journals on disk", needs=("session_days", "rollcall_outcomes"))
def _session_checks_read_no_journals(SD, RO):
    """Every code check that calls session_days.load() itself is run again
    with the two caches the disk's Journals are read through --
    session_days._SAT, a chamber's year of journals/ or journals_senate/, and
    rollcall_outcomes._DIVISIONS, a year's House divisions in words --
    replaced by ones that note each year asked of them. None may be asked,
    and each check must run to its end, or the silence proves nothing."""
    import inspect

    class Asked(dict):
        def __init__(self, log):
            super().__init__()
            self.log = log

        def __contains__(self, key):
            self.log.append(key)
            return super().__contains__(key)

    calls = re.compile(r"\bSD\.load\(")
    them = [c for c in CHECKS if c["group"] != "data"
            and c["fn"] is not _session_checks_read_no_journals
            and calls.search(inspect.getsource(c["fn"]))]
    read, ended = {}, {}
    for c in them:
        log = []
        kept = SD._SAT, RO._DIVISIONS
        SD._SAT, RO._DIVISIONS = Asked(log), Asked(log)
        try:
            ended[c["fn"].__name__] = _check_outcome(c)
        finally:
            SD._SAT, RO._DIVISIONS = kept
        if log:
            read[c["fn"].__name__] = sorted({tuple(k) for k in log})
    assert len(them) >= 8, f"only {len(them)} checks call session_days.load() themselves"
    short = {n: o for n, o in ended.items() if o[0] in ("FAIL", "ERROR")}
    assert not short, f"checks that did not run to their end, so read nothing by it: {short}"
    assert not read, (f"{len(read)} checks read the Journals on disk for a record of their own; "
                      f"give load() journals= (none: {{}}): "
                      + "; ".join(f"{n} {ks[:4]}" for n, ks in read.items()))
    return "ok", (f"{len(them)} checks that call load() on a record of their own read no "
                  "chamber's year of Journals and no House divisions from the disk")


@check("session", "before the roll-call file, every roll call the docket states is "
       "drawn from the docket", needs=("session_days",))
def _session_rollcalls_docket_only(SD):
    """Before 1999 the docket is the only record of a roll call, and a line
    of several questions told one: "REP JACOBSON SUBST OTP, ML RC(111-234);
    LAID ON TABLE, MA VV" (HB 435 of 1990, Docket_db_1989-1990.txt) drew the
    tabling by voice and not the substitute motion that lost 111-234 first.
    With no roll-call file the docket's count and its own result stand."""
    narr = {"1989-1990": {"HB435": [
        {"type": "floor", "date": "1990-02-01", "body": "H", "raw": "REP JACOBSON SUBST OTP, ML RC(111-234); LAID ON TABLE, MA VV;HJ27 HJ27,P827-830", "cite": "HJ 27", "action": "Laid on Table", "motion": "MA", "vote_kind": "VV"}]}}
    days = _sitting_fixture(SD, narr, {})
    got = _motions(days[("H", "1990-02-01")], "HB435")
    assert got == [("Ought to Pass", "Rep. Jacobson", "RC", 111, 234, False),
                   ("Laid on Table", "", "VV", None, None, True)], got
    assert days[("H", "1990-02-01")].counts() == {"roll call": 1, "voice vote": 1}
    return "ok", "HB 435's substitute motion of 1 February 1990 is drawn, lost 111-234"


@check("session", "a committee of conference report is named on its sitting page, "
       "never told as Ought to Pass", needs=("session_days",))
def _session_conference_report_named(SD):
    """The 1999-2006 reader takes the bare "Adopted" of a Senate conference
    report row for the question and words it "Ought to Pass": SB 164's report
    of 26 June 2001, adopted 13-11 (Docket_db_2001-2002.txt line 6380), read
    "On the motion: Ought to Pass ... it carried in this chamber", and HB
    291's of 1 July 1999 (Docket_db_1999-2000.txt line 4970) "On the motion:
    Cohen". The motion before SB 164's report -- not to adopt it, lost 11-13
    -- keeps its own words."""
    narr = {
        "2001-2002": {"SB164": [
            {"type": "floor", "date": "2001-06-26", "body": "S", "raw": "Sen. McCarley Moved Non Adopt RC 11Y-13N, MF", "action": "Non Adopt", "motion": "MF", "vote_kind": "RC", "yeas": "11", "nays": "13", "mover": "Sen. McCarley", "cite": "SJ 19"},
            {"type": "floor", "date": "2001-06-26", "body": "S", "raw": "Conference Committee Report RC 13Y-11N, Adopted", "action": "Ought to Pass", "motion": "MA", "cite": "SJ 19"}]},
        "1999-2000": {"HB291": [
            {"type": "floor", "date": "1999-07-01", "body": "S", "raw": "Conf Comm Report, Sen, Cohen, MA, VV", "action": "Cohen", "motion": "MA", "vote_kind": "VV", "cite": "SJ 27"}]}}
    rolls = {"2001-2002": {"SB164": [
        _rc("2001", "S", 122, "2001-06-26", "SB164", "Sen. McCarley moved to not adopt the committee of conference report Sen. McCarley/Sen. O'Hearn", 11, 13, False),
        _rc("2001", "S", 123, "2001-06-26", "SB164", "Adoption of the committee of conference report Sen. McCarley/Sen. Barnes", 13, 11, True)]}}
    days = _sitting_fixture(SD, narr, rolls)
    got = _motions(days[("S", "2001-06-26")], "SB164")
    assert got == [("Non Adopt", "Sen. McCarley", "RC", 11, 13, False),
                   ("Adopt the Conference Committee Report", "", "RC", 13, 11, True)], got
    rep = days[("S", "2001-06-26")].items[-1]
    assert rep.outcome_words == "The motion was adopted on a roll call.", rep.outcome_words
    got = _motions(days[("S", "1999-07-01")], "HB291")
    assert got == [("Adopt the Conference Committee Report", "", "VV", None, None, True)], got
    return "ok", ("SB 164's report of 2001 and HB 291's of 1999 are named as committee of "
                  "conference reports, and the motion not to adopt one keeps its words")


@check("session", "a roll call is drawn on another motion only where the record makes "
       "it that motion", needs=("session_days",))
def _session_rollcall_not_on_the_wrong_motion(SD):
    """The roll-call file files the Senate's 14-10 kill of HB 617 of 26 May
    2005 under HB 611 (the Senate Journal prints it under HB 617, as the
    docket does). Drawn on HB 611's motion to kill, which the docket says
    failed by voice, it said HB 611 was killed. And SB 330's committee
    amendment, a division of 13-11 on 14 February 2002, is not SB 198's roll
    call of the same count and words. Rows and roll calls as the record holds
    them (Docket_db_2005-2006.txt, Docket_db_2001-2002.txt)."""
    narr = {
        "2005-2006": {
            "HB611": [{"type": "floor", "date": "2005-05-26", "body": "S", "raw": "Inexpedient to Legislate, MF, VV", "action": "Inexpedient to Legislate", "motion": "MF", "vote_kind": "VV", "cite": "SJ 19"}],
            "HB617": [{"type": "floor", "date": "2005-05-26", "body": "S", "raw": "Inexpedient to Legislate, RC 14Y-10N, MA", "action": "Inexpedient to Legislate", "motion": "MA", "vote_kind": "RC", "yeas": "14", "nays": "10", "cite": "SJ 19"}]},
        "2001-2002": {
            "SB198": [{"type": "floor", "date": "2002-02-14", "body": "S", "raw": "Ought to Pass with Amendment {2228},(New Title) RC 13y - 11n, AA", "action": "Ought to Pass with Amendment", "motion": "MA", "vote_kind": "RC", "yeas": "13", "nays": "11", "cite": "SJ 5"}],
            "SB330": [{"type": "floor", "date": "2002-02-14", "body": "S", "raw": "Ought to Pass with Amendment {2588},(New Title), Division 13y - 11n, AA", "action": "Ought to Pass with Amendment", "motion": "MA", "yeas": "13", "nays": "11", "cite": "SJ 5"}]}}
    rolls = {
        "2005-2006": {"HB611": [_rc("2005", "S", 62, "2005-05-26", "HB611", "Inexpedient to Legislate", 14, 10, True)]},
        "2001-2002": {"SB198": [_rc("2002", "S", 40, "2002-02-14", "SB198", "Adoption of the committee amendment (2228s) Sen. Pignatelli/Sen Barnes", 13, 11, True)]}}
    days = _sitting_fixture(SD, narr, rolls)
    may = {i.bill: i for i in days[("S", "2005-05-26")].items}
    assert (may["HB611"].kind, may["HB611"].carried, may["HB611"].rc) == ("VV", False, None), (
        f"HB 611's failed motion to kill is drawn as {may['HB611'].kind} {may['HB611'].yeas}-"
        f"{may['HB611'].nays} carried={may['HB611'].carried}")
    assert may["HB617"].rc is not None and (may["HB617"].yeas, may["HB617"].carried) == (14, True)
    feb = {i.bill: i for i in days[("S", "2002-02-14")].items}
    assert feb["SB330"].rc is None and not feb["SB330"].shared and \
        days[("S", "2002-02-14")].counts().get("roll call") == 1, (
        feb["SB330"].rc, feb["SB330"].shared, days[("S", "2002-02-14")].counts())
    return "ok", ("the 14-10 of 26 May 2005 is HB 617's, not HB 611's failed voice vote, and "
                  "SB 330's division is not SB 198's roll call")


@check("session", "a roll call drawn between two of a bill's motions does not part "
       "them, so neither claims a speech the record ties to neither",
       needs=("session_days", "build_session_pages"))
def _session_drawn_vote_does_not_part_a_bill(SD, BSP):
    """HB 1633's tabling (page 33, a division 178-173) and its removal from
    the table (page 36, a roll call 162-189) of 13 June 2024 were one run of
    the day, and Rep. Jared Sullivan's speech, which the journal ties to
    neither count, was listed as spoken during the bill. HB 1665's conference
    report, failed 168-185 at page 34 and drawn since the page draws every
    roll call, fell between them and made two runs of one motion each, and
    each claimed the speech as its one motion's."""
    import html as _html
    narr = {"2023-2024": {
        "HB1633": [
            {"type": "floor", "date": "2024-06-13", "body": "H", "raw": "Lay HB1633 on Table (Rep. Simon): MA DV 178-173 06/13/2024", "action": "Lay HB1633 on Table", "motion": "MA", "vote_kind": "DV", "yeas": "178", "nays": "173", "mover": "Rep. Simon", "cite": "HJ 16", "cite_page": "33"},
            {"type": "floor", "date": "2024-06-13", "body": "H", "raw": "Remove from Table (Rep. Prout): MF RC 162-189 06/13/2024", "action": "Remove from Table", "motion": "MF", "vote_kind": "RC", "yeas": "162", "nays": "189", "mover": "Rep. Andrew Prout", "cite": "HJ 16", "cite_page": "36"}],
        "HB1665": [
            {"type": "other", "date": "2024-06-13", "body": "H", "raw": "Conference Committee Report 2024-2307c: Failed, RC 168-185 06/13/2024", "cite": "HJ 16", "cite_page": "34"}]}}
    rolls = {"2023-2024": {
        "HB1633": [_rc("2024", "H", 285, "2024-06-13", "HB1633", "Remove From Table", 162, 189, False)],
        "HB1665": [_rc("2024", "H", 284, "2024-06-13", "HB1665", "Adopt Conference Committee Report", 168, 185, False)]}}
    day = _sitting_fixture(SD, narr, rolls)[("H", "2024-06-13")]
    assert [i.bill for i in day.items] == ["HB1633", "HB1665", "HB1633"], [i.bill for i in day.items]
    found = {"attributions": [{"bill": "HB1633-FN-A", "side": "against", "names": ["Jared Sullivan"],
                               "tally": None, "inline_motion": None, "moved_since": []}]}
    html, _ = BSP.render(day, found, {}, {}, BSP.Members(Path("no-such-site")), _html.escape)
    assert "Spoke against the motion" not in html and html.count("Rep. Jared Sullivan") == 1 and \
        "Also spoke during this bill" in html, re.sub(r"<[^>]+>", " ", html)[:600]
    return "ok", ("HB 1665's conference report between HB 1633's two motions leaves Rep. "
                  "Sullivan's speech spoken during the bill, once")


@check("session", "a roll call is drawn once: a motion's own clause, a count the "
       "reader missed and the question's own words find the roll call on record",
       needs=("session_days",))
def _session_rollcall_drawn_once(SD):
    """Reviewed on 2 October 2026, ten pages drew one vote twice. A motion
    read with no count stayed beside its own clause drawn again (HB 1, 30
    June 2003: "Limit Debate ML RC(160-205); Veto Sustained ... RC(245-128)");
    a count in a form the reader did not take left HR 25's suspension of 24
    May 2006 ("..., MA, RC (292-48)") apart from its roll call, which was
    drawn again among the votes on no bill; and where a day held several
    roll calls of one count, the Senate's suspensions of 7 June 2007 for
    CACR 19 and CACR 20 (17-7 each, filed "(Rule Suspension Sen. Larsen)"
    and "(Rule Suspension Sen. Gatsas)"), its consent calendar of 18
    February 2021 and its special order of HB 296 and HB 615 of 29 April 2021
    (every vote 24-0) were drawn under their bills and again on no bill.
    Rows and roll calls as the record holds them."""
    narr = {
        "2003-2004": {"HB1": [
            {'type': 'other', 'date': '2003-06-30', 'body': 'H', 'raw': 'Rep Kurk moved to Limit Debate, Rep Vaillancourt moved to Am Motion, AL DIV(156-204)'},
            {'type': 'floor', 'date': '2003-06-30', 'body': 'H', 'raw': 'Limit Debate ML RC(160-205); Veto Sustained -failed nec 2/3- RC(245-128); HB 52, p1641-1645', 'action': 'Limit Debate', 'motion': 'ML', 'vote_kind': 'RC'}]},
        "2005-2006": {"HR25": [
            {'type': 'floor', 'date': '2006-05-24', 'body': 'H', 'raw': 'Suspension of Rules, Introduced after deadlines & consideration at present time and immediate third reading, MA, RC (292-48)', 'action': 'Introduced after deadlines & consideration at present time and immediate third reading', 'motion': 'MA', 'vote_kind': 'RC', 'cite': 'HJ 46'},
            {'type': 'floor', 'date': '2006-05-24', 'body': 'H', 'raw': 'Introduced, MA, VV', 'action': 'Introduced', 'motion': 'MA', 'vote_kind': 'VV', 'cite': 'HJ 46'},
            {'type': 'floor', 'date': '2006-05-24', 'body': 'H', 'raw': 'Rep. Albert, OTP, MA, RC (318-24)', 'action': 'Ought to Pass', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '318', 'nays': '24', 'cite': 'HJ 46'}]},
        "2007-2008": {b: [
            {'type': 'floor', 'date': '2007-06-07', 'body': 'S', 'raw': f'Sen. {who} Rules Suspension 18b,21,22,24,[48a,b,c,d,g,h] for Introduction; 2/3 nec. RC 17Y-7N, MA', 'action': f'Sen. {who} Rules Suspension 18b,21,22,24,[48a,b,c,d,g,h] for Introduction; 2/3 nec.', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '17', 'nays': '7'}]
            for b, who in (("CACR19", "Larsen"), ("CACR20", "Gatsas"))},
        "2021-2022": {
            "SB103": [
                {'type': 'report', 'date': '2021-02-18', 'body': 'S', 'raw': 'Committee Report: Ought to Pass, 02/18/2021; Vote 5-0; CC', 'yeas': '5', 'nays': '0', 'cite': 'SC 11'},
                {'type': 'floor', 'date': '2021-02-18', 'body': 'S', 'raw': 'Ought to Pass : RC 24Y-0N, MA; OT3rdg; 02/18/2021', 'action': 'Ought to Pass : RC 24Y-0N', 'motion': 'MA', 'cite': 'SJ 5'}],
            "SB120": [
                {'type': 'report', 'date': '2021-02-18', 'body': 'S', 'raw': 'Committee Report: Ought to Pass, 02/18/2021; Vote 5-0; CC', 'yeas': '5', 'nays': '0', 'cite': 'SC 11'},
                {'type': 'other', 'date': '2021-02-18', 'body': 'S', 'raw': 'Sen. Sherman Moved to Remove SB 120 from the Consent Calendar; 02/18/2021', 'cite': 'SJ 5'},
                {'type': 'amendment', 'date': '2021-02-18', 'body': 'S', 'raw': 'Sen. Sherman Floor Amendment #2021-0429s , RC 24Y-0N, AA; 02/18/2021', 'motion': 'AA', 'vote_kind': 'RC', 'mover': 'Sen. Sherman', 'cite': 'SJ 5', 'amendment': '2021-0429s', 'amend_kind': 'Floor Amendment'},
                {'type': 'floor', 'date': '2021-02-18', 'body': 'S', 'raw': 'Ought to Pass with Amendment 2021-0429s, RC 24Y-0N, MA; OT3rdg; 02/18/2021', 'action': 'Ought to Pass with Amendment 2021-0429s, RC 24Y-0N', 'motion': 'MA', 'cite': 'SJ 5'}],
            **{b: [{'type': 'floor', 'date': '2021-04-29', 'body': 'S', 'raw': 'Sen. Bradley Moved to Special Order to 05/06/2021, RC 24Y-0N, MA; 04/29/2021', 'action': 'Special Order to 05/06/2021, RC 24Y-0N', 'motion': 'MA', 'mover': 'Sen. Bradley', 'cite': 'SJ 13'}]
               for b in ("HB296", "HB615")}}}
    rolls = {
        "2003-2004": {"HB1": [_rc('2003', 'H', 109, '2003-06-30', 'HB1', 'REP KURK:  LIMIT DEBATE', 160, 205, False),
                              _rc('2003', 'H', 110, '2003-06-30', 'HB1', "OVERRIDE GOVERNOR'S VETO", 245, 128, False, 249)]},
        "2005-2006": {"HR25": [_rc('2006', 'H', 200, '2006-05-24', 'HR25', 'REP ALBERT: OTP', 318, 24, True)],
                      "_procedural": [_rc('2006', 'H', 199, '2006-05-24', None, "REP O'NEIL: RULES SUSPENSION - INTRODUCTION OF RESOLUTION", 292, 48, True, 227)]},
        "2007-2008": {"_procedural": [_rc('2007', 'S', 150, '2007-06-07', 'RULE', '(Rule Suspension Sen. Larsen)   Sen. Clegg/Sen. Kenney', 17, 7, True, 16),
                                      _rc('2007', 'S', 151, '2007-06-07', 'RULE', '(Rule Suspension Sen. Gatsas) Sen. Kenney/Sen. Barnes', 17, 7, True, 16)]},
        "2021-2022": {
            "SB120": [_rc('2021', 'S', 69, '2021-02-18', 'SB120', 'Floor Amendment 0429s', 24, 0, True),
                      _rc('2021', 'S', 70, '2021-02-18', 'SB120', 'Ought to Pass with Amendment', 24, 0, True)],
            "_procedural": [
            _rc('2021', 'S', 52, '2021-02-18', 'LATE', 'Adjourn Late Session', 24, 0, True),
            _rc('2021', 'S', 54, '2021-02-18', 'REPORT', 'Finance Report', 24, 0, True),
            _rc('2021', 'S', 55, '2021-02-18', 'CONSENT', 'Consent Calendar', 24, 0, True),
            _rc('2021', 'S', 75, '2021-02-18', 'EARLY', 'Adjourn Early Session', 24, 0, True),
            _rc('2021', 'S', 326, '2021-04-29', None, 'Adjourn Late Session', 24, 0, True),
            _rc('2021', 'S', 328, '2021-04-29', None, 'Special Order HB 296-FN and HB 615-FN to Thursday, May 6, 2021', 24, 0, True),
            _rc('2021', 'S', 329, '2021-04-29', None, 'Finance Report', 24, 0, True)]}}
    days = _sitting_fixture(SD, narr, rolls)
    hb1 = days[("H", "2003-06-30")]
    assert [(i.action, i.kind, i.yeas, i.nays) for i in hb1.items] == [
        ("Limit Debate", "RC", 160, 205), ("Override the Governor's veto", "RC", 245, 128)], (
        [(i.action, i.kind, i.yeas, i.nays) for i in hb1.items])
    hr = days[("H", "2006-05-24")]
    assert hr.items[0].rc is not None and SD.rollcall_key(hr.items[0].rc)[2] == 199 and \
        not hr.others and hr.counts() == {"roll call": 2, "voice vote": 1}, (hr.counts(), hr.others)
    jun = days[("S", "2007-06-07")]
    assert {i.bill: SD.rollcall_key(i.rc)[2] for i in jun.items} == {"CACR19": 150, "CACR20": 151} \
        and not jun.others and jun.counts() == {"roll call": 2}, (jun.counts(), jun.others)
    feb = days[("S", "2021-02-18")]
    cal = [i for i in feb.items if i.bill == "SB103"][0]
    # SB 120 came off the calendar ("Moved to Remove SB 120 from the Consent
    # Calendar") and was voted on alone, 24-0, its own roll call -- and SB
    # 103, left on the calendar alone (as it was, SB 38 off it too), is the
    # calendar's roll call #55 and not a vote of its own beside it: once the
    # removal was read (narrative.removed_from_consent), a lone bill with the
    # calendar's count was taken for a vote after it came off, and #55 was
    # drawn again on no bill (session_days._one_counted_vote).
    alone = [i for i in feb.items if i.bill == "SB120" and i.rc is not None]
    assert alone and not any(i.consent for i in alone), [(i.action, i.consent) for i in alone]
    assert not any(i.consent for e, i in SD.floor_items(
        "SB120", "2021-2022", narr["2021-2022"]["SB120"])), "SB 120's removal is not read"
    assert cal.rc is not None and SD.rollcall_key(cal.rc)[2] == 55 and cal.consent and \
        [SD.rollcall_key(i.rc)[2] for i in feb.others] == [52, 54, 75] and \
        feb.counts() == {"roll call": 6}, (feb.counts(), [i.action for i in feb.others])
    apr = days[("S", "2021-04-29")]
    # and the docket's count is not left in the motion's words to disagree
    # with the count drawn beneath them
    assert {i.action for i in apr.items} == {"Special Order to 05/06/2021"}, (
        {i.action for i in apr.items})
    assert {SD.rollcall_key(i.rc)[2] for i in apr.items} == {328} and \
        [SD.rollcall_key(i.rc)[2] for i in apr.others] == [326, 329] and \
        apr.counts() == {"roll call": 3}, (apr.counts(), [i.action for i in apr.others])
    assert not _one_roll_call_each(days)
    return "ok", ("HB 1's limit on debate, HR 25's suspension, CACR 19's and CACR 20's, the "
                  "consent calendar and HB 296's and HB 615's special order are each one "
                  "roll call, drawn once")


@check("session", "a roll call is drawn under the bill the record gives it: a docket row "
       "that states it, or the roll-call file's own bill", needs=("session_days",))
def _session_rollcall_under_its_bill(SD):
    """The Senate's 16-8 adoption of SB 287's conference report on 26 June
    2025 is filed under HB 287 in the roll-call file, and was drawn under HB
    287 -- a House bill killed in February -- with "the docket has no line
    for this vote", while SB 287's own row stating it went undrawn. And the
    House's 15-340 refusal to reconsider withdrawing HB 476 on 6 February
    2025 was drawn among the "votes on no bill", the docket holding no rows
    for the bill. Rows and roll calls as the record holds them (Docket.txt;
    rollcalls/RollCallHistory_2025.txt)."""
    narr = {"2025-2026": {
        "SB287": [{'type': 'other', 'date': '2025-06-26', 'body': 'S', 'raw': 'Conference Committee Report # 2025-2797c; RC 16Y-8N, Adopted; 06/26/2025', 'cite': 'SJ 17'}],
        "HB287": [{'type': 'floor', 'date': '2025-02-20', 'body': 'H', 'raw': 'Inexpedient to Legislate: MA DV 201-163 02/20/2025', 'action': 'Inexpedient to Legislate', 'motion': 'MA', 'vote_kind': 'DV', 'yeas': '201', 'nays': '163', 'cite': 'HJ 6', 'cite_page': '19'}],
        "HB60": [{'type': 'floor', 'date': '2025-02-06', 'body': 'H', 'raw': 'Ought to Pass: MA VV 02/06/2025', 'action': 'Ought to Pass', 'motion': 'MA', 'vote_kind': 'VV', 'cite': 'HJ 4', 'cite_page': '20'}]}}
    rolls = {"2025-2026": {
        "HB287": [_rc('2025', 'S', 117, '2025-06-26', 'HB287', 'Adopt Conference Committee Report', 16, 8, True)],
        "HB476": [_rc('2025', 'H', 3, '2025-02-06', 'HB476', 'Reconsider', 15, 340, False)]}}
    days = _sitting_fixture(SD, narr, rolls)
    s = days[("S", "2025-06-26")]
    assert [(i.bill, i.action, i.kind, i.yeas, i.nays, SD.rollcall_key(i.rc)[2]) for i in s.items] == [
        ("SB287", "Adopt the Conference Committee Report 2025-2797c", "RC", 16, 8, 117)], (
        [(i.bill, i.action) for i in s.items])
    h = days[("H", "2025-02-06")]
    hb = [i for i in h.items if i.bill == "HB476"]
    assert len(hb) == 1 and hb[0].added == "rollcall" and not h.others and \
        h.counts() == {"roll call": 1, "voice vote": 1}, (h.counts(), h.others)
    # Without SB 287's row the roll call stays HB 287's, and on a day the
    # record gives no order it is listed in its bill's place, not after the
    # roll call before it by number: it sat between HB 115 and HB 2.
    narr["2025-2026"].pop("SB287")
    narr["2025-2026"]["HB115"] = [
        {'type': 'floor', 'date': '2025-06-26', 'body': 'S', 'raw': 'Ought to Pass with Amendment #2025-2880s, MA, VV; OT3rdg; Read a Third Time and Final Passage in the Early Session; 06/26/2025', 'action': 'Ought to Pass with Amendment #2025-2880s', 'motion': 'MA', 'vote_kind': 'VV', 'cite': 'SJ 17'},
        {'type': 'amendment', 'date': '2025-06-26', 'body': 'S', 'raw': 'Sen. Rosenwald Floor Amendment # 2025-2893s, RC 8Y-16N, AF; 06/26/2025', 'motion': 'AF', 'vote_kind': 'RC', 'mover': 'Sen. Rosenwald', 'cite': 'SJ 17', 'amendment': '2025-2893s', 'amend_kind': 'Floor Amendment'}]
    narr["2025-2026"]["HB2"] = [{'type': 'other', 'date': '2025-06-26', 'body': 'S', 'raw': 'Conference Committee Report # 2025-2871c; RC 16Y-8N, Adopted; 06/26/2025', 'cite': 'SJ 17'}]
    rolls["2025-2026"]["HB115"] = [_rc('2025', 'S', 116, '2025-06-26', 'HB115', 'Adopt Floor Amendment', 8, 16, False)]
    rolls["2025-2026"]["HB2"] = [_rc('2025', 'S', 115, '2025-06-26', 'HB2', 'Adopt Conference Committee Report', 16, 8, True)]
    s = _sitting_fixture(SD, narr, rolls)[("S", "2025-06-26")]
    assert [i.bill for i in s.items] == ["HB115", "HB115", "HB2", "HB287"] and not s.ordered, (
        [i.bill for i in s.items])
    # A bill the term's list does not hold is no bill the record can name:
    # the Senate's 13-11 suspension of 27 June 2002 is filed under an SB 457
    # of 2001-2002 there is none of, and is drawn as a vote of the day.
    narr = {"2001-2002": {"SR1": [
        {'type': 'floor', 'date': '2002-06-27', 'body': 'S', 'raw': 'Sen. Klemm Moved Introduction of SR1, MA, VV', 'action': 'Introduction of SR1', 'motion': 'MA', 'vote_kind': 'VV', 'mover': 'Sen. Klemm', 'cite': 'SJ 16'}]}}
    rolls = {"2001-2002": {"SB457": [_rc('2002', 'S', 142, '2002-06-27', 'SB457', 'adoption of the suspension of the rules  Sen. Below/Sen. McCarley', 13, 11, True)]}}
    jun = _sitting_fixture(SD, narr, rolls, held={"2001-2002": ["SR1", "SB456"]})[("S", "2002-06-27")]
    assert [i.bill for i in jun.items] == ["SR1"] and [SD.rollcall_key(i.rc)[2] for i in jun.others] == [142], (
        [i.bill for i in jun.items], jun.others)
    return "ok", ("SB 287's conference report is drawn under SB 287, HB 476's vote under HB "
                  "476, a roll call no row states in its bill's place on a day of no order, and "
                  "one filed under a bill the term does not hold as a vote of the day")


@check("session", "a vote is drawn where the chamber's journal prints it, and once",
       needs=("session_days",))
def _session_rollcall_where_the_journal_prints_it(SD):
    """The docket enters HB 1599's kill of 2006 on 15 February as "RC
    (211-79)" and the roll-call file has it, 211-74, on the 16th: each was
    drawn on its own day's page. SB 336's kill of 15 May 2014 is entered on
    Monday the 19th, a day the House did not sit, and made a page saying the
    House took one roll call that day; House Journal 21 prints it on the
    15th, with the roll-call file. HB 2's amendment 1163h of 2017 is entered
    on 5 April and printed in House Journal 13 of Thursday 6 April, the
    roll-call file's day. Rows and roll calls as the record holds them; the
    journals as the counts they print."""
    narr = {
        "2005-2006": {
            "HB1599": [{'type': 'floor', 'date': '2006-02-15', 'body': 'H', 'raw': 'ITL, MA, RC (211-79) HJ 19a, pg 1181-1183', 'action': 'Inexpedient to Legislate', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '211', 'nays': '79', 'cite': 'HJ 19a'}],
            "HB1": [{'type': 'floor', 'date': '2006-02-16', 'body': 'H', 'raw': 'Passed VV', 'action': 'Ought to Pass', 'motion': 'MA', 'vote_kind': 'VV'}]},
        "2013-2014": {
            "SB336": [{'type': 'floor', 'date': '2014-05-19', 'body': 'H', 'raw': 'Inexpedient to Legislate MA RC 200-85', 'action': 'Inexpedient to Legislate', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '200', 'nays': '85'}],
            "SB307": [{'type': 'floor', 'date': '2014-05-15', 'body': 'H', 'raw': 'Ought to Pass with Amendment #1600h MA RC 183-87', 'action': 'Ought to Pass with Amendment #1600h', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '183', 'nays': '87'}]},
        "2017-2018": {"HB2": [
            {'type': 'amendment', 'date': '2017-04-05', 'body': 'H', 'raw': 'Amendment #2017-1163h : AF RC 169-177 04/05/2017', 'motion': 'AF', 'vote_kind': 'RC', 'cite': 'HJ 13', 'cite_page': '60', 'amendment': '2017-1163h', 'amend_kind': 'Amendment'},
            {'type': 'floor', 'date': '2017-04-05', 'body': 'H', 'raw': 'Lay on Table (Rep. Hinch): MA VV 04/05/2017', 'action': 'Lay on Table', 'motion': 'MA', 'vote_kind': 'VV', 'mover': 'Rep. Hinch', 'cite': 'HJ 13', 'cite_page': '62'},
            {'type': 'floor', 'date': '2017-04-06', 'body': 'H', 'raw': 'Lay on Table (Rep. Hoell): MF VV 04/06/2017', 'action': 'Lay on Table', 'motion': 'MF', 'vote_kind': 'VV', 'mover': 'Rep. Hoell'}]}}
    rolls = {
        "2005-2006": {"HB1599": [_rc('2006', 'H', 73, '2006-02-16', 'HB1599', 'COMMITTEE REPORT: ITL', 211, 74, True)]},
        "2013-2014": {"SB336": [_rc('2014', 'H', 251, '2014-05-15', 'SB336', 'Inexpedient to Legislate', 200, 85, True)],
                      "SB307": [_rc('2014', 'H', 264, '2014-05-15', 'SB307', 'Ought to Pass with Amendment', 183, 87, True)]},
        "2017-2018": {"HB2": [_rc('2017', 'H', 111, '2017-04-06', 'HB2', 'Adopt Amendment', 169, 177, False)]}}
    journals = {("H", "2014-05-15"): {"rc": [(200, 85), (183, 87)]},
                ("H", "2017-04-05"): {"rc": [(72, 276)]},
                ("H", "2017-04-06"): {"rc": [(169, 177)]}}
    days = _sitting_fixture(SD, narr, rolls, journals=journals)
    feb = days[("H", "2006-02-15")].items[0]
    assert (feb.yeas, feb.nays, feb.said) == (211, 74, (211, 79)) and \
        days[("H", "2006-02-16")].counts() == {"voice vote": 1}, (
        feb.yeas, feb.said, days[("H", "2006-02-16")].counts())
    may = days[("H", "2014-05-15")]
    assert ("H", "2014-05-19") not in days and may.counts() == {"roll call": 2} and \
        [i.entered for i in may.items if i.bill == "SB336"] == ["2014-05-19"], (
        sorted(days), may.counts())
    apr6 = days[("H", "2017-04-06")]
    assert [(i.action, i.kind, i.entered) for i in apr6.items if i.kind == "RC"] == [
        ("Adopt Amendment 2017-1163h", "RC", "2017-04-05")] and \
        "roll call" not in days[("H", "2017-04-05")].counts(), (
        [(i.action, i.kind) for i in apr6.items], days[("H", "2017-04-05")].counts())
    assert not _one_roll_call_each(days)
    return "ok", ("HB 1599 is drawn once with the ballots' count; SB 336 and HB 2's "
                  "amendment are on the sittings their journals print them on")


@check("session", "where the journal is on disk, a division stays a division and a "
       "count copied from another row is not a roll call", needs=("session_days",))
def _session_journal_holds_the_count(SD):
    """HB 299's kill of 20 February 2025 is "MA DV 193-177" in the docket and
    "On a division vote, with 193 members having voted in the affirmative,
    and 177 in the negative" in House Journal 6, though the roll-call file
    holds it: the page called it a roll call. HB 461's report of 22 January
    2014 is entered "MA RC 289-48", HB 597's roll call that day; the journal
    prints 289-48 once, of HB 597. HB 1559's "Special Order ... MF RC
    156-195" of 12 March 2026 is HB 1708's, on a bill the day's journal never
    names, and the page said "One roll call on 2 bills". HB 194's report of
    4 January 2024 is entered twice. And the Senate's enrolled bills reports
    of 2021, "Enrolled RC 24Y-0N, MA, (In recess of 04/08/2021)", are no roll
    call: the Senate Journal says "Adopted in recess"."""
    narr = {
        "2025-2026": {
            "HB299": [{'type': 'floor', 'date': '2025-02-20', 'body': 'H', 'raw': 'Inexpedient to Legislate: MA DV 193-177 02/20/2025', 'action': 'Inexpedient to Legislate', 'motion': 'MA', 'vote_kind': 'DV', 'yeas': '193', 'nays': '177', 'cite': 'HJ 6', 'cite_page': '51'}],
            "HB1559": [{'type': 'floor', 'date': '2026-03-12', 'body': 'H', 'raw': 'Special Order to next order of business (Rep. Vallone): MF RC 156-195 03/12/2026', 'action': 'Special Order to next order of business', 'motion': 'MF', 'vote_kind': 'RC', 'yeas': '156', 'nays': '195', 'mover': 'Rep. Mark Vallone', 'cite': 'HJ 8'}],
            "HB1708": [{'type': 'floor', 'date': '2026-03-12', 'body': 'H', 'raw': 'Special Order to next order of business (Rep. Malone): MF RC 156-195 03/12/2026', 'action': 'Special Order to next order of business', 'motion': 'MF', 'vote_kind': 'RC', 'yeas': '156', 'nays': '195', 'mover': 'Rep. Amy Malone', 'cite': 'HJ 8', 'cite_page': '58'}]},
        "2013-2014": {
            "HB461": [{'type': 'amendment', 'date': '2014-01-22', 'body': 'H', 'raw': 'Adopt Amendment #13-2337h AA VV', 'motion': 'AA', 'vote_kind': 'VV', 'amendment': '13-2337h', 'amend_kind': 'Amendment'},
                      {'type': 'floor', 'date': '2014-01-22', 'body': 'H', 'raw': 'Ought to Pass with Amendment #2337h MA RC 289-48', 'action': 'Ought to Pass with Amendment #2337h', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '289', 'nays': '48'}],
            "HB597": [{'type': 'floor', 'date': '2014-01-22', 'body': 'H', 'raw': 'Ought to Pass with Amendment #2261h(NT) MA RC 289-48', 'action': 'Ought to Pass with Amendment #2261h(NT)', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '289', 'nays': '48'}]},
        "2023-2024": {"HB194": [{'type': 'floor', 'date': '2024-01-04', 'body': 'H', 'raw': 'Ought to Pass with Amendment 2023-0037h: MA RC 194-179 01/04/2024', 'action': 'Ought to Pass with Amendment 2023-0037h', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '194', 'nays': '179', 'cite': 'HJ 2', 'cite_page': '35'}] * 2},
        "2021-2022": {b: [{'type': 'floor', 'date': '2021-04-08', 'body': 'S', 'raw': 'Enrolled RC 24Y-0N, MA, (In recess of 04/08/2021)', 'action': 'Enrolled RC 24Y-0N', 'motion': 'MA'}]
                      for b in ("HB150", "HB173")}}
    rolls = {
        "2025-2026": {"HB299": [_rc('2025', 'H', 38, '2025-02-20', 'HB299', 'Inexpedient to Legislate', 193, 177, True)],
                      "HB1708": [_rc('2026', 'H', 201, '2026-03-12', 'HB1708', 'Special Order', 156, 195, False)]},
        "2013-2014": {"HB597": [_rc('2014', 'H', 34, '2014-01-22', 'HB597', 'Ought to Pass with Amendment', 289, 48, True)]},
        "2023-2024": {"HB194": [_rc('2024', 'H', 26, '2024-01-04', 'HB194', 'Ought to Pass with Amendment', 194, 179, True)]}}
    journals = {("H", "2025-02-20"): {"div": [(193, 177)], "bills": ["HB299"]},
                ("H", "2014-01-22"): {"rc": [(289, 48)], "bills": ["HB461", "HB597"]},
                ("H", "2026-03-12"): {"rc": [(156, 195)], "bills": ["HB1708"]},
                ("H", "2024-01-04"): {"rc": [(194, 179)], "bills": ["HB194"]}}
    days = _sitting_fixture(SD, narr, rolls, journals=journals)
    feb = days[("H", "2025-02-20")]
    assert feb.items[0].kind == "DV" and feb.items[0].rc is not None and \
        feb.counts() == {"division": 1}, (feb.items[0].kind, feb.counts())
    jan = {i.bill: i for i in days[("H", "2014-01-22")].items}
    assert not jan["HB461"].counted and jan["HB461"].kind == "" and jan["HB461"].carried and \
        days[("H", "2014-01-22")].counts() == {"roll call": 1}, (
        days[("H", "2014-01-22")].counts(), jan["HB461"].kind)
    mar = days[("H", "2026-03-12")]
    assert [i.bill for i in mar.items] == ["HB1708"] and not mar.items[0].shared and \
        mar.counts() == {"roll call": 1}, ([i.bill for i in mar.items], mar.counts())
    assert len(days[("H", "2024-01-04")].items) == 1, days[("H", "2024-01-04")].items
    apr = days[("S", "2021-04-08")]
    assert all(not i.counted and i.action == "Enrolled" for i in apr.items) and \
        "roll call" not in apr.counts(), [(i.action, i.kind) for i in apr.items]
    return "ok", ("HB 299's division stays one; HB 461's copied count, HB 1559's copied row, "
                  "HB 194's second entry and the Senate's enrolled reports in recess are no "
                  "roll call")


@check("session", "one motion entered on several bills is one vote, and a consent "
       "calendar one, before the roll-call file as after", needs=("session_days",))
def _session_one_motion_one_vote(SD):
    """Before 1999 the docket is all there is: "REP COOPER MOVED TO LAY
    REMAINDER OF CAL ON TABLE, ML RC(133-163)" is entered on eight bills of
    24 September 1998 and was counted eight times, and the consent calendar
    of 7 January 1998, "PASSED WITH AM/CONSENT CAL RC(248-8)", was counted
    once per bill -- 116 roll calls on a day of six. Rows as
    Docket_db_1997-1998.txt holds them."""
    lay = 'REP COOPER MOVED TO LAY REMAINDER OF CAL ON TABLE, ML RC(133-163) HJ78,P2521-2523'
    narr = {"1997-1998": {
        "HB1669": [{'type': 'other', 'date': '1998-09-24', 'body': 'H', 'raw': lay, 'cite': 'HJ 78'},
                   {'type': 'floor', 'date': '1998-09-24', 'body': 'H', 'raw': 'ITL REPORT ADOPTED VV; HJ78,P2523', 'action': 'Inexpedient to Legislate', 'motion': 'MA', 'vote_kind': 'VV', 'cite': 'HJ 78'}],
        "HB1670": [{'type': 'other', 'date': '1998-09-24', 'body': 'H', 'raw': lay, 'cite': 'HJ 78'},
                   {'type': 'floor', 'date': '1998-09-24', 'body': 'H', 'raw': 'ITL REPORT ADOPTED RC(209-77); HJ78,P2523-2525', 'action': 'Inexpedient to Legislate', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '209', 'nays': '77', 'cite': 'HJ 78'}],
        "HB111": [{'type': 'floor', 'date': '1998-01-07', 'body': 'H', 'raw': 'PASSED WITH AM/CONSENT CAL RC(248-8); HJ3,P171 + HJ3A,P218', 'action': 'Ought to Pass with Amendment', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '248', 'nays': '8', 'cite': 'HJ 3'}],
        "HB132": [{'type': 'floor', 'date': '1998-01-07', 'body': 'H', 'raw': 'PASSED WITH AM/CONSENT CAL RC(248-8); HJ3,P178 + HJ3A,P218', 'action': 'Ought to Pass with Amendment', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '248', 'nays': '8', 'cite': 'HJ 3'}],
        # CACR 44's whole day, typed "report" by its first words: five roll
        # calls, the last glued to its threshold, "FAILS 3/5RC(192-153)"
        "CACR44": [{'type': 'report', 'date': '1998-09-24', 'body': 'H', 'raw': 'COMM REPT: ITL ML VV; REPS KURK & BURLING FL AM<2454>, AA RC(192-156); REP HOLT FL AM<2448>, AL VV;REP WEYLER FL AM<2452> AL RC(82-257); REP VACHON FL AM<2432>, AL DIV(22-246); REPS FRANKS ET AL FL AM<2425>, AL RC(110-197); REP ALGER WITHDREW FL AM<2434>; REP BICKFORD FL AM<2451>, AL VV;REP HEMON FL AM<2449> AL DIV(24-290); REP HEMON FL AM<2456>, AL DIV(8-310); REP MARTIN FL AM<2458>(NT), AL RC(44-300); COMM REPT: OTP/AM, FAILS 3/5RC(192-153); HJ78,P2492-2515', 'cite': 'HJ 78'},
                   {'type': 'floor', 'date': '1998-09-24', 'body': 'H', 'raw': 'INDEF POSTPONED [ALL BILLS NOT ACTED ON], REPS WHEELER & BURLING MA BY NEC 2/3VV; HJ78,P2542 (SEE PERM JOURNAL ALSO)', 'action': 'Indefinitely Postpone', 'motion': 'MA', 'vote_kind': 'VV', 'cite': 'HJ 78'}]}}
    days = _sitting_fixture(SD, narr, {})
    sep = days[("H", "1998-09-24")]
    assert sep.counts() == {"roll call": 7, "voice vote": 2} and \
        sorted(i.shared for i in sep.items if i.yeas == 133) == [2, 2] and \
        sorted((i.yeas, i.nays) for i in sep.items if i.bill == "CACR44" and i.counted) == [
            (44, 300), (82, 257), (110, 197), (192, 153), (192, 156)], (
        sep.counts(), [(i.bill, i.action, i.yeas, i.nays, i.shared) for i in sep.items])
    assert days[("H", "1998-01-07")].counts() == {"roll call": 1}, days[("H", "1998-01-07")].counts()
    return "ok", "the laying on the table of 24 September 1998 and the consent calendar of 7 January 1998 are one roll call each"


@check("session", "a speech is tied to a motion only by the journal's count, the same "
       "member is never on both sides of one motion, and a name is said once",
       needs=("session_days", "build_session_pages"))
def _session_speeches_by_the_record(SD, BSP):
    """SB 101's amendment 1451h of 23 April 2026 cites page 37, where SB 586
    is too, so the bill's motions fell in two runs and the amendment, alone
    in its run, took every speech the bill had: Rep. Peternel was on both
    sides of it, and Reps. Noble and Hall, who spoke on the report (168-184),
    were on it. House Journal 11 ties Balboni and Peternel to 182-172,
    Peternel to 169-184 and Noble and Hall to 168-184 (journal_days). HB
    1550's passage of 5 March 2014 is drawn with the ballots' 88-199; the
    journal prints the clerk's 88-200, and the speeches before it are tied
    by that. Rows and roll calls as the record holds them."""
    import html as _html
    narr = {
        "2025-2026": {
            "SB101": [
                {'type': 'amendment', 'date': '2026-04-23', 'body': 'H', 'raw': 'Amendment # 2026-1451h (NT): AA RC 182-172 04/23/2026', 'motion': 'AA', 'vote_kind': 'RC', 'cite': 'HJ 11', 'cite_page': '37', 'amendment': '2026-1451h', 'amend_kind': 'Amendment'},
                {'type': 'amendment', 'date': '2026-04-23', 'body': 'H', 'raw': 'Amendment # 2026-1455h: AF RC 169-184 04/23/2026', 'motion': 'AF', 'vote_kind': 'RC', 'cite': 'HJ 11', 'cite_page': '42', 'amendment': '2026-1455h', 'amend_kind': 'Amendment'},
                {'type': 'floor', 'date': '2026-04-23', 'body': 'H', 'raw': 'Ought to Pass with Amendment 2026-1451h: MF RC 168-184 04/23/2026', 'action': 'Ought to Pass with Amendment 2026-1451h', 'motion': 'MF', 'vote_kind': 'RC', 'yeas': '168', 'nays': '184', 'cite': 'HJ 11', 'cite_page': '45'}],
            "SB586": [{'type': 'floor', 'date': '2026-04-23', 'body': 'H', 'raw': 'Ought to Pass with Amendment 2026-1500h: MA DV 195-160 04/23/2026', 'action': 'Ought to Pass with Amendment 2026-1500h', 'motion': 'MA', 'vote_kind': 'DV', 'yeas': '195', 'nays': '160', 'cite': 'HJ 11', 'cite_page': '37'}]},
        "2013-2014": {"HB1550": [
            {'type': 'floor', 'date': '2014-03-05', 'body': 'H', 'raw': 'Ought to Pass: MF RC 88-200', 'action': 'Ought to Pass', 'motion': 'MF', 'vote_kind': 'RC', 'yeas': '88', 'nays': '200'},
            {'type': 'floor', 'date': '2014-03-05', 'body': 'H', 'raw': 'Refer to Interim Study: MA VV', 'action': 'Refer to Interim Study', 'motion': 'MA', 'vote_kind': 'VV'}]}}
    rolls = {
        "2025-2026": {"SB101": [_rc('2026', 'H', 241, '2026-04-23', 'SB101', 'Adopt Amendment', 182, 172, True),
                                _rc('2026', 'H', 242, '2026-04-23', 'SB101', 'Adopt Amendment', 169, 184, False),
                                _rc('2026', 'H', 243, '2026-04-23', 'SB101', 'Ought to Pass with Amendment', 168, 184, False)]},
        "2013-2014": {"HB1550": [_rc('2014', 'H', 99, '2014-03-05', 'HB1550', 'Ought to Pass', 88, 199, False)]}}
    days = _sitting_fixture(SD, narr, rolls)

    def spoke(html, action):
        # The record's words are the block's data-motion since 10 October
        # 2026, where the head says the approved words.
        part = html.split(f'data-motion="{action}"', 1)[1].split('<div class="dvote"', 1)[0]
        return {side: set(re.findall(r"Rep\. (\w+)", m.group(1)))
                for side, m in (("for", re.search(r"Spoke for the motion, urging a yes "
                                                  r"vote</span>(.*?)</p>", part)),
                                ("against", re.search(r"Spoke against the motion, urging a no "
                                                      r"vote</span>(.*?)</p>", part)))
                if m}

    said = {"attributions": [
        {'bill': 'SB101-FN', 'side': 'against', 'names': ['Balboni'], 'tally': (182, 172), 'inline_motion': None, 'moved_since': []},
        {'bill': 'SB101-FN', 'side': 'for', 'names': ['Peternel'], 'tally': (182, 172), 'inline_motion': None, 'moved_since': []},
        {'bill': 'SB101-FN', 'side': 'against', 'names': ['Peternel'], 'tally': (169, 184), 'inline_motion': None, 'moved_since': []},
        {'bill': 'SB101-FN', 'side': 'for', 'names': ['Noble'], 'tally': (168, 184), 'inline_motion': None, 'moved_since': []},
        {'bill': 'SB101-FN', 'side': 'against', 'names': ['Hall'], 'tally': (168, 184), 'inline_motion': None, 'moved_since': []}]}
    html, _ = BSP.render(days[("H", "2026-04-23")], said, {}, {}, BSP.Members(Path("no-such-site")), _html.escape)
    assert spoke(html, "Adopt Amendment 2026-1451h") == {"for": {"Peternel"}, "against": {"Balboni"}} and \
        spoke(html, "Adopt Amendment 2026-1455h") == {"against": {"Peternel"}} and \
        spoke(html, "Ought to Pass with Amendment 2026-1451h") == {"for": {"Noble"}, "against": {"Hall"}}, (
        re.sub(r"<[^>]+>", " ", html)[:900])
    said = {"attributions": [
        {'bill': 'HB1550', 'side': 'against', 'names': ['Hirsch', 'Kurk'], 'tally': (88, 200), 'inline_motion': None, 'moved_since': []},
        {'bill': 'HB1550', 'side': 'for', 'names': ['Warden', 'Warden'], 'tally': (88, 200), 'inline_motion': None, 'moved_since': []}]}
    html, _ = BSP.render(days[("H", "2014-03-05")], said, {}, {}, BSP.Members(Path("no-such-site")), _html.escape)
    assert spoke(html, "Ought to Pass") == {"for": {"Warden"}, "against": {"Hirsch", "Kurk"}} and \
        html.count("Rep. Warden") == 1, re.sub(r"<[^>]+>", " ", html)[:600]
    # Two motions of one count tie a speech to neither; one member on both
    # sides of the one motion of a day is named as having spoken, no more.
    one = days[("H", "2014-03-05")].items[:1]
    both = [{'bill': 'HB1550', 'side': s, 'names': ['Daniels'], 'tally': None, 'inline_motion': None,
             'moved_since': []} for s in ("for", "against")]
    assert BSP.speakers_for(both, "HB1550", one[0], sole=True)[0] == {"for": [], "against": []} and \
        BSP.unplaced(both, "HB1550", one) == ["Daniels"]
    twin = [{'bill': 'HB1550', 'side': 'for', 'names': ['Weyler'], 'tally': (88, 199),
             'inline_motion': None, 'moved_since': []}]
    a = days[("H", "2014-03-05")].items[0]
    amb = BSP.ambiguous_tallies([a, SD.Item("HB1550", "2013-2014", {"vote_kind": "RC", "yeas": "88", "nays": "199"}, 0)])
    assert (88, 199) in amb and BSP.speakers_for(twin, "HB1550", a, ambiguous=amb)[0]["for"] == []
    return "ok", ("SB 101's speeches go to the motions the journal ties them to, HB 1550's by "
                  "the clerk's count, a name is said once, and neither two motions of one count "
                  "nor one member on both sides takes a side")


@check("session", "a roll call the file files under no bill, or that only the file "
       "records, says no more than the record does", needs=("session_days", "build_session_pages"))
def _session_rollcall_says_no_more(SD, BSP):
    """The Senate's suspension for HB 1354 of 27 June 2012, 16-7, is filed
    under RULE: its ballots are on no bill's page, so the page does not send
    a reader to HB 1354's for them. A roll call no docket row states is drawn
    with no speaker. SB 138's passage of 1 April 2021, 24-0, was voted on
    alone, off the consent calendar, though the calendar's own roll call
    was 23-1 that day. HB 1406's veto of 27 June 2000 needed two thirds of
    the 342 voting on the ballots, 228, not of the docket's 345. And the
    House's roll calls of 24 February 2021, dated the 26th in the file, take
    a vote on no bill of the 26th with them to the 24th, where its
    neighbours by number are drawn. Rows and roll calls as the record holds
    them."""
    import html as _html
    susp = ('Sen. Bradley Moved that Senate Rule 8-1(h) be suspended in order to allow the Senate to act on '
            'HB 1354 after the Senate deadline. 2/3 necessary, RC 16Y-7N, MA')
    narr = {
        "2011-2012": {"HB1354": [
            {'type': 'floor', 'date': '2012-06-27', 'body': 'S', 'raw': susp, 'action': 'that Senate Rule 8-1(h) be suspended in order to allow the Senate to act on HB 1354 after the Senate deadline. 2/3 necessary', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '16', 'nays': '7'},
            {'type': 'floor', 'date': '2012-06-27', 'body': 'S', 'raw': 'Inexpedient to Legislate, RC 7Y-16N, MF', 'action': 'Inexpedient to Legislate', 'motion': 'MF', 'vote_kind': 'RC', 'yeas': '7', 'nays': '16'}]},
        "2021-2022": {
            "SB138": [{'type': 'report', 'date': '2021-04-01', 'body': 'S', 'raw': 'Committee Report: Ought to Pass with Amendment #2021-0979s , 04/01/2021; Vote 5-0; CC', 'yeas': '5', 'nays': '0', 'cite': 'SC 17', 'amendment': '2021-0979s'},
                      {'type': 'floor', 'date': '2021-04-01', 'body': 'S', 'raw': 'Ought to Pass with Amendment 2021-0979s, RC 24Y-0N, MA; OT3rdg; 04/01/2021', 'action': 'Ought to Pass with Amendment 2021-0979s, RC 24Y-0N', 'motion': 'MA', 'cite': 'SJ 10'}],
            "HB63": [{'type': 'floor', 'date': '2021-02-24', 'body': 'H', 'raw': 'Lay on Table (Rep. Conley): MF RC 156-196 02/24/2021', 'action': 'Lay on Table', 'motion': 'MF', 'vote_kind': 'RC', 'yeas': '156', 'nays': '196', 'mover': 'Rep. Conley', 'cite': 'HJ 3', 'cite_page': '23'},
                     {'type': 'floor', 'date': '2021-02-24', 'body': 'H', 'raw': 'Ought to Pass with Amendment : MA RC 188-169 02/24/2021', 'action': 'Ought to Pass with Amendment', 'motion': 'MA', 'vote_kind': 'RC', 'yeas': '188', 'nays': '169', 'cite': 'HJ 3', 'cite_page': '23'}]},
        "1999-2000": {"HB1406": [{'type': 'veto_override', 'date': '2000-06-27', 'body': 'H', 'raw': "Governor's Veto Sustained RC(19-326); HJ50, p1576-1579", 'cite': 'HJ 50'}]}}
    rolls = {
        "2011-2012": {"HB1354": [_rc('2012', 'S', 120, '2012-06-27', 'HB1354', 'Inexpedient to Legislate', 7, 16, False)],
                      "_procedural": [_rc('2012', 'S', 119, '2012-06-27', 'RULE', 'Suspension of Senate Rules', 16, 7, True, 16)]},
        "2021-2022": {"SB138": [_rc('2021', 'S', 278, '2021-04-01', 'SB138', 'Ought to Pass with Amendment', 24, 0, True)],
                      "HB63": [_rc('2021', 'H', 14, '2021-02-26', 'HB63', 'Lay on Table', 156, 196, False),
                               _rc('2021', 'H', 15, '2021-02-26', 'HB63', 'Ought to Pass with Amendment', 188, 169, True)],
                      "_procedural": [_rc('2021', 'S', 237, '2021-04-01', None, 'Consent Calendar', 23, 1, True),
                                      _rc('2021', 'H', 22, '2021-02-26', None, 'Amend Rule 36 (Prout)', 147, 208, False)]},
        "1999-2000": {"HB1406": [_rc('2000', 'H', 121, '2000-06-27', 'HB1406', "OVERRIDE GOVERNOR'S VETO", 19, 323, False, 228)]}}
    days = _sitting_fixture(SD, narr, rolls)
    jun = days[("S", "2012-06-27")]
    # Since 10 October 2026 a roll call on a bill draws the bill's Votes
    # tab's own display, its ballots by party (data-card), where a line sent
    # the reader to the bill's page for them: the suspension, filed under no
    # bill, draws its count and no ballots, with HB 1354's own card known.
    html, _ = BSP.render(jun, {}, {}, {("2011-2012", "HB1354"): "2012"},
                         BSP.Members(Path("no-such-site")), _html.escape,
                         ctx={"cards": {"2011-2012": {"HB1354": {"2012-S-120": 0}}}})
    tied = re.findall(r'data-bill="2012/HB1354" data-card="(\d+)"', html)
    assert tied == ["0"] and \
        html.index('data-card="0"') > html.index("Inexpedient to Legislate"), (
        re.sub(r"<[^>]+>", " ", html)[:700])
    sb = [i for i in days[("S", "2021-04-01")].items if i.bill == "SB138"][0]
    assert not sb.consent and SD.rollcall_key(sb.rc)[2] == 278, (sb.consent, sb.rc)
    veto = days[("H", "2000-06-27")].items[0]
    assert (veto.yeas, veto.nays, veto.need) == (19, 323, 228), (veto.yeas, veto.need)
    feb = days[("H", "2021-02-24")]
    assert [SD.rollcall_key(i.rc)[2] for i in feb.others] == [22] and ("H", "2021-02-26") not in days, (
        feb.others, sorted(days))
    alone = SD.Item("HB63", "2021-2022", {"action": "Print Remarks", "vote_kind": "RC"}, 0)
    alone.added, alone.yeas, alone.nays, alone.rc = "rollcall", 154, 185, {"bill": "HB63"}
    day = SD.Day("H", "2021-02-24", [alone])
    found = {"attributions": [{'bill': 'HB63', 'side': 'for', 'names': ['Prout'], 'tally': (154, 185),
                               'inline_motion': None, 'moved_since': []}]}
    html, _ = BSP.render(day, found, {}, {}, BSP.Members(Path("no-such-site")), _html.escape)
    assert "The docket has no line for this vote" in html and "Spoke for" not in html, html[:500]
    return "ok", ("HB 1354's suspension sends no one to HB 1354's page for its ballots, a "
                  "file-only vote names no speaker, SB 138's vote is its own, HB 1406's bar is "
                  "the ballots', and the misdated rules vote of 2021 goes with its neighbours")


@check("session", "business done in recess is on its sitting, a joint rule's "
       "weekend is no sitting, and neither leaves a link behind",
       needs=("session_days", "build_session_pages"))
def _session_recess_and_rule_days(SD, BSP):
    """Thirteen sitting pages were for days the chamber did not sit.

    Ten were business done in the recess of an earlier sitting, which the
    docket enters on the day it was done and the journal prints with the
    sitting: "The House, Wednesday 12 June 2013" held sixteen refusals of
    Senate amendments that House Journal 49 of 5 June prints at pages 1650 to
    1653. Three were bills dying under a joint rule on a weekend deadline:
    "The House, Sunday 1 July 1990". The person decided on 24 September 2026
    that recess business goes on its sitting and a joint rule's date is no
    sitting; the bill histories are not touched.

    The rows are real docket wording, each form once, and the cases that must
    NOT move are real rows with one thing changed: a recess naming a day the
    chamber has no sitting on, one citing another journal than the sitting's,
    a recess the same day, and a joint-rule death on a weekday. Then the pages
    are built, over pages a
    previous build left, and nothing -- a page, a sitemap entry, a previous
    or next link -- may still point at a day that is gone.
    """
    def floor(date, body, raw, action, cite="", mover=""):
        return {"date": date, "body": body, "type": "floor", "raw": raw,
                "action": action, "motion": "MA", "vote_kind": "VV",
                "cite": cite, "mover": mover}
    nc = "House Non-Concurs with Senate AM #1947s and Requests C of C"
    acc = "Accede to House Request for C of C"
    ipjr = "Indefinitely Postpone"
    narr = {
        "2013-2014": {
            "HB528": {"events": [floor("2013-06-05", "H", "House Concurs with Senate "
                                       "AM #1486s (Rep J.MacKay): MA VV; HJ49, PG.1563",
                                       "House Concurs with Senate AM", "HJ 49")]},
            "HB224": {"events": [floor("2013-06-12", "H", nc + " (Rep. Shurtleff): MA "
                                       "VV [Recess of 6/5/13]; HJ49, PG.1650", nc,
                                       "HJ 49", "Rep. Shurtleff")]},
            # another journal than the sitting's: stays where it is entered
            "HB225": {"events": [floor("2013-06-13", "H", nc + " (Rep. Shurtleff): MA "
                                       "VV [Recess of 6/5/13]; HJ50, PG.1700", nc,
                                       "HJ 50", "Rep. Shurtleff")]},
            "HB650": {"events": [floor("2014-05-15", "H", "Concur with Senate Amendment "
                                       "#1339s (Rep. Bouchard) MA VV",
                                       "Concur with Senate Amendment")]},
            "HB498": {"events": [floor("2014-05-21", "H", "Rep. Chandler moved to "
                                       "Non-Concur with Senate AM and request C of C; "
                                       "MA VV (In recess of 5/15/14)", nc)]},
            # a recess of a day with no sitting: stays
            "HB499": {"events": [floor("2014-06-20", "H", "Rep. Chandler moved to "
                                       "Non-Concur with Senate AM and request C of C; "
                                       "MA VV (In recess of 6/18/14)", nc)]}},
        "2003-2004": {
            "HB369": {"events": [floor("2004-05-06", "S", "Ought to Pass as Amended"
                                       "{1544},(New Title), MA, VV; OT3rdg",
                                       "Ought to Pass as Amended", "SJ 15"),
                                 floor("2004-05-13", "S", "Senator Peterson " + acc +
                                       ", MA, VV [05/06/04]", acc, "SJ 15")]}},
        "2005-2006": {
            "HB114": {"events": [floor("2005-06-09", "S", "Sen. Kenney " + acc + ", MA, "
                                       "VV", acc, "SJ 21")]},
            # the clerk's slipped year, beside nine rows reading [06/09/05]
            "HB433": {"events": [floor("2005-06-16", "S", "Senator Morse " + acc +
                                       ", MA, VV, [06/09/04]", acc, "SJ 21")]}},
        "2025-2026": {
            "SB14": {"events": [floor("2025-06-05", "S", "Sen. Gannon Moved Nonconcur "
                                      "with the House Amendment; Requests C of C, MA, "
                                      "VV; (In Recess 06/05/2025)", "Nonconcur")]}},
        "1989-1990": {
            "HB381": {"events": [floor("1990-07-01", "H", "INDEFINITELY POSTPONED BY "
                                       "JOINT RULE 24(B)", ipjr)]},
            "HB575": {"events": [floor("1990-07-01", "H", "INDEFINITELY POSTPONED PER "
                                       "JT. RULE 24 (B)", ipjr)]},
            "HB1": {"events": [floor("1990-06-28", "H", "Ought to Pass: MA VV",
                                     "Ought to Pass")]}},
        "1995-1996": {
            "HB222": {"events": [floor("1995-07-01", "H", "INDEFINITELY POSTPONED PER JT "
                                       "RULE 23-A; HJ81,P2122", ipjr, "HJ 81")]},
            # a weekday deadline is a day the chamber may have sat: kept
            "HB1504": {"events": [floor("1996-06-13", "H", "INDEFINITELY POSTPONED PER "
                                        "JT RULE 23-A", ipjr)]}},
    }
    root = Path(tempfile.mkdtemp())
    try:
        (root / "narratives.json").write_text(json.dumps(narr), encoding="utf-8")
        days = SD.load(root / "narratives.json", journals={})

        def bills(body, date):
            d = days.get((body, date))
            return sorted(i.bill for i in d.items) if d else None
        want = {("H", "2013-06-05"): ["HB224", "HB528"],
                ("H", "2013-06-12"): None, ("H", "2013-06-13"): ["HB225"],
                ("H", "2014-05-15"): ["HB498", "HB650"], ("H", "2014-05-21"): None,
                ("H", "2014-06-20"): ["HB499"],
                ("S", "2004-05-06"): ["HB369", "HB369"], ("S", "2004-05-13"): None,
                ("S", "2005-06-09"): ["HB114", "HB433"], ("S", "2005-06-16"): None,
                ("S", "2025-06-05"): ["SB14"],
                ("H", "1990-07-01"): None, ("H", "1995-07-01"): None,
                ("H", "1990-06-28"): ["HB1"], ("H", "1996-06-13"): ["HB1504"]}
        got = {k: bills(*k) for k in want}
        assert got == want, "sittings are not as the journal holds them: " + "; ".join(
            f"{k[0]} {k[1]} has {got[k]}, want {want[k]}" for k in want if got[k] != want[k])
        entered = {i.bill: getattr(i, "entered", None)
                   for d in days.values() for i in d.items}
        assert entered["HB224"] == "2013-06-12" and entered["HB433"] == "2005-06-16" \
            and entered["HB528"] is None and entered["SB14"] is None \
            and entered["HB225"] is None, (
            f"a moved row lost the day the docket enters it, or an unmoved one "
            f"claims to have moved: {entered}")
        assert not SD.JOINT_RULE.search("SEN CONCURS WITH HOUSE AM TO JT RULES"), (
            "the Senate adopting joint rules was read as a bill dying under one")

        here = Path(".").resolve()
        if not (here / "src/pages/bills.html").exists():
            return "ok", "sittings as the journal holds them; no bills.html to build pages"
        site = root / "site"
        (root / "src" / "pages").mkdir(parents=True, exist_ok=True)
        shutil.copy2(here / "src/pages/bills.html", root / "src/pages/bills.html")
        base = "https://graniterecord.org"
        gone = ["2013-06-12", "2014-05-21", "1990-07-01", "1995-07-01"]
        (site / "session" / "H").mkdir(parents=True)
        for d in gone:
            (site / "session" / "H" / f"{d}.html").write_text("old", encoding="utf-8")
        (site / "sitemap.xml").write_text(
            '<?xml version="1.0"?><urlset>\n' + "".join(
                f"<url><loc>{base}/session/H/{d}.html</loc></url>\n" for d in gone)
            + "</urlset>", encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_session_pages.py"), "--site", "site",
                  "--base", base, "--body", "H"],
                 cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, "build_session_pages: " + (r.stderr or r.stdout)[-300:]
        pages = {p.stem: p.read_text(encoding="utf-8")
                 for p in (site / "session" / "H").glob("*.html")}
        left = sorted(set(gone) & set(pages))
        assert not left, f"a page for a day that is no sitting is still on disk: {left}"
        sm = (site / "sitemap.xml").read_text(encoding="utf-8")
        dangling = [f"{d} from {k}" for k, html in pages.items() for d in gone
                    if f"{d}.html" in html] + [f"{d} from sitemap.xml" for d in gone
                                               if d in sm]
        assert not dangling, f"a link still reaches a day that is gone: {dangling}"
        page = pages.get("2013-06-05", "")
        assert "Done in the recess of this session day" in page and \
            "Wednesday, June 12, 2013" in page, (
            "the 5 June 2013 page does not say HB 224 was done in its recess and "
            "entered on 12 June, the date the bill's own history gives")
        return "ok", ("recess rows on their sitting with the docket's date beside "
                      "them, the guarded ones where they are; joint-rule weekends "
                      "are no sitting; no page, sitemap entry or neighbour link "
                      "reaches a day that went")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("session", "recess business the docket does not mark is on its sitting "
       "too, and claims no speech made at it",
       needs=("session_days", "build_session_pages", "shell"))
def _session_unmarked_recess(SD, BSP, shell):
    """Two ways the recess fix of 24 September fell short.

    Most recess business says nothing of a recess. The House's refusals of
    Senate amendments entered on 24, 28 and 29 May 2024 cite HJ 14, and House
    Journal 14 prints every one under RECESS after the House recessed on
    23 May; the three days still built as sittings the House never held.
    The rows below are real docket rows, and the ones that must stay are real
    rows with one thing changed -- a count on the day, which a recess never
    takes, or no page to say where the journal prints it. The Senate's own
    refusals of 21 May 2008 cite SJ 18, the 15 May journal, and are printed
    in the 21 May sitting.

    And a moved row took the day's speeches. SB 389's accession, done in the
    recess of 15 May 2014 with no debate at all, was the bill's only row that
    day, so it claimed the five speeches made on the bill's floor amendments,
    whose tallies were 219-72 and 110-177; SB 148's, beside the roll call
    O'Brien and Tucker spoke on, made a second motion and pushed them off it.
    """
    def floor(date, body, raw, cite="", page=None, kind="VV", yeas=None,
              nays=None):
        return {"date": date, "body": body, "type": "floor", "raw": raw,
                "action": raw.split(":")[0].split(",")[0], "motion": "MA",
                "vote_kind": kind, "yeas": yeas, "nays": nays, "cite": cite,
                "cite_page": page}
    nc = "House Non-Concurs with Senate Amendment 2024-{}s and Requests CofC: MA VV {}"
    otp = "Ought to Pass: MA VV"
    narr = {
        "2023-2024": {
            "HB1": {"events": [floor("2024-05-23", "H", otp, "HJ 14", 10)]},
            "HB2": {"events": [floor("2024-05-23", "H", otp, "HJ 14", 20)]},
            "HB3": {"events": [floor("2024-05-23", "H", "Ought to Pass: MA RC 200-150",
                                     "HJ 14", 173, "RC", 200, 150)]},
            # entered the next day, no page: HJ 14 prints it on page 177
            "HB1695": {"events": [floor("2024-05-24", "H", nc.format(1621, "05/24/2024"),
                                        "HJ 14")]},
            "HB1030": {"events": [floor("2024-05-24", "H", nc.format(1544, "05/24/2024"),
                                        "HJ 14", 177)]},
            # no journal cited at all, on a day of nothing else
            "HB1521": {"events": [floor("2024-05-28", "H", nc.format(1968, "05/28/2024"))]},
            "HB1069": {"events": [floor("2024-05-28", "H", nc.format(1966, "05/28/2024"),
                                        "HJ 14", 178)]},
            # a day with a count is a sitting: stays
            "HB1593": {"events": [floor("2024-05-29", "H", nc.format(2117, "05/29/2024")
                                        .replace("MA VV", "MA DV 200-100"), "HJ 14",
                                        180, "DV", 200, 100)]},
            # entered on the next sitting, which has a journal of its own
            "HB1292": {"events": [floor("2024-05-30", "H", nc.format(2179, "05/30/2024"),
                                        "HJ 14", 181)]},
            # the same, at a page inside the sitting's own: stays
            "HB468": {"events": [floor("2024-05-30", "H", nc.format(1525, "05/30/2024"),
                                       "HJ 14", 100)]},
            "HB4": {"events": [floor("2024-05-30", "H", otp, "HJ 15", 2)]},
            "HB5": {"events": [floor("2024-05-30", "H", otp, "HJ 15", 3)]},
            "HB6": {"events": [floor("2024-05-30", "H", otp, "HJ 15", 4)]}},
        "1997-1998": {
            "HB50": {"events": [floor("1997-05-28", "H", "PASSED VV; HJ70,P2010", "HJ 70")]},
            "HB51": {"events": [floor("1997-05-28", "H", "PASSED VV; HJ70,P2011", "HJ 70")]},
            "HB52": {"events": [floor("1997-05-28", "H", "PASSED VV; HJ70,P2012", "HJ 70")]},
            "HB130": {"events": [floor("1997-05-29", "H", "HOUSE NONC WITH SEN AM REQ CONF "
                                       "COMM, REP LOZEAU MA; HJ70,P2037", "HJ 70", kind="")]},
            "SB122": {"events": [floor("1997-05-29", "H", "HOUSE ACCEDED TO REQ FOR CONF "
                                       "COMM, REP LOZEAU MA; HJ70,P2038", "HJ 70", kind="")]}},
        "2007-2008": {
            "SB1": {"events": [floor("2008-05-15", "S", otp, "SJ 18")]},
            "SB2": {"events": [floor("2008-05-15", "S", otp, "SJ 18")]},
            "SB3": {"events": [floor("2008-05-15", "S", otp, "SJ 18")]},
            "SB4": {"events": [floor("2008-05-21", "S", otp, "SJ 19")]},
            "SB5": {"events": [floor("2008-05-21", "S", otp, "SJ 19")]},
            "SB32": {"events": [floor("2008-05-21", "S", "Sen. Foster Moved Nonconcur with "
                                      "House Am{2501}(NT); Requests C of C, MA, VV",
                                      "SJ 18")]}},
    }
    root = Path(tempfile.mkdtemp())
    try:
        (root / "narratives.json").write_text(json.dumps(narr), encoding="utf-8")
        days = SD.load(root / "narratives.json", journals={})

        def bills(body, date):
            d = days.get((body, date))
            return [i.bill for i in d.items] if d else None
        want = {("H", "2024-05-23"): ["HB1", "HB2", "HB3", "HB1030", "HB1695",
                                      "HB1069", "HB1521", "HB1292"],
                ("H", "2024-05-24"): None, ("H", "2024-05-28"): None,
                ("H", "2024-05-29"): ["HB1593"],
                ("H", "2024-05-30"): ["HB4", "HB5", "HB6", "HB468"],
                ("H", "1997-05-28"): ["HB130", "HB50", "HB51", "HB52", "SB122"],
                ("H", "1997-05-29"): None,
                ("S", "2008-05-15"): ["SB1", "SB2", "SB3"],
                ("S", "2008-05-21"): ["SB32", "SB4", "SB5"]}
        got = {k: bills(*k) for k in want}
        assert got == want, "sittings are not as the journal holds them: " + "; ".join(
            f"{k[0]} {k[1]} has {got[k]}, want {want[k]}" for k in want if got[k] != want[k])
        moved = {i.bill: (i.entered, i.recess) for d in days.values() for i in d.items
                 if i.entered}
        assert moved == {"HB1695": ("2024-05-24", False), "HB1030": ("2024-05-24", False),
                         "HB1521": ("2024-05-28", False), "HB1069": ("2024-05-28", False),
                         "HB1292": ("2024-05-30", False), "HB130": ("1997-05-29", False),
                         "SB122": ("1997-05-29", False)}, (
            f"a moved row lost the day the docket enters it, or claims the docket "
            f"said recess: {moved}")
        assert days[("H", "2024-05-23")].ordered, "the sitting no longer reads in order"

        # The page: what the journal gives the bill that day is the sitting's.
        Item = SD.Item
        blank = {"type": "floor", "body": "H", "motion": "MA"}

        def item(bill, seq, raw, entered=None, recess=False, **e):
            ev = dict(blank, raw=raw, action=raw.split(":")[0], **e)
            it = Item(bill, "2013-2014", ev, seq)
            it.entered, it.recess = entered, recess
            return it
        acc = "House Accedes to Senate Request for C of C: MA VV"
        s389 = item("SB389", 1, "Rep Almy moved to accede to request for C of C; MA VV "
                    "(In recess of 5/15/14)", "2014-05-22", True, vote_kind="VV")
        # SB 148's floor amendment and its report, each on a roll call of its
        # own (HJ 49 of 2013: YEAS 166 NAYS 119, then YEAS 170 NAYS 113).
        s148a = item("SB148", 1.5, "Floor Amendment #2013-2010h(NT) (Rep Butler): AA RC 166-119",
                     vote_kind="RC", yeas="166", nays="119")
        s148 = item("SB148", 2, "Ought to Pass with Amendment #1730h: MA RC 170-113",
                    vote_kind="RC", yeas="170", nays="113")
        s148r = item("SB148", 3, acc + " [Recess of 6/5/13]", "2013-06-13", True,
                     vote_kind="VV")
        s19 = item("SB19", 4, acc + " [06/05/13]", "2013-06-12", False, vote_kind="VV")
        day = SD.Day("H", "2014-05-15", [s389, s148a, s148, s148r, s19])
        # As journal_days reads them from HJ044 and HJ049: Reps. O'Brien and
        # Tucker spoke before the 166-119 on the floor amendment, and the
        # page had them on the report's 170-113, the bill's one motion it
        # then drew.
        speech = [{"bill": "SB389", "side": "for", "names": ["Burt", "Wright"],
                   "tally": (110, 177)},
                  {"bill": "SB389", "side": "against", "names": ["Beaudoin"],
                   "tally": (219, 72)},
                  {"bill": "SB148-FN", "side": "against",
                   "names": ["William O'Brien", "Tucker"], "tally": (166, 119)}]
        narrative = {"attributions": speech, "unanimous_consent": [],
                     "debates": [{"bill": "SB389", "speeches": [
                         ("Rep. Burt", "I rise in support of the amendment.")]}]}
        (root / "site").mkdir()
        html, _ = BSP.render(day, narrative, {}, {}, BSP.Members(root / "site"), shell.E)
        import html as H
        cards = {re.search(r'class="cnum"[^>]*>([^<]+)<', c).group(1):
                 H.unescape(re.sub(r"<[^>]+>", " ", c))
                 for c in html.split('<article class="card"')[1:]}
        assert not re.search(r"Burt|Wright|Beaudoin|Spoke|spoke", cards["SB 389"]), (
            "SB 389's accession, done in recess with no debate, is drawn with the "
            f"speeches on its floor amendments: {cards['SB 389'][:300]!r}")
        # The vote first, its count, then who spoke on it and which vote
        # they urged, and the clerk's words last, under the ring (the owner,
        # 24 October 2026: the speakers "below the motion" and above the
        # chart; the record's words "redundant or in the wrong place").
        assert re.search(r"166\D119\s+on a roll call\s+Spoke against the motion, urging a no "
                         r"vote\s+Rep\. William O'Brien\s*,\s*Rep\. Tucker\s+In the clerk’s words: "
                         r"Floor Amendment #2013-2010h\(NT\) \(Rep Butler\)\s+Ought to Pass",
                         cards["SB 148"]) \
            and cards["SB 148"].count("O'Brien") == 1 \
            and "Also spoke" not in cards["SB 148"], (
            "SB 148's speakers were pushed off the roll call they spoke on by the "
            f"recess row beside it, or put on another: {cards['SB 148'][:600]!r}")
        assert "Done in the recess of this session day" in cards["SB 389"] and \
            "Printed in the journal with this session day" in cards["SB 19"] and \
            "recess" not in cards["SB 19"], (
            "a row the docket says was done in recess, or one placed only by the "
            "journal it cites, is not described as the record has it")
        # By the section's heading: the day's index names the section too
        # (24 October 2026).
        tail = html.split('<h2 class="w4h">Also Printed in the Permanent Journal</h2>')
        assert len(tail) == 2 and "I rise in support" in tail[1], (
            "a debate printed on SB 389 that day is drawn under its recess row "
            "rather than among the debates on no motion of the day")
        return "ok", ("unmarked recess days and rows on their sitting, in the "
                      "journal's order, the counted day, the pageless row and the "
                      "row inside the sitting's pages where they are; a recess "
                      "row claims no speech and displaces none")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("session", "a sitting's page goes when its day does, never a term at once, "
       "and none is built ahead of today", needs=("build_session_pages",))
def _session_pages_pruned(BSP):
    """Correcting a date does not take its page down by itself.

    build_session_pages wrote a page per sitting and never removed one, so
    site/session/H/2026-09-19.html would have stayed on disk, deployed and
    linked after the row behind it was put right. It removes them now -- and,
    because a writer run on a subset destroys the rest, refuses to remove more
    than PRUNE_CEILING at once without --prune, which is what a narratives.json
    missing whole terms would ask of it. A day after the build is not built:
    the Senate enters rows up to ten days ahead of its sittings.
    """
    import datetime
    here = Path(".").resolve()
    if not (here / "src/pages/bills.html").exists():
        return "skip", "no bills.html here to build a page from"
    root = Path(tempfile.mkdtemp())
    try:
        site = root / "site"
        (site / "session" / "S").mkdir(parents=True)
        (root / "src" / "pages").mkdir(parents=True, exist_ok=True)
        shutil.copy2(here / "src/pages/bills.html", root / "src/pages/bills.html")
        ahead = (datetime.date.today() + datetime.timedelta(days=12)).isoformat()

        def floor(date):
            return {"date": date, "body": "S", "type": "floor",
                    "raw": "Ought to Pass, MA, VV", "action": "Ought to Pass",
                    "motion": "MA", "vote_kind": "VV"}
        (root / "narratives.json").write_text(json.dumps({"2025-2026": {
            "SB1": {"events": [floor("2026-02-19"), floor(ahead)]},
            "SB2": {"events": [floor("2026-03-05")]}}}), encoding="utf-8")
        base = "https://graniterecord.org"
        stale = ["2026-02-16"]
        for d in stale:
            (site / "session" / "S" / f"{d}.html").write_text("old", encoding="utf-8")
        (site / "sitemap.xml").write_text(
            '<?xml version="1.0"?><urlset>\n'
            + "".join(f"<url><loc>{base}/session/S/{d}.html</loc></url>\n"
                      for d in stale + ["2026-02-19"]) + "</urlset>", encoding="utf-8")

        def run(*extra):
            return _run([sys.executable, _paths.script("build_session_pages.py"),
                         "--site", "site", "--base", base, "--body", "S", *extra],
                        cwd=root, capture_output=True, text=True, timeout=180)
        r = run()
        assert r.returncode == 0, "build_session_pages: " + (r.stderr or r.stdout)[-300:]
        pages = sorted(p.stem for p in (site / "session" / "S").glob("*.html"))
        assert pages == ["2026-02-19", "2026-03-05"], (
            f"expected the two sittings and nothing else, got {pages}")
        sm = (site / "sitemap.xml").read_text(encoding="utf-8")
        assert "2026-02-16" not in sm, "the removed day is still in sitemap.xml"
        assert ahead not in sm and "after today not built" in r.stdout, (
            "a day after the build was published, or skipped without saying so")

        many = [f"2001-01-{n:02d}" for n in range(1, BSP.PRUNE_CEILING + 3)]
        for d in many:
            (site / "session" / "S" / f"{d}.html").write_text("old", encoding="utf-8")
        r = run()
        left = len(list((site / "session" / "S").glob("*.html")))
        assert r.returncode != 0 and "REFUSED" in (r.stderr + r.stdout) \
            and left == 2 + len(many), (
            f"{len(many)} removals at once were not refused, or a refusal "
            f"still removed pages ({left} left)")
        r = run("--prune")
        left = sorted(p.stem for p in (site / "session" / "S").glob("*.html"))
        assert r.returncode == 0 and left == ["2026-02-19", "2026-03-05"], (
            f"--prune did not remove the {len(many)} stale pages: {left[:4]}")
        return "ok", (f"a gone day's page and sitemap entry are removed; more "
                      f"than {BSP.PRUNE_CEILING} at once is refused without "
                      "--prune; a day after today is not built")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# The House's leave list of 11 March 2026 (journals/2026/HJ 07 March 11,
# 2026.txt, LEAVES OF ABSENCE) and of 7 January 2026 (HJ 01, the same block),
# with the ballots RollCallHistory.txt holds for two of the members that day.
LEAVE_2026_03_11 = [
    (["Buco", "Cambrils", "Tom Dolan", "Ford", "Grote", "Gruber", "Molly Howard",
      "Love", "Geoffrey Smith", "Sofikitis", "Swanson", "Varney"], "illness"),
    (["Balboni", "Bennett", "DeDe-Poulin", "Girard", "Hicks", "Janigian", "Lovett",
      "Lundgren", "Tim Mannion", "Markell", "Notter", "Plamondon", "Jonathan Smith",
      "St. Clair", "Warden"], "important business"),
    (["Cornell"], "illness in the family"),
]
# Rep. Cornell, member 841, 11 March 2026: Excused on H-133 to H-172, then a
# Yea or Nay on every roll call from H-173 to H-188.
BALLOTS_CORNELL = {**{n: "Not Voting/Excused" for n in range(133, 173)},
                   **{n: ("Yea" if n in (173, 174, 179, 180, 182, 185, 186, 188)
                          else "Nay") for n in range(173, 189)}}
# Rep. William Dolan, member 10784, on leave for 7 January 2026 ("the day,
# important business") and recorded Not Voting/Not Excused on all 31 roll
# calls that day.
BALLOTS_W_DOLAN = {n: "Not Voting/Not Excused" for n in range(1, 32)}


@check("session", "an excused or absent member's line says what the record says, "
       "and never why", needs=("build_session_pages", "shell"))
def _vote_category_text(BSP, shell):
    """Every full roll call told readers an Excused member was "excused in
    advance for the whole day -- illness, a death in the family, or other
    significant obligation".

    The ballots say otherwise: on 42% of House member-days with an Excused
    ballot, 1999-2026, the member voted on another question that day, and a
    declared conflict of interest is coded Excused too. Presiding said "one
    member presides ... and does not vote except to break a tie" over roll
    calls that record two; Not Excused said the member "left the chamber
    rather than vote". The sitting pages said everyone on the journal's leave
    list "were not in the chamber" -- and Rep. Cornell, on leave for 11 March
    2026, voted on sixteen roll calls that afternoon.

    So each line is attributed to the record, bans the claims the record
    contradicts and every reason word, and the sitting note is run on the real
    leave lists with the ballots that contradict the old wording beside them.
    The labels themselves are not checked: whether "Excused absence" and
    "Absent, not excused" should be renamed is the person's decision.
    """
    src = _source("src/pages/app.js")
    m = re.search(r"const OTHER=\[(.*?)\];", src, re.S)
    assert m, "app.js no longer defines OTHER, the vote categories' text"
    strs = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
    assert len(strs) == 9 and strs[0::3] == [
        "Presiding", "Not Voting/Excused", "Not Voting/Not Excused"], (
        f"OTHER is not the three categories it was: {strs[0::3]}")
    labels, blurbs = strs[1::3], strs[2::3]
    FALSE = ("in advance", "for the whole day", "rather than vote",
             "left the chamber", "except to break a tie", "one member presides",
             "not in the chamber", "had not been excused")
    REASON = re.compile(r"\b(illness|business|death|family|weather|birth|sick)\b", re.I)
    for text in labels + blurbs:
        bad = [p for p in FALSE if p in text.lower()]
        assert not bad, f"a vote category states what the record contradicts ({bad}): {text!r}"
        assert not REASON.search(text), f"a vote category gives a reason: {text!r}"
        assert not re.search(r'[<&"]', text), (
            f"a vote category string is inserted unescaped and holds < & or \": {text!r}")
    assert all(b.startswith("Recorded as") for b in blurbs), (
        "each category's explanation must attribute itself to the record: "
        + " | ".join(b[:40] for b in blurbs))
    assert "part of a day" in blurbs[1] and "single vote" in blurbs[1], (
        "the Excused explanation no longer says an excuse can cover part of a "
        "day or a single vote")

    # The ballots are the evidence the note has to allow for.
    assert any(v in ("Yea", "Nay") for v in BALLOTS_CORNELL.values()) and \
        any(v == "Not Voting/Excused" for v in BALLOTS_CORNELL.values())
    assert set(BALLOTS_W_DOLAN.values()) == {"Not Voting/Not Excused"}
    root = Path(tempfile.mkdtemp())
    try:
        members = BSP.Members(root)
        for leave in (LEAVE_2026_03_11,
                      [(["Aylward", "Bordes", "Cahill", "William Dolan"], "important business")]):
            narr = {"absences": [{"names": names, "when": "the day", "why": why}
                                 for names, why in leave]}
            html = BSP.absences_html(narr, "H", members, shell.E)
            names = [n for g, _ in leave for n in g]
            text = re.sub(r"<[^>]+>", " ", html)
            missing = [n for n in names if n not in text]
            assert not missing, f"the leave list lost {missing}"
            assert f"records {len(names)} member" in text, (
                f"the note's count is not the {len(names)} names it lists")
            assert not REASON.search(text), (
                "a sitting page gives the reason a member was away: "
                + REASON.search(text).group(0))
            assert "not in the chamber" not in text and \
                "may still have voted" in text and "does not always agree" in text, (
                "the leave note says members on leave were absent, which Rep. "
                "Cornell's ballots of 11 March 2026 contradict, or hides that the "
                "roll call and the journal disagree, as on William Dolan's of "
                "7 January 2026")
        return "ok", ("the three categories are attributed to the record, with "
                      "no contradicted claim and no reason; the leave note names "
                      "members only and allows for the ballots that vote or "
                      "disagree")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# Senate sittings as the Senate Journal prints them, cut down to the lines that
# matter: journals_senate/2026/SJ 09 April 16, 2026.txt (the day's excused
# senator, the roll call's own excused line, and one excused partway through);
# 2003/SJ 9.txt (the date on the line the sitting opens with); 2012/SJ 15 May
# 23, 2012.txt ("and" after the last comma, and the list again before a roll
# call); 2024/SJ 08 April 5 2024.txt ("for the moment"); 2024/SJ 09 April 11
# 2024.txt (a reason given); 2018/SJ005.txt (excused "for the day", after the
# consent calendar); 2006/SJ 4.txt (a JOURNAL line misprinting the date, which
# the masthead and running head correct), below a floor amendment's heading
# in the shape 2018/SJ005.txt prints one, whose own date line is the trap.
SENATE_JOURNALS = {
    "2026/SJ 09 April 16, 2026.txt": (
        "SENATE                                                       April 16, 2026\n"
        "JOURNAL 9\n\n"
        "The Senate reconvened at 9:00 a.m., a quorum being present.\n\n"
        "The Reverend Mark Warren, Chaplain to the Senate, offered the following prayer:\n\n"
        "Senator Watters led the Pledge of Allegiance.\n\n"
        "Senator McConkey is excused.\n\n"
        "                                         INTRODUCTION OF PAGES\n"
        "(The Chair recognized Senator Pearl.)\n\n"
        "HB 1215, relative to supporting the preferred method of communication of an "
        "individual with a\ncommunication disability.\n\n"
        "The following Senators voted Yes: Rochefort, Lang, Gray, Innis, Ward.\n\n"
        "The following Senators were excused: McConkey.\n\n"
        "Roll Call, Yeas: 15 - Nays: 8. Adopted, bill ordered to Third Reading.\n\n"
        "Senator Watters is excused.\n"),
    "2003/SJ 9.txt": (
        "SENATE\nJOURNAL 9\n\n"
        "The Senate met at 10:00 a.m.                                "
        "              March 20, 2003\n\n"
        "A quorum was present.\n\n"
        "Senator Roberge led the Pledge of Allegiance.\n\n"
        "Senator Prescott is excused for the day.\n\n"
        "                                     INTRODUCTION OF GUESTS\n"),
    "2012/SJ 15 May 23, 2012.txt": (
        "SENATE                                                  May 23, 2012\n"
        "JOURNAL 15\n\n"
        "The Senate reconvened at 11 a.m., a quorum being present.\n\n"
        "Sen. Boutin led the Pledge of Allegiance.\n\n"
        "Sens. Forrester, Luther, Larsen, and Merrill are excused.\n"
        "597  SENATE JOURNAL 23 MAY 2012\n\n"
        "SB 372-FN-L, establishing an education tax credit.\n"
        "Sen. Forsythe moves concurrence.\n"
        "A roll call was requested by Sen. Houde, seconded by Sen. D'Allesandro.\n"
        "Sens. Forrester, Luther, Larsen, and Merrill are excused.\n"),
    "2024/SJ 08 April 5 2024.txt": (
        "SENATE                                                        April 5, 2024\n"
        "JOURNAL 8\n\n"
        "The Senate reconvened at 10:00 a.m., a quorum being present.\n\n"
        "Senator Gendreau led the Pledge of Allegiance.\n\n"
        "Senator Ricciardi is excused for the moment.\n\n"
        "                                          MOTION OF RECONSIDERATION\n"),
    "2024/SJ 09 April 11 2024.txt": (
        "SENATE                                                        April 11, 2024\n"
        "JOURNAL 9\n\n"
        "The Senate reconvened at 10:00 a.m., a quorum being present.\n\n"
        "Senator Lang led the Pledge of Allegiance.\n\n"
        "                                           INTRODUCTION OF GUESTS\n"
        "I don't know if he's still there. And Ken Chamberlain.\n\n"
        "Senator D'Allesandro is excused due to medical necessity.\n\n"
        "                                             CONSENT CALENDAR\n"),
    "2018/SJ005.txt": (
        "                              February 22, 2018\n\n"
        "The Senate reconvened at 10:00 a.m., a quorum being present.\n\n"
        "Senator Hennessey led the Pledge of Allegiance.\n\n"
        "                             INTRODUCTION OF GUESTS\n\n"
        "SB 524-FN, relative to head injury policies for the community college\n"
        "system of New Hampshire and the university system of New Hampshire.\n\n"
        "The question is on the adoption of the Consent Calendar. Adopted.\n\n"
        "Senators Carson and D'Allesandro are excused for the day.\n\n"
        "                                  REGULAR CALENDAR\n"),
    # Its JOURNAL line is misprinted: the sitting is 9 February, as the
    # masthead and the running head say, and not the 2nd it is headed.
    "2006/SJ 4.txt": (
        "                                                   February 9, 2006\n"
        "                                                   Nos. 3 - 4\n\n"
        "        SENATE JOURNAL\n\n"
        " ADJOURNMENT - FEBRUARY 2, 2006 SESSION\n"
        "COMMENCEMENT - FEBRUARY 9, 2006 SESSION\n"
        "80                     SENATE JOURNAL 2 FEBRUARY 2006\n\n"
        "Sen. Hennessey, Dist 5\n"
        "January 26, 2006\n"
        "2006-0827s\n\n"
        "Adjournment.\n\n"
        "SENATE\n\n"
        "JOURNAL 4                                              February 2, 2006\n\n"
        "The Senate met at 10:00 a.m.\n\n"
        "A quorum was present.\n\n"
        "                           SENATE JOURNAL 9 FEBRUARY 2006                    81\n\n"
        "Senator Letourneau led the Pledge of Allegiance.\n\n"
        "Senator Kenney is excused for the day.\n\n"
        "                                    INTRODUCTION OF GUESTS\n"),
}
# The other way round: 2005/SJ 9.txt is headed rightly and carries 2004 in
# every running head, and its masthead agrees with the heading.
SENATE_2005_SJ9 = (
    " ADJOURNMENT - MARCH 10, 2005 SESSION\n"
    "COMMENCEMENT - MARCH 17, 2005 SESSION\n"
    "110                           SENATE JOURNAL 10 MARCH 2005\n\n"
    "Adjournment.\n\n"
    "SENATE\nJOURNAL 9\n\n"
    "                                                   March 17, 2005\n\n"
    "The Senate met at 10:00 a.m.\n\n"
    "A quorum was present.\n\n"
    "                             SENATE JOURNAL 17 MARCH 2004                 111\n\n"
    "The Reverend David P. Jones, chaplain to the Senate, offered the prayer.\n")


@check("session", "a Senate page names the senators excused for the day, and "
       "only those, and never why", needs=("journal_days", "build_session_pages", "shell"))
def _senate_excused(J, BSP, shell):
    """Senate sitting pages named nobody as excused; the House's have for a
    fortnight. The person asked on 24 September 2026 for the Senate's to
    match -- the members excused for the day, and not those excused for part
    of it, since a senator excused for the day sometimes comes back once the
    obligation is done.

    The Senate Journal has no LEAVES OF ABSENCE heading. It names the day's
    excused senators as each sitting opens, and the same sentence later in the
    day is a senator leaving partway or excused from one vote, so only the
    opening is read. The wrongs this rules out are each real: a mid-day
    excuse named as the day's, a roll call's own excused line, "for the
    moment", "and Merrill" as a name, a date taken from a floor amendment
    printed above the sitting, a heading's misprinted date believed over the
    masthead and every running head (Senator Kenney, excused on 9 February
    2006, was filed under the 2nd), and a reason printed on the page.
    """
    root = Path(tempfile.mkdtemp())
    try:
        for rel, text in SENATE_JOURNALS.items():
            f = root / "journals_senate" / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        # A day's debate printed a second time is not read again.
        (root / "journals_senate" / "2026" / "SJ 09 - Verbatim.txt").write_text(
            SENATE_JOURNALS["2026/SJ 09 April 16, 2026.txt"].replace(
                "McConkey is excused.", "Gray is excused."), encoding="utf-8")

        def names(date):
            got = J.read_senate_day(date, root / "journals_senate")
            return [n for g in got["absences"] for n in g["names"]]
        want = {"2026-04-16": ["McConkey"], "2003-03-20": ["Prescott"],
                "2012-05-23": ["Forrester", "Luther", "Larsen", "Merrill"],
                "2024-04-05": [], "2024-04-11": ["D'Allesandro"],
                "2018-02-22": [], "2006-02-09": ["Kenney"],
                "2006-02-02": [], "2006-01-26": []}
        got = {d: names(d) for d in want}
        assert got == want, (
            "the Senate's excused senators are not the opening's: " + "; ".join(
                f"{d} got {got[d]}, want {want[d]}" for d in want if got[d] != want[d]))
        dated = [d for d, _ in J.senate_openings(SENATE_2005_SJ9)]
        assert dated == ["2005-03-17"], (
            f"a running head's misprinted year redated a sitting: {dated}")

        members = BSP.Members(root)
        html = BSP.absences_html(J.read_senate_day("2024-04-11", root / "journals_senate"),
                                 "S", members, shell.E)
        text = re.sub(r"<[^>]+>", " ", html)
        assert "Allesandro" in text and "Sen. " in text and "1 senator " in text, (
            f"the Senate's excused list is not drawn as a senator: {text[:200]!r}")
        assert not re.search(r"medical|necessity|illness|business|family", text, re.I), (
            "a Senate page gives the reason a senator was excused")
        assert "may still have voted" in text and "does not always agree" in text, (
            "the Senate's excused note claims more than the ballots allow: Senator "
            "Carson, excused as the Senate opened on 7 May 2026, voted on all seven "
            "of its roll calls")
        return "ok", ("the opening's excused senators on six real sittings; no "
                      "mid-day, roll call or part-day excuse, no verbatim copy, "
                      "and no reason on the page")
    finally:
        shutil.rmtree(root, ignore_errors=True)



# THE KIT'S MISFILED HOUSE JOURNALS (wf20, 29 October 2026;
# docs/design/journals-misfiled/report.md on design/committee-videos). The
# General Court's index filed thirteen 2011 issues under its 2010 folder and
# two 1999 issues under 2000, and the fetch kept its folders: twelve are
# byte-for-byte copies of files in journals/2011/, and three are moves. The
# move is the owner's, in the bucket. Until it is made these fifteen are known,
# and the check below that holds the rest passes; the one after it holds them
# and fails as expected until the move, when it says to take its mark off.
JOURNALS_MISFILED = {
    "journals/2010/Daily Journal #1, 12-1-10, Organization Day Final.txt",
    "journals/2010/HJ006.txt", "journals/2010/HJ009.txt", "journals/2010/HJ010.txt",
    "journals/2010/HJ013.txt", "journals/2010/HJ018.txt", "journals/2010/HJ019.txt",
    "journals/2010/HJ020.txt", "journals/2010/HJ021.txt", "journals/2010/HJ022.txt",
    "journals/2010/HJ023.txt", "journals/2010/HJ024.txt", "journals/2010/HJ025.txt",
    "journals/2000/HJ025.txt", "journals/2000/HJ026.txt",
}


def _journal_folders_known(line, names):
    """Whether a problem is one the fifteen known files were measured to
    give, exactly: a numbered 2010 copy said to be the same bytes as its
    2011 file, the pair of them as duplicates, or one of the three moves with
    nothing of its name in the way. A third copy, a half-done move or a
    different file in the way is a new problem, though it names a known file."""
    if len(names) == 1 and names[0] in JOURNALS_MISFILED:
        p = names[0]
        tail = ("nothing of that name there." if "/2000/" in p or "Organization Day" in p
                else "this copy goes.")
        return line.startswith(p + ": in ") and line.endswith(tail)
    if len(names) == 2 and names[0] in JOURNALS_MISFILED and "/2010/HJ0" in names[0]:
        return names[1] == names[0].replace("/2010/", "/2011/")
    return False


def _journal_folders_found(JF):
    """(the audit, its problems other than the fifteen known files' own), or
    None where no journals are on this disk."""
    r = JF.audit(".")
    if "skip" in r:
        return None
    other = [ln for ln, names in zip(r["problems"], r["named_in"])
             if not _journal_folders_known(ln, names)]
    return r, other


@check("data", "every journal file is in its session's folder and no two are the same bytes, "
               "but the fifteen known misfiled House journals the owner is to move",
       needs=("journal_folders",))
def _journal_folders(JF):
    got = _journal_folders_found(JF)
    if got is None:
        return "skip", "no journals/ or journals_senate/ here"
    r, other = got
    assert not other, "\n".join(other)
    if not r["problems"]:
        return "ok", JF.ok_line(r)
    left = {n for names in r["named_in"] for n in names} & JOURNALS_MISFILED
    return "ok", (JF.counts(r) + f"; every file in its session's folder but {len(left)} of the "
                  "fifteen known misfiled House journals, waiting on the owner's move")


@check("data", "the fifteen known misfiled House journals are moved",
       needs=("journal_folders",),
       expect_fail="the kit's 15 misfiled House journals not yet moved (wf20): "
                   "docs/design/journals-misfiled/report.md section 6 is the owner's")
def _journal_folders_moved(JF):
    got = _journal_folders_found(JF)
    if got is None:
        return "skip", "no journals/ or journals_senate/ here"
    r, _ = got
    assert not r["problems"], "\n".join(r["problems"])
    return "ok", JF.ok_line(r)


# The fixtures for journal_folders, every one quoted from the kit's own files
# (file and lines named), leading spaces shortened. \r\n is kept where the
# file has it, and the form feed where it prints one.
_JF_ORG_2010 = (  # journals/2010/Daily Journal #1, 12-1-10, Organization Day Final.txt l.1-12
    "         HOUSE RECORD\r\n\r\n                First Year of the 162nd General Court\r\n"
    "             Calendar and Journal of the 2011 Session\r\n\r\n"
    "Vol. 33      Concord, N.H.  Wednesday, December 1, 2010  No. 5\r\n\r\n"
    "             HOUSE JOURNAL No. 1\r\n\r\n                               Wednesday, December 1, 2010\r\n"
    "\r\nOn the first Wednesday in December in the year of our Lord, two thousand ten, it being the\r\n")
_JF_HJ19_2025 = (  # journals/2025/HJ 19 December 17, 2025.txt l.18-22
    "             HOUSE JOURNAL NO. 19\n\n                             Wednesday, December 17, 2025\n\n"
    "The House assembled at 10:00 a.m. and was called to order by the Speaker.\n")
_JF_HJ022_2001 = (  # journals/2001/HJ022.txt l.1004-1006
    "         HOUSE JOURNAL No. 23\n\n                                 (Wednesday, December 12, 2001)\n")
_JF_HJ023_2003 = (  # journals/2003/HJ023.txt l.1-10 and l.75-76
    "         HOUSE RECORD\n\nFirst Year of the 158th Session of the General Court\n"
    "       Calendar and Journal of the 2003 Session\n\n"
    "Vol. 25  Concord N.H.  January 7, 2004  No. 74\n\nHOUSE JOURNAL No. 23 (cont.)\n\n"
    "                              (Thursday, September 4, 2003)\n\n"
    "The Speaker called the recessed session of September 4, 2003 to order at 10:00 a.m. on\n"
    "Wednesday, January 7, 2004 and declared a quorum present.\n")
_JF_HJ027_2000 = (  # journals/2000/HJ027.txt l.1-12 and l.737-740
    "         HOUSE RECORD\n\nFirst Year of the 156th Session of the General\n"
    "                              Court\n\n         Calendar and Journal of the 1999 Session\n\n"
    "Vol. 22  Concord N.H.  Wednesday, January 5, 2000  No. 5\n\nHOUSE JOURNAL No. 27 (cont.)\n\n"
    "                                   Wednesday, November 3, 1999\n"
    "HB 707-FN, relative to the family division of the courts.\n"
    "\f          HOUSE JOURNAL No. 1\n\n                                     Wednesday, January 5, 2000\n")
_JF_HJ001_2020 = (  # journals/2020/HJ001.txt l.9-13 and l.483-485
    "                Concord,N.H.  Wednesday,January8,2020                         No.1X\n\n"
    "      HOUSE JOURNAL NO. 23 (Cont'd)\n\n                             Wednesday, September 25, 2019\n"
    "adjourned.\n\n              HOUSE JOURNAL NO. 1\n\n                               Wednesday, January 8, 2020\n")
_JF_HJ004_2006 = (  # journals/2006/HJ004.txt l.1-10
    "HOUSE RECORD\n\n Second Year of the 159th General Court\nCalendar and Journal of the 2006 Session\n\n"
    "Vol. 27 Concord, N.H.  Wednesday, February 15, 2006  No. 19\n\nHOUSE JOURNAL No. 4 (cont.)\n\n"
    "                                 Thursday, February 2, 2006\n")
_JF_HJ004_1998 = (  # journals/1998/HJ004.txt l.1-16
    "  HOUSE RECORD\n\n Second Year of the 155th Session of the General Court\n"
    "          Calendar and Journal of the 1997 Session\n\n"
    "             Vol. 20 Concord N.H. Wednesday, February 18, 1998 No. 18\n\nHOUSE JOURNAL No. 4 (cont.)\n\n"
    "Adopted.                 Thursday, February 12, 1998\n\n"
    "                         Rep. Lozeau moved that the House adjourn.\n\n          HOUSE JOURNAL No. 5\n\n"
    "                                   Wednesday, February 18, 1998\n")
_JF_SJ01_2024 = (  # journals_senate/2025/SJ 01 December 4, 2024 Organization Day.txt l.1-21
    "                December4,2024\n                No.1\n\n           STATEOFNEWHAMPSHIRE\n\n"
    "        SENATEJOURNAL\n\nORGANIZATION DAY - DECEMBER 4, 2024 SESSION\n"
    "\f2  SENATEJOURNAL4DECEMBER2024\n\nSENATE      December 4, 2024\nJOU RNA L1\n\n"
    "                                                           ORGANIZATION DAY\n"
    "The Honorable Tammy L. Wright, Clerk of the Senate, called the Senate to order at 10:00 a.m.\n")
_JF_SJ9_2005 = (  # journals_senate/2005/SJ 9.txt l.1-17 and l.75
    "                March 17, 2005\n                Nos. 8 - 9\n\n          STATE OF NEW HAMPSHIRE\n\n"
    "       SENATE JOURNAL\n\n ADJOURNMENT - MARCH 10, 2005 SESSION\n"
    "COMMENCEMENT - MARCH 17, 2005 SESSION\n\f110                           SENATE JOURNAL 10 MARCH 2005\n\n"
    "SENATE                                                                    March 10, 2005\n"
    "JOURNAL 8 (Cont.)\n"
    "\f                             SENATE JOURNAL 17 MARCH 2004                                             111\n")
_JF_SJ001_2018 = (  # journals_senate/2018/SJ001.txt l.1-9
    "SENATEJOURNAL3JANUARY2018  1\n\nSTATE OF NEW HAMPSHIRE\n\n              CONVENING DAY\n\n"
    "                                 January 3, 2018\n\n"
    "The Senate reconvened at 10:00 a.m., a quorum being present.\n")
_JF_SJ02_2023 = (  # journals_senate/2023/SJ 02 January 4, 2023 - Convening Day.txt l.15-21
    "\f26  SENATEJOURNAL4JANUARY2023\r\n\r\nSENATE                         January 4, 2023\r\n"
    "JOU RNA L2\r\n\r\n                                                              CONVENING DAY\r\n"
    "The Senate convened at 10:00 a.m., a quorum being present.\r\n")
_JF_HB1 = (  # journals/2003/HB1_FinanceAmended.txt l.1-6
    "       House Finance\n       April 10, 2003\n       2003-1268h\n       03/10\n\n"
    "                                                             Amendment to HB 1-A\n")
_JF_HJ010_2011 = (  # journals/2011/HJ010.txt l.1-19
    "         State of New Hampshire\n\n         HOUSE RECORD\n\n"
    "            First Year of the 162nd General Court\n         Calendar and Journal of the 2011 Session\n\n"
    "Vol. 33  Concord, N. H.  Tuesday, March 15, 2011  No. 26\n\n         HOUSE JOURNAL No. 9 (cont.)\n\n"
    "                                  Wednesday, March 2, 2011\n\nRep. Silva moved that the House adjourn.\n"
    "Adopted.\n\n         HOUSE JOURNAL No. 10\n\n                                   Tuesday, March 15, 2011\n")
_JF_HJ025_2000 = (  # journals/2000/HJ025.txt l.1-8 and l.135-137
    "         HOUSE RECORD\n\nFirst Year of the 156th Session of the General\n"
    "                              Court\n\n         Calendar and Journal of the 1999 Session\n\n"
    "Vol. 21  Concord N.H.  Thursday, October 28, 1999  No. 89\n\n"
    "         HOUSE JOURNAL No. 26\n\n                                     Thursday, October 28, 1999\n")
_JF_HJ015_2010 = (  # journals/2010/HJ015.txt l.16-18
    "         HOUSE JOURNAL No. 15\n\n                                  Wednesday, April 21, 2010\n")

_JF_GOOD = {
    "journals/2011/Daily Journal #1, 12-1-10, Organization Day Final.txt": _JF_ORG_2010,
    "journals/2025/HJ 19 December 17, 2025.txt": _JF_HJ19_2025,
    "journals/2001/HJ022.txt": _JF_HJ022_2001,
    "journals/2003/HJ023.txt": _JF_HJ023_2003,
    "journals/2000/HJ027.txt": _JF_HJ027_2000,
    "journals/2020/HJ001.txt": _JF_HJ001_2020,
    "journals/2006/HJ004.txt": _JF_HJ004_2006,
    "journals/1998/HJ004.txt": _JF_HJ004_1998,
    "journals/2011/HJ010.txt": _JF_HJ010_2011,
    "journals_senate/2025/SJ 01 December 4, 2024 Organization Day.txt": _JF_SJ01_2024,
    "journals_senate/2005/SJ 9.txt": _JF_SJ9_2005,
    "journals_senate/2018/SJ001.txt": _JF_SJ001_2018,
    "journals_senate/2023/SJ 02 January 4, 2023 - Convening Day.txt": _JF_SJ02_2023,
    "journals/2003/HB1_FinanceAmended.txt": _JF_HB1,
    "journals/2003/HB1_Floor_Amendment.txt": _JF_HB1.replace("House Finance", "Floor"),
}


@check("code", "journal_folders places each journal by the sittings it prints: an Organization "
               "Day in the next year's folder, an odd-year December in its own, a heading after "
               "a form feed; it names a misfiled file, a copy, a file of two sessions and a file "
               "with no date, and fails rather than pass a tree it cannot read",
       needs=("journal_folders",))
def _journal_folders_rule(JF):
    import tempfile
    base = tempfile.TemporaryDirectory(prefix="pf_jf_")
    try:
        return _journal_folders_cases(JF, Path(base.name))
    finally:
        base.cleanup()


def _journal_folders_cases(JF, base):
    import tempfile

    def tree(files):
        d = Path(tempfile.mkdtemp(dir=base))
        for rel, text in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_bytes(text.encode("utf-8"))
        return d

    def found(files, *gone, **more):
        f = {k: v for k, v in files.items() if k not in gone}
        f.update({k.replace("__", "/"): v for k, v in more.items()})
        return JF.audit(tree(f))

    r = JF.audit(tree(_JF_GOOD))
    assert not r["problems"], "a correctly filed fixture was flagged:\n" + "\n".join(r["problems"])
    said = {ln.split(": ", 1)[0]: ln for ln in r["detail"]}
    assert "HOUSE JOURNAL No. 1 of January 5, 2000 (line 14)" in said["journals/2000/HJ027.txt"], (
        "the heading after a form feed was not read: " + said["journals/2000/HJ027.txt"])
    assert "prints no sitting of its own" in said["journals/2003/HJ023.txt"], (
        "2003/HJ023's issue line has no weekday and dated it: " + said["journals/2003/HJ023.txt"])
    assert "prints the 2001 series" in said["journals/2001/HJ022.txt"], said["journals/2001/HJ022.txt"]
    assert "prints the 2025 series" in said["journals/2025/HJ 19 December 17, 2025.txt"]
    assert "not a journal" in said["journals/2003/HB1_FinanceAmended.txt"]
    assert r["named"] == 2 and r["weak"] == 1, (r["named"], r["weak"])

    org = "Daily Journal #1, 12-1-10, Organization Day Final.txt"
    cases = [
        ("an Organization Day under its own year",
         found(_JF_GOOD, f"journals/2011/{org}", **{f"journals__2010__{org}": _JF_ORG_2010}),
         f"journals/2010/{org}: in 2010, prints the 2011 series: its own sitting HOUSE JOURNAL "
         "No. 1 of December 1, 2010 (line 8)", "Belongs in journals/2011/, nothing of that name there."),
        ("a copy of a 2011 issue under 2010",
         found(_JF_GOOD, **{"journals__2010__HJ010.txt": _JF_HJ010_2011}),
         "journals/2010/HJ010.txt: in 2010, prints the 2011 series",
         "where HJ010.txt is the same bytes: this copy goes."),
        ("the same copy, as bytes",
         found(_JF_GOOD, **{"journals__2010__HJ010.txt": _JF_HJ010_2011}),
         "the same bytes, twice: journals/2010/HJ010.txt and journals/2011/HJ010.txt", ""),
        ("a 1999 issue under 2000",
         found(_JF_GOOD, **{"journals__2000__HJ025.txt": _JF_HJ025_2000}),
         "journals/2000/HJ025.txt: in 2000, prints the 1999 series",
         "Belongs in journals/1999/, nothing of that name there."),
        ("a Senate Organization Day under its own year",
         found(_JF_GOOD, "journals_senate/2025/SJ 01 December 4, 2024 Organization Day.txt",
               **{"journals_senate__2024__SJ 01 December 4, 2024 Organization Day.txt": _JF_SJ01_2024}),
         "journals_senate/2024/SJ 01 December 4, 2024 Organization Day.txt: in 2024, prints the 2025 "
         "series", "Belongs in journals_senate/2025/, nothing of that name there."),
        ("a file with no date",
         found(_JF_GOOD, **{"journals__2004__HJ099.txt":  # journals/2011/HJ010.txt l.14
                            "Rep. Silva moved that the House adjourn.\n"}),
         "journals/2004/HJ099.txt: no date read", ""),
        ("a file of two sessions",
         found(_JF_GOOD, **{"journals__2010__HJ015.txt": _JF_HJ015_2010 + _JF_HJ010_2011}),
         "journals/2010/HJ015.txt: spans two sessions: the 2010 series by its own sitting HOUSE "
         "JOURNAL No. 15 of April 21, 2010",
         "the 2011 series by its own sitting HOUSE JOURNAL No. 10 of March 15, 2011 (line 20), "
         "its issue of March 15, 2011 (line 11)"),
        ("a named non-journal gone",
         found(_JF_GOOD, "journals/2003/HB1_Floor_Amendment.txt"),
         "journals/2003/HB1_Floor_Amendment.txt: named in NOT_JOURNALS and no longer there", ""),
    ]
    for what, got, start, end in cases:
        hit = [ln for ln in got["problems"] if ln.startswith(start) and ln.endswith(end)]
        assert hit, f"{what}: no line '{start} ... {end}' in:\n" + "\n".join(got["problems"])
        assert all(p for p in got["named_in"][got["problems"].index(hit[0])]), what
    # The data check excuses the fifteen known files' own lines and nothing
    # more: not a third copy of one, nor a move half done.
    def unexcused(files):
        got = JF.audit(tree(files))
        return [ln for ln, names in zip(got["problems"], got["named_in"])
                if not _journal_folders_known(ln, names)]
    known = dict(_JF_GOOD, **{"journals/2010/HJ010.txt": _JF_HJ010_2011})
    assert unexcused(known) == [], unexcused(known)
    third = unexcused(dict(known, **{"journals/2011/HJ 10 March 15, 2011.txt": _JF_HJ010_2011}))
    assert third and all("same bytes" in ln for ln in third), third
    half = unexcused(dict(_JF_GOOD, **{f"journals/2010/{org}": _JF_ORG_2010}))
    assert len(half) == 2 and half[0].endswith("is the same bytes: this copy goes.") \
        and half[1].startswith("the same bytes, twice:"), half
    # Nothing dated by its own sittings: the floor, rather than a pass.
    weak_only = {f"journals/{y}/HJ00{i}.txt": "         Calendar and Journal of the %s Session\n" % y
                 for i, y in enumerate(("2003", "2004", "2005"), 1)}
    weak_only["journals_senate/2018/SJ001.txt"] = "SENATEJOURNAL3JANUARY2018  1\n"
    got = JF.audit(tree(weak_only))
    assert any("under the 90% floor" in ln for ln in got["problems"]), got["problems"]
    assert not any("no date read" in ln for ln in got["problems"]), got["problems"]
    # A chamber with no files at all, and a tree with neither.
    got = JF.audit(tree({k: v for k, v in _JF_GOOD.items() if k.startswith("journals/")}))
    assert any(ln.startswith("journals_senate/: no Senate journal files") for ln in got["problems"])
    assert JF.audit(tree({})) == {"skip": "no journals/ or journals_senate/ here"}
    return "ok", (f"{len(_JF_GOOD) - 2} journals filed rightly pass, two named texts pass, and "
                  f"{len(cases) + 2} wrong trees are each named")


# ============================================ code: the House's withdrawn bills ==
#
# journal_bills.py reads the House Journal's introduction lists and its
# withdrawals, for the nine bills of 2025-2026 every current-term file of the
# General Court has dropped. The fixture is cut from the real journals: HJ 3
# of 9 January 2025 (HB 476's entry, HCR 7's name broken across a page head,
# HB 234's "Har-" / "rington"), the four "not introduced" placeholders of
# 7 January 2026, HJ 4 of 6 February 2025 (the consent calendar, its TO BE
# WITHDRAWN list, HB 476's motion and the reconsideration that failed) and
# HJ 9 of 20 March 2025 (HB 431's motion, which failed after a roll call).
#
# TWO CASES ARE INVENTED, because the record has no example of either, and
# each is marked where it stands: HB 523's removal from the consent calendar
# of 6 February 2025 (the House in fact withdrew HB 523 on that calendar; no
# bill on a 2025-2026 TO BE WITHDRAWN list was ever removed from one), and
# HCR 7's withdrawal and the reconsideration that undid it (HCR 7 was never
# moved to be withdrawn). The words are the journal's own forms.

_JB_INTRO = [
    "      State of   HOUSE RECORD",
    "",
    "              HOUSE JOURNAL NO. 3",
    "",
    "                                 Thursday, January 9, 2025",
    "",
    "                                                 RESOLUTION",
    "Rep. Doucette offered the following: RESOLVED, that in accordance with the list in the possession of the Clerk,",
    "Motion was adopted.",
    "",
    "                                                INTRODUCTION OF HOUSE BILLS",
    "",
    "                                                 First, second reading and referral",
    "",
    "HB 476-FN, relative to restrictions on elective abortion. (Peternel, Carr. 6; Aures, Merr. 13; Burnham, Straf.",
    "2; Granger, Straf. 2; M. Pearson, Rock. 34; Prudhomme-O'Brien, Rock. 13; Seidel, Hills. 29; Sellers, Graf. 18;",
    "Terry, Belk. 7; Judiciary)",
    "HB 523-FN, relative to the office of child advocate's oversight of restraint and seclusion reports. (DeSimone,",
    "Rock. 18; Children and Family Law)",
    "HCR 7, recognizing abortion as a critical component of comprehensive reproductive health care. (Simpson,",
    "Rock. 33; M. Smith, Straf. 10; Hakken-Phillips, Graf. 12; M. Murray, Hills. 37; Seibert, Hills. 21; Van-",
    "\f10  9JANUARY2025HOUSERECORD",
    "",
    "decasteele, Rock. 25; Turer, Rock. 6; Lloyd, Hills. 8; Ebel, Merr. 7; Weber, Ches. 5; Rosenwald, Dist 13;",
    "Prentiss, Dist 5; Altschiller, Dist 24; Reardon, Dist 15; Perkins Kwoka, Dist 21; Health, Human Services",
    "and Elderly Affairs)",
    "HB 1164, - not introduced.",
    "HB 1165, relative to gender designation on state-issued identification. (Perez, Rock. 16; Sellers, Graf. 10;",
    "Panek, Hills. 1; Transportation)",
    "HB 1437 - not introduced.",
    "HB 1438, requiring mental health caseworkers to report instances of animal abuse. (Lloyd, Hills. 8; Executive",
    "Departments and Administration)",
    "HB 1470 - not introduced",
    "HB 1471, relative to changes to the state retirement system. (Foote, Rock. 13; Executive Departments and",
    "Administration)",
    "HB 1545- not introduced.",
    "HB 1546-FN, repealing the business profits tax. (Ankarberg, Straf. 7; Ways and Means)",
    "HB 431, establishing a commission to review draft rules related to minimum standards for public school",
    "approval. (Notter, Hills. 12; Education Policy and Administration)",
    "HB 234-FN, relative to the statewide education property tax and excess revenue from games of chance. (Har-",
    "rington, Straf. 18; Granger, Straf. 2; Ways and Means)",
    "CACR 1, relating to the governor. Providing that there be a lieutenant governor who shall assume the duties",
    "of the governor if the governor is incapacitated. (Moffett, Merr. 4; Executive Departments and Administration)",
    "",
    "                                                                      RECESS",
    "",
]
_JB_FEB6 = [
    "              HOUSE JOURNAL NO. 4",
    "",
    "                                 Thursday, February 6, 2025",
    "",
    "                                                          CONSENT CALENDAR",
    "Rep. Osborne moved that the Consent Calendar with the relevant amendments as printed in the day's House",
    "Record be adopted.",
    # INVENTED: the journal prints no removal here, and the House withdrew HB
    # 523 on this very calendar. No bill on a 2025-2026 TO BE WITHDRAWN list
    # was ever removed from its calendar, so the case has no real example;
    # the line is in the form the journal prints a removal in.
    "HB 523-FN, relative to the office of child advocate's oversight of restraint and seclusion reports, removed",
    "by Reps. Heath Howard and Wade.",
    "Consent Calendar was adopted.",
    "",
    "                                                        MOTION TO WITHDRAW",
    "HB 476-FN, relative to restrictions on elective abortion, removed by Reps. Heath Howard, Wade, de Vries,",
    "Seibert, Wendy Thomas, Selig, Beauchemin, Sorensen, Parshall and DeRoy.",
    "",
    "The question being adoption of the motion to withdraw.",
    "Rep. Heath Howard requested a roll call; not sufficiently seconded.",
    "On a division vote, with 335 members having voted in the affirmative, and 18 in the negative, the motion to",
    "withdraw was adopted.",
    "\f2                   6FEBRUARY2025HOUSERECORD",
    "",
    "                                                       MOTION TO RECONSIDER",
    "Having voted with the prevailing side, Rep. Kuttab moved that the House reconsider its action whereby, on",
    "a Division vote of 335-18, the House adopted the motion to withdraw on HB 476-FN, relative to restrictions",
    "on elective abortion.",
    "",
    "The question being adoption of the motion to reconsider.",
    "Rep. Kuttab requested a roll call; sufficiently seconded.",
    "",
    "                                            YEAS 15 - NAYS 340",
    "",
    "                                            YEAS - 15",
    "                                            BELKNAP",
    "",
    "Comtois, Barbara    Nagel, David",
    "",
    "and the motion failed.",
    "",
    "HB 178, relative to foster parent representation of foster children with disabilities. OUGHT TO PASS.",
    "Rep. Mark Pearson for Children and Family Law. This bill does one simple thing. Vote 18-0.",
    "",
    "                                                            TO BE WITHDRAWN",
    "",
    "HB 234-FN, relative to the statewide education property tax and excess revenue from games of chance.",
    "HB 523-FN, relative to the office of child advocate's oversight of restraint and seclusion reports.",
    "",
    "                                                          REGULAR CALENDAR",
    "",
    "HB 511-FN, relative to cooperation with federal immigration authorities. OUGHT TO PASS WITH AMEND-",
    "MENT.",
]
_JB_MAR20 = [
    "              HOUSE JOURNAL NO. 9",
    "",
    "                                 Thursday, March 20, 2025",
    "",
    "                                                          CONSENT CALENDAR",
    "Rep. Osborne moved that the Consent Calendar with the relevant amendments as printed in the day's House",
    "Record be adopted.",
    "\f                      20MARCH2025HOUSERECORD                                                                 3",
    "",
    "Consent Calendar was adopted.",
    "",
    "                                                        MOTION TO WITHDRAW",
    "HB 431, establishing a commission to review draft rules related to minimum standards for public school",
    "approval, removed by Reps. Notter, Layon, Farrington, Osborne, Noble, McFarlane, Cordelli, Tom Mannion,",
    "Wherry and Litchfield.",
    "",
    "The question being adoption of the motion to withdraw.",
    "Rep. Cordelli requested a roll call; sufficiently seconded.",
    "",
    "                                           YEAS 160 - NAYS 207",
    "",
    "St. Clair, Charlie    Paige, David               YEAS - 160                             Woodcock, Stephen",
    "Burroughs, Anita                                 BELKNAP",
    "",
    "and the motion failed.                               Smith, Steven",
    "",
    # INVENTED: HCR 7 was never moved to be withdrawn. The words are the
    # journal's own forms, put to a bill so that a reconsideration that
    # CARRIED, and the motion to withdraw then put again and lost, is seen to
    # cancel the withdrawal it reconsidered.
    "                                                        MOTION TO WITHDRAW",
    "HCR 7, recognizing abortion as a critical component of comprehensive reproductive health care, removed by",
    "Reps. Wade and Selig.",
    "The question being adoption of the motion to withdraw.",
    "Motion was adopted.",
    "",
    "                                                       MOTION TO RECONSIDER",
    "Having voted with the prevailing side, Rep. Selig moved that the House reconsider its action whereby the",
    "House adopted the motion to withdraw on HCR 7.",
    "The question being adoption of the motion to reconsider.",
    "Motion was adopted.",
    "The question now being adoption of the motion to withdraw.",
    "Motion failed.",
    "",
    "                                                          REGULAR CALENDAR",
]


def _jb_tree(root):
    """The fixture's journals/ under `root`: three files of 2025."""
    d = root / "journals" / "2025"
    d.mkdir(parents=True)
    for name, lines in (("HJ 03 January 9, 2025.txt", _JB_INTRO),
                        ("HJ 04 February 6, 2025.txt", _JB_FEB6),
                        ("HJ 09 March 20, 2025.txt", _JB_MAR20)):
        (d / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root / "journals"


@check("build", "the House Journal's introductions are read, traps and all",
       needs=("journal_bills",))
def _journal_intros(J):
    """journal_bills.py reads each entry of a list of bills introduced: the
    designation as printed, the title, every sponsor in order and the
    committee. The traps are the journals' own. A "not introduced" placeholder
    in each of its four spellings gives nothing, and three of them have no
    comma, so a splitter that waits for one glues them to the entry before
    and loses the entry after. HCR 7's "Van-" ends a page and "decasteele"
    begins the next, below its running head; HB 234's "Har-" ends a line. A
    page head with no space between the day and the month is page 39, not 1.
    """
    import contextlib
    import io
    root = Path(tempfile.mkdtemp())
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            intros, records, report, problems = J.read_all(_jb_tree(root))
        assert not problems, problems
        got = {b: e for (t, b), e in intros.items()}
        assert all(t == "2025-2026" for t, _b in intros), sorted(intros)
        e = got.get("HB476")
        assert e, f"HB 476's entry was not read: {sorted(got)}"
        assert (e["designation"], e["suffix"], e["committee"]) == (
            "HB 476-FN", "-FN", "Judiciary"), (e["designation"], e["committee"])
        assert e["title"] == "relative to restrictions on elective abortion.", e["title"]
        assert e["sponsors"][0] == "Peternel, Carr. 6" and len(e["sponsors"]) == 9, e["sponsors"]
        assert e["sponsors"][2] == "Burnham, Straf. 2", e["sponsors"]
        assert (e["cite"]["journal"], e["cite"]["page"], e["cite"]["line"],
                e["cite"]["date"]) == ("HJ 3", 1, 15, "2025-01-09"), e["cite"]
        hcr = got.get("HCR7") or {}
        assert "Vandecasteele, Rock. 25" in hcr.get("sponsors", []), (
            f"a name broken across a page head was not rejoined: {hcr.get('sponsors')}")
        assert hcr.get("committee") == "Health, Human Services and Elderly Affairs", hcr
        assert got["HB234"]["sponsors"][0] == "Harrington, Straf. 18", got["HB234"]["sponsors"]
        for gone in ("HB1164", "HB1437", "HB1470", "HB1545"):
            assert gone not in got, f"the placeholder {gone} was read as a bill"
        for kept, title in (("HB1165", "relative to gender designation on state-issued "
                                       "identification."),
                            ("HB1438", "requiring mental health caseworkers to report "
                                       "instances of animal abuse."),
                            ("HB1471", "relative to changes to the state retirement system."),
                            ("HB1546", "repealing the business profits tax.")):
            assert got.get(kept, {}).get("title") == title, (
                f"the entry after a placeholder was swallowed or garbled: {kept} "
                f"{got.get(kept)}")
        assert got["HB1165"]["cite"]["page"] == 10, got["HB1165"]["cite"]
        assert got["CACR1"]["title"].startswith("relating to the governor. Providing that"), (
            got["CACR1"]["title"])
        assert got["CACR1"]["committee"] == "Executive Departments and Administration"
        assert len(got) == 10, sorted(got)
        assert J.pages(["x", "\f19FEBRUARY2026HOUSERECORD  39", "y"]) == [1, 39, 39], (
            "an odd page's head read as another page")
        assert J.pages(["\f4  8JANUARY2025HOUSERECORD", "y"]) == [4, 4]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("10 measures read; four placeholders give nothing and swallow "
                  "nothing; names rejoined at a line end and across a page head")


@check("build", "a withdrawal stands only where the House's own record says it did",
       needs=("journal_bills",))
def _journal_withdrawals(J):
    """A record is written for a bill introduced AND withdrawn for good:
      - listed TO BE WITHDRAWN on a consent calendar the journal records as
        adopted -- HB 234;
      - but not where members removed it from that calendar -- HB 523 here,
        whose removal is invented (the House withdrew it on that calendar);
      - a MOTION TO WITHDRAW adopted, with its vote, and the reconsideration
        that failed beside it -- HB 476, 335-18 and 15-340;
      - not a motion that failed, whose outcome comes after a roll call --
        HB 431, 160-207, which the House went on to pass;
      - not one a carried motion to reconsider undid, the motion to withdraw
        then put again and lost -- HCR 7 here, invented throughout.
    And a year folder holding a sitting of its own year with no introduction
    read from it is refused, non-zero, with nothing written; a folder holding
    only December's organization day is not.
    """
    import contextlib
    import io
    root = Path(tempfile.mkdtemp())
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _intros, records, report, problems = J.read_all(_jb_tree(root))
        assert not problems, problems
        recs = records.get("2025-2026") or {}
        assert sorted(recs) == ["HB234", "HB476"], (
            f"withdrawn records {sorted(recs)}, wanted HB234 and HB476; notes: {report}")
        w = recs["HB234"]["withdrawn"]
        assert (w["how"], w["date"], w["journal"]) == ("consent calendar", "2025-02-06",
                                                      "HJ 4"), w
        assert recs["HB234"]["introduced"]["date"] == "2025-01-09"
        w = recs["HB476"]["withdrawn"]
        assert (w["how"], w.get("vote"), w.get("reconsideration")) == (
            "motion", "335-18, division", "failed, 15-340"), w
        assert recs["HB476"]["title"] == "relative to restrictions on elective abortion."
        assert recs["HB476"]["committee"] == "Judiciary"
        assert any("HB523" in x and "removed" in x for x in report), report
        assert any("HCR7" in x and "reconsidered" in x for x in report), report

        # A year that cannot be read is refused rather than written empty.
        bad = Path(tempfile.mkdtemp())
        out = bad / "journal_bills.json"
        try:
            (bad / "journals" / "2025").mkdir(parents=True)
            (bad / "journals" / "2025" / "HJ 04 February 6, 2025.txt").write_text(
                "\n".join(_JB_FEB6) + "\n", encoding="utf-8")
            r = _run([sys.executable, _paths.script("journal_bills.py"), "--root", str(bad / "journals"),
                      "--out", str(out)], capture_output=True, text=True, timeout=120)
            assert r.returncode != 0 and not out.exists(), (
                f"a year of sittings with no introduction read was written "
                f"(exit {r.returncode}): {(r.stdout + r.stderr)[-300:]}")
            assert "REFUSED" in r.stderr, r.stderr[-300:]
            # December's organization day opens next year's folder and has no
            # list yet: said, not refused.
            shutil.rmtree(bad / "journals" / "2025")
            _jb_tree(bad)
            (bad / "journals" / "2027").mkdir()
            (bad / "journals" / "2027" / "HJ 01 December 2, 2026.txt").write_text(
                "              HOUSE JOURNAL NO. 1\n\n"
                "                          Wednesday, December 2, 2026\n\n"
                "The House assembled at 10:00 a.m.\n", encoding="utf-8")
            r = _run([sys.executable, _paths.script("journal_bills.py"), "--root", str(bad / "journals"),
                      "--out", str(out)], capture_output=True, text=True, timeout=120)
            assert r.returncode == 0 and out.exists(), (r.stdout + r.stderr)[-300:]
            assert sorted(json.loads(out.read_text(encoding="utf-8"))["2025-2026"]) == [
                "HB234", "HB476"]
        finally:
            shutil.rmtree(bad, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("consent-calendar and motion withdrawals stand; a removal, a failed "
                  "motion and a carried reconsideration give none; an unreadable year "
                  "is refused")


_JB_HEAD3 = ["              HOUSE JOURNAL NO. 3", "",
             "                                 Thursday, January 9, 2025", ""]
_JB_HEAD4 = ["              HOUSE JOURNAL NO. 4", "",
             "                                 Thursday, February 6, 2025", ""]
_JB_LIST = ["                                                INTRODUCTION OF HOUSE BILLS", "",
            "                                                 First, second reading and referral",
            ""]


def _jb_consent(tbw, adopted="Consent Calendar was adopted.", heading="TO BE WITHDRAWN",
                pre=()):
    """A consent calendar of 6 February 2025's shape, `tbw` its TO BE
    WITHDRAWN list."""
    return ["                                                          CONSENT CALENDAR",
            "Rep. Osborne moved that the Consent Calendar with the relevant amendments as "
            "printed in the day's House", "Record be adopted.", *pre, adopted, "",
            "HB 178, relative to foster parents. OUGHT TO PASS.",
            "Rep. Mark Pearson for Children and Family Law. Vote 18-0.", "",
            f"                                                            {heading}", "",
            *tbw, "", "                                                          REGULAR CALENDAR",
            ""]


def _jb_motion(bill, *after):
    return ["                                                        MOTION TO WITHDRAW",
            f"{bill}, relative to apples, removed by Reps. Wade and Selig.", "",
            "The question being adoption of the motion to withdraw.", *after]


def _jb_case(J, entries, body, files=()):
    """read_all over two sittings of 2025 -- 9 January's list of bills
    introduced holding `entries`, and 6 February's `body` -- and any `files`
    besides: ({bill: intro}, {bill: record}, notes, problems)."""
    import contextlib
    import io
    root = Path(tempfile.mkdtemp())
    try:
        d = root / "2025"
        d.mkdir(parents=True)
        for name, lines in (("HJ 03 January 9, 2025.txt",
                             _JB_HEAD3 + _JB_LIST + list(entries)
                             + ["", "                    RECESS", ""]),
                            ("HJ 04 February 6, 2025.txt", _JB_HEAD4 + list(body)),
                            *files):
            (d / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            intros, records, report, problems = J.read_all(root)
        return ({b: e for (_t, b), e in intros.items()}, records.get("2025-2026") or {},
                report, problems)
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the journal reader refuses a withdrawal it cannot decide",
       needs=("journal_bills",))
def _journal_undecided(J):
    """A withdrawn bill is in none of the General Court's files, so one the
    reader misses is gone from the site with every step reporting success.
    What it reads and understands it records or notes; what it saw and could
    not decide stops the run. Each case is a form the journals or the House
    Calendar print, or a way the reader was shown to fail silently:

      - "Motion adopted." (2026's wording, fourteen times), a heading in
        title case, "Consent Calendar adopted." -- read, and recorded;
      - a blank line inside an entry (SB 83 of 2025 lost 135 Senate bills
        after it), a committee alone below a blank (SB 118), a CACR under
        INTRODUCTION OF SENATE BILLS (CACR 11 of 2026) -- read, the CACR as
        the Senate's;
      - "not introduced" after an en dash or no dash -- a placeholder, not
        glued to the entry before;
      - a TO BE WITHDRAWN title wrapping onto a line that begins "HB 2," --
        one bill, not two; a "removed by" past a page head -- removed;
      - a reconsideration "whereby it withdrew" that carried, and the motion
        to withdraw then lost -- no record, a note;
      - REFUSED: a motion with no outcome read; TO BE WITHDRAWN outside a
        consent calendar, or on one not read as adopted; a reconsideration
        that carried with no second vote read; a House bill withdrawn with no
        introduction read; a record without sponsors or committee (a list
        that ran into the prose after it); a sitting whose dateline is not
        read. A Senate bill the House withdrew is a note, not a refusal.
    """
    apples = ["HB 100, relative to apples. (Smith, Hills. 1; Judiciary)"]
    tbw100 = ["HB 100, relative to apples."]

    def wants(case, got, records, report, problems, record=None, problem=None, note=None):
        if record is not None:
            assert sorted(records) == sorted(record) and not problems, (
                f"{case}: records {sorted(records)}, wanted {sorted(record)}; "
                f"problems {problems}; notes {report}")
        if problem:
            assert any(problem in x for x in problems), (
                f"{case}: not refused ({problem!r} not in {problems}); records "
                f"{sorted(records)}")
        if note:
            assert any(note in x for x in report) and not problems, (
                f"{case}: no note {note!r} ({report}); problems {problems}")

    # Read and recorded.
    for case, body in (
            ("Motion adopted.", _jb_motion("HB 100", "Motion adopted.", "")),
            ("To Be Withdrawn", _jb_consent(tbw100, heading="To Be Withdrawn")),
            ("Consent Calendar adopted.",
             _jb_consent(tbw100, adopted="Consent Calendar adopted."))):
        wants(case, *_jb_case(J, apples, body), record=["HB100"])

    # A blank line inside an entry, a placeholder of another spelling.
    got, recs, rep, prob = _jb_case(J, [
        "HB 100, relative to apples. (Smith, Hills. 1; Judiciary)",
        "HB 101, relative to pears and plums and other fruit that grows in the",
        "",
        "state of New Hampshire. (Jones, Rock. 2; Brown, Merr. 3; Ways and Means)",
        "HB 102 – not introduced.",
        "HB 103, relative to cherries. (Green, Ches. 4; Election Law)",
        "HB 104 not introduced.",
        "HB 105, relative to grapes. (",
        "",
        "White, Sull. 5; Housing)"],
        _jb_consent(["HB 101, relative to pears.", "HB 105, relative to grapes."]))
    assert sorted(got) == ["HB100", "HB101", "HB103", "HB105"], sorted(got)
    assert got["HB101"]["sponsors"] == ["Jones, Rock. 2", "Brown, Merr. 3"], got["HB101"]
    assert got["HB101"]["title"].endswith("state of New Hampshire."), got["HB101"]["title"]
    assert got["HB100"]["title"] == "relative to apples." and got["HB103"]["committee"] == (
        "Election Law"), (got["HB100"], got["HB103"])
    wants("a blank inside an entry", got, recs, rep, prob, record=["HB101", "HB105"])

    # One wrapped title, not two bills; a removal the page turned onto.
    wants("a title wrapping at a designation", *_jb_case(
        J, apples + ["HB 2, relative to the budget. (Weyler, Rock. 14; Finance)"],
        _jb_consent(["HB 100, relative to apples and to the amendments made in",
                     "HB 2, the budget."])), record=["HB100"])
    wants("a removal past a page head", *_jb_case(J, apples, _jb_consent(tbw100, pre=[
        "HB 100, relative to apples and to the many varieties of apple grown in orchards",
        "\f2  6FEBRUARY2025HOUSERECORD", "",
        "and sold at farm stands, removed by Reps. Wade and Selig."])),
        record=[], note="removed from the consent calendar")

    # A reconsideration that carried, the motion to withdraw then lost.
    recon = ["", "                                                       MOTION TO RECONSIDER",
             "Having voted with the prevailing side, Rep. Selig moved that the House "
             "reconsider its action whereby it withdrew HB 100.",
             "The question being adoption of the motion to reconsider.", "Motion adopted."]
    wants("reconsidered, then lost", *_jb_case(J, apples, _jb_motion(
        "HB 100", "Motion was adopted.", *recon,
        "The question now being adoption of the motion to withdraw.", "Motion failed.", "")),
        record=[], note="then failed")
    wants("reconsidered, second vote unread", *_jb_case(J, apples, _jb_motion(
        "HB 100", "Motion was adopted.", *recon, "")), problem="reconsidered")

    # Refused.
    for case, entries, body, problem in (
            ("no outcome", apples, _jb_motion("HB 100", "Rep. Wade spoke.", ""),
             "no outcome read"),
            ("outside a consent calendar", apples,
             ["                    TO BE WITHDRAWN", "", *tbw100, ""], "outside a consent"),
            ("calendar not read as adopted", apples,
             _jb_consent(tbw100, adopted="The calendar stood."), "not read as recording"),
            ("no introduction", apples, _jb_consent(["HB 900, relative to quinces."]),
             "no introduction list"),
            ("a list run into prose",
             apples + ["HB 101, relative to pears. (Jones, Rock. 2; Ways and Means)",
                       "Rep. Bogert moved that the House recess for introductions."],
             _jb_consent(["HB 101, relative to pears."]), "without a sponsors")):
        wants(case, *_jb_case(J, entries, body), problem=problem)
    wants("a Senate bill withdrawn", *_jb_case(
        J, apples, _jb_consent(["SB 9, relative to quinces."])), record=[],
        note="a Senate measure")
    wants("a dateline not read", *_jb_case(J, apples, [], files=[(
        "HJ 05 February 13, 2025.txt",
        ["              HOUSE JOURNAL NO. 5", "", "Thursday,February13,2025", ""]
        + _jb_motion("HB 100", "Motion was adopted."))]), problem="no dateline")

    # Whose list: a CACR under INTRODUCTION OF SENATE BILLS, and a committee
    # alone below a blank -- one the General Court's committee table names,
    # given here so that the check needs no Committees.txt on disk.
    root = Path(tempfile.mkdtemp())
    saved = list(J._CKEYS)
    J._CKEYS[:] = [{J._ckey("Health, Human Services and Elderly Affairs")}]
    try:
        f = root / "HJ 11 March 27, 2025.txt"
        f.write_text("\n".join(_JB_HEAD3 + [
            "                                               INTRODUCTION OF SENATE BILLS", "",
            "                                                 First, second reading and referral",
            "",
            "CACR 8, relating to sheriffs. Providing that there be no age limit. "
            "(Executive Departments and Administration)",
            "SB 118-FN, relative to the personal needs allowance of residents of nursing homes.",
            "", "(Health, Human Services and Elderly Affairs)", "",
            "SB 119-FN, relative to Medicaid pharmaceutical services. (Health, Human Services "
            "and Elderly Affairs)", "", "                    RECESS", ""]) + "\n",
            encoding="utf-8")
        r = J.read_file(f, 2025)
        got = {e["bill"]: e for e in r["intros"]}
        assert sorted(got) == ["CACR8", "SB118", "SB119"], sorted(got)
        assert {e["chamber"] for e in got.values()} == {"S"}, got["CACR8"]
        assert got["SB118"]["committee"] == "Health, Human Services and Elderly Affairs", (
            got["SB118"])
    finally:
        J._CKEYS[:] = saved
        shutil.rmtree(root, ignore_errors=True)
    # A title's own parenthesis does not close an entry at a page turn.
    assert not J._closed("HB 450, relative to clean energy and resiliency (C-PACER)")
    assert J._closed("SB 73-FN, relative to the operation of bingo games. (Ways and Means)")
    assert J._closed("HB 449, cases. (D. McGuire, Merr. 14; Resources, Recreation and Development)")
    assert J._continues("(Packard, Rock. 16; Hunt, Ches. 14;",
                        "HB 450, relative to clean energy and resiliency (C-PACER)")
    assert not J._continues("(Speaker Packard in the Chair)", "SB 56, relative to the authority.")
    assert not J._continues("(Packard, Rock. 16; Finance)", "HB 1, x. (Smith, Rock. 1; Finance)")
    return "ok", ("new wordings recorded, the press's blanks and placeholders read; "
                  "seven undecided withdrawals refused; a Senate CACR is the Senate's")


@check("frontend", "a seat reads the same on the chart, the roster and a member's page")
def _plate_agrees():
    """plate() is written three times and nothing held the copies together.

    A seat is stored as one integer, 4017, and shown as 4-017 -- division 4,
    seat 17, which is what a representative's licence plate says and what
    somebody looking one up has in their head. Three places turn one into the
    other: seating.py for the chart's own titles, app.js for a member's page,
    and build_pages' chart script for the readout under the floor.

    Drift would be quiet and confusing in the worst way: the same seat would
    read 4-017 on the member's page and 4017 under the chart, and a reader
    matching a plate would not know which of the two was the number they
    wanted. The three are run against the same inputs here rather than
    compared as text, because two of them are JavaScript and the thing that
    matters is the answer, not the spelling.
    """
    import seating as _seating
    cases = [4017, 3119, 1001, 6002, 5043, 2080, 1, 999, 12345]
    want = [_seating.plate(c) for c in cases]

    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", "node is not on PATH, so the JavaScript copies cannot be run"
    js = _source("src/pages/app.js", errors="replace")
    import inline_js as IJ
    # The builder and its scripts, in inline/ since 20 November 2026.
    bp = _source(_paths.locate("build_pages.py"), errors="replace") + "".join(
        _source(p, errors="replace") for n, p in IJ.files().items() if n.split(".")[0] == "build_pages")
    grab = lambda src, name: re.search(
        r"function plate\(\w+\)\{.*?\n(?:\s*)\}", src, re.S)
    got = {}
    for label, src in (("app.js", js), ("build_pages.py", bp)):
        m = grab(src, label)
        assert m, f"{label} has no plate() function"
        prog = (m.group(0) + "\n"
                + "const out=" + repr(cases).replace("'", '"')
                + ".map(c=>plate(c));\n"
                + "process.stdout.write(JSON.stringify(out));")
        r = subprocess.run([node, "-e", prog], capture_output=True, timeout=30)
        assert r.returncode == 0, (
            f"{label}'s plate() would not run: "
            + r.stderr.decode("utf-8", "replace")[-200:])
        got[label] = json.loads(r.stdout.decode("utf-8", "replace"))

    for label, answers in got.items():
        assert answers == want, (
            f"{label}'s plate() disagrees with seating.py: "
            + ", ".join(f"{c}: {label}={a!r} seating={w!r}"
                        for c, a, w in zip(cases, answers, want) if a != w))
    return "ok", f"three plate() copies agree on {len(cases)} seats, 4017 -> {want[0]}"


# Every form of a vote's question the 2025-2026 record carries, and a sample of the older
# clerks', with the key the approved words give it (10 October 2026, read off the built
# site's bills: 216 forms).
@check("session", "a unanimous-consent subject reads through a title's full stop",
       needs=("journal_days",))
def _uc_subject_titles(journal_days):
    """9 April 2026: "Rep. Kat McGhee requested Unanimous Consent of the House
    regarding Rep. Wendy Thomas and addressed the House." The subject stopped
    at the first full stop and the session day said "on Rep."."""
    got = [(m.group("name"), m.group("about")) for m in journal_days.UC_LINE.finditer(
        "Rep. Kat McGhee requested Unanimous Consent of the House regarding Rep. Wendy "
        "Thomas and addressed the House. Rep. Walz requested Unanimous Consent of the "
        "House regarding an apology and addressed the House. Rep. Smith addressed the House.")]
    assert got == [("Kat McGhee", "Rep. Wendy Thomas"), ("Walz", "an apology"),
                   ("Smith", None)], got
    return "ok", "a member named as the subject is named whole"


@check("session", "a session day names each member by the seat they held in its term: the old "
                  "seat on an old day, the roster's in the term it describes, and no seat where "
                  "the record gives none", needs=("build_session_pages", "build_site_v2"))
def _session_seat_at_the_time(BSP, B2):
    """labels-use-the-seat-held-at-the-time (the person, 16 September 2026:
    "show them as a rep when they were a rep and a senator when they were a
    senator"). A session day's chips -- who spoke, who was excused, who
    presided -- were each member's label from today's roster, so a member
    whose district was renumbered or who moved seats was named on 2015's
    days by the seat of 2025. The seat is each member's own ballots' of the
    day's term (build_site_v2.term_seats, written into the floor record);
    in the term the roster describes, a sitting member's roster label; and
    where neither says, the name alone with the day's chamber's honorific.
    Rep. James Spillane, whose seat was Rockingham 5 in 2015-2016 (a fixture's
    ballots) and is Rockingham 2 now."""
    def ballot(year, label, member="905", name="Spillane, James"):
        return {"year": str(year), "body": "H", "vote_number": 1, "member_id": member,
                "name": name, "party": "R", "label": label, "date": f"3/1/{year}"}
    # The ballots carry one undated label, today's roster's; the seat of
    # 2015-2016 is the one that term's bills print (term_seats' `printed`).
    seats = B2.term_seats({
        "905": [ballot(2015, "Rep. James Spillane (R - Rock 2)"),
                ballot(2016, "Rep. James Spillane (R - Rock 2)"),
                ballot(2025, "Rep. James Spillane (R - Rock 2)")],
        # two seats in one term name neither
        "77": [ballot(2015, "Rep. Pat Two (D - Hills 3)", "77", "Two, Pat"),
               ballot(2016, "Rep. Pat Two (D - Hills 4)", "77", "Two, Pat")]},
        printed={("2015-2016", "905"): ("H", "Rockingham", "5")})
    assert seats.get("2015-2016", {}).get("905") == "Rep. James Spillane (R - Rock 5)" and \
        seats.get("2025-2026", {}).get("905") == "Rep. James Spillane (R - Rock 2)" and \
        "77" not in seats.get("2015-2016", {}), f"the seats of a term read off its ballots: {seats}"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "legislators.json").write_text(json.dumps([
            {"id": "905", "slug": "james-spillane-rock-2", "name": "Spillane, James", "chamber": "H",
             "party": "R", "display_full": "Rep. James Spillane (R - Rock 2)"}]), encoding="utf-8")
        (root / "former.json").write_text("[]", encoding="utf-8")
        m = BSP.Members(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    m.seats = {"2015-2016": {"905": "Rep. James Spillane (R - Rock 5)"}}
    m.current = "2025-2026"
    got = {}
    for term in ("2015-2016", "2009-2010", "2025-2026"):
        m.term = term
        got[term] = (BSP.member_info("H", "Spillane", m) or {}).get("display_full")
    want = {"2015-2016": "Rep. James Spillane (R - Rock 5)", "2009-2010": "Rep. James Spillane",
            "2025-2026": "Rep. James Spillane (R - Rock 2)"}
    assert got == want, f"a member's chip on a day of each term reads {got}, not {want}"
    chip = BSP.members_row("H", ["Spillane"], m, str)
    assert "(R - Rock 2)" in chip, chip
    m.term = "2015-2016"
    assert "(R - Rock 5)" in BSP.members_row("H", ["Spillane"], m, str), (
        "a speaker line of 2015 names the member by today's seat")
    return "ok", ("Rep. James Spillane is Rock 5 on a day of 2015-2016, Rock 2 on one of "
                  "2025-2026, and seatless on one of 2009-2010, where no ballot says")


@check("data", "every chip on a past term's session day names the seat of its term or none, and a "
               "bill's sponsor line of the day's term agrees with it", needs=("build_session_pages",))
def _session_chips_seat_of_their_term(BSP):
    """The built pages, held to _session_seat_at_the_time's rule, on every
    session day outside the term the roster describes:
      - who spoke, was excused or presided is named by the seat of the term
        (data/floor_record.json's seats, build_site_v2.term_seats), or with
        none where the term has none;
      - a card's sponsor line is the bill's own record, so it is not held to
        the term's seat -- except that a bill of the day's term naming a
        member at another seat than the term's is one page naming one member
        two ways (Chandley on 3 March 2010: "Hills 6" as HB 1387's sponsor,
        "Hills 22" as a speaker, until 5 November 2026). A bill carried over
        from another term may name the seat it was filed under; a sponsor
        line with a party and no seat names none.
    THIS CHECK ONCE PASSED ON NOTHING (5 November 2026): its pattern wanted
    "legislator/<slug>.html" and the pages link "legislator/<slug>", so it
    read no chip at all for as long as it stood. It now fails on a run that
    reads none."""
    sess, fr = Path("site/session"), BSP.floor_record()
    if not sess.exists() or not fr.get("seats"):
        return "skip", "no built session days or no floor record seats here"
    ids = {}
    for f in ("site/legislators.json", "site/former.json"):
        if Path(f).exists():
            for r in json.loads(Path(f).read_text(encoding="utf-8")):
                if r.get("slug"):
                    # a mover's page stands for every number it lists, its own first
                    own = str(r.get("id") or "")
                    ids.setdefault(r["slug"], [own, *(str(x) for x in r.get("member_ids") or []
                                                      if str(x) != own)])
    import build_date
    import proceedings
    today = build_date.today().isoformat()
    current = proceedings.vote_term(today[:4], today)
    chip = re.compile(r'<span class="mchip p-\w" translate="no"><a href="legislator/([^"]+?)(?:\.html)?">'
                      r'([^<]*?)(?: <span class="mtag">([^<]*)</span>)?</a>')
    seat = re.compile(r"\(\w - ([^()]+)\)$")
    link = re.compile(r'<a class="psent" href="legislator/([^"]+?)(?:\.html)?" translate="no">([^<]*)</a>')
    bad, n = [], Counter()
    for page in sorted(sess.glob("[HS]/*.html")):
        term = proceedings.vote_term(page.stem[:4], page.stem)
        if term == current:
            continue
        html = page.read_text(encoding="utf-8")
        held = fr["seats"].get(term) or {}
        for m in chip.finditer(html):
            slug, name, tag = m.groups()
            n["read"] += 1
            want = BSP.seat_of(held, ids.get(slug, []), page.parent.name) or None
            before = html[:m.start()]
            if before.rfind('class="cmeta"') > before.rfind("</div>"):
                # a sponsor line: the bill's own record
                n["sponsor"] += 1
                year = (re.findall(r'href="bill/(\d{4})/', before[-4000:]) or [""])[-1]
                got, w = seat.search(tag or ""), seat.search(want or "")
                if got and w and year in (term[:4], term[5:]) and got.group(1) != w.group(1):
                    bad.append(f"{page.parent.name} {page.stem}: {name} as {year}'s sponsor at "
                               f"{got.group(1)}, the term's seat {w.group(1)}")
                continue
            n["named"] += 1
            if (f"{name} {tag}" if tag else None) != want and (tag or want):
                bad.append(f"{page.parent.name} {page.stem}: {name} {tag or '(no seat)'}, the seat of "
                           f"{term} is {want!r}")
        # who presided and who moved, named in a sentence (components.person_link):
        # the term's seat, else the name alone -- never a party letter alone
        for slug, said in link.findall(html):
            n["linked"] += 1
            said = __import__("html").unescape(said)
            want = BSP.seat_of(held, ids.get(slug, []), page.parent.name) or None
            if said != want and (want or said.endswith(")")):
                bad.append(f"{page.parent.name} {page.stem}: {said} in a sentence, the seat of "
                           f"{term} is {want!r}")
    # each pattern on its own: one finding names must not cover for the other
    assert n["read"], "no member chip was read on any past term's session day: the pattern has drifted"
    assert n["linked"], "no member named in a sentence was read on any past term's day: the pattern has drifted"
    assert not bad, f"{len(bad)} chip(s) name a seat not held that term: " + "; ".join(bad[:4])
    return "ok", (f"{n['read'] + n['linked']:,} member names on past terms' days: {n['named']:,} chips and "
                  f"{n['linked']:,} in sentences named by the seat of their term or none, "
                  f"{n['sponsor']:,} sponsor lines agreeing with it")


@check("frontend", "a session day folds the consent calendar and the excused with their counts, "
                   "names who presided in one line, and plays no recording for a consent bill")
def _session_day_folds():
    """The person's feedback of 9 October 2026 on the session day: the consent calendar's
    bills "hidden in a dropdown by default, with each category's count shown" (item 18),
    the counts in the status chips' colours (v19), the bills taken off it in their
    sentence; the members excused "a compact dropdown ... closed by default, with the
    count of members excused from each party" (v16); "a general line naming the members
    who presided" (v18); "a bill that passes on the consent calendar needs no embedded
    YouTube recording" (v3). Read off the fixture's session days and the code that draws
    them."""
    import build_session_pages as BSP
    shared, _base, _ran, _days = _fixture_site_shared()
    pages = sorted((shared / "site" / "session").rglob("*.html"))
    assert pages, "the fixture built no session day"
    text = "\n".join(p.read_text(encoding="utf-8") for p in pages)
    bad = []
    for m in re.finditer(r'<details class="sfold (sconsent|sexcused)"( open)?', text):
        if m.group(2):
            bad.append(f"the {m.group(1)} fold is drawn open")
    if '<p class="dvh">' in text and 'class="rhead rh-day"' not in text:
        bad.append("a session day has no record head")
    assert not bad, "; ".join(bad)
    src = _source("src/pages/build_session_pages.py")
    assert BSP.CONSENT_CLASS == {"Passed": "s-law", "Killed": "s-done",
                                 "Sent to Interim Study": "s-study",
                                 "Sent Back to Committee": "s-active", "Adopted": "s-adopted"}, (
        f"the consent counts are not in the chips' colours: {BSP.CONSENT_CLASS}")
    # EVERY GROUP IS ONE OF THE APPROVED WORDS, IN ITS CHIP'S COLOURS: the
    # Senate's "Refer to Interim Study" was listed under the record's own
    # words, in no colour, on 92 days, and the clerk's spellings of
    # Inexpedient to Legislate each made a group of one (the look of
    # 10 October 2026). The actions are the record's.
    class _It:
        def __init__(self, action):
            self.action, self.carried = action, True
    for said in ("Refer to Interim Study", "Rerefer to Interim Study", "Interim Study",
                 "Re-Refer to Committee", "Inexepdient to Legislate", "Inexpedient to Legistlate",
                 "Ought Not to Pass", "Ought to Adopt with Amendment #0806h (New Title)",
                 "Ought to Pass with Amendment 2026-0546h", "Inexpedient to Legislate",
                 "Indefinitely Postpone", "Adopt"):
        assert BSP.short_outcome(_It(said)) in BSP.CONSENT_CLASS, (
            f"a consent calendar lists {said!r} under {BSP.short_outcome(_It(said))!r}, "
            "which is none of the approved groups and has no chip's colours")
    for need, why in (("were removed from the consent", "the removed bills' sentence is gone"),
                      ("Presiding over the", "no general line names who presided"),
                      ("by_party", "the excused are not counted by party")):
        assert need in src, why
    assert BSP.and_list(["a", "b", "c"]) == "a, b, and c" and BSP.and_list(["a", "b"]) == "a and b"
    v2 = _source("src/pages/build_site_v2.py")
    fm = v2[v2.index("def floor_moment("):v2.index("def write_floor_record(")]
    assert '"consent"' not in fm or "return None" in fm
    import build_site_v2 as B2
    assert B2.floor_moment({"state": "consent", "video_id": "x", "what": "consent calendar",
                            "when": "2026-02-19", "committee": "House"}) is None, (
        "a bill decided on the consent calendar is given a moment in the day's recording")
    assert B2.floor_moment({"state": "floor_precise", "video_id": "v", "what": "floor debate",
                            "when": "2026-02-19", "committee": "House", "debate_start": 61.5,
                            "debate_end": 900.0, "window_start": 10.0})["from"] == 61
    return "ok", (f"{len(pages)} fixture session days: both folds closed; the counts in the "
                  "chips' colours; the presiding line; no moment for a consent bill")


@check("build", "a chamber's session days carry their recordings -- a bill's moments', or the "
       "channel's own session recording of the day -- and its page lists them on a Videos tab "
       "beside Session Days", needs=("build_session_pages", "build_full_sessions", "build_pages"))
def _chamber_videos(BSP, FS, BP):
    """The owner, 26 October 2026: "Same goes for session days". A day's
    `videos` were only the recordings a bill's moment of it is in, so every
    day before 2025 and a few since said "No recording of this day is on
    file" on the chamber's page, 108 of them over a recording the channel has
    and titles as the day's session. build_session_pages.day_record takes that
    recording where no moment names one, and writes `recordings` beside
    `videos`, the same in the same order, with when each began and ran; the
    chamber's page plays them in each day's fold, as before, and writes the
    latest term's days into the page for app.js to draw as its Videos tab,
    Session Days | Videos, at /session/<chamber>/videos, which _redirects
    serves. On the fixture: the Senate's 19 February 2026 by its title, the
    House's 6 March by its moment."""
    import about_figures as AF
    root = Path(tempfile.mkdtemp())
    try:
        _fixture_videos(root)
        facts = __import__("proceedings").video_facts(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    sv = BSP.session_videos(facts)
    assert dict(sv) == {("H", "2026-03-06"): ["VID2"], ("S", "2026-02-19"): ["senSessV001"]}, (
        f"the channel's session recordings read {dict(sv)}")
    red = BP.REDIRECTS
    for slug in FS.SLUG.values():
        assert f"\n/session/{slug}/videos /session/{slug} 200\n" in red, (
            f"_redirects does not serve /session/{slug}/videos as the chamber's page")
    # SILENCE IS NOT SUCCESS: moments naming recordings beside an index that
    # reads as nothing is a broken checkout, and the build stops, as
    # build_committees does (_committee_recordings). Taken out, nothing failed
    # (the review of 29 October 2026).
    import inspect
    src = inspect.getsource(BSP.chamber)
    stop = src.find('if ctx["moments"] and not ctx["facts"]:')
    assert stop >= 0 and "raise SystemExit(" in src[stop:stop + 200], (
        "build_session_pages no longer stops on an empty video index beside moments naming recordings")
    # ONE DAY, WORDED ONCE: the Videos tab's detail for a day and the day's
    # fold on Session Days (day_section; the page's script draws the same,
    # held to it by "a chamber's page ...") say what the day did, lead to its
    # full page and name its journal alike. app.js writes them a third time
    # (chamberRows), and nothing held the three together.
    d = {"date": "2026-02-19", "journal": "HJ 05", "journal_url": "https://example.test/hj5.pdf",
         "counts": {"bills": 164, "roll_calls": 17}, "videos": ["abcDEF12345"],
         "summary": "The House took up 164 bills, with 17 roll calls."}
    det = _app_js("scope.chamberRows(" + json.dumps({"body": "H", "days": [d]}) + ")[0].detail()",
                  names=("chamberRows",))
    if det is not None:
        said = lambda h: (re.findall(r'<p class="cmsaid">.*?</p>', h),
                          [a for a in re.findall(r"<a [^>]*>[^<]*</a>", h) if "youtube" not in a])
        fold = FS.day_section("H", d)
        assert said(det) == said(fold) and len(said(fold)[1]) == 2, (
            f"the Videos tab words a day as {said(det)}, its fold on Session Days as {said(fold)}")
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "ok", "the channel's session recordings read; not here to build: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    by = {}
    early = []
    for b in ("H", "S"):
        for f in (site / "session" / b).glob("*.json"):
            for d in json.loads(f.read_text(encoding="utf-8"))["days"]:
                by[(b, d["date"])] = d
                assert [r["id"] for r in d.get("recordings") or []] == (d.get("videos") or []), (
                    f"{b} {d['date']}: recordings {d.get('recordings')} are not its videos {d.get('videos')}")
                if d.get("videos") and d["date"] < AF.STREAM_START:
                    early.append(f"{b} {d['date']}")
    assert not early, f"a session day before the channels began has a recording: {early}"
    s = by[("S", "2026-02-19")]
    assert s.get("videos") == ["senSessV001"] and s.get("recordings") == [
        {"id": "senSessV001", "began": "09:58", "seconds": 11040}], (
            f"the Senate's 19 February has no recording, though its channel titles one its session: {s}")
    assert by[("H", "2026-03-06")].get("videos") == ["VID2"], "the House's day lost its moments' recording"
    page = (site / "session" / "senate.html").read_text(encoding="utf-8")
    fold = page[page.index('id="day-2026-02-19"'):]
    fold = fold[:fold.index("</details>")]
    assert 'data-embed="senSessV001|0|' in fold and "No recording of this day" not in fold, (
        "the Senate's 19 February still says no recording is on file in its fold")
    assert re.search(r'<div class="chpane" id="chdays"><div class="bfilt chorder"><label>Order ', page) and \
        '<div class="chpane" id="chvids" hidden><div class="vwhere" data-vwview="gr-videos">' in page, (
            "the chamber's page does not carry its two panes, the Videos one hidden until app.js draws it")
    data = json.loads(re.search(r'<script type="application/json" id="gr-videos">(.*?)</script>', page,
                                re.S).group(1))
    assert (data["kind"], data["body"], data["slug"], data["term"] == data["latest"]) == (
        "chamber", "S", "senate", True) and [d["date"] for d in data["days"]] == ["2026-02-19"] \
        and data["days"][0]["recordings"] == s["recordings"], f"the page's Videos rows read {data}"
    drawn = _app_js("[scope.videoView(scope.VW_STATIC.chamber(" + json.dumps(data) + ")),"
                    " scope.VW_STATIC.chamber(" + json.dumps(dict(data, term="2019-2020", days=[]))
                    + ").empty]", names=("videoView", "VW_STATIC"))
    if drawn is None:
        return "ok", "the days carry their recordings and the page its panes; node is not here to draw them"
    import html as _html
    view, empty = drawn
    flat = _html.unescape(re.sub(r"<[^>]+>", "", view))
    assert "<iframe" not in view and 'data-embed="senSessV001|0|v20260219_senSessV001"' in view, (
        "the chamber's Videos tab is not a still of its newest recording")
    assert "The Senate, ·\u00a0Feb 19, 2026, ·\u00a09:58 AM, ·\u00a03 h 4 min, ·\u00a0On YouTube" in flat \
        and "1 recording in 2025–2026" in flat and "1 bill, ·\u00a01 roll call" in flat \
        and not re.search(r"\b[HS]B\s?\d", flat), f"the chamber's Videos tab reads {flat[:400]!r}"
    assert '<a class="daylink" href="session/S/2026-02-19">The full session day</a>' in view, (
        "the chamber's Videos tab does not lead to the day's own page")
    assert _vw_loose_dots(view) == 0 and view.count(_VW_DOT_HEAD) >= 5, (
        "a dot in the chamber's Videos tab can end a line: it goes at the head of the part after it")
    assert empty == ("No recording of the Senate&rsquo;s session days in 2019–2020 is on file. "
                     "Recordings here begin in May 2020, with the General Court&rsquo;s YouTube channels."), (
        f"a term with none says {empty!r}")
    # ANOTHER TERM'S RECORDING, NAMED BY THE ADDRESS, is landed on as the
    # page's own term's is: /session/senate/videos?term=2023-2024#v-<id>
    # chose its row and left it at the top of a list of 39. Here the term's
    # file arrives (chamberVideos) and the row must be scrolled to inside a
    # list that scrolls, and the view brought into sight.
    landed = _node_app(r"""
require("./stub.js");
const fs = require("fs");
location.pathname = "/session/senate/videos"; location.search = "?term=2023-2024"; location.hash = "#v-mid2";
const s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({chamberVideos, setChamber: (d) => { VW_CHAMBER = d; }})");
const slot = document.querySelector("#chvids [data-vwview]");
const list = {scrollHeight: 2400, clientHeight: 440, scrollTop: 0, offsetTop: 0};
let seen = 0;
slot.closest = (sel) => sel === ".chpane" ? {} : null;
slot.scrollIntoView = () => { seen += 1; };
slot.querySelectorAll = () => [...slot.innerHTML.matchAll(/data-vwpick="([^"]*)"/g)].map((m, i) => {
  const li = {offsetTop: 60 * i, offsetHeight: 60};
  return {dataset: {vwpick: m[1]}, closest: (sel) => sel === ".vwlist" ? list : sel === "li" ? li : null};
});
const out = {};
try {
  s.setChamber({kind: "chamber", body: "S", slug: "senate", term: "2025-2026", latest: "2025-2026", days: []});
  const days = Array.from({length: 30}, (_, i) => ({date: `2023-${String(1 + Math.floor(i / 3)).padStart(2, "0")}-${
    String(10 + i % 3).padStart(2, "0")}`, videos: [i === 18 ? "mid2" : `v${i}`], counts: {}}));
  s.chamberVideos({term: "2023-2024", days});
  out.chosen = /data-vwpick="mid2" aria-current="true"/.test(slot.innerHTML);
  out.scrollTop = list.scrollTop; out.seen = seen; out.hash = location.hash;
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
""")
    if landed is not None:
        assert "threw" not in landed and landed["chosen"] and landed["hash"] == "#v-mid2", (
            f"another term's recording named by the address is not chosen: {landed}")
        # Newest first, mid2 (day 18 of 30) is the twelfth row: 11 x 60px down
        # its top, 720px its end, so the list moves 280px to show it whole.
        assert landed["scrollTop"] == 280 and landed["seen"] >= 1, (
            f"another term's recording named by the address is chosen but not shown: its list at "
            f"{landed['scrollTop']}px (280 shows it), the view brought into sight {landed['seen']} times")
    # A RECORDING PLAYING IN THE PANE A TAB HIDES IS PAUSED: the two panes are
    # shown and hidden, not drawn again, so a day's fold left playing under
    # the Videos tab, or the Videos tab's player under Session Days, played on
    # unseen (the review of 29 October 2026).
    paused = _node_app(r"""
require("./stub.js");
const fs = require("fs");
const s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({chamberShow})");
const sent = [];
const frame = (name) => ({onload: [], addEventListener(t, f) { if (t === "load") this.onload.push(f); },
  loaded() { this.onload.splice(0).forEach((f) => f()); },
  contentWindow: {postMessage: (m) => sent.push(name + " " + JSON.parse(m).func)}});
const pane = (name, hidden) => { const f = frame(name);
  return {hidden, f, querySelectorAll: (sel) => sel === "iframe" ? [f] : []}; };
const days = pane("days", false), vids = pane("vids", true);
document.getElementById = (id) => id === "chdays" ? days : id === "chvids" ? vids : null;
const out = {};
try {
  s.chamberShow(1, false); out.toVideos = sent.splice(0); out.shown = [days.hidden, vids.hidden];
  days.f.loaded(); out.loadedHidden = sent.splice(0);
  s.chamberShow(0, false); out.toDays = sent.splice(0);
  s.chamberShow(0, false); out.again = sent.splice(0);
  s.chamberShow(1, false); s.chamberShow(0, false); sent.splice(0);
  days.f.loaded(); out.loadedShown = sent.splice(0);
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
""")
    if paused is not None:
        assert "threw" not in paused and paused["shown"] == [True, False] and paused["toVideos"] == [
            "days pauseVideo"] and paused["toDays"] == ["vids pauseVideo"] and paused["again"] == [], (
            f"a recording playing in the pane a chamber's tab hides is not paused, or one shown is: {paused}")
        # A frame still loading when its pane is hidden cannot hear yet: it
        # is told again once loaded, and not if its pane is shown by then.
        assert paused["loadedHidden"] == ["days pauseVideo"] and paused["loadedShown"] == [], (
            f"a frame that loads after its pane is hidden plays on, or one shown again is paused: {paused}")
    # THE VIDEOS TAB TURNED TO AGAIN NAMES THE RECORDING CHOSEN THERE: Session
    # Days took the #v- off the address and the Videos tab did not put it
    # back, so Share, a copied link or a reload opened on the newest and not
    # on what was shown (the walk of 30 October 2026). The newest stays
    # unnamed, and an address that already names one keeps it.
    turned = _node_app(r"""
require("./stub.js");
const fs = require("fs");
location.pathname = "/session/senate/videos"; location.search = "?term=2023-2024"; location.hash = "#v-mid";
const at = () => location.pathname + location.search + location.hash;
history.replaceState = (st, t, u) => { const m = /^([^?#]*)(\?[^#]*)?(#.*)?$/.exec(u);
  location.pathname = m[1]; location.search = m[2] || ""; location.hash = m[3] || ""; };
const s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({chamberShow, set: (d, v) => { VW_CHAMBER = d; VVIEW = v; }})");
const pane = (hidden) => ({hidden, querySelectorAll: () => [], querySelector: (q) => q === ".vw" ? {} : null});
const days = pane(true), vids = pane(false);
document.getElementById = (id) => id === "chdays" ? days : id === "chvids" ? vids : null;
const out = {};
try {
  const v = {rows: [{id: "new"}, {id: "mid"}, {id: "old"}], chosen: "mid"};
  s.set({kind: "chamber", body: "S", slug: "senate", term: "2023-2024", latest: "2025-2026", days: []}, v);
  s.chamberShow(0, true); out.days = at();
  s.chamberShow(1, true); out.back = at();
  v.chosen = "new"; s.chamberShow(0, true); s.chamberShow(1, true); out.newest = at();
  v.chosen = "old"; location.hash = "#v-mid"; s.chamberShow(1, true); out.kept = at();
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
""")
    if turned is not None:
        assert "threw" not in turned and turned["days"] == "/session/senate?term=2023-2024" \
            and turned["back"] == "/session/senate/videos?term=2023-2024#v-mid", (
                f"the chamber's Videos tab turned to again does not name the recording chosen there: {turned}")
        assert turned["newest"] == "/session/senate/videos?term=2023-2024" \
            and turned["kept"] == "/session/senate/videos?term=2023-2024#v-mid", (
                f"the chamber's Videos tab names the newest, or drops a recording the address named: {turned}")
    return "ok", ("a day takes its channel's session recording where no moment names one; the "
                  "folds play it and the Videos tab, at its own address, lists the term's, counts "
                  "and no bills; a term before the channels says so; another term's recording the "
                  "address names is chosen and shown in its list; one playing in a pane its tab "
                  "hides is paused; the tab turned to again names the recording chosen there")


# A chamber's page as app.js meets it when it loads (GR_STATIC): the two
# panes, the term control the strip goes under, the slot and its rows, and the
# page's days; every click listener app.js registers is kept to be fired.
_VW_STATIC_HARNESS = r"""
require("./stub.js");
const fs = require("fs");
const heard = {window: {}, document: {}};
globalThis.addEventListener = (t, f) => (heard.window[t] = heard.window[t] || []).push(f);
document.addEventListener = (t, f) => (heard.document[t] = heard.document[t] || []).push(f);
const wrote = [];
history.replaceState = (st, t, u) => wrote.push(u);
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
location.pathname = fx.path; location.search = ""; location.hash = "";
const stubQ = document.querySelector;
const el = (o) => Object.assign({dataset: {}, innerHTML: "", hidden: false, attrs: {}, seen: 0,
  setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k] || null; },
  querySelectorAll: () => [], closest: () => null, scrollIntoView() { this.seen += 1; }}, o);
const section = el({});
const slot = el({dataset: {vwview: "gr-videos"},
  closest: (q) => q === ".chpane" ? (fx.data.kind === "chamber" ? {} : null) : q === "section" ? section : null});
const days = el({}), vids = el({hidden: true}), tabs = [el({}), el({})];
let strip = null;
const ctl = el({insertAdjacentHTML(w, h) { strip = w + " " + h; }});
document.querySelector = (q) => q === ".chamberctl" ? (fx.data.kind === "chamber" ? ctl : null)
  : q === ".chtabs" ? (strip ? {} : null) : q === "#chvids [data-vwview]" ? slot : stubQ(q);
document.querySelectorAll = (q) => q === "[data-vwview]" ? [slot] : q === ".chtabs .tab" && strip ? tabs
  : q === ".chdays > details" ? [el({}), el({}), el({})] : [];
document.getElementById = (id) => ({"gr-videos": el({textContent: JSON.stringify(fx.data)}),
  chdays: days, chvids: vids})[id] || null;
window.GR_STATIC = true;
const out = {};
let s = null;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({chamberVideos})"); }
catch (e) { out.threw = "app.js would not load: " + e.constructor.name + ": " + e.message; }
if (s) try {
  out.view = slot.innerHTML; out.strip = strip; out.tabs = tabs.map((t) => t.innerHTML);
  out.panes = [days.attrs.role, vids.attrs.role]; out.section = section.seen;
  if (fx.data.kind === "chamber") {
    // The Videos tab of the strip, clicked: every click listener hears it, and none may throw.
    const tab = {dataset: {chtab: "1"}};
    tab.closest = (q) => ["[data-chtab]", ".tab", ".tabs .tab"].includes(q) ? tab : null;
    out.errors = [];
    (heard.document.click || []).forEach((f) => { try { f({button: 0, detail: 1, target: tab,
      preventDefault() {}, stopPropagation() {}}); } catch (e) { out.errors.push(e.constructor.name + ": " + e.message); } });
    out.shown = [days.hidden, vids.hidden]; out.at = wrote.slice(-1)[0];
    // Another term, whose days lack the recording the address names: the address stops naming it.
    location.pathname = "/session/senate/videos"; location.search = "?term=2023-2024"; location.hash = "#v-gone";
    wrote.length = 0;
    s.chamberVideos({term: "2023-2024", days: [{date: "2023-03-02", videos: ["x2023"], counts: {bills: 3}}]});
    out.dropped = wrote.slice(); out.other = slot.innerHTML.includes('data-vwpick="x2023" aria-current="true"');
    out.tabsThen = tabs.map((t) => t.innerHTML);
  }
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").slice(0, 300); }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a chamber's and a study committee's Videos views are drawn when the page loads: "
       "the chamber's strip of two tabs, counted, each pane its tab's, a click on it heard without "
       "error; its script's order, term and Videos tab; a study committee's Videos tab in place",
       needs=("build_full_sessions",))
def _static_videos_wiring(FS):
    """The second review of the Videos views (29 October 2026) took each piece
    of the chamber's and the study committee's wiring out in turn and found
    preflight passed without it: app.js's call to staticVideos on a page that
    carries its own record, the chamber's strip (chamberStrip), the page
    script's Order select (which moved out of the term's box, so the script
    looking for it there threw on load and the order stopped working), the
    script handing another term to the Videos tab (GR_CHAMBER_TERM,
    chamberVideos), chamberVideos dropping a recording of the old term from
    the address, and the bill list's tab handler, which took the chamber's
    tabs for a card's and threw. Each is driven here as the page drives it:
    app.js loaded in node over a chamber's page and a study committee's, as
    their JSON stands in them, and the chamber page's own script run."""
    chamber = {"kind": "chamber", "body": "S", "slug": "senate", "term": "2025-2026", "latest": "2025-2026",
               "days": [{"date": "2026-02-19", "counts": {"bills": 1, "roll_calls": 1},
                         "summary": "The Senate took up 1 bill, with 1 roll call.",
                         "videos": ["senSessV001"],
                         "recordings": [{"id": "senSessV001", "began": "09:58", "seconds": 11040}]}]}
    # Its name in a sentence as the build gives it (build_study_committees,
    # named): a name that names no body is said bare.
    study = {"kind": "study", "who": "Administrative Rules", "what": "Administrative Rules",
             "key": "61", "path": "/committee/ss61",
             "rows": [{"id": "agingVid001", "date": "2026-03-10", "time": "10:00", "venue": "LOB 101",
                       "type": "Regular meeting", "anchor": "day-2026-03-10", "began": "10:02",
                       "seconds": 3720}]}
    got = _node_app(_VW_STATIC_HARNESS, {"fx.json": json.dumps({"path": "/session/senate", "data": chamber})})
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert "threw" not in got, "the chamber's page would not draw its Videos tab: " + got["threw"]
    assert 'data-embed="senSessV001|0|' in got["view"] and '<div class="vw"' in got["view"], (
        "app.js does not draw a chamber's Videos tab when the page loads (staticVideos)")
    # The chamber's page has its h1 and nothing under it is an h2 (page_head):
    # the list's heading is an h2, where an h3 skipped a level.
    assert '<h2 class="vwh" id="vwh">1 recording in 2025–2026</h2>' in got["view"], (
        "a chamber's list of recordings does not head the tab as an h2: "
        + (re.search(r"<h\d class=\"vwh\"[^>]*>", got["view"]) or [""])[0])
    # Drawn as the committee's h3 is: as an h2 it took the page's serif.
    assert re.search(r"\n\.vwh\{[^}]*font-family:var\(--sans\)", _source("src/pages/app.css")), (
        "app.css: a chamber's list heading, an h2, is not drawn in the committee's h3's face")
    strip = got["strip"] or ""
    assert strip.startswith("afterend ") and re.findall(r'<button class="tab" role="tab" id="chtab_(\d)" '
                                                         r'aria-controls="(\w+)" data-chtab="\1"', strip) == [
        ("0", "chdays"), ("1", "chvids")], f"the chamber's strip is not its two tabs under the term: {strip[:300]}"
    tn = lambda n: f'<span class="tn"><span class="tnp"> (</span>{n}<span class="tnp">)</span></span>'
    assert got["tabs"] == ["Session Days" + tn(3), "Videos" + tn(1)] and got["panes"] == ["tabpanel"] * 2, (
        f"the chamber's tabs read {got['tabs']}, its panes {got['panes']}")
    assert got["errors"] == [] and got["shown"] == [True, False] and got["at"] == "/session/senate/videos", (
        f"the chamber's Videos tab, clicked, throws in a listener ({got['errors']}) or is not shown, its "
        f"address its own: panes hidden {got['shown']}, address {got['at']}")
    assert got["dropped"] == ["/session/senate/videos?term=2023-2024"] and got["other"] and \
        got["tabsThen"] == ["Session Days" + tn(1), "Videos" + tn(1)], (
            f"another term's Videos tab is not drawn, or the address goes on naming the old term's "
            f"recording: {got['dropped']}, {got['tabsThen']}")
    st = _node_app(_VW_STATIC_HARNESS, {"fx.json": json.dumps({"path": "/committee/ss61/videos", "data": study})})
    assert "threw" not in st, "the study committee's page would not draw its Videos tab: " + st["threw"]
    assert 'data-embed="agingVid001|0|' in st["view"] and st["strip"] is None and st["section"] == 0 and \
        'aria-label="Play the recording of Administrative Rules, Mar 10, 2026"' in st["view"] and \
        'data-title="Recording of Administrative Rules, Mar 10, 2026"' in st["view"] and \
        '<h3 class="vwh" id="vwh">' in st["view"], (
            "app.js does not draw a study committee's Videos tab when the page loads, in its words, "
            "or scrolls the page to it at /videos, where its tab is shown as a standing committee's is")
    # THE PAGE'S OWN SCRIPT: its Order select is under Session Days now, out of
    # the term's box; another term fetched goes to the Videos tab.
    js = re.search(r"<script>(.*?)</script>", FS.SCRIPT, re.S).group(1)
    term = {"term": "2023-2024", "days": [{"date": "2023-03-02", "counts": {"bills": 3}},
                                          {"date": "2023-01-05", "counts": {"bills": 2}}]}
    ran = _node_app(r"""
const fs = require("fs");
globalThis.window = globalThis;
const T = JSON.parse(fs.readFileSync("./term.json", "utf8"));
const calls = [];
globalThis.chamberVideos = (t) => calls.push(t);
const on = {};
const term = {value: "2025-2026", options: [{value: "2025-2026"}, {value: "2023-2024"}],
  addEventListener(t, f) { on.term = f; }};
const sort = {value: "new", addEventListener(t, f) { on.sort = f; }};
const ctl = {dataset: {body: "S"}, querySelector: (q) => q === ".chterm" ? term : null};
const kids = [];
const list = {get children() { return kids.slice(); }, appendChild() {}, setAttribute() {}, removeAttribute() {},
  set innerHTML(h) { kids.length = 0; (h.match(/data-date="[^"]*"/g) || []).forEach((m) =>
    kids.push({dataset: {date: m.slice(11, -1)}})); }, get innerHTML() { return ""; }};
const count = {innerHTML: "", textContent: ""};
globalThis.document = {querySelector: (q) => ({".chamberctl": ctl, ".chsort": sort, ".chdays": list,
  ".chcount": count})[q] || null, getElementById: () => null};
globalThis.location = {search: "?term=2023-2024", pathname: "/session/senate", hash: ""};
globalThis.history = {replaceState() {}};
globalThis.fetch = async () => ({ok: true, json: async () => T});
const out = {};
(async () => {
  try {
    (0, eval)(fs.readFileSync("./script.js", "utf8"));
    for (let i = 0; i < 8; i++) await new Promise((r) => setImmediate(r));
    out.handed = calls.length === 1 && calls[0] === T && window.GR_CHAMBER_TERM === T;
    out.newest = count.innerHTML;
    sort.value = "old"; on.sort();
    out.oldest = count.innerHTML;
  } catch (e) { out.threw = e.constructor.name + ": " + e.message; }
  process.stdout.write("\n@@" + JSON.stringify(out));
})();
""", {"script.js": js, "term.json": json.dumps(term)})
    assert "threw" not in ran, "the chamber page's script throws: " + ran["threw"]
    assert ran["handed"], "the chamber page's script does not hand another term to the Videos tab"
    assert ran["newest"].startswith("2 days the Senate sat in 2023-2024, newest first") and \
        ran["oldest"].startswith("2 days the Senate sat in 2023-2024, oldest first"), (
            f"the chamber page's Order does not order its days: {ran['newest'][:80]!r}, then {ran['oldest'][:80]!r}")
    return "ok", ("a chamber's Videos tab and strip drawn on load, counted, each pane its tab's, a click on "
                  "it heard without error, another term's drawn and the old recording dropped from the "
                  "address; the page's script orders its days and hands another term over; a study "
                  "committee's Videos tab drawn in its words, the page left where it is")


@check("frontend", "the House seating chart is drawn with the rostrum at the top and Division 1 to 5 from left to right, every word upright")
def _seat_chart_turned():
    """"Maybe the seating chart diagram can be rotated 180 degrees so that the
    divisions can be listed in ascending order left to right since descending
    order is a bit confusing" (the person, 7 October 2026). seating.py reads
    the Clerk's plan, which puts the rostrum at the foot and runs the
    divisions 5 to 1, and turns every place it draws half a circle about the
    Speaker (_point).

    Held on the chart seating.svg draws and on the fixture's built page: the
    Speaker above every seat on the floor; each division's seats, on average,
    to the right of the one before, 1 to 5 -- on average, because the blocks
    overlap sideways; the seats written in the order of their numbers, which
    is the order the arrow keys walk, so Right goes on toward Division 5; and
    every caption laid on an arc centred on the Speaker, run left to right
    and swept under it, so its word stands the right way up rather than being
    turned with the chart -- and "Speaker" above its seat, inside the
    drawing."""
    import seating
    pos = seating.layout()
    sy = pos[seating.SPEAKER_SEAT][1]
    floor = {s: p for s, p in pos.items() if s != seating.SPEAKER_SEAT}
    low = [s for s, (_x, y) in floor.items() if y <= sy]
    assert not low, f"seats {sorted(low)[:5]} are drawn level with or above the Speaker"
    mean = {d: sum(x for s, (x, _y) in floor.items() if s // 1000 == d)
            / sum(1 for s in floor if s // 1000 == d) for d in sorted(seating.HIGHEST)}
    order = sorted(mean, key=mean.get)
    assert order == [1, 2, 3, 4, 5], (
        f"the divisions run {order} from left to right on the chart")
    who = {s: {"name": f"Member {s}", "slug": f"m{s}", "party_code": "R"}
           for s in seating.all_seats() + [seating.SPEAKER_SEAT]}
    drawn = seating.svg(who)

    def upright(svg):
        bad = []
        cx, cy = [float(v) for v in re.search(
            r'<circle class="seat rostrum[^"]*" cx="([\d.]+)" cy="([\d.]+)"', svg).groups()]
        for d, path in re.findall(r'<path id="divarc(\d)" d="([^"]+)"', svg):
            x1, y1, r, _r, _rot, _big, sweep, x2, y2 = [
                float(v) for v in re.findall(r"-?[\d.]+", path)]
            # An arc about the Speaker, run left to right and swept below
            # the rostrum: a letter stands on its path's left, which is up.
            if not (x1 < x2 and sweep == 0 and abs(math.hypot(x1 - cx, y1 - cy) - r) < 1.5
                    and min(y1, y2) > cy):
                bad.append(f"Division {d}'s caption runs {path}")
        sp = re.search(r'<text class="rostrumtext" x="[\d.]+" y="([\d.]+)"', svg)
        if not (sp and 0 < float(sp.group(1)) < cy):
            bad.append(f"\"Speaker\" is not above its seat at y={cy}")
        return bad
    bad = upright(drawn)
    assert not bad, "; ".join(bad)
    seen = [int(s) for s in re.findall(r'<circle class="seat[^"]*" [^>]*data-seat="(\d+)"', drawn)]
    assert seen == sorted(seen) == seating.all_seats(), (
        "the chart does not write its seats in the order of their numbers, which is the order "
        "the arrow keys walk")
    shared, _base, _ran, _days = _fixture_site_shared()
    page = (shared / "site" / "officials.html").read_text(encoding="utf-8")
    svg = re.search(r'<svg viewBox="[^"]+" class="seatmap".*?</svg>', page, re.S)
    assert svg, "the fixture's legislators page draws no seating chart"
    bad = upright(svg.group(0))
    assert not bad, "on the built page: " + "; ".join(bad)
    # THE READOUT IS UNDER THE FLOOR, NOT ON IT (the review of 7 October
    # 2026). Turned, the foot of the box is Division 3's back rows and its
    # caption, and the strip that names a member was laid over it: wherever
    # the box is shorter than the drawing -- 1366 by 900 -- it covered
    # "Division 3". The note is the stage's last row, after the scrolling
    # floor and in the flow, and it keeps its line when empty, so naming a
    # member moves nothing on the page.
    assert re.search(r'<div class="seatstage">\s*<div class="seatwrap"><svg [^>]*class="seatmap"'
                     r'.*?</svg></div>\s*<p class="seatnote" id="seatnote"', page, re.S), (
        "the readout is not the chart's stage's next row after its scrolling floor")
    css = re.sub(r"/\*.*?\*/", "", _source("src/pages/app.css"), flags=re.S)
    on_screen = re.sub(r"@media print\{(?:[^{}]*\{[^{}]*\})*\s*\}", "", css)
    note = [(sel.strip(), body) for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", on_screen)
            if ".seatnote" in sel]
    over = [sel for sel, body in note
            if re.search(r"position:(absolute|fixed|sticky)|display:none|pointer-events:none", body)]
    assert not over, f"the readout is laid over the floor or dropped when empty: {over}"
    own = [body for sel, body in note if sel == ":where(body.pg) .seatnote"]
    assert len(own) == 1 and "min-height:calc(1lh + 2 * var(--sp-3) + 2px)" in own[0], (
        "the readout's row is not one line high whether or not it names anyone")
    return "ok", ("the rostrum at the top, Division 1 to 5 from left to right at mean x "
                  + ", ".join(f"{mean[d]:.0f}" for d in order)
                  + ", the seats in number order for the arrow keys, five captions and "
                    "\"Speaker\" upright, on the chart and on the built page, and the readout "
                    "a row under the floor")


@check("frontend", "a session day's moment for a bill carries what the chamber did to it that day, as the "
                   "vote's chip with the counted tally, and nothing where the day recorded no outcome")
def _session_moment_says_the_vote():
    """The owner, 8 November 2026: on a session day's page the moment of each
    bill in the floor recording says, beside the time, what happened to it:
    the chip and "(202–169)", the shape the home page's Latest activity
    gives a report (build_pages.did_html). From the day's own votes only
    (build_session_pages.did_chip, the same `deciding` the day's index reads);
    a voice vote has a chip and no tally."""
    import types
    sys.path.insert(0, str(Path("src/pages").resolve()))
    import build_session_pages as BS
    vote = lambda action, carried, y, n: types.SimpleNamespace(
        action=action, carried=carried, yeas=y, nays=n, counted=y is not None)
    chip_ = BS.did_chip([vote("Inexpedient to Legislate", True, 202, 169)], "HB1", "H")
    assert "Motion Passed: Bill Killed" in chip_ and '<span class="latvote">(202–169)</span>' in chip_, (
        f"a counted floor vote is not said with its tally: {chip_!r}")
    failed = BS.did_chip([vote("Ought to Pass", False, 150, 190)], "HB1", "H")
    assert "Motion Failed" in failed and "(150–190)" in failed, f"a failed vote is not said: {failed!r}"
    voice = BS.did_chip([vote("Ought to Pass", True, None, None)], "HB1", "H")
    assert "Motion Passed" in voice and "latvote" not in voice, f"a voice vote carries a tally: {voice!r}"
    assert BS.did_chip([], "HB1", "H") == "", "a day with no vote says something"
    m = BS.moment_html({"v": "abc", "from": 65, "end": 90, "s": "floor_precise"}, "2026-02-12",
                       lambda x: x, chip_)
    assert m.index('class="jump"') < m.index('class="mdid"') and "(202–169)" in m, (
        "the day's moment does not carry the outcome beside its time")
    assert 'class="mdid"' not in BS.moment_html({"v": "abc", "from": 65}, "2026-02-12", lambda x: x), (
        "a moment with no outcome draws an empty one")
    return "ok", "a day's moment carries the vote's chip and counted tally, none for a voice vote or a day without one"


# THE CHAIR'S OFFICERS AS THE RECORD STATES THEM (the person, 9 October 2026),
# each excerpt as it stands in its file: the House's organization day of
# 4 December 2024 (HJ 1) with the Senate's message, the Senate's own (SJ 1),
# the sitting of 8 May 2025 the Deputy Speaker opened (HJ 14), the House
# Calendar's notices of 9 December 2022 (HC 2), 29 May 2026 (HC 22) and
# 31 July 2026 (HC 28), and 1997's list that names the title after the name
# (HC 13), which read the other way round made Rep. Brown Deputy Speaker.
# And the Senate's of 2012-2013, whose clerk wrote the office small: Senator
# Bragdon elected "president of the New Hampshire Senate" on 5 December 2012
# (SJ 1), and on 3 September 2013 resigning it and Senator Morse elected in
# his place (SJ 17). Read with a capital only, both were missed, and
# officers.json published Senator Bragdon as President until December 2014
# (the review of 9 October 2026).
_OFFICERS_FILES = {
    "journals_senate/2013/SJ 01 December 5, 2012 Organization Day.txt": """
                                                                                                              December 5, 2012

        STATE OF NEW HAMPSHIRE

Sen. Bradley nominated the Honorable Peter Bragdon for the president of the New Hampshire senate.

Sen. Larsen seconded the nomination.

Hearing no further nominations, Senator Odell declared nominations to be closed.

Adopted. The Honorable Peter Bragdon was elected president of the New Hampshire Senate.
""",
    "journals_senate/2013/SJ 17 September 3, 2013.txt": """
                                                                                                                  September 3, 2013
                                                                                                                  Nos. 16-17

Senate President Peter Bragdon resigned from the position of President of the New Hampshire Senate.

Senator Bragdon passed the gavel to President Pro Tem, Senator Bob Odell.

Adopted. The Honorable Chuck Morse was elected president of the New Hampshire Senate.

Senator Odell, President Pro Tem, requested Senators Rausch and D'Allesandro to escort The Honorable
Chuck Morse, President of the New Hampshire Senate, to the rostrum.
""",
    "journals/2025/HJ 01 December 4, 2024.txt": """
              HOUSE JOURNAL NO. 1

                              Wednesday, December 4, 2024

                                                        ELECTION OF SPEAKER
The Chair declared that nominations for Speaker were in order.
Rep. Weber placed the name of Rep. Alexis Simpson in nomination for Speaker and addressed the House.
Rep. Mazur placed the name of Rep. Sherman Packard in nomination for Speaker and addressed the House.
Of the 388 votes cast, 195 were needed for election. Rep. Simpson received 162 votes and Rep. Packard re-
ceived 202 votes. There were 7 blank votes and 17 scatter votes. The Chair declared Rep. Sherman Packard
the duly elected Speaker of the House for the 2025-2026 biennium.

The Acting Sergeant-at-Arms escorted Speaker Packard to the rostrum. The Speaker addressed the House.

                                                           SENATE MESSAGE
The Senate has organized, has elected its officers and is ready to meet with the House of Representatives in
Joint Convention for the purpose of electing a Secretary of State and a State Treasurer.
President of the Senate: Senator Sharon M. Carson
Clerk of the Senate: Tammy Wright
""",
    "journals/2025/HJ 14 May 8, 2025.txt": """
             HOUSE JOURNAL NO. 14

                                    Thursday, May 8, 2025

The House assembled at 10:00 a.m., the hour to which it stood adjourned, and was called to order by the
Deputy Speaker.

                                                          MEMORIAL REMARKS
Deputy Speaker Steven Smith: So, I shared an office with Norm for two years. I didn't know him well
when that started and I viewed him as a serious man, a confident man, a respected man and somebody I
""",
    "journals_senate/2025/SJ 01 December 4, 2024 Organization Day.txt": """
4  SENATEJOURNAL4DECEMBER2024

Hearing no further nominations, the Clerk declared nominations to be closed.

Adopted. Senator Sharon M. Carson was elected President of the Senate.

The Honorable Tammy L. Wright, Clerk of the Senate, requested Senator Birdsell to escort Senator Sharon
M. Carson, President of the Senate, to the rostrum.
""",
    "calendars/2023/HC002.txt": """
 Vol.45         Concord,N.H.  Friday,December9,2022                               No.2X
I have made appointments to my Speaker's Office leadership team. Rep. Steve Smith of Charlestown has been
reappointed as Deputy Speaker. Rep. Laurie Sanborn of Bedford has been appointed Speaker Pro Tempore.
Rep. Steve Shurtleff of Penacook has been appointed Speaker Emeritus.
""",
    "calendars/2026/HC022.txt": """
 Vol.48         Concord,N.H.  Friday,May29,2026                            No.22X
Senators and Members of the House are invited to attend a Taiwan Friendship Breakfast hosted by the Taipei
Economic and Cultural Office (TECO) in Boston and sponsored by Speaker Packard, Speaker Pro Tem Kofalt, and
Senate President Carson. The event will be held on Thursday, June 4, 2026, from 8:00 a.m. to 10:00 a.m. in
""",
    "calendars/2026/HC028.txt": """
 Vol.48         Concord,N.H.  Friday,July31,2026                           No.28X
Please join me in mourning the loss of our former colleague Fred Doucette, who served as Speaker Pro Tem
earlier this term. His contributions to the State of New Hampshire and his unwavering dedication to public
""",
    "calendars/1997/HC013.txt": """
                                                Vol. 19 Concord N.H. Friday, January 24, 1997 No. 13
I would like to take this opportunity to present the House leadership team for the 155th session of the General Court.
House Leadership
Donnalee Lozeau Deputy Speaker
Channing T. Brown Speaker Pro Tempore
Majority Leadership
""",
}


def _officers_fixture(OF, hand=None):
    """officers.load() over _OFFICERS_FILES laid out in a folder of its own,
    with `hand` as corrections/officials.json's legislative_officers."""
    root = Path(tempfile.mkdtemp())
    try:
        for name, text in _OFFICERS_FILES.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding="utf-8")
        if hand is not None:
            (root / "corrections").mkdir()
            (root / "corrections" / "officials.json").write_text(
                json.dumps({"governor": {}, "legislative_officers": {"entries": hand}}),
                encoding="utf-8")
        return OF.load(root / "journals", root / "journals_senate", root / "calendars",
                       root / "corrections" / "officials.json")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("session", "the chair's officers come from the record, and a turn in the chair is "
                  "headed by the office held that day", needs=("officers",))
def _officers_from_the_record(OF):
    """The House Journal heads whoever is in the chair "Speaker": "Speaker
    Steven Smith:" 251 times in 2025-2026, "Speaker Kofalt:" 59, beside
    "Speaker Packard:" 428, and the sitting pages printed it as it stood
    (the person, 9 October 2026: "he is the deputy speaker and sometimes
    fills in for Sherman Packard if he has other business, as does Jim
    Kofalt occasionally as speaker pro temp"). officers.py reads who held
    each office from the journals and calendars. Real rows: Speaker Packard,
    elected 4 December 2024 (HJ 1); Senator Carson, elected President of the
    Senate that day (SJ 1, and the Senate's message in HJ 1); Rep. Steven
    Smith, the Deputy Speaker the journal names on 8 May 2025, a day he
    presided over roll calls 182-192; Rep. Kofalt, in the chair on 10 April
    2025 (HJ 12, "(Rep. Kofalt in the Chair)"), whom the record names
    Speaker Pro Tem only on 29 May 2026, after "Fred Doucette, who served as
    Speaker Pro Tem earlier this term" -- so the record does not say when
    the office changed hands, and his turn in the chair that day is "Rep.
    Kofalt, in the chair" unless a person's entry says from when. And the
    Senate's of 2012-2013, its clerk writing "elected president of the New
    Hampshire Senate": Senator Bragdon President from 5 December 2012 until
    3 September 2013, the day he resigned it and Senator Morse was elected
    (the review of 9 October 2026, which found Bragdon held to December
    2014)."""
    tens, ms, bad = _officers_fixture(OF)
    assert not bad, bad
    got = {(t["body"], t["title"], t["name"], t["from"], t["to"], t["kind"]) for t in tens}
    for want in [("H", "Speaker", "Sherman Packard", "2024-12-04", "2026-12-02", "elected"),
                 ("S", "President", "Sharon M. Carson", "2024-12-04", "2026-12-02", "elected"),
                 ("H", "Deputy Speaker", "Steven Smith", "2024-12-04", "2026-12-02", "term"),
                 ("H", "Deputy Speaker", "Steve Smith", "2022-12-07", "2024-12-04", "term"),
                 ("H", "Speaker Pro Tempore", "Laurie Sanborn", "2022-12-07", "2024-12-04", "term"),
                 ("H", "Speaker Pro Tempore", "Kofalt", "2026-05-29", "2026-05-30", "day"),
                 # The office written small (SJ 1 of 2012, SJ 17 of 2013): Senator
                 # Bragdon until the day he resigned it, Senator Morse from then.
                 ("S", "President", "Peter Bragdon", "2012-12-05", "2013-09-03", "elected"),
                 ("S", "President", "Chuck Morse", "2013-09-03", "2014-12-03", "elected")]:
        assert want in got, f"no tenure {want}; read: {sorted(got)}"
    assert not any("Brown" in t["name"] or "Lozeau" in t["name"] for t in tens), (
        "1997's list, which gives the title after the name, was read the other way round: "
        + str([t for t in tens if t["from"] < "1998"]))
    carson = next(t for t in tens if t["title"] == "President" and t["from"] == "2024-12-04")
    assert carson["source"].startswith("journals_senate/") or "journals_senate" in carson["source"], (
        "the President's election is cited from the House's message, not the Senate's journal: "
        + carson["source"])
    lab = lambda who, day: OF.chair_label(who, day, tens)  # noqa: E731
    assert lab("Speaker Packard", "2025-05-08") == "Speaker Packard"
    assert lab("Speaker Steven Smith", "2025-05-08") == "Deputy Speaker Steven Smith", (
        lab("Speaker Steven Smith", "2025-05-08"))
    assert lab("Speaker Stevn Smith", "2026-04-23") == "Deputy Speaker Stevn Smith"
    assert lab("Speaker Kofalt", "2025-04-10") == "Rep. Kofalt, in the chair", (
        lab("Speaker Kofalt", "2025-04-10"))
    assert lab("Speaker Pro Tempore Weber", "2025-04-10") == "Speaker Pro Tempore Weber"
    assert lab("Rep. Edwards", "2025-04-10") == "Rep. Edwards"
    # A day the record names no Speaker for keeps the journal's heading.
    assert lab("Speaker Kofalt", "2003-04-10") == "Speaker Kofalt"
    now = {k: t["name"] for k, t in OF.holders(tens, ms, "2026-10-09").items()}
    assert now == {("H", "Speaker"): "Sherman Packard", ("S", "President"): "Sharon M. Carson",
                   ("H", "Deputy Speaker"): "Steven Smith",
                   ("H", "Speaker Pro Tempore"): "Kofalt"}, now
    # Named as a member of that chamber that term, and only one: Rep. Steven
    # Smith and not Rep. Geoffrey Smith.
    people = {("H", "2025-2026"): {"425": "Packard, Sherman", "656": "Smith, Steven",
                                   "10905": "Smith, Geoffrey", "9895": "Kofalt, Jim"},
              ("S", "2025-2026"): {"35": "Carson, Sharon"}}
    rows, _missed = OF.resolve(tens, people)
    ids = {(r["title"], r["from"]): r["member_id"] for r in rows if r["from"] >= "2024"}
    assert ids == {("Speaker", "2024-12-04"): "425", ("President", "2024-12-04"): "35",
                   ("Deputy Speaker", "2024-12-04"): "656",
                   ("Speaker Pro Tempore", "2026-05-29"): "9895"}, ids
    # A person's entry gives the day the record does not; one that does not
    # hold together is reported and left out.
    hand = [{"chamber": "H", "title": "Speaker Pro Tempore", "name": "Jim Kofalt",
             "member_id": "9895", "from": "2025-03-13", "source": "the site's author"},
            {"chamber": "H", "title": "Speaker Pro Tempore", "name": "Nobody",
             "from": "2025-03-13"}]
    tens2, _ms2, bad2 = _officers_fixture(OF, hand)
    assert [why for _e, why in bad2] == ["no source"], bad2
    assert OF.chair_label("Speaker Kofalt", "2025-04-10", tens2) == \
        "Speaker Pro Tempore Kofalt", OF.chair_label("Speaker Kofalt", "2025-04-10", tens2)
    return "ok", ("Speaker Packard and President Carson from 4 December 2024; on 8 May 2025 "
                  "\"Deputy Speaker Steven Smith\"; on 10 April 2025 \"Rep. Kofalt, in the "
                  "chair\", and \"Speaker Pro Tempore Kofalt\" with a person's entry")


@check("data", "no House sitting heads anyone but that day's Speaker \"Speaker\", and "
               "every other office it names in the chair is one held that day",
       needs=("officers",))
def _chair_headings_on_the_site(OF):
    """The House Journal heads whoever is in the chair "Speaker", and the
    sitting pages printed it: "Speaker Steven Smith" on 33 sittings of
    2021-2026, the Deputy Speaker (the person, 9 October 2026). Every built
    House sitting page is read here: a turn headed "Speaker <name>" must be
    the Speaker that site/officers.json says held the office that day, or
    a day it names no Speaker for; and the Deputy Speaker's turns of
    8 May 2025 are headed so.

    AND EVERY OTHER HEADING OF THE CHAIR (the review of 9 October 2026, which
    found the first form of this check passed a build that called Rep.
    Kofalt "Deputy Speaker" and one that demoted the Speaker to "Rep.
    Packard, in the chair", since it read only the headings that still
    began "Speaker"): a turn headed "Deputy Speaker <name>" or "Speaker Pro
    Tempore <name>" must be a member officers.json gives that office that
    day, and one headed "<name>, in the chair" must be neither that day's
    Speaker nor a member officers.json gives another office that day -- who
    would then have been titled by it."""
    import html as _h
    days, of = Path("site/session/H"), Path("site/officers.json")
    if not (days.is_dir() and of.exists()):
        return "skip", "site/session/H or site/officers.json is not here"
    tens = [t for t in json.loads(of.read_text(encoding="utf-8")).get("officers") or []
            if t["b"] == "H"]
    head = re.compile(r'<p class="sdsp"><span>([^<]+)</span>')
    wrong, n, retitled = [], 0, 0
    for f in sorted(days.glob("*.html")):
        iso = f.stem
        on = [t for t in tens if t["from"] <= iso < t["to"]]
        here = [t for t in on if t["title"] == "Speaker"]
        for who in head.findall(f.read_text(encoding="utf-8")):
            who = _h.unescape(who)
            office = re.match(r"(Deputy Speaker|Speaker Pro Tempore) (.+)$", who)
            member = re.match(r"(?:Rep\. )?(.+), in the chair$", who)
            if office:
                retitled += 1
                if not any(t["title"] == office.group(1)
                           and OF.same_person(t["name"], office.group(2)) for t in on):
                    wrong.append(f"{iso}: {who} (officers.json gives nobody of that name "
                                 "that office that day)")
                continue
            if member:
                retitled += 1
                held = [t["title"] for t in on if OF.same_person(t["name"], member.group(1))]
                if held:
                    wrong.append(f"{iso}: {who} (the {held[0]} that day)")
                continue
            m = re.match(r"Speaker (?!Pro Tem)(.+)$", who)
            if not m or not here:
                continue
            n += 1
            if not any(OF.same_person(t["name"], m.group(1)) for t in here):
                wrong.append(f"{iso}: {who}")
    assert not wrong, (f"{len(wrong)} turn(s) in the chair headed by an office not held "
                       f"that day: " + "; ".join(wrong[:6]))
    may8 = days / "2025-05-08.html"
    if may8.exists():
        assert "<span>Deputy Speaker Steven Smith</span>" in may8.read_text(encoding="utf-8"), (
            "8 May 2025: the Deputy Speaker's turns in the chair are not headed so")
    return "ok", (f"{n:,} turns headed \"Speaker\", each that day's Speaker; {retitled:,} "
                  "headed by another office or as a member in the chair")


@check("session", "a session day's summary says what the chamber did in general and names no bill",
       needs=("build_session_pages",))
def _day_summary_words(BSP):
    """The chamber's page lists each day with "a brief summary of what the
    house did that day but don't display the bill numbers" (the person, 10
    October 2026): day_summary, from the day record's own counts, consent
    calendar, presiding officer and excused."""
    rec = {"counts": {"bills": 47, "roll_calls": 12, "divisions": 1, "voice_votes": 30},
           "consent": {"bills": 25, "outcomes": [{"outcome": "Killed", "bills": 7},
                                                 {"outcome": "Passed", "bills": 18}],
                       "removed": ["HB1", "HB2"]},
           "presiding": [{"label": "Rep. Sherman Packard (R - Rock 5)", "roll_calls": 12}],
           "excused": {"total": 27}}
    got = BSP.day_summary(rec, "H")
    want = ("The House took up 47 bills, with 12 roll calls, 1 division vote and 30 voice votes. "
            "Its consent calendar held 25 bills: 7 killed and 18 passed; 2 bills were taken off it. "
            "Rep. Sherman Packard (R - Rock 5) presided. 27 members were excused for the day.")
    assert got == want, got
    assert not re.search(r"\b[HS]B ?\d", got), "the summary names a bill"
    assert BSP.day_summary({"counts": {"bills": 1}}, "S") == "The Senate took up 1 bill."
    return "ok", "a day in counts, its consent calendar by outcome, who presided and who was excused"


@check("session", "a member who sat in the other chamber is matched there in the terms they sat in it",
       needs=("build_session_pages",))
def _speaker_other_chamber(BSP):
    """The dry run of e82bd06 left "H Rosenwald" as words 177 times: Sen. Cindy
    Rosenwald sat in the House from 2005 to 2018, and a member was filed only
    under the chamber of their own row. careers.json gives each term's
    chamber; she is matched on a House day of 2017 and not on one of 2021,
    when the House had no Rosenwald."""
    root = Path(tempfile.mkdtemp(prefix="gr-chambers-"))
    keep = BSP._careers
    try:
        # The real shape: the roster's id is the PersonID (9406), careers.json
        # is keyed by employee number (209106) and carries the PersonID inside
        # -- the dry run of 3b43bf7 matched nobody while this test used one
        # number for both.
        (root / "legislators.json").write_text(json.dumps([
            {"id": "9406", "slug": "cindy-rosenwald-13", "name": "Rosenwald, Cindy", "chamber": "S"}]),
            encoding="utf-8")
        (root / "former.json").write_text("[]", encoding="utf-8")
        real = {"209106": {"person_id": "9406", "employee_nos": ["209106", "376622"],
                           "by_term": {"2017-2018": {"chambers": ["H"]},
                                       "2021-2022": {"chambers": ["S"]}}}}
        careers_file = root / "careers.json"
        careers_file.write_text(json.dumps(real), encoding="utf-8")
        here = Path.cwd()
        (root / "generated").mkdir()
        careers_file.rename(root / "generated" / "careers.json")
        import os as _os
        _os.chdir(root)
        try:
            table = keep()
        finally:
            _os.chdir(here)
        BSP._careers = lambda: table
        m = BSP.Members(root)
        m.term = "2017-2018"
        then = m.slug("H", "Rosenwald")
        m.term = "2021-2022"
        later = m.slug("H", "Rosenwald")
        senate = m.slug("S", "Rosenwald")
    finally:
        BSP._careers = keep
        shutil.rmtree(root, ignore_errors=True)
    assert then == "cindy-rosenwald-13", f"Rosenwald on a House day of 2017 is {then!r}"
    assert later is None, f"Rosenwald matched on a House day of 2021, when she sat in the Senate: {later!r}"
    assert senate == "cindy-rosenwald-13"
    return "ok", "Rosenwald on a House day of 2017; nobody of that name on one of 2021"


@check("session", "a former member whose one page joins both chambers is matched in each chamber "
       "in the terms they sat in it, so a namesake does not take their days",
       needs=("build_session_pages",))
def _joined_mover_session_days(BSP):
    """THE DEEP WALK OF 6 NOVEMBER 2026, on dry run 181's preview: 44 House
    session days named the wrong member. A former member who sat in both
    chambers has one page, filed under one chamber, and the pass for the
    other chamber read careers.json under the page's own number only, while
    the other chamber's years are under the number joined to it. So
    Frederick King's House years (2003-2008) and Melanie Levesque's
    (2007-2014) counted nowhere in the House. Every "Rep. King" of them went
    to Seth King and every "Rep. Levesque" to Cassandra Levesque, sitting
    members, the only ones of those names left. "Rep. Jeb Bradley" went to
    Paula Bradley, though the journal gave the first name.

    Here: King's page under the House (as fix/movers-term keeps it) and
    Levesque's under the Senate, each joined to their other number, and a
    sitting namesake of each, careers.json in its real shape. Each is
    matched in each chamber in the terms they sat in it, the namesakes in
    theirs, and nobody in a term where neither King sat.

    And the review of that night: a joined page whose numbers careers.json
    does not hold (Leo Fraser here) counts in its page's terms, not in every
    term and not in none; and a sitting senator's House number, in her
    member_ids (Tara Reardon, House 1999-2010), files her under the House in
    those terms, as six sitting senators are on the real record."""
    root = Path(tempfile.mkdtemp(prefix="gr-joined-"))
    keep = BSP._careers
    try:
        (root / "legislators.json").write_text(json.dumps([
            {"id": "11001", "slug": "seth-king-coos-4", "name": "King, Seth", "chamber": "H"},
            {"id": "11002", "slug": "cassandra-levesque-straf-4", "name": "Levesque, Cassandra",
             "chamber": "H"},
            {"id": "11003", "slug": "marilyn-fraser-merr-1", "name": "Fraser, Marilyn", "chamber": "H"},
            {"id": "11461", "slug": "tara-reardon-sd-15", "name": "Reardon, Tara", "chamber": "S",
             "member_ids": ["11461", "376162"]}]), encoding="utf-8")
        (root / "former.json").write_text(json.dumps([
            {"id": "376486", "slug": "frederick-king-coos-1", "name": "King, Frederick", "chamber": "H",
             "member_ids": ["376486", "205005"],
             "served": {"terms": ["1999-2000", "2003-2004", "2005-2006", "2007-2008"]}},
            {"id": "9405", "slug": "melanie-levesque-sd-12", "name": "Levesque, Melanie", "chamber": "S",
             "member_ids": ["9405", "376690"],
             "served": {"terms": ["2007-2008", "2013-2014", "2019-2020"]}},
            {"id": "371138", "slug": "leo-fraser-merr-37", "name": "Fraser, Leo", "chamber": "H",
             "member_ids": ["371138", "202333"],
             "served": {"terms": ["1999-2000", "2001-2002", "2003-2004"]}}]), encoding="utf-8")
        table = {"376486": {"by_term": {t: {"chambers": ["H"]}
                                        for t in ("2003-2004", "2005-2006", "2007-2008")}},
                 "205005": {"by_term": {"1999-2000": {"chambers": ["S"]}}},
                 "209108": {"person_id": "9405", "employee_nos": ["209108"],
                            "by_term": {"2019-2020": {"chambers": ["S"]}}},
                 "376690": {"by_term": {t: {"chambers": ["H"]} for t in ("2007-2008", "2013-2014")}},
                 "218765": {"person_id": "11461", "employee_nos": ["218765"],
                            "by_term": {"2025-2026": {"chambers": ["S"]}}},
                 "376162": {"by_term": {t: {"chambers": ["H"]} for t in ("1999-2000", "2001-2002")}}}
        (root / "generated").mkdir()
        (root / "generated" / "careers.json").write_text(json.dumps(table), encoding="utf-8")
        import os as _os
        here = Path.cwd()
        _os.chdir(root)
        try:
            careers = keep()
        finally:
            _os.chdir(here)
        BSP._careers = lambda: careers
        m = BSP.Members(root)
        got = {}
        for term, body, said in (("2005-2006", "H", "Frederick King"), ("1999-2000", "S", "King"),
                                 ("2025-2026", "H", "King"),
                                 ("2013-2014", "H", "Melanie Levesque"), ("2019-2020", "S", "Levesque"),
                                 ("2025-2026", "H", "Levesque"),
                                 ("2003-2004", "H", "Leo Fraser"), ("2025-2026", "H", "Fraser"),
                                 ("2001-2002", "H", "Tara Reardon"), ("2025-2026", "S", "Reardon")):
            m.term = term
            got[(term, body, said)] = m.slug(body, said)
        # The page's own chamber counts its own terms only: King sat in the
        # Senate in 1999-2000, and is no House King of it.
        m.term = "1999-2000"
        house_1999 = m.serving(m.by_last.get(("H", "king"), []))
        # The bare surname where the namesake also sits: the term's ballots
        # say which King voted that term (by_ballot), as on a real night.
        m.term, m.ballots = "2005-2006", {"2005-2006": {"376486": "Rep. Frederick King (R - Coos 1)"}}
        got[("2005-2006", "H", "King")] = m.slug("H", "King")
    finally:
        BSP._careers = keep
        shutil.rmtree(root, ignore_errors=True)
    want = {("2005-2006", "H", "Frederick King"): "frederick-king-coos-1",
            ("1999-2000", "S", "King"): "frederick-king-coos-1",
            ("2025-2026", "H", "King"): "seth-king-coos-4",
            ("2013-2014", "H", "Melanie Levesque"): "melanie-levesque-sd-12",
            ("2019-2020", "S", "Levesque"): "melanie-levesque-sd-12",
            ("2025-2026", "H", "Levesque"): "cassandra-levesque-straf-4",
            ("2005-2006", "H", "King"): "frederick-king-coos-1",
            # careers.json holds neither of Leo Fraser's numbers: his page's
            # own terms, so he is a House Fraser of 2003-2004 and not of
            # 2025-2026, where the sitting Marilyn Fraser is the only one
            ("2003-2004", "H", "Leo Fraser"): "leo-fraser-merr-37",
            ("2025-2026", "H", "Fraser"): "marilyn-fraser-merr-1",
            # a sitting senator's House number, among her member_ids
            ("2001-2002", "H", "Tara Reardon"): "tara-reardon-sd-15",
            ("2025-2026", "S", "Reardon"): "tara-reardon-sd-15"}
    bad = [f"{b} {t} {s!r} is {got.get((t, b, s))!r}, not {w!r}" for (t, b, s), w in want.items()
           if got.get((t, b, s)) != w]
    assert not bad, "a joined mover's days: " + "; ".join(bad)
    assert "frederick-king-coos-1" not in house_1999, (
        f"King counts as a House member of 1999-2000, when he sat in the Senate: {house_1999}")
    # Silence is not success: no careers.json is said.
    import contextlib
    import io
    empty = Path(tempfile.mkdtemp(prefix="gr-nocareers-"))
    here = Path.cwd()
    out = io.StringIO()
    try:
        _os.chdir(empty)
        with contextlib.redirect_stdout(out):
            none = keep()
    finally:
        _os.chdir(here)
        shutil.rmtree(empty, ignore_errors=True)
    assert none == {} and "WARNING" in out.getvalue() and "careers.json" in out.getvalue(), (
        f"a missing careers.json is not said: {out.getvalue()!r}")
    return "ok", ("Frederick King in the House in 2005 and the Senate in 1999, Melanie Levesque in "
                  "the House in 2013 and the Senate in 2019, each by their own name, and the "
                  "sitting Seth King and Cassandra Levesque where they are the only one; Leo "
                  "Fraser, whom careers.json lacks, in his page's terms; the sitting Tara Reardon "
                  "in her House years; a missing careers.json said")


@check("session", "how the day began keeps the case of the member who led the Pledge",
       needs=("build_session_pages",))
def _opening_keeps_case(BSP):
    """opening_html put its sentence's first letter up with str.capitalize(),
    which lowers the rest: 16 days read "rep. frederick andrews (r - hills
    34) led the pledge of allegiance" (found 5 November 2026)."""
    import html as _html
    out = BSP.opening_html({"opening": {"prayer": True, "pledge": "Andrews"}}, "H",
                           BSP.Members(Path("no-such-site")), _html.escape)
    assert out.startswith("<p>A prayer was offered, and ") and "Rep. Andrews" in out and \
        "Pledge of Allegiance" in out, f"the opening reads {out!r}"
    return "ok", "the first letter up, the member's name and the Pledge as written"


@check("session", "a speaker the rosters miss is linked by the term's own ballots, where one member has the name",
       needs=("build_session_pages",))
def _speaker_by_ballot(BSP):
    """A name no roster matches for the day's term is
    matched among the members whose own ballots of that term give them a
    seat, by surname, where exactly one has it; two who share it stay words,
    and a name nobody voted under is counted in `unmatched` for the log."""
    root = Path(tempfile.mkdtemp(prefix="gr-ballot-"))
    try:
        (root / "legislators.json").write_text(json.dumps([
            {"id": 1, "slug": "paul-terry-belk-7", "name": "Terry, Paul", "chamber": "H",
             "label": "Rep. Paul Terry (R - Belk 7)"},
            {"id": 3, "slug": "ann-lee-hills-1", "name": "Lee, Ann", "chamber": "H"},
            {"id": 4, "slug": "bo-lee-hills-2", "name": "Lee, Bo", "chamber": "H"}]), encoding="utf-8")
        (root / "former.json").write_text(json.dumps([
            {"id": 2, "slug": "joe-quill-hills-9", "name": "Quill, Joe", "chamber": "H",
             "served": {"terms": ["2023-2024"]}}]), encoding="utf-8")
        m = BSP.Members(root)
        m.term = "2025-2026"
        # who voted (floor_record's ballots), not the seats shown: Quill's
        # seat of the term no source gives, and he voted in it
        m.seats = {"2025-2026": {"1": "Rep. Paul Terry (R - Belk 7)"}}
        m.ballots = {"2025-2026": {"1": "Rep. Paul Terry (R - Belk 7)",
                                   "2": "Rep. Joe Quill (R - Hills 9)",
                                   "3": "Rep. Ann Lee (D - Hills 1)", "4": "Rep. Bo Lee (R - Hills 2)"}}
        got = (m.slug("H", "Quill"), m.slug("H", "Terry"), m.slug("H", "Lee"), m.slug("H", "Nobody"))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert got == ("joe-quill-hills-9", "paul-terry-belk-7", None, None), got
    assert m.unmatched[("H", "Lee")] == 1 and m.unmatched[("H", "Nobody")] == 1, m.unmatched
    return "ok", "Quill by the term's ballots; Terry by the roster; Lee, two of them, and Nobody left as words"


@check("session", "a member who moved between chambers is named on an old day by the seat their "
                  "ballots under the earlier number give", needs=("build_session_pages",))
def _mover_seat_on_old_day(BSP):
    """The follow-up of the former movers (5 November 2026): Sen. Shannon
    Chandley's page is 9404, and her House ballots of 2009-2010 are filed
    under 568, the number joined to it (the row's member_ids). label() read
    the page's own number only, so her 2010 speaker lines said "Rep. Shannon
    Chandley" without the seat she held. A sitting mover and one who has left
    are drawn alike; a name no roster matches is linked by a ballot under the
    joined number too (by_ballot)."""
    root = Path(tempfile.mkdtemp(prefix="gr-mover-"))
    try:
        (root / "legislators.json").write_text(json.dumps([
            {"id": "9401", "slug": "cindy-rosenwald-sd-13", "name": "Rosenwald, Cindy",
             "chamber": "S", "display_full": "Sen. Cindy Rosenwald (D - SD 13)",
             "member_ids": ["9401", "177"]}]), encoding="utf-8")
        (root / "former.json").write_text(json.dumps([
            {"id": "9404", "slug": "shannon-chandley-sd-11", "name": "Chandley, Shannon",
             "chamber": "S", "display_full": "Former Sen. Shannon Chandley (D - SD 11)",
             "member_ids": ["9404", "568"], "served": {"terms": ["2009-2010", "2019-2020"]}},
            {"id": "70", "slug": "pat-quay-hills-3", "name": "Quay, Pat", "chamber": "H",
             "served": {"terms": ["2009-2010"]}}]), encoding="utf-8")
        m = BSP.Members(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    m.current, m.term = "2025-2026", "2009-2010"
    m.seats = {"2009-2010": {"568": "Rep. Shannon Chandley (D - Hills 22)",
                             "177": "Rep. Cindy Rosenwald (D - Hills 30)",
                             "70": "Rep. Pat Quay (R - Hills 3)"},
               "2019-2020": {"9404": "Sen. Shannon Chandley (D - SD 11)"}}
    got = {s: m.label(s, "H") for s in ("shannon-chandley-sd-11", "cindy-rosenwald-sd-13",
                                         "pat-quay-hills-3")}
    want = {"shannon-chandley-sd-11": "Rep. Shannon Chandley (D - Hills 22)",
            "cindy-rosenwald-sd-13": "Rep. Cindy Rosenwald (D - Hills 30)",
            "pat-quay-hills-3": "Rep. Pat Quay (R - Hills 3)"}
    assert got == want, f"a mover on a day of 2009-2010 reads {got}, not {want}"
    m.term = "2019-2020"
    assert m.label("shannon-chandley-sd-11", "S") == "Sen. Shannon Chandley (D - SD 11)", (
        "the page's own number no longer names its own term's seat")
    m.term = "2009-2010"
    assert m.by_ballot("H", "Chandley") == "shannon-chandley-sd-11", (
        "a ballot under the joined number links no page")
    # the other chamber's seat is never the one held on this chamber's day
    # (Sen. David Boutin, April 2010, once "Rep. David Boutin (R - Merr 9)")
    assert m.label("shannon-chandley-sd-11", "S") == "Sen. Shannon Chandley", (
        f"a Senate day of 2009-2010 names her {m.label('shannon-chandley-sd-11', 'S')!r}: "
        "the House seat her other number held")
    # a move in mid-term: both numbers hold a seat in one term, and each
    # chamber's day names its own (the review of 5 November 2026)
    m.term = "2017-2018"
    m.seats["2017-2018"] = {"9404": "Sen. Shannon Chandley (D - SD 11)",
                            "568": "Rep. Shannon Chandley (D - Hills 22)"}
    both = (m.label("shannon-chandley-sd-11", "H"), m.label("shannon-chandley-sd-11", "S"))
    assert both == ("Rep. Shannon Chandley (D - Hills 22)", "Sen. Shannon Chandley (D - SD 11)"), (
        f"a member who moved in mid-term is named {both} on a House and a Senate day")
    return "ok", ("Chandley (former) and Rosenwald (sitting) named by the House seat of 2009-2010 "
                  "their earlier numbers held; Chandley by SD 11 in 2019-2020")


# ---- the live layer's reader of the General Court's public SQL database ----------
# The live layer's design (26 October 2026, approved by the person as
# "defaults"), sections 2.1, 2.2, 2.7 and 6.2: workers/live/tds.js, sql.js and
# test_mode.js, tests/live/, and workers/live/live.gen.js.
LIVE_DIRS = ("workers/live", "tests/live", "functions/api/live")
LIVE_VIEWS = ("RollCallSummary", "RollCallHistory", "legislators", "Docket")


def _live_host_problems(root, host):
    """Where the General Court's SQL host is named under `root` and should not
    be: nowhere in the live layer's code or tests, and in
    workers/live/wrangler.toml only as production's SQL_HOST, equal to
    probe_db.HOST; the top level and every other environment on the loopback
    address, and ENV = "production" under production alone (design 6.2)."""
    import tomllib
    root, bad = Path(root), []
    # Exempt by its path, not its name: a wrangler.toml anywhere else under
    # these folders is a configuration `wrangler dev --config` could run.
    toml = root / "workers" / "live" / "wrangler.toml"
    for top in LIVE_DIRS:
        d = root / top
        for p in sorted(d.rglob("*")) if d.is_dir() else []:
            if p.is_file() and p != toml and host in p.read_text(encoding="utf-8", errors="replace"):
                bad.append(f"{p.relative_to(root).as_posix()} names the SQL host")
    if toml.is_file():
        text = toml.read_text(encoding="utf-8")
        conf = tomllib.loads(text)
        envs = conf.get("env", {})
        prod = envs.get("production", {}).get("vars", {})
        if sum(host in ln for ln in text.splitlines()) > 1:
            bad.append("workers/live/wrangler.toml names the SQL host on more than one line")
        if host in text and prod.get("SQL_HOST") != host:
            bad.append("workers/live/wrangler.toml names the SQL host somewhere but production's SQL_HOST")
        if prod.get("SQL_HOST") not in (None, host, "127.0.0.1", "::1"):
            bad.append(f"production's SQL_HOST is {prod.get('SQL_HOST')}, not probe_db.HOST")
        for name, v in [("the top level", conf.get("vars", {}))] + \
                [(f"[env.{n}]", e.get("vars", {})) for n, e in envs.items() if n != "production"]:
            if v.get("SQL_HOST") not in (None, "127.0.0.1", "::1"):
                bad.append(f"{name} of workers/live/wrangler.toml sets SQL_HOST to {v['SQL_HOST']}, "
                           f"not the loopback address")
            if "ENV" in v:
                bad.append(f"{name} of workers/live/wrangler.toml sets ENV, which production's vars alone may")
    return bad


def _sql_split(s):
    """`s` cut at its commas outside brackets and quotes."""
    parts, depth, quote, cur = [], 0, False, ""
    for ch in s:
        if ch == "'":
            quote = not quote
        elif not quote and ch == "(":
            depth += 1
        elif not quote and ch == ")":
            depth -= 1
        if ch == "," and not depth and not quote:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return parts + [cur.strip()]


def _sql_textual(e):
    """Whether an output column comes back as nvarchar(n), n at most 4000: a
    CAST to it, a date as CONVERT(nvarchar(19), x, 126), or an ISNULL of such
    a column and either '' or another."""
    e = e.strip()
    m = re.fullmatch(r"CAST\((.*) AS nvarchar\((\d+)\)\)", e, re.S)
    if m and _sql_split(m.group(1)) == [m.group(1).strip()] and m.group(1).count("(") == m.group(1).count(")"):
        return 1 <= int(m.group(2)) <= 4000
    if re.fullmatch(r"CONVERT\(nvarchar\(19\), [a-z]\.\w+, 126\)", e):
        return True
    m = re.fullmatch(r"ISNULL\((.*)\)", e, re.S)
    if m:
        args = _sql_split(m.group(1))
        return len(args) == 2 and _sql_textual(args[0]) and (args[1] == "''" or _sql_textual(args[1]))
    return False


def _live_statement_problems(name, sql, views, width, refused):
    """What is wrong with one of sql.js's statements as written, {NAME} where a
    value goes: one SELECT over the four views, every column it names one the
    view has (`views`: {view: [columns]}), every output column nvarchar(n),
    `width` of them, no statement end, comment, star or variable, no word of
    fetch_past_db's refused list (JOIN alone, as Q2's one LEFT JOIN of the
    roster), and no literal but '' and Q3's '%RC [0-9]%'."""
    bad = []
    places = set(re.findall(r"\{([A-Z0-9]+)\}", sql))
    if places - {"Y", "FIRST", "UNTIL", "CHAMBERS", "BODY", "SEQS", "DAY", "NEXT", "SINCE", "MDY"}:
        bad.append(f"{name} has a place no builder fills: {sorted(places)}")
    literals = re.findall(r"'(?:[^']|'')*'", sql)
    odd = [x for x in literals if x not in ("''", "'%RC [0-9]%'")]
    if odd:
        bad.append(f"{name} carries the literal {odd[0]}: a value goes in through fill() and lit()")
    # A literal or a place is set aside before the words are read: '%RC [0-9]%'
    # is no identifier, and {UNTIL} no keyword.
    bare = re.sub(r"\{[A-Z0-9]+\}", "0", re.sub(r"'(?:[^']|'')*'", "''", sql))
    if not re.match(r"SELECT\s", bare):
        bad.append(f"{name} is not a SELECT")
    if re.search(r";|--|/\*|\*/|\*|@|#|\\", bare):
        bad.append(f"{name} holds a statement end, a comment, a star or a variable")
    said = [w for w in refused if re.search(rf"\b{w}\b", bare, re.I)]
    if said:
        bad.append(f"{name} says {said[0]}")
    joins = re.findall(r"\b\w+\s+JOIN\b[^\n]*", bare)
    if joins and (name != "Q2" or joins != ["LEFT JOIN legislators l ON l.Employeeno = h.EmployeeNumber"]):
        bad.append(f"{name} joins: {joins}")
    called = {c.upper() for c in re.findall(r"([A-Za-z_]\w*)\s*\(", bare)}
    if called - {"CAST", "CONVERT", "ISNULL", "NVARCHAR", "IN", "AND", "OR"}:
        bad.append(f"{name} calls {sorted(called - {'CAST', 'CONVERT', 'ISNULL', 'NVARCHAR', 'IN', 'AND', 'OR'})}")
    if len(re.findall(r"\bFROM\b", bare)) != 1 or len(re.findall(r"\bSELECT\b", bare)) != 1:
        bad.append(f"{name} is not one SELECT with one FROM")
    aliases = dict((a, v) for v, a in re.findall(r"\b(?:FROM|JOIN)\s+(\w+)\s+([a-z])\b", bare))
    known = {v.lower(): v for v in views}
    for a, v in aliases.items():
        if v not in LIVE_VIEWS or v.lower() not in known:
            bad.append(f"{name} reads {v}, which is not one of {', '.join(LIVE_VIEWS)}")
    for a, col in re.findall(r"\b([a-z])\.(\w+)", bare):
        v = aliases.get(a)
        if v is None:
            bad.append(f"{name} names {a}.{col}, and {a} is no view it reads")
        elif v.lower() in known and col not in views[known[v.lower()]]:
            bad.append(f"{name} names {v}.{col}, which the view's columns do not include")
    head = re.match(r"SELECT\s(.*?)\nFROM\s", bare, re.S)
    items = _sql_split(head.group(1)) if head else []
    if len(items) != width:
        bad.append(f"{name} returns {len(items)} columns, and its reader takes {width}")
    plain = [x for x in items if not _sql_textual(x)]
    if plain:
        bad.append(f"{name}'s column {plain[0]!r} is not cast to nvarchar(n), n at most 4000")
    return bad


def _live_web_named(root):
    """The live layer's code under `root` (workers/live/ and functions/api/live/)
    that names the General Court's web server, which it never asks."""
    root, said = Path(root), []
    for top in ("workers/live", "functions/api/live"):
        d = root / top
        for p in sorted(d.rglob("*")) if d.is_dir() else []:
            if p.is_file() and p.suffix in (".js", ".mjs") and re.search(
                    r"gc\.nh\.gov|gencourt", p.read_text(encoding="utf-8", errors="replace"), re.I):
                said.append(p.relative_to(root).as_posix())
    return said


def _live_hours_meet(start, end, windows, margin):
    """Where weekdays from hour `start` to hour `end` in New Hampshire, in
    daylight time and in standard time, meet one of `windows`
    (refusal.NIGHT_WINDOWS, in UTC) or the `margin` minutes before one."""
    met = []
    for offset in (4, 5):                                   # daylight time, standard time
        for weekday in range(5):
            for minute in range(start * 60, end * 60):
                utc = minute + offset * 60
                day, at = (weekday + utc // 1440) % 7, utc % 1440
                for wd, (h1, m1), (h2, m2), what in windows:
                    if (wd is None or wd == day) and h1 * 60 + m1 - margin <= at < h2 * 60 + m2:
                        met.append(f"UTC{-offset:+d} {minute // 60:02d}:{minute % 60:02d} meets {what}")
    return sorted(set(met))


def _live_sql(live_gen, dayfiles_from_db, fetch_past_db, refusal):
    """Part of _live_layer, which calls it: The design's section 6.2 and 7.1, for the half of the live Worker that
    reads the General Court's public SQL database:

    LIVE.GEN.JS is what src/pages/live_gen.py writes from the repository, and
    its SQL_LOGIN is probe_db.py's DATABASE, USER and PASSWORD -- the login the
    General Court publishes -- read here again from the committed file.

    THE HOST is named in no file of the live layer's code or tests, and in
    workers/live/wrangler.toml, once there is one, only as production's
    SQL_HOST, equal to probe_db.HOST, with every other level on the loopback
    address; tds.js refuses any other host without ENV = "production" too.
    The rule is tried on fixtures first, so that a rule that stopped biting
    is caught along with a file that breaks it.

    THE STATEMENTS in workers/live/sql.js: each one SELECT over the four views,
    every column it names one db/_columns.json lists (dayfiles_from_db.VIEWS,
    which keeps that file's names, where the dump is not on this disk), every
    output column nvarchar(n) so that tds.js reads one type, as many as its
    reader takes, and no literal but '' and '%RC [0-9]%': a value goes in
    through fill() and lit() alone. fetch_past_db.select_only's refused words
    are refused here, all but JOIN, which Q2's one LEFT JOIN of the roster
    needs (HISTORY_SQL's own). And no word of gc.nh.gov or gencourt in
    workers/live/ or functions/api/live/: the live layer never asks the web
    server.

    THE TEST HOURS of workers/live/test_mode.js, weekdays from TEST_HOURS[0]
    to TEST_HOURS[1] in New Hampshire, meet no window of refusal.NIGHT_WINDOWS
    nor START_MARGIN_MINUTES before one, in standard time or daylight time.

    Every rule is first tried on a fixture that breaks it alone, and must say
    so in its own words, so that a rule which stopped catching anything fails
    here along with a file that breaks it."""
    gen, sql_js, test_js = (Path("workers/live") / n for n in ("live.gen.js", "sql.js", "test_mode.js"))
    if not gen.is_file():
        return "skip", "workers/live/ is not here"
    ok, why = live_gen.current()
    assert ok, f"{why}: run {live_gen.COMMAND}"
    m = re.search(r"^export const SQL_LOGIN = (\{.*\});$", gen.read_text(encoding="utf-8"), re.M)
    assert m and json.loads(m.group(1)) == live_gen.published_login(), \
        "live.gen.js's SQL_LOGIN is not probe_db.py's DATABASE, USER and PASSWORD"
    host = live_gen.assigned(live_gen.PROBE_DB, ("HOST",))["HOST"]

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        fx = Path(tmp)
        main_toml = fx / "workers" / "live" / "wrangler.toml"
        good = ('name = "x-local"\n[vars]\nSQL_HOST = "127.0.0.1"\n[env.production.vars]\nENV = "production"\n'
                f'SQL_HOST = "{host}"\n')
        main_toml.parent.mkdir(parents=True)
        main_toml.write_text(good, encoding="utf-8")
        assert not _live_host_problems(fx, host), _live_host_problems(fx, host)
        prod = f'[env.production.vars]\nENV = "production"\nSQL_HOST = "{host}"\n'
        for path, text in (("workers/live/x.js", f'const h = "{host}";'),
                           ("tests/live/x.js", f'const h = "{host}";'),
                           ("functions/api/live/x.js", f'const h = "{host}";'),
                           ("tests/live/wrangler.toml", prod),
                           ("workers/live/sub/wrangler.toml", prod),
                           ("workers/live/wrangler.toml", f'[vars]\nSQL_HOST = "{host}"\n'),
                           ("workers/live/wrangler.toml", '[vars]\nENV = "production"\nSQL_HOST = "127.0.0.1"\n')):
            (fx / path).parent.mkdir(parents=True, exist_ok=True)
            (fx / path).write_text(text, encoding="utf-8")
            assert _live_host_problems(fx, host), f"the host rule no longer bites on {path}: {text}"
            if fx / path == main_toml:
                main_toml.write_text(good, encoding="utf-8")
            else:
                (fx / path).unlink()
        (fx / "functions" / "api" / "live" / "x.js").write_text('fetch("https://gc.nh.gov/x")', encoding="utf-8")
        assert _live_web_named(fx) == ["functions/api/live/x.js"], "the web server rule no longer bites"
    bad = _live_host_problems(".", host)
    assert not bad, "; ".join(bad)

    said = _live_web_named(".")
    assert not said, "these name the General Court's web server, which the live layer never asks: " + ", ".join(said)

    src = sql_js.read_text(encoding="utf-8")
    t = dict(re.findall(r"^export const (Q1|Q2|Q2_CHAMBER|Q3|VERSION) = `([^`]*)`;", src, re.M))
    assert set(t) == {"Q1", "Q2", "Q2_CHAMBER", "Q3", "VERSION"}, \
        f"sql.js no longer writes its statements where this reads them (found {sorted(t)})"
    width = {k: int(v) for k, v in re.findall(r"(\w+): (\d+)", re.search(r"export const WIDTH = \{([^}]*)\}", src).group(1))}
    assert t["VERSION"] == "SELECT @@VERSION", "the test's version statement is not SELECT @@VERSION"
    cols_file = Path("db/_columns.json")
    if cols_file.is_file():
        views, whose = json.loads(cols_file.read_text(encoding="utf-8")), "db/_columns.json"
        views = {v: [c if isinstance(c, str) else c.get("name") for c in cs] for v, cs in views.items()}
    else:
        views, whose = dayfiles_from_db.VIEWS, "dayfiles_from_db.VIEWS (db/ is not on this disk)"
    refused = [w for w in re.findall(r"[A-Z]+", fetch_past_db._NOT_READ.pattern) if w != "JOIN"]
    chambers = f"{t['Q2_CHAMBER']} OR {t['Q2_CHAMBER']}"
    statements = {"Q1": (t["Q1"], width["q1"]), "Q2": (t["Q2"].replace("{CHAMBERS}", chambers), width["q2"]),
                  "Q3": (t["Q3"], width["q3"])}
    bad = [p for name, (sql, w) in statements.items()
           for p in _live_statement_problems(name, sql, views, w, refused)]
    assert not bad, "; ".join(bad[:6])
    # Each rule bites, by its own words: a fixture that breaks it alone.
    one = "SELECT CAST(d.Description AS nvarchar(9))\nFROM Docket d"
    q2 = statements["Q2"][0]
    for name, wrong, width, says in (
            ("X", one.replace("nvarchar(9))", "nvarchar(9)), *"), 2, "a star"),
            ("X", one.replace("nvarchar", "varchar"), 1, "is not cast to nvarchar"),
            ("X", one.replace("Description", "Nothing"), 1, "which the view's columns do not include"),
            ("X", one + "; SELECT 1", 1, "a statement end"),
            ("X", one + " WHERE d.SessionYear = 'x'", 1, "carries the literal 'x'"),
            ("X", one + " WHERE d.SessionYear = {EVIL}", 1, "a place no builder fills"),
            ("X", one + " WHERE d.SessionYear IN (SELECT 1)", 1, "not one SELECT with one FROM"),
            ("X", "SELECT CAST(x.Name AS nvarchar(9))\nFROM Sessions x", 1, "reads Sessions, which is not one of"),
            ("X", one + " JOIN Docket e ON e.SessionYear = d.SessionYear", 1, "X joins"),
            ("Q2", q2.replace("h.EmployeeNumber\n", "h.EmployeeNumber\n  LEFT JOIN legislators m "
                                                   "ON m.Employeeno = h.EmployeeNumber\n"), 4, "Q2 joins"),
            ("X", one.replace("CAST(d.Description", "CAST(LEN(d.Description)"), 1, "calls ['LEN']"),
            ("X", one + "\nEXEC xp_cmdshell", 1, "says EXEC"),
            ("X", one, 2, "returns 1 columns, and its reader takes 2")):
        got = _live_statement_problems(name, wrong, views, width, refused)
        assert any(says in p for p in got), f"the statement rule no longer says {says!r} of {wrong!r}: {got}"

    hours = re.search(r"export const TEST_HOURS = \[(\d+), (\d+)\];", test_js.read_text(encoding="utf-8"))
    assert hours, "test_mode.js no longer says TEST_HOURS where this reads it"
    start, end = int(hours.group(1)), int(hours.group(2))
    margin = refusal.START_MARGIN_MINUTES
    # The rule bites: hours over the nightly, past midnight into Monday's
    # weekly job, and a window's margin before it opens.
    assert _live_hours_meet(4, 10, refusal.NIGHT_WINDOWS, margin), "the hours rule misses the nightly"
    assert any("Monday" in m for m in _live_hours_meet(0, 2, refusal.NIGHT_WINDOWS, margin)), \
        "the hours rule misses Monday's weekly job"
    edge = ((None, (9, 10), (9, 20), "a window at 09:10 UTC"),)
    assert _live_hours_meet(3, 4, edge, 30) and not _live_hours_meet(3, 4, edge, 0), \
        "the hours rule no longer keeps the margin before a window"
    met = _live_hours_meet(start, end, refusal.NIGHT_WINDOWS, margin)
    assert not met, "the November test's hours meet the night's window: " + "; ".join(met[:3])
    return "ok", (f"live.gen.js current, its login probe_db.py's; the host production's alone; Q1, Q2 and "
                  f"Q3 cast every column and name only columns {whose} lists; the test's "
                  f"{start:02d}:00-{end:02d}:00 misses the night's windows")
# The person's ready-made switches (workers/live/control/), each as the Worker
# must read it; and the values control.json may hold (store.js CONTROL_VALUES).
LIVE_CONTROL = {"all-off.json": {"youtube": "off", "sql": "off"},
                "on.json": {"youtube": "on", "sql": "on"},
                "sql-off.json": {"youtube": "on", "sql": "off"},
                "sql-test.json": {"youtube": "on", "sql": "test"}}
LIVE_CONTROL_VALUES = {"youtube": ("on", "off"), "sql": ("off", "test", "on")}
# What the live code may not name: the General Court's web server (it asks
# only YouTube, and in a later branch the published SQL host) and the email
# follower's database, which is another Worker's.
LIVE_NEVER = re.compile(r"gc\.nh\.gov|gencourt|graniterecord-follow|FOLLOW_DB", re.I)
LOOPBACK = ("127.0.0.1", "::1", "localhost")


@check("build", "the night's session.votes files: each dated session-day page's roll calls in the shape "
       "the live votes file keeps (schema/session.votes.json), the record's ballots aligned to its "
       "members, a file going with its page, and the morning page noindex, with no day file",
       needs=("build_live_session",))
def _live_session(BLS):
    """The session days' side of the live layer (design sections 4.2 to 4.4),
    on a site of three dated pages written here: build_live_session's checker
    judges every shared case as tests/live/schema_cases.json says (the node
    checker runs the same cases); every day file holds to the schema; a
    roll call's ballots are the record's, member by member; a date whose page
    is gone loses its file and a term file is untouched; a vote the shape has
    no character for stops the step; and the morning page is written for the
    build's day only, never over the record's page, noindex, with no day
    file, and gone the next day."""
    import tempfile
    shape = BLS.schema()
    cases = json.loads(_source("tests/live/schema_cases.json"))["cases"]
    wrong = []
    for c in cases:
        try:
            BLS.check(c["doc"], shape)
            ok = True
        except BLS.Invalid:
            ok = False
        if ok != c["valid"]:
            wrong.append(c["name"])
    assert len(cases) >= 30 and not wrong, f"the schema checker judges these against the cases file: {wrong}"
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        for d in ("session/H", "session/S", "data", "idx"):
            (site / d).mkdir(parents=True)
        for f in ("session/H/2026-03-11.html", "session/H/2026-03-12.html", "session/S/2026-03-12.html"):
            (site / f).write_text("<p>x</p>", encoding="utf-8")
        (site / "session/H/2025-2026.json").write_text('{"term": "kept"}', encoding="utf-8")
        (site / "session/H/2026-01-01.json").write_text("{}", encoding="utf-8")   # its page is gone
        (site / "data/rollcalls.csv").write_text(
            "roll_call,term,year,body,number,date,bill,question,question_plain,yeas,nays,not_voting,passed,"
            "procedural,threshold_needed,threshold_rule,outcome_source\n"
            "2026-H-41,2025-2026,2026,H,41,2026-03-11,HB 1376-FN,Ought to Pass,,2,0,1,1,0,,,\n"
            "2026-H-42,2025-2026,2026,H,42,2026-03-11,SUSPRULE,Suspend the Rules,,2,0,1,1,1,,,\n"
            "2026-H-40,2025-2026,2026,H,40,2026-03-11,,Shall Member Continue,,1,1,1,0,0,2,,\n"
            "2026-H-50,2025-2026,2026,H,50,2026-03-13,HB2,Table,,1,1,1,0,0,,,\n"
            "2026-S-9,2025-2026,2026,S,9,2026-03-12,SB12,Ought to Pass,,1,0,0,1,0,,,\n", encoding="utf-8")
        (site / "data/votes-2025-2026.csv").write_text(
            "roll_call,term,date,bill,question,member_id,member,party,chamber,vote\n"
            "2026-H-41,2025-2026,2026-03-11,HB1376,x,960,\"A, B\",R,House,Yea\n"
            "2026-H-41,2025-2026,2026-03-11,HB1376,x,11463,\"C, D\",D,House,Yea\n"
            "2026-H-41,2025-2026,2026-03-11,HB1376,x,200,\"E, F\",D,House,Not Voting/Excused\n"
            "2026-H-40,2025-2026,2026-03-11,,x,960,\"A, B\",R,House,Nay\n"
            "2026-H-42,2025-2026,2026-03-11,SUSPRULE,x,960,\"A, B\",R,House,Yea\n"
            "2026-H-42,2025-2026,2026-03-11,SUSPRULE,x,11463,\"C, D\",D,House,Yea\n"
            "2026-H-40,2025-2026,2026-03-11,,x,11463,\"C, D\",D,House,Yea\n"
            "2026-S-9,2025-2026,2026-03-12,SB12,x,7,\"G, H\",R,Senate,Yea\n", encoding="utf-8")
        (site / "meta.json").write_text('{"terms": ["2025-2026"]}', encoding="utf-8")
        (site / "idx/2025-2026.json").write_text(
            '[{"id": "HB1376", "year": 2026}, {"id": "HB2", "year": 2025}]', encoding="utf-8")
        docs = BLS.day_files(site)
        wrote, gone = BLS.write_day_files(site, docs)
        assert (wrote, gone) == (3, ["H/2026-01-01.json"]), (wrote, gone)
        assert (site / "session/H/2025-2026.json").read_text(encoding="utf-8") == '{"term": "kept"}', \
            "the session-day step's term file was written over"
        h = json.loads((site / "session/H/2026-03-11.json").read_text(encoding="utf-8"))
        BLS.check(h, shape)
        assert h["provisional"] is False and h["status"]["state"] == "record"
        assert h["members"] == {"H": ["200", "960", "11463"], "S": []}, h["members"]
        assert [r["id"] for r in h["rollcalls"]] == ["2026-H-40", "2026-H-41", "2026-H-42"], "in the record's order"
        r40, r41, r42 = h["rollcalls"]
        assert (r42["bill"], r42["bill_as_recorded"]) == (None, "SUSPRULE"), \
            f"a procedural vote names no bill, and keeps its words: {r42['bill']!r}"
        assert (r41["ballots"], r41["ballots_complete"], r41["bill"], r41["bill_as_recorded"], r41["passed"]) == \
            ("EYY", True, "2025-2026/HB1376", "HB 1376-FN", True), r41
        assert (r40["ballots"], r40["ballots_complete"], r40["bill"], r40["passed"], r40["threshold_needed"]) == \
            (".NY", True, None, False, 2), r40
        assert r41["taken"] is None and r41["docket"] is None, "the record vouches for no clock or docket line here"
        assert json.loads((site / "session/H/2026-03-12.json").read_text(encoding="utf-8"))["rollcalls"] == [], \
            "a sitting with no roll call has its file, empty"
        s = json.loads((site / "session/S/2026-03-12.json").read_text(encoding="utf-8"))
        assert [r["id"] for r in s["rollcalls"]] == ["2026-S-9"] and s["members"]["S"] == ["7"]
        assert not (site / "session/H/2026-03-13.json").exists(), "a roll call's day with no page has no file"
        # A broken document is refused before anything is written.
        bad = {k: dict(v, api=2) for k, v in docs.items()}
        try:
            BLS.write_day_files(site, bad, shape)
            raise AssertionError("a document breaking the schema was written")
        except SystemExit as e:
            assert "does not hold to schema/session.votes.json" in str(e), e
        # A vote the shape has no character for stops the step, by name.
        votes = site / "data/votes-2025-2026.csv"
        votes.write_text(votes.read_text(encoding="utf-8").replace("House,Nay", "House,Paired"), encoding="utf-8")
        try:
            BLS.day_files(site)
            raise AssertionError("an unknown vote word was written as a ballot")
        except SystemExit as e:
            assert "'Paired'" in str(e), e
        # Silence is not success: dated pages and no roll-call file to read.
        for gone_file in ("data/rollcalls.csv", "data/votes-2025-2026.csv"):
            kept = (site / gone_file).read_bytes()
            (site / gone_file).unlink()
            r = _run([sys.executable, str(Path(_paths.locate("build_live_session.py"))), "--site", str(site),
                      "--today", "2026-03-12"], capture_output=True, text=True, timeout=120)
            (site / gone_file).write_bytes(kept)
            assert r.returncode != 0 and "no data/" in (r.stderr + r.stdout), \
                f"without {gone_file} the step exited {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}"
        votes.write_text(votes.read_text(encoding="utf-8").replace("House,Paired", "House,Nay"), encoding="utf-8")
        # The morning page: the dated address on the morning of a sitting.
        D = __import__("datetime").date
        rows = [{"date": "2026-03-13", "body": "H", "kind": "floor debate", "bill": "HB2", "term": "2025-2026"},
                {"date": "2026-03-13", "body": "H", "kind": "public hearing", "bill": "HB9", "term": "2025-2026"},
                {"date": "2026-03-13", "body": "H", "kind": "floor debate", "bill": "hb1376", "term": "2025-2026"},
                {"date": "2026-03-13", "body": "H", "kind": "floor debate", "bill": "HB2", "term": "2025-2026"},
                {"date": "2026-03-13", "body": "S", "kind": "floor debate", "bill": "SB12", "term": "2025-2026"},
                {"date": "2026-03-16", "body": "H", "kind": "floor debate", "bill": "HB3", "term": "2025-2026"}]
        assert BLS.agenda("H", D(2026, 3, 13), rows) == [("2025-2026", "HB2"), ("2025-2026", "HB1376")], \
            "the floor's bills, in the calendar's order, each once, and no hearing"
        assert BLS.write_morning(site, "https://x.org", "H", D(2026, 3, 12), rows) is None and \
            (site / "session/H/2026-03-12.html").read_text(encoding="utf-8") == "<p>x</p>", \
            "a morning page was written over the record's page"
        (site / "session/H/today.html").write_text("old", encoding="utf-8")
        (site / "session/H/2026-03-13.json").write_text("{}", encoding="utf-8")   # an old file on the date
        # The Calendar, which runs before this step, leaves the floor card's
        # link to the build's day hidden (build_pages.cal_days); the step
        # shows it once it has written the page, and only that day's.
        import build_pages as BP
        import html as _h
        floor = BP.Meet("2026-03-13", "H", "House Floor", "")
        slot = {floor: [{"bill": "HB2", "time": "10:00", "what": "floor debate",
                         "venue": "Representatives Hall", "body": "H"}]}

        def card(sessions, morning):
            return BP.cal_days({floor.date: [floor]}, slot, {}, {}, {}, lambda d: (d, ""), _h.escape,
                               sessions=sessions, morning=morning)[0]
        waiting = card(set(), "2026-03-13")
        assert 'data-morning="H/2026-03-13" hidden><a data-href="session/H/2026-03-13">' in waiting \
            and ' href="session/H/2026-03-13' not in waiting \
            and "did that day" not in waiting, "the Calendar does not leave the morning page's link waiting"
        assert "data-morning" not in card(set(), "2026-03-12") and "session/H/2026-03-13" not in \
            card(set(), "2026-03-12"), "a sitting of another day with no page was given a link"
        assert "did that day" in card({("H", "2026-03-13")}, "2026-03-13") and "data-morning" not in \
            card({("H", "2026-03-13")}, "2026-03-13"), "a sitting with its record page lost its own link"
        other = waiting.replace("2026-03-13", "2026-03-20")
        (site / "calendar/data").mkdir(parents=True)
        (site / "calendar.html").write_text(waiting + other, encoding="utf-8")
        (site / "calendar/data/2026-03.json").write_text(json.dumps({"days": {"2026-03-13": waiting}}),
                                                        encoding="utf-8")
        seen = {}
        BLS.write(site, "https://x.org", D(2026, 3, 13), seen, rows)
        cal = (site / "calendar.html").read_text(encoding="utf-8")
        assert 'data-morning="H/2026-03-13"><a href="session/H/2026-03-13">' in cal \
            and 'data-morning="H/2026-03-20" hidden><a data-href=' in cal, \
            "the morning page's Calendar link was not shown, or another day's was"
        assert json.loads((site / "calendar/data/2026-03.json").read_text(encoding="utf-8"))["days"][
            "2026-03-13"].count('data-morning="H/2026-03-13"><a href=') == 1, "the month's data still hides the link"
        assert sorted(seen["calendar"]) == ["calendar.html", "calendar/data/2026-03.json"], seen["calendar"]
        assert sorted(seen["mornings"]) == ["H/2026-03-13.html", "S/2026-03-13.html"], seen["mornings"]
        assert not (site / "session/H/today.html").exists(), "the retired today page was kept"
        page = (site / "session/H/2026-03-13.html").read_text(encoding="utf-8")
        head = page.encode()[:BLS.HEAD_BYTES]
        assert BLS.MORNING.encode() in head and BLS.is_morning(site / "session/H/2026-03-13.html") \
            and not BLS.is_morning(site / "session/H/2026-03-12.html"), "the marker is not in the head"
        assert '<meta name="robots" content="noindex">' in page \
            and '<script src="/live.js" defer>' in page and 'data-day="2026-03-13" data-body="H"' in page \
            and 'id="live-day-status" class="lv-status" aria-live="polite"' in page
        assert [m for m in re.findall(r'class="lv-rcs" data-bill="(\w+)"', page)] == ["HB2", "HB1376"], \
            "each bill's card has a place for its votes, in the calendar's order"
        assert "Votes as they are read. Who spoke and the debate come with the House Journal, which can " \
               "take months." in page and "scheduled to sit on Friday, March 13, with 2 bills" in page
        assert "today" not in re.sub(r"<script.*?</script>", "", page.split('id="results"', 1)[1], flags=re.S), \
            "the page says today, which a page left up a day longer would say of the wrong day"
        assert "cstat" not in page, "last night's status chip beside the day's votes"
        # In short's words and the motions twin reach the page; the pending
        # line is the manager's wording, with the motion in votes.json's words.
        assert 'id="live-words"' in page and '"roll_call":"roll call"' in page \
            and '["ought to pass","pass it"]' in page, "In short's words are not in the page"
        assert page.index('<script src="/motions.js" defer>') < page.index('<script src="/live.js" defer>'), \
            "motions.js must load before live.js"
        pend = BLS.pending_html({"recommendation": "Ought to Pass", "yeas": 12, "nays": 8}, "HB2", "H")
        assert pend == ('<p class="lv-pending">Pending: Ought to Pass '
                        '(<span data-term="OTP">OTP</span>, Pass the bill). A special order, a motion '
                        'to table or a motion to indefinitely postpone can change what the House votes on '
                        'first.</p>'), pend
        assert BLS.pending_html(None, "HB2", "H") == "" and BLS.pending_html({}, "HB2", "S") == "", \
            "a pending line with no recommendation"
        assert BLS.S.E(BLS.ROLL_CALLS_ONLY) in page, "the page does not say that only roll calls are read during the day"
        # A report the chamber has already acted on is no pending motion: a
        # bill passed in January and back in March for a concurrence.
        import build_session_pages as BSP
        import committee_acts as CA
        evs = [{"date": "2026-01-10", "type": "report", "body": "H", "cancelled": False, "side": "",
                "committee": "House Commerce", "recommendation": "Ought to Pass", "amendment": "",
                "report_date": "01/10/2026", "yeas": "12", "nays": "8", "raw": "Committee Report: OTP 01/10/2026"},
               {"date": "2026-01-20", "type": "floor", "body": "H", "cancelled": False, "motion": "MA",
                "action": "Ought to Pass", "vote_kind": "VV", "raw": "Ought to Pass: MA VV 01/20/2026"}]
        assert BSP.recommendation_on(CA.acts(evs), "H", "2026-03-12", BLS.floor_items(evs, "H")) is None, \
            "a report the House acted on in January is the pending motion in March"
        assert BSP.recommendation_on(CA.acts(evs[:1]), "H", "2026-03-12", BLS.floor_items(evs[:1], "H")), \
            "a report not yet acted on is no pending motion"
        assert BLS.floor_items(evs, "S") == [], "the other chamber's floor vote was read as this one's"
        assert "lv-none" not in page, "the no-bills line on a day with bills"
        assert '"2025-2026":{"2025":["HB2"],"2026":["HB1376"]}' in page, "the bills' own years"
        assert not (site / "session/H/2026-03-13.json").exists(), \
            "a morning page has a record day file: a sitting still to come would read as one with no roll call"
        # A run for an earlier day leaves a later day's morning page.
        BLS.write(site, "https://x.org", D(2026, 3, 11), {}, rows)
        assert BLS.is_morning(site / "session/H/2026-03-13.html"), "a later day's morning page went"
        # The next day: the morning page of an earlier day goes; a floor day
        # with no bills listed yet (Organization Day) still has its page.
        (site / "live").mkdir(exist_ok=True)
        (site / "live/schedule.json").write_text(json.dumps(
            {"days": {"2026-03-17": [{"kind": "floor", "chamber": "S"}]}}), encoding="utf-8")
        seen = {}
        BLS.write(site, "https://x.org", D(2026, 3, 17), seen, rows)
        assert seen["mornings"] == ["S/2026-03-17.html"] and \
            not (site / "session/H/2026-03-13.html").exists() and \
            not (site / "session/S/2026-03-13.html").exists(), "an earlier day's morning page was kept"
        assert (site / "session/H/2026-03-12.html").exists(), "the record's page went with the morning pages"
        org = (site / "session/S/2026-03-17.html").read_text(encoding="utf-8")
        assert "The Senate is scheduled to sit on Tuesday, March 17." in org and 'id="lv-none"' in org, \
            "a sitting with no bills listed says so"
        # Without /live's schedule the step stops, by name.
        (site / "live/schedule.json").unlink()
        r = _run([sys.executable, str(Path(_paths.locate("build_live_session.py"))), "--site", str(site),
                  "--today", "2026-03-17"], capture_output=True, text=True, timeout=120)
        assert r.returncode != 0 and "no live/schedule.json" in (r.stderr + r.stdout), \
            f"without live/schedule.json the step exited {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}"
    # New Hampshire's day, by the rule: a stated day; then the clock on each
    # side of the changes of 2026 (8 March 07:00 UTC, 1 November 06:00 UTC).
    import build_live as BL
    import build_date
    saved = build_date.utcnow, build_date.stated
    try:
        build_date.stated = lambda: None
        for at, want in (("2026-03-08T06:59:00", "2026-03-08"), ("2026-03-08T04:59:00", "2026-03-07"),
                         ("2026-03-09T03:59:00", "2026-03-08"), ("2026-03-09T04:00:00", "2026-03-09"),
                         ("2026-11-01T05:59:00", "2026-11-01"), ("2026-11-02T04:59:00", "2026-11-01"),
                         ("2026-11-02T05:00:00", "2026-11-02"), ("2026-07-01T03:59:00", "2026-06-30")):
            build_date.utcnow = lambda at=at: __import__("datetime").datetime.fromisoformat(at + "+00:00")
            got = BL.nh_today().isoformat()
            assert got == want, f"at {at} UTC New Hampshire's day is {want}, and nh_today says {got}"
    finally:
        build_date.utcnow, build_date.stated = saved
    src = Path(_paths.locate("build_live_session.py")).read_text(encoding="utf-8")
    assert "sitemap" not in src.split('"""', 2)[2], "the morning pages must be in no sitemap"
    return "ok", (f"{len(cases)} shared cases judged alike; three day files on a fixture site, "
                  "ballots the record's, a file gone with its page, the morning page noindex and "
                  "file-less, in the calendar's order, and gone the next day")


@check("build", "/live's two links, the home page's line and the header search's row, are written by /live's "
       "own step, once however often it runs, and only while build_live.LINKED (the owner's switch) is on",
       needs=("build_live", "shell"))
def _live_links(BL, S):
    """PATCHES.md 2 and 3 by the release session's plan (5 November 2026):
    build_pages and build_indexes run before /live exists, so build_pages
    leaves the home page a slot and /live's step fills it and puts its own
    row in find.json (shell.find_merge). LINKED off takes both out again,
    which is how the owner unlinks /live (SWITCH_ON.md)."""
    import tempfile
    import datetime as _dt
    import build_pages as BP
    src = Path(_paths.locate("build_pages.py")).read_text(encoding="utf-8")
    assert BL.HOME_SLOT in src, "build_pages no longer leaves the home page's Live Now slot as build_live fills it"
    day = _dt.date(2026, 3, 12)
    sched = {"days": {"2026-03-12": [{"id": "a"}, {"id": "b"}], "2026-03-13": []}}
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        home = f"<main><div id=\"session\"></div>\n{BL.HOME_SLOT}\n</main>"
        (site / "index.html").write_text(home, encoding="utf-8")
        live = S.canon(BL.PAGE)                       # "live", as the site's other links are written
        rows = [["page", "Bills", "x", S.canon("bills.html"), ""], ["page", "Live Now", "old", live, ""]]
        (site / "find.json").write_text(json.dumps(rows), encoding="utf-8")
        saved = BL.LINKED
        try:
            BL.LINKED = True
            for _ in range(2):
                BL.link_home(site, sched, day)
                S.find_merge(site, ["page", "Live Now", "now", S.canon(BL.PAGE), BL.FIND_WORDS], S.canon(BL.PAGE))
            page = (site / "index.html").read_text(encoding="utf-8")
            assert page.count('class="lv-home"') == 1 and 'data-day="2026-03-12"' in page \
                and f'<a href="{live}">Live Now</a><span class="lv-count"> — 2 meetings today</span>' in page, page
            found = json.loads((site / "find.json").read_text(encoding="utf-8"))
            assert [r[3] for r in found].count(live) == 1 and found[0] == rows[0] \
                and found[-1][2] == "now", f"find.json after two runs: {found}"
            assert "—" not in BL.home_line(sched, _dt.date(2026, 3, 13)), "a day with no meetings has a count"
            BL.LINKED = False
            BL.link_home(site, sched, day)
            S.find_merge(site, None, S.canon(BL.PAGE))
            assert (site / "index.html").read_text(encoding="utf-8") == home, "LINKED off left the home line"
            assert json.loads((site / "find.json").read_text(encoding="utf-8")) == rows[:1], \
                "LINKED off left /live's row in find.json"
        finally:
            BL.LINKED = saved
    assert BL.HOME_SLOT not in BP.home_body("es", False, "", "", "", ""), \
        "the Spanish home has the English-only Live Now slot"
    assert BL.HOME_SLOT in BP.home_body("en", False, "", "", "", ""), "the English home has no Live Now slot"
    return "ok", ("home line and search row filled once in two runs, taken out with LINKED off; LINKED is "
                  + ("on" if BL.LINKED else "off"))


@check("build", "the live session page's In short says a vote as the session page does: motions.js reads "
       "every roll call's question on disk as motions.py does, and live.js's voteSaid gives "
       "build_session_pages.vote_said's sentence, passed, failed, not known and short of two thirds",
       needs=("build_session_pages", "build_live_session", "rollcall_parser"))
def _in_short_twin(BSP, BLS, RP):
    """The owner, 30 October 2026: the live day's In short is a finished
    day's, from the same code and the same words. motions.js is motions.py
    line for line, and live.js's voteSaid is vote_said for what a live roll
    call carries; this runs both over the questions the General Court's
    roll-call files hold (RollCallSummary's question, the field the Worker
    reads) and fails on any key or sentence that differs. What the day
    cannot know -- the bill's history, a passage left pending -- is not in
    either side's input: the history is empty and nothing is left pending."""
    import types
    import components as C
    root = Path(".")
    seen, cases = set(), []
    for f in sorted((root / "records/rollcalls").glob("RollCallSummary*.txt")):
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            q = line.split("|")
            if len(q) < 13 or q[1].strip() not in ("H", "S"):
                continue
            k = (q[11].strip(), RP.bill_number(q[4]) or "", q[1].strip())
            if k not in seen:
                seen.add(k)
    # Forms no roll-call file holds that a docket line does, so each branch of
    # vote_said is held: an enrolled bill amendment, and a Senate mover before
    # a motion no row of the vote words names (narrative.split_mover).
    for words in ("Enrolled Bill Amendment 2026-1234e", "Sen. Abbas Moved Retain",
                  "Sen. Abbas Moved Without Recommendation", "Floor Amendment 2026-0531h (Rep. Rice)"):
        seen.add((words, "SB12", "S"))
    for words, bill, body in sorted(seen):
        for carried, yeas, nays, need in ((True, 200, 150, None), (False, 150, 200, None), (None, 180, 170, None),
                                          (False, 220, 150, -(-370 * 2 // 3)), (False, 220, 150, None),
                                          (None, None, None, None)):
            cases.append({"words": words, "bill": bill, "body": body, "carried": carried,
                          "yeas": yeas, "nays": nays, "need": need})
    assert len(seen) >= 500, f"only {len(seen)} questions read off records/rollcalls/: the corpus is not there"
    # Each vote as the night's record gives it to vote_said: a vote on the
    # Governor's veto is a veto (session_days sets it.veto from its docket
    # row), and a motion votes.json says needs two thirds carries two thirds
    # of those voting as its threshold (vote_passage), which the live file
    # never carries and live.js supplies the same way.
    motions = C.WORDBOOK["votes"]["motions"]
    want = []
    for c in cases:
        it = types.SimpleNamespace(action=c["words"], carried=c["carried"], kind="RC", yeas=c["yeas"],
                                   nays=c["nays"], counted=c["yeas"] is not None and c["nays"] is not None,
                                   wo=False, veto=False, fifths=False, need=c["need"], raw="")
        k = BSP.motion_chip(it, c["bill"], c["body"])[1]
        mk = k.get("mk") or ""
        it.veto = mk.startswith("override")
        if it.need is None and it.counted and re.search(r"\btwo thirds\b", (motions.get(mk) or {}).get("gloss") or ""):
            it.need = -(-(it.yeas + it.nays) * 2 // 3)
        want.append([mk, BSP.vote_said(it, c["bill"], c["body"])])
    node = shutil.which("node")
    assert node, "node is not on PATH, and live.js's In short is the thing held here"
    feed = {"wordbook": C.WORDBOOK, "words": BLS.live_words(),
            "cases": [{"body": c["body"], "r": {"question": c["words"],
                                                "bill": f"t/{c['bill']}" if c["bill"] else None,
                                                "passed": c["carried"], "yeas": c["yeas"], "nays": c["nays"],
                                                "threshold_needed": c["need"]}} for c in cases]}
    r = _run([node, str(root / "tests/live/in_short_twin.mjs")], input=json.dumps(feed),
             capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"node could not run In short: {(r.stderr or r.stdout).strip()[-400:]}"
    got = json.loads(r.stdout)
    keys = [f"{c['words']!r} on {c['bill'] or 'no bill'}: motions.js {g[0]!r}, motions.py {w[0]!r}"
            for c, g, w in zip(cases, got, want) if g[0] != w[0]]
    said = [f"{c['words']!r} ({c['carried']}): live.js {g[1]!r}, the session page {w[1]!r}"
            for c, g, w in zip(cases, got, want) if g[1] != w[1]]
    assert not keys, f"{len(keys)} motions read apart: " + "; ".join(keys[:4])
    assert not said, f"{len(said)} votes said apart: " + "; ".join(said[:4])
    quoted = sum(1 for w in want if "“" in w[1])
    return "ok", (f"{len(seen):,} questions, {len(cases):,} votes said alike by live.js and the session "
                  f"page ({quoted:,} in the clerk's own words, quoted)")


def _live_host(root):
    """probe_db.HOST, read by parsing probe_db.py (importing no fetcher)."""
    tree = ast.parse((root / "src/fetch/gc_db/probe_db.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "HOST"
                                                for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("src/fetch/gc_db/probe_db.py no longer assigns HOST")


def _live_problems(root):
    """[sentence] for each way workers/live/ breaks a rule node cannot see:
    its configuration, where the General Court's host may be named, what its
    code imports and names, its README's commands and its switch's files."""
    import tomllib
    bad = []
    live = root / "workers/live"
    toml_text = (live / "wrangler.toml").read_text(encoding="utf-8")
    conf = tomllib.loads(toml_text)
    envs = conf.get("env", {})
    prod = envs.get("production") or {}
    # Production alone runs: its cron, its name, its bucket; nothing answers.
    # A route is refused wherever it is written: under a [[...]] table it
    # parses as that table's key, and would be read nowhere else.
    if re.search(r"^\s*(?:\[+[^\]]*\broutes?\]+|routes?\s*=)", toml_text, re.M):
        bad.append("wrangler.toml declares a route: the live Worker answers no request")
    if set(envs) != {"production"}:
        bad.append(f"wrangler.toml has the environments {sorted(envs)}, and the live Worker has "
                   "production alone")
    if "triggers" in conf:
        bad.append("wrangler.toml has a cron at the top level, which `wrangler dev` runs and which every "
                   "environment inherits: it belongs under [env.production.triggers] alone")
    if prod.get("triggers", {}).get("crons") != ["*/2 * * * *"]:
        bad.append(f"production's cron is {prod.get('triggers', {}).get('crons')}, not every 2 minutes, "
                   "which clock.js's STEP and every cadence assume")
    for where, d in (("the top level", conf), ("production", prod)):
        if d.get("workers_dev") is not False:
            bad.append(f"wrangler.toml: {where} does not set workers_dev = false")
        if {"route", "routes"} & set(d):
            bad.append(f"wrangler.toml gives {where} a route: the live Worker answers no request")
        if not (d.get("observability") or {}).get("enabled"):
            bad.append(f"wrangler.toml: {where} does not keep Workers Logs, where each run's codes go")
    if prod.get("name") != "graniterecord-live" or conf.get("name") == "graniterecord-live":
        bad.append(f"the production Worker is named {prod.get('name')!r} and the local one "
                   f"{conf.get('name')!r}: production is graniterecord-live, and only production")
    top_b = [(b.get("binding"), b.get("bucket_name")) for b in conf.get("r2_buckets", [])]
    prod_b = [(b.get("binding"), b.get("bucket_name")) for b in prod.get("r2_buckets", [])]
    if prod_b != [("LIVE", "graniterecord-live")]:
        bad.append(f"production binds {prod_b}, and the live Worker binds LIVE to graniterecord-live alone")
    if len(top_b) != 1 or top_b[0][0] != "LIVE" or top_b[0][1] == "graniterecord-live":
        bad.append(f"the top level binds {top_b}: LIVE to a local bucket, never the real one")
    for d in (conf, prod):
        for k in ("d1_databases", "kv_namespaces", "services", "durable_objects", "queues"):
            if d.get(k):
                bad.append(f"wrangler.toml binds {k}: the live Worker has its bucket and nothing else")
    clock = (live / "clock.js").read_text(encoding="utf-8")
    if not re.search(r"^export const STEP = 2 \* MINUTE;", clock, re.M):
        bad.append("clock.js's STEP is not the cron's 2 minutes")
    # The General Court's SQL host: in production's vars, as probe_db has it, or nowhere.
    host = _live_host(root)
    for k, v in (conf.get("vars") or {}).items():
        if k.endswith("_HOST") and v not in LOOPBACK:
            bad.append(f"wrangler.toml's top-level {k} is {v!r}: what `wrangler dev` runs reaches "
                       "loopback alone")
    pvars = prod.get("vars") or {}
    if "SQL_HOST" in pvars and pvars["SQL_HOST"] != host:
        bad.append(f"production's SQL_HOST is {pvars['SQL_HOST']!r}, not probe_db.HOST")
    roots = [live, root / "tests/live", root / "functions/api/live"]
    files = sorted(p for r_ in roots if r_.is_dir() for p in r_.rglob("*") if p.is_file())
    for p in files:
        rel = p.relative_to(root).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        if host in text:
            lines = [ln for ln in text.splitlines() if host in ln]
            ok = (rel == "workers/live/wrangler.toml" and len(lines) == 1
                  and re.fullmatch(rf'\s*SQL_HOST\s*=\s*"{re.escape(host)}"\s*(#.*)?', lines[0])
                  and pvars.get("SQL_HOST") == host)
            if not ok:
                bad.append(f"{rel} names the General Court's SQL host, which only production's "
                           "SQL_HOST in workers/live/wrangler.toml may")
        if p.suffix in (".js", ".toml", ".json") and LIVE_NEVER.search(text):
            bad.append(f"{rel} names {LIVE_NEVER.search(text).group(0)!r}: the live code asks neither the "
                       "General Court's web server nor the follow database")
    # The Worker's code imports its own folder, common.js's clock and
    # cloudflare:sockets (the database's socket, imported when a run needs it),
    # and nothing else; an import() is read as an import.
    for p in sorted(live.glob("*.js")):
        text = p.read_text(encoding="utf-8")
        specs = re.findall(r'^\s*import\s[^;]*?from\s+"([^"]+)"', text, re.M | re.S) + \
            re.findall(r'\bimport\(\s*["\']([^"\']+)["\']\s*\)', text)
        for spec in specs:
            if not (re.fullmatch(r"\./[\w.-]+\.js", spec) or spec in ("../follow/common.js", "cloudflare:sockets")):
                bad.append(f"workers/live/{p.name} imports {spec}: the Worker imports its own folder, "
                           "../follow/common.js and cloudflare:sockets, nothing else")
    # The live Functions read the bucket and do nothing else (design 6.4):
    # _store.js alone names env.LIVE, and hands back get and head; no file
    # there writes, deletes, lists or uploads. Previews read the production
    # bucket on the strength of this rule.
    fdir = root / "functions/api/live"
    for p in sorted(fdir.rglob("*.js")) if fdir.is_dir() else []:
        rel = p.relative_to(root).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?<!cache)\.(put|delete|list|createMultipartUpload|resumeMultipartUpload)\s*\(", text)
        if m:
            bad.append(f"{rel} calls {m.group(1)}(): the live Functions read the bucket, through _store.js's "
                       "get and head alone")
        if p.name != "_store.js" and re.search(r"\benv\s*(?:\.\s*LIVE\b|\[\s*[\"']LIVE[\"']\s*\])", text):
            bad.append(f"{rel} names env.LIVE: only functions/api/live/_store.js may")
        if p.name == "_store.js":
            other = sorted(set(re.findall(r"\bbucket\.(\w+)", text)) - {"get", "head"})
            if other:
                bad.append(f"{rel} hands the bucket's {', '.join(other)} on: the facade is get and head alone")
    # The site's binding of LIVE (root wrangler.toml), once it is there:
    # production and previews the real bucket, the local top level never.
    site_toml = root / "wrangler.toml"
    site = tomllib.loads(site_toml.read_text(encoding="utf-8")) if site_toml.is_file() else {}
    lv = lambda d: [b.get("bucket_name") for b in (d.get("r2_buckets") or []) if b.get("binding") == "LIVE"]
    senv = site.get("env") or {}
    bound = {"top": lv(site), "production": lv(senv.get("production") or {}), "preview": lv(senv.get("preview") or {})}
    if any(bound.values()):
        for where in ("production", "preview"):
            if bound[where] != ["graniterecord-live"]:
                bad.append(f"the site's wrangler.toml binds LIVE for {where} to {bound[where]}, not graniterecord-live")
        if bound["top"] != ["graniterecord-live-local"]:
            bad.append(f"the site's wrangler.toml binds LIVE at the top level to {bound['top']}: `wrangler pages dev` "
                       "reads a local bucket, graniterecord-live-local, never the real one")
    # The README's commands: every one reaches the real bucket and production.
    readme = (live / "README.md").read_text(encoding="utf-8")
    # The commands are the lines of its fenced blocks: prose may name them.
    fenced = re.findall(r"^[ \t]*```[^\n]*\n(.*?)^[ \t]*```", readme, re.M | re.S)
    cmds = [ln.strip() for block in fenced for ln in block.splitlines() if "wrangler " in ln]
    for ln in cmds:
        if re.search(r"wrangler\s+r2\s+object\b", ln) and "--remote" not in ln.split():
            bad.append(f"README.md: `{ln}` lacks --remote, and wrangler's r2 object commands write "
                       "local storage without it")
        if re.search(r"wrangler\s+(deploy|secret)\b", ln) and not (
                "--config workers/live/wrangler.toml" in ln and "--env production" in ln):
            bad.append(f"README.md: `{ln}` does not name --config workers/live/wrangler.toml --env "
                       "production, so it would reach the local Worker's name")
    for want in ("wrangler r2 bucket create graniterecord-live",
                 "wrangler deploy --config workers/live/wrangler.toml --env production",
                 "wrangler secret put YOUTUBE_API_KEY", "wrangler secret put HEALTHCHECK_URL"):
        if not any(want in ln for ln in cmds):
            bad.append(f"README.md gives no `{want}`")
    # The switch: the four files, each one the Worker reads as it says.
    ctl = live / "control"
    names = sorted(p.name for p in ctl.glob("*")) if ctl.is_dir() else []
    if names != sorted(LIVE_CONTROL):
        bad.append(f"workers/live/control/ holds {names}, not {sorted(LIVE_CONTROL)}")
    for name, want in LIVE_CONTROL.items():
        p = ctl / name
        try:
            got = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            bad.append(f"workers/live/control/{name} is not JSON: {e}")
            continue
        if got != want or any(got.get(k) not in v for k, v in LIVE_CONTROL_VALUES.items()):
            bad.append(f"workers/live/control/{name} says {got}, not {want}")
        if not re.search(rf"--file workers/live/control/{re.escape(name)}\b.*--remote", readme):
            bad.append(f"README.md gives no command that puts control/{name}, with --remote")
    store = (live / "store.js").read_text(encoding="utf-8")
    m = re.search(r"CONTROL_VALUES = Object\.freeze\((\{.*?\})\);", store)
    try:
        js_values = json.loads(re.sub(r"(\w+):", r'"\1":', m.group(1))) if m else None
    except ValueError:
        js_values = None
    if js_values != {k: list(v) for k, v in LIVE_CONTROL_VALUES.items()}:
        bad.append(f"store.js's CONTROL_VALUES is {js_values}, not {LIVE_CONTROL_VALUES}")
    return bad


def _live_titles(root):
    """{video id: title} of every committed recording, collected/videos/."""
    out = {}
    for f in sorted((root / "collected/videos").glob("videos_*.csv")):
        with open(f, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("video_id") and row.get("title") is not None:
                    out[row["video_id"]] = row["title"]
    return out


def _live_problems_bite(root):
    """Each rule of _live_problems, broken alone on a copy of workers/live/,
    must be said in its own words: a rule that stopped catching anything fails
    here, not in silence. [what failed to be said]."""
    import tempfile
    host = _live_host(root)
    cases = (
        ("wrangler.toml", lambda t: t + '\nroutes = [{ pattern = "x.org/*" }]\n', "declares a route"),
        ("wrangler.toml", lambda t: t + '\n[env.staging]\nname = "x"\n', "has the environments"),
        ("wrangler.toml", lambda t: t.replace("[[r2_buckets]]", '[triggers]\ncrons = ["*/2 * * * *"]\n\n'
                                              "[[r2_buckets]]", 1), "a cron at the top level"),
        ("wrangler.toml", lambda t: t.replace('"*/2 * * * *"', '"*/5 * * * *"'), "not every 2 minutes"),
        ("wrangler.toml", lambda t: t.replace("workers_dev = false\n", "", 1),
         "the top level does not set workers_dev = false"),
        ("wrangler.toml", lambda t: t.replace("[env.production.observability]\nenabled = true", ""),
         "production does not keep Workers Logs"),
        ("wrangler.toml", lambda t: t.replace('name = "graniterecord-live"', 'name = "graniterecord-x"'),
         "the production Worker is named"),
        ("wrangler.toml", lambda t: t.replace('bucket_name = "graniterecord-live"\n', 'bucket_name = "x"\n'),
         "production binds"),
        ("wrangler.toml", lambda t: t.replace('bucket_name = "graniterecord-live-local"',
                                              'bucket_name = "graniterecord-live"'), "the top level binds"),
        ("wrangler.toml", lambda t: t + '\n[[kv_namespaces]]\nbinding = "K"\nid = "x"\n', "binds kv_namespaces"),
        ("wrangler.toml", lambda t: t.replace('SQL_HOST = "127.0.0.1"', 'SQL_HOST = "192.0.2.1"', 1),
         "top-level SQL_HOST"),
        ("clock.js", lambda t: t.replace("export const STEP = 2 * MINUTE;", "export const STEP = 3 * MINUTE;"),
         "STEP is not the cron's 2 minutes"),
        ("x.js", lambda t: f'const h = "{host}";\n', "names the General Court's SQL host"),
        ("x.js", lambda t: 'fetch("https://gc.nh.gov/x");\n', "names 'gc.nh.gov'"),
        ("x.js", lambda t: 'import { y } from "../../src/y.js";\n', "imports ../../src/y.js"),
        ("x.js", lambda t: 'const m = await import("node:net");\n', "imports node:net"),
        ("README.md", lambda t: t.replace("--file workers/live/control/on.json --remote",
                                          "--file workers/live/control/on.json"), "lacks --remote"),
        ("README.md", lambda t: t.replace("wrangler deploy --config workers/live/wrangler.toml --env production",
                                          "wrangler deploy --config workers/live/wrangler.toml"),
         "does not name --config workers/live/wrangler.toml --env"),
        ("control/on.json", lambda t: '{"youtube": "on", "sql": "test"}\n', "control/on.json says"),
        ("control/extra.json", lambda t: "{}\n", "workers/live/control/ holds"),
        ("store.js", lambda t: t.replace('sql: ["off", "test", "on"]', 'sql: ["off", "on"]'),
         "store.js's CONTROL_VALUES is"),
        ("fn:functions/api/live/x.js", lambda t: "export const f = s => s.put('state.json', '{}');\n", "calls put()"),
        ("fn:functions/api/live/x.js", lambda t: "export const f = s => s.delete(['control.json']);\n", "calls delete()"),
        ("fn:functions/api/live/x.js", lambda t: "export const f = s => s.list({ prefix: '' });\n", "calls list()"),
        ("fn:functions/api/live/x.js", lambda t: "export const f = e => e.env.LIVE.get('state.json');\n", "names env.LIVE"),
        ("fn:functions/api/live/_store.js", lambda t: t.replace("head: key => bucket.head(key),",
                                                                "head: key => bucket.head(key),\n    w: k => bucket.put(k, ''),"),
         "hands the bucket's put on"),
    )
    missed = []
    with tempfile.TemporaryDirectory() as tmp:
        fx = Path(tmp)
        shutil.copytree(root / "workers/live", fx / "workers/live")
        if (root / "functions/api/live").is_dir():
            shutil.copytree(root / "functions/api/live", fx / "functions/api/live")
        (fx / "src/fetch/gc_db").mkdir(parents=True)
        shutil.copy(root / "src/fetch/gc_db/probe_db.py", fx / "src/fetch/gc_db/probe_db.py")
        assert not _live_problems(fx), f"the copy itself breaks a rule: {_live_problems(fx)}"
        for name, change, says in cases:
            p = fx / (name[3:] if name.startswith("fn:") else f"workers/live/{name}")
            p.parent.mkdir(parents=True, exist_ok=True)
            before = p.read_text(encoding="utf-8") if p.is_file() else None
            after = change(before or "")
            assert after != before, f"the fixture for {says!r} no longer changes {name}"
            p.write_text(after, encoding="utf-8")
            got = _live_problems(fx)
            if not any(says in g for g in got):
                missed.append(f"{says!r} ({name}: {got[:2]})")
            if before is None:
                p.unlink()
            else:
                p.write_text(before, encoding="utf-8")
    return missed


@check("build", "the live Worker: live.gen.js is what live_gen.py writes, the cron and the bucket are "
       "production's alone, the General Court's host is named nowhere it may not be, the README's "
       "commands reach the real bucket, its switch's files are ones it reads, and it reads a title "
       "and a stream as the Python does; the votes reader's statements are SELECTs over four views "
       "that cast every column to nvarchar and take values through one builder, and its test hours "
       "miss the night's windows",
       needs=("live_gen", "livestreams", "dayfiles_from_db", "fetch_past_db", "refusal"))
def _live_layer(LG, LS, DF, FP, RF):
    """workers/live/ (the person, 26 October 2026: "defaults"; the design's
    §6.2 and §7.1). What its node suite cannot see, held here:

      - live.gen.js is what src/pages/live_gen.py writes from
        fetch_channel_index.CHANNELS and refusal.NIGHT_WINDOWS, with the
        session-title pattern: a copy nothing holds is how a constant drifts;
      - wrangler.toml: production alone has the cron, every 2 minutes as
        clock.js's STEP assumes, the name graniterecord-live and the bucket
        graniterecord-live; the top level, which `wrangler dev` runs, has
        neither; workers_dev = false and no route at either; nothing bound
        but the bucket;
      - the General Court's SQL host (probe_db.HOST) appears in workers/live/,
        tests/live/ and functions/api/live/ only as production's SQL_HOST, and
        a top-level host var is loopback: so no local run or test can reach
        it (the database half, a later branch, adds the client's own guard);
      - no live code names gc.nh.gov, gencourt or the follow database, and the
        Worker imports its own folder and workers/follow/common.js alone;
      - every `wrangler r2 object` line in its README carries --remote
        (wrangler's r2 object commands write local storage without it), and
        every deploy and secret line names its config and --env production;
      - workers/live/control/ is the four switches, each one the Worker
        reads as its name says, and store.js's allowed values are these;
      - the Worker's title stem is live_gen.stem on every committed title,
        and its session pattern matches every title that begins "House
        Session" or "Senate Session" and no other;
      - livestreams.status_of says of each synthetic answer in
        tests/live/youtube_items.json what the file says, and the Worker's
        statusOf (held there by youtube.test.js) differs from it only where
        it is meant to: an end time is "ended" while YouTube still reports
        P0D, and an ordinary upload is no stream.

    SECURITY.md naming workers/live/ is _follow_documents_live's."""
    root = _paths.ROOT
    if not (root / "workers/live/wrangler.toml").is_file():
        return "skip", "workers/live/ is not here"
    # What live.gen.js is written from, by path here as in live_gen.py, so that
    # a change to either reaches this check under preflight --changed.
    sources = ("src/fetch/youtube/fetch_channel_index.py", "refusal.py", "src/fetch/gc_db/probe_db.py",
               "src/fetch/gc_db/fetch_rollcalls_db.py", "records/docket_abbrev.json")
    assert sorted(sources) == sorted(p.as_posix() for p in LG.SOURCES), (
        f"live_gen.py reads {sorted(p.as_posix() for p in LG.SOURCES)}, and this check names "
        f"{sorted(sources)}: name each here, so preflight --changed runs this when one moves")
    try:
        ok, why = LG.current()
    except LG.SourceError as e:
        raise AssertionError(f"live_gen.py cannot read its sources: {e}") from None
    assert ok, f"{why}: run `{LG.COMMAND}` and commit workers/live/live.gen.js"
    bad = _live_problems(root)
    assert not bad, "; ".join(bad[:6]) + (f" (+{len(bad) - 6} more)" if len(bad) > 6 else "")
    missed = _live_problems_bite(root)
    assert not missed, "these rules no longer catch a file that breaks them: " + "; ".join(missed)
    # The votes reader's statements, login, host and test hours.
    _live_sql(LG, DF, FP, RF)

    # The synthetic answers, read by the night's Python as the file says.
    items = json.loads((root / "tests/live/youtube_items.json").read_text(encoding="utf-8"))["items"]
    wrong = []
    for c in items:
        py, js, it = LS.status_of(c["item"]), c["js"], c["item"]
        ls = it.get("liveStreamingDetails")
        if py != c["python"]:
            wrong.append(f"{c['name']}: status_of says {py}, the file {c['python']}")
        if not (py == js or (js == "ended" and (ls or {}).get("actualEndTime") and py in ("live", "finished"))
                or (js == "upload" and not ls and py == "finished")):
            wrong.append(f"{c['name']}: the Worker reads {js} where the night reads {py}")
    assert not wrong, "; ".join(wrong)
    told = {c["js"] for c in items}
    assert {"live", "upcoming", "ended", "never", "upload"} <= told, (
        f"tests/live/youtube_items.json covers {sorted(told)}: each of live, upcoming, ended, never "
        "and upload needs an answer")

    # Every committed title, stemmed by the Worker and by live_gen.py.
    titles = _live_titles(root)
    if not titles:
        return "ok", (f"live.gen.js current; the configuration, host, README and switch hold; "
                      f"{len(items)} synthetic answers read alike; no collected/videos/ here, so the "
                      "stem was not compared")
    node = shutil.which("node") or shutil.which("node.exe")
    names = list(titles.values())
    want = [(LG.stem(t), LG.session_of(t)) for t in names]
    sessions = sum(1 for _, s in want if s)
    honest = [t for t in names if re.match(r"\s*(house|senate)\s+session\b", t, re.I)]
    assert sessions == len(honest) and all(LG.session_of(t) for t in honest), (
        f"SESSION_TITLE matches {sessions} committed titles, and {len(honest)} begin House Session "
        "or Senate Session")
    assert sessions >= 172, f"only {sessions} session titles matched; 172 were committed on 26 October 2026"
    if not node:
        return "ok", (f"live.gen.js current; the rest holds; {sessions} session titles of "
                      f"{len(names):,}; node is not on PATH, so the Worker's stem was not compared")
    src = ("import { stem, sessionOf } from " + json.dumps((root / "workers/live/youtube.js").as_uri())
           + ";\nlet s = ''; process.stdin.on('data', d => s += d); process.stdin.on('end', () => "
           "process.stdout.write(JSON.stringify(JSON.parse(s).map(t => [stem(t), sessionOf(t)]))));\n")
    r = _run([node, "--input-type=module", "-e", src], input=json.dumps(names),
             capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"node could not stem the titles: {(r.stderr or r.stdout).strip()[-400:]}"
    got = [tuple(x) for x in json.loads(r.stdout)]
    differ = [f"{t!r}: the Worker {g}, live_gen {w}" for t, g, w in zip(names, got, want) if g != w]
    assert not differ, f"{len(differ)} titles stem apart: " + "; ".join(differ[:4])
    return "ok", (f"live.gen.js current; the configuration, host, README and switch hold; "
                  f"{len(items)} synthetic answers read alike; {len(names):,} committed titles stem "
                  f"alike, {sessions} of them session streams")


# The doubtful sittings a person has still to rule on, each with its reason.
# A day flagged and NOT here fails the check below if it is 2017 or later, or
# on a weekend or a state holiday; older days flagged only because their
# journal belongs to another sitting are listed as warnings -- almost all are
# rows dated by the moment they were entered, which measured no worse than any
# bulk re-dating (98.3% against roll calls). Remove a line when it is decided.
#
# Decided on 24 September 2026 and gone from the list: 24, 28 and 29 May 2024,
# recess business now on the 23 May sitting (session_days.unmarked_recess),
# and the joint-rule weekends of 1 July 1990 and 1995, which are no sitting.
KNOWN_DOUBTFUL = {
    ("H", "2012-03-11"): "one row dated by the moment it was entered, a Sunday; "
                         "its journal is the 7 March 2012 sitting's",
}


@check("data", "no sitting page for a day the chamber did not sit")
def _no_phantom_sittings():
    """Eleven pages for sittings that never happened were live.

    One mistyped docket date publishes a whole sitting: "The House, Saturday
    19 September 2026" was a reconsideration of 19 August with its month typed
    09. docket_corrections.json put the eleven right; this is how the twelfth
    is noticed rather than published. session_days.doubtful() flags a day on a
    weekend or a state holiday, after the build, or whose every journal
    citation belongs to another sitting with no roll call of its own.

    A day after the build is never published -- build_session_pages skips it
    -- so that is checked on the pages, not the record: the Senate enters rows
    up to ten days ahead, and the nightly must not stop on that.
    """
    import datetime
    narr = Path("narratives.json")
    if not narr.exists():
        return "skip", "no narratives.json here"
    import session_days as SD
    today = datetime.date.today()
    days = _sittings_on_disk(SD, narr)
    rc = SD.read_rollcall_dates(
        [p for p in sorted(Path("records/rollcalls").glob("RollCallSummary_*.txt"))
         + [Path("RollCallSummary.txt")] if p.exists()])
    flags = SD.doubtful(days, today, rc)
    new, warn = [], []
    for key, why in sorted(flags.items()):
        why = [w for w in why if w != "after the build date"]
        if not why or key in KNOWN_DOUBTFUL:
            continue
        hard = key[1] >= "2017" or any(w in SD.DAYNAME or w == "a state holiday"
                                       for w in why)
        (new if hard else warn).append(f"{key[0]} {key[1]} ({'; '.join(why)})")
    published_ahead = sorted(
        f"{p.parent.name} {p.stem}" for p in Path("site/session").glob("*/*.html")
        if re.fullmatch(r"\d{4}-\d\d-\d\d", p.stem) and p.stem > today.isoformat())
    assert not published_ahead, (
        "sitting pages dated after today are on disk: "
        + ", ".join(published_ahead[:6]))
    assert not new, (
        f"{len(new)} sitting day(s) the record itself doubts, not on the known "
        "list: " + "; ".join(new[:5]) + ". A mistyped docket date goes in "
        "docket_corrections.json with its evidence; a day a person has ruled "
        "on goes in KNOWN_DOUBTFUL with the reason")
    resolved = sorted(f"{k[0]} {k[1]}" for k in KNOWN_DOUBTFUL if k not in flags)
    return "ok", (f"{len(days):,} sittings; {len(KNOWN_DOUBTFUL) - len(resolved)} "
                  "known doubtful days await a decision; "
                  f"{len(warn)} database-era days flagged as warnings"
                  + (f" (e.g. {warn[0]})" if warn else "")
                  + (f"; no longer doubtful: {', '.join(resolved)}"
                     if resolved else ""))


@check("session", "a House journal's running heads are found once, for the file flat and with "
       "its lines, and give what clean() gives each way", needs=("journal_days",))
def _journal_clean_both(JD):
    """read_year cleaned every House journal twice, once flat and once with
    its lines kept, and the running-head pattern read the whole file each
    time (29 October 2026: 36 s of the sitting pages' 314 under a profiler;
    the same answers on all 573 files on disk, 33 s to 20 s). clean_both()
    finds the heads once. This holds it to clean()'s two answers on the
    journal fixtures and on heads that stand mid-line, between lines, across
    a page break, at the start and the end, with Windows line ends and next
    to a word broken over the line; and holds read_year to the one pass."""
    import inspect
    heads = ("7MARCH2018HOUSERECORD", "6 MARCH 2013 HOUSE RECORD 12",
             "12 14 FEBRUARY 2019 HOUSE RECORD", "  3  APRIL  2020  HOUSE   RECORD  ")
    texts = [_JOURNAL_RECONSIDER, _JOURNAL_MOTION_AFTER, _JOURNAL_DECIDED, _JOURNAL_WALK,
             _JOURNAL_WALK_MORE, "", "no head at all", "moved that the commit-\ntee adjourn"]
    for h in heads:
        texts += [h, f"{h} first line", f"the last line {h}", f"the motion was {h} adopted.",
                  f"was adopted.\n{h}\nHB 422-FN, increasing", f"page one\f{h}\fpage two",
                  f"a line\r\n{h}\r\nthe next", f"the commit-\n{h}\ntee met", f"{h}{h}\n{h}"]
    texts.append("\n".join(texts))
    bad = [t for t in texts if JD.clean_both(t) != (JD.clean(t), JD.clean(t, lines=True))]
    assert not bad, f"clean_both and clean() differ on {len(bad)} text(s), the first {bad[0][:80]!r}"
    src = inspect.getsource(JD.read_year)
    assert "clean_both(" in src and "clean(raw" not in src, (
        "read_year cleans each journal twice again")
    return "ok", f"{len(texts)} texts the same both ways; read_year finds the heads once"


@check("session", "a House journal's running heads are looked for only just before a HOUSE "
       "RECORD, and found exactly where the pattern tried at every character finds them",
       needs=("journal_days",))
def _journal_furniture(JD):
    """furniture() tries FURNITURE only where the walk back from a HOUSE
    RECORD can reach (30 October 2026: the same 31,281 heads in all 3,632
    journal and calendar files on disk, 45 s to 4 s). Held here to
    FURNITURE.finditer, and clean() to FURNITURE.sub, on the heads the
    journals print and on what would trip the walk: the longest month and a
    word run into it, page numbers either side, heads back to back, long runs
    of white space, a head split over lines and pages, other scripts' spaces
    and digits, the words without a date, and none at all."""
    heads = ("7MARCH2018HOUSERECORD", "6 MARCH 2013 HOUSE RECORD 12",
             "12 14 FEBRUARY 2019 HOUSE RECORD", "  3  APRIL  2020  HOUSE   RECORD  ",
             "110 21 SEPTEMBER 2016 HOUSE RECORD 111", "21september2016houserecord",
             "4 MAY\n2017\fHOUSE\nRECORD", "7\u2003MARCH\u20032018\u2003HOUSE RECORD",
             "\u0667 MARCH 2018 HOUSE RECORD")
    texts = [_JOURNAL_RECONSIDER, _JOURNAL_MOTION_AFTER, _JOURNAL_DECIDED, _JOURNAL_WALK,
             _JOURNAL_WALK_MORE, "", "no head at all", "HOUSE RECORD", "the HOUSE RECORD of 2018",
             "MARCH 2018 HOUSE RECORD", "7 MARCH 18 HOUSE RECORD"]
    for h in heads:
        texts += [h, f"word{h}", f"SEPTEMBERX{h}", f"OCTOBERNOVEMBER{h}", f"{h}{h}", f"{h} {h}",
                  " " * 300 + h, f"12345 {h}", f"the motion was {h} adopted.", f"{h}\n{h}12"]
    texts.append("\n".join(texts))
    # The walk back rests on every month being plain letters: "SEPT." or any
    # regex syntax would stop it short and lose heads.
    assert all(re.fullmatch(r"[A-Z]+", m) for m in JD._MON.split("|")), JD._MON
    bad = [t for t in texts
           if [m.span() for m in JD.furniture(t)] != [m.span() for m in JD.FURNITURE.finditer(t)]]
    assert not bad, f"furniture() and FURNITURE.finditer differ on {len(bad)}, the first {bad[0][:80]!r}"
    norm = lambda t: t.replace("\r\n", "\n").replace("\r", "\n")
    for t in texts:
        want = JD.HYPHEN_WRAP.sub(r"\1\2", JD.FURNITURE.sub(" ", norm(t)))
        assert JD.clean(t) == want, f"clean() is not FURNITURE.sub's on {t[:80]!r}"
    return "ok", f"{len(texts)} texts, the same heads found either way"


_DEBATE_RUNON = """Rep. Nicholas Germana moved that the debate on HB 148, permitting classification of individuals based on
biological sex in certain circumstances, be printed in the Journal. Motion adopted.

                                                            DEBATE ON HB 148

Representative Layon: Thank you, Mister Speaker. HB 148 is a common-sense bill. I urge my colleagues to press
the green button and override the governor's veto of this bill. Thank you, Mister Speaker.
                                           REGULAR CALENDAR (CONT'D)
Representative Turer: Thank you, Mister Speaker. If I know that this exact language was vetoed by our
previous governor, then wouldn't I press the red button to uphold this very prudent veto? Thank you.
                                              HB 148 CONT'D
Speaker Steven Smith: The question is whether HB 148, notwithstanding the governor's veto, should become
law? This is a roll call vote. Failing to meet the two-thirds margin, the motion fails. 188 to 165.
                    17DECEMBER2025HOUSERECORD                                                      13

                                       GOVERNOR'S VETO MESSAGE ON HB 319-FN

By the authority vested in me, pursuant to part II, Article 44 of the New Hampshire Constitution, on June
3, 2025, I have vetoed House Bill 319, relative to the responsibility of local school districts to provide
transportation for pupils in kindergarten.
Representative Ammon: Thank you, Mister Speaker. I rise in favor of overriding the veto of HB 319 today.

                                        YEAS 182 - NAYS 173
"""


@check("session", "a printed debate ends at the next heading, a heading that ends on a bill's "
       "number among them, or at the next bill's report, and goes on over the page's continued "
       "headings",
       needs=("journal_days",))
def _debate_ends_at_numbered_heading(JD):
    """HB 148's override debate of 17 December 2025 ran on through
    "GOVERNOR'S VETO MESSAGE ON HB 319-FN" -- the veto message, Rep. Ammon's
    speech on HB 319 and its roll call -- because the heading pattern took no
    digit (the owner's report, 29 October 2026). Nine debates on disk ran on
    the same way. debates() ends a debate at DEBATE_END now, NEXT_HEAD with
    a bill's number allowed at the end; a heading that goes on after the
    number, or carries none -- REGULAR CALENDAR (CONT'D), HB 148 CONT'D -- is
    the same debate over the page. The fixture is the Journal's own lines,
    shortened."""
    got = JD.debates(JD.clean(_DEBATE_RUNON))
    assert [d["bill"] for d in got] == ["HB148"], f"the fixture's debates: {got}"
    who = [w for w, _s in got[0]["speeches"]]
    said = " ".join(s for _w, s in got[0]["speeches"])
    assert who == ["Representative Layon", "Representative Turer", "Speaker Steven Smith"], (
        f"HB 148's debate is spoken by {who}: a continued heading cut it short, or "
        "HB 319's speaker was read into it")
    assert said.endswith("188 to 165.") and "authority vested" not in said, (
        "HB 148's debate runs on into HB 319's veto message: "
        f"...{said[-120:]!r}")
    # And where the calendar goes on with no heading: the next bill's report,
    # its recommendation in capitals over a line end, ends the debate before
    # it; a bill's number that a speech wraps onto a line of its own does
    # not (HB 1555-FN of 30 January 2008; HB 1279's debate of 28 March 2024).
    nxt = JD.debates(JD.clean(
        "Rep. Wendelboe moved that the debate on HB 1428, naming a portion of the Franconia\n"
        "Notch Parkway after Corporal Bruce McKay, be printed in the Journal. Motion adopted.\n\n"
        "                                                DEBATE ON HB 1428\n\n"
        "Rep. Gile: Thank you, Mister Speaker. We have a much more important bill to name than\n"
        "HB 1279, which we sent on already, and I ask you to support Interim Study today.\n"
        "Rep. Ward: Thank you very much. Please support Interim Study.\n"
        "                                       REGULAR CALENDAR (CONT'D)\n\n"
        "HB 1555-FN, relative to an E-Z Pass discount for residents of Merrimack. INEXPEDIENT\n"
        "TO LEGISLATE.\n"
        "Rep. Sprague: This bill would have given all E-Z Pass account holders a discount.\n"))
    assert [w for w, _s in nxt[0]["speeches"]] == ["Rep. Gile", "Rep. Ward"] and \
        "E-Z Pass" not in nxt[0]["speeches"][-1][1], (
            f"a debate runs on into the next bill's report, or stops at a number a speech "
            f"wrapped: {nxt[0]['speeches']}")
    assert JD.NEXT_HEAD.pattern == r"^[ \t]{4,}[A-Z][A-Z' ’.,&-]{6,}[ \t]*$", (
        "NEXT_HEAD changed: journal_bills and the consent and leave readers were "
        "measured on it as it was, and only debates() takes a bill's number")
    return "ok", ("HB 148's debate ends on its own vote, over two continued headings; "
                  "HB 1428's at the next bill's report, not at a number a speech wrapped")


def _opening_letters(pattern):
    """The letters a pattern's matches can open on, where each top-level
    alternative opens on \\b and a letter, or on \\b and a group of such
    words: "\\b(?:moved|offered)\\b|\\bwithdrew ..." gives m, o, w. Anything
    else gives None, which fails the check that asks: it cannot say."""
    def split(p):
        out, depth, cur, i = [], 0, "", 0
        while i < len(p):
            c = p[i]
            if c == "\\":
                cur += p[i:i + 2]
                i += 2
                continue
            depth += c == "("
            depth -= c == ")"
            if c == "|" and depth == 0:
                out.append(cur)
                cur = ""
            else:
                cur += c
            i += 1
        return out + [cur]
    got = set()
    for alt in split(pattern):
        alt = alt[2:] if alt.startswith("\\b") else alt
        if alt.startswith("(?:"):
            depth, end = 0, None
            for j, c in enumerate(alt):
                depth += c == "("
                depth -= c == ")"
                if depth == 0:
                    end = j
                    break
            inner = _opening_letters(alt[3:end])
            if inner is None:
                return None
            got |= inner
        elif alt[:1].isalpha():
            got.add(alt[0])
        else:
            return None
    return got


@check("session", "the night's check of the House's speakers reads the Journal's patterns where "
       "they can begin")
def _speakers_check_found():
    """_every_speaker_where_the_journal_decides read DECIDED, MOTION_EVENT,
    SPOKE and MOVED_SPOKE with finditer from every character of every House
    day: 20 of its 53 seconds on the night. decisions() and found() give the
    same matches (_journal_found_is_finditer; the same rows on all 538 days
    on disk, 29 October 2026) in 7. Undone, the night is slower and nothing
    else would say so."""
    import inspect
    import journal_days as J
    src = inspect.getsource(_speakers_against_journal)
    slow = [n for n in ("DECIDED", "MOTION_EVENT", "SPOKE", "MOVED_SPOKE")
            if f"J.{n}.finditer(" in src]
    assert not slow and "J.decisions(text)" in src, (
        f"the speakers check runs {slow or ['DECIDED']} from every character again")
    # AND EACH CLASS STILL HOLDS EVERY CHARACTER ITS PATTERN CAN BEGIN WITH.
    # Every alternative opens on \b and a letter; a pattern given one that
    # opens on another ("\blaid ...") would lose those matches here and
    # nothing else would say so. The class is the one the check passes, read
    # from its source; each letter a match can begin with is tried.
    pairs = {n: re.search(r"J\.found\(J\." + n + r",\s*text,\s*\"([^\"]+)\"\)", src)
             for n in ("MOTION_EVENT", "SPOKE", "MOVED_SPOKE")}
    assert all(pairs.values()), f"the speakers check's classes are not where this reads: {pairs}"
    every = "".join(map(chr, range(0x110000)))
    for n, m in pairs.items():
        rx, first = getattr(J, n), m.group(1)
        # Where the pattern can begin: the code points a match of it can open
        # on, each tried with the rest of a real match after it.
        heads = {x.group(0)[0] for x in rx.finditer(" " + "  ".join(
            (_JOURNAL_RECONSIDER, _JOURNAL_MOTION_AFTER, _JOURNAL_DECIDED, _JOURNAL_WALK,
             _JOURNAL_WALK_MORE)))}
        assert heads and all(re.fullmatch(first, c) for c in heads), (
            f"{n} begins a match on {sorted(heads)}, and {first} misses one")
        letters = _opening_letters(rx.pattern)
        assert letters and all(re.fullmatch(first, c) for l in letters for c in (l.lower(), l.upper())), (
            f"{n} opens on {sorted(letters)}, and {first} misses one")
        read = set(re.findall(first, every, rx.flags & re.I))
        assert all(re.fullmatch(first, c) for c in read), (
            f"{first} misses a character {n} can begin with")
    return "ok", "decisions() and found() for the four patterns, each class whole"


@check("session", "a journal pattern found only where it can begin is finditer's own list",
       needs=("journal_days", "session_days"))
def _journal_found_is_finditer(JD, SD):
    """bill_marks and _journal_day ask journal_days.found() for each pattern,
    which tries it only where a character of the class it is given begins a
    match, and decisions() for DECIDED, which tries it only where a verdict
    follows (16 October 2026, private/BUILD_SPEED.md, item C). Both were
    proved the same as finditer over every journal block on disk; this holds
    them to it on the journal fixtures as written, cleaned and joined, and on
    a text with a match at its first character, matches back to back, the
    letters re.IGNORECASE reads from outside ASCII and verdicts in every
    case. A class short of a letter's other case, or a pattern edited to begin
    on a letter its class does not hold, loses matches here before it loses
    them on a page. And the two still ask: undone, the five steps that load
    the sitting days are each slower, and nothing else would say so."""
    odd = ("HB 1, first.\fSB 2, second.\n  HB 3-FN, third. Rep. Kurk moved that the House "
           "reconſider its action whereby it passed SB 9. Rep. Ball moved that the House "
           "RECONSIDER its action whereby it killed HB 4.Reps. Ohm and Lı offered the "
           "following: RESOLVED, that. yeas 12 - nays 3YEAS 4 NAYS 5 On a division vote, 12 "
           "members having voted in the affirmative and 4 in the negative.\nAdopted.\n\n"
           "The report was ADOPTED. Floor amendment failed; motion LOST. Mr. Lee moved that "
           "the House reconsider its action whereby it tabled CACR 7. İ")
    texts = [_JOURNAL_RECONSIDER, _JOURNAL_MOTION_AFTER, _JOURNAL_DECIDED, _JOURNAL_WALK,
             _JOURNAL_WALK_MORE]
    texts += [JD.clean(t) for t in texts] + [JD.clean(t, lines=True) for t in texts]
    texts += ["\n".join(texts), odd, odd.replace("ſ", "s").replace("ı", "i").replace("İ", "I")]
    # The classes the code gives found() itself: _journal_day's read of a
    # House and a Senate journal of these, which asks bill_marks too.
    root = Path(tempfile.mkdtemp())
    was = (JD.HOUSE, JD.SENATE, dict(SD._SAT), dict(JD._AT), JD.decisions)
    voiced = []
    try:
        for d, head in (("H", "HOUSE JOURNAL NO. 5\n\nThursday, February 13, 2025\n\n"),
                        ("S", "The Senate met at 10:00 a.m., February 13, 2025.\n")):
            (root / d / "2025").mkdir(parents=True)
            (root / d / "2025" / "J.txt").write_text(head + "\n".join(texts), encoding="utf-8")
        JD.HOUSE, JD.SENATE = root / "H", root / "S"
        JD.decisions = lambda s: (voiced.append(s), was[4](s))[1]
        SD._SAT.clear()
        JD._AT.clear()
        assert SD._journal_day("H", "2025-02-13") and SD._journal_day("S", "2025-02-13"), (
            "a fixture journal opens no sitting")
        asked = list(JD._AT)
    finally:
        JD.HOUSE, JD.SENATE, JD.decisions = was[0], was[1], was[4]
        SD._SAT.clear()
        SD._SAT.update(was[2])
        JD._AT.update(was[3])
        shutil.rmtree(root, ignore_errors=True)
    names = {rx.pattern for rx, _first in asked}
    want = (JD.BILL_HEAD, JD.CONFERENCE_HEAD, JD.RECONSIDER, JD.RESOLUTION_OFFERED, JD.TALLY,
            SD.SENATE_TALLY, SD.JOURNAL_DIVISION, SD.JOURNAL_BILL)
    assert voiced and all(rx.pattern in names for rx in want), (
        "bill_marks or _journal_day tries a pattern at every character again: "
        f"{[rx.pattern[:30] for rx in want if rx.pattern not in names] or 'DECIDED'}")
    # Every character a pattern's own case rule reads as one of its class is
    # in the class as written (the Kelvin sign, ſ, ı and İ are why).
    every = "".join(map(chr, range(0x110000)))
    for rx, first in asked:
        read = set(re.findall(first, every, rx.flags & re.I))
        assert all(re.fullmatch(first, c) for c in read), (
            f"{first} misses a character {rx.pattern[:30]!r} can begin with")
    rows = lambda it: [(m.span(), m.groups()) for m in it]
    for t in texts:
        for rx, first in asked:
            assert rows(JD.found(rx, t, first)) == rows(rx.finditer(t)), (
                f"found() is not finditer for {rx.pattern[:50]!r}")
        joined = re.sub(r"(?<!\n)\n(?!\n)", " ", t)
        assert SD.LINE_BREAK.sub(" ", t) == joined, "LINE_BREAK joins the lines another way"
        for s in (t, joined):
            assert rows(JD.decisions(s)) == rows(JD.DECIDED.finditer(s)), (
                "decisions() is not DECIDED.finditer")
    return "ok", (f"{len(asked)} patterns and DECIDED read only where they can begin, "
                  "as finditer reads them")


@check("build", "the officers' mentions kept between processes are the mentions the journals give",
       needs=("officers",))
def _officers_kept(OF):
    """officers.load() keeps the journals' mentions in .build_cache/ (KEPT, 23
    October 2026): the site data reads them and the session pages, a process
    later, take them as it left them, and so does the next night when its
    journals have not moved. Laid out as a build has them, in journals/,
    journals_senate/ and calendars/ of the working folder: a second process
    reads no journal and gets what the first read; a journal that changes is
    read again; and a fixture's own folders are read afresh and leave nothing
    behind."""
    root = Path(tempfile.mkdtemp(prefix="gr-officers-kept-"))
    try:
        for name, text in _OFFICERS_FILES.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding="utf-8")
        here = str(_paths.ROOT)
        code = "\n".join([
            "import sys, json",
            "sys.path.insert(0, sys.argv[1])",
            "import _paths",
            "import officers as OF",
            "if sys.argv[2] == 'kept':",
            "    def boom(*a, **k):",
            "        raise SystemExit('the journals were read again')",
            "    OF.house_mentions = OF.senate_mentions = OF.calendar_mentions = boom",
            "if sys.argv[2] == 'elsewhere':",
            "    got = OF.load(OF.Path('other/journals'), OF.Path('other/journals_senate'),",
            "                  OF.Path('other/calendars'))",
            "else:",
            "    got = OF.load()",
            "print(json.dumps(got, ensure_ascii=False))"])

        def load(how):
            return _run([sys.executable, "-c", code, here, how], cwd=root,
                        capture_output=True, text=True, timeout=120)
        first = load("read")
        assert first.returncode == 0, (first.stderr or first.stdout)[-400:]
        assert json.loads(first.stdout)[1], "the fixture's journals gave no mention"
        cache = root / ".build_cache" / f"{OF.KEPT}.json.gz"
        assert cache.exists(), "officers.load() kept nothing for the next process"
        second = load("kept")
        assert second.returncode == 0, (
            "the second process read the journals again: " + (second.stderr or "")[-300:])
        assert second.stdout == first.stdout, "the kept mentions are not the mentions read"
        j = next(p for p in sorted((root / "journals").rglob("*.txt")))
        j.write_text(j.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        moved = load("kept")
        assert moved.returncode != 0 and "read again" in (moved.stderr or ""), \
            "a journal changed and its kept mentions were used"
        cache.unlink()
        other = load("elsewhere")
        assert other.returncode == 0 and not cache.exists(), \
            "folders other than the build's own left a cache behind"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("a second process takes the first one's mentions and reads no journal; a "
                  "journal changed is read again; other folders keep nothing")


@check("data", "every bill the House withdrew is on the record")
def _withdrawn_on_record():
    """Each bill journal_bills.json reads as introduced and withdrawn is in
    data/bills.json under its term -- as the General Court's own record where
    its files carry it, and otherwise as the journal's. Nine bills of
    2025-2026 are in none of those files, and a step that dropped them would
    fall below every count the nightly guards: the census only stops a fall
    of 2%. So it is counted here, by name.
    """
    jp, bp = Path("journal_bills.json"), Path("data/bills.json")
    if not bp.exists():
        return "skip", "no data/bills.json here; run build_data.py"
    # NOT A SKIP WHERE THE JOURNALS ARE HERE. The file is missing then
    # because the step did not run or refused, and the nine bills are not on
    # the record: exactly what this check is for.
    J = imp("journal_bills")
    if not jp.exists():
        assert not (J and J.years()), (
            "the House Journals from 2025 are here and journal_bills.json is not, so "
            "build_data added no withdrawn bill: run python3 src/parse/journal_bills.py, then "
            "build_data.py")
        return "skip", ("no journal_bills.json and no journals/ from 2025 here; "
                        "journal_bills.py writes it from them before build_data reads it")
    jb = json.loads(jp.read_text(encoding="utf-8"))
    bills = json.loads(bp.read_text(encoding="utf-8"))
    # The withdrawn, which is what this counts: the file also holds the one
    # bill of an earlier term the journal gives (journal_bills.EARLIER),
    # and _past_measures_on_record holds that one to the record.
    want = [(t, b) for t, bb in jb.items() for b, r in bb.items() if "withdrawn" in r]
    assert want, ("journal_bills.json records no withdrawn bill, and the journals of "
                  "2025-2026 print nine")
    missing = [f"{b} {t}" for t, b in want if b not in (bills.get(t) or {})]
    assert not missing, ("the House Journal records these as introduced and withdrawn, "
                         "and data/bills.json does not have them: " + ", ".join(missing))
    own = sum(1 for t, b in want if (bills[t][b] or {}).get("journal"))
    return "ok", (f"{len(want)} withdrawn bill(s) on the record, {own} of them as the "
                  "House Journal's")


# journals/2021/HJ003.txt: the entry (lines 6280-6282), the first lines of
# the majority's report, the question and the count (6299-6306), and the foot
# of the roll call, where the outcome is printed through the names' columns
# (6455-6469). The 351 names between are cut to the lines kept here.
_HJ3_2021_HB459 = """\
                  HOUSE JOURNAL NO. 3

                              Wednesday, February 24, 2021

The House assembled at 9:30 a.m., and was called to order by the Speaker.

                            24FEBRUARY2021HOUSERECORD                                                               83

HB 459, prohibiting a transfer of funds within an adopted budget to a general ledger line item in such budget
that contains an entry of zero dollars. MAJORITY: INEXPEDIENT TO LEGISLATE. MINORITY: OUGHT
TO PASS WITH AMENDMENT.
Rep. Laurel Stavis for the Majority of Municipal and County Government. This is a bill that seeks to impose
severe penalties on any public official in our state who may transfer funds into an approved budget ledger
line containing zero dollars. Vote 11-7.
84                     24FEBRUARY2021HOUSERECORD

The question being adoption of the majority committee report of Inexpedient to Legislate.
Rep. Silber spoke against.
Rep. Stavis spoke in favor.
Rep. Rung requested a roll call; sufficiently seconded.

                                             YEAS 198 - NAYS 153

Bordes, Mike           Harvey-Bolia, Juliet       YEAS - 198                              Ploszaj, Tom
Trottier, Douglas                                 BELKNAP
                                                                                          MacDonald, John

Ankarberg, Aidan                     Bailey, Glenn              STRAFFORD
Harrington, Michael                  Hayward, Peter
Kittredge, Mac                       Newton, Clifford                           DeLemus, Susan
Wuelper, Kurt                                                                   Horgan, James
                                     Callum, John                               Pitre, Joseph
Aron, Judy
                     committee report was                         SULLIVAN
and the majority
                                                                                Rollins, Skip

                                                       adopted.
86  24FEBRUARY2021HOUSERECORD

                                                          REFERRAL DECLINED

Rep. Abbas, Chairman of the Committee on Criminal Justice and Public Safety, under the provisions of House
Rule 47 (f), declined the referral of HB 625-FN, relative to the protection of fetal life.
"""

# db/past/PastDocket.psv lines 470541 and 470544-470546: HB 459 of 2021, LSR
# 2021-0678, as narrative.past_docket_rows hands rows to build().
_PAST_DOCKET_HB459 = [
    ("01/10/2021 13:39:00", "  Introduced (in recess of) 01/06/2021 and referred to "
     "Municipal and County Government  HJ 2  P. 49"),
    ("02/18/2021 08:22:00", "Majority Committee Report: Inexpedient to Legislate   "
     "(Vote 11-7; RC)  HC 12  P. 23"),
    ("02/18/2021 08:22:00", "Minority Committee Report: Ought to Pass with Amendment "
     "# 2021-0250h"),
    ("02/24/2021 19:59:00", "Inexpedient to Legislate: MA RC 198-153 02/24/2021  "
     "HJ 3  P. 83"),
]


@check("status", "the one bill of an earlier term the House Journal gives is read whole, "
                 "says Killed, and is the docket's wherever its docket is here",
       needs=("journal_bills", "build_data", "build_site_v2", "narrative"))
def _journal_decided(J, BD, B, N):
    """HB 459 of 2021 is in the list the bill search gave for no term and in
    the database's table of past bills not at all; the House Journal prints
    its introduction and the vote that killed it, 198-153, and
    journal_bills.EARLIER names it.

    THE VOTE'S OUTCOME IS PRINTED THROUGH THE ROLL CALL'S COLUMNS -- "committee
    report was", "and the majority", "adopted." on three lines among the
    names -- so it is read loosely and held to the count. A count the
    question lost, or no word of what became of the report, is a problem and
    writes nothing; a sitting that does not take the bill up is nothing.

    The record carries "decided" where the nine withdrawn bills carry
    "withdrawn". With no docket on the machine the page is the journal's:
    Killed, credited to the House Journal, the vote one line of its journey.
    With its docket here (the past docket view) the page is the docket's, and
    a note says the title and sponsors are the journal's. Its sponsors keep
    the seat the journal printed: Rep. Silber sat for Belknap 2 in 2021.
    """
    import contextlib
    import io
    assert J.EARLIER == {2021: ("HB459",)}, (
        f"journal_bills.EARLIER is now {J.EARLIER}: each bill named there is read "
        "from a year no list was measured on, so this check should hold its text too")
    root = Path(tempfile.mkdtemp())
    try:
        def decided(text, bid="HB459"):
            f = root / "HJ003.txt"
            f.write_text(text, encoding="utf-8")
            lines = J.read_lines(f)
            pg = J.pages(lines)
            (start, end, date), = J.sittings(lines)
            return J._decided(lines, pg, start, end, bid, lambda i: {
                "date": date, "journal": "HJ 3", "page": pg[i], "file": f.name,
                "line": i + 1})
        got, why = decided(_HJ3_2021_HB459)
        assert why is None and got == {
            "date": "2021-02-24", "journal": "HJ 3", "page": 83, "file": "HJ003.txt",
            "line": 9, "question": "Inexpedient to Legislate", "vote": "198-153",
            "how": "roll call", "carried": True}, (got, why)
        # The count says the question lost and the words say adopted: neither.
        got, why = decided(_HJ3_2021_HB459.replace("YEAS 198 - NAYS 153",
                                                   "YEAS 153 - NAYS 198"))
        assert got is None and why and "not read" in why, (got, why)
        # No word of what became of it.
        got, why = decided(_HJ3_2021_HB459.replace(
            "                                                       adopted.\n", "\n"))
        assert got is None and why and "not read" in why, (got, why)
        # A bill the sitting does not take up, and one it only mentions.
        assert decided(_HJ3_2021_HB459, "HB460") == (None, None)
        assert decided(_HJ3_2021_HB459, "HB625") == (None, None)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Into the record: "decided" travels as "withdrawn" does.
    jrec = {"bill": "HB459", "designation": "HB 459", "suffix": "", "chamber": "H",
            "year": "2021", "committee": "Municipal and County Government",
            "title": "prohibiting a transfer of funds within an adopted budget to a "
                     "general ledger line item in such budget that contains an entry of "
                     "zero dollars.",
            "sponsors": ["Silber, Belk. 2", "Sylvia, Belk. 6"],
            "introduced": {"date": "2021-01-06", "journal": "HJ 2", "page": 49},
            "decided": {"date": "2021-02-24", "journal": "HJ 3", "page": 83,
                        "question": "Inexpedient to Legislate", "vote": "198-153",
                        "how": "roll call", "carried": True}}
    root = Path(tempfile.mkdtemp())
    try:
        p = root / "journal_bills.json"
        p.write_text(json.dumps({"2021-2022": {"HB459": jrec}}), encoding="utf-8")
        by_term = {"2021-2022": {"HB1": {"bill": "HB1", "lsr_year": "2021",
                                         "archived": True}}}
        with contextlib.redirect_stdout(io.StringIO()):
            added = BD.add_journal_bills(by_term, p)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    rec = by_term["2021-2022"].get("HB459") or {}
    assert added == {"2021-2022": {"HB459": rec}} and rec.get("archived") is True, added
    assert rec["journal"]["decided"]["vote"] == "198-153" and "withdrawn" not in (
        rec["journal"]) and rec["lsr"] == "", rec

    # With no docket: the journal's page.
    d = B.bill_disposition(rec, "HB459", {}, None, [], "2021-2022", "2025-2026")
    assert (d.kind, d.status, d.source) == ("done", "Killed", "House Journal"), d
    story = B.journal_story(rec, {})
    assert [(s["act"], s["mark"], s["text"], s["date"]) for s in story["steps"]] == [
        ("killed", "x", "Killed, 198–153", "2021-02-24")], story["steps"]
    assert story["stages"][1]["text"] == (
        "On February 24, 2021 the House voted to kill it on a roll call 198–153."), (
        story["stages"])
    assert story["intro"] == "2021-01-06" and len(story["notes"]) == 1 and (
        "HJ 3, February 24, 2021, page 83" in story["notes"][0]), story["notes"]

    # With its docket: the docket's page, and the same words for the vote.
    from datetime import datetime as _dt
    rows = [{"lsr": "2021-678", "session": "2021", "body": "H", "desc": desc, "flags": [],
             "created": _dt.strptime(stamp, "%m/%d/%Y %H:%M:%S")}
            for stamp, desc in _PAST_DOCKET_HB459]
    saved = (N.CORRECTIONS, N.MISFILED, N.TERM)
    try:
        N.CORRECTIONS, N.MISFILED, N.TERM = [], [], "2021-2022"
        narr = N.build("HB459", rows)
    finally:
        N.CORRECTIONS, N.MISFILED, N.TERM = saved
    d = B.bill_disposition(rec, "HB459", {}, narr, [], "2021-2022", "2025-2026")
    assert (d.kind, d.status, d.source) == ("done", "Killed", ""), d
    assert narr["stages"][-1]["text"] == story["stages"][1]["text"], (
        "the journal's sentence for the vote and the docket's differ: "
        f"{narr['stages'][-1]['text']!r}")
    note = B.record_notes(rec, narr)
    assert len(note) == 1 and "HJ 2, January 6, 2021, page 49" in note[0] and (
        "docket" in note[0]), note
    assert B.record_notes(rec, None) == [], (
        "a journal record with no docket carries a second note beside its story's")

    # The sponsors, at the seat the journal printed.
    import text_sponsors as TS
    sat = TS.Sat([{"member_id": "8258", "name": "Silber, Norman", "party": "R",
                   "year": "2021", "body": "H",
                   "label": "Rep. Norman Silber (R - Belk 6)"}])
    legs = {"8258": {"id": "8258", "name": "Silber, Norman", "party_code": "R",
                     "chamber": "H", "county": "Belknap", "county_abbr": "Belk",
                     "district": "6", "label": "Rep. Norman Silber (R - Belk 6)",
                     "slug": "norman-silber-belk-6"}}
    rows = BD.journal_sponsor_rows(["Silber, Belk. 2", "Nobody, Rock. 99"], "2021-2022",
                                   sat, legs, "2025-2026")
    assert (rows[0]["member_id"], rows[0]["label"], rows[0]["district"],
            rows[0]["seat_source"], rows[0]["source"], rows[0]["prime"]) == (
        "8258", "Rep. Norman Silber (R - Belk 2)", "2", "House Journal",
        "House Journal", True), rows[0]
    assert (rows[1]["member_id"], rows[1]["label"]) == ("", "Rep. Nobody (Rock 99)"), rows[1]
    from collections import defaultdict as _dd
    sp = B.bill_sponsor_list("HB459", {"designation": "HB 459", "title": "a bill"}, "2021",
                             "2021-2022", "2025-2026", {"2021-2022": {"HB459": rows}},
                             legs, {}, {}, _dd(list))
    assert (sp[0]["display_full"], sp[0]["slug"]) == (
        "Rep. Norman Silber (R - Belk 2)", "norman-silber-belk-6"), (
        f"a 2021 sponsor is drawn at today's seat: {sp[0]['display_full']!r}")
    return "ok", ("the vote read through the roll call's columns and held to its count; "
                  "Killed 198-153 from the journal alone, and from the docket where it "
                  "is here, in the same words; sponsors at the seat the journal printed")


# The House's resolutions of introduction, as the journals print them:
# journals/2009/HJ002.txt lines 7-11 and 818-826, journals/2012/HJ001.txt lines
# 10-12 and 31-39, journals/2017/HJ002.txt lines 10-12 and 1103-1108 (whose PDF
# breaks "Concur-rent" across two lines), journals/2007/HJ004.txt lines 7-9
# and 1392-1398, and journals/2010/HJ002.txt lines 7-9, 14-21 and 7623-7628 (a
# late bill or two by number, and a resolution reading in a Senate bill).
_INTRO_RESOLUTIONS = {
    "2009/HJ002.txt": """\
         HOUSE JOURNAL No. 2

                     Wednesday, January 7, 2009

The House assembled at 10:00 a.m. and was called to order by the Speaker.

                                                      RESOLUTION

Rep. Foster offered the following: Resolved, that in accordance with the list in the possession
of the Clerk, House Bills numbered 31 through 86, 88 through 133 and 135 through 223,
House Concurrent Resolutions numbered 1 through 4 and Constitutional Amendment
Concurrent Resolutions numbered 1 through 4 shall be by this resolution read a first and
second time by the therein listed titles, sent for printing and referred to the therein
designated committees.
Adopted.
""",
    "2012/HJ001.txt": """\
          HOUSE JOURNAL No. 1

                                Wednesday, January 4, 2012

                                                      RESOLUTION
Rep. Bettencourt offered the following: RESOLVED, that in accordance with the list in the
possession of the Clerk, House Bills numbered 1126 through 1283, 1285 through 1471 and
1473 through 1709, House Concurrent Resolutions numbered 30 through 43, House Joint
Resolutions numbered 20 through 22, House Resolutions numbered 20 through 27 and
Constitutional Amendment Concurrent Resolutions numbered 20 through 32 shall be by this
resolution read a first and second time by the therein listed titles, sent for printing and
referred to the therein designated committees.
Adopted.
""",
    "2017/HJ002.txt": """\
              HOUSE JOURNAL No. 2

                               Wednesday, January 4, 2017

Rep. Hinch offered the following: RESOLVED, that in accordance with the list in the possession of the Clerk,
House Bills numbered 76 through 176, 178 through 272, 275 through 276 and 278 through 286, House Concur-
rent Resolutions numbered 1 through 4, House Resolution numbered 7 and House Constitutional Amendment
Concurrent Resolutions numbered 1 through 7 shall be by this resolution read a first and second time by the
therein listed titles, sent for printing and referred to the therein designated committees.
Motion adopted.
""",
    "2007/HJ004.txt": """\
  HOUSE JOURNAL No. 3 (cont.)

                                 Thursday, January 4, 2007

                                                      RESOLUTION

Rep. Espiefs offered the following: RESOLVED, that in accordance with the list in the
possession of the Clerk, House Bills numbered 579 through 599, 601 through 624, 626
through 632, 634 through 639 and House Joint Resolution number 1 shall be by this
resolution read a first and second time by the therein listed titles, sent for printing and
referred to the therein designated committees.
Adopted.
""",
    "2010/HJ002.txt": """\
    HOUSE JOURNAL No. 1 (cont.)

                           Wednesday, January 6, 2010

                                                      RESOLUTION

Rep. Wallner offered the following: RESOLVED, that late drafting having been approved by
the Rules Committee, House Bills numbered 1689 and 1690 shall be by this resolution read a
first and second time by the therein listed titles, sent for printing and referred to the therein
designated committees.
Adopted.

                                                      RESOLUTION

Rep. Wallner offered the following: RESOLVED, that in accordance with the list in the
possession of the Clerk, Senate Bill numbered 300 shall be by this resolution read a first and
second time by the therein listed title.
Adopted.
""",
}


# What the House Journal's resolutions say of one measure. Not part of the
# build: only these checks read a number against them, so it lives here.
def _resolution_reading(resolutions, bid):
    """What the resolutions say of one measure, or None where they say nothing.

    {"introduced": True, ...} with the resolution that names its number;
    {"introduced": False, ...} where none names it and one steps over it --
    names numbers of its kind on both sides of it in one list, as "31 through
    86, 88 through 133" steps over 87. A number past the end of every list is
    not stepped over, and nothing is said of it."""
    m = re.match(r"^([A-Z]+)(\d+)$", bid or "")
    if not m:
        return None
    kind, n = m.group(1), int(m.group(2))

    def cite(r, introduced):
        return {"introduced": introduced, "date": r["date"], "journal": r["journal"],
                "numbered": r["words"].get(kind, ""), "file": r["file"], "line": r["line"]}
    for r in resolutions:
        if any(a <= n <= b for a, b in r["numbered"].get(kind, ())):
            return cite(r, True)
    for r in resolutions:
        rs = r["numbered"].get(kind, [])
        if any(b < n < c for (_a, b), (c, _d) in zip(rs, rs[1:])):
            return cite(r, False)
    return None


@check("status", "the House's resolutions of introduction are read by number, and the "
                 "introductions build_data publishes from them are what they say",
       needs=("journal_bills", "build_data"))
def _journal_resolutions(J, BD):
    """journal_bills.introduction_resolutions and the reading of them below, on the
    resolutions as printed. The House introduces its bills by a resolution
    that names them by number: a number it names was introduced that day; a
    number it steps over, with numbers of its kind named on both sides, was
    not; a number past the end of every list is not spoken of.

    Four of the 25 measures the search page left out were published against
    that: HB 87 and HB 134 of 2009 and HB 633 of 2007 as introduced and "In
    committee" on the strength of one docket row each, where the resolution
    of the day steps over all three; and HB 1512 of 2012 as never introduced,
    where the resolution of 4 January 2012 names it and steps over HB 1284
    and HB 1472. And four the search page's own list carries were: HB 177,
    HB 273, HB 274 and HB 277 of 2017, "In committee", where the resolution
    of 4 January 2017 steps over all four.

    build_data.INTRODUCTION_FROM_JOURNAL is the table of those readings, kept
    as a table because a number stepped over is evidence only beside the rest
    of a bill's record. Held here to the resolutions themselves: the answer,
    the day, the journal and the resolution's own words for the numbers.
    """
    root = Path(tempfile.mkdtemp())
    try:
        for name, text in _INTRO_RESOLUTIONS.items():
            (root / name).parent.mkdir(exist_ok=True)
            (root / name).write_text(text, encoding="utf-8")
        got = {y: J.introduction_resolutions(root, (y,)) for y in (2007, 2009, 2010, 2012, 2017)}
        absent = J.introduction_resolutions(root, (1993,))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert absent == [], "a year with no journals on the machine gave resolutions"
    assert [len(got[y]) for y in (2007, 2009, 2010, 2012, 2017)] == [1, 1, 1, 1, 1], (
        {y: len(v) for y, v in got.items()})
    r = got[2009][0]
    assert (r["date"], r["journal"], r["line"]) == ("2009-01-07", "House Journal No. 2", 9), r
    assert r["numbered"] == {"HB": [(31, 86), (88, 133), (135, 223)], "HCR": [(1, 4)],
                             "CACR": [(1, 4)]}, r["numbered"]
    # "Concur-" and "rent" on two lines; "House Resolution numbered 7"; and
    # 2017's "House Constitutional Amendment Concurrent Resolutions".
    assert got[2017][0]["numbered"] == {
        "HB": [(76, 176), (178, 272), (275, 276), (278, 286)], "HCR": [(1, 4)],
        "HR": [(7, 7)], "CACR": [(1, 7)]}, got[2017][0]["numbered"]
    assert got[2012][0]["numbered"]["HR"] == [(20, 27)] and (
        got[2012][0]["numbered"]["HJR"] == [(20, 22)]), got[2012][0]["numbered"]
    # A late pair by number; and the Senate's bill is not the House's list.
    assert got[2010][0]["numbered"] == {"HB": [(1689, 1689), (1690, 1690)]}, got[2010]

    def says(year, bid):
        x = _resolution_reading(got[year], bid)
        return None if x is None else x["introduced"]
    assert [says(2009, b) for b in ("HB86", "HB87", "HB88", "HB134", "HB223", "HB224",
                                    "HB30", "HCR2", "HCR5", "CACR4", "HR1", "SB1")] == [
        True, False, True, False, True, None, None, True, None, True, None, None], (
        "the resolution of 7 January 2009 is read as "
        + str([says(2009, b) for b in ("HB86", "HB87", "HB88", "HB134", "HB223", "HB224")]))
    assert [says(2012, b) for b in ("HB1284", "HB1472", "HB1512", "HB1283", "HB1710")] == [
        False, False, True, True, None]
    assert [says(2017, b) for b in ("HB177", "HB273", "HB274", "HB277", "HB276", "HR7")] == [
        False, False, False, False, True, True]
    assert [says(2007, b) for b in ("HB633", "HB632", "HB634", "HB600")] == [
        False, True, True, False]
    assert [says(2010, b) for b in ("HB1689", "HB1690", "HB1308", "SB300")] == [
        True, True, None, None]
    assert _resolution_reading(got[2009], "not a bill") is None

    # The table, against the resolutions it was read from.
    year_of = {"2007-2008": 2007, "2009-2010": 2009, "2011-2012": 2012, "2017-2018": 2017}
    assert sorted(BD.INTRODUCTION_FROM_JOURNAL) == [
        ("2007-2008", "HB633"), ("2009-2010", "HB134"), ("2009-2010", "HB87"),
        ("2011-2012", "HB1284"), ("2011-2012", "HB1472"), ("2011-2012", "HB1512"),
        ("2017-2018", "HB177"), ("2017-2018", "HB273"), ("2017-2018", "HB274"),
        ("2017-2018", "HB277")], (
        sorted(BD.INTRODUCTION_FROM_JOURNAL))
    # All but HB 1512 are bills the journal leaves out.
    assert sorted(k for k, v in BD.INTRODUCTION_FROM_JOURNAL.items() if v["introduced"]) == [
        ("2011-2012", "HB1512")], "the table calls another bill introduced"
    for (term, bid), fact in BD.INTRODUCTION_FROM_JOURNAL.items():
        x = _resolution_reading(got[year_of[term]], bid)
        assert x is not None and {k: x[k] for k in ("introduced", "date", "journal",
                                                    "numbered")} == fact, (
            f"{bid} of {term}: the table says {fact} and the resolution reads {x}")
    return "ok", ("31 through 86, 88 through 133 and 135 through 223 names HB 88 and steps "
                  "over HB 87 and HB 134; 2012's names HB 1512 and steps over HB 1284 and "
                  "HB 1472; 2017's steps over HB 177, HB 273, HB 274 and HB 277; a number "
                  "past the end is not spoken of; the ten readings build_data publishes "
                  "are the resolutions' own")


@check("data", "no measure the database fills, or the table of the journal's readings "
               "names, is told against the House Journal's resolution of introduction, "
               "or listed under a committee it never reached",
       needs=("journal_bills", "build_data"))
def _introductions_against_journal(J, BD):
    """What no check held the 25 to, and how four of them were published wrong:
    the House Journals on this disk. For every House measure whose record is
    the database's (build_data.PAST_SOURCE), the resolutions of its year are
    read (journal_bills.introduction_resolutions), and:

      - a number a resolution steps over, and none of the term names, is a
        bill the site does not call introduced: no rail, a record that says
        the journal was read, and no committee;
      - a number a resolution names is a bill the site does not call never
        introduced: it has its rail.

    And build_data's table says of each bill what the journals on disk say.
    A year whose journals are not here is not asked about, and that is said.

    AND NO BILL THAT WAS NEVER INTRODUCED IS FILED UNDER A COMMITTEE, journals
    or none: not in its record, so not on that committee's page or in the
    download. Nor is it marked as carried over from the year before.

    AND THE BILLS OF THE SEARCH PAGE'S OWN LIST THAT THE TABLE NAMES are held
    to all of it too: HB 177, HB 273, HB 274 and HB 277 of 2017, published "In
    committee" from the search page's status field. Every bill the table
    names carries its reading on its record, wherever its term is here; one
    the journal leaves out reads in the record's words for that -- never
    from a status field -- and its page draws no committee proceeding, which
    is what its committee's page takes its days from; and nothing reads Not
    introduced that the table does not name. NOT EVERY HOUSE MEASURE OF EVERY
    TERM: the reader misses resolutions the journals print (HB 397 through
    420 of 2017), and HB 650 and HB 651 of 2017 are stepped over and were
    heard, reported and voted on. A number stepped over is evidence only
    beside the rest of a bill's record, which is why the table is one.
    """
    bp = Path("data/bills.json")
    rows = _site_bills() if bp.exists() else None
    if rows is None:
        return "skip", "no data/bills.json or bill index here"
    bills = json.loads(bp.read_text(encoding="utf-8"))
    idx = {(r.get("term"), r.get("id")): r for r in rows}
    never = {"Not introduced", "Withdrawn prior to introduction", "Refused introduction",
             "Proposed for the special session"}
    table = BD.INTRODUCTION_FROM_JOURNAL
    ours = [(t, b, r) for t, bb in bills.items() for b, r in bb.items()
            if r.get("source") == BD.PAST_SOURCE or (t, b) in table]
    if not ours:
        return "skip", ("no record here is the database's (no db/past/PastLegislation.psv) "
                        "or one build_data's table names")
    narr = _narratives() if Path("narratives.json").exists() else {}
    bad, held, unread, cache = [], 0, set(), {}
    # The table on the records: each bill it names that has a record here
    # (the six of 2007-2012 have one only where the database's dump is)
    # carries the reading the table gives it.
    for (term, bid), fact in sorted(table.items()):
        rec = (bills.get(term) or {}).get(bid)
        if rec is not None and rec.get("introduction") != fact:
            bad.append(f"{bid} of {term}: build_data's table says {fact} and its record "
                       f"carries {rec.get('introduction')!r}")
    # Nothing reads Not introduced but on the journal's word.
    for (term, bid), row in idx.items():
        if row.get("status") == "Not introduced" and (
                table.get((term, bid)) or {}).get("introduced") is not False:
            bad.append(f"{bid} of {term} reads Not introduced, and build_data's table of "
                       "what the House Journal says does not name it as left out")
    import site_read as _SR
    for term, bid, rec in ours:
        row = idx.get((term, bid))
        if row is None:
            bad.append(f"{bid} of {term} is not in the site's index")
            continue
        told_never = row.get("status") in never or bool(
            ((narr.get(term) or {}).get(bid) or {}).get("not_introduced"))
        if (table.get((term, bid)) or {}).get("introduced") is False:
            # The status is the record's words for a bill never introduced,
            # or its docket's own withdrawal (HB 1284 and HB 1472 of 2012):
            # never the search page's field, which reads IN COMMITTEE.
            if row.get("status") not in never | {"Withdrawn"}:
                bad.append(f"{bid} of {term}, which the House Journal leaves out of the "
                           f"bills it introduces, reads {row.get('status')!r}")
        if told_never:
            page = _SR.one("site", row.get("year"), bid) or {}
            if page.get("stations"):
                bad.append(f"{bid} of {term}, never introduced, is drawn "
                           f"{len(page['stations'])} committee proceeding(s) on its page: "
                           + ", ".join(f"{s.get('what')} {s.get('when')}"
                                       for s in page["stations"][:3]))
            if "held a public hearing" in (page.get("narrative") or ""):
                bad.append(f"{bid} of {term}, never introduced, is told as heard: "
                           f"{page.get('narrative')!r}")
        if told_never and (rec.get("house_committee") or rec.get("senate_committee")
                           or row.get("committee") or row.get("carried")):
            bad.append(f"{bid} of {term}, never introduced, carries the committee "
                       f"{rec.get('house_committee') or rec.get('senate_committee')!r} "
                       f"or is marked carried over ({row.get('carried')})")
        if told_never and row.get("passage"):
            bad.append(f"{bid} of {term}, never introduced, is drawn the rail "
                       f"{row['passage']!r}")
        if not re.match(r"^(?:HB|HCR|HJR|HR|CACR)\d+$", bid) or rec.get("chamber") != "H":
            continue
        years = tuple(int(y) for y in term.split("-"))
        if not (J.ROOT / str(rec.get("lsr_year"))).is_dir():
            unread.add(str(rec.get("lsr_year")))
            continue
        if years not in cache:
            cache[years] = J.introduction_resolutions(J.ROOT, years)
        # A House bill's number is its year's: 1 to 999 in the first year of
        # a term and from 1001 in the second, so a bill is held to the
        # resolutions of the year it was filed for.
        said = _resolution_reading(
            [x for x in cache[years] if x["date"][:4] == str(rec.get("lsr_year"))], bid)
        fact = BD.INTRODUCTION_FROM_JOURNAL.get((term, bid))
        if said is None:
            if fact is not None:
                bad.append(f"{bid} of {term}: build_data says the journal was read "
                           f"({fact}) and no resolution on disk speaks of it")
            continue
        held += 1
        if not said["introduced"] and _resolution_reading(cache[years], bid)["introduced"]:
            continue                 # named by a resolution of the term's other year
        if said["introduced"] and told_never:
            bad.append(f"{bid} of {term} is told as never introduced, and the resolution "
                       f"of {said['date']} names it ({said['numbered']})")
        if not said["introduced"] and not told_never:
            bad.append(f"{bid} of {term} is told as introduced "
                       f"({row.get('status')!r}, rail {row.get('passage')!r}), and the "
                       f"resolution of {said['date']} steps over it ({said['numbered']})")
        if fact is not None and {k: said[k] for k in fact} != fact:
            bad.append(f"{bid} of {term}: build_data's table says {fact}, the journal "
                       f"{ {k: said[k] for k in fact} }")
        if fact is None and not said["introduced"]:
            bad.append(f"{bid} of {term} is stepped over by the resolution of "
                       f"{said['date']} and build_data.INTRODUCTION_FROM_JOURNAL does "
                       "not name it: read its journal and its docket, and add it")
    # AND NO COMMITTEE'S PAGE HAS ONE, among the bills referred to it or on a
    # day it sat: Executive Departments and Administration's said it met on
    # January 10, 2017 for public hearings on seven measures, HB 273 among
    # them, and Education's that it heard HB 1284 on January 12, 2012. Every
    # bill of the site told as never introduced, not only the ones above.
    untaken = {(t, b) for (t, b), row in idx.items()
               if row.get("status") in never
               or ((narr.get(t) or {}).get(b) or {}).get("not_introduced")}
    # AND NO ROW THE RULE CALLS A NOTICE IS A SITTING ANYWHERE
    # (proceedings.notice_only): not an item of a committee's day, not a
    # station of its bill's page and not a row of the download. The download
    # went on listing HB 273's hearing as a proceeding of Executive
    # Departments and Administration after both pages had stopped saying so,
    # and this check did not open it; and a bill introduced and then
    # withdrawn, HB 1512 of 2012, is not among the `untaken`, so nothing held
    # its notice off Municipal and County Government's 12 January 2012. The
    # table's notices are parted out again here, from proceedings.csv and the
    # histories on disk, and each is held to be what the rule says it is.
    import proceedings as _P
    _sat, notices = _P.sittings(_P.load(), narr)

    def meeting(term, bill, day, kind, time):
        return (term, bill, day, (kind or "").strip().lower(), (time or "").strip()[:5])
    # A notice is a row of the table, by its kind and hour, and not its day:
    # a meeting a later row cancelled or moved leaves the rest of its day
    # (narrative.voided_meetings).
    noticed = {meeting(r["term"], r["bill"], r["date"], r.get("kind"), r.get("time"))
               for r in notices}
    for r in notices:
        h = (narr.get(r["term"]) or {}).get(r["bill"]) or {}
        # Or a day its history puts no sitting on ("no_sitting"), and then
        # one of its docket lines says why beside it: the day a notice states
        # that is before the chamber had the bill, or a notice the chamber
        # overtook by taking the measure from its committee (HA 1 of 2008);
        # the notice itself, on that day, where a later row of the docket
        # cancelled or moved the meeting it names (decision 56: HB 114 of
        # 2013's of 15 January); the notice, on that day, of a recessed
        # hearing's next day the committee's report came before (HB 1218 of
        # 2002's 17 April); or the row a person dated afresh, where that
        # day is the one the docket gives (SB 106 of 2009's 10 January, told
        # on 10 February: docket_corrections.json).
        unsat = (r["date"] in (h.get("no_sitting") or [])
                 or any(_P.voided(r, m) for m in h.get("voided") or [])) and any(
            "has no row on the bill before" in (e.get("row_note") or "")
            or "took the measure from the committee" in (e.get("row_note") or "")
            or (e.get("notice") and e.get("overtaken") in ("cancelled", "moved")
                and e.get("date") == r["date"]
                and "A later row of the docket" in (e.get("row_note") or ""))
            # A meeting the docket cancels on most of its bills and the
            # calendars stopped printing, for a bill whose own notice of it
            # carries no mark (decision 58: HB 571 and HB 634 of 2015, SB 92
            # of 2013, on 29 October).
            or (e.get("notice") and e.get("overtaken") == "cancelled"
                and e.get("date") == r["date"]
                and "The docket cancels this meeting for most of the bills it was set for"
                in (e.get("row_note") or ""))
            or (e.get("notice") and e.get("date") == r["date"]
                and "The committee reported the bill before the day it names"
                in (e.get("row_note") or ""))
            or (e.get("date_as_recorded") == r["date"] and e.get("date_note")
                and e.get("date") != r["date"])
            for e in h.get("events", []))
        if not (h.get("not_introduced") or (h.get("withdrawn") and r["date"] > h["withdrawn"])
                or unsat):
            bad.append(f"{r['bill']} of {r['term']} ({r['kind']} {r['date']}) is left off as "
                       "a notice, and its history tells it neither as never introduced nor "
                       "as withdrawn before that day, nor says why no committee sat that day")
        page = _SR.one("site", (idx.get((r["term"], r["bill"])) or {}).get("year"),
                       r["bill"]) or {}
        if any(meeting(r["term"], r["bill"], s.get("when"), s.get("what"), s.get("time"))
               == meeting(r["term"], r["bill"], r["date"], r.get("kind"), r.get("time"))
               for s in page.get("stations") or []):
            bad.append(f"{r['bill']} of {r['term']}: its page draws a committee proceeding "
                       f"on {r['date']}, which its history tells as a notice")
    dl, listed_rows = Path("site/data/proceedings.csv"), 0
    if dl.exists():
        with dl.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                listed_rows += 1
                if (r.get("kind") or "").strip().lower() in _P.FLOOR_KINDS:
                    continue
                if (r.get("term"), r.get("bill")) in untaken:
                    bad.append(f"{r.get('bill')} of {r.get('term')}, never introduced, is in "
                               f"the download as a {r.get('kind')} of {r.get('committee')} "
                               f"on {r.get('date')} (site/data/proceedings.csv)")
                elif meeting(r.get("term"), r.get("bill"), r.get("date"), r.get("kind"),
                             r.get("time")) in noticed:
                    bad.append(f"{r.get('bill')} of {r.get('term')}: the download lists a "
                               f"{r.get('kind')} on {r.get('date')}, which its history tells "
                               "as a notice (site/data/proceedings.csv)")
    pages = sorted(Path("site/committee").glob("*.json"))
    for f in pages:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        for t, bb in (d.get("bills") or {}).items():
            for b in bb:
                if (t, b.get("id")) in untaken:
                    bad.append(f"{b.get('id')} of {t}, never introduced, is among the "
                               f"bills referred to {d.get('name')} ({f.name})")
        for s in d.get("sessions") or []:
            for it in s.get("items") or []:
                if (it.get("term"), it.get("bill")) in untaken:
                    bad.append(f"{d.get('name')} ({f.name}) is said to have sat on "
                               f"{it.get('bill')} of {it.get('term')}, never introduced, "
                               f"on {s.get('date')} ({it.get('kind')})")
                elif meeting(it.get("term"), it.get("bill"), s.get("date"), it.get("kind"),
                             it.get("time")) in noticed:
                    bad.append(f"{d.get('name')} ({f.name}) is said to have sat on "
                               f"{it.get('bill')} of {it.get('term')} on {s.get('date')} "
                               f"({it.get('kind')}), which its history tells as a notice")
    assert not bad, (f"{len(bad)} of the measures the database fills or build_data's "
                     "table names: " + "; ".join(bad[:6]))
    listed = sum(1 for t, b, r in ours if r.get("source") != BD.PAST_SOURCE)
    return "ok", (f"{len(ours) - listed} measures from the database and {listed} of the "
                  f"search page's own list that build_data's table names; {held} House "
                  "measures held to "
                  "the resolution that names or steps over them, none told against it; "
                  "none never introduced carries a committee, a rail, a carried mark or "
                  f"a committee proceeding; none of the {len(untaken)} bills told as never "
                  f"introduced is on any of {len(pages)} committee pages, and none of the "
                  f"{len(notices)} docket notices -- for a bill withdrawn or never introduced, "
                  "or of a meeting a later row cancelled or moved -- is a committee's day, a "
                  "station or one of the download's "
                  f"{listed_rows:,} rows"
                  + (f"; no journals here for {', '.join(sorted(unread))}" if unread else ""))


# ------------------------------------------------ the end of what the database fills --


@check("data", "every House measure the House Journal introduced is on the record")
def _journal_intros_on_record():
    """Measured against something it did not generate: every House measure the
    journals' lists of bills introduced print, from 2025 on, is in
    data/bills.json under its term. The General Court's files carry all of
    them but the withdrawn, and journal_bills.py writes those -- so a bill
    missing here is a withdrawal the reader did not see, or a bill the files
    dropped for some other reason, and either way a bill the site has lost.
    """
    J = imp("journal_bills")
    bp = Path("data/bills.json")
    if J is None:
        raise AssertionError("journal_bills.py will not import")
    if not J.years():
        return "skip", "no journals/ from 2025 here"
    if not bp.exists():
        return "skip", "no data/bills.json here; run build_data.py"
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        intros, _records, _report, problems = J.read_all()
    assert not problems, "journal_bills.py would refuse: " + "; ".join(problems[:3])
    bills = json.loads(bp.read_text(encoding="utf-8"))
    missing = sorted(f"{e['designation']} ({t}, {e['cite']['file']}:{e['cite']['line']})"
                     for (t, b), e in intros.items() if b not in (bills.get(t) or {}))
    assert not missing, (f"{len(missing)} House measure(s) the journals introduce are not "
                         "in data/bills.json: " + "; ".join(missing[:6]))
    return "ok", (f"all {len(intros):,} House measures the journals introduce are on "
                  "the record")


@check("session", "a session day gives every vote on each bill that day in order, the "
                  "docket's amendments among them, and the committee recommendation the "
                  "floor acted on", needs=("build_session_pages", "session_days",
                                           "committee_acts", "narrative"))
def _session_day_votes(BSP, SD, CA, N):
    """The person, 9 October 2026, v15: "each bill's card shows the
    committee's recommendation, and where a bill had several votes that day,
    every vote that occurred that day". Real rows (_CARD_DOCKETS): the
    House on 19 February 2026 put three questions to HB 1705-FN -- Interim
    Study failed on a division, 167-174; the minority's amendment 2026-0531h
    adopted by voice; Ought to Pass with Amendment carried 194-154 on a roll
    call -- and referred it to Finance, on the Labor committee's report
    (Interim Study, 11-9; a minority Ought to Pass with Amendment 2026-0531h).
    The sitting model draws no amendment voted by voice or division, so
    the second was on no page; it is read off the bill's own row and put
    where the docket enters it. HB 1525's report is entered on 22 February,
    after the House killed the bill on the 19th, so no recommendation is
    named for that day; and a concurrence months after the House passed
    HB 1681 is no vote on its committee's report."""
    ev = _card_events(N)

    def day(bill, date, body="H"):
        events = ev[bill]
        at = {id(e): n for n, e in enumerate(events)}
        items = []
        for e, it in SD.floor_items(bill, "2025-2026", events):
            it.seq = at[id(e)]
            if (e.get("date") or "")[:10] == date and (e.get("body") or "") == body:
                items.append(it)
        amds = [(at[id(e)], e) for e in events if e.get("type") == "amendment"
                and (e.get("date") or "")[:10] == date and (e.get("body") or "") == body
                and (e.get("vote_kind") or "").upper() != "RC"]
        floor = [((e.get("date") or "")[:10], it)
                 for e, it in SD.floor_items(bill, "2025-2026", events)
                 if (e.get("body") or "") == body]
        return (BSP.bill_votes(items, amds, {}),
                BSP.recommendation_on(CA.acts(events), body, date, floor),
                BSP.referral_on(events, body, {date}))

    votes, rec, ref = day("HB1705", "2026-02-19")
    got = [(v["motion"], v["result"], v.get("how"), v.get("yeas"), v.get("nays"),
            v.get("amendments"), v.get("amendment_kind")) for v in votes]
    want = [("Refer for Interim Study", "failed", "division", 167, 174, None, None),
            ("Adopt Amendment", "adopted", "voice vote", None, None, ["2026-0531h"],
             "Minority Amendment"),
            ("Ought to Pass with Amendment 2026-0531h", "adopted", "roll call", 194, 154,
             ["2026-0531h"], None)]
    assert got == want, f"HB 1705-FN's votes of 19 February 2026: {got}"
    assert rec and (rec.get("committee"), rec.get("code"), rec.get("yeas"), rec.get("nays"),
                    rec.get("minority_code"), rec.get("minority_amendment")) == (
        "Labor, Industrial and Rehabilitative Services", "IS", 11, 9, "OTPA", "2026-0531h"), (
        f"HB 1705-FN's recommendation on 19 February 2026: {rec}")
    assert ref == {"referred": "Finance"}, f"HB 1705-FN's referral: {ref}"
    votes, rec, _ref = day("HB1525", "2026-02-19")
    assert [(v["motion"], v["result"]) for v in votes] == [
        ("Inexpedient to Legislate", "adopted")], votes
    assert rec is None, f"HB 1525 is said to have been killed on a report entered later: {rec}"
    _v, rec, _r = day("HB1681", "2026-03-11")
    assert rec and rec.get("code") == "OTPA" and rec.get("yeas") == 17, rec
    _v, rec, _r = day("HB1681", "2026-05-21")
    assert rec is None, f"HB 1681's concurrence is said to act on its committee's report: {rec}"
    assert BSP.amendment_numbers("Ought to Pass with Amendment # 2026-1709s") == ["2026-1709s"]
    assert BSP.amendment_numbers("Ought to Pass W/Amendment, {1066}, AA") == ["1066"]
    return "ok", ("HB 1705-FN on 19 Feb 2026: Interim Study failed 167-174, amendment "
                  "2026-0531h adopted by voice, Ought to Pass with Amendment 194-154, on "
                  "Labor's Interim Study 11-9, then referred to Finance; HB 1525 names no "
                  "report entered after the vote")


class _MembersStub:
    """Members, for a check: names to slugs, slugs to a roster row."""

    def __init__(self, rows):
        self.by_slug = {r["slug"]: r for r in rows}
        self.by_id = {r["id"]: r for r in rows}
        self.names = {r["name"]: r["slug"] for r in rows}

    def slug(self, body, name):
        return self.names.get(name)


@check("session", "a session day counts its excused members by party and names who "
                  "presided, from the ballots and the journal, with the office held that day",
       needs=("build_session_pages",))
def _session_day_people(BSP):
    """The person, 9 October 2026: v16, the members excused for the day
    counted by party; v18, "a general line naming the members who presided
    over the chamber during the day (they switch back and forth)". Real
    rows: on 19 February 2026 Speaker Packard (425) was recorded presiding
    on roll calls 83-88 and Deputy Speaker Steven Smith (656) on 89-99
    (RollCallHistory.txt); officers.json gives each his office. A member the
    journal heads a turn in the chair with is named too, and a name no
    member's is counted unmatched rather than given a party."""
    rows = [{"id": "425", "slug": "sherman-packard-rock-16", "name": "Packard", "party": "R",
             "label": "Rep. Sherman Packard (R - Rock 16)"},
            {"id": "656", "slug": "steven-smith-sull-3", "name": "Steven Smith", "party": "R",
             "label": "Rep. Steven Smith (R - Sull 3)"},
            {"id": "9895", "slug": "jim-kofalt-hills-32", "name": "Kofalt", "party": "R",
             "label": "Rep. Jim Kofalt (R - Hills 32)"},
            {"id": "523", "slug": "thomas-buco-carr-1", "name": "Buco", "party": "D",
             "label": "Rep. Thomas Buco (D - Carr 1)"}]
    members = _MembersStub(rows)

    class _It:
        def __init__(self, n):
            self.rc = {"year": "2026", "body": "H", "number": n}

    class _Day:
        body, date = "H", "2026-02-19"
        items = [_It(n) for n in range(83, 100)]
        others = []

    presided = {f"2026-H-{n}": [["425", "Rep. Sherman Packard (R - Rock 16)"]]
                for n in range(83, 89)}
    presided.update({f"2026-H-{n}": [["656", "Rep. Steven Smith (R - Sull 3)"]]
                     for n in range(89, 100)})
    offices = [{"b": "H", "id": "425", "office": "Speaker of the House",
                "from": "2024-12-04", "to": "2026-12-02"},
               {"b": "H", "id": "656", "office": "Deputy Speaker of the House",
                "from": "2024-12-04", "to": "2026-12-02"}]
    narrative = {"debates": [{"speeches": [["Speaker Steven Smith", "The question is..."],
                                           ["Speaker Kofalt", "The Chair recognizes..."]]}],
                 "absences": [{"names": ["Buco", "Packard"]}, {"names": ["Nobody", "Buco"]}]}
    got = BSP.presiding_on(_Day(), narrative, presided, members, offices)
    seen = [(x["id"], x["roll_calls"], x.get("office"), bool(x.get("journal"))) for x in got]
    assert seen == [("425", 6, "Speaker of the House", False),
                    ("656", 11, "Deputy Speaker of the House", True),
                    ("9895", 0, None, True)], seen
    ex = BSP.excused_on(narrative, "H", members)
    assert ex == {"total": 3, "by_party": {"D": 1, "R": 1}, "unmatched": 1}, ex
    assert BSP.party_letter("Republican") == "R" and BSP.party_letter("D") == "D"
    return "ok", ("19 Feb 2026: Speaker Packard over 6 roll calls, Deputy Speaker Steven Smith "
                  "over 11 and in the journal's chair, Rep. Kofalt in the chair; excused "
                  "counted by party, a name no member's unmatched")


@check("code", "votes data: a session day's link asks /votes for the roll calls its page counts, by the day "
       "the page gives them, and the votes rows carry that day; a question no motion names is the record's "
       "words tidied", needs=("build_session_pages", "session_days", "build_votes"))
def _votes_session_days(BSP, SD, BV):
    """The review of 14 November 2026. The roll-call file dates the House's 13 roll calls of 11 June
    2020 on the 12th, and those of 24 and 25 February 2021 alike on the 26th, and a session day's
    "Search this day's roll calls" asked /votes for its own date: 13 became 0, and 27 and 18 became
    0. Held here: the pages' list of roll calls they count on another day than the file's, and of
    those no page counts (rollcall_days), written a chamber at a time; the link by the day, drawn
    only where the page counts a roll call the file holds; and build_votes' rows carrying the day
    (`s`), "" where no page counts it. And the record's words where no motion is named, tidied and
    nothing added: the Senate's glued mover and seconder off, the clerk's abbreviations spelled out,
    and the row taking a motion only where the words tidied are its name."""
    def item(bill, term, seq, date, **e):
        ev = {"type": "floor", "body": "H", "action": "Ought to Pass", "motion": "MA",
              "raw": "Ought to Pass: MA", "date": date, "vote_kind": "RC", "yeas": "1", "nays": "0"}
        ev.update(e)
        return SD.Item(bill, term, ev, seq)

    def rc(n, date, bill):
        return {"year": "2021", "body": "H", "number": n, "bill": bill, "yeas": 1, "nays": 0, "date": date}
    # 24 February: two roll calls the file dates the 26th. 25 February: one dated the 26th, one dated
    # the 25th, and one the docket calls a division. 13 October 2010: a roll call the docket alone states.
    a, b = item("HB1", "2021-2022", 1, "2021-02-24"), item("HB2", "2021-2022", 2, "2021-02-24")
    c, e = item("HB3", "2021-2022", 3, "2021-02-25"), item("HB6", "2021-2022", 6, "2021-02-25")
    dv = item("HB4", "2021-2022", 4, "2021-02-25", vote_kind="DV")
    a.rc, b.rc, c.rc = rc(1, "2021-02-26", "HB1"), rc(2, "2021-02-26", "HB2"), rc(3, "2021-02-26", "HB3")
    e.rc, dv.rc = rc(6, "2021-02-25", "HB6"), rc(4, "2021-02-25", "HB4")
    days = SD.Sittings({("H", "2021-02-24"): SD.Day("H", "2021-02-24", [a, b]),
                        ("H", "2021-02-25"): SD.Day("H", "2021-02-25", [c, dv, e]),
                        ("H", "2010-10-13"): SD.Day("H", "2010-10-13", [item("HB5", "2009-2010", 1, "2010-10-13")])})
    days.left = [(dict(rc(5, "2021-02-25", ""), question="Call of the Roll"), "a quorum call, which puts no question")]
    moved, none = BSP.rollcall_days(days, sorted(days), "H")
    assert moved == {"2021-H-1": "2021-02-24", "2021-H-2": "2021-02-24", "2021-H-3": "2021-02-25"}, (
        f"the roll calls counted on another day than the file's are {moved}")
    assert none == ["2021-H-4", "2021-H-5"], f"the roll calls no page counts are {none}"
    blank = {"attributions": [], "debates": [], "unanimous_consent": []}

    def link(key):
        h = BSP.day_head(days[key], blank, {}, jurl="", label="x", path=f"/session/H/{key[1]}.html",
                         base="https://x")
        return re.findall(r"<dt>Roll Calls</dt><dd>(.*?)</dd>", h)
    assert link(("H", "2021-02-24")) == ['<a href="votes?day=2021-02-24&amp;body=H">Search this day'
                                         '&rsquo;s roll calls</a>'], link(("H", "2021-02-24"))
    assert link(("H", "2010-10-13")) == [], (
        "a day whose roll calls the docket alone states leads to /votes, which holds none of them")
    root = Path(tempfile.mkdtemp())
    try:
        (root / "session").mkdir()
        BSP.write_days_index(root, "S", ["2021-03-04"], {}, {"2021-S-9": "2021-03-04"}, ["2021-S-79"])
        BSP.write_days_index(root, "H", ["2021-02-24", "2021-02-25"], {}, moved, none)
        BSP.write_days_index(root, "S", ["2021-03-04"], {})
        got = json.loads((root / "session" / "days.json").read_text(encoding="utf-8"))
        assert got.get("at") == {"H": moved, "S": {"2021-S-9": "2021-03-04"}} \
            and got.get("none") == {"H": none, "S": ["2021-S-79"]}, (
            f"session/days.json, written a chamber at a time, holds at {got.get('at')}, none {got.get('none')}")
        rolls = {"2021-2022": {f"HB{n}": [{"year": "2021", "body": "H", "number": n, "date": d,
                                          "bill": f"HB{n}", "question": "Ought to Pass", "yeas": 1,
                                          "nays": 0, "passed": True}]
                               for n, d in ((1, "2021-02-26"), (3, "2021-02-26"), (4, "2021-02-25"),
                                            (6, "2021-02-25"))}}
        ballots = [{"member_id": "10", "party": "R", "year": "2021", "body": "H", "vote_number": str(n),
                    "vote": "Yea"} for n in (1, 3, 4, 6)]
        rows, _enc, rep = BV.build(rolls, iter(ballots), root)
        by = {x["id"]: x for x in rows["2021-2022"]}
        assert rep["sittings"] and by["2021-H-1"].get("s") == "2021-02-24" and by["2021-H-3"].get("s") == "2021-02-25" \
            and by["2021-H-4"].get("s") == "" and "s" not in by["2021-H-6"], (
            f"the votes rows carry the session days {[(k, v.get('s')) for k, v in by.items()]}")
        (root / "session" / "days.json").unlink()
        rows, _enc, rep = BV.build(rolls, iter(ballots), root)
        assert not rep["sittings"] and not any("s" in x for x in rows["2021-2022"]), (
            "with no session/days.json the votes rows name a session day anyway")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # The record's words, tidied and nothing added.
    words = {("Ought to PassFrancoeur/Pignatelli", "S"): "Ought to Pass",
             ("Motion to Table Sen. Foster/Sen. Barnes", "S"): "Motion to Table",
             ("C OF C #2465C", "H"): "Committee of Conference #2465c",
             ("Adopt CofC", "H"): "Adopt Committee of Conference",
             ("MAJ AM 1905H(NT)", "H"): "Majority amendment 1905h(NT)",
             ("MOTION TO ADJOURN (REP HIKEL)", "H"): "Motion to adjourn (Rep. Hikel)",
             ("SHALL HB 109 BECOME LAW", "H"): "Shall HB 109 become law",
             ("Sections 3 and 4", "S"): "Sections 3 and 4"}
    off = {k: BV.plain_question({"question": k[0], "body": k[1]}) for k in words}
    off = {k: v for k, v in off.items() if v != words[k]}
    assert not off, f"the record's words tidied: {off}"
    motions = BV.WORDBOOK["votes"]["motions"]

    def row(q, bill, body):
        return BV.row_of({"year": "1999", "body": body, "number": 17, "date": "1999-03-04", "question": q,
                          "yeas": 15, "nays": 9, "passed": True}, bill, motions)
    otp, tab = row("Ought to PassFrancoeur/Pignatelli", "SB122", "S"), row("Motion to Table Sen. Foster/Sen. Barnes",
                                                                         "HJR24", "S")
    assert (otp["mk"], otp["k"], otp["q"]) == ("otp", "Committee report", "Ought to Pass"), otp
    assert (tab["mk"], tab["k"], tab["q"]) == ("", "Other", "Motion to Table"), (
        f"words that are not a motion's own name took one: {tab}")
    return "ok", ("the days' roll calls on another day or none, written a chamber at a time; ?day= drawn "
                  "only where a page counts a roll call on file; rows carry `s`; the record's words tidied")
