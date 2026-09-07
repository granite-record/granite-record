#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.1
"""
Which recordings the site has proceedings for and no captions.

    python3 caption_gaps.py
    python3 caption_gaps.py --list       # every recording, not just the summary

No network, no writes. This reads proceedings.csv and looks in work/.

WHY THIS EXISTS

A proceeding with no captions can still be linked to its recording, but it can
never get a timestamp: segment_markers reads what the chair said, and with no
transcript there is nothing to read. So the gap is not "a missing file", it is
"these bills link to an hour of video with no way in".

Measured on 6 September: 119 of 9,762 proceedings, on 54 recordings. That is
1.2%, and it is not spread evenly -- 112 of the 119 are committees of
conference, which is the worst possible place to be missing, because that is
where the final compromise on a contested bill is written. build_floor_index
says as much in its own docstring.

TWO DIFFERENT PROBLEMS, WHICH THE COUNT HIDES

  no folder at all      the recording was never fetched. A fetch would get it.
  a folder, no captions  it WAS fetched and produced nothing. That is either a
                        recording YouTube has no captions for -- in which case
                        whisper is the only route -- or a fetch that failed.

Telling those apart is the point of this: they need different work, and a
single number of "missing captions" does not say which.
"""

import argparse
import collections
import csv
import sys
from pathlib import Path

CAPTION_GLOBS = ("*.vtt", "*.srt", "*.json", "*.txt")


def caption_state(work, vid):
    """'none' if never fetched, 'empty' if fetched and silent, else 'ok'."""
    d = work / vid
    if not d.is_dir():
        return "none"
    for g in CAPTION_GLOBS:
        if any(d.glob(g)):
            return "ok"
    return "empty"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proceedings", default="proceedings.csv")
    ap.add_argument("--work", default="work")
    ap.add_argument("--list", action="store_true",
                    help="print every recording rather than a summary")
    a = ap.parse_args()

    p = Path(a.proceedings)
    if not p.exists():
        sys.exit(f"{p} is not here. Run build_proceedings.py first.")
    rows = list(csv.DictReader(p.open(encoding="utf-8-sig")))
    work = Path(a.work)

    by_vid = collections.defaultdict(list)
    for r in rows:
        v = (r.get("video_id") or "").strip()
        if v:
            by_vid[v].append(r)
    if not by_vid:
        sys.exit(f"{p} names no recordings, which is itself the finding.")

    state = {v: caption_state(work, v) for v in by_vid}
    gaps = {v: rs for v, rs in by_vid.items() if state[v] != "ok"}
    n_proc = sum(len(rs) for rs in by_vid.values())
    n_gap = sum(len(rs) for rs in gaps.values())

    print(f"{len(by_vid):,} recordings, {n_proc:,} proceedings")
    print(f"{len(gaps):,} recordings have no captions, covering {n_gap:,} "
          f"proceedings ({100 * n_gap / n_proc:.1f}%)")
    if not gaps:
        print("Nothing to do: every recording with a proceeding has captions.")
        return 0

    kinds = collections.Counter(r.get("kind") for rs in gaps.values() for r in rs)
    print("\n  by what the proceeding is:")
    for k, n in kinds.most_common():
        print(f"    {n:5,}  {k or '(unstated)'}")

    # The distinction that decides what work is needed.
    split = collections.Counter(state[v] for v in gaps)
    print("\n  and why:")
    print(f"    {split.get('none', 0):5,}  never fetched -- a fetch would get "
          "them")
    print(f"    {split.get('empty', 0):5,}  fetched and produced no captions -- "
          "either YouTube has none,")
    print("           in which case whisper is the only route, or the fetch "
          "failed")

    years = collections.Counter((r.get("date") or "")[:4]
                                for rs in gaps.values() for r in rs)
    print("\n  by year: " + ", ".join(f"{y or '(none)'} {n:,}"
                                      for y, n in sorted(years.items())))

    if a.list:
        print("\n  every recording, worst first:")
        for v in sorted(gaps, key=lambda x: -len(gaps[x])):
            rs = gaps[v]
            when = min((r.get("date") or "") for r in rs)
            what = collections.Counter(r.get("kind") for r in rs).most_common(1)
            print(f"    {v}  {state[v]:5}  {len(rs):3} proceeding(s)  {when}  "
                  f"{what[0][0] if what else ''}")
    else:
        worst = sorted(gaps, key=lambda x: -len(gaps[x]))[:8]
        print("\n  the eight covering the most, --list for all:")
        for v in worst:
            print(f"    {v}  {state[v]:5}  {len(gaps[v]):3} proceeding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
