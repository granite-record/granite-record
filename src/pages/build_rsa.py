#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.17
"""
The statutes (RSA) as pages: /laws, and one page a chapter at /laws/<chapter>.

    python3 src/pages/build_rsa.py --site site --base https://graniterecord.org

Asks nobody. Reads the General Court's statute table through rsa.py, what
rsa.py wrote (rsa_citations.json), and the bill index the site build wrote
(site/idx/<term>.json) for each bill's number, title and whether it is still
moving. Writes site/laws.html, site/laws/<chapter>.html and the three files the
landing page's search reads, site/laws/chapters.json, headings.json and
words.json.

THE DESIGN IS RSA_PAGE.md (7 October 2026), with the person's asks of 11
October: "a more easily searchable and viewable interface for RSAs,
including tagging sections that are in progress that propose to amend that
RSA section, with history of how it's changed through various bills over the
years. You should be able to easily scroll through sections and search
through the database for related laws in plain text, and the RSA pages
should be linked throughout the site to the Granite Record pages as an
interlinked system."

A CHAPTER PAGE, top to bottom (RSA_PAGE.md §5):

1. The chapter's number and name, and one line saying what the text is: the
   table as the General Court holds it, through the laws of the latest year
   its source notes name, with the official page one link away.
2. Pending: the sitting term's bills still moving that say they change this
   chapter, as chips, each section they name tagged below.
3. The sections in order, under the chapter's own inner headings, each an
   anchor (/laws/91-a#s4) carrying: its heading, a Pending tag where a bill
   still moving would change it, its text with every citation the table
   holds linked to its own anchor, its source note, and four folds -- How it
   has changed (the source note's laws, newest first, each the bill it was),
   Also proposed by (every other bill whose own instructions name the
   section, failed ones included), Cites, Cited by.
4. A repealed section is one muted line, its anchor kept, so an old bill's
   link still lands on something true.

TWO RECORDS, NOT ONE (RSA_PAGE.md §3). "How it has changed" is the Office of
Legislative Services' source note; "Also proposed by" is the bills' own
instructions. They are labelled apart and never merged.

THE TEXT IS TODAY'S. A 1997 bill's link opens the section as it reads now;
the currency line says so, and the history says when it changed, not what
it said.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import datetime
import html
import json
import math
import re

import build_date
import components as C
import constitution_tab as CT
import parse_constitution as PC
import rsa
import shell as S
import structured as LD

E = html.escape
SHOWN = 8          # a list folds after this many, as the bill page's Amends row does
OG_ALT = "Granite Record: New Hampshire's statutes"

STOP = set("""a an and are as at be been by for from has have in is it its may not of on or
shall such that the this to under which with any all other each than those these who whom
whose upon into within without where when there their them they was were will would
pursuant thereof therein hereby section chapter paragraph subparagraph rsa provided
including include includes also more less only same such state new hampshire person""".split())
WORD = re.compile(r"[a-z][a-z']{2,}")


SMALL = set("a an and as at but by for in nor of on or per the to vs via with from into upon".split())
ROMAN = re.compile(r"^(?=[IVXLC]+$)[IVXLC]+$")


def nice(name):
    """The table's capitals as a heading: "ACCESS TO GOVERNMENTAL RECORDS AND
    MEETINGS" -> "Access to Governmental Records and Meetings", Roman numerals
    and abbreviations of two or more capitals left as they are."""
    if not name or not name.isupper():
        return name or ""
    out = []
    for i, w in enumerate(name.split()):
        core = w.strip("(),;:.")
        if ROMAN.match(core) or (len(core) <= 4 and "." in w) or core in ("RSA", "UCC", "N.H."):
            out.append(w)
        elif i and w.lower() in SMALL:
            out.append(w.lower())
        else:
            out.append("-".join(x[:1].upper() + x[1:].lower() for x in w.split("-")))
    return " ".join(out)


def bill_order(key):
    """A bill key in the order the site lists bills: kind, then number."""
    term, _, bill = key.partition("/")
    m = re.match(r"([A-Z]+)(\d+)", bill)
    return (term, m.group(1), int(m.group(2))) if m else (term, bill, 0)


def stem(w):
    """The light stem the search uses on both sides, so "dogs" finds "dog"
    and "liabilities" "liability"; the same rule is in LANDING_JS."""
    w = w.lower().strip("'")
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def chapter_slug(ch):
    return ch.lower()


# The chapters whose page is a folder's index.html (chapter_file), and so
# whose address ends in a slash (chapter_path). Two scripts cannot import
# this and say it again -- app.js's LAW_FOLDERS and build_pages.NOT_FOUND's
# -- and preflight holds both to this one (16 October 2026).
FOLDER_CHAPTERS = ("404",)


def chapter_file(out, ch):
    """Where a chapter's page is written. RSA 404's page is laws/404/index.html,
    not laws/404.html: the host serves a folder's 404.html for every address
    in it that has no page, so every mistyped /laws/ address showed chapter
    404 (the preview, 11 October 2026). /laws/404/ is answered from the
    folder, and /laws/404 with a redirect to it, so chapter_path gives the
    address with its slash."""
    slug = chapter_slug(ch)
    return out / slug / "index.html" if slug in FOLDER_CHAPTERS else out / f"{slug}.html"


def chapter_path(ch, sec=""):
    """The address the host serves a chapter's page at: /laws/91-a, and
    /laws/404/ for the one chapter chapter_file puts in a folder; with
    `sec`, that section's anchor on it (/laws/404/#s5).

    THE SLASH IS PART OF RSA 404'S ADDRESS (the sitemap audit, 16 October
    2026). The host answers /laws/404 with a 308 to /laws/404/, measured on
    the live site, so the sitemap listed an address that redirects and the
    page named as its canonical the address that redirected back to it. Every
    place that writes a chapter's address asks here: the links, the sitemap,
    the page's canonical, og:url and citation, and the bill records, bill
    pages, feeds and guides that link a law."""
    slug = chapter_slug(ch)
    return f"/laws/{slug}" + ("/" if slug in FOLDER_CHAPTERS else "") + (f"#s{sec}" if sec else "")


def sec_anchor(addr):
    return "s" + addr.split(":", 1)[1]


def href(addr):
    """The site's own address for a statute address: /laws/91-a#s4, /laws/91-a."""
    ch, _, sec = addr.partition(":")
    return chapter_path(ch) + (f"#{sec_anchor(addr)}" if sec else "")


def term_of_year(y):
    y = int(y)
    a = y if y % 2 else y - 1
    return f"{a}-{a + 1}"


def chapter_label(ch, name):
    """ "Chapter 71: The Tax Commission" (the person, 11 October 2026: "Laws
    should also be labeled as Chapter 71: The Tax Commission rather than just
    71")."""
    return f"Chapter {ch}: {nice(name)}" if name else f"Chapter {ch}"


def title_label(tno, tname):
    """("VI", "TITLE VI PUBLIC OFFICERS AND EMPLOYEES") -> ("Title VI", "Public Officers and Employees")."""
    return f"Title {tno}", nice(re.sub(r"^TITLE\s+\S+\s*", "", tname or "").strip())


# A CHAPTER'S TOPICS are the bill search's own, read off the bills that say
# they change it (the person, 11 October 2026: "If laws are groupable into
# topics in a similar way to bills, that would be helpful for searching").
# Miscellaneous says nothing about a chapter and is not counted; a topic is
# the chapter's where at least TOPIC_SHARE of the rest of its bills and at
# least TOPIC_LEAST of them carry it, at most two. A chapter no bill of the
# record has changed has none, rather than a guessed one: 1,274 of 1,786 have
# one on 8 September 2026's table.
TOPIC_SHARE, TOPIC_LEAST, TOPIC_SKIP = 0.3, 2, ("Miscellaneous",)


def chapter_topics(data, bills):
    votes = collections.defaultdict(collections.Counter)
    for term, bs in data.get("bills", {}).items():
        for bill, rec in bs.items():
            tp = bills.row(f"{term}/{bill}").get("topic") or ""
            if not tp or tp in TOPIC_SKIP:
                continue
            for ch in {str(c).split(":")[0] for c in rec.get("changes") or []}:
                votes[ch][tp] += 1
    out = {}
    for ch, c in votes.items():
        n = sum(c.values())
        top = [t for t, v in c.most_common(2) if v >= TOPIC_LEAST and v / n >= TOPIC_SHARE]
        if top:
            out[ch] = top
    return out


def chapter_pending(data, bills):
    """{chapter: [bill keys]} for the sitting term's bills still moving that
    say they change it."""
    out = collections.defaultdict(set)
    for term, bs in data.get("bills", {}).items():
        for bill, rec in bs.items():
            k = f"{term}/{bill}"
            chs = {str(c).split(":")[0] for c in rec.get("changes") or []}
            if chs and bills.pending(k):
                for ch in chs:
                    out[ch].add(k)
    return {ch: sorted(ks, key=bill_order) for ch, ks in out.items()}


# ------------------------------------------------------------------ bills

class Bills:
    """Each bill's number, title, chip and whether it is still moving, from
    the site's own index (site/idx/<term>.json)."""

    def __init__(self, site, current):
        self.rows, self.current = {}, current
        for p in sorted((Path(site) / "idx").glob("[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9].json")):
            try:
                for r in json.loads(p.read_text(encoding="utf-8")):
                    self.rows[f"{p.stem}/{r.get('id')}"] = r
            except (OSError, ValueError):
                continue

    def row(self, key):
        return self.rows.get(key) or {}

    def moving(self, key):
        r = self.row(key)
        return bool(r) and S.still_moving(dict(r, term=r.get("term") or key.split("/")[0]),
                                          self.current)

    def pending(self, key):
        """Pending, as the Laws page says it: still moving, and not sent to
        interim study (the person, 22 October 2026: a bill studied "won't
        become law this year regardless of whether [it is] recommended for
        future legislation"). It is followable still (shell.still_moving),
        and listed under Other bills that proposed changes."""
        return self.moving(key) and self.row(key).get("kind") != "study"

    def label(self, key):
        r = self.row(key)
        term, _, bill = key.partition("/")
        if r.get("n"):
            return r["n"]
        m = re.match(r"([A-Z]+)(\d+)$", bill)
        return f"{m.group(1)} {m.group(2)}" if m else bill

    def url(self, key):
        r = self.row(key)
        term, _, bill = key.partition("/")
        year = r.get("year") or term[:4]
        return f"/bill/{year}/{bill.lower()}"

    def chip(self, key, with_year=True, always_year=False):
        """A bill as the site draws one in a list: its number linked, its
        status after it, the term's years where it is not the sitting one --
        or always, where a list mixes the sitting term with others (Other
        bills that proposed changes, the person, 22 October 2026)."""
        r = self.row(key)
        term = key.split("/")[0]
        when = ("" if not with_year or (term == self.current and not always_year)
                else f' <span class="rs-yr">{E(term)}</span>')
        st = r.get("chip") or ""
        title = r.get("title") or ""
        return (f'<li><a href="{E(self.url(key))}" title="{E(title)}">{E(self.label(key))}</a>{when}'
                + (f' <span class="rs-st">{E(st)}</span>' if st else "") + "</li>")


def folded(items, cls="rs-list"):
    """A list of <li>, the first SHOWN open and the rest behind Show all."""
    if not items:
        return ""
    head = "".join(items[:SHOWN])
    rest = items[SHOWN:]
    more = (f'<details class="rs-more"><summary>Show all {len(items)}</summary>'
            f'<ul class="{cls}">{"".join(rest)}</ul></details>') if rest else ""
    return f'<ul class="{cls}">{head}</ul>{more}'


# ------------------------------------------------------------------ text

def linked_text(table, text, own):
    """The section's text as paragraphs, every citation the table holds a
    link to its own anchor, the rest as written; a repealed target says so."""
    out = []
    for para in [p.strip() for p in (text or "").split("\n") if p.strip()]:
        pieces, pos = [], 0
        for c in rsa.cites(para):
            kind, target = table.resolve(c.chapter, c.section)
            if not kind or target == own:
                continue
            # the span to link: from "RSA" for the head, the number alone in a list
            st = c.start if c.how == "rsa" else para.find(c.section, c.start)
            en = c.end
            if st < pos or st < 0:
                continue
            gone = kind == "section" and table.sections[target].repealed
            pieces.append(E(para[pos:st]))
            pieces.append(f'<a href="{E(href(target))}">{E(para[st:en])}</a>'
                          + (' <span class="rs-gone">(repealed)</span>' if gone else ""))
            pos = en
        pieces.append(E(para[pos:]))
        out.append(f"<p>{''.join(pieces)}</p>")
    return "".join(out)


# ------------------------------------------------------------------ indexes

# A CHAPTER'S POPULAR NAME, as the statutes themselves write it: readers search
# "right to know", and chapter 91-A is titled "Access to Governmental Records
# and Meetings". The statutes say the name beside the citation, in either
# order -- "the right-to-know law, RSA 91-A", "RSA 91-A, the right-to-know
# law" -- or declare it: "This chapter shall be known as the Uniform
# Commercial Code". A name is kept where the chapter declares it or the
# statutes use it at least twice.
KNOWN_AS = re.compile(r"(?:shall|may)\s+be\s+(?:known|cited)(?:\s+and\s+(?:may\s+be\s+)?cited)?\s+as\s+"
                      r"(?:the\s+)?[\"\u201c]?([A-Z][^\"\u201d.;]{3,80}?)[\"\u201d]?(?:\.|,|;|\s+and\b)")
NAME_THEN_RSA = re.compile(r"\bthe\s+((?:[A-Za-z'\u2019-]+\s+){0,4}(?:law|act|code))\s*,\s*RSA\s+"
                           r"(\d{1,3}(?:-[A-Z]{1,2})?)(?![:\d])", re.I)
RSA_THEN_NAME = re.compile(r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)(?![:\d])\s*,\s*the\s+"
                           r"((?:[A-Za-z'\u2019-]+\s+){0,4}(?:law|act|code))\b", re.I)


def popular_names(table):
    """{chapter: [names]} from the statutes' own words."""
    got = collections.defaultdict(collections.Counter)
    for s in table.sections.values():
        for m in KNOWN_AS.finditer(s.text):
            got[s.chapter][m.group(1).strip()] += 2
        for m in NAME_THEN_RSA.finditer(s.text):
            got[m.group(2).upper()][m.group(1).strip().lower()] += 1
        for m in RSA_THEN_NAME.finditer(s.text):
            got[m.group(1).upper()][m.group(2).strip().lower()] += 1
    out = {}
    for ch, names in got.items():
        if ch not in table.chapters:
            continue
        keep, seen = [], set()
        for n, c in names.most_common():
            if c >= 2 and n.lower() not in seen:
                seen.add(n.lower())
                keep.append(n)
        if keep:
            out[ch] = keep[:4]
    return out


def build_indexes(table, cites, topics=None, pending=None):
    """chapters.json, headings.json and words.json for the landing page's
    search (RSA_PAGE.md §6), all in the reader's browser.

    words.json is what each section is ABOUT, not every word in it: the
    heading's words, and its twelve most telling words by how often the
    section uses them against how many sections do -- the plain-text search
    the person asked for, at a size a reader can fetch once."""
    names = popular_names(table)
    chapters = {ch: [nice(info["name"]), info["title_no"], len(info["sections"]), info["repealed"],
                     names.get(ch, []), (topics or {}).get(ch, []), len((pending or {}).get(ch, []))]
                for ch, info in table.chapters.items()}
    headings = [[a, s.heading] for a, s in table.sections.items() if not s.repealed]
    df = collections.Counter()
    tfs = {}
    for a, s in table.sections.items():
        if s.repealed:
            continue
        tf = collections.Counter(stem(w) for w in WORD.findall(s.text.lower()) if w not in STOP)
        tfs[a] = tf
        df.update(tf.keys())
    n = max(1, len(tfs))
    order = list(tfs)
    idx = {a: i for i, a in enumerate(order)}
    post = collections.defaultdict(list)
    for a, tf in tfs.items():
        head = {stem(w) for w in WORD.findall(table.sections[a].heading.lower()) if w not in STOP}
        top = sorted(tf, key=lambda w: (-tf[w] * math.log(n / df[w]), w))[:12]
        for w in sorted(head | set(top)):
            post[w].append(idx[a])
    # Postings as the gap from the one before, which compresses to about half
    # (951 KB to 518 KB gzipped on 8 September 2026's table), and numbered by
    # headings.json's own order, which is the same list -- so the sections are
    # not written twice.
    assert [h[0] for h in headings] == order, "headings.json and words.json list sections differently"
    words = {"words": {w: [v[0]] + [b - a for a, b in zip(v, v[1:])] for w, v in sorted(post.items())}}
    return chapters, headings, words


# ------------------------------------------------------------------ pages

# A REPEALED CHAPTER'S NOTE, as the table holds it: its title and name in
# capitals, then "[Repealed by 1971, 227:15, eff. Aug. 17, 1971.]". All 468
# chapters the table marks repealed carry the bracket, and nine of them were
# not repealed but moved: "[Redesignated as RSA 246 by 2024, 33:4, eff. July
# 1, 2024.]". The banner says which, in words.
REPEAL = re.compile(r"\[\s*Repealed,?\s+(?:by\s+)?(\d{4}),\s*([^\]]*?)"
                    r"(?:,?\s*(?:eff\.|effective)\s*([^\]]*?))?\.?\s*\]")
MOVED = re.compile(r"\[\s*Redesignated\s+as\s+RSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)\s+by\s+(\d{4}),\s*"
                   r"([^\]]*?)(?:,?\s*(?:eff\.|effective)\s*([^\]]*?))?\.?\s*\]")


def moved_to(note):
    """The chapter a redesignated chapter became, or ''."""
    m = MOVED.search(note or "")
    return m.group(1) if m else ""


def repeal_words(note):
    """The banner's words after its first: when and by what law the chapter
    was repealed or moved, or the bracket as the table has it where its words
    are in neither shape, or ''."""
    note = note or ""
    m = MOVED.search(note)
    if m:
        to, y, law, eff = m.groups()
        return (f' It is now <a href="{E(href(to))}">RSA {E(to)}</a>, moved there by the Laws of {E(y)}, '
                f"chapter {E(law)}" + (f", effective {E(eff)}." if eff else "."))
    m = REPEAL.search(note)
    if m:
        y, law, eff = m.groups()
        return (f" It was repealed by the Laws of {E(y)}, chapter {E(law)}"
                + (f", effective {E(eff)}." if eff else "."))
    b = re.search(r"\[([^\]]+)\]", note)
    return f" {E(b.group(1).strip())}" if b else ""


def chapter_page(tmpl, table, data, bills, ch, base):
    info = table.chapters[ch]
    secs = info["sections"]
    proposed = collections.defaultdict(list)     # address -> [bill key]
    for term, bs in data.get("bills", {}).items():
        for bill, rec in bs.items():
            for a in rec.get("changes", []):
                if a == ch or a.startswith(ch + ":"):
                    proposed[a].append(f"{term}/{bill}")
    cited_by = collections.defaultdict(list)
    for src, targets in data.get("statute", {}).items():
        for t in targets:
            if t.startswith(ch + ":") or t == ch:
                cited_by[t].append(src)
    pending_ch = sorted({k for a, ks in proposed.items() for k in ks if bills.pending(k)},
                        key=bill_order)
    latest = data.get("asof", {}).get("laws_through") or ""
    # THE PAGE'S OWN ADDRESS, AS THE HOST SERVES IT (16 October 2026): the
    # canonical, og:url, citation and the sections' own links all start from
    # this, so RSA 404's carry its slash (chapter_path).
    path = chapter_path(ch)
    title = chapter_label(ch, info["name"])
    first = table.sections[secs[0]] if secs else None
    # The General Court's own table of contents page for the chapter, the
    # address build_site_v2.rsa_url has linked for a chapter since 4
    # September, rather than a guessed one for the whole chapter's text.
    tno = (first.url.split("/")[0] if first and first.url else "") or (first.title_no if first else "")
    official = (f"https://gc.nh.gov/rsa/html/NHTOC/NHTOC-{tno}-{ch}.htm" if tno
                else "https://gc.nh.gov/rsa/html/nhtoc.htm")
    # THE NAME A READER SEARCHES FOR (the SEO review, 12 October 2026). The
    # title read "Chapter 91-A -- Laws": no "RSA", which is how the chapter is
    # cited and searched, and no name. Now "RSA 91-A -- Access to Governmental
    # Records and Meetings", with the state in the link card, and the page
    # says what it is in structured data, as a bill's does.
    name = nice(info["name"]) if info.get("name") else ""
    p = S.page(tmpl, path=path, base=base, title=S.title_of(f"RSA {ch}", name),
               og_title=f"New Hampshire RSA {ch}" + (f": {name}" if name else ""),
               description=f"New Hampshire RSA chapter {ch}, {name or info['name']}: "
               "its text, the bills that changed it and the bills that would.",
               og_image="og-learn.png", og_alt=OG_ALT, globals={"GR_STATIC": True, "GR_LAW": ch},
               noscript="", skip_label="Skip to the statute", sr_title="",
               nav_current="laws.html", cite=False,
               jsonld=LD.statute_chapter(ch, name, base, S.canon(path), official,
                                         bool(info.get("repealed"))))
    lead = (f"The text as the General Court's table holds it. {as_of(latest)} "
            f'<a href="{E(official)}" rel="noopener">The official text on gc.nh.gov</a>.')
    tl, tn = title_label(info["title_no"], info["title"])
    crumb = f"{tl}: {tn}" if tn else tl
    # A REPEALED CHAPTER SAYS SO AT THE TOP, at the size of the lead (the
    # person, 11 October 2026: "Repealed pages are a bit hard to tell that the
    # chapter has been repealed on the page since the text is quite small").
    gone = ""
    if info.get("repealed"):
        word = "Moved" if moved_to(info.get("note")) else "Repealed"
        gone = (f'<p class="rs-banner" role="note"><strong>{word}.</strong> This chapter is no '
                f'longer in force.{repeal_words(info.get("note"))}</p>')
    head = (f'<header class="l-head"><p class="rs-crumb"><a href="/laws">Laws</a> &rsaquo; '
            f'<a href="/laws#t-{E(info["title_no"])}">{E(crumb)}</a></p>'
            f'<p class="rs-kick">RSA {E(ch)}</p><h1>{E(title)}</h1>{gone}'
            f'<p class="l-lead">{lead}</p>' + S.cite_block(path, title, base, S.BUILT) + "</header>")
    pend = ""
    if pending_ch:
        pend = ('<section class="rs-pending" aria-label="Pending"><h2>Bills now before the '
                f'General Court that would change this chapter</h2>'
                + folded([bills.chip(k) for k in pending_ch]) + "</section>")
    toc_items = []
    body = []
    sub = None
    for a in secs:
        s = table.sections[a]
        if s.sub and s.sub != sub:
            sub = s.sub
            body.append(f'<h2 class="rs-sub">{E(sub)}</h2>')
        anchor = sec_anchor(a)
        if s.repealed:
            body.append(f'<p class="rs-repealed" id="{E(anchor)}"><a href="{E(path)}#{E(anchor)}">{E(a)}</a> '
                        f'<span class="rs-rbadge">Repealed</span> {E(s.heading)}</p>')
            toc_items.append(f'<li class="rs-off"><a href="{E(path)}#{E(anchor)}">{E(a)}</a> '
                             f'<span>Repealed</span></li>')
            continue
        toc_items.append(f'<li><a href="{E(path)}#{E(anchor)}"><b>{E(a)}</b> {E(s.heading)}</a></li>')
        pend_k = sorted((k for k in proposed.get(a, []) if bills.pending(k)), key=bill_order)
        hist = list(reversed(data.get("enacted", {}).get(a, [])))
        # A BILL IN THE HISTORY IS NOT ALSO "PROPOSED" (the person, 11 October
        # 2026: the two "sometimes show the exact same bill numbers which is
        # redundant"): the other list is the bills that did not become this
        # section's law.
        in_hist = {b for _y, _law, b in hist if b}
        other = [k for k in proposed.get(a, []) if not bills.pending(k) and k not in in_hist]
        rows = []
        if hist:
            items = []
            for y, law, b in hist:
                bl = (f' &middot; <a href="{E(bills.url(b))}">{E(bills.label(b))}</a>' if b else "")
                items.append(f'<li><span class="rs-yr">{E(y)}</span> Laws of {E(y)}, chapter '
                             f'{E(law.split(":")[0])}{bl}</li>')
            rows.append(("How it has changed", "From the section's source note, newest first.",
                         folded(items, "rs-hist")))
        if other:
            other.sort(key=lambda k: (k.split("/")[0], bill_order(k)[1], -bill_order(k)[2]), reverse=True)
            rows.append(("Other bills that proposed changes", "Bills whose own text says they "
                         "change this section, and that are not in its history above.",
                         folded([bills.chip(k, always_year=True) for k in other])))
        out_c = data.get("statute", {}).get(a, [])
        if out_c:
            rows.append(("Cites", "", folded([f'<li><a href="{E(href(t))}">RSA {E(t)}</a></li>'
                                              for t in out_c], "rs-refs")))
        if cited_by.get(a):
            rows.append(("Cited by", "", folded([f'<li><a href="{E(href(t))}">RSA {E(t)}</a></li>'
                                                 for t in sorted(cited_by[a], key=rsa.addr_key)],
                                                "rs-refs")))
        tag = ""
        if pend_k:
            tag = (f'<details class="rs-tag"><summary>Pending: {len(pend_k)} '
                   f'bill{"s" if len(pend_k) != 1 else ""}</summary>'
                   + folded([bills.chip(k) for k in pend_k]) + "</details>")
        folds = "".join(
            f'<details class="rs-fold"><summary>{E(h)}</summary>'
            + (f'<p class="rs-note">{E(n)}</p>' if n else "") + f"{c}</details>"
            for h, n, c in rows)
        body.append(
            f'<section class="rs-sec" id="{E(anchor)}"><h3 class="rs-h"><a href="{E(path)}#{E(anchor)}">'
            f'{E(a)}</a> {E(s.heading)}</h3>{tag}'
            f'<div class="rs-text" translate="no">{linked_text(table, s.text, a)}</div>'
            + (f'<p class="rs-source">Source. {E(s.note)}</p>' if s.note else "")
            + (f'<div class="rs-folds">{folds}</div>' if folds else "") + "</section>")
    # THE SECTIONS IN A SIDEBAR (the person, 11 October 2026: "when you're in
    # an RSA chapter, the sidebar would show you the chapter sections so you
    # could easily click through them"): sticky beside the text on a wide
    # screen, a fold above it on a narrow one.
    toc = ""
    if toc_items:
        toc = (f'<nav class="rs-side" aria-label="Sections of chapter {E(ch)}"><details class="rs-sidebox" open>'
               f'<summary><span class="rs-sumw">Chapter {E(ch)}: {len(toc_items)} '
               f'section{"s" if len(toc_items) != 1 else ""}</span>'
               f'<span class="rs-now" aria-hidden="true"></span></summary>'
               f'<ol>{"".join(toc_items)}</ol></details></nav>')
    art = f'<div class="rs-art">{pend}{"".join(body)}</div>'
    return p.replace('<div id="results"></div>',
                     f'<div id="results"><div class="l-page rs-page">{head}'
                     f'<div class="rs-chap{" rs-notoc" if not toc else ""}">{toc}{art}</div></div>'
                     f'{CHAPTER_JS}</div>', 1)


CHAPTER_JS = """<script>
(function(){
  // The sidebar's sections: the one being read marked as the page scrolls
  // past it. ON A PHONE (the person, 11 October 2026: "The index is not
  // accessible on mobile on individual chapters") the list is a bar held at
  // the top of the screen, naming the section being read; it opens over the
  // page, and choosing a section closes it.
  var d=document.querySelector(".rs-sidebox");if(!d)return;
  var narrow=function(){return window.matchMedia&&matchMedia("(max-width:60em)").matches;};
  if(narrow())d.open=false;
  var links={},box=d.querySelector("ol"),cur=null,now=d.querySelector(".rs-now");
  [].forEach.call(d.querySelectorAll("a[href*='#']"),function(a){links[a.getAttribute("href").split("#")[1]]=a;});
  d.addEventListener("click",function(e){if(e.target.closest("a")&&narrow())d.open=false;});
  document.addEventListener("keydown",function(e){if(e.key==="Escape"&&d.open&&narrow()){d.open=false;d.querySelector("summary").focus();}});
  if(!("IntersectionObserver" in window)||!box)return;
  var io=new IntersectionObserver(function(es){es.forEach(function(e){
    if(!e.isIntersecting)return;var a=links[e.target.id];if(!a||a===cur)return;
    if(cur)cur.removeAttribute("aria-current");a.setAttribute("aria-current","location");cur=a;
    if(now){var b=a.querySelector("b");now.textContent=b?b.textContent:a.textContent.split(" ")[0];}
    var li=a.parentNode;if(li.offsetTop<box.scrollTop||li.offsetTop>box.scrollTop+box.clientHeight-40)
      box.scrollTop=li.offsetTop-box.clientHeight/3;});},{rootMargin:"-15% 0px -75% 0px"});
  [].forEach.call(document.querySelectorAll(".rs-sec[id],.rs-repealed[id]"),function(s){io.observe(s);});
})();
</script>"""


LANDING_JS = """<script>
(function(){
  var root=document.getElementById("lw");if(!root)return;
  var box=document.getElementById("rsq"),out=document.getElementById("rsout"),dir=document.getElementById("lwdir"),
      read=document.getElementById("lwread"),count=document.getElementById("lwcount");
  var narrow=function(){return window.matchMedia&&matchMedia("(max-width:60em)").matches;};
  var CH=null,HD=null,WD=null,PAGES={};
  function get(u){return fetch(u).then(function(r){return r.ok?r.json():null;});}
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function chOf(a){return a.split(":")[0];}
  // A chapter's address is the one its row links (build_rsa.chapter_path),
  // so RSA 404's keeps the slash the host serves it at.
  function link(a){var p=a.split(":"),g=root.querySelector('.lw-ch[data-ch="'+p[0]+'"] > .lw-go');
    return (g?g.getAttribute("href"):"/laws/"+p[0].toLowerCase())+(p[1]?"#s"+p[1]:"");}
  function heads(){return HD?Promise.resolve(HD):get("laws/headings.json").then(function(d){return HD=d||[];});}
  function chapters(){return CH?Promise.resolve(CH):get("laws/chapters.json").then(function(d){return CH=d||{};});}

  // ---- THE READER: a section's text from its chapter's own page, on the right.
  function page(ch){
    if(!PAGES[ch])PAGES[ch]=fetch(link(ch)).then(function(r){return r.ok?r.text():"";}).then(function(t){
      return new DOMParser().parseFromString(t,"text/html");});
    return PAGES[ch];}
  function open(a){
    if(narrow()){location.href=link(a);return;}
    var ch=chOf(a),li=root.querySelector('.lw-ch[data-ch="'+ch+'"]');
    [].forEach.call(root.querySelectorAll("[data-sec][aria-current]"),function(x){x.removeAttribute("aria-current");});
    [].forEach.call(root.querySelectorAll('[data-sec="'+a+'"]'),function(x){x.setAttribute("aria-current","true");});
    var crumb=li?crumbOf(li):"",name=li?labelOf(li):"Chapter "+ch;
    read.innerHTML='<p class="lw-wait">Opening RSA '+esc(a)+'&hellip;</p>';
    page(ch).then(function(doc){
      var sec=doc&&doc.getElementById("s"+a.split(":")[1]);
      read.innerHTML='<p class="lw-rcrumb">'+esc(crumb)+' &rsaquo; '+esc(name)+'</p>'
        +(sec?sec.outerHTML:'<p>This section could not be opened here.</p>')
        +'<p class="lw-own"><a href="'+link(a)+'">Open RSA '+esc(a)+' on its chapter&rsquo;s page</a></p>';
      read.scrollTop=0;
      var r=read.getBoundingClientRect();if(r.top<0)read.scrollIntoView({block:"start"});
    });
  }
  root.addEventListener("click",function(e){
    var t=e.target.closest("[data-sec]");if(!t||e.metaKey||e.ctrlKey||e.shiftKey)return;
    if(narrow())return;e.preventDefault();open(t.getAttribute("data-sec"));});

  // A chapter's label and its title's name, from what the row already shows.
  function labelOf(li){var n=li.querySelector(".lw-chname");return "Chapter "+li.getAttribute("data-ch")+": "+(n?n.textContent:"");}
  function crumbOf(li){var t=li.closest(".lw-title"),a=t&&t.querySelector(".lw-tno"),b=t&&t.querySelector(".lw-tname");
    return (a?a.textContent:"")+(b&&b.textContent?": "+b.textContent:"");}
  // ---- A CHAPTER OPENED IN THE DIRECTORY lists its sections, and the way
  // to its own page under them.
  root.addEventListener("toggle",function(e){
    var d=e.target;if(!d.classList||!d.classList.contains("lw-chd")||!d.open)return;
    if(d.querySelector(".lw-secs"))return;
    var ch=d.parentNode.getAttribute("data-ch");
    var ol=document.createElement("ol");ol.className="lw-secs";ol.setAttribute("data-ch",ch);
    ol.innerHTML='<li class="lw-none">Loading the sections&hellip;</li>';
    var own=document.createElement("p");own.className="lw-own";
    own.innerHTML='<a href="'+link(ch)+'">Open Chapter '+esc(ch)+' on its own page</a>';
    d.appendChild(ol);d.appendChild(own);
    heads().then(function(hd){
      var rows=hd.filter(function(x){return chOf(x[0])===ch;});
      ol.innerHTML=rows.length?rows.map(function(x){return '<li><a href="'+link(x[0])+'" data-sec="'+esc(x[0])
        +'"><b>'+esc(x[0])+'</b> '+esc(x[1])+'</a></li>';}).join(""):'<li class="lw-none">No section of this chapter is in force.</li>';
    });
  },true);

  // ---- THE FILTERS: status, topic and title, over the chapters the page lists.
  var rows=[].slice.call(root.querySelectorAll(".lw-ch")),titles=[].slice.call(root.querySelectorAll(".lw-title"));
  function picked(name){return [].slice.call(root.querySelectorAll('input[name="'+name+'"]:checked')).map(function(x){return x.value;});}
  function keep(li){
    var st=picked("st"),tp=picked("tp"),ti=picked("ti");
    if(st.length){var ok=st.some(function(v){return v==="in"?li.getAttribute("data-rep")!=="1":
      v==="rep"?li.getAttribute("data-rep")==="1":Number(li.getAttribute("data-pend"))>0;});if(!ok)return false;}
    if(tp.length){var mine=(li.getAttribute("data-topics")||"").split("|");if(!tp.some(function(v){return mine.indexOf(v)>=0;}))return false;}
    if(ti.length&&ti.indexOf(li.getAttribute("data-title"))<0)return false;
    return true;}
  function filter(){
    var any=picked("st").length+picked("tp").length+picked("ti").length,shown=0,ts=0;
    rows.forEach(function(li){var k=keep(li);li.hidden=!k;if(k)shown++;});
    titles.forEach(function(t){var n=t.querySelectorAll(".lw-ch:not([hidden])").length;t.hidden=!n;
      if(n)ts++;var c=t.querySelector(".lw-tn");if(c)c.textContent=any?n+" of "+c.getAttribute("data-all"):c.getAttribute("data-all");
      if(any&&n&&n<=40)t.open=true;});
    count.textContent=any?shown.toLocaleString()+" chapter"+(shown===1?"":"s")+" in "+ts+" title"+(ts===1?"":"s")+" match":
      count.getAttribute("data-all");
    document.getElementById("lwclear").hidden=!any;
  }
  root.addEventListener("change",function(e){if(e.target.matches&&e.target.matches(".lw-side input[type=checkbox]"))filter();});
  document.getElementById("lwclear").addEventListener("click",function(){
    [].forEach.call(root.querySelectorAll(".lw-side input[type=checkbox]"),function(x){x.checked=false;});
    titles.forEach(function(t){t.open=false;});filter();});

  // ---- THE SEARCH: a number goes straight to it; words are ranked across the
  // chapters' names, the sections' headings and what each section is about.
  function stem(w){w=w.toLowerCase().replace(/^'+|'+$/g,"");if(/'s$/.test(w))w=w.slice(0,-2);
    if(w.length>4&&/ies$/.test(w))return w.slice(0,-3)+"y";
    if(w.length>3&&/s$/.test(w)&&!/ss$/.test(w))return w.slice(0,-1);return w;}
  var STOP=" a an and are as at be by for from in is it of on or the to with any all under ";
  function words(q){return (q.toLowerCase().match(/[a-z][a-z']{1,}/g)||[]).filter(function(w){
    return STOP.indexOf(" "+w+" ")<0;}).map(stem);}
  function has(text,w){return (text.toLowerCase().match(/[a-z][a-z']+/g)||[]).some(function(x){
    return stem(x)===w||(w.length>=4&&x.indexOf(w)===0);});}
  var CITE=/^\\s*(?:rsa\\s*)?(?:chapter\\s*)?(\\d{1,3}(?:-[a-z]{1,2})?)(?::\\s*([0-9a-z.\\-]+))?\\s*$/i;
  function label(a,ch,hd){var c=chOf(a),info=ch[c]||[];
    if(a.indexOf(":")<0)return "Chapter "+c+": "+(info[0]||"");
    var h=(hd.filter(function(x){return x[0]===a;})[0]||[])[1]||"";return h;}
  function show(list,note){
    dir.hidden=count.hidden=!!(list||note);
    out.innerHTML=!list&&!note?"":(note?'<p class="rs-note">'+esc(note)+'</p>':'')+(list&&list.length?'<ol class="rs-hits">'
      +list.slice(0,60).map(function(r){var sec=r[0].indexOf(":")>=0;
        return '<li><a href="'+link(r[0])+'"'+(sec?' data-sec="'+esc(r[0])+'"':'')+'>'
          +(sec?'<b>RSA '+esc(r[0])+'</b> ':'')+esc(r[1]||"")+'</a>'
          +(sec&&CH&&CH[chOf(r[0])]?' <span class="rs-in">in Chapter '+esc(chOf(r[0]))+'</span>':'')+'</li>';}).join("")+'</ol>':'');
  }
  function run(){
    var q=box.value.trim();
    if(!q){show(null,"");return;}
    var m=CITE.exec(q);
    Promise.all([chapters(),heads(),WD?WD:get("laws/words.json").then(function(d){return WD=d||{words:{}};})]).then(function(r){
      var ch=r[0],hd=r[1],wd=r[2];
      if(m&&ch[m[1].toUpperCase()]){
        var c=m[1].toUpperCase(),a=c+(m[2]?":"+m[2]:"");
        show([[a,label(a,ch,hd)]].concat(m[2]?[[c,label(c,ch,hd)]]:[]),"By number:");
        if(m[2]&&!narrow())open(a);return;
      }
      var ws=words(q);if(!ws.length){show([],"");return;}
      var hit={},name={};
      function add(a,lab,w,pts){var h=hit[a]||(hit[a]={w:{},s:0});h.w[w]=1;h.s+=pts;if(lab)name[a]=lab;}
      Object.keys(ch).forEach(function(c){var known=(ch[c][4]||[]).join(" "),lab="Chapter "+c+": "+ch[c][0];
        ws.forEach(function(w){if(has(ch[c][0]||"",w))add(c,lab,w,3);
          else if(known&&has(known,w))add(c,lab+" (the "+ch[c][4][0]+")",w,3);});});
      hd.forEach(function(x){ws.forEach(function(w){if(has(x[1],w))add(x[0],x[1],w,2);});});
      var hs={};hd.forEach(function(x){hs[x[0]]=x[1];});
      ws.forEach(function(w){var i=0;(wd.words[w]||[]).forEach(function(g){i+=g;var a=(hd[i]||[])[0];
        if(a)add(a,hs[a],w,1);});});
      var list=Object.keys(hit).map(function(a){return [a,name[a]||hs[a]||"",Object.keys(hit[a].w).length,hit[a].s];})
        .filter(function(x){return x[2]>=Math.min(ws.length,Math.max(1,ws.length-1));})
        .sort(function(x,y){var cx=x[0].indexOf(":")<0,cy=y[0].indexOf(":")<0;
          return y[2]-x[2]||(cy-cx)||y[3]-x[3]||(x[0]<y[0]?-1:1);});
      var all=list.filter(function(x){return x[2]===ws.length;}).length;
      show(list,list.length?(all===list.length?"Matching every word:":all+" match every word; then the closest:")
        :"Nothing found. Try fewer words, or a chapter number such as 91-A.");
    });
  }
  // The filters fold on a narrow screen, where they would fill the first one.
  if(narrow())document.getElementById("lwfbox").open=false;
  var t=null;box.addEventListener("input",function(){clearTimeout(t);t=setTimeout(run,180);});
  // The search's files are fetched once the box is chosen, not on the first
  // letter typed, so the first answer does not wait for them.
  box.addEventListener("focus",function(){chapters();heads();if(!WD)WD=get("laws/words.json").then(function(d){return WD=d||{words:{}};});},{once:true});
  document.getElementById("rsform").addEventListener("submit",function(e){e.preventDefault();run();});
  // A title linked from a chapter's breadcrumb (/laws#t-VI) opens.
  var h=location.hash.match(/^#t-(.+)$/);if(h){var d=document.getElementById("t-"+decodeURIComponent(h[1]));if(d){d.open=true;}}
  filter();
})();
</script>"""


# WHEN THE TABLE WAS TAKEN: db/_manifest.json's "fetched" for NH_RSA, which
# the weekly refreshes (nightly.STATUTE_VIEWS). Set by main(); "" where the
# manifest does not say, and then the pages say nothing of it.
TABLE_TAKEN = ""


def taken_on(db):
    """'September 8, 2026' from <db>/_manifest.json's NH_RSA entry, or ""."""
    try:
        got = json.loads((Path(db) / "_manifest.json").read_text(encoding="utf-8"))["NH_RSA"]["fetched"]
        d = datetime.date.fromisoformat(str(got)[:10])
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    return C.date_words(d, "full")


def as_of(latest):
    """The lead's sentences on how current the text is.

    IN THE PERSON'S WORDS (approved 17 October 2026): "Includes changes
    through 2025; 2026 laws not yet included." It said the table held the
    text "through the laws of 2025", which left a reader to work out that a
    law of 2026 was not in it."""
    taken = (f" Taken from the General Court's database on {E(TABLE_TAKEN)}."
             if TABLE_TAKEN else "")
    y = str(latest or "")
    if not y.isdigit():
        return taken.strip()
    return f"Includes changes through {E(y)}; {int(y) + 1} laws not yet included.{taken}"


def landing_page(tmpl, table, data, base, topics, pending, con=None):
    """THE LAWS AS THE BILL SEARCH IS LAID OUT (the person, 11 October 2026):
    filters at the side, the directory of titles and chapters in the middle
    -- each title saying which chapters it holds before it is opened, as the
    General Court's own table of contents does -- and a section's text on the
    right when one is chosen, with the way to its own page.

    AND THE CONSTITUTION ON A TAB OF ITS OWN (the person, 17 October 2026),
    from collected/constitution.json, which `con` is when a check hands it
    in. The statutes are the first tab and read as they did, their lead at
    the top of their panel; a disk without the file builds the page as it
    was, with no tabs."""
    path = "/laws"
    title = "New Hampshire laws"
    con = PC.load() if con is None else con
    p = S.page(tmpl, path=path, base=base,
               title=S.title_of("New Hampshire Laws", "every chapter of the RSA"),
               jsonld=LD.listing("New Hampshire Revised Statutes Annotated",
                                 "Every chapter of the New Hampshire Revised Statutes Annotated, "
                                 "with the bills that changed each section and the bills that would.",
                                 base, "/laws"),
               og_title=title, description="Every chapter of the New Hampshire Revised Statutes "
               "Annotated: browse by title or topic, search by number or words, with the bills that "
               "changed each section and the bills that would."
               + (" And the state Constitution, article by article." if con else ""),
               og_image="og-learn.png", og_alt=OG_ALT,
               globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the laws",
               sr_title="", nav_current="laws.html", cite=False)
    latest = data.get("asof", {}).get("laws_through") or ""
    rsa_lead = ('The Revised Statutes '
                'Annotated (RSA), chapter by chapter, as the General Court\'s table holds them: '
                f'each section with the bills that changed it and the bills that would. {as_of(latest)}')
    head_lead = ("The state Constitution, and the statutes the General Court passes under it, the "
                 "Revised Statutes Annotated (RSA)." if con else rsa_lead)
    head = (f'<header class="l-head"><h1>{E(title)}</h1><p class="l-lead">{head_lead}</p>'
            + S.cite_block(path, title, base, S.BUILT) + "</header>")
    groups = collections.OrderedDict()
    for ch in sorted(table.chapters, key=rsa.chap_key):
        info = table.chapters[ch]
        groups.setdefault((info["title_no"], info["title"]), []).append(ch)
    tcount = collections.Counter(t for ts in topics.values() for t in ts)
    n_rep = sum(1 for c in table.chapters.values() if c["repealed"])
    n_pend = sum(1 for c in table.chapters if pending.get(c))
    blocks, title_opts = [], []
    for (tno, tname), chs in groups.items():
        tl, tn = title_label(tno, tname)
        live = [c for c in chs if not table.chapters[c]["repealed"]]
        span = f"Chapters {chs[0]} to {chs[-1]}" if len(chs) > 1 else f"Chapter {chs[0]}"
        lis = []
        for c in chs:
            info = table.chapters[c]
            label = chapter_label(c, info["name"])
            pend = len(pending.get(c, []))
            badges = ((f'<span class="lw-badge lw-rep">{"Moved" if moved_to(info.get("note")) else "Repealed"}'
                       '</span>' if info["repealed"] else "")
                      + (f'<span class="lw-badge lw-pend">{pend} pending</span>' if pend else ""))
            # THE LEAST A CHAPTER NEEDS UNTIL IT IS OPENED (the polish of 12
            # October 2026): its sections, its label and its title's name are
            # drawn by LANDING_JS from what is here when it opens. Written
            # into every one of 1,786 rows they were about half the page.
            #
            # BUT THE WAY TO ITS OWN PAGE IS IN THE HTML (the sitemap audit,
            # 16 October 2026). It was drawn by the script too, only once a
            # reader opened the row, and a crawler opens none: /laws linked
            # no chapter at all, and 315 chapter pages had no link from
            # anywhere on the site. So each row carries one plain link,
            # "RSA 3-A", beside its summary and not inside it: a link inside
            # a <summary> would make the chapter's name a second control in
            # the one that opens the row, and a click on the name would leave
            # the page instead of listing the sections, which is what the
            # row is for. app.css sets it at the row's right, level with the
            # name, on a phone as on a desktop.
            topic_attr = f' data-topics="{E("|".join(topics.get(c, [])))}"' if topics.get(c) else ""
            lis.append(
                f'<li class="lw-ch" data-ch="{E(c)}" data-title="{E(tno)}"'
                + (' data-rep="1"' if info["repealed"] else "") + (f' data-pend="{pend}"' if pend else "")
                + f'{topic_attr}><details class="lw-chd"><summary><span class="lw-chn">Chapter {E(c)}:</span> '
                f'<span class="lw-chname">{E(nice(info["name"]))}</span>{badges}</summary></details>'
                f'<a class="lw-go" href="{E(chapter_path(c))}">RSA {E(c)}</a></li>')
        blocks.append(
            f'<details class="lw-title" id="t-{E(tno)}"><summary><span class="lw-tno">{E(tl)}</span>'
            f'<span class="lw-tname">{E(tn)}</span><span class="lw-tspan">{E(span)} &middot; '
            f'<span class="lw-tn" data-all="{len(chs)} chapters">{len(chs)} chapters</span></span>'
            # A title's first three chapter names stood under its count until
            # 14 October 2026; the person asked for the count alone.
            f'</summary><ul class="lw-chs">{"".join(lis)}</ul></details>')
        title_opts.append(f'<li><label><input type="checkbox" name="ti" value="{E(tno)}"> '
                          f'<span><b>{E(tl)}</b> {E(tn)}</span></label></li>')
    topic_opts = "".join(f'<li><label><input type="checkbox" name="tp" value="{E(t)}"> <span>{E(t)}</span>'
                         f'<span class="lw-n">{n}</span></label></li>'
                         for t, n in sorted(tcount.items(), key=lambda x: (-x[1], x[0])))
    n_all = len(table.chapters)
    side = (
        '<aside class="lw-side" aria-label="Search and filters">'
        '<form id="rsform" class="rs-search" role="search"><label for="rsq">Search the laws</label>'
        '<input id="rsq" type="search" autocomplete="off" placeholder="91-A:4, or right to know"></form>'
        '<details class="lw-fbox" id="lwfbox" open><summary>Filters</summary>'
        '<div class="lw-f"><h2>Status</h2><ul>'
        f'<li><label><input type="checkbox" name="st" value="in"> <span>In force</span><span class="lw-n">{n_all - n_rep:,}</span></label></li>'
        f'<li><label><input type="checkbox" name="st" value="pend"> <span>Bills pending this term</span><span class="lw-n">{n_pend:,}</span></label></li>'
        f'<li><label><input type="checkbox" name="st" value="rep"> <span>Repealed or moved</span><span class="lw-n">{n_rep:,}</span></label></li>'
        '</ul></div>'
        f'<div class="lw-f"><h2>Topic</h2><p class="lw-fnote">From the bills that changed each chapter.</p>'
        f'<ul class="lw-scroll">{topic_opts}</ul></div>'
        f'<div class="lw-f"><h2>Title</h2><ul class="lw-scroll">{"".join(title_opts)}</ul></div>'
        '<button type="button" class="lw-clear" id="lwclear" hidden>Clear filters</button></details></aside>')
    middle = (f'<section class="lw-dir" aria-label="The laws by title"><p class="lw-count" id="lwcount" '
              f'data-all="{n_all:,} chapters in {len(groups)} titles">{n_all:,} chapters in {len(groups)} titles</p>'
              '<div id="rsout" aria-live="polite"></div>'
              f'<div id="lwdir">{"".join(blocks)}</div></section>')
    reader = ('<aside class="lw-read" id="lwread" aria-label="The section chosen" aria-live="polite">'
              '<p class="lw-empty">Choose a chapter, then a section, to read it here.</p></aside>')
    art = f'<div class="lw" id="lw">{side}{middle}{reader}</div>'
    if con:
        # The constitution's sidebar is a chapter page's, so the chapter
        # page's script marks the article being read in it.
        art = CT.tabbed(art, rsa_lead, con) + CHAPTER_JS
    return p.replace('<div id="results"></div>',
                     f'<div id="results"><div class="l-page rs-page rs-landing">{head}{art}</div>{LANDING_JS}</div>', 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--only", nargs="*", help="build these chapters alone (for a look), not the set")
    # The fixture's own table, which preflight's chain builds the Laws pages
    # from: the nav links laws.html from every page, so a fixture without
    # them is a site of broken links.
    ap.add_argument("--db", help="the folder holding NH_RSA.psv and _columns.json (default: db/)")
    a = ap.parse_args()
    site = Path(a.site)
    table = rsa.load(Path(a.db) / "NH_RSA.psv", Path(a.db) / "_columns.json") if a.db else rsa.load()
    global TABLE_TAKEN
    TABLE_TAKEN = taken_on(a.db or rsa.TABLE.parent)
    cit = Path("rsa_citations.json")
    if table is None or not cit.is_file():
        print("build_rsa: no statute table or rsa_citations.json here; no statute pages written")
        return 0
    data = json.loads(cit.read_text(encoding="utf-8"))
    current = term_of_year(build_date.today().year)
    bills = Bills(site, current)
    tmpl = S.template(site)
    out = site / "laws"
    out.mkdir(parents=True, exist_ok=True)
    chs = [c.upper() for c in a.only] if a.only else sorted(table.chapters, key=rsa.chap_key)
    for ch in chs:
        chapter_file(out, ch).parent.mkdir(parents=True, exist_ok=True)
        chapter_file(out, ch).write_text(
            S.clean_links(chapter_page(tmpl, table, data, bills, ch, a.base)), encoding="utf-8")
    stale = out / "404.html"       # an earlier build's RSA 404, before chapter_file
    if not a.only and stale.is_file():
        stale.unlink()
    topics, pending = chapter_topics(data, bills), chapter_pending(data, bills)
    (site / "laws.html").write_text(S.clean_links(landing_page(tmpl, table, data, a.base, topics, pending)), encoding="utf-8")
    chapters, headings, words = build_indexes(table, data, topics, pending)
    for name, obj in (("chapters.json", chapters), ("headings.json", headings), ("words.json", words)):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                                encoding="utf-8")
    sizes = {n: (out / n).stat().st_size for n in ("chapters.json", "headings.json", "words.json")}
    print(f"build_rsa: {len(topics):,} of {len(table.chapters):,} chapters with a topic from their bills, "
          f"{len(pending):,} with a bill pending")
    print(f"build_rsa: {len(chs):,} chapter pages and the landing page; search files "
          + ", ".join(f"{n} {s / 1e6:.1f} MB" for n, s in sizes.items()))
    # SAID EITHER WAY: a landing page without its Constitution tab is a page
    # that lost a part, and must not pass in silence.
    con = PC.load()
    print("build_rsa: " + (f"the Constitution tab, {sum(con['counts'].values())} articles"
                           if con else f"NO Constitution tab: {PC.OUT.name} is not on this disk"))
    if not a.only:
        S.sitemap_merge(site, a.base, [a.base + "/laws"] + [a.base + chapter_path(c) for c in chs],
                        owns="/laws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
