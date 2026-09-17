#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.5
"""
Who holds a leadership role in each chamber.

    python3 fetch_leadership.py --plan     # the five addresses and where each is linked; no request
    python3 fetch_leadership.py            # save the five pages to archive/leadership/, 20 s apart
    python3 fetch_leadership.py --parse    # read what is saved, write leadership.json; no request

FETCHING AND READING ARE TWO STEPS. The House pages have
never been read, so the parser for them cannot be right the first time -- and
a parser that is allowed to be wrong must not cost a request each time it is
wrong. The fetch saves the pages whole and stops; --parse reads them as often
as it takes. The same split fetch_legislation.py has.

WHAT IT ASKS, AND WHAT MAKES IT STOP. Five pages, one request each, never
retried, 20 seconds apart, under refusal.check() and refusal.hold() like every
other fetch from this address. One refusal (403, 429, 503, the firewall's block
page even with a 200) ends the run and is recorded for 24 hours; two dropped
connections do the same; a linked page that answers 404 ends the run too,
rather than going on to ask the next. Until then it retried five times with a
back-off, which turned one 403 into five.

AND ONLY ADDRESSES THE GENERAL COURT LINKS. This address was blocked once for
asking for files that did not exist. Every page below is linked from a General
Court page already on this disk -- the navigation of committees_senate.html
and committees_house.html, which fetch_committees.py saved -- and one that is
not is never asked. The Senate's own "Senate Leadership" page is new here; the
About page is kept beside it because its list has been read and the other has
not.

Committee chair, vice chair and clerk come off a member's own page and are
already collected by fetch_members.py. Chamber leadership is not on any member
page: the Speaker's page does not say Speaker, and neither does the Majority
Leader's. It lives on the chamber's own pages instead.

THE SENATE

gc.nh.gov/senate/about_senate/about.aspx, under "Senate Leadership":

    President: Senator Sharon Carson of Londonderry
    Majority Leader: Senator Regina Birdsell of Hampstead
    Deputy Majority Leader: Senator Ruth Ward of Stoddard
    ...
    Minority Leader: Senator Rebecca Perkins Kwoka of Portsmouth

Labelled, one per line, with the member's town after "of". Nothing has to be
inferred.

Only the ROLES are taken from that page. The same page says the Senate is
"eighteen Republicans and six Democrats", and the roster says sixteen and
eight, so its prose is not current even where its list is. Counts come from the
roster, which is rebuilt from the roll every day.

THE HOUSE

The House has no equivalent single page. The Speaker's, Majority and Minority
offices each have one, and their shape has never been read, so --parse prints
what it finds on them rather than guessing at a pattern, and the parser can be
written against the real thing -- which is how the member pages and the RSA
addresses were done.

WHAT IT WRITES

leadership.json, keyed by the same member id as data/legislators.json:

    {"377204": {"chamber": "S", "roles": ["Majority Whip"]},
     "_unmatched": [{"name": "...", "role": "...", "chamber": "S"}]}

A name that matches nobody on the roster is recorded rather than dropped. A
leadership role attached to the wrong member is worse than one missing, so the
match has to be exact on the surname-first form of the name.
"""

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import refusal

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
WS = re.compile(r"\s+")
TAG = re.compile(r"<[^>]+>")

ROOT = Path("archive/leadership")
# (saved as, chamber, address, the saved General Court page that links it)
PAGES = [
    ("senate-leadership", "S", "https://gc.nh.gov/senate/members/leadership.aspx",
     "committees_senate.html"),
    ("senate-about", "S", "https://gc.nh.gov/senate/about_senate/about.aspx",
     "committees_senate.html"),
    ("house-speaker", "H", "https://gc.nh.gov/house/staff/speakersOffice.aspx",
     "committees_house.html"),
    ("house-majority", "H", "https://gc.nh.gov/house/staff/majorityOffice.aspx",
     "committees_house.html"),
    ("house-minority", "H", "https://gc.nh.gov/house/staff/MinorityOffice.aspx",
     "committees_house.html"),
]
DELAY = 20

# "Majority Leader: Senator Regina Birdsell of Hampstead"
# "Chair, Majority Policy Conference: Senator Dan Innis of Bradford"
ROLE_RE = re.compile(
    r"(?P<role>[A-Z][A-Za-z][A-Za-z ,]{2,44}?)\s*:\s*"
    r"(?:Senator|Sen\.|Representative|Rep\.)\s+"
    r"(?P<name>[A-Z][\w'\u2019.\-]*(?:\s+[A-Z][\w'\u2019.\-]*){1,3}?)"
    r"\s+of\s+(?P<town>[A-Z][A-Za-z .'\u2019-]{2,30})")

# Roles worth recording. A page carries plenty of other colon-separated text,
# and a list of what a leadership role can be called is a shorter and safer
# thing to maintain than a pattern that tries to exclude everything else.
ROLE_WORDS = re.compile(
    r"speaker|president|leader|whip|pro tempore|policy conference|clerk|"
    r"deputy|assistant", re.I)


def text_of(html):
    html = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", html,
                  flags=re.S | re.I)
    html = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", html, flags=re.I)
    t = TAG.sub(" ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#39;", "'"),
                 ("&quot;", '"'), ("&rsquo;", "\u2019")):
        t = t.replace(a, b)
    return "\n".join(WS.sub(" ", ln).strip() for ln in t.splitlines())


def linked(page):
    """Whether a General Court page saved on this disk links this address."""
    _key, _ch, url, where = page
    p = Path(where)
    if not p.exists():
        return False
    path = urllib.parse.urlsplit(url).path
    return f'href="{path}"' in p.read_text(encoding="utf-8", errors="replace")


def _get(url, timeout=60):
    """One request. No retry: a second ask after a refusal is the harm."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def saved(key):
    return ROOT / f"{key}.html"


def fetch(held, delay=DELAY, pages=None):
    """Ask for each page not already saved. Returns the exit status.

    0 every page saved; 1 stopped for a reason that is not a refusal; 2 a
    refusal, recorded in archive/refused.json for every fetch to see.
    """
    dropped, asked = 0, 0
    for page in pages or PAGES:
        key, _ch, url, where = page
        if saved(key).exists():
            print(f"  {key}: saved already, not asked")
            continue
        if not linked(page):
            print(f"  {key}: {url} is not linked from {where} on this disk, so it "
                  "is not asked. An address nobody has seen linked is a guess.")
            return 1
        if asked:
            time.sleep(delay * random.uniform(0.8, 1.2))
        # After the sleep, directly before the request: a refusal another
        # process met meanwhile is a refusal here too.
        if refusal.MARK.exists():
            print("\nStopping: archive/refused.json is on file.")
            return 2
        if not held.still():
            print("\nStopping: the lane holding archive/.lock is gone.")
            return 1
        asked += 1
        try:
            html = _get(url)
        except Exception as e:
            kind = refusal.classify(e)
            why = (f"HTTP {e.code} on {url}" if isinstance(e, urllib.error.HTTPError)
                   else f"{type(e).__name__}: {e} on {url}")
            if kind == "refused" or (kind == "dropped" and dropped + 1 >= 2):
                refusal.note("fetch_leadership", why)
                print(f"\nREFUSED: {why}. Stopping, and refusal.py now holds one "
                      "for 24 hours.\npython3 netcheck.py says what kind it is "
                      "without making it worse.")
                return 2
            if kind == "dropped":
                dropped += 1
                print(f"  {key}: dropped ({why}). One more ends the run.")
                continue
            # A page the General Court links that is not there is worth a
            # person's look, and not worth asking the next one to find out.
            print(f"\n  {key}: {kind} -- {why}. Stopping.")
            return 1
        if refusal.classify(body=html) == "refused":
            refusal.note("fetch_leadership", f"the firewall's block page, with a 200, on {url}")
            print(f"\nREFUSED: the block page, served as a page, on {url}. Stopping.")
            return 2
        if "<title" not in html[:4000].lower():
            print(f"\n  {key}: the answer is not a page, and is not saved. Stopping.")
            return 1
        ROOT.mkdir(parents=True, exist_ok=True)
        tmp = saved(key).with_name(saved(key).name + ".part")
        tmp.write_text(html, encoding="utf-8")
        os.replace(tmp, saved(key))
        print(f"  {key}: saved, {len(html):,} characters")
    return 1 if dropped else 0


def find_roles(text, chamber):
    out, seen = [], set()
    for m in ROLE_RE.finditer(text):
        role = WS.sub(" ", m.group("role")).strip(" ,.")
        if not ROLE_WORDS.search(role):
            continue
        rec = (role, WS.sub(" ", m.group("name")).strip(),
               WS.sub(" ", m.group("town")).strip(" .,"))
        if rec in seen:
            continue
        seen.add(rec)
        out.append({"role": role, "name": rec[1], "town": rec[2],
                    "chamber": chamber})
    return out


def name_key(raw):
    """(last word of the surname, first initial) -- the only two things that
    survive both ways these pages write a name.

    The roster says "Lang, Timothy"; the leadership page says "Tim Lang". The
    roster says "Perkins Kwoka, Rebecca"; the page says "Rebecca Perkins
    Kwoka". A full-name comparison misses the first, and treating the last word
    as the whole surname misses the second. The last word of the surname and
    the first initial survive both, and are checked within one chamber and
    required to land on exactly one member.
    """
    s = WS.sub(" ", (raw or "").strip())
    s = re.sub(r"^(?:Rep|Sen|Representative|Senator)\.?\s+", "", s, flags=re.I)
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    if "," in s:
        surname, _, given = s.partition(",")
    else:
        bits = s.split()
        surname, given = (bits[-1], " ".join(bits[:-1])) if len(bits) > 1 else (s, "")
    sur = (surname.split() or [""])[-1].lower().strip(".'\u2019-")
    ini = (given.strip() or " ")[0].lower()
    return (sur, ini)


def parse(a):
    """Read the saved pages; no request. Writes leadership.json unless --dry."""
    found, seen, missing = [], set(), []
    for key, ch, url, _where in PAGES:
        f = saved(key)
        if not f.exists():
            missing.append(key)
            continue
        t = text_of(f.read_text(encoding="utf-8", errors="replace"))
        if key == "senate-about":
            i = t.find("Senate Leadership")
            t = t[i:] if i >= 0 else t
        got = [x for x in find_roles(t, ch)
               if (x["chamber"], x["role"], x["name"]) not in seen]
        seen.update((x["chamber"], x["role"], x["name"]) for x in got)
        found += got
        print(f"{key}: {len(got)} roles  ({url})")
        if not got:
            # Never read before: show enough to write a pattern against, from
            # the page on disk, at no cost.
            body = [ln for ln in t.splitlines()
                    if 12 < len(ln) < 160 and re.search(r"[A-Z][a-z]+ [A-Z]", ln)]
            print("  nothing matched the labelled shape. Lines that mention a name:")
            for ln in body[:14]:
                print(f"    {ln[:110]}")
    if missing:
        print(f"\nNot saved yet: {', '.join(missing)}. "
              "python3 fetch_leadership.py fetches them.")

    print("\n" + "=" * 62)
    for x in found:
        print(f"  {x['chamber']}  {x['role']:<32} {x['name']} of {x['town']}")
    if not found:
        # Silence is not success: a leadership.json with nobody in it would
        # tell the site nobody leads either chamber.
        print("\nNo roles found, so nothing is written.")
        return 1
    if a.dry:
        print("\nNothing was written (--dry).")
        return 0
    return write(a, found)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="leadership.json")
    ap.add_argument("--plan", action="store_true",
                    help="the addresses and where each is linked; no request")
    ap.add_argument("--parse", action="store_true",
                    help="read the saved pages and write leadership.json; no request")
    ap.add_argument("--dry", action="store_true", help="with --parse: write nothing")
    ap.add_argument("--delay", type=float, default=DELAY,
                    help=f"seconds between requests (at least 5; default {DELAY})")
    a = ap.parse_args()

    if a.plan:
        for page in PAGES:
            key, _ch, url, where = page
            state = "saved" if saved(key).exists() else "wanted"
            print(f"  {key:18} {state:7} {'linked from ' + where if linked(page) else 'NOT LINKED -- would not be asked'}")
            print(f"  {'':18} {url}")
        return 0
    if a.parse:
        return parse(a)

    refusal.check("The leadership fetch")
    with refusal.hold("fetch_leadership") as held:
        rc = fetch(held, delay=max(a.delay, 5))
    if rc == 0:
        print("\nEvery page is saved. python3 fetch_leadership.py --parse reads "
              "them, and asks nothing.")
    return rc


def write(a, found):
    lp = Path(a.data) / "legislators.json"
    if not lp.exists():
        sys.exit(f"No {lp}; run build_data.py first.")
    legs = json.loads(lp.read_text(encoding="utf-8"))
    by_name = {}
    for m in legs:
        by_name.setdefault(name_key(m.get("name", "")), []).append(m)

    out, unmatched = {}, []
    for x in found:
        cands = [m for m in by_name.get(name_key(x["name"]), [])
                 if (m.get("chamber") or "").upper().startswith(x["chamber"])]
        # Exactly one, or nothing. A role on the wrong member is worse than a
        # role that is missing, and two members share a surname often enough.
        if len(cands) == 1:
            rec = out.setdefault(str(cands[0]["id"]),
                                 {"chamber": x["chamber"], "roles": []})
            if x["role"] not in rec["roles"]:
                rec["roles"].append(x["role"])
        else:
            unmatched.append(x)

    if unmatched:
        out["_unmatched"] = unmatched
    # Whole or not at all: a reader of a half-written file sees fewer leaders.
    dest = Path(a.out)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    os.replace(tmp, dest)
    named = len([k for k in out if not k.startswith("_")])
    print(f"\n{named} members with a leadership role -> {a.out}")
    if unmatched:
        print(f"{len(unmatched)} role(s) matched no single member on the roster:")
        for x in unmatched:
            print(f"  {x['role']}: {x['name']} of {x['town']} ({x['chamber']})")
        print("Either the name is written differently on the roster, or two "
              "members\nshare it. Neither is guessed at.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
