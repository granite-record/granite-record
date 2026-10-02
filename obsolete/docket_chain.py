#!/usr/bin/env python3
"""
Wait for the running drain, then the dockets, the last Senate
calendars, and the archived bill text.

Run from the repository root. Writes logs/docket_<term>.log and
logs/docket_chain.log; asks the General Court for nothing until archive/.lock
is gone.

WHY A CHAIN AND NOT THREE COMMANDS

Two fetches at once is what got this address blocked the second time, so the
one-worker rule has to hold across the handover as well as inside each run.
This waits on the lock, takes it, and holds it for the whole docket run.

AND WHY IT STOPS RATHER THAN CARRIES ON

fetch_archive_docket.py exits non-zero when two refusals end its run. That
answer applies to the address, not to the term, so a term that ends that way
stops the chain instead of starting the next one 15 seconds later. Everything
fetched is on disk and nothing already there is asked for again, so picking it
up later costs nothing.
"""
import os
import pathlib
import subprocess
import sys
import time

# The repository root, which is where this must be run from -- it drives the
# project's own scripts and they all read relative paths.
ROOT = pathlib.Path.cwd()
if not (ROOT / "fetch_archive_docket.py").exists():
    sys.exit(f"run this from the repository root; {ROOT} is not it")
LOCK = ROOT / "archive" / ".lock"
LOGS = ROOT / "logs"
# (term, seed). 2017-2022 is in neither the bulk download nor the database and
# has to be fetched whole. 2015-2016 is half in the database -- the Docket view
# runs out part way through 2016 -- so its 905 covered bills are seeded from
# db/Docket.psv and only the other 883 are asked for. It goes last because it
# is the term this buys the least new record for.
TERMS = [
    ("2017-2018", None),
    ("2019-2020", None),
    ("2021-2022", None),
    ("2015-2016", "Docket_db_2015-2016.txt"),
]
WAIT_LIMIT = 14 * 60 * 60          # give up waiting after fourteen hours
# Archived bill text, after the dockets. 31,449 bills at two requests each is
# 63,000 requests; these bounded runs are about eight hours apiece.
TEXT_BUDGET = 2000
TEXT_RUNS = 32


def say(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with (LOGS / "docket_chain.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main():
    LOGS.mkdir(exist_ok=True)
    say(f"waiting for {LOCK} to clear before asking for anything")

    waited = 0
    while LOCK.exists():
        if waited > WAIT_LIMIT:
            say("the calendar lock is still held after fourteen hours. "
                "Stopping without fetching; something needs a person.")
            return 1
        time.sleep(60)
        waited += 60
    say(f"lock cleared after {waited / 3600:.1f}h; the calendars are done")

    # Hold it ourselves, so nothing else starts a second worker.
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    try:
        for term, seed in TERMS:
            log = LOGS / f"docket_{term}.log"
            say(f"{term}: starting, 15s apart, two refusals ends it"
                + (f", seeded from {seed}" if seed else ""))
            cmd = [sys.executable, "fetch_archive_docket.py", "--term", term,
                   "--delay", "15", "--stop-refused", "2"]
            if seed:
                cmd += ["--seed", seed]
            with log.open("w", encoding="utf-8") as fh:
                rc = subprocess.call(cmd, cwd=str(ROOT), stdout=fh,
                                     stderr=subprocess.STDOUT)
            if rc != 0:
                say(f"{term}: ended with status {rc}. That is the address "
                    f"saying no, so the chain stops here rather than starting "
                    f"the next term. See {log.name}.")
                return rc
            say(f"{term}: done. {log.name} has the count.")
        say("every docket fetched: 1989-2026 is complete on this disk.")
    finally:
        LOCK.unlink(missing_ok=True)
        say("lock released")

    # ---- the 664 Senate calendars nobody was draining ---------------------
    # These have been queued since the calendar run stopped on two 403s and
    # nothing came back for them: the chain went dockets then text and never
    # returned to calendars, so they would have sat there forever. They go
    # BEFORE the text because they are 664 requests against 63,000 -- under
    # three hours to finish a dataset that is at 85%, against eleven days to
    # start one.
    #
    # fetch_calendar_archive.py takes archive/.lock itself, so this hands it
    # over rather than holding it; the lock is released above.
    say("dockets done; draining the 664 Senate calendars still queued")
    with (LOGS / "calendars_tail.log").open("w", encoding="utf-8") as fh:
        rc = subprocess.call(
            [sys.executable, "fetch_calendar_archive.py", "--kind", "calendar",
             "--budget", "700", "--delay", "15"],
            cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)
    if rc != 0:
        say(f"the calendar drain ended with status {rc}. That is the address "
            "saying no, so this stops here rather than starting the text. "
            "See calendars_tail.log.")
        return rc
    say("Senate calendars done. Extracting their text.")
    # The hearings parser reads the .txt, not the .pdf, so a calendar with no
    # text beside it is on this disk and invisible. No network.
    with (LOGS / "extract_tail.log").open("w", encoding="utf-8") as fh:
        subprocess.call([sys.executable, "extract_calendar_text.py"],
                        cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)

    # ---- then the archived bill text -------------------------------------
    # fetch_archive_text.py takes archive/.lock itself, so this hands it over
    # rather than holding it: the lock is released above before the first call
    # below. Discovery first, because 31,449 bills at two requests each is
    # eleven days and it is worth knowing which terms have any text at all
    # before spending them.
    say("docket done; asking which terms have any digital text")
    with (LOGS / "text_discover.log").open("w", encoding="utf-8") as fh:
        rc = subprocess.call(
            [sys.executable, "fetch_archive_text.py", "--discover",
             "--sample", "4", "--delay", "15"],
            cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)
    if rc != 0:
        say(f"discovery ended with status {rc}; stopping. "
            "See text_discover.log.")
        return rc
    say("discovery done. See logs/text_discover.log for which terms have text.")

    # Bounded runs rather than one long one, so each carries its own stop-loss
    # and the queue on disk is written between them. A run that ends non-zero
    # is a refusal and ends the lot.
    for n in range(1, TEXT_RUNS + 1):
        log = LOGS / f"text_{n:02d}.log"
        say(f"text run {n}/{TEXT_RUNS}: budget {TEXT_BUDGET} requests")
        with log.open("w", encoding="utf-8") as fh:
            rc = subprocess.call(
                [sys.executable, "fetch_archive_text.py",
                 "--budget", str(TEXT_BUDGET), "--delay", "15"],
                cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)
        if rc != 0:
            say(f"text run {n} ended with status {rc}. That is the address "
                f"saying no, so this stops here. See {log.name}.")
            return rc
        out = log.read_text(encoding="utf-8", errors="replace")
        if "nothing wanted" in out:
            say("every archived bill has been asked for. Done.")
            break
        say(f"text run {n} finished cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
