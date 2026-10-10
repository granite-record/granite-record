#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.2
"""
A change to the browser's files, put into the site the last full build made.

    python3 build_all.py --front-end               # app.css, components.js, app.js, find.js: seconds
    python3 build_all.py --front-end --dry-run     # what it would do, or why it will not

THE FAST PATH (decision D24, 9 October 2026). The person asked to stop waiting
forty minutes on a full build to see a change to app.css, when every page but
two derived files was going to come out of it byte for byte as it was. This
puts such a change into site/ as the full build would have: it calls the
build's own code for it (build_pages.front_end, which main() calls too), so
what it writes is what the step writes.

IT REFUSES, AND SAYS WHY, when anything else the build reads has moved since
the last full build -- a script, a data file, a fetch, a hand-run step that
rewrote a file the build reads -- because then the rest of site/ is no
longer what a build of this folder would make. build_all.py records what each
full build was built from as it ends (build_inputs.py, logs/last-build.json);
this compares the folder with that record and goes on only where every file
that moved is one of these:

  src/pages/app.css   site/app.css (without the mark's block where the build
                      has no mark) and site/style.css, which build_pages
                      makes of app.css's palette and regions
  src/pages/app.js    site/app.js and site/billmatch.js -- and site/sidx/, if
                      the search's tables in it (SYN, CONCEPTS, STOP) moved,
                      by running the search-index step as the build does
                      (about two minutes)
  src/pages/find.js   site/find.js
  src/pages/          site/components.js, with the words of src/pages/words/
    components.js     written between its markers (build_pages.with_words);
                      a change to a words file is not one of these, since
                      components.py draws the built pages with the same words
  versions.json,     read by the build only for data.html's two counts
  preflight.py        (build_exports.repo_facts): where a count moved, the
                      bulk-downloads step runs again as the build runs it;
                      where none did, the change is nothing to the site

and whatever else build_pages.COPIED names, but bills.html. A CHANGE TO
bills.html IS REFUSED: it is the template every record page is built from
(shell.template), and the theme control on every page build_pages writes
(build_pages.themer), so it reaches every page of the site with the data in
it, and only the page steps of a full build can rebuild those.

What it writes is said, file by file, and that everything else is the full
build's. The record is brought up to date, so a second change builds on the
first. site/build.json is left alone: it says when the data was rebuilt, and
it was not.

IT IS NOT A BUILD TO PUBLISH FROM. It is for seeing a change; publish builds
in full. The proof that it writes what a full build writes is
_fast_path_matches_the_build in preflight, on the fixture, and the byte for
byte comparison with a full build recorded in its commit.
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
import time

import build_inputs as BI
import child

SITE = Path("site")
TEMPLATE = "src/pages/bills.html"
TEMPLATE_WHY = ("the template every record page is built from (shell.template) and the "
                "theme control on every page build_pages writes (build_pages.themer): a "
                "change to it reaches every page of the site, which only the page steps "
                "of a full build rebuild")
# The files the build reads only in part, for data.html's two counts.
FACT_SOURCES = ("versions.json", "preflight.py")
# Which build step makes what a fact is read for: run again, as the build
# runs it, when the fact moved.
RERUN = {"search_tables": ("build_search_index.py", "site/sidx/, from app.js's search tables"),
         "repo": ("build_exports.py", "data.html, which counts the stamped files and the checks")}


def fast_files():
    """The repository paths of the browser's files this puts into a site:
    what build_pages copies, but the template."""
    import build_pages as BP
    return {f"src/pages/{n}" for n in BP.COPIED} - {TEMPLATE}


def facts():
    """What the build reads of the code it reads only in part: data.html's
    counts (build_exports.repo_facts) and a digest of the search's tables
    in app.js (build_search_index.table_terms). A fact that cannot be read
    is None, and a None that was not None before refuses."""
    out = {"repo": None, "search_tables": None}
    try:
        import build_exports
        out["repo"] = build_exports.repo_facts()
    except Exception:                                           # noqa: BLE001
        pass
    try:
        import build_search_index as SI
        app = Path("src/pages/app.js")
        if app.exists():
            tables = SI.table_terms(app.read_text(encoding="utf-8"))
            out["search_tables"] = hashlib.sha256(
                json.dumps(tables, sort_keys=True).encode("utf-8")).hexdigest()
    except (Exception, SystemExit):                             # noqa: BLE001
        pass
    return out


def _preflight_path():
    try:
        return _paths.locate("preflight.py").resolve().relative_to(
            Path(".").resolve()).as_posix()
    except ValueError:
        return "preflight.py"


def judge(rec, now, now_facts):
    """(fast, fact_moved, refused, reruns) for a record and the state now:

      fast       the browser's files that moved, which this writes
      fact_moved the FACT_SOURCES that moved
      refused    [(path, why)] for everything else that moved
      reruns     the RERUN keys whose fact moved
    """
    fast_set = fast_files()
    sources = {_preflight_path() if s == "preflight.py" else s for s in FACT_SOURCES}
    fast, fact_moved, refused = [], [], []
    for path, what in BI.compare(rec, now):
        if path in fast_set:
            fast.append(path)
        elif path == TEMPLATE:
            refused.append((path, f"{what}: it is {TEMPLATE_WHY}"))
        elif path in sources:
            fact_moved.append(path)
        else:
            refused.append((path, what))
    old = rec.get("facts") or {}
    reruns = [k for k in RERUN if old.get(k) != now_facts.get(k)]
    for k in reruns:
        if now_facts.get(k) is None:
            refused.append((RERUN[k][0], f"what the build reads for {RERUN[k][1]} could "
                                         "not be read here"))
    return fast, fact_moved, refused, reruns


def _steps(how):
    """build_all's plan, as the recorded build was asked for it."""
    import build_all
    a = argparse.Namespace(session=how.get("session"), base=how.get("base"),
                           archive=how.get("archive", "nh-archive"), allow_prune=False)
    return {s.args[0]: s for s in build_all.plan(a)}


def _say_refused(refused, rec):
    print("\nREFUSED: the fast path puts a change to the browser's files into the site the "
          "last full build made, and more than those has moved since that build "
          f"(finished {rec.get('finished')}, commit {str(rec.get('commit'))[:10]}):")
    for path, why in refused[:15]:
        print(f"  {path}: {why}")
    if len(refused) > 15:
        print(f"  ...and {len(refused) - 15:,} more")
    print("\nA build of this folder would differ from site/ by more than the fast path "
          "writes. Run the full build: python3 build_all.py --local")


def run(a):
    """`build_all.py --front-end`; returns the exit status."""
    t0 = time.time()
    rec = BI.load()
    if rec is None:
        print(f"REFUSED: there is no record of a full build here ({BI.RECORD}). A full "
              "build writes one when it ends well, and the fast path builds only on that: "
              "python3 build_all.py --local")
        return 2
    if not rec.get("usable", False):
        print(f"REFUSED: the full build of {rec.get('finished')} ran while code changed under "
              f"it ({', '.join(rec.get('code_moved') or [])[:300]}), so site/ is not a build "
              "of any one state of the code. Build again: python3 build_all.py --local")
        return 2
    if BI.site_build_sha(SITE) != rec.get("site_build"):
        print(f"REFUSED: {SITE}/build.json is not the one the recorded build wrote, so "
              f"{SITE}/ is not that build's: another build, or a copy, has been here since. "
              "Build again: python3 build_all.py --local")
        return 2
    now = BI.state(known=rec["code"])
    now_facts = facts()
    fast, fact_moved, refused, reruns = judge(rec, now, now_facts)
    if refused:
        _say_refused(refused, rec)
        return 2
    how = rec.get("how") or {}
    if not fast and not reruns:
        print(f"Nothing the site is built from has moved since the full build of "
              f"{rec.get('finished')}"
              + (f" ({', '.join(fact_moved)} moved, and nothing the build reads of "
                 "them did)" if fact_moved else "")
              + f": {SITE}/ is current.")
        return 0
    steps = _steps(how)
    for k in reruns:
        if RERUN[k][0] not in steps:
            print(f"REFUSED: {RERUN[k][1]} moved, and build_all's plan has no "
                  f"{RERUN[k][0]} step to make it again")
            return 2
    print(f"front end only, on the full build of {rec.get('finished')} "
          f"(commit {str(rec.get('commit'))[:10]}):")
    for p in fast:
        print(f"  {p} moved")
    for p in fact_moved:
        print(f"  {p} moved" + ("" if reruns else ", and nothing the build reads of it did"))
    for k in reruns:
        print(f"  {RERUN[k][1]}: the {RERUN[k][0]} step runs again, as the build runs it")
    if a.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    import build_all
    import build_date
    import build_pages as BP
    # A STEP RUN AGAIN IS GIVEN THE BUILD'S DAY where the build was given one,
    # so that what it dates (data.html, the downloads' manifest) is the day
    # the rest of the site carries. Where the build read the clock, so does
    # the step, as any build made now would.
    # (child.run lays what it is given over this process's environment, so
    # a day this shell states and the build did not is taken out here.)
    os.environ.pop(build_date.ENV, None)
    env = {build_date.ENV: how["date_env"]} if how.get("date_env") else {}
    with build_all.building():
        wrote = BP.front_end(SITE, BP.header_mark_placed())
        ran = []
        for k in reruns:
            s = steps[RERUN[k][0]]
            print(f"  running {s.name} ({' '.join(s.args)})", flush=True)
            st = time.time()
            r = child.run([sys.executable, _paths.script(s.args[0])] + s.args[1:],
                          capture_output=True, text=True, env=env)
            if r.returncode != 0:
                print(f"  FAILED after {time.time() - st:.1f}s: "
                      + ((r.stderr or r.stdout or "").strip().splitlines() or ["?"])[-1])
                # site/ now holds part of a change: no record describes it.
                BI.forget()
                print(f"\n{BI.RECORD} is removed: {SITE}/ is no longer what it described. "
                      "Build in full: python3 build_all.py --local")
                return 1
            ran.append(f"{s.name} ({time.time() - st:.0f}s)")
        # The record is brought up to date: what was taken in is now what the
        # site was built from. Whatever else moved while this ran is left as
        # it was recorded, so the next run refuses on it.
        after = BI.state(known=now["code"])
        for p in fast + fact_moved:
            for kind, other in (("code", "data"), ("data", "code")):
                if p in after[kind]:
                    rec[kind][p] = after[kind][p]
                    rec[other].pop(p, None)
        rec["facts"] = facts()
        rec["fast"] = (rec.get("fast") or []) + [{
            "moved": fast + fact_moved, "wrote": wrote, "ran": ran}]
        BI.save(rec)
    print(f"\nwrote {len(wrote)} file(s) into {SITE}/: {', '.join(wrote) or 'none changed'}"
          + (f"; ran {', '.join(ran)}" if ran else "")
          + f"; {time.time() - t0:.1f}s.")
    print(f"Everything else in {SITE}/ is the full build of {rec.get('finished')}. This is "
          "not a build to publish from: publish builds in full.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="build_all.py --front-end: a change to the "
                                             "browser's files, into the site the last full "
                                             "build made")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would be written, or why it will not be, and write nothing")
    ap.add_argument("--facts", action="store_true",
                    help="print what the build reads of versions.json, preflight.py and "
                         "app.js's search tables, as JSON (build_all.py records it)")
    a = ap.parse_args()
    if a.facts:
        print(json.dumps(facts(), sort_keys=True))
        return
    sys.exit(run(a))


if __name__ == "__main__":
    main()
