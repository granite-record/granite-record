#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.4
"""
A page per town and ward: everyone who represents the people who live there.

    python3 build_town_pages.py --site site --base https://graniterecord.org

Writes site/town/<slug>.html for each of the 320 town-wards, and adds them to
sitemap.xml.

WHY A PAGE AND NOT ONLY THE LOOKUP

The legislators page already answers "who are my representatives" in place:
pick a town, pick a ward, see the House and Senate seats. What it cannot do is
be linked to, shared, printed or found in a search -- and "who represents
Concord Ward 3" is exactly the question somebody types into a search engine.

It also stopped at the General Court. A resident has an executive councillor,
a member of the US House and two US senators as well, and the district
numbers for all of them were already on this disk in site/districts.json and
had never been shown.

WHAT IS DERIVED AND WHAT IS DECLARED

The districts are derived: districts/council.txt, congress.txt, senate.txt and
house.txt are the maps, and parse_districts.py turns them into a town-ward
lookup that includes the floterial districts the General Court's own file
leaves out.

The people are not. State legislators come from the roster the rest of the
site uses. The Governor, the five councillors, the two US representatives and
the two senators come from officials.json, which is edited by hand and which
no generator writes -- a name against an office is a claim about a real
person, and it should come from somebody who checked. Where a name is blank
the page names the office, gives the reader their district and links to the
official directory, which is correct and does not go stale.
"""

import argparse
import json
import re
from pathlib import Path

import shell as S

E = S.E


def slug(town, ward):
    s = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
    return f"{s}-ward-{ward}" if ward and ward != "0" else s


def where(town, ward, wards):
    return f"{town}, Ward {ward}" if len(wards) > 1 else town


def chip(m):
    p = (m.get("party") or "X")[:1].upper()
    return f'<span class="mchip p-{E(p)}">{E(m.get("display_full") or m.get("name") or "")}</span>'


def member_block(members, empty):
    """The people in a seat, each with a way to reach them."""
    if not members:
        return f'<p class="note">{E(empty)}</p>'
    out = []
    for m in members:
        link = (f'<a href="/legislator/{E(m["slug"])}">'
                f'{E(m.get("display_full") or m.get("name"))}</a>'
                if m.get("slug") else E(m.get("display_full") or m.get("name")))
        p = (m.get("party") or "X")[:1].upper()
        bits = [f'<span class="mchip p-{E(p)}">{link}</span>']
        if m.get("email"):
            bits.append(f'<a href="mailto:{E(m["email"])}">{E(m["email"])}</a>')
        if m.get("phone"):
            bits.append(E(m["phone"]))
        out.append('<li class="offrow">' + " &middot; ".join(bits) + "</li>")
    return '<ul class="offlist">' + "".join(out) + "</ul>"


def office_block(title, holder, fallback_url, note=""):
    """One office this site does not track: what it is, who holds it if we
    were told, and the official page either way."""
    holder = holder or {}
    name = (holder.get("name") or "").strip()
    url = (holder.get("official_url") or "").strip() or fallback_url
    bits = []
    if name:
        p = (holder.get("party") or "X")[:1].upper()
        who = (f'<a href="{E(url)}" rel="noopener">{E(name)}</a>'
               if url else E(name))
        bits.append(f'<span class="mchip p-{E(p)}">{who}</span>')
        if holder.get("phone"):
            bits.append(E(holder["phone"]))
        if holder.get("phone_dc"):
            bits.append(E(holder["phone_dc"]) + " (Washington)")
        if holder.get("email"):
            bits.append(f'<a href="mailto:{E(holder["email"])}">'
                        f'{E(holder["email"])}</a>')
        if url:
            bits.append(f'<a href="{E(url)}" rel="noopener">official page</a>')
    else:
        # NOT AN APOLOGY AND NOT AN EMPTY SPACE. The district is the useful
        # half of the answer and it is known; the name is the half this site
        # was not told, and the office's own directory is where it is right.
        bits.append(f'<a href="{E(url)}" rel="noopener">'
                    "who holds this seat, on the official directory</a>")
    body = '<ul class="offlist"><li class="offrow">' + \
           " &middot; ".join(bits) + "</li></ul>"
    return ((f'<h3 class="offh">{E(title)}</h3>' if title else "")
            + (f'<p class="note">{E(note)}</p>' if note else "")
            + body)


def build(town, ward, wards, dist, legs, off, base, tmpl):
    label = where(town, ward, wards)
    body = [f'<h1 class="offtitle">{E(label)}</h1>',
            '<p class="lead">Everyone elected to represent the people who live '
            'here, and how to reach them.</p>']

    # ---- the General Court, which this site does track --------------------
    body.append('<h2 class="offsec">In the General Court</h2>')
    house = dist.get("house") or []
    for h in house:
        who = [m for m in legs
               if m.get("chamber") == "H"
               and (m.get("county") or "") == h.get("county")
               and str(m.get("district") or "") == str(h.get("district"))]
        seats = h.get("seats")
        head = (f'{E(h.get("county",""))} district {h.get("district")}'
                + (f' &middot; {seats} seat{"s" if seats and seats > 1 else ""}'
                   if seats else ""))
        body.append(f'<h3 class="offh">House &mdash; {head}</h3>')
        if h.get("floterial"):
            body.append('<p class="note">A floterial district overlays several '
                        'towns that each already elect their own '
                        'representative, and elects additional members across '
                        'the combined population. You are represented by '
                        'both.</p>')
        body.append(member_block(who, "No sitting member is matched to this "
                                      "district."))
    if not house:
        body.append('<p class="note">No House district is on file for this '
                    'ward.</p>')

    sd = dist.get("senate")
    if sd:
        who = [m for m in legs if m.get("chamber") == "S"
               and str(m.get("district") or "") == str(sd)]
        body.append(f'<h3 class="offh">Senate &mdash; district {sd}</h3>')
        body.append(member_block(who, "No sitting senator is matched to this "
                                      "district."))

    # ---- the offices this site does not track ----------------------------
    body.append('<h2 class="offsec">Other offices</h2>')
    body.append('<p class="note">Granite Record follows the General Court. '
                'These offices are elected by the same people and are not part '
                'of it, so nothing they do appears elsewhere on this site. '
                'They are here because they represent you.</p>')

    cd = dist.get("council")
    if cd:
        c = off.get("council", {})
        body.append(office_block(
            f"Executive Council — district {cd}",
            (c.get("districts") or {}).get(str(cd)),
            c.get("official_url", ""),
            " ".join(c.get("about") or [])))

    gd = dist.get("congress")
    if gd:
        u = off.get("us_house", {})
        body.append(office_block(
            f"US House — New Hampshire district {gd}",
            (u.get("districts") or {}).get(str(gd)),
            u.get("official_url", ""),
            " ".join(u.get("about") or [])))

    us = off.get("us_senate", {})
    body.append(f'<h3 class="offh">US Senate</h3>')
    if us.get("about"):
        body.append(f'<p class="note">{E(" ".join(us["about"]))}</p>')
    for seat in (us.get("seats") or []):
        # No per-seat heading. Both are elected by the whole state and both
        # represent this town, so the names are what tells them apart --
        # senate.gov lists them in seniority order and calling one "senior"
        # here would be reading more into that order than it states.
        body.append(office_block("", seat, us.get("official_url", "")))

    g = off.get("governor", {})
    body.append(office_block("Governor of New Hampshire", g,
                             g.get("official_url", "")))

    # WHEN, as well as where. These offices change at an election and the
    # names here do not; the official link does not go stale, and a reader
    # who can see the date can tell which half they are looking at.
    checked = (off.get("_checked") or "").strip()
    body.append('<p class="srcs">Districts from the General Court\'s own '
                'district files, including the floterial districts its '
                'legislator list omits. Members of the House and Senate from '
                'the General Court roster, which the rest of this site is '
                'drawn from. The offices under "Other offices" are in no '
                'General Court file: they were read from the Governor\'s '
                'office, the Executive Council, the Secretary of State\'s '
                'congressional delegation page and senate.gov'
                + (f', on {E(checked)}' if checked else '')
                + '. Each links to its own official page, which stays right '
                'after an election when a name here would not.</p>')

    path = f"/town/{slug(town, ward)}.html"
    desc = (f"Who represents {label}: state representatives, state senator, "
            "executive councillor, US representative, US senators and the "
            "governor, with how to reach each of them.")
    p = S.page(tmpl, path=path, base=base,
               title=S.title_of(f"Who represents {label}"),
               og_title=f"Who represents {label}",
               description=desc, globals={"GR_STATIC": True},
               noscript="", skip_label="Skip to the page", sr_title="",
               nav_current="legislators.html")
    return p.replace('<div id="results"></div>',
                     '<div id="results"><div class="officials">'
                     + "".join(body) + "</div></div>", 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--officials", default="officials.json")
    a = ap.parse_args()

    site = Path(a.site)
    districts = json.loads((site / "districts.json").read_text(encoding="utf-8"))
    legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
    if isinstance(legs, dict):
        legs = list(legs.values())
    off = json.loads(Path(a.officials).read_text(encoding="utf-8"))
    tmpl = S.template(site)

    out = site / "town"
    out.mkdir(parents=True, exist_ok=True)
    urls, n = [], 0
    for town in sorted(districts):
        wards = districts[town]
        for ward in sorted(wards, key=lambda w: int(w) if w.isdigit() else 0):
            page = build(town, ward, wards, wards[ward], legs, off,
                         a.base, tmpl)
            (out / f"{slug(town, ward)}.html").write_text(page,
                                                          encoding="utf-8")
            urls.append(a.base + S.canon(f"/town/{slug(town, ward)}.html"))
            n += 1

    # Silence is not success.
    if not n:
        raise SystemExit("No town pages were written. Is site/districts.json "
                         "built? parse_districts.py writes it.")

    named = sum(1 for k, v in off.items()
                if isinstance(v, dict) and (v.get("name") or "").strip())
    for k in ("council", "us_house"):
        named += sum(1 for d in (off.get(k, {}).get("districts") or {}).values()
                     if (d.get("name") or "").strip())
    named += sum(1 for s in (off.get("us_senate", {}).get("seats") or [])
                 if (s.get("name") or "").strip())
    print(f"{n:,} town-ward pages -> {out}/")
    print(f"  {named} of 10 other offices name who holds them; the rest link "
          "to the official directory")

    # Appended rather than replaced: rewriting it here would drop every other
    # URL on the site.
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{E(u)}</loc></url>\n" for u in urls
                      if E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"  {len(add.splitlines())} added to sitemap.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
