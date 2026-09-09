#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.1
"""
One refusal stops every fetch, not just the one that was refused.

    import refusal
    refusal.check("fetch_archive_docket")      # exits if the last run was refused
    refusal.note("calendars", "HTTPError: 403")  # when a run stops on one

WHY THIS EXISTS

On 9 September the calendar drain ran cleanly for eight hours, fetched 1,846
documents, was answered with two HTTP 403s and stopped itself -- correctly, and
for the first time on this project. Fifty-four seconds later a chained run
started asking the same address for the 2017-2018 docket, because it was
waiting on the lock and the lock had cleared. It had no way to tell the
difference between a run that finished and a run that was refused.

That is the whole failure. Each fetcher had a stop-loss and honoured it; what
was missing was that a refusal is a fact about the ADDRESS, and so it has to
outlive the process that discovered it. Every fetch since has been careful and
this one was still one minute from pushing through a 403.

HOW IT BEHAVES

note() writes archive/refused.json. check() reads it and stops the caller dead
while it is less than QUIET hours old, printing when the refusal came, what it
said, and how to clear it. The file is small, plain and meant to be read.

Clearing it is a person's decision, deliberately: `python3 refusal.py --clear`,
after netcheck.py has said what kind of refusal it was. Nothing clears it
automatically, because "wait a bit and try again" is the behaviour that earns a
longer block.
"""

import argparse
import json
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
    sys.exit(
        f"\nThis address was refused {hours:.1f} hours ago and nothing has "
        f"asked it since.\n"
        f"  when   {d.get('at')}\n"
        f"  who    {d.get('where')}\n"
        f"  what   {d.get('why')}\n\n"
        f"{who or 'This fetch'} is stopping. A refusal is a fact about the "
        "address, not about\nthe run that found it, so it applies to every "
        "fetch and not only that one.\n\n"
        "  python3 netcheck.py          what kind of refusal it was\n"
        "  python3 refusal.py --clear   when a person has decided to go on\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true",
                    help="lift the standing refusal; a person's decision")
    a = ap.parse_args()
    s = standing()
    if a.clear:
        if MARK.exists():
            MARK.unlink()
            print("refusal cleared. Fetches may run again.")
        else:
            print("there was no refusal on record.")
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
