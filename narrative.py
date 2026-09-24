#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.34
"""
Turn a bill's docket entries into a plain-language history.

The docket is written in legislative shorthand. "Ought to Pass: MA VV 03/06/2025
HJ 8" means the House voted to pass the bill on a voice vote, with no record of
who voted which way. This renders that in a sentence a person can read, and says
so when no individual votes exist.

    python3 narrative.py --docket Docket.txt --bill HB84 --session 2025
    python3 narrative.py --docket Docket.txt --all --out narratives.json

Glossary sourced from the Citizens Count key to the NH Legislature website and
the NH General Court legislative handbook. Anything unrecognised is shown
verbatim rather than dropped -- an unexplained action is far better than a
missing one.
"""

import argparse
import json
import proceedings as P
import re
import sys
from collections import defaultdict, OrderedDict
from datetime import date, datetime
from pathlib import Path

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
CALENDAR = {
    # Two halves. The first explains what the consent calendar IS and is
    # said whenever a bill is put on one. The second explains how a bill comes
    # OFF it, and is said only when one did -- the docket records that as its
    # own action, so it is a fact about this bill rather than a rule recited
    # at every reader.
    "CC": ("the consent calendar",
           "A bill goes on the consent calendar when the committee vote was "
           "unanimous or nearly so, and any members who dissented did not "
           "object to placing it there. It then passes without floor debate."),
    "RC": ("the regular calendar", None),
}

# Said only where the docket records a bill actually coming off the consent
# calendar, which classify() reads as consent_off.
CONSENT_OFF_NOTE = ("Ten members may file a petition to pull a bill off the "
                    "consent calendar and have it debated and voted on "
                    "separately, which is what happened here.")

RECOMMENDATION = {
    "ought to pass with amendment": "pass it with changes",
    "ought to pass": "pass it",
    "inexpedient to legislate": "kill it",
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


def clamp_year(ev, session):
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
    """
    d = str(ev.get("date") or "")
    if not ONE_DATE.match(d):
        return ev
    try:
        year = int(str(session)[:4])
    except (TypeError, ValueError):
        return ev
    mo, dy, yr = (int(x) for x in d.split("/"))
    if year - 1 <= yr <= year + 1:
        return ev
    for y in (year, year - 1, year + 1):
        try:
            ev["date"] = datetime(y, mo, dy).strftime("%m/%d/%Y")
            break
        except ValueError:
            continue
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
# fixtures need a fixed answer.
TODAY = date.today()


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


def clean(s):
    # "== BILL KILLED ==" and "=== BILL KILLED ===". Two equals signs were
    # allowed for and three were not, so 717 floor lines kept a flag in the
    # middle and no pattern could read them.
    s = re.sub(r"=={1,}\s*[A-Z][A-Z ]*?\s*=={1,}", " ", s)
    s = re.sub(r"\s*(?:HJ|SJ|HC|SC)\s+\d+\b.*$", "", s)
    return re.sub(r"\s{2,}", " ", s).strip(" .;,")


# --------------------------------------------------------------- classify


# --- event families found in a full session's docket ------------------------

# "OT3rdg" = ordered to third reading, the procedural step after passage.
OT_RDG = re.compile(r"\bOT(\d)rdg\b", re.I)

# "Committee Amendment # 2025-1234s, AA, VV; 03/06/2025"
# "Amendment # 2025-1234h: AA VV 03/06/2025"
# "Enrolled Bill Amendment # 2025-2001e Adopted, VV, (In recess 06/26/2025)"
# "Sen. Birdsell Floor Amendment # 2026-1719s, AA, VV; 03/06/2026" -- the
# Senate puts the member who offered it in front, and the anchor meant 22 of
# these were not read as amendments at all. The name is captured rather than
# skipped, because who moved an amendment is worth a clause.
AMEND_RE = re.compile(
    # The name must not swallow the kind: "Sen. Birdsell Floor Amendment" is
    # a floor amendment offered by Birdsell, not an amendment by "Birdsell
    # Floor".
    r"^(?:(?P<mover>(?:Rep|Sen)\.\s+"
    r"(?:(?!Enrolled\b|Committee\b|Floor\b|Amendment\b)[A-Z][\w'\u2019.\-]*\s+){1,3}))?"
    r"(?P<what>(?:Enrolled Bill |Committee |Floor )?Amendment)\s*#?\s*"
    r"(?P<num>\d{4}-\d+[a-z]*)\s*[,:]?\s*"
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
    r"|\((?:Reps?|Sens?)\.?[^)]*\)[,;:]?\s*){0,3}"
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
# Ten members may petition to pull a bill off the consent calendar so it gets
# debated on the floor instead of passing without discussion. That is a
# substantive event and it was being dropped.
CONSENT_OFF_RE = re.compile(
    r"^(?P<bill>[A-Z]+\s*\d+)?\s*was Removed from the Consent Calendar"
    r"[;,]?\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)

# "Conference Committee Meeting: 06/12/2025 10:00 am GP 201"
# Where a contested bill gets its final wording, and we index those videos.
CONF_MEET_RE = re.compile(
    r"^Conference Committee Meeting[:\s]+(?P<date>\d{1,2}/\d{1,2}/\d{4})"
    r"\s*(?P<time>\d{1,2}:\d{2}\s*[ap]m)?\s*(?P<venue>[A-Z].*)?$", re.I)
DIED_RE = re.compile(r"^Died on Table[,;]?\s*Session ended\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)
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

PATTERNS = [
    ("introduced", re.compile(
        r"Introduced\s+(?:\(in recess of\)\s*)?(?P<date>\d{1,2}/\d{1,2}/\d{4})"
        r"\s+and\s+[Rr]eferred to\s+(?P<committee>.+?)$", re.I)),
    ("vacated", re.compile(
        r"Vacated and Referred to\s+(?P<committee>.+?)\s*(?:\(|:)", re.I)),
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
        r"(?:Refer(?:red)?\s+to\s+(?P<refer>[A-Z][A-Za-z ]+?)"
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
                 f"python3 narrative.py --docket Docket.txt --all --out {path}")
    return data.get(term or max(data), {})


def parse_docket(path, want_bill=None, want_session=None):
    bills = defaultdict(list)
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 7:
                continue
            bill = p[3].strip()
            if want_bill and bill.upper() != want_bill.upper():
                continue
            try:
                created = datetime.strptime(p[2].strip(), "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                created = datetime.min
            bills[bill].append({
                "lsr": f"{p[0]}-{p[1]}", "session": p[0].strip(),
                "body": p[4].strip(),
                "desc": p[5], "created": created,
                "flags": re.findall(r"==\s*([A-Z][A-Z ]*?)\s*==", p[5]),
            })
    return bills


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
FLOOR_AMD = re.compile(
    r"^A floor amendment \((?P<num>[^)]+)\)"
    r"(?:, offered by (?P<by>[^,]+),)? was (?P<what>adopted|rejected)"
    r"(?P<how> on a [a-z ]+?)?(?P<tally> \d+\u2013\d+)?"
    r"(?P<when> on \w+ \d{1,2}, \d{4})?"
    r"(?:, changing the text of the bill)?\.$")

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


def fold_amendments(run, chamber):
    """One sentence for a day's floor amendments, keeping every number."""
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
    when = next((m.group("when") for m in run if m.group("when")), "")
    lead = (f"On {when[4:]} the {chamber} took up {len(run)} floor amendments"
            if when else f"The {chamber} took up {len(run)} floor amendments")
    if not ok:
        return (f"{lead} and rejected all of them: "
                + and_list([cite(m) for m in no]) + ".")
    if not no:
        return (f"{lead} and adopted all of them: "
                + and_list([cite(m) for m in ok]) + ".")
    return (f"{lead}. It adopted " + and_list([cite(m) for m in ok])
            + ", and rejected " + and_list([cite(m) for m in no]) + ".")


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
            out.append(fold_amendments(run, chamber))
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
    if t in ("signed", "vetoed", "chaptered", "governor", "enrolled",
             "enrolled_amendment", "unsigned_law"):
        return ("G", "governor")
    if t in ("conference", "conference_meeting", "conf_report"):
        return ("C", "conference")
    if t == "introduced":
        return (body, "committee")
    if t == "amendment":
        # An amendment's stage is not its type, and the fall-through below put
        # every one of them in committee.
        #
        # A committee's own amendment is recorded inside the report line --
        # "Committee Report: Ought to Pass with Amendment # 2026-0503h (Vote
        # 10-0; CC)" -- so a standalone Amendment line with no other word in
        # front of it is one offered on the floor. The dates say the same
        # thing: a bare amendment line carries the floor vote's date, weeks
        # after the executive session it was being filed beside. The House
        # says it aloud the same way, announcing "floor amendment 1970H"
        # against the clerk's "the majority committee amendment".
        #
        # An enrolled bill amendment comes after both chambers have passed the
        # bill and belongs with enrolling, which is already staged with the
        # governor.
        what = (ev.get("what") or "").lower()
        if "enrolled" in what:
            return ("G", "governor")
        if "committee" in what:
            return (body, "committee")
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


def _squash(s):
    """Whitespace collapsed, so a row the clerk re-spaced still matches."""
    return re.sub(r"\s+", " ", str(s or "")).strip()


def load_corrections(path):
    """The entries of docket_corrections.json, or [] where there is none."""
    p = Path(path) if path else None
    if not p or not p.exists():
        return []
    doc = json.loads(p.read_text(encoding="utf-8"))
    return [e for e in (doc.get("dates") or []) if isinstance(e, dict)
            and e.get("source_says") and e.get("corrected_to")]


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

    if t == "introduced":
        if seen_intro:
            # Crossover: the second chamber records receipt as an introduction.
            return (f"It crossed to the {chamber} on {fdate(ev['date'])} and was "
                    f"referred to the {chamber} {ev['committee']} committee.")
        return (f"It was introduced on {fdate(ev['date'])} and referred to the "
                f"{chamber} {ev['committee']} committee.")

    if t == "vacated":
        return (f"The {chamber} withdrew that referral and sent the bill to the "
                f"{ev['committee']} committee instead.")

    if t == "hearing" and ahead(ev.get("date")):
        return (f"A public hearing is scheduled for {fdate(ev['date'])}"
                f"{signins(ev.get('_bill'), ev.get('date'))}.")

    if t == "exec" and ahead(ev.get("date")):
        return (f"The committee is due to meet in executive session on "
                f"{fdate(ev['date'])} to vote on its recommendation.")

    if t == "worksession" and ahead(ev.get("date")):
        return f"A work session is scheduled for {fdate(ev['date'])}."

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

        if verb and motion == "adopted":
            base = f"On {when} the {chamber} voted to {verb}"
        elif verb and motion == "failed":
            base = f"On {when} the {chamber} rejected a motion to {verb}"
        else:
            base = f"On {when} the {chamber} {motion or 'considered'} \u201c{action}\u201d"

        if vk:
            base += f" on a {vk}{tally}"
        if OT_RDG.search(ev.get("_raw", "")):
            base += " and ordered it to a third reading"
        if ev.get("refer"):
            base += (f", then sent it on to the {ev['refer'].strip()} committee "
                     "under the chamber's rules")
        return _stop(base + mover)

    if t == "amendment":
        kind = (ev.get("what") or "Amendment").strip()
        num = ev.get("num") or ""
        when = f" on {fdate(ev['date'])}" if ev.get("date") else ""
        adopted = (ev.get("motion") or "").upper() in ("AA", "ADOPTED")
        vk, _ = VOTE_KIND.get((ev.get("vote") or "").upper(), (None, None))
        y, n = ev.get("y"), ev.get("n")
        how = (f" on a {vk}" if vk else "") + (f" {y}\u2013{n}"
                                               if vk and y and n else "")
        if "Enrolled Bill" in kind:
            return (f"An enrolled bill amendment ({num}) was "
                    f"{'adopted' if adopted else 'considered'}{how}{when}. These correct "
                    "technical errors found after passage.")
        # THE SAME TEST stage_of USES, so the sentence and the heading over
        # it cannot disagree. A bare "Amendment" line is one offered on the
        # floor -- a committee's own amendment is recorded inside its report
        # line -- and stage_of has filed them under "On the House floor" since
        # it was written, while the sentence went on calling them "An
        # amendment". The heading was already making the claim; this says it
        # in the sentence too rather than leaving the reader to notice.
        who = ("The committee's amendment" if "committee" in kind.lower()
               else "A floor amendment")
        by = ""
        if ev.get("mover"):
            by = f", offered by {expand_mover(ev['mover'].strip())},"
        # "changing the text of the bill" was appended to every amendment,
        # including the ones that failed. A rejected amendment changed
        # nothing; saying it did is not a clumsy sentence, it is a false one.
        return (f"{who} ({num}){by} was {'adopted' if adopted else 'rejected'}"
                f"{how}{when}"
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

    if t == "consent_off":
        when = f" on {fdate(ev['date'])}" if ev.get("date") else ""
        return ("The bill was pulled off the consent calendar" + when +
                ", so it was debated and voted on separately rather than "
                "passing in a block. Ten members may petition for this.")

    if t == "conference_meeting":
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

    if t == "died":
        when = f" when the session ended on {fdate(ev['date'])}" if ev.get("date") else " when the session ended"
        return f"The bill died on the table{when}, having been set aside and never taken back up."

    if t == "rereferred":
        # THE CLERK DOES NOT ALWAYS NAME IT. HB 246 of 1999 reads
        # "Re-Referred to committee; HJ40, p907" and nothing more -- it went
        # back to the committee it came from, which the House did not need to
        # name. Printed through the sentence below that became "referred to
        # the  committee", with the gap where a name should be, on six pages.
        # Naming the committee it probably meant would be inventing a fact
        # the docket declines to state, so the sentence simply stops saying
        # which.
        c = (ev.get("committee") or "").strip()
        where = f" to the {c} committee" if c else " back to committee"
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


def hold_in_order(evs):
    """An as-of date (docket_vocab.as_of) may not move an action ahead of one
    it followed. evs is sorted; it is re-sorted if anything is put back.

    The clerk's "[05/06/04]" on "Senator Peterson Accede to House Request for
    C of C", entered on 13 May 2004, would have dated the Senate's answer six
    days before the House's request -- the date is the sitting the Senate was
    in recess of, not the day it acted. Where any action of the bill falls
    after the as-of date and by the day the row was entered, the row keeps
    the day it was entered.
    """
    back = False
    for ev in evs:
        stamp = ev.get("_stamp_date")
        if not stamp:
            continue
        try:
            entered = datetime.strptime(stamp, "%m/%d/%Y")
        except ValueError:
            continue
        if any(o is not ev and o.get("_type") in HELD_IN_ORDER
               and not o.get("cancelled") and ev["when"] < o["when"] <= entered
               for o in evs):
            ev["date"], ev["when"] = stamp, entered
            back = True
        ev.pop("_stamp_date", None)
    if back:
        evs.sort(key=lambda e: e["when"])
    return evs


def build(bill, rows):
    rows = sorted(rows, key=lambda r: r["created"])
    if CORRECTIONS:
        SIBLINGS.extend(_sibling_rows(bill, rows))
    # A DATABASE-ERA BILL IS READ IN ITS OWN DECADE'S VOCABULARY. The dump
    # covers 1989-2016, whose lines abbreviate almost everything and date
    # almost nothing; docket_vocab reads those and returns events in exactly
    # the shape classify() does. A 2017-2026 row never reaches it, and the
    # import is optional so a checkout without those modules builds as before.
    session = next((r.get("session") for r in rows if r.get("session")), None)
    vocab = None
    if _VOCAB is not None and _VOCAB.era_for(session) is not None:
        vocab = _VOCAB
        rows = vocab.join_rows(rows, session)
    evs = []
    for r in rows:
        ev = (vocab.classify(r["desc"], r["created"], r.get("session"))
              if vocab is not None else None) or classify(r["desc"])
        # The hearing sentence looks its own sign-ins up by bill and date.
        ev["_bill"] = bill
        # Off the raw line: clean() has already removed it from ev["_raw"].
        ev["cite"], ev["cite_page"] = cite_of(r["desc"])
        ev["body"] = r["body"]
        ev["cancelled"] = "CANCELLED" in r["flags"]
        ev["recessed"] = "RECESSED" in r["flags"]
        fixed, entry = corrected_date(r, bill) if CORRECTIONS else (None, None)
        if fixed:
            # The docket's own date is kept beside the corrected one: the
            # bill page shows the clerk's line verbatim, and that line still
            # carries the date the docket gives.
            ev["date_as_recorded"] = _iso(ev.get("date")) or (
                entry.get("stated_date") or "")
            ev["date_note"] = (entry.get("note") or "").strip()
            ev["date"] = fixed
        clamp_year(ev, r.get("session") or session)
        ev["when"] = event_date(ev, r["created"])
        evs.append(ev)
    evs.sort(key=lambda e: e["when"])
    hold_in_order(evs)

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

    sentences, notes, unknown = [], [], []
    # A note is said once per bill, however many rows repeat the action.
    used_notes = set()
    last_cmte = {}
    stages = []   # [{"label": ..., "text": ...}] in the order they happened
    recorded_votes = 0
    unrecorded_votes = 0

    seen_intro = False
    # Whether this bill ever came OFF the consent calendar, known before the
    # loop because the note that goes on beside the placing has to know what
    # happened after it. See the CALENDAR["CC"] note below.
    consent_off = any(e["_type"] == "consent_off" and not e["cancelled"]
                      for e in evs)
    for ev in evs:
        if ev["cancelled"]:
            continue
        s = describe(ev, ev["body"], seen_intro)
        if ev["_type"] == "introduced":
            seen_intro = True
        if s:
            sentences.append(s)
            key = stage_of(ev)
            cmte = (ev.get("committee") or "").strip()
            # Only the referral row names the committee; the hearing and
            # executive session rows that follow do not. Keying on what each
            # row happens to carry split one committee's work into "In Senate
            # committee - Commerce" followed by a second, unnamed "In Senate
            # committee". The committee holding a bill does not change between
            # its referral and its hearing, and when it does there is a
            # re-referral row that updates this.
            if cmte and key[1] == "committee":
                last_cmte[key[0]] = cmte
            elif key[1] == "committee":
                cmte = last_cmte.get(key[0], "")
            if cmte and key[1] == "committee":
                key = key + (cmte,)
            if stages and stages[-1]["key"] == key:
                stages[-1]["sentences"].append(s)
            else:
                base = STAGE_LABEL.get(key[:2], "")
                if len(key) > 2 and base:
                    base = f"{base} \u2014 {key[2]}"
                stages.append({"key": key, "label": base, "sentences": [s],
                               "notes": []})
        elif ev["_type"] == "other":
            unknown.append(ev["_raw"])

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
        def _note(text):
            if not stages or not text:
                return
            if text not in stages[-1]["notes"] and text not in used_notes:
                stages[-1]["notes"].append(text)
                used_notes.add(text)

        cm = CALENDAR_RE.search(ev["_raw"])
        if cm:
            _, cnote = CALENDAR[cm.group("cal").upper()]
            # THE TWO NOTES CONTRADICTED EACH OTHER ON 1,651 PAGES. The
            # standing note ends "It then passes without floor debate", which
            # is what the consent calendar is FOR -- and where the docket
            # records the bill actually coming off it, the note beside it says
            # ten members petitioned to have it "debated and voted on
            # separately, which is what happened here". 2025 HB107 printed
            # both, one after the other.
            #
            # Neither is wrong on its own; the first is a rule and the second
            # is this bill's history. So the rule keeps its first half, which
            # is the part a reader needs to understand what they are looking
            # at, and drops the clause the bill went on to disprove.
            if cnote and cm.group("cal").upper() == "CC" and consent_off:
                cnote = cnote.replace(
                    " It then passes without floor debate.", "")
            _note(cnote)
        if ev["_type"] == "consent_off":
            _note(CONSENT_OFF_NOTE)

        # THE LONGEST KEY, ONCE. NUANCE held "retain" and "retained in
        # committee", and "Retained in Committee" contains both, so every
        # retained bill -- 647 of them -- carried two explanations of the
        # same event on the same stage. _note dedupes on identical text,
        # which is the only reason "lay on table" and "laid on table" did not
        # do it too: they happen to share a sentence. The shorter key is
        # gone, and this fires only the most specific match so the next
        # overlapping pair cannot double up either.
        raw = ev["_raw"].lower()
        hits = [k for k in NUANCE if k in raw]
        if hits:
            _note(NUANCE[max(hits, key=len)])

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
                    "body": e["body"], "cancelled": e["cancelled"],
                    "raw": e["_raw"],
                    # The journal or calendar this one action is printed in.
                    # Every event carries it, because every kind of event has
                    # one: a hearing cites the calendar that noticed it, a
                    # floor vote the journal page that recorded it.
                    "cite": e.get("cite", ""), "cite_page": e.get("cite_page", ""),
                    # Where a person corrected the date (docket_corrections
                    # .json), the date the docket itself gives, and why.
                    **({"date_as_recorded": e["date_as_recorded"],
                        "date_note": e.get("date_note", "")}
                       if e.get("date_as_recorded") else {}),
                    **({**_floor_fields(e),
                        "motion": (e.get("motion") or "").upper(),
                        "vote_kind": (e.get("vote") or "").upper(),
                        "yeas": e.get("y"), "nays": e.get("n")}
                       if e["_type"] == "floor" else
                       # An amendment's number, what was moved on it and how it
                       # was decided. These were parsed and then thrown away at
                       # the door, so anything downstream had to re-read them
                       # out of the raw line -- and the site needs them to say
                       # which amendment a vote was on, and in what order they
                       # were taken up.
                       {"amendment": (e.get("num") or "").strip(),
                        "amend_kind": (e.get("what") or "").strip(),
                        "motion": (e.get("motion") or "").upper(),
                        "vote_kind": (e.get("vote") or "").upper(),
                        "mover": (e.get("mover") or "").strip()}
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
                        "committee": e.get("committee_now", ""),
                        "recommendation": (e.get("rec") or "").strip(),
                        "amendment": (e.get("amend") or "").strip(),
                        # The day the committee signed, not the day the clerk
                        # entered it.
                        "report_date": (e.get("date") or "").strip(),
                        "yeas": e.get("y"), "nays": e.get("n"),
                        "new_title": bool(e.get("new_title"))}
                       if e["_type"] == "report" else {})}
                   for e in evs],
        "unrecognised": unknown,
    }


def report_corrections(results):
    """Say what docket_corrections.json did to this run, and what it did not.

    A CORRECTION THAT MATCHES NOTHING HAS STOPPED WORKING -- the clerk fixed
    or re-worded the row upstream -- and the mistyped date it was holding back
    is published again, so it is reported rather than passed over. Only this
    run's terms are judged: an entry for another term is not this docket's to
    match. Returns (applied, stale) as lists of entries.
    """
    if not CORRECTIONS:
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
                    help="docket dates a person has corrected, with the "
                         "evidence; hand-made, and skipped if not there")
    a = ap.parse_args()

    global MEMBERS, TESTIMONY, CORRECTIONS
    MEMBERS = load_members(a.members)
    CORRECTIONS = load_corrections(a.corrections)
    try:
        TESTIMONY = json.loads(Path(a.testimony).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        TESTIMONY = {}

    bills = parse_docket(a.docket, want_bill=a.bill)
    if not bills:
        sys.exit(f"No docket rows found{' for ' + a.bill if a.bill else ''}.")

    # Keyed on the term. Every docket row for a bill carries the same session
    # year -- all 2,233 of them, split 847 in 2025 and 1,386 in 2026 with no
    # bill in both -- so the first row settles which term the bill belongs to.
    results = defaultdict(dict)
    global TERM
    for b, rows in bills.items():
        TERM = P.term_of(rows[0].get("session", ""))
        results[TERM][b] = build(b, rows)
    results = dict(results)
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
