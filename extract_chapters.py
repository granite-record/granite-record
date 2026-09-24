#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.5
"""
The chapter of the session laws each bill became, read out of the docket.

    python3 extract_chapters.py            # writes chapters.json
    python3 extract_chapters.py --check    # the measurements; writes nothing

No network. Reads every docket on this disk and nothing else: db/Docket.psv
(1989-2016 and 2025-2026), the fetched Docket_YYYY-YYYY.txt (2015-2024) and
Docket.txt (the current term). Where two of them cover a term they are one
record twice -- the web page is drawn from the database -- and a number read
from both collapses to one. data/bills.json names the bills; the output is
{term: {bill: {...}}}, like every per-bill file.

WHY THE DOCKET

Until 11 September a chapter was on the page for 2023-2026 only, from the
status page's chapter field, and for nobody in the seventeen terms before.
The docket states one in every term: the clerk writes it on the line that
records the signature -- "Signed by Governor Sununu 09/06/2019; Chapter 339"
-- and has since 1989 ("SIGNED BY GOVERNOR 5/8/89 EFF: 7/7/89 CHAP: 112").
build_site_v2 still prefers the status page's field for the terms it has one,
and where both exist they agree on 1,268 of 1,270 bills. The two they do not
are the clerk's typing: SB 62 of 2025 is chapter 38 in its own enrolled text
and in the field, and 39 in the docket, which is HB 511's number. That is
also how such a slip is found everywhere else -- see WHAT IS WITHHELD.

HOW A NUMBER IS READ

After "Chapter", "Chap.", "Chap:" or "Chap-", which are nearly every form the
clerks used, and not when ":1" or "-A" follows it: that is a section or an
RSA chapter ("Chapter 23:1 Committee Members Appointed by President"). The
rarer "CH.", "Chap,", "Chapt:" and "Chp." are read too, but only on the line
that made the bill law, because on any other line they name another law
(see CHAPTER_RARE). "See" and
whatever follows it on the line are dropped first, because they name another
law -- "See Chapter 240 for additional dates", "(SEE HB27, CH360 FOR EFF.
DATES)". A row is read only when its LSR is the bill's own: the database's
2016 rows carry two bills under another bill's LSR.

WHAT IS WITHHELD

Two bills of one term claiming one number in the same year's laws. One of
them is a typing error and the docket cannot say which, so both are left
blank and listed as withheld rather than one guessed at. Not a clash: a
special session's laws, which are numbered on their own (SSHB 1 of 2008 is
chapter 1, and so is HB 692); and a bill signed in January, which is often
the previous year's laws still being numbered (HB 778 of 2025, signed
8 January 2026, is chapter 305; so is HB 1469, signed that July).
The enrolled text settles each one -- its first line is "CHAPTER 263 SB 45 -
FINAL VERSION" -- and fetch_legislation.py is bringing it down.

--check also scores the numbers against every enrolled text already on disk
under legislation/, which nothing here wrote.

AND A FAILED OVERRIDE

A vetoed bill has no chapter, and in the twelve terms whose dockets are not
narrated nothing else on the page can say what happened to the veto: the
status fields stop at VETOED BY GOVERNOR. So the line that says the
override failed -- "OVERRIDE GOV VETO, ML <FAILED 2/3> RC(14-10)", "Veto
Sustained, RC 165-175" -- is kept as override_failed on a bill with no
number, and build_site_v2 reads it the way it reads the signature line.
"""
import argparse
import glob
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import proceedings as P

DB = Path("db/Docket.psv")
BILLS = Path("data/bills.json")
OUT = Path("chapters.json")

# The number ends at a word boundary, or where the clerk ran it into the
# first of a list of effective dates -- "Chapter 0241I. Section 2 Effective
# 12/31/13", 2011's habit, which cost 21 laws of 2011-2012 their number
# until the I. was allowed for.
CHAPTER = re.compile(r"\bchap(?:ter)?\s*[.:\-]?\s*0*(\d{1,4})"
                     r"(?:(?=I{1,3}\.)|\b(?![:\-]\s*[0-9A-Z]))", re.I)
# THE RARER SPELLINGS, AND ONLY ON THE LINE THAT MADE THIS BILL LAW. Five
# laws carried their number in a form the pattern above does not read, and
# had no chapter on the site: 1993 HB 241 "CH.0066", 1999 HB 426 "Chap,
# 0070", and 2004 SB 335 "Chapt:0099", SB 438 "Chapt:0066" and SB 481 "Chp.
# 0258" -- the last four the chapter their enrolled text is headed with. The
# same forms also stand in the dockets for OTHER laws: "CH.124,1989" on 1989
# HB 1, "for (Ch. 47)" on a study committee's membership line, "{LSR 0155,
# HB 154, CH. 183, 1997 SIGNED BY GOV 6/18/97}" on 1996 HB 1179. Read on
# every line, they would have cost eight laws the chapter they have, by
# giving each a second number, and given two bills another law's. So they
# count only on a law line that did not fail and names no other bill.
CHAPTER_RARE = re.compile(r"\b(?:ch(?=\s*\.)|chp|chapt)\s*[.:\-,]?\s*0*(\d{1,4})"
                          r"(?:(?=I{1,3}\.)|\b(?![:\-]\s*[0-9A-Z]))"
                          r"|\bchap\s*,\s*0*(\d{1,4})\b", re.I)
OTHER_BILL = re.compile(r"\b(?:HB|SB|HCR|SCR|HJR|SJR|CACR|HR|SR)\s*\d", re.I)
SEE = re.compile(r"\(?\bsee\b[^)]*\)?", re.I)
SPECIAL = re.compile(r"spec(?:ial)?\.?\s*sess", re.I)
# The lines that make a bill law, or record that it did. A failed override
# ("OVERRIDE VETO FAILED 2/3") matches too and carries no number, which is
# right: it is counted as a law line with no chapter, not given one.
LAW = re.compile(r"signed by|governor signed|without (?:the )?signature"
                 r"|law without|overrid|became law|chaptered", re.I)
# A law line that did not make law. "ML" is the 1990s docket's "motion
# lost": "OVERRIDE GOV VETO, ML RC(17-299)" is HB 149 of 1997's veto standing.
FAILED = re.compile(r"fail|sustain|\bML\b", re.I)
# The veto standing, in every way the clerks wrote it: "Veto Sustained",
# "=VETO SUSTAINED=", "OVERRIDE VETO FAILED 2/3", "OVERRIDE GOVERNOR'S VETO
# FAILS 2/3", "OVERRIDE GOV VETO, ML <FAILED 2/3>".
VETO_STOOD = re.compile(r"veto\s+sustained|overrid[^;]*?(?:\bfail|\bML\b)",
                        re.I)
DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2}(?:\d{2})?)\b")


def rows():
    """(source, session year, lsr, bill, row date, text) from every docket."""
    if DB.exists():
        with open(DB, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                r = line.rstrip("\r\n").split("|")
                if len(r) >= 7:
                    yield (DB.name, r[0], r[1], r[4].replace(" ", ""), r[3],
                           r[6])
    # Docket_db_*.txt are db/Docket.psv reshaped, so they are not read twice.
    for p in sorted(glob.glob("Docket_[0-9]*.txt")) + ["Docket.txt"]:
        if not Path(p).exists():
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                r = line.rstrip("\r\n").split("|")
                if len(r) >= 6:
                    yield p, r[0], r[1], r[3].replace(" ", ""), r[2], r[5]


def when(text, fallback):
    """(year, month) of the first date on the line, else of the row's date."""
    for s in (text, fallback):
        m = DATE.search(s or "")
        if m:
            y = int(m.group(3))
            y += 1900 if y > 50 and y < 100 else 2000 if y < 100 else 0
            return y, int(m.group(1))
    return None, None


def read(bills):
    """{(term, bill): facts} from every docket, and a Counter of what was
    passed over."""
    found = defaultdict(lambda: {"numbers": {}, "law": False,
                                 "special": False, "dates": [],
                                 "failed": ""})
    skipped = Counter()
    for src, year, lsr, bid, rowdate, text in rows():
        term = P.term_of(year)
        rec = bills.get(term, {}).get(bid)
        if not rec:
            skipped["bill not in data/bills.json"] += 1
            continue
        if lsr.strip().zfill(4) != (rec.get("lsr_num") or "").zfill(4):
            skipped["another bill's LSR"] += 1
            continue
        f = found[(term, bid)]
        if LAW.search(text):
            f["law"] = True
            if not FAILED.search(text):
                f["dates"].append(when(text, rowdate))
        if VETO_STOOD.search(text) and not f["failed"]:
            f["failed"] = text.strip()
        plain = SEE.sub(" ", text)
        nums = [int(m.group(1)) for m in CHAPTER.finditer(plain)]
        if (LAW.search(text) and not FAILED.search(text)
                and not OTHER_BILL.search(plain)):
            nums += [int(m.group(1) or m.group(2))
                     for m in CHAPTER_RARE.finditer(plain)]
        for n in nums:
            if not 0 < n < 1500:
                continue
            if n not in f["numbers"]:
                f["numbers"][n] = (text.strip(), when(text, None))
            if SPECIAL.search(text):
                f["special"] = True
        if bid.startswith("SS"):
            f["special"] = True
    return found, skipped


def settle(found):
    """{term: {bill: record}}, and what was withheld and why."""
    out = defaultdict(dict)
    many, taken = [], defaultdict(list)
    for (term, bid), f in found.items():
        if not f["numbers"]:
            # No law, and a line saying the override failed: kept, because
            # a term with no narrated docket has nothing else that says so,
            # and its status fields stop at VETOED BY GOVERNOR -- which the
            # page read as "awaiting an override vote" twenty-eight years on.
            if f["failed"]:
                out[term][bid] = {"chapter": None,
                                  "override_failed": f["failed"][:200]}
            continue
        if len(f["numbers"]) > 1:
            many.append((term, bid, sorted(f["numbers"])))
            continue
        (n, (line, dated)), = f["numbers"].items()
        # Dated by the last act that made it law -- the signature, or the
        # second chamber's override -- and not by the line holding the
        # number, whose first date is as often an effective date: SB 39 of
        # 2009, signed 17 April 2009, has "Sec 3 eff 12/31/10 ... Chapter
        # 0014" and would otherwise clash with 2010's chapter 14.
        dated = next((d for d in reversed(f["dates"]) if d[0]), dated)
        out[term][bid] = {"chapter": n, "line": line[:200]}
        if f["special"]:
            out[term][bid]["special"] = True
        taken[(term, n, f["special"])].append((bid, dated))

    withheld = []
    for (term, n, special), claims in taken.items():
        if len(claims) < 2 or special:
            continue
        by_year = defaultdict(list)
        for bid, (y, mo) in claims:
            if y and mo != 1:
                by_year[y].append(bid)
        for y, bids in by_year.items():
            if len(bids) < 2:
                continue
            for bid in bids:
                others = [b for b in bids if b != bid]
                out[term][bid] = {"chapter": None, "docket": n,
                                  "withheld": (f"{', '.join(others)} also "
                                               f"claims chapter {n} of {y}"),
                                  "line": out[term][bid]["line"]}
                withheld.append((term, bid, n, y))
    for term, bid, nums in many:
        out[term][bid] = {"chapter": None,
                          "withheld": f"its docket names chapters {nums}"}
        withheld.append((term, bid, nums, None))
    return out, withheld


def enrolled_check(out):
    """Score against the enrolled text under legislation/, which nothing
    here wrote. Its heading is "CHAPTER 339 HB 110-FN - FINAL VERSION".

    Returns (agree, differ, absent, doubled). A HEADING TWO BILLS SHARE IS NOT
    EVIDENCE ABOUT EITHER. Two laws cannot be one chapter, so where two of these
    pages print the same number one of them is wrong on its face, and the
    docket -- which numbers them distinctly -- is not what is in doubt. Both
    pairs this has met are that: 2017 HB 455 and HB 474 both head "CHAPTER 224"
    where the docket says 223 and 224, and 2018 HB 1331 and HB 1304 both head
    "CHAPTER 61" where the docket says 62 and 61. They are reported and they do
    not stop the build; a disagreement where the text's own numbering is
    consistent still does, because that one would be this parser's fault.
    """
    agree, differ, absent, doubled = 0, [], [], []
    said = {}
    for p in sorted(glob.glob("legislation/*/*.html")):
        parts = Path(p).parts
        year, stem = parts[-2], Path(p).stem
        m = re.match(r"([A-Z]+)0*(\d+)$", stem)
        if not m:
            continue
        bid = m.group(1) + m.group(2)
        t = html.unescape(re.sub(r"<[^>]+>", " ", Path(p).read_text(
            encoding="utf-8", errors="replace")))
        h = re.search(r"CHAPTER\s+(\d+)\s+(?:\(\s*)?%s\s*%s\b"
                      % (m.group(1), m.group(2)), re.sub(r"\s+", " ", t))
        if not h:
            continue
        said.setdefault((year, int(h.group(1))), []).append(bid)
        rec = out.get(P.term_of(year), {}).get(bid)
        if not rec or not rec.get("chapter"):
            absent.append(f"{bid} of {year}")
        elif rec["chapter"] == int(h.group(1)):
            agree += 1
        else:
            differ.append((year, int(h.group(1)), bid, rec["chapter"]))
    kept = []
    for year, text_ch, bid, docket_ch in differ:
        others = [b for b in said.get((year, text_ch), []) if b != bid]
        if others:
            doubled.append(f"{bid} of {year}: its text heads chapter {text_ch}, "
                           f"and so does {', '.join(others)}; the docket says "
                           f"{docket_ch}")
        else:
            kept.append(f"{bid} of {year}: text {text_ch}, docket {docket_ch}")
    return agree, kept, absent, doubled


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="print the measurements and write nothing")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    if not BILLS.exists():
        sys.exit(f"{BILLS} is not here; run build_data.py first.")
    bills = json.loads(BILLS.read_text(encoding="utf-8"))
    found, skipped = read(bills)
    out, withheld = settle(found)

    total = 0
    for term in sorted(bills):
        got = sum(1 for r in out.get(term, {}).values() if r.get("chapter"))
        law = sum(1 for (t, _), f in found.items() if t == term and f["law"])
        total += got
        print(f"  {term}: {got:4,} chapters  ({law:,} bills with a law line)")
    print(f"  {total:,} bills in {len(out)} terms have a chapter")
    failed = sum(1 for t in out.values() for r in t.values()
                 if r.get("override_failed"))
    print(f"  {failed:,} vetoed bills whose docket says the override failed")
    for k, n in skipped.most_common():
        print(f"  {n:,} docket rows passed over: {k}")
    if withheld:
        print(f"  {len(withheld)} withheld, the docket giving one number to "
              f"two bills:")
        for term, bid, n, y in sorted(withheld):
            print(f"    {bid} of {term}: {out[term][bid]['withheld']}")
    agree, differ, absent, doubled = enrolled_check(out)
    print(f"  against the enrolled text on disk: {agree} agree, "
          f"{len(differ)} differ, {len(absent)} have no chapter here")
    for d in differ[:10]:
        print(f"    differs: {d}")
    if doubled:
        print(f"  {len(doubled)} the published text cannot settle, because two "
              "bills' texts head the same chapter:")
        for d in doubled:
            print(f"    {d}")
    if not total:
        sys.exit("No chapter was read from any docket. Nothing written.")
    if differ:
        # A disagreement with the law's own text is a parser fault until
        # shown otherwise, and it would be printed on the page as fact.
        sys.exit("The docket and the enrolled text disagree. Nothing written.")
    if a.check:
        return
    Path(a.out).write_text(json.dumps(dict(sorted(out.items())), indent=1,
                                      sort_keys=True), encoding="utf-8")
    print(f"  -> {a.out}")


if __name__ == "__main__":
    main()
