#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
The rail's endings: the two bills the session's end killed with no vote on
either -- one left on the table (table_death, died_on_table) and one held for
interim study (study_ending, with the study committee's report,
interim_report) -- and the days each chamber sat, which date them
(chamber_sittings, journal_sittings, last_sat).

    import endings as END
    END.chamber_sittings(narratives)       # {(body, year): [each day it sat]}
    END.table_death(narr, tab, term, sittings)   # (the day a tabled bill died, its row or None)
    END.interim_report(narr, term)         # {"date", "rec", "vote", "year", ...} or None
    END.session_endings(narr, steps, rail, chip, status, term, over, sittings)
                                           # (tabled, ending), the lines added to steps
    END.session_end_line(step)             # whether a line is one of them

SECTIONS OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: session endings and table deaths). They
moved here as they stood, comments and all, in the file's order: from the
heading THE RAIL'S ENDINGS to session_endings, the import of committee_acts'
interim study patterns that stood among them included; then
SESSION_END_DEATHS and session_end_line. The rail's index row (RAIL_CODE,
without_rail, index_rail), which stood between the two, stayed with
build_bills and main. It imports no builder (_import_cycles_cut).
build_site_v2 imports every name here back under its own, so
build_site_v2.table_death and the rest answer as they did, for build_bills,
main, the bill's reports, journey_disagrees and the checks.
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

import narrative as N
# The words the pages say, src/pages/words/: here, the study reports'.
from components import WORDBOOK as _WORDBOOK
# Two of the chip's six words (parts.py).
from parts import DIED, INTERIM_STUDY
# A day written out in full (status.py) and the journey's rows and days (journey.py).
from status import _long_date
from journey import J_ACTS, _j_iso


# ===================================================== THE RAIL'S ENDINGS ==
#
# TWO BILLS THE SESSION'S END KILLED, WITH NO VOTE ON EITHER (the person, 8
# and 9 October 2026). Neither was drawn as dead on a day:
#
#   * A BILL LEFT ON THE TABLE: "Show the body it was tabled in with the
#     yellow pause, and show the red x mark on the law once it died when the
#     session ended". The chamber's stop was the cross on the day it was
#     tabled -- HB 1043 of 2026 read "Senate ✕ 7 May, Law ✕ 7 May" -- and the
#     history said nothing of a death that came three months later. Now the
#     stop is the pause, dated by the tabling; Law is the cross, on the day
#     it died (table_death); and How it got here has the death's line after
#     the tabling's (died_on_table). 2,170 bills in nineteen terms.
#   * A BILL HELD FOR INTERIM STUDY: "same goes for interim study bills that
#     weren't recommended for future legislation by showing the orange icon
#     in the body it was studied in", and a recommended one the same (option
#     (d), the person's answer of 9 October): the chamber keeps its "~", Law
#     takes the cross on the day the chamber that studied it last sat, and
#     How it got here a line of that and one of the committee's report -- an
#     orange arrow where it recommended the subject for future legislation,
#     the "~" where it did not, naming the next term's bill where the docket
#     does (study_ending). 2,392 bills.
#
# WHILE THE SESSION SITS NEITHER IS DEAD, and nothing changes: a bill on the
# table is the pause with Law not reached (its chip Tabled, and none of this
# applies), and one in interim study the "~" with Law not reached.
#
# THE SENATE OF 2026 (the person, 9 October 2026): its session counts as
# ended on 19 August 2026, its last sitting, though its journal says it
# recessed to the call of the chair. Its 52 tabled bills and 107 studied
# bills take that day, "when the Senate last sat"; a row of its own, when the
# clerk enters one, replaces the date by the first rule of table_death.

# The rows that show a chamber sitting: its floor's (narrative.FLOOR_TYPES,
# which has the veto votes) and its vote on a conference report.
SITTING_TYPES = frozenset(N.FLOOR_TYPES) | {"conf_report"}
# A row of a special session on a bill whose number does not say so: SB 1 of
# 2006, "Introduced, MA VV; 2006 Special Session", "Rep Vaillancourt moved
# lay on table; MF VV; 2006 Spec Sess", "Sen. Clegg Moved to Adopt Rules for
# Special Session; MA, VV; SJ, Special Session" -- the special session of 26
# September 2006 on the ballot (SJ SS, "PETITION FOR THE CALLING OF A
# SPECIAL SESSION"). Every row of the bill that day is the special session's.
SPECIAL_SESSION_ROW = re.compile(r"\bspec(?:ial)?\.?\s*ses+(?:ion)?\b", re.I)
# A row that records no sitting: Joint Rule 24(b)'s postponement of what was
# left unacted on, "INDEFINITELY POSTPONED PER JT. RULE 24 (B)", "...BY
# JOINT RULE 24(B)", 18 rows entered on Sunday 1 July 1990 with no motion,
# no vote and no journal. Read as the House's and the Senate's last sitting
# of 1990, they dated the 82 interim study bills of 1989-1990 to a Sunday
# (the review of the rail's endings, 9 October 2026).
NO_SITTING_ROW = re.compile(r"^\s*indefinitely\s+postponed\s+(?:per|by)\s+(?:jt\.?|joint)\s+"
                            r"rule\s*[\w()\s]*$", re.I)


def chamber_sittings(narratives):
    """{(body, year): [each day the chamber sat that year, in order]}, from
    the floor's rows of every bill of every term; and a special session's
    days apart, under (body + "*", year).

    THE LAST OF A YEAR IS ITS ADJOURNMENT, which is what a bill left on the
    table or in interim study died at: the House's of 2026 is 19 August (HJ
    16, "The House adjourned at 3:28 p.m."), the Senate's the same day (SJ
    15), 2020's 16 September for both. The docket does not hold every
    sitting -- the Senate's of 17 June 2004 and 28 June 2006 have no floor
    row -- and with_journals adds the days the journals open.

    NOT A SPECIAL SESSION'S: SSHB 1 of 2013 sat on 7 and 21 November 2013,
    after both chambers had ended their year, and the special session of 18
    November 2015 the same; a bill of the regular session did not die on
    either. Nor 26 September 2006's, whose bill is SB 1 and whose rows say
    "2006 Special Session" (SPECIAL_SESSION_ROW): read as the regular
    session's last sitting, it dated 154 bills of 2006 to it. NOR A DECEMBER
    OF THE SECOND YEAR, which is the next General Court's organization day
    (7 December 2022), not this one's. NOR A ROW THAT RECORDS NO SITTING
    (NO_SITTING_ROW, Sunday 1 July 1990).
    """
    days = defaultdict(set)
    for term_bills in (narratives or {}).values():
        for bid, narr in (term_bills or {}).items():
            evs = (narr or {}).get("events", []) or []
            ss = str(bid).upper().startswith("SS")
            sdays = {e.get("date") for e in evs if not e.get("cancelled")
                     and SPECIAL_SESSION_ROW.search(e.get("raw") or "")}
            for e in evs:
                d, body = e.get("date") or "", (e.get("body") or "")[:1].upper()
                if (e.get("type") not in SITTING_TYPES or e.get("cancelled")
                        or body not in ("H", "S") or not re.match(r"\d{4}-\d\d-\d\d$", d)
                        or (d[5:7] == "12" and int(d[:4]) % 2 == 0)
                        or NO_SITTING_ROW.search(e.get("raw") or "")):
                    continue
                days[(body + ("*" if ss or d in sdays else ""), d[:4])].add(d)
    return {k: sorted(v) for k, v in days.items()}


# A journal of a special session, by its name: "SJ SS.txt" (26 September
# 2006), "SJ SS November 07, 2013.txt", "HJ_SS 1 November 18 2015.txt".
SPECIAL_JOURNAL = re.compile(r"(?:^|[\s_])SS(?:[\s_.,]|$)|special", re.I)


def journal_sittings(roots=None):
    """{(body, year): {each day the chamber's journals on disk open a
    sitting}} -- the House's from 1997, the Senate's from 2003, by their day
    headings alone (journal_days.day_blocks, senate_sittings) -- leaving out
    a journal of a special session by its name. Empty where none is on disk."""
    try:
        import journal_days as J
    except Exception:
        return {}
    out = defaultdict(set)
    for body, root in (roots or (("H", J.HOUSE), ("S", J.SENATE))):
        if not Path(root).is_dir():
            continue
        for yd in sorted(Path(root).glob("[12][0-9][0-9][0-9]")):
            for f in sorted(yd.glob("*.txt")):
                if "erbatim" in f.name or SPECIAL_JOURNAL.search(f.stem):
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                for d, _b in (J.day_blocks(text) if body == "H" else J.senate_sittings(text)):
                    if d and re.match(r"\d{4}-\d\d-\d\d$", d):
                        out[(body, d[:4])].add(d)
    return dict(out)


def with_journals(sittings, journal):
    """chamber_sittings with the days the chambers' journals open a sitting
    on (journal_sittings), where the docket has no floor row: the Senate's
    of 17 June 2004 ("At the time of adjournment on June 17, 2004, the
    following House Bills remained on the table in the Senate", SJ 17) and
    of 28 June 2006 (SJ 17), which the 45 bills of 2004 and the 66 of 2006
    the Senate left on its table or in interim study died at, not the 25
    May 2004 and 24 May 2006 of its last floor rows.

    Not a December of the second year (the organization day, 1 December
    2010), nor a day either chamber sat in a special session by the docket
    (7 November 2013, whose Senate journal is "SJ SS November 07, 2013")."""
    out = {k: list(v) for k, v in (sittings or {}).items()}
    for (body, y), days in (journal or {}).items():
        special = set(out.get(("H*", y)) or []) | set(out.get(("S*", y)) or [])
        add = {d for d in days if d[:4] == y and d not in special
               and not (d[5:7] == "12" and int(y) % 2 == 0)}
        if add:
            out[(body, y)] = sorted(set(out.get((body, y)) or []) | add)
    return out


def term_years(term):
    """(1999, 2000) for "1999-2000"; (0, 0) for anything else."""
    m = re.match(r"(\d{4})-(\d{4})$", term or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# A row that says the bill died on the table: "Died on Table, Session ended
# 08/19/2026" (the House since 2021), "Died on Table" and "Died On The Table;
# SJ 11A" (both chambers, 2001-2020), "Died on Table (Sine Die)", "Died on
# Table at End of Session", "Died on Table [11/30/2011]", "Died, Session
# Ended" (SSHB 2 of 2010), "Died (All bills Laid on Table, by Sine Die
# Adjournment)", and the Senate's Rule 3-23 that ends a bill still on its
# table: "Inexpedient to Legislate, Senate Rule 3-23, Adjournment
# 10/10/2024", "..., Senate Rule 3-23, 10/31/2025", "Inexpedient to
# Legislate, 2013 Adjournment, Senate Rule 3-23".
TABLE_DEATH_ROW = re.compile(
    r"^\s*died\b|inexpedient\s+to\s+legislate,?\s*(?:\d{4}\s+adjournment,?\s*)?"
    r"senate\s+rule\s+3-23\b", re.I)
ROW_DAY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")


def died_on_table(steps, chip, status):
    """The line that laid a Died bill on the table it died on, or None: the
    chamber's last tabling, where the bill's status says it died on the table
    or a tabling is the last thing either chamber did, and nothing but the
    death followed it in that chamber."""
    if chip != DIED:
        return None
    hs = [s for s in steps if s.get("body") in ("H", "S")]
    if not (status in ("Died on the table", "Laid on the table")
            or (hs and hs[-1].get("act") == "tabled")):
        return None
    at = next((i for i in range(len(hs) - 1, -1, -1) if hs[i].get("act") == "tabled"), None)
    if at is None:
        return None
    tab = hs[at]
    if any(s.get("body") == tab["body"] and s.get("act") != "died" for s in hs[at + 1:]):
        return None
    return tab


def _sat_by_journal(body, day):
    """Whether the chamber's journal on disk opens a sitting on `day`
    (session_days, which reads only the journals' day headings); False where
    no journal says so, or none is on disk."""
    try:
        import session_days
        return bool(session_days._sat(body, day))
    except Exception:
        return False


# A row that lays a bill on the table (J_ACTS' "tabled"), for table_session_ends.
TABLING_ROW = next(rx for act, rx in J_ACTS if act == "tabled")


def table_session_ends(narratives):
    """{(body, term, year): day} -- the day a chamber's own death rows state
    that the bills it left on its table in `year` of `term` died, where
    every such row states the same day (table_death's first rule); a special
    session's bills under body + "*".

    FOR A BILL WHOSE OWN ROW IS MISSING: HB 266 of 2021, laid on the House's
    table on 9 April 2021 beside HB 111, HB 155 and HB 165, has no row of
    its death, and theirs say "Died on Table, Session ended 01/05/2022" --
    the House adjourned from its 2021 session on 5 January 2022 (HJ 1 of
    2022, "ADJOURN FROM 2021 SESSION"). Its last floor row of 2021 is of 24
    June, which last_sat gave it."""
    seen = defaultdict(set)
    for term, byb in (narratives or {}).items():
        first, last = term_years(term)
        for bid, narr in (byb or {}).items():
            ss = "*" if str(bid).upper().startswith("SS") else ""
            evs = [e for e in (narr or {}).get("events", []) or [] if not e.get("cancelled")]
            for i, e in enumerate(evs):
                raw = e.get("raw") or ""
                if not TABLE_DEATH_ROW.search(raw):
                    continue
                body, entered = (e.get("body") or "")[:1].upper(), e.get("date") or ""
                m = ROW_DAY.search(raw)
                day = _j_iso(m.group(1), m.group(2), m.group(3)) if m else ""
                laid = next((x.get("date") or "" for x in reversed(evs[:i])
                             if (x.get("body") or "")[:1].upper() == body
                             and not TABLE_DEATH_ROW.search(x.get("raw") or "")
                             and TABLING_ROW.search(x.get("raw") or "")), "")
                if (body in ("H", "S") and day and laid and first <= int(day[:4]) <= last
                        and laid <= day <= (entered or day)):
                    seen[(body + ss, term, laid[:4])].add(day)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def table_death(narr, tab, term, sittings, sat=_sat_by_journal, ends=None):
    """(the day a bill left on the table died, the row that says it died or
    None). `tab` is the line that laid it there (died_on_table).

    A BILL LEFT ON THE TABLE DIED WHEN ITS CHAMBER'S SESSION ENDED, never on
    the day it was tabled: counted over all 2,170 such bills on 8 October
    2026, none was taken off a table after its chamber adjourned -- the
    motions to take SB 436 of 2022 and HB 1711 of 2024 off it on their Veto
    Days both failed, 10-13 -- and the Senate's journals list the bills
    still on its table at adjournment (29 September 2016, "remained on the
    table"). The day, in this order:

      1. The day the bill's own death row states, where it is a day of the
         term no later than the row was entered: "Died on Table, Session
         ended 08/19/2026" (HB 609 of 2026); "Inexpedient to Legislate,
         Senate Rule 3-23, Adjournment 10/10/2024"; "..., Senate Rule 3-23,
         10/31/2025", the day the 2025 rule fixed (SB 14 of 2025); "Died on
         Table [11/30/2011]".
      2. Where the row states none -- "Died on Table", "(Sine Die)", "at End
         of Session", "2013 Adjournment, Senate Rule 3-23" -- or one it
         cannot be (HB 201 of 2020's "Adjournment 09/16/2021", entered on 9
         September 2021): the day the chamber adjourned, the last day it
         sat in a year of the term between the tabling and the row
         (adjourned_by). 227 House rows entered on 23 September 2020 are of
         a session that ended on the 16th.
      3. No row, the session over: the day the chamber's rows state for the
         other bills it left on its table that year, where they agree
         (`ends`, table_session_ends: HB 266 of 2021, 5 January 2022); else
         the last day the chamber sat in the year the bill lay there
         (last_sat), which the line says in as many words. The Senate's 52
         bills of 2026, HB 1043 among them, take 19 August 2026; the House's
         112 of 2022 its days.

    The row is the death's own in the chamber whose table it was, where it
    has one: SB 698 of 2020, which the House laid on its table, carries the
    Senate's Rule 3-23 row and the House's "Died on Table"."""
    body, laid = tab["body"], tab.get("date") or ""
    special = str((narr or {}).get("bill") or "").upper().startswith("SS")
    evs = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
    rows = [e for e in evs if TABLE_DEATH_ROW.search(e.get("raw") or "")
            and (e.get("date") or "") >= laid]
    row = next((e for e in rows if (e.get("body") or "")[:1].upper() == body),
               rows[0] if rows else None)
    if row is None:
        peer = (ends or {}).get((body + ("*" if special else ""), term, laid[:4]))
        if peer and peer >= laid:
            return peer, None
        return last_sat(body, laid, term, sittings, special), None
    entered = row.get("date") or ""
    first, last = term_years(term)
    m = ROW_DAY.search(row.get("raw") or "")
    day = _j_iso(m.group(1), m.group(2), m.group(3)) if m else ""
    if day and first <= int(day[:4]) <= last and laid <= day <= (entered or day):
        return day, row
    return adjourned_by(body, laid, entered, term, sittings, sat, special), row


def adjourned_by(body, laid, entered, term, sittings, sat=_sat_by_journal, special=False):
    """The day the chamber adjourned with the bill on its table, by a row
    entered on `entered` that states no day: the last day it sat in the
    latest year of the term to end between the tabling and the row.

    THE ROW'S OWN DAY, where the chamber's journal opens a sitting on it
    after the last of its floor's that year, and no special session sat
    then: the House's "Died on Table" rows of 30 November 2017 were entered
    on the day it adjourned (HJ 21, "stand adjourned from the 2017 House
    Session"), when it voted on nothing, and the Senate's 2013 Rule 3-23
    rows on 3 September 2013, a sitting of its own. Not 18 November 2015,
    the special session's day the House entered its "Died on the Table" on
    26 measures of 2015, which died with the regular session.

    A SPECIAL SESSION'S BILL BY ITS OWN DAYS (`special`): SSHB 2 of 2010,
    laid on the House's table on 9 June 2010 and "Died, Session Ended" the
    same day. Where no day the chamber sat is known, none is given.

    A FIRST YEAR'S SESSION RECESSED INTO THE SECOND ended on the day it was
    called back to order and adjourned, the chamber's first sitting of the
    second year, where the row was entered that January (the review of the
    rail's endings, 9 October 2026): the House's of 2013 and 2019 -- "Although
    the June 26, 2013 Session continues here, the actual date is January 8,
    2014" (HJ 20 cont.), "The recessed Session of September 25, 2019 was
    called to order by the Speaker on January 8, 2020" (HJ 23 cont.), each
    then "adjourn[ed] from the 2013 [2019] Session" -- and the Senate's of
    2005, out of recess and adjourned on 4 January 2006 (SJ 24 cont.). Their
    "Died on Table" rows were entered on 8 January 2014, 9 January 2020 and
    4 January 2006; and the House's own rows of 2021 say so in as many words,
    "Died on Table, Session ended 01/05/2022". The 13, 29 and 25 bills of
    those tables were dated 26 June 2013, 25 September 2019 and 16 November
    2005."""
    first, last = term_years(term)
    if not (first and laid):
        return ""
    key = body + ("*" if special else "")
    if (not special and entered and int(laid[:4]) == first and entered[:4] == str(last)
            and entered[5:7] == "01"):
        opened = (sittings.get((body, str(last))) or [""])[0]
        if opened and opened[5:7] == "01" and laid <= opened <= entered:
            return opened
    upto = entered or laid
    years = range(max(int(laid[:4]), first), min(int(upto[:4]), last) + 1)
    ends = []
    for y in years:
        days = sittings.get((key, str(y))) or []
        if days and laid <= days[-1] <= upto:
            ends.append(days[-1])
    if not special and entered and first <= int(entered[:4]) <= last and entered >= laid:
        days = sittings.get((body, entered[:4])) or []
        sessions = sittings.get((body + "*", entered[:4])) or []
        if ((not days or entered > days[-1]) and entered not in sessions
                and sat is not None and sat(body, entered)):
            ends.append(entered)
    if ends:
        return max(ends)
    within = [d for y in years for d in sittings.get((key, str(y))) or [] if laid <= d <= upto]
    return max(within, default="")


# Since when each chamber's adjournment killed the bills left on its table
# in the first year of a term, as the record shows it: the Senate from 2001,
# the House from 2007 (the review of the tabled bills, 8 October 2026).
# Before them a bill tabled in the first year carried over into the second
# -- the House calendar of 2000 says its bills "remained on the table" at
# the adjournment of 3 November 1999, and HB 536 came off it in 2000.
FIRST_YEAR_TABLE_DIES = {"S": 2001, "H": 2007}


def last_sat(body, laid, term, sittings, special=False):
    """The last day the chamber sat in the year a bill tabled on `laid` lay
    there: that year's, or the term's second year's for a first-year tabling
    of a chamber that carried them over (FIRST_YEAR_TABLE_DIES); a special
    session's own days for its bill. Never before the tabling, and none
    where no day the chamber sat is known."""
    first, last = term_years(term)
    if not (first and laid):
        return ""
    y = int(laid[:4])
    if y < last and y < FIRST_YEAR_TABLE_DIES.get(body, 0):
        y = last
    days = sittings.get((body + ("*" if special else ""), str(y))) or []
    return max(days[-1], laid) if days else ""


def table_death_line(narr, tab, steps, term, sittings, sat=_sat_by_journal, ends=None):
    """The line of How it got here that says the bill died on the table: a
    new one, or the journey's own where it already has the death's in that
    chamber -- the Senate's Rule 3-23 ("Killed under Senate Rule 3-23, still on the table at
    adjournment"), or the 1990s motion that killed "the other bills left on
    the table" -- whose day is set to table_death's where its row's is not
    the day it died: HB 201 of 2020's line had no day, its row saying
    "Adjournment 09/16/2021", and its Law stop none.
    Returns (line, day, how): `how` is "row" or "sat" for a new line, and
    "line" where `line` is the journey's own, which the caller does not add."""
    day, row = table_death(narr, tab, term, sittings, sat, ends)
    at = next(i for i, s in enumerate(steps) if s is tab)
    had = next((s for s in steps[at + 1:] if s.get("body") == tab["body"]
                and s.get("act") == "died"), None)
    if had is not None:
        if (row is not None and (had.get("text") or "").startswith("Killed under Senate Rule 3-23")
                and had.get("date") in ("", row.get("date")) and day and had.get("date") != day):
            had["date"] = day
        return had, had.get("date") or day, "line"
    chamber = {"H": "House", "S": "Senate"}[tab["body"]]
    text = ("Died on the table when the session ended" if row is not None else
            f"Still on the table when the {chamber} last sat; died there when the "
            "session ended")
    return ({"date": day, "body": tab["body"], "act": "died", "mark": "x", "text": text,
             "short": "died on table"}, day, "row" if row is not None else "sat")


# What a history already says of a death on the table, in its own words or a
# closing paragraph's: narrative.py's "The bill died on the table when the
# session ended ..." and "... under Senate Rule 3-23", the 1990s' kill of
# "all bills on table", CLOSING's "died when the session ended".
TOLD_TABLE_DEATH = ("died on the table", "died there", "rule 3-23", "session ended",
                    "died when the session", "bills on the table", "bills laid on the table",
                    "left on the table")


def table_death_told(narr, tab, day, how, line=None, ending=None):
    """The sentence a history ends with where it does not tell the bill's
    death on the table, or None where it does: in narrative.py's own words
    for a row it reads ("died", "senate_rule_kill"), so a history that comes
    to tell the row itself says the same; and where no row is on the docket,
    in the words of the line (table_death_line). `line` is the death's line
    of How it got here."""
    told = " ".join([s.get("text", "") for s in (narr or {}).get("stages", [])]
                    + [(ending or {}).get("text", "")]).lower()
    if any(g in told for g in TOLD_TABLE_DEATH) or not day:
        return None
    chamber = {"H": "House", "S": "Senate"}[tab["body"]]
    if how == "sat":
        return (f"It was still on the {chamber}'s table when the {chamber} last sat, on "
                f"{_long_date(day)}, and it died there when the session ended.")
    said = (line or {}).get("text") or ""
    if said.startswith("Killed under Senate Rule 3-23"):
        adj = " at adjournment" if said.endswith("at adjournment") else ""
        return (f"The bill died on the table under Senate Rule 3-23{adj} on {_long_date(day)}, "
                "having been set aside and never taken back up.")
    if how == "line":
        return (f"The bill died on the table on {_long_date(day)}, having been set aside and "
                "never taken back up.")
    return (f"The bill died on the table when the session ended on {_long_date(day)}, "
            "having been set aside and never taken back up.")


# THE INTERIM STUDY COMMITTEE'S REPORT, in every wording the docket has used
# (the review of interim study, 8 October 2026): "INT STUDY REPORT ITL FOR
# 1991 SESSION (VOTE 11-0)" (1989-90), "INT STUDY REPORT (ITL) FILED (VOTE
# 11-0)" (1991-92), "INT STUDY REPT: REC FOR LEG IN 1997 (VOTE 17-0) <LSR
# 97-0155>" (1993-98), "Int Study Report: REC FOR LEGIS IN 2001 (vote 14-0)",
# "Interim Study Report: Recommended for Future Legislation in 2009 (Vote
# 11-0)", "Interim Study Report: Without Recomendation (Vote 10-10)" (2024),
# "Interim Study Report: Not Recommended for Future Legislation 09/29/2026
# (Vote 8-2; )", "Interim Study Report: No Recommendation" (HB 1592 of
# 2014). STUDY_REPORT read the last two wordings alone, 751 of the 1,534
# reports.
# The interim study report's row, its tally and the year it names, read as
# the committee pages read them: committee_acts holds the patterns, and
# study_said what a report recommends, so that one row is read one way on
# both (9 October 2026).
from committee_acts import (INTERIM_REPORT_ROW, INTERIM_REPORT_TALLY,  # noqa: E402
                            INTERIM_REPORT_YEAR, study_said)


def interim_report(narr, term=""):
    """What the interim study committee reported, or None: {"date", "body",
    "rec": "rec", "not" or "without" (or "" where the row states none),
    "vote": "17–0", "year": "1997" where it names the next term's first year}.
    The majority's report over the minority's (HB 1561 of 1994 has both),
    and of several the latest."""
    reps = [e for e in (narr or {}).get("events", []) or []
            if not e.get("cancelled") and INTERIM_REPORT_ROW.search(e.get("raw") or "")]
    if not reps:
        return None
    maj = [e for e in reps if not re.search(r"\bMIN\b", e.get("raw") or "", re.I)] or reps
    e = max(maj, key=lambda x: x.get("date") or "")
    raw = e.get("raw") or ""
    rec = study_said(raw)
    t = INTERIM_REPORT_TALLY.search(raw)
    y = INTERIM_REPORT_YEAR.search(raw)
    nxt = term_years(term)[1] + 1 if term else 0
    return {"date": e.get("date") or "", "body": (e.get("body") or "")[:1].upper(),
            "rec": rec, "recommended": rec == "rec",
            "vote": f"{t.group(1)}–{t.group(2)}" if t else "",
            "year": y.group(1) if y and nxt and int(y.group(1)) == nxt else ""}


# THE NEXT TERM'S BILL, where the clerk wrote down its LSR (1991-1998): "<LSR
# 97-0155>" on the report itself (HB 1179 of 1996), "1995 LSR: 0131" (HB 1162
# of 1994, which is HB 581 of 1995), "<1995 LSR 0108>", "(SEE LSR 0175,
# 1993)", "{LSR 0155, HB 154, CH. 183, 1997 SIGNED BY GOV 6/18/97}". A "?"
# after the number is the clerk's own doubt, and the line says so.
NEXT_LSR = (
    re.compile(r"<\s*LSR\s+(?P<yy>\d{2})\s*-\s*(?P<num>\d{1,4})(?P<q>\?)?", re.I),
    re.compile(r"(?P<yyyy>(?:19|20)\d\d)\s+(?:MIN\s+REPT\s+)?LSR\s*:?\s*(?P<num>\d{1,4})(?P<q>\?)?",
               re.I),
    re.compile(r"\bSEE\s+LSR\s+(?P<num>\d{1,4})(?P<q>\?)?\s*,\s*(?P<yyyy>(?:19|20)\d\d)", re.I),
    re.compile(r"\{\s*LSR\s+(?P<num>\d{1,4})(?P<q>\?)?\s*,\s*(?P<bill>[A-Z]+)\s*(?P<bnum>\d+)",
               re.I),
)


def lsr_bills(bills):
    """{(term, LSR number): (bill, year)} over every term, for the next term's
    bill a clerk's LSR note names. Within a term the number is the bill's
    own: the 1990s numbered a second year's requests from 2000 up. Keyed by
    the term, not the year, because a bill carried into the second year is
    filed under it: "1995 LSR: 0171" on HB 1261 of 1994 is HB 207, whose
    docket rows of 1995 carry the session year 1996. A number two bills of a
    term carry is left out. `year` is the bill's year on this site, its
    address and the one its card names."""
    seen, out = Counter(), {}
    for term, byb in (bills or {}).items():
        for bid, b in byb.items():
            try:
                k = (term, int(str(b.get("lsr_num") or "").lstrip("0") or 0))
                y = int(b.get("lsr_year") or 0)
            except ValueError:
                continue
            if k[1] and y:
                seen[k] += 1
                out[k] = (bid, y)
    return {k: v for k, v in out.items() if seen[k] == 1}


def next_term_bill(narr, term, lsrs):
    """{"id", "year", "queried"} -- the next term's bill a clerk's LSR note
    on this one names, by the next term's first year and the number, where
    it resolves to a bill of that term -- or None."""
    end = term_years(term)[1]
    nxt, after = end + 1, f"{end + 1}-{end + 2}"
    if not (end and lsrs):
        return None
    got = []
    for e in (narr or {}).get("events", []) or []:
        raw = e.get("raw") or ""
        for rx in NEXT_LSR:
            for m in rx.finditer(raw):
                g = m.groupdict()
                y = (int(g["yyyy"]) if g.get("yyyy") else
                     (1900 if int(g["yy"]) > 50 else 2000) + int(g["yy"]) if g.get("yy") else nxt)
                hit = lsrs.get((after, int(g["num"]))) if y == nxt else None
                if not hit:
                    continue
                if g.get("bill") and hit[0].upper() != f"{g['bill']}{g['bnum']}".upper():
                    continue
                got.append({"id": hit[0], "year": hit[1], "queried": bool(g.get("q"))})
    if not got:
        return None
    return next((x for x in got if not x["queried"]), got[0])


def study_ending(narr, steps, rail, term, sittings, lsrs=None):
    """The lines How it got here ends with for a bill held for interim study
    once its session is over: the death, and the committee's report.

    IT DIED WHEN ITS SESSION ENDED, on the last day the chamber that studied
    it sat: counted over all 2,392 interim study bills of nineteen terms on 8
    October 2026, no row says one died, and none was acted on after that day.
    Since 1993 every referral is of the second year; the 23 of the first
    year, the Senate's of 1989 and 1991, take the second year's day too.

    THE REPORT IS ADVICE, NOT AN ACT ON THE BILL (House Rule 44(a) as
    amended in 1997, Rule 45(a) of 2025: the committee "shall submit ... its
    findings and any recommendations"), dated by the report and usually after
    the death: SB 570 of 2026 died on 19 August and was recommended for future
    legislation, 9-0, on 28 September. Its line is a green arrow where the
    committee recommended the subject come back as a new bill, and names
    that bill where the clerk wrote down its LSR; the "~" where it did not,
    or made no recommendation at all. The Senate files none."""
    hs = [s for s in steps if s.get("body") in ("H", "S")]
    study = next((s for s in reversed(hs) if s.get("act") == "study"), None)
    if study is not None:
        body = study["body"]
    elif rail and rail[0] in ("H", "S") and "x" in rail[1:3]:
        order = (rail[0], "S" if rail[0] == "H" else "H")
        body = order[rail[1:3].index("x")]
    else:
        return []
    chamber = {"H": "House", "S": "Senate"}[body]
    special = str((narr or {}).get("bill") or "").upper().startswith("SS")
    days = sittings.get((body + ("*" if special else ""), str(term_years(term)[1]))) or []
    day = days[-1] if days else ""
    if study is not None and day and (study.get("date") or "") > day:
        day = study["date"]
    out = [{"date": day, "body": body, "act": "died", "mark": "x",
            # THE PERSON'S WORDS (approved 17 October 2026), with the fall
            # named by its year so the line reads true in any later year: it
            # said "Still in interim study when the House last sat; died when
            # the session ended" beside an Interim Study chip and a work
            # session still to come.
            "text": (f"In interim study: the committee studies the subject in the fall of "
                     f"{term_years(term)[1]}; the bill goes no further"),
            "short": "died in interim study"}]
    rep = interim_report(narr, term)
    if rep:
        # SAID AS EVERY OTHER PLACE SAYS IT (23 October 2026): the phrase is
        # study_report.json's, which the docket's plain line, the bill's
        # closing note, a committee's meeting card and the emails take too;
        # this line adds the next term's year where the clerk wrote one.
        sr = _WORDBOOK["study_report"]
        words = sr["said"].get(rep["rec"])
        if words and rep["year"] and rep["rec"] != "without":
            words += f" in {rep['year']}"
        text = (f"{sr['head']}: {words}" if words else f"{sr['head']} filed") + (
            f", {rep['vote']}" if rep["vote"] else "")
        line = {"date": rep["date"], "body": rep["body"] if rep["body"] in ("H", "S") else body,
                "act": "study_report", "mark": "f" if rep["rec"] == "rec" else "s",
                # Which of the three it said, for its colour (app.js journeyList).
                "rec": rep["rec"], "text": text, "short": "interim study report"}
        nb = next_term_bill(narr, term, lsrs)
        if nb:
            name = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", nb["id"]) + f" of {nb['year']}"
            line["text"] += (f"; the clerk noted, with a question mark, that it was filed "
                             f"again as {name}" if nb["queried"] else f"; filed again as {name}")
            line["link"] = {"text": name, "href": f"bill/{nb['year']}/{nb['id'].lower()}"}
        out.append(line)
    out.sort(key=lambda s: s.get("date") or "9999")
    return out


def session_endings(narr, steps, rail, chip, status, term, over, sittings, lsrs=None,
                    ending=None, sat=_sat_by_journal, ends=None):
    """The rail's endings for one bill, as build_bills makes them: the lines
    How it got here ends with, added to `steps`, for a bill that died on the
    table (table_death_line) and for one held for interim study whose
    session is `over` (study_ending). Returns (tabled, ending): the line that
    laid a bill that died on the table there, for journey_rail; and the
    history's closing paragraph (closing_stage's `ending`), with the death's
    sentence where the history does not tell it (table_death_told)."""
    tabled = died_on_table(steps, chip, status)
    if tabled is not None:
        line, day, how = table_death_line(narr, tabled, steps, term, sittings, sat, ends)
        if how != "line":
            steps.append(line)
        said = table_death_told(narr, tabled, day, how, line, ending)
        if said and ending:
            ending = {**ending, "text": f"{ending['text']} {said}"}
        elif said:
            ending = {"label": "How It Ended", "text": said}
    elif chip == INTERIM_STUDY and over:
        steps.extend(study_ending(narr, steps, rail, term, sittings, lsrs))
    return tabled, ending


# The lines the session's end makes (table_death_line, study_ending), which
# no row of the docket decided.
SESSION_END_DEATHS = ("In interim study:", "Still on the table when",
                      "Died on the table when the session ended")


def session_end_line(s):
    """Whether a line of How it got here is one the session's end made."""
    return s.get("act") == "study_report" or (
        s.get("act") == "died" and (s.get("text") or "").startswith(SESSION_END_DEATHS))
