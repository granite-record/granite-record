#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-07.1
"""Every committee a chamber sent a bill to in a term, in the order the docket records it.

    import later_referrals as LR
    LR.chamber_referrals(events, "2025-2026")
        {"H": ["Education Funding", "Finance"], "S": ["Education"]}

`events` is one bill's history as narratives.json holds it: the clerk's own
docket lines, in order. No network and no file read; learn_numbers.py counts
the bills each committee received with it (F22, 7 October 2026).

WHY NOT referrals.py ALONE

referrals.py is the site's reader of the FIRST referral in each chamber --
the committee each bill's page names, and the committee pages list -- and it
deliberately ignores what comes after. A committee's workload is more than its
first referrals: the House sends a bill with a cost on to Finance or Ways and
Means after its policy committee (House Rule 47), and the Senate sends a bill
it has just voted to pass on to Finance (Senate Rule 24 before 2009, then 26,
now 4-5). This reads those as well, with referrals.py's own patterns for the
introduction, a referral on passage, a re-referral and a vacate, plus the
referrals written inside a line ("...; Refer to Finance Rule 4-5;", "COMM AM,
AA VV; PASSED WITH AM AND REF TO APPROP VV", "Recommitted to Finance").

WHAT IS NOT A REFERRAL HERE: a referral back to the committee that holds the
bill (retained, "re-referred to committee", interim study); a motion to refer
recorded as lost (ML or MF), or left pending when the bill was laid on the
table; a committee of conference; a name committee_names cannot place on a
committee that chamber had that term. Every name goes through
committee_names.official and must be one committee_names.known allows.

Measured first, read-only, from each term's own docket file (7 October 2026):
the first referral the site publishes agrees with the General Court's own
referral code for 49,370 of 49,497 bill-chambers, and where the database's
current committee differs from its referral committee, that committee is among
the referrals counted for 3,430 of 3,504.
"""

import re

import committee_names as CN
import referrals as R

PENDING = re.compile(r"\bpending\s+motion\b", re.I)
# A referral written inside a line: "...; Refer to Finance Rule 4-5;",
# "COMM AM, AA VV; PASSED WITH AM AND REF TO APPROP VV", "Taken off Table and
# Referred to X", "Recommitted to Finance, Rep Kurk MA VV".
INLINE = re.compile(
    r"(?:^|[;:,(]|\band\b|&)\s*(?:re-?)?(?:ref(?:er(?:red|ring)?|d)?|recommit(?:ted)?)\.?\s+to\s+"
    r"(?P<c>[^;\[\]]+)", re.I)
RULE_TAIL = re.compile(r"\s*\(?\b(?:senate\s+|house\s+)?rule\b.*$", re.I)
# "PASSED WITH AM AND REF TO FINANCE/CONSENT CAL RC(248-8)" (1997): passed on
# the consent calendar and referred to Finance.
CONSENT_TAIL = re.compile(r"\s*/\s*consent\s+cal\w*.*$", re.I)
STUDY = re.compile(r"\binterim\b|\bint\.?\s+study\b|\bstudy\b", re.I)
# Not a committee: back to the committee that has it, a conference, the table,
# a reading, a calendar.
NOT_NAME = re.compile(r"^\s*(?:the\s+)?(?:full\s+)?comm(?:ittee)?\b(?!\s+on)|"
                      r"conference|\b2nd\s+comm|second\s+comm|\btable\b|\breading\b|"
                      r"\bcalendar\b|governor", re.I)
TALLY = re.compile(r"[\s,]+(?:2/3\s*)?(?:DIV|DV|RC)\s*\(\s*\d+\s*-\s*\d+\s*\).*$", re.I)
LEAD = re.compile(r"^\s*the\s+committee\s+on\s+", re.I)
UNDER_RULES = re.compile(r"\s+(?:under|pursuant\s+to|per)\s+(?:house|senate)\s+rules?\b.*$", re.I)
# A row the clerk broke in the middle of a referral -- "PASSED WITH AM AND
# REF" then "TO FINANCE" -- is read with the chamber's next row.
DANGLE = re.compile(r"(?:\bref(?:er(?:red)?)?\.?|\bre-?referred|\bto|&|\band|,)\s*$", re.I)
# "ref Ways and Means   HJ 33,  pg 1795" (the House clerk of 2005-2006): no
# "to", anchored at the start, and never "ref for study".
BARE = re.compile(r"^\s*ref\.?\s+(?!to\b|for\b|interim\b|int\b)(?P<c>[^;\[\]]+)", re.I)


def place(raw, chamber, term):
    """The committee a referral names, as committee_names spells it, or None."""
    # A division or roll call that carried the motion, with its tally:
    # "REF TO FINANCE DIV(192-90)". Without the tally "DIV" stays, because the
    # Senate of 1993-1994 wrote "REF TO FIN DIV" for a division of its
    # finance committee, which is not a vote.
    s = R.clean(LEAD.sub("", TALLY.sub("", raw or "")))
    s = CONSENT_TAIL.sub("", RULE_TAIL.sub("", UNDER_RULES.sub("", s))).strip(" ,.;:)")
    if not s or STUDY.search(s) or NOT_NAME.search(s):
        return None
    return CN.known(CN.official(s, chamber, term), chamber, term) or None


def chamber_referrals(events, term):
    """{"H": [committee, ...], "S": [...]}: each committee the chamber sent
    the bill to in the term, once, in the order the docket first does."""
    rows = [((e.get("body") or "").upper()[:1], e.get("raw") or "") for e in events or []]
    rows = [(b, d) for b, d in rows if b in ("H", "S")]
    nxt, last = [None] * len(rows), {}
    for i in range(len(rows) - 1, -1, -1):
        nxt[i] = last.get(rows[i][0])
        last[rows[i][0]] = i
    out = {"H": [], "S": []}
    pending = {}
    for i, (body, desc) in enumerate(rows):
        ext = desc
        if DANGLE.search(desc) and nxt[i] is not None:
            ext = desc.rstrip() + " " + rows[nxt[i]][1].lstrip()
        got = []
        dangling = pending.pop(body, None)
        if dangling is not None:
            m = None if dangling else R.VACATE_NEXT.match(desc)
            raw = (desc if dangling and not R.HEARD.search(desc)
                   else m.group("c") if m else "")
            if raw:
                raw = re.sub(r"^\s*(?:the\s+)?(?:committee\s+on\s+)?", "", raw, flags=re.I)
                got.append(re.sub(r"\s+committee\b.*$", "", raw, flags=re.I))
        v = R.VACATED.search(desc)
        if v and not R.LOST.search(desc):
            got.append(v.group("c"))
        elif R.VACATE_WORD.search(desc) and not v and not R.LOST.search(desc) \
                and not R.NOT_TO_A_COMMITTEE.search(desc):
            pending[body] = R.DANGLING.search(desc) is not None
        for rx in (R.INTRO, R.PASSED, R.REREF, R.PLAIN, BARE):
            m = rx.match(ext)
            if m:
                got.append(m.group("c"))
                break
        for m in INLINE.finditer(ext):
            if m.start() >= len(desc) or PENDING.search(desc):
                continue
            # The clause the referral is written in, between semicolons: an
            # older clerk writes the motion that lost and the referral that
            # carried on one row ("REP ROSEN SUBST ITL, ML RC(65-266); PASSED
            # AND REF TO APPROP VV").
            a = ext.rfind(";", 0, m.start("c")) + 1
            b = ext.find(";", m.start("c"))
            if R.LOST.search(ext[a:b if b >= 0 else len(ext)]):
                continue
            got.append(m.group("c"))
        for raw in got:
            nm = place(raw, body, term)
            if nm and nm not in out[body]:
                out[body].append(nm)
    return out
