#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.6
"""
One refusal stops the fetch lane, not just the run that was refused.

NOT, YET, EVERY FETCHER. Twelve of the thirty-two fetch_*.py scripts consult
this module -- `grep -l refusal fetch_*.py` is the list -- and the rest,
started by hand, would walk straight through a recorded refusal. build_all.py
and watchers/gc_lane.py do honour it, which is what makes the scheduled path
safe. Closing the gap is a small change to twenty files and has not been made.

    import refusal
    refusal.check("fetch_archive_docket")      # exits if the last run was refused
    refusal.note("calendars", "HTTPError: 403")  # when a run stops on one

WHY THIS EXISTS

A calendar drain was answered with two HTTP 403s and stopped itself, correctly.
Fifty-four seconds later a chained run started asking the same address for
another docket, because it was waiting on the lock and the lock had cleared: it
had no way to tell a run that finished from a run that was refused. Each
fetcher had a stop-loss and honoured it; what was missing was that a refusal is
a fact about the ADDRESS, so it has to outlive the process that discovered it.

HOW IT BEHAVES

note() writes archive/refused.json. check() reads it and stops the caller dead
while it is less than QUIET hours old, printing when the refusal came, what it
said, and how to clear it. The file is small, plain and meant to be read.

Clearing it is a person's decision, deliberately: `python3 refusal.py --clear`,
after netcheck.py has said what kind of refusal it was. Nothing clears it
automatically, because "wait a bit and try again" is the behaviour that earns a
longer block.

ON GITHUB'S MACHINE (25 September 2026) it is the same file. GitHub's
machines start empty every night, so the record has to outlive the machine:
`cloud.py state-down` brings R2's state/refused.json down as archive/refused.json
before the night, and the workflow sends it back with `cloud.py state-up` the
moment one is on file. Every script reads it where it always has.

THE STAND-DOWN. Once GitHub runs the nightly, the laptop must not run it as
well: two writers of the same files, and two machines asking the General Court
for the same things. archive/runs-in-the-cloud.json says the laptop has handed
it over, and stand_down() is what the nightly, the daily snapshot, publish.bat
and the fetchers whose files GitHub now owns call to refuse, saying why.
`python3 refusal.py --stand-down` writes it; deleting it is moving back, a
person's decision. It never applies on GitHub's own machine.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

MARK = Path("archive/refused.json")
QUIET_HOURS = 24


def note(where, why):
    """Record that this address was refused. Called as a run gives up."""
    MARK.parent.mkdir(exist_ok=True)
    MARK.write_text(json.dumps({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epoch": time.time(),
        "where": where,
        "why": str(why)[:300],
    }, indent=1), encoding="utf-8")


def standing():
    """The refusal still in force, or None."""
    if not MARK.exists():
        return None
    try:
        d = json.loads(MARK.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    hours = (time.time() - float(d.get("epoch") or 0)) / 3600
    return None if hours > QUIET_HOURS else (d, hours)


def check(who=""):
    """Stop the caller if this address was refused recently."""
    s = standing()
    if not s:
        return
    d, hours = s
    # Status 2, which every fetcher and the lane read as "refused".
    print(
        f"\nThis address was refused {hours:.1f} hours ago and nothing has "
        f"asked it since.\n"
        f"  when   {d.get('at')}\n"
        f"  who    {d.get('where')}\n"
        f"  what   {d.get('why')}\n\n"
        f"{who or 'This fetch'} is stopping. A refusal is a fact about the "
        "address, not about\nthe run that found it, so it applies to every "
        "fetch and not only that one.\n\n"
        "  python3 netcheck.py          what kind of refusal it was\n"
        "  python3 refusal.py --clear   when a person has decided to go on\n",
        file=sys.stderr)
    sys.exit(2)


# ---- what an answer means --------------------------------------------------
#
# One reading of an answer, for every fetcher. The docket fetch matched
# refusals by substring of the error's text, and urllib wraps a reset at
# connect time as "<urlopen error [WinError 10054] ...>", which contains
# neither "RemoteDisconnected" nor "ConnectionReset": a connection being
# refused was counted as an ordinary failure, with no cool-off, no stop and
# no record. And neither fetch knew that a server shedding load says 503 with
# a Retry-After, which is a request to go away, not a flaky link.

BLOCKED = re.compile(r"Web Page Blocked|Attack ID", re.I)
BROKEN = re.compile(r"Runtime Error|Server Error in|Service Unavailable", re.I)


def classify(err=None, body=None):
    """"refused", "dropped", "missing", "failed", or None for a fine answer.

    refused  -- 403, 429, 503, a Retry-After, or the firewall's block page:
                the address saying no. One ends a run.
    dropped  -- accepted and closed without an answer, reset, aborted or
                timed out, at connect or mid-read: this address's usual
                sign of refusing. Two end a run.
    missing  -- 404 or 410: no such document.
    failed   -- anything else that is not a page.
    """
    import http.client
    import socket
    import ssl
    import urllib.error
    if err is not None:
        if isinstance(err, urllib.error.HTTPError):
            if err.code in (403, 429, 503) or (err.headers or {}).get("Retry-After"):
                return "refused"
            try:
                head = err.read(4000).decode("utf-8", "replace")
            except Exception:
                head = ""
            if BLOCKED.search(head):
                return "refused"
            return "missing" if err.code in (404, 410) else "failed"
        inner = err.reason if isinstance(err, urllib.error.URLError) else err
        if isinstance(inner, (http.client.RemoteDisconnected, ConnectionResetError,
                              ConnectionAbortedError, ConnectionRefusedError,
                              TimeoutError, socket.timeout, ssl.SSLEOFError)):
            return "dropped"
        if isinstance(inner, str) and "timed out" in inner:
            return "dropped"
        return "failed"
    if body is not None:
        head = body[:4000] if isinstance(body, str) else ""
        if BLOCKED.search(head):
            return "refused"
    return None


# ---- one worker ------------------------------------------------------------
#
# archive/.lock says a fetch from the General Court is running. Only three
# fetchers ever looked at it, one of them deleted any lock more than an hour
# old, and nothing refreshed one while it ran -- so any run longer than an hour
# could be joined by a second worker, which is how this address was blocked
# the second time. hold() is the rule in one place: take the lock, or run
# under the lane that holds it (watchers/gc_lane.py, whose pid is in the lock
# and who is this process's parent), or do not run at all.

LOCK = Path("archive/.lock")


class hold:
    """with refusal.hold("fetch_legislation"): ... -- one worker, or none."""

    def __init__(self, who):
        self.who, self.mine, self._stop = who, False, None

    def __enter__(self):
        import os
        import threading
        if LOCK.exists():
            held = LOCK.read_text(encoding="utf-8", errors="replace").strip()
            if held.isdigit() and int(held) == os.getppid():
                return self            # the lane that started us holds it
            print(f"\narchive/.lock is held (pid {held or '?'}): another "
                  f"fetch from the General Court is running, and {self.who} "
                  "will not be a second one. If nothing is running, a "
                  "person may remove the lock.\n", file=sys.stderr)
            sys.exit(3)
        LOCK.parent.mkdir(exist_ok=True)
        LOCK.write_text(str(os.getpid()), encoding="utf-8")
        self.mine = True
        # Touched every minute, so no rule about a lock's age can mistake a
        # long run for an abandoned one.
        self._stop = threading.Event()

        def beat():
            while not self._stop.wait(60):
                try:
                    os.utime(LOCK, None)
                except OSError:
                    pass
        threading.Thread(target=beat, daemon=True).start()
        return self

    def still(self):
        """Whether this run may still ask for anything. Before every request.

        A run that took the lock keeps it fresh itself. A run under the lane
        relies on the lane's heartbeat, so it checks that the lane is still
        there: the lock present, naming our parent, touched within three
        minutes. A lane killed hard leaves its child fetching with nobody
        refreshing the lock, and a lock nobody refreshes is one any other
        fetcher may decide is abandoned."""
        import os
        if self.mine:
            return True
        try:
            held = LOCK.read_text(encoding="utf-8", errors="replace").strip()
            fresh = time.time() - LOCK.stat().st_mtime < 180
        except OSError:
            return False
        return held.isdigit() and int(held) == os.getppid() and fresh

    def __exit__(self, *exc):
        if self.mine:
            self._stop.set()
            # Only our own lock. Another worker's is not ours to remove.
            try:
                if LOCK.read_text(encoding="utf-8").strip() == str(__import__("os").getpid()):
                    LOCK.unlink(missing_ok=True)
            except OSError:
                pass
        return False


# ---- the stand-down ---------------------------------------------------------
#
# The file that says this machine has handed the nightly and publishing to
# GitHub. It is read here rather than in each script so that "does this run on
# the laptop any more" has one answer, and so that GitHub's own machine can
# never be stood down by a copy of the file arriving there by mistake.

STANDDOWN = Path("archive/runs-in-the-cloud.json")
STOOD_DOWN = 4          # the exit status of a job this machine has handed over


def stood_down():
    """What the stand-down file says, or None when this machine may run it.

    None on GitHub's machine whatever is on disk: GITHUB_ACTIONS is "true"
    there, and the stand-down is about the laptop.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true" or not STANDDOWN.exists():
        return None
    try:
        d = json.loads(STANDDOWN.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        d = {}
    return d if isinstance(d, dict) else {}


def stand_down(who, instead=""):
    """Stop the caller on a machine that has handed its job to GitHub."""
    d = stood_down()
    if d is None:
        return
    print(f"\n{who} does not run on this machine any more: GitHub runs it, "
          f"since {d.get('since') or '(no date given)'}. {STANDDOWN} says so.\n"
          + (f"{instead}\n" if instead else "")
          + f"Moving it back is deleting {STANDDOWN}: a person's decision, made "
          "after this machine's copy of the data has been brought up to date "
          "from R2.\n", file=sys.stderr)
    sys.exit(STOOD_DOWN)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true",
                    help="lift the standing refusal; a person's decision")
    ap.add_argument("--stand-down", action="store_true",
                    help="hand the nightly and publishing to GitHub: write "
                         f"{STANDDOWN}; a person's decision")
    a = ap.parse_args()
    if a.stand_down:
        if STANDDOWN.exists():
            print(f"{STANDDOWN} is already on file: this machine is stood down.")
            return 0
        STANDDOWN.parent.mkdir(exist_ok=True)
        STANDDOWN.write_text(json.dumps({
            "since": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "what": "GitHub's workflows run the nightly, the weekly fetches and "
                    "publishing. This machine keeps the one-off jobs.",
        }, indent=1), encoding="utf-8")
        print(f"wrote {STANDDOWN}. The nightly, the daily snapshot, publish and "
              "the fetchers GitHub owns now refuse here. Deleting it moves back.")
        return 0
    if stood_down() is not None:
        print(f"stood down: {STANDDOWN} hands the nightly and publishing to GitHub.")
    s = standing()
    if a.clear:
        if MARK.exists():
            MARK.unlink()
            print("refusal cleared here. Fetches on this machine may run again.")
        else:
            print("there was no refusal on record here.")
        # THE NIGHTLY'S COPY IS THE BUCKET'S. GitHub's machine starts empty and
        # takes its refusal record from R2's state/refused.json, so clearing
        # this file leaves that one stopping every night until it is lifted
        # too -- and cloud.py, which talks to the bucket, is what lifts it.
        if stood_down() is not None:
            print("The nightly runs on GitHub and takes its refusal record from the "
                  "bucket's state/refused.json. Lift that one too: "
                  "python3 cloud.py clear-refusal")
        return 0
    if not s:
        print("no refusal in force." if not MARK.exists() else
              f"the recorded refusal is older than {QUIET_HOURS}h and no "
              "longer stops anything.")
        return 0
    d, hours = s
    print(f"refused {hours:.1f}h ago by {d.get('where')}: {d.get('why')}")
    print("every fetch is stopped until: python3 refusal.py --clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
