#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.1
"""
NH GRANIT's district geometry, and whether it carries the districts we publish.

    python3 parse_granit.py --report     # say what the layers hold, write nothing
    python3 parse_granit.py              # -> granit_layers.json

WHAT IS HERE AND WHERE IT CAME FROM. Six shapefiles under `sources/gis/`,
fetched on 20 September 2026 from

    https://ftp.granit.unh.edu/GRANIT_Data/Vector_Data/
        Administrative_and_Political_Boundaries/

by NH GRANIT at the University of New Hampshire. The zips are not in git --
4.2 MB, re-fetchable from that address -- so everything here skips cleanly
when they are absent.

    CongDistricts2022.zip              2 polygons   Cong2022
    NHExecDistricts2022.zip            5 polygons   ExecCo2022
    NHSenateDistricts2022.zip         24 polygons   Senate2022
    NHHouseDistricts2022_Base.zip    164 polygons   BaseHse22
    NHHouseDistricts2022_Float.zip    40 polygons   FloatHse22
    NHPolitDists.zip                 324 polygons   NAME / WARD

THE 2012 TRAP. `CongDistricts2012.zip` sits in the same directory as the 2022
file and taking the wrong one silently gives the previous decade's boundaries
with no error at all. The file names here are pinned and the record written
out carries the year, so a swap shows up as a name rather than as a map that
is quietly wrong.

NO SHAPEFILE LIBRARY IS NEEDED TO CHECK THIS. `pyshp` is not installed and is
not asked for: a `.dbf` is a dBase table the standard library can unpack, and
the shape count is in the `.shp`'s own record headers. What a library WOULD
be needed for is reprojection, and that is deliberately not done here -- see
below.

BOTH HOUSE LAYERS ARE REQUIRED, and the metadata says so. 164 base districts
plus 39 floterial is the 203 the state elects 400 members from, and a
floterial overlays towns that already have a base district, so the two layers
genuinely overlap. A map that draws only the base layer loses every
floterial; one that unions the two into a single non-overlapping layer is
arithmetically impossible. Of the 40 polygons in the floterial file 39 carry
a code and one is blank -- the metadata explains that areas with no floterial
district were given an empty value, so the blank is the rest of the state and
not a defect.

ZERO-PADDING IS INCONSISTENT IN GRANIT'S OWN FIELD: `BE1` sits beside `HI03`
in `BaseHse22`. The normalising rule is written once, here: two letters of
county, then the number with leading zeros stripped.

PROJECTION. Every `.prj` reads NAD_1983_StatePlane_New_Hampshire_FIPS_2800_
Feet: Transverse Mercator, central meridian -71.666666666666667, scale factor
0.9999666666666667, latitude of origin 42.5, false easting 984250.0, false
northing 0, UNIT Foot_US 0.3048006096012192, on GCS_North_American_1983. That
is EPSG:3437 -- NAD83 / New Hampshire (ftUS) -- and NOT EPSG:2823, which is
the same grid on the HARN realisation; the datum here is plain NAD83, which
is what separates them.

The units are confirmed rather than taken from the name: every layer's own
bounding box is x 745474 to 1267015 and y 72030 to 1023284, which are feet.
In degrees those numbers would be meaningless, and in metres the state would
be six hundred miles wide.

WHAT THIS DOES NOT DO IS REPROJECT. A web map wants EPSG:4326 and getting
there means inverting a Transverse Mercator, which is not a thing to hand-roll
beside a civic record. `pyproj` is the tool and it is not installed; asking
for it is a person's decision. Whenever that happens, the result must be
proven against a known point rather than eyeballed on a map.

WHAT THE CHECK IS FOR. `districts/house.txt` is now verified against the
Secretary of State's published table by `parse_sos_districts.py`. This adds a
third, independent witness from a fourth direction -- a GIS office digitising
boundaries rather than anybody transcribing a list -- and the three agree on
all 203 districts. That is about as much corroboration as this kind of data
admits of.
"""
import argparse
import collections
import json
import pathlib
import re
import struct
import sys
import zipfile

import parse_districts

ROOT = pathlib.Path(__file__).resolve().parent
GIS = ROOT / "sources" / "gis"
OUT = ROOT / "granit_layers.json"

BASE_URL = ("https://ftp.granit.unh.edu/GRANIT_Data/Vector_Data/"
            "Administrative_and_Political_Boundaries")
READ_ON = "2026-09-20"

# zip name -> (path under the GRANIT directory, the field carrying the code,
#              how many polygons it should hold)
LAYERS = {
    "CongDistricts2022.zip": ("d-congressional", "Cong2022", 2),
    "NHExecDistricts2022.zip": ("d-executivecouncil", "ExecCo2022", 5),
    "NHSenateDistricts2022.zip": ("d-nhsenatedists", "Senate2022", 24),
    "NHHouseDistricts2022_Base.zip": ("d-nhhousedists", "BaseHse22", 164),
    "NHHouseDistricts2022_Float.zip": ("d-nhhousedists", "FloatHse22", 40),
    "NHPolitDists.zip": ("d-nhpolitdists", "WARD", 324),
}

COUNTY = {"BE": "Belknap", "CA": "Carroll", "CH": "Cheshire", "CO": "Coos",
          "GR": "Grafton", "HI": "Hillsborough", "ME": "Merrimack",
          "RO": "Rockingham", "ST": "Strafford", "SU": "Sullivan"}

LICENCE = ("Access Constraints: None; Use Constraints: Not for legal use. "
           "Permissive enough to publish a map. The site must not present "
           "these boundaries as authoritative for any legal purpose -- the "
           "Secretary of State's published definitions are the legal text.")


# ------------------------------------------------------------------ dBase ---

def read_dbf(data):
    """A dBase table as a list of dicts. No library: it is a documented format."""
    n_rec, hdr_len, rec_len = struct.unpack("<IHH", data[4:12])
    fields, pos = [], 32
    while data[pos] != 0x0D:
        raw = data[pos:pos + 32]
        fields.append((raw[:11].split(b"\0")[0].decode("latin-1"),
                       chr(raw[11]), raw[16]))
        pos += 32
    out = []
    for i in range(n_rec):
        rec = data[hdr_len + i * rec_len:hdr_len + (i + 1) * rec_len]
        if not rec or rec[:1] == b"*":          # deleted
            continue
        vals, p = {}, 1
        for name, _typ, length in fields:
            vals[name] = rec[p:p + length].decode("latin-1").strip()
            p += length
        out.append(vals)
    return [f[0] for f in fields], out


def shp_header(data):
    """(count, bbox) from a .shp's own record headers."""
    xmin, ymin, xmax, ymax = struct.unpack("<4d", data[36:68])
    n, pos = 0, 100
    while pos + 8 <= len(data):
        _, clen = struct.unpack(">II", data[pos:pos + 8])
        pos += 8 + clen * 2
        n += 1
    return n, (xmin, ymin, xmax, ymax)


def open_layer(name):
    z = zipfile.ZipFile(GIS / name)
    dbf = [n for n in z.namelist() if n.lower().endswith(".dbf")][0]
    shp = [n for n in z.namelist() if n.lower().endswith(".shp")][0]
    prj = [n for n in z.namelist() if n.lower().endswith(".prj")][0]
    fields, rows = read_dbf(z.read(dbf))
    count, bbox = shp_header(z.read(shp))
    return fields, rows, count, bbox, z.read(prj).decode("utf-8", "replace")


# ------------------------------------------------------------------ codes ---

def split_code(c):
    """'BE1' and 'HI03' both -> (county, number). The padding is not reliable."""
    m = re.fullmatch(r"([A-Z]{2})0*(\d+)", (c or "").strip())
    return (COUNTY[m.group(1)], int(m.group(2))) \
        if m and m.group(1) in COUNTY else None


def survey():
    """Every layer, what it holds, and what disagrees. Skips what is absent."""
    out, problems = {}, []
    for name, (sub, field, expect) in LAYERS.items():
        if not (GIS / name).exists():
            out[name] = {"present": False}
            continue
        fields, rows, count, bbox, prj = open_layer(name)
        if count != len(rows):
            problems.append(f"{name}: {count} shapes but {len(rows)} records")
        if count != expect:
            problems.append(f"{name}: {count} polygons, expected {expect}")
        if "StatePlane_New_Hampshire_FIPS_2800_Feet" not in prj:
            problems.append(f"{name}: unexpected projection {prj[:60]!r}")
        blank = sum(1 for r in rows if not r.get(field, "").strip())
        out[name] = {
            "present": True, "polygons": count, "fields": fields,
            "code_field": field, "blank_codes": blank, "bbox_ftus": list(bbox),
            "source_url": f"{BASE_URL}/{sub}/{name}",
            "read_on": READ_ON, "method": "curl; dBase read with struct",
            "status": "published", "epsg": 3437, "licence": LICENCE,
        }
    return out, problems


def house_codes():
    """GRANIT's House codes against districts/house.txt."""
    if not (GIS / "NHHouseDistricts2022_Base.zip").exists():
        return None
    _, base, _, _, _ = open_layer("NHHouseDistricts2022_Base.zip")
    _, flt, _, _, _ = open_layer("NHHouseDistricts2022_Float.zip")
    g_base = {split_code(r["BaseHse22"]) for r in base}
    g_flot = {split_code(r["FloatHse22"]) for r in flt if r["FloatHse22"].strip()}
    h = parse_districts.parse_house(ROOT / "districts" / "house.txt")
    o_base = {(v["county"], int(v["district"])) for v in h.values()
              if not v["floterial"]}
    o_flot = {(v["county"], int(v["district"])) for v in h.values()
              if v["floterial"]}
    return {"granit_base": g_base, "granit_floterial": g_flot,
            "ours_base": o_base, "ours_floterial": o_flot}


def ward_layer():
    """NHPolitDists' places and wards, and the polygons that share a name."""
    if not (GIS / "NHPolitDists.zip").exists():
        return None
    _, rows, _, _, _ = open_layer("NHPolitDists.zip")
    wards = collections.defaultdict(set)
    for r in rows:
        m = re.match(r"^(.*?)\s*-\s*(.*)$", r["WARD"])
        wards[r["NAME"]].add(m.group(2) if m else r["WARD"])
    dup = [w for w, n in collections.Counter(r["WARD"] for r in rows).items()
           if n > 1]
    return {"polygons": len(rows), "places": len(wards),
            "split": {k: sorted(v) for k, v in wards.items()
                      if v != {"Entire"}},
            "duplicate_ward_values": sorted(dup)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true", help="write nothing")
    a = ap.parse_args()

    layers, problems = survey()
    missing = [n for n, v in layers.items() if not v["present"]]
    if missing:
        print(f"  not in sources/gis/: {', '.join(missing)}")
        print(f"  fetch them from {BASE_URL}")
        if len(missing) == len(LAYERS):
            return 0
    for n, v in layers.items():
        if v["present"]:
            print(f"  {n:34s} {v['polygons']:4d} polygons, field "
                  f"{v['code_field']}"
                  + (f", {v['blank_codes']} blank" if v["blank_codes"] else ""))
    for p in problems:
        print(f"  ! {p}")

    hc = house_codes()
    if hc:
        print()
        print(f"  House: GRANIT {len(hc['granit_base'])} base + "
              f"{len(hc['granit_floterial'])} floterial; districts/house.txt "
              f"{len(hc['ours_base'])} + {len(hc['ours_floterial'])}")
        for label, a_, b_ in (("base", hc["granit_base"], hc["ours_base"]),
                              ("floterial", hc["granit_floterial"],
                               hc["ours_floterial"])):
            if a_ != b_:
                print(f"  ! {label}: only GRANIT {sorted(a_ - b_)}; "
                      f"only ours {sorted(b_ - a_)}")
        if hc["granit_base"] == hc["ours_base"] \
                and hc["granit_floterial"] == hc["ours_floterial"]:
            print("    every district code agrees, both layers")

    w = ward_layer()
    if w:
        print()
        print(f"  NHPolitDists: {w['polygons']} polygons over {w['places']} "
              f"places, {len(w['split'])} split into wards")
        print(f"    split: {', '.join(sorted(w['split']))}")
        if w["duplicate_ward_values"]:
            print(f"  ! one ward value is carried by more than one polygon: "
                  f"{w['duplicate_ward_values']} -- a join keyed on WARD "
                  f"double-counts it")

    if a.report:
        print("\n  --report: nothing written")
        return 0
    payload = {
        "_what": "NH GRANIT's 2022 district geometry and 2012-2017 ward layer.",
        "_read_on": READ_ON, "_source": BASE_URL, "_licence": LICENCE,
        "_epsg": 3437,
        "layers": layers,
        "ward_layer": w,
        "house_codes_agree": bool(hc and hc["granit_base"] == hc["ours_base"]
                                  and hc["granit_floterial"] == hc["ours_floterial"]),
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True, default=sorted)
                   + "\n", encoding="utf-8")
    print(f"\n  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
