#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-24.1
"""
The General Court's calendar and journal PDFs, found by the drain's queue.

    import queue_links as QL
    QL.calendar_keys_from_queue()      # {"HC 18 2015": url}
    QL.journal_keys_from_queue()       # {"HJ 16 2026": (url, "2026-08-19")}
    QL.journal_url(date, "HJ 16", keys)

WHY A MODULE OF ITS OWN (24 September 2026). These three lived in
build_site_v2.py, and build_calendar.py and build_session_pages.py imported
build_site_v2 to reach them. Importing build_site_v2 imports topic_model,
which changes the working folder to the repository whenever it is run from
anywhere else -- so preflight's fixture run of build_session_pages, standing
in a temporary folder, read the fixture's narratives and then wrote its pages
into the real site/ (two Senate sittings were overwritten before the prune
ceiling refused the rest). Standard library and session_days only: importing
this changes nothing about where a builder stands. build_site_v2 imports the
same names from here, so its callers are unchanged.
"""
import csv
import re
from collections import defaultdict


def calendar_keys_from_queue(path="archive/queue.csv"):
    """{"HC 18 2015": address} for every calendar the drain fetched.

    calendars.json has year-qualified keys only for the years its fetcher
    ran, 2023-2026. The drain's queue names the address of every calendar on
    this disk and the file it went to, and a calendar's number is its file's
    number within its year -- so the key is the file's own. Only a base
    edition answers: a supplement or a verbatim saved at the base calendar's
    path would otherwise answer every citation of the base, and where several
    listed documents share one file it is the one row that records fetching
    it, or none. Journals are not here: in 1997-2012 the docket's "HJ n" is
    the House Record's issue number, not the file's.
    """
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except OSError:
        return {}
    by = defaultdict(list)
    for r in rows:
        if r.get("kind") == "calendar" and r.get("state") == "held":
            by[r["path"].replace("\\", "/").lower()].append(r)
    out = {}
    for p, rs in by.items():
        pick = rs if len(rs) == 1 else [r for r in rs if r.get("fetched")]
        if len(pick) != 1 or not pick[0].get("url"):
            continue
        if re.search(r"supplement|verbatim", pick[0].get("name") or "", re.I):
            continue
        m = re.match(r"^calendars(_senate)?/(\d{4})/(hc|sc)0*(\d+)([a-z]?)\.pdf$", p)
        if m:
            out[f"{m.group(3).upper()} {int(m.group(4))}{m.group(5).upper()} "
                f"{m.group(2)}"] = pick[0]["url"]
    return out


def journal_keys_from_queue(path="archive/queue.csv", since=2025):
    """{"HJ 16 2026": (address, "2026-08-19")} for the journals the drain
    fetched, from `since` on; the date is the one the file's name states, or
    "" where it states none ("SJ 15.pdf").

    The key is the journal's own number and the year of the folder it is
    filed under, which is its series: a session's numbering restarts each
    year and the December organization day opens the next year's, so
    "HJ 01 December 4, 2024" is filed under 2025 and is HJ 1 2025 --
    session_days.journal_series gives a sitting's date the same year. From
    2025 only, for the reason calendar_keys_from_queue leaves journals out:
    in 1997-2012 the docket's "HJ n" is the House Record's issue number, not
    the file's, and the years between have not been checked. A number that
    two held files claim answers nothing rather than either.
    """
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except OSError:
        return {}
    months = ("january february march april may june july august september "
              "october november december").split()
    seen = defaultdict(set)
    for r in rows:
        if r.get("kind") != "journal" or r.get("state") != "held" or not r.get("url"):
            continue
        p = r["path"].replace("\\", "/").lower()
        m = re.match(r"^journals(?:_senate)?/(\d{4})/(hj|sj)\s*0*(\d+)\b", p)
        if not (m and int(m.group(1)) >= since):
            continue
        d = re.search(r"\b(" + "|".join(months) + r")\s+(\d{1,2}),?\s+(\d{4})", p)
        named = (f"{d.group(3)}-{months.index(d.group(1)) + 1:02d}-{int(d.group(2)):02d}"
                 if d else "")
        seen[f"{m.group(2).upper()} {int(m.group(3))} {m.group(1)}"].add((r["url"], named))
    return {k: v.pop() for k, v in seen.items() if len(v) == 1}


def journal_url(date, cite, keys):
    """The address of the journal a sitting on `date` is printed in, or "".

    By the journal's NUMBER, which the sitting's own rows cite ("HJ 16"), and
    never by the date alone. The year is the number's series, which for a
    December sitting may be either year -- the organization day opens the
    next year's numbering, and a December session in an odd year stays in its
    own -- so both are tried, and a file is taken only where its own name
    states this very date, or states none and the year is the series
    session_days.journal_series gives. Anything else answers nothing: a
    wrong journal is worse than no link.
    """
    import session_days
    m = re.match(r"^([HS]J)\s*0*(\d+)$", (cite or "").strip().upper())
    if not m or not date:
        return ""
    series = session_days.journal_series(date)
    hits = set()
    for y in {date[:4], series}:
        v = keys.get(f"{m.group(1)} {int(m.group(2))} {y}")
        if v and (v[1] == date or (not v[1] and y == series)):
            hits.add(v[0])
    return hits.pop() if len(hits) == 1 else ""
