#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.5
"""
Fetch the bill STATUS page for bills the current-session files no longer cover.

    python3 fetch_bill_status.py --data data --limit 5 --debug 2
    python3 fetch_bill_status.py --data data
    python3 fetch_bill_status.py --data data --reparse   # cached pages only

Replaces fetch_bill_titles.py, which read the wrong page. bill_docket.aspx
lists ACTIONS, so extracting sponsors from it meant sifting member names out of
conference committee substitutions and floor motions -- "Rep. Mooney Replaces
Rep. Edwards" is not a sponsor, and neither is "Sen. Birdsell Objected".

Bill_status.aspx has the fields as fields:

    Bill Title: creating a committee to study the laws relative to oyster
                harvesting.
    Sponsors:   Aidan Ankarberg (I)      -> member.aspx?member=409047
                Jennifer Mandelbaum (D)  -> member.aspx?member=409203
                David Watters (D)        -> senate/.../district04.aspx
    Current Committee: Fish and Game and Marine Resources (H42)
    Bill Text: billText.aspx?id=43

Nothing has to be inferred from surrounding prose. The sponsor links also carry
the same member ids the roll call pages use, so a sponsor from an earlier
session can be tied to a person rather than left as a name.
"""

import argparse
import json
import proceedings as P
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}

WS = re.compile(r"\s+")
MEMBER_ID = re.compile(r"member\.aspx\?member=(\d+)", re.I)
SEN_DIST = re.compile(r"webpages/district(\d+)\.aspx", re.I)
CMTE_CODE = re.compile(r"committeedetails\.aspx\?code=([A-Z]\d+)", re.I)
# billText.aspx takes THREE parameters, and the session year is not optional:
# without sy the page fails server-side with "condensedbillno is neither a
# DataColumn nor a DataRelation for table text", which a reader sees as a blank
# page and an error message. The link on the status page has it; only our copy
# of the link did not.
TEXT_ID = re.compile(r"billText\.aspx\?(?P<q>[^\"'\s>]+)", re.I)
TEXT_PARAM = re.compile(r"(?:^|&|&amp;)(id|sy|txtFormat)=([^&\s\"']+)", re.I)
NAME_PARTY = re.compile(r"^(?P<name>.+?)\s*\((?P<party>[A-Z])\)\s*$")

# Field labels on the page. When a field is blank the pattern runs on into the
# next one, so these must never be accepted as values.
NOT_A_VALUE = {"status date", "current committee", "committee of referral",
               "date introduced", "due out of committee", "floor date",
               "house status", "senate status", "gen status", "status",
               "next/last hearing", "sponsors", "general status", "none"}


class StatusPage(HTMLParser):
    """Read the status page as labelled fields rather than as prose.

    Also captures the sponsors table on its own, because a member who has left
    office loses their member page and so appears there as plain text rather
    than a link: "Thomas Oppel (D)" with no anchor. Reading only the links drops
    exactly the sponsors hardest to recover any other way.
    """

    def __init__(self):
        super().__init__()
        self.text, self.links = [], []
        self._href, self._buf = None, []
        self.sponsor_cells, self._in_sp, self._cell = [], False, []
        self._seen_label = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href", "")
            self._buf = []
        # The first table after the "Sponsors" heading is the sponsor list.
        if self._seen_label and not self._in_sp and tag == "table":
            self._in_sp, self._depth = True, 0
        elif self._in_sp and tag == "table":
            self._depth += 1
        if self._in_sp and tag in ("td", "th"):
            self._cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self._href is not None:
            self._buf.append(data)
        if self._in_sp:
            self._cell.append(data)
        if not self._seen_label and re.search(r"\bSponsors?\b", data, re.I):
            self._seen_label = True

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, WS.sub(" ", "".join(self._buf)).strip()))
            self._href, self._buf = None, []
        if self._in_sp:
            if tag in ("td", "th"):
                v = WS.sub(" ", "".join(self._cell)).strip()
                if v:
                    self.sponsor_cells.append(v)
                self._cell = []
            elif tag == "table":
                if self._depth:
                    self._depth -= 1
                else:
                    self._in_sp = False

    def flat(self):
        return WS.sub(" ", " ".join(self.text)).strip()


def parse(html):
    p = StatusPage()
    p.feed(html)
    flat = p.flat()
    rec = {}

    m = re.search(r"Bill Title:\s*(?P<t>.+?)(?=\s*(?:General\s+Status|LSR#|$))",
                  flat, re.I)
    if m:
        rec["title"] = WS.sub(" ", m.group("t")).strip(" .;:") + "."

    for key, pat in (
            ("lsr", r"LSR#:\s*(\d+)"),
            ("body", r"Body:\s*([HS])\b"),
            ("local", r"Local Govt:\s*([YN])\b"),
            ("chapter", r"Chapter#:\s*(\d+)"),
            # The three status fields, stated rather than inferred. These are
            # the most-read facts on the site and were previously guessed by
            # string-matching docket prose.
            ("gen_status",
             r"Gen Status:\s*(?P<v>[A-Z][A-Za-z ,/\-]*?)\s*(?=House Status|$)"),
            ("house_status",
             r"House Status\s*Status\s*(?P<v>[A-Z][A-Za-z ,/\-]*?)"
             r"\s*(?=Status Date|Current Committee|Senate Status|$)"),
            ("senate_status",
             r"Senate Status\s*Status\s*(?P<v>[A-Z][A-Za-z ,/\-]*?)"
             r"\s*(?=Status Date|Current Committee|Next/Last|$)"),
            ("date_introduced", r"Date Introduced\s*(\d{1,2}/\d{1,2}/\d{4})"),
            ("floor_date", r"Floor Date\s*(\d{1,2}/\d{1,2}/\d{4})")):
        mm = re.search(pat, flat, re.I)
        if mm:
            v = (mm.groupdict().get("v") or mm.group(1) or "").strip(" .;:")
            # An empty field lets the pattern run on into the next label, so a
            # bill with no Senate action came back with a status of
            # "Status Date". Anything that IS a label is not a value.
            if v.lower() in NOT_A_VALUE:
                continue
            if v and v.lower() not in ("none",):
                rec[key] = v

    # Sponsors, in the order the page lists them. The first is the prime
    # sponsor by convention; the page does not mark it.
    #
    # Two passes. Links first, since they carry the member id. Then the sponsor
    # table's plain cells, which is where a member who has left office ends up:
    # they lose their member page, so the name is printed without an anchor.
    # Dropping those would lose precisely the sponsors that are hardest to
    # recover from anywhere else.
    sponsors, seen = [], set()
    for href, label in p.links:
        mid = MEMBER_ID.search(href)
        sd = SEN_DIST.search(href)
        if not (mid or sd):
            continue
        nm = NAME_PARTY.match(label)
        name = (nm.group("name") if nm else label).strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        sponsors.append({
            "name": name,
            "party": nm.group("party") if nm else "",
            "web_member_id": mid.group(1) if mid else "",
            "senate_district": sd.group(1) if sd else "",
            "chamber": "S" if sd else "H",
            "url": urllib.parse.urljoin("https://gc.nh.gov/", href),
        })
    for cell in p.sponsor_cells:
        nm = NAME_PARTY.match(cell)
        if not nm:
            continue
        name = nm.group("name").strip()
        if not name or name.lower() in seen or len(name) < 4:
            continue
        seen.add(name.lower())
        sponsors.append({
            "name": name, "party": nm.group("party"),
            "web_member_id": "", "senate_district": "",
            "chamber": "", "url": "", "no_member_page": True})

    if sponsors:
        rec["sponsors"] = sponsors

    cm = CMTE_CODE.search(html)
    if cm:
        rec["committee_code"] = cm.group(1)
    tm = TEXT_ID.search(html)
    if tm:
        q = {k.lower(): v for k, v in TEXT_PARAM.findall(tm.group("q"))}
        if q.get("id"):
            rec["text_id"] = q["id"]
            # The year is taken from the link rather than guessed, because a
            # bill carried over from one session to the next keeps the year it
            # was filed under and that is not something to infer.
            if q.get("sy"):
                rec["text_year"] = q["sy"]
            sy = f"&sy={q['sy']}" if q.get("sy") else ""
            rec["text_pdf"] = ("https://gc.nh.gov/bill_status/legacy/bs2016/"
                               f"billText.aspx?id={q['id']}&txtFormat=pdf{sy}")
    return rec


def get(url, timeout, tries=3):
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace"), None
        except Exception as e:
            last = e
            if n < tries - 1:
                time.sleep(2 * (n + 1))
    return None, last


# What a link's ADDRESS looks like, with the values stripped out. Two links to
# two different amendments are one pattern; two links to two different kinds of
# document are two. Grouping on the shape is what turns 2,234 pages into a
# handful of answers.
def link_shape(href):
    u = urllib.parse.urlsplit(href)
    path = re.sub(r"\d+", "#", u.path.rsplit("/", 1)[-1] or u.path)
    keys = sorted(k for k, _ in urllib.parse.parse_qsl(u.query))
    host = u.netloc or "(same site)"
    return f"{host}/{path}" + (f"?{'&'.join(keys)}" if keys else "")


def link_inventory(cache):
    """Every document link on every cached status page, grouped by address shape.

    The fiscal note and the amendment text are the two things this project
    still cannot link to, and the handoff records both as "address unknown".
    They are not unknown -- they are on these pages, which are already on disk,
    2,234 of them. This reads them and says what shapes exist and how common
    each one is, which is the difference between a probe of one bill and an
    answer.

    No network. Nothing is written.
    """
    files = sorted(cache.glob("*.html"))
    if not files:
        print(f"No cached pages under {cache}/. Run a fetch first.")
        return
    print(f"reading {len(files):,} cached status pages\n")
    shapes, labels, example = Counter(), {}, {}
    for f in files:
        pp = StatusPage()
        try:
            pp.feed(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for href, label in pp.links:
            if not href or href.lower().startswith(("javascript:", "#", "mailto:")):
                continue
            s = link_shape(href)
            shapes[s] += 1
            labels.setdefault(s, Counter())[WS.sub(" ", label).strip()[:40]] += 1
            example.setdefault(s, href)

    print(f"{'pages':>7}  {'address shape':<52} example label")
    print("-" * 100)
    for s, c in shapes.most_common(40):
        top = labels[s].most_common(1)[0][0] if labels[s] else ""
        print(f"{c:>7,}  {s[:52]:<52} {top}")
    print("\nexamples, one per shape:")
    for s, _ in shapes.most_common(40):
        print(f"  {s[:46]:<48} {example[s][:96]}")
    print("\nWhat to look for: a shape whose label mentions an amendment number,")
    print("a fiscal note, or a version of the bill text. Those are the three")
    print("addresses the project does not have, and they are either in this list")
    print("or they are not on this page at all -- which is itself the answer.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="bill_status.json")
    ap.add_argument("--cache", default="status_pages")
    ap.add_argument("--year")
    ap.add_argument("--term", help="which term of data/bills.json to fetch, "
                                   "e.g. 2023-2024; the newest by default")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--debug", type=int, default=0)
    ap.add_argument("--reparse", action="store_true",
                    help="re-run the parser over cached pages, no network")
    ap.add_argument("--bill", help="one bill only, e.g. CACR17, with full detail")
    ap.add_argument("--links", action="store_true",
                    help="inventory every document link across the cached pages, "
                         "no network")
    ap.add_argument("--all", action="store_true",
                    help="kept for compatibility; every bill is the default now")
    ap.add_argument("--missing", action="store_true",
                    help="only bills lacking a title or sponsors, the old default")
    a = ap.parse_args()

    # bills.json is {term: {bill: record}}. The newest term by default, which
    # is what a run during a session wants; --term names an archived one. The
    # archived records carry lsr_num and lsr_year like any other, which is
    # everything the status-page URL needs.
    all_bills = json.loads(
        (Path(a.data) / "bills.json").read_text(encoding="utf-8"))
    newest = max(all_bills) if all_bills else ""
    term = a.term or newest
    if term not in all_bills:
        raise SystemExit(f"data/bills.json has no term {term!r}. It holds: "
                         + ", ".join(sorted(all_bills)))
    bills = all_bills[term]
    print(f"term {term}: {len(bills):,} bills on file")
    sponsors_now = json.loads(
        (Path(a.data) / "sponsors.json").read_text(encoding="utf-8"))

    if a.links:
        link_inventory(Path(a.cache))
        return

    if a.bill:
        b = a.bill.upper().replace(" ", "")
        if b not in bills:
            print(f"{b} is not in data/bills.json")
            return
        rec = bills[b]
        q = urllib.parse.urlencode({
            "lsr": rec["lsr_num"], "sy": rec["lsr_year"],
            "sortoption": "billnumber", "txtsessionyear": rec["lsr_year"],
            "txtbillnumber": b.lower()})
        url = f"{BASE}?{q}"
        print(url + "\n")
        # 2,234 of these are already cached, and the page for a past action
        # does not change. Refetching to look at one is a request nobody needs
        # to make.
        cpath = Path(a.cache) / f"{rec['lsr_year']}_{rec['lsr_num']}_{b}.html"
        if cpath.exists():
            html = cpath.read_text(encoding="utf-8", errors="replace")
            print(f"(reading {cpath}, not the network)\n")
        else:
            html, err = get(url, a.timeout)
            if html is None:
                print(f"failed: {err}")
                return
        got = parse(html)
        print(json.dumps(got, indent=2)[:1200])
        pp = StatusPage()
        pp.feed(html)
        print("\n--- every link on the page ---")
        for href, label in pp.links:
            print(f"  {label[:44]:<46} {href[:88]}")
        return

    # Every bill, once. The old rule fetched only bills missing a title or
    # sponsors, which made sense when this page merely filled gaps. It is now
    # the authority for bill STATUS, which every bill has, so skipping any bill
    # leaves it on the derived-from-prose fallback.
    #
    # It also made the queue depend on the state of sponsors.json at the moment
    # of the run: HB2 was skipped because it still held a bad scraped sponsor,
    # and once that was cleaned out the fetch had already finished. A filter
    # that depends on data another step is still fixing will always have holes.
    #
    # Pages are cached permanently, so "fetch everything" costs nothing after
    # the first pass. --missing restores the narrow behaviour if wanted.
    todo = [b for b, r in bills.items()
            if r.get("lsr_num")
            and (not a.missing or not r.get("title") or not sponsors_now.get(b))
            and (not a.year or r.get("lsr_year") == a.year)]
    todo.sort()
    if not todo:
        print("Nothing to fetch.")
        return

    years = Counter(bills[b]["lsr_year"] for b in todo)
    print(f"{len(todo):,} bills in scope, by LSR year: {dict(years)}")
    if a.limit:
        todo = todo[:a.limit]
        print(f"limited to {len(todo)}")

    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    # bill_status.json is {term: {bill: record}}. A bill number is unique
    # within a term and not across them, so a flat file could only ever hold
    # one; it is read as the newest term's, which is what it was.
    #
    # `out_all` is what gets written and `out` is this term's slice of it, so
    # a run over 2023-2024 cannot drop 2025-2026 on its way out. A writer run
    # on a subset that replaces the whole file is how the manifest lost its
    # hand-marked times, twice.
    out_all, out = {}, {}
    if Path(a.out).exists():
        out_all = P.in_term(
            json.loads(Path(a.out).read_text(encoding="utf-8")), newest)
        # --reparse rebuilds THIS term from the cached pages, so this term's
        # records are dropped and re-derived. Every other term is kept: they
        # were fetched from pages this run has no cache of and cannot rebuild,
        # and a writer run on a subset that replaces the whole file is how the
        # manifest lost its hand-marked times, twice.
        out = {} if a.reparse else out_all.get(term, {})
        have = sum(1 for b in todo if b in out)
        others = sum(len(v) for k, v in out_all.items() if k != term)
        if a.reparse:
            print(f"--reparse: rebuilding {term} from the cache"
                  + (f"; {others:,} bills of other terms kept" if others else ""))
        else:
            print(f"{len(out):,} already on file for {term}; "
                  f"{len(todo) - have:,} still to fetch"
                  + (f"; {others:,} bills of other terms kept" if others else ""))
    # An empty term is noise in the file and reads as "fetched, found none"
    # rather than "not fetched yet". Only a term with records is written.
    if out:
        out_all[term] = out
    else:
        out_all.pop(term, None)

    fetched = cached = 0
    fails = Counter()
    for i, bill in enumerate(todo, 1):
        if bill in out and not a.reparse:
            continue
        rec = bills[bill]
        yr, lsr = rec["lsr_year"], rec["lsr_num"]
        q = urllib.parse.urlencode({
            "lsr": lsr, "sy": yr, "sortoption": "billnumber",
            "txtsessionyear": yr, "txtbillnumber": bill.lower()})
        cpath = cache / f"{yr}_{lsr}_{bill}.html"
        if cpath.exists():
            html = cpath.read_text(encoding="utf-8", errors="replace")
            cached += 1
        elif a.reparse:
            continue
        else:
            time.sleep(a.delay)
            html, err = get(f"{BASE}?{q}", a.timeout)
            if html is None:
                fails[type(err).__name__] += 1
                continue
            cpath.write_text(html, encoding="utf-8")
            fetched += 1

        got = parse(html)
        if got:
            out[bill] = got
        if a.debug:
            print(f"\n  {bill}")
            print(f"    title    : {got.get('title', '(none)')[:96]}")
            print(f"    sponsors : " + (", ".join(
                f"{s['name']} ({s['party']})" for s in got.get("sponsors", [])[:6])
                or "(none)"))
            print(f"    committee: {got.get('committee_code', '-')}  "
                  f"chapter: {got.get('chapter', '-')}  "
                  f"local: {got.get('local', '-')}  text id: {got.get('text_id', '-')}")
            a.debug -= 1

        if i % 25 == 0:
            print(f"  {i}/{len(todo)}  {fetched} fetched, {cached} cached",
                  flush=True)
            Path(a.out).write_text(json.dumps(out_all, indent=2),
                                   encoding="utf-8")

    Path(a.out).write_text(json.dumps(out_all, indent=2), encoding="utf-8")

    withtitle = sum(1 for v in out.values() if v.get("title"))
    withsp = sum(1 for v in out.values() if v.get("sponsors"))
    withtext = sum(1 for v in out.values() if v.get("text_id"))
    print(f"\n{len(out):,} bills of {term} -> {a.out} "
          f"({sum(len(v) for v in out_all.values()):,} across "
          f"{len(out_all)} term(s))")
    print(f"  {withtitle:,} with a title, {withsp:,} with sponsors, "
          f"{withtext:,} with a bill-text link")
    print(f"  {fetched:,} pages fetched, {cached:,} from cache")
    if fails:
        print(f"  failures: {dict(fails)}")
    if out and withsp < len(out) * 0.8:
        print("\nFewer than 80% have sponsors. Run --debug 3 and send the output;")
        print("the sponsor links may be laid out differently for that era.")

    ex = next((b for b, v in out.items() if v.get("sponsors")), None)
    if ex:
        v = out[ex]
        print(f"\nSample - {ex}: {v.get('title', '')[:70]}")
        for s in v["sponsors"][:6]:
            print(f"  {'PRIME' if s is v['sponsors'][0] else '     '} "
                  f"{s['name']} ({s['party']}) {s['chamber']}"
                  f"{'  id ' + s['web_member_id'] if s['web_member_id'] else ''}")
        print("  Prime is the first listed; the page does not mark the field.")


if __name__ == "__main__":
    main()
