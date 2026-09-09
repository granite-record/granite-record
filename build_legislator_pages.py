#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.6
"""
An address for every sitting legislator, and the sitemap entries for them.

    python3 build_legislator_pages.py --site site

/legislator/joseph-guthrie-rock-15.html is this site's search page with one
member open -- the same app.js, the same cards, the same roll call table as a
bill's page, drawing site/legislators/<id>.json.

Until 7 September it was a page rendered here in Python: its own markup, its own
stylesheet, its own vote table, and no site header at all. It looked unlike
every other page on the site because it was written by different code, which is
the same problem the bill pages had and was fixed the same way.

WHAT A MEMBER'S PAGE ANSWERS

Which bills they put their name to, prime and co-sponsored, filterable by term
and outcome; every roll call they are recorded in, filterable by how they voted;
the district they sit for and the towns in it, ward by ward where a city is
split between members.

Writes site/legislator/<slug>.html and appends them to sitemap.xml.
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path

import shell as S

E = S.E


def person_slug(m):
    """A stable, readable address: "joseph-guthrie-rock-15".

    Name plus seat, because two members share a name often enough to matter --
    Sen. Pat Long and Rep. Patrick Long sit at the same time -- and a bare name
    would give one of them the other's page.
    """
    name = m.get("display_plain") or m.get("name") or ""
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
        name = f"{first} {last}"
    name = re.sub(r"^(Rep\.|Sen\.)\s*", "", name).strip()
    seat = (m.get("district_label") or "").strip()
    if not seat:
        seat = f"{m.get('chamber','')}-{m.get('district','')}"
    raw = f"{name} {seat}"
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", raw.lower())).strip("-")


def describe(m):
    """The sentence a search engine shows under the link."""
    who = m.get("display_full") or m.get("display") or m.get("name") or ""
    seat = m.get("district_label") or ""
    bits = [who]
    if seat:
        bits.append(f"{seat}.")
    towns = m.get("towns") or []
    if towns:
        bits.append("Represents " + ", ".join(towns[:6])
                    + ("." if len(towns) <= 6 else " and others."))
    bits.append("Sponsored bills and every recorded roll call vote, from the "
                "New Hampshire General Court's own records.")
    return re.sub(r"\s+", " ", " ".join(bits)).strip()[:300]


def noscript(m):
    """What a reader without JavaScript is told, and where to go instead."""
    who = E(m.get("display_full") or m.get("name") or "")
    towns = m.get("towns") or []
    return (
        '<noscript><div class="wrap" style="max-width:70ch;padding:26px 20px">'
        f"<h1>{who}</h1>"
        + (f"<p>Represents {E(', '.join(towns))}.</p>" if towns else "")
        + "<p>This page draws the record — bills sponsored and every recorded "
          "roll call vote — in the browser, so it needs JavaScript. Everything "
          "it shows comes from the file linked below, which needs none.</p>"
          f'<ul><li><a href="/legislators/{E(str(m.get("id","")))}.json">this '
          "page's data as JSON</a></li>"
        + (f'<li><a href="{E(m["url"])}" rel="noopener">this member on '
           "gencourt</a></li>" if m.get("url") else "")
        + '</ul><p><a href="/legislators.html">All legislators</a></p>'
          "</div></noscript>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site = Path(a.site)
    legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
    out = site / "legislator"
    out.mkdir(parents=True, exist_ok=True)
    t = S.template(site)

    urls, written = [], 0
    for m in legs:
        slug = m.get("slug") or person_slug(m)
        path = f"/legislator/{slug}.html"
        who = m.get("display_full") or m.get("display") or m.get("name") or ""
        (out / f"{slug}.html").write_text(S.page(
            t, path=path, base=a.base,
            title=f"{who} | Granite Record",
            og_title=f"{who} — New Hampshire General Court",
            description=describe(m),
            globals={"GR_MEMBER": str(m.get("id", "")), "GR_STANDALONE": True},
            noscript=noscript(m), skip_label="Skip to this member"),
            encoding="utf-8")
        urls.append(a.base + S.canon(path))
        written += 1

    assert written or not legs, (
        "no legislator page was written, and legislators.json holds "
        f"{len(legs)}. That is a run that failed, not a roster that emptied.")

    # sitemap.xml is written by build_bill_pages.py, which runs first. Appended
    # rather than replaced: rewriting it here would drop 4,230 bill URLs.
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{E(u)}</loc></url>\n" for u in urls
                      if E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"{len(add.splitlines())} added to sitemap.xml")
        else:
            print("sitemap already lists legislator pages; left alone")

    total = sum(p.stat().st_size for p in out.glob("*.html"))
    print(f"{written} legislator pages -> {out}/  ({total/1e6:.1f} MB)")
    print("\nEach page is bills.html with one member open, drawn by app.js "
          "from the\nsame JSON the search page reads. Somebody searching a "
          "member's name finds\ntheir voting record, and it is the same record "
          "the rest of the site draws.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
