#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-30.3
"""
The laptop's evening job: the night's list of new livestreams down, captions
for the recordings YouTube would not give GitHub's machine, and their start
times up for the next night to publish.

    python3 laptop_evening.py             what Windows' Task Scheduler runs each evening
    python3 laptop_evening.py --dry-run   the pull's plan; captions and sends nothing

WHY THE LAPTOP

The nightly on GitHub finds each new House and Senate recording and puts it on
its bill's page the next morning, with a start taken from the schedule and
marked approximate. The exact start comes from the chair's words in the
captions, and YouTube answers GitHub's machines with "Sign in to confirm
you're not a bot": every caption the nightly asked for from 26 to 30 September
2026 was refused. It answers this laptop's home address. So the nightly lists
the recordings, and this reads them.

WHAT IT RUNS, IN ORDER, STOPPING AT THE FIRST THAT FAILS

  1. cloud.py pull
       the night's files, and its livestream state (archive/livestreams.json),
       which says which recordings wait for captions. The state must be under
       two days old, or nothing is captioned: an older list is a night that
       has not run, and the catch-up would be working from a stale one.
  2. livestreams.py --catch-up
       captions the waiting recordings -- whatever is waiting, the oldest
       first and twenty at most in an evening, a minute or two apart, one
       caption track each -- and reads the chair's boundaries out of them.
       What is left comes first the next evening. A recording that answered
       without captions is asked again after the new ones, a day later and
       then two, four and eight. The longest evening is about forty minutes
       of this step; livestreams.py says what that is in requests.
  3. probe_alignment.py --truth --candidate candidate_segments.json
       CLAUDE.md: nothing about timestamps goes on the site before this has
       been run and the median has not regressed. It is compared with the
       probe of the last times this job sent (or, the first evening, with the
       probe before the catch-up): a worse median, or fewer hand-timed
       proceedings placed out of the same number, and nothing is sent. The
       catch-up reads new recordings with the same method, so this should
       never fire; it is here because an unattended loop is where a quiet
       regression would otherwise go out every night.
  4. cloud.py seed-kit --only candidate_segments.json caption_spans.json work/*/segments.json
       the caption results and nothing else. Whatever else the laptop has
       changed -- a data file re-read on dev, not yet released -- stays here:
       it reaches the site with a release, never by this back door.

The next night publishes the times. A morning hearing is on its bill's page
the next morning, and has its exact start the morning after -- unless more
than twenty recordings were waiting that evening, or YouTube has refused
this laptop: then it waits its turn. Replayed against 2025 and 2026, two
recordings in the two years waited an evening longer, and none longer.

WHAT IT ASKS

The project's own R2 bucket, and YouTube for the captions. Never the General
Court, so neither the refusal record nor GitHub's night window governs it.

WHAT IT LEAVES

logs/evening-<day>.log, everything each step printed; and
archive/cloud/evening.json, when it last ran, how it ended, and the probe of
the times it last sent. If the laptop is off for a week, nothing breaks: the
recordings stay on their pages with approximate starts, the night's verdict
warns that they are waiting, and the evenings after it is back catch them up,
the oldest first and twenty an evening. A week off in session leaves forty or
fifty waiting, which is two or three evenings -- replayed for the weeks of
3 February 2026 and 12 February 2025.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = Path("archive/livestreams.json")
RECORD = Path("archive/cloud/evening.json")
LOGS = Path("logs")
FRESH_DAYS = 2
CAPTION_FILES = ("candidate_segments.json", "caption_spans.json", "work/*/segments.json")
PROBE = ["probe_alignment.py", "--truth", "--candidate", "candidate_segments.json"]
CANDIDATE = re.compile(r"A CANDIDATE: candidate_segments\.json\s+\((\d+) of (\d+) marked"
                       r"[^\n]*\n\s+median off by (\d+)m (\d+)s")


def run_step(argv, log):
    """(exit code, what it printed) of one of this folder's scripts, its output
    written into the evening's log."""
    p = subprocess.run([sys.executable, str(HERE / argv[0]), *argv[1:]], cwd=HERE,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    log(f"$ python3 {' '.join(argv)}\n{out.rstrip()}\n(exit {p.returncode})")
    return p.returncode, out


def state_age_days():
    """How many days old the night's livestream state is, or None without one."""
    try:
        st = json.loads(STATE.read_text(encoding="utf-8"))
        at = (st.get("last_run") or {}).get("at") or ""
        then = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except (OSError, ValueError, AttributeError, TypeError):
        return None
    return (datetime.now(timezone.utc) - then).total_seconds() / 86400


def probe(log):
    """The candidate's score against the hand-timed proceedings, or None."""
    code, out = run_step(PROBE, log)
    m = CANDIDATE.search(out)
    if code != 0 or not m:
        return None
    placed, total, mins, secs = map(int, m.groups())
    return {"median_s": mins * 60 + secs, "placed": placed, "total": total}


def regressed(base, now):
    """Why the probe is worse than base, or ""."""
    if now["median_s"] > base["median_s"]:
        return f"the median went from {base['median_s']}s to {now['median_s']}s"
    if now["total"] == base["total"] and now["placed"] < base["placed"]:
        return (f"it places {now['placed']} of {now['total']} hand-timed proceedings, "
                f"where it placed {base['placed']}")
    return ""


def last_sent_probe():
    try:
        return json.loads(RECORD.read_text(encoding="utf-8")).get("sent_probe")
    except (OSError, ValueError, AttributeError):
        return None


def evening(dry=False, log=print):
    """(exit code, {step: exit}, one line saying how it ended, the probe of
    what was sent or None)."""
    steps = {}
    # A pull reports a clash -- a night's file the laptop changed -- with
    # exit 1 and still brings the rest, the state included; so what decides
    # whether to go on is the state itself.
    steps["pull"], _ = run_step(["cloud.py", "pull"] + (["--dry-run"] if dry else []), log)
    if dry:
        return 0, steps, "dry run: the pull's plan only; nothing captioned or sent", None
    age = state_age_days()
    if age is None or age > FRESH_DAYS:
        why = ("the night's livestream state is not here" if age is None else
               f"the night's livestream state is {age:.1f} days old")
        return 1, steps, f"stopped: {why}; nothing was captioned or sent", None
    base = last_sent_probe()
    if base is None:
        base = probe(log)
        if base is None:
            return 1, steps, ("stopped: the timestamp probe would not run before the "
                              "catch-up; nothing was captioned or sent"), None
    steps["catch-up"], out = run_step(["livestreams.py", "--catch-up"], log)
    line = next((ln for ln in out.splitlines() if ln.startswith("LIVESTREAMS CATCH-UP:")), "")
    if steps["catch-up"] != 0:
        return (steps["catch-up"], steps,
                f"stopped: the catch-up ended with exit {steps['catch-up']}; nothing was sent"
                + (f" ({line})" if line else ""), None)
    after = probe(log)
    steps["probe"] = 0 if after else 1
    if after is None:
        return 1, steps, "stopped: the timestamp probe would not run; nothing was sent", None
    why = regressed(base, after)
    if why:
        steps["probe"] = 1
        return 1, steps, (f"stopped: the timestamp probe got worse ({why}); nothing was sent, "
                          "and nothing will be until a person has looked"), None
    steps["send"], out = run_step(["cloud.py", "seed-kit", "--only", *CAPTION_FILES], log)
    sent = next((ln for ln in out.splitlines() if ln.startswith("seed-kit: sent")), "")
    if steps["send"] != 0:
        return (steps["send"], steps,
                f"the start times were read but not sent (exit {steps['send']}); "
                "the next evening sends them", None)
    return (0, steps, "; ".join(x for x in (line or "LIVESTREAMS CATCH-UP: nothing to do", sent,
                                            f"probe median {after['median_s']}s, "
                                            f"{after['placed']} of {after['total']} placed") if x),
            after)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="the pull's plan only")
    a = ap.parse_args(argv)
    os.chdir(HERE)                          # Task Scheduler may start it anywhere
    LOGS.mkdir(exist_ok=True)
    started = datetime.now()
    with open(LOGS / f"evening-{started:%Y-%m-%d}.log", "a", encoding="utf-8") as fh:
        def log(msg):
            fh.write(msg + "\n")
            fh.flush()
            print(msg)                      # nothing, under pythonw
        log(f"=== {started:%Y-%m-%d %H:%M} laptop_evening.py" + (" --dry-run" if a.dry_run else ""))
        code, steps, said, sent_probe = evening(a.dry_run, log)
        log(said)
    if not a.dry_run:
        rec = {"at": started.isoformat(timespec="seconds"), "exit": code, "steps": steps,
               "said": said, "sent_probe": sent_probe or last_sent_probe()}
        RECORD.parent.mkdir(parents=True, exist_ok=True)
        tmp = RECORD.with_name(RECORD.name + ".part")
        tmp.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, RECORD)
    return code


if __name__ == "__main__":
    sys.exit(main())
