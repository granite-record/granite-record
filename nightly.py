#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.43
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
  upload rejected halfway. GitHub's workflow passes no --force: the one run
  there that may pass the census is the New term run (--new-term, below), and
  it cannot pass the ceiling either.

    bills          2% fewer in the bill index (idx/<term>.json, as meta.json
                   names them); none where it is not there or will not read
    legislators    2% fewer in legislators.json
    bill_data      2% fewer per-bill JSON files
    bill_pages     5% fewer static pages
    feeds          5% fewer feed files -- without this, a failed build_feeds
                   unpublishes every feed and no other count moves
    terms          1% fewer bills in any term but the newest, by its own list
                   (site/idx/<term>.json), on every run, the New term run
                   included (5 October 2026, terms_fell)

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
                      covered the recordings as it does on the laptop (with no
                      caption file and no summary of one it covers none, and
                      156 timestamps would go out an hour early), no tracked
                      code changed on the machine, and graniterecord.org is not
                      already serving it. Then a separate job behind the
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

THE ONE NIGHT A TERM TURNS OVER: --new-term (30 September 2026)

Each guard below is right to stop an ordinary night and wrong for the night
the General Court's files first show a new term, when they really do get
smaller. --new-term is "New term: accept the General Court's smaller files
once", a box on the nightly and the weekly run by hand, and only there: a
scheduled night never carries it. For that one run:

  the day's files     snapshot_gencourt.py --allow-shrink: tonight's files
                      are installed though they are much smaller, and the
                      log names each one. An empty file is still refused,
                      but for the two roll-call files when every other file
                      arrived whole and names the new term: none has voted
                      yet (snapshot_gencourt.MAY_BE_EMPTY, 5 October 2026)
  the study views     taken however much smaller, though never empty
  the feeds           build_all.py --allow-prune, for build_feeds.py. On
                      GitHub's machine site/ starts empty and nothing is
                      stale, so there the census is what sees feeds fall
  the census gates   a fall of the feeds is reported and does not stop the
                      night (NEW_TERM_MAY_FALL, since 5 October 2026: until
                      then any fall). Any other gate's fall, the sitting
                      legislators' included, a finished term that lost bills
                      and the file ceiling still stop it
  the weekly          the committee rosters, the committee list and the
                      study committees' views taken however much smaller,
                      never empty; the members who have left are a merge and
                      can never be smaller, so that guard stays

It is never a dry run, and never a run that does not fetch: the switch is the
run that takes the smaller files and may publish them, and it waits for the
person's approval in the "production" environment (nightly.yml says why that
must outlast the approvals of ordinary nights). Ticked with Dry run, or
without the fetch, it does nothing and says which boxes to tick.

A NEW TERM IS SEEN BY ITS YEARS (5 October 2026). Size was the only sign of a
turn, and on a copy a docket holding 2025, 2026 and 2027 grew, nothing shrank,
and a scheduled night would have published the new term unasked. Now the
snapshot refuses files that name a newer term than the installed ones,
whatever their size (snapshot_gencourt.judge), and the page says so
(NEW_TERM_TURN); the New term run passes --allow-turn as well. The switch is
the first night the files show the new term, Organization Day's resolutions
included (the person's decision of 5 October). And before that run asks
anything, the term it would leave must be frozen as installed
(new_term_ready, freeze_term.ready), or it stops and says to freeze first:
after the turn that term is built every night from its frozen inputs and
from nothing else. A file that turns on a later night -- LSRs.txt in January,
the roll calls at the first vote -- goes in on an ordinary night when the
copy it replaces is the finished term's frozen one, byte for byte; the page
names it among the warnings.

WHAT IT ACCEPTED IS KEPT ONLY ONCE ITS BUILD IS PUBLISHED (1 October 2026).
The first version of this wrote tonight's counts to archive/census.json and
let the workflow send the smaller files back to the kit the same night,
before anyone had approved anything. So a New term run that was rejected, or
still waiting when the next scheduled night began, or kept from production by
another blocker, had already made the smaller files the installed copies and
the lower counts the baseline: the next scheduled night would have taken the
new term's files without complaint and published the switch unasked. Now the
night of a New term run keeps nothing for later nights:

  the census          not written. The verdict carries tonight's counts, and
                      --deploy-to production writes them to archive/census.json
                      when, and only when, that deploy has landed
  the kit             the workflow's kit-up is given --hold: every file the
                      night changed waits under nights/<run>/kit/ in the
                      bucket, and kit/ keeps the copies it had. The publish job
                      runs cloud.py kit-release after the deploy has landed
  production          the publish job runs even when graniterecord.org already
                      serves this very build, because publishing is what lets
                      what the run accepted be kept

Until then the next night takes down the kit and the census as they were: it
meets the smaller files, refuses them, and its page says "a new term?" and
which boxes to tick -- and, when a New term run built the switch and was never
published, that too. The weekly job publishes nothing, so there is nothing
for its New term run to wait for: what it takes reaches the site with the
next night's build.

A NIGHT THE EXPORT FAILS: THE DATABASE (1 October 2026)

On 27 and 28 September and on 1 October the General Court's export came back
empty on every try -- its own page said "Error Generating ... File : Execution
Timeout Expired" -- and nothing was built those days. The same record is in
the SQL host the General Court publishes credentials for, and the person
approved the night asking it, gently, as the fallback. On GitHub's night only:

  when                the export was asked once and came back empty with
                      nothing else wrong (2 October 2026, DB_AFTER_TRIES:
                      until then it was asked EMPTY_TRIES times first, half
                      an hour apart, and the database only after the last);
                      no refusal from the web server is on file; no hold on
                      the SQL host is on file (probe_db.py's
                      archive/sql-held.json); the installed files are there
                      to take the years and the row order from; and it is not
                      a New term run. Never when the export arrived whole:
                      one source for the night's seven files. At once, with
                      no wait, and once a night at most
  what                fetch_day_db.py asks six views and five lookups, one
                      connection each, a few seconds apart (about 170,000
                      rows); dayfiles_from_db.py rebuilds the seven files that
                      change and guards them against the installed ones; the
                      seven and tonight's Members.txt go in through
                      snapshot_gencourt.install(), shrink rule and all, or
                      none does. The six lookups stay as the last good export
                      left them
  then                the night goes on as any night: the study committees'
                      views, next session's requests, the what-changed report
                      (on the columns both sources carry), the build, and the
                      same check_site, census and other gates
  it says so          the verdict keeps "fetch" as the truth about the export
                      and gains "day_files", which names the database; a
                      warning leads the run's page; DB_NIGHTS_MOST such nights
                      in a row is an error there, and the build still goes out.
                      "files_from" is the one word for where the installed
                      files came from, and "tried" lists what was asked for
                      them, in order, with how each ended
  what it let by      under a ceiling a few rows may differ from the installed
                      ones and the night install: a warning says how many,
                      and the rows -- the General Court's words, a member's
                      name -- are in the verdict (day_files, told), the log
                      and the what-changed report, never on the page. They
                      are not what "looked wrong" means below: only a check
                      that stops is
  a night it stops    one of the checks fired and nothing was installed: the
                      page says how many did, where they are named, that the
                      export was not asked again that night, that the site is
                      as it was, and what the next night will do, since the
                      installed files have not moved: the same check stops
                      the fallback again -- unless what stopped it is a
                      ceiling on a night's work, which is wider the older
                      those files are, and may let the same views by a night
                      later (stopped_next); that night's page says it did.
                      DB_STOPPED_MOST such nights since the files last moved,
                      counted by night and not by run, is an error
  how old             the checks' ceilings are a night's, and the installed
                      files may be older (nights_since): the checks are told
  a copy              nh-archive/from-db/<day>/, with a source.json that names
                      the files it replaced by their sha256, which is what the
                      what-changed report compares it with. The archive's
                      index stays the history of the website's files
  if it cannot be     a hold on file, a connection or a query that fails, a
  used                view cut short or not readable as the view it is, the
                      night's own step failing, no installed files: nothing
                      is installed from it, and none of these says anything
                      of the record itself. The
                      export is asked ONCE more, EMPTY_WAIT minutes later
                      (TRIES_AFTER_DB, which says why it is no longer five
                      times more), and a try that arrives whole is installed.
                      The database is not asked again that night, for the
                      study committees' views either (STUDY_NOT_AGAIN)
  if what it gave     a guard that stops, or rebuilt files much smaller than
  looked wrong        the copies installed (DB_LOOKED_WRONG): nothing is
                      installed and the export is not asked again that night
                      either. It is written from the same record, and a later
                      try would go in on the export's own, coarser, checks
  a New term run      never asks the database, and still asks the export up
                      to EMPTY_TRIES times, EMPTY_WAIT minutes apart: a person
                      started it, and a new term's files come from nowhere else

When nothing is installed the night is not clean. Its page says in this file's
own sentences what the export said and, when every try came back empty, what
the database did after which try and whether the export was asked again -- and,
of a night the checks stopped, how many did and where they are named; and it
lists what was asked for the day's files, in order, whichever way the last try
ended.

THAT HOST'S HOLD, ON A NIGHT THE EXPORT IS WHOLE. A connection to the SQL host
that fails is held (probe_db.py), and while the hold stands the night does not
ask it for the study committees' meetings either. That is a warning on the
night's page, the installed meetings stay, and the day's files are built and
published: another server's bad week does not hold the day's bills back. The
night the views' own connection is tried and fails is not clean, as it never
was. A connection that failed earlier the same night, when the database was
turned to for the day's files, has left its hold by then: the views are not
asked for, and that is the warning of a night whose export then arrived.

THE CALENDARS AND JOURNALS THE GENERAL COURT LISTS (1 October 2026)

The Calendar page links every House and Senate calendar and journal at the
General Court's own viewer address, from archive/queue.csv -- a list the
laptop last read on 13 September, so by 1 October it was three House calendars
behind and nothing refreshed it. The person approved the night reading it. On
GitHub's night only, with the day's files, under the same lock:

  what                fetch_calendar_archive.py --listing asks each chamber's
                      index page for its calendars and its journals of the
                      newest year: four requests, a few seconds apart and as
                      long before the first, and eight while two years' lists
                      can both still grow (its docstring says when). No
                      document is downloaded
  after the bill      it asks the address the bill requests were asked of a
  requests            moment before. If that fetch did not complete -- a
                      dropped connection ends it on 1 with no refusal on
                      record -- the list is not asked for that night
                      (EXITS): the lane's rule, that a step which fails
                      stops the chain, kept between these two
  whole or not        its answer goes to the scratch folder, and replaces the
                      installed list only if every list was read, none came
                      back empty or sharply shorter than the page listed when
                      it was last installed, nothing on file is missing or
                      moved, and each new address is the General Court's own
                      (its judge()). With it goes
                      archive/documents_listed.json: what each page listed,
                      in its words, and when
  short, night        a list that is only short is not taken that night. One
  after night         that comes back short the same way LIST_SAME_NIGHTS
                      nights running is the page's own, not a page half
                      served, and is taken then: the count rides in the
                      verdict (documents_short), so nobody has to edit the
                      night's file to let a real change through
  one writer          archive/queue.csv is the night's file in the kit from
                      this day. The laptop's drain still fetches the
                      documents, and what it fetched reaches this list
                      through its own file (archive/queue_fetched.csv)
  a failure           is a warning on the night's page and never a failed
                      night: the list installed stays, and a picker a few
                      days behind is no reason to hold back the day's docket.
                      A refusal met while asking is recorded as every
                      refusal is, and the next night does not ask at all
"""

import argparse
import gzip
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
from datetime import date, datetime
from pathlib import Path

import child
import refusal
import site_read as SR
from check_live import NOT_CHECKED as LIVE_NOT_CHECKED

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
# A finished term's rows that tonight's files still carried, counted and left
# out by build_data, with the bills they name (build_data.LEFT_OUT, under its
# --out; preflight holds the two names together). A night with none has none.
LEFT_OUT = Path("data/left_out.json")
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

# NEXT SESSION'S BILL REQUESTS (30 September 2026). fetch_lsrs.py merges each
# download into lsrs.json and marks a request that has gone as withdrawn, so a
# truncated download would withdraw real requests. The night keeps yesterday's
# file and puts it back when the fetch fails, writes nothing, or would newly
# withdraw more than LSR_GONE_MOST of the standing requests (and more than
# LSR_GONE_FLOOR). It warns rather than blocks: a list beside the record going
# stale for a night is no reason to hold back the day's docket, and a site
# left alone for a month must not stop because one page changed.
LSRS = Path("lsrs.json")
LSR_GONE_MOST = 0.10
LSR_GONE_FLOOR = 5

# THE CALENDARS AND JOURNALS THE GENERAL COURT LISTS (1 October 2026): the
# list the Calendar page's picker is built from, and what its pages listed
# when they were last read. fetch_calendar_archive.QUEUE and its
# listed_file(), which preflight holds these to. take_documents() says how
# the night takes them; like the bill requests, a night that cannot is a
# warning and never a stop.
DOCS = Path("archive/queue.csv")
DOCS_LISTED = Path("archive/documents_listed.json")
# A list that comes back sharply shorter is refused as a page half served. A
# page half served is one night's accident; the same documents missing on
# this many nights running is what the General Court's page now lists, and
# the night takes it. Without this a real change -- two files renamed in one
# day is enough, of sixteen -- refused all four lists every night after.
LIST_SAME_NIGHTS = 3
# How the night's own requests of the General Court's site ended, by script:
# take_lsrs writes its fetch's exit status, and take_documents, which asks
# the same address next, reads it. Emptied before the two are run.
EXITS = {}

# RECORDINGS WAITING FOR THEIR START TIMES (30 September 2026). YouTube refuses
# GitHub's machine the captions, so the laptop's evening job reads them. A
# finished recording the laptop has not read CAPTION_WAIT_DAYS after it ended
# is a warning: the laptop has been off, or its evening job is failing. Past
# CAPTION_WAIT_MOST days it is no longer counted, so no recording can hold a
# warning up for ever, and one with no captions published at all is not
# waiting for anything.
LIVE_STATE = Path("archive/livestreams.json")
CAPTION_WAIT_DAYS = 3
CAPTION_WAIT_MOST = 30
STUDY_WEEKLY = ("StatStudMembers", "vStatStudTemp")

# A result this much smaller than the copy it would replace is not swapped in:
# snapshot_gencourt's rule for the day's files, used for every other fetch.
SWAP_SHRINK = 0.30
# The New term run's: any fall at all, for that one run. An empty result is
# still refused -- take_json and take_views refuse one whatever this says.
NEW_TERM_SHRINK = 1.0
# What snapshot_gencourt's --into did, in the day's snapshot folder: its
# INSTALL_RECORD, which preflight holds to this.
INSTALL_RECORD = "install.json"
# ... and its MIN_BYTES, likewise held: a file shorter than this is an empty
# one (fetch_status, not_empty_file).
EMPTY_BYTES = 40

# The late-caption check has to cover the recordings as it does on the laptop,
# where on 25 September it compared 2,850 of the 2,851 recordings with
# published times. On GitHub's machine it can compare only what has a caption
# file there or the laptop's summary of one, and the livestream step's few new
# caption files are no cover for the rest. More left unchecked than this, or
# than 1% of them, and the build does not go to production.
LATE_CAPTION_UNCHECKED = 10

# The live check is retried before a deploy is called failed: on 24 September
# the laptop's publish said THE DEPLOY DID NOT LAND for a deploy that had,
# because it looked eight seconds after the upload.
LIVE_WAITS = (10, 30, 60, 120)
# What a deploy is called when the live check could not read a file to its end
# (check_live's NOT_CHECKED). Not "not serving what was built": nothing said it
# was not, and nothing said it was.
LIVE_UNREAD = ("DEPLOYED, BUT NOT CHECKED: the live check could not read a file "
               "to its end (it names the file above), so whether the site is "
               "serving what was built is not known.")

# THE COMMIT A BUILD WAS MADE FROM, PUBLISHED WITH IT (6 October 2026). The gate
# below holds the first night after a release for a person's look, and to know
# that night it has to know the code of the build production serves, which the
# site did not carry. So the night writes its own commit into site/build.json --
# a file build_all already writes, which the fingerprint does not hash -- and
# reads production's copy back where it reads production for live_fingerprint.
# Read from production rather than recorded at deploy, because production is
# what it is about: a deploy rolled back in Cloudflare, or one made from the
# laptop (whose build.json names no commit), is seen as it is. A build.json
# that cannot be read, or names no commit, is a commit not known, and the
# gate's answer to that is to wait.
BUILD_RECORD = "build.json"
BUILD_RECORD_MOST = 1 << 20     # build.json is a few KB; more is not one
COMMIT = re.compile(r"[0-9a-f]{40}")
# What live_fingerprint read of production beside the fingerprint, for the
# gate: "commit", what production's build.json names (None where it could not
# be read or names none). Emptied at the start of every read, and by judge
# before it reads, so a night never judges by an earlier night's answer.
SERVED = {}

# THE GATE (6 October 2026). Every night that passes its checks waits today for
# a person's approval in the "production" environment, and the live record
# lags by however long that takes. The design approved on 6 October 2026 lets an
# ordinary data night publish itself and keeps the look for a night that is
# one of these:
#
#   a New term run       always: the person's rule of 30 September 2026
#   a release            tonight's code is not the code of the build production
#                        serves (BUILD_RECORD): the first night after a merge to
#                        main, which is the person's one look at it. Where
#                        production's commit cannot be read, the answer is wait
#   far more changed     than a data night changes (REVIEW_ROWS_MOST)
#   a new warning        of a kind the night before did not carry
#
# Every night that builds says in its verdict, as "review": {"needed", "why"},
# whether the gate holds it and why; the night's step says it to the workflow
# as the output "review", and the run's page says it in one line. IN SHADOW
# until the workflow routes by it: the page says what the gate WOULD have done,
# and every night still waits for approval in "production" as before. Nothing
# here decides what is published, or when.
#
# How the run's page puts it, for a night whose build could go to production
# (REVIEW_LINES), for a dry run, and for a night whose build could not.
REVIEW_LINES = ("Would have published without approval.",
                "Would have waited for approval: {why}.")
REVIEW_DRY = "A dry run, so nothing was published; had it not been one, it {would}"
REVIEW_NOT_FOR = "Not for production tonight, so there was nothing to approve."
# The gate's second reason: a release. A release is a merge to main, the
# person's own act, and the first night after it is their one look at it; a
# night whose code is production's is a data night. Commit for commit: a merge
# of nothing but documents waits too, which is the safe side. Where either
# commit is not known, the night waits.
REVIEW_RELEASE = ("tonight's code (commit {tonight}) is not the code of the build production "
                  "serves (commit {served}): the first night after a release")
REVIEW_LIVE_UNKNOWN = ("the commit of the build production serves could not be read, so whether "
                       "tonight's code is a release's is not known")
REVIEW_SHA_UNKNOWN = ("tonight's own commit is not known, so whether its code is a release's is "
                      "not known")
# The third: a night that changed far more than a data night does. Measured on
# the bill lists, site/idx/<term>.json, against production's copies, which
# live_fingerprint reads already -- and not on pages: the date of the build is
# printed on every page, so every page changes every night (38,013 of the
# 54,975 files between the builds of 25 and 26 September 2026). Two measures,
# both only on a night whose code is not known to be a release's, which
# rewrites what it likes and waits anyway:
#
#   a finished term   its list differing from production's at all. A data night
#                     does not rewrite a finished term: of the nights whose
#                     every built file is on record, the three whose code was
#                     the night before's (29 and 30 September, 4 October 2026)
#                     rewrote none, and the four whose code had moved rewrote
#                     none, eight, all eighteen and all eighteen
#   the current term  more than REVIEW_ROWS_MOST of its bills' rows changed,
#                     added or gone, by bill
#
# REVIEW_ROWS_MOST, FROM THE TERM'S OWN DOCKET. The nights' what-changed
# reports, 13 September to 6 October 2026, moved 35 bills at most, but they
# are all of the interim, and three times that would have held 66 of the 355
# days of 2025-2026 that the docket gained lines on -- most session days. The
# docket itself (Docket.txt, each line by when it was entered) holds the
# session: 346 bills on its busiest day (5 February 2026), and 579 over its
# busiest three days running (21 to 23 January 2025), which is what a night
# after two failed ones would carry. A bill's row moves with its docket, so
# 600 holds no night that term had, and holds one that rewrote more than about
# a quarter of the term's 2,243 bills.
REVIEW_ROWS_MOST = 600
REVIEW_UNREAD = ("production's bill list of {terms} could not be read, so how much tonight "
                 "changed is not known")
REVIEW_FINISHED = ("the bill list of {terms} differs from production's, and a data night does "
                   "not rewrite a finished term")
REVIEW_ROWS = ("{n:,} of the {of:,} bills of {term} changed against production's, more than "
               "the {most:,} a data night changes")
REVIEW_FAILED = "the gate could not work out {what} ({kind}), so it would wait"

# Tracked files that are code. On GitHub's machine nobody edits anything, so a
# tracked code file differing from the commit means something wrote where it
# should not have, and that build does not go to production. A tracked DATA
# file the build rewrote is reported and does not stop it; the two tracked
# files the night's own fetch installs (GeneralCodes.txt, BodyStatusCodes.txt)
# are its job and are not even reported.
CODE_SUFFIXES = (".py", ".js", ".mjs", ".css", ".html", ".bat", ".cmd", ".ps1",
                 ".sh", ".toml", ".yml", ".yaml")

# ---- a night the export fails: the day's files from the database ---------------
#
# fetch_day_db.py's folder, which is dayfiles_from_db.VIEWS_DIR; and where a
# database night's files are kept, beside the archive of the website's own.
# preflight holds these to the modules they name.
DB_DAY = SCRATCH / "dbday"
FROM_DB = "from-db"
DB_SOURCE = "database"
# This many nights in a row built from the database is an error on the run's
# page: the export has come back empty that many nights running (on its one
# try, since 2 October: a night no longer asks it six times before turning to
# the database), the committee list and the other lookups are that old, and
# it is time to tell the General Court's IT office.
DB_NIGHTS_MOST = 7
# This many nights the fallback was tried and stopped by one of its own
# checks, since the installed files last moved, is an error too. The files
# tonight's are compared with are the installed ones, and a stopped night
# leaves those where they were: the check that stopped one night stops the
# next, and the one after, until the export returns or a person reads what it
# named and decides -- a ceiling that widens with the nights aside
# (stopped_next). The first such night may be the export's bad day; the
# second is a fallback that is stuck. Counted by the night's day
# (db_stopped_day), so that a second run on the day of the first is not the
# second night; and not "in a row", which a night that failed another way in
# between made untrue: the count is kept across such a night, since the
# files have not moved, and the sentences say what it counts.
DB_STOPPED_MOST = 2
# The SQL host's own hold (probe_db.HELD and HELD_ENV). Every step the night
# starts is told its full path: take_views runs its fetch in a scratch folder,
# where "archive/" would be somewhere else.
SQL_HELD = Path("archive/sql-held.json")
SQL_HELD_ENV = "GRANITE_SQL_HELD"
# What take_views says of a view it did not ask for because that hold stands.
# The night chose not to ask and the installed view stays: a warning on its
# page, and never a reason it was not clean. As first written it was one, and
# a night that is not clean exits 1, which publishes nothing: two failed
# connections in a row would have kept the next night's export, whole and
# built, off the site, and four in a row the next six nights'.
STUDY_HELD = "not taken: a hold on the General Court's database is on file"
# ... and of one it did not ask for because the database had been asked for
# the day's files earlier the same night and had not given them (2 October
# 2026). Until the export could be asked again AFTER the database, a database
# that failed ended the night's asking, and "is not asked twice" was true by
# construction. With the new order a failed query could be followed by an
# export that arrived, and take_views then asked the same host, minutes after
# it had timed out, for two more views. A warning, as the hold's is: the
# installed views stay, and the day's files are built and go out.
STUDY_NOT_AGAIN = ("not taken: the General Court's database did not give the day's files "
                   "earlier tonight, and it is not asked again the same night")
STUDY_UNASKED = (STUDY_HELD, STUDY_NOT_AGAIN)
# Why a fallback that was tried installed nothing. One of these, chosen by the
# night's own code, is all the run's page says of it: the page is public, and
# takes none of a server's own words. The detail is in the log and the verdict.
# "query" said "and nothing is asked twice in one night" until 2 October 2026,
# when the page of such a night went on to list the export asked again: it is
# the database that is not asked again, and DB_ASKED holds the night to that.
DB_WHY = {
    "held": "a hold on it is on file, so it was not asked",
    "connect": "its server could not be connected to",
    "query": "a query of it failed, so it was not asked again tonight",
    "short": "what came back from it was not whole, or could not be read",
    "guard": "what came back from it did not pass the night's checks against the installed files",
    "shrink": "the files rebuilt from it were much smaller than the copies installed",
    "error": "the night's own step for it failed",
}
# The reasons that mean the database WAS asked tonight and gave nothing the
# night could use: it is asked for nothing more that night (STUDY_NOT_AGAIN).
# Not "held": it was never asked, and the hold speaks for itself in
# take_views, as a failed connection's does once it is recorded.
DB_ASKED = ("connect", "query", "short", "error")

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
                       text=True, bufsize=1, cwd=cwd,
                       env={SQL_HELD_ENV: str(SQL_HELD.resolve())})
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

    def count_bills():
        # The bill index as the pages read it (site_read.bill_index). No site,
        # or one whose index does not hold together, counts none, so that the
        # gate names the fall rather than this stopping the night.
        try:
            return len(SR.bill_index(site) or [])
        except SR.Broken:
            return 0
    return {"bills": count_bills(),
            "legislators": count_json("legislators.json"),
            "bill_data": (sum(1 for _ in (site / "bills").glob("*/*.json"))
                          + sum(1 for _ in (site / "bills").glob("*.json"))),
            "bill_pages": sum(1 for _ in (site / "bill").rglob("*.html")),
            "feeds": sum(1 for _ in (site / "feed").rglob("*.xml")),
            "files": sum(1 for p in site.rglob("*") if p.is_file()),
            "terms": term_counts(site)}


# THE CENSUS BY TERM (5 October 2026). The bills gate counts the whole index,
# and a turn that lost 2025-2026 and gained 2027's first batch fell 6% --
# which a New term run let through as a fall it expects. So every term is
# counted from its own list, site/idx/<term>.json, and on EVERY run, the New
# term run included, a term other than the newest that has lost more than
# TERM_FALL_MOST of its bills stops the night. A little, not nothing: a
# correction that merges a duplicate or withholds a record takes one or two
# away. A baseline with no counts by term is no baseline for this gate.
TERM_FALL_MOST = 0.01
# What a New term run may let fall, of the gates above: the feeds, because the
# last term's moving bills stop being current (215 of 703 on 3 October 2026).
# Nothing else -- the design's word, and the review's of 5 October 2026: the
# sitting legislators were let fall too, so a legislators.txt cut short on
# the switch night passed every gate and was left to the approver. Organization
# Day fills the seats an election left empty (406 of 424 sat on 5 October
# 2026), so a real one does not fall past the 2% gate.
NEW_TERM_MAY_FALL = ("feeds",)


def term_counts(site):
    """{term: bills} from each term's list, site/idx/<term>.json."""
    out = {}
    for p in sorted((site / "idx").glob("*.json")) if (site / "idx").is_dir() else []:
        if re.fullmatch(r"\d{4}-\d{4}", p.stem):
            try:
                out[p.stem] = len(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                out[p.stem] = 0
    return out


def terms_fell(before, after):
    """["2025-2026 fell from 2,243 to 19", ...]: each term but the newest the
    build holds that lost more than TERM_FALL_MOST of its bills, or all."""
    was, now = before.get("terms"), after.get("terms")
    if not isinstance(was, dict) or not was or not isinstance(now, dict):
        return []
    newest = max(now) if now else ""
    out = []
    for t, n in sorted(was.items()):
        if t == newest or not isinstance(n, int) or not n:
            continue
        m = now.get(t, 0)
        if m < n * (1 - TERM_FALL_MOST):
            out.append(f"{t} fell from {n:,} to {m:,}")
    return out


def fingerprinted(meta):
    """The files the fingerprint is of, in order: meta.json, then the bill
    index it names -- each term's file and the bill requests' -- then
    home.json and legislators.json.

    THE TERM FILES, NOT index.json (5 October 2026), which was the same rows
    in one file that no page read, at 23.7 MB of the 25 MiB a file may be.
    Every term's file is in it, so a change to an archived term's bills is a
    change; and the requests file, which index.json never held."""
    return ["meta.json", *SR.bill_index_files(meta), "home.json", "legislators.json"]


def _meta_of(raw):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


def fingerprint(site):
    """Changed or not, without caring about file order or timestamps."""
    h = hashlib.sha256()
    mp = site / "meta.json"
    meta = _meta_of(mp.read_bytes()) if mp.exists() else {}
    for name in fingerprinted(meta):
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


def gated(before, after, force, new_term=False):
    """(stop, blocked, lines) for the census gates, the terms and the file
    ceiling. `force` (the laptop's --force) lets every gate's fall through
    but the ceiling's; `new_term` only NEW_TERM_MAY_FALL's."""
    lines = [f"  {'':<14}{'before':>10}{'after':>10}   change"]
    blocked, held = [], []
    for key, tol in GATES:
        b, n = before[key], after[key]
        if b and n < b * (1 - tol):
            blocked.append(f"{key} fell from {b:,} to {n:,}")
            if new_term and key not in NEW_TERM_MAY_FALL:
                held.append(blocked[-1])
        pct = f"{(n - b) / b * 100:+.1f}%" if b else "n/a"
        lines.append(f"  {key:<14}{b:>10,}{n:>10,}   {pct}")
    fell = terms_fell(before, after)
    blocked += fell
    if not isinstance(before.get("terms"), dict) or not before.get("terms"):
        lines.append(f"  {'terms':<14}{'-':>10}{len(after.get('terms') or {}):>10}   "
                     "no counts by term to compare with")
    else:
        lines.append(f"  {'terms':<14}{len(before['terms']):>10}{len(after.get('terms') or {}):>10}   "
                     + ("; ".join(fell) if fell else "no term but the newest fell"))
    ceiling = after["files"] >= FILE_CEILING
    lines.append(f"  {'files':<14}{before['files']:>10,}{after['files']:>10,}   "
                 f"ceiling {FILE_CEILING:,}")
    hard = [f"{after['files']:,} files is past the {FILE_CEILING:,} ceiling"] if ceiling else []
    if force:
        return hard, blocked, lines
    if new_term:
        return hard + held + fell, blocked, lines
    return hard + blocked, blocked, lines


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
    ap.add_argument("--new-term", action="store_true",
                    help="(--runner) the night, or the weekly job, a term turns over: the "
                         "General Court's smaller files accepted, once")
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
        if a.new_term and (a.deploy_to or a.close):
            ap.error("--new-term is for the night or the weekly job: a deploy and the "
                     "verdict are the same on every night")
        on_the_runner()
        if a.close:
            return close_verdict(a)
        if a.deploy_to:
            return runner_deploy(a)
        if a.weekly:
            return weekly(a)
    elif a.weekly or a.deploy_to or a.close or a.dry_run or a.new_term:
        ap.error("--weekly, --deploy-to, --close, --dry-run and --new-term are for "
                 "GitHub's machine, with --runner")

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
        if night and a.new_term and (a.dry_run or a.no_fetch):
            # The switch is the run that takes the smaller files and may
            # publish them, behind approval. A dry run cannot publish; and a
            # run that does not fetch takes no files, yet would let a build
            # that fell for some other reason through the census as though a
            # term had turned over. A run by hand has Dry run ticked and the
            # fetch unticked unless a person changes them, so both are said.
            say("\nSTOPPED: " + (NEW_TERM_DRY if a.dry_run else NEW_TERM_NO_FETCH))
            night.v["new_term"] = {"refused": REFUSED_DRY if a.dry_run else REFUSED_NO_FETCH}
            return 1
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
            if ok and night and a.new_term:
                # THE TERM BEING LEFT IS FROZEN FIRST (5 October 2026), before
                # anything is asked: a New term run that took the new term's
                # files over a term this disk does not hold whole would lose
                # it, and the snapshot would only refuse it after asking.
                ready, said = new_term_ready()
                night.v["new_term"]["freeze"] = said
                say(f"\n--- the term being left ---\n  {said}")
                if not ready:
                    say("\nSTOPPED: " + NEW_TERM_FREEZE)
                    night.v["new_term"]["refused"] = REFUSED_FREEZE
                    return 1
            if not ok:
                say(f"\nFETCH DEFERRED: {why}")
                if night:
                    night.v["fetch"] = f"deferred: {why}"
            else:
                # THE PAGE'S FIRST ERROR IS THE ONE KEPT (1 October 2026). Every
                # try opens the General Court's data page again and overwrites
                # what the last one recorded. On 1 October try 1 was told
                # "Error Generating LSR File : Execution Timeout Expired...",
                # the later tries' page timed out, and the verdict, reading
                # only the last try's answer, said nothing of it.
                asked, page_said, page_at = datetime.now(), "", 0
                db_day = False          # tonight's files came from the database
                db_asked = False        # the database is turned to once a night, at most
                last = EMPTY_TRIES      # the last try an empty export gets tonight
                if night:
                    # What was asked for the day's files, in the order it was
                    # asked, each with how it ended: the verdict's "tried".
                    night.v["tried"] = []
                try:
                    with refusal.hold("nightly"):
                        for tries in range(1, EMPTY_TRIES + 1):
                            asked = datetime.now()
                            rc = run(["snapshot_gencourt.py", "--dir", a.archive, "--into", "."]
                                     + (["--allow-shrink", "--allow-turn"] if a.new_term else []),
                                     "the day's bulk files"
                                     + (f", try {tries} of {last}" if tries > 1 else ""))
                            got = fetch_status(rc, a.archive, asked)
                            said = data_page(a.archive, asked)
                            if said and not page_said:
                                page_said, page_at = said, tries
                            if night:
                                night.v["tried"].append(f"the export, try {tries}: {got}")
                            if (not a.runner or not got.startswith("empty")
                                    or refusal.MARK.exists()):
                                break
                            # THE DATABASE, AS SOON AS THE EXPORT COMES BACK
                            # EMPTY (2 October 2026; DB_AFTER_TRIES says why it
                            # no longer waits for the last try), under the same
                            # lock: all seven changing files from it, or none.
                            # Never when a try arrived whole, or failed another
                            # way, and never a second time in one night.
                            if night and not db_asked and tries >= DB_AFTER_TRIES:
                                db_asked = True
                                night.v["fetch_tries"] = tries
                                db_day = from_database(a, night, tries, asked)
                                if db_day:
                                    break
                                if db_looked_wrong(night.v):
                                    # DB_LOOKED_WRONG says why this ends the
                                    # night's asking, and a hold does not.
                                    say("\n  The export is not asked again tonight: what the "
                                        "database gave looked wrong beside the installed files, "
                                        "and a later export would be installed on its own, "
                                        "coarser, checks. Nothing was installed.")
                                    night.v["tried"].append(EXPORT_NOT_AGAIN)
                                    break
                                if not a.new_term:
                                    # It could not be used: TRIES_AFTER_DB more
                                    # of the export, and not the old five.
                                    last = min(EMPTY_TRIES, tries + TRIES_AFTER_DB)
                            if tries >= last:
                                break
                            say(f"\n  {got}: the General Court's files are sometimes half "
                                f"written in the early morning. Asking again in {EMPTY_WAIT} "
                                f"minutes (try {tries + 1} of {last}).")
                            time.sleep(EMPTY_WAIT * 60)
                        if night:
                            night.v["fetch_tries"] = tries
                        # On GitHub's machine the study committees' meetings
                        # come with the day's files, under the same lock: the
                        # calendar shows them, and nothing else refreshes them.
                        if night and (rc == 0 or db_day) and not refusal.MARK.exists():
                            night.v["study_meetings"] = take_views(
                                STUDY_NIGHTLY, "the study committees' meetings, from the database",
                                shrink=NEW_TERM_SHRINK if a.new_term else SWAP_SHRINK,
                                not_again=db_asked_in_vain(night.v))
                            if a.new_term:
                                night.v["new_term"]["study views"] = "; ".join(
                                    f"{k} {r}" for k, r in night.v["study_meetings"].items())
                            # And next session's bill requests, from the site.
                            EXITS.clear()
                            if not refusal.MARK.exists():
                                night.v["lsrs"] = take_lsrs()
                            # And the calendars and journals the General
                            # Court lists, from its two index pages.
                            if not refusal.MARK.exists():
                                night.v["documents"] = take_documents(night.v)
                except SystemExit as e:
                    rc = e.code if isinstance(e.code, int) else 3
                    say(f"  the lock was taken by someone else first (exit {rc})")
                installed = rc == 0 or db_day
                if night:
                    # The truth about the export, whatever the database did;
                    # and, in one word, where the installed files came from.
                    night.v["fetch"] = fetch_status(rc, a.archive, asked)
                    night.v["files_from"] = ("export" if rc == 0 else
                                             DB_SOURCE if db_day else "none")
                    # A database night is counted where its files went in
                    # (from_database), so that a night stopped after that
                    # still counts; here only the export starts it again.
                    night.v["db_nights"] = 0 if rc == 0 else night.v["db_nights"]
                    # ... and the nights the fallback's own checks stopped it
                    # since the installed files last moved: one more for a
                    # night they stop, which is a night the export is not
                    # asked again; none after a night either source installs
                    # (from_database says that of its own files where they go
                    # in); and as it was after a night that failed another
                    # way.
                    # Counted by night and not by run: a second run on a
                    # day already counted -- a dry run, a run again by hand
                    # -- read "night 2" on the day of the first stop, and
                    # raised the error.
                    stopped = (night.v.get("day_files") or {}).get("why_code") == "guard"
                    again = night.v.get("db_stopped_day") == night.day
                    if rc == 0 or db_day:
                        night.v["db_stopped"] = 0
                        night.v.pop("db_stopped_day", None)
                    elif stopped:
                        night.v["db_stopped"] += 0 if again else 1
                        night.v["db_stopped_day"] = night.day
                    if a.new_term and rc == 0:
                        night.v["new_term"]["files"] = shrink_accepted(a.archive, asked)
                    if rc == 0 and released_tonight(a.archive, asked):
                        night.v["released"] = released_tonight(a.archive, asked)
                    _rec = load_json(snapshot_day(a.archive, asked) / INSTALL_RECORD)
                    if rc == 0 and isinstance(_rec, dict) and isinstance(_rec.get("empty"), dict):
                        # The roll-call files, empty and taken as no roll
                        # call yet (snapshot_gencourt.empty_is_data).
                        night.v["empty_rollcalls"] = _rec["empty"]
                    if page_said:
                        night.v["data_page_said"] = page_said
                        night.v["data_page_try"] = page_at
                    if rc == 0:
                        # The files went in: whatever an unpublished New term
                        # run had accepted is no longer the question.
                        night.v.pop("new_term_unpublished", None)
                if rc == 2:
                    say("\nREFUSED while fetching. Recorded; every fetch now waits "
                        "for a person.")
                elif rc != 0 and db_day:
                    say(f"\nThe export did not complete (exit {rc}). The day's files were "
                        "installed from the General Court's database instead, and the "
                        "night goes on with them.")
                elif rc != 0:
                    say(f"\nThe fetch did not complete (exit {rc}); nothing was "
                        "installed, so tonight's build would be yesterday's.")

        if installed:
            rc = run(["gc_changes.py", "--archive", a.archive,
                      "--out", f"reports/gc-changes-{day}.md"]
                     + (["--db-night", day] if db_day else []),
                     "what the General Court changed")
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
            if night and a.new_term:
                # On this machine site/ starts empty, so build_feeds finds
                # nothing stale and the census gates are what see feeds fall;
                # the prune is allowed for a build wherever site/ is kept.
                night.v["new_term"]["feeds"] = "the prune allowed, for this build"
            if run(["build_all.py", "--local"] + (["--no-captions"] if a.runner else [])
                   + (["--allow-prune"] if a.new_term else []),
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
            # A finished term's rows in tonight's files, left out of the build
            # (build_data.LEFT_OUT), go on the run's page: the count reached
            # build_data's log and nothing else (the review of 5 October 2026).
            left = load_json(LEFT_OUT)
            if night and isinstance(left, dict) and left.get("rows"):
                night.v["left_out"] = left
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
                stop, blocked, lines = gated(before, after, a.force, a.new_term)
            say("\n--- gates ---")
            for ln in lines:
                say(ln)
            if stop:
                say("\nNOT PUBLISHABLE: " + "; ".join(stop))
            elif blocked and a.new_term:
                say("\n  the census objected, and this is the New term run: the fall is let "
                    "through, and tonight's counts become the baseline once this build is "
                    "published: " + "; ".join(blocked))
            elif blocked:
                say("\n  the census objected, --force given: " + "; ".join(blocked))
            changed = fingerprint(site) != before_fp
            say(f"\n  the site {'changed' if changed else 'did not change'}")

            if night:
                night.judge(site, before, after, stop, changed,
                            accepted=blocked if a.new_term and not stop else [])
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
    rc = run(["check_live.py", "--gate", "--base", a.base, "--site", a.site],
             "what the live site is now serving")
    if rc == LIVE_NOT_CHECKED:
        say(f"\n{LIVE_UNREAD}")
        return False
    if rc != 0:
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


def gh_annotate(level, title, message):
    """A note at the top of the run's page on GitHub, when there is one: the
    first thing a person sees after "View workflow run" in GitHub's email.
    Public, like the summary."""
    if github("GITHUB_ACTIONS") != "true":
        return

    def esc(x, prop=False):
        x = str(x).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        return x.replace(":", "%3A").replace(",", "%2C") if prop else x
    print(f"::{level} title={esc(title, True)}::{esc(message)}", flush=True)


# WHY A NIGHT STOPPED, IN ONE SENTENCE (27 September 2026). GitHub's email for
# the first scheduled night listed two notes, both "Process completed with exit
# code 1", and the person could not tell from it why the night had failed: the
# day's files had come back empty. The verdict step now puts one sentence at
# the top of the run's page. The page is public, so the sentence is one of
# these, chosen by the verdict's own fields, and never a step's own words.
STEP_WHY = {
    "state-down": "the state files could not be brought down from the private bucket",
    "kit-down": "the night's data could not be brought down from the private bucket",
    "livestreams": "the livestream step failed",
    "night": "the night's own step failed",
    "preview": "the preview could not be deployed",
    "pack": "the site could not be sent to the private bucket for the publish job",
    "kit-up": "the night's data could not be sent back to the private bucket",
}

# THE NEW TERM, ON THE RUN'S PAGE (30 September 2026). The first is what an
# ordinary night says when the snapshot refused files much smaller than the
# copies installed: the one night that is right is the night a term turns
# over, and the box for it is on the nightly run by hand. The second is what
# the New term run says when it was also ticked as a dry run, which it will not
# be. preflight holds both to the box's name in nightly.yml.
NEW_TERM_BOX = "New term"
# The gate's first reason (THE GATE, above): a New term run waits for approval
# whatever else is true of it, because the person decided on 30 September 2026
# that the switch to a new term keeps their approval after ordinary nights
# stop needing it (the note above the box in nightly.yml).
REVIEW_NEW_TERM = (f"a {NEW_TERM_BOX} run, and the switch to a new term always waits for "
                   "approval")
# "OR A NEW SESSION YEAR" (5 October 2026): a term's second January shrinks
# LSRs.txt to the new year's few requests and meets the same rule, and the
# same box answers it. A new TERM is no longer seen by size at all: the
# snapshot reads the files' years (NEW_TERM_TURN, below).
NEW_TERM_HINT = (f"The General Court's files are much smaller: a new term, or a new session "
                 f"year? Run the nightly by hand with {NEW_TERM_BOX} ticked.")
# What an ordinary night says when the snapshot refused files that name a
# newer term than the installed ones (snapshot_gencourt.judge, "turned"),
# whatever their size. The person decided on 5 October 2026 that the switch
# is the first night the files show the new term, even if Organization Day
# brings only resolutions, and that it keeps their approval.
NEW_TERM_TURN = (f"The General Court's files show a new term, which only a run by hand with "
                 f"{NEW_TERM_BOX} ticked may take, once the term being left is frozen "
                 "(freeze_term.py --session, sent with seed-kit).")
# ... and when tonight's roster is another House's and the installed term's own
# roster is not frozen (snapshot_gencourt.roster_moved, the review of 5
# October 2026): Organization Day can seat the next House before the files
# show the next term, and the term's members are named from its frozen
# roster. No box takes it; a freeze lets the next night take it.
NEW_TERM_ROSTER = ("The General Court's roster is a new House, and the term the site holds has "
                   "no frozen roster of its own to name its members by, so nothing was "
                   "installed. Freeze it (freeze_term.py --session, sent with seed-kit, while "
                   "the installed roster is still the term's) and the next night takes the files.")
# The other boxes that run needs, by the words each one starts with on GitHub's
# "Run workflow" form: a run by hand has Dry run ticked and the fetch unticked
# unless a person changes them, and the hint alone named neither. preflight
# holds each to its box in the workflow.
DRY_BOX = "Dry run"
FETCH_BOX = "Take the day's data"
WEEKLY_FETCH_BOX = "Take the rosters and study committees"
NEW_TERM_HOW = (f'That run also needs "{FETCH_BOX}" ticked and {DRY_BOX} unticked, and what it '
                "builds waits for approval: nothing it accepts is kept until that build is "
                "published.")
NEW_TERM_AGAIN = (f'Run the nightly by hand again with {NEW_TERM_BOX} and "{FETCH_BOX}" ticked '
                  f"and {DRY_BOX} unticked.")
NEW_TERM_DRY = (f"{NEW_TERM_BOX} was ticked with {DRY_BOX}, so nothing was fetched or built: the "
                "switch to a new term is a run that may publish, and it waits for approval. "
                + NEW_TERM_AGAIN)
NEW_TERM_NO_FETCH = (f'{NEW_TERM_BOX} was ticked without "{FETCH_BOX}", so nothing was fetched or '
                     "built: the switch to a new term is the run that takes the General Court's "
                     "smaller files. " + NEW_TERM_AGAIN)
# What a New term run's verdict records when its other boxes stopped it.
REFUSED_DRY = "ticked with Dry run"
REFUSED_NO_FETCH = "ticked without the fetch"
# ... and when the term it would leave is not frozen as installed: it stops
# before any request (new_term_ready).
REFUSED_FREEZE = "stopped before any request: the term it would leave is not frozen as installed"
NEW_TERM_FREEZE = (f"{NEW_TERM_BOX} was ticked, and the term the installed files hold is not "
                   "frozen as they are, so nothing was asked for: installing a new term would "
                   "lose what of the old one is not frozen. Freeze it (freeze_term.py --session, "
                   f"sent with seed-kit) and run the nightly by hand with {NEW_TERM_BOX} ticked "
                   "again.")
# The weekly job's own two sentences: it has no Dry run box and publishes nothing.
WEEKLY_NEW_TERM_HINT = ("The General Court's committee lists are much smaller: a new term? Run "
                        f'the weekly by hand with {NEW_TERM_BOX} and "{WEEKLY_FETCH_BOX}" ticked.')
WEEKLY_NEW_TERM_NO_FETCH = (f'{NEW_TERM_BOX} was ticked without "{WEEKLY_FETCH_BOX}", so nothing '
                            "was taken. Run the weekly by hand again with both ticked.")

# What take_views and take_json say of a result kept out for being much smaller
# than the copy installed -- and of nothing else they keep out.
KEPT_SMALLER = re.compile(r"^not taken: [\d,]+(?: rows)? against [\d,]+ installed$")


def kept_smaller(results):
    """Whether any of these fetch results was kept out for being much smaller."""
    return any(KEPT_SMALLER.match(str(r)) for r in (results or {}).values())


def plain_why(v, weekly=False):
    """The one sentence a run's page leads with when it was not clean."""
    failed = [k for k, r in (v.get("steps") or {}).items()
              if r not in ("success", "skipped", "")]
    first = next((k for k in failed if k in STEP_WHY and k != "night"), "")
    step = STEP_WHY.get(first, "")
    new_term = v.get("new_term") if isinstance(v.get("new_term"), dict) else {}
    if weekly:
        if new_term.get("refused"):
            return WEEKLY_NEW_TERM_NO_FETCH
        # The members who have left are a merge: one that came back smaller
        # is a failed fetch in any week, and says nothing about a term.
        if not step and kept_smaller({k: r for k, r in (v.get("results") or {}).items()
                                      if k != "former_members"}):
            return (WEEKLY_NEW_TERM_HINT + " If no term has begun, a fetch came back cut "
                    "short: the lists installed were kept, and next week asks again.")
        return ("The weekly job did not finish cleanly"
                + (f": {step}." if step else "; its summary lists what fell short."))
    fetch = str(v.get("fetch") or "")
    # A night whose files came from the database installed them: the export's
    # failure is its warning, not why it was not clean.
    if from_db(v) and fetch.startswith("empty"):
        fetch = "installed"
    if new_term.get("refused"):
        why = {REFUSED_NO_FETCH: NEW_TERM_NO_FETCH,
               REFUSED_FREEZE: NEW_TERM_FREEZE}.get(new_term["refused"], NEW_TERM_DRY)
    elif v.get("preflight") == "failed":
        why = "The code checks failed, so nothing was fetched or built."
    elif fetch == "refused":
        why = ("The General Court refused a request. Nothing more was asked, and "
               "every fetch waits until a person clears the refusal.")
    elif fetch.startswith("empty"):
        # Some or all: at 02:04 on 20 September two of the fourteen came back
        # 3 bytes long, at 06:33 on 27 September thirteen.
        m = re.search(r"(\d+) of (\d+)", fetch)
        some = m and m.group(1) != m.group(2)
        tries = int(v.get("fetch_tries") or 1)
        why = ((f"{m.group(1)} of the General Court's {m.group(2)} daily files"
                if some else "The General Court's daily files")
               + " came back empty"
               + (f" on each of {tries} tries, {EMPTY_WAIT} minutes apart" if tries > 1 else "")
               + ", so nothing was installed or built."
               + (f' Their data page said{page_try(v)}: "{v["data_page_said"]}"'
                  if v.get("data_page_said") else "")
               + db_tried(v))
    elif fetch.startswith("turned"):
        # The files name a newer term than the installed ones: never taken on
        # a night nobody started, whatever their size (5 October 2026).
        why = (NEW_TERM_TURN + " " + NEW_TERM_HOW + unpublished_note(v)
               + " The site still serves the last term's files as they were installed.")
    elif fetch.startswith("roster"):
        # Organization Day's roster before the term's own is frozen (the
        # review of 5 October 2026): no box answers it, a freeze does.
        why = (NEW_TERM_ROSTER + unpublished_note(v)
               + " The site still serves the files as they were installed.")
    elif fetch.startswith("smaller"):
        # The shrink rule, which is right on every night but the one a term
        # turns over -- and that night is a person's to call.
        why = (NEW_TERM_HINT + " " + NEW_TERM_HOW + unpublished_note(v)
               + " If no term has begun, a file came back cut short: "
               "nothing was installed or built, and the next night asks again.")
    elif fetch.startswith("deferred"):
        why = ("The day's files were not asked for: a refusal on file or another "
               "fetch was in the way.")
    elif fetch.startswith("did not complete"):
        why = ("Not all of the General Court's daily files arrived, so nothing was "
               "installed or built." + db_tried(v))
    elif v.get("build") and v["build"] != "passed":
        why = "The build failed."
    elif v.get("check_site") and v["check_site"] != "passed":
        why = "The built site failed its checks."
    elif kept_smaller(v.get("study_meetings")):
        why = ("The study committees' meetings came back from the General Court's database "
               "much smaller, and were not taken. " + NEW_TERM_HINT + " " + NEW_TERM_HOW)
    elif step:
        # The state and the kit come down before the night; the rest after it.
        why = (f"The night could not start: {step}." if first in ("state-down", "kit-down")
               else f"The night ran, but {step}.")
    elif str(v.get("gates") or "").startswith("blocked:") and \
            re.search(r"\d{4}-\d{4} fell from", v["gates"]):
        # A term other than the newest has lost bills (terms_fell): never a
        # new term's doing, so no box answers it.
        why = ("The site was built, but a finished term has fewer bills than the last good "
               "night's build had, and no run may publish that, New term or not: "
               + "; ".join(re.findall(r"\d{4}-\d{4} fell from [\d,]+ to [\d,]+", v["gates"]))
               + ". The term's frozen inputs and its build are the place to look.")
    elif str(v.get("gates") or "").startswith("blocked:") and "fell from" in v["gates"]:
        # The census gates: a build that counts far less than the last good
        # night's. Wrong on the one night a term turns over, as the shrink
        # rule is, and the same box answers it.
        why = ("The site was built, but it counts far less than the last good night's did. "
               + NEW_TERM_HINT + " " + NEW_TERM_HOW + unpublished_note(v)
               + " If no term has begun, something upstream failed, and the night's checks "
               "kept the build from production.")
    elif v.get("blocking"):
        why = "The site was built, but the night's checks kept it from production."
    elif study_missed(v):
        # Asked for, and not taken. This night's page used to say it had
        # "stopped before it recorded what it did", of a night that had
        # installed the day's files and built the site.
        why = ("The day's files were installed and the site was built, but the study "
               "committees' meetings could not be taken from the General Court's database.")
    else:
        why = "The night stopped before it recorded what it did."
    return why + " Nothing was published."


def from_db(v):
    """Whether this verdict's day files were installed from the database."""
    return isinstance(v.get("day_files"), dict) and v["day_files"].get("source") == DB_SOURCE


def study_held(v):
    """Whether the night left the study committees' views unasked because a
    hold on the SQL host stood (take_views)."""
    got = v.get("study_meetings")
    return isinstance(got, dict) and any(r == STUDY_HELD for r in got.values())


def study_missed(v):
    """Whether a study committees' view was asked for and not taken."""
    got = v.get("study_meetings")
    return isinstance(got, dict) and any(
        r not in STUDY_UNASKED and not str(r).startswith("installed") for r in got.values())


def study_not_again(v):
    """Whether the night left the study committees' views unasked because the
    database had not given the day's files earlier that night (take_views)."""
    got = v.get("study_meetings")
    return isinstance(got, dict) and any(r == STUDY_NOT_AGAIN for r in got.values())


def sql_hold_said():
    """The hold on the SQL host, in probe_db's own sentence: when, how many
    times in a row, until when. Its words are this project's and none of the
    server's, so it is fit for the run's page."""
    import probe_db
    d = probe_db.hold_standing() or probe_db.hold_record()
    if isinstance(d, dict) and d.get("held"):
        return probe_db.hold_sentence(d)
    return "a hold on the General Court's database was on file"


def db_nights_of(v):
    """How many nights in a row the day's files had come from the database, by
    an earlier night's verdict; 0 when it says nothing of it."""
    if not isinstance(v, dict) or v.get("kind") != "nightly":
        return 0
    try:
        return max(0, int(v.get("db_nights") or 0))
    except (TypeError, ValueError):
        return 0


def db_stopped_of(v):
    """How many nights the fallback had been stopped by its own checks since
    the installed files last moved, by an earlier night's verdict; 0 when it
    says nothing of it."""
    if not isinstance(v, dict) or v.get("kind") != "nightly":
        return 0
    try:
        return max(0, int(v.get("db_stopped") or 0))
    except (TypeError, ValueError):
        return 0


def db_stopped_day_of(v):
    """The day of the last night counted in db_stopped_of(v), or ""."""
    if not isinstance(v, dict) or v.get("kind") != "nightly":
        return ""
    return str(v.get("db_stopped_day") or "")


def stops_wider_of(df):
    """(how many checks stopped a night, how many of them on a ceiling that is
    wider the older the installed files are), from a verdict's day_files:
    dayfiles_from_db.judge()'s "stops" and "wider"."""
    n = len(df["stops"]) if isinstance(df.get("stops"), list) else 0
    try:
        return n, max(0, min(n, int(df.get("stops_wider") or 0)))
    except (TypeError, ValueError):
        return n, 0


# What a stopped night's page, and the error of the second such night, say of
# the nights to come. It was one sentence: "the same check stops the fallback
# every night until the export returns or a person decides". That is true of
# a check on what the installed files hold, which do not move. It is false of
# a ceiling on a night's work, which dayfiles_from_db.py widens with every
# night the installed files are behind (SPAN, through nights_since): 1,631
# new docket rows over two days stopped a night whose installed files were
# two nights old, and the same views were installed the night after, by a
# page that had said they could not be.
STOPPED_UNTIL = ("the same check stops the fallback every night until the export returns or a "
                 "person decides")
STOPPED_WIDER = ("what stopped it is a ceiling on a night's work, which is wider the more nights "
                 "old those files are: a later night may let the same files by with nobody "
                 "deciding, and its page will say so")


def stopped_next(df):
    """What a night its checks stopped says of the nights after it, by which
    kind of check stopped it (stops_wider_of)."""
    n, wider = stops_wider_of(df)
    if n and wider == n:
        return "and " + STOPPED_WIDER
    if wider:
        return (f"so {STOPPED_UNTIL} -- {wider} of the {n} aside, a ceiling on a night's work "
                "that is wider the more nights old those files are")
    return "so " + STOPPED_UNTIL


def db_tried(v):
    """" The night then turned to the General Court's database, and ..." for a
    night the database was turned to and installed nothing, or "": after which
    try of the export (since 2 October 2026 the first, and the export may have
    been asked again afterwards), what the database did (DB_WHY), and, when
    what it gave looked wrong, that the export was not asked again. A night
    its checks stopped says more: how many did and where they are named,
    before that sentence; and after it that the site is as it was, and what
    the next night will do -- the same check stops it, or, where what stopped
    it is a ceiling that widens, may not (stopped_next) -- and none of what
    they named, which is the General Court's words. Sentences of this file's
    own, fit for the public run page."""
    df = v.get("day_files") if isinstance(v.get("day_files"), dict) else {}
    code = str(df.get("why_code") or "")
    why = DB_WHY.get(code)
    if not why or df.get("source") == DB_SOURCE:
        return ""
    tries = int(v.get("fetch_tries") or 1)
    after = int(df.get("after_try") or tries)
    when = (" The night then turned to" if after >= tries else
            " After the first empty try the night turned to" if after == 1 else
            f" After {after} empty tries the night turned to")
    said = f"{when} the General Court's database, and {why}."
    if code == "guard":
        n = stops_wider_of(df)[0]
        said += ((f" {n} checks stopped it, each" if n > 1 else " One check stopped it,")
                 + " named in the night's verdict (day_files, stops) and in its log.")
    if db_looked_wrong(v):
        said += (" The export was not asked again tonight, so that what looked wrong by one "
                 "route could not be installed by the other.")
    if code == "guard":
        # "Until the export returns" is a later night's export: tonight's is
        # not asked again, and every night asks it before the database.
        row = db_stopped_of(v)
        said += (" The site still serves the last build published. The files tonight's were "
                 f"compared with have not moved, {stopped_next(df)}."
                 + (f" Its checks have now stopped the fallback on {row} nights since those "
                    "files last moved." if row > 1 else ""))
    return said


def page_try(v):
    """", on try 1 of 6", for the data page's words on a night that asked more
    than once: the page is asked again on every try, and the first error it
    reported is the one kept."""
    tries, at = int(v.get("fetch_tries") or 1), int(v.get("data_page_try") or 0)
    return f", on try {at} of {tries}" if tries > 1 and at else ""


def unpublished_note(v):
    """" The New term run of <day> was not published, ..." when the verdict
    carries one (unpublished_new_term), or "". The run's page is public: the
    day is one of this project's own, and is checked to be a date."""
    was = v.get("new_term_unpublished") if isinstance(v.get("new_term_unpublished"), dict) else {}
    day = str(was.get("day") or "")
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", day):
        return ""
    return (f" The {NEW_TERM_BOX} run of {day} was not published, so nothing it accepted "
            "was kept.")


def unpublished_new_term(prev, census):
    """{"day", "run_id"} of a New term run that built the switch and was never
    published, or None: from the verdict of the night before (which carries an
    earlier one forward) and the census, which names the run whose counts it
    holds -- and a New term run's are written there only by its publish."""
    if not isinstance(prev, dict):
        return None
    was = prev.get("new_term_unpublished")
    was = was if isinstance(was, dict) else None
    if (prev.get("asked") or {}).get("new_term") and prev.get("built"):
        was = {"day": str(prev.get("day") or ""), "run_id": str(prev.get("run_id") or "")}
    if not was:
        return None
    c = census if isinstance(census, dict) else {}
    if c.get("new_term") and was.get("run_id") and str(c.get("run_id") or "") == was["run_id"]:
        return None
    return was


# THE DAY'S FILES ARE SOMETIMES HALF WRITTEN IN THE EARLY MORNING (28 September
# 2026). The first two scheduled nights on GitHub failed on them: at 06:33 UTC
# on the 27th all thirteen under dynamicdatadump/ came back 3 bytes long, and
# at 08:42 UTC on the 28th eight of them, in no order a rewrite in progress
# would leave. The laptop's snapshots had met it once, two files at 02:04 EDT on
# 20 September, and got whole files at 02:32 and 03:45 on other nights and at
# every run after 7 a.m. So no hour is safe on the evidence, and moving the
# schedule from 06:17 to 08:17 UTC, on one night's evidence, did not fix it.
# The night asks again instead: a snapshot that comes back with empty files
# and nothing else wrong is run again, whole, every EMPTY_WAIT minutes, up to
# EMPTY_TRIES times -- at most 84 requests over two and a half hours, each
# try one complete pass, so the files installed are still all from one moment.
# Since 2 October 2026 that wait is no longer the first answer to an empty
# export, and a scheduled night makes one such wait at most: DB_AFTER_TRIES
# and TRIES_AFTER_DB, below. Only the New term run still asks all six times.
EMPTY_TRIES = 6
EMPTY_WAIT = 30         # minutes

# THE DATABASE FIRST, AND NO LONG WAIT AFTER IT EITHER (2 October 2026).
# How many times the export is asked before an empty one sends the night to
# the database (from_database): once. As first written, on 1 October, it was
# EMPTY_TRIES: the database was asked only when the sixth try was empty, two
# and a half hours in. But on 27 and 28 September and 1 October the export
# came back empty on every try those nights made, and the person's reading
# of them is that asking again "tends to not work even if you try half an
# hour apart". On 2 October they decided, in their words: "I don't think
# retrying the export being empty is worth doing 5 times", "if the backup
# method works to fill in all the same information as the export, we should
# use that much quicker", and the system is not to "unnecessarily wait for
# 2.5 hours every time". So an export that is empty with nothing else wrong
# goes to the database at once, under the same lock and on every condition
# from_database() keeps. Putting EMPTY_TRIES here is the night of 1 October
# again, and preflight holds this to 1.
#
# TRIES_AFTER_DB is what is left for a night the database could not be used
# -- a hold on file, a connection or a query that fails, a view cut short,
# the night's own step failing, no installed files: how many MORE times the
# export is asked, EMPTY_WAIT minutes apart. The first version of this order
# kept all five, so every night that host failed or stood held (probe_db's
# hold is 20 to 164 hours) was the night of 1 October unchanged: 150 minutes
# and five more passes at the web server, for tries the person had just said
# were not worth making. They did not say what an unusable database should
# cost, so ONE is this file's reading and not their word, and a hedge rather
# than a finding: a file caught half written may be whole half an hour on,
# and a night with neither source loses half an hour finding out. 0 ends
# such a night at once. Whatever it is, the database is not asked a second
# time, and a try that arrives whole is installed.
#
# A New term run is the one night that still asks EMPTY_TRIES times: it never
# asks the database, a person started it, and a new term's files come from
# the export or from nowhere.
#
# THE EXPORT IS STILL ASKED FIRST, every night, whatever this says: 0 is 1.
# The person also said that if the export stays this unreliable all year "we
# may end up just making the backup method the primary update method". That
# is not this setting and is not built. The database rebuilds seven of the
# fourteen files; Members.txt, the six lookups, the page's own "Error
# Generating" and the archive's history of the website's files come only
# from asking the website; a new session year and a new term reach the
# installed files only through an export; and from_database()'s guards
# compare with the installed files, which after a run of database nights are
# the database's own. A night that never asked the export would need an
# answer to each. It is a person's decision, and a piece of work of its own.
DB_AFTER_TRIES = 1
TRIES_AFTER_DB = 1

# WHEN THE DATABASE'S FILES LOOKED WRONG, THE EXPORT IS NOT ASKED AGAIN THAT
# NIGHT (2 October 2026). These two of DB_WHY's reasons are the ones where the
# database answered whole and what it gave was refused: a guard stopped
# (dayfiles_from_db.judge), or the rebuilt files were much smaller than the
# copies installed. Every other reason is the database not being reachable,
# or not answering whole, and says nothing about the record, so the export is
# tried again. These two say the record itself may be wrong tonight -- a term
# turning over, the General Court part-way through a change of its own -- and
# the export is written from the same record. A later try that arrived whole
# would be installed on the export's own checks, which are coarser: it must
# not be empty and not much smaller, where the guards count a single bill
# missing from the docket. So nothing is installed, the night is not clean,
# its page says what the database's files failed on, and a person reads that
# before the next night asks the export again. It costs a day when the guard
# was wrong and the export would have been right; the other mistake would
# publish what the night's own checks had just refused.
#
# WHAT IS NOT "LOOKED WRONG", now that the guards read what a row says and
# name what they let by (dayfiles_from_db.judge's "stops" and "told"). Only a
# stop is: one check that fires, on any of the seven files, and the night is
# "guard". Rows counted under a ceiling and named ("told") are a night that
# installs, with a warning that says how many: the checks passed. And "short"
# stays with the reasons the database could not be used, though it now also
# means a view that could not be read -- written in another encoding, begun
# with a byte-order mark, a line not as wide as the view: the rebuild stopped
# before any guard saw a row, so nothing has been said of the record, and it
# is how the view travelled that failed. The export is asked once more.
DB_LOOKED_WRONG = ("guard", "shrink")
# The line that ends such a night's "tried".
EXPORT_NOT_AGAIN = ("the export: not asked again tonight, because what the database gave "
                    "looked wrong beside the installed files")


def db_looked_wrong(v):
    """Whether the database was asked tonight and what it gave was refused
    (DB_LOOKED_WRONG), rather than not reached or not whole."""
    df = v.get("day_files") if isinstance(v.get("day_files"), dict) else {}
    return df.get("source") != DB_SOURCE and df.get("why_code") in DB_LOOKED_WRONG


def db_asked_in_vain(v):
    """Whether the database was asked for the day's files tonight and gave
    nothing the night could use (DB_ASKED): it is asked for nothing more."""
    df = v.get("day_files") if isinstance(v.get("day_files"), dict) else {}
    return df.get("source") != DB_SOURCE and df.get("why_code") in DB_ASKED


def on_tries(n):
    """" on 6 tries", or "" for the one try an empty export now gets before
    the database is asked."""
    return f" on {n} tries" if n > 1 else ""


def tried_lines(v):
    """The run's page, on a night more than one thing was asked for the day's
    files: each, in the order it was asked, with how it ended (the verdict's
    "tried"). Every line is this file's own words."""
    tried = [str(t) for t in (v.get("tried") or [])]
    if len(tried) < 2:
        return []
    return (["- what was asked for the day's files, in order:"]
            + [f"  {i}. {t}" for i, t in enumerate(tried, 1)])


def page_quote(said):
    """The General Court's own words about a failed rebuild, fit for the public
    run page: only a message that starts "Error Generating", only letters,
    digits and ordinary punctuation, and only its first sentence."""
    s = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 .,:;'()/-]", " ", said or "")).strip()
    m = re.match(r"(Error Generating .{1,120}?\.)(?:\s|$)", s)
    return m.group(1) if m else ""


def snapshot_day(archive, since=None):
    """The folder a snapshot wrote in. snapshot_gencourt.py names it for the
    day it STARTED, and this reads it when it has finished: a run started
    before midnight and read after it used to be looked for under the new
    day, and "left no record". since is the moment just before the snapshot
    was started; the folder is that day's, or the next day's if midnight fell
    in between, whichever holds a manifest written since. Without since, today's."""
    root = Path(archive) / "snapshots"
    if since is None:
        return root / f"{datetime.now():%Y-%m-%d}"
    from datetime import timedelta
    for d in (since, since + timedelta(days=1)):
        man = root / f"{d:%Y-%m-%d}" / "manifest.json"
        try:
            if man.stat().st_mtime >= since.timestamp() - 2:
                return man.parent
        except OSError:
            continue
    return root / f"{since:%Y-%m-%d}"


def data_page(archive, since=None):
    """What the snapshot says the Dynamic Data Files page reported about its
    rebuild, as page_quote() gives it, or "" when it reported nothing wrong.
    With since, only a page asked since then: an earlier run's page.json, which
    comes down with the kit, does not speak for this one."""
    f = snapshot_day(archive, since) / "page.json"
    try:
        if since is not None and f.stat().st_mtime < since.timestamp() - 2:
            return ""
    except OSError:
        return ""
    page = load_json(f)
    return page_quote(page.get("said")) if isinstance(page, dict) and page.get("status") == "error" else ""


def shrink_sizes(small):
    """"Docket.txt 900 bytes against 90,000 (-99%)" for each file the snapshot
    recorded as much smaller: the run's page gave the names alone, and a
    person approving a New term run could not tell a new term's Docket from a
    file cut short -- the General Court's files are sometimes half written in
    the early morning."""
    out = []
    for x in small or []:
        if not isinstance(x, dict):
            continue
        now, was = x.get("bytes"), x.get("installed_bytes")
        if isinstance(now, int) and isinstance(was, int) and was:
            out.append(f"{x.get('name')} {now:,} bytes against {was:,} ({(now - was) / was:+.0%})")
        else:
            out.append(str(x.get("name")))
    return out


def not_empty_file(err):
    """Whether a snapshot's "not a data file (N bytes)" is of a body too big
    to be an empty file (EMPTY_BYTES): a page of some kind. One that gives no
    size is not known to be empty either."""
    m = re.search(r"not a data file \(([\d,]+) bytes\)", str(err))
    return not m or int(m.group(1).replace(",", "")) >= EMPTY_BYTES


def fetch_status(rc, archive, since=None):
    """The day's files as the verdict records them. A failed snapshot is told
    apart by its own manifest: the first scheduled night, 27 September 2026,
    met the General Court's daily files 3 bytes long, and its verdict said only
    "did not complete (exit 1)".

    Every file arriving and none installed is the shrink rule: its record,
    snapshots/<day>/install.json, names the files much smaller than the copies
    installed, and the verdict says "smaller" -- a new term, or a file cut
    short -- rather than "did not complete"."""
    if rc in (0, 2):
        return {0: "installed", 2: "refused"}[rc]
    day = snapshot_day(archive, since)
    man = load_json(day / "manifest.json")
    errs = [x["error"] for x in (man.values() if isinstance(man, dict) else [])
            if isinstance(x, dict) and x.get("error")]
    if errs and all("not a data file" in e for e in errs):
        # EMPTY IS A FILE WITH NOTHING IN IT, AND NOT A WEB PAGE (2 October
        # 2026). The snapshot says "not a data file" of two things: a body
        # under its MIN_BYTES, which is the 3-byte file of the failed nights,
        # and a body of any size that opens as HTML. "empty" is what sends
        # the night to the database and then on to the bill requests and the
        # calendar list; a page where a file should be is not known to be
        # that, and may be a refusal in words refusal.py does not know yet.
        # So it is "did not complete": nothing more is asked, by any door.
        pages = [e for e in errs if not_empty_file(e)]
        if pages:
            return (f"did not complete (exit {rc}): {len(pages)} of {len(man)} files came "
                    "back as something that is neither data nor an empty file")
        return f"empty: {len(errs)} of {len(man)} files came back with no data in them"
    rec = load_json(day / INSTALL_RECORD)
    # A NEW TERM, BY ITS YEARS (5 October 2026): before the size, because a
    # turn need not shrink anything, and one that does is still a turn.
    turned = rec.get("turned") if isinstance(rec, dict) and not rec.get("installed") else None
    if isinstance(turned, dict) and turned.get("to"):
        return (f"turned: {', '.join(turned.get('files') or []) or 'the files'} name "
                f"{turned['to']}, and the installed files {turned.get('from') or '?'}, so none "
                "was installed"
                + (": the term they would leave is not frozen as installed"
                   if rec.get("refused") == "freeze" else ""))
    # A NEW ROSTER BEFORE THE TERM'S OWN IS FROZEN (the review of 5 October
    # 2026; snapshot_gencourt.roster_moved): nothing installed, whatever else
    # tonight's files hold.
    roster = rec.get("roster") if isinstance(rec, dict) and not rec.get("installed") else None
    if isinstance(roster, dict) and rec.get("refused") == "roster":
        return (f"roster: legislators.txt is another roster, {roster.get('moved', '?')} of the "
                f"{roster.get('installed', '?')} members installed differ, and "
                f"{roster.get('term') or 'the term'}'s own roster is not frozen, so none was "
                "installed")
    small = rec.get("shrunk") if isinstance(rec, dict) and not rec.get("installed") else None
    if small and isinstance(small, list):
        # Not a file whose installed copy was a finished term's frozen one:
        # that one was let through (snapshot_gencourt.frozen_copy).
        freed = {x.get("name") for x in (rec.get("released") or []) if isinstance(x, dict)}
        small = [x for x in small if not isinstance(x, dict) or x.get("name") not in freed]
    if small and isinstance(small, list):
        names = shrink_sizes(small)
        return (f"smaller: {len(names)} of the files much smaller than the copies installed "
                f"({'; '.join(names[:4])}{' ...' if len(names) > 4 else ''}), so none was installed")
    return f"did not complete (exit {rc})"


def shrink_accepted(archive, since=None):
    """What the New term run's --allow-shrink let in tonight, from the
    snapshot's own record: the files much smaller than the copies they
    replaced, each with its size and how far it fell, or that none was."""
    rec = load_json(snapshot_day(archive, since) / INSTALL_RECORD)
    small = rec.get("shrunk") if isinstance(rec, dict) else None
    names = shrink_sizes(small)
    if not isinstance(rec, dict):
        return "the snapshot left no record of what it installed"
    turned = rec.get("turned") if isinstance(rec.get("turned"), dict) else None
    return ((f"accepted {len(names)} much smaller than the copies installed: {'; '.join(names)}"
             if names else "none of the files was much smaller")
            + (f"; the new term taken, {turned.get('from')} to {turned.get('to')}"
               if turned and turned.get("to") else ""))


def released_tonight(archive, since=None):
    """[[file, term]] the night's snapshot installed though much smaller,
    because the copy each replaced was that finished term's frozen one; []
    when it installed nothing."""
    rec = load_json(snapshot_day(archive, since) / INSTALL_RECORD)
    if not isinstance(rec, dict) or not rec.get("installed"):
        return []
    return [[str(x.get("name")), str(x.get("term"))] for x in rec.get("released") or []
            if isinstance(x, dict) and x.get("name")]


def new_term_ready(root="."):
    """(ok, sentence): whether a New term run may ask for tonight's files.

    Only where the installed files are in the LAST session of their term is
    the run's turn a new term, and then that term must be frozen as
    installed (freeze_term.ready: its docket and roll calls byte for byte,
    its views under db/term/). Before that the run can only be taking a new
    session year, which loses nothing and needs no freeze; files that name a
    new term would still be refused by the snapshot unless the term were
    frozen.

    THE LAST SESSION, NOT A DOCKET OF TWO YEARS (the review of 5 October
    2026). This asked whether the docket held both years of its term, and it
    does from the November of the first: 3,498 of today's 2026 rows are dated
    in 2025, the first 328 on 7 November 2025. So in a term's second January,
    when RollCallSummary.txt -- one session year -- meets its first vote of
    the new year and shrinks past the 30% rule, the box every scheduled night
    pointed to would have stopped for a freeze of an unfinished term. The
    files are in the last session when LSRs.txt and RollCallSummary.txt,
    which each hold one session year, both name the term's second year and
    nothing else: 2026 on 2 December 2026, 2027 in January 2028."""
    import freeze_term
    import proceedings as P
    import snapshot_gencourt as SG
    term = P.session_term(root)
    docket = Path(root) / "Docket.txt"
    years = SG.years_in(docket.read_bytes(), "Docket.txt") if docket.exists() else set()
    second = max(freeze_term.term_years(term)) if term else ""
    last = {}
    for name in ("LSRs.txt", "RollCallSummary.txt"):
        p = Path(root) / name
        last[name] = SG.years_in(p.read_bytes(), name) if p.exists() else set()
    if not term or not freeze_term.term_years(term) <= years or \
            any(ys != {second} for ys in last.values()):
        return True, ("the installed files are not in the last session of "
                      + (term or "a term") + " (LSRs.txt "
                      + (", ".join(sorted(last["LSRs.txt"])) or "no year")
                      + ", RollCallSummary.txt "
                      + (", ".join(sorted(last["RollCallSummary.txt"])) or "no year")
                      + "): a new session year needs no freeze, and the snapshot still refuses "
                        "a new term's files unless the term they leave is frozen")
    return freeze_term.ready(Path(root), term)


def installed_day(archive, docket):
    """Which day's files are installed here, by the docket: the day the
    archive first held this export, "<day> (from the database)" for a
    database night's copy, or "" when it is neither."""
    digest = hashlib.sha256(docket).hexdigest()
    idx = load_json(Path(archive) / "index.json") or {}
    hist = (idx.get("Docket.txt") or {}).get("history") if isinstance(idx, dict) else None
    days = [h[0] for h in (hist or []) if isinstance(h, list) and len(h) == 2 and h[1] == digest]
    if days:
        return str(days[-1])
    for src in sorted((Path(archive) / FROM_DB).glob("*/source.json"), reverse=True):
        rec = load_json(src) or {}
        if ((rec.get("files") or {}).get("Docket.txt") or {}).get("sha256") == digest:
            return f"{src.parent.name} (from the database)"
    return ""


def nights_since(archive, docket, day):
    """How many nights old the installed files are on the night of `day`, by
    the docket: the days since the archive last had these bytes as the
    General Court's newest -- the last night its export was fetched and was
    this, or a database night's copy -- and 1 when the archive cannot say.

    A database night's ceilings are a night's (dayfiles_from_db.SPAN), and a
    night that installs nothing leaves the files where they were: the next
    night's are compared with files two nights old, and four real days
    running bring more citations than a night's ceiling allows. One is the
    strictest answer, and the one given when nothing is known."""
    digest = hashlib.sha256(docket).hexdigest()
    days = []
    for ref in (Path(archive) / "snapshots").glob("*/Docket.txt.sha256"):
        try:
            if ref.read_text(encoding="utf-8").strip() == digest:
                days.append(ref.parent.name)
        except OSError:
            continue
    for src in (Path(archive) / FROM_DB).glob("*/source.json"):
        rec = load_json(src) or {}
        if ((rec.get("files") or {}).get("Docket.txt") or {}).get("sha256") == digest:
            days.append(src.parent.name)
    try:
        last = max(date.fromisoformat(d) for d in days if d < day)
        return max(1, (date.fromisoformat(day) - last).days)
    except ValueError:
        return 1


def tonights_members(archive, since):
    """Members.txt as the website served it tonight, or None. It is not part
    of the failing export, lives under /downloads/, and arrived whole on every
    failed night; the snapshot stored it though it installed nothing."""
    man = load_json(snapshot_day(archive, since) / "manifest.json")
    entry = man.get("Members.txt") if isinstance(man, dict) else None
    digest = entry.get("sha256") if isinstance(entry, dict) else None
    if not digest:
        return None
    try:
        with gzip.open(Path(archive) / "store" / f"{digest}.gz", "rb") as fh:
            data = fh.read()
    except (OSError, EOFError):
        return None
    return data if hashlib.sha256(data).hexdigest() == digest else None


def keep_db_copy(archive, day, files, block, src, was=None):
    """nh-archive/from-db/<day>/: what a database night installed, and a
    source.json saying when each view was asked, its rows, how many nights
    old the files it was judged against were, and each file's sha256. Beside
    the archive of the website's files, never in its index.

    `was` is the installed files the night's replaced, {name: bytes}: their
    sha256 goes in as "replaced", and gc_changes.py finds the copy to compare
    with by it. By date it took the archive's newest export, and on a night
    some of the export arrived whole that is tonight's own, which was never
    installed: the report compared the database's files with it and said
    nothing of what had changed since the installed day."""
    root = Path(archive) / FROM_DB / day
    root.mkdir(parents=True, exist_ok=True)
    rec = {"day": day, "asked": src.get("asked"), "views": src.get("views"),
           "compared_with": block.get("compared_with"), "years": block.get("years"),
           "nights": (block.get("held") or {}).get("nights"),
           "members": block.get("members"), "files": {},
           "replaced": {name: hashlib.sha256(data).hexdigest()
                        for name, data in sorted((was or {}).items())}}
    for name, data in sorted(files.items()):
        tmp = root / f"{name}.gz.part"
        with gzip.open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, root / f"{name}.gz")
        rec["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    write_json(root / "source.json", rec)
    return root


def from_database(a, night, tries, since):
    """A night the export came back empty -- on its first try, since
    2 October 2026 (DB_AFTER_TRIES); `tries` is how many had been made: the
    seven day files that change, from the General Court's database. True when
    they were installed -- all seven, with tonight's Members.txt -- and False
    when nothing was.

    The verdict's "day_files" is written here: its source ("database", or
    "none" with why_code and why when the fallback was tried and installed
    nothing), when the views were asked and how long they took, their rows,
    which day's files tonight's were compared with, the differences, what the
    content guards counted ("held": rows reworded, records changed, ballots
    cast otherwise, and how many nights old the installed files were -- every
    database night, so a threshold can be set from what a session shows), the
    rows behind every count that sits under a ceiling ("told": the General
    Court's own words, so they are in the verdict, the log and the
    what-changed report, and a warning says only how many), what was carried
    from the last good export, and the warnings; and, of a night the guards
    stopped, each stop ("stops") and how many of them are on a ceiling that
    widens with the nights ("stops_wider"). A night that may not fall back at
    all -- a New term run, a refusal on file, no installed files -- gets no
    "day_files" and one line in the log. Either way the verdict's "tried"
    gains a line in this file's own words, after the export try that sent the
    night here.
    """
    import dayfiles_from_db as DF
    import probe_db
    import snapshot_gencourt
    say("\n--- the day's files, from the General Court's database ---")
    tried = night.v.setdefault("tried", [])
    if a.new_term:
        say("  not asked: a New term run takes the new term's files from the export, or none")
        tried.append("the database: not asked, because a New term run takes its files from "
                     "the export or not at all")
        return False
    if refusal.MARK.exists():
        say("  not asked: a refusal from the web server is on file, and carrying on by "
            "another door is a person's decision")
        tried.append("the database: not asked, because a refusal from the web server is on file")
        return False
    try:
        was = DF.installed_files(".")
        DF.scope(was)
    except DF.Problem as e:
        say(f"  not asked: {e}", echo=False)
        say("  not asked: there are no installed files to take the years and the row order "
            "from. A machine with no last good day does not fall back.")
        tried.append("the database: not asked, because there are no installed files here to "
                     "compare its files with")
        return False
    block = night.v["day_files"] = {"source": "none", "after_try": tries,
                                    "because": "the export came back empty" + on_tries(tries)}

    def stop(code, detail=""):
        block.update(why_code=code, why=DB_WHY[code] + (f": {detail}" if detail else ""))
        tried.append(f"the database: nothing installed, because {DB_WHY[code]}")
        say(f"\nNOT INSTALLED FROM THE DATABASE: {DB_WHY[code]}. Nothing was installed.")
        if detail:
            say(f"  {detail}", echo=False)
        return False

    try:
        held = probe_db.hold_standing()
        if held:
            return stop("held", probe_db.hold_sentence(held))
        shutil.rmtree(DB_DAY, ignore_errors=True)
        t0 = time.time()
        rc = run(["fetch_day_db.py", "--fetch-only"],
                 "the day's records, from the General Court's database")
        src = load_json(DB_DAY / DF.SOURCE)
        src = src if isinstance(src, dict) else {}
        views = {k: e for k, e in (src.get("views") or {}).items() if isinstance(e, dict)}
        block.update(asked=src.get("asked"), seconds=round(time.time() - t0),
                     rows={k: e.get("rows") for k, e in views.items() if not e.get("error")})
        if rc != 0:
            # "query" only when a view says what failed. An exit with no
            # view's error beside it -- the lock gone, GitHub's window, the
            # script not starting -- was recorded as "a query of it failed",
            # and since 2 October 2026 the run's page prints that line.
            errs = [str(e.get("error") or "") for e in views.values()]
            code = ("held" if rc == probe_db.SQL_HELD else
                    "connect" if any(x.startswith("CONNECT_FAIL") for x in errs) else
                    "query" if any(errs) else "error")
            return stop(code, "; ".join(x for x in errs if x)[:300] or f"exit {rc}")
        try:
            files, facts = DF.rebuild(DB_DAY, ".")
        except DF.Problem as e:
            return stop("short", str(e))
        # The ceilings are a night's, and the installed files may be older.
        facts["nights"] = nights_since(a.archive, was["Docket.txt"], night.day)
        # Tonight's Members.txt, from the website: a changed roster is taken
        # when it names the database's (dayfiles_from_db.roster_named, the
        # person's decision of 5 October 2026). Never written to the verdict.
        facts["members"] = tonights_members(a.archive, since)
        result = DF.judge(files, was, facts)
        block.update(years=facts["years"], files=facts["rows"],
                     differences=result["differences"], held=result.get("held"),
                     told=result.get("told") or {},
                     compared_with=installed_day(a.archive, was["Docket.txt"]))
        for ln in DF.report(result, facts):
            say(ln, echo=False)
        if result["stops"]:
            block["stops"] = result["stops"]
            block["stops_wider"] = int(result.get("wider") or 0)
            return stop("guard", "; ".join(result["stops"]))
        notes = list(result["warnings"]) + DF.lookup_notes(DB_DAY, ".")
        fetched = dict(files)
        carried = sorted(set(snapshot_gencourt.FILES) - set(DF.DAY_FILES))
        members = tonights_members(a.archive, since)
        # MEMBERS.TXT IS THE WEBSITE'S, AND IS JUDGED AS THE WEBSITE'S
        # (2 October 2026). It went into the one install() with the seven
        # rebuilt files, so a short Members.txt alone tripped the shrink
        # rule, and the night's page said the files rebuilt from the
        # database were much smaller -- none was -- and, with the new order,
        # that the export was not asked again because of what the database
        # gave. A short one is treated as one that did not arrive.
        short = (snapshot_gencourt.shrunk({"Members.txt": members}, ".")
                 if members is not None else [])
        if short:
            carried.append("Members.txt")
            block["members"] = "the installed one: tonight's, from the website, was much smaller"
            notes.append("Members.txt from the website tonight was much smaller than the "
                         f"installed one ({short[0][1]:,} bytes against {short[0][2]:,}), so the "
                         "installed one stays")
            members = None
        elif members is not None:
            fetched["Members.txt"] = members
            block["members"] = "tonight's, from the website"
        else:
            carried.append("Members.txt")
            block["members"] = "the installed one: tonight's did not arrive"
            notes.append("Members.txt did not arrive from the website tonight, so the "
                         "installed one stays")
        done = (f"all seven of the day's changing files, {sum(facts['rows'].values()):,} rows, "
                "and " + ("tonight's Members.txt" if members is not None else "no Members.txt")
                + f"; compared with the files of {block['compared_with'] or 'an unknown day'}: "
                + (", ".join(f"{n} +{d['new']:,}/-{d['gone']:,}"
                             for n, d in result["differences"].items() if d["new"] or d["gone"])
                   or "no row differs"))
        ok, lines = snapshot_gencourt.install(fetched, ".")
        for ln in lines:
            say("  " + ln.strip(), echo=False)
        if not ok:
            return stop("shrink", lines[0])
    except Exception as e:                                      # noqa: BLE001
        return stop("error", f"{type(e).__name__}: {e}")
    # THE FILES ARE IN. Nothing from here on may say they are not: a copy that
    # could not be kept is a warning, never a night that installed nothing.
    block.update(source=DB_SOURCE, carried=carried, warnings=notes,
                 nights=night.v["db_nights"] + 1)
    # ... and the verdict names the source and counts the night from this
    # moment (2 October 2026), not from the end of the fetch: a night stopped
    # in a later step, with the seven files in and on their way back to the
    # kit, left a verdict that named no source and had not counted it. The
    # run of nights its checks stopped the fallback ends here as well: the
    # installed files have moved, which is what that count says they have not.
    night.v["files_from"], night.v["db_nights"] = DB_SOURCE, block["nights"]
    # A NIGHT THAT INSTALLS AFTER ONE THE CHECKS STOPPED SAYS SO. The files
    # the stopped night's were compared with had not moved and nobody had
    # decided anything; what let tonight's by is a ceiling that is wider a
    # night later, or views the General Court has changed since. Its page
    # said nothing of the night before, whose own page had said it could not
    # happen.
    # (Short: the run's page cuts a note off at 300 characters.)
    before = db_stopped_of(night.v)
    if before:
        notes.append("the night's own checks stopped this fallback on "
                     + (f"the {before} nights" if before > 1 else "the night")
                     + " before and passed it tonight, against the same installed files, with "
                     "nobody deciding in between: a night's ceilings are wider the older those "
                     "files are. What stopped it then is in that night's verdict and log")
    night.v["db_stopped"] = 0
    night.v.pop("db_stopped_day", None)
    say("\n  INSTALLED FROM THE DATABASE: " + done)
    tried.append("the database: all seven of the day's changing files installed")
    try:
        keep_db_copy(a.archive, night.day, fetched, block, src, was)
    except Exception as e:                                      # noqa: BLE001
        notes.append(f"the copy under {a.archive}/{FROM_DB}/{night.day}/ could not be "
                     f"written ({type(e).__name__})")
    return True


def count_lines(path):
    n = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            n += chunk.count(b"\n")
    return n


def captions_waiting(now=None):
    """How many finished recordings, CAPTION_WAIT_DAYS to CAPTION_WAIT_MOST
    days old, the laptop has not read yet, by the livestream state."""
    from datetime import timedelta, timezone
    st = load_json(LIVE_STATE)
    if not isinstance(st, dict):
        return 0
    now = now or datetime.now(timezone.utc)
    n = 0
    for v in (st.get("videos") or {}).values():
        if not isinstance(v, dict) or v.get("status") != "finished" or v.get("adopted"):
            continue
        if v.get("captions") not in ("waiting", "deferred", "failed", "for-laptop", "none-yet"):
            continue
        try:
            ended = datetime.fromisoformat(str(v.get("ended") or v.get("seen")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if timedelta(days=CAPTION_WAIT_DAYS) < now - ended <= timedelta(days=CAPTION_WAIT_MOST):
            n += 1
    return n


def take_lsrs():
    """Next session's bill requests into lsrs.json, whole or not at all, and a
    line saying what happened: "installed, ..." or "not taken: ...". The fetch
    runs here, in the working folder, so that a refusal it meets is recorded in
    the refusal record every other fetch reads."""
    before = LSRS.read_bytes() if LSRS.exists() else None
    old = load_json(LSRS) if before is not None else []
    old = old if isinstance(old, list) else []
    standing = {r.get("lsr") for r in old if isinstance(r, dict) and not r.get("withdrawn")}
    rc = run(["fetch_lsrs.py"], "next session's bill requests, from the General Court")
    EXITS["fetch_lsrs.py"] = rc
    new = load_json(LSRS)
    gone = [r for r in (new if isinstance(new, list) else [])
            if isinstance(r, dict) and r.get("withdrawn") and r.get("lsr") in standing]
    why = ""
    if rc != 0:
        why = f"the fetch did not complete (exit {rc})"
    elif not isinstance(new, list) or not new:
        why = "the fetch wrote no requests"
    elif len(gone) > max(LSR_GONE_FLOOR, LSR_GONE_MOST * len(standing)):
        why = f"it would newly withdraw {len(gone)} of the {len(standing)} standing requests"
    if why:
        if before is not None:
            tmp = LSRS.with_name(LSRS.name + ".part")
            tmp.write_bytes(before)
            os.replace(tmp, LSRS)
        else:
            LSRS.unlink(missing_ok=True)
        say(f"  bill requests not taken: {why}")
        return (f"not taken: {why}; "
                + (f"the earlier {len(standing)} kept" if before is not None else "none on file"))
    active = sum(1 for r in new if isinstance(r, dict) and not r.get("withdrawn"))
    return (f"installed, {active} requests (was {len(standing)})"
            + (f"; {len(gone)} newly withdrawn" if gone else ""))


def take_documents(v=None):
    """The General Court's list of its calendars and journals into
    archive/queue.csv, whole or not at all, and a line saying what happened:
    "installed, ...", "not taken: ..." or "not asked for: ...".

    fetch_calendar_archive.py --listing reads the two index pages -- four
    requests, under the lock this night holds -- and writes the queue with
    what is new added, and what each page listed, into the scratch folder.
    Both replace the installed copies only if the fetch exited 0 and its own
    judge() finds the list whole: every list read, none empty or sharply
    shorter than the page listed when it was last installed, every document
    on file still there at its own address, and each new address the General
    Court's own. The fetch runs here, in the working folder, so that a
    refusal it meets is recorded in the refusal record every other fetch
    reads.

    NOT ASKED AFTER A FETCH THAT DID NOT FINISH. The bill requests are asked
    of the same address a moment before this (EXITS). fetch_lsrs ends on 1,
    with no refusal recorded, when a connection is dropped or reset -- which
    its own docstring calls this address's way of refusing -- and the only
    thing between it and this step was the refusal record. So where that
    fetch did not complete, for whatever reason, the list waits for
    tomorrow: the lane's rule for a chain.

    SHORT THE SAME WAY, NIGHT AFTER NIGHT. `v` is the night's verdict, which
    carries documents_short from the night before: which documents a list
    came back without, as a digest, and for how many nights running. A list
    that is short and has nothing else wrong with it is counted there, and
    on night LIST_SAME_NIGHTS it is taken as the page's own.

    Every sentence this returns is this project's own -- counts and the
    lists' names -- because a warning is shown on the run's public page.
    """
    v = v if isinstance(v, dict) else {}
    SCRATCH.mkdir(exist_ok=True)
    new, listed = SCRATCH / DOCS.name, SCRATCH / DOCS_LISTED.name
    for f in (new, listed):
        f.unlink(missing_ok=True)
    try:
        import fetch_calendar_archive as CA
        was = CA.read_rows(DOCS)
    except Exception as e:                                      # noqa: BLE001
        say(f"  the list of calendars and journals not taken: {type(e).__name__}: {e}",
            echo=False)
        return "not taken: the night's own step for it failed; the list installed stays"
    kept = f"the earlier {len(was):,} kept" if was else "none on file"
    if EXITS.get("fetch_lsrs.py"):
        why = ("next session's bill requests were asked of the same address a moment "
               f"before and did not complete (exit {EXITS['fetch_lsrs.py']}), so nothing "
               "more is asked of it tonight")
        say(f"  the list of calendars and journals not asked for: {why}")
        return f"not asked for: {why}; {kept}"
    rc = run(["fetch_calendar_archive.py", "--listing", "--out", str(new)],
             "the calendars and journals the General Court lists")
    why, got, rec, settled = "", [], None, 0
    if rc == 2 and refusal.MARK.exists():
        # Only with the record on file: a script's own usage error ends on
        # 2 as well, and that is not the General Court saying no.
        why = ("the General Court refused a request: it is recorded, and every fetch "
               "waits for a person")
    elif rc != 0:
        # The listing says why it stopped, in its own words (its Stop), and
        # only words of that kind are passed on: the run's page is public.
        said = (load_json(listed) or {}).get("stopped") if listed.exists() else None
        why = (f"the listing stopped: {said}"
               if isinstance(said, str) and re.fullmatch(r"[A-Za-z0-9 ,.:;'()/-]{1,200}", said)
               else f"the fetch did not complete (exit {rc})")
    else:
        try:
            got, rec, last = CA.read_rows(new), load_json(listed), load_json(DOCS_LISTED)
            if not got or not isinstance(rec, dict):
                why = "the fetch wrote no list"
            else:
                why = CA.judge(was, got, rec, last)
                short = CA.shortfall(was, rec, last)
                if why and short and not CA.judge(was, got, rec, last, shorter=True):
                    # Short, and nothing else wrong with it: which documents,
                    # and for how many nights running.
                    same = hashlib.sha256(json.dumps(sorted(
                        [list(k), sorted(gone)] for k, gone, _, _ in short)).encode()
                    ).hexdigest()[:16]
                    seen = v.get("documents_short")
                    seen = seen if isinstance(seen, dict) else {}
                    n = seen.get("nights")
                    nights = (n if isinstance(n, int) and seen.get("same") == same else 0) + 1
                    if nights >= LIST_SAME_NIGHTS:
                        why, settled = "", nights
                    else:
                        v["documents_short"] = {"same": same, "nights": nights}
                        why += (f" (night {nights} of the {LIST_SAME_NIGHTS} running after "
                                "which the same answer is taken as the page's own)")
        except Exception as e:                                  # noqa: BLE001
            say(f"  {type(e).__name__}: {e}", echo=False)
            why = "what the fetch wrote could not be read"
    if not why:
        try:
            DOCS.parent.mkdir(parents=True, exist_ok=True)
            os.replace(new, DOCS)
            os.replace(listed, DOCS_LISTED)
        except OSError as e:
            say(f"  {type(e).__name__}: {e}", echo=False)
            why = "the list could not be put in place"
    for f in (new, listed):
        f.unlink(missing_ok=True)
    if why:
        say(f"  the list of calendars and journals not taken: {why}")
        return f"not taken: {why}; {kept}"
    v.pop("documents_short", None)
    what = f"installed, {len(got):,} documents (was {len(was):,}): {CA.news(was, got)}"
    if settled:
        what += (f"; a list that came back short the same way {settled} nights running "
                 "is taken as the page's own")
    for name in CA.unanswered(rec):
        what += (f"; {name} was not answered, with none on file for it: taken as none "
                 "posted yet")
    say(f"  the list of calendars and journals: {what}")
    return what


def take_views(views, label, shrink=SWAP_SHRINK, not_again=False):
    """The study committees' views from the database, whole or not at all.

    fetch_archive_db.py writes straight over db/<view>.psv and exits 0 even
    when a view fails, so it is run in a scratch folder, and each view replaces
    the installed copy only if the query succeeded, the file holds exactly the
    rows the query counted, and it is not more than `shrink` smaller than what
    it replaces (any fall, on the New term run; never empty). The views'
    entries in db/_manifest.json follow them in; the
    calendar reads the meetings' date from there. {view: what happened}.

    Not asked at all while a hold on the host stands (STUDY_HELD), or, with
    not_again, on a night the database was asked for the day's files and did
    not give them (STUDY_NOT_AGAIN).
    """
    import probe_db
    held = probe_db.hold_standing()
    if held or not_again:
        # No more queries of that host, from anything, while its hold stands;
        # and none the same night it failed the day's files, hold or no hold.
        say("  not asked: " + (probe_db.hold_sentence(held) if held else
                               "the database did not give the day's files earlier tonight"),
            echo=False)
        out = {v: STUDY_HELD if held else STUDY_NOT_AGAIN for v in views}
        for v, what in out.items():
            say(f"  {v}: {what}")
        return out
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
        if was and rows < was * (1 - shrink):
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
    reading where each track stops. A recording with no caption file is not
    compared, its times go out as they are, and the build prints one line.
    The same recordings, the same question, asked here so that the night can
    refuse to send a build to production that left them unchecked, rather
    than print a line about it. caption_span.last_cue reads the caption file
    itself; the laptop's summary of them (caption_spans.json, being written
    elsewhere) is what will let GitHub's machine pass this, and it has to be
    read there, through out_of_step, for this to see it.
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

    The same files, so the two compare: equal means production already
    serves this build, and there is nothing to approve. meta.json first,
    because the rest are the files the served meta.json names (fingerprinted).

    And, beside the fingerprint, into SERVED for the gate: each bill list it
    read, by its path, as bytes, or None where production answered 404
    ("files"); "whole" once every file was read, so that a list production's
    meta.json does not name is known to be one production does not have; and
    the commit production's build.json names (served_commit), asked for last
    and only once the fingerprint was read whole.
    """
    SERVED.clear()
    files = SERVED["files"] = {}
    h = hashlib.sha256()
    names, meta = ["meta.json"], None
    while names:
        name = names.pop(0)
        req = urllib.request.Request(f"{base.rstrip('/')}/{name}", headers={
            "User-Agent": "granite-record-selfcheck/1.0", "Cache-Control": "no-cache"})
        body, found = b"", True
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                h.update(body)
        except urllib.error.HTTPError as e:
            if e.code != 404:           # a 404 is passed over, as fingerprint()
                return None             # passes over a missing file
            found = False
        except Exception:               # noqa: BLE001 -- unreadable is "may differ"
            return None
        if name.startswith("idx/"):
            files[name] = body if found else None
        if meta is None:
            meta = _meta_of(body) if body else {}
            names = fingerprinted(meta)[1:]
    SERVED["whole"] = True
    SERVED["commit"] = served_commit(base, timeout)
    return h.hexdigest()[:16]


def served_commit(base, timeout=60):
    """The commit `base`'s build.json names, or None: where it cannot be read,
    is not JSON (a web page wearing its name), or names no commit -- a build
    published before 6 October 2026, or from the laptop."""
    req = urllib.request.Request(f"{base.rstrip('/')}/{BUILD_RECORD}", headers={
        "User-Agent": "granite-record-selfcheck/1.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read(BUILD_RECORD_MOST))
    except Exception:                   # noqa: BLE001 -- unreadable is "not known"
        return None
    c = d.get("commit") if isinstance(d, dict) else None
    return c if isinstance(c, str) and COMMIT.fullmatch(c) else None


def review_line(v, dry_run):
    """The gate's one line on the run's page, for a verdict that carries a
    review; "" for one that does not (a night that did not build). Each
    reason is a sentence of this file's own, from its own counts and the
    project's public commit ids: the page is public."""
    r = v.get("review") if isinstance(v.get("review"), dict) else None
    if not r:
        return ""
    if not v.get("publishable"):
        return REVIEW_NOT_FOR
    said = (REVIEW_LINES[1].format(why="; ".join(str(x) for x in r.get("why") or []))
            if r.get("needed") else REVIEW_LINES[0])
    if dry_run:
        return REVIEW_DRY.format(would=("would have " + said[len("Would have "):]))
    return said


def code_differs(sha, served):
    """True where tonight's commit and the one production's build names are
    both known and differ, False where both are known and the same, and None
    where either is not known."""
    if not COMMIT.fullmatch(str(sha or "")) or not COMMIT.fullmatch(str(served or "")):
        return None
    return sha != served


def release_reasons(sha, served):
    """The gate's second reason, as a list: [] on a night whose code is the
    code of the build production serves; one sentence where it is not, or
    where either commit is not known."""
    if not COMMIT.fullmatch(str(sha or "")):
        return [REVIEW_SHA_UNKNOWN]
    if not COMMIT.fullmatch(str(served or "")):
        return [REVIEW_LIVE_UNKNOWN]
    if code_differs(sha, served):
        return [REVIEW_RELEASE.format(tonight=sha[:12], served=served[:12])]
    return []


def bill_rows(raw):
    """{bill: its row as canonical JSON} of a bill list's bytes, the bill by
    its id and year (a term's two sessions may share a number); {} for none.
    A key that repeats keeps every row, in order."""
    rows = json.loads(raw) if raw else []
    if not isinstance(rows, list):
        raise ValueError("a bill list that is not a list")
    out = {}
    for r in rows:
        s = json.dumps(r, sort_keys=True, ensure_ascii=False)
        k = f"{r.get('id')}|{r.get('year')}" if isinstance(r, dict) and r.get("id") else s
        while k in out:
            k += "+"
        out[k] = s
    return out


def size_reasons(site, served, differs):
    """(reasons, measured): the gate's third reason, a night that changed far
    more than a data night does, from tonight's bill lists and production's
    copies (served["files"]). `measured` is recorded on every night: the
    current term, its bills, how many of their rows changed against
    production's, the finished terms whose lists differ, and the lists that
    could not be read. The reasons are given only where `differs` is not True
    (code_differs): a release waits anyway, and rewrites what it likes."""
    site = Path(site)
    mp = site / "meta.json"
    meta = _meta_of(mp.read_bytes()) if mp.exists() else {}
    terms = sorted({n[len("idx/"):-len(".json")] for n in SR.bill_index_files(meta)
                    if SR.TERM_FILE.fullmatch(n[len("idx/"):-len(".json")])})
    if not terms:
        raise ValueError("tonight's meta.json names no term")
    files = served.get("files") if isinstance(served.get("files"), dict) else {}

    def theirs(t):
        # Production's copy: bytes, None where it has none, or "unread".
        name = f"idx/{t}.json"
        if name in files:
            return files[name]
        return None if served.get("whole") else "unread"
    unread, differ = [], []
    for t in terms[:-1]:
        got = theirs(t)
        if got == "unread":
            unread.append(t)
        elif got != (site / "idx" / f"{t}.json").read_bytes():
            differ.append(t)
    newest, n, of = terms[-1], None, None
    got = theirs(newest)
    if got == "unread":
        unread.append(newest)
    else:
        mine, prod = bill_rows((site / "idx" / f"{newest}.json").read_bytes()), bill_rows(got)
        n, of = sum(1 for k in mine.keys() | prod.keys() if mine.get(k) != prod.get(k)), len(mine)
    measured = {"term": newest, "bills": of, "rows_changed": n, "finished_differ": differ,
                "unread": unread}
    if differs:
        return [], measured
    why = []
    if unread:
        why.append(REVIEW_UNREAD.format(terms=", ".join(unread)))
    if differ:
        why.append(REVIEW_FINISHED.format(terms=", ".join(differ)))
    if n is not None and n > REVIEW_ROWS_MOST:
        why.append(REVIEW_ROWS.format(n=n, of=of, term=newest, most=REVIEW_ROWS_MOST))
    return why, measured


def stamp_commit(site, sha):
    """Tonight's commit into site/build.json, which build_all wrote: what a
    later night reads back from production (served_commit). Only a full commit
    id, and only into a build.json that is there and reads as one; True when
    written. A build.json left without it is a commit a later night does not
    know, and waits for."""
    p = Path(site) / BUILD_RECORD
    if not COMMIT.fullmatch(str(sha or "")):
        return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(d, dict):
        return False
    d["commit"] = sha
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")
    return True


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
                  "asked": {"fetch": not a.no_fetch, "dry_run": a.dry_run,
                            "new_term": a.new_term},
                  "built": False, "publishable": False, "clean": False}
        # The gate's reasons from the build and from production (THE GATE),
        # filled in by judge; finish() adds the warnings' and writes "review".
        self.review_why = []
        prev = load_json(VERDICT)
        # How many nights in a row the day's files have come from the
        # database, carried from the night before: a night that installs the
        # export sets it to 0, one that falls back adds one, and a night that
        # takes neither leaves it.
        self.v["db_nights"] = db_nights_of(prev)
        # ... and how many nights the fallback was tried and stopped by its
        # own checks since the installed files last moved: one more for a
        # night they stop, 0 for a night either source installs, and left as
        # it was by a night that asks neither -- with the day of the last one
        # counted, so that a second run on that day adds none.
        self.v["db_stopped"] = db_stopped_of(prev)
        if db_stopped_day_of(prev):
            self.v["db_stopped_day"] = db_stopped_day_of(prev)
        # A list of calendars and journals that came back short, and for how
        # many nights running the same way (take_documents). Carried, so
        # that a night which does not ask leaves the count where it was.
        short = prev.get("documents_short") if isinstance(prev, dict) else None
        if isinstance(short, dict):
            self.v["documents_short"] = short
        if a.new_term:
            # What the New term run let through, filled in as it goes. Kept in
            # this night's verdict; what it accepted reaches a later night
            # only once its build is published (judge, runner_deploy).
            self.v["new_term"] = {}
        else:
            # A New term run that built the switch and was never published:
            # said on this night's page if it meets the smaller files again.
            was = unpublished_new_term(prev, load_json(CENSUS))
            if was:
                self.v["new_term_unpublished"] = was

    def intro(self):
        say(f"on GitHub's machine: commit {self.v['sha'][:12] or '(not on GitHub)'}, "
            f"run {self.v['run_id'] or '-'}; "
            + ("taking the day's data" if not self.a.no_fetch else "no fetch")
            + ("; a dry run: nothing goes to production" if self.a.dry_run else "")
            + (f"; {NEW_TERM_BOX}: the General Court's smaller files accepted, once"
               if self.a.new_term else ""))
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

    def judge(self, site, before, after, stop, changed, accepted=()):
        """After a build that passed check_site: can it go to production?

        accepted: what the census gates objected to and the New term run let
        through. A New term run writes no census here: its counts ride in the
        verdict and become the baseline when its build has landed on
        production (runner_deploy), so a run that is rejected, left waiting or
        blocked leaves the last good night's counts standing, and the next
        night is gated against those.
        """
        v, a = self.v, self.a
        v.update(build="passed", check_site="passed", built=True, census=after,
                 changed=changed)
        fp = fingerprint(site)
        v["fingerprint"] = fp
        # Tonight's commit goes out with the build (BUILD_RECORD), before the
        # list of every built file is made and before the preview and the
        # publish job take the site.
        if stamp_commit(site, v["sha"]):
            say(f"\n  {site.as_posix()}/{BUILD_RECORD} names commit {v['sha'][:12]}: a later "
                "night reads it back from production")
        else:
            say(f"\n  {site.as_posix()}/{BUILD_RECORD} names no commit (no full commit id "
                "tonight, or no build.json): a later night will not know this build's code")
        blocking = []
        if before is None:
            v["gates"] = "no baseline"
            blocking.append("there is no census from an earlier night, so the gates had "
                            "nothing to compare with; "
                            + ("a New term run sets no baseline until its build is published, "
                               "so run the nightly once without New term first (a dry run "
                               "that does not fetch sets one)" if a.new_term else
                               "tonight's counts are the baseline from tomorrow"))
        elif stop:
            v["gates"] = "blocked: " + "; ".join(stop)
            blocking += stop
        elif accepted:
            v["gates"] = "let through for a new term: " + "; ".join(accepted)
        else:
            v["gates"] = "passed"
        if "new_term" in v and before is not None and not stop:
            v["new_term"]["gates"] = ("let through: " + "; ".join(accepted) if accepted
                                      else "nothing the census counts fell")

        compared, of = captions_compared()
        unchecked = of - compared
        v["late_captions"] = {"compared": compared, "recordings": of}
        if unchecked > min(LATE_CAPTION_UNCHECKED, of // 100):
            blocking.append(
                f"the late-caption check compared {compared:,} of the {of:,} recordings "
                f"with published times: {unchecked:,} have no caption file here, nor a "
                "summary of one, so a caption track an hour out of step with its "
                "recording would be published as it is")

        code, data = tracked_changes()
        v["code_changed"], v["data_rewritten"] = code, data
        if code:
            blocking.append("tracked code differs from the commit: " + ", ".join(code[:6]))
        if data:
            say("\n  tracked data files the night rewrote (reported, not a stop): "
                + ", ".join(data[:12]) + (f" and {len(data) - 12} more" if len(data) > 12 else ""))

        SERVED.clear()
        live = live_fingerprint(a.base)
        v["live_fingerprint"] = live
        already = live == fp
        # The commit production's build names, read with it: None is "not
        # known", and a gate that cannot read it waits. And the bill lists it
        # read, for how much tonight changed against them; let go once used.
        v["live_commit"] = SERVED.get("commit")
        served = dict(SERVED)
        SERVED.clear()
        if not stop and a.new_term:
            # NOT WRITTEN TONIGHT. Written here, the lower counts were the
            # baseline before anyone had approved the switch, and the next
            # scheduled night passed its gates against them.
            v["new_term"]["kept"] = ("nothing yet: the smaller files, the study views and "
                                     "tonight's counts are kept for later nights once this "
                                     "build is published, and not before")
            say(f"  {CENSUS} is left as it was: a New term run's counts become the baseline "
                "when its build is published")
        elif not stop:
            write_json(CENSUS, {"census": after, "fingerprint": fp, "day": self.day,
                                "run_id": v["run_id"], "sha": v["sha"]})
            say(f"  tonight's counts are the baseline now: {CENSUS}")
        n = site_manifest(site, Path("logs") / f"site-{self.day}.sha256")
        say(f"  logs/site-{self.day}.sha256 lists all {n:,} files, with their sha256")

        v["blocking"] = blocking
        # THE GATE'S REASONS from the build and from production, in order:
        # finish() adds the warnings' and writes the verdict's "review".
        if a.new_term:
            self.review_why.append(REVIEW_NEW_TERM)
        self.review_why += release_reasons(v["sha"], v["live_commit"])
        try:
            why, v["against_production"] = size_reasons(
                site, served, code_differs(v["sha"], v["live_commit"]))
        except Exception as e:          # noqa: BLE001 -- the gate never stops a night
            say(f"  the gate could not measure tonight's change: {type(e).__name__}: {e}",
                echo=False)
            why = [REVIEW_FAILED.format(what="how much tonight changed", kind=type(e).__name__)]
        self.review_why += why
        del served
        # A New term run goes to the publish job even when production already
        # serves this very build: publishing is what lets what it accepted be
        # kept, and without it the next night would refuse the files for ever.
        v["publishable"] = not blocking and (not already or a.new_term)
        say("\n--- production ---")
        if blocking:
            say("\nNOT FOR PRODUCTION TONIGHT: " + " | ".join(blocking))
        elif already and not a.new_term:
            say(f"\n  {a.base} already serves this build: there is nothing to publish")
        elif a.dry_run:
            say("\n  this build could go to production; a dry run sends nothing there")
        else:
            say("\n  this build can go to production. The publish job waits for approval "
                "in the \"production\" environment, where there is a reviewer.")
            if a.new_term:
                say(("  " + a.base + " already serves this build, and it is published again "
                     "all the same: " if already else "  ")
                    + "what this New term run accepted is kept for later nights when that "
                    "deploy has landed, and not before.")

    def problems(self):
        """Why tonight was not clean, by CLOUD_MOVE.md's list; [] when it was."""
        v, why = self.v, []
        if (v.get("new_term") or {}).get("refused"):
            return [f"{NEW_TERM_BOX} was {v['new_term']['refused']}: nothing was done"]
        if v.get("preflight") != "passed":
            why.append("preflight " + str(v.get("preflight", "did not run")))
        if not self.a.no_fetch:
            if v.get("fetch") != "installed" and not from_db(v):
                why.append(f"the day's files: {v.get('fetch', 'not taken')}"
                           + ("." + db_tried(v).rstrip(".") if db_tried(v) else ""))
            else:
                # A view left unasked for the SQL host's hold is a warning
                # (warnings(), STUDY_HELD), as is one left unasked on a night
                # the database had already failed the day's files
                # (STUDY_NOT_AGAIN); one asked for and not taken is not.
                bad = [f"{k}: {r}" for k, r in (v.get("study_meetings") or {}).items()
                       if not r.startswith("installed") and r not in STUDY_UNASKED]
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

    def warnings(self):
        """What the night went ahead without: a list beside the record kept from
        an earlier night. Reported on the run's page and in the verdict, and
        never a reason to hold the night back."""
        out = []
        if from_db(self.v):
            # First, so that it leads the run's page.
            df, n = self.v["day_files"], int(self.v.get("db_nights") or 0)
            out.append("the day's files were built from the General Court's database, because "
                       "its export came back empty"
                       + on_tries(int(self.v.get("fetch_tries") or 1))
                       + (f" (night {n} in a row)" if n > 1 else ""))
            out += [str(w) for w in df.get("warnings") or []]
        elif db_tried(self.v) and self.v.get("fetch") == "installed":
            # The export's files, on a later try, after the database was
            # turned to and installed nothing: the night is the export's and
            # is clean, and its page says what the database did.
            out.append("the day's files are the export's, which arrived whole on try "
                       f"{int(self.v.get('fetch_tries') or 1)}: it came back empty first, and "
                       "the General Court's database, turned to then, installed nothing ("
                       + DB_WHY[self.v["day_files"]["why_code"]] + ")")
        empty = self.v.get("empty_rollcalls")
        if isinstance(empty, dict) and empty.get("files"):
            out.append(f"{' and '.join(empty['files'])} came back empty and were taken as files "
                       f"with no roll call in them yet: {str(empty.get('why') or '')[:150]}")
        left = self.v.get("left_out")
        if isinstance(left, dict) and left.get("rows"):
            # Rows of a finished term in tonight's files, counted and left out
            # (build_data): a late correction to that term would be one, and
            # whether its freeze should take it is a person's to decide.
            bills = [str(b) for b in left.get("bills") or []]
            out.append(f"rows of {', '.join(left.get('terms') or []) or 'a finished term'} in "
                       "tonight's files were left out, the term being built from its freeze: "
                       + ", ".join(f"{k} {v:,}" for k, v in sorted(left["rows"].items()))
                       + (f" ({', '.join(bills[:4])}{' ...' if len(bills) > 4 else ''})"
                          if bills else "")
                       + f"; {LEFT_OUT} lists them")
        for name, term in (self.v.get("released") or []):
            # A file that turned after the switch, taken because the copy it
            # replaced is a finished term's frozen one (snapshot_gencourt).
            out.append(f"{name} came back much smaller and was taken: the copy it replaced "
                       f"is {term}'s, frozen byte for byte, and that term is built from the "
                       "frozen copy")
        if study_held(self.v):
            # Short: the run's page cuts a note off at 300 characters.
            out.append("the study committees' meetings were not asked for: " + sql_hold_said())
        elif study_not_again(self.v):
            out.append("the study committees' meetings were not asked for: the General Court's "
                       "database did not give the day's files earlier tonight, and it is not "
                       "asked again the same night")
        lsrs = self.v.get("lsrs")
        if lsrs and not str(lsrs).startswith("installed"):
            out.append(f"next session's bill requests: {lsrs}")
        docs = self.v.get("documents")
        if docs and not str(docs).startswith("installed"):
            out.append(f"the General Court's list of calendars and journals: {docs}")
        n = captions_waiting()
        if n:
            out.append(f"{n} recording{'s' if n != 1 else ''} finished more than "
                       f"{CAPTION_WAIT_DAYS} days ago {'have' if n != 1 else 'has'} no start "
                       f"time from {'their' if n != 1 else 'its'} captions yet: the laptop's "
                       "evening catch-up (laptop_evening.py) reads them")
        return out

    def alarms(self):
        """What is an error on the run's page and does not stop the night:
        the build still goes out, and somebody has to act."""
        n = int(self.v.get("db_nights") or 0)
        if from_db(self.v) and n >= DB_NIGHTS_MOST:
            return [f"the day's files have come from the General Court's database {n} nights "
                    "in a row: its export came back empty on each of them, the committee list "
                    "and the other lookups are that old, and it is time to tell the General "
                    "Court's IT office"]
        df = self.v.get("day_files") if isinstance(self.v.get("day_files"), dict) else {}
        n = int(self.v.get("db_stopped") or 0)
        if df.get("why_code") == "guard" and n >= DB_STOPPED_MOST:
            return [f"the fallback on the General Court's database has been stopped by the "
                    f"night's own checks on {n} nights since the installed files last moved, "
                    "and the site has not moved in that time: the files it is compared with "
                    f"are the installed ones, {stopped_next(df)}. What stopped it is named "
                    "in the verdict (day_files, stops), and whether that is a wrong file or a "
                    "busy day is a person's to read"]
        return []

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
        alarms = self.alarms()
        v.update(finished=datetime.now().isoformat(timespec="seconds"), exit=code,
                 clean=not why and not alarms and code == 0, not_clean=why + alarms,
                 alarms=alarms, warnings=self.warnings())
        if v.get("built"):
            # THE GATE, for every night that built: whether it would wait for a
            # person, and why. In shadow it decides nothing.
            reasons = list(self.review_why)
            v["review"] = {"needed": bool(reasons), "why": reasons}
        write_json(VERDICT, v)
        say(f"\nverdict: {'CLEAN' if v['clean'] else 'NOT CLEAN'} -> {VERDICT}")
        for w in why + alarms:
            say(f"  - {w}")
        for w in v["warnings"]:
            say(f"  - warning: {w}")
        line = review_line(v, self.a.dry_run)
        if line:
            say(f"\nthe gate: {line}")
        # "review" is true wherever the gate did not clear the night, a night
        # that did not build included: the safe side for anything that reads it.
        gh_output(built=bool(v.get("built")), publishable=bool(v.get("publishable")),
                  clean=bool(v["clean"]), day=self.day,
                  review=bool((v.get("review") or {"needed": True})["needed"]))
        tries = int(v.get("fetch_tries") or 1)
        gh_summary([f"### Nightly {self.day}: {'clean' if v['clean'] else 'not clean'}",
                    f"- built: {'yes' if v.get('built') else 'no'}; for production: "
                    f"{'yes' if v.get('publishable') else 'no'}"]
                   + ([f"- **{v['warnings'][0]}**"] if from_db(v) and v["warnings"] else [])
                   + [f"- **error: {x}**" for x in alarms]
                   # The gate's line, under what leads the page.
                   + ([f"- {line}"] if line else [])
                   + ([f"- the day's files arrived whole on try {tries}"]
                      if tries > 1 and v.get("fetch") == "installed" else [])
                   + tried_lines(v)
                   + ([f"- the General Court's data page said{page_try(v)}: {v['data_page_said']}"]
                      if v.get("data_page_said") else [])
                   + [f"- {NEW_TERM_BOX}, {k}: {r}" for k, r in (v.get("new_term") or {}).items()
                      if k != "refused"]
                   + ([f"- {unpublished_note(v).strip()}"] if unpublished_note(v) else [])
                   + [f"- {w}" for w in why[:8]]
                   + [f"- warning: {w}" for w in v["warnings"]])


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
    if where == "production" and landed and (v.get("asked") or {}).get("new_term") \
            and isinstance(v.get("census"), dict):
        # THE NEW TERM RUN'S COUNTS BECOME THE BASELINE HERE, and nowhere
        # earlier: this build is published, so the next night is gated
        # against it. The workflow's next step moves the files the run
        # accepted into the kit (cloud.py kit-release) and sends this up.
        write_json(CENSUS, {"census": v["census"], "fingerprint": v.get("fingerprint"),
                            "day": v.get("day"), "run_id": v.get("run_id"),
                            "sha": v.get("sha"), "new_term": True,
                            "published": datetime.now().isoformat(timespec="seconds")})
        say(f"\n  {NEW_TERM_BOX}: this build is published, so its counts are the baseline "
            f"now: {CENSUS}")
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
    """wrangler to `target`, four attempts, then the live check, retried --
    except where it could not read a file to its end, which looking again
    would not change."""
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
        rc = run(["check_live.py", "--gate", "--base", base, "--site", str(site)],
                 f"what {base} is serving (look {i} of {len(LIVE_WAITS)})")
        if rc == 0:
            say(f"\nLive at {base}")
            return True
        if rc == LIVE_NOT_CHECKED:
            # Looking again would read the same file and stop at the same byte.
            say(f"\n{LIVE_UNREAD}")
            return False
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
    A night that was not clean puts plain_why()'s sentence at the top of the
    run's page on GitHub: an error when the job fails, a warning otherwise.
    """
    path = WEEKLY_VERDICT if a.weekly else VERDICT
    v = load_json(path)
    rid = github("GITHUB_RUN_ID")
    steps = {}
    for o in a.outcome:
        k, _, r = o.partition("=")
        steps[k.strip()] = r.strip()
    if not isinstance(v, dict) or v.get("run_id") != rid:
        older = v
        v = {"kind": "weekly" if a.weekly else "nightly", "run_id": rid,
             "sha": github("GITHUB_SHA"), "day": f"{datetime.now():%Y-%m-%d}",
             "clean": False, "built": False, "publishable": False,
             "not_clean": [f"the {'weekly job' if a.weekly else 'night'} stopped before "
                           "nightly.py recorded what it did"]}
        if not a.weekly:
            # A night that took neither source leaves the count of database
            # nights in a row as it was. Left out here, one night that never
            # started set it back to 0 in the middle of an outage, and the
            # error for DB_NIGHTS_MOST of them came that many nights late.
            v["db_nights"] = db_nights_of(older)
            v["db_stopped"] = db_stopped_of(older)
            if db_stopped_day_of(older):
                v["db_stopped_day"] = db_stopped_day_of(older)
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
    alarms = [str(x) for x in (v.get("alarms") or [])]
    if alarms and not failed and list(v.get("not_clean") or []) == alarms:
        # Built, and fit to go out, with something a person has to act on:
        # an error at the top of the run's page, and no failed job, because a
        # failed job publishes nothing.
        gh_annotate("error", "The night was built, with an error to act on",
                    "; ".join(alarms)[:400] + ". The build was not held back for it.")
        gh_summary([f"**Error:** {'; '.join(alarms)}"])
    elif not v.get("clean"):
        why = plain_why(v, a.weekly)
        gh_annotate("error" if failed else "warning",
                    f"Why the {'weekly job' if a.weekly else 'night'} "
                    f"{'failed' if failed else 'was not clean'}", why)
        gh_summary([f"**Why:** {why}"])
    elif v.get("warnings"):
        # Clean, and publishable, but something beside the record was kept
        # from an earlier night: said at the top of the run's page. Every
        # warning is a line nightly.py wrote from its own counts.
        gh_annotate("warning", "The night was clean, with a warning",
                    "; ".join(str(w) for w in v["warnings"])[:300]
                    + ". Everything else was taken as usual.")
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

    --new-term, the week a term's committee assignments are cleared and made
    again: the rosters, the committee list and the study committees' views are
    taken however much smaller, though never empty, for this one run. The
    members who have left are a merge, which is never smaller, and keep their
    guard. Ticked without the fetch it does nothing, and says so.
    """
    started = datetime.now()
    day = f"{started:%Y-%m-%d}"
    v = {"kind": "weekly", "day": day, "started": started.isoformat(timespec="seconds"),
         "run_id": github("GITHUB_RUN_ID"), "sha": github("GITHUB_SHA"),
         "asked": {"fetch": not a.no_fetch, "new_term": a.new_term}, "results": {},
         "clean": False}
    shrink = NEW_TERM_SHRINK if a.new_term else SWAP_SHRINK
    code = 1
    lock = Path(".nightly.lock")
    lock.write_text(f"{started:%Y-%m-%d %H:%M} pid {os.getpid()} (weekly)", encoding="utf-8")
    say("=" * 74)
    say(f"Granite Record weekly  {started:%Y-%m-%d %H:%M}")
    say("=" * 74)
    say(f"on GitHub's machine: commit {v['sha'][:12] or '(not on GitHub)'}; "
        f"the refusal record is {refusal.MARK}"
        + (f"; {NEW_TERM_BOX}: smaller committee lists accepted, once" if a.new_term else ""))
    before = {"committee_members": load_json("data/committee_members.json") or {},
              "former_members": load_json("former_members.json") or {},
              "committees": load_json("committees.json") or {},
              "study": {x: count_lines(Path("db") / f"{x}.psv")
                        for x in STUDY_WEEKLY if (Path("db") / f"{x}.psv").exists()}}
    try:
        if a.new_term and a.no_fetch:
            # Clean, and having taken nothing, its page used to say the lists
            # "were taken however much smaller".
            say("\nSTOPPED: " + WEEKLY_NEW_TERM_NO_FETCH)
            v["new_term"] = {"refused": REFUSED_NO_FETCH}
            v["not_clean"] = [f"{NEW_TERM_BOX} was {REFUSED_NO_FETCH}: nothing was taken"]
            return 1
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
                ["fetch_committee_members_db.py"], "data/committee_members.json", seats,
                shrink=shrink)
            time.sleep(4)
            res["former_members"], _ = take_json(
                "members who have left, from the database",
                ["fetch_members_db.py"], "former_members.json", len, seed=True, shrink=0.0)
            time.sleep(4)
            study = take_views(STUDY_WEEKLY, "the study committees' members and bills, "
                                             "from the database", shrink=shrink)
            res.update({f"study {k}": r for k, r in study.items()})
            time.sleep(4)
            if refusal.MARK.exists():
                res["committees"] = "not asked: a refusal is on file"
            else:
                res["committees"], rc = take_json(
                    "chairs, vice chairs, aides and rooms, from gc.nh.gov",
                    ["fetch_committees.py"], "committees.json", committee_count,
                    shrink=shrink)
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
        took = sum(1 for r in v["results"].values() if str(r).startswith("installed"))
        gh_summary([f"### Weekly {day}: {'clean' if v.get('clean') else 'not clean'}"]
                   + ([f"- {NEW_TERM_BOX}: {WEEKLY_NEW_TERM_NO_FETCH}"]
                      if (v.get("new_term") or {}).get("refused") else
                      [f"- {NEW_TERM_BOX}: for this run only, a committee list could come back "
                       f"any amount smaller, though never empty; {took} of the "
                       f"{len(v['results'])} below were taken"] if a.new_term else [])
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
