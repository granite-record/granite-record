#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.1
"""
The Secretary of State's own district table, and what it says about ours.

    python3 parse_sos_districts.py --report    # compare, write nothing
    python3 parse_sos_districts.py             # -> sos_districts.json

WHY. `districts/congress.txt`, `council.txt`, `senate.txt` and `house.txt`
carry no provenance of any kind: no source URL, no retrieval date, no
statement of which redistricting plan they encode. Everything this site says
about who represents a town rests on them, and nothing has ever checked them
against the published legal definition.

THE SOURCE. `sources/sos-towns-and-wards-districted-2023-04-26.pdf`, "Towns
and Wards as Districted for Election Purposes 2022", by Karen Ladd of the New
Hampshire Department of State. Its embedded CreationDate is
D:20230426104240-04'00', so 26 April 2023 is the date its contents are true
as of -- not the day it was downloaded. It is linked from
https://www.sos.nh.gov/elections/voting-districts, which indexes the legal
definitions, and it is the only one of them that carries all four district
classes and the county for every place in a single table.

It goes the other way round from our files. This table is one row per place
naming its districts; `districts/*.txt` is one district naming its places.
Inverting one to meet the other is the whole comparison, and it is worth
doing precisely because the two were written by different people from
different directions: an error that survives both is unlikely.

THE SHAPE. A plain row is

    Acworth 2 2 8 4, 8 Sullivan

-- name, congressional district, Executive Council district, senatorial
district, one or more representative districts, county. A warded city is a
header line naming the city and sometimes its county, then one line per ward
with no name and no county:

    Dover - Strafford
    Ward 1 1 1 4 14, 21

The county sits in three different places across the seven pages -- on the
header line, on the first ward line, or omitted because the header carried it
-- so it is carried forward from whichever of them supplied it rather than
read from a fixed column.

REPRESENTATIVE DISTRICTS ARE NUMBERED WITHIN A COUNTY, and a place with two
of them has a base district and a floterial: Acworth's "4, 8" is Sullivan 4
and Sullivan 8, and Sullivan 8 is the floterial it shares. That is the same
fact `districts/house.txt` states by listing a town under two districts, and
comparing them is how this checks the floterial layer that
`preflight.py:_floterials_overlay` can only check for self-consistency.

THE SEPARATOR BETWEEN TWO REPRESENTATIVE DISTRICTS IS NOT RELIABLE, which is
why the columns are read as tokens rather than matched with one expression.
Three spellings appear:

    Acworth 2 2 8 4, 8 Sullivan            a comma, in almost every row
    Ward 2 2 2 15 16. 28                   a full stop, Concord Ward 2 only
    East Kingston 1 3 23 14 34 Rockingham  a space, East Kingston only

The last is the dangerous one. Read greedily, "East Kingston 1" is a place
name and the districts shift one column left, which silently gives East
Kingston another town's congressional, Executive Council and senatorial
districts -- and it is the only row in the file where that happens, so no
count would have caught it. So the name is taken as the tokens before the
first bare number, the county as the token after the last, and everything
between as the four district columns in order: one congressional, one
Executive Council, one senatorial, and however many representative districts
are left. No New Hampshire place has a digit in its name, and a "Ward N"
line is matched before the rule runs, so the first bare number is always the
congressional district.

Concord Ward 2's full stop is recorded rather than fixed quietly. The
alternative readings are that it has one district called "16. 28", which is
not a district number, or that the 28 belongs to nothing. Merrimack 28 is the
floterial over Concord wards 1 to 3 and wards 1 and 3 both carry it, so the
comma is the only reading that leaves the table consistent with itself.

A NAME CAN WRAP, AND IT WRAPS IN BOTH DIRECTIONS. The unincorporated places
have the longest names and three of them are split across two lines -- but
not the same way round:

    Atk. & Gil. 2 1 1 2 Coos       the TAIL is the line below the data
    Academy Gt
    Low & Burbank's 2 1 1 6 Coos
    Grant
    Thompson &                     the HEAD is the line above the data
    Mes's Pur. 2 1 3 6 Coos

So a line carrying no digits cannot be read by its position alone. It is
attached to whichever side spells a place this site already knows, by the
same test `parse_clerks.py` uses on the clerk list's page breaks: "Academy
Gt" joined to the row above spells Atk. & Gil. Academy Grant, and joined to
the row below spells nothing. Where the line is a warded city's header the
next line is a ward, which settles it before the rule runs.
"""
import argparse
import collections
import json
import pathlib
import re
import sys

import parse_districts

ROOT = pathlib.Path(__file__).resolve().parent
PDF = ROOT / "sources" / "sos-towns-and-wards-districted-2023-04-26.pdf"
OUT = ROOT / "sos_districts.json"

DOCUMENT_DATE = "2023-04-26"
SOURCE_URL = ("https://www.sos.nh.gov/sites/g/files/ehbemt561/files/"
              "inline-documents/sonh/towns-and-wards-as-districted-for-"
              "election-purposes-2022-remediated.pdf")

COUNTIES = {"Belknap", "Carroll", "Cheshire", "Coos", "Grafton",
            "Hillsborough", "Merrimack", "Rockingham", "Strafford",
            "Sullivan"}

# The page furniture, and the one section heading -- "Unincorporated Places",
# which is not a place and would otherwise be offered to the wrapped-name rule.
SKIP = re.compile(r"^(TOWNS AND WARDS|2022$|Executive$|Congressional Council|"
                  r"District District|Unincorporated Places$)")

WARD = re.compile(r"^Ward\s+(\d+)\b\s*(.*)$", re.I)
NUM = re.compile(r"^\d+$")


def read_pdf(path):
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for line in (pg.extract_text() or "").splitlines():
                out.append((pg.page_number, line.strip()))
    return out


def columns(rest, page, line, notes):
    """The four district columns and the county, out of what follows a name.

    Separators between representative districts vary, so they are stripped and
    the numbers counted instead: the first is congressional, the second
    Executive Council, the third senatorial, and every one after that is a
    representative district.
    """
    if "." in rest and re.search(r"\d\s*\.\s*\d", rest):
        notes.append(f"page {page}: {line!r} separates two representative "
                     f"districts with a full stop; read as a comma")
    toks = [t for t in re.split(r"[\s,.]+", rest) if t]
    county = None
    if toks and toks[-1] in COUNTIES:
        county = toks.pop()
    if len(toks) < 4 or not all(NUM.match(t) for t in toks):
        notes.append(f"page {page}: {line!r} does not read as four district "
                     f"columns")
        return None
    n = [int(t) for t in toks]
    return n[0], n[1], n[2], n[3:], county


def known_places():
    """Every place districts/*.txt names, for settling a wrapped name."""
    d = parse_districts.parse_house(ROOT / "districts" / "house.txt")
    return sorted({t for v in d.values() for t, _ in v["towns"]})


def match_place(cand, places):
    """The one place `cand` spells, or None.

    The two lists abbreviate the unincorporated places differently and neither
    is more correct: this table writes "Erving's Loc." and "Pinkham's Gt"
    where the district files write them out. `parse_clerks.abbrev_of` already
    decides that question for the clerk list -- a token matches when its
    letters appear in order in the full word, starting at the first -- so it
    decides it here too rather than a second rule growing up beside it.

    None where nothing matches AND where more than one does, because a name
    that could be either of two places is not evidence for either.
    """
    import parse_clerks
    exact = [p for p in places if norm(p) == norm(cand)]
    if exact:
        return exact[0]
    up = cand.upper()
    hit = [p for p in places if parse_clerks.abbrev_of(up, p.upper())
           or parse_clerks.abbrev_of(p.upper(), up)]
    return hit[0] if len(hit) == 1 else None


def names_a_place(cand, places):
    return match_place(cand, places) is not None



def parse(path):
    """[(name, ward, cong, council, senate, [house], county)], and the notes."""
    raw = [(p, l) for p, l in read_pdf(path) if l and not SKIP.match(l)]
    places = known_places()
    rows, notes, fragments = [], [], []
    town = county = None
    for i, (page, line) in enumerate(raw):
        w = WARD.match(line)
        if w and w.group(2):
            if town is None:
                notes.append(f"page {page}: {line!r} is a ward with no city "
                             f"above it")
                continue
            got = columns(w.group(2), page, line, notes)
            if got is None:
                continue
            cong, council, senate, house, c = got
            if c:
                county = c
            rows.append((town, w.group(1), cong, council, senate, house, county))
            continue

        if not re.search(r"\d", line):
            # No digits: a warded city's header, or half of a name the
            # generator wrapped -- and the half can belong to the row above or
            # the row below. A ward on the next line settles the first case;
            # `resolve_fragment` settles the rest against the places we know.
            nxt = raw[i + 1][1] if i + 1 < len(raw) else ""
            head = re.sub(r"[-–]\s*$", "", line).strip()
            if WARD.match(nxt):
                bits = head.rsplit(" ", 1)
                if len(bits) == 2 and bits[1] in COUNTIES:
                    town, county = bits[0].rstrip(" -–").strip(), bits[1]
                else:
                    town, county = head.rstrip(" -–").strip(), None
                carry = ""
            else:
                fragments.append((len(rows), page, head))
            continue

        # A plain row: the name is everything before the first bare number.
        toks = line.split()
        cut = next((j for j, t in enumerate(toks) if NUM.match(t)), None)
        if cut is None or cut == 0:
            notes.append(f"page {page}: {line!r} has no name")
            carry = ""
            continue
        name = " ".join(toks[:cut]).strip()
        got = columns(" ".join(toks[cut:]), page, line, notes)
        if got is None:
            continue
        cong, council, senate, house, c = got
        town, county = name.rstrip(" -–").strip(), c
        rows.append((town, "0", cong, council, senate, house, county))

    # Now attach every wrapped half to the row it belongs to. Done after the
    # whole table is read, because the test is whether the join spells a place
    # -- which needs the row on each side to exist first.
    for at, page, frag in reversed(fragments):
        up = rows[at - 1] if at > 0 else None
        down = rows[at] if at < len(rows) else None
        up_name = f"{up[0]} {frag}".strip() if up else None
        down_name = f"{frag} {down[0]}".strip() if down else None
        fits_up = bool(up_name) and names_a_place(up_name, places) \
            and not names_a_place(up[0], places)
        fits_down = bool(down_name) and names_a_place(down_name, places) \
            and not names_a_place(down[0], places)
        if fits_up and not fits_down:
            rows[at - 1] = (up_name,) + up[1:]
        elif fits_down and not fits_up:
            rows[at] = (down_name,) + down[1:]
        else:
            notes.append(
                f"page {page}: {frag!r} carries no districts of its own and "
                f"joins neither {up[0]!r} above nor {down[0] if down else None!r} "
                f"below into a place this site knows"
                + (" -- both joins spell one" if fits_up and fits_down else ""))
    return rows, notes


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def ours():
    """districts/*.txt, inverted to place -> districts."""
    out = collections.defaultdict(lambda: {"cong": set(), "council": set(),
                                           "senate": set(), "house": set()})
    for key, name in (("cong", "congress"), ("council", "council"),
                      ("senate", "senate")):
        d = parse_districts.parse(ROOT / "districts" / f"{name}.txt")
        for num, places in d.items():
            for t, w in places:
                out[(norm(t), w)][key].add(int(num))
    h = parse_districts.parse_house(ROOT / "districts" / "house.txt")
    for v in h.values():
        for t, w in v["towns"]:
            out[(norm(t), w)]["house"].add((v["county"], int(v["district"])))
    return out


def compare():
    rows, notes = parse(PDF)
    mine = ours()
    theirs = {}
    places = known_places()
    unmatched = []
    for name, ward, cong, council, senate, house, county in rows:
        # Key on OUR spelling, so the two lists' different abbreviations of the
        # unincorporated places do not read as different places.
        m = match_place(name, places)
        if m is None:
            unmatched.append(name)
        k = norm(m or name)
        theirs[(k, ward)] = {"cong": {cong}, "council": {council},
                             "senate": {senate},
                             "house": {(county, n) for n in house},
                             "county": county}
    only_theirs = sorted(set(theirs) - set(mine))
    only_mine = sorted(set(mine) - set(theirs))
    diffs = collections.defaultdict(list)
    for k in sorted(set(theirs) & set(mine)):
        for field in ("cong", "council", "senate", "house"):
            a, b = mine[k][field], theirs[k][field]
            if a != b:
                diffs[field].append((k, sorted(a), sorted(b)))
    for n in unmatched:
        notes.append(f"{n!r} in the Secretary of State's table "
                     f"matches no place districts/*.txt names")
    return rows, notes, theirs, mine, only_theirs, only_mine, diffs


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true",
                    help="compare and write nothing")
    a = ap.parse_args()

    if not PDF.exists():
        print(f"  {PDF.name} is not in sources/")
        return 1

    rows, notes, theirs, mine, only_theirs, only_mine, diffs = compare()
    print(f"  {PDF.name}, document date {DOCUMENT_DATE}")
    print(f"  {len(rows)} rows read, {len(theirs)} distinct place-and-ward keys")
    print(f"  districts/*.txt has {len(mine)}")
    for n in notes:
        print(f"  ! {n}")
    print()
    if only_theirs:
        print(f"  {len(only_theirs)} in the Secretary of State's table and not "
              f"in ours:")
        for k in only_theirs:
            print(f"      {k}")
    if only_mine:
        print(f"  {len(only_mine)} in ours and not in the Secretary of State's:")
        for k in only_mine:
            print(f"      {k}")
    if not only_theirs and not only_mine:
        print("  the two name exactly the same places and wards")
    print()
    total = sum(len(v) for v in diffs.values())
    if not total:
        print("  and agree on every congressional, Executive Council, "
              "senatorial and representative district of every one of them")
    else:
        for field, items in diffs.items():
            print(f"  {len(items)} disagree on {field}:")
            for k, a, b in items[:40]:
                print(f"      {k}   ours {a}   theirs {b}")
    if a.report:
        print("\n  --report: nothing written")
        return 0

    payload = {
        "_what": "The Secretary of State's 'Towns and Wards as Districted for "
                 "Election Purposes 2022', one record per place and ward.",
        "_source_url": SOURCE_URL,
        "_read_on": DOCUMENT_DATE,
        "_method": "pdfplumber over the saved PDF; no network",
        "_notes": notes,
        "places": {f"{k[0]}|{k[1]}": {
            "cong": sorted(v["cong"]), "council": sorted(v["council"]),
            "senate": sorted(v["senate"]),
            "house": sorted(f"{c} {n}" for c, n in v["house"]),
            "county": v["county"],
            "source_url": SOURCE_URL, "read_on": DOCUMENT_DATE,
            "method": "pdfplumber", "status": "published",
        } for k, v in sorted(theirs.items())},
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"\n  wrote {OUT.name}: {len(theirs)} places")
    return 0


if __name__ == "__main__":
    sys.exit(main())
