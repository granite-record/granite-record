#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.1
"""
The district map's geometry: NH GRANIT's six layers, made small enough to draw.

    python3 src/towns/build_district_geometry.py --report   # say what it would write, write nothing
    python3 src/towns/build_district_geometry.py            # -> generated/district_geometry.json
    python3 src/towns/build_district_geometry.py --gis D:/nh/records/sources/gis

Run by a person when a source changes, like every other reader in this
folder: the GIS zips are on the laptop only (records/sources/gis/, 4.2 MB, in
neither git nor the kit; parse_granit.py says where they come from), and the
boundaries change once a decade. What it writes is committed, so the nightly
build carries it in git and the diff is the review. preflight holds the file
to its inputs ("the district map's geometry is as fresh as its inputs"): the
zips' digests where the zips are on the disk, this file's own stamp always,
and the district codes and town names of records/districts/ always.

WHAT IT WRITES. One file, every layer on shared arcs, in 100-ft integer units
of NAD83 / New Hampshire (ftUS), EPSG:3437, y down -- the state drawn in its
own State Plane, so no reprojection and no pyproj (parse_granit.py, PROJECTION):

    arcs        each boundary once, delta-encoded [x0, y0, dx1, dy1, ...]
    layers      base (164 State House base districts), float (39 floterials),
                senate (24), exec (5 Executive Council), cong (2 US House),
                county (10), towns (259 places): each feature a list of rings
                of arc indices (~i is arc i reversed) and a label point "l",
                the interior point farthest from the feature's edges; and "m",
                the arcs the layer draws as its borders
    _inputs     the sha256 of every zip it read; _builder, this file's stamp

THE METHOD is the design's (private/design/DISTRICT_MAP.md, section 3), ported
from its prototype's scratch scripts: vertices snapped to a 20-ft grid, which
makes the layers' shared borders coincide exactly; one topology across all
layers (a vertex where more than two directions meet is a junction, rings are
cut there into arcs, each arc stored once); Douglas-Peucker at 100 ft on each
arc with its ends fixed, so neighbours are simplified identically and never
gap or overlap; then 100-ft units. Two things the prototype did not do, both
from its own notes: a town is its wards DISSOLVED (the 2017 ward lines were
drawn inside eight cities whose wards have since moved; the design's section
1 says the ward file supplies town outlines and counties only), and so is a
county (its towns), so their lines and their label points are the place's
own; the arcs nothing then uses are dropped.

THE JOINS. House codes by parse_granit.split_code ("BE1" beside "HI03");
Senate, Council and US House by number; towns by name, through ALIAS, the
eight spellings NHPolitDists writes differently from records/districts/ (and
Derry, which that 2017 file still divides into four wards). Every name on
either side must meet the other, or this stops and names them.

Asks nobody: it reads the zips on the disk and records/districts/.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import gzip
import hashlib
import json
import math
import re
import struct
import zipfile

import parse_districts
import parse_granit

ROOT = _paths.ROOT
OUT = ROOT / "generated" / "district_geometry.json"
DISTRICTS = ROOT / "records" / "districts"

GRID = 20      # feet: the grid every vertex is snapped to
TOL = 100      # feet: Douglas-Peucker tolerance, per arc
UNIT = 100     # feet: one unit of the file

# The extent every layer shares, in feet (parse_granit's survey: x 745474 to
# 1267015, y 72030 to 1023284).
X0, X1, Y0, Y1 = 745474.0, 1267015.0, 72030.0, 1023284.0

# zip -> the field carrying each feature's code. NHPolitDists is read for
# NAME and COUNTY, its places and their counties.
ZIPS = {
    "exec": ("NHExecDistricts2022.zip", "ExecCo2022"),
    "senate": ("NHSenateDistricts2022.zip", "Senate2022"),
    "cong": ("CongDistricts2022.zip", "Cong2022"),
    "base": ("NHHouseDistricts2022_Base.zip", "BaseHse22"),
    "float": ("NHHouseDistricts2022_Float.zip", "FloatHse22"),
    "towns": ("NHPolitDists.zip", "NAME"),
}
LAYERS = ("base", "float", "senate", "exec", "cong", "county", "towns")

# NHPolitDists' spelling -> records/districts/'s (DISTRICT_MAP.md, section 1).
ALIAS = {"Atkinson & Gilmanton": "Atk. & Gil. Academy Grant",
         "Second College Grant": "Second College Gt",
         "Wentworth's Location": "Wentworth's Loc.",
         "Low & Burbanks Grant": "Low & Burbank's Grant",
         "Thompson & Meserve": "Thompson & Mes's Purchase",
         "Chandler's Purchase": "Chandler's Pur.",
         "Crawford's Purchase": "Crawford's Pur."}

CODE = {v: k for k, v in parse_granit.COUNTY.items()}


def stamp():
    """This file's own GRANITE_VERSION, which the output records."""
    m = re.search(r"GRANITE_VERSION:\s*(\S+)",
                  Path(__file__).read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


# ------------------------------------------------------------- shapefiles ---

def read_shp(data):
    """A .shp's polygons: one list of rings per record, each ring a list of
    (x, y) in feet. Type 5 only; a null record is an empty list."""
    shapes, pos = [], 100
    while pos + 8 <= len(data):
        _, clen = struct.unpack(">II", data[pos:pos + 8])
        rec = data[pos + 8:pos + 8 + clen * 2]
        pos += 8 + clen * 2
        if struct.unpack("<i", rec[:4])[0] == 0:
            shapes.append([])
            continue
        nparts, npts = struct.unpack("<ii", rec[36:44])
        parts = list(struct.unpack(f"<{nparts}i", rec[44:44 + 4 * nparts]))
        off = 44 + 4 * nparts
        pts = struct.unpack(f"<{2 * npts}d", rec[off:off + 16 * npts])
        xy = list(zip(pts[0::2], pts[1::2]))
        shapes.append([xy[s:(parts[i + 1] if i + 1 < nparts else npts)]
                       for i, s in enumerate(parts)])
    return shapes


def read_zip(path):
    """(rows, shapes) of one zip, which must hold as many of each."""
    z = zipfile.ZipFile(path)
    names = z.namelist()
    dbf = next(n for n in names if n.lower().endswith(".dbf"))
    shp = next(n for n in names if n.lower().endswith(".shp"))
    _fields, rows = parse_granit.read_dbf(z.read(dbf))
    shapes = read_shp(z.read(shp))
    if len(rows) != len(shapes):
        raise SystemExit(f"{path.name}: {len(rows)} records but {len(shapes)} shapes")
    return rows, shapes


def house_code(v):
    """'BE1', 'HI03' -> 'BE1', 'HI3'; None for a blank (the floterial file's
    rest of the state)."""
    sc = parse_granit.split_code(v)
    return f"{CODE[sc[0]]}{sc[1]}" if sc else None


def features(gis):
    """{layer: {fid: [rings in feet]}} for the six layers and the counties,
    and {town: county}."""
    out = {}
    for lk, (name, field) in ZIPS.items():
        rows, shapes = read_zip(gis / name)
        f = collections.defaultdict(list)
        county_of = {}
        for r, s in zip(rows, shapes):
            raw = r[field].strip()
            if not raw:
                continue
            if lk in ("base", "float"):
                fid = house_code(raw)
                if fid is None:
                    raise SystemExit(f"{name}: a code split_code cannot read: {raw!r}")
            elif lk == "towns":
                fid = ALIAS.get(raw, raw)
                county_of[fid] = r["COUNTY"].strip()
            else:
                fid = str(int(raw))
            f[fid].extend(s)
        out[lk] = dict(f)
        if lk == "towns":
            towns_county = county_of
    c = collections.defaultdict(list)
    for t, rings in out["towns"].items():
        c[towns_county[t]].extend(rings)
    out["county"] = dict(c)
    return out, towns_county


# --------------------------------------------------------------- topology ---

def quantize(rings):
    """Feet -> integer cells of GRID feet, y flipped; repeats dropped."""
    out = []
    for r in rings:
        pts = []
        for x, y in r:
            p = (int(round((x - X0) / GRID)), int(round((Y1 - y) / GRID)))
            if not pts or pts[-1] != p:
                pts.append(p)
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts.pop()
        if len(pts) >= 3:
            out.append(pts)
    return out


def topology(feats):
    """Rings -> shared arcs. Returns the arcs (point lists) and
    {layer: {fid: [ring as signed arc indices]}} (~i is arc i reversed)."""
    neigh = collections.defaultdict(set)
    every = []
    for lk in LAYERS:
        for fid in sorted(feats[lk]):
            for r in feats[lk][fid]:
                n = len(r)
                for i, p in enumerate(r):
                    neigh[p].add(r[i - 1])
                    neigh[p].add(r[(i + 1) % n])
                every.append((lk, fid, r))
    junction = {p for p, s in neigh.items() if len(s) > 2}
    arcs, index = [], {}

    def arc_id(seq):
        key = tuple(seq)
        if key in index:
            return index[key]
        rkey = key[::-1]
        if rkey in index:
            return ~index[rkey]
        arcs.append(list(seq))
        index[key] = len(arcs) - 1
        return len(arcs) - 1

    topo = {lk: collections.defaultdict(list) for lk in LAYERS}
    for lk, fid, r in every:
        n = len(r)
        js = [i for i, p in enumerate(r) if p in junction]
        if not js:
            # A ring that touches nothing: anchored at its smallest point, so
            # the same island in two layers is the same arc.
            k = min(range(n), key=lambda i: r[i])
            refs = [arc_id(r[k:] + r[:k] + [r[k]])]
        else:
            refs = [arc_id([r[i % n] for i in range(a, b + 1)])
                    for a, b in zip(js, js[1:] + [js[0] + n])]
        topo[lk][fid].append(refs)
    return arcs, topo


def dissolve(rings, arcs):
    """One feature's rings -> the rings of its outline: the arcs it uses once,
    stitched end to start. An arc a feature uses twice lies between two of its
    own parts (two wards of one town, two towns of one county) and goes."""
    use = collections.Counter(r if r >= 0 else ~r for ring in rings for r in ring)
    over = [a for a, n in use.items() if n > 2]
    if over:
        raise SystemExit(f"an arc used {use[over[0]]} times by one feature: cannot dissolve")
    edge = [r for ring in rings for r in ring if use[r if r >= 0 else ~r] == 1]

    def ends(r):
        a = arcs[r] if r >= 0 else arcs[~r][::-1]
        return a[0], a[-1]
    starts = collections.defaultdict(list)
    for r in edge:
        starts[ends(r)[0]].append(r)
    left, out = set(edge), []
    for first in edge:
        if first not in left:
            continue
        ring, cur = [first], first
        left.discard(first)
        home = ends(first)[0]
        while ends(cur)[1] != home:
            nxt = next((r for r in starts[ends(cur)[1]] if r in left), None)
            if nxt is None:
                raise SystemExit("an outline that does not close: cannot dissolve")
            ring.append(nxt)
            left.discard(nxt)
            cur = nxt
        out.append(ring)
    return out


def dp(pts, tol):
    """Douglas-Peucker on an open polyline, both ends kept."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack, t2 = [(0, len(pts) - 1)], tol * tol
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = pts[a], pts[b]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            if L == 0:
                d = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
                d = (ax + t * dx - px) ** 2 + (ay + t * dy - py) ** 2
            if d > best:
                best, bi = d, i
        if best > t2:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def simplify(arcs, tol):
    out = []
    for a in arcs:
        if a[0] == a[-1]:
            # a closed ring: cut at the point farthest from its anchor
            far = max(range(len(a)), key=lambda i: (a[i][0] - a[0][0]) ** 2
                      + (a[i][1] - a[0][1]) ** 2)
            out.append(dp(a[:far + 1], tol)[:-1] + dp(a[far:], tol))
        else:
            out.append(dp(a, tol))
    return out


def to_units(pts):
    s = UNIT / GRID
    out = []
    for x, y in pts:
        p = (int(round(x / s)), int(round(y / s)))
        if not out or out[-1] != p:
            out.append(p)
    return out


def ring_points(refs, arcs):
    pts = []
    for r in refs:
        a = arcs[r] if r >= 0 else arcs[~r][::-1]
        pts.extend(a if not pts else a[1:])
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def area2(pts):
    return sum(x1 * y2 - x2 * y1
               for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))


# ------------------------------------------------------------ label point ---

def _inside(p, rings):
    x, y = p
    c = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
    return c


def _edge_dist(p, edges):
    px, py = p
    best = float("inf")
    for (ax, ay), (bx, by) in edges:
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
        d = (ax + t * dx - px) ** 2 + (ay + t * dy - py) ** 2
        if d < best:
            best = d
    return math.sqrt(best)


def label_point(rings):
    """The point of the feature farthest from its edges, near enough for a
    label: a grid over its largest ring, then two finer grids about the best
    cell. Inside by even-odd over every ring, so a hole is outside."""
    big = max(rings, key=lambda r: abs(area2(r)))
    xs, ys = [p[0] for p in big], [p[1] for p in big]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    near = [r for r in rings if max(p[0] for p in r) >= x0 and min(p[0] for p in r) <= x1
            and max(p[1] for p in r) >= y0 and min(p[1] for p in r) <= y1]
    edges = [(a, b) for r in near for a, b in zip(r, r[1:] + r[:1])]
    best, bp = -1.0, ((x0 + x1) / 2, (y0 + y1) / 2)
    for step in (16, 8, 8):
        w, h = (x1 - x0) / step, (y1 - y0) / step
        for i in range(step + 1):
            for j in range(step + 1):
                p = (x0 + i * w, y0 + j * h)
                if not _inside(p, near):
                    continue
                d = _edge_dist(p, edges)
                if d > best:
                    best, bp = d, p
        x0, x1, y0, y1 = bp[0] - w * 2, bp[0] + w * 2, bp[1] - h * 2, bp[1] + h * 2
    return [int(round(bp[0])), int(round(bp[1]))]


# ---------------------------------------------------------------- the file ---

def record_names():
    """What records/districts/ calls every district and place: {layer: set}."""
    house = parse_districts.parse_house(DISTRICTS / "house.txt")
    names = {"base": set(), "float": set(), "towns": set(), "county": set()}
    for (county, num), v in house.items():
        names["float" if v["floterial"] else "base"].add(f"{CODE[county]}{int(num)}")
        names["county"].add(county)
        for town, _ward in v["towns"]:
            names["towns"].add(town)
    for lk, fname in (("senate", "senate.txt"), ("exec", "council.txt"),
                      ("cong", "congress.txt")):
        names[lk] = {str(int(k)) for k in parse_districts.parse(DISTRICTS / fname)}
    return names


def build(gis):
    """The geometry as a dict, and what it says about itself."""
    zips = {ZIPS[lk][0] for lk in ZIPS}
    absent = sorted(z for z in zips if not (gis / z).is_file())
    if absent:
        raise SystemExit(f"not in {gis}: {', '.join(absent)} "
                         f"(parse_granit.py says where they come from)")
    feats, _county_of = features(gis)

    # Every name on either side must meet the other.
    rec = record_names()
    for lk in LAYERS:
        ours, theirs = set(feats[lk]), rec[lk]
        if ours != theirs:
            raise SystemExit(f"{lk}: only in GRANIT {sorted(ours - theirs)[:8]}; "
                             f"only in records/districts {sorted(theirs - ours)[:8]}")

    q = {lk: {fid: quantize(r) for fid, r in feats[lk].items()} for lk in LAYERS}
    arcs, topo = topology(q)
    for lk in ("towns", "county"):
        for fid in topo[lk]:
            topo[lk][fid] = dissolve(topo[lk][fid], arcs)
    sarcs = simplify(arcs, TOL / GRID)
    uarcs = [to_units(a) for a in sarcs]

    # Rings that simplification collapsed (GIS slivers) go; a feature that
    # loses every ring stops the build.
    kept = {}
    for lk in LAYERS:
        kept[lk] = {}
        for fid in sorted(topo[lk]):
            rr = [(refs, ring_points(refs, uarcs)) for refs in topo[lk][fid]]
            rr = [(refs, pts) for refs, pts in rr if len(pts) >= 3 and area2(pts) != 0]
            if not rr:
                raise SystemExit(f"{lk} {fid}: every ring collapsed at {TOL} ft")
            kept[lk][fid] = rr

    # Only the arcs something still uses, renumbered in their first order.
    used = sorted({r if r >= 0 else ~r for lk in LAYERS for rr in kept[lk].values()
                   for refs, _ in rr for r in refs})
    new = {old: i for i, old in enumerate(used)}

    def renum(r):
        return new[r] if r >= 0 else ~new[~r]

    jarcs = []
    for old in used:
        s = uarcs[old]
        if len(s) == 1:
            s = s + s
        d = [s[0][0], s[0][1]]
        for (px, py), (qx, qy) in zip(s, s[1:]):
            d += [qx - px, qy - py]
        jarcs.append(d)

    layers = {}
    for lk in LAYERS:
        fs, use = {}, collections.defaultdict(set)
        for fid, rr in kept[lk].items():
            refs = [[renum(r) for r in refs] for refs, _ in rr]
            fs[fid] = {"r": refs, "l": label_point([pts for _, pts in rr])}
            for ring in refs:
                for r in ring:
                    use[r if r >= 0 else ~r].add(fid)
        # The arcs a layer draws as its borders: used by two features, or by
        # one (the state's edge, a coast, a lake).
        layers[lk] = {"f": fs, "m": sorted(use)}

    digest = {z: hashlib.sha256((gis / z).read_bytes()).hexdigest() for z in sorted(zips)}
    out = {
        "_what": ("NH GRANIT's 2022 district boundaries and its town outlines, made "
                  f"small for the district map: shared arcs simplified at {TOL} ft "
                  f"(Douglas-Peucker, on a {GRID}-ft grid), in {UNIT}-ft integer units of "
                  "NAD83 / New Hampshire (ftUS), EPSG:3437, y down. Written by "
                  "src/towns/build_district_geometry.py; never edited by hand. "
                  "Not for legal use: the Secretary of State's published definitions "
                  "are the legal text."),
        "_source": parse_granit.BASE_URL,
        "_licence": parse_granit.LICENCE,
        "_inputs": digest,
        "_builder": stamp(),
        "w": int(round((X1 - X0) / UNIT)) + 1,
        "h": int(round((Y1 - Y0) / UNIT)) + 1,
        "arcs": jarcs,
        "layers": layers,
    }
    return out


def dumps(geom):
    """The file's bytes: compact, keys sorted, so two runs on the same zips
    write the same file."""
    return (json.dumps(geom, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--gis", default=str(parse_granit.GIS),
                    help="the folder holding the six GRANIT zips")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--report", action="store_true", help="write nothing")
    a = ap.parse_args()

    geom = build(Path(a.gis))
    b = dumps(geom)
    print(f"  {len(geom['arcs']):,} arcs, "
          f"{sum(len(x) // 2 for x in geom['arcs']):,} vertices")
    for lk in LAYERS:
        L = geom["layers"][lk]
        print(f"  {lk:7s} {len(L['f']):4d} features, {len(L['m']):5d} border arcs")
    print(f"  {len(b):,} bytes, {len(gzip.compress(b, 9)):,} gzipped")
    if a.report:
        print("  --report: nothing written")
        return 0
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b)
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
