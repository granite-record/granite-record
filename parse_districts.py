#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Turn the Senate and Executive Council district lists into a town lookup.

    python3 parse_districts.py --dir districts --out site/districts.json

The General Court's data files carry House districts only, so town lookup
covered representatives and nothing else. These lists close that gap, and add
Executive Council districts, which almost nothing indexes at all despite the
Council approving contracts, judicial nominations and pardons.

Source format, one district per pair of lines:

    District 4
    Barrington, Dover-Ward 1, Dover-Ward 2, ... , Rollinsford, ...

Cities appear split by ward, "Dover-Ward 1", while HouseDistricts.txt records
the town and ward in separate fields. Both are normalised to (town, ward) so
the three sources line up. Unincorporated places -- "Bean's Purchase",
"Hale's Location", "Second College Gt" -- have no wards and pass through.

These are redistricted every ten years. Editing the text files and re-running
is the whole update.
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

HEAD = re.compile(r"^\s*District\s+(\d+)\s*$", re.I)

# "Rockingham County District 31 (2 seats) (Floterial)"
HOUSE_HEAD = re.compile(
    r"^\s*(?P<county>[A-Za-z ]+?)\s+County\s+District\s+(?P<num>\d+)\s*"
    r"(?:\((?P<seats>\d+)\s*seats?\)\s*)?"
    r"(?:\((?P<flot>Floterial)\)\s*)?$", re.I)
WARD = re.compile(r"^(?P<town>.+?)[-\u2013]\s*Ward\s*(?P<ward>\d+)\s*$", re.I)


def split_town(s):
    """'Dover-Ward 1' -> ('Dover', '1'); 'Bath' -> ('Bath', '0')."""
    s = " ".join(s.split())
    m = WARD.match(s)
    return (m.group("town").strip(), m.group("ward")) if m else (s, "0")


def parse_house(path):
    """House districts, including floterial ones.

    HouseDistricts.txt omits floterial districts entirely, which is why eight
    sitting members matched no town at all. A floterial overlays several towns
    that already have their own district and elects additional members across
    the combined population, so a resident is genuinely in two House districts
    at once and this file has to represent both.
    """
    out, cur = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        h = HOUSE_HEAD.match(line)
        if h:
            cur = (h.group("county").strip(), h.group("num"))
            out[cur] = {"county": cur[0], "district": cur[1],
                        "seats": int(h.group("seats") or 1),
                        "floterial": bool(h.group("flot")), "towns": []}
            continue
        if cur is None:
            continue
        for piece in line.split(","):
            piece = piece.strip()
            if piece:
                out[cur]["towns"].append(split_town(piece))
    return out


def parse(path):
    out, cur = defaultdict(list), None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        h = HEAD.match(line)
        if h:
            cur = h.group(1)
            continue
        if cur is None:
            continue
        for piece in line.split(","):
            piece = piece.strip()
            if piece:
                out[cur].append(split_town(piece))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="districts")
    ap.add_argument("--towns", default="site/towns.json",
                    help="from build_data.py, used to check the names line up")
    ap.add_argument("--out", default="site/districts.json")
    a = ap.parse_args()

    d = Path(a.dir)
    combined = defaultdict(dict)
    counts = {}
    for kind, fname in (("senate", "senate.txt"), ("council", "council.txt"),
                        ("congress", "congress.txt")):
        p = d / fname
        if not p.exists():
            print(f"missing: {p}")
            continue
        districts = parse(p)
        counts[kind] = len(districts)
        n = 0
        for num, entries in districts.items():
            for town, ward in entries:
                combined[town].setdefault(ward, {})[kind] = int(num)
                n += 1
        print(f"{kind}: {len(districts)} districts, {n:,} town-ward entries")

    # Do the names match the House district file? A silent mismatch would mean
    # a town looks up its representatives but not its senator.
    tp = Path(a.towns)
    if tp.exists():
        house = json.loads(tp.read_text(encoding="utf-8"))
        hnames = set(house)
        mine = set(combined)
        missing = sorted(hnames - mine)
        extra = sorted(mine - hnames)
        print(f"\ntowns in the House file: {len(hnames)}; in these lists: {len(mine)}")
        if missing:
            print(f"  {len(missing)} in the House file but not here: "
                  f"{', '.join(missing[:8])}{' …' if len(missing) > 8 else ''}")
        if extra:
            print(f"  {len(extra)} here but not in the House file: "
                  f"{', '.join(extra[:8])}{' …' if len(extra) > 8 else ''}")
        if not missing and not extra:
            print("  names line up exactly")

    # House districts, from the fuller list rather than HouseDistricts.txt.
    hp = d / "house.txt"
    if hp.exists():
        hd = parse_house(hp)
        flot = sum(1 for v in hd.values() if v["floterial"])
        seats = sum(v["seats"] for v in hd.values())
        print(f"\nhouse: {len(hd)} districts ({flot} floterial), "
              f"{seats} seats total")
        if seats != 400:
            print(f"  seat total is {seats}, not the constitutional 400 "
                  "\u2014 worth checking the source list")
        for (county, num), rec in hd.items():
            for town, ward in rec["towns"]:
                combined[town].setdefault(ward, {}).setdefault("house", []).append(
                    {"county": county, "district": int(num),
                     "seats": rec["seats"], "floterial": rec["floterial"]})
        for town, wards in combined.items():
            for w, v in wards.items():
                if "house" in v:
                    v["house"].sort(key=lambda x: (x["floterial"], x["district"]))
        nohouse = [f"{t}{'' if w=='0' else ' ward '+w}"
                   for t, ws in combined.items() for w, v in ws.items()
                   if "house" not in v]
        if nohouse:
            print(f"  {len(nohouse)} town-wards with no House district: "
                  f"{', '.join(nohouse[:6])}")

    kinds = set(counts)
    gaps = defaultdict(list)
    for town, wards in combined.items():
        for w, v in wards.items():
            for k in kinds:
                if k not in v:
                    gaps[k].append(f"{town}{'' if w=='0' else ' ward '+w}")
    if gaps:
        print("\ntown-wards missing a district (each should have all three):")
        for k, v in gaps.items():
            print(f"  {k}: {len(v)} — {', '.join(v[:6])}"
                  f"{' …' if len(v) > 6 else ''}")
    else:
        print("\nevery town-ward has a senate, council and congressional district")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(combined, indent=2, sort_keys=True),
                           encoding="utf-8")
    wards = sum(len(v) for v in combined.values())
    print(f"\n{len(combined):,} towns, {wards:,} town-ward combinations -> {a.out}")

    for t in ("Dover", "Manchester", "Bath"):
        if t in combined:
            print(f"  {t}: " + "; ".join(
                f"ward {w or '-'} senate {v.get('senate','?')} "
                f"council {v.get('council','?')} congress {v.get('congress','?')}"
                for w, v in sorted(combined[t].items())[:3]))


if __name__ == "__main__":
    main()
