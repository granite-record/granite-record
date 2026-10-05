#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.11
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
are, what to do next. Those are in CLAUDE.md, README.md and
ARCHITECTURE.md, they change slowly, and a person should write them.

THE CHECKS ARE READ, NOT RUN AGAIN (1 October 2026). A session starts with
inventory, preflight, handoff, and this used to run `preflight.py --code` a
second time straight after the person had: four more minutes on the laptop
for a line it had just printed. preflight now leaves a record of each run in
logs/preflight-last.json (record_run, below, which it calls), and this reads
it -- but only a run of THIS code: the record names the commit and a digest of
everything in the working tree that differs from it (tree_state), and where
either has moved since, or the run was of the data checks alone, the record
is refused and preflight is run again, as before. STATE.md says which.

WHAT ELSE A RECORD MUST BE (1 October 2026, from the review of the above). A
record was read back in four cases where it was not a run of what is here:
one that ran no checks at all (`--code --data` together, which preflight now
refuses to start); one two months old, or made under another Python -- the
commit and the tree were the same, and what the checks ran on was not; one
made by a copy of the code in a folder git ignores, where git answers for the
repository around the copy and sees no edit to it; and one whose tree held a
file with a name git writes in quotes, which was named and never read. Each
is refused now (last_run, tree_state). And the data checks' line is given
only while the data files are as that run read them (data_state): git
ignores nearly all of them, so the tree's digest cannot see one rebuilt.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import child
import site_read
from datetime import datetime, timedelta, timezone
from pathlib import Path


TERM_RE = re.compile(r"^\d{4}-\d{4}$")

# preflight's record of its last run, which section_checks reads. In logs/,
# which git ignores and no build reads.
RUN = Path("logs/preflight-last.json")
# How old a record may be and still be read. What a run checked is keyed, the
# commit and the tree; what it ran ON is not -- the packages installed, node,
# the date some checks read -- and a session's own preflight is minutes old.
RUN_FRESH_HOURS = 24
# The data the data checks read, as data_state() looks for it: files of
# these kinds directly in these folders, and the build's record of the site.
DATA_FOLDERS = (".", "data", "archive", "db")
DATA_KINDS = (".json", ".jsonl", ".csv", ".psv", ".txt")
DATA_ALSO = ("site/build.json",)


def tree_state():
    """(commit, tree): the commit checked out here, and a digest of how the
    working tree differs from it -- every changed, added, removed or untracked
    file git does not ignore, by name and by content. (None, None) where git
    cannot say, which is a folder that is not a repository.

    Two calls agree exactly when the code a preflight run checked is the code
    that is here now. Content, not only names: a file edited twice shows the
    same line in `git status` both times.
    """
    try:
        head = child.run(["git", "rev-parse", "HEAD"], capture_output=True,
                         text=True, timeout=60)
        top = child.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                        text=True, timeout=60)
        # -z: names as they are, one entry a NUL. Without it git writes a
        # name that is not plain ASCII in quotes with its bytes escaped, the
        # path read off that line did not exist, and the file was named in
        # the digest and never read: a second edit to it went unseen.
        st = child.run(["git", "status", "--porcelain", "-z", "--untracked-files=all"],
                       capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None, None
    if head.returncode != 0 or st.returncode != 0 or top.returncode != 0 \
            or not (head.stdout or "").strip():
        return None, None
    # THIS FOLDER'S OWN REPOSITORY. In a copy of the code inside a folder
    # the repository ignores, git answers for the repository around it: the
    # same commit, and a status that never shows an edit to the copy. A
    # record keyed on that vouches for code git is not looking at.
    try:
        if not os.path.samefile((top.stdout or "").strip(), "."):
            return None, None
    except OSError:
        return None, None
    fields, entries, i = (st.stdout or "").split("\0"), [], 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        if "R" in entry[:2] or "C" in entry[:2]:
            # A rename or a copy: git's next field is the name it came from.
            entry += "\0" + (fields[i] if i < len(fields) else "")
            i += 1
        entries.append(entry)
    h = hashlib.sha256()
    for ln in sorted(entries):
        h.update(ln.encode("utf-8", "replace") + b"\0")
        f = Path(ln[3:].split("\0")[0])
        try:
            if f.is_file():
                with f.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
        except OSError:
            h.update(b"unreadable")
        h.update(b"\0")
    return head.stdout.strip(), h.hexdigest()


def data_state():
    """A digest of the data files as they stand: the name, size and time of
    writing of every data file directly in DATA_FOLDERS, and of the build's
    record of the site. No file is opened, so it costs nothing to ask twice.

    It is not everything a data check reads -- the built pages and the
    caption folders are far too many to walk -- but a build, a fetch or a
    parser run writes at least one of these, and that is the question:
    has anything been rebuilt since the data checks read it?
    """
    seen = [Path(f) for f in DATA_ALSO]
    for folder in DATA_FOLDERS:
        try:
            seen += [f for f in Path(folder).iterdir() if f.suffix.lower() in DATA_KINDS]
        except OSError:
            pass
    h = hashlib.sha256()
    for f in sorted(seen, key=lambda f: f.as_posix()):
        try:
            s = f.stat()
            h.update(f"{f.as_posix()}\0{s.st_size}\0{s.st_mtime_ns}\0".encode("utf-8", "replace"))
        except OSError:
            h.update(f"{f.as_posix()}\0not here\0".encode("utf-8", "replace"))
    return h.hexdigest()


def record_run(mode, results, before, seconds, data=None):
    """Write RUN: what a preflight run found, and the code it ran on.

    `mode` is "code", "data" or "all"; `results` is preflight's own list of
    (group, name, status, message); `before` is tree_state() as the run
    began. The tree is read again here, and a tree that moved while the
    checks ran is recorded as no tree at all: such a run vouches for neither
    state, and a reader keyed on the tree refuses it. `data` is data_state()
    as the run began, recorded the same way: no digest at all where the data
    files moved under the run. Never raises -- a record that cannot be
    written must not change what preflight reports.
    """
    try:
        after, data_after = tree_state(), data_state()
        commit, tree = before if before == after else (before[0], None)
        RUN.parent.mkdir(exist_ok=True)
        tmp = RUN.with_name(RUN.name + ".part")
        tmp.write_text(json.dumps({
            "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seconds": round(seconds, 1), "mode": mode, "commit": commit, "tree": tree,
            "data": data_after if data in (None, data_after) else None,
            "python": sys.version.split()[0],
            "checks": [[g, name, status] for g, name, status, _ in results],
        }, indent=1) + "\n", encoding="utf-8", newline="\n")
        tmp.replace(RUN)
        return True
    except Exception:                                           # noqa: BLE001
        return False


def last_run():
    """(record, why not): preflight's last run if it was of this code, or
    None and the reason it cannot be used."""
    rec = jload(RUN)
    if not isinstance(rec, dict) or not isinstance(rec.get("checks"), list):
        return None, f"there is no {RUN.as_posix()}"
    if rec.get("mode") not in ("code", "all"):
        return None, "the last preflight run was of the data checks alone"
    # A RUN THAT RAN NOTHING IS NOT A RUN. `preflight.py --code --data` ran no
    # check, exited 0 and recorded "code" with an empty list, which this read
    # back as "0 passed, 0 failed, 0 skipped".
    if not any(isinstance(c, list) and len(c) == 3 and c[0] != "data" for c in rec["checks"]):
        return None, "the last preflight run ran no code checks"
    # WHAT IT RAN ON, which the commit and the tree do not say.
    if rec.get("python") != sys.version.split()[0]:
        return None, (f"the last preflight run was under python {rec.get('python')}, and "
                      f"this is {sys.version.split()[0]}")
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(str(rec.get("finished")))
    except (TypeError, ValueError):
        return None, "the last preflight run does not say when it finished"
    if not timedelta(minutes=-5) <= age <= timedelta(hours=RUN_FRESH_HOURS):
        return None, (f"the last preflight run finished {rec.get('finished')}, which is not "
                      f"within the last {RUN_FRESH_HOURS} hours")
    commit, tree = tree_state()
    if not commit or not tree:
        return None, ("git cannot say what code is here, or this folder is not the top "
                      "of its own repository")
    if not rec.get("commit") or not rec.get("tree"):
        return None, ("the last preflight run does not say what code it ran on, or "
                      "the code changed while it ran")
    if rec["commit"] != commit:
        return None, (f"the last preflight run was on commit {str(rec['commit'])[:9]}, "
                      f"and this is {commit[:9]}")
    if rec["tree"] != tree:
        return None, "the working tree has changed since the last preflight run"
    return rec, ""


def tally(checks, data):
    """"N passed, N failed, N skipped" over a record's data checks, or the rest."""
    mine = [c for c in checks if (c[0] == "data") == data]
    return (f"{sum(1 for c in mine if c[2] == 'ok')} passed, "
            f"{sum(1 for c in mine if c[2] in ('FAIL', 'ERROR'))} failed, "
            f"{sum(1 for c in mine if c[2] == 'skip')} skipped")


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
            # Several of these are {term: {bill: record}} now, so len() counts
            # terms rather than bills. Both shapes are still in the tree while
            # they are converted one at a time, so both are reported.
            if d and all(TERM_RE.match(k) for k in d):
                per = ", ".join(f"{t} {n(len(v))}" for t, v in sorted(d.items()))
                out.append(f"- `{f}`: {n(sum(len(v) for v in d.values()))} "
                           f"bills ({label}) -- {per}")
            else:
                out.append(f"- `{f}`: {n(len(d))} bills ({label})")

    work = Path("work")
    if work.is_dir():
        caps = ["captions.en.json3", "captions.en-orig.json3", "transcript.json"]
        dirs = [d for d in work.iterdir() if d.is_dir()]
        have = [d for d in dirs if any((d / c).exists() for c in caps)]
        out.append(f"- `work/`: {n(len(dirs))} recording folders, "
                   f"{n(len(have))} with captions this can read")
        # WHAT IS ON DISK FOR THE SUPERSEDED CLUSTERING PATH. These five
        # counts were a preflight data check until 1 October 2026, "what is
        # on disk for the markers to read". It asserted nothing and could not
        # fail, so it was a report filed among the checks; this is where a
        # report belongs.
        tr = [d for d in dirs if (d / "transcript.json").exists()]
        sg = [d for d in dirs if (d / "segments.json").exists()]
        both = [d for d in tr if (d / "segments.json").exists()]
        patched = 0
        for d in sg:
            try:
                if "start_stated" in (d / "segments.json").read_text(encoding="utf-8"):
                    patched += 1
            except (OSError, UnicodeDecodeError):
                pass
        out.append(f"- `work/`, for `apply_markers.py` (the superseded clustering "
                   f"path): {n(len(tr))} transcripts, {n(len(sg))} aligned, "
                   f"{n(len(both))} ready for it, {n(patched)} already patched")
    out.append("")


def section_timestamps(out):
    out.append("## Timestamps\n")
    cs = jload("candidate_segments.json", {})
    if not cs:
        out.append("No `candidate_segments.json`. Run "
                   "`python3 segment_markers.py --all --data data`.\n")
        return
    absent = cs.get("_absent", {})
    # _absent and _sequence are maps keyed on recording, beside the
    # recordings. Counting _sequence as one added a recording, every item of
    # every sequence it held as a proceeding, and its video ids as bills.
    sides = ("_absent", "_sequence")
    vids = [k for k in cs if k not in sides]
    # Proceedings, not bills: a bill heard in the morning and voted in the
    # afternoon is two, and the same bill on two recordings is two more. The
    # end count is per proceeding as well, so the two are comparable.
    segs = [s for k, v in cs.items() if k not in sides
            for ss in v.values() for s in ss]
    bills = {b for k, v in cs.items() if k not in sides for b in v}
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
    # Files, not entries. rglob yields directories as well, and this is the
    # number the file-cap decision rests on -- 100,000 on the Pro plan, not
    # the 20,000 of the free one this used to print.
    files = (sum(1 for x in site.rglob("*") if x.is_file())
             if site.is_dir() else 0)
    dirs = (sum(1 for x in site.rglob("*") if x.is_dir())
            if site.is_dir() else 0)
    # The bill index as the pages read it, one file per term
    # (site_read.bill_index): none where no site is built, and said where it
    # does not hold together rather than counted as no bills.
    try:
        idx = site_read.bill_index(site)
    except site_read.Broken as e:
        idx = f"the bill index will not read: {e}"
    out.append(f"- {n(files)} files in `site/` across {n(dirs)} folders "
               f"({files * 100 // 100000}% of the 100,000 Cloudflare Pages "
               "allows on the Pro plan)")
    if isinstance(idx, list):
        out.append(f"- {n(len(idx))} bills in the index")
    elif idx:
        out.append(f"- {idx}")
    when = b.get("finished") or b.get("when") or ""
    if when:
        out.append(f"- last built {when}")
    out.append("")


def section_checks(out):
    out.append("## Checks\n")
    if not Path("preflight.py").exists():
        out.append("`preflight.py` is not here.\n")
        return
    # THE RUN THAT JUST HAPPENED, where it was a run of this code. Otherwise
    # the record is refused, the reason is said, and the checks are run.
    rec, why_not = last_run()
    if rec:
        checks = rec["checks"]
        out.append("```\n" + tally(checks, data=False)
                   + "\ncode checks only; preflight.py with no flag runs the data "
                     "checks too\n```")
        if rec["mode"] == "all" and rec.get("data") and rec["data"] == data_state():
            out.append(f"\nThe same run's data checks: {tally(checks, data=True)}.")
        elif rec["mode"] == "all":
            # The tree's digest is of what git tracks or would; the data is
            # nearly all ignored, and a build since that run is not in it.
            out.append("\nThat run's data checks are not reported here: a data file has "
                       "been written since it read them. `python3 preflight.py` runs "
                       "them on what is here now.")
        out.append(f"\nRead from the preflight run that finished {rec.get('finished')}, "
                   f"on this commit ({str(rec['commit'])[:9]}) and this working tree; "
                   "`handoff.py` did not run it again.")
        bad = [c for c in checks if c[2] in ("FAIL", "ERROR")]
        if bad:
            out.append("\nFailing:\n")
            for c in bad[:6]:
                out.append(f"- {c[1]}")
        out.append("")
        return
    print(f"Running preflight.py --code: {why_not}.", flush=True)
    r = child.run([sys.executable, "preflight.py", "--code"],
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
    # SAY WHICH CHECKS. This runs preflight --code, which skips the data
    # checks, so the number here is smaller than the one preflight prints with
    # no flag -- and an unlabelled 48 beside an unlabelled 72 reads as checks
    # having been lost.
    out.append("```\n" + (lines[-1] if lines else
                          f"preflight exited {r.returncode}, no summary line")
               + "\ncode checks only; preflight.py with no flag runs the data "
                 "checks too\n```")
    out.append(f"\nRun by `handoff.py` just now: {why_not}.")
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
        "`ARCHITECTURE.md`",
        "and `CLAUDE.md`, which change slowly and are written by a person.",
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
              "CLAUDE.md.")


if __name__ == "__main__":
    main()
