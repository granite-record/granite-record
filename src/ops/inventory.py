#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.12
"""
Report what is actually on disk, and which scripts are out of date.

    python3 src/ops/inventory.py              # tree, data files, script versions
    python3 src/ops/inventory.py --full       # every filename, not just counts
    python3 src/ops/inventory.py --bump src/pages/app.js preflight.py
    python3 src/ops/inventory.py --bump-changed          # every file changed since HEAD
    python3 src/ops/inventory.py --bump-changed origin/dev
    python3 src/ops/inventory.py --write      # versions.json, from the files' stamps

Two questions this answers that are otherwise guesswork.

WHAT IS HERE. Directory sizes, file counts, and when each data file was last
written. Enough to see at a glance that a fetch produced nothing, or that a
build ran before the file it depends on.

AM I RUNNING THE CURRENT SCRIPT. Every script carries a stamp, and the stamp
in the file is the only place a version is kept: registry() reads the stamps
off the files, and the list of what each should be is never edited by hand.
versions.json, where there is one, is that list written out by --write -- a
local copy that git ignores, so no two branches can conflict over it.

Nothing here writes or changes anything, except --bump, --bump-changed and
--write.

BUMPING A STAMP. Every edit to a stamped file needs its stamp's .N raised
(CLAUDE.md, "Version stamps"); forgetting is the most common way a change
here fails preflight. --bump FILE... raises the stamp of each file named.
--bump-changed [BASE] raises it for every stamped file that differs from BASE
(HEAD unless named) and still carries BASE's stamp -- so it is safe to run
again before a commit, and on a branch of several commits
`--bump-changed origin/dev` bumps each changed file once. The date stays: it
is when the file was created. A changed file with no stamp is listed, not
stamped.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
from datetime import datetime

# Every script carries a version stamp on its second line:
#
#     # GRANITE_VERSION: 2026-09-04.2
#
# registry() reads them off the files. Against git it answers "was this file
# changed without its stamp being raised" exactly, rather than by looking for
# lines a newer version happens to contain. That guesswork was fragile in
# both directions: it missed real staleness when a fix did not add a
# distinctive line, and it cried wolf when I chose a marker badly.

# Files the pipeline reads. Their absence or staleness explains most surprises.
DATA = ["Docket.txt", "LSRs.txt", "LsrsOnly.txt", "LsrSponsors.txt",
        "RollCallSummary.txt", "RollCallHistory.txt", "legislators.txt",
        "Members.txt", "HouseDistricts.txt", "Counties.txt", "Committees.txt",
        "SubjectCodes.txt",
        "narratives.json", "rollcalls.json", "bill_status.json",
        "committee_reports.json", "senate_reports.json",
        "floor_index.json", "journals.json",
        "calendars.json", "former_members.json", "verification_manifest.csv"]

# A superseded SCRIPT does not always mean a superseded FILE. fetch_bill_titles.py
# was replaced by fetch_bill_status.py, but build_data.py still reads
# bill_titles.json as a fallback -- it holds titles recovered from the legacy
# docket pages for bills the current session's files no longer describe, which
# is the fix for the 847 bills that had a history and no title. Deleting it on
# this script's advice would quietly undo that.
#
# bill_sponsors.json is read by nothing, so it stays on the list.
STALE = ["bill_sponsors.json", "fetch_bill_titles.py",
         "fetch_rollcall_details.py", "analyze_drift.py", "build_site.py"]


def size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def age(p):
    d = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    if d.days > 0:
        return f"{d.days}d ago"
    h = d.seconds // 3600
    return f"{h}h ago" if h else f"{d.seconds // 60}m ago"


STAMP = re.compile(r"(GRANITE_VERSION:\s*)(\d{4}-\d{2}-\d{2})\.(\d+)")


def _stamp(text):
    """(date, n) of the stamp near the top of `text`, or None."""
    m = STAMP.search(text[:800])
    return (m.group(2), int(m.group(3))) if m else None


# What registry() looks at: the files of a repository that may carry a stamp,
# and the folders that never hold one (the data, the built site, the
# worktrees). The stamp is read from the first 800 bytes, as bump() does.
STAMPED = (".py", ".js", ".css", ".html", ".bat", ".sql", ".toml")
NOT_CODE = ("work/", "site/", "legislation/", "archive/", "db/", "node_modules/",
            ".git/", ".claude/worktrees/", ".build_cache/")
FULL_STAMP = re.compile(r"GRANITE_VERSION:[ \t]*(\d{4}-\d{2}-\d{2}\.\d+)\b")


def _git_names(root):
    """Tracked and untracked-but-not-ignored paths under `root`, or None
    where it is no git repository (a fixture, a bare copy)."""
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached",
                            "--others", "--exclude-standard"],
                           capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return sorted(x for x in r.stdout.decode("utf-8", "replace").split("\0") if x)


def _candidates(root):
    names = _git_names(root)
    if names is None:
        names = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    return [n for n in names if n.endswith(STAMPED) and not n.startswith(NOT_CODE)]


def _key(root, rel):
    """How the registry names a file: by its bare name where _paths finds it
    by that name, else by its path from the root (functions/api/report.js)."""
    bare = rel.rsplit("/", 1)[-1]
    try:
        if _paths.locate(bare, root=root).resolve() == (root / rel).resolve():
            return bare
    except LookupError:
        pass
    return rel


def registry(root=None):
    """{name: "YYYY-MM-DD.N"} for every stamped file under `root`, read off
    the files themselves. The one list of what each file's version is."""
    root = Path(root).resolve() if root is not None else _paths.ROOT
    out = {}
    for rel in _candidates(root):
        try:
            head = (root / rel).read_bytes()[:800].decode("utf-8", "replace")
        except OSError:
            continue
        m = FULL_STAMP.search(head)
        if m:
            out[_key(root, rel)] = m.group(1)
    return dict(sorted(out.items()))


def write_registry(root=None):
    """Write registry() to versions.json under `root`, for a tool that wants
    a file. Git ignores it, so it is never a thing two branches change."""
    root = Path(root).resolve() if root is not None else _paths.ROOT
    reg = registry(root)
    (root / "versions.json").write_text(
        json.dumps({"files": reg}, indent=2) + "\n", encoding="utf-8")
    return reg


def backwards(root, base="HEAD"):
    """The files whose stamp now is behind the stamp they had at `base`: an
    edit that took a stamp down, or a merge that kept the older one."""
    import subprocess
    out = []
    try:
        moved = set(subprocess.run(["git", "-C", str(root), "diff", "--name-only", base],
                                   capture_output=True, text=True, check=True,
                                   encoding="utf-8").stdout.split("\n"))
    except (OSError, subprocess.CalledProcessError):
        return out
    for rel in sorted(set(_candidates(root)) & moved):
        try:
            now = _stamp((root / rel).read_bytes().decode("utf-8"))
            r = subprocess.run(["git", "-C", str(root), "show", f"{base}:{rel}"],
                               capture_output=True)
        except (OSError, UnicodeDecodeError):
            continue
        if r.returncode:
            continue
        try:
            then = _stamp(r.stdout.decode("utf-8"))
        except UnicodeDecodeError:
            continue
        if now and then and (now[0], now[1]) < (then[0], then[1]):
            out.append(rel)
    return out


def bump(paths, root):
    """Raise each file's stamp by one. Returns [(path, old, new)] and the
    paths that carry no stamp. Bytes are kept as they are -- line endings
    included, on Windows too."""
    done, bare = [], []
    for f in paths:
        p = Path(f) if Path(f).is_absolute() else root / f
        raw = p.read_bytes().decode("utf-8")
        m = STAMP.search(raw[:800])
        if not m:
            bare.append(str(f))
            continue
        old = f"{m.group(2)}.{m.group(3)}"
        new = f"{m.group(2)}.{int(m.group(3)) + 1}"
        p.write_bytes((raw[:m.start()] + m.group(1) + new + raw[m.end():]).encode("utf-8"))
        done.append((str(f), old, new))
    return done, bare


def changed_since(root, base):
    """The stamped files that differ from `base` and still carry its stamp:
    the ones a commit would otherwise leave behind. And the changed files
    with no stamp at all, which are only listed."""
    import subprocess

    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8", check=True).stdout
    names = set(git("diff", "--name-only", base).split("\n"))
    names |= set(git("ls-files", "--others", "--exclude-standard").split("\n"))
    todo, bare = [], []
    for n in sorted(x for x in names if x):
        p = root / n
        if not p.is_file():
            continue
        try:
            now = _stamp(p.read_bytes().decode("utf-8"))
        except UnicodeDecodeError:
            continue
        if now is None:
            # Code with no stamp is worth saying; a document or a workflow
            # is not stamped and needs none.
            if p.suffix in (".py", ".js", ".css", ".html"):
                bare.append(n)
            continue
        try:
            then = _stamp(git("show", f"{base}:{n}"))
        except subprocess.CalledProcessError:
            then = None
        # A FILE NEW SINCE BASE KEEPS ITS FIRST STAMP: it has no earlier one
        # to move past, and bumping it on every run took strip_js.py from .1
        # to .3 in one afternoon (23 October 2026).
        if then is not None and then == now:
            todo.append(n)
    return todo, bare


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--bump", nargs="+", metavar="FILE",
                    help="raise each file's stamp by one")
    ap.add_argument("--write", action="store_true",
                    help="write versions.json from the files' stamps (git ignores it)")
    ap.add_argument("--bump-changed", nargs="?", const="HEAD", metavar="BASE",
                    help="--bump every stamped file changed since BASE (HEAD) that still "
                         "carries BASE's stamp")
    a = ap.parse_args()
    root = Path(a.dir).resolve()
    if a.write:
        reg = write_registry(root)
        print(f"  versions.json: {len(reg)} stamped files, read off the files")
        return
    if a.bump or a.bump_changed:
        bare = []
        files = a.bump or []
        if a.bump_changed:
            files, bare = changed_since(root, a.bump_changed)
        done, nostamp = bump(files, root)
        for f, old, new in done:
            print(f"  {f:<44} {old} -> {new}")
        if not done:
            print("  nothing to bump: every changed file's stamp has moved already")
        for f in nostamp + bare:
            print(f"  {f:<44} no stamp")
        return
    print("=" * 68)
    print(root)
    print("=" * 68)

    # ---- folders -----------------------------------------------------------
    print("\nFOLDERS")
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        files = [f for f in d.rglob("*") if f.is_file()]
        tot = sum(f.stat().st_size for f in files)
        subs = sorted({f.parent.relative_to(d).as_posix() for f in files
                       if f.parent != d})
        print(f"  {d.name + '/':<22} {len(files):>7,} files  {size(tot):>10}"
              + (f"   ({len(subs)} subfolders)" if subs else ""))
        if a.full and subs:
            for sname in subs[:12]:
                n = sum(1 for f in (d / sname).iterdir() if f.is_file())
                print(f"      {sname + '/':<24} {n:,}")
            if len(subs) > 12:
                print(f"      ... {len(subs) - 12} more")

    # ---- data --------------------------------------------------------------
    print("\nDATA FILES")
    missing = []
    for name in DATA:
        f = root / name
        if f.exists():
            print(f"  {name:<28} {size(f.stat().st_size):>10}   {age(f)}")
        else:
            missing.append(name)
    if missing:
        print(f"\n  not present: {', '.join(missing)}")

    # ---- script versions ---------------------------------------------------
    # The stamps are read off the files (registry); a file changed since HEAD
    # with its stamp unmoved is the one thing left to say.
    print("\nSCRIPTS")
    reg = registry(root)
    print(f"  ({len(reg)} stamped files)\n")
    scripts = {p.name for p in _paths.code_files("*.py", root=root, dirs=_paths.SCRIPT_DIRS)}
    unstamped = sorted(n for n in scripts if n not in reg)
    for name in sorted(reg):
        f = _paths.locate(name, root=root)
        print(f"  {name:<28} {reg[name]:<20} {age(f) if f.exists() else ''}")
    if unstamped:
        print(f"\n  no stamp yet: {', '.join(unstamped)}")
    old = []
    try:
        old = changed_since(root, "HEAD")[0]
    except Exception:
        pass

    # ---- files that should be gone -----------------------------------------
    leftover = [n for n in STALE if (root / n).exists()]
    if leftover:
        print("\nSUPERSEDED, safe to delete")
        for n in leftover:
            print(f"  {n}")

    # ---- verdict -----------------------------------------------------------
    print("\n" + "=" * 68)
    if old:
        print(f"{len(old)} file(s) changed since HEAD with the stamp unmoved:")
        for n in old:
            print(f"  {n}")
        print("\nRun: python3 src/ops/inventory.py --bump-changed")
    else:
        print("Every file changed since HEAD carries a raised stamp.")
    print("=" * 68)


if __name__ == "__main__":
    main()
