#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-18.6
"""
The Secretary of State's count of the State Primary's State Representative
and State Senate races, 2016 to 2026, each party's primary its own contest,
read into collected/primary_<year>.json beside the other offices' primaries,
which parse_sos_primary_offices reads and this writes (the elections display's data: every
official's whole election record, primaries included, the owner's word of
19 November 2026). The site reads them: src/pages/build_member_elections.py
draws a member's primaries on their Elections tab from every
collected/primary_*.json (primaries_on_file), with each race's margin from
src/pages/election_margin.py.

    python3 src/parse/parse_sos_primary_results.py --year 2024     # write one year
    python3 src/parse/parse_sos_primary_results.py --all           # every year on disk
    python3 src/parse/parse_sos_primary_results.py --all --check   # read again; write nothing

WHAT IT READS, in records/sources/, saved by a person in a browser byte for
byte under the names the Secretary of State gave them (nothing here asks the
network), one file a party:

    2016-sp-<county>-house-<party>.xls          a county's House races
    <year>-sp-house-<county>-<party>[_N].xls[x] (2018-2026)
    <year>-sp-state-senate-1-24-<party>[_N].xls every Senate district (2016-2024)
    2026-sp-state-senate-<a>[-<b>]-<party>.xlsx the Senate in parts, as 2026's
                                                general files are

<party> is democratic, republican or libertarian (2018 alone). A later upload
of one name (_N) replaces the earlier, as parse_sos_results.latest has it for
the general files; two names FILE_TYPOS lists misspell their county.

THE LAYOUT IS THE GENERAL ELECTION'S (read on 18 November 2026, file by
file, before a line of this was written), and the general reader's rules
read it (parse_sos_results: read_house, Block, district; the 2016-2022
layout of surnames and "Scatter" there is the same here). What differs:

  The titles say the primary and the party: "State of New Hampshire - 2024
  Primary Election", "State Representatives - BELKNAP County - Democratic",
  "State Senate District 1 - Democratic". The day is the second Tuesday of
  September, which every file that prints a day prints.

  A party's file names every candidate any place wrote in, of any party:
  "Tom Ploszaj, r" in the Democratic primary of Belknap 1 is a Republican
  with one write-in vote there. A party label is kept as the file prints it;
  the race is the party's whose file it is.

  An empty cell under a candidate is none: the files print a count only
  where a vote came (Block.count, with a primary block), and a Totals row
  prints nothing under a candidate nobody wrote in. Each file's count of
  such cells is said in _notes.

WINNERS ARE THE NOMINEES, AS MANY AS THE SEATS (the task of 19 November
2026). The files mark no nominee, so the candidates with the most votes are
marked "nominated": true, as many as the race has seats and none with no
votes; a tie for the last place is null. A race with fewer candidates who
won a vote than seats leaves the rest open ("open": the number). The
write-ins nobody named are one count for many names, so a nominee whose
place they could have taken (they come to as many votes as that nominee's
times the places left to share) is null, and said. Nothing here says
whether a write-in nominee accepted, or met any rule beyond the count.

EACH RACE IS HELD TO THE SAME YEAR'S GENERAL ELECTION (collected/
election_<year>.json, which parse_sos_results read from other files): the
race must be one the general names, with its seats, and its towns must be
the general's (one place spelt another way, within two letters, is read as
the general's and said). The general's spellings and floterial mark are
written. Where the general has no file for a county or for the Senate
(2016's Strafford House and its Senate), the race is the primary file's
alone, and said.

IT REFUSES RATHER THAN GUESSES, saying which file, sheet and row: a file it
cannot read is listed in "_refused" with why, and its races are not written;
a race it cannot settle is refused alone, and listed. A race whose column of
places does not add up to the Totals the file prints for it is one of those
(19 November 2026: one such race in the 2026 Strafford Democratic file had
taken the county's other twenty with it), and so is a candidate twice or a
block whose towns are not the district's (20 November 2026: 2016 Rockingham
D, 2022 Belknap, Cheshire and Merrimack D): listed in "_refused" by race and
printed as a REFUSED line, which figure is right never guessed. The rest of
the year is written. Files of the primary that are not these races (presidential
primaries, ballots cast, names on the checklist, delegates to a party's
convention, and the other offices, which parse_sos_primary_offices reads)
are not read: --not-read lists those on disk that neither reader reads,
with why. They are not in the document, which says only what its own files
say, wherever it is run.
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

import build_members_elect as BME
import parse_sos_results as PSR

SOURCES = PSR.SOURCES
YEARS = (2016, 2018, 2020, 2022, 2024, 2026)
PARTIES = {"democratic": "d", "republican": "r", "libertarian": "l"}
HOUSE_FILE = re.compile(r"^(?P<y>\d{4})-sp-(?:house-(?P<a>[a-z]+)-|(?P<b>[a-z]+)-house-)"
                        r"(?P<party>democratic|republican|libertarian)(?:_\d+)?\.xlsx?$")
SENATE_FILE = re.compile(r"^(?P<y>\d{4})-sp-state-senate-(?P<a>\d+)(?:-(?P<b>\d+))?-"
                         r"(?P<party>democratic|republican|libertarian)(?:_\d+)?\.xlsx?$")
# A file whose name misspells its county or runs it into the party, by name,
# with (county, party), read as that county's.
FILE_TYPOS = {"2016-sp-straffprd-house-republican.xls": ("strafford", "republican"),
              "2018-sp-house-sullivandemocratic_0.xls": ("sullivan", "democratic")}
# A Senate district's title: "State Senate District 1 - Democratic", "State
# Senate Dist. 9 - Democratic", "State Senate District No. 1 - Libertarian",
# and 2026's "State Senate District 1 Democratic", with no dash.
SENATE_TITLE = re.compile(r"^state senate (?:district|dist\.?)\s*(?:no\.?\s*)?(\d+)\s*-?\s*"
                          r"(democratic|republican|libertarian)$", re.I)
# The same with a word one letter off "Senate" or "District" (2018: "State
# Sente District No. 5", "State Senate Distrit No. 9"): read, and said.
SENATE_TITLE_LOOSE = re.compile(r"^state (\w+) (\w+)\s*(?:no\.?\s*)?(\d+)\s*-?\s*"
                                r"(democratic|republican|libertarian)$", re.I)
# A sheet whose day the official record misprints, by file and sheet, with
# why: read as the primary's day, and said (a typo flags, not fails).
DAY_TYPOS = {
    ("2016-sp-state-senate-1-24-republican.xls", "rsenate9-11"):
        "the 2014 primary's day, where the file's other sheets and its title say 2016's",
    ("2024-sp-state-senate-1-24-democratic_3.xls", "dsenate14-16"):
        "the 2022 primary's day, where the file's other sheets say 2024's",
    ("2024-sp-state-senate-1-24-republican_2.xls", "dsenate14-16"):
        "the 2022 primary's day, where the file's other sheets say 2024's",
}
# A Senate district's title the official record prints with another party's
# name, by file and district, with why: read as the file's party, and said.
TITLE_TYPOS = {
    ("2018-sp-state-senate-1-24-republican_0.xls", 24):
        "it is the Republican primary's file, and its every other title says Republican",
    ("2020-sp-state-senate-1-24-republican.xls", 24):
        "it is the Republican primary's file, and its every other title says Republican",
}
# The words that open a note the Senate files print under a district's
# Totals, one text cell a row, run on over the rows under it (2018: "No votes
# cast: Atkinson and Gilmanton Academy Grant; Bean's Grant; ..."): the places
# of the district where nobody voted in the party's primary, which the file
# gives no row. They are the race's places with no count, and said.
NOTE_OPENS = re.compile(r"^no votes cast\s*:\s*", re.I)
# The other files of a primary, by what their names say, with why each is not
# read here. Read in this order; the first that matches says.
NOT_READ = [
    (re.compile(r"-sp-ballots-?cast"), "the ballots cast, which is no race"),
    (re.compile(r"-sp-names-on-checklist"), "the names on the checklist, which is no race"),
    (re.compile(r"-sp-delegate-"), "delegates to a party's state convention, which is a party's "
                                   "office, not a public one"),
]
PP_FILE = re.compile(r"^\d{4}-pp-")


def out_path(year, root="."):
    return Path(root) / "collected" / f"primary_{year}.json"


class Refused(PSR.Refused):
    """A file or a race this does not recognise: listed, never guessed."""


class Primary(datetime.date):
    """The State Primary's day, as parse_sos_results.read_house takes an
    election: a date that carries the party it is read for, and the rule
    that marks its winners (nominate) under the key "nominated"."""

    def __new__(cls, year, party):
        d = datetime.date(year, 9, 1)
        while d.weekday() != 1:
            d += datetime.timedelta(days=1)
        d += datetime.timedelta(days=7)
        self = super().__new__(cls, d.year, d.month, d.day)
        self.party = party
        # The contest's word in a race's id (parse_sos_offices.contest_kind): "primary-r".
        self.contest = f"primary-{PARTIES[party]}"
        self.choose = nominate
        self.mark = "nominated"
        return self


# ---- the winners -----------------------------------------------------------------

def nominate(cands, seats, where, scatter=None):
    """The candidates, each marked nominated (True), not (False), or not
    settled by the file (None): the most votes, as many as the seats, and
    none with no votes. Those tied for the last place are None. A nominee
    the write-ins nobody named could have displaced is None too: the
    unnamed count `scatter` is one sum for many names, and it displaces a
    nominee with v votes only if it comes to v for each place left to share
    -- the seats less the named candidates with more votes than v."""
    voted = sorted((c["votes"] for c in cands if c["votes"] > 0), reverse=True)
    if not voted:
        return [dict(c, nominated=False) for c in cands]
    k = min(seats, len(voted))
    cut = voted[k - 1]
    tie = sum(1 for v in voted if v >= cut) > k
    out = []
    for c in cands:
        v = c["votes"]
        mark = v > cut or (v == cut and not tie) if v > 0 else False
        if v > 0 and v == cut and tie:
            mark = None
        if mark is True and scatter:
            above = sum(1 for x in voted if x > v)
            if scatter >= (seats - above) * v:
                mark = None
        out.append(dict(c, nominated=mark))
    return out


# ---- the files --------------------------------------------------------------------

def file_party(name):
    """(kind, county or (first, last), party) of a primary House or Senate
    file's name, or None."""
    if name in FILE_TYPOS:
        county, party = FILE_TYPOS[name]
        return "house", county, party
    m = HOUSE_FILE.match(name)
    if m:
        return "house", m.group("a") or m.group("b"), m.group("party")
    m = SENATE_FILE.match(name)
    if m:
        a = int(m.group("a"))
        return "senate", (a, int(m.group("b") or a)), m.group("party")
    return None


def source_files(root, year):
    """{"house": {(county, party): path}, "senate": {party: [path, ...]},
    "replaced": [(earlier, later)]}."""
    d = Path(root) / SOURCES
    house, senate, replaced = {}, {}, []
    for p in sorted(d.glob(f"{year}-*")) if d.is_dir() else []:
        if "-sp-" not in p.name:
            continue
        got = file_party(p.name)
        if got is None:
            # Another office's (parse_sos_primary_offices), or one of NOT_READ (unread()).
            continue
        kind, where, party = got
        if kind == "house":
            if where not in PSR.COUNTIES:
                raise Refused(f"{p.name} names no county of New Hampshire")
            house.setdefault((where, party), []).append(p)
        else:
            senate.setdefault(party, []).append(p)
    out = {"house": {k: PSR.latest(ps, f"{k[0]}'s {k[1]} House primary", replaced)
                     for k, ps in sorted(house.items())},
           "senate": {}, "replaced": replaced}
    for party, ps in sorted(senate.items()):
        parts = {}
        for p in ps:
            parts.setdefault(file_party(p.name)[1], []).append(p)
        gaps, overlaps = PSR.senate_unheld(parts)
        if overlaps or gaps:
            raise Refused(f"the {year} {party} Senate primary files hold "
                          + (f"district {overlaps[0][0]} twice" if overlaps else
                             f"no district {gaps[0]}"))
        out["senate"][party] = [PSR.latest(v, f"the {party} Senate primary for "
                                              f"{PSR.span_words(s)}", replaced)
                                for s, v in sorted(parts.items())]
    return out


def unread(root, year):
    """[(path, why)]: the year's primary files on disk that neither reader
    reads -- the presidential primary's, and every -sp- file this reader and
    parse_sos_primary_offices leave, each with NOT_READ's why, or that no
    reader knows its name."""
    import parse_sos_primary_offices as PO
    d = Path(root) / SOURCES
    files = source_files(root, year)
    known = {p for p in files["house"].values()} | {p for ps in files["senate"].values()
                                                     for p in ps}
    known |= {old for old, _new in files["replaced"]} | PO.files_known(root, year)
    out = []
    for p in sorted(d.glob(f"{year}-*")) if d.is_dir() else []:
        if PP_FILE.match(p.name):
            out.append((p, "the presidential primary, which is out of these readers' scope"))
        elif "-sp-" in p.name and p not in known:
            out.append((p, next((w for rx, w in NOT_READ if rx.search(p.name)),
                                "a name neither primary reader knows")))
    return out


def read_senate(path, election, legacy, span, notes, alone=None):
    """{district: district record} of one party's Senate file: a sheet for
    one to three districts, each a title "State Senate District 5 -
    Republican" (the day beside it or not), a header row whose first cell is
    the day or empty, its places and a Totals row. The file must hold the
    districts `span` names, each once. What it reads past is said in
    `notes`. A district whose column does not add up to its Totals goes to
    `alone`, as parse_sos_results.read_house has it, where one is given."""
    found, cur = {}, None

    def day_typo(day, where, sheet):
        why = DAY_TYPOS.get((path.name, sheet))
        if why is None:
            raise Refused(f"{where}: the day is {day!r}, not the primary of {election}")
        notes.append(f"{where}: the sheet prints the day {day}; read as {election}: {why}")
    for name, rows in PSR.sheets(path):
        cur = None
        for i, row in enumerate(rows):
            where = f"{path.name}, sheet {name!r}, row {i + 1}"
            while row and row[-1] is None:
                row = row[:-1]
            if PSR.blank(row):
                continue
            strs = [c for c in row if isinstance(c, str)]
            days = [c for c in row if isinstance(c, datetime.date)]
            title = next((SENATE_TITLE.match(c) for c in strs if SENATE_TITLE.match(c)), None)
            loose = next((SENATE_TITLE_LOOSE.match(c) for c in strs
                          if SENATE_TITLE_LOOSE.match(c)), None) if not title else None
            if loose and PSR.edits(loose.group(1).lower(), "senate") <= 1 and \
                    PSR.edits(loose.group(2).lower(), "district") <= 1:
                title = SENATE_TITLE.match(f"State Senate District {loose.group(3)} - "
                                           f"{loose.group(4)}")
                notes.append(f"{where}: the title prints {loose.group(0)!r}, a word one letter "
                             f"off; read as Senate district {loose.group(3)}")
            if title:
                n = int(title.group(1))
                if title.group(2).lower() != election.party:
                    why = TITLE_TYPOS.get((path.name, n))
                    if why is None:
                        raise Refused(f"{where}: {title.group(0)!r} is another party's primary")
                    notes.append(f"{where}: the title prints {title.group(0)!r}, read as the "
                                 f"{election.party.title()} primary's: {why}")
                if n in found:
                    raise Refused(f"{where}: Senate district {n} twice")
                if any(d != election for d in days):
                    day_typo(days[0], where, name)
                cur = found[n] = {"where": where, "blocks": [], "note": False, "no_votes": []}
                continue
            if cur is not None and cur["blocks"] and cur["blocks"][-1].totals is not None and \
                    len(strs) == 1 and len([c for c in row if c is not None]) == 1 and (
                        cur["note"] or NOTE_OPENS.match(strs[0])):
                cur["note"] = True
                cur["no_votes"] += [s.strip() for s in re.split(r"[;,]", NOTE_OPENS.sub("", strs[0]))
                                    if s.strip()]
                continue
            if len(strs) == 1 and len([c for c in row if c is not None]) == 1 and \
                    "primary election" in strs[0].lower():
                years = re.findall(r"\b20\d\d\b", strs[0])
                if years and years != [str(election.year)]:
                    raise Refused(f"{where}: {strs[0]!r} is the title of another election")
                day = PSR.as_day(re.sub(r"^.*primary election\s*-\s*", "", strs[0], flags=re.I))
                if "-" in strs[0].lower().split("primary election")[-1] and day != election:
                    raise Refused(f"{where}: {strs[0]!r} names a day that is not the primary "
                                  f"of {election}")
                continue
            if cur is None:
                raise Refused(f"{where}: {row!r} before any district's title")
            head = row[0]
            if not cur["blocks"]:
                if head is not None and PSR.as_day(head) != election:
                    day_typo(head, where, name)
                cur["blocks"].append(PSR.Block(PSR.entities(row, 1, where, legacy, True), where,
                                               source=(path, name), legacy=legacy,
                                               primary=True))
                continue
            b = cur["blocks"][-1]
            if PSR.is_totals(head):
                if b.totals is not None:
                    raise Refused(f"{where}: a second Totals row")
                b.totals = (row, where)
                continue
            if legacy and isinstance(head, str) and head.startswith("*"):
                PSR.footnote(b, head, where, len(row))
                continue
            if not isinstance(head, str):
                raise Refused(f"{where}: {head!r} where a town's name belongs")
            if b.totals is not None:
                raise Refused(f"{where}: a row of counts after the Totals")
            b.rows.append((PSR.starless(head) if legacy else head, row, where))
    want = list(range(span[0], span[1] + 1))
    if sorted(found) != want:
        raise Refused(f"{path.name} holds Senate district(s) "
                      f"{', '.join(map(str, sorted(found))) or 'none'}; its name says "
                      f"{PSR.span_words(span)}")
    for n, d in found.items():
        if not d["blocks"]:
            raise Refused(f"{d['where']}: Senate district {n} has no header row")
    out = {}
    for n, d in found.items():
        try:
            out[n] = PSR.district(d["blocks"], 1, d["where"], nominate, "nominated")
        except PSR.Refused as e:
            if alone is None or not PSR.race_alone(e):
                raise
            alone.append({"district": n, "where": d["where"], "why": str(e)})
            continue
        if d["no_votes"]:
            twice = sorted(set(d["no_votes"]) & set(out[n]["towns"]))
            if twice:
                raise Refused(f"{d['where']}: {', '.join(twice)} both counted and under "
                              "\"No votes cast\"")
            out[n]["no_votes"] = d["no_votes"]
            notes.append(f"{d['where']}: the file's note under the Totals says no votes were cast "
                         f"in {len(d['no_votes'])} place(s) it gives no row: "
                         f"{'; '.join(d['no_votes'])}; read as places of the race with no count")
    return out


# ---- a race, held to the general election ------------------------------------------

def general_races(root, year):
    """{key: race} of collected/election_<year>.json, and the counties and
    Senate it says it has no file for."""
    p = Path(root) / "collected" / f"election_{year}.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    gone = doc.get("_not_on_file") or {}
    return doc["races"], {"counties": [c.lower() for c in gone.get("counties") or []],
                          "senate": bool(gone.get("senate"))}


def held(key, rec, seats, general, notes, where):
    """(seats, floterial, towns) of a race, its towns as the general
    election's race spells them. Refused where the general names no such
    race, other seats, or other towns."""
    g = general.get(key)
    if g is None:
        raise Refused(f"{where}: {key} is no race of the same year's general election")
    if seats != g["seats"]:
        raise Refused(f"{where}: {seats} seat(s); the general election's {key} has {g['seats']}")
    spelt = {PSR.place_key(t): t for t in g["towns"]}
    towns, unknown = [], []
    for t in rec["towns"] + rec.get("no_votes", []):
        s = spelt.get(PSR.place_key(t))
        (towns if s else unknown).append(s or t)
    left = sorted(set(g["towns"]) - set(towns))
    if len(unknown) == 1 and len(left) == 1 and PSR.one_place(unknown[0], left[0]):
        notes.append(f"{where}: the file names {unknown[0]!r}, read as {left[0]}, the one place "
                     f"of {key} it names no other way")
        towns.append(left[0])
    elif unknown:
        raise Refused(f"{where}: {', '.join(map(repr, unknown))} not among the towns of the "
                      f"general election's {key}")
    if sorted(towns) != sorted(g["towns"]):
        raise Refused(f"{where}: {key}'s towns are {', '.join(sorted(towns))} here and "
                      f"{', '.join(sorted(g['towns']))} in the general election")
    return g["seats"], g["floterial"], sorted(towns)


def race_record(party, rec, seats, floterial, towns, legacy, house):
    """A race as primary_<year>.json writes it."""
    nominated = sum(c["nominated"] is True for c in rec["candidates"])
    out = {"party": PARTIES[party], "seats": seats, "floterial": floterial, "towns": towns,
           "candidates": [{"name": c["name"], "party": c["party"], "votes": c["votes"],
                           "write_in": c["write_in"], "nominated": c["nominated"]}
                          for c in rec["candidates"]],
           "scatter": rec["scatter"],
           "printed_totals": len(rec["printed_totals"])}
    unsettled = any(c["nominated"] is None for c in rec["candidates"])
    if nominated < seats and not unsettled:
        out["open"] = seats - nominated
    if rec["recounted"]:
        out["recounted"] = True
    if legacy and house:
        out["surnames"] = True
    return out


def race_notes(key, race, where):
    """What a race's count leaves unsettled, said."""
    out = []
    shut = [c["name"] for c in race["candidates"] if c["nominated"] is None]
    if shut:
        out.append(f"{where}: {key}: {', '.join(shut)} not settled by the count -- a tie for "
                   "the last place, or the write-ins nobody named "
                   f"({race['scatter'] or 0:,}) could have taken it")
    if race.get("open") and race["scatter"]:
        out.append(f"{where}: {key}: {race['open']} place(s) no named candidate won; the "
                   f"write-ins nobody named come to {race['scatter']:,}, and whether one of them "
                   "was nominated is not in the file")
    return out


# ---- the year ------------------------------------------------------------------------

def read_year(root, year):
    """The primary document of `year` (its House and Senate races), from the
    saved files under `root`; a file or race that refuses is listed."""
    root = Path(root).resolve()
    legacy = year <= PSR.LEGACY_UNTIL
    files = source_files(root, year)
    general, gone = general_races(root, year)
    races, refused, notes, read = {}, [], [], []
    notes += [f"{new.name} is read, and replaces {old.name}: the Secretary of State's later "
              "upload of the same results" for old, new in files["replaced"]]

    def settle(party, key, rec, seats, where, house):
        gkey = key
        county = key.split("|")[1].lower() if house else None
        free = (house and county in gone["counties"]) or (not house and gone["senate"])
        if free:
            notes.append(f"{where}: the general election has no file for "
                         + (f"{county.title()} County's House races" if house else
                            "the State Senate")
                         + ", so the race is the primary file's alone, its towns as it spells "
                           "them")
            s, flo, towns = seats, None, sorted(rec["towns"] + rec.get("no_votes", []))
        else:
            s, flo, towns = held(gkey, rec, seats, general, notes, where)
        notes.extend(rec.get("notes") or [])
        race = race_record(party, rec, s, flo, towns, legacy, house)
        k = f"{PARTIES[party].upper()}|{key}"
        notes.extend(race_notes(k, race, where))
        races[k] = race

    for (county, party), path in files["house"].items():
        election = Primary(year, party)
        alone = []
        try:
            got = PSR.read_house(path, county, election, legacy, alone)
        except PSR.Unreadable:
            raise
        except PSR.Refused as e:
            refused.append({"file": path.name, "why": str(e)})
            continue
        # ONE RACE THAT DOES NOT ADD UP IS REFUSED ALONE (19 November 2026),
        # listed by race; the file's other races are read.
        refused += [{"file": path.name, "race": f"{PARTIES[party].upper()}|H|{county.title()}|"
                                                f"{a['district']}", "why": a["why"]}
                    for a in alone]
        read.append(path)
        blanks = 0
        for n, (seats, _flo, rec) in got.items():
            blanks += rec["blank_named"]
            where = f"{path.name}, district {n}"
            try:
                settle(party, f"H|{county.title()}|{n}", rec, seats, where, True)
            except PSR.Refused as e:
                refused.append({"file": path.name, "race": f"{PARTIES[party].upper()}|H|"
                                                          f"{county.title()}|{n}", "why": str(e)})
        if blanks:
            notes.append(f"{path.name}: {blanks} empty cell(s) under a candidate, read as none")
    for party, paths in files["senate"].items():
        election = Primary(year, party)
        for path in paths:
            alone = []
            try:
                said = []
                got = read_senate(path, election, legacy, file_party(path.name)[1], said, alone)
                notes.extend(said)
            except PSR.Unreadable:
                raise
            except PSR.Refused as e:
                refused.append({"file": path.name, "why": str(e)})
                continue
            refused += [{"file": path.name, "race": f"{PARTIES[party].upper()}|S|{a['district']}",
                         "why": a["why"]} for a in alone]
            read.append(path)
            blanks = 0
            for n, rec in got.items():
                blanks += rec["blank_named"]
                where = f"{path.name}, district {n}"
                try:
                    settle(party, f"S|{n}", rec, 1, where, False)
                except PSR.Refused as e:
                    refused.append({"file": path.name,
                                    "race": f"{PARTIES[party].upper()}|S|{n}", "why": str(e)})
            if blanks:
                notes.append(f"{path.name}: {blanks} empty cell(s) under a candidate, read as "
                             "none")
    import parse_sos_primary_offices as PO
    others, also, said, alone, bad = PO.read_year(root, year)
    races.update(others)
    read += also
    notes += said
    refused += alone
    doc = {"_about": [
                "What the Secretary of State's State Primary results files say, each party's "
                "primary its own race: the State Representative and State Senate races, read by "
                "src/parse/parse_sos_primary_results.py and held to the same year's general "
                "election (collected/election_<year>.json), and Governor, United States "
                "Senator, Representative in Congress, Executive Councilor and the county "
                "offices, read by src/parse/parse_sos_primary_offices.py; each from the files "
                "in _source. Nothing in it is this project's decision but the nominees, which "
                "the files do not mark: the candidates with the most votes, as many as the race "
                "has seats and none with no votes; null where the count does not settle it.",
                "Write the file again by running the reader, never by hand: --check says where "
                "the saved files and this disagree."],
           "_source": [PSR.described(p, root) for p in read],
           "election": Primary(year, "democratic").isoformat(),
           "general": BME.general_election(year).isoformat(),
           "term": BME.term_after(year),
           "races": {k: races[k] for k in sorted(races, key=race_order)}}
    if notes:
        doc["_notes"] = notes
    if refused:
        doc["_refused"] = refused
    if bad:
        # A file that disagrees with itself, recorded with where, never corrected.
        doc["_disagreements"] = bad
    return doc


# The statewide and district offices first, in this order; then the Senate
# and the House; then the county offices, by county.
OFFICE_ORDER = ("governor", "us-senate", "us-house", "executive-council")


def race_order(key):
    """A race's place in the file: its office's, then the party's."""
    party, rest = key.split("|", 1)
    parts = rest.split("|")
    if parts[0] in OFFICE_ORDER:
        return (0, (OFFICE_ORDER.index(parts[0]), int(parts[1]) if len(parts) > 1 else 0), party)
    if BME.KEY_RE.match(rest):
        return (1, BME.race_order(rest), party)
    return (2, (parts[1], parts[0], int(parts[2]) if len(parts) > 2 else 0), party)


def dumps(doc):
    """The document as one race to a line or few, so that a diff is the race
    it moved and no more."""
    out = ["{"]
    for k in ("_about", "_notes", "_refused", "_disagreements"):
        if doc.get(k):
            out.append(f' "{k}": ' + json.dumps(doc[k], ensure_ascii=False, indent=2)
                       .replace("\n", "\n ") + ",")
    out.append(' "_source": [')
    out.append(",\n".join("  " + json.dumps(s, ensure_ascii=False) for s in doc["_source"]))
    out.append(" ],")
    for k in ("election", "general", "term"):
        out.append(f' "{k}": {json.dumps(doc[k])},')
    out.append(' "races": {')
    keys = list(doc["races"])
    for i, k in enumerate(keys):
        r = dict(doc["races"][k])
        cands = r.pop("candidates")
        head = json.dumps(r, ensure_ascii=False)[:-1]
        body = ",\n".join("    " + json.dumps(c, ensure_ascii=False) for c in cands)
        out.append(f'  {json.dumps(k)}: {head}, "candidates": [\n{body}]}}'
                   + ("," if i < len(keys) - 1 else ""))
    out.append(" }")
    out.append("}")
    return "\n".join(out) + "\n"


def same_but_days(a, b):
    """Whether two documents agree, the days the files were saved aside (a
    checkout does not keep a file's modification day)."""
    def plain(d):
        d = json.loads(json.dumps(d))
        for s in d.get("_source") or []:
            s.pop("saved", None)
        return d
    return plain(a) == plain(b)


def summary(doc):
    races = doc["races"]
    house = [k for k in races if "|H|" in k]
    senate = [k for k in races if "|S|" in k]
    cands = [c for r in races.values() for c in r["candidates"]]
    return (f"{len(doc['_source'])} files read; {len(house)} House races, {len(senate)} Senate "
            f"and {len(races) - len(house) - len(senate)} of other offices; {len(cands)} candidates, "
            f"{sum(c['nominated'] is True for c in cands)} nominated, "
            f"{sum(c['nominated'] is None for c in cands)} not settled; "
            f"{sum(r['printed_totals'] for r in races.values())} printed Totals held; "
            f"{len(doc.get('_refused') or [])} refused; "
            f"{len(doc.get('_disagreements') or [])} disagreement(s) recorded")


def years_on_disk(root="."):
    d = Path(root) / SOURCES
    return [y for y in YEARS if any(d.glob(f"{y}-sp-*"))]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--year", type=int)
    ap.add_argument("--all", action="store_true", help="every year whose files are on disk")
    ap.add_argument("--check", action="store_true", help="read again and compare with the "
                                                         "committed file; write nothing")
    ap.add_argument("--not-read", action="store_true", help="list the year's primary files on "
                                                            "disk that are not read, with why")
    a = ap.parse_args()
    years = years_on_disk() if a.all else [a.year] if a.year else []
    if not years:
        ap.error("--year or --all")
    if a.not_read:
        for y in years:
            for p, why in unread(".", y):
                print(f"{p.name}: {why}")
        return 0
    bad = 0
    for y in years:
        if y not in YEARS:
            print(f"REFUSED: {y} is not a State Primary these files hold", file=sys.stderr)
            return 1
        try:
            doc = read_year(".", y)
        except PSR.Refused as e:
            print(f"REFUSED: {y}: {e}", file=sys.stderr)
            return 1
        path = out_path(y)
        if a.check:
            try:
                committed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                print(f"{y}: {path.as_posix()} will not read: {e}")
                bad += 1
                continue
            if not same_but_days(doc, committed):
                print(f"{y}: {path.as_posix()} is not what the saved files say")
                bad += 1
                continue
            print(f"{y}: as committed. {summary(doc)}")
            continue
        path.write_text(dumps(doc), encoding="utf-8", newline="\n")
        print(f"{y}: wrote {path.as_posix()}. {summary(doc)}")
        for r in doc.get("_refused") or []:
            print(f"  REFUSED {r['file']}" + (f" {r['race']}" if r.get("race") else "")
                  + f": {r['why']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
