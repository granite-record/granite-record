#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-25.1
"""
Each town's transfer station or recycling centre, where the state's list of
permitted solid-waste facilities says a public body runs one in it.

    python3 src/towns/parse_transfer_stations.py --report    # say what it found, write nothing
    python3 src/towns/parse_transfer_stations.py             # -> collected/transfer_stations.json

WHY (the person, 24 October 2026: "gather more useful information for the
town pages like ... transfer station addresses and hours if possible", and
that evening: "Are you able to retrieve the other info like the transfer
stations so those cards can be included?"). The Town Services tab's third
card, after the town office and the library.

WHAT IT READS, saved by src/fetch/other/town_directory.py and touching no
network here:

  des_solid_waste     the Department of Environmental Services' map layer of
                      solid waste facilities: each one's DES id, class,
                      status, permit, name, street, town and coordinates.
  des_facility_pages  the page DES's OneStop keeps for each facility the
                      layer lists as an operating collection, storage and
                      transfer site: who holds its permit, who owns and runs
                      it, and whether its owner is PUBLIC or PRIVATE. Each
                      field is a named item of the page (P60_OWNER_TYPE and
                      the rest), read as such, not off its words.

WHICH FACILITIES. Those the layer lists as OPERATING, of the two classes a
resident's drop-off falls under -- C/S/T, and C/S/T - LIMITED PUBLIC TS --
whose page says their owner is PUBLIC. Not the other C/S/T classes (asbestos,
scrap metal, truck transfer stations, select recyclables, a materials
recovery facility), and not a privately owned one however its name reads: no
name settles it. Belmont's "Casella Waste Management, Belmont Transfer
Station" is a company's, and "Raymond A. LaRoche Sr. Transfer Station and
Recycling Center" is Durham's, named for a person; DES's own field says which
is which, so a name is never read for it.

WHERE. In the town DES files it under (SWF_CITY), matched to the site's
towns by the clerks' rule (parse_clerks_csv.match_town), and the page's own
street address must end in the same town. A station whose DES name is
nothing but towns' names before its facility words -- "Campton Thornton
Transfer Station", "Lincoln Woodstock Recycling Center", "Bartlett Jackson
Harts Location Transfer Station" -- is listed in each town it names as well,
since DES's name for it says it is theirs. A person's name that is also a
town's (Raymond, in Durham's) is not such a name, because the rest of it is
not towns.

WHAT IT DOES NOT KNOW, and the page does not claim. Which other towns share
a station: DES records none (BCEP's and Wilton's service areas are blank,
AVRRDD's lists four states), so Epsom's use of BCEP in Pittsfield waits for a
person's table. DES lists some stations as closed that run (the plan of 24
October 2026 named Hopkinton-Webster, Holderness, Loudon and Dover's
recycling centre), and a town with none listed draws no card rather than a
sentence saying it has none. Hours, stickers and what each takes are on the
towns' websites, which the card points to.

WHAT IT KEEPS, and what not: each station's name, street and town, its
permit, its DES id and page, who holds the permit, the owner and service
types, and its coordinates. Not the contact person, nor their phone or
e-mail: a person's details, which DES's page carries for whoever opens it.

THE NAMES. DES types them in capitals; facility_case writes them for the
page, keeping the acronyms (BCEP, AVRRDD, HHW) and lowering the small words,
and the layer's own words are kept beside them under `raw`.

A FLOOR. A layer cut short, or pages that were not read, still parse, and
would write a town page with no transfer station. It refuses to write under
town_sources.FLOORS["des_swf"] unless a person passes --allow-shrink.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import html
import json
import re

import parse_clerks_csv
import town_sources

ROOT = _paths.ROOT
STORE = ROOT / "records" / "sources" / "directory"
LAYER = STORE / "des_solid_waste" / "solid_waste_facilities.json"
PAGES = STORE / "des_facility_pages"
OUT = ROOT / "collected" / "transfer_stations.json"
SOURCE_URL = "https://www.des.nh.gov/waste/solid-waste"

# The layer's classes a resident's drop-off falls under. DES's other C/S/T
# classes are a business's: asbestos, scrap metal, a hauler's truck transfer
# station, select recyclables, a materials recovery facility.
KINDS = {"C/S/T": "transfer", "C/S/T - LIMITED PUBLIC TS": "limited public"}
OPERATING = "OPERATING"
PUBLIC = "PUBLIC"

# The words that begin what a facility is, after whose name it is: the name
# before the first of them is the place's. TOWN OF is read off before it.
FACILITY_WORDS = {"TRANSFER", "RECYCLING", "RECYCLE", "SOLID", "MSW", "DROP", "MUNICIPAL",
                  "RESOURCE", "REFUSE", "DISPOSAL", "BRUSH", "STUMP", "HHW", "FOAM",
                  "PUBLIC", "WASTE", "MATERIALS", "RECOVERY", "FACILITY", "CENTER"}

# Kept in capitals: the facility names' own acronyms, beside the clerks' list.
ACRONYMS = {"AVRRDD", "BCEP", "BWPOA", "DPW", "GDS", "HHW", "II", "III", "LLC", "MRF", "MSW",
            "NCES", "NH", "US"}
SMALL = {"AND", "AT", "BY", "FOR", "IN", "OF", "ON", "THE", "TO"}


def _word(w, first):
    """One word of a DES name in the page's case."""
    bare = re.sub(r"[^A-Z0-9']", "", w.upper())
    if bare in ACRONYMS:
        return w.upper()
    if bare in SMALL and not first:
        return w.lower()
    if re.fullmatch(r"\d+[A-Z]?", bare) or re.fullmatch(r"[A-Z]\.?", w.upper()):
        return w.upper()
    # "JOHN'S" is John's, "TRI" of "TRI-TOWN" Tri, "(CASELLA" (Casella: the
    # first letter is raised, not the first character.
    m = re.search(r"[A-Za-z]", w)
    if not m:
        return w
    return w[:m.start()] + w[m.start()].upper() + w[m.start() + 1:].lower()


def facility_case(s):
    """A DES name or street in the case the page writes: "TOWN OF MILTON
    TRANSFER STATION/RECYCLING CENTER" is "Town of Milton Transfer
    Station/Recycling Center", "BCEP SOLID WASTE DISTRICT" keeps BCEP, "29
    DPW ROAD" keeps DPW and "NH RT 3A" its NH and 3A. Each part either side
    of a slash, hyphen or ampersand is a word of its own ("S&S")."""
    out = []
    for i, tok in enumerate((s or "").split()):
        parts = re.split(r"([/&-])", tok)
        out.append("".join(p if p in ("/", "&", "-") else _word(p, i == 0 and j == 0)
                           for j, p in enumerate(parts) if p != ""))
    return " ".join(out)


def page_items(text):
    """{item: value} for the named items of a facility's page: its P60_ items
    (P60_OWNER_TYPE: "PUBLIC"), each value unescaped and a <br> in it a
    newline."""
    out = {}
    for m in re.finditer(r'<input type="hidden" id="(P60_[A-Z0-9_]+)" name="\1" '
                         r'data-type="[^"]*" value="([^"]*)"', text):
        out[m.group(1)] = re.sub(r"<br\s*/?>", "\n", html.unescape(m.group(2))).strip()
    return out


def lid_of(url):
    """The DES id an ONESTOP_LINK names, as the page's file is named: "0000338"."""
    m = re.search(r"[?&]p60_swf_lid=(\d+)$", url or "")
    return m.group(1) if m else None


def read_on():
    """(the day the layer was saved, {page file: the day it was read}), from
    the fetcher's _meta.json files; None and {} where there is no record."""
    def meta(d):
        try:
            return json.loads((d / "_meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    layer = meta(LAYER.parent).get(LAYER.name) or {}
    pages = {k: str(v.get("read_at"))[:10] for k, v in meta(PAGES).items() if v.get("read_at")}
    return (str(layer["read_at"])[:10] if layer.get("read_at") else None), pages


def named_towns(name, towns):
    """The towns a shared station's DES name is made of: ["CAMPTON",
    "THORNTON"] for "CAMPTON THORNTON TRANSFER STATION & RECYCLING CENTER";
    [] where the words before its facility words are one town or not towns
    at all. Each town is matched as a whole run of words, the longest first,
    with the apostrophe that neither list keeps the same way set aside
    (parse_clerks_csv.match_town's reason)."""
    words = (name or "").upper().replace(",", " ").split()
    if words[:2] == ["TOWN", "OF"]:
        words = words[2:]
    head = []
    for w in words:
        if re.sub(r"[^A-Z]", "", w) in FACILITY_WORDS:
            break
        head.append(w)
    flat = {re.sub(r"['’.]", "", t): t for t in towns}
    found, i = [], 0
    while i < len(head):
        for j in range(len(head), i, -1):
            run = re.sub(r"['’.]", "", " ".join(head[i:j]))
            if run in flat:
                found.append(flat[run])
                i = j
                break
        else:
            return []
    return found if len(found) > 1 else []


def station(a, items, day):
    """One station's entry, from its layer record and its page's items."""
    street = facility_case(a.get("SWF_ADD_1") or "")
    also = facility_case(a.get("SWF_ADD_2") or "")
    return {"name": facility_case(a["SWF_NAME"]),
            "street": street,
            "also": also,
            "place": facility_case(a["SWF_CITY"]),
            "kind": KINDS[a["SWF_TYPE"]],
            "permit": a.get("SWF_PERMIT") or "",
            "des_id": items.get("P60_FACILITY_ID") or "",
            "page": a["ONESTOP_LINK"],
            "permittee": facility_case(items.get("P60_PERMITTEE_NAME") or ""),
            "operator": facility_case(items.get("P60_OPERATOR_NAME") or ""),
            "owner_type": (items.get("P60_OWNER_TYPE") or "").lower(),
            "service_type": (items.get("P60_SERVICE_TYPE") or "").lower(),
            "lat": a.get("SWF_LAT"),
            "lon": a.get("SWF_LONG"),
            "read_on": day,
            "raw": {"name": a["SWF_NAME"], "street": a.get("SWF_ADD_1") or "",
                    "also": a.get("SWF_ADD_2") or "", "city": a["SWF_CITY"],
                    "permittee": items.get("P60_PERMITTEE_NAME") or ""}}


def build(records, pages, towns, layer_day, page_days):
    """({town key: entry}, {reason: [what]}) -- `records` the layer's
    attributes, `pages` {DES id: the page's items}. The second says what was
    left out and why, and what was kept with a caveat, for the report."""
    data, left = {}, {}

    def leave(why, what):
        left.setdefault(why, []).append(what)

    for a in records:
        what = f"{a.get('SWF_NAME')} ({a.get('SWF_CITY')}, {a.get('SWF_PERMIT')})"
        if not (a.get("SWF_TYPE") or "").startswith("C/S/T") or a.get("SWF_STATUS") != OPERATING:
            continue
        if a["SWF_TYPE"] not in KINDS:
            leave(f"left out, a business's class: {a['SWF_TYPE']}", what)
            continue
        lid = lid_of(a.get("ONESTOP_LINK"))
        items = pages.get(lid)
        if items is None:
            leave("left out, its DES page is not on disk", what)
            continue
        if items.get("P60_FACILITY_ID") != lid or items.get("P60_PERMIT_NUMBER") != a.get("SWF_PERMIT"):
            leave("left out, its page is another facility's, or another permit's", what)
            continue
        if items.get("P60_FACILITY_STATUS") != OPERATING:
            leave(f"left out, its page says {items.get('P60_FACILITY_STATUS') or 'no status'}", what)
            continue
        if items.get("P60_OWNER_TYPE") != PUBLIC:
            leave(f"left out, owned {(items.get('P60_OWNER_TYPE') or 'by nobody named').lower()}", what)
            continue
        town = parse_clerks_csv.match_town(a.get("SWF_CITY") or "", towns)
        if town is None:
            leave("left out, its town is not one the site has", what)
            continue
        last = (items.get("P60_FACILITY_STREET_ADDRESS") or "").splitlines()[-1:] or [""]
        if last[0].strip().upper() != a["SWF_CITY"].strip().upper():
            leave(f"left out, its page puts it in {last[0] or 'no town'}", what)
            continue
        day = min(d for d in (layer_day, page_days.get(f"{lid}.html")) if d)
        s = station(a, items, day)
        shared = named_towns(a["SWF_NAME"], towns)
        if shared and town not in shared:
            leave("kept in its own town only: its name names towns, and not the one it is in",
                  what)
            shared = []
        for t in shared or [town]:
            key = parse_clerks_csv.slug(t)
            entry = data.setdefault(key, {"read_on": day, "stations": []})
            entry["read_on"] = min(entry["read_on"], day)
            entry["stations"].append(dict(s, named=bool(shared and t != town)))
    for entry in data.values():
        # The town's own first, then by name.
        entry["stations"].sort(key=lambda x: (x["named"], x["name"]))
    return data, left


def load_pages():
    """{DES id: the page's items} for every page on disk."""
    out = {}
    for p in sorted(PAGES.glob("*.html")):
        out[p.stem] = page_items(p.read_text(encoding="utf-8", errors="replace"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true", help="say what it found; write nothing")
    ap.add_argument("--allow-shrink", action="store_true",
                    help="write under town_sources.FLOORS['des_swf'], saying what fell")
    ap.add_argument("--site", default="site", help="the built site, for its towns where "
                    "generated/places.json is not there")
    a = ap.parse_args(argv)
    if not LAYER.exists():
        sys.exit(f"{LAYER} is not here: run src/fetch/other/town_directory.py first")
    layer_day, page_days = read_on()
    if not layer_day:
        sys.exit(f"{LAYER.parent / '_meta.json'} does not say when the layer was read")
    records = [f["attributes"] for f in
               json.loads(LAYER.read_text(encoding="utf-8"))["features"]]
    pages = load_pages()
    towns = parse_clerks_csv.load_towns(a.site)
    data, left = build(records, pages, towns, layer_day, page_days)
    n = sum(1 for e in data.values() for s in e["stations"] if not s["named"])
    shared = sum(1 for e in data.values() for s in e["stations"] if s["named"])
    print(f"{len(records)} facilities in DES's layer; {len(pages)} pages on disk; {n} public "
          f"stations kept in {len(data)} towns, {shared} more listings in towns a shared "
          "station's name names")
    for why in sorted(left):
        print(f"  {why}: {len(left[why])}")
        for w in left[why]:
            print(f"    {w}")
    out = {"_about": {
        "source": ("the Department of Environmental Services' map layer of solid waste "
                   "facilities (gis.des.nh.gov, Core_GIS_Datasets/DES_Data_Public, layer 12) "
                   "and each facility's page on DES's OneStop"),
        "url": SOURCE_URL,
        "kept": ("the facilities the layer lists as operating, of the classes C/S/T and C/S/T - "
                 "LIMITED PUBLIC TS, whose page gives their owner type as PUBLIC; each in the "
                 "town DES files it under, and in each town a shared one's name names"),
        "licence": "state public records",
        "writer": "src/towns/parse_transfer_stations.py"}}
    out.update(dict(sorted(data.items())))
    short = town_sources.short_of("des_swf", out)
    if short:
        print("  under the floor: " + "; ".join(short))
    if a.report:
        print("--report: nothing written")
        return 0
    if short and not a.allow_shrink:
        sys.exit("not written: DES's list placed less than the floor holds (above); "
                 "--allow-shrink writes it anyway")
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                   newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
