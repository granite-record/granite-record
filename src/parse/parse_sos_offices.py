#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-17.4
"""
The Secretary of State's count of a general election's races for Governor,
United States Senator, Representative in Congress, Executive Councilor and
the county offices, read into collected/election_offices_<year>.json, for
2016 to 2026 (the elections plan's stages 4 and 5, readers only: nothing on
the site reads these files yet).

    python3 src/parse/parse_sos_offices.py --year 2026        # write one year
    python3 src/parse/parse_sos_offices.py --all              # every year on disk
    python3 src/parse/parse_sos_offices.py --all --check      # read again; write nothing
    python3 src/parse/parse_sos_offices.py --all --registry reports/sos-downloads-2026-11-10.json

WHAT IT READS, in records/sources/, saved by a person in a browser byte for
byte under the names the Secretary of State gave them (nothing here asks the
network):

    <year>-[ge-]governor[_N].xls             2016-2024: one workbook, a summary
    <year>-[ge-]us-senator[_N].xls           of the counties and a block of
                                             towns for each county
    <year>-ge-governor-summary.xlsx          2026: the summary in a file of its
    <year>-ge-governor-<county>.xlsx         own, and a file for each county
    (and the same for us-senator)
    <year>-[ge-]congressional-district-<n>[_N].xlsx      a district a file
    <year>-[ge-]executive-council-district-1-5[_N].xls   2016-2024: a district a sheet
    <year>-ge-executive-council-<n>.xlsx                  2026: a district a file
    <year>-ge-<county>-county[_N].xls           2016, 2022 } a county's offices,
    <year>-ge-county-<county>[_N].xls           2018, 2020 } one file a county
    <year>-ge-county-offices-<county>[_N].xls   2024, 2026 }

A recount's later upload of a name (_N) replaces the earlier, as the House
reader has it (parse_sos_results.latest).

ONE FILE A YEAR, beside collected/election_<year>.json, because the Secretary
of State publishes the results of one election together and replaces a
year's file after a recount: a rerun then touches that year alone, and
--check reads it again the way the House reader's does.

THE LAYOUT, AS THE FILES HAVE IT (read on 17 November 2026 before a line of
this was written). A sheet's title rows say "State of New Hampshire - General
Election", then the election's day and the office. Then blocks: a header row
whose first cell is "Summary By Counties" or a county ("Belknap County",
"Cheshire", "BELKNAP COUNTY") and whose other cells name the candidates
("Chris Sununu, r") and the counts that are no candidate's (Scatter in
2016-2022; Undervotes, Overvotes and Write-Ins in 2024; Write-Ins in 2026);
a row per county, or per town or ward; and a TOTALS row. The summary prints
full names; the county blocks of 2016-2022 print a surname ("Sununu, r") and
sometimes another party label ("l" for the summary's "lib") and another
order (2022's US Senator), so a county's column is matched to the summary's
by name and party, one to one, or the file is refused.

A DISTRICT OFFICE'S SHEET (Congress, the Council) is one district: its
titles say the State and "Congressional District 1" or "Executive Council -
District No. 1", then a header row whose first cell is the day, a row per
town or ward across the counties, and Totals. A file holds exactly the
districts its name says, and a district with no file is listed as not on
file. Such a race's count is its places' sum, as the House reader's is (a
RECOUNT column's where one follows a count), and the reader refuses a race
that the printed Totals would give to someone else.

A COUNTY'S OFFICES are side by side: under the titles ("Belknap County
Offices"), a row of labels -- Sheriff, Attorney, Treasurer, Reg. of Deeds,
Register of Probate, and the commissioners' "District 1", "Dist. 2",
"District No. 3", under a "County Commissioners" banner or none -- then a
row of candidates, the places and a TOTALS row, again for the next offices
and on further sheets (2024, 2026). A label opens a race that runs to the
column before the next label. A commissioner district's race is the places
that print a count under it; a district marked "No Election" (in the label,
candidate or first place row) is listed in "_no_election" and read as no
race. Strafford's commissioners of 2016-2022 are one race at large, and the
file prints no number of seats: the count is kept and no one is marked
elected. A race the reader cannot settle alone (2020's Grafton Register of
Probate, won by a write-in, whose scattered write-ins outnumber the winner)
is refused alone and listed in "_refused"; a layout it does not know stops
the year.

WHAT IT WRITES, per race: the candidates with their parties and counts, who
the count elects (the files mark no winner: the most votes; a tie is null),
the counts that are no candidate's, each county's row in the summary and its
block's Totals, every town or ward row as the file prints it, with its file,
sheet and row, and every Totals row printed. A race's count is the statewide
summary's TOTALS -- the figure the Secretary of State prints for the state
(the elections plan's decision 3) -- and the reader refuses a race where
another figure the files print (the counties' Totals, the towns' sum) would
elect someone else.

THE TIE-OUT (collected/election_offices_tieout.json, one entry a year, and a
writer of it merges): each column's places against the Totals row printed
under them; each county's row in the summary against its own block's Totals;
each race's count against its places' sum. A file that disagrees with itself
is RECORDED, never corrected, with the file, sheet and row; preflight fails
when the record changes.

IT REFUSES RATHER THAN GUESSES, saying which file, sheet and row: a title,
day, header or cell it does not recognise; a county twice or none; a county
column it cannot match to the summary's; a count that is not a whole number;
two files of one race under one upload number. Each exception it reads past
is named below by its file, with why, and said in "_notes": a typo in the
official record flags rather than fails (the person's rule).
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
import election_town_rows as ETR
import parse_sos_results as PSR
import state_settings as ST

SOURCES = PSR.SOURCES
YEARS = (2016, 2018, 2020, 2022, 2024, 2026)
TIEOUT = Path("collected") / "election_offices_tieout.json"
COUNTIES = ST.COUNTIES
# The 2016-2022 layout: a surname, Scatter, and no Undervotes or Overvotes.
LEGACY_UNTIL = PSR.LEGACY_UNTIL


def out_path(year, root="."):
    return Path(root) / "collected" / f"election_offices_{year}.json"


# The offices, each with the words its sheets' title rows use. `key` is the
# race's key in the file; `contest` is the elections plan's id
# (<date>.general.<office>.<district>).
OFFICES = {
    "governor": {"name": "Governor", "title": re.compile(r"^governor$", re.I),
                 "file": "governor"},
    "us-senate": {"name": "United States Senator",
                  "title": re.compile(r"^united states senator$", re.I),
                  "file": "us-senator"},
}
# The offices elected by district, each its sheets' title: one district a
# sheet. How many districts each has is the settings' (office_districts).
DISTRICT_OFFICES = {
    "us-house": {"name": "Representative in Congress",
                 "title": re.compile(r"^congressional district\s+(\d+)$", re.I),
                 "file": "congressional-district"},
    "executive-council": {"name": "Executive Councilor",
                          "title": re.compile(r"^executive council\s*-\s*district no\.?\s*(\d+)$",
                                              re.I),
                          "file": "executive-council"},
}
# 2016-2024: -congressional-district-1, -executive-council-district-1-5 (2020
# and 2022 without "ge-"); 2026: -executive-council-1 to -5.
DISTRICT_FILE = re.compile(r"^(?P<y>\d{4})-(?:ge-)?(?P<office>congressional-district|"
                           r"executive-council)-(?:district-)?(?P<a>\d+)(?:-(?P<b>\d+))?"
                           r"(?:_\d+)?\.xlsx?$")
# A county's offices: 2016 and 2022 -<county>-county, 2018 and 2020
# -county-<county>, 2024 and 2026 -county-offices-<county>.
COUNTY_FILE = re.compile(r"^(?P<y>\d{4})-ge-(?:county-offices-(?P<a>[a-z]+)|county-(?P<b>[a-z]+)|"
                         r"(?P<c>[a-z]+)-county)(?:_\d+)?\.xlsx?$")
# A county file whose name misspells its county, by name, with the county.
COUNTY_FILE_TYPOS = {"2018-ge-county-sullivanl.xls": "sullivan"}
STATEWIDE_FILE = re.compile(r"^(?P<y>\d{4})-(?:ge-)?(?P<office>governor|us-senator)"
                            r"(?:-(?P<part>[a-z]+))?(?:_\d+)?\.xlsx?$")
SUMMARY = re.compile(r"^summary by counties$", re.I)
COUNTY_HEAD = re.compile(r"^(?P<c>[A-Za-z]+)(?:\s+county)?$", re.I)
TITLE = re.compile(r"\bstate of new hampshire\b", re.I)
# A State Primary's title of 2018: "New Hampshire Primary Election - September
# 11, 2018", "New Hampshire - Primary Election - September 11,2018", "State of
# New Hampshire - Primary Election - September 11, 2018": the State, and the
# day at its end, where the office's row and the header print none.
PRIMARY_TITLE = re.compile(r"\bnew hampshire\b.*\bprimary election\b(?:\s*-\s*(?P<day>.+))?$",
                           re.I)
# "November 3,2020" (2020's Grafton and Strafford sheets): the day written
# out with no space after the comma, read as the day it names.
DAY_TIGHT = re.compile(r"^(?P<m>[A-Za-z]+) (?P<d>\d{1,2}),\s*(?P<y>\d{4})$")
# A county block the workbook does not hold, by file and county, with why:
# the summary's row is then the county's only figure, and is not tied out.
NO_BLOCK = {
    ("2016-ge-governor.xls", "Coos"):
        "the workbook has no sheet of Coos's towns (its sheets are the summary with Belknap, "
        "Carroll, Cheshire, Grafton, Hillsborough, Merrimack, Rockingham, and Strafford with "
        "Sullivan)",
}
# A sheet whose day row prints another election's day, by file and sheet,
# with why. 2018's governor workbook prints 8 November 2016 on two sheets.
DAY_TYPOS = {
    ("2018-ge-governor.xls", "carroll gov"): "its other sheets and its name say 6 November 2018",
    ("2018-ge-governor.xls", "grafton gov"): "its other sheets and its name say 6 November 2018",
    # The State Primary's (parse_sos_primary_offices).
    ("2024-sp-governor-republican_2.xlsx", "Sull Gov"):
        "it prints the 2022 primary's day, and its other sheets print 10 September 2024",
}


class Refused(PSR.Refused):
    """A file this does not recognise: nothing is written."""


# ---- cells ---------------------------------------------------------------------

def trimmed(row):
    row = list(row)
    while row and row[-1] is None:
        row.pop()
    return row


def day_of(v):
    """The election's day as a cell prints it: a date, a serial number, the
    day written out ("November 03, 2026"), or that with no space after the
    comma ("November 3,2020"); None for anything else."""
    d = PSR.as_day(v)
    if d is None and isinstance(v, str):
        m = DAY_TIGHT.match(v.strip())
        if m:
            try:
                d = datetime.datetime.strptime(f"{m.group('m').title()} {m.group('d')} "
                                               f"{m.group('y')}", "%B %d %Y").date()
            except ValueError:
                d = None
    return d


def count(v, kind, where, col):
    """A cell as a count: a whole number; a dash ("-", "--") is a place no
    vote came from, 0; an empty cell is None (no figure printed), and "N/A"
    under a count that is no candidate's is the same. Anything else refuses."""
    if isinstance(v, str) and PSR.DASHES.fullmatch(v.strip()):
        return 0
    if isinstance(v, str) and v.strip().upper() == "N/A" and kind not in VOTE_KINDS:
        return None
    if v is None:
        return None
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise Refused(f"{where}: {v!r} in column {col + 1}, where a count belongs")
    return v


VOTE_KINDS = ("candidate", "write_in_named")
META_KINDS = {"scatter": "write_ins_scattered", "under": "undervotes", "over": "overvotes"}
# A header cell the official record prints in a way no rule reads, by file
# and its exact text, read as the cell it is, with why (a typo flags, not
# fails). 2016's first congressional district prints two names after the
# Scatter column with no party, where each candidate on the ballot carries
# one: write-ins it names, as the House files of those years mark "w-in".
_AFTER_SCATTER = ("a name with no party after the Scatter column, where every candidate on the "
                  "ballot carries a party: a write-in the file names")
_NO_COMMA = "the comma before the party letters is left out"
HEADER_FIXES = {
    ("2016-ge-congressional-district-1.xlsx", "Ashooh"): ("Ashooh w-in", _AFTER_SCATTER),
    ("2016-ge-congressional-district-1.xlsx", "John Potucek"): ("John Potucek w-in",
                                                               _AFTER_SCATTER),
    ("2016-ge-strafford-county.xls", "Dubois d/r"): ("Dubois, d/r", _NO_COMMA),
    ("2016-ge-strafford-county.xls", "Velardi d/r"): ("Velardi, d/r", _NO_COMMA),
}


def heads(row, where, legacy, notes=None, primary=False):
    """The columns a header row names, as parse_sos_results.entities reads
    them, each given its row kind: candidate, write_in_named, or one of the
    counts that are no candidate's. A header cell HEADER_FIXES names is read
    as it says, and said in `notes`. `primary`: a State Primary's header,
    whose name with no party entities reads and flags."""
    row = list(row)
    name = where.split(",")[0]
    for c, v in enumerate(row):
        fix = HEADER_FIXES.get((name, v)) if isinstance(v, str) else None
        if fix:
            row[c] = fix[0]
            if notes is not None:
                notes.append(f"{where}: the header prints {v!r}, read as {fix[0]!r}: {fix[1]}")
    out = []
    for e in PSR.entities(row, 1, where, legacy, primary):
        if e.get("blc") is not None or e.get("header_count") is not None:
            raise Refused(f"{where}: a BLC column or a count in a header, which these files are "
                          "not known to print")
        if "meta" in e:
            kind = META_KINDS[e["meta"]]
        else:
            kind = "write_in_named" if e["write_in"] else "candidate"
        if primary and notes is not None and e.get("typo"):
            # What entities read past in a State Primary's header, said.
            notes.append(f"{where}: the header prints {e['typo'][0]!r}, read as {e['typo'][1]}")
        out.append(dict(e, kind=kind))
    return out


def label(e):
    """A column's name in the file's own words: "Chris Sununu, r", or the
    count's kind."""
    if e["kind"] in VOTE_KINDS:
        return f"{e['name']}, {e['party']}" if e["party"] else e["name"]
    return e["kind"]


def name_words(name):
    """A name's words, its commas and a Jr., Sr. or numeral after it set aside."""
    words = re.sub(r",", " ", name).split()
    while len(words) > 1 and words[-1].rstrip(".").lower() in ("jr", "sr", "ii", "iii", "iv"):
        words.pop()
    return [w.lower() for w in words]


def ends_with(full, short):
    """Whether `short` is `full` or its last words: "Van Ostern" of "Colin
    Van Ostern", "Sununu" of "Chris Sununu"."""
    a, b = name_words(full), name_words(short)
    return bool(b) and a[-len(b):] == b


def parties_agree(a, b):
    """"lib" and "l", "ind" and "i": the same party's letters, one the
    start of the other."""
    a, b = a.lower(), b.lower()
    return a == b or (a and b and (a.startswith(b) or b.startswith(a)))


def match_columns(full, short, where):
    """{index in `short`: index in `full`}: a county block's columns matched
    to the summary's, one to one -- a candidate by the summary's name or its
    surname and a party that agrees, a count by its kind. Refused where any
    is left over or could be two."""
    out, taken = {}, set()
    for j, e in enumerate(short):
        hits = []
        for i, f in enumerate(full):
            if e["kind"] != f["kind"]:
                continue
            if e["kind"] not in VOTE_KINDS:
                hits.append(i)
            elif ends_with(f["name"], e["name"]) and parties_agree(e["party"], f["party"]):
                hits.append(i)
        if len(hits) != 1 or hits[0] in taken:
            raise Refused(f"{where}: the column {label(e)!r} matches "
                          + ("no column" if not hits else f"{len(hits)} columns" if len(hits) > 1
                             else "a column already matched")
                          + " of the summary's header")
        out[j] = hits[0]
        taken.add(hits[0])
    left = [label(full[i]) for i in range(len(full)) if i not in taken]
    if left:
        raise Refused(f"{where}: the summary's {', '.join(map(repr, left))} has no column here")
    return out


# ---- a block: a header row, its rows and its Totals ----------------------------------

class Block:
    """A header row, the rows of places under it and the Totals row. Its
    columns (`cols`) are each entity's count and, where a RECOUNT column
    follows it, the recount's: (entity, 0) and (entity, 1). `span` is the
    columns the block owns, where a sheet holds several side by side (the
    county offices); None for all of them. `primary`: a State Primary's
    block (parse_sos_primary_offices), whose empty cell under a candidate is
    none, as parse_sos_results.Block has it; blank_named counts them."""

    def __init__(self, label, ents, where, path, sheet, span=None, primary=False):
        self.label, self.ents, self.where = label, ents, where
        self.path, self.sheet, self.span = path, sheet, span
        self.rows, self.totals, self.notes = [], None, []
        self.primary, self.blank_named = primary, 0
        self.cols = [(e, k) for e in ents for k in (0, 1) if k == 0 or e["recount"] is not None]

    def at(self, where):
        m = re.search(r"row (\d+)$", where)
        return [self.path.name, self.sheet, int(m.group(1))]

    def race_col(self, e):
        """The index in `cols` of the count an entity's race total is made
        of: its recount's where it has one."""
        return self.cols.index((e, 1 if e["recount"] is not None else 0))

    def read(self):
        """({place: [count per column]}, [the Totals' figure per column, None
        where it prints none], [disagreements]). A named write-in's empty
        cell is nought where the Totals account for it, as the House reader
        has it; a candidate's empty cell in a row of counts is refused."""
        got, seen = {}, set()
        named = {c for e in self.ents for c in (e["col"], e.get("recount")) if c is not None}
        for place, row, where in self.rows + ([(None, *self.totals)] if self.totals else []):
            # A column no header names holds nothing (2026 prints 0 in its Totals).
            span = self.span if self.span is not None else range(1, len(row))
            stray = [c for c in span if c < len(row) and c not in named and row[c] is not None
                     and row[c] != 0 and not (isinstance(row[c], str)
                                              and PSR.DASHES.fullmatch(row[c].strip()))]
            if stray:
                raise Refused(f"{where}: {row[stray[0]]!r} in column {stray[0] + 1}, which no "
                              "header names")

        def cell(row, e, k, where):
            c = e["col"] if k == 0 else e["recount"]
            v = row[c] if c < len(row) else None
            if isinstance(v, str) and v.strip().isdigit():
                # A count saved as text ("0", 2018's Coos): read as the number.
                self.notes.append(f"{where}: {v!r} in column {c + 1} is a count written as "
                                  f"text; read as {int(v)}")
                v = int(v)
            return count(v, e["kind"], where, c)
        for place, row, where in self.rows:
            if place in seen:
                raise Refused(f"{where}: {place} twice under one header")
            seen.add(place)
            got[place] = [cell(row, e, k, where) for e, k in self.cols]
            if self.primary:
                # A STATE PRIMARY'S EMPTY CELL UNDER A CANDIDATE IS NONE (18
                # November 2026): its files name every candidate any place
                # wrote in, of any party, and print a count only where a vote
                # came. Its Totals' empty cell is no figure printed.
                for i, (e, _k) in enumerate(self.cols):
                    if got[place][i] is None and e["kind"] in VOTE_KINDS:
                        got[place][i] = 0
                        self.blank_named += 1
        if not got:
            raise Refused(f"{self.where}: a header with no rows of counts under it")
        printed = [None] * len(self.cols)
        bad = []
        if self.totals is not None:
            row, where = self.totals
            for i, (e, k) in enumerate(self.cols):
                said = cell(row, e, k, where)
                printed[i] = said
                if said is None:
                    continue
                empty = [p for p, v in got.items() if v[i] is None]
                total = sum(v[i] or 0 for v in got.values())
                # AN EMPTY CELL THE TOTALS ACCOUNT FOR IS NOUGHT, as the House
                # reader has it for a write-in's: a candidate's too (2020's Coos,
                # Green's Grant), where the column's places make its Totals
                # with it as nought. Where the other places already pass the
                # Totals, no count in it could make them agree, and it is read
                # as nought with the disagreement recorded (2020's Grafton,
                # Livermore); where they fall short it may hold the rest, and
                # the race is refused.
                if empty and e["kind"] in VOTE_KINDS:
                    if total < said:
                        raise Refused(f"{where}: {col_label(e, k)} has an empty cell for "
                                      f"{', '.join(empty)}, and the places fall {said - total:,} "
                                      "short of the Totals, which it may hold")
                    for p in empty:
                        got[p][i] = 0
                    self.notes.append(f"{where}: {col_label(e, k)} has an empty cell for "
                                      f"{', '.join(empty)}; read as none, "
                                      + ("as the Totals account for it" if total == said else
                                         "as the other places already pass the Totals (the "
                                         "disagreement is recorded)"))
                if total != said:
                    bad.append({"check": "a column's places sum to the file's Totals",
                                "what": f"{self.label}: {col_label(e, k)}, the places add up to "
                                        f"{total:,}, the file's Totals say {said:,}",
                                "where": where})
        for i, (e, k) in enumerate(self.cols):
            empty = [p for p, v in got.items() if v[i] is None]
            if e["kind"] in VOTE_KINDS and empty:
                raise Refused(f"{self.where}: {col_label(e, k)} has an empty cell for "
                              f"{', '.join(empty)}, and no Totals account for it")
        return got, printed, bad


def contest_kind(election):
    """(the contest's word, the rule that marks its winners, the key it marks
    them under): ("general", parse_sos_results.elect, "elected"), or a State
    Primary's, which its day carries (parse_sos_primary_results.Primary):
    ("primary-r", nominate, "nominated")."""
    if getattr(election, "party", None) is None:
        return "general", PSR.elect, "elected"
    return election.contest, election.choose, election.mark


def col_label(e, k):
    """A column's name: the entity's, and " (recount)" for its recount's."""
    return label(e) + (" (recount)" if k else "")


def footnote(block, text, where, width):
    if width != 1:
        raise Refused(f"{where}: {text!r}, a starred row that is not a footnote of one cell")
    block.notes.append(f"{where}: the file's footnote {text!r}; the figures are those it prints")


def place_name(v):
    """A place as the file prints it, the star a clerk's correction puts on
    it dropped ("Barnstead*", "Manchester - Ward 5 *")."""
    return v.rstrip("*").strip() if isinstance(v, str) else v


# ---- the statewide offices -------------------------------------------------------

def state_title(text, election):
    """(whether `text` is the State's title row, the day its end prints or
    None): TITLE's, or a State Primary's PRIMARY_TITLE (2018), whose day is
    then read off its end."""
    if TITLE.search(text):
        m = PRIMARY_TITLE.search(text) if hasattr(election, "party") else None
        return True, (day_of(m.group("day").strip()) if m and m.group("day") else None)
    if hasattr(election, "party"):
        m = PRIMARY_TITLE.search(text)
        if m:
            return True, day_of(m.group("day").strip()) if m.group("day") else None
    return False, None


def title_rows(rows, path, sheet, election, office, at, notes):
    """The index of the first row after a sheet's titles, which must say
    the State of New Hampshire, the office and the election's day (a State
    Primary's of 2018 at the end of the State's title: state_title)."""
    said_state = said_office = False
    titled = None
    for i, row in enumerate(rows):
        row = trimmed(row)
        if not row:
            continue
        cells = [c for c in row if c is not None]
        text = " ".join(str(c) for c in cells if isinstance(c, str))
        is_state, day_said = state_title(text, election)
        if is_state and len(cells) == 1:
            years = re.findall(r"\b(?:19|20)\d\d\b", text)
            if years and years != [str(election.year)]:
                raise Refused(f"{at(i)}: {text!r} is the title of another election")
            said_state, titled = True, day_said
            continue
        strs = [c for c in cells if isinstance(c, str)]
        if strs and office["title"].match(strs[-1].strip()):
            day = next((day_of(c) for c in cells if day_of(c) is not None), titled)
            if day is None and said_state and hasattr(election, "party"):
                # A STATE PRIMARY'S SHEET THAT PRINTS NO DAY (2018's Democratic
                # and Libertarian Governor; 2022's Republican Governor), under a
                # title that names the primary and an office row that names its
                # party: read as the primary's, and said. A day that is another
                # is refused, as ever, unless DAY_TYPOS names it.
                notes.append(f"{at(i)}: the sheet prints no day; read as the primary of "
                             f"{election}, which its titles name")
            elif day != election:
                why = DAY_TYPOS.get((path.name, sheet))
                if why is None:
                    raise Refused(f"{at(i)}: the sheet's day is {day}, not the election of "
                                  f"{election}")
                notes.append(f"{at(i)}: the sheet prints the day {day}; read as {election}, as "
                             f"{why}")
            said_office = True
            continue
        if not (said_state and said_office):
            raise Refused(f"{at(i)}: {row!r} before the sheet's titles name the State, the "
                          f"{office['name']} and the day")
        return i
    raise Refused(f"{path.name}, sheet {sheet!r}: titles and nothing under them")


def statewide_blocks(path, office, election, legacy, notes):
    """[Block, ...] of one statewide file, every sheet's, in order: each a
    summary (label "summary") or a county's (label the county)."""
    out = []
    for sheet, rows in PSR.sheets(path):
        def at(i, sheet=sheet):
            return f"{path.name}, sheet {sheet!r}, row {i + 1}"
        start = title_rows(rows, path, sheet, election, office, at, notes)
        cur = None
        for i in range(start, len(rows)):
            row = trimmed(rows[i])
            if not row:
                continue
            head = row[0]
            # A header: a county's name, then names -- not a place of dashes
            # ("Kilkenny", "-", "-", 2020's Coos).
            if isinstance(head, str) and (SUMMARY.match(head.strip()) or (
                    COUNTY_HEAD.match(head.strip()) and len(row) > 2 and all(
                        v is None or isinstance(v, str) for v in row[1:]) and any(
                        isinstance(v, str) and not PSR.DASHES.fullmatch(v.strip())
                        for v in row[1:]))):
                name = "summary" if SUMMARY.match(head.strip()) else \
                    COUNTY_HEAD.match(head.strip()).group("c").title()
                if name != "summary" and name not in COUNTIES:
                    raise Refused(f"{at(i)}: {head!r} names no county of New Hampshire")
                primary = hasattr(election, "party")
                cur = Block(name, heads(row, at(i), legacy, notes if primary else None, primary),
                            at(i), path, sheet,
                            primary=hasattr(election, "party"))
                out.append(cur)
                continue
            if cur is None:
                raise Refused(f"{at(i)}: {row!r} before any header")
            if PSR.is_totals(head):
                if cur.totals is not None:
                    raise Refused(f"{at(i)}: a second Totals row under one header")
                cur.totals = (row, at(i))
                continue
            if isinstance(head, str) and head.startswith("*"):
                footnote(cur, head, at(i), len(row))
                continue
            if not isinstance(head, str):
                raise Refused(f"{at(i)}: {head!r} where a place's name belongs")
            if cur.totals is not None:
                raise Refused(f"{at(i)}: a row of counts after the Totals")
            cur.rows.append((place_name(head), row, at(i)))
    return out


def statewide_files(root, year, office):
    """{"whole": path} (2016-2024's one workbook) or {"summary": path,
    "counties": {county: path}} (2026), each name's latest upload, with
    `replaced` [(earlier, later)]; None where no file of the office is on
    disk."""
    d = Path(root) / SOURCES
    whole, summary, counties, replaced = [], [], {}, []
    for p in sorted(d.glob(f"{year}-*")) if d.is_dir() else []:
        m = STATEWIDE_FILE.match(p.name)
        if not m or m.group("y") != str(year) or m.group("office") != office["file"]:
            continue
        part = m.group("part")
        if part is None:
            whole.append(p)
        elif part == "summary":
            summary.append(p)
        elif part.title() in COUNTIES:
            counties.setdefault(part.title(), []).append(p)
        # Any other word ("-democratic") is a primary's file, read in a later stage.
    if not (whole or summary or counties):
        return None
    if whole and (summary or counties):
        raise Refused(f"the {year} {office['name']} results are saved both whole and in parts: "
                      "keep one way of saving them")
    if whole:
        return {"whole": PSR.latest(whole, f"the {office['name']} results", replaced),
                "replaced": replaced}
    if not summary:
        raise Refused(f"no {year} {office['name']} summary file beside its county files")
    return {"summary": PSR.latest(summary, f"the {office['name']} summary", replaced),
            "counties": {c: PSR.latest(ps, f"{c}'s {office['name']} results", replaced)
                         for c, ps in sorted(counties.items())},
            "replaced": replaced}


def read_statewide(root, year, key, election, notes):
    """(race, [files read], [disagreements]) for one statewide office, or
    (None, [], []) where no file of it is on disk."""
    office = OFFICES[key]
    legacy = year <= LEGACY_UNTIL
    files = statewide_files(root, year, office)
    if files is None:
        return None, [], []
    notes.extend(f"{new.name} is read, and replaces {old.name}: the Secretary of State's later "
                 "upload of the same results" for old, new in files["replaced"])
    blocks, read = [], []
    if "whole" in files:
        read.append(files["whole"])
        blocks = statewide_blocks(files["whole"], office, election, legacy, notes)
    else:
        read.append(files["summary"])
        got = statewide_blocks(files["summary"], office, election, legacy, notes)
        if [b.label for b in got] != ["summary"]:
            raise Refused(f"{files['summary'].name}: holds {[b.label for b in got]}, not the "
                          "summary alone")
        blocks += got
        for c, p in files["counties"].items():
            read.append(p)
            got = statewide_blocks(p, office, election, legacy, notes)
            if [b.label for b in got] != [c]:
                raise Refused(f"{p.name}: holds {[b.label for b in got]}, not {c}'s towns alone")
            blocks += got
    summaries = [b for b in blocks if b.label == "summary"]
    if len(summaries) != 1:
        raise Refused(f"the {year} {office['name']} files hold {len(summaries)} summaries of the "
                      "counties, not one")
    summ = summaries[0]
    by_county = {}
    for b in blocks:
        if b.label == "summary":
            continue
        if b.label in by_county:
            raise Refused(f"{b.where}: {b.label} County's towns twice (also {by_county[b.label].where})")
        by_county[b.label] = b
    return settle_statewide(year, key, election, summ, by_county, read, notes)


def settle_statewide(year, key, election, summ, by_county, read, notes):
    office = OFFICES[key]
    kind, choose, mark = contest_kind(election)
    contest = f"{election.isoformat()}.{kind}.{key}.statewide"
    cols = summ.ents
    for b in [summ, *by_county.values()]:
        if any(e["recount"] is not None for e in b.ents):
            raise Refused(f"{b.where}: a RECOUNT column, which no statewide file is known to "
                          "print")
    rows, printed, bad = summ.read()
    notes.extend(summ.notes)
    if sorted(rows) != sorted(COUNTIES):
        raise Refused(f"{summ.where}: the summary's rows are {sorted(rows)}, not the ten counties")
    if summ.totals is None:
        raise Refused(f"{summ.where}: a summary with no TOTALS row")
    out_printed = [["the summary's Totals", printed, *summ.at(summ.totals[1])]]
    counties, places = {}, []
    town_sum = [0] * len(cols)
    for c in COUNTIES:
        b = by_county.get(c)
        srow = rows[c]
        where_row = next(w for p, _r, w in summ.rows if p == c)
        if b is None:
            why = NO_BLOCK.get((read[0].name, c))
            if why is None:
                raise Refused(f"no block of {c} County's towns in the {year} {office['name']} "
                              "files")
            notes.append(f"{read[0].name}: {why}; {c} County's figures are its row in the "
                         "summary, not tied out to its towns")
            counties[c] = {"summary": srow, "summary_at": summ.at(where_row), "totals": None,
                           "totals_at": None, "towns": None}
            town_sum = None
            continue
        perm = match_columns(cols, b.ents, b.where)
        got, said, bad_b = b.read()
        notes.extend(b.notes)
        bad += bad_b
        aligned = [None] * len(cols)
        towns = [0] * len(cols)
        for j, i in perm.items():
            aligned[i] = said[j]
        for p, (_place, _row, where) in zip(got, b.rows):
            vals = [None] * len(cols)
            for j, i in perm.items():
                vals[i] = got[p][j]
            places.append([c, p, vals, *b.at(where)])
            for i, v in enumerate(vals):
                towns[i] += v or 0
        counties[c] = {"summary": srow, "summary_at": summ.at(where_row),
                       "totals": aligned if b.totals is not None else None,
                       "totals_at": b.at(b.totals[1]) if b.totals is not None else None,
                       "towns": towns}
        if b.totals is not None:
            out_printed.append([f"{c} County's Totals", aligned, *b.at(b.totals[1])])
        for i, e in enumerate(cols):
            figure = aligned[i] if aligned[i] is not None else towns[i]
            if srow[i] is not None and srow[i] != figure:
                bad.append({"check": "a county's row in the summary is its block's Totals",
                            "what": f"{c}: {label(e)}, the summary prints {srow[i]:,}, the "
                                    f"county's {'Totals' if aligned[i] is not None else 'towns'} "
                                    f"say {figure:,}",
                            "where": f"{where_row}; {b.totals[1] if b.totals else b.where}"})
        if town_sum is not None:
            town_sum = [a + t for a, t in zip(town_sum, towns)]
    cands = []
    for i, e in enumerate(cols):
        if e["kind"] not in VOTE_KINDS:
            continue
        votes = printed[i]
        if votes is None and summ.primary:
            # A State Primary's summary prints no Totals under a candidate no
            # county wrote in: the counties' rows are the count, and said.
            votes = sum(rows[c][i] or 0 for c in COUNTIES)
            notes.append(f"{summ.totals[1]}: the summary's Totals print no figure for "
                         f"{label(e)}; read as its counties' rows, {votes:,}")
        if votes is None:
            raise Refused(f"{summ.totals[1]}: the summary's Totals print no figure for {label(e)}")
        cands.append({"name": e["name"], "party": e["party"], "votes": votes,
                      "write_in": e["kind"] == "write_in_named"})
    meta = {k: next((printed[i] for i, e in enumerate(cols) if e["kind"] == k), None)
            for k in META_KINDS.values()}
    where = f"the {year} {office['name']}"
    shown = choose(cands, 1, where, meta["write_ins_scattered"])
    # The race's count is the summary's; every other figure the files print
    # must elect the same.
    alts = {"the counties' rows in the summary": [sum(rows[c][i] or 0 for c in COUNTIES)
                                                  for i in range(len(cols))]}
    if town_sum is not None:
        alts["the towns' sum"] = town_sum
    if all(counties[c]["totals"] is not None for c in COUNTIES):
        alts["the counties' Totals"] = [sum(counties[c]["totals"][i] or 0 for c in COUNTIES)
                                        for i in range(len(cols))]
    for name, fig in alts.items():
        k = 0
        other = []
        for i, e in enumerate(cols):
            if e["kind"] in VOTE_KINDS:
                other.append(dict(cands[k], votes=fig[i]))
                k += 1
        if [c[mark] for c in choose(other, 1, where)] != [c[mark] for c in shown]:
            raise Refused(f"{where}: {name} elects someone other than the summary's Totals do")
    for c in shown:
        c["id"] = candidate_id(contest, c)
    race = {"office": key, "district": None, "seats": 1, "contest": contest,
            "count_from": "the summary's Totals",
            "columns": [label(e) for e in cols],
            "candidates": shown,
            "scatter": meta["write_ins_scattered"], "undervotes": meta["undervotes"],
            "overvotes": meta["overvotes"],
            "counties": counties, "places": places, "printed": out_printed}
    return race, read, bad


def candidate_id(contest, c):
    if c.get("write_in"):
        return f"{contest}.{ETR.slug(c['name'])}-write-in"
    return f"{contest}.{ETR.slug(c['name'])}" + (f"-{ETR.slug(c['party'])}" if c["party"] else "")


# ---- the district offices: Congress and the Executive Council ------------------------

def office_districts(key):
    """How many districts elect one each, from the settings' office list
    (Const. Pt. 2, Art. 60 and 65 for the Council; two for Congress)."""
    return {o["office"]: o for o in ST.SETTINGS["offices"]}[key]["seats"]


def district_files(root, year, key):
    """{"parts": {(first, last): path}, "missing": [district, ...],
    "replaced": [(earlier, later)]}: the year's saved files of a district
    office, each part's latest upload once, grouped by the districts their
    names say they hold (2016-2024's -district-1-5, 2026's -1 to -5); None
    where none is on disk."""
    office = DISTRICT_OFFICES[key]
    d = Path(root) / SOURCES
    parts, replaced = {}, []
    for p in sorted(d.glob(f"{year}-*")) if d.is_dir() else []:
        m = DISTRICT_FILE.match(p.name)
        if not m or m.group("y") != str(year) or m.group("office") != office["file"]:
            continue
        a = int(m.group("a"))
        parts.setdefault((a, int(m.group("b") or a)), []).append(p)
    if not parts:
        return None
    n = office_districts(key)
    beyond = [ps[-1].name for s, ps in parts.items() if s[0] < 1 or s[0] > s[1] or s[1] > n]
    if beyond:
        raise Refused(f"{', '.join(beyond)}: named for districts outside 1 to {n}, or backwards")
    missing, overlaps = PSR.senate_unheld(parts, n)
    if overlaps:
        d0, spans = overlaps[0]
        raise Refused(f"{office['name']} district {d0} is named by more than one saved file -- "
                      + "; ".join(parts[s][-1].name for s in spans))
    return {"parts": {s: PSR.latest(ps, f"the {office['name']} results for "
                                        f"{PSR.span_words(s)}", replaced)
                      for s, ps in sorted(parts.items())},
            "missing": missing, "replaced": replaced}


def district_blocks(path, key, election, legacy, notes, office=None):
    """{district: Block} of one file of a district office: a sheet a
    district, its titles the State and "Congressional District 1" or
    "Executive Council - District No. 1", then a header row whose first cell
    is the election's day, a row per town or ward, and Totals. `office`, its
    name and the title of its sheets, is DISTRICT_OFFICES[key] unless given
    (a State Primary's titles name the party)."""
    office = office or DISTRICT_OFFICES[key]
    out = {}
    for sheet, rows in PSR.sheets(path):
        def at(i, sheet=sheet):
            return f"{path.name}, sheet {sheet!r}, row {i + 1}"
        n, said_state, cur, titled = None, False, None, None
        for i, row in enumerate(rows):
            row = trimmed(row)
            if not row:
                continue
            head = row[0]
            cells = [c for c in row if c is not None]
            if cur is None:
                one = cells[0].strip() if len(cells) == 1 and isinstance(cells[0], str) else None
                is_state, day_said = state_title(one, election) if one else (False, None)
                if is_state:
                    years = re.findall(r"\b(?:19|20)\d\d\b", one)
                    if years and years != [str(election.year)]:
                        raise Refused(f"{at(i)}: {one!r} is the title of another election")
                    said_state, titled = True, day_said
                    continue
                m = office["title"].match(one) if one else None
                if m and n is None:
                    n = int(m.group(1))
                    continue
                # A State Primary's header of 2018 begins with nothing, the day
                # being at the end of the State's title.
                day = day_of(head) if head is not None or titled is None else titled
                if said_state and n is not None and day is not None:
                    if day != election:
                        raise Refused(f"{at(i)}: the header's day is {day}, not the election of "
                                      f"{election}")
                    cur = Block(f"district {n}", heads(row, at(i), legacy, notes,
                                                       hasattr(election, "party")), at(i), path,
                                sheet, primary=hasattr(election, "party"))
                    continue
                raise Refused(f"{at(i)}: {row!r} before the sheet's titles name the State and "
                              f"the {office['name']}'s district, and a header begins with the day")
            if PSR.is_totals(head):
                if cur.totals is not None:
                    raise Refused(f"{at(i)}: a second Totals row under one header")
                cur.totals = (row, at(i))
                continue
            if isinstance(head, str) and head.startswith("*"):
                footnote(cur, head, at(i), len(row))
                continue
            if not isinstance(head, str):
                raise Refused(f"{at(i)}: {head!r} where a place's name belongs")
            if cur.totals is not None:
                raise Refused(f"{at(i)}: a row of counts after the Totals")
            cur.rows.append((place_name(head), row, at(i)))
        if cur is None:
            if n is None and not said_state:
                continue  # a sheet with nothing on it
            raise Refused(f"{path.name}, sheet {sheet!r}: no header of a district's counts")
        if n in out:
            raise Refused(f"{cur.where}: {office['name']} district {n} twice in one file")
        out[n] = cur
    return out


def settle_block(key, district, block, election, seats, notes):
    """(race, disagreements) of a race read from one block: its count is its
    places' sum, as the House reader's is (a recount's where the file prints
    one), and a race that the printed Totals would give to someone else is
    refused. `seats` None is a race the file prints no number of seats for:
    its counts are kept, and no one is marked elected."""
    kind, choose, mark = contest_kind(election)
    contest = f"{election.isoformat()}.{kind}.{key}.{ETR.slug(str(district))}"
    got, printed, bad = block.read()
    notes.extend(block.notes)
    sums = [sum(v[i] or 0 for v in got.values()) for i in range(len(block.cols))]
    shown_any = [any(v[i] is not None for v in got.values()) for i in range(len(block.cols))]
    votes = [e for e in block.ents if e["kind"] in VOTE_KINDS]
    cands = [{"name": e["name"], "party": e["party"], "votes": sums[block.race_col(e)],
              "write_in": e["kind"] == "write_in_named"} for e in votes]
    meta = {k: None for k in META_KINDS.values()}
    for e in block.ents:
        if e["kind"] in meta and shown_any[block.race_col(e)]:
            meta[e["kind"]] = sums[block.race_col(e)]
    where = block.where
    if seats is None:
        shown = [dict(c, **{mark: None}) for c in cands]
    else:
        shown = choose(cands, seats, where, meta["write_ins_scattered"])
        if bad:
            alt = [dict(c, votes=printed[block.race_col(e)]
                        if printed[block.race_col(e)] is not None else c["votes"])
                   for c, e in zip(cands, votes)]
            if [c[mark] for c in choose(alt, seats, where)] != [
                    c[mark] for c in shown]:
                raise Refused(f"{where}: a column adds up differently from the file's Totals, "
                              "and the two figures elect different people")
        if meta["write_ins_scattered"] is None:
            notes.append(f"{where}: the file counts no scattered write-ins, so whether a "
                         "write-in it does not name won could not be checked")
    for c in shown:
        c["id"] = candidate_id(contest, c)
    race = {"office": key, "district": district, "seats": seats, "contest": contest,
            "count_from": "the places' sum",
            "columns": [col_label(e, k) for e, k in block.cols], "candidates": shown,
            "scatter": meta["write_ins_scattered"], "undervotes": meta["undervotes"],
            "overvotes": meta["overvotes"]}
    if any(k for _e, k in block.cols):
        race["recounted"] = True
    race["places"] = [[None, p, got[p], *block.at(w)] for (p, _r, w) in block.rows]
    race["printed"] = ([["Totals", printed, *block.at(block.totals[1])]]
                       if block.totals is not None else [])
    return race, bad


def read_district(root, year, key, election, notes):
    """({race key: race}, [files read], [disagreements], [districts not on
    file]) for one district office, or (None, [], [], []) where no file of it
    is on disk."""
    office = DISTRICT_OFFICES[key]
    legacy = year <= LEGACY_UNTIL
    files = district_files(root, year, key)
    if files is None:
        return None, [], [], []
    notes.extend(f"{new.name} is read, and replaces {old.name}: the Secretary of State's later "
                 "upload of the same results" for old, new in files["replaced"])
    races, read, bad = {}, [], []
    for (a, b), path in files["parts"].items():
        read.append(path)
        got = district_blocks(path, key, election, legacy, notes)
        if sorted(got) != list(range(a, b + 1)):
            raise Refused(f"{path.name} holds district(s) {', '.join(map(str, sorted(got)))}; its "
                          f"name says {PSR.span_words((a, b))}")
        for n in sorted(got):
            race, d = settle_block(key, n, got[n], election, 1, notes)
            races[f"{key}|{n}"] = race
            bad += d
    return races, read, bad, files["missing"]


# ---- the county offices ---------------------------------------------------------------

# The labels of the county offices as the files print them, each the
# settings' office id ("Reg. of Deeds", "Reg.of Deeds", "REGISTER OF DEEDS").
COUNTY_LABELS = [
    (re.compile(r"^sheriff$", re.I), "sheriff"),
    (re.compile(r"^(?:county\s+)?attorney$", re.I), "county-attorney"),
    (re.compile(r"^treasurer$", re.I), "county-treasurer"),
    (re.compile(r"^reg(?:ister|\.)\s*of\s+deeds$", re.I), "register-of-deeds"),
    (re.compile(r"^reg(?:ister|\.)\s*of\s+probate$", re.I), "register-of-probate"),
    (re.compile(r"^(?:[a-z]+\s+)?county\s+commissioners?$", re.I), "county-commissioner"),
]
COMMISSIONER_DISTRICT = re.compile(r"^dist(?:rict|\.)\s*(?:no\.?\s*)?(\d)$", re.I)
NO_ELECTION = re.compile(r"\bno election\b", re.I)
COUNTY_TITLE = re.compile(r"^(?P<c>[A-Za-z]+) county offices$", re.I)
# A State Primary's: "Belknap County Offices - Republican", and 2026's "COOS
# COUNTY County Offices - Democratic".
PRIMARY_COUNTY_TITLE = re.compile(r"^(?P<c>[A-Za-z]+)(?: county)? county offices\s*-?\s*"
                                  r"(?P<p>democratic|republican|libertarian)$", re.I)


def county_label(v):
    """(office, district or None) a header cell names, or None: an office's
    label, or a commissioner's district ("District 1", "Dist. 2", "District
    No. 3")."""
    if not isinstance(v, str):
        return None
    v = " ".join(v.split())
    m = COMMISSIONER_DISTRICT.match(v)
    if m:
        return ("county-commissioner", int(m.group(1)))
    for pat, office in COUNTY_LABELS:
        if pat.match(v):
            return (office, None)
    return None


def county_files(root, year):
    """({county: path}, [(earlier, later)]): each county's latest upload
    once; the counties with no file the caller lists."""
    d = Path(root) / SOURCES
    found, replaced = {}, []
    for p in sorted(d.glob(f"{year}-*")) if d.is_dir() else []:
        m = COUNTY_FILE.match(p.name)
        if not m or m.group("y") != str(year):
            continue
        c = COUNTY_FILE_TYPOS.get(p.name) or m.group("a") or m.group("b") or m.group("c")
        if c.title() not in COUNTIES:
            raise Refused(f"{p.name} names no county of New Hampshire")
        found.setdefault(c.title(), []).append(p)
    return ({c: PSR.latest(ps, f"{c}'s county offices", replaced)
             for c, ps in sorted(found.items())}, replaced)


def is_place_row(row):
    """A place's row: its name, then counts, dashes or nothing -- or a "NO
    ELECTION" mark in the column of a district with no race (2016-2020
    Rockingham)."""
    head = row[0]
    if not isinstance(head, str) or PSR.is_totals(head) or head.startswith("*") or day_of(head):
        return False
    rest = [v for v in row[1:] if v is not None]
    return all(isinstance(v, int) and not isinstance(v, bool) or (isinstance(v, str) and (
        PSR.DASHES.fullmatch(v.strip()) or v.strip().isdigit() or NO_ELECTION.search(v)))
        for v in rest)


def county_sections(path, county, election, notes):
    """[(sheet, header rows [(i, row)], place rows [(place, row, where)],
    Totals (row, where))] of one county's file, every sheet's, in order: a
    section is its header rows, its places and its Totals."""
    out = []
    for sheet, rows in PSR.sheets(path):
        def at(i, sheet=sheet):
            return f"{path.name}, sheet {sheet!r}, row {i + 1}"
        said_state = said_county = False
        header, places = [], []
        for i, row in enumerate(rows):
            row = trimmed(row)
            if not row:
                continue
            cells = [c for c in row if c is not None]
            one = cells[0].strip() if len(cells) == 1 and isinstance(cells[0], str) else None
            if not (said_state and said_county):
                if one and TITLE.search(one):
                    years = re.findall(r"\b(?:19|20)\d\d\b", one)
                    if years and years != [str(election.year)]:
                        raise Refused(f"{at(i)}: {one!r} is the title of another election")
                    said_state = True
                    continue
                party = getattr(election, "party", None)
                m = (PRIMARY_COUNTY_TITLE if party else COUNTY_TITLE).match(one or "")
                if m:
                    if m.group("c").title() != county or (party and m.group("p").lower() != party):
                        raise Refused(f"{at(i)}: {one!r} in {county} County's file")
                    said_county = True
                    continue
                raise Refused(f"{at(i)}: {row!r} before the sheet's titles name the State and "
                              f"{county} County's offices")
            head = row[0]
            if PSR.is_totals(head):
                if not header or not places:
                    raise Refused(f"{at(i)}: a Totals row with no header or places above it")
                out.append((sheet, header, places, (row, at(i))))
                header, places = [], []
                continue
            if isinstance(head, str) and head.startswith("*") and len(cells) == 1:
                notes.append(f"{at(i)}: the file's footnote {head!r}; the figures are those it "
                             "prints")
                continue
            if len(cells) == 1 and county_label(head) and not places:
                # "County Commissioners" alone in the first column (2024's
                # Cheshire): the banner over the districts' labels.
                header.append((i, [None, head]))
                continue
            if is_place_row(row):
                if not header:
                    raise Refused(f"{at(i)}: {row!r} before any header")
                places.append((place_name(head), row, at(i)))
                continue
            if places:
                raise Refused(f"{at(i)}: {row!r} among the places, before their Totals")
            day = day_of(head)
            if head is not None and day is None:
                raise Refused(f"{at(i)}: {head!r} where a header's first cell is empty or the "
                              "day")
            if day is not None and day != election:
                raise Refused(f"{at(i)}: the header's day is {day}, not the election of "
                              f"{election}")
            header.append((i, row))
        if header or places:
            raise Refused(f"{path.name}, sheet {sheet!r}: a header with no Totals row under it")
    return out


def county_groups(header, where):
    """[(office, district, first column, last column or None)] of a
    section's header rows: an office's label, or a commissioner district's,
    opens a group that runs to the column before the next. A row whose one
    label is "County Commissioners" over a row of labels is the banner over
    them and opens nothing; an office's label over its district's in one
    column ("County Commissioner" over "District 3") is the district's."""
    labelled = []
    for k, (_i, row) in enumerate(header):
        found = [(c, county_label(v)) for c, v in enumerate(row) if c and county_label(v)]
        banner = (len(found) == 1 and found[0][1] == ("county-commissioner", None)
                  and k + 1 < len(header) and any(
                      county_label(v) for c, v in enumerate(header[k + 1][1]) if c))
        if not banner:
            labelled += found
    if not labelled:
        raise Refused(f"{where}: a header that names no county office")
    starts = {}
    for c, lab in labelled:
        prev = starts.get(c)
        if prev is not None and prev != lab:
            if prev == ("county-commissioner", None) and lab[0] == "county-commissioner":
                starts[c] = lab
                continue
            raise Refused(f"{where}: column {c + 1} is labelled both {prev} and {lab}")
        starts[c] = lab
    cols = sorted(starts)
    return [(*starts[c], c, cols[n + 1] - 1 if n + 1 < len(cols) else None)
            for n, c in enumerate(cols)]


def read_county(root, year, election, notes, files=None):
    """({race key: race}, [files read], [disagreements], [counties with no
    file], [{"race", "where"}: a district the file marks "No Election"]).
    `files` is ({county: path}, [(earlier, later)]), county_files' unless
    given (a State Primary's, one party's)."""
    legacy = year <= LEGACY_UNTIL
    files, replaced = county_files(root, year) if files is None else files
    notes.extend(f"{new.name} is read, and replaces {old.name}: the Secretary of State's later "
                 "upload of the same results" for old, new in replaced)
    races, read, bad, quiet, refused = {}, [], [], [], []
    for county, path in files.items():
        read.append(path)
        for sheet, header, places, totals in county_sections(path, county, election, notes):
            def at(i, sheet=sheet):
                return f"{path.name}, sheet {sheet!r}, row {i + 1}"
            gw = at(header[-1][0])
            width = max(len(r) for r in [*(r for _i, r in header), totals[0],
                                         *(r for _p, r, _w in places)])
            for office, district, first, last in county_groups(header, at(header[0][0])):
                span = range(first, (last + 1) if last is not None else width)
                key = f"{office}|{county}" + (f"|{district}" if district else "")
                cand_row, marks = [None] * span.stop, []
                for i, row in header:
                    for c in span:
                        v = row[c] if c < len(row) else None
                        if not isinstance(v, str) or county_label(v):
                            continue
                        if NO_ELECTION.search(v):
                            marks.append(at(i))
                        elif cand_row[c] is not None:
                            raise Refused(f"{at(i)}: two names in column {c + 1}'s header")
                        else:
                            cand_row[c] = v
                for _p, row, w in places:
                    if any(isinstance(row[c], str) and NO_ELECTION.search(row[c])
                           for c in span if c < len(row)):
                        marks.append(w)
                if not any(cand_row[c] for c in span):
                    if any(isinstance(r[c], int) and r[c] for _p, r, _w in places
                           for c in span if c < len(r)):
                        raise Refused(f"{gw}: counts under {key}, which no header names")
                    if marks:
                        quiet.append({"race": key, "where": marks[0], "says": "No Election"})
                    elif district is not None:
                        # A district labelled, with no candidate and no count
                        # under it (2020's Cheshire 3): no race is read.
                        quiet.append({"race": key, "where": gw,
                                      "says": "no candidate and no count"})
                        notes.append(f"{gw}: {key} is labelled, with no candidate and no count "
                                     "under it and no \"No Election\" mark; no race is read")
                    elif office != "county-commissioner":
                        raise Refused(f"{gw}: {key} has no candidates and no \"No Election\" "
                                      "mark")
                    # An office's label with no candidates of its own heads
                    # the districts that follow it.
                    continue
                if marks:
                    raise Refused(f"{marks[0]}: a \"No Election\" mark among {key}'s candidates")
                if key in races:
                    raise Refused(f"{gw}: {key} twice in {county} County's file")
                block = Block(key, heads(cand_row, gw, legacy, notes, hasattr(election, "party")),
                              gw, path, sheet, span=span,
                              primary=hasattr(election, "party"))
                block.totals = totals
                named = [c for c in span if cand_row[c]]
                for p, row, w in places:
                    vals = [row[c] if c < len(row) else None for c in span]
                    shown = [v for v in vals if v is not None]
                    if not shown:
                        if district is None:
                            # A place of a county-wide office printing nothing:
                            # its cells are held to the Totals (Block.read).
                            block.rows.append((p, row, w))
                        continue
                    if district is not None and all(v in (0, "0") for v in shown) and any(
                            (row[c] if c < len(row) else None) is None for c in named):
                        # A nought under a district the place is not in, the
                        # district's other cells empty (2016's Rockingham:
                        # Hampton's 0 under district 2): not a row of the race.
                        notes.append(f"{w}: {p} prints only a 0 under {key}, whose other "
                                     "cells it leaves empty; read as no row of that race")
                        continue
                    block.rows.append((p, row, w))
                # The commissioners of a county that elects them at large
                # (Strafford, 2016-2022): its file prints no number of seats.
                seats = None if office == "county-commissioner" and district is None else 1
                # A RACE THE READER CANNOT SETTLE IS REFUSED ALONE (2020's
                # Grafton Register of Probate, won by a write-in, whose
                # scattered write-ins outnumber the winner's count): listed in
                # _refused with why and where, and nothing of it is written.
                # The rest of the file is read; a layout it does not know
                # still stops the year.
                try:
                    race, d = settle_block(office, county.lower() + (
                        f"-{district}" if district else ""), block, election, seats, notes)
                except PSR.Unreadable:
                    raise
                except PSR.Refused as e:
                    refused.append({"race": key, "why": str(e)})
                    continue
                race["district"], race["county"] = district, county
                for pl in race["places"]:
                    pl[0] = county
                if seats is None:
                    notes.append(f"{gw}: {key} elects more than one at large and the file prints "
                                 "no number of seats, so the count is kept and no one is marked "
                                 "elected")
                races[key] = race
                bad += d
    missing = [c for c in COUNTIES if c not in files]
    return races, read, bad, missing, quiet, refused


# ---- the tie-out ------------------------------------------------------------------

def where_of(at):
    f, sheet, row = at
    return f"{f}, sheet {sheet!r}, row {row}"


def tie_out(doc):
    """{"checks": {name: {"held", "disagree"}}, "disagreements": [...]} of
    one year's document, from what it holds: every Totals row printed against
    the places under it, every county's row in a summary against its
    block's Totals, and every race's count against its places' sum. Each
    disagreement names its file, sheet and row; none is corrected."""
    checks, bad = {}, []

    def note(name, ok, what, where):
        c = checks.setdefault(name, {"held": 0, "disagree": 0})
        c["held"] += 1
        if not ok:
            c["disagree"] += 1
            bad.append({"check": name, "what": what, "where": where})
    for key, race in doc["races"].items():
        cols = race["columns"]
        for what, figs, f, sheet, row in race["printed"]:
            if what == "the summary's Totals":
                under = [vals for vals in race["counties"].values()]
                for i, said in enumerate(figs):
                    if said is None:
                        continue
                    got = sum(v["summary"][i] or 0 for v in under)
                    note("a column's places sum to the file's Totals", got == said,
                         f"{key} the summary: {cols[i]}, the counties add up to {got:,}, the "
                         f"file's Totals say {said:,}", f"{f}, sheet {sheet!r}, row {row}")
                continue
            county = what[:-len(" County's Totals")] if what.endswith(" County's Totals") else None
            mine = [p for p in race["places"] if p[0] == county] if county else race["places"]
            for i, said in enumerate(figs):
                if said is None:
                    continue
                got = sum(p[2][i] or 0 for p in mine)
                note("a column's places sum to the file's Totals", got == said,
                     f"{key} {what}: {cols[i]}, the places add up to {got:,}, the file's "
                     f"Totals say {said:,}", f"{f}, sheet {sheet!r}, row {row}")
        for c, v in (race.get("counties") or {}).items():
            if v["towns"] is None:
                continue
            for i, said in enumerate(v["summary"]):
                printed = (v["totals"] or [None] * len(cols))[i]
                fig = printed if printed is not None else v["towns"][i]
                if said is None:
                    continue
                note("a county's row in the summary is its block's Totals", said == fig,
                     f"{key} {c}: {cols[i]}, the summary prints {said:,}, the county's "
                     f"{'Totals' if printed is not None else 'towns'} say {fig:,}",
                     "; ".join(where_of(a) for a in (v["summary_at"], v["totals_at"]) if a))
        if any(v["towns"] is None for v in (race.get("counties") or {}).values()):
            continue
        for k, cand in enumerate(race["candidates"]):
            name = f"{cand['name']}, {cand['party']}" if cand["party"] else cand["name"]
            i = cols.index(name + " (recount)" if name + " (recount)" in cols else name)
            got = sum(p[2][i] or 0 for p in race["places"])
            # A race of one place prints no Totals: its row is where to look.
            at = race["printed"][0][2:] if race["printed"] else race["places"][0][3:6]
            note("a race's count is its places' sum", got == cand["votes"],
                 f"{key}: {cols[i]}, the places add up to {got:,}, the race's count is "
                 f"{cand['votes']:,}", where_of(at))
    return {"checks": {k: checks[k] for k in sorted(checks)}, "disagreements": bad}


# ---- the year ---------------------------------------------------------------------

def described(p, root, registry):
    """The _source entry of a file: the House reader's, held to the registry
    of downloads where it names the file. A file the registry does not name
    keeps no day, which only the registry records."""
    rel = p.relative_to(root).as_posix()
    if registry is not None and rel in registry:
        return PSR.described(p, root, registry=registry)
    out = PSR.described(p, root)
    out["saved"] = None
    return out


def read_year(root, year, registry=None):
    """The document for `year`, from the saved files under `root`."""
    root = Path(root).resolve()
    if year % 2 or year not in YEARS:
        raise Refused(f"{year} is not a general election this reads (it reads {YEARS})")
    election = BME.general_election(year)
    notes, races, files, bad = [], {}, [], []
    missing = []
    for key in OFFICES:
        race, read, b = read_statewide(root, year, key, election, notes)
        if race is None:
            missing.append(OFFICES[key]["name"])
            continue
        races[key] = race
        files += read
        # A disagreement is a typo in the official record: said here, recorded
        # in the tie-out, and the race keeps the count it names.
        notes.extend(f"{d['where']}: {d['what']}; the race's count is {race['count_from']}"
                     for d in b)
    for key, office in DISTRICT_OFFICES.items():
        got, read, b, gone = read_district(root, year, key, election, notes)
        if got is None:
            missing.append(office["name"])
            continue
        if gone:
            missing.append(f"{office['name']}, district " + ", ".join(map(str, gone)))
        races.update(got)
        files += read
        notes.extend(f"{d['where']}: {d['what']}; the race's count is the places' sum"
                     for d in b)
    got, read, b, gone, quiet, refused = read_county(root, year, election, notes)
    races.update(got)
    files += read
    notes.extend(f"{d['where']}: {d['what']}; the race's count is the places' sum" for d in b)
    if gone:
        missing.append("the county offices of " + ", ".join(gone))
    doc = {"_about": [
        "What the Secretary of State's results files say of the races for "
        + ", ".join(o["name"] for o in (*OFFICES.values(), *DISTRICT_OFFICES.values()))
        + " and the county offices, read by src/parse/parse_sos_offices.py from the files named in _source. Nothing in "
        "it is this project's decision but the winners, which the files do not mark: the "
        "candidate with the most votes; a tie is null. A race's count is the summary's Totals "
        "where the files print a summary of the counties, and its places' sum where they do not. "
        "Nothing on the site reads this file yet.",
        "Write it again by running the reader, never by hand: --check says where the saved files "
        "and this disagree."],
        "_source": [described(p, root, registry) for p in files],
        "election": election.isoformat(),
        "races": races}
    if missing:
        doc["_not_on_file"] = missing
        notes.append(f"Not on file for {year}: " + ", ".join(missing) + " -- no saved file of "
                     "the office's results; nothing is filled from another source.")
    if quiet:
        # A commissioner's district the file marks "No Election": no race,
        # where the mark is.
        doc["_no_election"] = quiet
    if refused:
        doc["_refused"] = refused
        notes.extend(f"Refused, and not written: {r['race']} -- {r['why']}" for r in refused)
    if notes:
        doc["_notes"] = notes
    return doc


def dumps(doc):
    """The document, a race's head on one line and each candidate, county,
    place and Totals row on its own, so that a recount's diff is the rows it
    moved."""
    out = ["{"]
    for k in ("_about", "_notes"):
        if doc.get(k):
            out.append(f' "{k}": ' + json.dumps(doc[k], ensure_ascii=False, indent=2)
                       .replace("\n", "\n ") + ",")
    if doc.get("_not_on_file"):
        out.append(' "_not_on_file": ' + json.dumps(doc["_not_on_file"], ensure_ascii=False) + ",")
    for k in ("_no_election", "_refused"):
        if doc.get(k):
            out.append(f' "{k}": [\n' + ",\n".join(
                "  " + json.dumps(q, ensure_ascii=False) for q in doc[k]) + "],")
    out.append(' "_source": [')
    out.append(",\n".join("  " + json.dumps(s, ensure_ascii=False) for s in doc["_source"]))
    out.append(" ],")
    out.append(f' "election": {json.dumps(doc["election"])},')
    out.append(' "races": {')
    keys = list(doc["races"])
    for n, k in enumerate(keys):
        r = dict(doc["races"][k])
        parts = {f: r.pop(f) for f in ("candidates", "counties", "places", "printed") if f in r}
        body = [f'  {json.dumps(k)}: ' + json.dumps(r, ensure_ascii=False)[:-1] + ","]
        body.append('   "candidates": [\n' + ",\n".join(
            "    " + json.dumps(c, ensure_ascii=False) for c in parts["candidates"]) + "],")
        if "counties" in parts:
            body.append('   "counties": {\n' + ",\n".join(
                f"    {json.dumps(c)}: " + json.dumps(v, ensure_ascii=False)
                for c, v in parts["counties"].items()) + "},")
        body.append('   "places": [\n' + ",\n".join(
            "    " + json.dumps(p, ensure_ascii=False) for p in parts["places"]) + "],")
        body.append('   "printed": [\n' + ",\n".join(
            "    " + json.dumps(p, ensure_ascii=False) for p in parts["printed"]) + "]}"
            + ("," if n < len(keys) - 1 else ""))
        out.extend(body)
    out.append(" }")
    out.append("}")
    return "\n".join(out) + "\n"


def plain(doc):
    """The document as written, without what only travels beside it."""
    return json.loads(dumps(doc))


def summary(doc):
    races = doc["races"]
    won = []
    for k, r in races.items():
        w = [c["name"] for c in r["candidates"] if c["elected"]]
        won.append(f"{k} {', '.join(w) if w else 'tied'}")
    return (f"{doc['election']}: {len(races)} race(s), {len(doc['_source'])} file(s); "
            + "; ".join(won))


def load_registry(path):
    if not path:
        return None
    try:
        return {e["file"]: e for e in json.loads(Path(path).read_text(encoding="utf-8"))}
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise Refused(f"the registry of downloads ({path}) will not read: {e}")


def years_on_disk(root="."):
    d = Path(root) / SOURCES
    return [y for y in YEARS if any(STATEWIDE_FILE.match(p.name) or DISTRICT_FILE.match(p.name)
                                    or COUNTY_FILE.match(p.name) for p in d.glob(f"{y}-*"))]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--year", type=int, help="the general election's year")
    g.add_argument("--all", action="store_true", help="every year with a file on disk")
    ap.add_argument("--check", action="store_true",
                    help="read again and compare with the committed files; write nothing")
    ap.add_argument("--registry", default=None,
                    help="the registry of downloads (JSON), which gives each _source its page "
                         "and day and holds it to the file's sha256")
    a = ap.parse_args()
    try:
        registry = load_registry(a.registry)
        years = years_on_disk() if a.all else [a.year]
        docs = {y: read_year(".", y, registry) for y in years}
    except PSR.Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    try:
        tied = json.loads(TIEOUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        tied = {}
    wrong = []
    for y, doc in docs.items():
        result = tie_out(plain(doc))
        text, path = dumps(doc), out_path(y)
        if a.check:
            try:
                committed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                committed = None
            if committed is None or committed != plain(doc) and not same_but_days(
                    committed, plain(doc)):
                wrong.append(f"{path.as_posix()} is not what the saved files say")
            if tied.get(str(y)) != result:
                wrong.append(f"{TIEOUT.as_posix()}: the tie-out of {y} is not what the saved "
                             "files give")
            print(f"{y}: " + summary(doc))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        tied[str(y)] = result
        print(f"wrote {path.as_posix()}: " + summary(doc))
        for d in result["disagreements"]:
            print(f"  DISAGREES ({d['check']}): {d['what']} [{d['where']}]")
        for n in doc.get("_notes") or []:
            print(f"  FLAGGED: {n}")
    if not a.check:
        with open(TIEOUT, "w", encoding="utf-8", newline="") as f:
            f.write(json.dumps(dict(sorted(tied.items())), ensure_ascii=False, indent=1) + "\n")
    for w in wrong:
        print(f"DIFFERS: {w}", file=sys.stderr)
    return 1 if wrong else 0


def same_but_days(a, b):
    """Whether two documents differ only in what the registry of downloads
    gives a _source (its page, address and day saved), which is on the
    person's computer and not in a checkout; the file and its sha256 are held."""
    def strip(d):
        d = json.loads(json.dumps(d))
        for s in d.get("_source") or []:
            for k in ("saved", "url", "file_url"):
                s.pop(k, None)
        return d
    return strip(a) == strip(b)


if __name__ == "__main__":
    sys.exit(main())
