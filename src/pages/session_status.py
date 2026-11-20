#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
Where the session is: the day the current term ran out of session days, as
corrections/status/status.txt states it (session_over), that day only where
it is a day of the current term (session_over_in), and the site's "where the
session is" panel, the hand-kept facts of the same file merged with what the
data can show (build_status).

    import session_status as SS
    over = SS.session_over_in(SS.session_over(path), current)   # a day, or ""
    status = SS.build_status(a, index, procs, floor, today, latest_by_body, upcoming)

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited: from
session_over to build_status, one block. It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

from datetime import date as _date
from pathlib import Path

import build_date
import proceedings as P


def session_over(path):
    """The day the current term ran out of session days, as corrections/status/status.txt
    states it, or "".

    Read on its own and before the bills are built, because it decides whether a
    bill of the current term that is still pending is still moving. build_status
    reads the same file later for the page's panel; this is one line of it, and
    duplicating the read costs nothing next to threading the panel through the
    bill loop.
    """
    p = Path(path)
    if not p.exists():
        return ""
    for raw in p.read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith("#"):
            continue
        k, _, v = raw.split("#")[0].partition(":")
        if k.strip().lower() == "session_over" and v.strip():
            return v.strip()
    return ""


def session_over_in(day, current):
    """`day`, the file's session_over, where it is a day of the term `current`;
    else "".

    THE LINE IS TAKEN OUT BY HAND ("Delete the line in December"), AND A LINE
    LEFT IN SAYS NOTHING OF THE NEXT TERM. With "session_over: 2026-08-19"
    still in the file when 2027-2028 is the current term, every measure of
    2027 that had passed its own chamber and awaited the other read "Died
    when the session ended", over a paragraph saying it went no further
    (ended_with_the_term, which the day turns on for the current term): 138
    of 138, when this term's docket was replayed two years on and cut at 15
    March. The day is of a term, and it ends that one.
    """
    return day if day and current and P.term_of(str(day)) == current else ""


def build_status(a, index, procs, floor, today, latest_by_body, upcoming):
    """The site's "where the session is" panel.

    Hand-maintained facts from status/session.txt merged with what the data
    can show. Split out of main(); returns the status dict.
    """
    # Hand-maintained facts merged with what the data can show. The phase, the
    # session calendar and veto day are set by the chambers and published only
    # in the calendars, so they are edited rather than derived; the last session
    # date and the count of scheduled hearings come from the data.
    status = {"milestones": []}
    ms_es = {}  # milestone_es: DATE | LABEL | NOTE, matched to the English one by date
    sp = Path(a.status)
    if sp.exists():
        last_key = None
        for raw in sp.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("#"):
                continue
            line = raw.split("#")[0].rstrip()
            if not line.strip():
                last_key = None
                continue
            # An indented line continues the previous value, so a note can be
            # written as a paragraph instead of one unreadable line.
            if raw[:1] in " \t" and last_key in ("note", "headline", "note_es"):
                status[last_key] = (status.get(last_key, "") + " "
                                    + line.strip()).strip()
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            last_key = k
            if k == "milestone":
                parts = [x.strip() for x in v.split("|")]
                if parts and parts[0] >= today:
                    status["milestones"].append({
                        "date": parts[0],
                        "label": parts[1] if len(parts) > 1 else "",
                        "note": parts[2] if len(parts) > 2 else ""})
            elif k == "milestone_es":
                parts = [x.strip() for x in v.split("|")]
                if parts and parts[0]:
                    ms_es[parts[0]] = {
                        "label_es": parts[1] if len(parts) > 1 else "",
                        "note_es": parts[2] if len(parts) > 2 else ""}
            elif k in ("updated", "phase", "headline", "note", "note_es", "session_over"):
                status[k] = v
        for m in status["milestones"]:
            m.update({x: y for x, y in ms_es.get(m["date"], {}).items() if y})
        status["milestones"].sort(key=lambda m: m["date"])
        if status.get("updated"):
            age = (build_date.today() - _date.fromisoformat(status["updated"])).days
            status["stale_days"] = age
            if age > 45:
                print(f"  corrections/status/status.txt was last updated {age} days ago "
                      "\u2014 the page will say so")
    # Latest sitting of either chamber, from the per-chamber map that replaced
    # the old single "most recent session".
    status["last_session"] = (max(v["date"] for v in latest_by_body.values())
                              if latest_by_body else None)
    status["hearings_next_14"] = len(upcoming)

    return status
