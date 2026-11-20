#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
The passage rail and the journey: the four stops a bill passes and what
happened at each (passage), and what each chamber decided and when, read from
the docket a line a decision (journey) -- the dated stops of a bill's rail and
the "How it got here" row of On the record both read that one list.

    import journey as J
    J.passage(narr["stages"], kind, status, bid)        # the rail's marks, as the list card draws them
    J.journey(narr, bid, rcs, chapter, law_line, term)  # (the day it was introduced, [a dict a decision])
    J.journey_rail(intro, steps, rail, bid)             # the rail's stops, dated from the journey

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: the largest of its subsystems, the
`_j_*` family). It moved here as it stood, comments and all; two of its
constants that sat further down build_site_v2 came with it, after the rest
(RAIL_SAY, the words of a stop no line fills, and J_ENDING). What it reads of
build_site_v2 and is no one subsystem's is parts.py's, and conferences.py
holds what the two chambers did with each other's version, so this imports
no builder (_import_cycles_cut). build_site_v2 imports every name here back
under its own, so build_site_v2.journey, build_site_v2._j_words and the rest
answer as they did.
"""

import functools
import re
from collections import defaultdict
from datetime import date as _date

import law_effect as LE
import names
import narrative as N
import shell as _shell
from conferences import CONF_UNABLE_RE, conference_failure
from parts import (BILL_OF_INTENT, DIED, INTERIM_STUDY, NO_GOVERNOR, REFERENDUM, SINGLE_CHAMBER,
                   TABLED, bill_prefix, docket_line)


# The four stops a bill passes, and what happened at each. "p" passed,
# "h" here now, "x" stopped here, "-" never reached.
#
# Read off the stages narrative.py built from the docket, which every bill
# has. house_status and senate_status from the status page would have been
# the obvious source and cover 1,387 of the current term's 2,234 bills and
# none of the archive.
# A HOUSE RESOLUTION NEVER GOES TO THE SENATE. HR and SR are the business of
# one chamber -- its rules, its own thanks and condolences -- and they never
# cross, never reach a governor and never become law. A concurrent resolution
# (HCR, SCR) and a constitutional amendment (CACR) do cross, so they are not
# in here. A special session numbers the same kinds with "SS" in front: SSHR 1
# of 2008 is the House adopting its rules and has two stops, not four.
ONE_CHAMBER = ("HR", "SR", "SSHR", "SSSR", BILL_OF_INTENT)
# The chamber a measure starts in, by its number.
OWN_CHAMBER = {"HB": "H", "HCR": "H", "HJR": "H", "HR": "H",
               "SB": "S", "SCR": "S", "SJR": "S", "SR": "S"}


def passage(stages, kind, status="", bill="", passed=None, acted=None, over=False):
    """`passed` is the chambers whose own last decision on the bill, in the
    journey, carried it on (journey_state "p"); `acted` every chamber the
    journey has deciding anything, in the order they first did; `over`
    whether the bill's session has no days left to sit, which ends a bill
    held for interim study (the Law stop below)."""
    hands = [st.get("hand", "") for st in (stages or []) if st.get("hand")]
    # A CHAMBER THAT DECIDED ON THE BILL WAS REACHED. The stages are built
    # from the lines narrative.py recognises, and "Introduced and Laid on
    # Table MA VV" -- one of the two lines with which the House of June 2020
    # laid 45 Senate bills on the table -- is not one of them, so SB 436's
    # rail said the House was never reached by a bill the House had tabled.
    for b in (acted or ()):
        if b not in {h.split(":")[0] for h in hands}:
            hands.append(f"{b}:floor")
    if not hands:
        return ""
    # A RAIL IS FOUR CLAIMS, AND IT MAY NOT CONTRADICT THE FIFTH. It is drawn
    # from the hands the docket names, and an archived docket does not always
    # name them all: 29 bills that became law came out as "House: stopped
    # here ... Law: passed". Where the marks disagree with the outcome beside
    # them, no rail is drawn -- as for the 21,000 archived bills that had
    # none at all until now.
    if kind == "law" and not {"H", "S"} <= {h.split(":")[0] for h in hands}:
        return ""

    # TWO STOPS, NOT FOUR. The rail drew a resolution against a Senate it was
    # never going to see and a Law it could never become, and marked its own
    # chamber with an X for stopping there -- so 36 resolutions that were
    # ADOPTED showed a cross on the chamber that adopted them. What the rail
    # should say is simply: this chamber, and whether it adopted the thing.
    if bill and any(bill.upper().startswith(k) and
                    not bill.upper().startswith(k + "R") for k in ONE_CHAMBER):
        origin = hands[0].split(":")[0]
        if origin in ("H", "S"):
            # Or where the docket has the chamber adopting it: HR 13 of 2007,
            # "Introduced and Adopted", whose status field says in committee.
            adopted = (kind == "adopted" or "adopt" in (status or "").lower()
                       or origin in (passed or ()))
            return origin + ("p" if adopted else "x") + ("p" if adopted else "x")
    # A bill reaches the governor THROUGH BOTH CHAMBERS. SB286 never left the
    # Senate -- laid on the table, then killed under Senate Rule 3-23 -- and
    # its last docket row is "Enrolled Adopted, VV", which stage_of files with
    # the governor. Dropped from the HANDS, not just from the set derived from
    # them: taking it out of the set alone left "where it ended" pointing at a
    # stop that was no longer on the rail, so the Senate read as passed rather
    # than as where the bill stopped.
    if not {"H", "S"} <= {h.split(":")[0] for h in hands}:
        hands = [h for h in hands if not h.startswith("G")]
    # AND THE GOVERNOR DID NOT ACT ON A BILL A CHAMBER ENDED. HB 613 and HB 614
    # of 1993 passed both chambers; the Senate recalled and tabled each the
    # next day and killed it with every tabled bill on 25 May, the day of a
    # House row "ENROLLED", which stage_of files with the governor. The rail
    # read "Senate: Passed, Governor: Passed, Law: Did not become law" beside
    # "Killed". A bill that reached the governor is law, or was vetoed, or is
    # there now: where the status is none of those and a chamber's own last
    # word did not carry the bill on, the enrolment is no governor's stop.
    if (kind == "done" and passed is not None and "veto" not in (status or "").lower()
            and not {"H", "S"} <= set(passed)):
        hands = [h for h in hands if not h.startswith("G")]
    if not hands:
        return ""
    seen = {h.split(":")[0] for h in hands}
    moving = kind == "active"
    # Where it ended is the last hand it was in.
    last = hands[-1].split(":")[0]
    # IN THE ORDER THE BILL TRAVELLED. A Senate bill goes to the Senate first
    # and the rail drew House first for everything, so SB 139 opened with an
    # empty House stop it had never been to. The chamber of origin comes from
    # the bill's own first hand rather than from its number -- the record
    # answering for itself.
    origin = next((h.split(":")[0] for h in hands
                   if h.split(":")[0] in ("H", "S")), "H")
    # UNLESS THE RECORD HAS FILED A ROW UNDER THE WRONG CHAMBER, and both
    # chambers decided on the bill: then its number says which went first.
    # HB 1650 of 2022 passed the House and the Senate on 5 January; the
    # House's rows were entered on the 10th, and the rail opened in the
    # Senate. The Senate's "Introduced 9/7/2011" on HB 652 of 2011 predates
    # the House vote that sent it there. A bill decided on by one chamber
    # keeps the record's answer, whatever its number.
    own = OWN_CHAMBER.get(bill_prefix(bill), "") if bill else ""
    if own and own != origin and {"H", "S"} <= set(acted or ()):
        origin = own
    other = "S" if origin == "H" else "H"
    # The governor stop says what the GOVERNOR DID, not that the bill got as
    # far as the desk. Reaching a stop was being read as clearing it, so all
    # 68 vetoed bills drew a green check on the governor who vetoed them --
    # the rail stating the opposite of the sentence beside it.
    vetoed = kind == "veto" or "veto" in (status or "").lower()
    reached_gov = "G" in seen
    out = []
    for stop in (origin, other, "G"):
        if stop not in seen:
            out.append("-")
        elif stop == "G" and bill and bill_prefix(bill) in NO_GOVERNOR:
            # "Enrolled" is filed with the governor, but a CACR, HCR or SCR
            # never goes to one: 30 resolution rails read "Governor: passed".
            out.append("-")
        elif stop == "G":
            out.append("x" if vetoed else
                       "p" if kind == "law" else
                       "h" if moving else "p")
        elif moving and stop == last:
            out.append("h")
        elif reached_gov or (stop == origin and other in seen):
            # It CLEARED this chamber: the bill went on from here, and a later
            # visit does not undo that. The House that failed to override the
            # veto of HB 1442 by 165-149 had passed the bill in May, and
            # crossing it because the override was the last thing in the
            # docket said the House had rejected it.
            out.append("p")
        elif kind == "adopted":
            # A resolution both chambers adopted stopped in the second one
            # because it was finished, not because it was refused there:
            # CACR 13 of 2026 drew a cross on the Senate that passed it 23-1.
            out.append("p")
        elif stop in (passed or ()):
            # THE LAST HAND IS NOT ALWAYS WHERE IT WAS STOPPED. HCR 14 of 2026
            # was adopted by the House, 5 March, and never taken up by the
            # Senate; its rail crossed the House that adopted it, beside a chip
            # saying "Passed one chamber". SB 625 passed the Senate and then
            # the House, amended; the Senate refused the amendment and the
            # conference never reported, and the rail crossed the House that
            # had passed it. A chamber whose own last word carried the bill on
            # is passed, and the stop after it is where it went no further.
            out.append("p")
        elif stop == last:
            out.append("x")
        elif acted and stop in acted:
            # Not the last hand, and its own last word did not carry the
            # bill on: SB 223 of 2020's docket dates the House's referral
            # before the Senate's final vote, so the Senate was the last hand,
            # and the House -- which then laid it on the table -- read passed.
            out.append("x")
        elif stop == other and status == "Passed one chamber" and not moving:
            # ONE CHAMBER PASSED IT, AND THIS IS THE OTHER. CACR 9 of 1995
            # passed the Senate 18-6 on 21 February; the House's row of
            # introduction states the 16th, so the Senate was the last hand,
            # and the House -- which vacated it from committee and "RETURNED
            # TO SENATE PER HOUSE RULE 19B" without a vote -- read passed,
            # beside a chip saying one chamber had. Of a measure that is
            # finished: while it is still moving the second chamber has not
            # stopped it, and a cross there would say it had.
            out.append("x")
        else:
            out.append("p")
    # THE FOURTH STOP IS THE OUTCOME, NOT A PLACE -- and it was drawing the
    # "here now" ring on 175 bills that are going nowhere. A bill is never AT
    # the law stop: it either became law or it did not, and while it is still
    # moving the honest mark is that it has not got there. The ring is a
    # 3px pine circle that reads as active, so a bill laid on the table in a
    # chamber that has finished sitting was showing a bold "in progress" mark
    # on its outcome. Reported, and right.
    # AND A BILL HELD FOR INTERIM STUDY DID NOT BECOME LAW ONCE ITS SESSION
    # ENDED (the person, 8 October 2026, option (d)): no row in nineteen
    # terms acts on one after its chamber's last sitting, and a committee's
    # recommendation is advice for a new bill in the next term. While the
    # session sits it could still be taken back (SB 409 of 1998 was, on 10
    # September 1998, and became law), and Law is not reached.
    out.append("p" if kind == "law" else
               "x" if kind in ("done", "veto") or (kind == "study" and over) else "-")
    # The order is part of the answer, so it travels with it.
    return origin + "".join(out)


# =============================================================== THE JOURNEY ==
#
# WHAT EACH CHAMBER DECIDED, AND WHEN: one line a decision, read from the
# docket, for the two places a bill's own view says how it got where it is --
# the dated stops of its rail and the "How it got here" row of On the record.
# Both read this one list, so the two cannot say different things.
#
# NOT THE STATUS PAGE'S HOUSE STATUS AND SENATE STATUS. Those were the rows On
# the record printed, and they are blank for one chamber on most bills: of
# this term's 2,234, 932 carry only a House status, 351 only a Senate one and
# 156 neither. HB 57 of 2025 passed the House on a voice vote on 13 February
# and its House field is empty. The docket has every decision, dated, in the
# chamber's own words -- the same events passage() and bill_disposition()
# already read.
#
# FLOOR DECISIONS ONLY: a motion a chamber carried that moved the bill --
# passed, killed, laid on the table, sent to interim study or back to
# committee, agreed to or refused the other chamber's amendment, adopted or
# rejected a conference report, overrode a veto or sustained it -- and a
# motion to pass that failed. Plus the governor, the chapter, and a CACR's
# referendum where the docket records one. Amendments, special orders,
# reconsiderations and rules suspensions are the Votes tab's, not this list's.
#
# Read clause by clause, because the clerks of 1989-1998 wrote a sitting's
# business on one line -- "COMM AM, AA VV; PASSED WITH AM VV; SJ20,P503" --
# and every era punctuates the motion, the vote and the outcome its own way.
# What a clause decided is the motion code the clerk wrote (MA, MF, AA...) or,
# on the oldest lines, the verb: "PASSED", "LAID ON THE TABLE", "RE-REFERRED".
# A clause naming a motion and no outcome -- "Ought to Pass [Not Voted On]",
# "Sen. Ward Moved Ought to Pass" -- decided nothing and is not a line.

# The event types that are never a floor decision. "introduced" is read for
# its date on its own; "Introduced and Adopted" and "Introduced ..., and Laid
# on Table" are typed floor or other, and are read.
J_NOT_FLOOR = {"hearing", "exec", "worksession", "report", "conference_meeting",
               "interim_report", "consent_off", "retained", "died", "introduced",
               "vacated", "subcommittee"}
# The motion codes are case-sensitive, as rollcall_outcomes reads them: "ma"
# is a syllable of a name as often as it is a motion.
# Lower case only where a voice vote follows: "Sen. Hollingworth susp rules
# for 3rd reading, ma 2/3vv; 3rd reading; ma vv" (HB 100 of 1999).
J_YES_CODE = re.compile(r"\b(?:MA|AA)\b|\b(?:ma|aa)(?=[,\s]+(?:2/3\s*)?vv\b)")
J_NO_CODE = re.compile(r"\b(?:MF|ML|AF|AL)\b|\b[am][fl](?=[,\s]+(?:2/3\s*)?vv\b)")
J_YES_WORD = re.compile(r"\b(?:adopted|adpoted|adotped|passed|overrid+en|concurred|"
                        r"carried|killed)\b", re.I)
J_NO_WORD = re.compile(r"\b(?:failed|fails|lost|defeated|lacking|not\s+adopted|"
                       r"sustained|overturned)\b", re.I)
# A tally, however the clerk wrote it: "RC 217-156", "RC(15-8)", "RC 16Y-8N",
# "DIV (166-103)", "DV 183-163", "Division 13Y-11N", "ROLL CALL: YEAS 5 NAYS
# 17", "ROLL CALL VOTE: YEA-13 NAYS-11" (HB 377 of 1989).
J_TALLY = re.compile(
    r"\b(?P<k>RC|DIV|DV|Division|Roll\s*Call)\b(?:\s+vote)?\.?\s*[:,]?\s*\(?\s*"
    r"(?:YEAS?\s*[-:]?\s*)?(?P<y>\d{1,3})\s*[Yy]?\s*(?:[-–]|,?\s*NAYS?\s*[-:]?)\s*"
    r"(?P<n>\d{1,3})(?!\d)", re.I)
J_RC_BARE = re.compile(r"\bRC\b|\bRoll\s*Call\b", re.I)
# "VV", "2/3VV", "MA 2/3 VV". Upper case only: it is a code, not a word.
J_VOICE = re.compile(r"(?<![A-Za-z])(?:VV|vv)\b|\bvoice\s+vote\b")
# Business that is not a decision about the bill's fate, however it was
# carried: the order of the day, the rules, a reconsideration (whose result is
# the next decision), a bill coming off the table or the consent calendar, a
# motion recorded as pending or not voted on, the chair's rulings.
# Not "GOVERNOR'S VETO SUSTAINED RC(11-11) (VETO MESSAGE PRINTED)" (SB 105 of
# 1993): the message was printed; the vote is the House's.
J_SKIP = re.compile(
    r"enrolled|special\s+order|reconsider|notice\s+of|^\s*(?:secs?|sections?)\b|"
    r"\b(?:remov\w*|taken|take)\s+(?:\w+\s+){0,2}from\s+(?:the\s+)?(?:table|consent)|"
    r"from\s+the\s+consent|pending\s+motion|(?<!message )\bprint\w*|"
    r"limit\w*\s+debate|divisible|divided|previous\s+question|moved\s+the\s+question|"
    r"non-?\s?germane|\brul(?:ed|ing)\b|rescind|technical\s+(?:and\s+\w+\s+)?correction|"
    r"sent\s+to\s+(?:the\s+)?governor|^\s*sections?\b|change\s+rept|deadline|"
    r"late\s+(?:drafting|filing|introduction)|withdr[ae]w|\bappoint", re.I)
J_NOT_VOTED = re.compile(r"^[^;]*?\bnot\s+voted\s+on\b\s*[)\]]?\s*,?\s*", re.I)
# A VOTE TO SUSPEND THE RULES DECIDES ONLY THAT THE RULES ARE SUSPENDED, and
# the business it names is what it lets the chamber take up, not what the
# chamber then did with it. "REPS WHEELER & BURLING MOVED TO SUSP RULES FOR
# CONF COMM REPORT, ML RC(221-135)" (HB 1 and HB 2 of 1997) is 221 members
# wanting to take the report up, short of two thirds -- and it read as the
# House rejecting the budget's conference report. "Rules Suspension to
# consider at the present time ... MF lacking necessary 2/3 RC 197-143" (CACR
# 21 of 2020) read as the House defeating a CACR a majority wanted to hear.
# So the suspension is taken out of the clause, through its own outcome and
# the vote that carried it, and what the clause says after that is read as
# usual: "Sen. Below Moved Rule Suspension, MA, VV (2/3rds Nec) Sen. Below
# Moved Rerefer, MA, VV" (HB 542 of 1999) is the bill sent back to committee.
J_SUSPEND = re.compile(r"\bsusp(?:\.|\w*)", re.I)
# "RULES SUSPENDED PLACED ON THIRD READING PASSED/ADOPTED" (HB 750 of 1989),
# "JOINT RULES SUSPENDED CONF COMM REPORT ADOPTED": the clerk's past tense,
# with no vote of its own. The words go, and the business after them stays.
J_SUSPENDED = re.compile(r"\b(?:(?:joint|jt\.?|house|senate)\s+)?rules?\s+suspended\b\s*[:;,]?",
                         re.I)
# The business a suspension would allow "if passed" is not its outcome.
J_IF_PASSED = re.compile(r"\b(?:if|upon|when)\s+(?:so\s+)?(?:passed|adopted|passage)\b", re.I)
# Its outcome is the first motion code after it, or on a line with none the
# first word of one -- not "adopted" in "by the adopted Senate deadline for
# HBs. 2/3 necessary, MA, RC 24Y-0N" (HB 652 of 2012).
J_SUSP_CODE = re.compile(r"\b(?:MA|MF|ML|AA|AF|AL)\b")
# The purpose, not a rule it sets aside: "SUSP RULES TO REF TO FINANCE", "for
# late ref to Finance" -- not "Rules Suspension to consider at the present
# time without required referral to committee" (HB 1650 of 2022).
J_SUSP_REFERRAL = re.compile(r"\b(?:to|for)\s+(?:late\s+)?ref(?:er(?:ral)?|\.)?\s+to\s+"
                             r"(?P<c>[A-Za-z0-9][A-Za-z0-9&/ ]*?)\s*(?:,|\(|\bafter\b|$)", re.I)
J_SUSP_WORD = re.compile(r"\b(?:adopted|failed|lost|lacking|carried|defeated|not\s+getting)\b",
                         re.I)
# What follows a suspension's outcome and is still the suspension's: the vote
# and the two thirds it needed.
J_SUSP_VOTE = re.compile(
    r"(?:[\s,;:.()]*(?:\d\s*/\s*\d\s*(?:rds?)?\s*(?:VV|nec\w*\.?)?|"
    r"(?:RC|DV|DIV|Division)?\s*\(?\s*\d{1,3}\s*[YN]?\s*-\s*-?\s*\d{1,3}\s*[YN]?|"
    r"(?:VV|RC|DV|Division|DIV|MF|MA|ML|vote|the|by|two-thirds|lacking|obtaining|getting|not)\b|"
    r"(?:required|nec|req)\w*\.?|"
    r"\d{1,2}/\d{1,2}/\d{2,4}))*[\s,;:.()]*", re.I)


def _j_unsuspend(clause):
    """A clause without the suspension of the rules in it: "" where that is
    all it was."""
    m = J_SUSPEND.search(clause or "")
    if not m:
        return clause
    past = next((x for x in J_SUSPENDED.finditer(clause)
                 if x.start() <= m.start() < x.end()), None)
    # What was before it and what comes after are kept apart, each a clause
    # of its own: "REPS PALUMBO & CHAMBERS SUSP RULES TO CONSIDER, MA 2/3VV,
    # ADOPTED" (HCR 6 of 1989) is the resolution adopted, not the movers.
    if past and not re.search(r"\bmov\w*|\bmotion\b", clause[:past.start()], re.I):
        return _j_unsuspend("; ".join(x for x in (clause[:past.start()].strip(" ,;:/"),
                                                   clause[past.end():].strip(" ,;:/")) if x))
    head = clause[:m.start()]
    # Blanked rather than removed, so positions in the rest still count.
    rest = J_IF_PASSED.sub(lambda x: " " * len(x.group(0)), clause[m.end():])
    o = J_SUSP_CODE.search(rest) or J_SUSP_WORD.search(rest)
    if not o:
        # No outcome: the clause from the suspension on is the motion,
        # wrapped onto the next row if it goes on (_j_rows joins it).
        return head.strip(" ,;:")
    end = J_SUSP_VOTE.match(rest, o.end()).end()
    left = _j_unsuspend("; ".join(x for x in (head.strip(" ,;:"), rest[end:].strip(" ,;:"))
                                  if x))
    # EXCEPT A SUSPENSION TO SEND THE BILL TO A SECOND COMMITTEE, which is
    # the referral: "COMM AM, AA VV; PASSED WITH AM VV; REPS A TORR & TROMBLY
    # SUSP RULES TO REF TO FINANCE, MA 2/3VV" (HB 1162 of 1996), whose House
    # passage was in March, after Finance.
    ref = J_SUSP_REFERRAL.search(rest, 0, o.start())
    if ref and re.match(r"MA|AA|adopted|carried", o.group(0), re.I):
        return f"Referred to {ref.group('c').strip()}" + (f"; {left}" if left else "")
    return left


def _j_suspension_failed(raw):
    """Where in a row a vote to suspend the rules failed, or -1.

    _j_unsuspend takes the vote out of the clause, which is right for what
    the bill's line says and loses that the chamber voted: "REPS GROSS &
    CHAMBERS MOVED TO SUSP RULES, ML DIV(213-115)" and then "REP KURK MOVED
    TO RECONSIDER, MA VV" (HB 322 of 1991) is the House taking up again the
    suspension it had just refused, not its refusal of the Senate's
    amendment a month before. Not "RULES SUSPENDED", which is the clerk's
    past tense for one that carried."""
    for x in re.finditer(r"[^;]+", raw or ""):
        clause = x.group(0)
        m = J_SUSPEND.search(clause)
        if not m or any(y.start() <= m.start() < y.end()
                        for y in J_SUSPENDED.finditer(clause)):
            continue
        rest = J_IF_PASSED.sub(lambda y: " " * len(y.group(0)), clause[m.end():])
        o = J_SUSP_CODE.search(rest) or J_SUSP_WORD.search(rest)
        if o and not re.match(r"MA|AA|adopted|carried", o.group(0), re.I):
            return x.start() + m.start()
    return -1


# The procedural motions whose outcome the clerk can put in the next clause:
# "Enrolled Bill Amendment{2230}; Adopted", "Sen. Gordon Moved Remove From
# Table; MA, VV". Not a finished act -- "REP BUCKLEY WITHDREW RECOMMIT
# MOTION; ADOPTED VV" is SCR 1 of 1995 adopted.
J_TAKES_OUTCOME = re.compile(r"\benroll|\b(?:remov\w*|taken|take)\s+(?:\w+\s+){0,2}from\s+"
                             r"(?:the\s+)?table|\breconsider|special\s+order", re.I)


# What a clause is about, tried in this order: a clause about a conference
# report is not an adoption of the bill, and one about the other chamber's
# amendment is not an amendment of this one.
J_ACTS = [
    # A vote on the veto names the veto. "SUSTAINED" alone is also the House
    # upholding its chair: "RULING OF CHR" / "SUSTAINED VV; PASSED WITH AM
    # RC(233-122)" (HB 1075 of 1998, which became law) drew a veto the
    # governor never made. A vote wrapped onto the next row, "...; GOVERNOR'S
    # VETO" / "SUSTAINED RC(221-117)" (HB 332 of 1995), is joined by _j_rows.
    ("veto_vote", re.compile(r"\bveto\w*\b[^;]{0,60}?\b(?:overrid|sustain)|"
                             r"\b(?:overrid|sustain)\w*[^;]{0,60}?\bveto|"
                             r"notwithstanding|\bshall\b[^;]{0,40}\bbecome\s+law", re.I)),
    # "As Passed by the House {2199}" is the name of the version a committee
    # of conference proposes, not a chamber passing the bill: all fourteen
    # rows in the record that say it are conference reports. The Senate's
    # "As Passed by the House {2199} RC 13Y-11N, Adopted" (HB 429 of 2007)
    # is it adopting conference report #2199 -- which read as the Senate
    # passing the bill 13-11, three weeks after it did so on a voice vote.
    ("conference", re.compile(r"conf(?:erence)?\.?\s*comm(?:ittee)?\.?\s*rep(?:ort|t)?\b"
                              r"|committee of conference report|\bC\s?of\s?C\s+rep"
                              r"|\bas\s+passed\s+by\s+(?:the\s+)?(?:house|senate)\b", re.I)),
    ("accede", re.compile(r"acced", re.I)),
    ("nonconcur", re.compile(r"non-?\s?conc|\bnonc\b|refus\w*\s+to\s+(?:concur|accept)",
                             re.I)),
    ("concur", re.compile(r"\bconc(?!urrent)(?:ur\w*|urrence)?\b", re.I)),
    # "Inexpedient to Legislate, Senate Rule 3-23, Adjournment 09/16/2020"
    # and, from 2025, the same without "Adjournment": the rule that kills a
    # bill still on the table. No motion code, because nothing was moved.
    # And the older rules to the same end: "ITL PER JOINT RULE 10(c)(1)"
    # (SB 4 of 1989), "DIED ON TABLE (RULE 6F)" (HB 250 of 1990).
    # AND 2013'S, "Inexpedient to Legislate, 2013 Adjournment, Senate Rule
    # 3-23" (HB 135 of 2013 and 18 others), whose year and "Adjournment"
    # stood between the words and the rule: read by nothing, so the bill's
    # last line was the Senate laying it on the table (the review of the
    # tabled bills, 8 October 2026).
    ("died", re.compile(r"(?:inexpedient\s+to\s+legislate|\bITL\b),?\s*"
                        r"(?:\d{4}\s+adjournment,?\s*)?(?:per\s+|under\s+)?"
                        r"(?P<rule>(?:senate|house|joint)\s+rule\s+[\w\-]+(?:\([\w]+\))*)"
                        r"|died\s+on\s+(?:the\s+)?table\s*\(\s*(?P<rule2>rule\s+[\w\-]+)\s*\)",
                        re.I)),
    # And the clerk's spellings: "REP HOLDEN MOVED REF FOR STUDY, MA VV" (CACR
    # 25 of 1992), "Sen. Below moved Rerefer to Iterim Study, MA, VV" (HB 109
    # of 2000).
    ("study", re.compile(r"\bin?terim\s+study|\bint\.?\s+study|\bRFS\b|"
                         r"\bref(?:er\w*)?\.?\s+for\s+study", re.I)),
    ("postponed", re.compile(r"indefinite\w*\s+postpone|\bindef\w*\.?\s+post", re.I)),
    # "Inexpedient to Lehgislate, MA, VV" (HB 353 of 2002): the clerk's
    # typing, so the first word is enough.
    # And "Ought Not to Pass", the report against an address for the removal
    # of a judge, adopted: "Ought Not to Pass: MA DIV 220-106" (HA 1 of 2010).
    ("killed", re.compile(r"\binexpedient\b|\bITL\b|\bkilled\b|"
                          r"\bought\s+not\s+to\s+pass\b", re.I)),
    ("tabled", re.compile(r"\b(?:lay|laid|lie|placed)\b[^;]{0,40}?\b(?:up)?on\s+(?:the\s+)?table\b"
                          r"|\btabled\b|\bLOT\b", re.I)),
    ("recommitted", re.compile(r"\brecommit\w*|\bre-?\s?refer\w*|\breferred\s+back",
                               re.I)),
    # "Adopted" is the passage of a resolution only where it is the motion:
    # "ADOPTED VV", "INTRODUCED AND ADOPTED", "PASSED/ADOPTED", "ADOPTED WITH
    # AM". After another motion it is that motion's outcome -- "ITL REPORT
    # ADOPTED" is a bill killed.
    ("passed", re.compile(r"ought\s+to\s+(?:pass|adopt)|\bOTP\w*|\bthird\s+reading\b|"
                          r"\b3rd\s+r(?:ea)?d(?:in)?g\b|\bOT\s?3\s?rd?g\b|\bpassed\b|^\s*pass\b|"
                          r"^\s*(?:[HS]\s+)?(?:introduced\s+and\s+)?adopt(?:ed|ion)?\b|"
                          r"\badopted\s+with\s+am|\bresolution\s+adopted\b", re.I)),
]
# "SEN RUSSMAN MOVED ITL ON BILLS LOT, MA VV" (SB 66 of 1993) kills the bills
# on the table; the table is where they were, not what was moved.
J_ON_THE_TABLE = re.compile(r"\b(?:on\s+)?(?:all\s+)?bills\s+(?:LOT|(?:laid\s+)?on\s+"
                            r"(?:the\s+)?table)\b", re.I)
# An amendment's own vote, not the bill's: "COMM AM, AA VV", "Committee
# Amendment # 2025-2308s, RC 16Y-8N, AA", "Sen. Birdsell Floor Amendment #
# 2026-1719s, AA, VV", "FLAM # 2025-1311h (Rep. McFarlane): AF DV 57-286".
# Adopted, it tells that day's passage that the bill passed amended --
# whichever of the two the clerk entered first: "Sen. Larsen moved OTP, MA,
# VV; Sen. Larsen Fl. Amend. (0179) AA, VV" (SR 3 of 1999). And the clerks'
# other ways of writing who offered it and what it was: "Sen. McCarley,
# Floor Amendment., {1666}" (HB 265 of 1999), "Flr AM {1759h}, AA" (SB 310
# of 2006).
J_AMEND_SUBJ = re.compile(
    r"^\s*(?:(?:Reps?|Sens?|Senator)[.,]?\s+[^,;:]*?,?\s+)?(?:adopt(?:ion\s+of)?\s+(?:the\s+)?)?"
    r"(?:prop(?:osed)?\s+)?(?:maj(?:ority)?\.?\s+|min(?:ority)?\.?\s+)?"
    r"(?:comm(?:ittee)?\.?\s+|floor\s+|flr?\.?\s+|senate\s+|house\s+|approp\s+)?"
    r"(?:am(?:end(?:ment)?)?s?\b|FLAM\b)", re.I)
# "Ought to Pass W/Majority Amendment, {1330}" (SB 108 of 1999), "Ought to
# Pass with Part of AM #1223h" (SB 492 of 2008).
J_AMENDED = re.compile(r"\bw(?:ith|/)\s*(?:part\s+of\s+)?(?:the\s+)?"
                       r"(?:maj(?:ority)?\.?\s+|min(?:ority)?\.?\s+|comm(?:ittee)?\.?\s+|"
                       r"floor\s+|fl\.?\s+)?am|\bas\s+amended|\bOTP\s*/\s*AM|\bOTPA\b|"
                       r"with\s+amendments?\b", re.I)
# AN AMENDMENT ADOPTED IN THE CLAUSE THAT PASSES THE BILL. The Senate of
# 1999-2002 wrote the two as one: "Sen. Larsen Floor Amendment {0965}, AA,
# VV, OT3rdg, RC 14Y-8N, MA" (HB 117 of 1999) is the bill passing amended,
# and it read "Passed, 14-8"; so is "Ought to Pass, MA, VV, Sen. Brown Floor
# Amendment, {1865}, RC 14Y-8N, AA" (HB 626 of 1999), the amendment after
# the motion. Adopted, with no other motion's code between the amendment
# and its AA.
J_AMEND_ADOPTED = re.compile(r"(?i:\bam(?:end(?:ment)?)?s?\b|\bFLAM\b)"
                             r"(?:(?!\b(?:MA|MF|ML|AF|AL)\b)[^;])*?\bAA\b")
# Past tense on the oldest lines is the outcome: "LAID ON THE TABLE",
# "RE-REFERRED TO HEALTH", "REFERRED TO INTERIM STUDY", with no code after.
J_DONE_VERB = re.compile(r"\b(?:laid|tabled|re-?referred|recommitted|referred|"
                         r"postponed)\b", re.I)
# "Ought to Pass, MA. VV. Rule 24 (refer to Finance)" and "..., AA, Refered
# to Finance Rule #24" (HB 224 and HB 1240 of 1999-2000) are the Senate
# sending a bill it approved to Finance, as much as "PASSED WITH AM AND REF
# TO FINANCE" is.
J_REFERRED_TO = re.compile(
    r"\bref(?:er(?:r?ed)?)?\.?\s+to\s+(?P<c>(?!interim)[A-Za-z][A-Za-z&/ ]{1,40}?)"
    r"(?=\s*(?:\(|\)|\[|\]|rule\b|;|,|$|\d))", re.I)
J_BARE_REFERRAL = re.compile(r"^\s*ref(?:er(?:red)?)?\.?\s+to\s+(?P<c>[A-Za-z][A-Za-z&/ ,]+?)"
                             r"\s*(?:\(|\[|\d|rule\b|$)", re.I)
J_SECOND_COMMITTEE = [(re.compile(r"^fin", re.I), "Finance"),
                      (re.compile(r"^approp", re.I), "Appropriations"),
                      (re.compile(r"^(?:ways|w\s*&\s*m)", re.I), "Ways and Means"),
                      (re.compile(r"^capital", re.I), "Capital Budget")]
J_THIRD = re.compile(r"third\s+reading|3rd\s+r(?:ea)?d(?:in)?g|\bOT\s?3\s?rd?g\b", re.I)
J_SIGNED = re.compile(r"signed\s+by\s+(?:the\s+)?gov|governor\s+signed", re.I)
J_VETOED = re.compile(r"vetoed\s+by\s+(?:the\s+)?gov|^\s*vetoed\b", re.I)
# "...enacted in accordance with Article 44, Part II of New Hampshire
# Constitution without signature of the Governor, July 16, 2008" (SB 312 of
# 2008) has no "the" before "signature".
J_UNSIGNED = re.compile(r"law\s+without\s+(?:the\s+)?(?:governor'?s\s+)?signature|"
                        r"without\s+(?:the\s+)?signature\s+of\s+the\s+governor", re.I)
J_OTHER_BILL = re.compile(r"\b(?:HB|SB|HCR|SCR|HJR|SJR|CACR)\s*(\d+)", re.I)
J_WAIVED = re.compile(r"\bwaiv\w*\b[^;]*\breferral|\breferral\b[^;]*\bwaiv", re.I)
# A MOTION DIVIDED TO TAKE THIS BILL OUT OF IT, and the vote on the bills
# left in it. The House reconsidered its third reading of 14 March 2012 to
# take HB 1659 out, "Divide Third Reading Motion to Remove HB1659: Speaker
# Ordered", then "Remaining Bills to Third Reading: MA VV", and sent HB 1659
# to a second committee -- and the second row, filed under HB 1659 as the
# first was, read as the House passing it.
J_DIVIDED_OUT = re.compile(r"\bdivide\w*\b[^;]*?\bremov\w*\b", re.I)
J_REMAINING = re.compile(r"^\s*remaining\s+bills\b", re.I)
# Where a governor's line starts saying when the law takes effect.
J_EFF_ANY = re.compile(r"\beff(?:ective|\.|:|-)?(?![a-z])|\btake\s+effect", re.I)
# A LAW WITH MORE THAN ONE EFFECTIVE DATE HAS NO ONE DATE TO STATE. "eff. I.
# Sec 3 1/1/2027 II. Rem eff 8/1/2026" (HB 131 of 2026), "eff as provided in
# Sec 3" (HB 557 of 2025), "EFF: 06/05/98*", and the governor's row carried on
# a row of its own: "I. Sections 5 & 6 Eff. 07/01/2011" and then "II.
# Remainder Eff. 08/12/2007" (HB 337 of 2007), which read as "in effect 1 Jul
# 2011" for a law most of which took effect four years earlier.
J_EFF_SEVERAL = re.compile(
    r"\bsec(?:tion)?s?\b|\bsec\.|\bremain\w*|\brem\b|as\s+provided|\bprov\b|"
    r"\bpart\s+[IVX]+\s+(?:eff|shall)|(?:^|[\s;.,])[IVX]{1,4}\.\s|multiple|\*|\bparagraph", re.I)
# The governor's row carried on in rows of its own.
J_EFF_MORE = re.compile(r"^\s*(?:\*|[IVX]{1,4}\.|part\s+[IVX]+\b|(?:the\s+)?remainder\b|"
                        r"effective\b|eff\b|sec(?:tion)?s?\b)", re.I)
J_DAY = re.compile(r"(?<![\d/])(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4}|\d{2})(?![\d/])")
J_MONTH_DAY = re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
                         r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b\.?\s+"
                         r"(\d{1,2}),?\s+(\d{4})\b", re.I)
# The day a clause states at its end: "Adopted and read a 3rd time MA VV
# 01/05/22". Not a sitting the chamber met "in recess of", and not a date in
# brackets, the older dockets' "done as of" a sitting: "Introduced and
# Adopted [11/30/2011]", entered on 4 January.
J_CLAUSE_DAY = re.compile(r"(?<!recess of )(?<!recess of\) )(?<!recess )(?<![\d/\[])"
                          r"(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\W*$", re.I)
# The Senate's way: the day as a clause of its own at the end of the row,
# "Conference Committee Report #2024-2290c , Adopted, VV; 06/13/2024".
J_ROW_DAY = re.compile(r";\s*(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\s*$")
# "Introduced ...", "5/3/2001 Introduced and ref to Judiciary", "Introducing
# and referred to Public Affairs" (SB 12 of 1999), "Sen. Birdsell Moved
# Introduction; 2/3 necessary, MA, VV" (SCR 1 of 2023).
J_INTRO_ROW = re.compile(r"^\s*(?:\d{1,2}/\d{1,2}/\d{2,4}\s+)?introduc(?:ed|ing|tion)\b|"
                         r"\bmoved\s+introduction\b", re.I)
J_REF_TALLY = re.compile(r"\(\s*([\d,]{3,})\s*[-–]\s*([\d,]{3,})\s*\)")
# The other chamber agreeing to a second committee of conference: "HOUSE
# ACCEDED TO REQ FOR NEW CONF COMM, REP R FOSTER MA VV" (HB 723 of 1997),
# "Senator Foster Moved Accede to House Request for New C of C; MA, VV" (HB
# 1640 of 2008). Not "REFUSED TO ACCEDE TO REQUEST OF NEW CONFERENCE
# COMMITTEE" (HB 1248 of 1990).
J_NEW_CONFERENCE = re.compile(
    r"(?<!refused to )(?<!refuses to )\bacced\w*\s+to\s+(?:(?:house|senate)\s+)?req(?:uest)?\s+"
    r"(?:for|of)\s+(?:a\s+)?new\s+(?:conf|c\s?of\s?c|committee\s+of\s+conf)", re.I)
J_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
         "Nov", "Dec"]
# The glyph each decision is drawn with, which carries its state as well as
# its colour: a check for a decision that moved the bill on, a cross for one
# that stopped it, and a turning arrow for one that sent it round again --
# tabled, back to committee, the other chamber's amendment refused.
# INTERIM STUDY HAS ITS OWN MARK, "s" (the person, 8 October 2026: the
# rail's marks): an orange "~", on the line that
# sent the bill there and on the rail's stop where it was held, so the page
# has one mark for the act. It was the turning arrow here and, on the rail,
# the red cross of a bill killed. And a bill lying on the table takes the
# pause, "t", on its stop and on the line that laid it there (journey_rail):
# while its session still sits, and -- the person, 8 October 2026 -- once it
# has died there, when its line of the death and the Law stop take the
# cross (died_on_table). The interim study committee's report is a line of
# its own once the session is over (study_ending): the "~", or "f", an
# arrow, where the committee recommended the subject for future
# legislation, coloured by what the report said (its "rec"; app.css .jrec-*).
J_MARK = {"passed": "p", "adopted": "p", "concurred": "p", "conf_adopted": "p",
          "override": "p", "signed": "p", "unsigned": "p", "law": "p",
          "ratified": "p",
          "killed": "x", "failed": "x", "postponed": "x", "died": "x",
          "conf_rejected": "x", "conf_refused": "x", "sustained": "x",
          "vetoed": "x", "not_ratified": "x",
          "study": "s", "study_report": "s",
          "tabled": "h", "recommitted": "h", "referred": "h",
          "nonconcurred": "h"}
# The chamber carried the bill on at this line.
J_PASSING = {"passed", "adopted", "referred"}


# A LAW IN EFFECT IN STAGES, IN ONE LINE (the audit of 25 October 2026, S7).
# HB 282 of 2025's Law stop was 117 words of section numbers -- twelve parts,
# "sections 4, 8, 9 and 43 on Jan 1, 2026, sections 2, 10, 18 and 44 on Jul
# 1, 2026, ..." -- in How it got here and in the rail's label alike. Where a
# law takes effect in three parts or more and every part has its day, the
# page says "Chapter 142, in effect in stages from Jul 1, 2025 to Jul 1,
# 2034"; which section takes effect when is the chaptered text's own last
# section, on the Bill Text tab. Two parts read as a line and are left as
# they are ("section 3 on Jan 1, 2027, the rest on Aug 1, 2026"), and so is
# a part dated only "as section 3 provides": the span would leave it out.
STAGES_FROM = 3
_STAGE_END = re.compile(r"\s+(?:on\s+(?P<mon>" + "|".join(J_MON) + r")\s+(?P<day>\d{1,2}),\s+"
                        r"(?P<year>\d{4})|as\s+section\s+\d{1,3}\s+provides)(?:,\s*|\s*$)")


def law_in_stages(chapter, parts):
    """"Chapter 142, in effect in stages from Jul 1, 2025 to Jul 1, 2034" for
    a law's parts as the Law step states them (_j_effective_parts,
    _j_chaptered), or "" where they are fewer than STAGES_FROM, any part has
    no day of its own, or the words do not read as parts to their end."""
    days, pos = [], 0
    for m in _STAGE_END.finditer(parts or ""):
        if not m.group("mon"):
            return ""
        try:
            days.append(_date(int(m.group("year")), J_MON.index(m.group("mon")) + 1,
                              int(m.group("day"))))
        except ValueError:
            return ""
        pos = m.end()
    if len(days) < STAGES_FROM or pos != len(parts) or min(days) == max(days):
        return ""
    return (f"Chapter {chapter}, in effect in stages from "
            f"{_j_prose_date(min(days).isoformat())} to {_j_prose_date(max(days).isoformat())}")


def law_line_dated(step):
    """THE LAW LINE'S DAY IS IN THE DATE COLUMN, as every other line's is (the
    owner, 10 November 2026: "in effect Jul 1, 2025" sat in the words of HB 1's
    line with its date empty). `shown` says "Chapter 140, in effect" beside
    it; `text` keeps the day in its words, for the Laws pages. A law in parts
    or stages has no one day and stays as it was. Called before the step's
    `short` and `effective` are dropped from the stored journey."""
    if (step.get("act") == "law" and step.get("effective") and not step.get("date")
            and not step.get("shown") and step.get("short")):
        step["date"] = step["effective"]
        step["shown"] = f"{step['short']}, in effect"
    return step


def _j_prose_date(iso, year=True):
    """"2026-01-11" -> "Jan 11, 2026", or "Jan 11" without the year:
    shell.date_words, month first like every date the site writes."""
    try:
        _date(*(int(x) for x in iso.split("-")))
    except (AttributeError, TypeError, ValueError):
        return ""
    return _shell.date_words(iso, "medium" if year else "short")


def _j_iso(m, d, y):
    y = int(y)
    y += (1900 if y > 50 else 2000) if y < 100 else 0
    try:
        return _date(y, int(m), int(d)).isoformat()
    except ValueError:
        return ""


def _j_outcome(seg, at):
    """True, False or None: what became of the motion a clause names -- the
    first outcome after it, else the last before it."""
    toks = sorted((m.start(), val) for rx, val in
                  ((J_YES_CODE, True), (J_NO_CODE, False),
                   (J_YES_WORD, True), (J_NO_WORD, False))
                  for m in rx.finditer(seg))
    if not toks:
        return None
    after = [t for t in toks if t[0] >= at]
    return (after[0] if after else toks[-1])[1]


def _j_motions(seg):
    """[(act, match)]: every motion a clause names, in the order it names
    them. Where two readings claim the same words -- "Non-Concurs" is a
    refusal, not a concurrence; "Inexpedient to Legislate, Senate Rule 3-23"
    is the rule, not a vote -- the one tried first keeps them.

    An amendment's own vote is ("amendment", None): "COMM AM, AA VV"."""
    got = []
    for act, rx in J_ACTS:
        for m in rx.finditer(seg):
            if any(m.start() < g.end() + 2 and m.end() > g.start() - 6
                   for _a, g in got):
                continue
            got.append((act, m))
    got.sort(key=lambda x: x[1].start())
    if J_AMEND_SUBJ.search(seg) and all(a == "passed" for a, _m in got) and not re.search(
            r"\bOT\s?3\s?rd?g\b|ought\s+to\s+pass|\bpassed\b|third\s+reading", seg, re.I):
        return [("amendment", None)]
    return got


# THE CLAUSE READERS KEEP WHAT THEY READ (16 October 2026,
# private/SITE_DATA_PROFILE.md, P2). Over the site data step _j_segments was
# asked 1.3 million times and _j_act 2.4 million, nearly always of a line or a
# clause already read: _j_rows splits the row before each row again, and
# journey splits every row once more. Each _j_act tried every J_ACTS pattern
# over its clause, which made _j_motions the step's largest cost of its own.
# So each of these keeps its answer by its argument, through
# functools.lru_cache, whose __wrapped__ is the same reading done afresh.
# THE MEMO IS RIGHT ONLY WHILE THEY READ THEIR STRING ARGUMENT ALONE. Today
# they read nothing but it and this module's compiled patterns. An edit that
# made one of them read a term, a bill, a date or anything a caller sets would
# hand every later caller the first answer, with no error, so such a reader
# must lose its lru_cache. preflight's _journey_clauses_kept holds the kept
# answers to the fresh ones.
@functools.lru_cache(maxsize=None)
def _j_act(seg):
    """The first motion a clause names, or None."""
    got = _j_motions(seg)
    return got[0][0] if got else None


@functools.lru_cache(maxsize=None)
def _j_has_outcome(seg):
    return bool(J_YES_CODE.search(seg) or J_NO_CODE.search(seg)
                or J_YES_WORD.search(seg) or J_NO_WORD.search(seg))


# A clause that is nothing but a vote and its outcome: "RC 15Y-8N, Adopted".
J_OUTCOME_ONLY = re.compile(
    r"^\s*(?:(?:RC|DV|DIV|Division|VV)\b[^,;A-Za-z]*(?:[YN]\b[^,;A-Za-z]*)*,?\s*)*"
    r"(?:adopted|failed|MA|MF|ML|AA|AF|AL)\b", re.I)


# "1427s; 1851s; and 1925s", "1807s;1824s;and 1932s", "#1735h; #1843h".
J_AMEND_LIST = re.compile(r"(?<=\d[hse]);(?=\s*(?:and\s+)?#?(?:\d{4}-)?\d{3,4}[hse]\b)")


def _j_segments(raw):
    """The clauses of one docket line (_j_clauses), as a list of the
    caller's own: one a caller changes cannot change what the next caller
    is given, because the kept answer is a tuple."""
    return list(_j_clauses(raw))


@functools.lru_cache(maxsize=None)
def _j_clauses(raw):
    """The clauses of one docket line, as a tuple. A motion whose outcome the
    clerk put in the next clause is one clause: "Sen. Gray Moved Nonconcur
    with the House Amendment; Requests C of C, MA, VV", "Conference Committee
    Report # 2026-2114c; RC 15Y-8N, Adopted".

    A SEMICOLON IN A LIST OF AMENDMENTS IS NOT THE END OF A CLAUSE. "House
    Non-Concurs with Senate Amendment 1427s; 1851s; 1898s; and 1925s (Rep.
    Kurk): MA RC 180-163" (HB 1636 of 2018) left "House Non-Concurs with
    Senate Amendment 1427s" to stand alone, which read as the House refusing
    with no count -- and so did the motion before it, which failed."""
    out = []
    raw = J_AMEND_LIST.sub(",", raw or "")
    for p in (y.strip() for x in raw.split(";")
              for y in _j_unsuspend(x.strip()).split(";")):
        if not p:
            continue
        # Not a floor amendment's own vote after a motion that was only
        # made: "Rep Goley moved OTP/AM; Rep Goley Fl Am{3930}, AA
        # RC(190-152)" (HB 1475 of 2000) is the amendment carrying, not the
        # bill -- which was killed that morning.
        nxt = _j_act(p)
        # AN OUTCOME ALONE IS THE OUTCOME OF THE CLAUSE BEFORE IT, whatever
        # that clause was about: "Enrolled Bill Amendment{2230}; Adopted" is
        # the enrolled bill amendment adopted (HB 1243 of 2006), and "Enrolled
        # Bill; Adopted, SJ 14" the enrolment (HB 235 of 2000). Read apart, the
        # bare "Adopted" was a committee report adopted -- a kill, on two bills
        # that became law.
        # BUT NOT A RECONSIDERATION'S. "Re-Referred to Res, Rec & Dev
        # committee RC(158-154); Rep Royce moved to reconsider, ML
        # RC(156-157)" (SB 135 of 1999, read whole since 1 October from the
        # two rows the database cut it into) is the bill sent back and a
        # motion to reconsider that failed, not a re-referral that failed.
        if (out and not _j_has_outcome(out[-1]) and _j_has_outcome(p)
                and not re.search(r"withdr[ae]w", out[-1], re.I)
                and not (J_RECONSIDER.search(p) and not J_RECONSIDER.search(out[-1])) and (
                (_j_act(out[-1]) and (
                    nxt is None or J_OUTCOME_ONLY.match(p)
                    or (nxt == "amendment" and _j_act(out[-1]) == "conference")))
                or (J_TAKES_OUTCOME.search(out[-1]) and J_OUTCOME_ONLY.match(p)))):
            out[-1] = f"{out[-1]}; {p}"
        # Across a clause that is neither motion nor outcome: "Sen. Prescott
        # moved Nonconcur with House Amendment #1958h, NT; Requests C of C;
        # MA VV" (SB 255 of 2015) is the Senate refusing the amendment.
        elif (len(out) > 1 and J_OUTCOME_ONLY.match(p) and not _j_act(out[-1])
              and not _j_has_outcome(out[-1]) and _j_act(out[-2])
              and not _j_has_outcome(out[-2])):
            out[-2:] = [f"{out[-2]}; {out[-1]}; {p}"]
        else:
            out.append(p)
    return tuple(out)


def _j_tally(seg, at=0):
    """("RC"|"DV"|"VV", yeas, nays): the vote the clause records, preferring
    one after the motion's own words."""
    ms = list(J_TALLY.finditer(seg))
    m = next((x for x in ms if x.start() >= at), ms[-1] if ms and not at else None)
    if m:
        k = m.group("k").upper()
        return ("RC" if k.startswith(("RC", "ROLL")) else "DV",
                int(m.group("y")), int(m.group("n")))
    if J_VOICE.search(seg):
        return ("VV", None, None)
    if J_RC_BARE.search(seg):
        return ("RC", None, None)
    return ("", None, None)


def _j_roll_call(rcs, date, body, vote, said):
    """The roll call a docket line's tally names: (vote, passed or None).

    The ballots are the headline wherever the docket's count and the roll
    call's differ (16 September), and what the vote decided is the roll
    call's `passed`, which rollcall_outcomes.py reads from the docket and the
    Journals -- SB 82 of 2005, "Ought to Pass with Amendment, RC 10Y-14N, MA",
    is a motion the Journal records as failing."""
    kind, y, n = vote
    if kind != "RC":
        return vote, None
    mine = [r for r in (rcs or []) if r.get("date") == date and r.get("body") == body]
    if y is not None:
        same = [r for r in mine
                if (r.get("yeas"), r.get("nays")) == (y, n)
                or (r.get("yeas_stated"), r.get("nays_stated")) == (y, n)]
        # Two roll calls of a day can share a count: CACR 20 of 2018 failed
        # to pass 13-11 and was laid on the table 13-11 the same morning.
        # The one whose outcome is the line's own is this line's.
        r = next((r for r in same if said is not None
                  and bool(r.get("passed")) == bool(said)), same[0] if same else None)
        if r:
            return ("RC", r.get("yeas"), r.get("nays")), r.get("passed")
        return vote, None
    cand = [r for r in mine if not r.get("procedural")
            and bool(r.get("passed")) == bool(said)]
    if said is not None and len(cand) == 1 and cand[0].get("yeas") is not None:
        return ("RC", cand[0]["yeas"], cand[0]["nays"]), cand[0].get("passed")
    return vote, None


def _j_decide(seg, bid, rcs=(), date="", body=""):
    """One clause, read: a dict of what it decided, "amended" for an amendment
    the chamber adopted, or None."""
    if J_SIGNED.search(seg) and not re.search(r"overrid", seg, re.I):
        # "{LSR 0155, HB 154, CH. 183, 1997 SIGNED BY GOV 6/18/97}" is on
        # 1996's HB 1179 and is about another bill's signature.
        if any(re.sub(r"\s+", "", m.group(0)).upper() != bid
               for m in J_OTHER_BILL.finditer(seg)):
            return None
        return {"act": "signed"}
    if J_VETOED.search(seg) and not re.search(r"overrid|sustain", seg, re.I):
        return {"act": "vetoed"}
    if J_UNSIGNED.search(seg) and not re.search(r"overrid", seg, re.I):
        return {"act": "unsigned"}
    # A motion "not voted on" decided nothing, and what the clause says after
    # it may have: "Ought to Pass (not voted on), Sen. Larsen Moved Laid on
    # Table, MA, VV" (HB 101 of 2001) is the Senate laying the bill on the
    # table.
    seg = J_NOT_VOTED.sub("", seg)
    if not seg.strip() or J_SKIP.search(seg):
        return None
    on_table = bool(J_ON_THE_TABLE.search(seg))
    seg = J_ON_THE_TABLE.sub(" ", seg)
    motions = _j_motions(seg)
    if motions and motions[0][0] == "amendment":
        return "amended" if _j_outcome(seg, 0) else None
    # THE LAST MOTION THAT DECIDED SOMETHING. The oldest lines put a
    # sitting's motions in one clause: "REP HATCH SUBST ITL, ML RC
    # (149-201), PASSED/ADOPTED VV" (HB 18 of 1989) is a kill that failed
    # and then the bill passing. Each motion is read up to the next.
    got, since = None, 0
    for i, (act, m) in enumerate(motions):
        end = motions[i + 1][1].start() if i + 1 < len(motions) else len(seg)
        begin = motions[i - 1][1].end() if i else 0
        one = _j_motion(seg, act, m, begin, end, len(motions) == 1,
                        bid, (rcs, date, body), since)
        if one is not None:
            got = one
            if one["act"] == "failed":
                since = end
    # Killing every bill still on the table is how a chamber of the 1990s
    # and 2000s ended the ones it had tabled: "Reps. O'Neil and Craig move
    # ITL all bills on table, MA, VV" (HB 646 of 2006) -- a bill that died
    # on the table, as the Senate's Rule 3-23 does it now.
    if got and on_table and got["act"] == "killed":
        got["act"], got["rule"] = "died", ""
    return got


def _j_motion(seg, act, m, begin, end, alone, bid="", ctx=((), "", ""), since=0):
    """What one motion in a clause decided, or None: read from the clause
    between its own words and the next motion's. `since` is where the clause
    starts to be about the motion that carried, after one that failed."""
    at = m.start()
    part = seg[at:end]
    if act == "accede" and not re.search(r"refus", seg, re.I):
        return None
    # "ADOPTED VV" is how the 1990s record a resolution passing -- and, on a
    # bill, a committee's REPORT being adopted, whatever it recommended.
    # Where no row says which (_j_rows joins the one that does), it says
    # nothing about the bill.
    # Not where the clause says the bill was read a third time: "Adopted and
    # read a 3rd time MA VV 01/05/22" is the House passing HB 1650 of 2022.
    bare = (act == "passed" and not bill_prefix(bid).endswith("R") and re.match(
        r"\s*(?:[HS]\s+)?adopt", m.group(0), re.I)
        and not re.search(r"\bread\s+(?:a\s+)?(?:3rd|third)\s+time", seg, re.I))
    # "INTRODUCED AND ADOPTED" on a bill is no committee's report: in the
    # Senate of the 1990s, under a suspension of the rules, it is the bill
    # passing ("SEN DELAHUNTY SUSP RULES TO CONSIDER, MA 2/3VV; INTRODUCED AND
    # ADOPTED VV", HB 27 of 1993, signed a week later); in the House of
    # 2019, "Introduced and Adopted (without objection)" ahead of "Ought to
    # Pass : MA RC 316-40", the motion to introduce it. So it is a passage
    # that a passage of the same day replaces, tally and all (_j_settle).
    intro_adopt = (act == "passed" and not bill_prefix(bid).endswith("R") and re.match(
        r"\s*(?:[HS]\s+)?introduced\s+and\s+adopt", m.group(0), re.I))
    said = _j_outcome(part, 0)
    if said is None and alone:
        said = _j_outcome(seg, at)
    vote = _j_tally(part, 0)
    if not vote[0] and alone:
        vote = _j_tally(seg, at)
    vote, counted = _j_roll_call(ctx[0], ctx[1], ctx[2], vote, said)
    if counted is not None:
        said = counted
    elif act != "veto_vote" and vote[1] is not None:
        # A majority question, where the clerk's count is all there is: a
        # line with no outcome is decided by it ("Inexpedient to Legislate,
        # Division 14Y-10N", HB 327 of 2007), and "MA" on fewer yeas than
        # nays is the count's, as rollcall_outcomes rules for a roll call.
        if said is None or (said and vote[1] <= vote[2]):
            said = vote[1] > vote[2]
    if act == "veto_vote":
        if said is None and vote[1] is not None:
            y, n = vote[1], vote[2]
            said = y >= -(-2 * (y + n) // 3)
        if said is None:
            return None
        return {"act": "override" if said else "sustained", "vote": vote}
    if act == "died":
        rule = " ".join(w.capitalize() if w.isalpha() else w
                        for w in (m.group("rule") or m.group("rule2") or "").split())
        return {"act": "died", "vote": ("", None, None), "rule": rule,
                "adjourned": bool(re.search(r"adjourn", seg, re.I))}
    # No code at all, on a line of the 1990s, is the clerk recording what was
    # done: "SENATE CONC WITH HOUSE AM", "LAID ON THE TABLE", "RE-REFERRED TO
    # HEALTH". Not where a member only MOVED it: "REP MUSLER MOVED CONC WITH
    # SEN AM; LAID ON THE TABLE" (HB 119 of 1993) concurred two days later.
    moved = re.search(r"\bmov(?:ed|es?)\b|\bmotion\b", seg[begin:end], re.I)
    if (said is None and not moved
            and (act in ("concur", "nonconcur") or J_DONE_VERB.search(seg[begin:end]))):
        said = True
    # "Sen. Gannon Moved Laid on Table, 05/07/2026", and nothing after it
    # in the Senate: the clerk wrote the motion and not the vote. Kept only
    # where it is the chamber's last word (journey() drops it otherwise);
    # both such bills in the record, HB 1217 and HB 1544 of 2026, are on
    # the table by the General Court's own status.
    if said is None and moved and act == "tabled":
        return {"act": "tabled", "vote": ("", None, None), "unanswered": True}
    if said is None and not (act == "conference"
                             and re.search(r"\bnot\s+accepted\b", seg[at:end], re.I)):
        return None
    out = {"vote": vote}
    # MORE YEAS THAN NAYS, AND IT FAILED: it needed more than a majority, and
    # the clerk says how much -- "MF RC 184-157 Lacking Necessary
    # Three-Fifths Vote" (CACR 4 of 2026). "Failed to pass, 184–157" read as
    # 184 voting it down; the line says what it fell short of.
    frac = re.search(r"\b(?:two[\s-]*thirds?|2\s*/\s*3)|\b(?:three[\s-]*fifths?|3\s*/\s*5)",
                     seg, re.I)
    if not said and frac and vote[1] is not None and vote[1] > vote[2]:
        out["short_of"] = ("three fifths" if re.search(r"fifth|5", frac.group(0), re.I)
                           else "two thirds")
    if bare:
        # Its committee's report adopted: journey() reads what the report
        # recommended. HB 33 of 2007, "Adopted VV", passed the House.
        if not said:
            return None
        out["act"] = "report_adopted"
        return out
    if act == "conference":
        if re.search(r"\btable\b", part, re.I):
            return None
        # A REPORT THE CHAMBER DID NOT ACCEPT, with no vote: "Conference
        # Committee Report Not Accepted by House pursuant to House Rule 49(j)"
        # (SB 305 of 2016). The line says that much and no more -- nobody
        # voted it down.
        if re.search(r"\bnot\s+accepted\b", part, re.I):
            return {"act": "conf_rejected", "vote": ("", None, None), "unaccepted": True}
        # A motion NOT to adopt, carried, is the report rejected: "Sen.
        # Pignatelli Moved Non Adopt Conference Committee Report RC 17Y-7N,
        # Non Adopt" (SB 69 of 2001) read as the Senate adopting it 17-7.
        # So is "REFUSED TO ADOPT CONF COMM REPT, REQ NEW CONF COMM REPORT,
        # SEN HEATH MA VV" (HB 352 of 1991).
        if re.search(r"\bnon[-\s]?adopt|\bnot\s+(?:to\s+)?adopt(?!ed)|\bmov\w*\s+(?:to\s+)?reject"
                     r"|\brefus\w*\s+to\s+adopt", seg[:end], re.I):
            # Unless nobody moved it and the words are the outcome, after a
            # count that lost: "Conference Committee Report RC 11Y-13N, Non
            # Adopt" (SB 95 of 2001) is the report voted down, 11-13.
            if not said and re.search(r"\bmov\w*|\bmotion\b|\brefus", seg[:end], re.I):
                return None
            out["act"] = "conf_rejected"
            return out
        out["act"] = "conf_adopted" if said else "conf_rejected"
    elif act == "accede":
        if not said:
            return None
        out["act"] = "conf_refused"
    elif act == "nonconcur":
        if not said:
            return None
        out["act"] = "nonconcurred"
        out["conf"] = bool(re.search(r"\bc\s?of\s?c\b|cofc|conf(?:erence)?\b|"
                                     r"\breq\w*", seg[at:], re.I))
    elif act == "concur":
        # A motion to concur that failed is a refusal (HB 1215 of 2024,
        # 172-180), which is what concurrence_outcome reads it as too.
        out["act"] = "concurred" if said else "nonconcurred"
    elif act == "passed":
        if not said:
            out["act"] = "failed"
        else:
            out["act"] = "passed"
            if intro_adopt:
                out["intro_adopt"] = True
            # Not the words of a motion before it that failed: "Ought to Pass
            # W/Amendment, {1683}, RC 6Y-16N, AF, Ought to Pass, MA, VV,
            # OT3rdg, RC 22Y-1N, MA" (HB 546 of 1999) is the bill passing
            # without the amendment, and read "Passed with an amendment".
            out["amended"] = bool(J_AMENDED.search(seg[since:end])
                                  or J_AMEND_ADOPTED.search(seg))
            # "Passed by Third Reading Resolution" (HB 118 of 2005, the day
            # after "Ought to Pass, RC 16Y-8N, MA") is the passage it names,
            # read a third time, and not a second one.
            out["third"] = bool(J_THIRD.search(seg)) and not re.search(
                r"ought\s+to\s+pass|\bOTP", seg, re.I)
            to = J_REFERRED_TO.search(part)
            if to:
                out["act"] = "referred"
                out["to"] = to.group("c").strip()
    elif not said:
        return None
    else:
        out["act"] = act
    return out


def _j_second_committee(name):
    """The committee a chamber sent a bill on to after approving it: the
    money committees by their full names, any other by its own, written out
    the way the rest of the site writes a committee."""
    name = (name or "").strip(" ,.")
    for rx, full in J_SECOND_COMMITTEE:
        if rx.search(name):
            return full
    # "SUSP RULES TO REF TO 2ND COMM": the docket does not say which.
    if re.match(r"(?:a\s+)?(?:2nd|second)\s+comm", name, re.I):
        return "a second committee"
    if not re.search(r"[A-Za-z]{3}", name):
        return ""
    try:
        import referrals
        return referrals.AMP.sub(" and ", names.committee(
            referrals.expand(referrals.clean(name)))) or name
    except Exception:                                       # pragma: no cover
        return name


def _j_vote_words(vote):
    """(" on a voice vote" | ", 217–156" | "", "voice vote" | "217–156" | "")."""
    kind, y, n = vote or ("", None, None)
    if y is not None:
        return f", {y}–{n}", f"{y}–{n}"
    if kind == "VV":
        return " on a voice vote", "voice vote"
    if kind == "RC":
        return " on a roll call", "roll call"
    return "", ""


def _j_words(st, bid):
    """The line's words, and the rail's one or two."""
    act, body = st["act"], st["body"]
    other = {"H": "Senate", "S": "House"}.get(body, "")
    long_, short = _j_vote_words(st.get("vote"))
    if st.get("consent") and (long_.startswith(",") or not long_):
        long_ = " on the consent calendar" + long_
    pre = bill_prefix(bid)
    # A bill of intent is one chamber's and is no resolution: its docket's
    # word is PASSED.
    resolution = ((pre in SINGLE_CHAMBER and pre != BILL_OF_INTENT)
                  or (pre in NO_GOVERNOR and pre != "CACR"))
    if act in ("passed", "adopted"):
        am = st.get("amended")
        text = ("Adopted" if resolution else "Passed") + (" with an amendment" if am else "")
        return text + long_, ", ".join(x for x in (short, "amended" if am else "") if x)
    if act == "referred":
        to = _j_second_committee(st.get("to"))
        money = to in {full for _rx, full in J_SECOND_COMMITTEE}
        return (("Approved with an amendment" if st.get("amended") else "Approved")
                + f" and sent to {to or 'another committee'}" + long_,
                f"to {to}" if money else "to committee")
    if act == "died":
        # The docket's words, not the status chip's: the rule killed it.
        rule = st.get("rule") or ""
        if not rule:
            return "Killed with the other bills left on the table" + long_, "killed"
        if rule.lower().startswith("rule"):
            return f"Died on the table under {rule}", "died on table"
        return (f"Killed under {rule}"
                + (", still on the table" if rule == "Senate Rule 3-23" else "")
                + (" at adjournment" if st.get("adjourned") else ""), "killed")
    words = {
        "failed": ("Not adopted" if resolution else "Failed to pass", "failed"),
        "killed": ("Killed", "killed"),
        "study": ("Sent to interim study", "interim study"),
        "postponed": ("Indefinitely postponed", "postponed"),
        "tabled": ("Laid on the table", "tabled"),
        "recommitted": ("Sent back to committee", "sent back"),
        "concurred": (f"Agreed to the {other}'s amendment", "agreed"),
        "nonconcurred": (f"Refused the {other}'s amendment"
                         + (" and asked for a committee of conference"
                            if st.get("conf") else ""), "refused amendment"),
        "conf_adopted": ("Adopted the conference report", "conference report"),
        "conf_rejected": (("Did not accept the conference report", "report not accepted")
                          if st.get("unaccepted")
                          else ("Rejected the conference report", "report rejected")),
        "conf_refused": ("Refused a committee of conference", "refused conference"),
        "override": ("Veto overridden", "overridden"),
        "sustained": ("Veto sustained", "sustained"),
    }
    text, word = words.get(act, (act, act))
    # A VOTE TO OVERRIDE IS COUNTED FOR THE OVERRIDE. "Veto Sustained
    # 12/17/2025: RC 176-175 Lacking Necessary Two-Thirds Vote" (HB 358 of
    # 2025) is 176 members voting to override, and "Veto sustained, 176–175"
    # read as 176 voting to sustain.
    kind, y, n = st.get("vote") or ("", None, None)
    if act == "sustained" and y is not None:
        long_ = f", {y}–{n} to override" + (", short of two thirds" if y > n else "")
    elif st.get("short_of"):
        long_ += f", short of {st['short_of']}"
    return text + long_, (f"{word}, {short}" if short and short != "voice vote"
                          and act in ("killed", "failed") else word)


def _j_effective(*lines):
    """The one date a law took effect, or "" where its lines give none or
    several. `lines` are the governor's row, the rows that carry it on, and
    the chapter's line: all of them are read, and any sign of a second date
    -- a section, a remainder, "as provided", a starred date -- is enough to
    state none."""
    lines = [x for x in lines if x]
    if any(J_EFF_SEVERAL.search(x) for x in lines):
        return ""
    # Each line's dates after its own "eff": HB 1256 of 2026's "Law Without
    # Signature 06/05/2026; Chapter 128; eff.Enacted in accordance with
    # Article 44" states no effective date at all.
    #
    # OR THE DAY STRAIGHT AFTER THE CHAPTER, where the line has no "eff":
    # "Signed by Governor Ayotte 06/02/2025; Chapter 59; 08/01/2025" (HB 227
    # of 2025, and HB 2, HB 153 and HB 230), which the database's
    # EffectiveDate agrees with on all four.
    days = {_j_iso(*d.groups()) for x in lines
            for m in [J_EFF_ANY.search(x) or J_CHAPTER_THEN_DAY.search(x)] if m
            for d in J_DAY.finditer(x, m.start())} - {""}
    return days.pop() if len(days) == 1 else ""


# The day straight after the chapter, where the line has no "eff" word: the
# row ends there, or a journal's citation follows.
J_CHAPTER_THEN_DAY = re.compile(r"\bchapter\s*\d+\s*;\s*(?=\d{1,2}/\d{1,2}/\d{2,4}\s*"
                                r"(?:$|\s+[HS][JC]\b))", re.I)

# A LAW WITH MORE THAN ONE EFFECTIVE DATE, PART BY PART (the audit of 7
# October 2026, cause 12). "eff. I. Sec 3 eff 01/01/2032 II. Rem eff
# 09/01/2026" (HB 1300 of 2026), or the Senate's rows of their own, "I.
# Section 24 Effective 07/01/2031" and "II. Remainder Effective 07/01/2026"
# (SB 56): 92 of the term's 649 laws stated no date at all, because a law in
# effect on several dates had no one date to state. Each part is read only
# where it names what it covers and gives one date, or the section that
# provides its date; anything else -- "I Sec 1-3-5", a line the docket cut
# short, "eff.06/05/20256" -- states none, as before. The reason for the old
# rule stands: no date is stated that the line does not give for that part.
#
# PARTS PAST VIII (the effective dates review of 8 October 2026). HB 282 of
# 2025 runs to "XII. Rem eff 7/1/25"; read to VIII, part VIII ran on into
# four more parts and their dates, and the law stated none. Numbered to XX.
J_EFF_PART = re.compile(r"(?:(?<=[\s.;,])|^)(?:XX|XIX|XIV|XV?I{0,3}|IX|IV|VI{0,3}|I{1,3})"
                        r"\s*\.?\s*(?=(?:Secs?|Sections?|Rem\w*|RSA)\b)", re.I)
J_EFF_PROVIDED = re.compile(r"\bas\s+(?:prov(?:ided)?\.?\s+(?:in\s+)?|in\s+)?"
                            r"sec(?:tion)?s?\.?\s*(\d+)\b"
                            r"|\beff\.?\s+prov(?:ided)?\.?\s+(?:in\s+)?sec(?:tion)?\.?\s*(\d+)",
                            re.I)
# What a part covers ends where its date begins -- a whole date, not a
# figure and a slash: "I. RSA 193:13/ I-X as inserted by Sec. 1 Eff:
# 07/01/2021" (HB 1558 of 2020) was labelled "RSA 193:".
J_EFF_WHAT = re.compile(r"^\s*(?P<what>(?:Secs?|Sections?)\.?\s*(?P<nums>[\dI][\d\s,&+.\-and]*?)"
                        r"|Rem\w*\.?|RSA\s+.+?)\s*(?:of\s+this\s+act\s+)?"
                        r"(?=\beff|\bshall\b|\bas\s|\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2}|$)", re.I)


def _j_sections(s):
    """"1.2.5.6" -> "sections 1, 2, 5 and 6", "5-8" -> "sections 5 to 8",
    "3" -> "section 3"; "" where it is not plainly a list of numbers."""
    s = re.sub(r"\band\b", "&", s, flags=re.I).strip(" .")
    # A RANGE WRITTEN WITH SPACES IS A RANGE in a list too: "Sec 26 27 - 33
    # 35 - 38 & 52" (HB 282 of 2025), "Sections 26, 27 through 33, 35
    # through 38, and 52" in its chaptered text. "1-3-5" stays unread: one
    # range or two numbers, the line cannot say which (HB 655 of 2025).
    s = re.sub(r"\s*-\s*", "-", s)
    # "SEC I" IS SECTION 1. An act's sections are numbered 1, 2, 3; the clerk's
    # capital I for the figure 1, alone after "Sec", is section 1 in every
    # line that writes it -- "I. Sec I eff 10/13/2026" (HB 1584 of 2026,
    # "I. Section 1 effective October 13, 2026" in its chaptered text), and
    # "Sec.I" and "SecI" on SB 50 and SB 97 of 2007 and SB 204 of 2009, each
    # "Section 1" in its own. Alone only: "Sec I-3" or "Sec II" is not read.
    if s == "I":
        s = "1"
    if re.fullmatch(r"\d+\s*-\s*\d+", s):
        a, b = re.split(r"\s*-\s*", s)
        return f"sections {a} to {b}"
    nums = [p for p in re.split(r"\s*[&+,.]\s*|\s+", s) if p]
    if not nums or not all(re.fullmatch(r"\d+(?:-\d+)?", p) for p in nums):
        return ""
    if len(nums) == 1 and "-" not in nums[0]:
        return f"section {nums[0]}"
    nums = [p.replace("-", " to ") for p in nums]
    return "sections " + (", ".join(nums[:-1]) + " and " + nums[-1] if len(nums) > 1
                          else nums[0])


def _j_effective_parts(*lines):
    """A law in effect on several dates, part by part: "section 3 on 1 Jan
    2032, the rest on 1 Sep 2026", or "" where any part does not say plainly
    what it covers and when. `lines` are the governor's row, the rows that
    carry it on and the chapter's line, each distinct line read once."""
    seen = list(dict.fromkeys(re.sub(r"\s+", " ", x).strip()
                              for x in lines if x and x.strip()))
    # A LINE CUT SHORT IS THE LINE IT BEGINS. chapters.json keeps the
    # chapter's line to its first 200 characters, and HB 282 of 2025's ends
    # "V. Sec 13 21 &" where the governor's row goes on to part XII: read
    # beside the row, the cut part stated no date and took every other part
    # with it. A line that is the start of another line read is that line.
    seen = [x for x in seen if not any(y != x and y.startswith(x) for y in seen)]
    tails = []
    for x in seen:
        m = re.search(r"\bchapter\s*\d+\s*[;,.]?", x, re.I)
        tails.append(x[m.end():] if m else x)
    pieces = J_EFF_PART.split(" ".join(tails))
    if len(pieces) < 3:
        return ""
    # A DATE BEFORE THE FIRST PART READ IS A PART NOT READ. "eff. I. Sec4 eff
    # 6/24/22 II. Sec 5 and 6 eff 7/1/25 III Rem eff 7/1/22" (HB 481 of
    # 2022): "Sec4" is no part this reads, and section 4, in effect on 24
    # June, would have been stated as part of "the rest", on 1 July.
    m = J_EFF_ANY.search(pieces[0])
    if m and J_DAY.search(pieces[0], m.start()):
        return ""
    out = []
    for p in pieces[1:]:
        p = re.sub(r"\s+(?:HJ|SJ|HC|SC)\s*\d+.*$", "", p).strip()
        s = J_EFF_WHAT.match(p)
        if not s:
            return ""
        what = s.group("what")
        if re.match(r"rem", what, re.I):
            label = "the rest"
        elif re.match(r"RSA", what, re.I):
            label = re.sub(r"\s+", " ", what).strip(" .")
            # A part that names an RSA and then more sections of the act --
            # "IV. RSA 485-A:17,II(b) as inserted by Section 30 and Sections
            # 50-51 Eff 01/01/08" (HB 2 of 2007) -- would lose the sections
            # from its label and leave them to "the rest": states none.
            if re.search(r"\band\s+sec", p[s.end():], re.I):
                return ""
        else:
            label = _j_sections(s.group("nums") or "")
            if not label:
                return ""
        rest = p[s.end():]
        days = [d for d in (_j_iso(*x.groups()) for x in J_DAY.finditer(rest)) if d]
        prov = J_EFF_PROVIDED.search(rest)
        if len(days) == 1 and not prov:
            out.append((label, "on " + _j_prose_date(days[0])))
        elif not days and prov:
            out.append((label, "as section " + (prov.group(1) or prov.group(2))
                        + " provides"))
        else:
            return ""
    out = list(dict.fromkeys(out))
    # ONE PART IS NOT PARTS. A law in effect in parts has two at least, so a
    # single part read is half of what the law says: HB 25 of 2023's row
    # names part I, section 24 on 30 June 2023, and nothing of the remainder
    # its chaptered text puts on 1 July; and a part read twice, by a row and
    # a copy of it the reader does not know for one, is still one part.
    if len(out) < 2 or len({w for w, _ in out}) != len(out):
        return ""
    out.sort(key=lambda x: x[0] == "the rest")
    return ", ".join(f"{w} {d}" for w, d in out)


def _j_act_sections(secs):
    """The act's sections a part of a chaptered law covers, in the words
    _j_sections gives the docket's: {3} "section 3", {1, 2, 5} "sections 1, 2
    and 5", {5, 6, 7, 8} "sections 5 to 8" -- a run of three or more is a
    range, as the chaptered text writes "Sections 26, 27 through 33" (HB 282
    of 2025); "" where there are none."""
    nums, items, i = sorted(secs or ()), [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        items += [f"{nums[i]} to {nums[j]}"] if j - i >= 2 else [str(n) for n in nums[i:j + 1]]
        i = j + 1
    if not items:
        return ""
    if len(items) == 1 and " to " not in items[0]:
        return f"section {items[0]}"
    return "sections " + (", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1
                          else items[0])


def _j_chaptered(body):
    """When a law takes effect as its chaptered text says it, in the Law
    step's words: (the one day, "") for the act as a whole, ("", "section 3 on
    Aug 19, 2027, the rest on Oct 18, 2026") in parts, or None where the text
    has no Effective Date lines or one law_effect does not read.

    The same rules as the docket's parts (_j_effective_parts): one part that
    is not the whole act is not enough to state, a part named twice states
    none, and the rest comes last."""
    parts = LE.chaptered_parts(body) if body else None
    if not parts:
        return None
    if len(parts) == 1:
        p = parts[0]
        return (p.day.isoformat(), "") if p.rest and p.day else None
    # A part that names a statute is said in the law's own words, its
    # paragraph and where it was inserted with it -- "RSA 654:12 VI as
    # inserted by section 5" (HB 464 of 2025), not "RSA 654:12" -- and the
    # act's sections named beside it after it: "RSA 597:2-b, I-a and sections
    # 16 and 17" (HB 318 of 2024). One line a part, in order.
    lines = LE.trailer_lines(body) or []
    out = []
    for i, p in enumerate(parts):
        if p.rest:
            label = "the rest"
        elif p.addr:
            words = LE.part_words(lines[i]) if len(lines) == len(parts) else ""
            m = LE.AND_SECTIONS.search(words)
            label = ((words[:m.start()] if m else words) or f"RSA {p.addr}") + (
                f" and {_j_act_sections(p.secs)}" if p.secs else "")
        else:
            label = _j_act_sections(p.secs)
        if not label:
            return None
        if p.day:
            when = "on " + _j_prose_date(p.day.isoformat())
        else:
            m = re.search(r"\bsection\s+(\d{1,3})\b", p.how or "")
            if not m:
                return None
            when = f"as section {m.group(1)} provides"
        out.append((label, when))
    if len({w for w, _ in out}) != len(out):
        return None
    out.sort(key=lambda x: x[0] == "the rest")
    return "", ", ".join(f"{w} {d}" for w, d in out)


def _j_days(a, b):
    """Days from ISO date b to ISO date a; 0 where either is missing."""
    try:
        return (_date.fromisoformat(a) - _date.fromisoformat(b)).days
    except (TypeError, ValueError):
        return 0


def _j_in_term(day, term):
    """Whether an ISO day can be a day of the term "2019-2020": from the
    December before its first year, when the House organises and the first
    bills are introduced, to the end of its second. True where either is
    missing.

    A day outside it is the clerk's year, not the bill's: "Introduced
    01/02/2014" on HB 214 of 2019-2020, "Adjournment 09/16/2021" on HB 201
    of the same term, a term that ended in December 2020."""
    m = re.match(r"(\d{4})-(\d{4})$", term or "")
    if not m or not day:
        return True
    return f"{int(m.group(1)) - 1}-11-01" <= day <= f"{m.group(2)}-12-31"


def _j_year_slip(said, day, term):
    """The day a row means where the one it states has the clerk's year:
    the same month and day in the year of the row's own date, where that is
    in the term and is the row's day or up to 60 days before it -- or "".

    "Introduction and referring to Judiciary 1/28/98" was entered at 10:14
    on 28 January 1999, the day the Senate sat (SB 66 of 1999); "Introduced
    and Adopted, VV; 02/09/2016" on SR 8 of 2017 cites Senate Journal 5, of
    9 February 2017; "Introduced and Adopted VV 01/06/2020" on HR 6 of 2021
    cites House Journal 2, of 6 January 2021. A month and a day are the
    clerk's; the year the row was entered in says which one."""
    try:
        got = _date(int(day[:4]), int(said[5:7]), int(said[8:10])).isoformat()
    except (TypeError, ValueError):
        return ""
    return got if _j_in_term(got, term) and 0 <= _j_days(day, got) <= 60 else ""


def _j_stated_day(text):
    """The first date a line states, "2007-06-11", or ""."""
    got = []
    for m in J_DAY.finditer(text or ""):
        iso = _j_iso(*m.groups())
        if iso:
            got.append((m.start(), iso))
            break
    m = J_MONTH_DAY.search(text or "")
    if m:
        try:
            got.append((m.start(), _date(int(m.group(3)), J_MON.index(m.group(1)[:3].title()) + 1,
                                         int(m.group(2))).isoformat()))
        except ValueError:
            pass
    return min(got)[1] if got else ""


def _j_gov_more(evs, gov, most=7):
    """The rows that carry a governor's row on -- "II. Remainder Eff.
    08/12/2007" -- in the order they follow it, at most `most` of them, or
    every one where `most` is None."""
    try:
        i = next(k for k, x in enumerate(evs) if x is gov)
    except StopIteration:
        return []
    out = []
    for x in evs[i + 1:None if most is None else i + 1 + most]:
        if x.get("type") not in ("other", "governor") or not J_EFF_MORE.match(x.get("raw") or ""):
            break
        out.append(x.get("raw") or "")
    return out


def _j_introduced(evs, bid, term=""):
    """The day the bill was introduced in the chamber it started in: the
    day its introduction row states where it states one ("Introduced pursuant
    to Rule 36c 02/20/2025", HR 17 of 2025, entered on the 25th), else the
    day of the row.

    A ROW THAT STATES A DAY OUTSIDE THE TERM STATES THE CLERK'S YEAR.
    "Introduction and referring ... 1/28/98" on SB 53 of 1999, "Introduced
    and Adopted, VV; 02/09/2016" on SR 8 of 2017 and "Introduced 01/02/2014"
    on HB 214 of 2019 had the rail say each was introduced a year or five
    before its term began. The month and day are taken in the year of the
    row's own date where that is in the term and not after the row
    (_j_year_slip) -- 28 January 1999, 9 February 2017, 2 January 2019, each
    the day of the Journal the row cites -- and otherwise the stop goes
    undated rather than take either.

    IN ITS OWN CHAMBER. A bill is introduced twice, once in each chamber, and
    the first row typed as an introduction is not always the first chamber's:
    SCR 1 of 2023's Senate row, "Sen. Birdsell Moved Introduction; 2/3
    necessary, MA, VV; 02/09/2023", is typed as a floor decision, and the
    House's introduction of 16 March was taken for the resolution's."""
    rows = [e for e in evs
            if e.get("type") == "introduced" or J_INTRO_ROW.search(e.get("raw") or "")]
    pre = bill_prefix(bid)
    # The chamber the number names, a special session's "SSHB" included: SSHB
    # 1 of 2013 was read as a Senate bill by its first letter, and its rail's
    # Introduced stop took 21 November, the day the Senate introduced it, a
    # fortnight after "Introduced: MA RC 183-141 and Referred to Finance" in
    # the House on the 7th.
    # Only where that chamber has an introduction row: SSHB 1 of 2010's House
    # rows begin at "Ought to Pass", and its stop keeps the Senate's row of
    # the same day, 9 June, the one day that session sat.
    named = pre[2:] if pre.startswith("SS") and len(pre) > 3 else pre
    if named != pre and any((e.get("body") or "")[:1].upper() == named[:1] for e in rows):
        pre = named
    own = "S" if pre.startswith("S") else "H" if pre.startswith("H") else ""
    # Where the first chamber's own row is missing, no date: SB 109 of 2009
    # has only the House's "Introduced and Referred to Transportation", a
    # fortnight after the Senate passed it.
    if own:
        rows = [e for e in rows if (e.get("body") or "")[:1].upper() == own]
    days = []
    for e in rows:
        d = e.get("date") or ""
        said = _j_stated_day(e.get("raw") or "")
        if said and not e.get("date_as_recorded") and (not d or said <= d):
            d = said if _j_in_term(said, term) else _j_year_slip(said, d, term)
        if d and _j_in_term(d, term):
            days.append(d)
    return min(days) if days else ""


# What a committee report recommended, as the decision its adoption was.
J_FROM_REPORT = [(re.compile(r"inexpedient|ought\s+not\s+to\s+pass", re.I), "killed"),
                 (re.compile(r"interim\s+study", re.I), "study"),
                 (re.compile(r"indefinitely\s+postpone", re.I), "postponed"),
                 (re.compile(r"ought\s+to\s+(?:pass|adopt)", re.I), "passed"),
                 (re.compile(r"re-?\s?refer|recommit", re.I), "recommitted")]
J_WRAPPED_TALLY = re.compile(r"\(\s*\d+\s*-?\s*$")
J_TALLY_TAIL = re.compile(r"^\s*-?\s*\d+\s*\)")
J_FILED = re.compile(r"\bfiled\b", re.I)
J_CONF = dict(J_ACTS)["conference"]
J_VETO_VOTE = dict(J_ACTS)["veto_vote"]
# Past tense: "Shall HB 455-FN Become Law" is the question the vote is on.
J_CHAPTERED = re.compile(J_EFF_ANY.pattern + r"|\bchap(?:ter)?\b|\bbecame\s+law\b", re.I)


def _j_unfile(raw):
    """A docket row without a conference report's filing in it: "" where
    that is all the row records.

    A REPORT FILED IS NOT A VOTE ON IT, and the words that describe the
    version it proposes read as one. "Conference Committee Report #2084, As
    Passed by the Senate: Filed" (SB 32 of 2008) was the House passing the
    bill, days before it voted the report down; "Conference Committee Report
    #2021-1946c Filed 06/10/2021; Version Adopted by Senate" (SB 103 of 2021)
    was the House adopting the report eight days before it did; "Conference
    Committee Report; Concur with Senate Am { 1729}; Filed" (HB 215 of 2001)
    was the Senate agreeing to an amendment of its own. So everything up to
    "Filed" goes, and the clause after it when it carries no vote -- "As
    Passed by the Senate", "House Amendment + New Amendment". A vote the
    clerk put in the same row stays: "CONF COMM REPORT (S AM + NEW AM)
    FILED; CONF COMM REPORT ADOPTED RC(19-3)" (HB 25 of 1991)."""
    m = J_FILED.search(raw or "")
    if not m or not J_CONF.search(raw[:m.end()]):
        return raw
    rest = [p.strip() for p in raw[m.end():].split(";")][1:]
    if rest and not (J_YES_CODE.search(rest[0]) or J_NO_CODE.search(rest[0])
                     or J_TALLY.search(rest[0]) or J_VOICE.search(rest[0])
                     or J_RC_BARE.search(rest[0])):
        rest = rest[1:]
    return "; ".join(p for p in rest if p)


def _j_rows(evs):
    """[(event, text)]: the docket rows a decision can be read from, with a
    row the clerk wrapped joined to the row it runs on into.

    "REP MCCANN MOVED OTP, ML RC(107-198); REP HOLDEN MOVED ITL, ITL" and
    then "REPORT ADOPTED VV; HJ37,P1295" (CACR 21 of 1996) are one motion
    and its outcome; so are "...ADOPTION ML RC(95-" and "235); HJ83,P2147"
    (SCR 13 of 1992). Read apart, the first is nothing and the second, in
    "REP B. HALL SUBST REF FOR STUDY, ML DIV(99-196); ITL REPORT" / "ADOPTED
    VV" (HB 265 of 1992), a resolution adopted.

    THE FLOOR'S WORDS CAN SIT IN A ROW TYPED AS A REPORT. "MAJ REPT OTP, ML
    DIV(114-223); REP MCGUIRK MOVED ITL, ITL REPORT" is a report row of SB 217
    of 1997, and its "ADOPTED VV" is the House's floor row of the same day --
    in whichever order the two were entered.

    A LINE TOLD QUESTION BY QUESTION IS STILL ONE LINE HERE. The 1999-2006
    reader gives a House floor day an event for each question it decided
    (docket_vocab.questions), each with its own clause as `raw`. Those are
    whole clauses, not a row wrapped onto the next, and read as rows they are
    joined back wrongly: SB 135 of 1999's "Re-Referred to Res, Rec & Dev
    committee RC(158-154)" and "Rep Royce moved to reconsider, ML
    RC(156-157)" became a re-referral that failed, and left the rail. The
    line is read whole, once, from the event that carries it (docket_line),
    which is what this was written for."""
    evs = [e for e in evs if not e.get("in_line")]
    tails = defaultdict(list)
    voted = set()
    for e in evs:
        if e.get("type") != "report":
            continue
        raw = docket_line(e)
        segs = _j_segments(raw)
        if (segs and re.search(r"\bM[AFL]\b|\bmoved\b|\bsubst", raw, re.I)
                and _j_act(segs[-1]) and not _j_has_outcome(segs[-1])):
            tails[(e.get("body"), e.get("date"))].append(raw)
        # A report row that is itself the floor's vote on the report, whole:
        # "Minority Committee Report: Ought to Pass with AM #0625h NT: MA RC
        # 193-141" (HB 1623 of 2008) is the House passing the bill; "COMM
        # REPORT ITL, ML VV; RE-REFERRED TO MUN & CNTY GOVT, REP BEHRENS MA
        # VV" (HB 475 of 1995) is it sending the bill back. Not the Senate's
        # "Committee Report; Ought to Pass with Amendment{0400s} (New
        # Title), MA, VV" (SB 165 of 2009), the committee's own report,
        # whose floor vote is a row of its own a fortnight later.
        elif ((J_YES_CODE.search(raw) or J_NO_CODE.search(raw))
              and not re.match(r"\s*committee\s+report\s*;", raw, re.I)):
            voted.add(id(e))
    out = []
    for e in evs:
        if e.get("type") in J_NOT_FLOOR and id(e) not in voted:
            continue
        raw = _j_unfile(docket_line(e))
        first = (_j_segments(raw) or [""])[0]
        tail = tails.get((e.get("body"), e.get("date")))
        if tail and J_OUTCOME_ONLY.match(first):
            out.append((e, f"{tail.pop(0).rstrip()} {raw.lstrip()}"))
            continue
        if out and raw.strip():
            pe, prev = out[-1]
            same = ((pe.get("body"), pe.get("date")) == (e.get("body"), e.get("date")))
            segs_p, segs_n = _j_segments(prev), _j_segments(raw)
            last = segs_p[-1] if segs_p else ""
            first = segs_n[0] if segs_n else ""
            tally = J_WRAPPED_TALLY.search(prev) and J_TALLY_TAIL.match(raw)
            # A motion wrapped mid-phrase: "...; NEW CONF COMM" and "REPORT
            # ADOPTED VV" (HB 1399 of 1992), "...; GOVERNOR'S VETO" and
            # "SUSTAINED RC(221-117)" (HB 332 of 1995) -- neither half names
            # a motion, and the two together do.
            wrapped = (last and not _j_has_outcome(last) and first and _j_has_outcome(first)
                       and not _j_act(first) and _j_act(f"{last} {first}"))
            # And a suspension of the rules the clerk ran onto the next row:
            # "REPS KURK & PFAFF SUSP" and "RULES FOR 3RD READING, MA 2/3VV".
            # Read alone, the second half is the bill passing.
            # Where the next row starts a motion of its own, it is not the
            # rest of this one, unless this one broke off at "SUSP".
            tail_p = prev.split(";")[-1]
            sm = J_SUSPEND.search(tail_p)
            open_susp = bool(sm) and not (J_SUSP_CODE.search(tail_p, sm.end())
                                          or J_SUSP_WORD.search(tail_p, sm.end())) and (
                bool(re.search(r"\bsusp\w*\.?\s*$", tail_p, re.I))
                or not _j_act(raw.split(";")[0]))
            if same and (tally or wrapped or open_susp
                         or (last and _j_act(last) and not _j_has_outcome(last)
                             and first and _j_has_outcome(first)
                             and (J_OUTCOME_ONLY.match(first) or not _j_act(first)))):
                out[-1] = (pe, prev.rstrip() + ("" if tally else " ") + raw.lstrip())
                continue
        out.append((e, raw))
    return out


def _j_row_day(e, raw):
    """The day a row states at its end ("; 03/27/2025"), else its event's.
    A row no pattern reads is dated by its entry: SB 86 of 2025's "Pending
    Motion OT3rdg; 03/27/2025" was entered on 4 June."""
    m = J_ROW_DAY.search(raw or "")
    return (_j_iso(*m.groups()) if m else "") or (e.get("date") or "")


def _j_untold(e, seg, evs):
    """Whether the history tells nothing of the clause a decision was read
    from: the row is one no pattern reads (type "other"), or it is a line
    told question by question (docket_vocab.questions) and this question is
    the one left untold -- "OTP/AM failed 3/5 RC(186-172)", the last clause
    of CACR 2 of 2004's floor line, whose event carries the clause alone."""
    if e.get("type") == "other":
        return True
    if not e.get("line"):
        return False
    want = re.sub(r"\s+", " ", seg or "").strip()
    for o in evs:
        if not (o.get("in_line") and o.get("type") == "other"
                and (o.get("body"), o.get("date")) == (e.get("body"), e.get("date"))):
            continue
        clause = re.sub(r"\s+", " ", o.get("raw") or "").strip()
        if clause and want and (clause in want or want in clause):
            return True
    return False


def journey(narr, bid, rcs=(), chapter="", law_line="", term="", db_effective="",
            untold=None, text=""):
    """(the date it was introduced, [one dict a decision]) -- from the docket.

    Each decision carries its date, its body (H, S, the Governor G, the Law L
    or the Voters V), what it was (`act`), the glyph it is drawn with
    (`mark`: p, x or h), its words for On the record (`text`) and for the
    rail (`short`). `term`, "2019-2020", bounds the days it will state.

    `untold`, a set the caller passes, is filled with the id() of each line
    read from a docket row narrative.py tells nothing of (its type "other"):
    a decision the bill's history does not narrate (closing_stage).

    `text` is the bill's text as its page shows it (bill_text_block's body):
    a chaptered law's own Effective Date lines date its Law stop before the
    docket's line does (_j_chaptered).
    """
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    intro = _j_introduced(evs, bid, term)
    # The day the conferees reported that they could not agree, where that is
    # the last word of the bill's conferences: a report adopted from that day
    # on is that report, and the line says what it said. Only a REPORT of no
    # agreement: where the record says none was signed, a chamber adopted no
    # report of that conference, and none of its lines is rewritten.
    failed = conference_failure(evs)
    unable_day = (max((e.get("date") or "" for e in evs
                       if CONF_UNABLE_RE.search(e.get("raw") or "")), default="")
                  if failed and failed[0] == "unable" else None)
    steps, amended = [], set()
    gov_raw, gov_more, gov_all = "", [], []
    reports = [e for e in evs if e.get("type") == "report"]
    # A second committee's chair can waive the referral, and the bill then
    # goes on as the chamber passed it: HB 243 of 2025, "Ought to Pass: MA
    # VV", "Referred to Criminal Justice and Public Safety", "Referral Waived
    # by Committee Chair per House Rule 47(f)", all on 20 February, and in
    # the Senate a fortnight later. The waiver can be entered ahead of the
    # referral it waives (SB 482 of 2026), or days after it.
    waived = {((e.get("body") or "")[:1].upper(), e.get("date") or "")
              for e in evs if J_WAIVED.search(e.get("raw") or "")}
    divided = {((e.get("body") or "")[:1].upper(), e.get("date") or "")
               for e in evs if J_DIVIDED_OUT.search(e.get("raw") or "")
               and any(re.sub(r"\s+", "", m.group(0)).upper() == bid
                       for m in J_OTHER_BILL.finditer(e.get("raw") or ""))}
    # What a reconsideration naming nothing is of (_j_reconsidered): a vote
    # the chamber took since its last decision, on any day; and, on the day
    # of the reconsideration, a motion it took up with no vote written beside
    # it or a suspension of the rules it refused.
    pending, voted, moved = {}, set(), {}
    # A MOTION TO PASS ADOPTED AND THEN TABLED BEFORE THE STEP THAT PASSES THE
    # BILL (narrative.passage_left_pending, the one reading the history and
    # the sitting pages ask too). The Senate passes a bill by ordering it to a
    # third reading -- "Ought to Pass: MA, VV; OT3rdg" -- or under its Rule 4-5
    # sends it to Finance first; SB 131 of 2025 has "Ought to Pass: MA, VV",
    # "Sen. Gray Moved Laid on Table, MA, VV" and "Pending Motion OT3rdg", all
    # of 27 March (Senate Journal 9: the motion "Adopted." and the tabling, and
    # no "bill ordered to Third Reading"), and died under Rule 3-23. Its rail
    # read "Passed on a voice vote". The line is kept while the rows are read,
    # so that a removal from the table, a reconsideration and the order to a
    # third reading that carries it later each find what they would have, and
    # is left out after, unless that order came.
    # THE ROWS ARE READ ONCE (16 October 2026, private/SITE_DATA_PROFILE.md,
    # P2). They were read twice, here and for the loop below, and nothing
    # between the two readings changes `evs` or an event in it:
    # passage_left_pending is handed tuples of strings. The second reading
    # was a third of journey's time over the site data step.
    rows = _j_rows(evs)
    unpassed = N.passage_left_pending(
        [((e.get("body") or "").upper()[:1], _j_row_day(e, raw), raw) for e, raw in rows])
    for e, raw in rows:
        body = (e.get("body") or "").upper()[:1]
        # THE JOURNAL A ROW CITES NAMES THE CHAMBER THAT ACTED. "PASSED VV;
        # SJ12,P305 + 318" is filed under the House on HB 1113 of 1994 and
        # is the Senate passing it; "Sen. Francoeur Moved Laid On Table, MA,
        # VV" sits under the House on HB 1249 of 2002 with the Senate
        # Journal's page. Read by the filing, the House passed those bills
        # twice and the Senate never did.
        # BUT A CITATION CAN BE THE TYPO, and then the filing is right. Which
        # it is, the chamber that held the bill says -- the one whose
        # introduction or committee report came last before the row: HB 366
        # of 1995's "ITL REPORT ADOPTED; SJ25,P532" is the House killing a
        # bill the Senate never received, and HB 426 of 1993's "PASSED VV;
        # HJ46,P217 + 221", filed under the Senate the day of the Senate
        # committee's report, is the Senate passing it.
        cite = (e.get("cite") or "").upper()
        if cite[:2] in ("HJ", "SJ") and body in ("H", "S") and cite[0] != body:
            before = evs[:next((k for k, x in enumerate(evs) if x is e), len(evs))]
            held = next(((x.get("body") or "")[:1].upper() for x in reversed(before)
                         if x.get("type") in ("introduced", "report")
                         or J_INTRO_ROW.search(x.get("raw") or "")), "")
            # Or the row says whose it is: "SEN CONC WITH HOUSE AM, SEN DANAIS
            # MA VV; SJ10,P117" (SB 157 of 1995) is the Senate concurring,
            # back from the House with no new introduction.
            who = ("S" if re.match(r"\s*(?:sen(?:ator)?s?\b\.?|senate\b)", raw, re.I)
                   else "H" if re.match(r"\s*(?:reps?\b\.?|house\b)", raw, re.I) else "")
            if held == cite[0] or who == cite[0] or J_INTRO_ROW.search(raw):
                body = cite[0]
        date = e.get("date") or ""
        # THE CHAPTER, NOT A THIRD VOTE ON THE VETO. Once both chambers have
        # overridden, the clerk records the law: "Veto Overriden 05/30/2019:
        # Eff: 05/30/2019; Chapter 42" (HB 455 of 2019, filed under the House
        # a week after the House's own 247-123), "VETO OVERRIDDEN (BECAME LAW
        # WITHOUT SIGNATURE) 09/15/93" (HB 25 of 1993). Read as a vote, the
        # House overrode twice. An override is a roll call; a row naming one
        # with no vote at all and a chapter, an effective date or the bill
        # becoming law is the Law line's, which says it already.
        if (J_VETO_VOTE.search(raw) and J_CHAPTERED.search(raw)
                and not any(rx.search(raw) for rx in (J_YES_CODE, J_NO_CODE, J_TALLY,
                                                      J_VOICE, J_RC_BARE))):
            continue
        # A vote to suspend the rules that failed, ahead of any
        # reconsideration in the row, or after it once the row is read. That
        # day only: HB 462 of 1989 was sent back to committee on 16 March,
        # failed to have the joint rules suspended on 13 April, and on 25
        # April had the rules suspended and reconsidered the recommittal.
        failed, rc = _j_suspension_failed(raw), J_RECONSIDER.search(raw)
        if failed >= 0 and (not rc or failed < rc.start()):
            moved[body] = date
        for seg in _j_segments(raw):
            if J_REMAINING.match(seg) and (body, date) in divided:
                continue
            if J_WAIVED.search(seg):
                last = next((s for s in reversed(steps) if s["body"] == body), None)
                if last and last["act"] == "referred":
                    last["act"] = "passed"
                    last.pop("to", None)
                continue
            # A BILL TAKEN OFF THE TABLE WAS NOT LEFT ON IT, whether the same
            # day or later: SB 315 of 2012 was passed and tabled with a batch
            # of Senate bills on 25 April, taken off on 16 May and signed in
            # June. "Remove from Table (Rep. Wherry): MF RC 151-168" (SB 222
            # of 2025) is a motion that failed, and left it there.
            off = re.search(r"\b(?:remov\w*|taken|take)\s+(?:\w+\s+){0,2}from\s+(?:the\s+)?table",
                            seg, re.I)
            if off:
                said = _j_outcome(seg, off.start())
                if said is None:
                    said = bool(re.match(r"removed|taken", off.group(0), re.I))
                # Not a line left out once the rows are read (`unpassed`):
                # HB 282 of 2025's Ought to Pass row was entered after the
                # tabling of 15 May that its removal of 26 June undid.
                mine = [i for i, s in enumerate(steps)
                        if s["body"] == body and not s.get("_unpassed")]
                if said and mine and steps[mine[-1]]["act"] == "tabled":
                    steps.pop(mine[-1])
                # And what the clause does next: "Sen D'Allesandro Moved
                # Remove From Table, MA, VV, Ought to Pass, MA, VV, OT3rdg,
                # MA, VV" (HB 501 of 1999) is the Senate passing the bill.
                o = J_SUSP_CODE.search(seg, off.end()) or J_SUSP_WORD.search(seg, off.end())
                seg = seg[J_SUSP_VOTE.match(seg, o.end()).end():] if o else ""
                if not _j_act(seg):
                    continue
            # "Ought to Pass ...: MA RC 197-149" and then, the same day,
            # "Referred to Finance" -- or "...MA, VV; Refer to Finance Rule
            # 4-5" on one line: the chamber approved it and sent it to a
            # second committee, which is not the bill leaving the chamber.
            # ANY SECOND COMMITTEE, not only the money ones. HB 493 of 2025
            # was approved on 13 March and "Referred to Executive Departments
            # and Administration" the same day, which killed it 193-177 in
            # April; read as passed, the House passed a bill it never passed.
            # THE CLERKS OF 1989 WROTE THE REFERRAL WHEN THEY GOT TO IT: before
            # the passage it followed ("REFERRED TO FINANCE/APPROP" at 12:49,
            # "PASSED/ADOPTED" at 14:36, HB 115 of 1989), or days after it
            # (HB 396, passed on 21 April, "REFERRED TO APPROP/FINANCE" on the
            # 25th). A passage the chamber sent on to a second committee
            # before the other chamber did anything is that referral; one
            # waiting for its passage takes it when it comes.
            ref = J_BARE_REFERRAL.match(seg)
            to = _j_second_committee(ref.group("c")) if ref and not _j_act(seg) else ""
            if to:
                at = next((i for i in range(len(steps) - 1, -1, -1)
                           if steps[i]["body"] == body), None)
                last = steps[at] if at is not None else None
                # Not a passage the chamber has since reconsidered, which the
                # referral came after: the Senate passed HB 1331 of 1990 on
                # 29 March, reconsidered it on 3 April and sent it to Finance
                # that day, and it read "Approved and sent to Finance,
                # reconsidered on 3 Apr".
                if last and last.get("reconsidered") and date >= last["reconsidered"]:
                    continue
                if (last and last["act"] == "passed" and (body, date) not in waived
                        and 0 <= _j_days(date, last["date"]) <= 30
                        and not any(s["body"] in ("H", "S") for s in steps[at + 1:])):
                    last["act"], last["to"] = "referred", to
                elif (body, date) not in waived:
                    pending[(body, date)] = to
                continue
            _j_reconsidered(steps, body, date, seg,
                            body not in voted and moved.get(body) != date)
            # THE PENDING ORDER, CARRIED LATER WITH NO CODE: "OT3rdg;
            # 03/21/2024", the day SB 173 of 2024 came off the table, its
            # Ought to Pass of 3 January left pending by the tabling; "OT3rdg"
            # on SB 144 of 2015. The bill passed then, on the motion it had
            # adopted.
            if N.BARE_THIRD.match(raw) and (body, _j_row_day(e, raw)) not in unpassed:
                waiting = next((s for s in reversed(steps)
                                if s["body"] == body and s.get("_unpassed")), None)
                if waiting:
                    waiting["_unpassed"], waiting["date"] = False, date
                    continue
            got = _j_decide(seg, bid, rcs, date, body)
            if (got is None or got == "amended") and not J_RECONSIDER.search(seg):
                # A vote since the chamber's last decision, which a
                # reconsideration naming nothing is then about -- or a
                # motion that day with no vote written beside it: "REP
                # LARSON SUBST ITL; VOTE TAKEN, INCORRECTLY, ON COMM AM; REP D
                # HALL MOVED TO RECONSIDER, MA VV" (SB 796 of 1994) undid that
                # day's mistaken vote, not the passage of a month before.
                if _j_has_outcome(seg):
                    voted.add(body)
                elif _j_act(seg) or J_AMEND_SUBJ.search(seg):
                    moved[body] = date
            if got is None:
                continue
            if got == "amended":
                amended.add((body, date))
                # The amendment's row can carry the referral that followed
                # the passage: "Sen. Pignatelli Floor Amendment, {2150}, AA,
                # VV, Rule 24 (Refer to Finance)" (HB 707 of 1999).
                to_ = J_REFERRED_TO.search(seg)
                last = next((s for s in reversed(steps) if s["body"] == body), None)
                if (to_ and last and last["date"] == date and last["act"] == "passed"
                        and (body, date) not in waived):
                    last["act"], last["to"] = "referred", to_.group("c").strip()
                continue
            if got["act"] == "report_adopted":
                rec = next((r.get("recommendation") or "" for r in reversed(reports)
                            if (r.get("body") or "")[:1] == body
                            and (r.get("date") or "") <= date
                            and r.get("side") != "Minority" and r.get("recommendation")), "")
                act = next((a for rx, a in J_FROM_REPORT if rx.search(rec)), "")
                # No report to adopt: the rules were suspended to take the
                # bill up without one, and "ADOPTED VV" is the bill -- "REPS
                # TEAGUE & WALLNER SUSP RULES TO CONSIDER, MA 2/3VV; ADOPTED
                # VV" (HB 1503 of 1992, signed in June). Not an amendment's
                # adoption: "Adopt Remainder Floor Amendment {2421h}; AA VV".
                if not rec and not re.search(r"amend|\brep(?:ort|t)\b", seg, re.I):
                    act = "passed"
                if not act:
                    continue
                got = {**got, "act": act,
                       "amended": act == "passed" and bool(re.search(r"amend", rec, re.I))}
            st = {"date": date, "body": body, **got, "_untold": _j_untold(e, seg, evs)}
            if got["act"] == "passed" and (body, _j_row_day(e, raw)) in unpassed:
                st["_unpassed"] = True
            # A COUNT THAT IS THE CONSENT CALENDAR'S (decision 51,
            # narrative.CONSENT_VOTE): "PASSED WITH AM/CONSENT CAL RC(248-8)"
            # read "Passed with an amendment, 248-8", the calendar's roll call
            # of 7 January 1998 as the bill's own.
            if (st.get("vote") or ("", None))[1] is not None and N.CONSENT_VOTE.search(seg):
                st["consent"] = True
                # And a count the calendar's other rows do not give is no
                # count of the calendar's (narrative.calendar_count_disputed):
                # "on the consent calendar", and no count.
                if e.get("calendar_count_disputed"):
                    st["vote"] = ("", None, None)
            # Whether its own clause names the amendment, before the day's
            # amendment rows mark every passage of that day (_j_merge).
            if got["act"] in J_PASSING:
                st["_own_am"] = bool(got.get("amended"))
            # THE DAY THE CLAUSE STATES, where the row was dated by its entry:
            # "Adopted and read a 3rd time MA VV 01/05/22", entered on 10
            # January (HB 1650 of 2022) -- four days after the governor
            # signed the bill it passed. Not a sitting the chamber met "in
            # recess of", which is the day before the one it acted on.
            # A BILL KILLED BY RULE AT ADJOURNMENT DIED THE DAY IT STATES, and
            # the clerk enters those rows in a batch long after: 427 of
            # 2019-2020's read "Inexpedient to Legislate, Senate Rule 3-23,
            # Adjournment 09/16/2020" and were entered in September 2021, a
            # year after the term ended, which is the day the line and the
            # rail's Senate stop carried. So its day is taken however far
            # back, as long as it is in the term and not before the
            # chamber's last word on the bill (the tabling it died on).
            # AND THE DAY AN INTRODUCTION ROW STATES, which is the day of what
            # it did on introduction: "Introduced and Adopted, VV; 02/09/2016"
            # on SR 8 of 2017 is Senate Journal 5 of 9 February 2017, the day
            # its rail says it was introduced (_j_introduced) -- and it read
            # as adopted on the 15th, the day the row was entered, six days
            # after the one motion that did both.
            said = J_CLAUSE_DAY.search(seg) or (J_INTRO_ROW.search(seg)
                                                and J_ROW_DAY.search(raw)) or None
            if (said and got["act"] not in ("signed", "vetoed", "unsigned")
                    and not e.get("date_as_recorded")):
                day = _j_iso(*said.groups())
                # The clerk's year, as on an introduction: HR 6 of 2021's
                # "Introduced and Adopted VV 01/06/2020", entered on 7 January.
                if day and not _j_in_term(day, term):
                    day = _j_year_slip(day, date, term)
                back = _j_days(day, date) if day else 0
                if day and _j_in_term(day, term) and (-60 <= back < 0 or (
                        got["act"] == "died" and back < 0 and not any(
                            s["body"] == body and s["date"] > day for s in steps))):
                    st["date"] = day
            # AND A SITTING THE ROW WAS ENTERED AHEAD OF. The Senate's clerk
            # enters a conference report's adoption before the sitting and
            # states the sitting after it: "Conference Committee Report
            # #2024-2290c , Adopted, VV; 06/13/2024", entered on 12 June (HB
            # 1573 of 2024), is Senate Journal 17 of 13 June, and the Senate
            # did not sit on the 12th. So were 34 of this term's, dated 29 May
            # 2026 and 24 June 2025. Up to a fortnight ahead, on a weekday:
            # "OT3rdg; 03/19/2017" on SB 152 of 2017, entered on the 16th
            # when the Senate sat, states a Sunday.
            ahead = [x for x in (said, J_ROW_DAY.search(raw)) if x]
            if got["act"] not in ("signed", "vetoed", "unsigned") and not e.get("date_as_recorded"):
                for x in ahead:
                    day = _j_iso(*x.groups())
                    if (day and _j_in_term(day, term) and 0 < _j_days(day, date) <= 14
                            and _date.fromisoformat(day).weekday() < 5):
                        st["date"] = day
                        break
                if ahead:
                    st["_stated"] = _j_iso(*ahead[-1].groups())
            # A report not accepted states the sitting it was done in recess
            # of, "05/19/2016" on SB 305 of 2016, a week before the report was
            # filed, and was entered on 3 June: undated, rather than either.
            if st.get("unaccepted"):
                st["date"] = ""
            # And no day outside the term at all: HB 201 of 2020's own row
            # reads "Adjournment 09/16/2021", entered on 9 September 2021,
            # and neither is a day of 2019-2020. Undated, rather than either.
            if not _j_in_term(st["date"], term):
                st["date"] = ""
            if got["act"] in ("signed", "vetoed", "unsigned"):
                st["body"] = "G"
                gov_raw = raw
                gov_more = _j_gov_more(evs, e)
                gov_all = _j_gov_more(evs, e, None)
                # THE DAY THE LINE GIVES, NOT THE DAY IT WAS ENTERED. "Signed
                # by the Governor on 06/11/07" (HB 101 of 2007) was entered on
                # the 12th, and 628 governor lines were dated by their entry.
                # Not a day before the chambers finished with the bill -- "on
                # 06/14/10" on a bill of 2011 is the clerk's year -- nor far
                # from the row itself, and not where a person corrected the
                # docket's date (docket_corrections.json).
                said = _j_stated_day(J_EFF_ANY.split(raw, 1)[0])
                done = max((s["date"] for s in steps if s["body"] in ("H", "S")), default="")
                if (said and not e.get("date_as_recorded") and done <= said
                        and _j_days(said, date) <= 14):
                    st["date"] = said
                # A veto overridden is enacted "without the signature of the
                # governor" (HB 1422 of 2026, the day after both chambers
                # overrode). That is the override's result, which the Law
                # line says; the governor's act was the veto.
                if got["act"] == "unsigned" and any(s["act"] == "override" for s in steps):
                    continue
            st["_row_day"] = date
            if re.search(r"\bin\s+recess\b", raw, re.I):
                st["_recess"] = True
            voted.discard(st["body"])
            moved.pop(st["body"], None)
            if st["act"] == "passed" and (body, date) in pending:
                st["act"], st["to"] = "referred", pending.pop((body, date))
            steps.append(st)
        if failed >= 0 and rc and failed > rc.start():
            moved[body] = date
    steps = [s for s in steps if not s.pop("_unpassed", False)]
    # AN AMENDMENT ADOPTED THAT DAY AMENDS THAT DAY'S PASSAGE, whether the
    # clerk entered it before the passage or after: "Sen. Fernald Moved Ought
    # to Pass, RC 22y - 1n, MA" and then "Sen. Francoeur Floor Amendment
    # {2837}, (New Title), RC 13y - 10n, AA" (SB 336 of 2002), the bill that
    # went to the House amended.
    # A DECISION ENTERED AFTER THE GOVERNOR ACTED WAS MADE BEFORE: the
    # Senate's "Conference Committee Report # 2025-2809c; RC 16Y-8N, Adopted;
    # 06/26/2025" on HB 377 of 2025 was entered on 3 November and read as the
    # Senate adopting the report three months after the governor signed the
    # bill. The day its row states, where that is in the term and not after
    # the governor. Not a vote on the veto, which comes after it.
    gov = min((s["date"] for s in steps if s["body"] == "G" and s["date"]), default="")
    for st in steps:
        if st["act"] in ("passed", "referred") and (st["body"], st.get("_row_day")) in amended:
            st["amended"] = True
        st.pop("_row_day", None)
        said = st.pop("_stated", "")
        if (gov and st["body"] in ("H", "S") and st["date"] > gov and said
                and st["act"] not in ("override", "sustained")
                and _j_in_term(said, term) and said <= gov):
            st["date"] = said
    # The governor's line where the history has none but the chapter's
    # line does: the same evidence, read the same way.
    if law_line and not any(s["body"] == "G" for s in steps):
        got = _j_decide(law_line, bid)
        if isinstance(got, dict) and got["act"] in ("signed", "unsigned"):
            steps.append({"date": _j_stated_day(J_EFF_ANY.split(law_line, 1)[0]),
                          "body": "G", **got})
            gov_raw = law_line
    # A vote on a veto is the record of the veto. The 1989 docket has
    # "GOVERNOR'S VETO SUSTAINED, RC(172-140)" on HB 377 and no line of its
    # own for the veto, so the veto is the line before the vote, undated.
    first = next((i for i, s in enumerate(steps)
                  if s["act"] in ("override", "sustained")), None)
    if first is not None and not any(s["act"] == "vetoed" for s in steps):
        steps.insert(first, {"date": "", "body": "G", "act": "vetoed"})
    # One veto, one signature: HB 396 of 2024 carries "Vetoed by Governor
    # Sununu 07/19/2024" and, in October, "Vetoed by Governor 101024 [&]".
    seen_g = set()
    steps = [s for s in steps if s["body"] != "G"
             or not (s["act"] in seen_g or seen_g.add(s["act"]))]
    # In the order of the days the lines now carry, which a row dated by its
    # entry can have put out of step: HB 1650 of 2022's House passage of 5
    # January was entered after the governor's signature of the 6th. Stable,
    # so a day's own order stands; an undated line keeps its place.
    carry, keyed = "", []
    for i, s in enumerate(steps):
        carry = s["date"] or carry
        keyed.append((carry, i, s))
    steps = [s for _d, _i, s in sorted(keyed, key=lambda x: (x[0], x[1]))]
    steps = _j_answers_after(_j_in_recess(steps), bid)
    steps = _j_settle(_j_amended_on(steps))
    # A CONFERENCE FOLLOWS A PASSAGE. SB 200 of 1989 was killed on 9
    # February, "ITL REPORT ADOPTED", and its docket then has "CONF COMM
    # REPORT ADOPTED" on 24 May -- a report of a conference no chamber's vote
    # could have called, which made the rail pass the Senate under a
    # "Killed" chip. A conference line after a decision that ended the bill,
    # and no passage, is not read.
    steps = [s for i, s in enumerate(steps)
             if s["act"] not in ("conf_adopted", "conf_rejected", "conf_refused")
             or not any(t["act"] in J_ENDING for t in steps[:i])
             or any(t["act"] in ("passed", "referred", "concurred", "nonconcurred")
                    for t in steps[:i])]
    # A REPORT VOTED DOWN AND A NEW CONFERENCE AGREED TO IS NOT WHERE THE BILL
    # STOPPED. HB 723 of 1997: the Senate, which had passed the bill (amended,
    # on a voice vote, after voting Ought to Pass 19-5), voted down its
    # conferees' "unable to agree" report 10-13 and asked for a
    # new committee of conference 13-10, and the House acceded the same day
    # ("HOUSE ACCEDED TO REQ FOR NEW CONF COMM"). The new conference never
    # reported (CONFERENCE_NOT_REPORTED), and the rail marked the Senate as
    # where the bill was stopped -- "Rejected the conference report, 10–13"
    # -- under "Died when the session ended". A rejection the other chamber
    # answered by acceding to a new conference, with no vote on a report in
    # the rejecting chamber after it, is not that chamber's last word: its
    # passage is. Where the new conference did report, the rejection stays
    # on the record beside the vote that followed it (HB 1182 of 1990).
    renewed = max((e.get("date") or "" for e in evs
                   if J_NEW_CONFERENCE.search(e.get("raw") or "")), default="")
    if renewed:
        steps = [s for i, s in enumerate(steps)
                 if s["act"] != "conf_rejected" or (s["date"] or "") > renewed
                 or any(t["body"] == s["body"] and t["act"].startswith("conf_")
                        for t in steps[i + 1:])]
    # An introduction dated after the first decision on the bill is a date
    # something has wrong, and the stop goes undated rather than out of
    # order. HB 113 of 2005's "Introduced and ref to Crim Just & PSfty" stood
    # at 1 December 2006, eleven months after the House killed it -- but the
    # docket says 1 December 2004, and it was narrative.clamp_year that moved
    # it, reading a retained bill's second-year session as the whole of its
    # term (narrative.session_keeps).
    first_day = min((s["date"] for s in steps if s["body"] in ("H", "S") and s["date"]),
                    default="")
    if intro and first_day and intro > first_day:
        intro = ""
    if chapter:
        # THE LAW'S OWN WORDS FIRST (24 October 2026). The chaptered text ends
        # with when it takes effect -- "Effective Date: January 01, 2027", or a
        # line a part -- and the docket's line can be another bill's: HB 1184
        # of 2026's governor row reads "I. Sec 2 eff 1/1/27 II. Sec 3 eff
        # 1/1/27 III. Rem eff 1/1/28", which is HB 1102's, overridden the same
        # day, and its page said so; its chaptered text says section 3 on
        # August 19, 2027 and the rest on October 18, 2026, as RSA 635:2-a's
        # source note does. The Laws pages read the text first for the same
        # reason (build_rsa, Bills.effect), with the same reader (law_effect).
        # The docket's line is read where the text has no such lines, as the
        # archived terms' texts mostly have not.
        told = _j_chaptered(text)
        if told:
            eff, parts = told
        else:
            eff = _j_effective(gov_raw, *gov_more, law_line)
            # A LINE THAT CARRIES ANOTHER BILL'S CHAPTER CARRIES ITS EFFECTIVE DATE
            # TOO. SB 28 of 2009 reads "Signed by the Governor on 05/15/09;
            # Effective 07/07/09; Chapter 0028" -- SB 109's line, signed a week
            # earlier, with the day of the signature changed: sixty days from 15
            # May is 14 July, which is what SB 28's enrolled text prints
            # ("Effective Date: July 14, 2009") and what the database holds. Once
            # extract_chapters settled the chapter at 31 the rail read "Chapter
            # 31, in effect 7 Jul 2009". `db_effective` is the database's date on
            # a settled record whose docket number is not its chapter
            # (chapters.json's database_effective), and it is taken only where
            # the line states one date and the database another: a line that
            # states none, or several, is left saying none.
            if eff and db_effective and eff != db_effective:
                eff = db_effective
            # A law in effect on several dates says each, part by part, and its
            # stop on the rail stays undated: there is no one day to draw. Every
            # row that carries the governor's on is read, not the first seven:
            # HB 2 of 2007 runs to part XVI, and its first eight parts were
            # stated as though they were all of it.
            parts = "" if eff else _j_effective_parts(gov_raw, *gov_all, law_line)
        # `effective` is the day the rail's Law stop is dated by (F13); the
        # line itself stays undated, so How it got here does not print the
        # day twice beside words that already say it.
        law_step = {"date": "", "body": "L", "act": "law",
                    "text": f"Chapter {chapter}" + (
                        f", in effect {_j_prose_date(eff)}" if eff else
                        f", in effect in parts: {parts}" if parts else ""),
                    "short": f"Chapter {chapter}", "effective": eff or ""}
        # `shown`, where the parts are too many to read as a line (law_in_stages):
        # what How it got here and the rail say. `text` keeps every part,
        # because the Laws pages read it (build_rsa.journey_parts).
        staged = law_in_stages(chapter, parts) if parts and not eff else ""
        if staged:
            law_step["shown"] = staged
        steps.append(law_step)
    for e in evs:
        m = REFERENDUM.search(e.get("raw") or "")
        if m:
            yes = m.group("how").lower() == "adopted"
            t = J_REF_TALLY.search(e.get("raw") or "", m.end() - 1)
            steps.append({"date": e.get("date") or "", "body": "V",
                          "act": "ratified" if yes else "not_ratified",
                          "text": ("Ratified" if yes else "Not ratified")
                          + (f", {t.group(1)}–{t.group(2)}" if t else ""),
                          "short": "ratified" if yes else "not ratified"})
    for st in steps:
        st["mark"] = J_MARK.get(st["act"], "h")
        if "text" not in st:
            if st["body"] == "G":
                st["text"], st["short"] = {
                    "signed": ("Signed", "signed"), "vetoed": ("Vetoed", "vetoed"),
                    "unsigned": ("Became law without signature", "unsigned")}[st["act"]]
            else:
                st["text"], st["short"] = _j_words(st, bid)
        # "Adopted the conference report" on HB 42 of 1989, whose report said
        # "UNABLE TO AGREE", reads as the conferees having settled it.
        if (st["act"] == "conf_adopted" and unable_day is not None
                and (st.get("date") or "") >= unable_day):
            # THE VOTE BEFORE THE REPORT. "...the conferees' report that they
            # could not agree on a voice vote" reads as though the voice vote
            # were what they could not agree on; a tally after a comma is
            # read rightly.
            voice = "Adopted the conference report on a voice vote"
            if st["text"].startswith(voice):
                st["text"] = ("Adopted, on a voice vote, the conferees' report that "
                              "they could not agree" + st["text"][len(voice):])
            else:
                st["text"] = st["text"].replace(
                    "Adopted the conference report",
                    "Adopted the conferees' report that they could not agree", 1)
        if st.get("reconsidered"):
            st["text"] += ", reconsidered on " + _j_prose_date(
                st["reconsidered"], st["reconsidered"][:4] != st["date"][:4])
        for k in ("vote", "amended", "third", "to", "conf", "rule", "adjourned",
                  "unanswered", "intro_adopt", "short_of", "reconsidered", "recon_third",
                  "consent",
                  "_recess", "unaccepted", "_own_am"):
            st.pop(k, None)
        if st.pop("_untold", False) and untold is not None:
            untold.add(id(st))
    return intro, steps


def _j_answers_after(steps, bid):
    """A day's steps with each answer after the act it answers, across the
    two chambers, whose rows of one day the clerk can enter in either order.

    A chamber agreeing to or refusing the other's amendment answers that
    chamber's passage: HB 10 of 2025 had the House "Agreed to the Senate's
    amendment, 210–160" (entered at 1:52) ahead of the Senate passing it with
    that amendment (2:48), both on 5 June. And a vetoed bill goes back to the
    chamber it started in, which votes on the veto first: SB 434 of 2026 had
    the House sustaining the veto ahead of the Senate overriding it.

    And a bill passes the chamber its number names before the other one:
    HB 1650 of 2022 passed both on 5 January, and the Senate's row, entered
    that day, was listed ahead of the House's, entered on the 10th."""
    pre = bill_prefix(bid)
    origin = "H" if pre.startswith("H") else "S" if pre.startswith("S") else ""
    veto = ("override", "sustained")
    passing = ("passed", "referred")
    # The chamber the number names, special sessions' "SSHB" included.
    named = (pre[2:] if pre.startswith("SS") else pre)[:1]
    named = named if named in ("H", "S") else ""

    def answers(s, t, before):
        if not s["date"] or s["date"] != t["date"] or {s["body"], t["body"]} != {"H", "S"}:
            return False
        return ((s["act"] in ("concurred", "nonconcurred") and t["act"] == "passed")
                or (s["act"] in veto and t["act"] in veto and origin and s["body"] != origin)
                or (s["act"] in passing and t["act"] in passing and t["body"] == named
                    and not any(x["body"] == named and x["act"] in passing for x in before)))

    out = list(steps)
    i = 0
    while i < len(out):
        s = out[i]
        last = max((j for j in range(i + 1, len(out)) if answers(s, out[j], out[:i])),
                   default=None)
        if last is None:
            i += 1
            continue
        out.insert(last, out.pop(i))
    return out


# A RECONSIDERATION CARRIED ON A LATER DAY. _j_settle keeps the last of a
# day's decisions, so a decision reconsidered the same day is gone; one
# reconsidered days later stood until then, and is said to have been undone:
# "SEN REFUSED TO ACCEDE TO REQ FOR CONF COMM" on 12 May and "SEN MACDONALD
# MOVED TO RECONSIDER REQ TO ACCEDE, MA VV" on the 17th (HB 628 of 1994) read
# as a refusal followed by a conference report, with no word between.
J_RECONSIDER = re.compile(r"\breconsider\w*", re.I)
# Not the notice of one, the order of the day it is set for, or its debate.
J_RECON_NOT = re.compile(r"notice|special\s+order|limit\w*\s+debate", re.I)
# Where the motion names what it reconsiders, the decision must be that one:
# "REP GROSS MOVED TO RECONSIDER REQ FOR NEW CONF COMM" (HB 1025 of 1992) is
# the House's accession to a new conference, which is no line here, and not
# its adoption of the report the day before.
J_RECON_NAMES = [
    (re.compile(r"acced|\breq\w*\.?\s+(?:for|to)\s+(?:a\s+)?(?:new\s+)?(?:conf|c\s?of\s?c)", re.I),
     {"conf_refused"}),
    (re.compile(r"non-?\s?conc", re.I), {"nonconcurred"}),
    (re.compile(r"\bconc", re.I), {"concurred"}),
    (re.compile(r"conf\w*\.?\s*comm\w*\.?\s*rep|conference\s+report", re.I),
     {"conf_adopted", "conf_rejected"}),
    (re.compile(r"third\s+reading|3rd\s+r|\bpass|\bOTP|ought\s+to\s+pass", re.I),
     {"passed", "referred"}),
    (re.compile(r"inexpedient|\bITL\b|\bkill", re.I), {"killed"}),
    (re.compile(r"\btabl", re.I), {"tabled"}),
    (re.compile(r"interim\s+study", re.I), {"study"})]
# Where the naming stops: its vote, or the chamber's code for the outcome.
J_RECON_END = re.compile(r"\b(?:MA|MF|ML|AA|AF|AL|VV)\b|\b(?:RC|DV|DIV|Division)(?![A-Za-z])|"
                         r"\b(?:adopted|failed|lost|carried)\b", re.I)


def _j_reconsidered(steps, body, date, seg, last=True):
    """Mark the chamber's last decision reconsidered where `seg` is a
    reconsideration carried on a later day than it -- of that decision.

    One that names nothing reconsiders the last vote the chamber took, which
    is the decision only where nothing was voted on since (`last`): "REP
    CHAMPAGNE MOVED TO RECONSIDER, MA RC(211-160)" on HR 1 of 1997 is the
    House taking up again an amendment to its rules it had just rejected
    186-186, not the rules it adopted in December. Nor where the clause takes
    something up ahead of it: "Sen. Squires Concur with House
    Amendment{4347}; Sen. Squires Motion Reconsideration, MA,VV" (SB 326 of
    2000) is the Senate going back on that day's concurrence, which it then
    refused, and not on its passage of March.

    One that names the third reading alone, where the chamber reads the bill
    a third time again that day, is marked `recon_third` for _j_settle."""
    rc = J_RECONSIDER.search(seg or "")
    if not rc or J_RECON_NOT.search(seg[:rc.start()]):
        return
    o = J_SUSP_CODE.search(seg, rc.end()) or J_SUSP_WORD.search(seg, rc.end())
    if not o or not re.match(r"MA|AA|adopted|carried", o.group(0), re.I):
        return
    mine = [s for s in steps if s["body"] == body]
    if not mine or not mine[-1]["date"] or not date or mine[-1]["date"] >= date:
        return
    end = J_RECON_END.search(seg, rc.end())
    named = re.sub(r"(?i)\([^)]*\)|\b(?:motion|the|of|to|on|by|its|vote|action|whereby)\b|"
                   r"[^A-Za-z]+", " ", seg[rc.end():end.start() if end else len(seg)]).strip()
    if named:
        acts = next((a for rx, a in J_RECON_NAMES if rx.search(named)), set())
        if mine[-1]["act"] not in acts:
            return
    elif not last or _j_act(seg[:rc.start()]) or _j_has_outcome(seg[:rc.start()]):
        return
    mine[-1]["reconsidered"] = date
    if J_THIRD.search(named) and not re.search(r"\bpass|\bOTP|ought", named, re.I):
        mine[-1]["recon_third"] = True


def _j_in_recess(steps):
    """Steps with an answer to the other chamber's amendment that the docket
    dates before the amendment was made put after it, undated.

    A CHAMBER IN RECESS DATES ITS BUSINESS BY THE SITTING IT RECESSED. "House
    Non-Concurs and Requests Committee of Conference (Rep Hinch): MA VV (in
    recess of 6/3/2015)" was entered on 5 June; the Senate passed the
    amendments it refuses on the 4th, and the House Journal of the 3 June
    sitting prints them "Amendments printed SJ 6-4-15". The 1999 and 2005
    budgets' "6/23/1999 House Nonc with Sen Am" and "06/08/2005 House Nonc"
    are the same, a day before the Senate's passage. The day the House acted
    is after the Senate's and the row does not say it, so the line goes after
    the passage it answers with no day, rather than a day before it. Only
    within a week of that passage: HB 109 of 1999's refusal of 30 March is
    the answer to a Senate passage of 25 March its docket writes in words
    the journey does not read, not to the one of October."""
    out = list(steps)
    i = 0
    while i < len(out):
        s = out[i]
        other = {"H": "S", "S": "H"}.get(s["body"])
        # Of the passages that stood: a refusal made in recess answers the
        # passage the other chamber made again after reconsidering one. HB
        # 1409 of 2014's "Non-Concur with Senate AM and request C of C; MA VV
        # (In recess of 5/15/2014)", entered on the 21st, answers the Senate's
        # passage of 16 May, not the one of the 15th it reconsidered.
        later = [j for j, t in enumerate(out) if t["body"] == other
                 and t["act"] == "passed" and t["date"]
                 and not (s.get("_recess") and t.get("reconsidered"))]
        if (s["act"] in ("concurred", "nonconcurred") and s["date"] and later
                and all(out[j]["date"] > s["date"] for j in later)
                and _j_days(out[later[0]]["date"], s["date"]) <= 7 and later[0] > i):
            s["date"] = ""
            out.insert(later[0], out.pop(i))
            continue
        i += 1
    return out


def _j_amended_on(steps):
    """Steps with a chamber's passage amended where the passage it sent to a
    second committee was.

    THE AMENDMENT GOES TO FINANCE WITH THE BILL. SB 538 of 2026 passed the
    House "with Amendment 2026-1453h and 2026-1578h" on 23 April and went to
    Finance, whose report the House passed on 14 May with no amendment of its
    own -- and the rail's House stop read "voice vote", above the Senate
    refusing "the House Amendment" that same day. The passage after the
    second committee is the passage of the bill as the chamber amended it --
    and so is a passage after the chamber reconsidered its first, which
    undoes the vote and not the amendments adopted before it.

    A day's passages are one passage, amended if any was, as _j_merge folds
    them: HB 1462 of 2002's "Ought to Pass with Amendment {3485}, RC 13y -
    11n, AA" and its "OT3rdg, MA, VV" of 16 April, reconsidered on the 18th."""
    held, day = set(), {}
    for s in steps:
        b = s["body"]
        if s["act"] in ("passed", "referred"):
            if day.get(b) == s["date"]:
                s["amended"] = True
            if s.get("amended"):
                day[b] = s["date"]
        if s.get("amended") and (s["act"] == "referred" or s.get("reconsidered")):
            held.add(b)
        elif s["act"] == "passed" and b in held:
            held.discard(b)
            s["amended"] = True
    return steps


def _j_merge(into, st):
    """A second passage of the same sitting, folded into the first: amended
    if either was, and the count of the one that has a count -- but never the
    count of a motion to introduce ("Introduced and Adopted: MA DV 259-66 By
    Necessary Two-Thirds Vote", then "Ought to Pass : MA VV", HB 2023 of
    2022)."""
    into["amended"] = into.get("amended") or st.get("amended")
    # A reconsideration of the third reading is of the passage it is.
    into["reconsidered"] = into.get("reconsidered") or st.get("reconsidered")
    if st.get("intro_adopt"):
        return
    # NOR THE COUNT OF A MOTION TAKEN BEFORE THE AMENDMENT, where the passage
    # that names the amendment states a vote of its own. "OTP MA RC(19-5); SEN
    # F KING FL AM<1494>, WITHDRAWN; SEN SQUIRES FL AM<1504>, AA VV; SEN
    # RUBENS MOVED LOT, ML VV; PASSED WITH AM VV" (HB 723 of 1997) is the
    # Senate voting Ought to Pass 19-5, adopting a floor amendment, and
    # passing the bill so amended on a voice vote, and the rail read "Passed
    # with an amendment, 19–5": the count of the bill before it was amended,
    # beside the words of the bill after. The rail had no rule for a count
    # taken on an earlier motion of the day; this is the one case of it a
    # passage's own words decide. Measured over every history on 2 October
    # 2026 it moves eight Senate and House stops of 1990-1998, each of this
    # shape, two of them a passage counted, reconsidered, and made again
    # amended on a voice vote: "PASSED RC(21-3)", then "SEN DANAIS MOVED TO
    # RECONSIDER, MA VV; SEN RUBENS FL AM<1930> (NEW TITLE), AA VV; PASSED
    # WITH AM VV" (HB 1226 of 1998). Where no later passage names the
    # amendment -- SB 336 of 2002, passed 22-1 and then amended 13-10 on a
    # row of its own -- the count stays the passage's, as it was. Nor where
    # the later passage states no vote at all ("PASSED WITH AM", no VV): it
    # has no count of its own to give, and the earlier one stands.
    if st.get("_own_am") and not into.get("_own_am") and st["vote"][0]:
        into["vote"], into["_own_am"] = st["vote"], True
        into["consent"] = st.get("consent", False)
        into.pop("intro_adopt", None)
        return
    if into.pop("intro_adopt", False) or st["vote"][1] is not None or not into["vote"][0]:
        # And whose count it is (the consent calendar's, decision 51).
        into["vote"], into["consent"] = st["vote"], st.get("consent", False)


def _j_settle(steps):
    """One line a sitting: of a chamber's decisions on one day, the last is
    the one that stood -- a failed motion to pass followed by a kill, a
    passage followed by the table, a kill reconsidered and passed. And a third
    reading after a passage is that passage, not a second one."""
    out = []
    for st in steps:
        prev = out[-1] if out else None
        # The same across the other chamber's rows of that day: HB 282 of
        # 2025 passed the Senate on 26 June, was reconsidered and passed
        # again with a second amendment, and the House's concurrence in both
        # amendments sits between the two rows.
        mine = next((s for s in reversed(out) if s["body"] == st["body"]), None)
        if (st["act"] == "passed" and st["body"] in ("H", "S") and mine is not None
                and mine is not prev and mine["act"] == "passed"
                and mine["date"] == st["date"]):
            _j_merge(mine, st)
            continue
        if (prev and st["body"] in ("H", "S") and prev["body"] == st["body"]
                and prev["date"] == st["date"]):
            if st["act"] == "passed" and prev["act"] in ("passed", "referred") \
                    and st.get("third"):
                # With its count, where the third reading had one:
                # "Ought to Pass with Amendment {1084}, AA, VV; OT3rdg, RC
                # 23Y-1N, MA" (SB 110 of 2001).
                if prev["act"] == "passed":
                    _j_merge(prev, st)
                continue
            if st["act"] == "passed" and prev["act"] == "passed":
                _j_merge(prev, st)
                continue
            # A motion to pass that failed is a substitute motion the clerk
            # wrote AFTER the result it lost to: "ITL REPORT ADOPTED VV; REP.
            # OUELLETTE REMOVED & SUBST OTP, ML VV" (HB 339 of 1989).
            if st["act"] == "failed" and not prev.get("unanswered"):
                continue
            # Passed, then laid on the table before it went anywhere: both
            # happened, and a later day may take it off the table again.
            if prev["act"] in J_PASSING and st["act"] == "tabled":
                out.append(st)
                continue
            # The same two the other way round are the same two: a bill on
            # the table is not passed until it is taken off, which is a row
            # of its own. HB 50 of 2023 has "Lay HB50 on Table: MA DV
            # 206-170" entered before "Ought to Pass with Amendment: MA VV",
            # and died on the table.
            if prev["act"] == "tabled" and st["act"] in J_PASSING:
                out[-1:] = [st, prev]
                continue
            out[-1] = st
            continue
        # Unless that passage was reconsidered: HB 1462 of 2002 passed the
        # Senate on 16 April, was reconsidered on the 18th, and "OT3rdg, MA,
        # VV" that day is it passing again.
        # BUT NOT WHERE ONLY ITS THIRD READING WAS, AND WAS READ AGAIN THAT
        # DAY. The House reconsidered its third reading of 14 March 2012 to
        # take one bill out of it, and read the other fourteen a third time
        # again: "Reconsider Third Reading Motion of March 14: MA VV", then
        # "Third Reading: MA VV". HB 1282's passage, 180-133 on the 14th,
        # read "reconsidered on 15 Mar", as if that vote had been undone, and
        # the rail showed the voice vote of the repeated reading in its
        # place. The reading again is the passage it was, as a third reading
        # on a later day always is.
        if st.get("third") and st["act"] == "passed":
            mine = [s for s in out if s["body"] == st["body"]]
            if mine and mine[-1]["act"] == "passed":
                last = mine[-1]
                if last.get("recon_third") and last.get("reconsidered") == st["date"]:
                    last.pop("reconsidered")
                    last.pop("recon_third")
                if not last.get("reconsidered"):
                    continue
        out.append(st)
    # A motion to table the clerk gave no vote for stands only as the
    # chamber's last word.
    return [s for i, s in enumerate(out) if not s.get("unanswered") or not any(
        t["body"] == s["body"] for t in out[i + 1:])]


def journey_state(steps, body):
    """p, x or h: where a chamber's own decisions left the bill, or "" where
    it made none."""
    mine = [s for s in steps if s["body"] == body]
    return mine[-1]["mark"] if mine else ""


def journey_rail(intro, steps, rail, bid, status="", chip="", tabled=None):
    """The rail's stops for a bill's own view, dated from the journey.

    The marks are the index's -- the same `passage` the list card draws -- so
    the card and the page cannot disagree about a stop; the journey gives
    each one its date, its word (`short`, which only the index row keeps, for
    the sentence its card says) and its sentence (`say`). The stops follow
    the bill's route: a resolution of one chamber has that chamber; a
    concurrent resolution two chambers and no governor; a CACR goes to the
    voters instead of the governor, with the ring on Voters while it waits
    for them.

    `chip` is the bill's chip (chip_word), which two marks of the rail's own
    refine (RAIL_REFINES, the person, 8 October 2026): the chamber's stop
    where an Interim Study bill was held is the orange "~", "s", where
    `passage` says only that it stopped there; and where a Tabled bill lies
    on the table while the session still sits, its stop and the line of the
    journey that laid it there are the yellow pause, "t", where `passage`
    has the ring of a bill still moving.

    A BILL THAT DIED ON THE TABLE IS PAUSED WHERE IT WAS TABLED (the person,
    8 October 2026: "Show the body it was tabled in with the yellow pause,
    and show the red x mark on the law once it died when the session
    ended"). `tabled` is the line that laid it on the table it died on
    (died_on_table), on a Died bill: that chamber's stop, the cross of a bill
    stopped there, is the pause, dated and worded by that line, and so is the
    line; the Law stop keeps the cross, on the day it died (law_day, which
    takes the line of the death that died_on_table makes). A chamber that
    passed the bill before laying it on the table -- HB 609 of 2026, which
    the House tabled after both chambers had passed it -- keeps its check,
    and only the line is the pause.

    THE STOP SAYS WHAT ITS MARK SAYS (the review of 8 October 2026). A
    refined stop takes its day and its words from the chamber's last line of
    the act its mark stands for (RAIL_ACT): the cross's stop was given the
    chamber's last kill, so HB 1171 of 2000 -- killed by the Senate on 20
    April 2000, the kill reconsidered, and sent to interim study on 18 May --
    drew the "~" over "Killed on a voice vote, reconsidered on 18 May", dated
    20 April, and HB 146 of 2002 the same. Where the chamber has no such line
    (SB 225 of 2000, whose "Refer to Interim Study; SJ 2" no line reads), the
    stop says the mark's own words and no day, as a stop with no line does."""
    stops = _journey_rail(intro, steps, rail, bid, status)
    if tabled is not None and chip == DIED:
        name = {"H": "House", "S": "Senate"}.get(tabled.get("body"))
        for st in stops:
            if st["stop"] == name and st["mark"] == RAIL_DEAD_TABLE[1]:
                st.update(mark=RAIL_DEAD_TABLE[0], date=tabled.get("date", ""),
                          short=tabled.get("short", ""),
                          say=tabled.get("text", "") or RAIL_SAY[RAIL_DEAD_TABLE[0]])
        tabled["mark"] = RAIL_DEAD_TABLE[0]
        return stops
    now = RAIL_MARK_OF_CHIP.get(chip)
    if not now:
        return stops
    was = RAIL_REFINES[now]
    for st in stops:
        if st["stop"] in ("House", "Senate") and st["mark"] == was:
            st["mark"] = now
            b = "H" if st["stop"] == "House" else "S"
            line = next((s for s in reversed(steps)
                         if s["body"] == b and s["act"] == RAIL_ACT[now]), None)
            st.update(date=(line or {}).get("date", ""), short=(line or {}).get("short", ""),
                      say=(line or {}).get("text", "") or RAIL_SAY[now])
            if now == "t" and line is not None:
                line["mark"] = "t"
    return stops


# The rail's own marks, which `passage` does not draw: the stop where a bill
# was held for interim study, and the stop where it lies on the table now
# (journey_rail). Each refines the passage letter it stands in for, which is
# what the list card's and the page's rails are held to (_journey_story in
# preflight).
RAIL_MARK_OF_CHIP = {INTERIM_STUDY: "s", TABLED: "t"}
RAIL_REFINES = {"s": "x", "t": "h"}
# The journey's act each of them stands for, whose line dates and words the stop.
RAIL_ACT = {"s": "study", "t": "tabled"}
# And the pause on a Died bill, where the cross of the chamber whose table it
# died on was (journey_rail's `tabled`, the person, 8 October 2026).
RAIL_DEAD_TABLE = ("t", "x")


def _journey_rail(intro, steps, rail, bid, status=""):
    """journey_rail's stops with the marks `passage` gives them."""
    if not rail or rail[0] not in ("H", "S"):
        return []
    origin = rail[0]
    other = "S" if origin == "H" else "H"
    marks = rail[1:]
    pre = bill_prefix(bid)
    stops = [{"stop": "Introduced", "mark": "p", "date": intro or "",
              "short": "", "say": "Introduced"}]

    def chamber(b, mark):
        mine = [s for s in steps if s["body"] == b]
        pick = None
        if mark == "p":
            pick = (next((s for s in reversed(mine) if s["act"] in ("passed", "adopted")), None)
                    or next((s for s in reversed(mine) if s["act"] == "referred"), None))
        elif mark in ("x", "h"):
            pick = (next((s for s in reversed(mine) if s["mark"] == "x"), None)
                    if mark == "x" else None) or (mine[-1] if mine else None)
        name = {"H": "House", "S": "Senate"}[b]
        return {"stop": name, "mark": mark, "date": (pick or {}).get("date", ""),
                "short": (pick or {}).get("short", ""),
                "say": (pick or {}).get("text", "") or RAIL_SAY.get(mark, "")}

    if len(marks) == 2:
        return stops + [chamber(origin, marks[0])]
    stops += [chamber(origin, marks[0]), chamber(other, marks[1])]
    if pre == "CACR":
        v = next((s for s in steps if s["body"] == "V"), None)
        low = (status or "").lower()
        when = re.search(r"in ([A-Z][a-z]+) (\d{4})", status or "")
        if v:
            stops.append({"stop": "Voters", "mark": v["mark"], "date": v["date"],
                          "short": v["short"], "say": v["text"]})
        elif "goes to the voters" in low:
            said = status.split(", ", 1)[-1]
            stops.append({"stop": "Voters", "mark": "h", "date": "",
                          "short": (f"{when.group(1)[:3]} {when.group(2)}" if when else ""),
                          "say": said[:1].upper() + said[1:]})
        elif "went to the voters" in low:
            stops.append({"stop": "Voters", "mark": "-", "date": "",
                          "short": "not recorded",
                          "say": "Went to the voters; the docket does not record "
                                 "their answer"})
        else:
            stops.append({"stop": "Voters", "mark": "-", "date": "", "short": "",
                          "say": RAIL_SAY["-"]})
        return stops
    if pre in NO_GOVERNOR:
        return stops
    gm, lm = marks[2], marks[3]
    g = next((s for s in steps if s["body"] == "G"
              and (s["act"] == "vetoed") == (gm == "x")), None)
    law = next((s for s in steps if s["body"] == "L"), None)
    stops.append({"stop": "Governor", "mark": gm,
                  "date": g["date"] if g and gm in ("p", "x") else "",
                  "short": g["short"] if g and gm in ("p", "x") else "",
                  "say": g["text"] if g and gm in ("p", "x") else RAIL_SAY.get(gm, "")})
    stops.append({"stop": "Law", "mark": lm, "date": law_day(lm, law, stops, steps),
                  "short": law["short"] if law and lm == "p" else "",
                  "say": ((law.get("shown") or law["text"]) if law and lm == "p"
                          else "Did not become law" if lm == "x"
                          else RAIL_SAY.get(lm, ""))})
    return stops


def law_day(mark, law, stops, steps):
    """The day under the rail's last stop, Law (the person, 7 October 2026,
    F13): "under Law, the effective date when it became law; when killed, the
    day it was killed under that last stop". The Law stop was the one stop
    reached that carried no day.

    A law: the day it took effect, where its lines state one day
    (_j_effective) -- a law in effect on several dates, by section, states
    none, and neither does its stop. A bill that did not become law: the day
    it was stopped, which is the latest day of a decision that ended it, on
    a stop or in the journey (a kill, a veto sustained, a conference report
    rejected), and the line of a death the session's end made, on the table
    or in interim study (died_on_table, study_ending). A Law stop not
    reached -- a bill still moving, or held for interim study while its
    session still sits -- has no day, as no stop not reached has."""
    if mark == "p":
        return (law or {}).get("effective", "") if law else ""
    if mark != "x":
        return ""
    days = [s.get("date") or "" for s in stops if s.get("mark") == "x"]
    days += [s.get("date") or "" for s in steps if s.get("mark") == "x"]
    return max((d for d in days if d), default="")


# What a stop says when no line of the journey fills it -- the same words the
# list card's rail uses.
RAIL_SAY = {"p": "Passed", "h": "Is here now", "x": "Stopped here",
            "-": "Never reached", "s": "Sent to interim study", "t": "On the table"}


# The decisions that end a bill in the chamber that makes them.
J_ENDING = {"killed", "died", "postponed", "study", "failed", "sustained",
            "conf_rejected", "conf_refused"}
