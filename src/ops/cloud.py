#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-25.19
"""
The nightly's kit and the laptop's backup, in the project's private R2 bucket.

    python3 src/ops/cloud.py kit-list [--sizes]        the kit's paths, from cloud_kit.json
    python3 src/ops/cloud.py seed-kit [--dry-run]      the laptop sends the kit, the first time
    python3 src/ops/cloud.py kit-down                  an empty machine takes the kit
    python3 src/ops/cloud.py kit-up [--dry-run]        ... and sends back what its night changed,
                                                       with the night's logs and state
    python3 src/ops/cloud.py kit-up --hold RUN         a New term run's: what it changed waits
                                                       under nights/RUN/kit/, out of kit/
    python3 src/ops/cloud.py kit-up --dry-night        a dry run's: only what it fetched goes
                                                       back, and its logs, apart (state-up too)
    python3 src/ops/cloud.py kit-release --run RUN     ... and goes into kit/, once that
                                                       run's build has been published
    python3 src/ops/cloud.py state-down | state-up     the small state files only
    python3 src/ops/cloud.py clear-refusal             lift the refusal record the night
                                                       keeps in the bucket (a person's call)
    python3 src/ops/cloud.py site-up --run ID          the night's built site, as one archive,
                                                       with that night's own verdict
    python3 src/ops/cloud.py site-down --run ID        ... and back, for the publish job
    python3 src/ops/cloud.py backup [--dry-run] [--with-site]
                                                       everything git does not hold
    python3 src/ops/cloud.py pull [--dry-run] [--day YYYY-MM-DD] [--changes-only]
                                  [--take PATH ...]    the laptop takes back what the
                                                       nights changed: their files, logs,
                                                       change lists, verdicts and refusal
    python3 src/ops/cloud.py send-refusal [--dry-run]  a refusal met here, to the bucket,
                                                       when refusal.py could not send it
                                                       or it waited behind another

    --local-bucket FOLDER   a folder stands in for the bucket, for testing
    --root FOLDER           the working folder (default: the current one)
    --workers N             transfers at once (default 8)

Run from the repository root. Credentials come from keys.r2(): the
environment on GitHub's machine, secrets.json on the laptop. Nothing here asks
the General Court, YouTube or GitHub anything; it talks to the bucket only,
and boto3 is needed only for that.

WHY THIS EXISTS

The nightly moved to GitHub's machines, which start empty every night. The
build reads 1.9 GB that git does not hold -- the day's files, the saved bill
pages, the dumped database, the outputs a build reads before it rewrites
them -- out of the 44.5 GB on the laptop, and cloud_kit.json lists it. The
laptop sends it once (seed-kit); each night takes it down (kit-down), builds,
and sends back what it changed (kit-up). The laptop's own copy of everything
else goes up with backup.

WHAT IT WILL NOT DO

Overwrite or delete anything in the bucket outright. An object about to be
replaced or removed is first copied to replaced/<date>/<prefix>/<path>, which
the bucket's lifecycle rule keeps for 30 days. Removals also stop above a
small share of what is there, because a walk of the wrong folder looks
exactly like a thousand deletions.

Report success for a partial transfer. Every file is checked against its size
and sha256 on the way down, every command ends on a line of counts and bytes,
and anything short is a non-zero exit with a plain sentence saying what.

Let two machines each overwrite the other. Each kit file has one owner. The
laptop's seed-kit never sends a file the night owns over the night's copy,
and the night's kit-up never sends a file the laptop owns; if the bucket's
copy of a file changed after this machine took it down, kit-up keeps the
bucket's and files its own under replaced/ rather than choose.

Send a secret or a reader's words. cloud_kit.json's "never" list is applied to
every command, and preflight holds the list to what it must contain.

THE BUCKET

    kit/<path>             the kit, laid out as the working folder is
    backup/<path>          the laptop's backup
    replaced/<date>/...    what a command would otherwise have overwritten or removed
    logs/<date>/<file>     the night's logs
    nights/<run>/          the night's built site, one archive, and site.json, which
                           carries the night's own verdict, for the publish job,
                           with first-seen.json, the ledger its build left
                           (FIRST_SEEN_NEXT), which a New term run's deploy keeps;
                           and under kit/, with kit.json, what a New term run's
                           night changed, waiting for its build to be published
    state/<file>           refused.json, census.json and the rest (cloud_kit.json);
                           kit-manifest.json and backup-manifest.json, the size,
                           sha256 and date of every file sent, which is how an
                           unchanged file is never sent twice

On a machine, small state lives under archive/ -- archive/refused.json,
archive/census.json -- and only the bucket calls it state/. This machine's
own record lives in archive/cloud/: what kit-down fetched, which build_all.py
reads as "this folder is built from the kit"; what state-down took, which
state-up reads so a copy taken down is never sent back over a newer one; and
a cache of hashes so an unchanged file is not read twice either.

THE ONE NIGHT A TERM TURNS OVER: kit-up --hold, kit-release (1 October 2026)

The New term run (nightly.py --new-term) installs files the shrink rule would
refuse on any other night, and the switch to a new term waits for the
person's approval. Sent to kit/ in the ordinary way, those files would be the
installed copies the next scheduled night compares with -- so that night
would take the new term's files without complaint and publish the switch,
whether the person had approved it, rejected it, or not yet looked. So that
run's kit-up is given --hold RUN: every file of the night's it changed goes
to nights/RUN/kit/<path> instead, with nights/RUN/kit.json saying what waits
and which copy of each the night had taken down, and kit/ and its manifest
keep what they held. (An entry cloud_kit.json marks "held": false goes to
kit/ all the same: the day's archive copy and the livestream index.) The
publish job runs kit-release --run RUN after the deploy has landed: each
waiting file is copied into kit/ over the copy the night took down -- all of
them or none, and none if kit/ has changed underneath since -- and the
manifest follows. A run never published is never released, and nights/ is
deleted by the bucket's lifecycle rule a few days on.

A DRY RUN SENDS BACK ONLY WHAT IT FETCHED: --dry-night (7 October 2026)

A dry run is how code not yet on main is tried, on dev, and until this its
kit-up sent back every file of the night's it had changed, and its state-up
every state file: the outputs a build carries (text_sponsors.json,
narratives.json, proceedings.csv and the rest), the one file of the site a
build reads, the study views, the bill requests, the list of calendars, the
livestream index, the census and the night's verdict -- every one of them
written by that branch's code, and every one taken down and read by main's
next night. So a dry run's code reached production a night later, without a
merge. --dry-night, which the workflow's DRY_RUN (DRY_ENV) implies on
GitHub's machine whatever a step passes -- and so does a run of any branch
but main (REF_ENV, MAIN_REF), which is a dry run whatever its boxes say (the
person's decision of 7 October 2026) -- sends back only what cloud_kit.json's
"dry_run" names:

  what it fetched     the archive's copy of each file the General Court's
                      export served tonight: a blob of nh-archive/store that
                      kit-down did not bring, sent only where its bytes,
                      unpacked, are the sha256 its name says (dry_sends,
                      blob_holds). The General Court's bytes, which no code
                      shapes; nothing is lost of what the run fetched
  not what it chose   THE REVIEW OF 7 OCTOBER 2026. This sent the day's files
                      as the run installed them too, where the store held
                      their bytes, and the archive's index.json and its
                      snapshots/<day>/ records. Those are the branch's code's
                      work: its index, in whatever shape it writes, is what
                      main's next snapshot opens and appends to and what
                      installed_day and gc_changes read; its install.json is
                      its own judging; and "the store holds it" is true of
                      every file the export ever served, so a branch that put
                      an older docket back sent that to kit/ for main's next
                      night to install. None of them goes back now: the kit's
                      day files, index and day records stay main's, and the
                      next real night fetches and indexes its own. Nor the
                      database nights' copies under nh-archive/from-db/
  its logs            under logs/<day>/dry-run/, apart from the night's, so
                      that pull, which takes logs/<day>/<name> alone, never
                      takes a dry run's log or change list for the night's
  the state           a refusal and a hold on the SQL host, which are facts
                      about another server and stop the next night's asking
                      whoever met them, and its own verdict
                      (state/last-dry-run.json, or a dry weekly's
                      state/last-dry-weekly.json); never the census, the
                      night's verdict, the week's or the first-seen ledger
                      (DRY_NEVER)

Nothing is removed from the kit on a dry night, and the rest it changed is
named as kept back. The weekly's dry run -- every run of it off main, since 7
October 2026 -- is the same command and the same rule: it archives nothing
in the store, so none of the lists it took goes back, only its logs, a refusal or a
hold, and its verdict, apart. A dev weekly proves the weekly's code and keeps
nothing it fetched. A New term run ticked with Dry run, which nightly.py
refuses before it asks for anything, is still given --hold by the workflow:
on a dry night that holds nothing and sends nothing of the kit, only the
logs and the state above.

BACK TO THE LAPTOP: pull (26 September 2026)

kit-down is for an empty machine and treats a differing file as a clash, so
until pull nothing brought the nights' work back: the laptop's data froze at
the stand-down, its nightly logs stopped, and the morning triage could not
read the day's change list. pull is the laptop's, never GitHub's (kit-down is
the command there), and it only ever READS the bucket -- it puts, copies and
deletes nothing there, and preflight holds its code to that.

  the night's kit files   brought down where the bucket's differs, but only
                          over the copy this laptop last had in common with
                          the bucket: archive/cloud/pull.json records each
                          one pull took or found the same, and before a
                          file's first pull the bucket's own manifests say
                          which copies it ever held (the current one and
                          those kept under replaced/). A night's file changed
                          here since is left alone and named, and pull exits
                          1: --take PATH sets this laptop's copy aside under
                          archive/cloud/set-aside/<day>/ and takes the
                          bucket's. The laptop's own files are never touched;
                          they flow the other way, with seed-kit. site/ is
                          never pulled: the laptop's site/ is its own build's,
                          and one file of the night's in it is neither build.
  the night's logs        logs/<day>/nightly-<day>.log, weekly-<day>.log and
                          site-<day>.sha256 to logs/; gc-changes-<day>.md and
                          gc-changes-weekly-<day>.md to reports/, where the
                          morning triage looks. Since the last pull, at most
                          PULL_DAYS days, or --day. A local file of the same
                          name that differs, and that pull did not write, is
                          a clash like a kit file's. The days start the day
                          before the last pull's, because a night's folder is
                          named for the day it started in Eastern time.
  the verdicts            state/last-night.json, last-dry-run.json,
                          last-weekly.json and last-dry-weekly.json to
                          archive/cloud/ -- NOT archive/, where state-down's
                          record would take them for this machine's own. A
                          night's from before yesterday is called STALE; a dry
                          run's is said to be one, kept apart from the night's
                          or the week's (nightly.DRY_VERDICT,
                          WEEKLY_DRY_VERDICT).
  the refusal             state/refused.json comes down as archive/refused.json
                          when the laptop has none (a refusal the night met
                          stops this laptop's fetches too); where both hold
                          one the newer stands and the older is set aside,
                          never dropped. When pull read it is recorded, with
                          the kind of bucket, and refusal.check() on a
                          stood-down laptop refuses to start a General Court
                          fetch until a read of the REAL bucket since
                          GitHub's last night window. A bucket holding
                          neither the kit manifest nor a night's verdict is
                          empty or not the night's: pull stops before
                          reading anything from it. A standing refusal here
                          that the bucket holds none of is a failure.

--changes-only is the morning triage's: the refusal, the verdicts and the
change lists, and nothing else -- except a line saying how old the last full
pull is and how many of the night's files the bucket's kit manifest has
changed since, which pull.json's "full" records and preflight holds to 48
hours on a stood-down laptop.

--local-bucket is for tests, and pull refuses it in the stood-down
repository that holds secrets.json unless --allow-local-bucket says a test
there is meant; its read of the refusal record never counts either way.

send-refusal is the other direction for the one file that must cross at
once: a refusal refusal.py records on a stood-down laptop goes to the
bucket's state/refused.json when the bucket holds none, so the night stops
too -- to the real bucket only from the repository that holds secrets.json.
refusal.note() calls send_refusal() itself; when the bucket cannot be
reached, or holds another refusal this one must wait behind (the night stops
at that one, and it is never overwritten from here), it leaves
archive/cloud/refusal-unsent.json saying which, and pull, state-up and
preflight report it until the bucket holds this refusal or a person lifts it
here. clear-refusal says when this machine holds a refusal the bucket does
not, which is the moment a waiting one needs sending.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import hashlib
import json
import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import child

KIT_FILE = "cloud_kit.json"
LOCAL = "archive/cloud"
KIT_RECORD = f"{LOCAL}/kit-down.json"
STATE_RECORD = f"{LOCAL}/state-down.json"
HASHES = f"{LOCAL}/hashes.json"
LOCK = f"{LOCAL}/lock"
MANIFEST = "state/{}-manifest.json"
MB = 1 << 20

# pull's own record, and where it puts what is not the working folder's.
PULL_RECORD = f"{LOCAL}/pull.json"
UNSENT = f"{LOCAL}/refusal-unsent.json"
SET_ASIDE = f"{LOCAL}/set-aside"
VERDICTS = {"last-night.json": f"{LOCAL}/last-night.json",
            "last-dry-run.json": f"{LOCAL}/last-dry-run.json",
            "last-weekly.json": f"{LOCAL}/last-weekly.json",
            "last-dry-weekly.json": f"{LOCAL}/last-dry-weekly.json"}
# ... and how pull names a dry run's verdict, which is never the night's or
# the week's (nightly.DRY_VERDICT, nightly.WEEKLY_DRY_VERDICT).
DRY_VERDICTS = {"last-dry-run.json": "a dry run, kept apart from the night's,",
                "last-dry-weekly.json": "a dry run of the weekly, kept apart from the week's,"}
# THE PUBLISH JOB DEPLOYS A RUN'S OWN BUILD BY ITS OWN VERDICT (7 October
# 2026). site-up sends the night's verdict, from where nightly.py writes it
# (nightly.VERDICT), inside nights/<run>/site.json, and site-down writes it
# where --deploy-to production reads it (nightly.RUN_VERDICT). preflight holds
# both names to nightly.py's.
NIGHT_VERDICT = "archive/last-night.json"
SITE_VERDICT = "archive/run-verdict.json"
# The workflow's word that a run is a dry run, which every step inherits
# (nightly.DRY_ENV). On GitHub's machine it makes kit-up and state-up a dry
# night's whatever they were told (--dry-night), and keeps site-up from
# sending a dry run's site for production.
DRY_ENV = "DRY_RUN"
# ... and every run of a branch other than main is one, whatever DRY_RUN says
# (7 October 2026, the person's decision): GitHub names the run's branch in
# GITHUB_REF, read here again so that an edit to the workflow's DRY_RUN line
# cannot reopen what it closes (nightly.REF_ENV and MAIN_REF, which preflight
# holds these to). Main is MAIN_REF exactly: a missing ref is not, and nor is
# refs/heads/Main, which the workflow's expressions cannot tell from it.
REF_ENV = "GITHUB_REF"
MAIN_REF = "refs/heads/main"
# Where a dry night's logs go, under logs/<day>/: a folder pull does not read.
DRY_LOGS = "dry-run"
# The state a dry night never sends, whatever cloud_kit.json's "dry_run" says:
# what the next real night is gated against, the night's own verdict, and the
# week's, which a dry weekly -- every weekly off main -- keeps apart too (7
# October 2026), and the first-seen ledger, which says what the email sender
# has been told is new (src/pages/follow_changes.py): a dry run reads the
# night's and sends none.
DRY_NEVER = ("census.json", "last-night.json", "last-weekly.json", "first-seen.json")
# The first-seen ledger a build leaves, beside the one it read
# (follow_changes.CANDIDATE; preflight holds the two names together). nightly.py
# keeps it for a build it accepts, and a New term run's only once its build is
# published -- on the publish job's machine, so site-up sends it with the site
# and site-down brings it back here, as the run's verdict travels. Only a real
# run's: site-up refuses a dry run -- every run off main -- before it reads it.
FIRST_SEEN_NEXT = "archive/first-seen.next.json"
PULL_DAYS = 7
# What pull takes from logs/<day>/, and the folder each goes to. Anything
# else there stays in the bucket: a name this does not know could be one the
# laptop uses for a log of its own.
CHANGES = re.compile(r"^gc-changes-(?:weekly-)?\d{4}-\d\d-\d\d\.md$")
PULL_LOGS = ((re.compile(r"^(?:nightly|weekly)-\d{4}-\d\d-\d\d\.log$"), "logs"),
             (re.compile(r"^site-\d{4}-\d\d-\d\d\.sha256$"), "logs"),
             (CHANGES, "reports"))
# The night's files pull never takes: the laptop's built site is its own.
PULL_NOT = ("site/",)
# Set by preflight for itself and everything it runs: with it, nothing here
# reaches the real bucket, whatever a check drives. A folder bucket still works.
NO_BUCKET = "GRANITE_NO_BUCKET"

# A removal is a decision. A walk of the wrong folder, or a disk that did not
# mount, looks exactly like a thousand files deleted, and moving them all to
# replaced/ would have them gone in 30 days. Above this share (or this count),
# nothing is removed without --allow-removals.
REMOVE_SHARE, REMOVE_MAX = 0.02, 1000

# Long transfers record their progress this often, so an interrupted first
# backup resumes rather than starting again.
CHECKPOINT = 300


class Failed(Exception):
    """A command that cannot go on: its message is the sentence the person reads."""


# What must never reach a log: GitHub's run logs of a public repository are
# public, and an error from the S3 client can carry the endpoint -- the
# account ID is in its host name -- which GitHub masks only if it was saved
# as a secret. R2Bucket adds the values it was given; everything printed
# passes through scrub().
_PRIVATE = []


def scrub(msg):
    msg = str(msg)
    for v in _PRIVATE:
        if v:
            msg = msg.replace(v, "<private>")
    return msg


def say(msg=""):
    print(scrub(msg), flush=True)


def human(n):
    n = float(n)
    if n < 1000:
        return f"{n:,.0f} bytes"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1000
        if n < 1000 or unit == "TB":
            return f"{n:,.2f} {unit}"


# ---------------------------------------------------------------- patterns --

def glob_re(pat):
    """A glob over /-separated relative paths, as a regex. * and ? stay inside
    one folder; ** crosses any number of folders, none included."""
    out, i = ["^"], 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:[^/]*/)*")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        else:
            c = pat[i]
            out.append("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def check_rel(p):
    """A relative /-path that cannot climb out of the working folder."""
    if (not isinstance(p, str) or not p or "\\" in p or p.startswith("/")
            or re.match(r"^[A-Za-z]:", p)
            or any(s in ("", ".", "..") for s in p.split("/"))):
        raise Failed(f"{KIT_FILE}: {p!r} is not a plain relative path")
    return p


def local(root, rel):
    return Path(root).joinpath(*rel.split("/"))


def expand(root, pat):
    """Every file under root matching one glob, as sorted /-paths. Only the
    folders the pattern can reach are walked: "Docket_*.txt" reads the root,
    not the 44 GB below it."""
    segs = pat.split("/")
    fixed = []
    for s in segs[:-1]:
        if "*" in s or "?" in s:
            break
        fixed.append(s)
    base = local(root, "/".join(fixed)) if fixed else Path(root)
    rx, deep, depth = glob_re(pat), "**" in pat, len(segs) - len(fixed)
    out = []
    if not base.is_dir():
        return out
    stack = [(base, "/".join(fixed), 1)]
    while stack:
        d, rel, lvl = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            r = f"{rel}/{e.name}" if rel else e.name
            if e.is_dir(follow_symlinks=False):
                if deep or lvl < depth:
                    stack.append((Path(e.path), r, lvl + 1))
            elif e.is_file(follow_symlinks=False) and rx.match(r):
                out.append(r)
    return sorted(out)


# --------------------------------------------------------------- the kit ----

def load_kit(root):
    p = Path(root) / KIT_FILE
    if not p.exists():
        raise Failed(f"No {KIT_FILE} in {Path(root).resolve()}. Run this from the "
                     "repository root, or give --root.")
    try:
        kit = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise Failed(f"{KIT_FILE} will not read: {e}")
    for e in kit.get("kit", []):
        if e.get("owner") not in ("night", "laptop"):
            raise Failed(f"{KIT_FILE}: an entry's owner is {e.get('owner')!r}, "
                         "not 'night' or 'laptop'")
        for x in list(e.get("paths", [])) + list(e.get("globs", [])):
            check_rel(x)
        if "held" in e and (e["held"] is not False or e["owner"] != "night"):
            raise Failed(f"{KIT_FILE}: an entry says held: {e['held']!r}. Only a night's "
                         "entry may say it, and only false: every other file of the "
                         "night's is held on a New term run")
    for s in kit.get("state", []):
        check_rel(s["path"])
        if not s.get("key") or "/" in s["key"]:
            raise Failed(f"{KIT_FILE}: state key {s.get('key')!r} is not a plain name")
    # What a dry night sends back: only the night's own files, and of the
    # state never what the next real night is gated against.
    d = kit.get("dry_run") or {}
    keys = {s["key"] for s in kit.get("state", [])}
    for x in list(d.get("globs", [])) + [d.get("store") or "x"]:
        check_rel(x)
    for x in [re.sub(r"\*+", "x", g) for g in d.get("globs", [])]:
        if owner_of(kit, x) != "night":
            raise Failed(f"{KIT_FILE}: \"dry_run\" names {x}, which is not a night's kit file")
    if "served" in d:
        raise Failed(f"{KIT_FILE}: \"dry_run\" names day files to send, and a dry night sends none "
                     "since the review of 7 October 2026: what it installed is its code's choice")
    bad = [k for k in d.get("state", []) if k not in keys or k in DRY_NEVER]
    if bad:
        raise Failed(f"{KIT_FILE}: \"dry_run\" sends state {bad}, which is not in the state list "
                     f"or is one a dry night never sends ({', '.join(DRY_NEVER)})")
    return kit


def dry_night(a):
    """Whether kit-up or state-up is a dry run's: --dry-night, or the
    workflow's word on GitHub's machine (dry_by_workflow), whatever a step
    passed."""
    return bool(getattr(a, "dry_night", False)) or dry_by_workflow()


def dry_sends(kit, root, rel, before):
    """Whether a dry night sends this night's file back: only the archive's
    copy of something the export served tonight -- a blob of "dry_run"'s
    store, matched by its globs, that kit-down did not bring (`before`, the
    record of what it did) and whose bytes unpacked are the sha256 its name
    says. Nothing else: not a day's file, whatever its bytes, nor the
    archive's index or its day records (the docstring says why)."""
    d = kit.get("dry_run") or {}
    store = d.get("store")
    if not store or rel in before or not any(glob_re(g).match(rel) for g in d.get("globs", [])):
        return False
    m = re.fullmatch(re.escape(store) + r"/([0-9a-f]{64})\.gz", rel)
    return bool(m) and blob_holds(local(root, rel), m.group(1))


def blob_holds(path, sha256):
    """Whether the archive's blob at `path` unpacks to bytes whose sha256 is
    `sha256`: what the store's names promise, read rather than trusted."""
    import gzip
    h = hashlib.sha256()
    try:
        with gzip.open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except (OSError, EOFError, ValueError):
        return False
    return h.hexdigest() == sha256


def never_rx(kit):
    return [glob_re(g) for g in (kit.get("never") or {}).get("globs", [])]


def entry_matches(e, rel):
    return rel in e.get("paths", []) or any(glob_re(g).match(rel)
                                            for g in e.get("globs", []))


def owner_of(kit, rel):
    for e in kit.get("kit", []):
        if entry_matches(e, rel):
            return e["owner"]
    return None


def held_back(kit, rel):
    """Whether kit-up --hold keeps this file out of kit/ until the New term
    run's build is published: every file of the night's, unless its entry
    says "held": false."""
    for e in kit.get("kit", []):
        if entry_matches(e, rel):
            return e["owner"] == "night" and e.get("held", True) is not False
    return False


def kit_files(root, kit):
    """({path: owner}, [entries that match nothing], [held back by never]).

    A required entry that matches nothing is missing: a partial kit builds a
    smaller site that passes its own checks, so it is a failure, not a note.
    """
    never = never_rx(kit)
    files, missing, held = {}, [], []
    for e in kit.get("kit", []):
        owner, found = e["owner"], []
        for p in e.get("paths", []):
            if local(root, p).is_file():
                found.append(p)
            elif not e.get("optional"):
                missing.append(p)
        for g in e.get("globs", []):
            got = expand(root, g)
            if not got and not e.get("optional"):
                missing.append(g)
            found.extend(got)
        for p in found:
            if any(rx.match(p) for rx in never):
                held.append(p)
                continue
            if files.get(p, owner) != owner:
                raise Failed(f"{KIT_FILE} gives {p} two owners; one file has one writer")
            files[p] = owner
    return files, missing, held


# ----------------------------------------------------------------- hashing --

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(4 * MB)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class Hashes:
    """sha256 per file, reused while its size and date are unchanged."""

    def __init__(self, root):
        self.root = Path(root)
        self.path = local(root, HASHES)
        self.lock = threading.Lock()
        try:
            self.seen = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.seen = {}

    def entry(self, rel):
        """{"size", "sha256", "mtime_ns"} for a file as it stands now."""
        st = local(self.root, rel).stat()
        with self.lock:
            hit = self.seen.get(rel)
        if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
            sha = hit[2]
        else:
            sha = sha256_of(local(self.root, rel))
            with self.lock:
                self.seen[rel] = [st.st_size, st.st_mtime_ns, sha]
        return {"size": st.st_size, "sha256": sha, "mtime_ns": st.st_mtime_ns}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with self.lock:
            tmp.write_text(json.dumps(self.seen), encoding="utf-8")
        os.replace(tmp, self.path)


def hash_all(hashes, rels, workers, what):
    """({rel: entry}, [failures]) for every file, several at a time."""
    out, bad = {}, []
    t0, last = time.time(), [time.time()]

    def one(rel):
        try:
            return rel, hashes.entry(rel), None
        except OSError as e:
            return rel, None, str(e)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (rel, ent, err) in enumerate(ex.map(one, rels), 1):
            if err:
                bad.append(f"{rel}: {err}")
            else:
                out[rel] = ent
            if time.time() - last[0] > 30:
                last[0] = time.time()
                say(f"  read {n:,} of {len(rels):,} {what} ({time.time() - t0:.0f}s)")
    return out, bad


# ---------------------------------------------------------------- buckets --

class FolderBucket:
    """A folder standing in for the bucket: the same keys, as files. Object
    metadata sits beside them under .meta/, which no listing shows.

    kind and name say which bucket a read was of, for pull's record: only a
    read of the real one ("r2") frees a stood-down laptop's fetches."""
    kind = "folder"

    def __init__(self, folder, create=True):
        self.root = Path(folder)
        # A dry run makes no folder: every read below answers "nothing there"
        # for a folder that does not exist.
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        self.name = str(self.root.resolve())

    def describe(self):
        return f"the folder {self.root}"

    def _p(self, key):
        return self.root.joinpath(*key.split("/"))

    def _meta(self, key):
        return Path(str(self.root.joinpath(".meta", *key.split("/"))) + ".json")

    def list(self, prefix):
        base = self._p(prefix.rstrip("/"))
        out = {}
        if not base.is_dir():
            return out
        for dirpath, _, names in os.walk(base):
            for n in names:
                f = Path(dirpath) / n
                out[f.relative_to(self.root).as_posix()] = f.stat().st_size
        return out

    def head(self, key):
        if not self._p(key).exists():
            return None
        try:
            return json.loads(self._meta(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def put_file(self, src, key, meta):
        dst = self._p(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
        m = self._meta(key)
        m.parent.mkdir(parents=True, exist_ok=True)
        m.write_text(json.dumps(meta), encoding="utf-8")

    def get_file(self, key, dst):
        shutil.copyfile(self._p(key), dst)

    def copy(self, src, dst):
        d = self._p(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._p(src), d)
        if self._meta(src).exists():
            self._meta(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self._meta(src), self._meta(dst))

    def delete(self, key):
        self._p(key).unlink(missing_ok=True)
        self._meta(key).unlink(missing_ok=True)

    def get_bytes(self, key):
        try:
            return self._p(key).read_bytes()
        except FileNotFoundError:
            return None

    def put_bytes(self, key, data):
        dst = self._p(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dst)


class NotAsked(FolderBucket):
    """For a --dry-run on a machine that cannot reach the bucket yet: an empty
    bucket, so the run can still show everything a first upload would send."""

    kind = "none"

    def __init__(self, why):
        self.why = why
        self.name = ""

    def describe(self):
        return f"the bucket (not asked: {self.why})"

    def list(self, prefix):
        return {}

    def head(self, key):
        return None

    def get_bytes(self, key):
        return None


class R2Bucket:
    """Cloudflare R2 through its S3 endpoint. boto3 is imported here and
    nowhere else, so every other command, preflight included, runs without it."""
    kind = "r2"

    def __init__(self, cfg, workers, quick=False):
        # quick: one small object, sent by refusal.note() as a fetch gives up,
        # which should hear "unreachable" in seconds rather than after ten
        # retries of five minutes each.
        _PRIVATE.extend(v for v in (cfg["account"], cfg["key_id"], cfg["secret"])
                        if len(v) >= 6)
        try:
            import boto3
            from boto3.s3.transfer import TransferConfig
            from botocore.config import Config
            from botocore.exceptions import ClientError
        except ImportError:
            raise Failed("cloud.py needs boto3 to reach R2: python3 -m pip install "
                         "boto3. --local-bucket FOLDER tests without it.")
        self.ClientError = ClientError
        # A large file goes up in four parts at once, beside the other workers.
        kw = dict(retries={"max_attempts": 2 if quick else 10, "mode": "standard"},
                  max_pool_connections=workers * 4 + 4,
                  connect_timeout=10 if quick else 30, read_timeout=30 if quick else 300,
                  signature_version="s3v4")
        try:
            # botocore 1.36 began sending checksums R2 did not accept at first;
            # asking for them only when an operation requires one works with
            # both.
            conf = Config(request_checksum_calculation="when_required",
                          response_checksum_validation="when_required", **kw)
        except TypeError:
            conf = Config(**kw)
        self.s3 = boto3.client(
            "s3", endpoint_url=f"https://{cfg['account']}.r2.cloudflarestorage.com",
            aws_access_key_id=cfg["key_id"], aws_secret_access_key=cfg["secret"],
            region_name="auto", config=conf)
        self.bucket = self.name = cfg["bucket"]
        # R2 wants every part but the last the same size, which this gives.
        self.tc = TransferConfig(multipart_threshold=64 * MB,
                                 multipart_chunksize=64 * MB, max_concurrency=4)

    def describe(self):
        return f"the R2 bucket {self.bucket}"

    def _missing(self, e):
        err = getattr(e, "response", {}) or {}
        return (err.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound")
                or err.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404)

    def list(self, prefix):
        out = {}
        pages = self.s3.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix)
        for page in pages:
            for o in page.get("Contents") or []:
                out[o["Key"]] = o["Size"]
        return out

    def head(self, key):
        try:
            got = self.s3.head_object(Bucket=self.bucket, Key=key)
        except self.ClientError as e:
            if self._missing(e):
                return None
            raise
        return dict(got.get("Metadata") or {})

    def put_file(self, src, key, meta):
        self.s3.upload_file(str(src), self.bucket, key,
                            ExtraArgs={"Metadata": meta}, Config=self.tc)

    def get_file(self, key, dst):
        self.s3.download_file(self.bucket, key, str(dst), Config=self.tc)

    def copy(self, src, dst):
        self.s3.copy({"Bucket": self.bucket, "Key": src}, self.bucket, dst,
                     Config=self.tc)

    def delete(self, key):
        self.s3.delete_object(Bucket=self.bucket, Key=key)

    def get_bytes(self, key):
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.ClientError as e:
            if self._missing(e):
                return None
            raise

    def put_bytes(self, key, data):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)


def make_bucket(local_bucket, workers, quick=False):
    """A folder standing in for the bucket, or R2 through keys.r2() -- never R2
    while NO_BUCKET is set, which preflight sets for everything it runs."""
    if local_bucket:
        return FolderBucket(local_bucket)
    if os.environ.get(NO_BUCKET):
        raise Failed(f"{NO_BUCKET} is set (preflight sets it for everything it runs), so "
                     "nothing here reaches the real bucket; --local-bucket FOLDER does")
    import keys
    return R2Bucket(keys.r2(), workers, quick=quick)


def home(root):
    """Whether root is the repository that holds secrets.json -- the one
    whose refusals are the real ones, and whose pull records a read of the
    real bucket. A temp folder with a stand-down file in it is not, and
    neither is a checkout with no secrets.json in it: keys.PATH names the
    file at the checkout's root whether it is there or not, so a worktree or
    a fresh clone would otherwise count as home."""
    import keys
    p = Path(keys.PATH)
    return p.exists() and Path(root).resolve() == p.resolve().parent


def open_bucket(a, preview=False):
    """The bucket named on the command line or by keys.r2(). With preview, a
    dry run that cannot reach it compares with an empty bucket and says so.
    A dry run's folder bucket is not created."""
    if a.local_bucket:
        return FolderBucket(a.local_bucket, create=not getattr(a, "dry_run", False))
    try:
        return make_bucket(None, a.workers)
    except (Failed, SystemExit) as e:
        if preview and a.dry_run:
            msg = str(e)
            return NotAsked("no R2 credentials here" if "R2_" in msg else
                            "boto3 is not installed" if "boto3" in msg else
                            msg.splitlines()[0][:80])
        raise Failed(str(e))


# ------------------------------------------------------- what the bucket holds --

def read_manifest(bucket, name):
    """(doc, raw) for the bucket's manifest; (None, None) when it has none."""
    key = MANIFEST.format(name)
    try:
        raw = bucket.get_bytes(key)
    except Exception as e:                                      # noqa: BLE001
        raise Failed(f"could not read {key} from {bucket.describe()}: "
                     f"{type(e).__name__}: {e}")
    if raw is None:
        return None, None
    try:
        doc = json.loads(raw.decode("utf-8"))
        if not isinstance(doc.get("files"), dict):
            raise ValueError("no files table")
    except (ValueError, AttributeError) as e:
        raise Failed(f"{key} in {bucket.describe()} will not read ({e}); nothing "
                     "was changed")
    return doc, raw


class Replacer:
    """Copies an object to replaced/<date>/<prefix>/<path> before it is
    overwritten or removed. A path replaced twice in a day keeps both: the
    second copy takes the time as a suffix rather than overwrite the first."""

    def __init__(self, bucket, day):
        self.bucket, self.day = bucket, day
        self.stamp = datetime.now().strftime("%H%M%S")
        self.taken = set(bucket.list(f"replaced/{day}/"))
        self.lock = threading.Lock()
        self.n = 0

    def keep(self, key):
        dst = f"replaced/{self.day}/{key}"
        with self.lock:
            if dst in self.taken:
                dst = f"{dst}~{self.stamp}"
            self.taken.add(dst)
        self.bucket.copy(key, dst)
        with self.lock:
            self.n += 1
        return dst


def write_manifest(bucket, name, changes, removed, by, replacer, keep_old=True):
    """Merge this run's changes into the bucket's manifest as it stands NOW,
    so what another machine recorded meanwhile is kept, and put it back. The
    copy it replaces goes to replaced/ like anything else -- except a
    checkpoint's, which only ever adds to the one it replaces."""
    cur, raw = read_manifest(bucket, name)
    files = dict((cur or {}).get("files", {}))
    files.update(changes)
    for p in removed:
        files.pop(p, None)
    doc = {"prefix": name, "written": datetime.now().isoformat(timespec="seconds"),
           "by": by, "count": len(files),
           "bytes": sum(e["size"] for e in files.values()),
           "files": dict(sorted(files.items()))}
    key = MANIFEST.format(name)
    if raw is not None and keep_old:
        replacer.keep(key)
    bucket.put_bytes(key, json.dumps(doc, indent=0).encode("utf-8"))
    return doc


# -------------------------------------------------------------- transfers --

class Progress:
    def __init__(self, what, n, total):
        self.what, self.n, self.total = what, n, total
        self.done = self.bytes = 0
        self.t0 = self.last = time.time()
        self.lock = threading.Lock()

    def tick(self, size):
        with self.lock:
            self.done += 1
            self.bytes += size
            now = time.time()
            if now - self.last < 30:
                return
            self.last = now
            done, got = self.done, self.bytes
            rate = got / max(1.0, now - self.t0)
        left = (self.total - got) / rate if rate else 0
        say(f"  {self.what} {done:,} of {self.n:,} files, {human(got)} of "
            f"{human(self.total)}, {human(rate)}/s"
            + (f", about {left / 3600:.1f} h left" if left > 5400 else
               f", about {left / 60:.0f} min left" if left > 90 else ""))


class Checkpoint:
    """Records each file as it lands, and writes the manifest every
    CHECKPOINT seconds, so an interrupted run resumes rather than restarts."""

    def __init__(self, bucket, name, by, replacer, base=None):
        self.bucket, self.name, self.by, self.replacer = bucket, name, by, replacer
        self.done = dict(base or {})
        self.lock = threading.Lock()
        self.last = time.time()
        self.writing = False
        self.first = True

    def __call__(self, rel, ent):
        with self.lock:
            self.done[rel] = ent
            if self.writing or time.time() - self.last < CHECKPOINT:
                return
            self.writing = True
            snap, first = dict(self.done), self.first
        try:
            write_manifest(self.bucket, self.name, snap, [], self.by + " (in progress)",
                           self.replacer, keep_old=first)
            with self.lock:
                self.first = False
        except Exception as e:                                  # noqa: BLE001
            say(f"  (progress not recorded this time: {type(e).__name__}: {e})")
        finally:
            with self.lock:
                self.last, self.writing = time.time(), False


def send(bucket, root, prefix, todo, remote_keys, replacer, workers, record=None):
    """Upload {rel: entry} under prefix/, keeping any object it replaces.
    Returns ({rel: entry} sent, [failures])."""
    sent, bad = {}, []
    lock = threading.Lock()
    prog = Progress("sent", len(todo), sum(e["size"] for e in todo.values()))

    def one(item):
        rel, ent = item
        key = f"{prefix}/{rel}"
        try:
            src = local(root, rel)
            st = src.stat()
            if st.st_size != ent["size"] or st.st_mtime_ns != ent["mtime_ns"]:
                raise OSError("it changed while this ran; the next run sends it")
            if key in remote_keys:
                replacer.keep(key)
            bucket.put_file(src, key, {"sha256": ent["sha256"],
                                       "mtime_ns": str(ent["mtime_ns"])})
        except Exception as e:                                  # noqa: BLE001
            with lock:
                bad.append(f"{rel}: {type(e).__name__}: {e}")
            return
        with lock:
            sent[rel] = ent
        prog.tick(ent["size"])
        if record:
            record(rel, ent)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, sorted(todo.items())))
    return sent, bad


def resumed(bucket, prefix, entries, known, remote_keys):
    """Objects in the bucket the manifest does not know, left by a run that
    stopped before it recorded them. Where one holds the same bytes -- its own
    sha256 says so -- it is recorded, not sent again, and not moved to
    replaced/ as though it were something older."""
    have = {}
    for rel, ent in entries.items():
        key = f"{prefix}/{rel}"
        if rel in known or remote_keys.get(key) != ent["size"]:
            continue
        if (bucket.head(key) or {}).get("sha256") == ent["sha256"]:
            have[rel] = ent
    return have


def diff(entries, known, have, prefix, remote_keys):
    """(to send, unchanged): a file is unchanged when what the bucket holds
    under its key has its size and sha256. A manifest entry whose object has
    gone from the bucket is sent again rather than trusted."""
    todo, same = {}, []
    for rel, ent in entries.items():
        was = have.get(rel) or (known.get(rel) if f"{prefix}/{rel}" in remote_keys
                                else None)
        if was and was["sha256"] == ent["sha256"] and was["size"] == ent["size"]:
            same.append(rel)
        else:
            todo[rel] = ent
    return todo, same


# ----------------------------------------------------------------- guards --

class machine_lock:
    """One cloud.py at a time on a machine: two would each write a manifest
    from what they alone had seen."""

    def __init__(self, root):
        self.path = local(root, LOCK)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and time.time() - self.path.stat().st_mtime < 180:
            held = self.path.read_text(encoding="utf-8", errors="replace").strip()
            raise Failed(f"{LOCK} is held ({held}): another cloud.py is running "
                         "here. Wait for it.")
        self.path.write_text(f"pid {os.getpid()} since {datetime.now():%H:%M}",
                             encoding="utf-8")
        self.stop = threading.Event()

        def beat():
            while not self.stop.wait(60):
                try:
                    os.utime(self.path, None)
                except OSError:
                    pass
        threading.Thread(target=beat, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.path.unlink(missing_ok=True)
        return False


def quiet_disk(root):
    """A build or a nightly rewriting the outputs right now would have this
    send a file half written. build_all touches .build.lock every 30 seconds
    and nightly.py holds .nightly.lock for the night."""
    for name, live in ((".build.lock", 180), (".nightly.lock", 6 * 3600)):
        p = local(root, name)
        if p.exists() and time.time() - p.stat().st_mtime < live:
            raise Failed(f"{name} is fresh: a build or a nightly is writing the "
                         "files this would send. Run this when it has finished.")


def removal_ok(n, total, allow):
    return allow or n <= max(1, min(REMOVE_MAX, int(total * REMOVE_SHARE)))


def show(label, rels, sizes, limit=8):
    if not rels:
        return
    say(f"  {label}: {len(rels):,} files, {human(sum(sizes.get(r, 0) for r in rels))}")
    for r in sorted(rels)[:limit]:
        say(f"      {r}")
    if len(rels) > limit and limit:
        say(f"      ... and {len(rels) - limit:,} more")


def sizes_of(entries):
    return {r: e["size"] for r, e in entries.items()}


# --------------------------------------------------------------- commands --

def cmd_kit_list(a, root):
    kit = load_kit(root)
    files, missing, held = kit_files(root, kit)
    sizes = {p: local(root, p).stat().st_size for p in files}
    for p in sorted(files):
        print(f"{sizes[p]}\t{p}" if a.sizes else p)
    err = sys.stderr
    if a.sizes:
        for e in kit["kit"]:
            mine = [p for p in files if entry_matches(e, p)]
            print(f"  {len(mine):>7,} files {human(sum(sizes[p] for p in mine)):>12}  "
                  f"[{e['owner']}] {e['what'][:72]}", file=err)
    print(f"kit: {len(files):,} files, {human(sum(sizes.values()))} "
          f"({sum(1 for o in files.values() if o == 'night'):,} the night's, "
          f"{sum(1 for o in files.values() if o == 'laptop'):,} the laptop's)",
          file=err, flush=True)
    if held:
        print(f"  {len(held):,} matched and held back by the never list: "
              + ", ".join(held[:5]), file=err)
    if missing:
        raise Failed(f"{len(missing)} entr{'y' if len(missing) == 1 else 'ies'} of "
                     f"{KIT_FILE} match nothing here: {', '.join(missing[:8])}")


def cmd_seed_kit(a, root):
    kit = load_kit(root)
    quiet_disk(root)
    files, missing, _ = kit_files(root, kit)
    if missing:
        raise Failed(f"not sending a partial kit: {', '.join(missing[:8])} "
                     f"{'is' if len(missing) == 1 else 'are'} missing here, and a kit "
                     "without them builds a smaller site that passes its own checks.")
    bucket = open_bucket(a, preview=True)
    hashes = Hashes(root)
    say(f"seed-kit: {len(files):,} files in {KIT_FILE}; reading them")
    entries, bad = hash_all(hashes, sorted(files), a.workers, "kit files")
    hashes.save()
    if bad:
        raise Failed(f"{len(bad)} kit files would not read: {'; '.join(bad[:4])}")
    man, _ = read_manifest(bucket, "kit")
    known = (man or {}).get("files", {})
    remote = bucket.list("kit/")
    have = resumed(bucket, "kit", entries, known, remote)
    todo, same = diff(entries, known, have, "kit", remote)
    # The night's own files: sent while the bucket's kit has none, never over
    # a copy the kit records -- which, after the first night, is the night's.
    kept = [r for r in todo if files[r] == "night" and r in known
            and f"kit/{r}" in remote]
    for r in kept:
        todo.pop(r)
    # --only: the files it names and nothing else, as laptop_evening.py sends
    # the caption results. Every other change here waits, and its copy in the
    # bucket, and its manifest entry, stand.
    held = []
    if getattr(a, "only", None):
        pats = [glob_re(g) for g in a.only]
        held = [r for r in todo if not any(p.match(r) for p in pats)]
        for r in held:
            todo.pop(r)
    elsewhere = [r for r in known if r not in entries]
    total = sum(e["size"] for e in entries.values())
    say(f"  {'first seed of' if man is None else 'the kit is already in'} "
        f"{bucket.describe()}: {len(entries):,} files, {human(total)} here")
    sz = sizes_of(entries)
    show("to send", list(todo), sz)
    show("unchanged, not sent", same, sz, limit=0)
    show("the night's own; its copy in the bucket stands", kept, sz)
    show("changed here and not named by --only; its copy in the bucket stands", held, sz)
    show("in the bucket's kit and not here; left as they are", elsewhere,
         {r: known[r]["size"] for r in elsewhere})
    if a.dry_run:
        say(f"--dry-run: nothing sent. {len(todo):,} files, "
            f"{human(sum(e['size'] for e in todo.values()))} would go to kit/ in "
            f"{bucket.describe()}.")
        return
    day = f"{datetime.now():%Y-%m-%d}"
    rep = Replacer(bucket, day)
    ck = Checkpoint(bucket, "kit", "seed-kit", rep, base=have)
    sent, fails = send(bucket, root, "kit", todo, remote, rep, a.workers, record=ck)
    doc = write_manifest(bucket, "kit", {**have, **sent}, [], "seed-kit", rep,
                         keep_old=ck.first)
    say(f"seed-kit: sent {len(sent):,} files, "
        f"{human(sum(e['size'] for e in sent.values()))}; {len(same):,} unchanged; "
        f"{len(kept):,} left as the night has them; {rep.n:,} older copies kept "
        f"under replaced/{day}/")
    say(f"  {MANIFEST.format('kit')}: {doc['count']:,} files, {human(doc['bytes'])}")
    if fails:
        raise Failed(f"{len(fails)} of {len(todo):,} files did not send, so the kit "
                     f"in the bucket is short: {'; '.join(fails[:4])}. Run seed-kit "
                     "again: what did send is recorded and will not go twice.")


def cmd_kit_down(a, root):
    kit = load_kit(root)
    bucket = open_bucket(a)
    man, _ = read_manifest(bucket, "kit")
    if man is None:
        raise Failed(f"{bucket.describe()} has no {MANIFEST.format('kit')}: the "
                     "laptop's seed-kit has not run, so there is no kit to take.")
    want = man["files"]
    # What the kit's definition requires and the bucket does not hold is the
    # same partial kit as a failed download, and is found before one.
    short = []
    for e in kit.get("kit", []):
        if e.get("optional"):
            continue
        short += [p for p in e.get("paths", []) if p not in want]
        short += [g for g in e.get("globs", [])
                  if not any(glob_re(g).match(p) for p in want)]
    rec_path = local(root, KIT_RECORD)
    prev = {}
    if rec_path.exists():
        try:
            prev = json.loads(rec_path.read_text(encoding="utf-8")).get("files", {})
        except (OSError, ValueError):
            prev = {}
    todo, here, clash = {}, [], []
    for rel, ent in want.items():
        f = local(root, rel)
        if not f.exists():
            todo[rel] = ent
            continue
        sha = sha256_of(f)
        if sha == ent["sha256"] and f.stat().st_size == ent["size"]:
            here.append(rel)
        elif rel in prev and prev[rel][1] == sha:
            todo[rel] = ent             # an earlier kit-down's copy: safe to replace
        else:
            clash.append(rel)           # this machine's own: left alone
    total = sum(e["size"] for e in want.values())
    say(f"kit-down: {len(want):,} files, {human(total)} in kit/ of "
        f"{bucket.describe()}; {len(todo):,} to fetch, {len(here):,} already here")
    if a.dry_run:
        say(f"--dry-run: nothing fetched. {len(todo):,} files, "
            f"{human(sum(e['size'] for e in todo.values()))} would come down; "
            f"{len(clash):,} here differ from the kit; the definition requires "
            f"{len(short):,} the bucket lacks.")
        return
    got, bad = set(), []
    lock = threading.Lock()
    prog = Progress("fetched", len(todo), sum(e["size"] for e in todo.values()))

    def one(item):
        rel, ent = item
        dst = local(root, rel)
        tmp = dst.with_name(dst.name + ".part")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            bucket.get_file(f"kit/{rel}", tmp)
            size, sha = tmp.stat().st_size, sha256_of(tmp)
            if size != ent["size"] or sha != ent["sha256"]:
                raise OSError(f"arrived as {size:,} bytes, sha256 {sha[:12]}; the "
                              f"manifest says {ent['size']:,}, {ent['sha256'][:12]}")
            os.replace(tmp, dst)
            ns = int(ent.get("mtime_ns") or 0)
            if ns:
                os.utime(dst, ns=(ns, ns))
        except Exception as e:                                  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            with lock:
                bad.append(f"{rel}: {type(e).__name__}: {e}")
            return
        with lock:
            got.add(rel)
        prog.tick(size)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(one, sorted(todo.items())))
    # THE RECORD: what arrived, which kit-up compares the night's files with,
    # and which build_all.py reads as "this folder is built from the kit".
    now = datetime.now()
    arrived = {r: [want[r]["size"], want[r]["sha256"], int(want[r].get("mtime_ns") or 0)]
               for r in sorted(set(here) | got)}
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(json.dumps({
        "at": now.isoformat(timespec="seconds"), "date": f"{now:%Y-%m-%d}",
        "epoch": time.time(), "manifest_written": man.get("written"),
        "files": arrived}), encoding="utf-8")
    say(f"kit-down: fetched {len(got):,} files, {human(sum(want[r]['size'] for r in got))}; "
        f"{len(here):,} were already here; every one checked against its size and "
        "sha256")
    problems = []
    if bad:
        problems.append(f"{len(bad)} files did not arrive whole: {'; '.join(bad[:4])}.")
    if clash:
        problems.append(f"{len(clash)} files here differ from the kit and were left "
                        f"as they are, kit-down being for an empty machine: "
                        f"{', '.join(clash[:4])}.")
    if short:
        problems.append(f"{KIT_FILE} requires {', '.join(short[:6])}, and the "
                        "bucket's kit holds none of it: run seed-kit on the laptop.")
    if problems:
        raise Failed("THE KIT IS SHORT. " + " ".join(problems)
                     + " A partial kit builds a smaller site that passes its own checks.")


def log_files(root, kit, since):
    never = never_rx(kit)
    out = set()
    for g in (kit.get("logs") or {}).get("globs", []):
        for rel in expand(root, g):
            if not any(rx.match(rel) for rx in never) \
                    and local(root, rel).stat().st_mtime >= since - 1:
                out.add(rel)
    return sorted(out)


def put_logs(bucket, root, logs, day, sub=None):
    """The logs to logs/<day>/, or a dry night's to logs/<day>/<sub>/."""
    sent, bad = [], []
    folder = f"logs/{day}/{sub}/" if sub else f"logs/{day}/"
    existing = bucket.list(folder)
    stamp = datetime.now().strftime("%H%M%S")
    for rel in logs:
        key = f"{folder}{rel.rsplit('/', 1)[-1]}"
        if key in existing:
            key = f"{key}~{stamp}"
        try:
            bucket.put_file(local(root, rel), key, {})
            sent.append(rel)
        except Exception as e:                                  # noqa: BLE001
            bad.append(f"{rel} (log): {type(e).__name__}: {e}")
    return sent, bad


def state_present(root, kit):
    return [s for s in kit.get("state", []) if local(root, s["path"]).is_file()]


def _sha(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def load_state_record(root):
    """What the bucket held of each state file when this machine last took
    them down or sent them: {"files": {key: sha256 or None}, "cleared": {...}},
    or None when this machine has no such record."""
    try:
        d = json.loads(local(root, STATE_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("files"), dict) else None


def save_state_record(root, rec):
    p = local(root, STATE_RECORD)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec["at"] = datetime.now().isoformat(timespec="seconds")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def state_up(bucket, root, kit, rep, day, only=None):
    """Send each state file this machine changed, and nothing it merely holds.
    `only`, a dry night's: the keys it may send, and no other is even read.

    ONE WRITER, AGAIN. Both machines hold these files, and a copy taken down
    last night is not news: sent back, it would put last night's census over
    tonight's. So a file goes up where the bucket holds none, or where it
    changed here since this machine took it down and did not change in the
    bucket. Where both changed, the bucket's stands and this machine's is
    kept under replaced/<day>/state-conflict/ -- a failure, except for a
    refusal on both sides, which is one fact however it arrived. A file
    cleared from the bucket by a person is never sent back, and one absent
    here is never removed there: a refusal is cleared by a person, not by a
    machine that happens not to hold it. Returns (sent, bytes, unchanged,
    notes, failures).
    """
    rec = load_state_record(root)
    base = dict((rec or {}).get("files", {}))
    cleared = dict((rec or {}).get("cleared", {}))
    n = size = same = 0
    notes, bad = [], []
    for s in state_present(root, kit):
        key, obj = s["key"], f"state/{s['key']}"
        if only is not None and key not in only:
            continue
        try:
            data = local(root, s["path"]).read_bytes()
            mine = _sha(data)
            old = bucket.get_bytes(obj)
            theirs = _sha(old)
            if theirs == mine:
                same += 1
                base[key] = mine
                continue
            if cleared.get(key) == mine:
                notes.append(f"{s['path']} is the {key} a person cleared from the "
                             "bucket, and is not sent back")
                continue
            known = rec is not None and key in base
            was = base.get(key) if known else None
            if old is None:
                if known and was is not None and was == mine:
                    notes.append(f"{s['path']} was removed from the bucket after this "
                                 "machine took it down, and is not sent back")
                    continue
            elif not known:
                bad.append(f"{obj}: the bucket holds another copy and this machine "
                           "has no record of taking it down; run state-down first")
                continue
            elif mine == was:
                notes.append(f"{obj}: the bucket's is newer than this machine's copy, "
                             "which is left as it is")
                continue
            elif theirs != was:
                kept = f"replaced/{day}/state-conflict/{key}"
                bucket.put_bytes(kept, data)
                if key == "refused.json":
                    notes.append(f"a refusal is on file in the bucket and here; the "
                                 f"bucket's stands, this machine's is at {kept}")
                else:
                    bad.append(f"{obj} changed in the bucket and here since this "
                               f"machine took it down; the bucket's stands, this "
                               f"machine's is at {kept}")
                continue
            if old is not None:
                rep.keep(obj)
            bucket.put_bytes(obj, data)
            base[key] = mine
            n += 1
            size += len(data)
        except Exception as e:                                  # noqa: BLE001
            bad.append(f"{obj}: {type(e).__name__}: {e}")
    save_state_record(root, {"files": base, "cleared": cleared})
    return n, size, same, notes, bad


def cmd_kit_up(a, root):
    kit = load_kit(root)
    rec_path = local(root, KIT_RECORD)
    if not rec_path.exists():
        raise Failed(f"no {KIT_RECORD}: kit-up sends what changed since kit-down, "
                     "and this machine has no record of a kit-down.")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    before = rec.get("files", {})
    day = rec.get("date") or f"{datetime.now():%Y-%m-%d}"
    files, _, _ = kit_files(root, kit)
    bucket = open_bucket(a)
    hashes = Hashes(root)
    # Unchanged since kit-down, by size and date, needs no reading.
    entries, maybe = {}, []
    for rel in sorted(files):
        st = local(root, rel).stat()
        b = before.get(rel)
        if b and b[0] == st.st_size and b[2] == st.st_mtime_ns:
            entries[rel] = {"size": b[0], "sha256": b[1], "mtime_ns": b[2]}
        else:
            maybe.append(rel)
    got, bad = hash_all(hashes, maybe, a.workers, "changed files")
    entries.update(got)
    if bad:
        raise Failed(f"{len(bad)} kit files would not read: {'; '.join(bad[:4])}")
    changed = [r for r, e in entries.items()
               if r not in before or before[r][1] != e["sha256"]]
    night = [r for r in changed if files[r] == "night"]
    theirs = [r for r in changed if files[r] == "laptop"]
    gone = [r for r in before if r not in files and not local(root, r).exists()
            and owner_of(kit, r) == "night"]
    # --hold RUN, a New term run's: what the night changed waits under
    # nights/RUN/kit/ and kit/ keeps the copies it had, until kit-release.
    hold = getattr(a, "hold", None)
    waiting, gone_waiting = [], []
    if hold:
        hprefix, hkey = _held_keys(hold)
        waiting = [r for r in night if held_back(kit, r)]
        night = [r for r in night if r not in waiting]
        gone_waiting = [r for r in gone if held_back(kit, r)]
        gone = [r for r in gone if r not in gone_waiting]
    # A DRY RUN SENDS BACK ONLY WHAT IT FETCHED (the docstring): the rest of
    # what it changed is its branch's code's work, and stays out of kit/.
    dry = dry_night(a)
    kept_back, unserved, gone_left = [], [], []
    held_off = None
    if dry:
        if hold:
            # A NEW TERM RUN TICKED WITH DRY RUN -- the Dry run box is ticked
            # unless a person unticks it -- gets --hold from the workflow, and
            # nightly.py refuses it before it asks for anything. Nothing is
            # held, and nothing of the kit goes back for it, not even a day
            # file: only its logs, apart, and a dry run's state. (Until the
            # review of 7 October 2026 this failed, and the refused run's logs
            # never reached the bucket.)
            held_off, hold = hold, None
            night, gone = night + waiting, gone + gone_waiting
            waiting, gone_waiting = [], []
        archived = [glob_re(g) for g in (kit.get("dry_run") or {}).get("globs", [])]
        sendable = [] if held_off else [r for r in night if dry_sends(kit, root, r, before)]
        unserved = [r for r in night if r not in sendable and any(x.match(r) for x in archived)]
        kept_back = [r for r in night if r not in sendable and r not in unserved]
        night, gone_left, gone = sendable, gone, []
    man, _ = read_manifest(bucket, "kit")
    cur = (man or {}).get("files", {})
    # The bucket's copy must still be the one this machine took down -- or
    # already be this very file, from a kit-up of the same night that is
    # being run again. Anything else is another writer's.
    there = {r: (cur.get(r) or {}).get("sha256") for r in night}
    already = [r for r in night if there[r] == entries[r]["sha256"]]
    conflict = [r for r in night if r not in already
                and there[r] != (before[r][1] if r in before else None)]
    night = [r for r in night if r not in conflict and r not in already]
    since = max(rec.get("epoch") or 0, rec.get("logs_sent") or 0)
    logs = log_files(root, kit, since)
    here_state = state_present(root, kit)
    sz = sizes_of(entries)
    say(f"kit-up: {len(files):,} kit files here; {len(changed):,} changed or new "
        f"since kit-down at {rec.get('at', '?')}")
    show("the night's, to send", night, sz)
    show("the laptop's, changed here and not sent: the laptop owns them", theirs, sz)
    show("changed in the bucket since kit-down; its copy stands and this "
         "machine's goes to replaced/", conflict, sz)
    show("the night's, gone since kit-down", gone, {r: before[r][0] for r in gone})
    if hold:
        say(f"  --hold {hold}: a New term run. What it changed stays out of kit/ until "
            f"its build is published (kit-release --run {hold})")
        show(f"the night's, to wait under {hprefix}/", waiting, sz)
        show("the night's, gone since kit-down; the removal waits too", gone_waiting,
             {r: before[r][0] for r in gone_waiting})
    if dry:
        say("  a dry run: only what it fetched goes back -- the archive's copies of what the "
            f"export served tonight, each read against its name -- and its logs go to "
            f"logs/{day}/{DRY_LOGS}/; of the state only "
            + (", ".join((kit.get("dry_run") or {}).get("state", [])) or "nothing"))
        if held_off:
            say(f"  --hold {held_off} on a dry run: a New term run ticked with Dry run, which "
                "nightly.py refuses, so nothing is held and nothing of the kit goes back")
        show("kept back: what the run's own code made or chose -- the day's files it "
             "installed, the archive's index and day records, the outputs a build carries -- "
             "which main's next night would read", kept_back, sz)
        show("kept back: archive copies kit-down brought, or whose bytes are not what their "
             "names say", unserved, sz)
        show("gone since kit-down, and left in kit/: a dry run removes nothing", gone_left,
             {r: before[r][0] for r in gone_left})
    say(f"  logs for logs/{day}/{DRY_LOGS + '/' if dry else ''}: {len(logs):,} files, "
        f"{human(sum(local(root, r).stat().st_size for r in logs))}; state files "
        f"here: {len(here_state)}")
    if not removal_ok(len(gone) + len(gone_waiting), len(before), a.allow_removals):
        raise Failed(f"{len(gone) + len(gone_waiting):,} of the night's kit files are gone since kit-down, "
                     "more than a night removes. Nothing was sent. "
                     "--allow-removals if it is meant.")
    if a.dry_run:
        say(f"--dry-run: nothing sent. {len(night):,} files, "
            f"{human(sum(sz[r] for r in night))} would go to kit/; {len(gone):,} "
            f"would move to replaced/; {len(logs):,} logs; state compared and sent "
            "where it differs."
            + (f" {len(waiting):,} files, {human(sum(sz[r] for r in waiting))} would "
               f"wait under {hprefix}/." if hold else ""))
        return
    rep = Replacer(bucket, day)
    remote = bucket.list("kit/")
    sent, fails = send(bucket, root, "kit", {r: entries[r] for r in night}, remote,
                       rep, a.workers)
    for r in conflict:
        try:
            bucket.put_file(local(root, r), f"replaced/{day}/kit-conflict/{r}",
                            {"sha256": entries[r]["sha256"],
                             "mtime_ns": str(entries[r]["mtime_ns"])})
        except Exception as e:                                  # noqa: BLE001
            fails.append(f"{r} (the conflicting copy): {type(e).__name__}: {e}")
    removed = []
    for r in gone:
        try:
            if f"kit/{r}" in remote:
                rep.keep(f"kit/{r}")
                bucket.delete(f"kit/{r}")
            removed.append(r)
        except Exception as e:                                  # noqa: BLE001
            fails.append(f"{r} (moving to replaced/): {type(e).__name__}: {e}")
    held = None
    if hold:
        # The waiting files, each under the run's own prefix, then the record
        # of them -- written only when every one arrived, so that kit-release
        # never moves half a night into kit/. kit/ and its manifest are not
        # touched for any of them, and neither is this machine's record of
        # what it took down: they are not in the kit.
        there_h = bucket.list(f"nights/{hold}/")
        want = {r: entries[r] for r in waiting}
        have = [r for r, e in want.items()
                if there_h.get(f"{hprefix}/{r}") == e["size"]
                and (bucket.head(f"{hprefix}/{r}") or {}).get("sha256") == e["sha256"]]
        hsent, hfail = send(bucket, root, hprefix,
                            {r: e for r, e in want.items() if r not in have},
                            there_h, rep, a.workers)
        fails += [f"{f} (to wait under {hprefix}/)" for f in hfail]
        if not hfail:
            held = {"run": hold, "day": day,
                    "written": datetime.now().isoformat(timespec="seconds"),
                    "files": dict(sorted(want.items())),
                    "base": {r: (before[r][1] if r in before else None)
                             for r in sorted(set(want) | set(gone_waiting))},
                    "removed": sorted(gone_waiting)}
            try:
                if hkey in there_h:
                    rep.keep(hkey)
                bucket.put_bytes(hkey, json.dumps(held, indent=1).encode("utf-8"))
            except Exception as e:                              # noqa: BLE001
                held = None
                fails.append(f"{hkey}: {type(e).__name__}: {e}")
    doc = write_manifest(bucket, "kit", sent, removed, "kit-up", rep)
    # What this machine now holds in common with the bucket: a second kit-up
    # the same night starts from here, not from what came down.
    for r, e in list(sent.items()) + [(r, entries[r]) for r in already]:
        before[r] = [e["size"], e["sha256"], e["mtime_ns"]]
    for r in removed:
        before.pop(r, None)
    rec["files"] = before
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    lsent, lfail = put_logs(bucket, root, logs, day, DRY_LOGS if dry else None)
    if not lfail:
        rec["logs_sent"] = time.time()
        rec_path.write_text(json.dumps(rec), encoding="utf-8")
    sn, sbytes, ssame, snotes, sfail = state_up(
        bucket, root, kit, rep, day,
        only=(kit.get("dry_run") or {}).get("state", []) if dry else None)
    fails += lfail + sfail
    for note in snotes:
        say(f"  state: {note}")
    say(f"kit-up: sent {len(sent):,} files, "
        f"{human(sum(e['size'] for e in sent.values()))}; moved {len(removed):,} to "
        f"replaced/; {len(lsent):,} logs, "
        f"{human(sum(local(root, r).stat().st_size for r in lsent))}; {sn} state "
        f"files sent, {ssame} unchanged, {human(sbytes)}; {rep.n:,} older copies "
        f"kept under replaced/{day}/")
    say(f"  {MANIFEST.format('kit')}: {doc['count']:,} files, {human(doc['bytes'])}")
    if dry:
        say(f"  a dry run: {len(kept_back) + len(unserved):,} changed files kept back, "
            f"{len(gone_left):,} gone and left in kit/")
    if hold:
        say(f"  held for run {hold}: " + (
            f"{len(held['files']):,} files, "
            f"{human(sum(e['size'] for e in held['files'].values()))}, wait under "
            f"{hprefix}/ and are not in kit/; {hkey} lists them"
            + (f", and {len(held['removed']):,} removals" if held["removed"] else "")
            if held is not None else
            f"NOT RECORDED. {hkey} was not written, so kit-release has nothing to release"))
    if fails or conflict:
        raise Failed(
            (f"{len(fails)} did not send: {'; '.join(fails[:4])}. " if fails else "")
            + (f"{len(conflict)} kit file(s) changed in the bucket after this machine "
               f"took them down, which is two writers for one file: "
               f"{', '.join(conflict[:4])}. The bucket's copy stands; this machine's "
               f"is under replaced/{day}/kit-conflict/." if conflict else ""))


def cmd_state_up(a, root):
    kit = load_kit(root)
    here = state_present(root, kit)
    # A dry night's: only a refusal, a hold and its own verdict (the docstring).
    only = (kit.get("dry_run") or {}).get("state", []) if dry_night(a) else None
    if only is not None:
        here = [s for s in here if s["key"] in only]
        say("state-up: a dry run, so only " + (", ".join(only) or "nothing")
            + " may go; never the census, the night's verdict, the week's or the "
              "first-seen ledger")
    bucket = open_bucket(a)
    if a.dry_run:
        say(f"--dry-run: nothing sent. {len(here)} state files here would be "
            f"compared with state/ and sent where they differ: "
            + (", ".join(s["path"] for s in here) or "none"))
        return
    day = f"{datetime.now():%Y-%m-%d}"
    rep = Replacer(bucket, day)
    n, size, same, notes, bad = state_up(bucket, root, kit, rep, day, only=only)
    for note in notes:
        say(f"  {note}")
    unsent = unsent_after(bucket, root)
    if unsent:
        bad.append(unsent)
    say(f"state-up: {len(here)} state files here; sent {n}, {human(size)}; {same} "
        f"unchanged; {rep.n} older copies kept under replaced/")
    if bad:
        raise Failed(f"{len(bad)} state files did not send: {'; '.join(bad)}")


def write_unsent(root, why):
    """archive/cloud/refusal-unsent.json, saying why the refusal on file here
    is not in the bucket -- the shape refusal.tell_the_bucket writes."""
    p = local(root, UNSENT)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "epoch": time.time(),
                             "refusal": "archive/refused.json", "why": str(why)[:300]},
                            indent=1), encoding="utf-8")


def _who(doc):
    return f"{doc.get('where') or '?'} at {doc.get('at') or '?'}"


def unsent_after(bucket, root):
    """The sentence for a refusal met here that the bucket was never told of,
    or "". The marker goes once the bucket holds THIS refusal, or there is
    none here any more. While the bucket holds another one it stays, and is
    said, but is no failure: the night stops at any refusal the bucket holds,
    so this one waits behind it rather than being lost -- until a person
    lifts that one, when send-refusal sends this."""
    marker = local(root, UNSENT)
    if not marker.exists():
        return ""
    here = local(root, _refusal_entry(load_kit(root))["path"])
    mine = here.read_bytes() if here.exists() else None
    theirs = bucket.get_bytes("state/refused.json")
    cleared = ((load_state_record(root) or {}).get("cleared") or {}).get("refused.json")
    if mine is None or (theirs is not None and theirs == mine) or cleared == _sha(mine):
        marker.unlink(missing_ok=True)
        say(f"  {UNSENT}: " + ("there is no refusal on file here any more" if mine is None else
                               "the bucket holds this refusal, so the night stops at it"
                               if theirs == mine else
                               "a person cleared this refusal from the bucket")
            + "; the marker is lifted")
        return ""
    if theirs is not None:
        say(f"  {UNSENT} stays: this machine's refusal ({_who(_refusal_doc(mine))}) waits "
            f"behind the one the bucket holds ({_who(_refusal_doc(theirs))}), which stops the "
            "night until a person lifts it; then python3 src/ops/cloud.py send-refusal sends this one")
        return ""
    return (f"{UNSENT} says a refusal met here never reached the bucket, and the bucket "
            "still holds none, so GitHub's night would ask the General Court: python3 "
            "src/ops/cloud.py send-refusal")


def cmd_state_down(a, root):
    """Each state file the bucket holds comes down, and what it held is
    recorded for state-up. One the bucket lacks is left alone here: an absence
    is not an instruction to delete. One changed here since the last
    state-down, and not yet sent, is left as well: taking the bucket's over it
    would lose what this machine wrote."""
    kit = load_kit(root)
    bucket = open_bucket(a)
    rec = load_state_record(root)
    base = dict((rec or {}).get("files", {}))
    n, size, same, absent, kept, bad = 0, 0, 0, [], [], []
    for s in kit.get("state", []):
        key = s["key"]
        try:
            data = bucket.get_bytes(f"state/{key}")
        except Exception as e:                                  # noqa: BLE001
            bad.append(f"state/{key}: {type(e).__name__}: {e}")
            continue
        dst = local(root, s["path"])
        if data is None:
            absent.append(key)
            if not a.dry_run:
                base[key] = None
            continue
        here = dst.read_bytes() if dst.exists() else None
        if here == data:
            same += 1
            base[key] = _sha(data)
            continue
        if here is not None and rec is not None and _sha(here) != base.get(key):
            kept.append(s["path"])
            continue
        if a.dry_run:
            say(f"  would take state/{key} -> {s['path']}, {human(len(data))}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dst)
        base[key] = _sha(data)
        n += 1
        size += len(data)
    if not a.dry_run:
        save_state_record(root, {"files": base,
                                 "cleared": dict((rec or {}).get("cleared", {}))})
    say(f"state-down{' --dry-run, nothing taken' if a.dry_run else ''}: took {n} "
        f"state files, {human(size)}; {same} already here"
        + (f"; the bucket holds no {', '.join(absent)}" if absent else "")
        + (f"; left {', '.join(kept)} as this machine changed it, for state-up"
           if kept else ""))
    if bad:
        raise Failed(f"{len(bad)} state files could not be read: {'; '.join(bad)}")


def cmd_clear_refusal(a, root):
    """Lift the refusal record the nightly's machine keeps in the bucket.

    refusal.py --clear lifts this machine's archive/refused.json. The nightly
    starts empty and takes its refusal record from the bucket's
    state/refused.json, so after the move that copy is the one that stops a
    night, and it outlives any machine. This moves it to replaced/, never
    deletes it, and records that it was cleared, so no state-up sends the same
    refusal back. Clearing it is a person's decision, after netcheck.py.

    It exits 1 when the refusal it cleared had a newer one of this laptop's
    waiting behind it -- one still in force, or one the unsent marker names:
    the bucket then holds no refusal at all, and the night would ask the
    address this laptop was refused by until send-refusal sends it. The
    clearing stands; the status is so a person, or the morning triage, does
    not read the run as the end of the matter.
    """
    kit = load_kit(root)
    entry = next((s for s in kit.get("state", []) if s["key"] == "refused.json"), None)
    if entry is None:
        raise Failed(f"{KIT_FILE} names no refused.json in its state list")
    bucket = open_bucket(a)
    obj = "state/refused.json"
    data = bucket.get_bytes(obj)
    here = local(root, entry["path"])
    mine = here.read_bytes() if here.exists() else None

    def about_here():
        # A refusal this machine holds that the bucket does not is the one
        # clearing the bucket's can lose: the night would stop at neither.
        if mine is None:
            return
        if data is not None and mine == data:
            say(f"  this machine still holds the same refusal at {entry['path']}: python3 "
                "refusal.py --clear lifts it here")
            return
        say(f"  THIS MACHINE HOLDS A REFUSAL THE BUCKET DOES NOT ({_who(_refusal_doc(mine))}), "
            f"at {entry['path']}. Clearing the bucket's does not lift it, and GitHub's night "
            f"will not stop at it until it is sent: python3 src/ops/cloud.py send-refusal"
            + (" (this machine's is newer than the one cleared, and was waiting behind it)"
               if data is not None and float(_refusal_doc(mine).get("epoch") or 0)
               > float(_refusal_doc(data).get("epoch") or 0) else "")
            + ". python3 refusal.py --clear lifts it here instead, if a person has decided "
              "it is over.")

    if data is None:
        say("clear-refusal: the bucket holds no refusal (state/refused.json); "
            "nothing to clear there")
    elif a.dry_run:
        say(f"--dry-run: state/refused.json ({human(len(data))}) would move to "
            "replaced/; nothing moved")
        about_here()
        return
    else:
        day = f"{datetime.now():%Y-%m-%d}"
        moved = Replacer(bucket, day).keep(obj)
        bucket.delete(obj)
        say(f"clear-refusal: state/refused.json ({human(len(data))}) moved to "
            f"{moved}; nothing in the bucket stops a fetch now")
    rec = load_state_record(root) or {"files": {}}
    rec["files"]["refused.json"] = None
    if data is not None:
        rec.setdefault("cleared", {})["refused.json"] = _sha(data)
    save_state_record(root, rec)
    about_here()
    if data is not None and mine is not None and mine != data:
        import refusal
        m, t = _refusal_doc(mine), _refusal_doc(data)
        newer = float(m.get("epoch") or 0) > float(t.get("epoch") or 0)
        marker = local(root, UNSENT).exists()
        if marker or (newer and refusal.hours_left(m) is not None):
            raise Failed(f"the bucket's refusal ({_who(t)}) is lifted, and this machine's "
                         f"({_who(m)}), which was waiting behind it"
                         + (f" ({UNSENT} names it)" if marker else
                            ", is newer and still in force")
                         + ", is not in the bucket: GitHub's night would ask the address this "
                           "machine was refused by. Send it: python3 src/ops/cloud.py send-refusal "
                           "(or python3 refusal.py --clear here, if a person has decided it "
                           "is over)")


def _refusal_entry(kit):
    entry = next((s for s in kit.get("state", []) if s["key"] == "refused.json"), None)
    if entry is None:
        raise Failed(f"{KIT_FILE} names no refused.json in its state list")
    return entry


def send_refusal(root, local_bucket=None, dry_run=False):
    """This machine's refusal record to the bucket's state/refused.json, when
    the bucket holds none, so GitHub's night stops at it too. (done, the
    sentence to print); Failed when it could not be sent.

    done is True when nothing is left to send: the bucket holds this refusal
    (sent now, or before), there is none here, or it is the one a person
    cleared from the bucket (clear-refusal records it, and it is never sent
    back). It is False while the bucket holds ANOTHER refusal: that one stops
    the night already, and is never overwritten from here, so this one waits
    behind it -- the unsent marker stays, saying so, until the bucket holds
    this refusal or a person lifts it here. Giving up there, as this once
    did, lost a newer laptop refusal the moment a person cleared the
    bucket's older one.

    refusal.note() calls this on a stood-down laptop, the moment a fetch meets
    a refusal; `cloud.py send-refusal` is the same by hand. The real bucket
    only from the repository that holds secrets.json (home()): a refusal
    recorded in a test's temp folder beside a stand-down file must never
    reach the night, so anywhere else needs a folder bucket.
    """
    root = Path(root)
    kit = load_kit(root)
    entry = _refusal_entry(kit)
    src, marker = local(root, entry["path"]), local(root, UNSENT)
    if not src.exists():
        if not dry_run:
            marker.unlink(missing_ok=True)
        return True, f"no refusal on file here ({entry['path']}); nothing to send"
    data = src.read_bytes()
    mine = _sha(data)
    rec = load_state_record(root)
    if (rec or {}).get("cleared", {}).get("refused.json") == mine:
        if not dry_run:
            marker.unlink(missing_ok=True)
        return True, (f"{entry['path']} is the refusal a person cleared from the bucket with "
                      "clear-refusal, and is not sent back; python3 refusal.py --clear lifts "
                      "it here")
    if not local_bucket and not home(root):
        import keys
        raise Failed(f"{root.resolve()} is not the repository that holds secrets.json "
                     f"({Path(keys.PATH).resolve().parent}), so its refusal is not sent to the "
                     "real bucket: only that repository's refusals are the night's business. "
                     "A test gives a folder bucket (--local-bucket FOLDER, or "
                     "refusal.CLOUD_BUCKET)")
    obj = "state/refused.json"
    try:
        bucket = make_bucket(local_bucket, 1, quick=True)
        theirs = bucket.get_bytes(obj)
        if theirs is None and dry_run:
            return True, f"--dry-run: {entry['path']} would go to {obj} in {bucket.describe()}"
        if theirs is None:
            bucket.put_bytes(obj, data)
            if bucket.get_bytes(obj) != data:
                raise Failed(f"{obj} did not read back as it was sent")
    except Failed:
        raise
    except (Exception, SystemExit) as e:                        # noqa: BLE001
        raise Failed(scrub(f"{type(e).__name__}: {e}"))
    if theirs is not None and theirs != data:
        t, m = _refusal_doc(theirs), _refusal_doc(data)
        older = float(t.get("epoch") or 0) <= float(m.get("epoch") or 0)
        why = (f"waiting behind the bucket's older refusal ({_who(t)}), which stops the night "
               "until a person lifts it with python3 src/ops/cloud.py clear-refusal; python3 src/ops/cloud.py "
               "send-refusal then sends this one" if older else
               f"the bucket holds a newer refusal ({_who(t)}), which stops the night; python3 "
               "src/ops/cloud.py pull takes it here and sets this one aside")
        if not dry_run:
            write_unsent(root, why)
        return False, (f"{bucket.describe()} holds another refusal at {obj}, so this one "
                       f"({_who(m)}) is not sent over it: {why}")
    if theirs is None:
        rec = rec or {"files": {}, "cleared": {}}
        rec["files"]["refused.json"] = mine
        save_state_record(root, rec)
        said = f"sent to {obj} in {bucket.describe()}, and GitHub's night stops at it too"
    else:
        said = f"{bucket.describe()} already holds this refusal at {obj}"
    if not dry_run:
        marker.unlink(missing_ok=True)
    return True, said


def cmd_send_refusal(a, root):
    done, said = send_refusal(root, a.local_bucket, a.dry_run)
    say(f"send-refusal: {said}")
    if not done and not a.dry_run:
        raise Failed(f"not sent; {UNSENT} stays and says why, and pull, state-up and "
                     "preflight report it until the bucket holds this refusal or a person "
                     "lifts it here")


# THE NIGHT'S BUILT SITE, AS ONE FILE. The publish job runs on another
# machine and needs the night's site/. Handed over as a GitHub artifact it
# would be downloadable by anyone signed in to GitHub, the repository being
# public, and it carries the licensed logo. Sent as 55,000 objects it would be
# 55,000 billed writes a night. So it goes to the private bucket as one
# archive, nights/<run>/site.tar.gz, with nights/<run>/site.json beside it
# saying what it holds; the bucket's lifecycle rule deletes nights/ after a
# few days.
RUN_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _night_keys(run):
    if not run or not RUN_ID.match(run):
        raise Failed(f"--run {run!r} is not a run id (letters, digits, . _ -)")
    return f"nights/{run}/site.tar.gz", f"nights/{run}/site.json"


def _first_seen_key(run):
    """Where a night's first-seen ledger (FIRST_SEEN_NEXT) waits beside its site."""
    return f"nights/{run}/first-seen.json"


def _held_keys(run):
    """(prefix, record) for what a New term run's kit-up --hold keeps waiting:
    nights/<run>/kit/<path> for each file, nights/<run>/kit.json listing them."""
    if not run or not RUN_ID.match(run):
        raise Failed(f"{run!r} is not a run id (letters, digits, . _ -)")
    return f"nights/{run}/kit", f"nights/{run}/kit.json"


def cmd_kit_release(a, root):
    """What a New term run's night changed, into kit/, once that run's build
    is published: the publish job runs this after its deploy has landed.

    All of it or none. Each waiting file replaces the copy the night took
    down, and only that copy: if kit/ holds anything else for one of them --
    another night or the weekly job wrote it since -- nothing is released,
    because a kit of some of that night's files and some of a later one's is
    the kit of no night. The copy each replaces goes to replaced/ first, like
    anything else. Run again after a failure, it finds what is already in
    kit/ and moves the rest.
    """
    kit = load_kit(root)
    hprefix, hkey = _held_keys(a.run)
    bucket = open_bucket(a)
    raw = bucket.get_bytes(hkey)
    if raw is None:
        raise Failed(f"{bucket.describe()} has no {hkey}: kit-up --hold did not finish "
                     f"for run {a.run}, or the lifecycle rule has deleted what it held. "
                     "Nothing was released, so the next night still compares with the "
                     "kit as it was; a new New term run is the way forward.")
    try:
        doc = json.loads(raw.decode("utf-8"))
        held, base = doc["files"], doc.get("base") or {}
        removed = list(doc.get("removed") or [])
        if not isinstance(held, dict) or not isinstance(base, dict) or not all(
                isinstance(e, dict) and isinstance(e.get("sha256"), str)
                and isinstance(e.get("size"), int) for e in held.values()):
            raise ValueError("not a record of held files")
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise Failed(f"{hkey} will not read ({e}); nothing was released")
    never = never_rx(kit)
    for rel in list(held) + removed:
        check_rel(rel)
        if not held_back(kit, rel) or any(rx.match(rel) for rx in never):
            raise Failed(f"{hkey} names {rel}, which {KIT_FILE} does not hold back for "
                         "a New term run; nothing was released")
    man, _ = read_manifest(bucket, "kit")
    if man is None:
        raise Failed(f"{bucket.describe()} has no {MANIFEST.format('kit')}; nothing "
                     "was released")
    cur = man["files"]
    remote = bucket.list("kit/")
    waits = bucket.list(f"{hprefix}/")
    todo, already, clash, short = {}, [], [], []
    for rel, ent in sorted(held.items()):
        there = (cur.get(rel) or {}).get("sha256")
        if there == ent["sha256"] and f"kit/{rel}" in remote:
            already.append(rel)
        elif there != base.get(rel):
            clash.append(rel)
        elif waits.get(f"{hprefix}/{rel}") != ent["size"] or                 (bucket.head(f"{hprefix}/{rel}") or {}).get("sha256") != ent["sha256"]:
            short.append(rel)
        else:
            todo[rel] = ent
    drop = []
    for rel in removed:
        if rel not in cur:
            continue
        if cur[rel].get("sha256") != base.get(rel):
            clash.append(rel)
        else:
            drop.append(rel)
    say(f"kit-release: run {a.run} holds {len(held):,} files, "
        f"{human(sum(e['size'] for e in held.values()))}, under {hprefix}/ of "
        f"{bucket.describe()}; {len(todo):,} to move into kit/, {len(already):,} "
        f"already there, {len(drop):,} to remove")
    if clash or short:
        raise Failed(
            "NOTHING WAS RELEASED. "
            + (f"kit/ no longer holds the copy run {a.run} took down of "
               f"{', '.join(clash[:6])}: another night or the weekly job has written "
               "there since, and one file has one writer. " if clash else "")
            + (f"{', '.join(short[:6])} {'is' if len(short) == 1 else 'are'} not under "
               f"{hprefix}/ as {hkey} records. " if short else "")
            + "The next night still compares with the kit as it was, and refuses the "
              "smaller files; a new New term run is the way forward.")
    if a.dry_run:
        say(f"--dry-run: nothing moved. {len(todo):,} files, "
            f"{human(sum(e['size'] for e in todo.values()))} would go into kit/.")
        return
    day = f"{datetime.now():%Y-%m-%d}"
    rep = Replacer(bucket, day)
    done, gone, fails = {}, [], []
    for rel, ent in todo.items():
        try:
            if f"kit/{rel}" in remote:
                rep.keep(f"kit/{rel}")
            bucket.copy(f"{hprefix}/{rel}", f"kit/{rel}")
            done[rel] = ent
        except Exception as e:                                  # noqa: BLE001
            fails.append(f"{rel}: {type(e).__name__}: {e}")
    for rel in drop:
        try:
            if f"kit/{rel}" in remote:
                rep.keep(f"kit/{rel}")
                bucket.delete(f"kit/{rel}")
            gone.append(rel)
        except Exception as e:                                  # noqa: BLE001
            fails.append(f"{rel} (moving to replaced/): {type(e).__name__}: {e}")
    mdoc = write_manifest(bucket, "kit", done, gone, f"kit-release {a.run}", rep)
    say(f"kit-release: moved {len(done):,} files, "
        f"{human(sum(e['size'] for e in done.values()))}, into kit/; {len(already):,} "
        f"were already there; removed {len(gone):,}; {rep.n:,} older copies kept under "
        f"replaced/{day}/")
    say(f"  {MANIFEST.format('kit')}: {mdoc['count']:,} files, {human(mdoc['bytes'])}")
    if fails:
        raise Failed(f"{len(fails)} of {len(todo) + len(drop):,} did not move, so kit/ "
                     f"holds part of run {a.run}'s night: {'; '.join(fails[:4])}. Run "
                     "kit-release again: what did move is recorded and is not moved twice.")


def _site_dir(root, name):
    try:
        return local(root, check_rel(name))
    except Failed:
        raise Failed(f"--site {name!r} is not a plain relative folder")


def _site_files(site):
    out = []
    for dirpath, _, names in os.walk(site):
        for nm in names:
            p = Path(dirpath) / nm
            out.append((p.relative_to(site).as_posix(), p))
    return sorted(out)


def dry_by_workflow():
    """Whether the workflow says this run is a dry run (DRY_ENV), or it is not
    a run of main (REF_ENV is not MAIN_REF exactly: another branch, a case
    variant of main, or no ref at all), on GitHub's machine --
    nightly.dry_by_workflow()'s rule, and nightly.py says why missing is not
    main (MAIN IS MAIN_REF EXACTLY)."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return False
    return os.environ.get(DRY_ENV) == "true" or os.environ.get(REF_ENV) != MAIN_REF


def _night_verdict(root, run):
    """The verdict the night of run `run` wrote (NIGHT_VERDICT), which goes
    with its site: a dict naming that run and not a dry run's, or Failed.
    The publish job deploys a run's own build by its own verdict, so a site
    never travels without it."""
    p = local(root, NIGHT_VERDICT)
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Failed(f"{NIGHT_VERDICT} will not read ({type(e).__name__}): the site goes up with "
                     "its night's verdict, and there is none here")
    if not isinstance(v, dict) or str(v.get("run_id") or "") != run:
        raise Failed(f"{NIGHT_VERDICT} is the verdict of run "
                     f"{(v.get('run_id') if isinstance(v, dict) else None) or '(none)'}, not run "
                     f"{run}: the site goes up with its own night's verdict, or not at all")
    if (v.get("asked") or {}).get("dry_run"):
        raise Failed(f"{NIGHT_VERDICT} is a dry run's, and a dry run sends no site for production")
    return v


def cmd_site_up(a, root):
    import tarfile
    key, meta_key = _night_keys(a.run)
    if dry_by_workflow():
        raise Failed("the workflow says this run is a dry run, and a dry run sends no site for "
                     "production")
    site = _site_dir(root, a.site)
    files = _site_files(site) if site.is_dir() else []
    if not files:
        raise Failed(f"no built site in {a.site}/ to send")
    verdict = _night_verdict(root, a.run)
    total = sum(p.stat().st_size for _, p in files)
    ledger = local(root, FIRST_SEEN_NEXT)
    ledger = ledger.read_bytes() if ledger.is_file() else None
    say(f"site-up: {a.site}/ holds {len(files):,} files, {human(total)}, and run {a.run}'s "
        f"verdict goes with them"
        + (f", and the first-seen ledger its build left ({FIRST_SEEN_NEXT})" if ledger else ""))
    if a.dry_run:
        say(f"--dry-run: nothing sent. They would go as one archive to {key}.")
        return
    bucket = open_bucket(a)
    tmp = local(root, f"{LOCAL}/site-{a.run}.tar.gz")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(tmp, "w:gz", compresslevel=6) as tf:
            for rel, p in files:
                tf.add(p, arcname=rel, recursive=False)
        size, sha = tmp.stat().st_size, sha256_of(tmp)
        remote = bucket.list(f"nights/{a.run}/")
        rep = Replacer(bucket, f"{datetime.now():%Y-%m-%d}")
        for k in (key, meta_key, _first_seen_key(a.run)):
            if k in remote:
                rep.keep(k)
        bucket.put_file(tmp, key, {"sha256": sha, "files": str(len(files))})
        got = bucket.list(f"nights/{a.run}/").get(key)
        if got != size:
            raise Failed(f"{key} arrived as {got} bytes, not {size:,}")
        if ledger is not None:
            bucket.put_bytes(_first_seen_key(a.run), ledger)
        bucket.put_bytes(meta_key, json.dumps({
            "run": a.run, "files": len(files), "bytes": total, "size": size,
            "sha256": sha, "written": datetime.now().isoformat(timespec="seconds"),
            "verdict": verdict,
            "first_seen": ({"size": len(ledger), "sha256": hashlib.sha256(ledger).hexdigest()}
                           if ledger is not None else None),
        }, indent=1).encode("utf-8"))
    finally:
        tmp.unlink(missing_ok=True)
    say(f"site-up: {len(files):,} files, {human(total)}, sent as one archive of "
        f"{human(size)} to {key}")


def cmd_site_down(a, root):
    import tarfile
    key, meta_key = _night_keys(a.run)
    bucket = open_bucket(a)
    raw = bucket.get_bytes(meta_key)
    if raw is None:
        raise Failed(f"{bucket.describe()} has no {meta_key}: no site was sent for "
                     f"run {a.run}, or the lifecycle rule has deleted it")
    meta = json.loads(raw.decode("utf-8"))
    verdict = meta.get("verdict")
    if not isinstance(verdict, dict) or str(verdict.get("run_id") or "") != a.run:
        raise Failed(f"{meta_key} carries no verdict of run {a.run}: the site was sent without "
                     "its own night's verdict, and the publish job deploys a run's own build by "
                     "that verdict and no other")
    site = _site_dir(root, a.site)
    if site.exists() and any(site.iterdir()):
        raise Failed(f"{a.site}/ is not empty here; site-down unpacks the night's "
                     "site into an empty folder, and nothing already here is "
                     "overwritten")
    say(f"site-down: run {a.run}'s site, {meta['files']:,} files, "
        f"{human(meta['bytes'])} in an archive of {human(meta['size'])}, with its verdict")
    if a.dry_run:
        say("--dry-run: nothing fetched.")
        return
    tmp = local(root, f"{LOCAL}/site-{a.run}.tar.gz")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        bucket.get_file(key, tmp)
        size, sha = tmp.stat().st_size, sha256_of(tmp)
        if size != meta["size"] or sha != meta["sha256"]:
            raise Failed(f"{key} arrived as {size:,} bytes, sha256 {sha[:12]}; "
                         f"{meta_key} says {meta['size']:,}, {meta['sha256'][:12]}")
        site.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tmp, "r:gz") as tf:
            tf.extractall(site, filter="data")
    finally:
        tmp.unlink(missing_ok=True)
    files = _site_files(site)
    total = sum(p.stat().st_size for _, p in files)
    if len(files) != meta["files"] or total != meta["bytes"]:
        raise Failed(f"the site unpacked as {len(files):,} files, {human(total)}; "
                     f"{meta_key} says {meta['files']:,}, {human(meta['bytes'])}")
    # The first-seen ledger the night's build left, where nightly.py keeps it
    # once a New term run's deploy has landed; whole, or not at all.
    led = meta.get("first_seen")
    if isinstance(led, dict):
        raw = bucket.get_bytes(_first_seen_key(a.run))
        if raw is None or len(raw) != led.get("size") or \
                hashlib.sha256(raw).hexdigest() != led.get("sha256"):
            raise Failed(f"{_first_seen_key(a.run)} is missing or not the ledger {meta_key} "
                         "names")
        dst = local(root, FIRST_SEEN_NEXT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + ".part")
        part.write_bytes(raw)
        os.replace(part, dst)
        say(f"site-down: the first-seen ledger its build left, at {FIRST_SEEN_NEXT}")
    # Its own night's verdict, where --deploy-to production reads it: written
    # last, once the site is whole, so a verdict here always has its site.
    dst = local(root, SITE_VERDICT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    tmp.write_text(json.dumps(verdict, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, dst)
    say(f"site-down: {len(files):,} files, {human(total)} unpacked into {a.site}/, "
        f"every one accounted for; run {a.run}'s verdict at {SITE_VERDICT}")


def tracked_files(root):
    try:
        r = child.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True)
    except OSError as e:
        raise Failed(f"git will not run ({e}), so what git holds cannot be told "
                     "from what it does not")
    if r.returncode != 0:
        raise Failed(f"{root} is not a git checkout, so what git holds cannot be "
                     "told from what it does not")
    return {p for p in (r.stdout or "").split("\0") if p}


def backup_files(root, kit, with_site):
    """Everything here git does not track, less what the backup leaves out and
    what is never sent, as sorted /-paths."""
    tracked = tracked_files(root)
    leave = [g for grp in (kit.get("backup") or {}).get("leave_out", [])
             for g in grp["globs"] if not (with_site and g.startswith("site/"))]
    rxs = [glob_re(g) for g in leave + (kit.get("never") or {}).get("globs", [])]
    prune = [glob_re(g[:-3]) for g in leave if g.endswith("/**")]
    out, stack = [], [(Path(root), "")]
    while stack:
        d, rel = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            r = f"{rel}/{e.name}" if rel else e.name
            if e.is_dir(follow_symlinks=False):
                if not any(rx.match(r) for rx in prune):
                    stack.append((Path(e.path), r))
            elif e.is_file(follow_symlinks=False) and r not in tracked \
                    and not any(rx.match(r) for rx in rxs):
                out.append(r)
    return sorted(out)


def cmd_backup(a, root):
    kit = load_kit(root)
    quiet_disk(root)
    rels = backup_files(root, kit, a.with_site)
    bucket = open_bucket(a, preview=True)
    hashes = Hashes(root)
    say(f"backup: {len(rels):,} files here that git does not hold"
        + ("" if a.with_site else ", site/ left out") + "; reading them")
    entries, unread = hash_all(hashes, rels, a.workers, "files")
    hashes.save()
    man, _ = read_manifest(bucket, "backup")
    known = (man or {}).get("files", {})
    remote = bucket.list("backup/")
    have = resumed(bucket, "backup", entries, known, remote)
    todo, same = diff(entries, known, have, "backup", remote)
    # Gone from here since the last backup: moved to replaced/, never deleted,
    # and only below the share a real tidy-up reaches. site/ is not "gone"
    # when --with-site was simply not given, and a file that would not read
    # is not gone either.
    unread_rels = {u.split(": ", 1)[0] for u in unread}
    gone = [r for r in known if r not in entries and r not in unread_rels
            and not local(root, r).exists()
            and (a.with_site or not r.startswith("site/"))]
    total = sum(e["size"] for e in entries.values())
    say(f"  {'first backup to' if man is None else 'changes since the last backup to'} "
        f"{bucket.describe()}: {len(entries):,} files, {human(total)} here")
    sz = sizes_of(entries)
    show("to send", list(todo), sz)
    show("unchanged, not sent", same, sz, limit=0)
    show("gone from here since the last backup, to be moved to replaced/", gone,
         {r: known[r]["size"] for r in gone})
    if unread:
        say(f"  {len(unread):,} files would not read and are not sent: "
            + "; ".join(unread[:3]))
    if not removal_ok(len(gone), len(known), a.allow_removals):
        raise Failed(f"{len(gone):,} files the backup holds are gone from here, which "
                     "looks like the wrong folder or a missing disk rather than a "
                     "tidy-up. Nothing was sent or moved. --allow-removals if it is "
                     "meant.")
    if a.dry_run:
        say(f"--dry-run: nothing sent. {len(todo):,} files, "
            f"{human(sum(e['size'] for e in todo.values()))} would go to backup/ in "
            f"{bucket.describe()}; {len(gone):,} would move to replaced/.")
        return
    day = f"{datetime.now():%Y-%m-%d}"
    rep = Replacer(bucket, day)
    ck = Checkpoint(bucket, "backup", "backup", rep, base=have)
    sent, fails = send(bucket, root, "backup", todo, remote, rep, a.workers, record=ck)
    removed = []
    for r in gone:
        try:
            if f"backup/{r}" in remote:
                rep.keep(f"backup/{r}")
                bucket.delete(f"backup/{r}")
            removed.append(r)
        except Exception as e:                                  # noqa: BLE001
            fails.append(f"{r} (moving to replaced/): {type(e).__name__}: {e}")
    doc = write_manifest(bucket, "backup", {**have, **sent}, removed, "backup", rep,
                         keep_old=ck.first)
    say(f"backup: sent {len(sent):,} files, "
        f"{human(sum(e['size'] for e in sent.values()))}; {len(same):,} unchanged; "
        f"{len(removed):,} moved to replaced/; {rep.n:,} older copies kept under "
        f"replaced/{day}/")
    say(f"  {MANIFEST.format('backup')}: {doc['count']:,} files, {human(doc['bytes'])}")
    fails = unread + fails
    if fails:
        raise Failed(f"{len(fails)} files did not go, so the backup is short: "
                     f"{'; '.join(fails[:4])}. Run backup again: what did send is "
                     "recorded and will not go twice.")


# ------------------------------------------------------------------- pull ---
#
# The laptop takes back what the nights did. READ-ONLY TOWARDS THE BUCKET:
# nothing below puts, copies or deletes an object there, and preflight reads
# every function cmd_pull reaches to hold it to that.

def load_pull_record(root):
    try:
        d = json.loads(local(root, PULL_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def save_pull_record(root, rec):
    p = local(root, PULL_RECORD)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rec, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def write_whole(dst, data):
    """Bytes to a file, whole or not at all: beside it first, then renamed."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, dst)


def create_whole(dst, data):
    """Bytes to a file that must not exist yet, whole or not at all.
    FileExistsError, with nothing written, when one is there -- however late
    it arrived. Written beside it first and hard-linked into place, so the
    name appears only complete and only if it is free; where the disk cannot
    make a hard link, an O_EXCL create, which is exclusive though not whole."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    tmp.write_bytes(data)
    try:
        os.link(tmp, dst)
    except FileExistsError:
        raise
    except OSError:
        fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
    finally:
        tmp.unlink(missing_ok=True)


def set_aside(root, rel, day):
    """This machine's copy of rel, kept under archive/cloud/set-aside/<day>/
    before pull puts the bucket's in its place. Returns where."""
    dst = local(root, f"{SET_ASIDE}/{day}/{rel}")
    if dst.exists():
        dst = dst.with_name(f"{dst.name}~{datetime.now():%H%M%S}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local(root, rel), dst)
    return dst.relative_to(Path(root)).as_posix()


def pull_days(a, rec, today):
    """(days, note): the days whose logs this pull looks for -- --day, or from
    the day BEFORE the last pull's to today, at most PULL_DAYS of them -- and
    a sentence when the record needed correcting, or "".

    The day before, because a night's folder is named for the day it started
    in Eastern time, and a pull can run before that night has sent it: the
    weekly starts at 04:17 UTC on Monday, which in winter is 11:17 p.m. on
    Sunday, so a pull early on Monday records Monday as done while Sunday's
    folder is still to come. A day looked at twice costs a listing; the
    files already here are "already here". A through-date after today (a
    clock that was wrong, or a record from another machine) would make the
    range empty for as long as it stays ahead, so it is taken as today, and
    said."""
    from datetime import date, timedelta
    if a.day:
        try:
            return [date.fromisoformat(a.day).isoformat()], ""
        except ValueError:
            raise Failed(f"--day {a.day!r} is not a date (YYYY-MM-DD)")
    earliest = today - timedelta(days=PULL_DAYS - 1)
    key = "changes_through" if a.changes_only else "logs_through"
    last, note = rec.get(key), ""
    try:
        through = date.fromisoformat(last) if last else None
    except ValueError:
        through, note = None, f"the pull record's {key} ({last!r}) is not a date, and is ignored"
    if through and through > today:
        note = (f"the pull record says the last pull took them through {through}, which is "
                f"after today ({today}): this machine's clock, or the record, is wrong, so "
                "today is used")
        through = today
    start = max(earliest, through - timedelta(days=1)) if through else earliest
    return ([(start + timedelta(days=k)).isoformat() for k in range((today - start).days + 1)],
            note)


def _refusal_doc(data):
    try:
        d = json.loads(data.decode("utf-8"))
        return d if isinstance(d, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def pull_refusal(bucket, root, kit, dry, day):
    """The bucket's refusal record against this laptop's. ([lines], [failures],
    what the bucket holds). A refusal only ever arrives or stays here; the
    older of two is set aside, never dropped.

    What each stops is refusal.force()'s sentence, because three readers read
    one differently: check() for 24 hours, the lane and GitHub's night for as
    long as it is on file. And a refusal on this laptop the bucket holds none
    of is a FAILURE while it stands -- the night would ask the address this
    laptop was refused by -- unless it is the one a person cleared from the
    bucket. The unsent marker is lifted only once the bucket holds the
    refusal this laptop holds, or there is none here.

    Where the laptop holds none, the bucket's is CREATED here, never written
    over whatever is there by then (create_whole): a fetch's refusal.note()
    can record one between the look above and the write, and replacing it
    would lose the laptop's newest refusal. When one did arrive, the two are
    compared as any two are."""
    import refusal
    entry = _refusal_entry(kit)
    here_p, marker = local(root, entry["path"]), local(root, UNSENT)
    theirs = bucket.get_bytes("state/refused.json")
    mine = here_p.read_bytes() if here_p.exists() else None
    lines, bad = [], []
    if theirs is not None and mine is None and not dry:
        try:
            create_whole(here_p, theirs)
        except FileExistsError:
            mine = here_p.read_bytes()
            lines.append(f"a refusal was recorded here ({_who(_refusal_doc(mine))}) while this "
                         f"pull read the bucket's; it is not written over, and the two are "
                         "compared")
    t = _refusal_doc(theirs) if theirs is not None else {}
    held = ("none" if theirs is None else
            {"where": t.get("where"), "at": t.get("at"), "sha256": _sha(theirs)})
    what = _who(t)
    cleared = ((load_state_record(root) or {}).get("cleared") or {}).get("refused.json")
    after = mine                    # what this laptop holds once this pull is done
    told = False                    # a failure already names send-refusal
    if theirs is None and mine is None:
        lines.append("no refusal on file in the bucket or here")
    elif theirs is None:
        m = _refusal_doc(mine)
        if cleared == _sha(mine):
            lines.append(f"{entry['path']} ({_who(m)}) is on file here and the bucket holds "
                         "none: a person cleared this one from the bucket, and python3 "
                         "refusal.py --clear lifts it here")
        elif refusal.hours_left(m) is not None:
            told = True
            bad.append(f"THIS LAPTOP'S REFUSAL ({_who(m)}, {entry['path']}) IS NOT IN THE BUCKET, "
                       f"which holds none, so GitHub's night would still ask the address this "
                       f"laptop was refused by. python3 src/ops/cloud.py send-refusal sends it (to the "
                       f"bucket, not the General Court); python3 refusal.py --clear lifts it "
                       f"here, if a person has decided it is over")
        else:
            lines.append(f"{entry['path']} ({_who(m)}) is on file here and the bucket holds "
                         f"none. It is older than {refusal.QUIET_HOURS} hours, so hand fetches "
                         "here are not stopped by it; the lane here is, and GitHub's night "
                         "never sees it: python3 src/ops/cloud.py send-refusal sends it if it should "
                         "stop the night too, and python3 refusal.py --clear lifts it here")
    elif mine is None:
        after = theirs                  # created here above, unless dry
        lines.append(f"THE BUCKET HOLDS A REFUSAL ({what}): "
                     f"{'it would go' if dry else 'it is now'} on file here too, as "
                     f"{entry['path']}. It is {refusal.force(t)}. Lifting it is a person's "
                     "decision, after netcheck.py: python3 src/ops/cloud.py clear-refusal lifts the "
                     "bucket's and python3 refusal.py --clear this one; lifting only this one "
                     "brings it back at the next pull")
    elif mine == theirs:
        lines.append(f"the same refusal ({what}) is on file in the bucket and here. It is "
                     f"{refusal.force(t)}")
    else:
        m = _refusal_doc(mine)
        newer = float(t.get("epoch") or 0) > float(m.get("epoch") or 0)
        if newer:
            after = theirs
            kept = f"{SET_ASIDE}/{day}/{entry['path']}" if dry else set_aside(root, entry["path"], day)
            if not dry:
                write_whole(here_p, theirs)
            lines.append(f"the bucket's refusal ({what}) is newer than this laptop's "
                         f"({_who(m)}), and {'would take' if dry else 'takes'} its place here; "
                         f"this laptop's is kept at {kept}. It is {refusal.force(t)}")
        else:
            lines.append(f"this laptop's refusal ({_who(m)}) is newer than the bucket's ({what}) "
                         f"and stays. The bucket's is {refusal.force(t)}; this laptop's waits "
                         "behind it, and when a person lifts the bucket's, python3 src/ops/cloud.py "
                         "send-refusal sends this one")
    if marker.exists():
        lift = (after is None or (theirs is not None and after == theirs)
                or (theirs is None and cleared == _sha(after)))
        if lift:
            if not dry:
                marker.unlink(missing_ok=True)
            lines.append(f"{UNSENT}: " + ("there is no refusal here to send" if after is None else
                                          "a person cleared this one from the bucket"
                                          if theirs is None else
                                          "the bucket holds this laptop's refusal, so the night "
                                          "stops at it")
                         + f"; the marker {'would be' if dry else 'is'} lifted")
        elif theirs is not None:
            lines.append(f"{UNSENT} stays: this laptop's refusal is not the bucket's, and waits "
                         "behind it (above)")
        elif not told:
            bad.append(f"a refusal met on this laptop never reached the bucket ({UNSENT}), "
                       "which holds none, so GitHub's night would still ask the General "
                       "Court: python3 src/ops/cloud.py send-refusal")
    return lines, bad, held


def pull_livestream_state(bucket, root, kit, dry):
    """state/livestreams.json to where livestreams.py reads it. ([lines])

    The night's record of the recordings it has seen and of those still
    waiting for captions, which the laptop's `livestreams.py --catch-up`
    reads and never writes: the night is its one writer, and this copy is
    only ever replaced by the bucket's. Until 30 September 2026 no pull
    brought it, so the catch-up could not start on the laptop at all."""
    entry = next((s for s in kit.get("state", []) if s["key"] == "livestreams.json"), None)
    if entry is None:
        return []
    data = bucket.get_bytes(f"state/{entry['key']}")
    if data is None:
        return ["the livestream state: the bucket holds none"]
    dst = local(root, entry["path"])
    if dst.exists() and dst.read_bytes() == data:
        return ["the livestream state: already here"]
    if not dry:
        write_whole(dst, data)
    return [f"the livestream state: {'would come down' if dry else 'taken'} "
            f"({human(len(data))}) to {entry['path']}"]


def pull_verdicts(bucket, root, dry, today):
    """state/last-night.json, last-dry-run.json, last-weekly.json and
    last-dry-weekly.json to archive/cloud/. ([lines], taken).

    A night's verdict from before yesterday is STALE: the morning triage
    reading "CLEAN" off it would be reading about a night that is not the
    last one, because the nightly on GitHub has not sent a verdict since. A
    dry run's is kept apart from the night's (nightly.DRY_VERDICT) and said to
    be one, so that it is never read as the night's; it is never stale, since
    dry runs are started by hand, when there is something to try. A dry
    weekly's -- a run of the weekly off main -- is kept apart from the week's
    the same way, and said to be one (DRY_VERDICTS)."""
    from datetime import timedelta
    lines, taken = [], 0
    yesterday = (today - timedelta(days=1)).isoformat()
    for key, rel in VERDICTS.items():
        data = bucket.get_bytes(f"state/{key}")
        if data is None:
            lines.append(f"{key}: the bucket holds none")
            continue
        v = _refusal_doc(data)
        dst = local(root, rel)
        same = dst.exists() and dst.read_bytes() == data
        if not same and not dry:
            write_whole(dst, data)
        taken += 0 if same else 1
        stale = key == "last-night.json" and str(v.get("day") or "") < yesterday
        kind = DRY_VERDICTS.get(key) or v.get("kind") or "?"
        lines.append(("STALE -- the newest night's verdict is from before yesterday, so the "
                      "nightly on GitHub has not sent one since (its Actions tab says why): "
                      if stale else "")
                     + f"{key}: {kind} of {v.get('day') or '?'}, "
                     f"{'CLEAN' if v.get('clean') else 'NOT CLEAN'}"
                     + ("" if v.get("clean") else
                        " -- " + "; ".join(str(x) for x in (v.get("not_clean") or [])[:3]))
                     + (" -- with a warning: " + "; ".join(str(x) for x in v["warnings"][:2])
                        if v.get("clean") and v.get("warnings") else "")
                     + (f"; already at {rel}" if same else
                        f"; {'would go' if dry else 'now'} at {rel}"))
    return lines, taken


def pull_logs(bucket, root, kit, days, changes_only, known, take, dry, day):
    """The night's logs and change lists for `days`, from logs/<day>/.

    The newest copy of each name wins: kit-up sends a second one of a day under
    the name with ~HHMMSS after it. A local file of that name is replaced only
    when pull wrote it and it is unchanged since (`known`), or --take names it.
    Returns (taken {rel: sha256}, same {rel: sha256}, clashes, set aside,
    failures, other names left in the bucket, {rel: size} of what was taken).
    """
    never, want = never_rx(kit), set(days)
    groups, other = {}, 0
    for key, size in bucket.list("logs/").items():
        parts = key.split("/")
        if len(parts) != 3 or parts[1] not in want:
            continue
        base, _, stamp = parts[2].partition("~")
        folder = next((f for rx, f in PULL_LOGS if rx.match(base)), None)
        if folder is None:
            other += 1
            continue
        rel = f"{folder}/{base}"
        if (changes_only and not CHANGES.match(base)) or any(rx.match(rel) for rx in never):
            continue
        groups.setdefault(rel, []).append((stamp, key, size))
    taken, same, clash, aside, bad, sizes = {}, {}, [], [], [], {}
    for rel, variants in sorted(groups.items()):
        _, key, size = max(variants)
        try:
            data = bucket.get_bytes(key)
            if data is None or len(data) != size:
                raise OSError(f"arrived as {None if data is None else len(data)} bytes, "
                              f"not the {size:,} the listing says")
            sha, dst = _sha(data), local(root, rel)
            if dst.exists():
                here = sha256_of(dst)
                if here == sha:
                    same[rel] = sha
                    continue
                if known.get(rel) != here and rel not in take:
                    clash.append(rel)
                    continue
                if known.get(rel) != here and not dry:
                    aside.append(set_aside(root, rel, day))
            if not dry:
                write_whole(dst, data)
            taken[rel] = sha
            sizes[rel] = len(data)
        except Exception as e:                                  # noqa: BLE001
            bad.append(f"{key}: {type(e).__name__}: {e}")
    return taken, same, clash, aside, bad, other, sizes


def kit_history(bucket, today, days=35):
    """{path: {sha256, ...}}: every copy of each file the bucket's kit manifest
    has recorded -- the current manifest and the older ones kept under
    replaced/<day>/state/ (the lifecycle rule keeps them 30 days). Settles a
    night's file this laptop has no pull record of: a copy the bucket ever
    held is one the laptop sent or took, not one it changed."""
    from datetime import timedelta
    hist = {}

    def add(doc):
        for rel, e in ((doc or {}).get("files") or {}).items():
            hist.setdefault(rel, set()).add((e or {}).get("sha256"))
    add(read_manifest(bucket, "kit")[0])
    name = MANIFEST.format("kit").split("/", 1)[1]
    for k in range(days):
        d = f"{today - timedelta(days=k):%Y-%m-%d}"
        rx = re.compile(rf"^replaced/{d}/state/{re.escape(name)}(?:~\d+)?$")
        for key in bucket.list(f"replaced/{d}/state/"):
            if rx.match(key):
                try:
                    add(json.loads((bucket.get_bytes(key) or b"{}").decode("utf-8")))
                except (ValueError, UnicodeDecodeError):
                    pass
    return hist


def pull_kit(a, bucket, root, kit, known, take, day, today):
    """The night's kit files, down to this laptop where the bucket's differs
    and this laptop's copy is still the one it last had in common with the
    bucket. Returns a dict of what it found and did."""
    man, _ = read_manifest(bucket, "kit")
    if man is None:
        raise Failed(f"{bucket.describe()} has no {MANIFEST.format('kit')}: seed-kit has "
                     "not run, so there is no kit to take anything back from")
    never = never_rx(kit)
    night, r = {}, {"laptop": 0, "nobody": 0, "site": 0, "never": 0}
    for rel, ent in man["files"].items():
        owner = owner_of(kit, rel)
        if any(rx.match(rel) for rx in never):
            r["never"] += 1
        elif owner == "laptop":
            r["laptop"] += 1
        elif owner is None:
            r["nobody"] += 1
        elif rel.startswith(PULL_NOT):
            r["site"] += 1
        else:
            night[rel] = ent
    hashes = Hashes(root)
    todo, here, clash, unknown, bad = {}, [], [], [], []
    # (size, mtime_ns) of each file as it was judged -- None for one that was
    # not there -- so that one changed between then and its replacement is a
    # clash, not overwritten: the judging can take minutes on a large kit.
    pre = {}
    for rel, ent in sorted(night.items()):
        try:
            check_rel(rel)
            if not local(root, rel).exists():
                todo[rel] = ent
                pre[rel] = None
                continue
            cur = hashes.entry(rel)
        except (Failed, OSError) as e:
            bad.append(f"{rel}: {e}")
            continue
        pre[rel] = (cur["size"], cur["mtime_ns"])
        if cur["sha256"] == ent["sha256"] and cur["size"] == ent["size"]:
            here.append(rel)
        elif rel in known and known[rel][1] == cur["sha256"]:
            todo[rel] = ent
        elif rel in known:
            clash.append(rel)
        else:
            unknown.append((rel, cur["sha256"]))
    if unknown:
        hist = kit_history(bucket, today)
        for rel, sha in unknown:
            if sha in hist.get(rel, ()):
                todo[rel] = night[rel]
            else:
                clash.append(rel)
    taking = sorted(rel for rel in clash if rel in take)
    clash = sorted(rel for rel in clash if rel not in take)
    for rel in taking:
        todo[rel] = night[rel]
    gone = sorted(rel for rel in known if rel not in man["files"])
    r.update(todo=todo, here=here, clash=clash, taking=taking, gone=gone, got=set(),
             bad=bad, aside=[], night=len(night), moved=[])
    if a.dry_run:
        return r
    for rel in taking:
        r["aside"].append(set_aside(root, rel, day))
    lock = threading.Lock()
    prog = Progress("taken", len(todo), sum(e["size"] for e in todo.values()))

    def one(item):
        rel, ent = item
        dst = local(root, rel)
        tmp = dst.with_name(dst.name + ".part")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            bucket.get_file(f"kit/{rel}", tmp)
            size, sha = tmp.stat().st_size, sha256_of(tmp)
            if size != ent["size"] or sha != ent["sha256"]:
                raise OSError(f"arrived as {size:,} bytes, sha256 {sha[:12]}; the "
                              f"manifest says {ent['size']:,}, {ent['sha256'][:12]}")
            # Looked at again just before it is replaced: a file written here
            # since it was judged -- a build, an editor -- is this laptop's
            # change, and a clash like any other.
            try:
                st = dst.stat()
                now_is = (st.st_size, st.st_mtime_ns)
            except FileNotFoundError:
                now_is = None
            if now_is != pre.get(rel):
                tmp.unlink(missing_ok=True)
                with lock:
                    r["clash"].append(rel)
                    r["moved"].append(rel)
                return
            os.replace(tmp, dst)
            ns = int(ent.get("mtime_ns") or 0)
            if ns:
                os.utime(dst, ns=(ns, ns))
            st = dst.stat()
            with hashes.lock:
                hashes.seen[rel] = [st.st_size, st.st_mtime_ns, sha]
        except Exception as e:                                  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            with lock:
                r["bad"].append(f"{rel}: {type(e).__name__}: {e}")
            return
        with lock:
            r["got"].add(rel)
        prog.tick(size)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(one, sorted(todo.items())))
    hashes.save()
    for rel in here + sorted(r["got"]):
        known[rel] = [night[rel]["size"], night[rel]["sha256"]]
    for rel in gone:
        known.pop(rel, None)
    return r


def take_paths(root, raw):
    """--take's paths as the /-relative paths pull names clashes by.

    A person copies a path from pull's own message, from a listing or from
    Explorer, so .\\x, ./x, x\\y and an absolute path under the working folder
    are all the same file. Anything that is not a file in the working folder
    is refused, naming --take -- not cloud_kit.json, which check_rel names."""
    base = Path(root).resolve()
    out = set()
    for p in raw or []:
        q = p.strip()
        if Path(q).is_absolute() or re.match(r"^[A-Za-z]:", q):
            try:
                q = Path(q).resolve().relative_to(base).as_posix()
            except ValueError:
                raise Failed(f"--take {p!r} is not under the working folder {base}")
        q = q.replace("\\", "/")
        while q.startswith("./"):
            q = q[2:]
        try:
            out.add(check_rel(q))
        except Failed:
            raise Failed(f"--take {p!r} is not a path of a file in the working folder "
                         "(as pull names a clash: Docket.txt, logs/nightly-2026-09-26.log)")
    return out


def bucket_is_the_nights(bucket):
    """Whether the bucket holds what a night leaves: the kit manifest or a
    night's verdict. One with neither is empty, or not the night's, and
    reading "no refusal" from it proves nothing -- so pull stops before it
    reads the refusal record, and records no read."""
    for key in (MANIFEST.format("kit"), "state/last-night.json"):
        if bucket.head(key) is not None:
            return True
    return False


def full_pull_news(bucket, kit, rec, now):
    """--changes-only's word on everything else: how old the last FULL pull
    is, and how many of the night's files the bucket's kit manifest has
    changed since -- which a morning of changes-only pulls would otherwise
    leave unsaid while the laptop's copies of them grow old. Read-only: the
    manifest, and this laptop's pull record."""
    full = rec.get("full") or {}
    try:
        man = read_manifest(bucket, "kit")[0]
    except Failed as e:
        return [f"the bucket's kit manifest would not read ({e}), so what the nights changed "
                "since the last full pull is not known"]
    if man is None:
        return ["the bucket holds no kit manifest"]
    never, known = never_rx(kit), rec.get("kit") or {}
    night = {rel: e for rel, e in man["files"].items()
             if owner_of(kit, rel) == "night" and not rel.startswith(PULL_NOT)
             and not any(rx.match(rel) for rx in never)}
    newer = sorted(rel for rel, e in night.items()
                   if (known.get(rel) or [None, None])[1] != e.get("sha256"))
    if not full.get("epoch"):
        return [f"NO FULL PULL has run here: the night's {len(night):,} files in the bucket's "
                f"kit are not on this laptop as the nights left them ({len(newer):,} differ "
                "from anything pull brought). python3 src/ops/cloud.py pull brings them"]
    hours = (now.timestamp() - float(full["epoch"])) / 3600
    return [f"the last full pull was {hours:.0f} hours ago ({full.get('at') or '?'}); the "
            f"bucket's kit manifest has {len(newer):,} of the night's {len(night):,} files "
            "changed since"
            + (": python3 src/ops/cloud.py pull brings them" if newer else ", so nothing waits")
            + (". OLDER THAN 48 HOURS: preflight fails on it" if hours > 48 else "")]


def cmd_pull(a, root):
    """The laptop takes back what the nights changed. The module docstring says
    what comes down and where; this only ever reads the bucket."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise Failed("pull is the laptop's. On GitHub's machine, which starts empty, "
                     "state-down and kit-down are the commands.")
    # A FOLDER IS NOT THE BUCKET. Its read of the refusal record never counts
    # (refusal.refusal_read wants a read of R2), but a folder pull in the
    # repository whose fetches that record governs would still bring a test's
    # files over the laptop's real ones.
    if a.local_bucket and home(root) and (Path(root) / "archive/runs-in-the-cloud.json").exists() \
            and not a.allow_local_bucket:
        raise Failed("--local-bucket is a test, and this is the stood-down repository that "
                     "holds secrets.json: a folder's files and refusal record are not the "
                     "night's. Pull from the real bucket here, or test in another folder "
                     "(--root); --allow-local-bucket says a test here is meant")
    quiet_disk(root)
    kit = load_kit(root)
    bucket = open_bucket(a)
    rec = load_pull_record(root)
    now = datetime.now()
    today, day = now.date(), f"{now:%Y-%m-%d}"
    take = take_paths(root, a.take)
    days, note = pull_days(a, rec, today)
    mode = "--changes-only" if a.changes_only else "a full pull"
    say(f"pull{' --dry-run' if a.dry_run else ''}: {mode} from {bucket.describe()}, "
        f"logs of {days[0]}" + (f" to {days[-1]}" if len(days) > 1 else ""))
    if note:
        say(f"  ({note})")
    last = rec.get("changes_through" if a.changes_only else "logs_through")
    if not a.day and last and not note and last < days[0]:
        say(f"  (the last pull took them to {last}; days before {days[0]} are not looked "
            f"for, {PULL_DAYS} being the most one pull looks back. --day YYYY-MM-DD takes "
            "one of them; the bucket keeps a month)")
    if not bucket_is_the_nights(bucket):
        raise Failed(f"{bucket.describe()} holds neither {MANIFEST.format('kit')} nor "
                     "state/last-night.json: it is empty, or not the night's. Nothing was "
                     "taken, and its refusal record was not read or recorded, because \"no "
                     "refusal\" from a bucket the night never wrote to says nothing")
    failures, clashes = [], []

    # 1. THE REFUSAL, first and recorded at once: it is what a General Court
    # fetch on this laptop waits for, whatever happens to the rest. The time
    # recorded is taken before the read, so a read is never dated later than
    # it happened; and which bucket was read, because only a read of the real
    # one counts (refusal.refusal_read).
    read_at = time.time()
    lines, bad, held = pull_refusal(bucket, root, kit, a.dry_run, day)
    for ln in lines:
        say(f"  refusal: {ln}")
    failures += bad
    if not a.dry_run:
        rec["refusal"] = {"read": read_at, "at": now.isoformat(timespec="seconds"),
                          "kind": bucket.kind, "bucket": bucket.name, "holds": held}
        save_pull_record(root, rec)
        if bucket.kind != "r2":
            say(f"  refusal: read from {bucket.describe()}, which is not the real bucket, so "
                "it does not count as reading the night's refusal record")

    # 2. THE VERDICTS
    lines, n_verdicts = pull_verdicts(bucket, root, a.dry_run, today)
    for ln in lines:
        say(f"  verdict: {ln}")

    # 3. THE LOGS AND THE CHANGE LISTS
    files = rec.setdefault("files", {})
    taken, same, lclash, laside, lbad, other, lsizes = pull_logs(
        bucket, root, kit, days, a.changes_only, files, take, a.dry_run, day)
    if not a.dry_run:
        files.update(taken)
        files.update(same)
    show("logs and change lists " + ("that would come down" if a.dry_run else "taken"),
         list(taken), lsizes)
    for p in laside:
        say(f"  this laptop's copy kept at {p}")
    clashes += lclash
    failures += lbad
    changes = sorted(r for r in {**taken, **same} if r.startswith("reports/"))
    if not changes:
        say(f"  NO CHANGE LIST in the bucket for {days[0]}"
            + (f" to {days[-1]}" if len(days) > 1 else "")
            + ": no night installed the day's files then, or none has sent its logs yet. "
              "The verdict above says what the night did.")
    if not a.changes_only and not any(r.startswith("logs/nightly-") for r in {**taken, **same}):
        say(f"  NO NIGHTLY LOG in the bucket for {days[0]}"
            + (f" to {days[-1]}" if len(days) > 1 else "")
            + ": the night has not run since, or has not reached kit-up, which sends it")

    # 4. THE KIT -- or, for --changes-only, how far behind it this laptop is.
    k = None
    if a.changes_only:
        for ln in full_pull_news(bucket, kit, rec, now):
            say(f"  kit: {ln}")
    else:
        known = rec.setdefault("kit", {})
        k = pull_kit(a, bucket, root, kit, known, take, day, today)
        todo = k["todo"]
        show("the night's files " + ("that would come down" if a.dry_run else "to take"),
             list(todo), {r: e["size"] for r, e in todo.items()})
        for p in k["aside"]:
            say(f"  this laptop's copy kept at {p}")
        show("in this laptop's pull record and gone from the bucket's kit; left as they "
             "are", k["gone"], {})
        show("changed on this laptop while this pull ran, and left as they are", k["moved"], {})
        clashes += k["clash"]
        failures += k["bad"]

    # 5. THE LIVESTREAM STATE, which the laptop's caption catch-up reads.
    if not a.changes_only:
        for ln in pull_livestream_state(bucket, root, kit, a.dry_run):
            say(f"  {ln}")

    stray = sorted(take - set(k["taking"] if k else []) - set(taken))
    if stray:
        say(f"  --take named {', '.join(stray)}, which {'is' if len(stray) == 1 else 'are'} "
            "not a clash in this pull; nothing was set aside for "
            f"{'it' if len(stray) == 1 else 'them'}")
    if not a.dry_run:
        rec.update(at=now.isoformat(timespec="seconds"), epoch=time.time(),
                   mode="changes-only" if a.changes_only else "full")
        # THE LAST FULL PULL: the one --changes-only and preflight measure
        # the laptop's copies of the night's files by. A pull whose kit step
        # could not bring every file down whole does not count; one with
        # clashes does, because a clash is this laptop's own change, named
        # by every pull until --take settles it.
        if k and not k["bad"]:
            rec["full"] = {"epoch": time.time(), "at": now.isoformat(timespec="seconds"),
                           "clashes": len(k["clash"])}
        if not a.day:
            rec["changes_through"] = days[-1]
            if not a.changes_only:
                rec["logs_through"] = days[-1]
        save_pull_record(root, rec)

    would = "to take" if a.dry_run else "taken"
    parts = []
    if k:
        moved = k["todo"] if a.dry_run else {r: k["todo"][r] for r in k["got"]}
        parts.append(f"the night's files {len(moved):,} {would} "
                     f"({human(sum(e['size'] for e in moved.values()))}), "
                     f"{len(k['here']):,} already here, {len(k['clash']):,} clashing, "
                     f"{k['laptop']:,} the laptop's left alone")
    parts.append(f"logs and change lists {len(taken)} {would} "
                 f"({human(sum(lsizes.values()))}), {len(same)} already here, "
                 f"{len(lclash)} clashing"
                 + (f", {other} other names left in the bucket" if other else ""))
    parts.append(f"verdicts {n_verdicts} {would}")
    parts.append("the refusal record read" + ("" if a.dry_run else " and recorded"))
    say(f"pull{' --dry-run, nothing written' if a.dry_run else ''}: " + "; ".join(parts))
    problems = []
    if failures:
        problems.append(f"{len(failures)} did not come down whole or need a person: "
                        + "; ".join(failures[:4]) + ".")
    if clashes:
        problems.append(
            f"{len(clashes)} file(s) the night owns differ here from the copy this laptop "
            f"last had in common with the bucket, so this laptop changed them and pull left "
            f"them alone: {', '.join(clashes[:8])}. A night's file never goes back up from "
            "the laptop, so what changed here reaches nobody; a laptop build rewriting the "
            "carried outputs is the usual cause. To set this laptop's copies aside under "
            f"{SET_ASIDE}/{day}/ and take the bucket's:\n  python3 src/ops/cloud.py pull --take "
            + " ".join(clashes))
    if problems:
        raise Failed(" ".join(problems))


COMMANDS = {"kit-list": cmd_kit_list, "seed-kit": cmd_seed_kit,
            "kit-down": cmd_kit_down, "kit-up": cmd_kit_up,
            "state-down": cmd_state_down, "state-up": cmd_state_up,
            "clear-refusal": cmd_clear_refusal,
            "site-up": cmd_site_up, "site-down": cmd_site_down,
            "kit-release": cmd_kit_release,
            "backup": cmd_backup, "pull": cmd_pull, "send-refusal": cmd_send_refusal}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="The nightly's kit and the laptop's backup, in R2.")
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would be sent, and send nothing")
    ap.add_argument("--sizes", action="store_true", help="kit-list: with sizes")
    ap.add_argument("--with-site", action="store_true",
                    help="backup: include the built site/, which it leaves out")
    ap.add_argument("--allow-removals", action="store_true",
                    help="move more files to replaced/ than a normal run would")
    ap.add_argument("--local-bucket", metavar="FOLDER",
                    help="use a folder as the bucket (testing; no credentials)")
    ap.add_argument("--root", default=".", help="the working folder")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--run", help="site-up, site-down, kit-release: the night's run id "
                                  "(GitHub's run id), which names nights/<run>/")
    ap.add_argument("--dry-night", action="store_true",
                    help="kit-up, state-up: a dry run's night -- only what it fetched, its "
                         "logs apart and a refusal, a hold and its own verdict go back; on "
                         "GitHub's machine the workflow's DRY_RUN, or a run of a branch "
                         "other than main, says so whatever is passed")
    ap.add_argument("--hold", metavar="RUN",
                    help="kit-up, on a New term run: what the night changed waits under "
                         "nights/RUN/kit/ and stays out of kit/ until kit-release --run RUN")
    ap.add_argument("--site", default="site",
                    help="site-up, site-down: the built site's folder")
    ap.add_argument("--day", metavar="YYYY-MM-DD",
                    help="pull: that day's logs and change lists, instead of those "
                         "since the last pull")
    ap.add_argument("--changes-only", action="store_true",
                    help="pull: the refusal, the verdicts and the change lists, and "
                         "nothing else (the morning triage's)")
    ap.add_argument("--only", nargs="+", metavar="GLOB",
                    help="seed-kit: send only the kit files these globs name; every "
                         "other change waits")
    ap.add_argument("--take", nargs="+", metavar="PATH",
                    help="pull: set this laptop's copy of each named clash aside under "
                         f"{SET_ASIDE}/<day>/ and take the bucket's")
    ap.add_argument("--allow-local-bucket", action="store_true",
                    help="tests only: let pull --local-bucket run in the stood-down "
                         "repository that holds secrets.json (its read of the refusal "
                         "record still never counts)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    t0 = time.time()
    try:
        if a.command == "kit-list":
            cmd_kit_list(a, root)
        elif a.command == "pull" and a.dry_run:
            # A dry pull writes nothing, so there is no writer for the lock to
            # keep out -- and taking it would make archive/cloud/, a folder a
            # dry run has no business making.
            cmd_pull(a, root)
        else:
            with machine_lock(root):
                COMMANDS[a.command](a, root)
    except Failed as e:
        print(scrub(f"\ncloud.py {a.command} FAILED: {e}"), file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print(f"\ncloud.py {a.command} FAILED: interrupted; what had been sent is "
              "recorded up to the last checkpoint", file=sys.stderr, flush=True)
        return 1
    except Exception as e:                                      # noqa: BLE001
        print(scrub(f"\ncloud.py {a.command} FAILED: {type(e).__name__}: {e}"),
              file=sys.stderr, flush=True)
        return 1
    if a.command != "kit-list":
        say(f"({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
