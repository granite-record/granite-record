#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.7
"""
Which pages load which stylesheet, and which rules are dead.

    python3 src/checks/audit_css.py --site site

WHY THIS EXISTS

It was written to find STRANDED components. Until 23 October 2026 app.css
had three marked regions and the five pages build_pages.py writes loaded
style.css, a view of two of them, so a component styled outside those
regions was invisible to those pages -- `.mchip` sat there for weeks with a
comment saying the roster drew it, and the whole footer was there too. Since
that day every page loads app.css whole (app.css, ONE STYLESHEET FOR EVERY
PAGE), and nothing can be stranded by where it sits in the file.

What is left to report: that every built page does load app.css, which is
the one way a component could be stranded again -- a page that links some
other stylesheet -- and the reverse, rules nothing uses, because a stylesheet
nobody prunes is how a class name comes to mean two things.

WHAT IT CANNOT SEE. Classes a script adds after load. app.js builds the
committee roster, the bill detail and the vote rings in the browser, so their
classes are read out of app.js, and components.js which it draws with, as well
as out of the HTML; anything it composes from a variable rather than a literal
is invisible here and is listed as such.

It reads app.css, components.js, app.js and find.js from src/pages/, where they
sit, and the built pages from --site.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import json
import re

# A class in markup: class="a b c" in HTML, and the same inside a JS template.
CLASS_ATTR = re.compile(r'class\s*=\s*["\']([^"\'<>{}$]+)["\']')
# A selector's class names, from a stylesheet.
SEL_CLASS = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")

# Classes that are never styled and are not meant to be: hooks for scripts and
# for the checks themselves.
IGNORE = {"js", "no-js", "sr-only"}


def classes_in(text):
    out = set()
    for m in CLASS_ATTR.finditer(text):
        for c in m.group(1).split():
            c = c.strip()
            if c and not c.startswith(("{", "$")):
                out.add(c)
    return out


def styled_in(css):
    return {m.group(1) for m in SEL_CLASS.finditer(css)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    site = Path(a.site)

    app_css = Path("src/pages/app.css").read_text(encoding="utf-8")
    styled_app = styled_in(app_css)

    # Which pages load which stylesheet, read off the built page rather than
    # assumed: the answer is what a reader's browser actually fetches. map.css
    # and print.css are additions a page takes beside app.css, not instead.
    by_sheet = collections.defaultdict(list)
    for f in sorted(site.rglob("*.html")):
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        sheets = [h.lstrip("/") for h in re.findall(
            r'<link rel="stylesheet" href="([^"]+)"', t)
            if not h.startswith(("http:", "https:"))]
        mine = [h for h in sheets if h not in ("map.css", "print.css")]
        by_sheet[" + ".join(mine) if mine else "no stylesheet"].append(f)

    print(f"{sum(len(v) for v in by_sheet.values()):,} built pages")
    for k, v in sorted(by_sheet.items()):
        print(f"  {len(v):6,} load {k}")
    astray = sorted(f.relative_to(site).as_posix()
                    for k, v in by_sheet.items() if k != "app.css" for f in v)
    if astray:
        print(f"\n  ASTRAY -- {len(astray)} pages do not load app.css alone, so a "
              f"component\n  styled there may not reach them:")
        for x in astray[:20]:
            print(f"    {x}")
    else:
        print("\n  every page loads app.css, the one stylesheet: no component "
              "can be stranded")

    # And the other direction, over the whole site.
    everything = set()
    for v in by_sheet.values():
        for f in v[:400]:
            everything |= classes_in(f.read_text(encoding="utf-8", errors="replace"))
    for js in ("components.js", "app.js", "find.js"):
        p = Path("src/pages") / js
        if p.exists():
            everything |= classes_in(p.read_text(encoding="utf-8", errors="replace"))
    for py in _paths.code_files("build_*.py"):
        everything |= classes_in(py.read_text(encoding="utf-8", errors="replace"))

    dead = sorted(c for c in styled_app
                  if c not in everything and c not in IGNORE)
    print(f"\n  {len(dead)} class selectors in app.css that nothing found here "
          "uses.")
    if a.verbose and dead:
        for c in dead:
            print(f"    .{c}")
    else:
        print("    (--verbose to list them; a class built from a variable in "
              "a script will show up here and is not necessarily dead)")

    return 1 if astray else 0


if __name__ == "__main__":
    raise SystemExit(main())
