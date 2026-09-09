#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.1
"""
Captions for the recordings the proceedings table has never heard of.

    python3 fetch_archive_captions.py --check          # what is missing, no network
    python3 fetch_archive_captions.py --limit 50
    python3 fetch_archive_captions.py --year 2024

Writes work/<video_id>/captions.en.json3, the same layout everything else
already reads.

WHY THIS AND NOT fetch_captions.py

fetch_captions.py decides what to fetch from proceedings.csv, and hands each
video to transcribe_and_align.py, which exits with "No manifest rows" for a
video that is not in it. That is correct for its job -- it aligns a recording
against the proceedings it holds -- and it means the archive is unreachable
through it. Measured: proceedings.csv knows 915 of the 4,428 videos on the two
channels. The other 3,513 include 596 from 2021, 626 from 2022, 883 from 2023
and 765 from 2024, none of which any table on this disk has a row for.

So this fetches the caption file and stops there. RAW FIRST, PARSED SECOND,
which is the rule the whole archive is built on: the artefact is worth having
now, and aligning it against proceedings can happen whenever those proceedings
exist. Doing it the other way round means no captions until the dockets for
four terms are fetched, and those cost 7,200 requests nobody has agreed to.

WHAT IT COSTS, AND WHOSE SERVER

YouTube's, not the General Court's. That matters: the address this project
fetches from has refused it twice and is being treated gently, and none of
that applies here. One yt-dlp call per video, no audio downloaded, about five
and a half megabytes of captions each -- so the whole gap is roughly 20 GB.

A video with no auto-captions published is recorded as such and never asked
for again, which is the difference between a gap and a fault.
"""

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

INDEX = Path("channel_index_full.json")
WORK = Path("work")
LEDGER = Path("archive/captions.json")


def known():
    """Every video the two channels list, with its date and chamber."""
    if not INDEX.exists():
        sys.exit("channel_index_full.json is not here. It is written by the "
                 "channel walk in\nfetch_channel_index.py and needs an API key.")
    out = {}
    for chamber, d in json.loads(INDEX.read_text(encoding="utf-8")).items():
        for v in d.get("videos", []):
            out[v["id"]] = {"chamber": chamber, "date": v["published"][:10],
                            "title": v["title"]}
    return out


def has(vid):
    d = WORK / vid
    return (d / "captions.en.json3").exists() or (d / "transcript.json").exists()


def ledger():
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def fetch(vid, timeout=300):
    """(True, how) if a caption file landed, else (False, why)."""
    d = WORK / vid
    d.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--write-auto-subs",
             "--sub-langs", "en.*", "--sub-format", "json3/vtt",
             "--skip-download", "--no-warnings",
             "-o", str(d / "captions"),
             f"https://www.youtube.com/watch?v={vid}"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timed out"
    got = sorted(d.glob("captions*.json3")) + sorted(d.glob("captions*.vtt"))
    if got:
        return True, got[0].name
    err = (r.stderr or r.stdout or "").strip().splitlines()
    why = err[-1][:120] if err else "no caption file appeared"
    # A video with no auto-captions is a gap in the source, not a failure
    # here, and must not count towards the stop-loss.
    if "no subtitles" in why.lower() or "There are no subtitles" in why:
        return False, "none published"
    return False, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--year", help="only videos published in this year")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--stop-after", type=int, default=5,
                    help="consecutive real failures before giving up")
    a = ap.parse_args()

    vids = known()
    led = ledger()
    todo = [v for v in vids
            if not has(v)
            and led.get(v, {}).get("state") != "none published"
            and (not a.year or vids[v]["date"][:4] == a.year)]
    todo.sort(key=lambda v: vids[v]["date"], reverse=True)

    print(f"{len(vids):,} videos on the two channels")
    print(f"{sum(1 for v in vids if has(v)):,} already have captions")
    none_pub = sum(1 for v in led.values() if v.get("state") == "none published")
    if none_pub:
        print(f"{none_pub:,} have none published and are not asked for again")
    print(f"{len(todo):,} to fetch")
    by = Counter(vids[v]["date"][:4] for v in todo)
    for y in sorted(by):
        print(f"    {y}  {by[y]:>5}")

    if a.check:
        print("\n  Nothing was fetched.")
        return 0
    if a.limit:
        todo = todo[:a.limit]
    if not todo:
        return 0

    ok = miss = 0
    run = 0
    t0 = time.time()
    for i, v in enumerate(todo, 1):
        got, why = fetch(v)
        if got:
            ok += 1
            run = 0
            led[v] = {"state": "held", "how": why,
                      "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        elif why == "none published":
            miss += 1
            run = 0
            led[v] = {"state": "none published"}
        else:
            run += 1
            led[v] = {"state": "failed", "why": why}
            print(f"  [{i}] {v}: {why}", flush=True)
            if run >= a.stop_after:
                print(f"\n{a.stop_after} in a row. Stopping.")
                break
        if (ok + miss) % 25 == 0 and (ok + miss):
            LEDGER.parent.mkdir(exist_ok=True)
            LEDGER.write_text(json.dumps(led, indent=1), encoding="utf-8")
            print(f"  {i}/{len(todo)}  {ok} fetched, {miss} none published, "
                  f"{ok / max(1e-9, time.time() - t0) * 60:.0f}/min", flush=True)
        time.sleep(a.delay)

    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=1), encoding="utf-8")
    print(f"\n{ok:,} fetched, {miss:,} have none published, "
          f"{time.time() - t0:.0f}s")
    left = sum(1 for v in vids if not has(v)
               and led.get(v, {}).get("state") != "none published")
    print(f"{sum(1 for v in vids if has(v)):,} of {len(vids):,} now have "
          f"captions; {left:,} still wanted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
