#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.10
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
import structured as LD

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
    # THE SEAT ONCE. display_full already carries it -- "Rep. Aboul Khan (R -
    # Rock 30)" -- and the seat was appended again, so all 406 of these read
    # "(R - Rock 30) Rock 30." in a search result until 13 September. The
    # places come straight after the name, because they are what a person
    # searching a representative's name is usually checking.
    who = m.get("display_full") or m.get("display") or m.get("name") or ""
    if not (m.get("display_full") or "") and m.get("district_label"):
        who = f"{who} ({m['district_label']})"
    body = "Senate" if m.get("chamber") == "S" else "House of Representatives"
    # Ward 2 before Ward 10, which the roster's own order does not give.
    towns = sorted(m.get("towns") or [],
                   key=lambda t: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", t)])
    if towns:
        # "and 1 more" hides a name in the space it takes to say so.
        shown = towns if len(towns) <= 7 else towns[:6]
        more = len(towns) - len(shown)
        places = (", ".join(shown[:-1]) + " and " + shown[-1] if len(shown) > 1 and not more
                  else ", ".join(shown) + (f" and {more} more" if more else ""))
        lead = f"{who} represents {places} in the New Hampshire {body}."
    else:
        lead = f"{who}, New Hampshire {body}."
    text = (f"{lead} Bills sponsored and every recorded roll call vote, from the "
            "General Court's own records.")
    # A clip at a word, not a slice: [:300] would cut a word in half the day a
    # member represented enough towns to reach it.
    return S.clip(text, 300)


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
            # Name, office, chamber, party, district. Not email or telephone:
            # structured.py says why.
            jsonld=LD.person(m, a.base, S.canon(path)),
            globals={"GR_MEMBER": str(m.get("id", "")), "GR_STANDALONE": True},
            noscript=noscript(m), skip_label="Skip to this member",
            # Without this the template's marker stays on Bills, and all 406
            # member pages told a screen reader they were Bills.
            nav_current="legislators.html",
            # And the template's hidden "New Hampshire bills" <h1> went, as
            # the first heading, before the member's own -- which the page
            # draws (and its noscript carries), so the hidden one is removed
            # rather than renamed: two headings saying one name is worse.
            sr_title=""),
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
