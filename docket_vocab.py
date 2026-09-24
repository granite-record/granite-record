#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-11.3
"""
Which vocabulary a docket line is written in, and the glue it needs.

narrative.py calls this for a row of a DATABASE-era docket -- 1989 to 2016,
the years the General Court's own dump covers -- and for nothing else. A row
of the 2017-2026 web docket never reaches here, so those narratives cannot
move.

WHY IT EXISTS

narrative.py's PATTERNS were written against the web docket, which spells
things out and ends most lines with a four-digit date. The database's older
rows do neither, and the further back they go the less they do it. Measured
against the 14 files of 1989-2016, the modern patterns alone recognise:

    1989-1998   11.1% of 106,881 rows
    1999-2006   10.3% of  80,817
    2007-2016   48.1% of 102,863

which is why the archive had no history at all before 2017. The three era
tables take those to 81%, 87% and 90%, and what is left is mostly notices
that change nothing about where a bill stands -- seat pockets, due dates,
appointments -- which are deliberately kept as "other" and shown verbatim.

THE ORDER, WHICH IS THE WHOLE DESIGN

  1. the era's FIRST table, for lines a modern pattern matches BADLY
     ("Signed by the Governor on 5/5/1999 Eff: 7/1/1999 Chap.0022" matches
     the modern governor pattern and yields neither date nor chapter);
  2. narrative.PATTERNS, unchanged;
  3. the era's AFTER table, only on what those leave as "other";
  4. the era's routine notices, left as "other" on purpose.

Every table yields one of narrative.py's EXISTING event types with the named
groups describe(), stage_of() and build() already read, and then the era's
own normalise() fills what a regex cannot: a full date from "MAR10" or
"3/18/99" and the row's own timestamp, "ITL" into "Inexpedient to
Legislate", "Maj" into "Majority", DIV into DV, "Passed" into motion MA.

An era module is docket_era_1989.py, docket_era_1999.py, docket_era_2007.py.
"""

import re
from datetime import date as _date

import narrative

import docket_era_1989 as E1989
import docket_era_1999 as E1999
import docket_era_2007 as E2007

# The 1989 era's own table runs BEFORE the modern patterns: almost nothing in
# those ten years is written the modern way, and a modern pattern that fires
# on one of its lines is usually reading it wrong.
_E1989_FIRST = [(pid, typ, pat, fixed) for pid, typ, pat, fixed in E1989.TABLE]

ERAS = [
    (1989, 1998, E1989, _E1989_FIRST, [], E1989.ROUTINE),
    (1999, 2006, E1999, E1999.FIRST, E1999.AFTER, E1999.ROUTINE),
    (2007, 2016, E2007, E2007.FIRST, E2007.AFTER, E2007.ROUTINE),
]

# The last session the database dump covers, and the first the web docket
# does. A row outside this range is not ours.
FIRST_YEAR, LAST_YEAR = 1989, 2016


def era_for(session):
    """The (module, FIRST, AFTER, ROUTINE) for a session year, or None."""
    try:
        y = int(str(session)[:4])
    except (TypeError, ValueError):
        return None
    for lo, hi, mod, first, after, routine in ERAS:
        if lo <= y <= hi:
            return mod, first, after, routine
    return None


# describe() prints a date for these, and prints an empty one as "on ." --
# 699 signature lines of 1999-2006 whose date the clerk mistyped
# ("Signed by the Governor on 5/2/8/1999", "3//29/2000"). The row's own
# timestamp is the fallback the rest of this glue already uses, and it is
# also what event_date() orders the event by.
_PRINTS_A_DATE = ("introduced", "hearing", "exec", "worksession",
                  "conference_meeting", "rereferred", "floor", "governor",
                  "veto_override", "amendment", "enrolled", "consent_off",
                  "died", "vacated", "retained")
_DATE_OK = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


# THE CLERK'S OWN AS-OF DATE, where a floor row that states no date carries
# one. Such a row is dated by the moment it was entered, which is right 98% of
# the time and wrong exactly when the clerk says so: "Veto Sustained: RC
# 231-128 ..., [done during 1/4/2012 morning veto session]" was entered on
# 30 November 2011 and put four of January's veto votes on a November page;
# "ITL [1/4/2006] MA", entered on 5 January, put the 4 January consent
# calendar's bills on the 5th.
#
# NOT BUSINESS DONE IN RECESS. "[Recess of 6/5/13]", "(In recess of 5/15/14)"
# and "[Recessed from 5/17/12 Session]" name the sitting the chamber was in
# recess of -- the day the journal prints the business under -- not the day
# it was done, and so, in effect, do the Senate's bare "[05/06/04]" and
# "[06/09/05]" on accessions entered a week later: dated by them, the Senate
# acceded to a House request six days before the House made it. Measured
# over every database-era docket, the rule with those markers moved 91 rows
# and put 68 of them before an action of the bill they answer. How a day in
# recess is shown is the person's decision; this leaves those rows on the
# day they were entered, and narrative.hold_in_order() refuses any as-of
# date that would still move an action ahead of one it followed. As it
# stands it moves 14 rows, puts none ahead of anything, empties two pages
# that held nothing else, creates none, and the five with a roll call agree
# with its date.
#
# Not a bare date at the start of a row -- "11/3/99" led a row voted on
# 5 January 2000 -- and not a row about a special order, a deadline or a
# reporting date, whose date is the one being set rather than the one it
# happened on. Only within AS_OF_DAYS of the row's own stamp: "[06/09/04]" on
# a row of June 2005 is a slipped year, not an as-of date.
AS_OF = re.compile(
    r"\[\s*(?:done during\s+)?(?P<a>\d{1,2}/\d{1,2}/\d{2,4})"
    r"|\((?:as of|on)\s+(?P<b>\d{1,2}/\d{1,2}/\d{2,4})\)"
    r"|^\s*<(?P<c>\d{1,2}/\d{1,2}/\d{2,4})>", re.I)
AS_OF_NOT = re.compile(r"special order|deadline|reporting date|extended to|"
                       r"rept date", re.I)
AS_OF_DAYS = 90


def as_of(desc, created, session=None):
    """The date the clerk wrote a floor row as of, or None."""
    if not desc or created is None or AS_OF_NOT.search(desc):
        return None
    m = AS_OF.search(desc)
    if not m:
        return None
    mo, dy, yr = (int(x) for x in (m.group("a") or m.group("b")
                                   or m.group("c")).split("/"))
    if yr < 100:
        yr += 2000 if yr < 50 else 1900
    try:
        when = _date(yr, mo, dy)
    except ValueError:
        return None
    if abs((when - created.date()).days) > AS_OF_DAYS:
        return None
    try:
        year = int(str(session)[:4])
    except (TypeError, ValueError):
        year = None
    if year is not None and not (year - 1 <= when.year <= year + 1):
        return None
    return when


def _ensure_date(d, created, session=None, desc=None):
    """A date on every event that prints one, and inside its own session.

    Two things go wrong in the dump. The clerk mistypes ("Signed by the
    Governor on 5/2/8/1999"), which leaves no date at all and prints "on ."
    -- 699 of them. And a year can be wrong in the record itself: a 1990
    hearing typed "3/20/99", a row whose own timestamp is 1904. A date
    outside the bill's own session is not a fact about the bill, so the day
    and month are kept and the year is the session's.

    A floor row that states no date is dated by the moment it was entered --
    here, or already by the era's normalise() -- unless the clerk wrote the
    date it was done as of (as_of, above).
    """
    if d.get("_type") not in _PRINTS_A_DATE:
        return d
    if not _DATE_OK.match(str(d.get("date") or "")):
        if created is None:
            return d
        d["date"] = created.strftime("%m/%d/%Y")
    if d.get("_type") in ("floor", "veto_override") and created is not None \
            and d["date"] == created.strftime("%m/%d/%Y"):
        stated = as_of(desc if desc is not None else d.get("_raw"),
                       created, session)
        if stated:
            # kept, so narrative.hold_in_order can put it back
            d["_stamp_date"] = d["date"]
            d["date"] = stated.strftime("%m/%d/%Y")
    try:
        year = int(str(session)[:4])
    except (TypeError, ValueError):
        return d
    mo, dy, yr = (int(x) for x in d["date"].split("/"))
    if not (year - 1 <= yr <= year + 1):
        for y in (year, year - 1, year + 1):
            try:
                d["date"] = _date(y, mo, dy).strftime("%m/%d/%Y")
                break
            except ValueError:
                continue
    return d


# THE COMMITTEE'S NAME, NOT THE CLERK'S SHORTHAND. The older dockets write
# "Mun & Cnty Govt", "Crim Just & PSfty", "Elec Law" -- 176 spellings across
# 6,396 stage labels -- and referrals.expand() with names.committee() already
# knows how to read all but a handful of them. The 1989 table expanded its own
# matches from the start; the 1999 and 2007 tables did not, so a reader of a
# 2003 bill was told "House Mun & Cnty Govt committee".
def _committee_name(raw):
    if not raw or not raw.strip():
        return raw
    try:
        import names
        import referrals
        return referrals.AMP.sub(
            " and ", names.committee(referrals.expand(referrals.clean(raw))))
    except Exception:                                       # pragma: no cover
        return raw


def _expand_committees(d):
    for k in ("committee", "refer"):
        if d.get(k):
            d[k] = _committee_name(d[k])
    return d


def _event(pid, typ, m, fixed, clean, mod, created, session=None, desc=None):
    d = dict(m.groupdict())
    for k, v in (fixed or {}).items():
        if not d.get(k):
            d[k] = v
    d["_type"] = typ
    d["_raw"] = clean
    d["_era"] = pid
    fix = getattr(mod, "normalise", None) or getattr(mod, "fix", None)
    if fix is not None:
        # docket_era_1989 keeps the older signature fix(d, type, created).
        try:
            fix(d, typ, created)
        except TypeError:
            fix(d, created)
    if typ == "report":
        d.update(narrative.report_fields(d.pop("rest", "") or ""))
    return _expand_committees(_ensure_date(d, created, session, desc))


def classify(desc, created=None, session=None):
    """One docket line -> an event, in narrative.classify's own shape.

    Returns None when this line is not ours, so the caller keeps whatever
    narrative.classify made of it.
    """
    era = era_for(session)
    if era is None:
        return None
    mod, first, after, routine = era
    clean = narrative.clean(desc)
    for pid, typ, pat, fixed in first:
        m = pat.search(clean)
        if m:
            return _event(pid, typ, m, fixed, clean, mod, created, session,
                          desc)
    ev = narrative.classify(desc)
    if ev["_type"] != "other":
        # A modern pattern read it; it still needs this era's glue, because
        # its date may be "3/12/08" or missing altogether.
        fix = getattr(mod, "normalise", None)
        if fix is not None:
            try:
                fix(ev, created)
            except TypeError:
                fix(ev, ev["_type"], created)
        return _expand_committees(_ensure_date(ev, created, session, desc))
    for pid, typ, pat, fixed in after:
        m = pat.search(clean)
        if m:
            return _event(pid, typ, m, fixed, clean, mod, created, session,
                          desc)
    for name, pat in routine:
        if pat.search(clean):
            return {"_type": "other", "_raw": clean, "_era": "routine:" + name}
    return ev


def join_rows(rows, session=None):
    """Rows of one bill, with an action split across several joined up.

    narrative.py holds a row as a dict; an era's rule works on
    (created, bill, body, desc), which is all any of them compares. The
    joined row keeps the first piece's timestamp and citation, which is what
    the action was recorded under.
    """
    era = era_for(session)
    if era is None or not rows:
        return rows
    fn = getattr(era[0], "join_rows", None)
    if fn is None:
        return rows
    tup = [(r.get("created"), "", r.get("body", ""), r.get("desc", ""))
           for r in rows]
    out = fn(tup)
    if isinstance(out, tuple):
        out = out[0]
    if len(out) == len(rows):
        return rows
    # Map each joined line back onto the row it started from, in order.
    joined, i = [], 0
    for created, _b, _body, desc in out:
        while i < len(rows) and rows[i].get("created") != created:
            i += 1
        base = rows[i] if i < len(rows) else rows[-1]
        joined.append({**base, "desc": desc})
        i += 1
    return joined
