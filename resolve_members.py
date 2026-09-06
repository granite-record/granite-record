#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Put names to the members who voted but are missing from legislators.txt.

420 members appear in RollCallHistory.txt; legislators.txt lists 406. The
difference is people who resigned, died, or were replaced mid-term. Their votes
remain part of the record and their pages should carry their names, not
"Former member #11371".

Members.txt does mark former members (electedStatus = Former), but it carries no
member id, so it cannot be joined to the vote records. The legacy roll call
pages can: each row links the member by id and prints the name beside it.

So: find one roll call each unknown member voted in, fetch that page, read the
name. Roughly a dozen requests, not a scrape.

    python3 resolve_members.py --data data --session 2026

Writes former_members.json, which build_data.py picks up automatically.
"""

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://gc.nh.gov/bill_status/legacy/bs2016/Roll_calls/"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}
MEMBER_ID = re.compile(r"member=(\d+)")


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found, self.cell, self.row, self.mid, self.in_td = {}, [], [], None, False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "td":
            self.in_td, self.cell = True, []
        elif tag == "tr":
            self.row, self.mid = [], None
        elif tag == "a" and "href" in d:
            m = MEMBER_ID.search(d["href"])
            if m:
                self.mid = m.group(1)

    def handle_data(self, data):
        if self.in_td:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td":
            self.in_td = False
            self.row.append(" ".join("".join(self.cell).split()))
        elif tag == "tr":
            if self.mid and len(self.row) >= 4 and self.row[0]:
                self.found[self.mid] = {"name": self.row[0], "party": self.row[1],
                                        "county": self.row[2], "district": self.row[3]}
            self.row, self.mid = [], None


def expand_bill(b):
    m = re.match(r"^([A-Z]+)\s*(\d+)$", b.upper())
    return f"{m.group(1)}{int(m.group(2)):04d}" if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--session", required=True)
    ap.add_argument("--out", default="former_members.json")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--cache", default="rc_pages",
                    help="fetched pages are kept here, so raising --max-requests "
                         "continues where it left off without re-fetching")
    ap.add_argument("--debug", type=int, default=0,
                    help="dump this many raw responses, to tell a bad URL from "
                         "a page that simply lacks these members")
    ap.add_argument("--max-requests", type=int, default=120,
                    help="stop after this many, so a wrong assumption cannot "
                         "turn into an unbounded crawl")
    a = ap.parse_args()

    d = Path(a.dir)
    known = {m["id"] for m in json.loads((Path(a.data) / "legislators.json")
                                         .read_text(encoding="utf-8"))}

    # Which roll calls did each unknown member vote in?
    votes = defaultdict(list)
    with open(d / "RollCallHistory.txt", encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) < 8 or f[0].strip() != a.session:
                continue
            mid = f[4].strip()
            if mid and mid not in known:
                votes[mid].append((f[1].strip(), f[2].strip()))
    if not votes:
        print("Every member who voted is already in legislators.json.")
        return
    print(f"{len(votes)} members to resolve")

    summary, lsr_of = {}, {}
    with open(d / "RollCallSummary.txt", encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) > 4 and f[0].strip() == a.session:
                summary[(f[1].strip(), f[2].strip())] = f[4].strip().upper()
    with open(d / "Docket.txt", encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            f = line.split("|")
            if len(f) > 3 and f[3].strip():
                lsr_of.setdefault(f[3].strip().upper(), f[1].strip().lstrip("0") or "0")

    # Who still needs a name, and which roll calls each voted in.
    want = set(votes)
    calls = defaultdict(set)
    for mid, cs in votes.items():
        for c in cs:
            calls[c].add(mid)

    # The website and the data files use DIFFERENT member id spaces. Susan Almy
    # is 411 in legislators.txt and RollCallHistory.txt, but 376095 in the
    # member= links on the roll call pages. So an id can never be looked up
    # directly.
    #
    # It can be deduced instead. For one roll call the page gives the NAMES who
    # voted yea; the history file gives the IDS who voted yea. Remove everyone
    # already identified and the leftovers on each side must be the same people.
    # One roll call rarely settles it -- several unknowns may share a bucket --
    # but each additional roll call narrows the candidates, and a member's
    # pattern of votes across a session is effectively unique.
    VOTE_COL = {1: "Yea", 2: "Nay", 3: None, 4: None}   # 3/4 are the absence pages

    known_names = {m["name"] for m in json.loads(
        (Path(a.data) / "legislators.json").read_text(encoding="utf-8"))}

    hist = defaultdict(lambda: defaultdict(set))     # (body,num) -> vote -> ids
    with open(d / "RollCallHistory.txt", encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) < 8 or f[0].strip() != a.session:
                continue
            hist[(f[1].strip(), f[2].strip())][f[6].strip()].add(f[4].strip())

    candidates = {mid: None for mid in want}         # None = not yet constrained
    name_rec = {}                                    # name -> row, for lookups
    resolved, tried, fails, skipped, cached = {}, 0, {}, 0, 0
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)

    print(f"{len(calls)} candidate roll calls, busiest first\n")
    for call, members in sorted(calls.items(), key=lambda kv: -len(kv[1])):
        if not (want - set(resolved)):
            break
        if tried >= a.max_requests:
            print(f"\nStopped at {a.max_requests} requests. "
                  "Raise --max-requests to keep going.")
            break
        body, num = call
        bill = summary.get(call, "")
        eb, lsr = expand_bill(bill), lsr_of.get(bill)
        if not eb or not lsr:
            skipped += 1
            continue

        page = {}
        for yn in (1, 2):
            q = urllib.parse.urlencode({"yn": yn, "sy": a.session, "vs": num,
                                        "lb": body, "eb": eb, "sortoption": "",
                                        "txtsessionyear": a.session,
                                        "ddlsponsors": "", "lsr": lsr})
            cpath = cache / f"{body}_{num}_{yn}.html"
            if cpath.exists():
                html = cpath.read_text(encoding="utf-8", errors="replace")
                cached += 1
            else:
              try:
                time.sleep(a.delay)
                tried += 1
                req = urllib.request.Request(BASE + "rc_yeahnay.aspx?" + q, headers=UA)
                with urllib.request.urlopen(req, timeout=45) as r:
                    html = r.read().decode("utf-8", errors="replace")
                cpath.write_text(html, encoding="utf-8")
              except (urllib.error.URLError, urllib.error.HTTPError) as e:
                fails[f"{type(e).__name__}: {e}"] = fails.get(
                    f"{type(e).__name__}: {e}", 0) + 1
                continue
            pr = Rows()
            pr.feed(html)
            page[VOTE_COL[yn]] = {v["name"]: v for v in pr.found.values()}

        def propagate():
            """A resolved name is nobody else's. Removing it can leave another
            set with one member, which resolves in turn -- so repeat until
            nothing changes. This finishes pairs that voted identically on every
            roll call fetched, with no further requests."""
            changed = True
            while changed:
                changed = False
                taken = {r["name"] for r in resolved.values()}
                for mid, cs in candidates.items():
                    if mid in resolved or not cs:
                        continue
                    trimmed = cs - taken
                    if trimmed != cs:
                        candidates[mid] = trimmed
                        changed = True
                    if len(trimmed) == 1:
                        nm = next(iter(trimmed))
                        rec = name_rec.get(nm)
                        # Claim the name immediately. Waiting until the next
                        # pass let two members both take it, because `taken`
                        # was still stale when the second one was checked.
                        if rec and nm not in taken:
                            resolved[mid] = rec
                            taken.add(nm)
                            print(f"    {mid:<8} -> {rec['name']} ({rec['party']}) "
                                  f"{rec['county']} {rec['district']}  [by elimination]",
                                  flush=True)
                            changed = True

        narrowed = 0
        for vote, seen in page.items():
            name_rec.update(seen)
            ids = hist[call].get(vote, set())
            unknown_ids = {i for i in ids if i in want and i not in resolved}
            unknown_names = {n: v for n, v in seen.items() if n not in known_names}
            if not unknown_ids or not unknown_names:
                continue
            for mid in unknown_ids:
                prev = candidates.get(mid)
                nxt = set(unknown_names) if prev is None else prev & set(unknown_names)
                candidates[mid] = nxt
                if len(nxt) == 1:
                    nm = next(iter(nxt))
                    resolved[mid] = seen[nm]
                    narrowed += 1
                    print(f"    {mid:<8} -> {seen[nm]['name']} ({seen[nm]['party']}) "
                          f"{seen[nm]['county']} {seen[nm]['district']}", flush=True)
        propagate()
        left = len(want) - len(resolved)
        sizes = [len(v) for k, v in candidates.items()
                 if v is not None and k not in resolved]
        print(f"  {body}{num} {bill}: {left} unresolved"
              + (f", narrowest candidate set {min(sizes)}" if sizes else ""), flush=True)

    # Anyone still unconstrained never appeared in a yea or nay list, because
    # they were absent, excused or presiding for every roll call fetched. Those
    # people are on yn=3 and yn=4 -- the absence pages -- which the main pass
    # skips because they contribute nothing to a vote-pattern match. Pool both
    # pages against every non-yea/nay id and the same elimination applies.
    stuck = [m for m in (want - set(resolved)) if not candidates.get(m)]
    if stuck:
        print(f"\n{len(stuck)} never voted yea or nay. Checking the absence pages.")
        for call, members in sorted(calls.items(), key=lambda kv: -len(kv[1])):
            if not [m for m in stuck if m not in resolved]:
                break
            if tried >= a.max_requests + 40:
                break
            body, num = call
            bill = summary.get(call, "")
            eb, lsr = expand_bill(bill), lsr_of.get(bill)
            if not eb or not lsr:
                continue
            absent_names = {}
            for yn in (3, 4):
                q = urllib.parse.urlencode({"yn": yn, "sy": a.session, "vs": num,
                                            "lb": body, "eb": eb, "sortoption": "",
                                            "txtsessionyear": a.session,
                                            "ddlsponsors": "", "lsr": lsr})
                cpath = cache / f"{body}_{num}_{yn}.html"
                if cpath.exists():
                    html = cpath.read_text(encoding="utf-8", errors="replace")
                    cached += 1
                else:
                    try:
                        time.sleep(a.delay)
                        tried += 1
                        req = urllib.request.Request(
                            BASE + "rc_yeahnay.aspx?" + q, headers=UA)
                        with urllib.request.urlopen(req, timeout=45) as r:
                            html = r.read().decode("utf-8", errors="replace")
                        cpath.write_text(html, encoding="utf-8")
                    except (urllib.error.URLError, urllib.error.HTTPError):
                        continue
                pr = Rows()
                pr.feed(html)
                absent_names.update({v["name"]: v for v in pr.found.values()})
            name_rec.update(absent_names)
            unknown_names = {n for n in absent_names if n not in known_names}
            absent_ids = {i for v, ids in hist[call].items()
                          if v not in ("Yea", "Nay") for i in ids}
            for mid in [m for m in stuck if m not in resolved and m in absent_ids]:
                prev = candidates.get(mid)
                candidates[mid] = unknown_names if not prev else prev & unknown_names
            propagate()
            left = [m for m in stuck if m not in resolved]
            if left:
                print(f"  {body}{num}: {len(left)} still unnamed, narrowest "
                      f"{min(len(candidates[m] or []) for m in left)}", flush=True)

    propagate()

    # Last resort, and it costs nothing. Members.txt marks people who left with
    # electedStatus = Former. It carries no member id, which is why it could not
    # be used directly -- but once the others are named, a single unclaimed
    # Former name against a single unresolved id is a determination, not a guess.
    missing = want - set(resolved)
    mp = d / "Members.txt"
    if missing and mp.exists():
        formers = []
        with open(mp, encoding="utf-8-sig", errors="replace") as fh:
            head = next(fh).rstrip("\n").split("\t")
            col = {n.lower(): i for i, n in enumerate(head)}
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) <= col.get("electedstatus", 99):
                    continue
                if f[col["electedstatus"]].strip().lower() != "former":
                    continue
                formers.append({
                    "name": f"{f[col['lastname']].strip()}, {f[col['firstname']].strip()}",
                    "party": f[col["party"]].strip().upper(),
                    "county": f[col["county"]].strip(),
                    "district": f[col["district"]].strip()})
        taken = {r["name"] for r in resolved.values()} | known_names
        spare = [x for x in formers if x["name"] not in taken]
        print(f"\nMembers.txt lists {len(formers)} former members; "
              f"{len(spare)} are unaccounted for")
        if len(spare) == 1 and len(missing) == 1:
            mid = next(iter(missing))
            resolved[mid] = spare[0]
            print(f"    {mid:<8} -> {spare[0]['name']} ({spare[0]['party']}) "
                  f"{spare[0]['county']} {spare[0]['district']}  "
                  "[only unclaimed former member]")
        elif spare:
            print("  candidates, if you want to match them by hand:")
            for x in spare:
                print(f"    {x['name']} ({x['party']}) {x['county']} {x['district']}")
            for mid in sorted(missing):
                cs = candidates.get(mid)
                print(f"    id {mid} could be: {sorted(cs) if cs else 'unconstrained'}")

    Path(a.out).write_text(json.dumps(resolved, indent=2), encoding="utf-8")
    print(f"\n{len(resolved)}/{len(votes)} resolved in {tried} requests "
          f"({cached} pages from cache) -> {a.out}")
    if skipped:
        print(f"{skipped} roll calls skipped: no bill number, or no LSR for it "
              "in Docket.txt (procedural votes have neither)")
    if fails:
        print("request failures:")
        for k, n in sorted(fails.items(), key=lambda x: -x[1])[:5]:
            print(f"  {n:>4}x  {k}")
    missing = want - set(resolved)
    if missing:
        print("still unnamed:", ", ".join(sorted(missing)))
        for mid in sorted(missing):
            cs = candidates.get(mid)
            print(f"  {mid}: {sorted(cs) if cs else 'no constraint yet'}")
        print("Raise --max-requests to keep going; cached pages are not refetched.")
        print("A member who never cast a roll call vote would not appear here at "
              "all, so everyone listed did vote at least once.")


if __name__ == "__main__":
    main()
