#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.1
"""
What a committee did to each bill at each of its meetings, read from the
bill's own docket, for the committee page's Meetings and Bills tabs.

    import committee_acts as CA
    acts = CA.acts(events)                 # every act a committee recorded on the bill
    own = CA.owners(acts, meetings, code_of)   # whose each act is
    CA.outcome(code, date, kinds, acts, own, mine, signins)   # what happened at one meeting
    CA.reported(code, acts, own, mine)     # the committee's acts, for its Bills tab

Data, not words: the page chooses how to say it (the component plan's C4,
approved 9 October 2026: "the deciding happens once, upstream, in Python").
build_committees.py puts it on each committee's record: `outcomes` on every
meeting, `reported` on every bill of its Bills tab.

WHY THE DOCKET'S VOTE DATE. The person's feedback of 9 October 2026, item
12: a committee's Meetings tab should make clear "what changed on each bill
at that meeting, if anything did". The House docket dates a committee's
report by the meeting the vote was taken at -- "Majority Committee Report:
Inexpedient to Legislate 03/03/2026 (Vote 9-8; RC)" -- in the report_date
narrative.py reads off the row, where the row's own date is the day it was
entered. Read by the entry date, the second-round prototype's first draft
said "no vote" on the day of a vote. Where a row prints no vote date (the
House's before 2015 or so, and HB 309 of 2025), the row's own day is all
the record gives, and it is used as it stands: a vote is placed at a
meeting only where the docket dates it that day, never at the nearest
executive session (the prototype's question 1, approved as drawn: it
"states only what the record says"). HB 1525 of 2026's report is dated
22 February 2026, a Sunday three days after the House killed the bill; its
executive session was 22 January, and nothing here moves the report there.

THE SENATE'S DATE IS ITS SITTING'S. A Senate committee's row reads
"Committee Report: Ought to Pass with Amendment # 2026-1709s, 05/07/2026;
Vote 4-1; CC", and 7 May 2026 is the sitting the Senate took the report up
at (HB 1681), not the day the committee voted. The Senate's meetings on
record are its hearings, so a Senate report is never placed at a meeting:
it is given with the docket's date, `dated` "sitting".

WHOSE ACT IT IS. A report names its committee; a retention ("Retained in
Committee") and an interim study report do not. A retention is the
committee that last met on the bill in that chamber on or before the row's
day (HB 572 of 2025: retained on 2 April, after Finance's executive session
of the 1st -- Finance's, not Housing's); an interim study report is the
committee whose report sent the bill to interim study. Only this
committee's acts are its own: after "Referred to Finance" the docket's
reports are Finance's (HB 572's ITL, 14-11, of 30 October 2025).

AN INTERIM STUDY REPORT NOT RECOMMENDING FUTURE LEGISLATION IS A KILLING
(the person, 9 October 2026, v8: "listed as killed, explaining what the
committee voted, rather than with the '~'"). `killed` is set on a study
report that recommends nothing for future legislation -- "Not Recommended"
or "Without Recommendation", the two the bill's own How it got here draws
alike (build_site_v2.study_ending: the "~" where the committee "did not, or
reported without a recommendation"). The record's own word stays beside it
in `said` ("rec", "not", "without", or "" where the row states none), so the
page can say which. The interim study rows are read in every wording the
docket has used, by the patterns the bill page reads them with
(build_site_v2.interim_report, which takes them from here); a minority's
study report ("MIN") is left to the majority's.

A STUDY REPORT DATED THE DAY BEFORE ITS MEETING. HB 65 of 2026's report,
"Not Recommended for Future Legislation 09/30/2026 (Vote 5-4)", is entered
for Housing's executive session of 1 October. A study report within a day
of an executive session the committee held on the bill is that meeting's,
its own date kept (the prototype's rule, drawn and approved). Only a study
report: a recommendation is placed by its date alone.

Standard library only; imports nothing of the project's, so that both
build_committees.py and build_site_v2.py can take its readings without
taking each other.
"""

import datetime
import re

# AN INTERIM STUDY REPORT, in every wording the docket has used: "Interim
# Study Report: Not Recommended for Future Legislation", 1989-2006's "INT
# STUDY REPT", "Interm Study Majority Report". Here since 9 October 2026,
# from build_site_v2.py, which imports them, so that the committee pages and
# the bill pages read one row one way.
INTERIM_REPORT_ROW = re.compile(r"\b(?:in?terim|int\.?)\s+study\s+(?:(?:maj|min)\w*\s+)?rep",
                                re.I)
INTERIM_REPORT_TALLY = re.compile(r"\(\s*v\w?te\s*:?\s*\(?\s*P?(\d+)\s*-\s*(\d+)", re.I)
INTERIM_REPORT_YEAR = re.compile(r"\b(?:IN|FOR)\s+((?:19|20)\d\d)\b", re.I)
INTERIM_REPORT_MINORITY = re.compile(r"\bMIN\b", re.I)


def study_said(raw):
    """What an interim study report recommends, from its row: "without" (no
    recommendation), "not" (not recommended for future legislation), "rec"
    (recommended), or "" where the row states none."""
    raw = raw or ""
    return ("without" if re.search(r"\b(?:without|no)\s+recom", raw, re.I) else
            "not" if re.search(r"\bnot\s+re+c|\bITL\b|inexpedient", raw, re.I) else
            "rec" if re.search(r"\brec|\bOTP\b|ought\s+to\s+pass", raw, re.I) else "")


# The committee's recommendation, as a code the page words. The docket's
# words vary over the decades -- "Ought to Pass W/Amendment", "Ought to Pass
# with AM", "Inexpedient to Legislate for Mar 7 CC", "Rereferred to
# Committee" -- and the code is what they mean; "" where none of these fits,
# with the words kept beside it either way.
REC_CODES = (
    ("OTPA", re.compile(r"ought\s+to\s+pass\s*(?:with|w/)\s*am|\bOTP\s*/\s*AM\b", re.I)),
    ("OTP", re.compile(r"ought\s+to\s+pass|\bOTP\b", re.I)),
    ("ITL", re.compile(r"inexpedient|\bITL\b", re.I)),
    ("IS", re.compile(r"interim\s+study|\bRFS\b", re.I)),
    ("RR", re.compile(r"re-?\s*refer", re.I)),
    ("WR", re.compile(r"without\s+recom", re.I)),
)
REC_WORDS = {"OTPA": "Ought to Pass with Amendment", "OTP": "Ought to Pass",
             "ITL": "Inexpedient to Legislate", "IS": "Interim Study",
             "RR": "Re-refer to Committee", "WR": "Without Recommendation"}
# " for Mar 7 CC", " for March 27", " for 1/6/2000": the calendar the report
# was printed for, which some dockets append to the recommendation.
FOR_DAY = re.compile(r"\s+for\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d)\S*.*$",
                     re.I)
MDY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _mdy(s):
    m = MDY.search(s or "")
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


def _int(v):
    s = str(v if v is not None else "").strip()
    return int(s) if s.isdigit() else None


def recommendation(words):
    """(code, words): the words in the site's form where the code is known,
    else the docket's own, less the calendar it was printed for."""
    w = FOR_DAY.sub("", (words or "").strip()).strip()
    code = next((c for c, pat in REC_CODES if pat.search(w)), "")
    return code, REC_WORDS.get(code) or w


def acts(events):
    """Every act a committee recorded on one bill, in the docket's order:

    {"act": "report", "body", "committee", "date", "entered", "dated",
     "recommendation", "code", "amendment", "yeas", "nays",
     "minority", "minority_code", "minority_amendment"}
    {"act": "study report", "body", "date", "entered", "said", "killed",
     "yeas", "nays"}
    {"act": "retained", "body", "date", "entered"}

    `date` is the day the docket dates the vote: the House's vote date where
    the row prints one (`dated` "vote"), else the row's own day ("row"); a
    Senate report's is its sitting's ("sitting"). `entered` is the row's own
    day. A minority's report goes on the majority's it answers: the next
    minority row of the same committee before that committee's next report."""
    out, last_main = [], {}
    for e in events or ():
        if e.get("cancelled"):
            continue
        typ, raw = e.get("type"), e.get("raw") or ""
        body = (e.get("body") or "").strip().upper()[:1]
        day = (e.get("date") or "")[:10]
        if INTERIM_REPORT_ROW.search(raw):
            if INTERIM_REPORT_MINORITY.search(raw):
                continue
            said = study_said(raw)
            t = INTERIM_REPORT_TALLY.search(raw)
            out.append({"act": "study report", "body": body, "date": day, "entered": day,
                        "said": said, "killed": said in ("not", "without"),
                        "yeas": int(t.group(1)) if t else None,
                        "nays": int(t.group(2)) if t else None})
        elif typ == "report":
            side = (e.get("side") or "").strip().lower()
            cmte = (e.get("committee") or "").strip()
            code, words = recommendation(e.get("recommendation") or "")
            amd = (e.get("amendment") or "").strip() or None
            if side == "minority":
                main = last_main.get((body, cmte.lower()))
                if main is not None and main["minority"] is None:
                    main["minority"], main["minority_code"] = words, code
                    main["minority_amendment"] = amd
                continue
            voted = _mdy(e.get("report_date") or "")
            a = {"act": "report", "body": body, "committee": cmte,
                 "date": voted or day, "entered": day,
                 "dated": "sitting" if body == "S" else ("vote" if voted else "row"),
                 "recommendation": words, "code": code, "amendment": amd,
                 "yeas": _int(e.get("yeas")), "nays": _int(e.get("nays")),
                 "minority": None, "minority_code": None, "minority_amendment": None}
            out.append(a)
            last_main[(body, cmte.lower())] = a
        elif typ == "retained":
            out.append({"act": "retained", "body": body, "date": day, "entered": day})
    return out


def owners(acts_, meetings, code_of):
    """[page code or None] for each act: whose it is. `meetings` is the
    bill's meetings [(date, code, kinds)] in date order, across committees;
    `code_of(name, body)` a report's committee as a page code."""
    out = []
    for a in acts_:
        if a["act"] == "report":
            out.append(code_of(a["committee"], a["body"]) if a["committee"] else None)
            continue
        if a["act"] == "study report":
            # The committee whose report sent the bill to interim study, the
            # latest before this one in its chamber.
            sent = [o for x, o in zip(acts_, out) if x["act"] == "report"
                    and x["body"] == a["body"] and x["code"] == "IS" and o
                    and x["entered"] <= a["date"]]
            if sent:
                out.append(sent[-1])
                continue
        # A retention, or a study report with no report to follow: the
        # committee that last met on the bill in its chamber, on or before.
        prior = [c for d, c, _k in meetings if d <= a["date"] and c[:1] == a["body"]]
        out.append(prior[-1] if prior else None)
    return out


def _days_apart(a, b):
    try:
        return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)
    except ValueError:
        return 99


def at_meeting(a, code, mine):
    """The day of committee `code`'s meeting on the bill that act `a` was
    voted at, or None. `mine` is {date: kinds} for the committee's meetings
    on the bill. A Senate report is never placed: its date is a sitting's."""
    if a.get("dated") == "sitting" or a["body"] != code[:1]:
        return None
    if a["date"] in mine:
        return a["date"]
    if a["act"] == "study report":
        near = sorted(d for d, kinds in mine.items()
                      if "executive session" in kinds and _days_apart(d, a["date"]) == 1)
        if near:
            return near[0]
    return None


def public(a, meeting=None):
    """An act as a committee's record carries it, less its reading aids."""
    keep = {k: v for k, v in a.items() if k not in ("body", "entered")
            and v is not None and v != ""}
    if a["act"] == "study report":
        keep["killed"] = bool(a.get("killed"))
    if meeting:
        keep["meeting"] = meeting
    return keep


HEARD = ("public hearing", "hearing")


def outcome(code, date, kinds, acts_, owners_, mine, signins=None, ahead=False):
    """What happened to one bill at one meeting of committee `code`:

    {"kinds": [...], "outcome": one of
       "voted"      the committee voted on it here, and `votes` says what
       "heard"      a hearing, and nothing voted here
       "no vote"    an executive session with nothing the docket dates here
       "worked"     a work session or any other sitting, nothing voted
       "scheduled"  a meeting still to come,
     "votes": [act, ...]   where voted, each as public() gives it,
     "voted": {"act", "date", "meeting"?}  where nothing was voted here: the
              committee's next dated act on the bill after this meeting, or,
              for an executive session with none after it, the last before
              it (SB 170 of 2025: its House report dated 6 April, before its
              hearings; its executive session was 6 May); `meeting` where
              the docket dates that act to a meeting of this committee,
     "signins": {"for", "against", "neutral", "total"}  at a hearing, where
              the sign-in record has this hearing's date (the bill page's
              station for it)}"""
    out = {"kinds": list(kinds)}
    if signins and any(k in HEARD for k in kinds):
        out["signins"] = {"for": signins.get("support") or 0,
                          "against": signins.get("oppose") or 0,
                          "neutral": signins.get("neutral") or 0,
                          "total": signins.get("total") or 0}
    if ahead:
        out["outcome"] = "scheduled"
        return out
    mine_acts = [a for a, o in zip(acts_, owners_) if o == code]
    here = [public(a, date) for a in mine_acts if at_meeting(a, code, mine) == date]
    if here:
        out["outcome"], out["votes"] = "voted", here
        return out
    out["outcome"] = ("heard" if any(k in HEARD for k in kinds) else
                      "no vote" if "executive session" in kinds else "worked")
    own = sorted(mine_acts, key=lambda a: a["date"])
    after = [a for a in own if a["date"] > date]
    before = [a for a in own if a["date"] < date]
    nxt = after[0] if after else (before[-1] if before and "executive session" in kinds
                                  else None)
    if nxt is not None:
        v = {"act": nxt["act"], "date": nxt["date"]}
        at = at_meeting(nxt, code, mine)
        if at:
            v["meeting"] = at
        out["voted"] = v
    return out


def reported(code, acts_, owners_, mine):
    """The committee's acts on the bill, for its Bills tab: each as public()
    gives it, with `meeting` where the docket dates it to one of this
    committee's meetings on the bill."""
    return [public(a, at_meeting(a, code, mine)) for a, o in zip(acts_, owners_) if o == code]
