#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.1
"""
Download the public files a town's directory is read from: its libraries,
the census blocks that say which town a place is in, and the 2014 survey
that gives each town hall a street address.

    python3 src/fetch/other/town_directory.py --status              # what is on disk, no network
    python3 src/fetch/other/town_directory.py                       # every source below
    python3 src/fetch/other/town_directory.py --source imls         # one of them

WHY (the person, 24 October 2026: "gather more useful information for the
town pages like the address of city hall, directories for the public schools
in that town's district, transfer station addresses and hours if possible
... That would exist on town pages and would display in things like the
guides if you have your town selected"). The plan that followed is phased;
this is its first phase's reading, the sources any machine can reach. The
State's own hosts behind Akamai (NH Employment Security, Revenue
Administration, Education) refuse a cloud machine, so what they publish is
saved on the laptop instead, and nothing here asks them.

WHAT IT ASKS, one file at a time, a second apart:

  imls           the Institute of Museum and Library Services' Public
                 Libraries Survey, fiscal year 2024 (published June 2026):
                 every public library outlet in the country, with its
                 address, phone, coordinates and census block. Federal data,
                 public domain.
  census_blocks  the Census Bureau's 2020 block assignment file for New
                 Hampshire, which names the county subdivision -- the town
                 -- each census block lies in, and the list of those
                 subdivisions with their names. Public domain.
  granit_cai     NH GRANIT's Community Anchor Institutions layer, its
                 attribute table only: 3,969 places surveyed for the state's
                 broadband map as of 30 September 2014, among them every
                 town hall or town office with a street address. "Not for
                 legal use", no access constraints (its metadata, saved
                 beside it).

Not the General Court: no lock, no lane, and archive/refused.json is about
gc.nh.gov and does not apply.

WHAT IS SAVED. Each source's files, unmodified, under
records/sources/directory/<source>/, which is gitignored as
records/sources/tiger/ is (re-fetchable), and _meta.json beside them: for
each file the address asked, the status, the server's Last-Modified, the
length, a sha256 and when it was read. The readers in src/towns/
(parse_libraries.py first) read them and touch no network, so a reader can
be wrong without costing a request.

A file already on disk at the length the server gives is not fetched again;
--again fetches every one.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone

ROOT = _paths.ROOT
STORE = ROOT / "records" / "sources" / "directory"
PACE = 1.0
AGENT = "graniterecord.org (a public record of the NH General Court; contact@graniterecord.org)"

GRANIT = ("https://ftp.granit.unh.edu/GRANIT_Data/Vector_Data/Cultural_Society_and_Demographic/"
          "d-communityanchorinstitutions/")

# (file name, its address), for each source. The IMLS address is the one the
# survey's own page linked on 24 October 2026; a new year's survey is a new
# address, found on that page
# (https://www.imls.gov/research-evaluation/surveys/public-libraries-survey-pls).
SOURCES = {
    "imls": (
        ("pls_fy2024_csv.zip", "https://www.imls.gov/sites/default/files/2026-06/pls_fy2024_csv.zip"),
    ),
    "census_blocks": (
        ("BlockAssign_ST33_NH.zip",
         "https://www2.census.gov/geo/docs/maps-data/data/baf2020/BlockAssign_ST33_NH.zip"),
        ("st33_nh_cousub2020.txt",
         "https://www2.census.gov/geo/docs/reference/codes2020/cousub/st33_nh_cousub2020.txt"),
    ),
    "granit_cai": (
        ("CAINH.dbf", GRANIT + "CAINH.dbf"),
        ("cainh.txt", GRANIT + "cainh.txt"),
    ),
}


def folder(source):
    return STORE / source


def _read_meta(d):
    try:
        return json.loads((d / "_meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_meta(d, meta):
    (d / "_meta.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n",
                                  encoding="utf-8", newline="\n")


def status(sources):
    missing = 0
    for source in sources:
        d = folder(source)
        meta = _read_meta(d)
        print(f"{source}: {d}")
        for name, _url in SOURCES[source]:
            p = d / name
            m = meta.get(name) or {}
            if p.is_file():
                print(f"  {name:32} {p.stat().st_size:>12,}  read {m.get('read_at') or 'at no recorded time'}")
            else:
                missing += 1
                print(f"  {name:32} {'missing':>12}")
    return 1 if missing else 0


def fetch(sources, again=False):
    got = kept = 0
    first = True
    for source in sources:
        d = folder(source)
        d.mkdir(parents=True, exist_ok=True)
        meta = _read_meta(d)
        for name, url in SOURCES[source]:
            p = d / name
            if not first:
                time.sleep(PACE)
            first = False
            if p.is_file() and not again:
                head = urllib.request.Request(url, method="HEAD", headers={"User-Agent": AGENT})
                with urllib.request.urlopen(head, timeout=60) as r:
                    size = int(r.headers.get("Content-Length") or -1)
                if size == p.stat().st_size:
                    kept += 1
                    print(f"  {source}/{name}: on disk at the server's length, kept")
                    continue
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=300) as r:
                body = r.read()
                meta[name] = {"url": url, "status": r.status,
                              "last_modified": r.headers.get("Last-Modified"),
                              "length": len(body),
                              "sha256": hashlib.sha256(body).hexdigest(),
                              "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if not body:
                raise SystemExit(f"{url} answered {meta[name]['status']} with nothing in it")
            tmp = p.with_suffix(p.suffix + ".part")
            tmp.write_bytes(body)
            tmp.replace(p)
            got += 1
            print(f"  {source}/{name}: {len(body):,} bytes, Last-Modified "
                  f"{meta[name]['last_modified']}")
            # Written after every file, so a run cut short still says what it has.
            _write_meta(d, meta)
    print(f"town directory sources: {got} fetched, {kept} already here, in {STORE}")
    if not got and not kept:
        raise SystemExit("nothing was fetched and nothing was on disk")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--source", nargs="+", choices=sorted(SOURCES), default=list(SOURCES),
                    help="which sources (default: every one)")
    ap.add_argument("--status", action="store_true", help="what is on disk; no network")
    ap.add_argument("--again", action="store_true", help="fetch every file, even one on disk")
    a = ap.parse_args()
    if a.status:
        return status(a.source)
    return fetch(a.source, a.again)


if __name__ == "__main__":
    sys.exit(main())
