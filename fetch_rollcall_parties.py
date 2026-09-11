#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.2
"""The party of everyone who voted before 2017, from one roll call a chamber a year.

    python3 fetch_rollcall_parties.py --plan     # which votes, no network
    python3 fetch_rollcall_parties.py --probe 4  # four of them, then report
    python3 fetch_rollcall_parties.py --budget 60
    python3 fetch_rollcall_parties.py --parse    # no network at all

WHY

24 years of roll calls came off the database dump on 10 September and
773,506 of their ballots carry no party: 88% of 1999-2000, 57% of
2011-2012, 6% of 2015-2016. No roster on this disk names those people's
party, and inferring one -- from a later namesake, or from how somebody
voted -- would fabricate the fact a reader is most likely to act on.

A person found the page that has it. The legacy roll call detail carries
every member's PARTY, county and district beside their vote:

    Adams, Jarvis   Republican   Hillsborough   02   Nay
    Zolla, William  Republican   Rockingham     05   Yea

and it is addressed by exactly what RollCallSummary already gives:

    Roll_calls/billstatus_rcdetails.aspx?sy=2004&vs=46&lb=H

Checked by hand: the bill number, the LSR and the other five parameters the
site's own link carries are ignored -- the same 388 rows come back without
them.

WHY IT IS ~50 REQUESTS AND NOT 8,061

A party is a fact about a member in a term, not about a vote. One House roll
call lists 387 of about 400 representatives -- absentees included, since the
page prints Excused, Not Voting and Presiding as well as Yea and Nay -- so
the fullest roll call of a year names almost the whole chamber at one
request. This takes the largest vote per (year, chamber), measures what it
covered, and only then asks for a second where a year is still short.

HOW IT JOINS

Not by name against a roster, which is the guess this project keeps having to
undo. The page and `rollcalls/RollCallHistory_<year>.txt` describe THE SAME
VOTE, so the two lists are aligned within it: our side has Employeeno and a
name, the page has a name and a party, and the pair (name, district) settles
the handful of members who share a surname and forename -- "Adams, Jarvis"
sits in Hillsborough 02 and Hillsborough 31 in the same chamber.

GENTLE, AND IT STOPS

15 seconds apart, --budget, two refusals ends it, refusal.py holds one for 24
hours, and every answer is saved gzipped and never asked for twice.
"""

import argparse
import collections
import gzip
import html as _html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import past_members
import refusal

URL = ("https://gc.nh.gov/bill_status/legacy/bs2016/Roll_calls/"
       "billstatus_rcdetails.aspx?sy={year}&vs={vs}&lb={body}")
RC = Path("rollcalls")
OUT = Path("rollcall_party_pages")
RESULT = Path("member_party.json")
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
PARTY = {"republican": "R", "democrat": "D", "democratic": "D",
         "independent": "I", "libertarian": "L"}
ERROR_PAGE = re.compile(
    r"is either negative or above rows count|is neither a DataColumn", re.I)

# County as the page spells it, against the abbreviation every other file on
# this disk uses. Read off the pages rather than invented: the page writes
# "Hillsborough" where past_members.json writes "Hills".
COUNTY = {"belknap": "Belk", "carroll": "Carr", "cheshire": "Ches",
          "coos": "Coos", "grafton": "Graf", "hillsborough": "Hills",
          "merrimack": "Merr", "rockingham": "Rock", "strafford": "Straf",
          "sullivan": "Sull"}


def flat(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def parse(page):
    """[{name, party, county, district, vote}] -- the ballot table."""
    out = []
    for tr in ROW.findall(page):
        cells = [flat(_html.unescape(c)) for c in CELL.findall(tr)]
        if len(cells) != 5:
            continue
        name, party, county, district, vote = cells
        key = party.strip().lower()
        if key not in PARTY:
            continue                      # the header row, and anything else
        out.append({"name": name, "party": PARTY[key],
                    "county": COUNTY.get(county.strip().lower(), county.strip()),
                    "district": district.strip(), "vote": vote})
    return out


def summaries():
    """[(year, body, vs, voters)] for every roll call on disk, fullest first."""
    got = []
    for f in sorted(RC.glob("RollCallSummary_*.txt")):
        for line in f.open(encoding="utf-8-sig", errors="replace"):
            p = line.rstrip("\n").split("|")
            if len(p) < 9 or not p[0].strip().isdigit():
                continue
            nums = [int(x) if x.strip().lstrip("-").isdigit() else 0
                    for x in p[5:9]]
            got.append((int(p[0]), p[1].strip(), p[2].strip(), sum(nums)))
    got.sort(key=lambda r: -r[3])
    return got


def plan(per_slot=1):
    """The fullest roll call of each (year, chamber): the most names per request."""
    seen = collections.Counter()
    out = []
    for year, body, vs, voters in summaries():
        if not body:
            continue
        if seen[(year, body)] >= per_slot:
            continue
        seen[(year, body)] += 1
        out.append((year, body, vs, voters))
    out.sort()
    return out


def page_path(year, body, vs):
    return OUT / str(year) / f"{body}{vs}.html.gz"


def fetch(year, body, vs, delay):
    p = page_path(year, body, vs)
    if p.exists():
        return "cached"
    time.sleep(delay)
    url = URL.format(year=year, vs=vs, body=body)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            page = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            refusal.note("fetch_rollcall_parties", f"HTTP {e.code} on {url}")
            return "refused"
        return "missing"
    except (urllib.error.URLError, TimeoutError):
        return "missing"
    if ERROR_PAGE.search(page[:6000]):
        return "error page"
    if not parse(page):
        return "no ballots"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(page.encode("utf-8"), 6))
    return "saved"


def history(year):
    """{(name, district): employeeno} for one year, from the roll call history.

    The name comes from past_members.json, which is how a pre-2017 ballot got
    a name at all; a member that file does not carry cannot be matched here
    either, and is counted rather than guessed at.
    """
    people = past_members.roster()
    out = {}
    f = RC / f"RollCallHistory_{year}.txt"
    if not f.exists():
        return out
    for line in f.open(encoding="utf-8-sig", errors="replace"):
        p = line.rstrip("\n").split("|")
        if len(p) < 8:
            continue
        emp = p[3].strip()
        who = people.get(emp)
        if who:
            out[(who["name"].lower(), who["district"].lstrip("0"))] = emp
    return out


def harvest():
    """{employeeno: {party, county, district, source}} from what is saved."""
    found, clash, unmatched = {}, 0, collections.Counter()
    for d in sorted(OUT.glob("*")):
        if not d.is_dir() or not d.name.isdigit():
            continue
        year = int(d.name)
        index = history(year)
        for f in sorted(d.glob("*.html.gz")):
            page = gzip.decompress(f.read_bytes()).decode("utf-8")
            for row in parse(page):
                emp = index.get((row["name"].lower(),
                                 row["district"].lstrip("0")))
                if not emp:
                    unmatched[year] += 1
                    continue
                prev = found.get(emp)
                if prev and prev["party"] != row["party"]:
                    clash += 1
                    continue
                found[emp] = {"party": row["party"], "county": row["county"],
                              "district": row["district"],
                              "source": f"{year}-{f.stem.split('.')[0]}"}
    return found, clash, unmatched


# --------------------------------------------------------------- solving --

def _vote_class(v):
    v = (v or "").strip().lower()
    return "Y" if v.startswith("yea") else "N" if v.startswith("nay") else "A"


def _name_key(printed):
    """"Adams, Jarvis" -> ("adams", "jarvis"), the shape db/Legislators.psv has."""
    parts = [x.strip() for x in (printed or "").split(",")]
    last = re.sub(r"[^a-z]", "", parts[0].lower()) if parts else ""
    first = re.sub(r"[^a-z]", "", parts[-1].lower()) if len(parts) > 1 else ""
    return (last, first)


def _legislator_ids():
    """{(surname, forename): employeeno}, only where the pair names one person."""
    out = collections.defaultdict(set)
    f = Path("db/Legislators.psv")
    if not f.exists():
        return {}
    for line in f.open(encoding="utf-8", errors="replace"):
        c = line.rstrip("\n").split("|")
        if len(c) > 3 and c[3].strip():
            out[(re.sub(r"[^a-z]", "", c[1].lower()),
                 re.sub(r"[^a-z]", "", c[2].lower()))].add(c[3].strip())
    return {k: next(iter(v)) for k, v in out.items() if len(v) == 1}


def _ballots(year):
    """{(year, body, vs): {employeeno: vote class}} for one year's roll calls."""
    out = collections.defaultdict(dict)
    f = RC / f"RollCallHistory_{year}.txt"
    if not f.exists():
        return out
    for line in f.open(encoding="utf-8-sig", errors="replace"):
        c = line.rstrip("\n").split("|")
        if len(c) >= 8:
            out[(year, c[1].strip(), c[2].strip())][c[3].strip()] = _vote_class(c[6])
    return out


def solve():
    """{employeeno: {name, party, county, district}} for rows the join misses.

    NOT A GUESS FROM A NAMESAKE. Three constraints, all of them facts already
    on this disk:

      a printed row must be one of THAT roll call's voters -- the page and
      rollcalls/RollCallHistory_<year>.txt describe the same vote;
      it must have cast the vote the page prints beside the name;
      and a person printed on several pages must be the same employeeno on
      every one of them.

    Where db/Legislators.psv names a row outright it is pinned, which settles
    that row and takes its employeeno out of every other row's candidates on
    the same page. Then the ordinary sudoku step: a row with one candidate
    left claims it, and everybody else loses it.

    MEASURED BEFORE IT WAS USED. People the ordinary join already answers were
    hidden in samples of 10, 25, 50, 100 and 200, their employeenos returned
    to the pool, and the solver asked to find them again: 286 pinned, 286
    correct, 0 wrong. It declines far more often than it errs, which is the
    property that matters -- a wrong pin files one member's votes under
    another's name, and that is what preflight's "every voter in the record is
    one person" exists to catch.
    """
    legis = _legislator_ids()
    pages = []
    for d in sorted(Path(OUT).glob("*")):
        if not d.is_dir() or not d.name.isdigit():
            continue
        year = int(d.name)
        votes = _ballots(year)
        index = history(year)
        for f in sorted(d.glob("*.html.gz")):
            stem = f.name.split(".")[0]
            key = (year, stem[0], stem[1:])
            rows = parse(gzip.decompress(f.read_bytes()).decode("utf-8"))
            pages.append((key, rows, votes.get(key, {}), index))

    cand = collections.defaultdict(dict)
    seen = {}
    for key, rows, votes, index in pages:
        matched, unm = set(), []
        for r in rows:
            e = index.get((r["name"].lower(), r["district"].lstrip("0")))
            if e:
                matched.add(e)
            else:
                unm.append(r)
        pool = {e: v for e, v in votes.items() if e not in matched}
        for r in unm:
            who = (r["name"], r["county"], r["party"])
            seen[who] = r
            want = _vote_class(r["vote"])
            pin = legis.get(_name_key(r["name"]))
            if pin and pool.get(pin) == want:
                cand[who].setdefault("PIN", set()).add(pin)
            cand[who][key] = {e for e, v in pool.items() if v == want}

    space = {}
    for who, per in cand.items():
        pin = per.pop("PIN", None)
        sets = list(per.values())
        keep = set.intersection(*sets) if sets else set()
        if pin:
            keep = (keep & pin) or pin
        space[who] = keep
    changed = True
    while changed:
        changed = False
        taken = {next(iter(s)) for s in space.values() if len(s) == 1}
        for s in space.values():
            if len(s) != 1 and (s & taken):
                s -= taken
                changed = True

    out = {}
    for who, s in space.items():
        if len(s) != 1:
            continue
        r = seen[who]
        out[next(iter(s))] = {"name": r["name"], "party": r["party"],
                              "county": r["county"], "district": r["district"],
                              "source": "solved"}
    return out, len(seen)


def report():
    found, clash, unmatched = harvest()
    print(f"{len(found):,} members given a party, from "
          f"{len(list(OUT.rglob('*.html.gz'))):,} saved roll calls")
    if clash:
        print(f"  {clash:,} rows disagreed with a party already found and were "
              "dropped rather than overwritten")
    if unmatched:
        print("  ballot rows that matched no member on this disk, by year: "
              + ", ".join(f"{y}:{n}" for y, n in sorted(unmatched.items())))
    mv = Path("data/member_votes.json")
    if mv.exists():
        votes = json.loads(mv.read_text(encoding="utf-8"))
        nop = [v for v in votes if (v.get("party") or "X") == "X"]
        would = [v for v in nop if str(v.get("member_id")) in found]
        print()
        print(f"{len(nop):,} ballots carry no party; {len(would):,} "
              f"({100 * len(would) // max(len(nop), 1)}%) would gain one")
    if found:
        RESULT.write_text(json.dumps(found, indent=1, sort_keys=True),
                          encoding="utf-8")
        print(f"-> {RESULT}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true",
                    help="which roll calls would be asked for; no network")
    ap.add_argument("--probe", type=int, default=0)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--each", type=int, default=1,
                    help="roll calls per (year, chamber)")
    ap.add_argument("--delay", type=float, default=15.0)
    ap.add_argument("--stop-refused", type=int, default=2)
    ap.add_argument("--parse", action="store_true")
    ap.add_argument("--solve", action="store_true",
                    help="pin the printed rows the join misses; no network")
    a = ap.parse_args()

    if a.solve:
        found, printed = solve()
        print(f"{printed} printed people the join does not answer; "
              f"{len(found)} pinned by constraint")
        have = {}
        if RESULT.exists():
            have = json.loads(RESULT.read_text(encoding="utf-8"))
        added = 0
        for mid, rec in found.items():
            # MERGE, NEVER REBUILD. A writer of a derived file run on a subset
            # destroys the rest, and this one is a subset by construction.
            if mid not in have:
                have[mid] = rec
                added += 1
        RESULT.write_text(json.dumps(have, indent=1, sort_keys=True),
                          encoding="utf-8")
        print(f"{added} new, {len(have)} in {RESULT}")
        return 0
    if a.parse:
        return report()
    todo = plan(a.each)
    if a.plan:
        print(f"{len(todo)} roll calls, the fullest of each year and chamber:")
        for year, body, vs, voters in todo:
            print(f"  {year} {body} vote {vs:>4}  {voters:>3} voters")
        print(f"\n{len(todo)} requests at {a.delay:g}s is "
              f"{len(todo) * a.delay / 60:.0f} minutes.")
        return 0
    if not (a.probe or a.budget):
        sys.exit("give --budget N or --probe N, so a run always has an end. "
                 f"--plan lists the {len(todo)} it would ask for.")

    refusal.check("The roll call party fetch")
    if a.probe:
        todo = todo[:a.probe]
    budget = a.budget or len(todo)
    print(f"{len(todo)} roll calls, {budget} requests this run, {a.delay:g}s apart")
    tally, refused, spent = collections.Counter(), 0, 0
    for year, body, vs, _voters in todo:
        if spent >= budget:
            break
        what = fetch(year, body, vs, a.delay if tally else 0)
        tally[what] += 1
        if what != "cached":
            spent += 1
        print(f"  {year} {body} {vs}: {what}")
        if what == "refused":
            refused += 1
            if refused >= a.stop_refused:
                print(f"\n{refused} refusals. Stopping; refusal.py holds one "
                      "for 24 hours. netcheck.py says what kind it is.")
                return 2
    print()
    print(", ".join(f"{v} {k}" for k, v in tally.most_common()))
    return report()


if __name__ == "__main__":
    sys.exit(main())
