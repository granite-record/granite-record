#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-08.18
"""
A page for each bill request of the session the site lists, so a request can
be shared by its own address rather than by the search.

    python3 src/pages/build_request_pages.py --site site

Alice, 8 November 2026. Each page is /request/<number> (build_lsrs.py's
"address"); noindex and out of the sitemap, as the provisional members-elect
pages are; it shows what a request has -- its number, title, prime sponsor
(the chip as everywhere), what kind of request it is and where it stands --
under a bill's tab strip (16 November 2026), its Summary saying what the
record says of its text, and the requests' own explanation. Nothing here
knows how a state numbers its requests or where they come from:
build_lsrs.py, the source's reader, gives each row its "address" and, once
the request is a bill or filing is complete, its "moved_to".

WHICH ARE WRITTEN. Every request with no "moved_to": filed, or withdrawn (a
withdrawn request keeps its page, as a withdrawn bill does). One with
"moved_to" has no page: its address answers with a 301 there, which
build_pages writes into _redirects (moved_requests). So no night leaves a
page and a redirect at one address -- and a page an earlier night wrote for a
request that has since moved is taken away here, as is one for a request no
longer listed.

A REQUEST STAYS A REQUEST UNTIL IT IS INTRODUCED (the owner, 17 November
2026; build_lsrs): filed as a numbered bill, its page stays, saying the bill
it was filed as (the row's "introduced" and "bill_at"), its Follow the
bill's, where its follow has moved; and once the night has read its text
("text_on_file"), a Bill Text tab shows it (text_pane), read by machine from
the General Court's PDF, which it links. It forwards only once the bill is
introduced.
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
# The site's word for a topic nobody could place (topics.MISC), never printed.
MISC = "Miscellaneous"


def explain(year, abbr=None):
    """The requests' explanation, the bill search's own words
    (fix/search-polish, 8 November 2026), and what the number's abbreviation
    stands for (the owner, 13 November 2026), said in words beside the
    number's popover (term_html): `abbr` is meta.requests's, a map of an
    abbreviation to its words. A request's card on the bill search says the
    same on its Summary, in these words (app.js lsrAbout; the owner, 17
    November 2026)."""
    said = "".join(f" {E(k)} stands for {E(v)}." for k, v in (abbr or {}).items())
    return ("<b>Requests, not bills yet.</b> Each is a member&rsquo;s request to have a bill "
            "drafted: a title and a sponsor, nothing more, until it is filed as a numbered "
            f"{E(str(year))} bill. Some are withdrawn first." + said)


def term_html(text, abbr):
    """`text` escaped, its first word marked for the site's term popover where
    `abbr` names it (components.term_mark): glossary.json's entry, its name in
    full and what it means, on a tap, a held hover or keyboard focus -- the
    mechanism the FN of a bill's number uses (the owner, 15 November 2026:
    the request's tooltip should use "the same mechanism as the other tooltip
    definitions like -FN"; until then an <abbr> whose title only a mouse could
    read). components.js arms the first on the page, so the number in the
    head carries it and the trail's stays plain, as a bill page's does."""
    first, sep, rest = str(text or "").partition(" ")
    if first and first in (abbr or {}):
        return C.term_mark(first, first) + E(sep + rest)
    return E(str(text or ""))


def sponsors(site):
    """{slug: {"party_code", "display_full", "slug"}} for the chip: the sitting
    roster's members (legislators.json) and the provisional members-elect pages
    (elect_pages.json). former.json is deliberately NOT read: a former member
    holds no seat, and their display_full names the old one, which others hold
    now (the review of 13 November 2026); person_chip draws them from the
    request's own row instead.

    A member-elect's chip carries their title until the day they take office,
    "Rep. “Elect” Colin Mitchell (R)" (the owner, 17 November 2026;
    build_lsrs.elect_title and elect_window), as the request's row labels them
    for its card; a sitting member's is the roster's, as it was."""
    import build_lsrs
    out = {}
    f = site / "legislators.json"
    for m in (json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []):
        if m.get("slug"):
            out[m["slug"]] = {"party_code": m.get("party"), "slug": m["slug"],
                              "display_full": m.get("display_full") or m.get("display")
                              or m.get("name")}
    f = site / "elect_pages.json"
    titled = build_lsrs.elect_window(site)
    for p in (json.loads(f.read_text(encoding="utf-8")).get("pages") or [] if f.is_file() else []):
        title = f"{build_lsrs.elect_title(p.get('chamber'))} " if titled else ""
        out.setdefault(p["slug"], {"party_code": p.get("party"), "slug": p["slug"],
                                   "display_full": title + (f"{p['name']} ({p['party']})"
                                                            if p.get("party") else p["name"])})
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
    """A request's own rail: the stops its row carries (`rail`, which the
    source's reader writes -- build_lsrs.rail_stops says what each stop
    means and when it carries a day), drawn by the bill's rail component, as
    the request's card draws them (the owner, 15 November 2026: "adding the
    rail on the card"). Same rail_html, same look, one set of stops for the
    two. A row with none draws none."""
    return C.rail_html(r.get("rail") or [])


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
    # THE BILL IT WAS FILED AS (the owner, 17 November 2026: "Drafted and filed
    # as HB123 sounds fine"), linked to the bill's page, while it is still a
    # request: once introduced it forwards there.
    if r.get("introduced"):
        num = E(r["introduced"])
        facts.append(["Filed As", f'<a href="{E(r["bill_at"])}">{num}</a>' if r.get("bill_at") else num])
    # THE TOPIC AS A BILL'S PAGE GIVES ITS SUBJECT (the owner, 14 November
    # 2026: "remove the topic from title label"): the name alone, under the
    # bill page's label, and none for the Miscellaneous of a request
    # request_topics could not place, which the Topic filter lists and a page
    # does not print, as a bill's page does not print the topic model's.
    if r.get("topic") and r["topic"] != MISC:
        facts.append(["Subject", E(r["topic"])])
    cite = S.cite_block(path, f"{r.get('n')}: {r.get('title') or ''} | Granite Record", base,
                        S.cited())
    assert cite.endswith("</div>"), "the citation block no longer ends its row"
    chips = C.WORDBOOK.get("chips", {}).get("request", {})
    page = C.record_head({
        "trail": [["Bills", "bills"],
                  [req.get("label") or "Bill Requests", f"bills?term={req['term']}"],
                  [r.get("n") or "", ""]],
        "title": term_html(r.get("n"), req.get("abbr")),
        "chip": C.chip(word, "cstat " + chips.get(word, ""), "m"),
        "line": f'<span translate="no">{E(r.get("title") or "")}</span>',
        "facts": facts, "rail": rail_of(r),
        "actions": cite[:-len("</div>")] + SHARE + "</div>",
        "kind": "bill"})
    # The trail names the request by its number, plain text, as record_head
    # writes it: the head's number carries the term's popover.
    return page


def text_note(r, year):
    """What the Summary says of the request's text, by what its row says
    (the owner, 16 November 2026: "the summary should explain that the bill
    text is not yet available as it is still being drafted so that the
    format doesn't look cut off"): a request still requested is being
    drafted, and its text is public once it is filed as a numbered bill (the
    rail's Filed, "Text public"); a withdrawn one was withdrawn before it was
    filed, as its rail's crossed Filed says; one already filed or introduced
    says nothing of the kind ("" -- its Summary is what it was)."""
    if r.get("withdrawn"):
        return ("<b>Withdrawn.</b> This request was withdrawn before it was filed as a bill, "
                "so it has no text.")
    # FILED, ITS TEXT NOT READ HERE YET (17 November 2026): the night reads it
    # a few a night, and until then the Summary says where it is.
    if (r.get("filed") or r.get("introduced")) and not r.get("text_on_file"):
        pdf = (f' <a href="{E(r["text_pdf"])}" target="_blank" rel="noopener">The PDF at the '
               "General Court</a>.") if r.get("text_pdf") else ""
        return ("<b>Filed.</b> Its text is public, and is added here once this site has read it."
                + pdf)
    if r.get("filed") or r.get("introduced"):
        return ""
    return ("<b>Not public yet.</b> This request is still being drafted into a bill. Its text "
            f"will be public when it is filed as a numbered {E(str(year))} bill.")


def text_pane(r):
    """THE BILL TEXT TAB, ONCE THE TEXT IS IN (the owner, 17 November 2026: "a
    link that says View the text that shows the granite record tab once we've
    imported the text"): what the night read off the PDF the General Court's
    request list links (build_lsrs.request_text), in the bill page's block for
    a text (.vtext), said to be read by machine, with the PDF itself linked."""
    import build_lsrs
    num = str(r.get("address") or "").rsplit("/", 1)[-1]
    text = build_lsrs.request_text(num)
    pdf = (f'<p class="src"><a href="{E(r["text_pdf"])}" target="_blank" rel="noopener">The PDF '
           "at the General Court</a></p>") if r.get("text_pdf") else ""
    return ('<p class="btwhat">The text as the General Court publishes it with this request, read '
            "by machine from its PDF: the PDF is the document.</p>"
            f'<pre class="vtext" translate="no">{E(text)}</pre>{pdf}')


def summary(r, req):
    """The Summary tab: what the record says of the request's text
    (text_note), as a bill's Summary leads with what its text says, and the
    requests' explanation. The facts of this one are the head's (the status
    chip, the field grid): not said twice (the owner, 14 November 2026: "just
    let the pages speak for themselves")."""
    year = r.get("year") or req.get("year")
    note = text_note(r, year)
    return ((C.section("Bill Text", f"<p>{note}</p>", "text") if note else "")
            + C.section("About Requests", f'<p class="lsrnote">{explain(year, req.get("abbr"))}</p>',
                        "about"))


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


def tabs(rid, path, panes):
    """THE STRIP A BILL'S PAGE HAS, AND ITS PANES (the owner, 16 November
    2026: a request's page "should at least show the summary tab"):
    the record's strip, components.record_tabs, as app.js's renderDetail
    draws a bill's -- the same component, its tabs keyed as a bill's (0
    Summary, 4 Sponsors, 7 History, as the request's card keys them) -- and
    drawn for the Summary alone too, which until then drew no strip and left
    the page ending under the rail. `panes` is [(key, word, count, body)],
    the first chosen. The page is built ahead with every pane on it, so the
    strip carries the page's address (`base`) for app.js's ssTabs, which
    turns the panes as on a study committee's page; every tab is at the
    page's own address, a place on one named by its pane's #id. WITHOUT A
    SCRIPT (app.css): the strip is hidden and every pane is on the page in
    turn under its own heading, which the script hides for a screen reader's
    alone. A pane's id is pane_<id>_<key>, never "summary": bills.html
    carries <p id="summary">, and ssPaneOf finds a pane by its id."""
    strip = C.record_tabs(rid, [[k, word, n] for k, word, n, _b in panes], panes[0][0], path)
    return strip + "".join(
        f'<div class="pane sspane" role="tabpanel" id="pane_{E(rid)}_{k}" aria-labelledby="tab_{E(rid)}_{k}" '
        f'tabindex="0" data-t="{k}"{" data-on" if i == 0 else ""}><h2 class="ssph">{E(word)}</h2>{body}</div>'
        for i, (k, word, _n, body) in enumerate(panes))


def body(r, req, who_of, path, base):
    """One request's page: a bill's, with what a request has drawn and the
    rest left quiet."""
    panes = [("0", "Summary", 0, summary(r, req))]
    # Second, as on a bill's page; keyed 6 as a bill's Bill Text tab is.
    if r.get("text_on_file"):
        panes.append(("6", "Bill Text", 0, text_pane(r)))
    if r.get("cosponsors"):
        panes.append(("4", "Sponsors", len(r["cosponsors"]) + 1, sponsors_pane(r, who_of)))
    if r.get("history"):
        panes.append(("7", "History", len(r["history"]), history_pane(r)))
    return head(r, req, who_of, path, base) + tabs(r.get("id") or "", path, panes)


def text_address(r):
    """The address of a request's Bill Text tab on its own page, its pane
    named by the place the strip opens on (app.js's ssWanted reads "#<pane
    id>"): "/<address>#pane_<id>_6", from the row's own address and id --
    "" for a request whose text is not read, which has no such tab. The
    follow email's "View the text" (build_feeds, follow_changes.ending; the
    owner, 17 November 2026). Once the request forwards to its bill, the page
    there opens as it does."""
    if not (r.get("text_on_file") and r.get("address") and r.get("id")):
        return ""
    return f"/{r['address']}#pane_{r['id']}_6"


def follow_key(r, num):
    """What the page's Follow follows: the request ("lsr:2027-0001") until it
    is filed as a bill, and from then the bill it was filed as, where its
    follow has moved (build_feeds, BILL REQUESTS) -- "bill:2027/HB45", the
    key of the bill's page the row gives (bill_at, "bill/2027/hb45")."""
    m = re.fullmatch(r"bill/(\d{4})/([a-z]+\d+)", str(r.get("bill_at") or ""))
    return f"bill:{m.group(1)}/{m.group(2).upper()}" if m else f"lsr:{num}"


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
            g["GR_FOLLOW"] = follow_key(r, num)
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
