#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.14
"""
A page per town and ward: everyone who represents the people who live there.

    python3 build_town_pages.py --site site --base https://graniterecord.org

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

The districts are derived: districts/council.txt, congress.txt, senate.txt and
house.txt are the maps, and parse_districts.py turns them into a town-ward
lookup that includes the floterial districts the General Court's own file
leaves out.

The people are not. State legislators come from the roster the rest of the
site uses. The Governor, the five councillors, the two US representatives and
the two senators come from officials.json, which is edited by hand and which
no generator writes -- a name against an office is a claim about a real
person, and it should come from somebody who checked. Where a name is blank
the page names the office, gives the reader their district and links to the
official directory, which is correct and does not go stale.
"""

import argparse
import datetime as dt
import json
import re
from pathlib import Path

import shell as S
# The parser's test for an e-mail address, so that what it accepts from a
# threaded cell and what a page links are the same test.
from parse_officials import EMAIL_OK

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


def chip(m):
    p = (m.get("party") or "X")[:1].upper()
    return f'<span class="mchip p-{E(p)}">{E(m.get("display_full") or m.get("name") or "")}</span>'


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
    """The people in a seat, each with a way to reach them."""
    if not members:
        return f'<p class="note">{E(empty)}</p>'
    out = []
    for m in members:
        link = (f'<a href="/legislator/{E(m["slug"])}">'
                f'{E(m.get("display_full") or m.get("name"))}</a>'
                if m.get("slug") else E(m.get("display_full") or m.get("name")))
        p = (m.get("party") or "X")[:1].upper()
        how = []
        if maillink(m.get("email")):
            how.append(maillink(m.get("email")))
        if m.get("phone"):
            how.append(f'<span class="offtel">{E(m["phone"])}</span>')
        out.append(off_row(f'<span class="mchip p-{E(p)}">{link}</span>',
                           how, seat))
    return '<ul class="offlist">' + "".join(out) + "</ul>"


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
    return f'<a href="mailto:{E(a)}">{E(a)}</a>'


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


def town_officials_block(town, key, town_off):
    """The '<Town> Officials' section: NHDOT's rows, the town offices, the
    note that says where they come from. "" if NHDOT names nobody here."""
    if not town_off.get("officials"):
        return ""
    body = [f'<h2 class="offsec">{E(town)} Officials</h2>']
    rows = []
    for pos, o in local_offices(key, town_off["officials"]):
        how = []
        if o.get("phone"):
            how.append(tel(o["phone"]))
        if not names_someone_else(o.get("email"), o.get("name"),
                                  town_off["officials"]):
            if maillink(o.get("email")):
                how.append(maillink(o.get("email")))
        rows.append(off_row(f'<span class="mchip">{E(o["name"])}</span>',
                            how, E(pos)))
    if rows:
        body.append('<ul class="offlist">' + "".join(rows) + "</ul>")
    how = []
    if town_off.get("phone"):
        how.append(tel(town_off["phone"]))
    if maillink(town_off.get("email")):
        how.append(maillink(town_off.get("email")))
    offices_site = weblink(town_off.get("website"))
    if offices_site:
        how.append(offices_site)
    if town_off.get("mailing") or how:
        body.append('<ul class="offlist">'
                    + off_row(E(town_off.get("mailing") or town),
                              how, "Town offices")
                    + "</ul>")
    body.append(f'<p class="note">Source: {NHDOT}. It does not show anyone '
                f'elected or appointed since then, so check {E(town)}\'s own '
                'website for changes.</p>')
    return "".join(body)


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
    return (f'<a href="{E(url)}" rel="noopener">{E(label or host)}'
            " &#8599;</a>")


def _is_address(host):
    """Whether a host is one a reader could be sent to. See weblink()."""
    return bool(host) and "." in host and " " not in host and "@" not in host


MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def election_line(raw):
    """"11/03/2026-STATE GENERAL ELECTION" as a date in a heading.

    Returns the parenthetical for the section title: "November 3rd". The year
    is added only when it is not this one, because a reader looking at a page
    in 2026 does not need to be told that November is in 2026 and does need
    to be told when it is not.

    It says "Next Election" only while the date is ahead of the build. After
    that it says "Election on file": a heading still promising "next" in
    December would be wrong about the one thing the section is for.
    """
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(.+)$", raw or "")
    if not m:
        return ""
    mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not 1 <= mm <= 12:
        return ""
    today = dt.date.today()
    when = f"{MONTHS[mm - 1]} {ordinal(dd)}"
    if yy != today.year:
        when += f", {yy}"
    ahead = (yy, mm, dd) >= (today.year, today.month, today.day)
    return f"{'Next Election' if ahead else 'Election on file'}: {when}"


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
        link = (f'<a href="{E(url)}" rel="noopener">{E(name)}</a>'
                if url else E(name))
        who = f'<span class="mchip p-{E(p)}">{link}</span>'
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
    return ((f'<h3 class="offh">{E(title)}</h3>' if title else "")
            + '<ul class="offlist">' + row + "</ul>"
            + (f'<p class="note">{E(note)}</p>' if note else ""))


def state_house(dist, legs, body):
    """The representatives, after the senator: more seats, smaller district."""
    house = dist.get("house") or []
    for h in house:
        who = [m for m in legs
               if m.get("chamber") == "H"
               and (m.get("county") or "") == h.get("county")
               and str(m.get("district") or "") == str(h.get("district"))]
        seats = h.get("seats")
        head = (f'{E(h.get("county",""))} district {h.get("district")}'
                + (f' &middot; {seats} seat{"s" if seats and seats > 1 else ""}'
                   if seats else ""))
        body.append(f'<h3 class="offh">House &mdash; {head}</h3>')
        if h.get("floterial"):
            body.append('<p class="note">A floterial district overlays several '
                        'towns that each already elect their own '
                        'representative, and elects additional members across '
                        'the combined population. You are represented by '
                        'both.</p>')
        body.append(member_block(who, "No sitting member is matched to this "
                                      "district."))
    if not house:
        body.append('<p class="note">No House district is on file for this '
                    'ward.</p>')


def build(town, ward, wards, dist, legs, off, base, tmpl):
    """One town, highest office to lowest, with the vote at the top.

    THE ORDER IS THE POINT. This page used to open with the General Court,
    because the General Court is what the rest of the site is about -- and a
    reader who comes to a page called "who represents me" is not reading an
    index of this site's coverage. They are looking up their own government,
    and it runs Governor, Council, Congress, Senate, House, town hall. What
    they came for most often is simpler still and used to be two thirds of the
    way down: where do I vote, when, and who do I ring about it.
    """
    label = where(town, ward, wards)
    loc = (off.get("_local") or {}).get(slug(town, ward)) or {}
    town_off = (off.get("_offices") or {}).get(slug(town, "0")) or {}
    body = [f'<h1 class="offtitle">{E(label)}</h1>',
            ward_picker(town, ward, wards),
            '<p class="lead">Everyone elected to represent the people who live '
            'here, and how to reach them.</p>']

    # ---- the vote, first --------------------------------------------------
    if loc or town_off:
        rows = []
        if loc.get("polling_place"):
            # THE ANSWER, NOT A ROW. This was drawn exactly like the line above
            # it about the town's website -- same size, same weight, the label
            # in grey underneath -- and it is the one fact on this page that,
            # got wrong, stops somebody voting. The label goes above the
            # address rather than below it, because a reader scanning for
            # "where do I vote" needs the question before the answer, and the
            # address itself is set larger than anything else in the section.
            hours = loc.get("state_hours") or ""
            rows.append(off_row(
                E(loc["polling_place"]),
                [f'<span class="offwhen">{E(hours)}</span>'] if hours else [],
                "Where you vote", cls="offvote"))
        # A TOWN THAT VOTES IN MORE THAN ONE PLACE, BEHIND ONE LINE. Eight of
        # them -- Berlin, Derry, Farmington, Goffstown, Hudson, Merrimack,
        # Salem and Walpole -- are one town in the district file this site's
        # pages are named after and several voting wards on the Secretary of
        # State's list, so there is no ward for this page to be about and no
        # way to ask the reader which is theirs.
        #
        # Four addresses in a row was the first answer and it is three
        # addresses too many: a reader wants one. So the number is stated and
        # the list is behind it, which is the same shape as the chapter list
        # on a bill and the filter panel on a phone -- the answer first, the
        # rest on request.
        by_ward = loc.get("polling_by_ward") or []
        # THE FALLBACK IS ON USABILITY, NOT ON EMPTINESS. This read
        # `town_officials or town_clerks`, so a town whose DoT row holds
        # "no website" or one of the seven interleaved strings got that
        # instead of the perfectly good address the clerks file had -- the
        # first value was not empty, so the second was never reached. Eleven
        # towns' addresses were on this disk and none of them was shown.
        # Five towns now show no website at all, Portsmouth among them,
        # because every value either file holds for them is mangled. That is
        # a parser to mend, not a link to guess: see parse_officials.py.
        vote_site = weblink(town_off.get("website")) or weblink(loc.get("website"))
        if vote_site:
            rows.append(off_row(vote_site, [], "Town website"))
        if loc.get("clerk"):
            how = []
            if loc.get("phone"):
                how.append(tel(loc["phone"]))
            if maillink(loc.get("email")):
                how.append(maillink(loc.get("email")))
            rows.append(off_row(
                f'<span class="mchip">{E(loc["clerk"])}</span>', how,
                "Town or city clerk"))
        if by_ward:
            inner = []
            for w in by_ward:
                hours = w.get("state_hours") or ""
                inner.append(off_row(
                    E(w.get("polling_place") or ""),
                    [f'<span class="offwhen">{E(hours)}</span>']
                    if hours else [],
                    f'Ward {E(w.get("ward"))}'))
            rows.append(
                '<li class="offrow offwards"><details class="wards">'
                f'<summary>{E(town)} votes in {len(by_ward)} places, by '
                'ward &mdash; show them</summary>'
                '<ul class="offlist">' + "".join(inner) + "</ul></details></li>")
        if rows:
            when = election_line(loc.get("election", ""))
            body.append('<h2 class="offsec">How to Vote'
                        + (f' <span class="offwhen">({E(when)})</span>'
                           if when else "")
                        + "</h2>")
            body.append('<ul class="offlist">' + "".join(rows) + "</ul>")
            if not loc.get("polling_place") and not loc.get("polling_by_ward"):
                # The Secretary of State's own list is blank here, as it is
                # for 109 of its 331 rows.
                body.append('<p class="note">The Secretary of State\'s list '
                            'has no polling place recorded for here. The town '
                            'clerk above is who to ask.</p>')

    # ---- the state executive ----------------------------------------------
    body.append('<h2 class="offsec">Executive Branch</h2>')
    g = off.get("governor", {})
    body.append(office_block("Governor of New Hampshire", g,
                             g.get("official_url", ""),
                             " ".join(g.get("about") or [])))
    cd = dist.get("council")
    if cd:
        c = off.get("council", {})
        body.append(office_block(
            f"Executive Council \u2014 district {cd}",
            (c.get("districts") or {}).get(str(cd)),
            c.get("official_url", ""),
            " ".join(c.get("about") or [])))

    # ---- the federal delegation -------------------------------------------
    body.append('<h2 class="offsec">Federal Delegation</h2>')
    us = off.get("us_senate", {})
    body.append('<h3 class="offh">US Senate</h3>')
    seats = us.get("seats") or []
    if seats:
        # No per-seat heading. Both are elected by the whole state and both
        # represent this town, so the names are what tells them apart --
        # senate.gov lists them in seniority order and calling one "senior"
        # here would be reading more into that order than it states.
        rows = [office_block("", seat, us.get("official_url", ""))
                for seat in seats]
        body.append(re.sub(r"</ul><ul class=\"offlist\">", "", "".join(rows)))
    else:
        body.append(office_block("", {}, us.get("official_url", "")))
    # Under the names, the same way round as every other office here.
    if us.get("about"):
        body.append(f'<p class="note">{E(" ".join(us["about"]))}</p>')
    gd = dist.get("congress")
    if gd:
        u = off.get("us_house", {})
        body.append(office_block(
            f"US House \u2014 New Hampshire district {gd}",
            (u.get("districts") or {}).get(str(gd)),
            u.get("official_url", ""),
            " ".join(u.get("about") or [])))

    # ---- the General Court, senator before representative -----------------
    body.append('<h2 class="offsec">Legislative Branch</h2>')
    sd = dist.get("senate")
    if sd:
        who = [m for m in legs if m.get("chamber") == "S"
               and str(m.get("district") or "") == str(sd)]
        body.append(f'<h3 class="offh">Senate &mdash; district {sd}</h3>')
        body.append(member_block(who, "No sitting senator is matched to this "
                                      "district."))
    state_house(dist, legs, body)

    # ---- the town's own offices -------------------------------------------
    # NHDOT's "City and Town Officials of the State of New Hampshire",
    # September 2025, parsed by parse_officials.py: 1,414 named offices across
    # all 234 municipalities the directory covers. A city's wards share one
    # selectboard, so these are looked up by the town's slug and not the
    # ward's -- a ward elects a councillor, and the town is what the board
    # governs.
    section = town_officials_block(town, slug(town, "0"), town_off)
    body.append(section)

    body.append('<p class="srcs">Sources: NH General Court, Secretary of '
                'State' + (f", and {NHDOT}" if section else "") + '</p>')

    path = town_file(town, ward)
    desc = (f"Who represents {label}: state representatives, state senator, "
            "executive councillor, US representative, US senators and the "
            "governor, with how to reach each of them.")
    p = S.page(tmpl, path=path, base=base,
               title=S.title_of(f"Who represents {label}"),
               og_title=f"Who represents {label}",
               og_image="og-town.png", og_alt="Granite Record: who represents your town",
               description=desc, globals={"GR_STATIC": True},
               noscript="", skip_label="Skip to the page", sr_title="",
               nav_current="legislators.html")
    return p.replace('<div id="results"></div>',
                     '<div id="results"><div class="officials">'
                     + sectionise("".join(body)) + "</div></div>", 1)


# THE SECTIONS WERE ALREADY THERE, JUST NOT IN THE MARKUP. The body is built
# as a flat run of <h2>, <ul>, <p>, <h2>, <ul>... which reads correctly and
# lays out only one way: straight down. Wrapping each heading and what follows
# it in a <section> costs nothing to the reader and lets the stylesheet put
# two of them abreast on a wide screen, which halves a page that was running
# to 2,858px.
#
# Done here rather than at the ten places that append, because those ten are
# the content and this is the shape of it -- and because a wrapper opened in
# one branch and closed in another is exactly the sort of thing that ships
# half-applied.
def sectionise(html):
    """Wrap each <h2 class="offsec"> and the blocks after it in a section."""
    parts = re.split(r'(?=<h2 class="offsec")', html)
    if len(parts) < 2:
        return html
    out = []
    for i, chunk in enumerate(parts):
        if not chunk.strip():
            continue
        if not chunk.startswith('<h2 class="offsec"'):
            # Whatever sits above the first heading -- the title and the lead.
            out.append(chunk)
            continue
        # HOW TO VOTE SPANS BOTH COLUMNS. It is the answer the reader came for
        # -- where to vote, when, and who the clerk is -- and the rest of the
        # page is the general explanation of who represents them. Putting it
        # in a column beside the Governor would bury it.
        wide = " twnwide" if "How to Vote" in chunk[:200] else ""
        out.append(f'<section class="twnsec{wide}">{chunk}</section>')
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--officials", default="officials.json")
    ap.add_argument("--local", default="town_clerks.json",
                    help="clerks and polling places, if parsed")
    ap.add_argument("--offices", default="town_officials.json",
                    help="the town's own officials, if parsed")
    a = ap.parse_args()

    site = Path(a.site)
    districts = json.loads((site / "districts.json").read_text(encoding="utf-8"))
    legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
    if isinstance(legs, dict):
        legs = list(legs.values())
    off = json.loads(Path(a.officials).read_text(encoding="utf-8"))
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
    tmpl = S.template(site)

    out = site / "town"
    out.mkdir(parents=True, exist_ok=True)
    urls, n = [], 0
    for town in sorted(districts):
        wards = districts[town]
        for ward in sorted(wards, key=lambda w: int(w) if w.isdigit() else 0):
            page = build(town, ward, wards, wards[ward], legs, off,
                         a.base, tmpl)
            (out / f"{slug(town, ward)}.html").write_text(page,
                                                          encoding="utf-8")
            urls.append(a.base + town_path(town, ward))
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
    print(f"  {named} of 10 other offices name who holds them; the rest link "
          "to the official directory")

    # Appended rather than replaced: rewriting it here would drop every other
    # URL on the site.
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{E(u)}</loc></url>\n" for u in urls
                      if E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"  {len(add.splitlines())} added to sitemap.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
