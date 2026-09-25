#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.2
"""
Whether a recording's captions reach the end of the recording.

    python3 caption_span.py            # every recording whose captions stop short
    python3 caption_span.py --write    # refresh caption_spans.json from work/
    python3 caption_span.py --check    # does caption_spans.json agree with work/?

No network. Reads work/<video>/ and videos_*.csv; only --write writes, and
only caption_spans.json.

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

ON A MACHINE WITHOUT THE CAPTIONS (25 September 2026)

The nightly moved to a machine that starts empty every night and is given a
kit of 1.9 GB, not the 20 GB of caption files. Without them this compared
nothing, and 156 times on 13 recordings -- 89 a chair stated, 67 clustered --
would have been published from tracks known to run about an hour late, under
one printed line nobody reads at two in the morning.

So the answer travels instead of the files. caption_spans.json holds, for
every recording whose captions were read, what last_cue said and the size and
date of the files it said it from. segment_markers.py --all writes it after
every run, because that is the step that reads every caption file anyway, and
--write does the same by hand. It MERGES: a folder with no caption file on
this machine keeps the entry made where its captions are, because a machine
missing the captions is not evidence that they stopped anywhere.

out_of_step reads a caption file where there is one and the summary where
there is not. Where a summary is in use and a recording with times has
neither, nothing can vouch for its clock, and build_site_v2 withholds its
times like a late track's and says so: a summary that has fallen behind the
captions costs a few "start not identified" lines, never an hour-early start.
On the laptop, where both exist, --check says whether they agree, and
preflight holds them to it.
"""

import csv
import json
import os
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

# What travels in the nightly's kit in place of the caption files: see the
# docstring. Relative to the working folder, like work/.
SUMMARY = "caption_spans.json"

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


def caption_files(folder):
    """{name: [size, mtime]} for each of WORK_FILES in the folder: what
    last_cue reads, and what says whether an answer read off it is current."""
    out = {}
    for name in WORK_FILES:
        f = Path(folder) / name
        if f.exists():
            st = f.stat()
            out[name] = [st.st_size, int(st.st_mtime)]
    return out


def load_summary(path=SUMMARY):
    """{video: {"last": seconds or None, "files": {...}}}, or None when there
    is no summary at all -- which is not the same as an empty one.

    A summary that will not parse stops whatever asked: the answer it would
    have given is the one thing standing between an hour-late track and the
    page, and carrying on without it is how 156 times get published."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise SystemExit(f"{p} will not read ({e}). Rewrite it where the "
                         f"captions are: python3 caption_span.py --write")
    rec = doc.get("recordings") if isinstance(doc, dict) else None
    if not isinstance(rec, dict):
        raise SystemExit(f"{p} has no 'recordings' table. Rewrite it where the "
                         f"captions are: python3 caption_span.py --write")
    return rec


def write_summary(work="work", path=SUMMARY):
    """Refresh the summary from every caption file under work/. (read, kept).

    MERGED, never rebuilt: a folder with no caption file here keeps the entry
    made where its captions were, because a machine that lacks the files --
    the nightly's, which is given the summary instead of them -- would
    otherwise write "no captions" over every recording it was never given.
    Written whole and then moved into place, so a reader never meets half.
    """
    old = load_summary(path) or {}
    new = dict(old)
    read = 0
    root = Path(work)
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            files = caption_files(d)
            if not files:
                continue
            new[d.name] = {"last": last_cue(d), "files": files}
            read += 1
    doc = {"about": ("Where each recording's captions stop, for a machine that "
                     "does not hold the caption files. Written by caption_span.py "
                     "--write and by segment_markers.py --all; read by "
                     "build_site_v2.withhold_late_captions. See caption_span.py."),
           "recordings": new}
    p = Path(path)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    os.replace(tmp, p)
    return read, len(new) - read


# out_of_step's default for spans: read SUMMARY from the working folder if it
# is there. A caller asking where captions stop is asking the same question
# whether this machine holds the caption files or only their summary.
_FROM_DISK = object()


def out_of_step(vids, work="work", slack=SLACK, known=None, spans=_FROM_DISK,
                report=None, files=True):
    """({video: (last_cue, duration)}, compared, undated).

    The first is every recording whose captions stop more than `slack`
    seconds before it does. A recording with no caption file is not
    compared, since nothing was read off it. One WITH captions and no
    published duration cannot be compared either, and is counted in
    `undated` rather than passed as though it had been -- a guard that
    checked nothing and said nothing looks exactly like a guard that passed.

    `spans` is the summary: by default SUMMARY as it stands in the working
    folder, None for none, or a table from load_summary. Where a recording
    has no caption file here, its entry answers in the file's place. Where it
    has neither and a summary is in use, nothing here can say where its
    captions stop: it is named in report["unsummarised"], for the caller to
    withhold, and report["from_summary"] counts the answers the summary gave.
    files=False answers from the summary alone, as the nightly's machine
    would.
    """
    if spans is _FROM_DISK:
        spans = load_summary()
    known = durations() if known is None else known
    late, compared, undated = {}, 0, []
    from_summary, unsummarised = 0, []
    for v in sorted(vids):
        folder = Path(work) / v
        if spans is not None and not (files and caption_files(folder)):
            entry = spans.get(v)
            if not isinstance(entry, dict):
                unsummarised.append(v)
                continue
            last = entry.get("last")
            from_summary += 1
        else:
            last = last_cue(folder)
        if last is None:
            continue
        dur = known.get(v)
        if not dur:
            undated.append(v)
            continue
        compared += 1
        if dur - last > slack:
            late[v] = (last, dur)
    if report is not None:
        report["from_summary"] = from_summary
        report["unsummarised"] = unsummarised
    return late, compared, undated


def check_summary(work="work", path=SUMMARY, known=None):
    """Where the summary and the caption files disagree: [(video, what)].

    For a machine that holds both. Every recording with a caption file here
    must have an entry naming the same files at the same sizes and dates and
    giving the same answer, or the nightly -- which has only the summary --
    is checking something other than what is on this disk.
    """
    spans = load_summary(path)
    if spans is None:
        return [("", f"there is no {path}")]
    bad = []
    root = Path(work)
    vids = [d.name for d in sorted(root.iterdir()) if d.is_dir()] \
        if root.is_dir() else []
    for v in vids:
        files = caption_files(root / v)
        if not files:
            continue
        e = spans.get(v)
        if not isinstance(e, dict):
            bad.append((v, "has captions here and no entry"))
        elif e.get("files") != files:
            bad.append((v, f"entry names {e.get('files')}, the folder holds {files}"))
        elif e.get("last") != last_cue(root / v):
            bad.append((v, f"entry says {e.get('last')}, the captions say "
                           f"{last_cue(root / v)}"))
    # And the answer the build acts on: the same recordings late whether the
    # files are read or the summary is.
    known = durations() if known is None else known
    have = [v for v in vids if v in spans and caption_files(root / v)]
    by_files = set(out_of_step(have, work, known=known, spans=None)[0])
    by_summary = set(out_of_step(have, work, known=known, spans=spans,
                                 files=False)[0])
    if by_files != by_summary:
        bad.append(("", f"late by the files: {sorted(by_files - by_summary)}; "
                        f"late by the summary: {sorted(by_summary - by_files)}"))
    return bad


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
    ap.add_argument("--summary", default=SUMMARY,
                    help=f"the summary the nightly reads (default {SUMMARY})")
    ap.add_argument("--write", action="store_true",
                    help="refresh the summary from the caption files here, "
                         "keeping the entries of recordings whose files are not")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 unless the summary agrees with the caption "
                         "files here, recording by recording")
    a = ap.parse_args()

    root = Path(a.work)
    if not root.is_dir():
        raise SystemExit(f"No {root}/ here. Run this from the repository root.")
    if a.write:
        read, kept = write_summary(a.work, a.summary)
        print(f"{a.summary}: {read:,} recordings read from their caption files, "
              f"{kept:,} kept from where their captions are, "
              f"{Path(a.summary).stat().st_size:,} bytes")
        return
    if a.check:
        bad = check_summary(a.work, a.summary)
        spans = load_summary(a.summary) or {}
        if bad:
            print(f"{a.summary} disagrees with {a.work}/ in {len(bad):,} "
                  "place(s):")
            for v, what in bad[:20]:
                print(f"  {v}  {what}")
            print("Rewrite it here: python3 caption_span.py --write")
            raise SystemExit(1)
        print(f"{a.summary} agrees with every caption file under {a.work}/: "
              f"{len(spans):,} recordings, and the same ones late read either way")
        return
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
