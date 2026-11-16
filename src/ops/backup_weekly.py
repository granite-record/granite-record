#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
The laptop's weekly backup, for Task Scheduler (backup_weekly.xml beside it).

    python3 -X utf8 src/ops/backup_weekly.py              the backup, then a sample
                                                          restore when one is due
    python3 -X utf8 src/ops/backup_weekly.py --dry-run    what each would do: nothing
                                                          sent, restored or recorded
    python3 -X utf8 src/ops/backup_weekly.py --task-xml FILE
                                                          the Task Scheduler entry for
                                                          this checkout, written to FILE
                                                          for schtasks /create /xml

    --local-bucket FOLDER   a folder stands in for the bucket, for testing
    --root FOLDER           the working folder (default: this checkout)

WHY (16 November 2026; the refactor's stage 0, ops items 5 and 6). The laptop's
backup of everything git does not hold went to the bucket when the person ran
it, and nothing said when it last had: the design decided on 24 September 2026
asked for a schedule of its own and a failure that is heard, and it had
neither. This is that job, once a week:

  1. cloud.py backup, which gathers the extras first (cloud.py, THE BACKUP'S
     EXTRAS), tried up to TRIES times, RETRY_MINUTES apart: a build in
     progress refuses it, and a file changed while it read goes with the next
     try, which sends only what the first did not
  2. cloud.py restore --sample SAMPLE_FILES, when the last good sample of the
     bucket is SAMPLE_DAYS old or the last one failed (cloud.py, A SAMPLE
     RESTORE, MONTHLY)
  3. one line, "BACKUP WEEKLY ok" or "BACKUP WEEKLY FAILED -- what", and
     exit 0 or 1

A FAILURE IS HEARD THREE WAYS. Each step records itself under archive/cloud/
(cloud.BACKUP_RECORD, cloud.SAMPLE_RECORD), and this writes a step's failure
there itself when the step could not -- it stopped before its own record, or
never started -- so the record never says a week went well that did not.
cloud.py pull prints both records on every run, a failure as FAILED and an
old one as STALE, and the morning triage reads pull's lines. Task Scheduler's
Last Result is this exit code. And the night warns when the bucket's backup
manifest is two weeks old (nightly.backup_warned), which catches the week
this never ran at all: the laptop off, the task gone, its password changed.

The laptop's alone: refused on GitHub's machine, and outside the repository
that holds secrets.json unless --local-bucket says a test is meant.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import contextlib
import json
import os
import time
from datetime import datetime
from xml.sax.saxutils import escape

import cloud

TRIES = 3
RETRY_MINUTES = 20
# The entry Task Scheduler is given: its template, filled in for the checkout
# by --task-xml, under the name the person registers it as. Found from the
# root, as every file is (CONTRIBUTING.md's rules for a script).
XML = _paths.ROOT / "src" / "ops" / "backup_weekly.xml"
CHECKOUT = "@CHECKOUT@"
TASK_NAME = "Granite Record weekly backup"
LOG = r"logs\backup-weekly.log"


class Tee:
    """A stream that passes everything through and keeps it, for the last line."""

    def __init__(self, out):
        self.out, self.kept = out, []

    def write(self, s):
        self.kept.append(s)
        return self.out.write(s)

    def flush(self):
        self.out.flush()

    def last(self):
        lines = [ln for ln in "".join(self.kept).splitlines() if ln.strip()]
        return lines[-1].strip() if lines else ""


def step(argv):
    """cloud.main(argv) with its output passed through: (exit code, the line
    that says why, where it failed)."""
    out, err = Tee(sys.stdout), Tee(sys.stderr)
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cloud.main(argv)
    return code, err.last() or out.last()


def read(root, rel):
    try:
        d = json.loads(cloud.local(root, rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def failed_unrecorded(root, rel, since, said, what):
    """The step's failure, in its record, when the step did not write one
    since `since`: a record that still says last week went well would be a
    week of silence."""
    rec = read(root, rel)
    if rec and float(rec.get("epoch") or 0) >= since:
        return
    cloud.save_record(root, rel, {"at": datetime.now().isoformat(timespec="seconds"),
                                  "epoch": time.time(), "ok": False, "by": "backup_weekly.py",
                                  "said": f"{what} did not finish: {said or 'it said nothing'}"})


def sample_due(root, now, kind):
    """(due, why): a sample restore is due when there is no record of one of
    this kind of bucket ("r2", or "folder" for a test), the last failed, or it
    is cloud.SAMPLE_DAYS old."""
    rec = read(root, cloud.SAMPLE_RECORD)
    if not rec:
        return True, "none on record"
    if (rec.get("bucket") or {}).get("kind") != kind:
        return True, "the one on record is not of this bucket"
    if not rec.get("ok"):
        return True, "the last one failed"
    days = (now - float(rec.get("epoch") or 0)) / 86400
    if days >= cloud.SAMPLE_DAYS:
        return True, f"the last was {days:.0f} days ago"
    return False, f"the last good one was {days:.0f} days ago, and one is due at {cloud.SAMPLE_DAYS}"


def task_xml(root):
    """The Task Scheduler entry for this checkout, as text: the template with
    the checkout's folder in it and its explanatory comment out."""
    text = XML.read_text(encoding="utf-8")
    head, _, body = text.partition("-->")
    if "<!--" not in head:
        raise SystemExit(f"{XML} is not the template this reads")
    text = '<?xml version="1.0" encoding="UTF-16"?>\r\n' + body.lstrip()
    return text.replace(CHECKOUT, escape(str(Path(root).resolve()), {'"': "&quot;"}))


def write_task_xml(root, dst):
    """FILE for schtasks /create /xml: UTF-16 with its mark, as schtasks exports
    a task, and CRLF lines."""
    text = "\r\n".join(task_xml(root).splitlines()) + "\r\n"
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(text.encode("utf-16"))
    print(f"backup_weekly: the Task Scheduler entry for {Path(root).resolve()} is in {dst}. "
          "To register it, in cmd, as the person who runs the backup (it asks for that "
          "account's Windows password, as the captions inbox's entry needs):")
    print(f'    schtasks /create /tn "{TASK_NAME}" /xml "{dst}" /ru "%USERDOMAIN%\\%USERNAME%" /rp *')


def main(argv=None):
    ap = argparse.ArgumentParser(description="The laptop's weekly backup, and a sample "
                                             "restore when one is due.")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what each step would do; send, restore and record nothing")
    ap.add_argument("--task-xml", metavar="FILE",
                    help="write the Task Scheduler entry for this checkout to FILE, and stop")
    ap.add_argument("--local-bucket", metavar="FOLDER",
                    help="use a folder as the bucket (testing; no credentials)")
    ap.add_argument("--root", help="the working folder (default: this checkout)")
    ap.add_argument("--retry-minutes", type=float, default=RETRY_MINUTES,
                    help=f"minutes between tries of the backup (default {RETRY_MINUTES})")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else _paths.ROOT
    if a.task_xml:
        write_task_xml(root, a.task_xml)
        return 0
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("BACKUP WEEKLY FAILED -- this is the laptop's job, and this is GitHub's machine")
        return 1
    if not a.local_bucket and not cloud.home(root):
        print(f"BACKUP WEEKLY FAILED -- {root} is not the repository that holds secrets.json, "
              "whose files the backup is of; --local-bucket FOLDER for a test")
        return 1
    started = time.time()
    print(f"BACKUP WEEKLY {datetime.now():%Y-%m-%d %H:%M} in {root}"
          + (" (a dry run)" if a.dry_run else ""), flush=True)
    common = ["--root", str(root)] + (["--local-bucket", a.local_bucket] if a.local_bucket else []) \
        + (["--dry-run"] if a.dry_run else [])
    bad = []
    for n in range(1, TRIES + 1):
        code, said = step(["backup", *common])
        if code == 0 or a.dry_run:
            break
        if n < TRIES:
            print(f"  the backup's try {n} of {TRIES} did not finish ({said}); the next in "
                  f"{a.retry_minutes:g} minutes", flush=True)
            time.sleep(a.retry_minutes * 60)
    if code != 0:
        bad.append(f"the backup: {said}")
        if not a.dry_run:
            failed_unrecorded(root, cloud.BACKUP_RECORD, started, said, "the weekly backup")
    due, why = sample_due(root, time.time(), "folder" if a.local_bucket else "r2")
    if due:
        print(f"  a sample restore is due ({why})", flush=True)
        t0 = time.time()
        code, said = step(["restore", "--sample", str(cloud.SAMPLE_FILES), *common])
        if code != 0:
            bad.append(f"the sample restore: {said}")
            if not a.dry_run:
                failed_unrecorded(root, cloud.SAMPLE_RECORD, t0, said, "the sample restore")
    else:
        print(f"  no sample restore this week: {why}", flush=True)
    took = f"{(time.time() - started) / 60:.0f} minutes"
    if bad:
        print(f"BACKUP WEEKLY FAILED -- " + "; ".join(bad) + f" ({took})", flush=True)
        return 1
    print(f"BACKUP WEEKLY ok -- {'nothing sent, a dry run' if a.dry_run else 'sent and recorded'}"
          f" ({took})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
