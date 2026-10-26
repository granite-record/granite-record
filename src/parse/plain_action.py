#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-14.13
"""
A docket line in plain words, for a reader who does not know the clerk's
shorthand -- the email digest and the Documents tab (the person's choices of
14 October 2026). The clerk's own line is never replaced: it stays beside
these words as the citation, and where a line is of a kind this does not
know, the answer is "" and the reader is shown the line as written.

    import plain_action as PA
    PA.plain("Ought to Pass: MA, VV; OT3rdg; 02/19/2026")
    # "Bill passed, on a voice vote"
    PA.plain("Majority Committee Report: Ought to Pass with Amendment # 2025-2969h 10/01/2025 (Vote 12-3; RC)")
    # "Majority committee report: pass the bill with changes (amendment 2025-2969h), 12–3"
    PA.plain("Executive Session: 06/15/2026 10:30 am GP 159")
    # "Executive session, 10:30 a.m., Granite Place 159"

THE WORDS ARE ALREADY APPROVED. A floor vote's are votes.json's -- the head
the Votes tab gives the same motion ("Bill Passed with Changes", "Sent to
Interim Study"), in sentence case -- read through motions.classify, the one
place the record's motions are recognised. A line's kind is
narrative.classify's, the reader the stories are written from. Nothing here
decides what a motion is.

NO DATE IN THE WORDS. Every place that shows these shows the line's date
beside them, and the clerk wrote it in a form ("06/15/2026") the site does not
use, so it is dropped here rather than said twice. The one date said is a
law's effective date ("II. Remainder Effective 06/10/2025"), which is what
that line is about and not the day it was entered.

ONE LINE AT A TIME, AND THE LINE AFTER IT. A caller that has the bill's
docket passes the line that follows (next_line): one kind of line, "Introduced
and Adopted" on a bill, means one thing or another by what comes next
(_introduced).

Standard library only, beside narrative.py and motions.py.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import json
import re
from datetime import date

import motions as M
import narrative as N

VOTES = json.loads((_paths.ROOT / "src/pages/words/votes.json").read_text(encoding="utf-8"))
# What an interim study committee's report said, in the words every page and
# email says it in (23 October 2026): they were written here first, and the
# file is their one copy now.
STUDY = json.loads((_paths.ROOT / "src/pages/words/study_report.json").read_text(encoding="utf-8"))

# The buildings the clerk abbreviates, as the calendar and the site name them.
# SL IS THE STATE LIBRARY (the person, 26 October 2026: "SL is the state
# library map room"). The Senate's Education committee sat in its Map Room
# for 54 hearings of 2025-2026, which the docket writes "Room Map Room, SL"
# and "Map Room, SL", the schedule "SL Map Room", the committee's own record
# "SL Rm Map Room" and the database "SL Room Map Room"; the Testify button,
# the Hearings tab, the committee's page and the email all printed the "SL".
BUILDINGS = {"LOB": "Legislative Office Building", "SH": "State House", "GP": "Granite Place",
             "SL": "State Library"}

_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", re.I)
_ROOM = re.compile(r"\bRoom\s+([\w][\w .\-]*?)\s*,\s*([A-Z]{2,3})\b", re.I)
# A room number, never the hour after it: "Representatives' Hall, SH 3:00
# p.m.", the Senate's hearing on HB 1 and HB 2 of 2015, read as "State House
# 3" once its two-digit year was read (16 October 2026).
_BLDG = re.compile(r"\b(LOB|SH|GP|SL)\s+([0-9][0-9A-Za-z\-]*)\b(?!:)")
# A ROOM WITH A NAME, NOT A NUMBER, after its building, whichever side of
# the room the clerk wrote the building on (26 October 2026): all five
# spellings of the Map Room above are "State Library Map Room", one room read
# one way, as "GP Room 230" and "GP 230" are both "Granite Place 230" (S7).
# A name is capitalised words ending in "Room", so a number never is one.
# app.js's roomWords has the same two patterns, held to these by preflight.
_NAMED = r"(?:[A-Z][\w']*\s+)+Room"
_NAMED_AFTER = re.compile(rf"\b(?:Room\s+)?({_NAMED})\s*,\s*(LOBO|LOB|SH|GP|SL)\b")
_NAMED_BEFORE = re.compile(rf"\b(LOBO|LOB|SH|GP|SL)\s+(?:Rm\.?\s+|Room\s+)?({_NAMED})\b")


def _named(t):
    """t with a named room in the site's words: "Map Room, SL" and "SL Rm Map
    Room" are "State Library Map Room"."""
    t = _NAMED_AFTER.sub(lambda m: f"{_PLACE_BUILDINGS[m.group(2)]} {m.group(1)}", t)
    return _NAMED_BEFORE.sub(lambda m: f"{_PLACE_BUILDINGS[m.group(1)]} {m.group(2)}", t)


_TALLY =re.compile(r"\b(RC|DV|VV)\b\s*=?\s*(?:(\d+)\s*Y?\s*-\s*(\d+)\s*N?)?", re.I)
_VOTE = re.compile(r"\bVote\s+(\d+)\s*-\s*(\d+)", re.I)
_AMD = re.compile(r"#\s*((?:\d{4}-)?\d+[a-z]*)", re.I)
_CHAPTER = re.compile(r"\bChapter\s*(\d+)", re.I)


def _clock(m):
    h, mi, ap = int(m.group(1)), m.group(2), m.group(3).lower()
    return f"{h}:{mi} {ap}.m."


def _where(raw):
    """", 10:30 a.m., Granite Place 159" from what follows a meeting's date."""
    bits = []
    t = _TIME.search(raw)
    if t:
        bits.append(_clock(t))
    n = _NAMED_AFTER.search(raw) or _NAMED_BEFORE.search(raw)
    r = _ROOM.search(raw)
    if n:
        bits.append(_named(n.group(0)))
    elif r:
        bits.append(f"Room {r.group(1).strip()}, {BUILDINGS.get(r.group(2).upper(), r.group(2))}")
    else:
        b = _BLDG.search(raw)
        if b:
            bits.append(f"{BUILDINGS[b.group(1)]} {b.group(2)}")
    return "".join(", " + x for x in bits)


def _how(raw):
    """", 193–143 on a roll call" / ", on a voice vote" / "" from a vote's codes."""
    m = _TALLY.search(raw)
    if not m:
        return ""
    kind = m.group(1).upper()
    if kind == "VV":
        return ", on a voice vote"
    words = {"RC": "on a roll call", "DV": "on a division vote"}[kind]
    if m.group(2) and m.group(3):
        return f", {m.group(2)}–{m.group(3)} {words}"
    return f", {words}"


def _veto(outcome, raw):
    """A veto vote's words. THE TALLY IS THE OVERRIDE'S (the review of 16
    October 2026). Everywhere else "<outcome>, Y–N" gives the votes FOR that
    outcome, so "Veto sustained, 176–175" read as the House sustaining the
    veto 176 to 175, where 176 voted to override and the override failed only
    for want of two thirds -- 195 lines of the record, 21 of them this term's
    (HB 358 is that one). So a sustained veto's count is named as the
    override's, in the words the bill's passage rail already gives the same
    vote ("Veto sustained, 176–175 to override, short of two thirds"). An
    overridden veto's yeas are the outcome's own, and read as they always did."""
    if outcome.lower() != "sustained":
        return "Veto overridden" + _how(raw)
    t = _TALLY.search(raw)
    if t and t.group(1).upper() in ("RC", "DV") and t.group(2) and t.group(3):
        words = {"RC": "on a roll call", "DV": "on a division vote"}[t.group(1).upper()]
        return f"Veto sustained, {t.group(2)}–{t.group(3)} to override {words}, short of two thirds"
    return "Veto sustained" + _how(raw)


def _sentence(s):
    s = s.replace("{Bill} ", "Bill ").replace("{Bill}", "Bill").strip()
    return s[:1].upper() + s[1:].lower() if s else s


def _motion_words(raw, carried, bill="", body=""):
    """The approved head for a floor motion's outcome, or "" for one the
    words do not name (then the caller falls back to the clerk's line)."""
    got = M.classify(raw, bill, body)
    row = VOTES["motions"].get(got.get("mk") or "")
    if not row:
        return ""
    said = row.get("passed" if carried else "failed") or ""
    if said and "{" not in said.replace("{Bill}", ""):
        return _sentence(said)
    gloss = (row.get("gloss") or "").strip()
    if not gloss or "{" in gloss:
        return ""
    return f"Motion to {gloss[:1].lower() + gloss[1:]} {'carried' if carried else 'failed'}"


# A committee's recommendation, in the gloss of the motion it recommends --
# but interim study by its name, the words a reader meets on every page.
def _rec(rec):
    got = M.classify(rec or "")
    if got.get("mk") == "is":
        return "send the bill to interim study"
    row = VOTES["motions"].get(got.get("mk") or "")
    gloss = (row or {}).get("gloss") or ""
    return gloss[:1].lower() + gloss[1:] if gloss and "{" not in gloss else ""


# THE LINES narrative.classify KEEPS AS "other" or reads too coarsely for a
# sentence, read here first (14 October 2026, from 865 docket lines of 89
# bills of 2025-2026, of which these were most of the 13% left as written).
# Each answers (match) -> words, or "" to fall through.
_AMEND = re.compile(
    r"^(?:(?P<who>(?:Sen|Rep)\.\s+[\w.' -]+?)\s+)?(?P<what>Committee Amendment|Floor Amendment|FLAM|"
    r"Enrolled Bill Amendment|Amendment)\s*#?\s*(?P<num>(?:\d{4}-)?\d+[a-z]*)"
    r"(?:\s*\(NT\))?(?:\s*\((?P<by>(?:Rep|Sen)s?\.[^)]*)\))?[\s,:;]*"
    # The Senate's clerk puts a roll call before the outcome: "Sen. Rosenwald
    # Floor Amendment # 2025-2660s, RC 8Y-16N, AF" (15 October 2026); _how
    # reads the count from the whole line either way.
    r"(?:(?:RC|DV)\s*\d+\s*Y?\s*-\s*\d+\s*N?[\s,:;]*)?"
    r"(?P<out>AA|AF|Adopted|Failed)\b", re.I)
_SIMPLE = [
    (re.compile(r"^Died on (?:the )?Table\b", re.I), lambda m, r: "Died on the table when the session ended"),
    # The history's words for the same row (narrative.SENATE_RULE_KILL_RE),
    # and the status chip's, "Died on the table" (15 October 2026).
    (re.compile(r"^Inexpedient\s+to\s+Legislate,?\s*(?:\d{4}\s+Adjournment,?\s*)?Senate\s+Rule\s+3-23\b",
                re.I),
     lambda m, r: "Died on the table under Senate Rule 3-23"),
    (re.compile(r"^Referred to (?!Interim)(?P<c>[A-Z][\w ,&]+?)\s+\d{1,2}/\d{1,2}/\d{4}", re.I),
     lambda m, r: f"Referred to {m.group('c')}"),
    (re.compile(r"^Referral Waived by Committee Chair", re.I),
     lambda m, r: "Its second committee's chair waived the referral"),
    (re.compile(r"Removed from (?:the )?Consent", re.I),
     lambda m, r: "Removed from the consent calendar, to be debated"),
    # The Senate's clerk writes the same meeting the other way round.
    (re.compile(r"^(?:Committee of Conference|Conference Committee) Meeting\s*:", re.I),
     lambda m, r: "Committee of conference meeting" + _where(r)),
    # 15 OCTOBER 2026, from the 1,066 lines of the session's docket still left
    # as written: the kinds below say what lines already said here say, in the
    # same words. The Senate's own forms of a hearing, a conferee change and a
    # resolution's adoption (_introduced, which needs the bill and the line
    # after it); and a report that recommends nothing.
    #
    # A TWO-DIGIT YEAR IS A YEAR (16 October 2026). The Senate's clerk wrote
    # "Hearing: 3/29/11, Room 102, LOB, 10:00 a.m.; SC17" from 2011 to 2015,
    # and a rule that wanted four digits left those rows as written: 2,459 of
    # them as the build reads them (listed_line, the clerk's flags out but a
    # cancel mark kept), each counted once though three dockets on disk hold
    # 2015. 269 of those carry a flag in the middle ("=== RESCHEDULED ===",
    # "=== TIME CHANGE ===", "=== RECESSED ===", "=== RECONVENE ===") and read
    # as such a row of four digits already did; a cancelled one is still no
    # hearing.
    (re.compile(r"^Hearing\s*:\s*\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})(?!\d)", re.I),
     lambda m, r: "Public hearing" + _where(r)),
    # A veto vote, in the House's form and the Senate's ("Notwithstanding the
    # Governor's Veto, Shall SB 213 Become Law: RC 0Y-24N, Veto Sustained"), in
    # votes.json's words for it -- "Veto Sustained", "Overridden in the
    # {Chamber}" -- without the chamber, which the line does not give; and
    # never "became law", which one chamber's override does not make it.
    (re.compile(r"^(?:Notwithstanding the Governor's Veto\b.*?\b)?Veto\s+(?P<o>Sustained|Overridden)\b",
                re.I),
     lambda m, r: _veto(m.group("o"), r)),
    (re.compile(r"^(?:(?P<side>Majority|Minority)\s+)?Committee Report\s*:\s*Without Recommendation",
                re.I),
     lambda m, r: (f"{m.group('side')} committee report" if m.group("side") else "Committee report")
     + ": makes no recommendation"
     + (lambda v: f", {v.group(1)}–{v.group(2)}" if v else "")(_VOTE.search(r))),
    (re.compile(r"^Conference Committee Report\b.*?\b(?P<o>Adopted|Failed|Rejected)\b", re.I),
     lambda m, r: f"Conference committee report {m.group('o').lower()}" + _how(r)),
    (re.compile(r"^Conference Committee Report\b.*?\bNot (?:Signed Off|Filed)\b", re.I),
     lambda m, r: "The committee of conference filed no agreed report"),
    (re.compile(r"^Conference Committee Report\b.*?\bFiled\b", re.I),
     lambda m, r: "Conference committee report filed"),
    (re.compile(r"^Speaker Appoints\s*:\s*(?P<w>.+?)\s*(?:\d{1,2}/\d{1,2}/\d{4}|\(|$)", re.I),
     lambda m, r: f"The Speaker named the House conferees: {m.group('w').strip(' ;,')}"),
    (re.compile(r"^President Appoints\s*:\s*(?P<w>.+?)\s*(?:;|\(|\d{1,2}/\d{1,2}/\d{4}|$)", re.I),
     lambda m, r: f"The Senate President named the Senate conferees: {m.group('w').strip(' ;,')}"),
    (re.compile(r"^Conferee Change\s*[:;]\s*(?P<a>.+?)\s+Replaces\s+(?P<b>.+?)\s*"
                r"(?:;|\s\d{1,2}/\d{1,2}/\d{4}|$)", re.I),
     lambda m, r: f"Conferee changed: {m.group('a')} replaces {m.group('b')}"),
    (re.compile(r"^Interim Study Report\s*:\s*(?:(?P<no>Not )?Recommended for Future Legislation|"
                r"(?P<none>Without Recommendation))", re.I),
     lambda m, r: f"{STUDY['head']}: "
     + STUDY["said"]["without" if m.group("none") else "not" if m.group("no") else "rec"]
     + (lambda v: f", {v.group(1)}\u2013{v.group(2)}" if v else "")(_VOTE.search(r))),
    (re.compile(r"^(?P<who>(?:Sen|Rep)\.\s+[\w.' -]+?)\s+Moved\s+(?P<m>.+?)\s*;", re.I),
     lambda m, r: (lambda w: f"{m.group('who')} moved to {w[:1].lower() + w[1:]}" if w else "")(_rec(m.group("m")))),
    # 16 OCTOBER 2026: THE WORDS THE PERSON APPROVED for the kinds most often
    # left as written, each rule read against every docket on disk.
    #
    # The motion still before the Senate when it laid the bill on the table
    # (SB 20: "Ought to Pass: RC 23Y-0N, MA", "Sen. Gray Moved Laid on Table",
    # "Pending Motion OT3rdg"). Only the four motions the words were approved
    # for; "Pending Motion Ought to Pass with Amendment" and a pending
    # amendment stay as written.
    (re.compile(r"^Pending\s+Motion\s*[,:]?\s*(?P<m>OT3rdg|Ought\s+to\s+Pass|Inexpedient\s+to\s+Legislate|"
                r"Interim\s+Study)\s*(?=[;,(]|SJ\b|$)", re.I),
     lambda m, r: "Motion left pending: " + ("order the bill to a third reading"
                                             if m.group("m").lower() == "ot3rdg" else _rec(m.group("m")))),
    # A law in effect on several dates, one part to a row: "II. Remainder
    # Effective 06/10/2025", "I. Section 5 Effective 06/30/2025". THE DATE IS
    # THE LAW'S, NOT THE LINE'S: the line's own date is the day it was
    # entered, and is shown beside these words as every other line's is.
    (re.compile(
        r"^(?:[IVX]{1,4}\.\s*)?"
        r"(?:(?P<rest>Rem(?:ainder|aining)?\.?)"
        r"|Sec(?:tion|s)?s?\.?\s*(?P<nums>I|\d+(?:\s*(?:,\s*(?:and\s+|&\s*)?|-|&|\band\b|\bthrough\b)\s*\d+)*)"
        r"|(?P<part>Part\s+[IVX]{1,4})"
        r"|(?P<rsa>RSA\s+\S+(?:\s+[IVX]+(?:\([a-z]\))?)?,?\s+as\s+inserted\s+by\s+Section\s+\d+))"
        r"\s*,?\s*(?:of\s+this\s+act\s+)?(?:Effective|Eff\.?|shall\s+take\s+effect)\s*"
        r"(?:(?P<mo>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4}|\d{2})(?!\d)"
        r"(?:\s+at\s+(?P<at>\d{1,2}:\d{2}\s*[ap]\.?\s*m\.?))?"
        r"|as\s+prov(?:ided|\.)?\s+in\s+Sec(?:tion|\.)?\s*(?P<prov>\d+)(?:\s+of\s+this\s+act)?)"
        r"[\s.;,]*(?:[HS][JC]\s*\d+\w*)?\s*$", re.I),
     lambda m, r: _effective(m)),
    # Only the line that says nothing more: "The order of the floor
    # amendments should be as follows" (HB 400 of 2017) stays as written.
    (re.compile(r"^Without\s+Objection,?\s+the\s+Clerk\s+is\s+authorized\s+to\s+make\s+technical\s+and\s+"
                r"admin\w*\s+corrections\s+which\s+are\s+necessary\s+to\s+reflect\s+the\s+intent\s+of\s+the\s+"
                r"(?:Senate|House)(?:,?\s+Relative\s+to\s+Bills\s+and\s+Amendments\s+Passed\s+Today)?"
                r"\s*[,;]?\s*(?:MA\b|$)", re.I),
     lambda m, r: "" if re.search(r"\bMF\b", r) else "The clerk may make technical corrections to the text"),
    # A bill taken from one committee and given to another: the House's
    # "Vacated and Referred to Finance (Rep. C. McGuire): MA VV" and the
    # Senate's "HB 517 is vacated from Judiciary and referred to Finance", in
    # the gloss the Votes tab gives the same motion.
    (re.compile(r"^(?:Without\s+Objection,?\s+)?(?:[A-Z]{2,5}\s*\d+(?:-[A-Z]+)*\s+is\s+)?Vacated\s+"
                r"(?:from\s+.+?\s+)?and\s+Referred\s+to\s+(?P<c>[A-Z][\w ,&'\-]*?)\s*"
                r"(?=\(|:|;|\s+M[AF]\b|\s+[HS]J\b|$)", re.I),
     lambda m, r: "" if re.search(r"\bMF\b", r) else
     "Moved to another committee, " + " ".join(m.group("c").split()) + _how(r)),
    # Law without the Governor's signature, in every form the dockets give
    # it, from "LAW WITHOUT SIGNATURE 4/17/89 EFF: 6/16/89 CHAP: 46" to
    # "Enacted in accordance with Article 44 Part II of the N.H. Constitution
    # without the signature of the governor".
    (re.compile(r"^(?:Became\s+)?Law\s+Without\s+Signature\b|^Passed\s+Without\s+Signature\b|"
                r"^Enacted\s+in\s+accordance\s+with\s+Article\s*44\b.*?\bwithout\s+the\s+signature\s+of\s+the\s+"
                r"governor", re.I),
     lambda m, r: "Became law without the Governor's signature"
     + (lambda c: f", chapter {int(c.group(1))}" if c else "")(_CHAPTER_ANY.search(r))),
    # Set for the next session day, where the vote words leave the line as
    # written: 189 lines, "Special Order to Next Session, Without Objection".
    # A LINE THE VOTE WORDS ALREADY READ KEEPS THEIR WORD (the review of 16
    # October 2026). 167 lines with the motion's "MA" read "Rescheduled",
    # which is votes.json's head for the same motion on the Votes tab, and
    # these words over them would give a reader two words for one vote.
    # Whether they too should read "Set for the next session day" is the
    # person's to say. A dated special order is "Rescheduled" either way.
    (re.compile(r"^(?:Without\s+Objection,?\s+)?(?:[A-Z]{2,5}\s*\d+(?:-[A-Z]+)*\s+is\s+)?Special\s+Order(?:ed)?\s+"
                r"(?:[A-Z]{2,5}\s*\d+(?:-[A-Z]+)*\s+)?to\s+(?:to\s+)?(?:the\s+)?Next\s+Session(?:\s+(?:Day|Date))?"
                r"(?:\s+in\s+(?:the\s+)?Regular\s+Calendar\s+Order)?\s*(?=[,;:(]|Without\b|[HS]J\b|$)", re.I),
     lambda m, r: "" if re.search(r"\bMF\b", r) or _vote_words(N.classify(r), r)
     else "Set for the next session day" + _how(r)),
    (re.compile(r"^The\s+Chair\s+ruled\s+the\s+Question\s+Divisible\b", re.I),
     lambda m, r: "The chair ruled the question could be divided"),
    # One amendment's sections only: "..., and the following Amendments
    # Non-Germane" (HB 1817 of 2018) names more than these words would.
    (re.compile(r"^Chair\s+Ruled\s+Sections\s+of\s+Amendment\s*#\s*(?P<a>(?:\d{4}-)?\d+[a-z]*)\s+Non-?Germane\b"
                r"(?=\s*[,;]?\s*(?:\d{1,2}/\d{1,2}/\d{2,4}|[HS]J\b|$))", re.I),
     lambda m, r: f"The chair ruled parts of amendment {m.group('a')} off the bill's subject"),
]

# A chapter however the clerk abbreviated it: "Chapter 86", "CHAP.0329",
# "Chap: 0024", "Chap- 0115", "Chapt:0099", "Chp. 0260", "CH.0066".
_CHAPTER_ANY = re.compile(r"\bCh(?:apter|apt|ap|p)?\s*[.:\-]?\s*(\d+)", re.I)

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December")


def _day(mo, d, y):
    """"06/10/2025" (or "07/06/15") as "June 10, 2025", or "" for no such
    day. A two-digit year is the century the rail reads it in (_j_iso)."""
    y = int(y)
    y += (1900 if y > 50 else 2000) if y < 100 else 0
    try:
        date(y, int(mo), int(d))
    except ValueError:
        return ""
    return f"{_MONTHS[int(mo) - 1]} {int(d)}, {y}"


def _sections(nums):
    """"1-3" -> "Sections 1 to 3", "7 & 8" -> "Sections 7 and 8", "5" ->
    "Section 5", "" where it is not plainly a list of numbers: the passage
    rail's words for the same parts (build_site_v2._j_sections). "1-3-5"
    stays unread there and here: one range or two numbers, it cannot say."""
    s = re.sub(r"\s*(?:-|\bthrough\b)\s*", "-", nums.strip(), flags=re.I)
    parts = [p for p in re.split(r"\s*(?:,|&|\band\b)\s*", s, flags=re.I) if p]
    if parts == ["I"]:
        parts = ["1"]
    if not parts or not all(re.fullmatch(r"\d+(?:-\d+)?", p) for p in parts):
        return ""
    if len(parts) == 1 and "-" not in parts[0]:
        return f"Section {parts[0]}"
    parts = [p.replace("-", " to ") for p in parts]
    return "Sections " + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0])


def _effective(m):
    """One part of a law's effective dates in words, from _SIMPLE's match:
    "The rest of the act takes effect June 10, 2025", "Sections 7 and 8 take
    effect January 1, 2027", "Section 8 takes effect as section 9 provides"."""
    if m.group("rest"):
        what = "The rest of the act"
    elif m.group("part"):
        what = "Part " + m.group("part").split()[-1].upper()
    elif m.group("rsa"):
        what = re.sub(r"\bas inserted by section\b", "as inserted by section", re.sub(r"\s+", " ", m.group("rsa")),
                      flags=re.I)
    else:
        what = _sections(m.group("nums") or "")
    if not what:
        return ""
    verb = "take" if what.startswith("Sections ") else "takes"
    if m.group("prov"):
        return f"{what} {verb} effect as section {m.group('prov')} provides"
    day = _day(m.group("mo"), m.group("d"), m.group("y"))
    if not day:
        return ""
    at = _TIME.search(m.group("at") or "")
    return f"{what} {verb} effect {day}" + (f", at {_clock(at)}" if at else "")


# "INTRODUCED AND ADOPTED" ON A BILL IS ITS INTRODUCTION WHEN ITS PASSAGE
# FOLLOWS (16 October 2026). A resolution is introduced and adopted in one
# motion, and the words say so. A bill let in after the deadline is written
# the same way, and the line means one of two things by what comes after it:
#
#   HB 2023 of 2022   "Introduced and Adopted: MA DV 259-66 By Necessary
#                     Two-Thirds Vote", then "Ought to Pass : MA VV". The
#                     journal gives 259-66 as the two-thirds vote to suspend
#                     the rules and let the bill in, and "Introduced and
#                     adopted, 259-66" read as the House passing it by that
#                     count. So it is "Introduced by a two-thirds vote,
#                     259-66 on a division vote". HB 3 and HB 4 of 2019 are
#                     the same, with "Ought to Pass" next.
#   HB 1703 of 2016   "Introduced and Adopted: MA RC 314-25 By Necessary
#                     Two-Thirds Vote", and no line after it. The journal
#                     (HJ 42) gives the suspension 253-87, then "Ought to
#                     Pass" 314-25 and third reading: the one line is the
#                     introduction and the passage, and 314-25 is the
#                     passage's. So it keeps "Introduced and adopted, 314-25
#                     on a roll call", as HB 1702 of 2016 keeps its own.
#
# The line alone cannot tell the two apart, so the caller passes the line
# after it (next_line); without one, a line reads as the whole of what it
# records, as it did before. Five lines on disk, all of them House bills.
_INTRO_ADOPTED = re.compile(r"^Introduced\s+and\s+Adopted\b", re.I)
_BILL = re.compile(r"^\s*(?:SS)?[HS]B\s*\d", re.I)
_PASSAGE = re.compile(r"^\s*Ought\s+to\s+Pass\b", re.I)


def _introduced(raw, bill, next_line=""):
    """The words for an "Introduced and Adopted" line: a bill's introduction,
    by two thirds where the line says the vote needed them, where the vote
    on its passage is the next line; else "Introduced and adopted", which is
    a resolution's adoption and a bill's introduction and passage in one."""
    if not (_BILL.match(bill or "") and _PASSAGE.match(next_line or "")):
        return "Introduced and adopted" + _how(raw)
    two_thirds = re.search(r"\btwo[- ]thirds\b|\b2/3\b", raw, re.I)
    return "Introduced" + (" by a two-thirds vote" if two_thirds else "") + _how(raw)


def _vote_words(d, raw, bill="", body=""):
    """A floor vote's words, from narrative.classify's reading of the line
    (d): votes.json's head for the motion's outcome and the count, or "" for
    a line that is not a floor vote or a motion the words do not name."""
    if d.get("_type") != "floor":
        return ""
    carried = (d.get("motion") or "").upper() == "MA"
    head = _motion_words(d.get("action") or raw, carried, bill, body)
    return head + _how(raw) if head else ""


def _amendment(raw):
    m = _AMEND.search(raw)
    if not m:
        return ""
    kind = {"committee amendment": "Committee amendment", "floor amendment": "Floor amendment",
            "flam": "Floor amendment", "enrolled bill amendment": "Enrolled bill amendment"}.get(
        m.group("what").lower(), "Amendment")
    who = m.group("who") or m.group("by")
    out = "adopted" if m.group("out").upper() in ("AA", "ADOPTED") else "failed"
    return f"{kind} {m.group('num')}" + (f" ({who.strip()})" if who else "") + f" {out}" + _how(raw)


def plain(raw, bill="", body="", next_line=""):
    """The line in plain words, or "" where it is of a kind not known here.
    next_line is the bill's docket line after this one, where the caller has
    the docket (_introduced)."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.upper().startswith("==CANCELLED=="):
        return ""
    words = _amendment(raw)
    if words:
        return words
    if _INTRO_ADOPTED.search(raw):
        return _introduced(raw, bill, next_line)
    for pat, say in _SIMPLE:
        m = pat.search(raw)
        if m:
            words = say(m, raw)
            if words:
                return words
    d = N.classify(raw)
    k = d.get("_type")
    if k == "introduced":
        return f"Introduced and referred to {d['committee'].strip()}"
    if k in ("hearing", "nongermane_hearing"):
        return "Public hearing" + _where(raw)
    if k == "exec":
        return "Executive session" + _where(raw)
    if k == "worksession":
        kind = re.sub(r"\s+", " ", d.get("kind") or "Work Session").strip()
        return kind[:1].upper() + kind[1:].lower() + _where(raw)
    if k == "report":
        side = (d.get("side") or "").lower()
        side = "Majority " if side.startswith("major") else "Minority " if side.startswith("minor") else ""
        what = _rec(d.get("rec"))
        if not what:
            return ""
        amd = _AMD.search(raw)
        v = _VOTE.search(raw)
        out = f"{side}committee report: {what}"
        out = out[:1].upper() + out[1:]
        if amd and "amend" in (d.get("rec") or "").lower():
            out += f" (amendment {amd.group(1)})"
        if v:
            out += f", {v.group(1)}–{v.group(2)}"
        if re.search(r"[;,(]\s*CC\b", raw):
            out += ", for the consent calendar"
        return out
    if k == "floor":
        return _vote_words(d, raw, bill, body)
    if k == "governor":
        w = (d.get("what") or "").lower()
        if w.startswith("signed"):
            ch = _CHAPTER.search(raw)
            return "Signed by the Governor" + (f", chapter {int(ch.group(1))}" if ch else "")
        if w.startswith("vetoed"):
            return "Vetoed by the Governor"
        if w.startswith("sent"):
            return "Sent to the Governor"
        return ""
    if k == "enrolled":
        return "Enrolled: the final text checked before it goes to the Governor"
    if k == "retained":
        return "Retained in committee"
    return ""


# THE ROOM AND THE MOTION, FOR THE EMAIL'S OWN LINES (17 October 2026, the
# language sweep). The week ahead printed the clerk's "GP 231", and a
# legislator's roll call "On OTPA", where every line above them in the same
# email already said "Granite Place 229" and the vote words. These are the
# same words, for the two fields the changes files carry on their own.
#
# THE ROOM AS THE SCHEDULE TYPES IT, NOT ONLY AS IT SHOULD (the review of 17
# October 2026). 2025-2026's committee days and upcoming rows hold, beside
# "GP 231", the same rooms run together ("GP231", "GP153"), the Office
# Building with a letter too many ("LOBO 202-204"), a building alone ("LOB"),
# and the House chamber three ways ("SH Reps Hall", "SH Representatives
# Hall", "Reps Hall"), which the docket elsewhere writes "Representatives'
# Hall, SH". Each is the room it plainly is.
#
# AND THE DATABASE'S "GP Room 230" (the audit of 25 October 2026, S7), which
# the Calendar and a committee's Meets In print beside the docket's "GP 230"
# for the same room: "Granite Place 230", as the docket's is. app.js's
# roomWords is this rule in the browser, held to it by preflight.
#
# AND "Rm" (26 October 2026): the Senate committees' own record gives the
# room they meet in as "SH Rm 100", "SH Rm 122-123" and "SL Rm Map Room",
# and their pages said Meets In "SH Rm 100" where a hearing of theirs says
# "State House 100". A named room, the State Library's Map Room, is _named's.
_PLACE_BLDG = re.compile(r"\b(LOBO|LOB|SH|GP|SL) ?(?:Room |Rm\.? ?)?([0-9][0-9A-Za-z\-]*)\b(?!:)")
_PLACE_ALONE = re.compile(r"^(LOBO|LOB|SH|GP|SL)$")
_REPS_HALL = re.compile(r"^(?:SH,?\s+)?(?:Reps|Representatives)'?\s+Hall(?:,?\s*SH)?$", re.I)
_PLACE_BUILDINGS = dict(BUILDINGS, LOBO=BUILDINGS["LOB"])


def place(raw):
    """A meeting's room in the words the calendar uses: "GP 231", "GP231" and
    "GP Room 231" are "Granite Place 231", "Room 100, SH" is "Room 100, State
    House", "SH Reps Hall" is "Representatives' Hall, State House", "SL Map
    Room" and "Map Room, SL" are "State Library Map Room". Anything else comes
    back as it was, spaces made single."""
    t = " ".join(str(raw or "").split())
    if _REPS_HALL.match(t):
        return "Representatives' Hall, State House"
    if _PLACE_ALONE.match(t):
        return _PLACE_BUILDINGS[t]
    t = _named(t)
    t = _ROOM.sub(lambda m: f"Room {m.group(1).strip()}, "
                            f"{BUILDINGS.get(m.group(2).upper(), m.group(2))}", t)
    return _PLACE_BLDG.sub(lambda m: f"{_PLACE_BUILDINGS[m.group(1)]} {m.group(2)}", t)


# A MEETING THE DOCKET SETS, AS FACTS FOR THE EMAIL TO SAY (17 October 2026).
# The person, approving it that day: "emails can use plain words for hearing
# entries". An email printed the clerk's "Public Hearing: 10/14/2026 10:00 am
# LOB 305" under the day the notice was posted, and plain() above drops the
# meeting's own date, which is right where the line's date is the meeting's
# and wrong where it is the notice's. So this hands the email what the line
# says -- the kind of meeting, its day, its hour, its room in place()'s words
# and whether the clerk marked it rescheduled, recessed or cancelled -- and the
# email words it with its own dates. The site's docket and the feeds keep the
# clerk's line, which is the record.
#
# ANYTHING NOT UNDERSTOOD LEAVES THE LINE AS IT WAS. A mark this does not know
# ("==Executive Session To Follow==", "==Continued=="), a line that does not
# start with the meeting ("Retained Bill - Executive Session"), or a "room"
# that is a paragraph (the 2020-21 Zoom notices) answers None, and the email
# prints the line as before rather than words that leave something out.
_MARK = re.compile(r"=+\s*([A-Za-z][A-Za-z ]*?)\s*(?:\([^)]*\))?\s*=+")
_MARKS = {"CANCELLED": "cancelled", "CANCELED": "cancelled", "RESCHEDULED": "rescheduled",
          "RECESSED": "recessed", "TIME CHANGE": "time changed", "ROOM CHANGE": "room changed"}
_MEETING = re.compile(
    r"^(?:Public Hearing on non-germane Amendment\s*#\s*(?P<amd>(?:\d{4}-)?\d+[a-z]*)"
    r"|(?P<hearing>Public Hearing|Hearing)|(?P<exec>Executive Session)"
    r"|(?:(?P<part>Full Committee|Subcommittee|Division [IVX]+)\s+)?(?P<work>Work Session)"
    r"|(?P<conf>Conference Committee Meeting|Committee of Conference Meeting))\s*:\s*", re.I)
_ON = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])[\s,]*")
# The Senate's calendar reference after the room: "; SC17", "SC 12, Pg.8".
_SENATE_CAL = re.compile(r"[;,]?\s*SC\s*\d+[A-Z]?(?:\s*,?\s*Pg\.?\s*\d+)?\s*$", re.I)
_ROOMLIKE = re.compile(r"^[\w' .,\-]{1,60}$")


def meeting(raw):
    """A docket line that sets a meeting, as {"what", "date", "time"?,
    "venue"?, "state"?}, or None for any other line. "what" is the kind in
    lower case ("public hearing", "executive session", "full committee work
    session"), "date" YYYY-MM-DD, "time" HH:MM on a 24-hour clock, "venue" the
    room as place() spells it, and "state" one of rescheduled, recessed,
    cancelled, time changed, room changed."""
    t = " ".join(str(raw or "").split())
    states = []

    def mark(m):
        states.append(_MARKS.get(" ".join(m.group(1).upper().split())))
        return " "
    t = " ".join(_MARK.sub(mark, t).split())
    if None in states or len(set(states)) > 1:
        return None
    k = _MEETING.match(t)
    if not k:
        return None
    if k.group("amd"):
        what = f"public hearing on non-germane amendment {k.group('amd')}"
    elif k.group("hearing"):
        what = "public hearing"
    elif k.group("exec"):
        what = "executive session"
    elif k.group("work"):
        part = (k.group("part") or "").split()
        part = [w.lower() if not re.fullmatch(r"[IVX]+", w) else w for w in part]
        what = " ".join(part + ["work session"])
    else:
        what = "committee of conference meeting"
    rest = t[k.end():]
    on = _ON.match(rest)
    if not on:
        return None
    year = int(on.group(3)) + (2000 if len(on.group(3)) == 2 else 0)
    try:
        day = date(year, int(on.group(1)), int(on.group(2))).isoformat()
    except ValueError:
        return None
    rest = rest[on.end():]
    out = {"what": what, "date": day}
    hour = _TIME.search(rest)
    if hour:
        h = int(hour.group(1))
        if not 1 <= h <= 12:
            return None
        out["time"] = f"{h % 12 + (12 if hour.group(3).lower() == 'p' else 0):02d}:{hour.group(2)}"
        rest = rest[:hour.start()] + " " + rest[hour.end():]
    room = " ".join(_SENATE_CAL.sub("", rest.strip(" ,;")).strip(" ,;").split())
    room = re.sub(r"\s+,", ",", room)
    if room:
        if not _ROOMLIKE.match(room) or _TIME.search(room) or _ON.match(room):
            return None
        out["venue"] = place(room)
    if states:
        out["state"] = states[0]
    return out


def motion_words(raw, bill="", body=""):
    """A floor motion as a vote card heads it (votes.json, the person's rule of
    8 October 2026): the motion's own name, then in brackets the abbreviation
    where it has one and a plain gloss -- "Ought to Pass with Amendment (OTPA,
    Pass the bill with changes)". "" for a motion the words do not name, and
    the caller keeps the record's own. `bill` is "HB1681", `body` "H" or "S"."""
    row = VOTES["motions"].get(M.classify(raw or "", bill, body).get("mk") or "")
    name = (row or {}).get("motion") or ""
    if not name or "{" in name:
        return ""
    gloss = (row.get("gloss") or "").strip()
    gloss = "" if "{" in gloss else gloss
    abbr = f"{row['abbr']}, " if row.get("abbr") and gloss else (row.get("abbr") or "")
    return name + (f" ({abbr}{gloss})" if gloss or abbr else "")


if __name__ == "__main__":
    for line in sys.argv[1:] or sys.stdin.read().splitlines():
        print(f"{line}\n  -> {plain(line) or '(as written)'}")
