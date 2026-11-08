#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-08.1
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
from components import pchip

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


def body(r, req, who):
    """One request's page: what a request has, and nothing it has not."""
    chip = pchip(who) if who else E(r.get("sponsor_label") or r.get("sponsor") or "")
    state = ("Withdrawn before it became a bill." if r.get("withdrawn")
             else E(r.get("status") or ""))
    return ('<div class="static-rec shown" id="request-rec">'
            f'<p class="sx-name">{E(req.get("label") or "Bill Request")}</p>'
            f"<h1>{E(r.get('n') or '')}</h1>"
            f'<p class="sx-title">{E(r.get("title") or "")}</p>'
            '<ul class="sx-facts">'
            f"<li><b>Prime sponsor:</b> {chip}</li>"
            + (f"<li><b>Kind:</b> {E(r['body_label'])}</li>" if r.get("body_label") else "")
            + f"<li><b>Status:</b> {state}</li></ul>"
            f'<p class="lsrnote">{explain(r.get("year") or req.get("year"))}</p>'
            f'<p><a href="bills?term={E(req["term"])}">All {E(req.get("label") or "requests")}</a></p>'
            "</div>")


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
        page = S.page(t, path=path, base=base, title=f"{title} | Granite Record",
                      og_title=r.get("n") or "", og_image="og-bill.png",
                      og_alt="Granite Record: the New Hampshire General Court's bills",
                      description=f"{r.get('n')}, a request for a bill: {r.get('title') or ''}",
                      globals={"GR_STATIC": True}, noscript="",
                      skip_label="Skip to the request", nav_current="bills.html", sr_title="")
        page = page.replace('<div id="results"></div>',
                            f'<div id="results">{body(r, req, who_of.get(r.get("sponsor_slug")))}</div>', 1)
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
