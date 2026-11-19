#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
The Secretary of State's special elections for State Representative, read from
its pages as a person saved them, into collected/specials.json (the specials
design of 19 November 2026, reports/money-specials-design/specials-and-upcoming.md,
A2; the owner's "Yes to all 9" of that day).

    python3 src/parse/parse_sos_specials.py            # write collected/specials.json
    python3 src/parse/parse_sos_specials.py --check    # read again and compare; write nothing

THE SOURCE. records/sources/specials/<day>-<county>-<number>.txt, one page each,
saved as page text with a three-line head ("Address: <the page>", "Read: <day>,
how", "---"), and _manifest.json beside them giving each file's address, day,
size and sha256. There is no spreadsheet: each special is its own web page, and
nothing before October 2019 is listed. A file whose sha256, size, address or day
is not its manifest entry's, or that the manifest does not name, is refused.

THE PAGES PRINT EACH CANDIDATE'S HOME ADDRESS, so the folder is excluded from git
(.git/info/exclude) and exists only on the laptop, and this file is what the
build reads. Read here and kept: names, party, votes (primary, general and
recount), WINNER, the days of the primary, the special, the recount and the
swearing-in, the district, and a House resolution the page names. Read past and
NEVER kept: the street, post office box and ZIP code, and the town a candidate
lives in. No sentence this writes, a refusal's included, quotes a candidate's
line: a refusal names the file, the line's number and the candidate.

THE WORDINGS, as the nineteen pages print them (read on 19 November 2026, page by
page, before a line of this was written). A candidate's line is the party (or
"Declaration of Intent"; or a party heading over the lines under it; or a dash,
or nothing, for one more of the party above), "Write-In" where the page says so,
the name, a comma and the town, the address in brackets and the ZIP code, and
then each count in brackets in any of these forms, a count alone on a line
belonging to the candidate above:

  (Republican Primary Total 312 - WINNER) (Election - 880 WINNER)        2019
  (primary vote 341) WON PRIMARY (election vote-961)                      2020
  (Primary 210 votes) (General 1393 votes)                                2021
  (WINNER - Election Result 2,531)                                        2021
  (1281 votes - WON PRIMARY) (2190 votes - WON ELECTION)                  2021
  (245 votes - Primary WINNER) (General Election votes 1571 - WINNER)     2023
  (Primary Votes - 615 WINNER) (General votes - 2207 WINNER)              2026
  (General Votes - 864) (Recount Votes - 873)                             2025

A bracket of a number and only the words these use (primary, general, election,
total, votes, result, recount, winner, won, and a party) is a count; one that
names no stage is the primary's on a page with a primary day, the next one the
general's, and the general's on a page with none. Anything else on a line --
any bracket or word this does not know -- refuses the special alone, as the
results readers refuse a race alone, and says which line.

THE RULES, each a tie-out against the page itself: one WINNER of the special, who
has the most votes (the recount's, where there was one, and the first count's);
a primary's WINNER, where printed, has the most votes of its party's primary; a
party's candidate in the special is its primary's leader where it held one; the
person sworn in by the Governor and Council is the winner; the primary comes
before the special, the recount and the swearing-in after; the district is the
one the page's sentence "SPECIAL ELECTION for State Representative from ...
County District ..." names, the same its title and the file's name give, and a
race of the general election that elected the term (collected/election_<year>.json),
which holds every district of those lines. A declaration of intent with no votes
printed is no candidate on any count (two pages; said in _notes), and a write-in
is the primary's: "Write-In Dale Fincher" won the 2026 Carroll 7 Republican
primary and is that party's candidate in the special.

WHAT IT WRITES, in src/lib/entities.py's shapes (contest and candidacy), each
record checked against its kind's shape: the special (stage "special", one seat:
one vacancy, whatever the district's seats), and each party's primary for it
(stage "primary", its party, and "for": the special, so it is never read as a
State Primary). The district is the model's id, with its era: the term the seat
is of (proceedings.term_on, the term sitting on the special's day) gives it by
entities.era_of -- "house:2022:carroll-7" for a term from 2023-2024 -- and a term
of 2013-2014 to 2021-2022, before every era the state's settings hold, is on the
2012 lines, written "house:2012:rockingham-9" by the same district_id. The general
results' race key ("H|Carroll|7") is kept in "keys". A candidacy's person is
null: whom it is is decided where the site is built, by the certain rule
(build_member_elections), never here. "takes_office" is the sworn-in day where the
page gives one (Hillsborough 7, 2021, gives none), "recounted" the recount's day.

WHY IT WAS HELD ("cause", A5.3), only where a record states it: a page that names
a House resolution, in a district whose general election of the term is a tie in
the results file, is the tie's re-run (Strafford 8, 21 February 2023, House
Resolution 6, after 970 to 970 in 2022) -- {"kind": "tie", "resolution", "of": the
tied contest}. No page says a seat was vacant, or whom a winner replaced, so no
special says either (A5.5); a named predecessor waits for a reader of the journal.

Standard library and this project's own modules only; reads no network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import hashlib
import json
import re

import build_members_elect as BME
import entities as EN
import proceedings
import state_settings as ST

SOURCE = Path("records") / "sources" / "specials"
# How a record names its page, wherever the folder was read from (--source).
WHERE = "records/sources/specials"
MANIFEST = "_manifest.json"
OUT = Path("collected") / "specials.json"
# The 2012 lines: the districts the elections of 2012 to 2020 were held on, which filled the
# terms 2013-2014 to 2021-2022. The state's settings hold no era before 2022 (no table of the
# 2012 districts is on any disk here), so an id of a seat of those terms is written in this
# era's name, by the model's own district_id.
PRIOR_ERA, PRIOR_FIRST = "2012", "2013-2014"

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
DATE = r"(?:" + "|".join(MONTHS) + r") \d{1,2},\s*\d{4}"
DATE_RE = re.compile(r"(" + "|".join(MONTHS) + r") (\d{1,2}),\s*(\d{4})")
WEEKDAY = r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? )?"
FILE_RE = re.compile(r"^(\d{4}-\d\d-\d\d)-([a-z]+)-(\d+)\.txt$")
# "SPECIAL ELECTION for State Representative from Rockingham County District No. 9", and every
# page's own form of it; the title's "Rockingham County Dist. 1", "Merrimack District 24".
SENTENCE_RE = re.compile(r"SPECIAL ELECTION for State Representative from ([A-Z][a-z]+) County "
                         r"District (?:No\. ?)?(\d+)\b")
TITLE_RE = re.compile(r"\b([A-Z][a-z]+) (?:County )?(?:District|Dist\.) (?:No\. ?)?(\d+)\b")
PRIMARY_LINE = re.compile(r"^\*?\s*Primary(?: Election)?\s*:", re.I)
SPECIAL_LINE = re.compile(r"^\*?\s*Special Election\s*:", re.I)
RECOUNT_LINE = re.compile(r"^RECOUNT - " + WEEKDAY + "(" + DATE + r")\s*$")
SECTION_START = re.compile(r"^\s*\*?\s*(?:Filings|FILINGS|Candidates)\s*:\s*$")
SECTION_END = re.compile(r"^\s*(?:Reporting Requirements|ALSO see|Sample Ballot)\b")
HEADING = re.compile(r"^\s*(Republican|Democratic|Democrat)\s*:\s*$")
PREFIX = re.compile(r"^\s*(?:(?P<party>Republican|Democratic|Democrat)\s*[-:]\s*"
                    r"|(?P<doi>Declaration of Intent)\s*-\s*|(?P<dash>-)\s*)?"
                    r"(?P<wi>Write-In\s+)?(?P<rest>\S.*)$")
PARTY_WORDS = {"republican": "r", "democratic": "d", "democrat": "d"}
NAME = re.compile(r"^[^\W\d_][\w.'\-]*(?: [^\W\d_][\w.'\-]*)+$")
TOWN = re.compile(r"^[^\W\d_][\w.' ]*$")
GROUP = re.compile(r"\(([^()]*)\)")
ZIP = re.compile(r"^\s*\d{5}\b")
SWORN_TAIL = (r"sworn into office by the Governor and Executive Council on " + WEEKDAY
              + "(" + DATE + r")\.?")
SWORN_NAMED = re.compile(r"(?:Representative|Rep\.?)[ -]elect\s+([A-Z][\w.'\-]*(?: [A-Z][\w.'\-]*)*)"
                         r"\s+was " + SWORN_TAIL)
SWORN_BARE = re.compile(r"Sworn into office by the Governor and Executive Council on " + WEEKDAY
                        + "(" + DATE + r")\.?")
# Cheshire 9 (2021): a declaration of intent's note, read and kept nowhere.
DOI_TAIL = re.compile(r"--\s*nomination papers must be filed no later than " + DATE
                      + r" for access to special election ballot on [A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?\.?")
NOT_FILED = re.compile(r"^\s*Nomination papers were NOT filed\s*$")
RESOLUTION = re.compile(r"\bHouse Resolution (\d+)\b")
VOTE_WORDS = {"republican", "democratic", "primary", "total", "winner", "won", "votes", "vote",
              "general", "election", "result", "results", "recount"}


class Refused(Exception):
    """A page this cannot read whole: that special is refused alone and listed."""


def iso(words):
    """"October 8, 2019" -> "2019-10-08"."""
    m = DATE_RE.search(words)
    if not m:
        return None
    return f"{int(m.group(3)):04d}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"


def vote_group(text):
    """{"votes", "stage", "winner", "party"} of a bracket that is a count, else None: one
    number, and only the words the pages count in."""
    nums = re.findall(r"\d{1,3}(?:,\d{3})+|\d+", text)
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", text)]
    if len(nums) != 1 or not words or any(w not in VOTE_WORDS for w in words):
        return None
    stage = ("recount" if "recount" in words else "primary" if "primary" in words
             else "general" if "general" in words or "election" in words else None)
    party = "r" if "republican" in words else "d" if "democratic" in words else None
    return {"votes": int(nums[0].replace(",", "")), "stage": stage,
            "winner": "winner" in words or "won" in words, "party": party}


def read_head(text, entry, name):
    """The page's lines below its three-line head, the head held to the manifest's entry."""
    lines = text.split("\n")
    if len(lines) < 4 or not lines[0].startswith("Address: ") or not lines[1].startswith("Read: ") \
            or lines[2].strip() != "---":
        raise Refused(f"{name}: the head is not the three lines Address:, Read:, ---")
    if lines[0][len("Address: "):].strip() != entry.get("address"):
        raise Refused(f"{name}: its Address: is not the manifest's")
    if lines[1][len("Read: "):len("Read: ") + 10] != entry.get("read"):
        raise Refused(f"{name}: its Read: day is not the manifest's {entry.get('read')}")
    return lines[3:]


class Cand:
    def __init__(self, name, party, doi, write_in, line):
        self.name, self.party, self.doi, self.write_in, self.line = name, party, doi, write_in, line
        self.votes, self.won, self.sworn = {}, {"primary": False, "general": False}, []


def take_group(c, g, has_primary, name, n):
    """Put count `g` (vote_group's) on candidate `c`."""
    stage = g["stage"]
    if stage is None:
        stage = "primary" if has_primary and "primary" not in c.votes else "general"
    if stage in c.votes:
        raise Refused(f"{name}, line {n}: two {stage} counts for {c.name}")
    if g["party"] and g["party"] != c.party:
        raise Refused(f"{name}, line {n}: {c.name}'s count names another party's primary")
    c.votes[stage] = g["votes"]
    if g["winner"] and stage in c.won:
        c.won[stage] = True


def outside(c, seg, name, n):
    """The words between a candidate's brackets: WON PRIMARY, WON ELECTION, the sworn-in
    sentence, a declaration of intent's note, dashes. Anything else refuses."""
    for rx, what in ((SWORN_NAMED, "sworn"), (SWORN_BARE, "sworn"), (DOI_TAIL, "doi")):
        for m in list(rx.finditer(seg)):
            if what == "sworn":
                c.sworn.append(iso(m.group(m.lastindex)))
        seg = rx.sub(" ", seg)
    for word, stage in (("WON PRIMARY", "primary"), ("WON ELECTION", "general")):
        if word in seg:
            c.won[stage] = True
            seg = seg.replace(word, " ")
    if re.sub(r"[\s\-–]+", "", seg):
        raise Refused(f"{name}, line {n}: words after {c.name}'s name this reader does not know")


def candidate(line, party, has_primary, name, n):
    """(Cand, the party lines below it are of) of a candidate's line, or Refused."""
    m = PREFIX.match(line)
    if not m:
        raise Refused(f"{name}, line {n}: a line of the filings this reader does not know")
    if m.group("party"):
        party = PARTY_WORDS[m.group("party").lower()]
    elif m.group("doi"):
        party = None
    elif party is None:
        raise Refused(f"{name}, line {n}: a candidate under no party")
    rest = m.group("rest")
    cut = [i for i in (rest.find(","), rest.find("(")) if i >= 0]
    if not cut:
        raise Refused(f"{name}, line {n}: a line of the filings with no name this reader can find")
    who = " ".join(rest[:min(cut)].split())
    if not NAME.match(who):
        raise Refused(f"{name}, line {n}: a candidate's name this reader does not know")
    c = Cand(who, party, bool(m.group("doi")), bool(m.group("wi")), n)
    after = rest[min(cut):]
    if after.startswith(","):
        j = after.find("(")
        if j < 0 or not TOWN.match(after[1:j].strip()):
            raise Refused(f"{name}, line {n}: no town and address after {who}'s name")
        after = after[j:]
    pos, first = 0, True
    for g in GROUP.finditer(after):
        seg = after[pos:g.start()]
        if first and seg.strip():
            raise Refused(f"{name}, line {n}: words before {who}'s first bracket")
        if not first:
            if zip_next:
                seg = ZIP.sub(" ", seg, count=1)
            outside(c, seg, name, n)
        text = g.group(1)
        got = vote_group(text)
        zip_next = False
        if got is not None:
            take_group(c, got, has_primary, name, n)
        elif SWORN_BARE.fullmatch(text.strip()):
            c.sworn.append(iso(text))
        elif NOT_FILED.match(text) and c.doi:
            pass
        elif first:
            zip_next = True   # the address: read past, and its ZIP code after it
        else:
            raise Refused(f"{name}, line {n}: a bracket on {who}'s line this reader does not know")
        first, pos = False, g.end()
    if first:
        raise Refused(f"{name}, line {n}: {who}'s line has no brackets")
    seg = after[pos:]
    if zip_next:
        seg = ZIP.sub(" ", seg, count=1)
    outside(c, seg, name, n)
    return c, (None if c.doi else party)


def filings(body, has_primary, name):
    """([Cand], [(who named, day)]) of the page's Filings (or Candidates) section, and the
    sworn-in sentences of every other line."""
    starts = [i for i, ln in enumerate(body) if SECTION_START.match(ln)]
    if len(starts) != 1:
        raise Refused(f"{name}: {len(starts)} Filings or Candidates headings, where one is wanted")
    cands, named, party = [], [], None
    end = len(body)
    for i in range(starts[0] + 1, len(body)):
        if SECTION_END.match(body[i]):
            end = i
            break
    for i, ln in enumerate(body):
        if starts[0] < i < end:
            continue
        for m in SWORN_NAMED.finditer(ln):
            named.append((m.group(1), iso(m.group(2))))
        if SWORN_BARE.search(ln) and not SWORN_NAMED.search(ln):
            raise Refused(f"{name}, line {i + 4}: a sworn-in sentence that names no one")
    for i in range(starts[0] + 1, end):
        ln, n = body[i], i + 4
        s = ln.strip()
        if not s:
            continue
        h = HEADING.match(ln)
        if h:
            party = PARTY_WORDS[h.group(1).lower()]
            continue
        m = SWORN_NAMED.fullmatch(s)
        if m:
            named.append((m.group(1), iso(m.group(2))))
            continue
        groups = GROUP.findall(s)
        if s.startswith("(") and not GROUP.sub("", s).strip():
            if not cands:
                raise Refused(f"{name}, line {n}: a count with no candidate above it")
            for text in groups:
                got = vote_group(text)
                if got is not None:
                    take_group(cands[-1], got, has_primary, name, n)
                elif SWORN_BARE.fullmatch(text.strip()):
                    cands[-1].sworn.append(iso(text))
                else:
                    raise Refused(f"{name}, line {n}: a bracket this reader does not know")
            continue
        c, party = candidate(ln, party, has_primary, name, n)
        cands.append(c)
    return cands, named


def surname_fits(named, printed):
    """Whether the name a sworn-in sentence gives ("Vose", "Muriel Hall") ends the printed
    name, word for word."""
    a, b = named.lower().split(), printed.lower().replace(",", "").split()
    return bool(a) and b[-len(a):] == a


def read_page(path, entry, generals, root="."):
    """(contests, candidacies, notes) of one saved page, or Refused. `entry` is its manifest
    entry, `generals` {general election's year: collected/election_<year>.json}."""
    name = path.name
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
        raise Refused(f"{name}: its sha256 is not the manifest's: the file changed since it was saved")
    if len(raw) != entry.get("bytes"):
        raise Refused(f"{name}: {len(raw)} bytes, where the manifest says {entry.get('bytes')}")
    if entry.get("ends_whole") is not True:
        raise Refused(f"{name}: the manifest does not say the saved text ends whole")
    try:
        text = raw.decode("utf-8").replace("\r\n", "\n").replace("\xa0", " ")
    except UnicodeDecodeError:
        raise Refused(f"{name}: not UTF-8 text")
    body = read_head(text, entry, name)
    fm = FILE_RE.match(name)
    if not fm:
        raise Refused(f"{name}: not a name of the form <day>-<county>-<number>.txt")
    # The district: the page's sentence, held to its title and the file's name.
    said = {(m.group(1), int(m.group(2))) for m in SENTENCE_RE.finditer("\n".join(body))}
    if len(said) != 1:
        raise Refused(f"{name}: the page names {len(said)} districts in its SPECIAL ELECTION sentence")
    county, number = said.pop()
    if county not in ST.COUNTIES:
        raise Refused(f"{name}: {county} is no county of the state's settings")
    t = TITLE_RE.search(body[0])
    if not t or (t.group(1), int(t.group(2))) != (county, number):
        raise Refused(f"{name}: its title does not name {county} {number}")
    if (fm.group(2), int(fm.group(3))) != (county.lower(), number):
        raise Refused(f"{name}: the page is of {county} {number}, which the file's name is not")
    # The days.
    days = {"primary": [], "special": [], "recount": []}
    for ln in body:
        s = ln.strip()
        if PRIMARY_LINE.match(s):
            days["primary"].append(iso(s))
        elif SPECIAL_LINE.match(s):
            days["special"].append(iso(s))
        elif RECOUNT_LINE.match(s):
            days["recount"].append(iso(s))
    if len(days["special"]) != 1 or not days["special"][0]:
        raise Refused(f"{name}: {len(days['special'])} Special Election lines with a day, where one is wanted")
    if len(days["primary"]) > 1 or None in days["primary"] or len(days["recount"]) > 1:
        raise Refused(f"{name}: more than one Primary or RECOUNT line, or one with no day")
    day = days["special"][0]
    pday = days["primary"][0] if days["primary"] else None
    rday = days["recount"][0] if days["recount"] else None
    if day != fm.group(1):
        raise Refused(f"{name}: the page's special is on {day}, which the file's name is not")
    title_day = iso(body[0])
    if title_day and title_day != day:
        raise Refused(f"{name}: its title's day is {title_day}, its Special Election line's {day}")
    if pday and pday >= day:
        raise Refused(f"{name}: the primary, {pday}, is not before the special, {day}")
    if rday and rday <= day:
        raise Refused(f"{name}: the recount, {rday}, is not after the special, {day}")
    cands, named = filings(body, bool(pday), name)
    notes = []
    # The counts, held to each other.
    general = [c for c in cands if "general" in c.votes]
    if not general:
        raise Refused(f"{name}: no candidate has a count in the special")
    prim = [c for c in cands if "primary" in c.votes]
    if prim and not pday:
        raise Refused(f"{name}: primary counts, and no Primary line with a day")
    if pday and not prim:
        raise Refused(f"{name}: a primary day, and no primary counts")
    rec = [c for c in cands if "recount" in c.votes]
    if rec and (len(rec) != len(general) or any("general" not in c.votes for c in rec)):
        raise Refused(f"{name}: a recount count for some of the special's candidates and not all")
    if bool(rec) != bool(rday):
        raise Refused(f"{name}: recount counts and a RECOUNT day are not both there")
    for c in cands:
        if not c.votes:
            if not c.doi:
                raise Refused(f"{name}, line {c.line}: {c.name} has no count")
            notes.append(f"{name}: {c.name} filed a declaration of intent and has no votes printed; "
                         "no candidate on any count")
        if c.doi and "primary" in c.votes:
            raise Refused(f"{name}, line {c.line}: a declaration of intent with a party primary's count")
        if c.write_in and "primary" not in c.votes:
            raise Refused(f"{name}, line {c.line}: a write-in with no primary count")
    final = "recount" if rec else "general"
    won = [c for c in general if c.won["general"]]
    if len(won) != 1:
        raise Refused(f"{name}: {len(won)} winners of the special marked, where one is wanted")
    w = won[0]
    for stage in (("general", final) if final != "general" else ("general",)):
        if any(c is not w and c.votes[stage] >= w.votes[stage] for c in general):
            raise Refused(f"{name}: the special's WINNER, {w.name}, does not have the most votes "
                          f"({stage})")
    # Each party's primary: its WINNER, where printed, has the most votes; its leader is its
    # candidate in the special.
    by_party = {}
    for c in prim:
        if c.party not in ("r", "d"):
            raise Refused(f"{name}, line {c.line}: a primary count for a candidate of no party")
        by_party.setdefault(c.party, []).append(c)
    for p, cs in by_party.items():
        top = max(c.votes["primary"] for c in cs)
        leaders = [c for c in cs if c.votes["primary"] == top]
        marked = [c for c in cs if c.won["primary"]]
        if marked and (len(marked) != 1 or leaders != marked):
            raise Refused(f"{name}: the {p.upper()} primary's WINNER does not have the most votes")
        ran = [c for c in general if c.party == p]
        if len(ran) > 1:
            raise Refused(f"{name}: two {p.upper()} candidates in the special")
        if ran and (len(leaders) != 1 or ran[0] is not leaders[0]):
            raise Refused(f"{name}: the {p.upper()} candidate in the special is not its primary's leader")
    # The swearing-in: one day, after the special, and of the winner.
    sworn = set(d for c in cands for d in c.sworn) | {d for _who, d in named}
    if len(sworn) > 1:
        raise Refused(f"{name}: {len(sworn)} different sworn-in days")
    if any(c is not w for c in cands if c.sworn) or any(not surname_fits(who, w.name) for who, _d in named):
        raise Refused(f"{name}: the page swears in someone other than the special's WINNER, {w.name}")
    took = sworn.pop() if sworn else None
    if took and took <= day:
        raise Refused(f"{name}: sworn in on {took}, which is not after the special, {day}")
    # The term the seat is of, the general that elected it, and the district on its lines.
    term = proceedings.term_on(day)
    cycle = int(term[:4]) - 1
    if BME.term_after(cycle) != term:
        raise Refused(f"{name}: the term sitting on {day} is {term}, which no general election elected")
    results = generals.get(cycle)
    if results is None:
        raise Refused(f"{name}: no collected/election_{cycle}.json to hold the district to")
    key = f"H|{county}|{number}"
    race = (results.get("races") or {}).get(key)
    if race is None:
        raise Refused(f"{name}: {key} is no race of the {cycle} general election, which elected {term}")
    era = EN.era_of(term)
    if era is None and PRIOR_FIRST <= term:
        era = PRIOR_ERA
    if era is None:
        raise Refused(f"{name}: {term} is before every era of districts this reader can name")
    where = f"{EN.slug(county)}-{number}"
    did = EN.district_id("house", era, where)
    src = f"{WHERE}/{name}"
    sid = EN.contest_id(day, "special", "house", where)
    special = {"contest": sid, "election": day, "stage": "special", "office": "house",
               "district": did, "seats": 1, "term": term}
    if rday:
        special["recounted"] = rday
    if took:
        special["takes_office"] = took
    hr = {m.group(1) for m in RESOLUTION.finditer("\n".join(body))}
    if hr:
        tied = [c for c in race["candidates"] if c.get("elected") is None]
        if len(hr) != 1 or not tied:
            raise Refused(f"{name}: names House Resolution {', '.join(sorted(hr))}, and the {cycle} "
                          f"general's {key} is no tie")
        special["cause"] = {"kind": "tie", "resolution": f"House Resolution {hr.pop()}",
                            "of": EN.contest_id(results["election"], "general", "house", where)}
    special.update({"keys": {"results": key}, "source": src})
    contests, cands_out = [EN.ordered("contest", special)], []

    def cand_rec(contest, c, stage, extra):
        x = {"candidacy": EN.candidacy_id(contest, c.name, c.party or ""), "contest": contest,
             "printed": c.name}
        if c.party:
            x["party"], x["parties"] = c.party, list(EN.party_letters(c.party))
        x.update(extra)
        x["votes"] = c.votes[stage]
        x.update({"person": None, "source": src})
        return EN.ordered("candidacy", x)

    for c in sorted(general, key=lambda c: (-c.votes[final], c.name)):
        extra = {"elected": c is w}
        if rec:
            extra["first_count"] = c.votes["general"]
        cands_out.append(cand_rec(sid, c, final, extra))
    for p in sorted(by_party):
        pid = EN.contest_id(pday, "primary", "house", where, p)
        contests.append(EN.ordered("contest", {
            "contest": pid, "election": pday, "stage": "primary", "party": p,
            "parties": list(EN.party_letters(p)), "office": "house", "district": did, "seats": 1,
            "term": term, "for": sid, "keys": {"results": key}, "source": src}))
        for c in sorted(by_party[p], key=lambda c: (-c.votes["primary"], c.name)):
            cands_out.append(cand_rec(pid, c, "primary", {"write_in": True} if c.write_in else {}))
    bad = [s for r in contests for s in EN.shape_problems(r, EN.SHAPES["contest"], r["contest"])]
    bad += [s for r in cands_out for s in EN.shape_problems(r, EN.SHAPES["candidacy"], r["candidacy"])]
    if bad:
        raise Refused(f"{name}: a record breaks its kind's shape: {bad[0]}")
    return contests, cands_out, notes


def generals_on_file(collected):
    """{year: collected/election_<year>.json} of every general election on file."""
    out = {}
    for p in sorted(Path(collected).glob("election_*.json")):
        m = BME.RESULTS_RE.match(p.name)
        if m:
            out[int(m.group(1))] = json.loads(p.read_text(encoding="utf-8"))
    return out


def read_all(source=SOURCE, collected=Path("collected")):
    """The document of every page in `source`: each read whole or refused alone."""
    source = Path(source)
    mp = source / MANIFEST
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
        entries = {e["file"]: e for e in man["pages"]}
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise Refused(f"{mp.as_posix()} will not read: {e}")
    generals = generals_on_file(collected)
    contests, cands, notes, refused, read = [], [], [], [], []
    files = sorted(p for p in source.glob("*.txt"))
    for name in sorted(set(entries) - {p.name for p in files}):
        refused.append({"file": name, "why": "named in the manifest and not in the folder"})
    for p in files:
        entry = entries.get(p.name)
        if entry is None:
            refused.append({"file": p.name, "why": "not in the manifest"})
            continue
        try:
            got, xs, said = read_page(p, entry, generals)
        except Refused as e:
            refused.append({"file": p.name, "why": str(e)})
            continue
        contests += got
        cands += xs
        notes += said
        read.append({"file": f"{WHERE}/{p.name}", "address": entry["address"],
                     "read": entry["read"], "sha256": entry["sha256"]})
    doc = {"_about": [
        "The Secretary of State's special elections for State Representative, read by "
        "src/parse/parse_sos_specials.py from its pages as saved in records/sources/specials/ "
        "(the folder is not in git: the pages print candidates' home addresses, which are read "
        "past and never kept here), each special and its party primaries in "
        "src/lib/entities.py's contest and candidacy shapes. A candidacy's person is null: a "
        "member's Elections tab links one only on a certain match, where the site is built.",
        "Write the file again by running the reader, never by hand: --check says where the saved "
        "pages and this disagree."],
        "_source": read}
    if notes:
        doc["_notes"] = notes
    if refused:
        doc["_refused"] = refused
    doc["contest"] = sorted(contests, key=lambda c: (c.get("for") or c["contest"], c.get("for") is not None,
                                                     c["contest"]))
    doc["candidacy"] = cands
    return doc


def dumps(doc):
    """One record a line, so that a diff is the record it moved."""
    out = ["{"]
    for k in ("_about", "_notes", "_refused"):
        if doc.get(k):
            out.append(f' "{k}": ' + json.dumps(doc[k], ensure_ascii=False, indent=2).replace("\n", "\n ") + ",")
    for k in ("_source", "contest", "candidacy"):
        rows = doc.get(k) or []
        body = ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows)
        out.append(f' "{k}": [' + ("\n" + body + "\n ]" if rows else "]") + ("," if k != "candidacy" else ""))
    out.append("}")
    return "\n".join(out) + "\n"


def summary(doc):
    sp = [c for c in doc["contest"] if c["stage"] == "special"]
    pr = [c for c in doc["contest"] if c["stage"] == "primary"]
    return (f"{len(doc['_source'])} pages read: {len(sp)} specials, {len(pr)} party primaries for "
            f"{len({c['for'] for c in pr})} of them, {len(doc['candidacy'])} candidacies; "
            f"{len(doc.get('_refused') or [])} refused")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--source", default=str(SOURCE), help="the saved pages and their _manifest.json")
    ap.add_argument("--collected", default="collected", help="the general results, and where it writes")
    ap.add_argument("--check", action="store_true", help="read again and compare; write nothing")
    a = ap.parse_args()
    if not (Path(a.source) / MANIFEST).is_file():
        print(f"specials: {a.source}/{MANIFEST} is not here: the saved pages are on the laptop only, "
              "and collected/specials.json is what the build reads", file=sys.stderr)
        return 1
    try:
        doc = read_all(a.source, a.collected)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    out = Path(a.collected) / OUT.name
    if a.check:
        try:
            committed = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"specials: {out.as_posix()} will not read: {e}")
            return 1
        if committed != json.loads(dumps(doc)):
            print(f"specials: {out.as_posix()} is not what the saved pages say")
            return 1
        print(f"specials: as committed. {summary(doc)}")
        return 0
    out.write_text(dumps(doc), encoding="utf-8", newline="\n")
    print(f"specials: wrote {out.as_posix()}. {summary(doc)}")
    for r in doc.get("_refused") or []:
        print(f"  REFUSED {r['file']}: {r['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
