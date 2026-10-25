#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.1
"""
New Hampshire's public libraries, each in the town it stands in.

    python3 src/towns/parse_libraries.py --report    # say what it found, write nothing
    python3 src/towns/parse_libraries.py             # -> collected/libraries.json

WHY (the person, 24 October 2026: "gather more useful information for the
town pages like the address of city hall, directories for the public
schools in that town's district, transfer station addresses and hours if
possible ... That would exist on town pages and would display in things like
the guides if you have your town selected"). The library is one of the first
phase's cards on a town page's Town Services tab, beside the town office and
the tax rate.

WHAT IT READS, saved by src/fetch/other/town_directory.py and touching no
network here:

  imls           the Public Libraries Survey's outlet file, fiscal year 2024
                 (the Institute of Museum and Library Services, published
                 June 2026): each library building, central or branch, with
                 its address, phone, coordinates and the census block it was
                 geocoded to. Federal data, public domain.
  census_blocks  the Census Bureau's 2020 block assignment file, which names
                 the county subdivision -- the town -- of every block, and
                 the subdivisions' names.

WHERE A LIBRARY IS: ITS BLOCK'S TOWN, NEVER ITS POSTAL CITY. The survey's
city is the post office's, and 224 of its city names are not all towns: the
research of 24 October 2026 found only 198 of them to be a municipality's
name. A block lies in exactly one town, and every New Hampshire outlet
carries one, so each library is placed by it.

WHAT IT WRITES: collected/libraries.json, one entry a town that has a library,
keyed as the town pages key a town, each carrying the day its copy was read
(`read_on`, the day the fetcher saved the survey) and the survey's year, as
src/towns/town_sources.py asks every row to; under them the libraries,
central ones first. The survey types its names in capitals; they are
title-cased for the page by the clerks' rule (parse_clerks.placecase), and
the survey's own words are kept beside them under `raw`.

A FLOOR. A survey cut short, or a block file that matches nothing, still
parses, and would write a town page with no library. It refuses to write
under town_sources.FLOORS["imls_pls"] unless a person passes --allow-shrink.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import io
import json
import re
import zipfile

import parse_clerks
import parse_clerks_csv
import town_sources

ROOT = _paths.ROOT
STORE = ROOT / "records" / "sources" / "directory"
SURVEY = STORE / "imls" / "pls_fy2024_csv.zip"
OUTLETS = "CSV/pls_fy24_outlet_pud24i.csv"
BLOCKS = STORE / "census_blocks" / "BlockAssign_ST33_NH.zip"
BLOCK_FILE = "BlockAssign_ST33_NH_MCD.txt"
NAMES = STORE / "census_blocks" / "st33_nh_cousub2020.txt"
OUT = ROOT / "collected" / "libraries.json"

FISCAL_YEAR = 2024
SOURCE_URL = "https://www.imls.gov/research-evaluation/surveys/public-libraries-survey-pls"
KIND = {"CE": "central", "BR": "branch", "BS": "bookmobile", "BM": "books by mail"}
# The subdivision classes that are not a place a person lives in (the
# Census's Z9, "not a place"; parse_tiger_streets.NOT_A_PLACE says the same).
NOT_A_PLACE = "Z9"


def read_on():
    """The day the fetcher saved the survey, from its _meta.json; None where
    there is no record of it."""
    try:
        meta = json.loads((SURVEY.parent / "_meta.json").read_text(encoding="utf-8"))
        return str(meta[SURVEY.name]["read_at"])[:10]
    except (OSError, ValueError, KeyError):
        return None


def outlets():
    """The survey's New Hampshire outlets, as its own rows. The file is
    Windows-1252, as the survey publishes it."""
    with zipfile.ZipFile(SURVEY) as z:
        text = z.read(OUTLETS).decode("cp1252")
    return [r for r in csv.DictReader(io.StringIO(text)) if r["STABR"] == "NH"]


def block_towns():
    """{2020 block: (county, subdivision)}."""
    with zipfile.ZipFile(BLOCKS) as z:
        lines = z.read(BLOCK_FILE).decode("utf-8").splitlines()
    head = lines[0].split("|")
    out = {}
    for line in lines[1:]:
        r = dict(zip(head, line.split("|")))
        out[r["BLOCKID"]] = (r["COUNTYFP"], r["COUSUBFP"])
    return out


def subdivision_names():
    """{(county, subdivision): its name as this site writes a town's}: "Alton
    town" is Alton, "Berlin city" Berlin, and an unincorporated place keeps
    its kind, "Hale's location" written Hale's Location, as
    parse_tiger_streets.town_names has them."""
    lines = NAMES.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("|")
    out = {}
    for line in lines[1:]:
        r = dict(zip(head, line.split("|")))
        if r["CLASSFP"] == NOT_A_PLACE:
            continue
        head_, _, kind = r["COUSUBNAME"].rpartition(" ")
        if kind in ("town", "city") and head_:
            name = head_
        elif head_:
            name = f"{head_} {kind[:1].upper()}{kind[1:]}"
        else:
            name = r["COUSUBNAME"]
        out[(r["COUNTYFP"], r["COUSUBFP"])] = name
    return out


def phone(raw):
    """"6038352150" as 603-835-2150; "" for anything that is not ten digits
    (the survey writes -3 for none)."""
    d = re.sub(r"\D", "", raw or "")
    return f"{d[:3]}-{d[3:6]}-{d[6:]}" if len(d) == 10 else ""


def build(rows, blocks, names, towns, day):
    """({town key: entry}, [unplaced outlet], {town key: name}) -- each
    outlet in its block's town, matched to the towns the site has pages for
    by the clerks' rule (parse_clerks_csv.match_town)."""
    data, unplaced, named = {}, [], {}
    for r in rows:
        sub = blocks.get(r["CENBLOCK"].strip())
        name = names.get(sub) if sub else None
        town = parse_clerks_csv.match_town(name, towns) if name else None
        if town is None:
            unplaced.append(f"{r['LIBNAME']} ({r['CITY']}, block {r['CENBLOCK']}: "
                            f"{name or 'no town for the block'})")
            continue
        key = parse_clerks_csv.slug(town)
        named[key] = name
        lib = {"name": parse_clerks.placecase(r["LIBNAME"]),
               "street": parse_clerks.placecase(r["ADDRESS"]),
               "city": parse_clerks.placecase(r["CITY"]),
               "zip": (r["ZIP"] or "").strip()[:5],
               "phone": phone(r["PHONE"]),
               "kind": KIND.get(r["C_OUT_TY"], r["C_OUT_TY"].lower()),
               "lat": round(float(r["LATITUDE"]), 6),
               "lon": round(float(r["LONGITUD"]), 6),
               "imls": f"{r['FSCSKEY']}-{r['FSCS_SEQ']}",
               "block": r["CENBLOCK"].strip(),
               "raw": {"name": r["LIBNAME"], "address": r["ADDRESS"], "city": r["CITY"]}}
        entry = data.setdefault(key, {"read_on": day, "survey": f"FY{FISCAL_YEAR}",
                                      "libraries": []})
        entry["libraries"].append(lib)
    for entry in data.values():
        entry["libraries"].sort(key=lambda x: (x["kind"] != "central", x["name"]))
    return data, unplaced, named


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true", help="say what it found; write nothing")
    ap.add_argument("--allow-shrink", action="store_true",
                    help="write under town_sources.FLOORS['imls_pls'], saying what fell")
    ap.add_argument("--site", default="site", help="the built site, for its towns where "
                    "generated/places.json is not there")
    a = ap.parse_args(argv)
    for p in (SURVEY, BLOCKS, NAMES):
        if not p.exists():
            sys.exit(f"{p} is not here: run src/fetch/other/town_directory.py first")
    day = read_on()
    if not day:
        sys.exit(f"{SURVEY.parent / '_meta.json'} does not say when the survey was read")
    towns = parse_clerks_csv.load_towns(a.site)
    rows = outlets()
    data, unplaced, named = build(rows, block_towns(), subdivision_names(), towns, day)
    n = sum(len(e["libraries"]) for e in data.values())
    print(f"{len(rows)} New Hampshire outlets in the FY{FISCAL_YEAR} survey; {n} placed in "
          f"{len(data)} towns by their census blocks, {len(unplaced)} not placed")
    for u in unplaced:
        print(f"  not placed: {u}")
    out = {"_about": {
        "source": (f"the Institute of Museum and Library Services' Public Libraries Survey, "
                   f"fiscal year {FISCAL_YEAR}, its outlet file ({OUTLETS})"),
        "url": SOURCE_URL,
        "placed_by": "each library's census block, in the Census Bureau's 2020 block "
                     "assignment file for New Hampshire (county subdivisions)",
        "licence": "federal data, public domain",
        "writer": "src/towns/parse_libraries.py"}}
    out.update(dict(sorted(data.items())))
    short = town_sources.short_of("imls_pls", out)
    if short:
        print("  under the floor: " + "; ".join(short))
    if a.report:
        print("--report: nothing written")
        return 0
    if short and not a.allow_shrink:
        sys.exit("not written: the survey placed less than the floor holds (above); "
                 "--allow-shrink writes it anyway")
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                   newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
