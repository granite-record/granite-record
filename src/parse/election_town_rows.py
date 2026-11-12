#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.2
"""
The town and ward rows of the Secretary of State's State Representative and
State Senate general-election files, kept (stage 1 of the elections plan,
12 November 2026), and held to the Totals the files print.

parse_sos_results.py reads every town's row to check a race's column against
the Totals row beside it, and used to keep only the race's total. It now hands
this module what it read; this writes two tidy tables per election, beside
collected/election_<year>.json, which it leaves exactly as it was:

    collected/election_town_rows_<year>.csv   one row per candidate (or count
                                              that is not a candidate's) per
                                              town or ward
    collected/election_printed_totals_<year>.csv  one row per figure a file's
                                              Totals row prints

A ROW IS THE FILE'S OWN, COPIED. Nothing is inferred: `votes` is the cell,
read as a whole number; `place` is the town or ward as the file prints it
(a star a clerk put on a corrected count is dropped, as the reader drops it),
`place_district_table` its spelling in the district table where the year has
one; `source_file`, `source_sheet`, `source_row` and `source_sha256` say where
to look. `row_kind` is candidate, write_in_named, write_ins_scattered,
undervotes or overvotes -- the last three are counts of ballots, never a
candidate's, and are never added to one. A cell the file leaves empty and
nothing needs is not a row.

IDS ARE BUILT FROM THINGS IN THE FILES, never a counter, so a rerun cannot
renumber them: election_id `2024-11-05-general`; contest_id
`2024-11-05.general.house.strafford-15` (the date, the stage, the office, the
district); candidate_id the contest and a slug of the printed name and party
(`...wendy-chase-d`; a named write-in `...kathy-desroches-write-in`; the three
counts `...undervotes`); row_id the candidate, the place and the count kind.
`person_id` is not here: matching a name to a member is stage 2's, and a
loss is never put on a person on a guess.

A RECOUNT'S FIGURES REPLACE THE FIRST COUNT'S, and both are kept: `count_kind`
is `first` or `recount`, and `in_race_count` says which one the race's own
total (collected/election_<year>.json) is made of. A BLC column (the Ballot
Law Commission's count, taken as the later count) is `blc_adjusted`.

TIE_OUT holds the rows to three things that were not generated from them:
    1. each column's town rows sum to the figure the file's Totals row prints;
    2. each candidate's rows in a race sum to the race's total in
       election_<year>.json, and the scattered write-ins to its `scatter`;
    3. the places of a race are its towns in election_<year>.json and, for
       the years with a district table (2022 on), the district table's.
A file that disagrees with itself is RECORDED, not corrected: collected/
election_tieout.json lists each, with the file, sheet and row, and preflight
fails when the list changes. Where the printed Totals and the towns differ
the race uses the towns, as the reader always did, and says so in _notes.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import csv
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict

TOWN_COLUMNS = ["row_id", "election_id", "election_date", "contest_id", "office", "district_key",
                "district", "county", "seats", "place", "place_district_table", "place_kind",
                "candidate_id", "candidate", "party", "row_kind", "count_kind", "in_race_count",
                "blc_adjusted", "block_header_row", "votes", "source_file", "source_sheet", "source_row",
                "source_sha256"]
TOTAL_COLUMNS = ["contest_id", "election_id", "office", "district_key", "candidate_id",
                 "candidate", "party", "row_kind", "count_kind", "in_race_count", "blc_adjusted",
                 "block_header_row", "printed_total", "source_file", "source_sheet", "source_row", "source_sha256"]
VOTE_KINDS = ("candidate", "write_in_named")


def town_path(year, root="."):
    return Path(root) / "collected" / f"election_town_rows_{year}.csv"


def totals_path(year, root="."):
    return Path(root) / "collected" / f"election_printed_totals_{year}.csv"


TIEOUT = Path("collected") / "election_tieout.json"


def slug(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def district_words(key):
    """("house", "Strafford 15", "Strafford") or ("senate", "Senate 5", "")."""
    parts = key.split("|")
    if parts[0] == "H":
        return "house", f"{parts[1]} {parts[2]}", parts[1]
    return "senate", f"Senate {parts[1]}", ""


def place_kind(place):
    return "ward" if re.search(r"\bward\b", place, re.I) else "town"


def tables(doc, election):
    """(town rows, printed totals), each a list of dicts, from the document
    read_all made (its `_town_rows`), in a fixed order."""
    sha = {Path(s["file"]).name: s["sha256"] for s in doc["_source"]}
    eid = f"{election.isoformat()}-general"
    rows, totals = [], []
    for key, trows, printed, spelt in doc["_town_rows"]:
        office, district, county = district_words(key)
        contest = f"{election.isoformat()}.general.{office}.{slug(district)}"
        seats = doc["races"][key]["seats"]

        def cid(r):
            if r["row_kind"] == "candidate":
                return f"{contest}.{slug(r['candidate'])}" + (f"-{slug(r['party'])}" if r["party"] else "")
            if r["row_kind"] == "write_in_named":
                return f"{contest}.{slug(r['candidate'])}-write-in"
            return f"{contest}.{r['row_kind'].replace('_', '-')}"
        for r in trows:
            c = cid(r)
            row_id = f"{c}@{slug(r['place'])}.{r['count_kind']}"
            rows.append({
                "row_id": row_id, "election_id": eid, "election_date": election.isoformat(),
                "contest_id": contest, "office": office, "district_key": key,
                "district": district, "county": county, "seats": seats, "place": r["place"],
                "place_district_table": spelt.get(r["place"], ""),
                "place_kind": place_kind(r["place"]), "candidate_id": c,
                "candidate": r["candidate"], "party": r["party"], "row_kind": r["row_kind"],
                "count_kind": r["count_kind"], "in_race_count": r["in_race_count"],
                "blc_adjusted": r["blc"], "block_header_row": r["header_row"],
                "votes": r["votes"], "source_file": r["source_file"],
                "source_sheet": r["source_sheet"], "source_row": r["source_row"],
                "source_sha256": sha[r["source_file"]]})
        for r in printed:
            c = cid(r)
            totals.append({
                "contest_id": contest, "election_id": eid, "office": office,
                "district_key": key, "candidate_id": c, "candidate": r["candidate"],
                "party": r["party"], "row_kind": r["row_kind"], "count_kind": r["count_kind"],
                "in_race_count": r["in_race_count"], "blc_adjusted": r["blc"],
                "block_header_row": r["header_row"], "printed_total": r["printed_total"], "source_file": r["source_file"],
                "source_sheet": r["source_sheet"], "source_row": r["source_row"],
                "source_sha256": sha[r["source_file"]]})
    return rows, totals


def to_csv(rows, columns):
    """The rows as text: UTF-8, \\n line ends, True/False for flags, so the
    same rows are the same bytes on any machine."""
    out = io.StringIO(newline="")
    w = csv.writer(out, lineterminator="\n")
    w.writerow(columns)
    for r in rows:
        w.writerow([("true" if r[c] else "false") if isinstance(r[c], bool) else r[c]
                    for c in columns])
    return out.getvalue()


def from_csv(text):
    """The rows of a table as written by to_csv, flags and whole numbers
    restored."""
    out = []
    for r in csv.DictReader(io.StringIO(text, newline="")):
        for k, v in list(r.items()):
            if v in ("true", "false"):
                r[k] = v == "true"
            elif k in ("votes", "printed_total", "source_row", "seats", "block_header_row"):
                r[k] = int(v)
        out.append(r)
    return out


def tie_out(rows, totals, races, districts_races=None):
    """{"checks": {name: {"held": n, "disagree": n}}, "disagreements": [...],
    "kinds": {row_kind: n}} for one election's tables, `races` being the
    `races` of collected/election_<year>.json and `districts_races` the
    district table's races (build_members_elect.races_on_file), or None for
    a year the table does not describe. Each disagreement names its file,
    sheet and row; none is corrected."""
    checks = defaultdict(lambda: {"held": 0, "disagree": 0})
    bad = []

    def note(name, ok, what, where):
        checks[name]["held"] += 1
        if not ok:
            checks[name]["disagree"] += 1
            bad.append({"check": name, "what": what, "where": where})
    by_row = defaultdict(list)
    for r in rows:
        by_row[(r["contest_id"], r["candidate_id"], r["count_kind"],
                r["block_header_row"])].append(r)
    ids = Counter(r["row_id"] for r in rows)
    for k, n in ids.items():
        note("row ids are unique", n == 1, f"{k} appears {n} times", "")
    for r in rows:
        note("every row carries a count and its source", isinstance(r["votes"], int)
             and r["votes"] >= 0 and r["source_file"] and r["source_row"] > 0
             and len(r["source_sha256"]) == 64,
             f"{r['row_id']}: votes {r['votes']!r}, source {r['source_file']!r} row "
             f"{r['source_row']!r}", f"{r['source_file']} row {r['source_row']}")
    # 1. A column's town rows against the Totals row the file prints.
    for t in totals:
        if t["blc_adjusted"]:
            # The BLC column's cells are whole counts or changes (apply_blc);
            # the printed Totals were held to them there, not to the rows.
            continue
        got = sum(r["votes"] for r in by_row[(t["contest_id"], t["candidate_id"],
                                              t["count_kind"], t["block_header_row"])])
        note("a column's towns sum to the file's Totals", got == t["printed_total"],
             f"{t['district_key']} {t['candidate']} ({t['row_kind']}, {t['count_kind']}): "
             f"the towns add up to {got:,}, the file's Totals say {t['printed_total']:,}",
             f"{t['source_file']}, sheet {t['source_sheet']!r}, row {t['source_row']}")
    # 2. A race's candidates against the race's total in the results file.
    per = defaultdict(lambda: defaultdict(int))
    scatter = defaultdict(int)
    for r in rows:
        if not r["in_race_count"]:
            continue
        if r["row_kind"] in VOTE_KINDS:
            per[r["district_key"]][(r["candidate"], r["party"])] += r["votes"]
        elif r["row_kind"] == "write_ins_scattered":
            scatter[r["district_key"]] += r["votes"]
    for key, race in races.items():
        have = per.get(key, {})
        for c in race["candidates"]:
            got = have.get((c["name"], c["party"]))
            note("a candidate's towns sum to the race's total",
                 got == c["votes"],
                 f"{key} {c['name']}: the towns add up to "
                 f"{'nothing' if got is None else format(got, ',')}, the race says "
                 f"{c['votes']:,}", key)
        named = {(c["name"], c["party"]) for c in race["candidates"]}
        extra = sorted(set(have) - named)
        note("every candidate in the rows is in the race", not extra,
             f"{key}: {extra} are in the town rows and not in the race", key)
        if race.get("scatter") is not None:
            note("the scattered write-ins sum to the race's", scatter.get(key, 0)
                 == race["scatter"], f"{key}: the rows add up to {scatter.get(key, 0):,}, the "
                 f"race says {race['scatter']:,}", key)
    note("every race has rows", all(k in per for k in races) and all(k in races for k in per),
         "a race without town rows, or town rows without a race", "")
    # 3. A race's places against the race's towns, and the district table's.
    places = defaultdict(set)
    for r in rows:
        places[r["district_key"]].add(r["place_district_table"] or r["place"])
    for key, race in races.items():
        note("a race's places are its towns", places.get(key, set()) == set(race["towns"]),
             f"{key}: the rows name {sorted(places.get(key, set()))}, the race "
             f"{sorted(race['towns'])}", key)
        if districts_races is not None:
            t = districts_races.get(key)
            note("a race's places are the district table's",
                 t is not None and places.get(key, set()) == set(t["towns"])
                 and race["seats"] == t["seats"],
                 f"{key}: the rows name {sorted(places.get(key, set()))}, the district table "
                 f"{sorted(t['towns']) if t else 'no such district'}", key)
    kinds = Counter(r["row_kind"] for r in rows)
    return {"checks": {k: dict(v) for k, v in sorted(checks.items())},
            "disagreements": bad, "kinds": dict(sorted(kinds.items()))}


def summary(year, rows, totals, result):
    off = Counter(r["office"] for r in rows)
    return (f"{year}: {len(rows):,} town rows ("
            + ", ".join(f"{o} {n:,}" for o, n in sorted(off.items()))
            + f"), {len(totals):,} printed totals; tie-out "
            + ", ".join(f"{v['held'] - v['disagree']}/{v['held']}"
                        for v in result["checks"].values())
            + f"; {len(result['disagreements'])} disagreement(s)")
