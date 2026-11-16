#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.3
"""
A term: its key, the arithmetic of its years, and which one a build is of --
in one place. A term is the General Court's two years, written "2025-2026";
it begins in the odd year.

THE KEY (16 November 2026, the refactor's build design, step S1). The text
that names a term in every file, address and record is its key. Its shape is
the state's setting, not this code's: src/lib/state_settings.json, "term",
"key" -- "{first}-{last}" for New Hampshire -- and "label", what a reader
sees ("{first}–{last}", with an en dash, as components.term_words writes it).
With today's settings every function here answers as the code always has, so
no key, address or file name moves. A key sorts in time order as text, and
preflight holds that it does: about a hundred sorts and comparisons rely on
it.

    key(2025)                "2025-2026": the term whose first year is 2025
    term_of_year(2026)       "2025-2026": BY YEAR (below); key_of_year is it
    key_on("2026-12-02")     "2027-2028": BY DATE, with Organization Day
    years("2025-2026")       (2025, 2026); ValueError for what is no key
    is_key("2027-0001")      False: an LSR number has the shape and is no term
    label("2025-2026")       "2025–2026"
    sitting()                the build's one term (THE SITTING TERM, below)

The callers that take a term apart by its characters, test its shape with a
pattern of their own or ask session_term for themselves have not moved here
yet; that is a later step, after the switch to 2027-2028.

THE TWO RULES, and they are two functions, not one with a flag:

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
                        key_on(day) here is that function, not a copy of it.

Why they stay two: a December day before Organization Day is in the old term
by one rule and the new by the other, and a bill filed under 2026 is in
2025-2026 whatever day it is read. Both rules are checked against each other
over 1985-2030 by preflight ("term helpers"), and preflight fails when a
definition of either appears outside this file and proceedings.py.

unh_extract.term_of(year, month, day) is neither: it knows a month without a
day, for a source that prints no day, and says so there.

THE SITTING TERM, ONCE A BUILD. The term the build is of was worked out three
ways: from the installed files (proceedings.session_term), as the newest term
of the bill index, and by date with Organization Day (app.js's sittingTerm).
They agree on an ordinary night and part around the turn. build_all.py now
decides it once, when it makes its plan, from the installed files --
decide(), the state's reading of them: for New Hampshire the newest session
year the six General Court files name, the files the turn guard reads, which
nothing later in a build can change, since the guard refuses a new term
without --allow-turn -- and hands it to every step as GRANITE_TERM. sitting()
is that answer; a step run alone works it out itself, once a process.
build_all.py records it in site/build.json beside what the day and the bill
index say (differences() puts a difference in words, and it never stops a
build). GRANITE_TERM is read here and nowhere else, as the build's stated day
is read only in build_date.py; a value that is no term stops whatever reads it.
"""

import functools
import os
import re
from pathlib import Path

import state_settings as ST

# The state's term, from its settings: how many years, the parity of the
# first, the key's shape and the label's.
LENGTH = int(ST.TERM["length_years"])
FIRST_PARITY = 1 if ST.TERM["first_year_parity"] == "odd" else 0
KEY = ST.TERM["key"]
LABEL = ST.TERM["label"]

# The variable build_all.py hands every step the build's term in.
ENV = "GRANITE_TERM"

# The key's shape as a pattern: each year a four-digit number where the
# setting says {first} or {last}, everything else as written.
_SHAPE = re.compile("".join(
    f"(?P<{p[1:-1]}>\\d{{4}})" if p in ("{first}", "{last}") else re.escape(p)
    for p in re.split(r"(\{first\}|\{last\})", KEY) if p))


@functools.cache
def key(first):
    """The key of the term whose first year is `first`, an int: key(2025)
    -> "2025-2026"."""
    return KEY.format(first=first, last=first + LENGTH - 1)


def first_year(year):
    """The first year of the term `year` falls in, by year: 2026 -> 2025,
    2027 -> 2027. ValueError for what is not a year, as int() gives."""
    y = int(year)
    return y - (y - FIRST_PARITY) % LENGTH


def term_of_year(year):
    """'2027' or 2027 -> '2027-2028'; 2026 -> '2025-2026'. A term begins in
    the odd year. ValueError for what is not a year."""
    return key(first_year(year))


# The name the build design gives the rule; term_of_year is what today's
# callers call it.
key_of_year = term_of_year


def _first_of(s):
    """The first year of a key, or None for anything that is not one: the
    shape, a first year of the state's parity, and the last year the length
    makes of it -- so "2027-0001", an LSR number, and "2026-2027" are not."""
    if not isinstance(s, str):
        return None
    m = _SHAPE.fullmatch(s)
    if not m:
        return None
    first = int(m.group("first"))
    return first if first_year(first) == first and key(first) == s else None


def is_key(s):
    """Whether `s` is a term's key: is_key("2025-2026") True, and
    "2027-0001", "2026-2027", "2027-requests", "" and 2025 False."""
    return _first_of(s) is not None


def years(k):
    """(first, last) of a key: years("2025-2026") -> (2025, 2026).
    ValueError for what is not one."""
    first = _first_of(k)
    if first is None:
        raise ValueError(f"{k!r} is not a term")
    return first, first + LENGTH - 1


def next_key(k):
    """The term after `k`: "2025-2026" -> "2027-2028"."""
    return key(years(k)[0] + LENGTH)


def previous_key(k):
    """The term before `k`: "2025-2026" -> "2023-2024"."""
    return key(years(k)[0] - LENGTH)


def label(s):
    """A term's years as a reader sees them, "2025–2026", in the setting's
    label; anything else as it came ("2027-requests"), "" for None --
    components.term_words, which preflight holds to this."""
    s = "" if s is None else str(s)
    m = _SHAPE.fullmatch(s)
    return LABEL.format(first=m.group("first"), last=m.group("last")) if m else s


def key_on(day):
    """The term a day falls in, Organization Day the next term's:
    "2026-12-01" -> "2025-2026", "2026-12-02" -> "2027-2028". It is
    proceedings.term_on, asked here so that a caller has one module for a
    term; "" for no day."""
    import proceedings
    return proceedings.term_on(day)


def decide(folder="."):
    """The term the state's installed files are of: for New Hampshire the
    newest session year the six General Court files in `folder` name, each
    in its own column (proceedings.session_term), as a key; "" where none is
    there or names a year. Read off the files every time it is asked."""
    import proceedings
    return proceedings.session_term(folder)


def stated():
    """The term the environment hands this process (GRANITE_TERM), or None
    where it hands none. A value that is no term stops it: a mistyped term
    taken for none would build every step from its own reading, which is
    what the variable is there to end."""
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    if not is_key(raw):
        raise SystemExit(
            f"{ENV}={raw!r} is not a term (one is written like {key(first_year(2025))}). "
            "Nothing was built: build_all.py hands every step the term it read off the "
            "installed files, and a step run alone works its own out.")
    return raw


@functools.cache
def _decided(folder):
    return decide(folder)


def sitting():
    """The build's one term: GRANITE_TERM where build_all.py handed it down,
    and otherwise the installed files' term (decide), worked out once a
    process for the folder it runs in; "" where no session file names a
    year."""
    return stated() or _decided(str(Path(".").resolve()))


def differences(sitting_term, by_date="", index_newest=""):
    """The build's two other readings of the term against the one it was
    handed, in words: [] where they say the same term or say none. Around the
    turn they part for a while, and that is said as the turn: from
    Organization Day until the New term run installs the new term's files,
    the day's term is the next one; and from that run until the new term's
    first bills are in the bill index, the index's newest is the one before.
    Anything else is said as a disagreement. None of it stops a build."""
    out = []
    if not is_key(sitting_term):
        return out
    nxt, prev = next_key(sitting_term), previous_key(sitting_term)
    if by_date and by_date != sitting_term:
        if by_date == nxt:
            out.append(f"the day is in {by_date} and the installed files still say "
                       f"{sitting_term}: the turn, from Organization Day until the New term "
                       "run installs the new term's files")
        elif by_date == prev:
            out.append(f"the installed files already say {sitting_term} and the day is still "
                       f"in {by_date}: the turn, the new term's files taken before "
                       "Organization Day")
        else:
            out.append(f"the day is in {by_date} and the installed files say {sitting_term}, "
                       "which is not the turn")
    if index_newest and index_newest != sitting_term:
        if index_newest == prev:
            out.append(f"the bill index's newest term is {index_newest} and the installed "
                       f"files say {sitting_term}: the turn, until the new term's first "
                       "bills are in the index")
        else:
            out.append(f"the bill index's newest term is {index_newest} and the installed "
                       f"files say {sitting_term}, which is not the turn")
    return out
