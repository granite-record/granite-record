#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-18.1
"""
The Secretary of State's count of the State Primary's races for Governor,
United States Senator, Representative in Congress, Executive Councilor and
the county offices, 2016 to 2026, each party's primary its own race. Read by
parse_sos_primary_results.read_year into the same collected/primary_<year>.json
as the House and Senate races (that reader writes the file; this one only
reads), so that one writer writes the year whole. Nothing on the site reads
these files yet.

WHAT IT READS, in records/sources/, saved by a person in a browser byte for
byte under the names the Secretary of State gave them (nothing here asks the
network), one file a party:

    <year>-sp-governor-<party>[_N].xls[x]             2016-2024: one workbook,
    <year>-sp-u.s.-senate-<party>.xls (2016)          a summary of the counties
    <year>-sp-united-states-senate-<party>.xls,       and a block of towns for
      -uss-<party>[_N].xls (2020, 2022)               each county
    2026-sp-governor-<county|summary>-<party>.xlsx    2026: a file a county and
    2026-sp-us-senator-<county|summary>-<party>.xlsx  the summary
    <year>-sp-congressional-district-<n>-<party>[_N].xlsx
    <year>-sp-executive-council-1-5-<party>[-][_N].xls    2016-2024: a district a sheet
    2026-sp-executive-council-<n>-<party>.xlsx            2026: a district a file
    <year>-sp-<county>-county-<party>[_N].xls         2016-2022: a county's offices
    <year>-sp-county-offices-<county>-<party>[_N].xls 2024, 2026

and five files of 2016 whose names do not say the year or the primary
(ALIASES), each read as the 2016 primary's: their titles say the primary and
the party, and their headers print 13 September 2016, which the reader holds.

THE LAYOUT IS THE GENERAL ELECTION'S (read on 18 November 2026, file by file,
before a line of this was written), and parse_sos_offices's rules read it
(statewide_blocks and settle_statewide; district_blocks and settle_block;
read_county), given the primary's day as parse_sos_primary_results.Primary,
which carries the party and the rule that marks the nominees. What differs:
the titles name the party ("Governor - Republican", "Congressional District 1
- Democratic", "Belknap County Offices - Republican"); a party's file names
every candidate any place wrote in, of any party, with an empty cell where no
vote came, read as none (parse_sos_offices.Block with a primary); and a
summary's Totals that print nothing under a candidate no county wrote in are
read as the counties' rows, and said.

THE NOMINEES are parse_sos_primary_results.nominate's: the most votes, as
many as the seats and none with no votes, a tie or a place the unnamed
write-ins could have taken null and said, places no named candidate won
"open". A race's count is the summary's Totals for the statewide offices, as
the general reader has it, and its places' sum for the others; where another
figure the files print would nominate someone else, the race is refused. A
file that disagrees with itself is recorded in "_disagreements" with file,
sheet and row, never corrected.

IT REFUSES RATHER THAN GUESSES: a file it cannot read is listed in the year's
"_refused" with why and where, and its races are not written; a county
office's race it cannot settle is refused alone. The rest of the year is
written.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import re

import parse_sos_offices as PSO
import parse_sos_primary_results as P
import parse_sos_results as PSR

SOURCES = PSR.SOURCES
PARTY = r"(?P<party>democratic|republican|libertarian)"
STATEWIDE_FILE = re.compile(r"^(?P<y>\d{4})-sp-(?P<office>governor|u\.s\.-senate|"
                            r"united-states-senate|uss|us-senator)(?:-(?P<part>[a-z]+))??-"
                            + PARTY + r"-?(?:_\d+)?\.xlsx?$")
DISTRICT_FILE = re.compile(r"^(?P<y>\d{4})-sp-(?P<office>congressional-district|executive-council)-"
                           r"(?P<a>\d+)(?:-(?P<b>\d+))?-" + PARTY + r"-?(?:_\d+)?\.xlsx?$")
COUNTY_FILE = re.compile(r"^(?P<y>\d{4})-sp-(?:county-offices-(?P<a>[a-z]+)|(?P<b>[a-z]+)-county)-"
                         + PARTY + r"-?(?:_+\d+)?\.xlsx?$")
# A file whose name runs a stray letter onto the party, by name, with (county,
# party), read as that county's.
COUNTY_FILE_TYPOS = {"2016-sp-belknap-county-democraticl.xls": ("belknap", "democratic"),
                     "2016-sp-sullivan-county-republicanl.xls": ("sullivan", "republican")}
# 2016's files whose names say neither the year nor the primary, by name, with
# (office key, district or None, party). Their titles say the primary and the
# party, and their headers the primary's day, which the reader holds.
ALIASES = {
    "2016-governor-democratic.xls": ("governor", None, "democratic"),
    "congressional-district-1-democratic.xlsx": ("us-house", 1, "democratic"),
    "congressional-district-1-republican16.xlsx": ("us-house", 1, "republican"),
    "congressional-district-2-democratic.xlsx": ("us-house", 2, "democratic"),
    "congressional-district-2-republican16.xlsx": ("us-house", 2, "republican"),
}
ALIAS_YEAR = 2016
STATEWIDE_KEYS = {"governor": "governor", "u.s.-senate": "us-senate",
                  "united-states-senate": "us-senate", "uss": "us-senate",
                  "us-senator": "us-senate"}
DISTRICT_KEYS = {"congressional-district": "us-house", "executive-council": "executive-council"}
# The title of an office's sheets in {p}'s primary: "Governor - Republican",
# "Congressional District 1 - Democratic"; the dash before the party is left
# out in 2016-2022's Council ("Executive Council - District No. 1 Democratic")
# and 2026's Congress.
TITLES = {
    "governor": ("Governor", r"^governor\s*-?\s*{p}$"),
    "us-senate": ("United States Senator", r"^united states senator\s*-?\s*{p}$"),
    "us-house": ("Representative in Congress", r"^congressional district\s+(\d+)\s*-?\s*{p}$"),
    "executive-council": ("Executive Councilor",
                          r"^executive council\s*-\s*district no\.?\s*(\d+)\s*-?\s*{p}$"),
}


def office(key, party):
    """The office as parse_sos_offices's readers take it: its name, and the
    title its sheets print in `party`'s primary."""
    name, title = TITLES[key]
    return {"name": name, "title": re.compile(title.format(p=party), re.I)}


def files_of(root, year):
    """{"statewide": {(key, party): {"whole": path} or {"summary": path,
    "counties": {county: path}}}, "district": {(key, party): {(a, b): path}},
    "county": {(county, party): path}, "replaced": [(earlier, later)]}."""
    d = Path(root) / SOURCES
    sw, dist, county, replaced = {}, {}, {}, []
    names = sorted(d.glob(f"{year}-*")) if d.is_dir() else []
    if year == ALIAS_YEAR:
        names += [d / n for n in ALIASES if (d / n).is_file() and d / n not in names]
    for p in names:
        alias = ALIASES.get(p.name)
        if alias:
            key, n, party = alias
            if n is None:
                sw.setdefault((key, party), {"whole": [], "summary": [], "counties": {}})[
                    "whole"].append(p)
            else:
                dist.setdefault((key, party), {}).setdefault((n, n), []).append(p)
            continue
        m = STATEWIDE_FILE.match(p.name)
        if m:
            key, party, part = STATEWIDE_KEYS[m.group("office")], m.group("party"), m.group("part")
            got = sw.setdefault((key, party), {"whole": [], "summary": [], "counties": {}})
            if part is None:
                got["whole"].append(p)
            elif part == "summary":
                got["summary"].append(p)
            elif part.title() in PSO.COUNTIES:
                got["counties"].setdefault(part.title(), []).append(p)
            else:
                raise P.Refused(f"{p.name}: {part!r} is neither a county nor the summary")
            continue
        m = DISTRICT_FILE.match(p.name)
        if m:
            a = int(m.group("a"))
            dist.setdefault((DISTRICT_KEYS[m.group("office")], m.group("party")), {}).setdefault(
                (a, int(m.group("b") or a)), []).append(p)
            continue
        typo = COUNTY_FILE_TYPOS.get(p.name)
        m = COUNTY_FILE.match(p.name)
        if typo or m:
            c, party = typo or ((m.group("a") or m.group("b")), m.group("party"))
            if c.title() not in PSO.COUNTIES:
                raise P.Refused(f"{p.name} names no county of New Hampshire")
            county.setdefault((c.title(), party), []).append(p)
    out = {"statewide": {}, "district": {}, "county": {}, "replaced": replaced}
    for (key, party), got in sorted(sw.items()):
        what = f"the {party} {TITLES[key][0]} primary"
        if got["whole"] and (got["summary"] or got["counties"]):
            raise P.Refused(f"{what} is saved both whole and in parts")
        if got["whole"]:
            out["statewide"][(key, party)] = {"whole": PSR.latest(got["whole"], what, replaced)}
        else:
            if not got["summary"]:
                raise P.Refused(f"no summary file of {what} beside its county files")
            out["statewide"][(key, party)] = {
                "summary": PSR.latest(got["summary"], f"{what}'s summary", replaced),
                "counties": {c: PSR.latest(ps, f"{c}'s {what}", replaced)
                             for c, ps in sorted(got["counties"].items())}}
    for (key, party), parts in sorted(dist.items()):
        n = PSO.office_districts(key)
        missing, overlaps = PSR.senate_unheld(parts, n)
        if overlaps:
            raise P.Refused(f"the {party} {TITLES[key][0]} primary's district {overlaps[0][0]} is "
                            "in more than one saved file")
        out["district"][(key, party)] = {
            s: PSR.latest(ps, f"the {party} {TITLES[key][0]} primary, {PSR.span_words(s)}",
                          replaced) for s, ps in sorted(parts.items())}
    for (c, party), ps in sorted(county.items()):
        out["county"][(c, party)] = PSR.latest(ps, f"{c}'s {party} county offices primary",
                                                replaced)
    return out


def record(race, party, notes):
    """A race as primary_<year>.json writes it: its candidates, the counts
    that are no candidate's, how many figures its Totals rows printed, and
    the places no named candidate won."""
    cands = [{k: c[k] for k in ("name", "party", "votes", "write_in", "nominated", "id")}
             for c in race["candidates"]]
    out = {"party": P.PARTIES[party], "office": race["office"], "district": race["district"],
           "seats": race["seats"], "contest": race["contest"], "count_from": race["count_from"],
           "candidates": cands, "scatter": race["scatter"], "undervotes": race["undervotes"],
           "overvotes": race["overvotes"],
           "printed_totals": sum(sum(v is not None for v in p[1]) for p in race["printed"])}
    if race.get("county"):
        out["county"] = race["county"]
    if race.get("recounted"):
        out["recounted"] = True
    won = sum(c["nominated"] is True for c in cands)
    if race["seats"] is not None and won < race["seats"] and not any(
            c["nominated"] is None for c in cands):
        out["open"] = race["seats"] - won
    return out


def read_year(root, year):
    """(races, files read, notes, refused, disagreements) of `year`'s
    primaries for the offices this reads."""
    root = Path(root)
    legacy = year <= PSR.LEGACY_UNTIL
    files = files_of(root, year)
    races, read, notes, refused, bad = {}, [], [], [], []
    notes += [f"{new.name} is read, and replaces {old.name}: the Secretary of State's later "
              "upload of the same results" for old, new in files["replaced"]]

    def put(key, race, party, said):
        rec = record(race, party, said)
        k = f"{P.PARTIES[party].upper()}|{key}"
        said.extend(P.race_notes(k, rec, race["contest"]))
        races[k] = rec

    for (key, party), fs in files["statewide"].items():
        election, said, here = P.Primary(year, party), [], []
        try:
            off = office(key, party)
            blocks = []
            if "whole" in fs:
                here.append(fs["whole"])
                blocks = PSO.statewide_blocks(fs["whole"], off, election, legacy, said)
            else:
                here.append(fs["summary"])
                got = PSO.statewide_blocks(fs["summary"], off, election, legacy, said)
                if [b.label for b in got] != ["summary"]:
                    raise P.Refused(f"{fs['summary'].name}: holds {[b.label for b in got]}, not "
                                    "the summary alone")
                blocks += got
                for c, p in fs["counties"].items():
                    here.append(p)
                    got = PSO.statewide_blocks(p, off, election, legacy, said)
                    if [b.label for b in got] != [c]:
                        raise P.Refused(f"{p.name}: holds {[b.label for b in got]}, not {c}'s "
                                        "towns alone")
                    blocks += got
            summ = [b for b in blocks if b.label == "summary"]
            if len(summ) != 1:
                raise P.Refused(f"{here[0].name}: {len(summ)} summaries of the counties, not one")
            by_county = {}
            for b in blocks:
                if b.label != "summary":
                    if b.label in by_county:
                        raise P.Refused(f"{b.where}: {b.label} County's towns twice")
                    by_county[b.label] = b
            race, _r, d = PSO.settle_statewide(year, key, election, summ[0], by_county, here,
                                               said)
        except PSR.Unreadable:
            raise
        except PSR.Refused as e:
            # Every file of the race is listed: it is read whole or not at all.
            whole = [fs["whole"]] if "whole" in fs else [fs["summary"], *fs["counties"].values()]
            refused += [{"file": p.name, "why": str(e)} for p in whole]
            continue
        blanks = sum(b.blank_named for b in blocks)
        if blanks:
            said.append(f"the {party} {off['name']} primary: {blanks} empty cell(s) under a "
                        "candidate, read as none")
        put(key, race, party, said)
        read += here
        notes += said
        bad += d
    for (key, party), parts in files["district"].items():
        election, off = P.Primary(year, party), office(key, party)
        for (a, b), path in parts.items():
            said = []
            try:
                got = PSO.district_blocks(path, key, election, legacy, said, office=off)
                if sorted(got) != list(range(a, b + 1)):
                    raise P.Refused(f"{path.name} holds district(s) "
                                    f"{', '.join(map(str, sorted(got)))}; its name says "
                                    f"{PSR.span_words((a, b))}")
                settled = {n: PSO.settle_block(key, n, got[n], election, 1, said)
                           for n in sorted(got)}
            except PSR.Unreadable:
                raise
            except PSR.Refused as e:
                refused.append({"file": path.name, "why": str(e)})
                continue
            blanks = sum(blk.blank_named for blk in got.values())
            if blanks:
                said.append(f"{path.name}: {blanks} empty cell(s) under a candidate, read as none")
            for n, (race, d) in settled.items():
                put(f"{key}|{n}", race, party, said)
                bad += d
            read.append(path)
            notes += said
    for (county, party), path in files["county"].items():
        election, said = P.Primary(year, party), []
        try:
            got, _r, d, _m, quiet, alone = PSO.read_county(root, year, election, said,
                                                           files=({county: path}, []))
        except PSR.Unreadable:
            raise
        except PSR.Refused as e:
            refused.append({"file": path.name, "why": str(e)})
            continue
        for k, race in got.items():
            put(k, race, party, said)
        refused += [{"file": path.name, "race": f"{P.PARTIES[party].upper()}|{r['race']}",
                     "why": r["why"]} for r in alone]
        said += [f"{q['where']}: {P.PARTIES[party].upper()}|{q['race']}: {q['says']}; no race "
                 "is read" for q in quiet]
        read.append(path)
        notes += said
        bad += d
    return races, read, notes, refused, bad


def files_known(root, year):
    """Every file files_of names for `year`, the replaced among them."""
    files = files_of(root, year)
    known = {p for fs in files["statewide"].values()
             for p in ([fs["whole"]] if "whole" in fs else [fs["summary"], *fs["counties"].values()])}
    known |= {p for parts in files["district"].values() for p in parts.values()}
    return known | set(files["county"].values()) | {old for old, _new in files["replaced"]}
