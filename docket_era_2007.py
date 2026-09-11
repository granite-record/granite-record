#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.1
"""
The 2007-2016 docket's own vocabulary, mapped onto narrative.py's events.

Read by docket_vocab.py and by nothing else. By this decade the clerks write
almost the modern vocabulary -- and almost never the trailing four-digit date
every modern pattern requires:

    Inexpedient to Legislate: MA VV
    Ought to Pass, MA, VV; OT3rdg
    Committee Report; Ought to Pass [04/17/08]; SC19
    Executive Session: 3/12/08 10:00 AM LOB 305
    Committee Amendment{1234}, AA, VV

So these patterns are the modern ones with the date made optional and the
punctuation loosened, and they run only on lines narrative.PATTERNS leaves
as "other": 48.1% of 102,863 rows are already recognised, and these take it
to 89.8%.

The date those lines do not carry is the row's own timestamp, which for a
floor vote is the same day 90.3% of the time (5,091 of 5,641 measured
against the calendar the report names), later by a week or more on 114.
"""

import re

MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
D_NUM = r"\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})\b"
D_ANY = rf"(?:{D_NUM}|{MON}\s+\d{{1,2}}\s*,?\s*\d{{4}})"
# "=== TIME CHANGE ===", "= =", "==Continued==" between a label and its date
JUNK = r"(?:[=\s]*[A-Za-z][A-Za-z &()]*?\s*=+\s*)*[=\s]*"
NOCANCEL = r"(?!.*cancel)"

ERA = [
    # ---------------------------------------------------------- introduced
    # "Introduced and ref to Commerce (4/11/07)": the trailing date is the
    # session day, 2-7+ days before the row was entered (128 of 131 lines).
    ("introduced", re.compile(
        r"^Introduced\b\s*(?:\((?:in\s+recess\b[^)]*|Approved\s+by\s+Rules\s+Comm\w*)\)\s*)?,?\s*"
        r"and\s+(?:Referred|Ref)\.?\s+to\s+(?P<committee>[^;(\[]+?)\s*[(\[]\s*(?:in\s+recess\s+of\s+)?"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s*[)\]]", re.I)),
    ("introduced", re.compile(
        r"^(?:Rules\s+Comm\w*\s+Approved\s*:\s*)?Introduced\b\s*"
        r"(?:\((?:in\s+recess\b[^)]*|Approved\s+by\s+Rules\s+Comm\w*)\)\s*)?"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})?\s*,?\s*"
        r"and\s+(?:Referred|Ref)\.?\s+to\s+(?P<committee>[^;(\[]+?)\s*(?:[;(\[].*)?$", re.I)),
    ("introduced", re.compile(
        r"^Late\s+Drafting\s*(?:&|and)\s*Intro\w*\s+Approved\s+by\s+Rules\s+Comm\w*\s*:\s*"
        r"(?:Referred|Ref)\.?\s+to\s+(?P<committee>[^;(\[]+?)\s*(?:[;(\[].*)?$(?P<date>)", re.I)),
    # "Vacated from Transportation and Referred to Public Works and Highways"
    ("vacated", re.compile(
        r"^Vacated\s+from\s+[^;]+?\s+and\s+Referred\s+to\s+(?P<committee>[^;(]+?)\s*(?:[;(].*)?$", re.I)),
    # ---------------------------------------------------------- meetings
    ("hearing", re.compile(
        rf"^{NOCANCEL}{JUNK}(?:(?:Continued|Rescheduled|DIV\.?\s+[IVX]+)\s+)?"
        rf"(?P<kind>Public\s+Hearing|Hearing)(?:\s+on\s+[A-Za-z\- ]{{0,40}}?)?\s*[:;,]?\s*{JUNK}(?:Hearing\s*[:;]\s*)?"
        rf"(?P<date>{D_ANY})", re.I)),
    ("exec", re.compile(
        rf"^{NOCANCEL}.*?\bEx(?:e)?cutive\s+Se(?:s+|es)ion\b[^:0-9]{{0,60}}:?\s*{JUNK}"
        rf"(?P<date>{D_NUM})", re.I)),
    ("worksession", re.compile(
        rf"^{NOCANCEL}.*?\b(?P<kind>Work\s+Session|Subcom\w*\s+Session)\b[^:]{{0,90}}:\s*{JUNK}"
        rf"(?P<date>{D_NUM})", re.I)),
    ("conference_meeting", re.compile(
        rf"^{NOCANCEL}.*?\b(?:Committee\s+of\s+Conference|Conference\s+Committee|"
        rf"Conference\s+of\s+Committee|C\s*of\s*C)\s+Meeting\b\s*(?:=+[A-Za-z ]+=+\s*)?"
        rf"[:;]\s*{JUNK}(?P<date>{D_ANY})", re.I)),
    # ---------------------------------------------------------- committee report
    # Side only when spelled out: report_side() needs "major"/"minor" at the
    # start, and "Maj"/"Min" would be read as the whole committee.
    ("report", re.compile(
        r"^[=\s]*(?:Corrected\s+)?(?:(?P<side>Majorit\w*|Minorit\w*)\s+)?"
        r"Comm(?:ittee)?\.?\s+R(?:eport|ept|pt)\s*[:;]\s*"
        # Words only, and "with" only as "with Amendment(s)": "Ought to Pass
        # with AM #2591h", "with Ammendment" and "Ought to Pass Amended" would
        # otherwise reach RECOMMENDATION as plain "ought to pass" -- "pass it",
        # losing "with changes". Those stay unrecognised instead.
        r"(?P<rec>(?:(?!with\b|Amended\b)[A-Za-z'\-]+|with\s+Amendments?)"
        r"(?:\s+(?:(?!with\b|Amended\b)[A-Za-z'\-]+|with\s+Amendments?))*?)"
        rf"(?=\s*(?:#|\{{|\[|\(|\bfor\s+{MON}\s+\d|\d{{3,4}}[a-z]*\b|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|[,;]|\bVote\b|$))"
        r"(?P<rest>.*)$", re.I)),
    ("interim_report", re.compile(
        r"^Interim\s+Study\s+Report\s*:\s*"
        r"(?P<rec>(?:Not\s+)?Recommended\s+for\s+(?:Future\s+)?Legislation(?:\s+in\s+\d{4})?)\s*"
        r"(?:\(\s*Vote\s*(?P<y>\d+)\s*-\s*(?P<n>\d+)\s*;?\s*(?P<cal>CC|RC)?\s*\))?", re.I)),
    # ---------------------------------------------------------- amendments
    # The outcome is REQUIRED: describe() says "rejected" for anything that is
    # not AA/Adopted, so a line with no outcome must not reach it.
    ("amendment", re.compile(
        r"^(?:(?P<mover>Sen\.\s+(?:(?!Enrolled\b|Committee\b|Floor\b|Amendment\b|Moved\b)"
        r"[A-Z][\w'\u2019.\-]*\s+){1,3}))?"
        r"(?:Adopt\s+)?"
        r"(?P<what>(?:Enrolled\s+Bill\s+|(?:Majority\s+|Minority\s+)?Committee\s+|Floor\s+)?"
        r"(?:Amendment|AM))\b\s*"
        r"(?:\((?:\d\w*\s+)?(?:New\s+Title|NT)\)\s*)?"
        r"[#{(]?\s*(?P<num>(?:\d{2,4}-)?\d{3,4}[a-z]*)\s*[})]?"
        r"(?:[\s,;:]*(?:\((?:\d\w*\s+)?New\s+Title\)|\(NT\)|NT\b|\((?:Rep|Sen)s?\.?\s[^)]*\)"
        r"|[#{]?\d{4}[a-z]*\}?))*"
        r"[\s,;:]*"
        r"(?:(?:(?P<motion>AA|AF|AL|Adopted|Failed|Lost)\b|(?P<vote>VV|DV|DIV|RC)\b"
        r"|Div(?:ision)?\.?|(?P<y>\d+)\s*Y?\s*-\s*(?P<n>\d+)\s*N?\b)[,;:\s]*){1,4}"
        r"(?(motion)|(?!))"
        r"[,;\s]*(?:\(?\s*in\s+recess(?:\s+of)?\s*)?(?P<date>\d{1,2}/\d{1,2}/\d{4})?", re.I)),
    # ---------------------------------------------------------- floor
    # A floor action needs its result: MA/MF/ML must be present.
    ("floor", re.compile(
        r"^(?!.*\bNot\s+Voted\s+On\b)"
        # A reconsideration of a disposal is not the disposal: floor_disposed()
        # searches the action for "inexpedient to legislate" anywhere.
        r"(?!.*\bReconsider\w*\b.{0,40}\b(?:Inexpedient|Indefinite|Interim)\b)"
        r"(?P<action>[A-Za-z(].+?)\s*[:,;]?\s*"
        # A tally counts only straight after its vote kind, so "Sec.1-5" is not one.
        r"(?:(?:(?P<motion>MA|MF|ML)\b"
        r"|(?P<vote>VV|DV|RC|DIV|Div(?:ision)?)\b\.?"
        r"(?:\s*\(?\s*(?P<y>\d+)\s*Y?\s*-\s*(?P<n>\d+)\s*N?\)?)?|=)[,;:\s]*){1,5}"
        r"(?(motion)|(?!))"
        r"(?:OT\s*\d\s*rdg[,;\s]*)?"
        r"(?:Refer(?:red)?\s+to\s+(?P<refer>[A-Z][A-Za-z ]+?)(?:\s*\[?\s*Rule\s*[\d\-]+\s*\]?)?)?"
        # the modern shape carries its date straight after the vote
        r"[,;\s]*(?:\(?\s*in\s+recess(?:\s+of)?\s*)?(?P<date>\d{1,2}/\d{1,2}/\d{4})?",
        re.I)),
    # ---------------------------------------------------------- other endings
    ("died", re.compile(r"^Died\s+on\s+(?:the\s+)?Table\b", re.I)),
    # "Referred to Judiciary for Interim Study" is the docket's echo of the
    # floor vote already read as floor; left verbatim rather than filed as a
    # committee called "Judiciary for Interim Study".
    ("rereferred", re.compile(
        r"^(?!.*\bfor\s+Interim\s+Study\b)Refer(?:red)?\s+to\s+"
        r"(?P<committee>(?!Interim\b)[A-Z][A-Za-z,&'\-\s]+?)"
        r"(?:\s*\[?\s*Rule\s*[\d\-()a-z]+\s*\]?)?\s*(?:[;(].*)?$(?P<date>)", re.I)),
    ("consent_off", re.compile(
        r"^(?:Removed\s+from\s+(?:the\s+)?Consent\b"
        r"|Sen\.\s+[A-Z][\w'.\-]*(?:\s+[A-Z][\w'.\-]*)?\s+Moved\s+to\s+Remove\s+[A-Z]+\s*\d+\s+from\s+the\s+Consent\s+Calendar)"
        r"(?:[^0-9]*?(?P<date>\d{1,2}/\d{1,2}/\d{4}))?",
        re.I)),
    ("veto_override", re.compile(
        r"^(?=(?:.*?\b(?P<vote>RC|DIV|DV|VV)\s*\(?\s*(?P<y>\d+)\s*Y?\s*-\s*(?P<n>\d+))?)"
        r"(?:Notwithstanding\s+the\s+Governor[\u2019']?s\s+Veto,?\s*Shall\s+(?:the\s+Bill|[A-Z]+\s*\d+)"
        r"\s+(?:Become\s+Law|Pass)|Shall\s+[A-Z]+\s*\d+\s+Become\s+Law|Governor[\u2019']?s(?=\s+Veto))"
        r".*?\bVeto\s+(?P<outcome>Sustained|Overridden)\b", re.I)),
]


# -------------------------------------------------------------- joining
ROMAN = re.compile(r"^[IVX]{1,5}\s*\.\s*\S")
RESULT_ONLY = re.compile(r"^(?:MA|MF|ML|AA|AF|AL|Motion\s+(?:Adopted|Failed|Lost))\b", re.I)
LOWER = re.compile(r"^[a-z]")
HAS_RESULT = re.compile(r"\b(?:MA|MF|ML|AA|AF|AL|Adopted|Failed)\b")
GAP_RESULT = 120        # every bare-result continuation measured was within 120 s (16/16)
GAP_LOWER = 86400       # lowercase continuations measured up to 11,206 s apart


def join_rows(rows):
    """rows: list of (created datetime, bill, body, desc) in docket order.
    Returns the joined list and a list of (before, after, joined, gap) examples.
    The joined row keeps the FIRST piece's created time; the gap is measured
    from the LAST piece joined."""
    out, joins, last = [], [], None
    for r in rows:
        created, bill, body, desc = r
        if out:
            pc, pb, pbody, pdesc = out[-1]
            gap = (created - last).total_seconds()
            same = pb == bill and pbody == body and gap >= 0
            lower = LOWER.match(desc) and gap <= GAP_LOWER
            # A bare result joins only a row that has no result of its own:
            # "...MF, RC 7Y-16N: SJ 10" is complete, and its colon is a typo.
            result_for_open = (RESULT_ONLY.match(desc) and not HAS_RESULT.search(pdesc)
                               and gap <= GAP_RESULT)
            if same and (lower or result_for_open):
                new = (pc, pb, pbody, pdesc.rstrip() + " " + desc.strip())
                joins.append((pdesc, desc, new[3], gap))
                out[-1] = new
                last = created
                continue
        out.append(r)
        last = created
    return out, joins


# The dispatcher's contract. Nothing here runs before narrative.PATTERNS:
# this era's lines are the modern vocabulary, so a modern match is right.
FIRST = []
AFTER = [(f"2007:{t}", t, p, {}) for t, p in ERA]
ROUTINE = []


def normalise(ev, created):
    """The date these lines leave out is the row's own timestamp.

    Measured against the calendar day a committee report names: the same day
    on 5,091 of 5,641 floor lines, 1-7 days later on 348, more than a week
    later on 114 and earlier on 88. describe() crashes on a missing date
    (fdate catches ValueError, not TypeError), so every type it prints a date
    for gets one."""
    t = ev.get("_type")
    d = ev.get("date")
    if d and re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2}", d):      # 3/12/08
        mo, dy, yr = d.split("/")
        ev["date"] = f"{int(mo):02d}/{int(dy):02d}/{2000 + int(yr) if int(yr) < 50 else 1900 + int(yr)}"
    if not ev.get("date") and created is not None and t in (
            "introduced", "floor", "rereferred", "amendment", "enrolled",
            "consent_off", "veto_override", "died", "retained", "vacated"):
        ev["date"] = created.strftime("%m/%d/%Y")
    if (ev.get("vote") or "").upper() in ("DIV", "DIVISION"):
        ev["vote"] = "DV"
    return ev
