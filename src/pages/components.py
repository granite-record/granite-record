#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.5
"""
The site's components, in Python: what the builders draw a person, a
committee, a chip, a date and a time with, and the words they say.

    import components as C
    C.date_words("2026-02-19", "full")     # "February 19, 2026"
    C.clock("13:30")                       # "1:30 PM", a no-break space before PM
    C.pchip(member)                        # one legislator, as every page draws one
    C.chip("Public Hearing", "calkind k-hearing")   # every other chip, in one shape
    C.title_words("INEXPEDIENT TO LEGISLATE")      # "Inexpedient to Legislate"
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


# ONE CHIP, IN TWO SIZES (the component plan's step 3, approved 9 October
# 2026; the person's rule of 22 September 2026, that every kind of chip shares
# the legislator chip's shape and placement). A bill's status was a box in
# its own ink, a meeting's kind a pill with an inset edge, a version a pine
# tint in capitals, the finder's kind a 13px outlined tag in capitals, the
# sign-ins pills, a member's vote outcome a bare coloured word: six shapes
# for one idea, each from its own line of markup in one of two languages.
# Every one of them is chip() now, here and in components.js, and app.css
# draws a chip one way -- the person chip's frame (3px corners, a 1px edge,
# a 3px bar down the left in the chip's own ink) at 14px, or 16px in a head
# -- with a family's class to colour it. The person chip is pchip, above,
# whose frame is the same rule.
def chip(word, cls="", size="s"):
    """A word in the site's one chip: a bill's status, a meeting's kind, a
    vote's result, a party's letter, or a neutral word for anything else.

        chip("Became Law", "cstat s-law", "m")
        -> '<span class="chip chip-m cstat s-law">Became Law</span>'

    `cls` is the classes it takes beside its own, separated by spaces: the
    family that colours it (chips.json's s-law and the rest, a meeting
    kind's k-hearing and the rest, pass or fail, a party's pt-R) and the
    hook a page places it by (cstat, calkind, rcres); with no family it is
    the neutral chip. `size` is "m" in a head, the bill card's, and the
    chip is "s" otherwise, the size everywhere else. The word is drawn as
    it comes: its case is decided where the word is made -- title_words, for
    a record's capitals -- never here."""
    names = ["chip"] + (["chip-m"] if size == "m" else []) + [
        c for c in str(cls or "").split(" ") if c]
    return f'<span class="{esc(" ".join(names))}">{esc(word)}</span>'


def title_words(s):
    """A record's words as a chip says them, in Title Case, the case the
    person set for every chip's words: "INEXPEDIENT TO LEGISLATE" is
    "Inexpedient to Legislate", the bill text's "As amended by the house"
    is "As Amended by the House", "Not ratified" is "Not Ratified".

    For words a record holds in a case of its own -- a committee's
    recommendation the clerk typed in capitals, a version written three
    ways -- and only there: a word made here is written in its case where it
    is made, and nothing recases it on display (C8 of the component plan).
    The small words a title keeps in lower case after its first word are
    meeting_kinds.json's "small", the same that a kind of meeting's title
    keeps. A word with a figure in it is left as it is ("4/28/10",
    "1429S"), and so, where the words are not all capitals, is a word in
    capitals ("RSA"), which is then an abbreviation rather than a shout.

    THE RECORD'S ABBREVIATIONS STAY IN CAPITALS, whatever case the record
    wrote them in: chips.json's "capitals", the kinds of bill, a fiscal
    note's FN and its suffixes, the calendars' CC and RC, TBD. In a shout
    nothing marks them, so "INEXPEDIENT TO LEGISLATE HB 143" came out
    "Inexpedient to Legislate Hb 143" -- a bill's number misspelt on its
    own Reports tab -- and "FOR MAR 5 CC" "for Mar 5 Cc", and the version
    "Fn - as introduced" "Fn - As Introduced" (the review of steps 0-3, 9
    October 2026, reading every recommendation and version the built bills
    carry). And a small word straight after a dash starts what follows, so
    it takes a capital as a title's first word does: "Fn - a - as
    introduced" is "FN - A - As Introduced", the bill's FN-A."""
    s = "" if s is None else str(s)
    shout = not re.search(r"[a-z]", s)
    small, caps = WORDBOOK["meeting_kinds"]["small"], WORDBOOK["chips"]["capitals"]
    words, out = s.split(" "), []
    for i, w in enumerate(words):
        if w.upper() in caps:
            out.append(w.upper())
            continue
        if re.search(r"[0-9]", w) or (
                not shout and re.fullmatch(r"[^a-z]*[A-Z][^a-z]*[A-Z][^a-z]*", w)):
            out.append(w)
            continue
        low = w.lower()
        out.append(low if i and words[i - 1] not in TW_DASHES and low in small else re.sub(
            r"^([^A-Za-z]*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), low))
    return " ".join(out)


# A word that is a dash alone, after which title_words starts again.
TW_DASHES = ("-", "–", "—")


# ICONS: THE PROTOTYPE KIT'S DRAWINGS (the polish's second round, 9 October
# 2026, private/design/polish/proto/css/kit.css), drawn for this project on a
# 24-unit grid with a 1.75 stroke and round ends; report and share were drawn
# the same way for Polish 1, at the person's asking ("add a share button
# alongside the report button with the same thing in mind"). Each is a
# picture beside a word, never the only name of its control: aria-hidden, so
# a screen reader reads the control's own text and not "image", and
# currentColor, so it takes the ink of whatever holds it in both themes.
# app.css sizes it (.icon) in rem with the text beside it.
ICON_PAINT = ('fill="none" stroke="currentColor" stroke-width="1.75" '
              'stroke-linecap="round" stroke-linejoin="round"')
ICONS = {
    # the sections: the nav's tabs and the home page's cards
    "bill": ('<path d="M6.25 2.75h7.75l4.25 4.25v14.25H6.25z"/><path d="M13.75 2.75v4.5h4.5"/>'
             '<path d="M9 11.75h6.5M9 15h6.5M9 18.25h4"/>'),
    "person": ('<circle cx="12" cy="7.75" r="3.75"/>'
               '<path d="M4.5 20.75c.9-4.25 3.8-6.5 7.5-6.5s6.6 2.25 7.5 6.5"/>'),
    "committee": ('<circle cx="6.25" cy="8.25" r="2.25"/><circle cx="12" cy="6.5" r="2.25"/>'
                  '<circle cx="17.75" cy="8.25" r="2.25"/><path d="M2.75 13.25h18.5"/>'
                  '<path d="M5.25 13.25v7.5M18.75 13.25v7.5"/><path d="M8.5 17h7"/>'),
    "book": ('<path d="M12 6.75C9.6 5 6.6 4.6 3.25 5.25v13.5c3.35-.65 6.35-.25 8.75 1.5 '
             '2.4-1.75 5.4-2.15 8.75-1.5V5.25C17.4 4.6 14.4 5 12 6.75z"/><path d="M12 6.75v13.5"/>'),
    "calendar": ('<rect x="3.5" y="4.75" width="17" height="16" rx="1.5"/>'
                 '<path d="M3.5 9.75h17M8 2.75v4M16 2.75v4"/>'
                 '<path d="M7.25 13.25h3v3h-3z" fill="currentColor"/>'),
    # a page's actions
    "cite": ('<path fill="currentColor" stroke="none" d="M4.5 18v-4.6c0-3.4 1.7-6 4.6-7.4l.9 1.6c-1.7 '
             '1-2.6 2.4-2.8 4.2H10V18zM13.5 18v-4.6c0-3.4 1.7-6 4.6-7.4l.9 1.6c-1.7 1-2.6 2.4-2.8 '
             '4.2H19V18z"/>'),
    "follow": ('<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.75h-15z"/>'
               '<path d="M10 20.75a2 2 0 0 0 4 0"/>'),
    "print": ('<path d="M7 9V3.75h10V9"/><path d="M7 17.25H4.25v-7.5h15.5v7.5H17"/>'
              '<path d="M7 14h10v6.25H7z"/>'),
    "testify": ('<path d="M4.25 5.25h15.5v10.5H10.5l-4.5 3.75v-3.75H4.25z"/>'
                '<path d="M8 9.25h8M8 12.25h5"/>'),
    "report": '<path d="M5.5 21.25V3.5"/><path d="M5.5 4.25h12.25L15 8.75l2.75 4.5H5.5"/>',
    "share": ('<path d="M12 15V3.25"/><path d="M7.75 7.5 12 3.25l4.25 4.25"/>'
              '<path d="M8.75 10.75h-3v10h12.5v-10h-3"/>'),
    # the controls that already carried a drawing or a character of their own
    "search": '<circle cx="10.5" cy="10.5" r="6.25" stroke-width="2"/><path d="M15.25 15.25l5 5" stroke-width="2"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18" stroke-width="2"/>',
    "play": '<path fill="currentColor" stroke="none" d="M8 5.5v13l10.5-6.5z"/>',
}


def icon(name):
    """One of ICONS as an inline SVG, or "" for a name it does not hold.

    Pure, like every helper here: the same markup in components.js's icon(),
    which preflight holds byte for byte. The control it sits in carries the
    words -- a visible label, or an aria-label where the drawing stands alone
    -- and preflight fails a page that gives a drawing no words beside it."""
    inner = ICONS.get(name) if isinstance(name, str) else None
    if inner is None:
        return ""
    return (f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" '
            f'{ICON_PAINT}>{inner}</svg>')
