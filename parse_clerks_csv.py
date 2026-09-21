#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.1
"""
The Secretary of State's clerks and polling places, out of the CSV export.

    python3 parse_clerks_csv.py --report    # say what it found, write nothing
    python3 parse_clerks_csv.py             # -> town_clerks.json

THIS SUPERSEDES parse_clerks.py, AND THE REASON IS WORTH KEEPING.

The same page offers the same list as a PDF and as a CSV, and only the PDF
was ever taken. The PDF's Producer is jsPDF 2.5.1 -- it is generated in the
browser from the table already on the page -- and jsPDF's splitTextToSize
DISCARDS THE SPACE at a word-boundary wrap. So "ALLENSTOWN ELEMENTARY
SCHOOL" reaches the file as "ALLENSTOWN" / "ELEMENTARY" / "SCHOOL 30 MAIN"
and cannot be told apart from "SKIFFINGTO" / "N", which is one word the same
routine chopped because it did not fit a line.

parse_clerks.py is 300 lines of careful geometry trying to tell those two
apart, and it cannot be done. The proof is two lines of the same column of
the same document: "GOVERNMENT" is 71.67pt and was broken across lines, so
the wrap width is under 71.67; "STATION 153 S" is 72.25pt and sits on one
line, so the wrap width is at least 72.25. No single width produces both, so
no rule recovers the spaces, and 187 breaks across 132 of 242 multi-line
polling cells were closed up with nothing between them -- "Berlin
Recreationcenter", "1 Memorial Drhudson", "Alvirne Highschool", all of it
live on the site.

The CSV has none of that. It is the same 331 rows with the spaces still in
them, so this file is a hundred lines instead of a thousand and is right
instead of nearly right. parse_clerks.py stays, because it is the only
reader of the September PDF and that PDF is a dated capture of a list that
changes; nothing should run it to produce town_clerks.json again.

WHAT IS SHARED WITH IT, DELIBERATELY. The title-casing and the test of what
counts as a website are imported rather than rewritten, so the two readers
cannot drift into disagreeing about how a name is written or what a town
page may link.

THE LIST IS TYPED IN CAPITALS, which is how the form stores it and not how a
name is written, so the name and the polling place are title-cased for
display and the original is kept beside them under _raw.

WHAT IT STILL CANNOT DO IS CHECK THE SECRETARY OF STATE'S ARITHMETIC. Three
rows give Errol Town Hall an address that is not Errol Town Hall's, and the
CSV carries the error as faithfully as the PDF did. Those are corrected
against NHDOT's directory, from place_corrections.json, which keeps the
original beside the correction -- see that file for the evidence. A
correction whose `source_says` no longer matches the export is reported and
NOT applied, because that means the row has changed and the correction is
the stale thing.
"""
import argparse
import csv
import json
import pathlib
import re
import sys

import parse_clerks
import parse_officials

ROOT = pathlib.Path(__file__).resolve().parent
CSV_IN = ROOT / "sources" / "sos-clerks-and-polling-places-2026-09-20.csv"
OUT = ROOT / "town_clerks.json"
CORRECTIONS = ROOT / "place_corrections.json"

SOURCE_URL = "https://app.sos.nh.gov/statelistclerkandpolling"
READ_ON = "2026-09-20"          # the export's own timestamp, D:20260920200437

BLANK = {"", "not applicable", "n/a", "none", "not available", "-"}

COL = {"town": "Town/City", "clerk": "Clerk", "addr": "Address",
       "phone": "Phone", "fax": "Fax", "email": "E-Mail",
       "site": "Town Website Address",
       "shours": "State Election Start Time - End Time",
       "lhours": "Local Election Start Time - End Time",
       "poll": "Polling Place", "elect": "Election Date-Name"}

WARD = re.compile(r"^(?P<town>.*?)\s+WARD\s+0*(?P<ward>\d+)\s*$", re.I)


def clean(s):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return "" if s.lower() in BLANK else s


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def match_town(name, towns):
    """The town this row names, out of the ones the site has pages for.

    The two lists abbreviate the unincorporated places differently -- this one
    writes "AT.& GIL. AC. GT." where the district files write "Atk. & Gil.
    Academy Grant" -- so `parse_clerks.abbrev_of` decides it, the same rule
    that decided it when the list was read from the PDF. None where nothing
    matches and none where more than one does.

    AND THE APOSTROPHE HAS TO GO FIRST. `abbrev_of` compares token by token
    and requires the same number of them, and an apostrophe is a token
    boundary to it: "CHANDLER'S PUR." is three tokens where this list's
    "CHANDLERS PURCHASE" is two, so the two spellings of one place did not
    match and the row was dropped. Two places were lost that way, Chandler's
    Purchase and Low & Burbank's Grant, which is how this was noticed. The
    apostrophe is punctuation neither list is consistent about, so it is
    removed from both sides before the tokens are counted.
    """
    up = name.upper()
    if up in towns:
        return up
    flat = lambda s: s.replace("'", "").replace("’", "")
    for a, bs in ((up, towns), (flat(up), [flat(t) for t in towns])):
        hit = [t for t, orig in zip(bs, towns)
               if parse_clerks.abbrev_of(a, t) or parse_clerks.abbrev_of(t, a)]
        if len(hit) == 1:
            return [orig for b, orig in zip(bs, towns) if b == hit[0]][0]
    return None


def load_towns(site_dir):
    """{TOWN: [ward, ...]} -- ['0'] where the site does not ward it.

    Read from places.json where it exists, because that is built from the
    district files alone and needs no site build; site/districts.json is the
    fallback and says the same thing.
    """
    p = ROOT / "places.json"
    if p.exists():
        places = json.loads(p.read_text(encoding="utf-8"))["places"]
        return {v["name"].upper(): (v["named_by"]["districts"]["wards"] or ["0"])
                for v in places.values()}
    dj = pathlib.Path(site_dir) / "districts.json"
    if not dj.exists():
        sys.exit(f"neither places.json nor {dj} is there")
    d = json.loads(dj.read_text(encoding="utf-8"))
    return {t.upper(): sorted(d[t]) for t in d}


def build(rows, towns, fixes):
    data, unmatched, applied, stale = {}, [], [], []
    for r in rows:
        raw_town = clean(r[COL["town"]])
        m = WARD.match(raw_town)
        bare, ward = (m.group("town"), m.group("ward")) if m else (raw_town, None)
        name = match_town(bare, towns)
        if name is None:
            unmatched.append(raw_town)
            continue
        key = f"{slug(name)}-ward-{ward.lstrip('0') or '0'}" if ward \
            else slug(name)

        site = parse_officials.web_address(clean(r[COL["site"]]).lower())
        if site and not site.startswith("http"):
            site = "https://" + site.lstrip("/")

        # The Secretary of State's own cell repeats the district marker inside
        # the street address -- "PINKERTON ACADEMY (DIST 1) 5 PINKERTON
        # (DIST 1) ST DERRY" -- where a number and a street name cannot have a
        # district between them. The first is kept: it says which of Derry's
        # four polling places this is.
        poll = re.sub(r"(\((?:DIST|WARD)\.?\s*\d+\))(.*?)\s*\1", r"\1\2",
                      clean(r[COL["poll"]]))

        rec = {
            "clerk": parse_clerks.namecase(clean(r[COL["clerk"]])),
            "clerk_raw": clean(r[COL["clerk"]]),
            "clerk_address": parse_clerks.placecase(clean(r[COL["addr"]])),
            "phone": clean(r[COL["phone"]]),
            "email": clean(r[COL["email"]]).lower(),
            "website": site,
            "polling_place": parse_clerks.placecase(poll),
            "polling_raw": poll,
            "election": clean(r[COL["elect"]]),
            "state_hours": clean(r[COL["shours"]]),
            "local_hours": clean(r[COL["lhours"]]),
        }

        fix = fixes.get("polling_place", {}).get(key)
        if fix:
            if poll != fix["source_says"]:
                stale.append(f"{key}: the list now says {poll!r}, and the "
                             f"correction expects {fix['source_says']!r}")
            else:
                rec["polling_place"] = parse_clerks.placecase(fix["corrected_to"])
                rec["polling_raw"] = fix["corrected_to"]
                rec["polling_place_source_says"] = \
                    parse_clerks.placecase(fix["source_says"])
                rec["polling_place_note"] = fix["why"]
                applied.append(key)

        data[key] = {k: v for k, v in rec.items() if v}
    return data, unmatched, applied, stale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(CSV_IN))
    ap.add_argument("--site", default="site")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    src = pathlib.Path(a.csv)
    if not src.exists():
        sys.exit(f"{src} is not there; the export lives in sources/")
    towns = load_towns(a.site)
    fixes = json.loads(CORRECTIONS.read_text(encoding="utf-8")) \
        if CORRECTIONS.exists() else {}

    with open(src, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    missing_cols = [c for c in COL.values() if rows and c not in rows[0]]
    if missing_cols:
        sys.exit(f"the export is missing columns: {missing_cols}")

    data, unmatched, applied, stale = build(rows, towns, fixes)
    added = parse_clerks.fold_wards(data, towns)

    print(f"  {src.name}, exported {READ_ON}")
    print(f"  {len(rows)} rows read, {len(data) - len(added)} keyed to a town "
          f"page, {len(added)} town-level rows carried over from their wards")
    if added:
        print(f"    {', '.join(added)}")
    if unmatched:
        print(f"  ! {len(unmatched)} rows name no town this site has: "
              f"{unmatched}")
    for s in stale:
        print(f"  ! {s}")
        print("    the correction was NOT applied; re-read the row before "
              "trusting place_corrections.json")
    if applied:
        print(f"  {len(applied)} corrections applied from "
              f"{CORRECTIONS.name}: {', '.join(applied)}")

    n = len(data)
    for f, label in (("polling_place", "a polling place"), ("email", "an e-mail"),
                     ("phone", "a phone"), ("website", "a website")):
        print(f"    {sum(1 for v in data.values() if v.get(f))} of {n} carry "
              f"{label}")

    if a.report:
        print("  --report: nothing written")
        return 0
    pathlib.Path(a.out).write_text(
        json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"  -> {a.out} ({n} towns and wards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
