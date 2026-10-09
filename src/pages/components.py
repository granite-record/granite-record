#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.2
"""
The site's components, in Python: what the builders draw a person, a
committee, a date and a time with, and the words they say.

    import components as C
    C.date_words("2026-02-19", "full")     # "February 19, 2026"
    C.clock("13:30")                       # "1:30 PM", a no-break space before PM
    C.pchip(member)                        # one legislator, as every page draws one
    C.WORDBOOK["meeting_kinds"]["kinds"]   # the words, from src/pages/words/

ONE FILE IN EACH LANGUAGE, THE SAME NAMES (the component plan's C1, approved
9 October 2026). components.js, beside this file and published as
site/components.js, holds the same helpers for the pages a browser draws --
a bill, a legislator and a committee are app.js drawing a record -- and every
page loads it before any of its own scripts. A name here is the name there in
this language's case: date_words is dateWords, cmte_link is cmteLink. Two
files because the pages built ahead need Python and the pages drawn in the
browser need JavaScript; node rendering at build time, HTML inside each
record's JSON and one template read by two engines were each turned down in
the plan, for the reasons it gives.

HOW THEY STAY ONE. preflight's "every component gives the same answer in
Python and in the browser" runs every helper here and in components.js on
each case in tests/components_cases.json and compares the two answers byte
for byte. It fails on a helper one file has and the other does not, on a
helper no case runs, and on any line or branch of a helper -- here, or a
block there -- that no case reaches. A case may also state the answer it
wants, which holds both to the words the person chose (month first, "10:00
AM"). So a change to one file fails until the other agrees.

PURE AND THIN (C4). A plain value in, a string out, nothing read from a page
or a file: cmte_link is handed meta.json's committee codes. Deciding --
grouping meetings, choosing a chip's word, writing a person's label with the
seat held at the time -- happens upstream, once, and a helper only draws.

Moved here unchanged on 9 October 2026: esc, clock and pchip from
build_pages.py, date_words and date_span from shell.py, which keep their old
names for the builders that import them from there.

THE WORDS ARE WRITTEN ONCE (C3). The chip's words and classes, the kinds of
meeting, the vote words and the glossary are JSON files in
src/pages/words/, one to a kind. WORDBOOK below is each file by its name --
WORDBOOK["chips"], ["meeting_kinds"], ["votes"], ["glossary"] -- a key starting
with "_" being a note left out. The builders read them here, and the build
writes the same into site/components.js between its WORDBOOK markers
(build_pages.with_words), where the browser's scripts read them as
WORDBOOK. So there is one copy of each table, where there were two kept
alike by hand; preflight holds the browser's WORDBOOK to this one byte for
byte. (Not WORDS, which app.js already names the spelling list's state.)
"""

import _paths
import datetime
import json
import re

WORDBOOK_DIR = _paths.ROOT / "src" / "pages" / "words"
WORDBOOK = {p.stem: {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
                     if not k.startswith("_")}
            for p in sorted(WORDBOOK_DIR.glob("*.json"))}
if not WORDBOOK:
    # Not an empty table and a page that draws every chip without its colour.
    raise ImportError(f"components.py: no words in {WORDBOOK_DIR}, which holds what the "
                      "pages say: the chips, the kinds of meeting, the votes, the glossary")


def esc(s):
    """components.js's esc, exactly: ampersand, the angles and the double quote.

    NOT shell.E, which is html.escape and also turns an apostrophe into
    &#x27;. The two render identically, so the difference is invisible on the
    page and would be invisible in a diff of the two chips as well -- which is
    how a check that was meant to hold them together would come to be relaxed
    until it held nothing. The components escape for themselves so the
    comparison can stay byte for byte.
    """
    return (str("" if s is None else s).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


# DATEWORDS:START
# A DATE, ONE WAY, MONTH FIRST (8 October 2026: the person's D6 of the polish
# plan, "May 21, 2026" and "10:00 AM"). The site wrote its own dates in
# twelve forms -- "8 Jan 2025" and then "13 Feb" on one rail, "Thursday 19
# February 2026" over a session day, "WED 7 OCT" on the home page,
# "8/19/2026" in a member's votes, "2025-01-22 at 15:00" on the Hearings tab
# -- from six formatters in the builders and four in app.js. date_words() is
# the one in Python and components.js's dateWords() the one in the browser,
# and preflight holds the two to one answer for every form and fails a
# builder or script that writes a date some other way. A time is clock()'s
# "10:00 AM".
#
# What keeps its own style, because it follows somebody else's: a
# citation's date (shell.cite_day, MLA's "24 Sept. 2026"), a feed's RFC 822
# date, the docket's own lines as the clerk wrote them, and the home page's
# floor session titles ("August 19th, 2026"), which the person chose.
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DATE_FORMS = ("long", "full", "medium", "short", "day", "wkd")


def date_words(iso, form="medium"):
    """A day as the site writes it. `iso` is a date, or a string that starts
    "YYYY-MM-DD" (what follows is ignored); anything else comes back as it
    came, as clock() gives back what is not a time.

        long    Thursday, February 19, 2026   a day's own title
        full    February 19, 2026             in a sentence
        medium  Feb 19, 2026                  a row, a list, the rail
        short   Feb 19                        where the year is already said
        day     Thursday, February 19         a day inside a week that says its year
        wkd     Thu, Feb 19                   the same, where the room is short
    """
    if isinstance(iso, datetime.datetime):
        iso = iso.date()
    if isinstance(iso, datetime.date):
        d = iso
    else:
        m = re.match(r"(\d{4})-(\d\d)-(\d\d)", str(iso or ""))
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
        except ValueError:
            d = None
        if d is None:
            return "" if iso is None else str(iso)
    month, mon, wd = MONTHS[d.month - 1], MONTHS[d.month - 1][:3], WEEKDAYS[d.weekday()]
    return {"long": f"{wd}, {month} {d.day}, {d.year}",
            "full": f"{month} {d.day}, {d.year}",
            "short": f"{mon} {d.day}",
            "day": f"{wd}, {month} {d.day}",
            "wkd": f"{wd[:3]}, {mon} {d.day}"}.get(form, f"{mon} {d.day}, {d.year}")


def date_span(a, b):
    """Two days as one span, month first: "October 5–11, 2026", "September 28
    – October 4, 2026", "December 28, 2026 – January 3, 2027"; one day where
    the two are the same. components.js's dateSpan() says the same."""
    if str(a)[:10] == str(b)[:10]:
        return date_words(a, "full")
    fa, fb = date_words(a, "full"), date_words(b, "full")
    if fa == str(a) or fb == str(b):
        return f"{fa} – {fb}"
    (ma, da, ya), (mb, db, yb) = (x.replace(",", "").split() for x in (fa, fb))
    if ya != yb:
        return f"{fa} – {fb}"
    if ma != mb:
        return f"{ma} {da} – {mb} {db}, {yb}"
    return f"{ma} {da}–{db}, {yb}"
# DATEWORDS:END


def clock(t):
    """"13:30" -> "1:30 PM": a time as a reader says it.

    Asked for on 25 September 2026: "I'd also prefer if times were listed
    with AM and PM instead of 13:00." Noon is "12:00 PM" and midnight "12:00
    AM". Only what is printed changes: a card's data-time keeps the record's
    own "13:30", which the Calendar's script and the add-to-calendar links
    read. A no-break space keeps AM or PM with its time when a narrow column
    wraps the line. components.js's clock() is the same function in the
    browser. Anything that is not a time is given back as it came.
    """
    m = re.match(r"^(\d{1,2}):(\d\d)", t or "")
    if not m or int(m.group(1)) > 23:
        return t or ""
    h = int(m.group(1))
    return f"{h % 12 or 12}:{m.group(2)}\u00a0{'AM' if h < 12 else 'PM'}"


def cmte_link(name, term, codes):
    """A committee named on a bill, as a link to its page where there is one:
    components.js's cmteLink. `codes` is meta.json's committee_codes, where a
    name that has been two committees maps each term to its own page,
    {"": page, "<term>": page}, and the term decides; the label is never
    changed to the later name."""
    v = (codes or {}).get(name)
    code = v if isinstance(v, str) else (
        (v[term] if term and term in v else v.get("")) if v else "")
    return f'<a href="committee/{esc(code)}.html">{esc(name)}</a>' if code else esc(name)


# THE PARTY AND DISTRICT ARE ONE UNIT (the look of 7 October 2026). Where a
# chip has to wrap -- the House by seat in five columns, any chip on a phone --
# it broke wherever a space fell, so a line ended "Rep. Jason Osborne (R" and
# the next began "- Rock 2)". The trailing "(R - Rock 2)" is its own span,
# which app.css keeps on one line, so a chip that wraps does so between the
# name and the tag. The text is unchanged.
CHIP_TAG = re.compile(r"(.*\S)\s+(\([^()]*\))")


def pchip(m):
    """One legislator, as the site draws them everywhere else.

    The party code reads party_code first and the first letter of party
    second, because sponsor records carry "Republican" and the roster carries
    "R", and a member must not read as one party on a bill and another on the
    roster -- which is the bug that made this one component in the first
    place."""
    code = str(m.get("party_code") or m.get("party") or "").upper()[:1] or "X"
    full = str(m.get("display_full") or m.get("label") or m.get("name") or "")
    tag = CHIP_TAG.fullmatch(full)
    who = (f'{esc(tag.group(1))} <span class="mtag">{esc(tag.group(2))}</span>'
           if tag else esc(full))
    role = m.get("role") if (m.get("role") and m.get("role") != "Member") else (
        "Prime" if m.get("prime") else "")
    slug = m.get("slug") or ""
    inner = (f'<a href="legislator/{esc(slug)}.html">{who}</a>' if slug else who)
    return (f'<span class="mchip p-{esc(code)}">{inner}'
            + (f" <i>{esc(role)}</i>" if role else "") + "</span>")
