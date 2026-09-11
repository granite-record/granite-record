#!/usr/bin/env python3
"""
Turn each archived docket into plain-language histories as it lands.

Run from the repository root. No network: it reads Docket_*.txt off this disk
and writes narratives.json. Logs to logs/narrative_watch.log.

WHY A WATCHER

fetch_archive_docket.py finishes a term roughly every three hours and nothing
was picking the result up. Docket_2017-2018.txt has been complete and
unprocessed since 21:13 -- 1,983 bills' worth of history sitting in a file
while narratives.json still held two terms. The chain that fetches them runs
for days, so waiting for a person to notice each one costs a day per term.

WHAT IT WILL NOT DO

It will not read a docket that is still being written. A term is processed
only once its file has been still for QUIET seconds, because narrative.py
rebuilds a term whole from the docket it is given and a half-written docket
makes a half-written term. Being late costs one cycle; being early publishes
a truncated history of every bill in a biennium.

It will not overwrite another term. narrative.py merges: narratives.json is
{term: {bill: record}}, the terms this run built are replaced, and every term
it does not cover is kept. That is checked below rather than assumed -- if a
run comes back having lost a term, this stops and says so, because "a writer
of a derived file, run on a subset, destroys the rest" is the failure this
project has had twice and neither time announced itself.
"""
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path.cwd()
if not (ROOT / "narrative.py").exists():
    sys.exit(f"run this from the repository root; {ROOT} is not it")
LOGS = ROOT / "logs"
OUT = ROOT / "narratives.json"
CYCLE = 600                 # ten minutes between looks
# THE FETCHER WRITES IN BATCHES, so "untouched for a while" is not the same
# as "finished": fetch_archive_docket.py flushes every 100 bills, which at 15
# seconds apart is 25 minutes of stillness in the middle of a live run. Twenty
# minutes caught a half-written 2019-2020 at 298 bills of 1,983. Forty-five
# clears the batch interval. A term built early is not lost -- the signature
# below is (size, mtime), so the term is rebuilt whole when the file moves --
# it is just work done twice.
QUIET = 45 * 60             # a docket must be untouched this long to be read
# A DAY, NOT FIVE HOURS. Each remaining term takes about eight hours to fetch,
# so a watcher that gives up after thirty idle cycles would stop before
# 2021-2022 ever landed and the term would sit unprocessed until somebody
# noticed. It should outlast the thing it is waiting for.
IDLE_STOP = 144             # cycles with nothing to do before giving up
TERM = re.compile(r"Docket_(?:db_)?(\d{4}-\d{4})\.txt$")


def say(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    LOGS.mkdir(exist_ok=True)
    with (LOGS / "narrative_watch.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def terms_in(path):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return {t: len(v) for t, v in d.items()} if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def finished(term):
    """Has the fetch chain said this term's docket is complete?

    A DOCKET THAT IS STILL ARRIVING MAKES A TERM THAT IS WRONG, not merely
    thin. narrative.py rebuilds a term whole, and every stage of a bill's
    passage comes from docket rows, so a bill whose veto has not been fetched
    yet is published as a bill that was never vetoed. preflight caught exactly
    that: ten passage rails saying a bill reached no governor when the record
    says it was vetoed, all of them from a 2015-2016 seed whose rows stop on
    11 June 2015.

    Quietness was the first guard and it is not enough -- the fetcher flushes
    every hundred bills, so a live run is still for twenty-five minutes at a
    time. docket_chain.py writes "<term>: done" when a term completes, and
    that is a statement rather than an inference.
    """
    log = LOGS / "docket_chain.log"
    try:
        return f"{term}: done" in log.read_text(encoding="utf-8")
    except OSError:
        return False


def dockets():
    """{term: path}, newest docket for a term winning over the db seed.

    A term can have both Docket_2015-2016.txt from the web and
    Docket_db_2015-2016.txt seeded from the database. The fetched one is the
    fuller: the seed exists because the database's Docket view runs out part
    way through 2016.
    """
    found = {}
    for f in sorted(ROOT.glob("Docket*.txt")):
        m = TERM.search(f.name)
        if not m:
            continue
        # NOT THE SEEDS. Docket_db_<term>.txt is what could be read out of the
        # database, and for 2015-2016 that is 905 bills of 1,788 because the
        # Docket view runs out part way through 2016. It exists so the web
        # fetch can skip what it already has, not so a term can be built from
        # it. Building 2015-2016 from it produced 905 bills with truncated
        # histories and turned preflight red.
        if "_db_" in f.name:
            continue
        term = m.group(1)
        prev = found.get(term)
        if prev is None or (f.stat().st_size > prev.stat().st_size
                            and "_db_" not in f.name):
            found[term] = f
    return found


def main():
    say("watching for archived dockets to turn into narratives")
    done = {}                       # term -> (size, mtime) already processed
    idle = 0
    while True:
        had = terms_in(OUT)
        work = []
        for term, f in sorted(dockets().items()):
            st = f.stat()
            sig = (st.st_size, int(st.st_mtime))
            if done.get(term) == sig:
                continue
            age = time.time() - st.st_mtime
            if age < QUIET:
                say(f"{term}: {f.name} was written {age / 60:.0f} min ago, "
                    "still growing. Leaving it.")
                continue
            if term in had and not done:
                # Already in the file from an earlier session and the docket
                # has not moved since this watcher started: nothing to redo.
                done[term] = sig
                continue
            if not finished(term) and term not in had:
                say(f"{term}: {f.name} is here but the chain has not said it "
                    "is done. A part-fetched docket makes a term whose bills "
                    "have not finished happening.")
                continue
            work.append((term, f, sig))

        if not work:
            idle += 1
            if idle >= IDLE_STOP:
                say(f"nothing to do for {IDLE_STOP} cycles. "
                    f"narratives.json holds {terms_in(OUT)}. Stopping.")
                return 0
            time.sleep(CYCLE)
            continue

        idle = 0
        for term, f, sig in work:
            say(f"{term}: building narratives from {f.name} "
                f"({f.stat().st_size:,} bytes)")
            log = LOGS / f"narrative_{term}.log"
            with log.open("w", encoding="utf-8") as fh:
                rc = subprocess.call(
                    [sys.executable, "narrative.py", "--docket", f.name,
                     "--all", "--out", "narratives.json",
                     "--members", "data/legislators.json"],
                    cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)
            now = terms_in(OUT)
            if rc != 0:
                # ONE TERM FAILING IS NOT THE NIGHT FAILING. Terms are taken
                # in order and 2015-2016 is first, so stopping here would let
                # a seed file this parser has never been pointed at cost every
                # later term its build. It is marked done so it is not retried
                # in a loop, and the log says which one and why.
                say(f"{term}: narrative.py exited {rc}. See {log.name}. "
                    "Leaving it and going on to the next term.")
                done[term] = sig
                continue
            lost = [t for t in had if t not in now]
            if lost:
                say(f"{term}: THAT RUN LOST {', '.join(lost)} from "
                    "narratives.json. Stopping. The merge is supposed to keep "
                    "every term a docket does not cover, and it did not.")
                return 2
            if term not in now:
                # Still a stop: this one means the merge is not doing what
                # the rest of this relies on.
                say(f"{term}: the run finished cleanly and wrote no term by "
                    f"that name. narratives.json holds {sorted(now)}. "
                    "Stopping -- a build that publishes nothing is not a "
                    "success.")
                return 3
            say(f"{term}: {now[term]:,} bills. narratives.json now holds "
                + ", ".join(f"{t} ({n:,})" for t, n in sorted(now.items())))
            done[term] = sig
        time.sleep(CYCLE)


if __name__ == "__main__":
    sys.exit(main())
