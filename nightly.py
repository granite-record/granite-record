#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.13
"""
The nightly run. Fetch the day's bulk files, rebuild, check, compile what
readers reported and what changed -- and publish only if told to.

    python3 nightly.py                 fetch, rebuild, check, write the day's reports
    python3 nightly.py --deploy        ... and publish, if every gate passes
    python3 nightly.py --no-fetch      rebuild and report from what is on disk
    python3 nightly.py --force         past the census gate (never past the file ceiling)

Meant for Task Scheduler. Everything it prints also goes to
logs/nightly-YYYY-MM-DD.log.

WHAT IT ASKS THE GENERAL COURT FOR: fourteen files, once

snapshot_gencourt.py's bulk files, a few seconds apart, and nothing else. They
are enough to notice what a day changed -- Docket.txt drives the build, and a
newly scheduled hearing, a status change, a referral, a roll call and a new
sponsor all arrive through it -- and they are the one fetch that cannot be done
later, because the files are live views overwritten as a session moves. Every
other network step build_all has (bill pages, testimony, committee pages) has
no refusal handling or budget and stays out of the nightly; the build runs
--local.

IT ASKS ONLY WHEN NOTHING ELSE IS ASKING. This address has blocked the project
twice, the second time for two fetches at once, and the bill-text lane runs for
days. So before any request: a refusal on file, at any age, means no fetch
tonight (a run nobody watches does not decide a refusal is over); the lane's
lock held means no fetch tonight; a build already running means no run at all.
Deferring is not a failure and the log's first line says why. The lock is taken
for the fetch and released before the hour of building, which asks nothing.

IT DOES NOT PUBLISH UNLESS TOLD TO. `publish` deploys the live site, and a
nightly that published by default would publish whatever the working tree held
at three in the morning -- including someone's half-finished edit. With
--deploy it publishes only a tree whose tracked files are all committed, and
only past every gate.

THE GATES, before any deploy

  preflight --code passes; check_site passes;
  the census has not fallen past its threshold (below); the site changed;
  and the file count is under 95,000 of Cloudflare's 100,000 -- a ceiling
  --force cannot lift, because stopping short of the cap beats having the
  upload rejected halfway.

    bills          2% fewer in index.json
    legislators    2% fewer in legislators.json
    bill_data      2% fewer per-bill JSON files
    bill_pages     5% fewer static pages
    feeds          5% fewer feed files -- without this, a failed build_feeds
                   unpublishes every feed and no other count moves

WHAT IT WRITES FOR THE MORNING

  reports/gc-changes-<date>.md          what the General Court's files changed (gc_changes.py)
  reports/triage-production-<date>.md   what readers reported, screened (compile_reports.py)
  reports/FAILED-<date>.txt             written only when the reports step failed

The triage file is named for the database it was pulled from. The nightly pulls
production's; a file for the preview database is only ever made by hand, and is
never triaged. Until 13 September this docstring and reports/TRIAGE.md both
left the database out of the name -- a file nothing writes -- so the session
told to open it would have found nothing on every night, and could not have
told a failed pull from a quiet one.

Neither can change the night's exit status: a broken report step is logged and
the site is unaffected. But it is not allowed to be quiet either. The log gets
a line beginning REPORTS FAILED: with the reason, and reports/FAILED-<date>.txt
says so where the triage session looks. preflight's data check fails on that
line in the newest log that reached the reports step, on a newest log more
than 48 hours old once the logs show a schedule, and on seven nights meant to
fetch that installed nothing, whatever stopped them. It reads the lines this
file writes at the start of a line, so a change to their wording is a change
to preflight too.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import child
import refusal

LOG = []

# The Pages project's production branch -- what --branch tells Cloudflare a
# deploy is. The same value as publish.bat's PRODUCTION_BRANCH, and preflight
# holds the two together.
PRODUCTION_BRANCH = "master"

# The branch this FOLDER must be on for a deploy to happen, which since
# 17 September is a different name. The repository was renamed master -> main
# for the open-source release; the Pages project was not, and its production
# branch still answers to master.
#
# These were one constant, and the rename therefore stopped the nightly
# deploying at all: it compared the folder's branch, now main, against the
# Cloudflare name, still master, and would have said NOT DEPLOYED every night
# it ran with --deploy. Renaming the Cloudflare value instead would have been
# worse -- deploys would have gone to a PREVIEW while wrangler reported
# success, which is what happened on 6 September in mirror image.
REPO_BRANCH = "main"

# What a fall in each of these means: something upstream failed, not that the
# legislature deleted its own record.
GATES = [("bills", 0.02), ("legislators", 0.02), ("bill_data", 0.02),
         ("bill_pages", 0.05), ("feeds", 0.05)]
FILE_CEILING = 95_000
BUILD_LOCK = Path(".build.lock")
BUILD_LIVE = 180          # build_all touches its lock every 30 s

# What compile_reports.py writes for the production database, and what the
# nightly writes in the same folder when that step fails. preflight holds the
# first to the writer, and both to reports/TRIAGE.md, which tells the triage
# session to open them.
REPORTS = Path("reports")
TRIAGE_NAME = "triage-production-{day}.md"
FAILED_NAME = "FAILED-{day}.txt"


def say(msg=""):
    print(msg, flush=True)
    LOG.append(msg)


def last_words(lines):
    """The last line a step printed, from its stretch of LOG: the reason it gave.

    run() logs a header, the step's own lines, and a closing "(Ns, exit N)".
    """
    said = [ln.strip() for ln in lines[1:-1] if ln.strip()]
    return said[-1][:300] if said else "it printed nothing"


def triage_written(days):
    """Whether a production triage file exists for any of these dates.

    compile_reports.py names a second compile on the same day -2, -3, so any
    of those counts.
    """
    return any(next(REPORTS.glob(TRIAGE_NAME.format(day=d)[:-len(".md")] + "*.md"), None)
               for d in days)


def mark_reports_failed(day, log_name):
    """The file the triage session finds on a night the reports step failed.

    One fixed sentence and none of what the step printed: a failed pull's
    output can carry whatever the database sent back, which includes what
    strangers typed, and the session that reads this file must meet a reader's
    words only inside the triage file's quotation. The reason is in the log,
    for the person.
    """
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / FAILED_NAME.format(day=day)
    out.write_text(f"REPORTS FAILED: the reader reports for {day} were not compiled. "
                   f"Nothing here says there were none. The reason is in logs/{log_name}, "
                   "for the person to read.\n", encoding="utf-8", newline="\n")
    return out


def run(args, label):
    """Stream the step's output as it happens, and log it too. The exit code.

    A child of this process, run with this interpreter directly and no shell,
    so a fetch it starts sees this process as its parent and runs under the
    lock this process holds.
    """
    say(f"\n--- {label} ---")
    t0 = time.time()
    proc = child.popen([sys.executable, "-u"] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, bufsize=1)
    for ln in proc.stdout:
        say("  " + ln.rstrip())
    proc.wait()
    say(f"  ({time.time() - t0:.0f}s, exit {proc.returncode})")
    return proc.returncode


def gc_quiet():
    """Whether tonight may ask the General Court for anything: (ok, why)."""
    if refusal.MARK.exists():
        try:
            d = json.loads(refusal.MARK.read_text(encoding="utf-8"))
            why = f"{d.get('where', '?')} at {d.get('at', '?')}"
        except (ValueError, OSError):
            why = "unreadable"
        return False, (f"a refusal is on file ({why}); clearing one is a person's "
                       "decision, after netcheck.py")
    if refusal.LOCK.exists():
        held = refusal.LOCK.read_text(encoding="utf-8", errors="replace").strip()
        return False, f"archive/.lock is held (pid {held or '?'}): the lane or a fetch is running"
    return True, ""


def build_running():
    try:
        return time.time() - BUILD_LOCK.stat().st_mtime < BUILD_LIVE
    except OSError:
        return False


def census(site):
    """The few numbers that say whether this is still the site, from what was built."""
    def count_json(name):
        try:
            return len(json.loads((site / name).read_text(encoding="utf-8")))
        except Exception:
            return 0
    return {"bills": count_json("index.json"),
            "legislators": count_json("legislators.json"),
            "bill_data": (sum(1 for _ in (site / "bills").glob("*/*.json"))
                          + sum(1 for _ in (site / "bills").glob("*.json"))),
            "bill_pages": sum(1 for _ in (site / "bill").rglob("*.html")),
            "feeds": sum(1 for _ in (site / "feed").rglob("*.xml")),
            "files": sum(1 for p in site.rglob("*") if p.is_file())}


def fingerprint(site):
    """Changed or not, without caring about file order or timestamps."""
    h = hashlib.sha256()
    for name in ("index.json", "meta.json", "home.json", "legislators.json"):
        f = site / name
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def tree_clean():
    """(clean, what): tracked files all committed, so a deploy publishes a commit."""
    try:
        r = child.run(["git", "status", "--porcelain", "--untracked-files=no"],
                      capture_output=True)
    except OSError as e:
        return False, f"git would not run: {e}"
    dirty = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    return (r.returncode == 0 and not dirty), ("; ".join(dirty[:6]) or f"git exit {r.returncode}")


def gated(before, after, force):
    """(blocked, lines) for the census gates and the file ceiling."""
    lines = [f"  {'':<14}{'before':>10}{'after':>10}   change"]
    blocked = []
    for key, tol in GATES:
        b, n = before[key], after[key]
        if b and n < b * (1 - tol):
            blocked.append(f"{key} fell from {b:,} to {n:,}")
        pct = f"{(n - b) / b * 100:+.1f}%" if b else "n/a"
        lines.append(f"  {key:<14}{b:>10,}{n:>10,}   {pct}")
    ceiling = after["files"] >= FILE_CEILING
    lines.append(f"  {'files':<14}{before['files']:>10,}{after['files']:>10,}   "
                 f"ceiling {FILE_CEILING:,}")
    hard = [f"{after['files']:,} files is past the {FILE_CEILING:,} ceiling"] if ceiling else []
    return (hard + ([] if force else blocked)), blocked, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--project", default="graniterecord")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--archive", default="nh-archive")
    ap.add_argument("--deploy", action="store_true",
                    help="publish if every gate passes (off unless given)")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--force", action="store_true", help="past the census gate")
    a = ap.parse_args()

    lock = Path(".nightly.lock")
    if lock.exists() and time.time() - lock.stat().st_mtime < 6 * 3600:
        print(f"Another nightly is already going: "
              f"{lock.read_text(encoding='utf-8', errors='replace').strip()}")
        return 1
    lock.write_text(f"{datetime.now():%Y-%m-%d %H:%M} pid {os.getpid()}", encoding="utf-8")

    started = datetime.now()
    day = f"{started:%Y-%m-%d}"
    site = Path(a.site)
    code = 1
    reports = True        # the reports are pulled on every run, including a
                          # deferred one: see the build_running branch below
    say("=" * 74)
    say(f"Granite Record nightly  {started:%Y-%m-%d %H:%M}")
    say("=" * 74)
    try:
        if build_running():
            # THE REPORTS ARE STILL PULLED, and the line above used to say the
            # opposite. A reader's report sits in the D1 database until
            # something fetches it; compile_reports.py reads it with wrangler
            # and touches the built site only to list which member pages exist,
            # for grouping. So a build running here is a reason to skip the
            # fetch and the rebuild, and no reason at all to leave a reader's
            # words in a database nobody has read.
            #
            # It cost two days. The nightly deferred on 15 and 16 September,
            # wrote a 434-byte log and exited 0 both times, and a report filed
            # on the evening of the 14th -- Senate Finance listing members from
            # an older session -- was still unpulled when the person asked on
            # the 16th whether reports were arriving. An exit 0 and a short log
            # nobody reads is exactly what CLAUDE.md means by "silence is not
            # success".
            say("\nDEFERRED: a build is running (.build.lock is fresh). Nothing "
                "fetched and nothing rebuilt. The reader reports are still "
                "pulled below: they come from the database, not from the pages "
                "the build is rewriting.")
            code = 0
            return 0

        if run(["preflight.py", "--code"], "preflight") != 0:
            say("\nSTOPPED: preflight failed. Nothing fetched, nothing built.")
            return 1

        installed = False
        if a.no_fetch:
            say("\n--- fetch ---\n  skipped: --no-fetch")
        else:
            ok, why = gc_quiet()
            if not ok:
                say(f"\nFETCH DEFERRED: {why}")
            else:
                try:
                    with refusal.hold("nightly"):
                        rc = run(["snapshot_gencourt.py", "--dir", a.archive, "--into", "."],
                                 "the day's bulk files")
                except SystemExit as e:
                    rc = e.code if isinstance(e.code, int) else 3
                    say(f"  the lock was taken by someone else first (exit {rc})")
                installed = rc == 0
                if rc == 2:
                    say("\nREFUSED while fetching. Recorded; every fetch now waits "
                        "for a person.")
                elif rc != 0:
                    say(f"\nThe fetch did not complete (exit {rc}); nothing was "
                        "installed, so tonight's build would be yesterday's.")

        if installed:
            run(["gc_changes.py", "--archive", a.archive,
                 "--out", f"reports/gc-changes-{day}.md"], "what the General Court changed")

        rebuilt = False
        if installed or a.no_fetch:
            before = census(site)
            before_fp = fingerprint(site)
            if run(["build_all.py", "--local"], "rebuild") != 0:
                say("\nSTOPPED: the build failed. The live site is untouched.")
                return 1
            if run(["check_site.py", "--site", a.site, "--base", a.base],
                   "check the built site") != 0:
                say("\nSTOPPED: check_site failed. The live site is untouched.")
                return 1
            rebuilt = True
            after = census(site)
            stop, blocked, lines = gated(before, after, a.force)
            say("\n--- gates ---")
            for ln in lines:
                say(ln)
            if stop:
                say("\nNOT PUBLISHABLE: " + "; ".join(stop))
            elif blocked:
                say("\n  the census objected, --force given: " + "; ".join(blocked))
            changed = fingerprint(site) != before_fp
            say(f"\n  the site {'changed' if changed else 'did not change'}")

            if a.deploy and not stop and changed:
                clean, what = tree_clean()
                if not clean:
                    say(f"\nNOT DEPLOYED: tracked files are not all committed ({what}). "
                        "A nightly publishes a commit, not a working tree.")
                else:
                    if not deploy(a):
                        return 1
            elif not a.deploy:
                say("\nNot deploying: --deploy was not given. Publishing is a person's "
                    "decision unless they have handed it to the nightly.")
            if stop:
                return 1
        else:
            say("\nNothing new was installed, so there is nothing to rebuild.")

        code = 0
        return 0
    finally:
        # The reports are written whatever happened above, and cannot change
        # the exit status: a person reads them in the morning either way.
        #
        # Until 13 September a failure here was one indented line in the middle
        # of the log, and the triage session, finding no file, had nothing to
        # tell a failed pull from a night nobody reported anything. So a
        # failure -- a non-zero exit, a step that could not start, or an exit 0
        # that left no triage file -- now says REPORTS FAILED: at the start of
        # a line, and leaves a marker beside where the triage file would be.
        if reports:
            failed = ""
            t0 = datetime.now()
            mark = len(LOG)
            try:
                rc = run(["compile_reports.py", "--site", a.site], "what readers reported")
                if rc != 0:
                    failed = f"compile_reports.py exit {rc}: {last_words(LOG[mark:])}"
                elif not triage_written({f"{t0:%Y-%m-%d}", f"{datetime.now():%Y-%m-%d}"}):
                    failed = ("compile_reports.py exit 0, but there is no "
                              f"{REPORTS / TRIAGE_NAME.format(day=f'{t0:%Y-%m-%d}')}")
            except Exception as e:                              # noqa: BLE001
                failed = f"the reports step could not run: {e}"
            if failed:
                say(f"\nREPORTS FAILED: {failed}")
                try:
                    out = mark_reports_failed(f"{t0:%Y-%m-%d}", f"nightly-{day}.log")
                    say(f"  {out} says so for the triage session. The site is unaffected, "
                        "and the night's exit status is not changed by it.")
                except OSError as e:
                    say(f"  and the marker for the triage session could not be written: {e}")
        lock.unlink(missing_ok=True)
        say("\n" + "=" * 74)
        say(f"finished {datetime.now():%H:%M}, "
            f"{(datetime.now() - started).seconds // 60} min, exit {code}")
        logs = Path("logs")
        logs.mkdir(exist_ok=True)
        (logs / f"nightly-{day}.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")
        for old in sorted(logs.glob("nightly-*.log"))[:-14]:
            old.unlink()


def current_branch():
    try:
        r = child.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True)
        return (r.stdout or "").strip()
    except OSError:
        return ""


def deploy(a):
    say("\n--- publish ---")
    # --branch sends the deploy to production whatever git says, so a branch
    # checked out in this folder would be published as the site. publish.bat
    # refuses the same way.
    branch = current_branch()
    if branch != REPO_BRANCH:
        say(f"\nNOT DEPLOYED: this folder is on branch {branch or '(unknown)'}, not "
            f"{REPO_BRANCH}. A deploy publishes whatever the folder holds.")
        return False
    for attempt in range(1, 5):
        # --branch names the production branch rather than letting wrangler
        # take it from git; publish.bat says why. Four attempts, as
        # publish.bat: a timeout uploading the large files, not a refusal.
        r = child.run(["npx", "wrangler", "pages", "deploy", a.site,
                       f"--project-name={a.project}",
                       f"--branch={PRODUCTION_BRANCH}", "--commit-dirty=true"],
                      capture_output=True, shell=(sys.platform == "win32"))
        for ln in ((r.stdout or "") + (r.stderr or "")).rstrip().splitlines()[-12:]:
            say("  " + ln)
        if r.returncode == 0:
            break
        say(f"  upload attempt {attempt} of 4 failed")
    else:
        say("\nSTOPPED: the deploy failed four times. The previous version is still live.")
        return False
    time.sleep(8)
    if run(["check_live.py", "--gate", "--base", a.base, "--site", a.site],
           "what the live site is now serving") != 0:
        say("\nDEPLOYED, BUT THE LIVE SITE IS NOT SERVING WHAT WAS BUILT.\n"
            "A previous version can be restored from the Deployments tab in Cloudflare.")
        return False
    say(f"\nLive at {a.base}")
    return True


if __name__ == "__main__":
    sys.exit(main())
