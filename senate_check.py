#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.6
"""How the Senate rows fared in the manifest.

The overall counts are dominated by the 5,550 House rows, so a Senate-only
failure -- a title format that does not parse, or a missing livestream start
time -- would be invisible in them.
"""
import collections
import csv
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "verification_manifest.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
print(f"{len(rows):,} rows, columns: {', '.join(rows[0].keys())}\n")

# Find the chamber column whatever it is called.
cand = [c for c in rows[0]
        if {(r.get(c) or "").strip().upper() for r in rows[:400]} <= {"H", "S", ""}
        and any((r.get(c) or "").strip().upper() == "S" for r in rows)]
if cand:
    col = cand[0]
    print(f"chamber column: {col!r}\n")
    body_of = lambda r: (r.get(col) or "").strip().upper()
else:
    # A manifest written before build_manifest.py recorded the chamber. The
    # venue gives it away: the Senate sits in the State House, the House in the
    # Legislative Office Building or the annex.
    print("No chamber column; inferring from the venue and committee name.\n")
    def body_of(r):
        v = ((r.get("venue") or "") + " " + (r.get("committee") or "")).upper()
        if "SH " in v or v.strip().endswith(" SH") or ", SH" in v:
            return "S"
        if "LOB" in v or "GP " in v:
            return "H"
        return "?"

import collections as _c
print("rows by inferred chamber:",
      dict(_c.Counter(body_of(r) for r in rows)), "\n")

for body, label in (("H", "House"), ("S", "Senate"), ("?", "unclear")):
    sub = [r for r in rows if body_of(r) == body]
    if not sub:
        continue
    vid = sum(1 for r in sub if (r.get("video_id") or "").strip())
    # The columns are stream_start and predicted_offset. Guessing at names
    # reported zero for both chambers and looked like a data failure.
    start = sum(1 for r in sub if (r.get("stream_start") or "").strip())
    offset = sum(1 for r in sub if (r.get("predicted_offset") or "").strip())
    print(f"{label}: {len(sub):,} rows")
    print(f"   with a video      {vid:,}")
    print(f"   with a livestream start {start:,}")
    print(f"   with a predicted offset {offset:,}"
          + ("   <- these can be aligned" if offset else
             "   <- nothing to anchor to"))
    mk = next((k for k in ("match", "match_note", "notes") if k in rows[0]), None)
    if mk:
        top = collections.Counter((r.get(mk) or "").split(" -")[0].split(" that")[0]
                                  for r in sub).most_common(4)
        for k, n in top:
            print(f"   {n:>5}  {k or '(blank)'}")
    print()
