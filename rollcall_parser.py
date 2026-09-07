#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.3
"""
Parse RollCallSummary.txt into per-bill voting records.

Two things this handles that a naive parser gets wrong:

1. THE COLUMNS MEAN DIFFERENT THINGS IN EACH CHAMBER.
   Senate: field 7 is total members voting (yeas+nays), field 8 is the rest.
   House:  fields 7 and 8 are two separate categories of non-voting member, and
           yeas+nays+f7+f8 equals the seat count (395 early in 2026, 384 by
           August as vacancies accumulate).
   Which House category is "excused" and which is "absent" is NOT established.
   They are reported together as "did not vote" rather than guessed at.

2. A MAJORITY IS NOT ALWAYS ENOUGH.
   Veto overrides need two thirds of those voting. Constitutional amendments
   (CACRs) need three fifths of the ENTIRE membership -- 240 of 400 in the
   House, 15 of 24 in the Senate -- regardless of how many showed up. CACR 10
   drew 194-158 in March 2026: a clear majority, and it failed. The official
   status reads "Failed to Pass with Necessary Three-fifths Vote". Showing the
   tally without the threshold actively misleads.

3. A BILL NUMBER MEANS NOTHING WITHOUT A TERM.
   HB396 exists in every biennium. The download covers the current session
   only, so that never came up; rollcalls/ holds a file per past year fetched
   from the General Court's database, and the moment 2023 sits beside 2025 a
   flat {bill: votes} map merges two different bills. The output is keyed on
   the TERM, not the year, because one bill is voted on in both years of its
   biennium -- HB56 was filed in 2025 and voted on in 2026.

    python3 rollcall_parser.py --file RollCallSummary.txt --bill HB1442
    python3 rollcall_parser.py --file RollCallSummary.txt --all --out rollcalls.json
"""

import argparse
import json
import proceedings as P
import re
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime

SEATS = {"H": 400, "S": 24}

# The House writes motions as abbreviations, the Senate spells them out.
# Same motion, two vocabularies.
QUESTION = {
    "otp": ("Ought to Pass", "pass the bill"),
    "ought to pass": ("Ought to Pass", "pass the bill"),
    "otpa": ("Ought to Pass with Amendment", "pass the bill with changes"),
    "ought to pass w/amendment": ("Ought to Pass with Amendment", "pass the bill with changes"),
    "ought to pass with amendment": ("Ought to Pass with Amendment", "pass the bill with changes"),
    "ought to pass w/ amendment": ("Ought to Pass with Amendment", "pass the bill with changes"),
    "itl": ("Inexpedient to Legislate", "kill the bill"),
    "inexpedient to legislate": ("Inexpedient to Legislate", "kill the bill"),
    "table": ("Lay on Table", "set the bill aside without killing it"),
    "laid on table": ("Lay on Table", "set the bill aside without killing it"),
    "remove from table": ("Remove From Table", "take the bill back up"),
    "interim study": ("Interim Study", "study the bill after the session"),
    "refer to interim study": ("Interim Study", "study the bill after the session"),
    "indefinitely postpone": ("Indefinitely Postpone",
                              "kill the bill and bar the subject for the rest of the term"),
    "concur": ("Concur", "accept the other chamber's changes"),
    "nonconcur": ("Nonconcur", "reject the other chamber's changes"),
    "adopt amendment": ("Adopt Amendment", "change the bill"),
    "committee amendment": ("Adopt Committee Amendment", "change the bill"),
    "adopt floor amendment": ("Adopt Floor Amendment", "change the bill on the floor"),
    "floor amendment": ("Adopt Floor Amendment", "change the bill on the floor"),
    "adopt cofc report": ("Adopt Conference Committee Report",
                          "accept the compromise version"),
    "conference committee report": ("Adopt Conference Committee Report",
                                    "accept the compromise version"),
    "veto override": ("Veto Override", "override the governor's veto"),
    "veto message - roll call required": ("Veto Override", "override the governor's veto"),
    "reconsider": ("Reconsider", "vote on the bill again"),
    "reconsideration": ("Reconsider", "vote on the bill again"),
    "special order": ("Special Order", "move the bill to a different point in the day"),
}

# Motions that are chamber business rather than action on a bill.
PROCEDURAL = {"call of the roll", "rules suspension", "limit debate", "print remarks",
              "shall member continue", "uphold ruling of chair",
              "uphold ruling of the chair", "affirm the report"}


def threshold(question_std, bill, body, yeas, nays):
    """(needed, rule_text, basis) or (None, None, None) for a simple majority."""
    voting = yeas + nays
    if question_std == "Veto Override":
        need = -(-2 * voting // 3)          # ceil(2/3 of those voting)
        return need, "two thirds of members voting", voting
    if bill and bill.upper().startswith("CACR"):
        seats = SEATS[body]
        need = -(-3 * seats // 5)           # ceil(3/5 of entire membership)
        return need, f"three fifths of the entire {seats}-member membership", seats
    return None, None, None


def parse(path, want_bill=None):
    out = []
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for ln, line in enumerate(fh, 1):
            p = line.rstrip("\n").split("|")
            if len(p) < 13:
                continue
            try:
                year, body, num = p[0].strip(), p[1].strip(), int(p[2])
                yeas, nays = int(p[5]), int(p[6])
                f7, f8 = int(p[7] or 0), int(p[8] or 0)
            except ValueError:
                continue
            if body not in SEATS:
                continue

            bill = p[4].strip()
            if want_bill and bill.upper() != want_bill.upper():
                continue

            raw_q = p[11].strip()
            key = re.sub(r"\s+", " ", raw_q.lower()).strip()
            # Senate appends section notes: "Ought to Pass w/Amendment - Remainder"
            # "Ought to Pass with Amendment- Sections 1-10 and the effective
            # date". Splitting leaves a trailing hyphen when the source writes
            # no space before it, and "ought to pass with amendment-" matches
            # nothing in the glossary, so the motion printed verbatim.
            base = re.split(r"\s+-\s+|\s*-?\s*sections?\b", key)[0].strip(" -\u2013,")
            std, plain = QUESTION.get(key) or QUESTION.get(base) or (raw_q, None)

            try:
                when = datetime.strptime(p[3].strip(), "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                when = None

            # Chamber-specific: see module docstring.
            if body == "S":
                voting, not_voting = f7, f8
                if voting != yeas + nays:
                    voting = yeas + nays
            else:
                voting = yeas + nays
                not_voting = f7 + f8
            seated = yeas + nays + f7 + f8 if body == "H" else SEATS["S"]

            need, rule, basis = threshold(std, bill, body, yeas, nays)
            if need is None:
                passed = yeas > nays
                margin_note = None
            else:
                passed = yeas >= need
                if not passed and yeas > nays:
                    margin_note = (f"A majority voted yes, but this needed {need} "
                                   f"({rule}) and fell {need - yeas} short.")
                else:
                    margin_note = f"Needed {need} \u2014 {rule}."

            out.append({
                "year": year, "body": body, "number": num,
                "date": when.strftime("%Y-%m-%d") if when else "",
                "time": when.strftime("%H:%M") if when else "",
                "bill": bill or None,
                "procedural": (not bill) or key in PROCEDURAL,
                "question": std, "question_raw": raw_q, "question_plain": plain,
                "yeas": yeas, "nays": nays, "voting": voting, "not_voting": not_voting,
                "seats": SEATS[body], "seated": seated,
                "vacancies": SEATS[body] - seated,
                "threshold_needed": need, "threshold_rule": rule,
                "passed": passed, "threshold_note": margin_note,
                "title": p[12].strip(),
            })
    return out


def parse_all(current, extra_dir):
    """Every roll call this machine has, the download and the archive both.

    rollcalls/RollCallSummary_<year>.txt is written by fetch_rollcalls_db.py
    from the General Court's database, one file per past session year. The
    download is the current session and is read first, so if a year somehow
    appears in both the download's row is the one kept -- it is the copy the
    General Court publishes directly, and the database's answer was verified
    against it rather than the other way round.

    Deduplicated on (year, body, number), which is what identifies a roll call.
    """
    seen, out = set(), []
    files = [Path(current)] if Path(current).exists() else []
    d = Path(extra_dir)
    if d.is_dir():
        files += sorted(d.glob("RollCallSummary_*.txt"))
    if not files:
        return [], []
    for f in files:
        kept = 0
        for r in parse(f):
            key = (r["year"], r["body"], r["number"])
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
            kept += 1
        print(f"  {f}: {kept:,} roll calls")
    return out, files


def sentence(r):
    ch = "House" if r["body"] == "H" else "Senate"
    when = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%B %d, %Y") if r["date"] else ""
    verb = "voted" if r["passed"] else "voted against a motion"
    what = r["question_plain"] or f"the motion \u201c{r['question']}\u201d"
    if r["passed"]:
        s = f"On {when} the {ch} voted to {what}, {r['yeas']}\u2013{r['nays']}."
    else:
        s = f"On {when} the {ch} rejected a motion to {what}, {r['yeas']}\u2013{r['nays']}."
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="RollCallSummary.txt",
                    help="the current session's bulk download")
    ap.add_argument("--dir", default="rollcalls",
                    help="a directory of RollCallSummary_<year>.txt files for "
                         "past sessions, from fetch_rollcalls_db.py")
    ap.add_argument("--bill")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()

    rows, files = parse_all(a.file, a.dir)
    if not files:
        sys.exit(f"No roll call file to read: neither {a.file} nor anything in "
                 f"{a.dir}/.")
    if a.bill:
        rows = [r for r in rows if (r["bill"] or "").upper() == a.bill.upper()]
    if not rows:
        sys.exit("No roll calls matched.")

    if a.out:
        # Keyed on the term, not the bill: HB396 exists in every biennium, and
        # the moment a past year sits beside the current one a flat map merges
        # two different bills. Not on the year either -- a bill filed in 2025
        # is voted on in 2026 and both belong to the same record.
        by_term = defaultdict(lambda: defaultdict(list))
        for r in rows:
            by_term[P.term_of(r["year"])][r["bill"] or "_procedural"].append(r)
        stray = by_term.pop("", None)
        if stray:
            print(f"  {sum(len(v) for v in stray.values()):,} roll calls have "
                  "no readable session year and are left out")
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(by_term, fh, indent=2)
        unknown = sorted({r["question_raw"] for r in rows if r["question_plain"] is None
                          and not r["procedural"]})
        for term in sorted(by_term):
            n_b = len(by_term[term]) - (1 if "_procedural" in by_term[term] else 0)
            n_r = sum(len(v) for v in by_term[term].values())
            print(f"  {term}: {n_r:,} roll calls across {n_b:,} bills")
        print(f"{len(rows):,} roll calls across {len(by_term)} term(s) -> {a.out}")
        thr = [r for r in rows if r["threshold_needed"]]
        near = [r for r in thr if not r["passed"] and r["yeas"] > r["nays"]]
        print(f"{len(thr):,} votes carried a supermajority threshold; "
              f"{len(near):,} won a majority and still failed")
        if unknown:
            print(f"\n{len(unknown)} motion types not in the glossary "
                  "(shown verbatim, never guessed):")
            for u in unknown[:20]:
                print(f"    {u}")
        return

    for r in sorted(rows, key=lambda x: (x["date"], x["number"])):
        tag = "" if r["passed"] else "  [failed]"
        print(f"\n{r['date']}  {'House' if r['body']=='H' else 'Senate'} "
              f"roll call #{r['number']}{tag}")
        print(f"  {r['question']}")
        vac = (f", {r['vacancies']} seat{'s' if r['vacancies'] != 1 else ''} vacant"
               if r["vacancies"] else "")
        print(f"  {r['yeas']} yes, {r['nays']} no   "
              f"({r['voting']} voting, {r['not_voting']} did not vote{vac})")
        if r["threshold_note"]:
            print(f"  {r['threshold_note']}")
        print(f"  \u2192 {sentence(r)}")


if __name__ == "__main__":
    main()
