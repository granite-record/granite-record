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
fetch_calendar_archive used to delete a lock more than an hour old, and nothing
else refreshed one, so any run longer than an hour could be joined by a second
worker. (Since 12 September it takes the lock through refusal.hold() like the
rest, which runs a child of this lane under the lane's lock, and it no longer
needs a handover.) A step that takes the lock itself is written with "handover "
in front of it, and the lane lets go of the lock for exactly that step.

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

GITHUB'S NIGHT (26 September 2026)

Since the laptop stood down, GitHub's machine asks the General Court every
night and early on Monday. On a stood-down laptop the lane asks
refusal.gc_turn() before it starts each step, daily ones included, and stops
at that boundary -- exit 4, the stand-down's status, with the reason in its
log -- inside GitHub's night window (refusal.NIGHT_WINDOWS, the one
definition), in the half hour before it, or when this laptop has not read the
bucket's refusal record since the last window closed, which `python3 cloud.py
pull --changes-only` does. A refusal the night met is in the bucket, not here,
until that read brings it down. It stops rather than waits: a lane that
outlived a night would need that read anyway, and reading the bucket is a
person's command here, not the lane's. A daily step that itself exits 4 while
refusal.gc_turn() says it is GitHub's turn was held, not run: it is not
recorded as today's, and the lane stops. One that exits 4 on a stood-down
laptop when gc_turn() says nothing was stood down for good -- the script
calls refusal.stand_down(), because GitHub runs that job now -- so it is
recorded as run, the log says the line should come out of the queue, and the
lane goes on. A step already
running when the window opens stops at its next request if it asks
refusal.hold().still() before each one, as the lane's fetchers do; one that
does not is not stopped, so a long one is best queued after the window
closes.

A STEP THE WINDOW CUT SHORT IS NOT DONE. It can end 0 (a fetch whose loop
stops early and returns 0), 1 or 3 as easily as 4, so the lane does not read
its status for this: each step is started with refusal.WINDOW_STOP_ENV naming
WINDOW_STOP, which the step's hold writes when the window stops it. A step
that wrote it is recorded in neither logs/gc_lane.done nor
logs/gc_lane.daily, whatever it exited, and the lane stops with 4.

DAILY STEPS

A line written "daily HH:MM <step>" is not run once and done: it runs once a
day, at the first step boundary after HH:MM local time, before the lane goes
on with its queue. It exists because of 13 September: the nightly fetches the
General Court's bulk files only when nothing else holds archive/.lock, and the
bill-text lane holds it for more than a week, so while bill text ran no day's
files would be taken at all -- and they are live views, overwritten as a
session moves, so a day not taken is gone. The day's fetch belongs in the one
worker, between its other steps, not beside them.

Daily steps run in the order the queue lists them, and "{date}" in one becomes
today's date. They are recorded in logs/gc_lane.daily when they finish, so a
lane restarted the same day does not run them again. One that exits non-zero
does not stop the lane -- a failed night's build is not the address saying no
-- but the day's later daily steps are skipped, because they read what the
failed one should have made; a refusal still stops everything, through
archive/refused.json, before the next step. While any daily step is queued
the lane does not give up on an empty queue: it waits for the next day.

STOPPING IT AT A BOUNDARY

watchers/gc_lane.stop, if it exists before a step, ends the lane cleanly with
the lock released, and is removed. That is how the lane is restarted on new
code without killing it halfway through a request. It stops only between
steps, so a step already running finishes first.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import os
import pathlib
import re
import subprocess
import threading
import time

ROOT = pathlib.Path.cwd()
if not (ROOT / "refusal.py").exists():
    sys.exit(f"run this from the repository root; {ROOT} is not it")
try:
    import refusal
except Exception as e:                                          # noqa: BLE001
    sys.exit(f"refusal.py will not import from {ROOT} ({type(e).__name__}: {e}); the "
             "lane does not run without it, because it is what says whose turn it is")

LOCK = ROOT / "archive" / ".lock"
REFUSED = ROOT / "archive" / "refused.json"
QUEUE = ROOT / "watchers" / "gc_lane.queue"
LOGS = ROOT / "logs"
DONE = LOGS / "gc_lane.done"
DAILY = LOGS / "gc_lane.daily"
LOG = LOGS / "gc_lane.log"
STOP = ROOT / "watchers" / "gc_lane.stop"
WINDOW_STOP = LOGS / "gc_lane.window-stop"   # a step's hold writes it (above)
IDLE_HOURS = 12          # an empty queue for this long ends the lane
HEARTBEAT = 60           # seconds between touches of the lock
DAILY_RE = re.compile(r"^daily\s+([01]\d|2[0-3]):([0-5]\d)\s+(\S.*)$")
_WARNED = set()          # malformed daily lines already reported


def say(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def lines():
    """Every queue line, in order, comments and blanks dropped."""
    if not QUEUE.exists():
        return []
    out = []
    for ln in QUEUE.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            out.append(ln)
    return out


def queued():
    """The queue's run-once steps, in order."""
    return [ln for ln in lines() if not ln.startswith("daily ")]


def daily():
    """[(hour, minute, step, line)] for the queue's daily steps, in order.

    A line that starts "daily " and does not parse is reported and left out
    rather than run once as a step: a lane that ran "daily" as a script would
    stop on it.
    """
    out = []
    for ln in lines():
        if not ln.startswith("daily "):
            continue
        m = DAILY_RE.match(ln)
        if not m or m.group(3).startswith("handover "):
            if ln not in _WARNED:
                _WARNED.add(ln)
                say(f"not a daily step this lane can run, left out: {ln}")
            continue
        out.append((int(m.group(1)), int(m.group(2)), m.group(3), ln))
    return out


def daily_done(day):
    """The daily lines already run on `day` (YYYY-MM-DD)."""
    if not DAILY.exists():
        return set()
    out = set()
    for ln in DAILY.read_text(encoding="utf-8").splitlines():
        d, _, line = ln.partition("\t")
        if d == day and line.strip():
            out.add(line.strip())
    return out


def daily_due(now=None):
    """The daily lines due now and not yet run today, in queue order."""
    now = now or time.localtime()
    day = time.strftime("%Y-%m-%d", now)
    ran = daily_done(day)
    return [(step, line) for h, m, step, line in daily()
            if (now.tm_hour, now.tm_min) >= (h, m) and line not in ran]


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
        # Only our own. A lock naming another pid is another worker's.
        try:
            if LOCK.read_text(encoding="utf-8").strip() == str(os.getpid()):
                LOCK.unlink(missing_ok=True)
        except OSError:
            pass

    def ours(self):
        try:
            return LOCK.read_text(encoding="utf-8").strip() == str(os.getpid())
        except OSError:
            return False

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


def run_child(args, log):
    """One step as a child of this lane, logged to its own file.

    (status, minutes, its last three lines, what its hold wrote in
    WINDOW_STOP when GitHub's night window stopped it, or ""). Unbuffered, so
    the step's log shows where it has got to: a child writing to a file
    buffers otherwise, and a fetch that prints its first line after a
    hundred requests looks exactly like a hang.
    """
    WINDOW_STOP.unlink(missing_ok=True)
    t0 = time.time()
    with log.open("w", encoding="utf-8") as fh:
        # The line's script by its bare name, in whichever code folder of the
        # root the lane runs in holds it (_paths.script), so a queue line never
        # has to be rewritten when a file moves -- and rewriting one would run
        # it again. One that is not there ends the step with its reason in the
        # step's log.
        try:
            script = _paths.script(args[0], root=ROOT)
        except LookupError as e:
            fh.write(f"{e}\n")
            rc = 1
        else:
            rc = subprocess.call([sys.executable, script, *args[1:]], cwd=str(ROOT),
                                 stdout=fh, stderr=subprocess.STDOUT,
                                 env={**os.environ, "PYTHONUNBUFFERED": "1",
                                      refusal.WINDOW_STOP_ENV: str(WINDOW_STOP)})
    tail = [ln for ln in log.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()][-3:]
    cut = ""
    if WINDOW_STOP.exists():
        try:
            cut = WINDOW_STOP.read_text(encoding="utf-8", errors="replace").strip() or "(empty)"
        except OSError:
            cut = "(unreadable)"
        WINDOW_STOP.unlink(missing_ok=True)
    return rc, (time.time() - t0) / 60, tail, cut


def cut_short(n, rc, cut, tail, daily=False):
    """Say why a step GitHub's night window stopped is not recorded."""
    say(f"step {n}{' (daily)' if daily else ''} exited {rc}, but GitHub's night window "
        f"stopped it before it finished ({' '.join(cut.split())[:200]}): not recorded as "
        + ("run today" if daily else "done") + ", and the lane stops (exit "
        f"{refusal.STOOD_DOWN}, the stand-down's). Last lines: " + " | ".join(tail)[:400])


def run_daily(due, n):
    """Today's due daily steps, in order. Returns (the step count reached,
    whether the lane must stop now for GitHub's turn).

    Each is recorded when it finishes, whatever its status -- except one
    GitHub's night window cut short (run_child's WINDOW_STOP), whatever it
    exited, and one that exited refusal.STOOD_DOWN while refusal.gc_turn()
    says it is GitHub's turn: neither ran to the end, and recording it would
    lose that day's step for good (its files are live views). The lane stops
    there, as it does when githubs_turn() holds a step before it starts,
    which it asks before EACH daily step: a day's steps can run long enough
    for the window to come round. On a stood-down laptop a 4 that gc_turn()
    does not explain is the stand-down itself (refusal.stand_down: GitHub
    runs that job now), which
    no wait will change: it is recorded, the log says the line should come
    out of the queue, and the day's steps go on. One that fails ends the
    day's daily steps: those after it read what it should have made.
    """
    today = time.strftime("%Y-%m-%d")
    for i, (step, line) in enumerate(due):
        if githubs_turn():
            return n, True
        args = step.replace("{date}", today).split()
        n += 1
        log = LOGS / f"gc_{time.strftime('%m%d_%H%M')}_{slug(' '.join(args))}.log"
        say(f"step {n} (daily, {line.split()[1]}): python3 {' '.join(args)}  -> {log.name}")
        rc, mins, tail, cut = run_child(args, log)
        if cut:
            cut_short(n, rc, cut, tail, daily=True)
            return n, True
        # On a laptop that has not stood down a 4 is no stand-down, and is
        # read as any other failure below.
        if rc == refusal.STOOD_DOWN and refusal.stood_down() is not None:
            turn = refusal.gc_turn()
            if turn:
                say(f"step {n} (daily) exited {rc}, the stand-down's: held for GitHub's turn "
                    f"({turn[0]}), so not recorded as run today, and the lane stops here "
                    "rather than ask it again at every boundary. Last lines: "
                    + " | ".join(tail)[:400])
                return n, True
            with DAILY.open("a", encoding="utf-8") as fh:
                fh.write(f"{today}\t{line}\n")
            say(f"step {n} (daily) exited {rc}, the stand-down's, and it is not GitHub's turn "
                "now, so this is the stand-down itself: this machine has handed that job to "
                "GitHub, and it will not run here on any day. Recorded as run today so it is "
                f"not asked again, and the lane goes on. The line should come out of "
                f"watchers/{QUEUE.name}: {line}. Last lines: " + " | ".join(tail)[:400])
            continue
        with DAILY.open("a", encoding="utf-8") as fh:
            fh.write(f"{today}\t{line}\n")
        if rc == 0:
            say(f"step {n} (daily) done in {mins:.0f} min. " + " | ".join(tail)[:400])
            continue
        say(f"step {n} (daily) ended with status {rc} after {mins:.0f} min. "
            "The lane goes on: a refusal would be on file and stops it before "
            "the next step. Last lines: " + " | ".join(tail)[:400])
        rest = due[i + 1:]
        if rest:
            with DAILY.open("a", encoding="utf-8") as fh:
                for _, later in rest:
                    fh.write(f"{today}\t{later}\n")
            say("  skipped for today, because they read what that step should have "
                "made: " + "; ".join(later for _, later in rest)[:400])
        break
    return n, False


def githubs_turn():
    """True, having said why in the log, when this laptop must not start a
    General Court step now: inside GitHub's night window, or before it has
    read the bucket's refusal record since the last one (refusal.gc_turn).
    Never on a laptop that has not stood down."""
    turn = refusal.gc_turn()
    if not turn:
        return False
    say("stopping before the next step, with the lock released: "
        + " ".join(turn[1].split()) + f" (exit {refusal.STOOD_DOWN}, the stand-down's)")
    return True


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
            if not lock.ours():
                say("archive/.lock no longer names this lane. Something else "
                    "took or removed it; stopping rather than running beside it.")
                return 4
            if STOP.exists():
                try:
                    STOP.unlink()
                except OSError:
                    pass
                say("watchers/gc_lane.stop was there: stopping at this step "
                    "boundary, as asked, and removing it.")
                return 0
            due = daily_due()
            if due:
                n, held = run_daily(due, n)
                if held:
                    return refusal.STOOD_DOWN
                # Back to the top: the refusal and lock checks come before
                # anything else is asked.
                continue
            todo = [s for s in queued() if s not in done()]
            if not todo:
                keep = bool(daily())
                if idle_since is None:
                    idle_since = time.time()
                    say("queue empty; the daily steps keep the lane running" if keep
                        else f"queue empty; waiting up to {IDLE_HOURS}h for more")
                if not keep and time.time() - idle_since > IDLE_HOURS * 3600:
                    say(f"nothing new for {IDLE_HOURS}h. Stopping.")
                    return 0
                time.sleep(300)
                continue
            idle_since = None
            if githubs_turn():
                return refusal.STOOD_DOWN
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
            rc, mins, tail, cut = run_child(args, log)
            if handover:
                if LOCK.exists():
                    say("the handed-over step left archive/.lock behind. "
                        "Stopping rather than guessing whose it is.")
                    return 4
                lock.take()
            if cut:
                cut_short(n, rc, cut, tail)
                return refusal.STOOD_DOWN
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
