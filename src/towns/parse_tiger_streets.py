#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.1
"""
Every New Hampshire street that carries house numbers, by town and ZIP code,
read from the Census Bureau's TIGER/Line files.

    python3 src/towns/parse_tiger_streets.py --report    # what it found, write nothing
    python3 src/towns/parse_tiger_streets.py             # -> collected/nh_streets.json
    python3 src/towns/parse_tiger_streets.py --year 2027

WHY (the person, 24 October 2026: "I'd like to make some improvements to the
address search so that it shows you a dropdown of matching addresses around
New Hampshire as you're typing with the zip codes"). The Your town panel's
address box suggests addresses as a reader types, from files this site
serves (src/pages/build_addr_index.py writes them from this file), so that
nothing the reader types goes anywhere until they choose an address. This is
the list those files are cut from.

THE SOURCE. TIGER/Line, the release src/fetch/other/tiger_streets.py saved
under records/sources/tiger/<year>/; this reads those zips and asks no
network. Three layers, joined:

  ADDRFEAT  an edge of a street with house numbers: the name (FULLNAME, and
            a row for each alternate name of the same edge -- "Bemis Rd" and
            "Bemis Savoie Rd" are one stretch of road in Bedford), the first
            and last number on each side (LFROMHN, LTOHN, RFROMHN, RTOHN),
            whether a side's numbers are odd, even or both (PARITYL,
            PARITYR), and each side's ZIP code (ZIPL, ZIPR).
  FACES     the polygon on each side of an edge (TFIDL, TFIDR), with the
            county subdivision it lies in (COUSUBFP).
  COUSUB    the county subdivisions' names.

THE TOWN IS THE SIDE'S OWN. A road on a town line has one town on its left
and another on its right, and each side's numbers are given the town its own
face is in. That is the simplest join that is right on a boundary: the
county-subdivision layer would need the geometry, and FACES already carries
the answer for every face. It is the municipality, which is what this site
is about, and not the post office's name for the place: a house in Webster
on ZIP 03303 is "Webster", though its mail is addressed to Concord. The
Census geocoder takes either (asked 24 October 2026: "50 Battle St,
Webster, NH 03303" matches, in Webster). An unorganized place is named with
what it is, "Hale's Location", "Beans Purchase", because COUSUB's own name
alone is "Hale's" -- and "Beans" twice, a grant and a purchase, and
"Wentworth", a location as well as a town.

THE NUMBERS ARE KEPT BY PARITY. On most streets the odd numbers are one side
and the even the other, and where a street is a ZIP boundary the two sides
have different ZIP codes (North Mammoth Road in Manchester: the even side
03104, the odd 03106), so the number's parity is what picks the ZIP. Each
side's range becomes the odd or the even numbers between its ends ("both"
gives one of each), and ranges of one parity that meet are joined: Concord's
North Main Street is 32 edges, and here "1-299 2-298". A gap stays a gap,
since the geocoder places a number only inside a range.

WHAT IS LEFT OUT, AND SAID. A side whose numbers are not plain numbers --
Sanbornton's "264-98" and its neighbours', Belmont's "B98" -- gives its
street to the list with no range, so the street is still suggested and the
number the reader types is shown as they typed it. An edge with no name, or
a side whose face lies in no county subdivision (water), is not a street
anyone lives on. --report counts each.

THE FILE. collected/nh_streets.json: where it came from, then one row a
line -- street, town, ZIP, house numbers -- sorted by town, street and ZIP,
so a new release's diff reads town by town. The house numbers are
space-separated runs, each of only odd or only even numbers, its ends'
parity: "1-299 2-298", or one number alone, "5".
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import struct
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime

ROOT = _paths.ROOT
YEAR = 2026
OUT = ROOT / "collected" / "nh_streets.json"
# The county subdivision classes with addresses: a town (T1, and T9 for
# Livermore, which has no government), a city (C5), and an unorganized grant,
# location, purchase or township (Z1). Z9 is the water no subdivision covers.
UNORGANIZED = "Z1"
NOT_A_PLACE = "Z9"


def dbf_rows(data):
    """The records of a dBASE table, as dicts of stripped strings. TIGER's
    tables are plain dBASE III: a header, 32 bytes a field, then fixed-width
    records, the first byte of each "*" where it is deleted."""
    n, hlen, rlen = struct.unpack("<IHH", data[4:12])
    fields, off = [], 32
    while data[off] != 0x0D:
        name = data[off:off + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, data[off + 16]))
        off += 32
    pos = hlen
    for _ in range(n):
        rec = data[pos:pos + rlen]
        pos += rlen
        if rec[:1] == b"*":
            continue
        row, o = {}, 1
        for name, width in fields:
            # TIGER's 2026 tables are UTF-8 (their .cpg says so).
            row[name] = rec[o:o + width].decode("utf-8", "replace").strip()
            o += width
        yield row


def read_dbf(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".dbf"))
        return list(dbf_rows(z.read(name)))


def town_names(folder, year):
    """(county, subdivision) -> the name this site gives it."""
    out = {}
    for r in read_dbf(folder / f"tl_{year}_33_cousub.zip"):
        if r["CLASSFP"] == NOT_A_PLACE:
            continue
        if r["CLASSFP"] == UNORGANIZED:
            # "Hale's location" -> "Hale's Location".
            head, _, kind = r["NAMELSAD"].rpartition(" ")
            name = f"{head} {kind[:1].upper()}{kind[1:]}" if head else r["NAMELSAD"]
        else:
            name = r["NAME"]
        out[(r["COUNTYFP"], r["COUSUBFP"])] = name
    return out


def parity_run(lo, hi, parity):
    """The runs a side's range stands for: [(lo, hi)], each of one parity."""
    lo, hi = min(lo, hi), max(lo, hi)
    want = {"O": (1,), "E": (0,)}.get(parity, (1, 0))
    out = []
    for p in want:
        a = lo if lo % 2 == p else lo + 1
        b = hi if hi % 2 == p else hi - 1
        if a <= b:
            out.append((a, b))
    return out


def join_runs(runs):
    """Runs of one parity that meet, joined; odd runs first, each in order."""
    out = []
    for p in (1, 0):
        mine = sorted(r for r in runs if r[0] % 2 == p)
        joined = []
        for a, b in mine:
            if joined and a <= joined[-1][1] + 2:
                joined[-1][1] = max(joined[-1][1], b)
            else:
                joined.append([a, b])
        out += joined
    return out


def say_runs(runs):
    return " ".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


def read(folder, year):
    """The rows, and what was counted on the way."""
    towns = town_names(folder, year)
    face = {}
    for c in sorted(folder.glob(f"tl_{year}_33*_faces.zip")):
        for r in read_dbf(c):
            face[r["TFID"]] = (r["COUNTYFP"], r["COUSUBFP"])
    runs = defaultdict(list)
    seen = set()
    n = Counter()
    for c in sorted(folder.glob(f"tl_{year}_33*_addrfeat.zip")):
        n["counties"] += 1
        for r in read_dbf(c):
            n["edge names"] += 1
            name = " ".join(r["FULLNAME"].split())
            if not name:
                n["edges with no name"] += 1
                continue
            for s in "LR":
                lo, hi = r[f"{s}FROMHN"], r[f"{s}TOHN"]
                if not lo and not hi:
                    continue
                n["sides with numbers"] += 1
                town = towns.get(face.get(r[f"TFID{s}"]))
                if not town:
                    n["sides in no town"] += 1
                    continue
                zp = r[f"ZIP{s}"]
                if not zp:
                    n["sides with no ZIP"] += 1
                key = (name, town, zp)
                seen.add(key)
                if lo.isdigit() and hi.isdigit():
                    runs[key] += parity_run(int(lo), int(hi), r[f"PARITY{s}"])
                else:
                    n["sides whose numbers are not plain numbers"] += 1
    rows = sorted(([k[0], k[1], k[2], say_runs(join_runs(runs.get(k, [])))] for k in seen),
                  key=lambda r: (r[1], r[0], r[2]))
    return rows, n


def published(folder, year):
    """The day the files were published -- the newest Last-Modified the
    fetcher recorded -- and the day they were read; or, where nothing was
    recorded, the newest date stamped inside the zips."""
    try:
        meta = json.loads((folder / "_meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    days = [parsedate_to_datetime(m["last_modified"]).date().isoformat()
            for m in meta.values() if m.get("last_modified")]
    read_on = [m["read_at"][:10] for m in meta.values() if m.get("read_at")]
    if not days:
        for p in folder.glob(f"tl_{year}_33*.zip"):
            with zipfile.ZipFile(p) as z:
                days += [datetime(*i.date_time).date().isoformat() for i in z.infolist()]
    return (max(days) if days else None), (min(read_on) if read_on else None)


def write(rows, folder, year, out):
    pub, read_on = published(folder, year)
    head = {
        "_about": ("Every New Hampshire street that carries house numbers, by town and ZIP "
                   "code: the list the Your town panel's address box suggests from. Written by "
                   "src/towns/parse_tiger_streets.py from the Census Bureau's TIGER/Line "
                   "files; its docstring says how. Each row is street, town, ZIP, house "
                   "numbers: space-separated runs, each of only odd or only even numbers, "
                   "\"1-299 2-298\". Public domain, as its source is."),
        "source": {
            "publisher": "U.S. Census Bureau",
            "release": f"TIGER/Line Shapefiles, {year}",
            "files": (f"https://www2.census.gov/geo/tiger/TIGER{year}/ -- ADDRFEAT and FACES "
                      "for each of the ten counties, COUSUB for the state"),
            "published": pub,
            "read_on": read_on,
        },
        "counts": {"rows": len(rows), "streets": len({r[0] for r in rows}),
                   "towns": len({r[1] for r in rows}),
                   "zip_codes": len({r[2] for r in rows if r[2]})},
        "columns": ["street", "town", "zip", "house numbers"],
    }
    # One row a line, so that a new release's diff is the review.
    text = json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ',\n "rows": [\n'
    text += ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows)
    text += "\n ]\n}\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--year", type=int, default=YEAR)
    ap.add_argument("--report", action="store_true", help="say what was found; write nothing")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    folder = ROOT / "records" / "sources" / "tiger" / str(a.year)
    need = [f"tl_{a.year}_33_cousub.zip"]
    missing = [x for x in need if not (folder / x).is_file()]
    if missing or not list(folder.glob(f"tl_{a.year}_33*_addrfeat.zip")):
        raise SystemExit(f"the TIGER{a.year} files are not in {folder}: "
                         f"python3 src/fetch/other/tiger_streets.py --year {a.year} brings them")
    rows, n = read(folder, a.year)
    if n["counties"] != 10:
        raise SystemExit(f"{n['counties']} of New Hampshire's 10 counties' ADDRFEAT files are in "
                         f"{folder}; a list with a county missing would suggest nothing there")
    # Silence is not success: a list this short is a reading gone wrong.
    if len(rows) < 30000:
        raise SystemExit(f"only {len(rows):,} rows were read; New Hampshire has nearly 40,000")
    for k, v in n.items():
        print(f"  {k}: {v:,}")
    print(f"  rows: {len(rows):,}, streets {len({r[0] for r in rows}):,}, "
          f"towns {len({r[1] for r in rows})}, with no range "
          f"{sum(1 for r in rows if not r[3]):,}")
    if a.report:
        return 0
    size = write(rows, folder, a.year, Path(a.out))
    print(f"{len(rows):,} rows -> {a.out} ({size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
