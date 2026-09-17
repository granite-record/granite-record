#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.19
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


def _follows_committee(narr):
    """The percentage of this term's floor decisions that went the committee's way.

    Rounded to a whole number, because a tenth of a point on a claim like this
    is precision the sentence cannot carry. It counts only bills where a
    committee reported and the chamber then took a majority-recommendation
    vote -- the cases where the two can be compared at all.
    """
    stats, _ = learn_numbers.overturned(narr)
    decided = sum(v[0] for v in stats.values())
    against = sum(v[1] for v in stats.values())
    return round(100 * (decided - against) / decided) if decided else 0


def _load(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# "shall adopt rules", "may adopt rules pursuant to RSA 541-A" -- the sentence
# by which the legislature hands an agency the detail. Written out rather than
# counted by hand because the administrative rules page's whole argument is
# that this happens constantly and invisibly, and a reader is entitled to the
# number behind it.
_DELEGATES = re.compile(r"(?:shall|may)\s+adopt\s+rules?", re.I)


def _rules_delegated(root, term):
    """Bills of this term whose own text delegates rulemaking to an agency."""
    texts = _load(Path(root) / "bill_text.json", {}).get(term) or {}
    n = 0
    for rec in texts.values():
        body = rec.get("text") if isinstance(rec, dict) else rec
        if body and _DELEGATES.search(body):
            n += 1
    return n


def _notice(root, term, _seen={}):
    """(hearings counted, median days) between a calendar's publication and the
    hearing it announced, over this term.

    The testifying page says how much warning a reader actually gets, and that
    is a promise about the future, so it has to be measured rather than
    guessed. A hearing is counted once however many calendars carried it.
    Cached because two figures are taken from one pass.
    """
    if term in _seen:
        return _seen[term]
    rows = _load(Path(root) / "meetings.json", [])
    gaps, seen = [], set()
    years = set()
    if "-" in term:
        a, b = term.split("-")[0], term.split("-")[-1]
        years = {a, b}
    for r in rows:
        if r.get("kind") != "public hearing":
            continue
        day, noticed = (r.get("date") or "")[:10], (r.get("noticed") or "")[:10]
        if not (day and noticed) or day[:4] not in years:
            continue
        key = (r.get("body"), r.get("bill"), day, r.get("committee"))
        if key in seen:
            continue
        seen.add(key)
        try:
            from datetime import date
            d1 = date(*map(int, noticed.split("-")))
            d2 = date(*map(int, day.split("-")))
        except (TypeError, ValueError):
            continue
        gap = (d2 - d1).days
        if gap >= 0:
            gaps.append(gap)
    gaps.sort()
    med = gaps[len(gaps) // 2] if gaps else 0
    _seen[term] = (len(gaps), med)
    return _seen[term]


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
        # How often a chamber went the way its committee recommended, from the
        # record rather than from an impression. learn_numbers.overturned pairs
        # each committee report with the floor vote that followed it and is
        # what the draft page of numbers reports at length; this is the one
        # figure of it the Learn page states. The prose used to say "usually
        # follows it", which is true and says nothing: it is 98%, and the 2%
        # is the interesting part.
        "follows_committee": _follows_committee(narr),
        # Eight more the rewritten pages asked for, each counted from the file
        # named beside it rather than typed. A page may state a figure only if
        # the site can produce it, which is the rule that keeps this section
        # worth believing.
        "municipalities": len(_load(Path(root) / "town_officials.json", {})),
        "members_sitting": len(_load(Path(site) / "legislators.json", [])),
        "members_email": sum(1 for m in _load(Path(site) / "legislators.json", [])
                             if (m.get("email") or "").strip()),
        "floterial_seats": sum(h.get("seats") or 1 for h in house.values()
                               if h.get("floterial")),
        # The '1989' in 'back to 1989', from the terms themselves.
        "first_year": min((r.get("term") or "" for r in idx if r.get("term")),
                          default="-").split("-")[0],
        "rules_delegated": _rules_delegated(root, term),
        "notice_hearings": _notice(root, term)[0],
        "notice_median": _notice(root, term)[1],
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


def dashes(text):
    """" -- " as the dash it is meant to be.

    The Learn prose is written in the plain-text shorthand this repository's own
    documents use, and it was published that way: "The Council -- five members,
    elected by district -- approves contracts", 5 times on the hub and 54 across
    the eleven pages on 15 September. Nowhere else on the site prints it. Only a
    hyphen pair with a space on each side is touched, so "Education - General",
    a range, and anything inside a tag are left alone.
    """
    return re.sub(r"(?<=\s)--(?=\s)", "—", text or "")


def fill(text, figures):
    """[[name]] -> its figure. A name with no figure stops the build: a page
    that printed "[[killed]]", or nothing where a number was, would publish."""
    unknown = sorted(set(re.findall(r"\[\[(\w+)\]\]", text or "")) - set(figures))
    if unknown:
        raise SystemExit(f"civics.py names figures build_civics does not count: {unknown}")
    return dashes(re.sub(r"\[\[(\w+)\]\]",
                         lambda m: str(figures[m.group(1)]), text or ""))


def sources_block(sources):
    if not sources:
        return ""
    # A SOURCE ON THIS SITE IS NOT AN OUTWARD LINK. Every entry here used to be
    # somebody else's page, so every one got target="_blank" and the arrow this
    # site uses to mean "this leaves the record". One of them is now our own
    # directory -- the General Court's address lookup answers 404 and the town
    # pages already hold what it gave -- and sending a reader to our own page in
    # a new tab, marked as though it were elsewhere, tells them something untrue
    # about where they are going.
    def one(label, u):
        away = u.startswith("http")
        mark = ' target="_blank" rel="noopener"' if away else ""
        arrow = " &#8599;" if away else ""
        return f'<li><a href="{E(u)}"{mark}>{E(label)}</a>{arrow}</li>'

    items = "".join(one(label, u) for label, u in sources)
    return (f'<section class="srcs"><h2>Where this comes from</h2>'
            f'<ul class="reading">{items}</ul></section>')


def rail(topics, here=None):
    """The eleven pages, beside whichever one is open.

    THE SECTION READS AS A BOOK OR AS ELEVEN DEAD ENDS. Each page ended with the
    next one by name and nothing else, so a reader who wanted the third page
    from the second had to go back to the hub; and since these pages line up on
    the site's left edge (16 September) the right two thirds of a Learn page was
    empty, which is the shape the person has said reads as broken. The rail
    fills it with the one thing a reader of a civics section wants: where they
    are among the rest. It is the same list the hub draws, in the same order.
    """
    items = "".join(
        f'<li><a href="{E(S.canon("learn/" + t["slug"] + ".html"))}"'
        + (' aria-current="page"' if t["slug"] == here else "")
        + f'>{E(t["title"])}</a></li>' for t in topics)
    # The count comes from the list, like every other number on these pages, and
    # it is spelled the way the prose spells a small number.
    words = ["no", "one", "two", "three", "four", "five", "six", "seven",
             "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
             "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
    n = len(topics)
    return ('<aside class="lrail" aria-label="The pages of this section">'
            f'<h2>The {words[n] if n < len(words) else n} pages</h2>'
            f'<ol>{items}</ol></aside>')


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


# Spelled out, because "11 short pages" in a sentence reads like a list
# heading rather than prose. Falls back to the digits past twenty, by which
# point the section is a different thing and the sentence needs rewriting
# anyway.
NUMBER_WORD = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
    7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven",
    12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen",
    16: "Sixteen", 17: "Seventeen", 18: "Eighteen", 19: "Nineteen",
    20: "Twenty",
}


def hub(topics):
    # COUNTED, NOT TYPED. This read "Eleven short pages" while civics.TOPICS
    # held eleven, and the sentence is one edit to that list away from being
    # false -- on a page whose whole argument is that its figures come from
    # the record rather than from someone's memory.
    n = len(topics)
    out = ['<h1>How New Hampshire works</h1>',
           f'<p class="lead">{NUMBER_WORD.get(n, n)} short pages on the parts '
           'of state and local government, each one linked to where you can '
           'watch it happening in the record.</p>',
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
                f'<span>{dashes(E(t["blurb"]))}</span></a></li>')
        out.append("</ol>")
    # NOT ONE OF THE NUMBERED PAGES. The topics above are short explanations
    # meant to be read in order, and each ends by naming the next. This is a
    # long table of statistics counted from the record -- a different kind of
    # thing for a different reader, and putting it in the sequence would
    # interrupt the sequence. It sits after them, named for what it is.
    out.append(
        '<h2>The record in numbers</h2>'
        '<p class="src">Counted from the General Court\'s own record, at '
        'build time, every time this site is built.</p>'
        '<ol class="tlist"><li>'
        '<a href="learn/by-the-numbers.html">'
        '<b>The record in numbers</b>'
        '<span>Vetoes and what happens to them, the closest votes on record, '
        'how often a chamber overrules its own committee, and how the two '
        'chambers differ in the way they take a vote.</span></a></li></ol>')
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
    # NO RAIL ON THE HUB. Every topic page carries a rail of the other ten,
    # because a reader inside the section needs a way across it. The hub IS
    # that list: drawing the rail here printed all eleven titles twice on one
    # page, the second time in grey at half the size, and left the whole right
    # half of a 1440px window empty while the eleven entries queued up in a
    # 560px column. Without it the hub is one thing at full width.
    page = page.replace('<div id="results"></div>',
                        f'<div id="results">'
                        f'<div class="civics hubpage">{hub(topics)}</div>'
                        f'</div>', 1)
    (site / "learn.html").write_text(page, encoding="utf-8")

    # ---- one page a topic ----------------------------------------------
    for i, t in enumerate(topics):
        body = [f'<p class="crumb"><a href="learn.html">How New Hampshire '
                f'works</a></p>',
                f'<h1>{E(t["title"])}</h1>']
        if t["blurb"]:
            body.append(f'<p class="lead">{dashes(E(t["blurb"]))}</p>')
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
                      f'<div id="results"><div class="lcols">'
                      f'<div class="civics">{"".join(body)}</div>'
                      f'{rail(topics, t["slug"])}</div></div>', 1)
        if "[[" in p:
            raise SystemExit(f"learn/{t['slug']}.html would publish an unfilled figure: "
                             + p[p.index("[["):p.index("[[") + 40])
        (out / f"{t['slug']}.html").write_text(p, encoding="utf-8")
        urls.append(a.base + S.canon(f"/learn/{t['slug']}.html"))

    # ---- the record in numbers ------------------------------------------
    # learn_numbers.py says what it is. It was written on 13 September as a
    # draft: noindex, absent from the hub and from the sitemap, so the person
    # could read it at its address before anyone else was led to it. They read
    # it and asked on the 17th for it to be public, so the three things that
    # were keeping it private are gone -- it is in the hub, it is in the
    # sitemap, and it is no longer noindex.
    #
    # It is NOT in civics.TOPICS. The topics are short explanations that end by
    # naming the next one, and this is a long table of counts; hub() puts it
    # after them under its own heading rather than in the sequence.
    path = "/learn/by-the-numbers.html"
    p = S.page(tmpl, path=path, base=a.base,
               title=S.title_of("The record in numbers", "How New Hampshire works"),
               og_title="The record in numbers",
               description=("Statistics counted from the New Hampshire General Court's own "
                            "record: vetoes, the closest votes, how votes are taken, and how "
                            "often a chamber overrules its committee."),
               og_image="og-learn.png", og_alt="Granite Record: how New Hampshire works",
               globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the page",
               sr_title="", nav_current="learn.html")
    p = p.replace('<div id="results"></div>',
                  '<div id="results"><div class="civics"><p class="crumb"><a href="learn.html">'
                  'How New Hampshire works</a></p><h1>The record in numbers</h1>'
                  + learn_numbers.body(site) + '</div></div>', 1)
    (out / "by-the-numbers.html").write_text(p, encoding="utf-8")
    urls.append(a.base + S.canon(path))
    print("  learn/by-the-numbers.html: the page of statistics (public since 17 Sep)")

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
