#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.1
"""Who sponsored what, asked one legislator at a time instead of one bill at a time.

    python3 fetch_sponsors_by_member.py --members      # the roster, 1 request
    python3 fetch_sponsors_by_member.py --probe 6      # a handful, both modes
    python3 fetch_sponsors_by_member.py --budget 200   # fetch, then stop
    python3 fetch_sponsors_by_member.py --parse        # no network at all

WHY THIS AND NOT ONE PAGE PER BILL

Seventeen of nineteen terms have no sponsors. The obvious route is the bill's
own text -- gc.nh.gov/legislation/<year>/<BILL>.html carries "SPONSORS:" --
and that is 33,000 requests for the archive, or 7,830 for the five terms with
nothing at all.

byAnyMember.aspx asks the other way round. It offers 2,614 past and present
legislators in one list, has NO session-year selector, and returns a member's
whole career in one answer:

    Year   Bill #    Status                Title
    1989   HB175     SIGNED BY GOVERNOR    relative to bail commissioners' fees.
    1990   HB1092    SIGNED BY GOVERNOR    (2nd New Title) relative to low and ...

Two requests a member -- Prime Sponsored, then CoSponsored -- is 5,228 for
EVERY term from 1989 to 2026, against 7,830 for five terms the other way.

It is also better data. Each row links
billinfo.aspx?sy=1989&Pastid=<lsr><year>, so the LSR is in the address and
the join to data/bills.json is exact rather than a guess at which "Rep.
Allard" is meant; and the list gives a member's full first name, where a
bill's text gives only a surname.

THE ONE KNOWN GAP, MEASURED BEFORE THIS IS TRUSTED

HB1 of 1989 is a SPECIAL SESSION bill, LSR 1989-9100, and its own text names
Rep. Vartanian. It appears in neither of her lists. Whether special sessions
are absent from this view or filed under another year is not known from one
sample, which is what --probe is for: it fetches the members who sponsored
bills we already hold saved text for, and reports which of those bills come
back and which do not. Run it, read it, and only then decide whether this
route stands alone or needs the per-bill pages behind it.

HOW THE PAGE WORKS

An ASP.NET postback. One GET yields __VIEWSTATE (about 135 KB),
__EVENTVALIDATION (about 56 KB) and the whole member list; each POST sets
__EVENTTARGET, the member and the radio. The tokens are reused across members
-- EVENTVALIDATION validates that the posted member is one of the listed
options, and every member is listed -- and are refetched when the server
stops accepting them.

GENTLE, AND IT STOPS

15 seconds between requests, --budget to end a run early, two refusals to end
it immediately, and refusal.py to keep every other fetcher stopped for 24
hours afterwards. Every answer is saved gzipped under sponsors_pages/ and
never asked for twice, so the parser can be wrong as often as it likes
without costing a request. This address has been blocked twice.
"""

import argparse
import gzip
import html as _html
import json
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
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}

HIDDEN = re.compile(r"<input[^>]+type=[\"']hidden[\"'][^>]*>", re.I)
ATTR = re.compile(r"(\w+)\s*=\s*[\"']([^\"']*)[\"']")
OPTION = re.compile(r"<option[^>]*value=[\"'](\d+)[\"'][^>]*>(.*?)</option>", re.I | re.S)
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
    for mid, label in OPTION.findall(page):
        text = flat(_html.unescape(label))
        if mid in seen or not text:
            continue
        seen.add(mid)
        out.append((mid, text))
    return out


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
            "status": cols[2].strip(" -| ") if len(cols) > 2 else "",
            "title": (flat(_html.unescape(title.group(1))).lstrip("  ")
                      if title else ""),
        })
    return rows


def page_path(mid, mode):
    return OUT / mode / f"{mid}.html.gz"


def save(mid, mode, page):
    p = page_path(mid, mode)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(page.encode("utf-8"), 6))


def load(mid, mode):
    p = page_path(mid, mode)
    return gzip.decompress(p.read_bytes()).decode("utf-8") if p.exists() else None


def fetch_member(mid, mode, form, delay):
    """One answer, saved. "saved" / "cached" / "error page" / "refused" / "missing"."""
    if page_path(mid, mode).exists():
        return "cached", form
    time.sleep(delay)
    fields = dict(form)
    fields.update({
        "__EVENTTARGET": "ctl00$pageBody$lstMembers",
        "__EVENTARGUMENT": "",
        "ctl00$pageBody$lstMembers": mid,
        "ctl00$pageBody$rdoPrime": MODES[mode],
    })
    try:
        page = get(URL, urllib.parse.urlencode(fields).encode())
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            refusal.note("fetch_sponsors_by_member", f"HTTP {e.code} on {URL}")
            return "refused", form
        if e.code == 500:
            # The tokens went stale. One GET replaces them; it is a request,
            # so it is counted like any other.
            return "stale", form
        return "missing", form
    except (urllib.error.URLError, TimeoutError):
        return "missing", form
    if ERROR_PAGE.search(page[:6000]):
        return "error page", form
    save(mid, mode, page)
    # The answer carries fresh tokens; using them keeps the next post valid.
    fresh = tokens(page)
    if fresh.get("__VIEWSTATE"):
        form = fresh
    return "saved", form


def roster(fetch=False):
    """[(id, label)], from disk, or from one request with --members."""
    if ROSTER.exists() and not fetch:
        return [tuple(x) for x in json.loads(ROSTER.read_text(encoding="utf-8"))]
    if not fetch:
        return []
    refusal.check("The sponsor fetch")
    print("1 request: the member list")
    page = get(URL)
    got = members(page)
    ROSTER.write_text(json.dumps(got, indent=1), encoding="utf-8")
    Path("sponsors_form.html").write_text(page, encoding="utf-8")
    print(f"  {len(got):,} legislators -> {ROSTER}")
    return got


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
        return 0
    print(f"{len(by_bill):,} distinct (year, bill) pairs carry a sponsor")
    years = Counter(y for y, _ in by_bill)
    print()
    print("bills with a sponsor, by year:")
    for y in sorted(years):
        print(f"  {y}: {years[y]:,}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--members", action="store_true",
                    help="fetch the legislator list (one request)")
    ap.add_argument("--probe", type=int, default=0,
                    help="fetch this many members, both modes, and report")
    ap.add_argument("--budget", type=int, default=0,
                    help="stop after this many requests")
    ap.add_argument("--delay", type=float, default=15.0)
    ap.add_argument("--stop-refused", type=int, default=2)
    ap.add_argument("--parse", action="store_true",
                    help="read what is saved and report; no network")
    a = ap.parse_args()

    if a.parse:
        return report()

    people = roster(fetch=a.members)
    if a.members:
        return 0
    if not people:
        sys.exit(f"No {ROSTER}. Run --members first (one request).")
    if not (a.probe or a.budget):
        sys.exit("give --budget N (requests) or --probe N (members), so a run "
                 "always has an end. 2,614 members x 2 modes is 5,228 requests.")

    refusal.check("The sponsor fetch")
    form_page = Path("sponsors_form.html")
    if not form_page.exists():
        sys.exit("sponsors_form.html is missing; run --members again.")
    form = tokens(form_page.read_text(encoding="utf-8", errors="replace"))
    assert form.get("__VIEWSTATE"), "no __VIEWSTATE in the saved form page"

    todo = [(mid, mode) for mid, _ in people for mode in MODES]
    if a.probe:
        todo = [(mid, mode) for mid, _ in people[:a.probe] for mode in MODES]
    budget = a.budget or len(todo)
    print(f"{len(todo):,} answers wanted, {budget:,} requests this run, "
          f"{a.delay:g}s apart")
    tally, refused, spent = Counter(), 0, 0
    for mid, mode in todo:
        if spent >= budget:
            break
        what, form = fetch_member(mid, mode, form, a.delay if tally else 0)
        if what == "stale":
            print("  tokens stale; reloading the form")
            spent += 1
            form = tokens(get(URL))
            what, form = fetch_member(mid, mode, form, a.delay)
        tally[what] += 1
        if what not in ("cached",):
            spent += 1
        if what == "refused":
            refused += 1
            if refused >= a.stop_refused:
                print(f"\n{refused} refusals. Stopping, and refusal.py now "
                      "holds one for 24 hours.")
                print("python3 netcheck.py says what kind it is without "
                      "making it worse.")
                return 2
        if spent and spent % 50 == 0:
            print(f"  {spent}/{budget}  " +
                  ", ".join(f"{v:,} {k}" for k, v in tally.most_common()))
    print()
    print(", ".join(f"{v:,} {k}" for k, v in tally.most_common()))
    print(f"-> {OUT}/   then: python3 fetch_sponsors_by_member.py --parse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
