#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.1
"""
How the docket words a mention of ANOTHER bill, counted -- so that "amended
into" can be read from what the clerks wrote, not from a guess at it.

Related bills (build_related.py) are to list a bill whose text was amended
into another during a session; the plan says "'Amended into' is the easier
half and is in the docket already". The wording is not on the disk this was
written on, and CLAUDE.md's first rule is to read the artefact before
modelling it: "When tempted to write a parser from a description, open the
file". This opens it, for every row of every term, the way
segment_markers --phrases counts what chairs say.

Every docket row (narratives.json, each bill's `events`, `raw`) naming a bill
other than its own is reduced to its words with the other bill's number as
<BILL> and every other number as #, and those shapes are counted. The
commonest shapes, with an example or two of each, are the patterns to write
-- and the counts are how many rows each would read.

    python3 src/checks/bill_mentions.py                 the 60 commonest
    python3 src/checks/bill_mentions.py --top 200
    python3 src/checks/bill_mentions.py --grep "into"   only shapes with a word
    python3 src/checks/bill_mentions.py --json out.json every shape, for keeping

Reads narratives.json and nothing else; writes only what --json names. Asks
nobody anything.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
from collections import Counter, defaultdict

# A bill's number as the docket writes it: "HB 1234", "HB1234", "SB 5-FN",
# "CACR 12". build_site_v2.J_OTHER_BILL's kinds, with the resolutions.
BILL = re.compile(r"\b(HB|SB|HCR|SCR|HJR|SJR|CACR|HR|SR)\s*(\d{1,4})(?:-[A-Z-]+)?\b", re.I)
NUM = re.compile(r"\d+")
SPACE = re.compile(r"\s+")


def own(bid):
    m = re.match(r"([A-Z]+)(\d+)$", str(bid or "").upper())
    return (m.group(1), int(m.group(2))) if m else None


def shape(raw, bid):
    """The row's words with every OTHER bill as <BILL> and every other number
    as #, or None where it names no other bill."""
    me, other = own(bid), False

    def sub(m):
        nonlocal other
        if me and (m.group(1).upper(), int(m.group(2))) == me:
            return "<SELF>"
        other = True
        return "<BILL>"
    s = BILL.sub(sub, raw or "")
    if not other:
        return None
    s = NUM.sub("#", s)
    return SPACE.sub(" ", s).strip().upper()


def census(narr):
    """Counter of shapes, and up to three examples of each: (term, bill, raw)."""
    count, eg = Counter(), defaultdict(list)
    for term, bills in (narr or {}).items():
        if not isinstance(bills, dict):
            continue
        for bid, rec in bills.items():
            for e in (rec or {}).get("events") or []:
                sh = shape(e.get("raw"), bid)
                if sh is None:
                    continue
                count[sh] += 1
                if len(eg[sh]) < 3:
                    eg[sh].append((term, bid, e.get("raw") or ""))
    return count, eg


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--narratives", default="narratives.json")
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--grep", default="", help="only shapes containing this (any case)")
    ap.add_argument("--json", default="", help="write every shape and its examples here")
    a = ap.parse_args()
    p = Path(a.narratives)
    if not p.exists():
        print(f"bill_mentions: {p} is not here -- it is built by the narrative step "
              "(build_all) on the machine with the docket", file=sys.stderr)
        return 3
    count, eg = census(json.loads(p.read_text(encoding="utf-8")))
    rows = [(n, s) for s, n in count.most_common() if a.grep.upper() in s]
    total = sum(count.values())
    if not total:
        # SILENCE IS NOT SUCCESS: no row naming another bill is itself a finding.
        print("bill_mentions: no docket row names another bill -- narratives.json has "
              "no `events`, or none carries `raw`", file=sys.stderr)
        return 1
    print(f"{total:,} docket rows name another bill, in {len(count):,} shapes"
          + (f"; {len(rows):,} contain {a.grep!r}" if a.grep else ""))
    for n, s in rows[:a.top]:
        print(f"\n{n:>7,}  {s[:160]}")
        for term, bid, raw in eg[s][:2]:
            print(f"         {term} {bid}: {raw[:150]}")
    if a.json:
        Path(a.json).write_text(json.dumps(
            [{"n": n, "shape": s, "examples": eg[s]} for n, s in rows],
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nevery shape written to {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
