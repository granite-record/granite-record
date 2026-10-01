#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.45
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

# A BILL WITHDRAWN, on a row that is not a floor vote (1 October 2026). Twelve
# rows across every docket on disk, all of them on bills the General Court's
# search page left out and the site had no record of: "Withdrawn Prior to
# Introduction" on four bills of 2010, "Withdrawn" and "Withdrawn 11/30/2011"
# on three of 2012, "Read in January 4, 2012 and Withdrawn" on a petition.
# The whole line, so that "Withdrawn from Committee Without Recommendation"
# -- a committee discharged -- is not one; a withdrawal the chamber voted,
# "Withdrawn (Rep Kreis): MA VV", is a floor row and is read as one.
WITHDRAWN_ROW = re.compile(
    r"^\s*(?:Read\s+in\s+(?P<read>[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})\s+and\s+)?"
    r"Withdrawn(?P<prior>\s+Prior\s+to\s+Introduction)?"
    r"(?:\s+(?P<date>\d{1,2}/\d{1,2}/\d{4}))?\s*$", re.I)
# "Proposed bill for special sesssion." is the one row of HB 3 of the 2006
# special session: a bill proposed for it, and nothing after.
PROPOSED_ROW = re.compile(
    r"^\s*Proposed\s+bill\s+for\s+(?:the\s+)?special\s+sess+ion\s*$", re.I)
# The introduction row as the House wrote it weeks ahead: "To Be Introduced
# 1/6/2010 and Referred to Finance". Every bill of those sessions carries it
# and was introduced on that day -- except one withdrawn first (build()).
TO_BE_INTRODUCED = re.compile(r"^\s*To\s+Be\s+Introduced\b", re.I)

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


def parse_docket(path, want_bill=None, want_session=None, lsrs=None):
    """{bill: [row]} -- the docket's rows, grouped by the bill-number field.

    With `lsrs` ({term: {bill: (LSR year, LSR number)}}, load_lsrs()), each
    bill's rows are its OWN rows: own_rows() says which those are and why.
    Without it every row stays under the number it was filed under, which is
    what a checkout with no data/bills.json gets.
    """
    bills = defaultdict(list)
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


def load_lsrs(path):
    """{term: {bill: (LSR year, LSR number)}} from data/bills.json, or {}."""
    p = Path(path) if path else None
    if not p or not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    if not is_term_keyed(data):
        return {}
    return {t: {b: (str(r.get("lsr_year") or "").strip(), _lsr_num(r.get("lsr_num")))
                for b, r in byb.items() if isinstance(r, dict)}
            for t, byb in data.items()}


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
        if (str(e.get("session")) != str(r.get("session"))
                or str(e.get("body", "")).upper() != str(r.get("body", "")).upper()):
            continue
        if (str(e.get("bill", "")).upper() == bill.upper()
                and _squash(e["source_says"]) == desc):
            MOVED.add(i)
            return e, ""
        if (str(e.get("belongs_to", "")).upper() == bill.upper()
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
                f"the {chamber} {ev['committee']} committee.")

    if ev.get("_void") and t in ("hearing", "exec", "worksession"):
        # Scheduled for a day after the bill was withdrawn: a notice, not a
        # meeting. The past tense of every sentence below would say it sat.
        what = {"hearing": "A public hearing", "exec": "An executive session",
                "worksession": "A work session"}[t]
        return f"{what} had been scheduled for {fdate(ev['date'])}."

    if t == "withdrawn":
        when = (fdate(ev["date"]) if ev.get("date")
                else ev["when"].strftime(MONTH) if ev.get("when") else "")
        on = f" on {when}" if when else ""
        if ev.get("read"):
            return (f"It was read in on {re.sub(r'\s+', ' ', ev['read']).strip()} "
                    "and withdrawn.")
        if ev.get("prior"):
            return f"It was withdrawn prior to introduction{on}."
        return f"It was withdrawn{on}."

    if t == "proposed":
        when = ev["when"].strftime(MONTH) if ev.get("when") else ""
        return ("It was proposed as a bill for the special session"
                + (f" on {when}" if when else "") + ".")

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
        # THE SAME TEST stage_of USES, so the sentence and the heading over
        # it cannot disagree. A bare "Amendment" line is one offered on the
        # floor -- a committee's own amendment is recorded inside its report
        # line -- and stage_of has filed them under "On the House floor" since
        # it was written, while the sentence went on calling them "An
        # amendment". The heading was already making the claim; this says it
        # in the sentence too rather than leaving the reader to notice.
        # And an amendment the committee's minority wrote is neither the
        # committee's nor any member's: the 1999-2006 reader's "Min Am{1208}"
        # (docket_era_1999.MINORITY_AMENDMENT), offered on the floor against
        # the majority's.
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
    evs, elsewhere = [], []
    for r in rows:
        # One question of a line docket_vocab.questions split comes with its
        # event already read ("event"): a clause is read by its era's clause
        # table, not by the tables a whole line is read by.
        ev = r.get("event") or (
            vocab.classify(r["desc"], r["created"], r.get("session"))
            if vocab is not None else None) or classify(r["desc"])
        # The hearing sentence looks its own sign-ins up by bill and date.
        ev["_bill"] = bill
        if ev.get("chapter"):
            ev["chapter"] = confirmed_chapter(
                P.term_of(str(r.get("session") or session or "")), bill, ev["chapter"])
        # Off the raw line: clean() has already removed it from ev["_raw"].
        # Every question of one split line cites what the line cites, which
        # the clerk wrote once at its end ("entry").
        ev["cite"], ev["cite_page"] = cite_of(r.get("entry") or r["desc"])
        ev["body"] = r["body"]
        ev["cancelled"] = "CANCELLED" in r["flags"]
        ev["recessed"] = "RECESSED" in r["flags"]
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
        clamp_year(ev, r.get("session") or session)
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
                              "cite": ev.get("cite", ""),
                              "cite_page": ev.get("cite_page", ""),
                              "belongs_to": away["belongs_to"],
                              "row_note": (away.get("note") or "").strip()})
            continue
        # The order it was entered in, for hold_in_order to break a tie by;
        # it takes the key off again.
        ev["_row"] = len(evs)
        evs.append(ev)
    evs.sort(key=day_order)
    hold_in_order(evs)

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
    # introduced first. (The House Journal of 4 January 2012 can, and prints
    # "HB 1284 - Withdrawn." in its list of bills introduced where it prints
    # HB 1512's entry in full; both read "Withdrawn" here, which is all the
    # docket says of either.)
    gone = [e for e in evs if e["_type"] == "withdrawn" and not e["cancelled"]]
    not_introduced = False
    if gone:
        cut = min(e["when"] for e in gone).date()
        stated = any(e.get("prior") for e in gone)
        for e in evs:
            if e["cancelled"]:
                continue
            if e["_type"] == "introduced" and TO_BE_INTRODUCED.match(e["_raw"]) \
                    and (stated or e["when"].date() >= cut):
                e["_type"], not_introduced = "to_be_introduced", True
                e["when"] = e["_entered"]
            elif e["_type"] in ("hearing", "exec", "worksession") \
                    and e["when"].date() > cut:
                e["_void"] = True
                e["when"] = e["_entered"]
    # And a bill only ever proposed for a session: HB 3 of the 2006 special
    # session, whose one row is PROPOSED_ROW.
    if any(e["_type"] == "proposed" for e in evs) and not any(
            e["_type"] == "introduced" for e in evs):
        not_introduced = True
    if not_introduced:
        for e in evs:
            if e["_type"] in ("to_be_introduced", "withdrawn", "proposed") \
                    or e.get("_void"):
                e["_pre"] = True
    if gone:
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
    for ev in evs:
        if ev["cancelled"]:
            continue
        s = describe(ev, ev["body"], seen_intro)
        if ev["_type"] == "introduced":
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
                    # A meeting set for a day after the bill was withdrawn did
                    # not sit, and is carried as a cancelled one is.
                    "body": e["body"],
                    "cancelled": e["cancelled"] or bool(e.get("_void")),
                    "raw": e["_raw"],
                    # A withdrawal the row itself says came before the bill
                    # was introduced: "Withdrawn Prior to Introduction".
                    **({"before_introduction": True}
                       if e["_type"] == "withdrawn" and e.get("prior") else {}),
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
                    # This bill's own row of a vote the docket also files
                    # under another bill (docket_corrections.json "misfiled").
                    **({"row_note": e["row_note"]} if e.get("row_note") else {}),
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

    global MEMBERS, TESTIMONY, CORRECTIONS, MISFILED, SETTLED_CHAPTERS
    MEMBERS = load_members(a.members)
    CORRECTIONS = load_corrections(a.corrections)
    MISFILED = load_corrections(a.corrections, "misfiled")
    SETTLED_CHAPTERS = load_settled_chapters(a.chapters) if a.chapters else {}
    try:
        TESTIMONY = json.loads(Path(a.testimony).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        TESTIMONY = {}

    lsrs = load_lsrs(a.bills)
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
