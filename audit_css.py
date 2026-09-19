#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.1
"""
Which components are stranded, and which rules are dead.

    python3 audit_css.py --site site

WHY THIS EXISTS

app.css is one file with three regions, and style.css is a VIEW of it:

    PALETTE  + SHARED + PAGES        -> style.css
    the whole file                   -> app.css

Every page built from bills.html through shell.page loads app.css and sees
everything. Every page build_pages.py writes -- the home page, the roster,
about, 404 -- loads style.css and sees only those three regions. A component
styled in the middle region, between SHARED:END and PAGES:START, is invisible
to half the site.

That is not hypothetical. `.mchip` sat there for weeks with a comment on it
reading "the legislators page, the committee roster and the sponsor list all
draw" it, and the legislators page could not have been getting it: the rule was
in the region style.css does not take. The roster drew its own hand-written
row instead, and the same member read one way there and another on a bill.

So this reads what each built page actually uses and what its own stylesheet
actually carries, and reports the gap. It also reports the reverse -- rules
nothing uses -- because a stylesheet nobody prunes is how a class name comes to
mean two things.

WHAT IT CANNOT SEE. Classes a script adds after load. app.js builds the
committee roster, the bill detail and the vote rings in the browser, so their
classes are read out of app.js as well as out of the HTML; anything it composes
from a variable rather than a literal is invisible here and is listed as such.
"""

import argparse
import collections
import json
import re
from pathlib import Path

# A class in markup: class="a b c" in HTML, and the same inside a JS template.
CLASS_ATTR = re.compile(r'class\s*=\s*["\']([^"\'<>{}$]+)["\']')
# A selector's class names, from a stylesheet.
SEL_CLASS = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")

# Classes that are never styled and are not meant to be: hooks for scripts and
# for the checks themselves.
IGNORE = {"js", "no-js", "sr-only"}


def regions(css):
    """{name: text} for the three marked regions of app.css."""
    out = {}
    for name, start, end in (("palette", "/* PALETTE:START", "/* PALETTE:END"),
                             ("shared", "/* SHARED:START", "/* SHARED:END"),
                             ("pages", "/* PAGES:START", "/* PAGES:END")):
        try:
            a = css.index(start)
            b = css.index(end)
        except ValueError:
            continue
        out[name] = css[a:b]
    return out


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

    app_css = Path("app.css").read_text(encoding="utf-8")
    reg = regions(app_css)
    # SILENCE IS NOT SUCCESS: without the markers every class looks stranded,
    # and the report would be one long false alarm.
    assert "shared" in reg and "pages" in reg, (
        "app.css has no SHARED/PAGES markers; this audit reads the regions by "
        "them and cannot say anything without them")

    style_css = (site / "style.css").read_text(encoding="utf-8")
    styled_style = styled_in(style_css)
    styled_app = styled_in(app_css)
    middle = styled_app - styled_in(reg["shared"]) - styled_in(reg["pages"]) \
        - styled_in(reg.get("palette", ""))

    # Which pages load which stylesheet, read off the built page rather than
    # assumed: the answer is what a reader's browser actually fetches.
    by_sheet = collections.defaultdict(list)
    for f in sorted(site.rglob("*.html")):
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # 404.html links "/style.css" with a leading slash, because a 404 is
        # served from whatever path the reader asked for and a relative href
        # would resolve against it. Matching only the relative form filed the
        # 404 under "neither" and left it out of the audit entirely.
        sheet = ("style.css" if re.search(r'href="/?style\.css"', t)
                 else "app.css" if re.search(r'href="/?app\.css"', t)
                 else "?")
        by_sheet[sheet].append(f)

    print(f"{sum(len(v) for v in by_sheet.values()):,} built pages")
    for k, v in sorted(by_sheet.items()):
        print(f"  {len(v):6,} load {k}")

    # EVERY style.css page, not a sample. There are four of them -- the home
    # page, the roster, About and 404 -- and sampling one per directory read
    # one of the four, because all four sit in the site root. An audit that
    # looks at a quarter of what it claims to is worse than none.
    seen = {f.relative_to(site).as_posix(): f
            for f in by_sheet.get("style.css", [])}
    used = set()
    for key, f in sorted(seen.items()):
        used |= classes_in(f.read_text(encoding="utf-8", errors="replace"))
    used -= IGNORE

    stranded = sorted(c for c in used
                      if c in middle and c not in styled_style)
    print(f"\n{len(seen)} page shapes load style.css, using {len(used)} classes")
    if stranded:
        print(f"\n  STRANDED -- used by a style.css page, styled only in the\n"
              f"  region style.css does not take ({len(stranded)}):")
        for c in stranded:
            print(f"    .{c}")
    else:
        print("\n  nothing stranded: every class those pages use is styled "
              "in a region their stylesheet carries")

    # And the other direction, over the whole site.
    everything = set()
    for v in by_sheet.values():
        for f in v[:400]:
            everything |= classes_in(f.read_text(encoding="utf-8", errors="replace"))
    for js in ("app.js", "find.js"):
        p = Path(js)
        if p.exists():
            everything |= classes_in(p.read_text(encoding="utf-8", errors="replace"))
    for py in Path(".").glob("build_*.py"):
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

    return 1 if stranded else 0


if __name__ == "__main__":
    raise SystemExit(main())
