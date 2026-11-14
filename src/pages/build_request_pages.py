#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-08.9
"""
A page for each bill request of the session the site lists, so a request can
be shared by its own address rather than by the search.

    python3 src/pages/build_request_pages.py --site site

Alice, 8 November 2026. Each page is /request/<number> (build_lsrs.py's
"address"); noindex and out of the sitemap, as the provisional members-elect
pages are; it shows what a request has -- its number, title, prime sponsor
(the chip as everywhere), what kind of request it is and where it stands --
and the requests' own explanation. Nothing here knows how a state numbers
its requests or where they come from: build_lsrs.py, the source's reader,
gives each row its "address" and, once the request is a bill or filing is
complete, its "moved_to".

WHICH ARE WRITTEN. Every request with no "moved_to": filed, or withdrawn (a
withdrawn request keeps its page, as a withdrawn bill does). One with
"moved_to" has no page: its address answers with a 301 there, which
build_pages writes into _redirects (moved_requests). So no night leaves a
page and a redirect at one address -- and a page an earlier night wrote for a
request that has since moved is taken away here, as is one for a request no
longer listed.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re

import shell as S
import components as C

E = S.E
# Not indexed (Alice, 8 November 2026), as the provisional members-elect pages.
ROBOTS = '<meta name="robots" content="noindex,follow">'


def explain(year, abbr=None):
    """The requests' explanation, the bill search's own words
    (fix/search-polish, 8 November 2026), and what the number's abbreviation
    stands for (the owner, 13 November 2026), which a phone cannot hover to
    read: `abbr` is meta.requests's, a map of an abbreviation to its words."""
    said = "".join(f" {E(k)} stands for {E(v)}." for k, v in (abbr or {}).items())
    return ("<b>Requests, not bills yet.</b> Each is a member&rsquo;s request to have a bill "
            "drafted: a title and a sponsor, nothing more, until it is filed as a numbered "
            f"{E(str(year))} bill. Some are withdrawn first." + said)


def abbr_html(text, abbr, hard=False):
    """`text` escaped, its first word an <abbr> with the title that says what
    it stands for where `abbr` names it (the owner, 13 November 2026: add
    what it stands for "as a tooltip"); the title is the tooltip, and explain() says it in words for
    a touch screen. `hard`: a non-breaking space after it, for the trail,
    whose flex row drops a plain one."""
    first, sep, rest = str(text or "").partition(" ")
    if first and first in (abbr or {}):
        return f'<abbr class="lsrabbr" title="{E(abbr[first])}">{E(first)}</abbr>{"&nbsp;" if hard and sep else sep}{E(rest)}'
    return E(str(text or ""))


def sponsors(site):
    """{slug: {"party_code", "display_full", "slug"}} for the chip: the sitting
    roster's members (legislators.json) and the provisional members-elect pages
    (elect_pages.json). former.json is deliberately NOT read: a former member
    holds no seat, and their display_full names the old one, which others hold
    now (the review of 13 November 2026); person_chip draws them from the
    request's own row instead."""
    out = {}
    f = site / "legislators.json"
    for m in (json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []):
        if m.get("slug"):
            out[m["slug"]] = {"party_code": m.get("party"), "slug": m["slug"],
                              "display_full": m.get("display_full") or m.get("display")
                              or m.get("name")}
    f = site / "elect_pages.json"
    for p in (json.loads(f.read_text(encoding="utf-8")).get("pages") or [] if f.is_file() else []):
        out.setdefault(p["slug"], {"party_code": p.get("party"), "slug": p["slug"],
                                   "display_full": f"{p['name']} ({p['party']})"
                                   if p.get("party") else p["name"]})
    return out


SHARE = ('<button type="button" class="pshare" data-share>' + C.icon("share") + "Share</button>"
         '<span class="sharestate" role="status" aria-live="polite"></span>')


def state_of(r):
    """The word the page's chip and status say: "Withdrawn", as the source
    says it and no more -- the list does not say when, nor tell a withdrawal
    from a request that became a bill the bill data has not caught up with
    (build_lsrs; the review of 8 November 2026) -- else the status the row
    carries: Requested, or Filed (the owner, 13 November 2026)."""
    return "Withdrawn" if r.get("withdrawn") else (r.get("status") or "")


def person_chip(who_of, slug, label, party=""):
    """THE ONE RULE for a person on a request's page (13 November 2026): a
    sitting member, or a provisional member-elect page, keeps the chip the
    roster gives -- their seat today. Anyone else the row names, a returning
    former member for one, is drawn as the row's own label and party, linked
    to their page when there is a slug, as the request's card draws them
    ("Ben Baroody (D)"): their old seat belongs to someone else now. `party`
    is the row's party code; where the caller has none it is read from a
    trailing "(D)" in the label."""
    m = who_of.get(slug) if slug else None
    if m:
        return C.pchip(m)
    tag = re.search(r"\(([A-Za-z])\)\s*$", label or "")
    return C.pchip({"party_code": party or (tag.group(1) if tag else ""),
                    "slug": slug or "", "display_full": label or ""})


def chips_of(people, who_of):
    """The chips of the people a row names: [{"label", "slug"}, ...]."""
    return [person_chip(who_of, c.get("slug"), c.get("label"), c.get("party") or "")
            for c in people or []]


def rail_of(r):
    """A request's own rail, three stops (Alice, 12 November 2026, from a phone
    screenshot where the bill's six stops ran into one another: "a separate
    rail for the requests with Requested, Filed meaning the text is publicly
    available, and Introduced"): Requested, always reached -- a withdrawn
    request was still requested (the owner, the same morning: "Request being
    withdrawn should still show request as green but filed as red"); Filed,
    reached once the bill's text is public, and the cross where the request
    was withdrawn instead; Introduced, which a request reaches by becoming a numbered bill,
    when its address forwards to the bill's page and the bill's own rail
    takes over -- so it is never reached here. Same rail_html, same look. No
    day is shown: the list gives none.

    WHAT SAYS "FILED". Nothing on disk yet: the request list (the list build_lsrs reads)
    carries a number, kind, title, sponsor and a withdrawn flag, and no bill
    of the session has been published (data/bills.json has no 2027-2028).
    So the stop reads the row's "filed" -- true, or the day the text became
    public ("YYYY-MM-DD"), which build_lsrs.rows_from carries over from the
    source row once the source gives it -- and is drawn not reached until
    then. A withdrawn request ends there, at the cross."""
    gone = bool(r.get("withdrawn"))
    filed = r.get("filed") and not gone
    day = r["filed"] if filed and isinstance(r["filed"], str) and r["filed"][:1].isdigit() else ""
    stops = [
        {"stop": "Requested", "mark": "p", "date": "", "short": "",
         "say": "made"},
        {"stop": "Filed", "mark": "x" if gone else ("p" if filed else "-"), "date": day, "short": "",
         "say": "Withdrawn" if gone else ("Text public" if filed else "")},
        {"stop": "Introduced", "mark": "-", "date": "", "short": "", "say": ""}]
    return C.rail_html(stops)


def head(r, req, who_of, path, base):
    """The bill page's head (components.record_head, as app.js's billHead
    draws a bill's): the trail, the number with the status chip, the title, the
    field grid, the rail, and the action column -- Cite this page, Share and
    Report a problem as every record page's, and Follow, which app.js puts
    after Cite where a request can be followed (GR_REQUEST). No Testify, no
    Print: there is no hearing to sign in to and no record to print yet.
    A field the request has no value for is left out, as the bill page leaves
    its own out: no Committee until it is referred."""
    word = state_of(r)
    slug = r.get("sponsor_slug")
    name = r.get("sponsor_label") or r.get("sponsor") or ""
    facts = []
    if slug and (slug in who_of or name):
        facts.append(["Prime Sponsor", person_chip(who_of, slug, name, r.get("sponsor_party") or "")])
    elif name:
        facts.append(["Prime Sponsor", E(name)])
    cos = chips_of(r.get("cosponsors"), who_of)
    if cos:
        facts.append(["Co-Sponsors" if len(cos) > 1 else "Co-Sponsor", " ".join(cos)])
    if r.get("body_label"):
        facts.append(["Kind", E(r["body_label"])])
    # THE TOPIC READ FROM THE TITLE (request_topics.py), said to be so; the
    # General Court's own topic is the bill's, after it is filed.
    if r.get("topic") and r.get("topic_by") == "title":
        facts.append(["Topic (from the title)", E(r["topic"])])
    cite = S.cite_block(path, f"{r.get('n')}: {r.get('title') or ''} | Granite Record", base,
                        S.cited())
    assert cite.endswith("</div>"), "the citation block no longer ends its row"
    chips = C.WORDBOOK.get("chips", {}).get("request", {})
    page = C.record_head({
        "trail": [["Bills", "bills"],
                  [req.get("label") or "Bill Requests", f"bills?term={req['term']}"],
                  [r.get("n") or "", ""]],
        "title": abbr_html(r.get("n"), req.get("abbr")),
        "chip": C.chip(word, "cstat " + chips.get(word, ""), "m"),
        "line": f'<span translate="no">{E(r.get("title") or "")}</span>',
        "facts": facts, "rail": rail_of(r),
        "actions": cite[:-len("</div>")] + SHARE + "</div>",
        "kind": "bill"})
    # The trail names the request by its number, plain text: the same
    # abbreviation, explained.
    n = r.get("n") or ""
    return page.replace(f'<li aria-current="page">{E(n)}</li>',
                        f'<li aria-current="page">{abbr_html(n, req.get("abbr"), True)}</li>', 1)


def summary(r, req):
    """The Summary tab: the requests' explanation, and the facts of this
    one."""
    state = state_of(r)
    return (C.section("About Requests",
                      f'<p class="lsrnote">{explain(r.get("year") or req.get("year"), req.get("abbr"))}</p>',
                      "about")
            + C.section("The Request", f'<p><b>Status:</b> {E(state)}</p>', "request"))


def sponsors_pane(r, who_of):
    """The Sponsors tab, only where co-sponsors are listed (the General
    Court lists one once they have accepted): the prime sponsor and every
    co-sponsor as the person chip, by person_chip's one rule, as head() draws
    the prime sponsor: a returning former member from the row, never their
    old seat."""
    cos = chips_of(r.get("cosponsors"), who_of)
    slug = r.get("sponsor_slug")
    name = r.get("sponsor_label") or r.get("sponsor") or ""
    prime = (person_chip(who_of, slug, name, r.get("sponsor_party") or "")
             if slug and (slug in who_of or name) else E(name))
    return (f'<p class="spcount">{len(cos) + 1} Sponsors</p>'
            f'<h2 class="sech spgrp">Prime Sponsor</h2><div class="chosen">{prime}</div>'
            f'<h2 class="sech spgrp">{"Co-Sponsors" if len(cos) > 1 else "Co-Sponsor"} '
            f'<span class="sechn">{len(cos)}</span></h2><div class="chosen">{" ".join(cos)}</div>'
            '<p class="src">A co-sponsor is listed once they have accepted.</p>')


def history_pane(r):
    """The History tab, only where an earlier bill has this request's title
    (build_lsrs.history_of: exactly, after case, spacing and final
    punctuation): each bill's number and year, linked, and the word its card
    says."""
    hist = r.get("history") or []
    items = "".join(
        f'<li><a href="bill/{E(str(h.get("year")))}/{E(str(h.get("id") or "").lower())}">{E(h.get("n"))} '
        f'<span class="cyear">({E(str(h.get("year")))})</span></a> '
        + C.chip(h.get("word") or "", "cstat " + str(h.get("cls") or ""), "m") + "</li>"
        for h in hist)
    return (f'<p class="src">{"A bill" if len(hist) == 1 else "Bills"} of an earlier session with '
            f'this same title:</p><ul class="lsrhist">{items}</ul>')


def tab_n(n):
    """A tab's count as app.js's tabN draws it: the badge, its brackets there
    for a screen reader; nothing for none."""
    return (f'<span class="tn"><span class="tnp"> (</span>{n:,}<span class="tnp">)</span></span>'
            if n else "")


def tabs(path, panes):
    """The strip and its panes, as a study committee's page has them (the
    same script, ssTabs, and the same stylesheet): `panes` is [(id, word,
    count, body)], the first shown. Every tab is at the page's own address
    (no slug), a place on a tab named by its #id."""
    strip = ('<div class="tabs sstabs" role="tablist" data-base="' + E(path) + '">'
             + "".join(f'<button type="button" class="tab" role="tab" id="sstab-{pid}" '
                       f'aria-controls="{pid}" data-sstab="" aria-selected="{"true" if i == 0 else "false"}">'
                       f'{E(word)}{tab_n(n)}</button>'
                       for i, (pid, word, n, _b) in enumerate(panes))
             + "</div>")
    return strip + "".join(
        f'<div class="pane sspane" role="tabpanel" id="{pid}" aria-labelledby="sstab-{pid}" tabindex="0"'
        f'{" data-on" if i == 0 else ""}><h2 class="ssph">{E(word)}</h2>{body}</div>'
        for i, (pid, word, _n, body) in enumerate(panes))


def body(r, req, who_of, path, base):
    """One request's page: a bill's, with what a request has drawn and the
    rest left quiet."""
    panes = [("summary", "Summary", 0, summary(r, req))]
    if r.get("cosponsors"):
        panes.append(("sponsors", "Sponsors", len(r["cosponsors"]) + 1, sponsors_pane(r, who_of)))
    if r.get("history"):
        panes.append(("history", "History", len(r["history"]), history_pane(r)))
    return head(r, req, who_of, path, base) + tabs(path, panes)


def write(site, base):
    """Write the pages; take away the ones no longer wanted. (written, removed)."""
    meta = json.loads((site / "meta.json").read_text(encoding="utf-8"))
    req = meta.get("requests") or {}
    out_dirs = set()
    rows = []
    if req.get("term"):
        f = site / "idx" / f"{req['term']}.json"
        rows = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
    t = S.template(site)
    who_of = sponsors(site)
    wanted = set()
    for r in rows:
        addr = r.get("address")
        if not addr or r.get("moved_to"):
            continue
        path = f"/{addr}"
        dest = site / f"{addr}.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        out_dirs.add(dest.parent)
        title = f"{r.get('n')}: {r.get('title') or ''}".strip()
        num = addr.rsplit("/", 1)[-1]
        # GR_REQUEST says whose page it is, which keeps the bill search's box on it
        # as a bill's page has it (shell.page); GR_FOLLOW names the key Follow
        # is drawn for, only for a request that can be followed: still a
        # request, not withdrawn (the card's own rule, app.js lsrCardHtml).
        # GR_REPORT names the record for Report a problem, as a study
        # committee's page does.
        g = {"GR_STATIC": True, "GR_REQUEST": num, "GR_REPORT": f"request:{num}"}
        if not r.get("withdrawn"):
            g["GR_FOLLOW"] = f"lsr:{num}"
        page = S.page(t, path=path, base=base, title=f"{title} | Granite Record",
                      og_title=r.get("n") or "", og_image="og-bill.png",
                      og_alt="Granite Record: the New Hampshire General Court's bills",
                      description=f"{r.get('n')}, a request for a bill: {r.get('title') or ''}",
                      globals=g, noscript="", cite=False,
                      skip_label="Skip to the request", nav_current="bills.html", sr_title="")
        page = page.replace('<div id="results"></div>',
                            f'<div id="results">{body(r, req, who_of, path, base)}</div>', 1)
        page = page.replace('<link rel="canonical"', ROBOTS + '\n<link rel="canonical"', 1)
        assert ROBOTS in page, f"{path}: the template has no canonical link to put noindex before"
        dest.write_text(S.clean_links(page), encoding="utf-8")
        wanted.add(dest.resolve())
    # A page for a request now a bill, retired, or no longer listed goes:
    # its address is a 301 now, or nothing.
    removed = 0
    for d in out_dirs | {site / "request"}:
        for old in (d.glob("*.html") if d.is_dir() else []):
            if old.resolve() not in wanted:
                old.unlink()
                removed += 1
    return len(wanted), removed, sum(1 for r in rows if r.get("moved_to"))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    n, gone, moved = write(Path(a.site), a.base)
    print(f"  {n} request pages (noindex, not in the sitemap)"
          + (f"; {moved} forward to a bill or a sponsor's page" if moved else "")
          + (f"; {gone} no longer wanted taken away" if gone else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
