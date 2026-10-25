#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.17
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
# date, and the docket's own lines as the clerk wrote them. (The home page's
# floor session titles, "August 19th, 2026", were one until 25 October 2026,
# when the audit's M8 replaced them with a line in date_words' medium form.)
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DATE_FORMS = ("long", "full", "medium", "short", "day", "wkd")


def date_words(iso, form="medium", lang="en"):
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
    if lang == "es":
        return _date_words_es(d, form)
    month, mon, wd = MONTHS[d.month - 1], MONTHS[d.month - 1][:3], WEEKDAYS[d.weekday()]
    return {"long": f"{wd}, {month} {d.day}, {d.year}",
            "full": f"{month} {d.day}, {d.year}",
            "short": f"{mon} {d.day}",
            "day": f"{wd}, {month} {d.day}",
            "wkd": f"{wd[:3]}, {mon} {d.day}"}.get(form, f"{mon} {d.day}, {d.year}")


# IN SPANISH, DAY FIRST, AS SPANISH WRITES A DATE (23 October 2026; i18n.py).
# The person's month-first rule (D6) is the English page's; a Spanish page
# says "19 de febrero de 2026", with the months and days in lower case and
# the short forms the Real Academia's ("feb.", "jue."). components.js's
# dateWords() says the same where the page is Spanish (window.GR_LANG).
#     long    jueves, 19 de febrero de 2026
#     full    19 de febrero de 2026
#     medium  19 feb. 2026
#     short   19 feb.
#     day     jueves, 19 de febrero
#     wkd     jue., 19 feb.
MONTHS_ES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre")
MONS_ES = ("ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.",
           "ago.", "sept.", "oct.", "nov.", "dic.")
WEEKDAYS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
WKDS_ES = ("lun.", "mar.", "mié.", "jue.", "vie.", "sáb.", "dom.")


def _date_words_es(d, form):
    """date_words' forms of the date `d`, in Spanish."""
    month, mon = MONTHS_ES[d.month - 1], MONS_ES[d.month - 1]
    wd, wk = WEEKDAYS_ES[d.weekday()], WKDS_ES[d.weekday()]
    return {"long": f"{wd}, {d.day} de {month} de {d.year}",
            "full": f"{d.day} de {month} de {d.year}",
            "short": f"{d.day} {mon}",
            "day": f"{wd}, {d.day} de {month}",
            "wkd": f"{wk}, {d.day} {mon}"}.get(form, f"{d.day} {mon} {d.year}")


def _date_span_es(a, b, form):
    """date_span in Spanish: "5–11 de octubre de 2026", "28 de septiembre –
    4 de octubre de 2026", "28 de diciembre de 2026 – 3 de enero de 2027";
    with form "medium", "9–13 feb. 2026" and "28 sept. – 2 oct. 2026"."""
    fa, fb = date_words(a, form, "es"), date_words(b, form, "es")
    if fa == str(a) or fb == str(b):
        return f"{fa} – {fb}"
    ya, yb = str(a)[:4], str(b)[:4]
    if ya != yb:
        return f"{fa} – {fb}"
    if form == "medium":
        (da, ma, _y), (db, mb, _z) = fa.split(" "), fb.split(" ")
        return f"{da}–{db} {mb} {yb}" if ma == mb else f"{da} {ma} – {db} {mb} {yb}"
    ma, mb = str(a)[5:7], str(b)[5:7]
    da, db = int(str(a)[8:10]), int(str(b)[8:10])
    if ma == mb:
        return f"{da}–{db} de {MONTHS_ES[int(mb) - 1]} de {yb}"
    return f"{da} de {MONTHS_ES[int(ma) - 1]} – {db} de {MONTHS_ES[int(mb) - 1]} de {yb}"


def date_span(a, b, form="full", lang="en"):
    """Two days as one span, month first: "October 5–11, 2026", "September 28
    – October 4, 2026", "December 28, 2026 – January 3, 2027"; one day where
    the two are the same. components.js's dateSpan() says the same.

    `form` "medium" is the same span with the months short, "Feb 9–13, 2026"
    or "Sep 28 – Oct 2, 2026": what the Calendar's pager says under Previous
    Week and Next Week, where the room is half a column (9 October 2026)."""
    if str(a)[:10] == str(b)[:10]:
        return date_words(a, form, lang)
    if lang == "es":
        return _date_span_es(str(a)[:10], str(b)[:10], form if form in ("full", "medium") else "full")
    fa, fb = date_words(a, form), date_words(b, form)
    if fa == str(a) or fb == str(b):
        return f"{fa} – {fb}"
    (ma, da, ya), (mb, db, yb) = (x.replace(",", "").split() for x in (fa, fb))
    if ya != yb:
        return f"{fa} – {fb}"
    if ma != mb:
        return f"{ma} {da} – {mb} {db}, {yb}"
    return f"{ma} {da}–{db}, {yb}"
# DATEWORDS:END


def clock(t, lang="en"):
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
    # In Spanish, "1:30 p. m.", the Real Academia's abbreviation, held
    # together by no-break spaces as AM and PM are.
    if lang == "es":
        return f"{h % 12 or 12}:{m.group(2)}\u00a0{'a.' if h < 12 else 'p.'}\u00a0m."
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


def cmte_title(name, chamber=""):
    """A committee's whole name for a sentence: components.js's cmteTitle.
    "Housing" of the House is "House Committee on Housing"; a name that says
    "Committee" itself takes only the chamber -- "House Special Committee on
    Housing", where the page said "The House Committee on Special Committee
    on Housing" (16 October 2026) -- and one that already names its chamber
    is left as it is. Text, not markup: the caller escapes it."""
    name, chamber = str(name or ""), str(chamber or "")
    if chamber and name.lower().startswith(chamber.lower() + " "):
        return name
    if re.search(r"\bcommittee\b", name, re.I):
        return f"{chamber} {name}".strip()
    return f"{chamber} Committee on {name}".strip()


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
    # A NAME IS NOT TRANSLATED (23 October 2026): a browser's translation
    # leaves the chip's name and seat alone and translates its role.
    return (f'<span class="mchip p-{esc(code)}" translate="no">{inner}'
            + (f' <i translate="yes">{esc(role)}</i>' if role else "") + "</span>")


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
    "law": ('<path d="M12 3.25v17.5M7.75 20.75h8.5M4.75 6.75h14.5M12 3.25v3.5"/>'
            '<path d="M4.75 6.75 2.25 13a2.5 2.5 0 0 0 5 0zM19.25 6.75 16.75 13a2.5 2.5 0 0 0 5 0z"/>'),
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
    # the footer's language choice (24 October 2026)
    "globe": ('<circle cx="12" cy="12" r="8.75"/><path d="M3.25 12h17.5"/>'
              '<path d="M12 3.25c2.4 2.4 3.6 5.3 3.6 8.75s-1.2 6.35-3.6 8.75c-2.4-2.4-3.6-5.3-3.6-8.75'
              's1.2-6.35 3.6-8.75z"/>'),
    # the Resources hub's topics (build_civics.badge; 24 October 2026)
    "capitol": '<path d="M3.25 20.75h17.5M4.25 13.25h15.5"/><path d="M5.75 20.75v-7.5M9.25 20.75v-7.5M14.75 20.75v-7.5M18.25 20.75v-7.5"/><path d="M6.75 13.25a5.25 5.25 0 0 1 10.5 0"/><path d="M12 8V3.25h2.5"/>',
    "ballot": '<rect x="3.75" y="11.25" width="16.5" height="9.5" rx="1"/><path d="M7.75 11.25v-7.5h8.5v7.5"/><path d="M10 7.5l1.5 1.5 3-3"/><path d="M8.5 15.75h7"/>',
    "car": '<path d="M4.75 12.25 6.4 7.6a1.5 1.5 0 0 1 1.4-1h8.4a1.5 1.5 0 0 1 1.4 1l1.65 4.65"/><rect x="3.25" y="12.25" width="17.5" height="5" rx="1.25"/><path d="M6 17.25v2.5M18 17.25v2.5"/><circle cx="7.25" cy="14.75" r=".75"/><circle cx="16.75" cy="14.75" r=".75"/>',
    "heart": '<path d="M12 20.25s-7.75-4.6-7.75-10.1A4.15 4.15 0 0 1 12 7.6a4.15 4.15 0 0 1 7.75 2.55c0 5.5-7.75 10.1-7.75 10.1z"/>',
    "house": '<path d="M3.5 11 12 4l8.5 7"/><path d="M5.75 9.25v11.5h12.5V9.25"/><path d="M10 20.75v-5.5h4v5.5"/>',
    "pin": '<path d="M12 21s-6.25-6.1-6.25-11a6.25 6.25 0 0 1 12.5 0c0 4.9-6.25 11-6.25 11z"/><circle cx="12" cy="10" r="2.25"/>',
    "columns": '<path d="M3.25 20.75h17.5M4.25 9.25h15.5L12 4z"/><path d="M6.75 9.25v11.5M10.25 9.25v11.5M13.75 9.25v11.5M17.25 9.25v11.5"/>',
    "chart": '<path d="M3.75 20.25h16.5"/><path d="M6.75 20.25v-6M11 20.25V8.75M15.25 20.25v-9M19.25 20.25V5.75"/>',
    "map": '<path d="M3.75 6.25 9 4l6 2.25 5.25-2.25v13.75L15 20l-6-2.25-5.25 2.25z"/><path d="M9 4v13.75M15 6.25V20"/>',
    "idcard": '<rect x="2.75" y="5.25" width="18.5" height="13.5" rx="1.5"/><circle cx="8.5" cy="11" r="2"/><path d="M5.5 15.75c.6-1.5 1.6-2.25 3-2.25s2.4.75 3 2.25"/><path d="M14 10h4.5M14 13.25h3"/>',
    "gavel": '<path d="M9.4 7.25 12.25 4.4l6.35 6.35-2.85 2.85z"/><path d="M12.6 10.4 4.75 18.25"/><path d="M13 20.75h7.5"/>',
    "box": '<path d="M3.75 8.25 12 4.25l8.25 4v9.5L12 21.75l-8.25-4z"/><path d="M3.75 8.25 12 12.25l8.25-4M12 12.25v9.5"/><path d="M7.9 6.25l8.25 4"/>',
    "signpost": '<path d="M12 3.25v17.5M8.75 20.75h6.5"/><path d="M12 5.25h6.5l2 2-2 2H12"/><path d="M12 11.25H5.5l-2 2 2 2H12"/>',
    "grid": '<rect x="4" y="4" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1"/>',
    # The outdoors: fishing, hunting and boating (25 October 2026).
    "tree": '<path d="M12 3.25 7 9.75h2.75L5.5 15.25h13l-4.25-5.5H17z"/><path d="M12 15.25v5.5M9.25 20.75h5.5"/>',
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


# ============================================================================
# POLISH 2: THE RECORD PAGES' COMPONENTS (ws/records, 10 October 2026). The
# component plan's steps 4 to 8, approved 9 October 2026: the bill in three
# sizes (card, row, mention), the dated rail, a person in a sentence, a term
# for its popover, the vote words, the record head and the W4 section. Each
# has its twin under the same name in components.js, held to one answer by
# _components_agree.
# ============================================================================

def card_word(word, passage=""):
    """A bill CARD's chip word: the short form of a stage the bill page's
    chip says at length (D18, approved by the person on 10 October 2026;
    chips.json's "short"). "Passed one chamber" and "In progress" name the
    chamber the bill passed, from its passage ("Hpp--": the House passed,
    then the Senate); a word with no short form is its own in Title Case.

        card_word("Retained in committee")            -> "Retained"
        card_word("Passed one chamber", "Hp---")      -> "Passed House"
        card_word("Became Law")                       -> "Became Law"
    """
    s = "" if word is None else str(word)
    ch = WORDBOOK["chips"]
    if s in ch["short"]:
        return ch["short"][s]
    for pre, short in ch["short_prefix"]:
        if s.startswith(pre):
            return short
    p = str(passage or "")
    names = {"H": "House", "S": "Senate"}
    if s in ch["short_passed"] and p[:1] in names and "p" in p[1:3]:
        other = "S" if p[:1] == "H" else "H"
        return "Passed " + names[other if p[2:3] == "p" else p[:1]]
    return title_words(s)


def bill_mention(n, href, year=""):
    """A bill named in running words (the plan's "mention"): its number as
    an underlined link, no chip and no preview (D12), the year beside it
    where the page spans terms. "HB 652-FN", "HB 1681 (2026)"."""
    y = f' <span class="byr">({esc(year)})</span>' if year else ""
    return f'<a class="bmention" href="{esc(href)}" translate="no">{esc(n)}{y}</a>'


def bill_row(r):
    """A bill as one row (the plan's "row"): its number and year in a fixed
    column as the link, the title in the serif, the chip at the right where
    the heading above does not already say the outcome, and a line for what
    happened here. `r`: {n, year, href, title, word, cls, line}."""
    chp = chip(r.get("word"), "cstat " + str(r.get("cls") or "")) if r.get("word") else ""
    year = f'<span class="byr">({esc(r.get("year"))})</span>' if r.get("year") else ""
    line = f'<span class="brline">{r.get("line")}</span>' if r.get("line") else ""
    return (f'<div class="brow"><a class="brnum" href="{esc(r.get("href"))}" translate="no">'
            f'{esc(r.get("n"))}{year}</a><span class="brtitle" translate="no">{esc(r.get("title"))}</span>'
            f'{chp}{line}</div>')


def bill_byline(sponsor, committees, topic, term, codes):
    """A card's line of who and where: the prime sponsor as the person chip
    (D14), each committee as a mention of its page (cmte_link), and the
    subject. `sponsor` is a member as pchip takes one, or None; `topic` is
    "" where the subject is the topic model's refusal ("Miscellaneous"),
    which the caller knows and this does not."""
    parts = ([pchip(sponsor)] if sponsor else []) + [
        cmte_link(c, term, codes) for c in (committees or []) if c] + (
        [esc(topic)] if topic else [])
    return ' <span class="cdot" aria-hidden="true">&middot;</span> '.join(parts)


def bill_card(c):
    """A bill as a card (the plan's C5, with the person's feedback of
    9 October 2026: a card, not a row, on member, committee and session-day
    pages). The number and year are the link to the bill's own page, the
    chip is at the right, then the title, the byline, the line for what
    happened at this meeting or on this day, and the dated rail.

    `c`: {id, href, n, year, word, cls (the chip's family), title, byline,
    notes, line, rail, open, body, card (more classes)}. Where `open` is
    true or false the title is the button that opens the card in place and
    `body` is what it opens; where it is null the card is drawn whole, for
    a page built ahead (a session day), and the title is text. The head is
    no longer a button holding links (C5)."""
    opened = c.get("open")
    year = f'<span class="cyear"> ({esc(c.get("year"))})</span>' if c.get("year") else ""
    chp = chip(c.get("word"), "cstat " + str(c.get("cls") or ""), "m") if c.get("word") else ""
    title = (f'<div class="ctitle" translate="no">{esc(c.get("title"))}</div>' if opened is None else
             f'<button type="button" class="ctitle" aria-expanded="{"true" if opened else "false"}"'
             f' translate="no">{esc(c.get("title"))}</button>')
    meta = f'<div class="cmeta">{c.get("byline")}</div>' if c.get("byline") else ""
    line = f'<div class="cline">{c.get("line")}</div>' if c.get("line") else ""
    body = ("" if c.get("body") is None else
            f'<div class="cbody"{"" if opened else " hidden"}>{c.get("body")}</div>')
    more = f' {c.get("card")}' if c.get("card") else ""
    # A bill with no page of its own to go to (no href) has its number as
    # text: a link to nowhere is a link that fails.
    num = (f'<a class="cnum" href="{esc(c.get("href"))}" translate="no">{esc(c.get("n"))}{year}</a>'
           if c.get("href") else f'<span class="cnum" translate="no">{esc(c.get("n"))}{year}</span>')
    return (f'<article class="card{" open" if opened else ""}{more}" data-id="{esc(c.get("id"))}">'
            f'<div class="chead"><div class="crow">{num}{chp}</div>{title}{meta}'
            f'{c.get("notes") or ""}{line}{c.get("rail") or ""}</div>{body}</article>')


# THE DATED RAIL, in both languages since 10 October 2026 (it was app.js's
# datedRail, moved here unchanged in what it draws and says, so a session
# day built ahead draws a card's rail as a bill's page does). A stop is
# {stop, mark, date, short, say}, or an index row's ["Hp", "2026-03-11",
# "231–99, amended"]: the stop's letter and its mark, its day, its words.
RAIL_STOP = {"I": "Introduced", "H": "House", "S": "Senate", "G": "Governor", "L": "Law",
             "V": "Voters"}
# The wave of interim study, drawn rather than typed so it centres at any size.
RAIL_WAVE = ('<svg class="wave" viewBox="0 0 12 12" aria-hidden="true" focusable="false">'
             '<path d="M1.7 7.4C2.9 4.8 4.5 4.6 6 6.1s3.1 1.4 4.3-1.2" fill="none" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>')
RAIL_MARK = {"p": "✓", "x": "✕", "s": RAIL_WAVE}
RAIL_SAY = {"p": "passed", "h": "is here now", "x": "stopped here", "-": "never reached",
            "s": "sent to interim study", "t": "on the table"}
RAIL_SAY_DIED = {"t": "laid on the table"}
RAIL_SAID = {"s": "interim study", "t": "tabled"}
RAIL_CLASS = {"-": "o", "s": "istudy", "t": "ontable"}
RAIL_MON = tuple(m[:3] for m in MONTHS)
_RAIL_DAY = re.compile(r"\b(" + "|".join(RAIL_MON) + r") (\d{1,2}), (\d{4})\b")
_RAIL_MONTH = re.compile(r"\b(" + "|".join(RAIL_MON) + r") (\d{4})\b")


def rail_html(stops, died=False):
    """The rail of a bill's stops, each dated, and the same facts as one
    sentence for a reader who hears it: every date in full, a tally read "16
    to 8". `died` is whether the bill's chip is Died, which says a pause is
    the tabling it was. "" where there are no stops."""
    st = []
    for s in stops or []:
        if isinstance(s, (list, tuple)):
            row = list(s) + ["", "", ""]
            sm = str(row[0] or "")
            st.append({"stop": RAIL_STOP.get(sm[:1], sm[:1]), "mark": sm[1:],
                       "date": row[1] or "", "short": row[2] or "", "say": ""})
        else:
            st.append({k: s.get(k) or "" for k in ("stop", "mark", "date", "short", "say")})
    if not st:
        return ""
    words = {**RAIL_SAY, **RAIL_SAY_DIED} if died else RAIL_SAY
    cells, said = [], []
    for s in st:
        day = date_words(s["date"]) if s["date"] else ""
        small = (f'<small>{esc(day[:-5])}<span class="ry">{esc(day[-5:])}</span></small>'
                 if day else "")
        cells.append(f'<span class="stop s-{esc(RAIL_CLASS.get(s["mark"]) or s["mark"])}"><b>'
                     f'{RAIL_MARK.get(s["mark"], "")}</b><i>{esc(s["stop"])}</i>{small}</span>')
        when = date_words(s["date"], "full") if s["date"] else ""
        own = bool(s["short"]) and s["stop"] in ("Governor", "Law", "Voters") and s["mark"] in ("p", "x")
        short = "" if s["short"] == RAIL_SAID.get(s["mark"]) else s["short"]
        what = s["say"] or (s["short"] if own else ", ".join(
            x for x in (words.get(s["mark"]), short) if x))
        what = re.sub(r"(\d)–(\d)", r"\1 to \2", what)
        what = _RAIL_DAY.sub(lambda m: date_words(
            f"{m.group(3)}-{RAIL_MON.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}", "full"), what)
        what = _RAIL_MONTH.sub(lambda m: f"{MONTHS[RAIL_MON.index(m.group(1))]} {m.group(2)}", what)
        law_day = s["stop"] == "Law" and s["mark"] == "p"
        tail = ("" if not when else f", {when}" if not law_day else
                "" if "in effect" in what else f", in effect {when}")
        said.append(f"Introduced{f' {when}' if when else ''}" if s["stop"] == "Introduced"
                    else f'{s["stop"]}: {what[:1].lower() + what[1:]}{tail}')
    s_ = esc("; ".join(said))
    return (f'<span class="rail dated" role="img" aria-label="{s_}" title="{s_}">'
            f'{"".join(cells)}</span>')


def person_link(m):
    """A person in a running sentence (D14, the person, 8 October 2026):
    the full label as a link -- "Rep. Alice Wade (D - Straf 15)", never the
    party letter alone -- with the seat held at the time, which the caller's
    record gives. Text where there is no page to link to."""
    full = str(m.get("display_full") or m.get("label") or m.get("name") or "")
    slug = m.get("slug") or ""
    return (f'<a class="psent" href="legislator/{esc(slug)}.html" translate="no">{esc(full)}</a>'
            if slug else esc(full))


def term_mark(key, text):
    """A term of the record's shorthand, marked for its popover (C9): the
    writer chooses the key by context (RC is a roll call on a vote,
    RC-calendar the Regular Calendar), and components.js makes the first on
    the page a button that opens glossary.json's entry."""
    return f'<span data-term="{esc(key)}">{esc(text)}</span>'


def _vote_motion(key):
    """The vote words' row for a motion key, the consent calendar's for
    "consent", or None."""
    v = WORDBOOK["votes"]
    return v["consent"] if key == "consent" else v["motions"].get(key)


def _vote_fill(s, fill):
    """{Committee}, {Chamber} and {Bill} put in a vote's words."""
    for k, x in (fill or {}).items():
        s = s.replace("{" + k + "}", str(x))
    return s


def vote_head(key, own="", fill=None):
    """A vote's head in the approved words (the person, 8 October 2026,
    votes.json): the motion's own name in Title Case and a plain gloss in
    brackets, an abbreviation before it only for OTP, OTPA, ITL and IS, each
    marked for its popover -- "Inexpedient to Legislate (ITL, Kill the
    bill)". `own` is the head where the words have no single name (a part of
    a divided question) or the motion is one they do not hold: the record's
    words, as they are. `fill` names {Committee} and {Chamber}."""
    m = _vote_motion(key)
    if m is None or m.get("motion") is None:
        return esc(own)
    gloss = esc(_vote_fill(m.get("gloss") or "", fill))
    abbr = term_mark(m["abbr"], m["abbr"]) + ", " if m.get("abbr") else ""
    return esc(_vote_fill(m["motion"], fill)) + (f" ({abbr}{gloss})" if gloss else "")


def vote_chip(key, passed, bill="", fill=None):
    """What the vote did, as its chip, coloured by the vote's outcome (the
    person, 8 October 2026: green where the motion passed, red where it
    failed, whatever follows the colon): "Motion Passed: Bill Killed",
    "Motion Failed". {Bill} is the measure's noun by the letters of its
    number; a vote on no bill takes none. "" where the outcome is not on
    record."""
    if passed is None:
        return ""
    v = WORDBOOK["votes"]
    m = _vote_motion(key) or {}
    prefix = re.match(r"[A-Z]+", str(bill or "").upper())
    noun = next((n for n, ps in v["nouns"].items() if prefix and prefix.group(0) in ps), "")
    raw = m.get("passed" if passed else "failed") or ""
    tail = "" if "{Bill}" in raw and not noun else _vote_fill(raw, dict(fill or {}, Bill=noun))
    # A place in the words the record could not fill -- the committee a
    # referral was vacated to, where the docket names only the one it left
    # -- leaves the outcome alone rather than a brace on the page.
    tail = "" if "{" in tail else tail
    word = (v["passed"] if passed else v["failed"]) + (f": {tail}" if tail else "")
    return chip(word, "rcres " + ("pass" if passed else "fail"))


def record_head(h):
    """THE RECORD'S HEAD (the plan's page head, from option E; C6): the
    trail ending in the kind of record, the h1 with the year beside it and
    the chip at the right, one line, up to six labelled facts, the rail
    centred (a bill's), the actions, and nothing tinted behind it. ONE DOM
    ORDER AT EVERY WIDTH -- trail, title, chip, line, facts, rail, actions --
    and the stylesheet's grid areas move the actions to the right on a
    desktop and under the rail on a phone, so the keyboard's order is the
    reading order. The tabs follow it, hanging from its foot rule.

    `h`: {trail: [[label, href], ...] (the last, the kind, has no href),
    title (markup), year, chip (markup), line (markup), facts: [[label,
    markup, note], ...], rail (markup), actions (markup), kind (a class)}."""
    crumbs = "".join(
        (f'<li><a href="{esc(href)}">{esc(lab)}</a></li>' if href else
         f'<li aria-current="page">{esc(lab)}</li>') for lab, href in (h.get("trail") or []))
    year = f' <span class="ryear">({esc(h.get("year"))})</span>' if h.get("year") else ""
    facts = "".join(
        f'<div><dt>{esc(f[0])}</dt><dd>{f[1]}'
        + (f'<small>{f[2]}</small>' if len(f) > 2 and f[2] else "") + "</dd></div>"
        for f in (h.get("facts") or [])[:6] if f[1])
    kind = f' rh-{esc(h.get("kind"))}' if h.get("kind") else ""
    return (f'<header class="rhead{kind}">'
            + (f'<nav class="rtrail" aria-label="Where this page is"><ol>{crumbs}</ol></nav>'
               if crumbs else "")
            + f'<div class="rtop"><h1 class="rh1">{h.get("title") or ""}{year}</h1>'
            + f'{h.get("chip") or ""}</div>'
            + (f'<p class="rline">{h.get("line")}</p>' if h.get("line") else "")
            + (f'<dl class="rfacts">{facts}</dl>' if facts else "")
            + (f'<div class="rrail">{h.get("rail")}</div>' if h.get("rail") else "")
            + f'<div class="racts">{h.get("actions") or ""}</div></header>')


def doc_row(x):
    """A document of the record, as a bill's Documents tab lists it (the
    component plan's step 7): its label as the link to the General Court's
    own copy, opening in a new tab as every outside link does (D20), where
    it comes from and when, and what it is the record of. `x`: {kind,
    label, url, of, what}; `what` is markup, the docket's lines or the
    sentence that says what the document is. A room's building is not
    named: the General Court's key knows LOB and SH and not GP, and the
    plan does not guess it."""
    of = f'<span class="docof">{esc(x.get("of"))}</span>' if x.get("of") else ""
    return (f'<li class="doc doc-{esc(x.get("kind"))}"><a href="{esc(x.get("url"))}" '
            f'target="_blank" rel="noopener">{esc(x.get("label"))}</a>{of}{x.get("what") or ""}</li>')


def section(heading, body, sid=""):
    """A W4 section (C7): its heading in Title Case in a margin level with
    its first line, beside prose about a hundred characters wide; over its
    text below 960px. The heading is written in its case where it is made
    (C8); preflight holds every one of them to the rule."""
    i = f' id="{esc(sid)}"' if sid else ""
    return (f'<section class="w4"{i}><h2 class="w4h">{esc(heading)}</h2>'
            f'<div class="w4b">{body}</div></section>')


# WHAT RETIRES ON A DAY (the members-elect, the person's decisions of 16
# October 2026). A member-elect is drawn until Organization Day and not on
# it, and a page built on the 1st may still be read on the 3rd: a night held,
# a copy a browser kept. So whatever retires carries its last day in
# data-until, and components.js's behaviour hides it by the reader's own
# clock, as the home page's stale warning works its age out again. The build
# also stops writing site/members_elect.json that day; this is the reader's
# half of the same rule.
UNTIL_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def until_attrs(until, today):
    """The attributes of an element that retires on `until` ("YYYY-MM-DD",
    or a date), as drawn on `today` -- the build's day in Python, the
    reader's in the browser:

        until_attrs("2026-12-02", "2026-11-20")  -> ' data-until="2026-12-02"'
        until_attrs("2026-12-02", "2026-12-02")  -> ' data-until="2026-12-02" hidden'

    Hidden from its day on. An `until` that is no day is hidden at once: a
    block that cannot say when it ends is not shown at all. A `today` that
    is no day leaves the judging to the reader's clock."""
    u = "" if until is None else str(until)[:10]
    t = "" if today is None else str(today)[:10]
    if not UNTIL_DAY.fullmatch(u):
        return " hidden"
    gone = bool(UNTIL_DAY.fullmatch(t)) and t >= u
    return f' data-until="{esc(u)}"' + (" hidden" if gone else "")


# MEMBERS-ELECT, DRAWN ONE WAY (the person's decisions of 16 October 2026,
# private/MEMBERS_ELECT_PLAN.md). Who November's election sent is drawn on a
# town page and in the district map's panel, on the Officials page's own
# tab, in the My Town card and on a returning member's own page -- two of
# those built here in Python and three drawn in the browser -- so the block,
# its words and its chip are these helpers in both languages and nowhere
# else. Every one of them is drawn from site/members_elect.json alone, never
# from the roster; each element carries data-elect, which says what it is,
# and until_attrs, which retires it on the day they take office. The words
# are the person's: "Elected November 3, 2026", "Takes office December 2,
# 2026.", "Result not final" with "a recount was requested" only where the
# race says so, "No member-elect on file for 1 seat." and "Serving now". No
# contact detail is drawn for a member-elect, and nothing about a sitting
# member who is not on the list.
ELECT_KEY = re.compile(r"H\|([^|]+)\|([0-9]+)|S\|([0-9]+)")


def elect_now(takes_office, today, lang="en"):
    """"Serving now", the label over the sitting members wherever a
    members-elect block is drawn beside them, so that two lists of people
    under one district say which is which. It names nobody, and retires
    with the block. Its words in `lang` (the Your Town card in Spanish, 25
    October 2026), as components.js's tr gives them."""
    import i18n
    return (f'<p class="elnow" data-elect{until_attrs(takes_office, today)}>'
            + i18n.say(lang, "elect.serving", "Serving now") + "</p>")


def elect_race(race, lang="en"):
    """One race of site/members_elect.json as the pages draw it, under
    whatever heading the page gives it: each member-elect in the site's one
    person chip, with their party's letters -- a cross-nomination ("R/D")
    on the neutral chip, both letters kept, and no letter where none was
    printed -- and linked to a page only where the file gives both an id
    and a page, so a new person is never somebody else's record; then
    "Result not final" where seats are, which is every race until the
    recount deadline has passed and so the normal state of the first days;
    then the seats with nobody on file, held ones among them. A race with
    no seats to speak of draws nothing."""
    import i18n
    r = race or {}
    won = r.get("elected") or []
    chips = []
    for e in won:
        p = str(e.get("p") or "")
        chips.append("<li>" + pchip({
            "party_code": p if len(p) == 1 else "X",
            "display_full": f'{e.get("n") or ""} ({p})' if p else (e.get("n") or ""),
            "slug": e.get("s") if e.get("id") and e.get("s") else ""}) + "</li>")
    left = (r.get("seats") or 0) - len(won) - (r.get("not_final") or 0)
    return (('<ul class="ellist">' + "".join(chips) + "</ul>" if chips else "")
            + ('<p class="elnf"><b>' + i18n.say(lang, "elect.not_final", "Result not final") + "</b>"
               + (" " + i18n.say(lang, "elect.recount", "&mdash; a recount was requested")
                  if r.get("recount") else "") + "</p>"
               if r.get("not_final") else "")
            + ('<p class="elnone">'
               + (i18n.say(lang, "elect.none_one", "No member-elect on file for {n} seat.", n=left)
                  if left == 1 else
                  i18n.say(lang, "elect.none", "No member-elect on file for {n} seats.", n=left))
               + "</p>" if left > 0 else ""))


def elect_block(races, election, takes_office, today, lang="en"):
    """The members-elect block: "Elected November 3, 2026" and "Takes office
    December 2, 2026." over each race in `races` -- [[label, race], ...],
    the label "" where the block sits under its district's own heading, as
    on a town page, and the district's name where one block holds two, as
    the My Town card's House seat can. The dates are the file's own
    election and takes_office."""
    import i18n
    body = "".join((f'<p class="elwhere">{esc(label)}</p>' if label else "") + elect_race(race, lang)
                   for label, race in races or [])
    return (f'<div class="elect" data-elect{until_attrs(takes_office, today)}>'
            '<p class="elhead"><b>' + i18n.say(lang, "elect.elected", "Elected {day}",
                                              day=esc(date_words(election, "full", lang)))
            + "</b> <span>" + i18n.say(lang, "elect.takes", "Takes office {day}.",
                                       day=esc(date_words(takes_office, "full", lang)))
            + f"</span></p>{body}</div>")


def elect_line(key, election, takes_office, today):
    """The one line on a returning or re-elected member's own page: "Elected
    November 3, 2026, for Rockingham district 13. Takes office December 2,
    2026." -- the race's own county and district, which may not be the seat
    the page's heading names, or "Senate District 24". The heading above it
    is left as it is until they take office ("Former Representative ..."
    stays until the switch)."""
    m = ELECT_KEY.fullmatch("" if key is None else str(key))
    where = ("" if not m else f"Senate District {m.group(3)}" if m.group(3)
             else f"{m.group(1)} district {m.group(2)}")
    return (f'<p class="elline" data-elect{until_attrs(takes_office, today)}>'
            f'Elected {esc(date_words(election, "full"))}'
            + (f", for {esc(where)}" if where else "")
            + f'. Takes office {esc(date_words(takes_office, "full"))}.</p>')
