#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-01.13
"""
The General Court's calendars and journals, as the PDFs the General Court
serves: the list the Calendars and journals page's pickers read.

    import calendar_documents as CD
    docs, out = CD.read()            # what is linked, and what is left out
    CD.index(docs)                   # site/calendar/documents.json
    CD.block_html(docs)              # the pickers and the newest, at the top of the list page
    CD.list_body(docs, out)          # site/calendar/documents.html's heading, line and directory
    CD.PICKER_JS                     # the pickers' script

    python3 src/pages/calendar_documents.py    # what a build would link, no network

WHAT WAS ASKED (1 October 2026). Below the Calendar page's schedule, a way to
open the House and Senate calendars and journals as PDFs "in a similar way to
how GenCourt does it": pickers in a row -- which kind, which year, which
document -- and a button that opens the one chosen. The General Court has a
page per chamber, each with three pickers; here it is one row, and the first
picker carries the chamber: House Calendars, House Journals, Senate Calendars,
Senate Journals.

AT THE TOP OF THE LIST (the owner, 25 November 2026): "move this section of
the calendar/journal selector to the calendars/journals tab at the top so that
it's easy to select what you're looking for quickly and have the full
directory below that rather than splitting it across the schedule page." The
pickers and the newest of each kind are the first thing under the list page's
heading, its line and Cite this page, and the directory follows them as it
was. The week's schedule carries none of it: the Calendar row's Calendars and
journals tab is the way there.

LINKED, NOT HOSTED. The PDFs are 1.5 GB against a 2.0 GB deploy, three of
them are larger than Cloudflare Pages allows one file to be, and GitHub's
nightly machine does not hold them at all. What it does hold is
archive/queue.csv: one row for every document the General Court's own
dropdown listed, with the address its own "View PDF File" button uses. So
every link here is one of those addresses, byte for byte.

NOTHING IS CONSTRUCTED. A file's name follows no rule -- "No 32 September 4
2026", "No30 August 14 2026", "HC 32", "63", "HJ No 25 06-25-1997" -- and
guessing at names is what got this project's address blocked. An address is
in the list or it is not linked: the index stores each one as the part after
its chamber's viewer prefix, cut from the recorded text and never encoded
again, so the page's script cannot produce an address the record does not
hold. preflight holds every link to that.

WHAT A LABEL SAYS. The name of the General Court's file, with nothing
rewritten: "No 01 January 04 1012" stays as the House filed it. THE FILE'S
NAME, WHICH IS NOT ALWAYS THE GENERAL COURT'S LABEL. Its own dropdown shows
the file's name for all but the newest document, which it posts under a short
name and labels in full: on the saved probe_calendars.html the option
"SC 29.pdf" reads "No 29 September 3 2026". The queue records the file's name
and not that label, so the list page says a document is under its file's
name, and not "named as the General Court names it", which it said on
1 October. Where a name states no date ("HC 32", "SC 29", "SJ 15") the date
the document itself prints is added after a dash, read from the text beside
the PDF where that text is on disk: a calendar's masthead, taken only where
it carries the document's own number, and a Senate journal's sitting
(journal_days.senate_openings), taken only where the journal holds one day's.
Anywhere else the name stands alone: a date nobody could check is not
offered. printed_date holds the measure of both readings against the names
that do state a date.

EACH DOCUMENT ONCE, UNDER ITS OWN DATE'S YEAR. The General Court files
December's documents under the next year, and lists some twice -- twenty of
2011's House journals are under 2010 as well. Here a document is under the
year its date gives, once. A document whose date is not known stays under
the year list the General Court put it in -- so for those a year is the
General Court's filing and not a date, and the list page says so and says
how many they are. A year is not guessed from a neighbour's date: the guess
would be taken back the night the document's own text is read.

WHAT IS LEFT OUT, AND SAID. A row the queue marks withheld, gone or failed,
or holds an error against, is not linked. The list page says how many in one
line, once, and names them. "NOT LINKED HERE", AND NOT "DOES NOT
SERVE". The page said "the General Court lists but does not serve" of 45
documents, and the queue bears that out for two: 2008's "09A" and "09B"
answered 403. Forty-two more were set aside for having names of the same
form and were never asked for, and the forty-fifth answered 500 at an
address carrying this project's own unescaped "&#39;". A statement about the
General Court's server, on a page its staff read, has to be one the record
holds. What the record holds is that this page does not link them, and how
many of them were ever asked for.

THE LIST GROWS. The nightly refreshes the queue, so nothing here counts on
its size, its years or its states: a row in a state this has not seen is
linked if it has an address and no error, a set with nothing in it draws
nothing, and the build prints what it read every time.

WHY A MODULE OF ITS OWN. As queue_links.py: standard library only, so
importing it changes nothing about where a builder stands. The two readers
of the documents' own dates are imported when a date is wanted, not before.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import csv
import datetime
import html
import json
import re
from collections import Counter, OrderedDict, defaultdict, namedtuple

import build_date
import inline_js as IJ
import shell
from i18n import say

QUEUE = Path("archive") / "queue.csv"

# (id, chamber, kind, what the picker calls the set, what a link calls one)
# in the order of the first picker.
SETS = (("hc", "H", "calendar", "House Calendars", "House Calendar"),
        ("hj", "H", "journal", "House Journals", "House Journal"),
        ("sc", "S", "calendar", "Senate Calendars", "Senate Calendar"),
        ("sj", "S", "journal", "Senate Journals", "Senate Journal"))
SET_OF = {(ch, kind): sid for sid, ch, kind, _many, _one in SETS}
MANY = {sid: many for sid, _ch, _kind, many, _one in SETS}
ONE = {sid: one for sid, _ch, _kind, _many, one in SETS}
CHAMBER = {sid: ch for sid, ch, _kind, _many, _one in SETS}

# Where the pickers and their list live. The list is beside the week pages and
# not in calendar/data/, which build_calendar.month_files prunes. ANCHOR is the
# box at the top of the list page, which the pickers' script looks for.
ANCHOR = "cdocs"
NOT_LINKED = "notlinked"    # the list page's section that names what is left out
LIST_PATH = "/calendar/documents.html"
INDEX_PATH = "/calendar/documents.json"

# Only the General Court's own addresses are linked.
HOST = "https://gc.nh.gov/"
# A state that says the address is not one to send a reader to.
HELD_BACK = ("withheld", "gone", "failed")

MONTHS = ("January February March April May June July August September "
          "October November December").split()

# A date a name states. "No 32 September 4 2026", "HJ 16 August 19, 2026",
# "No13aFebruary 21 2025", "No 18 March31 2023", "No 17 February 29
# (AMENDMENTS) 2008", "No 22 March 27 and 28 2007 Amendments"; and the
# figures of 1997-2011, "HJ No 25 06-25-1997", "Daily Journal No 25 11-30-11
# Final", "Daily Journal No 2 1-7-09-Convening Day Final". A misspelt month
# ("Octobet", "Apri l13") or year ("1012", "208") is not read: the name then
# states no date this can use.
_WORDED = re.compile(r"(?i)(" + "|".join(MONTHS) + r")\s*(\d{1,2})(?:\s+and\s+\d{1,2})?"
                     r"(?:\s*\([^)]*\))?\s*,?\s+(\d{4})(?!\d)")
_FIGURES = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})-(\d{4}|\d{2})(?!\d)")
# The documents begin in December 1996; nothing is dated before the bills are.
FIRST_YEAR = 1989
# A document's number and the letter of a supplement: "No 8a", "HC 32",
# "SC 05A", "9B", "Daily Journal No 06", "Daily Journal #1", and the "a" of
# "No13aFebruary 21 2025" -- a letter the next word does not continue.
_NUMBER = re.compile(r"^(?i:(?:(?:daily|special\s+session)\s+journal\s+|hj_ss\s+|[hs][cj]\s+)?"
                     r"(?:no\.?\s*|#)?)0*(\d{1,3})(?!\d)([A-Za-z](?![a-z]))?")

Doc = namedtuple("Doc", "set year listed name label url date number order")
Doc.__doc__ = """One listed document, linked.

set     "hc", "hj", "sc" or "sj"
year    the year it is shown under: its date's, else the General Court's list
listed  the year list the General Court put it in
name    the name of the General Court's file, without its extension
label   the name, with the document's own date added where the name has none
url     the address the General Court's own button uses, as recorded
date    ISO, or "" where none is known
number  (number, supplement letter), for the order within a day
order   its place in the queue, which is the General Court's listed order
"""

Out = namedtuple("Out", "set year name asked")
Out.__doc__ = """One listed document that is not linked.

set     "hc", "hj", "sc" or "sj"
year    the year list the General Court put it in
name    the name of its file
asked   whether its address was ever asked for, by the queue's count of
        attempts: False for a row set aside without a request
"""


def rows(path=QUEUE):
    """The queue's rows as written, or [] where there is no queue.

    Read as utf-8-sig, so a queue saved with a byte-order mark is still a
    queue. As plain UTF-8 the mark became part of the first column's name, no
    row had a chamber, and the section left every week's page with the build
    exiting zero."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def clean(name):
    """The name of the General Court's file for a document, without the
    extension. An entity in it is the page's own escaping ("Governor&#39;s"),
    and runs of spaces are one space, as a browser would show them.

    A FILE'S OTHER SUFFIXES GO WITH ".pdf" (the R2 polish, 30 October 2026):
    "SC 36.tagged.pdf" and "... Veto Day Final.doc.pdf" were labelled "SC
    36.tagged" and "... Final.doc". Only .tagged, .doc and .docx, and only
    right before ".pdf"; every other name is shown as the General Court wrote
    it (the rule of 1 October), and the address is never touched."""
    s = html.unescape(name or "")
    s = re.sub(r"(?i)(?:\.(?:tagged|docx?))*\.pdf$", "", s.strip())
    return " ".join(s.split())


def linkable(r):
    """Whether a row's address is one to send a reader to.

    Held is fetched. Anything else with an address and no recorded error is
    listed and not yet asked for -- which is what a night's new document is
    -- so it is linked: the picker reads addresses, not files."""
    state = (r.get("state") or "").strip().lower()
    return (bool((r.get("url") or "").startswith(HOST))
            and state not in HELD_BACK and not (r.get("error") or "").strip())


def asked(r):
    """Whether a row's address was ever asked for, by the queue's count."""
    try:
        return int((r.get("attempts") or "").strip() or 0) > 0
    except ValueError:
        return False


def name_date(name, last_year=None):
    """The date a name states, ISO, or "" where it states none this can read."""
    last = last_year or build_date.today().year + 1
    for m in _WORDED.finditer(name or ""):
        d = _date(int(m.group(3)), MONTHS.index(m.group(1).capitalize()) + 1, int(m.group(2)))
        if d and FIRST_YEAR <= d.year <= last:
            return d.isoformat()
    for m in _FIGURES.finditer(name or ""):
        y = int(m.group(3))
        if y < 100:
            y += 1900 if y >= 89 else 2000
        d = _date(y, int(m.group(1)), int(m.group(2)))
        if d and FIRST_YEAR <= d.year <= last:
            return d.isoformat()
    return ""


def _date(y, m, d):
    try:
        return datetime.date(y, m, d)
    except ValueError:
        return None


def day_words(iso):
    """"September 4, 2026", the way this site writes a day (shell.date_words)."""
    return shell.date_words(datetime.date.fromisoformat(iso), "full")


def number_of(name):
    m = _NUMBER.match(clean(name))
    return (int(m.group(1)), (m.group(2) or "").upper()) if m else (0, "")


# THE SENATE CALENDAR'S MASTHEAD: the date alone on a line and the issue's
# number on the next line that is not blank,
#
#                                                          January8,2026
#                                                          No.1
#
# The number is what makes it the masthead. A date alone on a line is not
# enough: Senate Calendar 43 of 2010 opens with a stray "April 29, 2010" above
# its own date, and so do the 81 calendars before it.
_S_MAST = re.compile(r"(?im)^[ \t]*(" + "|".join(MONTHS) + r")[ \t]*(\d{1,2})[ \t]*,[ \t]*(\d{4})"
                     r"[ \t]*\r?\n(?:[ \t]*\r?\n)*[ \t]*No\.?[ \t]*(\d{1,3})(?!\d)")
_MAST_REACH = {"H": 6000, "S": 4000}    # calendar_meetings.pub_date's own


def masthead(text, chamber, number):
    """The date on a calendar's masthead, as a date, where that masthead
    carries the issue number `number` -- the document's own, from its name --
    and None where no such masthead is read.

    MEASURED ON THE CALENDARS WHOSE NAMES DO STATE A DATE (1 October 2026),
    which are the only ones a reading can be held against. The Senate: 931 of
    946 agree with the name, 10 differ and 5 give nothing; without the number,
    calendar_meetings.pub_date's first date alone on a line agreed for 837
    and differed for 106. The House, whose masthead is one line ("Concord,
    N.H.  Friday, February 27, 2009  No. 15"): 1,502 of 1,579 agree, 54
    differ -- nearly all by days, the name and the masthead being a day or a
    week apart in the General Court's own hands -- and 23 give nothing.
    """
    if not number:
        return None
    if chamber == "S":
        found = ((m.group(1), m.group(2), m.group(3), m.group(4))
                 for m in _S_MAST.finditer(text[:_MAST_REACH["S"]]))
    else:
        import calendar_meetings
        rx = re.compile(calendar_meetings.PUBDATE.pattern + r"\s*No\.?\s*(\d{1,3})(?!\d)", re.I)
        found = ((m.group(1), m.group(2), m.group(3), m.group(4))
                 for m in rx.finditer(text[:_MAST_REACH["H"]]))
    for month, day, year, issue in found:
        if int(issue) == number and month.capitalize() in MONTHS:
            return _date(int(year), MONTHS.index(month.capitalize()) + 1, int(day))
    return None


def printed_date(r, root=Path(".")):
    """The date a document prints on itself, ISO, or "".

    Read from the text beside the PDF, and only where the reading can be told
    from a misreading. A CALENDAR'S MASTHEAD MUST CARRY THE DOCUMENT'S OWN
    NUMBER (masthead), so a name with no number in it is given no date. ONE
    SITTING'S JOURNAL HAS ONE DATE, and only such a Senate journal is given
    one, by journal_days.senate_openings: "SPJ 2018 - Verbatim" is the
    Senate's whole year in one file, twenty sittings, and the first of them is
    not the document's date. Against the Senate journals whose names state a
    date that reading agrees for 370, differs for 2 -- both files that two
    listed documents share -- and gives nothing for 14. A House journal is not
    read: all but three state their date in their name, and those are two
    floor amendments filed among the journals and one name with a misprinted
    year. The date must fall in the year the General Court listed the document
    under or the one before, which is where December's are; anything else is
    a misreading and answers nothing.
    """
    path = Path(root) / (r.get("path") or "").replace("\\", "/")
    try:
        text = path.with_suffix(".txt").read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""
    got = None
    try:
        if r.get("kind") == "calendar":
            got = masthead(text, r.get("chamber") or "H", number_of(r.get("name"))[0])
        elif r.get("chamber") == "S":
            import journal_days
            sat = {day for day, _opening in journal_days.senate_openings(text)}
            got = datetime.date.fromisoformat(sat.pop()) if len(sat) == 1 else None
    except Exception:   # a date is an addition; the name stands without it
        return ""
    try:
        listed = int(r.get("year") or 0)
    except ValueError:
        return ""
    return got.isoformat() if got and got.year in (listed, listed - 1) else ""


def read(path=QUEUE, root=Path("."), today=None):
    """(docs, left_out) -- every document linked, in the picker's order, and
    the rows the General Court lists that are not linked.

    docs is a list of Doc, grouped by set in SETS' order, then by year newest
    first, then newest first within the year. left_out is a list of Out in
    the queue's order.
    """
    last = (today or build_date.today()).year + 1
    listed = [r for r in rows(path) if (r.get("chamber"), r.get("kind")) in SET_OF]
    # A FILE TWO LISTED DOCUMENTS SHARE IS READ FOR NEITHER, unless the queue
    # records which of them was fetched to it: fetch_calendar_archive names
    # the local file by the document's number, so "No 01 January 04 2012" and
    # "No 01 January 04 1012" are one file on disk, and the date it prints is
    # one document's.
    by_file = defaultdict(list)
    for r in listed:
        by_file[(r.get("path") or "").replace("\\", "/").lower()].append(r)

    def owns(r):
        rs = by_file[(r.get("path") or "").replace("\\", "/").lower()]
        if len(rs) == 1:
            return True
        took = [x for x in rs if (x.get("fetched") or "").strip()]
        return len(took) == 1 and took[0] is r

    found, left_out, taken = [], [], set()
    for i, r in enumerate(listed):
        sid = SET_OF[(r["chamber"], r["kind"])]
        name = clean(r.get("name"))
        if not linkable(r):
            left_out.append(Out(sid, (r.get("year") or "").strip(), name, asked(r)))
            continue
        # ONE ADDRESS IS ONE DOCUMENT. A row written twice is linked once, and
        # is not counted as left out either. The dated twins below are told
        # apart by name and date; a row with no date has only its address.
        if r["url"] in taken:
            continue
        taken.add(r["url"])
        date = name_date(name, last)
        added = False
        if not date and owns(r):
            date = printed_date(r, root)
            added = bool(date)
        year = date[:4] if date else (r.get("year") or "").strip()
        if not re.fullmatch(r"\d{4}", year):
            left_out.append(Out(sid, year, name, asked(r)))
            continue
        found.append(Doc(sid, year, (r.get("year") or "").strip(), name,
                         f"{name} — {day_words(date)}" if added else name,
                         r["url"], date, number_of(name), i))

    # ONCE. The same name with the same date in two of the General Court's
    # year lists is one document at two addresses; the one kept is the one
    # filed under its own date's year, else under the year after it, where
    # the General Court files December.
    seen = {}
    for d in found:
        if not d.date:
            continue
        k = (d.set, d.name.lower(), d.date)
        rank = (0 if d.listed == d.year else 1 if d.listed == str(int(d.year) + 1) else 2, d.order)
        if k not in seen or rank < seen[k][0]:
            seen[k] = (rank, d)
    once = [d for d in found
            if not d.date or seen[(d.set, d.name.lower(), d.date)][1] is d]

    # NEWEST FIRST, BY DATE AND THEN BY NUMBER. A document with no date known
    # takes its place from its number: beside the dated document of its own
    # year list numbered nearest below it, so a night's new "HC 33" is above
    # "HC 32" before anybody has read its masthead. Where a whole list is
    # undated it runs by number, which the General Court's own dropdown does
    # not ("No 9", "No 8", "No 64").
    series = defaultdict(list)
    for d in once:
        if d.date and d.number[0]:
            series[(d.set, d.listed)].append((d.number, d.date))

    def place(d):
        if d.date:
            return d.date
        near = series.get((d.set, d.listed)) or []
        if not (d.number[0] and near):
            return ""
        below = [x for x in near if x[0] <= d.number]
        return max(below)[1] if below else min(near)[1]

    order = {sid: n for n, (sid, *_rest) in enumerate(SETS)}
    once.sort(key=lambda d: (place(d), d.listed, d.number, -d.order), reverse=True)
    once.sort(key=lambda d: int(d.year), reverse=True)
    once.sort(key=lambda d: order[d.set])
    return once, left_out


def by_set(docs):
    """{set: {year: [Doc]}} in the picker's order, every set present."""
    out = OrderedDict((sid, OrderedDict()) for sid, *_rest in SETS)
    for d in docs:
        out[d.set].setdefault(d.year, []).append(d)
    return out


def bases(docs):
    """{chamber: the viewer prefix its addresses share}, read from the
    addresses themselves: everything up to and including "fileName="."""
    n = {"H": Counter(), "S": Counter()}
    for d in docs:
        cut = d.url.find("fileName=")
        if cut > 0:
            n[CHAMBER[d.set]][d.url[:cut + len("fileName=")]] += 1
    return {ch: c.most_common(1)[0][0] for ch, c in n.items() if c}


def index(docs):
    """What site/calendar/documents.json holds.

    A document is [label, tail, date]: the address is base[chamber] + tail,
    and where an address does not begin with its chamber's base the tail is
    the whole address. date is absent where none is known.

    NO DATE OF ITS MAKING. It carried one, "made", which nothing read and
    which made the file a new file every day: a list that had not changed
    was sent again with each night's deploy."""
    base = bases(docs)
    sets = []
    for sid, years in by_set(docs).items():
        b = base.get(CHAMBER[sid], "")
        ys = OrderedDict()
        for y, ds in years.items():
            ys[y] = [[d.label, d.url[len(b):] if b and d.url.startswith(b) else d.url]
                     + ([d.date] if d.date else []) for d in ds]
        sets.append({"id": sid, "chamber": CHAMBER[sid], "name": MANY[sid],
                     "one": ONE[sid], "years": ys})
    return {"base": base, "sets": sets}


def address(ix, chamber, doc):
    """The address of one of the index's documents, as the page's script
    builds it: the tail whole where it is an address already."""
    tail = doc[1]
    return tail if tail.startswith("https://") else ix["base"].get(chamber, "") + tail


def left_out_line(left_out, lang="en"):
    """The one plain line that says what is not linked, or "". It says what
    this page does, and nothing of the General Court's server: the note at
    the top of this file says why."""
    n = len(left_out)
    if not n:
        return ""
    return (say(lang, "calp.cd_left_one", "1 document the General Court lists is not linked here.")
            if n == 1 else
            say(lang, "calp.cd_left", "{n} documents the General Court lists are not linked here.",
                n=f"{n:,}"))


def left_out_why(left_out):
    """What the record holds about them, for the list page: how many were
    asked for and answered with an error, and how many were never asked."""
    yes = sum(1 for o in left_out if o.asked)
    no = len(left_out) - yes
    if yes and no:
        return (f"Of these, {yes:,} answered with an error when this site asked for "
                f"{'it' if yes == 1 else 'them'} and {no:,} {'was' if no == 1 else 'were'} "
                "set aside without being asked for.")
    one = len(left_out) == 1
    if yes:
        return f"{'It' if one else 'Each'} answered with an error when this site asked for it."
    if no:
        return f"{'It was' if one else 'They were'} set aside without being asked for."
    return ""


def summary(docs, left_out):
    """What the build prints: how many, the newest of each set, what is out."""
    first = []
    for sid, years in by_set(docs).items():
        if years:
            d = next(iter(years.values()))[0]
            first.append(f"{ONE[sid]} {d.name}"
                         + (f" ({day_words(d.date)})" if d.date and d.label != d.name else ""))
    return (f"{len(docs):,} calendars and journals in the picker"
            + (f"; newest: {'; '.join(first)}" if first else "")
            + f"; {len(left_out):,} listed and not linked")


def newest_date(docs, sid=None):
    """The latest date on a document of one set -- of any, given none -- ISO,
    or "" where no document has a date."""
    return max((d.date for d in docs if d.date and sid in (None, d.set)), default="")


def newest(docs, sid="hc"):
    """The document a set's picker opens on: the first of its newest year,
    which has no date where it is a night's new short name. None where the
    set is empty."""
    years = by_set(docs).get(sid)
    return next(iter(years.values()))[0] if years else None


def behind(docs, today, days, sid="hc"):
    """(the set's latest date, its age in days) where the list looks to have
    fallen behind the General Court's own, else None.

    THE NEWEST LISTED MAY HAVE NO DATE. The age was read off the newest DATED
    document alone, so a night's new "HC 33", listed and its text not yet
    read, would have left "the newest House Calendar listed is 4 September"
    warning on every run of a list that was current. Where the document the
    picker opens on has no date, the list has moved since the last date it
    knows and its age cannot be told: no warning."""
    first = newest(docs, sid)
    if first is None or not first.date:
        return None
    last = newest_date(docs, sid)
    age = (today - datetime.date.fromisoformat(last)).days
    return (last, age) if age > days else None


def sources(docs):
    """[(chamber's name, the General Court's own page of its calendars and
    journals)], for the chambers with a document here.

    Each is a recorded viewer address up to its folder -- the page that
    address is linked from, https://gc.nh.gov/house/calendars_journals/ --
    so it is cut from the record as a document's address is, and not made."""
    out = []
    for ch, base in sorted(bases(docs).items()):
        cut = base.rfind("/")
        if base.startswith(HOST) and cut >= len(HOST):
            out.append(("House" if ch == "H" else "Senate", base[:cut + 1]))
    return out


# ---- the box at the top of the list page ---------------------------------------
#
# WITHOUT SCRIPT IT IS LINKS: the newest of each set, at the General Court's
# address, and under the box the directory, every document of every year a
# plain link. WITH SCRIPT the row of pickers comes up above the newest; it is
# emitted hidden like every other control on this site -- a control that does
# nothing is worse than no control.
#
# UNTIL 25 NOVEMBER 2026 THIS WAS A SECTION UNDER EVERY WEEK'S SCHEDULE, with
# a heading of its own ("Calendars & Journals"), every year of every set as a
# link to that year here, and a link to this page. On this page the page's
# own heading names the box, and the directory under it is the years.

def set_name(sid, many, lang="en"):
    """A set's name for the picker (many) or for a link (one), in `lang`: the
    kind of document, which the General Court's own files are of. The
    documents' own names ("HC 32") stay as they are printed."""
    if lang == "en":
        return MANY[sid] if many else ONE[sid]
    return {("hc", True): say(lang, "calp.cd_hc_many", "House Calendars"),
            ("hc", False): say(lang, "calp.cd_hc_one", "House Calendar"),
            ("hj", True): say(lang, "calp.cd_hj_many", "House Journals"),
            ("hj", False): say(lang, "calp.cd_hj_one", "House Journal"),
            ("sc", True): say(lang, "calp.cd_sc_many", "Senate Calendars"),
            ("sc", False): say(lang, "calp.cd_sc_one", "Senate Calendar"),
            ("sj", True): say(lang, "calp.cd_sj_many", "Senate Journals"),
            ("sj", False): say(lang, "calp.cd_sj_one", "Senate Journal")}[(sid, many)]


def block_html(docs, esc=html.escape, lang="en"):
    """The box at the top of the list page, or "" where there is nothing to
    link: the row of pickers and its button (emitted hidden, for the script
    to show), the line its live status is said in, the newest of each set,
    and what a calendar and a journal are. The list page puts it under its
    heading, its line and Cite this page, and above the directory
    (build_calendar.documents_files).

    THE WORDS SAY WHAT THE RECORD HOLDS, as they did under the schedule:
    "the newest listed here", never "the newest". HOW MANY ARE NOT LINKED IS
    SAID ONCE ON THE PAGE, in the directory's own section that names them
    (list_body), and not here as well.

    WHERE THE PARAGRAPH ON THE TWO KINDS GOES: last in the box, under the
    newest of each and right above the directory it describes, where it was
    in the section -- after what a reader came for, which is the pickers.

    In another language (the Calendar in Spanish, 9 November 2026) the
    box's words and the kinds of document are that language's; a document's
    own name, which the General Court printed, is marked as English. English
    is as it was. The list page is English alone (i18n.PAGES), so nothing
    draws the box in another language today; its words keep their entries
    in each catalog for the day the page has a Spanish version."""
    sets = by_set(docs)
    # A document's name, as the General Court printed it: set apart in
    # another language, so a screen reader says it in English.
    doc_name = (lambda s: s) if lang == "en" else (lambda s: f'<span lang="en">{s}</span>')
    opt_en = "" if lang == "en" else " lang=\"en\""
    if not docs:
        return ""
    first = next((sid for sid, years in sets.items() if years), "")
    years0 = sets[first]
    y0 = next(iter(years0))
    d0 = years0[y0][0]

    latest = "".join(
        f'<li><span class="cdset">{esc(set_name(sid, False, lang))}</span> '
        f'<a class="out" href="{esc(ds[0].url)}" target="_blank" rel="noopener">'
        f'{doc_name(esc(ds[0].label))} (PDF)</a></li>'
        for sid, years in sets.items() if years
        for ds in [next(iter(years.values()))])
    # THE PICKERS OPEN ON WHAT THE GENERAL COURT'S DO: the first set, its
    # newest year, its newest document -- written here, so the button is a
    # real link to a real document before the list has been fetched.
    # ONE CHOICE EACH UNTIL THE LIST COMES, the first picker too. It was
    # written with all four kinds, and a reader who chose House Journals
    # before the list arrived was shown "House Journals, 2026, HC 32" over a
    # button that still opened the House Calendar: nothing can refill the
    # other two without the list. Now the row cannot say anything the button
    # does not do; the kinds, years and documents all arrive together.
    # NOT DISABLED WHILE THEY WAIT: a disabled control is skipped by Tab, and
    # a reader who came by keyboard a moment before the list did would be put
    # past all three.
    # THE FORM HAS NO NAME OF ITS OWN. Named by the heading of the section it
    # was in under the schedule, it was a second landmark with that name.
    pick = ('<form class="cdpick" id="cdpick" hidden>'
            '<div class="cdf"><label for="cdset">'
            + say(lang, "calp.cd_set", "Calendar or journal") + '</label>'
            f'<select id="cdset"><option value="{first}" selected>'
            f'{esc(set_name(first, True, lang))}</option>'
            '</select></div>'
            '<div class="cdf"><label for="cdyear">' + say(lang, "calp.cd_year", "Year") + '</label>'
            f'<select id="cdyear"><option value="{y0}" selected>{y0}</option>'
            '</select></div>'
            '<div class="cdf"><label for="cddoc">' + say(lang, "calp.cd_doc", "Document") + '</label>'
            f'<select id="cddoc"><option value="0" selected{opt_en}>{esc(d0.label)}</option>'
            '</select></div>'
            # THE DOCUMENT CHOSEN, IN FULL, at every width. A closed picker
            # cuts a long name off, and not only on a phone: the document
            # picker is 346px at its widest and 243px at 1024px, and "Daily
            # Journal No 03 1-21-10 State of the State Final" read "Daily
            # Journal No 03 1-21-10" there with the whole of it nowhere on
            # the page. Measured in Chrome on 1 October with the picker's
            # own font, about 167 of the 4,320 names are wider than it has
            # room for at 1024px, and about 15 at its widest.
            f'<p class="cdnow" id="cdnow">{esc(chosen_name(set_name(first, False, lang), d0.label))}</p>'
            # A NEW TAB, MARKED AS GOING OUT (the person, 7 October 2026,
            # F12), as every link to a calendar or journal is: the reader
            # keeps the list where they left it.
            f'<a class="cdopen out" id="cdopen" href="{esc(d0.url)}" '
            'target="_blank" rel="noopener" '
            f'aria-label="{esc(open_name(set_name(first, False, lang), d0.label, lang))}">'
            + say(lang, "calp.cd_open", "Open the PDF") + '</a>'
            '</form>'
            # Outside the form, so it can still speak when the list will not
            # load and the form is taken away again.
            '<p class="calhint" id="cdstat" role="status" aria-live="polite"></p>')
    # NO HEADING OF ITS OWN: the page's own (LIST_TITLE) names it. So what
    # heads the newest is a level-two heading here, as the directory's four
    # kinds are, drawn as the label it was under the section (app.css,
    # .cdocs .cdsub).
    return (f'<div class="cdocs" id="{ANCHOR}">'
            + pick
            # "LISTED HERE", because the list is as old as the queue. On
            # 1 October this headed House Calendar 32 of 4 September as "the
            # newest of each", and the example the person gave when asking
            # for the pickers was No 35 of 25 September. Each is shown with
            # its date, and the list page says how far the list reaches.
            + '<h2 class="cdsub" id="cdnew">' + say(lang, "calp.cd_newest", "The newest listed here")
            + '</h2>'
            f'<ul class="cdlatest" aria-labelledby="cdnew">{latest}</ul>'
            '<p class="src">' + say(lang, "calp.cd_src", "The calendar is what each chamber "
            "publishes ahead of time: hearings, committee reports and what the next session will "
            "take up. The journal is the record of a session day. These open the General "
            "Court&rsquo;s own files.") + '</p>'
            + '</div>')


# THE PICKER'S SCRIPT IN ANOTHER LANGUAGE (the Calendar in Spanish, 9 November
# 2026; since 25 November the pickers are on the list page alone, which is
# English, so no page carries it until that page has a Spanish version):
# PICKER_JS as it was, with the pairs below put over it by picker_js(),
# so the English page's script is the English script to the byte. Each pair is
# (the text of PICKER_JS, what replaces it); a pair that does not apply once
# stops the build. The words are tr() calls: the page carries the language's
# own (i18n.page_words), and a word that has none is said in English.
PICKER_ES = [
    (r"""  function setOf(ix,id){""", r"""  var LANG=G.GR_LANG||"en", ES=LANG==="es";
  // A set's kind of document in the page's language; its documents' own names are the General Court's.
  function nm(s,many){
    if(!ES) return many?s.name:s.one;
    return s.id==="hc"?(many?tr("calp.cd_hc_many","House Calendars"):tr("calp.cd_hc_one","House Calendar"))
      :s.id==="hj"?(many?tr("calp.cd_hj_many","House Journals"):tr("calp.cd_hj_one","House Journal"))
      :s.id==="sc"?(many?tr("calp.cd_sc_many","Senate Calendars"):tr("calp.cd_sc_one","Senate Calendar"))
      :s.id==="sj"?(many?tr("calp.cd_sj_many","Senate Journals"):tr("calp.cd_sj_one","Senate Journal"))
      :(many?s.name:s.one);
  }
  function setOf(ix,id){"""),
    (r"""            chosen:doc?set.one+", "+doc[0]:"",
            name:doc?"Open the PDF: "+set.one+", "+doc[0]+", at the General Court":"Open the PDF",
            count:n+" "+(n===1?set.one:set.name)+" for "+y+
                  (ys.length>1?"; the list runs "+ys[ys.length-1]+" to "+ys[0]+".":".")};""",
     r"""            chosen:doc?nm(set,false)+", "+doc[0]:"",
            name:doc?tr("calp.cd_open_named","Open the PDF: {name}, at the General Court",
                        {name:nm(set,false)+", "+doc[0]}):tr("calp.cd_open","Open the PDF"),
            count:tr("calp.cd_count","{n} {what} for {year}",{n:n,what:nm(set,n!==1),year:y})+
                  (ys.length>1?tr("calp.cd_runs","; the list runs {from} to {to}.",
                                  {from:ys[ys.length-1],to:ys[0]}):".")};"""),
    (r"""s.sets.map(function(x){ return x.name; })""", r"""s.sets.map(function(x){ return nm(x,true); })"""),
    (r"""say("The list of documents could not be loaded here. Every year is linked below.")""",
     r"""say(tr("calp.cd_fail","The list of documents could not be loaded here. Every year is linked below."))"""),
    (r"""say("Loading the list of documents.")""", r"""say(tr("calp.cd_loading","Loading the list of documents."))"""),
]


def picker_js(lang="en"):
    """PICKER_JS for a page in `lang`: itself for English."""
    if lang == "en":
        return PICKER_JS
    js = PICKER_JS
    for old, new in PICKER_ES:
        assert js.count(old) == 1, f"PICKER_JS no longer holds, once: {old[:60]!r}"
        js = js.replace(old, new)
    return js


def chosen_name(one, label):
    """The document the pickers are on, said whole: "House Calendar, HC 32"."""
    return f"{one}, {label}"


def open_name(one, label, lang="en"):
    """The button's accessible name, which begins with the words it shows."""
    return say(lang, "calp.cd_open_named", "Open the PDF: {name}, at the General Court",
               name=chosen_name(one, label))


def _canon(path):
    """shell.canon, for the two addresses this writes: the host serves a
    page without its extension."""
    return path[:-5] if path.endswith(".html") else path


# ---- the list page --------------------------------------------------------------

LIST_TITLE = "Calendars and Journals of the General Court"

# Opens the year an address names -- /calendar/documents#hc-2019 -- which a
# browser will not do for a <details> on its own.
LIST_JS = IJ.script("calendar_documents.list")


def span(docs):
    """(first year, last year) of everything linked, as integers."""
    ys = [int(d.year) for d in docs]
    return (min(ys), max(ys)) if ys else (0, 0)


def list_lead(docs, esc=html.escape):
    """What the list page says of itself, under its heading. Three things it
    said on 1 October were not so, and each is now what the record holds:

    THE NAME is the file's, with the document's printed date after a dash
    where the name has none -- not "as the General Court names it", whose own
    label for its newest document is fuller than the file's name.
    THE YEAR is the date's for a document with a date and the General Court's
    list for one without, and the page says how many are without: it said "a
    document is under the year of its date" of all of them, and 645 of 4,320
    had none.
    HOW FAR IT REACHES: the latest date on any document here, and where a
    newer one is. The list is as old as archive/queue.csv, which nothing
    refreshes at night, so "the newest" is the newest listed and may not be
    the newest there is. The General Court's own two pages have the rest, at
    the addresses its documents here are linked from (sources)."""
    first, last = span(docs)
    undated = sum(1 for d in docs if not d.date)
    said = [f"{len(docs):,} documents, {first} to {last}, each a link to the General "
            "Court&rsquo;s own file, under that file&rsquo;s name. A date after a dash "
            "is the one the document prints, added where the name has none."]
    said.append("Each is under the year of its date, newest first"
                + (f"; the {undated:,} with no date known are under the year the General "
                   "Court lists them for." if undated else "."))
    latest = newest_date(docs)
    if latest:
        where = " and ".join(f'<a href="{esc(url)}" rel="noopener">the {esc(name)}</a>'
                             for name, url in sources(docs))
        said.append(f"The latest date on a document here is {day_words(latest)}"
                    + (f"; anything published since is on the General Court&rsquo;s own "
                       f"pages for {where}." if where else "."))
    return " ".join(said)


def list_body(docs, left_out, esc=html.escape):
    """(heading, lead, body) of site/calendar/documents.html: four sections,
    a year to a <details>, the newest year of each open, every document a
    plain link; then the documents listed and not linked, named. The page
    has the box of pickers (block_html) between its lead and this body,
    which is the directory as it was before the box came up to the top
    (build_calendar.documents_files)."""
    sets = by_set(docs)
    here = _canon(LIST_PATH)
    jump = " &middot; ".join(f'<a href="{here}#{sid}">{esc(MANY[sid])}</a>'
                             for sid, years in sets.items() if years)
    lead = list_lead(docs, esc)
    # The four kinds, on a line of their own: at the end of the lead they ran
    # on from its links to the General Court's two pages, "the House and the
    # Senate. House Calendars", links out and links down side by side.
    body = [f'<p class="src">{jump}</p>']
    for sid, years in sets.items():
        if not years:
            continue
        n = sum(len(v) for v in years.values())
        body.append(f'<h2 id="{sid}">{esc(MANY[sid])} <span class="cdn">{n:,}</span></h2>')
        for i, (y, ds) in enumerate(years.items()):
            body.append(f'<details class="cdyear" id="{sid}-{y}"{" open" if i == 0 else ""}>'
                        f'<summary>{y} <span class="cdn">{len(ds)}</span></summary>'
                        '<ul class="cdlist">'
                        + "".join(f'<li><a class="out" href="{esc(d.url)}" '
                                  'target="_blank" rel="noopener">'
                                  f'{esc(d.label)} (PDF)</a></li>' for d in ds)
                        + "</ul></details>")
    if left_out:
        groups = OrderedDict()
        for o in left_out:
            groups.setdefault((o.set, o.year), []).append(o.name)
        why = left_out_why(left_out)
        body.append(f'<h2 id="{NOT_LINKED}">Listed by the General Court and not linked here '
                    f'<span class="cdn">{len(left_out):,}</span></h2>'
                    f'<p class="src">{esc(left_out_line(left_out))} '
                    + (f"{esc(why)} " if why else "")
                    + "They are named here by their files&rsquo; names, under the year the "
                    "General Court lists them for.</p>"
                    '<ul class="cdlist cdout">'
                    + "".join(f'<li><span class="cdset">{esc(MANY[sid])}, {esc(year)}</span> '
                              f'{esc(", ".join(names))}</li>'
                              for (sid, year), names in groups.items())
                    + "</ul>")
    return LIST_TITLE, lead, "".join(body)


# ---- the pickers' script ------------------------------------------------------------
#
# Shaped as build_calendar.WEEK_JS is: a core of plain functions over the
# index, which preflight runs in node, and below it the part that touches the
# page and does no reasoning of its own. No string spans a line, so
# build_calendar.lean_js can take the comments out.
PICKER_JS = IJ.script("calendar_documents.picker")


def main():
    docs, left_out = read()
    if not docs:
        print(f"no calendars or journals: {QUEUE} is not here, or lists nothing to link")
        return 1
    print(summary(docs, left_out))
    for sid, years in by_set(docs).items():
        ys = list(years)
        dated = sum(1 for v in years.values() for d in v if d.date)
        n = sum(len(v) for v in years.values())
        print(f"  {MANY[sid]:16} {n:5,} in {len(ys)} years"
              + (f", {ys[-1]}-{ys[0]}" if ys else "") + f"; {n - dated:,} with no date known")
    blob = json.dumps(index(docs), ensure_ascii=False, separators=(",", ":"))
    print(f"  the index is {len(blob.encode('utf-8')):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
