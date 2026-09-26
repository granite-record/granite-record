#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.8
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

ONE FETCH AT A TIME, ACROSS BOTH MACHINES (26 September 2026). A stood-down
laptop still runs General Court fetches of its own -- the lane, the bill
text, the archive -- and GitHub's night asks the same address every morning.
So on a stood-down laptop, and only there:

  - no General Court request starts inside GitHub's night window
    (NIGHT_WINDOWS, the one definition, in UTC because GitHub's cron is):
    check() exits STOOD_DOWN (4) with a sentence naming the window in
    Eastern time and when it ends; watchers/gc_lane.py asks gc_turn() before
    each step; probe_db asks window_check() before every query of the SQL
    host, which the night and the weekly query too;
  - no request starts until this laptop has read the bucket's refusal record
    (`cloud.py pull`, which records when) since the last window ended, which
    is never more than 24 hours ago: a refusal the night met is recorded in
    the bucket, not here, and would otherwise be invisible;
  - a refusal recorded here is sent to the bucket's state/refused.json when
    the bucket holds none, so the night stops too (note(), through
    cloud.send_refusal). If the bucket cannot be reached it says so loudly
    and leaves archive/cloud/refusal-unsent.json, which pull, state-up and
    preflight report until `python3 cloud.py send-refusal` has sent it.
    note() itself never fails for it: the refusal is on file here first.

Exit 4, not 2: 2 is "refused", and the lane and every fetcher read it as the
address saying no. Waiting for the other machine's turn is the stand-down's
arrangement, so it takes the stand-down's status.
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

# Tests only: a folder standing in for the bucket when note() sends a refusal
# (cloud.py's --local-bucket). None is the real one, through keys.r2().
CLOUD_BUCKET = None


def note(where, why):
    """Record that this address was refused. Called as a run gives up.

    On a stood-down laptop the refusal also goes to the bucket, so GitHub's
    night stops at it too -- after it is on file here, and without ever
    making this call fail (tell_the_bucket)."""
    MARK.parent.mkdir(exist_ok=True)
    MARK.write_text(json.dumps({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epoch": time.time(),
        "where": where,
        "why": str(why)[:300],
    }, indent=1), encoding="utf-8")
    if _governing() is not None:
        tell_the_bucket()


def unsent_marker():
    """archive/cloud/refusal-unsent.json, beside the refusal record it is about."""
    return MARK.parent / "cloud" / "refusal-unsent.json"


def tell_the_bucket():
    """Send the refusal on file here to the bucket's state/refused.json.
    True when nothing is left to send (sent, the bucket already holds one, or a
    person cleared this one from it); False, loudly, when it could not be sent.

    The marker is written BEFORE the send and removed by cloud.send_refusal
    only once the bucket holds a refusal, so an interrupted or crashed send
    still leaves it for pull, state-up and preflight to report. Nothing here
    raises: note() is called as a run gives up, and a refusal already on file
    must not be lost to a network error on the way to the bucket.
    """
    marker = unsent_marker()

    def mark(why):
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "epoch": time.time(),
                "refusal": str(MARK), "why": str(why)[:300]}, indent=1), encoding="utf-8")
        except OSError:
            pass
    mark("being sent to the bucket")
    try:
        import cloud
        said = cloud.send_refusal(MARK.resolve().parent.parent, local_bucket=CLOUD_BUCKET)
        print(f"\nThe refusal went to the bucket as well: {said}", file=sys.stderr)
        return True
    except (Exception, SystemExit) as e:                        # noqa: BLE001
        why = f"{type(e).__name__}: {e}"
        try:
            import cloud
            why = cloud.scrub(why)
        except Exception:                                       # noqa: BLE001
            pass
        mark(why)
        print(f"\nTHE BUCKET HAS NOT BEEN TOLD. This refusal is on file here ({MARK}), "
              f"but it could not be sent to the bucket's state/refused.json:\n  {why}\n"
              "GitHub's night reads the bucket's refusal record, not this one, so it would "
              f"still ask the General Court. {marker} says so until it is sent:\n"
              "  python3 cloud.py send-refusal\n", file=sys.stderr)
        return False


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
    """Stop the caller if this address was refused recently -- and, on a
    stood-down laptop, while GitHub's night may be running or until this
    laptop has read the bucket's refusal record since the last one (gc_turn)."""
    s = standing()
    if not s:
        turn = gc_turn()
        if turn:
            print(f"\n{who or 'This fetch'} is not starting. {turn[1]}\n", file=sys.stderr)
            sys.exit(STOOD_DOWN)
        soon = window_soon()
        if soon:
            print(f"\nNote: {soon}\n", file=sys.stderr)
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


# ---- GitHub's night window ---------------------------------------------------
#
# The one definition of when GitHub's machine may be asking the General Court,
# in UTC because GitHub's cron has no time zone. The nightly starts at 06:17
# and is allowed four hours; the weekly starts at 04:17 on Monday and is
# allowed two, and the night waits for it (one concurrency group), so on a
# Monday the two run together as 04:00 to 10:30. A few minutes each side of
# the start is margin; GitHub starting a scheduled run later than asked is the
# known weakness, and HANDOFF.md says so.

NIGHT_WINDOWS = (
    # (weekday or None for every day, start, end, what), UTC; weekday 0 is Monday
    (None, (6, 0), (10, 30), "the nightly, which GitHub starts at 06:17 UTC and allows "
                             "four hours"),
    (0, (4, 0), (6, 30), "Monday's weekly job, which GitHub starts at 04:17 UTC and "
                         "allows two hours"),
)

# Tests only: the time the window is judged at, as ISO 8601 UTC, for a test
# that runs a script as a child and cannot hand it a clock. Every sentence
# the guards print says so when it is set.
CLOCK_ENV = "GRANITE_CLOCK_UTC"

# How soon before a window check() mentions it: a fetch already running when
# the window opens is not stopped by it.
SOON_MINUTES = 60


def _governing():
    """The stand-down that governs MARK -- the file beside it -- or None.

    In the working folder that is stood_down()'s answer exactly: MARK is
    archive/refused.json and the stand-down archive/runs-in-the-cloud.json. A
    test that points MARK at a folder of its own is governed by that folder,
    never by the machine running it -- the guards below exit and send, and a
    check that drives a fetcher on the stood-down laptop at 06:30 UTC must not
    fail for the time of day, or send its made-up refusal to the real bucket.
    Never on GitHub's machine.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return None
    p = MARK.parent / STANDDOWN.name
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        d = {}
    return d if isinstance(d, dict) else {}


def _utc(now=None):
    """An aware UTC datetime: `now` as given (aware, naive-as-UTC, or an epoch),
    or GRANITE_CLOCK_UTC when set, or the clock."""
    from datetime import datetime, timezone
    if now is None:
        raw = os.environ.get(CLOCK_ENV, "").strip()
        if raw:
            try:
                now = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                print(f"{CLOCK_ENV}={raw!r} is not an ISO time; the real clock is used",
                      file=sys.stderr)
                now = None
        if now is None:
            return datetime.now(timezone.utc)
    if isinstance(now, (int, float)):
        return datetime.fromtimestamp(now, timezone.utc)
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)


def _spans(now):
    """GitHub's windows from two days before `now` to two after, merged where
    they overlap or touch: [(start, end, [what, ...])], sorted."""
    from datetime import datetime, timedelta, timezone
    out = []
    for k in range(-2, 3):
        d = now.date() + timedelta(days=k)
        for wd, (sh, sm), (eh, em), what in NIGHT_WINDOWS:
            if wd is not None and d.weekday() != wd:
                continue
            s = datetime(d.year, d.month, d.day, sh, sm, tzinfo=timezone.utc)
            e = datetime(d.year, d.month, d.day, eh, em, tzinfo=timezone.utc)
            out.append((s, e if e > s else e + timedelta(days=1), what))
    merged = []
    for s, e, what in sorted(out, key=lambda x: (x[0], x[1])):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
            merged[-1][2].append(what)
        else:
            merged.append([s, e, [what]])
    return [(s, e, w) for s, e, w in merged]


def night_window(now=None):
    """(start, end, what) of the window `now` falls in -- start <= now < end --
    or None. Anywhere: whether it applies is gc_turn()'s question."""
    now = _utc(now)
    for s, e, w in _spans(now):
        if s <= now < e:
            return s, e, ", and then ".join(w)
    return None


def last_window_end(now=None):
    """When the most recent window that has closed by `now` closed."""
    now = _utc(now)
    ends = [e for _, e, _ in _spans(now) if e <= now]
    return max(ends) if ends else None


def next_window(now=None):
    """(start, end, what) of the next window to open after `now`."""
    now = _utc(now)
    later = [(s, e, ", and then ".join(w)) for s, e, w in _spans(now) if s > now]
    return min(later) if later else None


def eastern(dt):
    """(wall-clock time, "EDT" or "EST") in New Hampshire for an aware time.

    By hand, because Python on Windows has no time zone database here: daylight
    time from 2 a.m. on the second Sunday of March (07:00 UTC) to 2 a.m. on
    the first Sunday of November (06:00 UTC), the US rule since 2007.
    """
    from datetime import date, datetime, timedelta, timezone
    dt = _utc(dt)

    def sunday(month, nth):
        d = date(dt.year, month, 1)
        return d + timedelta(days=(6 - d.weekday()) % 7 + 7 * (nth - 1))
    on = datetime.combine(sunday(3, 2), datetime.min.time(), timezone.utc) + timedelta(hours=7)
    off = datetime.combine(sunday(11, 1), datetime.min.time(), timezone.utc) + timedelta(hours=6)
    hours, zone = (4, "EDT") if on <= dt < off else (5, "EST")
    return (dt - timedelta(hours=hours)).replace(tzinfo=None), zone


def _clock(dt, weekday=False):
    t, zone = eastern(dt)
    h = t.hour % 12 or 12
    return (f"{t:%A} " if weekday else "") + f"{h}:{t.minute:02d} " \
        + ("a.m." if t.hour < 12 else "p.m.") + f" {zone}"


def _until(then, now):
    mins = max(0, int((then - now).total_seconds() // 60))
    return f"{mins // 60} h {mins % 60:02d} min" if mins >= 60 else f"{mins} min"


def describe_window(s, e, what):
    """The window in the words a person in New Hampshire reads it in."""
    same_day = eastern(s)[0].date() == eastern(e)[0].date()
    return (f"{_clock(s, weekday=True)} to {_clock(e, weekday=not same_day)} "
            f"({s:%H:%M} to {e:%H:%M} UTC), for {what}")


def _clock_note():
    raw = os.environ.get(CLOCK_ENV, "").strip()
    return f" (The time is {CLOCK_ENV}'s, {raw}, not the clock's.)" if raw else ""


def refusal_read():
    """When this machine last read the bucket's refusal record, as an epoch,
    or None: `cloud.py pull` records it in archive/cloud/pull.json."""
    try:
        d = json.loads((MARK.parent / "cloud" / "pull.json").read_text(encoding="utf-8"))
        return float(((d.get("refusal") or {}).get("read")) or 0) or None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def gc_turn(now=None):
    """None when this machine may start a General Court request now; otherwise
    (kind, sentence), kind "window" or "pull". Only a stood-down laptop is ever
    held: GitHub's own machine and a laptop that has not handed the night over
    are never, whatever the time."""
    if _governing() is None:
        return None
    now = _utc(now)
    w = night_window(now)
    if w:
        s, e, what = w
        return "window", (
            f"GitHub's night may be asking the General Court now: its window is "
            f"{describe_window(s, e, what)}, and no General Court request starts on this "
            f"laptop inside it -- one fetch at a time, across both machines. It ends at "
            f"{_clock(e)}, in {_until(e, now)}; start this again then." + _clock_note())
    closed = last_window_end(now)
    read = refusal_read()
    if read is None or _utc(read) < closed:
        when = ("has never read that record" if read is None else
                f"last read that record at {_clock(_utc(read), weekday=True)} "
                f"({_utc(read):%Y-%m-%d %H:%M} UTC), before the last night window closed "
                f"at {_clock(closed, weekday=True)}")
        return "pull", (
            f"GitHub's night records a refusal it meets in the bucket's state/refused.json, "
            f"not here, and this laptop {when}. A refusal the night met would be "
            f"invisible to this fetch. Read it first:\n"
            f"  python3 cloud.py pull --changes-only     (or a full pull)\n"
            f"and start this again." + _clock_note())
    return None


def window_check(who=""):
    """Stop the caller inside GitHub's night window on a stood-down laptop.

    The window alone: for the General Court's SQL host, which the night and the
    weekly query too (the study committees' views, the rosters), but whose
    refusals are a different problem from the web server's, so neither the
    refusal record nor the pull governs it. probe_db calls this before every
    query."""
    if _governing() is None:
        return
    w = night_window()
    if w:
        s, e, what = w
        now = _utc()
        print(f"\n{who or 'This query'} is not starting: GitHub's night may be querying the "
              f"General Court's database now. Its window is {describe_window(s, e, what)}, "
              f"and it ends at {_clock(e)}, in {_until(e, now)}; start this again then."
              + _clock_note() + "\n", file=sys.stderr)
        sys.exit(STOOD_DOWN)


def window_soon(now=None):
    """A sentence when a window opens within SOON_MINUTES on a stood-down
    laptop, or "": a fetch already running then is not stopped by it."""
    if _governing() is None:
        return ""
    now = _utc(now)
    n = next_window(now)
    if not n or (n[0] - now).total_seconds() > SOON_MINUTES * 60:
        return ""
    s, e, what = n
    return (f"GitHub's night window opens at {_clock(s)}, in {_until(s, now)}, and a fetch "
            f"still running then is not stopped by it. A long one belongs after {_clock(e)}."
            + _clock_note())


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
        w, n = night_window(), next_window()
        if w:
            print(f"GitHub's night window is open: {describe_window(*w)}.{_clock_note()}")
        elif n:
            print(f"GitHub's night window is closed; the next is {describe_window(*n)}."
                  + _clock_note())
        read, turn = refusal_read(), gc_turn()
        print("the bucket's refusal record "
              + ("has never been read here" if read is None else
                 f"was last read here at {_clock(_utc(read), weekday=True)}")
              + ("; General Court fetches here wait for python3 cloud.py pull --changes-only"
                 if turn and turn[0] == "pull" else
                 "; General Court fetches here may start outside the window" if not w else ""))
        if unsent_marker().exists():
            print(f"{unsent_marker()} is on file: a refusal met here has not reached the "
                  "bucket. python3 cloud.py send-refusal sends it.")
    s = standing()
    if a.clear:
        if MARK.exists():
            MARK.unlink()
            print("refusal cleared here. Fetches on this machine may run again.")
        else:
            print("there was no refusal on record here.")
        # A refusal lifted by a person needs no sending: the marker that says
        # the bucket was never told of it goes with it.
        if unsent_marker().exists():
            unsent_marker().unlink()
            print(f"{unsent_marker()} removed with it: the bucket need not be told of a "
                  "refusal a person has lifted.")
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
