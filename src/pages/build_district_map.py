#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.1
"""
The district map's data, and its script and stylesheet, into the site.

    python3 src/pages/build_district_map.py --site site

Writes site/district_map.json, the one file the map draws (map.js), and copies
src/pages/map.js and src/pages/map.css beside it. No page mounts the map yet:
Polish 3 places it on the Officials page's My Town tab and on the town pages,
each of which then loads /map.css and /map.js and calls GRMap.mount().

WHAT THE FILE HOLDS, and where each part comes from:

    w, h, arcs, layers   the geometry, as generated/district_geometry.json has
                         it (src/towns/build_district_geometry.py, run by a
                         person from the GIS zips, which only the laptop has;
                         committed, so the nightly carries it in git)
    _geometry            that file's sha256, so a site built from an older
                         geometry says so (preflight)
    places               every town and ward and the five districts it votes
                         in, from site/districts.json (parse_districts)
    cities               the thirteen cities (town_boards.CITIES), named on
                         the map before any town
    wards                each city's wards grouped by the State House district
                         they lie in, with the point their name is drawn at and
                         the box it must fit in
    seats, who           each district's seats and who sits for it: the
                         members from site/legislators.json, the Executive
                         Council and the US House from corrections/officials.json
                         (read, never written)
    fill                 the party each district is filled with: the letters
                         of its sitting members' parties, Republican first,
                         then Democratic, then Independent; "" where every
                         seat is vacant. A base district by its OWN members
                         (method (a), 8 October 2026), its floterial framed
                         in the floterial's. Counties and towns are not filled

THE PARTY IS THE RECORD'S. A member's party is site/legislators.json's, as
every page shows it; a councillor's or a representative's is officials.json's,
the person's hand-kept file. preflight holds every fill to those files
("every district on the map is filled from the record's party").

Asks nobody: it reads the site's own files and two tracked ones.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import hashlib
import json
import math
import re
import shutil

import town_boards

GEOMETRY = "generated/district_geometry.json"
SCRIPT, STYLE = "src/pages/map.js", "src/pages/map.css"

CODE = {"Belknap": "BE", "Carroll": "CA", "Cheshire": "CH", "Coos": "CO",
        "Grafton": "GR", "Hillsborough": "HI", "Merrimack": "ME",
        "Rockingham": "RO", "Strafford": "ST", "Sullivan": "SU"}
ORDER = "RDI"
# The layers whose districts are filled with their members' party; floterials
# are framed in theirs. Counties and towns are neutral.
FILLED = ("base", "float", "senate", "exec", "cong")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def letter(party):
    """'Republican' -> 'R'; 'D' -> 'D'; '' -> 'X'."""
    return (str(party or "").strip()[:1] or "X").upper()


def letters(parties):
    """The parties a district is filled with, in the map's fixed order:
    R, D, I, then any other letter alphabetically; each once."""
    got = set(parties)
    return "".join([p for p in ORDER if p in got] + sorted(got - set(ORDER)))


def places_table(districts):
    """{town: {"c": county, "w": {ward: [base, floterial or None, senate,
    council, congress]}}} from site/districts.json."""
    out = {}
    for town in sorted(districts):
        wards = {}
        county = None
        for ward in sorted(districts[town], key=lambda w: int(w) if w.isdigit() else 0):
            d = districts[town][ward]
            base = next(f"{CODE[h['county']]}{h['district']}" for h in d["house"]
                        if not h["floterial"])
            flo = next((f"{CODE[h['county']]}{h['district']}" for h in d["house"]
                        if h["floterial"]), None)
            county = county or d["house"][0]["county"]
            wards[ward] = [base, flo, str(d["senate"]), str(d["council"]),
                           str(d["congress"])]
        out[town] = {"c": county, "w": wards}
    return out


def seats_of(districts):
    """{House code: seats}."""
    out = {}
    for wards in districts.values():
        for d in wards.values():
            for h in d["house"]:
                out[f"{CODE[h['county']]}{h['district']}"] = int(h["seats"])
    return out


def who_sits(legislators, officials, places):
    """{"base|BE1": [person], "float|HI40": [...], "senate|16": [...],
    "exec|2": [...], "cong|1": [...]}. A member is {n: the site's full label,
    p: party letter, s: slug}; an official {n: name, p, u: their own site}.
    A House member is base or floterial by which kind of district their code
    is."""
    flo = {w[1] for t in places.values() for w in t["w"].values() if w[1]}
    out = {}
    for m in sorted(legislators, key=lambda m: (m.get("sort") or m.get("name") or "")):
        if m.get("chamber") == "H":
            code = f"{CODE.get(m.get('county'), '??')}{int(m['district'])}"
            key = ("float|" if code in flo else "base|") + code
        elif m.get("chamber") == "S":
            key = f"senate|{int(m['district'])}"
        else:
            continue
        out.setdefault(key, []).append({
            "n": m.get("display_full") or m.get("label") or m.get("name") or "",
            "p": letter(m.get("party")), "s": m.get("slug") or ""})
    for lk, office in (("exec", "council"), ("cong", "us_house")):
        for num, o in sorted(((officials.get(office) or {}).get("districts") or {}).items()):
            if o.get("name"):
                out[f"{lk}|{int(num)}"] = [{"n": o["name"], "p": letter(o.get("party")),
                                            "u": o.get("official_url") or o.get("url") or ""}]
    return out


def fills(geom, who):
    """{layer: {fid: letters}} for every district of every filled layer:
    its sitting members' parties, "" where nobody sits."""
    return {lk: {fid: letters(p["p"] for p in who.get(f"{lk}|{fid}", []))
                 for fid in sorted(geom["layers"][lk]["f"])}
            for lk in FILLED}


# ---------------------------------------------------------- ward label points ---

def arcs_of(geom):
    out = []
    for a in geom["arcs"]:
        p = [(a[0], a[1])]
        for i in range(2, len(a), 2):
            p.append((p[-1][0] + a[i], p[-1][1] + a[i + 1]))
        out.append(p)
    return out


def rings_of(geom, arcs, lk, fid):
    rings = []
    for refs in geom["layers"][lk]["f"][fid]["r"]:
        pts = []
        for r in refs:
            a = arcs[r] if r >= 0 else arcs[~r][::-1]
            pts.extend(a if not pts else a[1:])
        rings.append(pts)
    return rings


def inside(x, y, rings):
    c = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
    return c


def edge_dist(x, y, rings):
    best = float("inf")
    for ring in rings:
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            dx, dy = bx - ax, by - ay
            L = dx * dx + dy * dy
            t = 0 if L == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L))
            best = min(best, (ax + t * dx - x) ** 2 + (ay + t * dy - y) ** 2)
    return math.sqrt(best)


def box(rings):
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return [min(xs), min(ys), max(xs), max(ys)]


def ward_groups(geom, places, cities):
    """{city: [{d: base district, w: [wards], l: [x, y], b: [x0, y0, x1, y1]}]}.

    A city's wards, grouped by the 2022 State House district each lies in:
    57 of the 61 city-ward districts hold one ward, four hold several wards
    of one small city ("Wards 1, 3-6", Belknap 5). Where the district lies in
    the city alone its own label point and box are the ward's. Where it runs
    on into other towns (Dover Ward 4 with Lee and Madbury; Rochester Ward 5
    with Milton) the ward's part is the district's area inside the city: its
    name is drawn at the point of that part farthest from both edges, and
    must fit in that part's box. Wards come from the 2022 districts, never
    from the 2017 ward file (DISTRICT_MAP.md, section 1)."""
    arcs = arcs_of(geom)
    in_district = {}
    for t, p in places.items():
        for w in p["w"].values():
            in_district.setdefault(w[0], set()).add(t)
    out = {}
    for t in sorted(places):
        wards = [w for w in places[t]["w"] if w != "0"]
        if not wards:
            continue
        by = {}
        for w in wards:
            by.setdefault(places[t]["w"][w][0], []).append(w)
        groups = []
        for fid in sorted(by, key=lambda f: min(int(w) for w in by[f])):
            f = geom["layers"]["base"]["f"][fid]
            ws = sorted(by[fid], key=int)
            if in_district[fid] == {t}:
                groups.append({"d": fid, "w": ws, "l": f["l"],
                               "b": box(rings_of(geom, arcs, "base", fid))})
                continue
            dr, tr = rings_of(geom, arcs, "base", fid), rings_of(geom, arcs, "towns", t)
            a, b = box(dr), box(tr)
            x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
            G, pts = 36, []
            for i in range(1, G):
                for j in range(1, G):
                    x, y = x0 + (x1 - x0) * i / G, y0 + (y1 - y0) * j / G
                    if inside(x, y, dr) and inside(x, y, tr):
                        pts.append((x, y))
            if not pts:
                groups.append({"d": fid, "w": ws, "l": f["l"], "b": a})
                continue
            best = max(pts, key=lambda p: min(edge_dist(p[0], p[1], dr),
                                              edge_dist(p[0], p[1], tr)))
            cell = max(x1 - x0, y1 - y0) / G
            groups.append({"d": fid, "w": ws, "l": [round(best[0]), round(best[1])],
                           "b": [math.floor(min(p[0] for p in pts) - cell),
                                 math.floor(min(p[1] for p in pts) - cell),
                                 math.ceil(max(p[0] for p in pts) + cell),
                                 math.ceil(max(p[1] for p in pts) + cell)]})
        out[t] = groups
    return out


# --------------------------------------------------------------- the file ---

def build(geom_bytes, districts, legislators, officials):
    """site/district_map.json, as a dict."""
    geom = json.loads(geom_bytes)
    places = places_table(districts)
    missing = sorted(set(places) - set(geom["layers"]["towns"]["f"]))
    if missing:
        raise SystemExit(f"towns the geometry does not draw: {', '.join(missing[:8])} "
                         "(run src/towns/build_district_geometry.py)")
    legs = legislators if isinstance(legislators, list) else list(legislators.values())
    who = who_sits(legs, officials, places)
    cities = sorted(t for t in places if slug(t) in town_boards.CITIES)
    return {
        "_what": ("The district map's data: NH GRANIT's 2022 boundaries "
                  "(generated/district_geometry.json), every town and ward and the "
                  "districts it votes in, who sits for each district and the party "
                  "it is filled with. Written by src/pages/build_district_map.py "
                  "every night. Boundaries: NH GRANIT, University of New Hampshire "
                  "(2022). Not for legal use."),
        "_geometry": hashlib.sha256(geom_bytes).hexdigest(),
        "w": geom["w"], "h": geom["h"], "arcs": geom["arcs"], "layers": geom["layers"],
        "places": places,
        "cities": cities,
        "wards": ward_groups(geom, places, cities),
        "seats": seats_of(districts),
        "who": who,
        "fill": fills(geom, who),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--site", default="site")
    ap.add_argument("--geometry", default=GEOMETRY)
    ap.add_argument("--officials", default="corrections/officials.json")
    a = ap.parse_args()
    site = Path(a.site)

    def read(p):
        return json.loads(Path(p).read_text(encoding="utf-8"))
    geom_bytes = Path(a.geometry).read_bytes()
    data = build(geom_bytes, read(site / "districts.json"),
                 read(site / "legislators.json"), read(a.officials))
    # A district every seat of which is vacant is drawn hatched, and a site
    # whose every district were so would be a roster that failed to load:
    # silence is not success.
    filled = sum(1 for lk in ("base", "senate") for v in data["fill"][lk].values() if v)
    if not filled:
        raise SystemExit("no State House or Senate district has a sitting member: "
                         "is site/legislators.json the roster?")
    out = site / "district_map.json"
    out.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True) + "\n",
                   encoding="utf-8")
    for src in (SCRIPT, STYLE):
        shutil.copyfile(src, site / Path(src).name)
    vac = {lk: sum(1 for v in data["fill"][lk].values() if not v) for lk in FILLED}
    print(f"  {out}: {out.stat().st_size:,} bytes; "
          f"{len(data['places'])} places, {sum(len(g) for g in data['wards'].values())} "
          f"ward groups in {len(data['wards'])} cities; every seat vacant in "
          + ", ".join(f"{n} {lk}" for lk, n in vac.items()))
    print(f"  copied {SCRIPT} and {STYLE} into {site}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
