#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.10
"""
Report what is actually on disk, and which scripts are out of date.

    python3 src/ops/inventory.py              # tree, data files, script versions
    python3 src/ops/inventory.py --full       # every filename, not just counts
    python3 src/ops/inventory.py --bump src/pages/app.js preflight.py
    python3 src/ops/inventory.py --bump-changed          # every file changed since HEAD
    python3 src/ops/inventory.py --bump-changed origin/dev

Two questions this answers that are otherwise guesswork.

WHAT IS HERE. Directory sizes, file counts, and when each data file was last
written. Enough to see at a glance that a fetch produced nothing, or that a
build ran before the file it depends on.

AM I RUNNING THE CURRENT SCRIPT. There are no version numbers in these files,
so instead each is checked for a few lines that only the current version has --
a fix, a renamed variable, a new argument. A script missing them is an older
copy that was never replaced, which has already caused several confusing hours:
a bug reported as unfixed because the fix was sitting in the downloads folder.

Nothing here writes or changes anything, except --bump and --bump-changed.

BUMPING A STAMP. Every edit to a stamped file is two more edits: the stamp's
.N in the file and its entry in versions.json (CLAUDE.md, "Version stamps"),
and forgetting one is the most common way a change here fails preflight.
--bump FILE... makes both for each file named. --bump-changed [BASE] makes
them for every stamped file that differs from BASE (HEAD unless named) and
still carries BASE's stamp -- so it is safe to run again before a commit, and
on a branch of several commits `--bump-changed origin/dev` bumps each changed
file once. The date stays: it is when the file was created. A changed file
with no stamp is listed, not stamped.
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
# versions.json says which version each file should be. Comparing the two
# answers "am I running the copy you gave me" exactly, rather than by looking
# for lines a newer version happens to contain. That guesswork was fragile in
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


def bump(paths, root):
    """Raise each file's stamp by one and its versions.json entry with it.
    Returns [(path, old, new)] and the paths that carry no stamp. Bytes are
    kept as they are -- line endings included, on Windows too."""
    vp = root / "versions.json"
    vtext = vp.read_bytes().decode("utf-8")
    listed = json.loads(vtext).get("files", {})
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
        if p.name in listed:
            want = f'"{p.name}": "{listed[p.name]}"'
            if want in vtext:
                vtext = vtext.replace(want, f'"{p.name}": "{new}"', 1)
                listed[p.name] = new
        done.append((str(f), old, new))
    vp.write_bytes(vtext.encode("utf-8"))
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
    for n in sorted(x for x in names if x and x != "versions.json"):
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
                    help="raise each file's stamp and its versions.json entry by one")
    ap.add_argument("--bump-changed", nargs="?", const="HEAD", metavar="BASE",
                    help="--bump every stamped file changed since BASE (HEAD) that still "
                         "carries BASE's stamp")
    a = ap.parse_args()
    root = Path(a.dir).resolve()
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
    print("\nSCRIPTS")
    expected = {}
    vp = root / "versions.json"
    if vp.exists():
        expected = json.loads(vp.read_text(encoding="utf-8")).get("files", {})
        print(f"  (versions.json lists {len(expected)} files)\n")
    else:
        print("  versions.json not found - versions are listed but not checked.")
        print("  Download it alongside the scripts to get the comparison.\n")

    # Every script wherever it sits: the root's and src/'s by their bare names,
    # as versions.json lists them, so a script moved under src/ is still found
    # and one nobody listed is still noticed (_paths.SCRIPT_DIRS). The
    # browser's files are found by their bare names too, in src/pages/ and
    # tests/ (_paths.BROWSER).
    old, absent, unstamped = [], [], []
    scripts = {p.name for p in _paths.code_files("*.py", root=root, dirs=_paths.SCRIPT_DIRS)}
    for name in sorted(set(expected) | scripts | {"bills.html"}):
        f = _paths.locate(name, root=root)
        if not f.exists():
            # A page that is not among the code: site/ holds the built copy,
            # which is all a machine given only the built site has.
            alt = root / "site" / name if name.endswith(".html") else None
            if alt and alt.exists():
                f = alt
            else:
                if name in expected:
                    absent.append(name)
                continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"GRANITE_VERSION:\s*(\S+?)\s*(?:-->|\*/|$)", txt, re.M)
        got = m.group(1) if m else None
        want = expected.get(name)
        if got is None:
            # If versions.json expects this file, an unstamped copy predates
            # stamping entirely -- which makes it old, not merely unlabelled.
            if want:
                old.append((name, "unstamped", want))
                print(f"  {name:<28} OUT OF DATE  no stamp   want {want}")
            else:
                unstamped.append(name)
                print(f"  {name:<28} no version stamp     {age(f)}")
        elif want and got != want:
            old.append((name, got, want))
            print(f"  {name:<28} OUT OF DATE  have {got}  want {want}")
        else:
            print(f"  {name:<28} {got:<20} {age(f)}")

    if absent:
        print(f"\n  listed but not present: {', '.join(absent)}")
    if unstamped:
        print(f"\n  no stamp yet: {', '.join(unstamped)}")

    # ---- files that should be gone -----------------------------------------
    leftover = [n for n in STALE if (root / n).exists()]
    if leftover:
        print("\nSUPERSEDED, safe to delete")
        for n in leftover:
            print(f"  {n}")

    # ---- verdict -----------------------------------------------------------
    print("\n" + "=" * 68)
    if old:
        print(f"{len(old)} file(s) are older copies. Re-download these:")
        for n, got, want in old:
            print(f"  {n:<28} {got}  ->  {want}")
        print("\nAn old copy is the usual reason a fix appears not to have")
        print("worked: the change exists, just not in the file being run.")
    elif expected:
        print("Every file matches the version it should be.")
    else:
        print("No versions.json, so nothing was compared.")
    print("=" * 68)


if __name__ == "__main__":
    main()
