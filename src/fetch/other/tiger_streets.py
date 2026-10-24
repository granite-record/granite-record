#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.1
"""
Download the Census Bureau's TIGER/Line files that name New Hampshire's
streets, for the address box's suggestions.

    python3 src/fetch/other/tiger_streets.py --status          # what is on disk, no network
    python3 src/fetch/other/tiger_streets.py                   # the newest release this knows
    python3 src/fetch/other/tiger_streets.py --year 2027       # another release

WHY (the person, 24 October 2026: "I'd like to make some improvements to the
address search so that it shows you a dropdown of matching addresses around
New Hampshire as you're typing with the zip codes"). The Census Bureau's
geocoder, which the Your town panel asks, has no type-ahead, and a
third-party one would send every key a reader presses to another outside
service. So the suggestions are a list of streets this site serves itself,
and this brings down what that list is read from.

WHAT IT ASKS. www2.census.gov, and nothing else: 21 files, one at a time, a
second apart.

  ADDRFEAT, one a county (10)  every edge of a street that carries house
                               numbers: its name and each alternate name, the
                               low and high number on each side, their
                               parity, and each side's ZIP code
  FACES, one a county (10)     the polygons either side of each edge, with
                               the county subdivision -- the town -- each is in
  COUSUB, the state's one      the county subdivisions' names

All public domain. Not the General Court: no lock, no lane, and
archive/refused.json is about gc.nh.gov and does not apply.

WHAT IS SAVED. The zips, unmodified, under records/sources/tiger/<year>/,
which is gitignored as records/sources/gis/ is (about 54 MB, and
re-fetchable), and _meta.json beside them: for each file the address asked,
the status, the server's Last-Modified, the length, a sha256 and when it was
read. src/towns/parse_tiger_streets.py reads them and touches no network.

A file already on disk at the length the server gives is not fetched again;
--again fetches every one. Each release is a folder of its own, so a new
year's files never overwrite the last's.
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
# The newest release on 24 October 2026: TIGER2026, published 6 October 2026.
YEAR = 2026
# New Hampshire's ten counties, by their FIPS codes (33 is the state).
COUNTIES = ("001", "003", "005", "007", "009", "011", "013", "015", "017", "019")
BASE = "https://www2.census.gov/geo/tiger/TIGER{year}"
PACE = 1.0
AGENT = "graniterecord.org (a public record of the NH General Court; contact@graniterecord.org)"


def folder(year):
    return ROOT / "records" / "sources" / "tiger" / str(year)


def wanted(year):
    """(file name, its address) for every file the list is read from."""
    base = BASE.format(year=year)
    out = []
    for c in COUNTIES:
        out.append((f"tl_{year}_33{c}_addrfeat.zip", f"{base}/ADDRFEAT/tl_{year}_33{c}_addrfeat.zip"))
        out.append((f"tl_{year}_33{c}_faces.zip", f"{base}/FACES/tl_{year}_33{c}_faces.zip"))
    out.append((f"tl_{year}_33_cousub.zip", f"{base}/COUSUB/tl_{year}_33_cousub.zip"))
    return out


def status(year):
    d = folder(year)
    meta = _read_meta(d)
    have = 0
    for name, _url in wanted(year):
        p = d / name
        m = meta.get(name) or {}
        if p.is_file():
            have += 1
            print(f"  {name:32} {p.stat().st_size:>10,}  {m.get('last_modified') or 'no record of when'}")
        else:
            print(f"  {name:32} {'missing':>10}")
    print(f"{have} of {len(wanted(year))} files for TIGER{year} in {d}")
    return 0 if have == len(wanted(year)) else 1


def _read_meta(d):
    try:
        return json.loads((d / "_meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_meta(d, meta):
    (d / "_meta.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n",
                                  encoding="utf-8", newline="\n")


def fetch(year, again=False):
    d = folder(year)
    d.mkdir(parents=True, exist_ok=True)
    meta = _read_meta(d)
    got = kept = 0
    for i, (name, url) in enumerate(wanted(year)):
        p = d / name
        if i:
            time.sleep(PACE)
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        if p.is_file() and not again:
            head = urllib.request.Request(url, method="HEAD", headers={"User-Agent": AGENT})
            with urllib.request.urlopen(head, timeout=60) as r:
                size = int(r.headers.get("Content-Length") or -1)
                said = {"url": url, "status": r.status,
                        "last_modified": r.headers.get("Last-Modified")}
            if size == p.stat().st_size:
                kept += 1
                if name not in meta:
                    # Put here some other way (copied, or a run cut short
                    # before it wrote this): what the server says of it now.
                    body = p.read_bytes()
                    meta[name] = {**said, "length": len(body),
                                  "sha256": hashlib.sha256(body).hexdigest(),
                                  "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                    _write_meta(d, meta)
                print(f"  {name}: on disk at the server's length, kept")
                continue
        with urllib.request.urlopen(req, timeout=300) as r:
            body = r.read()
            meta[name] = {"url": url, "status": r.status,
                          "last_modified": r.headers.get("Last-Modified"),
                          "length": len(body),
                          "sha256": hashlib.sha256(body).hexdigest(),
                          "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        tmp = p.with_suffix(".part")
        tmp.write_bytes(body)
        tmp.replace(p)
        got += 1
        print(f"  {name}: {len(body):,} bytes, Last-Modified {meta[name]['last_modified']}")
        # Written after every file, so a run cut short still says what it has.
        _write_meta(d, meta)
    print(f"TIGER{year}: {got} fetched, {kept} already here, in {d}")
    if not got and not kept:
        raise SystemExit("nothing was fetched and nothing was on disk")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--year", type=int, default=YEAR)
    ap.add_argument("--status", action="store_true", help="what is on disk; no network")
    ap.add_argument("--again", action="store_true", help="fetch every file, even one on disk")
    a = ap.parse_args()
    if a.status:
        return status(a.year)
    return fetch(a.year, a.again)


if __name__ == "__main__":
    sys.exit(main())
