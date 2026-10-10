#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.1
"""
A member's term at a glance: the figures a member's page heads its term with.

    import member_figures as MF
    MF.status_category(row)                  # "Passed", "Died", ... as the bill search files a bill
    MF.term_figures(sponsored, attendance, rows)   # {term: {...}}

THE PERSON'S ORDER (9 October 2026, item 7): "the selected term's
attendance, then attendance on roll calls, then the number of bills filed
and the number passed, in the selected term". And v7, the same day: "'bills
filed' counts every bill filed, prime and co-sponsor together; 'bills
passed' the same." So `bills_filed` is every bill the member put their name
to that term, as prime sponsor or co-sponsor, and `bills_passed` those of
them the bill search files under Passed -- became law, a resolution
adopted, or a constitutional amendment the voters ratified. The prime and
co-sponsored counts are kept beside the totals, so a page that wants to say
how many were their own can, without working it out again.

PASSED IS THE BILL SEARCH'S PASSED, NOT A NEW RULE. status_category is
app.js's statusCat, the bill search's Status filter (the person, 8 October
2026): the chip's word first, then the bill's kind. preflight runs both over
the same rows and holds them to one answer, so the member's figure and the
search's category cannot drift apart.

ATTENDANCE IS member_attendance'S, unchanged (build_site_v2: a day is a day
the member's chamber held a roll call while they held the seat, attended if
they cast any vote that day; presiding and a declared conflict count as
present). `roll_calls_recorded` is the roll calls they voted on, presided
over or declared a conflict on: the prototype's "of roll calls recorded on"
(private/design/polish/proto/tools/build_members2.py, glance), decided here
once rather than by each page. A term before the roll calls begin (1999) has
no attendance, and says so with None, not with a zero.
"""

# app.js CAT_OF_CHIP, word for word: each word a chip can say that is not a
# stage, and the category it is in.
CAT_OF_CHIP = {
    "Became Law": "Passed", "Died": "Died", "Interim Study": "Interim Study",
    "Tabled": "Tabled", "Vetoed": "Vetoed", "Withdrawn": "Withdrawn",
    "Not introduced": "Died", "Proposed for the special session": "Died",
    "Passed both chambers, ratified by the voters": "Passed",
    "Passed both chambers, not ratified by the voters": "Died",
    "Passed, awaiting the governor": "In Progress"}
for _w in ("In committee", "In progress", "Retained in committee", "Re-referred to committee",
           "Committee report filed", "Passed one chamber", "In a committee of conference",
           "Conference committee report adopted", "One chamber did not concur",
           "One chamber did not concur; a committee of conference was asked for"):
    CAT_OF_CHIP[_w] = "In Progress"
# app.js CAT_OF_KIND.
CAT_OF_KIND = {"active": "In Progress", "law": "Passed", "adopted": "Passed",
               "study": "Interim Study", "done": "Died", "veto": "Died"}


def cat_of_chip(chip):
    """app.js catOfChip."""
    s = str(chip or "")
    if s in CAT_OF_CHIP:
        return CAT_OF_CHIP[s]
    if s.startswith("Adopted by "):
        return "Passed"
    if s.startswith("Passed both chambers, goes to the voters"):
        return "In Progress"
    return ""


def status_category(row):
    """app.js statusCat: the bill search's category for an index row; "" for
    a row with no chip (a request, which is not a bill yet)."""
    chip = (row or {}).get("chip")
    if not chip:
        return ""
    return cat_of_chip(chip) or CAT_OF_KIND.get((row or {}).get("kind")) or "In Progress"


def how_passed(row):
    """"law", "adopted" or "ratified" for a bill the search files under
    Passed, else None."""
    if status_category(row) != "Passed":
        return None
    chip = str((row or {}).get("chip") or "")
    if chip == "Became Law" or (row or {}).get("kind") == "law" and not chip.startswith("Passed both"):
        return "law"
    if chip.startswith("Passed both chambers, ratified"):
        return "ratified"
    return "adopted"


def term_figures(sponsored, attendance, rows):
    """{term: figures} for one member.

    `sponsored` is the member's sponsorships [{"term", "bill", "prime"}],
    `attendance` member_attendance()'s {term: {...}}, `rows` the bill index
    {(term, bill): row}. Every term either names is given."""
    out = {}
    terms = sorted({s.get("term") for s in sponsored or () if s.get("term")}
                   | set(attendance or {}))
    for t in terms:
        mine = {}
        for s in sponsored or ():
            if s.get("term") == t and s.get("bill"):
                # One bill once: prime wins where both are recorded.
                mine[s["bill"]] = mine.get(s["bill"], False) or bool(s.get("prime"))
        ways = {b: how_passed(rows.get((t, b))) for b in mine}
        prime = [b for b, p in mine.items() if p]
        co = [b for b, p in mine.items() if not p]
        f = {"bills_filed": len(mine),
             "bills_passed": sum(1 for b in mine if ways[b]),
             "became_law": sum(1 for b in mine if ways[b] == "law"),
             "adopted": sum(1 for b in mine if ways[b] == "adopted"),
             "ratified": sum(1 for b in mine if ways[b] == "ratified"),
             "prime": len(prime), "prime_passed": sum(1 for b in prime if ways[b]),
             "cosponsored": len(co), "cosponsored_passed": sum(1 for b in co if ways[b])}
        a = (attendance or {}).get(t)
        if a:
            f.update({"session_days": a.get("days", 0),
                      "days_attended": a.get("attended", 0),
                      "roll_calls": a.get("roll_calls", 0),
                      "roll_calls_recorded": (a.get("voted", 0) + a.get("presided", 0)
                                              + a.get("conflict", 0))})
        else:
            f.update({"session_days": None, "days_attended": None,
                      "roll_calls": None, "roll_calls_recorded": None})
        out[t] = f
    return out
