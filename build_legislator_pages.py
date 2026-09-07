#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.4
"""
One page per sitting legislator, that a search engine can find.

    python3 build_legislator_pages.py --site site --base https://graniterecord.org

Reads site/legislators.json and site/legislators/<id>.json, both written by
build_site_v2.py. Needs no network and writes only into the site folder.

WHY THESE EXIST

legislators.html is a search page: everything on it arrives by JavaScript, so
there is nothing at a fixed address for a crawler to index or for anyone to
link to. Somebody searching a representative's name finds the General Court's
own page, a campaign site, and a news archive -- and not their voting record.

These are the same thing bill pages are: plain HTML at a stable address, no
JavaScript needed, one per member.

CURRENT MEMBERS ONLY

A member who has left keeps their votes and their sponsorships wherever those
appear -- a roll call from 2025 names whoever voted in 2025, and always will.
What they do not get is a page of their own, because a page implies a present
tense: this is who represents you, here is how to contact them. For somebody
who left two years ago that is not a record, it is a misdirection.

The votes stay. The page does not. When earlier terms are loaded, the right
answer is a page per member PER TERM, which is a different thing again and can
wait until there are earlier terms to put in it.

ADDRESSES

    /legislator/jodi-nelson-rock-13.html

Name and district, because two members share a name often enough and the
district is the thing that makes one of them yours. Anyone who has left keeps
no address at all, so a link never rots into someone else's page.
"""

import argparse
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

WS = re.compile(r"\s+")


def E(x):
    return html.escape(str(x or ""), quote=True)


def slug(*parts):
    s = " ".join(str(p) for p in parts if p)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s)


def person_slug(m):
    """jodi-nelson-rock-13: the name, then what distinguishes one from another."""
    name = m.get("display_plain") or m.get("name", "")
    name = re.sub(r"^(?:Rep|Sen)\.\s+", "", name)
    if "," in name:                       # "Nelson, Jodi" -> "Jodi Nelson"
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    # Both chambers' districts are geographic -- Senate district 14 is Auburn,
    # Hudson and Londonderry. The difference is how they are NUMBERED. House
    # districts are numbered within a county, so Rockingham 13 and Hillsborough
    # 13 are two different districts and the county is what tells them apart.
    # Senate districts are numbered once across the state, 1 to 24, so the
    # number alone is already unique and a county would only add noise.
    senate = str(m.get("chamber", "")).upper().startswith("S")
    where = "sd" if senate else (m.get("county_abbr") or m.get("county") or "")
    return m.get("slug") or slug(name, where, m.get("district"))


VOTE_WORDS = {"Yea": "yes", "Nay": "no", "Excused": "excused",
              "Not Voting": "did not vote", "Presiding": "presiding",
              "Absent": "absent"}


def sponsored_section(detail, base):
    """The bills this member put their name to, prime sponsorship first.

    The page's meta description has promised "sponsored bills" since it was
    written and the file did not carry them, so a search engine was being told
    about a section that did not exist. 8,259 sponsorships across 406 members,
    1,352 of them as prime sponsor.

    Prime first because that is the one a member is asked about: a bill with
    fifteen co-sponsors is fifteen people's bill in name and one person's in
    practice.
    """
    rows = detail.get("sponsored") or []
    if not rows:
        return ""
    prime = [r for r in rows if r.get("prime")]
    rest = [r for r in rows if not r.get("prime")]

    def table(items):
        return ('<table class="votes"><thead><tr><th>Bill</th><th>Title</th>'
                "</tr></thead><tbody>"
                + "".join(
                    f'<tr><th scope="row"><a href="../bill/{r.get("year","")}/'
                    f'{r["bill"].lower()}.html">{E(r.get("n") or r["bill"])}</a>'
                    f'</th><td>{E(r.get("title") or "")}</td></tr>'
                    for r in items)
                + "</tbody></table>")

    out = [f"<h2>Bills sponsored</h2>"]
    out.append(f'<p class="meta">{len(rows):,} bill'
               f'{"" if len(rows) == 1 else "s"}, '
               f'{len(prime):,} as prime sponsor.</p>')
    out.append('<p class="src">Taken from the General Court&#8217;s own sponsor '
               "list. Sponsoring a bill is putting a name to it, which is not "
               "the same as voting for it and is not counted as one here.</p>")
    if prime:
        out.append("<h3>As prime sponsor</h3>" + table(prime))
    if rest:
        out.append(f"<h3>As co-sponsor &#8212; {len(rest):,}</h3>"
                   "<details><summary>Show them</summary>"
                   + table(rest) + "</details>")
    return "\n".join(out)


def page(m, detail, base, css):
    name = m.get("display_full") or m.get("display") or m.get("name", "")
    plain = m.get("display_plain") or name
    chamber = "Senate" if str(m.get("chamber", "")).upper().startswith("S") \
        else "House of Representatives"
    sponsored_block = sponsored_section(detail, base)
    votes = detail.get("votes") or []
    counts = detail.get("counts") or {}
    towns = m.get("towns") or []
    cmtes = m.get("committees") or []

    rows = ""
    for v in votes[:400]:
        rows += (f'<tr><td class="d">{E(v.get("d", ""))}</td>'
                 f'<td class="b"><a href="../bill/{E(v.get("y") or "2026")}/'
                 f'{E(str(v.get("b", "")).lower())}.html">{E(v.get("b", ""))}</a></td>'
                 f'<td>{E(v.get("q", ""))}</td>'
                 f'<td class="v">{E(VOTE_WORDS.get(v.get("v"), v.get("v", "")))}</td>'
                 "</tr>")

    tally = " &middot; ".join(
        f"{E(VOTE_WORDS.get(k, k))} {n:,}" for k, n in
        sorted(counts.items(), key=lambda x: -x[1]) if n)

    # Everything a crawler needs to know this is a person, and who.
    ld = {"@context": "https://schema.org", "@type": "Person",
          "name": plain, "jobTitle": f"Member, New Hampshire {chamber}",
          "url": f"{base}/legislator/{person_slug(m)}.html",
          "affiliation": {"@type": "GovernmentOrganization",
                          "name": "New Hampshire General Court"}}
    if m.get("email"):
        ld["email"] = m["email"]

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(plain)} — {E(chamber)} — Granite Record</title>
<meta name="description" content="{E(plain)}, {E(m.get('party',''))}, {E(chamber)}
 district {E(m.get('district',''))}. Voting record, sponsored bills and
 committees, from the New Hampshire General Court's own records.">
<link rel="canonical" href="{base}/legislator/{person_slug(m)}.html">
<link rel="alternate" type="application/rss+xml" title="{E(plain)} votes"
      href="{base}/feed/legislator/{E(m.get('id',''))}.xml">
<link rel="stylesheet" href="../style.css">
<style>{css}</style>
<script type="application/ld+json">{json.dumps(ld)}</script>
</head><body>
<a class="skip" href="#main">Skip to the content</a>
<nav class="top"><div class="in"><span class="brand">Granite Record</span>
<a href="../index.html">Home</a><a href="../bills.html">Bills</a>
<a href="../legislators.html" aria-current="page">Legislators</a>
<a href="../learn.html">How it works</a><a href="../about.html">About</a>
</div></nav>
<div class="wrap" id="main">
<a class="backsearch" href="../legislators.html">&#8592; Back to search</a>
<h1>{E(name)}</h1>
<p class="meta">{E(chamber)}
{f" &middot; District {E(m.get('district',''))}" if m.get("district") else ""}
{f" &middot; {E(m.get('county',''))} County" if m.get("county") else ""}</p>
{f'<p class="meta"><a href="mailto:{E(m["email"])}">{E(m["email"])}</a></p>'
 if m.get("email") else ""}

{f'<h2>Towns represented</h2><p>{", ".join(E(t) for t in towns)}</p>' if towns else ""}

{f'<h2>Committees</h2><p>{", ".join(E(c) for c in cmtes)}</p>' if cmtes else ""}

{sponsored_block}
<h2>Recorded votes</h2>
{f'<p class="meta">{len(votes):,} recorded votes. {tally}</p>' if votes else ""}
<p class="src">Every roll call this member is recorded in, newest first, from
the General Court roll call files. Nothing here is rated, scored or totalled
into a rating: a vote is shown as it was cast and what it was on. Voice and
division votes leave no record of individual members and so do not appear.</p>
{f'<table class="votes"><thead><tr><th>Date</th><th>Bill</th><th>Question</th>'
 f'<th>Vote</th></tr></thead><tbody>{rows}</tbody></table>' if rows else
 '<p>No recorded roll call votes.</p>'}
{f'<p class="src">Showing the most recent 400 of {len(votes):,}.</p>'
 if len(votes) > 400 else ""}

<p class="src" style="margin-top:26px">Built from records published by the New
Hampshire General Court. This site is not affiliated with the General Court.
The official record always takes precedence.
<a href="../feed/legislator/{E(m.get('id',''))}.xml">Follow this member by
RSS</a>.</p>
</div>
<footer><div class="in">Built from public records published by the New Hampshire
General Court. Not affiliated with the General Court.
<a href="../about.html">How this is made</a>.</div></footer>
</body></html>
"""


CSS = """
.wrap{max-width:900px;margin:0 auto;padding:26px 20px 60px}
/* Top right, and a plain link rather than history.back(), so it goes to the
   search whether the reader arrived from it, from a bill's sponsor list, or
   from a search engine. */
.backsearch{float:right;font-size:13.5px;margin:2px 0 0 16px}
@media(max-width:620px){.backsearch{float:none;display:block;margin:0 0 10px}}
h1{clear:none}
h1{font-size:24px;margin:6px 0 4px}
h2{font-size:14px;font-weight:600;color:var(--ink-2);letter-spacing:.05em;
text-transform:uppercase;margin:26px 0 7px;padding-bottom:6px;
border-bottom:1px solid var(--rule)}
.meta{color:var(--ink-2);font-size:14px;margin:2px 0}
.src{color:var(--ink-3);font-size:13px;line-height:1.5}
table.votes{width:100%;border-collapse:collapse;font-size:14px;margin-top:10px}
table.votes th{text-align:left;font-size:12px;letter-spacing:.04em;
text-transform:uppercase;color:var(--ink-3);border-bottom:1px solid var(--rule);
padding:6px 8px 6px 0}
table.votes td{padding:6px 8px 6px 0;border-bottom:1px solid var(--rule);
vertical-align:top}
table.votes .d{white-space:nowrap;color:var(--ink-3);font-size:13px}
table.votes .b{white-space:nowrap;font-weight:600}
table.votes .v{white-space:nowrap}
@media(max-width:620px){table.votes,table.votes tbody,table.votes tr,
table.votes td{display:block;width:100%}table.votes thead{display:none}
table.votes tr{padding:8px 0;border-bottom:1px solid var(--rule)}
table.votes td{border:0;padding:1px 0}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site = Path(a.site)
    lp = site / "legislators.json"
    if not lp.exists():
        raise SystemExit(f"No {lp}. Run build_site_v2.py first.")
    legs = json.loads(lp.read_text(encoding="utf-8"))

    out = site / "legislator"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.html"):
        old.unlink()

    seen, written, skipped = {}, 0, 0
    urls = []
    for m in legs:
        # Sitting members only. A page says "this is who represents you"; for
        # somebody who has left, that sentence is false, and their votes are
        # still wherever they were cast.
        if m.get("former") or m.get("left") or not m.get("id"):
            skipped += 1
            continue
        s = person_slug(m)
        if s in seen:
            s = f"{s}-{m['id']}"
        seen[s] = m["id"]
        d = site / "legislators" / f"{m['id']}.json"
        detail = json.loads(d.read_text(encoding="utf-8")) if d.exists() else {}
        (out / f"{s}.html").write_text(page(m, detail, a.base, CSS),
                                       encoding="utf-8")
        urls.append(f"{a.base}/legislator/{s}.html")
        written += 1

    print(f"{written:,} legislator pages -> {out}/")
    if skipped:
        print(f"{skipped:,} skipped: no id, or no longer sitting")

    # Into the sitemap, next to the bills. A page nothing points at is a page
    # nothing finds.
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
        if "</urlset>" in text and "/legislator/" not in text:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"{len(urls):,} added to sitemap.xml")
        elif "/legislator/" in text:
            print("sitemap already lists legislator pages; left alone")
    print("\nThese are plain HTML at a fixed address. Somebody searching a "
          "member's\nname can now find their voting record, which they could "
          "not before.")


if __name__ == "__main__":
    main()
