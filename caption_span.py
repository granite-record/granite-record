#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.1
"""
Whether a recording's captions reach the end of the recording.

    python3 caption_span.py          # every recording whose captions stop short

No network, and nothing written. Reads work/<video>/ and videos_*.csv.

WHY THIS EXISTS

On 10 September nine recordings of 2024-2026 carried a YouTube caption track
that ends an hour before the video does, and the track is not short -- it is
late. Its clock starts an hour into the recording, so everything read off it
lands an hour early: the boundary a chair stated, which the page draws as the
chair's own moment, and the clustering estimate beside it. 74 published starts
on those nine were an hour out. Measured three ways, none of them the captions:

  The bench.    HB1130's hearing in House Judiciary on 28 January 2026 was
                published at 0:17:26 to 0:58:26 and timed by hand at 1:17:48
                to 1:58:29 -- 3,622 seconds out at the start, 3,603 at the end.
  The chair.    "It's 10 o'clock, but I'm going to wait" sits 1:30 into the
                captions of a Judiciary stream that began at 8:58. "It is
                10:00 a.m. I'm going to call the..." sits 14:42 into one that
                began at 8:45, and "it's 2:30 and I'm going to open the" hearing
                on HB1089, scheduled for 2:30, lands at 1:30 on the same clock.
  The schedule. On the four Judiciary recordings nearly every hearing a chair
                opened lands 10 to 90 minutes BEFORE its scheduled time, which is
                not how hearings run. Moved an hour later, all but two land
                within fifty minutes after it, which is.

A CAPTION FILE CANNOT SAY THIS ABOUT ITSELF

YouTube's json3 opens with a window event whose length is exactly the end of
its last cue -- 56 of 56 files sampled -- so a track knows its own span and
nothing about the recording's. The duration YouTube published for the video,
in the channel index, is the only thing that does. So the guard is one
comparison: where the captions stop, against where the recording stops.

WHERE THE LINE IS

A room goes quiet before the stream stops, and the captions stop with it. Of
3,628 recordings with both, 3,538 end within five minutes of their video and
32 end more than fifteen minutes early. House Ways and Means on 7 February
2023 ends 45 minutes early and is NOT shifted: the chair's "just past one
o'clock" lands at 13:01 on the caption clock. A track that starts an hour late
cannot end less than an hour early -- its last cue and the hour it is missing
both have to fit inside the recording. The line sits between the two, at fifty
minutes. Seventeen recordings are past it: sixteen stop an hour short or more,
give or take a second, and the other is a local whisper transcript at
fifty-seven.

WHAT THIS DOES NOT DO

It does not move anything by an hour. The shift looks like exactly 3,600
seconds on every recording measured, and it may well be -- but that is a new
way of producing a timestamp, and nothing about timestamps goes on the site
until it has been scored against times a person took. Until then a late
track's recordings fall back to the schedule, which comes from the stream's
own clock and not from its captions.
"""

import csv
import json
import re
from pathlib import Path

# The same files, in the same order, that segment_markers.read_words tries --
# the question is whether the track the times were read from is in step.
from segment_markers import WORK_FILES

# Past this, a track is out of step with its recording. See the docstring for
# why fifty minutes and not fifteen or sixty.
SLACK = 50 * 60

# The end of a file holds its last cues: they are written in time order, and
# yt-dlp writes json3 a field to a line, so 64 KB is a few minutes of speech.
TAIL = 1 << 16

ISO = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")
# The opening of one cue: json3's {"tStartMs": ...} or whisper's {"start": ...}.
# A word inside a cue is {"utf8": ...} and does not match.
CUE = re.compile(r'\{\s*"(?:tStartMs|start)"\s*:')


def seconds(iso):
    """'PT7H23M41S' -> 26621. None for anything else, including ''."""
    m = ISO.match(iso or "")
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def durations(pattern="videos_*.csv"):
    """{video_id: seconds}, as YouTube published them in the channel index."""
    out = {}
    for f in sorted(Path(".").glob(pattern)):
        with open(f, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                s = seconds(r.get("duration_iso"))
                if s and r.get("video_id"):
                    out[r["video_id"]] = s
    return out


def _end(cue):
    """Where one cue ends, in seconds, or None if it says nothing."""
    if not isinstance(cue, dict):
        return None
    if "tStartMs" in cue:
        # The opening window and the bare line breaks carry no words. The
        # window spans the whole track, so counting it would answer the
        # question with the thing being asked about.
        if not any((s.get("utf8") or "").strip() for s in cue.get("segs") or []):
            return None
        return (cue["tStartMs"] + (cue.get("dDurationMs") or 0)) / 1000.0
    if "start" in cue and str(cue.get("text") or "").strip():
        return float(cue.get("end") or cue["start"])
    return None


def _last(text):
    dec = json.JSONDecoder()
    last = None
    for m in CUE.finditer(text):
        try:
            cue, _ = dec.raw_decode(text, m.start())
        except ValueError:
            continue            # the cue the tail cut in half
        e = _end(cue)
        if e is not None and (last is None or e > last):
            last = e
    return last


def last_cue(folder):
    """Seconds into the recording at which its captions stop, or None.

    Only the tail is read, which is what makes this cheap enough to run on
    every build: the whole of work/ is tens of gigabytes. The whole file is
    read only when its tail holds no words at all.
    """
    for name in WORK_FILES:
        f = Path(folder) / name
        if not f.exists():
            continue
        size = f.stat().st_size
        with open(f, "rb") as fh:
            fh.seek(max(0, size - TAIL))
            got = _last(fh.read().decode("utf-8", errors="replace"))
        if got is None and size > TAIL:
            got = _last(f.read_text(encoding="utf-8", errors="replace"))
        if got is not None:
            return got
    return None


def out_of_step(vids, work="work", slack=SLACK, known=None):
    """({video: (last_cue, duration)}, compared, undated).

    The first is every recording whose captions stop more than `slack`
    seconds before it does. A recording with no caption file is not
    compared, since nothing was read off it. One WITH captions and no
    published duration cannot be compared either, and is counted in
    `undated` rather than passed as though it had been -- a guard that
    checked nothing and said nothing looks exactly like a guard that passed.
    """
    known = durations() if known is None else known
    late, compared, undated = {}, 0, []
    for v in sorted(vids):
        last = last_cue(Path(work) / v)
        if last is None:
            continue
        dur = known.get(v)
        if not dur:
            undated.append(v)
            continue
        compared += 1
        if dur - last > slack:
            late[v] = (last, dur)
    return late, compared, undated


def hms(sec):
    sec = int(round(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Which recordings' captions stop well before the recording does.")
    ap.add_argument("--work", default="work")
    ap.add_argument("--slack", type=float, default=SLACK / 60,
                    help="minutes short before a track counts as out of step "
                         f"(default {SLACK // 60})")
    a = ap.parse_args()

    root = Path(a.work)
    if not root.is_dir():
        raise SystemExit(f"No {root}/ here. Run this from the repository root.")
    vids = [d.name for d in root.iterdir() if d.is_dir()]
    late, compared, undated = out_of_step(vids, a.work, a.slack * 60)
    try:
        import proceedings as P
        rows = {v: len(rs) for v, rs in P.by_video(P.load()).items()}
    except Exception:                                   # noqa: BLE001
        rows = {}

    print(f"{compared:,} recordings compared: where their captions stop, "
          "against the length YouTube published.")
    if undated:
        print(f"{len(undated):,} have captions and no published length, so were "
              f"not compared, e.g. {', '.join(undated[:3])}")
    print(f"{len(late):,} stop more than {a.slack:.0f} minutes short, and "
          "build_site_v2 publishes no time read from their captions:\n")
    for v, (last, dur) in sorted(late.items(), key=lambda kv: kv[1][0] - kv[1][1]):
        n = rows.get(v, 0)
        print(f"  {v}  captions stop at {hms(last)} of {hms(dur)}, "
              f"{(dur - last) / 60:.0f} min short"
              + (f"   {n} proceeding{'s' if n != 1 else ''}" if n else ""))


if __name__ == "__main__":
    main()
