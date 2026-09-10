#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.11
"""
Fetch captions for every recording that has none, busiest first.

    python3 fetch_captions.py --floor-first        # the 95 floor sessions first
    python3 fetch_captions.py --limit 4            # try a few
    python3 fetch_captions.py --list missing_captions.txt

Calls transcribe_and_align.py once per video. It does the work; this decides
the order, skips what is already there, keeps going when one fails, and stops
when the far end is clearly unhappy.

WHY --source captions AND NOT auto

transcribe_and_align.py offers captions, whisper, or auto. Captions come from
YouTube in seconds. Whisper transcribes locally over hours, and a floor session
runs five to seven of them. "auto" falls back to whisper when captions are
missing -- which on a 95-video run means a job that looks like an afternoon and
is actually a week, with no warning at the point it changes its mind.

So captions is the default here and whisper has to be asked for by name.

ORDER

Busiest first. A floor session carries two hundred bill appearances against a
committee hearing's dozen, so an interrupted run should already have taken the
recordings that matter most. --floor-first puts every floor session ahead of
every committee one regardless of count.
"""

import argparse
import proceedings as P
import json
import re
import subprocess
import sys
import time
import child
from collections import Counter, defaultdict
from pathlib import Path

CAPTION_FILES = ["captions.en.json3", "captions.en-orig.json3", "transcript.json"]


def has_captions(workdir, vid):
    d = Path(workdir) / vid
    return d.is_dir() and any((d / f).exists() for f in CAPTION_FILES)


def hms(s):
    s = int(max(0, s))
    h, m = divmod(s // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s % 60:02d}s"


MANIFEST_COLS = ["bill", "body", "committee", "proceeding", "sched_date",
                 "sched_time", "venue", "tier", "bills_in_slot", "match",
                 "video_id", "video_title", "stream_start", "predicted_offset",
                 "watch_url", "candidates", "observed_start", "observed_end",
                 "notes"]


def working_manifest(rows, out_path):
    """A manifest-shaped file for transcribe_and_align.py, from the table.

    That tool refuses a video with no manifest rows, and it is not this
    project's to change. It used to get a copy of the real manifest with floor
    rows patched on; now it gets every proceeding from the one table, in the
    columns it expects. The real manifest is not read here at all.
    """
    import csv
    with Path(out_path).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLS)
        w.writeheader()
        for r in rows:
            if not r["video_id"]:
                continue
            w.writerow({
                "bill": r["bill"], "body": r["body"], "committee": r["committee"],
                "proceeding": r["kind"], "sched_date": r["date"],
                "sched_time": r["time"], "venue": r["venue"], "tier": "",
                "bills_in_slot": "", "match": r["match"],
                "video_id": r["video_id"], "video_title": r["video_title"],
                "stream_start": r["stream_start"],
                "predicted_offset": ("" if r["predicted_offset"] is None
                                     else r["predicted_offset"]),
                "watch_url": f"https://www.youtube.com/watch?v={r['video_id']}",
                "candidates": "", "observed_start": "", "observed_end": "",
                "notes": ""})
    return out_path


def sources():
    """(counts by video, floor session videos, whole-video recordings)."""
    rows = P.load()
    if not rows:
        sys.exit("No proceedings.csv. Run: python3 build_proceedings.py")
    counts = Counter()
    for r in rows:
        if r["video_id"]:
            counts[r["video_id"]] += 1
    return rows, counts, P.floor_videos(rows), P.whole_videos(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", help="a file of video ids, one per line "
                                   "(from probe_alignment.py --missing)")
    ap.add_argument("--workdir", default="work")

    ap.add_argument("--floor-first", action="store_true",
                    help="every floor session before any committee one")
    ap.add_argument("--only-floor", action="store_true")
    ap.add_argument("--source", default="captions",
                    choices=["captions", "whisper", "auto"])
    ap.add_argument("--model", default=None,
                    help="whisper model: tiny|base|small|medium|large-v3. "
                         "base is usually enough here -- see the note below.")
    ap.add_argument("--device", default=None, choices=["auto", "cpu", "cuda"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--stop-after", type=int, default=5,
                    help="consecutive failures before giving up")
    ap.add_argument("--timeout", type=float, default=None,
                    help="seconds to allow one video. Default: 900 for "
                         "captions, 8 hours for whisper -- a six-hour floor "
                         "session transcribed locally does not finish in "
                         "fifteen minutes, and killing it at fifteen minutes "
                         "looks exactly like the job hanging.")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.timeout is None:
        a.timeout = 900 if a.source == "captions" else 8 * 3600

    tool = Path("transcribe_and_align.py")
    if not tool.exists():
        sys.exit("transcribe_and_align.py is not in this folder.")

    # transcribe_and_align.py wants manifest rows for the video it is given.
    # Floor sessions have none, so it refuses them before it ever asks YouTube
    # for anything. Give it a copy of the manifest with the floor index folded
    # in.
    rows, counts, floor, whole_video = sources()
    use_manifest = working_manifest(rows, "_captions_manifest.csv")
    print(f"{len(rows):,} proceedings from the table -> {use_manifest} "
          "(what transcribe_and_align.py reads)")

    if a.list:
        ids = [x.strip() for x in Path(a.list).read_text(encoding="utf-8").split()
               if x.strip()]
    else:
        ids = list(counts)

    todo = [v for v in ids if not has_captions(a.workdir, v)]
    skip_whole = [v for v in todo if v in whole_video and v not in floor]
    if skip_whole:
        todo = [v for v in todo if v not in whole_video or v in floor]
        print(f"{len(skip_whole):,} recordings skipped: the title names the "
              "bill, so the whole\nrecording is that one proceeding and there "
              "is no boundary to find.\nMostly committees of conference.")
    if a.only_floor:
        todo = [v for v in todo if v in floor]
    todo.sort(key=lambda v: (0 if (a.floor_first and v in floor) else 1,
                             -counts.get(v, 0)))
    if a.limit:
        todo = todo[:a.limit]

    already = len(ids) - len([v for v in ids if not has_captions(a.workdir, v)])
    print(f"{len(ids):,} recordings known, {already:,} already have captions")
    print(f"{len(todo):,} to fetch, "
          f"{sum(1 for v in todo if v in floor):,} of them floor sessions")
    if a.source != "captions":
        print(f"\n  --source {a.source}: whisper transcribes locally, "
              f"{len(todo)} recordings.")
        print("  How long that takes depends on the model, the device and "
              "the machine,\n  so the first one is timed and the rest "
              "projected from it rather than\n  guessed at here.")
        if not a.model:
            print("\n  No --model given. The small ones are usually enough: "
                  "the phrases\n  being looked for are ordinary English, and "
                  "a bill number only has to\n  pick one out of the handful "
                  "the docket scheduled. Try --model base.")
        print("\n  Ctrl-C now if that was not intended.\n")
        time.sleep(5)
    if a.dry_run:
        for v in todo[:20]:
            print(f"  {v}  {counts.get(v, 0):>4} bill appearances"
                  + ("   floor" if v in floor else ""))
        # Whisper is hours per recording, so this is a decision rather than a
        # queue. A floor session carrying two hundred bills earns it; a hearing
        # carrying three almost certainly does not.
        big = [v for v in todo if counts.get(v, 0) >= 20]
        small = [v for v in todo if counts.get(v, 0) < 20]
        if big or small:
            print(f"\n  {len(big)} carry 20 bills or more -- those are worth "
                  f"transcribing.\n  {len(small)} carry fewer; between them "
                  f"{sum(counts.get(v, 0) for v in small)} bill appearances, "
                  "which may not be\n  worth the hours.")
        print(f"\n--dry-run: nothing fetched.")
        return

    t0 = time.time()
    ok = fail = 0
    misses = []
    stopped = ""
    # Ctrl-C is a normal way to end a run that reports a time remaining in
    # hours. Letting it raise threw away the summary and the list of
    # recordings that will never have captions -- the only two things the run
    # had produced.
    try:
        _run(todo, a, tool, use_manifest, misses, t0, counts)
    except KeyboardInterrupt:
        stopped = "stopped by hand"
    ok = sum(1 for v in todo if has_captions(a.workdir, v))
    _report(ok, misses, t0, stopped)
    return


def _run(todo, a, tool, use_manifest, misses, t0, counts_of=None):
    import sys as _s
    counts_of = counts_of or {}
    ok = fail = 0
    for i, vid in enumerate(todo, 1):
        # --video=ID rather than --video ID. A YouTube id may begin with a
        # hyphen -- "-IqRWnHKSlQ" is one of these -- and argparse reads that as
        # a flag and rejects the whole call. The joined form has no such
        # ambiguity.
        cmd = [sys.executable, str(tool), f"--video={vid}",
               "--source", a.source, "--workdir", a.workdir]
        if a.model:
            cmd += ["--model", a.model]
        if a.device:
            cmd += ["--device", a.device]
        if Path(use_manifest).exists():
            cmd += ["--manifest", use_manifest]
        started = time.time()
        # Whisper on one recording can run for hours with nothing on screen,
        # which is indistinguishable from a hang -- the same defect this
        # project has shipped four times. Say what is being worked on before
        # starting it, not only after it finishes.
        if a.source != "captions":
            _s.stdout.write(f"\r  {i}/{len(todo)}  transcribing {vid} "
                            f"({counts_of.get(vid, 0)} bill appearances) "
                            "-- this takes a while   ")
            _s.stdout.flush()
        try:
            r = child.run(cmd, capture_output=True, text=True,
                               timeout=a.timeout)
            good = r.returncode == 0 and has_captions(a.workdir, vid)
            why = "" if good else (
                (r.stderr or r.stdout or "").strip().splitlines() or ["no output"]
            )[-1][:70]
        except subprocess.TimeoutExpired:
            good, why = False, f"took longer than {a.timeout:g}s"
        except Exception as e:
            good, why = False, f"{type(e).__name__}: {e}"

        # A recording whose captions are switched off will never have them,
        # however long we wait. Counting that toward "the far end is unhappy"
        # stopped a 95-video run after 47 because five such recordings happened
        # to fall together -- and the run had been working perfectly.
        permanent = bool(why) and (
            "no captions available" in str(why).lower()
            or "captions are disabled" in str(why).lower())

        if good:
            ok += 1
            fail = 0
        else:
            if not permanent:
                fail += 1
            misses.append((vid, why))
            print(f"\n  {vid} failed: {why}"
                  + ("  (permanent; not counted toward stopping)"
                     if permanent else ""), flush=True)
            if fail >= a.stop_after:
                print(f"\n{fail} in a row failed for reasons that are not "
                      "'no captions'.\nStopping rather than hammering it. What "
                      "succeeded is on disk; run\nagain to carry on.")
                break

        done = time.time() - t0
        left = hms(done / i * (len(todo) - i))
        nocap = sum(1 for _, w in misses if "no captions" in str(w).lower())
        _s.stdout.write(
            f"\r  {i}/{len(todo)}  {ok} fetched, {len(misses)} failed"
            + (f" ({nocap} have none at all)" if nocap else "")
            + f"  {hms(done)} gone, {left} left  {vid}   ")
        _s.stdout.flush()
        if i < len(todo):
            time.sleep(a.delay)


def _report(ok, misses, t0, stopped):
    if stopped:
        print(f"\n\n{stopped}.")
    print(f"\n{ok:,} recordings now have captions "
          f"(this run took {hms(time.time() - t0)})")
    if misses:
        print(f"{len(misses):,} failed:")
        for vid, why in misses[:6]:
            print(f"  {vid}  {why}")
        # Written down, because a list printed to a terminal at the end of a
        # two-hour run is a list that gets lost. These are the ones that need
        # whisper, and whisper is hours each -- so the list is the input to a
        # decision about which are worth it, not a queue to run blindly.
        nocap = [v for v, w in misses if "caption" in w.lower()]
        if nocap:
            Path("no_captions.txt").write_text("\n".join(nocap) + "\n",
                                               encoding="utf-8")
            print(f"\n{len(nocap):,} have no captions at all -> "
                  "no_captions.txt")
            print("  Those need --source whisper, which runs locally over "
                  "hours per\n  recording. Worth doing for a floor session "
                  "carrying two hundred\n  bills; probably not for a hearing "
                  "carrying three.")
    print("\nThen: python3 probe_alignment.py --suggest")


if __name__ == "__main__":
    main()
