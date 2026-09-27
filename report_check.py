#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-26.1
"""
A House committee report printed under another bill, caught against the
report the committee filed.

    python3 report_check.py            # what it finds; writes nothing
    python3 report_check.py --apply    # writes report_corrections.json

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

A calendar report is another bill's when either

  - its words are another bill's filed report of the same term -- eight words
    running, at least ten times and over half the report -- and not its own
    bill's, which has filed reports and shares under a fifth of them; or
  - it opens by naming another bill in the form a filing names its own:
    "HB197 AN ACT ...". This one needs no filed copy, so it covers every term.

Same term only: a member who files the same reasoning on a bill two sessions
later (2021 HB 85 and 2019 HB 567, the Atlantic time zone) is not a misprint.

WHAT IT DOES ABOUT ONE

  filed     the bill has a filed report from the same side, signed by the same
            member: its text replaces the misprint, and the page says so.
  withheld  it has none: the text comes off, and the page says why, rather
            than printing another bill's reasoning or claiming there was none.
  dropped   every report in the calendar's record is another bill's and none
            has a filed copy: the record is not this bill's at all.

Measured on everything on disk (26 September 2026): 2021 HB 365's majority,
filed; 2024 HB 463's "minority report" from House Calendar 20, which is SB
453's and was never HB 463's -- fetch_committee_reports now reads it where it
belongs, and until that is re-run this drops it. Nothing else: 30,441 reports
of every term read for their opening words, 9,744 of them (2016-2026) compared
with the filed copies, which each find HB 365's on their own.

WHAT IT WRITES

report_corrections.json, {term: {bill: [correction]}}, each correction naming
the calendar record by its source and the report by its side and signer. Every
run rewrites it whole from what is on disk -- it is derived, and a run over part
of the record would silently forget the rest.
"""

import argparse
import csv
import html as _html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
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

SHINGLE = 8          # words in a run
LEAST = 10           # runs a report must share with another bill's filed copy
MOST_OWN = 0.2       # share of its runs a misprint may have with its own bill's
WORD = re.compile(r"[a-z0-9]+")


def text_of(markup):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup or "")
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def shingles(text):
    w = WORD.findall((text or "").lower())
    return {" ".join(w[i:i + SHINGLE]) for i in range(len(w) - SHINGLE + 1)}


def surname(author):
    words = re.findall(r"[A-Za-z'’-]+", author or "")
    return words[-1].lower() if words else ""


def parse_filed(text, side=None):
    """One filed House committee report as {bill, side, author, text, all}, or
    None.

    The document is the Clerk's form: REPORT OF COMMITTEE, the bill number,
    the recommendation, STATEMENT OF INTENT and the reasoning, the member who
    signs FOR THE MAJORITY, MINORITY or COMMITTEE -- and then the calendar entry
    the committee sent for printing, which repeats the reasoning after "Rep. X
    for the Majority of <committee>.". Some forms leave the statement empty and
    carry the reasoning only there -- 2020 HB 1101's majority report does -- so
    that entry is the text where the statement is empty, and "all" is the whole
    document, which is what a calendar printing is compared with.
    """
    m = BILL_NUMBER.search(text)
    if not m:
        return None
    if side is None:
        s = FILED_SIDE.search(text)
        side = s.group(1).title() if s else "Committee"
    signer = SIGNED.search(text)
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
    return {"bill": f"{m.group(1).upper()}{int(m.group(2))}", "side": side,
            "author": f"Rep. {signer.group('who').strip()}" if signer else "",
            "text": statement, "all": text}


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


def filed_reports(bills, past=PAST, current=CURRENT):
    """{(term, bill): [filed report]} from both dumps, joined by billText id.

    Each filed report names its own bill, and a year comes with it; where the
    bill's record holds a billText id, that id must be the report's too, or the
    report is not used. A report whose bill number and billText id disagree is
    one this cannot place, and placing it wrongly is the fault being fixed.
    """
    out, census = defaultdict(list), Counter()

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
    if Path(current).exists():
        csv.field_size_limit(1 << 30)
        with open(current, encoding="utf-8", newline="") as fh:
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
                add(d.group(3), r["LegislationID"].strip(),
                    parse_filed(text_of(r["HTMLText"])),
                    f"{d.group(3)}-{d.group(1)}-{d.group(2)}",
                    f"CandH_Reports {r['LegislationID'].strip()}")
    return out, census


def check(reports, filed):
    """{term: {bill: [correction]}} for every House calendar report that is
    another bill's, and a census of what was compared."""
    index = defaultdict(set)            # shingle -> {(term, bill)}
    own_sh = {}
    for key, docs in filed.items():
        s = set()
        for d in docs:
            s |= shingles(d.get("all") or d["text"])
        own_sh[key] = s
        for x in s:
            index[x].add(key)
    terms_filed = {t for t, _ in filed}

    census, out = Counter(), defaultdict(lambda: defaultdict(list))
    for term, byb in reports.items():
        for bid, recs in byb.items():
            for rec in recs:
                verdicts = []
                for e in rec.get("reports") or []:
                    census["reports read"] += 1
                    t = e.get("text") or ""
                    other, why = None, ""
                    m = OPENS_WITH_BILL.match(t)
                    if m and f"{m.group(1).upper()}{int(m.group(2))}" != bid:
                        other, why = f"{m.group(1).upper()}{int(m.group(2))}", "its own opening words"
                    elif term in terms_filed and (term, bid) in filed:
                        s = shingles(t)
                        if len(s) >= LEAST:
                            census["compared with filed copies"] += 1
                            hits = Counter(k for x in s for k in index.get(x, ())
                                           if k[0] == term)
                            mine = hits.pop((term, bid), 0)
                            if hits:
                                (_, b2), n = hits.most_common(1)[0]
                                if n >= max(LEAST, len(s) / 2) and mine < MOST_OWN * len(s):
                                    other, why = b2, "another bill's filed report"
                    if not other:
                        verdicts.append(None)
                        continue
                    census["another bill's report"] += 1
                    same = [d for d in filed.get((term, bid), [])
                            if d["side"] == e.get("side") and d["text"]
                            and surname(d["author"]) == surname(e.get("author"))]
                    verdicts.append((e, other, why, same[0] if same else None))
                bad = [v for v in verdicts if v]
                if not bad:
                    continue
                whole = len(bad) == len(verdicts) and not any(v[3] for v in bad)
                for e, other, why, fix in bad:
                    c = {"source": rec.get("source") or "", "side": e.get("side") or "",
                         "author": e.get("author") or "", "belongs_to": other,
                         "found_by": why}
                    if fix:
                        c.update(action="filed", text=fix["text"],
                                 filed=fix["source"], released=fix["released"])
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
                        printed = (f"{rec.get('source') or 'The House Calendar'} printed "
                                   f"{kind_name(c.get('belongs_to'))}'s report here.")
                        if c.get("action") == "filed":
                            e["text"] = c.get("text") or ""
                            day = said_day(c.get("released"))
                            e["note"] = (f"{printed} This is the report as the committee "
                                         f"filed it with the Clerk"
                                         + (f" on {day}" if day else "") + ".")
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
    # Silence is not success. With neither dump on disk this compares nothing
    # but opening words, and says so rather than reporting a clean record.
    if not filed:
        print(f"\nNO FILED REPORTS: neither {PAST} nor {CURRENT} gave one, so only "
              "each report's opening words are checked.")
    got, census = check(reports, filed)
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
