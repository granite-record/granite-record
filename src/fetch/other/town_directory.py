#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.2
"""
Download the public files a town's directory is read from: its libraries,
the census blocks that say which town a place is in, and the 2014 survey
that gives each town hall a street address.

    python3 src/fetch/other/town_directory.py --status              # what is on disk, no network
    python3 src/fetch/other/town_directory.py                       # every source below
    python3 src/fetch/other/town_directory.py --source imls         # one of them
    python3 src/fetch/other/town_directory.py --source des_facility_pages   # DES's pages, ~11 min

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
  des_solid_waste  the Department of Environmental Services' map layer of
                 solid waste facilities, every record in one query: 687
                 transfer stations, recycling centres, landfills and the
                 rest, each with its permit, its status, its street address,
                 its town and coordinates (gis.des.nh.gov, which answers a
                 cloud machine where des.nh.gov does not). Added 24 October
                 2026 for the Town Services tab's transfer station card.
  des_facility_pages  the page DES's OneStop keeps for each facility the
                 layer lists as an operating collection, storage and transfer
                 site (about 210 of them), at the address the layer's own
                 ONESTOP_LINK gives, never one built here. A page names what
                 the layer does not: who holds the permit, who owns and runs
                 the place, and whether its owner is PUBLIC or PRIVATE -- the
                 difference between a town's transfer station and a scrap
                 dealer's yard, which no name settles. Read one page at a
                 time, PAGE_PACE apart, on one session (OneStop is an Oracle
                 APEX application and answers a request without its cookie
                 with an error page). It stops at the first page that is
                 refused or carries no facility, and asks nothing more; what
                 it has is kept. A page on disk is not read again without
                 --again, so a yearly refresh passes it. Its service area
                 says nothing of which towns share a station (BCEP's and
                 Wilton's are blank, AVRRDD's lists states, read 25 October
                 2026), so that stays a person's table.

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
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = _paths.ROOT
STORE = ROOT / "records" / "sources" / "directory"
PACE = 1.0
# Between two facility pages: they are an application's pages, not files, and
# about 210 of them are asked in a run.
PAGE_PACE = 3.0
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
    "des_solid_waste": (
        ("solid_waste_facilities.json",
         "https://gis.des.nh.gov/server/rest/services/Core_GIS_Datasets/DES_Data_Public/"
         "MapServer/12/query?where=1%3D1&outFields=*&returnGeometry=false&f=json"),
    ),
}
# Read after the layer, from the addresses it gives (facility_links).
PAGES = "des_facility_pages"
LAYER = ("des_solid_waste", "solid_waste_facilities.json")
ONESTOP = "https://onestop.des.nh.gov/"
# What a facility's page carries and an error page does not.
A_FACILITY = b"Facility ID:"


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


def facility_links():
    """[(file name, address)] for the facility pages to read: each record of
    the saved layer typed C/S/T (collection, storage and transfer, whatever
    follows) and listed as OPERATING, by its own ONESTOP_LINK. [] where the
    layer is not on disk."""
    try:
        d = json.loads((folder(LAYER[0]) / LAYER[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = set()
    for f in d.get("features") or []:
        a = f.get("attributes") or {}
        if not ((a.get("SWF_TYPE") or "").startswith("C/S/T")
                and a.get("SWF_STATUS") == "OPERATING"):
            continue
        url = (a.get("ONESTOP_LINK") or "").strip()
        m = re.search(r"[?&]p60_swf_lid=(\d+)$", url)
        if url.startswith(ONESTOP) and m:
            out.add((f"{m.group(1)}.html", url))
    return sorted(out)


def status(sources):
    missing = 0
    for source in sources:
        d = folder(source)
        meta = _read_meta(d)
        print(f"{source}: {d}")
        if source == PAGES:
            links = facility_links()
            have = sum((d / name).is_file() for name, _url in links)
            missing += len(links) - have
            days = sorted({str(m.get("read_at"))[:10] for m in meta.values()})
            print(f"  {have} of the {len(links)} pages the layer links are on disk"
                  + (f", read {days[0]}" + (f" to {days[-1]}" if len(days) > 1 else "")
                     if days else ""))
            continue
        for name, _url in SOURCES[source]:
            p = d / name
            m = meta.get(name) or {}
            if p.is_file():
                print(f"  {name:32} {p.stat().st_size:>12,}  read {m.get('read_at') or 'at no recorded time'}")
            else:
                missing += 1
                print(f"  {name:32} {'missing':>12}")
    return 1 if missing else 0


def fetch_pages(again=False):
    """Each facility page the saved layer links, one at a time, PAGE_PACE
    apart, on one cookie session. Stops at the first page refused or with no
    facility on it, keeping what it has: (fetched, already here)."""
    links = facility_links()
    if not links:
        raise SystemExit(f"no facility pages to read: {LAYER[0]} is not on disk, or lists none "
                         "(--source des_solid_waste first)")
    d = folder(PAGES)
    d.mkdir(parents=True, exist_ok=True)
    meta = _read_meta(d)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    got = kept = 0
    for name, url in links:
        p = d / name
        if p.is_file() and not again:
            kept += 1
            continue
        if got:
            time.sleep(PAGE_PACE)
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        try:
            with opener.open(req, timeout=120) as r:
                body, code = r.read(), r.status
        except (urllib.error.URLError, OSError) as e:
            _write_meta(d, meta)
            raise SystemExit(f"  {url}: {e}\nstopped after {got} pages read, asking nothing "
                             "more; what was read is kept")
        if A_FACILITY not in body:
            _write_meta(d, meta)
            raise SystemExit(f"  {url} answered {code} with no facility on it ({len(body):,} "
                             f"bytes)\nstopped after {got} pages read, asking nothing more; "
                             "what was read is kept")
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(body)
        tmp.replace(p)
        meta[name] = {"url": url, "status": code, "length": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(),
                      "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        got += 1
        if got % 25 == 0:
            print(f"  {PAGES}: {got} read, {kept} already here, of {len(links)}", flush=True)
            _write_meta(d, meta)
    _write_meta(d, meta)
    print(f"  {PAGES}: {got} read, {kept} already here, of the {len(links)} the layer links")
    return got, kept


def fetch(sources, again=False):
    got = kept = 0
    first = True
    for source in sources:
        if source == PAGES:
            continue
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
    if PAGES in sources:
        # After the layer, which says which pages there are.
        g, k = fetch_pages(again)
        got, kept = got + g, kept + k
    print(f"town directory sources: {got} fetched, {kept} already here, in {STORE}")
    if not got and not kept:
        raise SystemExit("nothing was fetched and nothing was on disk")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--source", nargs="+", choices=sorted([*SOURCES, PAGES]),
                    default=[*SOURCES, PAGES], help="which sources (default: every one)")
    ap.add_argument("--status", action="store_true", help="what is on disk; no network")
    ap.add_argument("--again", action="store_true",
                    help="fetch every file and page, even one on disk")
    a = ap.parse_args()
    if a.status:
        return status(a.source)
    return fetch(a.source, a.again)


if __name__ == "__main__":
    sys.exit(main())
