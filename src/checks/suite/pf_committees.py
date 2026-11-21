#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
preflight's checks of committees and study committees.

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

from pf_core import (_run, _source, check)
from pf_fixture import (CHAIN_NEEDS, FIXTURE_VIDEOS, FIXTURE_VIDEO_COLS, _fixture_site_shared,
                        _fixture_videos)
from pf_harness import (_app_js, _node_app, _with_components)
from pf_shared import (CALENDAR_PAGE, _COMMITTEE_WORK, _FULL_COMMITTEE_NAMES, _HEARD_PRELUDE,
                       _VW_DOT_HEAD, _bill_index_write, _card_events, _css_decls, _css_rules,
                       _css_selectors, _narratives, _site_bills, _vw_loose_dots)


# A REFERRAL UNMADE, ON EVERY HISTORY (5 October 2026). What the data check
# below finds for itself, with none of narrative's readers: a referral its
# chair waived or declined, the row that referred the bill, a rules
# suspension that made a referral, and the sentences that tell each.
# Any row with a word that gives something up near a word for a referral, in
# either order: not narrative's wordings (REFERRAL_WAIVED), which missed
# "Committee Refused Referral" (SB 166 of 2013) and "Referral to Ways and
# Means withdrawn" (HB 1679 of 2006) while this search copied them. Not a
# chamber refusing a conference, a reconsideration that lists what it
# rescinds, nor a motion its mover withdrew ("MOVED TO RE-REF, THEN WITHDREW
# MOTION", HB 424 of 1991).
_WAIVER_LOOSE = re.compile(
    r"(?:waiv|declin|refus|withdr|rescind)\w*[^;]{0,40}?\bref(?:er(?:ral|red|ence)?|\.)?(?![a-z])"
    r"|\bref(?:er(?:ral|red|ence)?|\.)?(?![a-z])[^;]{0,40}?(?:waiv|declin|refus|withdr|rescind)", re.I)
_WAIVER_NOT = re.compile(r"\baccede|\bconf(?:erence)?\b|\breconsider|\bthen\s+withdr|\bwithdr\w*\s+"
                         r"(?:the\s+|his\s+|her\s+)?motion", re.I)
_REFERRED_LOOSE = re.compile(
    r"^\W*(?:Refer(?:red)?|ref\.?)\s+to\s+(?:the\s+Committee\s+on\s+)?(?P<c>[A-Z][A-Za-z,&'. \-]*?)\s*"
    r"(?:\d{1,2}/|;|$|\bHJ\b)|\bPASSED\b[^;]*?\bREF\s+TO\s+(?P<p>[A-Z][A-Za-z,&'. \-]*?)\s*(?:\bVV\b|;|$)"
    r"|^\W*Ought\s+to\s+Pass\b[^;]*;\s*Refer\s+to\s+(?P<s>[A-Z][A-Za-z,&'. \-]*?)\s+Rule\b",
    re.I)
_WAIVER_TOLD = re.compile(r"\b(?:waived|declined|refused) the referral\b"
                          r"|\bthe referral was (?:waived|declined|refused|withdrawn)\b"
                          r"|\bwithdrew that referral\b")
# A loose match whose referral this search cannot find: each one read by a
# person, and the bill named here. A new one fails the check until it is.
_WAIVER_UNPAIRED = {
    # "Referral Waived by Committee Chair per House Rule 47(f)" with no
    # "Referred to" row on the docket at all.
    ("HB1138", "2023-2024"), ("SB134", "2025-2026"),
    # "Sen. Daniels Waived Referral to Finance" before the vote, or with it,
    # and no passage of the day refers the bill: the referral Senate Rule 4-5
    # would have made was never made, and the history tells no referral.
    ("SB133", "2017-2018"), ("SB135", "2017-2018"), ("SB191", "2017-2018"), ("SB525", "2017-2018"),
    ("SB314", "2019-2020"), ("SB223", "2025-2026"), ("HB1199", "2025-2026"),
}
# "then referred it on to the Senate Finance committee" is the Senate's (the
# person's wording, 7 October 2026), and the House's is the same words (8
# October): neither names a rule.
_SENT_ON_SAID = re.compile(r"then (?:sent it on to the|referred it on to the (?:House|Senate)) "
                           r"(?P<c>.+?) committee[.,]")
# The clause the House's passages carried until 8 October 2026.
_UNDER_THE_RULES = "under the chamber's rules"
_REPORT_SAID = re.compile(r"^(?:The committee recommended|The majority|The minority|The committee's "
                          r"amendment|The committee reported|The committee made no recommendation)")
_MOVED_AFTER = re.compile(r"Recommit|send it back|sent the bill to|referred the bill|Rerefer|Vacat", re.I)
_SENTENCE = re.compile(r"(?<=[.”])\s+(?=(?:On |The |A |It |In ))")
_WAIVERS_AT_LEAST = 155
_SENT_ON_AT_LEAST = 2500


def _when_said(iso):
    from datetime import date as _d
    try:
        y, m, d = (int(x) for x in iso[:10].split("-"))
        return _d(y, m, d).strftime("%B ") + str(d) + f", {y}"
    except ValueError:
        return ""


@check("data", "no referral a chair waived heads a stage, no first committee's report follows the "
               "passage that sent the bill on, and no passage's referral is said to be under the "
               "chamber's rules", needs=("committee_names",))
def _referrals_unmade_on_disk(CN):
    """Three things, of every history in narratives.json, read from its own
    rows by a search of this check's own.

    A REFERRAL ITS CHAIR WAIVED. For every row of a chamber with a word that
    gives something up near a word for a referral ("Referral Waived by
    Committee Chair per House Rule 47(f)", "REF TO FINANCE DECLINED",
    "Committee Refused Referral", "Referral to Ways and Means withdrawn",
    "Sen. Daniels Waived Referral to Finance"), the row that made the
    referral -- "Referred to Finance", "ref to Ways & Means", a passage's
    "PASSED AND REF TO FINANCE" or "Refer to Finance Rule 4-5" -- is found
    before it with no meeting or report of that chamber's committee between,
    or after it the same day. Where it is, no stage of that chamber is headed
    with that committee and tells nothing but the referral, no passage of
    that day "sent it on" to it, a history that says the referral was made
    says what undid it, and says so in a stage of that chamber. Where it is
    not found, a person has read the bill and named it (_WAIVER_UNPAIRED).
    Before 5 October 2026, 147 histories failed: 143 a stage headed with the
    committee that declined, three a passage that "sent it on"; and SB 166 of
    2013 and HB 1679 of 2006 failed after it, which a search copying
    narrative's wordings could not find.

    A FIRST COMMITTEE'S REPORT AFTER THE PASSAGE. No stage of a chamber's
    committee that tells only its report or its amendment comes straight after
    a floor stage that sent the bill on to another committee, headed with the
    committee the bill was sent from. 31 histories, HB 658 of 2025 among them.
    And the committee's stage before that passage tells no day after it: a
    notice entered before the passage for a later day is not given back to it.

    UNDER THE CHAMBER'S RULES. No history says it. Until 8 October 2026 the
    House's passages that sent a bill on said so where the rules sent it, and
    this part looked for one made by suspending them (48 histories of
    1995-2006); the person then chose the Senate's words for the House's too,
    so the clause is gone from every passage, and a history that still says
    it is one built before that change, or the clause come back. Read on the
    same histories as the passages counted above.

    Each count has a floor: a search that finds nothing is not a search that
    found nothing wrong."""
    fn = Path("narratives.json")
    if not fn.exists():
        return "skip", "no narratives.json here"
    narr = _narratives()
    waivers = paired = again = sent_on = 0
    headed, sent, untold, alone, misplaced, back, early, under = [], [], [], [], [], [], [], []

    def placed(name, ch, term):
        return CN.known(CN.official(name, ch, term), ch, term) or ""

    def loose(raw):
        return bool(_WAIVER_LOOSE.search(raw or "")) and not _WAIVER_NOT.search(raw or "")

    for term, byb in narr.items():
        for bill, n in byb.items():
            stages = n.get("stages", [])
            evs = [e for e in n.get("events", []) if not e.get("cancelled")]
            text = " ".join(s.get("text") or "" for s in stages)
            # 1 -- a referral its chair waived
            for i, w in enumerate(evs):
                if not loose(w.get("raw")):
                    continue
                waivers += 1
                ch = w.get("body")
                made, busy = None, False
                for e in reversed(evs[:i]):
                    if e.get("body") != ch:
                        continue
                    raw = e.get("raw") or ""
                    if e.get("type") == "introduced" or loose(raw):
                        break
                    if _REFERRED_LOOSE.search(raw):
                        made = e
                        break
                    if e.get("type") in _COMMITTEE_WORK:
                        busy = True
                if made is None or busy:
                    for e in evs[i + 1:]:
                        if e.get("body") != ch:
                            continue
                        if (e.get("date") != w.get("date") or e.get("type") in _COMMITTEE_WORK
                                or e.get("type") == "introduced"):
                            break
                        if _REFERRED_LOOSE.search(e.get("raw") or ""):
                            made, busy = e, False
                            break
                if made is None:
                    if (bill, term) not in _WAIVER_UNPAIRED:
                        alone.append(f"{bill} of {term}: {(w.get('raw') or '')[:60]!r}")
                    continue
                paired += 1
                m = _REFERRED_LOOSE.search(made.get("raw") or "")
                c = placed(m.group("c") or m.group("p") or m.group("s"), ch, term)
                chamber = "House" if ch == "H" else "Senate"
                day = _when_said(made.get("date") or "")
                # And a referral the chamber made again after the undoing is
                # the one the history tells: "The Chair rescinded Refer to
                # Finance Rule 4-5", a reconsideration, and the passage again
                # with "Refer to Finance Rule 4-5", that day (HB 1272 of 2016).
                if made in evs[:i] and any(
                        e.get("body") == ch and (x := _REFERRED_LOOSE.search(e.get("raw") or ""))
                        and placed(x.group("c") or x.group("p") or x.group("s"), ch, term) == c
                        for e in evs[i + 1:]):
                    again += 1
                    continue
                # Told in that chamber's stage: the House chair's waiver not
                # under the Senate's committee that had begun (HB 186 of 2026).
                if _WAIVER_TOLD.search(text) and not any(
                        _WAIVER_TOLD.search(s.get("text") or "") and (s.get("hand") or "").startswith(ch + ":")
                        for s in stages):
                    misplaced.append(f"{bill} of {term}")
                # Told without what undid it: the referral said to have been
                # made that day, and no waiver, refusal or withdrawal said.
                if c and day and not _WAIVER_TOLD.search(text) and re.search(
                        rf"On {re.escape(day)} the bill was referred to the {re.escape(c)} committee"
                        rf"|On {re.escape(day)} the {chamber} voted [^.]*then (?:sent it on to the"
                        rf"|referred it on to the (?:House|Senate)) {re.escape(c)} committee"
                        rf"|The {chamber} referred the bill to the "
                        rf"{re.escape(c)} committee", text):
                    untold.append(f"{bill} of {term}")
                if busy or not c:
                    continue
                for s in stages:
                    if s.get("label") != f"{chamber} Committee ({c})":
                        continue
                    told = [x for x in _SENTENCE.split(s.get("text") or "") if x]
                    if told and all(re.match(r"On .+ the bill was referred to the |The (?:House|Senate) "
                                             r"referred the bill to the ", x) for x in told):
                        headed.append(f"{bill} of {term}: {s.get('label')}")
                if (m.group("p") or m.group("s")) and day and re.search(
                        rf"On {re.escape(day)} the {chamber} voted [^.]*then (?:sent it on to the"
                        rf"|referred it on to the (?:House|Senate)) {re.escape(c)} committee", text):
                    sent.append(f"{bill} of {term}: {day}")
            # 2 -- a first committee's report after the passage that sent the bill on
            for i, s in enumerate(stages):
                hand = s.get("hand") or ""
                if not hand.endswith(":floor"):
                    continue
                t = s.get("text") or ""
                m = None
                for m in _SENT_ON_SAID.finditer(t):
                    pass
                if not m:
                    continue
                sent_on += 1
                chamber = "House" if hand.startswith("H") else "Senate"
                # Nothing dated after the passage is told in the first
                # committee's stage before it: only its report or its amendment
                # is given back there, not a notice of a meeting entered before
                # the passage for a day after it (SB 339 of 2006's of 15 March).
                said = re.search(rf"On (?P<d>[A-Z][a-z]+ \d{{1,2}}, \d{{4}}) the {chamber} voted [^.]*$",
                                 t[:m.start()])
                if said and i and stages[i - 1].get("hand") == f"{hand[0]}:committee":
                    passed = _said_date(said.group("d"))
                    later = [d for d in re.findall(r"[A-Z][a-z]+ \d{1,2}, \d{4}", stages[i - 1].get("text") or "")
                             if passed and (_said_date(d) or passed) > passed]
                    if later:
                        early.append(f"{bill} of {term}: {stages[i - 1].get('label')}, {later[0]}")
                if _MOVED_AFTER.search(t[m.end():]) or i + 1 >= len(stages):
                    continue
                nxt = stages[i + 1]
                prior = next((x.get("label") for x in reversed(stages[:i])
                              if (x.get("label") or "").startswith(f"{chamber} Committee")), "")
                label = nxt.get("label") or ""
                if (label.startswith(f"{chamber} Committee (") and label == prior
                        and label != f"{chamber} Committee ({m.group('c')})"):
                    told = [x for x in _SENTENCE.split(nxt.get("text") or "") if x]
                    if told and all(_REPORT_SAID.match(x) for x in told):
                        back.append(f"{bill} of {term}: {label}")
            # 3 -- under the chamber's rules
            for s in stages:
                t = s.get("text") or ""
                at = t.find(_UNDER_THE_RULES)
                if at >= 0:
                    under.append(f"{bill} of {term}: {s.get('label')}, "
                                 f"{t[max(0, at - 60):at + len(_UNDER_THE_RULES)]!r}")
                    break
    problems = []
    if headed:
        problems.append(f"{len(headed)} stages are headed with a committee whose referral its chair "
                        "waived, and tell nothing but the referral: " + "; ".join(headed[:6]))
    if sent:
        problems.append(f"{len(sent)} passages say the bill was sent on to a committee that declined "
                        "it: " + "; ".join(sent[:6]))
    if untold:
        problems.append(f"{len(untold)} histories say a referral was made and not what undid it: "
                        + ", ".join(untold[:10]))
    if alone:
        problems.append(f"{len(alone)} rows undo a referral this search cannot find; read each, and "
                        "either tell it or name the bill in _WAIVER_UNPAIRED: " + "; ".join(alone[:6]))
    if misplaced:
        problems.append(f"{len(misplaced)} histories tell a waiver in none of its chamber's stages: "
                        + ", ".join(misplaced[:10]))
    if back:
        problems.append(f"{len(back)} first committees' reports or amendments are told after the "
                        "passage that sent the bill on: " + "; ".join(back[:6]))
    if early:
        problems.append(f"{len(early)} first committees' stages before the passage that sent the bill "
                        "on tell a day after it: " + "; ".join(early[:6]))
    if under:
        problems.append(f"{len(under)} histories say a referral was made {_UNDER_THE_RULES}, the "
                        "clause the person took out on 8 October 2026 (narratives.json is older than "
                        "that change, or the clause is back): " + "; ".join(under[:6]))
    if waivers < _WAIVERS_AT_LEAST or sent_on < _SENT_ON_AT_LEAST:
        problems.append(f"{waivers:,} waived referrals and {sent_on:,} passages that sent a bill on, "
                        f"against at least {_WAIVERS_AT_LEAST:,} and {_SENT_ON_AT_LEAST:,}: a search "
                        "has stopped finding them")
    assert not problems, "\n".join(problems)
    return "ok", (f"{waivers:,} rows undoing a referral, {paired:,} with the row that made it ({again:,} "
                  f"made again after), none heading a stage or told without what undid it; "
                  f"{sent_on:,} passages that sent a bill on, no first "
                  f"committee's report after one, and no history saying {_UNDER_THE_RULES}")


def _said_date(s):
    """"March 15, 2006" as a date, or None."""
    from datetime import datetime as _dt
    try:
        return _dt.strptime(s, "%B %d, %Y").date()
    except ValueError:
        return None


@check("reports", "a bill number inside a sentence does not start a new report",
       needs=("fetch_committee_reports",))
def _prose_bill_number(fetch_committee_reports):
    """It split a real minority report in half and filed the tail as a new bill.

    House Calendar 10 of 2026 says "...prevented many towns and school
    districts from adopting SB 2, concentrating budgetary and governance
    decisions...". SB 2 is not a bill -- it is the name New Hampshire gives the
    ballot-vote form of town meeting -- and the section that started there took
    1,669 characters of Municipal and County Government's minority report with
    it. HB 394, cited the same way in the same calendar, took 3,567 more.

    Across the 82 cached calendars: 2 phantom sections, 5 real ones that had
    been swallowed, and 70,935 characters of committee reasoning that were
    being cut off mid-report.
    """
    got = fetch_committee_reports.parse_reports(CALENDAR_PAGE, "House Calendar 1, 2026")
    keys = sorted(got)
    assert "SB2" not in keys, (
        "a bill number inside a sentence started a section: " + str(keys))
    assert "HB394" not in keys, (
        "a bill cited inside a report started a section: " + str(keys))
    assert keys == ["HB1418", "HB1419"], keys
    mino = [e for r in got["HB1418"] for e in r["reports"]
            if e.get("side") == "Minority"]
    assert mino, "the minority report was not read at all"
    text = mino[0]["text"]
    assert "the minority opposes the motion" in text, (
        f"the minority report is cut short at {len(text)} characters: "
        f"...{text[-70:]!r}")
    return "ok", "one section per heading, and the prose stays whole"


# House Calendar 20 of 2024, page 21, as pdftotext gives it: SB 453's majority
# report wraps so that "HB 463," opens a line.
WRAPPED_BILL_PAGE = """\
SB 453-FN-A, making an appropriation to the statewide voter registration system. MAJORITY: REFER
FOR INTERIM STUDY. MINORITY: OUGHT TO PASS.
Rep. Dan McGuire for the Majority of Finance. This bill combines $450,000 from the general fund with
$100,000 from HAVA funds to pay for the creation of an online voter registration portal and other improve-
ments to the registration database. The problem is that the companion bill that implements these policies,
HB 463, may not be passed, and therefore we would have allocated $450,000 to the Secretary of State for no
purpose. The correct action is for the allocation of funds to be attached to the policy bill so that they can rise
or fall together. Vote 13-12. Rep. Karen Ebel for the Minority of Finance. This bill would make a $450,000
appropriation to the Secretary of State to incorporate additional capabilities into the Statewide Voter Reg-
istration System, such as an election information portal and maintaining the system. The recommendation
of Division I of the Finance Committee on SB 453 was unanimously Ought to Pass.
"""


@check("reports", "a bill number that wraps to the start of a line inside a "
                  "report does not take the rest of it to another bill",
       needs=("fetch_committee_reports",))
def _wrapped_bill_number(fetch_committee_reports):
    """HB 463's page carried a report the House never made on it.

    SB 453's majority report in House Calendar 20 of 2024 wraps so that "HB
    463, may not be passed" opens a line, and BILL_START read that as a
    heading. SB 453 lost the end of its majority report and its vote, and its
    minority report went to HB 463 -- "OUGHT TO PASS", signed by Rep. Ebel,
    reasoning about SB 453. The rule that catches it: a heading's first report
    is never preceded by a committee vote, and the other side of a divided
    committee signs for the same committee. Rebuilt from the 1,580 calendars
    on disk, 7 such lines, 7 bills' records changed, and no others.
    """
    got = fetch_committee_reports.parse_reports(WRAPPED_BILL_PAGE,
                                                "House Calendar 20, 2024")
    assert sorted(got) == ["SB453"], (
        "a bill number wrapped inside a report opened a section of its own: "
        + str(sorted(got)))
    r = got["SB453"][0]
    sides = {e["side"]: e for e in r["reports"]}
    assert set(sides) == {"Majority", "Minority"}, sides.keys()
    assert "rise or fall together" in sides["Majority"]["text"] and \
        sides["Majority"].get("vote_yeas") == 13, (
        "SB 453's majority report was cut at the wrapped number: "
        + repr(sides["Majority"]["text"][-80:]))
    assert sides["Minority"]["author"] == "Rep. Karen Ebel", sides["Minority"]
    assert r["minority_recommendation"] == "OUGHT TO PASS", r
    return "ok", "the wrapped number stays in SB 453's report, and both sides are read"


# Headings the parser did not know, each as a calendar prints it: "HB-604-FN,"
# (House Calendar 32 of 2001), "SB 131--FN," (56 of 1997), "SJR-2," (51 of
# 1997), "HCACR 15," (3 of 2016) and an address, "HA 1," (9 of 2018), after
# HB 1813's report.
MISSED_HEADINGS_PAGE = """\
   HB 218-FN, relative to the motor vehicle road toll law and motor vehicle registration fees. OUGHT TO PASS WITH
   AMENDMENT

   Rep. John S. Langone for Ways and Means: The committee feels that this bill, as amended, accomplishes the intent of the Dept.
   of Safety and the Transportation Committee. It also removes the "Dedicated Funds" section of the bill. Vote 15-2.

   HB-604-FN, relative to increasing certain fees and making other changes to fish and game licenses. OUGHT TO PASS

   Rep. Jeff Gilbert for Ways and Means: The Committee voted on a bipartisan basis 12-6 to approve the proposed license fee
   increases of approximately 40% over a two year period. These fees represent nearly all of the sources of funding for the
   Department of Fish and Game. Vote 12-6.

   SB 131--FN, allowing certain state employees to take paid leave to participate in disaster relief service work. RE-REFER TO COMMITTEE

   Rep. Jon P. Beaulieu for Executive Departments and Administration: The committee understands the importance of the work
   that the American Red Cross provides with its disaster relief services. However, there were a number of unanswered
   questions as to the effect of such legislation. Vote 12-4.

   SJR-2, relative to federal funding under the Individuals with Disabilities Education Act. OUGHT TO PASS WITH AMENDMENT

   Rep. Stanley Searles for Education: This Senate Joint Resolution urges Congress to keep its promises, appropriate the
   40% average per pupil expenditure funds as established in law. Vote 15-0.

HCACR 15, relating to the election of judges. Providing that judges be elected for specific terms. INEXPEDIENT TO LEGISLATE.
Rep. Timothy Horrigan for Judiciary. This resolution is the most recent version of an idea which has been proposed and
rejected many times before: electing judges. The committee concluded the idea is not suitable. Vote 16-0.

HB 1813-FN, relative to the law regarding Medicaid expansion. INEXPEDIENT TO LEGISLATE.
Rep. John Fothergill for Health, Human Services and Elderly Affairs. The committee agreed the topic needs
to be part of the larger discussion, but this is not the right time. Vote 22-0.

JUDICIARY

HA 1, seeking the removal from office of superior court judge James D. O'Neill, III. OUGHT NOT TO PASS.
Article 73 of the State Constitution provides that in a House Address, "the cause for removal shall be stated
fully and substantially in the Address." This address does not meet that requirement; therefore, the commit-
tee voted unanimously to recommend the Address be found Ought Not To Pass. Vote 17-0.
"""

# House Calendar 7 of 1998, a browser's printout: the page broke inside HB
# 1211's heading, leaving its title at the foot of one page and its number at
# the top of the next.
SPLIT_HEADING_PAGE = """\
   HB 1206, affirming that it is the legislature's intent that new court facility construction costs
   reflect the needs and usage of the judiciary. INEXPEDIENT TO LEGISLATE

   Rep. Steve Vaillancourt for Public Works and Highways: This bill would affirm the legislature's
   intent that new court construction costs reflect the needs and usage of the judiciary. The
   committee believes this bill is not necessary. Vote 18-0.

                         , appropriating startup funds for the Governors State Park in Laconia. OUGHT TO PASS

file:///C/Users/sue.forcier/Downloads/working/houcal7.htm[11/8/2021 1:47:35 PM]
\fHouse Calendar 7

   HB 1211-FN-A
   WITH AMENDMENT

   Rep. Gene G. Chandler for Public Works and Highways: This bill, as presented, involved an
   appropriation of $750,000 for Governors State Park located near the Laconia Correctional
   Facility, for the purpose of development of said park. Vote 20-0.
"""


@check("reports", "a heading the calendar prints oddly still ends the report "
                  "above it, and an address is no bill",
       needs=("fetch_committee_reports",))
def _headings_the_parser_missed(fetch_committee_reports):
    """36 bills' pages carried another item's committee report.

    BILL_START knew HB, SB, CACR, HR, SR, HCR, SCR and HJR, each with at most a
    space before its number and single hyphens after. So "HB-604-FN," (House
    Calendar 32 of 2001) was no heading and HB 604's report -- Fish and Game
    license fees -- went to HB 218; "SB 131--FN," gave SB 106 the Red Cross
    leave; every "SJR 2," and "HA 1," went to the bill above it; "HCACR 15,"
    gave HB 1281 and HB 1350 the report on electing judges; and HB 1813 showed
    an address's reasoning with its vote, 17-0, for its own 22-0. And four
    times the 1998 printouts broke a heading across a page, so no heading was
    read at all. Re-reading the 1,580 calendars: 36 bills lose another item's
    report, 24 gain their own, and five lose a stray heading off the end of
    theirs.

    An address's section ends the report above it and makes no record: its
    committee recommends OUGHT NOT TO PASS, which the parser does not read,
    and a record for one carried the minority's recommendation as the
    majority's.
    """
    F = fetch_committee_reports
    got = F.parse_reports(MISSED_HEADINGS_PAGE, "House Calendar 32, 2001")
    assert sorted(got) == ["CACR15", "HB1813", "HB218", "HB604", "SB131", "SJR2"], (
        "headings read: " + ", ".join(sorted(got)))
    one = {k: v[0]["reports"] for k, v in got.items()}
    assert all(len(v) == 1 for v in one.values()), {k: len(v) for k, v in one.items()}
    assert "fish and game" not in one["HB218"][0]["text"].lower() and \
        one["HB218"][0].get("vote_yeas") == 15, (
        "HB 604's report is still on HB 218: " + one["HB218"][0]["text"][-100:])
    assert one["HB604"][0]["author"] == "Rep. Jeff Gilbert", one["HB604"]
    assert one["SB131"][0]["author"] == "Rep. Jon P. Beaulieu", one["SB131"]
    assert "Address" not in one["HB1813"][0]["text"] and \
        (one["HB1813"][0]["vote_yeas"], one["HB1813"][0]["vote_nays"]) == (22, 0), (
        "an address's report and vote are still on HB 1813: " + str(one["HB1813"]))
    assert F.bill_key("HCACR 15") == "CACR15" and F.bill_key("HB-604-FN") == "HB604", (
        F.bill_key("HCACR 15"), F.bill_key("HB-604-FN"))

    got = F.parse_reports(SPLIT_HEADING_PAGE, "House Calendar 7, 1998")
    assert sorted(got) == ["HB1206", "HB1211"], (
        "the heading the page broke was not read: " + ", ".join(sorted(got)))
    h1206, h1211 = got["HB1206"][0], got["HB1211"][0]
    assert [e["author"] for e in h1206["reports"]] == ["Rep. Steve Vaillancourt"] and \
        "Governors State Park" not in h1206["reports"][0]["text"], h1206
    assert h1211["majority_recommendation"] == "OUGHT TO PASS WITH AMENDMENT" and \
        h1211["reports"][0]["author"] == "Rep. Gene G. Chandler", h1211
    return "ok", ("a hyphened, doubled or chamber-marked number, an SJR and a "
                  "heading the page broke all start a report; an address ends one")


@check("build", "a committee day still to come is scheduled, not met", needs=("build_committees",))
def _committee_tense(BC):
    """On 13 September the Judiciary committee's page said it "met" on the 30th,
    seventeen days before it did: the docket carries sittings ahead of time and
    the day's sentence had one tense."""
    import datetime
    items = [{"kind": "executive session", "n": "HB 293", "bill": "HB293", "term": "2025-2026"}]
    later = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    earlier = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    ahead = BC.narrate("Judiciary", "H", later, items, {})
    past = BC.narrate("Judiciary", "H", earlier, items, {})
    assert "is scheduled to meet" in ahead and " met on" not in ahead, ahead
    assert " met on" in past and "scheduled" not in past, past
    return "ok", "future days scheduled, past days met"


@check("build", "a committee of conference is not a sitting of the committee its bill was referred to",
       needs=("build_committees",))
def _committee_not_conference(BC):
    """House Finance's page would have said it "met on June 12, 2025 for
    committees of conference on HB 1 and HB 2".

    A conference row of proceedings.csv carries the committee the bill was
    referred to, because a docket row for the bill did -- the notice itself,
    "Conference Committee Meeting: 06/12/2025 02:00 pm LOB 210-211", names
    none. build_committees filed every row with a committee under that
    committee's page, so reading the House's notices would have put 50
    conference days on 16 House committees' pages in 2025-2026, days they did
    not sit; the Senate's notices already did the same, Senate Finance
    "met on May 22, 2026 for a committee of conference on SB 481-FN-A".
    build_pages.meeting_key keeps the same rule on the Calendar.

    The rows are proceedings.csv's own.
    """
    keep = [
        {"term": "2025-2026", "bill": "HB1", "body": "H", "kind": "public hearing",
         "date": "2025-03-12", "time": "14:00", "committee": "Finance",
         "venue": "SH Reps Hall", "source": "docket"},
        {"term": "2025-2026", "bill": "SB481", "body": "S", "kind": "hearing",
         "date": "2026-01-13", "time": "13:20", "committee": "Finance",
         "venue": "SH 103", "source": "docket"},
    ]
    drop = [
        {"term": "2025-2026", "bill": "HB1", "body": "H", "kind": "committee of conference",
         "date": "2025-06-12", "time": "14:00", "committee": "Finance",
         "venue": "LOB 210-211", "source": "docket"},
        {"term": "2025-2026", "bill": "SB481", "body": "S", "kind": "committee of conference",
         "date": "2026-05-22", "time": "13:00", "committee": "Finance",
         "venue": "GP 159", "source": "docket"},
        # And, as before, a row naming no committee, or no day.
        {"term": "2025-2026", "bill": "HB1", "body": "H", "kind": "committee of conference",
         "date": "2025-06-12", "committee": "", "video_id": "aGy5YRZ4rdw"},
        {"term": "2025-2026", "bill": "HB1", "body": "H", "kind": "public hearing",
         "date": "", "committee": "Finance"},
    ]
    f = getattr(BC, "its_own_sitting", None)
    assert f, "build_committees has no its_own_sitting"
    wrong = [r for r in keep if not f(r)] + [r for r in drop if f(r)]
    assert not wrong, ("filed under a committee's page wrongly, or left off it: "
                       + "; ".join(f"{r['bill']} {r['kind']} {r['date']}" for r in wrong))
    src = _source(BC.__file__)
    main_ = src[src.index("def main("):]
    assert re.search(r"for r in rows:\s+if not its_own_sitting\(r\):\s+continue",
                     main_), "build_committees.main no longer files its rows through its_own_sitting"
    return "ok", ("HB 1's conference of 12 June 2025 is not House Finance's sitting, nor "
                  "SB 481's of 22 May 2026 Senate Finance's; their hearings are")


# proceedings.csv's own rows (lines 69325, 54496, 54759, 54498, 69319, 69336 and
# 51828), cut to the columns the rule and the builders read; and what
# narratives.json holds of each bill that the rule asks about.
_NOTICE_ROWS = {
    "HB273": {"term": "2017-2018", "bill": "HB273", "body": "H", "kind": "public hearing",
              "date": "2017-01-10", "time": "13:30", "venue": "LOB 306",
              "committee": "Executive Departments and Administration", "source": "docket"},
    "HB1284 hearing": {"term": "2011-2012", "bill": "HB1284", "body": "H",
                       "kind": "public hearing", "date": "2012-01-12", "time": "10:30",
                       "venue": "LOB 207", "committee": "Education", "source": "docket"},
    "HB1284 exec": {"term": "2011-2012", "bill": "HB1284", "body": "H",
                    "kind": "executive session", "date": "2012-01-24", "time": "10:00",
                    "venue": "LOB 207", "committee": "Education", "source": "docket"},
    "HB1512": {"term": "2011-2012", "bill": "HB1512", "body": "H", "kind": "public hearing",
               "date": "2012-01-12", "time": "12:05", "venue": "LOB 301",
               "committee": "Municipal and County Government", "source": "docket"},
}
_SITTING_ROWS = {
    "HB255 hearing": {"term": "2017-2018", "bill": "HB255", "body": "H",
                      "kind": "public hearing", "date": "2017-01-10", "time": "13:00",
                      "venue": "LOB 306",
                      "committee": "Executive Departments and Administration",
                      "source": "docket"},
    "HB255 exec": {"term": "2017-2018", "bill": "HB255", "body": "H",
                   "kind": "executive session", "date": "2017-01-10", "time": "",
                   "venue": "LOB 306",
                   "committee": "Executive Departments and Administration",
                   "source": "docket"},
    # The other HB 273: 2011's, heard by Labor on 8 February 2011. A history
    # looked up by the number alone would take 2017's.
    "HB273 of 2011": {"term": "2011-2012", "bill": "HB273", "body": "H",
                      "kind": "public hearing", "date": "2011-02-08", "time": "10:15",
                      "venue": "LOB 307",
                      "committee": "Labor, Industrial and Rehabilitative Services",
                      "source": "docket"},
}
_NOTICE_HISTORIES = {
    "2017-2018": {"HB273": {"not_introduced": True}, "HB255": {}},
    "2011-2012": {"HB1284": {"withdrawn": "2012-01-04", "not_introduced": True},
                  "HB1512": {"withdrawn": "2012-01-04"}, "HB273": {}},
}


@check("build", "a docket notice for a bill withdrawn or never introduced is not a sitting "
                "of the committee on it, nor a proceeding in the download",
       needs=("build_committees", "proceedings", "build_site_v2", "build_exports",
              "build_civics"))
def _committee_not_a_notice(BC, P, B, BE, BV):
    """Education's page said the committee met on January 12, 2012 for a public
    hearing on HB 1284, a bill withdrawn on the 4th and never introduced, and
    Executive Departments and Administration's that it heard HB 273 on
    January 10, 2017, a bill the House's resolution of introduction steps
    over. Both are rows of proceedings.csv, which reads the docket's notices,
    and a notice is entered before the day.

    ONE RULE, proceedings.notice_only, asked of the bill's own history: a
    committee row for a bill that was never introduced, or for a day after
    the bill was withdrawn. build_site_v2 asks it for the bill's stations,
    build_committees for the committee's days, build_exports for the download
    and build_civics for the count of hearings, the last three through
    proceedings.sittings, which looks the history up by the row's own term
    and bill. The rule was first taken from the stations a bill's page lacked,
    which left off any row a page happened not to draw and kept every row
    when the lookup missed; both directions are held here.

    AND THROUGH main(), on a project of three bills: the committee's page is
    built with HB 255's hearing and without HB 273's; without narratives.json
    the build stops; and with a history that does not know HB 273 was never
    introduced it stops on the index's word (untaken_guard), which is the
    silent direction -- every notice filed as a sitting, exit 0.

    The rows are proceedings.csv's own, and the histories what narratives.json
    holds of each bill. Two rows are made for the guard and say so.
    """
    f, part = getattr(P, "notice_only", None), getattr(P, "sittings", None)
    assert f and part, "proceedings has no notice_only, or no sittings"
    hist = _NOTICE_HISTORIES

    def of(r):
        return (hist.get(r["term"]) or {}).get(r["bill"])
    for name, r in _NOTICE_ROWS.items():
        assert f(r, of(r)), f"{name}, a notice no committee sat for, is a sitting"
    for name, r in _SITTING_ROWS.items():
        assert not f(r, of(r)), f"{name}, a sitting, is left off as a notice"
    hb1512, hb1284 = hist["2011-2012"]["HB1512"], hist["2011-2012"]["HB1284"]
    # MADE FOR THE GUARD, on no docket: a sitting on the day of the withdrawal
    # itself stands for a bill that was introduced (the rule is "after"), and
    # for one that never was it does not -- no committee had that bill on any
    # day; and a bill with no history is not judged.
    on_the_day = {**_NOTICE_ROWS["HB1512"], "date": "2012-01-04"}
    assert not f(on_the_day, hb1512), "a sitting on the day of a withdrawal is a notice"
    assert f({**on_the_day, "bill": "HB1284", "date": "2012-01-03"}, hb1284), (
        "a meeting set for a bill that was never introduced, for a day before its "
        "withdrawal, is a sitting")
    assert not f(_NOTICE_ROWS["HB273"], None) and not f(_NOTICE_ROWS["HB273"], {}), (
        "a row whose bill has no history is left off")
    # Never a floor row, nor a conference: neither is a committee's sitting.
    for kind in sorted(P.FLOOR_KINDS):
        assert not f({**_NOTICE_ROWS["HB1512"], "kind": kind}, hb1512), (
            f"a {kind} row is left off as a committee's notice")
    rows = list(_NOTICE_ROWS.values()) + list(_SITTING_ROWS.values())
    kept, notices = part(rows, hist)
    assert notices == list(_NOTICE_ROWS.values()) and kept == list(_SITTING_ROWS.values()), (
        "proceedings.sittings parts the rows otherwise: "
        + ", ".join(f"{r['bill']} {r['date']}" for r in notices))
    assert part(rows, {}) == (rows, []) and part(rows, None) == (rows, []), (
        "with no histories a row is left off")
    # The lookup is by the row's term: under the number alone, or the other
    # term, HB 273 of 2011 goes and HB 273 of 2017 stays.
    swapped = {"2011-2012": hist["2017-2018"], "2017-2018": hist["2011-2012"]}
    assert [r["term"] for r in part(
        [_NOTICE_ROWS["HB273"], _SITTING_ROWS["HB273 of 2011"]], swapped)[1]] == ["2011-2012"]

    ceiling = BC.NOTICE_CEILING
    # A few hundred notices are left off since a meeting a later row cancelled
    # or moved stopped being told as held (425 on 6 October 2026).
    assert 500 <= ceiling <= 2000, (
        f"NOTICE_CEILING is {ceiling}: a few hundred notices are left off, and "
        "proceedings.csv has tens of thousands of rows to lose")
    assert BC.notice_guard(["HB1284 public hearing 2012-01-12"] * ceiling) == "", (
        "the guard stops a build at its own ceiling")
    msg = BC.notice_guard(["HB1284 public hearing 2012-01-12"] * (ceiling + 1))
    assert msg and str(ceiling) in msg and "HB1284" in msg, msg
    # The index's words for a bill never introduced are build_site_v2's.
    assert BC.NEVER_INTRODUCED == B.NEVER_INTRODUCED, (
        f"build_committees.NEVER_INTRODUCED is {sorted(BC.NEVER_INTRODUCED)} and "
        f"build_site_v2's {sorted(B.NEVER_INTRODUCED)}")
    filed = [(_SITTING_ROWS["HB255 hearing"], {"status": "Signed into law"}),
             (_NOTICE_ROWS["HB1512"], {"status": "Withdrawn"}),
             (_SITTING_ROWS["HB273 of 2011"], {})]
    assert BC.untaken_guard(filed) == "" and BC.untaken_guard([]) == "", (
        BC.untaken_guard(filed))
    for status in sorted(B.NEVER_INTRODUCED):
        msg = BC.untaken_guard(filed + [(_NOTICE_ROWS["HB273"], {"status": status})])
        assert msg and "HB273 of 2017-2018" in msg and status in msg, (status, msg)

    # Through main().
    here = Path(".").resolve()
    if not _paths.locate("build_committees.py").exists() or not (here / "src/pages/bills.html").exists():
        return "skip", "build_committees.py or bills.html not here"
    root = Path(tempfile.mkdtemp(prefix="gr-cmte-notice-"))
    try:
        (root / "site").mkdir()
        (root / "data").mkdir()
        (root / "src" / "pages").mkdir(parents=True, exist_ok=True)
        shutil.copy2(here / "src/pages/bills.html", root / "src/pages/bills.html")
        (root / "data" / "committees.json").write_text(json.dumps({
            "H07": {"code": "H07", "name": "Executive Departments and Administration",
                    "abbr": "ED&A"},
            "H18": {"code": "H18", "name": "Municipal and County Government",
                    "abbr": "M&C"}}), encoding="utf-8")

        def entry(bid, year, term, status, cmte):
            return {"id": bid, "n": re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid), "term": term,
                    "year": year, "title": "a title", "status": status, "kind": "done",
                    "committee": cmte, "committees": [cmte] if cmte else []}
        _bill_index_write(root / "site", [
            entry("HB255", 2017, "2017-2018", "Signed into law",
                  "House Executive Departments and Administration"),
            entry("HB273", 2017, "2017-2018", "Not introduced", ""),
            entry("HB1512", 2012, "2011-2012", "Withdrawn",
                  "House Municipal and County Government")])
        P.write([_SITTING_ROWS["HB255 hearing"], _SITTING_ROWS["HB255 exec"],
                 _NOTICE_ROWS["HB273"], _NOTICE_ROWS["HB1512"]], root / "proceedings.csv")
        histories = {"2017-2018": hist["2017-2018"],
                     "2011-2012": {"HB1512": hist["2011-2012"]["HB1512"]}}

        def build(narr):
            path = root / "narratives.json"
            if narr is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(json.dumps(narr), encoding="utf-8")
            r = _run([sys.executable, _paths.script("build_committees.py"), "--site", "site",
                      "--data", "data", "--base", "https://graniterecord.org"],
                     cwd=root, capture_output=True, text=True, timeout=180,
                     env={"GRANITE_PROCEEDINGS": ""})
            return r.returncode, (r.stdout or "") + (r.stderr or "")

        def days(code):
            d = json.loads((root / "site" / "committee" / f"{code}.json").read_text(
                encoding="utf-8"))
            return {(s.get("date"), it.get("bill"), it.get("kind"))
                    for s in d.get("sessions") or [] for it in s.get("items") or []}

        code, out = build(histories)
        assert code == 0, f"build_committees stopped: {out.strip()[-300:]}"
        assert days("H07") == {("2017-01-10", "HB255", "public hearing"),
                               ("2017-01-10", "HB255", "executive session")}, (
            "Executive Departments and Administration's days, built from HB 255's two "
            f"sittings and HB 273's notice, are {sorted(days('H07'))}")
        assert days("H18") == set(), (
            "Municipal and County Government sat on HB 1512 after its withdrawal: "
            f"{sorted(days('H18'))}")
        assert "2 docket notice(s) left off" in out and "HB273 public hearing 2017-01-10" in out, (
            "the build does not say which notices it left off: " + out.strip()[-300:])
        # A history that does not know HB 273 was never introduced: the index
        # does, and the build stops rather than file the notice.
        code, out = build({"2017-2018": {"HB255": {}}, "2011-2012": histories["2011-2012"]})
        assert code != 0 and "HB273 of 2017-2018" in out and "Not introduced" in out, (
            "a notice for HB 273, Not introduced in the index, was filed as a sitting "
            f"and the build went on ({code}): " + out.strip()[-300:])
        # And none at all: said as that, before any row is looked at.
        for none in (None, {}):
            code, out = build(none)
            assert code != 0 and "narratives.json is not there, or holds nothing" in out, (
                f"with no histories in narratives.json ({none!r}) the build went on, or "
                f"stopped on something else ({code}): " + out.strip()[-300:])

        # THE DOWNLOAD, by the same rule over the same rows: it went on
        # listing HB 273's hearing under Executive Departments and
        # Administration, as a proceeding on record, after the bill's page
        # and the committee's had stopped saying so.
        import contextlib
        import io
        table = [_SITTING_ROWS["HB255 hearing"], _SITTING_ROWS["HB255 exec"],
                 _NOTICE_ROWS["HB273"], _NOTICE_ROWS["HB1512"]]
        out_dir = root / "site" / "data"
        out_dir.mkdir()
        with contextlib.redirect_stdout(io.StringIO()) as said:
            BE.proceedings_table(out_dir, root / "site", table=table, histories=histories)
        with (out_dir / "proceedings.csv").open(encoding="utf-8", newline="") as fh:
            got = {(r["term"], r["bill"], r["kind"], r["date"]) for r in csv.DictReader(fh)}
        assert got == {("2017-2018", "HB255", "public hearing", "2017-01-10"),
                       ("2017-2018", "HB255", "executive session", "2017-01-10")}, (
            f"the download of HB 255's two sittings and two notices holds {sorted(got)}")
        assert "2 docket notice(s)" in said.getvalue() and "HB273 2017-01-10" in said.getvalue(), (
            "the download does not say which notices it left out: " + said.getvalue()[-200:])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                BE.proceedings_table(out_dir, root / "site", table=table, histories={})
        except SystemExit as e:
            assert "narratives.json" in str(e), str(e)
        else:
            raise AssertionError("with no histories the download was written, every "
                                 "notice in it as a proceeding")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # And the order main() does it in, and that the other readers ask the
    # same rule: read from the source, after what main() does has been run.
    src = _source(BC.__file__)
    main_ = src[src.index("def main("):]
    loop = main_[main_.index("rows, histories = P.load()"):main_.index("# ---- bills referred")]
    at = [loop.find(x) for x in (
        "if rows and not histories:", "rows, left_off = P.sittings(rows, histories)",
        "for r in rows:", "if not its_own_sitting(r):", "filed.append((r, meta))",
        "day_said[code]", "days[code]",
        "stop = notice_guard(notices) or untaken_guard(filed)", "raise SystemExit(stop)")]
    assert all(x >= 0 for x in at) and at == sorted(at), (
        "build_committees.main no longer parts its rows by proceedings.sittings before "
        f"it files them, or no longer stops on its guards: {at}")
    site_src = _source(B.__file__)
    assert re.search(r"stations = \[x for x in stations\s+if not P\.notice_only\(",
                     site_src), "build_site_v2 no longer asks proceedings.notice_only"
    # The count of hearings the Learn pages state: of sittings, by the
    # histories record_figures has already read.
    assert "procs, _notices = P.sittings(P.load(), every_narr)" in _source(BV.__file__), (
        "build_civics no longer counts its hearings from proceedings.sittings")
    return "ok", ("HB 273 of 2017 and HB 1284 and HB 1512 of 2012 are notices by their own "
                  "histories, HB 255's hearing and executive session and 2011's HB 273 "
                  "are sittings; through main() the committee's page has HB 255 and not "
                  f"HB 273, and the download likewise; past {ceiling} notices, on a notice "
                  "filed for a bill the index says was never introduced, or with no "
                  "histories, the build stops")


@check("build", "committee names that reach no page stop the build past a stated ceiling",
       needs=("build_committees",))
def _committee_unmatched_ceiling(BC):
    """build_committees printed six of the names that matched no committee
    page and exited 0. It was 15 names on 10 September and 656 on 24
    September, with House Executive Departments and Administration showing no
    sitting day for 1999-2004, and no log said when it happened. The count is
    now held to UNMATCHED_CEILING: at the ceiling the build goes on, one past
    it main() stops with the names, and main() still asks."""
    from collections import Counter as C
    ceiling = BC.UNMATCHED_CEILING
    assert 112 <= ceiling <= 300, (
        f"UNMATCHED_CEILING is {ceiling}: 112 names matched no page on 24 "
        "September, and a ceiling far above that would not have stopped the jump "
        "to 656")
    at = C({f"H Name {i}": 1 for i in range(ceiling)})
    over = C({f"H Name {i}": 1 for i in range(ceiling + 1)})
    over["H Exec Depts and Admin"] = 1094
    assert BC.unmatched_guard(at) == "", "the guard stops a build at its own ceiling"
    msg = BC.unmatched_guard(over)
    assert msg and str(ceiling) in msg and "Exec Depts and Admin" in msg, msg
    src = _source(BC.__file__)
    main_ = src[src.index("def main("):]
    assert re.search(r"stop = unmatched_guard\(unmatched\)\s+if stop:\s+raise SystemExit",
                     main_), "build_committees.main no longer stops on the guard"
    return "ok", f"ceiling {ceiling}: at it the build goes on, past it it stops and names them"


@check("build", "a committee is archived only on two facts, and never on a guess",
       needs=("build_committees",))
def _committees_archived(BC):
    """The launch list asked for disbanded committees at the bottom of /committees.
    The record cannot say disbanded. It can say a committee is not on the General
    Court's list today and that its bills and sitting days end before this term,
    and it takes both: H05 Education is on no list and has 1,530 bills to 2024,
    and three special committees are on no list with no record at all and mostly
    sitting members, which is not evidence of anything having ended."""
    rows = [
        {"code": "H05", "name": "Education", "chamber": "H", "span": ["1989-1990", "2023-2024"]},
        {"code": "H07", "name": "Executive Departments and Administration", "chamber": "H",
         "span": ["1989-1990", "2025-2026"]},
        {"code": "H30", "name": "Committee of Conference", "chamber": "H",
         "span": ["1999-2000", "2015-2016"]},
        {"code": "H57", "name": "Special Committee on Commissions", "chamber": "H", "span": []},
        {"code": "S91", "name": "Education and Workforce Development", "chamber": "S",
         "span": ["2019-2020"]},
        {"code": "S99", "name": "On no list, but on this term's record", "chamber": "S",
         "span": ["2025-2026"]},
    ]
    live, idle, archived = BC.listing_groups(rows, {"H07"}, "2025-2026")
    got = lambda xs: sorted(c["code"] for c in xs)
    assert got(archived) == ["H05", "S91"], got(archived)
    assert got(idle) == ["H57"], "a committee with no record was filed as " + (
        "archived" if "H57" in got(archived) else "live")
    assert got(live) == ["H07", "H30", "S99"], got(live)
    assert BC.years(["1989-1990", "2023-2024"]) == "1989 to 2024"
    # By run: a committee's record that stops and starts again is not said
    # to run through the years between.
    assert BC.runs(["1989-1990", "1991-1992", "1997-1998", "2011-2012"]) == \
        "1989 to 1992, 1997 to 1998 and 2011 to 2012"
    # And the committee's own page says it, since a reader from a search never
    # sees the listing.
    src = _source(_paths.locate("build_committees.py"))
    assert 'rec["archived"] = {"years": runs(c["span"])}' in src, \
        "archived committees' JSON no longer carries the years"
    # The whole function, to the next one: a fixed 1,200 characters lost the
    # note when a comment above it grew (16 October 2026).
    head = _source("src/pages/app.js")
    head = head[head.find("function renderCommitteeHead"):]
    head = head[:head.find("\nfunction ", 1)]
    assert "c.archived" in head and "A former committee." in head, (
        "a committee's page no longer says it is a former committee")
    return "ok", "not listed and ended before this term; no record means no claim"


# The House listing's Rules committee on 6 September 2026, as the General Court
# printed it: an assistant and a researcher labelled and left blank.
_CMTE_BLANKS = (
    "<h5 class=\"card-header\"><a href='committeedetails.aspx?id=14'>Rules</a></h5>"
    "<div class=\"card-body\"><p class=\"card-text\">"
    "Chairman:&nbsp;Sherman Packard<br />Vice Chairman:&nbsp;Steven Smith<br />"
    "Committee Assistant:&nbsp;<br />Researcher:&nbsp;<br /><br />"
    "Location:&nbsp;<span title='Granite Place'>GP&nbsp;Room&nbsp;000</span><br />"
    "Phone:&nbsp;603-271-3661</p></div>" + "<!-- the committee's section -->" * 6)


@check("build", "a label left blank on a committee page reads as blank, not as the next label",
       needs=("fetch_committees", "fetch_committee_details"))
def _committee_blank_labels(FC, FCD):
    """Both committee parsers find a label and take what follows it, skipping
    the markup between -- which is how they read the House's "Label:&nbsp;"
    at all. A label the page leaves blank is followed by the next label, so
    the House listing of 6 September gave Rules an aide called "Researcher:"
    and a researcher called "Location:", and a blank "Clerk:" on a committee's
    own page read the start of its duty as the clerk.

    A reading that ends in a colon, or begins with a label or with the duty's
    "Pursuant to", is empty now. The two parsers keep one list of the labels
    between them, and it must name every label either asks for.
    """
    rows = FC.parse(_CMTE_BLANKS, "H")
    assert len(rows) == 1, f"fetch_committees.parse no longer reads the Rules block: {rows}"
    r = rows[0]
    assert not r.get("aide") and not r.get("researcher"), (
        f"a blank label on the listing read as the next one: aide {r.get('aide')!r}, "
        f"researcher {r.get('researcher')!r}")
    assert (r.get("chair"), r.get("vice_chair"), r.get("location"), r.get("phone")) == (
        "Sherman Packard", "Steven Smith", "GP Room 000", "603-271-3661"), (
        f"the labels that are filled in no longer read: {r}")

    body = ("<div>Chairman:&nbsp;Jane Doe<br />Clerk:&nbsp;<br /></div><p>Pursuant to "
            "House Rule 99: It shall be the duty of the Committee on Fixture Affairs to "
            "consider matters relating to fixtures, and such other matters as may be "
            "referred to it.</p><div>HELPFUL LINKS</div>")
    rec = FCD.parse(body)
    assert not rec.get("clerk"), f"a blank Clerk: read the duty as the clerk: {rec.get('clerk')!r}"
    assert (rec.get("purpose") or {}).get("rule") == "House Rule 99", (
        f"the duty after a blank clerk no longer reads: {rec.get('purpose')}")
    rec = FCD.parse("Clerk:&nbsp;<br />Researcher:&nbsp;Rae Search<br />Phone:&nbsp;<br />")
    assert not rec.get("clerk") and rec.get("researcher") == "Rae Search" and not rec.get(
        "phone"), f"a blank label on a committee page read the next one: {rec}"
    for mod in (FC, FCD):
        assert mod.labelled("Location:&nbsp;Room 302<br />", "Location") == "Room 302", (
            f"{mod.__name__} no longer reads a room that begins with the word Room")
        assert mod.labelled("Chairman:&nbsp;Chairez Smith<br />", "Chairman") == "Chairez Smith"

    # Which labels each parser asks for, from the parser itself: labelled() is
    # wrapped and each parse run on a section that names nothing, so every
    # fallback to a label is taken.
    labels = {}
    bare_section = ("<h3><a href='committeedetails.aspx?id=1'>Nothing Filled</a></h3>"
                    + "<!-- the committee's section -->" * 8)
    for mod, run in ((FC, lambda: FC.parse(bare_section, "H")),
                     (FCD, lambda: FCD.parse(bare_section))):
        asked, real = set(), mod.labelled

        def listen(block, *labs, _real=real, _asked=asked):
            _asked.update(labs)
            return _real(block, *labs)
        mod.labelled = listen
        try:
            run()
        finally:
            mod.labelled = real
        assert asked, f"{mod.__name__}: its parser asked labelled() for nothing"
        known = {x.lower() for x in mod.LABELS}
        missing = sorted(x for x in asked if x.lower() not in known)
        assert not missing, (f"{mod.__name__} asks for {missing}, which its LABELS does not "
                             "name, so a blank label before one of them reads it as a value")
        labels[mod.__name__] = set(mod.LABELS)
    assert labels["fetch_committees"] == labels["fetch_committee_details"], (
        "the two committee parsers' LABELS differ: "
        f"{sorted(labels['fetch_committees'] ^ labels['fetch_committee_details'])}")
    return "ok", ("the 6 September Rules block gives no aide and no researcher; a blank "
                  "clerk is blank; both parsers share one list of labels")


@check("build", "an older committee name links, as written, to the committee the General Court files it under",
       needs=("committee_names", "build_committees", "build_site_v2"))
def _committee_older_names(committee_names, build_committees, build_site_v2):
    """The person decided on 24 September that a bill or a hearing naming a
    committee by a name it has since lost prints that name and links to the
    committee it was, and that committees the General Court no longer lists
    get pages in the committees page's archived list.

    Which committee a name was is the General Court's own filing, never the
    names looking alike (committee_names.CODES). The case that shows why: the
    Senate's Election Law and Internal Affairs of 2007-2008 is the retired
    S33, and linked by name alone its 77 bills went to S50, formed under the
    same name for 2017-2018 -- two committees shown as one. And 1995-2008's
    House Commerce is H33, not 2009's Commerce and Consumer Affairs, H43.

    The same case is why a retired name that comes back after a gap links
    nowhere. The search list prints a retired code's name in capitals, which
    says the code is retired and not which one, and the first version of this
    table put the Senate's Internal Affairs of 1997-2006 and 2011-2012 on S09
    and the House's Local and Regulated Revenues of 2009-2010 on H21 on the
    strength of those capitals alone: 412 bills and 184 sittings on two
    archived pages, shown as one committee's record across gaps of four and
    ten years.

    On 25 September 25 names still linked nowhere, and one bill-status page
    was fetched for each. Those pages link the Senate's committee as
    committee_details.aspx?cc=S20, not code=, which a search for the House's
    form had missed: 24 of the 25 were settled by them, 2,686 card and 3,611
    hearing mentions came to link, and none that linked before moved. The
    25th is why a page is read and not just matched: 1989 HB 15 and HB 27 file
    the Senate's Development, Recreation and Environment under S03, a code
    that prints APPROPRIATIONS and is 1993's Appropriations -- two committees,
    one code, a gap between.

    The person decided both gaps that day, and committee_names.GAPS holds
    the decisions with their evidence. S03 is two committees, "listed
    separately": Development, Recreation and Environment has a page of its
    own, S03-1989, which says the General Court's records file it under S03,
    the number later given to Appropriations, and Appropriations keeps S03.
    The Senate's Internal Affairs came back twice, and STATUS 2011 CACR 14
    files it under S09 again: one committee, on S09's page. On the record of
    25 September that linked 493 card and 484 hearing mentions that linked
    nowhere, and moved none that did. codes_problems accepts exactly those
    gaps; the mutations below are the proof that it still refuses a gap or a
    reuse nobody decided.
    """
    from collections import Counter as C
    CN, BC, B = committee_names, build_committees, build_site_v2
    bad = CN.codes_problems()
    assert not bad, "; ".join(bad[:4])
    assert {(g[0], g[1], g[2]): g[3] for g in CN.GAPS} == {
        ("S03", 1990, 1993): CN.DIFFERENT, ("S09", 1992, 1997): CN.SAME,
        ("S09", 2006, 2011): CN.SAME}, f"GAPS is not the person's two decisions: {CN.GAPS}"

    def refused(why, said):
        back = CN.codes_problems()
        assert any(said(b) for b in back), (
            f"{why} is no longer refused: " + ("; ".join(back[:3]) or "no problem at all"))
    # A GAP NOBODY DECIDED. The House's Local and Regulated Revenues of
    # 2009-2010 prints in capitals as H21 does after ten years without the
    # name, and no page files it under H21: put there, it is refused.
    lrr = ("H", 2009, 2010, "Local and Regulated Revenues", None)
    i = CN.CODES.index(lrr)
    CN.CODES[i] = lrr[:4] + ("H21",)
    try:
        refused("H21 on a run begun after a gap", lambda b: b.startswith("H21:") and "gap" in b)
    finally:
        CN.CODES[i] = lrr
    # A REUSE NOBODY DECIDED: another committee's name on S03 after
    # Appropriations, across terms with nothing under it.
    CN.CODES.append(("S", 2005, 2006, "Health and Human Services", "S03"))
    try:
        refused("another committee on S03 after a gap",
                lambda b: b.startswith("S03:") and "gap" in b and "Health" in b)
    finally:
        CN.CODES.pop()
    # EACH DECISION TAKEN AWAY: the gap it decided is refused again.
    for k, g in enumerate(list(CN.GAPS)):
        del CN.GAPS[k]
        try:
            refused(f"{g[0]}'s gap after {g[1]} with no decision in GAPS",
                    lambda b: b.startswith(g[0] + ":") and "gap" in b and f"to {g[1]}," in b)
        finally:
            CN.GAPS.insert(k, g)
    # A DECISION ABOUT NO GAP decides nothing, and is refused: S20 runs
    # unbroken across Fish and Game/Recreation, and nobody decided anything
    # about 1994 and 1995.
    CN.GAPS.append(("S20", 1994, 1995, CN.SAME))
    try:
        refused("a decision about a gap S20 does not have",
                lambda b: b.startswith("GAPS S20 1994-1995") and "no such gap" in b)
    finally:
        CN.GAPS.pop()
    assert not CN.codes_problems(), "the table was not put back as it was"
    today = {(ch, CN._norm(nm)): code for ch, nm, code in (
        ("H", "Criminal Justice and Public Safety", "H26"),
        ("H", "Commerce and Consumer Affairs", "H43"),
        ("H", "Special Committee on Public Employee Pension Plans", "H47"),
        ("S", "Election Law and Internal Affairs", "S50"),
        ("S", "Rules and Enrolled Bills", "S45"),
        ("S", "Executive Departments and Administration", "S06"))}
    for name, ch, term, want in (
            ("Corrections and Criminal Justice", "H", "1995-1996", "H26"),
            ("Corrections and Criminal Justice", "H", "1993-1994", "H26"),
            ("Criminal Justice and Public Safety", "H", "2025-2026", "H26"),
            ("Criminal Justice and Public Safety", "H", "", "H26"),
            ("Special Committee on Public Employee Pensions Reform", "H", "2011-2012", "H47"),
            ("Commerce", "H", "2003-2004", "H33"),
            ("Commerce and Consumer Affairs", "H", "2013-2014", "H43"),
            ("Election Law and Internal Affairs", "S", "2007-2008", "S33"),
            ("Election Law and Internal Affairs", "S", "2017-2018", "S50"),
            # STATUS 2005 HCR 11 files 2005's under S22, RULES AND ENROLLED
            # BILLS in capitals: the retired code, not the S45 formed later.
            ("Rules and Enrolled Bills", "S", "2005-2006", "S22"),
            ("Rules and Enrolled Bills", "S", "2007-2008", "S22"),
            ("Rules and Enrolled Bills", "S", "2023-2024", "S45"),
            # A run no witness reaches links nowhere, however alike the name:
            # 2009-2010's Fish and Game may be H08 or H42. 1989 HB 27 and 1991
            # HB 41 file 1989-1992's under H08, FISH AND GAME.
            ("Fish and Game", "H", "2009-2010", None),
            ("Fish and Game", "H", "1991-1992", "H08"),
            ("Fish and Game", "H", "2005-2006", "H08"),
            # The Senate's section of a page gives its code as cc=S20. 1991 HB
            # 41 files Wildlife and Recreation under S20, printed WILDLIFE &
            # RECREATION, and 1995 HB 107 files the name of the one term
            # between under the same code, so the name's later run is S20 too.
            ("Wildlife and Recreation", "S", "1991-1992", "S20"),
            ("Fish and Game/Recreation", "S", "1995-1996", "S20"),
            ("Wildlife and Recreation", "S", "2001-2002", "S20"),
            # Today's pages, under the names the bills had: 1989 HB 36 and HB
            # 244, whose texts print "REFERRED TO: State Institutions and
            # Housing", are filed under H26; 1989 CACR 1's Senate referral,
            # "Executive Departments", under S06.
            ("State Institutions and Housing", "H", "1989-1990", "H26"),
            ("Executive Departments", "S", "1991-1992", "S06"),
            ("Executive Departments and Administration", "S", "1993-1994", "S06"),
            # ONE CODE, TWO COMMITTEES, the person's decision: 1989 HB 15 and
            # HB 27 file the Senate's Development, Recreation and Environment
            # under S03, which prints APPROPRIATIONS and files 1993 SB 30's
            # Appropriations. Appropriations keeps S03's page, and the earlier
            # committee has its own.
            ("Development, Recreation and Environment", "S", "1989-1990", "S03-1989"),
            ("Appropriations", "S", "1993-1994", "S03"),
            ("Economic Development", "S", "1993-1994", "S18"),
            ("Economic Development", "H", "1993-1994", "H32"),
            # Witnessed by a bill-status page, and unbroken from it.
            ("Internal Affairs", "S", "1991-1992", "S09"),
            ("Local and Regulated Revenues", "H", "1997-1998", "H21"),
            # ONE COMMITTEE THAT CAME BACK, the person's decision: STATUS 2011
            # CACR 14 files it under S09 again. The years between link nowhere.
            ("Internal Affairs", "S", "1999-2000", "S09"),
            ("Internal Affairs", "S", "2011-2012", "S09"),
            ("Internal Affairs", "S", "2009-2010", None),
            # Back after a gap nobody decided, and printed in capitals only.
            ("Local and Regulated Revenues", "H", "2009-2010", None)):
        got = CN.page_code(name, ch, term, today)
        assert got == want, f"page_code({name!r}, {ch}, {term!r}) is {got!r}, not {want!r}"
    # The code a bill-status page links is the General Court's, whatever
    # page the committee has here.
    for name, term, want in (("Development, Recreation and Environment", "1989-1990", "S03"),
                             ("Appropriations", "1993-1994", "S03"),
                             ("Internal Affairs", "2011-2012", "S09")):
        got = CN.court_code(name, "S", term, today)
        assert got == want, f"court_code({name!r}, S, {term!r}) is {got!r}, not {want!r}"
    last = CN.retired()
    assert (last["H33"], last["S18"], last["H21"]) == (
        "Commerce", "Energy and Economic Development", "Local and Regulated Revenues"), last
    assert (last["S03-1989"], last["S03"], last["S09"]) == (
        "Development, Recreation and Environment", "Appropriations", "Internal Affairs"), last
    assert CN.shared() == {"S03": ("S03", ["S03-1989"]), "S03-1989": ("S03", ["S03"])}, CN.shared()
    # S20's archived page takes the name the General Court prints for the
    # code, WILDLIFE & RECREATION, not the one of the term between; S35's
    # the longer of its two 2007-2008 names, which ran on to 2010.
    assert (last["S20"], last["S35"], last["S22"]) == (
        "Wildlife and Recreation", "Wildlife, Fish and Game and Agriculture",
        "Rules and Enrolled Bills"), last

    # meta.json's map, which the page hands cmteLink.
    links = B.committee_links([
        {"term": "1995-1996", "committees": ["House Corrections and Criminal Justice"]},
        {"term": "2003-2004", "committees": ["House Commerce"]},
        {"term": "2005-2006", "committees": ["Senate Rules and Enrolled Bills"]},
        {"term": "2007-2008", "committees": ["Senate Election Law and Internal Affairs"]},
        {"term": "2017-2018", "committees": ["Senate Election Law and Internal Affairs"]},
        {"term": "2023-2024", "committees": ["Senate Rules and Enrolled Bills"]},
        {"term": "1991-1992", "committees": ["Senate Internal Affairs"]},
        {"term": "2011-2012", "committees": ["Senate Internal Affairs"]},
        {"term": "1991-1992", "committees": ["Senate Wildlife and Recreation"]},
        {"term": "2001-2002", "committees": ["Senate Wildlife and Recreation"]},
        {"term": "1989-1990", "committees": ["House State Institutions and Housing",
                                             "Senate Development, Recreation and Environment"]}],
        {"House Criminal Justice and Public Safety": "H26",
         "Senate Election Law and Internal Affairs": "S50",
         "Senate Rules and Enrolled Bills": "S45"})
    for full, want in (("House Corrections and Criminal Justice", "H26"),
                       ("House Commerce", "H33"),
                       ("House Criminal Justice and Public Safety", "H26"),
                       ("Senate Election Law and Internal Affairs", {"": "S50", "2007-2008": "S33"}),
                       ("Senate Rules and Enrolled Bills", {"": "S45", "2005-2006": "S22"}),
                       ("Senate Internal Affairs", "S09"),
                       ("Senate Wildlife and Recreation", "S20"),
                       ("House State Institutions and Housing", "H26"),
                       ("Senate Development, Recreation and Environment", "S03-1989")):
        assert links.get(full) == want, f"committee_codes[{full!r}] is {links.get(full)!r}, not {want!r}"

    # Each page of the code the General Court gave two committees names the
    # other, with the other's years, and a page with no record is named by
    # none: it is nowhere to send a reader.
    idx_ = [{"code": "S03", "name": "Appropriations"},
            {"code": "S03-1989", "name": "Development, Recreation and Environment"}]
    got = BC.shared_pages(CN.shared(), {"S03": ["1993-1994"], "S03-1989": ["1989-1990"]}, idx_)
    assert got == {
        "S03-1989": ("S03", [{"page": "S03", "name": "Appropriations",
                              "years": "1993 to 1994", "when": "later"}]),
        "S03": ("S03", [{"page": "S03-1989", "name": "Development, Recreation and Environment",
                         "years": "1989 to 1990", "when": "earlier"}])}, got
    assert BC.shared_pages(CN.shared(), {"S03-1989": ["1989-1990"]}, idx_[1:]) == {}

    # The committee's own page: the day under the name it had, the page head
    # naming what it was called before, and main() asking by term.
    assert BC.name_on_the_day("Criminal Justice and Public Safety",
                              C({"Corrections and Criminal Justice": 3})) == \
        "Corrections and Criminal Justice"
    assert BC.name_on_the_day("Criminal Justice and Public Safety",
                              C({"Criminal justice and public safety": 2})) == \
        "Criminal Justice and Public Safety"
    assert BC.former_names("Local and Regulated Revenues", {
        "Regulated Revenues": {"1989-1990", "1991-1992", "1993-1994", "1995-1996"},
        "Local and Regulated Revenues": {"1997-1998"}}) == [
        {"name": "Regulated Revenues", "years": "1989 to 1996"}]
    assert BC.runs(["2009-2010", "1997-1998"]) == "1997 to 1998 and 2009 to 2010"
    src = _source(BC.__file__)
    # From who_sits on: main() reads the codes, the retired ones among them,
    # through who_sits since 10 October 2026, which with_roster shares.
    main_ = src[src.index("def who_sits("):]
    assert "R = who_sits(site, data)" in src[src.index("def main("):], (
        "build_committees.main no longer reads the codes through who_sits")
    for said in ("CN.retired()", 'code_of(cname, r.get("body"), r.get("term"))',
                 'code_of(nm, "", b.get("term"))', "name_on_the_day(name,",
                 "shared_pages(CN.shared(), span_of, index)", 'rec["same_code"] = '):
        assert said in main_, f"build_committees.main (or who_sits) no longer has {said}"
    # A retired page's tab and search result carry its years, since S33's
    # name is S50's too.
    assert 'title=f"{name}{when} — ' in main_ and \
        "if code in retired and span_of[code]" in main_, (
        "a retired committee's title no longer carries its years")

    # And the page: the name as the bill carries it, to the page of its term.
    ext, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    if not (ext.exists() and stub.exists()) or not shutil.which("node"):
        return "skip", "resolved and mapped; app.js, dom_stub.js or node not here to draw it"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(ext)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "links.json").write_text(json.dumps(links), encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
const src = fs.readFileSync("./page.js", "utf8");
let scope;
try { scope = (0, eval)(src + "; ({cmteLink, billByline, renderCommitteeHead, setMeta: m => { META = m; }});"); }
catch (e) { console.log("LOAD " + e.message); process.exit(1); }
// meta.json's map: the page's META, which a card's byline hands cmteLink, and
// what cmteLink is handed here.
const CODES = JSON.parse(fs.readFileSync("./links.json", "utf8"));
scope.setMeta({committee_codes: CODES});
const link = (name, term) => scope.cmteLink(name, term, CODES);
const E = "Senate Election Law and Internal Affairs";
const out = {
  old: link("House Corrections and Criminal Justice", "1995-1996"),
  s33: link(E, "2007-2008"), s50: link(E, "2017-2018"),
  none: link(E), reb: link("Senate Rules and Enrolled Bills", "2005-2006"),
  ia92: link("Senate Internal Affairs", "1991-1992"),
  ia12: link("Senate Internal Affairs", "2011-2012"),
  wr: link("Senate Wildlife and Recreation", "2001-2002"),
  dre: link("Senate Development, Recreation and Environment", "1989-1990"),
  card: scope.billByline(null, [E, "House Commerce"], "", "2007-2008", CODES),
  head: scope.renderCommitteeHead({code: "H26", name: "Criminal Justice and Public Safety",
    chamber: "H", names: [{name: "Corrections and Criminal Justice", years: "1993 to 1996"}]}),
  s03_1989: scope.renderCommitteeHead({code: "S03-1989",
    name: "Development, Recreation and Environment", chamber: "S",
    same_code: {code: "S03", others: [{page: "S03", name: "Appropriations",
                                       years: "1993 to 1994", when: "later"}]}}),
  s03: scope.renderCommitteeHead({code: "S03", name: "Appropriations", chamber: "S",
    same_code: {code: "S03", others: [{page: "S03-1989",
      name: "Development, Recreation and Environment", years: "1989 to 1990", when: "earlier"}]}})};
fs.writeFileSync("./out.json", JSON.stringify(out));
""", encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True, text=True, timeout=90)
        assert r.returncode == 0, (r.stdout + r.stderr).strip()[:200]
        out = json.loads((root / "out.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert out["old"] == ('<a href="committee/H26">House Corrections and '
                          'Criminal Justice</a>'), out["old"]
    assert "committee/S33" in out["s33"] and "committee/S50" in out["s50"] \
        and "committee/S50" in out["none"], (out["s33"], out["s50"], out["none"])
    assert "committee/S22" in out["reb"] and "S45" not in out["reb"], (
        "2005's Rules and Enrolled Bills does not link to S22, the code its page "
        "files it under: " + out["reb"])
    assert out["wr"] == ('<a href="committee/S20">Senate Wildlife and '
                         'Recreation</a>'), out["wr"]
    assert out["dre"] == ('<a href="committee/S03-1989">Senate Development, '
                          'Recreation and Environment</a>'), (
        "1989's Development, Recreation and Environment does not link to its own "
        "page: " + out["dre"])
    assert "committee/S09" in out["ia92"] and "committee/S09" in out["ia12"], (
        "the Senate's Internal Affairs does not link across its gaps to S09: "
        + out["ia92"] + " / " + out["ia12"])
    assert "committee/S33" in out["card"] and "committee/H33" in out["card"] \
        and "S50" not in out["card"], "a card does not link by its own term: " + out["card"]
    head = re.sub(r"\s+", " ", out["head"])
    assert "<b>Corrections and Criminal Justice</b> (1993 to 1996)" in head, (
        "the committee's page does not name what it was called before: " + head[:300])
    assert "under the code" not in head, "a page whose code is its own says it shares it"
    # And each page of S03 says plainly that the number is shared by two
    # committees, naming the other.
    s89, s03 = (re.sub(r"\s+", " ", out[k]) for k in ("s03_1989", "s03"))
    assert ("The General Court files this committee under the code <b>S03</b> in its own "
            "records, and later gave the same number to the Senate Committee on "
            '<a href="committee/S03">Appropriations</a> (1993 to 1994). The two are '
            "different committees" in s89), (
        "Development, Recreation and Environment's page does not say it shares S03 with "
        "Appropriations: " + s89[:600])
    assert ("also file an earlier committee under the code <b>S03</b>: the Senate Committee "
            'on <a href="committee/S03-1989">Development, Recreation and Environment'
            "</a> (1989 to 1990). The two are different committees" in s03), (
        "Appropriations' page does not name the earlier committee under S03: " + s03[:600])
    return "ok", (f"{len(CN.CODES)} older names placed on {len(last)} pages of the General "
                  f"Court's own codes, {len(CN.GAPS)} gaps in them decided by the person and "
                  "no other accepted; linked by term, printed as the bill has them")


@check("data", "no bill-status page on disk files a committee under another code than the table's",
       needs=("committee_names",))
def _committee_codes_pages(committee_names):
    """committee_names.CODES cites the legacy bill-status pages in
    archive_samples/ as its witness, and this reads every one of them against
    it: the code a chamber's section links its committee of referral by must
    be the code the table sends that bill's committee to, wherever the table
    places the name at all.

    Both forms of the link are read, code=H26 in the House's section and
    cc=S20 in the Senate's. The 25 names that linked nowhere on 25 September
    were read with the first alone, which found no Senate code on any page;
    the pages fetched for them gave a Senate code for all 16 Senate names.
    A code the table does not place yet is listed rather than failed: 1989 HB
    15 files the Senate's Development, Recreation and Environment under S03,
    Appropriations' code, and that was a decision, not a mistake to fix here.
    The person made it the same day, and the table now places the name on
    S03 with a page of its own, S03-1989: so the comparison is with the
    General Court's code (court_code), never with the page it has here.
    """
    CN = committee_names
    root, fb, fc = Path("archive_samples"), Path("data/bills.json"), Path("data/committees.json")
    if not (root.is_dir() and fb.exists() and fc.exists()):
        return "skip", "archive_samples/, data/bills.json or data/committees.json not here"
    bills = json.loads(fb.read_text(encoding="utf-8"))
    today = {(c[:1].upper(), CN._norm(r.get("name") or "")): c
             for c, r in json.loads(fc.read_text(encoding="utf-8")).items()
             if (r.get("name") or "").strip() and c[:1].upper() in ("H", "S")}
    sect = re.compile(r"(?i)\b(House|Senate) Status\s*</b>")
    row = re.compile(r"(?is)Committee of Referral\s*</STRONG>(.*?)</tr>")
    link = re.compile(r"(?i)[?&](?:code|cc)=([A-Za-z]+\d+)")
    placed, differ, unplaced, pages = 0, [], [], 0
    for f in sorted(root.glob("[12][0-9][0-9][0-9]/*.html")):
        year, bill = f.parent.name, f.stem.upper()
        y = int(year)
        term = f"{y}-{y + 1}" if y % 2 else f"{y - 1}-{y}"
        rec = (bills.get(term) or {}).get(bill)
        if not rec or str(rec.get("lsr_year") or year) != year:
            continue
        pages += 1
        parts = sect.split(f.read_text(encoding="utf-8", errors="replace"))
        for word, body in zip(parts[1::2], parts[2::2]):
            ch = word[:1].upper()
            name = rec.get("house_committee" if ch == "H" else "senate_committee") or ""
            m = row.search(body)
            got = link.search(m.group(1)) if m else None
            if not name or not got:
                continue
            want = CN.court_code(name, ch, term, today)
            if want is None:
                unplaced.append(f"{year} {bill} {ch} {name!r} {got.group(1)}")
            elif want.upper() != got.group(1).upper():
                differ.append(f"{year} {bill} {ch} {name!r}: the table says {want}, "
                              f"the page {got.group(1)}")
            else:
                placed += 1
    assert placed, (f"no committee of referral was read off {pages} status pages: "
                    "the page's shape has changed, or this check has")
    assert not differ, (f"{len(differ)} status pages file a committee under another "
                        "code than committee_names gives it: " + "; ".join(differ[:4]))
    return "ok", (f"{placed} committees of referral on {pages} pages filed where the "
                  f"table puts them; {len(unplaced)} under a code it does not place"
                  + (": " + "; ".join(unplaced) if unplaced else ""))


# A committee's page as renderPage draws it, after _HEARD_PRELUDE: its Bills
# tab and its Meetings tab, Show more pressed on each, the Bill status select
# set to each category it offers and changed through its own handler, and a
# day named by the address. fx.json holds the index rows and the committee.
_COMMITTEE_PAGED_HARNESS = r"""
load("renderPage, IDX, focusKey, setPage: (p) => { PAGE = p; }, getPage: () => PAGE,"
  + " setTab: (t) => { PAGE_TAB = t; }, setMeta: (m) => { META = m; }, setTerm: (t) => { term = t; }");
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
s.setMeta({terms: ["2025-2026"], committee_codes: {}, topics: []});
s.setTerm("2025-2026");
s.IDX.length = 0; fx.rows.forEach(r => s.IDX.push(r));
const results = document.querySelector("#results");
const draw = () => { s.renderPage(); return results.innerHTML; };
const fresh = (status) => s.setPage({kind: "committee", data: fx.committee, terms: ["2025-2026"],
  term: "2025-2026", status: status || "", vfilter: "", vparty: "", vshow: 0, bshow: 0, mshow: 0});
// The list the button names, as the browser would hand it back: what focus()
// was called on, by the list's key and the item's place in it.
let took = [];
const list = (n, key) => ({children: Array.from({length: n}, (_, i) => ({tabIndex: 0,
  querySelector: q => q === "summary,a[href],button" ? {focus() { took.push(key + "@" + i); }} : null,
  focus() { took.push(key + "#" + i); }}))});
const realGet = document.getElementById;
const press = (key, from, ctl, n) => {
  document.getElementById = id => id === ctl ? list(n, key) : realGet.call(document, id);
  took = [];
  click(q => q === "[data-pmore]" ? {dataset: {pmore: key, from: String(from)},
    getAttribute: k => (k === "aria-controls" ? ctl : null)} : null);
  document.getElementById = realGet;
  return {html: results.innerHTML, took: took.slice(), count: s.getPage()[key]};
};
const out = {};
try {
  fresh(""); s.setTab(0);
  out.first = draw();
  out.more1 = press("bshow", 20, "pbills", 45);
  out.more2 = press("bshow", 40, "pbills", 45);
  out.filtered = {};
  for (const st of fx.cats) { fresh(st); out.filtered[st] = draw(); }
  fresh(""); draw(); s.getPage().bshow = 40;
  heard.document.change.forEach(f => f({target: {dataset: {pf: "status"}, value: "Died",
    closest: () => null}}));
  out.changed = {bshow: s.getPage().bshow, html: results.innerHTML};
  fresh(""); s.setTab(1);
  out.meet = draw();
  out.meetMore = press("mshow", 20, "pmeets", 30);
  fresh(""); s.setTab(1); location.hash = "#" + fx.named;
  out.named = draw();
  location.hash = "";
  out.key = s.focusKey({dataset: {pmore: "bshow", from: "20"}, tagName: "BUTTON", id: "",
    closest: q => (q === "#results,#facets" ? {} : null), classList: [], getAttribute: () => null});
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a committee's Bills and Meetings tabs show twenty at a time: Show more brings "
                   "the next twenty and the keyboard to the first of them, the Bill status "
                   "select's counts are its cards, a day the address names is shown, and printed "
                   "or without script every one is there",
       needs=("build_committees",))
def _committee_lists_paged(BC):
    """The person, 23 October 2026: committee pages were far too long on a
    phone. House Executive Departments and Administration was 94,689px tall
    at 375px wide, a full card for each of its 164 bills of 2025-2026, and
    its Meetings tab, 46 days, 17,712px. app.js (A COMMITTEE'S LONG LISTS)
    shows the first twenty of each and a button for the next twenty.

    Run in node over a committee of 45 bills -- 30 died, 10 passed, 5 still
    in committee -- and 30 meetings. Held: the Bills tab draws all 45 cards
    in number order and marks every one past the twentieth .unshown; its
    button says "Show 20 more -- 25 of 45 not yet shown", names the list
    (aria-controls) and says where the next begins (data-from), and pressed
    it shows forty, then all 45 with no button, putting focus each time on
    the first focusable of the first card it brought; the select's options
    read each category with its count, the counts add to the tab, and each
    chosen lists that many cards, twenty of them shown and the button only
    over twenty; choosing a status through the select's own handler starts
    the list again at twenty; the Meetings tab the same, twenty days of
    thirty and focus on the 21st day's summary; a day the address names,
    the 27th, is shown and open, the list drawn as far as it; and Show more
    is given no focus key, so the redraw does not pull focus back to it.
    Read: .unshown is hidden by app.css on a screen and nowhere else, and
    the button left off the sheet, so a printed page has every card; and
    the plain page a reader without script gets (build_committees.
    static_record) lists all 45 bills."""
    def row(bid, kind, chip, status=None):
        return {"id": bid, "n": re.sub(r"^([A-Z]+)", r"\1 ", bid), "title": "a bill",
                "kind": kind, "status": status or chip, "chip": chip, "committees": [],
                "committee": "", "topic": "", "sponsor": "", "term": "2025-2026",
                "year": 2025, "passage": "", "votedays": [], "nrc": 0, "last_action": ""}
    rows = ([row(f"HB{i}", "done", "Died", "Killed") for i in range(1, 31)]
            + [row(f"HB{i}", "law", "Became Law", "Signed into law") for i in range(31, 41)]
            + [row(f"HB{i}", "active", "In committee") for i in range(41, 46)])
    import datetime as _dt
    dates = [(_dt.date(2025, 1, 6) + _dt.timedelta(days=3 * i)).isoformat() for i in range(30)]
    sessions = [{"date": d, "term": "2025-2026",
                 "items": [{"bill": "HB1", "kind": "public hearing", "time": "10:00",
                            "venue": "LOB 306", "term": "2025-2026", "year": 2025}],
                 "outcomes": [{"bill": "HB1", "kinds": ["public hearing"], "outcome": "heard"}]}
                for d in dates]
    named = "day-" + sorted(dates, reverse=True)[26]
    committee = {"code": "H07", "name": "Executive Departments and Administration",
                 "chamber": "H", "members": [], "officers": [], "sessions": sessions,
                 "bills": {"2025-2026": [{"id": r["id"], "n": r["n"], "term": "2025-2026",
                                          "year": 2025, "title": r["title"], "status": r["status"]}
                                         for r in reversed(rows)]}}
    got = _node_app(_HEARD_PRELUDE + _COMMITTEE_PAGED_HARNESS,
                    {"fx.json": json.dumps({"rows": rows, "committee": committee, "named": named,
                                            "cats": ["In Progress", "Passed", "Died"]})})
    if got is None:
        return "skip", "app.js, dom_stub.js or node is not here"
    assert "threw" not in got, f"a committee's page threw {got['threw']}"
    bad = []
    say = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h.replace("&mdash;", "--"))).strip()

    def read(html, item=r'<article class="card([^"]*)" data-id="([^"]*)"'):
        items = re.findall(item, html)
        btn = re.search(r'<button type="button" class="discl pgmore" data-pmore="(\w+)" '
                        r'data-from="(\d+)"\s+aria-controls="(\w+)">(.*?)</button>', html, re.S)
        return {"all": [i for _c, i in items], "shown": [i for c, i in items if "unshown" not in c],
                "btn": btn and (btn.group(1), int(btn.group(2)), btn.group(3), say(btn.group(4)))}
    ids = [f"HB{i}" for i in range(1, 46)]
    a = read(got["first"])
    if a["all"] != ids or a["shown"] != ids[:20]:
        bad.append(f"the Bills tab draws {len(a['all'])} cards and shows {a['shown'][:3]}... "
                   f"({len(a['shown'])}), not all 45 in number order with the first 20 shown")
    if a["btn"] != ("bshow", 20, "pbills", "Show 20 more -- 25 of 45 not yet shown"):
        bad.append(f"the Bills tab's button is {a['btn']}")
    if '<div class="cards" id="pbills">' not in got["first"] \
            or not re.search(r'<select data-pf="status" aria-controls="pbills"', got["first"]):
        bad.append("the cards are not the list #pbills that the button and the select name")
    for k, n, took, btn in (("more1", 40, "bshow@20", ("bshow", 40, "pbills",
                                                        "Show 5 more -- 5 of 45 not yet shown")),
                            ("more2", 45, "bshow@40", None)):
        r = read(got[k]["html"])
        if r["shown"] != ids[:n] or r["btn"] != btn or got[k]["count"] != int(took[6:]) + 20:
            bad.append(f"Show more ({k}) shows {len(r['shown'])} with the button {r['btn']}, "
                       f"not {n} with {btn}")
        if got[k]["took"] != [took]:
            bad.append(f"after Show more ({k}) focus went to {got[k]['took']}, not the first "
                       f"focusable of the first card it brought ({took})")
    opts = re.findall(r'<option value="([^"]+)"[^>]*>([^<]*)</option>',
                      re.search(r'<select data-pf="status".*?</select>', got["first"], re.S).group(0))
    counted = {}
    for v, text in opts:
        m = re.fullmatch(r"(.+) \((\d+)\)", text.strip())
        if not m or m.group(1) != v:
            bad.append(f"the option {v!r} reads {text.strip()!r}, not the category and its count")
        else:
            counted[v] = int(m.group(2))
    if counted != {"In Progress": 5, "Passed": 10, "Died": 30}:
        bad.append(f"the select counts {counted}, not In Progress 5, Passed 10 and Died 30")
    for v, n in counted.items():
        r = read(got["filtered"].get(v, ""))
        want_btn = ("bshow", 20, "pbills", f"Show {min(20, n - 20)} more -- {n - 20} of {n} not "
                    "yet shown") if n > 20 else None
        if len(r["all"]) != n or len(r["shown"]) != min(n, 20) or r["btn"] != want_btn:
            bad.append(f"{v} ({n}) draws {len(r['all'])} cards, shows {len(r['shown'])}, button "
                       f"{r['btn']}")
    r = read(got["changed"]["html"])
    if got["changed"]["bshow"] != 0 or len(r["shown"]) != 20 or len(r["all"]) != 30:
        bad.append(f"choosing Died after Show more keeps {got['changed']['bshow']} and shows "
                   f"{len(r['shown'])} of {len(r['all'])}: the list does not start again at twenty")
    day = r'<details class="cmeet([^"]*)" id="([^"]*)"'
    m = read(got["meet"], day)
    if len(m["all"]) != 30 or len(m["shown"]) != 20 \
            or m["btn"] != ("mshow", 20, "pmeets", "Show 10 more -- 10 of 30 not yet shown") \
            or '<div class="cmeets" id="pmeets">' not in got["meet"]:
        bad.append(f"the Meetings tab draws {len(m['all'])} days, shows {len(m['shown'])}, "
                   f"button {m['btn']}")
    mm = read(got["meetMore"]["html"], day)
    if len(mm["shown"]) != 30 or mm["btn"] or got["meetMore"]["took"] != ["mshow@20"]:
        bad.append(f"Show more on the meetings shows {len(mm['shown'])}, button {mm['btn']}, "
                   f"focus on {got['meetMore']['took']}, not all 30 and the 21st day's summary")
    nm = read(got["named"], day)
    opened = re.search(rf'<details class="cmeet([^"]*)" id="{named}" open>', got["named"])
    if len(nm["shown"]) != 27 or named not in nm["shown"] or not opened \
            or nm["btn"] != ("mshow", 27, "pmeets", "Show 3 more -- 3 of 30 not yet shown"):
        bad.append(f"the address naming the 27th day shows {len(nm['shown'])} days, it "
                   f"{'open' if opened else 'shut or hidden'}, button {nm['btn']}")
    if got["key"] is not None:
        bad.append(f"Show more is given a focus key, {got['key']}: the redraw would pull focus "
                   "back to the button")
    # On paper and without script.
    css = _source("src/pages/app.css")
    hides = [(ctx, sel) for ctx, sel, body, _ln in _css_rules(css)
             if ".unshown" in sel and "none" in dict(_css_decls(body)).get("display", "")]
    if not hides or any(ctx != ("@media screen",) for ctx, _s in hides):
        bad.append(f"what a list has not reached is hidden {hides}: on a screen and only there, "
                   "or a printed page loses it")
    off = [sel for ctx, sel, body, _ln in _css_rules(css)
           if any(c.startswith("@media print") for c in ctx) and "none" in body
           and ".pgmore" in _css_selectors(sel)]
    if not off:
        bad.append("the button and its count of what is not yet shown print")
    plain = BC.static_record("H07", committee["name"], "House",
                             {"bills": {"2025-2026": [dict(r, year=2025) for r in rows]}}, [])
    listed = re.findall(r'<li><a href="bill/2025/(hb\d+)">', plain)
    if sorted(listed) != sorted(i.lower() for i in ids):
        bad.append(f"the page without script lists {len(listed)} of the 45 bills")
    assert not bad, "; ".join(bad[:6])
    return "ok", ("twenty of 45 bills and of 30 days shown, Show more twenty further with focus "
                  "on the first it brought, the select's counts its cards, a named day shown "
                  "and open, and every card printed and in the page without script")


@check("narrative", "a committee has one name in each term, the one it had then",
       needs=("committee_names",))
def _one_name_per_committee(committee_names):
    """The 1991-1992 Committee filter listed "House Child Y and Jj" (34),
    "House Child, Y and Jj" (12) and "House Children Y and Jj" (3) as three
    committees, 1989-1990 listed 112 values for 39, and the clerk's shorthand
    on 1999-2006's hearings kept every one of them off the committee pages.

    committee_names.official is what settles a name now, and what it may do
    is narrow: return the name it was given, or a name OFFICIAL lists for
    that chamber and term. This holds it to that on real spellings, and to
    the two rules no entry may break: an alias never turns a different
    committee's name, in a term both had, into its own, and never writes a
    name onto a year before the committee carried it.
    """
    CN = committee_names
    bad = CN.conflicts() + CN.unplaced()
    assert not bad, "; ".join(bad[:4])
    cyjj = "Children, Youth and Juvenile Justice"
    cases = (
            # The three the person saw, and 1989's other spellings.
            ("Child Y and Jj", "H", "1991-1992", cyjj),
            ("Child, Y and Jj", "H", "1991-1992", cyjj),
            ("Children Y and Jj", "H", "1991-1992", cyjj),
            ("Children, Youth and Juv Just", "H", "1989-1990", cyjj),
            ("Child/Juv Just", "H", "1989-1990", cyjj),
            # The Senate's nine ways of 1989-1990.
            ("Dev, Rec, and Envir", "S", "1989-1990",
             "Development, Recreation and Environment"),
            ("Dev. Rec. and Env", "S", "1989-1990",
             "Development, Recreation and Environment"),
            # The name at the time, and never a later one.
            ("Executive Departments and Administration", "S", "1991-1992",
             "Executive Departments"),
            ("Exec. Depart", "S", "1989-1990", "Executive Departments"),
            ("EXEC DEPTS+ADMIN", "S", "1993-1994",
             "Executive Departments and Administration"),
            ("Commerce", "H", "1991-1992",
             "Commerce, Small Business and Consumer Affairs"),
            ("Commerce", "H", "1995-1996",
             "Commerce, Small Business, Consumer Affairs and Economic Development"),
            ("Commerce", "H", "1999-2000", "Commerce"),
            ("Public Works", "H", "1993-1994", "Public Works"),
            ("Public Works", "H", "1999-2000", "Public Works and Highways"),
            ("Judiciary", "H", "1997-1998", "Judiciary and Family Law"),
            ("Judiciary", "H", "1999-2000", "Judiciary"),
            ("Health", "H", "1989-1990", "Health, Human Services and Elderly Affairs"),
            ("Special Committee on Public Employee Pension Plans", "H", "2011-2012",
             "Special Committee on Public Employee Pensions Reform"),
            ("Special Committee on Public Employee Pension Plans", "H", "2015-2016",
             "Special Committee on Public Employee Pension Plans"),
            # The clerk's shorthand and what follows the name.
            ("Exec Depts and Admin for Interim Study VV", "H", "2001-2002",
             "Executive Departments and Administration"),
            ("Crim Just and PSfty", "H", "2003-2004", "Criminal Justice and Public Safety"),
            ("Mun and Cnty Govt committee", "H", "1999-2000",
             "Municipal and County Government"),
            ("Elec Law", "H", "1999-2000", "Election Law"),
            ("Health HS and EA: HJ18, p274", "H", "1999-2000",
             "Health, Human Services and Elderly Affairs"),
            ("Executive Departments and Administration [3/17/2011]", "H", "2011-2012",
             "Executive Departments and Administration"),
            ("Finance committee 2/3DIV(226-13)", "H", "1999-2000", "Finance"),
            ("PUBLIC WORKS RC(252-67)", "H", "1997-1998", "Public Works and Highways"),
            ("Wildlife & Recreation", "S", "1999-2000", "Wildlife and Recreation"),
            ("Transportation and Interstate Cooperation Committee", "S", "2009-2010",
             "Transportation and Interstate Cooperation"),
            # Typing slips, where one committee is the only one that close.
            ("Transporation", "H", "1999-2000", "Transportation"),
            ("Enviroment", "S", "1999-2000", "Environment"),
            ("Juduciary", "S", "2003-2004", "Judiciary"),
            # Left as written: a House abbreviation in the Senate; a Senate
            # committee's name expanded for the House; a note that is part of
            # the name; the chamber's own placeholder; and a joint referral.
            ("St Inst", "S", "1991-1992", "St Inst"),
            ("INSUR", "H", "1991-1992", "INSUR"),
            ("Special Committee on the Division for Children, Youth and "
             "Families (DCYF)", "H", "2025-2026",
             "Special Committee on the Division for Children, Youth and "
             "Families (DCYF)"),
            ("No Committee Assignment", "H", "2025-2026", "No Committee Assignment"),
            ("E and a and Rr and D", "H", "1993-1994", "E and a and Rr and D"),
            ("", "H", "1991-1992", ""))
    for name, ch, term, want in cases:
        got = CN.official(name, ch, term)
        assert got == want, f"official({name!r}, {ch}, {term}) gave {got!r}, wanted {want!r}"
    # Every committee the General Court names today comes back as itself, in
    # either chamber, and anything official() writes is left alone by it.
    moved = [f"{ch} {n!r} -> {CN.official(n, ch, '2025-2026')!r}"
             for n in _FULL_COMMITTEE_NAMES for ch in "HS"
             if CN.official(n, ch, "2025-2026") != n]
    assert not moved, "today's names are rewritten: " + "; ".join(moved[:4])
    again = [f"{ch} {lo}-{hi} {nm!r}" for ch, lo, hi, nm in CN.OFFICIAL
             for y in CN.span_terms(lo, hi)
             if CN.official(nm, ch, f"{y}-{y + 1}") != nm]
    assert not again, "an official name is rewritten: " + "; ".join(again[:4])
    return "ok", (f"{len(CN.ALIASES)} aliases onto {len(CN.OFFICIAL)} names at the "
                  "time, none taking another committee's name; "
                  f"{len(cases)} real spellings placed or left as written")


@check("narrative", "a committee sitting today keeps its name, its aliases and its typing slips "
       "into the next term, and a rename is one line in ENDED", needs=("committee_names",))
def _committee_names_outlast_the_term(committee_names):
    """THE TURN OF THE TERM NEEDS NOTHING DONE TO THE TABLE (18 October 2026,
    private/UNATTENDED_AUDIT_2026-10-18.md, section 4.3.2). Every span in
    committee_names' OFFICIAL and ALIASES ended at 2026, and _covers wants
    both years of a term inside a span, so for 2027-2028 official() handed
    every name back as the clerk wrote it: "Finance Division II" stayed
    beside Finance in the Committee filter, "Exec Depts and Admin" kept its
    hearings off Executive Departments and Administration's page, and
    "Juduciary" stayed a committee of its own. No check failed for it. A name
    still in use now ends in NOW, and a committee renamed or closed is one
    line in ENDED.

    Held here: no row or alias, as written, ends in the last year of the
    newest term the tables know (such a row is a name closed before anyone
    knew it ended -- the shape of the bug); the clerk's spellings of three
    committees that sit today are placed in 2027-2028 and 2029-2030 as in
    2025-2026; one ENDED line, close_ended() shows, closes the name's open row
    and every alias that writes it and nothing else; ended_problems() is
    empty for ENDED as it stands and refuses a line that closes nothing, a
    year that ends no term and one before the name's first term."""
    CN = committee_names
    rows = ([("OFFICIAL", ch, lo, hi, nm) for ch, lo, hi, nm in CN.OFFICIAL_AS_WRITTEN]
            + [("ALIASES", ch, lo, hi, full) for ch, lo, hi, _p, full in CN.ALIASES_AS_WRITTEN])
    newest = max(lo for _t, _c, lo, _h, _n in rows)
    newest_end = newest + 1 if newest % 2 else newest
    shut = [f"{t} {ch} {lo}-{hi} {nm!r}" for t, ch, lo, hi, nm in rows
            if hi is not CN.NOW and hi >= newest_end]
    assert not shut, (f"{len(shut)} row(s) end in {newest_end}, the newest term's last year, so the "
                      "name stops at the turn though nobody knows it ended (write NOW, and close a "
                      "name that did end with a line in ENDED): " + "; ".join(shut[:4]))
    assert any(hi is CN.NOW for _t, _c, _l, hi, _n in rows), "no name is still in use"
    for term in ("2025-2026", "2027-2028", "2029-2030"):
        for said, ch, want in (("Finance Division II", "H", "Finance"),
                               ("Exec Depts and Admin", "H", "Executive Departments and Administration"),
                               ("Juduciary", "S", "Judiciary"),
                               ("Ways and Means", "S", "Ways and Means")):
            got = CN.official(said, ch, term)
            assert got == want, f"official({said!r}, {ch}, {term}) gave {got!r}, wanted {want!r}"
    assert not CN.ended_problems(), "; ".join(CN.ended_problems())
    line = ("H", "Finance", 2026)
    o, a = CN.close_ended(CN.OFFICIAL_AS_WRITTEN, CN.ALIASES_AS_WRITTEN, [line])
    changed = [(x, y) for x, y in zip(CN.OFFICIAL_AS_WRITTEN, o) if x != y]
    assert changed == [(("H", 1995, CN.NOW, "Finance"), ("H", 1995, 2026, "Finance"))], (
        f"one ENDED line closed {changed} in OFFICIAL")
    moved = [(x, y) for x, y in zip(CN.ALIASES_AS_WRITTEN, a) if x != y]
    assert moved and all(y[0] == "H" and y[2] == 2026 and y[4] == "Finance" for _x, y in moved) \
        and not [y for x, y in zip(CN.ALIASES_AS_WRITTEN, a)
                 if y[0] == "H" and y[4] == "Finance" and y[2] is CN.NOW], (
        f"one ENDED line left an alias writing House Finance open, or closed another: {moved}")
    bad = CN.ended_problems(ended=[("H", "Nonesuch", 2026), ("S", "Judiciary", 2027),
                                   ("H", "Housing", 2024)])
    assert len(bad) == 3, f"ended_problems let a bad line through: {bad}"
    return "ok", (f"{sum(1 for r in rows if r[3] is CN.NOW)} names and aliases still in use, none "
                  f"ending at {newest_end}; the clerk's spellings placed through 2029-2030; one "
                  f"ENDED line closes House Finance's row and its {len(moved)} aliases, nothing "
                  "else; three bad lines refused")


@check("narrative", "build_data writes each bill's committees under their names at the time",
       needs=("committee_names", "build_data"))
def _bills_official_committees(committee_names, build_data):
    """The alias table does nothing unless build_data runs it, and every
    reader of a bill's committee -- the cards, the Committee filter,
    meta.json, bills.csv, the committee pages' bill lists -- reads what
    build_data wrote. Three 1991-1992 spellings of one committee go in; one
    name comes out, a current bill is left alone, and the count says so."""
    by_term = {
        "1991-1992": {
            "HB1": {"house_committee": "Child Y and Jj", "senate_committee": ""},
            "HB2": {"house_committee": "Child, Y and Jj",
                    "senate_committee": "Executive Departments and Administration"},
            "HB3": {"house_committee": "Children Y and Jj", "senate_committee": "Fin"}},
        "2025-2026": {
            "HB4": {"house_committee": "Municipal and County Government",
                    "senate_committee": "Election Law and Municipal Affairs"}}}
    moved = build_data._official_committees(by_term)
    old = by_term["1991-1992"]
    assert {r["house_committee"] for r in old.values()} == {
        "Children, Youth and Juvenile Justice"}, old
    assert old["HB2"]["senate_committee"] == "Executive Departments", old["HB2"]
    assert old["HB3"]["senate_committee"] == "Finance", old["HB3"]
    assert by_term["2025-2026"]["HB4"] == {
        "house_committee": "Municipal and County Government",
        "senate_committee": "Election Law and Municipal Affairs"}
    assert sum(moved.values()) == 5, moved
    return "ok", "three spellings of 1991-1992 written as one name; a current bill untouched"


@check("data", "the Committee filter names each committee once in a term",
       needs=("committee_names",))
def _committee_filter_one_name(committee_names):
    """The built record against the alias table.

    Every bill-chamber committee in data/bills.json, and every value of the
    bills page's Committee filter in the bill index, must be what
    committee_names.official writes for it -- which is what build_data
    wrote, so this fails when a build ran on older code or a new spelling
    arrived that the table resolves and the data does not yet show. On the
    build of 24 September the filter carried 259 values across all terms,
    112 of them in 1989-1990 for 39 committees.
    """
    fb = Path("data/bills.json")
    if not fb.exists():
        return "skip", "no data/bills.json"
    CN = committee_names
    bills = json.loads(fb.read_text(encoding="utf-8"))
    off = Counter()
    for t, byb in bills.items():
        for rec in byb.values():
            for field, ch in (("house_committee", "H"), ("senate_committee", "S")):
                v = rec.get(field) or ""
                if v and CN.official(v, ch, t) != v:
                    off[f"{t} {ch} {v!r} -> {CN.official(v, ch, t)!r}"] += 1
    assert not off, (f"{sum(off.values()):,} bill committees are not written as "
                     "the committee's name at the time (rebuild with build_all.py "
                     "if the code is newer than data/bills.json): "
                     + "; ".join(k for k, _ in off.most_common(4)))
    rows = _site_bills()
    if rows is None:
        return "ok", "data/bills.json names each committee once; no site built"
    facet = {}
    for row in rows:
        for c in row.get("committees") or []:
            facet.setdefault(row.get("term"), set()).add(c)
    stray = sorted(f"{t} {c!r}" for t, cs in facet.items() for c in cs
                   if c.split(" ", 1)[0] in ("House", "Senate") and
                   CN.official(c.split(" ", 1)[1], c[0], t) != c.split(" ", 1)[1])
    assert not stray, (f"{len(stray)} Committee filter values are another spelling "
                       "of a committee (rebuild the site): " + "; ".join(stray[:4]))
    return "ok", (f"{sum(len(v) for v in facet.values()):,} filter values across "
                  f"{len(facet)} terms, one per committee")


@check("data", "every hearing is filed under the name its committee had then",
       needs=("committee_names", "proceedings"))
def _proceedings_one_name(committee_names, proceedings):
    """proceedings.csv against the alias table, as the check above holds the
    bills to it: a row whose committee committee_names.official would write
    differently is a table built on older code, and a hearing the committee
    pages cannot find. On the table of 24 September 11,911 of 96,438 were in
    that state, 1,094 of them "Exec Depts and Admin"."""
    P = proceedings
    if not Path(P.PATH).exists():
        return "skip", f"no {P.PATH}"
    CN = committee_names
    off, n = Counter(), 0
    for r in P.load():
        c = r.get("committee") or ""
        if not c:
            continue
        n += 1
        if CN.official(c, r.get("body"), r.get("term")) != c:
            off[f"{r.get('term')} {r.get('body')} {c!r}"] += 1
    assert not off, (f"{sum(off.values()):,} of {n:,} committee rows are not written "
                     "as the committee's name at the time (rebuild with "
                     "build_proceedings.py): "
                     + "; ".join(f"{k} x{v}" for k, v in off.most_common(4)))
    return "ok", f"{n:,} committee rows, each under the name its committee had then"


# The fixture's statutory and study committees (_study_fixture): the active
# ones by CommitteeID, and the archived one, which has no page.
STUDY_ACTIVE, STUDY_ARCHIVED = ("1451", "1740", "69"), "44"


@check("build", "every statutory and study committee the General Court lists as active has a page, "
       "in the sitemap and in study_committees.json; an archived one has none; build_committees "
       "leaves them in the sitemap; and a run that would write none fails",
       needs=("build_study_committees", "shell"))
def _study_committee_pages(SC, S):
    """The person, 17 October 2026: statutory and study committees get pages
    of their own, the active ones first (the plan's step 2). SILENCE IS NOT
    SUCCESS: a copy with no active committee, or none on disk, must stop the
    run, not publish a site with no page and a zero in the log."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    shared, base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    pages = sorted(p.stem for p in (site / "committee").glob("ss*.html"))
    assert pages == sorted(f"ss{c}" for c in STUDY_ACTIVE), (
        f"the study committees' pages are {pages}; every active one wants one, the archived "
        f"ss{STUDY_ARCHIVED} none")
    rows = json.loads((site / SC.INDEX).read_text(encoding="utf-8"))
    assert sorted(r["cid"] for r in rows) == sorted(STUDY_ACTIVE) and all(
        r["page"] == f"/committee/ss{r['cid']}.html" for r in rows), (
        f"study_committees.json does not list each page once: {rows}")
    sm = (site / "sitemap.xml").read_text(encoding="utf-8")
    for cid in STUDY_ACTIVE:
        assert f"<loc>{base}/committee/ss{cid}</loc>" in sm, f"/committee/ss{cid} is not in the sitemap"
    assert f"/committee/ss{STUDY_ARCHIVED}<" not in sm and f"<loc>{base}/committee/H43</loc>" in sm, (
        "the sitemap lists the archived committee, or lost the chamber committee's page")
    # build_committees owns /committee, and spares the study committees'.
    tmp = Path(tempfile.mkdtemp(prefix="gr-study-none-"))
    try:
        (tmp / "sitemap.xml").write_text(
            '<?xml version="1.0"?>\n<urlset>\n' + "".join(
                f"<url><loc>{base}/committee/{c}</loc></url>\n" for c in ("H43", "H99", "ss1451"))
            + "</urlset>\n", encoding="utf-8")
        added, dropped = S.sitemap_merge(tmp, base, [f"{base}/committee/H43"], spare=("/committee/ss*",),
                                         owns="/committee")
        locs = re.findall(r"<loc>[^<]*/committee/([^<]+)</loc>",
                          (tmp / "sitemap.xml").read_text(encoding="utf-8"))
        assert locs == ["H43", "ss1451"] and (added, dropped) == (0, 1), (
            f"build_committees' sitemap merge keeps {locs}: it must take out H99, which it no "
            "longer writes, and leave the study committee's page it does not write")
        src = _source(_paths.locate("build_committees.py"))
        assert re.search(r"spare=STUDY_PAGES", src) and '"/committee/ss*"' in src, (
            "build_committees no longer spares the study committees' pages in the sitemap")
        # A RUN THAT WOULD WRITE NONE FAILS, with the copy gone and with one
        # that lists no active committee.
        (tmp / "site").mkdir()
        shutil.copy(Path("src/pages/bills.html"), tmp / "site" / "bills.html")
        for why, text in (("no copy", None),
                          ("no active committee", "|".join(
                              ["44", "2014", "", "", "HB1136"] + [""] * 12
                              + ["Archived Chaptered Study Committee"] + [""] * 10) + "\n")):
            db = tmp / "db"
            shutil.rmtree(db, ignore_errors=True)
            if text is not None:
                db.mkdir()
                (db / "StatStudDetails.psv").write_text(text, encoding="utf-8")
            r = _run([sys.executable, _paths.script("build_study_committees.py"), "--site", "site"],
                     cwd=tmp, capture_output=True, text=True, timeout=120)
            assert r.returncode == 1 and "FAILED" in r.stdout and not list(
                (tmp / "site").glob("committee/ss*.html")), (
                f"with {why}, build_study_committees exited {r.returncode} and said "
                f"{(r.stdout + r.stderr).strip()[-200:]!r}: it must fail, saying so, and write nothing")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(STUDY_ACTIVE)} active committees, {len(STUDY_ACTIVE)} pages, listed and in the "
                  "sitemap; the archived one has none; build_committees spares them; no copy, or no "
                  "active committee, fails the run")


@check("build", "/committees folds the statutory and study committees under the chambers' own, shut, "
       "grouped by the General Court's two classes, each card its kind's chip, with a find box the "
       "script shows", needs=("build_study_committees",))
def _study_committees_listed(SC):
    """The person, 17 October 2026: on the committee page "not as prominently
    as standing committees ... Maybe ... under a drop-down menu of some
    kind". So one fold, shut, after the House and Senate columns and before
    the committees with no record and the former ones; statutory then
    study; a card each, linking its page; and the find box hidden until its
    script shows it, so a reader without script meets no box that does
    nothing."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    import components as C
    shared, _base, _ran, _days = _fixture_site_shared()
    t = (shared / "site" / "committees.html").read_text(encoding="utf-8")
    assert t.count("<!-- statstud -->") == 1 and t.count("<!-- /statstud -->") == 1, (
        "the statutory and study committees' slot is missing or doubled")
    sec = t[t.index("<!-- statstud -->"):t.index("<!-- /statstud -->")]
    assert sec.startswith('<!-- statstud --><details class="sfold ssfold" id="statstud"><summary>') \
        and "<span class=\"sflab\">Statutory and Study Committees</span> <span class=\"w4n\">3</span>" in sec, (
        "the section is not one shut fold that says how many: " + sec[:200])
    # The former committees' heading, not its words: the header's row names
    # them too, above everything (chrome.ROWS).
    former = '<h2 id="archived">Former committees'
    assert t.index('<div class="ctwo">') < t.index("<!-- statstud -->") and (
        former not in t or t.index("<!-- statstud -->") < t.index(former)), (
        "the fold is not under the chambers' columns, above the former committees")
    groups = re.findall(r'<section class="ssgrp" data-class="(\w+)">', sec)
    assert groups == ["statutory", "study"], f"the classes are {groups}, not statutory then study"
    cards = re.findall(r'<a class="ccard sscard" href="([^"]+)"', sec)
    assert cards == ["committee/ss69", "committee/ss1451", "committee/ss1740"], (
        f"the cards, by class and then name, lead to {cards}")
    assert _clean_links(C.chip("Commission", "k-study")) in sec and C.chip("Board", "k-study") in sec, (
        "a card does not carry its kind, from its name, as the chip")
    assert '<div class="ssfind" hidden>' in sec and 'id="ssq"' in sec and "wrap.hidden=false" in sec, (
        "the find box is not hidden until its script shows it")
    return "ok", "one shut fold after the chambers, statutory then study, a card each with its kind; a find box the script shows"


@check("build", "a statutory or study committee's page: every sitting legislator's seat is the site's "
       "one chip with its role, every other seat as the record describes it, and the law, the "
       "report and the meetings as the record has them", needs=("build_study_committees",))
def _study_committee_page(SC):
    """The plan's page (private/STUDY_COMMITTEES_PLAN.md, approved 17 October
    2026), on the fixture's commission: a seat of type 0 or 1 is a
    legislator's, found on the roster by the member's own number and drawn
    with components.pchip, its role beside it; the seat of a lapsed
    appointment is not drawn; a seat whose number is on no roster, and every
    public member's, is the statute's own description of it, alike seats one
    line, never a name. What It Does links the bill and the statute that made
    it, Report says what is due, Meetings are newest first with the record's
    marks, each a Calendar link from the Calendar's first week, the older
    ones folded."""
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    import components as C
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    t = (site / "committee" / "ss1451.html").read_text(encoding="utf-8")
    legs = {str(m["id"]): m for m in json.loads((site / "legislators.json").read_text(encoding="utf-8"))}
    members = t[t.index('id="members"'):t.index('id="meetings"')]
    seats = [ln.split("|") for ln in (shared / "db" / "StatStudMembers.psv").read_text(
        encoding="utf-8").splitlines()]
    sitting = {s[1] for s in seats if s[0] == "1451" and s[5] == "True" and s[3] in ("0", "1")
               and s[1] in legs}
    n = members.count('class="mchip ')
    assert n == len(sitting) == 2, (
        f"{n} chips for {len(sitting)} sitting legislators' seats: every one is a chip, once")
    for no in sitting:
        role = "Chair" if no == "377204" else "Member"
        want = _clean_links(C.pchip(dict(legs[no], role=role)))
        assert want in members, f"member {no}'s seat is not the site's chip, with its role: want {want}"
    assert "A hydrogeologist, appointed by the governor." in members and "(c)" not in members, (
        "a seat whose member is on no roster is not described as the record describes it")
    assert members.count("Fifteen members of the public, appointed by the governor.") == 1 \
        and "2 seats on record" in members and "Reappointed" not in members, (
        "two alike public members' seats are not one line of the record's own words")
    does = t[t.index('id="does"'):t.index('id="members"')]
    assert 'href="bill/2026/sb434"' in does and 'href="/laws/91-a#s4"' in does \
        and "Minutes and Records Available for Public Inspection" in does \
        and "chapter 152:2 of the Laws of 2026" in does and 'href="bill/2026/hb1442"' in does, (
        "What It Does does not link the bill and the statute that made it, with the session "
        "law's chapter as the record has it: " + re.sub(r"<[^>]+>", " ", does)[:300])
    assert "Report" in t and "November 1, 2026" in t and "No report is on file" in t, (
        "the report's due date, or that none is on file, is not said")
    meets = t[t.index('id="meetings"'):]
    ids = re.findall(r'<details class="cmeet" id="([^"]+)"', meets)
    assert ids == ["day-2026-03-12", "day-2026-03-10", "day-1993-01-11"], (
        f"the meetings are not newest first, each at its day's address: {ids}")
    first = meets[meets.index('id="day-2026-03-12"'):meets.index('id="day-2026-03-10"')]
    # The room in the Calendar's words (plain_action.place, 26 October 2026).
    assert C.chip("Cancelled", "calkind") in first and "Legislative Office Building 102" in first, (
        "the cancelled meeting does not carry the record's mark and its room in words")
    assert 'href="calendar?week=2026-W11&amp;day=2026-03-10&amp;committee=State+Commission+on+Aging"' \
        in meets, "a meeting since the Calendar's first week does not lead to it there"
    fold = meets[meets.index('<details class="sfold ssold"'):]
    assert 'id="day-1993-01-11"' in fold and "Earlier meetings, 1993" in fold, (
        "the meetings before the last few years are not folded away")
    # The board the list marks non-legislative: its name without the mark,
    # said in words, and given no parent in the General Court.
    b = (site / "committee" / "ss69.html").read_text(encoding="utf-8")
    assert "NON-LEGISLATIVE" not in b.upper().replace("NON-LEGISLATIVE:", "") \
        and "marks it non-legislative" in b and '"parentOrganization"' not in b, (
        "the board the list marks non-legislative keeps the mark in its name, is not said to be "
        "non-legislative, or is given the General Court as its parent")
    assert '"parentOrganization"' in t, "the commission's structured data names no parent"
    return "ok", ("two sitting legislators' seats, two chips with their roles; the lapsed seat "
                  "left; the unrostered and public seats described, alike ones as one; the bill, "
                  "law and statute linked; the meetings newest first, marked, the oldest folded")


def _clean_links(html):
    """A component as a built page carries it: shell.clean_links's addresses."""
    import shell
    return shell.clean_links(html)


@check("build", "a study or statutory committee's recorded meetings are its Videos tab, drawn by the "
       "one Videos view, and a recording plays on its own committee's meeting of its own day and "
       "no other", needs=("build_study_committees",))
def _study_committee_videos(SC):
    """The owner, 26 October 2026: "Same goes for session days, or study
    committees, commissions, etc that are livestreamed from those channels."
    build_study_committees.videos_html writes the committee's recorded
    meetings as rows in the page, the body of its Videos tab (tabs_html, the
    owner's tabs of 29 October 2026, which _study_committee_tabs holds), and
    app.js's videoView draws them; without script the tab's pane says each
    recorded meeting under Meetings has its player. And ONE RECORDING, ONE
    MEETING: the Calendar's rows were keyed by MeetingID alone, which
    repeats, so the Nuclear Decommissioning Financing Committee's meeting of
    14 June 2002 played a task force's recording of 23 October 2026 and
    stood in its room. The fixture's study committee has a meeting of 2002
    under the commission's MeetingID: it takes nothing, and no study page
    puts a recording on a meeting before the channels began."""
    import about_figures as AF
    c = {"cid": "85", "meetings": [
        {"MeetingID": "7001", "MeetingDate": "06/14/2002 10:00:00", "MeetingLocation": "RM100,LOB",
         "webtext": ""},
        {"MeetingID": "7002", "MeetingDate": "03/10/2026 10:00:00",
         "MeetingLocation": "LOB Room 101  Regular Meeting", "webtext": ""}]}
    recent = {("1741", "7001"): {"date": "2002-06-14", "venue": "State House 100", "video_id": "wL_4WYC1M6g"},
              ("85", "7002"): {"date": "2026-03-11", "venue": "Elsewhere", "video_id": "otherDay001"}}
    got = {m["date"]: (m["video"], m["venue"]) for m in SC.meetings_of(c, recent, None)}
    assert got["2002-06-14"][0] == "" and "State House 100" not in got["2002-06-14"][1] \
        and got["2026-03-10"][0] == "" and got["2026-03-10"][1] != "Elsewhere", (
            f"a meeting takes another committee's, or another day's, room or recording: {got}")
    recent[("85", "7002")]["date"] = "2026-03-10"
    got = {m["date"]: m["video"] for m in SC.meetings_of(c, recent, None)}
    assert got == {"2002-06-14": "", "2026-03-10": "otherDay001"}, (
        f"a meeting does not take its own committee's recording of its own day: {got}")
    # A STREAM NOT YET RUN -- no start, no length in the index -- is not listed
    # until it has run; taken out, nothing failed (the review of 29 October
    # 2026). And a recording the index does not have yet is listed.
    ms = [{"date": "2026-11-30", "time": "10:00", "venue": "LOB 101", "type": "Regular meeting",
           "id": "day-2026-11-30", "video": "soonStream1"},
          {"date": "2026-10-20", "time": "10:00", "venue": "LOB 101", "type": "Regular meeting",
           "id": "day-2026-10-20", "video": "ranStream01"},
          {"date": "2026-10-13", "time": "10:00", "venue": "LOB 101", "type": "Regular meeting",
           "id": "day-2026-10-13", "video": "notIndexed1"}]
    facts = {"soonStream1": {"streamed": False}, "ranStream01": {"streamed": True, "began": "10:01", "seconds": 600}}
    sec, n = SC.videos_html({"cid": "85", "name": "Fiscal Committee"}, ms, {"facts": facts})
    listed = [r["id"] for r in json.loads(re.search(r'id="gr-videos">(.*?)</script>', sec, re.S).group(1))["rows"]]
    assert listed == ["ranStream01", "notIndexed1"] and n == 2, (
        f"the Videos tab lists {listed} ({n}): a stream that has not run is listed, or one it has is not")
    # THE COMMITTEE IN A SENTENCE: "Play the recording of the Fiscal Committee",
    # its own article kept small, and a name that names no body bare --
    # "the Administrative Rules" was what the player said (the review of 29
    # October 2026).
    for name, want in (("Fiscal Committee", "the Fiscal Committee"),
                       ("The Governor's Commission on Addiction, Treatment and Prevention",
                        "the Governor's Commission on Addiction, Treatment and Prevention"),
                       ("Administrative Rules", "Administrative Rules")):
        assert SC.named(name) == want, f"{name!r} is named {SC.named(name)!r} in a sentence, not {want!r}"
    assert '"what":"Administrative Rules"' in SC.videos_html({"cid": "61", "name": "Administrative Rules"},
                                                             ms[1:2], {"facts": facts})[0] and \
        'data-title="Recording of Administrative Rules, Oct 20, 2026"' in SC.player(
            {"cid": "61", "name": "Administrative Rules"}, ms[1]), (
        "the Videos tab or a meeting's player names Administrative Rules as \"the Administrative Rules\"")
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "ok", "a recording plays on its own meeting; not here to build the fixture: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    t = (site / "committee" / "ss1451.html").read_text(encoding="utf-8")
    sec = t[t.index('<div class="pane sspane" role="tabpanel" id="videos"'):]
    assert sec.startswith('<div class="pane sspane" role="tabpanel" id="videos" aria-labelledby="sstab-videos" '
                          'tabindex="0"><h2 class="ssph">Videos</h2><div class="vwhere" data-vwview="gr-videos">'
                          '<p class="src">Each recorded meeting under Meetings has its own player.</p></div>'), (
        "the commission's Videos tab is not its pane, with its line for no script: " + sec[:200])
    data = json.loads(re.search(r'<script type="application/json" id="gr-videos">(.*?)</script>', sec,
                                re.S).group(1))
    want_row = {"id": "agingVid001", "date": "2026-03-10", "time": "10:00",
                "venue": "Legislative Office Building 101", "type": "Regular meeting",
                "anchor": "day-2026-03-10",
                "calendar": "calendar?week=2026-W11&day=2026-03-10&committee=State+Commission+on+Aging",
                "began": "10:02", "seconds": 3720}
    assert data == {"kind": "study", "who": "State Commission on Aging", "what": "the State Commission on Aging",
                    "key": "1451", "path": "/committee/ss1451", "rows": [want_row]}, f"the section's rows read {data}"
    early, stray = [], []
    for f in sorted((site / "committee").glob("ss*.html")):
        page = f.read_text(encoding="utf-8")
        for day, body in re.findall(r'<details class="cmeet" id="day-([0-9-]{10})[^"]*"[^>]*>(.*?)</details>',
                                    page, re.S):
            if "data-embed=" in body and day < AF.STREAM_START:
                early.append(f"{f.stem} {day}")
        if f.stem != "ss1451" and 'id="videos"' in page:
            stray.append(f.stem)
    assert not early, f"a study meeting before the channels began plays a recording: {early}"
    assert not stray, f"a committee with no recorded meeting has a Videos tab: {stray}"
    drawn = _app_js('(location.pathname="/committee/ss1451/videos", scope.videoView(scope.VW_STATIC.study('
                    + json.dumps(data) + ")))", names=("videoView", "VW_STATIC"))
    if drawn is None:
        return "ok", "the commission's Videos tab is written; node is not here to draw it"
    import html as _html
    flat = _html.unescape(re.sub(r"<[^>]+>", "", drawn))
    assert "<iframe" not in drawn and 'data-embed="agingVid001|0|v20260310_agingVid001"' in drawn, (
        "the tab's player is not a still of its recording")
    assert "State Commission on Aging, ·\u00a0Mar 10, 2026, ·\u00a010:02 AM, ·\u00a01 h 2 min, ·\u00a0On YouTube" in flat \
        and "1 recording, newest first" in flat, f"the tab draws {flat[:300]!r}"
    assert _vw_loose_dots(drawn) == 0 and drawn.count(_VW_DOT_HEAD) >= 5, (
        "a dot in the study committee's Videos tab can end a line: it goes at the head of "
        "the part after it")
    # "This meeting" is the meeting on the Meetings tab, at its own address --
    # the page's, which lands on its Meetings -- turned to in place (app.js,
    # ssTabs).
    assert '<a href="/committee/ss1451#day-2026-03-10" data-ssgo>This meeting</a>' in drawn and \
        '<a href="calendar?week=2026-W11&amp;day=2026-03-10&amp;committee=State+Commission+on+Aging">' \
        'This meeting on the Calendar</a>' in drawn and \
        'href="/committee/ss1451/videos#v-agingVid001"' in drawn, (
            "the tab does not lead to its meeting on the Meetings tab and on the Calendar, or its row to itself")
    return "ok", ("a meeting takes only its own committee's recording of its own day; the "
                  "commission's Videos tab drawn as a still and its playlist; no study meeting before "
                  "May 2020 plays one")


# A study committee's page as app.js meets it: its strip of three tabs, each
# pane by its id, a meeting's fold inside the earlier meetings' fold, and a
# frame playing in the Videos pane; every listener app.js registers kept to
# be fired. As the build writes it, the page lands on its Meetings, which has
# no slug, Bills and Videos at theirs; the strip stays at the top of the
# window, 44.5px high. app.js is loaded over it at /committee/ss1451/sessions,
# as a page that carries its own record (GR_STATIC).
_SS_TABS_HARNESS = _HEARD_PRELUDE + r"""
const attrs = (o, a) => Object.assign(o, {a: Object.assign({}, a),
  getAttribute(k) { return k in this.a ? this.a[k] : null; }, setAttribute(k, v) { this.a[k] = String(v); },
  hasAttribute(k) { return k in this.a; }, removeAttribute(k) { delete this.a[k]; }});
const sent = [];
const frame = {contentWindow: {postMessage: (m) => sent.push(JSON.parse(m).func)}, addEventListener() {}};
const panes = {};
for (const id of ["bills", "meetings", "videos"])
  panes[id] = attrs({id, querySelectorAll: (q) => q === "iframe" && id === "videos" ? [frame] : []},
                    id === "meetings" ? {"data-on": ""} : {});
const strip = {dataset: {base: "/committee/ss1451"}, pos: "sticky", getBoundingClientRect: () => ({height: 44.5})};
globalThis.getComputedStyle = (el) => ({position: (el && el.pos) || "static", getPropertyValue: () => ""});
const rootVars = {};
document.documentElement.style.setProperty = (k, v) => { rootVars[k] = v; };
const tabs = [["bills", "bills"], ["meetings", ""], ["videos", "videos"]].map(([id, slug], i) =>
  attrs({id: "sstab-" + id, dataset: {sstab: slug}, closest: (q) => q === ".sstabs" ? strip : null},
        {"aria-controls": id, "aria-selected": String(i === 1)}));
strip.querySelectorAll = (q) => q === "[data-sstab]" ? tabs : [];
const earlier = {tagName: "DETAILS", open: false, parentElement: null};
const day = {tagName: "DETAILS", open: false, parentElement: earlier, seen: 0, scrollIntoView() { this.seen += 1; }};
const stubQ = document.querySelector, stubId = document.getElementById;
document.querySelector = (q) => q === ".sstabs" ? strip : stubQ(q);
document.getElementById = (id) => panes[id] || (id === "day-1993-01-11" ? day : /^day-/.test(id) ? null : stubId(id));
const state = () => ({tabs: tabs.map((t) => t.a["aria-selected"]).join(""),
  on: Object.keys(panes).filter((k) => panes[k].hasAttribute("data-on")), at: location.pathname + location.hash,
  wrote: wrote.splice(0)});
go("/committee/ss1451/sessions"); window.GR_STATIC = true;
load("ssLand, addressed");
const out = {onLoad: state()};
try {
  place("/committee/ss1451/videos"); s.ssLand(); out.byPath = state();
  sent.length = 0;
  click((q) => q === "[data-sstab]" ? tabs[0] : null); out.clicked = state(); out.paused = sent.splice(0);
  place("/committee/ss1451#day-1993-01-11"); s.ssLand();
  out.byDay = Object.assign(state(), {open: [earlier.open, day.open], seen: day.seen, held: rootVars["--ssheld"]});
  place("/committee/ss1451#videos"); (heard.window.hashchange || []).forEach((f) => f({})); out.byHash = state();
  earlier.open = day.open = false; day.seen = 0;
  const go = click((q) => q === "a[data-ssgo]" ? {getAttribute: (k) => k === "href" ? "/committee/ss1451#day-1993-01-11" : null} : null);
  out.go = Object.assign(state(), {prevented: go.prevented, open: day.open, seen: day.seen});
  place("/committee/ss1451/sessions"); s.ssLand(); out.bySlug = state();
  place("/committee/ss1451/bills"); s.ssLand(); out.byBills = state();
  place("/committee/ss1451"); s.ssLand(); out.bare = state();
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").slice(0, 300); }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("build", "a study or statutory committee has a standing committee's tabs -- Bills, Meetings, "
       "Videos, each counted and at its own address -- under what it does, its report and its members; "
       "no tab where it would be empty", needs=("build_study_committees", "build_pages"))
def _study_committee_tabs(SC, BP):
    """The owner, 29 October 2026, reversing the full-width Videos section
    (Q5): "study committees, commissions and boards get the same tab format as
    standing committees: Bills | Meetings | Videos", with room for tabs to
    come, such as Reports. build_study_committees.tabs_html writes a
    standing committee's strip in its own classes (.rhead ~ .tabs: on the
    head's foot rule, pinned as a pane scrolls) and a pane each, after the
    W4 sections that stay above it -- What It Does, Report, Members -- as a
    standing committee keeps its members and its rule above its tabs. Bills
    are the bills that made it and changed it, which is what the record
    names for a body nothing is referred to (bills_of); a body whose record
    names none has no Bills tab, and one with no recorded meeting no Videos
    tab. Without JavaScript every pane is on the page under its heading;
    with it the first shows from the first paint, and app.js (ssLand) turns
    to the tab the address names -- /sessions, /videos, a meeting's #day-,
    a recording's #v-, a pane's old #id -- and to the one pressed, pausing a
    recording in the pane it leaves.

    THE PAGE LANDS ON ITS MEETINGS (the review of 29 October 2026, 4):
    opened on Bills, the State Commission on Aging showed HB 621 of 2019 and
    no more, and the Fiscal Committee four housekeeping bills, its 165
    meetings a click away. The strip keeps the owner's order; the page's own
    address is its Meetings (a body that has never met, the first tab with
    something in it), Bills at /bills, which the committee rewrite serves.
    A MEETING THE ADDRESS NAMES LANDS BELOW THE STRIP (2), which stays at the
    top: its height written as --ssheld, which app.css keeps above a meeting.
    AND THE BILLS ARE BY YEAR, NONE SAID TO COME "SINCE" (5): the record lists
    bills amending a body that are older than the bill that set it up --
    HB 746 of 1975 for a council set up by HB 317 of 1995 -- and the tab had
    them as having changed it since; such a bill says it is older."""
    root = Path(tempfile.mkdtemp())
    try:
        (root / "bill" / "2026").mkdir(parents=True)
        (root / "bill" / "2026" / "sb434.html").write_text("", encoding="utf-8")
        ctx = {"bills": {("SB434", "2026"): 2026, ("HB1442", "2026"): 2026}, "site": root,
               "titles": {("SB434", "2026"): "establishing a commission on aging.",
                          ("HB1442", "2026"): "relative to insurance coverage."}, "first_year": "1989"}
        aging = {"cid": "1451", "name": "State Commission on Aging", "bill": "SB434", "year": "2026",
                 "amended": "HB1442(2026), SB434(2026)"}
        rows = SC.bills_of(aging, ctx)
        fiscal = SC.bills_of({"cid": "57", "name": "Fiscal Committee", "bill": "", "year": "1965",
                              "amended": "HB10(1995) HB2(2009)"}, ctx)
        none = SC.bills_of({"cid": "69", "name": "A Board", "bill": "", "year": "1967", "amended": ""}, ctx)
        # Administrative Rules, set up by HB 366 of 1983: before the site's bills.
        early = SC.bills_of({"cid": "61", "name": "Administrative Rules", "bill": "HB366", "year": "1983",
                             "amended": ""}, ctx)
        # The record's amending bills older than the body: the Advisory Council
        # on Unemployment Compensation, set up by HB 317 of 1995, lists HB 746 of
        # 1975, HB 110 of 1981 and HB 317 itself; the New England Board of Higher
        # Education Compact, set up in 1989 by no bill named, HB 576 of 1981.
        council = SC.bills_of({"cid": "90", "name": "Advisory Council", "bill": "HB317", "year": "1995",
                               "amended": "HB1142(2002), HB746(1975), HB110(1981), HB317(1995)"}, ctx)
        board = SC.bills_of({"cid": "75", "name": "A Compact", "bill": "", "year": "1989",
                             "amended": "SB51(2003) HB576(1981)"}, ctx)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert [(r["n"], r["year"], r["href"], r["line"]) for r in rows] == [
        ("SB 434", "2026", "bill/2026/sb434.html", "Set it up"), ("HB 1442", "2026", "", "Amended it")] and \
        none == [], f"a study committee's bills are not the one that set it up and those that changed it, once: {rows}"
    assert early == [{"n": "HB 366", "year": "1983", "href": "", "line": "Set it up",
                      "title": "Before 1989, when this site’s record of bills begins."}], (
        f"a bill from before the site's record stands blank, or says something else: {early}")
    assert [(r["n"], r["line"]) for r in council] == [
        ("HB 746", "Older than the bill that set it up"), ("HB 110", "Older than the bill that set it up"),
        ("HB 317", "Set it up"), ("HB 1142", "Amended it")] and \
        [(r["n"], r["line"]) for r in board] == [("HB 576", "Older than 1989, when it was set up"),
                                                 ("SB 51", "Amended it")], (
            "a body's bills are not by year, or one the record lists as amending it that is older than the "
            f"body is said to have changed it: {[(r['n'], r['line']) for r in council + board]}")
    said = SC.bills_html(aging, rows)
    assert said.startswith('<p class="src">The bill that set it up, and the bill the General Court&rsquo;s record '
                           "lists as amending it, by year.</p>") and \
        '<a class="brnum" href="bill/2026/sb434.html" translate="no">SB 434<span class="byr">(2026)</span></a>' \
        in said and '<span class="brnum">HB 1442<span class="byr">(2026)</span></span>' in said and \
        "relative to insurance coverage." in said, "the Bills tab does not say what its bills are, each as a row: " + said[:300]
    leads = [SC.bills_html({"year": "1965"}, fiscal), SC.bills_html(aging, rows[:1]), SC.bills_html({"year": "1995"}, council)]
    assert leads[0].startswith('<p class="src">The 2 bills the General Court&rsquo;s record lists as amending it, by '
                               "year. It was set up in 1965.</p>") and \
        leads[1].startswith('<p class="src">The bill that set it up, as the General Court&rsquo;s record names it.</p>') \
        and not any("since" in x[:x.index("</p>")] for x in leads), (
            "a committee set up by no bill named does not say so, or the Bills tab says its bills came \"since\" "
            "the body: " + " | ".join(x[:x.index("</p>")] for x in leads))
    page = SC.tabs_html(aging, {"meetings": (3, "MEETINGS"), "bills": (2, "BILLS"), "videos": (1, "VIDEOS")})
    strip = re.search(r'<div class="tabs sstabs" role="tablist" data-base="/committee/ss1451">(.*?)</div>', page).group(1)
    tabs = re.findall(r'<button type="button" class="tab" role="tab" id="sstab-(\w+)" aria-controls="\1" '
                      r'data-sstab="(\w*)" aria-selected="(true|false)">(\w+)(.*?)</button>', strip)
    assert [t[:4] for t in tabs] == [("bills", "bills", "false", "Bills"), ("meetings", "", "true", "Meetings"),
                                     ("videos", "videos", "false", "Videos")], (
        f"the strip is not Bills | Meetings | Videos, each at its address, the page landing on its Meetings: {tabs}")
    panes = re.findall(r'<div class="pane sspane" role="tabpanel" id="(\w+)" aria-labelledby="sstab-\1" '
                       r'tabindex="0"( data-on)?><h2 class="ssph">(\w+)</h2>(\w+)</div>', page)
    assert panes == [("bills", "", "Bills", "BILLS"), ("meetings", " data-on", "Meetings", "MEETINGS"),
                     ("videos", "", "Videos", "VIDEOS")], f"the panes are not each its tab's, Meetings shown: {panes}"
    # A body that has never met lands on the first tab with something in it.
    unmet = SC.tabs_html(aging, {"meetings": (0, "M"), "bills": (2, "B")})
    assert re.findall(r'id="sstab-(\w+)" aria-controls="\w+" data-sstab="(\w*)" aria-selected="(\w+)"', unmet) == [
        ("bills", "", "true"), ("meetings", "sessions", "false")] and \
        re.findall(r'id="(\w+)" aria-labelledby="[^"]*" tabindex="0" data-on', unmet) == ["bills"], (
            "a body that has never met lands on an empty Meetings, or its Bills is not at the page's own address")
    assert re.findall(r'id="sstab-(\w+)"', SC.tabs_html(aging, {"meetings": (0, "M")})) == ["meetings"] and \
        "class=\"tn\"" not in SC.tabs_html(aging, {"meetings": (0, "M")}), "a tab with nothing in it is drawn"
    slugs = {slug for _p, _w, slug in SC.TABS if slug}
    assert slugs <= set(BP.COMMITTEE_TAB_SLUGS), (
        f"a study committee's tab is at an address the committee rewrite does not serve: {slugs - set(BP.COMMITTEE_TAB_SLUGS)}")
    css = _source("src/pages/app.css")
    for rule, why in (("\nhtml:not(.js) .sstabs{display:none}", "without JavaScript the strip is shown"),
                      ("\nhtml.js .sspane:not([data-on]){display:none}", "with JavaScript every pane is shown"),
                      (".rhead ~ #ppane,.rhead ~ .sspane{background:var(--surface)", "a pane is not the record's sheet"),
                      (".rhead ~ .tabs{position:sticky;top:0;", "the strip is not pinned as a standing committee's is"),
                      ("\n.sspane .cmeet{scroll-margin-top:calc(var(--ssheld,3.25rem) + var(--sp-6))}",
                       "a meeting the address names lands under the strip that stays at the top")):
        assert rule in css, f"app.css: {why}"
    tn = _app_js("scope.tabN((1234).toLocaleString())", names=("tabN",))
    assert tn is None or tn == SC.tab_n(1234), f"a study committee's count reads {SC.tab_n(1234)!r}, a standing one's {tn!r}"
    # /bills, which a study committee's Bills tab is at, is a committee's tab
    # address app.js reads as one -- Bills is tab 0, which a test of truth had
    # passed over, and /committee/H34/bills/sessions would have been written
    # from it -- while a standing committee's Bills is still written as its
    # page's own address.
    slugs = _app_js('(location.pathname="/committee/H34/bills", [scope.tabFromPath(), scope.isTabSlug("constructor"), '
                    'scope.slugOf(scope.COMMITTEE_TABS,0), scope.slugOf(scope.COMMITTEE_TABS,1), '
                    'scope.slugOf(scope.BILL_TABS,"6")])', names=("tabFromPath", "isTabSlug", "slugOf", "COMMITTEE_TABS",
                                                                "BILL_TABS"))
    assert slugs is None or slugs == ["bills", False, "", "sessions", "text"], (
        f"/committee/H34/bills is not read as the Bills tab's address, or a standing committee's Bills is "
        f"written with a slug: {slugs}")
    got = _node_app(_SS_TABS_HARNESS)
    if got is not None:
        assert "threw" not in got, "the study committee's tabs could not be driven: " + got["threw"]
        assert (got["onLoad"]["tabs"], got["onLoad"]["on"]) == ("falsetruefalse", ["meetings"]), (
            f"app.js, loaded at /committee/ss1451/sessions, does not open the page on its Meetings tab: {got['onLoad']}")
        assert got["byPath"] == {"tabs": "falsefalsetrue", "on": ["videos"], "at": "/committee/ss1451/videos", "wrote": []}, (
            f"/committee/ss1451/videos does not open on its Videos tab: {got['byPath']}")
        assert got["clicked"] == {"tabs": "truefalsefalse", "on": ["bills"], "at": "/committee/ss1451/bills", "wrote": [
            "replace /committee/ss1451/bills"]} and got["paused"] == ["pauseVideo"], (
            f"Bills pressed is not shown at its address, or the recording left playing: {got['clicked']}, {got['paused']}")
        assert got["byDay"] == {"tabs": "falsetruefalse", "on": ["meetings"], "at": "/committee/ss1451#day-1993-01-11",
                                "wrote": ["replace /committee/ss1451#day-1993-01-11"], "open": [True, True], "seen": 1,
                                "held": "45px"}, (
            f"a meeting the address names is not opened on the Meetings tab, named there, below the strip that "
            f"stays at the top: {got['byDay']}")
        assert got["byHash"]["on"] == ["videos"] and got["bySlug"]["on"] == ["meetings"] and \
            got["byBills"]["on"] == ["bills"] and (got["bare"]["on"], got["bare"]["tabs"]) == (["meetings"], "falsetruefalse"), (
            f"the old #videos or /sessions, /bills or the page's own address does not open its tab: {got['byHash']}, "
            f"{got['bySlug']}, {got['byBills']}, {got['bare']}")
        assert got["go"]["prevented"] == 1 and got["go"]["on"] == ["meetings"] and got["go"]["open"] and \
            got["go"]["seen"] == 1 and got["go"]["at"] == "/committee/ss1451#day-1993-01-11", (
                f"the Videos tab's \"This meeting\" does not turn to the meeting in place: {got['go']}")
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "ok", "the tabs are written and turned to; not here to build the fixture: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    want = {"ss1451": [("bills", 2), ("meetings", 3), ("videos", 1)], "ss1740": [("bills", 1), ("meetings", 1)],
            "ss69": [("meetings", 0)]}
    for stem, tabs_want in want.items():
        t = (site / "committee" / f"{stem}.html").read_text(encoding="utf-8")
        m = re.search(r'</header><div class="w4s ssbody">(.*?)</div><div class="tabs sstabs" role="tablist" '
                      r'data-base="/committee/' + stem + '">', t, re.S)
        assert m, f"{stem}: the strip does not follow the head and its sections, where a standing committee's is"
        above = re.findall(r'<section class="w4" id="([a-z]+)">', m.group(1))
        assert above[0] == "does" and above[-1] == "members", f"{stem}: above the tabs are {above}"
        drawn = [(pid, int(n or 0)) for pid, n in re.findall(
            r'id="sstab-(\w+)"[^>]*>\w+(?:<span class="tn"><span class="tnp"> \(</span>([\d,]+)<span)?', t)]
        assert drawn == tabs_want, f"{stem}'s tabs are {drawn}, not {tabs_want}"
        # Each lands on its Meetings, at the page's own address, the pane shown from the first paint.
        assert re.findall(r'id="sstab-(\w+)" aria-controls="\w+" data-sstab="" aria-selected="true"', t) == ["meetings"] \
            and re.findall(r'<div class="pane sspane" role="tabpanel" id="(\w+)"[^>]* data-on>', t) == ["meetings"], (
                f"{stem} does not land on its Meetings")
    bills = (site / "committee" / "ss1451.html").read_text(encoding="utf-8")
    # What It Does says what the record says of them, by year, and not
    # "Changed since by", which it had said of a council's bills of 1975 and
    # 1981 set up in 1995 (5).
    does = bills[bills.index('<section class="w4" id="does">'):]
    does = does[:does.index("</section>")]
    assert "The General Court&rsquo;s record lists it as amended by " in does and "since" not in does, (
        "What It Does does not say what the record lists as amending the body, or says they came since: "
        + re.sub(r"<[^>]+>", "", does)[:300])
    bills = bills[bills.index('id="bills"'):bills.index('id="meetings"')]
    assert 'href="bill/2026/sb434"' in bills and 'href="bill/2026/hb1442"' in bills and \
        bills.count('<span class="brline">Set it up</span>') == 1 and \
        bills.count('<span class="brline">Amended it</span>') == 1, (
            "the commission's Bills tab is not the bill that set it up and the one that changed it")
    return "ok", ("Bills | Meetings | Videos under the sections, each counted and at its address, a "
                  "standing committee's strip and sheet, landing on Meetings; the bills that made and changed "
                  "it, by year, none said to come since; no tab where it would be empty; the address's tab, a "
                  "meeting below the strip or a recording turned to, a recording paused in the pane left")


@check("build", "the study committees' record is read as it was written: a lost break parted only "
       "where the record says so, an old room read as its room, a kind from its name, and the "
       "statute and the session law put back where the record swapped them",
       needs=("build_study_committees", "plain_action"))
def _study_committee_reading(SC, PA):
    """The database copy lost the line breaks inside its text, as it did in a
    venue: "chairpersons of thehouse and senate committees". A word is parted
    only where the vocabulary says so, never a word the statutes' headings
    use ("record" is not "re cord"); a small letter met by a capital is a
    break, but not McAuliffe's. A room written "RM205,LOB -" is LOB Room 205.
    "Business Finance Authority Board of Directors" is a board."""
    w = SC.Words({"record", "indirect"})
    w.counts.update({"the": 900, "house": 800, "thehouse": 40, "of": 900, "each": 300,
                     "ofeach": 12, "re": 50, "cord": 50, "in": 900, "direct": 60, "for": 900,
                     "th": 30, "forth": 2, "proposed": 368, "legislation": 434,
                     "proposedlegislation": 37, "representatives": 300, "ofrepresentatives": 8,
                     "thehouseofrepresentatives": 1})
    got = {x: SC.parted(x, w) for x in ("thehouse", "ofeach", "record", "indirect", "forth",
                                        "onNovember", "McAuliffe", "proposedlegislation",
                                        "thehouseofrepresentatives", "eNorth")}
    assert got == {"thehouse": "the house", "ofeach": "of each", "record": None, "indirect": None,
                   "forth": None, "onNovember": "on November", "McAuliffe": None,
                   "proposedlegislation": "proposed legislation",
                   "thehouseofrepresentatives": "the house of representatives", "eNorth": None}, got
    said = Counter()
    assert SC.prose("report to thehouse,senate and the committee�s chair.The end", w, said) == (
        "report to the house, senate and the committee's chair. The end"), "prose() misreads the copy"
    assert said == Counter({"thehouse": 1}), said
    assert SC.seat_words("(j)  Fifteen members of the public. (Reappointed 12/12/24)", w) == (
        "Fifteen members of the public."), "a seat keeps its paragraph's letter or an appointment's note"
    # The clerk's codes, which plain_action.place then words as every room on the site
    # (the R2 polish batch, 30 October 2026: "State House 105-A", not "State House Room 105-A").
    rooms = {"RM205,LOB -": ("LOB 205", ""),
             "RMs306-308,LOB - Continued Meeting": ("LOB 306-308", "Continued Meeting"),
             "RM105-A, St House -": ("SH 105-A", ""),
             "RM101,LOB   (Org meeting)": ("LOB 101", "Org meeting"),
             "GP Room 230": ("GP Room 230", "")}
    for r, want in rooms.items():
        assert SC.old_room(r) == want, f"{r!r} reads as {SC.old_room(r)}"
    for r, want in (("RM205,LOB -", "Legislative Office Building 205"),
                    ("RMs306-308,LOB - Continued Meeting", "Legislative Office Building 306-308"),
                    ("RM105-A, St House -", "State House 105-A")):
        assert PA.place(SC.old_room(r)[0]) == want, f"{r!r} is said {PA.place(SC.old_room(r)[0])!r}"
    kinds = {"Business Finance Authority Board of Directors": "Board",
             "Advisory Committee on the Human Rights Commission": "Committee",
             "Commission to Study Stable Tokens": "Commission",
             "Subcommittee on Alzheimer's Disease and Other Related Dementia": "Subcommittee",
             "Youth Council Subgroup Within Governor's Workforce Opportunity Council": "Council",
             "Working Group for the Study of Nursing Home Rate Medicaid Methodology": "Working Group",
             "Administrative Rules": "Committee"}
    for n, k in kinds.items():
        assert SC.kind_of(n) == k, f"{n!r} is a {SC.kind_of(n)}, not a {k}"
    assert SC.rsa_of("312", "106-L:17 ") == ("106-L:17", "312") and SC.rsa_of("19-P:1", "0152:2") == (
        "19-P:1", "152:2"), "the statute and the session law are not put back where the record swapped them"
    st = SC.statute("362-H;3", {"362-H:3": "Members"}, {"362-H": ["Hydrogen", "", 1]})
    assert st == {"addr": "362-H:3", "href": "/laws/362-h#s3", "heading": "Members"}, st
    assert SC.statute("9:3-a,IV", {}, {"9": ["Budget", "", 1]})["href"] == "/laws/9", (
        "a section the Laws pages do not hold is not linked to its chapter")
    import build_calendar as BC
    assert BC.committee_name("OPLC OVERSIGHT COMMITTEE") == "OPLC Oversight Committee" and \
        BC.committee_name("ADVISORY COMMITTEE ON THE EDUCATION OF CHILDREN/STUDENTS WITH "
                          "DISABILITIES") == ("Advisory Committee on the Education of "
                                              "Children/Students with Disabilities") and \
        BC.committee_name("NH RETIREMENT SYSTEM BOARD OF TRUSTEES ==NON-LEGISLATIVE==") == (
            "NH Retirement System Board of Trustees") and \
        BC.committee_name("MCAULIFFE-SHEPARD DISCOVERY CENTER BOARD") == (
            "McAuliffe-Shepard Discovery Center Board"), "a committee's name is cased wrong"
    return "ok", ("lost breaks parted only where the record says; McAuliffe, record and indirect "
                  "kept; old rooms read; kinds from names; the swapped statute put back")


@check("data", "on the built site, every active statutory and study committee in db/ has its page, "
       "and every seat of a sitting legislator on it is that member's chip",
       needs=("build_study_committees",))
def _study_committees_built(SC):
    """The fixture's few committees prove the reading; this holds the whole
    copy to it once a build has written the pages: on 17 October 2026, 153
    active committees and the seats of the legislators who sit today on
    them, each a chip linking the member's page."""
    site, db = Path("site"), Path("db")
    if not (site / SC.INDEX).exists() or not (db / "StatStudDetails.psv").exists():
        return "skip", "no built study committees' pages, or no database copy, here"
    comms = SC.read(db)
    legs = {str(m.get("id")): m for m in json.loads((site / "legislators.json").read_text(
        encoding="utf-8"))}
    missing = [c["cid"] for c in comms if not (site / "committee" / f"ss{c['cid']}.html").exists()]
    assert not missing, f"{len(missing)} active committees have no page: ss{', ss'.join(missing[:6])}"
    bad, n = [], 0
    for c in comms:
        t = (site / "committee" / f"ss{c['cid']}.html").read_text(encoding="utf-8")
        for s in c["seats"]:
            m = legs.get(s["memberno"].strip()) if s["MemberType"].strip() in ("0", "1") else None
            if m:
                n += 1
                if f'href="legislator/{m.get("slug")}"' not in t:
                    bad.append(f"ss{c['cid']}: {m.get('display_full')}")
    assert not bad, f"{len(bad)} sitting legislators' seats drawn as no chip: {bad[:5]}"
    return "ok", f"{len(comms)} active committees, each with its page; {n:,} legislators' seats, each a chip"


@check("frontend", "a note that stands for a section of the committees' pages takes the width it has")
def _committee_notes_fill():
    """"'Not on the General Court's list today' and 'No bills or sessions on
    record' sit in the left half" (the person, 7 October 2026, F9). Each is a
    heading and a paragraph over cards that fill the page, and the paragraph
    was held to the 560px measure every source note keeps. Those two on the
    committees index, and a committee page's own "not on the list" and "no
    day on record" notes, are .src.fill, which app.css lets fill the width in
    the region both stylesheets take. Drawn from build_committees' source and
    from app.js in node."""
    import inspect
    import build_committees as BCM
    src = inspect.getsource(BCM)
    for head in ("<h2>No bills or meetings on record</h2>",
                 "<h2 id=\"archived\">Former committees</h2>"):
        at = src.index(head)
        assert "'<p class=\"src fill\">" in src[at:at + 200], (
            f"the note under {head} is held to the measure")
    css = _source("src/pages/app.css")
    assert ".src.fill{max-width:none}" in css and css.index(".src.fill{max-width:none}") \
        > css.index(".src,.lead{max-width:var(--measure)}"), (
            "app.css does not let a .src.fill note take its width, after the measure")
    # A COMMITTEE PAGE BY ITS HEAD, NOT ITS ROSTER (the look of 7 October
    # 2026): a retired committee has no roster, so :has(.croster) left its
    # "Nothing is scheduled" note and its count of bills at 560px.
    for sel in ("main:has(.cmtehead) .cal .note", "main:has(.cmtehead) .pane > .src"):
        assert sel in css, f"app.css has no {sel}: a committee without a roster keeps the measure"
    assert "main:has(.croster)" not in css, (
        "a committee page's widths still hang on its roster, which a retired committee lacks")
    got = _app_js('[scope.renderCommitteeHead({name:"House Old Committee", chamber:"H",'
                  ' archived:{years:"1999-2004"}}),'
                  ' scope.renderCommitteeSessions({sessions:[]})]',
                  names=("renderCommitteeHead", "renderCommitteeSessions"))
    if got is None:
        return "ok", "the index's two notes fill; node is not here to draw a committee page"
    head, sess = got
    assert re.search(r'<header class="rhead [^"]*\bcmtehead\b', head), (
        "a committee page's head does not say it is one, so app.css cannot widen its notes")
    assert re.search(r'<p class="src fill rnote">A former committee\.', head), (
        "a committee page's \"former committee\" note is held to the measure")
    assert '<p class="src fill">No day of this committee is' in sess, (
        "a committee page's \"no day on record\" note is held to the measure")
    return "ok", ("the index's two section notes and a committee page's own fill the width "
                  "they have")


@check("frontend", "the committees list says what it holds, and a former committee says it is "
                   "one plainly", needs=("build_committees",))
def _committee_explanations_plain(BCM):
    """"The explanation at the top of the committee page is confusing to
    readers, either remove it or replace it" (the person, 16 October 2026),
    who took the replacement offered for it and for a former committee's own
    note. The list opens with what it holds, where it set committees against
    bill search ("These answer what a committee did on a day"); a former
    committee's page says it is one, that it no longer meets -- the search's
    own words for it -- and the years of its record, where it explained what
    the records cannot say. Drawn from build_committees' source and from
    app.js in node."""
    import inspect
    src = inspect.getsource(BCM)
    assert ("<p class=\"src\">Every committee of the House and the Senate: who sits " in src
            and "on it, what it does, and the bills and meetings on its record.</p>" in src), (
        "the committees list does not open with what it holds")
    assert "These answer what a committee did on a day.</p>" not in src, (
        "the committees list still sets committees against bill search")
    # Its former committees under the search's own name for them, in a line.
    assert ("<h2 id=\"archived\">Former committees</h2>'\n"
            "                    '<p class=\"src fill\">Committees that no longer meet, with the '\n"
            "                    \"years of their record.</p>\"") in src.replace("\r\n", "\n"), (
        "the committees list does not head its former committees as Former committees, in a line")
    assert "page does not guess which" not in src, (
        "the committees list still explains what the records cannot say about former committees")
    got = _app_js('[scope.renderCommitteeHead({name:"Old", chamber:"H",'
                  ' archived:{years:"1999 to 2004"}}),'
                  ' scope.renderCommitteeHead({name:"Old", chamber:"H", archived:{}}),'
                  ' scope.renderCommitteeHead({name:"Sitting", chamber:"S"})]',
                  names=("renderCommitteeHead",))
    if got is None:
        return "ok", "the list's opening line is plain; node is not here to draw a committee page"
    ran, bare, sitting = got
    assert ('<p class="src fill rnote">A former committee. It no longer meets; its bills and '
            'meetings here run from 1999 to 2004.</p>') in ran, (
        "a former committee's page does not say plainly that it is one, and the years of its record")
    assert '<p class="src fill rnote">A former committee. It no longer meets.</p>' in bare, (
        "a former committee with no years on record draws an empty \"run from\"")
    assert not any("renamed, divided" in h for h in got), (
        "a former committee's page still explains what the records cannot say")
    assert "former committee" not in sitting, "a sitting committee is called a former one"
    return "ok", ("the committees list opens with what it holds, and a former committee says "
                  "it is one, that it no longer meets, and its years")


@check("frontend", "a committee's Sessions tab counts the days it met, and a day still to "
                   "come apart", needs=("build_committees",))
def _committee_days_met(BCM):
    """"56 days this committee met in 2025-2026" over a list whose first day,
    14 October 2026, was still to come (the survey of 7 October 2026, on
    Commerce and Consumer Affairs). The docket books sittings ahead of time;
    the day's own sentence already said "is scheduled to meet", and the
    count, the committees index and the page's description counted it as
    met. build_committees marks a day after the build `ahead` and counts the
    days met; app.js counts the two apart and gives a day to come no "No
    recording of this day is on file"."""
    import inspect
    was = os.environ.get("GRANITE_BUILD_DATE")
    os.environ["GRANITE_BUILD_DATE"] = "2026-10-08"
    try:
        got = [BCM.is_ahead(d) for d in ("2026-10-14", "2026-10-08", "2026-09-30", "")]
    finally:
        if was is None:
            os.environ.pop("GRANITE_BUILD_DATE", None)
        else:
            os.environ["GRANITE_BUILD_DATE"] = was
    assert got == [True, False, False, False], f"days still to come read {got}"
    src = inspect.getsource(BCM)
    assert '**({"ahead": True} if is_ahead(date) else {})' in src, (
        "build_committees does not mark a day still to come")
    # "meetings", the person's word for a committee's days (D19, 8 October 2026).
    assert '"n_sessions": met_days' in src and "{met_days:,} meetings" in src, (
        "the committees index or the page's description counts days still to come as met")
    day = lambda d, ahead, said: {
        "date": d, "term": "2025-2026", "video_id": "", "narrative": said,
        "items": [{"bill": "SB256", "n": "SB 256-FN", "year": 2025, "kind": "work session",
                   "start": None, "state": ""}], **({"ahead": True} if ahead else {})}
    sess = _app_js("scope.renderCommitteeSessions({sessions:" + json.dumps([
        day("2026-10-14", True, "The Committee on Commerce and Consumer Affairs is scheduled "
            "to meet on October 14, 2026 for a work session on SB 256-FN."),
        day("2026-10-07", False, "The Committee on Commerce and Consumer Affairs met on "
            "October 7, 2026 for a work session on SB 256-FN.")]) + "})",
        names=("renderCommitteeSessions",))
    if sess is None:
        return "ok", "build_committees counts the days met; node is not here to draw the tab"
    flat = re.sub(r"\s+", " ", sess)
    # "meetings" (D19), and the order the reader chose (10 October 2026).
    assert re.search(r"<b>1 meeting</b>(?: in [^,]*)?, and 1 still to come, the newest first", flat), (
        "the Sessions tab's count reads: " + flat[:200])
    assert flat.count("No recording of this day is on file.") == 1, (
        "a day still to come is said to have no recording on file")
    return "ok", ("a day after the build is marked and counted apart, on the tab, the index "
                  "and the description")


@check("build", "a committee's Videos tab lists the recordings its bills name and the ones its own "
       "title names on its chamber's channel, newest first, and none still to come, in the older "
       "form, of a session day or on another page", needs=("build_committees", "proceedings"))
def _committee_recordings(BCM, P):
    """The owner, 26 October 2026: "Committee pages should have a videos tab
    that essentially compiles the youtube playlist of that committee's
    meetings". build_committees.committee_recordings gives each page its
    `recordings` (THE VIDEOS TAB'S LIST) out of proceedings.video_facts:
    every recording one of its items names, and every streamed one no row of
    proceedings.csv carries whose parsed title is this committee in the
    channel's chamber -- House Finance's divisions marked -- and nothing
    fuzzy. Read here from rows written as the index writes them, then from
    the fixture's build, where H43 lists VID1 and VID4 by their bills and a
    recording by its title, and not the stream still to come, the title in
    the older form, the House's session or House Finance's division (no
    page). SILENCE IS NOT SUCCESS: an index that reads as nothing beside a
    table naming recordings stops the build."""
    root = Path(tempfile.mkdtemp())
    try:
        _fixture_videos(root)
        facts = P.video_facts(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert set(facts) == {r[0] for rows in FIXTURE_VIDEOS.values() for r in rows}, f"the index reads {sorted(facts)}"
    assert facts["VID1"] == {"date": "2026-02-03", "chamber": "H", "title": "House Commerce (02/03/2026)",
                             "parsed_committee": "Commerce", "began": "09:58", "seconds": 6723,
                             "streamed": True}, f"a recording reads {facts['VID1']}"
    assert (facts["cmteSoonV02"]["streamed"], facts["cmteOldV003"]["parsed_committee"],
            facts["cmteTitleV1"]["began"], P.iso_seconds("PT1H52M3S"), P.iso_seconds("P0D")) == (
        False, "", "", 6723, 0), "a stream to come, a title in the older form or a length read wrong"
    pages = {"H43", "H34"}
    code_of = lambda nm, ch, term: {("H", "Commerce"): "H43", ("H", "Finance"): "H34"}.get((ch, nm))
    days = {"H43": {("2025-2026", "2026-02-03"): [{"video_id": "VID1"}],
                    ("2025-2026", "2026-02-10"): [{"video_id": "VID4"}, {"video_id": "VID4"}]},
            "H99": {("2025-2026", "2026-02-11"): [{"video_id": "VIDX"}]}}
    got, found = BCM.committee_recordings(days, {"VID1", "VID4", "VID2"}, facts, code_of, pages)
    assert [r["id"] for r in got.get("H43", [])] == ["cmteTitleV1", "VID4", "VID1"], (
        f"House Commerce lists {got.get('H43')}")
    assert got["H43"][0] == {"id": "cmteTitleV1", "date": "2026-02-24", "term": "2025-2026",
                             "seconds": 2170}, f"a recording by its title is listed as {got['H43'][0]}"
    assert got["H43"][-1] == {"id": "VID1", "date": "2026-02-03", "term": "2025-2026", "began": "09:58",
                              "seconds": 6723}, f"a recording by its bills is listed as {got['H43'][-1]}"
    assert got.get("H34") == [{"id": "financeDiv2", "date": "2026-02-24", "term": "2025-2026",
                               "began": "13:00", "seconds": 7200, "label": "Division II"}], (
        f"House Finance's division is listed as {got.get('H34')}")
    assert "H99" not in got and dict(found) == {"by_bills": 2, "by_titles": 2, "no_page": 1}, (
        f"a page with no page, or the counts: {dict(found)}")
    # A recording a row carries is not added to a page by its title.
    got2, _ = BCM.committee_recordings({}, {"cmteTitleV1"}, facts, code_of, pages)
    assert "cmteTitleV1" not in [r["id"] for r in got2.get("H43", [])], (
        "a recording proceedings.csv carries is listed again by its title")
    # A division's recording that a bill row places keeps the division its own
    # title names, as House Finance's of 4 May 2026 does (seven bills).
    got3, _ = BCM.committee_recordings({"H34": {("2025-2026", "2026-02-24"): [{"video_id": "financeDiv2"}]}},
                                       {"financeDiv2"}, facts, code_of, pages)
    assert got3.get("H34") == [{"id": "financeDiv2", "date": "2026-02-24", "term": "2025-2026",
                                "began": "13:00", "seconds": 7200, "label": "Division II"}], (
        f"a division's recording placed by its bills is listed as {got3.get('H34')}, without its division")
    # THE OTHER SPELLINGS OF A DIVISION the channel's titles use, "1" and a
    # lower-case "l": each is House Finance's, marked Division I, and not
    # counted as a recording named for no page; and "ll", were it written,
    # Division II.
    odd = dict(facts, **{vid: {"date": "2026-02-25", "chamber": "H", "title": title,
                               "parsed_committee": title, "began": "", "seconds": 600, "streamed": True}
                         for vid, title in (("div1V", "Finance - Division 1"), ("divlV", "Finance Division l"),
                                            ("divllV", "Finance Division ll"))})
    got4, found4 = BCM.committee_recordings({}, set(facts), odd, code_of, pages)
    labels = {r["id"]: r.get("label") for r in got4.get("H34", [])}
    assert labels == {"div1V": "Division I", "divlV": "Division I", "divllV": "Division II"} \
        and not found4["no_page"], (
        f"House Finance's divisions in their other spellings are listed as {labels}, "
        f"{found4['no_page']} named for no page")
    # WHAT ONE ROW OF THE INDEX LACKS, THE OTHER GIVES: a channel file's row
    # with a length and no start, before the night's row with both, kept the
    # first and lost the start (dupV); and of two rows that know as much, the
    # first is kept and takes the day only the second has (tieV), where the
    # recording had been left with no day and off every page.
    root = Path(tempfile.mkdtemp())
    try:
        d = root / "collected" / "videos"
        d.mkdir(parents=True)
        for name, rows in (("videos_house_a.csv", (("dupV", "", ""), ("tieV", "", ""))),
                           ("videos_house_livestreams.csv", (("dupV", "2026-02-25 10:00:00", "2026-02-25"),
                                                             ("tieV", "", "2026-02-26")))):
            with open(d / name, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(FIXTURE_VIDEO_COLS)
                for vid, start, day in rows:
                    w.writerow([vid, "House Commerce", "yes", "Commerce", day, "title",
                                "yes" if start else "no", start, "", "", "PT1H", ""])
        two = P.video_facts(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    dup, tie = two["dupV"], two["tieV"]
    assert (dup["date"], dup["began"], dup["seconds"], dup["streamed"]) == ("2026-02-25", "10:00", 3600, True) \
        and (tie["date"], tie["seconds"]) == ("2026-02-26", 3600), (
            f"recordings two rows of the index name read {dup} and {tie}: the start or the day one of "
            "them has is lost")
    import inspect
    src = inspect.getsource(BCM.main)
    assert "if carried and not facts:" in src and "raise SystemExit(" in src[src.index("if carried and not facts:"):][:200], (
        "build_committees no longer stops on an empty index beside a table naming recordings")
    absent = [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]
    if absent:
        return "ok", "the list is read and made; not here to build the fixture: " + ", ".join(absent)
    shared, _base, _ran, _days = _fixture_site_shared()
    rec = json.loads((shared / "site" / "committee" / "H43.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in rec.get("recordings") or []] == ["cmteTitleV1", "VID4", "VID1"], (
        f"the fixture's House Commerce lists {rec.get('recordings')}")
    # Every page the build wrote: each recording its items name listed, and
    # once; and none from before the channels began.
    import about_figures as AF
    twice, unlisted, early = [], [], []
    for f in sorted((shared / "site" / "committee").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            continue
        ids = [r["id"] for r in d.get("recordings") or []]
        twice += [f"{f.stem} {i}" for i in sorted(set(ids)) if ids.count(i) > 1]
        named = {i.get("video_id") for s in d.get("sessions") or [] for i in s.get("items") or []} - {"", None}
        unlisted += [f"{f.stem} {i}" for i in sorted(named - set(ids))]
        early += [f"{f.stem} {r['id']} {r['date']}" for r in d.get("recordings") or []
                  if r["date"] < AF.STREAM_START]
    assert not twice and not unlisted and not early, (
        f"a page lists a recording twice {twice}, leaves out one its items name {unlisted}, or lists "
        f"one before the channels began {early}")
    return "ok", ("the index read once, a stream to come and a title in the older form left off; "
                  "House Commerce lists 2 recordings by its bills and 1 by its title, newest first; "
                  "a division marked, by its bills or its title; every page's recordings once and none "
                  "before May 2020; an empty index stops the build")


@check("frontend", "the committees index says its counts of bills and sessions are every "
                   "term's, beside today's chair and members", needs=("build_committees",))
def _committee_card_counts(BCM):
    """"Chaired by Ross Berry · 18 members · 1,257 bills · 577 sessions": the
    chair and members are today's and the counts every term's since 1997,
    unlabelled, and Election Law's own page says 144 bills this term (the
    survey of 7 October 2026, C10). The counts now say since when; a card
    the index dates by its years (a committee not on today's list) says it
    there already and is unchanged."""
    span = [f"{y}-{y + 1}" for y in range(1997, 2027, 2)]
    live = BCM.committee_card({"code": "H36", "name": "Election Law", "chair": "Ross Berry",
                               "n_members": 18, "n_bills": 1257, "n_sessions": 577,
                               "span": span})
    assert ("Chaired by Ross Berry &middot; 18 members &middot; 1,257 bills and 577 meetings "
            "since 1997</span>") in live, live
    one = BCM.committee_card({"code": "H63", "name": "Education Funding", "chair": "Rick Ladd",
                              "n_members": 17, "n_bills": 92, "n_sessions": 0,
                              "span": ["2023-2024", "2025-2026"]})
    assert "17 members &middot; 92 bills since 2023</span>" in one, one
    old = BCM.committee_card({"code": "H05", "name": "Education", "chair": "",
                              "n_members": 0, "n_bills": 1530, "n_sessions": 600,
                              "span": [f"{y}-{y + 1}" for y in range(1989, 2025, 2)]},
                             dated=True)
    assert "1,530 bills &middot; 600 meetings</span>" in old and "since" not in old, old
    return "ok", "\"1,257 bills and 577 meetings since 1997\"; a dated card as it was"


@check("build", "the committee pages fetch stops at a refusal, records it, and says when it found "
       "nothing", needs=("fetch_committees",))
def _committees_fetch_stops(FC):
    """fetch_committees.py printed a 403, asked for the next page two seconds
    later, recorded nothing, and exited 0 -- and GitHub's weekly job runs it
    unattended. Now a refusal or the block page ends it with status 2 and a
    record, and finding nothing is status 1, not a quiet 0."""
    import contextlib
    import io
    import urllib.error
    import refusal
    tmp = Path(tempfile.mkdtemp(prefix="gr-cmte-"))
    saved = (FC.get, refusal.MARK, sys.argv)
    saved_env = os.environ.get("GITHUB_ACTIONS")
    os.environ["GITHUB_ACTIONS"] = "true"          # never stood down, whatever this folder holds
    try:
        def drive(answers):
            asked = []

            def get(url):
                asked.append(url)
                a = answers[len(asked) - 1]
                if isinstance(a, BaseException):
                    raise a
                return a
            FC.get = get
            refusal.MARK = tmp / "refused.json"
            refusal.MARK.unlink(missing_ok=True)
            sys.argv = ["fetch_committees.py", "--out", str(tmp / "c.json"), "--delay", "0"]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    code = FC.main()
                except SystemExit as e:
                    code = e.code
            return code, asked, refusal.MARK.exists()

        code, asked, noted = drive([urllib.error.HTTPError("u", 403, "no", {}, None), "<html></html>"])
        assert code == 2 and len(asked) == 1 and noted, (code, asked, noted)
        code, asked, noted = drive(["<h1>Web Page Blocked</h1> Attack ID: 7", "<html></html>"])
        assert code == 2 and len(asked) == 1 and noted, (code, asked, noted)
        code, asked, noted = drive(["<html>nothing here</html>", "<html>nor here</html>"])
        assert code == 1 and len(asked) == 2 and not noted and not (tmp / "c.json").exists(), \
            (code, asked, noted)
    finally:
        FC.get, refusal.MARK, sys.argv = saved
        if saved_env is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = saved_env
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", "a 403 or the block page ends it with a record; nothing found is exit 1"


@check("calendar", "a calendar printed for another term is left out of that year's reports")
def _calendar_own_term():
    """The General Court's 1999 list carries three 1998 calendars as well --
    "1a", "2a" and "4a", whose mastheads read "Vol. 20 Concord N.H.
    Wednesday, January 7, 1998 No. 1" and so on -- and read as 1999's, 155 of
    their reports sat on the 1999-2000 bills sharing their numbers: 2000's HB
    555 carried 1998's report on exempting pensions. The masthead's volume is
    the calendar's year; a December calendar is already the next year's
    volume, which is why the term is compared and not the year; and a
    calendar that prints no masthead is read as before."""
    import fetch_committee_reports as FCR
    head = "House Calendar\n\n        "
    cases = [
        ("Vol. 20 Concord N.H. Wednesday, January 7, 1998 No. 1", 1999, 1998),
        ("Vol. 20 Concord N.H. Wednesday, January 7, 1998 No. 1", 1998, None),
        # December 1998, the new House's first calendar: 1999's volume.
        ("Vol. 21 Concord N.H. Wednesday, December 2, 1998 No. 1", 1999, None),
        # December 1999 filed under 2000: the same term.
        ("Vol. 21 Concord N.H. Friday, December 31, 1999 No. 100", 2000, None),
        ("Vol.37         Concord,N.H.           Friday,December5,2014    No.1", 2015, None),
        ("Vol.37         Concord,N.H.           Friday,December5,2014    No.1", 2017, 2015),
        ("HB 12, citing Vol. 3 of the annotations. OUGHT TO PASS.", 1999, None),
        ("", 1999, None),
    ]
    for text, year, want in cases:
        got = FCR.printed_for_another_term(head + text, year)
        assert got == want, (f"{text[:48]!r} in {year}'s list was read as "
                             f"{got or 'this term'}'s, not {want or 'this term'}'s")
    return "ok", ("1998's calendar in 1999's list is left out; a December calendar, a "
                  "later masthead's spacing and a page with none are read as before")


@check("calendar", "a bill heading at the top of a page still starts a report")
def _formfeed_heading():
    """The page break that made old reports carry the next bill's header.

    pdftotext writes a page break as a form feed, so an entry beginning at the
    top of a page is preceded by that rather than by a newline. BILL_START
    wanted a newline and then spaces or tabs, so it did not see those headings
    and the PREVIOUS committee's report ran on through the whole next entry --
    its number, its title and its recommendation. House Calendar 70 of 2011
    put HB 633's header inside HB 619's report, and 19 bills of that year had
    no report at all because theirs had been swallowed whole.

    405 headings across 1,579 calendars were hidden this way, all but two of
    them in 2003-2012, which is exactly the span a reader described as "old
    committee reports".

    The other half of the check matters as much: the LINE ANCHOR must stay. It
    is there because House Calendar 10 of 2026 contains the phrase "adopting
    SB 2, concentrating budgetary and governance decisions", and without the
    anchor that split a real minority report in half and filed the second half
    under a bill that does not exist -- SB 2 being the name New Hampshire gives
    the ballot-vote form of town meeting.
    """
    import fetch_committee_reports as FCR

    page_break = "\f" "HB 633, preventing prescribing practitioners"
    assert FCR.BILL_START.search("Vote 12-0.\n     6\n" + page_break), (
        "a bill heading preceded by a page break is not read as a heading. "
        "That is the form feed pdftotext writes at every page break, and "
        "without it the previous report swallows the whole entry.")

    mid = ("the committee heard that many towns have trouble adopting "
           "SB 2, concentrating budgetary decisions among a few attendees")
    assert not FCR.BILL_START.search(mid), (
        "a bill number INSIDE a sentence is being read as a heading. The line "
        "anchor is what prevents that; it split a real minority report in "
        "half the last time it was missing.")

    # The ordinary case, and the one that must keep working.
    assert FCR.BILL_START.search("\nHB 1234, relative to something"), (
        "a heading at the start of an ordinary line is no longer read as one")
    return "ok", ("a page break starts a heading, a mid-sentence bill number "
                  "does not")


@check("build", "a committee's meeting says what happened to each bill there, by the day the "
                "docket dates the committee's vote, and its Bills tab dates each report by "
                "the meeting it was voted at", needs=("committee_acts", "narrative"))
def _committee_meeting_outcomes(CA, N):
    """The person, 9 October 2026, item 12: a committee's Meetings tab should
    make clear "what changed on each bill at that meeting, if anything did";
    and v8: an interim study report not recommending future legislation is
    listed as killed, with what the committee voted. committee_acts reads it
    off each bill's docket, by the day the docket dates the vote -- "03/03/2026
    (Vote 17-0; CC)" -- not the day the row was entered, which made the
    prototype's first draft say "no vote" on the day of a vote. Real rows
    (_CARD_DOCKETS), at House Housing (H64), House Finance (H34) and Senate
    Commerce (S37):

      HB 1681, 17 Feb 2026: heard, 7 signed in for and 6 against (the
        sign-in record's own count for that hearing), and voted on 3 March,
        a meeting of the committee: Ought to Pass with Amendment 2026-0998h,
        17-0. Its Senate hearing of 21 April is heard, and the Senate's
        report is dated 7 May, the sitting that took it up, and is placed at
        no meeting.
      HB 1652-FN, 17 Feb 2026, a hearing and an executive session: voted,
        Interim Study, 12-0; and on 1 October its interim study report,
        recommended for future legislation, 8-1.
      HB 65, 1 Oct 2026: the study report dated 30 September, not
        recommended, 5-4: killed, at the meeting of the 1st.
      HB 572: Housing's report of 4 March 2025, 16-0; the retention of
        2 April is Finance's, after its executive session of the 1st, and
        so is the ITL of 30 October, 14-11, with the minority's Ought to
        Pass with Amendment 2025-2956h -- none of it on Housing's page.
      HB 1525, 22 Jan 2026: an executive session with no report dated that
        day; the docket dates it 22 February, no meeting of the committee,
        and it is not moved to the nearest one."""
    ev = _card_events(N)
    codes = {("H", "housing"): "H64", ("H", "finance"): "H34", ("S", "commerce"): "S37"}

    def code_of(name, body):
        return codes.get((body, (name or "").strip().lower()))

    meetings = {
        "HB1681": [("2026-02-17", "H64", ["public hearing"]),
                   ("2026-03-03", "H64", ["executive session"]),
                   ("2026-04-21", "S37", ["hearing"])],
        "HB1652": [("2026-02-17", "H64", ["public hearing", "executive session"]),
                   ("2026-10-01", "H64", ["executive session"])],
        "HB65": [("2025-01-21", "H64", ["public hearing"]),
                 ("2025-09-23", "H64", ["executive session", "full committee work session"]),
                 ("2026-10-01", "H64", ["executive session"])],
        "HB572": [("2025-01-28", "H64", ["public hearing"]),
                  ("2025-03-04", "H64", ["executive session"]),
                  ("2025-04-01", "H34", ["executive session"]),
                  ("2025-10-30", "H34", ["executive session"])],
        "HB1525": [("2026-01-22", "H64", ["public hearing", "executive session"])],
    }

    def at(bill, code, date, signins=None):
        acts = CA.acts(ev[bill])
        own = CA.owners(acts, meetings[bill], code_of)
        mine = {d: k for d, c, k in meetings[bill] if c == code}
        return CA.outcome(code, date, mine[date], acts, own, mine, signins)

    def rep(bill, code):
        acts = CA.acts(ev[bill])
        own = CA.owners(acts, meetings[bill], code_of)
        return CA.reported(code, acts, own, {d: k for d, c, k in meetings[bill] if c == code})

    bad = []

    def want(got, **kw):
        miss = {k: (got.get(k), v) for k, v in kw.items() if got.get(k) != v}
        if miss:
            bad.append(f"{miss} in {got}")

    signed = {"date": "2026-02-17", "total": 13, "support": 7, "oppose": 6, "neutral": 0,
              "dated": True}
    want(at("HB1681", "H64", "2026-02-17", signed), outcome="heard",
         signins={"for": 7, "against": 6, "neutral": 0, "total": 13},
         voted={"act": "report", "date": "2026-03-03", "meeting": "2026-03-03"})
    got = at("HB1681", "H64", "2026-03-03")
    want(got, outcome="voted")
    want((got.get("votes") or [{}])[0], act="report", code="OTPA", amendment="2026-0998h",
         yeas=17, nays=0, dated="vote", meeting="2026-03-03")
    want(at("HB1681", "S37", "2026-04-21"), outcome="heard",
         voted={"act": "report", "date": "2026-05-07"})
    want(rep("HB1681", "S37")[0], dated="sitting", code="OTPA", yeas=4, nays=1)
    if "meeting" in rep("HB1681", "S37")[0]:
        bad.append("the Senate's report of HB 1681 is placed at a meeting")
    got = at("HB1652", "H64", "2026-02-17")
    want(got, outcome="voted")
    want((got.get("votes") or [{}])[0], code="IS", recommendation="Interim Study",
         yeas=12, nays=0)
    got = at("HB1652", "H64", "2026-10-01")
    want((got.get("votes") or [{}])[0], act="study report", said="rec", killed=False,
         yeas=8, nays=1)
    got = at("HB65", "H64", "2026-10-01")
    want(got, outcome="voted")
    want((got.get("votes") or [{}])[0], act="study report", said="not", killed=True,
         yeas=5, nays=4, date="2026-09-30", meeting="2026-10-01")
    want(at("HB65", "H64", "2025-01-21"), outcome="heard",
         voted={"act": "retained", "date": "2025-01-31"})
    housing = [(a["act"], a.get("code")) for a in rep("HB572", "H64")]
    finance = rep("HB572", "H34")
    if housing != [("report", "OTPA")]:
        bad.append(f"House Housing's acts on HB 572: {housing}")
    if [a["act"] for a in finance] != ["retained", "report"]:
        bad.append(f"House Finance's acts on HB 572: {finance}")
    else:
        want(finance[1], code="ITL", yeas=14, nays=11, minority_code="OTPA",
             minority_amendment="2025-2956h", meeting="2025-10-30")
    want(at("HB1525", "H64", "2026-01-22"), outcome="heard",
         voted={"act": "report", "date": "2026-02-22"})
    if CA.study_said("Interim Study Report: Without Recomendation (Vote 10-10)") != "without":
        bad.append("a study report without a recommendation is not read as one")
    assert not bad, "; ".join(bad[:6])
    return "ok", ("HB 1681 heard on 17 Feb 2026 (7 for, 6 against) and voted on 3 March, 17-0; "
                  "HB 1652-FN Interim Study, 12-0; HB 65's study report not recommended, 5-4, "
                  "killed; HB 572's Finance acts on Finance's page alone")
