#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.8
"""
The nightly run. Fetch what changed, rebuild, check, publish -- or don't.

    python3 nightly.py                 fetch, rebuild, check, publish
    python3 nightly.py --dry-run       everything except the deploy
    python3 nightly.py --key YOURKEY   also refresh the video index
    python3 nightly.py --force         publish even if the sanity gate objects

Meant for Task Scheduler. Everything it prints also goes to
logs/nightly-YYYY-MM-DD.log, and the exit code is 0 only if the site was
published or was already up to date.

WHY THIS AND NOT publish.bat

publish.bat gates each step on the one before it, which is most of the job. Two
things it does not do, and both matter more when nobody is watching:

  1. `publish` with no argument runs build_all --local, which touches no
     network. Correct for a hand-run rebuild; useless for a nightly, which
     exists to pick up yesterday's docket.

  2. Nothing checks that the rebuilt site is still a site. If the General
     Court is down, or an endpoint changes, or a bulk file arrives truncated,
     every script can succeed on nothing and produce a valid, empty result.
     check_site.py checks the site is well-formed. It cannot know that 2,234
     bills became 41.

THE SANITY GATE

Before rebuilding, the counts in the live site are recorded. After, they are
compared. A fall past the thresholds below stops the deploy and leaves the
published site alone:

    bills          more than 2% fewer in index.json
    legislators    more than 2% fewer in legislators.json
    bill_data      more than 2% fewer per-bill JSON files
    bill_pages     more than 5% fewer static pages

Bills are only added during a session and the roster only changes at a special
election, so any real fall is small and slow. A large one is a failure
upstream, and the right response to a failure upstream is to keep yesterday's
site.

Growth is never blocked. --force overrides, for the day a fall is real.

WHAT IT DOES NOT DO

It does not re-transcribe or re-align video. Those cost hours and change only
when a new recording appears; run align_all and apply_markers by hand.

It does not run without the bulk files being fetchable. If snapshot_gencourt
cannot reach the General Court, the build steps that read those files still
run against yesterday's copies, and the gate then finds the counts unchanged
and skips the deploy. Nothing breaks; nothing is published; the log says so.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
import time
import child
from datetime import datetime
from pathlib import Path

LOG = []

# The Pages project's production branch. The same value as publish.bat's
# PRODUCTION_BRANCH, and preflight holds the two together.
PRODUCTION_BRANCH = "master"

# What a fall in each of these means: something upstream failed, not that the
# legislature deleted its own record.
GATES = [("bills", 0.02), ("legislators", 0.02), ("bill_data", 0.02),
         ("bill_pages", 0.05)]


def say(msg=""):
    print(msg, flush=True)
    LOG.append(msg)


def run(args, label):
    """Stream the step's output as it happens, and log it too.

    This used to capture and print at the end, which meant a rebuild that
    fetches 2,234 bill pages showed nothing for the best part of an hour.
    Silence is indistinguishable from a crash, and the thing you least want in
    something meant to run unattended is a person unable to tell whether it is
    working.
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
    return proc.returncode == 0


def reachable():
    """One request, before an hour of them.

    A run whose first step failed on a closed connection carried on through
    seventeen more, each fetching nothing, and would have built a site from
    whatever was already on disk. That build is not wrong so much as pointless,
    and the danger is that it is only PARTLY pointless: enough fetched to pass
    the sanity gate, not enough to be today's record.

    So: ask for one page. If the General Court will not answer that, there is
    nothing for tonight's run to do.
    """
    req = urllib.request.Request(
        "https://gc.nh.gov/senate/about_senate/about.aspx",
        headers={"User-Agent": "granite-record/1.0 (civic transparency "
                               "project; contact@graniterecord.org)"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status == 200, f"HTTP {r.status}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def census(site):
    """The few numbers that say whether this is still the site.

    All four come from what was built, not from the source files, because the
    failure being guarded against is one where every source file reads fine and
    the output is empty anyway.
    """
    def count_json(name):
        try:
            v = json.loads((site / name).read_text(encoding="utf-8"))
            return len(v)
        except Exception:
            return 0

    return {"bills": count_json("index.json"),
            "legislators": count_json("legislators.json"),
            # Per-bill data sits under its filing year. Both shapes are counted so
            # that the gate reads the same number across the change rather than
            # seeing every bill vanish at once.
            "bill_data": (sum(1 for _ in (site / "bills").glob("*/*.json"))
                          + sum(1 for _ in (site / "bills").glob("*.json"))),
            "bill_pages": sum(1 for _ in (site / "bill").rglob("*.html"))}


def fingerprint(site):
    """Changed or not, without caring about file order or timestamps."""
    h = hashlib.sha256()
    for name in ("index.json", "meta.json", "home.json", "legislators.json"):
        f = site / name
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--project", default="graniterecord")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--key", help="YouTube key, to refresh the video index too")
    ap.add_argument("--dry-run", action="store_true", help="never deploy")
    ap.add_argument("--force", action="store_true", help="deploy past the gate")
    a = ap.parse_args()

    # One at a time. build_all runs the same fetches this does, so a second
    # run -- or a fetch started by hand in another window -- has two processes
    # writing the same JSON files and asking the General Court for everything
    # twice.
    lock = Path(".nightly.lock")
    if lock.exists():
        age = time.time() - lock.stat().st_mtime
        who = lock.read_text(encoding="utf-8", errors="replace").strip()
        if age < 6 * 3600:
            print(f"Another run is already going: {who}\n"
                  f"Started {age / 60:.0f} minutes ago. Two of these write the "
                  f"same files.\nWait for it, or delete {lock} if you are sure "
                  f"it died.")
            return 1
        print(f"Ignoring a stale lock from {age / 3600:.0f} hours ago.")
    lock.write_text(f"{datetime.now():%Y-%m-%d %H:%M} pid {__import__('os').getpid()}",
                    encoding="utf-8")

    started = datetime.now()
    say("=" * 74)
    say(f"Granite Record nightly  {started:%Y-%m-%d %H:%M}")
    say("=" * 74)

    site = Path(a.site)
    before = census(site)
    before_fp = fingerprint(site)
    say(f"\nlive now: " + ", ".join(f"{v:,} {k}" for k, v in before.items()))

    code = 1
    try:
        # Cheap and offline, so it runs first: a file that will not import is
        # not worth an hour of fetching to find out about.
        if not run(["preflight.py", "--code"], "preflight"):
            say("\nSTOPPED: preflight failed. Nothing fetched, nothing published.")
            return 1

        say("\n--- can we reach the General Court? ---")
        ok, how = reachable()
        say(f"  {how}")
        if not ok and not a.force:
            say("\nSTOPPED: the General Court is not answering, so there is "
                "nothing to\nfetch. The live site is untouched and no data "
                "file was rewritten.\nRun netcheck.py to find out why, or "
                "--force to build from what is\nalready on disk.")
            return 1

        args = ["build_all.py"] + (["--key", a.key] if a.key else [])
        if not run(args, "rebuild"):
            say("\nSTOPPED: the build failed. The live site is untouched.")
            return 1

        if not run(["check_site.py", "--site", a.site, "--base", a.base],
                   "check the built site"):
            say("\nSTOPPED: check_site failed. The live site is untouched.")
            return 1

        after = census(site)
        say("\n--- sanity gate ---")
        say(f"  {'':<14}{'before':>10}{'after':>10}   change")
        blocked = []
        for key, tol in GATES:
            b, n = before[key], after[key]
            if b and n < b * (1 - tol):
                blocked.append(f"{key} fell from {b:,} to {n:,}")
            pct = f"{(n - b) / b * 100:+.1f}%" if b else "n/a"
            say(f"  {key:<14}{b:>10,}{n:>10,}   {pct}")

        if blocked and not a.force:
            say("\nSTOPPED: " + "; ".join(blocked))
            say("A fall that size is a failure upstream, not a change in the\n"
                "record. Yesterday's site is still live. Re-run by hand, and\n"
                "if the fall is real, --force publishes it.")
            return 1
        if blocked:
            say("\n  gate objected, --force given: " + "; ".join(blocked))

        if fingerprint(site) == before_fp:
            say("\nNothing changed since the last run. Not deploying an "
                "identical site.")
            code = 0
            return 0

        if a.dry_run:
            say("\nChecks passed and the site changed. Not deploying, because "
                "--dry-run.")
            code = 0
            return 0

        say("\n--- publish ---")
        # --branch names the production branch rather than letting wrangler
        # take it from git; publish.bat says why. A nightly nobody watches is
        # exactly where a deploy that quietly became a preview goes unseen.
        r = child.run(["npx", "wrangler", "pages", "deploy", a.site,
                            f"--project-name={a.project}",
                            f"--branch={PRODUCTION_BRANCH}", "--commit-dirty=true"],
                           capture_output=True, text=True, shell=(sys.platform
                                                                  == "win32"))
        for ln in ((r.stdout or "") + (r.stderr or "")).rstrip().splitlines():
            say("  " + ln)
        if r.returncode != 0:
            say("\nSTOPPED: the deploy failed. The previous version is still "
                "live.")
            return 1
        # The deploy reporting success means the upload finished, not that the
        # world is getting what left this machine. That gap has produced three
        # separate confusions, so it is now the last step rather than an
        # assumption.
        if Path("check_live.py").exists():
            time.sleep(8)
            if not run(["check_live.py", "--base", a.base, "--site", a.site],
                       "what the live site is now serving"):
                say("\nDEPLOYED, BUT THE LIVE SITE DOES NOT LOOK RIGHT.\n"
                    "The upload succeeded; what it produced did not. A previous "
                    "version can be\nrestored from the Deployments tab in "
                    "Cloudflare.")
                return 1
        say(f"\nLive at {a.base}")
        code = 0
        return 0
    finally:
        lock.unlink(missing_ok=True)
        say("\n" + "=" * 74)
        say(f"finished {datetime.now():%H:%M}, "
            f"{(datetime.now() - started).seconds // 60} min, exit {code}")
        logs = Path("logs")
        logs.mkdir(exist_ok=True)
        (logs / f"nightly-{started:%Y-%m-%d}.log").write_text(
            "\n".join(LOG) + "\n", encoding="utf-8")
        # Two weeks is enough to see a pattern and not enough to notice.
        keep = sorted(logs.glob("nightly-*.log"))[:-14]
        for old in keep:
            old.unlink()


if __name__ == "__main__":
    sys.exit(main())
