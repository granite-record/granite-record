#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
The election law's days, by the text of the section in force on the day: the
state primary (RSA 653:8), the state general election (RSA 653:7) and the
filing period for the primary (RSA 655:14), each worked out from the words of
the statute as db/NH_RSA.psv prints them, or from LAW_COPY where that table is
not in the folder a run is in.

    import election_law as EL
    EL.state_primary(2028)        # date(2028, 6, 13): RSA 653:8 as 2026, 44:1 amends it
    EL.state_general(2028)        # date(2028, 11, 7): RSA 653:7
    EL.filing_period(2028)        # (date(2028, 3, 3), date(2028, 3, 10)): RSA 655:14
    EL.in_force("653:8", 2026)    # (first day, last day, Law) of the text in force

SHARED, NOT A PAGE'S (19 November 2026). This was src/pages/key_dates.py's,
which reads it still under the same names, and moved here as it stood so that
a reader of src/parse/ can date a State Primary by the law in force
(parse_sos_primary_results.Primary) without importing a page module, which
key_dates is (it imports i18n). Nothing here imports anything of this
project's. Standard library only; reads db/NH_RSA.psv where it is in the
folder a run is in, and asks no network.
"""

import html
import re
from collections import namedtuple
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# THE ELECTION LAW'S DAYS, BY THE TEXT IN FORCE ON THE DAY (19 November 2026)
#
# 2026, 44 (HB 481, signed 8 May 2026) moves the state primary from September
# to June and its filing period from June to March, from 1 January 2028.
# db/NH_RSA.psv prints both texts of RSA 653:8 and 655:14, each headed
# "[RSA 653:8 effective until January 1, 2028; ...]" or "[RSA 653:8
# effective January 1, 2028; ...]", and the act in the section's source note
# ("2026, 44:1, eff. Jan. 1, 2028."). A day is worked out from the words of
# the text in force on it (in_force): each text's own day for the year, and
# the text whose time in force holds that day. No day is typed here.
#
# Read off the table in the build's own folder (TABLE_HERE) where it holds
# the section, and off LAW_COPY where it does not -- the fixture's table and
# a bare clone's; preflight's _election_law_in_force holds the copy to the
# table. A text whose words no rule here reads (rule_days) dates nothing,
# and unread() says which.
# ---------------------------------------------------------------------------
# One text of a section: in force from `since` until `until` (ISO days, ""
# for always), made by `act` ("2026, 44:1"; "" for the text as first
# enacted, which is cited by its section alone), its operative words.
Law = namedtuple("Law", "sec since until act words")

# The sections' texts as db/NH_RSA.psv of 26 October 2026 prints them.
LAW_COPY = {
    "653:7": (Law("653:7", "", "", "",
                  "The state general election shall be held on the first Tuesday following the first "
                  "Monday in November of every even-numbered year."),),
    "653:8": (Law("653:8", "", "2028-01-01", "",
                  "The state primary election shall be held on the second Tuesday in September of "
                  "every even-numbered year."),
              Law("653:8", "2028-01-01", "", "2026, 44:1",
                  "The state primary election shall be held on the second Tuesday in June of every "
                  "even-numbered year.")),
    "655:14": (Law("655:14", "", "2028-01-01", "",
                   "he or she shall file with the appropriate official between the first Wednesday in "
                   "June and the Friday of the following week a declaration of candidacy as provided "
                   "in RSA 655:17."),
               Law("655:14", "2028-01-01", "", "2026, 44:4",
                   "he or she shall file with the appropriate official between the first Friday in "
                   "March and the Friday of the following week a declaration of candidacy as "
                   "provided in RSA 655:17.")),
}

_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_WEEKDAY = {w: i for i, w in enumerate(
    ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}
_MONTH = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"))}
_W = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_M = r"(january|february|march|april|may|june|july|august|september|october|november|december)"
# The three ways the election law states a day, as the table prints them.
RULE_GENERAL = re.compile(r"\bthe first tuesday following the first monday in " + _M
                          + r" of every (even|odd)-numbered year", re.I)
RULE_PERIOD = re.compile(r"\bbetween the (first|second|third|fourth) " + _W + r" in " + _M
                         + r" and the " + _W + r" of the following week", re.I)
RULE_DAY = re.compile(r"\bthe (first|second|third|fourth) " + _W + r" (?:in|of) " + _M
                      + r" of every (even|odd)-numbered year", re.I)


def nth_weekday(year, month, nth, weekday):
    """The `nth` `weekday` (0 Monday) of a month."""
    first = date(int(year), int(month), 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))


def rule_days(words, year):
    """(first day, last day) the law's `words` give in `year` -- the same day
    twice for one day -- or None: the year is not one its words name, or no
    rule here reads them. A filing period's year is its election's."""
    year = int(year)
    m = RULE_GENERAL.search(words)
    if m:
        if year % 2 != (m.group(2).lower() == "odd"):
            return None
        d = nth_weekday(year, _MONTH[m.group(1).lower()], 1, 0) + timedelta(days=1)
        return d, d
    m = RULE_PERIOD.search(words)
    if m:
        a = nth_weekday(year, _MONTH[m.group(3).lower()], _ORD[m.group(1).lower()],
                        _WEEKDAY[m.group(2).lower()])
        # "the Friday of the following week": the week, Monday to Sunday, after a's.
        b = a - timedelta(days=a.weekday()) + timedelta(days=7 + _WEEKDAY[m.group(4).lower()])
        return a, b
    m = RULE_DAY.search(words)
    if m:
        if year % 2 != (m.group(4).lower() == "odd"):
            return None
        d = nth_weekday(year, _MONTH[m.group(3).lower()], _ORD[m.group(1).lower()],
                        _WEEKDAY[m.group(2).lower()])
        return d, d
    return None


def rule_words(words):
    """The day's rule in a few words, as the law says it ("the second Tuesday
    in June"), or ""."""
    m = RULE_DAY.search(words) or RULE_GENERAL.search(words) or RULE_PERIOD.search(words)
    if not m:
        return ""
    s = m.group(0)
    return s[len("between "):] if s.lower().startswith("between ") else re.sub(
        r" of every (even|odd)-numbered year$", "", s, flags=re.I)


# Words a text of the law gave that no rule here reads: (section, words), for
# the build to say (unread).
UNREAD = set()


def in_force(sec, year):
    """(first day, last day, Law) of section `sec` in `year`, by the text in
    force on the day it gives, or None: the year is none of its days, or no
    one text's day is in its own time in force (a text no rule here reads
    is said by unread())."""
    hit = []
    for law in laws(sec):
        got = rule_days(law.words, year)
        if got is None:
            if not (RULE_GENERAL.search(law.words) or RULE_PERIOD.search(law.words)
                    or RULE_DAY.search(law.words)):
                UNREAD.add((sec, law.words[:160]))
            continue
        first = got[0].isoformat()
        if (not law.since or first >= law.since) and (not law.until or first < law.until):
            hit.append((got[0], got[1], law))
    return hit[0] if len(hit) == 1 else None


def state_primary(year):
    """The state primary of `year` by RSA 653:8 as in force on its day, or
    None: an odd year has none."""
    got = in_force("653:8", year)
    return got[0] if got else None


def state_general(year):
    """The state general election of `year` by RSA 653:7, or None."""
    got = in_force("653:7", year)
    return got[0] if got else None


def filing_period(year):
    """(first day, last day) of the filing period for `year`'s state primary
    by RSA 655:14 as in force on its first day, or None: a year with no
    primary has none."""
    if state_primary(year) is None:
        return None
    got = in_force("655:14", year)
    return (got[0], got[1]) if got else None


def unread(out=print):
    """Say each text of the election law no rule here reads."""
    for sec, words in sorted(UNREAD):
        out(f"  key dates: RSA {sec} as db/NH_RSA.psv prints it gives no day this file can read "
            f"({words!r}); no day is dated by it until key_dates.rule_days reads it")
    return len(UNREAD)


_SECTIONS = {}
_LAWS = {}

# THE TABLE THE LAWS PAGES ARE BUILT FROM: db/NH_RSA.psv in
# the folder the build runs in. That is rsa.TABLE in a real build, which runs
# from the repository, and the fixture's own two-chapter table where preflight
# builds a site (build_rsa.py --db db). Read from rsa.TABLE whatever the
# folder, the fixture's calendar linked RSA 39:1, 40:13, 653:8 and 669:1 on a
# machine that holds the real table, to Laws pages its build never wrote, and
# the dry run of 24 October 2026 stopped at the link check; here, with no
# table, nothing was linked and the check passed.
TABLE_HERE = Path("db") / "NH_RSA.psv"


def _sections_on_disk():
    """{"39:1", "39:1-A", ...}: the sections of the statute table the Laws
    pages are built from (TABLE_HERE), empty where it is not here. Read once
    a run for each folder, by each row's heading alone, which is a second's
    reading where loading the whole table is not. The same reading keeps the
    source note and the text of each section LAW_COPY names (_LAWS), for
    laws()."""
    table = TABLE_HERE.resolve()
    if table not in _SECTIONS:
        got, rows = set(), {}
        try:
            if table.is_file():
                with open(table, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        f = line.split("|", 7)
                        m = re.match(r"Section (\S+?) ", f[6]) if len(f) > 6 else None
                        if m:
                            got.add(m.group(1).upper())
                            if m.group(1) in LAW_COPY and m.group(1) not in rows:
                                # SourceNote, and EntireRSA: the "rsa" column
                                # before it is cut short, and holds only the
                                # first of two texts.
                                f = line.split("|", 10)
                                if len(f) > 9:
                                    rows[m.group(1)] = (f[7], f[9])
        except Exception:                                    # noqa: BLE001
            got, rows = set(), {}
        _SECTIONS[table], _LAWS[table] = got, rows
    return _SECTIONS[table]


def _plain(s):
    """Text with its tags taken out and its spaces made one."""
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


_MON = {m[:3]: i + 1 for i, m in enumerate(_MONTH)}


def _iso(words):
    """"January 1, 2028" or "Jan. 1, 2028" -> "2028-01-01", or ""."""
    m = re.fullmatch(r"([A-Za-z]{3})[a-z]*\.? (\d{1,2}), (\d{4})", words.strip())
    if not m or m.group(1).lower() not in _MON:
        return ""
    return date(int(m.group(3)), _MON[m.group(1).lower()], int(m.group(2))).isoformat()


# "[RSA 653:8 effective until January 1, 2028; see also RSA 653:8 set out
# below.]", "[RSA 653:8 effective January 1, 2028; see also RSA 653:8 above.]"
TEXT_HEAD = re.compile(r"\[RSA (\S+) effective (until )?([A-Z][a-z]+\.? \d{1,2}, \d{4})[^\]]*\]")
# "2026, 44:1, eff. Jan. 1, 2028." in a source note: the act, and its day.
SOURCE_ACT = re.compile(r"(\d{4}, \d+:[\w-]+(?:[,;] ?\d+:[\w-]+)*), eff\. ([A-Z][a-z]+\.? \d{1,2}, \d{4})")


def law_texts(sec, source, body):
    """[Law] of one section from its row of the table: one for each text the
    row prints, each headed with when it is in force (TEXT_HEAD), or the one
    text where none is headed; a text in force from a day is made by the act
    the source note gives that day."""
    text, note = _plain(body), _plain(source)
    acts = {_iso(d): a for a, d in SOURCE_ACT.findall(note)}
    heads = list(TEXT_HEAD.finditer(text))
    if not heads:
        return [Law(sec, "", "", "", text)]
    out = []
    for i, h in enumerate(heads):
        words = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)].strip()
        day = _iso(h.group(3))
        out.append(Law(sec, "" if h.group(2) else day, day if h.group(2) else "",
                       "" if h.group(2) else acts.get(day, ""), words))
    return out


def laws(sec):
    """[Law] of section `sec`: the table's (TABLE_HERE) where it holds the
    section, LAW_COPY's where it does not."""
    _sections_on_disk()
    row = _LAWS.get(TABLE_HERE.resolve(), {}).get(sec)
    return law_texts(sec, *row) if row else list(LAW_COPY.get(sec, ()))
