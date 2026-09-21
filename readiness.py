#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.2
"""
Write READINESS.md: how far the site is from the five conditions for launch.

    python3 readiness.py            # write READINESS.md
    python3 readiness.py --print    # to the screen instead

WHY THIS EXISTS. On 20 September the person set out what would make them feel
prepared to launch -- the five conditions in CONDITIONS below -- and said
something else in the same breath that is the real reason for this file. The
visual pass kept turning up pages that were still first drafts, so each one
became a second draft before the visual work could go on. That is the right
thing to do. What it cost was the sense of momentum, because every loose end
arrived as a surprise and there was no way to see how many were left.

So this does for the launch what handoff.py does for the state of the data: it
measures rather than asserts, and it is regenerated rather than edited. A
number here is either read off the disk or read out of launch_register.json,
and the report says which. Nothing in READINESS.md is written by hand, which
is the only way it stays true -- HANDOFF.md, ARCHITECTURE.md and CLAUDE.md all
drift, and the numbers in them have been wrong within hours before now.

WHAT IT CANNOT MEASURE, and does not pretend to. An error nobody has noticed
is not in the register. No script can tell a page that has had a second draft
from one that has not. Those two lists are a person's, they live in
launch_register.json, and their being hand-kept is the point rather than a
shortcoming: making them explicit is what turns "an unknown number of loose
ends" into a list that gets shorter.

NO NETWORK, and it writes nothing but READINESS.md.
"""

import argparse
import json
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path


CONDITIONS = [
    ("THE RECORD",
     "The database is as complete as is feasible with what has been gathered."),
    ("WHAT IS KNOWN TO BE WRONG",
     "As many known factual errors as possible are fixed before the site is "
     "widely known."),
    ("THE SITE A READER MEETS",
     "Visually cohesive, and navigable by someone who knows the statehouse "
     "and by someone who does not."),
    ("RUNNING WITHOUT A PERSON",
     "It can be left alone for a week and trusted to keep updating itself."),
    ("THE CLERK TEST",
     "The House Clerk could be shown it and would see a reliable source."),
]

ROOT = Path(".")


def n(x):
    return f"{x:,}"


def pct(a, b):
    return "--" if not b else f"{a / b * 100:.0f}%"


def load(path, default=None):
    p = ROOT / path
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def bar(done, total, width=24):
    """A plain-text meter. Not decoration: the point of this file is that a
    person can see movement at a glance without reading the numbers."""
    if not total:
        return "[" + " " * width + "]"
    filled = round(width * done / total)
    return "[" + "#" * filled + "." * (width - filled) + "]"


# --------------------------------------------------------------- 1. record --
def section_record(out):
    m = load("site/data/manifest.json")
    if not m or "coverage" not in m:
        out.append("  site/data/manifest.json is not built, so coverage is "
                   "unknown here. Run a site build.\n")
        return
    cov = m["coverage"]
    cols = cov.get("columns") or []
    rows = cov.get("by_term") or []
    rows = sorted(rows, key=lambda r: r.get("term", ""), reverse=True)

    total_bills = sum(r.get("bills", 0) for r in rows)
    filled = sum(r.get(c, 0) for r in rows for c in cols)
    possible = total_bills * len(cols)
    out.append(f"  {n(total_bills)} bills across {len(rows)} terms. "
               f"{n(filled)} of {n(possible)} fields filled "
               f"({pct(filled, possible)}).\n")
    out.append(f"  {bar(filled, possible)}\n\n")

    # A term is called out only where it is meaningfully behind: a column
    # under 90% is a gap a reader would notice, and naming the term is what
    # makes it actionable rather than a percentage to feel bad about.
    behind = []
    for r in rows:
        bills = r.get("bills", 0)
        for c in cols:
            if bills and r.get(c, 0) / bills < 0.90:
                behind.append((r["term"], c, r.get(c, 0), bills))
    if behind:
        out.append("  Terms under 90% on a column:\n")
        for term, col, have, bills in behind:
            out.append(f"    {term}  {col:<10} {n(have)} of {n(bills)} "
                       f"({pct(have, bills)})\n")
    else:
        out.append("  Every term is at 90% or better on every column.\n")
    out.append("\n  Measured from site/data/manifest.json, written by the "
               "last site build\n  (generated "
               f"{(m.get('generated') or '?')[:19]}).\n")


# --------------------------------------------------------------- 2. errors --
def section_errors(out, reg):
    errs = reg.get("errors") or []
    if not errs:
        out.append("  launch_register.json lists no errors. That means "
                   "nobody has written any down,\n  not that there are "
                   "none.\n")
        return
    openish = [e for e in errs if e.get("status") == "open"]
    fixed = [e for e in errs if e.get("status") == "fixed"]
    gaps = [e for e in errs if e.get("status") == "source_gap"]

    out.append(f"  {n(len(fixed))} fixed, {n(len(openish))} open, "
               f"{n(len(gaps))} a gap in the source rather than an error here.\n")
    out.append(f"  {bar(len(fixed), len(fixed) + len(openish))}\n\n")

    unguarded = [e for e in fixed if (e.get("guard") or "none").lower() == "none"]
    if unguarded:
        out.append(f"  {n(len(unguarded))} of the fixed ones have no check "
                   "guarding them, so they can come back:\n")
        for e in unguarded:
            out.append(f"    - {e['what'][:96]}\n")
        out.append("\n")

    if openish:
        out.append("  OPEN:\n")
        for e in sorted(openish, key=lambda e: e.get("found", "")):
            days = _days_since(e.get("found"))
            age = f", {days} days" if days is not None else ""
            out.append(f"    - [{e.get('found', '?')}{age}] {e['what']}\n")
            out.append(f"      where: {e.get('where', '?')}\n")
    if gaps:
        out.append("\n  A HOLE IN THE SOURCE, not something a fix here can "
                   "close:\n")
        for e in gaps:
            out.append(f"    - {e['what']}\n")


def _scheduled_state():
    """Does anything on this machine actually start the nightly?

    A run of missing nights and an absent scheduler read the same way in a log
    directory and mean opposite things: one is automation that is failing, the
    other is automation that was never set up. Worth one subprocess call to
    tell them apart, because the work they imply is completely different.

    Windows only, and it degrades to saying so rather than guessing. The
    project's own direction is that this should end up running in the cloud
    rather than off a scheduled task on a person's PC, so a "no" here is not
    necessarily a defect -- it is a statement of where the automation is.
    """
    try:
        r = subprocess.run(["schtasks", "/query", "/fo", "csv", "/v"],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return ("could not ask the task scheduler here, so this is unknown "
                "-- check by hand")
    if r.returncode != 0:
        return "the task scheduler returned an error, so this is unknown"
    here = str(Path(".").resolve()).lower()
    hits = [l for l in r.stdout.splitlines()
            if here in l.lower() or "nightly.py" in l.lower()
            or "gc_lane" in l.lower()]
    total = max(0, len(r.stdout.splitlines()) - 1)
    if hits:
        return (f"yes -- {len(hits)} scheduled task(s) name this folder or "
                f"nightly.py, out of {n(total)} on this machine")
    return (f"NO. None of this machine's {n(total)} scheduled tasks names this "
            "folder,\n    nightly.py or the fetch lane. Every night that ran "
            "was started by hand, so\n    the rows above measure somebody "
            "remembering rather than a machine working.")


def _days_since(iso):
    try:
        return (date.today() - date.fromisoformat(iso)).days
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------- 3. site --
def section_site(out, reg):
    feats = reg.get("features") or []
    second = [f for f in feats if f.get("draft") == 2]
    first = [f for f in feats if f.get("draft") == 1]
    unknown = [f for f in feats if f.get("draft") not in (1, 2)]

    out.append(f"  {n(len(second))} of {n(len(feats))} parts have had a "
               f"second draft.\n")
    out.append(f"  {bar(len(second), len(feats))}\n\n")

    if first:
        out.append("  STILL A FIRST DRAFT:\n")
        for f in first:
            note = f" -- {f['note']}" if f.get("note") else ""
            out.append(f"    - {f['name']}{note}\n")
        out.append("\n")
    if unknown:
        out.append(f"  NOT LOOKED AT YET ({n(len(unknown))}). This is the "
                   "list that has been arriving one\n  surprise at a time; "
                   "it is here so it stops doing that.\n")
        for f in unknown:
            note = f" -- {f['note']}" if f.get("note") else ""
            out.append(f"    - {f['name']}{note}\n")

    # Measured, rather than taken from the register: what a reader can reach.
    site = ROOT / "site"
    if site.is_dir():
        kinds = [("bill pages", "bill"), ("legislators", "legislator"),
                 ("committees", "committee"), ("towns", "town"),
                 ("session days", "session"), ("learn", "learn")]
        counts = []
        for label, sub in kinds:
            d = site / sub
            if d.is_dir():
                counts.append(f"{label} {n(sum(1 for _ in d.rglob('*.html')))}")
        if counts:
            out.append("\n  Built and reachable: " + ", ".join(counts) + ".\n")


# ------------------------------------------------------------- 4. unwatched --
NIGHTLY = re.compile(r"nightly-(\d{4}-\d{2}-\d{2})\.log$")
FINISHED = re.compile(r"^finished\s+\d{1,2}:\d{2},\s*(\d+)\s*min,\s*exit\s*(\d+)",
                      re.M)
DEFERRED = re.compile(r"^DEFERRED:", re.M)


def section_unwatched(out, days=21):
    logs = ROOT / "logs"
    found = {}
    if logs.is_dir():
        for p in logs.glob("nightly-*.log"):
            m = NIGHTLY.search(p.name)
            if m:
                found[m.group(1)] = p

    today = date.today()
    # TONIGHT HAS NOT HAPPENED YET. The nightly runs in the small hours, so
    # counting today as a missed night marks the report wrong every evening.
    window = [(today - timedelta(days=i)) for i in range(days, 0, -1)]

    # AND A NIGHT BEFORE THE FIRST LOG IS NOT A FAILURE. Nothing on disk says
    # when the schedule was created, so a gap before the earliest log is
    # ambiguous and the report says so rather than scoring it.
    earliest = min(found) if found else None

    rows, clean_run, best_run, worst = [], 0, 0, []
    for d in window:
        key = d.isoformat()
        p = found.get(key)
        if p is None:
            if earliest and key < earliest:
                rows.append((key, "before", "", ""))
                continue
            rows.append((key, "MISSING", "", ""))
            clean_run = 0
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fin = FINISHED.search(text)
        mins = fin.group(1) if fin else "?"
        code = fin.group(2) if fin else "?"
        if DEFERRED.search(text):
            rows.append((key, "deferred", mins, code))
            clean_run = 0            # it exited 0 and did nothing
            worst.append((key, "deferred -- a build held the lock"))
        elif code == "0":
            rows.append((key, "ran", mins, code))
            clean_run += 1
            best_run = max(best_run, clean_run)
        else:
            rows.append((key, "FAILED", mins, code))
            clean_run = 0
            worst.append((key, f"exit {code}"))

    ran = sum(1 for r in rows if r[1] == "ran")
    before = sum(1 for r in rows if r[1] == "before")
    scored = len(rows) - before
    out.append(f"  Of the {scored} nights since the first nightly log "
               f"({earliest or 'none'}): {ran} did real\n  work and exited "
               f"clean, {sum(1 for r in rows if r[1] == 'deferred')} deferred, "
               f"{sum(1 for r in rows if r[1] == 'FAILED')} failed, "
               f"{sum(1 for r in rows if r[1] == 'MISSING')} did not run.\n")
    if before:
        out.append(f"  ({before} earlier nights are not scored: nothing on "
                   "disk says when the schedule\n  was created, so a gap "
                   "before the first log may mean it did not exist yet.)\n")
    out.append(f"  {bar(ran, scored)}\n\n")
    out.append(f"  LONGEST CLEAN RUN: {best_run} consecutive night"
               f"{'' if best_run == 1 else 's'}.\n")
    out.append("  The condition is seven. A deferred night breaks the run "
               "even though it exits 0,\n  because a night that did nothing "
               "is not a night that worked.\n\n")

    for key, what, mins, code in rows:
        mark = {"ran": "  ok  ", "deferred": " skip ", "FAILED": " FAIL ",
                "MISSING": " --   ", "before": "      "}[what]
        extra = f"{mins} min" if mins not in ("", "?") else ""
        label = "not scored" if what == "before" else what
        out.append(f"    [{mark}] {key}  {label:<11} {extra}\n")

    # IS ANYTHING ACTUALLY SCHEDULED? Asked before the log rows are believed,
    # because the two readings look identical and mean opposite things. A run
    # of missing nights reads as flaky automation; it can equally mean there
    # is no automation and every night that ran was started by hand. On
    # 20 September that was the answer -- none of this machine's 209 scheduled
    # tasks ran python or named this folder -- and the report had been
    # implying the first while the truth was the second.
    out.append("\n  Scheduled to run at all?\n")
    state = _scheduled_state()
    out.append(f"    {state}\n")

    # The fetch lane, which is the other half of running unattended.
    out.append("\n  The fetch lane:\n")
    lock = ROOT / "archive" / ".lock"
    if lock.exists():
        age = (datetime.now() - datetime.fromtimestamp(lock.stat().st_mtime))
        fresh = age.total_seconds() < 120
        out.append(f"    archive/.lock is {'FRESH -- a fetch is running now' if fresh else 'stale (' + str(int(age.total_seconds() // 60)) + ' min)'}\n")
    else:
        out.append("    no archive/.lock, so no fetch is in flight\n")
    ref = load("archive/refused.json")
    out.append(f"    {'A REFUSAL IS BEING HELD -- the lane is stopped' if ref else 'no standing refusal'}\n")

    q = ROOT / "watchers" / "gc_lane.queue"
    done = ROOT / "logs" / "gc_lane.done"
    if q.exists():
        steps = [l.strip() for l in q.read_text(encoding="utf-8",
                                                errors="replace").splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        ran_steps = set()
        if done.exists():
            ran_steps = {l.strip() for l in done.read_text(
                encoding="utf-8", errors="replace").splitlines() if l.strip()}
        left = [s for s in steps if s not in ran_steps]
        out.append(f"    {n(len(left))} of {n(len(steps))} queued steps "
                   f"have not run\n")


# ------------------------------------------------------------- 5. the clerk --
def section_clerk(out, reg):
    out.append(
        "  Not a score. The other four are things to finish; this is the\n"
        "  standard they are finished AGAINST, and the way to test it is to\n"
        "  read the site as somebody who knows the record better than we do.\n\n"
        "  What such a reader can already check:\n"
        "    - every figure on a page traces to the General Court's own file\n"
        "    - a correction says what was wrong, what the sources said, and\n"
        "      which check now stops it recurring\n"
        "    - where the record is silent the page says so rather than\n"
        "      filling the gap\n"
        "    - the timestamp on a recording is the claim; the recording is\n"
        "      the evidence, and captions are never quoted as speech\n\n"
        "  What would fail it today: anything in the OPEN list above that a\n"
        "  Clerk would recognise on sight. A wrong polling place is the one\n"
        "  to fear -- it is the only error here that stops somebody voting.\n")


# ------------------------------------------------------------------- main ---
def build():
    reg = load("launch_register.json", {})
    out = []
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    out.append("# Launch readiness\n\n")
    out.append(f"Generated by `readiness.py` at {stamp}. **Never edit this "
               "file** -- it is\nrewritten wholesale, and anything typed here "
               "is lost and was wrong anyway.\nThe hand-kept half lives in "
               "`launch_register.json`.\n\n")
    out.append("The five conditions are the person's own, set out on "
               "20 September 2026.\n\n---\n\n")

    if not reg:
        out.append("**launch_register.json is missing**, so two of the five "
                   "sections have nothing\nto read. Everything measured off "
                   "disk still works.\n\n")

    fns = [section_record, None, None, None, None]
    for i, (title, why) in enumerate(CONDITIONS, 1):
        out.append(f"## {i}. {title}\n\n*{why}*\n\n")
        if i == 1:
            section_record(out)
        elif i == 2:
            section_errors(out, reg)
        elif i == 3:
            section_site(out, reg)
        elif i == 4:
            section_unwatched(out)
        else:
            section_clerk(out, reg)
        out.append("\n\n")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="show", action="store_true",
                    help="write to the screen instead of READINESS.md")
    a = ap.parse_args()
    text = build()
    if a.show:
        print(text)
    else:
        Path("READINESS.md").write_text(text, encoding="utf-8")
        print(f"READINESS.md written, {len(text.splitlines())} lines")


if __name__ == "__main__":
    main()
