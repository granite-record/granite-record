#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.1
"""
The term arithmetic, in one place. A term is the General Court's two years,
written "2025-2026"; it begins in the odd year.

There are two rules, and they are two functions, not one with a flag:

  term_of_year(year)    BY YEAR. "2027" -> "2027-2028", 2026 -> "2025-2026".
                        For what is filed under a session year: a bill, a
                        docket row, a roll call's SessionYear. Raises on
                        something that is not a year, as int() does.
                        (proceedings.term_of(text) is the same rule for
                        callers that hand it a date or nothing at all: it
                        reads the first four characters and answers "" for
                        what is not a year.)

  proceedings.term_on(day)
                        BY DATE, WITH ORGANIZATION DAY. "2026-12-01" ->
                        "2025-2026", "2026-12-02" -> "2027-2028": the new
                        General Court organises on the first Wednesday of
                        December of the even year, and what it does that day
                        is the next term's (proceedings.py, ORGANIZATION DAY
                        BELONGS TO THE NEXT TERM). For what is dated and
                        filed under no session year: a floor debate, a
                        hearing, a recording, a status line.
                        proceedings.vote_term(year, when) is the same rule
                        for a roll call, which carries both; the calendar's
                        legislative_year.term_of(today) asks it of a date.

Why they stay two: a December day before Organization Day is in the old term
by one rule and the new by the other, and a bill filed under 2026 is in
2025-2026 whatever day it is read. Both rules are checked against each other
over 1985-2030 by preflight ("term helpers"), and preflight fails when a
definition of either appears outside this file and proceedings.py.

unh_extract.term_of(year, month, day) is neither: it knows a month without a
day, for a source that prints no day, and says so there.
"""


def term_of_year(year):
    """'2027' or 2027 -> '2027-2028'; 2026 -> '2025-2026'. A term begins in
    the odd year. ValueError for what is not a year."""
    y = int(year)
    start = y if y % 2 else y - 1
    return f"{start}-{start + 1}"
