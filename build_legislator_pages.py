#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.14
"""
An address for every sitting legislator, and the sitemap entries for them.

    python3 build_legislator_pages.py --site site

/legislator/joseph-guthrie-rock-15.html is this site's search page with one
member open -- the same app.js, the same cards, the same roll call table as a
bill's page, drawing site/legislators/<id>.json.

It was once a page rendered here in Python: its own markup, its own
stylesheet, its own vote table, and no site header at all. It looked unlike
every other page on the site because it was written by different code, which is
the same problem the bill pages had and was fixed the same way.

WHAT A MEMBER'S PAGE ANSWERS

Which bills they put their name to, prime and co-sponsored, filterable by term
and outcome; every roll call they are recorded in, filterable by how they voted;
the district they sit for and the towns in it, ward by ward where a city is
split between members.

Writes site/legislator/<slug>.html and appends them to sitemap.xml. Each page
names the member's feed in its head, on the test build_feeds writes it on.
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
    # "(R - Rock 30) Rock 30." in a search result. The places come straight
    # after the name, because they are what a person searching a
    # representative's name is usually checking.
    who = m.get("display_full") or m.get("display") or m.get("name") or ""
    if not (m.get("display_full") or "") and m.get("district_label"):
        who = f"{who} ({m['district_label']})"
    body = "Senate" if m.get("chamber") == "S" else "House of Representatives"
    # Ward 2 before Ward 10, which the roster's own order does not give.
    towns = sorted(m.get("towns") or [],
                   key=lambda t: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", t)])
    # PAST TENSE FOR SOMEBODY WHO NO LONGER SERVES, and no towns: the roster
    # carries none for them, and the town map is today's, so "represents" would
    # be wrong twice over.
    #
    # The years are the record's rather than the career's -- roll calls here
    # begin in 1999, so somebody first sworn in before that appears from the
    # year the evidence starts. List the terms the record covers and leave the
    # wording plain: the case is rare enough that a sentence of hedging costs
    # the reader more than the imprecision does.
    if m.get("former"):
        yrs = _served_years(m)
        lead = (f"{who} served in the New Hampshire {body}"
                + (f", {yrs}." if yrs else "."))
    elif towns:
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


def _served_years(m):
    """"2013 to 2026", the span of the RECORD this site holds for a member.

    The span of the RECORD, which is not always the span of the service: roll
    calls here begin in 1999 and bills in 1989, so somebody who took their seat
    in 1985 and left in 2002 appears from 1999. The wording stays plain: the
    case is rare enough that a sentence of hedging costs the reader more than
    the imprecision does. The one place it is still worth avoiding is
    structured data, which asserts a startDate as fact with no prose around
    it; structured.person says so.

    One year where both ends fall in it, because "2026 to 2026" reads as a
    fault rather than as a fact.
    """
    s = m.get("served") or {}
    a, b = str(s.get("first") or "")[-4:], str(s.get("last") or "")[-4:]
    if not (a.isdigit() and b.isdigit()):
        return ""
    return a if a == b else f"{a} to {b}"


def heading(m):
    """The member's name as their own page heads it, and as its title and
    link card give it: "Former Rep. Michael Gunski (R - Hills 6)" for somebody
    who has left.

    THE WORD JOINS THE HONORIFIC, as the person settled it in September: a
    legislator who has left is written "Former Rep. David Smith", in the name
    itself and never as a chip, badge or pill beside it, on their own page and
    in search results -- and nowhere else, so a roll call, a sponsor list or a
    committee roster names them exactly as it names a sitting member, and
    nothing says why they left. The honorific is the record's own, the office
    they last held under it. A name with no honorific ("Member #377204") is
    left as it is, and the page's line under it keeps saying "Former member".
    app.js's formerName heads the page the same way.
    """
    who = m.get("display_full") or m.get("display") or m.get("name") or ""
    return f"Former {who}" if m.get("former") and re.match(r"(Rep|Sen)\. ", who) else who


def noscript(m):
    """What a reader without JavaScript is told, and where to go instead."""
    who = E(heading(m))
    towns = m.get("towns") or []
    yrs = _served_years(m) if m.get("former") else ""
    # The heading says "Former" where it can, so the line under it gives only
    # the years, as the page app.js draws does.
    titled = heading(m).startswith("Former ")
    return (
        '<noscript><div class="wrap" style="max-width:70ch;padding:26px 20px">'
        f"<h1>{who}</h1>"
        + ((f"<p>{E('On record ' + yrs + '. ') if yrs else ''}This page is their "
            "record in the New Hampshire General Court; it is not a current "
            "directory entry.</p>" if titled else
            f"<p>Former member of the New Hampshire General Court"
            f"{E(', ' + yrs) if yrs else ''}. This page is their record; it is "
            "not a current directory entry.</p>") if m.get("former") else "")
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
    # AND THE MEMBERS WHO LEFT MID-TERM. build_site_v2.former_roster writes
    # them to their own file rather than into the roster, because a dozen
    # builders read the roster to mean "who serves now". They get a page by
    # the same code as everyone else -- same shell, same slug, same JSON --
    # so a reader who follows a sponsor's name from a bill they filed this
    # term arrives at their voting record instead of at plain text.
    former = json.loads((site / "former.json").read_text(encoding="utf-8")) \
        if (site / "former.json").exists() else []
    out = site / "legislator"
    out.mkdir(parents=True, exist_ok=True)
    t = S.template(site)

    urls, written, n_former = [], 0, 0
    for m in [*legs, *former]:
        slug = m.get("slug") or person_slug(m)
        path = f"/legislator/{slug}.html"
        # "Former Rep. ..." for a member who has left: heading() says why.
        who = heading(m)
        mid = str(m.get("id") or "")
        # THE MEMBER'S FEED, WHERE ONE IS WRITTEN: their recorded votes and the
        # bills they sponsored. build_feeds once wrote one for each of the 406
        # and no page named any, so the only way to one was
        # already knowing its address. A feed reader given this page finds it
        # here, as it finds a bill's. build_feeds runs after this step, so
        # there is no file to look for: shell.member_followable is the test
        # both use. Titled as the feed titles itself.
        named = m.get("display") or m.get("name") or f"Member #{mid}"
        feed = (f'<link rel="alternate" type="application/rss+xml" '
                f'title="{E(named)} — Granite Record" '
                f'href="/feed/legislator/{E(mid)}.xml">'
                if S.member_followable(m) else "")
        (out / f"{slug}.html").write_text(S.page(
            t, path=path, base=a.base,
            title=f"{who} | Granite Record",
            # The member's name and seat and nothing after it: "-- New Hampshire
            # General Court" in a link card read as the General Court's own page.
            og_title=who, og_image="og-legislator.png",
            og_alt="Granite Record: legislators and their voting records",
            description=describe(m), alternate=feed,
            # Name, office, chamber, party, district. Not email or telephone:
            # structured.py says why.
            jsonld=LD.person(m, a.base, S.canon(path)),
            # GR_FORMER tells app.js to say, on this page and nowhere else,
            # that the member no longer serves -- and to leave out the contact
            # details, which belonged to the office. It says nothing about why
            # they left, and nothing anywhere else on the site marks them:
            # in a roll call or a sponsor list they are named exactly as a
            # sitting member is.
            globals={"GR_MEMBER": str(m.get("id", "")), "GR_STANDALONE": True,
                     **({"GR_FORMER": True} if m.get("former") else {})},
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
        n_former += bool(m.get("former"))

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
    print(f"{written} legislator pages -> {out}/  ({total/1e6:.1f} MB)"
          + (f"; {n_former} of them members who left mid-term, whose votes and "
             "sponsorships were plain text before" if n_former else ""))
    print("\nEach page is bills.html with one member open, drawn by app.js "
          "from the\nsame JSON the search page reads. Somebody searching a "
          "member's name finds\ntheir voting record, and it is the same record "
          "the rest of the site draws.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
