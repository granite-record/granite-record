#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.42
"""
A page per town and ward: everyone who represents the people who live there.

    python3 src/pages/build_town_pages.py --site site --base https://graniterecord.org

Writes site/town/<slug>.html for each of the 320 town-wards, and adds them to
sitemap.xml.

WHY A PAGE AND NOT ONLY THE LOOKUP

The legislators page already answers "who are my representatives" in place:
pick a town, pick a ward, see the House and Senate seats. What it cannot do is
be linked to, shared, printed or found in a search -- and "who represents
Concord Ward 3" is exactly the question somebody types into a search engine.

It also stopped at the General Court. A resident has an executive councillor,
a member of the US House and two US senators as well, and the district
numbers for all of them were already on this disk in site/districts.json and
had never been shown.

WHAT IS DERIVED AND WHAT IS DECLARED

The districts are derived: records/districts/council.txt, congress.txt, senate.txt and
house.txt are the maps, and parse_districts.py turns them into a town-ward
lookup that includes the floterial districts the General Court's own file
leaves out.

The people are not. State legislators come from the roster the rest of the
site uses. The Governor, the five councillors, the two US representatives and
the two senators come from officials.json, which is edited by hand and which
no generator writes -- a name against an office is a claim about a real
person, and it should come from somebody who checked. Where a name is blank
the page names the office, gives the reader their district and links to the
official directory, which is correct and does not go stale. A successor the
file names under a seat is its holder from the day the file says they take
office (build_members_elect.read_officials, 23 October 2026).

A town's select board, and a city's mayor and council, come from its own
website where that page was current when read (town_boards.py decides, and
writes town_boards.json), and otherwise from NHDOT's directory of September
2025, which is dated on the page and shown without the chair it names. A page
that lists fewer than the body's seats is shown, labelled with how many it
lists. The town clerk comes from the Secretary of State's list.

Between a general election and Organization Day the State House and Senate
districts also say who the election sent, from site/members_elect.json alone
(build_members_elect.for_pages), under the sitting members and with "Serving
now" over them; places.json carries the same for the My Town card. Outside
those weeks there is no file, and the pages are what they were.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import json
import re
import urllib.parse

import build_date
import components as C
import shell as S
# Who November's election sent, for the weeks before they sit: the one
# reader of site/members_elect.json, beside its one writer (16 October 2026).
# And the one reader of corrections/officials.json, which puts each office's
# successor in office on the day the file gives (23 October 2026).
from build_members_elect import for_pages as members_elect, race_order, read_officials
# The parser's test for an e-mail address, so that what it accepts from a
# threaded cell and what a page links are the same test.
from parse_officials import EMAIL_OK
# How a town's own page spells a board officer and a name, decided where the
# board is read, so the page and town_boards.json cannot drift apart -- and
# the list of the thirteen cities, kept in one place.
from town_boards import CITIES, board_role, display_name, in_capitals
# The one person chip for a legislator, the same one the roster, a committee
# and a bill draw.
from build_pages import pchip

E = S.E


def slug(town, ward):
    s = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
    return f"{s}-ward-{ward}" if ward and ward != "0" else s


def town_file(town, ward):
    """Where this town-ward's page is written, as a path from the site root."""
    return f"/town/{slug(town, ward)}.html"


def town_path(town, ward):
    """The address the host serves that file at, and the only form a link to
    it may take.

    ONE FUNCTION BECAUSE THERE WERE THREE PLACES. The canonical tag, the
    sitemap entry and the ward picker each built this address themselves, and
    the ward picker built it differently and wrongly -- see ward_picker().
    """
    return S.canon(town_file(town, ward))


def where(town, ward, wards):
    return f"{town}, Ward {ward}" if len(wards) > 1 else town


def off_row(who, how, seat="", cls=""):
    """One official: who they are on the left, how to reach them on the right.

    NOT a middle-dot string. These rows were built as `name &middot; email
    &middot; phone`, which DESIGN.md names as a default to avoid and which at
    360px wrapped three facts into a ribbon with no shape. The two halves are
    two cells now, and the stylesheet stacks them on a phone.

    cls is for the one row that is not like the others -- see offvote.
    """
    return (f'<li class="offrow{(" " + cls) if cls else ""}">'
            '<span class="offwho">' + who
            + (f'<span class="offseat">{seat}</span>' if seat else "")
            + '</span>'
            + ('<span class="offhow">' + "".join(how) + '</span>' if how else "")
            + '</li>')


def member_block(members, empty, seat=""):
    """The people in a seat, each with a way to reach them.

    A LEGISLATOR IS DRAWN BY THE SHARED CHIP. This wrote a chip of its own --
    the same classes, its own link and its own idea of the name -- which is
    the drift pchip was made to end: a member reads the same here as on the
    roster, a committee page and a bill.
    """
    if not members:
        return f'<p class="note">{E(empty)}</p>'
    out = []
    for m in members:
        how = []
        if maillink(m.get("email")):
            how.append(maillink(m.get("email")))
        if m.get("phone"):
            how.append(f'<span class="offtel">{E(m["phone"])}</span>')
        out.append(off_row(pchip(m), how, seat))
    return '<ul class="offlist">' + "".join(out) + "</ul>"


# A seat the directory records as empty. "VACANT" is not a person, and a
# person's chip around it said it was one: Danville's, Deering's and
# Rindge's administrators and Roxbury's road agent.
VACANT = re.compile(r"^\s*(?:position\s+)?vacant\s*$", re.I)


def person(name):
    """A town official's name as a chip, or a vacancy as the plain word.

    A name written wholly in capitals is set in normal case (the person, 24
    September 2026), by town_boards.display_name, whichever source gave it.
    A clerk arrives already recased: the Secretary of State gives every one
    in capitals, and parse_clerks.namecase set them in normal case when it
    wrote town_clerks.json.
    """
    if VACANT.match(name or ""):
        return "Vacant"
    return f'<span class="mchip" translate="no">{E(display_name(name))}</span>'


# Ten digits, then an extension if there is one: "603-588-6785 ext 221",
# "603-927-2400 ext. 4", "(603) 224-5000 x 12".
PHONE = re.compile(r"^\s*\(?(\d{3})\)?[-. ]?(\d{3})[-. ]?(\d{4})\s*,?\s*"
                   r"(?:(?:ext\.?|ex\.?|x)\s*(\d+))?\s*$", re.I)


def tel(num):
    """A number that dials, on the device most readers are holding.

    These were plain text. A town clerk's number on a town page is the single
    most likely thing on this site to be tapped, and tapping it did nothing.

    AN EXTENSION IS NOT MORE OF THE NUMBER. This took every digit in the
    value, so "603-588-6785 ext 221" dialled +6035886785221 -- a number in no
    country this site is about -- and 28 links on the town pages did that.
    The extension is written the way a phone reads it now, `;ext=221` after
    the number (RFC 3966), and a value that holds no single number -- two
    numbers in one cell -- is shown as written and not linked, because either
    guess would ring somebody.
    """
    m = PHONE.match(num or "")
    if m:
        a, b, c, ext = m.groups()
        href = f"tel:+1{a}{b}{c}" + (f";ext={ext}" if ext else "")
        return f'<a class="offtel" href="{href}">{E(num)}</a>'
    digits = re.sub(r"[^0-9]", "", num or "")
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return f'<a class="offtel" href="tel:+{digits}">{E(num)}</a>'
    return f'<span class="offtel">{E(num)}</span>'


def maillink(addr):
    """A mailto link for an e-mail address, and nothing for anything else.

    NHDOT's e-mail column holds notes as well as addresses -- "can email
    through the website, no stated email", "no stated email address", "not
    listed", once a street address -- 125 of them across 104 towns, and every
    one was published as a mailto link a reader could click. A note that
    says there is no address tells a reader what no link already does, and
    the town's website is on the page, so nothing is drawn.

    All five places on these pages that write a mailto go through here.
    """
    a = (addr or "").strip()
    if not EMAIL_OK.match(a):
        return ""
    # A LINE MAY BREAK AFTER THE @, and so the address breaks there rather
    # than wherever the column runs out: at the interface's 16px a select
    # board member's address in a town card's contact column read
    # "Jim.Craig@GoffstownNH.g" over "ov" (the review of the polish
    # foundation, 8 October 2026). Only the words drawn; the address is whole.
    return f'<a href="mailto:{E(a)}">{E(a).replace("@", "@<wbr>", 1)}</a>'


# Words in a printed name that are not the person's first or last name.
_NOT_A_NAME = {"jr", "sr", "ii", "iii", "iv", "dr", "mr", "mrs", "ms", "rev"}


def _first_last(name):
    words = [re.sub(r"[^a-z]", "", w) for w in (name or "").lower().split()]
    words = [w for w in words if len(w) > 1 and w not in _NOT_A_NAME]
    return (words[0], words[-1]) if len(words) >= 2 else None


def _one_edit(a, b):
    """Whether two strings differ by at most one letter added, lost or changed."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(short == long_[:i] + long_[i + 1:] for i in range(len(long_)))


def address_names(email, name):
    """Whether an e-mail address is built from this person's name.

    The forms towns use: "rbridle", "jhoytselectman", "johnw.herbert",
    "suemckinnon" -- a first name or initial, perhaps a middle initial, then
    the surname, then anything. A surname of five letters or more may be one
    letter out, because the directory's own typing sometimes is: "ahanson"
    for Amy Hansen, "cbariont" for Carleigh Beriont.

    The surname may also open the address, or follow one stray letter:
    Nashua writes "clemonsb@", Lincoln "dalybos@", Hancock "smith@", and the
    directory prints "lflanagan@" for Ian Flanagan and "JAiello@" for Anthony
    Aiello. Of the 315 addresses in the September 2025 directory that name
    their own row, 28 are recognised only that way.

    IT IS LOOSER THAN "A NAME". That form, with the one-letter allowance,
    also reads an office address as a person's: "clerk@" names a John Clark,
    "roadagent@" a Bob Road, and "jsmith@" a Mary Smith, and
    names_someone_else() would then withhold the office's address beside
    anybody else. In the September 2025 directory it finds exactly the nine
    wrong-person addresses and nothing else; with a new edition, the count
    main() prints is where a correct address withheld this way would first
    show.
    """
    fl = _first_last(name)
    if not fl or "@" not in (email or ""):
        return False
    first, last = fl
    if len(last) < 3:
        return False
    local = re.sub(r"[^a-z]", "", email.split("@", 1)[0].lower())
    heads = {"", first[0], first}
    heads |= {h + c for h in (first[0], first)
              for c in "abcdefghijklmnopqrstuvwxyz"}
    for h in heads:
        if not local.startswith(h):
            continue
        rest = local[len(h):]
        if len(last) < 5:
            if rest.startswith(last):
                return True
            continue
        for n in (len(last) - 1, len(last), len(last) + 1):
            if n <= len(rest) and _one_edit(rest[:n], last):
                return True
    return False


def names_someone_else(email, name, officials):
    """The other official of the same town an address is named for, or "".

    AN ADDRESS BESIDE THE WRONG PERSON. NHDOT prints nine addresses on the
    wrong row: in Hampton four of the five selectmen carry another
    selectman's address (Amy Hansen beside rbridle@, Rusty Bridle beside
    ahanson@), Bow's and Salisbury's two selectmen carry each other's, and
    Newfields' road agent carries the town clerk's. A page that draws
    rbridle@ beside Amy Hansen tells a reader to write to her at Rusty
    Bridle's address. An address that names the person beside it is theirs
    and is kept; one that names nobody -- "selectmen@", "townclerk@" -- is
    the office's and is kept; one that names another official of the town and
    not this one is not drawn.
    """
    if not email or address_names(email, name):
        return ""
    me = re.sub(r"[^a-z]", "", (name or "").lower())
    for o in officials:
        other = o.get("name") or ""
        if re.sub(r"[^a-z]", "", other.lower()) == me:
            continue
        if address_names(email, other):
            return other
    return ""


# THE CLERK IS THE SECRETARY OF STATE'S. How to Vote names the town or city
# clerk from the Secretary of State's list, and NHDOT's directory names one
# too, on nineteen rows: twelve "Town Clerk", one "City Clerk" and six
# "Town Administrator/ Town Clerk". Drawn together, thirty pages carried two
# clerk rows and seven towns named two different people as clerk -- Windsor
# had Stephanie L Houle above and Melissa Merrill below. The Secretary of
# State keeps the list of clerks, so NHDOT's clerk rows are not drawn.
CLERK_ROW = re.compile(r"\b(?:town|city) clerk\b", re.I)
COMBINED_ROW = re.compile(r"^\s*town administrator\s*/\s*town clerk\s*$", re.I)

# The six combined rows are on NHDOT's first two pages. The Secretary of
# State names somebody else as clerk in all six, so the clerk half is wrong;
# the administrator half is confirmed by a second source on this disk for
# two of them, and those two are kept as "Town Administrator". The other four
# -- Albany, Alexandria, Alstead, Amherst -- are not drawn: Alexandria's own
# page calls its person an administrative assistant, and Alstead's names a
# different Select Board Office Administrator. Keyed by the name NHDOT
# prints, so a new edition naming somebody else is not relabelled unchecked.
ADMINISTRATOR_CONFIRMED = {
    # NHDOT's own address for him is administrator@alton.nh.gov
    ("alton", "Ryan Heath"),
    # town-atkinsonnh.com/334/Board-of-Selectmen, read 20 September 2026:
    # "John Apple, Town Administrator"
    ("atkinson", "John Apple"),
}


def local_offices(key, officials):
    """The NHDOT rows a town page draws, as (office, row) pairs, in order."""
    out = []
    for o in officials or []:
        pos = o.get("position") or ""
        if COMBINED_ROW.match(pos):
            if (key, o.get("name")) in ADMINISTRATOR_CONFIRMED:
                out.append(("Town Administrator", o))
            continue
        if CLERK_ROW.search(pos):
            continue
        out.append((pos, o))
    return out


# The directory every row in a town's Officials section comes from, named in
# full: "DoT" told a reader new to this nothing about which department, or
# why a transport agency lists selectmen.
NHDOT = ("the New Hampshire Department of Transportation's directory of city "
         "and town officials, dated September 2025")
NHDOT_SHORT = "the New Hampshire Department of Transportation's directory"

# NHDOT's rows for the select board: "Board of Selectman" and "Board of
# Selectman, Chair", as it prints them.
BOARD_ROW = re.compile(r"^\s*board of selectm[ae]n\b", re.I)
# The officer a board or council chose for itself -- chair, vice chair,
# secretary -- written after the seat. A board chooses its officers again
# after every election, and the directory's chair disagrees with the town's
# own page in 25 of the 40 towns where both name one, so the directory's are
# not drawn. The seat itself ("City Councilor, Ward 3") is.
OFFICER = re.compile(r"\s*(?:,\s*(?:(?:vice[\s-]?)?chair(?:man|woman|person)?|"
                     r"secretary|clerk)|"
                     r"\((?:secretary|clerk|(?:vice[\s-]?)?chair)\))\s*$", re.I)
COUNCIL_ROW = re.compile(r"council|alder", re.I)


def long_date(stamp):
    """"2026-09-20T22:22:15-0400" as "September 20, 2026": shell.date_words."""
    if not re.match(r"\d{4}-\d\d-\d\d", stamp or ""):
        return ""
    return S.date_words(stamp, "full")


def own_board_rows(board, officials, council=False):
    """The select board -- or, with `council`, a city's mayor and council --
    as the town's own page lists it, one row a member.

    The page gives names and the chair; the directory, where it has the SAME
    person (town_boards.py matched them, and wrote the directory's spelling
    down as directory_name), gives the phone and e-mail. An address that
    names another official of the town is not drawn beside anybody, the same
    rule every other row here follows. Returns (rows, whether any contact
    came from the directory).
    """
    row = COUNCIL_OR_MAYOR if council else BOARD_ROW
    by_name = {o.get("name"): o for o in officials or []
               if row.search(o.get("position") or "")}
    pool = list(officials or []) + [{"name": m["name"]}
                                    for m in board.get("members") or []]
    rows, borrowed = [], False
    for m in board.get("members") or []:
        how = []
        o = by_name.get(m.get("directory_name") or "")
        if o:
            if o.get("phone"):
                how.append(tel(o["phone"]))
            if not names_someone_else(o.get("email"), o.get("name"), pool):
                if maillink(o.get("email")):
                    how.append(maillink(o.get("email")))
            borrowed = borrowed or bool(how)
        # Under a "Select board" heading, so the seat line carries only the
        # officer the town's page names, and nothing for a member. A
        # council's carries the seat -- "Ward 3", "At large", "Mayor" -- and
        # the office its own page gives: "At large, President".
        if council:
            seat = ", ".join(s for s in (m.get("seat"), m.get("role")) if s)
        else:
            seat = board_role(m.get("role"))
        rows.append(off_row(person(m.get("display") or m["name"]), how,
                            E(seat)))
    return rows, borrowed


def listed_label(body, noun="members"):
    """The label a partial list carries beside its heading (the person, 24
    September 2026: "3 of 5 members listed"), and "" for a whole one. Where
    no source gives the body's size the label has no denominator, and the
    note under the names says why."""
    if not body.get("partial"):
        return ""
    # The members the size counts, as town_boards.py counted them: a mayor
    # read off another page is shown, and is one of Nashua's fifteen
    # aldermen only if the page's sentence says so. A file written before
    # that count was kept has every member counted.
    n = body.get("read") or len(body.get("members") or [])
    size = body.get("size")
    text = f"{n} of {size} {noun} listed" if size else f"{n} {noun} listed"
    return f' <span class="twnseats">{E(text)}</span>'


# Where a partial list's size came from, as the note under it says so.
SIZE_FROM = {
    "the page states it": "as its own page says",
    "another of the town's pages states it": "as another page of its "
                                             "website says",
    "another of the city's pages states it": "as another page of its "
                                             "website says",
}


def listed_note(body, what):
    """The sentence under a partial list: how many seats, and on whose word,
    or that no source on file says."""
    if not body.get("partial"):
        return ""
    size = body.get("size")
    if not size:
        return (f" No source on file gives the size of the {what}, so this "
                "may be only part of it.")
    whose = SIZE_FROM.get(body.get("size_from") or "",
                          f"as {NHDOT_SHORT} lists")
    return f" The {what} has {size} seats, {whose}."


def dot_row(pos, o, officials):
    """One of NHDOT's rows: the person, their seat, and how to reach them."""
    how = []
    if o.get("phone"):
        how.append(tel(o["phone"]))
    if not names_someone_else(o.get("email"), o.get("name"), officials):
        if maillink(o.get("email")):
            how.append(maillink(o.get("email")))
    if BOARD_ROW.match(pos):
        # Drawn under a "Select board" heading, and without the directory's
        # chair: see OFFICER.
        pos = ""
    elif COUNCIL_ROW.search(pos):
        pos = OFFICER.sub("", pos)
    return off_row(person(o.get("name")), how, E(pos))


def card(title, inner, wide=False):
    """One section of a tab: a heading that outranks what it heads, and the
    rows under it, in a card of its own so that where one section ends and
    the next begins is a line on the page rather than a guess."""
    return (f'<section class="twnsec{" twnwide" if wide else ""}">'
            f'<h3 class="twnh">{title}</h3>{inner}</section>')


def note(text):
    return f'<p class="note">{text}</p>' if text else ""


MAYOR_ROW = re.compile(r"^\s*(?:assistant\s+|deputy\s+)?mayor\b", re.I)
# The directory's rows for a mayor or a council seat: the ones a city's own
# council list replaces, and lends its phone and e-mail.
COUNCIL_OR_MAYOR = re.compile(r"council|alder|^\s*(?:(?:assistant|deputy)\s+)?"
                              r"mayor\b", re.I)
# NEW HAMPSHIRE'S THIRTEEN CITIES are town_boards.CITIES, named rather than
# inferred: read off the directory's labels, Hooksett came out a city because
# NHDOT calls its town councillors "City Councilor"; it is a town with a town
# council.


def officials_sections(town, key, town_off, site_on_page=None, board=None,
                       loc=None, council=None):
    """The Town officials tab, as cards: the select board (or a city's mayor
    and council), the clerk, and the town offices with the rest of NHDOT's
    rows. Each card says under its names where they came from, because the
    three come from three places and two different years. [] if there is
    nothing to show, which is every unincorporated place.

    THE BOARD IS THE TOWN'S OWN WHERE THE TOWN'S PAGE GIVES IT. `board` is
    the town's entry in town_boards.json: the board, read off the town's own
    website on a date, from a page that does not date itself before the
    March 2026 town meeting. Everywhere else the board is NHDOT's, from
    September 2025 -- before that meeting -- and says so, without the
    directory's chair.

    A PAGE THAT LISTS PART OF THE BOARD IS SHOWN, LABELLED (the person, 24
    September 2026): "3 of 5 members listed" beside the heading, with the
    size's source under the names, or "5 members listed" and a sentence
    saying no source gives the size. The directory is not drawn in its
    place.

    A CITY'S MAYOR AND COUNCIL ARE THE CITY'S OWN BY THE SAME RULE. `council`
    is the city's entry in town_boards.json's "councils"; where there is one
    it is drawn in place of the directory's mayor and council, with each
    member's seat as the city's page gives it.

    THE CLERK IS THE SECRETARY OF STATE'S, and it is here and in How to vote
    both: the clerk runs the town's elections and keeps its records, and a
    reader on either tab should not have to go to the other to find them.

    `site_on_page` says whether the page links the town's website anywhere;
    left out, it is whether the offices card does. The last of NHDOT's notes
    sends a reader to that website only when there is one to go to: NHDOT
    records "no website" for Clarksville and Ellsworth and "website was
    discontinued" for Stewartstown, and "check Clarksville's own website"
    sent them looking for a page that is not there.
    """
    # AN UNINCORPORATED PLACE HAS NO TOWN GOVERNMENT, so no tab for one. The
    # directory covers all 234 of New Hampshire's towns and cities, and a
    # place it does not list is one of the 25 grants, purchases, locations
    # and unorganised towns the county governs. The Secretary of State does
    # name a clerk for most of them -- Bean's Grant's is Gorham's clerk, who
    # runs its elections at Gorham Town Hall -- and How to vote says so;
    # under "Town clerk" she would read as an officer of a town that has none.
    if not town_off and not board and not council:
        return []
    own_council = council if council and council.get("members") else None
    officials = town_off.get("officials") or []
    loc = loc or {}
    drawn = local_offices(key, officials)
    dot_board = [(p, o) for p, o in drawn if BOARD_ROW.match(p)]
    council = [(p, o) for p, o in drawn if not BOARD_ROW.match(p)
               and (COUNCIL_ROW.search(p) or MAYOR_ROW.match(p))]
    others = [(p, o) for p, o in drawn
              if (p, o) not in dot_board and (p, o) not in council]
    city = key in CITIES
    how = []
    if town_off.get("phone"):
        how.append(tel(town_off["phone"]))
    if maillink(town_off.get("email")):
        how.append(maillink(town_off.get("email")))
    offices_site = weblink(town_off.get("website"))
    if offices_site:
        how.append(offices_site)
    offices_row = bool(town_off.get("mailing") or how)
    if site_on_page is None:
        site_on_page = bool(offices_site)
    if site_on_page:
        then = f", so check {E(town)}'s own website for changes"
    elif offices_row:
        then = ", so ask the town offices for changes"
    else:
        then = ""
    # Which of NHDOT's cards is the last on the tab: it carries where to look
    # for changes, once, rather than every card saying it.
    dot_cards = [n for n, has in (
        ("board", bool(dot_board) and not (board and board.get("members"))),
        ("council", bool(council) and not own_council),
        ("offices", bool(others or offices_row))) if has]

    def since(which):
        return ("It does not show anyone elected or appointed since then"
                + (then if dot_cards and dot_cards[-1] == which else "") + ".")

    def own_card(title, body, what, noun, council=False):
        """A body as its own website lists it: the names, then where and
        when they were read, and a partial list's label and size. `what` is
        the body as the note names it, `noun` the one that has seats."""
        rows, borrowed = own_board_rows(body, officials, council=council)
        src = weblink(body.get("source_url"))
        # A mayor the council's page does not name, from another of the
        # city's pages: Keene names Jay Kahn on its city government page.
        # Labelled with the page and not only the host, or the note would
        # carry two links that both read "keenenh.gov".
        elsewhere = [weblink(m["source_url"], re.sub(
                         r"^https?://(?:www\.)?", "", m["source_url"]).rstrip("/"))
                     for m in body.get("members")
                     if m.get("source_url")
                     and m["source_url"] != body.get("source_url")]
        return card(title + listed_label(body), (
            '<ul class="offlist">' + "".join(rows) + "</ul>"
            + note(f"As {E(town)}'s website listed the {what} when this site "
                   f"read it on {E(long_date(body.get('read_on')))}"
                   + (f": {src}" if src else "") + "."
                   + (f" The mayor is from another page of the same "
                      f"website, {elsewhere[0]}."
                      if elsewhere and elsewhere[0] else "")
                   + listed_note(body, noun)
                   + (f" The phone numbers and e-mail addresses beside the "
                      f"names are from {NHDOT}." if borrowed else ""))))

    out = []
    # ---- who governs: the select board, or the mayor and council --------
    if board and board.get("members"):
        out.append(own_card("Select board", board, "select board",
                            "select board"))
    elif dot_board:
        # "Before the 2026 town elections": every town chose a selectman at
        # its 2026 meeting, and every board chose its chair again after it.
        out.append(card("Select board", (
            '<ul class="offlist">'
            + "".join(dot_row(p, o, officials) for p, o in dot_board)
            + "</ul>"
            + note(f"From {NHDOT}, before the 2026 town elections. "
                   + since("board")))))
    if council or own_council:
        mayor = any(MAYOR_ROW.match(p) for p, _o in council) or any(
            MAYOR_ROW.match(m.get("seat") or "")
            for m in (own_council or {}).get("members") or [])
        body = ("aldermen" if any(re.search(r"alder", p, re.I)
                                  for p, _o in council) else "council")
        title = (f"Mayor and {body}" if mayor else
                 "Board of aldermen" if body == "aldermen" else
                 "City council" if city else "Town council")
        if own_council:
            out.append(own_card(title, own_council,
                                title[0].lower() + title[1:],
                                "board of aldermen" if body == "aldermen"
                                else "council", council=True))
        else:
            out.append(card(title, (
                '<ul class="offlist">'
                + "".join(dot_row(p, o, officials) for p, o in council)
                + "</ul>" + note(f"From {NHDOT}. " + since("council")))))
    # ---- the clerk ---------------------------------------------------------
    if loc.get("clerk"):
        out.append(card("City clerk" if city else "Town clerk", (
            '<ul class="offlist">' + clerk_row(loc, seat="") + "</ul>"
            + note("From the Secretary of State's list of town and city "
                   "clerks."))))
    # ---- the town offices, and everyone else NHDOT lists ------------------
    if others or offices_row:
        rows = []
        if offices_row:
            # Under the card's own "Town offices" heading, so the row says
            # what it is instead: where to write, and how else to reach them.
            rows.append(off_row(E(town_off.get("mailing") or town), how,
                                "Mailing address" if town_off.get("mailing")
                                else "Contact"))
        rows += [dot_row(p, o, officials) for p, o in others]
        out.append(card("City offices" if city else "Town offices", (
            '<ul class="offlist">' + "".join(rows) + "</ul>"
            + note(f"From {NHDOT}. " + since("offices")))))
    return out


def town_officials_block(town, key, town_off, site_on_page=None, board=None,
                         loc=None, council=None):
    """The Town officials tab's cards as one string: see officials_sections."""
    return "".join(officials_sections(town, key, town_off, site_on_page,
                                      board, loc, council))


# ---- THE TOWN SERVICES TAB --------------------------------------------------
# The person, 24 October 2026: "gather more useful information for the town
# pages like the address of city hall, directories for the public schools in
# that town's district, transfer station addresses and hours if possible ...
# That would exist on town pages and would display in things like the guides
# if you have your town selected." The plan's first phase is here: where the
# town office is and how to reach it, and the town's public libraries. Each
# card says where its facts come from and how old they are, as the officials'
# cards do. The transfer stations followed on 25 October 2026 (the person, the
# evening before: "Are you able to retrieve the other info like the transfer
# stations so those cards can be included?"); the schools and the tax rate come
# later, as cards of this tab.
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
OSM_SEARCH = "https://www.openstreetmap.org/search?query="
LIBRARY_SURVEY = ("the Public Libraries Survey for fiscal year 2024, by the Institute of "
                  "Museum and Library Services")
DES_LIST = "the Department of Environmental Services' list of permitted solid waste facilities"


def month_year(iso):
    """"2025-09-02" as "September 2025"; "" for anything else."""
    m = re.match(r"^(\d{4})-(\d\d)", iso or "")
    return f"{MONTHS[int(m.group(2)) - 1]} {m.group(1)}" if m else ""


def address_sources(town, said):
    """The sentence under the town office's address: which sources give it
    (collected/town_halls.json's `from`, two or more), each with its date --
    the reason it is drawn at all (parse_town_halls: two that agree, or no
    address)."""
    names = []
    for f in said:
        src, on = f.get("source"), f.get("on") or ""
        if src == "nhdot":
            names.append(f"{NHDOT_SHORT} ({month_year(on)})")
        elif src == "sos_list":
            names.append(f"the Secretary of State's list of town and city clerks "
                         f"({month_year(on)})")
        elif src == "granit_cai":
            names.append("NH GRANIT's 2014 survey of public buildings")
        elif src == "town_site":
            names.append(f"{E(town)}'s own website, as this site read it on {long_date(on)}")
    if len(names) < 2:
        return ""
    joined = (", ".join(names[:-1]) + " and " + names[-1]) if len(names) > 2 \
        else " and ".join(names)
    return (f"{joined[:1].upper()}{joined[1:]} "
            f"{'all' if len(names) > 2 else 'both'} give this address.")


def maplink(line):
    """The address on OpenStreetMap, in a new tab: a link a reader follows,
    and nothing asked of anybody until they do."""
    return (f'<a class="offmap" href="{E(OSM_SEARCH + urllib.parse.quote(line))}" '
            'target="_blank" rel="noopener">Map</a>')


def station_row(town, s):
    """One transfer station of collected/transfer_stations.json: its name,
    which opens its page at DES -- the record it is drawn from -- its street
    and town, and who holds its permit where that is not the town itself and
    not the station's own name (a district's, a county's, the neighbouring
    town's whose station this town's name is on)."""
    street = s.get("street") or ""
    line = ", ".join(x for x in (street + (f' ({s["also"]})' if s.get("also") else ""),
                                 s.get("place") or "") if x)
    seat = E(line)
    holder = s.get("permittee") or ""
    if holder and holder.lower() != (s.get("name") or "").lower() and not re.fullmatch(
            rf"(?:town|city) of {re.escape(town)}", holder, re.I):
        seat += "<br>" + E(f"Permit holder: {holder}")
    where_ = ", ".join(x for x in (street or s.get("name") or "", s.get("place") or "") if x)
    who = (f'<a href="{E(s["page"])}" target="_blank" rel="noopener">{E(s["name"])}</a>'
           if s.get("page") else E(s["name"]))
    return off_row(who, [maplink(f"{where_}, NH")], seat)


def stations_card(town, city, entry, site=""):
    """The transfer station card: what DES's list holds in the town -- the
    stations it lists as operating and publicly owned, and a shared one whose
    name includes the town -- each a row (station_row), and under them where
    they come from, the day the list was read, and that hours, stickers and
    what each takes are the town's to say. "" where the list holds none: DES
    lists some stations as closed that run (Holderness's, Loudon's), so a
    town with none listed is not said to have none."""
    rows = (entry or {}).get("stations") or []
    if not rows:
        return ""
    own = [s for s in rows if not s.get("named")]
    named = [s for s in rows if s.get("named")]
    said = (f"From {DES_LIST}, as this site read it on {long_date(entry.get('read_on') or '')}"
            if long_date(entry.get("read_on") or "") else f"From {DES_LIST}")
    held = []
    if own:
        held.append(f"{'each one' if len(own) > 1 else 'the one'} it lists in {E(town)} as "
                    "operating and publicly owned")
    for s in named:
        held.append(f"{E(s['name'])} in {E(s.get('place') or '')}, whose name includes "
                    f"{E(town)}")
    whose = "city's" if city else "town's"
    hours = (f"Hours, stickers and what {'each' if len(rows) > 1 else 'it'} takes are on the "
             f"{whose} own website" + (f": {site}." if site else "."))
    return card("Transfer stations" if len(rows) > 1 else "Transfer station", (
        '<ul class="offlist">' + "".join(station_row(town, s) for s in rows) + "</ul>"
        + note(f"{said}: " + "; and ".join(held) + ". " + hours)))


def services_sections(town, key, town_off, hall=None, libraries=None, stations=None):
    """The Town Services tab's cards, for the town `key` names (a city's wards
    share it): its office, its libraries and its transfer stations. [] for a
    place NHDOT does not list -- an unincorporated place has no town office --
    so the tab is not drawn there (tabbed: a panel with nothing in it has no
    tab).

    `libraries` is the town's entry in collected/libraries.json, {} where the
    file holds none for it -- which the card says -- and None where the file
    was not loaded, when the card is not drawn at all: a missing file is not
    a town with no library. `stations` is its entry in
    collected/transfer_stations.json, on the same terms, except that a town
    the file holds none for draws no card (stations_card)."""
    if not town_off:
        return []
    city = key in CITIES
    out = []
    # ---- the town office ---------------------------------------------------
    hall = hall or {}
    rows, how = [], []
    if town_off.get("phone"):
        how.append(tel(town_off["phone"]))
    site = weblink(town_off.get("website"))
    if site:
        how.append(site)
    line = ""
    if hall.get("street"):
        line = f'{hall["street"]}, {hall["place"]}, NH {hall["zip"]}'
        rows.append(off_row(E(line), how + [maplink(line)], "Where it is"))
    mailing = town_off.get("mailing") or ""
    if mailing and not (hall.get("street") and mailing.lower().startswith(
            hall["street"].lower())):
        rows.append(off_row(E(mailing), [] if line else how, "Mailing address"))
    elif not line and how:
        rows.append(off_row(E(town), how, "Contact"))
    if rows:
        said = address_sources(town, hall.get("from") or []) if line else ""
        out.append(card("City hall" if city else "Town office", (
            '<ul class="offlist">' + "".join(rows) + "</ul>"
            + note(said or ("No street address for the office is on file that two sources "
                            "agree on; the mailing address is NHDOT's.")))))
    # ---- the libraries -----------------------------------------------------
    libs = (libraries or {}).get("libraries") or []
    if libs:
        rows = []
        for lib in libs:
            where_ = f'{lib["street"]}, {lib["city"]}'
            seat = (f"Branch library, {where_}" if lib.get("kind") == "branch" else where_)
            rows.append(off_row(E(lib["name"]), [tel(lib["phone"])] if lib.get("phone") else [],
                                E(seat)))
        out.append(card("Libraries" if len(libs) > 1 else "Library", (
            '<ul class="offlist">' + "".join(rows) + "</ul>"
            + note(f"From {LIBRARY_SURVEY}."))))
    elif libraries is not None:
        out.append(card("Library", note(f"No public library is listed in {E(town)} in "
                                        f"{LIBRARY_SURVEY}.")))
    # ---- the transfer stations ---------------------------------------------
    trash = stations_card(town, city, stations, site) if stations else ""
    if trash:
        out.append(trash)
    return out


def clerk_row(loc, seat="Town or city clerk"):
    """The town or city clerk, from the Secretary of State's list. Under the
    Town officials tab's "Town clerk" heading the seat is not said again."""
    how = []
    if loc.get("phone"):
        how.append(tel(loc["phone"]))
    if maillink(loc.get("email")):
        how.append(maillink(loc.get("email")))
    return off_row(person(loc["clerk"]), how, seat)


def weblink(url, label=None):
    """An outward link labelled with where it goes, or nothing.

    "official page" told a reader nothing about which page; the host does, and
    it is what they would read off the address bar anyway. The arrow is this
    site's mark for a link that leaves it.

    A SCHEME IS ADDED AND A NON-ADDRESS IS REFUSED. The DoT directory does not
    write addresses the way a browser reads them, and this function used to
    pass every value through untouched into an href:

      * 17 of its 234 rows are a bare host -- "www.concordnh.gov". With no
        scheme that is a RELATIVE link, and bills.html carries <base href="/">,
        so it left the site for /www.concordnh.gov. 40 dead links.
      * 4 rows are prose -- "no website", "website was discontinued" -- which
        became links to /no%20website. 8 dead links.
      * 7 more are the directory's two columns interleaved a character at a
        time by parse_officials.py: "httpsT:o//wwnw wIn.bfooscawennh.gov/" is
        "https://www.boscawennh.gov/" with "To www Info" threaded through it.
        A parser bug, not this file's to fix -- but not this file's to publish
        as a link either.

    So the host is checked before anything is written. No dot, a space, or an
    "@" (town_clerks.json records an email address as the website for two
    towns) and it is not an address this page can send a reader to, and the
    caller draws nothing rather than a link to a 404.
    """
    url = (url or "").strip()
    if not url:
        return ""
    # https:// and not http://: a guess, and the safe one -- every host here
    # that does carry a scheme carries this one, and a server that only speaks
    # http will redirect where the reverse would not.
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    if not _is_address(re.sub(r"^https?://", "", url, flags=re.I).split("/")[0]):
        return ""
    host = re.sub(r"^https?://(?:www\.)?", "", url).rstrip("/").split("/")[0]
    return (f'<a href="{E(url)}" target="_blank" rel="noopener">{E(label or host)}'
            "</a>")


def _is_address(host):
    """Whether a host is one a reader could be sent to. See weblink()."""
    return bool(host) and "." in host and " " not in host and "@" not in host


def election_day(raw):
    """The day "11/03/2026-STATE GENERAL ELECTION" names, as a date, or None
    where the list's cell names none (many of its rows are blank) or names
    one that is no day. Where a cell names two elections, as Concord's and
    Laconia's name a school election beside the state's, the first is the
    one read; on the list the two fall on the same day."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(.+)$", raw or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def next_possible_election(day):
    """The first day after `day` on which a New Hampshire town may vote again
    in the ordinary course of the law: from it, an election the Secretary of
    State's list names and that has passed can no longer be called the
    town's last.

    The days are the statutes', read in db/NH_RSA.psv on 16 October 2026:
    the school district meetings that choose district officers, from 1 March
    (RSA 197:1); town elections on the second Tuesday of March, April or May
    (RSA 669:1 and 40:14, X); the state primary on the second Tuesday of
    September (RSA 653:8); the general election on the first Tuesday after
    the first Monday of November (RSA 653:7), which is also the day a charter
    town may elect in an odd year (RSA 669:1, II); and the presidential
    primary, whose day the Secretary of State sets (RSA 653:9).

    EARLY WHERE THE LAW LEAVES ROOM, ON PURPOSE. The statutes hold the state
    primary and the general election in even years; every year is taken
    here, because the cities elect their own officers in the odd years under
    charters this file has not read, and may hold primaries before them. The
    presidential primary is taken as 1 January of a presidential year, which
    is a guess: the statute lets it come as early as the year before. Ending
    early costs a date in a heading; ending late states something untrue.
    A special election can come sooner than any of these and nothing here
    can know of one, which is a reason to read the list again rather than
    something this function can answer.
    """
    def tuesday(y, m, nth):
        first = datetime.date(y, m, 1)
        return first + datetime.timedelta(days=(1 - first.weekday()) % 7 + 7 * (nth - 1))

    days = []
    for y in (day.year, day.year + 1):
        nov = datetime.date(y, 11, 1)
        days += [datetime.date(y, 3, 1), tuesday(y, 3, 2), tuesday(y, 4, 2), tuesday(y, 5, 2),
                 tuesday(y, 9, 2), nov + datetime.timedelta(days=(0 - nov.weekday()) % 7 + 1)]
        if y % 4 == 0:
            days.append(datetime.date(y, 1, 1))
    return min(d for d in days if d > day)


def election_line(raw):
    """"11/03/2026-STATE GENERAL ELECTION" as a date in a heading.

    Returns the parenthetical for the section title: "November 3, 2026",
    month first and with its year like every date the site writes
    (shell.date_words, 8 October 2026). It was "November 3rd", with the year
    only when it was not this one.

    It says "Next Election" only while the date is ahead of the build, and on
    the day itself. After that it says "Last election": a heading still
    promising "next" in December would be wrong about the one thing the
    section is for.

    "Last election", where it said "Election on file" (the person, 16 October
    2026). The capitals are as approved: "Next Election" keeps its own, and
    "Last election" is written as the approved wording writes it.

    ONLY UNTIL THE TOWN COULD HAVE VOTED AGAIN, THEN NO DATE (16 October
    2026, a review's finding). The date comes from the Secretary of State's
    list as it was last read (collected/town_clerks.json), and nothing reads
    that list on a schedule: a person does (src/towns/parse_clerks_csv.py).
    So the date it names is the town's last election only until the town
    could have held another, and "Last election: November 3, 2026" after the
    town elections of March would be wrong in a way "Election on file" never
    was. From next_possible_election() this returns "", and the card takes
    the heading it has wherever the list names no date, "Where you vote";
    places.json's row drops "when" with it. preflight's
    _town_election_heading holds the three stretches on real rows, and
    _town_clerks_reread is the reminder, from the day the third begins, that
    the list wants reading again.
    """
    day = election_day(raw)
    if day is None:
        return ""
    try:
        when = S.date_words(day.isoformat(), "full")
    except ValueError:
        return ""
    today = build_date.today()
    if day >= today:
        return f"Next Election: {when}"
    if today < next_possible_election(day):
        return f"Last election: {when}"
    return ""


def ward_picker(town, ward, wards):
    """The other wards of this town, behind the one you are in.

    Dover has six wards and eleven representatives; a resident of ward 2 is
    shown ward 2, which is the whole point of these pages. But the question
    after "who represents me" is often "and who represents the rest of the
    town", and the only way to ask it was to go back to the finder and pick
    Dover again.

    A disclosure with links inside, not a <select>: a select needs script to
    navigate and hands a screen reader options with no addresses, where these
    are plain links that work with the keyboard and with no JavaScript at
    all. The ward you are in is in the list and is not a link.

    EVERY ONE OF THESE LINKS WAS DEAD, AND THE ADDRESS SAYS WHY. They were
    written relative -- href="dover-ward-4.html" -- which is the address a
    reader of /town/dover-ward-3.html would expect to work. It does not,
    because the template these pages are built from is bills.html and
    bills.html carries <base href="/">: a relative href on any page built by
    shell.py resolves against the SITE ROOT, not the folder the page is in. So
    the ward picker on all 73 ward pages sent its reader to
    /dover-ward-4.html, which is not a file and never was, and the 320 pages
    are all in /town/. 462 links: twelve towns have wards, and each of their
    pages links the other wards of that town.

    Root-relative and extension-less now, which is the form every other link
    this file writes already uses (/legislator/<slug>) and the address the
    host actually serves -- shell.canon is the same function the canonical tag
    and the sitemap entry for this page go through, so the three agree.
    """
    if len(wards) < 2:
        return ""
    rows = []
    # wards is the dict districts.json keys by ward, so the order is the
    # file's and Ward 10 sorts before Ward 2 as text. Numeric, the way the
    # loop that writes these pages already sorts them.
    for w in sorted(wards, key=lambda x: int(x) if str(x).isdigit() else 0):
        name = f"Ward {E(str(w))}"
        if str(w) == str(ward):
            rows.append(f'<span class="wpthis" aria-current="page">{name}'
                        f'</span>')
        else:
            rows.append(f'<a href="{E(town_path(town, w))}">{name}</a>')
    return (f'<details class="wardpick"><summary><span class="wpnow">Ward '
            f'{E(str(ward))}</span><span class="wpcue">{len(wards)} wards in '
            f'{E(town)}</span><span class="chev">&#9656;</span></summary>'
            f'<nav class="wplist" aria-label="Wards of {E(town)}">'
            + "".join(rows) + '</nav></details>')


def office_block(title, holder, fallback_url, note=""):
    """One office this site does not track: what it is, who holds it if we
    were told, and the official page either way."""
    holder = holder or {}
    name = (holder.get("name") or "").strip()
    url = (holder.get("official_url") or "").strip() or fallback_url
    if name:
        p = (holder.get("party") or "X")[:1].upper()
        # THE PARTY IN LETTERS AS WELL AS COLOUR, as a legislator's chip
        # carries it in "(R - Rock 16)": the Governor's, the councillors' and
        # the delegation's chips said it by the bar's colour alone (the survey
        # of 7 October 2026), which a reader who cannot tell red from blue,
        # or a screen reader, never gets.
        said = f'{E(name)} <span class="mtag">({E(p)})</span>' if p != "X" else E(name)
        link = (f'<a href="{E(url)}" rel="noopener">{said}</a>'
                if url else said)
        who = f'<span class="mchip p-{E(p)}" translate="no">{link}</span>'
        how = []
        if holder.get("phone"):
            how.append(tel(holder["phone"]))
        if holder.get("phone_dc"):
            how.append(tel(holder["phone_dc"]) + " (Washington)")
        if maillink(holder.get("email")):
            how.append(maillink(holder.get("email")))
        official_site = weblink(url)
        if official_site:
            how.append(official_site)
        row = off_row(who, how)
    else:
        # NOT AN APOLOGY AND NOT AN EMPTY SPACE. The district is the useful
        # half of the answer and it is known; the name is the half this site
        # was not told, and the office's own directory is where it is right.
        row = off_row(f'<a href="{E(url)}" rel="noopener">'
                      "who holds this seat, on the official directory</a>", [])
    # THE NOTE GOES UNDER THE NAME. Asked for, and it is the right way round:
    # the heading says which office, the row says who holds it, and the note
    # says what the office does. A reader who came to find out who their
    # councillor is should not have to read three sentences about the Council
    # to get to the name; a reader who wants to know what the Council does has
    # it immediately after.
    inner = ('<ul class="offlist">' + row + "</ul>"
             + (f'<p class="note">{E(note)}</p>' if note else ""))
    # A titled office is a card of its own on the Representatives tab.
    return card(E(title), inner) if title else inner


def elect_race_of(elect, key):
    """The race `key` ("H|Rockingham|13", "S|24") of the members-elect file,
    or None where there is no file or it does not hold the race."""
    return ((elect or {}).get("races") or {}).get(key)


def elect_parts(elect, key):
    """(the "Serving now" label, the members-elect block) for one district's
    race, or ("", "") where nothing is drawn.

    WHO NOVEMBER'S ELECTION SENT, UNDER THE DISTRICT THEY WERE ELECTED FOR
    (the person's decisions of 16 October 2026). The block is drawn from
    site/members_elect.json alone, under the sitting members and never among
    them, and the sitting members get "Serving now" over them wherever one
    is drawn, which names nobody. Both carry data-elect and retire on the day
    they take office (components.until_attrs); with no file neither is
    drawn and the page is the page it was."""
    race = elect_race_of(elect, key)
    if race is None:
        return "", ""
    today = build_date.today().isoformat()
    return (C.elect_now(elect["takes_office"], today),
            C.elect_block([["", race]], elect["election"], elect["takes_office"], today))


def state_house(dist, legs, elect=None):
    """The State House card: each district the town sits in, with its
    members. A floterial district is a second district over the first, so
    the two are one card with a heading each, not two offices. Between the
    election and Organization Day each district's members-elect follow its
    sitting members (elect_parts)."""
    house = dist.get("house") or []
    if not house:
        return card("State House", '<p class="note">No House district is on '
                                   'file for this ward.</p>')
    parts = []
    for h in house:
        who = [m for m in legs
               if m.get("chamber") == "H"
               and (m.get("county") or "") == h.get("county")
               and str(m.get("district") or "") == str(h.get("district"))]
        seats = h.get("seats")
        parts.append(
            f'<h4 class="twnsub">{E(h.get("county", ""))} district '
            f'{E(str(h.get("district")))}'
            + (" (floterial)" if h.get("floterial") else "")
            + (f' <span class="twnseats">{seats} seat'
               f'{"s" if seats > 1 else ""}</span>' if seats else "")
            + "</h4>")
        if h.get("floterial"):
            parts.append('<p class="note">A floterial district overlays several '
                         'towns that each already elect their own '
                         'representative, and elects additional members across '
                         'the combined population. You are represented by '
                         'both.</p>')
        now, block = elect_parts(elect, f"H|{h.get('county')}|{h.get('district')}")
        parts.append(now + member_block(who, "No sitting member is matched to this "
                                             "district.") + block)
    return card("State House", "".join(parts))


def _and(items):
    """"17", "17 and 28", "6, 7 and 32"."""
    items = [str(i) for i in items]
    return (", ".join(items[:-1]) + " and " + items[-1]) if len(items) > 1 \
        else "".join(items)


def answer_line(dist):
    """The county and the districts, in one line above the tabs: the answer
    to "who represents me" in the words a ballot uses, before any of the
    people. "In Merrimack County. Represented in the State House by
    Merrimack districts 17 and 28, and in the State Senate by district 15."

    The county is the House district's: a House district never crosses a
    county line, so the county a town's districts carry is the town's.
    """
    house = dist.get("house") or []
    counties = []
    for h in house:
        if h.get("county") and h["county"] not in counties:
            counties.append(h["county"])
    bits = []
    if len(counties) == 1:
        c = counties[0]
        nums = [h.get("district") for h in house]
        bits.append(f"in the State House by {E(c)} "
                    f"district{'s' if len(nums) > 1 else ''} {E(_and(nums))}")
    elif house:
        bits.append("in the State House by " + E(_and(
            f"{h.get('county')} district {h.get('district')}" for h in house)))
    if dist.get("senate"):
        bits.append(f"in the State Senate by district {E(str(dist['senate']))}")
    out = (f"In {E(counties[0])} County. " if len(counties) == 1 else "")
    if bits:
        out += "Represented " + ", and ".join(bits) + "."
    return f'<p class="lead twnlede">{out.strip()}</p>' if out else ""


def representatives_sections(dist, legs, off, elect=None):
    """The Representatives tab, nearest office first: the State House, the
    State Senate, the Executive Council, the Governor, the US House and the
    US Senate. The person's order, 24 September 2026 -- the seats a town
    elects on its own ballot come before the ones the whole state does.
    The State House and the Senate carry their members-elect while there
    are any; the Governor, the Council and Congress never do (16 October
    2026: those are corrections/officials.json's, and take office in
    January)."""
    out = [state_house(dist, legs, elect)]
    sd = dist.get("senate")
    if sd:
        who = [m for m in legs if m.get("chamber") == "S"
               and str(m.get("district") or "") == str(sd)]
        now, block = elect_parts(elect, f"S|{sd}")
        out.append(card(f"State Senate &mdash; district {E(str(sd))}",
                        now + member_block(who, "No sitting senator is matched to "
                                                "this district.") + block))
    cd = dist.get("council")
    if cd:
        c = off.get("council", {})
        out.append(office_block(
            f"Executive Council — district {cd}",
            (c.get("districts") or {}).get(str(cd)),
            c.get("official_url", ""),
            " ".join(c.get("about") or [])))
    g = off.get("governor", {})
    out.append(office_block("Governor", g, g.get("official_url", ""),
                            " ".join(g.get("about") or [])))
    gd = dist.get("congress")
    if gd:
        u = off.get("us_house", {})
        out.append(office_block(
            f"US House — New Hampshire district {gd}",
            (u.get("districts") or {}).get(str(gd)),
            u.get("official_url", ""),
            " ".join(u.get("about") or [])))
    us = off.get("us_senate", {})
    seats = us.get("seats") or []
    if seats:
        # No per-seat heading. Both are elected by the whole state and both
        # represent this town, so the names are what tells them apart --
        # senate.gov lists them in seniority order and calling one "senior"
        # here would be reading more into that order than it states.
        inner = re.sub(r"</ul><ul class=\"offlist\">", "", "".join(
            office_block("", seat, us.get("official_url", ""))
            for seat in seats))
    else:
        inner = office_block("", {}, us.get("official_url", ""))
    # Under the names, the same way round as every other office here.
    if us.get("about"):
        inner += f'<p class="note">{E(" ".join(us["about"]))}</p>'
    out.append(card("US Senate", inner))
    return out


def vote_sections(town, loc, town_off):
    """The How to vote tab: where, when, the town's website and the clerk,
    in one card that spans the tab. [] where the Secretary of State's list
    and the directory have nothing for here."""
    if not (loc or town_off):
        return []
    rows = []
    if loc.get("polling_place"):
        # THE ANSWER, NOT A ROW. This was drawn exactly like the line below
        # it about the town's website -- same size, same weight, the label in
        # grey underneath -- and it is the one fact on this page that, got
        # wrong, stops somebody voting. The label goes above the address
        # rather than below it, because a reader scanning for "where do I
        # vote" needs the question before the answer, and the address itself
        # is set larger than anything else in the section.
        hours = loc.get("state_hours") or ""
        rows.append(off_row(
            E(loc["polling_place"]),
            [f'<span class="offwhen">{E(hours)}</span>'] if hours else [],
            "Where you vote", cls="offvote"))
    # A TOWN THAT VOTES IN MORE THAN ONE PLACE, BEHIND ONE LINE. Eight of
    # them -- Berlin, Derry, Farmington, Goffstown, Hudson, Merrimack, Salem
    # and Walpole -- are one town in the district file this site's pages are
    # named after and several voting wards on the Secretary of State's list,
    # so there is no ward for this page to be about and no way to ask the
    # reader which is theirs.
    #
    # Four addresses in a row was the first answer and it is three addresses
    # too many: a reader wants one. So the number is stated and the list is
    # behind it, which is the same shape as the chapter list on a bill and
    # the filter panel on a phone -- the answer first, the rest on request.
    by_ward = loc.get("polling_by_ward") or []
    # THE FALLBACK IS ON USABILITY, NOT ON EMPTINESS. This read
    # `town_officials or town_clerks`, so a town whose DoT row holds "no
    # website" or one of the seven interleaved strings got that instead of
    # the perfectly good address the clerks file had -- the first value was
    # not empty, so the second was never reached. Eleven towns' addresses
    # were on this disk and none of them was shown. Five towns now show no
    # website at all, Portsmouth among them, because every value either file
    # holds for them is mangled. That is a parser to mend, not a link to
    # guess: see parse_officials.py.
    vote_site = weblink(town_off.get("website")) or weblink(loc.get("website"))
    if vote_site:
        # Concord's is the city's website, as its officials are city officials.
        rows.append(off_row(vote_site, [], "City website"
                            if slug(town, "0") in CITIES else "Town website"))
    if loc.get("clerk"):
        rows.append(clerk_row(loc))
    if by_ward:
        inner = []
        for w in by_ward:
            hours = w.get("state_hours") or ""
            inner.append(off_row(
                E(w.get("polling_place") or ""),
                [f'<span class="offwhen">{E(hours)}</span>'] if hours else [],
                f'Ward {E(w.get("ward"))}'))
        rows.append(
            '<li class="offrow offwards"><details class="wards">'
            f'<summary>{E(town)} votes in {len(by_ward)} places, by '
            'ward &mdash; show them</summary>'
            '<ul class="offlist">' + "".join(inner) + "</ul></details></li>")
    if not rows:
        return []
    inner = '<ul class="offlist">' + "".join(rows) + "</ul>"
    if not loc.get("polling_place") and not by_ward:
        # The Secretary of State's own list is blank here, as it is for 109
        # of its 331 rows.
        inner += ('<p class="note">The Secretary of State\'s list has no '
                  'polling place recorded for here. The town clerk above is '
                  'who to ask.</p>')
    # The date is the card's heading: "Next Election: November 3, 2026" while
    # it is ahead, "Last election: November 3, 2026" after it, and "Where you
    # vote" once the town could have voted again -- see election_line.
    when = election_line(loc.get("election", ""))
    return [card(E(when) if when else "Where you vote", inner, wide=True)]


def build(town, ward, wards, dist, legs, off, base, tmpl, elect=None):
    """One town: the answer above, then a tab for each kind of thing.

    TABS, NOT ONE LONG PAGE (the person, 24 September 2026): the sections
    "just read as very cluttered and indistinct, making them hard to parse".
    Who represents the town, who runs it and how to vote in it are three
    different questions, and a reader comes with one of them. Above the tabs
    is the answer to the first in one line -- the county and the districts --
    and Representatives is the tab a page opens on.

    THE TABS ARE DATA. A tab is drawn only where the page has something to
    put in it: an unincorporated place has no town officials and no Town
    officials tab, and a town budget or a list of committees becomes a tab
    the day its data is collected, by adding it to the list below.
    """
    label = where(town, ward, wards)
    loc = (off.get("_local") or {}).get(slug(town, ward)) or {}
    town_off = (off.get("_offices") or {}).get(slug(town, "0")) or {}
    # NHDOT's "City and Town Officials of the State of New Hampshire",
    # September 2025, parsed by parse_officials.py. A city's wards share one
    # government, so these are looked up by the town's slug and not the
    # ward's -- a ward elects a councillor, and the town is what the board
    # governs.
    board = (off.get("_boards") or {}).get(slug(town, "0"))
    council = (off.get("_councils") or {}).get(slug(town, "0"))
    officials = officials_sections(
        town, slug(town, "0"), town_off,
        # The same test the How to vote tab's "Town website" row is drawn by.
        site_on_page=bool(weblink(town_off.get("website"))
                          or weblink(loc.get("website"))),
        board=board, loc=loc, council=council)
    # A city's are city officials: Concord has a mayor, not a select board.
    # THE DISTRICT MAP (Polish 3: "The map also goes on the town pages"),
    # second, after the people who represent the place, as the approved
    # drawing has it (proto/town-dover-ward-1.html); and the strip's words in
    # Title Case, as that drawing's are, so the new tab is not the one that
    # reads differently.
    panels = [("representatives", "Representatives",
               representatives_sections(dist, legs, off, elect)),
              ("map", "District Map", map_section(town, ward, dist)),
              ("officials", "City Officials" if slug(town, "0") in CITIES
               else "Town Officials", officials),
              ("vote", "How to Vote", vote_sections(town, loc, town_off)),
              # THE TOWN SERVICES TAB (24 October 2026): services_sections,
              # where its files are loaded; without them the office is the
              # Town Officials tab's card already, and the tab is not drawn.
              ("services", "City Services" if slug(town, "0") in CITIES else "Town Services",
               services_sections(
                   town, slug(town, "0"), town_off,
                   (off.get("_halls") or {}).get(slug(town, "0")),
                   None if off.get("_libraries") is None
                   else off["_libraries"].get(slug(town, "0"), {}),
                   None if off.get("_stations") is None
                   else off["_stations"].get(slug(town, "0"), {}))
               if any(off.get(k) is not None for k in ("_halls", "_libraries", "_stations"))
               else [])]

    srcs = ["NH General Court", "Secretary of State"]
    if (board or council) and officials:
        srcs.append(f"{E(town)}&rsquo;s own website")
    if town_off.get("officials") and officials:
        srcs.append(NHDOT)
    if town_off and (off.get("_libraries") or {}).get(slug(town, "0")):
        srcs.append("the Institute of Museum and Library Services")
    if town_off and ((off.get("_stations") or {}).get(slug(town, "0")) or {}).get("stations"):
        srcs.append("the Department of Environmental Services")
    if town_off and any(f.get("source") == "granit_cai" for f in
                        ((off.get("_halls") or {}).get(slug(town, "0")) or {}).get("from") or []):
        srcs.append("NH GRANIT")
    body = [f'<h1 class="offtitle">{E(label)}</h1>',
            ward_picker(town, ward, wards),
            answer_line(dist),
            tabbed(label, panels),
            '<p class="srcs">Sources: ' + ", ".join(srcs[:-1])
            + (", and " if len(srcs) > 2 else " and ") + srcs[-1] + '</p>']

    path = town_file(town, ward)
    desc = (f"Who represents {label}: state representatives, state senator, "
            "executive councilor, US representative, US senators and the "
            "governor, with how to reach each of them.")
    p = S.page(tmpl, path=path, base=base,
               # The state in the title a search result shows (the SEO review,
               # 12 October 2026): "Who represents Stark" could be anywhere.
               title=S.title_of(f"Who represents {label}, NH"),
               og_title=f"Who represents {label}, New Hampshire",
               og_image="og-town.png", og_alt="Granite Record: who represents your town",
               description=desc, globals={"GR_STATIC": True},
               noscript="", skip_label="Skip to the page", sr_title="",
               nav_current="officials.html")
    return p.replace('<div id="results"></div>',
                     '<div id="results"><div class="officials">'
                     + "".join(body) + "</div>" + TABS_JS
                     + (MAP_JS if 'id="twnmap"' in "".join(body) else "") + "</div>", 1)


def place_record(town, ward, wards, dist, legs, loc, elect=None):
    """One row of places.json: what "your town" carries round the site.

    THE SAME FACTS THE PAGE PRINTS, FROM THE SAME DATA, so the header picker
    cannot say a different district or polling place from the town's own
    page. The browser keeps only the slug ("concord-ward-4"); the rest is
    read from here when a page needs it. Members are the ones state_house
    and the Senate card match, by the same test.

    "e" IS THE PLACE'S RACES IN THE MEMBERS-ELECT FILE (16 October 2026):
    the keys its State House districts and its Senate district have there,
    in the page's order, which the My Town card draws from places.json's
    "elect" -- each race once, as "people" holds each member once. Never in
    "m", which is who sits now; and absent, with "elect", whenever there is
    no file, so the row is the row it was."""
    house = dist.get("house") or []
    m = [x.get("slug") for h in house for x in legs
         if x.get("chamber") == "H" and x.get("slug")
         and (x.get("county") or "") == h.get("county")
         and str(x.get("district") or "") == str(h.get("district"))]
    sd = dist.get("senate")
    m += [x.get("slug") for x in legs if sd and x.get("chamber") == "S"
          and x.get("slug") and str(x.get("district") or "") == str(sd)]
    rec = {"s": slug(town, ward), "n": where(town, ward, wards), "t": town,
           "u": town_path(town, ward),
           "h": [[h.get("county"), h.get("district"), 1 if h.get("floterial")
                  else 0] for h in house],
           "co": next((h.get("county") for h in house if h.get("county")), None),
           "sd": sd, "ec": dist.get("council"), "cd": dist.get("congress"),
           "m": m}
    e = [k for k in [f"H|{h.get('county')}|{h.get('district')}" for h in house]
         + ([f"S|{sd}"] if sd else []) if elect_race_of(elect, k) is not None]
    if e:
        rec["e"] = e
    if slug(town, "0") in CITIES:
        rec["c"] = 1
    if len(wards) > 1:
        rec["w"] = ward
    vote = {"poll": loc.get("polling_place"), "hours": loc.get("state_hours"),
            "clerk": loc.get("clerk"), "phone": loc.get("phone"),
            "email": loc.get("email") if maillink(loc.get("email")) else None,
            "when": election_line(loc.get("election", "")) or None,
            "wards": [[w.get("ward"), w.get("polling_place"),
                       w.get("state_hours")]
                      for w in loc.get("polling_by_ward") or []] or None}
    rec.update({k: v for k, v in vote.items() if v})
    return rec


# The map's code for a county (build_district_map.CODE): a State House
# district is "ST14", Strafford 14.
MAP_COUNTY = {"Belknap": "BE", "Carroll": "CA", "Cheshire": "CH", "Coos": "CO",
              "Grafton": "GR", "Hillsborough": "HI", "Merrimack": "ME",
              "Rockingham": "RO", "Strafford": "ST", "Sullivan": "SU"}


def map_section(town, ward, dist):
    """The District Map tab: map v1 (map.js), framed on the town, the rest of
    the state veiled, the town's own ward named first and its State House
    district chosen, with the switch between State House, State Senate,
    Executive Council and US House and the label toggle (town names by
    default). Drawn by the script the first time the tab is shown (MAP_JS);
    without it, the tabs are a page and the districts are in its first
    line.

    "ITS SITTING MEMBERS", NOT "THE MEMBERS IT ELECTED" (the person, 16
    October 2026). The fill is the sitting members' party, as it always was;
    from the day after an election the old words could be read as the
    members it has just elected, who do not sit until Organization Day. The
    Officials page's copy of this note says the same."""
    base = next((h for h in dist.get("house") or [] if not h.get("floterial")), None)
    pick = (MAP_COUNTY.get(base.get("county"), "") + str(base.get("district") or "")) \
        if base and MAP_COUNTY.get(base.get("county")) else ""
    inner = ('<p class="note">Each district colored by the party of its sitting '
             'members. Choose a kind of district, then a district on the map.</p>'
             f'<div class="twnmap" id="twnmap" data-town="{E(town)}"'
             + (f' data-ward="{E(ward)}"' if ward and ward != "0" else "")
             + (f' data-pick="{E(pick)}"' if pick else "")
             + '></div><noscript><p class="note">The map needs JavaScript; the '
             "districts are in the line above the tabs.</p></noscript>")
    return [card("The Map", inner, wide=True)]


# The map's own stylesheet and script, and its mount: the first time the
# District Map tab is shown, at the size it will have, since a map drawn into
# a hidden panel measures nothing. The page carries <base href="/">, so the
# addresses are the site root's either way.
MAP_JS = """<link rel="stylesheet" href="/map.css">
<script src="/map.js" defer></script>
<script>
(function(){
  var el=document.getElementById("twnmap"),api=null;
  if(!el)return;
  function mount(){
    if(api||!window.GRMap||el.offsetParent===null)return;
    api=GRMap.mount(el,{layer:"base",layers:["base","senate","exec","cong"],
      frame:el.dataset.town,town:el.dataset.town,ward:el.dataset.ward||null,
      pick:el.dataset.pick||null,list:false,dim:true});
  }
  addEventListener("DOMContentLoaded",mount);
  var pane=el.closest(".twnpane");
  if(pane&&window.MutationObserver)
    new MutationObserver(mount).observe(pane,{attributes:true,attributeFilter:["hidden"]});
})();
</script>"""


def tabbed(label, panels):
    """The tab strip and the panels it switches, from (id, name, [cards]).

    THE LEGISLATORS PAGE'S TABS, the same pattern: a role=tablist with a
    name, buttons with role=tab, aria-selected, aria-controls and a roving
    tabindex, panels with role=tabpanel labelled by their tab, and the same
    switching script (TABS_JS) with one addition -- the panel's id is its
    address, so /town/lyme#vote opens How to vote and a click writes the
    tab into the address without adding to the history.

    WITHOUT JAVASCRIPT EVERY PANEL IS SHOWN, in order, each under its own
    heading, and the strip is not: it is written `hidden` and the script is
    what shows it, because a row of tabs that does nothing when pressed is
    worse than no tabs. With the script running, the strip names the panel
    and the panel's own heading is for a screen reader only.

    A panel with nothing in it is not drawn and neither is its tab.
    """
    panels = [(pid, name, cards) for pid, name, cards in panels if cards]
    tabs, panes = [], []
    for i, (pid, name, cards) in enumerate(panels):
        on = i == 0
        tabs.append(
            f'<button type="button" role="tab" id="tab-{pid}" '
            f'data-pane="{pid}" aria-controls="{pid}" '
            f'aria-selected="{"true" if on else "false"}" '
            f'tabindex="{0 if on else -1}">{E(name)}</button>')
        panes.append(
            f'<div class="twnpane" id="{pid}" role="tabpanel" '
            f'aria-labelledby="tab-{pid}"><h2 class="twnph">{E(name)}</h2>'
            f'<div class="twngrid">{"".join(cards)}</div></div>')
    return (f'<div class="twntabs" role="tablist" aria-label="About '
            f'{E(label)}" hidden>' + "".join(tabs) + "</div>"
            + "".join(panes))


# THE SWITCHING SCRIPT, the legislators page's (build_pages.py, "THREE TABS,
# WHICH ARE THE ORDERING") with the address added. Inline, after the panels,
# so it runs before the page is first painted and a reader never sees three
# panels collapse into one.
#
# ONE HISTORY ENTRY PER PAGE, NOT PER CLICK: replaceState rather than
# pushState, so Back leaves the page rather than stepping through its tabs.
# A hash that names no tab -- #results, from the skip link -- is left alone
# and the first tab shown.
#
# THE ADDRESS IS WRITTEN WITH THE PAGE'S OWN PATH. The page carries
# <base href="/">, so a bare "#officials" resolves against the site's root:
# choosing "Town officials" on /town/acworth wrote /#officials into the address
# bar, and a reload, a bookmark or a link copied from there opened the home
# page (the audit of 2 October 2026, on all 320 pages). The trap is written
# down in six other places in the build; this call had been missed.
#
# HOME AND END, as the bill's and the member's tabs have them: a tab list
# answers both, and here End scrolled the page to its foot with the keyboard
# left on a tab out of sight (the review of 2 October 2026).
TABS_JS = """<script>
(function(){
  var bar=document.querySelector(".twntabs");
  if(!bar)return;
  var tabs=[].slice.call(bar.querySelectorAll("[role=tab]"));
  if(!tabs.length)return;
  function named(h){
    for(var i=0;i<tabs.length;i++)if(tabs[i].dataset.pane===h)return h;
    return null;
  }
  function show(id,write){
    tabs.forEach(function(t){
      var on=t.dataset.pane===id;
      t.setAttribute("aria-selected",String(on));
      t.tabIndex=on?0:-1;
      var pane=document.getElementById(t.dataset.pane);
      if(pane)pane.hidden=!on;
    });
    if(write&&history.replaceState)
      history.replaceState(null,"",location.pathname+location.search+"#"+id);
  }
  tabs.forEach(function(t){
    t.addEventListener("click",function(){show(t.dataset.pane,true);});
  });
  bar.addEventListener("keydown",function(e){
    var i=tabs.indexOf(document.activeElement);
    if(i<0)return;
    var j;
    if(e.key==="ArrowRight")j=(i+1)%tabs.length;
    else if(e.key==="ArrowLeft")j=(i-1+tabs.length)%tabs.length;
    else if(e.key==="Home")j=0;
    else if(e.key==="End")j=tabs.length-1;
    else return;
    e.preventDefault();
    tabs[j].focus(); show(tabs[j].dataset.pane,true);
  });
  addEventListener("hashchange",function(){
    var h=named(location.hash.slice(1));
    if(h)show(h,false);
  });
  bar.hidden=false;
  show(named(location.hash.slice(1))||tabs[0].dataset.pane,false);
})();
</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--officials", default=None,
                    help="the hand file of the other offices; corrections/officials.json "
                         "where none is given (build_members_elect.read_officials)")
    ap.add_argument("--local", default="collected/town_clerks.json",
                    help="clerks and polling places, if parsed")
    ap.add_argument("--offices", default="collected/town_officials.json",
                    help="the town's own officials, if parsed")
    ap.add_argument("--boards", default="collected/town_boards.json",
                    help="select boards read off towns' own websites, "
                         "written by town_boards.py")
    ap.add_argument("--halls", default="collected/town_halls.json",
                    help="each town office's street address, written by parse_town_halls.py")
    ap.add_argument("--libraries", default="collected/libraries.json",
                    help="each town's public libraries, written by parse_libraries.py")
    ap.add_argument("--stations", default="collected/transfer_stations.json",
                    help="each town's public transfer stations, written by "
                         "parse_transfer_stations.py")
    a = ap.parse_args()

    site = Path(a.site)
    districts = json.loads((site / "districts.json").read_text(encoding="utf-8"))
    legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
    if isinstance(legs, dict):
        legs = list(legs.values())
    off = read_officials(a.officials)
    # The clerk and the polling place, if they have been fetched. One file for
    # all 331 towns and wards, keyed by the same slug the pages are named
    # after. Absent is the normal state until somebody runs the fetch, and
    # absent means the section is not drawn rather than drawn empty.
    local = Path(a.local)
    if local.exists():
        try:
            off["_local"] = json.loads(local.read_text(encoding="utf-8"))
            print(f"  local offices: {len(off['_local'])} towns from {local}")
        except ValueError as e:
            print(f"  local offices: {local} did not parse ({e}); skipped")
    else:
        print(f"  local offices: {local} is not on disk, so the clerk and "
              "polling place section is not drawn")
    # The same contract as --local: absent means the section is not drawn
    # rather than drawn empty.
    offices = Path(a.offices)
    if offices.exists():
        try:
            off["_offices"] = json.loads(offices.read_text(encoding="utf-8"))
            n = sum(len(v.get("officials") or [])
                    for v in off["_offices"].values())
            print(f"  town officials: {len(off['_offices'])} municipalities, "
                  f"{n} named offices from {offices}")
            # WHAT IS NOT DRAWN, COUNTED. Each of these is a row or an address
            # in the file that no page shows, and a count that moves is a
            # new edition of the directory to read before publishing.
            clerks = kept = notes = wrong = 0
            for key, v in off["_offices"].items():
                offs = v.get("officials") or []
                drawn = local_offices(key, offs)
                clerks += len(offs) - len(drawn)
                kept += sum(1 for pos, o in drawn
                            if pos != (o.get("position") or ""))
                for pos, o in drawn:
                    if o.get("email") and not maillink(o["email"]):
                        notes += 1
                    elif names_someone_else(o.get("email"), o.get("name"),
                                            offs):
                        wrong += 1
            print(f"    {clerks} clerk rows not drawn (the clerk is the "
                  f"Secretary of State's), {kept} kept as Town Administrator; "
                  f"{notes} e-mail cells that are not an address and {wrong} "
                  "addresses that name another official of the town, not "
                  "linked")
        except ValueError as e:
            print(f"  town officials: {offices} did not parse ({e}); skipped")
    else:
        print(f"  town officials: {offices} is not on disk, so the "
              "\"who runs\" section is not drawn")
    # THE TOWN SERVICES TAB'S FILES (24 October 2026), on the same contract:
    # absent, the card is not drawn rather than drawn empty.
    for opt, slot, what in ((a.halls, "_halls", "town offices' street addresses"),
                            (a.libraries, "_libraries", "public libraries"),
                            (a.stations, "_stations", "transfer stations")):
        f = Path(opt)
        if not f.exists():
            print(f"  {what}: {f} is not on disk, so the Town Services tab goes without them")
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            print(f"  {what}: {f} did not parse ({e}); skipped")
            continue
        off[slot] = {k: v for k, v in data.items() if not k.startswith("_")}
        if slot == "_halls":
            n = sum(1 for v in off[slot].values() if v.get("street"))
            print(f"  town offices: {n} of {len(off[slot])} with a street address two "
                  f"sources agree on, from {f}")
        elif slot == "_libraries":
            n = sum(len(v.get("libraries") or []) for v in off[slot].values())
            print(f"  libraries: {n} in {len(off[slot])} towns, from {f}")
        else:
            n = sum(len(v.get("stations") or []) for v in off[slot].values())
            print(f"  transfer stations: {n} listings in {len(off[slot])} towns, from {f}")
    # A town's own select board, where its website lists all of it and is
    # current. Absent, every board is the directory's -- which is dated and
    # says so, so the page is still true, only older.
    boards = Path(a.boards)
    if boards.exists():
        try:
            bdata = json.loads(boards.read_text(encoding="utf-8"))
            off["_boards"] = bdata.get("boards") or {}
            off["_councils"] = bdata.get("councils") or {}
            listed = sorted(k for k, b in (off["_boards"]
                                           | off["_councils"]).items()
                            if b.get("partial"))
            print(f"  select boards: {len(off['_boards'])} towns from their "
                  f"own websites ({boards}); the rest from the directory")
            print(f"  mayors and councils: {len(off['_councils'])} of the "
                  f"{len(CITIES)} cities from their own websites; the rest "
                  "from the directory")
            print(f"  {len(listed)} shown as partial lists, labelled: "
                  f"{', '.join(listed) or 'none'}")
        except ValueError as e:
            print(f"  select boards: {boards} did not parse ({e}); every "
                  "board is the directory's")
    else:
        print(f"  select boards: {boards} is not on disk, so every board is "
              "the directory's")
    # NAMES IN CAPITALS, COUNTED: every one a town page prints in normal
    # case, by what recased it. A count that moves is a new edition of a
    # source to look at.
    #
    # THE CLERKS ARE COUNTED AS THE SECRETARY OF STATE GAVE THEM. Every one
    # is in capitals there, and parse_clerks.namecase recased them before
    # this reads the file, so counted off the clerk field they were none:
    # the count read 3, all Kensington's, and missed every clerk.
    caps = [n for n in
            [o.get("name") for v in (off.get("_offices") or {}).values()
             for o in v.get("officials") or []]
            + [v.get("clerk") for v in (off.get("_local") or {}).values()
               if isinstance(v, dict)]
            + [m.get("name") for b in ((off.get("_boards") or {})
                                       | (off.get("_councils") or {})).values()
               for m in b.get("members") or []]
            if in_capitals(n) and not VACANT.match(n or "")]
    clerk_caps = [v for v in (off.get("_local") or {}).values()
                  if isinstance(v, dict) and v.get("clerk")
                  and in_capitals(v.get("clerk_raw"))]
    print(f"  names given wholly in capitals: {len(caps)} set in normal case "
          "here, by town_boards.display_name" + (f" {caps}" if caps else "")
          + f"; {len({v['clerk_raw'] for v in clerk_caps})} clerks in "
          f"{len(clerk_caps)} rows of the Secretary of State's list, recased "
          "by parse_clerks.namecase")
    tmpl = S.template(site)
    # The members-elect, while there are any: None outside the weeks between
    # the election and Organization Day, and then nothing below draws them.
    elect = members_elect(site)

    out = site / "town"
    out.mkdir(parents=True, exist_ok=True)
    urls, places, n = [], [], 0
    for town in sorted(districts):
        wards = districts[town]
        for ward in sorted(wards, key=lambda w: int(w) if w.isdigit() else 0):
            page = build(town, ward, wards, wards[ward], legs, off,
                         a.base, tmpl, elect)
            (out / f"{slug(town, ward)}.html").write_text(S.clean_links(page),
                                                          encoding="utf-8")
            urls.append(a.base + town_path(town, ward))
            places.append(place_record(
                town, ward, wards, wards[ward], legs,
                (off.get("_local") or {}).get(slug(town, ward)) or {}, elect))
            n += 1

    # Silence is not success.
    if not n:
        raise SystemExit("No town pages were written. Is site/districts.json "
                         "built? parse_districts.py writes it.")

    named = sum(1 for k, v in off.items()
                if isinstance(v, dict) and (v.get("name") or "").strip())
    for k in ("council", "us_house"):
        named += sum(1 for d in (off.get(k, {}).get("districts") or {}).values()
                     if (d.get("name") or "").strip())
    named += sum(1 for s in (off.get("us_senate", {}).get("seats") or [])
                 if (s.get("name") or "").strip())
    print(f"{n:,} town-ward pages -> {out}/")
    # Your town (the person, 12 October 2026): the header picker's one file.
    # The people by slug, once, rather than in every row they sit for: the
    # name the chip draws and the party its colour is.
    people = {x["slug"]: [x.get("display_full") or x.get("label") or x.get("name"),
                          str(x.get("party_code") or x.get("party") or "")[:1].upper()]
              for x in legs if x.get("slug")
              and any(x["slug"] in p["m"] for p in places)}
    # THE TWO OFFICES A TOWN ELECTS THAT ARE NOT LEGISLATORS, by district, as
    # the town pages name them (corrections/officials.json): the My Town tab's
    # card says who holds each seat (the person's choice A, 14 October 2026).
    offices = {k: {d: [v.get("name") or "", str(v.get("party") or "")[:1].upper(),
                       v.get("official_url") or ""]
                   for d, v in (off.get(src, {}).get("districts") or {}).items()
                   if (v.get("name") or "").strip()}
               for k, src in (("ec", "council"), ("cd", "us_house"))}
    doc = {"places": places, "people": people, "offices": offices}
    # THE MEMBERS-ELECT OF THE RACES A PLACE NAMES IN "e", each race once,
    # with the file's two days, for the My Town card (find.js). Only while
    # there is a file: without one places.json is what it was.
    if elect:
        keys = sorted({k for p in places for k in p.get("e") or []}, key=race_order)
        doc["elect"] = {"election": elect["election"], "takes_office": elect["takes_office"],
                        "races": {k: elect["races"][k] for k in keys}}
    (site / "places.json").write_text(
        json.dumps(doc, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8")
    print(f"  places.json: {len(places)} towns and wards, "
          f"{sum(1 for p in places if p.get('poll') or p.get('wards'))} "
          "with a polling place")
    print(f"  {named} of 10 other offices name who holds them; the rest link "
          "to the official directory")

    # Added to the sitemap rather than replacing it, which would drop every
    # other URL on the site. THROUGH shell.sitemap_merge, AS THE OTHER
    # BUILDERS ADD THEIRS (the sitemap audit, 16 October 2026): the test here
    # was whether an address appeared anywhere in the file's text, which
    # takes /town/chester as listed wherever /town/chesterfield is -- eight
    # such pairs, Hampton and Hampton Falls and Concord's Ward 1 and Ward 10
    # among them -- and nothing ever took out a town this run no longer
    # writes. Every town and ward is written on every run, so this run owns
    # /town whole.
    added, dropped = S.sitemap_merge(site, a.base, urls, "/town")
    if added or dropped:
        print(f"  sitemap.xml: {added} added, {dropped} no longer written taken out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
