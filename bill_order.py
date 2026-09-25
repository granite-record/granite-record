#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-24.2
"""
The order bill numbers are listed in, wherever this site lists them.

    import bill_order as BO
    sorted(ids, key=BO.bill_key)
    sorted(rows, key=lambda r: BO.bill_key(r["id"]))

WHY ONE KEY

A bill number is text -- "HB1003", "HB 103" -- and sorted as text HB1003 comes
before HB103, and SB 16 after SB 133. bills.html has listed bills by number
since it was first written, through billKey in app.js, but the lists this build
writes sorted the text: a committee's Bills tab opened HB1003, HB101, HB1027, a
member's sponsored bills and a sitting day's consent calendar did the same, and
so did bills.csv. Someone scanning a long list for HB 101 finds it after
HB 1003, or decides it is not there.

THE ORDER IS app.js's, EXACTLY. House bills, House resolutions, House
concurrent resolutions, CACRs, then the Senate's bills and resolutions, then
the joint resolutions; anything else -- an LSR, a petition, an id with no
number -- after all of those; and within a kind, the number as a number. The
id's leading letters are the kind and the digits straight after them the
number, so a suffix such as "-FN" is ignored, as app.js ignores it.
preflight runs app.js's own billKey against this one, so the two cannot drift.

The id itself comes last, only so that two ids app.js would call equal
("HB 5" and "HB5") still come out the same way on every run. app.js's sort is
stable, so a list already in this order stays in it on the page.

build_indexes.py heads its directory's sections by kind in KIND_ORDER too,
and lists each by this key, so /directory reads in the order the bill search
and the downloads do. Standard library only; no network.
"""
import re

KIND_ORDER = ("HB", "HR", "HCR", "CACR", "SB", "SR", "SCR", "HJR", "SJR")
_RANK = {k: i for i, k in enumerate(KIND_ORDER)}
# app.js: /^([A-Z]+)\s*(\d+)/ on the upper-cased id. JavaScript's \d is ASCII
# only, and Python's is not, so the digits are spelled out.
_ID = re.compile(r"([A-Z]+)\s*([0-9]+)")


def bill_key(bid):
    """(kind's rank, number, id) -- app.js's billKey, plus a tie-break."""
    s = str(bid or "").upper()
    m = _ID.match(s)
    if not m:
        return (99, 0, s)
    return (_RANK.get(m.group(1), 99), int(m.group(2)), s)
