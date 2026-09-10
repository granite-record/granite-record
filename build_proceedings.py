#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.3
"""
Build proceedings.csv: one row per (bill, date, kind, recording), whether it
is a committee hearing or a floor debate.

    python3 build_proceedings.py

Reads verification_manifest.csv (committee proceedings, from build_manifest.py)
and floor_index.json (floor debates, from build_floor_index.py) and writes one
table in one shape. The two producers stay as they are for now; this is the
file everything downstream reads. Once every reader has moved, the producers
can be merged too.

Why: the two sources have different shapes and keys, and every tool that read
one had to be separately taught the other. Five times in one day a tool
silently excluded the floor. This is the fix for the cause rather than for
the fifth instance.

What it refuses: to write a smaller table than last time without being told
it may. A rebuild that halves the proceedings is a rebuild that lost a source.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import proceedings as P


def as_seconds(v):
    """'1:23:45' or '83:45' or '5025' -> seconds, else None."""
    if v in (None, ""):
        return None
    s = str(v).strip()
    try:
        return float(s)
    except ValueError:
        pass
    try:
        parts = [float(x) for x in s.split(":")]
    except ValueError:
        return None
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def manifest_paths(patterns):
    """Every manifest named or matched, in a stable order, without repeats.

    ONE PER TERM, AND THE TABLE BUILT WHOLE FROM ALL OF THEM. build_manifest
    writes one manifest per docket it is given, so 2023-2024 lands beside
    2025-2026 rather than on top of it. The alternative was a --term flag
    here that rebuilt one term's rows inside a file holding every term, and
    that is a writer running on a subset of what it rewrites -- which is how
    the manifest lost the 35 hand-marked times, and how segment_markers
    --transcript once discarded 842 recordings' results. Reading all of them
    every time means no writer here ever sees a subset, and the shrink guard
    below goes on comparing whole tables.
    """
    out, seen = [], set()
    for pat in patterns:
        hits = (sorted(Path(".").glob(pat))
                if any(c in pat for c in "*?[") else [Path(pat)])
        for f in hits:
            k = f.resolve()
            if f.exists() and k not in seen:
                seen.add(k)
                out.append(f)
    return out


def from_manifest(path):
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            bill = (r.get("bill") or "").strip().upper()
            if not bill:
                continue
            date = (r.get("sched_date") or "")[:10]
            rows.append({
                "term": P.term_of(date), "bill": bill,
                "body": (r.get("body") or "").strip(),
                "kind": (r.get("proceeding") or "").strip().lower(),
                "date": date, "time": (r.get("sched_time") or "").strip(),
                "committee": (r.get("committee") or "").strip(),
                "venue": (r.get("venue") or "").strip(),
                "video_id": (r.get("video_id") or "").strip(),
                "video_title": (r.get("video_title") or "").strip(),
                "stream_start": (r.get("stream_start") or "").strip(),
                "predicted_offset": as_seconds(r.get("predicted_offset")),
                "match": (r.get("match") or "").strip(),
                "debate_end": None, "window_start": None, "precise": False,
                "motions": [], "tallies": [], "whole_video": False,
                "source": "manifest",
            })
    return rows


def from_floor_index(path):
    p = Path(path)
    if not p.exists():
        return []
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    rows = []
    for bill, entries in (doc.items() if isinstance(doc, dict) else []):
        b = str(bill).strip().upper()
        for e in (entries if isinstance(entries, list) else [entries]):
            if not isinstance(e, dict):
                continue
            date = str(e.get("date") or "")[:10]
            kind = str(e.get("kind") or "floor debate").strip().lower()
            if kind not in P.FLOOR_KINDS:
                # A recording whose title names a bill is not automatically a
                # floor debate. Five of them are committee work sessions and a
                # study committee -- "House Health, Human Services and Elderly
                # Affairs Work Session on HB 54" was on the site as a floor
                # debate. The title says what it is, so read it.
                title = str(e.get("title") or "").lower()
                if "conference" in kind or "conference" in title:
                    kind = "committee of conference"
                elif "work session" in title:
                    kind = "work session"
                elif "committee to study" in title or "study committee" in title:
                    kind = "study committee"
                elif "executive session" in title:
                    kind = "executive session"
                elif "subcommittee" in title:
                    kind = "subcommittee work session"
                else:
                    kind = "floor debate"
            rows.append({
                "term": P.term_of(date), "bill": b,
                "body": str(e.get("body") or ""),
                "kind": kind, "date": date, "time": "",
                "committee": "", "venue": "",
                "video_id": str(e.get("video_id") or ""),
                "video_title": str(e.get("title") or ""),
                "stream_start": "",
                "predicted_offset": e.get("window_start"),
                "match": "roll call clock" if e.get("precise") else
                         ("title names the bill" if e.get("whole_video")
                          else "session that day"),
                "debate_end": e.get("debate_end"),
                "window_start": e.get("window_start"),
                "precise": bool(e.get("precise")),
                "motions": list(e.get("motions") or []),
                "tallies": list(e.get("tallies") or []),
                "whole_video": bool(e.get("whole_video")),
                "source": "floor_index",
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    # A GLOB, NOT A FILE. verification_manifest.csv is the current term and
    # verification_manifest_2023-2024.csv is what build_manifest writes when
    # given that term's docket; both are read, and any later term's too,
    # without this default needing to change again.
    ap.add_argument("--manifest", nargs="+",
                    default=["verification_manifest*.csv"],
                    help="one or more manifests, or a pattern matching them")
    ap.add_argument("--floor", default="floor_index.json")
    ap.add_argument("--out", default=str(P.PATH))
    ap.add_argument("--allow-shrink", action="store_true",
                    help="write even if this table is smaller than the last")
    a = ap.parse_args()

    files = manifest_paths(a.manifest)
    cm, per_file = [], []
    for f in files:
        got = from_manifest(f)
        per_file.append((f.name, len(got)))
        cm.extend(got)
    fl = from_floor_index(a.floor)
    if not cm and not fl:
        sys.exit(f"Nothing matches {' '.join(a.manifest)} and no {a.floor} is "
                 "here. Nothing to build.")
    if not cm:
        print(f"  WARNING: nothing matches {' '.join(a.manifest)} "
              "-- no committee proceedings")
    if not fl:
        print(f"  WARNING: {a.floor} not found -- no floor debates")

    rows = cm + fl
    # One row per (bill, date, kind, video). The floor index can list a bill
    # twice on one day when it had two runs of roll calls; keep the first.
    seen, uniq = set(), []
    for r in rows:
        k = (r["bill"], r["date"], r["kind"], r["video_id"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    uniq.sort(key=lambda r: (r["date"], r["time"] or "~", r["bill"]))

    prior = P.load(a.out)
    if prior and len(uniq) < 0.8 * len(prior) and not a.allow_shrink:
        sys.exit(f"Refusing: {len(uniq):,} rows, but {a.out} already holds "
                 f"{len(prior):,}.\nA table that shrinks by a fifth lost a "
                 "source. Pass --allow-shrink if that is intended.")

    P.write(uniq, a.out)

    with_video = sum(1 for r in uniq if r["video_id"])
    floor = [r for r in uniq if r["kind"] in P.FLOOR_KINDS]
    terms = sorted({r["term"] for r in uniq if r["term"]})
    print(f"{len(uniq):,} proceedings -> {a.out}")
    print(f"  {len(cm):,} from {len(files)} manifest(s), "
          f"{len(fl):,} from the floor index")
    for name, n in per_file:
        print(f"      {n:>7,}  {name}")
    print(f"  {with_video:,} have a recording; "
          f"{len({r['video_id'] for r in uniq if r['video_id']}):,} distinct")
    print(f"  {len(floor):,} floor rows, "
          f"{sum(1 for r in floor if r['precise']):,} with a roll-call end, "
          f"{sum(1 for r in floor if r['whole_video']):,} whole-video")
    print(f"  terms: {', '.join(terms)}")
    if prior:
        print(f"  (was {len(prior):,})")


if __name__ == "__main__":
    main()
