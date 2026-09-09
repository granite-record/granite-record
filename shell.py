#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.10
"""
The page every record's own address is: bills.html, with one record open.

    import shell
    t = shell.template(Path("site"))
    html = shell.page(t, path="/bill/2026/hb1094.html", title="HB 1094 — ...",
                      description="...", base="https://graniterecord.org",
                      globals={"GR_BILL": "2026/HB1094"}, noscript="<p>...</p>")

WHY ONE MODULE

Three things now have a page of their own -- a bill, a legislator, a committee
-- and all three are the same app with one record open. app.js binds to #q,
#qgo, #year, #sort, #facets, #results and #count as it loads, and a page
missing any of them is a blank screen that reports nothing. Three generators
each with their own copy of that markup is three chances for one of them to
drift, silently, across thousands of files.

So the template IS bills.html, read at build time, and the substitutions assert
that what they are replacing was actually there.
"""

import hashlib
import html
import json
import re
from pathlib import Path

E = html.escape

# The two files every page loads. Their URL carries a hash of their content.
ASSETS = ("app.js", "app.css")


def asset_query(site=Path("site")):
    """"?v=1a2b3c4d", from the bytes of app.js and app.css together.

    A hash rather than the GRANITE_VERSION stamp, because the stamp is bumped
    by hand and the one time somebody forgets is the release that breaks --
    silently, for four hours, for everyone who visited that morning.
    """
    h = hashlib.md5()
    found = False
    for name in ASSETS:
        for base in (Path("."), Path(site)):
            f = base / name
            if f.exists():
                h.update(f.read_bytes())
                found = True
                break
    return f"?v={h.hexdigest()[:8]}" if found else ""


def bust(text, q):
    """Point every asset reference in a page at the versioned URL."""
    if not q:
        return text
    for name in ASSETS:
        text = text.replace(f'src="{name}"', f'src="{name}{q}"')
        text = text.replace(f'href="{name}"', f'href="{name}{q}"')
    return text

# The pieces of bills.html that get substituted. If one stops being there,
# every page is quietly wrong, so each is asserted rather than left to
# str.replace's silent no-op.
NEEDS = {
    "title": "<title>Granite Record — New Hampshire legislative history</title>",
    # Absolute, because bills.html now carries <base href="/"> too -- opening
    # a bill pushes /bill/2026/hb1123 and a bare "#results" would resolve
    # against the site root rather than down the page.
    "skip": '<a class="skip" href="/bills.html#results">Skip to the bills</a>',
    "script": '<script src="app.js"></script>',
    "viewport": '<meta name="viewport" content="width=device-width, initial-scale=1">',
    # bills.html is a page in its own right and carries its own description,
    # canonical and unfurl card. Every record page built from it writes its
    # own, so this block is removed rather than inherited -- otherwise 34,000
    # pages would all claim to be the bill search page.
    "seo": '''<meta name="description" content="Search every bill of the New Hampshire General Court by number, subject, sponsor or committee, with its votes, hearings and full history."><link rel="canonical" href="https://graniterecord.org/bills.html"><meta property="og:type" content="website"><meta property="og:title" content="New Hampshire bills | Granite Record"><meta property="og:description" content="Search every bill of the New Hampshire General Court by number, subject, sponsor or committee."><meta property="og:url" content="https://graniterecord.org/bills.html"><meta property="og:site_name" content="Granite Record"><meta name="twitter:card" content="summary">''',
}

# Every element app.js binds to on load.
BINDS = ('id="q"', 'id="qgo"', 'id="year"', 'id="sort"',
         'id="facets"', 'id="results"', 'id="count"')


def template(site=Path("site")):
    """bills.html, checked for everything the substitutions rely on."""
    for p in (Path("bills.html"), Path(site) / "bills.html"):
        if p.exists():
            t = p.read_text(encoding="utf-8")
            break
    else:
        raise SystemExit(
            "bills.html is not in the project root or in the site folder, and "
            "it is the template every record's page is made from.")
    absent = [k for k, v in NEEDS.items() if v not in t]
    assert not absent, (
        f"bills.html no longer contains: {', '.join(absent)}. Every page is "
        "built by substituting into those, so they cannot be edited there "
        "without editing shell.py too.\nExpected literally:\n  "
        + "\n  ".join(NEEDS[k] for k in absent))
    missing = [b for b in BINDS if b not in t]
    assert not missing, (
        f"bills.html is missing {', '.join(missing)}, which app.js binds to "
        "when it loads. Every page would draw a blank screen and say nothing "
        "about why.")
    return t


BRAND = "Granite Record"


def canon(path):
    """The address the host actually serves, for a page written as .html.

    MEASURED, not assumed, against the live site on 9 September:

        /bill/2026/hb1442        200, and the address bar keeps it
        /bill/2026/hb1442.html   308 to /bill/2026/hb1442

    Cloudflare Pages strips the extension. So every canonical link and all
    34,158 entries in the sitemap named an address that redirects -- telling a
    crawler the real address of this page is one that immediately sends it
    somewhere else. Google follows it and indexes the destination, so nothing
    was broken; it was 34,158 wasted round trips and a canonical that
    contradicted itself.

    index.html is the directory, not a page called index.
    """
    if not path:
        return "/"
    if path.endswith("/index.html"):
        return path[: -len("index.html")]
    if path == "index.html":
        return "/"
    return path[:-5] if path.endswith(".html") else path

# A search result shows roughly the first sixty characters of a title and a
# hundred and sixty of a description. Longer is not penalised -- it is simply
# not shown -- but a cut that lands mid-word is, because the fragment that
# survives reads as broken.
# Sixty is what is SHOWN; the rest still counts for relevance and costs
# nothing, so the room here is for the lead and the subject together and the
# brand is added after it. Sixty flat left "making appropriations for
# capital..." -- a cut that loses the word the reader needed.
TITLE_ROOM = 70
DESC_ROOM = 155


def clip(s, room):
    """Trim to about `room` characters, at a word boundary, never mid-word."""
    s = re.sub(r"\s+", " ", (s or "")).strip()
    if len(s) <= room:
        return s
    cut = s[:room]
    sp = cut.rfind(" ")
    if sp > room * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,;:-\u2013\u2014.") + "\u2026"


def title_of(lead, detail="", brand=True):
    """A page title: what this page IS, then what it is about, then the site.

    The lead is never trimmed -- it is the thing a person searched for, and
    "HB 25 (2015)" is the whole reason this page is not the other thirteen
    pages with the same subject. The detail takes whatever room is left.
    """
    lead = re.sub(r"\s+", " ", (lead or "")).strip()
    tail = f" | {BRAND}" if brand else ""
    room = TITLE_ROOM - len(lead) - 3
    detail = clip(detail, room) if (detail and room > 12) else ""
    return (f"{lead} \u2014 {detail}" if detail else lead) + tail


def page(t, *, path, title, description, base, globals=None, noscript="",
         alternate="", skip_label="Skip to the content", og_title=None,
         sr_title=None, nav_current="", jsonld=None):
    """One record's page: the template, told which record it is.

    sr_title replaces the template's own visually-hidden <h1>. bills.html
    carries "New Hampshire bills" because that is what bills.html is, and
    every page built from it inherits the same line -- so a screen reader
    opening the committees index, a member's page or a civics page is told
    "New Hampshire bills" before it is told anything true. It is invisible,
    which is why it has gone unnoticed, and it is the first thing announced,
    which is why it matters."""
    if nav_current:
        # The template is bills.html, so its nav marks Bills as the current
        # page and every page built from it inherits that -- the committees
        # index, a member's page and these all tell a reader they are on
        # Bills. aria-current is what a screen reader uses to say "you are
        # here", so this is not only decoration.
        t = t.replace(' aria-current="page"', "", 1)
        t = t.replace(f'<a href="{nav_current}"',
                      f'<a href="{nav_current}" aria-current="page"', 1)
    if sr_title is not None:
        # An empty string REMOVES it, which is what a page with its own
        # visible <h1> wants: keeping both makes a screen reader announce the
        # same heading twice, which is worse than the wrong one it replaced.
        repl = f'<h1 class="sr">{E(sr_title)}</h1>' if sr_title else ""
        t = t.replace('<h1 class="sr">New Hampshire bills</h1>', repl, 1)
    head = (
        NEEDS["viewport"]
        # <base href="/"> is in bills.html itself now -- opening a bill on the
        # search page pushes /bill/2026/hb1123, which re-bases every relative
        # link there too -- and bills.html IS this template, so adding one here
        # put two on every record page.
        + f"\n<title>{E(title)}</title>"
        + f'\n<meta name="description" content="{E(description)}">'
        + f'\n<link rel="canonical" href="{base}{canon(path)}">'
        + (f"\n{alternate}" if alternate else "")
        + '\n<meta property="og:type" content="article">'
        # The card a link unfurls into wants the record's name, not
        # the browser tab's "... | Granite Record".
        + f'\n<meta property="og:title" content="{E(og_title or title)}">'
        + f'\n<meta property="og:description" content="{E(description)}">'
        # og:url and og:site_name: a card unfurled from a shared link had no
        # address of its own and no site to belong to, so it read as a
        # headline from nowhere. Same address as the canonical, deliberately.
        + f'\n<meta property="og:url" content="{base}{canon(path)}">'
        + f'\n<meta property="og:site_name" content="{BRAND}">'
        + '\n<meta name="twitter:card" content="summary">'
        # Structured data, where the page has something a search engine has a
        # vocabulary for. It is passed in rather than guessed at here, because
        # only the builder knows whether this is a bill, a person or a body.
        + (f'{NL}<script type="application/ld+json">{jsonld}</script>'
           if jsonld else ""))

    out = t.replace(NEEDS["viewport"], head, 1)
    # ONE TITLE PER PAGE. head starts with the viewport meta and adds a
    # <title> after it, so the template's own title survived the substitution
    # and every one of the 34,152 generated pages carried two of them -- the
    # record's, and then "Granite Record — New Hampshire legislative history".
    # A browser shows the first and a crawler is entitled to either.
    out = out.replace(NEEDS["title"], "", 1)
    out = out.replace(NEEDS["seo"], "", 1)
    # <base> would send the skip link to the site root instead of down the
    # page, which is the one thing a skip link must not do.
    out = out.replace(
        NEEDS["skip"],
        f'<a class="skip" href="{canon(path)}#results">{E(skip_label)}</a>',
        1)
    decl = "".join(f"window.{k}={json.dumps(v)};"
                   for k, v in (globals or {}).items())
    out = out.replace(
        NEEDS["script"],
        (noscript + "\n" if noscript else "")
        + f"<script>{decl}</script>\n{NEEDS['script']}", 1)
    return bust(out, asset_query())
