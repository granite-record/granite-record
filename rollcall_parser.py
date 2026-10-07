#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.15
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

2. A MAJORITY IS NOT ALWAYS ENOUGH, AND THE RECORD SAYS WHICH.
   Veto overrides and rules suspensions need two thirds of those voting.
   Passing a constitutional amendment (a CACR) needs three fifths of the
   members IN OFFICE -- 239 of the 397 seated carried CACR 26 in 2012 -- not
   of the 400 seats. Other motions on a CACR are majority questions unless
   the House's rules of the day said otherwise, and the docket says so where
   they did. What each vote DECIDED is the clerk's, read off the docket (or,
   for a vote no docket line names, the Journal) by rollcall_outcomes.py after
   the ballots are counted; the rule here only supplies the number a
   threshold note and the chart's tick need, and the outcome where the record
   names none. CACR 10 drew 194-158 in March 2026: a clear majority, and it
   failed, "Lacking Necessary Three-Fifths Vote". Showing the tally without
   the threshold actively misleads.

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

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import proceedings as P
import rollcall_outcomes as RO
import re
from collections import Counter, defaultdict
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

# The bill-number column does not always hold a bill. The House's two votes on
# 8 January 2025 to amend House Rule 64 are filed under "HRULE64", which looks
# enough like a bill number to be keyed as one and gave the site a bill that
# does not exist. Those are votes about the chamber's own rules, which is what
# "procedural" already means here.
#
# The prefixes are the General Court's, listed rather than matched loosely: an
# any-letters-then-digits pattern is exactly what admitted HRULE64.
#
# THE LIST WAS SHORT OF THREE KINDS data/bills.json HOLDS, each with a record
# of its own: the House address (HA1 of 1999, to remove Chief Justice Brock
# from office, which the House voted 256-58 ought not to pass), HCO1 (2002's,
# on an election in the districts the court's order set, and the Senate's
# 13-11 on suspending its rules for it) and every special-session bill and
# resolution (SSHB1, SSSB1, SSHR1, SSHCR1). 68 roll calls on them were
# published as procedural, in /data/rollcalls.csv and the roll-call index,
# and twelve records said they had none. A vote on the chamber's own
# special-session rules ("SSRULES") or on a draft no record carries ("DRAFT")
# stays procedural.
BILL_NO = re.compile(r"^(?:(?:SS)?(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR|SJR)|HA|HCO)\d+$", re.I)

# ONE BILL NUMBER, HOWEVER THE FILE TYPED IT. Seven roll calls were typed some
# other way than data/bills.json keys their bill: "SB 406" (2012 S 118), "HB
# 315" (2017 S 198) and "SB 426" (2018 S 84) with a space, "sb136" (2016 H 21)
# in lower case, "SB115-FN" (2001 S 11) with its fiscal-note flag, and
# "HCACR2" and "HCACR15" (2016 H 31 and H 38) with the House's letter in
# front of a CACR. This parser stripped spaces and did not upper-case, so
# SB 136's vote was on no bill page; build_data upper-cased and did not strip,
# so the three spaced ones linked no member's ballot to the bill. The last
# three matched no bill number at all and were filed as procedural: CACR 2's
# 234-90 vote to kill it was on neither its page nor its member's, and
# /data/rollcalls.csv published it as procedural. Both now ask this.
FLAGS = re.compile(r"(?:-(?:FN|LOCAL|L|A))+$")


def bill_number(raw):
    """The bill a roll call's bill field names, keyed as data/bills.json keys
    it -- spaces out, upper case, no -FN, -L, -A or -LOCAL, HCACR read as CACR
    -- or "" where the field names no bill ("HRULE64", "SUSPRULE", blank)."""
    b = FLAGS.sub("", re.sub(r"\s+", "", raw or "").upper())
    b = re.sub(r"^HCACR(?=\d)", "CACR", b)
    return b if BILL_NO.match(b) else ""


# ONE NUMBER, TWO MEASURES IN ONE TERM. The Senate's roll calls 32 and 33 of
# 2009 are filed "SR1", and they are: 2009's SR 1, LSR 2009-1052, "requesting
# an opinion of the justices concerning the constitutionality of SB 21",
# introduced and passed 14-9 on 1 April 2009 (SJ 10 p.163). data/bills.json
# holds one SR 1 for 2009-2010, 2010's, on EPA vapor recovery, which was
# adopted on voice votes -- so its page drew both roll calls, and 23
# senators' pages said they had voted on it. Neither the General Court nor
# its file is wrong; one record per number in a term is this site's model. A
# roll call listed here is filed under a name no record carries, which keeps
# it off the other measure's page and every member's ballot unlinked, and is
# not procedural: it was a vote on a measure.
OTHER_MEASURE = {("2009", "S", 32): "SR1 (2009)", ("2009", "S", 33): "SR1 (2009)"}


def roll_call_bill(year, body, number, raw):
    """The bill a roll call is filed under: bill_number(raw), or for a roll
    call on a measure that shares its number with another measure's record
    in the same term, the name OTHER_MEASURE gives it."""
    try:
        k = (str(year).strip(), str(body).strip(), int(number))
    except (TypeError, ValueError):
        k = None
    return OTHER_MEASURE.get(k) or bill_number(raw)


def other_measure(r):
    """True for a parsed roll call OTHER_MEASURE files under its own name."""
    try:
        k = (str(r.get("year")).strip(), str(r.get("body")).strip(), int(r.get("number")))
    except (TypeError, ValueError):
        return False
    return k in OTHER_MEASURE and r.get("bill") == OTHER_MEASURE[k]


def threshold(question_raw, bill, yeas, nays, seated):
    """(needed, rule_text) or (None, None) for a simple majority.

    Provisional: parse_all() settles it from the ballots (the members in
    office) and the record. One rule, in rollcall_outcomes.threshold.
    """
    return RO.threshold({"question_raw": question_raw, "bill": bill,
                         "yeas": yeas, "nays": nays, "seated": seated})


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

            # A bill as data/bills.json keys it; anything else as typed.
            bill = roll_call_bill(year, body, num, p[4]) or p[4].strip()
            if want_bill and bill.upper() != (bill_number(want_bill)
                                              or want_bill).upper():
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
            # More members than seats is not a count, it is a misread column:
            # the database's House rows of 1999-2013 do not use fields 7 and 8
            # as the download does. parse_all() replaces this from the ballots
            # wherever they add up to the tally; where they do not, unknown
            # is said rather than a number that cannot be.
            if body == "H" and seated > SEATS["H"]:
                not_voting = seated = None

            need, rule = threshold(raw_q, bill, yeas, nays, seated)
            passed = yeas >= need if need else yeas > nays
            margin_note = RO.note(passed, yeas, nays, need, rule)

            out.append({
                "year": year, "body": body, "number": num,
                "date": when.strftime("%Y-%m-%d") if when else "",
                "time": when.strftime("%H:%M") if when else "",
                "bill": bill or None,
                "procedural": ((not bill_number(bill)
                                and (year, body, num) not in OTHER_MEASURE)
                               or key in PROCEDURAL),
                "question": std, "question_raw": raw_q, "question_plain": plain,
                "yeas": yeas, "nays": nays, "voting": voting, "not_voting": not_voting,
                "seats": SEATS[body], "seated": seated,
                "vacancies": None if seated is None else SEATS[body] - seated,
                "threshold_needed": need, "threshold_rule": rule,
                "passed": passed, "threshold_note": margin_note,
                "title": p[12].strip(),
            })
    return out


# WHAT THE DATABASE CALLS A VOTE, and the two codes nobody mapped.
#
# The General Court stores a ballot as a number and fetch_rollcalls_db.py
# translates it in SQL: 1 Yea, 2 Nay, 3 excused, 4 not excused, 6 presiding,
# 0 nothing. Codes 5 and 7 were never in that map, and a code the map does not
# cover passes through as its own digit -- so 411 ballots reached the site
# reading "5" and 156 reading "7", 567 in all, where a vote should be.
#
# Neither is a Yea or a Nay. The General Court's own roll call page for
# 2017 SB 133 shows Sen. Scott McGilvray with the Vote column simply EMPTY,
# and that ballot is code 7: the page says nothing was recorded, and so should
# this site. Code 5 is treated the same way on a roll call, because it is not a
# vote cast either way.
#
# They are named rather than blanked so a reader can tell "the record shows no
# vote" from a member who is simply absent from the list.
NO_VOTE = "No vote recorded"
VOTE_WORDS = {"Yea", "Nay", "Not Voting/Excused", "Not Voting/Not Excused",
              "Presiding", ""}

# CODE 5 IS A DECLARED CONFLICT OF INTEREST. It is in the House every year
# from 1999 to 2013 and in the Senate to 2019, and the journals say what it
# is: "Reps. Burling, Dalianis and Quandt declared conflicts of interest and
# did not participate" (House, 12 July 2000), "Senator Foster Rule #42 on SB
# 183-FN" (Senate, 2007), "Sen. Reagan asserts Rule 6-25 on HB 1116-FN"
# (Senate, 7 April 2016) -- Rules 42, 2-15 and 6-25 being the Senate's
# conflict rule under its successive numberings. Read against the journals on
# this disk, 371 of the 385 code 5 ballots of a year that has one sit beside
# the member's name and a conflict or that rule; the Senate's journals here
# begin in 2003. The member was in the chamber and stood aside from one
# question, which attendance must not count as an absence.
CONFLICT = "5"


def vote_word(raw):
    """One ballot as the site says it, with an unmapped code named honestly."""
    v = (raw or "").strip()
    return v if v in VOTE_WORDS else NO_VOTE


def ballot(raw):
    """A member vote row's own fields for one ballot: its word, and a flag
    where it is a declared conflict -- which the word cannot carry, "No vote
    recorded" being what an empty ballot is called too. Only on those rows."""
    out = {"vote": vote_word(raw)}
    if (raw or "").strip() == CONFLICT:
        out["conflict"] = True
    return out


def ballot_counts(current="RollCallHistory.txt", extra_dir="rollcalls"):
    """{(year, body, number): Counter of ballot codes}, from the member ballots.

    WHO DID NOT VOTE, FROM THE BALLOTS. The summary's fields 7 and 8 were
    read as the House's two kinds of non-voter, which is what they are in the
    current download (2026 roll call 3: 193|152|16|34, and the ballots say 15
    not excused plus the presiding officer, and 34 excused). In the
    database's files for 1999-2013 they are not: roll call 4 of 1999 reads
    276|41|335|81 and its 399 ballots say 46 excused, 35 not excused and one
    presiding -- 81 in field 8 alone. Adding the two put "733 seated" and 416
    non-voters on 2,483 House votes in /data/rollcalls.csv. Every roll call
    from 1999 has its ballots on this disk, each naming its own code, so the
    count comes from them, the same way in every year, and settles the old
    question of which field is "excused" by not needing either.

    A roll call's ballots come from the first file that holds it, the
    download first -- the rule parse_all keeps for the summaries. Summed
    across every file, a roll call in two would count each member twice, and
    since these counts are the headline tally, 2026 would have published
    doubled yeas and nays from the night 2026 was archived beside a download
    still holding it. By roll call rather than by year: see
    build_data.rows_all.
    """
    counts = defaultdict(Counter)
    files = [Path(current)] if Path(current).exists() else []
    d = Path(extra_dir)
    if d.is_dir():
        files += sorted(d.glob("RollCallHistory_*.txt"))
    source = {}
    for f in files:
        left_out = 0
        with open(f, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                p = line.rstrip("\n").split("|")
                if len(p) > 6 and p[2].strip().isdigit():
                    key = (p[0].strip(), p[1].strip(), int(p[2]))
                    if source.setdefault(key, f) != f:
                        left_out += 1
                        continue
                    counts[key][vote_word(p[6])] += 1
        if left_out:
            print(f"  {f.name}: {left_out:,} ballots left out as roll calls an earlier file holds")
    return counts


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
    ballots = ballot_counts(extra_dir=extra_dir)
    from_ballots = differ = 0
    for f in files:
        kept = 0
        for r in parse(f):
            key = (r["year"], r["body"], r["number"])
            if key in seen:
                continue
            seen.add(key)
            c = ballots.get(key)
            if c:
                n = sum(c.values())
                if (c.get("Yea", 0), c.get("Nay", 0)) != (r["yeas"], r["nays"]):
                    # THE BALLOTS ARE THE HEADLINE, and the summary's tally is
                    # kept beside them. The person decided this on 16 September:
                    # the ballots carry the actual record of who voted which
                    # way, and in every one of these cases the difference does
                    # not change the outcome.
                    #
                    # The General Court publishes two files and for 13 roll
                    # calls of 9,565 they disagree -- 2018 SB 503 states 11-11
                    # over a list of 12 yea and 10 nay. The page used to print
                    # the stated tally above a member list that did not add up
                    # to it, which asks a reader to believe both. Now it counts
                    # the members and says what the summary said, so the
                    # difference is visible and attributed rather than hidden.
                    r["yeas_stated"], r["nays_stated"] = r["yeas"], r["nays"]
                    r["yeas"], r["nays"] = c.get("Yea", 0), c.get("Nay", 0)
                    differ += 1
                r["excused"] = c.get("Not Voting/Excused", 0)
                r["not_excused"] = c.get("Not Voting/Not Excused", 0)
                r["presiding"] = c.get("Presiding", 0)
                r["no_vote_recorded"] = c.get(NO_VOTE, 0)
                r["not_voting"] = n - r["yeas"] - r["nays"]
                r["seated"] = n
                r["vacancies"] = r["seats"] - n
                from_ballots += 1
            out.append(r)
            kept += 1
        print(f"  {f}: {kept:,} roll calls")
    print(f"  who did not vote, from the ballots: {from_ballots:,} roll calls"
          + (f"; {differ:,} where the General Court's summary and its ballots "
             "disagree now take the headline from the ballots, and keep the "
             "stated tally beside it" if differ else ""))
    # WHAT EACH VOTE DECIDED, after the ballots have said who was in office.
    # The clerk's outcome where a docket line names it and could be right,
    # the Journal's where no docket line does, the rule where neither does.
    # See rollcall_outcomes.py.
    root = Path(".")
    src = RO.apply(out, root=root)
    conflicts = sum(1 for r in out if r.get("outcome_conflict"))
    print("  outcome: " + ", ".join(f"{v:,} from the {k}" for k, v in sorted(src.items()) if v)
          + (f"; {conflicts} where the record and the count disagree, kept as "
             "outcome_conflict" if conflicts else ""))
    # SILENCE IS NOT SUCCESS: a docket that stopped being read would leave
    # every outcome to the rule and still exit zero. A tree with no docket at
    # all -- a fresh checkout, the preflight fixture -- is told so and goes on.
    from_docket = src.get("docket", 0) + src.get("docket, implied", 0)
    if out and not from_docket:
        if RO.docket_paths(root):
            sys.exit("Docket files are on disk but no roll call's outcome was "
                     "read from one -- the pairing or the outcome reader has "
                     "stopped working. See rollcall_outcomes.py.")
        print("  WARNING: no Docket*.txt here, so every outcome comes from the "
              "rule rather than the clerk's record.")
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
    ap.add_argument("--bills", default="data/bills.json",
                    help="the session's bill list, used only to report roll "
                         "calls that name a bill it does not carry")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()

    rows, files = parse_all(a.file, a.dir)
    if not files:
        sys.exit(f"No roll call file to read: neither {a.file} nor anything in "
                 f"{a.dir}/.")
    if a.bill:
        rows = [r for r in rows if (r["bill"] or "").upper()
                == (bill_number(a.bill) or a.bill).upper()]
    if not rows:
        sys.exit("No roll calls matched.")

    if a.out:
        # Keyed on the term, not the bill: HB396 exists in every biennium, and
        # the moment a past year sits beside the current one a flat map merges
        # two different bills. Not on the year either -- a bill filed in 2025
        # is voted on in 2026 and both belong to the same record.
        by_term = defaultdict(lambda: defaultdict(list))
        for r in rows:
            # A vote whose bill column does not hold a bill number goes with
            # the other procedural votes rather than inventing a bill -- unless
            # OTHER_MEASURE has named the measure it was on.
            key = bill_number(r["bill"]) or (
                r["bill"] if other_measure(r) else "_procedural")
            # By its session year, or the next term's for a roll call of
            # Organization Day (proceedings.vote_term).
            by_term[P.vote_term(r["year"], r["date"])][key].append(r)
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
        # A recorded vote on a bill the session's files do not carry. The
        # General Court's own file has one: House vote 3 of 2025, "Reconsider",
        # 15-340, filed under HB476 and titled "relative to restrictions on
        # elective abortion" -- and the HB476s on record are a 2009 bill about
        # qualifications and a 2018 bill about registers of probate. Nothing
        # downstream can resolve it, so nothing downstream shows it; saying so
        # is better than an orphan key nobody ever looks up.
        # {term: set(bills)}. Checked WITHIN a term: bills.json holds the terms
        # it holds, and once an archived term's votes are read in, every one of
        # its bills would be "not in the list" if the check ignored the term.
        known = {}
        bp = Path(a.bills)
        if bp.exists():
            try:
                idx = json.loads(bp.read_text(encoding="utf-8"))
                if P.term_keyed(idx):
                    known = {t: set(byb) for t, byb in idx.items()}
            except ValueError:
                known = {}
        if known:
            stray = sorted({b for t, byb in by_term.items() if t in known
                            for b in byb
                            if b != "_procedural" and b not in known[t]})
            if stray:
                print()
                print(f"{len(stray)} roll call bill number(s) are not a bill "
                      f"in {a.bills}, so no page can show them:")
                for b in stray[:10]:
                    for byb in by_term.values():
                        for r in byb.get(b, [])[:1]:
                            print(f"    {b:9} {r['date']} {r['body']} "
                                  f"{r['question_raw']!r} {r['yeas']}-{r['nays']}"
                                  f"  {r['title'][:56]!r}")
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
