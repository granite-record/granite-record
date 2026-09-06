#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.2
"""
Write STATE.md from what is actually on disk.

    python3 handoff.py            # write STATE.md
    python3 handoff.py --print    # to the screen instead

Every number in a handover document goes stale the moment someone runs a
fetch. STATUS.md has been rewritten by hand four times this week and was wrong
within hours each time, because a person has to notice that a number changed
and then remember to edit a file about it.

So the numbers are not written by hand any more. This reads versions.json,
proceedings.csv, candidate_segments.json, ground_truth.csv, the data files and
the site, and reports what it finds. Run it at the start of a session and the
state section is current by construction.

What it does NOT generate: why the project is built this way, what the rules
are, what to do next. Those are in HANDOFF.md, they change slowly, and a
person should write them.
"""

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def n(x):
    return f"{x:,}"


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def rows(p):
    try:
        with Path(p).open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def section_files(out):
    v = jload("versions.json", {}).get("files", {})
    out.append(f"## Files\n\n{n(len(v))} scripts, listed in `versions.json`.\n")
    missing = [f for f in v if not Path(f).exists()]
    if missing:
        out.append(f"**{len(missing)} listed but not present:** "
                   + ", ".join(sorted(missing)[:8]) + "\n")
    recent = []
    for f in v:
        p = Path(f)
        if p.exists():
            recent.append((p.stat().st_mtime, f, v[f]))
    recent.sort(reverse=True)
    out.append("Most recently changed:\n")
    for _, f, ver in recent[:8]:
        out.append(f"- `{f}` {ver}")
    out.append("")


def section_data(out):
    out.append("## Data\n")
    pr = rows("proceedings.csv")
    if pr:
        floor = [r for r in pr if r.get("kind") in
                 ("floor debate", "committee of conference")]
        vids = {r.get("video_id") for r in pr if r.get("video_id")}
        terms = sorted({r.get("term") for r in pr if r.get("term")})
        out.append(f"- `proceedings.csv`: {n(len(pr))} proceedings, "
                   f"{n(len(vids))} recordings, {n(len(floor))} floor rows, "
                   f"terms {', '.join(terms)}")
    else:
        out.append("- `proceedings.csv`: **MISSING**. Run "
                   "`python3 build_proceedings.py` -- every tool refuses "
                   "without it.")

    gt = rows("ground_truth.csv")
    out.append(f"- `ground_truth.csv`: {n(len(gt))} proceedings timed by hand. "
               "The only measurement a person made; no generator writes it.")

    for f, label in (("narratives.json", "bill histories"),
                     ("bill_status.json", "docket status"),
                     ("committee_reports.json", "committee reports"),
                     ("floor_index.json", "floor appearances"),
                     ("bill_text.json", "bill texts")):
        d = jload(f)
        if isinstance(d, dict):
            out.append(f"- `{f}`: {n(len(d))} bills ({label})")

    work = Path("work")
    if work.is_dir():
        caps = ["captions.en.json3", "captions.en-orig.json3", "transcript.json"]
        dirs = [d for d in work.iterdir() if d.is_dir()]
        have = [d for d in dirs if any((d / c).exists() for c in caps)]
        out.append(f"- `work/`: {n(len(dirs))} recording folders, "
                   f"{n(len(have))} with captions this can read")
    out.append("")


def section_timestamps(out):
    out.append("## Timestamps\n")
    cs = jload("candidate_segments.json", {})
    if not cs:
        out.append("No `candidate_segments.json`. Run "
                   "`python3 segment_markers.py --all --data data`.\n")
        return
    absent = cs.get("_absent", {})
    vids = [k for k in cs if k != "_absent"]
    # Proceedings, not bills: a bill heard in the morning and voted in the
    # afternoon is two, and the same bill on two recordings is two more. The
    # end count is per proceeding as well, so the two are comparable.
    segs = [s for k, v in cs.items() if k != "_absent"
            for ss in v.values() for s in ss]
    bills = {b for k, v in cs.items() if k != "_absent" for b in v}
    ends = sum(1 for s in segs if s.get("end") is not None)
    out.append(f"- {n(len(segs))} proceedings with a boundary the chair "
               f"stated, on {n(len(vids))} recordings ({n(len(bills))} "
               "distinct bills)")
    out.append(f"- {n(ends)} of those proceedings also have a stated end")
    if absent:
        out.append(f"- {n(sum(len(v) for v in absent.values()))} bills never "
                   "named on their recording (consent calendar; not a gap)")
    out.append("\nScore it before publishing:\n\n```\npython3 "
               "probe_alignment.py --truth --candidate candidate_segments.json"
               "\n```\n\nThe number to watch is the candidate median. It was "
               "**0m 01s** on 5 September\nagainst 1m 27s for the clustering "
               "model and 17m 05s for the schedule alone.\nIf it moves off "
               "seconds, something regressed and the site should not go out.\n")


def section_site(out):
    b = jload("site/build.json")
    out.append("## Site\n")
    if not b:
        out.append("No `site/build.json` -- the site has not been built here.\n")
        return
    site = Path("site")
    # Files, not entries. rglob yields directories as well, and the number
    # this feeds is the one the Cloudflare 20,000 cap decision rests on.
    files = (sum(1 for x in site.rglob("*") if x.is_file())
             if site.is_dir() else 0)
    dirs = (sum(1 for x in site.rglob("*") if x.is_dir())
            if site.is_dir() else 0)
    idx = jload("site/index.json", [])
    out.append(f"- {n(files)} files in `site/` across {n(dirs)} folders "
               f"(Cloudflare Pages allows 20,000 files)")
    if isinstance(idx, list):
        out.append(f"- {n(len(idx))} bills in the index")
    when = b.get("finished") or b.get("when") or ""
    if when:
        out.append(f"- last built {when}")
    out.append("")


def section_checks(out):
    out.append("## Checks\n")
    if not Path("preflight.py").exists():
        out.append("`preflight.py` is not here.\n")
        return
    r = subprocess.run([sys.executable, "preflight.py", "--code"],
                       capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if "passed," in l]
    # A preflight that crashed and one that printed in an unexpected format
    # used to look identical here: both produced "preflight did not report"
    # and no failures. That is rule 3 broken inside the tool that reports
    # whether rule 3 is being kept.
    if r.returncode != 0 and not lines:
        tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
        out.append(f"**preflight exited {r.returncode} without reporting.** "
                   "Run it directly; the state below\nis from files it did not "
                   "get to check.\n")
        out.append("```\n" + "\n".join(tail) + "\n```")
        return
    out.append("```\n" + (lines[-1] if lines else
                          f"preflight exited {r.returncode}, no summary line")
               + "\n```")
    bad = [l.strip() for l in r.stdout.splitlines() if "[ FAIL ]" in l]
    if bad:
        out.append("\nFailing:\n")
        for l in bad[:6]:
            out.append(f"- {l.replace('[ FAIL ] ', '')}")
    out.append("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="show", action="store_true")
    ap.add_argument("--out", default="STATE.md")
    a = ap.parse_args()

    out = [
        "# Granite Record — current state",
        "",
        f"Generated by `handoff.py` on "
        f"{datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}. "
        "Do not edit;",
        "run it again instead. The prose that explains the project is in "
        "`HANDOFF.md`,",
        "which changes slowly and is written by a person.",
        "",
    ]
    section_checks(out)
    section_data(out)
    section_timestamps(out)
    section_site(out)
    section_files(out)
    text = "\n".join(out) + "\n"

    if a.show:
        print(text)
    else:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"{a.out} written. Paste it into a new chat alongside "
              "HANDOFF.md.")


if __name__ == "__main__":
    main()
