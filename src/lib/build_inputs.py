#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.1
"""
What the last full build was built from, and what has moved since.

    import build_inputs
    before = build_inputs.state()                  # as a build begins
    ...every step...
    build_inputs.record(before, how, facts)        # as it ends, if it ended well
    rec = build_inputs.load()                      # later
    moved = build_inputs.compare(rec, build_inputs.state(known=rec["code"]))

WHY IT EXISTS (9 October 2026, decision D24). A change to app.css waited on a
full build -- forty minutes on the laptop, more under load -- to put two
derived files into a site whose other 55,000 were going to come out byte for
byte as they were. `build_all.py --front-end` (front_end.py) puts such a
change into the site the last full build made, in seconds, and it may do that
only while nothing else the build reads has moved since. This is how it knows.

WHAT IS RECORDED, in RECORD, when a full build ends well (build_all.py):

  code   every file git sees here -- tracked, or untracked and not ignored --
         with its size, its time of writing and a sha256 of its bytes. The
         hash is what is compared: a checkout rewrites a file's time and not
         its bytes, and a fast path that refused after `git switch` and back
         would be refused for nothing.
  data   every other file under the folder, with its size and its time of
         writing, but for NOT_INPUTS. Nothing is opened: the data is
         gigabytes, and a file the build reads that is rewritten -- fetched,
         rebuilt by hand -- is rewritten with a new time.
  written  the data files the build itself wrote (their size or time moved
         between the build's start and its end). site_manifest.py keys a
         baseline on the others, which no build writes.
  dirty  the files git sees that differ from the commit, at the start;
         empty for a build of a clean checkout.
  facts  what front_end.py reads off code the build reads only in part
         (front_end.facts): data.html's counts, the search's tables.

RECORD IS NOT IN site/, which is published, and not where a night sends its
logs: it is the laptop's, and build_all.py writes none on GitHub's machine.
A build that begins removes it, because from that moment site/ is no longer
what it describes; one that fails writes none. A record whose code moved
while the build ran (a file saved mid-build) says so, and front_end.py will
not build on it.

WHAT IT CANNOT SEE: a builder run by hand into site/ after the build, with
code and data unchanged, rewrites what the build wrote with what the build
would write. A file fetched into the folder WHILE the build ran is taken as
the build left it. site_manifest.py compares the site itself, which this does
not.

Nothing here writes outside RECORD, or asks the network.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import child

RECORD = Path("logs/last-build.json")

# NEVER AN INPUT TO THE BUILD, and so never a reason to refuse. Each is here
# for a reason it states; preflight (_fast_path_inputs) holds that no script
# on the build's path names one of these folders, or a Markdown file, as a
# path it reads.
NOT_INPUTS = (
    "site",          # the output, which site_manifest.py compares
    ".git",          # git's own (a worktree's .git is a file naming it)
    ".claude",       # the assistant's worktrees, each a copy of everything
    "logs",          # every run's log, this record among them
    "private",       # the person's plans
    "reports",       # the triage's, and the assistant's reports
    "obsolete",      # code nothing runs
    "tests",         # the checks' cases; preflight reads them, no build step
    ".github",       # the workflows, which start a build and are not read by one
    ".wrangler", ".venv", "node_modules",
    "archive/cloud", # the bucket's state, rewritten by every pull
)
NOT_INPUT_NAMES = ("__pycache__",)          # at any depth
NOT_INPUT_FILES = (".build.lock",           # a build's own lock
                   "archive/.lock",         # the lane's, touched every minute
                   ".gitignore", ".gitattributes",
                   "STATE.md", "READINESS.md")
NOT_INPUT_SUFFIXES = (".md", ".pyc")        # documents: no builder reads one


def _skipped(rel):
    if rel in NOT_INPUT_FILES or rel.endswith(NOT_INPUT_SUFFIXES):
        return True
    return any(rel == d or rel.startswith(d + "/") for d in NOT_INPUTS)


def walk(root=".", skip=True):
    """(relative posix path, os.stat_result) for every file under root that
    is not one of NOT_INPUTS (every file, with skip=False), in no particular
    order. Links and junctions are not followed: a folder reached twice
    would be counted twice."""
    root = Path(root)
    todo = [""]
    while todo:
        rel = todo.pop()
        try:
            entries = list(os.scandir(root / rel if rel else root))
        except OSError:
            continue
        for e in entries:
            name = f"{rel}/{e.name}" if rel else e.name
            if skip and (e.name in NOT_INPUT_NAMES or _skipped(name)):
                continue
            try:
                if e.is_symlink() or (hasattr(e, "is_junction") and e.is_junction()):
                    continue
                if e.is_dir(follow_symlinks=False):
                    todo.append(name)
                elif e.is_file(follow_symlinks=False):
                    yield name, e.stat(follow_symlinks=False)
            except OSError:
                continue


def git_files(root="."):
    """{posix path} of every file git sees in this folder -- tracked, or
    untracked and not ignored -- or None where the folder is not the top of
    a repository (a fixture under the temp directory, a copy)."""
    try:
        top = child.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                        capture_output=True, text=True, timeout=60)
        if top.returncode != 0 or not os.path.samefile(top.stdout.strip(), root):
            return None
        r = child.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                      cwd=root, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return {n for n in (r.stdout or "").split("\0") if n}


def git_head(root="."):
    """(commit, [paths git sees that differ from it]), or (None, None)."""
    try:
        head = child.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                         text=True, timeout=60)
        st = child.run(["git", "status", "--porcelain", "-z", "--untracked-files=all"],
                       cwd=root, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None, None
    if head.returncode != 0 or st.returncode != 0:
        return None, None
    fields, dirty, i = (st.stdout or "").split("\0"), [], 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        if "R" in entry[:2] or "C" in entry[:2]:
            i += 1                                  # the name it came from
        dirty.append(entry[3:])
    return head.stdout.strip(), sorted(dirty)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def state(root=".", known=None):
    """{"code": {path: [size, mtime_ns, sha256]}, "data": {path: [size,
    mtime_ns]}} for every input under root (walk). `known` is an earlier
    state's "code": a file whose size and time it gives is not read again,
    so asking after a full build costs a walk and a hash of what moved."""
    root = Path(root)
    seen = git_files(root)
    known = known or {}
    code, data = {}, {}
    for rel, st in walk(root):
        size, mtime = st.st_size, st.st_mtime_ns
        if seen is not None and rel in seen:
            was = known.get(rel)
            if was and was[0] == size and was[1] == mtime and was[2]:
                code[rel] = [size, mtime, was[2]]
            else:
                try:
                    code[rel] = [size, mtime, sha256(root / rel)]
                except OSError:
                    continue
        else:
            data[rel] = [size, mtime]
    return {"code": code, "data": data}


def compare(rec, now):
    """[(path, what)] for every input that differs between a record (or a
    state) and a later state, sorted: what is "changed", "added" or
    "removed". A file is the same when its bytes are (code) or its size and
    time of writing are (data); one that git began or stopped seeing is
    compared by its size and time."""
    out = []
    old ={**{p: ("data", v) for p, v in rec["data"].items()},
           **{p: ("code", v) for p, v in rec["code"].items()}}
    new = {**{p: ("data", v) for p, v in now["data"].items()},
           **{p: ("code", v) for p, v in now["code"].items()}}
    for p in sorted(set(old) | set(new)):
        if p not in new:
            out.append((p, "removed"))
        elif p not in old:
            out.append((p, "added"))
        else:
            (ka, a), (kb, b) = old[p], new[p]
            same = a[2] == b[2] if ka == kb == "code" else a[:2] == b[:2]
            if not same:
                out.append((p, "changed"))
    return out


def written_during(before, after):
    """The data files a build wrote: new at its end, or moved in size or
    time between its start and its end."""
    return sorted(p for p, v in after["data"].items() if before["data"].get(p) != v)


def code_moved(before, after):
    """The files git sees whose bytes moved while the build ran."""
    return sorted(p for p in set(before["code"]) | set(after["code"])
                  if (before["code"].get(p) or [None] * 3)[2]
                  != (after["code"].get(p) or [None] * 3)[2])


def forget(path=RECORD):
    """Remove the record: site/ is about to stop being what it describes."""
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


def site_build_sha(site="site"):
    """sha256 of site/build.json, which ties a record to the build that
    wrote it, or None where there is none."""
    p = Path(site) / "build.json"
    return sha256(p) if p.is_file() else None


def record(before, how, facts, site="site", path=RECORD, commit=None, dirty=None, root="."):
    """Write the record of a build that ended well: the state at its end,
    what it wrote, what moved under it, and what it was asked to do. Returns
    the record."""
    after = state(root, known=before["code"])
    moved = code_moved(before, after)
    try:
        finished = json.loads((Path(site) / "build.json").read_text(encoding="utf-8"))["finished"]
    except (OSError, ValueError, KeyError, TypeError):
        finished = None
    rec = {
        "finished": finished,
        "commit": commit, "dirty": dirty, "how": how,
        "site_build": site_build_sha(site),
        "usable": not moved,
        "code_moved": moved[:50],
        "facts": facts,
        "written": written_during(before, after),
        "code": after["code"], "data": after["data"],
        "fast": [],
    }
    save(rec, path)
    return rec


def save(rec, path=RECORD):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".part")
    tmp.write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)


def load(path=RECORD):
    """The record, or None where there is none or it will not read."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
