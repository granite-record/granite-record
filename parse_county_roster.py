#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-22.1
"""
New Hampshire's elected county officers, out of the Secretary of State's roster.

    python3 parse_county_roster.py --report   # what it found, writes nothing
    python3 parse_county_roster.py            # -> county_officials.json

WHICH OFFICES, AND WHY THESE. RSA 655:9 names them: county commissioner,
sheriff, county attorney, county treasurer, register of deeds and register of
probate. Ten counties, three commissioners each by district and one of each
of the others -- eighty seats. None of them appeared anywhere in this project
before this file: not in NHDOT's directory, not in the clerk list, not in the
town-website sweep. The person named county officials, and sheriffs in
particular, as part of what they meant by municipal officials.

THE SOURCE. `sources/sos-county-roster-2025-2026.pdf`, "COUNTY ROSTER
2025-2026", from the Secretary of State's Election Division -- the election
authority's own list of who won the 2024 county elections, in one document
for all ten counties. Its embedded CreationDate is D:20241205110929-05'00',
so 5 December 2024 is the date it is true as of. It was fetched through a
real browser because sos.nh.gov refuses scripted clients, and saved byte for
byte: 163,109 bytes, sha256
8b507d159a095d71cd79e33a401a42410948df23c367676db5735a3fe6cc2f24.

It was chosen over the ten county websites because it is uniform -- one
document, one format, one authority for all ten -- and over search results
because it is the record rather than a summary of one. The search results
were stale: they named a Carroll County sheriff and county attorney from an
older annual report, and this roster names different people.

WHAT IT CANNOT KNOW. RSA 661:9 fills a vacancy by vote of the county
convention, and 661:9-a has the probate court fill a register of probate's.
So a holder can change between elections without this document changing,
and every record says the date it is true as of rather than claiming to be
current. The counties' own sites are the corroboration for that, and are not
read here.

WHAT IS NOT RECORDED, DELIBERATELY. The roster prints each candidate's street
address and ZIP. Those are filing addresses -- where the person lives -- and
not an office's published contact, and this project does not republish a
home address even where an official source prints one. Name, office,
district, party and domicile town only. Domicile is the town, not the
address, and it is printed on the New Hampshire ballot itself.

READ BY POSITION, NOT BY GUESSWORK. A row is "Name  Domicile  Address
City/State/Zip  Party" with nothing marking where a name ends and a town
begins, and a town can be two words (Gilmanton Iron Works) just as a name
can. Each page's own header row gives the column edges, and every word is
assigned by where it sits.
"""
import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PDF = ROOT / "sources" / "sos-county-roster-2025-2026.pdf"
OUT = ROOT / "county_officials.json"

SOURCE_URL = ("https://www.sos.nh.gov/sites/g/files/ehbemt561/files/documents/"
              "2024-12/roster-county-offices-2024.pdf")
READ_ON = "2024-12-05"
SHA256 = "8b507d159a095d71cd79e33a401a42410948df23c367676db5735a3fe6cc2f24"

COUNTIES = {"BELKNAP", "CARROLL", "CHESHIRE", "COOS", "GRAFTON",
            "HILLSBOROUGH", "MERRIMACK", "ROCKINGHAM", "STRAFFORD", "SULLIVAN"}

# RSA 655:9, in the words the roster uses for them.
#
# THE COMMISSIONER HEADING IS WRITTEN TWO WAYS in the same document. Eight
# counties say "County Commissioner District 1"; Carroll and Sullivan say
# "County Commissioner, 1st District". Matching only the first left those two
# headings unrecognised, the Register of Probate heading above them stayed in
# force, and each of those counties came out with four registers of probate
# and no commissioners -- six real commissioners published under an office
# that has one seat. Both forms are read now, and SEATS below would have
# failed on it either way.
OFFICE = re.compile(
    r"^(Sheriff|County Attorney|County Treasurer|Register of Deeds|"
    r"Register of Probate|County Commissioner)"
    r"(?:,?\s+(?:District\s+(\d+)|(\d+)(?:st|nd|rd|th)\s+District))?\s*$",
    re.I)

# One of each per county, three commissioners (RSA 655:9, 662:4). A county
# holding more than this has had a heading go unrecognised and an office
# drift down the page onto people who belong to the next one.
SEATS = {"Sheriff": 1, "County Attorney": 1, "County Treasurer": 1,
         "Register of Deeds": 1, "Register of Probate": 1,
         "County Commissioner": 3}
PARTY = re.compile(r"^(REP|DEM|LIB|IND|GRN|UND|CON)(/(REP|DEM|LIB|IND|GRN|UND|CON))*$")


def columns(words):
    """The x at which each column starts, from this page's own header row.

    THE ADDRESS COLUMN STARTS AT ITS FIRST WORD, NOT ITS LAST. Its header is
    "Candidate Address", two words, and the column's content is aligned under
    the first of them (x 375.5) -- not under "Address" (x 427.2). Taking the
    edge from "Address" put every street number and "PO Box" in the gap
    between the two, which is where the domicile is read from, so the first
    run published "Conway 643 Stark Road" and "Wolfeboro PO Box 991" as
    towns. That is a home address, which is the one thing this file exists
    not to record.
    """
    head = {}
    cands = []
    for w in words:
        t = w["text"]
        if t == "Candidate":
            cands.append(w["x0"])
        elif t == "Domicile":
            head["domicile"] = w["x0"]
        elif t.startswith("City/State"):
            head["city"] = w["x0"]
        elif t == "Party":
            head["party"] = w["x0"]
    if cands:
        head["name"] = min(cands)
    if "domicile" in head:
        after = [x for x in cands if x > head["domicile"]]
        if after:
            head["address"] = min(after)
    return head


def lines_of(words):
    rows = collections.defaultdict(list)
    for w in words:
        rows[round(w["top"])].append(w)
    return [sorted(rows[k], key=lambda w: w["x0"]) for k in sorted(rows)]


def read(path):
    import pdfplumber
    out, notes = [], []
    county = office = district = None
    col = None
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            words = pg.extract_words()
            c = columns(words)
            if len(c) == 5:
                col = c                      # a page without one keeps the last
            if not col:
                notes.append(f"page {pg.page_number}: no header row to read "
                             f"columns from")
                continue
            for line in lines_of(words):
                text = " ".join(w["text"] for w in line)
                if text.startswith(("OFFICE OF THE SECRETARY", "COUNTY ROSTER",
                                    "Candidate Name", "Page ")):
                    continue
                m = re.match(r"^([A-Z]+)\s+County\s*$", text)
                if m and m.group(1) in COUNTIES:
                    county, office, district = m.group(1).title(), None, None
                    continue
                o = OFFICE.match(text)
                if o:
                    office = o.group(1).title().replace(" Of ", " of ")
                    district = o.group(2) or o.group(3)
                    continue
                party = [w["text"] for w in line if w["x0"] >= col["party"] - 2]
                if not party:
                    continue                 # a wrapped address or ZIP
                name = " ".join(w["text"] for w in line
                                if w["x0"] < col["domicile"] - 2)
                dom = " ".join(w["text"] for w in line
                               if col["domicile"] - 2 <= w["x0"] < col["address"] - 2)
                p = " ".join(party)
                if not (county and office and name):
                    notes.append(f"page {pg.page_number}: a row with no county, "
                                 f"office or name: {text[:60]!r}")
                    continue
                # A DOMICILE IS A TOWN. A digit, a PO box or a street word in
                # it means an address has crossed the column edge, and the row
                # is refused outright rather than written: better a missing
                # town than a published home address.
                if re.search(r"\d|\bP\.?O\.?\b|\bBox\b|\b(Rd|Road|St|Street|"
                             r"Ave|Avenue|Dr|Drive|Ln|Lane|Way|Hwy)\b", dom) \
                        or len(dom.split()) > 4:
                    notes.append(f"page {pg.page_number}: REFUSED {name!r} -- "
                                 f"domicile {dom!r} carries an address")
                    continue
                if not PARTY.match(p):
                    notes.append(f"page {pg.page_number}: {name!r} has party "
                                 f"{p!r}, which is not a party code")
                out.append({"county": county, "office": office,
                            "district": district, "name": name,
                            "domicile": dom, "party": p})
    return out, notes


def build(rows):
    recs = []
    for r in rows:
        rec = dict(r)
        rec.update({
            "source_url": SOURCE_URL,
            "source_file": str(PDF.relative_to(ROOT)).replace("\\", "/"),
            "source_sha256": SHA256,
            "read_on": READ_ON,
            "method": "pdfplumber by column position over the saved roster",
            "status": "published",
            "filled_by": "elected",
            "filled_by_source": "the Secretary of State's roster of 2024 "
                                "county election winners",
            "note": "true as of the roster's own date; RSA 661:9 fills a "
                    "vacancy by the county convention between elections",
        })
        if rec["district"] is None:
            rec.pop("district")
        recs.append(rec)
    return recs


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if not PDF.exists():
        print(f"  {PDF.name} is not in sources/")
        return 1
    rows, notes = read(PDF)
    recs = build(rows)
    seated = collections.Counter((r["county"], r["office"]) for r in recs)
    over = [(c, o, n) for (c, o), n in seated.items() if n > SEATS.get(o, 1)]
    for c, o, n in over:
        notes.append(f"{c} has {n} people as {o}, which seats "
                     f"{SEATS.get(o, 1)} -- a heading was not recognised")
    by = collections.Counter(r["county"] for r in recs)
    offs = collections.Counter(r["office"] for r in recs)
    print(f"  {PDF.name}, true as of {READ_ON}")
    print(f"  {len(recs)} officers across {len(by)} counties")
    for c in sorted(by):
        print(f"    {c:13s} {by[c]}")
    print("  by office:")
    for o, n in offs.most_common():
        print(f"    {n:3d}  {o}")
    for n in notes:
        print(f"  ! {n}")
    if a.report:
        print("  --report: nothing written")
        return 0
    OUT.write_text(json.dumps({
        "_what": "Elected county officers of New Hampshire (RSA 655:9), from "
                 "the Secretary of State's county roster of 2024 winners.",
        "_source_url": SOURCE_URL, "_read_on": READ_ON, "_sha256": SHA256,
        "officers": recs}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"  wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
