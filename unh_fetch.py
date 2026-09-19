#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.1
"""
Fetch the word geometry for a run of volumes, one at a time.

    python3 unh_fetch.py --plan            # what it would ask for, no network
    python3 unh_fetch.py --gap             # every 1989-1998 volume not yet here
    python3 unh_fetch.py --only journalofsenateo1994newh

WHAT IT FETCHES AND WHY ONLY THAT

One file per volume: the _djvu.xml, which carries a bounding box per word.
Nothing else is needed. The PDF is 60-100 MB against the XML's 36-57, the
flattened _djvu.txt is smaller still but loses which side of a vote a name
was on (unh_measure.py --split measures that: 7% against 96%), and the page
images are a gigabyte a volume.

HOW IT BEHAVES

Everything goes through unh_survey.get, so every rule there applies without
being restated: robots.txt asked before each request, a refusal recorded per
host and obeyed for 24 hours, every response cached and never asked for
twice, and redirects followed only by making a second deliberate request.

archive.org answers /download/ with a 302 to whichever datanode holds the
item, so each volume costs two requests plus, the first time a datanode is
seen, one more for its robots.txt. A volume already in the cache costs none,
which is what makes this safe to re-run.

It stops on the first refusal rather than working through the list. Twenty-one
volumes is a lot to ask of a host in one afternoon and the point at which it
stops being welcome is the point to stop.
"""

import argparse
import re
import sys
import time

import unh_survey as S

BASE = "https://archive.org/download/{ident}/{ident}_djvu.xml"

# The 1989-1998 gap, both chambers, as the Internet Archive names them. Taken
# from a search rather than constructed: the House writes 1990 as "8990" and
# 1996 as "9596" because those volumes are bound across two years, and the
# Senate splits most years into two or three.
GAP = [
    "journalofhouseof1989newh",
    "journalofhouseof8990newh",
    "journalofhouseof1991newh",
    "journalofhouseof1992newh",
    "vol1993journalofthehouseofrepresentativesofthestateofnewhampshireattheirsession",
    "journalofhouseof1994newh",
    "journalofhouseof1995newh",
    "journalofhouseof9596newh",
    "journalofhouseof1997newh",
    "journalofhouseof1998newh",
    "journalofsenateo1989newh",
    "journalofsenateo1990newh",
    "journalofsenateo19911newh",
    "journalofsenateo19912newh",
    "journalofsenateo19921newh",
    "journalofsenateo19922newh",
    "journalofsenateo19931newh",
    "journalofsenateo19932newh",
    "journalofsenateo1994newh",
    "journalofsenateo1995newh",
    "journalofsenateo1996newh",
    "journalofsenateo19971newh",
    "journalofsenateo19972newh",
    "journalofsenateo19981newh",
    "journalofsenateo19982newh",
]


def have(ident):
    """Is this volume's XML already cached, under any file name?

    By URL rather than by path, because the 1993 House journal's file is
    named after the book and not the item.
    """
    import json
    for meta in S.RAW.glob("*.meta.json"):
        try:
            url = json.loads(meta.read_text(encoding="utf-8")).get("url", "")
        except Exception:
            continue
        if ident in url and url.endswith("_djvu.xml"):
            body = meta.with_name(meta.name[: -len(".meta.json")])
            if body.exists() and body.stat().st_size > 1_000_000:
                return True
    return False


def fetch_one(ident, delay):
    """(ok, note). Two requests: the redirect, then the datanode it names."""
    url = BASE.format(ident=ident)
    status, headers, _body, _src = S.get(url, delay=delay)
    if status is None:
        return False, "no answer"
    if status == 200:
        return True, "served without a redirect"
    if status != 302 or not headers.get("Location"):
        return False, f"HTTP {status} with no Location"
    node = headers["Location"]
    status, _h, body, _src = S.get(node, delay=delay)
    if status is None:
        return False, "the datanode did not answer"
    if status != 200:
        return False, f"the datanode answered HTTP {status}"
    if len(body) < 1_000_000:
        return False, f"only {len(body):,} bytes; that is not a volume"
    return True, f"{len(body):,} bytes"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gap", action="store_true",
                    help="every 1989-1998 volume not already cached")
    ap.add_argument("--only", nargs="+", metavar="ID", help="these volumes")
    ap.add_argument("--plan", action="store_true", help="say what it would ask for")
    ap.add_argument("--delay", type=float, default=5.0)
    a = ap.parse_args()

    wanted = a.only if a.only else (GAP if (a.gap or a.plan) else None)
    if not wanted:
        ap.print_help()
        return

    todo = [i for i in wanted if not have(i)]
    print(f"{len(wanted)} volumes named, {len(wanted) - len(todo)} already cached, "
          f"{len(todo)} to fetch")
    if a.plan:
        for i in todo:
            print(f"  {BASE.format(ident=i)}")
        print(f"\n{len(todo) * 2} requests at {a.delay:g}s apart, plus one "
              f"robots.txt per datanode not seen before.")
        return
    if not todo:
        print("nothing to do")
        return

    ok = bad = 0
    started = time.time()
    for n, ident in enumerate(todo, 1):
        good, note = fetch_one(ident, a.delay)
        mark = "ok " if good else "NO "
        print(f"  {mark}{n:>2}/{len(todo)}  {ident:<62} {note}", flush=True)
        if good:
            ok += 1
        else:
            bad += 1
            # One failure is a gap in the archive; a run of them is the host
            # or this script being wrong, and asking on regardless is how the
            # General Court block was earned on the other side of this project.
            if bad >= 3:
                print("\n3 failures. Stopping rather than working through the "
                      "rest of the list.", file=sys.stderr)
                break
    mins = (time.time() - started) / 60
    print(f"\n{ok} fetched, {bad} not, in {mins:.0f} min")
    # Silence is not success.
    if ok == 0:
        sys.exit("nothing was fetched at all")


if __name__ == "__main__":
    main()
