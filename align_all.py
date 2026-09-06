#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Align every video the manifest references, skipping those already done.

    python3 align_all.py --dry-run          # what would run, and roughly how long
    python3 align_all.py --chamber S        # Senate only
    python3 align_all.py                    # everything outstanding

Alignment is per video and each one is independent, so this is a loop rather
than anything clever. What it adds over a batch file is knowing which videos
still need doing, reporting how well each went, and carrying on past a failure
instead of stopping at the first video whose captions are missing.

Captions take about a second per video, so a few hundred is a few minutes.
Whisper takes hours per video, which is why captions are the default and why
this script does not offer to run it.

A video is skipped when work/<id>/segments.json already exists, so an
interrupted run picks up where it stopped.
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


def chamber_of(row):
    """Which chamber a proceeding belongs to.

    Manifests written before build_manifest.py recorded it need the venue: the
    Senate sits in the State House, the House in the Legislative Office
    Building or the annex.
    """
    b = (row.get("body") or "").strip().upper()
    if b in ("H", "S"):
        return b
    v = ((row.get("venue") or "") + " " + (row.get("committee") or "")).upper()
    if "SH " in v or ", SH" in v or v.strip().endswith(" SH"):
        return "S"
    if "LOB" in v or "GP " in v:
        return "H"
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="verification_manifest.csv")
    ap.add_argument("--workdir", default="work")
    ap.add_argument("--chamber", choices=["H", "S"], help="one chamber only")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=1.0,
                    help="pause between videos, to be polite to YouTube")
    ap.add_argument("--redo", action="store_true",
                    help="realign videos that already have segments")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.manifest, encoding="utf-8-sig")))
    work = Path(a.workdir)

    vids = {}
    for r in rows:
        vid = (r.get("video_id") or "").strip()
        if not vid:
            continue
        ch = chamber_of(r)
        if a.chamber and ch != a.chamber:
            continue
        vids.setdefault(vid, {"chamber": ch, "n": 0,
                              "committee": r.get("committee", "")})
        vids[vid]["n"] += 1

    done = {v for v in vids if (work / v / "segments.json").exists()}
    todo = sorted(vids) if a.redo else sorted(set(vids) - done)

    by_ch = Counter(vids[v]["chamber"] for v in vids)
    print(f"{len(vids):,} videos in the manifest "
          + ", ".join(f"{n} {c}" for c, n in sorted(by_ch.items())))
    print(f"{len(done):,} already aligned, {len(todo):,} to do")
    if a.limit:
        todo = todo[:a.limit]
        print(f"limited to {len(todo)}")

    if not todo:
        print("\nNothing outstanding.")
        return
    print(f"roughly {len(todo) * 3 / 60:.0f} minutes at a few seconds each\n")

    if a.dry_run:
        for v in todo[:15]:
            d = vids[v]
            print(f"  {v}  {d['chamber']}  {d['n']:>2} proceedings  {d['committee']}")
        if len(todo) > 15:
            print(f"  ... {len(todo) - 15} more")
        print("\nNothing was run. Drop --dry-run to do it.")
        return

    ok = failed = 0
    located = total = 0
    problems = []
    t0 = time.time()
    for i, vid in enumerate(todo, 1):
        d = vids[vid]
        print(f"[{i}/{len(todo)}] {vid}  {d['chamber']}  "
              f"{d['n']} proceedings  {d['committee'][:34]}", flush=True)
        time.sleep(a.delay)
        r = subprocess.run(
            [sys.executable, "transcribe_and_align.py", "--video", vid,
             "--source", "captions", "--workdir", a.workdir]
            + (["--realign"] if a.redo else []),
            capture_output=True, text=True)
        if r.returncode != 0:
            failed += 1
            last = [l for l in (r.stdout + r.stderr).strip().splitlines() if l.strip()]
            msg = last[-1] if last else "no output"
            problems.append((vid, msg[:90]))
            print(f"      failed: {msg[:90]}")
            continue
        ok += 1
        # The summary line reads "N/M proceedings located".
        for line in r.stdout.splitlines():
            if "proceedings located" in line:
                print(f"      {line.strip()}")
                try:
                    a_, b_ = line.strip().split()[0].split("/")
                    located += int(a_)
                    total += int(b_)
                except (ValueError, IndexError):
                    pass
                break

    mins = (time.time() - t0) / 60
    print(f"\n{'-' * 58}")
    print(f"{ok:,} aligned, {failed:,} failed, {mins:.1f} minutes")
    if total:
        print(f"{located:,} of {total:,} proceedings located "
              f"({100 * located / total:.0f}%)")
    if problems:
        print(f"\n{len(problems)} video(s) failed:")
        for v, m in problems[:12]:
            print(f"  {v}  {m}")
        print("\nA video with no caption track cannot be aligned. Those "
              "proceedings keep a link to the recording with no start time, "
              "which is the honest outcome rather than a guess.")
    print("\nRun build_site_v2.py to pick these up, then publish.")


if __name__ == "__main__":
    main()
