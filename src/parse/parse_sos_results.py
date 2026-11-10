#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-17.6
"""
The Secretary of State's count of one general election's State Representative
and State Senate races, read into collected/election_<year>.json.

    python3 src/parse/parse_sos_results.py --year 2024          # collected/election_2024.json
    python3 src/parse/parse_sos_results.py --year 2024 --check  # compare again; write nothing
    python3 src/parse/parse_sos_results.py --year 2026 --url https://www.sos.nh.gov/...
                                         # and name the results page the files came from

WHAT IT READS. The spreadsheets the Secretary of State publishes after a
general election, saved by a person in a browser, byte for byte and under the
names the Secretary of State gave them, in records/sources/ (the person's
decision of 16 October 2026: no fetcher until the 2026 page has been seen):

    <year>-ge-house-<county>[_N].xls or .xlsx      one per county, ten in all
    <year>-ge-state-senate-district-1-24[_N].xls   every Senate district (2024)
    <year>-ge-state-senate-<n>[_N].xlsx and        the Senate split by district
    <year>-ge-state-senate-<a>-<b>[_N].xlsx        (2026): -1 ... -9, -10-11, ...

and site/districts.json, the district table every page draws from, which the
files are held against. It needs openpyxl for .xlsx and xlrd for .xls, and
nothing else outside the standard library. Nothing here asks the network.

WHAT IT WRITES. collected/election_<year>.json, in the shape
src/parse/build_members_elect.py reads (its docstring has the shape): every
race the district table names, with its seats, whether it is floterial, its
towns as the district table spells them, every candidate with a party and a
count of votes, who was elected, and the scattered write-ins. "_source" names
each file read with its sha256 and the day it was saved. A person runs this
and commits the file, so that the diff is the review. With --check it writes
nothing, and says where what it reads now differs from what is committed.

THE LAYOUT, AS THE 2024 FILES HAVE IT, read on 17 October 2026 before a line
of this was written:

  A county's House file is one sheet. Three title rows: the election, "State
  Representative(s) - <COUNTY> County", and the election's day. Then each
  district: a header row "District No. 5 (4)" -- the number, the seats, and
  " F" or "FL" for a floterial -- with a column per candidate, "Wendy Chase,
  d", then Undervotes, Overvotes and Write-Ins; a row per town or ward; and a
  Totals row where there is more than one. A district with more candidates
  than fit across the sheet goes on below, under a header row whose first
  cell is empty, with its own rows per town. A recount shows two ways: a
  "RECOUNT" column beside each candidate's count, which holds the recount's
  figure (Hillsborough 9, 17, 18 and 24; Grafton 7; Sullivan 5), or a second
  whole district, "District No. 4 (3) RECOUNT FIGURES" (Strafford 4).

  The Senate file is a sheet for one to three districts: "State Senate
  District 10", then a header row whose first cell is the election's day and
  whose others name the candidates as the House files do, a row per town or
  ward, and Totals.

  A candidate written in and named is "WRITE-IN   Kathy DesRoches"
  (Merrimack 14), with no party. A party is its letters; a cross-nominated
  candidate's are joined with "&" ("Janet Larsen, i&r"), and are written here
  joined with "/" as build_members_elect reads them.

WINNERS ARE THE TOP OF THE COUNT. The files mark no winner, so the candidates
with the most votes, as many as the race has seats, are elected; where the
last seat's count is shared, those sharing it are neither ("elected": null),
which build_members_elect draws as not final. A race whose count is a
recount's carries "recounted": true.

IT REFUSES RATHER THAN GUESSES, saying which file, sheet and row, and writes
nothing: a title, header or cell it does not recognise; a district or a place
the district table does not name; seats or a district's towns that disagree
with the district table; a race the table names and no file holds; a town's
count missing for a candidate; a column that does not add up to the Totals
the file prints beside it, which are the Secretary of State's own sums; a
write-in the file does not name who may have won -- fewer named candidates
than seats, or scattered write-ins as many as the last seat's votes; and a
file of another election, or a county's file twice under one number.

THE PERSON'S DECISIONS OF 17 OCTOBER 2026 about the reader, each as
recommended after the 2024 files were read: a printed floterial mark the
towns contradict is flagged in "_notes" and decides nothing (a typo in the
official record flags rather than fails); a write-in winner the file does not
name is refused, never guessed; and a county's file saved again after a
recount, under the Secretary of State's next number ("_8" after "_7"),
replaces the earlier, which is said in "_notes" and not read.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from html.parser import HTMLParser

import build_members_elect as BME

SOURCES = Path("records") / "sources"
COUNTIES = ("belknap", "carroll", "cheshire", "coos", "grafton", "hillsborough", "merrimack",
            "rockingham", "strafford", "sullivan")

HOUSE_FILE = re.compile(r"^(\d{4})-ge-house-([a-z]+)(?:_\d+)?\.(?:xlsx?|html)$")
# THE SENATE, WHOLE OR IN PARTS (5 November 2026). In 2024 the Secretary of
# State published one file, -district-1-24; in 2026 fifteen, named for the
# districts each holds: -1 to -9, then -10-11, -12-13, -14-16, -17-18, -19-21
# and -22-24. A file's name says which districts it holds (senate_span), each
# part is a recount's later upload of its own name (_N), and together the
# parts must hold every district once (senate_parts' caller refuses a gap or
# an overlap; senate_merged refuses a file that holds other than its name).
SENATE_FILE = re.compile(r"^(\d{4})-(?:ge-)?state-senate-(?:district-(\d+)-(\d+)|(\d+)(?:-(\d+))?)"
                         r"(?:_\d+)?\.xlsx?$")
# The Senate's districts, as the district table holds them (S|1 to S|24):
# read_all refuses a table that says otherwise, so this cannot drift silently.
SENATE_DISTRICTS = 24
# THE 2016-2022 LAYOUT (10 November 2026): the files of these years print a
# surname for a candidate, "Scatter" for write-ins nobody named, and no day;
# see LEGACY_META. 2024 and 2026 print full names, undervotes and overvotes.
LEGACY_UNTIL = 2022
# The first general election held on the districts of site/districts.json, the
# only district table on this machine: New Hampshire redistricted for 2022.
TABLE_SINCE = BME.DISTRICTS_SINCE

# EVERY SPELLING OF A DISTRICT'S HEADER THE 2024 FILES USE (17 October
# 2026), and no other: "District No. 5 (4)", "District No 17 (2)", "District
# No.7 (1)", "District 16 (1)", "District No. 31 (2)FL", "District No. 8 (2)
# F", and the recount's "District No. 4 (3) RECOUNT FIGURES". A header that
# moves from these is refused, not guessed at.
DISTRICT = re.compile(r"^district(?:\s+no\b\.?)?\s*(\d+)\s*\((\d+)\)\s*(fl|f)?\s*"
                      r"(recount figures)?$", re.I)
SENATE = re.compile(r"^state senate district\s+(\d+)$", re.I)
# The election's day as the 2026 files write it, in text (as_day).
DAY_WRITTEN = re.compile(r"^[A-Za-z]+ \d{1,2}, \d{4}$")
REP_TITLE = re.compile(r"^state representatives?\s*-\s*([a-z]+)\s+county$", re.I)
# A CANDIDATE IS A NAME, A COMMA AND THE PARTY'S LETTERS (17 October 2026):
# "Mark Proulx,r" has no space, and "Raymond C. Peeples Jr., r" has a comma
# of its own before it, so the last comma is the one that counts.
# The 2016-2022 files also write a cross-nomination "d/r" (2018 Strafford).
CANDIDATE = re.compile(r"^(?P<name>\S.*?)\s*,\s*(?P<party>[a-z]{1,3}(?:\s*[&/]\s*[a-z]{1,3})*)$", re.I)
# A named write-in: "WRITE-IN   Kathy DesRoches" in 2024, the word first;
# "Amanda Allen       WRITE-IN" (Hillsborough) and "Desiree McLaughlin
# WRITE-IN" (Merrimack) in 2026, the word last (5 November 2026). Either way,
# and only with the word whole at one end.
WRITE_IN = re.compile(r"^(?:write[- ]?in\s+(?P<name>\S.*)|(?P<after>\S.*?)\s+write[- ]?in)$",
                      re.I)
META = {"undervotes": "under", "overvotes": "over", "write-ins": "scatter"}
# THE 2016-2022 FILES (10 November 2026) print the write-ins nobody named as
# "Scatter", a named write-in as "Tofts w-in" (the surname, as they print every
# name), and no Undervotes or Overvotes at all.
LEGACY_META = dict(META, scatter="scatter")
DASHES = re.compile(r"-[\s-]*")
# A later header of a district that prints no seats, "District No. 2".
DISTRICT_BARE = re.compile(r"^district(?:\s+no\b\.?)?\s*(\d+)$", re.I)
LEGACY_NO_COMMA = re.compile(r"^(?P<name>[^\W\d_].*?)\s+(?P<party>[rdil])$", re.I)
# A district header the official record misprints, each named by its file and
# its exact text, read as the header it is, with why (a typo flags, not fails):
# 2022 Merrimack 30 prints (21) seats for a district that elects one.
# Rows of counts the official record leaves unnamed, each by its file and row
# (1-based), read as what the file's other rows say they are: 2022 Rockingham
# 1's first block names no town, its second names Northwood and Nottingham,
# and the first block's three rows are those two towns and, the third being
# their sum, the Totals. The column sums are held to the Totals as always.
ROW_LABELS = {("2022-ge-house-rockingham_7.xls", 4): "Northwood",
              ("2022-ge-house-rockingham_7.xls", 5): "Nottingham",
              ("2022-ge-house-rockingham_7.xls", 6): "Totals"}
ROW_LABELS_WHY = ("the district's second block names the two towns in the order of the first "
                  "block's first two rows, and the third row adds them")
HEADER_TYPOS = {
    ("2022-ge-house-strafford_0.xls", "Dover Ward 16 (1)"):
        ("District No. 16 (1)", "it stands between districts 15 and 17 and over Dover Ward 3, "
         "which the district table gives district 16"),
    ("2022-ge-house-merrimack_5.xls", "District No. 30 (21) FL"):
        ("District No. 30 (1) FL", "the district table gives it one seat, and the file's rows "
         "hold two candidates and a count for one"),
}
LEGACY_WRITE_IN = re.compile(r"^(?P<name>\S.*?)\s+\(?w(?:rite)?-?in\)?$", re.I)
LEGACY_SUFFIX = re.compile(r",\s*(jr|sr|ii|iii|iv)\.?$", re.I)
TOTALS = "totals"
URL = re.compile(r"https://\S+")

# THE UNINCORPORATED PLACES, WHICH EACH FILE ABBREVIATES ITS OWN WAY (17
# October 2026): "At. & Gilm. Ac. Grant", "Atkinson and Gilmanton Ac. Gt." and
# the district table's "Atk. & Gil. Academy Grant" are one place. A word is
# expanded only whole, and the result must then be a place the table names
# exactly, or the file is refused.
# And the other way (5 November 2026): the 2026 Coos file names "Thompson &
# Meserve's Purchase" whole, where the table abbreviates it "Thompson & Mes's
# Purchase" ("mes's" is "mess" once the apostrophe goes).
ABBREVIATIONS = {"pur": "purchase", "gt": "grant", "loc": "location", "ac": "academy",
                 "at": "atkinson", "atk": "atkinson", "gil": "gilmanton", "gilm": "gilmanton",
                 "thomp": "thompson", "mess": "meserves"}


class Refused(Exception):
    """A file this does not recognise: nothing is written."""


class Unreadable(Refused):
    """A file this machine has no library to open: not a fault in the file."""


# ---- cells -------------------------------------------------------------------

def cell(v):
    """A cell as this reads it: None for an empty one or one of spaces, a
    whole number for a count (xlrd hands every number back as a float), a
    date for a day, and a string with its ends trimmed."""
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, str):
        return " ".join(v.split()) or None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def sheets(path):
    """[(sheet name, [[cell, ...], ...]), ...] of a saved file, by its kind."""
    path = Path(path)
    if path.suffix.lower() == ".html":
        return html_sheets(path)
    try:
        if path.suffix.lower() == ".xlsx":
            import openpyxl
            book = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                return [(ws.title, [[cell(v) for v in row]
                                    for row in ws.iter_rows(values_only=True)])
                        for ws in book.worksheets]
            finally:
                book.close()
        import xlrd
    except ImportError as e:
        raise Unreadable(f"{path.name} needs {e.name} to be read: pip install openpyxl==3.1.5 "
                         "xlrd==2.0.2")
    book = xlrd.open_workbook(str(path))
    out = []
    for sh in book.sheets():
        rows = []
        for r in range(sh.nrows):
            row = []
            for c in range(sh.ncols):
                x = sh.cell(r, c)
                row.append(xlrd.xldate_as_datetime(x.value, book.datemode).date()
                           if x.ctype == xlrd.XL_CELL_DATE else cell(x.value))
            rows.append(row)
        out.append((sh.name, rows))
    return out


class _Tables(HTMLParser):
    """The rows of every <table> in a results page; a cell is its paragraphs,
    for a cell may hold two (see html_sheets)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.row, self.cell = [], None, None
        self.seen_p = self.in_p = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell, self.seen_p, self.in_p = [[]], False, False
        elif tag == "p" and self.cell is not None:
            # The text before a cell's first paragraph is the page's own spacing.
            self.cell = [[]] if not self.seen_p else self.cell + [[]]
            self.seen_p = self.in_p = True

    def handle_data(self, data):
        if self.cell is not None and (self.in_p or not self.seen_p):
            self.cell[-1].append(data)

    def handle_endtag(self, tag):
        if tag == "p":
            self.in_p = False
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(["".join(p) for p in self.cell])
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.tables[-1].append(self.row)
            self.row = None


def html_sheets(path):
    """[(table n, rows)] of a results PAGE saved as html: the Secretary of
    State's own page, for a file it publishes no spreadsheet of (2018
    Strafford, whose spreadsheet and PDF both answer 404). A cell is its
    text, a non-breaking space or nothing is empty, and "1,297" is 1297.

    A ROW WHOSE CELLS HOLD TWO PARAGRAPHS IS TWO ROWS (2018 Strafford, between
    its district 18 and 19: "TOTALS" over "District No. 19 (1)FL" in one cell,
    "2,215" over "Coleman, r" in the next): the page fused a Totals row to the
    header that follows it, and each paragraph is read as the row it is. The
    title rows each table after the first repeats are dropped."""
    parser = _Tables()
    parser.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    out = []
    for i, table in enumerate(parser.tables, 1):
        rows = []
        for r in table:
            width = max((len(c) for c in r), default=1)
            for k in range(width):
                row = []
                for c in r:
                    c = cell(c[k].replace("\xa0", " ")) if k < len(c) else None
                    if isinstance(c, str) and re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d+", c):
                        c = int(c.replace(",", ""))
                    row.append(c)
                rows.append(row)
        if i > 1:
            while rows and isinstance(rows[0][0], str) and rows[0][0].startswith(
                    ("State of New Hampshire", "State Representative")):
                rows.pop(0)
        out.append((f"table {i}", rows))
    return out


def as_day(v):
    """A day from a date cell, or from the serial number an .xls cell keeps
    a date as when it is not formatted as one (45601 is 5 November 2024), or
    from the day written out as text, as the 2026 files write it (5 November
    2026): "November 03, 2026" in the House files, "NOVEMBER 03, 2026" in the
    Senate's. That one form, the month by its whole name; nothing looser."""
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, int) and 30000 < v < 80000:
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=v)
    if isinstance(v, str) and DAY_WRITTEN.match(v):
        try:
            return datetime.datetime.strptime(v.title(), "%B %d, %Y").date()
        except ValueError:
            return None
    return None


def fold(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")


def edits(a, b):
    """The fewest letters added, taken away or changed to make `a` into `b`."""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (x != y))
    return row[-1]


def one_place(named, left):
    """Whether a name the district table does not hold can be its district's
    one place left unmatched: within two letters of it (2024 Rockingham's
    "Newfield" for Newfields), or AND ONE SHORTENED (5 November 2026) -- the
    table's name with its last word gone, as the 2026 Senate 3 file names
    "Thompson & Meserve's" for the table's "Thompson & Mes's Purchase"."""
    a, b = place_key(named), place_key(left)
    return edits(a, b) <= 2 or (" " in b and b.rsplit(" ", 1)[0] == a)


def place_key(s):
    """A place's name with its abbreviations spelled out, for matching only.
    fold() has already dropped a curly apostrophe; a straight one and a
    point go here, so that "Mes's" and "Ac." are read as one word."""
    s = re.sub(r"['.]", "", fold(s).lower().replace("&", " and "))
    return " ".join(str(int(w)) if w.isdigit() else ABBREVIATIONS.get(w, w)
                    for w in re.findall(r"[a-z0-9]+", s))


# ---- one block: a header row and the rows under it ------------------------

def entities(row, start, where, legacy=False):
    """The columns a header row names: candidates and the three counts that
    are not a candidate's, each with the column of its recount where a
    "RECOUNT" column follows it."""
    out = []
    for c in range(start, len(row)):
        v = row[c]
        if v is None:
            continue
        if legacy and isinstance(v, int) and not isinstance(v, bool) and out and "name" in out[-1]:
            # A NUMBER WHERE "Scatter" BELONGS (2020 Hillsborough 16): the
            # record's header prints the write-ins' count in the label's place
            # and its row leaves the cell blank. Read as the Scatter column
            # with that count, flagged; only for a block of one town.
            out.append({"meta": "scatter", "col": c, "recount": None, "header_count": v,
                        "typo": (str(v), f"the Scatter column, with {v} as its count")})
            continue
        if not isinstance(v, str):
            raise Refused(f"{where}: {v!r} in column {c + 1}, where a candidate's name belongs")
        low = v.lower()
        if low == "recount":
            # A RECOUNT COLUMN BELONGS TO THE ONE BESIDE IT (17 October 2026),
            # as every one in the 2024 files does, and only to that one:
            # anywhere else it would be a guess which count it revises.
            if not out or out[-1]["recount"] is not None or out[-1]["col"] != c - 1:
                raise Refused(f"{where}: a RECOUNT column in column {c + 1} follows no count")
            out[-1]["recount"] = c
            continue
        if legacy and low == "blc":
            # A "BLC" COLUMN AFTER A RECOUNT COLUMN (2018 Belknap 3, 2022
            # Rockingham 6) is a later count of the same candidate, taken as the
            # Ballot Law Commission's, and is the one read; Block.apply_blc
            # decides, from the file's own Totals, whether its cells are whole
            # counts or changes to the recount's, and flags it (Block.notes).
            if not out or out[-1]["recount"] != c - 1 or out[-1].get("blc") is not None:
                raise Refused(f"{where}: a BLC column in column {c + 1} follows no recount")
            out[-1]["blc"] = c
            continue
        if low in (LEGACY_META if legacy else META):
            out.append({"meta": (LEGACY_META if legacy else META)[low], "col": c,
                        "recount": None})
            continue
        if legacy and low.isalpha() and len(low) >= 6 and edits(low, "scatter") <= 2:
            # "Scattrer", "Scattter": a word within two letters of Scatter and
            # no candidate (a candidate carries a party), flagged.
            out.append({"meta": "scatter", "col": c, "recount": None,
                        "typo": (v, "Scatter")})
            continue
        m = (LEGACY_WRITE_IN if legacy else WRITE_IN).match(v)
        if m:
            name = m.group("name") if legacy else (m.group("name") or m.group("after"))
            out.append({"name": name.strip(), "party": "",
                        "write_in": True, "col": c, "recount": None})
            continue
        m = CANDIDATE.match(v)
        flagged = None
        if not m and legacy:
            # A comma the record leaves out ("Richardson r", 2020 Carroll): a
            # surname and one party letter, flagged, read as "Richardson, r".
            m = LEGACY_NO_COMMA.match(v)
            flagged = (v, f"{m.group('name')}, {m.group('party')}") if m else None
            if not m and re.fullmatch(r"[^\W\d_][\w'’.\-]*,?", v):
                # A surname and no party at all (2018 Grafton 6, "Sanborn"):
                # a candidate whose party the record leaves out, drawn with none.
                out.append({"name": v.rstrip(","), "party": "", "write_in": False, "col": c,
                            "recount": None,
                            "typo": (v, f"the candidate {v.rstrip(',')!r}, whose party the file "
                                        "leaves out")})
                continue
        if not m:
            raise Refused(f"{where}: {v!r} in column {c + 1} is neither a candidate (\"Name, d\") "
                          "nor Undervotes, Overvotes or Write-Ins")
        party = "/".join(p.strip().lower() for p in re.split(r"[&/]", m.group("party")))
        name = m.group("name").strip()
        if legacy:
            # "Joseph, Jr., d" is the surname Joseph and a Jr.: no comma in a name.
            name = LEGACY_SUFFIX.sub(lambda m: " " + m.group(1), name)
        out.append({"name": name, "party": party, "write_in": False,
                    "col": c, "recount": None, **({"typo": flagged} if flagged else {})})
    if not any("name" in e for e in out):
        raise Refused(f"{where}: a header row that names no candidate")
    return out


def formulas(path):
    """{(sheet, row, column): "=SUM(B47:B48)"}: the formulas an .xlsx file
    keeps behind its cells (row 1-based, column 0-based, as the `where` of a
    row and Block.count's `col` say them); {} for an .xls, whose formulas
    xlrd does not give. Read only when a Totals row disagrees with its towns."""
    path = Path(path)
    key = str(path.resolve())
    if key not in _FORMULAS:
        out = {}
        if path.suffix.lower() == ".xlsx":
            import openpyxl
            book = openpyxl.load_workbook(path, read_only=True, data_only=False)
            try:
                for ws in book.worksheets:
                    for r, row in enumerate(ws.iter_rows(values_only=True), 1):
                        for c, v in enumerate(row):
                            if isinstance(v, str) and v.startswith("="):
                                out[(ws.title, r, c)] = v
            finally:
                book.close()
        _FORMULAS[key] = out
    return _FORMULAS[key]


_FORMULAS = {}
ROW_OF = re.compile(r"row (\d+)$")
SUM_RANGE = re.compile(r"^=SUM\(([A-Z]{1,3})(\d+):([A-Z]{1,3})(\d+)\)$")


def column_letter(col):
    """The spreadsheet's letters for a 0-based column: 0 A, 25 Z, 26 AA."""
    s, n = "", col + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class Block:
    """A header row and the rows under it, to the next header."""

    def __init__(self, ents, where, recount_figures=False, source=None, legacy=False):
        self.ents, self.where, self.rows, self.totals = ents, where, [], None
        self.recount_figures = recount_figures
        # The 2016-2022 layout: "--" and a blank Scatter cell are none, counted in blank_scatter.
        self.legacy, self.blank_scatter = legacy, 0
        # A "Recount" row under the block's one town (read_house).
        self.recount_row = None
        # {candidate: the Totals row's figure} where a candidate's towns do not
        # add up to it in the 2016-2022 layout (see read, and district).
        self.disputed = {}
        # (entity, 0 for the count or 1 for its recount) that a Totals row held.
        self.held = set()
        # (path, sheet name) of the file the block is read from, for its
        # formulas (short_sum); and what reading it flagged, for _notes.
        self.source = source
        self.notes = [f"{where}: the header prints {e['typo'][0]!r}, read as {e['typo'][1]}"
                      for e in ents if e.get("typo")]
        if any(e.get("blc") is not None for e in ents):
            self.notes.append(f"{where}: a column headed BLC follows the Recount column; it is "
                              "taken to be the Ballot Law Commission's count after the recount "
                              "(the file does not say what BLC stands for), and is the count "
                              "read here: see the note on how its cells were read")

    def short_sum(self, where, col, said, inside_of):
        """A note, or None. THE FILE'S TOTALS FORMULA LEAVES OUT A TOWN (5
        November 2026): the 2026 Grafton file's Totals for district 9 print
        Ella V. Barrett's as 1,152 from =SUM(B47:B48), leaving out Orange on
        row 49, while Bradley Macrae's are =SUM(C47:C49); her towns add up to
        1,240. Where a Totals cell is a SUM over its own column, its range
        holds only rows of this block's own towns, it leaves some out, and its
        printed figure is exactly the towns it does name, the towns are the
        count and the Totals are a typo in the official record: read, and
        flagged, as one is (the person's rule). Anything else is refused."""
        if self.source is None:
            return None
        path, sheet = self.source
        line = ROW_OF.search(where)
        f = formulas(path).get((sheet, int(line.group(1)), col)) if line else None
        m = SUM_RANGE.match(f or "")
        letter = column_letter(col)
        if not m or m.group(1) != letter or m.group(3) != letter:
            return None
        a, b = int(m.group(2)), int(m.group(4))
        lines = {}
        for town, _row, w in self.rows:
            n = ROW_OF.search(w)
            if not n:
                return None
            lines[int(n.group(1))] = town
        if a > b or any(r not in lines for r in range(a, b + 1)):
            return None
        named = [lines[r] for r in range(a, b + 1)]
        left = [t for r, t in sorted(lines.items()) if not a <= r <= b]
        if not left or sum(inside_of(t) or 0 for t in named) != said:
            return None
        return (f"{where}: the file's Totals cell is {f}, which leaves out "
                f"{', '.join(str(t) for t in left)}; read as the towns add up")

    def count(self, row, col, meta, where, ent=None):
        v = row[col] if col < len(row) else None
        if self.legacy and v is None and (ent or {}).get("header_count") is not None:
            v = ent["header_count"]
        if self.legacy:
            # "--" (2020 Senate) and "- ---" (2020 Coos) are a place no vote came from.
            if isinstance(v, str) and DASHES.fullmatch(v):
                v = 0
            elif v is None and (ent or {}).get("meta") == "scatter":
                # Blank is not nought here: a district's other block may
                # print it (2022 Hillsborough 27), and district() decides.
                self.blank_scatter += 1
            elif v is None and (ent or {}).get("write_in"):
                v = 0
        # "N/A" WHERE A COUNT THAT IS NOT A CANDIDATE'S BELONGS IS NONE
        # PRINTED (5 November 2026): the 2026 Hillsborough file's district 12
        # (Merrimack) prints "N/A" for its scattered write-ins, which is what
        # an empty cell there says. Flagged; a candidate's "N/A" is refused.
        if meta and isinstance(v, str) and v.strip().upper() == "N/A":
            self.notes.append(f"{where}: the file prints N/A in column {col + 1}, where a count "
                              "of undervotes, overvotes or write-ins belongs; read as none printed")
            v = None
        if v is None and meta:
            return None
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise Refused(f"{where}: {v!r} in column {col + 1}, where a count belongs")
        return v

    def read(self, single_town):
        """{town: {entity index: (count, recount)}}, each column held to the
        Totals row the file prints, where it prints one."""
        out = {}
        if len(self.rows) > 1 and any(e.get("header_count") is not None for e in self.ents):
            raise Refused(f"{self.where}: a count printed in a header, in a block of "
                          f"{len(self.rows)} towns: which town's it is is not in the file")
        for town, row, where in self.rows:
            if town is None:
                # A ROW WITH NO TOWN IS THE DISTRICT'S ONE TOWN (17 October
                # 2026), as under Hillsborough 9's second header in 2024;
                # where the district has more than one, which it is would be
                # a guess.
                if single_town is None:
                    raise Refused(f"{where}: a row of counts that names no town, in a district "
                                  "of more than one")
                town = single_town
            if town in out:
                raise Refused(f"{where}: {town} twice in one block")
            # A named write-in's cell may be empty, as a count that is not a
            # candidate's may (blank_ok); it is held to the Totals below.
            again = self.recount_row[0] if self.recount_row else row
            out[town] = {i: (self.count(row, e["col"], blank_ok(e), where, e),
                             None if e["recount"] is None
                             else self.count(again, e["recount"], blank_ok(e), where, e))
                         for i, e in enumerate(self.ents)}
        if not out:
            raise Refused(f"{self.where}: a header with no rows of counts under it")
        if self.totals is None:
            if len(out) > 1:
                raise Refused(f"{self.where}: {len(out)} towns and no Totals row to hold them to")
            self.write_ins_held(out)
            self.apply_blc(out)
            return out
        row, where = self.totals
        for i, e in enumerate(self.ents):
            for k, col in ((0, e["col"]), (1, e["recount"])):
                if col is None:
                    continue
                # A Totals row of the 2016-2022 layout leaves the write-ins' total
                # blank where it adds none up: nothing is said to hold them to.
                if self.legacy and blank_ok(e) and (col >= len(row) or row[col] is None):
                    continue
                kept = self.blank_scatter
                said = self.count(row, col, blank_ok(e), where, e)
                self.blank_scatter = kept
                if said is None:
                    continue
                # AN EMPTY CELL THE TOTALS ACCOUNT FOR IS NOUGHT (17 October
                # 2026). Senate 3's Madison prints no write-ins in 2024 and
                # the district's Totals say 19, which the other towns make
                # without it.
                self.held.add((i, k))
                got = sum(v[i][k] or 0 for v in out.values())
                if got != said:
                    who = f"{e.get('name') or e['meta']}'s {'recount ' if k else ''}column"
                    note = self.short_sum(where, col, said,
                                          lambda t, i=i, k=k: out[t][i][k] if t in out else None)
                    if note is None and self.legacy and e.get("meta") == "scatter":
                        # The write-ins nobody named are never drawn and only
                        # bound the unnamed-write-in check; a total that is
                        # not their sum is a typo in the record: said, and the
                        # towns' sum is the count (2022 Rockingham 32).
                        self.notes.append(f"{where}: the write-ins nobody named add up to "
                                          f"{got:,} by the towns and the file's Totals say "
                                          f"{said:,}; the towns' sum is read")
                        continue
                    if note is None and self.legacy and e.get("name") and not e.get("write_in"):
                        # A TOWNS' SUM THAT IS NOT THE PRINTED TOTAL (2018 Coos
                        # 7, 2016 and after): a typo in the record, which one of
                        # the two is the count is not in the file. The towns'
                        # sum is read and flagged, and district() refuses the
                        # race unless the same people win on the printed total.
                        if (k == 1) == (e["recount"] is not None):
                            self.disputed[e["name"]] = said
                        self.notes.append(f"{where}: {who} adds up to {got:,} by the towns and "
                                          f"the file's Totals say {said:,}; the towns' sum is "
                                          "read, and the winners are the same on either figure")
                        continue
                    if note is None:
                        raise Refused(f"{where}: {who} adds up to {got:,} and the file's Totals "
                                      f"say {said:,}")
                    self.notes.append(f"{note}: {who}, {got:,}, where the Totals say {said:,}")
        self.write_ins_held(out)
        self.apply_blc(out)
        return out

    def apply_blc(self, out):
        """Where a candidate's column is followed by a BLC column, the count
        read is the BLC's. Its cells are whole counts where the file's Totals
        say so (their sum is the printed total; 2022 Rockingham 6, one town,
        which prints no Totals: a cell of the size of the recount's) and
        changes to the recount's where the Totals do (the recount's total
        plus the cells is the printed total; 2018 Belknap 3, where one place
        prints -1 and the rest are blank). Anything else is refused."""
        for i, e in enumerate(self.ents):
            col = e.get("blc")
            if col is None:
                continue
            cells = {}
            for town, row, where in self.rows:
                v = row[col] if col < len(row) else None
                if isinstance(v, str) and DASHES.fullmatch(v):
                    v = 0
                if v is not None and (not isinstance(v, int) or isinstance(v, bool)):
                    raise Refused(f"{where}: {v!r} in the BLC column, where a count belongs")
                cells[town if town is not None else self.rows[0][0]] = v
            recount = {t: out[t][i][1] for t in out}
            said = None
            if self.totals is not None:
                said = self.totals[0][col] if col < len(self.totals[0]) else None
            full = all(v is not None for v in cells.values())
            if said is not None:
                if full and sum(cells.values()) == said:
                    mode = "whole"
                elif sum(recount.values()) + sum(v or 0 for v in cells.values()) == said:
                    mode = "change"
                else:
                    raise Refused(f"{self.where}: the BLC column's Totals, {said:,}, are neither "
                                  "its cells' sum nor the recount's total plus its cells")
            elif len(out) == 1 and full and list(recount.values())[0] is not None and \
                    list(cells.values())[0] * 2 >= list(recount.values())[0] > 0:
                mode = "whole"
            else:
                raise Refused(f"{self.where}: a BLC column that no Totals row and no size of "
                              "count says how to read")
            for t in out:
                n = (cells[t] if mode == "whole" else (recount[t] or 0) + (cells[t] or 0))
                out[t][i] = (out[t][i][0], n)
            self.notes.append(f"{self.where}: {e['name']}'s BLC cells are read as "
                              + ("whole counts" if mode == "whole" else
                                 "changes to the recount's counts, as the file's Totals say")
                              + ", and the BLC count is the one read")

    def write_ins_held(self, out):
        """A NAMED WRITE-IN'S EMPTY CELL IS NOUGHT WHERE THE TOTALS ACCOUNT
        FOR IT (5 November 2026), as an empty cell of scattered write-ins is:
        the 2026 Merrimack file's district 3 prints Desiree McLaughlin's
        write-in votes for Franklin Wards 2 and 3 (46 and 45) and nothing for
        Ward 1, and its Totals print 91. Where the block prints no Totals for
        that column, or it is the block's one town, an empty cell is no
        count, and refused. Changes `out` in place."""
        for i, e in enumerate(self.ents):
            if not e.get("write_in"):
                continue
            for k in (0, 1):
                empty = [t for t, v in out.items() if v[i][k] is None
                         and (k == 0 or e["recount"] is not None)]
                if not empty:
                    continue
                if (i, k) not in self.held:
                    raise Refused(f"{self.where}: {e['name']}'s {'recount ' if k else ''}count is "
                                  f"empty for {', '.join(map(str, empty))}, and no Totals row "
                                  "accounts for it")
                for t in empty:
                    v = list(out[t][i])
                    v[k] = 0
                    out[t][i] = tuple(v)
                self.notes.append(f"{self.where}: {e['name']}, written in, has an empty cell for "
                                  f"{', '.join(map(str, empty))}; read as none, as the file's "
                                  "Totals account for it")


def blank_ok(e):
    """Whether an entity's cell may be empty: a count that is not a
    candidate's, or a named write-in's (Block.write_ins_held)."""
    return "meta" in e or bool(e.get("write_in"))


# ---- a district, from its blocks -------------------------------------------

def district(blocks, seats, where):
    """{"towns", "candidates", "scatter", "recounted"} from a district's
    blocks: the first and any under it, and a whole recount's block, whose
    figures replace the first count's."""
    first = [b for b in blocks if not b.recount_figures]
    again = [b for b in blocks if b.recount_figures]
    if len(again) > 1:
        raise Refused(f"{where}: more than one block of recount figures")

    def counts(group):
        # `nought`: the towns whose empty cell of a count a Totals row
        # accounted for, which is then nought where no block prints it.
        cands, meta, towns, nought = {}, {}, None, {}
        recounted = False
        single = None
        for b in group:
            got = b.read(single)
            if towns is None:
                towns = list(got)
                single = towns[0] if len(towns) == 1 else None
            elif set(got) != set(towns):
                raise Refused(f"{b.where}: the towns {sorted(got)} under this header are not the "
                              f"district's {sorted(towns)}")
            for i, e in enumerate(b.ents):
                if e["recount"] is not None:
                    recounted = True
                if "meta" in e:
                    k = 1 if e["recount"] is not None else 0
                    if (i, k) in b.held:
                        nought.setdefault(e["meta"], set()).update(got)
                    for t, v in got.items():
                        n = v[i][k]
                        if n is None:
                            continue
                        old = meta.setdefault(e["meta"], {}).setdefault(t, n)
                        if old != n:
                            raise Refused(f"{b.where}: {t}'s {e['meta']} is {old} in one block "
                                          f"and {n} in another")
                    continue
                if e["name"] in cands:
                    raise Refused(f"{b.where}: {e['name']} twice in one district")
                votes = sum(v[i][1] if e["recount"] is not None else v[i][0]
                            for v in got.values())
                cands[e["name"]] = {"name": e["name"], "party": e["party"], "votes": votes,
                                    "write_in": e["write_in"]}
        scatter = meta.get("scatter") or {}
        for t in nought.get("scatter") or ():
            scatter.setdefault(t, 0)
        # In the 2016-2022 layout a blank cell in a Scatter column that some
        # place prints is none, so the sum is the places that print it.
        flat = any(b.legacy for b in group) and "scatter" in meta
        return (towns, list(cands.values()),
                sum(scatter.values()) if (set(scatter) == set(towns) or flat) else None,
                recounted)

    towns, cands, scatter, recounted = counts(first)
    if again:
        t2, c2, s2, _ = counts(again)
        if set(t2) != set(towns) or {c["name"] for c in c2} != {c["name"] for c in cands}:
            raise Refused(f"{again[0].where}: the recount's towns or candidates are not the "
                          "first count's")
        # A recount block that prints no write-ins (a Recount row, 2022) leaves
        # the first count's.
        cands, scatter, recounted = c2, (s2 if s2 is not None else scatter), True
    shown = elect(cands, seats, where, scatter)
    disputed = {}
    for b in (again or first):
        disputed.update(b.disputed)
    if disputed:
        # Either figure for a column the file contradicts, and the same people win.
        alt = elect([dict(c, votes=disputed.get(c["name"], c["votes"])) for c in cands], seats,
                    where, scatter)
        if [(c["name"], c["elected"]) for c in shown] != [(c["name"], c["elected"]) for c in alt]:
            raise Refused(f"{where}: a column adds up differently from the file's Totals "
                          f"({', '.join(sorted(disputed))}), and the two figures elect different "
                          "people")
    return {"towns": towns, "candidates": shown,
            "scatter": scatter, "recounted": recounted,
            "blank_scatter": sum(b.blank_scatter for b in blocks),
            "notes": [n for b in blocks for n in b.notes]}


def elect(cands, seats, where, scatter=None):
    """The candidates, each marked elected, not, or tied for the last seat
    (null): the files mark no winner, so the count decides. `scatter` is
    the write-ins the file counts and does not name, or None where it does
    not count them for every place."""
    if len(cands) < seats:
        raise Refused(f"{where}: {len(cands)} named candidate(s) for {seats} seat(s) -- a write-in "
                      "the file does not name may have won, and this does not guess who")
    by = sorted((c["votes"] for c in cands), reverse=True)
    cut = by[seats - 1]
    if cut == 0:
        raise Refused(f"{where}: a seat whose winner has no votes")
    # A WRITE-IN WINNER THE FILE DOES NOT NAME IS REFUSED, NOT GUESSED (the
    # person's decision of 17 October 2026). The scattered write-ins are one
    # count for many names, so where it reaches the last seat's votes one of
    # those names may hold the seat, and which is not in the file. In 2024
    # the most it came to was 128 against 3,389 (Rockingham 4).
    if scatter is not None and scatter >= cut:
        raise Refused(f"{where}: the write-ins the file does not name come to {scatter:,}, and the "
                      f"last seat was won with {cut:,} -- one of them may have won, and this does "
                      "not guess who")
    above = sum(1 for v in by if v > cut)
    at = sum(1 for v in by if v == cut)
    tie = above + at > seats
    return [dict(c, elected=(True if c["votes"] > cut or (c["votes"] == cut and not tie)
                             else None if c["votes"] == cut else False)) for c in cands]


# ---- the files ---------------------------------------------------------------

def blank(row):
    return all(v is None for v in row)


def is_totals(head):
    """Whether a row's first cell is the Totals label: "TOTALS", or with a
    word in brackets after it ("TOTALS (tie)", 2016 Cheshire 12)."""
    return isinstance(head, str) and bool(re.fullmatch(r"totals(?:\s*\(.*\))?", head.lower()))


def starless(town):
    """A town's name without the star the 2016-2022 files put on a place whose
    count a clerk corrected ("Stratham*"; the footnote says so, footnote())."""
    return town.rstrip("*").strip() if isinstance(town, str) else town


def footnote(block, text, where, width):
    """A one-cell row beginning with a star is the file's footnote to a
    starred place: said in the block's notes, and read as nothing else."""
    if width != 1:
        raise Refused(f"{where}: {text!r}, a starred row that is not a footnote of one cell")
    block.notes.append(f"{where}: the file's footnote {text!r} belongs to the place it stars; "
                       "its figures are those the file prints")


def read_house(path, county, election, legacy=False):
    """{district number: (seats, floterial, district record)} from one
    county's House file. `legacy` is the 2016-2022 layout (LEGACY_META): no
    day in the file, a surname for a name, "Scatter" for the write-ins."""
    got = sheets(path)
    if legacy and path.suffix.lower() == ".html":
        # A results page: its tables are one county's rows, cut in two.
        got = [("the page's tables", [r for _n, rs in got for r in rs])]
    spare = []
    if legacy and len(got) > 1 and path.suffix.lower() != ".html":
        # A SHEET AFTER THE COUNTY'S (2020 Rockingham's "dist 2") is a
        # scratch table of one district whose candidates are not those the
        # county's sheet counts for it: not read, and said.
        spare = [n for n, _r in got[1:]]
        got = got[:1]
    if len(got) != 1:
        raise Refused(f"{path.name}: {len(got)} sheets where a county's House file has one")
    name, rows = got[0]

    def at(i):
        return f"{path.name}, sheet {name!r}, row {i + 1}"
    title = " ".join(str(c) for c in (rows[0] if rows else []) if c)
    # The 2016 files print no year in the title: the file's name says it then.
    years = re.findall(r"\b(?:19|20)\d\d\b", title)
    if "general election" not in title.lower() or (
            years != [str(election.year)] if (years or not legacy) else False):
        raise Refused(f"{at(0)}: {title!r} is not the title of the {election.year} general "
                      "election")
    # The 2016-2022 files sometimes shift the title one column right.
    second = next((c for c in (rows[1] if len(rows) > 1 else [])[:2 if legacy else 1] if c), "")
    m = REP_TITLE.match(str(second))
    if not m or m.group(1).lower() != county:
        raise Refused(f"{at(1)}: {rows[1][:1] if len(rows) > 1 else []!r} is not \"State "
                      f"Representatives - {county.upper()} County\"")
    if not legacy:
        day = as_day((rows[2] if len(rows) > 2 else [None])[0])
        if day != election:
            raise Refused(f"{at(2)}: the file's day is {day}, not the election of {election}")
    found, cur = {}, None
    for i in range(2 if legacy else 3, len(rows)):
        row = rows[i]
        while row and row[-1] is None:
            row = row[:-1]
        if blank(row):
            continue
        head = row[0]
        typo = HEADER_TYPOS.get((path.name, head)) if isinstance(head, str) else None
        if not typo and legacy and isinstance(head, str) and not DISTRICT.match(head):
            # "Distict No. 3 (2)": the first word one letter off "District".
            first = re.match(r"[A-Za-z]+", head)
            if first and first.group().lower() != "district" and \
                    edits(first.group().lower(), "district") == 1:
                fixed = "District" + head[first.end():]
                if DISTRICT.match(fixed):
                    typo = (fixed, "the first word is one letter off District")
        if not typo and legacy and isinstance(head, str):
            # "Dover Ward 15 (1)" for "District No. 15 (1)" (2020 Strafford):
            # a ward's name where the district's belongs, with seats after it.
            ward = re.match(r"^[A-Za-z ]+ Ward (\d+)\s*(\(\d+\)\s*(?:FL|F)?)$", head)
            if ward:
                typo = (f"District No. {ward.group(1)} {ward.group(2)}",
                        "a ward's name stands where District No. belongs, before the seats")
        if typo:
            head = typo[0]
        label = ROW_LABELS.get((path.name, i + 1)) if head is None and cur is not None else None
        if label:
            head = label
            cur[2][-1].notes.append(f"{at(i)}: the row names no town; it is read as {label!r}, "
                                    f"which the file's own rows say: {ROW_LABELS_WHY}")
        bare = DISTRICT_BARE.match(head) if legacy and isinstance(head, str) else None
        if bare:
            # A DISTRICT'S LATER HEADER WITH NO SEATS (2020: "District No. 2"
            # again under "District No. 2 (4)"): the same district's next
            # block of candidates, as a header with no label is. Alone in its
            # row, it only titles the names row that follows. A first header
            # that prints no seats cannot be settled without a table of the
            # districts, which is the one thing these years lack: refused.
            n = int(bare.group(1))
            if n not in found:
                raise Refused(f"{at(i)}: {head!r}, the first header of the district, prints no "
                              "seats, and no table of the districts of this year says how many")
            cur = found[n]
            if len(row) == 1:
                continue
            head = None
        m = DISTRICT.match(head) if isinstance(head, str) else None
        if m:
            n, seats = int(m.group(1)), int(m.group(2))
            flo, again = bool(m.group(3)), bool(m.group(4))
            # THE FULL HEADER AGAIN (2016, 2018): a district too wide for one
            # row prints its header again, with the same seats, over the next
            # candidates. It is the district's next block, not a second district.
            if legacy and not again and n in found and (seats, flo) == found[n][:2]:
                cur = found[n]
                cur[2].append(Block(entities(row, 1, at(i), legacy), at(i), source=(path, name),
                                    legacy=legacy))
                continue
            if again != (n in found):
                raise Refused(f"{at(i)}: district {n} " + ("recounted before it is counted"
                                                           if again else "twice"))
            if not again:
                found[n] = (seats, flo, [], at(i))
            elif (seats, flo) != found[n][:2]:
                raise Refused(f"{at(i)}: the recount's seats or floterial mark are not the "
                              "first count's")
            cur = found[n]
            cur[2].append(Block(entities(row, 1, at(i), legacy), at(i), recount_figures=again,
                                source=(path, name), legacy=legacy))
            if typo:
                cur[2][-1].notes.append(f"{at(i)}: the header prints {row[0]!r}, read as "
                                        f"{typo[0]!r}: {typo[1]}")
            continue
        if cur is None:
            raise Refused(f"{at(i)}: {row!r} before any district's header")
        # In the 2016-2022 layout the second header may carry a town's name in
        # its first cell (2022 Rockingham 16, Londonderry): a row of names, not
        # of counts, whatever its first cell says.
        if (head is None or (legacy and isinstance(head, str) and not is_totals(head))) \
                and any(isinstance(v, str) and not DASHES.fullmatch(v) for v in row[1:]):
            # THE COUNTS THAT ARE NOT A CANDIDATE'S KEEP THEIR COLUMNS (17
            # October 2026) under a second header that does not name them
            # again: in 2024 Rockingham 17's Windham prints its undervotes,
            # overvotes and write-ins on the row under the second header, in
            # the columns the first header named.
            ents = entities(row, 1, at(i), legacy)
            taken = {c for e in ents for c in (e["col"], e["recount"]) if c is not None}
            named = {e["meta"] for e in ents if "meta" in e}
            ents += [dict(e) for e in cur[2][0].ents if "meta" in e and e["meta"] not in named
                     and not {e["col"], e["recount"]} & taken]
            cur[2].append(Block(ents, at(i), recount_figures=cur[2][-1].recount_figures,
                                source=(path, name), legacy=legacy))
            continue
        if legacy and isinstance(head, str) and head.lower() in ("recount",
                                                                  "court ordered recount"):
            # A ROW LABELLED "Recount" UNDER A BLOCK OF ONE TOWN (2022 Coos 5,
            # Hillsborough 29) holds that town's recounted figures, in the
            # columns of the candidates above it. Under more towns it would
            # be a guess which they are, and is refused.
            # A "Court ordered recount" row after a Recount row (2022 Hillsborough
            # 16) is the later count, and is read; the earlier is said.
            blk = cur[2][-1]
            court = head.lower().startswith("court")
            if len(blk.rows) != 1 or blk.totals is not None or (
                    blk.recount_row is not None and not court):
                raise Refused(f"{at(i)}: a Recount row under {len(blk.rows)} towns, or a "
                              "second one, or after Totals")
            if blk.recount_row is not None:
                blk.notes.append(f"{at(i)}: a court-ordered recount, which is read in place of "
                                 f"the recount at {blk.recount_row[1]}")
            blk.recount_row = (row, at(i))
            for e in blk.ents:
                if "name" in e:
                    e["recount"] = e["col"]
            continue
        if isinstance(head, str) and is_totals(head):
            if cur[2][-1].totals is not None:
                raise Refused(f"{at(i)}: a second Totals row under one header")
            cur[2][-1].totals = (row, at(i))
            continue
        if legacy and isinstance(head, str) and head.startswith("*"):
            footnote(cur[2][-1], head, at(i), len(row))
            continue
        if legacy and head is None:
            # A STRAY COUNT WITH NO TOWN, in no candidate's column (2020
            # Strafford 23: a lone 6 below the Totals; 2016 Rockingham 12: a
            # lone 4 under the one town): said, and not read. A candidate's
            # column is never passed over; and where there are Totals they
            # hold the district's columns to its towns.
            cand_cols = {e["col"] for e in cur[2][-1].ents if "name" in e}
            cand_cols |= {e["recount"] for e in cur[2][-1].ents if e.get("recount") is not None}
            if all(v is None or c not in cand_cols for c, v in enumerate(row)):
                cur[2][-1].notes.append(f"{at(i)}: a count with no town, in no candidate's "
                                        f"column ({[v for v in row if v is not None]}); "
                                        "not read")
                continue
        if head is not None and not isinstance(head, str):
            raise Refused(f"{at(i)}: {head!r} where a town's name belongs")
        if cur[2][-1].totals is not None:
            raise Refused(f"{at(i)}: a row of counts after the Totals")
        cur[2][-1].rows.append((starless(head) if legacy else head, row, at(i)))
    if not found:
        raise Refused(f"{path.name}: no district in it")
    if spare:
        first = found[min(found)][2][0]
        first.notes.append(f"{path.name}: the sheet(s) {', '.join(map(repr, spare))} after the "
                           "county's are not read: a scratch table whose candidates are not those "
                           "the county's sheet counts for the district")
    return {n: (seats, flo, district(blocks, seats, where))
            for n, (seats, flo, blocks, where) in found.items()}


def read_senate(path, election, legacy=False):
    """{district number: district record} from the Senate file. `legacy` is
    the 2018-2022 layout: the district's title may share its row with the
    election's day (2018), or the header row may begin with the day (2020,
    2022) or with nothing; the counts are read as LEGACY_META says."""
    found, cur = {}, None
    for name, rows in sheets(path):
        cur = None
        for i, row in enumerate(rows):
            where = f"{path.name}, sheet {name!r}, row {i + 1}"
            while row and row[-1] is None:
                row = row[:-1]
            if blank(row):
                continue
            head = row[0]
            m, titled_day = None, []
            if legacy:
                for c in row:
                    if isinstance(c, str) and SENATE.match(c):
                        m = SENATE.match(c)
                        titled_day = [d for d in row if isinstance(d, datetime.date)]
                        break
            elif isinstance(head, str):
                m = SENATE.match(head)
            if m:
                n = int(m.group(1))
                if n in found:
                    raise Refused(f"{where}: Senate district {n} twice")
                if titled_day and titled_day[0] != election:
                    raise Refused(f"{where}: the title's day is {titled_day[0]}, not the "
                                  f"election of {election}")
                cur = found[n] = {"n": n, "where": where, "blocks": []}
                continue
            if isinstance(head, str) and len(row) == 1 and (
                    "general election" in head.lower()
                    or (legacy and head.lower() == "state of new hampshire")):
                continue
            if legacy and len(row) == 2 and row[0] is None and row[1] == "State of New Hampshire":
                continue
            if cur is None:
                raise Refused(f"{where}: {row!r} before any district's title")
            if not cur["blocks"]:
                # A later district's header row begins with nothing in the
                # 2020 and 2022 layouts: the day was read at the first.
                said = None
                if not (legacy and (head is None or head == election)):
                    day = as_day(head)
                    # A day mistyped in the record ("11/63/20", 2020 Senate 22): its
                    # month and year are the election's, its day is no day; said.
                    if day is None and legacy and isinstance(head, str) and re.fullmatch(
                            r"11/\d\d/" + str(election.year)[2:], head):
                        said = (f"{where}: the header's day is printed {head!r}, which is no "
                                f"day; its month and year are the election's, {election}")
                    elif day != election:
                        raise Refused(f"{where}: the header's day is {head!r}, not the election "
                                      f"of {election}")
                cur["blocks"].append(Block(entities(row, 1, where, legacy), where,
                                           source=(path, name), legacy=legacy))
                if said:
                    cur["blocks"][-1].notes.append(said)
                continue
            b = cur["blocks"][-1]
            if isinstance(head, str) and is_totals(head):
                if b.totals is not None:
                    raise Refused(f"{where}: a second Totals row")
                b.totals = (row, where)
                continue
            if legacy and isinstance(head, str) and head.startswith("*"):
                footnote(b, head, where, len(row))
                continue
            if not isinstance(head, str):
                raise Refused(f"{where}: {head!r} where a town's name belongs")
            if b.totals is not None:
                raise Refused(f"{where}: a row of counts after the Totals")
            b.rows.append((starless(head) if legacy else head, row, where))
    if not found:
        raise Refused(f"{path.name}: no Senate district in it")
    for n, d in found.items():
        if not d["blocks"]:
            raise Refused(f"{d['where']}: Senate district {n} has no header row")
    return {n: district(d["blocks"], 1, d["where"]) for n, d in found.items()}


def upload_number(p):
    """Where a saved file stands among the Secretary of State's uploads of
    one name: none (-1) before "_0", "_0" before "_1", and so on."""
    m = re.search(r"_(\d+)\.xlsx?$", p.name)
    return int(m.group(1)) if m else -1


def latest(files, what, replaced):
    """The one of `files` the Secretary of State uploaded last, by the
    number on its name; each earlier one is added to `replaced` as (the
    earlier, the later).

    A RECOUNT'S RE-DOWNLOAD REPLACES THE COUNTY'S FILE (the person's
    decision of 17 October 2026). The number on a saved file's name rises
    with each upload of that name -- the 2024 Hillsborough file, which
    carries four recounts, is "_7" -- so a recount's figures saved beside
    the first count are, by that sign and not by anything the Secretary of
    State has said, the higher number; and the later is the results. Until
    then two files of one county stopped the reader. Two under the same
    number are still refused: which is the later is then not in their
    names."""
    files = sorted(files, key=lambda p: (upload_number(p), p.name))
    if len(files) > 1 and upload_number(files[-1]) == upload_number(files[-2]):
        raise Refused(f"{files[-2].name} and {files[-1].name} are both {what}, under one number: "
                      "which the Secretary of State published later is not in their names; keep "
                      "the one saved last")
    replaced.extend((old, files[-1]) for old in files[:-1])
    return files[-1]


def senate_span(name):
    """(first, last): the Senate districts a file's name says it holds --
    (1, 24) for 2024's -district-1-24, (5, 5) for -5, (14, 16) for -14-16;
    None for a name that is no Senate file."""
    m = SENATE_FILE.match(name)
    if not m:
        return None
    a, b = (m.group(2), m.group(3)) if m.group(2) else (m.group(4), m.group(5) or m.group(4))
    return int(a), int(b)


def senate_parts(paths):
    """{(first, last): [paths, by upload]}: the Senate files grouped by the
    districts their names say they hold, so that a recount's later upload of
    one part (_N) replaces that part alone."""
    out = {}
    for p in paths:
        out.setdefault(senate_span(p.name), []).append(p)
    return {k: sorted(v, key=lambda p: (upload_number(p), p.name)) for k, v in sorted(out.items())}


def senate_unheld(spans, n=SENATE_DISTRICTS):
    """(missing, overlaps): the districts 1..n no span holds, and each
    district two spans hold, as [(district, [span, span, ...])]."""
    holders = {}
    for a, b in spans:
        for d in range(a, b + 1):
            holders.setdefault(d, []).append((a, b))
    missing = [d for d in range(1, n + 1) if d not in holders]
    overlaps = [(d, hs) for d, hs in sorted(holders.items()) if len(hs) > 1]
    return missing, overlaps


def span_words(span):
    a, b = span
    return f"district {a}" if a == b else f"districts {a} to {b}"


def senate_merged(read):
    """{district: record} from [(file name, {district: record}), ...], each a
    Senate file as read_senate read it. A file must hold exactly the districts
    its name says, and no district may come from two files: anything else is
    refused, not merged."""
    out, came = {}, {}
    for name, got in read:
        a, b = senate_span(name)
        want = list(range(a, b + 1))
        if sorted(got) != want:
            raise Refused(f"{name} holds Senate district(s) {', '.join(map(str, sorted(got)))}; "
                          f"its name says {span_words((a, b))}")
        for d, rec in got.items():
            if d in out:
                raise Refused(f"Senate district {d} is in both {came[d]} and {name}")
            out[d], came[d] = rec, name
    return out


def source_files(root, year, partial=False):
    """{"house": {county: path}, "senate": [paths, by district], "replaced":
    [(earlier, later), ...], "missing": [county, ...], "senate_missing":
    bool}: the year's saved files, each county's latest once and each Senate
    part's latest once. A county or the whole Senate with no file is refused,
    unless `partial` (2016, whose Strafford House file and State Senate files
    the Secretary of State's site no longer serves): then it is returned, to
    be said in the results file's notes, and filled from nowhere."""
    d = Path(root) / SOURCES
    house, senate, replaced = {}, [], []
    for p in sorted(d.glob(f"{year}-*")) if d.is_dir() else []:
        m = HOUSE_FILE.match(p.name)
        if m and m.group(1) == str(year):
            if m.group(2) not in COUNTIES:
                raise Refused(f"{p.name} names no county of New Hampshire")
            house.setdefault(m.group(2), []).append(p)
        elif SENATE_FILE.match(p.name):
            senate.append(p)
    missing = [c for c in COUNTIES if c not in house]
    if missing and not partial:
        raise Refused(f"no {year} House results saved in {d.as_posix()}/ for "
                      + ", ".join(missing))
    if not senate and not partial:
        raise Refused(f"no {year} State Senate file in {d.as_posix()}/")
    parts = senate_parts(senate)
    beyond = [p[-1].name for s, p in parts.items() if s[0] < 1 or s[0] > s[1]
              or s[1] > SENATE_DISTRICTS]
    if beyond:
        raise Refused(f"{', '.join(beyond)}: a Senate file named for districts outside 1 to "
                      f"{SENATE_DISTRICTS}, or backwards")
    gaps, overlaps = senate_unheld(parts)
    if overlaps:
        d0, spans = overlaps[0]
        raise Refused(f"Senate district {d0} is named by more than one saved file -- "
                      + "; ".join(p.name for s in spans for p in parts[s][-1:])
                      + " -- so which to read is not in their names; keep one way of saving the "
                      "Senate, whole or in parts")
    if gaps and senate:
        raise Refused(f"no saved {year} State Senate file holds district(s) "
                      + ", ".join(map(str, gaps)))
    return {"missing": missing, "senate_missing": not senate, "house": {c: latest(ps, f"{c}'s House results", replaced) for c, ps in house.items()},
            "senate": [latest(ps, f"the State Senate results for {span_words(s)}", replaced)
                       for s, ps in parts.items()],
            "replaced": replaced}


def described(p, root, saved=None, url=None, registry=None):
    """A _source entry: the file, as a path from the project's root, the
    address of the Secretary of State's results page it was saved from
    (--url; None where not given), its sha256, and the day it was saved --
    its modification day, unless stated."""
    data = p.read_bytes()
    day = saved or datetime.date.fromtimestamp(p.stat().st_mtime).isoformat()
    out = {"file": p.relative_to(root).as_posix(), "url": url, "saved": day,
           "sha256": hashlib.sha256(data).hexdigest()}
    # THE REGISTRY OF DOWNLOADS (10 November 2026) names each file's address,
    # the results page it was on and the day it was saved, and its sha256 is
    # held to the file's: a file that is not the one registered is refused.
    if registry is not None:
        entry = registry.get(out["file"])
        if entry is None:
            raise Refused(f"{out['file']} is in no entry of the registry of downloads")
        if entry.get("sha256") != out["sha256"]:
            raise Refused(f"{out['file']} is not the file the registry of downloads names: its "
                          f"sha256 is {out['sha256']}, the registry's {entry.get('sha256')}")
        out.update(url=entry.get("page"), saved=entry.get("saved") or day,
                   file_url=entry.get("url"))
    return out


# ---- the whole election -------------------------------------------------------

def read_all(root, year, districts, saved=None, url=None, partial=False, registry=None):
    """The results document for `year`, from the saved files under `root`
    and the district table `districts` (site/districts.json's contents),
    each file's _source naming `url`, the results page it was saved from.
    Refused on anything it does not recognise.

    `districts` None is a year whose districts are not the table's: New
    Hampshire redistricted for 2022, and the table on this machine is the
    2022 one, so 2016, 2018 and 2020 (the 2012 districts) are held to none --
    the 2012 table is on no disk here, and one is not made up. Each race is
    then what its file lists, its towns as the file spells them, its seats
    from its header and its floterial from its towns, and the file says so
    in its notes. `partial` lets a county or the Senate have no file, said in
    the notes. `registry` is the list of where each file came from
    (reports/sos-downloads-*.json), which gives each _source its address and
    day and is held to the file's sha256."""
    root = Path(root).resolve()
    election = BME.general_election(year)
    legacy = year <= LEGACY_UNTIL
    files = source_files(root, year, partial)
    held = districts is not None
    on_file, clash = BME.races_on_file(districts) if held else ({}, [])
    if clash:
        raise Refused("the district table names districts that are no race: "
                      + "; ".join(clash[:4]))
    places = {}
    for r in on_file.values():
        for t in r["towns"]:
            k = place_key(t)
            if places.setdefault(k, t) != t:
                raise Refused(f"the district table names {places[k]!r} and {t!r}, which read as "
                              "one place")
    races, blanks, noscatter = {}, Counter(), defaultdict(list)
    notes = [f"{new.name} is read, and replaces {old.name}: the Secretary of State's later upload "
             "of the same results, as after a recount" for old, new in files["replaced"]]
    if not held:
        notes.append(f"The districts of {year} are the 2012 districts, and no table of them is on "
                     "this machine, so no race here is held to a district table: each is what its "
                     "file lists, its towns as the file spells them, its seats from its header, "
                     "and whether it floats from its towns.")
    if files["missing"]:
        notes.append("Not on file: " + ", ".join(c.title() for c in files["missing"])
                     + " County's State Representative results (the Secretary of State's site no "
                     "longer serves the file), so the races of "
                     + ("that county are" if len(files["missing"]) == 1 else "those counties are")
                     + " not here and are filled from no other source.")
    if files["senate_missing"]:
        notes.append("Not on file: the State Senate results (the Secretary of State's site no "
                     "longer serves the files), so no State Senate race is here and none is filled "
                     "from another source.")

    def settle(key, rec, seats, flo, where):
        blanks[where.split(",")[0]] += rec.get("blank_scatter") or 0
        if not held:
            races[key] = {"seats": seats, "floterial": False, "towns": sorted(rec["towns"]),
                          "candidates": rec["candidates"], "scatter": rec["scatter"]}
            if rec["recounted"]:
                races[key]["recounted"] = True
            if legacy and key.startswith("H|"):
                races[key]["surnames"] = True
            notes.extend(rec.get("notes") or [])
            return
        if key not in on_file:
            raise Refused(f"{where}: {key} is no district in the district table")
        t = on_file[key]
        if seats != t["seats"]:
            raise Refused(f"{where}: {seats} seat(s); the district table says {t['seats']}")
        towns, unknown = [], []
        for town in rec["towns"]:
            p = places.get(place_key(town))
            (towns if p else unknown).append(p or town)
        # ONE MISSPELT PLACE IS READ, AND FLAGGED, WHERE IT CAN BE NOTHING ELSE
        # (17 October 2026). The 2024 Rockingham file names district 10's
        # towns "Newfield" and Newmarket; the table's are Newfields and
        # Newmarket, and the same file spells Newfields right under district
        # 33. A name the table does not hold is taken as the table's only
        # when it is the one place of the district left unmatched and is
        # within two letters of it. Anything more is refused.
        left = sorted(set(t["towns"]) - set(towns))
        if len(unknown) == 1 and len(left) == 1 and one_place(unknown[0], left[0]):
            notes.append(f"{where}: the file names {unknown[0]!r}, read as {left[0]}, the one "
                         f"place of {key} it names no other way")
            towns.append(left[0])
        elif unknown:
            raise Refused(f"{where}: {', '.join(map(repr, unknown))} "
                          + ("is no place" if len(unknown) == 1 else "are no places")
                          + " the district table names")
        if sorted(towns) != sorted(t["towns"]):
            raise Refused(f"{where}: {key}'s towns are {', '.join(sorted(towns))} here and "
                          f"{', '.join(sorted(t['towns']))} in the district table")
        notes.extend(rec.get("notes") or [])
        race = {"seats": seats, "floterial": t["floterial"], "towns": sorted(towns),
                "candidates": rec["candidates"], "scatter": rec["scatter"]}
        if rec["recounted"]:
            race["recounted"] = True
        # The House files of 2016-2022 print a surname for each candidate: the
        # race says so, and members_elect matches them by the seat held.
        if legacy and key.startswith("H|"):
            race["surnames"] = True
        # WHERE THE FILE COUNTS NO SCATTERED WRITE-INS, THAT IS SAID (17
        # October 2026): elect() could not hold them to the last seat, and
        # silence is not success. In 2024, Hillsborough 12's one town prints
        # none.
        if rec["scatter"] is None:
            if legacy:
                noscatter[where.split(",")[0]].append(key)
            else:
                notes.append(f"{where}: the file counts no scattered write-ins for every place, "
                             "so whether a write-in it does not name won could not be checked")
        races[key] = race

    for county, path in files["house"].items():
        got = read_house(path, county, election, legacy)
        for n, (seats, flo, rec) in got.items():
            settle(f"H|{county.title()}|{n}", rec, seats, flo, f"{path.name}, district {n}")
        # WHICH DISTRICTS FLOAT IS READ FROM THE FILE'S OWN TOWNS, and held to
        # the table (17 October 2026). The printed mark is wrong four times
        # in 2024: Cheshire 14 (Rindge alone) and Grafton 16 (Enfield alone)
        # are marked "FL", and Hillsborough 44 (Goffstown and Weare) and
        # Strafford 18 are not, though each of those two is exactly the towns
        # of districts beneath it. A floterial is a district whose towns are
        # the towns of the other districts that lie inside it, and that is a
        # fact of the file's own rows. Where it and the table disagree the
        # file is refused; where only the printed mark does, the mark is
        # flagged in the file for the review, as a typo in the official record
        # is (the person's rule), and decides nothing.
        towns = {n: set(races[f"H|{county.title()}|{n}"]["towns"]) for n in got}
        for n, (seats, flo, rec) in got.items():
            key, where = f"H|{county.title()}|{n}", f"{path.name}, district {n}"
            inside = [towns[m] for m in towns if m != n and towns[m] <= towns[n]]
            floats = bool(inside) and set().union(*inside) == towns[n]
            if not held:
                races[key]["floterial"] = floats
            elif floats != races[key]["floterial"]:
                raise Refused(f"{where}: its towns make it " + ("a floterial" if floats else
                                                                "a base district")
                              + "; the district table says otherwise")
            if flo != floats:
                notes.append(f"{where}: the file " + ("marks it floterial" if flo else
                                                      "does not mark it floterial")
                             + ("; by its towns it is " if not held else
                                "; by its towns, and in the district table, it is ")
                             + ("floterial" if floats else "a base district"))
    table_senate = sorted(int(k[2:]) for k in on_file if k.startswith("S|"))
    if held and table_senate != list(range(1, SENATE_DISTRICTS + 1)):
        raise Refused(f"the district table names Senate districts {table_senate[:3]} ... "
                      f"{table_senate[-3:]}, not 1 to {SENATE_DISTRICTS}: SENATE_DISTRICTS is code")
    read = [(p.name, read_senate(p, election, legacy)) for p in files["senate"]]
    came = {d: name for name, got in read for d in got}
    for n, rec in senate_merged(read).items():
        settle(f"S|{n}", rec, 1, False, f"{came[n]}, district {n}")
    missing = sorted(set(on_file) - set(races), key=BME.race_order)
    if missing:
        raise Refused("the district table names races no file holds: " + ", ".join(missing[:8])
                      + (" ..." if len(missing) > 8 else ""))
    for name, keys in sorted(noscatter.items()):
        notes.append(f"{name}: no scattered write-ins are counted in {len(keys)} race(s) "
                     f"({', '.join(keys[:6])}{' ...' if len(keys) > 6 else ''}), so whether a "
                     "write-in it does not name won could not be checked there")
    for name, n in sorted(blanks.items()):
        if n:
            notes.append(f"{name}: {n} blank cell(s) in a Scatter column, which this layout "
                         "leaves blank for none, read as none")
    sources = [described(p, root, saved, url, registry) for p in
               [*(files["house"][c] for c in COUNTIES if c in files["house"]), *files["senate"]]]
    doc = {"_about": [
                "What the Secretary of State's results files say of the State Representative and "
                "State Senate races, read by src/parse/parse_sos_results.py from the files named "
                "in _source and held to the district table"
                + (" (none, for the districts of 2012: see _notes)" if not held else "")
                + ". Nothing in it is this project's "
                "decision but the winners, which the files do not mark: the candidates with the "
                "most votes, as many as the race has seats; a tie for the last seat is null.",
                "Write the file again by running the reader, never by hand: --check says where "
                "the saved files and this disagree."],
            "_source": sources,
            "election": election.isoformat(), "term": BME.term_after(year),
            "races": {k: races[k] for k in sorted(races, key=BME.race_order)}}
    if notes:
        doc["_notes"] = notes
    if files["missing"] or files["senate_missing"]:
        # What the Secretary of State's site no longer serves, said where the
        # pages can say it: the counties with no House file, and the Senate.
        doc["_not_on_file"] = {"counties": [c.title() for c in files["missing"]],
                               "senate": bool(files["senate_missing"])}
    return doc


def dumps(doc):
    """The document as one race to a line or few, so that a recount's diff
    is the race it moved and no more."""
    out = ["{"]
    out.append(' "_about": ' + json.dumps(doc["_about"], ensure_ascii=False, indent=2)
               .replace("\n", "\n ") + ",")
    if doc.get("_notes"):
        out.append(' "_notes": ' + json.dumps(doc["_notes"], ensure_ascii=False, indent=2)
                   .replace("\n", "\n ") + ",")
    if doc.get("_not_on_file"):
        out.append(' "_not_on_file": ' + json.dumps(doc["_not_on_file"], ensure_ascii=False) + ",")
    out.append(' "_source": [')
    out.append(",\n".join("  " + json.dumps(s, ensure_ascii=False) for s in doc["_source"]))
    out.append(" ],")
    out.append(f' "election": {json.dumps(doc["election"])},')
    out.append(f' "term": {json.dumps(doc["term"])},')
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


def differences(now, committed):
    """Where what the files say now and the committed document part, the
    days the files were saved aside: a checkout does not keep a file's
    modification day, so that is the one thing the files cannot say again."""
    def plain(d):
        d = json.loads(json.dumps(d))
        for s in d.get("_source") or []:
            s.pop("saved", None)
        return d
    a, b = plain(now), plain(committed)
    out = []
    for k in ("_notes", "_not_on_file", "_source", "election", "term"):
        if a.get(k) != b.get(k):
            out.append(f"{k}: the files say {json.dumps(a.get(k))[:200]}, the committed file "
                       f"{json.dumps(b.get(k))[:200]}")
    ra, rb = a.get("races") or {}, b.get("races") or {}
    for k in sorted(set(ra) | set(rb), key=lambda k: BME.race_order(k) if BME.KEY_RE.match(k)
                    else (2, k, 0)):
        if ra.get(k) != rb.get(k):
            out.append(f"{k}: " + ("not in the committed file" if k not in rb else
                                   "not in the files" if k not in ra else
                                   "the files and the committed file differ"))
    return out


def summary(doc):
    races = doc["races"].values()
    cands = [c for r in races for c in r["candidates"]]
    won = Counter(str(c["elected"]) for c in cands)
    recounted = [k for k, r in doc["races"].items() if r.get("recounted")]
    tied = [k for k, r in doc["races"].items() if any(c["elected"] is None
                                                      for c in r["candidates"])]
    house = [k for k in doc["races"] if k.startswith("H|")]
    # A Totals cell read past (Block.short_sum) is said here, not hidden
    # behind "every column agrees".
    short = sum(1 for n in doc.get("_notes") or [] if "the file's Totals cell is" in n)
    return (f"{len(doc['_source'])} files; {len(house)} House races and "
            f"{len(doc['races']) - len(house)} Senate, {sum(r['seats'] for r in races)} seats; "
            f"{len(cands)} candidates, {won['True']} elected"
            + (f", {won['None']} tied for a last seat in {', '.join(tied)}" if tied else "")
            + (f"; recounted: {', '.join(recounted)}" if recounted else "")
            + (". Every column agrees with the file's Totals" if not short else
               f". Every column agrees with the file's Totals but {short} whose Totals formula "
               "leaves out a town (flagged)")
            + " and every race elects its seats.")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--year", type=int, required=True, help="the general election's year")
    ap.add_argument("--districts", default="site/districts.json")
    ap.add_argument("--out", default=None, help="default collected/election_<year>.json")
    ap.add_argument("--saved", default=None, help="the day the files were saved, YYYY-MM-DD; "
                                                  "default each file's modification day")
    ap.add_argument("--check", action="store_true", help="compare with the committed file; "
                                                         "write nothing")
    ap.add_argument("--registry", default=None,
                    help="the registry of downloads (JSON: file, url, page, saved, sha256 of "
                         "each), which gives each _source its page and day and holds it to the "
                         "file's sha256")
    ap.add_argument("--partial", action="store_true",
                    help="a county or the whole Senate may have no file; say so in the notes "
                         "(2016)")
    # THE RESULTS PAGE'S ADDRESS (23 October 2026). README promises that
    # /members_elect.json carries "the address of the Secretary of State's
    # results it was read from", and the Officials tab links "the Secretary of
    # State's count" to it -- but build_members_elect takes it from each
    # _source's url, and this wrote None there every time, so the 2024
    # rehearsal's file named no address and the tab's link was never drawn.
    ap.add_argument("--url", default=None,
                    help="the Secretary of State's results page the files were saved from, "
                         "https://..., written as each _source's url")
    a = ap.parse_args()
    out = Path(a.out or f"collected/election_{a.year}.json")
    try:
        if a.year % 2:
            raise Refused(f"{a.year} has no state general election")
        if a.url is not None and not URL.fullmatch(a.url):
            raise Refused(f"--url {a.url!r} is not an https address")
        try:
            districts = (json.loads(Path(a.districts).read_text(encoding="utf-8"))
                         if a.year >= TABLE_SINCE else None)
        except (OSError, ValueError) as e:
            raise Refused(f"the district table ({a.districts}) will not read, and every race is "
                          f"held to it: {e}")
        registry = None
        if a.registry:
            try:
                registry = {e["file"]: e for e in json.loads(Path(a.registry).read_text(
                    encoding="utf-8"))}
            except (OSError, ValueError, KeyError, TypeError) as e:
                raise Refused(f"the registry of downloads ({a.registry}) will not read: {e}")
        doc = read_all(".", a.year, districts, a.saved, a.url, a.partial, registry)
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    if a.check:
        try:
            committed = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"REFUSED: {out.as_posix()} will not read: {e}", file=sys.stderr)
            return 1
        diff = differences(doc, committed)
        if diff:
            print(f"{out.as_posix()} is not what the saved files say ({len(diff)}):",
                  file=sys.stderr)
            for d in diff[:20]:
                print(f"  {d}", file=sys.stderr)
            return 1
        print(f"{out.as_posix()} is what the saved files say. " + summary(doc))
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(doc), encoding="utf-8")
    for n in doc.get("_notes") or []:
        print(f"FLAGGED: {n}")
    print(f"wrote {out.as_posix()}: " + summary(doc))
    print("  The files mark no winner: each race's winners are its top counts, as many as its "
          "seats.")
    if not a.url and not a.registry:
        # Silence is not success: a file with no address is a page that
        # cites the count and cannot link it.
        print("  NO --url: no _source names the results page, so members_elect.json will name "
              "no address for them and the Officials tab cites the count unlinked. Run it "
              "again with --url https://... (the page the files were saved from).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
