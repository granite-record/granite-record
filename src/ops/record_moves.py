#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-05.1
"""
Record every address a former member's page has moved from, so it answers
with a 301 for good.

    python3 src/ops/record_moves.py            # merge site/former.json's moves in; say what is new
    python3 src/ops/record_moves.py --check    # say what is new, write nothing

A former member's page is addressed by their seat (build_site_v2.member_slug),
and the page moves when its seat is put right -- from the bills of their last
term (date_former_seats), or when two of their numbers become one page
(former_movers). The build answers the old address with a 301 from the row's
moved_from, but works that out afresh every time: the day the reason for a move
goes away, the address would die with it, and old emails link through those
addresses (the manager, 5 November 2026: "keep the 301s permanently").

So this keeps them in generated/moved_addresses.json, {address: member id},
which every build reads (build_site_v2.keep_moved). It MERGES: an address is
added, never dropped or re-pointed, and a run over a build that moved fewer
pages takes nothing away. Run it after a build that warns of unrecorded
addresses, and commit the file. No network.
"""
import argparse
import json
import sys
from pathlib import Path

OUT = Path("generated/moved_addresses.json")


def moves(former_rows):
    """{address: member id} for every moved_from of the published rows."""
    out = {}
    for r in former_rows:
        for a in r.get("moved_from") or []:
            out.setdefault(a, str(r.get("id") or ""))
    return out


def merge(have, found):
    """have, with every address of found that it does not hold yet -- an
    address it holds keeps the member it was recorded for."""
    got = dict(have)
    for a, mid in found.items():
        if a not in got and mid:
            got[a] = mid
    return dict(sorted(got.items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", default="site")
    ap.add_argument("--check", action="store_true", help="write nothing")
    a = ap.parse_args()
    src = Path(a.site) / "former.json"
    if not src.exists():
        sys.exit(f"{src} is not here: build the site first")
    found = moves(json.loads(src.read_text(encoding="utf-8")))
    have = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    new = {k: v for k, v in found.items() if k not in have}
    clash = {k: (have[k], v) for k, v in found.items() if k in have and have[k] != v}
    print(f"{len(found):,} moved address(es) in {src}; {len(have):,} recorded; {len(new):,} new")
    for k, (was, now) in sorted(clash.items()):
        print(f"  NOTE: {k} is recorded for {was} and this build moves it from {now}; "
              "the record stands")
    if a.check or not new:
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(merge(have, found), indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT}: {len(have) + len(new):,} address(es)")


if __name__ == "__main__":
    main()
