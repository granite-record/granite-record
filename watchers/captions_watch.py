#!/usr/bin/env python3
"""
Ask YouTube for captions again, occasionally, and drain if it says yes.

Run from the repository root. Touches YouTube only -- not the General Court,
whose calendars and dockets are being fetched by other processes holding
archive/.lock.

WHY IT IS SHAPED LIKE THIS

YouTube has refused this address every time today: 429 on the very first
request at a 20-second delay, which is a per-address throttle rather than a
burst limit. Pacing alone will not get past it, and hammering it is how an
address stops being served at all.

So this is a POLITENESS LOOP, not a drain. It probes with a handful of
requests, and:

  refused  -> reset to the smallest probe and the longest wait, and lengthen
              the wait again if the next probe is also refused
  clean    -> ask for more next time and wait less, up to a steady pace

At its most cautious that is three requests an hour. If the throttle lifts
while nobody is watching, it finds out within the hour and starts draining on
its own; if it never lifts, the whole night costs YouTube fewer requests than
one impatient minute would.

The ledger records every outcome, so nothing is asked for twice, and a video
with no captions published is never asked for again.
"""
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path.cwd()
if not (ROOT / "fetch_archive_captions.py").exists():
    sys.exit(f"run this from the repository root; {ROOT} is not it")

LOG = ROOT / "logs" / "captions_watch.log"
HOURS = 30

PROBE, MAX_BATCH = 3, 60
WAIT_MIN, WAIT_MAX = 5 * 60, 120 * 60
SLOW, FAST = 45.0, 20.0                 # seconds between requests


def say(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


(ROOT / "logs").mkdir(exist_ok=True)
say(f"probing YouTube every so often for {HOURS}h; backing off on a refusal, "
    f"easing forward on a clean pass")

deadline = time.time() + HOURS * 3600
batch, wait, delay = PROBE, 45 * 60, SLOW
cycles = got_total = 0

while time.time() < deadline:
    cycles += 1
    r = subprocess.run(
        [sys.executable, "fetch_archive_captions.py",
         "--limit", str(batch), "--delay", str(delay),
         "--backoff", "300", "--stop-refused", "2"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")

    refused = "rate limiting this address" in out or "REFUSED" in out
    m = re.search(r"^([\d,]+) fetched,", out, re.M)
    got = int(m.group(1).replace(",", "")) if m else 0
    got_total += got

    if refused and not got:
        # Nothing got through at all. Back off hard, and further each time.
        wait = min(WAIT_MAX, max(60 * 60, int(wait * 1.5)))
        batch, delay = PROBE, SLOW
        say(f"cycle {cycles}: refused, nothing fetched. "
            f"Next probe in {wait // 60} min.")
    elif refused:
        # PARTIAL PROGRESS IS NOT A WALL. Some got through and then the
        # limiter cut in, which means the throttle is porous rather than
        # absolute -- and the file dates say why: 984 captions landed on
        # 5 September from this same command, and the flag appeared after
        # that volume, not before it. A flag earned by volume decays.
        #
        # So a cycle that fetched something holds its cadence instead of
        # lengthening the wait again. It does not shorten it either, and the
        # batch stays small: the point is a steady trickle that keeps finding
        # out, not a run at the limiter.
        batch, delay = max(PROBE, batch), SLOW
        say(f"cycle {cycles}: {got} fetched, then refused. Holding at "
            f"{wait // 60} min -- the throttle is porous, not a wall.")
    else:
        # It answered. Ask for a little more next time, and sooner.
        batch = min(MAX_BATCH, max(PROBE * 2, batch * 2))
        wait = max(WAIT_MIN, wait // 2)
        delay = FAST if got >= PROBE else SLOW
        left = re.search(r"([\d,]+) still wanted", out)
        # NOTHING LEFT IS A REASON TO STOP, not to poll. On 11 September
        # all 676 landed at 14:56 and this went on asking every five minutes
        # for recordings that only a refreshed video index can add, until a
        # person stopped it. A new index means a new run of this.
        # fetch_archive_captions says "0 to fetch" and asks YouTube nothing
        # when the list is empty, so those five-minute cycles cost no
        # requests -- but they were noise, and they never ended.
        if not got and re.search(r"^0 to fetch", out, re.M):
            say(f"cycle {cycles}: nothing is wanted. Stopping; run this "
                "again after the video index is refreshed.")
            break
        say(f"cycle {cycles}: {got} fetched, no refusal"
            + (f", {left.group(1)} still wanted" if left else "")
            + f". Next {batch} in {wait // 60} min at {delay:.0f}s.")

    if r.returncode != 0:
        say(f"  fetch_archive_captions exited {r.returncode}: "
            f"{out.strip().splitlines()[-1:]}")
    time.sleep(wait)

say(f"stopping after {HOURS}h: {cycles} cycles, {got_total:,} captions "
    f"fetched in total")
