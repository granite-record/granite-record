#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.2
"""
What the two chambers did with each other's version of a bill, read from its
docket: a concurrence refused or agreed, a committee of conference asked for,
its report adopted or rejected, and conferees who could not agree or never
signed a report.

    import conferences as CF
    CF.conference_failure(events)       # ("unable", "2026-06-04"), or None
    CF.conference_outcome(events)       # {chamber: "adopted" | "failed"}, each one's last vote
    CF.between_chambers(narr, status)   # ("done", CONF_UNABLE), or None

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md). It moved here as it stood, comments and
all, because the journey reads conference_failure and is a module of its own
too (journey.py), and a module split out of build_site_v2 may not import it
back (_import_cycles_cut). build_site_v2 imports every name here back under
its own, so build_site_v2.conference_failure and the rest answer as they did,
and its status, its disposition and its journey read them as before. The
last piece, conference_not_taken_up, came the same day from build_site_v2's
measures that died with their term, because the status reads it too.
"""

import re

from parts import SIGNED_RE


# WHAT THE TWO CHAMBERS DID WITH EACH OTHER'S VERSION, from the docket.
#
# The status fields name a stage and stop there: HB 1215 of 2024 has a Senate
# field saying CONFERENCE REPORT ADOPTED and nothing in STATED for the House's
# CONFERENCE REPORT FAILED, so it read "Conference committee report adopted"
# over a docket whose last line is the House voting the report down 102-261.
# CACR 6 and CACR 12 of 2012 have no field saying it at all. And SB 34 of 2026
# read "Passed one chamber" because its Senate field is blank -- the docket has
# the House passing it amended and the Senate refusing to concur.
CONF_REPORT = re.compile(r"conf(?:erence)?\.?\s*comm(?:ittee)?\.?\s*rep(?:ort|t)?\b"
                         r"|committee of conference report", re.I)
# "Failed", and the older dockets' "Fails", "lost" and "defeated": 1999's
# HB 252 "Conf Comm Report Fails DIV(76-210)", 2006's HB 381 "Conf Comm Report
# lost RC(154-175)".
# And the Senate clerk of 2001's "Non Adopt" -- "Conference Committee Report
# RC 11Y-13N, Non Adopt" is SB 95 of 2001, whose report the House had adopted
# 196-159 that morning -- and the House's "Conference Committee Report Not
# Accepted by House pursuant to House Rule 49(j)" (SB 305 of 2016), a report
# filed and never taken up. SB 95 read "One chamber did not concur" and SB 305
# "In a committee of conference", each over a last row that ended it.
CONF_FAILED = re.compile(r"\bfail(?:ed|s)?\b|not adopted|\brejected\b|lacking|"
                         r"\blost\b|\bdefeated\b|\bnon[-\s]?adopt|\bnot\s+accepted\b", re.I)
# A NEW committee of conference -- "New Conf Comm", "New Committee of
# Conference", "new C of C" -- but not "New Conf Comm Report ... MA", which
# is the new conference's report being adopted (SB 140 of 1999).
NEW_CONF = re.compile(r"\bnew\s+(?:conf(?:erence)?\.?\s*comm(?:ittee)?\.?(?!\s*rep)|"
                      r"comm\w*\s+of\s+conf|c\s?of\s?c(?!\s*rep))", re.I)
# The clause about the report ends where the next member's motion starts:
# "Conf Comm Report Adopted RC(190-181); Rep Herman moved to Reconsider, ML".
NEXT_MOTION = re.compile(r";\s*(?:rep|reps|sen|senator)\b|moved to reconsider", re.I)
CONF_REJECTED = "Died when the conference report was rejected"

# CONFEREES WHO COULD NOT AGREE, AND SAID SO. A committee of conference that
# cannot settle the two versions files a report saying it is "unable to agree"
# -- the docket's words from 1989 to 2010 run "CONF COMM REPORT (UNABLE TO
# AGREE) ADOPTED VV" (HB 1181 of 1990), "CONF COMM REPORT (COMM UNABLE TO
# REACH AGREEMENT) SIGNED" (HB 1332 of 1990) and "Conference Committee Report
# 2246; Unable to Reach Agreement, Filed" (HB 431 of 2010) -- and the chambers
# adopt that report, which ends the bill: there is no agreed version left to
# pass. The status fields call it CONFERENCE REPORT ADOPTED, and 69 bills of
# 1989-2010 read "Conference committee report adopted" as though the
# conferees had settled it; every one of their dockets says they could not.
# The House Calendar says it in prose where the committee reported it: "The
# House and Senate members agreed to disagree" (SB 326, 2000).
CONF_UNABLE = "Died: conferees could not agree"
CONF_UNABLE_RE = re.compile(r"\bunable\s+to\s+(?:reach\s+)?agree", re.I)

# THE STAGES A BILL CAN DIE AT, AND THE WORD FOR DYING THERE (17 October
# 2026, the language sweep's items 13 and 14). Once a term has no session days
# left, a bill whose last word is one of these did not go on, and its chip
# already says Died; the status said "Laid on the table" or "One chamber did
# not concur; a committee of conference was asked for", which read as though
# a vote were still to come. The table's is the General Court's own phrase
# (its docket's "Died on Table"); the chambers' is said in the same form as
# CONF_UNABLE, and is true whether the second chamber refused a conference
# (HB 191 of 2026), none was asked for, or the conferees never reported.
CHAMBERS_APART = "Died: the chambers did not agree on a version"
ENDED_AS = {
    "Laid on the table": "Died on the table",
    "One chamber did not concur": CHAMBERS_APART,
    "One chamber did not concur; a committee of conference was asked for": CHAMBERS_APART,
    "In a committee of conference": CHAMBERS_APART,
}

# AND CONFEREES WHO NEVER SIGNED A REPORT AT ALL. A conference's report is
# signed off by its conferees, and where they did not settle the versions and
# signed nothing, the clerks record that instead:
# "(CONF COMM REPORT NOT SIGNED)" (HB 75 of 2000), "Conference Committee
# Report [Not Signed Off]" (HB 109 of 2003), "Conference Committee; Not
# Signed Off" (HB 1227 of 2004), "Conference Committee Report; Not Signed
# Off" (HB 1323 of 2026); the House's clerk "Conference Committee Report: Not
# Filed" (SB 625 of 2026); and in the oldest docket "NO CONF COMM REPORT
# SIGNED" (HB 575 of 1990) and "DIED IN COMMITTEE OF CONFERENCE" (SB 65 of
# 1989). The status fields stop at CONFERENCE COMMITTEE, NONCONCURRED REQUEST
# CONFERENCE or DIED, SESSION ENDED, so these bills read "In a committee of
# conference", "One chamber did not concur; a committee of conference was
# asked for" or "Died when the session ended", the last on 20 bills of
# 2025-2026 alone. Every such row in the record is about a conference; the
# conference is still named in the pattern, so that a line saying something
# else was not signed never reads as one.
CONF_UNSIGNED_RE = re.compile(
    r"(?:\bconf(?:erence)?|\bc\s?of\s?c)\b.*?\bnot\s+(?:signed|filed)\b"
    r"|\bno\s+conf\w*\.?\s*comm\w*\.?\s*rep\w*\s+signed\b"
    r"|\bdied\s+in\s+(?:the\s+)?comm\w*\s+of\s+conf", re.I)
# A REPORT SIGNED AFTER ALL, too late. HB 1091 of 2026's conferees were "Not
# Signed Off" at the deadline and then filed report 2026-2022c, which the
# Senate adopted the same day; the House refused 180-156 to suspend its rules
# "to consider late sign off report", and the bill died there -- not for want
# of an agreement. HB 1410 of 2002's Senate voted down a motion "To Allow C of
# C Report After Deadline" the day after its "(Conf Comm Report Not Signed)",
# which says a report may have been signed late. Neither is read as conferees
# who could not agree; both keep the label they have.
CONF_LATE_RE = re.compile(
    r"\blate\s+sign\w*[\s-]*off"
    r"|\b(?:c\s?of\s?c|conf\w*\.?\s*comm\w*\.?)\s+rep\w*\s+after\s+(?:the\s+)?deadline", re.I)


FAILURE_RANK = {"unable": 3, "unsigned": 2, "died": 1, "unfiled": 1}


def _failure_how(raw):
    """What a docket row says of a conference that ended without an agreement:
    "unable" (its report said so), "unsigned" or "unfiled" (no report was
    signed, or none filed), "died" (it died there), or None."""
    if CONF_UNABLE_RE.search(raw):
        return "unable"
    m = CONF_UNSIGNED_RE.search(raw)
    if not m:
        return None
    said = m.group(0).lower()
    return ("died" if said.startswith("died") else
            "unfiled" if said.endswith("filed") else "unsigned")


def conference_failure(evs):
    """(how, day) where the bill's last committee of conference ended without
    an agreement, or None. `how` is _failure_how's word for the row; a
    report saying the conferees were unable to agree outranks a note that no
    report was signed, in one conference.

    A new conference formed after it starts again: HB 1210 of 2002's first
    report went unsigned, the chambers formed a new one, and its report
    became Chapter 230. One the other chamber REFUSED leaves the earlier
    conference standing, as conference_outcome reads it (SB 69 of 2001:
    "House Refused to Accede to req for New Conf Comm"). Within one row,
    whichever comes later decides.

    And nothing after it may say the bill went on -- enrolled, to the
    governor, a concurrence that carried -- nor anything in that conference
    say a report was signed after all: a report signed late (CONF_LATE_RE),
    or, where the only word is that none was signed, a chamber voting on one.
    """
    said, start, saved = None, 0, None

    def keep(was, how, i):
        # The conferees' own report of no agreement says the most, and that
        # none was signed says more than that none was filed: HB 243 of
        # 2025's Senate row is "Not Signed Off" and the House's, three weeks
        # later, "Not Filed". Of two rows that say as much, the later.
        if was and FAILURE_RANK[was[0]] > FAILURE_RANK[how]:
            return was
        return how, evs[i].get("date") or "", i

    for i, e in enumerate(evs):
        raw = e.get("raw") or ""
        how = _failure_how(raw)
        hit = (CONF_UNABLE_RE.search(raw) or CONF_UNSIGNED_RE.search(raw)) if how else None
        new = NEW_CONF.search(raw)
        if new and re.search(r"refus", raw, re.I):
            if saved is not None:
                said, start = saved
            new = None
        elif new and not (re.search(r"\bMA\b", raw) or re.search(r"\bacced", raw, re.I)):
            new = None
        if hit and new and hit.start() < new.start():
            said = keep(said, how, i)
            saved, said, start = (said, start), None, i
        elif hit:
            if new:
                saved, said, start = (said, start), None, i
            said = keep(said, how, i)
        elif new:
            saved, said, start = (said, start), None, i
    if not said:
        return None
    how, day, at = said
    later = evs[at + 1:]
    if any(e.get("type") in ("enrolled", "governor") or SIGNED_RE.search(e.get("raw") or "")
           for e in later):
        return None
    went_on = concurrence_outcome(later)
    if went_on and went_on[0] == "con":
        return None
    if any(CONF_LATE_RE.search(e.get("raw") or "") for e in evs[start:]):
        return None
    if how != "unable" and conference_outcome(evs):
        return None
    return how, day


def conferees_disagreed(evs):
    """Whether the bill's last committee of conference ended without an
    agreement, as conference_failure reads it."""
    return conference_failure(evs) is not None


def _conference_vote(said, e, raw, m):
    """One chamber's vote on a conference report, into `said`, from the clause
    that names the report -- not from the whole row, where an MF or ML
    often belongs to another motion."""
    before = raw[:m.start()]
    # A motion ABOUT the report -- to reconsider it, table it, suspend the
    # rules for it -- is not a vote on it, when it is in the same clause as
    # the report's name: "Reconsideration, Conference Committee Report #2089c
    # ...: MF RC 108-247" (SB 135 of 2014) left the adopted report standing.
    if re.search(r"(?:reconsider\w*|susp\w*|table|\bLOT\b)[^;]*$", before, re.I):
        return
    tail = raw[m.start():]
    cut = NEXT_MOTION.search(tail)
    if cut:
        tail = tail[:cut.start()]
    if re.search(r"susp", tail, re.I):
        return
    body = (e.get("body") or "").upper() or "?"
    if CONF_FAILED.search(tail) or re.search(r"\bM[FL]\b", tail):
        said[body] = "failed"
    elif re.search(r"\badopted\b", tail, re.I) or re.search(r"\bMA\b", tail):
        said[body] = "adopted"


def conference_outcome(evs):
    """{chamber: "adopted" | "failed"} -- each chamber's LAST vote on a
    conference report, as veto_outcome reads overrides: a chamber may
    reconsider (SB 14 of 2025 failed 183-186, then carried 185-182).

    A NEW conference asked for or agreed to starts the count again -- but one
    the other chamber REFUSED leaves the rejected report as the last word:
    HB 1211 of 1992 lost its report, the House asked for a new conference and
    the Senate refused to accede. Same-day rows are not reliably in order, so
    either side may come first (HB 723 of 1998 has the House acceding before
    the Senate's request)."""
    said = {}
    saved = None
    for e in evs:
        raw = e.get("raw") or ""
        if NEW_CONF.search(raw) and re.search(r"refus", raw, re.I):
            if saved is not None:
                said = saved
            continue
        ms = list(CONF_REPORT.finditer(raw))
        # The report's vote first: the narrative joins wrapped rows, so one
        # event can carry "REPORT LOST ...; REQ NEW CONF COMM, ... MA".
        if ms:
            _conference_vote(said, e, raw, ms[-1])
        if NEW_CONF.search(raw) and (re.search(r"\bMA\b", raw)
                                     or re.search(r"\bacced", raw, re.I)):
            saved = said if said else saved
            said = {}
    return said


def concurrence_outcome(evs):
    """("non", asked_for_conference) or ("con", False): the last decision on
    concurring with the other chamber's amendment, or None. A motion to
    concur that FAILED is a refusal (HB 1215: 172-180), and a motion to
    non-concur that failed is not one."""
    last = None
    for e in evs:
        raw = e.get("raw") or ""
        low = raw.lower()
        failed = bool(re.search(r"\bM[FL]\b", raw))
        if re.search(r"non-?\s?conc|\bnonc\b|refused to accept|refuses? to concur|"
                     r"refused to concur", low):
            if not failed:
                last = ("non", bool(re.search(r"\bc\s?of\s?c\b|cofc|conf(?:erence)?\b", low)))
        elif re.search(r"\bconc(?:ur\w*)?\b", low) and "enrolled" not in low:
            if failed:
                last = ("non", False)
            elif re.search(r"\bMA\b|\bVV\b", raw):
                last = ("con", False)
    return last


# The labels a later dated docket line is allowed to replace: the stages a bill
# goes THROUGH. An outcome -- killed, tabled, law, vetoed -- is never replaced.
BEFORE_CONFERENCE = {
    "Passed one chamber", "In progress", "In committee", "Retained in committee",
    "Committee report filed", "Passed, awaiting the governor",
    "In a committee of conference", "Conference committee report adopted",
    "One chamber did not concur",
    "One chamber did not concur; a committee of conference was asked for"}
BEFORE_CONCURRENCE = {
    "Passed one chamber", "In progress", "In committee", "Retained in committee",
    "Committee report filed"}
# The labels the conferees' failure replaces: the stages before and in a
# conference -- not "Passed, awaiting the governor", which says the bill went
# on -- and the General Court's DIED, SESSION ENDED, which says only that the
# term ran out where the docket says why the bill did not get there.
BEFORE_UNABLE = (BEFORE_CONFERENCE - {"Passed, awaiting the governor"}) | {
    "Died when the session ended"}
# Any row about a committee of conference: one asked for, acceded to, named,
# meeting, or reporting. "Concur" is not one.
CONFERENCE_ROW = re.compile(r"\bconf(?:erence|eree)|\bc\s?of\s?c\b|\bcofc\b", re.I)


def between_chambers(narr, status):
    """A dated docket answer to what became of the two versions, or None."""
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    conf = conference_outcome(evs)
    # NOT WHERE THE REPORT A CHAMBER VOTED DOWN WAS THE CONFEREES' REPORT THAT
    # THEY COULD NOT AGREE. SB 69 of 2001's conferees filed "Conf Comm Report
    # (UNABLE TO AGREE)"; the House adopted that report, the Senate non-adopted
    # it 17-7 and asked for a new conference, and the House refused to accede.
    # No agreed version was rejected: the conferees could not agree, which the
    # test below says.
    unable = (conference_failure(evs) or ("",))[0] == "unable"
    if status in BEFORE_CONFERENCE and "failed" in conf.values() and not unable:
        return "done", CONF_REJECTED
    # A report ADOPTED keeps its label only where the conferees agreed; a
    # conference the fields still call sitting (HB 1323 of 2026), a request
    # for one (HB 291 of 2021) and the term's end (HB 243 of 2025) give way
    # where its conferees reported no agreement or never signed a report.
    if status in BEFORE_UNABLE and conferees_disagreed(evs):
        return "done", CONF_UNABLE
    # A committee of conference the other chamber REFUSED to form never sat:
    # SB 58 of 1990, "HOUSE REFUSED TO ACCEDE", and HB 1432 of 2022.
    if status == "In a committee of conference" and not conf:
        req = [i for i, e in enumerate(evs) if re.search(r"acced", e.get("raw") or "", re.I)]
        if req and re.search(r"refus", evs[req[-1]].get("raw") or "", re.I):
            return "active", ("One chamber did not concur; a committee of "
                              "conference was asked for")
    if status in BEFORE_CONCURRENCE and not conf:
        c = concurrence_outcome(evs)
        if c and c[0] == "non":
            return "active", ("One chamber did not concur; a committee of "
                              "conference was asked for" if c[1]
                              else "One chamber did not concur")
    # AND "DIED, SESSION ENDED" IS THE TERM RUNNING OUT, WHERE THE DOCKET SAYS
    # WHAT STOPPED THE BILL: HB 1768 of 2026 passed the Senate amended and on
    # 21 May the House refused the amendment and asked for no conference,
    # "House Non-Concurs with Senate Amendment 2026-1745s (Rep. Harb): MA VV",
    # its last row. Forty-one bills of that term with the same last row read
    # "One chamber did not concur"; this one read "Died when the session
    # ended", from the House's field. ONLY WHERE NO COMMITTEE OF CONFERENCE
    # WAS EVER ASKED FOR OR FORMED -- no row of the docket names one. HB 751
    # and HB 1709 of 2026 went to a conference whose report the Senate laid on
    # the table, and no vote on a report is what `conf` being empty means for
    # them too: a bill that reached a conference did not end at the refusal.
    if (status == "Died when the session ended" and not conf
            and not any(CONFERENCE_ROW.search(e.get("raw") or "") for e in evs)
            and concurrence_outcome(evs) == ("non", False)):
        return "active", "One chamber did not concur"
    return None


# A CHAMBER THAT WOULD NOT TAKE THE CONFERENCE'S REPORT UP. From build_site_v2's
# section on the measures that died with their term (ended_with_the_term), whose
# comment says what it is one of the tests of; the status's closing paragraph
# (closing_stage) reads it too.
CONF_NOT_TAKEN_UP = re.compile(
    r"\bsusp\w*\.?\s+rules?\s+for\s+(?:the\s+)?conf\w*\.?\s*comm\w*\.?\s*rep\w*\s*,\s*"
    r"(?:failed|fails|ML\b|MF\b)", re.I)


def conference_not_taken_up(evs):
    """The docket row that says a chamber would not take the conference's
    report up -- a report after the deadline, or a failed vote to suspend the
    rules for it -- or None."""
    return next((e for e in evs if CONF_LATE_RE.search(e.get("raw") or "")
                 or CONF_NOT_TAKEN_UP.search(e.get("raw") or "")), None)
