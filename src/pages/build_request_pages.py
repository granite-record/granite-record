#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-08.4
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

import shell as S
import components as C

E = S.E
# Not indexed (Alice, 8 November 2026), as the provisional members-elect pages.
ROBOTS = '<meta name="robots" content="noindex,follow">'


def explain(year):
    """The requests' explanation, the bill search's own words
    (fix/search-polish, 8 November 2026)."""
    return ("<b>Requests, not bills yet.</b> Each is a member&rsquo;s request to have a bill "
            "drafted: a title and a sponsor, nothing more, until it is filed as a numbered "
            f"{E(str(year))} bill. Some are withdrawn first.")


def sponsors(site):
    """{slug: {"party_code", "display_full", "slug"}} for the chip: the roster's
    members and the provisional members-elect pages."""
    out = {}
    for name in ("legislators.json", "former.json"):
        f = site / name
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
    carries, "Filed as a request"."""
    return "Withdrawn" if r.get("withdrawn") else (r.get("status") or "")


def chips_of(people, who_of):
    """The chips of the people a row names: [{"label", "slug"}, ...]."""
    out = []
    for c in people or []:
        m = who_of.get(c.get("slug")) or {"display_full": c.get("label"), "slug": c.get("slug") or ""}
        out.append(C.pchip(m))
    return out


def rail_of(r):
    """A request's own rail, three stops (Alice, 12 November 2026, from a phone
    screenshot where the bill's six stops ran into one another: "a separate
    rail for the requests with Requested, Filed meaning the text is publicly
    available, and Introduced"): Requested, reached while the request exists
    (a cross where it was withdrawn); Filed, reached once the bill's text is
    public; Introduced, which a request reaches by becoming a numbered bill,
    when its address forwards to the bill's page and the bill's own rail
    takes over -- so it is never reached here. Same rail_html, same look. No
    day is shown: the list gives none.

    WHAT SAYS "FILED". Nothing on disk yet: the request list (the list build_lsrs reads)
    carries a number, kind, title, sponsor and a withdrawn flag, and no bill
    of the session has been published (data/bills.json has no 2027-2028).
    So the stop reads the row's "filed" -- true, or the day the text became
    public ("YYYY-MM-DD"), which build_lsrs.rows_from carries over from the
    source row once the source gives it -- and is drawn not reached until
    then. A withdrawn request never reaches it."""
    gone = bool(r.get("withdrawn"))
    filed = r.get("filed") and not gone
    day = r["filed"] if filed and isinstance(r["filed"], str) and r["filed"][:1].isdigit() else ""
    stops = [
        {"stop": "Requested", "mark": "x" if gone else "p", "date": "", "short": "",
         "say": "Withdrawn" if gone else "Filed as a request"},
        {"stop": "Filed", "mark": "p" if filed else "-", "date": day, "short": "",
         "say": "Text public" if filed else ""},
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
    sponsor = who_of.get(r.get("sponsor_slug"))
    name = r.get("sponsor_label") or r.get("sponsor") or ""
    facts = []
    if sponsor:
        facts.append(["Prime Sponsor", C.pchip(sponsor)])
    elif name:
        facts.append(["Prime Sponsor", E(name)])
    cos = chips_of(r.get("cosponsors"), who_of)
    if cos:
        facts.append(["Co-Sponsors" if len(cos) > 1 else "Co-Sponsor", " ".join(cos)])
    if r.get("body_label"):
        facts.append(["Kind", E(r["body_label"])])
    cite = S.cite_block(path, f"{r.get('n')}: {r.get('title') or ''} | Granite Record", base,
                        S.cited())
    assert cite.endswith("</div>"), "the citation block no longer ends its row"
    chips = C.WORDBOOK.get("chips", {}).get("chip", {})
    return C.record_head({
        "trail": [["Bills", "bills"],
                  [req.get("label") or "Bill Requests", f"bills?term={req['term']}"],
                  [r.get("n") or "", ""]],
        "title": E(r.get("n") or ""),
        "chip": C.chip(word, "cstat " + chips.get(word, ""), "m"),
        "line": f'<span translate="no">{E(r.get("title") or "")}</span>',
        "facts": facts, "rail": rail_of(r),
        "actions": cite[:-len("</div>")] + SHARE + "</div>",
        "kind": "bill"})


def summary(r, req):
    """The one tab, Summary: the requests' explanation, and the facts of this
    one. The other tabs a bill has are not here until the bill is."""
    state = state_of(r)
    return (C.section("About Requests",
                      f'<p class="lsrnote">{explain(r.get("year") or req.get("year"))}</p>', "about")
            + C.section("The Request", f'<p><b>Status:</b> {E(state)}</p>', "request"))


def tabs(path, pane):
    """The strip and its pane, as a study committee's page has them (the
    same script, ssTabs, and the same stylesheet): one tab, shown."""
    return ('<div class="tabs sstabs" role="tablist" data-base="' + E(path) + '">'
            '<button type="button" class="tab" role="tab" id="sstab-summary" '
            'aria-controls="summary" data-sstab="" aria-selected="true">Summary</button></div>'
            '<div class="pane sspane" role="tabpanel" id="summary" '
            'aria-labelledby="sstab-summary" tabindex="0" data-on>'
            f'<h2 class="ssph">Summary</h2>{pane}</div>')


def body(r, req, who_of, path, base):
    """One request's page: a bill's, with what a request has drawn and the
    rest left quiet."""
    return head(r, req, who_of, path, base) + tabs(path, summary(r, req))


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
