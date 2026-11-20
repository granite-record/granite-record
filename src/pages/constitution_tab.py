#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-17.5
"""
The state Constitution as a tab on the Laws page, and the links to its articles
from the rest of the site.

    import constitution_tab as CT
    CT.tabbed(statutes_html, statutes_lead, con)   # the strip, both panels and the script
    CT.link_citations(html, con)                  # "Part Second, Article 44" -> its article

Asks nobody and reads nothing: build_rsa.py hands it collected/constitution.json
(parse_constitution.load()), and build_civics.py its Learn pages' HTML.

THE PERSON'S ASK, 17 October 2026: "Can you fetch the constitution at least so
we can present that on the laws page, possibly on its own tab?" So the Laws
page has two tabs, Statutes (RSA) first, as the page was, and Constitution.

THE TAB IS A CHAPTER PAGE. The Constitution is laid out with the statute
pages' own parts (build_rsa.chapter_page): its articles in a sidebar, sticky
beside the text on a wide screen and a bar over it on a phone, each article a
section with its own anchor and a link to itself, Part Second's divisions as
the chapter's inner headings, and a repealed article marked as a repealed
section is. CHAPTER_JS, which marks the article being read, runs on it
unchanged.

EVERY ARTICLE HAS AN ADDRESS: /laws#part1-art2-a, /laws#part2-art78, and
/laws#part1 and /laws#part2 for a whole part. An address naming an article
opens the Constitution tab and lands on it, which the town pages' tab script
did not do (it knew only a panel's own id), so the Laws page carries its own.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import html
import re

import components as C
import constitution_history as CH
import inline_js as IJ
import parse_constitution as PC

E = html.escape
PATH = "/laws"
ROMAN = {1: "I", 2: "II"}
TABS = (("statutes", "Statutes (RSA)"), ("constitution", "Constitution"))


def _toc(con):
    """The sidebar's list: each part and division a line of its own, then its
    articles. The part rides inside each article's number, hidden, so the bar
    on a phone names "Pt. II, Art. 78" and not an "Art. 78" of either part."""
    items = []
    for part in con["parts"]:
        p = part["part"]
        items.append(f'<li class="cn-tg">{E(part["name"])}: {E(part["title"])}</li>')
        for d in part["divisions"]:
            if len(part["divisions"]) > 1:
                items.append(f'<li class="cn-td">{E(d["name"])}</li>')
            for a in d["articles"]:
                num = (f'<b><span class="sr">Pt. {ROMAN[p]}, </span>Art. {E(a["key"])}</b>')
                link = f'{PATH}#{a["anchor"]}'
                if a["repealed"]:
                    items.append(f'<li class="rs-off"><a href="{E(link)}">{num}</a> <span>Repealed</span></li>')
                else:
                    items.append(f'<li><a href="{E(link)}">{num} {E(a["title"])}</a></li>')
    n = sum(len(d["articles"]) for part in con["parts"] for d in part["divisions"])
    return (f'<nav class="rs-side" aria-label="Articles of the Constitution"><details class="rs-sidebox" open>'
            f'<summary><span class="rs-sumw">The Constitution: {n} articles</span>'
            f'<span class="rs-now" aria-hidden="true"></span></summary>'
            f'<ol>{"".join(items)}</ol></details></nav>')


def _article(p, a, level, hist=None):
    """One article as a statute section is drawn: its number linking to itself,
    its title, its words, and nh.gov's notes on when it was adopted and
    amended, as printed."""
    link = f'{PATH}#{a["anchor"]}'
    badge = ' <span class="rs-rbadge">Repealed</span>' if a["repealed"] else ""
    text = "" if a["repealed"] else (
        '<div class="rs-text" translate="no">' + "".join(f"<p>{E(t)}</p>" for t in a["text"]) + "</div>")
    notes = ""
    if a["notes"]:
        notes = ('<ul class="cn-notes" aria-label="Adopted and amended">'
                 + "".join(f"<li>{E(n)}</li>" for n in a["notes"]) + "</ul>")
    return (f'<section class="rs-sec cn-art" id="{E(a["anchor"])}"><h{level} class="rs-h">'
            f'<a href="{E(link)}">Article {E(a["key"])}</a> {E(a["title"])}{badge}</h{level}>'
            f'{text}{notes}{CH.fold(p, a["key"], *hist) if hist else ""}</section>')


def lead(con):
    """What the Constitution is, in two sentences, and where its text here comes from."""
    read = (con.get("_source", {}).get("read") or [""])[0]
    when = C.date_words(read, "full") if read else ""
    # THE ANSWER FIRST, AT THE LEAD'S SIZE, AND THE PARTICULARS SMALL UNDER
    # IT (the phone check of 17 October 2026: the whole of it at the lead's
    # size filled a 375-pixel screen before the first article).
    return (
        "<p class=\"l-lead cn-lead\">New Hampshire's Constitution is the state's highest law. "
        f'<a href="{PATH}#part1">Part First</a>, the Bill of Rights, states the people\'s rights and '
        f'what the state may not do; <a href="{PATH}#part2">Part Second</a>, the Form of Government, '
        "sets up the House, the Senate, the Governor, the Council and the courts.</p>"
        '<p class="cn-src">It took effect on June 2, 1784, and an amendment becomes part of it only '
        "when two thirds of those voting on it approve "
        f'(<a href="{PATH}#part2-art100">Part Second, Article 100</a>; how that works is on '
        '<a href="learn/the-constitution.html">The Constitution</a>). The text is as the State of '
        "New Hampshire publishes it on NH.gov" + (f", read on {E(when)}" if when else "")
        + ", with the state's notes under each article on when it was adopted and amended. "
        '<a href="https://www.nh.gov/glance/state-constitution" rel="noopener">The Constitution on '
        "NH.gov</a>.</p>")


def panel(con, hist=None):
    """The Constitution tab's content: the lead, then the sidebar and the
    articles, Part First's under its heading and Part Second's under each of
    its divisions."""
    body = []
    for part in con["parts"]:
        p = part["part"]
        body.append(f'<h3 class="cn-part" id="part{p}">{E(part["name"])}: {E(part["title"])}</h3>')
        many = len(part["divisions"]) > 1
        for d in part["divisions"]:
            if many:
                body.append(f'<h4 class="rs-sub" id="{E(d["slug"])}">{E(d["name"])}</h4>')
            for a in d["articles"]:
                body.append(_article(p, a, 5 if many else 4, hist))
    return (lead(con) + f'<div class="rs-chap cn-chap">{_toc(con)}'
            f'<div class="rs-art">{"".join(body)}</div></div>')


def tabbed(statutes, statutes_lead, con, hist=None):
    """The strip and the two panels, Statutes (RSA) first, as the page was.

    THE TOWN PAGES' TABS (build_town_pages.tabbed): a role=tablist written
    hidden and shown by the script, buttons with a roving tabindex, panels
    labelled by their tab, and without JavaScript both panels in order, each
    under its own heading."""
    panes = {"statutes": f'<p class="l-lead">{statutes_lead}</p>{statutes}', "constitution": panel(con, hist)}
    strip = ('<div class="twntabs lw-tabs" role="tablist" aria-label="New Hampshire Laws" hidden>'
             + "".join(
                 f'<button type="button" role="tab" id="tab-{pid}" data-pane="{pid}" aria-controls="{pid}" '
                 f'aria-selected="{"true" if k == 0 else "false"}" tabindex="{0 if k == 0 else -1}">'
                 f"{E(name)}</button>" for k, (pid, name) in enumerate(TABS)) + "</div>")
    return strip + "".join(
        f'<div class="twnpane" id="{pid}" role="tabpanel" aria-labelledby="tab-{pid}">'
        f'<h2 class="twnph">{E(name)}</h2>{panes[pid]}</div>' for pid, name in TABS) + TABS_JS


# THE SWITCHING SCRIPT, the town pages' (build_town_pages.TABS_JS) with one
# thing more: an address may name an article inside a panel, not only a panel,
# and then that panel opens and the page lands on the article. A tab chosen is
# written into the address with replaceState and the page's own path -- never
# a bare "#", which the page's <base href="/"> resolves against the site's
# root -- so Back leaves the page rather than stepping through its tabs.
#
# THE BROWSER'S OWN JUMP CAME TOO SOON. It goes to an article while the panel
# that holds it is still hidden, and lands nowhere; so once the page has
# loaded, an address naming an article is scrolled to again -- and once more
# when the web fonts arrive, because on a phone their wider letters push
# Part Second's articles a screen or more further down (Article 10 was found
# under Article 4 on 17 October 2026).
TABS_JS = "<script>\n" + IJ.script("constitution_tab") + "</script>"


# A CITATION OF AN ARTICLE BECOMES A LINK TO IT (17 October 2026). The Learn
# pages cite the Constitution as a reader would -- "Part Second, Article 44",
# "Part II, Article 9", "articles 71 and 81 of Part Second" -- and each now
# opens that article on the Laws page. Only an article the Constitution as
# read holds is linked, and nothing already inside a link or a tag is touched.
_PART = {"first": 1, "i": 1, "second": 2, "ii": 2}
_NUM = r"\d{1,3}(?:-[a-z])?"
CITE_ONE = re.compile(r"\bPart (First|Second|II|I),? Article (" + _NUM + r")\b")
CITE_MANY = re.compile(r"\b([Aa]rticles? )(" + _NUM + r"(?:(?:, | and |, and )" + _NUM + r")*)"
                       r"( of Part (First|Second|II|I))\b")
_SKIP = re.compile(r"(<a\b.*?</a>|<[^>]+>)", re.S)


def link_citations(text, con):
    """`text` with each citation of an article the Constitution holds linked to it."""
    have = {(p, a["key"]) for p, a in PC.articles(con)}
    if not have or not text:
        return text

    def one(m):
        p, key = _PART[m.group(1).lower()], m.group(2)
        if (p, key) not in have:
            return m.group(0)
        return f'<a href="{PC.href(p, key)}">{m.group(0)}</a>'

    def many(m):
        p = _PART[m.group(4).lower()]
        nums = re.split(r"(, and |, | and )", m.group(2))
        if not all((p, n) in have for n in nums[::2]):
            return m.group(0)
        linked = "".join(f'<a href="{PC.href(p, n)}">{n}</a>' if i % 2 == 0 else n
                         for i, n in enumerate(nums))
        return m.group(1) + linked + m.group(3)

    out = []
    for i, seg in enumerate(_SKIP.split(text)):
        if i % 2:
            out.append(seg)
        else:
            out.append(CITE_ONE.sub(one, CITE_MANY.sub(many, seg)))
    return "".join(out)
