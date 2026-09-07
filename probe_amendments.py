#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.3
"""
Is the amendment text already on this disk?

    python3 probe_amendments.py            # what the cached calendars hold
    python3 probe_amendments.py --show 3   # print three in full

No network. Nothing written. Reads only calendars/*.pdf and narratives.json.

WHY ASK

Amendment text is the largest remaining content gap, and `fetch_bill_status.py
--links` settled that it is not on the bill status page: ten address shapes
across 2,234 cached pages and not one of them an amendment.

But the House Calendar prints amendments. It is where a member reads one before
voting on it, and it is already parsed by fetch_committee_reports.py for the
majority and minority reports. Twenty-nine of them sit in calendars/ right now.

So before writing a fetcher for an address nobody has found, this asks whether
the text is already here.

WHAT IT REPORTS

  1. How many amendment numbers appear in the cached calendars at all.
  2. How many of the amendments the DOCKET cites are among them -- the coverage
     number, and the one that decides whether this is a route worth taking.
  3. What sits around each one, so the shape of an amendment block can be seen
     rather than guessed at. Whether it is followed by the text of the
     amendment or by a bare line saying it was adopted is the whole question,
     and it is not one to assume the answer to.

WHAT COMES NEXT EITHER WAY

  High coverage, text present  -> an extractor, and amendment diffing needs no
                                  network at all
  Numbers present, text absent -> the calendars only reference amendments, and
                                  the text lives somewhere still unfound
  Nothing found                -> the cached calendars are the wrong documents,
                                  and the House Journal is the next place to
                                  look
"""

import argparse
import json
import narrative
import re
import sys
from collections import Counter
from pathlib import Path

# "2026-1719h", "2026-0503s". Four-digit year, a serial, and a chamber letter.
AMEND_NUM = re.compile(r"\b(\d{4}-\d{3,4}[a-z]?)\b")

# What an amendment block would open with if the calendar prints one. These are
# the forms the General Court uses in its own drafting instructions; finding
# them near a number is the difference between the text being here and a
# mention of it being here.
TEXT_MARKS = re.compile(
    r"amend the bill by|amend the said bill by|by replacing all after the "
    r"enacting clause|amend RSA|insert after section|delete section|"
    r"amend paragraph|shall read as follows", re.I)


def cited_amendments(path):
    """Every amendment number the docket refers to, per bill."""
    if not Path(path).exists():
        return {}, Counter()
    narr = narrative.load_narratives(path)
    by_bill, all_nums = {}, Counter()
    for bid, rec in narr.items():
        nums = set()
        for e in rec.get("events", []):
            if "amendment" in (e.get("raw", "") or "").lower():
                nums.update(AMEND_NUM.findall(e.get("raw", "")))
        if nums:
            by_bill[bid] = nums
            all_nums.update(nums)
    return by_bill, all_nums


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calendars", default="calendars")
    ap.add_argument("--narratives", default="narratives.json")
    ap.add_argument("--show", type=int, default=2,
                    help="print this many amendment blocks in full")
    a = ap.parse_args()

    # Recursive: the downloader files calendars under a year folder, so a
    # top-level glob finds a directory and reports an empty cupboard.
    cal = Path(a.calendars)
    pdfs = sorted(set(list(cal.rglob("*.pdf")) + list(cal.rglob("*.PDF"))))
    if not pdfs:
        here = [str(x) for x in cal.iterdir()][:6] if cal.exists() else []
        sys.exit(f"No PDFs under {cal}/ or below it."
                 + (f"\nWhat is there: {', '.join(here)}" if here else
                    f"\n{cal}/ does not exist. Try --calendars <folder>."))

    try:
        sys.path.insert(0, ".")
        from fetch_committee_reports import extract_text
    except Exception as e:
        sys.exit(f"Cannot borrow the PDF reader from fetch_committee_reports: {e}")

    print(f"reading {len(pdfs)} cached calendars, no network\n")

    found, per_file, contexts = Counter(), {}, []
    for f in pdfs:
        try:
            text, _ = extract_text(f)
        except Exception as e:
            print(f"  ! {f.name}: {e}")
            continue
        nums = AMEND_NUM.findall(text)
        per_file[f.name] = len(set(nums))
        found.update(nums)
        for m in AMEND_NUM.finditer(text):
            window = text[m.start(): m.start() + 900]
            if TEXT_MARKS.search(window):
                contexts.append((f.name, m.group(1), window))

    print(f"{len(found):,} distinct amendment numbers across the calendars")
    top = [f"{n} in {k}" for k, n in
           sorted(per_file.items(), key=lambda x: -x[1])[:3] if n]
    if top:
        print("  busiest files: " + "; ".join(top))

    by_bill, cited = cited_amendments(a.narratives)
    if cited:
        hit = sum(1 for n in cited if n in found)
        pct = 100 * hit / len(cited)
        print(f"\nthe docket cites {len(cited):,} amendments across "
              f"{len(by_bill):,} bills")
        print(f"{hit:,} of them appear in a cached calendar ({pct:.0f}%)")
        if pct >= 60:
            print("  -> worth an extractor: most of what the site would show "
                  "is already here")
        elif pct > 0:
            print("  -> partial. The calendars carry some of them; the rest "
                  "are elsewhere")
        else:
            print("  -> none of the cited amendments are in these files")

    print(f"\n{len(contexts):,} of those numbers are followed by drafting "
          "language,\nwhich is what the text of an amendment looks like.")
    if not contexts:
        print("  None are. The calendars name amendments without printing "
              "them,\n  so the text is somewhere still unfound and the House "
              "Journal is\n  the next place to look.")
        return

    print("\n" + "=" * 70)
    print("WHAT AN AMENDMENT BLOCK LOOKS LIKE HERE")
    print("=" * 70)
    for name, num, window in contexts[:max(1, a.show)]:
        body = re.sub(r"\s+", " ", window).strip()
        print(f"\n[{num}] from {name}")
        print("-" * 70)
        print(body[:800])
    print("\n" + "=" * 70)
    print("Send the blocks above. Where one ENDS is the part that cannot be\n"
          "guessed: an extractor that runs past the end of an amendment picks\n"
          "up the next item of business and prints it as part of the bill.")


if __name__ == "__main__":
    main()
