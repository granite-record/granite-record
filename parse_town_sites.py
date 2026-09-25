#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.7
"""
Who a New Hampshire town says holds its offices, out of the town's own pages.

    python3 parse_town_sites.py --report        # what it found, writes nothing
    python3 parse_town_sites.py --show lyme     # one town, in detail
    python3 parse_town_sites.py                 # -> town_officials_web.json

Reads only what `town_sites.py` saved under `town_sites/`. Touches no
network, so it is free to be wrong.

WHAT IT IS FOR. NHDOT's directory is an administrative contact list. Measured
against RSA 669:15 and 669:16 -- the statute's own list of the offices a town
elects -- its 1,407 rows carry 761 selectmen, 18 town clerks, one "Expert
Highway Agent", and NOT ONE moderator, supervisor of the checklist,
treasurer, tax collector, trustee of trust funds, library trustee, auditor,
constable or sewer commissioner. Ten of the thirteen statutory elected
offices appear nowhere in it. The towns publish those themselves.

THE FOUR SHAPES, each read off a real page before it was handled:

  Portsmouth   an HTML table, "Name | Title | ... | Term", with the section
               header carrying the authority ("CITY COUNCIL (City Charter,
               Art. IV)").
  Wentworth    no table at all. An office alone on a line, then a run of
               "Name, role, year" lines until the next office. Richer than it
               looks: the page marks "(appointed)" and "(Resigned 7/2024)"
               itself, so those are read rather than assumed.
  Benton       the name and the office on ONE line, hyphen-joined, with no
               heading anywhere: "William Darcy-Selectman Chair". It looks
               exactly like a heading, because it names an office, so the
               line after it ended the run and the town came out empty.
               Forty-nine towns had names and offices on the page and
               yielded nothing, and this was the largest reason.
  Bedford      a page headed "Elected Officials List" with nothing under it.
               Not a PDF, not a redirect -- a stub. It yields nothing and
               says so. Acworth is the same in a different way: 417,554 bytes
               whose roster is inside an <iframe title="Table Master">, which
               is not in the file at all.

A PAGE OF ATTENDEES IS NOT A ROSTER, and this is the guard that matters. A
survey of the 514 saved pages offered 13,113 candidate name-and-office pairs
across 141 towns -- ninety a town, for towns that elect perhaps twenty
people. Stark alone gave 1,294, because its best page was select board
meeting minutes: every name that ever attended, under a heading that says
Select Board. It has the shape of a roster and none of the meaning.

So three caps, and a page that trips any of them is rejected whole:

  a page yielding more than ROSTER_MAX pairs is not a roster;
  an office holding more than SEAT_MAX people in one run is not an office;
  a page whose link text or path carries a meeting word is not read at all,
  even though the request was already spent on it -- a request spent is not a
  reason to believe what came back.

WHAT IS NOT RECORDED, DELIBERATELY. No street addresses, and no telephone
numbers or e-mail addresses in this pass. A published official contact is
fair to record, but only against the right person: on these pages a contact
sits near a name rather than in a field with it, and a contact matched to the
wrong official is a false statement about a real person, which is the thing
this project fixes before anything else. Names, offices, roles and terms
only, and the page each came from.

`elected` IS NEVER INFERRED FROM AN OFFICE. RSA 669:15 records its own
exceptions -- the treasurer is elected "unless provision has been made for
appointment pursuant to RSA 41:26-e", highway agents likewise -- so holding
an office proves nothing about how it was filled. The flag is set only where
the page says so: a page whose own title is "Elected Officials", or a person
the page marks appointed. Everything else leaves it unset.
"""
import argparse
import collections
import datetime
import html
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
STORE = ROOT / "town_sites"
OUT = ROOT / "town_officials_web.json"

ROSTER_MAX = 80          # pairs on one page; above this it is not a roster
SEAT_MAX = 25            # people under one office heading in one run

# HOW MANY PEOPLE AN OFFICE CAN HOLD, generously. Bennington's roster page
# gave fifteen selectmen, because the page lists every board in sequence and
# the first heading stayed in force down the whole of it. RSA 41:8 has a town
# choose one selectman a year for a three-year term -- a board of three, five
# where a town has voted for five -- so fifteen is not a near miss, it is a
# run that has drifted into the next body.
#
# A run over the cap is DROPPED ENTIRELY rather than trimmed: the drift is
# somewhere inside it and there is no way to tell from the page which of the
# fifteen are the selectmen. Publishing the first three would be a guess
# wearing the clothes of a roster.
SEATS = {
    "Board of Selectmen": 5,        # RSA 41:8; five where a town has voted so
    "Moderator": 2,                 # and a moderator pro tem
    "Town Clerk": 3,                # clerk, deputy, assistant
    "City Clerk": 3,
    "Town Clerk/Tax Collector": 3,
    "Treasurer": 3,                 # treasurer and deputies
    "Tax Collector": 3,
    "Supervisor of the Checklist": 4,   # RSA 41:46-a provides for three
    "Highway Agent": 3,
    "Mayor": 2,                     # and an assistant or acting mayor
    "Auditor": 4,
    "Sewer Commissioner": 6,
    "Trustee of Trust Funds": 6,
    "Library Trustee": 12,
    "Cemetery Trustee": 8,
    "Constable": 6,
    "Fire Ward": 8,
}

# ------------------------------------------------------------- vocabulary ---
# The statutory offices (RSA 669:15 and 669:16) first, then the bodies a town
# also elects or appoints and names on the same pages. An office is only
# recognised from this list: a heading this does not know is not an office,
# which is what stops a page's section titles becoming job titles.
OFFICES = [
    ("Board of Selectmen", r"board of selectmen|select\s*board|selectmen|"
                           r"selectperson|selectman|selectwoman"),
    ("Moderator", r"\bmoderator\b"),
    ("Supervisor of the Checklist", r"supervisors?\s+of\s+the\s+checklist"),
    ("Town Clerk", r"\btown clerk\b"),
    ("City Clerk", r"\bcity clerk\b"),
    ("Town Clerk/Tax Collector", r"town clerk\s*[/&-]\s*tax collector"),
    ("Treasurer", r"\btreasurer\b"),
    ("Tax Collector", r"\btax collector\b"),
    ("Trustee of Trust Funds", r"trustees?\s+of\s+(the\s+)?trust\s+funds?"),
    ("Library Trustee", r"library trustees?"),
    ("Cemetery Trustee", r"cemetery trustees?"),
    ("Auditor", r"\bauditors?\b"),
    ("Highway Agent", r"highway agent|road agent"),
    ("Constable", r"\bconstables?\b"),
    ("Sewer Commissioner", r"sewer commissioners?"),
    ("Fire Ward", r"fire wards?"),
    ("Town Council", r"town council(?:lor|or)?s?\b"),
    ("City Council", r"city council(?:lor|or)?s?\b"),
    ("Board of Aldermen", r"board of aldermen|alderm[ae]n"),
    ("Mayor", r"\bmayor\b"),
    ("Planning Board", r"planning board"),
    ("Zoning Board of Adjustment", r"zoning board"),
    ("Budget Committee", r"budget committee"),
    ("School Board", r"school board"),
]
OFFICE_RE = [(name, re.compile(pat, re.I)) for name, pat in OFFICES]

# A role within a body, which is not itself an office.
ROLE = re.compile(
    r"\b(chair(?:man|woman|person)?|vice[\s-]?chair(?:man|woman|person)?|"
    r"clerk|secretary|ex[\s-]?officio|deputy|assistant|acting|"
    r"at[\s-]?large|ward\s*\d+|alternate|emeritus)\b", re.I)

# What the page says about how the seat was filled, in its own words.
APPOINTED = re.compile(r"\bappoint(?:ed|ment)?\b", re.I)
RESIGNED = re.compile(r"\bresign(?:ed|ation)?\b|\bdeceased\b|\bvacant\b", re.I)
TERM = re.compile(r"\b(20\d\d)\b")
# A TERM WRITTEN AS A RANGE ENDS AT ITS SECOND YEAR. Goffstown writes "Term:
# 2024 through 2027" and Rindge "2025 - 2028", and the first year was stored
# as the one the term expires -- so a board elected for 2027 read as a board
# whose terms ran out in 2024, which is the one question town_boards.py asks
# of these years.
TERM_RANGE = re.compile(r"\b(20\d\d)\s*(?:-|–|—|to|through|thru)\s*(20\d\d)\b",
                        re.I)


def term_year(text):
    """The year a term ends: the second of "2024 through 2027", or else the
    first year the text names, or None."""
    m = TERM_RANGE.search(text or "")
    if m:
        return m.group(2)
    t = TERM.search(text or "")
    return t.group(1) if t else None


# A written personal name. Two to four capitalised words, allowing an
# initial, a hyphen, an apostrophe, a quoted nickname and a suffix. Anchored
# at both ends, because a name is the whole of what it is.
#
# OR ONE OR TWO INITIALS AND THEN A NAME. Lincoln's chairman is "O.J.
# Robinson" and two of Litchfield's five are "F. Robert Leary" and "G.
# Stephen Gannon"; a name had to open with a word of two letters or more, so
# each was not a person and the line after them ended the run.
_WORD = r"[A-Z][A-Za-z'’‘-]+"
_MORE = (r"(?:\s+(?:[A-Z]\.?|[\"“][A-Za-z]+[\"”]|" + _WORD
         + r"|[A-Z][a-z]?[A-Z][A-Za-z'-]*))")
NAME = re.compile(
    r"^(?:" + _WORD + _MORE + r"{1,3}"
    r"|(?:[A-Z]\.\s?|[A-Z]\s){1,2}" + _WORD + _MORE + r"{0,2})"
    r"(?:,?\s+(?:Jr\.?|Sr\.?|I{2,3}|IV|V))?$")

# Words that disqualify a line from being a person, however capitalised it is.
# Every one of these was a false positive on the first run over Wentworth:
# "Alternate Tuesdays", "Emergency Meetings", "Infrastructure Projects",
# "Official Mailing Address:", "Physical Location Address:", "Tax Assessor",
# "Welfare Support", "Special Meetings". Two capitalised words is the shape of
# a name and also the shape of half the headings on a town website.
# Months that are also first names; see looks_like_name.
GIVEN_MONTHS = {"april", "may", "june"}

NOT_A_NAME = re.compile(
    r"\b(towns?|cit(?:y|ies)|boards?|committees?|commissions?|departments?|"
    r"offices?|halls?|streets?|roads?|avenues?|drives?|schools?|librar(?:y|ies)|"
    r"church(?:es)?|cent(?:er|re)s?|meetings?|agendas?|minutes?|hours?|"
    r"mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?|"
    r"januarys?|february|march|april|may|june|july|august|september|october|"
    r"november|december|new hampshire|nh|usa|emails?|phones?|fax|contacts?|"
    r"addresses?|locations?|mailing|physical|official|emergency|special|"
    r"infrastructure|projects?|support|welfare|assessors?|wardens?|forest|"
    r"sessions?|notices?|records?|services?|forms?|permits?|applications?|"
    r"stations?|bridges?|parks?|cemeter(?:y|ies)|trails?|maps?|fees?|"
    # The office nouns themselves, as a net under `office_of`: Lyme
    # spells a heading "Cemetary Trustees" and the misspelling matched no
    # office, so it read as a person. Nobody is called Trustees.
    r"trustees?|clerks?|agents?|collectors?|moderators?|supervisors?|"
    r"terms?|expires?|inspectors?|managers?|administrators?|chiefs?|"
    # Description lines. Benton writes what each office does under the
    # person holding it -- "Manages All Intent-to-Cut Applications" -- and
    # three capitalised words is the shape of a name.
    r"manages?|approves?|oversees?|handles?|responsible|provides?|"
    r"maintains?|issues?|collects?|administers?|coordinates?|assists?|"
    r"press to zoom|click here|learn more|view|download|"
    # Breadcrumbs. Bedford's stub page is "Departments / Town Clerk /
    # Elected Officials List / Elected Officials", and with Town Clerk
    # read as a heading the three that follow were filed as the people
    # holding it. Nobody is called Elected Officials List.
    r"officials?|elected|lists?|directory|roster|staff|overview|"
    # Agenda items and page furniture. The person, reviewing a sample,
    # marked "New Business" wrong -- published as SEABROOK'S TREASURER,
    # because the town's selectmen page carries a meeting agenda under
    # the roster and two capitalised words is the shape of a name. The
    # screen that followed found "Annual Report" as Groton's Town
    # Clerk/Tax Collector and "New Page" as Hooksett's Town Council.
    r"business|reports?|pledge|allegiance|approvals?|comments?|"
    r"hearings?|adjourn\w*|correspondence|non-?public|announcements?|"
    r"motions?|discussions?|updates?|items?|"
    # And "Council" itself, which the office-noun list above only had as
    # councillor. "Communications Council" was published as Loudon's
    # Treasurer, and it was preflight's independent word list that caught
    # it -- the parser's own vocabulary had nothing to say about it.
    r"councils?|societ(?:y|ies)|associations?|foundations?|"
    r"commissioners?|council(?:l)?ors?|alderm[ae]n|selectm[ae]n|"
    r"treasurers?|auditors?|constables?|assistants?|directors?|"
    # Headings that follow a roster, and a body that is not a person.
    # Once a member's card no longer ends the list (CARD_LINE), the line
    # after the last card is what does: Windham's "Membership Details",
    # Seabrook's "Upcoming Events" and "SEABROOK BEACH VILLAGE DISTRICT".
    r"membership|details|upcoming|events?|districts?|village|rsa|"
    r"plans?|programs?|improvements?|officers?|"
    r"read more|click|home|search|menu|login|copyright|rights reserved)\b",
    re.I)

# The same meeting words town_sites.py filters on. A page already fetched
# under the old rule is still not read.
NOISE_TEXT = re.compile(
    r"\b(minutes?|agendas?|newsletters?|meetings?|sessions?|notices?|"
    r"calendars?|archives?|packets?|videos?|recordings?|schedules?|dates?|"
    # A "Government Links" page is a list of OTHER governments. Holderness's
    # names the White House, both US Senators, the Governor and three state
    # representatives -- all real people, none of them Holderness officials.
    # Nothing was published from it only because no municipal office matched;
    # that is too narrow a margin to leave to chance.
    r"links?|"
    r"live\s*stream(ed)?)\b", re.I)

ELECTED_PAGE = re.compile(r"\belected\s+official", re.I)

# Tags that end a line of text. Everything else is inline and is removed
# without splitting, so that "Arnold D. Scheller, <b>Chairperson</b>, 2026"
# stays one line instead of becoming three.
BLOCK = re.compile(
    r"(?is)</?(p|div|li|tr|td|th|h[1-6]|br|hr|section|article|ul|ol|table|"
    r"tbody|thead|nav|header|footer|form|blockquote|dd|dt|dl)\b[^>]*>")


# ------------------------------------------------------------------ parse ---

def content_of(t):
    """The page's own content, without its navigation.

    THE MENU IS THE PROBLEM, not the roster. Wentworth's navigation sits at
    the top of the document and lists Planning Board, Select Board and Town
    Clerk/Tax Collector -- three offices -- followed by Tax Maps, Local
    Regulations, Transfer Station and Village Bridge. Read straight through,
    each office heading in the menu opened a run and the menu items after it
    were collected as the people holding it.

    Every page of this kind says where its content is: `<main>` if it has
    one, and otherwise everything that is not `<nav>`, `<header>`, `<footer>`
    or `<aside>`. That is a fact about the document rather than a list of
    phrases to exclude, so it works on towns whose menu says something else.
    """
    stripped = re.sub(r"(?is)<(nav|header|footer|aside)\b[^>]*>.*?</\1>", " ", t)
    m = re.search(r"(?is)<main\b[^>]*>(.*?)</main>", t)
    if not m:
        return stripped
    # A <main> IS NOT ALWAYS WHERE THE CONTENT IS. Acworth's page is 417,554
    # bytes and its <main> is 1,841 of them, holding the words "Town
    # Officials" and nothing else -- so preferring <main> on size alone threw
    # the whole page away and the town came out empty. Whichever of the two
    # actually carries more text is the content; on a page built the ordinary
    # way that is <main>, and on one where <main> is a shell it is not.
    def words(x):
        return len(re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", x)).strip())
    return m.group(1) if words(m.group(1)) >= words(stripped) * 0.5 else stripped


def flatten(t):
    """A page as lines, keeping an inline-formatted line in one piece."""
    t = re.sub(r"(?is)<(script|style|noscript|svg|head|select|textarea)"
               r"\b.*?</\1>", " ", t)
    t = re.sub(r"(?s)<!--.*?-->", " ", t)
    t = content_of(t)
    t = BLOCK.sub("\n", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    t = html.unescape(t)
    out = []
    for line in t.splitlines():
        line = re.sub(r"[ ​]+", " ", line)
        line = re.sub(r"\s+", " ", line).strip(" \t|")
        if line:
            out.append(line)
    return out


def office_of(s):
    """The office a line names, longest match first, or None."""
    if len(s) > 70:
        return None
    hits = [(len(m.group(0)), name)
            for name, rx in OFFICE_RE for m in [rx.search(s)] if m]
    return max(hits)[1] if hits else None


def looks_like_name(s):
    """Is this a person, rather than a heading that happens to be Title Case?

    The strongest test is not a vocabulary of forbidden words but the two
    vocabularies this file already has: a candidate that names an OFFICE is a
    heading, and one that names a ROLE is a job. "Cemetery Trustees",
    "Deputy Forest Fire Warden", "Administrative Assistant" and "Alternate
    Tuesdays" are all rejected by that alone, and no real name is.
    """
    if s.rstrip().endswith(":"):
        return False
    s = s.strip(" .,;:")
    if not (3 < len(s) <= 46):
        return False
    hit = NOT_A_NAME.search(s)
    if hit:
        # APRIL, MAY AND JUNE ARE GIVEN NAMES TOO. The months are here so that
        # "June 2026" and "March Meeting" are not people, and they took
        # Manchester's at-large alderman June Trisciani off her own city's
        # page (25 September 2026), as they had Dover's April Richer. One of
        # the three, first, before a word that is not itself excluded and in
        # a line with no digits, is a first name.
        first = s.split()[0]
        rest = s[len(first):]
        if not (first.lower() in GIVEN_MONTHS and hit.start() == 0
                and hit.end() == len(first) and rest.strip()
                and not re.search(r"\d", s) and not NOT_A_NAME.search(rest)):
            return False
    if office_of(s) or ROLE.search(s):
        return False
    # No person's first name is New, Old, Other, Annual or Public -- and each
    # of those opens a heading this project has published as a person.
    if s.split()[0].lower() in {"new", "old", "other", "annual", "public",
                                "unfinished", "general", "regular", "consent"}:
        return False
    return bool(NAME.match(s))


def name_and_office(line):
    """'William Darcy-Selectman Chair' -> ('Board of Selectmen', person).

    A FOURTH SHAPE, found on Benton's page after the first three were
    handled: the name and the office on ONE line with a hyphen between them,
    no heading anywhere. Read as a heading -- which is what it looked like,
    since it names an office -- the next line ("Town Affairs") ended the run
    and the whole town came out empty. Forty-nine towns had names and offices
    on the page and yielded nothing, and this is the largest reason.

    The split is only accepted when the left side is a name AND the right
    side is an office, which is what keeps a hyphenated surname intact:
    "Kathleen Springham-Mack" splits to "Mack", which is not an office, so
    the line is left alone.
    """
    for sep in (" - ", " – ", "-", "–", ",", "|", "•", ":"):
        if sep not in line:
            continue
        left, right = line.split(sep, 1)
        left, right = left.strip(), right.strip()
        if not right or not looks_like_name(left):
            continue
        office = office_of(right)
        if office:
            p = split_person(left + " , " + right)
            if p:
                return office, p
    return None


# "Jr." and its kind, when a comma has cut it off the name it ends.
SUFFIX_PART = re.compile(r"^(?:Jr|Sr|I{2,3}|IV)\.?$")
# A term written straight after the name, with nothing between: Harrisville
# writes "Andrea Hodson Term expires 2028", Litchfield "Dianne Plansky,
# Member Term expires March 2028".
TERM_TAIL = re.compile(r"\s+term\b.*$", re.I)


def split_person(line):
    """'Arnold D. Scheller, Chairperson, 2026' -> name, role, term, notes.

    An en dash separates as a spaced hyphen does: Dalton writes "Eric Moore
    – Term expires March 2027", and the whole line was tested as a name. So
    does a bracket: Andover writes "Dana Swenson (Chair) (2027)"."""
    parts = [p.strip() for p in re.split(r"[,•|]| [-–—] |\s+(?=\()", line)
             if p.strip()]
    if parts:
        parts[0] = TERM_TAIL.sub("", parts[0])
    if not parts or not looks_like_name(parts[0]):
        return None
    name = parts[0].strip(" .")
    # "Franklin W. Sterling, Jr." is one name, as the page wrote it.
    if len(parts) > 1 and SUFFIX_PART.match(parts[1]):
        name = f"{name}, {parts.pop(1)}"
    rest = " , ".join(parts[1:])
    role = None
    m = ROLE.search(rest)
    if m:
        role = re.sub(r"\s+", " ", m.group(0)).strip().title()
    # Off the line as written and not off `rest`: the split above cuts
    # Rindge's "2025 - 2028" at its " - " into two parts, and the range with
    # it.
    term = term_year(line)
    return {"name": name, "role": role, "term_expires": term,
            "appointed": bool(APPOINTED.search(rest)),
            "left": bool(RESIGNED.search(rest))}


# One "Name - Role" of several on a line.
_PAIR = re.compile(r"^(?P<name>[^,–-]+?)\s+[-–]\s+(?P<role>.+)$")


def several_people(line):
    """Every (part, person) on a line that names more than one, or [].

    Alstead's departments page gives its whole select board on one line:
    "Joe Levesque - Chair, Joel McCarty - Full Member, David Hogan - Full
    Member". Read as one person, the chair was the board. A line is taken
    this way only when two or more of its comma-separated parts are each a
    name, a dash and a role; a part with no name ("Chair", after "Glenn
    Elsesser - Appointed Member") belongs to the person before it.
    """
    people = []
    for part in (p.strip() for p in line.split(",")):
        m = _PAIR.match(part)
        if m and looks_like_name(m.group("name").strip()):
            p = split_person(m.group("name").strip() + " , " + m.group("role"))
            if p:
                people.append((part, p))
                continue
        m = ROLE.search(part)
        if people and m and not people[-1][1].get("role"):
            people[-1][1]["role"] = re.sub(r"\s+", " ", m.group(0)).strip().title()
    return people if len(people) >= 2 else []


def page_office(url):
    """The office a page is the page OF, read off its address's last
    segment: ".../1368/Board-of-Selectmen" is the select board's page, and
    ".../departments" is nobody's. On a body's own page a line such as
    "Charlie King, Chairman" names a member of that body even where no
    heading is in force (Farmington heads its board "Staff Contacts")."""
    path = re.sub(r"^https?://[^/]+", "", url or "").rstrip("/")
    seg = path.split("/")[-1] if path else ""
    seg = re.sub(r"\.(php|html?|aspx?)$", "", seg)
    return office_of(re.sub(r"[-_]+", " ", seg)) if seg else None


def from_tables(text, own=None):
    """(office, person) out of any table with a name column.

    `own` is the office whose page this is (see page_office). A row whose
    title is only a place on the board -- "Chuck Myette | Chairman | 2028" --
    names no office, and was dropped: Chester, Chichester, Greenfield,
    Newington and Wilton each lost their chair that way, and every one of
    them is a table on the select board's own page. On that page, with no
    section heading in the table to say otherwise, the row is the board's.
    """
    out = []
    for tab in re.findall(r"(?is)<table.*?</table>", text):
        rows = []
        for r in re.findall(r"(?is)<tr.*?</tr>", tab):
            cells = [re.sub(r"\s+", " ",
                            html.unescape(re.sub(r"(?s)<[^>]+>", " ", c))).strip()
                     for c in re.findall(r"(?is)<t[dh].*?</t[dh]>", r)]
            if any(cells):
                rows.append(cells)
        section = None
        for cells in rows:
            joined = " ".join(cells)
            # A one-cell row, or a row with no name in it, is a section header.
            named = [c for c in cells if looks_like_name(c)]
            # A cell may be a name and a role together: Strafford's chair is
            # "Lynn Sweet - Chair", Swanzey's "James Tempesta, Chairman", and
            # read as a header the row was nobody's.
            lead = None if named else next(
                ((c, q) for c in cells for q in [split_person(c)]
                 if q and q.get("role")), None)
            if not named and not lead:
                o = office_of(joined)
                if o:
                    section = o
                continue
            if lead:
                name = lead[1]["name"]
                others = " , ".join([lead[0].replace(name, "", 1)]
                                    + [c for c in cells if c is not lead[0]])
            else:
                name = named[0]
                others = " , ".join(c for c in cells if c != name)
            office = office_of(others)
            if office and REPRESENTS.search(others) and (section or own):
                office = None               # see REPRESENTS
            office = office or section
            if not office and own and MEMBER_ROLE.search(others):
                office = own
            if not office or is_staff(office, others):
                continue
            p = split_person(name + (" , " + others if others else ""))
            if p:
                out.append((office, p))
    return out


# A CivicPlus page puts the term on its own line under each person, and
# heads the roster with a bare "Members" after a paragraph about the body.
# Both look like the end of a run and neither is.
#
# THE TERM IS WRITTEN A DOZEN WAYS, and every way this did not know ended
# the run at the first member: "Term Expires: March 2027" (Boscawen,
# Greenland), "Term Expiration: 2027" (Belmont), "Term Ending: 2028" and
# "Term Exp. 2029" (Pelham), "Term-2027" (Seabrook). So anything short and
# without a digit may stand between the word and the year.
TERM_TEXT = re.compile(r"\b(term|appointed|elected)\b[^\d\n]{0,24}"
                       r"(20\d\d|\d{1,2}/\d{1,2}/\d{2,4})", re.I)
TERM_LINE = re.compile(r"^\s*" + TERM_TEXT.pattern, re.I)
# The term column of a table read as lines, under a "Term Expires" heading:
# "2027", "March 2027", "Expires 2027" (Strafford, Swanzey, Hampton). Only
# inside a run and straight under a person: Strafford's page goes on to list
# its minutes by year, "2026", "2025", "2024", and a stray year is nobody's
# term.
BARE_TERM = re.compile(r"^\s*(?:(?:term\s+)?expires?\s*:?\s*)?"
                       r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|"
                       r"dec)[a-z]*\.?\s+)?20\d\d\s*$", re.I)

# The header row of a table read as lines: Hampton's select board is "Name"
# / "Email" / "Term Expires" and then the five of them, and the header ended
# the run before the first.
TABLE_HEAD = re.compile(
    r"^\s*(?:name|title|position|e-?mail(?:\s+address)?|phone|"
    r"term(?:\s+(?:expires|expiration|ends))?|title\s*/\s*term\s+expires)"
    r"\s*:?\s*$", re.I)
MEMBERS_LINE = re.compile(
    r"^\s*(board\s+|committee\s+|commission\s+|current\s+|elected\s+)?"
    r"members(hip)?\s*[:\-]?\s*$", re.I)

# WHAT ELSE A CARD SAYS UNDER A MEMBER'S NAME, and none of it ends the run.
# Jaffrey writes each selectman as a card -- the name, "Chairman", "Email
# Charles Turcotte", "Phone: 603-532-7880 Ext. 100", "More Information" --
# and the first line of the first card that was not a name or an office
# ended the run, so one of three was read. Pelham's cards say "Contact
# Jason Croteau", Seabrook's "Read Bio" and "×", Freedom's "Town Of
# Freedom", Belmont's "Elected". Each is a way of reaching the person above
# or a word about how they were chosen; none is a person, and none is the
# end of the list.
CARD_LINE = re.compile(
    r"^\s*(?:(?:phone|tel|cell|work|home|fax|office|p|c|f)\s*[:.#]?\s*[\(\d]"
    r"|\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b"
    r"|(?:e-?mail|contact|send\s+(?:an\s+)?e-?mail)\b"
    r"|\S+@\S+\s*$|\[email[\s\xa0]protected\]"
    r"|(?:read|view)\s+(?:bio|more|profile)\s*$|more\s+information\s*$"
    r"|[×x]\s*$|elected\s*$|appointed\s*$"
    r"|(?:the\s+)?(?:town|city)\s+of\s+[A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,2}\s*$)",
    re.I)

# A LINE THAT IS ONLY A MEMBER'S PLACE ON THE BOARD, under their name:
# "Chairman", "Vice-Chair", "Board Member", "Selectmen (2029)", "Chair
# (2027)", "Member (Chair)". Belmont and Pelham put it on the line below the
# name, and it belongs to the person above -- not to the list, not to the
# next name, and not an end to either.
SEAT_LINE = re.compile(
    r"^\s*(?:(?:select\s*board|board|selectboard|full|sb)\s+)?"
    r"(?P<role>(?:vice[\s-]?)?chair(?:man|woman|person)?|member|"
    r"selectm[ae]n|selectwoman|selectperson|clerk|secretary)"
    r"\s*(?:\(\s*(?P<paren>(?:vice[\s-]?)?chair\w*|20\d\d)\s*\))?\s*$", re.I)

# THE PEOPLE WHO WORK FOR A GOVERNING BODY ARE NOT ON IT. Alstead lists its
# board and then "Misty Gratacos - Select Board Office Administrator",
# "Sharon Iozzo - Assistant Select Board Office Administrator" and "Shelley
# Steuwe - Select Board Recording Secretary": each line names the select
# board, and read as members they made six, and a board of six is over the
# cap, so the whole board was dropped. Only for the bodies that govern,
# where a staff post is never a seat; an assistant moderator or a deputy
# town clerk is an office of its own.
GOVERNING = {"Board of Selectmen", "Town Council", "City Council",
             "Board of Aldermen"}
BODY_STAFF = re.compile(
    r"\b(administrat(?:or|ive|ion)|assistant(?!\s+mayor)|"
    r"recording\s+secretary|office\s+manager|coordinator|bookkeeper|"
    r"executive\s+(?:assistant|secretary)|(?:town|city)\s+manager|staff)\b",
    re.I)

# Roles that make somebody a member of the body whose page this is, when the
# page names no office beside them: "Charlie King, Chairman" on Farmington's
# Board of Selectmen page, under a CivicPlus "Staff Contacts" heading. Not
# "clerk" or "secretary", which on these pages are as often staff -- unless
# a term year stands with it: Amherst's "Pam Coughlin | Clerk (2028)" is
# the board's clerk, elected until 2028, and no staff post has a term.
MEMBER_ROLE = re.compile(r"\b((?:vice[\s-]?)?chair(?:man|woman|person)?|"
                         r"member|selectm[ae]n|selectwoman|selectperson)\b|"
                         r"\b(?:clerk|secretary)\b\W{0,3}(?:\(\s*)?20\d\d\b",
                         re.I)

# A SEAT HELD FOR THE BODY ON ANOTHER BODY. Greenland's select board page
# lists "Stephan Toth, Planning Board Alternate Rep" under Board of
# Selectmen: he is a selectman, and the Planning Board is where he
# represents the board. The office on the line is where the person is
# sent, not what they are, so it does not take them out of the heading's
# body -- and on a planning board's page, "Jane Doe, Selectmen's Rep" is a
# member of the planning board for the same reason.
REPRESENTS = re.compile(r"\b(rep\.?|representative|liaison)\s*$|"
                        r"\b(rep\.?|representative|liaison)\s*[,(]", re.I)


def is_staff(office, text):
    """Whether a line names a staff post of a governing body: see
    BODY_STAFF."""
    return office in GOVERNING and bool(BODY_STAFF.search(text or ""))


def from_headings(lines, own=None):
    """(office, person) where an office heads a run of people.

    ATKINSON IS THE SHAPE THIS HAD TO LEARN. CivicPlus writes

        Board of Selectmen          <- the heading
        Overview
        The Board of Selectmen is the executive, managerial ...
        Meetings / 6 pm / Town Hall / 19 Academy Avenue
        Members                     <- and the roster starts here
        Wendy Barker, Chair
        Term Expires: 2027
        Peter Torosian, Vice-Chair
        Term Expires: 2028

    Under a rule that ends a run at the first line which is neither a person
    nor an office, the heading died at "Overview" and every one of those
    people was dropped. So two lines are no longer treated as the end of
    anything: a bare "Members" REOPENS the office last seen, and a "Term
    Expires: 2027" belongs to the person above it and carries their term.

    Neither weakens the guard that matters. A run still cannot cross a line
    it cannot account for, and reopening only ever restores an office the
    page has already named.

    WHAT A MEMBER'S CARD SAYS IS NOT THE END OF THE LIST EITHER. Twenty-three
    towns' own pages list their whole board and were read as listing part
    of it -- Belmont one of five, Pelham one of five, Seabrook one of three --
    because the line under the first name was "Chairman", "Phone: ...",
    "Term Expiration: 2027" or "Read Bio". Those lines now belong to the
    person above them (CARD_LINE, SEAT_LINE, TERM_LINE), and the rule that
    ends a run at a line it cannot account for is unchanged for every other
    line. `own` is the office whose page this is (page_office): on it, a
    line that gives only a place on the board -- "Charlie King, Chairman" --
    is that board's even where no heading is in force, and on no other page.
    """
    out = []
    office = None
    last_office = None
    run = 0
    # A place on the board written ABOVE the first name, not below it, means
    # the page puts titles over names; below that, a title is not the
    # person above's, and it is not guessed which name it belongs to.
    title_first = False
    for line in lines:
        if MEMBERS_LINE.match(line):
            # "Members" under the heading goes on with it (East Kingston);
            # after a heading's run has ended it reopens the last office.
            if office is None and (last_office or own):
                office, run, title_first = last_office or own, 0, False
            continue
        if out and (TERM_LINE.match(line)
                    or office and run and BARE_TERM.match(line)):
            t = term_year(line)
            if t and not out[-1][1].get("term_expires"):
                out[-1][1]["term_expires"] = t
            if APPOINTED.search(line):
                out[-1][1]["appointed"] = True
            continue
        if office and (TABLE_HEAD.match(line)
                       or run and CARD_LINE.match(line)):
            continue
        seat = SEAT_LINE.match(line) if office else None
        if seat:
            if run and not title_first:
                p = out[-1][1]
                role = (seat.group("paren") or "").strip()
                role = role if not role.isdigit() and role else seat.group("role")
                if ROLE.fullmatch(role.strip()) and not p.get("role"):
                    p["role"] = re.sub(r"\s+", " ", role).strip().title()
                if seat.group("paren") and seat.group("paren").isdigit() \
                        and not p.get("term_expires"):
                    p["term_expires"] = seat.group("paren")
            elif not run:
                title_first = True
            continue
        many = several_people(line)
        if many:
            for part, p in many:
                o = office_of(part)
                if o and REPRESENTS.search(part) and office:
                    o = None
                if (o or office) and not is_staff(o or office, part):
                    out.append((o or office, p))
                    run += 1
            continue
        # A line that is a name AND an office is a person, not a heading, and
        # it is checked first because it looks exactly like a heading.
        pair = name_and_office(line)
        if pair:
            if office and (pair[0] == office or REPRESENTS.search(line)):
                # The heading's own office on the line, or a seat held for
                # the heading's body elsewhere: the run goes on.
                if not is_staff(office, line):
                    out.append((office, pair[1]))
                    run += 1
                continue
            if not is_staff(pair[0], line):
                out.append(pair)
            office, run = None, 0
            continue
        o = office_of(line)
        # A heading is an office named by a SHORT line that is not a person.
        if o and not looks_like_name(re.split(r"[,|]", line)[0].strip()):
            # "Selectmen's Office Staff" names the select board, and heads
            # the people who work for it, not on it.
            if re.search(r"\bstaff\b", line, re.I):
                office = None
                continue
            office, last_office, run, title_first = o, o, 0, False
            continue
        if office is None:
            # A roster line, not a sentence: the role within a few words of
            # the name. Jaffrey quotes "RSA Title III, 41:8, states: Every
            # town ... shall choose ... one selectman", and a statute is not
            # a member of the board.
            p = split_person(line) if own else None
            rest = line.replace(p["name"], " ", 1) if p else ""
            rest = TERM_TEXT.sub("", rest)
            if p and len(rest) <= 30 and MEMBER_ROLE.search(rest) \
                    and not office_of(line) and not is_staff(own, line):
                out.append((own, p))
                # And the list goes on from here, as it would under a
                # "Members": Goshen names its chair "Derek Tremblay (March
                # 2027) – Chair" and its other two with a term and nothing
                # else.
                office, run, title_first = own, 1, False
            continue
        p = split_person(line)
        if p:
            # An office named on the same line as the person wins over the
            # heading above: "Deborah Ziemba, Town Clerk/Tax Collector, 2027"
            # -- unless it is where the person represents the heading's body.
            o = office_of(line)
            if o and o != office and REPRESENTS.search(line):
                o = None
            if is_staff(o or office, line):
                continue
            out.append((o or office, p))
            run += 1
            if run >= SEAT_MAX:
                office = None
        else:
            # ANYTHING THAT IS NEITHER A PERSON NOR AN OFFICE ENDS THE RUN,
            # and this is the difference between a roster and a guess. Lyme's
            # page spells a heading "Cemetary Trustees"; unrecognised, it was
            # read as a person, the Treasurer heading above it stayed in
            # force, and three members of a board were published as Treasurer
            # of the town. New Boston's sidebar -- Governing Policies, Tax
            # Breakdown, Zoning Ordinance -- did the same to its selectmen.
            #
            # A wrong office against a real person's name is the error this
            # project fixes before anything else, so the run breaks at the
            # first line it cannot account for and the people after it are
            # dropped rather than attributed. That loses real officials on
            # pages with a decorative line mid-list. Losing them is a gap;
            # keeping them is a false statement about somebody.
            office = None
    return out


def read_town(key, keep_noisy=False):
    """Every (office, person, page) this town's saved pages yield."""
    meta_path = STORE / key / "_meta.json"
    if not meta_path.exists():
        return [], []
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    found, pages = [], []
    for fn, v in sorted(meta.items(),
                        key=lambda kv: -(kv[1].get("score") or 0)):
        if v.get("kind") != "officials" or v.get("status") != 200:
            continue
        link = v.get("link_text", "")
        path = re.sub(r"[-_/.]+", " ", v.get("url", ""))
        noisy = bool(NOISE_TEXT.search(link) or NOISE_TEXT.search(path))
        if noisy and not keep_noisy:
            pages.append({"url": v.get("url"), "link_text": link,
                          "status": "not_read", "why": "a meeting page"})
            continue
        p = STORE / key / fn
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        own = page_office(v.get("url"))
        pairs = from_tables(content_of(text), own)
        if len(pairs) < 2:
            pairs = from_headings(flatten(text), own)
        # ONE PERSON NAMED TWICE ON A PAGE IS ONE SEAT. Seabrook's card
        # prints each selectman's name above the "Read Bio" link and again
        # inside the bio, so three selectmen came to six and the office was
        # over its cap. Merged before the cap is counted, keeping whatever
        # either mention said.
        merged = {}
        for o, q in pairs:
            k = (o, q["name"].lower())
            if k in merged:
                merged[k].update({f: x for f, x in q.items()
                                  if x and not merged[k].get(f)})
            else:
                merged[k] = q
        pairs = [(o, q) for (o, _n), q in merged.items()]
        rec = {"url": v.get("url"), "link_text": link,
               "read_on": v.get("read_on"), "agent": v.get("agent"),
               "sha256": v.get("sha256"), "found": len(pairs)}
        if len(pairs) > ROSTER_MAX:
            rec.update({"status": "rejected",
                        "why": f"{len(pairs)} pairs is not a roster"})
            pages.append(rec)
            continue
        # An office whose run overran what the office can hold has drifted
        # into the next body, and the drift is somewhere inside it. Drop the
        # whole run: there is no way to tell from the page which of fifteen
        # names are the three selectmen, and publishing the first three would
        # be a guess wearing the clothes of a roster.
        by_office = collections.Counter(o for o, _q in pairs)
        over = {o for o, n in by_office.items() if n > SEATS.get(o, SEAT_MAX)}
        if over:
            rec["dropped_offices"] = sorted(f"{o} ({by_office[o]})"
                                            for o in over)
            pairs = [(o, q) for o, q in pairs if o not in over]
            rec["found"] = len(pairs)
        rec["status"] = "read"
        rec["says_elected"] = bool(ELECTED_PAGE.search(link))
        pages.append(rec)
        for office, person in pairs:
            found.append((office, person, rec))
    return found, pages


def build(keys):
    today = datetime.date.today().isoformat()
    out = {}
    for key in keys:
        found, pages = read_town(key)
        people = {}
        for office, person, page in found:
            k = (person["name"].lower(), office)
            if k in people:
                continue
            rec = {
                "name": person["name"],
                "office": office,
                "role": person["role"],
                "term_expires": person["term_expires"],
                "source_url": page["url"],
                "read_on": page["read_on"],
                "method": "parse_town_sites.py over a saved page",
                "status": "published",
            }
            # The page's own words about how the seat was filled, and nothing
            # more. An office never implies an election: RSA 669:15 records
            # its own exceptions.
            if person["appointed"]:
                rec["filled_by"] = "appointed"
                rec["filled_by_source"] = "the page marks this person appointed"
            elif page.get("says_elected"):
                rec["filled_by"] = "elected"
                rec["filled_by_source"] = (
                    f"the page is titled {page['link_text']!r}")
            if person["left"]:
                rec["note"] = "the page marks this person as having left"
            people[k] = rec
        # AND THE CAP AGAIN, ACROSS THE WHOLE TOWN. Capping per page is not
        # enough: New Boston's fire wards come to nine over two pages, each
        # page under the cap on its own, and Portsmouth ends with four mayors
        # because more than one of its pages names one. A town has the seats
        # it has however many pages mention them, so the count that matters is
        # the town's, and an office over it is dropped whole for the same
        # reason as before -- there is no way to tell which of the four is the
        # mayor.
        counts = collections.Counter(r["office"] for r in people.values())
        over = {o for o, c in counts.items() if c > SEATS.get(o, SEAT_MAX)}
        kept = [r for r in people.values() if r["office"] not in over]
        out[key] = {"officials": sorted(kept,
                                        key=lambda r: (r["office"], r["name"])),
                    "pages": pages, "built": today}
        if over:
            out[key]["dropped_offices"] = sorted(
                f"{o} ({counts[o]} people, {SEATS.get(o, SEAT_MAX)} seats)"
                for o in over)
    return out


# ----------------------------------------------------------------- report ---

def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--show", nargs="*", default=None)
    a = ap.parse_args()

    keys = sorted(os.path.basename(p) for p in
                  (str(d) for d in STORE.iterdir() if d.is_dir())) \
        if STORE.exists() else []
    if a.show:
        keys = [k for k in keys if k in set(a.show)]
    if not keys:
        print("  nothing under town_sites/; run town_sites.py first")
        return 0

    data = build(keys)
    have = {k: v for k, v in data.items() if v["officials"]}
    n = sum(len(v["officials"]) for v in data.values())
    print(f"  {len(keys)} towns with saved pages")
    print(f"  {len(have)} yield at least one official; {n} people in all")
    per = sorted((len(v["officials"]), k) for k, v in data.items())
    if per:
        mid = per[len(per) // 2][0]
        print(f"  median per town {mid}, most {per[-1][0]} ({per[-1][1]})")
    offices = collections.Counter(r["office"] for v in data.values()
                                  for r in v["officials"])
    print("\n  offices found:")
    for o, c in offices.most_common():
        print(f"    {c:5d}  {o}")
    rejected = [(k, p) for k, v in data.items() for p in v["pages"]
                if p["status"] == "rejected"]
    notread = sum(1 for v in data.values() for p in v["pages"]
                  if p["status"] == "not_read")
    print(f"\n  {len(rejected)} page(s) rejected as not a roster, "
          f"{notread} not read as meeting pages")
    for k, p in rejected[:8]:
        print(f"    {k:16s} {p['why']:28s} {p['link_text'][:34]}")

    if a.show:
        for k in keys:
            print(f"\n=== {k}")
            for r in data[k]["officials"]:
                bits = [r["office"], r["name"]]
                if r["role"]:
                    bits.append(r["role"])
                if r["term_expires"]:
                    bits.append("term " + r["term_expires"])
                if r.get("filled_by"):
                    bits.append(r["filled_by"])
                print("    " + " | ".join(bits))
            for p in data[k]["pages"]:
                print(f"    [{p['status']}] {p.get('found', '-')} "
                      f"{p['link_text'][:40]!r}")
        return 0

    if a.report:
        print("\n  --report: nothing written")
        return 0
    OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"\n  wrote {OUT.name}: {len(have)} towns, {n} people")
    return 0


if __name__ == "__main__":
    sys.exit(main())
