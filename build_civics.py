#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.13
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
import re
from collections import Counter
from pathlib import Path

import civics
import learn_numbers
import proceedings as P
import shell as S


def E(s):
    return html.escape(str(s or ""), quote=True)


def _load(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def record_figures(site, root=Path(".")):
    """Every count the Learn pages state, from what the build has just written.

    THEY WERE TYPED, AND THEY DRIFTED. Measured on 12 September against the
    built site, the pages said "4,230 bills on this site" of a site holding
    33,683, "68 vetoed bills" across "two terms" of nineteen, and "855 were
    killed" of a term the record now puts at 853 -- each true on the day it
    was written. civics.py names a figure as [[name]] and this fills it, each
    by the definition the typed number had been counted by, checked the same
    day: every one reproduced the typed figure wherever that was still right.
    """
    idx = _load(Path(site) / "index.json", [])
    term = max((r.get("term") or "" for r in idx), default="")
    cur = [r for r in idx if r.get("term") == term]
    status = Counter(r.get("status") for r in cur)
    kind = Counter(r.get("kind") for r in cur)
    prefix = Counter(re.match(r"[A-Z]*", r.get("id") or "").group(0) for r in cur)

    # The House from the district map, as build_composition counts it: seats per
    # (county, district), and the sitting members from the roster.
    house = {}
    senate = set()
    for wards in _load(Path(site) / "districts.json", {}).values():
        for w in wards.values():
            if w.get("senate"):
                senate.add(w["senate"])
            for h in w.get("house") or []:
                house[(h.get("county"), h.get("district"))] = h
    ordinary = [h for h in house.values() if not h.get("floterial")]
    seats = sum(h.get("seats") or 1 for h in house.values())
    sitting = sum(1 for m in _load(Path(site) / "legislators.json", []) if m.get("chamber") == "H")

    # How many members each House roll call of the term recorded, voting or not.
    first = term.split("-")[0]
    seated = Counter()
    if first.isdigit():
        years = {first, str(int(first) + 1)}
        for v in _load(Path(root) / "data" / "member_votes.json", []):
            if v.get("body") == "H" and str(v.get("year")) in years:
                seated[(v.get("year"), v.get("vote_number"))] += 1

    narr = _load(Path(root) / "narratives.json", {}).get(term, {})

    def chambers(rec):
        labels = [" " + (s.get("label") or "") + " " for s in rec.get("stages") or []]
        return {c for c, word in (("H", " House "), ("S", " Senate ")) if any(word in x for x in labels)}

    vetoed = {(r.get("term"), r.get("id")) for r in idx
              if r.get("status") in ("Vetoed, override failed", "Veto overridden, became law", "Vetoed")}
    messages = _load(Path(root) / "veto_messages.json", {})
    pending = sum(1 for r in idx if r.get("status") == "Vetoed")
    # Constitutional amendments of the term, by the passage marks the index
    # carries: origin, then first chamber, second chamber, governor, law.
    cacrs = [r for r in cur if (r.get("id") or "").startswith("CACR")]
    marks = lambda r: (r.get("passage") or "-----").ljust(5, "-")
    both = sum(1 for r in cacrs if marks(r)[2] == "p")
    # A hearing of a bill, once however many recordings it was matched against.
    hearings = len({(r.get("term"), r.get("bill"), r.get("body"), r.get("date")) for r in P.load()
                    if r.get("kind") in ("public hearing", "hearing")})
    figures = {
        "term": term.replace("-", "&ndash;"),
        "bills": len(cur), "hb": prefix["HB"], "sb": prefix["SB"], "cacr": prefix["CACR"],
        "resolutions": sum(n for p, n in prefix.items() if p.endswith("R") and p != "CACR"),
        "killed": status["Killed"], "signed": status["Signed into law"],
        "study": status["Referred for interim study"], "tabled": status["Died on the table"],
        "session_end": status["Died when the session ended"],
        "unsigned": status["Became law unsigned"], "overridden": status["Veto overridden, became law"],
        "law": kind["law"],
        "house_seats": seats, "house_sitting": sitting, "house_vacant": max(seats - sitting, 0),
        "seated_most": max(seated.values(), default=0), "seated_fewest": min(seated.values(), default=0),
        "house_districts": len(house), "senate_districts": len(senate), "ordinary": len(ordinary),
        "single": sum(1 for h in ordinary if h.get("seats") == 1),
        "two": sum(1 for h in ordinary if h.get("seats") == 2),
        "largest": max((h.get("seats") or 1 for h in house.values()), default=0),
        "floterial": len(house) - len(ordinary),
        "all_bills": len(idx), "all_rollcall": sum(1 for r in idx if (r.get("nrc") or 0) > 0),
        "all_no_rollcall": sum(1 for r in idx if not (r.get("nrc") or 0) > 0),
        "hb2_rollcalls": len(_load(Path(root) / "rollcalls.json", {}).get(term, {}).get("HB2", [])),
        "narrated": len(narr), "both_chambers": sum(1 for v in narr.values() if chambers(v) == {"H", "S"}),
        "conference": sum(1 for v in narr.values()
                          if any("conference" in (s.get("label") or "").lower() for s in v.get("stages") or [])),
        "terms": len({r.get("term") for r in idx if r.get("term")}),
        "vetoed": len(vetoed),
        "veto_failed": sum(1 for r in idx if r.get("status") == "Vetoed, override failed"),
        "veto_overridden": sum(1 for r in idx if r.get("status") == "Veto overridden, became law"),
        "veto_messages": sum(1 for t, b in vetoed if b in messages.get(t, {})),
        "veto_pending": ("" if not pending else " One is still awaiting its override vote."
                         if pending == 1 else f" {pending} are still awaiting their override votes."),
        "cacr_voters": ("<b>None of them reached the voters.</b>" if not both else
                        f"<b>{both:,} passed both chambers and went to the voters.</b>"),
        "cacr_killed": sum(1 for r in cacrs if r.get("status") == "Killed"),
        "cacr_session_end": sum(1 for r in cacrs if r.get("status") == "Died when the session ended"),
        "cacr_one_chamber": sum(1 for r in cacrs if marks(r)[1] == "p" and marks(r)[2] == "x"),
        "hearings": hearings,
    }
    return {k: (f"{v:,}" if isinstance(v, int) else v) for k, v in figures.items()}


def fill(text, figures):
    """[[name]] -> its figure. A name with no figure stops the build: a page
    that printed "[[killed]]", or nothing where a number was, would publish."""
    unknown = sorted(set(re.findall(r"\[\[(\w+)\]\]", text or "")) - set(figures))
    if unknown:
        raise SystemExit(f"civics.py names figures build_civics does not count: {unknown}")
    return re.sub(r"\[\[(\w+)\]\]", lambda m: str(figures[m.group(1)]), text or "")


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
    # PREVIOUS ON THE LEFT, NEXT ON THE RIGHT, in the order a reader reads --
    # the person's correction of 14 September, when the next topic sat on the
    # left. The markup is in the order it is drawn, so the keyboard meets them
    # the same way round.
    bits = ['<nav class="tnav">']
    if i:
        prev = topics[i - 1]
        bits.append(f'<a class="prev" href="learn/{E(prev["slug"])}.html">'
                    f'<span>Previous</span><b>{E(prev["title"])}</b></a>')
    bits.append('<a class="all" href="learn.html">All topics</a>')
    if i + 1 < len(topics):
        nxt = topics[i + 1]
        bits.append(f'<a class="next" href="learn/{E(nxt["slug"])}.html">'
                    f'<span>Next topic</span><b>{E(nxt["title"])}</b></a>')
    else:
        bits.append('<a class="next" href="learn.html">'
                    '<span>Back to</span><b>All topics</b></a>')
    bits.append("</nav>")
    return "".join(bits)


def hub(topics):
    out = ['<h1>How New Hampshire works</h1>',
           '<p class="lead">Eleven short pages on the parts of state '
           'government, each one linked to where you can watch it happening '
           'in the record.</p>',
           # WHAT THIS IS FOR, SAID ONCE. The hub was a numbered list and
           # nothing else: a reader arriving cold could not tell whether
           # these were explainers written from a textbook or written from
           # the record, and that distinction is the only reason this section
           # exists rather than linking to somebody else's civics site.
           '<p>Every figure on these pages is one this site can produce from '
           'the record, and every page says what it counts and over what '
           'period. Where the record holds nothing &mdash; the courts, the '
           'Executive Council &mdash; the page is short and says so rather '
           'than being padded with prose nobody here can check.</p>',
           # THE ONE PAGE MOST PEOPLE WANT. Eleven equal items in a list made
           # the reader choose before they knew what they were choosing
           # between, and nine times in ten the answer is the same page.
           '<div class="shows"><h2>If you read one</h2>'
           '<p><a href="learn/how-a-bill-becomes-law.html">How a bill becomes '
           'law</a> &mdash; the course a bill runs, the stages it can die at, '
           'and two bills of 2024 followed all the way through with the '
           'recording of every hearing and vote.</p></div>']
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
        'is wrong, <a href="mailto:contact@graniterecord.org">tell us</a> '
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
    figures = record_figures(site)
    print(f"figures from the record: {figures['all_bills']} bills, {figures['terms']} terms, "
          f"{figures['vetoed']} vetoed, {figures['bills']} in {figures['term'].replace('&ndash;', '-')}")

    # ---- the hub -------------------------------------------------------
    page = S.page(tmpl, path="/learn.html", base=a.base,
                  title="How New Hampshire works | Granite Record",
                  og_title="How New Hampshire works",
                  og_image="og-learn.png", og_alt="Granite Record: how New Hampshire works",
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
        body.append(fill(t["body"], figures))
        if t.get("holds"):
            body.append(f'<p class="caveat">{fill(t["holds"], figures)}</p>')
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
                   og_image="og-learn.png", og_alt="Granite Record: how New Hampshire works",
                   globals={"GR_STATIC": True}, noscript="",
                   skip_label="Skip to the page", sr_title="",
                   nav_current="learn.html")
        p = p.replace('<div id="results"></div>',
                      f'<div id="results"><div class="civics">'
                      f'{"".join(body)}</div></div>', 1)
        if "[[" in p:
            raise SystemExit(f"learn/{t['slug']}.html would publish an unfilled figure: "
                             + p[p.index("[["):p.index("[[") + 40])
        (out / f"{t['slug']}.html").write_text(p, encoding="utf-8")
        urls.append(a.base + S.canon(f"/learn/{t['slug']}.html"))

    # ---- the record in numbers: a DRAFT, on no list ----------------------
    # learn_numbers.py says what it is. noindex, not in the hub, not in the
    # sitemap: the person reads it at its address before anyone else is led to it.
    path = "/learn/by-the-numbers.html"
    p = S.page(tmpl, path=path, base=a.base,
               title=S.title_of("The record in numbers", "How New Hampshire works"),
               og_title="The record in numbers",
               description=("Statistics counted from the New Hampshire General Court's own "
                            "record: vetoes, the closest votes, how votes are taken, and how "
                            "often a chamber overrules its committee."),
               alternate='<meta name="robots" content="noindex">',
               og_image="og-learn.png", og_alt="Granite Record: how New Hampshire works",
               globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the page",
               sr_title="", nav_current="learn.html")
    p = p.replace('<div id="results"></div>',
                  '<div id="results"><div class="civics"><p class="crumb"><a href="learn.html">'
                  'How New Hampshire works</a></p><h1>The record in numbers</h1>'
                  + learn_numbers.body(site) + '</div></div>', 1)
    (out / "by-the-numbers.html").write_text(p, encoding="utf-8")
    print("  learn/by-the-numbers.html: the draft page of statistics (noindex, unlisted)")

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
