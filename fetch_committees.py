#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.2
"""
Every standing committee, from the two pages that list them.

    python3 fetch_committees.py --probe    # print what it finds, write nothing
    python3 fetch_committees.py            # write committees.json

Two requests. Nothing else is touched.

WHY THIS RATHER THAN THE MEMBER PAGES

Committees have been read off each member's own page, one member at a time --
406 requests to learn something two pages state outright. Worse, a member page
gives a list of names with no separator to rely on: "Current Committees:
Education Finance" is one committee, and there is nothing in that string to say
whether it is one or two. Guessing wrong publishes a committee that does not
exist.

These pages settle it. Each committee has a heading, an address of its own, a
chair, a vice chair, its members, its aide, its phone and its room:

    Education Finance      committee_details.aspx?cc=1715
      Chairman Keith Murphy, V Chairman Daniel Innis
      Timothy Lang, Sharon Carson, Ruth Ward, Cindy Rosenwald, Debra Altschiller
      Aide Karen Davis, (603) 271-7875, NA

So a name parsed from anywhere else can be checked against a list of committees
that exist, and a name that is not on it is a parse error rather than a new
committee.

The chairs are here too, which is the only place this project has found who
chairs what without asking each member in turn.

THE HOUSE

The House page has the same job and has never been read. Its committee
addresses are a different shape -- committeedetails.aspx?code=H42 against the
Senate's cc=1715 -- so the patterns allow for both, and --probe reports what it
managed rather than assuming it worked.
"""

import argparse
import html as _html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}
PAGES = [("S", "https://gc.nh.gov/senate/committees/senate_committees.aspx"),
         ("H", "https://gc.nh.gov/house/committees/standingcommittees.aspx")]

WS = re.compile(r"\s+")
# Both address shapes, and the name that goes with them.
CMTE_LINK = re.compile(
    r"<a\b[^>]*href=[\"'](?P<href>[^\"']*committee_?details\.aspx\?"
    r"(?:cc|code)=(?P<code>[^\"'&]+))[\"'][^>]*>(?P<name>[^<]{2,70})</a>",
    re.I)
# A member, however the chamber addresses them.
MEMBER_LINK = re.compile(
    r"<a\b[^>]*href=[\"'][^\"']*(?:webpages/district\d+\.aspx"
    r"|member\.aspx\?(?:member|pid)=\d+)[^\"']*[\"'][^>]*>(?P<who>[^<]{2,70})</a>",
    re.I)
ROLE = re.compile(r"^\s*(?P<role>V\s*Chair(?:man|woman)?|Chair(?:man|woman)?|"
                  r"Clerk|Ranking Member)\s+(?P<who>.+)$", re.I)
AIDE = re.compile(r"Committee Aide:\s*(?:<[^>]+>)*\s*([^<\n]{2,50})", re.I)
PHONE = re.compile(r"Phone:\s*(?:<[^>]+>)*\s*\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})", re.I)
PLACE = re.compile(r"Location:\s*(?:<[^>]+>)*\s*([^<\n]{1,40})", re.I)


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def clean(s):
    return WS.sub(" ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse(page, chamber):
    """Split at each committee heading, then read that committee's block."""
    marks = [(m.start(), m.group("code"), clean(m.group("name")),
              _html.unescape(m.group("href"))) for m in CMTE_LINK.finditer(page)]
    # A committee is named twice on these pages: once in the navigation and
    # once as its own heading. The heading is the later, longer block.
    seen, out = {}, []
    for i, (pos, code, name, href) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(page)
        block = page[pos:end]
        if len(block) < 200:            # a nav link, not a section
            continue
        if code in seen:
            continue
        seen[code] = True

        members, roles = [], {}
        for mm in MEMBER_LINK.finditer(block):
            who = clean(mm.group("who"))
            r = ROLE.match(who)
            if r:
                role = WS.sub(" ", r.group("role")).strip()
                role = "Vice Chair" if role.lower().startswith("v") else "Chair"
                who = clean(r.group("who"))
                roles[who] = role
            if who and who not in members:
                members.append(who)

        rec = {"chamber": chamber, "name": name, "code": code,
               "url": urllib.parse.urljoin(
                   "https://gc.nh.gov/senate/committees/" if chamber == "S"
                   else "https://gc.nh.gov/house/committees/", href),
               "members": [{"name": w, "position": roles.get(w, "Member")}
                           for w in members]}
        a = AIDE.search(block)
        if a:
            rec["aide"] = clean(a.group(1))
        ph = PHONE.search(block)
        if ph:
            rec["phone"] = f"({ph.group(1)}) {ph.group(2)}-{ph.group(3)}"
        pl = PLACE.search(block)
        if pl and clean(pl.group(1)).upper() not in ("NA", "N/A", ""):
            rec["location"] = clean(pl.group(1))
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="committees.json")
    ap.add_argument("--probe", action="store_true", help="print, write nothing")
    ap.add_argument("--raw", action="store_true",
                    help="also save each page, so a parser that "
                         "matched nothing can be fixed against "
                         "the real thing")
    ap.add_argument("--delay", type=float, default=2.0)
    a = ap.parse_args()

    found = {}
    for chamber, url in PAGES:
        print(f"\n{'Senate' if chamber == 'S' else 'House'}: {url}")
        try:
            page = get(url)
        except Exception as e:
            print(f"  could not fetch: {type(e).__name__}: {e}")
            continue
        if a.raw:
            # The House page returned 0 committees on 6 September.
            # Guessing at a heading shape is the thing this project does
            # not do, so the page is kept and the patterns are written
            # against it.
            name = ("committees_"
                    + ("senate" if chamber == "S" else "house") + ".html")
            with open(name, "w", encoding="utf-8") as fh:
                fh.write(page)
            print(f"  wrote {name} ({len(page):,} chars)")
        recs = parse(page, chamber)
        print(f"  {len(recs)} committees")
        if not recs:
            print("  Nothing matched. The committee headings on this page "
                  "are a shape\n  this does not read; run again with "
                  "--raw and the patterns can be written against the page "
                  "itself.")
            chair = next((m["name"] for m in r["members"]
                          if m["position"] == "Chair"), "")
            print(f"    {r['name']:<44} {len(r['members']):>2} members"
                  + (f"   chair {chair}" if chair else "   (no chair found)"))
        found[chamber] = recs
        time.sleep(a.delay)

    total = sum(len(v) for v in found.values())
    nochair = [r["name"] for v in found.values() for r in v
               if not any(m["position"] == "Chair" for m in r["members"])]
    print(f"\n{total} committees in all")
    if nochair:
        print(f"{len(nochair)} with no chair identified: "
              + ", ".join(nochair[:4]))

    if a.probe:
        print("\nNothing was written. Drop --probe once the list above looks "
              "right.")
        return
    if not total:
        print(f"\nNOT WRITING {a.out}: nothing was found.")
        return
    Path(a.out).write_text(json.dumps(found, indent=2), encoding="utf-8")
    print(f"-> {a.out}")
    print("\nA committee name parsed anywhere else can now be checked against "
          "this.\nA name that is not here is a parse error, not a new "
          "committee.")


if __name__ == "__main__":
    main()
