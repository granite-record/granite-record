#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.1
"""
Put the reversed meridiems right in the manifests that are already built.

    python3 fix_meridiem_manifests.py            # say what would change
    python3 fix_meridiem_manifests.py --apply    # change it

WHY THIS EXISTS AND WHY IT IS ONE-OFF

docket_parser._unslip now corrects a meridiem the clerk typed the wrong way
round -- "Public Hearing: 03/09/2026 12:15 am GP 159" for a hearing that ran
at quarter past noon. Any manifest built from a docket after that change is
right without this script.

Four are not rebuildable. verification_manifest_2017-2018.csv through
_2023-2024.csv were built from a source no longer on this disk: db/Docket.psv
jumps from 2016 to 2025, and Docket.txt carries 2025-2026 only. Rebuilding the
other fifteen and migrating those four would be two paths to one answer, and
the difference between them would be invisible -- so this runs over all
eighteen named manifests, touches only the rows in the window, and leaves the
rest of every file exactly as it found it.

WHAT IT CHANGES, AND WHAT IT MUST NOT

sched_time, and the two columns computed FROM sched_time:

  predicted_offset   seconds from the start of the recording to the scheduled
                     time. Shift the time by twelve hours and leave this, and
                     the manifest says a hearing at 11am starts twelve hours
                     into a two-hour recording.
  watch_url          carries that offset in its &t=.

Both are recomputed with build_manifest's own predicted_offset and hhmmss,
rather than by adding 43,200 to what is there, so this file cannot drift from
the arithmetic the real builder uses.

NOT observed_start, observed_end or notes. Those are the bench's and the
person's -- 35 times somebody marked by watching the video -- and they are
elapsed times into a recording, not clock times, so the correction does not
touch them and neither does this. THE MANIFEST HAS LOST THOSE TWICE.
"""

import argparse
import csv
import glob
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import docket_parser
    from build_manifest import hhmmss, predicted_offset
except ImportError as e:  # pragma: no cover - a missing sibling, not a bug here
    sys.exit(f"needs docket_parser.py and build_manifest.py beside it: {e}")

# Never written by this script. The list is named rather than inlined so that
# adding a column to it is a visible act.
UNTOUCHED = ("observed_start", "observed_end", "notes")


def unslipped(hhmm):
    """The corrected clock time, or None where there is nothing to correct."""
    try:
        h, m = (int(x) for x in hhmm.split(":"))
        t = datetime(2000, 1, 1, h, m).time()
    except (ValueError, AttributeError):
        return None
    if t.hour not in docket_parser._SLIP_HOURS:
        return None
    return t.replace(hour=(t.hour + 12) % 24).strftime("%H:%M")


def fix(path, apply):
    with open(path, newline="", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        cols = r.fieldnames
        rows = list(r)
    if not cols:
        return 0, []

    changed = []
    for row in rows:
        was = (row.get("sched_time") or "").strip()
        now = unslipped(was)
        if not now:
            continue
        before = dict(row)
        row["sched_time"] = now

        # The offset and the link hang off the time, so they move with it.
        start = (row.get("stream_start") or "").strip()
        if start and "predicted_offset" in cols:
            # predicted_offset wants a full timestamp; the manifest keeps only
            # the clock, so the row's own date supplies the day.
            stamp = f"{row.get('sched_date', '')} {start}"
            off = predicted_offset(now, stamp)
            if off is not None:
                row["predicted_offset"] = hhmmss(off)
                if row.get("video_id") and "watch_url" in cols:
                    row["watch_url"] = (
                        f"https://www.youtube.com/watch?v={row['video_id']}"
                        f"&t={max(off - 300, 0)}s")

        for c in UNTOUCHED:
            assert row.get(c) == before.get(c), (
                f"{path}: this script wrote {c}, which is not its to write")
        changed.append((before, row))

    if changed and apply:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    return len(changed), changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the files; without it, only say what would change")
    a = ap.parse_args()

    files = sorted(glob.glob("verification_manifest*.csv"))
    # SILENCE IS NOT SUCCESS. Nineteen manifests are on this disk; a glob that
    # found none would otherwise print a tidy zero and exit happy.
    assert files, "no verification_manifest*.csv here; run this in the repo root"

    total = 0
    for f in files:
        n, changed = fix(f, a.apply)
        total += n
        if not n:
            continue
        print(f"{f}: {n}")
        for before, after in changed[:3]:
            bits = [f"{before['sched_time']} -> {after['sched_time']}"]
            if before.get("predicted_offset") != after.get("predicted_offset"):
                bits.append(f"offset {before['predicted_offset'] or '-'} -> "
                            f"{after['predicted_offset']}")
            print(f"    {after['sched_date']} {after['bill']:8} "
                  f"{(after['committee'] or '')[:28]:28} {'; '.join(bits)}")
        if n > 3:
            print(f"    ... and {n - 3} more")

    print(f"\n{total} reversed meridiems across {len(files)} manifests"
          + ("" if a.apply else " -- nothing written; pass --apply"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
