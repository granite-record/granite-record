#!/usr/bin/env python3
"""
The one worker for the General Court: run its fetches one after another.

    python3 watchers/gc_lane.py            # from the repository root
    tail -f logs/gc_lane.log

Reads watchers/gc_lane.queue, one fetch per line (the script and its
arguments, as they would follow "python3"), and runs them in order. A line
already run is recorded in logs/gc_lane.done and never run twice, so a lane
that is stopped and started again picks up where it was. Lines may be added to
the queue while the lane runs; when it runs out it waits for more, and gives up
after IDLE_HOURS with nothing new.

WHY A LANE AND NOT A CHAIN OF COMMANDS

Two fetches at once is what got this address blocked the second time, and the
fetchers do not all honour archive/.lock: fetch_archive_docket,
fetch_sponsors_by_member, fetch_rollcall_parties and fetch_legislation neither
take it nor look at it. So the rule has to be held from outside them. This
holds the lock for as long as it runs, and touches it every minute --
fetch_calendar_archive deletes a lock more than an hour old, and nothing else
refreshed one, so any run longer than an hour could be joined by a second
worker. A step that takes the lock itself is written with "handover " in front
of it, and the lane lets go of the lock for exactly that step.

WHY IT STOPS RATHER THAN CARRIES ON

A step that exits non-zero ends the lane. For every fetcher here that means
the address said no, or the run broke -- and either way the next step starting
fifteen seconds later is the behaviour refusal.py exists to prevent. And
before every step the lane looks for archive/refused.json and stops if it is
there at all, whatever its age: refusal.check() lets a fetcher resume after
twenty-four hours, but a lane nobody is watching should not be the thing that
decides a refusal is over. Clearing one is a person's decision.

No network of its own. It asks the General Court for nothing that the steps
in its queue do not.
"""

import os
import pathlib
import re
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path.cwd()
if not (ROOT / "refusal.py").exists():
    sys.exit(f"run this from the repository root; {ROOT} is not it")

LOCK = ROOT / "archive" / ".lock"
REFUSED = ROOT / "archive" / "refused.json"
QUEUE = ROOT / "watchers" / "gc_lane.queue"
LOGS = ROOT / "logs"
DONE = LOGS / "gc_lane.done"
LOG = LOGS / "gc_lane.log"
IDLE_HOURS = 12          # an empty queue for this long ends the lane
HEARTBEAT = 60           # seconds between touches of the lock


def say(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def queued():
    """The queue's steps, in order, comments and blanks dropped."""
    if not QUEUE.exists():
        return []
    out = []
    for ln in QUEUE.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            out.append(ln)
    return out


def done():
    if not DONE.exists():
        return set()
    return {ln.strip() for ln in DONE.read_text(encoding="utf-8").splitlines()
            if ln.strip()}


class Lock:
    """archive/.lock, held and kept fresh; released for a handover step."""

    def __init__(self):
        self.held = False
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._beat, daemon=True)
        self._t.start()

    def take(self):
        LOCK.parent.mkdir(exist_ok=True)
        LOCK.write_text(str(os.getpid()), encoding="utf-8")
        self.held = True

    def release(self):
        self.held = False
        LOCK.unlink(missing_ok=True)

    def _beat(self):
        while not self._stop.wait(HEARTBEAT):
            if self.held and LOCK.exists():
                try:
                    os.utime(LOCK, None)
                except OSError:
                    pass

    def close(self):
        self._stop.set()
        self.release()


def slug(step):
    words = re.findall(r"[A-Za-z0-9]+", step.replace(".py", ""))
    return "_".join(words[:6])[:60] or "step"


def main():
    LOGS.mkdir(exist_ok=True)
    if LOCK.exists():
        age = (time.time() - LOCK.stat().st_mtime) / 60
        pid = LOCK.read_text(encoding="utf-8", errors="replace").strip()
        say(f"archive/.lock is already there (pid {pid}, touched {age:.0f} "
            f"minutes ago). Another worker may be running; this lane will not "
            f"start a second one. A person should look before removing it.")
        return 2

    lock = Lock()
    lock.take()
    say(f"lane started, pid {os.getpid()}, holding archive/.lock")
    idle_since = None
    n = 0
    try:
        while True:
            if REFUSED.exists():
                say("archive/refused.json is on file. Stopping the lane: a "
                    "refusal is a fact about the address, and clearing one is "
                    "a person's decision (netcheck.py, then refusal.py --clear).")
                return 3
            todo = [s for s in queued() if s not in done()]
            if not todo:
                if idle_since is None:
                    idle_since = time.time()
                    say(f"queue empty; waiting up to {IDLE_HOURS}h for more")
                if time.time() - idle_since > IDLE_HOURS * 3600:
                    say(f"nothing new for {IDLE_HOURS}h. Stopping.")
                    return 0
                time.sleep(300)
                continue
            idle_since = None
            step = todo[0]
            handover = step.startswith("handover ")
            args = step[len("handover "):].split() if handover else step.split()
            n += 1
            log = LOGS / f"gc_{time.strftime('%m%d_%H%M')}_{slug(' '.join(args))}.log"
            say(f"step {n}: python3 {' '.join(args)}"
                + ("  (hands the lock over)" if handover else "")
                + f"  -> {log.name}")
            if handover:
                lock.release()
            t0 = time.time()
            # Unbuffered, so the step's log shows where it has got to. A child
            # writing to a file buffers otherwise, and a fetch that prints its
            # first line after a hundred requests looks exactly like a hang.
            with log.open("w", encoding="utf-8") as fh:
                rc = subprocess.call([sys.executable, *args], cwd=str(ROOT),
                                     stdout=fh, stderr=subprocess.STDOUT,
                                     env={**os.environ, "PYTHONUNBUFFERED": "1"})
            if handover:
                if LOCK.exists():
                    say("the handed-over step left archive/.lock behind. "
                        "Stopping rather than guessing whose it is.")
                    return 4
                lock.take()
            mins = (time.time() - t0) / 60
            tail = [ln for ln in log.read_text(encoding="utf-8",
                                               errors="replace").splitlines()
                    if ln.strip()][-3:]
            if rc != 0:
                say(f"step {n} ended with status {rc} after {mins:.0f} min. "
                    f"That is the address saying no or the run breaking, and "
                    f"either way the lane stops here. Last lines: "
                    + " | ".join(tail)[:400])
                return rc
            with DONE.open("a", encoding="utf-8") as fh:
                fh.write(step + "\n")
            say(f"step {n} done in {mins:.0f} min. " + " | ".join(tail)[:400])
    finally:
        lock.close()
        say("lane stopped; archive/.lock released")


if __name__ == "__main__":
    sys.exit(main())
