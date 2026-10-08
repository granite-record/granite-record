#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.107
"""
Turn a bill's docket entries into a plain-language history.

The docket is written in legislative shorthand. "Ought to Pass: MA VV 03/06/2025
HJ 8" means the House voted to pass the bill on a voice vote, with no record of
who voted which way. This renders that in a sentence a person can read, and says
so when no individual votes exist.

    python3 src/parse/narrative.py --docket Docket.txt --bill HB84 --session 2025
    python3 src/parse/narrative.py --docket Docket.txt --all --out narratives.json

Glossary sourced from the Citizens Count key to the NH Legislature website and
the NH General Court legislative handbook. Anything unrecognised is shown
verbatim rather than dropped -- an unexplained action is far better than a
missing one.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import build_date
import committee_names as CN
import json
import proceedings as P
import re
from collections import defaultdict, OrderedDict
from datetime import date, datetime

# CHAPTERS A PERSON HAS CONFIRMED over the docket's own number. The facts table
# prints extract_chapters' confirmed number, so the history beside it must
# print the same one: 1991 HB 329's history said "Chapter 1313" under a facts
# table saying 131. extract_chapters.CONFIRMED holds the evidence for each.
try:
    from extract_chapters import CONFIRMED as _CONFIRMED_CHAPTERS
except Exception:                                   # noqa: BLE001
    _CONFIRMED_CHAPTERS = {}


# AND CHAPTERS THE DATABASE SETTLED. The docket gave one number to two bills
# on eight pairs of laws, and extract_chapters fills each from the General
# Court's database where that tells the two apart: HB 1278 of 1992 reads
# "CHAP.0233" on the docket and is chapter 232, as its own final version is
# headed. The facts table prints 232, so the history must: for the same
# reason as above, and from the file the table reads. {(term, bill): (the
# chapter published, the number the docket's line gives)}, for the records of
# chapters.json where the two differ; empty unless --chapters names the file,
# which narrate_archive.py does and the current term's step does not, so a
# run without it tells every chapter as it did before.
SETTLED_CHAPTERS = {}


def load_settled_chapters(path):
    """SETTLED_CHAPTERS from chapters.json, or {} where it is not there."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    out = {}
    for term, byb in data.items():
        for bill, rec in (byb.items() if isinstance(byb, dict) else ()):
            if isinstance(rec, dict) and rec.get("chapter") and rec.get("docket") \
                    and rec["chapter"] != rec["docket"]:
                out[(term, bill)] = (rec["chapter"], rec["docket"])
    return out


def confirmed_chapter(term, bill, n):
    """The person-confirmed chapter where the docket's number is the one the
    correction replaces, or the one the database settled where the docket's
    is the one it gave to two bills; otherwise the number as the docket gives
    it."""
    said = str(n or "").strip().lstrip("0")
    fix = _CONFIRMED_CHAPTERS.get((term, bill))
    if fix and said == str(fix[1]):
        return str(fix[0])
    got = SETTLED_CHAPTERS.get((term, bill))
    if got and said == str(got[1]):
        return str(got[0])
    return n

# --------------------------------------------------------------- glossary

VOTE_KIND = {
    "VV": ("voice vote", False),
    "DV": ("division vote", False),
    "RC": ("roll call", True),
}
# second element: are individual member votes recorded?

MOTION = {
    "MA": "adopted",   # Motion Adopted
    "MF": "failed",    # Motion Failed
    "ML": "failed",    # Motion Lost
    "AA": "adopted",   # Amendment Adopted
    "AF": "failed",    # Amendment Failed
    "AL": "failed",    # Amendment Lost
}

# Which calendar a committee report was placed on. CC is not decoration: a bill
# on the Consent Calendar passed without floor debate because no member pulled
# it off. That is real information about how contested a bill was.
#
# The second sentence of the consent calendar's note, apart, so that the checks
# can name it.
#
# IT STATES THE RULE, AND SAYS NOTHING OF THIS BILL. It read "The chamber then
# adopts the committee's recommendation without floor debate" -- a claim about
# what happened to this report -- and was left off beside a chamber whose
# docket records the bill coming off its consent calendar. Three passes each
# read more of the ways a docket writes that, and each missed some: on
# 2 October 2026 the sentence still stood beside 146 Senate reports of
# 2011-2024 the Senate took off ("Sen. Daniels Moved to Remove HB 1313 from the
# Consent Calendar", HB 1313 of 2018), three House reports of 1992 ("REMOVED
# FROM CON CAL, REQ REP JACOBSON", HB 476), and a dozen reports no row says
# came off and the floor plainly decided -- HB 1142 of 2014, whose House
# rejected the committee's interim study 102-207 and passed the bill on roll
# calls, and HB 624 of 2025, decided on two division votes. The rule is true
# beside every one of them whether a removal is read or not, and with it the
# note no longer depends on reading every wording; this bill's own removal is
# said by CONSENT_OFF_NOTE where one is read. The site's civics page and its
# glossary of docket codes put it the same way: the calendar is adopted in one
# vote, and a bill can be taken off first.
CC_THEN = (" The chamber adopts all the reports on its consent calendar in one vote, "
           "without floor debate, unless a bill is taken off it first.")
# A FLOOR ROW WHOSE COUNT IS THE CONSENT CALENDAR'S (6 October 2026; the
# person's word on decision 51). The House adopted its consent calendar of 7
# January 1998 on one roll call, and the clerk wrote it on each of the 113
# bills the calendar held -- "PASSED WITH AM/CONSENT CAL RC(248-8)", "ITL
# REPORT ADOPTED/CONS CAL RC(248-8)" -- and the calendar of 25 March 2014 on
# a division, "Ought to Pass: MA Div 282-9 (Consent Calendar)", on 28. Each
# history told the count as the bill's own vote ("voted to pass it with
# changes on a roll call 248-8"); it is the calendar's, and the history says
# so (describe). A row that names the consent calendar with no count -- "ITL
# MA (Cons Cal by nec 2/3)" -- states no vote of the bill's to mistake.
CONSENT_VOTE = re.compile(
    r"/\s*CONS(?:ENT)?\.?\s+CAL\b|\(\s*(?:Consent\s+Calendar|Cons(?:ent)?\.?\s+Cal\b|CC\s+by\b)",
    re.I)
# AND ONLY WHERE THE CALENDAR'S ROWS AGREE ON IT (7 October 2026). Two of the
# 28 rows of the calendar of 25 March 2014 read "MA Div 289-9 (Consent
# Calendar)" (HB 1286 and HB 1348), where the other 26 read 282-9, the count
# House Journal 13 prints for the calendar's adoption; told as the calendar's
# vote, the site gave two counts for one vote. A count fewer of the day's
# consent rows in that chamber carry than another is not told as the
# calendar's: the history says the bill went with the calendar and gives no
# count, the rail the same (calendar_count_disputed, which build_site_v2
# reads), and the docket line keeps the clerk's words. Which count the row
# should have said is a person's to settle (docket_corrections.json), not a
# rule's. {(term, chamber, day): Counter of (vote, yeas, nays)}, filled by
# main() from the term's histories; empty, every count is told.
CONSENT_COUNTS = {}


def consent_counts(results):
    """{(term, chamber, day): Counter((vote, yeas, nays))} of the floor rows
    whose count is a consent calendar's (CONSENT_VOTE), from built histories
    ({term: {bill: history}})."""
    from collections import Counter
    out = defaultdict(Counter)
    for term, byb in results.items():
        for rec in byb.values():
            for e in rec.get("events") or []:
                if (e.get("type") == "floor" and e.get("yeas") and e.get("nays")
                        and CONSENT_VOTE.search(e.get("raw") or "")):
                    out[(term, e.get("body"), e.get("date"))][
                        ((e.get("vote_kind") or "").upper(), e["yeas"], e["nays"])] += 1
    return dict(out)


def calendar_count_disputed(ev):
    """Does another count stand on more of this consent calendar's rows than
    the one this row gives (CONSENT_COUNTS)?"""
    when = ev.get("when")
    got = CONSENT_COUNTS.get((ev.get("_term"), ev.get("body"),
                              when.strftime("%Y-%m-%d") if hasattr(when, "strftime") else ""))
    if not got or not CONSENT_VOTE.search(ev.get("_raw") or ""):
        return False
    mine = ((ev.get("vote") or "").upper(), ev.get("y"), ev.get("n"))
    top, most = got.most_common(1)[0]
    return mine != top and got.get(mine, 0) < most

CALENDAR = {
    # Two halves. The first explains what the consent calendar IS and is
    # said whenever a bill is put on one, rule and all. The second says that
    # THIS bill came off, and is said only where the docket records that --
    # as its own action, so it is a fact about this bill rather than a rule
    # recited at every reader.
    #
    # WHAT THE CONSENT CALENDAR DOES IS ADOPT THE COMMITTEE'S REPORT, whatever
    # the report recommends. The clause read "It then passes without floor
    # debate", beside every report on a consent calendar that recommended
    # killing the bill or studying it -- HA 1 of 2018, "Committee Report:
    # Ought Not to Pass for 03/06/2018 (Vote 17-0; CC)", under a status of
    # Killed.
    #
    # AND THE FIRST SENTENCE SAYS WHO PUTS A REPORT THERE, NOT BY WHAT VOTE.
    # It read "when the committee vote was unanimous or nearly so, and any
    # members who dissented did not object to placing it there", in 47
    # histories that give the report as carried 3-2, 2-1 or 4-2 (HB 138 of
    # 2025, "Ought to Pass, 05/08/2025; Vote 3-2; CC", adopted with the
    # Senate's calendar of 8 May). The placement is the committee's own
    # decision, apart from its vote on the recommendation -- unanimous under
    # the House's rules of 1995 and 1997 (Rule 51, legislation/1995/HR0001.html)
    # and in both chambers now, as the civics page says -- but the rules of
    # every year and both chambers are not on this disk, so the note says
    # only what the record shows of every one of them: the committee decides,
    # and a divided recommendation can still go there.
    "CC": ("the consent calendar",
           "A committee decides whether its report goes on the consent "
           "calendar, and can send it there even when its members divided on "
           "the recommendation itself." + CC_THEN),
    "RC": ("the regular calendar", None),
}

# Where the docket records a bill actually coming off the consent calendar:
# classify() reads some of these rows as consent_off, and this reads them all,
# for CONSENT_OFF_NOTE.
#
# EVERY FORM THE DOCKETS WRITE IT IN, wherever in the row it stands: "Removed
# from Consent (Rep. Testerman) 04/07/2021", the House's since 2017; "Removed
# from CC (Rep. Vaillancourt)", the House's of 2006; "Rep Sorg: Removed from
# Consent Calendar" (HB 87 of 2007); "Remove from Consent Calendar (Rep Kurk)"
# (HB 676 of 2015); "Sen. Carson Moved Remove From Consent Calendar" (HB 1410
# of 2014); "MA VV; Removed from Consent Cal, req Rep Mock" (HB 605 of 1999);
# "REMOV FR CC, REQ KEANS" (HB 51 of 1989); and the Senate's "SB 60-FN was
# Removed from the Consent Calendar; 02/13/2025", which CONSENT_OFF_RE reads
# only without the "-FN". It was the first alone, at the start of the row,
# and 36 measures kept "It then passes without floor debate" beside the
# chamber that took them off.
#
# AND THE BILL NAMED BETWEEN THE VERB AND THE CALENDAR, which is how the
# Senate has written it since 2011 (from 2025 beside a row of the form above)
# and the pattern above did not read: "Sen.
# Daniels Moved to Remove HB 1313 from the Consent Calendar" (HB 1313 of
# 2018), "Sen. Watters Moved to Remove SB 155-FN-A from the Consent Calendar"
# (SB 155 of 2013), "Sen. Sherman Moved Remove SB 522 from the Consent
# Calendar" (2020), "Moved to Remove HB 1405 from the Consent Calendar" (2014),
# "Moved to Remove SB108 from the Consent Calendar" (2021) -- 325 rows in the
# files on disk. And
# the House's "REMOVED FROM CON CAL, REQ REP JACOBSON" (HB 476 of 1992, three
# rows) and "Removed frm Consent (Rep. Umberger)" (SB 116 of 2013). Those
# are every wording a loose search of all 21 docket files on disk found on
# 2 October 2026 (anything removed beside "consent", "cons cal", "con cal"
# or "CC"), and the data check asks the same question in its own words.
#
# NOT EVERY REMOVAL NAMES THE CALENDAR. The House's floor rows of 1989 write
# some as the member alone -- "REP SPEAR REMOV; REP TOWNSEND SUB ITL;" (HB 12
# of 1989, reported "VOTE (12-2;CC)"), "REP O'BRIEN REMOVED; ITL REPORT
# ADOPTED VV" (HB 312), on 33 bills -- and neither this nor the check reads
# them, because "removed" alone could be anything. Those histories say
# nothing of a removal, which is a gap and not a claim, and 32 of them say
# nothing of the consent calendar at all, their placings being written
# "VOTE (12-2;CC)", which CALENDAR_RE does not read; the one that states the
# rule (HB 171 of 1989) states it as a rule.
#
# Not a row about OTHER bills: "Special Order to after the Bills removed from
# the Consent Calendar, Without Objection, MA" (HB 275 of 2022) orders this
# bill behind them. Not another calendar: "REMOVED FROM CONF COMM CONSENT
# CAL, REQ REP MOCK" (HB 1123 and HB 1531 of 1998) is a conference report's,
# and "Removed from the Consent List; 06/16/2020" (CACR 19 of 2020) is the
# Senate's Laid on the Table Consent List of that day -- Senate Journal 8 of
# 2020 prints it under "BILLS REMOVED FROM CONSENT LIST" -- on a measure no
# committee ever reported.
REMOVED_FROM_CONSENT = re.compile(
    r"\bRemov(?:e|ed)?\s+(?:(?:[A-Z]{2,4}\s*\d+(?:-[A-Z]+)*)\s+)?(?:from|frm|fr)\s+(?:the\s+)?"
    r"(?:Consent\b(?!\s+List)|Cons?\.?\s*Cal\b|CC\b)", re.I)
NOT_THIS_BILL_REMOVED = re.compile(r"\bSpecial\s+Order\b", re.I)


def removed_from_consent(raw):
    """Does this docket row take its own bill off the consent calendar?"""
    return bool(REMOVED_FROM_CONSENT.search(raw or "")
                and not NOT_THIS_BILL_REMOVED.search(raw or ""))


# Said beside a removal the docket records, of the chamber whose row it is.
#
# WHAT THE ROW RECORDS AND NO MORE. It read "Ten members may file a petition
# to pull a bill off the consent calendar and have it debated and voted on
# separately, which is what happened here" -- on 1,682 histories, most of them
# beside a removal at one member's request ("REMOVED FROM CONS CAL, REQ REP R
# FOSTER", HB 613 of 1993) and others beside the Senate's, where no petition
# is written at all. Ten members has been the House's rule since January 2023;
# before that one member's request was enough, as the civics page says, and
# the rule is not this note's to state for every year and chamber. Nor is what
# came after: HB 68 of 2021 was taken off and never voted on, and sixty-seven
# bills of 1993 were put back on the consent calendar after they came off
# ("RETURNED TO CONSENT CALENDAR, REP MCGOVERN", HB 264).
#
# AND NOT WHAT A BILL IS TAKEN OFF FOR. It said ", to be taken up on its own"
# for one evening, beside those sixty-seven, which were not: HB 264's
# history read, with the rule beside it, as a bill the calendar did not
# decide, and the calendar killed it on 16 March. So it says that the chamber
# took the bill off, and nothing else; where the chamber put it back,
# CONSENT_BACK_NOTE says that too.
CONSENT_OFF_NOTE = "The {chamber} took this bill off its consent calendar."

# Said where the docket records the bill put back on the calendar it came off.
# One wording on disk, the House's of 16 March 1993 and nowhere else:
# "RETURNED TO CONSENT CALENDAR, REP MCGOVERN; HJ40,P958" (HB 264), 67 rows,
# each on a bill a row read above took off the House's calendar of 10 March.
# HB 264's next row is "ITL REPORT ADOPTED", with the calendar. What followed
# is the history's to tell, not this note's: HB 625 was then laid on the
# table on a member's motion.
RETURNED_TO_CONSENT = re.compile(r"\bRETURNED\s+TO\s+(?:THE\s+)?CONSENT\s+CAL", re.I)
CONSENT_BACK_NOTE = "The {chamber} later put this bill back on its consent calendar."

RECOMMENDATION = {
    "ought to pass with amendment": "pass it with changes",
    "ought to pass": "pass it",
    "inexpedient to legislate": "kill it",
    # The report against an address for the removal of an officer, which is
    # how an address is killed: "Ought Not to Pass: MA DIV 220-106" (HA 1 of
    # 2010). The site's word for the outcome is the one it uses for
    # Inexpedient to Legislate, in the status and here. Without it the report
    # was printed in the docket's words with its calendar day inside them --
    # "The committee reported: Ought Not to Pass for unanimously, 17–0" (HA 1
    # of 2018) -- and the House "adopted “Ought Not to Pass”".
    "ought not to pass": "kill it",
    "interim study": "study it after the session ends",
    "refer for interim study": "study it after the session ends",
    # The clerk writes this one both ways and the site had only the first, so
    # 142 lines fell past the table and were printed in the docket's own
    # wording: "The committee reported: Referred to Interim Study."
    "referred to interim study": "study it after the session ends",
    "retain": "hold on to it for further work",
    "rerefer to committee": "send it back to committee",
    # And this one, 65 more.
    "rereferred to committee": "send it back to committee",
    "without recommendation": "make no recommendation",
    "no recommendation": "make no recommendation",
    "lay on table": "lay it on the table",
    # THE SENATE'S SPELLING. The House clerk writes "Lay on Table" and the
    # Senate clerk writes "Laid on Table", and this is a prefix match, so
    # the second fell through and was printed in the docket's own words
    # while the first read as plain English. 318 Senate actions, plus the
    # ones carrying a roll-call tally after them. The compound forms --
    # "vacated from committee and laid on table", "introduced ..., and laid
    # on table" -- start with a different verb and are two actions in one
    # line; they are left as the clerk wrote them rather than losing half.
    "laid on table": "lay it on the table",
    "table": "lay it on the table",
    "indefinitely postpone": "kill it and bar the subject for the rest of the term",
    "adopt": "adopt it",
    "concur": "agree to the other chamber's changes",
    "nonconcur": "reject the other chamber's changes",
}

# Floor actions often name who moved them: "Lay on Table (Rep. Osborne): MA VV"
MOVER_RE = re.compile(r"\s*\((?P<mover>(?:Rep|Sen)\.[^)]+)\)\s*$")

# The clerk types the mover as an initial and a surname often enough that the
# site was reading "on a motion by Rep. N. Germana". These sentences are
# generated from the docket rather than quoted from it, so the member's actual
# name belongs in them -- but only where the roster settles which member it is.
# Two members sharing a surname keeps the initial rather than picking one.
#
# Optional: with no roster the mover is left exactly as the docket wrote it.
MEMBERS = {}
EXPANDED = [0]
MOVER_NAME_RE = re.compile(r"^(?P<hon>Rep|Sen)\.\s*(?P<rest>.+)$")


def load_members(path):
    """(chamber, surname) -> given names, from data/legislators.json."""
    p = Path(path) if path else None
    if not p or not p.exists():
        return {}
    try:
        recs = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    if isinstance(recs, dict):
        recs = list(recs.values())
    idx = defaultdict(list)
    for r in recs:
        if not isinstance(r, dict):
            continue
        nm = (r.get("name") or "").strip()
        if not nm:
            continue
        if "," in nm:
            surname, given = [x.strip() for x in nm.split(",", 1)]
        else:
            bits = nm.split()
            surname, given = bits[-1], " ".join(bits[:-1])
        if given:
            idx[((r.get("chamber") or "").upper()[:1], surname.lower())].append(given)
    return idx


def expand_mover(mover):
    m = MOVER_NAME_RE.match(mover.strip())
    if not m or not MEMBERS:
        return mover
    hon = m.group("hon")
    bits = m.group("rest").split()
    if not bits:
        return mover
    surname = bits[-1]
    initial = bits[0].rstrip(".")[:1].upper() if len(bits) > 1 else ""
    cands = MEMBERS.get(("H" if hon.lower() == "rep" else "S", surname.lower()), [])
    if initial:
        cands = [g for g in cands if g[:1].upper() == initial]
    if len(cands) != 1:
        return mover
    full = f"{hon}. {cands[0]} {surname}"
    if full != mover.strip():
        EXPANDED[0] += 1
    return full

# Committee reports end with the calendar the report was placed on:
# "(Vote 16-0; CC)" or "(Vote 12-8; RC)". Per the General Court's official
# docket abbreviation list, RC here is Regular Calendar -- it only means Roll
# Call when tallies follow it, as in "MA RC 202-161".
CALENDAR_RE = re.compile(r"\bVote\s*\d+\s*-\s*\d+\s*;\s*(?P<cal>CC|RC)\b", re.I)

# Plain-language notes attached to particular outcomes.
NUANCE = {
    "interim study": "In practice this often ends a bill's progress for the term.",
    "lay on table": "Laying a bill on the table sets it aside without voting it down. A tabled bill can be taken back up later, but dies at the "
                    "end of the session if it is not.",
    "laid on table": "Laying a bill on the table sets it aside without voting it down. A tabled bill can be taken back up later, but dies at the "
                     "end of the session if it is not.",
    "retained in committee": "A retained bill stays with the committee into the "
                             "second year of the term. Sometimes that means more work "
                             "is planned, and sometimes it is a quiet ending.",
    "died on table": "The bill was set aside during the session and never taken back "
                     "up, so it died when the session ended.",
    "indefinitely postponed": "This kills the bill and blocks the same subject "
                              "from being raised again for the rest of the two-year term.",
}

MONTH = "%B %-d, %Y" if sys.platform != "win32" else "%B %#d, %Y"


def fdate(d):
    try:
        return datetime.strptime(d, "%m/%d/%Y").strftime(MONTH)
    except ValueError:
        return d


ONE_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def in_term(yr, mo, dy, session):
    """Whether a day falls in the term a session year belongs to: from
    1 November before the term's first year to the end of its second.

    The House and Senate organise on the first Wednesday of December of the
    even year, and the first bills are introduced that day -- the whole of
    2005-2006's first batch is dated 1 December 2004. The line is drawn where
    build_site_v2._j_in_term draws the rail's, so a date this keeps is one
    the rail will print.
    """
    start = session if session % 2 else session - 1
    return (start - 1, 11, 1) <= (yr, mo, dy) <= (start + 1, 12, 31)


def session_keeps(yr, mo, dy, session):
    """Whether a docket date belongs to a bill of this session year: within a
    year of it, as the database glue has always allowed, or anywhere in its
    term.

    THE SESSION COLUMN IS THE BILL'S LAST YEAR, NOT ITS FIRST. A bill
    retained into the second year of its term carries that year on every
    row, so a year either side of it reaches back only to January of the
    first -- and twelve introductions of 2005-2006 were entered at the
    organisation of the term, the December before. They are the only dates
    across the nineteen terms this keeps that the year either side did not.
    """
    return session - 1 <= yr <= session + 1 or in_term(yr, mo, dy, session)


def years_to_try(session, mo, dy, entered=None):
    """The years clamp_year tries for a month and day whose year is outside
    the bill's session, in order: the year the row was entered for, then the
    session's and the years either side of it.

    THE SESSION COLUMN IS THE BILL'S LAST YEAR, and a bill retained into its
    second year carries that year on every row. "Subcommittee Work Session:
    3/3/2008 10:00 AM LOB 208" was entered on 18 February 2009 on HB 50, a
    bill of 2009 retained into 2010, and "Retained Bill - Subcommittee Work
    Session: 9/30/2006 2:30 PM LOB 205" on 23 September 2009 on HB 606: the
    session's year made them work sessions of 3 March and 30 September 2010,
    a year after each was noticed. The year the row was entered in -- or the
    next, for a notice entered in December -- is tried first, where it puts
    the day from a week before the row to YEAR_SLIP_AHEAD days after it and
    inside the term."""
    first = []
    if isinstance(entered, datetime) and entered != datetime.min:
        for y in (entered.year, entered.year + 1):
            try:
                ahead = (date(y, mo, dy) - entered.date()).days
            except ValueError:
                continue
            if -7 <= ahead <= YEAR_SLIP_AHEAD and in_term(y, mo, dy, session):
                first.append(y)
    return first + [session, session - 1, session + 1]


def clamp_year(ev, session, entered=None):
    """A date outside the bill's own session, brought back into it.

    This is docket_vocab._ensure_date's rule and its words, applied to the
    terms that function never sees. It reads 1989-2016 from the database dump
    and has clamped their mistyped years since the 11th; the fetched dockets
    of 2017-2026 went through classify() instead and kept theirs, which is why
    HB 1484 of 2018 said it was "enrolled on April 26, 2089" and HB 1247 of
    2020 had an amendment rejected "on June 16, 2062". Six such dates across
    four terms, each a clerk's slip on a digit.

    A date outside the bill's own session is not a fact about the bill, so the
    day and month are kept -- they are the clerk's and are almost certainly
    right -- and the year is the session's. The year that would be correct is
    often guessable from an amendment number, and guessing it is still
    inventing a date, so this does not.

    ev["eff"] is deliberately untouched: a law of 2014 really can take effect
    in 2020, and two do.

    A DATE IN THE BILL'S OWN TERM IS NOT OUTSIDE ITS SESSION, whatever the
    session column says (session_keeps). A bill retained into its second
    year carries that year on every row, its introduction included, so HB 113
    of 2005-2006, introduced on organisation day, 1 December 2004, was brought
    "back" to 1 December 2006 -- eleven months after the House killed it.
    """
    d = str(ev.get("date") or "")
    if not ONE_DATE.match(d):
        return ev
    try:
        year = int(str(session)[:4])
    except (TypeError, ValueError):
        return ev
    mo, dy, yr = (int(x) for x in d.split("/"))
    if session_keeps(yr, mo, dy, year):
        return ev
    for y in years_to_try(year, mo, dy, entered):
        try:
            ev["date"] = datetime(y, mo, dy).strftime("%m/%d/%Y")
            break
        except ValueError:
            continue
    return ev


# ---- the day a row states, where the row was entered on another ---------------
#
# A ROW NO PATTERN READS TAKES THE DAY IT WAS ENTERED, which is right for a row
# entered as the thing happened and wrong for four kinds the clerks enter on
# another day and date in their own words. Each states the day of what it
# records, so the row is dated by it (the fourth, a petition read in, is set
# out after the cautions below):
#
#   THE END OF A TABLED BILL AT ADJOURNMENT. "Inexpedient to Legislate, Senate
#   Rule 3-23, Adjournment 09/16/2020" was entered on 8, 9 and 10 September
#   2021 on 427 bills of 2020, "... Adjournment 06/22/2017" on 3 January 2018
#   on 23 of 2017, "... Adjournment 06/24/2021" on 5 January 2022 on 26 of
#   2021. Each bill's last action read as a day in the year after it died,
#   and 432 measures introduced, tabled and dead within one year were
#   "carried over" into the next.
#
#   A VOTE ON A CONFERENCE REPORT. "Conference Committee Report 2072c; RC
#   11Y-13N, Failed; 06/01/2016" (HB 1660 of 2016) was entered on 22 June, and
#   the Senate's rejection of the report was dated three weeks after it:
#   House Journal 42 of 1 June prints the Senate's message, and the roll call
#   is of 1 June. "... RC 16Y-8N, Adopted; 06/26/2025" (HB 377 of 2025) was
#   entered on 3 November, three months after the governor signed the bill.
#
#   A HEARING NOTICE THE HEARING PATTERN DOES NOT READ. "Hearing: 01/20/2026,
#   Map Room, SL, 09:15 am" was entered on 11 December 2025, and "Hearing:
#   01/22/2026, Room 103, SH, 11:25 am; SC 47A" on 22 December: twelve Senate
#   bills of 2026 carried one row of 2025 and were "carried over". Every
#   notice the pattern does read is dated the day of its hearing.
#
# ONLY WHERE THE DAY CAN BE THE DAY. In the bill's own term; and for the first
# two, not after the row was entered -- a row cannot record what has not
# happened, and a day ahead of its entry is the sitting the row was entered
# ahead of, which build_site_v2's journey reads. "Adjournment 09/16/2021" on
# HB 201 of 2020, entered on 9 September 2021, is neither and keeps the day it
# was entered. Not a row that names the sitting it was done in recess of, and
# not a report filed: "Conference Committee Report Filed, # 2025-2809c;
# 06/26/2025" states the day the report is to be taken up.
#
# NOT EVERY ROW THAT STATES A DAY. "9/7/11-Notwithstanding the Governor's
# Veto, Shall HB 542 Become Law: RC 17Y-5N", entered on 4 January 2012, names
# the legislative day the Senate was still sitting in; "Died on Table
# [11/30/2011]", entered that same day on sixteen House measures, names the
# House's; "Report due 1/29/2004" and "RE-REF MAJ REPORT ITL FOR 1/5/94" name
# days to come. Read each kind before adding it here.
#
#   A PETITION READ IN. "Read In January 4, 2012; HJ 7, PG.367" was entered on
#   13 December 2011 on nine petitions of the 2012 session, PET 20 to PET 28,
#   three weeks before the House sat: each petition's first action read as a
#   day of 2011, and each was "carried over" from a session it was never in.
#   The same words on PET 11, entered on the day itself, were always right.
#   Entered ahead of the day, as a hearing notice is; and the journal it
#   cites is the day's own, so the citation is looked up in the day's year.
STATES_ITS_DAY = (
    ("adjournment", re.compile(
        r"\bSenate\s+Rule\s+3-23\b\W*(?:Adjournment\W*)?"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\W*$", re.I)),
    ("conference vote", re.compile(
        r"^\s*Conference\s+Committee\s+Report\b(?!.*\b(?:Filed|recess)\b)"
        r".*\b(?:Adopted|Failed)\b.*?(?<![\d/])(?P<date>\d{1,2}/\d{1,2}/\d{4})\W*$", re.I)),
    ("notice", re.compile(
        r"^\s*(?:Public\s+)?Hearing\s*:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})\b", re.I)),
    ("read in", re.compile(
        r"^\s*Read\s+In\s+(?P<month>[A-Z][a-z]+)\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})\b"
        r"(?!\s+and\s+Withdrawn)", re.I)),
)
# The kinds entered ahead of the day they state.
STATED_AHEAD = ("notice", "read in")


def _stated(m):
    """The day a STATES_ITS_DAY match names: "01/20/2026", or the month
    written out. ValueError where it is no day."""
    d = m.groupdict()
    if d.get("date"):
        return datetime.strptime(d["date"], "%m/%d/%Y")
    return datetime.strptime(f"{d['month']} {d['day']} {d['year']}", "%B %d %Y")


def stated_day(ev, r):
    """Date a row no pattern reads by the day it states, where that is the
    day of what it records (STATES_ITS_DAY)."""
    if ev.get("_type") not in ("other", "conf_report", "senate_rule_kill",
                               "nongermane_hearing") or ev.get("date"):
        return ev
    created = r.get("created")
    for kind, pat in STATES_ITS_DAY:
        m = pat.search(ev.get("_raw") or "")
        if not m:
            continue
        try:
            said = _stated(m)
            session = int(str(r.get("session"))[:4])
        except (TypeError, ValueError):
            return ev
        if not in_term(said.year, said.month, said.day, session):
            return ev
        if kind not in STATED_AHEAD and not (isinstance(created, datetime)
                                             and said.date() <= created.date()):
            return ev
        ev["date"] = said.strftime("%m/%d/%Y")
        # THE VOLUME IT CITES IS OF THE YEAR IT WAS ENTERED. A citation carries
        # no year and is looked up in the year of its row's date: "SC 46" on
        # "Hearing: 01/20/2026, Map Room, SL, 09:15 am", entered on 11 December
        # 2025, is Senate Calendar 46 of that December, and dated by its
        # hearing the row lost the link to it. The year the row was entered
        # in travels with it (cite_year), so the link is what it was. Not
        # for a petition read in: "HJ 7" on that row is the journal of the
        # day it was read.
        if (kind != "read in" and isinstance(created, datetime) and created != datetime.min
                and created.year != said.year):
            ev["cite_year"] = str(created.year)
        return ev
    return ev


# ---- a year one off -----------------------------------------------------------
#
# THE CLERK'S YEAR. A row entered around the turn of a year, or by a hand still
# writing last year's, states the right month and day in the year before:
#
#   "To Be Introduced 01/06/2015 and referred to Environment and Agriculture"
#   was entered on 14 December 2015 (HB 1615 of 2016); "Introduced 01/03/2023
#   and referred to Labor ..." on 1 December 2023 (HB 1178 of 2024); "Introduced
#   01/07/2025 and referred to ..." on 12 November and 10 December 2025 (HR 24,
#   HR 25 and HB 1535 of 2026). Each read as introduced a year before its
#   first hearing, and as "carried over".
#
#   "Hearing; February 4, 2003, Room 105-A, SH, 8:30 a.m.; SC3" was entered on
#   12 January 2004 on SB 407 of 2004, a bill introduced on the 7th: five
#   Senate bills of 2004 opened "The committee held a public hearing on
#   February 4, 2003. It was introduced on January 7, 2004". So did HB 69 of
#   2003 ("March 26, 2002"), HB 307 of 2005 ("May 18, 2004") and the
#   conference meetings of SB 302 of 2004 and of four Senate bills of 2014.
#
# THE TEST IS THE BILL'S OWN RECORD, NOT THE GAP. A row entered long after the
# day it states is usually right about the day: "Introduced 01/09/2025 and
# Referred to Election Law ..." was entered on 3 November 2025 on SB 215, which
# was heard that January, and "Hearing: 01/30/2019" on SB 69 of 2019 was
# entered that December. So the year is a slip only where
#
#   - the row states a day more than YEAR_SLIP_FAR days before it was entered;
#   - the same day a year on is in the bill's term and is a day the row can
#     have been entered for: from the day it was entered (a week before, for a
#     meeting entered once it had recessed) to YEAR_SLIP_AHEAD days after;
#   - and nothing else on the bill in that chamber had been entered by the
#     day the row states, or was within YEAR_SLIP_ALONE days after it: the
#     chamber did not have the bill then. Measured from the day the row
#     states to the chamber's first row, whenever that was entered -- SB 268
#     of 2014's conference "RECONVENE === 5/29/2013" was entered on 27 May
#     2014, and its introduction row on 11 December 2013 for 8 January: 196
#     days after the day stated, which a test of "more than 200 days" let
#     through as the Senate having the bill, seven months before it was
#     filed. An introduction must also come out on or before the next row of
#     its chamber.
#
# Meetings and introductions only. A floor row's stated day has rules of its
# own (docket_vocab.as_of), a report's is the calendar it was written for,
# and where clamp_year already brings a date outside the term back to the
# same day -- "Introduction and referring to Judiciary 1/28/98", entered on 28
# January 1999 -- that is left to it and nothing is noted.
YEAR_SLIP_KINDS = ("introduced", "hearing", "exec", "worksession", "conference_meeting")
YEAR_SLIP_FAR, YEAR_SLIP_AHEAD, YEAR_SLIP_ALONE = 150, 90, 30
CHAMBER_NAME = {"H": "House", "S": "Senate"}


def year_slip(ev, r, rows):
    """Put a meeting or an introduction dated in the year before the one its
    row was entered for into that year, keeping the date the docket gives
    beside it (date_as_recorded) with why."""
    intro = ev.get("_type") == "introduced"
    created = r.get("created")
    if (ev.get("_type") not in YEAR_SLIP_KINDS or not ONE_DATE.match(str(ev.get("date") or ""))
            or not isinstance(created, datetime) or created == datetime.min):
        return ev
    try:
        said = datetime.strptime(ev["date"], "%m/%d/%Y")
        meant = said.replace(year=said.year + 1)
        session = int(str(r.get("session"))[:4])
    except (TypeError, ValueError):
        return ev
    ahead = (meant.date() - created.date()).days
    if ((created.date() - said.date()).days <= YEAR_SLIP_FAR
            or not (0 if intro else -7) <= ahead <= YEAR_SLIP_AHEAD
            or not in_term(meant.year, meant.month, meant.day, session)):
        return ev
    others = [o["created"] for o in rows
              if o is not r and o.get("body") == r.get("body")
              and isinstance(o.get("created"), datetime) and o["created"] != datetime.min]
    if not others or (min(others).date() - said.date()).days <= YEAR_SLIP_ALONE:
        return ev
    if intro and meant.date() > min(others).date():
        return ev
    if clamp_year({"date": ev["date"]}, session)["date"] == meant.strftime("%m/%d/%Y"):
        return ev
    ev["date_as_recorded"] = said.strftime("%Y-%m-%d")
    ev["date_note"] = (
        f"The General Court's docket dates this {said.strftime(MONTH)}, in a row entered "
        f"on {created.strftime(MONTH)}. The {CHAMBER_NAME.get(r.get('body'), 'chamber')} "
        f"has no other row on the bill before {min(others).strftime(MONTH)}, so the year "
        f"is read as {meant.year}.")
    ev["date"] = meant.strftime("%m/%d/%Y")
    return ev


# ---- a meeting stated for a day before the chamber had the bill -----------------
#
# THE MONTH WRITTEN OUT, AND WRONG. The Senate's notices of 2007 to 2010 write
# the day in words (docket_era_2007.normalise turns them into dates), and one
# of the 2,684 names a day its bill did not exist on: "Hearing; January 10,
# 2009, Room 103, State House, 2:45 p.m.; SC10" on SB 106 of 2009, entered on
# 5 February, the day after the Senate's first row on the bill, "Introduced
# and Referred to Judiciary". Taken as written, the bill's history opened with
# a hearing 25 days before its introduction. Senate Calendar 10 prints the
# hearing under Tuesday 10 February: the month is the clerk's slip. A slip of
# a month is not a rule this reader can prove -- the year's slip above is, by
# the bill's own rows -- so the day is NOT TAKEN: the row keeps the day it
# was entered, as every such notice did before the month was read, and says
# so beside it. Putting the right day on it is a person's correction
# (docket_corrections.json), which outranks this.
#
# AND THE DAY IT WAS ENTERED IS NOT THE DAY THE COMMITTEE SAT. With the row on
# 5 February the history said "The committee held a public hearing on February
# 5, 2009", the day the notice was typed, while the bill's stations and the
# download still gave the 10 January the row states: one hearing, three days
# on one page, none of them the calendar's. The row keeps its place in the
# list of docket lines; the history tells the hearing without a day
# ("_no_day"), and the day the row states is carried out of build() as one
# the docket puts a sitting on and the history does not ("no_sitting"), which
# proceedings.notice_only reads, so that no station, committee's day or row
# of the download says 10 January either.
#
# Only a day the reader made out of a month in words (the event's "_spelled"),
# and only where no row of that chamber on the bill had been entered by it.
# A year's slip is found first and is not this.
STATED_BEFORE_THE_BILL = (
    "The docket's row states {said}, and the {chamber} has no row on the bill before "
    "{first}. The row is shown on the day it was entered, and the history gives the "
    "meeting no day.")


def before_the_bill(ev, r, rows):
    """Leave a written-out meeting day untaken where it is before the day the
    chamber's first row on the bill was entered (STATED_BEFORE_THE_BILL)."""
    created = r.get("created")
    if (not ev.get("_spelled") or ev.get("date_as_recorded")
            or not ONE_DATE.match(str(ev.get("date") or ""))
            or not isinstance(created, datetime) or created == datetime.min):
        return ev
    said = datetime.strptime(ev["date"], "%m/%d/%Y")
    first = min((o["created"] for o in rows
                 if o.get("body") == r.get("body") and isinstance(o.get("created"), datetime)
                 and o["created"] != datetime.min), default=None)
    if first is None or said.date() >= first.date():
        return ev
    ev["row_note"] = STATED_BEFORE_THE_BILL.format(
        said=said.strftime(MONTH), chamber=CHAMBER_NAME.get(r.get("body"), "chamber"),
        first=first.strftime(MONTH))
    ev["date"] = created.strftime("%m/%d/%Y")
    ev["_no_day"] = said.strftime("%Y-%m-%d")
    return ev


# ---- a row stamped decades outside its term --------------------------------------
#
# THE STAMP IS TYPED TOO. Five rows of the database's dockets carry an entry
# stamp in another century's year: 04/13/1900 (SB 391 of 1990), 01/06/1904 (SB
# 623 of 1994), 01/04/1905 (HB 171 of 1995), 01/29/1927 (HB 685 of 1997) and
# 12/02/1939 (SCR 1 of 1999). Four are rows that print a date, which the
# vocabulary's glue brings back into the bill's session. The fifth is the
# citation "SJ Org. Day, P 12-13", a row cut off the Senate's action of
# Organization Day, 2 December 1998 -- the rows either side of it are stamped
# 10:01 and 10:40 that morning, and it is stamped 10:03 -- and it states no
# date, so SCR 1 of 1999's list of docket lines opened in 1939 and the
# resolution was "carried over" across sixty years.
#
# A stamp more than STAMP_FAR years from the bill's session keeps its month,
# day and time and takes the year, of the session's and the two beside it,
# that puts it nearest another row of the bill. Real stamps outside a term
# are a year or two out, and are left alone: an opinion of the justices
# printed on 30 January 1997 for HB 1549 of 1996, SB 503 of 1998's meetings
# into 2000.
STAMP_FAR = 5
STAMP_REREAD = ("The General Court's docket stamps this row {stamp}. The rows entered beside "
                "it are of {near}, and the year is read as {year}.")


def stamps_in_reach(rows):
    """The rows, with a stamp decades outside the bill's session brought to
    the year nearest the bill's other rows (STAMP_FAR). A row put right
    carries its own stamp as "stamp_as_recorded"."""
    def far(r):
        c = r.get("created")
        try:
            return (isinstance(c, datetime) and c != datetime.min
                    and abs(c.year - int(str(r.get("session"))[:4])) > STAMP_FAR)
        except (TypeError, ValueError):
            return False
    if not any(far(r) for r in rows):
        return rows
    sane = [r["created"] for r in rows
            if isinstance(r.get("created"), datetime) and r["created"] != datetime.min
            and not far(r)]
    out = []
    for r in rows:
        if not far(r) or not sane:
            out.append(r)
            continue
        c, session = r["created"], int(str(r["session"])[:4])
        tries = []
        for y in (session - 1, session, session + 1):
            try:
                tries.append(c.replace(year=y))
            except ValueError:
                continue
        if not tries:
            out.append(r)
            continue
        best = min(tries, key=lambda t: min(abs((t - s).total_seconds()) for s in sane))
        out.append({**r, "created": best, "stamp_as_recorded": c})
    return out


# ---- the day of an introduction, read from the journal -------------------------
#
# AN INTRODUCTION ROW THAT STATES NO DAY IS DATED THE DAY IT WAS ENTERED, and
# these twelve were entered on another. A TABLE OF WHAT WAS READ, on 2 October
# 2026, not a rule: the House Record a row cites prints more than one sitting
# too often for a citation to date a row by itself.
#
#   2005-2006  HB 1216, 1278, 1281, 1283 and 1305 were entered on 14 December
#              2005 and HB 1612 and 1615 on 28 December, each citing "HJ 7"
#              at page 337, 339, 340 or 350. Of the 582 introduction rows of
#              the 2006 session that cite House Record 7, the other 575 were
#              entered on 4 January 2006, the day the session convened, and
#              each of the four pages is cited by 25 to 29 of them
#              (Docket_db_2005-2006.txt). The General Court's database gives
#              4 January for four of the seven and repeats the row's day for
#              three. The journal of that day is not on this disk.
#   2007-2008  HR 3 and HR 6 were entered on 7 December 2006, "Introduced and
#              adopted VV; HJ 3, p.24" and "p.25", the pages HR 1, 2, 4 and 5
#              cite in rows entered on the 6th. House Record 3 is the journal
#              of Organization Day, Wednesday 6 December 2006, and prints both
#              resolutions (journals/2007/HJ001.txt lines 676 and 755).
#              HB 332 was entered on 25 January 2007 citing "HJ 14, pg.207":
#              House Record 14 prints House Journal 3 of Thursday 4 January
#              2007, and lists HB 332 among the bills introduced that day
#              (journals/2007/HJ004.txt lines 8-10 and 535).
#   2015-2016  HB 1, "Introduced and Referred to Finance", was entered on 24
#              February 2015. The House Journal of Wednesday 18 February 2015
#              carries the resolution that read HB 1-A, HB 2-FN-A-L and HB
#              25-FN-A a first and second time (journals/2015/HJ020.txt lines
#              3704-3712); HB 2 and HB 25 are dated the 18th by their own rows.
#   2021-2022  CACR 21, the amendment on registers of probate that went to
#              the voters, has "Introduced and referred to Judiciary", entered
#              on 3 November 2021 with no day in it; the rows of CACR 13 to 20
#              and 22 to 35, entered with it, read "Introduced 01/05/2022 and
#              referred to ...". The House Journal of Wednesday 5 January 2022
#              carries the resolution that read "Constitutional Amendment
#              Concurrent Resolutions numbered 13 through 15, and 17 through
#              35" a first and second time ("journals/2022/HJ 01 January 5,
#              2022.txt" lines 1609-1614). Its introduction read 3 November
#              2021, and it was "carried over" from a year it was not in.
#
# {(term, bill): (the day, the chamber, what the page says of it)}. The row is
# the first of that chamber that begins "Introduced"; the day it was entered
# is kept beside it (date_as_recorded), as a person's correction keeps the
# docket's date. preflight reads the journals and the docket again wherever
# they are on disk.
#
# WHAT THE SEVEN OF 2006 SAY BESIDE THE ROW is that the day is read from the
# citation, because it is: no journal of 4 January 2006 was opened. The
# others name the journal that was.
_ENTERED_AHEAD = ("The docket's row was entered on {entered}, ahead of the day, and states no "
                  "date. It cites House Record 7 at a page that the other House bills of 2006 "
                  "cite in rows entered on {day}, and the day is read from that citation.")
_ENTERED_AFTER = ("The docket's row was entered on {entered} and states no date. The House "
                  "Journal records it on {day}.")
INTRODUCED_ON = {
    **{("2005-2006", b): ("2006-01-04", "H", _ENTERED_AHEAD)
       for b in ("HB1216", "HB1278", "HB1281", "HB1283", "HB1305", "HB1612", "HB1615")},
    ("2007-2008", "HR3"): ("2006-12-06", "H", _ENTERED_AFTER),
    ("2007-2008", "HR6"): ("2006-12-06", "H", _ENTERED_AFTER),
    ("2007-2008", "HB332"): ("2007-01-04", "H", _ENTERED_AFTER),
    ("2015-2016", "HB1"): ("2015-02-18", "H", _ENTERED_AFTER),
    ("2021-2022", "CACR21"): ("2022-01-05", "H", _ENTERED_AFTER),
}
INTRODUCTION_ROW = re.compile(r"^\s*Introduced\b", re.I)


def introduced_on(ev, r, bill, done):
    """Date the bill's introduction row by the journal's reading of it
    (INTRODUCED_ON). `done` is the bills whose row has been found."""
    created = r.get("created")
    try:
        key = (P.term_of(str(r.get("session"))), bill.upper())
    except (AttributeError, TypeError, ValueError):
        return ev
    read = INTRODUCED_ON.get(key)
    if (not read or key in done or r.get("body") != read[1]
            or not INTRODUCTION_ROW.match(ev.get("_raw") or "")
            or not isinstance(created, datetime)):
        return ev
    done.add(key)
    day = datetime.strptime(read[0], "%Y-%m-%d")
    if day.date() == created.date():
        return ev
    ev["date_as_recorded"] = created.strftime("%Y-%m-%d")
    ev["date_note"] = read[2].format(entered=created.strftime(MONTH), day=day.strftime(MONTH))
    ev["date"] = day.strftime("%m/%d/%Y")
    return ev


def _stop(s):
    """A sentence ended with exactly one full stop.

    A mover's surname can carry its own: 41 floor sentences of 2021-2022 ended
    "on a motion by Rep. Alexander Jr..", because the period that ends the
    sentence was added to a name that already had one. The name is right and
    the sentence is right; only the join was wrong.
    """
    s = s.rstrip()
    return s if s.endswith(".") else s + "."


# TODAY, so a scheduled meeting is not written as a held one. Overridable
# because a build that is reproducible cannot ask the clock, and because the
# fixtures need a fixed answer. build_date.today() is the clock, unless the
# build's day is stated.
TODAY = build_date.today()


def ahead(d):
    """True if this docket date is still in the future.

    THE SITE MUST NOT SAY A MEETING HAPPENED BECAUSE IT IS ON THE DOCKET.
    A committee posts a hearing or a work session days or weeks before it
    sits, and every sentence in this file was written in the past tense, so
    thirteen bills of the current term read "The committee held a work session
    on October 13, 2026" for a session that has not been held. That is the
    site stating a future event as fact, which is worse than saying nothing.
    """
    try:
        return datetime.strptime(d, "%m/%d/%Y").date() > TODAY
    except (ValueError, TypeError):
        return False


# The older dockets' vocabulary. Optional: without it, a database-era bill
# is read by the modern patterns alone, which is what happened until
# 11 September and left the archive with no histories before 2017.
try:
    import docket_vocab as _VOCAB
except ImportError:                                         # pragma: no cover
    _VOCAB = None


# "== BILL KILLED ==" and "=== BILL KILLED ===". Two equals signs were
# allowed for and three were not, so 717 floor lines kept a flag in the
# middle and no pattern could read them.
FLAG_MARK = re.compile(r"=={1,}\s*[A-Z][A-Z ]*?\s*=={1,}")
# The clerk's cancel mark among those flags, spelled with one L or two.
CANCEL_WORD = re.compile(r"CANCELL?ED")


def clean(s, keep_cancel=False):
    """The docket line as every pattern here reads it: the clerk's flags
    taken out, and a citation at its end. With keep_cancel, a cancel mark
    stays where the clerk typed it (marked_line)."""
    s = FLAG_MARK.sub(lambda m: m.group(0) if keep_cancel and CANCEL_WORD.search(m.group(0))
                      else " ", s)
    s = re.sub(r"\s*(?:HJ|SJ|HC|SC)\s+\d+\b.*$", "", s)
    return re.sub(r"\s{2,}", " ", s).strip(" .;,")


def marked_line(desc, raw):
    """The line as the bill's docket list shows it where the clerk put a
    cancel mark on it, or "" where the line carries none (the person, 7
    October 2026: the list "shows the clerk's own cancel mark (for example
    ==CANCELLED==) on the rows that carry one, as the official docket prints
    it").

    Every line is read with its flags taken out (clean), which is right for
    reading it and took the one word a reader of the list most needs off a
    meeting that never sat: "===CANCELLED=== Public Hearing: 1/15/2013 2:00
    PM LOB 301" was listed as "Public Hearing: 1/15/2013 2:00 PM LOB 301".
    `raw` is the line as read; where it is the clerk's line cleaned, the mark
    goes back where the clerk typed it ("Hearing; === CANCELLED === January
    22, 2009, ..."), and where an era's reader made the line otherwise, the
    mark leads it, which is where the clerk typed it on nearly every row."""
    plain = clean(desc)
    kept = clean(desc, keep_cancel=True)
    if kept == plain:
        return ""
    if plain == raw:
        return kept
    marks = [m.group(0) for m in FLAG_MARK.finditer(desc) if CANCEL_WORD.search(m.group(0))]
    return " ".join(marks + [raw]) if raw else ""


# --------------------------------------------------------------- classify


# --- event families found in a full session's docket ------------------------

# "OT3rdg" = ordered to third reading, the procedural step after passage.
OT_RDG = re.compile(r"\bOT(\d)rdg\b", re.I)

# THE STEP AFTER OUGHT TO PASS, LEFT PENDING BY A TABLING (7 October 2026).
# The Senate passes a bill by ordering it to a third reading, "Ought to Pass:
# MA, VV; OT3rdg", or under its Rule 4-5 sends it to Finance first. A tabling
# moved between the two leaves the docket saying which was interrupted: SB
# 131 of 2025 has "Ought to Pass: MA, VV", "Sen. Gray Moved Laid on Table,
# MA, VV" and "Pending Motion OT3rdg", all of 27 March -- Senate Journal 9
# prints the motion "Adopted." and the tabling, and no "bill ordered to Third
# Reading" -- and it died under Rule 3-23 in October. Its history said "the
# Senate voted to pass it", and so did 62 others of the term. SB 476 of 2026
# was ordered to a third reading and "The Chair rescinded OT3rdg" before the
# tabling; SB 635 of 2026's "Pending Motion Refer to Finance Rule 4-5" is the
# same a step earlier. build_site_v2.journey asks this too, so the rail and
# the history are one reading.
PASSAGE_PENDING = re.compile(
    r"(?:^|;)\s*pending\s+motion\W*(?:(?P<third>OT\s?3\s?rd?g\b)|refer\w*\s+to\s+finance\b)",
    re.I)
OFF_TABLE = re.compile(r"\b(?:remov\w*|taken|take)\s+(?:\w+\s+){0,2}from\s+(?:the\s+)?table",
                       re.I)
# The pending order carried on a later day, with no code: "OT3rdg; 03/21/2024",
# the day SB 173 of 2024 came off the table (its Ought to Pass was of 3
# January), and "OT3rdg" on SB 144 of 2015.
BARE_THIRD = re.compile(r"^\s*OT\s?3\s?r?d?g\s*(?:;\s*\d{1,2}/\d{1,2}/\d{2,4}\s*)?$", re.I)
# The day a row states at its end. A row no pattern reads is dated by its
# entry: SB 86 of 2025's "Pending Motion OT3rdg; 03/27/2025" was entered on 4
# June.
ROW_DAY = re.compile(r";\s*(\d{1,2}/\d{1,2}/\d{4})\s*$")


def row_day(raw, fallback=""):
    """"2025-03-27" from a row ending "; 03/27/2025", else `fallback`."""
    m = ROW_DAY.search(raw or "")
    if m:
        try:
            return datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return fallback or ""


def passage_left_pending(rows):
    """{(body, day): "third" | "finance"}: the sittings at which a chamber
    tabled the bill with its third reading (or its referral to Finance)
    pending, and did not take it off the table again later that day. `rows`
    is [(body, day, raw)] in the docket's order. HB 1601 of 2018 was taken off
    and ordered to a third reading the same day; HB 726 of 2019's motion to
    take it off failed, 10-13, and it died on the table."""
    held = {}
    for body, day, raw in rows:
        m = PASSAGE_PENDING.search(raw or "")
        if m:
            held[(body, day)] = "third" if m.group("third") else "finance"
            continue
        off = OFF_TABLE.search(raw or "") if held.get((body, day)) else None
        if off and not re.search(r"\b(?:MF|ML)\b|\b(?:failed|lost)\b", raw[off.end():]):
            if re.search(r"\bMA\b|\badopted\b", raw[off.end():]) or re.match(
                    r"removed|taken", off.group(0), re.I):
                held[(body, day)] = ""
    return {k: v for k, v in held.items() if v}

# "Committee Amendment # 2025-1234s, AA, VV; 03/06/2025"
# "Amendment # 2025-1234h: AA VV 03/06/2025"
# "Enrolled Bill Amendment # 2025-2001e Adopted, VV, (In recess 06/26/2025)"
# "Sen. Birdsell Floor Amendment # 2026-1719s, AA, VV; 03/06/2026" -- the
# Senate puts the member who offered it in front, and the anchor meant 22 of
# these were not read as amendments at all. The name is captured rather than
# skipped, because who moved an amendment is worth a clause.
# "FLAM # 2026-1971h(NT) (Rep. Pauer): AA RC 171-162 05/14/2026" -- the
# House's floor amendment, with its mover in brackets. No pattern read it,
# and all 108 of 2025-2026 were told nowhere (classify gives "Floor
# Amendment" and the mover).
AMEND_RE = re.compile(
    # The name must not swallow the kind: "Sen. Birdsell Floor Amendment" is
    # a floor amendment offered by Birdsell, not an amendment by "Birdsell
    # Floor".
    r"^(?:(?P<mover>(?:Rep|Sen)\.\s+"
    r"(?:(?!Enrolled\b|Committee\b|Floor\b|Amendment\b)[A-Z][\w'\u2019.\-]*\s+){1,3}))?"
    r"(?P<what>(?:Enrolled Bill |Committee |Floor )?Amendment|FLAM\b)\s*#?\s*"
    # Not a number the clerk split with a space, "FLAM # 2022-041 7h (Rep.
    # Testerman): AF VV 02/16/2022" (HB 1598 of 2022): read as "2022-041", it
    # lost its day and was told after the bill's referral of that day, inside
    # Ways and Means' stage. It stays unread, as it was before FLAM was read.
    r"(?P<num>\d{4}-\d+[a-z]*)(?![\da-z])(?!\s\d+[a-z]\b)\s*[,:]?\s*"
    # The motion, the vote kind and the tally, in whatever order and
    # punctuation the chamber uses, each at most once:
    #
    #   House   "Amendment # 2025-1488h: AA RC 200-175 04/10/2025"
    #   Senate  "Floor Amendment # 2025-2647s, RC 9Y-15N, AF; 06/05/2025"
    #
    # None of the three was allowed for between the number and the date, so
    # every roll-called or divided amendment lost BOTH its tally and its date
    # -- the date pattern was left sitting in front of "200-175". Thirteen of
    # HB2's Senate amendments were undated in the published narrative and 26
    # of its House ones were dated only by the sentence before them.
    #
    # AND THE DOCKET PUTS THINGS BETWEEN THE NUMBER AND THE MOTION. Nothing
    # was allowed there, so the alternation below matched zero times and the
    # line lost its motion, its vote kind AND its tally together -- 1,075
    # amendment events, every one of them with vote_kind None. 2025-2026
    # SB13 reads "Amendment # 2025-1934h (NT): AA DV 183-163" -- adopted on
    # a division of 183 to 163 -- and the site showed none of the three. The
    # date survived, because it is matched separately, which is why this
    # looked like nothing was wrong.
    #
    # WHAT IS ACTUALLY THERE, counted over those 1,075 lines rather than
    # guessed at: the New Title marker in four punctuation shapes ((NT):
    # 330, "NT," 175, (NT) 79, "NT;" 5), a parenthesised sponsor ((Rep 132,
    # (Rep. 48, (Reps 15), and the enrolled-bill marker (E 26, -EBA: 17,
    # EBA 6). None of the three carries an outcome, so they are skipped
    # rather than captured -- this pattern is read for what the chamber
    # DID, and a title change is not that.
    r"(?:(?:\(?(?:NT|New Title)\)?|-?EBA)[,;:]?\s*"
    r"|\((?P<by>(?:Reps?|Sens?)\.?[^)]*)\)[,;:]?\s*){0,3}"
    # DIV is the House's other spelling of a division, and "Failed" is the
    # spelled-out form of AF. The docket writes the outcome either way and
    # this had the abbreviation of both and the word for only one -- the
    # same half-a-pair that left 153 events with no outcome in
    # build_site_v2.ADOPTED.
    r"(?:(?:(?P<motion>AA|Adopted|AF|AL|Failed)"
    r"|(?P<vote>VV|DIV|DV|RC)"
    r"|(?P<y>\d+)\s*Y?\s*[-\u2013]\s*(?P<n>\d+)\s*N?)[,;]?\s*){0,4}"
    r"(?:\(?(?:in recess of|In recess)\)?\s*)?"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)

# AN AMENDMENT NUMBER WITH NO YEAR, WITH ITS LETTER (the launch audit's
# recheck of 7 October 2026): "Amendment # 0339h: AA VV 03/13/2025" (HB 179
# of 2025, the committee's amendment), "FLAM # 1282h (Rep. Johnson): AF DV
# 60-270 03/31/2022" (HB 1627 of 2022). AMEND_RE wants the year, and 3 rows of
# 2025-2026 and 89 of 2021-2022 the House adopted or rejected were told by no
# history and missing from the amendments list. Read in build() for the
# dockets of 2017 on only: the database's of 1989-2016 have era readers of
# their own for such rows ("Committee Amendment 1502s, Not Voted On"), and
# AMEND_RE reading them first would take the rows from those readers. Told as
# the clerk wrote it, with no year put to it: a bill carried over moves
# amendments of the year before.
AMEND_YEARLESS = re.compile(
    AMEND_RE.pattern.replace(r"(?P<num>\d{4}-\d+[a-z]*)", r"(?P<num>\d{3,4}[a-z])", 1), re.I)


def yearless_amendment(ev):
    """The amendment event of a row AMEND_YEARLESS reads, in classify()'s
    shape; else None."""
    m = AMEND_YEARLESS.search(ev.get("_raw") or "")
    if not m:
        return None
    d = m.groupdict()
    by = (d.pop("by", None) or "").strip()
    if (d.get("what") or "").upper() == "FLAM":
        d["what"] = "Floor Amendment"
        if by and not d.get("mover"):
            d["mover"] = re.sub(r",\s*(?=[^,]+$)", " and ", by)
    return {**d, "_type": "amendment", "_raw": ev["_raw"]}


# WHAT BECAME OF AN AMENDMENT WHOSE ROW CARRIES NO MOTION THE PATTERN ABOVE
# READS. A blank motion was written as "was rejected", and it is not one:
# "Sen. Birdsell Floor Amendment # 2026-0720s; 02/19/2026" is the Senate
# ANNOUNCING the amendment at 10:23, and "... # 2026-0720s, AA, VV" at 10:26
# is it carrying, so HB 266 of 2026 read that 0720s was rejected and then
# adopted. 192 amendment rows of 2007-2026 carry no motion that pattern reads,
# on 118 bills, and every one of them said "rejected" -- falsely for 150 rows
# on 97 bills. 61 were announcements another row decides; the rest say what
# happened in words the pattern does not take -- "Withdraws", "Not Voted On",
# "Ruled Non-Germane", and codes in another order, "Division 17Y-7N, AA" (SB
# 212 of 2012, adopted) or "MF RC 157-162" (SB 375 of 2012, rejected) -- or
# say nothing at all.
AMEND_SAID = [
    (re.compile(r"withdr[ae]w", re.I), "withdrawn"),
    (re.compile(r"not voted on", re.I), "not voted on"),
    (re.compile(r"non-?germane", re.I), "ruled non-germane"),
    (re.compile(r"\b(?:AF|AL|MF|ML)\b|\b(?i:fail(?:ed|s)?)\b"), "rejected"),
    (re.compile(r"\b(?:AA|MA)\b|\b(?i:adopted)\b"), "adopted"),
]
# A motion ABOUT the amendment is not its outcome: "Floor Amendment
# #2014-0025h, Divide Sections 1-8 (Rep. Jasper) MF RC 160-183" is the motion
# to divide failing, and HB 544 of 2014 then adopted 0025h 186-155.
AMEND_ABOUT = re.compile(r"\bdivide\b|\btable\b|reconsider|special order", re.I)
# A vote on some of it: "Committee Amendment #2020-1471s : Sections 7 and 24,
# RC 12Y-12N, AF" (HB 1166 of 2020), "Remainder of the Amendment".
AMEND_PART = re.compile(r"\bsections?\b|\blines?\b|remainder|balance of|\baccount\b", re.I)
AMEND_VOTE = re.compile(r"\b(RC|VV|DV|DIV|Div\.?|Division)(?![\w])", re.I)
AMEND_TALLY = re.compile(r"\b(\d{1,3})\s*Y?\s*[-–]\s*(\d{1,3})\s*N?\b")
# The Senate's verb before "Floor Amendment", which the mover pattern takes
# for a second name: "Sen. Bradley Offered", "Sen. Houde Withdrew".
MOVER_VERB = re.compile(r"\s+(?:offered|offers|withdr(?:ew|aws|awn))\s*$", re.I)


def amendment_outcome(raw):
    """(said, part, vote kind, yeas, nays) from a row AMEND_RE read no motion
    on, said being None where the row states no outcome. Quoted amending
    language is not the row's own words: HB 1623 of 2020's "... Reading as
    Intended: "Amend RSA 415-J:3, IV-VI, as inserted by section 3 ...", AA,
    VV" adopted the whole amendment, not a section of it."""
    raw = re.sub(r'"[^"]*"', " ", raw or "")
    said = next((w for rx, w in AMEND_SAID if rx.search(raw)), None)
    if said in ("adopted", "rejected") and AMEND_ABOUT.search(raw):
        said = None
    if said not in ("adopted", "rejected"):
        return said, False, None, None, None
    vk = AMEND_VOTE.search(raw)
    tally = AMEND_TALLY.search(raw, vk.end()) if vk else None
    kind = None
    if vk:
        kind = {"RC": "RC", "VV": "VV"}.get(vk.group(1).upper(), "DV")
    # As text, the way AMEND_RE hands its own tally over: a unanimous
    # "24Y-0N" has a nay count of "0", which is there, where 0 would not be.
    return (said, bool(AMEND_PART.search(raw)), kind,
            tally.group(1) if tally else None,
            tally.group(2) if tally else None)


# ONE AMENDMENT, SPELLED SEVERAL WAYS. SCR 1 of 2013 announced "2013-1554h"
# in May and rejected "1554h(NT)" in June; SB 88 of 2011 laid "#2235(NT)" on
# the table; SB 135 of 2017 divided the question on "2017-1215". Matched
# letter for letter, each announcement was read as never decided, and the
# history said "the docket records no vote on it" a sentence away from the
# vote. The year, the leading zeros and the chamber's letter may each be
# missing; the digits may not. A bare number counts only with its letter or
# after "#", so a tally, a date or a section is never taken for one.
AMEND_NUM = re.compile(
    r"(?:\b(?P<year>(?:19|20)\d\d)-|(?P<hash>[#{])\s*|\b)"
    r"(?P<digits>\d{3,4})(?P<letter>[a-z])?(?![\w-])")
# What another row says of an amendment it names: "Sen. Boutin Withdrew Floor
# Amendment 1550s" (HB 422 of 2014), "Chair Ruled Sections of Amendment #
# 2025-0752s Non-Germane" (SB 119 of 2025). Neither is an amendment row, so
# neither is told, and the announcement is the one place to say it.
AMEND_WITHDRAWN = re.compile(r"withdr[ae]w", re.I)
AMEND_RULED = re.compile(r"\bruled\b[^;]*non-?germane", re.I)


def amend_keys(text):
    """(year, number, letter) for every amendment number text names, the
    year and the letter None where it leaves them out."""
    out = []
    for m in AMEND_NUM.finditer(text or ""):
        y, d, ltr = m.group("year"), int(m.group("digits")), m.group("letter")
        if not (y or ltr or m.group("hash")):
            continue
        # "2017-2018" is a term, not amendment 2018 of 2017.
        if y and not ltr and d == int(y) + 1:
            continue
        out.append((y, d, ltr))
    return out


def same_amendment(a, b):
    """Do two amend_keys() name one amendment? The number must agree, and
    the year and letter wherever both are written."""
    return a[1] == b[1] and all(x == z or not x or not z
                                for x, z in ((a[0], b[0]), (a[2], b[2])))


# WHOSE AMENDMENT AN AMENDMENT ROW MOVES, where the row's own word does not
# say. The House adopts its committee's amendment on a bare row --
# "Amendment # 2026-0989h: AA VV 03/11/2026" (HB 1449 of 2026), which House
# Journal 7 prints as "Majority Amendment (0989h)" under the report -- and
# enters an amendment a member offers as "FLAM # 2026-1971h(NT) (Rep.
# Pauer)". A number one of the bill's own reports in that chamber names is
# that report's amendment, the committee's or its minority's, whoever moved
# it; any other is one offered on the floor.
WHOSE_KIND = {"committee": "Committee Amendment", "minority": "Minority Amendment"}


def whose_amendment(evs):
    reported = [(k, report_side(e.get("side")), e["body"]) for e in evs
                if e["_type"] == "report" and not e.get("cancelled")
                for k in amend_keys(e.get("_raw"))]
    for e in evs:
        if e["_type"] != "amendment" or (e.get("what") or "").strip().lower() not in (
                "amendment", "floor amendment"):
            continue
        mine = amend_keys(e.get("num"))[:1]
        side = next((s for k, s, b in reported if mine and b == e["body"]
                     and same_amendment(k, mine[0])), None)
        if side is not None:
            e["_whose"] = "minority" if side == "Minority" else "committee"


# "Enrolled Adopted, VV, (In recess 06/26/2025)" / "Enrolled (in recess of) 06/26/2025"
ENROLLED_RE = re.compile(
    r"^Enrolled\b(?!\s+Bill)\s*(?P<motion>Adopted)?[,;]?\s*(?P<vote>VV|DV|RC)?[,;]?\s*"
    r"(?:\(?(?:in recess of|In recess)\)?\s*)?(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)

RETAINED_RE = re.compile(r"^Retained in Committee", re.I)

# A bill sent to interim study comes back with a report, and the report is the
# last thing that happens to it. Real line, from a bill on the live site:
#
#   "Interim Study Report: Not Recommended for Future Legislation 06/02/2026
#    (Vote 14-0; RC)"
#
# The recommendation is captured rather than matched, for the same reason the
# veto outcome is: the negative form is the common one, and a pattern looking
# for "Recommended" would read a rejection as an endorsement. It is then
# repeated in the committee's own words.
INTERIM_REPORT_RE = re.compile(
    r"^Interim Study Report\s*:\s*(?P<rec>[^0-9]+?)\s*"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})?\s*"
    r"(?:\(\s*Vote\s*(?P<y>\d+)\s*-\s*(?P<n>\d+)\s*;?\s*(?P<cal>CC|RC)?\s*\))?\s*$",
    re.I)

# "SB 123 was Removed from the Consent Calendar; 05/15/2025"
# A bill pulled off the consent calendar is taken up on its own instead of
# being adopted with the rest without discussion. That is a substantive event
# and it was being dropped.
CONSENT_OFF_RE = re.compile(
    r"^(?P<bill>[A-Z]+\s*\d+)?\s*was Removed from the Consent Calendar"
    r"[;,]?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)

# "Conference Committee Meeting: 06/12/2025 10:00 am GP 201"
# Where a contested bill gets its final wording, and we index those videos.
CONF_MEET_RE = re.compile(
    r"^Conference Committee Meeting[:\s]+(?P<date>\d{1,2}/\d{1,2}/\d{4})"
    r"\s*(?P<time>\d{1,2}:\d{2}\s*[ap]m)?\s*(?P<venue>[A-Z].*)?$", re.I)
DIED_RE = re.compile(r"^Died on Table[,;]?\s*Session ended\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)
# A CHAMBER'S VOTE ON A COMMITTEE OF CONFERENCE'S REPORT (the launch audit of
# 7 October 2026, cause 10). "Conference Committee Report # 2026-2109c; RC
# 15Y-8N, Adopted; 06/04/2026" (the Senate) and "Conference Committee Report
# 2026-2109c: Adopted, RC 183-170 06/04/2026" (the House), HB 1300 of 2026:
# read by no pattern, so no history of 2007-2026 said a conference report was
# adopted, while the rail drew both votes. The number with its letter is
# required, which leaves the 1999-2008 readers' "Conference Committee
# Report{2206}" to them; a "Filed" row is the report arriving, not a vote on
# it. No date is captured: the row is dated by stated_day ("conference
# vote"), as it was while it was read by nothing.
CONF_REPORT_RE = re.compile(
    r"^Conference\s+Committee\s+Report\s*#?\s*(?P<num>(?:\d{4}-)?\d{3,4}[a-z])\b"
    r"(?!.*\bFiled\b).*?\b(?P<outcome>Adopted|Failed)\b", re.I)
# A BILL ENDED BY SENATE RULE 3-23 (the launch audit of 7 October 2026, cause
# 11): "Inexpedient to Legislate, Senate Rule 3-23, 10/31/2025" (SB 131 of
# 2025), "..., Adjournment 09/16/2020" (HB 1101 of 2020), "Inexpedient to
# Legislate, 2013 Adjournment, Senate Rule 3-23" (HB 135 of 2013). Read by no
# pattern, so 67 histories of 2025-2026 never said how the bill ended, while
# the rail drew it; SB 131's ended with the Senate's tabling. 723 of the 724
# rows on disk follow a Senate tabling. Dated by stated_day ("adjournment"),
# as it was while it was read by nothing. Its own type, not "died": the rail's
# reader passes over a "died" row as no floor action.
SENATE_RULE_KILL_RE = re.compile(
    r"^Inexpedient\s+to\s+Legislate,?\s*(?:\d{4}\s+Adjournment,?\s*)?"
    r"Senate\s+Rule\s+3-23\b", re.I)
# A PUBLIC HEARING ON A PROPOSED NON-GERMANE AMENDMENT (the launch audit of 7
# October 2026, cause 15). The House: "Public Hearing on non-germane Amendment
# # 2025-0102h: 02/11/2025 01:30 pm LOB 210-211" (HB 519 of 2025, which has
# sign-ins that day), "Public Hearing on non-germane Amendment #2016-0081h
# (NT): ...", "Public Hearing on Proposed Non-Germane Amendment ...", "...
# Non-Germane AM ...". The Senate: "Hearing: 02/18/2026, Room 103, SH, 09:00
# am, on proposed non-germane amendment # 2026-0579s" (SB 425 of 2026), and
# "Hearing: 4/16/13, Room 103, LOB, 10:00 a.m. Proposed non-germane amendment
# to HB 636 #2013-1233s". Read by no pattern: 65 hearings on 59 bills of
# 2025-2026 were in no history, and the House's were dated by the day the
# row was entered. Its own type, not "hearing": the meeting rules
# (overtaken, voided_meetings, whole_day) are about the bill's own hearings,
# and HB 1300 of 2026's of 10:00 and its hearing on 2026-0093h at 10:15 are
# two hearings of one day. The Senate's rows state their day as a hearing
# notice does, and keep it by stated_day ("notice"), as they did while they
# were read by nothing. And the bill's own hearing whose row says it takes
# the amendment up too, "Public Hearing: 4/21/2015 1:00 PM Representatives
# Hall; to include consideration of non-germane amendment #2015-1351h" (SB 30
# and SB 242 of 2015), which the hearing pattern could not read for what
# follows its room ("incl").
NONGERMANE_HEARING_HOUSE = re.compile(
    r"^Public\s+Hearing\s+on\s+(?:Proposed\s+)?Non-?\s?Germane\s+(?:Amendment|AM)\b\.?\s*"
    r"(?:#\s*)?(?P<num>(?:\d{4}-)?\d{3,4}[a-z])?\s*(?:\(NT\))?\s*:\s*"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)
NONGERMANE_HEARING_SENATE = re.compile(
    r"^(?P<joint>Joint\s+)?Hearing\b[^:;]{0,80}?:\s*(?P<sdate>\d{1,2}/\d{1,2}/\d{2,4})\b.*?"
    r"\b(?:on\s+)?proposed\s+non-?\s?germane\s+amendment\b(?:\s+to\s+[A-Z]+\s*\d+)?\s*(?:#\s*)?"
    r"(?P<num>(?:\d{4}-)?\d{3,4}[a-z])?", re.I)
NONGERMANE_HEARING_WITH_BILL = re.compile(
    r"^Public\s+Hearing\s*:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})\b[^;]*;\s*"
    r"(?P<incl>to\s+include\s+consideration\s+of)\s+non-?\s?germane\s+amendment\s*(?:#\s*)?"
    r"(?P<num>(?:\d{4}-)?\d{3,4}[a-z])?", re.I)
REREF_RE = re.compile(r"^Referred to\s+(?P<committee>[A-Z][A-Za-z,&\-\s]+?)\s+"
                      r"(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)

# The end of a session is where the docket's wording changes completely, and
# none of it was being recognised. These are real lines, taken from bills on
# the live site:
#
#   "Veto Sustained 08/19/2026: RC 152-167 Lacking Necessary Two-Thirds Vote"
#   "Notwithstanding the Governor's Veto, Shall SB 434 Become Law: RC 16Y-8N,
#    Veto Overridden by necessary two-thirds vote; 08/19/2026"
#
# The House states the outcome first; the Senate states the question first and
# the outcome last. That is the same split as the motion vocabularies in
# rollcall_parser.py, where the House abbreviates and the Senate spells out.
#
# The outcome word is CAPTURED, never assumed. A pattern that only knew how to
# find "Overridden" would silently miss every sustained veto, and a sustained
# veto is the more common result.
VETO_HOUSE_RE = re.compile(
    r"^Veto\s+(?P<outcome>Sustained|Overridden)\b[,;:]?\s*"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})?\s*[,;:]?\s*"
    r"(?:(?P<vote>RC|VV|DV)\s*(?P<y>\d+)\s*[-\u2013]\s*(?P<n>\d+))?", re.I)

VETO_SENATE_RE = re.compile(
    r"^Notwithstanding the Governor'?s Veto,?\s*Shall\s+[A-Z]+\s*\d+\s+Become\s+Law"
    r"[,;:]?\s*(?:(?P<vote>RC|VV|DV)\s*(?P<y>\d+)\s*Y?\s*[-\u2013]\s*"
    r"(?P<n>\d+)\s*N?)?[,;:]?\s*Veto\s+(?P<outcome>Sustained|Overridden)"
    r"(?:.*?[;,]\s*(?P<date>\d{1,2}/\d{1,2}/\d{4}))?", re.I)

# A bill the governor neither signs nor returns becomes law regardless, and the
# docket says so two different ways. Both were unrecognised, which meant a bill
# that is law read as though it were still sitting on the governor's desk.
#
#   "Law Without Signature 08/19/2026; Chapter 344; Effective 08/19/2026; ..."
#   "Enacted in accordance with Article 44 PartII of the N.H. Constitution
#    without the signature of the governor. Chapter 343;I. sec 4 eff 12/1/26..."
#
# The second form carries no full date at all -- its effective dates use
# two-digit years -- so the event falls back to the docket row's own timestamp
# rather than inventing one.
UNSIGNED_RE = re.compile(
    r"^Law Without Signature\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?"
    r"(?:.*?Chapter\s*(?P<chapter>\d+))?", re.I)
ENACTED_RE = re.compile(
    # ".*?" rather than "[^.]*?": the clause in between contains "N.H.", and a
    # class excluding dots can never cross it.
    r"^Enacted in accordance with Article\s*44.*?without the signature of the"
    r"\s*governor\.?\s*(?:.*?Chapter\s*(?P<chapter>\d+))?", re.I)

# A BILL WITHDRAWN, on a row that is not a floor vote (1 October 2026). Twelve
# rows across every docket on disk, all of them on bills the General Court's
# search page left out and the site had no record of: "Withdrawn Prior to
# Introduction" on four bills of 2010, "Withdrawn" and "Withdrawn 11/30/2011"
# on three of 2012, "Read in January 4, 2012 and Withdrawn" on a petition.
# The whole line, so that "Withdrawn from Committee Without Recommendation"
# -- a committee discharged -- is not one; a withdrawal the chamber voted,
# "Withdrawn (Rep Kreis): MA VV", is a floor row and is read as one.
# AND A PETITION ITS PETITIONER WITHDREW: "Petition Withdrawn By Petitioner",
# the last row of PET 7 of 2012, entered the day its committee was to vote on
# it. The row was read by nothing and the petition read "In committee".
WITHDRAWN_ROW = re.compile(
    r"^\s*(?:Read\s+in\s+(?P<read>[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})\s+and\s+)?"
    r"(?:Petition\s+)?Withdrawn(?P<prior>\s+Prior\s+to\s+Introduction)?"
    r"(?P<by>\s+By\s+Petitioner)?"
    r"(?:\s+(?P<date>\d{1,2}/\d{1,2}/\d{4}))?\s*$", re.I)
# "Proposed bill for special sesssion." is the one row of HB 3 of the 2006
# special session: a bill proposed for it, and nothing after.
PROPOSED_ROW = re.compile(
    r"^\s*Proposed\s+bill\s+for\s+(?:the\s+)?special\s+sess+ion\s*$", re.I)
# The introduction row as the House wrote it weeks ahead: "To Be Introduced
# 1/6/2010 and Referred to Finance". Every bill of those sessions carries it
# and was introduced on that day -- except one withdrawn first (build()).
TO_BE_INTRODUCED = re.compile(r"^\s*To\s+Be\s+Introduced\b", re.I)
# AN INTRODUCTION ROW WITH NO DAY IN IT, in a docket of 2017 on: "Introduced
# and referred to Judiciary", CACR 21 of 2022, the one such row of those
# dockets. The pattern below wants a day, so the row was read by nothing: the
# amendment's history never said the House had introduced it, and opened "It
# was introduced on February 24, 2022 and referred to the Senate ...", of a
# House measure. Read in build(), for these dockets only -- the older ones
# have their own readers of the same words -- and dated the day it was
# entered, which the journal's reading then puts right (INTRODUCED_ON). Not
# "To Be Introduced and referred to ...", which is a plan (CACR 6 of 2021's
# last row, another measure's).
INTRODUCED_UNDATED = re.compile(
    r"^\s*Introduced\s+and\s+referred\s+to\s+(?P<committee>[A-Z][^;:(]*?)\s*$", re.I)
# A RESOLUTION INTRODUCED AND ADOPTED IN ONE MOTION (7 October 2026). On
# Organization Day each chamber adopts its first resolutions -- its rules, its
# officers -- as they are introduced, and the docket says so in one row:
# "Introduced and Adopted VV 12/04/2024  HJ 1" (HR 1 to HR 5 of 2025),
# "Introduced and Adopted, VV; 12/04/2024;  SJ 1" (SR 1 to SR 5), "Introduced
# and adopted VV; HJ 3, p.24" (HR 1 of 2007). From 2007 nothing read the row --
# 172 of them -- so those resolutions had no history and no sitting page was
# drawn for 4 December 2024. The reader of 1999-2006 already reads the same
# words as the chamber's adoption (docket_era_1999.WORDS: "Introduced and
# adopted" is "Ought to Pass"), and the later rows are read the same way, and
# told in the sentence every adopted resolution's passage has. Read in build(),
# where the bill is known: only a resolution's, and only where its chamber
# records no passage of its own -- for HR 16 of 2020, HJR 3 of 2019 and SJR 2
# of 2020 the row is the motion to introduce, each passed on a row of its own
# ("Ought to Pass : MA VV"), and for HB 3 of 2019 the House taking the bill up.
# Not the row the floor pattern already reads, "Introduced and Adopted: MA RC
# 314-25". A date in brackets, "[11/30/2011]" (HR 14 of 2011, entered on 4
# January), is the sitting it was done in.
INTRODUCED_ADOPTED = re.compile(
    r"^\s*Introduced\s+and\s+Adopted\b(?!\s*(?:\([^)]*\)\s*)?:)\s*"
    r"(?:\(without\s+objection\)\s*)?[,;\s]*"
    r"(?:\[\s*(?P<asof>\d{1,2}/\d{1,2}/\d{4})\s*\]\s*[,;]?\s*)?"
    r"(?:(?P<vote>VV|RC|DV)\b\s*(?:(?P<y>\d+)\s*Y?\s*-\s*(?P<n>\d+)\s*N?)?)?"
    r"[,;\s]*(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)
RESOLUTION = re.compile(r"^[HS](?:C|J)?R\d+$", re.I)
PASSAGE_ROW = re.compile(r"^\s*Ought\s+to\s+Pass\b", re.I)


def _adopted_in_term(when, r, bill, session):
    """Whether an "Introduced and Adopted" row's day can be the adoption's: a
    day in the bill's own term, or one a person corrected the row to
    (docket_corrections.json).

    A DAY BEFORE THE TERM IS A SLIP, AND A SITTING NOBODY HELD (the review of
    7 October 2026). HR 6 of 2021, memorializing Speaker Hinch, reads
    "Introduced and Adopted VV 01/06/2020 HJ 2 P. 2", entered on 7 January
    2021: House Journal 2 is the sitting of 6 January 2021, and read as
    stated the row drew "The House, Monday 6 January 2020", a sitting of the
    term before. Correcting the year is a person's (docket_corrections.json),
    so until then the row is left as it was, unread, rather than drawn on a
    day the House did not sit."""
    try:
        mo, dy, yr = (int(x) for x in str(when or "").split("/"))
        year = int(str(r.get("session") or session)[:4])
    except (TypeError, ValueError):
        return True
    if in_term(yr, mo, dy, year):
        return True
    return bool(CORRECTIONS) and corrected_date(r, bill)[0] is not None

PATTERNS = [
    ("introduced", re.compile(
        r"Introduced\s+(?:\(in recess of\)\s*)?(?P<date>\d{1,2}/\d{1,2}/\d{4})"
        r"\s+and\s+[Rr]eferred to\s+(?P<committee>.+?)$", re.I)),
    ("vacated", re.compile(
        r"Vacated and Referred to\s+(?P<committee>.+?)\s*(?:\(|:)", re.I)),
    ("nongermane_hearing", NONGERMANE_HEARING_HOUSE),
    ("nongermane_hearing", NONGERMANE_HEARING_SENATE),
    ("nongermane_hearing", NONGERMANE_HEARING_WITH_BILL),
    ("hearing", re.compile(
        r"(?P<kind>Public Hearing|Hearing)\s*:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})"
        # "Room Map Room, SL" -- the room name can be words, not a number,
        # and [\w-]+ cannot cross the space. 41 Senate hearings fell out of the
        # narrative on that alone.
        r"(?:[, ]+(?:Room\s+(?P<room>[\w][\w .\-]*?),\s*(?P<bldg>\w+),)?)?"
        r"\s*(?P<time>\d{1,2}:\d{2}\s*[ap]m)?\s*(?P<venue>[A-Za-z0-9 .-]*)$", re.I)),
    ("exec", re.compile(
        r"Executive Session\s*:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)),
    ("worksession", re.compile(
        r"(?P<kind>(?:Subcommittee|Full Committee)?\s*Work Session)\s*:\s*"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)),
    # "Committee Report: Ought to Pass with Amendment # 2026-0797h (NT)
    # 02/18/2026 (Vote 9-8; RC)", and sixteen other punctuations of the same
    # six facts. Anchored at the start, because "Conference Committee Report"
    # is a different body -- the committee of conference, sitting for both
    # chambers -- and the unanchored pattern read fourteen of its lines as the
    # policy committee's own recommendation. The side is matched loosely --
    # Major\w*, not Majority -- because the clerk typed "Majoritiy
    # Committee Report" on HB749, and an exact spelling drops that report.
    #
    # The recommendation ends at the first thing that is not part of it: an
    # amendment number, a date, a vote, or a separator. Taking [^,(;#]+ instead
    # ended it at a comma that is often not there, so the date came away inside
    # it on 1,511 of 4,398 lines -- "Ought to Pass 05/06/2025" -- which turned
    # nine recommendations into 273 and put a raw docket date into a published
    # sentence. What follows the recommendation is picked apart by
    # report_fields(), because those facts appear in any order.
    ("report", re.compile(
        r"^\s*(?:(?P<side>Major\w*|Minor\w*)\s+)?Committee\s+Report\s*:\s*"
        r"(?P<rec>.*?)"
        r"(?=\s*(?:#|\d{1,2}/\d{1,2}/\d{4}|[,;(]|\bVote\b|$))"
        r"(?P<rest>.*)$", re.I)),
    ("conf_report", CONF_REPORT_RE),
    ("senate_rule_kill", SENATE_RULE_KILL_RE),
    ("veto_override", VETO_HOUSE_RE),
    ("veto_override", VETO_SENATE_RE),
    ("unsigned_law", UNSIGNED_RE),
    ("unsigned_law", ENACTED_RE),
    # Floor action. The House writes "Ought to Pass: MA VV 03/06/2025"; the
    # Senate writes "Ought to Pass: MA, VV; OT3rdg; 03/06/2025". Same event,
    # different punctuation, and the separator may also be a comma rather than
    # a colon: "Inexpedient to Legislate, MA, VV = =; 03/06/2025".
    ("floor", re.compile(
        r"^(?P<action>.+?)\s*[:,]\s*(?P<motion>MA|MF|ML)\b[,;\s]*"
        r"(?P<vote>VV|DV|RC)?\s*=?\s*=?[,;\s]*"
        r"(?:(?P<y>\d+)\s*-\s*(?P<n>\d+))?[,;\s]*"
        r"(?:OT\drdg)?[,;\s]*"
        # A bill can be sent straight on to Finance under House Rule 4-5 in the
        # same motion that passes it. That clause sits between the vote and the
        # date and was stopping the whole line from parsing.
        # THE NAME RUNS TO THE RULE, the bracket or the separator after it
        # (3 October 2026). "[A-Z][A-Za-z ]+?" with nothing after it required
        # stopped at two letters wherever the clause skipped below could take
        # the rest: "Refer to Finance Rule 4-5; 03/06/2025" (HB 71 of 2025)
        # read "Fi", and 966 histories said "sent it on to the Fi committee".
        r"(?:Refer(?:red)?\s+to\s+(?P<refer>[A-Z][A-Za-z ]*?[A-Za-z])"
        r"(?=\s*(?:\[|\(|Rule\b|[,;]|\d|$))"
        r"(?:\s+Rule\s*[\d\-]+)?[,;\s]*)?"
        # WHAT THE CHAMBER SAID ABOUT ITS OWN VOTE, between the tally and the
        # date: "Lacking Necessary Two-Thirds Vote", "by necessary two-thirds
        # vote", "(In recess of)". 2,024 floor lines across the archive and
        # the current term ended at this clause and were never read as votes
        # at all -- including every constitutional amendment that failed for
        # want of three fifths, which then had no outcome but a minority
        # report's words.
        r"(?:[A-Za-z(][^;]{0,70}?)?[,;\s]*"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)),
    ("amendment", AMEND_RE),
    ("enrolled", ENROLLED_RE),
    ("consent_off", CONSENT_OFF_RE),
    ("conference_meeting", CONF_MEET_RE),
    ("interim_report", INTERIM_REPORT_RE),
    ("retained", RETAINED_RE),
    ("died", DIED_RE),
    ("rereferred", REREF_RE),
    ("governor", re.compile(
        # The clerk writes it both with and without the article: "Signed by
        # Governor Ayotte 7/10/2026" 400 times and "Signed by the Governor on
        # 7/10/2026" 233 times. Only the first was recognised, so a third of
        # the signatures on the record arrived as unclassified text.
        r"(?P<what>Signed by (?:the )?Governor|Vetoed by (?:the )?Governor"
        r"|Sent to (?:the )?Governor)"
        # And then the governor's SURNAME, or the word "on", before the date:
        # "Signed by Governor Ayotte 06/27/2025" and "Signed by the Governor
        # on 02/27/2025". Neither was allowed for, so the date matched empty
        # on all 1,254 signed lines and 49 of the 69 vetoes, and every bill
        # that became law read "The governor signed it on ." The chapter and
        # the effective date came through, which is why it looked like a
        # sentence with a gap in it rather than a pattern that had failed.
        r"(?:\s+(?:on|[A-Z][A-Za-z.'\u2019\-]+)){0,2}"
        r"[,;]?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?"
        r"(?:.*?Chapter\s*(?P<chapter>\d+))?"
        r"(?:.*?Effective\s*(?P<eff>\d{1,2}/\d{1,2}/\d{4}))?", re.I)),
    # Last: nothing above reads these two, which were "other" until now.
    ("withdrawn", WITHDRAWN_ROW),
    ("proposed", PROPOSED_ROW),
]


# --- the rest of a committee report line ------------------------------------
#
# The clerk punctuates the same six facts a dozen ways -- "; Vote 5-0; CC",
# "(Vote 9-8; RC)", ", 01/30/2025, Vote 3-2" -- so each is found by its own
# marker rather than by where it sits. Anything the line does not carry is
# simply absent: a minority report has no vote of its own, and 706 of them
# say so by omission.
R_AMEND = re.compile(r"#\s*(?P<amend>(?:\d{4}-)?\d+[a-z]*)", re.I)
# The date the committee signed its report, which is not the date the docket
# row was created and is usually days earlier.
R_RDATE = re.compile(r"(?P<date>\d{1,2}/\d{1,2}/\d{4})")
R_RVOTE = re.compile(r"\bVote\s+(?P<y>\d+)\s*-\s*(?P<n>\d+)", re.I)
# A new title travels with the amendment and changes what the bill is called,
# which is why two reports on one bill can carry two different titles.
R_NT = re.compile(r"\(NT\)", re.I)


def report_side(raw):
    """Majority, Minority or neither, however the clerk spelled it."""
    w = (raw or "").lower()
    return ("Majority" if w.startswith("major")
            else "Minority" if w.startswith("minor") else "")


def report_fields(rest):
    """Amendment, date and vote off the tail of a committee report line."""
    out = {}
    for pat in (R_AMEND, R_RDATE, R_RVOTE):
        m = pat.search(rest or "")
        if m:
            out.update({k: v for k, v in m.groupdict().items() if v})
    if R_NT.search(rest or ""):
        out["new_title"] = "1"
    return out


# --- the volume and page the clerk cited ------------------------------------
#
# Two thirds of the docket ends with one: "HJ 7", "SC 4", "HC 10  P. 4". It is
# the published record of that single action -- the page of the journal where
# the vote is printed, the calendar the report appeared in -- and it is the
# strongest citation this site can offer for anything.
#
# clean() deletes it before any pattern below sees the line, and has to: every
# pattern here was written against a line that ends at the date, and the
# hearing pattern's venue group would otherwise swallow "SC 4" and file 132
# hearings in a room of that name. So it is taken off the raw line first and
# carried on the event instead of being thrown away.
#
# It was being thrown away. 17,290 of 25,270 docket rows carry a citation and
# 12,970 of those name a volume already on disk, yet _cite() in build_site_v2,
# which exists to turn exactly this into a link, was reading the cleaned line
# and finding nothing on every event of every bill.
CITE_RE = re.compile(r"\b(?P<vol>HJ|SJ|HC|SC)\s*(?P<num>\d+[A-Za-z]?)"
                     r"(?:\s*P\.?\s*(?P<page>\d+))?", re.I)


def cite_of(desc):
    """The journal or calendar a docket line cites, as ("HC 10", "4")."""
    m = CITE_RE.search(desc or "")
    if not m:
        return "", ""
    return (f"{m.group('vol').upper()} {m.group('num')}", m.group("page") or "")


def classify(desc):
    c = clean(desc)
    for name, pat in PATTERNS:
        m = pat.search(c)
        if m:
            d = m.groupdict()
            if name == "report":
                d.update(report_fields(d.pop("rest", "")))
            if name == "conf_report":
                # The vote kind and count, in either chamber's order, the way
                # amendment_outcome reads them off an amendment row.
                vk = AMEND_VOTE.search(c, m.end("num"))
                tally = AMEND_TALLY.search(c, vk.end()) if vk else None
                d["vote"] = ({"RC": "RC", "VV": "VV"}.get(vk.group(1).upper(), "DV")
                             if vk else None)
                d["y"], d["n"] = (tally.group(1), tally.group(2)) if tally else (None, None)
                d["motion"] = "MA" if d["outcome"].lower() == "adopted" else "MF"
            if name == "nongermane_hearing":
                # The Senate's row states its day as a hearing notice does,
                # and stated_day reads it; where the year is two digits
                # ("Hearing: 4/10/13, Room 102, LOB, ..."), or the row is a
                # joint hearing's ("Joint Hearing with the House Education
                # Funding Committee: 10/14/2025, ..."), which it does not
                # read, the day is the row's here, as the era reader gave it.
                said = d.pop("sdate", None)
                if said and not d.get("date"):
                    mo, dy, yr = said.split("/")
                    if len(yr) == 2 or d.get("joint"):
                        yr = yr if len(yr) == 4 else f"{'20' if int(yr) < 50 else '19'}{yr}"
                        d["date"] = f"{int(mo):02d}/{int(dy):02d}/{yr}"
            if name == "amendment":
                # "FLAM # 2026-1971h(NT) (Rep. Pauer): AA RC 171-162" is the
                # House's floor amendment, and who offered it is in brackets.
                by = (d.pop("by", None) or "").strip()
                if (d.get("what") or "").upper() == "FLAM":
                    d["what"] = "Floor Amendment"
                    if by and not d.get("mover"):
                        d["mover"] = re.sub(r",\s*(?=[^,]+$)", " and ", by)
            d["_type"] = name
            d["_raw"] = c
            return d
    return {"_type": "other", "_raw": c}


# A term as this project writes one: "2025-2026". narratives.json is keyed on
# it because bill numbers repeat every biennium, and the old flat {bill: record}
# shape merges HB396 of 2023 with HB396 of 2025 the moment a past session is
# read in.
TERM_RE = re.compile(r"^\d{4}-\d{4}$")


def is_term_keyed(data):
    """Is this narratives.json the {term: {bill: record}} shape?"""
    return bool(data) and all(TERM_RE.match(k) for k in data)


def load_narratives(path, term=None):
    """narratives.json as {bill: record}, for one term.

    The default term is the most recent the file holds, which is what every
    tool working on the current session wants. Reading the old flat shape with
    a term lookup returns nothing for every bill without failing, so it is
    refused rather than read.
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if not data:
        return {}
    if not is_term_keyed(data):
        sys.exit(f"{path} is keyed on bill number, not on term. Rebuild it: "
                 f"python3 src/parse/narrative.py --docket Docket.txt --all --out {path}")
    return data.get(term or max(data), {})


def parse_docket(path, want_bill=None, want_session=None, lsrs=None):
    """{bill: [row]} -- the docket's rows, grouped by the bill-number field.

    With `lsrs` ({term: {bill: (LSR year, LSR number)}}, load_lsrs()), each
    bill's rows are its OWN rows: own_rows() says which those are and why.
    Without it every row stays under the number it was filed under, which is
    what a checkout with no data/bills.json gets.
    """
    bills = defaultdict(list)
    # ONE MEASURE UNDER BOTH YEARS OF ITS TERM IS STILL ONE DOCKET. The
    # database holds HBI 5 of 1993 under session 1993 and again under 1994,
    # with one LSR, and the dump gives its eight rows twice, word for word and
    # stamp for stamp. Read as sixteen, its history said it "crossed to the
    # House" on the day the House introduced it -- the second copy of the
    # introduction row -- and every line of its docket was printed twice. A
    # row repeated under another session year of the same number and LSR is
    # entered once, as the past docket view's repeats are (past_docket_rows).
    # It is the one measure of the nineteen dockets entered that way.
    entered = {}
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 7:
                continue
            bill = p[3].strip()
            # Asked for one bill, the whole file is still read when the rows
            # are chosen by LSR: a row of that bill's can be filed under
            # another key, and the rows are chosen before the one is kept.
            if want_bill and not lsrs and bill.upper() != want_bill.upper():
                continue
            again = (bill, p[1].strip(), p[2].strip(), p[4].strip(), p[5])
            if entered.setdefault(again, p[0].strip()) != p[0].strip():
                continue
            try:
                created = datetime.strptime(p[2].strip(), "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                created = datetime.min
            bills[bill].append({
                "lsr": f"{p[0]}-{p[1]}", "session": p[0].strip(),
                # "s" is "S": 65 rows of 1999-2002 give the chamber in lower
                # case, and SB 182 of 1999's Senate committee report, its
                # chamber "s", was told in a stage headed with no chamber and
                # named on the Reports tab for the House's committee.
                "body": p[4].strip().upper(),
                "desc": p[5], "created": created,
                "flags": re.findall(r"==\s*([A-Z][A-Z ]*?)\s*==", p[5]),
            })
    if lsrs:
        bills, taken, moved = own_rows(bills, lsrs)
        LSR_REPORT.update(taken=taken, moved=moved)
        if want_bill:
            bills = {b: r for b, r in bills.items()
                     if b.upper() == want_bill.upper()}
    return bills


# WHOSE ROW IS IT. The docket files every row under a bill-number field the
# clerk typed, and grouping on that field alone put another measure's events
# into 43 archived histories and filed 59 bills' own rows under keys no bill
# carries. Each row also carries its LSR, the drafting request it was filed
# against, and data/bills.json records each bill's own. So a bill's rows are
# the ones carrying its LSR -- the rule referrals._own_rows reads committees
# by, so a page's committee row and the history under it come from the same
# rows. Three shapes, every one of them in the database's dockets of
# 1989-2014 and none in 2015-2026:
#
#   A NUMBER USED TWICE IN ONE TERM. A resolution can be numbered again in
#   the term's second year. SCR 2 of 1990 is the Fast Day resolution, LSR
#   2730, which the Senate killed; the docket files the 1989 recycling
#   resolution, LSR 0564, under the same SCR2, and its history said the House
#   had passed it on 13 April 1989. That LSR is left out of SCR 2's history.
#   The earlier measure has no record of its own to go to (data/bills.json
#   holds one bill per number per term), so its rows go nowhere.
#
#   A ROW WHOSE LSR IS ANOTHER BILL'S. SB 98 of 2011 carries "Introduced and
#   Referred to Transportation", LSR 2011-0961, which is SB 99's: its history
#   said it "crossed to the Senate on January 19, 2011", which is SB 99's
#   introduction. Left out of SB 98's -- and NOT put on SB 99's. The LSR may
#   be the mistake rather than the number, so moving a row onto the bill it
#   names corrects the General Court's own record, which is a person's
#   decision; until one is made the row is in neither history. 27 rows of
#   1999-2014 are this shape.
#
#   A ROW UNDER A KEY NO BILL CARRIES: a blank number, "1101" for HB 1101,
#   "SB420-FN", "SB21`", "HCR 9", "HB500" (LSR 0500's number typed for the
#   bill's). Given to the one bill whose LSR, year and number both, it
#   carries. HB 1101 of 2000 had a history with no introduction. A key that
#   names no bill and whose LSR names none either is a real bill with no
#   record, and its rows stay where they are.
#
# MATCHED ON THE NUMBER WITHIN A BILL, as _own_rows matches. HCR 15, CACR 13
# and HR 11 of 1991-1992 and HBI 5 of 1993-1994 carry one LSR across both
# years of the term, and a match on the year as well would have cut each one's
# history in half.
#
# AND ONE MEASURE ENTERED TWICE IS STILL ONE MEASURE. On 1 December 2010 the
# Senate's SR 2 to SR 5 were each entered under two LSRs the same day, the
# second never given a status: SR 3's select committee report -- the return of
# votes found correct -- is on LSR 2011-2003 and nowhere else. A second LSR
# that no bill carries, whose rows begin the same day as the bill's own, is
# that, and its rows stay. Every LSR a bill's number was reused for began on
# another day; most in another year.
#
# THE KEYS WHOSE LSR IS THE MISTAKE, whose rows stay under the number they
# were filed under, as they always have, rather than go to the bill the LSR
# names. Each is a row the key, not the LSR, describes:
#
#   1989-1990's "SSHB1" carries LSR 1990-2755, which is SR 8's -- "requesting
#   the teaching of the founding of the state" -- and its two rows are the
#   House's special-session votes on HB 1 of 14 December 1989. HB 1's own
#   row carries the count too, but its history reads the day as voice votes,
#   so these are the only place the 217-147 roll call reaches the sitting's
#   page: dropping them took it off.
#   1995-1996's "HB 0306" carries LSR 1996-2936, HB 1637's, on four Judiciary
#   work sessions entered on 24 July 1995. HB 1637 is the welfare bill,
#   introduced on 5 March 1996 and sent to Health; HB 306 was re-referred to
#   Judiciary, and its own row six minutes later covers the same dates.
#   1997-1998's "H  0718" carries LSR 1997-0938, CACR 22's, on a copy to the
#   chairman due 5 March 1997: HB 718's due date, not CACR 22's.
#
# All three are for the Clerk's list.
NOT_MOVED = {("1989-1990", "SSHB1", "2755"), ("1995-1996", "HB 0306", "2936"),
             ("1997-1998", "H  0718", "938")}
LSR_REPORT = {"taken": [], "moved": []}


def _lsr_num(s):
    return str(s or "").strip().lstrip("0")


_BILLS_READ = {}


def _bills_doc(path):
    """data/bills.json as {term: {bill: record}}, or {} where it is not there
    or is not keyed by term. Read once for a path: load_lsrs and
    load_introductions both ask, and the file is 25 MB."""
    key = str(path or "")
    if key not in _BILLS_READ:
        p = Path(path) if path else None
        data = {}
        if p and p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                data = {}
        _BILLS_READ[key] = data if is_term_keyed(data) else {}
    return _BILLS_READ[key]


def load_lsrs(path):
    """{term: {bill: (LSR year, LSR number)}} from data/bills.json, or {}."""
    return {t: {b: (str(r.get("lsr_year") or "").strip(), _lsr_num(r.get("lsr_num")))
                for b, r in byb.items() if isinstance(r, dict)}
            for t, byb in _bills_doc(path).items()}


# WHAT THE HOUSE JOURNAL SAYS OF A BILL'S INTRODUCTION, where build_data's
# record carries a reading (its INTRODUCTION_FROM_JOURNAL: six of the
# measures it adds from the General Court's database, and four bills of 2017
# the bill search's own list carries). The House introduces
# its bills by a resolution that names them by number, and the docket's
# introduction row is typed ahead of the day: HB 87 of 2009 carries
# "Introduced 1/7/2009 and Referred to Municipal and County Government" and
# the resolution of that day steps over 87. {(term, bill): {"introduced",
# "date", "journal", "numbered"}}; empty unless --bills names a file whose
# records carry "introduction", so a run without one tells every docket as
# it did before. build() says what each answer changes.
INTRODUCTIONS = {}


def load_introductions(path):
    """INTRODUCTIONS from data/bills.json, or {} where it is not there."""
    return {(t, b): r["introduction"] for t, byb in _bills_doc(path).items()
            for b, r in byb.items()
            if isinstance(r, dict) and isinstance(r.get("introduction"), dict)}


def own_rows(bills, lsrs):
    """(bills, taken, moved): each bill's own rows, by LSR. See NOT_MOVED.

    `taken` is [(term, bill, row, {bills its LSR is})] for every row left out
    of the history it was filed under, `moved` [(term, key, bill, row)] for
    every row given to the bill its LSR is. A bill whose record names no LSR,
    or one no row of it carries, keeps every row, and so does a row that
    carries no LSR itself: there is nothing to tell them apart by.
    """
    owner = defaultdict(set)
    for term, recs in lsrs.items():
        for b, (y, n) in recs.items():
            if n:
                owner[(term, y, n)].add(b)
    num = lambda r: _lsr_num(r["lsr"].partition("-")[2])
    # The keys in the docket's order, so that a term nothing moves in is
    # written exactly as it was.
    out = {k: [] for k in bills}
    taken, moved = [], []
    for key, rows in bills.items():
        by_term = defaultdict(list)
        for r in rows:
            by_term[P.term_of(r["session"])].append(r)
        for term, rs in by_term.items():
            rec = lsrs.get(term, {}).get(key)
            if rec:
                own = rec[1]
                if not own or all(num(r) != own for r in rs):
                    out[key] += rs
                    continue
                began = defaultdict(lambda: datetime.max)
                for r in rs:
                    began[num(r)] = min(began[num(r)], r["created"])
                for r in rs:
                    n = num(r)
                    whose = owner.get((term, r["session"], n), set())
                    if n == own or not n or (not whose and
                                             began[n].date() == began[own].date()):
                        out[key].append(r)
                    else:
                        taken.append((term, key, r, whose))
                continue
            for r in rs:
                n = num(r)
                whose = owner.get((term, r["session"], n), set())
                if len(whose) != 1 or (term, key, n) in NOT_MOVED:
                    out[key].append(r)
                else:
                    dest = next(iter(whose))
                    out.setdefault(dest, []).append(r)
                    moved.append((term, key, dest, r))
    return {k: v for k, v in out.items() if v}, taken, moved


def report_lsrs(taken, moved, source):
    """Say what own_rows did to this run. Printed with a marker narrate_archive
    passes on, because a rule that quietly stopped working looks exactly like
    a docket with no misfiled row."""
    if source is None:
        print("  rows by LSR: no bill list, so every row stays under the number "
              "it was filed under")
        return
    hosts = {(t, b) for t, b, _r, _w in taken}
    gained = {(t, b) for t, _k, b, _r in moved}
    keys = {(t, k) for t, k, _b, _r in moved}
    print(f"  rows by LSR ({source}): {len(taken):,} row(s) left out of "
          f"{len(hosts):,} histor{'y' if len(hosts) == 1 else 'ies'} as another "
          f"measure's; {len(moved):,} given to the {len(gained):,} bill(s) "
          f"whose LSR they carry, from {len(keys):,} key(s) no bill carries")


# THE DOCKET OF A BILL THE TERM'S OWN FILE HAS NO ROW FOR (1 October 2026).
# A term's docket file is the database's dump for 1989-2014 and, from 2015,
# the pages fetched bill by bill off the list the General Court's search gave
# -- so a bill that list left out has no row in it. SB 499 of 2016 and the
# House's six organizing resolutions of December 2016 are in no docket file;
# nor are SB 340 of 2016 and HB 451 of 2019, which have records and had no
# history; nor HB 459 of 2021, whose record is the House Journal's. The
# General Court's past docket view (fetch_past_db.py's PastDocket.psv) holds
# every one of them, in the same words the docket pages print.
#
# ONLY A BILL WITH NO ROW AT ALL. A bill the term's file has any row for
# keeps that file's and takes nothing from here: the two are one record, and
# one bill told from both would be told twice.
#
# BY THE BILL'S OWN LSR, as own_rows chooses rows, AND UNDER ITS OWN NUMBER:
# a row that carries the bill's LSR under another bill's number is one of
# the rows own_rows leaves in neither history, and stays in neither. For a
# record that names no LSR -- a journal record does not -- by its number,
# where every row the view files under that number in the term carries one
# LSR.
#
# THE VIEW REPEATS ROWS: each of HR 69 of 1992's three is in it twice, under
# two ids. A row repeated word for word at the same minute is entered once.
def past_docket_rows(path, bills, lsrs):
    """{bill: [row]} in parse_docket's shape, from the past docket view, for
    the bills of this docket's term that `bills` (its rows by bill) has none
    for. {} where the view or its manifest is not there."""
    p = Path(path)
    man = p.with_name("_manifest.json")
    if not (p.exists() and man.exists()):
        return {}
    try:
        cols = json.loads(man.read_text(encoding="utf-8"))["PastDocket"]["columns"]
        at = {c: cols.index(c) for c in ("SessionYear", "LSR", "StatusDate",
                                         "CondensedBillNo", "LegislativeBody",
                                         "Description", "statusorder")}
    except (ValueError, KeyError):
        return {}
    terms = {P.term_of(rows[0].get("session", "")) for rows in bills.values() if rows}
    have = {b.upper() for b in bills}
    by_lsr, by_number = {}, {}
    for term in terms:
        for b, (y, n) in (lsrs.get(term) or {}).items():
            if b.upper() in have:
                continue
            if n:
                by_lsr[(y, n)] = b
            else:
                by_number[(term, b.upper())] = b
    if not (by_lsr or by_number):
        return {}
    years = {y for t in terms for y in t.split("-")}
    got, seen = defaultdict(list), set()
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[:4] not in years:
                continue
            f = line.rstrip("\r\n").split("|")
            if len(f) != len(cols):
                continue
            year, lsr = f[at["SessionYear"]].strip(), f[at["LSR"]].strip()
            number = re.sub(r"\s+", "", f[at["CondensedBillNo"]]).upper()
            bill = by_lsr.get((year, _lsr_num(lsr))) or \
                by_number.get((P.term_of(year), number))
            if not bill:
                continue
            # UNDER ITS OWN NUMBER, where the row carries one. The view files
            # "Introduction, Sen. Trombly - Ought to pass; MA, VV" of 23 March
            # 1999 under SR1 with LSR 1999-1020, which is SR 5's: own_rows
            # leaves that row out of SR 1's history and does not give it to
            # SR 5, because which of the two is mistyped is a person's to say.
            # This must not give it to SR 5 by another door.
            if number and number != bill.upper():
                continue
            body, desc = f[at["LegislativeBody"]].strip(), f[at["Description"]]
            stamp = f[at["StatusDate"]].strip()
            if (bill, year, lsr, stamp, body, desc) in seen:
                continue
            seen.add((bill, year, lsr, stamp, body, desc))
            try:
                created = datetime.strptime(stamp, "%m/%d/%Y %H:%M:%S")
            except ValueError:
                created = datetime.min
            try:
                order = int(f[at["statusorder"]] or 0)
            except ValueError:
                order = 0
            got[bill].append((created, order, len(got[bill]), {
                "lsr": f"{year}-{lsr}", "session": year, "body": body,
                "desc": desc, "created": created,
                "flags": re.findall(r"==\s*([A-Z][A-Z ]*?)\s*==", desc)}))
    out = {}
    numbered = set(by_number.values())
    for bill, rows in got.items():
        if bill in numbered and len({r[3]["lsr"] for r in rows}) > 1:
            # Two measures under one number, and no LSR to tell them apart.
            continue
        out[bill] = [r[3] for r in sorted(rows, key=lambda x: x[:3])]
    return out


def event_date(ev, fallback):
    d = ev.get("date")
    if d:
        try:
            return datetime.strptime(d, "%m/%d/%Y")
        except ValueError:
            pass
    return fallback


# --------------------------------------------------------------- narrative

# A bill's history has natural stages, and running them together as one long
# paragraph loses the shape that makes it readable. These are the hands the
# bill passes through: a House committee, then the whole House, then the same
# again in the Senate, then a conference and the governor.
CHAMBER = {"H": "House", "S": "Senate"}
COMMITTEE_TYPES = {"hearing", "exec", "report", "retained", "consent_off",
                   "subcommittee", "interim_report"}
FLOOR_TYPES = {"floor", "tabled", "reconsider", "ot3rdg", "nonconcur",
               "concur", "veto_override"}


# "The committee held a work session on September 9. The committee held a work
# session on November 5. The committee held a work session on November 12."
# Three sentences saying one thing. Fold repeats of the same shape into a single
# sentence with the dates listed.
# Enrolment and the amendment made during it are one step: the text is checked
# before it goes to the governor, and anything found wrong is corrected then.
# Told as two sentences it read as two separate events on the same day, with
# the correction announced before the check that produced it.
ENROLLED_AMD = re.compile(
    r"^An enrolled bill amendment \((?P<num>[^)]+)\) was (?P<what>adopted|considered)"
    r"(?P<how> on a [\w ]+)?(?P<when> on \w+ \d{1,2}, \d{4})?\. "
    r"These correct technical errors found after passage\.$")
ENROLLED = re.compile(
    r"^The bill was enrolled(?P<when> on \w+ \d{1,2}, \d{4})? \u2014 the final "
    r"check of the text before it goes to the governor\.$")

DIVIDED = (
    re.compile(r"^The majority of the committee recommended that the (\w+) (.+?)"
               r"((?:,| by a vote).*)?\.$"),
    re.compile(r"^The minority of the committee recommended that the \w+ (.+?)"
               r"((?:,| by a vote).*)?\.$"),
)

# A run of floor amendments taken on one day. HB2, the budget trailer bill,
# had 26 of them on 10 April 2025 -- 2,600 characters of one sentence written
# 26 times, differing only in a number. Folded, every number and every tally
# is still there and the paragraph can be read.
#
# Deliberately does NOT match a sentence naming who offered the amendment:
# that is a fact worth its own sentence, and a run carrying one stays as it
# is.
#
# A withdrawn one is part of the day's run. It was folded in as "rejected"
# until the rows were read for what they say, and once it read "withdrawn"
# it broke the run: HB 1 of 2011 "took up 13 floor amendments" on 31 March,
# then told 1306h, 1321h and 1322h one sentence each, where the House took
# up sixteen.
FLOOR_AMD = re.compile(
    r"^A floor amendment \((?P<num>[^)]+)\)"
    r"(?:, offered by (?P<by>[^,]+),)? was (?P<what>adopted|rejected|withdrawn)"
    r"(?P<how> on a [a-z ]+?)?(?P<tally> \d+\u2013\d+)?"
    r"(?P<when> on \w+ \d{1,2}, \d{4})?"
    r"(?:, changing the text of the bill)?\.$")

# The remainder of a floor amendment voted on in parts, as describe() words
# the 1999-2006 reader's "part": "rest".
REST_OF_AMD = re.compile(
    r"^The rest of the floor amendment \([^)]+\).*? was (?:adopted|rejected)"
    r"[^.]*?(?P<when> on \w+ \d{1,2}, \d{4})?(?:, changing the text of the bill)?\.$")

REPEATABLE = [
    (re.compile(r"^The committee held a work session on (.+)\.$"),
     "The committee held work sessions on {dates}."),
    # Date-shaped rather than (.+), because a hearing sentence now carries the
    # sign-in counts after the date and (.+) folded those into the date list.
    (re.compile(r"^The committee held a public hearing on "
                r"(\w+ \d{1,2}, \d{4})\.$"),
     "The committee held public hearings on {dates}."),
    (re.compile(r"^The committee met in executive session on (.+?)( to .+)?\.$"),
     "The committee met in executive session on {dates}."),
    (re.compile(r"^A committee of conference met on (.+?) to try to settle "
                r"the differences between the two chambers' versions of the "
                r"bill\.$"),
     "A committee of conference met on {dates} to try to settle the "
     "differences between the two chambers' versions of the bill."),
]


def and_list(items):
    items = list(dict.fromkeys(items))
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def fold_amendments(run, chamber, other=False):
    """One sentence for a day's floor amendments, keeping every number.

    other: the sentence before the run told a floor amendment the chamber
    voted on in parts that day, so these are the day's other ones."""
    def cite(m):
        num = m.group("num")
        # Who offered it is kept: it is the one fact in these sentences that
        # is not repetition, and folding thirteen of them into a count would
        # lose thirteen different names.
        inner = [x for x in (m.group("by"), (m.group("tally") or "").strip())
                 if x]
        if not inner:
            how = (m.group("how") or "").strip()
            if how.startswith("on a "):
                inner = [how[5:]]
        return f"{num} ({', '.join(inner)})" if inner else num

    ok = [m for m in run if m.group("what") == "adopted"]
    no = [m for m in run if m.group("what") == "rejected"]
    wd = [m for m in run if m.group("what") == "withdrawn"]
    when = next((m.group("when") for m in run if m.group("when")), "")
    n = f"{len(run)} other" if other else f"{len(run)}"
    lead = (f"On {when[4:]} the {chamber} took up {n} floor amendments"
            if when else f"The {chamber} took up {n} floor amendments")
    gone = (f" {'Amendment' if len(wd) == 1 else 'Amendments'} "
            + and_list([cite(m) for m in wd])
            + f" {'was' if len(wd) == 1 else 'were'} withdrawn." if wd else "")
    if not ok and not no:
        return (f"{lead}, and all of them were withdrawn: "
                + and_list([cite(m) for m in wd]) + ".")
    if not ok:
        return (f"{lead} and rejected {'all of them' if not wd else 'the rest'}: "
                + and_list([cite(m) for m in no]) + "." + gone)
    if not no:
        return (f"{lead} and adopted {'all of them' if not wd else 'the rest'}: "
                + and_list([cite(m) for m in ok]) + "." + gone)
    return (f"{lead}. It adopted " + and_list([cite(m) for m in ok])
            + ", and rejected " + and_list([cite(m) for m in no]) + "." + gone)


def collapse(sentences, chamber="House"):
    """Fold consecutive sentences of the same shape into one.

    Also drops exact repeats. Enrolling is recorded once by each chamber, so
    the docket carries two rows with the same date and the same wording, and
    HB 396 read "An enrolled bill amendment (2026-2155e) was adopted... An
    enrolled bill amendment (2026-2155e) was adopted..." Two identical
    sentences describing one dated action are one action written twice, never
    two things that happened.
    """
    # EXACT REPEATS GO FIRST. Enrolment is recorded once by each chamber, so
    # the docket carries two identical amendment rows and two identical
    # enrolment rows -- and the merge below consumed the second amendment with
    # the first enrolment before the de-duplicator further down ever saw
    # either. HB2 said it three times: the amendment, then the merged
    # sentence, then the enrolment again.
    #
    # Two identical sentences describing one dated action are one action
    # written twice, never two things that happened.
    sentences = list(dict.fromkeys(x.strip() for x in sentences if x.strip()))
    out, i = [], 0
    seen = set()
    while i < len(sentences):
        # A day's floor amendments, folded. Four is the threshold: three
        # sentences read as a list of three things, and twenty-six do not.
        run, j = [], i
        while j < len(sentences):
            m = FLOOR_AMD.match(sentences[j].strip())
            if not m or (run and m.group("when") != run[0].group("when")):
                break
            run.append(m)
            j += 1
        if len(run) >= 4:
            # "took up 5 floor amendments and rejected all of them", straight
            # after the sentence that says the rest of a sixth was adopted
            # that day (HB 999 of 1999), counts one too few and reads as a
            # contradiction: these are the day's other ones.
            m = REST_OF_AMD.match(out[-1].strip()) if out else None
            out.append(fold_amendments(
                run, chamber,
                other=bool(m and m.group("when") == run[0].group("when"))))
            i = j
            continue
        # Enrolment and its amendment, in either order.
        #
        # The flag is not tidiness. This used to decide whether a merge had
        # happened by inspecting the last sentence written -- and once a merged
        # enrolment sentence was there, EVERY later iteration saw it, took the
        # continue, and never advanced i. Any bill with an enrolled bill
        # amendment followed by anything at all -- a veto, an override, a
        # chapter number -- put the build in an infinite loop.
        merged = False
        if i + 1 < len(sentences):
            for first, second in ((ENROLLED_AMD, ENROLLED), (ENROLLED, ENROLLED_AMD)):
                x = first.match(sentences[i].strip())
                y = second.match(sentences[i + 1].strip())
                if x and y:
                    amd = x if first is ENROLLED_AMD else y
                    enr = y if first is ENROLLED_AMD else x
                    when = (enr.group("when") or amd.group("when") or "")
                    out.append(
                        f"The bill was enrolled{when} \u2014 the final check of "
                        "the text before it goes to the governor \u2014 and an "
                        f"enrolled bill amendment ({amd.group('num')}) was "
                        f"{amd.group('what')}{amd.group('how') or ''} to correct "
                        "technical errors found after passage.")
                    i += 2
                    merged = True
                    break
            if merged:
                continue

        # ENROLMENT IS ONE STEP, NOT TWO. Each chamber records its own
        # enrolment row, so a bill that passed both reads "The bill was
        # enrolled on May 30, 2012 ... The bill was enrolled on June 5,
        # 2012", which is the same check announced twice. The later date is
        # when it was finished, and the explanation is written once.
        if i + 1 < len(sentences):
            a = ENROLLED.match(sentences[i].strip())
            b = ENROLLED.match(sentences[i + 1].strip())
            if a and b:
                when = b.group("when") or a.group("when") or ""
                out.append(f"The bill was enrolled{when} — the final "
                           "check of the text before it goes to the governor.")
                i += 2
                continue

        # A divided committee: majority and minority are one decision.
        if i + 1 < len(sentences):
            a = DIVIDED[0].match(sentences[i].strip())
            b = DIVIDED[1].match(sentences[i + 1].strip())
            if a and b:
                tail = (a.group(3) or "").strip().lstrip(",").strip()
                chamber = a.group(1)
                # The committee's own vote, where the line carries it, said
                # with the recommendation it belongs to rather than trailed
                # after the calendar it was printed on.
                vote = ""
                vm = re.search(r"by a vote of\s*(\d+\s*[-\u2013]\s*\d+)",
                               (a.group(3) or "") + " " + (b.group(2) or ""),
                               re.I)
                if vm:
                    vote = f", by a vote of {vm.group(1).replace(' ', '')}"
                    tail = re.sub(r",?\s*by a vote of\s*\d+\s*[-\u2013]\s*\d+",
                                  "", tail, flags=re.I).strip().lstrip(",").strip()
                # The tail was written to follow a comma, so it opens with
                # "and". Standing on its own it does not need one, and keeping
                # it produces "And the report was placed on the regular
                # calendar."
                tail = re.sub(r"^and\s+", "", tail, flags=re.I).strip()
                # "and the minority RECOMMENDED that" -- the verb repeated,
                # because dropping it makes the second clause read as an
                # afterthought to the first rather than the other half of a
                # split decision. And the calendar is its own sentence: where
                # a report was printed is a different fact from what it said.
                out.append(
                    f"The majority recommended that the {chamber} {a.group(2)}, "
                    f"and the minority recommended that the {chamber} "
                    f"{b.group(1)}{vote}."
                    + (f" {tail[0].upper()}{tail[1:]}." if tail else ""))
                i += 2
                continue
        matched = False
        for pat, tmpl in REPEATABLE:
            m = pat.match(sentences[i].strip())
            if not m:
                continue
            dates = [m.group(1)]
            j = i + 1
            while j < len(sentences):
                m2 = pat.match(sentences[j].strip())
                if not m2:
                    break
                dates.append(m2.group(1))
                j += 1
            if len(dates) > 1:
                out.append(tmpl.format(dates=and_list(dates)))
                i, matched = j, True
            break
        if not matched:
            s = sentences[i]
            if s.strip() not in seen:
                seen.add(s.strip())
                out.append(s)
            i += 1
    return " ".join(out)


def stage_of(ev):
    """Which hand the bill is in for this action."""
    t, body = ev["_type"], ev.get("body") or "H"
    if ev.get("_pre"):
        # Before the bill was ever introduced: it was in no committee and
        # on no floor (build() says which rows these are).
        return (body, "filed")
    if t == "withdrawn" and ev.get("read"):
        # "Read in January 4, 2012 and Withdrawn": read in to the chamber.
        return (body, "floor")
    if t in ("signed", "vetoed", "chaptered", "governor", "enrolled",
             "enrolled_amendment", "unsigned_law"):
        return ("G", "governor")
    if t in ("conf_report", "senate_rule_kill", "died"):
        # Each chamber's own vote on the conferees' report, on its floor, as
        # the 1989-2006 readers tell the same rows; and the Senate's rule that
        # ends a bill still lying on its table.
        #
        # AND A DEATH ON THE TABLE IS THE FLOOR'S (the launch audit of 7
        # October 2026). "Died on Table, Session ended 12/17/2025" (HB 761 of
        # 2025) fell through to the committee below, and 130 histories of
        # 2025-2026 told it under "In House committee", after the floor's
        # tabling it ends. Not in FLOOR_TYPES, which build() also reads for
        # the days a chamber sat.
        return (body, "floor")
    if t in ("conference", "conference_meeting"):
        return ("C", "conference")
    if t == "introduced":
        return (body, "committee")
    if t == "amendment":
        # An amendment's stage is not its type, and the fall-through below put
        # every one of them in committee.
        #
        # A bare House amendment row is a vote ON THE FLOOR -- it carries the
        # floor vote's date and journal page -- but it is not a floor
        # amendment: it is how the House adopts or rejects the amendment its
        # committee's report recommends, "Amendment # 2026-0989h: AA VV" (HB
        # 1449 of 2026, "Majority Amendment (0989h)" in House Journal 7). A
        # member's amendment is a FLAM row (2015 on) or a "Floor Amendment"
        # row (2007-2014). Whose it is, is whose_amendment()'s to say; where
        # it is told is here, and for a bare row that is the floor. This
        # comment once read a bare row as a floor amendment, and 633 House
        # committee amendments of 2025-2026 were told as floor amendments
        # while the 108 FLAM rows were read by nothing.
        #
        # An enrolled bill amendment comes after both chambers have passed the
        # bill and belongs with enrolling, which is already staged with the
        # governor.
        # AND A COMMITTEE'S AMENDMENT IS VOTED ON THE FLOOR TOO (the launch
        # audit of 7 October 2026). "Committee Amendment # 2025-0531s, AA,
        # VV; 03/06/2025" (SB 17 of 2025) is the Senate adopting its
        # committee's amendment, with the bill's passage the next row: Senate
        # Journal 6 prints the vote on the floor. Staged with the committee
        # by its word "Committee", it was told under "In Senate committee", a
        # heading of its own between the floor's, on 484 histories of
        # 2025-2026. Whose it is is the sentence's to say ("The committee's
        # amendment").
        what = (ev.get("what") or "").lower()
        if "enrolled" in what:
            return ("G", "governor")
        return (body, "floor")
    if t in FLOOR_TYPES:
        return (body, "floor")
    if t in COMMITTEE_TYPES:
        return (body, "committee")
    return (body, "committee")


STAGE_LABEL = {
    ("H", "committee"): "In House committee",
    ("H", "floor"): "On the House floor",
    ("S", "committee"): "In Senate committee",
    ("S", "floor"): "On the Senate floor",
    ("C", "conference"): "Committee of conference",
    ("G", "governor"): "With the governor",
    # A bill that was never introduced was never in a committee's hands.
    ("H", "filed"): "Before introduction in the House",
    ("S", "filed"): "Before introduction in the Senate",
}


# {term: {bill: {"hearings": [{"date": ..., "support": ..., ...}]}}}, from
# fetch_testimony_db.py. Empty unless --testimony names a file, so a run
# without it produces exactly the sentences it did before.
TESTIMONY = {}
TERM = ""

# A DATE THE CLERK TYPED WRONG, put right by a person, with the evidence beside
# it. docket_corrections.json is a hand-made file in the family of
# member_corrections.json: no generator writes it, this is its only reader,
# and an entry is applied only while the docket row still says what the entry
# says it says. "Reconsider HB1491 (Rep. N. Germana): MF VV 09/19/2026 HJ 16
# P. 48" was written at 2:27 PM on 19 August, four journal pages after that
# afternoon's veto vote, and it published a House sitting on a Saturday in
# September that never happened.
CORRECTIONS_FILE = "docket_corrections.json"
CORRECTIONS = []
CORRECTED = set()
SIBLINGS = []
# AND A ROW FILED UNDER THE WRONG BILL, from the same file's "misfiled" list.
# HB 1364 of 2026 carries "Special Order next order of business (Rep. Luneau):
# MF RC 151-180 03/12/2026 HJ 7", which the House Journal of 11 March and the
# roll call both put on HB 1824. The row is taken out of the bill's history --
# its sentence, its journey, its sitting -- and kept, with the entry's note,
# in the list of the docket's own lines, where the clerk still shows it; the
# bill it belongs to gets a note on its own row of the same vote.
MISFILED = []
MOVED = set()


def _squash(s):
    """Whitespace collapsed, so a row the clerk re-spaced still matches."""
    return re.sub(r"\s+", " ", str(s or "")).strip()


def load_corrections(path, kind="dates"):
    """The entries of docket_corrections.json, or [] where there is none:
    its dates, or with kind="misfiled" its rows filed under another bill."""
    p = Path(path) if path else None
    if not p or not p.exists():
        return []
    doc = json.loads(p.read_text(encoding="utf-8"))
    need = "corrected_to" if kind == "dates" else "belongs_to"
    return [e for e in (doc.get(kind) or []) if isinstance(e, dict)
            and e.get("source_says") and e.get(need)]


def misfiled(r, bill):
    """(the entry, where r is the row it takes off this bill; or None) and
    the note for r where it is the belonging bill's own row of that vote."""
    desc = _squash(r.get("desc"))
    for i, e in enumerate(MISFILED):
        if str(e.get("body", "")).upper() != str(r.get("body", "")).upper():
            continue
        if (str(e.get("session")) == str(r.get("session"))
                and str(e.get("bill", "")).upper() == bill.upper()
                and _squash(e["source_says"]) == desc):
            MOVED.add(i)
            return e, ""
        # The bill it belongs to by the TERM: its own rows can carry the
        # term's other session year. SB 286 of 2025's "Enrolled" row
        # (session 2025) is SB 268's, whose rows say 2026.
        if (P.term_of(str(e.get("session")))
                and P.term_of(str(e.get("session"))) == P.term_of(str(r.get("session")))
                and str(e.get("belongs_to", "")).upper() == bill.upper()
                and _squash(e.get("belongs_to_says")) == desc):
            return None, (e.get("note_there") or "").strip()
    return None, ""


def _iso(mdy):
    try:
        return datetime.strptime(mdy, "%m/%d/%Y").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def corrected_date(r, bill):
    """(corrected mm/dd/yyyy, the entry) for this docket row, or (None, None).

    Matched on session, bill, chamber and the row's own text, whitespace
    collapsed on both sides."""
    desc = _squash(r.get("desc"))
    for i, e in enumerate(CORRECTIONS):
        if (str(e.get("bill", "")).upper() == bill.upper()
                and str(e.get("body", "")).upper() == str(r.get("body", "")).upper()
                and str(e.get("session")) == str(r.get("session"))
                and _squash(e["source_says"]) == desc):
            CORRECTED.add(i)
            y, m, d = e["corrected_to"].split("-")
            return f"{m}/{d}/{y}", e
    return None, None


def _sibling_rows(bill, rows):
    """Rows no entry corrects that state an entry's mistyped date and cite
    its journal. SB 152's committee amendment carried the same Sunday date as
    its floor vote beside it and was missed until a second reading; a row
    like that is a correction nobody has written yet."""
    out = []
    for e in CORRECTIONS:
        if str(e.get("bill", "")).upper() != bill.upper():
            continue
        try:
            y, m, d = str(e.get("stated_date") or "").split("-")
        except ValueError:
            continue
        stated = re.compile(rf"\b0?{int(m)}/0?{int(d)}/{y}\b")
        cite = cite_of(e.get("source_says"))[0]
        for r in rows:
            # An action the pages date: not a note such as "Removed from
            # Consent (Reps. ...)", which names the day it was noted.
            if classify(r.get("desc") or "")["_type"] not in (
                    "floor", "veto_override", "amendment", "enrolled"):
                continue
            if (str(r.get("session")) == str(e.get("session"))
                    and str(r.get("body", "")).upper() == str(e.get("body", "")).upper()
                    and stated.search(r.get("desc") or "")
                    and (not cite or cite_of(r.get("desc"))[0] == cite)
                    and not any(_squash(x["source_says"]) == _squash(r.get("desc"))
                                for x in CORRECTIONS
                                if str(x.get("bill", "")).upper() == bill.upper())):
                out.append((bill, _squash(r.get("desc"))))
    return sorted(set(out))


def signins(bill, date):
    """", with online testimony at 55 signed in support, 140 in opposition
    and 43 neutral" -- or nothing at all.

    Only where the database has this bill AND this date. Its whole-bill total
    is true of the bill and not of one hearing, and a bill with three hearings
    would otherwise have the same figure printed under each of them as though
    each had drawn that many.
    """
    rec = (TESTIMONY.get(TERM) or {}).get(bill or "")
    if not rec or not date:
        return ""
    # The docket writes 03/12/2025 and the database writes 2025-03-12. The
    # first version compared them directly and matched on no bill at all,
    # which is the shape of failure that looks like "no hearing has counts".
    try:
        mm, dd, yy = date.split("/")
        iso = f"{yy}-{int(mm):02d}-{int(dd):02d}"
    except ValueError:
        iso = date
    h = next((x for x in rec.get("hearings", []) if x.get("date") == iso), None)
    if not h or not h.get("total"):
        return ""
    bits = [f"{h[k]:,} {word}" for k, word in
            (("support", "signed in support"), ("oppose", "in opposition"),
             ("neutral", "neutral")) if h.get(k)]
    return ", with online testimony at " + and_list(bits) if bits else ""


# The Senate puts the mover in FRONT and folds the verb in with the name:
# "Sen. Abbas Moved Laid on Table", "Sen. Fuller Clark Moved to Concur with
# the House Amendment", "Sen. Innis Accedes to House Request for Committee of
# Conference". 1,257 floor actions begin this way and no House action does --
# the House writes a trailing "(Rep. K. Rice)", which MOVER_RE already reads.
# The name runs up to the first verb, so a two-word surname stays whole.
# "Moved"/"Move" and a following "to" belong to the mover clause, not the
# motion; "Accedes", "Refused" and "Waived" ARE the motion and stay.
LEAD_MOVER_RE = re.compile(
    r"^(?P<mover>Sen\.\s+(?:[A-Z][\w'\u2019.\-]*\s+){1,3}?)"
    r"(?=(?:Moved?|Accedes|Refused|Waived)\b)", re.I)
MOVED_RE = re.compile(r"^Moved?\s+(?:to\s+)?", re.I)


def _floor_fields(e):
    """action with the mover taken out, and the mover expanded from the roster.

    Exported beside the motion so the site can print "Moved by Sen. Daryl
    Abbas" under a voice vote rather than inside its heading. raw is untouched
    -- the docket list keeps the clerk's exact words.
    """
    action, who = split_mover(e.get("action"))
    return {"action": action, "mover": expand_mover(who) if who else ""}


def split_mover(action):
    """(motion without the mover, mover) for one floor action.

    House:  "Lay on Table (Rep. K. Rice)"    -> ("Lay on Table", "Rep. K. Rice")
    Senate: "Sen. Abbas Moved Laid on Table" -> ("Laid on Table", "Sen. Abbas")

    Before this, the Senate name stayed inside the motion, so the Votes tab
    headed a voice vote "Sen. Abbas Moved Laid on Table" as though that were
    the question put, and the sentence said the Senate adopted it.
    """
    action = (action or "").strip()
    m = MOVER_RE.search(action)
    if m:
        return MOVER_RE.sub("", action).strip(), m.group("mover").strip()
    m = LEAD_MOVER_RE.match(action)
    if m:
        rest = action[m.end():].strip()
        return (MOVED_RE.sub("", rest).strip() or rest), m.group("mover").strip()
    return action, ""


def _chapter_plain(ev):
    """The chapter without the clerk's leading zeros: "0213" is Chapter 213."""
    c = str(ev.get("chapter") or "").strip()
    return int(c) if c.isdigit() else c


def describe(ev, body, seen_intro=False):
    """One sentence for one docket event, or None to skip."""
    t = ev["_type"]
    chamber = "House" if body == "H" else "Senate"

    if t == "to_be_introduced":
        # The row's own words: it was to be, and build() found it withdrawn
        # on or before that day.
        return (f"It was to be introduced on {fdate(ev['date'])} and referred to "
                f"the {chamber} {_committee(ev, body)}.")

    if t == "entered_introduced":
        # The docket's row says introduced and the House Journal's resolution
        # of introduction steps over the number (build()): told as what the
        # docket enters, with what the journal says beside it, and never as
        # an introduction. "on" a day only where the row states one -- HB 633
        # of 2007's states none, and the day it was typed is not that day.
        # And in the row's own tense: HB 177 and HB 277 of 2017 are each one
        # row that still reads "To Be Introduced 01/04/2017 and referred to
        # ...", which the docket never entered as done.
        j = ev.get("_journal") or {}
        to = (f" and referred to the {chamber} {_committee(ev, body)}"
              if ev.get("committee") else "")
        try:
            day = datetime.strptime(j.get("date") or "", "%Y-%m-%d").strftime(MONTH)
        except ValueError:
            day = ""
        left = ("; the House Journal" + (f" of {day}" if day else "")
                + " leaves it out of the bills it introduces")
        as_ = ("to be introduced" if TO_BE_INTRODUCED.match(ev.get("_raw") or "")
               else "introduced")
        if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", ev.get("_raw") or "") and ev.get("date"):
            return f"The docket enters it as {as_} on {fdate(ev['date'])}{to}{left}."
        typed = (f", on a row entered {ev['_entered'].strftime(MONTH)}"
                 if ev.get("_entered") and ev["_entered"] != datetime.min else "")
        return f"The docket enters it as {as_}{to}{typed}{left}."

    if ev.get("_void") and t in ("hearing", "exec", "worksession"):
        # Scheduled for a day after the bill was withdrawn: a notice, not a
        # meeting. The past tense of every sentence below would say it sat.
        #
        # AND NOT TOLD AT ALL (decision 59e, the person's rule of 6 October
        # 2026 for a meeting that did not sit): HB 1284 and HB 1512 of 2012,
        # withdrawn on 4 January with a hearing set for the 12th, and HA 1 of
        # 2008, taken from its committee two days before its hearing of 25
        # April, were the last histories saying "A public hearing had been
        # scheduled for ...". The row stays among the docket lines with its
        # note (notice_note), as every notice a later row cancelled does; and
        # so does one set for a bill that was never introduced, which no
        # committee had. Only HB 273 of 2017's, whose bill the House Journal
        # leaves out, is told, because nothing on disk says it did not sit.
        if not ev.get("_journal"):
            return None
        what = {"hearing": "A public hearing", "exec": "An executive session",
                "worksession": "A work session"}[t]
        if ev.get("_journal"):
            # Or scheduled for a bill the House Journal leaves out of those it
            # introduced (build()): HB 273 of 2017, "Public Hearing: 01/10/2017
            # 01:30 PM LOB 306", entered on 4 January. The row is the docket's
            # notice and nothing on disk says more -- the committee filed a
            # report of every other hearing it noticed for that day and none
            # of this one -- so the sentence says whose word it is, and that
            # nothing here says whether the hearing was held.
            return (f"The docket schedules {what[0].lower()}{what[1:]} for "
                    f"{fdate(ev['date'])}, for a bill the House did not introduce; no "
                    "record on this site says whether it was held.")

    if t == "withdrawn":
        when = (fdate(ev["date"]) if ev.get("date")
                else ev["when"].strftime(MONTH) if ev.get("when") else "")
        on = f" on {when}" if when else ""
        if ev.get("read"):
            return (f"It was read in on {re.sub(r'\s+', ' ', ev['read']).strip()} "
                    "and withdrawn.")
        if ev.get("prior"):
            return f"It was withdrawn prior to introduction{on}."
        if ev.get("by"):
            return f"It was withdrawn by the petitioner{on}."
        return f"It was withdrawn{on}."

    if t == "proposed":
        when = ev["when"].strftime(MONTH) if ev.get("when") else ""
        return ("It was proposed as a bill for the special session"
                + (f" on {when}" if when else "") + ".")

    if t == "introduced":
        # A joint committee is named whole by its row -- "a Joint Committee
        # of Finance and Ways and Means" (SB 152 of 2013) -- and "the House a
        # Joint Committee of ... committee" is not a sentence.
        # And one the row names without the article, "Joint Committee on
        # Address" (HA 1 of 1999) and "Joint Legislative Committee on Address"
        # (HA 1 of 2010), is of both chambers: "the House Joint Committee on
        # Address committee" names neither it nor a House committee.
        to = (ev["committee"] if re.match(r"a\s+Joint\s+Committee\b", ev.get("committee") or "")
              else f"the {ev['committee']}"
              if re.match(r"Joint\s+(?:Legislative\s+)?Committee\s+on\b", ev.get("committee") or "")
              else f"the {chamber} {_committee(ev, body)}")
        if seen_intro and ev.get("_crossed_late"):
            # Told after the vote that sent it (crossing_order), and with no
            # day: the chamber introduced it in recess and dates it by the
            # session it was in recess of, a day before the vote. The event,
            # the docket list and the rail keep that day; the sentence says
            # only that it crossed (the person's wording, 8 October 2026).
            return f"It crossed to the {chamber} and was referred to {to}."
        if seen_intro:
            # Crossover: the second chamber records receipt as an introduction.
            return (f"It crossed to the {chamber} on {fdate(ev['date'])} and was "
                    f"referred to {to}.")
        return f"It was introduced on {fdate(ev['date'])} and referred to {to}."

    if t == "vacated":
        # "Vacated ref to Executive Dept & Administration, MA, VV" (SB 295 of
        # 2006) names the referral it vacates, not where the bill went: it
        # went "ref to Commerce" on a row of its own, which says so. The
        # reader's committee is the one the bill left, and the sentence said
        # the House sent the bill to it "instead".
        if VACATES_REFERRAL.search(ev.get("_raw") or ""):
            return f"The {chamber} withdrew that referral."
        return (f"The {chamber} withdrew that referral and sent the bill to the "
                f"{_committee(ev, body)} instead.")

    if t == "hearing" and ahead(ev.get("date")):
        return (f"A public hearing is scheduled for {fdate(ev['date'])}"
                f"{signins(ev.get('_bill'), ev.get('date'))}.")

    if t == "exec" and ahead(ev.get("date")):
        return (f"The committee is due to meet in executive session on "
                f"{fdate(ev['date'])} to vote on its recommendation.")

    if t == "worksession" and ahead(ev.get("date")):
        return f"A work session is scheduled for {fdate(ev['date'])}."

    if t == "hearing" and ev.get("_no_day"):
        # The day its row states is not taken, and the day the row was
        # entered is not the day the committee sat (before_the_bill).
        return "The committee held a public hearing."

    if t == "hearing":
        # Counts only, and only for THIS hearing's date. Who signed in is not
        # published here and is not asked for: almost every one of the 400,000
        # rows is a private individual who signed a committee's sheet.
        return (f"The committee held a public hearing on {fdate(ev['date'])}"
                f"{signins(ev.get('_bill'), ev.get('date'))}.")

    if t == "exec":
        return (f"The committee met in executive session on {fdate(ev['date'])} "
                "to vote on its recommendation.")

    if t == "worksession":
        return f"The committee held a work session on {fdate(ev['date'])}."

    if t == "report":
        rec = (ev.get("rec") or "").strip().lower()
        plain = None
        for k, v in RECOMMENDATION.items():
            if rec.startswith(k):
                plain = v
                break
        # UNANIMOUS, WHERE IT WAS. "by a vote of 11-0" is the record, but a
        # committee that agreed without a dissenting voice is worth saying
        # plainly, and a tie is worth saying too: a tied committee vote
        # carries no majority. Where no vote was recorded, nothing is said.
        _y, _n = str(ev.get("y") or ""), str(ev.get("n") or "")
        vote = ""
        if _y.isdigit() and _n.isdigit():
            if int(_n) == 0 and int(_y) > 0:
                vote = f" unanimously, {_y}–{_n}"
            elif int(_y) == int(_n):
                vote = (f" on a tied vote, {_y}–{_n}, which carries no "
                        "majority")
            else:
                vote = f" by a vote of {_y}–{_n}"
        calm = CALENDAR_RE.search(ev.get("_raw", ""))
        cal = ""
        if calm:
            name, _ = CALENDAR[calm.group("cal").upper()]
            cal = f", and the report was placed on {name}"
        amend = f" (amendment {ev['amend']})" if ev.get("amend") else ""
        # The pattern already found which side signed it. Searching the
        # line again for the word missed "Majoritiy", and would read a
        # bill whose own title says "minority" as a minority report.
        side = {"Majority": "the majority",
                "Minority": "the minority"}.get(report_side(ev.get("side")), "")
        who = f"{side.capitalize()} of the committee" if side else "The committee"
        if plain:
            return (f"{who} recommended that the {chamber} {plain}"
                    f"{amend}{vote}{cal}.")
        rec = (ev.get("rec") or "").strip()
        # THE CLERK'S OWN WORD FOR NO RECOMMENDATION. SB 466 of 2000 read
        # "The committee reported: None." -- which looks like this site
        # failing to fill a template, and is not: the docket line is
        # "Committee Report None, 05/03/2000", and the next line is
        # "Sen. Trombly moved to suspend Rule #22A to allow no committee
        # recommendation before the body". The committee reported without
        # recommending, and that is worth a sentence rather than a blank.
        if not rec or rec.lower() in ("none", "no recommendation", "n/a"):
            return f"{who} made no recommendation{vote}."
        return f"{who} reported: {rec}{vote}."

    if t == "ot3rdg":
        # The order a tabling left pending, carried once the bill came off
        # the table (build(): PASSAGE_PENDING).
        return f"On {ev['when'].strftime(MONTH)} the {chamber} ordered it to a third reading."

    if t == "floor":
        action, who = split_mover(ev.get("action"))
        mover = f", on a motion by {expand_mover(who)}" if who else ""
        motion = MOTION.get((ev.get("motion") or "").upper(), "")
        vcode = (ev.get("vote") or "").upper()
        has_tally = bool(ev.get("y") and ev.get("n"))
        if vcode == "RC" and not has_tally:
            # "RC" without numbers is Regular Calendar, not Roll Call.
            vcode = ""
        vk, recorded = VOTE_KIND.get(vcode, (None, None))
        low = action.lower()

        verb = None
        for k, v in RECOMMENDATION.items():
            if low.startswith(k):
                verb = v
                break

        when = fdate(ev["date"]) if ev.get("date") else ""
        tally = (f" {ev['y']}\u2013{ev['n']}" if ev.get("y") and ev.get("n") else "")

        if verb and motion == "adopted" and ev.get("_unpassed"):
            # Not a passage (PASSAGE_PENDING): the motion carried, and the
            # step that passes the bill was left pending by a tabling.
            base = (f"On {when} the {chamber} adopted the motion that it ought to pass"
                    + (" with an amendment" if "with amendment" in low else ""))
        elif verb and motion == "adopted":
            base = f"On {when} the {chamber} voted to {verb}"
        elif verb and motion == "failed":
            base = f"On {when} the {chamber} rejected a motion to {verb}"
        else:
            base = f"On {when} the {chamber} {motion or 'considered'} \u201c{action}\u201d"

        if vk and tally and motion == "adopted" and CONSENT_VOTE.search(ev.get("_raw") or ""):
            # The count is the consent calendar's (CONSENT_VOTE), unless the
            # calendar's other rows give another (calendar_count_disputed).
            # And "adopted" once: the House "adopted 'Refer to Interim
            # Study' as part of its consent calendar, which it adopted on a
            # division vote" (HB 1286 of 2014).
            if calendar_count_disputed(ev):
                base += " as part of its consent calendar"
            else:
                base += (f" as part of its consent calendar, which it "
                         f"{'adopted' if verb else 'approved'} on a {vk}{tally}")
        elif vk:
            base += f" on a {vk}{tally}"
        if ev.get("_unpassed"):
            base += (", but its third reading was left pending" if ev["_unpassed"] == "third"
                     else ", but its referral to the Finance committee was left pending")
        elif OT_RDG.search(ev.get("_raw", "")):
            base += " and ordered it to a third reading"
        if ev.get("refer"):
            # The person's wording (7 October 2026): "the Senate voted to
            # pass it on a voice vote, then referred it on to the Senate
            # Finance committee." AND THE HOUSE'S IN THE SAME WORDS (the
            # launch audit's recheck): its referral on the passage's own row,
            # "PASSED AND REF TO FINANCE" (1989-2006), read "then sent it on
            # to the Finance committee", a sentence of its own for the same
            # step; it is told as the Senate's is. Exactly as the Senate's
            # (the person, 8 October 2026): the House's no longer adds "under
            # the chamber's rules" where the rules sent it.
            to = _committee(ev, body, "refer")
            named = to if to.lower().startswith(chamber.lower()) else f"{chamber} {to}"
            base += f", then referred it on to the {named}"
        return _stop(base + mover)

    if t == "amendment":
        kind = (ev.get("what") or "Amendment").strip()
        num = ev.get("num") or ""
        when = f" on {fdate(ev['date'])}" if ev.get("date") else ""
        motion = (ev.get("motion") or "").upper()
        adopted = motion in ("AA", "ADOPTED")
        vk, _ = VOTE_KIND.get((ev.get("vote") or "").upper(), (None, None))
        y, n = ev.get("y"), ev.get("n")
        # NO MOTION IS NOT A REJECTION. See amendment_outcome().
        # A vote on part of it, where the event says so itself: the 1999-2006
        # reader's "Am{2229}, Remaining Secs, AA RC(239-112)" carries its
        # result and "part" (docket_era_1999.CLAUSE_AMEND_PART).
        said, part = ("adopted" if adopted
                      else "rejected" if motion in ("AF", "AL", "FAILED")
                      else None), ev.get("part") or False
        if said is None and "Enrolled Bill" not in kind:
            said, part, vk2, y2, n2 = amendment_outcome(ev["_raw"])
            adopted = said == "adopted"
            if not vk and vk2:
                vk, _ = VOTE_KIND.get(vk2, (None, None))
                y, n = y or y2, n or n2
            # The kind read without its count: the database era's "Div.
            # 16Y-8N, AA" (HB 1487 of 2012) arrives as a division and no
            # tally, and the tally is on the row.
            elif (vk and vk2 and vk2 != "VV" and not (y and n)
                  and VOTE_KIND.get(vk2, (None, None))[0] == vk):
                y, n = y2, n2
            if said in (None, "not voted on") and ev.get("_decided_elsewhere"):
                return None
        how = (f" on a {vk}" if vk else "") + (f" {y}\u2013{n}"
                                               if vk and y and n else "")
        if "Enrolled Bill" in kind:
            return (f"An enrolled bill amendment ({num}) was "
                    f"{'adopted' if adopted else 'considered'}{how}{when}. These correct "
                    "technical errors found after passage.")
        # WHOSE AMENDMENT IT IS, from the bill's own reports where the row's
        # word does not say (whose_amendment): a bare House row, or a FLAM
        # row, whose number a report of that chamber names is the committee's
        # or its minority's; any other is one offered on the floor. A bare
        # row was called "a floor amendment" here on the word of stage_of,
        # and on 601 bills of 2025-2026 that was the committee's own.
        # And an amendment the committee's minority wrote is neither the
        # committee's nor any member's: the 1999-2006 reader's "Min Am{1208}"
        # (docket_era_1999.MINORITY_AMENDMENT), offered on the floor against
        # the majority's.
        kind = WHOSE_KIND.get(ev.get("_whose")) or kind
        who = ("The committee's amendment" if "committee" in kind.lower()
               else "The committee minority's amendment"
               if kind.lower() == "minority amendment"
               else "A floor amendment")
        # The Senate's verb is not part of the senator's name: "Sen. Bradley
        # Offered Floor Amendment" read "offered by Sen. Bradley Offered".
        mover = MOVER_VERB.sub("", (ev.get("mover") or "").strip())
        by = f", offered by {expand_mover(mover)}," if mover else ""
        # "Amendment #2022-0339s to HB 50 will be proposed and can be accessed
        # via the General Court Website": a Senate Calendar's notice of an
        # amendment to come, not one offered on the floor. Five bills of 2022
        # carry one, four of them pointing to the redistricting committee's
        # page of submissions, and each was told as a floor amendment.
        if said is None and re.search(r"\bwill be proposed\b", ev.get("_raw") or "", re.I):
            return f"Notice was given that an amendment ({num}) would be proposed{when}."
        if said in (None, "not voted on"):
            # Offered, and no amendment row decides it -- or the docket says
            # in as many words that it was not voted on. What the bill's other
            # rows say of it is build()'s _fate; with none, nothing is claimed
            # beyond the offer, and "no vote" is said only where no other row
            # names the amendment at all.
            verb = "proposed" if said is None else "offered"
            fate = ev.get("_fate") or ""
            tail = ("; it was not voted on" if said else "") + (
                (" and was later withdrawn" if said else "; it was later withdrawn")
                if fate == "withdrawn"
                else "; the chair ruled sections of it non-germane" if fate == "sections ruled"
                else "; the chair ruled it non-germane" if fate == "ruled"
                else "; the docket records no vote on it" if fate == "unnamed" and not said
                else "")
            return ((f"{expand_mover(mover)} {verb} {who[0].lower()}{who[1:]}"
                     if mover else f"{who} was {verb}").replace(
                         "amendment", f"amendment ({num})", 1)
                    + when + tail + ".")
        if part == "rest":
            # What was left once sections were divided out of it, and the
            # sentence before has usually just told those.
            who = "The rest of " + ("the floor amendment" if who == "A floor amendment"
                                    else f"{who[0].lower()}{who[1:]}")
        elif part:
            who = f"Part of {who[0].lower()}{who[1:]}"
        # "changing the text of the bill" was appended to every amendment,
        # including the ones that failed. A rejected amendment changed
        # nothing; saying it did is not a clumsy sentence, it is a false one.
        return (f"{who} ({num}){by} was {said}"
                f"{how if said in ('adopted', 'rejected') else ''}{when}"
                + (", changing the text of the bill." if adopted else "."))

    if t == "veto_override":
        outcome = (ev.get("outcome") or "").lower()
        when = f"On {fdate(ev['date'])} " if ev.get("date") else ""
        vk, _ = VOTE_KIND.get((ev.get("vote") or "").upper(), (None, None))
        how = f" on a {vk}" if vk else ""
        y, n = ev.get("y"), ev.get("n")
        tally = f" {y}\u2013{n}" if y and n else ""
        if outcome == "overridden":
            return (f"{when}the {chamber} voted{tally} to override the governor's "
                    f"veto{how}, meeting the two thirds threshold.")
        # Deliberately no remark on whether a majority was in favour. The
        # tally's column order is not stated on this line, and the roll call
        # record already carries the authoritative numbers and says when a
        # majority fell short of the threshold.
        # The threshold joined to the outcome rather than following it as a
        # standalone rule. Why it failed is the same thought as that it
        # failed, and two sentences made a reader hold one to reach the other.
        return (f"{when}the {chamber} voted{tally} on overriding the governor's "
                f"veto{how}, and the veto was sustained, failing to meet the "
                f"two thirds threshold.")

    if t == "unsigned_law":
        when = f" on {fdate(ev['date'])}" if ev.get("date") else ""
        ch = f", as Chapter {_chapter_plain(ev)}" if ev.get("chapter") else ""
        return (f"It became law without the governor's signature{when}{ch}. The "
                "governor neither signed it nor returned it, and the docket "
                "records it as enacted under Part II, Article 44 of the state "
                "constitution.")

    if t == "enrolled":
        when = f" on {fdate(ev['date'])}" if ev.get("date") else ""
        return (f"The bill was enrolled{when} \u2014 the final check of the text "
                "before it goes to the governor.")

    # WHAT THE ROW RECORDS, as CONSENT_OFF_NOTE says it. This read "..., so
    # it was debated and voted on separately rather than passing in a block.
    # Ten members may petition for this." on 1,722 stages of 1,682 histories
    # after the note beside it had stopped saying either: the House needed
    # one member's request until January 2023 and the Senate never needed
    # ten, and the 67 bills of 1993 put back on the calendar
    # (RETURNED_TO_CONSENT) went through with it -- HB 264 of 1993 was told
    # as debated separately beside "ITL REPORT ADOPTED" with the calendar of
    # 16 March.
    if t == "consent_off":
        when = f" on {fdate(ev['date'])}" if ev.get("date") else ""
        return "The bill was taken off the consent calendar" + when + "."

    if t == "conference_meeting":
        if ev.get("_no_day"):
            return ("A committee of conference met to try to settle the differences "
                    "between the two chambers' versions of the bill.")
        return (f"A committee of conference met on {fdate(ev['date'])} to try to "
                "settle the differences between the two chambers' versions of "
                "the bill.")

    if t == "interim_report":
        rec = re.sub(r"\s+", " ", (ev.get("rec") or "").strip()).rstrip(".")
        lead = (f"On {fdate(ev['date'])} the committee" if ev.get("date")
                else "The committee")
        vote = (f", by a vote of {ev['y']} to {ev['n']}"
                if ev.get("y") and ev.get("n") else "")
        # Quoted rather than folded into the sentence. The docket writes the
        # recommendation in Title Case, and lowercasing it to fit the grammar
        # would be editing the committee's own words to make a sentence read
        # better.
        said = f": \u201c{rec}\u201d" if rec else ""
        return (f"{lead} reported back on its interim study of the bill"
                f"{said}{vote}.")

    if t == "retained":
        return ("The committee retained the bill, holding it for further work rather "
                "than reporting it out this year.")

    if t == "nongermane_hearing":
        # The hearing sentence above, of the amendment: "The committee held a
        # public hearing on February 11, 2025 on a proposed non-germane
        # amendment (2025-0102h), with online testimony at ...". The sign-ins
        # are the day's (signins), and go with the bill's own hearing where
        # it had one that day (_day_told, build()).
        # And the bill's own hearing whose row takes the amendment up too is
        # told by its other row of that day where it has one: SB 30 of 2015's
        # "==ROOM CHANGE== Public Hearing: 4/21/2015 1:00 PM LOB 210-211" is
        # the same hearing as its "...; to include consideration of
        # non-germane amendment #2015-1351h".
        if ev.get("_joint_told") or (ev.get("incl") and ev.get("_day_told")):
            return None
        num = f" ({ev['num']})" if ev.get("num") else ""
        counts = "" if ev.get("_day_told") else signins(ev.get("_bill"), ev.get("date"))
        if not ev.get("date"):
            return f"The committee held a public hearing on a proposed non-germane amendment{num}."
        if ahead(ev.get("date")):
            return (f"A public hearing on a proposed non-germane amendment{num} is scheduled "
                    f"for {fdate(ev['date'])}{counts}.")
        if ev.get("incl"):
            return (f"The committee held a public hearing on {fdate(ev['date'])}, which "
                    f"included a proposed non-germane amendment{num}{counts}.")
        return (f"The committee held a public hearing on {fdate(ev['date'])} on a proposed "
                f"non-germane amendment{num}{counts}.")

    if t == "conf_report":
        # The floor sentence above -- "On May 23, 1989 the Senate adopted
        # “Conference Committee Report” on a voice vote." is how the 1989-2006
        # readers' rows are told -- with what was adopted in the rail's words:
        # "On June 4, 2026 the Senate adopted the conference report
        # (2026-2109c) on a roll call 15–8." "On" a day only where the row
        # states one (stated_day).
        vk, _ = VOTE_KIND.get((ev.get("vote") or "").upper(), (None, None))
        tally = f" {ev['y']}–{ev['n']}" if vk and ev.get("y") and ev.get("n") else ""
        did = "adopted" if ev.get("motion") == "MA" else "rejected"
        lead = f"On {fdate(ev['date'])} the {chamber}" if ev.get("date") else f"The {chamber}"
        num = f" ({ev['num']})" if ev.get("num") else ""
        # "Failed, RC 224-141 Lacking Necessary Three-Fifths Vote" (CACR 12 of
        # 2012): a majority, short of what a constitutional amendment needs --
        # the rail's words.
        short = re.search(r"\blacking\s+(?:the\s+)?necessary\s+(two|three)\W+(thirds|fifths)",
                          ev.get("_raw") or "", re.I)
        return (f"{lead} {did} the conference report{num}"
                + (f" on a {vk}{tally}" if vk else "")
                + (f", short of {short.group(1).lower()} {short.group(2).lower()}"
                   if short and did == "rejected" else "") + ".")

    if t == "died":
        when = f" when the session ended on {fdate(ev['date'])}" if ev.get("date") else " when the session ended"
        return f"The bill died on the table{when}, having been set aside and never taken back up."

    if t == "senate_rule_kill":
        # The sentence above, under the rule that ended it, and in the status
        # chip's words for it, "Died on the table": "The bill died on the
        # table under Senate Rule 3-23 on October 31, 2025, having been set
        # aside and never taken back up." "on" a day only where the row
        # states one (stated_day).
        adj = " at adjournment" if re.search(r"\badjournment\b", ev.get("_raw") or "", re.I) else ""
        when = f" on {fdate(ev['date'])}" if ev.get("date") else ""
        return (f"The bill died on the table under Senate Rule 3-23{adj}{when}, having been "
                "set aside and never taken back up.")

    if t == "rereferred":
        # THE CLERK DOES NOT ALWAYS NAME IT. HB 246 of 1999 reads
        # "Re-Referred to committee; HJ40, p907" and nothing more -- it went
        # back to the committee it came from, which the House did not need to
        # name. Printed through the sentence below that became "referred to
        # the  committee", with the gap where a name should be, on six pages.
        # Naming the committee it probably meant would be inventing a fact
        # the docket declines to state, so the sentence simply stops saying
        # which.
        c = _named(ev, body)
        where = f" to the {_committee(ev, body)}" if c else " back to committee"
        return f"On {fdate(ev['date'])} the bill was referred{where}."

    if t == "governor":
        w = (ev.get("what") or "").lower()
        when = fdate(ev["date"]) if ev.get("date") else ""
        if "signed" in w:
            s = f"The governor signed it on {when}"
            if ev.get("chapter"):
                # WITHOUT THE CLERK'S LEADING ZEROS. The docket writes
                # "Chapter 0213" and the status line beside this sentence
                # writes "Chapter 213"; one fact, printed two ways, on 345
                # of the current terms' 1,270 sentences and on 2,800 of the
                # archived ones.
                _ch = str(ev["chapter"]).strip()
                s += (f", making it Chapter {int(_ch) if _ch.isdigit() else _ch}"
                      " of the session laws")
            if ev.get("eff"):
                # TENSE. "It takes effect January 1, 1994" on a law from
                # 1993 reads as a promise about the future; the date passed
                # thirty years ago. ahead() is the same test every meeting
                # sentence uses.
                s += (f". It takes effect {fdate(ev['eff'])}"
                      if ahead(ev["eff"]) else
                      f". It took effect on {fdate(ev['eff'])}")
            return s + "."
        if "vetoed" in w:
            # Some veto lines carry no parsed date; rather than "vetoed it on ."
            # take the date out of the raw text, and say nothing if there is
            # none to take.
            if not when:
                dm = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", ev.get("_raw", ""))
                when = fdate(dm.group(1)) if dm else ""
            return (f"The governor vetoed it{' on ' + when if when else ''}. "
                    "The legislature can override a veto with a two-thirds vote "
                    "in both chambers.")
        return f"It was sent to the governor on {when}."

    return None


HELD_IN_ORDER = ("floor", "veto_override", "amendment", "enrolled", "governor")

# "Enrolled (In recess 4/9/2015)", "House Non-Concurs ... (in recess of
# 6/3/2015)", "Enrolled (in recess of) 06/04/2026": the sitting a chamber was
# in recess of, which the line's own pattern takes as its date.
IN_RECESS = re.compile(r"\bin\s+recess(?:\s+of)?\)?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})", re.I)


# What an enrolment follows: the chambers' votes on the bill. And what it
# comes before: the bill going to the governor, and the governor's action.
ENROLMENT_FOLLOWS = ("floor", "veto_override")
ENROLMENT_PRECEDES = ("governor", "unsigned_law")


def in_recess(ev, r, fixed=None):
    """Mark an enrolment dated by the sitting it was done in recess of, so
    that hold_in_order puts it back to the day it was entered where that
    date would tell it before a vote on the bill.

    A DAY IN RECESS IS NOT THE DAY IT WAS DONE, and put an enrolment ahead
    of the passage it enrolled: SB 48 of 2015's "Enrolled (In recess
    4/9/2015)" was entered on 29 April and told as enrolled on 9 April, six
    days before the House passed the bill on the 15th.

    ONLY AN ENROLMENT, and only ahead of a vote. Held in order by every
    action of the bill, as an as-of date is, 922 bills' in-recess rows moved
    -- introductions, and the House refusing an amendment on the day it was
    entered rather than the day it was done, after the Senate's answer to
    it. An enrolment follows the votes and nothing else, so a vote is the
    one thing it may not come before. Not where a person corrected the date
    (`fixed`).

    NOR AFTER THE GOVERNOR. SB 447 of 2016, Chapter 1 of that year's laws,
    was "Enrolled (In recess 01/14/2016)", entered on 26 January: the House
    passed it on the 20th and the governor signed it on the 21st, so the day
    it was entered told the enrolment five days after the signature. There
    it takes the day of the last vote before the governor acted, and its
    place after that vote -- the earliest day it can have been done, and the
    day the House's own "Enrolled 01/20/2016" states."""
    m = IN_RECESS.search(r.get("desc") or "")
    created = r.get("created")
    enrolment = ev.get("_type") == "enrolled" or (
        ev.get("_type") == "amendment" and re.match(r"\s*enrolled", r.get("desc") or "", re.I))
    if (not m or not enrolment or fixed or ev.get("_stamp_date") or not ev.get("date")
            or not isinstance(created, datetime) or created == datetime.min):
        return ev
    try:
        said = datetime.strptime(m.group("date"), "%m/%d/%Y")
        dated = datetime.strptime(ev["date"], "%m/%d/%Y")
    except ValueError:
        return ev
    if said == dated and created.date() > dated.date():
        ev["_stamp_date"] = created.strftime("%m/%d/%Y")
        ev["_stamp_after"] = ENROLMENT_FOLLOWS
        ev["_stamp_before"] = ENROLMENT_PRECEDES
    return ev


# A ROW FILED UNDER THE OTHER CHAMBER. The docket's chamber column is typed by
# hand, and HB 1371 of 1992 carries its House committee's report under S:
# "1992|2256|02/04/1992|HB1371|S|MAJ REPORT ITL FOR FEB11 (VOTE 14-0;CC)", the
# one row of that letter, between the committee's work session and "ITL REPORT
# ADOPTED" in the House on 11 February. HB 1188 of 1992 carries a subcommittee
# work session of House Transportation the same way. The history gave each a
# stage "In Senate committee", and the rail drew "House: Passed, Senate:
# Passed" for a bill the House killed and one it sent to interim study.
#
# A committee's row needs a referral, and a referral an introduction. So where
# a chamber's ONLY row on a measure is a committee's -- a hearing, a session
# or a report -- and the other chamber has every other row, at least two, the
# row is told as the chamber's whose bill it is, and the bill's list of
# docket lines says so beside it. Not a floor row: "Sen. Francoeur Rules
# Suspension 2/3 nec. for Introduction, MF" is the Senate's one row on HB 2002
# of 2002, and it is the Senate refusing the bill.
#
# AND ONLY WHERE THE OTHER CHAMBER CANNOT HAVE HAD THE BILL. A docket still
# being written can show the same shape for a moment and mean the opposite:
# the House passes a bill, and the Senate's first row on it is a hearing
# notice, entered before its row of introduction. That row is the Senate's.
# So the chamber the row is given to must not have passed the measure on --
# no floor row of its own carrying a motion to pass or adopt it -- and must
# have gone on acting on it afterwards, with a row entered after this one. HB
# 1371's is followed by "ITL REPORT ADOPTED" in the House, and HB 1188's by
# the House's referral to interim study: neither left the House.
COMMITTEE_ROWS = ("hearing", "exec", "worksession", "report", "interim_report", "retained")
FILED_UNDER = ("The General Court's docket files this row under the {wrong}. It is the only "
               "row there, and a committee's: it is told as the {right}'s.")
CARRIED_ON = re.compile(r"^\W*(?:ought\s+to\s+pass|OTP\b|pass|adopt)", re.I)


def other_chambers_row(evs):
    """Give a committee row filed under the chamber that never had the bill
    to the chamber that did (COMMITTEE_ROWS). evs is every row of the bill,
    in the order entered."""
    for wrong, right in (("S", "H"), ("H", "S")):
        mine = [e for e in evs if (e.get("body") or "").upper() == wrong]
        theirs = [e for e in evs if (e.get("body") or "").upper() == right]
        if not (len(mine) == 1 and len(theirs) >= 2
                and mine[0].get("_type") in COMMITTEE_ROWS):
            continue
        sent_on = any(e.get("_type") == "floor" and (e.get("motion") or "").upper() == "MA"
                      and CARRIED_ON.search(e.get("action") or "") for e in theirs)
        later = any(e.get("_row", -1) > mine[0].get("_row", 0) for e in theirs)
        if sent_on or not later:
            continue
        mine[0]["body"] = right
        if not mine[0].get("row_note"):
            mine[0]["row_note"] = FILED_UNDER.format(
                wrong=CHAMBER[wrong], right=CHAMBER[right])
    return evs


def hold_in_order(evs):
    """An as-of date (docket_vocab.as_of) may not move an action ahead of one
    it followed. evs is sorted; it is re-sorted if anything is put back.

    The clerk's "[05/06/04]" on "Senator Peterson Accede to House Request for
    C of C", entered on 13 May 2004, would have dated the Senate's answer six
    days before the House's request -- the date is the sitting the Senate was
    in recess of, not the day it acted. Where any action of the bill falls
    after the as-of date and by the day the row was entered, the row keeps
    the day it was entered.

    AND ITS PLACE IN THAT DAY. A row put back keeps the midnight of the day
    it was entered, and so ties every other row of that day; a stable sort
    would leave it where the as-of date had put it, ahead of them all -- the
    Senate's accession of 4:39 PM before the House's request of 10:54 AM, on
    fourteen bills of 2004. Ties are broken by the order the rows were
    entered (ev["_row"], set by build), which is the order they had before
    any as-of date moved one.
    """
    back = False
    for ev in evs:
        stamp = ev.get("_stamp_date")
        # What it may not come before: any action, for an as-of date; a
        # vote, for an enrolment done in recess (in_recess).
        after = ev.pop("_stamp_after", HELD_IN_ORDER)
        # And what it may not come after: the governor, for that enrolment.
        before = ev.pop("_stamp_before", ())
        if not stamp:
            continue
        try:
            entered = datetime.strptime(stamp, "%m/%d/%Y")
        except ValueError:
            continue
        if any(o is not ev and o.get("_type") in after
               and not o.get("cancelled") and ev["when"] < o["when"] <= entered
               for o in evs):
            gov = [o for o in evs if o is not ev and o.get("_type") in before
                   and not o.get("cancelled") and ev["when"] < o["when"] <= entered]
            first = min(gov, key=day_order) if gov else None
            if first is None or first["when"].date() == entered.date():
                # The governor acting the day it was entered leaves it that
                # day, ahead of the governor (HB 273 of 2021, 11 May).
                ev["date"], ev["when"] = stamp, entered
                if first is not None:
                    ev["_row"] = min(ev.get("_row", 0), first.get("_row", 0) - 0.5)
                back = True
            else:
                votes = [o for o in evs if o is not ev and o.get("_type") in after
                         and not o.get("cancelled") and ev["when"] < o["when"]
                         and day_order(o) < day_order(first)]
                if votes:
                    last = max(votes, key=day_order)
                    ev["date"] = last["when"].strftime("%m/%d/%Y")
                    ev["when"], ev["_row"] = last["when"], last.get("_row", 0) + 0.5
                    back = True
        ev.pop("_stamp_date", None)
    if back:
        evs.sort(key=day_order)
    for ev in evs:
        ev.pop("_row", None)
    return evs


def day_order(ev):
    """The sort key of a bill's events: the day, then the order the clerk
    entered the rows.

    NOT THE MOMENT. A row whose line states its date is dated at midnight
    and a row that states none at the minute it was entered, so sorting on
    the moment put every dated row of a day ahead of every undated one,
    whatever the order they were entered in. HB 705 of 2003's House
    defeated its conference report 159-172 at 5:07 PM, reconsidered at 5:08
    and adopted it at 5:14; the two floor rows are dated, "Conf Comm Report
    Defeated" is not, and the history told the adoption first and the
    defeat last -- which is how the bill's journey came to end in the House
    with a rejection, on a bill that became law."""
    return (ev["when"].date(), ev.get("_row", 0))


# A CHAMBER INTRODUCES A BILL AFTER THE OTHER HAS SENT IT, WHATEVER DAY ITS
# ROW GIVES (the launch audit of 7 October 2026, cause 7). The Senate
# introduces the House's bills in recess and dates them by the session it is
# in recess of: HB 1460 of 2026 passed the House on 12 February (Docket.txt
# line 16976), and the Senate's row, entered on the 13th, reads "Introduced
# 02/05/2026" (line 17077) -- Senate Journal 4 prints it under pages headed 5
# February, "Adopted in recess". Told by its date, the history had it cross a
# week before the House voted, on 51 bills of 2025-2026, and the House does
# the same with Senate bills in every term since 1991 ("03/17/94 INTRODUCED
# AND REF TO APPROP", SB 504 of 1994, entered on the 23rd after the Senate's
# vote of the 22nd). So the receiving chamber's introduction, dated before a
# vote of the sending chamber that was entered before it, is told after the
# last such vote and the sending chamber's other rows of that day; its date,
# the docket list and the rail are as they were. Only the votes up to the
# receiving chamber's next row: SB 1 of 2023's House introduction was entered
# in April, after the Senate concurred on 14 February, and the vote that sent
# it was the Senate's of 26 January.
def crossing_order(evs):
    """The bill's events in the order its history tells them (above)."""
    first, moves = None, []
    for e in evs:
        if e["cancelled"] or e["_type"] != "introduced":
            continue
        if first is None:
            first = e
            continue
        day = e["when"].date()
        limit = min((x["when"].date() for x in evs if x is not e and x["body"] == e["body"]
                     and x["when"].date() > day), default=None)
        sent = [f["when"].date() for f in evs
                if f is not e and not f["cancelled"] and f["body"] != e["body"]
                and f["_type"] == "floor" and _entered_before(f, e["_entered"])
                and f["when"].date() > day and (limit is None or f["when"].date() <= limit)]
        if sent:
            moves.append((e, max(sent)))
    out = list(evs)
    for e, last in moves:
        out = [x for x in out if x is not e]
        sender = OTHER_CHAMBER.get(e["body"])
        j = max((i for i, x in enumerate(out)
                 if x["body"] == sender and x["when"].date() <= last), default=-1)
        out.insert(j + 1, e)
        e["_crossed_late"] = True
    return out


# A FLOOR VOTE WHOSE ROW STATES NO DATE (the launch audit of 7 October 2026,
# cause 8). "Inexpedient to Legislate: MA VV  HJ 6  P. 30" (HB 1473 of 2026,
# Docket.txt line 18612) is the House killing the bill on 5 March 2026, and
# the floor pattern, which ends at a date, read it as nothing: the history
# stopped at the committee and the Votes tab said there was no vote. Five
# bills of 2025-2026. The database's dockets of 1989-2016 already date such a
# row by the moment it was entered (docket_vocab._ensure_date); from 2017 a
# row that ends at its motion and vote is dated so too, but only where that
# day is one the dated floor rows citing the same journal carry: the clerk
# entered HB 1473's at 10:51 that morning, and HB 1036's "Inexpedient to
# Legislate: MA VV 03/05/2026  HJ 6  P. 2" (line 18484) says HJ 6 is of the
# 5th. "Lay HB1175 on Table (Rep. Abbas): MA VV HJ 5" was entered on 11 March
# 2022 for a journal whose rows are of the 10th, and is left as it was. Not a
# row the lenient floor pattern would misread: "... Withdrawn: MF DV
# 2025-1713h" (SB 78 of 2025) or the garbled "MF DV 031126 [&]" (HB 1565).
# {(chamber, "HJ 6", year): {day}}, over the whole docket main() reads.
VOLUME_DAYS = {}
FLOOR_UNDATED = re.compile(
    r"^(?P<action>.+?)\s*:\s*(?P<motion>MA|MF|ML)\s+(?P<vote>VV|DV|RC)"
    r"(?:\s+\d+\s*-\s*\d+)?\s*(?:\[&\])?$", re.I)


def volume_days(bills):
    """VOLUME_DAYS for {bill: [row]} (parse_docket)."""
    floor = dict(PATTERNS)["floor"]
    out = defaultdict(set)
    for rows in bills.values():
        for r in rows:
            vol, _page = cite_of(r.get("desc"))
            m = floor.search(clean(r.get("desc") or "")) if vol[:2] in ("HJ", "SJ") else None
            try:
                d = datetime.strptime(m.group("date"), "%m/%d/%Y").date() if m else None
            except ValueError:
                d = None
            if d:
                out[(r.get("body"), vol, d.year)].add(d)
    return dict(out)


def undated_floor(ev, r):
    """The floor event of a row that ends at its motion and vote, dated by the
    day it was entered where that is a day its journal covers; else None."""
    created = r.get("created")
    vol, _page = cite_of(r.get("desc"))
    if (not FLOOR_UNDATED.match(ev["_raw"] or "") or not isinstance(created, datetime)
            or created == datetime.min
            or created.date() not in VOLUME_DAYS.get((r.get("body"), vol, created.year), ())):
        return None
    line = re.sub(r"\s*\[&\]\s*$", "", ev["_raw"])
    got = dict(PATTERNS)["floor"].search(f"{line} {created:%m/%d/%Y}")
    return {**got.groupdict(), "_type": "floor", "_raw": ev["_raw"]} if got else None


# A COMMITTEE'S AMENDMENT IS VOTED AFTER THE REPORT THAT CARRIES IT, AND
# BEFORE THE PASSAGE THAT TAKES IT. All three are dated the day of the floor's
# vote, and told in the order the clerk entered them. HB 154 of 2025's
# "Committee Amendment # 2025-1828s, AA, VV; 05/08/2025" carries an entry
# stamp of 28 March (Docket.txt line 6880), a month before the Senate
# committee's report of 30 April that recommends it; HB 658 of 2025's
# "Committee Amendment # 2025-1642s, AA, VV; 05/01/2025" was entered two hours
# after "Ought to Pass with Amendment #2025-1642s, MA, VV; Refer to Finance
# Rule 4-5", and told on the floor after it the amendment read as adopted
# once the bill had gone to Finance. In the order the history tells them, a
# committee's amendment goes after its chamber's report of the same day
# naming its number, and before its chamber's passage of that day naming it.
def amendment_after_report(evs):
    """The bill's events, each committee's amendment told between the report
    that carries it and the passage that takes it (above)."""
    out = list(evs)
    for e in list(out):
        if (e["cancelled"] or e["_type"] != "amendment"
                or "committee" not in (e.get("what") or "").lower()):
            continue
        mine = amend_keys(e.get("num"))[:1]
        if not mine:
            continue

        def names(r, key):
            return any(same_amendment(mine[0], k) for k in amend_keys(r.get(key)))

        i = out.index(e)
        later = [j for j, r in enumerate(out) if j > i and r["_type"] == "report"
                 and not r["cancelled"] and r["body"] == e["body"]
                 and r["when"].date() == e["when"].date() and names(r, "amend")]
        if later:
            out.insert(max(later), out.pop(i))
            continue
        passed = [j for j, r in enumerate(out) if j < i and r["_type"] == "floor"
                  and not r["cancelled"] and r["body"] == e["body"]
                  and r["when"].date() == e["when"].date()
                  and PASSAGE.match(split_mover(r.get("action"))[0]) and names(r, "_raw")]
        if passed:
            out.insert(min(passed), out.pop(i))
    return out


# A SENTENCE OF THE FLOOR TOLD AGAIN. collapse() drops a sentence a stage
# repeats word for word, which is right for one action the clerk entered
# twice -- HB 154 of 2025's committee amendment has two identical rows -- and
# drops the second of two votes that happened: HB 1384 of 2026's Senate
# adopted floor amendment 2026-1928s and passed the bill, reconsidered both,
# and did each again, and the history told each once. Where the chamber told
# something else in between, the repeat happened again and says so
# (told_again); where it did not, it is the one action entered twice, and is
# not told twice.
AGAIN_AMENDMENT = re.compile(r" was (adopted|rejected|withdrawn|offered|proposed)\b")


def told_again(s, ev, told, last):
    """`s` as the history tells it, given `told`, the floor and amendment
    sentences of ev's chamber told so far, and `last`, the history's last
    sentence: None for a repeat of the last, "again" put in for a repeat of an
    earlier one, else `s`. Not for an amendment the row gives no number: two
    of those are not one told twice."""
    if not s or s not in told or (ev["_type"] == "amendment" and not (ev.get("num") or "").strip()):
        return s
    if last == s:
        return None
    if ev["_type"] == "amendment":
        return AGAIN_AMENDMENT.sub(r" was \1 again", s, count=1)
    chamber = f"the {CHAMBER.get(ev['body'], 'House')} "
    return s.replace(chamber, chamber + "again ", 1) if chamber in s else s


def notice_note(ev):
    """What the bill's list of docket lines says beside a meeting row that
    build() tells as a notice and not as a meeting.

    The list is headed "every action the General Court recorded", and it left
    these rows out as it leaves out a row the docket cancelled -- which the
    docket did not do to them. HB 273 of 2017's note said "Its docket has two
    rows" over a list of one. The row is shown, and this says why the history
    does not tell it as a sitting: the journal's word (HB 273's "Public
    Hearing: 01/10/2017 01:30 PM LOB 306"), the withdrawal that came first
    (HB 1284 and HB 1512 of 2012), or, where neither names the day, that the
    bill was never introduced."""
    if ev.get("_journal"):
        return ("A notice, for a bill the House did not introduce. No record on this "
                "site says whether it was held.")
    if ev.get("_void") == "withdrawn":
        return "A notice. The bill was withdrawn before the day it names."
    if ev.get("_void") == "taken":
        return (f"A notice. The {CHAMBER_NAME.get(ev.get('body'), 'chamber')} took the "
                "measure from the committee before the day it names.")
    if ev.get("_void") == "reported":
        return "A notice. The committee reported the bill before the day it names."
    if ev.get("_whole_day"):
        return ("A notice. The docket cancels this meeting for most of the bills it was set "
                "for, and the calendars printed after this bill was set down for another "
                "meeting no longer print it.")
    if ev.get("_void") == "cancelled":
        return "A notice. A later row of the docket cancels the meeting it names."
    if ev.get("_void") == "moved":
        return (f"A notice. A later row of the docket moves the "
                f"{VOIDED_KIND.get(ev.get('_type'), 'hearing')} to another day.")
    return "A notice, for a bill that was never introduced."


# A MEETING A LATER ROW OF THE DOCKET CANCELLED OR MOVED WAS NOT HELD
# (6 October 2026; the person's word on decision 56). The docket keeps the
# notice and adds a row after it, and the history told the notice as a
# meeting held:
#
#   - CANCELLED BY A LATER ROW. "Public Hearing: 1/15/2013 2:00 PM LOB 301"
#     and, the next morning, "===CANCELLED=== Public Hearing: 1/15/2013 2:00
#     PM LOB 301" (HB 114 of 2013, whose history said the committee held
#     public hearings on 15 and 22 January). The House from 2007 cancels a
#     meeting that way, and the Senate's "Hearing; === CANCELLED === January
#     19, 2006" (SB 339 of 2006; Senate Calendar 2 prints "SB 339, HAS BEEN
#     CANCELLED AND WILL BE RESCHEDULED FOR A LATER DATE") is the same. A
#     later cancelled row of the same chamber, kind and day, at the same time
#     within five minutes where both state one; and for an executive or work
#     session, in the same room and of the same session where both name one,
#     since two of one day are two meetings ("Sales Tax" and "Casino"
#     subcommittees of HB 145 of 2007, at 1:00 in rooms 202 and 207 of the
#     Legislative Office Building). And not where a notice for the same
#     day was entered after the cancellation: the meeting only moved to
#     another hour and sat that day (HB 142 of 2015's hearing of 12 February,
#     moved from one o'clock to ten), and the history tells it once.
#   - MOVED BY A LATER ROW, for a public hearing only. The House's docket of
#     2005-2006 marks the notice it moved -- "===RESCHEDULED===Public Hearing
#     Jan 31 11:00 RM 306 LOB" and then "Public Hearing Feb 9 10:00" (HB 1696
#     of 2006; House Calendar 8 prints "Rescheduled public hearing on HB
#     1696-FN" under 9 February) -- and so does the House's "==POSTPONED=="
#     of the storm of 27 January 2015. The Senate and the dockets before 2000
#     mark the new notice instead: "Hearing; === RESCHEDULED === February 22,
#     2006", entered on 8 February over SB 339's notice for 15 March;
#     "RESCHEDULED HEARING 3/27/89" over HB 228's for the 22nd. Either mark,
#     and a later notice for another day entered by the day the first one
#     named. Not a continuation ("Continued", "RECONVENE", "RECESSED":
#     the hearing sat and went on another day). An executive or work session
#     recurs -- a committee that meets every Tuesday notices the next Tuesday
#     before this one (HB 607 of 2005) -- so it has a rule of its own
#     (_session_moved_by, below), which asks the calendars.
#
#     AND ONLY A LATER NOTICE THAT IS ITSELF A MEETING, on the evidence of the
#     rows (7 October 2026). A move now takes a hearing out of the history, so
#     a held hearing read as moved disappears from it, and the House
#     calendars found five that had:
#       - a later row that is itself cancelled is no meeting the first one
#         moved to. HB 462 of 2015's "==RESCHEDULED== Public Hearing:
#         2/13/2015 10:00 AM" was read as moved by "===CANCELLED=== Public
#         Hearing: 2/12/2015 11:00 AM", the copy of the notice it replaced
#         (House Calendar 13 prints HB 462 at 10:00 on 13 February); HB 1626
#         of 2006's "===RESCHEDULED===Public Hearing Jan 17" by
#         "===CANCELLED===Public Hearing Jan 24" (House Calendar 6: "11:00
#         a.m. Rescheduled public hearing on HB 1626-FN-A" on 17 January).
#       - no day the docket itself notices a continued hearing on is a day
#         the first one moved to. HB 2014 of 2014's rows set "Continued Public
#         Hearing: 2/11/2014 10:00 AM" before "==RESCHEDULED== Public Hearing:
#         2/11/2014 10:45 AM", and the hearing of 6 February sat (House
#         Calendar 7 prints it at 10:45 that day, and Calendar 9 the 11th as
#         "Continued public hearing on HB 2014"); HB 445 of 2015's
#         "Continued Public Hearing: 2/13/2015 11:00 AM" followed its
#         "==RESCHEDULED==" notice for that day by three hours, and House
#         Calendar 11 prints the hearing on the 12th and again on the 13th.
#         A rescheduling row the docket called off in its turn still moved
#         the notice before it: HB 1334 of 1990's hearing of 15 February went
#         to 8 March by "RESCHEDULED HEARING 3/8/90", which was cancelled and
#         moved again to the 16th.
#       - where the only mark is the first notice's own "rescheduled", a
#         plain notice entered after the hour the first one named is the
#         next meeting, not the same one moved: HB 234 of 2015's "Public
#         Hearing: 2/5/2015 2:00 PM", entered at 4:52 PM on 28 January, after
#         the hearing of 11:15 that morning, which House Calendar 10 calls a
#         "Continued public hearing on HB 234" -- the House of 2013-2016 puts
#         that mark on the notice that replaced another ("==RESCHEDULED==
#         Public Hearing: 1/28/2015", after "==POSTPONED== Public Hearing:
#         1/27/2015"). Entered on the day itself, the row has to state an
#         hour and its stamp has to carry one. A rescheduling row of its own
#         is the clerk's word whatever hour it was typed (overtaken_by).
MOVED_MARK = re.compile(r"=+\s*(?:RESCHEDULED|POSTPONED)\s*=+", re.I)
POSTPONED_MARK = re.compile(r"=+\s*POSTPONED\s*=+", re.I)
RESCHEDULED_MARK = re.compile(r"=+\s*RESCHEDULED\s*=+", re.I)
# The rescheduling row's own words, and the Senate's "=== DATE CHANGE ===",
# which is the same row by another name: "Hearing: === RESCHEDULED ===
# 3/15/11" and then "Hearing: === DATE CHANGE === 3/22/11" (SB 120 of 2011;
# Senate Calendar 15 prints "SB 120 has been rescheduled for March 22nd").
# And the Senate of 1999-2000's other words for it (docket_era_1999.
# RESCHEDULED_TO): "==CANCELED AND RESCHEDULED== Feb.11" (SB 405), "New Date ,
# Feb. 22" (SB 326), "Hearing Rescheduled, 3/16/99" (SB 155).
RESCHEDULING = re.compile(
    r"=+\s*(?:RESCHEDULED|DATE\s+CHANGE|CANCELL?ED\s+AND\s+RESCHEDULED)\s*=+"
    r"|^\W*(?:(?:Public\s+)?Hearing\s*[;:,]?\s*)?RESCHED(?:ULED)?\b(?!\s+TIME)"
    r"|^\W*New\s+Date\s*,",
    re.I)
# A row that gives a notice of the same day a new hour: "Hearing; === TIME
# CHANGE === February 6, 2002" (HB 462 of 2002), "==NEW TIME== Feb.10".
TIME_CHANGED = re.compile(r"\bTIME\s+CHANGE\b|\bNEW\s+TIME\b", re.I)
GOES_ON = re.compile(r"\bCONTINU|\bRECONVEN|\bRECESS", re.I)
# A day the docket notices a hearing carried on from an earlier one: not one
# that recessed, which sat (HJR 22 of 2006's of 23 March).
GOES_ON_DAY = re.compile(r"\bCONTINU|\bRECONVEN", re.I)
MEETING_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
# The hour, with its meridiem where the row gives one.
MEETING_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})\s*(?:([ap])\.?\s?m\b\.?)?", re.I)


# Which session, where a row names one: "Sales Tax Subcommittee Work Session:
# 8/21/07 1:00 PM LOB 202" is not "==CANCELLED==Casino Subcommittee Work
# Session: 8/21/07 1:00 PM LOB 207" (HB 145 of 2007). The room, and the words
# before "Work Session" or "Executive Session" that are not the same for every
# session ("Retained Bill - Subcommittee").
ROOM_SAID = re.compile(r"\b(?:LOB|SH|RM|Room)\W*(\d{2,3})", re.I)
SESSION_SAID = re.compile(r"^(.*?)(?:Work\s*Sess|Exec\w*\.?\s*Sess)", re.I)
SESSION_ANY = re.compile(r"\b(?:ret(?:ained)?|bill|interim|study|subcom\w*|full|committee|"
                         r"continued)\b|[^A-Za-z ]", re.I)


def _session_of(ev):
    m = SESSION_SAID.search(ev.get("_raw") or "")
    return " ".join(SESSION_ANY.sub(" ", m.group(1)).lower().split()) if m else ""


def _room_of(ev):
    m = ROOM_SAID.search(ev.get("_raw") or "")
    return m.group(1) if m else ""


def _meeting_minute(ev):
    """The minute of the half-day a meeting row states (h:mm, with no
    meridiem: "2:15 a.m." for 2:15 p.m. is a slip of SB 348 of 2010's), or
    None."""
    m = MEETING_TIME.search(ev.get("_said") or ev.get("_raw") or "")
    return (int(m.group(1)) % 12) * 60 + int(m.group(2)) if m else None


def _meeting_start(ev):
    """The moment the meeting a row names was to begin -- its day, at the hour
    it states -- or None where it states none. A bare hour from one to six is
    the afternoon's, and so is one typed "a.m." ("2:15 a.m." for 2:15 p.m. is
    a slip of SB 348 of 2010's): no committee sits before seven."""
    m = MEETING_CLOCK.search(ev.get("_said") or ev.get("_raw") or "")
    if not m:
        return None
    h, mi, mer = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if mer == "p" and h < 12:
        h += 12
    elif mer != "p" and 1 <= h <= 6:
        h += 12
    if h > 23 or mi > 59:
        return None
    return datetime(ev["when"].year, ev["when"].month, ev["when"].day, h, mi)


def _entered_ahead(o, ev):
    """Was row `o` entered before the meeting `ev` names? Before its day; or on
    the day, before the hour it states, where `o`'s stamp carries an hour."""
    e = o.get("_entered")
    if not isinstance(e, datetime) or e == datetime.min:
        return False
    day = ev["when"].date()
    if e.date() != day:
        return e.date() < day
    start = _meeting_start(ev)
    return start is not None and (e.hour, e.minute, e.second) != (0, 0, 0) and e < start


def _cancelled_by(ev, evs):
    """Rule (a), above: ("cancelled", the later row that cancels the meeting
    this notice names); ("", None) where a notice for the same day was entered
    after that row, and the meeting sat that day at another hour; else
    (None, None)."""
    day = ev["when"].date()
    # A row that says only "Hearing Cancelled" and names no day
    # (docket_era_1999.cancelled_notice) calls off the bill's hearing it was
    # entered over: of those entered before it, for its day or later, the one
    # entered last. SB 12 of 1999's "Hearing Cancelled" of 16 March is its
    # hearing of 2 April, entered on 10 March, and not that of 17 February.
    for o in evs:
        if (o.get("_cancels_next") and o is not ev and o["body"] == ev["body"]
                and ev["_type"] == "hearing" and _entered_before(ev, o["_entered"])):
            over = [x for x in evs
                    if x["_type"] == "hearing" and x["body"] == o["body"]
                    and not x.get("_cancels") and _entered_before(x, o["_entered"])
                    and x["when"].date() >= o["_entered"].date()]
            if over and max(over, key=lambda x: x["_entered"]) is ev:
                return "cancelled", o
    for o in evs:
        if not (o is not ev and o["body"] == ev["body"] and o["_type"] == ev["_type"]
                and _entered_before(ev, o["_entered"]) and not o.get("_cancels_next")
                and o["cancelled"] and o["when"].date() == day):
            continue
        a, b = _meeting_minute(ev), _meeting_minute(o)
        if ev["_type"] != "hearing" and any(
                x and y and x != y for x, y in ((_session_of(ev), _session_of(o)),
                                                (_room_of(ev), _room_of(o)))):
            continue
        # THE HOUR A LATER ROW MOVED THIS NOTICE TO (decision 59c, 7 October
        # 2026). "Hearing; February 6, 2002, Room 104, LOB, 3:15 p.m.; SC8",
        # then "Hearing; === TIME CHANGE === February 6, 2002, ... 3:45 p.m.;
        # SC8A", then "Hearing; === CANCELLED === February 6, 2002, ... 3:45
        # p.m.; SC9", and the hearing was held on the 13th, which Senate
        # Calendar 10 prints (HB 462 and HB 560 of 2002): the cancellation is
        # of the meeting the first notice set, at the hour the second gave it,
        # and the history went on telling the hearing of the 6th.
        if a is not None and b is not None and abs(a - b) > 5 and any(
                x is not ev and x["body"] == ev["body"] and x["_type"] == ev["_type"]
                and x["when"].date() == day and TIME_CHANGED.search(x.get("_said") or "")
                and _entered_before(ev, x["_entered"]) and _entered_before(x, o["_entered"])
                and _meeting_minute(x) is not None and abs(_meeting_minute(x) - b) <= 5
                for x in evs):
            a = b
        if a is None or b is None or abs(a - b) <= 5:
            # Unless the day's meeting was only moved to another hour: a
            # notice for the same day entered after the cancellation is the
            # meeting that sat, and the history tells it once.
            if any(x["_type"] == ev["_type"] and x["body"] == ev["body"]
                   and not x["cancelled"] and x["when"].date() == day
                   and _entered_before(o, x["_entered"]) for x in evs):
                return "", None
            return "cancelled", o
    return None, None


def overtaken_by(ev, evs):
    """("cancelled" or "moved", the row that did it) where a later row of the
    docket cancelled or moved the meeting this notice names (the rules
    above); else ("", None)."""
    if (ev["_type"] not in ("hearing", "exec", "worksession") or ev["cancelled"]
            or ev.get("_void") or ev.get("recessed")):
        return "", None
    why, o = _cancelled_by(ev, evs)
    if why is not None:
        return why, o
    if ev["_type"] != "hearing":
        o = _session_moved_by(ev, evs)
        return ("moved", o) if o is not None else ("", None)
    day = ev["when"].date()
    for o in evs:
        if (o is ev or o["body"] != ev["body"] or o["_type"] != ev["_type"]
                or not _entered_before(ev, o["_entered"])
                or o["cancelled"] or o.get("recessed") or o["when"].date() == day
                or GOES_ON.search(o.get("_said") or o["_raw"])
                or (o["_entered"].date() > day and not _moved_after(o, day))
                or any(x["body"] == ev["body"] and x["_type"] == ev["_type"]
                       and x["when"].date() == o["when"].date()
                       and GOES_ON_DAY.search(x.get("_said") or x["_raw"]) for x in evs)):
            continue
        # The clerk's rescheduling row naming the new day, or this notice
        # marked postponed, whenever that day the row was typed: Senate
        # Calendar 15 of 1999, of 23 March, prints SB 191's hearing on the
        # 31st "RESCHEDULED FROM MARCH 24TH", and the docket's row for it was
        # typed at 10:05 on the 24th. A mark of "rescheduled" on this notice
        # alone, which in the House of 2013-2016 marks the notice that
        # replaced another, only where the later one was entered before the
        # meeting this one names (HB 234 of 2015, above).
        if (RESCHEDULING.search(o.get("_said") or "")
                or POSTPONED_MARK.search(ev.get("_said") or "")
                or (MOVED_MARK.search(ev.get("_said") or "") and _entered_ahead(o, ev)
                    and not _replaces_unmarked(ev, evs))):
            return "moved", o
    return "", None


# THE SENATE OF 2000 TYPED SOME MOVES THE DAY AFTER. Its hearings of 25
# January 2000 were moved on rows entered on the 26th -- "==RESCHEDULED==
# Feb.15,Room 104,LOB,3:30 p.m." (SB 387) -- and those of 3 February on the
# 7th ("=RESCHEDULED= Feb. 17", SB 373 and SB 396); Senate Calendar 10 prints
# "SB 381-FN, CACR 38, & SB 387-FN-L HAVE BEEN RESCHEDULED FROM JANUARY 25TH",
# SB 378, SB 404 and SB 416 "RESCHEDULED FROM JANUARY 25TH", and SB 373 and SB
# 396 "RESCHEDULED FROM FEBRUARY 3RD". A later notice entered after the day
# is otherwise the next meeting, not the same one moved (overtaken_by); a row
# whose only reading is the move (docket_era_1999.rescheduled_notice), typed
# within a week of the day, is the move.
MOVED_LATE_DAYS = 7


def _moved_after(o, day):
    """Is `o`, entered after `day`, the clerk's row moving that day's hearing?"""
    return (o.get("_era") == "1999:rescheduled"
            and 0 < (o["_entered"].date() - day).days <= MOVED_LATE_DAYS
            and bool(RESCHEDULING.search(o.get("_said") or "")))


def _replaces_unmarked(ev, evs):
    """Is this notice, marked "rescheduled", the one that replaced an earlier
    notice for another day that carries no such mark? Then the mark is the
    House's of 2013-2016, on the new notice ("Public Hearing: 2/6/2014" and
    then "==RESCHEDULED== Public Hearing: 2/13/2014", HB 1586 of 2014; or after
    "==POSTPONED==", HB 234 of 2015), and says nothing of a later move. The
    House of 2005-2006 marks the notice it moved, the first one (HB 1696 of
    2006) or each in turn (HB 1345 of 2006: "===RESCHEDULED===Public Hearing
    Jan 11" and "===RESCHEDULED===Public Hearing Jan 19", then the 25th, which
    House Calendars 4 and 6 print as "Rescheduled public hearing")."""
    day = ev["when"].date()
    prior = [x for x in evs if x is not ev and x["body"] == ev["body"]
             and x["_type"] == ev["_type"] and not x["cancelled"]
             and x["when"].date() != day and _entered_before(x, ev["_entered"])]
    return bool(prior) and not any(RESCHEDULED_MARK.search(x.get("_said") or "") for x in prior)


def overtaken(ev, evs):
    """"cancelled" or "moved" where a later row of the docket cancelled or
    moved the meeting this notice names (overtaken_by); else ""."""
    return overtaken_by(ev, evs)[0]


# AN EXECUTIVE OR WORK SESSION THE DOCKET MARKS AND SETS DOWN FOR A LATER DAY
# (the launch audit of 7 October 2026, cause 6). Education Funding's sessions
# of 4 November 2025 are "==RESCHEDULED== Executive Session: 11/04/2025 02:00
# pm GP 232" on fourteen bills (HB 729's is Docket.txt line 11574), and on 28
# October the docket set each down plainly for 13 November (line 11662).
# House Calendar 45 of 31 October has no Tuesday 4 November and prints the
# sessions under Thursday 13 November; the histories said the committee met
# on both days. A session is moved where
#   - its own notice carries the mark (MOVED_MARK: the docket's own word);
#   - a notice of the same chamber, kind and session for a LATER day, not
#     itself cancelled, recessed or a continuation, was entered after it and
#     before its day (not on the day: HB 1377 and HB 1643 of 2026's of 2
#     March were re-noticed for the 3rd at 2:19 that afternoon, which leaves
#     whether the 10:00 session sat to the docket's mark, as decision 57
#     does for HB 1586 of 2014);
#   - and the mark is "==POSTPONED==", the clerk's word that it did not sit
#     (the storm of 27 January 2015), or the calendars say so.
# "==RESCHEDULED==" alone is not enough: the House of 2007, of 2013-2016 and
# of 2025-2026 also puts it on the notice that replaced another. Ways and
# Means' "Casino & Gambling" subcommittee of 2007 had marked notices for 23 and
# 30 October (Docket_db_2007-2008.txt lines 13964 and 13966), and House
# Calendar 64 of 18 October prints both as "Rescheduled ... work session"; HB
# 1300 of 2026's marked session of 27 January sat, and the recording shows
# the chair open it. So a calendar printed after the later notice was entered
# and before the day must print the committee's session of that kind on the
# later day and none on this one -- at this hour, or for this bill
# (_calendars_moved). Where no calendar was printed in between, the session is
# told as held, as before.
def _session_moved_by(ev, evs):
    """The later notice an executive or work session was moved to by the
    rule above, or None."""
    if not MOVED_MARK.search(ev.get("_said") or ""):
        return None
    day = ev["when"].date()
    for o in evs:
        if (o is ev or o["body"] != ev["body"] or o["_type"] != ev["_type"]
                or o["cancelled"] or o.get("recessed") or o["when"].date() <= day
                or not _entered_before(ev, o["_entered"])
                or not isinstance(o.get("_entered"), datetime)
                or o["_entered"].date() >= day
                or GOES_ON.search(o.get("_said") or o["_raw"])
                or any(x and y and x != y for x, y in (
                    (_session_of(ev), _session_of(o)),
                    (_session_of_kind(ev), _session_of_kind(o))))):
            continue
        if POSTPONED_MARK.search(ev.get("_said") or "") or _calendars_moved(ev, o, evs):
            return o
    return None


# A session the rule above asked the calendars about and could not, because no
# calendar of its chamber and term was read: (term, chamber, committee, day).
# main() says them, and stops where the calendars broke (CALENDAR_UNREAD), as
# whole_day_unchecked() does: a rule that turns itself off says so.
MOVED_UNCHECKED = set()


def _calendars_moved(ev, o, evs):
    """Do the calendars printed after `o` was entered and before the day `ev`
    names print the committee's session of that kind on o's day, and none on
    ev's at its hour or for this bill? False where none was printed then."""
    term = ev.get("_term") or TERM
    k = _meeting_key(ev, evs, term)
    cmte = k[2] if k else ""
    every = _calendar_rows(ev["body"], term)
    if not every:
        MOVED_UNCHECKED.add((term, ev["body"], cmte, ev["when"].date().isoformat()))
        return False
    kind = CALENDAR_KIND[ev["_type"]]
    since, day = o["_entered"].date().isoformat(), ev["when"].date().isoformat()
    bill, at = (ev.get("_bill") or "").upper(), _clock(ev)
    rows = [r for r in every
            if since < (r.get("noticed") or "") < day
            and kind in (r.get("kind") or "").lower()
            and ((cmte and r.get("committee") == cmte) or _calendar_bill(r.get("bill")) == bill)]
    return (any(r["date"] == o["when"].date().isoformat() for r in rows)
            and not any(r["date"] == day and (
                _calendar_bill(r.get("bill")) == bill or not at or not r.get("time")
                or P.same_minute(at, r.get("time"))) for r in rows))


def _cancelled_twin(ev, evs):
    """Is there a row of the same chamber and kind, in the same words, entered
    at the same moment and after this one in the docket, that the clerk's own
    mark calls off (build(), on HB 355 of 2022)?"""
    stamp = ev.get("_entered")
    if not isinstance(stamp, datetime):
        return False
    # After ev in evs, which build() has put in the order the rows were
    # entered within a day (day_order, hold_in_order).
    after = False
    for o in evs:
        if o is ev:
            after = True
        elif (after and o["cancelled"] and not o.get("_void")
              and o["body"] == ev["body"] and o["_type"] == ev["_type"]
              and o.get("_raw") == ev.get("_raw") and o.get("_entered") == stamp):
            return True
    return False


# WHAT A VOIDED NOTICE LEAVES OFF IS ITS MEETING, NOT ITS DAY (7 October 2026).
# The day of a notice a later row cancelled or moved was carried out of build()
# whole, and only where nothing the history tells fell on it, since
# proceedings.notice_only read a day. So 33 of the 541 such notices kept their
# meeting wherever the bill had anything else that day, in either chamber: HB
# 1288 of 1990's Senate hearing of 8 March, cancelled and held on the 6th, was
# still a station, a row of the download and a day Senate Education "met ...
# for a hearing on HB 1288-FN", because the Senate passed the bill on the 8th;
# and Finance "met on February 18, 2014 for public hearings on HB 435-FN, HB
# 461-FN, HB 525-FN and HB 650-FN-A", whose hearing was cancelled that
# afternoon and whose work session that day, moved to one o'clock, was held.
# Each is now carried as the meeting it was -- day, chamber, kind and hour --
# and notice_only leaves off the row of the table that is that meeting and
# keeps the rest of the day.
#
# NOT WHERE THE TABLE'S ROW COULD BE A MEETING THE HISTORY TELLS: one of the
# same chamber and kind that day at the same hour, or of the same kind of
# session at any hour, since the table keeps one row of a kind a day and
# gives it the first notice's hour. HB 1132 of 2002's Senate hearing set for
# 8:30 on 19 March was moved to the 7th, called off, and noticed again for
# 8:45 on the 19th, when it was held; the table's one row of that day says
# 8:30. A work session of another kind is another row: HB 2014 of 2014's work
# session of 11:00 on 11 February, cancelled, is the table's "work session"
# at 11:00, and the full committee's at 11:15 that it held is its own.
VOIDED_KIND = {"hearing": "hearing", "exec": "executive session",
               "worksession": "work session"}


def _clock(ev):
    """"10:00", the hour a meeting row states, or ""."""
    s = _meeting_start(ev)
    return s.strftime("%H:%M") if s else ""


def _session_of_kind(ev):
    """Which work session a row names, as the table tells them apart
    (docket_parser): a subcommittee's, the full committee's, or neither."""
    if ev["_type"] != "worksession":
        return ""
    k = (ev.get("_said") or ev.get("_raw") or "").lower()
    if re.search(r"\bsub-?comm?", k):
        return "sub"
    if re.search(r"\bfull\s+comm", k):
        return "full"
    return ""


def _time_changed_clock(e, evs):
    """The hour, "HH:MM", that the last row of the bill in e's chamber entered
    after it and marked TIME CHANGE or NEW TIME gives e's day; else "".

    THE TABLE'S ROW CARRIES THAT HOUR (7 October 2026): docket_parser gives a
    Senate notice of 1999-2006 the hour such a row gives its day
    (TIME_CHANGED_ROW there), so a meeting this history voids is that hour in
    proceedings.csv. SB 387 of 2000's hearing of 25 January, noticed for 3:40,
    set for 3:25 by "==TIME CHANGE== Jan. 25", and moved to 15 February, is
    voided at both. The day the row names is read as docket_parser reads it
    (docket_era_1999.DTXT, full_date)."""
    E = getattr(_VOCAB, "E1999", None)
    if E is None:
        return ""
    day, best = e["_unheld_day"], None
    for x in evs:
        said = x.get("_said") or ""
        if (x is e or x["body"] != e["body"] or not TIME_CHANGED.search(said)
                or not _entered_before(e, x.get("_entered"))):
            continue
        m = re.search(E.DTXT, said, re.I)
        named = E.full_date(m.group(0), x["_entered"], forward=True) if m else None
        if not named or datetime.strptime(named, "%m/%d/%Y").date() != day:
            continue
        at = _clock({"_said": said[m.end():], "when": x["_entered"]})
        if at and (best is None or x["_entered"] >= best[0]):
            best = (x["_entered"], at)
    return best[1] if best else ""


def voided_meetings(evs):
    """[[day, chamber, kind, "HH:MM" or ""]], each meeting a later row of the
    docket cancelled or moved (overtaken) whose row in the table could be no
    meeting the history tells (above), for proceedings.notice_only -- at the
    hour its notice states, and at the hour a later TIME CHANGE row gave it
    (_time_changed_clock), which is the one the table's row carries."""
    told = [e for e in evs
            if not e["cancelled"] and not e.get("_void") and e["_type"] in ROW_MEETINGS]
    out = set()
    for e in evs:
        if not e.get("_unheld_day") or e["_type"] not in VOIDED_KIND:
            continue
        day, said = e["_unheld_day"], _clock(e)
        moved = _time_changed_clock(e, evs) if said else ""
        for at in [said] + ([moved] if moved and moved != said else []):
            if any(t["when"].date() == day and t["body"] == e["body"] and t["_type"] == e["_type"]
                   and (P.same_minute(at, _clock(t)) or _session_of_kind(t) == _session_of_kind(e))
                   for t in told):
                continue
            out.add((day.isoformat(), e["body"], VOIDED_KIND[e["_type"]], at))
    return [list(x) for x in sorted(out)]


# A MEETING THE DOCKET CANCELS ON MOST OF ITS BILLS, AND NO LATER CALENDAR
# PRINTS, WAS CANCELLED FOR ALL OF THEM (decision 58, the person's word of 6
# October 2026). Ways and Means set an executive session for 10:00 on 29
# October 2015 on eleven retained bills, entered on 16 September. The docket
# marks nine of the notices "==CANCELED==", and re-notices them on the 23rd
# "==RESCHEDULED==Executive Session: 10/14/2015 10:00 AM LOB 202"; HB 571's and
# HB 634's notices for the 29th carry no mark, and their own rows of the 23rd
# set them down for the 14th too. House Calendar 53 (18 September) printed the
# session of the 29th on HB 359 and CACR 2; Calendars 55, 56 and 58 print the
# eleven on 14 October, and none printed from 25 September to 23 October
# prints a session of the 29th. The histories of HB 571 and HB 634 said the
# committee "met in executive session on October 14, 2015 and October 29,
# 2015". The whole day was called off, and those two had their meeting on the
# 14th.
#
# THE NARROWEST RULE THAT SAYS SO. A meeting -- the committee that had the
# bill, the chamber, the day, the kind and the hour -- is cancelled for a bill
# whose notice of it the docket left unmarked only where
#   - the docket cancels it, by its own mark or a later row (overtaken), on
#     more than half of the bills it was set for;
#   - every bill it is still told for was set down, after it, for a meeting of
#     the same kind on another day (the meeting it had instead); and
#   - the calendars printed after those notices print that other meeting for
#     each such bill and this one for none of its bills -- and at least one of
#     them is on disk.
# Measured over every term (whole_day.txt in the stage 2b survey) the docket's
# half reaches 46 meetings, and nearly every one sat for the bills it was told
# for: an executive session on 16 February 2012 called off for 17 bills and
# held for 12, Finance's work session of 27 April 2010 held on SB 450, which
# House Calendar 33 prints. The calendars' half leaves this one. Not where
# the calendars say nothing: Judiciary's session of 15 November 2023, cancelled
# on eight of nine bills, is printed for all nine by every calendar on disk up
# to 3 November, and the one after it is a notice of another committee's
# amended session; nor Education Funding's of 2 May 2025, moved on 1 May to
# that afternoon, which no calendar printed in between can show.
WHOLE_DAY = {}
# Every meeting notice the histories built so far read, by meeting
# (_meeting_key): filled by build(), read once by whole_day_meetings().
NOTICED = defaultdict(list)
# {(chamber, term): [calendar_meetings row]}, read from calendars/ and
# calendars_senate/ once a term and only where a meeting asks.
CALENDAR_ROWS = {}
CALENDAR_KIND = {"hearing": "hearing", "exec": "executive", "worksession": "work session"}
# THE RULE DOES NOT TURN ITSELF OFF IN SILENCE (the review of decision 58, 7
# October 2026). Its calendar half read nothing where calendar_meetings could
# not load a term -- an error swallowed, or no calendar on disk for its years
# -- and every meeting whose docket half held was then told as held for its
# unmarked bills, with nothing said: HB 571 and HB 634 of 2015 and SB 92 of
# 2013 would have gone back to telling 29 October with every check green.
# CALENDAR_UNREAD says why a (chamber, term) could not be read, and
# whole_day_meetings() puts in WHOLE_DAY_UNCHECKED each meeting whose docket
# half held and whose term's calendars gave no row at all. main() stops on the
# first kind, which is a failure, and says the second, which is a disk
# without that term's calendars.
CALENDAR_UNREAD = {}
WHOLE_DAY_UNCHECKED = []


def _meeting_key(e, evs, term):
    """(term, chamber, the committee that had the bill, "YYYY-MM-DD", kind,
    the minute of the half-day) for a meeting row, or None where the row
    states no hour or no committee had the bill."""
    held = ""
    for x in evs:
        if x is e:
            break
        if x["body"] == e["body"] and (x.get("committee") or "").strip():
            held = x["committee"].strip()
    minute = _meeting_minute(e)
    if not held or minute is None or e["_type"] not in VOIDED_KIND:
        return None
    return (term, e["body"], committee_said(held, e["body"], term),
            e["when"].date().isoformat(), e["_type"], minute)


def _notice_seen(bill, e, evs, term):
    """Put this notice in NOTICED: whether the history leaves it out as
    cancelled or moved, and the meetings of the same kind the bill was set
    down for on other days after it, before its day."""
    if e["_type"] not in VOIDED_KIND or e.get("_void") in ("withdrawn", "taken",
                                                            "not introduced", "reported"):
        return
    k = _meeting_key(e, evs, term)
    if not k:
        return
    day = e["when"].date()
    NOTICED[k].append({
        "bill": bill, "cancelled": bool(e["cancelled"]),
        "others": [(x["when"].date().isoformat(), x["_entered"]) for x in evs
                   if x is not e and x["_type"] == e["_type"] and x["body"] == e["body"]
                   and not x["cancelled"] and x["when"].date() != day
                   and _entered_before(e, x["_entered"]) and x["_entered"].date() <= day]})


def _calendar_rows(chamber, term):
    """The meetings the chamber's calendars on disk print for the term's
    years, the year before and the year after (calendar_meetings.load)."""
    key = (chamber, term)
    if key not in CALENDAR_ROWS:
        try:
            import calendar_meetings as CM
            years = [int(y) for y in (term or "").split("-") if y.isdigit()]
            CALENDAR_ROWS[key] = CM.load(chamber, years=range(min(years) - 1, max(years) + 2)) \
                if years else []
        except Exception as exc:                    # noqa: BLE001
            CALENDAR_ROWS[key] = []
            CALENDAR_UNREAD[key] = f"{type(exc).__name__}: {exc}"
    return CALENDAR_ROWS[key]


def _calendar_bill(s):
    m = re.match(r"^\s*([A-Z]+)\s*0*(\d+)", str(s or "").upper())
    return f"{m.group(1)}{m.group(2)}" if m else ""


def whole_day_unchecked():
    """(why the run stops, or None; the line it says, or None) for the
    meetings whole_day_meetings() could not hold to the calendars
    (WHOLE_DAY_UNCHECKED): a stop where a term's calendars raised
    (CALENDAR_UNREAD), a line where none is on this disk for the term."""
    broke = sorted({(k[1], k[0]) for k in WHOLE_DAY_UNCHECKED} & set(CALENDAR_UNREAD))
    if broke:
        return ("narrative.py: the calendars could not be read for "
                + "; ".join(f"the {'House' if c == 'H' else 'Senate'} of {t} "
                            f"({CALENDAR_UNREAD[(c, t)]})" for c, t in broke)
                + ", so the meetings the docket cancels on most of their bills there "
                  "cannot be held to them (whole_day_meetings)"), None
    if not WHOLE_DAY_UNCHECKED:
        return None, None
    return None, (f"  whole-day rule not applied: {len(WHOLE_DAY_UNCHECKED)} meeting(s) the "
                  "docket cancels on most of their bills have no calendar on this disk for "
                  "their term, so the bills whose own notice is unmarked are told as the "
                  "docket gives them: "
                  + "; ".join(f"{k[2]} ({'House' if k[1] == 'H' else 'Senate'}), {k[3]}, "
                              f"{VOIDED_KIND[k[4]]} of {k[0]}"
                              for k in sorted(WHOLE_DAY_UNCHECKED)))


def whole_day_meetings(noticed=None, calendar=None):
    """{meeting key: {"told": [bill], "off": [bill], "calendars": [name]}}:
    each meeting the rule above cancels for every bill. `calendar(chamber,
    term)` gives a calendar's rows -- bill, date, kind, noticed, calendar --
    and is _calendar_rows unless a check passes its own."""
    noticed = NOTICED if noticed is None else noticed
    calendar = calendar or _calendar_rows
    out = {}
    WHOLE_DAY_UNCHECKED.clear()
    for k, seen in noticed.items():
        term, chamber, _committee, day, kind, _minute = k
        bills = defaultdict(list)
        for x in seen:
            bills[x["bill"]].append(x)
        off = sorted(b for b, xs in bills.items() if all(x["cancelled"] for x in xs))
        told = sorted(b for b, xs in bills.items() if not all(x["cancelled"] for x in xs))
        if not told or len(off) <= len(told):
            continue
        # The meeting each told bill was set down for instead, and the day
        # every one of them had been.
        instead = {b: [o for x in bills[b] if not x["cancelled"] for o in x["others"]]
                   for b in told}
        if not all(instead.values()):
            continue
        since = max(min(o[1] for o in os_) for os_ in instead.values()).date().isoformat()
        every = calendar(chamber, term)
        if not every:
            WHOLE_DAY_UNCHECKED.append(k)
            continue
        rows = [r for r in every
                if since < (r.get("noticed") or "") < day
                and CALENDAR_KIND[kind] in (r.get("kind") or "").lower()]
        if not rows:
            continue
        mine = set(off) | set(told)
        if any(r["date"] == day and _calendar_bill(r.get("bill")) in mine for r in rows):
            continue
        # The meeting each told bill was set down for instead, printed for the
        # meeting's bills -- this one's, or the others' where the calendar's
        # line is one calendar_meetings does not read every bill of: House
        # Calendar 60 of 2013 prints SB 92 in Commerce's session of 22
        # October beside the twenty bills moved there from the 29th, at a
        # line's end ("credit card fees, SB 92,") its parse passes over.
        shown = []
        for b in told:
            days = {o[0] for o in instead[b]}
            got = sorted({r.get("calendar") or r.get("noticed") for r in rows
                          if _calendar_bill(r.get("bill")) in mine and r["date"] in days})
            if not got:
                break
            shown += got
        else:
            out[k] = {"told": told, "off": off, "calendars": sorted(set(shown))}
    return out


# "Withdraw From Joint Committee (Reps Wallner and Hess): MA VV" (HA 1 of
# 2008): the chamber's vote to take a measure from the committee it is in.
# Not "Per House Rule 50, Withdrawn from Committee" (HB 457 of 2015) or
# "Withdrawn from Committee Without Recommendation" (SB 416 of 2022), which
# are no vote and are followed by the committee's report.
TAKEN_FROM_COMMITTEE = re.compile(r"^\s*Withdraw\s+from\s+(?:the\s+)?(?:Joint\s+)?Committee\b",
                                  re.I)
# A row that sends a bill back to a committee whose name it may not give
# ("Rereferred to Committee, MA, VV"), which sends_to does not read: after it,
# a reconvened hearing may sit again (build(), the reported rule).
RECOMMITTED_ROW = re.compile(r"\bRECOMM?IT|\bRE-?\s*REFER", re.I)


# --------------------------------------------------- the committee that has it
#
# A COMMITTEE IS NAMED AS IT WAS, IN THAT CHAMBER AND TERM (3 October 2026).
# The sentences printed the name a row's reader produced, and 3,587 of them,
# in 3,323 histories, named no committee that chamber had that term: "the Fi
# committee" for Finance on 966 (a cut, mended where it is made, above and in
# docket_era_2007), the clerk's "Wildlife" and "St Inst", the reader's
# "Executive Departments and Administration" for the Senate's Executive
# Departments of 1989-1992, "Commerce" for the House's commerce committee of
# 1989-1996, "Finance Committee committee". committee_names.official is the
# one table of what each committee was called when; a name it cannot place is
# printed as the row gives it, as before.
#
# Where the reader's name cannot be placed, the clerk's own words are tried
# (docket_vocab keeps them, "_as_written"), and then each half of a name the
# clerk joined with a slash, where exactly one half is a committee of that
# chamber and term: "REFERRED TO FINANCE/APPROP" and "APPROPRIATION/FINANCE"
# are the 1989 Senate's Finance, which the reader had written "Appropriations"
# -- a committee the Senate did not have until 1993.
JOINT_WORD = re.compile(r"\b(?:joint|jt)\b", re.I)


def committee_placed(name, body, term, written=""):
    """The committee's name in that chamber and term, or "" where neither
    `name` nor the clerk's `written` words are one that committee_names.
    OFFICIAL lists for them."""
    if body not in ("H", "S") or not term:
        return ""

    def placed(s):
        s = re.sub(r"\s+", " ", s or "").strip()
        s = re.sub(r"^(?:the\s+)?Committee\s+on\s+(?=[A-Z])", "", s, flags=re.I)
        got = CN.known(CN.official(s, body, term), body, term) or "" if s else ""
        # A JOINT COMMITTEE IS NOT ONE OF ITS MEMBERS: "Ref to a Jt Comm of
        # Exec Depts & Admin & Fin" (HB 1643 and HB 1645 of 2008) is placed by
        # committee_names on Executive Departments and Administration, and the
        # joint committee's hearing and 25-15 report were headed with it. A
        # joint name is placed only on a committee whose own name is joint.
        return "" if got and JOINT_WORD.search(s) and not JOINT_WORD.search(got) else got

    for s in (name, written):
        got = placed(s)
        if got:
            return got
    for s in (written, name):
        halves = {placed(x) for x in re.split(r"\s*/\s*", s or "") if x.strip()}
        halves.discard("")
        if "/" in (s or "") and len(halves) == 1:
            return halves.pop()
    return ""


def committee_said(name, body, term, written=""):
    """`name` as a heading or a sentence prints it: the committee's own name
    in that chamber and term, or the name as given where nothing places it."""
    n = re.sub(r"\s+", " ", name or "").strip()
    return committee_placed(n, body, term, written) or n


def _named(ev, body, key="committee"):
    """The committee an event names, as describe() prints it."""
    return committee_said(ev.get(key), body, ev.get("_term"),
                          (ev.get("_as_written") or {}).get(key, ""))


def _committee(ev, body, key="committee"):
    """"Finance committee", and "Finance Executive Committee" where the
    committee's own name says it (the Senate's of 1993-1994): never "...
    Committee committee"."""
    n = _named(ev, body, key)
    return n if n.lower().endswith("committee") else f"{n} committee"


# A HISTORY'S STAGE IS HEADED WITH THE COMMITTEE THAT HAS THE BILL. The
# heading carried the last committee a row named -- an introduction, a vacated
# referral, a re-referral -- and nothing else moved it. But a chamber sends a
# bill on to a second committee more often than that, and says so on the row
# of the vote that does it:
#
#   "Ought to Pass: MA, VV; Refer to Finance Rule 4-5; 03/06/2025"   SB 286, 2025
#   "Ought to Pass, MA, VV; Refer to Finance [Rule 26]"              SB 106, 2009
#   "COMM AM, AA VV; PASSED WITH AM AND REF TO APPROP VV"            HB 613, 1993
#   "PASSED/ADOPTED; REF TO APPROP"                                  SB 58, 1989
#   "HB517 is vacated from Judiciary and referred to Finance"       HB 517, 2025
#   "Vacated to Children and Family Law Without Objection"           CACR 2, 2017
#   "RECOMMITTED TO APPROPRIATIONS, REP HAGER MA VV"                 HB 363, 1991
#   "REFERRED TO EXEC DEPTS & ADMIN FOR INTERIM STUDY VV"            HB 357, 1996
#
# Finance's 6-0 report on SB 286 was told under "In Senate committee --
# Executive Departments and Administration", and so were 5,242 sentences of
# 2,680 histories: a second committee's hearing, work, executive session and
# report told as the first's. sends_to() reads where a row sends the bill, and
# build() begins a new stage there, headed with that committee and chamber.
# It changes no event's type and no event's committee: the heading, and the
# referral a passage's sentence tells, and nothing else.
#
# A REFERRAL IS READ ONLY WHERE IT CARRIED, and only to a committee
# committee_names can place: "Pending Motion Refer to Finance Rule 4-5", "Sen.
# Daniels Waived Referral to Finance", "The Chair rescinded Refer to Finance",
# "REF TO FINANCE DECLINED", a clause that lost, a motion whose outcome the row
# does not give. The floor's own reader's `refer` is the exception: it is the
# rule referral after a passage, and where its name cannot be placed -- the
# 1993-1994 Senate's "FIN DIV", whose divisions the person has yet to name --
# the heading stops naming the first committee and names none, until a row
# that names its committee says which.
_SEND_VERB = r"(?P<again>RE-?)?REF(?:E?R+ED|ER|\.)?"
_SEND_BILL = r"(?:(?:HB|SB|HCR|SCR|HJR|SJR|HR|SR|CACR|HA|PET)\s*\d+(?:-[A-Z]+)*\s+)?"
_SEND_TO = r"TO\s+(?:THE\s+COMMITTEE\s+ON\s+)?"
_SEND_NAME = r"(?P<c>[A-Z][A-Za-z&+,'/. \-]*?)"
# The name ends at a bracket either way: "Rule 24 (Refer to Finance)" is how
# the Senate of 1999-2000 wrote its rule referral, on 22 histories.
_SEND_END = (r"(?=\s*(?:[;()\[{<:]|$|,\s*(?:REPS?|SENS?|SENATOR)\b|,?\s*\d|,?\s*[HS]J\s*\d"
             r"|,?\s*\b(?:VV|RC|DV|MA|ML|MF|AA|RULE|UNDER|PER)\b|,?\s*\bDIV(?:ISION)?\b\.?\s*[(\d]"
             r"|\s+FOR\s+(?:INT|STUDY)|\s+WITHOUT\s+OBJ|\s+BY\s+(?:THE\s+)?NEC|\s+IN\s+[A-Z]"
             r"|\s+AND\s+TO\b|\s+DECLINED\b))")
SENDS = [
    # "Inadvertently referred to Election Law and Municipal Affairs and will be
    # referred to Judiciary, MA, VV" (SB 487 and SB 536 of 2020): the second
    # is where it went.
    ("vacated", re.compile(r"\bWILL\s+BE\s+REFERRED\s+" + _SEND_TO + _SEND_NAME + _SEND_END, re.I)),
    # "vacated from Judiciary and referred to Finance", "Vacated to Children and
    # Family Law Without Objection", "VACATE TO MUN & CTY GOVT", "Moved to
    # Vacate HB 225-FN from Finance to Energy and Natural Resources" (2017)
    ("vacated", re.compile(
        r"\bVACAT\w*\s+" + _SEND_BILL + r"(?:FROM\s+[A-Z][^;]*?\s+)?(?:(?:AND|&)\s+)?"
        r"(?:(?:RE-?)?REF(?:E?R+ED|ER|\.)?\s+)?" + _SEND_TO + _SEND_NAME + _SEND_END, re.I)),
    ("recommitted", re.compile(
        r"\bRECOMM?IT\w*\s+" + _SEND_BILL + r"(?:BACK\s+)?" + _SEND_TO + _SEND_NAME + _SEND_END, re.I)),
    # "REFERRED TO CRIM JUST & PSFTY FOR INTERIM STUDY", "REFERRED FOR MUN &
    # CNTY GOVT FOR INTERIM STUDY", "ref to Executive Dept and Admin. for
    # Interim Study"
    ("study", re.compile(
        r"\b" + _SEND_VERB + r"\s+(?:TO|FOR)\s+\(?" + _SEND_NAME
        + r"\)?\s+(?:FOR\s+)?(?:INT(?:ERIM)?\.?\s+)?STUDY\b", re.I)),
    # "PASSED W/AM & REFERRED TO APPROP", "Refer to Finance [Rule 24]",
    # "Moved to refer SB 287 back to Energy and Natural Resources" (2020),
    # "Rerefer to the Committee on Health and Human Services" -- and without
    # the "to", which a name committee_names places must then follow: "ref
    # Finance  HJ 33, pg 1881" (SB 262 and seven more of 2006), "Refer Finance
    # [Rule 26]" (SB 324 of 2008).
    ("referred", re.compile(
        r"\b" + _SEND_VERB + r"\s+" + _SEND_BILL + r"(?:BACK\s+)?(?:" + _SEND_TO + r")?" + _SEND_NAME
        + _SEND_END, re.I)),
]
# "REFERRED TO (JOINT COMMS) INTERIM STUDY VV" (HB 442 of 1994): two
# committees together, and no one of them. The heading names neither.
_SEND_JOINT = re.compile(r"^\(?\s*(?:a\s+)?(?:joint|jt)\b", re.I)
# And a row that vacates a referral, "Vacated ref to Executive Dept &
# Administration, MA, VV" (SB 295 of 2006, the bill then "ref to Commerce" on
# a row of its own), sends it to no committee: not to the one it names.
VACATES_REFERRAL = re.compile(r"\bVACAT\w*\s+REF(?:ERENCE|ERRAL)?\b\.?\s*TO\b", re.I)
_SEND_SKIP = re.compile(r"\bPending\s+Motion\b|\bNot\s+Voted\s+On\b|\brescind|\bwaive|"
                        + VACATES_REFERRAL.pattern, re.I)
# What a clause refers that is not the bill: "REMAINING AMS REF TO RULES" (HR 1
# of 1993).
_SEND_NOT_THE_BILL = re.compile(r"\b(?:AMS|AMENDMENTS?)\s+$", re.I)
_SEND_LOST = re.compile(r"\b(?:ML|MF|AL|AF)\b|\bfail|\blost\b|\bdeclin", re.I)
_SEND_MOVED = re.compile(r"\bmove[ds]?\b|\bmotion\b", re.I)
_SEND_CARRIED = re.compile(r"\b(?:MA|AA)\b|\badopted\b|\bwithout\s+objection\b", re.I)
_SEND_NOT_A_NAME = re.compile(
    r"^(?:the\s+)?(?:(?:full|same|standing)\s+)?(?:comm(?:ittee)?s?|int(?:erim)?\.?(?:\s+study)?"
    r"|study|table|(?:third|3rd)\s+reading|cons(?:ent)?\b.*|calendar|sub-?comm\w*"
    r"|committee\s+of\s+conf\w*|conf\w*\s+comm\w*|joint\s+comms?)$", re.I)


def _sent_name(raw):
    n = (raw or "").strip(" ,.-/")
    n = re.sub(r"^(?:the\s+)?committee\s+(?:on\s+)?(?=[A-Z])", "", n, flags=re.I).strip(" ,.-/")
    return "" if not n or _SEND_NOT_A_NAME.match(n) else n


PASSAGE = re.compile(r"^\s*(?:ought\s+to\s+pass|pass|adopt)", re.I)
# The passage the referral follows, in the row's own words.
PASSED_WORDS = re.compile(r"\bPASS(?:ED)?\b|\bADOPTED\b|\bOTP\b", re.I)
SUSPENDS_RULES = re.compile(r"\bSUSP\w*\.?\s+(?:OF\s+)?(?:THE\s+|ALL\s+)?(?:HOUSE\s+|SENATE\s+)?RULES?\b", re.I)
# "The Chair Rescinded Refer to Finance Rule 4-5", "Sen. Daniels Waived
# Referral to Finance", "Rescind Order to the Committee on Finance".
REFERRAL_UNDONE = re.compile(
    r"\b(?:rescind(?:ed)?|waived?)\s+(?:the\s+)?(?:refer(?:ral)?\b|order\s+to\s+the\s+committee)", re.I)
# A REFERRAL THE COMMITTEE'S CHAIR WAIVED, under House Rule 47(f) (46(f)
# until 2019), every wording of it on disk: "Referral Waived by Committee
# Chair per House Rule 47(f)" (HB 1574 of 2026; the House Journal prints it
# "REFERRAL DECLINED ... declined the referral"), "Second Committee Referral
# Waived by Committee Chair", "Speaker Waived Second Committee Referral" (HB
# 407 of 2015), "Declination of Referral Under House Rule 46(f) (Rep
# Wallner)", "Referral declined by Chair of Ways and Means per House Rule 46
# (f)", and the 1995 clerk's "REF TO FINANCE DECLINED, ORDERED TO 3RD
# READING" (HB 126 of 1995), a week after the passage that made it. And two
# the release check's review found by a looser search: "Committee Refused
# Referral; HJ41, PG.1421" (SB 166 of 2013, where the journal prints
# "REFERRAL DECLINED"), and a referral undone the afternoon it was made,
# "Referral to Ways and Means withdrawn  HJ 19a, pg 1176" (HB 1679 of 2006).
REFERRAL_WAIVED = re.compile(
    r"\bReferral\s+(?:Waived|Declined)\b|\bDeclination\s+of\s+Referral\b"
    r"|\bWaived\s+Second\s+Committee\s+Referral\b|\bRefused\s+Referral\b"
    r"|\bReferral\s+to\s+(?P<w>[A-Z][A-Za-z&,'. ]*?)\s+withdrawn\b"
    r"|\bREF(?:ERRAL)?\s+TO\s+(?P<c>[A-Z][A-Za-z&,'. ]*?)\s+DECLINED\b", re.I)
WAIVED_BY_CHAIR = re.compile(r"\bChair(?:man)?\s+of\s+(?P<c>[A-Z][A-Za-z&,'. ]*?)\s+per\b", re.I)
HOUSE_RULE_CITED = re.compile(r"\bHouse\s+Rule\s*(?P<n>\d+)\s*\(\s*(?P<p>[a-z])\s*\)", re.I)


def waiver_said(w, referral=None):
    """The sentence for `w`, a row REFERRAL_WAIVED reads: who gave the
    referral up, in the row's own verb and under the rule it cites. With
    `referral`, the sentence that told the referral, without its full stop,
    the waiver is told as the end of it; without, on its own."""
    raw = w.get("_raw") or ""
    verb = ("waived" if re.search(r"waiv", raw, re.I) else "refused" if re.search(r"refus", raw, re.I)
            else "withdrawn" if re.search(r"withdr", raw, re.I) else "declined")
    rule = HOUSE_RULE_CITED.search(raw)
    rule = f" under House Rule {rule.group('n')}({rule.group('p').lower()})" if rule else ""
    if re.search(r"\bSpeaker\b", raw, re.I):
        who = "the Speaker"
    elif re.search(r"\bChair", raw, re.I):
        who = "chair"
    else:
        who = ""
    if referral:
        tail = (f", whose chair {verb} the referral" if who == "chair"
                else f", and {who} {verb} the referral" if who
                else f", and the referral was {verb}")
        return f"{referral}{tail}{rule}."
    said = ("The committee's chair" if who == "chair" else who[:1].upper() + who[1:]
            if who else "")
    return (f"{said} {verb} the referral{rule}." if said
            else f"The referral was {verb}{rule}.")


def sends_to(ev, term):
    """Where this row sends the bill, as (how, the committee, placed, where in
    the row it is named) -- how is "rule" for the floor reader's own `refer`,
    "joint" for joint committees (no committee is named), else the form read
    off the row ("referred", "rereferred", "vacated", "recommitted", "study"),
    and placed whether committee_names could name it -- or None where it sends
    it nowhere or the row does not say that it carried. A row that sends the
    bill twice sends it where it says last: "RE-REFERRED TO EXEC DEPTS+ADMIN,
    SEN LAMIRANDE MA VV; SEN BOURQUE SUSP RULES TO RE-REF TO WILDLIFE&REC, MA
    2/3VV; RE-REFERRED TO WILDLIFE & REC, MA VV" (SB 165 of 1994)."""
    t, body = ev.get("_type"), ev.get("body")
    if body not in ("H", "S") or t not in ("floor", "amendment", "other"):
        return None
    raw = ev.get("_raw") or ""
    if _SEND_SKIP.search(raw) or ev.get("_unsent"):
        return None
    motion = (ev.get("motion") or "").upper()
    if t == "floor" and motion in ("ML", "MF"):
        return None
    if t == "floor" and ev.get("refer"):
        n = _sent_name(ev["refer"])
        placed = committee_placed(n, body, term,
                                  _sent_name((ev.get("_as_written") or {}).get("refer")))
        return ("rule", placed or n, bool(placed), len(raw)) if n else None
    forms = SENDS[:1] if re.search(r"\binadvertent", raw, re.I) else SENDS
    best = None
    for how, rx in forms:
        for m in rx.finditer(raw):
            # Joint only where the row says the bill went TO them: "RE-REF
            # JOINT WORK SESSION WITH LABOR COMM" (HB 190 of 1990) is a
            # meeting's notice.
            joint = bool(_SEND_JOINT.match(m.group("c"))
                         and re.search(r"\bTO\s+\(?\s*$", raw[:m.start("c")], re.I))
            name = "" if joint else _sent_name(m.group("c"))
            if not (name or joint) or _SEND_NOT_THE_BILL.search(raw[:m.start()]):
                continue
            a = raw.rfind(";", 0, m.start()) + 1
            z = raw.find(";", m.end())
            clause = raw[a:z if z >= 0 else len(raw)]
            if _SEND_LOST.search(clause):
                continue
            if _SEND_MOVED.search(clause) and not _SEND_CARRIED.search(raw):
                continue
            if joint:
                got = ("joint", "", False)
            else:
                placed = committee_placed(name, body, term)
                if not placed:
                    continue
                got = ("rereferred" if how == "referred" and m.group("again") else how,
                       placed, True)
            if best is None or m.start("c") > best[3]:
                best = got + (m.start("c"),)
    return best


# A ROW THAT NAMES ITS OWN COMMITTEE. The 1989-1998 clerk ended a meeting's
# row with the committee that sat -- "HEARING 3/28/89 10:00 RM100,SH FOR:
# APPROPRIATIONS" -- and the finance committees' reports open with their name,
# "FIN MAJ REPORT OTP FOR JAN29 (VOTE 19-0;CC)", "Fin Maj Report OTP/AM".
# Where the heading names no committee -- the 1993-1994 Senate's "FIN DIV",
# whose divisions the record does not let it name -- the first row that names
# one says which, and holds from there: "HEARING APR06 ... FOR: CAP BUDGET".
# A row that names a committee of that chamber and term other than the one
# holding the bill is a record that cannot say whose the work is, and from
# that row the heading names the chamber alone (build()): it had been headed
# with the one it names, for that row only, and the clerk's "FOR: INSUR" on a
# continued hearing of Internal Affairs (HCR 25 of 1998) became Insurance's,
# and a hearing the House Journal gives, with its report, to Criminal Justice
# (HB 163 of 1997) a stage between two of Commerce's. A joint meeting names no
# one committee (ROW_JOINT).
ROW_FOR = re.compile(r"\bFOR\s*:\s*(?P<c>[A-Z][A-Za-z&+,'/. \-]*?)\s*$", re.I)
ROW_MONEY = re.compile(
    r"^(?:(?:RE-?REF\w*|INT(?:ERIM)?\.?\s+STUDY|RESCHED\w*|CONTINUED)\s+)?"
    # "FIN EXEC COMM REPORT REF FOR STUDY MAR22" (SB 732 of 1994): the 1993
    # Senate's Finance Executive Committee, a name committee_names places.
    r"(?:(?:MAJ|MIN)\w*\.?\s+)?(?P<c>FIN(?:ANCE)?(?:\s+EXEC\w*)?|APPROP\w*|W\s*&\s*M|WAYS\s*(?:&|AND)\s*MEANS"
    r"|CAP(?:ITAL)?\s+BUDGET)\b\.?(?:\s+DIV\w*\.?\s+[IV]+)?\s+(?:(?:MAJ|MIN)\w*\.?\s+)?"
    r"(?:COMM\w*\.?\s+)?(?:REPORT|REPT|REP|RPT|RPRT|PUBLIC\s+HEARING|HEARING|WORK|WK|EXEC|SUBCOM\w*"
    r"|FULL)\b", re.I)
# Not a joint meeting: "JOINT HEARING 3/22/89 7:00 REP HALL FOR: APP & WAYS &
# MEANS" (HB 777 of 1989) is Appropriations and Ways and Means together.
ROW_JOINT = re.compile(r"^\W*(?:JOINT|JT\.?)\s", re.I)
ROW_MEETINGS = ("hearing", "exec", "worksession")
ROW_NAMERS = ROW_MEETINGS + ("report", "retained", "interim_report")
# "Committee of Conference Hearing: 05/29/2008 11:30 AM LOB 304" (HB 1405 of
# 2008) is the conferees' meeting, read as a hearing because it says one.
CONFERENCE_ROW = re.compile(
    r"^\W*(?:Committee\s+of\s+Conference|Conf(?:erence)?\.?\s+Comm(?:ittee)?\.?)\s+"
    r"(?:Public\s+)?(?:Hearing|Meeting|Work|Exec)", re.I)


def row_names(ev, body, term):
    """The committee a committee row names as its own, where it names one
    committee_names can place; else ""."""
    t = ev.get("_type")
    if t not in ROW_NAMERS:
        return ""
    raw = ev.get("_raw") or ""
    if ROW_JOINT.match(raw):
        return ""
    m = ROW_MONEY.match(raw) or (ROW_FOR.search(raw) if t in ROW_MEETINGS else None)
    return committee_placed(m.group("c"), body, term) if m else ""


OTHER_CHAMBER = {"H": "S", "S": "H"}


# THE HOUSE JOURNAL'S WORD ON WHICH COMMITTEE REPORTED (6 October 2026; the
# person's word on decision 50). Where a House row names another committee
# than the one the docket referred the bill to, the stage after it is headed
# with the House alone (build(), "A ROW THAT NAMES ANOTHER COMMITTEE"). HB 163
# of 1997 was "INTRODUCED AND REF TO COMMERCE", heard "FOR: CRIM JUST &
# PSFTY" and reported 20-0; SB 479 of 1998 was "INTRODUCED AND REF TO ST-FED
# RELATIONS" in the House, heard "FOR: CRIM JUST" and reported 13-0. The
# House Journal prints each report under the bill -- "Rep. Herbert R. Hansen
# for Criminal Justice and Public Safety: This bill repeals ... Vote 20-0."
# (journals/1997/HJ003.txt), "... Vote 13-0." (journals/1998/HJ014.txt) -- and
# where it prints the bill's report for the committee the row names, and for
# none the referral named, the row names the committee that had the bill and
# the stage is headed with it. Read from the House Journals of the term on
# disk, once a term and only when a row asks (house_reported); where none is
# on disk the stage is headed as before.
JOURNALS = Path("journals")
JOURNAL_BILL = re.compile(
    r"^(?P<pre>HB|SB|HCR|SCR|HJR|SJR|HR|SR|CACR|HA|PET)\s*(?P<n>\d+)(?:-[A-Z]+)*,", re.M)
JOURNAL_FOR = re.compile(
    r"^Rep\.\s+[^:\n]{2,80}?\s+for\s+(?P<c>[A-Z][A-Za-z,&'./ \-]{2,90}?)\s*:", re.M)
# {term: {bill: {committee as printed}}}, filled by house_reported.
HOUSE_REPORTED = {}


def journal_reports(text):
    """{bill: {committee}}: each committee a House Journal's text prints a
    report on a bill for, "Rep. ... for <committee>:" under the bill's own
    heading and before the next."""
    out = defaultdict(set)
    heads = list(JOURNAL_BILL.finditer(text))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        m = JOURNAL_FOR.search(text, h.end(), end)
        if m:
            out[f"{h.group('pre')}{int(h.group('n'))}"].add(" ".join(m.group("c").split()))
    return dict(out)


def house_reported(term, bill):
    """The committees the House Journals of `term` on disk print reports on
    `bill` for, as committee_placed names them for the House."""
    if term not in HOUSE_REPORTED:
        got = defaultdict(set)
        for year in (term or "").split("-")[:2]:
            if not year.isdigit():
                continue
            for f in sorted((JOURNALS / year).glob("HJ*.txt")):
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for b, cs in journal_reports(text).items():
                    got[b] |= cs
        HOUSE_REPORTED[term] = dict(got)
    return {committee_placed(c, "H", term) for c in HOUSE_REPORTED[term].get(bill, ())} - {""}


def _day_of(iso):
    """2009-01-10 as a date, or None."""
    try:
        return date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None


def _entered_before(ev, stamp):
    """Was this row entered before `stamp`? Only where both carry a stamp:
    the dockets of 2017 on stamp every row at midnight, so a row of the same
    day is never before."""
    e = ev.get("_entered")
    return (isinstance(e, datetime) and isinstance(stamp, datetime)
            and datetime.min not in (e, stamp) and e < stamp)


# "==CANCELED==" IS "==CANCELLED==" (7 October 2026). The clerk spelled the
# mark with one L on 53 rows of the dockets the histories read, 49 of them in
# 2015-2016: "==CANCELED== Executive Session: 2/3/2015 LOB 302" (HB 230 of
# 2015), "===CANCELED===Public Hearing: 1/29/2015 11:00 AM LOB 306" (HB 377 of
# 2015), "Hearing;===CANCELED=== January 23, 2001" (SB 19 of 2001). The
# history read only the two-L flag, so it told each as a meeting
# held -- the executive session HB 230's committee never sat, the hearing HB
# 377's never held -- while proceedings.csv, whose reader looks for the word
# however it is spelled (docket_parser.cancelled), left them off as cancelled.
CANCEL_FLAGS = ("CANCELLED", "CANCELED")

# AND A ROW THAT CANCELS A HEARING AND NAMES ITS NEW DAY IS THE NOTICE OF THAT
# DAY (7 October 2026). The Senate wrote both on one row in 2001-2002 and
# 2009: "Hearing; ==CANCELLED== RESCHEDULED == May 8, 2001, Room 101, LOB,
# 2:15 p.m.; SC19" (HB 643 of 2001), after the notice for 1 May. Senate
# Calendar 19 prints the 1 May hearings of HB 332, HB 553, HB 635 and HB 643
# "CANCELLED AND RESCHEDULED FOR MAY 8TH" and lists all four under Tuesday 8
# May; Calendar 22 does the same for HB 412's and HB 748's of 16 May ("one
# L": "=== CANCELED == RESCHEDULED == May 23, 2001"), and Calendar 20 of 2002
# for HB 1393's of 2 April. Read as cancelled, the row told the new day
# nowhere, and once the 1 May notice was read as moved by it (decision 56)
# those bills had no Senate hearing at all. So the mark is the old day's, the
# row is a live notice of the day it names, and "RESCHEDULED" in it is the
# rescheduling row's word (RESCHEDULING) that moves the earlier notice there.
# Only that order and that second mark: "=== CANCELLED === TO BE RESCHEDULED
# ===" is a cancellation, and so is the House's "==CANCELLED==Rescheduled
# Hearing Mar 9 11:00 Rm303,LOB" (HB 395 of 1999), a rescheduled notice it
# later called off -- House Calendars 21 and 22 print the rescheduled hearing
# of 9 March, and the docket moves it again to the 23rd and the 24th.
CANCELLED_AND_RESCHEDULED = re.compile(
    r"=+\s*CANCELL?ED\s*=+\s*RESCHEDULED\s*=+\s*(?=[A-Z][a-z]+\.?\s+\d|\d{1,2}/\d)", re.I)


# AND THE MARK SPELLED ANY OTHER WAY THE CLERK SPELLED IT (decision 59a, 7
# October 2026). parse_docket's flags are "==WORD==" in capitals, and 74 rows
# of 2009-2021 that the proceedings reader (docket_parser.cancelled) already
# leaves off were told as meetings held: "=Cancelled= Executive Session:
# 2/11/2010 10:00 AM LOB 204" (HB 1134 of 2010), "==Cancelled==Retained Bill -
# Executive Session: 10/29/2013 10:00 AM LOB 302" (twenty retained bills of
# Commerce, re-noticed "==Rescheduled==" for 22 October), "Executive Session:
# 2/06/2014 2:15 PM LOB 302 =cancelled due to weather=", "... LOB
# 210-211=CANCELLED=" (SB 370 of 2014, moved to 1 May), "Cancelled Continued
# Executive Session: 5/8/2014" (SB 220) and "CANCELLED Subcommittee Work
# Session: 09/17/2021" (SB 92). Each is the clerk's mark on the notice itself,
# and the calendars on disk agree where they print the bills: the meeting
# printed before the mark, and the bill's next meeting printed after it
# (cancel_spellings in the stage 2b survey). Not a mark that moves the
# meeting ("==CANCELED AND RESCHEDULED== Feb.11", SB 405 of 2000, the notice
# of the new day), and not "Cancelled" in a row's prose.
CANCEL_SPELLED = re.compile(
    r"=+\s*cancell?ed\b(?:(?!resched)[^=]){0,40}=+"
    r"|^\W*cancell?ed\s+(?=(?:continued\s+|retained\s+bill\s*-\s*)?(?:public\s+hearing|executive"
    r"\s+session|(?:sub)?committee\s+work|full\s+committee|work\s+session|division))", re.I)


def cancel_marked(r, kind=None):
    """Does the row's own mark call off the meeting it names? The mark spelled
    another way (CANCEL_SPELLED) counts only on a meeting's own row, `kind`
    being the event's type: "=== CANCELLED SESSION === Committee Report: Ought
    to Pass" (HB 407 of 2015) is the Senate's report for a session called
    off, and still a report."""
    desc = r.get("desc") or ""
    if CANCELLED_AND_RESCHEDULED.search(desc):
        return False
    return (any(f in CANCEL_FLAGS for f in r["flags"])
            or (kind in ROW_MEETINGS and bool(CANCEL_SPELLED.search(desc))))


def build(bill, rows, introduction=None):
    rows = sorted(stamps_in_reach(rows), key=lambda r: r["created"])
    if CORRECTIONS:
        SIBLINGS.extend(_sibling_rows(bill, rows))
    # A DATABASE-ERA BILL IS READ IN ITS OWN DECADE'S VOCABULARY. The dump
    # covers 1989-2016, whose lines abbreviate almost everything and date
    # almost nothing; docket_vocab reads those and returns events in exactly
    # the shape classify() does. A 2017-2026 row never reaches it, and the
    # import is optional so a checkout without those modules builds as before.
    session = next((r.get("session") for r in rows if r.get("session")), None)
    term = P.term_of(str(session or ""))
    vocab = None
    if _VOCAB is not None and _VOCAB.era_for(session) is not None:
        vocab = _VOCAB
        rows = vocab.join_rows(rows, session)
    evs, elsewhere = [], []
    read_from_journal = set()
    # The chambers that record a resolution's passage on a row of its own
    # (INTRODUCED_ADOPTED).
    passed = ({r["body"] for r in rows if PASSAGE_ROW.match(clean(r["desc"]))}
              if RESOLUTION.match(bill) else set())
    for r in rows:
        # One question of a line docket_vocab.questions split comes with its
        # event already read ("event"): a clause is read by its era's clause
        # table, not by the tables a whole line is read by.
        ev = r.get("event") or (
            vocab.classify(r["desc"], r["created"], r.get("session"))
            if vocab is not None else None) or classify(r["desc"])
        if vocab is None and ev["_type"] == "other":
            undated = INTRODUCED_UNDATED.match(ev["_raw"])
            if undated and isinstance(r.get("created"), datetime) \
                    and r["created"] != datetime.min:
                ev = {**ev, "_type": "introduced",
                      "committee": undated.group("committee"),
                      "date": r["created"].strftime("%m/%d/%Y")}
            else:
                # A floor vote whose row states no date (VOLUME_DAYS), or an
                # amendment whose number states no year (AMEND_YEARLESS).
                ev = undated_floor(ev, r) or yearless_amendment(ev) or ev
        # A resolution introduced and adopted in one motion (INTRODUCED_ADOPTED).
        if ev["_type"] == "other" and RESOLUTION.match(bill) and r["body"] not in passed:
            adopted = INTRODUCED_ADOPTED.match(ev["_raw"])
            if adopted:
                when = adopted.group("asof") or adopted.group("date")
                if not when and isinstance(r.get("created"), datetime) \
                        and r["created"] != datetime.min:
                    when = r["created"].strftime("%m/%d/%Y")
                if _adopted_in_term(when, r, bill, session):
                    ev = {**ev, "_type": "floor", "action": "Ought to Pass", "motion": "MA",
                          "vote": (adopted.group("vote") or "").upper() or None,
                          "y": adopted.group("y"), "n": adopted.group("n"), "refer": None,
                          "date": when}
        # The hearing sentence looks its own sign-ins up by bill and date.
        ev["_bill"] = bill
        # And a committee's name is the one it had in this term (committee_said).
        ev["_term"] = term
        if ev.get("chapter"):
            ev["chapter"] = confirmed_chapter(
                P.term_of(str(r.get("session") or session or "")), bill, ev["chapter"])
        # Off the raw line: clean() has already removed it from ev["_raw"].
        # Every question of one split line cites what the line cites, which
        # the clerk wrote once at its end ("entry").
        ev["cite"], ev["cite_page"] = cite_of(r.get("entry") or r["desc"])
        ev["body"] = r["body"]
        ev["cancelled"] = cancel_marked(r, ev["_type"]) or bool(ev.get("_cancels"))
        ev["recessed"] = "RECESSED" in r["flags"]
        # The row as the clerk typed it, marks and all, for overtaken().
        ev["_said"] = r["desc"]
        # And as the bill's docket list shows it, with the clerk's cancel
        # mark where the line carries one (marked_line).
        ev["_marked"] = marked_line(r["desc"], ev.get("_raw") or "")
        # A line docket_vocab.join_rows put back together from rows the
        # database cut it into, which read one by one were more than one
        # floor action and which still tells one: how many, where its era
        # asks that this be said.
        ev["joined"] = r.get("joined") or 0
        # One question of a line split into its questions: the row that
        # tells what the whole line tells carries the line ("line"), and the
        # others say their words are in it ("in_line"). docket_vocab.questions.
        ev["line"], ev["in_line"] = r.get("line") or "", bool(r.get("in_line"))
        # Which line that was, for a question the same line decides twice.
        ev["_entry"] = (r.get("created"), r["entry"]) if r.get("entry") else None
        fixed, entry = corrected_date(r, bill) if CORRECTIONS else (None, None)
        if fixed:
            # The docket's own date is kept beside the corrected one: the
            # bill page shows the clerk's line verbatim, and that line still
            # carries the date the docket gives.
            ev["date_as_recorded"] = _iso(ev.get("date")) or (
                entry.get("stated_date") or "")
            ev["date_note"] = (entry.get("note") or "").strip()
            ev["date"] = fixed
            ev["_corrected"] = True
        if not fixed:
            # The day the row states (STATES_ITS_DAY), before clamp_year,
            # which then has nothing of its to bring back.
            stated_day(ev, r)
            # And the year a row was entered for, and the journal's reading
            # of an introduction (INTRODUCED_ON).
            year_slip(ev, r, rows)
            introduced_on(ev, r, bill, read_from_journal)
            # And a day in words that is before the chamber had the bill.
            before_the_bill(ev, r, rows)
        if r.get("stamp_as_recorded") and not ev.get("row_note"):
            near = min((o["created"] for o in rows
                        if o is not r and not o.get("stamp_as_recorded")
                        and isinstance(o.get("created"), datetime)
                        and o["created"] != datetime.min),
                       key=lambda c: abs((c - r["created"]).total_seconds()), default=None)
            if near is not None:
                ev["row_note"] = STAMP_REREAD.format(
                    stamp=r["stamp_as_recorded"].strftime(MONTH),
                    near=near.strftime(MONTH), year=r["created"].year)
        clamp_year(ev, r.get("session") or session, r.get("created"))
        in_recess(ev, r, fixed)
        ev["when"] = event_date(ev, r["created"])
        # The moment the row was entered, for the rows a withdrawal turns
        # back into notices (below).
        ev["_entered"] = r["created"]
        away, there = misfiled(r, bill) if MISFILED else (None, "")
        if there:
            ev["row_note"] = there
        if away:
            # Out of the history, and into the bill's list of docket lines
            # with the note saying whose it is.
            elsewhere.append({"date": ev["when"].strftime("%Y-%m-%d"),
                              "type": ev["_type"], "body": ev["body"],
                              "cancelled": ev["cancelled"], "raw": ev["_raw"],
                              **({"said": ev["_marked"]} if ev.get("_marked") else {}),
                              "cite": ev.get("cite", ""),
                              "cite_page": ev.get("cite_page", ""),
                              "belongs_to": away["belongs_to"],
                              "row_note": (away.get("note") or "").strip()})
            continue
        # The order it was entered in, for hold_in_order to break a tie by;
        # it takes the key off again.
        ev["_row"] = len(evs)
        evs.append(ev)
    other_chambers_row(evs)
    evs.sort(key=day_order)
    hold_in_order(evs)
    whose_amendment(evs)
    # A hearing on a proposed non-germane amendment the day of the bill's own
    # hearing: that one carries the day's sign-ins (SB 222 of 2025, 22 April
    # 2025). And one the two chambers' committees held together is told once,
    # by the chamber whose row says it was joint: "Joint Hearing with the
    # House Education Funding Committee: 10/14/2025, ... on proposed
    # nongermane amendment # 2025-2978s" is the Senate's row of HB 292 of
    # 2025, and the House's row of the same hearing, told on its own, opened
    # a House committee's stage in the middle of the Senate's.
    for e in evs:
        if e["_type"] == "nongermane_hearing":
            e["_day_told"] = any(o["_type"] == "hearing" and not o["cancelled"]
                                 and o.get("date") and o.get("date") == e.get("date")
                                 for o in evs)
            e["_joint_told"] = any(
                o is not e and o["_type"] == "nongermane_hearing" and not o["cancelled"]
                and o.get("joint") and not e.get("joint") and o["body"] != e["body"]
                and o.get("date") == e.get("date")
                and any(same_amendment(x, y) for x in amend_keys(o.get("num"))[:1]
                        for y in amend_keys(e.get("num"))[:1])
                for o in evs)

    # A BILL WITHDRAWN BEFORE THE DAY IT WAS TO BE INTRODUCED WAS NOT
    # INTRODUCED, AND WHAT WAS SCHEDULED FOR AFTER IT DID NOT HAPPEN. The
    # House's docket of 2009-2012 enters a bill weeks ahead -- "To Be
    # Introduced 1/6/2010 and Referred to Finance", a hearing for the 7th --
    # and every sentence here tells such a row in the past tense, as done.
    # HB 1587 of 2010 was "Withdrawn Prior to Introduction" on 22 December
    # 2009 and its history said it was introduced on 6 January; HB 1284 of
    # 2012 was withdrawn on 4 January and its history held a public hearing
    # on the 12th and an executive session on the 24th. So where a row
    # withdraws the bill (not a floor vote: WITHDRAWN_ROW):
    #   - a "To Be Introduced" row for that day or a later one is told in its
    #     own words, as what was to be, and typed to_be_introduced so that
    #     nothing reads it as an introduction;
    #   - a hearing, executive session or work session set for a later day is
    #     told as a notice, and leaves the record's events as a cancelled one
    #     does -- the docket has no flag on it, and the bill was gone.
    # Both are placed where the docket entered them, so the history runs in
    # the order things were done: planned, scheduled, withdrawn.
    # The same day counts as before: the row says "To Be", the withdrawal is
    # entered that morning, and the docket alone cannot say the bill was
    # introduced first.
    #
    # THE HOUSE JOURNAL CAN, AND WHERE THE RECORD CARRIES ITS WORD THAT WORD
    # DECIDES (`introduction`, or INTRODUCTIONS: the reading build_data puts
    # on six of the measures it adds). On 4 January 2012 the House's
    # resolution introduced "House Bills numbered 1126 through 1283, 1285
    # through 1471 and 1473 through 1709": HB 1284, entered "Withdrawn" at
    # 8.11 that morning, is stepped over and printed "HB 1284 - Withdrawn.";
    # HB 1512, entered "Withdrawn" at 8.49, is inside the last range and is
    # printed in full with its committee. The same-day rule told both as never
    # introduced, and HB 1512 was read a first and second time and referred.
    # So a bill the journal says was introduced keeps its introduction, on
    # the day its row names, and is then withdrawn; a notice for a later day
    # is still a notice. A row that says "Prior to Introduction" in its own
    # words is not overruled by this: none is, on disk.
    #
    # AND AN "INTRODUCED" ROW THE JOURNAL DOES NOT BEAR OUT IS NOT AN
    # INTRODUCTION. HB 87 and HB 134 of 2009 and HB 633 of 2007 each have one
    # row -- "Introduced 1/7/2009 and Referred to Municipal and County
    # Government; HJ 8, PG. 121" -- which is the row every bill of that day
    # was given ahead of it, and the resolution of that day steps over each
    # number. Told in the past tense it said the House had introduced the bill
    # and referred it. Typed entered_introduced, told as what the docket
    # enters with the journal beside it (describe), and the bill is one that
    # was never introduced.
    #
    # AND A MEETING THE DOCKET SETS FOR SUCH A BILL IS A NOTICE (1 October
    # 2026). HB 273 of 2017 has two rows: "Introduced 01/04/2017 and referred
    # to Executive Departments and Administration", typed on 30 December, and
    # "Public Hearing: 01/10/2017 01:30 PM LOB 306", entered on 4 January --
    # the day the House's resolution stepped over 273 and 274. Its history
    # said "The committee held a public hearing on January 10, 2017" of a bill
    # no committee was sent. Nothing on disk says a hearing was held, and
    # nothing says one was not, so the row is told as what the docket
    # schedules (describe), set beside the row it belongs to, and leaves the
    # record's events as a notice for a day after a withdrawal does. A notice
    # a withdrawal has already made one keeps the sentence it had.
    said = introduction if introduction is not None else (
        INTRODUCTIONS.get((P.term_of(str(session or "")), bill)) or {})
    journal_in = said.get("introduced") is True
    journal_out = said.get("introduced") is False
    gone = [e for e in evs if e["_type"] == "withdrawn" and not e["cancelled"]]
    not_introduced = False
    if gone:
        cut = min(e["when"] for e in gone).date()
        stated = any(e.get("prior") for e in gone)
        for e in evs:
            if not e["cancelled"] and e["_type"] == "introduced" \
                    and TO_BE_INTRODUCED.match(e["_raw"]) \
                    and (stated or journal_out
                         or (e["when"].date() >= cut and not journal_in)):
                e["_type"], not_introduced = "to_be_introduced", True
                e["when"] = e["_entered"]
        for e in evs:
            if not e["cancelled"] and e["_type"] in ("hearing", "exec", "worksession") \
                    and e["when"].date() > cut:
                # Truthy, and the reason, for the row's note (notice_note).
                e["_void"] = "withdrawn"
                # Beside the plan it belonged to, where the bill never was
                # introduced; a bill that was keeps the notice on its day.
                if not_introduced:
                    e["when"] = e["_entered"]
    if journal_out:
        for e in evs:
            if not e["cancelled"] and e["_type"] == "introduced":
                e["_type"], not_introduced = "entered_introduced", True
                e["_journal"] = said
                # On the day the row was entered, as a "To Be Introduced" row
                # a withdrawal overtook is: HB 177's was typed on 28 December
                # 2016, and dated by the day it names it put an action of the
                # House on 4 January 2017, on the bill's list of docket lines
                # and as the last thing done to it, where the page says the
                # House did nothing. The sentence still gives the day the row
                # names, as the row's.
                e["when"] = e["_entered"]
    # And a bill only ever proposed for a session: HB 3 of the 2006 special
    # session, whose one row is PROPOSED_ROW.
    if any(e["_type"] == "proposed" for e in evs) and not any(
            e["_type"] == "introduced" for e in evs):
        not_introduced = True
    if not_introduced:
        # EVERY MEETING SET FOR A BILL THAT WAS NEVER INTRODUCED, whichever
        # row says it was not and whatever day the meeting was set for: no
        # committee had the bill. proceedings.notice_only leaves every such
        # row off the bill's stations, and a history that told one as held
        # would say what its own page does not draw. The one on disk is
        # HB 273's (the withdrawal rule above has already made notices of HB
        # 1284's two), and it carries the journal's word, for its sentence.
        for e in evs:
            if not e["cancelled"] and not e.get("_void") \
                    and e["_type"] in ("hearing", "exec", "worksession"):
                e["_void"], e["when"] = "not introduced", e["_entered"]
                if journal_out:
                    e["_journal"] = said
        for e in evs:
            if e["_type"] in ("to_be_introduced", "entered_introduced", "withdrawn",
                              "proposed") or e.get("_void"):
                e["_pre"] = True
    # AND A MEETING NOTICED BEFORE THE CHAMBER TOOK THE MEASURE FROM ITS
    # COMMITTEE, FOR A DAY AFTER IT DID. HA 1 of 2008: "Public Hearing:
    # 4/25/2008 9:00 AM LOB 206-208", entered on 8 April; on 23 April the
    # House voted "Withdraw From Joint Committee (Reps Wallner and Hess): MA
    # VV" and laid the address on the table, where it died. The history said
    # the committee held a public hearing on the 25th, two days after it had
    # nothing to hear. A notice, told as one (the rule a withdrawn bill's
    # notices follow above); a meeting noticed after the vote is another
    # committee's, or a later referral's, and is not this.
    for out_ in [e for e in evs if not e["cancelled"]
                 and TAKEN_FROM_COMMITTEE.match(e["_raw"])
                 and (e.get("motion") or "").upper() == "MA"]:
        for e in evs:
            if (not e["cancelled"] and not e.get("_void") and e["body"] == out_["body"]
                    and e["_type"] in ("hearing", "exec", "worksession")
                    and e["_entered"] < out_["_entered"]
                    and e["when"].date() > out_["when"].date()):
                e["_void"] = "taken"
    # AND A MEETING A LATER ROW CANCELLED OR MOVED IS NOT TOLD AT ALL (6
    # October 2026; the person's word on decision 56, and that day again:
    # "hearings that were cancelled and rescheduled do not need to be listed
    # as it just adds visual clutter"). overtaken() says which. Decided for
    # every row first and then applied, since a row carried as cancelled is
    # one rule (a) reads. Carried as a row the docket cancelled is, so neither
    # the narration nor any rule that reads what happened takes it for a
    # meeting, and the history tells the meeting that sat -- the rescheduled
    # day, where the docket gives one. For a day the notice was told as "A
    # public hearing had been scheduled for ...", where the docket entered it,
    # and SB 339 of 2006's first stage read "... had been scheduled for
    # January 19, 2006. A public hearing had been scheduled for March 15,
    # 2006. The committee held a public hearing on February 22, 2006." The row
    # keeps its day and its place among the bill's docket lines, with its note
    # (notice_note), and the calendar it cites stays among the bill's
    # documents: that calendar printed the bill.
    over = [(e, overtaken(e, evs)) for e in evs]
    for e, why in over:
        if why:
            e["_void"], e["_unheld_day"], e["cancelled"] = why, e["when"].date(), True
    # AND A NOTICE ITS OWN CANCELLED TWIN OF ONE STAMP CALLS OFF (the person's
    # decision of 8 October 2026). HB 355 of 2022's conference of 16 May is
    # given twice, word for word and at one stamp, plain and then marked
    # "==CANCELLED==" (Docket_2021-2022.txt lines 10239-10240), and the
    # history said a committee of conference "met on May 16, 2022, May 17,
    # 2022 and May 18, 2022": overtaken() reads no conference, and
    # _entered_before cannot order two rows of one stamp. The row that follows
    # in the docket is the later one; docket_parser.cancelled_twins reads the
    # pair the same way, so the table has no meeting that day either.
    for e in evs:
        if (not e["cancelled"] and not e.get("_void")
                and e["_type"] in ROW_MEETINGS + ("conference_meeting",)
                and _cancelled_twin(e, evs)):
            e["_void"], e["_unheld_day"], e["cancelled"] = "cancelled", e["when"].date(), True
    # AND A RECESSED HEARING'S NEXT DAY THAT FELL AFTER THE COMMITTEE HAD
    # REPORTED THE BILL (the review of decision 59g, 7 October 2026). HB 1218
    # of 2002's Senate hearing of 9 April was entered on the 9th as "Hearing;
    # === RECESSED === RECONVENE === April 17, 2002, Room 104, LOB, 1:30
    # p.m.", and the next evening as "Committee Report; Ought to Pass with
    # Amendment {3389}, (New Title) [04/11/02]"; the Senate tabled the bill on
    # the 11th. Senate Calendar 24A of 9 April prints the report, "Vote 5-0",
    # and under 17 April "PLEASE NOTE HB 1218 CANCELLED" and "Cancelled HB
    # 1218", as Calendars 25 to 26A do after it, and the history said the
    # committee held a public hearing on the 17th, a week after it had
    # reported. A reconvened day (docket_era_1999.reconvened_notice) after a
    # report of the same chamber entered after the notice, with nothing
    # between sending the bill back to a committee, is a notice the report
    # overtook: not told, its row kept among the docket lines with its note
    # (notice_note) and no day a committee sat (voided_meetings). Across all
    # nineteen terms it is this one; the other notices told for a day after
    # such a report are the House's continued executive sessions "if needed"
    # and the like, which nothing on disk says did not sit, and are left.
    for e in evs:
        if (e.get("_era") != "1999:reconvened" or e["cancelled"] or e.get("_void")
                or e["_type"] != "hearing"):
            continue
        day = e["when"].date()
        for rep in evs:
            if not (rep["_type"] == "report" and rep["body"] == e["body"]
                    and not rep["cancelled"] and rep["_entered"] > e["_entered"]
                    and rep["when"].date() < day):
                continue
            if any(x["body"] == e["body"] and x["_entered"] > rep["_entered"]
                   and x["when"].date() <= day
                   and (sends_to(x, term) or RECOMMITTED_ROW.search(x.get("_raw") or ""))
                   for x in evs):
                continue
            e["_void"], e["_unheld_day"], e["cancelled"] = "reported", day, True
            break
    # AND A MEETING CANCELLED ON MOST OF ITS BILLS AND DROPPED BY THE CALENDARS
    # (WHOLE_DAY, which main() decides once every history is built), for a
    # bill whose own notice of it the docket left unmarked.
    for e in evs:
        if (WHOLE_DAY and not e["cancelled"] and not e.get("_void")
                and _meeting_key(e, evs, term) in WHOLE_DAY):
            e["_void"], e["_unheld_day"], e["cancelled"] = "cancelled", e["when"].date(), True
            e["_whole_day"] = True
    for e in evs:
        _notice_seen(bill, e, evs, term)
    if gone or journal_out:
        evs = [e for _i, e in sorted(enumerate(evs),
                                     key=lambda x: (x[1]["when"].date(), x[0]))]

    # Which committee held the bill when each thing happened. Only the referral
    # line names one, so it is carried forward until the next referral -- the
    # rule stage_of already uses to label a stage, applied to every event so a
    # committee report knows whose report it is. The site had been taking the
    # committee off the bill record instead, which holds only the current one:
    # 858 of 1,929 reports had no committee against them, including every
    # report on a bill that had since moved on.
    held = {}
    for ev in evs:
        c = (ev.get("committee") or "").strip()
        if c:
            held[ev["body"]] = c
        ev["committee_now"] = held.get(ev["body"], "")

    # A PASSAGE THAT SENDS THE BILL ON SAYS SO, wherever its row's reader left
    # the referral off: "Ought to Pass, MA, VV; Refer to Finance [Rule 24]"
    # (HB 1119 of 2002, read by the 1999 reader's House pattern, which has no
    # `refer`), "PASSED/ADOPTED; REF TO APPROP" and "PASSED W/AM & REFERRED TO
    # APPROP" (SB 58 and HB 100 of 1989, whose reader wanted " AND REF TO").
    # Told as the referral the floor's reader reads is told (describe), and
    # only where the row carried a passage: a re-referral, a vacated
    # referral, a recommittal or a study changes the heading (sends_to) and
    # is not this. And only where the row passes the bill BEFORE it names the
    # referral: "COMM AM<2151>, AL DIV(4-16); REF TO FINANCE; FIN COMM
    # AM<2202>(NEW TITLE), AA VV; ...; PASSED WITH AM VV" (SB 173 of 1995) is
    # Finance's amendment adopted and the bill passed, not a bill passed and
    # then sent on.
    #
    # A REFERRAL THE CHAMBER UNDID IS NOT TOLD. "Ought to Pass with Amendment
    # 0121s, MA, VV; Refer to Finance Rule 4-5" and, seven minutes later, "The
    # Chair Rescinded Refer to Finance Rule 4-5" (SB 91 of 2014); "Sen. Daniels
    # Waived Referral to Finance" (SB 553 of 2018). The bill never went: a
    # later row of that chamber that day undoing the referral takes the
    # referral out of the sentence and the heading.
    for i, ev in enumerate(evs):
        if ev["cancelled"] or ev["_type"] != "floor":
            continue
        if ev.get("refer") or sends_to(ev, term):
            day = ev["when"].date()
            if any(not e["cancelled"] and e["body"] == ev["body"]
                   and e["when"].date() == day and REFERRAL_UNDONE.search(e["_raw"])
                   for e in evs[i + 1:]):
                ev["refer"] = ""
                ev["_unsent"] = True
                continue
        if ev.get("refer"):
            continue
        sent = sends_to(ev, term)
        if (sent and sent[0] == "referred" and PASSAGE.match(split_mover(ev.get("action"))[0])
                and PASSED_WORDS.search(ev["_raw"][:sent[3]])):
            ev["refer"] = sent[1]

    # A COMMITTEE'S NAME THE DATABASE CUT AT A ROW'S END is finished by the row
    # it goes on in, entered with it: "REP N. FORD SUBST ITL, ML RC(118-218);
    # RE-REFERRED TO REG" and, thirteen seconds later, "REV VV; HJ42,P803-806"
    # (HB 297 of 1992) sent the bill "to the Reg committee", under a heading
    # of its own; "PASSED AND REF TO WAYS" and "& MEANS" (SB 151 of 1993);
    # "RE-REFERRED TO CON" and, three minutes later, "& STAT, REP TROMBLY MA
    # VV" (HB 683 of 1994). Only where the next row of that chamber was
    # entered within ten minutes, and the name and its first words are a
    # committee committee_names places; and only for what a heading or a
    # sentence prints (_as_written): the rows are not joined, and the Reports
    # tab's committee is as it was.
    for i, ev in enumerate(evs):
        said = ev.get("_as_written") or {}
        for key in ("committee", "refer"):
            cut = (said.get(key) or ev.get(key) or "").strip()
            if (not cut or ev["cancelled"]
                    or committee_placed(ev.get(key), ev["body"], term, said.get(key, ""))
                    or not re.search(re.escape(cut) + r"\W*$", ev["_raw"], re.I)):
                continue
            nxt = next((e for e in evs[i + 1:] if e["body"] == ev["body"]), None)
            if nxt is None or not (_entered_before(ev, nxt["_entered"]) and (
                    nxt["_entered"] - ev["_entered"]).total_seconds() <= 600):
                continue
            words = re.findall(r"[A-Za-z&]+", nxt["_raw"].split(";")[0])[:3]
            for k in range(1, len(words) + 1):
                whole = f"{cut} {' '.join(words[:k])}"
                if committee_placed(whole, ev["body"], term):
                    ev["_as_written"] = {**said, key: whole}
                    break

    # A REFERRAL THE COMMITTEE'S CHAIR WAIVED IS TOLD AS ONE (5 October 2026).
    # "Referred to Finance" and, that afternoon, "Referral Waived by Committee
    # Chair per House Rule 47(f)" (HB 1574 of 2026): the history said "the bill
    # was referred to the Finance committee" under a heading of its own, and the
    # Senate's committee came next, on 143 histories, and three of 1995 said
    # the House "sent it on to the Finance committee" a week before "REF TO
    # FINANCE DECLINED", because no row the undoing above reads says it so. The
    # chair declined the referral -- the House Journal prints "REFERRAL
    # DECLINED" over that bill and nine others -- and the bill never went.
    #
    # So a row REFERRAL_WAIVED reads, which no pattern tells, waives the
    # referral it follows: the last row of that chamber that referred the bill
    # to a committee, with no introduction and no other waiver between; or,
    # where the chamber's committee met or reported between the two, or there
    # is none, a referral of that chamber entered after it that day, as "Referral
    # Waived by Committee Chair" and then "Referred to Finance" on HB 368 of
    # 2017 and SB 482 of 2026. Where the waiver names the committee ("Referral
    # declined by Chair of Ways and Means"), only a referral to that one.
    #
    # Where nothing of the committee's lies between, the referral is told with
    # its waiver, in one sentence, where the waiver stands -- "On February 19,
    # 2026 the bill was referred to the Finance committee, whose chair waived
    # the referral under House Rule 47(f)." -- and heads no stage: the row
    # that made it is not told on its own, and a passage's sends it on to no
    # one (`refer`, _unsent). Where the committee had sat on it first (HB 194
    # of 2024: a Division I work session, then the waiver six weeks later), the
    # referral and the work are told as they were, and the waiver after them.
    # A waiver no referral can be found for is told as before, by nothing:
    # HB 1138 of 2024 has no "Referred to" row at all.
    for i, w in enumerate(evs):
        m = REFERRAL_WAIVED.search(w["_raw"] or "")
        if w["cancelled"] or w["_type"] != "other" or not m:
            continue
        b = w["body"]
        by = WAIVED_BY_CHAIR.search(w["_raw"])
        said = m.group("c") or m.group("w") or (by.group("c") if by else "")
        named = committee_placed(said, b, term) if said else ""

        def made(e):
            """The committee row `e` refers the bill to, as a sentence
            names it, or None."""
            if e.get("_waived_by") or e.get("_unsent"):
                return None
            if e["_type"] == "rereferred" and (e.get("committee") or "").strip():
                return _named(e, b)
            if e["_type"] == "floor" and e.get("refer"):
                return _named(e, b, "refer")
            sent = sends_to(e, term)
            if sent and sent[2] and sent[0] in ("referred", "rereferred", "rule"):
                return sent[1]
            return None

        back, busy = None, False
        for e in reversed(evs[:i]):
            if e["cancelled"] or e["body"] != b:
                continue
            if e["_type"] == "introduced" or REFERRAL_WAIVED.search(e["_raw"] or ""):
                break
            to = made(e)
            if to:
                back = (e, to)
                break
            if e["_type"] in ROW_NAMERS:
                busy = True
        ahead_ = None
        if back is None or busy:
            for e in evs[i + 1:]:
                if e["cancelled"] or e["body"] != b:
                    continue
                if e["when"].date() != w["when"].date() or e["_type"] in ROW_NAMERS \
                        or e["_type"] == "introduced":
                    break
                to = made(e)
                if to:
                    ahead_ = (e, to)
                    break
        pick, busy = ((back, False) if back and not busy else (ahead_, False) if ahead_
                      else (back, True))
        if pick is None or (named and named != pick[1]):
            continue
        r, to = pick
        if busy:
            w["_waives"] = ("after", r, to)
            continue
        r["_waived_by"] = w
        if r["_type"] == "rereferred":
            w["_waives"] = ("made", r, to)
            continue
        # A passage's referral, or one read off a row (sends_to): the passage
        # is told without it, and the waiver tells it.
        to = to if to.lower().endswith("committee") else f"{to} committee"
        w["_waives"] = ("sent", r, f"The {CHAMBER.get(b, 'House')} referred the bill to the {to}")
        r["refer"] = ""
        r["_unsent"] = True

    # A MOTION TO PASS ADOPTED AND THEN TABLED BEFORE THE STEP THAT PASSES THE
    # BILL (PASSAGE_PENDING) is told as the motion adopted, not the bill
    # passed; and a later bare "OT3rdg" of that chamber, the pending order
    # carried once the bill came off the table, is told as that order.
    held = passage_left_pending([(e["body"], row_day(e["_raw"], e["when"].strftime("%Y-%m-%d")),
                                  e["_raw"]) for e in evs if not e["cancelled"]])
    # The order is read on a sitting that did not itself leave it pending,
    # as build_site_v2.journey reads it.
    waiting = {}
    for e in evs:
        if e["cancelled"]:
            continue
        sitting = (e["body"], row_day(e["_raw"], e["when"].strftime("%Y-%m-%d")))
        why = held.get(sitting)
        if (why and e["_type"] == "floor" and (e.get("motion") or "").upper() == "MA"
                and re.match(r"\s*ought\s+to\s+pass\b", split_mover(e.get("action"))[0], re.I)):
            e["_unpassed"] = why
            waiting[e["body"]] = e
        elif (e["_type"] == "other" and BARE_THIRD.match(e["_raw"]) and sitting not in held
              and waiting.get(e["body"])):
            e["_type"] = "ot3rdg"
            waiting.pop(e["body"])

    sentences, notes, unknown = [], [], []
    # A note is said once per bill, however many rows repeat the action.
    used_notes = set()
    last_cmte = {}
    # {chamber: (the moment the row that sent the bill on was entered, the
    # committee that had it before, the stage that committee's work is told
    # in)}, for a row entered ahead of that one.
    moved = {}
    # {chamber: when the other chamber's introduction of the bill was entered}
    crossed = {}
    # {chamber: [(the amendments a committee's report carried, when it was
    # entered)]}, for the amendment the floor then votes on.
    carried_by = {}
    for e in evs:
        if e["_type"] == "report" and not e["cancelled"] and e.get("amend"):
            carried_by.setdefault(e["body"], []).append(
                (amend_keys(e["amend"]), e["_entered"]))
    stages = []   # [{"label": ..., "text": ...}] in the order they happened
    recorded_votes = 0
    unrecorded_votes = 0

    seen_intro = False
    # The consent calendar is explained once a bill, beside its first placing,
    # in the same words whatever happened after it: the note is the rule
    # (CC_THEN), and this bill's removal is said where a row records one
    # (CONSENT_OFF_NOTE). It was a set of the chambers that took the bill off,
    # read before the loop so that the note beside the placing could leave its
    # second sentence out there -- which made the note only as true as the
    # reading of every removal, and it was not.
    cc_explained = False
    # An amendment announced on one row and decided on another is told once,
    # by the row that decides it (amendment_outcome). "Not Voted On" decides
    # nothing when another row does: SB 535 of 2016's 2016-1160s is "Not
    # Voted On" and then "AF, VV" the same day.
    #
    # One that no amendment row decides is told with what the other rows DO
    # say of it (_fate, which describe reads), because "the docket records no
    # vote on it" is a claim about every row of the bill. It was made from the
    # amendment rows alone, numbers matched letter for letter, and was false
    # on SB 318 of 2018, whose 2018-1198s was divided and adopted 11-10 on
    # rows that begin with the number, and on HB 1696 of 2016, whose "1230s"
    # failed in three parts. See amend_keys().
    opened = [e for e in evs
              if e["_type"] == "amendment" and not e["cancelled"]
              and (e.get("num") or "").strip()
              and "Enrolled Bill" not in (e.get("what") or "")
              and not (e.get("motion") or "").strip()
              and amendment_outcome(e.get("_raw"))[0] in (None, "not voted on")]
    if opened:
        skip = {id(e) for e in opened}
        named = [(e, amend_keys(e.get("_raw"))) for e in evs
                 if not e["cancelled"] and id(e) not in skip]
        for a in opened:
            mine = amend_keys(a["num"])[:1]
            if not mine:
                continue
            there = [e for e, keys in named
                     if any(same_amendment(mine[0], k) for k in keys)]
            ours = [e.get("_raw") or "" for e in there if e["body"] == a["body"]]
            # An amendment row of the same chamber naming it carries an
            # outcome, or it would be in opened: that row tells it.
            if any(e["_type"] == "amendment" and e["body"] == a["body"]
                   for e in there):
                a["_decided_elsewhere"] = True
            ruled = [x for x in ours if AMEND_RULED.search(x)]
            a["_fate"] = (
                "unnamed" if not there
                else "withdrawn" if any(AMEND_WITHDRAWN.search(x) for x in ours)
                else "sections ruled" if any(re.search(r"\bsections?\s+of\b", x, re.I)
                                             for x in ruled)
                else "ruled" if ruled else "")
    # A QUESTION ONE LINE DECIDES TWICE HAPPENED TWICE. collapse() drops a
    # sentence repeated word for word, because two identical rows are one
    # action entered twice -- each chamber records the same enrolment. Two
    # clauses of one entry are not that: the clerk typed "Passed with Am
    # RC(172-171[including Speaker]); Rep O'Hearn moved to reconsider, MA
    # RC(175-167); Passed with Am RC(172-171)" (HB 633 of 1999) because the
    # House passed the bill, reconsidered, and passed it again by the same
    # count, and with the second sentence dropped the history read passed,
    # reconsidered, and nothing after. The repeat says "again", which is what
    # happened and is also what keeps it.
    told_on_line = set()
    # {chamber: [the floor and amendment sentences told so far]} (told_again).
    told_floor = defaultdict(list)
    for ev in amendment_after_report(crossing_order(evs)):
        if ev["cancelled"]:
            continue
        s = describe(ev, ev["body"], seen_intro)
        if ev["_type"] in ("floor", "amendment") and not ev.get("_entry"):
            plain = s
            s = told_again(s, ev, told_floor[ev["body"]], sentences[-1] if sentences else None)
            if plain:
                told_floor[ev["body"]].append(plain)
        # A referral its committee's chair waived is told by the waiver
        # (REFERRAL_WAIVED, above), and heads no stage.
        if ev.get("_waived_by") and ev["_type"] == "rereferred":
            s = None
        # The stage this row's sentence goes into, for its notes (_note); and
        # whether the row is given back to the committee a row sent the bill
        # on from (moved, below).
        here, back = None, False
        if ev["_type"] == "introduced":
            # THE COMMITTEE A ROW SENT THE BILL ON TO IS NOT CARRIED PAST ITS
            # CROSSING. A row of that chamber's committee entered after the
            # other chamber's introduction was, with no referral of its own,
            # is not told as that committee's: "EXEC SESS MAY14 2:30 & MAY15
            # 1:00 RM103, ST HOUSE", coded to the House on HB 25 of 1997 three
            # weeks after the Senate's introduction was entered, in the
            # Senate's room between the Senate Capital Budget's sessions, was
            # headed with the House's Finance. Entered, not dated: the
            # Senate's introduction of HB 187 of 2025 is dated 27 March and
            # was entered on 11 April, after the House Finance report it falls
            # before by date. Only a committee a row sent the bill on to
            # (sends_to): carried past the crossing from an introduction, the
            # heading is as it always was.
            other = OTHER_CHAMBER.get(ev["body"])
            if other in moved:
                crossed[other] = ev["_entered"]
            seen_intro = True
        if s and ev["_type"] == "floor" and ev.get("_entry"):
            if (ev["_entry"], s) in told_on_line:
                chamber = f"the {CHAMBER.get(ev['body'], 'House')} "
                s = s.replace(chamber, chamber + "again ", 1)
            told_on_line.add((ev["_entry"], s))
        if s:
            sentences.append(s)
            key = stage_of(ev)
            # A COMMITTEE'S AMENDMENT VOTED BETWEEN TWO FLOOR QUESTIONS IS ON
            # THE FLOOR. stage_of files a committee amendment under the
            # committee, which is where it was written. As one question of a
            # floor line told question by question it is voted in the middle
            # of the floor's business: "Taken from the Table, Rep Alukonis MA
            # VV; Fin Comm Am{4110}, AA VV; Laid on the Table, Rep Alukonis MA
            # VV" (HR 10 of 1999) came out as a floor heading, an "In House
            # committee" heading over the one amendment, and a floor heading
            # again, on a resolution that was never in committee. Where the
            # chamber's floor already holds the bill, it stays there.
            if (ev["_type"] == "amendment" and key[1] == "committee"
                    and (ev.get("in_line") or ev.get("line"))
                    and stages and stages[-1]["key"][:2] == (key[0], "floor")):
                key = (key[0], "floor")
            cmte = (ev.get("committee") or "").strip()
            # Only the referral row names the committee; the hearing and
            # executive session rows that follow do not. Keying on what each
            # row happens to carry split one committee's work into "In Senate
            # committee - Commerce" followed by a second, unnamed "In Senate
            # committee". The committee holding a bill does not change between
            # its referral and its hearing, and when it does there is a row
            # that says so: a re-referral, which names it, or a row that sends
            # the bill on, which sends_to reads (below, after the row's own
            # stage). A committee is named as it was then (committee_said), so
            # one committee the clerk wrote two ways is one stage.
            if key[1] == "committee" and ev["_type"] in ROW_MEETINGS \
                    and CONFERENCE_ROW.match(ev["_raw"]):
                key = ("C", "conference")
            elif key[1] == "committee":
                b = key[0]
                if cmte:
                    cmte = last_cmte[b] = committee_said(
                        cmte, b, term, (ev.get("_as_written") or {}).get("committee", ""))
                    moved.pop(b, None)
                    crossed.pop(b, None)
                else:
                    cmte = last_cmte.get(b, "")
                    if b in crossed and _entered_before({"_entered": crossed[b]}, ev["_entered"]):
                        cmte = last_cmte[b] = ""
                        crossed.pop(b)
                    # A ROW ENTERED BEFORE THE ROW THAT SENT THE BILL ON is the
                    # committee's it was sent from, wherever its own date files
                    # it after: Commerce's report on HB 1076 of 2024, dated 16
                    # May and entered on the 7th, beside the Senate's referral
                    # to Finance of the 15th.
                    if b in moved and _entered_before(ev, moved[b][0]):
                        cmte = moved[b][1]
                        back = True
                    # AND A COMMITTEE'S AMENDMENT IS THE COMMITTEE'S WHOSE
                    # REPORT CARRIED IT, wherever the floor votes on it: the
                    # report naming Commerce's 2024-1826s on HB 1380 of 2024
                    # was entered on 8 May, and the amendment was adopted on
                    # the 15th, in the vote that passed the bill and sent it
                    # on to Finance.
                    if ev["_type"] == "amendment" and b in moved:
                        mine = amend_keys(ev.get("num"))
                        if any(_entered_before({"_entered": at}, moved[b][0])
                               and any(same_amendment(k, x) for k in keys for x in mine)
                               for keys, at in carried_by.get(b, ())):
                            cmte = moved[b][1]
                            back = True
                    # A ROW THAT NAMES ANOTHER COMMITTEE THAN THE ONE HOLDING
                    # THE BILL is a record that cannot say whose the work is,
                    # and from there the chamber is named alone, until a row
                    # says which. "CONTINUED HEARING MAR19 ... FOR: INSUR" on
                    # HCR 25 of 1998, whose hearing of the 12th, in the same
                    # room and hour, was Internal Affairs'; "HEARING JAN15 ...
                    # FOR: CRIM JUST & PSFTY" on HB 163 of 1997, referred to
                    # Commerce. UNLESS THE HOUSE JOURNAL SAYS WHICH: it gives
                    # HB 163's 20-0 report to Criminal Justice and Public
                    # Safety, and the stage is headed with it (house_reported).
                    # A holder the row does not place -- a name the database
                    # cut, "RE-REFERRED TO REG" -- is kept.
                    named = row_names(ev, b, term)
                    if named and named != cmte:
                        held = last_cmte.get(b, "")
                        if not held:
                            last_cmte[b] = named
                            moved.pop(b, None)
                            cmte = named
                        elif named == held:
                            cmte = named
                        elif b == "H" and named in (said_by := house_reported(term, bill)) \
                                and held not in said_by:
                            # The House Journal prints the bill's report
                            # for the committee this row names (house_reported).
                            last_cmte[b] = cmte = named
                            moved.pop(b, None)
                        elif committee_placed(held, b, term):
                            last_cmte[b] = cmte = ""
                if cmte:
                    key = key + (cmte,)
            # AND ITS REPORT OR ITS AMENDMENT IS TOLD IN ITS OWN STAGE, before
            # the passage that sent the bill on (5 October 2026). "Committee
            # Amendment # 2025-1642s, AA, VV; 05/01/2025" was entered two hours
            # after "Ought to Pass with Amendment #2025-1642s, MA, VV; Refer to
            # Finance Rule 4-5" on HB 658 of 2025, and the Senate Journal of
            # that day prints the amendment in Ways and Means' report; HHS's
            # report on HB 1568 of 2024 is dated 16 May, the calendar's day,
            # and was entered on the 6th, a week before the referral of the
            # 15th. Told where they fell by date, each opened a stage headed
            # with the first committee straight after the sentence that sent
            # the bill to Finance, on 31 histories. Only a report, or an
            # amendment, that the rules above give back to that committee by
            # what it is: a meeting entered before the referral for a day after
            # it is told where its date puts it, since nothing in the row says
            # it was not the second committee's to hold. (SB 339 of 2006's
            # hearing of 15 March was the case in point, until the later row
            # that moved it to 22 February was read: overtaken() leaves it out
            # of the history.) A report is told before the
            # vote on the committee's amendment the stage already tells (HB 1202
            # of 2024),
            # as the committee reported it before the floor took it up.
            home = moved.get(key[0], ())[2:3]
            if (back and home and home[0] is not None and home[0]["key"] == key
                    and ev["_type"] in ("report", "amendment")):
                here = home[0]
                told = here["sentences"]
                at = next((k for k, x in enumerate(told)
                           if x.startswith("The committee's amendment (")),
                          len(told)) if ev["_type"] == "report" else len(told)
                told.insert(at, s)
            elif stages and stages[-1]["key"] == key:
                here = stages[-1]
                here["sentences"].append(s)
            else:
                base = STAGE_LABEL.get(key[:2], "")
                if len(key) > 2 and base:
                    base = f"{base} \u2014 {key[2]}"
                here = {"key": key, "label": base, "sentences": [s], "notes": []}
                stages.append(here)
            # THE REPORTS TAB NAMES THE COMMITTEE THE HISTORY HEADS THE REPORT
            # WITH (6 October 2026; the person's word on decision 48). The
            # report's own "committee" was the referral line's, carried
            # forward (committee_now), so Finance's 6-0 report on SB 286 of
            # 2025, told under "In Senate committee -- Finance", was
            # Executive Departments and Administration's on the tab. The
            # stage's committee where it names one; where it names the
            # chamber alone the report keeps the referral's, as before.
            if ev["_type"] == "report" and len(here["key"]) > 2:
                ev["_stage_cmte"] = here["key"][2]
        elif ev["_type"] == "other":
            unknown.append(ev["_raw"])

        # THE WAIVER OF A REFERRAL, where its chamber last stood (above).
        waives = ev.get("_waives")
        if waives and not s:
            b = ev["body"]
            if waives[0] == "made":
                said = waiver_said(ev, (describe(waives[1], b) or "").rstrip(" ."))
            elif waives[0] == "sent":
                said = waiver_said(ev, waives[2])
            else:
                said = waiver_said(ev)
                if last_cmte.get(b) == waives[2]:
                    last_cmte[b] = ""
            here = next((st for st in reversed(stages) if st["key"][0] == b), None)
            if here is None:
                here = {"key": (b, "floor"), "label": STAGE_LABEL[(b, "floor")],
                        "sentences": [], "notes": []}
                stages.append(here)
            here["sentences"].append(said)
            sentences.append(said)

        if ev["_type"] == "floor":
            vk = (ev.get("vote") or "").upper()
            if vk == "RC":
                recorded_votes += 1
            elif vk in ("VV", "DV"):
                unrecorded_votes += 1

        # Onto the stage this action belongs to, so the explanation sits
        # under the sentence that needed it. There may be no stage yet -- a
        # cancelled or unrecognised row produces no sentence -- in which case
        # there is nothing for the note to explain and it is dropped.
        def _note(text, stage=None):
            stage = (stage if stage is not None else here if here is not None
                     else (stages[-1] if stages else None))
            if stage is None or not text:
                return
            if text not in stage["notes"] and text not in used_notes:
                stage["notes"].append(text)
                used_notes.add(text)

        cm = CALENDAR_RE.search(ev["_raw"])
        if cm:
            _, cnote = CALENDAR[cm.group("cal").upper()]
            # THE TWO NOTES CONTRADICTED EACH OTHER ON 1,651 PAGES. The
            # standing note ended "It then passes without floor debate", and
            # where the docket records the bill actually coming off, the note
            # beside it said it was "debated and voted on separately, which is
            # what happened here". 2025 HB107 printed both, one after the
            # other. The cure was to leave the clause out beside a chamber
            # that took the bill off, which held only where the removal was
            # read (CC_THEN). Now the clause is the rule, "unless a bill is
            # taken off it first", so the two read as a rule and then this
            # bill's case of it, and the rule is said whole beside every
            # placing: once, beside the first, in one text.
            if cnote and cm.group("cal").upper() == "CC":
                if cc_explained:
                    cnote = None
                elif stages:
                    cc_explained = True
            _note(cnote)
        # Every removal the docket records, whether a pattern above tells it
        # (consent_off, with its own sentence) or the row is shown as the
        # clerk wrote it -- "Sen. Perkins Kwoka Moved to Remove SB 47 from the
        # Consent Calendar" (SB 47 of 2023) is told by nothing, and the page
        # said nothing of the removal. The chamber the row is of. And the
        # return of one to the calendar it came off (RETURNED_TO_CONSENT).
        #
        # UNDER THAT CHAMBER'S OWN STAGE. A consent_off row is staged with its
        # chamber's committee and the note followed it there, but a row typed
        # "other" makes no stage, and the note went under whichever was last:
        # the Senate's removal of HB 592 of 2025 under "With the governor",
        # because it was entered after the enrolment; the House's of HB 116
        # of 2022 under "On the Senate floor", entered in March for 5 January;
        # the Senate's of SCR 2 of 2015 under the House committee the
        # resolution had just crossed to -- nine histories. It goes under the
        # latest stage of the row's chamber, or of a committee of conference,
        # whose report the House has taken off its calendar since 2018
        # ("Removed from Consent (Rep. Roberts) 05/23/2018" beside "Conference
        # Committee Report 2009c: Adopted, RC 173-155", HB 1254 of 2018).
        #
        # AND AFTER THE RULE. A removal says the bill was on a consent
        # calendar whether or not its placing is read: 221 histories said
        # "took this bill off its consent calendar" and nowhere what the
        # calendar is, their placings written "for Mar 24 CC (vote 18-0)"
        # (HB 522 of 2009) or "{Vote: 14-3; CC}" (HB 177 of 2007), which
        # CALENDAR_RE does not read, or not marked at all; and SB 84 of
        # 2025's Senate removal was said six months before the House's
        # placing, under which the rule then stood. The rule is said beside
        # the first removal where no placing has said it yet, in the same
        # one text.
        off = ev["_type"] == "consent_off" or removed_from_consent(ev["_raw"])
        if (off or RETURNED_TO_CONSENT.search(ev["_raw"])) and stages:
            mine = next((st for st in reversed(stages)
                         if st["key"][0] in (ev["body"], "C")), stages[-1])
            if not cc_explained:
                _note(CALENDAR["CC"][1], mine)
                cc_explained = True
            _note((CONSENT_OFF_NOTE if off else CONSENT_BACK_NOTE).format(
                chamber=CHAMBER.get(ev["body"], "chamber")), mine)

        # THE LONGEST KEY, ONCE. NUANCE held "retain" and "retained in
        # committee", and "Retained in Committee" contains both, so every
        # retained bill -- 647 of them -- carried two explanations of the
        # same event on the same stage. _note dedupes on identical text,
        # which is the only reason "lay on table" and "laid on table" did not
        # do it too: they happen to share a sentence. The shorter key is
        # gone, and this fires only the most specific match so the next
        # overlapping pair cannot double up either.
        raw = ev["_raw"].lower()
        # Not the note a "died" row's own sentence already says: "The bill
        # died on the table when the session ended ..., having been set aside
        # and never taken back up." was followed by "The bill was set aside
        # during the session and never taken back up, so it died when the
        # session ended." on 130 histories of 2025-2026. A bare "Died on
        # Table" that no pattern reads (CACR 11 of 2019) keeps it, being told
        # by nothing else.
        hits = [k for k in NUANCE if k in raw
                and not (k == "died on table" and ev["_type"] == "died")]
        if hits:
            _note(NUANCE[max(hits, key=len)])

        # WHERE THIS ROW SENDS THE BILL, from the next row of that chamber's
        # committee on (sends_to). The floor's own `refer` to a name nothing
        # can place leaves the heading naming no committee rather than the one
        # the bill has left.
        sent = sends_to(ev, term)
        if sent and (sent[2] or sent[0] in ("rule", "joint")):
            b = ev["body"]
            crossed.pop(b, None)
            had = last_cmte.get(b, "")
            # And the stage that committee's work was told in, for its report
            # or amendment entered after this row (above).
            moved[b] = (ev["_entered"], had,
                        next((st for st in reversed(stages)
                              if st["key"] == (b, "committee", had)), None) if had else None)
            last_cmte[b] = sent[1] if sent[2] else ""
            # AND SAYS SO, where nothing else on the row does: "HB517 is
            # vacated from Judiciary and referred to Finance" (HB 517 of 2025)
            # and "Rule 24 (Refer to Finance)" (HB 294 of 1999) are read by no
            # pattern, and the history went from one committee's heading to
            # another's without a word. In describe()'s own sentence for a
            # vacated referral, or "The Senate referred the bill to the Finance
            # committee.", under the committee's heading.
            # Not on a passage, whose sentence tells the referral after it
            # (above) or, where the row names it first, has no need to.
            # Nor on a row that suspends the rules: "SUSP RULES TO REF TO FIN,
            # MA 2/3VV" (HB 1154 of 1996) is the motion describe() tells, the
            # referral the passage's of the next day; "Sen Trombly moved to
            # Suspend Rule 24 nec 2/3 vote MA, VV; Ref. to Finance[Rule24]"
            # (SB 337 of 2000), and the bill crossed to the House that day.
            # Nor where the row says it was yet to be done: "To Be Introduced
            # and referred to State-Federal Relations and Veterans Affairs" (CACR
            # 6 of 2021, in November, with nothing after it). And only where the
            # heading moves from one committee to another: "SUBST RE-REFER TO
            # COMMERCE, MA VV" (HB 355 of 1990) is the House sending the bill
            # back to the committee that had it, which the row's own sentence
            # says, and a second sentence told it as another referral; and a
            # referral where no committee had the bill is an introduction no
            # pattern reads, whose heading was already the committee's, and
            # whose sentence alone made the one stage of "PETITION READ AND
            # REFERRED TO SUBCOMM ON ELECTIONS, LEG ADMIN" (HR 10 of 1991),
            # and with it a rail the page had not drawn.
            if (sent[2] and sent[0] in ("vacated", "referred", "rereferred")
                    and had and sent[1] != had
                    and sent[1] not in (s or "")
                    and not SUSPENDS_RULES.search(ev["_raw"])
                    and not re.search(r"\bTo\s+Be\s+Introduced\b", ev["_raw"], re.I)
                    and not (ev["_type"] == "floor"
                             and PASSAGE.match(split_mover(ev.get("action") or "")[0]))):
                # Without a date: a row read by no pattern is dated by when it
                # was entered, and "(JAN23)INTRODUCED AND REF TO BANKS" (HB 128
                # of 1997) was entered on the 30th.
                to = sent[1] if sent[1].lower().endswith("committee") else f"{sent[1]} committee"
                chamber = CHAMBER.get(b, "House")
                said = (f"The {chamber} withdrew that referral and sent the bill to the {to} instead."
                        if sent[0] == "vacated" else
                        f"The {chamber} referred the bill to the {to}.")
                key = (b, "committee", sent[1])
                sentences.append(said)
                if stages and stages[-1]["key"] == key:
                    stages[-1]["sentences"].append(said)
                else:
                    stages.append({"key": key, "sentences": [said], "notes": [],
                                   "label": f"{STAGE_LABEL[key[:2]]} \u2014 {sent[1]}"})

    # Not a note on the summary. This is about the votes, and the Votes tab
    # is where somebody goes to look for them.
    vote_note = ""
    if unrecorded_votes and not recorded_votes:
        vote_note = ("Every floor vote on this bill was a voice or division "
                     "vote, so there is no record of how individual "
                     "legislators voted.")
    elif unrecorded_votes:
        vote_note = (f"{unrecorded_votes} of the floor votes on this bill were "
                     "voice or division votes, which do not record how "
                     "individual legislators voted.")

    # The one-string version is the collapsed stages joined, not the raw
    # sentences. It used to be the raw ones, so everything reading this field
    # -- the feeds, the page description, the archived term -- got the
    # twenty-six-sentence version of HB2 that the page itself does not show.
    # "hand" is the stage's own key -- H:committee, S:floor, G:governor --
    # so anything downstream can ask how far a bill got without matching on
    # the label's prose.
    staged = [{"label": st["label"],
               "hand": f"{st['key'][0]}:{st['key'][1]}",
               "text": collapse(st["sentences"],
                                CHAMBER.get(st["key"][0], "House")),
               # What this stage's actions needed explaining, in the order
               # they came up.
               "notes": st["notes"]}
              for st in stages]
    # A meeting a later row cancelled or moved (overtaken) is carried as that
    # meeting, not its day (voided_meetings): HB 142 of 2015's hearing at ten
    # on 12 February was held where the one at one o'clock was cancelled.
    told_on = {e["when"].date() for e in evs
               if not e["cancelled"] and not e.get("_void")
               and e["_type"] in ROW_MEETINGS + ("conference_meeting",) + tuple(FLOOR_TYPES)}
    voided = voided_meetings(evs)
    no_sitting = sorted({e["_no_day"] for e in evs if e.get("_no_day")}
                        | {e["when"].strftime("%Y-%m-%d") for e in evs
                           if e.get("_void") == "taken"}
                        # And the day a person's correction took off a meeting
                        # row (docket_corrections.json): proceedings.csv reads
                        # the docket's day, and SB 106 of 2009's hearing of 10
                        # February would be drawn again at the 10 January its
                        # row states.
                        | {e["date_as_recorded"] for e in evs
                           if e.get("_corrected") and e.get("date_as_recorded")
                           and e["_type"] in ROW_MEETINGS
                           and _day_of(e["date_as_recorded"]) not in told_on})
    return {
        "bill": bill,
        "narrative": " ".join(x["text"] for x in staged),
        # The same history, broken at each change of hands. The site shows
        # these as separate paragraphs; the joined version above is kept for
        # anything that wants one string.
        "stages": staged,
        "notes": notes,
        "vote_note": vote_note,
        # Floor details are carried through so the site can show voice and
        # division votes alongside roll calls. Those never appear in
        # RollCallSummary.txt -- only a roll call is recorded there -- yet they
        # decide a great many bills.
        "events": [{"date": e["when"].strftime("%Y-%m-%d"), "type": e["_type"],
                    # A meeting set for a day after the bill was withdrawn did
                    # not sit, and is carried as a cancelled one is.
                    "body": e["body"],
                    "cancelled": e["cancelled"] or bool(e.get("_void")),
                    "raw": e["_raw"],
                    # The line with the clerk's cancel mark, where it carries
                    # one, for the bill's docket list alone (marked_line):
                    # everything that reads the line reads `raw`.
                    **({"said": e["_marked"]} if e.get("_marked") else {}),
                    # A withdrawal the row itself says came before the bill
                    # was introduced: "Withdrawn Prior to Introduction".
                    **({"before_introduction": True}
                       if e["_type"] == "withdrawn" and e.get("prior") else {}),
                    # The journal or calendar this one action is printed in.
                    # Every event carries it, because every kind of event has
                    # one: a hearing cites the calendar that noticed it, a
                    # floor vote the journal page that recorded it.
                    "cite": e.get("cite", ""), "cite_page": e.get("cite_page", ""),
                    # The year of the volume cited, where it is not the year
                    # of the date above (stated_day).
                    **({"cite_year": e["cite_year"]} if e.get("cite_year") else {}),
                    # Where a person corrected the date (docket_corrections
                    # .json), the date the docket itself gives, and why.
                    **({"date_as_recorded": e["date_as_recorded"],
                        "date_note": e.get("date_note", "")}
                       if e.get("date_as_recorded") else {}),
                    # This bill's own row of a vote the docket also files
                    # under another bill (docket_corrections.json "misfiled").
                    **({"row_note": e["row_note"]} if e.get("row_note") else {}),
                    # A meeting row told as a notice. "cancelled" above keeps
                    # it out of everything that reads what happened; this says
                    # the row did not cancel itself, so the bill's list of
                    # docket lines still shows the row, with why it is not
                    # told as a meeting beside it (notice_note). And for one a
                    # later row cancelled or moved (overtaken), which: the
                    # calendar it cites is still one that printed the bill
                    # (build_site_v2.bill_documents).
                    **({"notice": True,
                        "row_note": e.get("row_note") or notice_note(e),
                        **({"overtaken": e["_void"]}
                           if e["_void"] in ("cancelled", "moved") else {})}
                       if e.get("_void") else {}),
                    # One line the clerk typed, read whole from rows the
                    # database cut it into, and how many floor actions those
                    # rows were read as one by one (docket_era_1999.
                    # MARK_JOINED), where the line still tells one of them:
                    # the sitting page needs to know the House put others to
                    # the bill on that line. A line split into its questions
                    # again (docket_vocab.questions) carries no mark.
                    **({"joined": e["joined"]} if e.get("joined") else {}),
                    # A question of a line the clerk typed as one entry and
                    # the 1999-2006 reader tells question by question: `raw`
                    # is this question's own clause, and the whole line is
                    # carried once, by the event that tells what the line
                    # read whole tells ("line"); the others say their words
                    # are in it ("in_line"). For what shows or reads a docket
                    # line as a line: the bill page's list, the passage rail.
                    **({"line": e["line"]} if e.get("line") else {}),
                    **({"in_line": True} if e.get("in_line") else {}),
                    **({**_floor_fields(e),
                        "motion": (e.get("motion") or "").upper(),
                        "vote_kind": (e.get("vote") or "").upper(),
                        "yeas": e.get("y"), "nays": e.get("n"),
                        # A consent calendar's count its other rows do not
                        # give (CONSENT_COUNTS): the rail tells no count.
                        **({"calendar_count_disputed": True}
                           if calendar_count_disputed(e) else {})}
                       if e["_type"] == "floor" else
                       # An amendment's number, what was moved on it and how it
                       # was decided. These were parsed and then thrown away at
                       # the door, so anything downstream had to re-read them
                       # out of the raw line -- and the site needs them to say
                       # which amendment a vote was on, and in what order they
                       # were taken up.
                       {"amendment": (e.get("num") or "").strip(),
                        "amend_kind": (WHOSE_KIND.get(e.get("_whose"))
                                       or (e.get("what") or "").strip()),
                        "motion": (e.get("motion") or "").upper(),
                        "vote_kind": (e.get("vote") or "").upper(),
                        # And its count, for the Votes tab's card of a
                        # division (build_site_v2.bill_rollcalls; the launch
                        # audit of 7 October 2026, cause 16).
                        "yeas": e.get("y"), "nays": e.get("n"),
                        "mover": (e.get("mover") or "").strip(),
                        # Decided again by a later clause of the same line
                        # (docket_vocab.questions): this outcome did not stand.
                        **({"decided_again": True} if e.get("decided_again") else {}),
                        # A vote on part of the amendment, where the docket's
                        # reader says so: "some" for sections of it, "rest"
                        # for the remainder, whose outcome is the amendment's.
                        **({"part": e["part"]} if e.get("part") else {})}
                       if e["_type"] == "amendment" else
                       # A committee report's own facts, for the same reason
                       # the two above are here. The Reports tab could show
                       # only the 1,901 bills whose reasoning a House Calendar
                       # printed, and told everyone else that Senate reports
                       # "use a different format and are not loaded yet". The
                       # format is this line: 1,708 Senate reports state their
                       # recommendation, the date the committee signed it and
                       # the vote, in the docket, and were being read and
                       # discarded at this door.
                       {"side": report_side(e.get("side")),
                        # The committee its stage of the history is headed
                        # with (decision 48), else the referral's.
                        "committee": e.get("_stage_cmte") or e.get("committee_now", ""),
                        "recommendation": (e.get("rec") or "").strip(),
                        "amendment": (e.get("amend") or "").strip(),
                        # The day the committee signed, not the day the clerk
                        # entered it.
                        "report_date": (e.get("date") or "").strip(),
                        "yeas": e.get("y"), "nays": e.get("n"),
                        "new_title": bool(e.get("new_title"))}
                       if e["_type"] == "report" else
                       # A chamber's vote on the conferees' report: its number,
                       # outcome, kind and count, for the Votes tab.
                       {"amendment": (e.get("num") or "").strip(),
                        "motion": e.get("motion") or "",
                        "vote_kind": (e.get("vote") or "").upper(),
                        "yeas": e.get("y"), "nays": e.get("n")}
                       if e["_type"] == "conf_report" else {})}
                   for e in evs],
        "unrecognised": unknown,
        # Rows the docket files under this bill that belong to another
        # (docket_corrections.json "misfiled"): shown with the docket's lines,
        # read by nothing that tells the bill's story.
        **({"misfiled": elsewhere} if elsewhere else {}),
        # The day a row of the docket withdrew the bill, where one did and it
        # was not a floor vote; and that the bill was never introduced, where
        # its own rows say so (the block above). build_site_v2 reads both:
        # the first to drop a sitting scheduled for after it, the second so
        # that no rail is drawn from an introduction that did not happen.
        **({"withdrawn": min(e["when"] for e in gone).strftime("%Y-%m-%d")}
           if gone else {}),
        **({"not_introduced": True} if not_introduced else {}),
        # The days the docket's rows put a committee's sitting on that this
        # history does not: the day a row states and the reader did not take
        # (before_the_bill), and the day of a notice the chamber overtook by
        # taking the measure from its committee. proceedings.notice_only
        # reads it, for the stations, the committee's days and the download.
        **({"no_sitting": no_sitting} if no_sitting else {}),
        # And each meeting a later row cancelled or moved, as [day, chamber,
        # kind, hour] (voided_meetings), which notice_only reads the same way
        # for that meeting alone.
        **({"voided": voided} if voided else {}),
    }


def report_corrections(results):
    """Say what docket_corrections.json did to this run, and what it did not.

    A CORRECTION THAT MATCHES NOTHING HAS STOPPED WORKING -- the clerk fixed
    or re-worded the row upstream -- and the mistyped date it was holding back
    is published again, so it is reported rather than passed over. Only this
    run's terms are judged: an entry for another term is not this docket's to
    match. Returns (applied, stale) as lists of entries.
    """
    if not CORRECTIONS and not MISFILED:
        return [], []
    mine = [i for i, e in enumerate(CORRECTIONS)
            if str(e.get("bill", "")).upper() in {
                b.upper() for b in results.get(
                    P.term_of(str(e.get("session", ""))), {})}]
    hit = [CORRECTIONS[i] for i in mine if i in CORRECTED]
    stale = [CORRECTIONS[i] for i in mine if i not in CORRECTED]
    if hit:
        print(f"  docket_corrections.json: {len(hit)} docket date(s) corrected")
    for e in stale:
        print(f"  ! docket_corrections.json: {e.get('bill')} of "
              f"{e.get('session')} matched no docket row and was NOT applied; "
              f"the row no longer reads {_squash(e.get('source_says'))!r}")
    for bill, desc in SIBLINGS:
        print(f"  ! docket_corrections.json: {bill} has another row with a "
              f"corrected entry's date and journal and no entry of its own: "
              f"{desc!r}")
    # The misfiled rows, judged the same way: one that matched no row has
    # stopped holding a vote off the wrong bill.
    for i, e in enumerate(MISFILED):
        if str(e.get("bill", "")).upper() not in {
                b.upper() for b in results.get(P.term_of(str(e.get("session", ""))), {})}:
            continue
        if i in MOVED:
            print(f"  docket_corrections.json: {e.get('bill')}'s row of "
                  f"{e.get('belongs_to')} taken off it")
        else:
            print(f"  ! docket_corrections.json: {e.get('bill')} of "
                  f"{e.get('session')} matched no docket row and was NOT "
                  f"applied; the row no longer reads "
                  f"{_squash(e.get('source_says'))!r}")
    return hit, stale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docket", default="Docket.txt")
    ap.add_argument("--bill")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--members", default="data/legislators.json",
                    help="roster used to give a motion's mover their full "
                         "first name; skipped if the file is not there")
    ap.add_argument("--testimony", default="testimony_db.json",
                    help="sign-in counts, so a public hearing says how many "
                         "signed in and on which side; skipped if not there")
    ap.add_argument("--corrections", default=CORRECTIONS_FILE,
                    help="docket dates, and rows filed under the wrong bill, "
                         "a person has corrected, with the evidence; "
                         "hand-made, and skipped if not there")
    ap.add_argument("--bills", default="data/bills.json",
                    help="each bill's own LSR, which decides which docket rows "
                         "are its own (own_rows); skipped if not there")
    ap.add_argument("--past-docket", default="",
                    help="the General Court's past docket view (db/past/"
                         "PastDocket.psv), for the bills of this docket's term "
                         "that it has no row for (past_docket_rows); not read "
                         "unless named, and narrate_archive.py names it")
    ap.add_argument("--chapters", default="",
                    help="chapters.json, so a law the docket numbers as another "
                         "bill's is told with the chapter the page prints "
                         "(SETTLED_CHAPTERS); not read unless named")
    a = ap.parse_args()

    global MEMBERS, TESTIMONY, CORRECTIONS, MISFILED, SETTLED_CHAPTERS, INTRODUCTIONS
    MEMBERS = load_members(a.members)
    CORRECTIONS = load_corrections(a.corrections)
    MISFILED = load_corrections(a.corrections, "misfiled")
    SETTLED_CHAPTERS = load_settled_chapters(a.chapters) if a.chapters else {}
    try:
        TESTIMONY = json.loads(Path(a.testimony).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        TESTIMONY = {}

    lsrs = load_lsrs(a.bills)
    INTRODUCTIONS = load_introductions(a.bills)
    bills = parse_docket(a.docket, want_bill=a.bill, lsrs=lsrs)
    if not bills:
        sys.exit(f"No docket rows found{' for ' + a.bill if a.bill else ''}.")
    report_lsrs(LSR_REPORT["taken"], LSR_REPORT["moved"],
                a.bills if lsrs else None)
    if a.past_docket and lsrs:
        more = past_docket_rows(a.past_docket, bills, lsrs)
        if a.bill:
            more = {b: r for b, r in more.items() if b.upper() == a.bill.upper()}
        bills.update(more)
        # Said with a marker narrate_archive passes on, like the LSRs' line:
        # a file that stopped being read looks exactly like a term with
        # every bill's docket in its own file.
        print(f"  rows from the past docket ({a.past_docket}): "
              f"{sum(len(r) for r in more.values()):,} row(s) given to the "
              f"{len(more):,} bill(s) this docket has no row for"
              + (f" ({', '.join(sorted(more))})" if more else ""))

    # Keyed on the term. Every docket row for a bill carries the same session
    # year -- all 2,233 of them, split 847 in 2025 and 1,386 in 2026 with no
    # bill in both -- so the first row settles which term the bill belongs to.
    results = defaultdict(dict)
    global TERM, CONSENT_COUNTS, WHOLE_DAY, VOLUME_DAYS
    # Every row of the docket, also where one bill is asked for (undated_floor).
    VOLUME_DAYS = volume_days(parse_docket(a.docket) if a.bill else bills)
    NOTICED.clear()
    MOVED_UNCHECKED.clear()
    WHOLE_DAY = {}
    for b, rows in bills.items():
        TERM = P.term_of(rows[0].get("session", ""))
        results[TERM][b] = build(b, rows)
    results = dict(results)
    # A MEETING CANCELLED ON MOST OF ITS BILLS AND NO LONGER PRINTED BY THE
    # CALENDARS (WHOLE_DAY): read once every history is built, and the bills
    # whose notice of it the docket left unmarked are built again.
    WHOLE_DAY = whole_day_meetings()
    NOTICED.clear()
    # Said, and where the calendars broke, a stop (CALENDAR_UNREAD).
    stop, said = whole_day_unchecked()
    if stop:
        sys.exit(stop)
    if said:
        print(said)
    if WHOLE_DAY:
        was = EXPANDED[0]
        again = sorted({(k[0], b) for k, w in WHOLE_DAY.items() for b in w["told"]})
        for t, b in again:
            TERM = t
            results[t][b] = build(b, bills[b])
        EXPANDED[0] = was
        print(f"  {len(WHOLE_DAY)} meeting(s) the docket cancels on most of their bills and "
              "the calendars no longer print, so cancelled for all of them: "
              + "; ".join(f"{k[2]} ({'House' if k[1] == 'H' else 'Senate'}), {k[3]}, "
                          f"{VOIDED_KIND[k[4]]}, for {', '.join(w['told'])} of {k[0]} "
                          f"({', '.join(w['calendars'])})" for k, w in sorted(WHOLE_DAY.items())))
    # A CONSENT CALENDAR'S COUNT, BY ALL ITS ROWS (CONSENT_COUNTS): read once
    # every history is built, and the few bills whose row gives a count the
    # calendar's other rows do not are built again with it. The movers they
    # name are counted once.
    CONSENT_COUNTS = consent_counts(results)
    again = sorted({(t, b) for t, byb in results.items() for b, rec in byb.items()
                    for e in rec.get("events") or []
                    if e.get("type") == "floor" and e.get("yeas") and e.get("nays")
                    and CONSENT_VOTE.search(e.get("raw") or "")
                    and (lambda got, mine: got and mine != got.most_common(1)[0][0]
                         and got.get(mine, 0) < got.most_common(1)[0][1])(
                        CONSENT_COUNTS.get((t, e.get("body"), e.get("date"))),
                        ((e.get("vote_kind") or "").upper(), e["yeas"], e["nays"]))})
    if again:
        was = EXPANDED[0]
        for t, b in again:
            TERM = t
            results[t][b] = build(b, bills[b])
        EXPANDED[0] = was
        print(f"  {len(again)} bill(s) whose consent calendar row gives a count the "
              f"calendar's other rows do not, told with no count: "
              + ", ".join(f"{b} of {t}" for t, b in again))
    # THE SESSION'S DOCKET SPEAKS FOR THE SESSION'S TERM ONLY (5 October
    # 2026). Below, every term this run builds replaces that term's histories
    # whole, which is right for a docket that holds the term. A turned
    # Docket.txt can still carry ten rows of the term before, and those ten
    # bills would have replaced its 2,233 histories -- rescued only because
    # narrate_archive.py happens to run later from that term's own docket,
    # which preflight now holds build_all to. So rows of any other term in the
    # session's docket are counted and left out, never merged.
    if Path(a.docket).name == "Docket.txt":
        session = P.session_term(Path(a.docket).parent)
        other = {t: len(b) for t, b in results.items() if session and t != session}
        for t in other:
            results.pop(t)
        if other:
            print("  left out: " + ", ".join(f"{n:,} bill(s) of {t}" for t, n in sorted(other.items()))
                  + f" -- the session's docket is {session}'s, and another term's histories "
                  "come from that term's own docket (narrate_archive.py)")
    # A SESSION THE CALENDARS COULD NOT BE ASKED ABOUT (_session_moved_by): a
    # stop where they broke, a line where none is on this disk for the term.
    broke = sorted({(c, t) for t, c, _k, _d in MOVED_UNCHECKED} & set(CALENDAR_UNREAD))
    if broke:
        sys.exit("narrative.py: the calendars could not be read for "
                 + "; ".join(f"the {'House' if c == 'H' else 'Senate'} of {t} "
                             f"({CALENDAR_UNREAD[(c, t)]})" for c, t in broke)
                 + ", so the sessions the docket marks rescheduled there cannot be held "
                   "to them (_session_moved_by)")
    if MOVED_UNCHECKED:
        print(f"  moved-session rule not applied: {len(MOVED_UNCHECKED)} session(s) the "
              "docket marks rescheduled and sets down for a later day have no calendar on "
              "this disk for their term, so they are told as held: "
              + "; ".join(f"{k} ({'House' if c == 'H' else 'Senate'}), {d} of {t}"
                          for t, c, k, d in sorted(MOVED_UNCHECKED)))
    report_corrections(results)
    n_sign = sum(1 for byb in results.values() for r in byb.values()
                 if "online testimony at" in (r["narrative"] or ""))
    print(f"  {n_sign:,} bills say how many signed in at a hearing"
          + ("" if TESTIMONY else f" (no counts at {a.testimony})"))

    if a.out:
        # MERGE. A run over one term's docket must not remove another's: this
        # file is {term: {bill: record}}, and a docket file covers one term.
        # Terms this run did build are replaced whole, because it rebuilt them
        # from their own docket and its answer is the current one.
        prior, kept = {}, []
        _op = Path(a.out)
        if _op.exists():
            try:
                prior = json.loads(_op.read_text(encoding="utf-8"))
            except ValueError:
                prior = {}
        if isinstance(prior, dict):
            kept = [t for t in prior if t not in results]
            merged = {**{t: prior[t] for t in kept}, **results}
        else:
            merged = results
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
        if kept:
            print("  kept, because this run's docket does not cover them: "
                  + ", ".join(f"{t} ({len(prior[t]):,} bills)"
                              for t in sorted(kept)))
        flat = [r for byb in results.values() for r in byb.values()]
        unk = sum(len(r["unrecognised"]) for r in flat)
        for t in sorted(results):
            print(f"  {t}: {len(results[t]):,} bills")
        print(f"{len(flat):,} bills across {len(results)} term(s) -> {a.out}")
        if MEMBERS:
            print(f"{EXPANDED[0]:,} motion movers given their full name from "
                  f"{a.members}")
        else:
            print(f"no roster at {a.members}, so motion movers keep the "
                  "initials the docket used")
        print(f"{unk:,} docket lines not recognised "
              f"(shown verbatim on the page, never dropped)")
        if unk:
            seen = OrderedDict()
            for r in flat:
                for u in r["unrecognised"]:
                    k = re.sub(r"\d", "#", u)[:70]
                    seen[k] = seen.get(k, 0) + 1
            print("\nmost common unrecognised shapes:")
            for k, v in sorted(seen.items(), key=lambda kv: -kv[1])[:12]:
                print(f"  {v:5}  {k}")
        return

    # Printing to the terminal rather than writing the file: one flat view,
    # since a person asking for a bill by name does not care which term the
    # docket they just pointed at belongs to.
    for b, r in ((b, r) for byb in results.values() for b, r in byb.items()):
        print(f"\n{'=' * 68}\n{b}\n{'=' * 68}")
        print(r["narrative"] or "(no recognised events)")
        for n in r["notes"]:
            print(f"\n  Note: {n}")
        if r["unrecognised"]:
            print("\n  Not recognised, shown as-is:")
            for u in r["unrecognised"]:
                print(f"    {u}")


if __name__ == "__main__":
    main()
