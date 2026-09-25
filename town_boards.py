#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-24.2
"""
Which towns' own websites list their select board, and which cities' their
mayor and council, as they stand now.

    python3 town_boards.py --report         # what it decides, writes nothing
    python3 town_boards.py --show lyme      # one town, with the lines it read
    python3 town_boards.py                  # -> town_boards.json

Reads what town_sites.py saved under town_sites/, through parse_town_sites.py,
and NHDOT's directory in town_officials.json. Touches no network.
build_town_pages.py reads the file this writes; it never reads town_sites/,
which is not in the repository.

WHY. Every town page showed the New Hampshire Department of Transportation's
directory of city and town officials, dated September 2025 -- before the
March 2026 town meetings, where every town elected a selectman and every
board chose its chair again. Lyme's page named Judith Brotman as chair of the
select board. Lyme's own page, read on 20 September 2026, says "Ben Kilham -
Chair until 2028 / David Kahn - Vice Chair until 2027 / Michael Hinsely -
Member until 2029", and does not name her at all.

THE RULE, the person's (24 September 2026). A town's own dated roster is the
source of truth; the directory is the fallback, shown with its date. A town's
page is used where it is CURRENT, and is marked partial where it is not
WHOLE:

  whole     as many members as the board has seats, and the number of seats
            comes from a source or is not given: the board's own page ("a
            five member Board of Selectmen"), a sentence on another of the
            town's pages that names the select board, or else the directory's
            count when that is three or five (RSA 41:8: one selectman a year
            for three years, five where a town has voted so) and the page
            does not list more. A board of four in the directory is no size.
  current   the page does not date itself before the March 2026 town
            meeting, and no member's term had ended when the page was read
            (see term_has_ended: one year stricter than "before 2026").
            Wentworth's town-officials page is headed "For the year ending
            December 2024" and gives a selectman a term ending in 2025: every
            name on it is real, and it is not the board today. Its select
            board page, saved the same night, is laid out role-first and the
            parser does not read it, so Wentworth stays on the directory.
            Lincoln's lists its chairman with a term that ended in March
            2026, and stays there too.

The page must also be the only word: a board name on another of the town's
pages that the chosen page lacks is a disagreement, and the town stays on
the directory.

And the page must say something the directory does not. A page naming
exactly the directory's board, with no date after the March 2026 meeting and
no term that began at it, is no evidence of anything newer than September
2025 -- it may simply not have been touched since. Columbia's select board
page lists Cloutier, Stohl and Campbell, as the directory did, undated and
without terms; its own minutes of 12 March 2026 swear in "newly elected
Selectman Karl Pike", and every meeting since lists Cloutier, Stohl and Pike.
Hampton Falls and Sugar Hill have the same kind of page and nothing on disk
either way, so they stay on the directory with it (see later_than_directory).

A PARTIAL LIST IS PUBLISHED, LABELLED (the person, 24 September 2026: "Show
them labeled"). "3 of 5 members listed" where the size has a source, and a
partial list without a number where it has none; the directory is not shown
in its place. This file used to keep every partial list off the page, and
the reason it gave was right: the missing name was as often one the parser
failed to read as a departed member. Read line by line, every one of the 23
towns then held back lists its whole board -- Belmont all five, where one
was read -- and the parser now reads each of them. So a partial list is
published only where the page itself gives part: a directory selectman the
page names, or any name set out like a member's among the members read,
that this did not read, keeps the town on the directory (unread_on_page).

THE CITIES FOLLOW THE SAME RULE (the person, 24 September 2026), for the
mayor and the council or board of aldermen: see decide_council.

A NAME WRITTEN WHOLLY IN CAPITALS is set in normal case for display (the
person, 24 September 2026): see display_name. Kensington's three are the
only such names on any town page today.

THE SCREEN. A name the parser read is used only if it passes every rule
below, read against the page's own line. Each was found on a real page:

  S1  only the select board. The other offices on these pages are not what
      this file decides.
  S2  no word no personal name contains: "Linked Documents", "Powered By
      Munibit" and "More Links" were all read as people.
  S4  a title is not a first name ("President Wilshire").
  S10 not someone the page marks as having left (Carroll: "Jules Marquis,
      2029 - Selectman (resigned 4/21/2026)").
  S6  not read off a page listing other bodies: judged on the address's last
      segment, because Carroll's board lives at /boards-and-committees/
      board-of-selectmen/.
  S0  the name is on its source page, as saved.
  S7  nothing but an office or a role before the name on its line: "Contact
      Leala Kullgren" and a line of minutes are not roster lines.
  S8  the line, or the short title line beside a name that stands alone,
      names no other office.
  S9  not a seat held for the board on another body: Rep, Ex Officio,
      Alternate, Liaison -- unless the line names the other body, which
      makes the person a selectman the board sent there ("Planning Board
      Rep" on Greenland's select board page).
  S5  not staff: "Select Board's Clerk", "Administrative Assistant", "Town
      Administrator" printed beside the name.
  S3  a warning, not a gate: a given name no New Hampshire list on this disk
      carries is reported for a person to look at.
  S11 one person spelled two ways in one town is one person, the fuller
      spelling kept.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import parse_town_sites as PTS

OUT = "town_boards.json"
BOARD = "Board of Selectmen"

# A term that ended before this year means the page predates the town meeting
# that filled it. The March 2026 meetings are the ones this file is for.
TERM_FLOOR = 2026
# The March 2026 town meeting, as a (year, month): a page dated before it is
# not the board that meeting chose.
MEETING = (2026, 3)

# ------------------------------------------------------------ the screen ---
# S2  words no person's name contains. Every one was read as a person off a
#     page on this disk; S3 below is the net for words not yet seen.
#     NOT "lawn" or "beach", which were here for "Lawn Care Tips" and
#     "SEABROOK BEACH VILLAGE DISTRICT" -- "care", "tips", "village" and
#     "district" still catch both -- and which are surnames: Andrew Lawn is
#     one of Jaffrey's three selectmen, and was screened off his own board.
JUNK = re.compile(
    r"\b(polic(?:y|ies)|documents?|links?|rates?|officers?|sergeant|powered|"
    r"privacy|principles|positions|plans?|article|members?|statement|events?|"
    r"credits|building|garden|district|congratulations|registrations?|"
    r"licens\w*|payments?|information|questions|residents|tips|values|"
    r"improvements|guard|program|portal|history|photos|timeline|about|"
    r"websites?|recordings?|land\s+use|assessments?|public|village|community|"
    r"current|previous|quick|useful|mission|all|dmv|faq|welcome|contact|"
    r"resources|calendar|news|online|vehicle|driver|dog|notary|voter|sewer|"
    r"commision|health|compliance|police|fire|capital|master|subc|care|"
    r"core|cadet|honor|expenditures|departmental|government|our|legislative|"
    r"guiding|civil|communication|action|rerc|basin|river|"
    r"winnipesaukee|video|upcoming|picture|munibit|understanding|historic|"
    r"wilton|stratham|seabrook)\b", re.I)

# S4  an office or a title is not a first name.
TITLE_FIRST = {"president", "mayor", "alderman", "alderwoman", "councilor",
               "councillor", "selectman", "selectwoman", "selectperson",
               "chair", "chairman", "chairwoman", "vice", "assistant",
               "deputy", "commissioner", "representative", "rep", "senator",
               "clerk", "treasurer", "officer", "sergeant", "chief",
               "director", "manager", "administrator", "health", "police",
               "fire", "notary", "judge", "hon", "honorable", "the", "town",
               "city", "board", "member", "members", "current", "all"}

# S5  staff, not a member of the board.
STAFF = re.compile(
    r"\b(administrat(?:or|ive|ion)|admin\.?|assistant|asst\.?|"
    r"recording\s+secretary|board'?s\s+clerk|select\s*board'?s\s+clerk|"
    r"selectmen'?s\s+clerk|coordinator|bookkeeper|office\s+manager|"
    r"executive\s+assistant|finance|welfare|town\s+manager|city\s+manager|"
    r"land\s+clerk|contact\s+\w+|staff)\b", re.I)

# S9  a seat on ANOTHER body held for the board.
REP = re.compile(r"\b(rep\.?|representative|ex[\s-]?officio|alternate|"
                 r"liaison)\b|selectmen[’']?s\s+rep", re.I)

# S6  a page that lists other bodies, judged on the last path segment.
LISTPAGE = re.compile(r"committee|commission|ad-hoc|joint", re.I)

# S7  what may stand before a name on a roster line.
LEAD_OK = re.compile(
    r"(?i)((assistant|deputy)\s+)?(mayor|council+or|alderm[ae]n|"
    r"selectm[ae]n|selectwoman|selectperson|chair(man|woman|person)?|"
    r"vice[\s-]?chair\w*|member|ward\s*\d+|at[\s-]large|[\s,]+)+")


def line_office(s):
    """S8: the office a line names for the person on it, or None."""
    s = (s or "").lower()
    if re.search(r"\b(assistant|deputy)\s+mayor\b", s):
        return "Council"
    if re.search(r"\bmayor\b", s):
        return "Mayor"
    if re.search(r"\bcouncil+or|\bcouncil\b", s):
        return "Council"
    if re.search(r"\balderm[ae]n\b", s):
        return "Board of Aldermen"
    if re.search(r"select", s):
        return BOARD
    return None


def last_segment(url):
    """The address's last segment, without its extension -- and the one
    before it where the last is only "index": Dover's council is at
    .../city-council/index.html."""
    path = re.sub(r"^https?://[^/]+", "", url or "").rstrip("/")
    segs = [re.sub(r"\.(php|html?|aspx?)$", "", s)
            for s in path.split("/") if s] if path else []
    while segs and segs[-1].lower() in ("index", "default"):
        segs.pop()
    return segs[-1] if segs else ""


def _titleish(s):
    """A short line that is a title and names nobody."""
    return (bool(s) and len(s) <= 45 and not s.rstrip().endswith(".")
            and not any(PTS.looks_like_name(p.strip())
                        for p in re.split(r"[,:\-–|]", s)))


def screen(office, person, page, lines):
    """(verdict, why): verdict is "keep", "reject" or "out".

    `lines` is the source page as parse_town_sites.flatten() reads it. Every
    rule is judged against the page's own words, which is why this runs here
    and not on the parsed file: the file does not keep the line.
    """
    name = person["name"]
    if office != BOARD:
        return "out", f"S1 {office!r} is not the select board"
    m = JUNK.search(name)
    if m:
        return "reject", f"S2 {m.group(0)!r} is not a word in a name"
    first = re.sub(r"[^a-z]", "", name.split()[0].lower())
    if first in TITLE_FIRST:
        return "reject", f"S4 {name.split()[0]!r} is a title, not a first name"
    if person.get("left"):
        return "reject", "S10 the page marks this person as having left"
    seg = last_segment(page.get("url"))
    link = page.get("link_text") or ""
    if LISTPAGE.search(seg) or (not seg and LISTPAGE.search(link)):
        return "reject", (f"S6 read off a list of other bodies "
                          f"({seg or link!r})")
    idx = [i for i, ln in enumerate(lines) if name in ln]
    if not idx:
        return "reject", "S0 the name is not on its source page as saved"

    # The line the name heads, where the page has one. Harrisville's select
    # board page carries its minutes above its roster -- "Select Board
    # Tuesday, September 8, 2026 Meeting Minutes Select Board: Andrew
    # Maneval, Andrea Hodson, Kathy Scott" -- and judged on the first line
    # that names them, two of its three selectmen followed other words.
    def heads(i):
        before = lines[i][:lines[i].find(name)].strip(" -:,|")
        return not before or LEAD_OK.fullmatch(before)
    i = next((j for j in idx if heads(j)), idx[0])
    line = lines[i]
    # A line that names several people is judged a person at a time, on the
    # part that is theirs: Alstead's "Joe Levesque - Chair, Joel McCarty -
    # Full Member, David Hogan - Full Member" puts two selectmen after other
    # words, and those words are the first selectman.
    for part, _p in PTS.several_people(line):
        if name in part:
            line = part
            break
    pos = line.find(name)
    before = line[:pos].strip(" -:,|")
    rest = line[pos + len(name):]
    alone = len(re.sub(r"[\W\d_]+", "", rest)) == 0 and not before
    if before and not LEAD_OK.fullmatch(before):
        return "reject", (f"S7 the name follows other words on its line "
                          f"({before[:40]!r})")
    # A name alone on its line has its title on the line beside it: ABOVE
    # when that is a short office heading (Concord: "Mayor" / "Byron
    # Champlin"), otherwise BELOW (Portsmouth: "Deaglan McEachern" / "Mayor").
    ctx, adjacent = rest, ""
    if alone:
        prv = lines[i - 1] if i else ""
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        pp = lines[i - 2] if i > 1 else ""
        # Title AFTER the name: the line above is the previous person's
        # title, because the line above that is a name.
        title_after = _titleish(prv) and PTS.looks_like_name(pp.strip())
        if _titleish(prv) and PTS.office_of(prv) and not title_after:
            ctx = prv
        elif _titleish(nxt):
            ctx = nxt
        adjacent = " ".join(s for s in (prv, nxt) if _titleish(s))
    lo = line_office(before) or line_office(ctx)
    if lo and lo != BOARD:
        return "reject", f"S8 the page's line names {lo!r} for this person"
    m = REP.search(ctx)
    # Unless the line names the OTHER body the seat is on, which makes the
    # person the board's own member sent there: Greenland's select board
    # page lists "Stephan Toth, Planning Board Alternate Rep" and "Heather
    # Droesch, Planning Board Rep" among its five. "Selectmen's Rep" names
    # the board itself, and is a seat on somebody else's list.
    elsewhere = PTS.office_of(ctx) not in (None, BOARD)
    if m and not elsewhere:
        return "reject", f"S9 a seat held for the board elsewhere ({m.group(0)!r})"
    m = STAFF.search(ctx) or STAFF.search(adjacent)
    if m:
        return "reject", f"S5 staff, not a member: the page says {m.group(0)!r}"
    return "keep", ""


# ------------------------------------------------------------ one person ---
SUFFIX = {"jr", "sr", "ii", "iii", "iv"}
NICK = [("bob", "robert"), ("rob", "robert"), ("bill", "william"),
        ("will", "william"), ("jim", "james"), ("tom", "thomas"),
        ("dick", "richard"), ("rick", "richard"), ("rich", "richard"),
        ("doug", "douglas"), ("tricia", "patricia"), ("pat", "patricia"),
        ("katie", "kathleen"), ("kathy", "kathleen"), ("kathy", "katherine"),
        ("peg", "margaret"), ("sue", "susan"), ("dan", "daniel"),
        ("mike", "michael"), ("dave", "david"), ("joe", "joseph"),
        ("chris", "christopher"), ("steve", "stephen"), ("steve", "steven"),
        ("les", "leslie"), ("arnie", "arnold"), ("ed", "edward"),
        ("ted", "edward"), ("jack", "john"), ("jeff", "jeffrey"),
        ("larry", "lawrence"), ("charlie", "charles"), ("ken", "kenneth"),
        ("nate", "nathan"), ("nate", "nathaniel"), ("matt", "matthew"),
        ("andy", "andrew"), ("ben", "benjamin"), ("jon", "jonathan")]


def given(full):
    """The first word of a name that is a given name, lower case."""
    for tok in re.sub(r"[\"“”'‘’]\w+[\"“”'‘’]", " ", full or "").split():
        t = tok.strip(",.").lower()
        if not t or re.fullmatch(r"[a-z](\.[a-z])*\.?", t) or len(t) == 1:
            continue
        if t in ("dr", "mr", "mrs", "ms", "rev"):
            continue
        return t
    return ""


def surname(full):
    toks = [t.strip(",.").lower()
            for t in re.sub(r"[\"“”][^\"“”]*[\"“”]", " ", full or "").split()]
    toks = [t for t in toks if t and t not in SUFFIX]
    return toks[-1] if toks else ""


def compatible(a, b):
    """One person spelled two ways: the same surname, given names that are
    one another's prefix, first three letters or nickname, and no middle
    initials that disagree. "Les" and "Leslie R. Babb" are; "Paul A." and
    "Paul S. Jadis" are not. A curly apostrophe is a straight one: Belmont
    writes "Travis O’Hara" and the directory "Travis O'Hara"."""
    a, b = (a or "").replace("’", "'"), (b or "").replace("’", "'")
    if surname(a) != surname(b) or not surname(a):
        return False
    ga, gb = given(a), given(b)
    ok = (ga == gb or ga.startswith(gb) or gb.startswith(ga)
          or (ga[:3] == gb[:3] and len(ga) >= 3)
          or (ga, gb) in NICK or (gb, ga) in NICK)
    if not ok:
        return False

    def mi(s):
        return [t[0].lower() for t in s.split()[1:-1]
                if re.fullmatch(r"[A-Z]\.?", t)]
    ma, mb = mi(a), mi(b)
    return not (ma and mb and ma != mb)


def _dl1(a, b):
    """At most one letter added, lost, changed or swapped."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        d = [i for i in range(len(a)) if a[i] != b[i]]
        return len(d) == 1 or (len(d) == 2 and d[1] == d[0] + 1
                               and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]])
    if len(a) > len(b):
        a, b = b, a
    return any(a == b[:i] + b[i + 1:] for i in range(len(b)))


def same_person(a, b):
    """The directory's name and the town's for one person: compatible, or
    the same surname with a given name one letter out ("Brain DuBois" is
    "Brian DuBois"), or the same given name with a long surname one letter
    out (Bristol's "Don Milbrand", whose own address is dmilbrand@, is the
    directory's "Don Millbrand"). Used to carry the directory's phone and
    e-mail to the person it belongs to, and to compare the two lists; never
    to decide who sits on a board."""
    if compatible(a, b):
        return True
    a, b = (a or "").replace("’", "'"), (b or "").replace("’", "'")
    sa, sb, ga, gb = surname(a), surname(b), given(a), given(b)
    if bool(sa) and sa == sb and len(ga) >= 4 and _dl1(ga, gb):
        return True
    return (bool(ga) and ga == gb and min(len(sa), len(sb)) >= 5
            and _dl1(sa, sb))


def in_capitals(name):
    """Whether a name is written wholly in capitals: "SARA HAMILTON", not
    "James Bailey III" or "J. R."."""
    return bool(name) and name == name.upper() and \
        bool(re.search(r"[A-Z]{2}", re.sub(r"\b(?:I{2,3}|IV)\b", "", name)))


# A word whose capitals inside it no rule can recover: MacDonald or
# Macdonald, LeBlanc or Leblanc, DiPietro or Dipietro -- both spellings are
# New Hampshire surnames -- and a particle, which is "de" to one family and
# "De" to the next. The spelling another list on disk gives decides; failing
# that the word is set in ordinary case and reported as a guess.
#
# A PREFIX RUN INTO THE NAME IS AS AMBIGUOUS AS ONE STANDING ALONE. This
# matched the particles only on their own, so DIPIETRO, DELUCA and LAFLAMME,
# which no list on disk spells, were cased the ordinary way and not reported.
# It matches Dennis and Laura too; known_spellings gives those the one
# spelling every list agrees on, so what is reported is a word no list has,
# or one two lists spell two ways.
AMBIGUOUS = re.compile(r"^(?:MAC[A-Z]{3,}|(?:DE|DI|DU|DA|LA|LE|VAN|VON)[A-Z]*)$")
# The spellings a list on disk can settle: a capital after one of these.
INTERCAP = re.compile(r"^(?:Mc|Mac|De|Di|Du|La|Le|Van|Von|Del|Da)[A-Z][a-z]")
# And the same words spelled plainly -- Leclerc, Macdonald, Deluca -- which
# are the other half of the question. Not Mc: McDonald is always McDonald.
PLAIN = re.compile(r"^(?:Mac|De|Di|Du|Da|La|Le|Van|Von)[a-z]+$")
SUFFIXES = {"JR": "Jr", "SR": "Sr"}
NUMERALS = {"II", "III", "IV", "V"}


def display_name(name, known=None, guessed=None):
    """A name as a page should print it (the person, 24 September 2026: a
    name given wholly in capitals is set in normal case). Kensington writes
    its board "SARA HAMILTON", "TOM BALABON", "IAN O'REILLY".

    Carefully, a part at a time:
      "O'REILLY", "D'ANGELO"      each side of the apostrophe: O'Reilly
      "SMITH-JONES"               each side of the hyphen: Smith-Jones
      "MCDONALD"                  Mc and a capital, always: McDonald
      "J.", "O.J.", "R"           initials stay as they are
      "JR.", "SR"                 Jr., Sr -- only after the first word
      "II", "III", "IV"           stay in capitals
      "BOB" in quotes             the nickname inside, recased: "Bob"
      "JR", "TJ" as the first     initials without their stops: JR Smith
      "MACDONALD", "LEBLANC",     no rule knows: the spelling in `known`
      "VAN", "DE" and the like    (upper -> the one spelling on disk)
                                  decides, else ordinary case; a Mac name,
                                  a particle or a word opening with one
                                  cased that way goes into `guessed` for a
                                  person to check
    A name that is not wholly in capitals is returned as it was written.
    """
    if not in_capitals(name):
        return name
    known = known or {}

    def part(p, first):
        core = p.strip(".,\"“”")
        if not core:
            return p
        at = p.find(core)
        lead, tail = p[:at], p[at + len(core):]
        if not first and core in NUMERALS:
            return p
        if not first and core in SUFFIXES:
            return lead + SUFFIXES[core] + tail
        # An initial, or initials run together with stops: "J", "O.J".
        if re.fullmatch(r"[A-Z](?:\.[A-Z])*", core):
            return p
        # Initials run together without them, as the first word: "JR
        # SMITH" is J.R. Smith, and was set as "Jr Smith". Two or three
        # capitals and no vowel are not a word, so not recased.
        if first and re.fullmatch(r"[B-DF-HJ-NP-TV-XZ]{2,3}", core):
            return p
        if core in known:
            return lead + known[core] + tail
        if re.match(r"MC[A-Z]", core):
            return lead + "Mc" + core[2] + core[3:].lower() + tail
        if AMBIGUOUS.match(core) and guessed is not None:
            guessed.append(core)
        return lead + core[0] + core[1:].lower() + tail

    out = []
    for i, w in enumerate(name.split()):
        halves = []
        for j, h in enumerate(w.split("-")):
            # The apostrophe kept, and each side of it cased on its own.
            bits = re.split(r"(['’])", h)
            halves.append("".join(
                b if b in ("'", "’") else part(b, i == 0 and j == 0 and k == 0)
                for k, b in enumerate(bits)))
        out.append("-".join(halves))
    return " ".join(out)


def known_spellings(root=Path(".")):
    """Every surname and given name whose case no rule can recover --
    McDonald, MacCleery, LeBlanc, and Leclerc beside it -- in the New
    Hampshire lists on disk, keyed by the word in capitals, where the lists
    agree on one spelling. What display_name uses before it guesses.

    A PLAIN SPELLING IS A SPELLING. Only the ones with a capital inside
    were collected, so a list's "Leclerc" never counted against another's
    "LeClerc", and one legislator's spelling decided every LECLERC.

    NOT THE CLERKS. The Secretary of State gives every clerk in capitals
    and parse_clerks.namecase recased them; its "Leclerc" is that rule's
    guess, not anybody's spelling."""
    seen = {}

    def add(full):
        for w in re.split(r"[\s\-'’\"“”,]+", full or ""):
            w = w.strip(".")
            if INTERCAP.match(w) or PLAIN.match(w):
                seen.setdefault(w.upper(), set()).add(w)

    def load(name):
        p = root / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for t in load("town_officials.json").values():
        for o in t.get("officials") or []:
            add(o.get("name"))
    for o in (load("county_officials.json") or {}).get("officers", []):
        add(o.get("name"))
    for v in load("careers.json").values():
        if isinstance(v, dict):
            add(" ".join(str(v.get(f) or "") for f in ("first", "last", "name")))
    legs = load("site/legislators.json")
    for m in (legs.values() if isinstance(legs, dict) else legs):
        add(m.get("display_full") or m.get("name") or "")
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


ROLE_SHOWN = [(re.compile(r"^vice[\s-]?chair", re.I), "Vice chair"),
              (re.compile(r"^chair", re.I), "Chair"),
              (re.compile(r"^clerk$", re.I), "Clerk"),
              (re.compile(r"^secretary$", re.I), "Secretary")]


def board_role(role):
    """The officer role a town's page gives a member, in one spelling, or ""."""
    for rx, label in ROLE_SHOWN:
        if role and rx.search(role.strip()):
            return label
    return ""


# ------------------------------------------------------------- the page ---
MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), 1)}
_MON = r"(january|february|march|april|may|june|july|august|september|" \
       r"october|november|december)"

# The ways a page dates itself, each at the START of a line of its own:
# Wentworth heads its officials page "For the year ending December 2024".
# Anchored, because the same words inside a line are nearly always the title
# of something the page links to -- Hancock's select board page lists its
# annual reports, "Year Ending December 31, 2013" and a dozen more, and a
# "Notice of Changes to all Pole Licenses... as of April 1, 2019" -- and the
# page is dated by what it says of itself, not by its archive.
_WHEN = r"(?:" + _MON + r"\s+(?:\d{1,2},?\s+)?)?(20\d\d)\b"
DATED = [
    re.compile(r"^(?:for\s+the\s+)?(?:fiscal\s+|calendar\s+)?year\s+"
               r"end(?:ing|ed)\s*:?\s*" + _WHEN, re.I),
    re.compile(r"^(?:page\s+)?(?:last\s+)?(?:updated|revised|current\s+as\s+of|"
               r"as\s+of)(?:\s+on)?\s*:?\s*" + _WHEN, re.I),
    re.compile(r"^(?:page\s+)?(?:last\s+)?(?:updated|revised|as\s+of)"
               r"(?:\s+on)?\s*:?\s*(\d{1,2})/\d{1,2}/(20\d\d|\d\d)\b", re.I),
    re.compile(r"^(?:\w+\s+){0,3}(?:town\s+|elected\s+)?officials\s+(?:for\s+)?"
               r"(20\d\d)$", re.I),
    re.compile(r"^(20\d\d)\s+(?:town\s+|elected\s+)?officials$", re.I),
]


def page_dated(lines, head=None):
    """The date a page gives itself, as (year, month, line), or None.

    `head` is how many lines come before the roster. A year's end and an
    officials list's year count only there, as a heading: below the roster
    they are the titles of reports, and Hancock lists a dozen. "Updated" and
    "as of" count anywhere, because nobody titles a document that way.

    Where it gives only a year, the month is December for a year's END
    ("for the year ending 2024") and 0 otherwise, so that "Town Officials
    2026" is not taken for a list made after the March 2026 meeting: it may
    well have been made before it. The earliest date wins.
    """
    best = None
    for i, ln in enumerate(lines):
        if len(ln) > 80:
            continue
        for n, rx in enumerate(DATED):
            if n in (0, 3, 4) and head is not None and i >= head:
                continue
            m = rx.search(ln.strip())
            if not m:
                continue
            g = [x for x in m.groups()]
            if len(g) == 2 and g[0] and g[0].isdigit():
                mon, yr = int(g[0]), int(g[1])
                yr = yr + 2000 if yr < 100 else yr
            elif len(g) == 2:
                mon = MONTHS[g[0].lower()] if g[0] else (
                    12 if "end" in m.group(0).lower() else 0)
                yr = int(g[1])
            else:
                mon, yr = 0, int(g[0])
            if best is None or (yr, mon) < best[:2]:
                best = (yr, mon, ln)
    return best


def term_has_ended(year, read_on):
    """Whether a term ending in `year` was over when the page was read.

    A select board term runs to the town meeting in March of the year it
    ends, so a page read in September 2026 that still says "Term expires
    2026" has not been changed since that meeting -- the seat was on the
    ballot and the page does not say who won it. That is one year stricter
    than "no term ended before 2026", on purpose; it moves no town today,
    because no page this file would otherwise use lists a term ending in
    2026.
    """
    try:
        ry, rm = int(read_on[:4]), int(read_on[5:7])
    except (TypeError, ValueError):
        return year < TERM_FLOOR
    return year < ry or (year == ry and rm > 3)


def elected_at_meeting(year):
    """Whether a term ending in `year` began at or after the March 2026
    meeting: a selectman's term is three years (RSA 41:8), so a term ending
    in 2029 or later is one that meeting, or a later one, filled."""
    return year >= MEETING[0] + 3


def later_than_directory(people, dboard, dated, partial=False, floor=MEETING):
    """What on the page is later than the directory, or "" for nothing.

    `dated` is page_dated()'s answer. A date counts only when it is after
    the meeting's month, since a page "updated March 2026" may predate it.
    A board that differs from the directory's by a person shows the page was
    changed since September 2025; the same people with no date and no term
    shows nothing, which is Columbia's page, one selectman out of date.

    For a `partial` list a directory name the page lacks is no evidence of
    anything: the page lists part of the board, so of course it lacks some.
    Only a person the directory does not have is. `floor` is the election
    a date must be after: the March 2026 town meeting, or a city's November
    2025 election.
    """
    if dated and dated[:2] > floor:
        return f"the page is dated {dated[2]!r}"
    new = sorted({int(p["term_expires"]) for p in people
                  if str(p.get("term_expires") or "").isdigit()
                  and elected_at_meeting(int(p["term_expires"]))})
    if new:
        return (f"a term ending {new[-1]} began at the "
                + ("2026 meeting" if floor == MEETING else "2025 election"))
    extra = [p["name"] for p in people
             if not any(same_person(o["name"], p["name"]) for o in dboard)]
    gone = [o["name"] for o in dboard
            if not any(same_person(o["name"], p["name"]) for p in people)]
    if partial:
        gone = []
    if extra or gone:
        return (f"the page names {extra} where the directory names {gone}")
    return ""


_N = r"(three|five|3|5)(?:\s*\(\s*[35]\s*\))?"
_SELECT = r"(?:select\s*board|board\s+of\s+selectmen|selectmen|selectboard)"
SIZES = {"three": 3, "3": 3, "five": 5, "5": 5}


def stated_size(lines, own_page=True):
    """The board's size where a page says it: "Andover has a five-member
    Select Board", "a three member board of selectmen", "Langdon's
    Selectboard is made up of three members", "The Select Board consists of
    5 elected members".

    `own_page` is whether these are the select board's own page. There, "a
    three member board" can only be this board; on the town's other pages
    the sentence has to name the select board, because "The Zoning Board is
    a five member board" is a sentence those pages carry too. A board's
    term -- "elected to three year terms" -- is not its size, and neither
    reading can take it for one.
    """
    text = re.sub(r"\s+", " ", " ".join(lines).lower())
    board = r"(?:select|board)" if own_page else _SELECT
    for rx in (_N + r"[\s-]+(?:member|person)\s+" + board,
               _SELECT + r"[^.]{0,40}?\b(?:consists|is\s+made\s+up|"
               r"is\s+composed|is\s+comprised)\s+of\s+" + _N +
               r"\s+(?:elected\s+|board\s+)?(?:members|selectmen|"
               r"selectpersons)\b"):
        m = re.search(rx, text)
        if m:
            return SIZES[m.group(1)]
    return None


def page_lines(key, url):
    """The saved page for this address, as the parser reads it."""
    meta = PTS.STORE / key / "_meta.json"
    if not meta.exists():
        return []
    for fn, v in json.loads(meta.read_text(encoding="utf-8")).items():
        if v.get("url") == url and v.get("kind") == "officials":
            p = PTS.STORE / key / fn
            if p.exists():
                return PTS.flatten(p.read_text(encoding="utf-8",
                                               errors="replace"))
    return []


def saved_pages(key):
    """Every saved page of the town's own that the parser reads, as
    {"url", "read_on", "lines"}: not the meeting pages it skips."""
    meta = PTS.STORE / key / "_meta.json"
    if not meta.exists():
        return []
    out = []
    for fn, v in sorted(json.loads(meta.read_text(encoding="utf-8")).items()):
        path = re.sub(r"[-_/.]+", " ", v.get("url") or "")
        if v.get("kind") != "officials" or v.get("status") != 200 or \
                PTS.NOISE_TEXT.search(v.get("link_text") or "") or \
                PTS.NOISE_TEXT.search(path):
            continue
        p = PTS.STORE / key / fn
        if p.exists():
            out.append({"url": v.get("url"), "read_on": v.get("read_on"),
                        "lines": PTS.flatten(p.read_text(encoding="utf-8",
                                                         errors="replace"))})
    return out


def town_pages(key):
    """The lines of each of the town's saved pages: where the board's size
    may be stated when its own page does not."""
    return [p["lines"] for p in saved_pages(key)]


# ------------------------------------------------------------- the town ---
def directory_board(dot):
    """NHDOT's select board rows for a town, as the directory prints them."""
    return [o for o in (dot or {}).get("officials") or []
            if (o.get("position") or "").startswith("Board of Selectman")]


# How far either side of the members read a partial list is searched for a
# name that was not read. Each card here is two to five lines.
NEAR = 6


def unread_on_page(people, dboard, lines, rejected, url):
    """The people a partial list leaves out whom its own page names.

    Two ways, because either alone let a false "4 of 5" through:

      the directory's selectmen, wherever the page names them -- written
      whole, or as a line or a comma-, dash- or bar-separated part of one
      that is the same person's name;

      any name at all among the members read, or within NEAR lines of the
      first or last of them. Amherst's page lists five, one of them "Pam
      Coughlin / Clerk (2028)", and she was not read; the directory is from
      before her election, so only her place in the list gives her away.

    A person the screen took off this page for a reason -- marked as having
    left (S10), staff (S5), a seat on another body (S9) -- is accounted for.
    """
    screened = [r["name"] for r in rejected if r.get("url") == url]
    names = [p["name"] for p in people]

    def accounted(n):
        return any(same_person(n, m) or compatible(n, m)
                   for m in names + screened)

    def parts(ln):
        # Split as split_person splits, brackets included: "Cal Carver
        # (2027)" is a name and a term.
        out = [ln.strip()] + [p.strip() for p in
                              re.split(r"[,|–]| - |\s+(?=\()", ln)]
        # A seat has the shape of a name -- Claremont's "Councilor, Ward
        # I" -- and is nobody.
        return [PTS.TERM_TAIL.sub("", p) for p in out
                if p and not (WARD.search(p) or LARGE.search(p))]
    # A line the page itself marks as staff accounts for whoever is on it:
    # Newport's "Joanne F. Dufour - Executive Assistant" stands two lines
    # above its chairman, and Goshen's former selectman Dianne Craig is now
    # its "Selectmen Office Assistant".
    roster = [ln for ln in lines if not STAFF.search(ln)]
    missed = []
    for o in dboard:
        dn = o.get("name") or ""
        if accounted(dn):
            continue
        if any(dn in ln for ln in roster) or any(
                PTS.looks_like_name(p) and same_person(dn, p)
                for ln in roster for p in parts(ln)):
            missed.append(dn)
    # A name counts only where the page gives it as a member is given: with
    # a role, a term or a seat on its line or on the line under it. A menu
    # beside the roster is made of lines with the shape of a name --
    # Claremont's "Procurement Opportunities" stands four lines above its
    # mayor -- and a roster is not.
    def member_like(ln, nxt, p):
        rest = ln.replace(p, " ", 1)
        return bool(PTS.ROLE.search(rest) or PTS.MEMBER_ROLE.search(rest)
                    or re.search(r"\b20\d\d\b", rest) or seat_of(rest)
                    or PTS.SEAT_LINE.match(nxt) or PTS.TERM_LINE.match(nxt)
                    or PTS.BARE_TERM.match(nxt) or PTS.CARD_LINE.match(nxt)
                    or seat_of(nxt))

    at = [i for i, ln in enumerate(lines) if any(n in ln for n in names)]
    if at:
        for i in range(max(0, min(at) - NEAR), min(len(lines), max(at) + NEAR + 1)):
            ln = lines[i]
            # The staff title may be the line under a name that stands
            # alone: Littleton's "Vicki Potter" / "Administrative Secretary".
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if STAFF.search(ln) or (_titleish(nxt) and STAFF.search(nxt)):
                continue
            for p in parts(ln):
                if PTS.looks_like_name(p) and not accounted(p) and \
                        p not in missed and not JUNK.search(p) and \
                        member_like(ln, nxt, p):
                    missed.append(p)
    return missed


def decide(key, found, dot, lines_of, other_pages=()):
    """What a town's own pages say about its board, and whether it is used.

    found        (office, person, page) as parse_town_sites.read_town gives
                 them
    dot          the town's NHDOT record, or None
    lines_of     url -> the page's lines
    other_pages  the lines of each of the town's saved pages, where one of
                 them may state the board's size

    Returns {"case": "own" | "directory", "why": ..., ...}. "own" carries
    the members, the source and the read date, and "partial" where the page
    lists fewer than the board's seats, or where no source gives the board's
    size at all; "directory" says why not.
    """
    dboard = directory_board(dot)
    kept, rejected = {}, []
    for office, person, page in found:
        if office != BOARD:
            continue
        url = page.get("url")
        v, why = screen(office, person, page, lines_of(url))
        if v != "keep":
            rejected.append({"name": person["name"], "why": why, "url": url})
            continue
        recs = kept.setdefault(url, {"page": page, "people": []})
        twin = next((r for r in recs["people"]
                     if compatible(r["name"], person["name"])), None)
        if twin is None:
            recs["people"].append(dict(person))
        elif len(person["name"]) > len(twin["name"]):
            # S11: the fuller spelling, keeping what either line said
            twin.update({k: v for k, v in person.items() if v}, name=person["name"])
    base = {"directory_size": len(dboard), "rejected": rejected}
    if not kept:
        return dict(base, case="directory", why="no board read off the town's pages")

    # One page, the body's own where several name the board. A name on any
    # other page that the chosen page does not carry is a disagreement, and a
    # disagreement is not a roster anybody should publish.
    def rank(url):
        seg = last_segment(url).lower()
        return (0 if re.search(r"select|board|council|aldermen", seg) else 1,
                -len(kept[url]["people"]), url)
    url = sorted(kept, key=rank)[0]
    people = kept[url]["people"]
    page = kept[url]["page"]
    lines = lines_of(url)
    others = [p["name"] for u, r in kept.items() if u != url
              for p in r["people"]
              if not any(same_person(p["name"], q["name"]) for q in people)]

    # THE BOARD'S SIZE COMES FROM A SOURCE OR IT IS NOT GIVEN (the person, 24
    # September 2026). The board's own page first; then a sentence on another
    # of the town's own pages that names the select board; then the
    # directory, where it lists three or five (RSA 41:8: a board is one or
    # the other). A directory of four, or none, is no size at all.
    size, size_from = stated_size(lines), "the page states it"
    if not size:
        for other in other_pages or ():
            size = stated_size(other, own_page=False)
            if size:
                size_from = "another of the town's pages states it"
                break
    # The directory's count is a size only while the page does not list more:
    # Littleton's page names five selectmen, two with terms the 2026 meeting
    # began, where the directory of September 2025 lists three.
    if not size and len(dboard) in (3, 5) and len(people) <= len(dboard):
        size, size_from = len(dboard), f"the directory lists {len(dboard)}"
    out = dict(base, source_url=url, read_on=page.get("read_on"),
               read=len(people), size=size, size_from=size_from if size else "",
               members=[{"name": p["name"], "role": p.get("role"),
                         "term_ends": p.get("term_expires")} for p in people])

    at = [i for i, ln in enumerate(lines)
          if any(p["name"] in ln for p in people)]
    dated = page_dated(lines, head=min(at) if at else None)
    ended = sorted({int(p["term_expires"]) for p in people
                    if p.get("term_expires")
                    and term_has_ended(int(p["term_expires"]),
                                       page.get("read_on"))})
    if dated and dated[:2] < MEETING:
        return dict(out, case="directory", stale=True,
                    why=f"the page dates itself {dated[0]}: {dated[2]!r}")
    if ended:
        return dict(out, case="directory", stale=True,
                    why=f"a term on the page ended in {ended[0]}")
    if others:
        return dict(out, case="directory",
                    why=f"another of the town's pages names {others}")
    if size and len(people) > size:
        return dict(out, case="directory",
                    why=f"{len(people)} names read for a board of {size}")
    # A PAGE THAT LISTS PART OF THE BOARD IS SHOWN, LABELLED (the person, 24
    # September 2026: "Show them labeled"), with how many of the board's
    # seats it lists where the size has a source, and as a partial list
    # without a number where it has none. The directory is not shown in its
    # place: the names the town gives are its own and newer.
    #
    # BUT ONLY A PARTIAL LIST THE PAGE GIVES, never one this file failed to
    # read. Every one of the 23 towns this rule was written for turned out,
    # read line by line, to list its whole board -- Belmont all five, where
    # one was read -- and "1 of 5 members listed" under Belmont's name
    # would have been false about Belmont. So a directory selectman whom the
    # page names, and who was neither read nor marked as having left, means
    # the list is ours and not the town's, and the town stays on the
    # directory until the parser reads its page.
    partial = not size or len(people) < size
    if partial:
        missed = unread_on_page(people, dboard, lines, rejected, url)
        if missed:
            return dict(out, case="directory", unread=missed,
                        why=f"the page names {missed}, whom this did not read "
                            "as members")
    later = later_than_directory(people, dboard, dated, partial=partial)
    if not later:
        return dict(out, case="directory", unproven=True,
                    why="the directory's own board, with no date or term on "
                        "the page to show it changed after the March 2026 "
                        "meeting")
    out["later"] = later
    if partial:
        out["partial"] = True
    # The directory's name for each member, where it has the same person,
    # so the page can carry the phone and e-mail the directory gives them.
    for m in out["members"]:
        twin = [o["name"] for o in dboard if same_person(o["name"], m["name"])]
        m["directory_name"] = twin[0] if len(twin) == 1 else None
    return dict(out, case="own", why="")


# ------------------------------------------------------------ the cities ---
# THE CITIES FOLLOW THE SAME RULE (the person, 24 September 2026: "Should
# the 13 cities follow the same rule as towns (the city's own site
# first)?" -- "Yes"). A city is governed by a mayor and a council or board
# of aldermen, and every one of them held an election after the directory's
# September 2025 edition: the thirteen in November 2025, Lebanon in March
# 2026. Dover's page names Dennis Shanahan as mayor, from 5 January 2026;
# the directory still names Robert Carrier.
#
# NEW HAMPSHIRE'S THIRTEEN CITIES, named rather than inferred: read off the
# directory's labels, Hooksett came out a city because NHDOT calls its town
# councillors "City Councilor". build_town_pages.py reads this list too.
CITIES = frozenset({"berlin", "claremont", "concord", "dover", "franklin",
                    "keene", "laconia", "lebanon", "manchester", "nashua",
                    "portsmouth", "rochester", "somersworth"})
# The November 2025 municipal elections, as a (year, month): a city page
# dated before them is not the council they chose.
CITY_ELECTION = (2025, 11)

_NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18}
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
          "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}
MAYOR_WORD = re.compile(r"\b(?:(assistant|deputy)\s+)?mayor\b", re.I)
SEAT_WORD = re.compile(r"\b(?:(?:assistant|deputy)\s+)?mayor\b|"
                       r"\bcouncil+(?:or|man|woman|member)s?\b|"
                       r"\balder(?:m[ae]n|woman|person)s?\b", re.I)
# A heading over several people, not one person's seat: "Ward Councilors",
# "At-Large Councilors", "Councilors", "Aldermen".
GROUP_WORD = re.compile(r"\bcouncil+(?:or|member)s\b|\baldermen\b", re.I)
WARD = re.compile(r"\bward\s+(\d{1,2}|" + "|".join(_NUMS) + r"|[ivx]{1,4})\b",
                  re.I)
LARGE = re.compile(r"\bat[\s-]*large\b", re.I)
DISTRICT = re.compile(r"\bdistrict\s+(\d{1,2})\b", re.I)
OFFICER = re.compile(r"\b(vice[\s-]?president|president|vice[\s-]?chair|"
                     r"chair)\w*\b", re.I)
# What stands before a name on a line that gives the seat first: "Mayor -
# Mike Bordes", "Assistant Mayor Devin R. Wilkie", "Councilor Kellen
# Appleton", "Ward 1 - James Ravan", Keene's "Mayor Jay Kahn" and Nashua's
# "Meet Mayor Jim Donchess".
SEAT_LEAD = re.compile(
    r"^(?:meet\s+)?(?:(?:(?:assistant|deputy)\s+)?mayor|council+or|"
    r"alder(?:man|woman)|ward\s+\S+)\s*[-–:]?\s+", re.I)


def ward_number(text):
    m = WARD.search(text or "")
    if not m:
        return None
    w = m.group(1).lower()
    return int(w) if w.isdigit() else _NUMS.get(w) or _ROMAN.get(w)


def seat_of(text, strict=True):
    """The seat a piece of text gives, as {"seat", "role"}, or None.

    "Councilor, Ward III" is Ward 3; "Alderman-At-Large Vice President" is
    at large, and vice president; "Mayor, Ward 1 (Term Expires: 3/27)" is
    the mayor, who in Lebanon also holds a ward seat; "City Councilor" is a
    seat with nothing more to say about it.

    `strict`: the text must say mayor, councillor or alderman. A ward alone
    is not a council seat -- Portsmouth lists each ward's registrar, clerk
    and moderator under "Ward 1" -- and is taken for one only under a
    heading that says council (Concord's "Ward Councilors" over "Brent
    Todd, Ward One").
    """
    t = text or ""
    if not (SEAT_WORD.search(t) or WARD.search(t) or LARGE.search(t)):
        return None
    if strict and not SEAT_WORD.search(t):
        return None
    bits = []
    m = MAYOR_WORD.search(t)
    if m:
        bits.append(f"{m.group(1).title()} mayor" if m.group(1) else "Mayor")
    w = ward_number(t)
    if w:
        bits.append(f"Ward {w}")
    elif LARGE.search(t):
        bits.append("at large" if bits else "At large")
    elif DISTRICT.search(t):
        bits.append(f"District {DISTRICT.search(t).group(1)}")
    r = OFFICER.search(t)
    return {"seat": ", ".join(bits),
            "role": re.sub(r"\s+|-", " ", r.group(1)).capitalize() if r else ""}


def _named(text):
    """The name a short piece of text is, or "". A seat is not a name,
    though "Ward I" has the shape of one."""
    t = (text or "").strip(" ,-–:|")
    if t.endswith(".") and not re.search(r"\b(?:Jr|Sr|[A-Z])\.$", t):
        t = t[:-1]
    if SEAT_WORD.search(t) or WARD.search(t) or LARGE.search(t):
        return ""
    return t if PTS.looks_like_name(t) and not JUNK.search(t) and \
        re.sub(r"[^a-z]", "", t.split()[0].lower()) not in TITLE_FIRST else ""


def _seat_only(line, strict=True):
    """A short line that gives a seat and names nobody -- not "Assistant
    Mayor Devin R. Wilkie", whose seat comes first and whose name follows."""
    if len(line) > 70 or not seat_of(line, strict):
        return False
    if SEAT_LEAD.match(line) and _named(line[SEAT_LEAD.match(line).end():]):
        return False
    return not any(_named(p) for p in re.split(r"[,|–:]| - ", line))


def _on_one_line(line, strict=True):
    """(name, seat text) where one line gives both, or None: "Brent Todd,
    Ward One", "Mayor - Mike Bordes", "Councilor Kellen Appleton"."""
    if len(line) > 90:
        return None
    m = SEAT_LEAD.match(line)
    if m and _named(line[m.end():]) and seat_of(m.group(0), strict):
        return _named(line[m.end():]), m.group(0)
    for sep in (",", " - ", " – ", "|"):
        if sep in line:
            left, right = line.split(sep, 1)
            if _named(left) and seat_of(right, strict) and len(right) <= 60:
                return _named(left), right
    return None


def _ends_term(line):
    """The year a line says a term ENDS in, or None: "Term End: 1/3/2028",
    "2026-2027", "Councilor Ward 1 – 2026 to 2027". Not "Term Begin"."""
    if re.search(r"\bbegin", line, re.I):
        return None
    if re.search(r"\bterm\b.*\b(end|expir)", line, re.I) or \
            PTS.TERM_RANGE.search(line):
        # A month and a year of two figures: Lebanon's "Term Expires: 3/27"
        # is March 2027, the city's elections being in March and its terms
        # two years. A third figure would make it a day, so not this.
        short = re.search(r"\b(?:end|expir)\w*\s*:?\s*\d{1,2}/(\d\d)\b(?!/)",
                          line, re.I)
        return PTS.term_year(line) or (f"20{short.group(1)}" if short
                                       else None)
    return None


# A line in a member's card that is no end to the list: a phone, an
# address, "Contact Dale", "Submit", Dover's "hideThis" and "2 year".
CITY_CARD = re.compile(
    r"^\s*(?:tel|address|role|term\s+\w+)\s*:|^\s*(?:submit|hidethis|"
    r"email this person|a copy of this message.*|\d\s+years?|member info|"
    r"contact info|public body|your search found members|member:.*|"
    r"(?:vice[\s-]?)?chair:.*)\s*$|^\s*\(?[\w.+-]+@[\w.-]+\)?\s*$", re.I)


def read_council(lines):
    """Every member a city's council page lists, in its order, as
    {"name", "seat", "role", "term_expires", "at"} (`at`: the line).

    The layouts it was written from, one city each:

      Concord     a seat over names: "Mayor" / "Byron Champlin", "At-Large
                  Councilors" / four names, and "Brent Todd, Ward One"
      Claremont   the seat under the name: "Dale Girard" / "Mayor", then a
                  phone, "Contact Dale", an address and a form
      Laconia     "Mayor - Mike Bordes", "Jon Hildreth, Ward 1"
      Lebanon     "Mayor Douglas Whittlesey", and again lower down as
                  "Douglas Whittlesey" / "Mayor, Ward 1 (Term Expires: 3/27)"
      Keene       "Ward 1" / "Jacob R. Favolise" / "Councilor Ward 1 – 2026
                  to 2027" -- the seat under the name wins over the heading
      Nashua      "Lori Wilshire" / "Alderman-At-Large President", "Ward 1 -
                  James Ravan" / "Alderman - Ward 1"
      Portsmouth  "Deaglan McEachern" / "Mayor", "Kate Cook" / "City
                  Councilor"
      Dover       the first name, the surname and "Role: Mayor", each on a
                  line of its own

    A name under a heading takes the heading's seat only while nothing but
    names and their cards follow it; anything else ends it, as a run ends in
    parse_town_sites.from_headings. A seat under a name that is a heading
    over several ("Ward Councilors", plural) is not that name's seat.
    """
    out, heading = [], None

    def add(i, name, seat_text, extra=""):
        s = seat_of(seat_text, strict=False) or {"seat": "", "role": ""}
        more = seat_of(extra) or {"seat": "", "role": ""}
        rec = {"name": name, "seat": s["seat"] or more["seat"],
               "role": s["role"] or more["role"],
               "term_expires": _ends_term(seat_text) or _ends_term(extra),
               "at": i}
        # One person named twice is one seat, with what either said:
        # Lebanon's "Councilor Kellen Appleton" above, and "Kellen Appleton"
        # / "Councilor, At-Large (Term Expires: 3/28)" below.
        twin = next((o for o in out if same_person(name, o["name"])), None)
        if twin:
            # The seat said more fully wins: Lebanon's "Mayor Douglas
            # Whittlesey" is "Mayor", and lower down "Mayor, Ward 1". Kept
            # at "Mayor", Lebanon's list had one Ward 1 councillor, and the
            # city two.
            if rec["seat"].startswith(twin["seat"]):
                twin["seat"] = rec["seat"]
            twin.update({k: v for k, v in rec.items()
                         if v and not twin.get(k)})
            return
        out.append(rec)

    def own_seat(line):
        """A seat line that is one person's, not a heading over several."""
        return _seat_only(line) and not GROUP_WORD.search(line)

    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        nx2 = lines[i + 2].strip() if i + 2 < len(lines) else ""
        # Dover: "Richard L." / "Robison, Jr." / "Role: City Councilor, Ward 5".
        # The first line of that widget is a given name by construction, so
        # a month is not a reason to doubt it: Dover's Ward 1 councillor is
        # April Richer.
        if nx2.lower().startswith("role:") and len(ln) < 25 and len(nxt) < 25:
            name = f"{ln} {nxt}".strip()
            name = name if PTS.NAME.match(name) and not JUNK.search(name) \
                else ""
            if name:
                add(i, name, nx2)
                heading, i = None, i + 3
                continue
        # A ward is a seat on a line of its own only under a heading that
        # says council, or with the council seat said on the next line.
        loose = bool(heading and SEAT_WORD.search(heading))
        one = _on_one_line(ln, strict=not loose) or (
            own_seat(nxt) and _on_one_line(ln, strict=False))
        if one:
            # Nashua's "Ward 1 - James Ravan" is followed by "Alderman -
            # Ward 1", which is the same seat said again and is read with it.
            if own_seat(nxt):
                add(i, one[0], one[1], nxt)
                i += 2
            else:
                add(i, one[0], one[1])
                i += 1
            continue
        if _seat_only(ln):
            heading, i = ln, i + 1
            continue
        name = _named(ln)
        if name:
            # MANCHESTER SAYS EACH SEAT ABOVE ITS HOLDER: "Ward 1 Alderman" /
            # "Bryce Kaw-uh" / "Ward 2 Alderman" / "Dan Goonan". The seat under
            # a name is then the NEXT member's, and read as this one's it moved
            # every alderman a ward on. So where the name sits under one
            # person's seat and the line below names a different seat, the one
            # above is this name's. Keene's "Ward 1" / "Jacob R. Favolise" /
            # "Councilor Ward 1 - 2026 to 2027" names the same seat both
            # times, and still takes the fuller line below.
            above = seat_of(heading, strict=False) if heading and own_seat(heading) \
                else None
            below = seat_of(nxt, strict=False) if own_seat(nxt) else None
            if above and below and above["seat"] and below["seat"] \
                    and above["seat"] != below["seat"]:
                add(i, name, heading)
                heading, i = None, i + 1
                continue
            if own_seat(nxt):
                add(i, name, nxt)
                i += 2
                continue
            if heading:
                add(i, name, heading)
            i += 1
            continue
        if not (CITY_CARD.match(ln) or PTS.CARD_LINE.match(ln)):
            heading = None
        elif out and not out[-1]["term_expires"]:
            out[-1]["term_expires"] = _ends_term(ln)
        i += 1
    return out


def stated_council_size(lines):
    """(seats, whether the sentence counts the mayor) where a page states
    its council's size, or (None, False).

      "The Keene City Council consists of 16 members: Two in each of the
       five wards, plus five at-large members, and the Mayor as the Chair."
                                              -> 16, counting the mayor
      "The City Council consists of nine (9) councilors"       -> 9
      "A nine-member City Council is elected"                  -> 9
      "a Council of nine Councilors, one Councilor from each ward, two
       Councilors at Large, and one Councilor to serve as Mayor" -> 9
      "The Board of Aldermen consists of 9 ward aldermen ... and 6 at-large
       aldermen"                                               -> 15

    The first number is the total unless it is itself a part -- "9 WARD
    aldermen" -- and then the parts are added. Only the words before a
    colon count: what follows Keene's is how its sixteen are made up.
    """
    text = re.sub(r"\s+", " ", " ".join(lines))
    num = r"(\d{1,2}|" + "|".join(_NUMS) + r")(?:\s*\(\s*\d{1,2}\s*\))?"
    noun = r"(?:members|council+ors|aldermen|alderpersons)"
    for sent in re.split(r"(?<=[.;])\s", text):
        m = re.search(r"\b(?:consists|is\s+made\s+up|is\s+composed|"
                      r"is\s+comprised)\s+of\s+|\bcouncil\s+of\s+|"
                      r"\b(?=" + num + r"[\s-]+member\s+(?:city\s+)?council)",
                      sent, re.I)
        if not m or not re.search(r"council|aldermen", sent, re.I):
            continue
        head = sent[m.start():].split(":")[0]
        mayor = bool(MAYOR_WORD.search(sent[m.start():]))
        m1 = re.search(num + r"[\s-]+member\s+(?:city\s+)?council", head, re.I)
        if m1:
            return int(_NUMS.get(m1.group(1).lower(), m1.group(1))), mayor
        parts = list(re.finditer(num + r"\s+((?:ward|at[\s-]*large)\s+)?" + noun,
                                 head, re.I))
        if not parts:
            continue

        def n(p):
            return int(_NUMS.get(p.group(1).lower(), p.group(1)))
        if parts[0].group(2):
            return sum(n(p) for p in parts), mayor
        return n(parts[0]), mayor
    return None, False


def directory_council(dot):
    """NHDOT's rows for the mayor and the council or aldermen."""
    return [o for o in (dot or {}).get("officials") or []
            if re.search(r"council|alder|^\s*(?:(?:assistant|deputy)\s+)?mayor",
                         o.get("position") or "", re.I)]


def mayor_named(pages, skip):
    """(name, url) where another of the city's own pages names its mayor on
    a line of its own -- Keene's "Mayor Jay Kahn", Nashua's "Meet Mayor Jim
    Donchess" -- or (None, None). Two pages naming two mayors is no answer.
    """
    found = []
    for p in pages:
        if p["url"] == skip:
            continue
        for ln in p["lines"]:
            m = re.match(r"^\s*(?:meet\s+)?mayor\s*[:\-–]?\s+(.+?)\s*$", ln, re.I)
            if m and _named(m.group(1)):
                found.append((_named(m.group(1)), p["url"]))
    names = {n for n, _u in found}
    if found and all(same_person(a, b) for a in names for b in names):
        return found[0]
    return None, None


def decide_council(key, pages, dot):
    """What a city's own pages say about its mayor and council: the rule
    decide() applies to a select board, with a council's seats.

    pages  saved_pages(key)
    dot    the city's NHDOT record, or None
    """
    drows = directory_council(dot)
    # The council's own page, or the city's list of its elected officials --
    # not a committee of the council: Nashua's "Ad Hoc Joint Mayoral - Board
    # of Aldermen" page names four of them.
    cands = [p for p in pages
             if re.search(r"council|aldermen|elected", last_segment(p["url"]),
                          re.I)
             and not LISTPAGE.search(last_segment(p["url"]))]
    # The page that reads the most; of two that read as many, the one that
    # gives more of their seats -- Lebanon's council page gives each ward,
    # and the sidebar of its resolutions page only the names -- and then
    # the council's own: Portsmouth's council page and its list of elected
    # officials both give the nine, and only the first says it has nine.
    reads = sorted(((read_council(p["lines"]), p) for p in cands),
                   key=lambda rp: (-len(rp[0]),
                                   -sum(1 for m in rp[0] if m["seat"]),
                                   0 if re.search(r"council|aldermen",
                                                  last_segment(rp[1]["url"]),
                                                  re.I) else 1))
    base = {"directory_size": len(drows)}
    if not reads or not reads[0][0]:
        return dict(base, case="directory",
                    why="no council read off the city's pages")
    people, page = reads[0]
    lines = page["lines"]
    others = [q["name"] for r, _p in reads[1:] for q in r
              if not any(same_person(q["name"], x["name"]) for x in people)]
    size, mayor_counts = stated_council_size(lines)
    size_from = "the page states it" if size else ""
    if not size:
        for p in pages:
            if p is not page:
                size, mayor_counts = stated_council_size(p["lines"])
                if size:
                    size_from = "another of the city's pages states it"
                    break
    if not any(MAYOR_WORD.search(m["seat"]) for m in people):
        name, url = mayor_named(pages, page["url"])
        if name:
            people = [{"name": name, "seat": "Mayor", "role": "",
                       "term_expires": None, "at": -1, "source_url": url}] \
                + people
    counted = [m for m in people
               if not m.get("source_url") or mayor_counts or not size]
    if not size and len(drows) and len(counted) <= len(drows):
        size, size_from = len(drows), f"the directory lists {len(drows)}"
    out = dict(base, source_url=page["url"], read_on=page["read_on"],
               read=len(counted), size=size, size_from=size_from,
               members=[{f: m.get(f) for f in ("name", "seat", "role",
                                               "source_url")}
                        | {"term_ends": m.get("term_expires")}
                        for m in people])
    at = [m["at"] for m in people if m["at"] >= 0]
    dated = page_dated(lines, head=min(at) if at else None)
    ended = sorted({int(m["term_expires"]) for m in people
                    if str(m.get("term_expires") or "").isdigit()
                    and term_has_ended(int(m["term_expires"]),
                                       page.get("read_on"))})
    if dated and dated[:2] < CITY_ELECTION:
        return dict(out, case="directory", stale=True,
                    why=f"the page dates itself {dated[0]}: {dated[2]!r}")
    if ended:
        return dict(out, case="directory", stale=True,
                    why=f"a term on the page ended in {ended[0]}")
    if others:
        return dict(out, case="directory",
                    why=f"another of the city's pages names {others}")
    if size and len(counted) > size:
        return dict(out, case="directory",
                    why=f"{len(counted)} names read for {size} seats")
    partial = not size or len(counted) < size
    if partial:
        missed = unread_on_page(people, drows, lines, [], page["url"])
        if missed:
            return dict(out, case="directory", unread=missed,
                        why=f"the page names {missed}, whom this did not read "
                            "as members")
    later = later_than_directory(people, drows, dated, partial=partial,
                                 floor=CITY_ELECTION)
    if not later:
        return dict(out, case="directory", unproven=True,
                    why="the directory's own council, with nothing on the "
                        "page to show it changed after the election")
    out["later"] = later
    if partial:
        out["partial"] = True
    for m in out["members"]:
        twin = [o["name"] for o in drows if same_person(o["name"], m["name"])]
        m["directory_name"] = twin[0] if len(twin) == 1 else None
    return dict(out, case="own", why="")


def given_names(root=Path(".")):
    """S3's lexicon: every given name in the New Hampshire lists on disk."""
    names = set()

    def add(full):
        g = given(full)
        if g:
            names.add(g)

    def load(name):
        p = root / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for t in load("town_officials.json").values():
        for o in t.get("officials") or []:
            add(o.get("name"))
    for c in load("town_clerks.json").values():
        add(c.get("clerk", ""))
    for o in (load("county_officials.json") or {}).get("officers", []):
        add(o.get("name"))
    for v in load("careers.json").values():
        if isinstance(v, dict) and v.get("first"):
            names.add(v["first"].lower().strip(" ."))
    legs = load("site/legislators.json")
    for m in (legs.values() if isinstance(legs, dict) else legs):
        add(m.get("display_full") or m.get("name") or "")
    return names


def build(keys, dot, known=None, guessed=None):
    """(the file's contents, every town's decision, every city's decision).

    `known` is known_spellings(); a member named wholly in capitals is
    written with a "display" spelling from display_name, and any word of it
    cased by a guess is added to `guessed`."""
    today = dt.date.today().isoformat()
    towns, cities = {}, {}
    for key in keys:
        found, _pages = PTS.read_town(key)
        cache = {}

        def lines_of(url, key=key, cache=cache):
            if url not in cache:
                cache[url] = page_lines(key, url)
            return cache[url]
        towns[key] = decide(key, found, dot.get(key), lines_of,
                            town_pages(key))
        if key in CITIES:
            cities[key] = decide_council(key, saved_pages(key), dot.get(key))

    def kept(decisions, fields):
        out = {}
        for k, v in decisions.items():
            if v["case"] != "own":
                continue
            out[k] = {f: v[f] for f in fields if f in v}
            for m in out[k]["members"]:
                if in_capitals(m["name"]):
                    m["display"] = display_name(m["name"], known, guessed)
        return out
    # `read` is how many of the members the size counts, which is not all
    # of them where a mayor from another page is shown beside a council
    # whose size leaves the mayor out: the label says "8 of 15", not 9.
    fields = ("source_url", "read_on", "size", "size_from", "later",
              "members", "partial", "read")
    return {
        "_what": ("Select boards, and the cities' mayors and councils, read "
                  "off their own websites where the page is current. A "
                  "board or council whose page lists fewer than its seats, "
                  "or whose size no source gives, is marked partial. Written "
                  "by town_boards.py from town_sites/; read by "
                  "build_town_pages.py. A town or city not here is shown from "
                  "the New Hampshire Department of Transportation's "
                  "directory."),
        "_built": today,
        "boards": kept(towns, fields),
        "councils": kept(cities, fields),
        "not_used": {k: {f: v.get(f) for f in ("why", "read", "size",
                                               "source_url", "read_on")
                         if v.get(f) is not None}
                     for k, v in towns.items()
                     if v["case"] != "own" and v.get("read")},
    }, towns, cities


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--show", nargs="*", default=None)
    ap.add_argument("--officials", default="town_officials.json")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    if not PTS.STORE.exists():
        print(f"  nothing under {PTS.STORE}; town_sites.py saves it")
        return 1
    dot = json.loads(Path(a.officials).read_text(encoding="utf-8"))
    keys = sorted(d.name for d in PTS.STORE.iterdir() if d.is_dir())
    guessed = []
    data, towns, cities = build(keys, dot, known_spellings(), guessed)
    boards, councils = data["boards"], data["councils"]
    # Silence is not success: a run that reads the pages and finds no board
    # anywhere has lost the pages or the parser, not the boards.
    if not boards:
        raise SystemExit("town_boards: no town's own page gave a whole board; "
                         "nothing written")

    lex = given_names()
    held = [(k, m["name"]) for k, b in (boards | councils).items()
            for m in b["members"] if given(m["name"]) not in lex]
    listed = sorted(k for k, b in (boards | councils).items()
                    if b.get("partial"))
    unread = {k: v for k, v in towns.items() if v.get("unread")}
    stale = {k: v for k, v in towns.items() if v.get("stale")}
    same = {k: v for k, v in towns.items() if v.get("unproven")}
    print(f"  {len(keys)} towns with saved pages; {len(boards)} give their "
          f"current board, {len(councils)} of the {len(CITIES)} cities their "
          f"mayor and council")
    both = boards | councils
    print(f"  shown as partial lists: {len(listed)} (" + ", ".join(
        f"{k} {len(both[k]['members'])} of {both[k].get('size') or 'no size'}"
        for k in listed) + ")")
    print(f"  on the directory: {len(unread)} whose page names a member this "
          f"did not read ({', '.join(sorted(unread))}), "
          f"{len(stale)} whose page is dated or lists an ended term, "
          f"{len(same)} whose page is the directory's board with nothing "
          f"later on it ({', '.join(sorted(same))}), "
          f"{len(data['not_used']) - len(unread) - len(stale) - len(same)} "
          "for another reason")
    recased = [(k, m["name"], m["display"])
               for k, b in (boards | councils).items() for m in b["members"]
               if m.get("display")]
    print(f"  {len(recased)} names given wholly in capitals, set in normal "
          f"case: {recased}")
    if guessed:
        print(f"  cased by a guess, for a person to check: {sorted(set(guessed))}")
    if held:
        print(f"  S3, for a person to look at -- given names no NH list on "
              f"disk carries: {held}")

    show = set(a.show or [])
    for k, v in list(towns.items()) + [(f"{c} (council)", v)
                                       for c, v in cities.items()]:
        if show and k.split()[0] not in show:
            continue
        if not show and not v.get("read"):
            continue
        rows = directory_council if "(council)" in k else directory_board
        dn = [o["name"] for o in rows(dot.get(k.split()[0]))]
        names = [m["name"] + (f" ({m.get('seat') or m.get('role')})"
                              if m.get("seat") or m.get("role") else "")
                 for m in v.get("members") or []]
        print(f"\n  {k}: {v['case']}  {v['why']}")
        print(f"    own page: {names}  {v.get('source_url', '')}")
        print(f"    directory: {dn}")
        for r in v.get("rejected") or []:
            print(f"    screened out: {r['name']!r} -- {r['why']}")

    if a.report or a.show is not None:
        print("\n  --report: nothing written")
        return 0
    Path(a.out).write_text(json.dumps(data, indent=1, sort_keys=True,
                                      ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"\n  wrote {a.out}: {len(boards)} boards, {len(councils)} councils")
    return 0


if __name__ == "__main__":
    sys.exit(main())
