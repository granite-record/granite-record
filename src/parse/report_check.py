#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-26.6
"""
A House committee report printed under another bill, caught against the
report the committee filed.

    python3 src/parse/report_check.py            # what it finds; writes nothing
    python3 src/parse/report_check.py --apply    # writes report_corrections.json

No network. It reads committee_reports.json -- the House Calendar printings
fetch_committee_reports.py reads -- data/bills.json for each bill's billText
id, and the reports as the committees filed them with the Clerk:
db/past/PastCommitteeReports.jsonl for 2016-2024 (fetch_past_db.py) and
db/CandH_Reports.psv for the current term (fetch_archive_db.py).
build_site_v2 applies what it writes.

WHAT WAS WRONG

2021 HB 365's majority report read "HB197 AN ACT relative to the justified
use of deadly force upon another person. This bill was an extension of the
stand your ground law..." -- HB 197's minority report, word for word. Nothing
here put it there: House Calendar 12 of 2021, page 25, prints it under HB 365's
heading and over Rep. Testerman's name. The parser read what was printed.

The calendar is the only place the House's reasoning was ever read from, so a
misprint in it became the site's record with nothing to catch it. The
committee's own copy was on disk all along. PastCommitteeReports holds HB
365's majority report as Rep. Testerman filed it on 23 February 2021: "HB365
seeks to authorize federal agents to enforce New Hampshire laws..."

HOW IT DECIDES

A calendar report is another bill's when

  - its words are another bill's filed report of the same term and the same
    side -- eight words running, at least ten times and over half the report
    -- and not its own bill's, which has filed reports on that side and shares
    under a fifth of them; or
  - it opens by naming another bill in the form a filing names its own:
    "HB197 AN ACT ...". This one needs no filed copy, so it covers every term;
    or
  - its words are another bill's report in the calendars of the same term:
    over half its eight-word runs are printed under exactly one other bill's
    heading, it does not name its own bill, no filed copy of its own on the
    same side carries them, and either its heading already has a report of
    its own on that side, or it speaks in the other bill's title's words and
    in none of its own title's. This is the only test there is before the
    filed copies begin in 2016, and it withholds; it never drops a record,
    because the heading and the recommendation above the text are this
    bill's. The vote printed with the text goes with it only where it is the
    vote the other bill's own printing carries.

Same term only: a member who files the same reasoning on a bill two sessions
later (2021 HB 85 and 2019 HB 567, the Atlantic time zone) is not a misprint.
Nor is a text a committee wrote once for several bills heard together -- the
seven turnpike toll bills of 2007 -- which is why the calendar test wants
exactly one other bill, and why two bills whose titles share their subject
are left alone: 2011 SB 172 was amended to carry HB 164's common core
language, and its report says so in HB 164's words.

WHAT IT DOES ABOUT ONE

  filed     the bill has a filed report from the same side, signed by the same
            member (the whole name, not the surname): its text replaces the
            misprint, and the page says so.
  withheld  it has none: the text comes off, and the page says why, rather
            than printing another bill's reasoning or claiming there was none.
  dropped   every report in the calendar's record is another bill's by the
            filed copies or its opening words, and none has a filed copy: the
            record is not this bill's at all.

Measured on everything on disk (27 September 2026), with the calendars re-read
by this commit's fetch_committee_reports: 2021 HB 365's majority, filed; and,
withheld by the calendar test, 2006 HB 1141 (House Calendar 18 printed HB
1195's report as a second one under it), 2010 HB 271 (Calendar 2 printed HB
133's minority as HB 271's), 2010 HB 1221 (Calendar 14 printed HB 1239's
heading "B 1239"), 2012 HB 1470 (Calendar 14, HB 1191's words over Rep.
Dowling's name), 2013 HB 529 (Calendar 69, HB 456's over Rep. Williams's),
2014 HB 1247 (Calendar 13, HB 1392's minority as a second one) and 2016 HB
1497 (Calendar 14, HB 1652's over Rep. Cordelli's). Each was read in the
calendar. The file as it stood before that re-read also has 2024 HB 463's
phantom, which this drops. And dropped by its heading: the record of 1999's
SJR 1, on sulfur in gasoline, which the re-read put on 2000's SJR 1, another
resolution of the same number (another_measure() says why only resolutions).

WHAT IT WRITES

report_corrections.json, {term: {bill: [correction]}}, each correction naming
the calendar record by its source and the report by its side, its signer and
its opening words. Every run rewrites it whole from what is on disk -- it is
derived, and a run over part of the record would silently forget the rest.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import html as _html
import json
import re
from collections import Counter, defaultdict
from urllib.parse import parse_qs, urlparse

import proceedings as P

REPORTS = Path("committee_reports.json")
BILLS = Path("data/bills.json")
PAST = Path("db/past/PastCommitteeReports.jsonl")
CURRENT = Path("db/CandH_Reports.psv")
CANDH_COLUMNS = ["LegislationID", "DateTimeStamp", "CommitteeType",
                 "PDFImage_bytes", "ChamberCode", "HTMLText", "BillNbr",
                 "ReleaseDate"]
OUT = Path("report_corrections.json")

PAST_SIDES = {"Hse MAJ Committee Rpt": "Majority",
              "Hse MIN Committee Rpt": "Minority",
              "Hse Comm Rpt": "Committee"}
KINDS = r"(HB|SB|CACR|HCR|SCR|HJR|SJR|HR|SR)"
BILL_NUMBER = re.compile(rf"Bill Number:\s*{KINDS}\s*0*(\d+)", re.I)
FILED_SIDE = re.compile(r"REPORT OF COMMITTEE\s+The\s+(Majority|Minority)\s+of\s+the\s+Committee",
                        re.I)
SIGNED = re.compile(r"\bRep\.\s+(?P<who>[^.]{2,60}?)\s+FOR THE\s+(?:MAJORITY|MINORITY|COMMITTEE)\b")
INTENT = re.compile(r"STATEMENT OF INTENT\s*")
VOTE_END = re.compile(r"\s*Vote[:\s]\s*\d{1,3}\s*[-–]\s*\d{1,3}\s*\.?\s*$", re.I)
# The calendar entry at the end of a filed report: "Rep. Ray Newman for the
# Majority of Criminal Justice and Public Safety. <reasoning> Vote 11-9."
ENTRY = re.compile(r"\bRep\.\s+[^.]{2,60}?\s+for\s+(?:the\s+(?:Majority|Minority)\s+of\s+)?"
                   r"[A-Z][A-Za-z,&\-\s]{2,80}?[.:]\s+(?P<text>.+?)"
                   r"(?=\s*Vote[:\s]\s*\d{1,3}\s*[-–]\s*\d{1,3}|$)")
# "HB197 AN ACT relative to ...": how a filed report names the bill it is on.
OPENS_WITH_BILL = re.compile(rf"^\s*{KINDS}\s*0*(\d+)(?:-[A-Z]+)*\s*,?\s+AN\s+ACT\b")

# The form's own date: "Date: February 8, 2021". The dump's release date is
# not it -- 2021 HB 365's form is dated 8 February and was released on the
# 23rd, after House Calendar 12 had printed the committee's report.
FILED_DATE = re.compile(r"\bDate:\s*([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})")
# Another bill named in a report's own words, as a calendar prints numbers.
NAMES = re.compile(rf"\b{KINDS}\s?-?\s?0*(\d{{1,4}})\b")

SHINGLE = 8          # words in a run
LEAST = 10           # runs a report must share with another bill's filed copy
MOST_OWN = 0.2       # share of its runs a misprint may have with its own bill's
CAL_LEAST = 25       # runs a report needs before the calendars can say whose it is
CAL_WHY = "another bill's report in the calendars"
# Resolutions are numbered again in a term's second year; bills are not.
RESOLUTION = re.compile(r"^(?:CACR|HCR|SCR|HJR|SJR|HR|SR)\d")
WORD = re.compile(r"[a-z0-9]+")
# Words every title and report uses, which say nothing about whose report it is.
GENERIC = frozenset("""
relative with that this from which have been their other certain establishing
establish requiring making relating providing state states hampshire concerning
regarding shall under into amendment amendments title titles bill bills house
senate committee committees study studies commission general court legislature
legislative legislation laws also would such about more than these those there
where when were will provide provides department
""".split())


def text_of(markup):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup or "")
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def shingles(text):
    w = WORD.findall((text or "").lower())
    return {" ".join(w[i:i + SHINGLE]) for i in range(len(w) - SHINGLE + 1)}


def signer(author):
    """'Rep. Carol M. McGuire' -> 'carol m mcguire': the whole name, so that a
    filed copy signed by another member of the same surname is not taken for
    the report the calendar printed."""
    name = re.sub(r"^\s*(?:Rep|Sen)s?\.\s*", "", author or "", flags=re.I)
    return " ".join(re.findall(r"[a-z0-9'-]+", name.lower().replace("’", "'")))


def title_words(text):
    """The words that say what a title or a report is about, cut to their
    first six letters so that 'parents' and 'parental' are one word."""
    return {w[:6] for w in re.findall(r"[a-z]+", (text or "").lower())
            if len(w) >= 4 and w not in GENERIC}


def bill_title(bills, term, bid):
    t = ((bills or {}).get(term, {}).get(bid) or {}).get("title") or ""
    return re.sub(r"^\s*\((?:\w+\s+)?new title\)\s*", "", t, flags=re.I)


def named(text):
    return {f"{k.upper()}{int(n)}" for k, n in NAMES.findall(text or "")}


def another_measure(bills, term, bid, rec):
    """The year of the other resolution a calendar record is for, or "".

    ANOTHER MEASURE OF THE SAME NUMBER (27 September 2026). Resolutions are
    numbered again in the second year of a term, and the record keeps one of
    each number a term: 1999-2000's SJR 1 is 2000's, on the White Mountain
    National Forest, and House Calendar 59 of 1999 reports 1999's SJR 1,
    "supporting the reduction of the sulfur content of gasoline". Once the
    calendars were re-read with their SJR headings, that report sat on the
    forest resolution's page. So a resolution's record printed in the other
    year of its term, under a heading that shares no word with its title, is
    the other measure's. A title an amendment replaced is left alone: it can
    share no word with the heading it was reported under.

    Bills are not tested. Their numbers are not used twice in a term, and the
    same test would take 2019-2020 HB 496's own 2019 report, printed under the
    title the Senate later replaced without marking it a new title."""
    if not RESOLUTION.match(bid or ""):
        return ""
    b = (bills or {}).get(term, {}).get(bid) or {}
    own = str(b.get("lsr_year") or "")
    m = re.search(r",\s*((?:19|20)\d\d)\s*$", rec.get("source") or "")
    if not own or not m or m.group(1) == own:
        return ""
    if re.match(r"^\s*\((?:\w+\s+)?new title\)", b.get("title") or "", re.I):
        return ""
    heading = title_words(rec.get("title"))
    title = title_words(bill_title(bills, term, bid))
    return m.group(1) if len(heading) >= 2 and title and not (heading & title) else ""


def parse_filed(text, side=None):
    """One filed House committee report as {bill, side, author, text, all,
    dated}, or None.

    The document is the Clerk's form: REPORT OF COMMITTEE, the bill number,
    the recommendation, STATEMENT OF INTENT and the reasoning, the member who
    signs FOR THE MAJORITY, MINORITY or COMMITTEE -- and then the calendar entry
    the committee sent for printing, which repeats the reasoning after "Rep. X
    for the Majority of <committee>.". Some forms leave the statement empty and
    carry the reasoning only there -- 2020 HB 1101's majority report does -- so
    that entry is the text where the statement is empty, and "all" is the whole
    document, which is what a calendar printing is compared with. "dated" is
    the form's own Date: line, or empty.
    """
    m = BILL_NUMBER.search(text)
    if not m:
        return None
    if side is None:
        s = FILED_SIDE.search(text)
        side = s.group(1).title() if s else "Committee"
    signed = SIGNED.search(text)
    statement = ""
    i = INTENT.search(text)
    if i:
        end = SIGNED.search(text, i.end())
        statement = text[i.end(): end.start() if end else len(text)]
        statement = VOTE_END.sub("", statement).strip()
    if not statement:
        entry = list(ENTRY.finditer(text))
        if entry:
            statement = VOTE_END.sub("", entry[-1].group("text")).strip()
    dated = ""
    d = FILED_DATE.search(text)
    if d and d.group(1) in MONTHS:
        dated = f"{d.group(3)}-{MONTHS.index(d.group(1)) + 1:02d}-{int(d.group(2)):02d}"
    return {"bill": f"{m.group(1).upper()}{int(m.group(2))}", "side": side,
            "author": f"Rep. {signed.group('who').strip()}" if signed else "",
            "text": statement, "all": text, "dated": dated}


def billtext_id(rec):
    """The billText id data/bills.json holds for a bill, or None.

    2016's text_pdf carries the LSR-and-year form (5352016) instead, which no
    filed report is keyed on, so it gives none.
    """
    q = parse_qs(urlparse((rec or {}).get("text_pdf") or "").query)
    if "id" not in q:
        return None
    ident, year = q["id"][0], (q.get("sy") or [""])[0]
    if year and ident.endswith(year) and len(ident) > len(year):
        return None
    return ident


# A FINISHED TERM'S FILED REPORTS OUTLIVE THE CURRENT VIEW (5 October 2026).
# CandH_Reports is the database's current term, and the first dump after the
# General Court turns it over to 2027-2028 holds no 2025-2026 report. The view
# is frozen before it turns (freeze_term.py --views), and senate_hearing_reports
# and build_bill_versions already read the freeze; this read only the current
# view, so every 2025-2026 House report would have lost its filed copy. A
# frozen term that is no longer the session's is read from its freeze alone,
# and a row of it the current view still holds is counted and left out: the
# one rule for a finished term's rows in new files, never merged. While the
# term is still the session's, its freeze waits and the current view is read.
FROZEN = Path("db") / "term"


def frozen_candh(session=None):
    """{term: its frozen CandH_Reports.psv} for each frozen term older than the
    term the session's files describe."""
    session = P.session_term() if session is None else session
    if not FROZEN.is_dir() or not session:
        return {}
    return {d.name: d / "CandH_Reports.psv" for d in sorted(FROZEN.iterdir())
            if d.is_dir() and P.TERM_RE.match(d.name) and d.name < session
            and (d / "CandH_Reports.psv").exists()}


def filed_reports(bills, past=PAST, current=CURRENT, frozen=None):
    """{(term, bill): [filed report]} from both dumps, joined by billText id.

    Each filed report names its own bill, and a year comes with it; where the
    bill's record holds a billText id, that id must be the report's too, or the
    report is not used. A report whose bill number and billText id disagree is
    one this cannot place, and placing it wrongly is the fault being fixed.

    `frozen` is {term: CandH_Reports.psv} of the finished terms (frozen_candh,
    by default): each is read for its own term only, and the current view's
    rows of it are counted and left out.
    """
    out, census = defaultdict(list), Counter()
    frozen = frozen_candh() if frozen is None else frozen

    def add(year, ident, parsed, released, source):
        if not parsed:
            census["no bill number"] += 1
            return
        term = P.term_of(str(year))
        rec = (bills.get(term) or {}).get(parsed["bill"])
        if rec is None:
            census["no such bill on the site"] += 1
            return
        mine = billtext_id(rec)
        if mine is not None and str(ident) != mine:
            census["billText id disagrees with the bill number"] += 1
            return
        parsed.update({"released": released, "source": source})
        out[(term, parsed["bill"])].append(parsed)
        census["filed reports placed"] += 1

    if Path(past).exists():
        with open(past, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("chamberCode") != "H" or r.get("committeeType") not in PAST_SIDES:
                    continue
                lid = str(r.get("legislationid") or "")
                if len(lid) < 5:
                    continue
                add(lid[-4:], lid[:-4],
                    parse_filed(text_of(r.get("htmlText")), PAST_SIDES[r["committeeType"]]),
                    r.get("releaseDAte") or "", f"PastCommitteeReports {r.get('id')}")
    def candh(path, only=None, skip=()):
        csv.field_size_limit(1 << 30)
        with open(path, encoding="utf-8", newline="") as fh:
            for row in csv.reader(fh, delimiter="|", quoting=csv.QUOTE_NONE):
                if len(row) != len(CANDH_COLUMNS):
                    continue
                r = dict(zip(CANDH_COLUMNS, row))
                if (r["ChamberCode"].strip() != "H"
                        or r["CommitteeType"].strip() != "Committee Report"):
                    continue
                d = re.match(r"(\d{2})/(\d{2})/(\d{4})", r["ReleaseDate"])
                if not d:
                    continue
                term = P.term_of(d.group(3))
                if (only and term != only) or term in skip:
                    if term in skip:
                        census[f"reports of {term} in the current view, left out: the "
                               "term is read from its freeze"] += 1
                    continue
                add(d.group(3), r["LegislationID"].strip(),
                    parse_filed(text_of(r["HTMLText"])),
                    f"{d.group(3)}-{d.group(1)}-{d.group(2)}",
                    f"CandH_Reports {r['LegislationID'].strip()}")

    if Path(current).exists():
        candh(current, skip=set(frozen))
    for term, path in sorted(frozen.items()):
        candh(path, only=term)
    return out, census


def calendar_claim(bid, rec, e, byb, index, own_filed, bills=None, term=""):
    """(the other bill, the calendar that prints it under that bill's heading,
    the vote printed with it there) where one other bill's calendar reports
    of the same term claim this report's words, else None. `index` is this
    term's {run: {bill}}.

    Over half the report's runs must be printed under exactly one other bill
    -- a text a committee wrote once for a group of bills is shared with
    several and is nobody's misprint -- and printed there as that bill's own
    report, the only one on its side under that heading. A text two bills
    both carry as a second report is a third heading's that nothing read, and
    this cannot say whose. The report must not name its own bill, nor match a
    filed copy of its own on the same side. Then either its heading already
    carries a report of its own on this side, so this one is a second, or it
    speaks in the other bill's title's words (two at least) and in none of
    its own title's, where the two titles do not share their subject."""
    s = shingles(e.get("text"))
    if len(s) < CAL_LEAST:
        return None
    per = Counter(b for x in s for b in index.get(x, ()) if b != bid)
    claims = [b for b, n in per.items() if n >= len(s) / 2]
    if len(claims) != 1:
        return None
    b2 = claims[0]
    if bid in named(e.get("text")):
        return None
    if own_filed:
        mine = set()
        for d in own_filed:
            mine |= shingles(d.get("all") or d["text"])
        if len(s & mine) >= len(s) / 2:
            return None
    # Where the other bill prints these words as its own report: the calendar
    # that does, and every run the other bill's reports carry.
    where, vote, theirs = "", None, set()
    for r2 in byb.get(b2) or []:
        sides = Counter(e2.get("side") for e2 in r2.get("reports") or [])
        for e2 in r2.get("reports") or []:
            sh = shingles(e2.get("text"))
            theirs |= sh
            if not where and sides[e2.get("side")] == 1 and len(s & sh) >= len(s) / 2:
                where = r2.get("source") or ""
                if e2.get("vote_yeas") is not None:
                    vote = [e2.get("vote_yeas"), e2.get("vote_nays")]
    if not where:
        return None
    for e2 in rec.get("reports") or []:
        if e2 is e or e2.get("side") != e.get("side"):
            continue
        s2 = shingles(e2.get("text"))
        if s2 and len(s2 & theirs) < len(s2) / 2:
            return b2, where, vote
    if bills:
        mine_t = title_words(bill_title(bills, term, bid))
        theirs_t = title_words(bill_title(bills, term, b2))
        if len(mine_t & theirs_t) < 2:
            said = title_words(e.get("text"))
            if len(said & (theirs_t - mine_t)) >= 2 and not said & (mine_t - theirs_t):
                return b2, where, vote
    return None


def check(reports, filed, bills=None):
    """{term: {bill: [correction]}} for every House calendar report that is
    another bill's, and a census of what was compared. `bills`
    (data/bills.json) gives the titles the calendar test reads; without it
    that test only finds a second report on one side."""
    index = defaultdict(set)            # (side, shingle) -> {(term, bill)}
    for key, docs in filed.items():
        for d in docs:
            for x in shingles(d.get("all") or d["text"]):
                index[(d["side"], x)].add(key)
    terms_filed = {t for t, _ in filed}

    census, out = Counter(), defaultdict(lambda: defaultdict(list))
    for term, byb in reports.items():
        # This term's calendar reports, run by run, for the calendar test.
        cal = defaultdict(set)
        for b, recs in byb.items():
            for r in recs:
                for e in r.get("reports") or []:
                    for x in shingles(e.get("text")):
                        cal[x].add(b)
        for bid, recs in byb.items():
            for rec in recs:
                year = another_measure(bills, term, bid, rec)
                if year:
                    # The whole record is the other measure's: its heading and
                    # its recommendation as well as its reasoning.
                    for e in rec.get("reports") or []:
                        census["reports read"] += 1
                        census["another measure of the same number"] += 1
                        census["dropped"] += 1
                        out[term][bid].append({
                            "source": rec.get("source") or "", "side": e.get("side") or "",
                            "author": e.get("author") or "",
                            "opens": (e.get("text") or "")[:60], "belongs_to": bid,
                            "found_by": f"{year}'s {kind_name(bid)}, by its heading",
                            "action": "dropped"})
                    continue
                verdicts = []
                for e in rec.get("reports") or []:
                    census["reports read"] += 1
                    t = e.get("text") or ""
                    side = e.get("side")
                    other, why, where, vote = None, "", "", None
                    m = OPENS_WITH_BILL.match(t)
                    if m and f"{m.group(1).upper()}{int(m.group(2))}" != bid:
                        other, why = f"{m.group(1).upper()}{int(m.group(2))}", "its own opening words"
                    elif term in terms_filed and (term, bid) in filed:
                        s = shingles(t)
                        if len(s) >= LEAST:
                            census["compared with filed copies"] += 1
                            # The same side only: a majority report is
                            # compared with filed majority reports.
                            hits = Counter(k for x in s for k in index.get((side, x), ())
                                           if k[0] == term)
                            mine = hits.pop((term, bid), 0)
                            if hits:
                                (_, b2), n = hits.most_common(1)[0]
                                if n >= max(LEAST, len(s) / 2) and mine < MOST_OWN * len(s):
                                    other, why = b2, "another bill's filed report"
                    if not other:
                        census["compared with the term's calendars"] += 1
                        got = calendar_claim(
                            bid, rec, e, byb, cal,
                            [d for d in filed.get((term, bid), []) if d["side"] == side],
                            bills, term)
                        if got:
                            (other, where, vote), why = got, CAL_WHY
                    if not other:
                        verdicts.append(None)
                        continue
                    census["another bill's report"] += 1
                    same = [d for d in filed.get((term, bid), [])
                            if d["side"] == side and d["text"]
                            and signer(d["author"]) == signer(e.get("author"))]
                    verdicts.append((e, other, why, same[0] if same else None, where, vote))
                bad = [v for v in verdicts if v]
                if not bad:
                    continue
                # A record goes only where the filed copies or the opening
                # words say every report in it is another bill's. The
                # calendar test withholds: the heading and the recommendation
                # it found the text under are this bill's.
                whole = (len(bad) == len(verdicts) and not any(v[3] for v in bad)
                         and all(v[2] != CAL_WHY for v in bad))
                for e, other, why, fix, where, vote in bad:
                    c = {"source": rec.get("source") or "", "side": e.get("side") or "",
                         "author": e.get("author") or "",
                         "opens": (e.get("text") or "")[:60], "belongs_to": other,
                         "found_by": why}
                    if where:
                        c["printed_under"] = where
                    if vote:
                        c["their_vote"] = vote
                    if fix:
                        c.update(action="filed", text=fix["text"], filed=fix["source"],
                                 released=fix["released"], dated=fix.get("dated") or "")
                    else:
                        c["action"] = "dropped" if whole else "withheld"
                    census[c["action"]] += 1
                    out[term][bid].append(c)
    return {t: dict(v) for t, v in out.items()}, census


def kind_name(bid):
    m = re.match(r"([A-Z]+)(\d+)", bid or "")
    return f"{m.group(1)} {m.group(2)}" if m else bid


MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def said_day(iso):
    """'2021-02-23' -> 'February 23, 2021', as the page writes a date in prose."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    return f"{MONTHS[int(m.group(2)) - 1]} {int(m.group(3))}, {m.group(1)}" if m else ""


def apply(reports, corrections):
    """Put report_corrections.json into committee_reports.json's records, in
    place. Returns how many reports it changed. A correction naming a record
    or a report no longer there changes nothing: the calendar was re-read and
    the misprint went with it, or it did not, and report_check says so next
    run."""
    n = 0
    for term, byb in (corrections or {}).items():
        for bid, fixes in byb.items():
            recs = (reports.get(term) or {}).get(bid)
            if not recs:
                continue
            for c in fixes:
                for rec in list(recs):
                    if (rec.get("source") or "") != c.get("source"):
                        continue
                    if c.get("action") == "dropped":
                        recs.remove(rec)
                        n += 1
                        break
                    for e in rec.get("reports") or []:
                        if (e.get("side"), e.get("author")) != (c.get("side"), c.get("author")):
                            continue
                        # And the words it was found in, where the correction
                        # records them: a record can carry two reports on one
                        # side over one name, and only one is another bill's.
                        if c.get("opens") and not (e.get("text") or "").startswith(c["opens"]):
                            continue
                        other = kind_name(c.get("belongs_to"))
                        printed = (f"{rec.get('source') or 'The House Calendar'} printed "
                                   f"{other}'s report here.")
                        if c.get("action") == "filed":
                            e["text"] = c.get("text") or ""
                            # The form's own date, never the dump's release
                            # date, which can fall after the calendar that
                            # printed the report.
                            day = said_day(c.get("dated"))
                            e["note"] = (f"{printed} This is the report as the committee "
                                         f"filed it with the Clerk"
                                         + (f", dated {day}" if day else "") + ".")
                        elif c.get("printed_under"):
                            # The vote printed at the end of those words goes
                            # with them where it is the vote the other bill's
                            # own printing carries: 2006 HB 1141's second
                            # report is HB 1195's, signed and voted 11-1. Where
                            # it differs it is this bill's -- 2016 HB 1497's
                            # 19-0 beside HB 1652's 20-0 -- and it stays.
                            e["text"] = ""
                            if c.get("their_vote") and c["their_vote"] == [
                                    e.get("vote_yeas"), e.get("vote_nays")]:
                                for k in ("vote_yeas", "vote_nays", "calendar"):
                                    e.pop(k, None)
                            e["note"] = (f"{printed} {c['printed_under']} prints the same "
                                         f"words under {other}'s own heading, so no "
                                         "reasoning is shown for it here.")
                        else:
                            e["text"] = ""
                            e["note"] = (f"{printed} The committee's own copy of this "
                                         "report is not in the record here, so no reasoning "
                                         "is shown for it.")
                        n += 1
            if not recs:
                del reports[term][bid]
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write report_corrections.json")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not REPORTS.exists():
        sys.exit(f"{REPORTS} is not here; fetch_committee_reports.py writes it.")
    reports = json.loads(REPORTS.read_text(encoding="utf-8"))
    bills = json.loads(BILLS.read_text(encoding="utf-8")) if BILLS.exists() else {}
    filed, fc = filed_reports(bills)
    for k, v in sorted(fc.items()):
        print(f"  {v:>7,}  {k}")
    # Silence is not success. With neither dump on disk this compares no filed
    # copy, and says so rather than reporting a clean record.
    if not filed:
        print(f"\nNO FILED REPORTS: neither {PAST} nor {CURRENT} gave one, so each "
              "report is checked against its own opening words and the term's "
              "calendars only.")
    if not bills:
        print(f"\nNO TITLES: {BILLS} is not here, so the calendar test finds only a "
              "second report on one side.")
    got, census = check(reports, filed, bills)
    for k, v in sorted(census.items()):
        print(f"  {v:>7,}  {k}")
    for term in sorted(got):
        for bid, cs in sorted(got[term].items()):
            for c in cs:
                print(f"  {term} {bid:7} {c['action']:8} {c['side']:9} {c['author']}: "
                      f"{kind_name(c['belongs_to'])}'s report ({c['found_by']}), "
                      f"{c['source']}")
    if a.apply:
        OUT.write_text(json.dumps(got, indent=1), encoding="utf-8")
        print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
