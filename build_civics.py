#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.7
"""
The civics section: a hub and one page per topic, in order.

    python3 build_civics.py --site site --base https://graniterecord.org

Writes site/learn.html (the hub) and site/learn/<slug>.html (the topics).
No network. Reads civics.py for the writing and shell.py for the page frame.

WHY THE HUB KEEPS THE OLD ADDRESS

learn.html was one page called "How it works" and is now the way into eleven.
It keeps its address because the nav links to it, the home page links to it,
and anything already pointing at it should still arrive somewhere sensible
rather than at a 404. The topics live under /learn/ beneath it.

THE ORDER MATTERS

Each page ends with the next one by name -- "Next: How a bill becomes law" --
because a reader who has just learned what the General Court is has a natural
next question, and a menu does not answer it. The order is civics.TOPICS and
nothing else; the hub, the footers and the sitemap all read it, so there is
one place to reorder the section.
"""

import argparse
import html
import json
from pathlib import Path

import civics
import shell as S


def E(s):
    return html.escape(str(s or ""), quote=True)


def sources_block(sources):
    if not sources:
        return ""
    items = "".join(
        f'<li><a href="{E(u)}" target="_blank" rel="noopener">{E(label)}'
        f'</a> &#8599;</li>' for label, u in sources)
    return (f'<section class="srcs"><h2>Where this comes from</h2>'
            f'<ul class="reading">{items}</ul></section>')


def footer_nav(i, topics):
    """The next topic by name, and the way back to the hub.

    Every href here is written from the SITE ROOT, not relative to /learn/.
    bills.html carries <base href="/"> -- it has to, because opening a bill on
    the search page pushes /bill/2026/hb1123 and re-bases every link on it --
    and these pages are built from that same template. So "../learn.html"
    would resolve to /../learn.html and a sibling "courts.html" to /courts.html.
    """
    bits = ['<nav class="tnav">']
    if i + 1 < len(topics):
        nxt = topics[i + 1]
        bits.append(f'<a class="next" href="learn/{E(nxt["slug"])}.html">'
                    f'<span>Next topic</span><b>{E(nxt["title"])}</b></a>')
    else:
        bits.append('<a class="next" href="learn.html">'
                    '<span>Back to</span><b>All topics</b></a>')
    if i:
        prev = topics[i - 1]
        bits.append(f'<a class="prev" href="learn/{E(prev["slug"])}.html">'
                    f'<span>Previous</span><b>{E(prev["title"])}</b></a>')
    bits.append('<a class="all" href="learn.html">All topics</a>')
    bits.append("</nav>")
    return "".join(bits)


def hub(topics):
    out = ['<h1>How New Hampshire works</h1>',
           '<p class="lead">Eleven short pages on the parts of state '
           'government, each one linked to where you can watch it happening '
           'in the record.</p>']
    for group, note in civics.GROUPS:
        rows = [(i, t) for i, t in enumerate(topics) if t["group"] == group]
        if not rows:
            continue
        out.append(f'<h2>{E(group)}</h2><p class="src">{E(note)}</p>'
                   '<ol class="tlist">')
        for n, (i, t) in enumerate(rows, 1):
            out.append(
                f'<li><a href="learn/{E(t["slug"])}.html">'
                f'<b>{E(t["title"])}</b>'
                f'<span>{E(t["blurb"])}</span></a></li>')
        out.append("</ol>")
    out.append(
        '<p class="note">Every page here ends with its sources. If something '
        'is wrong, <a href="mailto:corrections@graniterecord.org">tell us</a> '
        '&mdash; that address exists for this.</p>')
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()

    site = Path(a.site)
    topics = civics.TOPICS
    if not topics:
        print("civics.TOPICS is empty; nothing written.")
        return 0
    out = site / "learn"
    out.mkdir(parents=True, exist_ok=True)

    tmpl = S.template(site)
    urls = [a.base + S.canon("/learn.html")]

    # ---- the hub -------------------------------------------------------
    page = S.page(tmpl, path="/learn.html", base=a.base,
                  title="How New Hampshire works | Granite Record",
                  og_title="How New Hampshire works",
                  description=("Short, plain explanations of the parts of New "
                               "Hampshire state government, each linked to "
                               "where you can watch it happening."),
                  globals={"GR_STATIC": True}, noscript="",
                  skip_label="Skip to the topics",
                  sr_title="", nav_current="learn.html")
    page = page.replace('<div id="results"></div>',
                        f'<div id="results"><div class="civics hubpage">'
                        f'{hub(topics)}</div></div>', 1)
    (site / "learn.html").write_text(page, encoding="utf-8")

    # ---- one page a topic ----------------------------------------------
    for i, t in enumerate(topics):
        body = [f'<p class="crumb"><a href="learn.html">How New Hampshire '
                f'works</a></p>',
                f'<h1>{E(t["title"])}</h1>']
        if t["blurb"]:
            body.append(f'<p class="lead">{E(t["blurb"])}</p>')
        body.append(t["body"])
        if t.get("holds"):
            body.append(f'<p class="caveat">{t["holds"]}</p>')
        body.append(sources_block(t["sources"]))
        body.append(footer_nav(i, topics))

        p = S.page(tmpl, path=f"/learn/{t['slug']}.html", base=a.base,
                   # THE SITE'S NAME LAST, on every page. These eleven ended
                   # "| How New Hampshire works" while the other 34,000 ended
                   # "| Granite Record", so a search result for a civics page
                   # did not look like it came from the same site. The section
                   # is worth naming, so it goes in front of the brand rather
                   # than instead of it.
                   title=S.title_of(t["title"],
                                    "How New Hampshire works"),
                   og_title=t["title"], description=t["blurb"],
                   globals={"GR_STATIC": True}, noscript="",
                   skip_label="Skip to the page", sr_title="",
                   nav_current="learn.html")
        p = p.replace('<div id="results"></div>',
                      f'<div id="results"><div class="civics">'
                      f'{"".join(body)}</div></div>', 1)
        (out / f"{t['slug']}.html").write_text(p, encoding="utf-8")
        urls.append(a.base + S.canon(f"/learn/{t['slug']}.html"))

    # ---- the sitemap, appended rather than rewritten -------------------
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{S.E(u)}</loc></url>\n"
                      for u in urls if S.E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"  {len(add.splitlines())} added to sitemap.xml")

    n_src = sum(len(t["sources"]) for t in topics)
    print(f"{len(topics)} topics -> {out}/ and learn.html")
    print(f"  {n_src} sources linked, "
          f"{sum(1 for t in topics if t.get('holds'))} pages state a limit")
    missing = [t["slug"] for t in topics if not t["sources"]]
    if missing:
        print(f"  NO SOURCES on: {', '.join(missing)} -- every page needs "
              "somewhere a reader can check it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
