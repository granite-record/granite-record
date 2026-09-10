#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.3
"""
Who holds a leadership role in each chamber.

    python3 fetch_leadership.py --probe      # print what the pages say, write nothing
    python3 fetch_leadership.py              # write leadership.json

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
offices each have one, and their shape has never been read, so this fetches
them and prints what it finds rather than guessing at a pattern. Run --probe,
send the output, and the parser can be written against the real thing -- which
is how the member pages and the RSA addresses were done.

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
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
WS = re.compile(r"\s+")
TAG = re.compile(r"<[^>]+>")

SENATE = "https://gc.nh.gov/senate/about_senate/about.aspx"
HOUSE = [("Speaker's office", "https://gc.nh.gov/house/staff/speakersOffice.aspx"),
         ("Majority office", "https://gc.nh.gov/house/staff/majorityOffice.aspx"),
         ("Minority office", "https://gc.nh.gov/house/staff/MinorityOffice.aspx")]

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


# The General Court closes the connection without answering when it is being
# asked for too much at once -- which is what a nightly run looks like from its
# side. urllib reports that as RemoteDisconnected, whose message says nothing
# about the cause, so it is named here instead of left to be puzzled over.
REFUSED = ("remotedisconnected", "connection reset", "connection aborted",
           "closed connection without response", "timed out")


def busy_note():
    """Say the likely reason before the requests start, not after they fail."""
    if Path(".nightly.lock").exists():
        print("NOTE: a nightly run is going, and the General Court will refuse\n"
              "      connections from a second one. Wait for it to finish.\n")


def refused(err):
    return any(w in f"{type(err).__name__} {err}".lower() for w in REFUSED)


def get(url, timeout=60, tries=5):
    """Fetch, backing off properly when the far end is turning us away.

    Two seconds then four is the right shape for a blip and the wrong one for
    throttling, which is what these failures were: six requests across three
    scripts all refused at once while a nightly run held the connection budget.
    Backing off 3, 9, 27 then 60 seconds gives a busy server time to mean it.
    """
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace"), None
        except Exception as e:
            last = e
            if i < tries - 1:
                wait = min(60, 3 ** (i + 1)) + random.uniform(0, 1.5)
                if refused(e):
                    print(f"    refused, waiting {wait:.0f}s "
                          f"({i + 1} of {tries - 1})")
                time.sleep(wait)
    if refused(last):
        return None, (f"{last} -- the General Court refused the connection. "
                      "This is\n  almost always another fetch running at the "
                      "same time; nothing is wrong\n  with the address.")
    return None, last


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="leadership.json")
    ap.add_argument("--probe", action="store_true",
                    help="print what the pages say and write nothing")
    a = ap.parse_args()

    busy_note()
    found = []
    print(f"Senate: {SENATE}")
    html, err = get(SENATE)
    if html is None:
        print(f"  could not fetch: {err}")
    else:
        t = text_of(html)
        i = t.find("Senate Leadership")
        found += find_roles(t[i:] if i >= 0 else t, "S")
        print(f"  {len([x for x in found if x['chamber'] == 'S'])} roles")

    for label, url in HOUSE:
        print(f"\nHouse, {label}: {url}")
        html, err = get(url)
        if html is None:
            print(f"  could not fetch: {err}")
            continue
        t = text_of(html)
        got = find_roles(t, "H")
        found += got
        print(f"  {len(got)} roles")
        if not got and a.probe:
            # The House pages have never been read. Show enough to write a
            # pattern against without another fetch.
            body = [ln for ln in t.splitlines()
                    if 12 < len(ln) < 160 and re.search(r"[A-Z][a-z]+ [A-Z]", ln)]
            print("  nothing matched the labelled shape. Lines that mention a "
                  "name:")
            for ln in body[:14]:
                print(f"    {ln[:110]}")

    print("\n" + "=" * 62)
    for x in found:
        print(f"  {x['chamber']}  {x['role']:<32} {x['name']} of {x['town']}")

    if a.probe:
        print("\nNothing was written. Drop --probe once the list above looks "
              "right.")
        return

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
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    named = len([k for k in out if not k.startswith("_")])
    print(f"\n{named} members with a leadership role -> {a.out}")
    if unmatched:
        print(f"{len(unmatched)} role(s) matched no single member on the roster:")
        for x in unmatched:
            print(f"  {x['role']}: {x['name']} of {x['town']} ({x['chamber']})")
        print("Either the name is written differently on the roster, or two "
              "members\nshare it. Neither is guessed at.")


if __name__ == "__main__":
    main()
