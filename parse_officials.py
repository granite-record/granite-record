#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.1
"""
Municipal officials, out of the Department of Transportation's directory.

    python3 parse_officials.py --report     # says what it found, writes nothing
    python3 parse_officials.py              # -> town_officials.json

WHAT THIS IS

"City and Town Officials of the State of New Hampshire", September 2025,
prepared by the Bureau of Planning and Community Assistance at NHDOT. It is
the only list on this disk that says who sits on a selectboard, and it is the
answer to a question asked of this site early on: the town pages name everyone
who represents a town in Concord and in Washington, and named nobody who
represents it at home.

Thirty-one pages, one table each, ten columns. A municipality is named on its
first row and left blank on the rest, so the town is carried forward; each row
after it is one office. The names are properly spaced and properly cased here,
which is worth knowing twice over: it is what the town pages can show, and it
is the dictionary `parse_clerks.py` uses to settle the joins in the Secretary
of State's hard-wrapped PDF.

WHAT IS PUBLISHED, AND WHY

Phone numbers and e-mail addresses, including the ones at msn.com and
gmail.com. This site already republishes a legislator's published contact
details on the same reasoning: an official who lists an address as the way to
reach their office has published it as an official address, and a directory of
municipal officials prepared by a state agency is exactly that. Nothing here
is a home address -- the mailing address in the table is the town's own -- and
no office is listed that the directory does not list.

WHAT IT DOES NOT HAVE. Wards. The directory is per municipality, so a city's
twelve wards share one selectboard entry, which is correct: a city council is
elected by ward but governs the city.
"""
import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PDF = ROOT / "sources" / "nh-municipal-officials-2025-09-01.pdf"
OUT = ROOT / "town_officials.json"

MUNI, MAIL, MPHONE, MFAX, SITE, MEMAIL, POS, NAME, PHONE, EMAIL = range(10)

# The offices worth showing, in the order a reader would ask for them. The
# directory's own wording is kept -- "Board of Selectman" is how it spells it
# -- except where it labels the chair, which is worth keeping distinct.
ORDER = ["Mayor", "City Manager", "Town Manager", "Town Administrator",
         "Board of Selectman, Chair", "Board of Selectman", "City Council",
         "Town Clerk", "Road Agent"]


def rank(pos):
    for i, k in enumerate(ORDER):
        if pos.lower().startswith(k.lower()):
            return i
    return len(ORDER) + 1


# The directory spells the same office both ways -- "Town Counsilor" 28 times
# and "Town Councilor" 14 -- so the label is spelled one way here. A person's
# name is never touched: "Jim ManEachern" is what the directory prints, and a
# name is not ours to correct from a guess, however obvious the guess.
LABEL_FIX = {"counsilor": "Councilor", "counsilor,": "Councilor,",
             "councilman": "Councilor", "councilman,": "Councilor,"}


def fix_label(s):
    return " ".join(LABEL_FIX.get(w.lower(), w) for w in s.split())


def clean(s):
    s = re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()
    return "" if s.lower() in {"", "-", "n/a", "none"} else s


def read(pdf_path):
    import pdfplumber
    towns, notes = collections.OrderedDict(), []
    with pdfplumber.open(pdf_path) as pdf:
        # `here` CARRIES ACROSS PAGES. A town's offices run past the bottom of
        # a page -- Andover's start on page 2 and finish on page 3 -- and
        # resetting it per page threw away every office above the first town
        # named on the page, which is where the report said "a row before any
        # town" six times on page 3 alone.
        here = None
        for pg in pdf.pages:
            tb = pg.extract_table()
            if not tb:
                continue
            for row in tb:
                if len(row) < 10:
                    continue
                cells = [clean(c) for c in row]
                if not any(cells):
                    continue
                head = cells[MUNI].lower()
                # the page's own headers, which repeat on every page and once
                # collided with a phone number in the text layer
                if (head.startswith("municipal officials in")
                        or head.startswith("town info")
                        or cells[POS].lower().startswith("position")):
                    continue
                if cells[MUNI]:
                    here = cells[MUNI]
                    t = towns.setdefault(here, {
                        "municipality": here, "mailing": cells[MAIL],
                        "phone": cells[MPHONE], "fax": cells[MFAX],
                        "website": cells[SITE], "email": cells[MEMAIL],
                        "officials": []})
                    # a town can start on one page and run onto the next
                    for k, v in (("mailing", cells[MAIL]), ("phone", cells[MPHONE]),
                                 ("fax", cells[MFAX]), ("website", cells[SITE]),
                                 ("email", cells[MEMAIL])):
                        if v and not t[k]:
                            t[k] = v
                if here is None:
                    notes.append(f"page {pg.page_number}: a row before any town")
                    continue
                if cells[POS] or cells[NAME]:
                    towns[here]["officials"].append({
                        "position": fix_label(cells[POS]), "name": cells[NAME],
                        "phone": cells[PHONE], "email": cells[EMAIL]})
    return towns, notes


def tidy(towns):
    """Drop the empty offices, order them, and fold the obvious duplicates."""
    for t in towns.values():
        seen, keep = set(), []
        for o in t["officials"]:
            if not o["name"]:
                continue              # "Mayor" with nobody in it, in 200 towns
            k = (o["position"].lower(), o["name"].lower())
            if k in seen:
                continue
            seen.add(k)
            keep.append(o)
        keep.sort(key=lambda o: (rank(o["position"]), o["name"]))
        t["officials"] = keep
    return towns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(PDF))
    ap.add_argument("--site", default="site")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    pdf = pathlib.Path(a.pdf)
    if not pdf.exists():
        sys.exit(f"{pdf} is not there; the directory lives in sources/")
    towns, notes = read(pdf)
    towns = tidy(towns)

    dj = pathlib.Path(a.site) / "districts.json"
    known = {}
    if dj.exists():
        d = json.loads(dj.read_text(encoding="utf-8"))
        # Apostrophes: the directory writes "Harts Location" and the district
        # file "Hart's Location".
        known = {t.upper(): t for t in d}
        known.update({t.upper().replace("'", ""): t for t in d})
    out, unmatched = {}, []
    for name, rec in towns.items():
        key = name.upper()
        real = known.get(key) or known.get(key.replace("'", ""))
        if not real:
            unmatched.append(name)
            continue
        s = re.sub(r"[^a-z0-9]+", "-", real.lower()).strip("-")
        out[s] = rec
    counts = collections.Counter(
        o["position"] for r in out.values() for o in r["officials"])
    print(f"  {len(towns)} municipalities in the directory, "
          f"{len(out)} matched to a town this site has")
    print(f"  {sum(len(r['officials']) for r in out.values())} named offices")
    for pos, n in counts.most_common(12):
        print(f"      {n:>4}  {pos}")
    if unmatched:
        print(f"    {len(unmatched)} the site has no page for: "
              + ", ".join(unmatched[:10]))
    have = [k for k, r in out.items() if r["officials"]]
    print(f"    {len(have)} of {len(out)} carry at least one named official")
    for n in notes[:6]:
        print(f"    {n}")
    if a.report:
        print("  --report: nothing written")
        return
    pathlib.Path(a.out).write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"  -> {a.out} ({len(out)} municipalities)")


if __name__ == "__main__":
    main()
