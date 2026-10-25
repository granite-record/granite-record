#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.76
"""
Write a real address for every bill, and the sitemap that points at them.

    python3 src/pages/build_bill_pages.py --site site

WHAT THESE PAGES ARE

/bill/2026/hb1094.html is this site's search page with one bill open. Not a
second rendering of it -- the same one, from the same app.js, drawing the same
site/bills/2026/HB1094.json.

It was once a second rendering: 900 lines of Python emitting a complete
no-JavaScript page per bill. That is why a reader who arrived from a
legislator page found a bill laid out differently from the one they had been
reading a moment before, and why a fix to one view never reached the other.
Two renderers of the same record disagree; it is only a question of when.

So this file no longer knows what a roll call looks like. It knows what a bill
is CALLED, what its address is, and how to hand app.js the one fact it cannot
work out for itself -- which bill this page is.

WHY IT READS bills.html RATHER THAN HOLDING ITS OWN COPY

app.js binds to #q, #qgo, #year, #sort, #facets, #results and #count when it
loads. A page missing any of them is a blank screen with no error. Keeping a
second copy of that markup here would mean an edit to bills.html silently
breaking 4,230 pages, which is the same class of failure as the two renderers
this replaces -- so the template IS bills.html, read at build time, and the
substitutions below assert that what they are replacing was actually there.

WHAT IS GIVEN UP, SAID PLAINLY

These pages needed no JavaScript. They do now. That was a deliberate trade: a
duplicate renderer is a worse cost than a JavaScript dependency, and the
machine-readable route for anyone who wants the record without running a
browser is site/bills/<year>/<id>.json, which is the same file the page reads.
The <noscript> block says so and links the General Court directly.

Writes site/bill/<year>/<id>.html, plus sitemap.xml and robots.txt.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import html
import json
import re

import build_date
import build_rsa as BR
from components import clock
import rsa
import shell as S
import site_read as SR
import structured as LD

E = html.escape

# "(New Title)" is the General Court's marker for a subject changed by
# amendment. It belongs on the page, where the change is the story, and not at
# the front of a search result, where it is the first thing read and says
# nothing about the bill.
NEW_TITLE = re.compile(r"^\s*\((?:New Title|Second New Title)\)\s*", re.I)



# THE CHAPTERS /laws HAS A PAGE FOR: build_rsa.py writes one for every
# chapter of the statute table, and only where the table is on this disk, so
# the same table says which addresses will resolve. None where it is absent.
_LAWS = []


def law_href(cite):
    """/laws/91-a#s4 for "RSA 91-A:4" where /laws has that chapter, else ""."""
    if not _LAWS:
        t = rsa.load()
        _LAWS.append({k.upper() for k in t.chapters} if t else set())
    m = re.search(r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)(?::(\S+?))?(?=[\s,;.)]|$)", cite, re.I)
    if not m or m.group(1).upper() not in _LAWS[0]:
        return ""
    # The chapter's address as build_rsa writes it, which for RSA 404 ends in
    # the slash the host serves it at (build_rsa.chapter_path, 16 October 2026).
    return BR.chapter_path(m.group(1).upper()) + (f"#s{m.group(2)}" if m.group(2) else "")

def clean_title(s):
    return NEW_TITLE.sub("", s or "").strip()


def describe(b):
    """The sentence a search engine shows under the link.

    Built to fit rather than sliced to fit: the status and what the page holds
    are what make one bill's description different from another's, and the old
    version could push them past where they would be shown.
    """
    n = b.get("n") or b["id"]
    yr = str(b.get("year") or "")
    lead = f"{n} ({yr})" if yr else n
    st = status_shown(b).strip().rstrip(".")
    tail = f" {st}." if st else ""
    subject = clean_title(b.get("title") or "")
    room = S.DESC_ROOM - len(lead) - len(tail) - 2
    subject = S.clip(subject, max(20, room))
    return f"{lead}: {subject}{tail}".strip()


def _day(iso):
    """A docket date in words, or the text as it came where it is not one."""
    try:
        return S.date_words(str(iso)[:10], "full")
    except (ValueError, TypeError):
        return str(iso or "")


CHAMBER = {"H": "House", "S": "Senate"}


def status_shown(b):
    """A bill's status as its page says it: "Died when the session ended"
    where the chip says Died and the record keeps the stage the bill stood at
    -- "In committee", "Committee report filed" -- as app.js's statusShown
    does (the audit of 25 October 2026, S4: HB 520 of 2017 read "Died" over
    "Status: In committee"). The record itself is unchanged."""
    s = str(b.get("status") or "")
    if b.get("chip") == "Died" and s.lower() in ("in committee", "committee report filed"):
        return "Died when the session ended"
    return s


def static_record(b, d, data_url=None):
    """THE RECORD IN THE PAGE ITSELF, for a reader with no JavaScript.

    The SEO review of 12 October 2026: everything on a bill's page was drawn
    by app.js from the gr-data JSON, so a reader that does not run scripts --
    most AI crawlers, a text browser, a reader with scripts off -- saw the
    bill's name, the citation box and a <noscript> line saying the page needs
    JavaScript. No sponsor, no vote, no hearing, no history.

    So the page carries the record as plain HTML, from the same record the
    script draws: what it is, where it stands, the story, the sponsors (each
    to their page), hearings, roll calls, the docket, the laws it would
    change, related bills and the General Court's own documents. html.js --
    set in the head before the first paint, by the same inline script that
    sets the theme -- hides it, and app.js draws the page as before; a reader
    without scripts reads this instead. Nothing here is not also on the page
    the script draws.
    """
    n = b.get("n") or b["id"]
    yr = str(b.get("year") or "")
    out = ['<div class="static-rec" id="static-rec">',
           f'<p class="sx-name">{E(n)}{f" ({E(yr)})" if yr else ""}</p>']
    title = b.get("title") or d.get("title") or ""
    if title:
        out.append(f'<p class="sx-title" translate="no">{E(clean_title(title))}</p>')
    facts = []
    if b.get("status"):
        facts.append(f"<b>Status:</b> {E(status_shown(b))}")
    if b.get("term"):
        facts.append(f"<b>Term:</b> {E(b['term'])}")
    for ch, key in (("House", "house_committee"), ("Senate", "senate_committee")):
        if d.get(key):
            facts.append(f"<b>{ch} committee:</b> {E(d[key])}")
    if d.get("subject"):
        facts.append(f"<b>Subject:</b> {E(d['subject'])}")
    if d.get("chapter"):
        facts.append(f"<b>Chapter law:</b> {E(str(d['chapter']))}")
    if facts:
        out.append('<ul class="sx-facts">' + "".join(f"<li>{x}</li>" for x in facts) + "</ul>")
    if d.get("narrative"):
        out.append(f'<h2>The Story</h2><p>{E(d["narrative"])}</p>')
    sp = d.get("sponsors") or []
    if sp:
        def who(s):
            name = s.get("display_full") or s.get("label") or s.get("name") or ""
            link = (f'<a href="legislator/{E(s["slug"])}">{E(name)}</a>'
                    if s.get("slug") else E(name))
            return link + (" (prime sponsor)" if s.get("prime") else "")
        out.append("<h2>Sponsors</h2><ul>"
                   + "".join(f"<li>{who(s)}</li>" for s in sp) + "</ul>")
    st = [s for s in d.get("stations") or [] if s.get("when")]
    if st:
        out.append("<h2>Hearings and Sessions</h2><ul>" + "".join(
            # "8:30 AM", not "08:30" (17 October 2026), as every other
            # time on the site is printed (components.clock).
            "<li>" + E(_day(s["when"])) + (f", {E(clock(s['time']))}" if s.get("time") else "")
            + ": " + E(s.get("what") or "")
            + (", " + E(f"{CHAMBER.get(s.get('body'), '')} {s['committee']}".strip())
               if s.get("committee") else "")
            + (f", {E(s['venue'])}" if s.get("venue") else "") + "</li>" for s in st) + "</ul>")
    rc = d.get("rollcalls") or []
    if rc:
        def vote(r):
            how = (f"yeas {r['yeas']}, nays {r['nays']}" if r.get("yeas") is not None
                   and r.get("nays") is not None else (r.get("vote_kind_label") or ""))
            res = {True: "passed", False: "failed"}.get(r.get("passed"), "")
            return (f"{E(_day(r.get('date')))}, {E(CHAMBER.get(r.get('body'), ''))}: "
                    f"{E(r.get('question') or '')}" + (f" &mdash; {E(how)}" if how else "")
                    + (f", {res}" if res else ""))
        out.append("<h2>Votes</h2><ul>" + "".join(f"<li>{vote(r)}</li>" for r in rc) + "</ul>")
    ev = [e for e in d.get("events") or [] if not e.get("cancelled")]
    if ev:
        # In the docket's own words, dates and all, as the page app.js draws
        # gives them: class "sx-docket" is how the date check knows a quotation.
        out.append('<h2>The Docket</h2><div class="sx-docket" translate="no"><ul>' + "".join(
            f"<li>{E(_day(e.get('date')))}: {E(e.get('text') or '')}</li>" for e in ev)
            + "</ul></div>")
    # The sections the bill amends, each to the site's own page for its
    # chapter at /laws, as the app's Laws tab links them (14 October 2026),
    # and to the General Court's page only where this build has no page for
    # that chapter: a chapter the statute table does not hold, or a build
    # with no statute table at all.
    am = d.get("amends") or {}
    # AND A CACR'S ARTICLES OF THE CONSTITUTION (17 October 2026), as the
    # app's summary says them (app.js constLine), each to its article on the
    # Laws page's Constitution tab.
    con = [x for x in d.get("constitution") or [] if x.get("href") and x.get("label")]
    if am or con:
        def law(r, u):
            h = law_href(r)
            return (f'<li><a href="{E(h)}">{E(r)}</a></li>' if h
                    else f'<li><a href="{E(u)}" rel="noopener">{E(r)}</a></li>')

        def article(x):
            a = f'<a href="{E(x["href"])}">{E(x["label"])}</a>'
            if x.get("verb") == "insert_after":
                return f"<li>A new article of the state Constitution, after {a}</li>"
            if x.get("verb") == "reenact_part":
                return f"<li>{a} of the state Constitution, rewritten</li>"
            return f"<li>{a} of the state Constitution</li>"
        out.append("<h2>Laws It Would Change</h2><ul>" + "".join(
            law(r, u) for r, u in am.items() if u) + "".join(article(x) for x in con) + "</ul>")
    rel = d.get("related") or []
    if rel:
        out.append("<h2>Related Bills</h2><ul>" + "".join(
            f'<li><a href="bill/{E(str(r.get("y")))}/{E(str(r.get("o", "")).split("/")[-1].lower())}">'
            f'{E(r.get("n") or "")} ({E(str(r.get("y")))})</a>'
            + (f": {E(clean_title(r['t']))}" if r.get("t") else "") + "</li>"
            for r in rel if r.get("o") and r.get("y")) + "</ul>")
    docs = [x for x in d.get("documents") or [] if x.get("url")]
    links = [f'<a href="{E(x["url"])}" rel="noopener">{E(x.get("label") or "Document")}</a>'
             for x in docs]
    if data_url:
        links.append(f'<a href="{E(data_url)}">This page&rsquo;s data as JSON</a>')
    if links:
        out.append("<h2>From the General Court</h2><ul>"
                   + "".join(f"<li>{x}</li>" for x in links) + "</ul>")
    out.append("</div>")
    return "".join(out)


# HOW BIG A RECORD MAY TRAVEL INSIDE ITS PAGE.
#
# Measured across all 33,683 bills: the median record is 1.3 KB, the 90th
# percentile 9.5 KB, the 99th 56 KB -- and the largest is HB2 at 2,059 KB,
# almost all of it individual roll call ballots. Roll calls are 34% of every
# byte on this site.
#
# At 100 KB, 98 bills keep a file of their own and 33,585 do not: 99.7% of the
# saving, and no page larger than about 104 KB. Inlining the other 98 would
# mean asking somebody to download two megabytes to read a bill.
INLINE_CAP = 100 * 1024


def shell(t, b, d, base, raw=None, data_url=None, current_term="", modified=None):
    """One bill's page: bills.html, told which bill it is. `modified` is the
    day it last moved (lastmod), for its structured data."""
    bid = b["id"]
    yr = str(b.get("year") or "")
    n = b.get("n") or bid
    title = b.get("title") or ""
    path = f"/bill/{yr}/{bid.lower()}.html"
    # A per-bill feed exists only where there is a docket to report AND the
    # bill is still moving: the sitting term, not concluded (shell.still_moving,
    # which build_feeds uses too). Closed terms stopped getting feeds when the
    # 1989-2016 histories arrived; concluded bills of the sitting term stopped
    # too, because only a bill still moving needs following. A page must not
    # advertise a feed that is not there.
    feed = (f'<link rel="alternate" type="application/rss+xml" '
            f'title="{E(n)} updates" href="/feed/bill/{yr}/{bid.lower()}.xml">'
            if d.get("events") and S.still_moving(b, current_term) else "")
    return S.page(
        t, path=path, base=base,
        jsonld=LD.bill(b, d, base, S.canon(path), modified=modified),
        # THE YEAR IS PART OF THE NAME. Bill numbers repeat every two
        # years, so 192 pages shared a title with another term's bill --
        # fourteen of them "HB 25 — making appropriations for capital
        # improvements" — and a search engine has no way to tell them apart.
        # The old title also cut the subject at ninety characters flat,
        # mid-word.
        title=S.title_of(f"{n} ({yr})" if yr else n, clean_title(title)),
        # WHAT THE BILL IS ABOUT, in the card a shared link unfurls into. It
        # read "HB 1442-FN -- New Hampshire General Court": nothing about the
        # bill, and a card that looked like the General Court's own page.
        og_title=S.clip(f"{n} ({yr}): {clean_title(title)}" if yr and title else n, 110),
        # THE SAME NAME, UNCLIPPED, FOR THE CITATION. og_title above is cut to
        # 110 characters because a social card has a width; a citation has
        # none, and a bill's full title is the one thing in it that must not
        # be shortened. 11,558 of these exceed that 110 and would otherwise
        # still be quoted with an ellipsis inside somebody's bibliography.
        cite_title=(f"{n} ({yr}): {clean_title(title)}" if yr and title else n),
        og_image="og-bill.png", og_alt="Granite Record: bills, votes and hearings",
        description=describe(b), alternate=feed,
        globals={"GR_BILL": f"{yr}/{bid}", "GR_STANDALONE": True},
        data_json=raw, data_url=data_url,
        # The record itself is in the page now (static_record), so the
        # <noscript> apology that stood in for it is gone.
        static=static_record(b, d, data_url),
        skip_label="Skip to this bill",
        # The page's heading for a screen reader. Every bill page kept the
        # search page's own hidden "New Hampshire bills", so 33,683 pages
        # announced themselves as the search.
        sr_title=(f"{n} ({yr}): {clean_title(title)}" if yr
                  else f"{n}: {clean_title(title)}"))


def lastmod(b, built, d=None):
    """One bill's <lastmod>, which may not be later than the day of the build,
    or None where the record gives no day it can stand behind.

    last_action is the latest date in the bill's docket, and a docket holds
    meetings that have not happened yet. So 45 of the 33,690 entries were
    dated after the day the file was written -- 27 of them 2026-09-30, the
    furthest 2026-10-13. All 45 are of the current term and 44 of them were
    referred for interim study, with the next work session already on the
    calendar; the forty-fifth was vetoed and had its override fail, and its
    docket carries a later date all the same. HB 561 is the plainest case:
    last_action 2026-09-29, a fortnight out, because that is when the
    committee next sits.

    A sitemap's lastmod means the day the page was last modified. A date in
    the future is therefore a claim about a day that has not happened, and it
    is not a harmless one: it is the same failure as stamping every entry with
    the build date, which this field was changed to avoid -- a crawler that
    finds one lastmod it cannot believe has no reason to believe the rest.

    NOT THE BUILD'S DAY EITHER (the sitemap audit, 16 October 2026). The
    clamp took the build date, so the 17 bills of the sitting term with a
    meeting still to come were re-dated every night until the meeting had
    passed, whether or not anything on the page had moved, and the three
    bills whose docket carries no date at all (2026 HR 48, 2019 HR 1, 1999
    SR 5) took it every night as well. Nobody can believe a date that moves
    on its own. So a bill with a meeting to come is dated by the latest day
    in its docket that has already happened (`d`, the bill's own record, the
    docket the page shows), and a bill with no such day carries no lastmod at
    all: the field is optional, and an entry without one is still listed and
    crawled. Every bill whose last action is already past keeps exactly the
    date it had. An ISO date sorts in the order it runs, so <= compares days.
    """
    moved = str(b.get("last_action") or "")[:10]
    if not ISO_DAY.fullmatch(moved):
        return None
    if moved <= built:
        return moved
    past = [str(e.get("date") or "")[:10] for e in (d or {}).get("events") or []]
    past = [x for x in past if ISO_DAY.fullmatch(x) and x <= built]
    return max(past) if past else None


ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

# STANDING PAGES WITH NO DATE (the sitemap audit, 16 October 2026). Each
# standing page was dated by the build, which is true of the home page and of
# /data -- the day's activity and the downloads' own date are rebuilt every
# night -- and not of About, the bill search's frame or the officials' list,
# which read the same from one night to the next while their date moved. A
# date nobody can believe teaches a crawler to believe none of them, so these
# three carry none, as the sitemap's other undated pages do.
UNDATED_STANDING = ("about.html", "bills.html", "officials.html")


# The record as it was written into a page, for a run that happens after the
# file it came from was removed.
EMBEDDED = re.compile(
    r'<script type="application/json" id="gr-data">(.*?)</script>', re.S)


def embedded(page):
    """The record inside a built page, or None."""
    if not page.exists():
        return None
    m = EMBEDDED.search(page.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return None
    # The one escape shell.py applies on the way in.
    return m.group(1).replace("<" + chr(92) + "/", "</")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site = Path(a.site)
    # Every bill's row, from the term files the pages read (site_read).
    idx = SR.bill_index_or_stop(site, "build_bill_pages.py")
    # THE NEWEST TERM FIRST, AS meta.json NAMES THE TERMS, and each term's
    # bills in the order the index gives them. The sitemap is written in this
    # order, and it used to be whatever order index.json happened to hold:
    # data/bills.json's, which is 2025-2026, 2023-2024 and then 1989-1990
    # upward -- the order build_data met the dockets in, which nothing chose.
    # Stated here, the order of the TERMS is the same however the rows are
    # read. Within a term it is not stated: a term's bills come in its
    # idx/<term>.json's order, which the loader keeps, and the sort is stable.
    idx = sorted(idx, key=lambda b: str(b.get("term") or ""), reverse=True)
    out = site / "bill"
    out.mkdir(parents=True, exist_ok=True)
    generated = build_date.today().isoformat()
    t = S.template(site)

    # The year is part of the path because bill numbers are only unique within
    # a term. There really is an HB 84 in several of them, and /bill/hb84.html
    # could only ever point at one.
    # The term still sitting: the only one whose bills get a feed of their own.
    current_term = max((b.get("term") or "" for b in idx), default="")
    written, missing, noyear = 0, 0, 0
    inlined, kept = 0, 0
    urls = []
    for b in idx:
        yr = str(b.get("year") or "")
        if not yr:
            noyear += 1
            continue
        # The detail file lives under its filing year too, for the reason the
        # page does: a bill number is unique within a term and not beyond it.
        f = site / "bills" / yr / f"{b['id']}.json"
        page = out / yr / f"{b['id'].lower()}.html"
        # IDEMPOTENT, because the first run takes the file away. A record
        # small enough to travel inside its page leaves no file behind, so a
        # second run of this script alone found 33,585 bills with "no detail
        # file", skipped them, and rewrote sitemap.xml with the 104 it had
        # left -- a writer run on a subset destroying the rest, which is the
        # failure this project keeps meeting.
        raw = f.read_text(encoding="utf-8") if f.exists() else embedded(page)
        if raw is None:
            missing += 1
            continue
        d = json.loads(raw)
        small = len(raw.encode("utf-8")) <= INLINE_CAP
        (out / yr).mkdir(parents=True, exist_ok=True)
        moved = lastmod(b, generated, d)
        html = shell(t, b, d, a.base,
                     raw=raw if small else None,
                     data_url=None if small else f"/bills/{yr}/{b['id']}.json",
                     current_term=current_term, modified=moved)
        page.write_text(S.clean_links(html), encoding="utf-8")
        # THE PAGE IS WRITTEN BEFORE THE FILE IS REMOVED, and only the one
        # file whose contents are now inside it. A run that stops half way
        # leaves every bill either inlined or with its file, never neither.
        if small:
            f.unlink(missing_ok=True)
            inlined += 1
        else:
            kept += 1
        # lastmod is the day the bill last moved, not the day of the build. Every
        # one of 34,000 entries carried the build date, which tells a search
        # engine every page changed every night -- and it learns to ignore the
        # field, and to recrawl nothing sooner for it. Never later than a day
        # that has happened, and none where there is no such day: lastmod().
        urls.append((a.base + S.canon(f"/bill/{yr}/{b['id'].lower()}.html"), moved))
        written += 1
        if written % 1000 == 0:
            print(f"  {written:,}...", flush=True)

    print(f"  {inlined:,} records travel inside their page; "
          f"{kept:,} are larger than {INLINE_CAP // 1024} KB and keep a file "
          "of their own")

    for p in ("index.html", "bills.html", "officials.html",
              # data.html was added to the nav and not here, so the downloads
              # page was on every header and in no sitemap -- the same shape
              # of defect as the nav tuple in build_pages.py, one level down.
              "committees.html", "resources.html", "data.html", "about.html"):
        # ALWAYS, NOT ONLY IF THE FILE IS THERE YET. committees.html, resources.html
        # and data.html are written by steps that run after this one, so a
        # build into an empty site/ -- every night on GitHub's machine --
        # dropped all three (found 25 September 2026). Every one is built on
        # every run, and check_site fails the publish if a sitemap address
        # has no file, so a page that stops being built is caught loudly
        # rather than left out quietly.
        urls.append((a.base + S.canon("/" + p), None if p in UNDATED_STANDING else generated))
    # A PAGE IN ANOTHER LANGUAGE (i18n.py), once that language is offered to
    # everyone: until then it is unlisted, linked from nowhere and asking not
    # to be indexed, and a sitemap naming it would say otherwise.
    import i18n
    for lang in i18n.LANGS:
        if lang != i18n.DEFAULT and i18n.offered(lang):
            for p in i18n.PAGES.get(lang, ()):
                urls.append((a.base + S.canon(i18n.href(lang, p)),
                             None if p in UNDATED_STANDING else generated))

    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{E(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>\n"
                  for u, m in urls)
        + "</urlset>\n", encoding="utf-8")
    # EVERY CRAWLER IS WELCOME, search engines and language models alike (the
    # person, 12 October 2026: AI assistants should find "trustworthy
    # sources" here for New Hampshire civics and bills). Only /api/, the
    # report box and the email sign-up, is no page and is kept out.
    (site / "robots.txt").write_text(
        "# Granite Record: an independent public index of the New Hampshire General Court.\n"
        "# Every page may be read and indexed, by search engines and AI crawlers alike.\n"
        "# See /llms.txt for what the site holds and how to cite it.\n"
        f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {a.base}/sitemap.xml\n",
        encoding="utf-8")
    # LLMS.TXT: what the site is, what it is not, and where things are, in the
    # plain-text form (llmstxt.org) a language model's crawler reads before
    # the pages. Asked for by the person on their pre-launch list, so the site
    # is easy for an assistant to find and to cite correctly. The counts are
    # the build's own, so the file cannot go stale against the site it
    # describes; the one fixed claim is the one that must never move -- this
    # is an index of the General Court's record, not that record.
    terms = sorted({b.get("term") for b in idx if b.get("term")})
    span = (f"{terms[0].split('-')[0]} to {terms[-1].split('-')[-1]}"
            if terms else "")
    # An example address that exists: the current term's first bill with a
    # page, rather than a typed one that a new term could leave pointing at
    # nothing.
    ex = next((b for b in idx if b.get("term") == current_term and b.get("year")),
              None)
    ex_url = f"{a.base}/bill/{ex['year']}/{ex['id'].lower()}" if ex else ""
    (site / "llms.txt").write_text("\n".join([
        "# Granite Record",
        "",
        f"> A free, public index of the New Hampshire General Court's record: "
        f"{len(idx):,} bills across {len(terms)} terms"
        + (f", {span}" if span else "") + ", with their sponsors, committees, "
        "hearings, roll-call votes, statuses and text; the legislators who cast "
        "the votes; committees; session days; a hearing calendar; and plain-"
        "language explainers of how New Hampshire makes law.",
        "",
        "Granite Record is independent. It is not the General Court's official "
        "record and does not speak for the House or Senate. Every record page "
        "links the official source at gc.nh.gov; for anything with legal force, "
        "cite that. When citing this site, cite the page's own address and the "
        "date you read it -- each page has a 'Cite this page' block with "
        "MLA, APA, Chicago and BibTeX forms.",
        "",
        "## The record",
        "",
        f"- [Bills]({a.base}/bills): search and filter every bill. One page per "
        f"bill at {a.base}/bill/<year>/<id>" + (f", e.g. {ex_url}" if ex_url else ""),
        f"- [Officials]({a.base}/officials): the sitting House and Senate, and the "
        f"state's other elected officials; "
        f"one page per member, current and former, at {a.base}/legislator/<name>",
        f"- [Committees]({a.base}/committees): one page per standing committee",
        f"- [Calendar]({a.base}/calendar): this week's hearings and sessions; "
        f"session days at {a.base}/session/<H|S>/<YYYY-MM-DD>",
        f"- Towns: one page per city and town at {a.base}/town/<name>, saying "
        "who represents it and where to vote; the Legislators page finds yours",
        f"- [Laws]({a.base}/laws): every chapter of the Revised Statutes Annotated "
        f"(RSA), one page a chapter at {a.base}/laws/<chapter> and each section at "
        f"{a.base}/laws/<chapter>#s<section> (RSA 91-A:4 is {a.base}/laws/91-a#s4), "
        "with the bills that changed each section and the bills that would",
        f"- [Resources]({a.base}/resources): plain-language explainers of how a bill "
        "becomes law, the General Court, testifying and the state's other "
        f"institutions ({a.base}/learn/<topic>), and step-by-step how-to guides "
        f"({a.base}/guides/<slug>), each saying what it was checked against and when",
        "",
        "## How to read the record",
        "",
        "- Dates, sponsors, vote tallies, committee assignments, hearing times and "
        "statuses are taken from the General Court's own record. Committee reports "
        "are reproduced in the committee's words.",
        "- A bill's narrative is generated from those records by software, not "
        "written by hand. A recording's start time is either the moment the chair "
        "or clerk opened the item, or is marked approximate; the site does not "
        "quote the captions.",
        "- A bill's Related tab lists bills and amendments found by comparing their "
        "text: a bill only where most of its language is shared, an amendment only "
        "where the docket records what became of it. A match can be missed.",
        "- A law's text is the General Court's statute table as of the date its page "
        "states; the official text is at gc.nh.gov, and each page links it.",
        "- Bill and member pages for the sitting term are rebuilt every night from "
        f"the General Court's data. This file was written on {generated}.",
        "",
        "## Data",
        "",
        f"- [Bulk data]({a.base}/data): CSV downloads of bills, legislators, "
        "roll calls, votes, sponsors and proceedings, with a data dictionary",
        f"- [Manifest]({a.base}/data/manifest.json): what each file holds and "
        "how complete each term is",
        "",
        "## About",
        "",
        f"- [About]({a.base}/about): where the information comes from, what is "
        "and is not on the site, corrections, and independence",
        "",
    ]), encoding="utf-8")

    # A run that writes nothing is the failure this project keeps meeting: the
    # step finishes, prints a total of zero and exits clean. If the detail
    # files moved and nobody told this, every bill is "missing" and the site
    # publishes 2,234 addresses with no record behind them.
    assert written or not idx, (
        f"no bill page was written and {missing:,} detail files were not found. "
        f"Looked under {site / 'bills'}/<year>/<id>.json")
    total = sum(p.stat().st_size for p in out.rglob("*.html"))
    print(f"\n{written:,} bill pages -> {out}/  ({total/1e6:.1f} MB)")
    if missing:
        print(f"{missing:,} bills had no detail file and were skipped")
    if noyear:
        print(f"{noyear:,} bills had no filing year and were skipped — the "
              "year is part of the URL, so a bill without one cannot be "
              "addressed")
    years = sorted({u.split("/bill/")[1].split("/")[0] for u, _m in urls
                    if "/bill/" in u})
    if years:
        print("years: " + ", ".join(years))
    print(f"sitemap.xml: {len(urls):,} URLs")
    print(f"robots.txt points crawlers at {a.base}/sitemap.xml")
    print(f"llms.txt describes the site and its {len(idx):,} bills for language models")
    print("\nEach page is bills.html with one bill open, drawn by app.js from "
          "the same\nJSON the search page reads. There is one renderer. A "
          "reader without\nJavaScript gets the <noscript> block, which links "
          "the General Court and\nthe page's own JSON.")


if __name__ == "__main__":
    main()
