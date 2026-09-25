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

ON GITHUB'S MACHINE: --runner (25 September 2026)

The same night, run by GitHub Actions on a fresh Windows machine
(.github/workflows/nightly.yml), because the person accepted
reports/cloud/CLOUD_MOVE.md. The workflow brings the kit and state/ down from
R2 before this runs and takes what changed back up afterwards; everything the
night itself does is here, and what differs on that machine is behind --runner:

  the refusal record  archive/refused.json as ever, but the machine is gone by
                      morning and a refusal has to outlive it: cloud.py brings
                      R2's state/refused.json down to it before the night, and
                      the workflow sends it back the moment one is on file
  the day's data      the website's fourteen files as ever, then the study
                      committees' meetings and details from the database (the
                      calendar shows them), each into a scratch folder first
                      and swapped in only if it arrived whole
  the build           build_all.py --local --no-captions: that machine holds
                      no caption files, so the step that reads them is skipped
                      and says so
  the gates           against archive/census.json, the last good build's
                      counts, which cloud.py carries in R2's state/, because
                      site/ starts empty. No census is no baseline, and that
                      night cannot go to production
  production          never from the night itself. A build may go only if the
                      gates had a baseline and passed, the late-caption check
                      compared something (without the caption files it cannot,
                      and 156 timestamps would go out an hour early), no
                      tracked code changed on the machine, and graniterecord.org
                      is not already serving it. Then a separate job behind the
                      "production" environment deploys it, once approved
  deploys             --deploy-to preview|production, workflow steps of their
                      own that alone hold the Pages token; wrangler pinned;
                      the live check retried before a deploy is called failed
  reader reports      not pulled there. They stay on the laptop, where the
                      morning triage pulls them
  the log             the whole log to logs/nightly-<date>.log, which goes to
                      R2; GitHub's log, which is public, gets each step's name
                      and result, and a failing step's last lines
  the verdict         archive/last-night.json (R2's state/last-night.json):
                      what the night did and whether it was clean, finished
                      by --close with the workflow's own step results

--runner --weekly is Sunday night's job (.github/workflows/weekly.yml): the
committee rosters, the members who have left and the study committees'
members and bills, one fetch at a time, each whole or not at all, with a
report of what changed in reports/gc-changes-weekly-<date>.md, beside the
night's own what-changed reports.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
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

# ---- GitHub's machine --------------------------------------------------------

# The branch a runner's preview goes to. Anything that is not PRODUCTION_BRANCH
# is a preview to Cloudflare, and this one answers at
# https://nightly.graniterecord.pages.dev.
PREVIEW_BRANCH = "nightly"

# npx takes whatever wrangler is newest unless told. CLOUD_MOVE.md recorded
# 4.140.0 in the laptop's npx cache on 25 September, which is the version the
# laptop's own deploys have been made with.
WRANGLER = "wrangler@4.140.0"

# What travels between nights: cloud.py carries each of these to R2's state/
# prefix and back (cloud_kit.json's "state" list). The refusal record travels
# the same way, and is refusal.MARK itself.
CENSUS = Path("archive/census.json")          # the last good build's counts and fingerprint
VERDICT = Path("archive/last-night.json")     # what tonight did, and whether it was clean
WEEKLY_VERDICT = Path("archive/last-weekly.json")

# Scratch space for a fetch that must arrive whole before it replaces anything.
# Inside the working folder, so a swap is a rename on the same disk.
SCRATCH = Path(".night")

# The study committees' views, from the General Court's database. The calendar
# shows the meetings, so those two come every night; the members and the bills
# that made each committee come on Sunday. fetch_archive_db.GITHUB_VIEWS names
# the same four, and preflight holds the lists together.
STUDY_NIGHTLY = ("StatStudMeetings", "StatStudDetails")
STUDY_WEEKLY = ("StatStudMembers", "vStatStudTemp")

# A result this much smaller than the copy it would replace is not swapped in:
# snapshot_gencourt's rule for the day's files, used for every other fetch.
SWAP_SHRINK = 0.30

# The live check is retried before a deploy is called failed: on 24 September
# the laptop's publish said THE DEPLOY DID NOT LAND for a deploy that had,
# because it looked eight seconds after the upload.
LIVE_WAITS = (10, 30, 60, 120)

# Tracked files that are code. On GitHub's machine nobody edits anything, so a
# tracked code file differing from the commit means something wrote where it
# should not have, and that build does not go to production. A tracked DATA
# file the build rewrote is reported and does not stop it; the two tracked
# files the night's own fetch installs (GeneralCodes.txt, BodyStatusCodes.txt)
# are its job and are not even reported.
CODE_SUFFIXES = (".py", ".js", ".mjs", ".css", ".html", ".bat", ".cmd", ".ps1",
                 ".sh", ".toml", ".yml", ".yaml")

QUIET = False             # --runner: child output to the log file only


def say(msg="", echo=True):
    """Print and log a line. With --runner a step's own output is logged and not
    printed (echo=False), because GitHub's log is public."""
    if echo or not QUIET:
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


def run(args, label, cwd=None):
    """Stream the step's output as it happens, and log it too. The exit code.

    A child of this process, run with this interpreter directly and no shell,
    so a fetch it starts sees this process as its parent and runs under the
    lock this process holds.
    """
    say(f"\n--- {label} ---")
    t0 = time.time()
    mark = len(LOG)
    proc = child.popen([sys.executable, "-u"] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, bufsize=1, cwd=cwd)
    for ln in proc.stdout:
        say("  " + ln.rstrip(), echo=False)
    proc.wait()
    if QUIET and proc.returncode:
        # GitHub's log says why a step failed without anyone opening the
        # whole log: its failure lines and its last few.
        for ln in failure_lines(LOG[mark:]):
            print(ln, flush=True)
    say(f"  ({time.time() - t0:.0f}s, exit {proc.returncode})")
    return proc.returncode


def failure_lines(lines, tail=6):
    """What a failed step said about failing, for a log that shows no more."""
    hits = [ln for ln in lines if re.search(
        r"\b(FAIL\w*|ERROR|STOPPED|NOT|Traceback|[Rr]efused)\b", ln)][:12]
    last = [ln for ln in lines if ln.strip()][-tail:]
    return hits + [ln for ln in last if ln not in hits]


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


FINGERPRINTED = ("index.json", "meta.json", "home.json", "legislators.json")


def fingerprint(site):
    """Changed or not, without caring about file order or timestamps."""
    h = hashlib.sha256()
    for name in FINGERPRINTED:
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
    # GitHub's machine. The docstring says what each one changes.
    ap.add_argument("--runner", action="store_true",
                    help="the night on GitHub's machine, not the laptop")
    ap.add_argument("--dry-run", action="store_true",
                    help="(--runner) a supervised run: nothing goes to production, and "
                         "what would have stopped it is reported without failing the night")
    ap.add_argument("--weekly", action="store_true",
                    help="(--runner) Sunday night's fetches instead of the night")
    ap.add_argument("--deploy-to", choices=("preview", "production"),
                    help="(--runner) deploy tonight's build; a workflow step of its own")
    ap.add_argument("--close", action="store_true",
                    help="(--runner) finish the verdict with the workflow's step results")
    ap.add_argument("--outcome", action="append", default=[], metavar="STEP=RESULT",
                    help="(--close) one workflow step's result; repeatable")
    a = ap.parse_args()

    # THE STAND-DOWN. Once GitHub runs the nightly, the laptop does not, in any
    # form: two builds from two copies of the data, two writers of every
    # carried file. Never on GitHub's own machine.
    refusal.stand_down("The nightly", 'On GitHub, "Run workflow" on the nightly in '
                       "the repository's Actions tab runs it by hand.")
    if a.runner:
        if a.deploy:
            ap.error("--deploy is the laptop's. On GitHub's machine the deploys are "
                     "--deploy-to steps, and production is behind its own environment.")
        on_the_runner()
        if a.close:
            return close_verdict(a)
        if a.deploy_to:
            return runner_deploy(a)
        if a.weekly:
            return weekly(a)
    elif a.weekly or a.deploy_to or a.close or a.dry_run:
        ap.error("--weekly, --deploy-to, --close and --dry-run are for GitHub's "
                 "machine, with --runner")

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
    reports = not a.runner  # the reports are pulled on every run on the laptop,
                            # including a deferred one: see the build_running
                            # branch below. Never on GitHub's machine.
    night = Night(a, started) if a.runner else None
    say("=" * 74)
    say(f"Granite Record nightly  {started:%Y-%m-%d %H:%M}")
    say("=" * 74)
    if night:
        night.intro()
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
            if night:
                night.v["build"] = "deferred: a build was running"
                return 1
            code = 0
            return 0

        if run(["preflight.py", "--code"], "preflight") != 0:
            say("\nSTOPPED: preflight failed. Nothing fetched, nothing built.")
            if night:
                night.v["preflight"] = "failed"
            return 1
        if night:
            night.v["preflight"] = "passed"

        installed = False
        if a.no_fetch:
            say("\n--- fetch ---\n  skipped: --no-fetch")
            if night:
                night.v["fetch"] = "not asked"
        else:
            ok, why = gc_quiet()
            if not ok:
                say(f"\nFETCH DEFERRED: {why}")
                if night:
                    night.v["fetch"] = f"deferred: {why}"
            else:
                try:
                    with refusal.hold("nightly"):
                        rc = run(["snapshot_gencourt.py", "--dir", a.archive, "--into", "."],
                                 "the day's bulk files")
                        # On GitHub's machine the study committees' meetings
                        # come with the day's files, under the same lock: the
                        # calendar shows them, and nothing else refreshes them.
                        if night and rc == 0 and not refusal.MARK.exists():
                            night.v["study_meetings"] = take_views(
                                STUDY_NIGHTLY, "the study committees' meetings, from the database")
                except SystemExit as e:
                    rc = e.code if isinstance(e.code, int) else 3
                    say(f"  the lock was taken by someone else first (exit {rc})")
                installed = rc == 0
                if night:
                    night.v["fetch"] = {0: "installed", 2: "refused"}.get(
                        rc, f"did not complete (exit {rc})")
                if rc == 2:
                    say("\nREFUSED while fetching. Recorded; every fetch now waits "
                        "for a person.")
                elif rc != 0:
                    say(f"\nThe fetch did not complete (exit {rc}); nothing was "
                        "installed, so tonight's build would be yesterday's.")

        if installed:
            rc = run(["gc_changes.py", "--archive", a.archive,
                      "--out", f"reports/gc-changes-{day}.md"], "what the General Court changed")
            if night:
                night.v["changes_report"] = ("written" if rc == 0 and
                                             Path(f"reports/gc-changes-{day}.md").exists()
                                             else f"not written (exit {rc})")

        rebuilt = False
        if installed or a.no_fetch:
            if night:
                # site/ starts empty on GitHub's machine: last night's counts
                # come from archive/census.json, or there is no baseline.
                before, before_fp = night.baseline()
            else:
                before = census(site)
                before_fp = fingerprint(site)
            if run(["build_all.py", "--local"] + (["--no-captions"] if a.runner else []),
                   "rebuild") != 0:
                say("\nSTOPPED: the build failed. The live site is untouched.")
                if night:
                    night.v["build"] = "failed"
                return 1
            if run(["check_site.py", "--site", a.site, "--base", a.base],
                   "check the built site") != 0:
                say("\nSTOPPED: check_site failed. The live site is untouched.")
                if night:
                    night.v.update(build="passed", check_site="failed")
                return 1
            rebuilt = True
            after = census(site)
            if before is None:
                stop, blocked = [], []
                lines = [f"  {'':<14}{'before':>10}{'after':>10}"]
                lines += [f"  {key:<14}{'-':>10}{after[key]:>10,}" for key, _ in GATES]
                lines.append(f"  {'files':<14}{'-':>10}{after['files']:>10,}   "
                             f"ceiling {FILE_CEILING:,}")
                if after["files"] >= FILE_CEILING:
                    stop = [f"{after['files']:,} files is past the {FILE_CEILING:,} ceiling"]
            else:
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

            if night:
                night.judge(site, before, after, stop, changed)
            elif a.deploy and not stop and changed:
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

        if night:
            code = night.exit_code()
            return code
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
        elif night:
            say("\nThe reader reports are not pulled on GitHub's machine. They stay on the "
                "laptop, where the morning triage pulls them.")
            night.finish(code)
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


# =============================================================================
# GitHub's machine. Nothing below runs without --runner.
# =============================================================================

def on_the_runner():
    """What --runner changes before anything else happens: a step's own output
    goes to the log file only, and archive/ is there for what travels."""
    global QUIET
    QUIET = True
    Path("archive").mkdir(exist_ok=True)


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                   newline="\n")
    os.replace(tmp, path)


def github(name, default=""):
    return os.environ.get(name, default)


def gh_output(**kv):
    """Step outputs for the workflow's later steps and jobs, when there is one."""
    out = github("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as fh:
        for k, v in kv.items():
            fh.write(f"{k}={str(v).lower() if isinstance(v, bool) else v}\n")


def gh_summary(lines):
    """A few lines on the run's page on GitHub, when there is one. Public."""
    out = github("GITHUB_STEP_SUMMARY")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def count_lines(path):
    n = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            n += chunk.count(b"\n")
    return n


def take_views(views, label):
    """The study committees' views from the database, whole or not at all.

    fetch_archive_db.py writes straight over db/<view>.psv and exits 0 even
    when a view fails, so it is run in a scratch folder, and each view replaces
    the installed copy only if the query succeeded, the file holds exactly the
    rows the query counted, and it is not sharply smaller than what it
    replaces. The views' entries in db/_manifest.json follow them in; the
    calendar reads the meetings' date from there. {view: what happened}.
    """
    scratch = SCRATCH / "views"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    script = str(Path("fetch_archive_db.py").resolve())
    rc = run([script, "--refetch"] + [x for v in views for x in ("--only", v)],
             label, cwd=scratch)
    man = load_json(scratch / "db" / "_manifest.json") or {}
    installed_man = load_json(Path("db") / "_manifest.json") or {}
    took, out = False, {}
    for v in views:
        new, old = scratch / "db" / f"{v}.psv", Path("db") / f"{v}.psv"
        entry = man.get(v) or {}
        if entry.get("error") or not new.exists() or not entry.get("rows"):
            out[v] = ("not taken: " + str(entry.get("error") or f"nothing came back (exit {rc})"))[:240]
            continue
        rows = count_lines(new)
        if rows != entry["rows"]:
            out[v] = (f"not taken: the file holds {rows:,} lines and the query "
                      f"counted {entry['rows']:,}")
            continue
        was = count_lines(old) if old.exists() else 0
        if was and rows < was * (1 - SWAP_SHRINK):
            out[v] = f"not taken: {rows:,} rows against {was:,} installed"
            continue
        old.parent.mkdir(exist_ok=True)
        os.replace(new, old)
        installed_man[v] = entry
        took = True
        out[v] = f"installed, {rows:,} rows (was {was:,})"
    if took:
        write_json(Path("db") / "_manifest.json", installed_man)
    shutil.rmtree(scratch, ignore_errors=True)
    for v, what in out.items():
        say(f"  {v}: {what}")
    return out


def take_json(label, args, installed, count, seed=False, shrink=SWAP_SHRINK):
    """One fetch that writes one JSON file, whole or not at all.

    The fetch writes into the scratch folder (--out); the result replaces
    `installed` only if the fetch exited 0, the file parses, count() finds
    something in it, and it is not more than `shrink` smaller than the copy it
    replaces. seed copies the installed file in first, for a fetch that merges
    into what is already there. (what happened, exit status of the fetch)
    """
    def n(d):
        try:
            return count(d) if d is not None else 0
        except (TypeError, AttributeError):
            return 0

    installed = Path(installed)
    SCRATCH.mkdir(exist_ok=True)
    new = SCRATCH / installed.name
    new.unlink(missing_ok=True)
    if seed and installed.exists():
        shutil.copyfile(installed, new)
    rc = run(args + ["--out", str(new)], label)
    got = load_json(new) if new.exists() else None
    was = n(load_json(installed)) if installed.exists() else 0
    if rc != 0 or got is None:
        what = f"not taken: the fetch exited {rc}" + ("" if got is not None else ", no file")
    elif not n(got):
        what = "not taken: it came back empty"
    elif was and n(got) < was * (1 - shrink):
        what = f"not taken: {n(got):,} against {was:,} installed"
    else:
        installed.parent.mkdir(parents=True, exist_ok=True)
        os.replace(new, installed)
        what = f"installed, {n(got):,} (was {was:,})"
    new.unlink(missing_ok=True)
    say(f"  {installed}: {what}")
    return what, rc


def captions_compared(work="work", markers="candidate_segments.json"):
    """(compared, recordings): the late-caption check, as the build makes it.

    build_site_v2.withhold_late_captions withholds every time read off a
    caption track that stops well short of its recording -- 156 of them on
    18 recordings when CLOUD_MOVE.md measured it -- and it can only do that by
    reading where each track stops. With no caption file for any recording it
    compares nothing, withholds nothing, and prints one line. The same
    recordings, the same question, asked here so that the night can refuse to
    send that build to production rather than print a line about it.
    """
    import caption_span
    vids = set()
    w = Path(work)
    if w.is_dir():
        vids |= {f.stem for f in w.glob("*.json")}
        vids |= {d.name for d in w.iterdir() if d.is_dir() and (d / "segments.json").exists()}
    marks = load_json(markers) or {}
    vids |= {k for k in marks if not str(k).startswith("_")}
    if not vids:
        return 0, 0
    _late, compared, _undated = caption_span.out_of_step(vids, work)
    return compared, len(vids)


def tracked_changes():
    """(code, data): tracked files that differ from the commit, by kind.

    The day's files snapshot_gencourt.py installs are left out: installing
    them is the night's job, and two of them are tracked.
    """
    import snapshot_gencourt
    ours = set(snapshot_gencourt.FILES) | {name for _, name in snapshot_gencourt.EXTRA}
    try:
        r = child.run(["git", "status", "--porcelain", "--untracked-files=no"],
                      capture_output=True)
    except OSError as e:
        return [f"(git would not run: {e})"], []
    if r.returncode != 0:
        return [f"(git status exit {r.returncode})"], []
    code, data = [], []
    for ln in (r.stdout or "").splitlines():
        p = ln[3:].strip().strip('"').split(" -> ")[-1]
        if not p or p in ours:
            continue
        is_code = p.lower().endswith(CODE_SUFFIXES) or p.startswith(("functions/", ".github/"))
        (code if is_code else data).append(p)
    return code, data


def live_fingerprint(base, timeout=180):
    """fingerprint() of what `base` serves now, or None if it could not be read.

    The same four files, so the two compare: equal means production already
    serves this build, and there is nothing to approve.
    """
    h = hashlib.sha256()
    for name in FINGERPRINTED:
        req = urllib.request.Request(f"{base.rstrip('/')}/{name}", headers={
            "User-Agent": "granite-record-selfcheck/1.0", "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                h.update(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:           # as fingerprint() passes over a missing file
                continue
            return None
        except Exception:               # noqa: BLE001 -- unreadable is "may differ"
            return None
    return h.hexdigest()[:16]


def site_manifest(site, out):
    """Every file in site/ with its sha256 and size, sorted: the file-for-file
    comparison CLOUD_MOVE.md asks of the first dry runs, and the record of what
    a night built. The files it lists."""
    rows = []
    for p in site.rglob("*"):
        if p.is_file():
            h = hashlib.sha256()
            with p.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            rows.append((p.relative_to(site).as_posix(), h.hexdigest(), p.stat().st_size))
    rows.sort()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"{d}  {s}  {r}\n" for r, d, s in rows), encoding="utf-8",
                   newline="\n")
    return len(rows)


class Night:
    """What --runner records about one night, and what it decides from it."""

    def __init__(self, a, started):
        self.a = a
        self.day = f"{started:%Y-%m-%d}"
        self.v = {"kind": "nightly", "day": self.day,
                  "started": started.isoformat(timespec="seconds"),
                  "run_id": github("GITHUB_RUN_ID"), "attempt": github("GITHUB_RUN_ATTEMPT"),
                  "sha": github("GITHUB_SHA"), "on_github": github("GITHUB_ACTIONS") == "true",
                  "asked": {"fetch": not a.no_fetch, "dry_run": a.dry_run},
                  "built": False, "publishable": False, "clean": False}

    def intro(self):
        say(f"on GitHub's machine: commit {self.v['sha'][:12] or '(not on GitHub)'}, "
            f"run {self.v['run_id'] or '-'}; "
            + ("taking the day's data" if not self.a.no_fetch else "no fetch")
            + ("; a dry run: nothing goes to production" if self.a.dry_run else ""))
        say(f"  the refusal record is {refusal.MARK}; python {sys.version.split()[0]}")

    def baseline(self):
        """(census, fingerprint) of the last good build, from CENSUS, or (None, None)."""
        rec = load_json(CENSUS)
        c = rec.get("census") if isinstance(rec, dict) else None
        if not isinstance(c, dict) or any(not isinstance(c.get(k), int)
                                          for k in [g for g, _ in GATES] + ["files"]):
            say(f"\n  no usable {CENSUS}: the gates have nothing to compare "
                "tonight's build with")
            return None, None
        say(f"\n  the gates compare with the build of {rec.get('day', '?')} "
            f"(run {rec.get('run_id') or '?'}), from {CENSUS}")
        return c, rec.get("fingerprint")

    def judge(self, site, before, after, stop, changed):
        """After a build that passed check_site: can it go to production?"""
        v, a = self.v, self.a
        v.update(build="passed", check_site="passed", built=True, census=after,
                 changed=changed)
        fp = fingerprint(site)
        v["fingerprint"] = fp
        blocking = []
        if before is None:
            v["gates"] = "no baseline"
            blocking.append("there is no census from an earlier night, so the gates had "
                            "nothing to compare with; tonight's counts are the baseline "
                            "from tomorrow")
        elif stop:
            v["gates"] = "blocked: " + "; ".join(stop)
            blocking += stop
        else:
            v["gates"] = "passed"

        compared, of = captions_compared()
        v["late_captions"] = {"compared": compared, "recordings": of}
        if of and not compared:
            blocking.append(
                f"the late-caption check compared none of {of:,} recordings: there is no "
                "caption file, or summary of one, on this machine, so a caption track an "
                "hour out of step with its recording would be published as it is")

        code, data = tracked_changes()
        v["code_changed"], v["data_rewritten"] = code, data
        if code:
            blocking.append("tracked code differs from the commit: " + ", ".join(code[:6]))
        if data:
            say("\n  tracked data files the night rewrote (reported, not a stop): "
                + ", ".join(data[:12]) + (f" and {len(data) - 12} more" if len(data) > 12 else ""))

        live = live_fingerprint(a.base)
        v["live_fingerprint"] = live
        already = live == fp
        if not stop:
            write_json(CENSUS, {"census": after, "fingerprint": fp,
                                             "day": self.day, "run_id": v["run_id"],
                                             "sha": v["sha"]})
            say(f"  tonight's counts are the baseline now: {CENSUS}")
        n = site_manifest(site, Path("logs") / f"site-{self.day}.sha256")
        say(f"  logs/site-{self.day}.sha256 lists all {n:,} files, with their sha256")

        v["blocking"] = blocking
        v["publishable"] = not blocking and not already
        say("\n--- production ---")
        if blocking:
            say("\nNOT FOR PRODUCTION TONIGHT: " + " | ".join(blocking))
        elif already:
            say(f"\n  {a.base} already serves this build: there is nothing to publish")
        elif a.dry_run:
            say("\n  this build could go to production; a dry run sends nothing there")
        else:
            say("\n  this build can go to production. The publish job waits for approval "
                "in the \"production\" environment, where there is a reviewer.")

    def problems(self):
        """Why tonight was not clean, by CLOUD_MOVE.md's list; [] when it was."""
        v, why = self.v, []
        if v.get("preflight") != "passed":
            why.append("preflight " + str(v.get("preflight", "did not run")))
        if not self.a.no_fetch:
            if v.get("fetch") != "installed":
                why.append(f"the day's files: {v.get('fetch', 'not taken')}")
            else:
                bad = [f"{k}: {r}" for k, r in (v.get("study_meetings") or {}).items()
                       if not r.startswith("installed")]
                if not v.get("study_meetings"):
                    bad = ["the study committees' meetings were not taken"]
                why += bad
                if v.get("changes_report") != "written":
                    why.append(f"the what-changed report: {v.get('changes_report', 'not run')}")
        if v.get("build") != "passed":
            why.append(f"the build: {v.get('build', 'not run')}")
        elif v.get("check_site") != "passed":
            why.append(f"check_site: {v.get('check_site', 'not run')}")
        else:
            why += [b for b in v.get("blocking", []) if b not in why]
        return why

    def exit_code(self):
        """0 when the night did what it was asked. A dry run is asked for a build
        and, if it was told to fetch, the day's data; the rest is reported."""
        why = self.problems()
        if self.a.dry_run:
            asked = [w for w in why if not any(w == b for b in self.v.get("blocking", []))]
            return 1 if asked else 0
        return 1 if why else 0

    def finish(self, code):
        v = self.v
        why = self.problems()
        v.update(finished=datetime.now().isoformat(timespec="seconds"), exit=code,
                 clean=not why and code == 0, not_clean=why)
        write_json(VERDICT, v)
        say(f"\nverdict: {'CLEAN' if v['clean'] else 'NOT CLEAN'} -> {VERDICT}")
        for w in why:
            say(f"  - {w}")
        gh_output(built=bool(v.get("built")), publishable=bool(v.get("publishable")),
                  clean=bool(v["clean"]), day=self.day)
        gh_summary([f"### Nightly {self.day}: {'clean' if v['clean'] else 'not clean'}",
                    f"- built: {'yes' if v.get('built') else 'no'}; for production: "
                    f"{'yes' if v.get('publishable') else 'no'}"]
                   + [f"- {w}" for w in why[:8]])


def runner_deploy(a):
    """--deploy-to preview|production: tonight's build, to one of two places.

    A workflow step of its own, because it alone is given the Pages token.
    Tonight's verdict decides: a preview needs a build that passed its checks;
    production needs a build the night judged fit for it, the same site as the
    one judged (by fingerprint), this folder on REPO_BRANCH, and the newest
    night -- an older night's approval is refused, because a newer one has run.
    """
    where = a.deploy_to
    vpath = VERDICT
    v = load_json(vpath) or {}
    site = Path(a.site)
    rid = github("GITHUB_RUN_ID")
    say(f"\n--- deploy to {where} ---")
    if rid and v.get("run_id") != rid:
        say(f"\nNOT DEPLOYED: {vpath} is the verdict of run {v.get('run_id') or '(none)'}, "
            f"not this run ({rid})."
            + (" A newer night has run since; approve that one." if where == "production" else ""))
        return 1
    if where == "preview":
        if not v.get("built"):
            say("\nNOT DEPLOYED: tonight's build did not pass its checks.")
            return 1
        target, base = PREVIEW_BRANCH, f"https://{PREVIEW_BRANCH}.{a.project}.pages.dev"
    else:
        if not v.get("publishable"):
            say("\nNOT DEPLOYED: tonight's verdict does not send this build to production.")
            return 1
        if fingerprint(site) != v.get("fingerprint"):
            say("\nNOT DEPLOYED: the site in this folder is not the build tonight's checks "
                "passed (its fingerprint differs).")
            return 1
        branch = current_branch()
        if branch != REPO_BRANCH:
            say(f"\nNOT DEPLOYED: this folder is on branch {branch or '(unknown)'}, not "
                f"{REPO_BRANCH}.")
            return 1
        target, base = PRODUCTION_BRANCH, a.base
    landed = upload_and_check(a, site, target, base)
    if where == "preview":
        v["preview"] = {"at": datetime.now().isoformat(timespec="seconds"),
                        "base": base, "landed": landed}
        write_json(vpath, v)
    log = Path("logs") / f"nightly-{v.get('day', '')}.log"
    if log.exists():
        with log.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(LOG) + "\n")
    return 0 if landed else 1


def upload_and_check(a, site, target, base):
    """wrangler to `target`, four attempts, then the live check, retried."""
    out = ""
    for attempt in range(1, 5):
        # The pinned wrangler, with the branch named: PREVIEW_BRANCH is a
        # preview to Cloudflare, PRODUCTION_BRANCH is the site.
        r = child.run(["npx", "--yes", WRANGLER, "pages", "deploy", str(site),
                       f"--project-name={a.project}", f"--branch={target}",
                       "--commit-dirty=true"],
                      capture_output=True, shell=(sys.platform == "win32"))
        out = (r.stdout or "") + (r.stderr or "")
        for ln in out.rstrip().splitlines()[-12:]:
            say("  " + ln)
        if r.returncode == 0:
            break
        say(f"  upload attempt {attempt} of 4 failed")
    else:
        say("\nSTOPPED: the deploy failed four times. What was there before is still there.")
        return False
    for i, wait in enumerate(LIVE_WAITS, 1):
        time.sleep(wait)
        if run(["check_live.py", "--gate", "--base", base, "--site", str(site)],
               f"what {base} is serving (look {i} of {len(LIVE_WAITS)})") == 0:
            say(f"\nLive at {base}")
            return True
    say(f"\nDEPLOYED, BUT {base} IS NOT SERVING WHAT WAS BUILT, after "
        f"{sum(LIVE_WAITS)} seconds of looking. A previous version can be restored "
        "from the Deployments tab in Cloudflare.")
    return False


def close_verdict(a):
    """--close: the workflow's own step results, folded into the verdict.

    The last word on a night, run whatever happened before it. If the night
    stopped before nightly.py wrote a verdict -- the kit did not come down, say
    -- the verdict state-down left here is an older night's, and this replaces it
    with one that says so, rather than letting last night's CLEAN stand.

    Exit 1 when any step it is told of failed, so a step allowed to carry on
    past its own failure -- the livestreams -- still fails the night at the end.
    """
    path = WEEKLY_VERDICT if a.weekly else VERDICT
    v = load_json(path)
    rid = github("GITHUB_RUN_ID")
    steps = {}
    for o in a.outcome:
        k, _, r = o.partition("=")
        steps[k.strip()] = r.strip()
    if not isinstance(v, dict) or v.get("run_id") != rid:
        v = {"kind": "weekly" if a.weekly else "nightly", "run_id": rid,
             "sha": github("GITHUB_SHA"), "day": f"{datetime.now():%Y-%m-%d}",
             "clean": False, "built": False, "publishable": False,
             "not_clean": [f"the {'weekly job' if a.weekly else 'night'} stopped before "
                           "nightly.py recorded what it did"]}
    v["steps"] = steps
    failed = [f"{k} ({r})" for k, r in steps.items() if r not in ("success", "skipped", "")]
    if failed:
        v["clean"] = False
        v.setdefault("not_clean", []).append("workflow steps that did not succeed: "
                                             + ", ".join(failed))
    v["closed"] = datetime.now().isoformat(timespec="seconds")
    write_json(path, v)
    print(f"{path}: {'CLEAN' if v.get('clean') else 'NOT CLEAN'}"
          + ("" if v.get("clean") else " -- " + "; ".join(v.get("not_clean", [])[:4])))
    return 1 if failed else 0


# ---- Sunday night ------------------------------------------------------------

def seats(d):
    return sum(len(x) for x in d.values()) if isinstance(d, dict) else 0


def committee_count(d):
    return sum(len(x) for x in d.values() if isinstance(x, list)) if isinstance(d, dict) else 0


def weekly(a):
    """--runner --weekly: the Sunday fetches, whole or not at all, and what they changed.

    Four things the build reads and the day's files do not carry, each fetched
    into the scratch folder and swapped in only if it arrived whole and is not
    sharply smaller than what it replaces:

      data/committee_members.json   who sits on each committee (the database)
      former_members.json           members who have left (the database; merged)
      db/StatStudMembers.psv and    the study committees' members, and the bill
      db/vStatStudTemp.psv          that made each (the database)
      committees.json               chairs, vice chairs, aides and rooms (two
                                    pages of gc.nh.gov, under the refusal rule)

    One at a time, a few seconds apart, under the same lock and the same
    refusal record as the night; the database first, the web server last.
    """
    started = datetime.now()
    day = f"{started:%Y-%m-%d}"
    v = {"kind": "weekly", "day": day, "started": started.isoformat(timespec="seconds"),
         "run_id": github("GITHUB_RUN_ID"), "sha": github("GITHUB_SHA"),
         "asked": {"fetch": not a.no_fetch}, "results": {}, "clean": False}
    code = 1
    lock = Path(".nightly.lock")
    lock.write_text(f"{started:%Y-%m-%d %H:%M} pid {os.getpid()} (weekly)", encoding="utf-8")
    say("=" * 74)
    say(f"Granite Record weekly  {started:%Y-%m-%d %H:%M}")
    say("=" * 74)
    say(f"on GitHub's machine: commit {v['sha'][:12] or '(not on GitHub)'}; "
        f"the refusal record is {refusal.MARK}")
    before = {"committee_members": load_json("data/committee_members.json") or {},
              "former_members": load_json("former_members.json") or {},
              "committees": load_json("committees.json") or {},
              "study": {x: count_lines(Path("db") / f"{x}.psv")
                        for x in STUDY_WEEKLY if (Path("db") / f"{x}.psv").exists()}}
    try:
        if run(["preflight.py", "--code"], "preflight") != 0:
            say("\nSTOPPED: preflight failed. Nothing fetched.")
            v["preflight"] = "failed"
            return 1
        v["preflight"] = "passed"
        if a.no_fetch:
            say("\n--- fetch ---\n  skipped: --no-fetch")
            code = 0
            v["clean"] = True
            return 0
        ok, why = gc_quiet()
        if not ok:
            say(f"\nFETCH DEFERRED: {why}")
            v["results"]["all"] = f"deferred: {why}"
            return 1
        res = v["results"]
        with refusal.hold("weekly"):
            res["committee_members"], _ = take_json(
                "who sits on each committee, from the database",
                ["fetch_committee_members_db.py"], "data/committee_members.json", seats)
            time.sleep(4)
            res["former_members"], _ = take_json(
                "members who have left, from the database",
                ["fetch_members_db.py"], "former_members.json", len, seed=True, shrink=0.0)
            time.sleep(4)
            study = take_views(STUDY_WEEKLY, "the study committees' members and bills, "
                                             "from the database")
            res.update({f"study {k}": r for k, r in study.items()})
            time.sleep(4)
            if refusal.MARK.exists():
                res["committees"] = "not asked: a refusal is on file"
            else:
                res["committees"], rc = take_json(
                    "chairs, vice chairs, aides and rooms, from gc.nh.gov",
                    ["fetch_committees.py"], "committees.json", committee_count)
                if rc == 2:
                    say("\nREFUSED while fetching. Recorded; every fetch now waits for a person.")
        report = write_weekly_report(day, before)
        say(f"\n  what changed: {report}")
        bad = [f"{k}: {r}" for k, r in res.items() if not str(r).startswith("installed")]
        v["not_clean"] = bad
        v["clean"] = not bad
        code = 0 if not bad else 1
        return code
    finally:
        lock.unlink(missing_ok=True)
        shutil.rmtree(SCRATCH, ignore_errors=True)
        v.update(finished=datetime.now().isoformat(timespec="seconds"), exit=code)
        write_json(WEEKLY_VERDICT, v)
        say(f"\nverdict: {'CLEAN' if v.get('clean') else 'NOT CLEAN'} -> {WEEKLY_VERDICT}")
        gh_output(clean=bool(v.get("clean")), day=day)
        gh_summary([f"### Weekly {day}: {'clean' if v.get('clean') else 'not clean'}"]
                   + [f"- {k}: {r}" for k, r in v["results"].items()])
        say("\n" + "=" * 74)
        say(f"finished {datetime.now():%H:%M}, "
            f"{(datetime.now() - started).seconds // 60} min, exit {code}")
        logs = Path("logs")
        logs.mkdir(exist_ok=True)
        (logs / f"weekly-{day}.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")


def write_weekly_report(day, before):
    """reports/gc-changes-weekly-<day>.md: seats added and ended, members who have
    left, committees' leadership, and the study committees' row counts."""
    lines = [f"# What the weekly refresh changed, {day}", ""]

    old, new = before["committee_members"], load_json("data/committee_members.json") or {}
    lines += ["## Committee seats (data/committee_members.json)", ""]
    seat_lines = []
    for code in sorted(set(old) | set(new)):
        o = {m.get("id"): m for m in old.get(code, []) if isinstance(m, dict)}
        n = {m.get("id"): m for m in new.get(code, []) if isinstance(m, dict)}
        parts = []
        for label, ids in (("added", [i for i in n if i not in o]),
                           ("gone from the table", [i for i in o if i not in n]),
                           ("seat ended", [i for i in n if i in o and o[i].get("seat_active")
                                           and not n[i].get("seat_active")]),
                           ("seat resumed", [i for i in n if i in o and not o[i].get("seat_active")
                                             and n[i].get("seat_active")])):
            if ids:
                src = n if label != "gone from the table" else o
                parts.append(f"{label}: " + ", ".join(
                    f"{src[i].get('name', i)} ({src[i].get('party_code', '?')})" for i in ids))
        if parts:
            seat_lines.append(f"- {code}: " + "; ".join(parts))
    lines += (seat_lines or ["No change."]) + [""]

    old, new = before["former_members"], load_json("former_members.json") or {}
    lines += ["## Members who have left (former_members.json)", ""]
    added = [k for k in new if k not in old]
    lines += ([f"- {k}: {new[k].get('name', '?')} ({new[k].get('party', 'no party given')})"
               for k in sorted(added)] or ["No one newly listed."]) + [""]

    old, new = before["committees"], load_json("committees.json") or {}
    lines += ["## Committees, chairs and rooms (committees.json)", ""]
    c_lines = []
    for ch in sorted(set(old) | set(new)):
        o = {r.get("code"): r for r in old.get(ch, []) if isinstance(r, dict)}
        n = {r.get("code"): r for r in new.get(ch, []) if isinstance(r, dict)}
        for k in sorted(set(o) | set(n), key=str):
            if k not in o:
                c_lines.append(f"- {ch} {n[k].get('name', k)}: new")
            elif k not in n:
                c_lines.append(f"- {ch} {o[k].get('name', k)}: no longer listed")
            else:
                for f in ("chair", "vice_chair", "aide", "location"):
                    if (o[k].get(f) or "") != (n[k].get(f) or ""):
                        c_lines.append(f"- {ch} {n[k].get('name', k)}: {f.replace('_', ' ')} "
                                       f"was {o[k].get(f) or '(none)'}, now {n[k].get(f) or '(none)'}")
    lines += (c_lines or ["No change."]) + [""]

    lines += ["## Study and statutory committees (db/)", ""]
    for x in STUDY_WEEKLY:
        p = Path("db") / f"{x}.psv"
        now = count_lines(p) if p.exists() else 0
        lines.append(f"- {x}: {now:,} rows, was {before['study'].get(x, 0):,}")
    out = REPORTS / f"gc-changes-weekly-{day}.md"
    REPORTS.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    sys.exit(main())
