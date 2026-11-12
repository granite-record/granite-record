#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.3
"""
The quick preview: a change to the browser's files, seen in minutes on GitHub.

    python3 src/ops/quick_preview.py plan   [--site site]
    python3 src/ops/quick_preview.py apply  [--site site]
    python3 src/ops/quick_preview.py check  [--site site]
    python3 src/ops/quick_preview.py deploy [--site site]

THE WORKFLOW (.github/workflows/preview.yml) RUNS THESE IN THIS ORDER, after
`cloud.py site-down --latest` has unpacked the last night fit for production
into site/. The recommendation is 1 of reports/faster-updates-and-live-2026-11.md,
approved by the owner on 11 November 2026: a dry run is 36 to 56 minutes and a
visual change needs the answer to "how does it look", not to "is the data
whole".

  plan    which commit built the site in site/ (its build.json names it, nightly.
          stamp_commit), what differs between that commit's tree and this
          checkout's, and whether every difference is something the fast path
          (front_end.py) can put into that site. It goes on only if so, and
          where it does not it says which file, and why, and leaves the full
          dry run as the way to see the change.
  apply   build_pages.front_end -- the function the full build's own step and
          `build_all.py --front-end` both call -- over site/. What it writes
          is what a full build of this checkout would write, because it is the
          same code (preflight: _quick_preview).
  check   check_site.py and `preflight.py --built` on the result, and a verdict.
  deploy  to the Pages preview alias QUICK_BRANCH, never to production, then
          the same look at what that address serves as the night's own preview
          takes.

WHAT IT NEVER DOES. It writes no verdict of the night, no census, no gate
record, nothing to the bucket's kit or state or nights/ (it holds the bucket's
READ keys only, for site-down), nothing under corrections/ or review/, and it
asks the General Court nothing. It does not deploy to PRODUCTION_BRANCH, the
night's PREVIEW_BRANCH or a dry run's DRY_PREVIEW_BRANCH (preflight holds the
four names apart): the night waiting for approval is approved from its own
address, and this must not replace it. The page it deploys carries
quick-preview.html and quick-preview.json saying it is a front-end preview over
the night of a stated day, and is not a build to publish from.

WHAT IT MAY APPLY (judge). The paths that differ between the archive's commit
and this checkout, each one of:

  - src/pages/app.css, app.js, components.js, find.js, print.js, print.css:
    front_end.fast_files(), modified and not added or removed; for app.js only
    while its search tables (SYN, CONCEPTS, STOP) are unchanged, since a
    changed table also changes site/sidx/, which this does not rebuild;
  - a path no build step reads (build_inputs.NOT_INPUTS: logs, tests, reports,
    private, .github, ...; any .md): said, and ignored.

Everything else is refused by name: a data file, bills.html (the template of
every record page), chrome.py (the header, nav and footer of every page), a
words file, any script, preflight.py, functions/.

THE ONE TRUST THIS DEPENDS ON. The code that decides is the checkout's own, as
it is for every run of a branch. A run must be started by a person with write
access to the repository, as a dry run is, and the Pages token reaches only the
deploy step, as in nightly.yml.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import os
import re
import time
from datetime import datetime

import child

SITE = "site"
# The alias the preview is deployed to: https://quick.<project>.pages.dev.
# Not the night's preview ("nightly"), not a dry run's ("dry-run"), not
# production ("master"): preflight holds the four apart.
QUICK_BRANCH = "quick"
PROJECT = "graniterecord"
PLAN = Path("logs/quick-preview-plan.json")
VERDICT = Path("logs/quick-preview-verdict.json")
BUILT_CHECKS = Path("logs/built-checks.json")
STAMP_JSON = "quick-preview.json"
STAMP_PAGE = "quick-preview.html"
# The bucket's lifecycle rule deletes a night three days on; one a day older
# than that cannot have come from it, and is refused rather than shown.
MAX_AGE_DAYS = 4
COMMIT = re.compile(r"[0-9a-f]{40}")

# Why a path is refused, by what it is.
WHY_TEMPLATE = ("the template every record page is built from (shell.template): a change to "
                "it reaches every page of the site, which only the page steps of a full "
                "build rebuild")
WHY_CHROME = ("the header, nav and footer of every page, written into each page by the page "
              "steps of a full build")
WHY_WORDS = ("the words the pages are drawn from (components.py and the page builders read "
             "them), written into pages by a full build")
WHY_SCRIPT = ("a script of the build or of the checks: the night's pages were made by the "
              "base commit's copy of it, and only a full build says what this one makes")
WHY_DATA = "data the build reads: the pages in the night's site were made from the old one"
WHY_OTHER = "a file the build reads, which only a full build can put into the site"
DATA_FOLDERS = ("data/", "corrections/", "review/", "archive/", "db/", "records/",
                "legislation/", "work/", "assets/", "brand/", "nh-archive/", "bill_status/",
                "dynamicdatadump/")


def fast_files():
    import front_end
    return front_end.fast_files()


def _not_an_input(path):
    import build_inputs as BI
    return BI._skipped(path)


def why_refused(path):
    """Why `path`, which differs and which the fast path does not apply, is
    refused: said by what it is."""
    import front_end
    if path == front_end.TEMPLATE:
        return WHY_TEMPLATE
    if path.endswith("/chrome.py") or path == "chrome.py":
        return WHY_CHROME
    if "src/pages/words/" in path or path.startswith("words/"):
        return WHY_WORDS
    if path.startswith(DATA_FOLDERS):
        return WHY_DATA
    if path.endswith(".py") or path == "preflight.py":
        return WHY_SCRIPT
    return WHY_OTHER


def judge(changes, tables=None):
    """(apply, ignored, refused) for `changes`, [(status, path)] as
    `git diff --name-status` gives them (M, A, D, T); `tables` is (the base's
    search-tables digest, this checkout's) of app.js, needed only where app.js
    differs. refused is [(path, why)]; the preview goes on only where it is
    empty. A pure function of its arguments, which preflight tries on each
    kind of path there is."""
    fast = fast_files()
    apply, ignored, refused = [], [], []
    for status, path in changes:
        if path in fast:
            if status != "M":
                refused.append((path, ("added" if status == "A" else "removed" if status == "D"
                                       else "its kind changed") + ": a file the night's site "
                                "does not hold in this form cannot be made by writing the "
                                "browser's files over it"))
            elif path == "src/pages/app.js" and (
                    not tables or tables[0] is None or tables[1] is None
                    or tables[0] != tables[1]):
                refused.append((path, "its search tables (SYN, CONCEPTS, STOP) moved, or could "
                                "not be read, and site/sidx/ is made from them by a step this "
                                "preview does not run"))
            else:
                apply.append(path)
        elif _not_an_input(path):
            ignored.append(path)
        else:
            refused.append((path, why_refused(path)))
    return sorted(apply), sorted(ignored), sorted(refused)


def git(*args, check=True, cwd=None):
    r = child.run(["git", *args], capture_output=True, cwd=cwd)
    out = r.stdout or ""
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])}: {(r.stderr or out).strip()[-200:]}")
    return out, r.returncode


def git_changes(base, head="HEAD", cwd=None):
    """[(status, path)] between two commits' trees, renames taken as a removal
    and an addition, sorted by path."""
    out, _ = git("diff", "--name-status", "--no-renames", "-z", base, head, cwd=cwd)
    parts = out.split("\0")
    pairs = []
    for i in range(0, len(parts) - 1, 2):
        if parts[i]:
            pairs.append((parts[i][0], parts[i + 1]))
    return sorted(pairs, key=lambda p: p[1])


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def night_of(site):
    """(commit, finished, why_not): what the archive's build.json says built
    it. why_not is a sentence where it cannot serve as a baseline."""
    b = _read_json(Path(site) / "build.json")
    if not isinstance(b, dict):
        return None, None, f"{site}/build.json is missing or does not read"
    commit, finished = b.get("commit"), b.get("finished")
    if not COMMIT.fullmatch(str(commit or "")):
        return None, finished, (f"{site}/build.json names no commit (a full 40-character id), "
                                "so what the night was built from is not known; this is not a "
                                "night's archive, or an older one than the stamp")
    if b.get("ok") is False:
        return commit, finished, "the archive's build did not finish ok"
    try:
        age = (datetime.now() - datetime.fromisoformat(str(finished))).total_seconds() / 86400
    except ValueError:
        return commit, finished, f"{site}/build.json's finished ({finished!r}) is not a time"
    if age > MAX_AGE_DAYS:
        return commit, finished, (f"the archive is {age:.1f} days old; the bucket keeps a "
                                  f"night three days and this refuses past {MAX_AGE_DAYS}")
    return commit, finished, ""


def cmd_plan(a):
    site = Path(a.site)
    commit, finished, why_not = night_of(site)
    plan = {"allowed": False, "base_commit": commit, "night_finished": finished,
            "apply": [], "ignored": [], "refused": []}

    def done(code):
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(plan, indent=1), encoding="utf-8")
        return code
    if why_not:
        print(f"REFUSED: {why_not}.")
        plan["refused"] = [[f"{site}/build.json", why_not]]
        return done(2)
    try:
        head, _ = git("rev-parse", "--verify", "HEAD^{commit}")
        head = head.strip()
        plan["head_commit"] = head
        _, rc = git("cat-file", "-e", f"{commit}^{{commit}}", check=False)
        if rc != 0:
            why = (f"the commit the night was built from ({commit[:12]}) is not in this "
                   "checkout, so what changed since cannot be told (check out with full history)")
            print(f"REFUSED: {why}.")
            plan["refused"] = [["(history)", why]]
            return done(2)
        _, dirty = git("diff", "--quiet", "HEAD", check=False)
        if dirty != 0:
            why = "the checkout has uncommitted changes to tracked files; the preview is of a commit"
            print(f"REFUSED: {why}.")
            plan["refused"] = [["(checkout)", why]]
            return done(2)
        changes = git_changes(commit, "HEAD")
    except RuntimeError as e:
        print(f"REFUSED: git cannot say what changed ({e}).")
        plan["refused"] = [["(git)", str(e)]]
        return done(2)
    tables = None
    if any(p == "src/pages/app.js" and s == "M" for s, p in changes):
        import front_end
        old, _ = git("show", f"{commit}:src/pages/app.js", check=False)
        new = Path("src/pages/app.js").read_text(encoding="utf-8")
        tables = (front_end.search_tables_digest(old) if old else None,
                  front_end.search_tables_digest(new))
    apply, ignored, refused = judge(changes, tables)
    plan.update({"apply": apply, "ignored": ignored, "refused": [list(r) for r in refused]})
    print(f"The night's archive: built {finished} from commit {commit[:12]}.")
    print(f"This checkout:       {head[:12]}; {len(changes)} file(s) differ.")
    for p in apply:
        print(f"  will apply   {p}")
    for p in ignored:
        print(f"  ignored      {p}  (no build step reads it)")
    if refused:
        print(f"\nREFUSED: {len(refused)} changed file(s) are not ones the quick preview can "
              "put into the night's site:")
        for p, why in refused[:25]:
            print(f"  {p}: {why}")
        if len(refused) > 25:
            print(f"  ...and {len(refused) - 25:,} more")
        print("\nThe full dry run is the way to see this change (Actions -> nightly -> Run "
              "workflow, dry run). If the work is only the browser's files, cut the branch "
              "from main so that only they differ.")
        return done(2)
    if not apply:
        print("\nNothing the site is made of differs: the preview will be the night's site "
              "as it is.")
    plan["allowed"] = True
    return done(0)


def mark_in_site(site):
    """Whether the night's build had the header mark, which decides whether
    app.css went into its site with the mark's block (build_pages.front_end's
    has_mark): the build places the mark's file beside the pages, so its
    presence in the archive is the answer the build gave. A clone has no logo,
    so asking assets/ here, as the laptop's fast path does, would be wrong."""
    import build_pages as BP
    return (Path(site) / BP.HEADER_MARK).is_file()


def cmd_apply(a):
    plan = _read_json(PLAN)
    if not isinstance(plan, dict) or plan.get("allowed") is not True:
        print(f"REFUSED: {PLAN} does not say the change may be applied; run plan first.")
        return 2
    site = Path(a.site)
    if not (site / "build.json").is_file():
        print(f"REFUSED: {site}/ holds no night's site.")
        return 2
    import build_pages as BP
    t0 = time.time()
    has_mark = mark_in_site(site)
    wrote = BP.front_end(site, has_mark)
    stamp = {
        "preview": "front-end only",
        "says": ("A preview of a change to the browser's files over the night's site of "
                 f"{plan.get('night_finished')} (commit {str(plan.get('base_commit'))[:12]}). "
                 "Everything else here is that night's. Not a build to publish from."),
        "night_commit": plan.get("base_commit"), "night_finished": plan.get("night_finished"),
        "checkout_commit": plan.get("head_commit"), "applied": plan.get("apply"),
        "wrote": wrote, "mark": has_mark,
        "at": datetime.now().isoformat(timespec="seconds")}
    (site / STAMP_JSON).write_text(json.dumps(stamp, indent=1), encoding="utf-8")
    (site / STAMP_PAGE).write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="robots" content="noindex"><title>Front-end preview</title></head><body>'
        "<h1>Front-end preview</h1><p>" + stamp["says"].replace("&", "&amp;").replace("<", "&lt;")
        + "</p></body></html>\n", encoding="utf-8")
    print(f"\nwrote {len(wrote)} file(s) into {site}/: {', '.join(wrote) or 'none changed'}; "
          f"{time.time() - t0:.1f}s. Everything else is the night's.")
    return 0


def cmd_check(a):
    site = Path(a.site)
    results = {}
    t0 = time.time()
    sys.stdout.flush()
    r = child.run([sys.executable, _paths.script("check_site.py"), "--site", str(site),
                   "--base", "https://graniterecord.org"])
    results["check_site"] = r.returncode == 0
    print(f"\ncheck_site: {'passed' if r.returncode == 0 else 'FAILED'} ({time.time() - t0:.0f}s)")
    if BUILT_CHECKS.exists():
        BUILT_CHECKS.unlink()
    t0 = time.time()
    sys.stdout.flush()
    child.run([sys.executable, _paths.script("preflight.py"), "--built"])
    rows = _read_json(BUILT_CHECKS)
    if not isinstance(rows, list) or not rows:
        results["built"] = False
        failed, ran = ["the built-site checks wrote no list"], 0
    else:
        bad = [r for r in rows if isinstance(r, dict) and r.get("status") in ("FAIL", "ERROR")]
        failed = [str(r.get("name")) for r in bad]
        ran = sum(1 for r in rows if isinstance(r, dict) and r.get("status") == "ok")
        results["built"] = not bad
    print(f"preflight --built: {ran} passed, {len(failed)} failed ({time.time() - t0:.0f}s)")
    for n in failed[:20]:
        print(f"  FAILED: {n}")
    ok = all(results.values())
    VERDICT.parent.mkdir(parents=True, exist_ok=True)
    VERDICT.write_text(json.dumps({"ok": ok, "results": results, "failed": failed},
                                  indent=1), encoding="utf-8")
    print(f"\nVERDICT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def preview_url(project=PROJECT):
    return f"https://{QUICK_BRANCH}.{project}.pages.dev"


def summary(lines):
    """Appended to the run's page where GitHub gives a file for it."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def cmd_deploy(a):
    import nightly as NI
    # The four names stand apart, or this could replace what a night waiting
    # for approval is approved from.
    if len({QUICK_BRANCH, NI.PREVIEW_BRANCH, NI.DRY_PREVIEW_BRANCH, NI.PRODUCTION_BRANCH}) != 4:
        print("REFUSED: the quick preview's branch is one of nightly.py's.")
        return 2
    plan, verdict = _read_json(PLAN), _read_json(VERDICT)
    if not isinstance(plan, dict) or plan.get("allowed") is not True:
        print(f"REFUSED: {PLAN} does not allow the preview.")
        return 2
    if not isinstance(verdict, dict) or verdict.get("ok") is not True:
        print(f"REFUSED: {VERDICT} does not say the checks passed.")
        return 2
    site = Path(a.site)
    if not (site / STAMP_JSON).is_file():
        print(f"REFUSED: {site}/ is not a site apply has stamped as a preview.")
        return 2
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        print("REFUSED: no CLOUDFLARE_API_TOKEN: nothing is deployed.")
        return 2
    base = preview_url(a.project)
    for attempt in range(1, 5):
        r = child.run(["npx", "--yes", NI.WRANGLER, "pages", "deploy", str(site),
                       f"--project-name={a.project}", f"--branch={QUICK_BRANCH}",
                       "--commit-dirty=true"],
                      capture_output=True, shell=(sys.platform == "win32"))
        out = (r.stdout or "") + (r.stderr or "")
        for ln in out.rstrip().splitlines()[-12:]:
            print("  " + ln)
        if r.returncode == 0:
            break
        print(f"  upload attempt {attempt} of 4 failed")
    else:
        print("STOPPED: the deploy failed four times. Nothing else was touched.")
        return 1
    landed = False
    for i, wait in enumerate(NI.LIVE_WAITS, 1):
        time.sleep(wait)
        r = child.run([sys.executable, _paths.script("check_live.py"), "--gate", "--base", base,
                       "--site", str(site)])
        if r.returncode == 0:
            landed = True
            break
        print(f"  look {i} of {len(NI.LIVE_WAITS)}: {base} is not serving the build yet")
    line = (f"Quick preview {'LIVE' if landed else 'DEPLOYED, BUT NOT YET SERVING WHAT WAS BUILT'}"
            f": {base}  (front-end only, over the night of "
            f"{plan.get('night_finished')}; applied: {', '.join(plan.get('apply') or []) or 'nothing'})")
    print("\n" + line)
    summary(["### Quick preview", "", line])
    return 0 if landed else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="The quick preview of a change to the browser's files.")
    ap.add_argument("command", choices=("plan", "apply", "check", "deploy"))
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--project", default=PROJECT)
    a = ap.parse_args(argv)
    code = {"plan": cmd_plan, "apply": cmd_apply, "check": cmd_check, "deploy": cmd_deploy}[a.command](a)
    if a.command == "plan":
        summary(["### Quick preview: " + ("may go on" if code == 0 else "refused"), ""]
                + [f"- refused `{p}`: {w}" for p, w in (_read_json(PLAN) or {}).get("refused", [])])
    return code


if __name__ == "__main__":
    sys.exit(main())
