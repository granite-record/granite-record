#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.3
"""Who sponsored what, asked one legislator at a time instead of one bill at a time.

    python3 fetch_sponsors_by_member.py --plan        # no network at all
    python3 fetch_sponsors_by_member.py --members     # the roster, 1 request
    python3 fetch_sponsors_by_member.py --probe 6     # a handful, and score them
    python3 fetch_sponsors_by_member.py --budget 200  # fetch, then stop
    python3 fetch_sponsors_by_member.py --parse       # read the disk; no network

WHY THIS AND NOT ONE PAGE PER BILL

Seventeen of nineteen terms have no sponsors: data/sponsors.json holds
2023-2024 and 2025-2026 and nothing else. The obvious route is the bill's own
text -- gc.nh.gov/legislation/<year>/<BILL>.html carries "SPONSORS:" -- and
that is 33,000 requests for the archive.

byAnyMember.aspx asks the other way round. It offers past and present
legislators in one list, has NO session-year selector, and returns a member's
whole career in one answer:

    Year   Bill #    Status                Title
    1989   HB175     SIGNED BY GOVERNOR    relative to bail commissioners' fees.
    1990   HB1092    SIGNED BY GOVERNOR    (2nd New Title) relative to low and ...

Two requests a member -- Prime Sponsored, then CoSponsored -- covers every
term from 1989 to 2026 for a few thousand requests rather than tens of
thousands.

It is also better data. Each row links
billinfo.aspx?sy=1989&Pastid=<lsr><year>, so the LSR is in the address and the
join to data/bills.json is exact rather than a guess at which "Rep. Allard" is
meant; and a member's own list states whether they were PRIME or a
co-sponsor, where the status page infers it from the order names are printed
in (`prime_inferred: True` on every archived row that route would give us).

WHAT IS NOT KNOWN YET, AND WHY THE FIRST RUN IS SIX REQUESTS

**No page from this endpoint is on disk.** Every regex below was written from
markup read during a survey, not from a saved artefact, and this file's own
rule is to read the artefact before modelling it. So the parser is a
hypothesis, and --probe is the experiment:

  --members   one GET: the member list, the hidden fields, and the real
              markup of the form, saved to sponsors_form.html.
  --probe N   N members, both modes, SCORED AGAINST data/sponsors.json.

The scoring is the point. 2023-2026 sponsors came from the General Court's
own database, not from this script, so a member who prime-sponsored HB1234 in
2025 according to the database must appear with HB1234 in their Prime list
here. That one comparison tests four things at once that no amount of reading
the HTML can settle: whether parse_rows finds rows at all, whether MODES maps
"prime" to the right radio value, whether this list's member ids are the same
ids the database uses, and whether a member's list really does reach back
across terms.

A sweep of thousands of requests before that comparison has been run would be
a sweep on a guess.

THE ONE KNOWN GAP, MEASURED BEFORE THIS IS TRUSTED

HB1 of 1989 is a SPECIAL SESSION bill, LSR 1989-9100, and its own text names
Rep. Vartanian. It appears in neither of her lists. Whether special sessions
are absent from this view or filed under another year is not known from one
sample. --probe reports it where the sample reaches it.

HOW THE PAGE WORKS

An ASP.NET postback. One GET yields __VIEWSTATE (about 135 KB),
__EVENTVALIDATION (about 56 KB) and the whole member list; each POST sets
__EVENTTARGET, the member and the radio. The tokens are reused across members
-- EVENTVALIDATION validates that the posted member is one of the listed
options, and every member is listed -- and are refetched when the server
stops accepting them.

THE ANSWER MUST BE THE MEMBER ASKED FOR

615 bills of 2023-2024 were one address rule away from being saved under
another bill's name in fetch_legislation, and nothing would have said so.
The same mistake here is worse: a postback that quietly returns the previous
member's list would file one legislator's whole career under another's, and
--parse would report it as fact. So every answer is checked against the
member and the mode that were posted, read back out of the page's own
selected <option> and checked radio, and a page that disagrees is never
written. Where the markup carries neither, the answer is counted
"unverified", saved for a person to read, and a sweep refuses to start.

GENTLE, AND IT STOPS

One worker or none (refusal.hold, the same lock every other fetcher takes),
15 seconds between requests with jitter, --budget to end a run early, a
refusal ends it at once and two dropped connections do too, and refusal.py
keeps every other fetcher stopped for 24 hours afterwards. Every answer is
saved gzipped under sponsors_pages/ and never asked for twice, so the parser
can be wrong as often as it likes without costing a request. This address has
been blocked twice.
"""

import argparse
import gzip
import html as _html
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import child  # noqa: F401  (kept so the module list stays uniform)
import refusal

URL = "https://gc.nh.gov/bill_Status/byAnyMember.aspx"
OUT = Path("sponsors_pages")
ROSTER = Path("sponsors_members.json")
FORM = Path("sponsors_form.html")
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}

HIDDEN = re.compile(r"<input[^>]+type=[\"']hidden[\"'][^>]*>", re.I)
ATTR = re.compile(r"([\w:$-]+)\s*=\s*[\"']([^\"']*)[\"']")
OPTION = re.compile(r"<option([^>]*)>(.*?)</option>", re.I | re.S)
VALUE = re.compile(r"value\s*=\s*[\"'](\d+)[\"']", re.I)
SELECTED = re.compile(r"\bselected\b", re.I)
# The radio pair that chooses Prime or Co. Read back out of the answer to
# prove the mode that came back is the mode that was posted.
RADIO = re.compile(r"<input[^>]*type=[\"']radio[\"'][^>]*>", re.I)

# A result row is one <tr>, and inside it the four fields are DIVs in a
# single cell rather than four <td>s: the year, the bill as a link, the
# status, and the title behind a <b>title:</b> label. Written against the
# real markup of Rep. Vartanian's answer, because the RENDERED table is one
# column and a parser built from what it looks like finds nothing.
TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
LINK = re.compile(
    r"billinfo\.aspx\?sy=(?P<sy>\d{4})&(?:amp;)?Pastid=(?P<pastid>\d+)"
    r"[^>]*>(?P<bill>.*?)</a>", re.I | re.S)
COL = re.compile(r"<div class=\"col-sm(?:-2)?\">(.*?)</div>", re.I | re.S)
TITLE = re.compile(r"<b>\s*title:\s*</b>(.*?)</div>", re.I | re.S)
# What the application says instead of failing. Met on the sibling endpoint:
# a wrong id answers with an error inside an HTTP 200, not a 404.
ERROR_PAGE = re.compile(
    r"is either negative or above rows count|is neither a DataColumn", re.I)

MODES = {"prime": "0", "co": "1"}
MEMBER_FIELD = "ctl00$pageBody$lstMembers"
MODE_FIELD = "ctl00$pageBody$rdoPrime"

HOLD = None          # set in main(); None when nothing is holding the lock


def flat(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def get(url, data=None, timeout=90):
    req = urllib.request.Request(
        url, data=data,
        headers=dict(UA, **({"Content-Type":
                             "application/x-www-form-urlencoded"} if data else {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def tokens(page):
    """The hidden fields a postback has to carry back."""
    out = {}
    for m in HIDDEN.finditer(page):
        a = {k.lower(): v for k, v in ATTR.findall(m.group(0))}
        if a.get("name"):
            out[a["name"]] = _html.unescape(a.get("value", ""))
    return out


def members(page):
    """[(id, label)] -- every legislator the list offers, in its own order."""
    out, seen = [], set()
    for attrs, label in OPTION.findall(page):
        v = VALUE.search(attrs)
        text = flat(_html.unescape(label))
        if not v or v.group(1) in seen or not text:
            continue
        seen.add(v.group(1))
        out.append((v.group(1), text))
    return out


def selected_member(page):
    """The member id the ANSWER says it is about, or None if it does not say.

    ASP.NET marks the chosen option `selected="selected"`. None is not a
    pass: it means this page cannot be checked, and the caller says so
    rather than assuming the answer is the one asked for.
    """
    for attrs, _label in OPTION.findall(page):
        if SELECTED.search(attrs):
            v = VALUE.search(attrs)
            if v:
                return v.group(1)
    return None


def checked_mode(page):
    """The radio value the answer carries back, or None if it does not say."""
    for tag in RADIO.findall(page):
        a = {k.lower(): v for k, v in ATTR.findall(tag)}
        if MODE_FIELD.lower() not in (a.get("name") or "").lower():
            continue
        if re.search(r"\bchecked\b", tag, re.I):
            return a.get("value")
    return None


def parse_rows(page):
    """[{lsr, year, bill, status, title}] out of one member's answer.

    Keyed on the link rather than on position, because the header row
    carries the same four divs and would otherwise parse as a bill.
    """
    rows = []
    for tr in TR.findall(page):
        link = LINK.search(tr)
        if not link:
            continue
        sy, pastid = link.group("sy"), link.group("pastid")
        # Pastid is the LSR with the session year stuck on the end: HB750
        # of 1989 is LSR 1171 and its Pastid is 11711989. That is the
        # exact join key to data/bills.json, and the reason this route
        # beats matching a surname against a roster.
        lsr = pastid[:-4] if pastid.endswith(sy) and len(pastid) > 4 else ""
        cols = [flat(_html.unescape(c)) for c in COL.findall(tr)]
        title = TITLE.search(tr)
        rows.append({
            "lsr": lsr,
            "year": sy,
            "bill": re.sub(r"\s+", "",
                           flat(_html.unescape(link.group("bill")))),
            # cols is [year, bill, status, title]; the status is the
            # third, and is empty rather than wrong where it is absent.
            "status": cols[2].strip(" -| ") if len(cols) > 2 else "",
            "title": (flat(_html.unescape(title.group(1))).lstrip("  ")
                      if title else ""),
        })
    return rows


def page_path(mid, mode):
    return OUT / mode / f"{mid}.html.gz"


def write_atomically(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def save(mid, mode, page):
    write_atomically(page_path(mid, mode),
                     gzip.compress(page.encode("utf-8"), 6))


def load(mid, mode):
    p = page_path(mid, mode)
    return gzip.decompress(p.read_bytes()).decode("utf-8") if p.exists() else None


def fetch_member(mid, mode, form, delay):
    """One answer, saved. Returns (outcome, form, detail).

    Outcomes that asked nothing: "cached", "halted".
    Outcomes that asked: "saved", "unverified" (saved, but the page does not
    say who it is about), "wrong member", "wrong mode" (not saved),
    "error page", "stale" (tokens rejected), "refused", "dropped",
    "missing", "failed".
    """
    if page_path(mid, mode).exists():
        return "cached", form, ""
    time.sleep(delay * random.uniform(0.75, 1.25) if delay else 0)
    # A refusal another process met while this one slept is a refusal here
    # too -- so this is asked AFTER the sleep, directly before the request.
    if refusal.MARK.exists():
        return "halted", form, "archive/refused.json is on file"
    if HOLD is not None and not HOLD.still():
        return "halted", form, "the lane holding archive/.lock is gone"
    fields = dict(form)
    fields.update({
        "__EVENTTARGET": MEMBER_FIELD,
        "__EVENTARGUMENT": "",
        MEMBER_FIELD: mid,
        MODE_FIELD: MODES[mode],
    })
    try:
        page = get(URL, urllib.parse.urlencode(fields).encode())
    except Exception as e:
        # One reading of an error for every fetcher: a reset or a timeout
        # wrapped in a URLError is a dropped connection, not a failure, and
        # a 503 or a Retry-After is the server asking us to go away.
        kind = refusal.classify(e)
        why = (f"HTTP {e.code} on {URL}" if isinstance(e, urllib.error.HTTPError)
               else f"{type(e).__name__}: {e}")
        if isinstance(e, urllib.error.HTTPError) and e.code == 500:
            # The tokens went stale. One GET replaces them; it is a request,
            # so it is counted like any other.
            return "stale", form, why
        return kind, form, why
    if refusal.classify(body=page) == "refused":
        return "refused", form, "the firewall's block page, with a 200"
    if ERROR_PAGE.search(page[:6000]):
        return "error page", form, ""
    # THE ANSWER MUST BE THE MEMBER ASKED FOR. A postback that returns the
    # previous member's list would file one legislator's career under
    # another's, and --parse would report it as fact.
    said = selected_member(page)
    if said is not None and said != mid:
        return "wrong member", form, f"asked {mid}, the page says {said}"
    said_mode = checked_mode(page)
    if said_mode is not None and said_mode != MODES[mode]:
        return "wrong mode", form, (f"asked {mode}={MODES[mode]}, the page "
                                    f"says {said_mode}")
    save(mid, mode, page)
    # The answer carries fresh tokens; using them keeps the next post valid.
    fresh = tokens(page)
    if fresh.get("__VIEWSTATE"):
        form = fresh
    if said is None or said_mode is None:
        missing = " and ".join(
            x for x, ok in (("the selected member", said is not None),
                            ("the checked mode", said_mode is not None))
            if not ok)
        return "unverified", form, f"the page does not state {missing}"
    return "saved", form, ""


def roster(fetch=False):
    """[(id, label)], from disk, or from one request with --members."""
    if ROSTER.exists() and not fetch:
        return [tuple(x) for x in json.loads(ROSTER.read_text(encoding="utf-8"))]
    if not fetch:
        return []
    print("1 request: the member list")
    page = get(URL)
    if refusal.classify(body=page) == "refused":
        refusal.note("fetch_sponsors_by_member", "block page on the member list")
        sys.exit("REFUSED on the member list. refusal.py now holds one for "
                 "24 hours; python3 netcheck.py says what kind it is.")
    got = members(page)
    if not got:
        sys.exit("the member list came back with no options in it; "
                 f"{FORM} holds what was served, and nothing was written to "
                 f"{ROSTER}.")
    ROSTER.write_text(json.dumps(got, indent=1), encoding="utf-8")
    FORM.write_text(page, encoding="utf-8")
    print(f"  {len(got):,} legislators -> {ROSTER}")
    print(f"  the form as served    -> {FORM}")
    return got


# ------------------------------------------------------------------ scoring

def known_sponsors():
    """{(term, bill): {"prime": {name}, "co": {name}}} from data/sponsors.json.

    The two terms the General Court's own database covers. This script did
    not generate them, which is the whole reason they are worth scoring
    against.
    """
    p = Path("data/sponsors.json")
    if not p.exists():
        return {}
    out = {}
    for term, by_bill in json.loads(p.read_text(encoding="utf-8")).items():
        for bill, rows in by_bill.items():
            d = out.setdefault((term, bill), {"prime": set(), "co": set()})
            for r in rows:
                d["prime" if r.get("prime") else "co"].add(
                    surname(r.get("name", "")))
    return out


HONORIFIC = re.compile(r"^(?:rep|sen|representative|senator|hon)\.?\s+", re.I)
SUFFIX = re.compile(r",?\s*\b(?:jr|sr|ii|iii|iv)\b\.?\s*$", re.I)


def surname(name):
    """"Rep. Vartanian, Elsie(Rock. 20)" and "Vartanian, Elsie" both give
    "vartanian".

    THE TWO SIDES OF THE SCORE WRITE A MEMBER DIFFERENTLY, and this is the
    join between them. byAnyMember's list carries the honorific and the seat
    -- "Rep. Vartanian, Elsie(Rock. 20)" -- while data/sponsors.json carries
    "Vartanian, Elsie". Until this stripped the honorific it returned
    "repvartanian" against "vartanian", so --probe would have matched nobody,
    scored zero on every member, and pointed at the row parser or the radio
    mapping -- none of which would have been wrong.

    Found by running the scoring half against data/sponsors.json before any
    page was fetched, which cost nothing and would otherwise have cost twelve
    requests and a wrong conclusion.
    """
    n = flat(name).strip()
    n = re.sub(r"\([^)]*\)", " ", n)        # "(Rock. 20)" is a seat, not a name
    n = HONORIFIC.sub("", n.strip()).strip()
    n = SUFFIX.sub("", n).strip()
    if "," in n:
        # "Barnes, Jr., John" -- the suffix sits between surname and first
        # name, and the surname is still what comes before the first comma.
        n = n.split(",")[0]
    else:
        parts = n.split()
        n = parts[-1] if parts else ""
    return re.sub(r"[^a-z]", "", SUFFIX.sub("", n).lower())


def term_of(year):
    y = int(year)
    return f"{y - 1}-{y}" if y % 2 == 0 else f"{y}-{y + 1}"


def score(people):
    """Read what is on disk against data/sponsors.json. No network.

    Prints, for every member whose answers are saved, how many of the bills
    the database says they sponsored in 2023-2026 came back in the list --
    and how many bills the list claims that the database does not.
    """
    known = known_sponsors()
    if not known:
        print("data/sponsors.json is empty; nothing to score against.")
        return
    by_name = {}
    for (term, bill), d in known.items():
        for role in ("prime", "co"):
            for who in d[role]:
                by_name.setdefault(who, {"prime": set(), "co": set()})
                by_name[who][role].add((term, bill))
    print()
    print("SCORED AGAINST data/sponsors.json (2023-2026, from the database)")
    print(f"{'member':34}{'mode':7}{'rows':>7}{'expected':>10}"
          f"{'found':>7}{'extra':>7}")
    hit = miss = 0
    for mid, label in people:
        who = surname(label)
        for mode in MODES:
            page = load(mid, mode)
            if page is None:
                continue
            rows = parse_rows(page)
            got = {(term_of(r["year"]), r["bill"]) for r in rows
                   if r["bill"] and r["year"]}
            want = by_name.get(who, {}).get(mode, set())
            want = {x for x in want if x in {k for k in known}}
            found = got & want
            extra = {x for x in got if x[0] in ("2023-2024", "2025-2026")} - want
            hit += len(found)
            miss += len(want) - len(found)
            print(f"{label[:33]:34}{mode:7}{len(rows):>7}{len(want):>10}"
                  f"{len(found):>7}{len(extra):>7}")
            for t, b in sorted(want - found)[:4]:
                print(f"    the database says {b} of {t}; the list does not")
    print()
    if hit + miss:
        print(f"{hit:,} of {hit + miss:,} known sponsorships came back "
              f"({100 * hit / (hit + miss):.0f}%)")
    print("A low number here means the parser, the mode mapping or the member "
          "ids are wrong -- not that the archive is missing. Fix it before "
          "any sweep; the pages are on disk and cost nothing to re-read.")


def report():
    """What is on disk and what it says. No network."""
    people = roster()
    if not people:
        sys.exit(f"No {ROSTER}. Run --members first (one request).")
    by_bill = defaultdict(list)
    seen = Counter()
    for mid, label in people:
        for mode in MODES:
            page = load(mid, mode)
            if page is None:
                continue
            seen[mode] += 1
            for r in parse_rows(page):
                if r["bill"]:
                    by_bill[(r["year"], r["bill"])].append(
                        {"member": mid, "name": label, "role": mode})
    print(f"{sum(seen.values()):,} answers on disk "
          f"({seen['prime']:,} prime, {seen['co']:,} co) "
          f"of {len(people) * 2:,}")
    if not by_bill:
        print("No rows parsed out of them. If answers are on disk and this "
              "says nothing, the parser is wrong -- read one: python3 -c "
              "\"import gzip,sys;print(gzip.open(sys.argv[1]).read()"
              ".decode()[:4000])\" sponsors_pages/prime/<id>.html.gz")
        return 0
    print(f"{len(by_bill):,} distinct (year, bill) pairs carry a sponsor")
    years = Counter(y for y, _ in by_bill)
    print()
    print("bills with a sponsor, by year:")
    for y in sorted(years):
        print(f"  {y}: {years[y]:,}")
    score(people)
    return 0


def plan():
    """What a full sweep would cost, and what is already done. No network."""
    people = roster()
    if not people:
        print(f"No {ROSTER} yet. The first request of all is the member "
              f"list:\n  python3 fetch_sponsors_by_member.py --members")
        print("\nThe survey counted 2,614 legislators, so a full sweep is "
              "about 5,228 requests -- at 15s apart, roughly 22 hours of "
              "asking, which belongs in the lane a run at a time.")
        return 0
    cached = sum(1 for mid, _ in people for mode in MODES
                 if page_path(mid, mode).exists())
    want = len(people) * 2
    print(f"{len(people):,} legislators x {len(MODES)} modes = {want:,} answers")
    print(f"  {cached:,} on disk, {want - cached:,} still to ask")
    print(f"  at 15s apart that is {(want - cached) * 15 / 3600:.1f} hours "
          f"of asking, in runs of 200 with a rest between")
    if not cached:
        print("\nNothing has been fetched yet. --probe 6 first: six answers, "
              "scored against data/sponsors.json, before any sweep.")
    return 0


def main():
    global HOLD
    ap = argparse.ArgumentParser()
    ap.add_argument("--members", action="store_true",
                    help="fetch the legislator list (one request)")
    ap.add_argument("--probe", type=int, default=0,
                    help="fetch this many members, both modes, and score them")
    ap.add_argument("--budget", type=int, default=0,
                    help="stop after this many requests")
    ap.add_argument("--delay", type=float, default=15.0)
    ap.add_argument("--stop-refused", type=int, default=2)
    ap.add_argument("--parse", action="store_true",
                    help="read what is saved and report; no network")
    ap.add_argument("--plan", action="store_true",
                    help="what a sweep would cost; no network")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="sweep even though the answers do not say which "
                         "member they are about")
    a = ap.parse_args()

    if a.plan:
        return plan()
    if a.parse:
        return report()

    refusal.check("The sponsor fetch")
    with refusal.hold("fetch_sponsors_by_member") as held:
        HOLD = held
        people = roster(fetch=a.members)
        if a.members:
            return 0
        if not people:
            sys.exit(f"No {ROSTER}. Run --members first (one request).")
        if not (a.probe or a.budget):
            sys.exit("give --budget N (requests) or --probe N (members), so a "
                     "run always has an end. 2,614 members x 2 modes is "
                     "5,228 requests.")
        if not FORM.exists():
            sys.exit(f"{FORM} is missing; run --members again.")
        form = tokens(FORM.read_text(encoding="utf-8", errors="replace"))
        if not form.get("__VIEWSTATE"):
            sys.exit(f"no __VIEWSTATE in {FORM}; run --members again.")

        # A SWEEP DOES NOT START ON UNCHECKABLE ANSWERS. If the pages already
        # on disk never state which member they are about, this route cannot
        # tell one legislator's career from another's, and thousands of
        # requests would produce a file nobody should believe.
        if a.budget and not a.probe:
            unverified = [(mid, mode) for mid, _ in people for mode in MODES
                          if (load(mid, mode) or "") and
                          selected_member(load(mid, mode)) is None]
            if unverified and not a.allow_unverified:
                sys.exit(
                    f"{len(unverified):,} answers on disk do not say which "
                    "member they are about, so this sweep would be unable to "
                    "tell whose bills it is filing. Read one, fix "
                    "selected_member(), or pass --allow-unverified knowing "
                    "that the check is off.")

        todo = [(mid, mode) for mid, _ in people for mode in MODES]
        if a.probe:
            # Members the database already knows about, so the answers can be
            # scored the moment they land.
            known = {surname(n) for (t, b), d in known_sponsors().items()
                     for role in ("prime", "co") for n in d[role]}
            pick = [p for p in people if surname(p[1]) in known] or people
            todo = [(mid, mode) for mid, _ in pick[:a.probe] for mode in MODES]
        budget = a.budget or len(todo)
        print(f"{len(todo):,} answers wanted, {budget:,} requests this run, "
              f"{a.delay:g}s apart")
        tally, refused, dropped, spent = Counter(), 0, 0, 0
        for mid, mode in todo:
            if spent >= budget:
                break
            what, form, why = fetch_member(mid, mode, form,
                                           a.delay if tally else 0)
            if what == "stale":
                print("  tokens stale; reloading the form")
                spent += 1
                try:
                    form = tokens(get(URL))
                except Exception as e:
                    print(f"  could not reload the form: {e}")
                    break
                what, form, why = fetch_member(mid, mode, form, a.delay)
            tally[what] += 1
            if what not in ("cached", "halted"):
                spent += 1
            if what in ("wrong member", "wrong mode", "unverified"):
                print(f"  {mid} {mode}: {what} -- {why}")
            if what == "halted":
                print(f"\nStopping: {why}.")
                break
            if what == "refused":
                refusal.note("fetch_sponsors_by_member", why)
                print(f"\nREFUSED: {why}. Stopping, and refusal.py now holds "
                      "one for 24 hours.")
                print("python3 netcheck.py says what kind it is without "
                      "making it worse.")
                return 2
            if what == "dropped":
                dropped += 1
                if dropped >= a.stop_refused:
                    refusal.note("fetch_sponsors_by_member", why)
                    print(f"\n{dropped} dropped connections -- this address's "
                          "usual way of refusing. Stopping, and refusal.py "
                          "holds it.")
                    return 2
            # A postback answering about the wrong member is not a bad page,
            # it is a session this run no longer understands. One is a
            # curiosity; three in a row means stop before anything is filed
            # under the wrong name.
            if what in ("wrong member", "wrong mode"):
                refused += 1
                if refused >= 3:
                    print("\nThree answers came back about somebody else. "
                          "Stopping; nothing was saved from them.")
                    return 2
            else:
                refused = 0
            if spent and spent % 50 == 0:
                print(f"  {spent}/{budget}  " +
                      ", ".join(f"{v:,} {k}" for k, v in tally.most_common()),
                      flush=True)
        print()
        print(", ".join(f"{v:,} {k}" for k, v in tally.most_common()))
        print(f"-> {OUT}/   then: python3 fetch_sponsors_by_member.py --parse")
        if a.probe:
            score([p for p in people if page_path(p[0], "prime").exists()
                   or page_path(p[0], "co").exists()])
    return 0


if __name__ == "__main__":
    sys.exit(main())
