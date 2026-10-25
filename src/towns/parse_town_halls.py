#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.1
"""
Where each town's office stands: a street address that two sources agree on.

    python3 src/towns/parse_town_halls.py --report    # say what it found, write nothing
    python3 src/towns/parse_town_halls.py             # -> collected/town_halls.json

WHY (the person, 24 October 2026: "gather more useful information for the
town pages like the address of city hall ..."). NHDOT's directory, which the
Town Officials tab draws the town offices from, gives a MAILING address, and
67 of its 234 are post office boxes. A reader who has to go to the town
office needs the building.

WHAT IT READS, touching no network:

  nhdot          collected/town_officials.json, NHDOT's directory of
                 September 2025: each town office's mailing address.
  sos_list       collected/town_clerks.json, the Secretary of State's list of
                 September 2026: each clerk's address.
  granit_cai     NH GRANIT's Community Anchor Institutions layer, its table
                 (records/sources/directory/granit_cai/CAINH.dbf, saved by
                 src/fetch/other/town_directory.py): places surveyed for the
                 state's broadband map as of 30 September 2014, the
                 government ones named "<Town> - Town Office" and the like,
                 each with a street address and coordinates.
  town_sites     town_sites/, the towns' own pages as src/fetch/other/
                 town_sites.py saved them on the laptop (not in git): read
                 where they are there, and nothing is fetched.

TWO SOURCES THAT AGREE, OR NO ADDRESS. Every disagreement between the survey
and NHDOT's street addresses was read by hand on 24 October 2026, and they
were of three kinds: the same address spelled two ways ("1 City Hall Plz"
and "1 City Hall Plaza", "488 Townhouse Rd" and "488 Town House Rd", "818
First New Hampshire Tpke" and "818 1st NH Turnpike"), which STREET_WORDS
and the comparison of a street's letters without its spaces make one; an
office that has moved since 2014 (Bristol's from 230 Lake St to 5 School St,
Durham's from 15 to 8 Newmarket Rd, Epsom's from Black Hall Rd to 1598 Dover
Rd), where NHDOT and the clerk list agree with each other and not with the
survey; and a typing slip in one source (Lempster's 865 or 856, Wilmot's
"Kearsage"), which no rule here can settle. So a street address counts, and
a town page draws it, where two sources agree on its number and its street:

  1. NHDOT's mailing address and the clerk's address, the newest two, read
     a year apart by two departments;
  2. the survey's address and either of those;
  3. either of those or the survey's, and a page of the town's own site
     (the laptop's town_sites/, where a town's mail goes to a box).

Each agreeing source is kept with its day (`from`), so the page can say
where the address comes from. A town with no two agreeing has none until a
source changes or the laptop runs this over its saved pages.

WHICH OF A TOWN'S BUILDINGS, in the survey. Its names for a town's own were
read before this was written: 121 "Town Hall", 55 "Town Offices", 47 "Town
Office", 14 "City Hall", 2 "Municipal Offices", 2 "Town Meeting House", and
one each of "Town Municipal Building" (Hill), "Meeting House" (Sharon) and
"Town Hall / EOC" (Stratham), with "City of Keene" for Keene and a dash
without its space for Harrisville. Some towns have a hall and offices in two
buildings, and the business is done in the offices, so offices come first
(OFFICE_ORDER); "Old Town Hall" is not one of them. A village's name ("West
Milan") is its town's (VILLAGE).

NOT IN town_sources.py, deliberately: the survey is one edition and is not
read again, so a freshness rule over it would be due for ever. What can go
stale is what confirms it, and NHDOT's directory, the clerk list and the
towns' pages are each held there already.

WHAT IT WRITES: collected/town_halls.json, one entry for each of the 234
towns NHDOT lists, keyed as the town pages key a town: the street address
two sources agree on (`street`, its place and ZIP, and `from`), or none; and
the survey's record where it has one (`survey`: the building's kind, its
street built from the survey's own parts -- its "ADDRESS" doubles a route's
type, "130 NH Rte 10 Rte", and runs a number into its direction, "41S Main
St" -- its coordinates and day). A FLOOR: it refuses to write fewer than
FLOOR_FOUND towns with an address unless a person passes --allow-shrink.
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
import parse_tiger_streets

ROOT = _paths.ROOT
SURVEY = ROOT / "records" / "sources" / "directory" / "granit_cai" / "CAINH.dbf"
OFFICIALS = ROOT / "collected" / "town_officials.json"
CLERKS = ROOT / "collected" / "town_clerks.json"
SITES = ROOT / "town_sites"
OUT = ROOT / "collected" / "town_halls.json"

SURVEYED = "2014-09-30"
SOURCE_URL = ("https://ftp.granit.unh.edu/GRANIT_Data/Vector_Data/"
              "Cultural_Society_and_Demographic/d-communityanchorinstitutions/")
GOVERNMENT = "6"            # the survey's CAICAT for a government building
OFFICE_ORDER = ("Town Offices", "Town Office", "Municipal Offices", "Town Municipal Building",
                "Municipal Building", "City Hall", "Town Hall", "Town Meeting House",
                "Meeting House")
NAMED = re.compile(r"^(?:(?:City|Town) of\s+)?(?P<town>.*?)\s*-\s*(?P<kind>"
                   + "|".join(OFFICE_ORDER) + r")(?:\s*/.*)?$")
VILLAGE = re.compile(r"^(?:North|South|East|West|Center|Centre)\s+")
# Measured on 24 October 2026, with no town pages saved on the machine: 202 of
# the 234 towns have an address two sources agree on. The floor sits under it.
FLOOR_FOUND = 185

# A street's words as one spelling, so that two sources' "Rd" and "Road"
# agree. Only the type and direction words; a street's name is its own.
STREET_WORDS = {
    "street": "st", "st": "st", "road": "rd", "rd": "rd", "avenue": "ave", "ave": "ave",
    "av": "ave", "drive": "dr", "dr": "dr", "lane": "ln", "ln": "ln", "highway": "hwy",
    "hwy": "hwy", "route": "rte", "rte": "rte", "rt": "rte", "square": "sq", "sq": "sq",
    "squ": "sq", "place": "pl", "pl": "pl", "plaza": "plz", "plz": "plz", "court": "ct",
    "ct": "ct", "circle": "cir", "cir": "cir", "turnpike": "tpke", "tpke": "tpke",
    "tpk": "tpke", "terrace": "ter", "ter": "ter", "boulevard": "blvd", "blvd": "blvd",
    "parkway": "pkwy", "pkwy": "pkwy", "green": "grn", "grn": "grn", "way": "way",
    "north": "n", "n": "n", "south": "s", "s": "s", "east": "e", "e": "e",
    "west": "w", "w": "w", "first": "1st", "1st": "1st"}
# The words that end a street's name, so that a street can be read out of a
# line that runs on into its town ("93 Main Street Sutton 03221").
TYPES = {"st", "rd", "ave", "dr", "ln", "hwy", "rte", "sq", "pl", "plz", "ct", "cir", "tpke",
         "ter", "blvd", "pkwy", "grn", "way"}
# "NH Route 10", "US Route 4" and "Route 10" are one road to a reader and,
# written by two sources, one road here; "New Hampshire" is "NH".
ROUTE_PREFIX = {"nh", "us", "state"}
NUMBER = re.compile(r"\d+[a-z]?")


def words(text):
    """An address or a page as its words, lower case, its abbreviations made
    one; punctuation is a space."""
    raw = re.sub(r"[^0-9a-z' ]+", " ", html.unescape(text or "").lower())
    raw = re.sub(r"\bnew hampshire\b", "nh", raw)
    out = []
    for w in raw.split():
        w = w.strip("'")
        if w:
            out.append(STREET_WORDS.get(w, w))
    # "nh rte 10" -> "rte 10"
    return [w for i, w in enumerate(out)
            if not (w in ROUTE_PREFIX and i + 1 < len(out) and out[i + 1] in ("rte", "hwy"))]


def same_number(a, b):
    """Two house numbers are one where they are equal, or one is the other
    with a unit's letter ("268" and "268B")."""
    return a == b or (a[:-1] == b and a[-1:].isalpha()) or (b[:-1] == a and b[-1:].isalpha())


def street_in(text):
    """(number, the street's letters) of the first street address in `text`:
    a number not a box's, then words to the first that ends a street's name
    (TYPES), with a route's number after it. None where there is none."""
    w = words(text)
    for i, t in enumerate(w):
        if not NUMBER.fullmatch(t) or (i and w[i - 1] == "box"):
            continue
        st = []
        for j in range(i + 1, min(i + 9, len(w))):
            st.append(w[j])
            if w[j] in TYPES:
                if w[j] in ("rte", "hwy") and j + 1 < len(w) and NUMBER.fullmatch(w[j + 1]):
                    st.append(w[j + 1])
                return t, "".join(st)
    return None


def carries(text, number, street):
    """Whether `text` carries `number` and then the street's letters."""
    if not number or not street:
        return False
    w = words(text)
    for i, t in enumerate(w):
        if not same_number(t, number):
            continue
        got = ""
        for x in w[i + 1:i + 12]:
            got += x
            if got == street:
                return True
            if len(got) >= len(street):
                break
    return False


def street_of(r):
    """(the street as the page writes it, number, the street's letters) from
    the survey's parts: a route's type said once ("130 NH Rte 10", not "...
    Rte 10 Rte"), a direction apart from the number ("41 S Main St"), and a
    direction its street's name already says left out ("29 South Village
    Rd", not "29 S South Village Rd")."""
    name = " ".join(r["STREETNAME"].split())
    typ = r["STREETTYPE"].strip()
    if typ and typ.lower() in name.lower().split():
        typ = ""
    pre = r["PREDIR"].strip()
    if pre and STREET_WORDS.get(name.split(" ")[0].lower()) == pre.lower():
        pre = ""
    parts = [r["BLDGNBR"].strip(), pre, name, typ, r["SUFFDIR"].strip()]
    shown = " ".join(p for p in parts if p)
    return shown, parts[0].lower(), "".join(words(" ".join(parts[1:])))


def page_text(raw):
    """A saved page's words, without its markup, its scripts or its styles."""
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw or "")
    return re.sub(r"<[^>]+>", " ", raw)


def site_pages(key):
    """[(url, read_on, text)] for the pages of a town's own site saved in
    town_sites/, home page first; [] where there are none. Read straight from
    the store: town_sites.saved() makes the folder it looks in."""
    d = SITES / key
    try:
        meta = json.loads((d / "_meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for name, rec in meta.items():
        if not isinstance(rec, dict) or rec.get("status") != 200:
            continue
        p = d / name
        if not p.is_file():
            continue
        out.append((rec.get("kind") != "home", rec.get("url", ""),
                    str(rec.get("read_on") or "")[:10],
                    page_text(p.read_text(encoding="utf-8", errors="replace"))))
    return [(u, day, t) for _h, u, day, t in sorted(out, key=lambda x: x[0])]


def clerk_for(key, clerks):
    """The clerk list's row for a town, or for a city filed by ward its first
    ward's, as town_sites.municipalities reads it."""
    return clerks.get(key) or next(
        (v for k, v in sorted(clerks.items())
         if k.startswith(key + "-ward-") and isinstance(v, dict)), None) or {}


def mailing_parts(mailing):
    """(street, place, zip) out of NHDOT's "5 School St, Bristol, NH 03222";
    the street without a parenthesis ("4 Signature Dr (off Rte 125)") or a
    box after it."""
    bits = [b.strip() for b in re.sub(r"\s*\([^)]*\)", "", mailing or "").split(",")]
    street = bits[0] if bits else ""
    place = bits[1] if len(bits) > 1 and not re.search(r"\bp\.?\s*o\b", bits[1], re.I) else ""
    z = re.search(r"\b(\d{5})(?:-\d{4})?\s*$", mailing or "")
    return street, place, z.group(1) if z else ""


def survey_offices(rows, towns):
    """({town key: (kind, survey row)}, [a name matched to no town]): each
    town's own building in the survey, offices first (OFFICE_ORDER)."""
    best, unmatched = {}, []
    for r in rows:
        if r.get("CAICAT") != GOVERNMENT:
            continue
        m = NAMED.match(" ".join(r["ANCHORNAME"].split()))
        if not m:
            continue
        town = (parse_clerks_csv.match_town(m.group("town"), towns)
                or parse_clerks_csv.match_town(VILLAGE.sub("", m.group("town")), towns))
        if town is None:
            unmatched.append(r["ANCHORNAME"])
            continue
        key = parse_clerks_csv.slug(town)
        rank = OFFICE_ORDER.index(m.group("kind"))
        if key not in best or rank < best[key][0]:
            best[key] = (rank, m.group("kind"), r)
    return {k: (kind, r) for k, (_rank, kind, r) in best.items()}, unmatched


def build(rows, towns, officials, clerks, pages=site_pages):
    """({town key: entry}, [a survey name matched to no town]), for every
    town NHDOT lists."""
    survey, unmatched = survey_offices(rows, towns)
    towns_name = {parse_clerks_csv.slug(t): t.title() for t in towns}
    out = {}
    for key in sorted(k for k, v in officials.items() if isinstance(v, dict)):
        off = officials[key]
        clerk = clerk_for(key, clerks)
        mail, caddr = off.get("mailing") or "", clerk.get("clerk_address") or ""
        dot_said = {"source": "nhdot", "on": off.get("as_of") or "", "said": mail}
        sos_said = {"source": "sos_list", "on": clerk.get("read_on") or "", "said": caddr}
        dot = street_in(mail)
        entry = {"street": "", "place": "", "zip": "", "from": []}
        site = pages(key)

        def on_site(number, street):
            for url, day, text in site:
                if carries(text, number, street):
                    return {"source": "town_site", "on": day, "url": url}
            return None
        # 1. NHDOT and the clerk list, the newest two.
        if dot and carries(caddr, *dot):
            street, place, z = mailing_parts(mail)
            entry.update(street=street, place=place, zip=z, **{"from": [dot_said, sos_said]})
        got = survey.get(key)
        if got:
            kind, r = got
            shown, number, street = street_of(r)
            agree = [s for s, text in ((dot_said, mail), (sos_said, caddr))
                     if carries(text, number, street)]
            if not agree:
                hit = on_site(number, street)
                agree = [hit] if hit else []
            entry["survey"] = {"kind": kind, "street": shown,
                               "place": " ".join(r["CITY"].split()), "zip": r["ZIP5"].strip(),
                               "lat": round(float(r["LATITUDE"]), 6),
                               "lon": round(float(r["LONGITUDE"]), 6),
                               "surveyed": SURVEYED, "agrees": bool(agree),
                               "raw": {"name": r["ANCHORNAME"], "address": r["ADDRESS"]}}
            # 2. the survey and either, or 3. the survey and the town's site.
            if not entry["street"] and agree:
                entry.update(street=shown, place=entry["survey"]["place"],
                             zip=entry["survey"]["zip"],
                             **{"from": [{"source": "granit_cai", "on": SURVEYED}] + agree})
            elif entry["street"] and agree:
                entry["from"].append({"source": "granit_cai", "on": SURVEYED})
        # 3. NHDOT's street and the town's own site.
        if not entry["street"] and dot:
            hit = on_site(*dot)
            if hit:
                street, place, z = mailing_parts(mail)
                entry.update(street=street, place=place, zip=z, **{"from": [dot_said, hit]})
        # A PLACE AND A ZIP FOR EVERY ADDRESS. NHDOT's line can stop short --
        # Wolfeboro's is "84 South Main St, PO Box" -- so they come from the
        # survey where it agrees, else the clerk's line, else the town's name.
        if entry["street"] and not (entry["place"] and entry["zip"]):
            sv = entry.get("survey") or {}
            ok = sv.get("agrees")
            z = re.search(r"\b(\d{5})\s*$", caddr)
            entry["place"] = entry["place"] or (sv.get("place") if ok else "") \
                or towns_name.get(key, "")
            entry["zip"] = entry["zip"] or (sv.get("zip") if ok else "") or (z.group(1) if z else "")
        out[key] = entry
    return out, unmatched


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true", help="say what it found; write nothing")
    ap.add_argument("--allow-shrink", action="store_true",
                    help="write under FLOOR_FOUND, saying what fell")
    ap.add_argument("--site", default="site", help="the built site, for its towns where "
                    "generated/places.json is not there")
    a = ap.parse_args(argv)
    if not SURVEY.exists():
        sys.exit(f"{SURVEY} is not here: run src/fetch/other/town_directory.py first")
    towns = parse_clerks_csv.load_towns(a.site)
    rows = list(parse_tiger_streets.dbf_rows(SURVEY.read_bytes()))
    officials = json.loads(OFFICIALS.read_text(encoding="utf-8"))
    clerks = json.loads(CLERKS.read_text(encoding="utf-8"))
    data, unmatched = build(rows, towns, officials, clerks)
    found = [e for e in data.values() if e["street"]]
    by = {}
    for e in found:
        k = " and ".join(sorted(f["source"] for f in e["from"]))
        by[k] = by.get(k, 0) + 1
    have_sites = SITES.is_dir() and any(SITES.iterdir())
    print(f"{len(found)} of {len(data)} towns have a street address two sources agree on"
          f"{'' if have_sites else ' (no town pages saved on this machine)'}:")
    for k, n in sorted(by.items(), key=lambda x: -x[1]):
        print(f"  {n:4}  {k}")
    print(f"  the survey names an office for {sum(1 for e in data.values() if 'survey' in e)}; "
          f"{sum(1 for e in data.values() if not e['street'])} towns have none agreed")
    for u in unmatched:
        print(f"  matched to no town: {u}")
    out = {"_about": {
        "rule": "a street address shown only where two sources agree on its number and street",
        "sources": {
            "nhdot": "NHDOT's directory of city and town officials (collected/town_officials.json)",
            "sos_list": "the Secretary of State's list of town and city clerks "
                        "(collected/town_clerks.json)",
            "granit_cai": f"NH GRANIT's Community Anchor Institutions layer, as of "
                          f"{SURVEYED}: {SOURCE_URL}; not for legal use, no access constraints",
            "town_site": "the town's own website, as saved in town_sites/"},
        "writer": "src/towns/parse_town_halls.py"}}
    out.update(data)
    short = len(found) < FLOOR_FOUND
    if short:
        print(f"  under the floor: {len(found)} towns with an address, under {FLOOR_FOUND}")
    if a.report:
        print("--report: nothing written")
        return 0
    if short and not a.allow_shrink:
        sys.exit("not written: under the floor (above); --allow-shrink writes it anyway")
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                   newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
