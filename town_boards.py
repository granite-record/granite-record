#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-24.1
"""
Which towns' own websites list their whole select board, as it stands now.

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
page is used only where it gives the WHOLE board and is CURRENT:

  whole     as many members as the page says the board has, or else as many
            as the directory lists when that is three or five (RSA 41:8: one
            selectman a year for three years, five where a town has voted
            so). A board of four in the directory with no size on the page is
            not a size anybody can check against, so it is not used.
  current   the page does not date itself before the March 2026 town
            meeting, and no member's term had ended when the page was read
            (see term_has_ended: one year stricter than "before 2026").
            Wentworth's town-officials page is headed "For the year ending
            December 2024" and gives a selectman a term ending in 2025: every
            name on it is real, and it is not the board today. Its select
            board page, saved the same night, is laid out role-first and the
            parser does not read it, so Wentworth stays on the directory.

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

A PARTIAL LIST IS NOT PUBLISHED, deliberately. A page that names four of five
members proves the directory wrong about somebody, but not about whom -- and
the missing name is as often the chair, whom the parser did not read, as a
departed member. Those towns stay on the directory for now, and --report
lists them, because each is a board a parser change or a person could finish.

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
      Alternate, Liaison.
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
JUNK = re.compile(
    r"\b(polic(?:y|ies)|documents?|links?|rates?|officers?|sergeant|powered|"
    r"privacy|principles|positions|plans?|article|members?|statement|events?|"
    r"credits|building|garden|district|congratulations|registrations?|"
    r"licens\w*|payments?|information|questions|residents|tips|values|"
    r"improvements|guard|program|portal|history|photos|timeline|about|"
    r"websites?|recordings?|land\s+use|assessments?|public|village|community|"
    r"current|previous|quick|useful|mission|all|dmv|faq|welcome|contact|"
    r"resources|calendar|news|online|vehicle|driver|dog|notary|voter|sewer|"
    r"commision|health|compliance|police|fire|capital|master|subc|lawn|care|"
    r"core|cadet|honor|expenditures|departmental|government|our|legislative|"
    r"guiding|civil|communication|action|rerc|beach|basin|river|"
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
    path = re.sub(r"^https?://[^/]+", "", url or "").rstrip("/")
    seg = path.split("/")[-1] if path else ""
    return re.sub(r"\.(php|html?|aspx?)$", "", seg)


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
    i = idx[0]
    line = lines[i]
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
    if m:
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
    "Paul S. Jadis" are not."""
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
    sa, sb, ga, gb = surname(a), surname(b), given(a), given(b)
    if bool(sa) and sa == sb and len(ga) >= 4 and _dl1(ga, gb):
        return True
    return (bool(ga) and ga == gb and min(len(sa), len(sb)) >= 5
            and _dl1(sa, sb))


def display_name(name):
    """A name as a page should print it. Kensington writes its board in
    capitals -- "SARA HAMILTON", "IAN O'REILLY" -- and those are set in
    ordinary case. A capitalised name whose case cannot be recovered that
    way ("MCDONALD" is McDonald, not Mcdonald) is left as the town wrote it,
    because a wrong spelling is worse than a loud one."""
    if not name or name != name.upper() or not re.search(r"[A-Z]{2}", name):
        return name
    if re.search(r"\b(MC|MAC|DE|DI|LA|LE|VAN|VON)[A-Z]", name):
        return name

    def word(w):
        return "-".join("'".join(p[:1].upper() + p[1:].lower()
                                 for p in part.split("'"))
                        for part in w.split("-"))
    return " ".join(word(w) if len(w.strip(".")) > 1 else w
                    for w in name.split())


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


def later_than_directory(people, dboard, dated):
    """What on the page is later than the directory, or "" for nothing.

    `dated` is page_dated()'s answer. A date counts only when it is after
    the meeting's month, since a page "updated March 2026" may predate it.
    A board that differs from the directory's by a person shows the page was
    changed since September 2025; the same people with no date and no term
    shows nothing, which is Columbia's page, one selectman out of date.
    """
    if dated and dated[:2] > MEETING:
        return f"the page is dated {dated[2]!r}"
    new = sorted({int(p["term_expires"]) for p in people
                  if str(p.get("term_expires") or "").isdigit()
                  and elected_at_meeting(int(p["term_expires"]))})
    if new:
        return f"a term ending {new[-1]} began at the 2026 meeting"
    extra = [p["name"] for p in people
             if not any(same_person(o["name"], p["name"]) for o in dboard)]
    gone = [o["name"] for o in dboard
            if not any(same_person(o["name"], p["name"]) for p in people)]
    if extra or gone:
        return (f"the page names {extra} where the directory names {gone}")
    return ""


def stated_size(lines):
    """The board's size where the page says it: "Andover has a five-member
    Select Board", "a three member board of selectmen"."""
    text = " ".join(lines).lower()
    m = re.search(r"\b(three|five|3|5)[\s-]+(?:member|person)\s+"
                  r"(?:select|board)", text)
    return {"three": 3, "3": 3, "five": 5, "5": 5}[m.group(1)] if m else None


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


# ------------------------------------------------------------- the town ---
def directory_board(dot):
    """NHDOT's select board rows for a town, as the directory prints them."""
    return [o for o in (dot or {}).get("officials") or []
            if (o.get("position") or "").startswith("Board of Selectman")]


def decide(key, found, dot, lines_of):
    """What a town's own pages say about its board, and whether it is used.

    found     (office, person, page) as parse_town_sites.read_town gives them
    dot       the town's NHDOT record, or None
    lines_of  url -> the page's lines

    Returns {"case": "own" | "directory", "why": ..., ...}. "own" carries
    the members, the source and the read date; "directory" says why not.
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

    size, size_from = stated_size(lines), "the page states it"
    if not size and len(dboard) in (3, 5):
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
    if not size:
        return dict(out, case="directory",
                    why=f"no board size to check {len(people)} names against "
                        f"(the directory lists {len(dboard)})")
    if len(people) != size:
        return dict(out, case="directory", partial=len(people) < size,
                    why=f"{len(people)} of {size} members read")
    later = later_than_directory(people, dboard, dated)
    if not later:
        return dict(out, case="directory", unproven=True,
                    why="the directory's own board, with no date or term on "
                        "the page to show it changed after the March 2026 "
                        "meeting")
    out["later"] = later
    # The directory's name for each member, where it has the same person,
    # so the page can carry the phone and e-mail the directory gives them.
    for m in out["members"]:
        twin = [o["name"] for o in dboard if same_person(o["name"], m["name"])]
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


def build(keys, dot):
    today = dt.date.today().isoformat()
    towns = {}
    for key in keys:
        found, _pages = PTS.read_town(key)
        cache = {}

        def lines_of(url, key=key, cache=cache):
            if url not in cache:
                cache[url] = page_lines(key, url)
            return cache[url]
        towns[key] = decide(key, found, dot.get(key), lines_of)
    boards = {k: {f: v[f] for f in ("source_url", "read_on", "size",
                                     "size_from", "later", "members")}
              for k, v in towns.items() if v["case"] == "own"}
    return {
        "_what": ("Select boards read off towns' own websites, where the page "
                  "gives the whole board and is current. Written by "
                  "town_boards.py from town_sites/; read by "
                  "build_town_pages.py. A town not here is shown from the "
                  "New Hampshire Department of Transportation's directory."),
        "_built": today,
        "boards": boards,
        "not_used": {k: {f: v.get(f) for f in ("why", "read", "size",
                                               "source_url", "read_on")
                         if v.get(f) is not None}
                     for k, v in towns.items()
                     if v["case"] != "own" and v.get("read")},
    }, towns


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
    data, towns = build(keys, dot)
    boards = data["boards"]
    # Silence is not success: a run that reads the pages and finds no board
    # anywhere has lost the pages or the parser, not the boards.
    if not boards:
        raise SystemExit("town_boards: no town's own page gave a whole board; "
                         "nothing written")

    lex = given_names()
    held = [(k, m["name"]) for k, b in boards.items() for m in b["members"]
            if given(m["name"]) not in lex]
    partial = {k: v for k, v in towns.items() if v.get("partial")}
    stale = {k: v for k, v in towns.items() if v.get("stale")}
    same = {k: v for k, v in towns.items() if v.get("unproven")}
    print(f"  {len(keys)} towns with saved pages; {len(boards)} give their "
          f"whole, current board")
    print(f"  on the directory: {len(partial)} with part of the board read, "
          f"{len(stale)} whose page is dated or lists an ended term, "
          f"{len(same)} whose page is the directory's board with nothing "
          f"later on it ({', '.join(sorted(same))}), "
          f"{len(data['not_used']) - len(partial) - len(stale) - len(same)} "
          "for another reason")
    if held:
        print(f"  S3, for a person to look at -- given names no NH list on "
              f"disk carries: {held}")

    show = set(a.show or [])
    for k, v in towns.items():
        if show and k not in show:
            continue
        if not show and not v.get("read"):
            continue
        dn = [o["name"] for o in directory_board(dot.get(k))]
        names = [m["name"] + (f" ({m['role']})" if m.get("role") else "")
                 for m in v.get("members") or []]
        print(f"\n  {k}: {v['case']}  {v['why']}")
        print(f"    town page: {names}  {v.get('source_url', '')}")
        print(f"    directory: {dn}")
        for r in v.get("rejected") or []:
            print(f"    screened out: {r['name']!r} -- {r['why']}")

    if a.report or a.show is not None:
        print("\n  --report: nothing written")
        return 0
    Path(a.out).write_text(json.dumps(data, indent=1, sort_keys=True,
                                      ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"\n  wrote {a.out}: {len(boards)} boards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
