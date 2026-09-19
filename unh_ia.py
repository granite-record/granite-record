#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.1
"""
The same volumes, from the people who scanned them.

    python3 unh_ia.py --find "journal of the house"   # search, cached
    python3 unh_ia.py --meta <identifier>             # what files an item has
    python3 unh_ia.py --files <identifier>            # the file list, readable

WHY LOOK HERE AT ALL

The UNH record for every volume in this collection says, in its own metadata,

    Scanning Information: Scanned by Internet Archive, Open Content
                          Alliance (2008)

so the books were digitised by an organisation whose whole purpose is to hand
scans out, and which publishes a documented metadata API to do it with. That
matters for two reasons and they point the same way:

  * archive.org derives an OCR text layer -- <identifier>_djvu.txt -- and
    publishes it beside the scan. Whether the 1989-1998 journals can be read
    by machine is answerable from that file without a single PDF being moved.
  * Pulling 145 bound volumes of a century of legislative journals through a
    university library's Digital Commons instance is a lot to ask of a host
    that never offered it. The Internet Archive did offer it.

This is NOT a way around scholars.unh.edu having answered 403. That refusal is
on file, it stands, and a person decides what it meant. This is a different
source, named by UNH's own record, with its own terms -- and it gets exactly
the same care: robots.txt honoured, one request at a time, everything cached,
and its own refusal file that stops this and nothing else.

WHAT IS STILL UNKNOWN WHEN THIS FINISHES

That a volume is here and carries a text layer does not make the text usable.
These are 1990s photo-offset books scanned in 2008; the OCR was done by the
tools of that year. Nothing in this script measures quality. That is what
comparing a 1997 volume against journals/1997/, which this site already holds
from the General Court, is for.
"""

import argparse
import json
import sys
import urllib.parse

import unh_survey as S

BASE = "https://archive.org"


def search(query, rows=50, fields=("identifier", "title", "year", "date",
                                   "contributor", "sponsor", "publicdate")):
    """The documented advanced-search endpoint, asked once and cached."""
    q = urllib.parse.urlencode(
        [("q", query), ("rows", str(rows)), ("page", "1"), ("output", "json")]
        + [("fl[]", f) for f in fields])
    url = f"{BASE}/advancedsearch.php?{q}"
    status, _headers, body, source = S.get(url)
    if status is None:
        return None, url, source
    if status != 200:
        print(f"search returned HTTP {status}", file=sys.stderr)
        return None, url, source
    try:
        return json.loads(body.decode("utf-8", "replace")), url, source
    except json.JSONDecodeError as e:
        print(f"search did not return JSON ({e}); body cached at "
              f"{S.cache_path(url)}", file=sys.stderr)
        return None, url, source


def metadata(identifier):
    """https://archive.org/metadata/<id> -- every file in the item."""
    url = f"{BASE}/metadata/{identifier}"
    status, _headers, body, source = S.get(url)
    if status is None or status != 200:
        return None, url, source
    try:
        return json.loads(body.decode("utf-8", "replace")), url, source
    except json.JSONDecodeError as e:
        print(f"metadata was not JSON ({e})", file=sys.stderr)
        return None, url, source


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--find", metavar="QUERY", help="search archive.org")
    ap.add_argument("--rows", type=int, default=50)
    ap.add_argument("--meta", metavar="ID", help="the raw metadata record")
    ap.add_argument("--files", metavar="ID", help="that item's files, readable")
    a = ap.parse_args()

    if a.find:
        data, url, source = search(a.find, rows=a.rows)
        if data is None:
            sys.exit(1)
        resp = data.get("response", {})
        docs = resp.get("docs", [])
        print(f"{resp.get('numFound', '?')} found, {len(docs)} shown  [{source}]")
        # Silence is not success: a search that matched nothing is a fact
        # worth printing loudly, not an empty list to be read past.
        if not docs:
            print("NOTHING MATCHED. The query, not the archive, is the thing "
                  "to change first.")
            return
        for d in docs:
            print(f"\n  {d.get('identifier')}")
            print(f"    {str(d.get('title'))[:150]}")
            bits = [f"{k}={d[k]}" for k in ("year", "date", "sponsor", "contributor")
                    if d.get(k)]
            if bits:
                print(f"    {'  '.join(str(b)[:80] for b in bits)}")
        return

    if a.meta:
        data, _url, _source = metadata(a.meta)
        if data is None:
            sys.exit(1)
        print(json.dumps(data.get("metadata", {}), indent=1)[:4000])
        return

    if a.files:
        data, _url, source = metadata(a.files)
        if data is None:
            sys.exit(1)
        files = data.get("files", [])
        print(f"{a.files}: {len(files)} files  [{source}]")
        if not files:
            print("NO FILES LISTED -- an item id that exists but holds nothing.")
            return
        for f in sorted(files, key=lambda f: -int(f.get("size") or 0)):
            size = int(f.get("size") or 0)
            print(f"  {size:>13,}  {f.get('format',''):<28} {f.get('name','')}")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
