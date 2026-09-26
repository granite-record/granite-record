#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.7
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
import refusal
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
PAGES = [("S", "https://gc.nh.gov/senate/committees/senate_committees.aspx"),
         ("H", "https://gc.nh.gov/house/committees/standingcommittees.aspx")]

WS = re.compile(r"\s+")
# Both address shapes, and the name that goes with them.
CMTE_LINK = re.compile(
    r"<a\b[^>]*href=[\"'](?P<href>[^\"']*committee_?details\.aspx\?"
    r"(?:cc|code|id)=(?P<code>[^\"'&]+))[\"'][^>]*>(?P<name>[^<]{2,70})</a>",
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


# Every label a committee page puts before a value, as this parser and
# fetch_committee_details.py's read them; preflight holds the two lists to
# each other and to every label either parser asks for. A label the page
# leaves blank is followed by the next one, and the pattern in labelled()
# skips the markup between them: on the House listing of 6 September, Rules
# has a blank "Committee Assistant:" and "Researcher:", and its aide was read
# as "Researcher:" and its researcher as "Location:".
LABELS = ("Chairman", "Chairwoman", "Chair", "VChairman", "V Chairman",
          "Vice Chairman", "Vice Chair", "Clerk", "Committee Assistant",
          "Committee Asst", "Committee Aide", "Researcher", "Location", "Room",
          "Phone")
NEXT_LABEL = re.compile(
    r"^(?:(?:" + "|".join(r"\s+".join(map(re.escape, lab.split()))
                          for lab in sorted(LABELS, key=len, reverse=True))
    + r")\s*:|Pursuant\s+to\b)", re.I)


def not_a_value(v):
    """Whether a label's reading is the page's next label rather than a value:
    it ends in a colon, or begins with a label or with a committee's duty."""
    return v.endswith(":") or bool(NEXT_LABEL.match(v))


def labelled(block, *labels):
    """The value after one of these labels, however the page spaces it.

    The two chambers write the same facts differently. The Senate uses
    "Committee Aide:"; the House writes "Committee Assistant:" and separates
    label from value with a literal &nbsp; rather than a space, which is why
    a pattern expecting whitespace found nothing on 27 House committees.

    A label with nothing after it gives "", not the next label: see LABELS.
    """
    for lab in labels:
        m = re.search(re.escape(lab) + r"\s*:(?:&nbsp;|&#160;|\s|<[^>]+>)*"
                      r"([^<\n]{2,60})", block, re.I)
        if m:
            v = clean(m.group(1))
            if v and v not in (":", "-") and not not_a_value(v):
                return v
    return ""


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

        # The two chambers publish different amounts here, and the record
        # says which. The Senate page carries a full roster with the chair
        # and vice chair marked on the member links. The House page carries
        # leadership and the room only -- "Chairman:", "Vice Chairman:",
        # "Committee Assistant:", separated from their values by a literal
        # &nbsp; -- and its roster lives on 27 separate detail pages.
        #
        # So House committees get members == [] rather than a two-name list
        # that would read as the whole committee, and `roster` says whether
        # the list is everybody or nobody.
        chair = (next((w for w in members if roles.get(w) == "Chair"), "")
                 or labelled(block, "Chairman", "Chair"))
        vice = (next((w for w in members if roles.get(w) == "Vice Chair"), "")
                or labelled(block, "Vice Chairman", "Vice Chair"))
        rec = {"chamber": chamber, "name": name, "code": code,
               "url": urllib.parse.urljoin(
                   "https://gc.nh.gov/senate/committees/" if chamber == "S"
                   else "https://gc.nh.gov/house/committees/", href),
               "members": [{"name": w, "position": roles.get(w, "Member")}
                           for w in members],
               "roster": "full" if members else "leadership only",
               "chair": chair, "vice_chair": vice}
        aide = labelled(block, "Committee Aide", "Committee Assistant")
        if aide:
            rec["aide"] = aide
        researcher = labelled(block, "Researcher")
        if researcher:
            rec["researcher"] = researcher
        ph = PHONE.search(block)
        if ph:
            rec["phone"] = f"({ph.group(1)}) {ph.group(2)}-{ph.group(3)}"
        else:
            ph2 = labelled(block, "Phone")
            if ph2:
                rec["phone"] = ph2
        place = labelled(block, "Location", "Room")
        if place and place.upper() not in ("NA", "N/A", ""):
            rec["location"] = place
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
    # GitHub's weekly job owns committees.json once the laptop has stood down.
    refusal.stand_down("The committee pages fetch", "GitHub's weekly job takes "
                       "committees.json on Sunday nights now.")
    refusal.check("The committee membership fetch")

    found = {}
    dropped = 0
    for chamber, url in PAGES:
        print(f"\n{'Senate' if chamber == 'S' else 'House'}: {url}")
        try:
            page = get(url)
        except Exception as e:
            print(f"  could not fetch: {type(e).__name__}: {e}")
            # ONE READING OF AN ANSWER, the one every other fetcher uses. This
            # printed a 403 and asked for the next page two seconds later, and
            # recorded nothing, so the next fetch to start asked again. It runs
            # unattended in GitHub's weekly job now, which is where walking
            # through a refusal would go unseen longest.
            kind = refusal.classify(e)
            dropped += kind == "dropped"
            if kind == "refused" or dropped >= 2:
                refusal.note("fetch_committees", f"{type(e).__name__}: {e}")
                print("  Refused. Recorded in the refusal file; nothing more is "
                      "asked, and every fetch now waits for a person.")
                sys.exit(2)
            continue
        if refusal.classify(body=page[:4000]) == "refused":
            refusal.note("fetch_committees", "the firewall's block page, served as 200")
            print("  The firewall's block page. Recorded; nothing more is asked.")
            sys.exit(2)
        if a.raw:
            # The House page has come back with 0 committees on it.
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
        for r in recs:
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
    lead_only = [r["name"] for v in found.values() for r in v
                 if r.get("roster") != "full"]
    if lead_only:
        print(f"{len(lead_only)} of them carry leadership and room only, no "
              "member roster:")
        print("  the House standing-committees page does not list members; "
              "they are on")
        print("  27 separate detail pages, which is 27 more requests and is "
              "not done here.")
    if nochair:
        print(f"{len(nochair)} with no chair identified: "
              + ", ".join(nochair[:4]))

    if a.probe:
        print("\nNothing was written. Drop --probe once the list above looks "
              "right.")
        return
    if not total:
        # Exit 1, not 0: a fetch that found nothing and said so on one line
        # looks exactly like one that worked to anything reading its status.
        print(f"\nNOT WRITING {a.out}: nothing was found.")
        return 1
    Path(a.out).write_text(json.dumps(found, indent=2), encoding="utf-8")
    print(f"-> {a.out}")
    print("\nA committee name parsed anywhere else can now be checked against "
          "this.\nA name that is not here is a parse error, not a new "
          "committee.")


if __name__ == "__main__":
    sys.exit(main())
