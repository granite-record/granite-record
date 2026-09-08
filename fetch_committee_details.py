#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.3
"""
Each committee's own page: the clerk, the staff, and what the committee is for.

    python3 fetch_committee_details.py --probe --only H24 --raw   # ONE request
    python3 fetch_committee_details.py                            # all of them

WHY THIS RATHER THAN THE LISTING PAGES

fetch_committees.py reads the two pages that list the committees, which is two
requests for the chair, the vice chair, the aide, the researcher, the phone and
the room. Three things are not on those pages and are on each committee's own:

  the clerk       an officer of the committee, and a member of it
  the roster      the House listing gives leadership only; the detail page
                  gives every member with their party
  the purpose     "Pursuant to House Rule 31: It shall be the duty of the
                  Committee on Children and Family Law to consider matters
                  relating to children and youth..."

The purpose is the one thing on a committee page that a reader who does not
already know the General Court cannot work out from a list of bills. A
committee's name says what it is called, not what is sent to it.

THE COST

One request per committee, 41 of them, 1.5 seconds apart -- about a minute.
That is the whole reason it is a separate script from fetch_committees.py,
which costs two requests and is run often.

IT MERGES

committees.json is written by fetch_committees.py from the listing pages. This
adds fields to the rows already there and never removes one, because a writer
of a shared file that runs on a subset destroys the rest -- which has happened
to three files on this project. It refuses to write a file with fewer
committees than it read.

WHAT --probe IS FOR

The description block's markup has not been read yet. --probe fetches one
committee, prints every field it parsed, and writes nothing; --raw keeps the
page so the patterns can be written against the real thing rather than against
an idea of what the page looks like.
"""

import argparse
import html as _html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}
WS = re.compile(r"\s+")

# "Pursuant to House Rule 31:" and the duty that follows it. The rule is
# captured separately so the page can cite it: the text is the General Court's
# and the citation is what makes it checkable.
RULE = re.compile(r"Pursuant\s+to\s+((?:House|Senate|Joint)\s+Rules?"
                  r"[^:<]{0,24}?)\s*:", re.I)
# A member of the committee, with the party the page prints after the name.
MEMBER = re.compile(
    r"<a\b[^>]*href=[\"'][^\"']*(?:member\.aspx\?(?:pid|member)=(?P<pid>\d+)"
    r"|webpages/district\d+\.aspx[^\"']*)[^\"']*[\"'][^>]*>(?P<who>[^<]{2,70})</a>"
    r"(?P<after>(?:\s|&nbsp;|<[^>]+>){0,40}\(?\s*(?P<party>[RDIL])\s*\)?)?",
    re.I)
STRIP = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def clean(s):
    return WS.sub(" ", _html.unescape(TAG.sub(" ", s or ""))).strip()


def labelled(page, *labels):
    """The value after one of these labels, however the page spaces it.

    Lifted from fetch_committees.py, which learned it the hard way: the House
    separates a label from its value with a literal &nbsp; rather than a
    space, so a pattern expecting whitespace found nothing on 27 pages.
    """
    for lab in labels:
        m = re.search(re.escape(lab) + r"\s*:(?:&nbsp;|&#160;|\s|<[^>]+>)*"
                      r"([^<\n]{2,60})", page, re.I)
        if m:
            v = clean(m.group(1))
            # A page with no clerk writes one. Matched case-insensitively
            # because it was not, and three committees published a clerk
            # named "n/a" -- a placeholder presented as a person.
            if v and v.strip().lower() not in (":", "-", "na", "n/a", "none",
                                               "tbd", "vacant", "."):
                return v
    return ""


# What the page puts after the duty. Read off the pages themselves rather than
# imagined: every one of the 26 runs straight from "...as may be referred to
# it." into "HELPFUL LINKS Committees of Conference Redistricting Ethics
# Committee..." with no punctuation between.
FOOTER = ("HELPFUL LINKS", "DOCUMENTS & MEDIA", "OTHER RESOURCES",
          "Pursuant to", "Committee Members", "Bills currently",
          "The General Court of New Hampshire", "NH General Court",
          "Copyright", "\u00a9")
# And a general form of the same thing, for a page whose footer is worded
# differently: two or more shouted words in a row is a navigation heading, not
# a sentence about a committee's duties. "RSA 169-B" and "DWI" appear inside
# duties and are one word each, so neither trips this.
SHOUT = re.compile(r"\b[A-Z]{3,}(?:\s*&)?\s+[A-Z]{3,}\b")


def trim_duty(tail):
    """The duty, and nothing the page printed after it.

    Cut at whichever comes first, then back up to the last full stop -- so a
    cut that lands in the wrong place drops a sentence rather than publishing
    half of one.
    """
    cuts = [tail.find(x) for x in FOOTER]
    m = SHOUT.search(tail)
    if m:
        cuts.append(m.start())
    cuts = [i for i in cuts if i > 0]
    if cuts:
        tail = tail[:min(cuts)]
    text = WS.sub(" ", tail).strip()
    dot = text.rfind(".")
    if dot > 40:
        text = text[:dot]
    return text.strip(" .;,") + "."


def purpose(page):
    """The committee's duty under the chamber's rules, and the rule's number.

    Read off the flattened text rather than the markup: the sentence is what
    is wanted and the tags inside it are not, and a page that moves the
    paragraph into a different container still reads.

    Stops at the first thing that is plainly not part of the duty -- the
    General Court's footer, or another "Pursuant to" -- rather than taking a
    fixed number of characters, which would cut a long duty in half and
    silently publish a sentence that stops mid-clause.
    """
    flat = clean(STRIP.sub(" ", page))
    m = RULE.search(flat)
    if not m:
        return None
    text = trim_duty(flat[m.end():])
    # A duty is a sentence, not a word. Anything shorter is the pattern having
    # matched a heading with nothing under it, and saying so is better than
    # publishing it.
    if len(text) < 40:
        return None
    return {"rule": WS.sub(" ", _html.unescape(m.group(1))).strip(),
            "text": text}


def roster(page):
    """Every member the page names, with the party letter beside them."""
    out, seen = [], set()
    for m in MEMBER.finditer(page):
        who = clean(m.group("who"))
        # "Chairman: Debra DeSimone" -- the officer links carry their title in
        # the surrounding text, not in the anchor, so the anchor is the name.
        if not who or who.lower() in seen or len(who) < 3:
            continue
        seen.add(who.lower())
        out.append({"name": who, "party_code": (m.group("party") or "").upper(),
                    "pid": m.group("pid") or ""})
    return out


def parse(page):
    """Everything this page adds to what the listing pages already gave."""
    rec = {}
    for key, labels in (("clerk", ("Clerk",)),
                        ("chair", ("Chairman", "Chairwoman", "Chair")),
                        ("vice_chair", ("VChairman", "V Chairman",
                                        "Vice Chairman", "Vice Chair")),
                        ("aide", ("Committee Asst", "Committee Assistant",
                                  "Committee Aide")),
                        ("researcher", ("Researcher",)),
                        ("location", ("Location", "Room")),
                        ("phone", ("Phone",))):
        v = labelled(page, *labels)
        if v:
            rec[key] = v
    p = purpose(page)
    if p:
        rec["purpose"] = p
    r = roster(page)
    if r:
        rec["web_members"] = r
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="committees.json",
                    help="read the committees from here, and merge back into it")
    ap.add_argument("--only", default="",
                    help="one committee, by the code its page uses (H24, S30) "
                         "or by name")
    ap.add_argument("--probe", action="store_true", help="print, write nothing")
    ap.add_argument("--raw", action="store_true",
                    help="keep each page, so a parser that matched nothing "
                         "can be fixed against the real thing")
    ap.add_argument("--delay", type=float, default=1.5)
    a = ap.parse_args()

    path = Path(a.file)
    if not path.exists():
        sys.exit(f"{path} is not there. Run fetch_committees.py first -- this "
                 "adds to what that wrote and cannot invent the list.")
    book = json.loads(path.read_text(encoding="utf-8"))
    before = sum(len(v) for v in book.values())

    want = a.only.strip().lower()
    todo = []
    for chamber, rows in book.items():
        for r in rows:
            code = f"{chamber}{r.get('code', '')}"
            if want and want not in (code.lower(), (r.get("name") or "").lower()):
                continue
            if not r.get("url"):
                print(f"  {code} {r.get('name')}: no address on file, skipped")
                continue
            todo.append((chamber, code, r))
    if not todo:
        sys.exit(f"nothing to fetch{f' matching {a.only!r}' if a.only else ''}")

    print(f"{len(todo)} committee page(s), {a.delay}s apart "
          f"-- about {len(todo) * a.delay / 60:.1f} minutes\n")
    got, failed = 0, []
    for i, (chamber, code, row) in enumerate(todo):
        url = row["url"]
        try:
            page = get(url)
        except Exception as e:                       # noqa: BLE001
            failed.append(f"{code}: {type(e).__name__}: {e}")
            print(f"  {code:<5} {row.get('name', '')[:38]:<38} FAILED "
                  f"{type(e).__name__}")
            # A refusal is the one thing worth stopping for. Carrying on
            # through 40 more is how this address got blocked twice.
            if len(failed) >= 3:
                print("\nThree in a row failed. Stopping rather than making "
                      "38 more requests at a server that is refusing.\n"
                      "python3 netcheck.py says what kind of refusal it is.")
                break
            time.sleep(a.delay)
            continue
        if a.raw:
            name = f"committee_{code}.html"
            Path(name).write_text(page, encoding="utf-8")
            print(f"  wrote {name} ({len(page):,} chars)")
        rec = parse(page)
        got += 1
        have = [k for k in ("clerk", "purpose", "researcher", "location")
                if rec.get(k)]
        print(f"  {code:<5} {row.get('name', '')[:38]:<38} "
              f"{len(rec.get('web_members', [])):>2} members  "
              + (", ".join(have) if have else "nothing new"))
        if a.probe:
            for k, v in rec.items():
                if k == "web_members":
                    print(f"      {k}: " + ", ".join(
                        f"{m['name']}{' (' + m['party_code'] + ')' if m['party_code'] else ''}"
                        for m in v[:6]) + (" ..." if len(v) > 6 else ""))
                elif k == "purpose":
                    print(f"      rule: {v['rule']}")
                    print(f"      text: {v['text'][:300]}"
                          + ("..." if len(v["text"]) > 300 else ""))
                else:
                    print(f"      {k}: {v}")
        # MERGE. A field already on file is only replaced by a non-empty one:
        # the listing pages and the detail pages disagree about spacing and
        # occasionally about a name, and an empty parse must never blank a
        # value that was there.
        for k, v in rec.items():
            if v:
                row[k] = v
        if i + 1 < len(todo):
            time.sleep(a.delay)

    print(f"\n{got} of {len(todo)} pages read")
    n_clerk = sum(1 for v in book.values() for r in v if r.get("clerk"))
    n_purp = sum(1 for v in book.values() for r in v if r.get("purpose"))
    print(f"  {n_clerk} committees now have a clerk, {n_purp} a stated purpose")
    if failed:
        print(f"  {len(failed)} failed: " + "; ".join(failed[:3]))

    if a.probe:
        print("\nNothing was written. Drop --probe once the fields above look "
              "right.")
        return 0
    if not got:
        print(f"\nNOT WRITING {a.file}: no page was read.")
        return 1
    if not (n_clerk or n_purp):
        print(f"\nNOT WRITING {a.file}: {got} pages were read and neither a "
              "clerk nor a purpose came out of any of them. That is a parser "
              "that no longer matches the page, not 41 committees without a "
              "clerk. Run with --probe --raw --only H24 and fix the patterns "
              "against the page.")
        return 1
    after = sum(len(v) for v in book.values())
    assert after >= before, (
        f"{a.file} would go from {before} committees to {after}. This script "
        "adds fields to rows and removes none, so a smaller file is a bug in "
        "it, not a change at the General Court.")
    path.write_text(json.dumps(book, indent=2), encoding="utf-8")
    print(f"-> {a.file} ({after} committees, {before} read)")
    print("\nRun build_committees.py to put the clerk and the purpose on the "
          "pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
