#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.4
"""
Amendment text, out of the calendars already on this disk.

    python3 extract_amendments.py             # write amendments.json
    python3 extract_amendments.py --show 2    # print two and write nothing
    python3 extract_amendments.py --check     # coverage only, write nothing

No network. Reads calendars/ and narratives.json, writes amendments.json.

WHERE THIS CAME FROM

`fetch_bill_status.py --links` established that amendment text is not on the
bill status page. `probe_amendments.py` then found 545 amendment numbers in the
cached calendars followed by drafting language -- which is not a mention of an
amendment, it is the amendment.

The shape, from that probe:

    2025-3111h) Proposed by Rep. Chourasia
    Amend RSA 415:6-e, III(a) as inserted by section 1 of the bill by
    replacing it with the following: ...

A number, a bracket, who proposed it, then the instructions. The next
amendment opens the same way, which is the boundary: an extractor that runs
past the end of one picks up the next item of business and prints it as part of
the bill.

TWO THINGS THE PDF DOES TO THE TEXT

Words break across lines with a hyphen -- "provid- ers", "adminis- tration" --
and joining the lines without repairing that leaves the hyphen in the middle of
a word. But real hyphens exist too, in "sixty-day" and "RSA 415:6-e", so only a
break where the next fragment starts lowercase is repaired.

Line numbers and page furniture are stripped: calendars are printed with a
running header and a number down the margin, and both land in the middle of
sentences when the page is read as text.

WHAT IT DOES NOT DO

It does not decide which bill an amendment belongs to. The docket already says,
in the lines narrative.py reads, so the join happens there and no guess is made
here. An amendment nobody cites is still recorded; it simply goes unused.
"""

import argparse
import json
import narrative
import re
import sys
from collections import Counter
from pathlib import Path

# "2025-3111h)" -- the marker that opens an amendment in the calendar.
OPEN_RE = re.compile(r"\b(?P<num>\d{4}-\d{3,4}[a-z]?)\s*\)")

# "Proposed by Rep. Brown", and also "Proposed by the Committee on Health,
# Human Services and Elderly Affairs-c". A committee proposes more amendments
# than any member does, and a pattern that only knew members left the whole
# phrase sitting at the front of the amendment text.
PROPOSER_RE = re.compile(
    r"Proposed by\s+(?P<who>(?:Rep|Sen)s?\.\s+[^\n]{2,80}?"
    r"|the Committee on\s+[^\n]{2,80}?)"
    r"\s*[\u2013\u2014-]?\s*c?"
    r"(?=\s+Amend\b|\s+Amendment\b|$)", re.I)

# What tells an amendment from a reference to one.
DRAFTING = re.compile(
    r"amend the bill|amend the said bill|amend RSA|replacing all after the "
    r"enacting clause|insert after section|delete section|shall read as "
    r"follows|amend paragraph", re.I)

# A running header, a bare page number, a margin line number, on its own line.
NOISE = re.compile(
    r"^\s*(?:\d{1,3}|HOUSE RECORD|SENATE RECORD|\d+\s+HOUSE RECORD|"
    r"[A-Z][a-z]+day,\s+\w+\s+\d{1,2},\s+\d{4})\s*$")

# And the same header where it is NOT on its own line. A PDF read as text lays
# the header into the middle of whichever sentence spans the page break:
#
#     ... by replacing it with the following: 31 JANUARY 2025 HOUSE RECORD 29
#         II. A student who has obtained ...
#
# which is amendment text with a page header buried in it, published as though
# the drafter had written it. A page number or the title must be adjacent: an
# all-capital date alone is not enough to delete, because bill text is
# sometimes set in capitals.
_MON = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|"
        "NOVEMBER|DECEMBER")
_DATE = rf"\d{{1,2}}\s+(?:{_MON})\s+\d{{4}}"
RUNNING_HEAD = re.compile(
    r"\s*(?:"
    rf"\d{{1,3}}\s+{_DATE}(?:\s+HOUSE\s+RECORD)?"
    rf"|{_DATE}\s+HOUSE\s+RECORD(?:\s+\d{{1,3}})?"
    rf"|HOUSE\s+RECORD\s+\d{{1,3}}\s+{_DATE}"
    rf"|\d{{1,3}}\s+HOUSE\s+RECORD\s+{_DATE}"
    rf"|{_DATE}\s+\d{{1,3}}\s+HOUSE\s+RECORD"
    rf"|HOUSE\s+RECORD\s+{_DATE}"
    r")\s*")


def repair_hyphens(doc):
    """Rejoin words the typesetter cut in half, and only those.

    "provid- ers" is one word broken across a line. "sixty- day" is two, broken
    at a hyphen that was always there. A pattern cannot tell them apart: both
    are a hyphen at a line break followed by lowercase.

    So the document is asked. Legal drafting repeats its terms, and if
    "providers" appears anywhere else here then the break was the typesetter's;
    if "sixty-day" appears elsewhere then the hyphen is the drafter's.

    Where the document says neither, the HYPHEN STAYS. An unwanted hyphen is a
    visible artefact of a PDF. A wrongly joined word is a word the General
    Court did not write, printed as though it had.
    """
    cand = set(re.findall(r"(\w{2,})-\s*\n\s*([a-z]\w+)", doc))
    if not cand:
        return doc
    flat = re.sub(r"\s+", " ", doc)
    joinable = set()
    for a, b in cand:
        # Case-insensitive: the word is as likely to be attested at the start
        # of a sentence as in the middle of one.
        if re.search(rf"\b{re.escape(a + b)}\b", flat, re.I):
            joinable.add((a, b))          # attested as one word
        elif re.search(rf"\b{re.escape(a)}-{re.escape(b)}\b", flat, re.I):
            pass                          # attested as two; leave the hyphen
    def fix(m):
        a, b = m.group(1), m.group(2)
        return a + b if (a, b) in joinable else f"{a}-{b}"
    return re.sub(r"(\w{2,})-\s*\n\s*([a-z]\w+)", fix, doc)


def clean(text):
    """Join the lines back into prose without the page furniture."""
    lines = [ln for ln in text.splitlines() if not NOISE.match(ln)]
    joined = re.sub(r"\s+", " ", "\n".join(lines)).strip()
    return re.sub(r"\s{2,}", " ", RUNNING_HEAD.sub(" ", joined)).strip()


def amendments_in(text, source):
    """Every amendment printed in one calendar, from marker to next marker."""
    marks = [(m.start(), m.group("num"), m.end()) for m in OPEN_RE.finditer(text)]
    out = {}
    for i, (pos, num, after) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[after:end]
        if not DRAFTING.search(body[:600]):
            continue                      # a reference, not the amendment
        pm = PROPOSER_RE.search(body[:300])
        who = re.sub(r"\s+", " ", pm.group("who")).strip(" .,") if pm else ""
        if pm:
            body = body[pm.end():]
        body = clean(body)
        if len(body) < 80:
            continue
        prev = out.get(num)
        # The same amendment is reprinted in later calendars. Keep the fullest
        # copy: a truncated one is a page break, not a shorter amendment.
        if not prev or len(body) > len(prev["text"]):
            out[num] = {"text": body, "proposed_by": who, "source": source,
                        "chars": len(body)}
    return out


def cited(path):
    if not Path(path).exists():
        return {}
    narr = narrative.load_narratives(path)
    by_bill = {}
    for bid, rec in narr.items():
        nums = set()
        for e in rec.get("events", []):
            raw = e.get("raw", "") or ""
            if "amendment" in raw.lower():
                nums.update(re.findall(r"\b\d{4}-\d{3,4}[a-z]?\b", raw))
        if nums:
            by_bill[bid] = sorted(nums)
    return by_bill


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calendars", default="calendars")
    ap.add_argument("--narratives", default="narratives.json")
    ap.add_argument("--out", default="amendments.json")
    ap.add_argument("--show", type=int, default=0, help="print N, write nothing")
    ap.add_argument("--check", action="store_true", help="coverage only")
    ap.add_argument("--replace", action="store_true",
                    help="rewrite amendments.json from this run alone, "
                         "rather than merging into it")
    a = ap.parse_args()

    pdfs = sorted(set(list(Path(a.calendars).rglob("*.pdf"))
                      + list(Path(a.calendars).rglob("*.PDF"))))
    if not pdfs:
        sys.exit(f"No PDFs under {a.calendars}/ or below it.")

    sys.path.insert(0, ".")
    from fetch_committee_reports import extract_text

    print(f"reading {len(pdfs)} calendars, no network\n")
    found, per_file = {}, Counter()
    for f in pdfs:
        try:
            text, _ = extract_text(f)
        except Exception as e:
            print(f"  ! {f.name}: {e}")
            continue
        got = amendments_in(repair_hyphens(text), f.name)
        per_file[f.name] = len(got)
        for num, rec in got.items():
            if num not in found or rec["chars"] > found[num]["chars"]:
                found[num] = rec

    print(f"{len(found):,} amendments with their text")
    for name, k in per_file.most_common(3):
        if k:
            print(f"  {k:>4} in {name}")
    if found:
        lens = sorted(r["chars"] for r in found.values())
        print(f"  length: shortest {lens[0]:,}, median "
              f"{lens[len(lens) // 2]:,}, longest {lens[-1]:,} characters")
        named = sum(1 for r in found.values() if r["proposed_by"])
        print(f"  {named:,} name who proposed them")

    by_bill = cited(a.narratives)
    want = {n for ns in by_bill.values() for n in ns}
    if want:
        hit = want & set(found)
        bills = [b for b, ns in by_bill.items() if set(ns) & hit]
        print(f"\nthe docket cites {len(want):,} amendments across "
              f"{len(by_bill):,} bills")
        print(f"{len(hit):,} of those have text here, on {len(bills):,} bills "
              f"({100 * len(hit) / len(want):.0f}%)")
        print("Every calendar fetched from here raises that; nothing else has "
              "to change.")

    if a.show:
        for num, rec in list(found.items())[:a.show]:
            print("\n" + "=" * 70)
            print(f"{num}  {rec['proposed_by'] or '(proposer not printed)'}"
                  f"   {rec['source']}, {rec['chars']:,} chars")
            print("=" * 70)
            print(rec["text"][:1200])
        print("\nNothing written, because --show was given.")
        return
    if a.check:
        print("\nNothing written, because --check was given.")
        return

    out = Path(a.out)
    prior = {}
    if out.exists():
        try:
            prior = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            prior = {}
    if not isinstance(prior, dict):
        prior = {}
    # MERGED, NOT REPLACED. The only guard here was a shrink below half, so
    # a run over one year's calendars -- 660 found for 2019 against 663 on
    # file -- passed it and wrote a file holding 2019 and nothing of 2025-2026.
    # Every amendment number carries its year ("2025-0067h"), so this run's
    # finds replace their own numbers and leave every other one alone. A
    # full rewrite from what this run found is a flag, not an accident.
    if a.replace:
        if prior and len(found) < len(prior) * 0.5:
            print(f"\nNOT WRITING {a.out}: --replace with {len(found):,} "
                  f"found against {len(prior):,} on file. That is a read that "
                  "failed, not amendments that were withdrawn.")
            return
        merged = found
    else:
        merged = {**prior, **found}
        kept = len(set(prior) - set(found))
        if kept:
            print(f"  kept {kept:,} on file that this run did not read "
                  f"(--replace to rewrite from this run alone)")
    out.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"\n-> {a.out}")
    print("build_site_v2.py joins these to bills on the numbers the docket "
          "cites.")


if __name__ == "__main__":
    main()
