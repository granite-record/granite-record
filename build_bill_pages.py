#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.39
"""
Write a real address for every bill, and the sitemap that points at them.

    python3 build_bill_pages.py --site site

WHAT THESE PAGES ARE

/bill/2026/hb1094.html is this site's search page with one bill open. Not a
second rendering of it -- the same one, from the same app.js, drawing the same
site/bills/2026/HB1094.json.

Until 7 September it was a second rendering: 900 lines of Python emitting a
complete no-JavaScript page per bill. That is why a reader who arrived from a
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

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path

import shell as S

E = html.escape

def describe(b):
    """The sentence a search engine shows under the link."""
    n = b.get("n") or b["id"]
    title = b.get("title") or ""
    desc = f"{n}, {title} " if title else f"{n}. "
    desc = re.sub(r"\s+", " ", desc)[:180].strip()
    return (desc + f" Status: {b.get('status', '')}. Sponsors, votes, hearings "
                   "and the full record.")


def noscript(b, d):
    """What a reader without JavaScript is told, and where to go instead.

    Not an apology and not an empty div. It names the bill, says plainly that
    the record is drawn in the browser, and gives two ways to the same facts
    that do not need one: the General Court's own page, and this site's JSON.
    """
    bid, n = b["id"], (b.get("n") or b["id"])
    yr = str(b.get("year") or "")
    title = b.get("title") or ""
    links = []
    if d.get("docket_url"):
        links.append(f'<a href="{E(d["docket_url"])}" rel="noopener">'
                     "the General Court's own docket for this bill</a>")
    if d.get("text_pdf"):
        links.append(f'<a href="{E(d["text_pdf"])}" rel="noopener">'
                     "the bill text (PDF)</a>")
    links.append(f'<a href="/bills/{E(yr)}/{E(bid)}.json">this page\'s data '
                 "as JSON</a>")
    return (
        '<noscript><div class="wrap" style="max-width:70ch;padding:26px 20px">'
        f"<h1>{E(n)}</h1>"
        + (f"<p>{E(title)}</p>" if title else "")
        + (f"<p><b>Status:</b> {E(b.get('status', ''))}</p>"
           if b.get("status") else "")
        + "<p>This page draws the record — sponsors, votes, hearings, "
          "committee reports and the bill text — in the browser, so it "
          "needs JavaScript. Everything it shows comes from the files linked "
          "below, which need none.</p><ul>"
        + "".join(f"<li>{x}</li>" for x in links)
        + '</ul><p><a href="/bills.html">All bills</a></p></div></noscript>')


def shell(t, b, d, base):
    """One bill's page: bills.html, told which bill it is."""
    bid = b["id"]
    yr = str(b.get("year") or "")
    n = b.get("n") or bid
    title = b.get("title") or ""
    path = f"/bill/{yr}/{bid.lower()}.html"
    # A per-bill feed exists only where there is a docket to report.
    feed = (f'<link rel="alternate" type="application/rss+xml" '
            f'title="{E(n)} updates" href="/feed/bill/{yr}/{bid.lower()}.xml">'
            if d.get("events") else "")
    return S.page(
        t, path=path, base=base,
        title=f"{n} — {title[:90]} | Granite Record",
        og_title=f"{n} — New Hampshire General Court",
        description=describe(b), alternate=feed,
        globals={"GR_BILL": f"{yr}/{bid}", "GR_STANDALONE": True},
        noscript=noscript(b, d), skip_label="Skip to this bill")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site = Path(a.site)
    idx = json.loads((site / "index.json").read_text(encoding="utf-8"))
    out = site / "bill"
    out.mkdir(parents=True, exist_ok=True)
    generated = date.today().isoformat()
    t = S.template(site)

    # The year is part of the path because bill numbers are only unique within
    # a term. There really is an HB 84 in several of them, and /bill/hb84.html
    # could only ever point at one.
    written, missing, noyear = 0, 0, 0
    urls = []
    for b in idx:
        yr = str(b.get("year") or "")
        if not yr:
            noyear += 1
            continue
        # The detail file lives under its filing year too, for the reason the
        # page does: a bill number is unique within a term and not beyond it.
        f = site / "bills" / yr / f"{b['id']}.json"
        if not f.exists():
            missing += 1
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        (out / yr).mkdir(parents=True, exist_ok=True)
        (out / yr / f"{b['id'].lower()}.html").write_text(
            shell(t, b, d, a.base), encoding="utf-8")
        urls.append(f"{a.base}/bill/{yr}/{b['id'].lower()}.html")
        written += 1
        if written % 1000 == 0:
            print(f"  {written:,}...", flush=True)

    for p in ("index.html", "bills.html", "legislators.html", "towns.html",
              "learn.html", "about.html"):
        if (site / p).exists():
            urls.append(f"{a.base}/{p}")

    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{E(u)}</loc><lastmod>{generated}</lastmod></url>\n"
                  for u in urls)
        + "</urlset>\n", encoding="utf-8")
    (site / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {a.base}/sitemap.xml\n",
        encoding="utf-8")

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
    years = sorted({u.split("/bill/")[1].split("/")[0] for u in urls
                    if "/bill/" in u})
    if years:
        print("years: " + ", ".join(years))
    print(f"sitemap.xml: {len(urls):,} URLs")
    print(f"robots.txt points crawlers at {a.base}/sitemap.xml")
    print("\nEach page is bills.html with one bill open, drawn by app.js from "
          "the same\nJSON the search page reads. There is one renderer. A "
          "reader without\nJavaScript gets the <noscript> block, which links "
          "the General Court and\nthe page's own JSON.")


if __name__ == "__main__":
    main()
