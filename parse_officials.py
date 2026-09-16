#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.2
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

THE BANNER THAT LANDS ON A TOWN. Every page carries a two-word banner over the
table -- "Town Info" over the first six columns, "Town Officials" over the last
four -- and it is drawn in Aptos Narrow Bold at 5.64pt, 0.95pt above the first
data line, which is Aptos Narrow at 5.16. On 23 of the 30 pages the ruling grid
gives the banner a row to itself. On the other seven it does not, and pdfplumber
sorts the two overlapping lines into one, left to right, a character at a time:
Boscawen's website came out "httpsT:o//wwnw wIn.bfooscawennh.gov/", which is
"https://www.boscawennh.gov/" with "Town Info" threaded through it, and its
Mayor came out named "Town" with the telephone number "Officials". Both were
published. `without_banner` takes the banner's characters off the page before
the table is read, which is the one edit that fixes both.

A WEBSITE WRAPS TWO WAYS. Inside its cell -- "https://www.cityofportsmouth.co"
/ "m/" -- and, where the ruling grid splits the town's first row in two, onto a
row of its own with the municipality column empty: eleven of them, "us/" for
Hillsborough and ".aspx?id=55881&catid=0" for Plainfield. A URL cannot contain
a space, so both are joined with nothing; the town-info columns beside it are
NOT, because the e-mail column's continuations are second addresses and not
second halves.

AND IT IS CHECKED. Four rows are prose -- "no website", "website was
discontinued" -- and a fragment published as a live link sends a reader
somewhere that is not the town, which is worse than sending them nowhere. A
value that is not a host is not recorded.
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


def tight(s):
    """A cell joined with nothing, which is how an address wraps.

    The Website column is the only cell in this table that cannot contain a
    space, so every break in it is the generator's and none of them is the
    text's. Join it the way `clean` joins the others and Portsmouth's address
    becomes "www.cityofportsmouth.co m/".
    """
    return re.sub(r"\s+", "", s or "")


# The banner, with its spaces taken out, as it reads when the two halves are
# sorted into one line. Matched as the whole of a line and nothing less, so a
# page whose banner is somewhere else is reported rather than half-stripped.
BANNER = "TownInfoTownOfficials"

HOST = re.compile(r"(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}")


def web_address(s):
    """A Website cell as an address a reader can be sent to, or "".

    Not every cell in that column is an address. This directory writes "no
    website" in four of them and the Secretary of State's list writes an e-mail
    address in five; a cell can also be a host with a note after it, or the
    front half of one where the back half was lost. The rule is the same for
    all of them: what goes in the file is a host, and anything else is nothing,
    because a town page that draws no link is right where one that links
    "https://mnh.gov" sends a reader to somebody else's website.
    """
    s = re.sub(r"\s+", "", s or "")
    rest = re.sub(r"^https?://", "", s, flags=re.I).lstrip("/")
    host = re.split(r"[/?#]", rest, maxsplit=1)[0]
    if not host or "@" in host or not HOST.fullmatch(host):
        return ""
    return s


def without_banner(pg):
    """The page with its "Town Info / Town Officials" banner taken off it.

    Returns (page, how many characters went). The banner is found by what it
    says, not by where it sits or what it is set in: the characters are grouped
    into lines by their own baseline -- which separates the banner from the data
    line 0.95pt below it, where pdfplumber's word grouping does not -- and a
    line is the banner only when it is exactly the banner.
    """
    by_line = collections.defaultdict(list)
    for c in pg.chars:
        by_line[round(c["top"], 2)].append(c)
    drop = set()
    for y, cs in by_line.items():
        text = "".join(c["text"] for c in sorted(cs, key=lambda c: c["x0"]))
        if re.sub(r"\s+", "", text) == BANNER:
            drop |= {(round(c["x0"], 2), y) for c in cs}
    if not drop:
        return pg, 0
    return pg.filter(lambda o: not (
        o.get("object_type") == "char"
        and (round(o["x0"], 2), round(o["top"], 2)) in drop)), len(drop)


def read(pdf_path):
    import pdfplumber
    towns, notes = collections.OrderedDict(), []
    raw_site = {}
    with pdfplumber.open(pdf_path) as pdf:
        # `here` CARRIES ACROSS PAGES. A town's offices run past the bottom of
        # a page -- Andover's start on page 2 and finish on page 3 -- and
        # resetting it per page threw away every office above the first town
        # named on the page, which is where the report said "a row before any
        # town" six times on page 3 alone.
        here = None
        for pg in pdf.pages:
            page, stripped = without_banner(pg)
            tb = page.extract_table()
            if not tb:
                continue
            if not stripped:
                notes.append(f"page {pg.page_number}: no banner found to strip")
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
                site = tight(row[SITE])
                if site and (cells[MUNI] or here is not None):
                    # kept with its spaces in, so that a cell this refuses can
                    # be printed as the directory wrote it rather than as
                    # "nowebsite"
                    raw_site.setdefault(cells[MUNI] or here, []).append(cells[SITE])
                if cells[MUNI]:
                    here = cells[MUNI]
                    t = towns.setdefault(here, {
                        "municipality": here, "mailing": cells[MAIL],
                        "phone": cells[MPHONE], "fax": cells[MFAX],
                        "website": site, "email": cells[MEMAIL],
                        "officials": []})
                    # a town can start on one page and run onto the next
                    for k, v in (("mailing", cells[MAIL]), ("phone", cells[MPHONE]),
                                 ("fax", cells[MFAX]), ("website", site),
                                 ("email", cells[MEMAIL])):
                        if v and not t[k]:
                            t[k] = v
                elif here is not None and site:
                    # THE OTHER HALF OF AN ADDRESS. The ruling grid splits a
                    # town's first row in two often enough that eleven websites
                    # ended one character short of a host -- Moultonborough at
                    # ".go", Northumberland at ".or" -- with the rest sitting on
                    # a row whose municipality column is empty. There is one
                    # website per municipality and it is written on its first
                    # row, so text in that column afterwards is the rest of it.
                    if towns[here]["website"]:
                        towns[here]["website"] += site
                    else:
                        notes.append(f"page {pg.page_number}: {here} has "
                                     f"{cells[SITE]!r} on a row of its own and "
                                     "no website above it")
                if here is None:
                    notes.append(f"page {pg.page_number}: a row before any town")
                    continue
                if cells[POS] or cells[NAME]:
                    towns[here]["officials"].append({
                        "position": fix_label(cells[POS]), "name": cells[NAME],
                        "phone": cells[PHONE], "email": cells[EMAIL]})
    for name, t in towns.items():
        t["website"] = web_address(t["website"])
    return towns, notes, {k: " ".join(v) for k, v in raw_site.items()}


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
    towns, notes, raw_site = read(pdf)
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
    # THE WEBSITE, COUNTED AND NAMED. It is the one field here a reader clicks,
    # so what was refused is printed rather than dropped quietly: a town that
    # has no site and a town whose cell this could not read look identical in
    # the file and are not the same thing.
    sites = sum(1 for r in out.values() if r["website"])
    refused = sorted((k, raw_site.get(r["municipality"], ""))
                     for k, r in out.items()
                     if not r["website"] and raw_site.get(r["municipality"]))
    print(f"    {sites} of {len(out)} carry a website the site can link")
    if refused:
        print(f"    {len(refused)} whose Website cell is not an address, "
              "recorded as nothing:")
        for k, v in refused:
            print(f"      {k}: {v!r}")
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
