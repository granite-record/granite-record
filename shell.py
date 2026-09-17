#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.18
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

import datetime
import html
import json
import re
from pathlib import Path

E = html.escape

# app.js and app.css are named plainly in every page, and site/_headers says
# they must be revalidated before reuse -- see THE VERSION QUERY, GONE in
# DESIGN.md. Until 12 September their URL carried a hash of their content
# instead, which worked and cost a gigabyte a publish: the hash is inside the
# HTML, so one changed byte of app.css rewrote all 34,000 record pages.

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
    "seo": '''<meta name="description" content="Search every bill of the New Hampshire General Court by number, subject, sponsor or committee, with its votes, hearings and full history."><link rel="canonical" href="https://graniterecord.org/bills.html"><meta property="og:type" content="website"><meta property="og:title" content="New Hampshire bills | Granite Record"><meta property="og:description" content="Search every bill of the New Hampshire General Court by number, subject, sponsor or committee."><meta property="og:url" content="https://graniterecord.org/bills.html"><meta property="og:site_name" content="Granite Record"><meta name="twitter:card" content="summary_large_image">''',
    # The card a shared link unfurls into. The template names the bills
    # section's card; page() puts each kind of page's own in its place.
    "og_image": '<meta property="og:image" content="https://graniterecord.org/og-bill.png">',
    "og_alt": '<meta property="og:image:alt" content="Granite Record: bills, votes and hearings">',
    "tw_image": '<meta name="twitter:image" content="https://graniterecord.org/og-bill.png">',
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

# The day the site was built, as the fallback date in a citation. A file on
# a CDN cannot know when it is read; app.js puts the reader's own date in
# where it can, and this is what a reader without JavaScript is given.
BUILT = datetime.date.today().strftime("%d %B %Y").lstrip("0")


def cite_block(path, title, base, built=""):
    """How to cite this page, in the four forms a paper or a newsroom asks for.

    HERE, AND NOT IN TEN BUILDERS. Every record page on this site is built
    through page() below -- a bill, a member, a committee, a town, a Learn
    topic -- so one block here reaches all of them and cannot drift between
    them.

    THE NOTE COMES FIRST, AND SAYS THE AWKWARD THING. This site is an index of
    the General Court's record and is not that record. Somebody citing a bill
    in a paper should be citing the General Court, and every page here already
    links to what it was drawn from. A citation tool that quietly encouraged
    the opposite would be a disservice dressed up as a convenience.

    THE DATE IS THE DAY THE PAGE WAS READ, which a file on a CDN cannot know.
    app.js fills every .citeday with the reader's own date; the build date is
    written in as the fallback so a reader without JavaScript gets something
    true about the page rather than "Accessed ." -- and the note says which
    date it is, so neither reader is misled.
    """
    url = f"{base}{canon(path)}"
    # The record's name, without the browser tab's " | Granite Record".
    name = title.split(" | ")[0].strip()
    # MLA, APA and Chicago each close the name with a full stop of their own,
    # and 33,313 of 33,683 bill titles already end in one -- "relative to
    # portable electronics insurance.." . BibTeX adds none, so it keeps the
    # name as written. Only ONE trailing stop is removed: an ellipsis is left
    # alone, because a name that really was shortened should still look it.
    stem = name[:-1].rstrip() if name.endswith(".") and not name.endswith("…") else name
    day = f'<span class="citeday">{E(built)}</span>'
    # A BibTeX key a person can read: the address, minus the punctuation
    # BibTeX treats as syntax.
    key = canon(path).strip("/").replace("/", "-").replace(".", "") or "granite-record"
    forms = [
        ("MLA", f'&ldquo;{E(stem)}.&rdquo; <i>{BRAND}</i>, {E(url)}. '
                f'Accessed {day}.'),
        ("APA", f'{BRAND}. (n.d.). <i>{E(stem)}</i>. Retrieved {day}, '
                f'from {E(url)}'),
        ("Chicago", f'{BRAND}. &ldquo;{E(stem)}.&rdquo; Accessed {day}. '
                    f'{E(url)}.'),
        ("BibTeX", f'<code>@misc{{{E(key)},<br>&nbsp;&nbsp;title = '
                   f'{{{E(name)}}},<br>&nbsp;&nbsp;howpublished = {{{BRAND}}},'
                   f'<br>&nbsp;&nbsp;url = {{{E(url)}}},'
                   f'<br>&nbsp;&nbsp;note = {{Accessed {day}}}<br>}}</code>'),
    ]
    rows = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in forms)
    return ('<section class="citewrap"><details class="cite">'
            '<summary>Cite this page</summary>'
            '<div class="citebody">'
            '<p class="citenote">Granite Record indexes the General '
            'Court&rsquo;s record; it is not that record. Where a citation '
            'allows only one source, cite the General Court &mdash; every page '
            'here links to what it is drawn from. The date below is the day '
            'the page was read.</p>'
            f'<dl class="citeforms">{rows}</dl>'
            '</div></details></section>')


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


def still_moving(row, current_term):
    """Whether a bill can be followed: one of the sitting term, not concluded.

    The person who owns the site, 12 September: "The only bills that need to be
    followable by rss or email are bills that are still moving." A bill signed,
    killed, vetoed and settled, sent to study or died has nothing more to
    report. build_bill_pages advertises a feed and build_feeds writes one on
    this same test, so a page never offers a feed that is not there.

    A bill referred for interim study is still moving, on the person's word of
    13 September: the study committee reports whether it recommends future
    legislation, and that is exactly what somebody following the bill is
    waiting to hear.
    """
    return (row.get("term") or "") == current_term and row.get("kind") in ("active", "study")


def committee_followable(rec):
    """Whether a committee has a feed: one not archived, with a record.

    An archived committee is off the General Court's list and its record has
    ended; it will not sit again, and a feed of it is a file no reader will
    ever see change. One with no sitting day and no bill on record at all --
    the commissions and boards the list names -- has nothing to report either.
    build_feeds writes /feed/committee/<code>.xml on this test, empty or not,
    and build_committees names the feed in the committee's page on the same.
    """
    return not rec.get("archived") and bool(
        rec.get("sessions") or any((rec.get("bills") or {}).values()))


def member_followable(m):
    """Whether a sitting member has a feed: one with a vote or a bill on record.

    build_feeds writes /feed/legislator/<id>.xml on this test and
    build_legislator_pages names it in the member's page on the same one -- the
    member's counterpart of still_moving. The page cannot look for the file
    instead, because the feeds are written after the pages.

    It reads the roster's counts, which build_site_v2 writes in the loop that
    writes the member's own file: n_votes, the length of its vote list, and
    n_sponsored, the bills naming the member a sponsor. On 13 September every
    one of the 406 sitting members had one or both.
    """
    return bool(str(m.get("id") or "")) and bool(m.get("n_votes") or m.get("n_sponsored"))


def ld_script(jsonld):
    """Structured data as a script element, safe inside a page.

    A dict or a list of dicts, wrapped in one schema.org graph. "</" is
    written "<\\/" so a title containing "</script>" cannot end the element --
    the same guard the page's own record gets. Until 13 September this was an
    f-string interpolating a name, NL, that was never defined: no caller had
    passed jsonld, so nothing had raised, and no page had structured data.
    """
    if not jsonld:
        return ""
    graph = jsonld if isinstance(jsonld, list) else [jsonld]
    body = json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, separators=(",", ":"))
    return '\n<script type="application/ld+json">' + body.replace("</", "<\\/") + "</script>"


def page(t, *, path, title, description, base, globals=None, noscript="",
         alternate="", skip_label="Skip to the content", og_title=None,
         sr_title=None, nav_current="", jsonld=None,
         data_json=None, data_url=None, og_type="article", og_image=None,
         og_alt=None, cite=True, cite_title=None):
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
        # "article" for a record's page, "website" for a list of them: the
        # committees index and the directories are not articles.
        + f'\n<meta property="og:type" content="{E(og_type)}">'
        # The card a link unfurls into wants the record's name, not
        # the browser tab's "... | Granite Record".
        + f'\n<meta property="og:title" content="{E(og_title or title)}">'
        + f'\n<meta property="og:description" content="{E(description)}">'
        # og:url and og:site_name: a card unfurled from a shared link had no
        # address of its own and no site to belong to, so it read as a
        # headline from nowhere. Same address as the canonical, deliberately.
        + f'\n<meta property="og:url" content="{base}{canon(path)}">'
        + f'\n<meta property="og:site_name" content="{BRAND}">'
        # The wide card: every page names a 1200x630 image, and "summary" had
        # X draw a thumbnail of the square icon beside the words instead.
        + '\n<meta name="twitter:card" content="summary_large_image">'
        # Structured data, where the page has something a search engine has a
        # vocabulary for. It is passed in rather than guessed at here, because
        # only the builder knows whether this is a bill, a person or a body.
        + ld_script(jsonld))

    out = t.replace(NEEDS["viewport"], head, 1)
    # EACH KIND OF PAGE ITS OWN CARD (build_brand.py draws them): a shared bill
    # and a shared legislator unfurled identically. A page that names none gets
    # the plain logo card.
    img = f"{base}/{og_image or 'og.png'}"
    out = out.replace(NEEDS["og_image"], f'<meta property="og:image" content="{img}">', 1)
    out = out.replace(NEEDS["tw_image"], f'<meta name="twitter:image" content="{img}">', 1)
    out = out.replace(NEEDS["og_alt"], f'<meta property="og:image:alt" content="'
                      f'{E(og_alt or BRAND)}">', 1)
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

    # THE RECORD ITSELF, OR ITS ADDRESS. A bill's page was a 4.3 KB shell that
    # loaded app.js, which then fetched the record as a SECOND round trip --
    # and for half the bills on this site that record is 1.3 KB, so the
    # envelope cost more than the letter and took an extra journey to deliver
    # it.
    #
    # Small enough, and it travels inside the page. Too big, and the page says
    # where it is instead: 98 of 33,683 bills carry more than 100 KB, almost
    # all of it individual roll call ballots, and HB2 alone is 2 MB. Inlining
    # those would make a page nobody should be asked to download.
    #
    # <script type="application/json"> and not window.X = {...}: the search
    # page fetches this page to expand a card, and a script tag with an id is
    # read with one DOMParser call, where a JavaScript assignment would have
    # to be pulled out of the text by hand.
    block = ""
    if data_json:
        block = ('<script type="application/json" id="gr-data">'
                 + data_json.replace("</", "<\\/") + "</script>\n")
    elif data_url:
        block = f'<meta name="gr-data" content="{E(data_url)}">\n'

    # Below the record and above the footer, outside #results so app.js
    # rewriting the page cannot take it away.
    if cite:
        # NOT `title`, which is the browser tab's version and has already been
        # elided to fit: "prohibiting the use of state funds for new…". Every
        # citation built from it quoted a name the bill does not have, on
        # 25,596 of 33,683 bill pages.
        #
        # And not og_title either, on its own. That one is clipped to 110
        # characters, which still truncates 11,558 bill titles -- better, but
        # a citation that is right two times in three is not right. So a
        # caller with the untruncated name passes cite_title and nothing
        # shortens it; the others fall back through og_title to title, which
        # is correct for pages whose names are short anyway.
        #
        # A citation is a claim about what a document is CALLED, and unlike
        # everything else on the page it gets pasted into someone else's work
        # and outlives the visit. It is the one string here worth carrying
        # separately.
        out = out.replace('<footer><div class="in">',
                          cite_block(path, cite_title or og_title or title,
                                     base, BUILT)
                          + '<footer><div class="in">', 1)

    out = out.replace(
        NEEDS["script"],
        (noscript + "\n" if noscript else "")
        + block
        + f"<script>{decl}</script>\n{NEEDS['script']}", 1)
    return out
