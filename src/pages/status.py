#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A bill's status: the General Court's own status words read against what a
bill of each kind has to clear (STATED, for_bill_kind, classify_stated), the
docket alone for a bill the status page does not cover (classify), a last
paragraph for a bill whose ending the docket never narrates (closing_stage),
and what happens next (next_step).

    import status as STA
    STA.classify_stated(st, "HR")              # (state, label) from the status fields, or None
    STA.classify(narr, rcs, "HB", bid, term)   # (state, label) from the docket alone
    STA.next_step(narr, bill, "HB")            # "Pending a vote of the full chamber"

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: status classification). It moved here as
it stood, comments and all, in its three places' order: the status vocabulary
(for_bill_kind to NEVER_INTRODUCED), journal_not_introduced, and
classify_stated to next_step. What it reads of build_site_v2 and is no one
subsystem's is parts.py's; the journey and the passage rail are journey.py's
and what the two chambers did with each other's version conferences.py's, so
this imports no builder (_import_cycles_cut). build_site_v2 imports every name
here back under its own, so build_site_v2.classify and the rest answer as
they did, for bill_disposition, build_bills and the checks.
"""

import re
from datetime import date as _date

import shell as _shell
from conferences import CONF_UNABLE, conference_failure, conference_not_taken_up
from journey import journey, passage
from parts import BILL_OF_INTENT, NO_GOVERNOR, SIGNED_RE, SINGLE_CHAMBER, TABLE_DEATH

def for_bill_kind(needle, kind, label, prefix):
    """The same status word, read against what that kind of bill needs.

    "PASSED/ADOPTED" on a House Bill means one chamber down and one to go. On
    a House Resolution it is the final action. The status page does not make
    the distinction because it does not have to -- the reader knows which kind
    of thing they asked about, and this site has to say so.
    """
    if needle == "passed/adopted" and prefix in SINGLE_CHAMBER:
        return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
    if needle == "concurred" and prefix in NO_GOVERNOR:
        if prefix == "CACR":
            return "adopted", "Passed both chambers, goes to the voters"
        return "adopted", "Adopted by both chambers"
    return kind, label


STATED = [
    ("signed by governor", "law", "Signed into law"),
    # The field says "LAW WITHOUT SIGNATURE"; the needle wanted "became law
    # without signature" and so never matched it. Nine bills. Masked until
    # now because docket_outcome rescued every one of them from the docket.
    ("law without signature", "law", "Became law unsigned"),
    # The three outcomes of a veto, most specific first. A bill awaiting the
    # override vote, one where the override failed, and one where it succeeded
    # are three different situations, and lumping them as "Vetoed" hides the
    # only part anyone wants to know.
    #
    # SUSTAINED BEFORE OVERRIDDEN, as classify() already has it for the
    # docket: an override needs two-thirds in both chambers, so one chamber
    # sustaining ends the bill whatever the other did. The fields are read
    # together, and a bill whose House field says VETO OVERRIDDEN and whose
    # Senate field says VETO SUSTAINED read "Veto overridden, became law" --
    # eleven of them, 1989 to 2012, every one confirmed by its docket as an
    # override that failed in the second chamber. The fourteen in terms with
    # a narrated docket were rescued by docket_outcome.
    ("veto sustained", "veto", "Vetoed, override failed"),
    ("override failed", "veto", "Vetoed, override failed"),
    ("veto overridden", "law", "Veto overridden, became law"),
    ("override adopted", "law", "Veto overridden, became law"),
    ("veto override", "veto", "Vetoed, override vote pending"),
    ("vetoed by governor", "veto", "Vetoed, awaiting an override vote"),
    ("inexpedient to legislate", "done", "Killed"),
    # OUGHT NOT TO PASS, ADOPTED, IS THE CHAMBER'S REJECTION: BodyStatusCodes.txt
    # code 26, the House's field on five addresses for the removal of a judge
    # -- HA 1 of 1999, of 2006 and of 2018, HA 1 and HA 3 of 2010 -- each of
    # whose dockets has the House adopting that report ("Ought Not to Pass: MA
    # DIV 220-106"). With no row here they read "In committee" or "In
    # progress". "Killed" is the word this site gives a chamber's adopted
    # rejection: HA 1 of 2015, ended by Inexpedient to Legislate, reads it.
    ("ought not to pass", "done", "Killed"),
    ("died on the table", "done", "Died on the table"),
    ("died, session ended", "done", "Died when the session ended"),
    # Parked for the committee to work on out of session, not killed.
    ("interim study", "study", "Referred for interim study"),
    ("indefinitely postponed", "done", "Indefinitely postponed"),
    ("laid on table", "active", "Laid on the table"),
    ("retained in committee", "active", "Retained in committee"),
    # The docket hyphenates; BodyStatusCodes.txt code 21 does not.
    ("re-referred", "active", "Re-referred to committee"),
    ("rereferred", "active", "Re-referred to committee"),
    # BEFORE "concurred", which is a substring of both of these. 21 bills
    # were live reading "Passed, awaiting the governor" when a chamber had
    # refused to concur -- the opposite of what happened, on the field the
    # site treats as most authoritative. BodyStatusCodes.txt has all three
    # as separate codes: 12 CONCURRED, 13 NONCONCURRED, 14 NONCONCURRED
    # REQUEST CONFERENCE.
    ("nonconcurred request conference", "active",
     "One chamber did not concur; a committee of conference was asked for"),
    ("nonconcurred", "active", "One chamber did not concur"),
    ("concurred", "active", "Passed, awaiting the governor"),
    ("passed/adopted", "active", "Passed one chamber"),
    ("in committee", "active", "In committee"),
    # A CHAMBER REFUSED TO INTRODUCE THE BILL: BodyStatusCodes.txt code 24,
    # in the General Court's own words. SB 267 of 2007 and SB 499 of 2016
    # carry it in their Senate field and nothing else -- the Senate voted
    # down the motion to introduce each -- and with no row here they read
    # "In committee", a committee neither ever reached. LAST, so that it is
    # the answer only where nothing above is: HB 2002 and HCO 1 of 2002
    # passed the House before the Senate refused them, and stay "Passed one
    # chamber".
    ("refused introduction", "done", "Refused introduction"),
]

# The statuses of a bill that was never introduced: the passage rail starts
# at Introduced, and none is drawn for these (build_bills).
WITHDRAWN_PRIOR = "Withdrawn prior to introduction"
PROPOSED_ONLY = "Proposed for the special session"
# AND ONE WHOSE DOCKET SAYS "INTRODUCED" AND WHOSE HOUSE DID NOT INTRODUCE IT.
# HB 87 and HB 134 of 2009 and HB 633 of 2007 each have one docket row, the
# introduction row typed ahead of the day, and the House's resolution of
# introduction steps over each number (build_data.INTRODUCTION_FROM_JOURNAL;
# narrative.build types the row entered_introduced). Nothing on disk says
# what became of them -- withdrawn, most likely, and no row says so -- so the
# status says the one thing the record bears out. HB 177, HB 273, HB 274 and
# HB 277 of 2017 are the same, on records the bill search's own list carries.
NOT_INTRODUCED = "Not introduced"
NEVER_INTRODUCED = {"Refused introduction", WITHDRAWN_PRIOR, PROPOSED_ONLY, NOT_INTRODUCED}


def journal_not_introduced(narr):
    """Whether the bill's history is one the House Journal's resolution of
    introduction decided against its docket: narrative.build found the
    record's reading, typed the docket's introduction row entered_introduced
    and marked the bill not_introduced. The one question classify() and
    bill_disposition() both ask."""
    return bool((narr or {}).get("not_introduced")) and any(
        e.get("type") == "entered_introduced" for e in (narr or {}).get("events", []))


def classify_stated(st, prefix="", origin=""):
    """Map the page's own status wording to a display state, or None.

    Scans every status field at once and takes the most specific match, rather
    than the first field that matches anything. Checking gen_status first meant
    a bill whose override had already failed still read "VETOED BY GOVERNOR" and
    came out as awaiting a vote, because the general field never catches up with
    the chamber's.
    """
    blob = " ".join((st.get(f) or "").strip().lower()
                    for f in ("gen_status", "house_status", "senate_status"))
    if not blob.strip():
        return None
    hit = next(((n, k, l) for n, k, l in STATED if n in blob), None)
    # A RESOLUTION BOTH CHAMBERS PASSED IS FINISHED, and "passed/adopted" is
    # in every such record's fields -- so the STATED row below answered
    # "Passed one chamber" for 151 of them (CACR 13 of 2026 among them, its
    # own status box saying "Senate: PASSED/ADOPTED"), and the bare-PASSED
    # fallback at the foot of this function was never reached. What says
    # both chambers are done is the SECOND chamber's own field reading
    # PASSED/ADOPTED without amendment -- nothing is left to concur in.
    # gen_status PASSED is not enough on its own: HCR 10 and HCR 11 of 2024
    # carry it with no Senate action in their dockets at all. Only where
    # nothing more decisive is stated: a resolution a field says was killed
    # stays so.
    if prefix in NO_GOVERNOR and (hit is None or hit[0] in ("passed/adopted", "in committee")):
        second = (st.get("senate_status" if (origin or "H") == "H" else "house_status")
                  or "").strip().lower()
        if second.startswith("passed/adopted") and "amend" not in second:
            if prefix == "CACR":
                return "adopted", "Passed both chambers, goes to the voters"
            return "adopted", "Adopted by both chambers"
    if hit:
        return for_bill_kind(*hit, prefix)
    # Nothing in the table matched. GeneralCodes.txt code 04 is "PASSED", and
    # the table does not carry it because for a bill it says nothing the docket
    # does not say better -- passed the legislature, governor next. For a
    # resolution it is the whole answer, and HR35 sat on "In progress" with
    # gen_status PASSED and an adopted floor vote behind it. Asked last, and
    # only of resolutions, so it cannot shadow a more specific outcome.
    if "passed" in blob:
        if prefix in SINGLE_CHAMBER:
            return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
        if prefix == "CACR":
            return "adopted", "Passed both chambers, goes to the voters"
        if prefix in NO_GOVERNOR:
            return "adopted", "Adopted by both chambers"
    return None


# How a bill ends when the docket does not say so.
#
# The docket records actions, and a session ending is not an action: it just
# stops. For 111 bills the last line is a committee report and the status page
# alone knows the bill died with the term, so the page showed a red headline
# over a history that trailed off mid-sentence -- the status said one thing and
# the story below it said nothing at all.
#
# Each of these says what happened and what it means, because "DIED, SESSION
# ENDED" is the General Court's phrase rather than a plain-English one.
CLOSING = {
    # label: (phrases that mean the history ALREADY says it, the paragraph)
    #
    # The guards are per outcome, and they have to be. A first attempt tested
    # for "kill it" anywhere in the narrative and matched every bill whose
    # committee recommended that the chamber kill it -- which is a committee
    # report, not an ending, and it suppressed the paragraph on all 111.
    "Died when the session ended": (
        ("session ended", "died when the session", "died on the table"),
        # "THE BILL ITSELF", because a vote on a motion about it is still a
        # vote. HB 1420, HB 1223 and CACR 19 of 2026 each met a motion to
        # take it up out of order that failed on a division -- HB 1420's
        # 141-203 -- and then nothing more, and
        # the page said "No vote was ever taken on it" over the tally. The
        # journey counts decisions on the bill, not procedural motions, so
        # the sentence claims exactly that much.
        "Neither chamber ever voted on the bill itself, and it died when the "
        "session ended. That is a procedural end rather than a decision -- much like a "
        "bill left on the table, it ran out of time -- and it would have to be "
        "filed again as a new bill in a later term."),
    "Indefinitely postponed": (
        ("indefinitely postpone",),
        "The chamber voted to indefinitely postpone it. That ends the bill for "
        "the term and, under the rules, bars the same subject from being taken "
        "up again before the term is out."),
    # CONF_UNABLE. The history says "adopted Conference Committee Report"
    # and no more, which is the one reading this paragraph must not leave
    # standing: what the chambers adopted was the conferees' word that they
    # could not agree.
    "Died: conferees could not agree": (
        ("could not agree", "unable to agree"),
        "The committee of conference -- members of both chambers named to settle "
        "the differences between the House and Senate versions -- could not "
        "agree on one, and reported that it was unable to agree. With no version "
        "that both chambers had accepted, the bill went no further, and it died."),
    # "Killed" is deliberately NOT here. The status page reports it for bills
    # whose docket already says what ended them -- 28 were laid on the table
    # and died there, and the narrative says so in as many words -- so a
    # paragraph claiming "the docket does not record the vote that ended it"
    # would have been false on most of the bills it appeared under.
}

# The same ending where the conferees filed no report saying so: the paragraph
# says what the docket says, which is that no report was signed, or none
# filed, or that the bill died in the committee (conference_failure's word
# for the row). "Reported that it was unable to agree" would be a report the
# record does not have.
CONF_UNABLE_CLOSING = {
    how: ("The committee of conference -- members of both chambers named to "
          "settle the differences between the House and Senate versions -- could "
          f"not agree on one, and {said}. With no version that both chambers had "
          f"accepted, {rest}")
    for how, said, rest in (
        ("unsigned", "no report was signed", "the bill went no further, and it died."),
        ("unfiled", "no report was filed", "the bill went no further, and it died."),
        ("died", "the bill died in the committee", "it went no further."))}


# "No vote was ever taken on it" is a claim, and on 35 of the 111 bills of
# 2025-2026 that carried it the docket records one: HB 243 passed both
# chambers and went to a committee of conference that never reported; CACR 8
# passed the Senate 21-3 and failed in the House, 203-158. Where a chamber
# decided anything, this is what the ending was instead.
SESSION_ENDED_AFTER_VOTES = (
    "It had not finished its passage when the session ended, and the bill died "
    "then. That is a procedural end rather than a decision -- it ran out of "
    "time -- and it would have to be filed again as a new bill in a later term.")


# AND "IT RAN OUT OF TIME" IS A CLAIM TOO, which the record can contradict.
# SSSB 1 of the 2010 special session passed the Senate 14-9 and the House
# voted it down 141-191 an hour before "Died, Session Ended": the paragraph
# above called that "a procedural end rather than a decision". HB 1534 of
# 2016's last row is "Pursuant to House Rule 35e HB 1534 returned to the
# Senate", and HB 1048, HB 1216 and HB 1562 of 2026 were "returned to the House
# per Senate Rule 3-21": sent back, which is not the clock.
SESSION_ENDED_AFTER_FAILED = (
    "The last vote on it was a motion to pass it, which failed, and nothing more "
    "was done on it before the session ended. It would have to be filed again as "
    "a new bill in a later term.")
# Where the record shows something else than time running out -- a measure
# one chamber sent back to the other: what is known, and no more.
SESSION_ENDED_PLAINLY = (
    "It had not finished its passage when the session ended, and the bill died "
    "then. It would have to be filed again as a new bill in a later term.")
# A measure one chamber sent back to the other.
RETURNED_ROW = re.compile(r"\breturned\s+to\s+(?:the\s+)?(?:house|senate)\b", re.I)

# WHERE THE ENDING IS THIS SITE'S READING OF A FINISHED TERM (ended_with_the_
# term), THE PARAGRAPH DATES NOTHING. The General Court never said when these
# died. Seventy House measures of 2021 were reported and never voted on
# before the House's deadline of 9 April 2021, in the first year of their
# term, and "it died when the session ended ... it ran out of time ... a
# later term" gave them a day and a cause the record does not. What is known
# is what was not done.
ENDED_UNVOTED = (
    "Neither chamber ever voted on the bill itself, and the record shows nothing "
    "more done on it. It went no further.")
ENDED_UNFINISHED = (
    "It had not finished its passage, and the record shows nothing more done on "
    "it. It went no further.")
# And where the docket says what stopped it: a chamber asked to suspend its
# rules for a conference report after the deadline, and refusing. "Sen.
# Wheeler Rules Suspension; To Allow C of C Report After Deadline 2/3 nec.,
# MF" is HB 1410 of 2002's last row, the day after "(Conf Comm Report Not
# Signed)"; "MOVED TO SUSP RULES FOR CONF COMM REPT, FAILED 2/3RC(185-133)"
# is SB 437 of 1998's.
CONF_REPORT_NOT_TAKEN_UP = (
    "The {chamber} voted on suspending its rules to take up the committee of "
    "conference's report, and the motion failed. The report was not taken up, and "
    "the bill went no further.")
# And where the House Journal says the conference never reported
# (CONFERENCE_NOT_REPORTED).
CONF_NEVER_REPORTED = (
    "The committee of conference it was last sent to -- members of both chambers "
    "named to settle the differences between the House and Senate versions -- "
    "never reported: {journal}. Nothing more is recorded on the bill, and it went "
    "no further.")

# THE DECISION THE STATUS RESTS ON, WHERE THE HISTORY ABOVE DOES NOT TELL IT.
# The history is told from the rows narrative.py reads, and the status from
# the journey, which reads more of them. SB 95 of 2001 "Died when the
# conference report was rejected" under a history whose last sentence had the
# House adopting the report 196-159: the Senate's "Conference Committee Report
# RC 11Y-13N, Non Adopt" is a row no pattern tells. SB 305 of 2016's ended at
# the conference's meetings, over "Conference Committee Report Not Accepted by
# House pursuant to House Rule 49(j)"; CACR 2 of 2004 "Failed to pass" under
# a floor stage that ends on an amendment adopted, because "OTP/AM failed 3/5
# RC(186-172)" is left untold on purpose (docket_era_1999: no sentence there
# can say it without reading as 186 voting it down). Where the journey's last
# decision is a conference report rejected or a vote to pass that failed, and
# the row it was read from is one the history does not tell (journey's
# `untold`), this says it, in the journey's own words and with its day.
ENDING_UNTOLD = {
    "conf_rejected": ("{when} {chamber} {did}. A conference report has to be adopted by "
                      "both chambers, so the bill went no further."),
    "failed": "{when} {chamber} voted on the motion to {verb} it, and the motion failed{how}.",
}
UNTOLD_FOR = {"Died when the conference report was rejected": "conf_rejected",
              "Failed to pass": "failed"}


def _long_date(iso):
    """"2001-06-26" -> "June 26, 2001", or "": shell.date_words."""
    try:
        d = _date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return _shell.date_words(d, "full")


def untold_ending(label, steps, untold):
    """The paragraph for a status whose deciding row the history does not tell
    (ENDING_UNTOLD), or None. `untold` is the ids of the journey's lines read
    from such a row, as journey() fills it."""
    act = UNTOLD_FOR.get(label)
    last = next((s for s in reversed(steps or []) if s.get("body") in ("H", "S")), None)
    if not act or not last or last.get("act") != act or id(last) not in (untold or ()):
        return None
    chamber = {"H": "the House", "S": "the Senate"}[last["body"]]
    day = _long_date(last.get("date") or "")
    when = f"On {day}" if day else ""
    text = last.get("text") or ""
    if act == "conf_rejected":
        said = ENDING_UNTOLD[act].format(when=when, chamber=chamber,
                                         did=text[:1].lower() + text[1:])
    else:
        head = next((h for h in ("Failed to pass", "Not adopted") if text.startswith(h)), None)
        if head is None:
            return None
        said = ENDING_UNTOLD[act].format(
            when=when, chamber=chamber, verb="adopt" if head == "Not adopted" else "pass",
            how=text[len(head):])
    said = said.strip()
    return {"label": "How It Ended", "text": said[:1].upper() + said[1:]}


def closing_stage(label, narr, decided=False, steps=None, inferred=False,
                  untold=None, journal=""):
    """A last paragraph for a bill whose ending the docket never narrates.

    The docket records actions, and a session ending is not an action: it just
    stops. For 111 bills the last line is a committee report and only the
    status page knows the bill died with the term, so a settled red headline
    sat above a history that trailed off mid-sentence.

    `decided` is whether the journey has a chamber deciding anything on the
    bill. Returns None where the history already says it.

    `steps` is the journey's lines, where the caller has them, and `inferred`
    whether the ending is this site's reading of a finished term rather than
    the General Court's word (ended_with_the_term): together they say which
    of the session-ended paragraphs the record bears out. `untold` is the
    journey's lines read from rows the history does not tell, and `journal`
    what the House Journal says of a conference that never reported
    (CONFERENCE_NOT_REPORTED).
    """
    said = untold_ending(label, steps, untold)
    if said:
        return said
    hit = CLOSING.get(label)
    if not hit:
        return None
    guards, text = hit
    told = " ".join(s.get("text", "") for s in (narr or {}).get("stages", [])).lower()
    if any(g in told for g in guards):
        return None
    if inferred and label == "Died when the session ended":
        evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
        row = conference_not_taken_up(evs)
        if journal:
            text = CONF_NEVER_REPORTED.format(journal=journal)
        elif row is not None and (row.get("body") or "")[:1].upper() in ("H", "S"):
            text = CONF_REPORT_NOT_TAKEN_UP.format(
                chamber={"H": "House", "S": "Senate"}[row["body"][:1].upper()])
        else:
            text = ENDED_UNFINISHED if decided else ENDED_UNVOTED
    elif decided and label == "Died when the session ended":
        text = SESSION_ENDED_AFTER_VOTES
        last = next((s for s in reversed(steps or []) if s.get("body") in ("H", "S")), None)
        if last and last.get("act") == "failed":
            text = SESSION_ENDED_AFTER_FAILED
        elif any(RETURNED_ROW.search(e.get("raw") or "")
                 for e in (narr or {}).get("events", [])
                 if not e.get("cancelled")):
            text = SESSION_ENDED_PLAINLY
    if label == CONF_UNABLE:
        failed = conference_failure([e for e in (narr or {}).get("events", [])
                                     if not e.get("cancelled")])
        text = CONF_UNABLE_CLOSING.get((failed or ("unable",))[0], text)
    return {"label": "How It Ended", "text": text}


def veto_votes(evs):
    """Each chamber's last word on a veto, {body: "law" or "veto"}: "law"
    where it overrode, "veto" where it sustained. veto_outcome reads the
    answer from it, and bill_disposition whether only one chamber has voted."""
    said = {}
    for e in evs:
        raw = (e.get("raw") or "").lower()
        word = (e.get("outcome") or "").lower()
        body = (e.get("body") or "").upper() or "?"
        if "veto sustained" in raw or word == "sustained":
            said[body] = "veto"
        elif ("veto overridden" in raw or "veto overriden" in raw
              or "=veto override=" in raw or word == "overridden"):
            said[body] = "law"
    return said


def veto_outcome(evs):
    """What became of a veto, read per chamber and in order, or None.

    An override needs two-thirds in BOTH chambers, so one chamber sustaining
    ends the bill whatever the other did -- SB 434 of 2026, where the Senate
    overrode 16Y-8N and the House sustained 165-140 the same day. But a
    chamber may reconsider its own vote: HB 542 of 2011 was sustained
    244-130, reconsidered, and overridden 255-112 that morning, and it is
    Chapter 271. So the answer is each chamber's LAST word, and a sustain by
    either of them wins.
    """
    said = veto_votes(evs)
    if not said:
        return None
    if "veto" in said.values():
        return "veto", "Vetoed, override failed"
    return "law", "Veto overridden, became law"


def docket_outcome(narr):
    """The outcome as the DOCKET states it, or None.

    classify_stated already knows the status page lags: its own note records a
    bill whose override had failed still reading VETOED BY GOVERNOR because
    "the general field never catches up with the chamber's". The docket is the
    same official source and does not lag -- it carries a dated line the day
    the vote happens.

    HB 396 is the case. The House sustained the veto on 19 August; the status
    page still says "Senate: PASSED/ADOPTED WITH AMENDMENT", which was true in
    May and is the Senate's last action rather than the bill's state. So a
    dated outcome in the docket outranks a summary field that has not caught
    up, and only for this family, where the lag is known.

    Sustained is tested before overridden for the reason it always is: both
    chambers must override, so one sustaining ends the bill.
    """
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    text = " ".join(e.get("raw", "") for e in evs).lower()
    # THE LAST OUTCOME IN THE RECORD, for the reason classify() gives: one
    # chamber sustaining ends the bill (SB 434), but a chamber may reconsider
    # and override an hour later (HB 542 of 2011, Chapter 271).
    outcome = veto_outcome(evs)
    if outcome:
        return outcome
    if ("without the signature of the governor" in text
            or "law without signature" in text):
        return "law", "Became law unsigned"
    # And the signature itself, for the same reason and on the same evidence.
    # The status page carries no governor field for 219 bills whose docket
    # records the day the governor signed them and the chapter number they
    # became -- so they read "Passed one chamber", "Passed, awaiting the
    # governor", "In committee" or, for five of them, "Killed". The page is
    # describing the last thing it was told; the docket is describing what
    # happened.
    if SIGNED_RE.search(text):
        return "law", "Signed into law"
    return None


# A floor motion the chamber ADOPTED that finishes the bill.
#
# Read from the motion code and the action, not from a substring of the whole
# docket. classify() below tests `"inexpedient to legislate" in text`, and that
# phrase appears in every MINORITY report as well -- which is how HCR1, HCR4
# and HCR9 came to read "Killed" when the House had adopted Ought to Pass on
# them 197-156, 195-149 and 204-163.
#
# A WITHDRAWAL THE CHAMBER ADOPTED FINISHES THE BILL TOO (30 September 2026).
# "Withdrawn Under House Rule 38(e) (Rep Cebrowski): MA VV" is HB 641 of
# 2013, and "Withdrawn Pursuant to House Rule 38(e) (Rep Coulombe): MA VV" HB
# 1186 of 2012; both read "In committee", over a docket that withdrew them.
# The action has to BEGIN with the withdrawal -- "REP. HEALY SUB ITL,
# WITHDRAWN; PASSED VV" is a motion withdrawn, not a bill, and "Withdraw From
# Joint Committee" is not "Withdrawn" -- and only an adopted one counts, as
# for every row here: "Persuant to House Rule 39(e), Withdrawn: MF RC
# 160-207" is HB 431 of 2025, which the House then passed. The rule is cited
# with "to" and without -- "Persuant House Rule 39(e), Withdrawn: MF DV" is
# SB 78 of 2025 -- and "Per House Rule 38, Withdrawn from Committee" is a
# committee discharged, not a bill withdrawn.
WITHDRAWN_ACT = re.compile(
    r"^\s*(?:(?:p[eu]r?s?uant(?:\s+to)?|per)\s+(?:house|senate)\s+rule\s+[\w.]+"
    r"(?:\s*\(\w\))?\s*,?\s*)?withdrawn\b(?!\s+from)", re.I)
DISPOSED = [
    (re.compile(r"inexpedient to legislate", re.I), ("done", "Killed")),
    # The motion a chamber carried, never a committee's report of the same
    # words: floor_disposed reads the floor rows a chamber adopted, and HA 2
    # of 2010 and HB 31 of 2023 carry "Ought Not to Pass" on a report alone.
    (re.compile(r"ought not to pass", re.I), ("done", "Killed")),
    (re.compile(r"indefinitely postpone", re.I),
     ("done", "Indefinitely postponed")),
    (re.compile(r"interim study", re.I), ("study", "Referred for interim study")),
    (WITHDRAWN_ACT, ("done", "Withdrawn")),
]
# A reconsideration the chamber carried, as a clause of a floor line:
# "Rep Norelli moved to Reconsider, MA RC(153-150)". See classify().
RECONSIDER_CARRIED = re.compile(r"(?i:\breconsider\w*)[^;]*?\bMA\b")
# Where a bill's record is the House Journal's rather than the General
# Court's files (journal_bills.py, build_data.add_journal_bills).
JOURNAL_SOURCE = "House Journal"


def floor_disposed(narr):
    """The last adopted floor motion that finished the bill, or None.

    A later adopted motion that is NOT a disposal clears an earlier one: a bill
    killed, reconsidered and then passed is not killed, and the docket records
    that as two adopted motions in order.
    """
    out = None
    for e in sorted((narr or {}).get("events", []),
                    key=lambda x: x.get("date") or ""):
        if e.get("cancelled") or e.get("type") != "floor":
            continue
        if (e.get("motion") or "").upper() != "MA":
            continue
        act = e.get("action") or ""
        hit = next((res for pat, res in DISPOSED if pat.search(act)), None)
        out = hit
    return out


def last_decision(narr, bid, rcs=(), term=""):
    """The last decision either chamber made on the measure, as the journey
    reads it -- one of journey()'s lines -- or None where neither decided
    anything.

    The journey is the one reading of a docket that knows a tabling undone by
    a carried removal from the table, a decision reconsidered, a day's
    motions in the order they stood, a suspension of the rules that is not
    the business it would have allowed, and a row wrapped onto the next. What
    ended a measure is asked of it rather than of a second reading of the
    same rows: the tests in classify() that looked for a word among the
    carried motions could not tell CACR 4 of 2009's special order from a
    decision, and so could not see that its last decision was a vote it
    lost.
    """
    steps = [s for s in journey(narr, bid, rcs, term=term)[1] if s["body"] in ("H", "S")]
    return steps[-1] if steps else None


def classify(narr, rcs, prefix="", bid="", term=""):
    """Map a bill to one of four display states, from the docket alone.

    Only the fallback for bills the status page does not cover: 804 of
    33,683 once the archived terms have histories.

    A DECISION IS A MOTION THE CHAMBER ADOPTED, NOT A WORD IN THE DOCKET.
    This read substrings of the whole history, and "inexpedient to
    legislate" is in every MINORITY report, in every committee report
    recommending it, and in the question the chamber then voted down. When
    the 1989-2016 histories arrived that called 36 bills "Killed" that no
    chamber had killed -- including HB 589 of 2002, which died because its
    committee of conference never signed a report. The tests below read the
    events: type "floor", motion MA, and the action the chamber carried,
    which is the same rule floor_disposed() uses.
    """
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    text = " ".join(e.get("raw", "") for e in evs).lower()
    # THE LAST VETO OUTCOME, NOT ANY OF THEM. Both chambers must override, so
    # one sustaining ends the bill -- SB 434, where the House sustained and
    # the Senate overrode. But a chamber may reconsider: HB 542 of 2011 was
    # sustained 244-130, reconsidered, and overridden 255-112 the same
    # morning, and it is Chapter 271. Reading "sustained" anywhere called a
    # law a dead bill; reading the last outcome in the record gets both right.
    outcome = veto_outcome(evs)
    if outcome:
        return outcome
    if ("without the signature of the governor" in text
            or "law without signature" in text):
        return "law", "Became law unsigned"
    if SIGNED_RE.search(text):
        return "law", "Signed into law"
    if "vetoed" in text:
        return "veto", "Vetoed"
    # A WITHDRAWAL THE CHAMBER ADOPTED, where it is the last disposal the
    # floor carried (floor_disposed, and WITHDRAWN_ACT above DISPOSED). HB 641
    # of 2013 and HB 1186 of 2012 read "In committee" without this.
    _w = floor_disposed(narr)
    if _w and _w[1] == "Withdrawn":
        return _w
    # AND A WITHDRAWAL THE DOCKET RECORDS ON A ROW OF ITS OWN, with no vote
    # (narrative.WITHDRAWN_ROW, event type "withdrawn"): "Withdrawn" and
    # "Withdrawn 11/30/2011" on three House bills of 2012, "Read in January
    # 4, 2012 and Withdrawn" on a petition -- and "Withdrawn Prior to
    # Introduction" on four of 2010, which says so in the row's own words,
    # because a bill never introduced was never "withdrawn" from anything a
    # reader would take that word to mean. Each read "In committee". Only
    # where it is the last thing the record says the bill did: a floor
    # decision after it would be the answer.
    _gone = [i for i, e in enumerate(evs) if e.get("type") == "withdrawn"]
    if _gone and not any(e.get("type") == "floor" for e in evs[_gone[-1] + 1:]):
        return "done", (WITHDRAWN_PRIOR if evs[_gone[-1]].get("before_introduction")
                        else "Withdrawn")
    # A BILL ONLY EVER PROPOSED. HB 3 of the 2006 special session has one
    # row, "Proposed bill for special sesssion.", and no introduction: it was
    # in no committee, and "In committee" is what the foot of this function
    # would have called it.
    if evs and all(e.get("type") == "proposed" for e in evs):
        return "done", PROPOSED_ONLY
    # AN INTRODUCTION THE DOCKET ENTERS AND THE HOUSE JOURNAL DOES NOT HAVE
    # (NOT_INTRODUCED). Read "In committee", of a committee nothing was
    # referred to.
    if journal_not_introduced(narr):
        return "done", NOT_INTRODUCED
    # A DISPOSAL THE CHAMBER RECONSIDERED IS NOT ONE. HB 323 of 2005 read
    # "Killed": the House adopted Inexpedient to Legislate on 23 March, 164-153,
    # and on 30 March reconsidered it, 153-150, voted the kill down and passed
    # the bill, which went on to die in a committee of conference. Reading
    # "inexpedient to legislate" anywhere among the carried motions counted a
    # kill the House had undone. So a carried disposal is dropped where the
    # same chamber later carried a motion to reconsider AND then passed the
    # bill, and what followed decides. Both are needed: HB 1267 of 2012's
    # "Special Order (Reconsideration Motion)" only scheduled a motion that
    # then failed, and HB 666 of 1997 reconsidered its kill and killed the
    # bill again in a row the parser reads in two halves.
    #
    # The reconsideration can also be a clause of the passage's own line. The
    # House typed 30 March 2005 as one entry, "Rep Norelli moved to
    # Reconsider, MA RC(153-150); ITL ML DIV(149-151); ...; Passed with Am
    # VV", which the 1999-2006 docket reader joins back together from the
    # rows the database cut it into, and a whole line is told by its last
    # carried question, the passage. So a passage whose own line carried a
    # reconsideration before it undoes the disposal too.
    fl = [e for e in evs if e.get("type") == "floor"
          and (e.get("motion") or "").upper() == "MA"]
    fl = [e for _i, e in sorted(enumerate(fl),
                                key=lambda x: (x[1].get("date") or "", x[0]))]
    passage = re.compile(r"ought to pass|\botp\b|\bpassed\b", re.I)

    def undone(i, e):
        a = (e.get("action") or "").lower()
        if not re.search(r"inexpedient to legislate|ought not to pass|interim study"
                         r"|refer for study|indefinitely postpone", a):
            return False
        body = e.get("body") or ""
        for j in range(i + 1, len(fl)):
            if (fl[j].get("body") or "") == body and \
                    RECONSIDER_CARRIED.search(fl[j].get("raw") or "") and \
                    passage.search(fl[j].get("action") or ""):
                return True
            x = (fl[j].get("action") or "").lower()
            if (fl[j].get("body") or "") != body or not re.search(r"\breconsider", x) \
                    or re.match(r"\s*special order", x):
                continue
            return any((y.get("body") or "") == body and re.search(
                r"ought to pass|\botp\b|\bpassed\b", (y.get("action") or ""), re.I)
                for y in fl[j + 1:])
        return False
    carried = " | ".join((e.get("action") or "").lower()
                         for i, e in enumerate(fl) if not undone(i, e))
    if "inexpedient to legislate" in carried or "ought not to pass" in carried:
        return "done", "Killed"
    if re.search(r"interim study|refer for study", carried):
        # Its own kind, not "done". A bill sent to interim study has not been
        # killed -- it is parked for the committee to work on out of session,
        # and it can come back. Grouping it with bills that were voted down
        # said something untrue about it every time.
        return "study", "Referred for interim study"
    if "indefinitely postpone" in carried:
        return "done", "Indefinitely postponed"
    # A MOTION TO PASS THAT FAILED IS AN ANSWER. Where nothing else carried
    # after it, the chamber voted and the bill did not pass -- which is what
    # happened to every constitutional amendment that fell short of three
    # fifths. Until the floor pattern could read "MF RC 202-171 Lacking
    # Necessary Three-Fifths Vote", those bills had no outcome at all, and 78
    # of them took the word "Killed" from a MINORITY report.
    if not carried and any(
            e.get("type") == "floor" and (e.get("motion") or "").upper() in ("MF", "ML")
            and re.search(r"ought to pass|passage", e.get("action") or "", re.I)
            for e in evs):
        return "done", "Failed to pass"
    # With the article and without: "Died on Table, Session ended" is the
    # current docket's row and "Died on the Table" the House's of 2010 and
    # 2015, which this did not match.
    if re.search(r"died on (?:the )?table", text):
        return "done", "Died on the table"
    # THE SESSION ENDING IS AN ENDING. The docket's own last line says so --
    # "Died, Session ended 10/10/2024" -- and without this a bill whose kill
    # motion FAILED fell through to "In committee": CACR 17 of 2024, where
    # Inexpedient to Legislate lost 174-186 and Ought to Pass then lost
    # 180-183 for want of three fifths. The same words STATED uses.
    if "session ended" in text or "died, session" in text:
        return "done", "Died when the session ended"
    # A CHAMBER'S OWN RULE IS A DECISION, even though the clerk records it
    # with no motion code: "Inexpedient to Legislate, Senate Rule 3-23,
    # Adjournment" is how a bill left on the table dies at adjournment. 80
    # bills of 2017-2026 say exactly that and nothing else.
    # SENATE RULE 3-23 IS THE TABLE'S: it ends what is still lying there, and
    # this site's words for that are "Died on the table", on 669 bills whose
    # field says DIED ON THE TABLE or LAID ON TABLE over the same row. SB 14,
    # SB 20, SB 113, SB 227 and SB 304 of 2025 carry the row under a blank
    # field and read "Killed", of bills no chamber voted to kill: each was
    # laid on the table by a carried motion and never taken off it.
    if TABLE_DEATH.search(text):
        return "done", "Died on the table"
    if re.search(r"inexpedient to legislate,\s*(?:senate|house)\s+rule", text):
        return "done", "Killed"
    # THE LAST DECISION ON THE MEASURE WAS A MOTION TO PASS IT THAT FAILED.
    # The test above answers only where no motion of any kind carried, and a
    # carried special order, reconsideration, recommittal or tabling since
    # undone is not a decision on the measure: CACR 4 of 2009 was special
    # ordered on 12 February and lost 193-176 on the 18th, "Lacking Necessary
    # Three-Fifths", and read "In committee"; CACR 26 of 2008 lost, was
    # reconsidered and lost again; CACR 8 and CACR 11 of 2012 were retained,
    # lost, were tabled and taken off the table, and read "Retained in
    # committee"; CACR 2 of 2004's "OTP/AM failed 3/5 RC(186-172)" followed an
    # amendment it adopted. The LAST decision, of any kind: a tabling that
    # stood (HB 1681 of 1998, HB 1176 of 2026), a kill, a study, a
    # postponement or a recommittal after the vote is the answer instead, and
    # so is the docket's own row for the end, tested above.
    last = last_decision(narr, bid or prefix, rcs, term)
    if last and last["act"] == "failed":
        return "done", "Failed to pass"
    # AND A TABLING THAT STOOD IS WHERE THE MEASURE IS. Only a status field
    # saying LAID ON TABLE gave that label, and a bill tabled under a field
    # that says something STATED does not list fell through: HB 1668, HB 1679
    # and HB 1681 of 1998, three of the school-funding tax bills the House
    # laid on the table on 24 September 1998 ("LAID ON THE TABLE, REP HAGER MA
    # DIV(193-109)"), read "Committee report filed" from the field REPORT
    # FILED; SB 476, SB 566 and SB 651 of 2026, tabled by the Senate under a
    # blank field, read "In progress". After the tests above, which read a
    # docket's own row for a death on the table, the term's end or a
    # chamber's rule: SB 14 of 2025 was tabled and then killed by Senate Rule
    # 3-23, and that row is its ending.
    if last and last["act"] == "tabled":
        return "active", "Laid on the table"
    # RETAINED IS WHERE A BILL WAS, NOT WHERE IT IS once anything came after.
    # Read as "any retention anywhere" it called 21 bills "Retained in
    # committee" that had since been reported, passed both chambers and gone
    # to a committee of conference -- HB 589 of 2002 among them.
    # Moved on means the chamber then passed it, or the other chamber took it
    # up; a later vote that failed leaves the answer where it was.
    ret = [i for i, e in enumerate(evs) if e.get("type") == "retained"]
    if ret:
        where = evs[ret[-1]].get("body")
        moved_on = any(
            (e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
             and re.search(r"ought to pass|adopted", e.get("action") or "", re.I))
            or (e.get("body") and where and e.get("body") != where)
            for e in evs[ret[-1] + 1:])
        if not moved_on:
            return "active", "Retained in committee"
    # THE LAST THING THE RECORD SAYS. Where a committee has reported and no
    # floor vote is on the page, that is the honest answer: 51 bills of 2021
    # carry a majority report of Inexpedient to Legislate, a minority report
    # the other way, and nothing after them. Reading the majority's
    # recommendation as the chamber's decision called them "Killed"; reading
    # nothing called them "In committee", which is where they are not.
    if evs and evs[-1].get("type") == "report" and not any(
            e.get("type") == "floor" for e in evs):
        return "active", "Committee report filed"
    # And a resolution of one chamber "Introduced and Adopted", which the
    # clerk writes with no motion code: HR 13 of 2007 read "In committee"
    # over the one line of its docket that adopted it.
    # And the 1989-1998 reader's word for it: "REP MAVIGLIO MOVED LOT, ML
    # RC(74-250); ADOPTED VV" is told as the action "Adopt", carried. Every
    # other resolution of those years states PASSED/ADOPTED in its fields and
    # never reaches this line; HR 69 of 1992 has a docket and no fields, and
    # read "In committee" beside a journey that had the House adopting it.
    adopted_floor = any(
        (e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
         and re.search(r"ought to pass|adopted", e.get("action") or "", re.I))
        or (prefix in SINGLE_CHAMBER
            and re.match(r"\s*introduced\s+and\s+adopted\b", e.get("raw") or "", re.I))
        or (prefix in SINGLE_CHAMBER and e.get("type") == "floor"
            and (e.get("motion") or "").upper() == "MA"
            and re.match(r"\s*adopt\s*$", e.get("action") or "", re.I))
        for e in (narr or {}).get("events", []) if not e.get("cancelled"))
    if adopted_floor or any(r.get("passed") for r in rcs):
        # A resolution of one chamber that has carried a vote is finished.
        # There is no other chamber for it to be in progress towards.
        if prefix in SINGLE_CHAMBER:
            return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
        return "active", "In progress"
    return "active", "In committee"


# What the status box says of a one-chamber measure its chamber carried: a
# resolution, and a House bill of intent, which is not one and whose docket
# says PASSED.
ONE_CHAMBER_DONE = ("Adopted. A resolution of one chamber goes no further",
                    "Passed by the House, which is as far as a House bill of intent goes")


def next_step(narr, bill, prefix=""):
    """Plain-language 'what happens next', from the last recognised event."""
    evs = (narr or {}).get("events", [])
    if not evs:
        return "No recorded action yet"
    last = evs[-1]
    raw, t = last.get("raw", "").lower(), last.get("type")
    # A veto outcome is read from the WHOLE history, not just the last line.
    # An override is voted in each chamber separately, so the final line is one
    # chamber's answer rather than the bill's, and taking it alone reported
    # SB 434 as law when the House had already sustained the veto.
    every = " ".join(e.get("raw", "").lower() for e in evs)
    if "veto sustained" in every:
        return "Vetoed. The override failed and the bill is dead"
    if "veto overridden" in every:
        return "Vetoed, then overridden. It becomes law"
    if ("without the signature of the governor" in every
            or "law without signature" in every):
        return "Became law without the governor's signature"
    # THE SIGNATURE, LIKE THE VETO ABOVE, IS READ FROM THE WHOLE HISTORY.
    # Read off the last line alone it was missed whenever anything followed
    # it -- an effective-date row, a chaptering line, a same-day row that
    # sorts after it -- and 185 bills whose chip said "Signed into law" had a
    # status box reading "In progress" or "Enrolled. Pending the governor's
    # signature", 31 of them in the current term.
    if SIGNED_RE.search(every):
        return "Signed into law"
    if "vetoed" in raw:
        return "Vetoed. Awaiting a possible override vote"
    # A resolution of one chamber is finished the moment that chamber adopts
    # it, and the line recording that is not always the last one: HR16's floor
    # vote is followed by the roll call on the amendment it adopted, so the
    # chain below read "amendment" and answered "In progress" for a resolution
    # the House had passed a month earlier.
    if prefix in SINGLE_CHAMBER and any(
            e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
            and re.search(r"ought to pass|adopted", e.get("action") or "", re.I)
            for e in evs if not e.get("cancelled")):
        return ONE_CHAMBER_DONE[prefix == BILL_OF_INTENT]
    if t == "introduced":
        return f"Pending public hearing in {bill.get('house_committee') or 'committee'}"
    if t == "hearing":
        return "Pending executive session in committee"
    if t == "exec":
        return "Pending a committee report"
    if t == "report":
        return "Pending a vote of the full chamber"
    if t == "floor":
        if prefix in SINGLE_CHAMBER:
            return ONE_CHAMBER_DONE[prefix == BILL_OF_INTENT]
        return "Pending action in the other chamber"
    if t == "enrolled":
        if prefix == "CACR":
            return "Goes to the voters at the next general election"
        if prefix in NO_GOVERNOR:
            return "Adopted by both chambers. It does not go to the governor"
        return "Enrolled. Pending the governor's signature"
    if t == "retained":
        return "Retained in committee for further work"
    if t == "died":
        return "Died when the session ended"
    return "In progress"
