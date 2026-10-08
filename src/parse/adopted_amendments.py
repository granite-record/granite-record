#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-07.2
"""What a passed bill's docket says was done to its text, and which committees reported on it.

    import adopted_amendments as AA
    per, conference, enrolled = AA.chamber_amendments(events)
        per = {"H": {"amended": True, "n": 2}, "S": {"amended": False, "n": 0}}
    AA.reporting_committees(events, term)
        {"H": ["Education", "Finance"], "S": ["Finance"]}
    AA.credited_reports(events, term)
        [(report event, "H", "Finance"), ...]

`events` is one bill's history as narratives.json holds it. No network, no
file read: learn_numbers.py calls both for the Learn page of numbers.

WHERE THIS CAME FROM

The person asked on 7 October 2026 for the share of bills passed as
introduced against amended, and how many amendments a bill takes before it
passes (F18). It was measured first, read-only, over all nineteen terms, and
checked against two sources this project did not write: the General Court's
own HouseAmended and SenateAmended fields (PastLegislation, 1989-2024), with
which the chamber-by-chamber answer agrees in 20,725 of 20,776 comparisons
outside two terms whose flag was evidently not kept up; and the bill-text
versions ("As Amended by the House/Senate"), 2016 on, 6,325 of 6,326. The
reader below is that measurement's, moved here unchanged in what it counts.

WHAT COUNTS AS AN AMENDMENT

An amendment adopted on the floor of either chamber before the governor
acted: a committee amendment the chamber adopted, a floor amendment, a second
committee's amendment. Counted by number where the docket gives one
(2019-1397h, {3685}, <4906>); where it gives none -- most lines before 1999 --
once for each amendment a line names, so a divided question that adopts one
amendment in parts is one. An amendment adopted and then withdrawn or
defeated on reconsideration is dropped. A chamber that passed the bill "with
amendment", or whose amendment the other chamber concurred or non-concurred
in, with no adoption line of its own, counts one.

Not amendments here, and returned apart: the Enrolled Bills Committee's
technical correction after both chambers passed the bill (`enrolled`), and a
committee of conference's report (`conference`).

THE TWO GRADES OF EVIDENCE. From 2007 every adoption line carries the
amendment's number. Before 1999 adoption lines rarely do ("COMM AM, AA VV";
"FLOOR AMENDMENT INTRODUCED/ADOPTED"), so they are counted by what each line
names. The split between none, one and two is sound throughout; three and
more before 1999 is the part to state with care, and the page says so.

WHICH COMMITTEES REPORTED

A majority (or sole) committee report naming the committee, minority reports
left out, each committee once per bill and chamber, in the order they first
reported. A second committee's report is credited to the second committee:
narrative.py carries the committee of the last referral line forward to each
report, and before 2007 the line that sends a bill on to Appropriations or
Finance is usually a floor line ("PASSED WITH AM AND REF TO APPROP"), or the
report names its committee only in its own first words ("FIN MAJ REPORT
OTP/AM"), so HB 35 of 1991's Appropriations report was credited to Public
Works. Names go through committee_names.official, the site's one table.
"""

import re
from collections import Counter

# ---------------------------------------------------------------- patterns
EBA = re.compile(r"ENROLL", re.I)
CONF = re.compile(r"CONF(?:ERENCE)?\.?\s*COMM(?:ITTEE)?\.?\s*(?:REPORT|RPT)|C\s*OF\s*C\s*REPORT|"
                  r"COMMITTEE\s+OF\s+CONFERENCE\s+REPORT", re.I)
CONF_OK = re.compile(r"ADOPTED|\bMA\b|\bAA\b|ACCEPTED", re.I)
CONF_BAD = re.compile(r"FILED|SIGNED\b|REJECT|\bMF\b|\bML\b|FAIL|NOT\s+ADOPTED|INDEF", re.I)
AMWORD = re.compile(r"\bAM\b|AMEND\w*|W/AM\b|\bAMDT\b|\bFLAM\b|\bAM\.|\bAM\{|\bAM<|\bAM#|\bAM\d", re.I)
GONE = re.compile(r"\bAF\b|\bAL\b|FAILED|\bMF\b|WITHDR|NOT\s+ADOPTED", re.I)
ADOPT = re.compile(r"\bAA\b|\bADOPTED\b", re.I)
NOTADOPT = re.compile(r"\bAF\b|\bAL\b|FAILED|\bMF\b|\bML\b|NOT\s+ADOPTED|WITHDR|NOT\s+VOTED|"
                      r"LAID\s+ON|\bTABLE\b|RECONSID|RESCIND", re.I)
SKIP_LINE = re.compile(r"\bRULES?\b(?!.*\bAMEND\w*\s*(?:#|\{|<|\d))|PROPOSED|\bPROP\b|DEADLINE", re.I)
FLOOR_MA = re.compile(r"(?:FLOOR\s*AM\w*|FL\.?\s*AM\w*|FLAM)[^;]*?\bMA\b", re.I)
PASS_AM = re.compile(r"(?:PASSED(?:/ADOPTED)?|OUGHT\s+TO\s+PASS|\bOTP)\s*(?:/\s*)?(?:W/|WITH|AS|W)?\s*/?\s*AM|"
                     r"OUGHT\s+TO\s+PASS\s+AMENDED|\bOTPA\b|\bOTP/A\b|PASSED\s+W/\s*AM", re.I)
REPORTLINE = re.compile(r"^\s*(?:RE-?REF\s+)?(?:MAJ|MIN|COMM|FIN|COMMITTEE|MAJORITY|MINORITY|APPROP)"
                        r"\w*\.?\s*(?:\w+\s+)?(?:REPORT|REP|RPRT)\b", re.I)
CONCUR_OTHER = re.compile(r"(?<!NON)(?<!NON-)CONC(?:UR)?\w*\s+(?:WITH\s*|W/\s*)?(?:THE\s+)?"
                          r"(?P<who>SEN(?:ATE)?|HOUSE)\s*(?:AM|AMEND)", re.I)
NONCONCUR_OTHER = re.compile(r"NON-?CONC(?:UR)?\w*\s+(?:WITH\s*|W/\s*)?(?:THE\s+)?"
                             r"(?P<who>SEN(?:ATE)?|HOUSE)\s*(?:AM|AMEND)", re.I)

# Amendment numbers: 2019-1397h, #0429h, {3685}, <4906>, 1493s, {0257h}. An
# "e" suffix is an enrolled-bill amendment's.
NUM_PATS = [
    re.compile(r"(?:19|20)\d\d-\s?(\d{4})\s?([hse])\b", re.I),
    re.compile(r"[#{<]\s*(?:(?:19|20)\d\d-\s?)?(\d{3,4})\s?([hse]?)\s*[}>]?", re.I),
    re.compile(r"\b(\d{4})([hs])\b", re.I),
]


def _nums(clause):
    out = set()
    for p in NUM_PATS:
        for m in p.finditer(clause):
            if (m.group(2) or "").lower() == "e":
                continue
            out.add(int(m.group(1)))
    return out


def _clauses(raw):
    """The line split at semicolons -- except that a clause carrying an
    adoption token and no amendment word is joined to the clause before it:
    "Ought to Pass with Amendment {4559}; (New Title) AA, VV"."""
    out = []
    for c in re.split(r";", raw):
        if not c.strip():
            continue
        if out and ADOPT.search(c) and not AMWORD.search(c) and AMWORD.search(out[-1]) \
                and not ADOPT.search(out[-1]):
            out[-1] = out[-1] + " " + c
        else:
            out.append(c)
    return out


def chamber_amendments(events):
    """({"H": {"amended", "n"}, "S": {...}}, conference, enrolled) for one
    bill's docket events, read up to the governor's action."""
    adopted_nums = {"H": set(), "S": set()}
    adopted_bare = Counter()
    pass_am = set()
    pass_am_nums = {"H": set(), "S": set()}
    concur_other = set()
    conf = eba = False
    for e in events or []:
        if e.get("cancelled"):
            continue
        body = (e.get("body") or "").upper()[:1]
        if body not in ("H", "S"):
            continue
        typ = e.get("type") or ""
        u = e.get("raw") or ""
        if typ in ("hearing", "worksession", "exec", "conference_meeting", "report", "introduced"):
            continue
        # A committee's report is a recommendation, not an adoption -- but the
        # Senate of 1999-2000 wrote its floor action as "Committee Report
        # Ought to Pass with Amendment {4553}; AA, VV; OT3rdg, MA, VV".
        if REPORTLINE.search(u) and not re.search(r"\bAA\b|\bMA\b|ADOPTED|PASSED", u, re.I):
            continue
        if typ in ("governor", "unsigned_law"):
            break
        if CONF.search(u):
            if CONF_OK.search(u) and not CONF_BAD.search(u):
                conf = True
            continue
        if EBA.search(u):
            if AMWORD.search(u) and ADOPT.search(u) or (AMWORD.search(u) and re.search(r"\bMA\b", u)):
                eba = True
            continue
        for rx in (CONCUR_OTHER, NONCONCUR_OTHER):
            m = rx.search(u)
            if m:
                concur_other.add("S" if m.group("who").upper().startswith("SEN") else "H")
        line_keys = set()
        for c in _clauses(u):
            if SKIP_LINE.search(c) and not ADOPT.search(c):
                continue
            if re.search(r"\bRULES?\b", c, re.I) and not re.search(r"AMEND\w*\s*[#{<]|\bAM\s*[#{<]", c, re.I):
                # "AM TO HOUSE RULES ADOPTED", suspensions
                if not PASS_AM.search(c):
                    continue
            if CONCUR_OTHER.search(c) or NONCONCUR_OTHER.search(c):
                continue
            # A NUMBER ALREADY ADOPTED AND THEN WITHDRAWN OR DEFEATED is not
            # standing: HB 1179 of 2024's floor amendment 2162s was adopted,
            # reconsidered and withdrawn; SB 461 of 2018's 0996s was adopted
            # and the motion to pass the bill with it failed 12-12.
            if GONE.search(c) and not re.search(r"\bAA\b|\bADOPTED\b", c, re.I):
                for x in _nums(c):
                    adopted_nums[body].discard(x)
                if re.search(r"WITHDR", c, re.I) and not _nums(c) and adopted_bare[body]:
                    adopted_bare[body] -= 1
            has_am = bool(AMWORD.search(c))
            # "PASSED/ADOPTED WITH AM" is the bill passing, not an amendment
            # being adopted: the 1989 Senate writes the adoption on its own
            # line ("COMMITTEE AMENDMENT/ADOPTED") and then this one.
            passage_only = bool(PASS_AM.search(c)) and not re.search(r"\bAA\b", c) \
                and not re.search(r"AM\w*\s*[#{<(]?\s*\d", c, re.I) \
                and not re.search(r"(?:COMM(?:ITTEE)?|FL(?:OOR)?)\.?\s+AM\w*\s*(?:INTRO\w*\s*)?/?\s*ADOPTED",
                                  c, re.I)
            if has_am and ADOPT.search(c) and not passage_only \
                    and not (NOTADOPT.search(c) and not re.search(r"\bAA\b", c)):
                ns = _nums(c)
                if ns:
                    adopted_nums[body] |= ns
                else:
                    # NO NUMBER, so one adoption per amendment the clause
                    # names -- not per vote. A divided question adopts one
                    # amendment in parts: HB 35 of 1991's "COMM AM (SEC.
                    # 1,IV), AA RC(178-145); ... COMM AM (SEC. 1,V,B4), AA VV
                    # & (SEC 2,B), AA RC(231-94)" is the committee amendment
                    # once. Keyed by who offered it and what kind it is,
                    # within the one docket line.
                    for seg in re.split(r"(?<=\bAA\b)|(?<=ADOPTED)", c, flags=re.I):
                        if not ADOPT.search(seg) or not AMWORD.search(seg):
                            continue
                        who = re.search(r"\b(?:REPS?|SENS?)\.?\s+([A-Z][A-Z.' -]{1,30}?)\s+"
                                        r"(?:FL|FLOOR|AM|PROP|MOVED)", seg, re.I)
                        kind = ("FL" if re.search(r"\bFL\b|FL\.|FLOOR", seg, re.I) else
                                (re.search(r"(\w+)\s+(?:COMM(?:ITTEE)?\s+)?AM", seg, re.I)
                                 or [None, "AM"])[1].upper())
                        key = (kind, (who.group(1).strip().upper() if who else ""))
                        if key not in line_keys:
                            line_keys.add(key)
                            adopted_bare[body] += 1
            elif has_am and FLOOR_MA.search(c) and not NOTADOPT.search(c) and not re.search(
                    r"SPECIAL\s+ORDER|RECONSID", c, re.I):
                ns = _nums(c)
                if ns:
                    adopted_nums[body] |= ns
                else:
                    adopted_bare[body] += 1
            if PASS_AM.search(c) and not re.search(r"\bMF\b|\bML\b|FAILED|RECOMMIT|RECONSID|NOT\s+VOTED|"
                                                    r"LAID|TABLE|SPECIAL\s+ORDER", c, re.I):
                if re.search(r"\bMA\b|PASSED|ADOPTED|\bAA\b", c, re.I):
                    # Numbers named in an adopted passage motion were adopted.
                    ns = _nums(c)
                    if ns:
                        adopted_nums[body] |= ns
                        pass_am_nums[body] |= ns
                    else:
                        pass_am.add(body)
    per = {}
    for ch in ("H", "S"):
        if pass_am_nums[ch] & adopted_nums[ch]:
            pass_am.add(ch)
        n = len(adopted_nums[ch]) + adopted_bare[ch]
        amended = n > 0 or ch in pass_am or ch in concur_other
        # Passage "with amendment" or a concurrence and no adoption line: one.
        per[ch] = {"amended": amended, "n": max(n, 1) if amended else 0}
    return per, conf, eba


# ------------------------------------------------- which committees reported
SECOND = [
    (re.compile(r"APPROP\w*", re.I), "Appropriations"),
    (re.compile(r"FIN(?:ANCE)?\b(?:\s+(?:DIV\w*|EXEC\w*))?|FIN\.", re.I), "Finance"),
    (re.compile(r"WAYS\s*(?:&|AND)\s*MEANS|W\s*&\s*M\b", re.I), "Ways and Means"),
    (re.compile(r"CAP(?:ITAL)?\.?\s+BUDGET", re.I), "Capital Budget"),
    (re.compile(r"ED\s*&\s*A\b", re.I), "Executive Departments and Administration"),
]
REPORT_PREFIX = re.compile(r"^\s*(?:RE-?REF\s+)?(?:MAJ\.?\s+|MIN\.?\s+|MAJORITY\s+|MINORITY\s+)?(?P<c>.{2,25}?)\s+"
                           r"(?:COMM\s+)?(?:MAJ\w*\s+|MIN\w*\s+)?(?:COMM(?:ITTEE)?\s+)?(?:REPORT|REP|RPRT)\b", re.I)
SENT_ON = re.compile(r"(?:\bREF(?:ERRED|\.)?|\bREFER)\s+TO\s+(?P<c>[A-Z&.' ]{2,25})", re.I)


def _second_name(text):
    for rx, nm in SECOND:
        if rx.match(text.strip()):
            return nm
    return None


def credited_reports(events, term, official=None):
    """[(event, chamber, committee)]: every committee report in `events`,
    minority reports included, with the committee it is credited to ("" where
    none is named) -- a second committee's report to the second committee, as
    the module's notes say. `official(name, chamber, term)` puts a name in the
    site's spelling. Both of the Learn page's per-committee tables read
    reports through this, so that the consent table and the passage rates
    credit the same report to the same committee."""
    out = []
    first, sent = {}, {}
    for e in events or []:
        ch = (e.get("body") or "").upper()[:1]
        if e.get("cancelled"):
            continue
        if e.get("type") in ("introduced", "vacated"):
            sent.pop(ch, None)
        raw = e.get("raw") or ""
        if e.get("type") != "report":
            m = SENT_ON.search(raw)
            if m and e.get("type") != "introduced":
                nm = _second_name(m.group("c"))
                if nm:
                    sent[ch] = nm
            continue
        own = REPORT_PREFIX.match(raw)
        own_nm = _second_name(own.group("c")) if own else None
        name = (e.get("committee") or "").strip()
        if ch in ("H", "S") and name and ch not in first:
            first[ch] = name
        if own_nm:
            name = own_nm
        elif sent.get(ch) and name == first.get(ch):
            name = sent[ch]
        if official and ch in ("H", "S") and name:
            name = official(name, ch, term)
        out.append((e, ch, name))
    return out


def minority(e):
    """Whether a report is a minority report."""
    return (e.get("side") or "").lower().startswith("min") or bool(
        re.match(r"\s*(?:MIN\b|MINORITY)", e.get("raw") or "", re.I))


def reporting_committees(events, term, official=None):
    """{"H": [committee, ...], "S": [...]}: the committees of each chamber
    that made a majority report on the bill, in the order they first did.
    `official(name, chamber, term)` puts a name in the site's spelling."""
    seen = {"H": [], "S": []}
    for e, ch, name in credited_reports(events, term, official):
        if minority(e) or ch not in ("H", "S") or not name:
            continue
        if name not in seen[ch]:
            seen[ch].append(name)
    return seen
