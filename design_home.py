#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.1
"""
Three arrangements of the home page, built from the real one.

    python3 design_home.py --site site
    -> site/design/home-a.html, home-b.html, home-c.html

NOT A SECOND HOME PAGE. This takes site/index.html as it was built, finds its
blocks, and puts them in a different order with a little extra CSS. The
content, the scripts, the head and every component are the page's own, so what
a reader sees in a variant is what they would see if the arrangement shipped --
and when the real page changes, so does every variant, because there is no copy
of anything here.

WHAT THE VARIANTS ARE ANSWERING

Today the page is three columns above 1180px: a 300px rail, the middle, a 290px
rail. The masthead lockup, the slogan and the search box live in the MIDDLE
one, which is about 482px on a 1440px screen -- so the site's name and its
primary action are the narrowest full-height thing on the page, with secondary
rails either side. Every arrangement below starts by giving the hero the width
of the page and deciding what goes under it.

The lockup and the slogan stay in all three. They are not up for redesign.
"""

import argparse
import re
from pathlib import Path

BLOCKS = {
    # name: (start marker, end marker) -- end is matched by balancing <div>s
    "hero": ('<h1 class="lockup">', '<div class="entry">'),
    "entry": ('<div class="entry">', '<div id="fresh"'),
    "fresh": ('<div id="fresh"', "</div>\n<section"),
    "left": ('<section class="hside hleft"', "</section>"),
    "right": ('<section class="hside hright"', "</section>"),
    "recent": ('<div id="recent">', None),
}


def cut(html, start, end):
    i = html.find(start)
    if i < 0:
        return "", html
    if end is None:
        j = len(html)
    else:
        j = html.find(end, i + len(start))
        if j < 0:
            j = len(html)
    return html[i:j], html[:i] + html[j:]


VARIANT_CSS = """
<style>
/* A VARIANT'S OWN LAYOUT, and nothing else. Everything visual comes from
   style.css; these rules only say where the page's existing blocks go. */
body.pg .hcols{display:block}
.vhero{max-width:1180px;margin:0 auto;padding:0 var(--sp-8)}
.vhero .lockup,.vhero .slogan{text-align:center}
.vhero .lead{max-width:62ch;margin-left:auto;margin-right:auto;text-align:center}
.vband{max-width:1180px;margin:0 auto var(--sp-9);padding:0 var(--sp-8)}
.vrow{display:grid;gap:var(--sp-9);align-items:start}
.vnote{max-width:1180px;margin:0 auto var(--sp-6);padding:var(--sp-4) var(--sp-8);
border-left:3px solid var(--pine);background:var(--surface);font-size:var(--t-ui)}
.vnote b{color:var(--pine)}
.vhero .entry{margin-top:var(--sp-7)}
%s
@media (max-width:900px){.vrow{grid-template-columns:1fr!important}}
</style>
"""

LAYOUTS = {
    "a": (
        "Hero across the top, then the week beside what just happened",
        """The masthead, the slogan and the search take the full width. Under
        them the two things that change -- the week's sittings and the latest
        activity -- sit side by side, the calendar wider because a week of
        committee cards needs the room. The three entry cards run as a band
        under the hero, and the legislator finder closes the page.""",
        ".vrow-main{grid-template-columns:minmax(0,1.6fr) minmax(0,1fr)}",
        ["hero+entry", "row:left|recent", "band:right"],
    ),
    "b": (
        "Hero across the top, then three equal panels",
        """Closest to what is there now, with one change: the hero is no longer
        boxed into the middle column. The three panels keep their present
        contents and become equal thirds beneath it, so the calendar, the
        finder and the latest activity read as three peers rather than as a
        centre with two rails.""",
        ".vrow-main{grid-template-columns:repeat(3,minmax(0,1fr))}",
        ["hero+entry", "row:left|right|recent"],
    ),
    "c": (
        "One column, each thing at full width",
        """No rails at all. The hero, then the week, then the latest activity,
        then the finder, each taking the whole measure of the page in turn.
        The most direct answer to a narrow thing in a wide box, and the one
        that reads the same on a phone as on a desk.""",
        ".vband .cal,.vband .hfind{max-width:none}",
        ["hero+entry", "band:left", "band:recent", "band:right"],
    ),
}


def build(html, order, extra_css, title, blurb, name):
    parts, rest = {}, html
    for key, (a, b) in BLOCKS.items():
        parts[key], rest = cut(rest, a, b)

    body = [f'<p class="vnote"><b>Arrangement {name.upper()}</b> &mdash; '
            f'{title}. {re.sub(r"\\s+", " ", blurb).strip()}</p>']
    for step in order:
        if step.startswith("row:"):
            cols = step[4:].split("|")
            body.append('<div class="vband vrow vrow-main">'
                        + "".join(parts.get(c, "") for c in cols) + "</div>")
        elif step.startswith("band:"):
            body.append('<div class="vband">' + parts.get(step[5:], "")
                        + "</div>")
        elif step == "hero+entry":
            body.append('<div class="vhero">' + parts.get("hero", "")
                        + parts.get("entry", "") + parts.get("fresh", "")
                        + "</div>")
    # Put the rearranged blocks back where .hcols was.
    i = rest.find('<div class="hcols">')
    j = rest.find("</div>", i) if i >= 0 else -1
    out = (rest[:i] + "".join(body) + rest[j + 6:]) if i >= 0 else rest + "".join(body)
    # A BASE, BECAUSE THE VARIANTS LIVE A DIRECTORY DOWN. index.html has no
    # base tag and asks for "style.css", "app.js" and every link relatively,
    # which is correct for a page served from the root and resolves to
    # /design/style.css from here -- so the first build of these rendered as
    # unstyled markup. The variants are the same page one directory down, so
    # they carry the base the original does not need.
    # THE BASE GOES FIRST IN THE HEAD, not last. A browser resolves relative
    # URLs in document order, so a <base> after the stylesheet link does
    # nothing for it -- which is what the first attempt did, and the variants
    # rendered as bare markup with a base tag sitting uselessly below the
    # link it was meant to fix.
    i = out.lower().find("<head")
    j = out.find(">", i) + 1 if i >= 0 else -1
    assert j > 0, "the page has no <head> to put a base in"
    out = out[:j] + '<base href="/">' + out[j:]
    return out.replace("</head>", (VARIANT_CSS % extra_css) + "</head>", 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    a = ap.parse_args()
    site = Path(a.site)
    src = site / "index.html"
    assert src.exists(), f"{src} is not built; run build_pages.py first"
    html = src.read_text(encoding="utf-8")
    # SILENCE IS NOT SUCCESS: without the grid the extractor finds nothing and
    # writes three copies of the page it was given.
    assert '<div class="hcols">' in html, (
        "index.html has no .hcols block, so this cannot find the pieces to "
        "rearrange; the home page's markup has changed")

    out = site / "design"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for name, (title, blurb, css, order) in sorted(LAYOUTS.items()):
        page = build(html, order, css, title, blurb, name)
        assert "lockup" in page, f"{name}: the masthead did not survive"
        p = out / f"home-{name}.html"
        p.write_text(page, encoding="utf-8")
        made.append((p, title))
    for p, title in made:
        print(f"  {p}  {title}")
    print(f"\n{len(made)} arrangements. They are built from index.html as it "
          "stands, so\nnothing here is a second copy of the home page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
