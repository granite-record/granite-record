#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.1
"""
One canonical list of New Hampshire places, and what each source says about it.

    python3 build_places.py --report     # says what it found, writes nothing
    python3 build_places.py              # -> places.json

WHY THIS FILE EXISTS

Five lists on this disk count the same state and get five different answers:

    districts/*.txt                 320 rows, 259 distinct names
    town_clerks.json                339 rows, 259 distinct names
    town_officials.json             234 rows, 234 distinct names
    db/Towns.psv                    273 rows
    GRANIT NHPolitDists             324 polygons          (not on this disk)

None of them is wrong. They count different things, and every tool that
joins two of them has to decide -- usually silently, usually differently --
what a "place" is. This writes the decision down once.

THE RULE. A PLACE is a row in the four district files: a city, a town, an
unincorporated place, or a ward of one of those. That is the unit the
General Court legislates for and the unit a district is built from, and it
is the only list here that all four district classes agree on exactly.

Everything else is recorded as what a named source says about that place,
not as a fact about the world. A ward is not a property of a town; it is a
property of a town AS A PARTICULAR LIST WARDS IT, and the two lists here
ward differently on purpose (see below).

HOW THE FIVE COUNTS RECONCILE. Measured, not asserted -- `--report` prints
the arithmetic and preflight checks it:

    259 distinct places          in districts/*.txt and in town_clerks.json,
                                 the same 259 in both
    259 = 234 + 25               234 are in NHDOT's City and Town Officials
                                 directory; 25 are not
    320 = 247 + 73               districts/*.txt: 247 rows for places it does
                                 not ward, 73 ward rows across 12 places
    339 = 331 + 8                town_clerks.json: 331 rows read from the
                                 Secretary of State's list, plus 8 town-level
                                 rows parse_clerks.py synthesises for the
                                 towns that list wards and this site does not
    331 = 247 + 92 - 8           the Secretary of State's own 331 rows: 92
                                 ward rows across 20 places
    273                          db/Towns.psv, which is not a list of
                                 municipalities at all: it carries village and
                                 postal names -- Penacook, West Lebanon, Etna,
                                 Sanbornville -- that have no town government.

THE TWO LISTS WARD DIFFERENTLY, AND BOTH ARE RIGHT. The General Court wards
a place when it needs to, to build a House district out of part of a city;
the Secretary of State wards a place when its voters vote in more than one
building. So:

    twelve places are warded by both       Claremont, Concord, Dover,
                                           Franklin, Keene, Laconia, Lebanon,
                                           Manchester, Nashua, Portsmouth,
                                           Rochester, Somersworth
    eight more by the Secretary of State   Berlin, Derry, Farmington,
      alone                                Goffstown, Hudson, Merrimack,
                                           Salem, Walpole

Berlin is a city the General Court does not ward. Derry, Farmington,
Goffstown, Hudson, Merrimack, Salem and Walpole are TOWNS with wards. Any
code that reads a ward as meaning "this is a city" is wrong about eight
places, and any code that reads "no ward here" as "the other list is stale"
is wrong about Berlin.

WHAT THIS FILE DOES NOT DECIDE. Which places are cities, which are towns and
which are unincorporated. That is a fact about the world with a published
answer, and this has not read it: the Secretary of State's "Towns and Wards
Redistricted for Election Purposes Beginning 2022" carries it. Until then
every record says so in as many words rather than carrying a guess, because
`in NHDOT's directory` and `is an incorporated municipality` are two
different claims that happen to agree on a count.

PROVENANCE, PER RECORD AND PER SOURCE. Each record says which source named
it, what that source's own document date is, and when this read it. The
district files are the awkward case and say so: they carry no source URL, no
retrieval date and no statement of which redistricting plan they encode, so
their provenance is recorded as unknown rather than as today's date. Fixing
that means checking them against the Secretary of State's published
definitions, which is outstanding work and not this script's job.
"""
import argparse
import collections
import datetime
import json
import pathlib
import re
import sys

import parse_districts

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "places.json"

DISTRICT_FILES = ("congress", "council", "senate", "house")

# What each source is, and what its own document date is -- which is not the
# day this read it. A PDF's embedded CreationDate is the day the information
# is true as of; the day a parser happened to open it says nothing.
SOURCES = {
    "districts": {
        "what": "districts/congress.txt, council.txt, senate.txt, house.txt",
        "document_date": None,
        "provenance": "unknown -- these files carry no source URL, no "
                      "retrieval date and no statement of which redistricting "
                      "plan they encode. Checking them against the Secretary "
                      "of State's published district definitions at "
                      "https://www.sos.nh.gov/elections/voting-districts is "
                      "outstanding.",
    },
    "sos_clerks": {
        "what": "sources/sos-clerks-and-polling-places.pdf, exported by hand "
                "from app.sos.nh.gov/statelistclerkandpolling",
        "document_date": "2026-09-12",
        "provenance": "the PDF's embedded CreationDate is "
                      "D:20260912173019-04'00'.",
    },
    "nhdot_officials": {
        "what": "sources/nh-municipal-officials-2025-09-01.pdf, NHDOT's "
                "City and Town Officials of the State of New Hampshire",
        "document_date": "2025-09-02",
        "provenance": "the PDF's embedded CreationDate is "
                      "D:20250902153549-04'00', which is a day later than the "
                      "date in the filename.",
    },
}


def slug(name):
    """'Bean's Grant' -> 'bean-s-grant', matching town_clerks.json's keys."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower())
    return s.strip("-")


def norm(name):
    """Letters and digits only, for joining lists that punctuate differently."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# The four district files and db/Towns.psv abbreviate the unincorporated
# places differently and neither is more correct than the other. These are the
# pairs, written out rather than matched by a rule, because a rule loose enough
# to pair "Low & Burbank's Gt." with "Low & Burbank's Grant" is loose enough to
# pair two real towns.
SPELLINGS = {
    "atkgilacademygrant": "atkgilmantonacademygt",
    "chandlerspur": "chandlerspurchase",
    "crawfordspur": "crawfordspurchase",
    "lowburbanksgrant": "lowburbanksgt",
    "thompsonmessspurchase": "thompsonmesspur",
    "wentworthsloc": "wentworthslocation",
    "secondcollegegt": "secondcollegegrant",
}


def read_districts():
    """{(town, ward)} per district file, and the county of every town."""
    per_file, county = {}, {}
    for name in DISTRICT_FILES:
        path = ROOT / "districts" / f"{name}.txt"
        if name == "house":
            d = parse_districts.parse_house(path)
            for key, v in d.items():
                for t, w in v["towns"]:
                    county.setdefault(norm(t), set()).add(v["county"])
            places = {tw for v in d.values() for tw in v["towns"]}
        else:
            d = parse_districts.parse(path)
            places = {tw for towns in d.values() for tw in towns}
        per_file[name] = places
    return per_file, county


def read_clerks():
    """{(town, ward)} as the Secretary of State's list wards them, and which
    of the keys parse_clerks.py synthesised rather than read."""
    data = json.load(open(ROOT / "town_clerks.json", encoding="utf-8"))
    places, synthetic = set(), set()
    for key, rec in data.items():
        m = re.match(r"^(.*?)-ward-(\d+)$", key)
        if m:
            places.add((m.group(1), m.group(2)))
        else:
            places.add((key, "0"))
            # A town-level key that carries polling_by_ward, or one whose own
            # wards are keyed separately, is the roll-up parse_clerks.py makes
            # for a town this site draws one page for. It is not a row of the
            # Secretary of State's list.
            if "polling_by_ward" in rec or any(
                    k.startswith(key + "-ward-") for k in data):
                synthetic.add(key)
    return places, synthetic


def read_officials():
    data = json.load(open(ROOT / "town_officials.json", encoding="utf-8"))
    return {k: v.get("municipality", k) for k, v in data.items()}


def build():
    today = datetime.date.today().isoformat()
    per_file, county = read_districts()
    clerk_places, synthetic = read_clerks()
    officials = read_officials()

    # THE RULE: a place is a row in the district files. All four must agree,
    # and they are compared rather than assumed to.
    sets = {name: {(t, w) for t, w in p} for name, p in per_file.items()}
    base = sets["house"]
    disagree = {n: (s ^ base) for n, s in sets.items() if s != base}

    names = {}
    for p in base:
        names.setdefault(norm(p[0]), p[0])

    off_by_norm = {norm(v): k for k, v in officials.items()}

    places = {}
    for key in sorted(names, key=lambda k: names[k]):
        name = names[key]
        gc_wards = sorted((int(w) for t, w in base if norm(t) == key and w != "0"))
        sos_wards = sorted((int(w) for t, w in clerk_places
                            if norm(t) == key and w != "0"))
        in_clerks = any(norm(t) == key for t, w in clerk_places)
        oh = off_by_norm.get(key) or off_by_norm.get(SPELLINGS.get(key, ""))
        counties = sorted(county.get(key, ()))

        places[slug(name)] = {
            "name": name,
            "county": counties[0] if len(counties) == 1 else None,
            "classification": {
                "state": "not_looked",
                "note": "city, town or unincorporated place. The Secretary of "
                        "State's 'Towns and Wards Redistricted for Election "
                        "Purposes Beginning 2022' carries this and has not "
                        "been read.",
            },
            "named_by": {
                "districts": {
                    "present": True,
                    "wards": [str(w) for w in gc_wards],
                    "read": today,
                },
                "sos_clerks": {
                    "present": in_clerks,
                    "wards": [str(w) for w in sos_wards],
                    "read": "2026-09-16",
                },
                "nhdot_officials": {
                    "present": oh is not None,
                    "key": oh,
                    "read": "2026-09-16",
                },
            },
        }
        if len(counties) != 1:
            places[slug(name)]["county_note"] = (
                f"districts/house.txt puts this place in {len(counties)} "
                f"counties: {', '.join(counties) or 'none'}")
    return places, disagree, synthetic, today


def report(places, disagree, synthetic):
    n = len(places)
    gc_ward_rows = sum(len(p["named_by"]["districts"]["wards"]) for p in places.values())
    gc_warded = sum(1 for p in places.values() if p["named_by"]["districts"]["wards"])
    sos_ward_rows = sum(len(p["named_by"]["sos_clerks"]["wards"]) for p in places.values())
    sos_warded = sum(1 for p in places.values() if p["named_by"]["sos_clerks"]["wards"])
    in_off = sum(1 for p in places.values() if p["named_by"]["nhdot_officials"]["present"])
    in_cl = sum(1 for p in places.values() if p["named_by"]["sos_clerks"]["present"])
    unwarded_gc = n - gc_warded
    unwarded_sos = n - sos_warded

    print(f"  {n} places, the rule being one row per name in districts/*.txt")
    if disagree:
        for name, diff in disagree.items():
            print(f"  ! districts/{name}.txt disagrees with house.txt on "
                  f"{len(diff)} rows: {sorted(diff)[:4]}")
    else:
        print("  all four district files name the same places, exactly")
    print(f"  {in_cl} are in the Secretary of State's clerk list")
    print(f"  {in_off} are in NHDOT's City and Town Officials directory, "
          f"{n - in_off} are not")
    print()
    print(f"  districts/*.txt : {unwarded_gc} unwarded + {gc_ward_rows} ward rows "
          f"across {gc_warded} places = {unwarded_gc + gc_ward_rows}")
    print(f"  clerk list      : {unwarded_sos} unwarded + {sos_ward_rows} ward rows "
          f"across {sos_warded} places = {unwarded_sos + sos_ward_rows}")
    print(f"  town_clerks.json: that, plus {len(synthetic)} town-level rows "
          f"parse_clerks.py synthesises = "
          f"{unwarded_sos + sos_ward_rows + len(synthetic)}")
    print()
    both = sorted(k for k, p in places.items()
                  if p["named_by"]["districts"]["wards"]
                  and p["named_by"]["sos_clerks"]["wards"])
    sos_only = sorted(k for k, p in places.items()
                      if not p["named_by"]["districts"]["wards"]
                      and p["named_by"]["sos_clerks"]["wards"])
    gc_only = sorted(k for k, p in places.items()
                     if p["named_by"]["districts"]["wards"]
                     and not p["named_by"]["sos_clerks"]["wards"])
    print(f"  warded by both ({len(both)}): {', '.join(both)}")
    print(f"  warded by the Secretary of State alone ({len(sos_only)}): "
          f"{', '.join(sos_only)}")
    print(f"  warded by the General Court alone ({len(gc_only)}): "
          f"{', '.join(gc_only) or 'none'}")
    mismatch = [k for k, p in places.items()
                if p["named_by"]["districts"]["wards"]
                and p["named_by"]["sos_clerks"]["wards"]
                and p["named_by"]["districts"]["wards"]
                != p["named_by"]["sos_clerks"]["wards"]]
    print(f"  warded by both but into different wards: {mismatch or 'none'}")
    nocounty = [k for k, p in places.items() if p["county"] is None]
    print(f"  places whose county is not a single answer: {nocounty or 'none'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true",
                    help="say what was found and write nothing")
    args = ap.parse_args()

    places, disagree, synthetic, today = build()
    report(places, disagree, synthetic)

    if args.report:
        print("\n  --report: nothing written")
        return 0

    payload = {
        "_what": "One row per city, town, unincorporated place and ward of "
                 "one, as districts/*.txt names them. See build_places.py for "
                 "the rule and for how the 320 / 331 / 339 / 234 / 273 counts "
                 "reconcile to it.",
        "_generated": today,
        "_sources": SOURCES,
        "places": places,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"\n  wrote {OUT.name}: {len(places)} places")
    return 0


if __name__ == "__main__":
    sys.exit(main())
