#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
Where each bill's committee files are: the Secretary of State's archive page
the General Court's own bill pages link as "SOS Archives!", read into
collected/sos_archives.json from the pages saved on this disk.

    python3 src/parse/sos_archives.py           # collected/sos_archives.json
    python3 src/parse/sos_archives.py --check   # read again; compare; write nothing

    import sos_archives as SA
    SA.address(SA.load(), 2025, "HB57", "21", today)
        "https://gc.nh.gov/bill_status/legacy/bs2016/sos_archives.aspx?lsr=21&sy=2025&..."

THE OWNER'S DECISION, 19 November 2026 ("Link now, trimmed PDFs later"): a
bill's Reports tab links the archive's page listing the House and Senate
committee files -- scans, some typed, some handwritten -- and nothing of them
is fetched, ever. The address is built from the record; this script asks
nobody, and nothing here or in the build requests it.

WHAT IT READS. The General Court's docket pages saved under docket_pages/
(2016 to 2024) and its status pages under status_pages/ (2023 to 2026), named
<session year>_<LSR>_<bill>.html, both read-only. A page carries the link, in
red, as "SOS Archives!", and its House History and Senate History links are
one address. Measured on 19 November 2026: 8,044 of 8,607 docket pages carry
it, and 750 of the 847 status pages of 2025 and none of the 1,387 of 2026;
every address is this scheme, with the bill's own LSR as the page prints it,
its own session year and its number in lower case -- so the file keeps the
LSR as printed and address() writes the rest, and a page whose address is not
the scheme byte for byte stops the run rather than being guessed at.

WHAT IT WRITES. {"read": {year: the first day a page of that year was
saved}, "links": {year: {bill: LSR as printed}}}. A year is in "read" where
its pages were saved after the year ended (the files are scanned once the
year's work is over: one file, 2025's CACR 6, scanned on 31 December, is the
evidence, so this is a guess from one example), and for such a year a bill
the pages name without the link has no link: the General Court's own page
says it has no file.

THE RULE address() keeps, per bill:
  - a year whose saved pages were read after it ended: the address the page
    printed, or none;
  - a later year, once it has ended (the build's day is past its 31
    December): the address built by the same scheme from the bill's LSR;
  - before that: none.
Before 2016 no saved page shows the link, so no bill of those years has one.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
from datetime import date as _date

OUT = Path("collected/sos_archives.json")
FOLDERS = ("docket_pages", "status_pages")
# The pages' own link, relative to the folder their pages are in.
BASE = "https://gc.nh.gov/bill_status/legacy/bs2016/"
HREF = re.compile(r"""href\s*=\s*['"](sos_archives\.aspx\?[^'"]*)['"]""", re.I)
NAME = re.compile(r"^(\d{4})_(\d+)_([A-Z]+\d+)\.html$")


def query(lsr, year, bill):
    """The address's own part, as every saved page prints it."""
    return (f"sos_archives.aspx?lsr={lsr}&sy={year}&sortoption=billnumber"
            f"&txtsessionyear={year}&txtbillnumber={str(bill).lower()}")


def read(root=Path(".")):
    """(read, links, counts) from the saved pages under `root`."""
    first, links, counts = {}, {}, {}
    for folder in FOLDERS:
        for p in sorted((Path(root) / folder).glob("*.html")):
            m = NAME.match(p.name)
            if not m:
                continue
            year, _lsr, bill = m.groups()
            day = _date.fromtimestamp(p.stat().st_mtime).isoformat()
            first[year] = min(first.get(year, day), day)
            c = counts.setdefault(year, {"pages": 0, "linked": 0, "_seen": set()})
            # A bill both folders saved (2023 and 2024) is one bill.
            c["pages"] += bill not in c["_seen"]
            c["_seen"].add(bill)
            found = set(HREF.findall(p.read_text(encoding="utf-8", errors="replace")))
            if not found:
                continue
            if len(found) > 1:
                raise SystemExit(f"{folder}/{p.name} links {len(found)} archive addresses: {sorted(found)}")
            href = found.pop()
            q = re.match(r"sos_archives\.aspx\?lsr=(\d+)&", href)
            if not q or href != query(q.group(1), year, bill):
                raise SystemExit(f"{folder}/{p.name}: {href!r} is not the scheme; not guessed at")
            had = links.setdefault(year, {}).get(bill)
            if had is not None and had != q.group(1):
                raise SystemExit(f"{folder}/{p.name}: LSR {q.group(1)}, another page {had}")
            if had is None:
                c["linked"] += 1
            links[year][bill] = q.group(1)
    # Only a year whose pages were all saved after it ended says which bills
    # have no file.
    read_ = {y: d for y, d in first.items() if d > f"{y}-12-31"}
    return read_, links, counts


def load(path=OUT):
    """The file, or {} where there is none."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def address(data, year, bill, lsr, today):
    """The archive's address for one bill, or "" (the module's docstring has
    the rule). `today` is the build's day, an ISO date or a date."""
    y = str(year or "")
    if not re.fullmatch(r"\d{4}", y) or not bill:
        return ""
    data = data or {}
    if y in (data.get("read") or {}):
        lsr_ = ((data.get("links") or {}).get(y) or {}).get(str(bill).upper())
        return BASE + query(lsr_, y, bill) if lsr_ else ""
    if int(y) < 2016:
        return ""
    if str(today)[:10] <= f"{y}-12-31":
        return ""
    num = str(lsr or "").split("-")[-1].lstrip("0")
    return BASE + query(num, y, bill) if num.isdigit() else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="read again and compare; write nothing")
    ap.add_argument("--root", default=".", help="the folder holding docket_pages/ and status_pages/")
    a = ap.parse_args()
    read_, links, counts = read(Path(a.root))
    if not links:
        raise SystemExit("no saved page carries an archive link: are docket_pages/ and status_pages/ here?")
    for y in sorted(counts):
        c = counts[y]
        print(f"{y}: {c['linked']:,} of {c['pages']:,} bills' pages link the archive"
              f"{'' if y in read_ else ', saved before the year ended: not read as no file'}")
    body = {"_about": "Written by src/parse/sos_archives.py from the saved docket and status pages; "
                      "its docstring says what each part is.",
            "read": dict(sorted(read_.items())),
            "links": {y: dict(sorted(links[y].items())) for y in sorted(links)}}
    text = json.dumps(body, indent=1, sort_keys=False) + "\n"
    if a.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print(f"{OUT} {'agrees with' if same else 'differs from'} the saved pages")
        sys.exit(0 if same else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}: {sum(len(v) for v in links.values()):,} bills in {len(links)} years")


if __name__ == "__main__":
    main()
