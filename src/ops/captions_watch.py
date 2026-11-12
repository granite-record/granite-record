#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.3
"""
When the captions route has been silent for too long. Read-only: it reads
files that are already on this disk and writes nothing, asks nobody anything.

    python3 src/ops/captions_watch.py [--root FOLDER] [--now ISO]

Three silences, each a warning in a sentence and never a failure (the exit
status is 0 whatever it finds), for the morning triage and a person to read:

  the laptop's job   logs/captions-inbox.log has no run in more than
                     JOB_SILENT_DAYS (2) days: the 7:30 pm Task Scheduler job
                     has not run, or has not been able to write its line.
  the canary         logs/captions-canary.log has no passing line ("CANARY ok")
                     in more than CANARY_SILENT_DAYS (8) days, or does not
                     exist: the weekly proof of the route (livestreams.py
                     --canary) has not passed, so yt-dlp, node, the solver or
                     YouTube may have drifted while nothing waited.
  a recording        waiting_long(): a finished recording that has waited for
                     its captions, or was read and has no timestamp on the
                     record (no row of proceedings.csv names it), for more than
                     WAIT_NIGHTS (3) nights. The audit of 12 November 2026 found
                     three recordings of 29 and 30 October read and not placed
                     with nothing saying so. Some are committees that took up no
                     bill, which no timestamp could be for; the sentence says so
                     and leaves the judgment to a reader.

The night calls waiting_long() in its verdict (nightly.not_moving), where it
is a warning of the "record not moving" kind, which never holds a night. The
two laptop logs are not in the bucket, so the first two are for the laptop
and the morning triage, which runs there.

Standard library only; the clock is passed in, never read here.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import json
import re
from datetime import datetime, timedelta, timezone

JOB_SILENT_DAYS = 2
CANARY_SILENT_DAYS = 8
WAIT_NIGHTS = 3
WAIT_MOST_DAYS = 30        # nightly.CAPTION_WAIT_MOST: older is the archive's, not this week's
# nightly.CAPTIONS_WAITING, which preflight holds this equal to.
CAPTIONS_WAITING = ("waiting", "deferred", "failed", "for-laptop", "none-yet")
JOB_LOG = "logs/captions-inbox.log"
CANARY_LOG = "logs/captions-canary.log"

_STAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\b")


def when(text):
    """A UTC datetime from "2026-11-12T00:30:01Z" (or an offset form), or None."""
    try:
        d = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def last_stamp(text, keep=lambda line: True):
    """The newest leading timestamp among the lines of `text` that `keep`."""
    best = None
    for line in (text or "").splitlines():
        m = _STAMP.match(line)
        if m and keep(line):
            d = when(m.group(1))
            if d and (best is None or d > best):
                best = d
    return best


def job_silent(log_text, now):
    """[sentence]: the laptop's evening job has not written a run's first line
    to its log for more than JOB_SILENT_DAYS days, or has no log."""
    at = last_stamp(log_text)
    if at is None:
        return ["The laptop's captions job has no run on record: logs/captions-inbox.log is "
                "missing or has no timed line, so whether the 7:30 pm Task Scheduler job runs "
                "is not known."]
    days = (now - at).total_seconds() / 86400
    if days <= JOB_SILENT_DAYS:
        return []
    return [f"The laptop's captions job has not reported since {at:%Y-%m-%d %H:%M} UTC "
            f"({days:.0f} days): the 7:30 pm Task Scheduler job did not run, or the laptop was "
            "off or signed out. logs/captions-inbox.log there says what it last did."]


def canary_silent(log_text, now):
    """[sentence]: no passing canary line ("CANARY ok") in more than
    CANARY_SILENT_DAYS days, or none at all. A "skipped" or "FAIL" line is not
    a pass, and says why in the sentence when it is the newest."""
    ok = last_stamp(log_text, lambda ln: " CANARY ok " in ln + " ")
    if ok is not None and (now - ok).total_seconds() / 86400 <= CANARY_SILENT_DAYS:
        return []
    newest = ""
    lines = [ln for ln in (log_text or "").splitlines() if _STAMP.match(ln) and " CANARY " in ln]
    if lines:
        newest = f" Its newest line: {lines[-1][:200]}"
    return [("The captions canary has not passed since " + (f"{ok:%Y-%m-%d}" if ok else "ever")
             + f" (more than {CANARY_SILENT_DAYS} days): the weekly proof that YouTube still "
             "answers the laptop with captions that read has not been run, or failed."
             " (python3 -X utf8 src\\ops\\livestreams.py --canary)" + newest)]


def waiting_long(st, placed, now, waiting_too=True):
    """[sentence] from the livestream state `st` ({"videos": {id: entry}}):
    finished recordings more than WAIT_NIGHTS days and at most WAIT_MOST_DAYS
    days old that

      - are still waiting for captions (the state's "captions" in
        CAPTIONS_WAITING, not adopted), and
      - were read ("captions": "captioned") and are in no row of proceedings.csv:
        `placed`, the set of its video_ids, or None where that file is not on
        this machine, which leaves this second part out rather than call every
        recording unplaced.

    `waiting_too` False leaves the first half out: the night already warns of
    those (nightly.KIND_CAPTIONS_WAIT), and a second kind for the same
    recordings would be news to the gate.

    Never fails a night: a sentence per kind, naming up to three titles."""
    if not isinstance(st, dict) or not isinstance(st.get("videos"), dict):
        return []
    waiting, unplaced = [], []
    for vid, v in st["videos"].items():
        if not isinstance(v, dict) or v.get("status") != "finished" or v.get("adopted"):
            continue
        ended = when(v.get("ended") or v.get("seen"))
        if ended is None:
            continue
        age = now - ended
        if not timedelta(days=WAIT_NIGHTS) < age <= timedelta(days=WAIT_MOST_DAYS):
            continue
        title = str(v.get("title") or vid)
        if v.get("captions") in CAPTIONS_WAITING:
            if not waiting_too:
                continue
            waiting.append((ended, title))
        elif v.get("captions") == "captioned" and placed is not None and vid not in placed:
            unplaced.append((ended, title))

    def names(rows):
        rows = sorted(rows)
        return "; ".join(t for _e, t in rows[:3]) + (f"; and {len(rows) - 3} more"
                                                      if len(rows) > 3 else "")
    out = []
    if waiting:
        n = len(waiting)
        out.append(f"{n} recording{'s' if n != 1 else ''} finished more than {WAIT_NIGHTS} nights "
                   f"ago {'still wait' if n != 1 else 'still waits'} for captions: {names(waiting)}.")
    if unplaced:
        n = len(unplaced)
        out.append(f"{n} recording{'s' if n != 1 else ''} finished more than {WAIT_NIGHTS} nights "
                   f"ago {'were' if n != 1 else 'was'} read from captions and "
                   f"{'have' if n != 1 else 'has'} no timestamp on the record: {names(unplaced)}. "
                   "A committee that took up no bill has none to give; any other is worth a look.")
    return out


def placed_ids(path):
    """The set of video_ids proceedings.csv names, or None where it is not
    there or will not read."""
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return {r.get("video_id") for r in csv.DictReader(fh) if r.get("video_id")}
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


def _text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def report(root, now):
    """Every sentence the three silences give for the working folder `root`."""
    root = Path(root)
    out = job_silent(_text(root / JOB_LOG), now) + canary_silent(_text(root / CANARY_LOG), now)
    try:
        st = json.loads(_text(root / "archive" / "livestreams.json") or "null")
    except ValueError:
        st = None
    out += waiting_long(st, placed_ids(root / "proceedings.csv"), now)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--root", default=str(_paths.ROOT))
    ap.add_argument("--now", help="the time to act as of (ISO), for tests")
    a = ap.parse_args(argv)
    now = when(a.now) if a.now else datetime.now(timezone.utc)
    said = report(a.root, now)
    for s in said:
        print("WARNING: " + s)
    print(f"CAPTIONS WATCH: {len(said)} warning{'s' if len(said) != 1 else ''} "
          "(none of them a failure)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
