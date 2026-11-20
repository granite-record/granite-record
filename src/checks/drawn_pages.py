#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.5
"""
What the browser draws on a built site's pages, written down, so that two
builds can be compared by what a reader is shown and not only by the HTML.

    python3 src/checks/drawn_pages.py --site <site> --out <dir>
    python3 src/checks/drawn_pages.py --compare <dir> <dir>

WHY. A bill's, a legislator's and a committee's page is app.js drawing a JSON
record in the browser, and the bill search, the home page and the Calendar
draw part of themselves the same way. A sha256 manifest of the built site
proves the HTML and the records unchanged and says nothing of what the
scripts make of them, so a change meant to move nothing (the component plan's
"nothing should move" steps, 9 October 2026) is proved by comparing this
tool's output as well.

WHAT IT DRAWS. Every bill, legislator and committee page under --site, at its
own address and at the address of each of its tabs (the slugs the site's
_redirects serves), and the bill search, the home page, the Calendar, the
all-results search and the legislators page. Each page's scripts run in node
as a browser runs them: every classic script in the order the page names it,
an external one read from the site (components.js in the head, app.js,
find.js) and an inline one from the page, the deferred ones after, then
DOMContentLoaded and load. They run against tests/dom_stub.js, the stand-in
preflight runs app.js against, told only what the page itself holds: an
element is there if the page or something already drawn carries its id, a
record's JSON is the page's own, and fetch is answered from the site folder.
The day is fixed (--today), so a page that says "in 3 days" says it the same
in both runs. A timer set ten seconds or more away never fires: the drawing
is the page as it first stands (LATER_MS). What each page's scripts wrote -- every element's markup and
text, the title, and every error, in the order met -- goes to one file per
page and tab under --out, with manifest.json, the sha256 of each.

--compare names every page and tab whose drawing differs between two such
folders, or that only one has, and exits 1 if there is any.

Asks nobody: it reads --site and tests/dom_stub.js and writes only --out.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

import inline_js as IJ

# The pages that are not a record but draw part of themselves in the browser.
LISTS = ("bills.html", "index.html", "calendar.html", "search.html", "officials.html")

# A timer set this many milliseconds or more away never fires in a drawing (A
# TIMER A WHILE AWAY IS THE PAGE LATER, in the driver): above the timers the
# pages set while they load, which wait six seconds at most, and below
# live.js's every look, at thirty seconds and more (VOTES_FAST_MS, POLL_MS,
# VOTES_SLOW_MS). The pages' two twenty-second timers (find.js's address
# lookup, app.js's follow form) start only when a reader acts, never in a
# drawing.
LATER_MS = 10_000

# How long the pages' scripts may run, in seconds, before a drawing is called
# one that never stops (draw's `timeout`). The fixture's 51 pages and tabs
# draw in about a second; five minutes is room for a slow machine, and a
# script that never stops costs a run five minutes, not half an hour.
DRAW_TIMEOUT = 300

# The node side. One context a page, so nothing one page's scripts declare is
# another's; the stub is loaded into it and then told what the page holds.
DRIVER = IJ.script("drawn_pages")


def tab_slugs(site):
    """{"bill": [...], "legislator": [...], "committee": [...]}: the tab
    addresses the site serves, read from its _redirects."""
    slugs = {"bill": [], "legislator": [], "committee": []}
    red = Path(site) / "_redirects"
    if red.exists():
        for ln in red.read_text(encoding="utf-8").splitlines():
            m = re.match(r"/(bill|legislator|committee)/(?::\w+/)+(\w+) ", ln)
            if m:
                slugs[m.group(1)].append(m.group(2))
    return slugs


def jobs_for(site, today):
    """Every page and tab to draw: (key, page file, address)."""
    site = Path(site)
    slugs = tab_slugs(site)
    out = []
    for kind, pattern in (("bill", "bill/*/*.html"), ("legislator", "legislator/*.html"),
                          ("committee", "committee/*.html")):
        for f in sorted(site.glob(pattern)):
            # A STATUTORY OR STUDY COMMITTEE'S PAGE IS WRITTEN WHOLE (18
            # October 2026, build_study_committees.py): app.js draws no record
            # on it and it has no tabs, as a session day's page has none.
            if kind == "committee" and f.stem.startswith("ss"):
                continue
            page = f.relative_to(site).as_posix()
            own = "/" + page[:-len(".html")]
            out.append({"key": page, "page": page, "path": own})
            out += [{"key": f"{page}#{s}", "page": page, "path": f"{own}/{s}"} for s in slugs[kind]]
    for page in LISTS:
        if (site / page).exists():
            out.append({"key": page, "page": page, "path": "/" + page})
    for j in out:
        j["site"] = str(site.resolve())
        j["today"] = [today.year, today.month, today.day]
        j["later_ms"] = LATER_MS
    return out


def draw(site, out, today, only=None, timeout=DRAW_TIMEOUT):
    """Draw every page and tab of `site` into `out`; returns how many.

    `only`: the page addresses to draw, as prefixes ("committee/"), where not
    every one. `timeout`: the seconds the scripts may run, after which the
    drawing stops and says so rather than waiting on a script that never
    ends."""
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        raise SystemExit("node is not on PATH, and the pages' scripts run in node")
    stub = _paths.ROOT / "tests" / "dom_stub.js"
    jobs = jobs_for(site, today)
    if only:
        only = (only,) if isinstance(only, str) else tuple(only)
        jobs = [j for j in jobs if j["page"].startswith(only)]
        if not jobs:
            raise RuntimeError(f"no page under {site} begins with {', '.join(only)}: nothing "
                               "to draw")
    if not jobs:
        raise SystemExit(f"no record page under {site}: nothing to draw")
    tmp = Path(tempfile.mkdtemp(prefix="gr-drawn-"))
    try:
        (tmp / "drive.js").write_text(DRIVER, encoding="utf-8")
        (tmp / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        try:
            r = subprocess.run([node, str(tmp / "drive.js"), str(stub), str(tmp / "jobs.json"),
                                str(tmp / "out.json")], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            # Said in words: the day drawn on and how many pages, which a
            # weekend-only hang needs. An error, as TimeoutExpired was, so
            # preflight records that check's ERROR and goes on.
            raise RuntimeError(f"the pages' scripts did not finish in {timeout} s, drawn on "
                               f"{today.isoformat()}: a script on one of {len(jobs)} pages "
                               "and tabs never stops") from None
        if r.returncode != 0 or not (tmp / "out.json").exists():
            raise SystemExit("the pages' scripts did not run: " + (r.stderr or r.stdout)[-400:])
        drawn = json.loads((tmp / "out.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    manifest = {}
    for key, d in drawn.items():
        page, _, tab = key.partition("#")
        f = out / page / f"{tab or '_'}.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        text = (f"== title\n{d['title']}\n"
                + "".join(f"== {k}{' (hidden)' if hid else ''}\n{h}\n-- text\n{tx}\n"
                          + (f"-- value\n{v}\n" if v else "")
                          + (f"-- attributes\n{at}\n" if at != "{}" else "")
                          for k, h, tx, hid, v, at in d["elements"])
                + "".join(f"== error\n{e}\n" for e in d["errors"]))
        f.write_text(text, encoding="utf-8", newline="\n")
        manifest[key] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True),
                                       encoding="utf-8", newline="\n")
    empty = [k for k, d in drawn.items() if not d["elements"]]
    errs = sum(1 for d in drawn.values() if d["errors"])
    print(f"drawn: {len(drawn)} pages and tabs of {site} into {out}"
          f" ({errs} with an error the scripts met, {len(empty)} with nothing drawn)")
    return drawn


def compare(a, b):
    """The pages and tabs whose drawing differs between two outputs."""
    ma = json.loads((Path(a) / "manifest.json").read_text(encoding="utf-8"))
    mb = json.loads((Path(b) / "manifest.json").read_text(encoding="utf-8"))
    differ = sorted(k for k in set(ma) & set(mb) if ma[k] != mb[k])
    only_a, only_b = sorted(set(ma) - set(mb)), sorted(set(mb) - set(ma))
    for k in differ:
        print("differs:", k)
    for k in only_a:
        print(f"only in {a}:", k)
    for k in only_b:
        print(f"only in {b}:", k)
    print(f"{len(set(ma) & set(mb)) - len(differ)} of {len(set(ma) | set(mb))} pages and tabs "
          f"drawn the same; {len(differ)} differ; {len(only_a) + len(only_b)} in one only")
    return not (differ or only_a or only_b)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", help="a built site folder")
    ap.add_argument("--out", help="where to write what was drawn")
    ap.add_argument("--today", help="the day the pages are drawn on, YYYY-MM-DD "
                    "(default: GRANITE_BUILD_DATE, else today)")
    ap.add_argument("--compare", nargs=2, metavar="DIR", help="two outputs to compare")
    a = ap.parse_args()
    if a.compare:
        sys.exit(0 if compare(*a.compare) else 1)
    if not (a.site and a.out):
        ap.error("--site and --out, or --compare")
    day = a.today or os.environ.get("GRANITE_BUILD_DATE", "")[:10]
    today = datetime.date.fromisoformat(day) if day else datetime.date.today()
    drawn = draw(a.site, a.out, today)
    # SILENCE IS NOT SUCCESS: a site whose record pages draw nothing at all is
    # a broken driver, not a quiet site.
    if not any(d["elements"] for k, d in drawn.items() if "/" in k):
        sys.exit("no record page drew anything")


if __name__ == "__main__":
    main()
