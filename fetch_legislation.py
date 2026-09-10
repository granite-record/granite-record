#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.9
"""
The bill itself, from an address that can simply be constructed.

    python3 fetch_legislation.py --sample 10 --from 1989 --to 2026
    python3 fetch_legislation.py --parse            # no network; read what is saved

WHY THIS PATH AND NOT THE OTHER ONE

Every archive fetcher here goes through bill_status/legacy/bs2016, which wants
a search, a session and a POST per bill. A person found this instead:

    https://gc.nh.gov/legislation/1989/HB0015.html

It is directly constructible from a year and a zero-padded bill number, and it
carried, in four kilobytes, the two fields five terms of this archive do not
have at all:

    INTRODUCED BY: Rep. Millard of Merrimack Dist. 4
    REFERRED TO:   Commerce, Small Business and Consumer Affairs
    AN ACT repealing certain laws relative to measuring wood.
    ANALYSIS  This bill repeals laws relating to cord dimensions...

Probed across eight years from 1989 to 2017, plus 2021: every one returned a
page.

WHAT 380 BILLS, TEN A YEAR FROM 1989 TO 2026, FOUND (10 September)

297 pages. The 83 that were not there are not scattered: every bill asked for
under 1996, 2016, and 2022 through 2026 answered 404, and nothing else did
except thirteen single bills. 2022 onward is expected -- the current terms
are served by bill_status, and the site already has them from the database.
1996 and 2016 are not explained. bills.json puts 893 bills in 1996 and 1,072
in 2016, the archive path for 1990, 1992 and every other even year works,
and whether those two years sit under another name or are missing from the
archive is a question for a browser, not for this script.

Of the 297, 29 name no sponsor and every one is the document: 22 are the
housekeeping resolutions of an organisation day ("House Resolutions 1-5 were
housekeeping resolutions adopted during the House Organization Session"),
7 are HB 1's budget-category tables or a link to a PDF. Sponsors,
committees and titles are otherwise read across all 15 kinds and 31 years,
which took three passes of reading the pages the parser missed; the comments
by each pattern say what each pass found. The archive is served in Latin-1
on half its pages and UTF-8 on a sixth, and 73 pages saved before decode()
existed carry a replacement character where a non-breaking space was;
re-fetching them is the only repair, and it is not worth 73 requests.

FETCH ONCE, PARSE MANY TIMES

Pages are saved under legislation/<year>/<BILL>.html and never re-fetched. The
labels move with the decades -- INTRODUCED BY and REFERRED TO in 1989-1993,
SPONSORS: by 2017 -- so the parser will be wrong several times before it is
right, and it must be possible to be wrong without asking the General Court
again. --parse reads the saved pages and touches no network at all.

GENTLE, AND IT STOPS

15 seconds between requests, two refusals end the run, and refusal.py records
one so that it outlives this process and stops every other fetcher for 24
hours. This address has been blocked twice. Nothing else may be fetching from
the General Court while this runs.
"""

import argparse
import json
import re
from html import unescape as _unescape
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import refusal

OUT = Path("legislation")
URL = "https://gc.nh.gov/legislation/{year}/{bill}.html"
# The same document, served by the application instead of as a file. Proven
# the same document rather than assumed: the 2,234 pages in bill_text/ came
# from here, and today's parser reads sponsors, committee, title and analysis
# out of them exactly as it does out of a legislation/<year>/ page.
TEXT = ("https://gc.nh.gov/bill_status/legacy/bs2016/billText.aspx"
        "?id={id}&txtFormat=html&sy={year}")

# WHICH ADDRESS SERVES WHICH YEAR, and how each line was established.
#
# The static path answered for every year sampled from 1989 to 2021 except
# two. 2016 and 1996 returned 404 for all ten bills asked, and a person
# confirmed both in a browser on 10 September:
#
#     legislation/2016/HB1101.html                     404
#     legislation/1996/hb297.htm                       404  (the archive's OWN
#                                                            published link)
#     bs2016/billText.aspx?id=20142016&sy=2016         serves the bill
#
# So 2016 has no static directory and is served by the application, and 1996
# has neither -- the address its own status page publishes is dead, and no
# other address for a 1996 bill's text is known. Both years sit exactly on a
# change of the tool that generated these pages.
#
# THE ID IS NOT ONE SCHEME. data/bills.json carries an id per bill, scraped
# from the search results, and what the address wants is not always it:
#
#     2016   stored 882016 (the LSR and the year)   used as stored   browser
#     2023   stored 1                               wants 12023      the saved
#     2024   stored 4                               wants 42024      status
#     2025   stored 7                               used as stored   pages in
#     2026   stored 6                               used as stored   status_pages/
#
# 2017-2021 are not in the table because the static path serves them and the
# question does not arise. 2022 is not in it because nothing on this disk
# answers it: there is no saved 2022 status page, and guessing between two
# forms is exactly the filename probing that got this address blocked. One
# person opening one address settles it.
# 2022 onward as well: fifty bills were asked for across those five years in
# the sample and every one answered 404. The static archive stops at 2021,
# which is consistent with the current terms being served by the application
# -- bill_text/ holds 2,234 of them, fetched from billText.aspx.
STATIC_404 = {1996, 2016, 2022, 2023, 2024, 2025, 2026}
ID_AS_STORED = {2016, 2025, 2026}
ID_PLUS_YEAR = {2023, 2024}
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}

# Padded to four digits, which is what the address wants: HB15 is HB0015.
PAD = re.compile(r"^([A-Z]+)(\d+)$")

# The order a sample should reach for. One of each kind that exists in a year
# beats ten House bills, because the point of sampling is to meet the formats
# rather than to count them.
KIND_ORDER = ["HB", "SB", "CACR", "HR", "SR", "HCR", "SCR", "HJR", "SJR"]


def padded(bid):
    m = PAD.match(bid.strip().upper())
    return f"{m.group(1)}{int(m.group(2)):04d}" if m else None


def text_id(rec, year):
    """The id billText.aspx wants for this bill, or None if it is not known.

    The stored id is whatever the search results page linked; the table above
    says, per year, whether that is the id the text address takes or whether
    the year is appended to it. A year in neither set returns None rather
    than a guess, because a guessed id is a request for a document that does
    not exist, and a few thousand of those is what a firewall calls a scan.
    """
    m = re.search(r"[?&]id=(\d+)", str(rec.get("text_pdf") or ""))
    if not m:
        return None
    if year in ID_AS_STORED:
        return m.group(1)
    if year in ID_PLUS_YEAR:
        return f"{m.group(1)}{year}"
    return None


def address(year, bid, rec):
    """Where this bill's text is, or None if nowhere known.

    Returns (url, why). A bill with no address is not a failure to fetch: it
    is a document this project cannot presently reach, and the report says so
    rather than the run discovering it one 404 at a time.
    """
    pad = padded(bid)
    if not pad:
        return None, "not a bill number"
    if year not in STATIC_404:
        return URL.format(year=year, bill=pad), "static"
    tid = text_id(rec or {}, year)
    if tid:
        return TEXT.format(id=tid, year=year), "billText"
    return None, ("1996 has no known address: its own status page links "
                  "legislation/1996/hb297.htm and that is a 404"
                  if year == 1996 else
                  f"no id known for {year}; see the table in this file")


def sample(bills, per_year, lo, hi):
    """A stratified draw: every kind a year has, before any kind twice."""
    by_year = defaultdict(lambda: defaultdict(list))
    for _term, bs in bills.items():
        for bid, rec in bs.items():
            y = str(rec.get("year") or rec.get("lsr_year") or "")[:4]
            m = PAD.match(bid.strip().upper())
            if y.isdigit() and lo <= int(y) <= hi and m:
                by_year[int(y)][m.group(1)].append(bid)
    picked = {}
    for year in sorted(by_year):
        kinds = by_year[year]
        for k in kinds:
            kinds[k].sort(key=lambda b: int(PAD.match(b).group(2)))
        order = [k for k in KIND_ORDER if k in kinds]
        order += sorted(k for k in kinds if k not in KIND_ORDER)
        out, i = [], 0
        # Round-robin: one of each kind, then a second of each, and so on.
        while len(out) < per_year and any(len(kinds[k]) > i for k in order):
            for k in order:
                if len(out) >= per_year:
                    break
                if len(kinds[k]) > i:
                    out.append(kinds[k][i])
            i += 1
        picked[year] = out
    return picked


def fetch(year, bid, delay, rec=None):
    """One page, saved.

    Returns "saved", "cached", "missing", "refused" or "unreachable" -- the
    last meaning no address is known for that year, which is a fact about the
    archive and not a failure of the run. Both addresses save to the same
    place, so --parse never learns which one a page came from and does not
    need to: they serve the same document.
    """
    pad = padded(bid)
    if not pad:
        return "skipped"
    f = OUT / str(year) / f"{pad}.html"
    if f.exists() and f.stat().st_size > 200:
        return "cached"
    url, _why = address(year, bid, rec)
    if not url:
        return "unreachable"
    f.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(delay)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            refusal.note("fetch_legislation", f"HTTP {e.code} on {url}")
            return "refused"
        return "missing"
    except (urllib.error.URLError, TimeoutError):
        return "missing"
    # The bytes as served. Decoding is decode()'s job at parse time, so a
    # wrong guess about the encoding is corrected by re-parsing, not by
    # asking the General Court for the page again.
    f.write_bytes(body)
    return "saved"


# ------------------------------------------------------------------ parsing

def decode(raw):
    """Text of a saved page.

    Bytes that are valid UTF-8 are UTF-8: every pure-ASCII page, the 48 that
    declare it, and every page this script saved before 10 September, which
    it decoded on the way in and wrote back out as UTF-8 whatever the page
    said. Anything else is Windows-1252, the superset of the Latin-1 that
    152 of the 297 sample pages declare. The declaration itself is not
    consulted: a page declaring iso-8859-1 that was saved as UTF-8 text
    would have its replacement characters read as three Latin-1 letters
    each, which is how "Sen. Clegg" came out as "ï¿½ï¿½ Sen. Clegg".
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def flatten(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    # Every entity, not five of them. "SCR 1 &#8211; FINAL VERSION" and the
    # box-drawing rule "&#9472;&#9472;..." the modern page draws under the
    # committee were arriving as text, and the rule was landing inside the
    # committee's name. 268 of 297 pages carry an entity of some kind.
    t = _unescape(t)
    # Pages saved before 10 September were decoded as UTF-8 on the way in,
    # and the archive's 0xA0 -- a non-breaking space, in the Latin-1 most of
    # it is served as -- became U+FFFD. It was a space; it is one again.
    t = t.replace("\ufffd", " ")
    return re.sub(r"\s+", " ", t).strip()


# READ OFF THE PAGES, NOT IMAGINED. The first version of this anchored
# everything on "AN ACT", which is what a bill says and what nothing else
# does, so every resolution in the sample yielded a sponsor and no committee
# and no title. Three shapes, from the sample:
#
#   a bill        INTRODUCED BY: ... REFERRED TO: ... AN ACT <title>.
#   a CACR        INTRODUCED BY: ... REFERRED TO: ... RELATING TO: <subject>
#                 PROVIDING THAT: <what it does>
#   a resolution  HOUSE RESOLUTION NO. 1  RESOLVED, that ...
#
# The third has no sponsor and no committee because a House resolution has
# neither. That is the document, not a gap in the parser, and it is recorded
# as such rather than counted as a failure.
#
# STOP is every heading that can follow the one being read. Anchoring on one
# of them is what broke this the first time.
# Where a captured field ends: the label of the next field, or the head of
# the document proper. Each entry past the first line was added because a
# page needed it. "AMENDED ANALYSIS" follows an amended bill's committee;
# "STATE OF NEW HAMPSHIRE", the session line and the LSR number ("19-0789
# 11/06") are what follows a COMMITTEE: that names nobody, and without them
# the capture ran on into the bill.
STOP = (r"(?:REFERRED TO|AN ACT|AN ORDER|AN ADDRESS|A RESOLUTION|JOINT RESOLUTION|"
        r"CONCURRENT RESOLUTION|RELATING TO|PROVIDING THAT|RESOLVED|"
        r"AMENDED ANALYSIS|ANALYSIS|STATEMENT OF INTENT|STATE OF NEW HAMPSHIRE|"
        r"COMMITTEE:|SPONSORS?:|\d{4} SESSION|\d\d-\d{4}\s+\d\d\b)")
# A field begins with a letter (or the "[committee]" placeholder, dropped by
# clean) and not with the next label. "COMMITTEE: 2002 SESSION 02-2470" and
# "COMMITTEE: ANALYSIS This senate bill..." are a committee left blank, and
# both read as one before this.
BEGIN = r"(?!" + STOP + r")(?=[A-Za-z\[])"

# The labels are upper-case and end in a colon on every page that has one.
# Matching them case-blind with the colon optional let "COMMITTEE" find the
# word inside "AN ACT establishing a committee to study..." and report the
# bill's own study committee as the one it was referred to, and find
# "committees of the senate" and report "s of the senate".
SPONSOR_RE = [
    re.compile(r"INTRODUCED BY:\s*(.+?)\s*" + STOP),
    re.compile(r"SPONSORS?:\s*(.+?)\s*" + STOP),
]
COMMITTEE_RE = [
    re.compile(r"REFERRED TO:\s*" + BEGIN + r"(.+?)\s*" + STOP),
    re.compile(r"COMMITTEE:\s*" + BEGIN + r"(.+?)\s*" + STOP),
]
TITLE_RE = [
    # The opener is upper-case and the title after it lower-case, on every
    # page read: "AN ACT relative to term limits", "A RESOLUTION affirming
    # revenue estimates", "JOINT RESOLUTION supporting the improvement of
    # primary health care delivery" (1993, no article), "AN ORDER relative to
    # implementing an election" (a House concurrent order). Only AN ACT was
    # known before the sample: 94 pages open that way, 93 with CONCURRENT
    # RESOLUTION, 40 with JOINT RESOLUTION, 29 with A RESOLUTION. This is
    # case-sensitive, and the look-ahead for a lower-case letter is what
    # keeps the header "HOUSE CONCURRENT RESOLUTION 6" from being the title.
    # A House address ("AN ADDRESS for the removal of ... from his said
    # office") is the seventh opener. The full stop that ends a title is
    # not one after an initial or "St", "Mt", "Dr", "Jr", "No", "Inc":
    # "naming the Kenneth M. Tarr Highway" was ending at "Kenneth M".
    re.compile(r"\b(?:AN ACT|AN ORDER|AN ADDRESS|(?:A |AN )?(?:JOINT |CONCURRENT )?RESOLUTION)"
               r"\s+(?=[a-z])(.+?)(?:\s+SPONSORS?:|\s+COMMITTEE:|\s+ANALYSIS\b|"
               r"(?<![A-Z])(?<!\bSt)(?<!\bMt)(?<!\bDr)(?<!\bJr)(?<!\bNo)(?<!\bInc)\.\s)"),
    # A CACR states a subject and then what it would do. Both are the title.
    # In 1989 the sponsor and committee came before RELATING TO and the
    # analysis after; by 2009 SPONSORS: and COMMITTEE: follow it, and a
    # capture that ran on to ANALYSIS swallowed both, exceeded the cap, and
    # left the title to the RESOLVED clause -- "be amended as follows: I".
    re.compile(r"RELATING TO:?\s*(.+?)\s*(?:SPONSORS?:|COMMITTEE:|ANALYSIS|"
               r"EXPLANATION|STATEMENT OF INTENT|$)", re.I),
    re.compile(r"RESOLVED,?\s*(.+?)(?:\.\s|$)", re.I),
]
# A bill of intent (HBI, 1989-1994) carries a STATEMENT OF INTENT where a bill
# carries an ANALYSIS. The modern page ends its analysis with a rule of dashes
# and then the LSR number; the old one with EXPLANATION.
ANALYSIS_RE = re.compile(
    r"\b(?:ANALYSIS|STATEMENT OF INTENT)\b\s*(.+?)"
    r"(?=\s*(?:EXPLANATION\b|(?:-\s*){5,}|\u2500{5,}|STATE OF NEW HAMPSHIRE|"
    r"\d\d-\d{4}\s+\d\d\b)|$)", re.I)


def clean(s):
    """A captured field without the rule drawn after it.

    The modern page draws a line -- ASCII dashes on some pages, box-drawing
    characters on others -- between the committee and the analysis, and it
    was arriving inside the committee's name. "[committee]" is the template's
    placeholder for a committee never filled in, and is no committee.
    """
    s = re.sub(r"^[\s:;.\-\u2500-\u257f]+|[\s:;.\-\u2500-\u257f]+$", "", s)
    return "" if re.fullmatch(r"\[.*\]", s) else s

# NO SUCH RULE. There was one here -- NO_SPONSOR_KINDS = {"HR", "SR"} -- on
# the grounds that a simple resolution of one chamber names no sponsor and is
# referred to nobody. Four pages supported it. All four were from 1991-1994,
# because that is as far as the sample had fetched, and a modern House
# resolution does have sponsors and does get referred to a committee.
#
# So it was never a fact about the kind. It was a fact about the era, stated
# as a fact about the kind, from the only pages that had arrived yet -- which
# is this project's oldest failure wearing new clothes: a rule generalised
# from the subset that happened to be on disk.
#
# What replaces it is not a better rule but no rule. The report crosses kind
# with era and prints what was found, so "HR carries no sponsor before the
# mid-nineties and carries one after" is something a reader sees in the
# numbers rather than something this file asserts.


def parse(html):
    flat = flatten(html)
    got = {}
    # The cap on a sponsor list was 400 characters. Six pages exceed it --
    # SB 1 of 1995 names 21 sponsors in 478 -- and every one of the six was
    # reported as having no sponsor at all. 2,500 is room for a budget
    # trailer's forty-odd names; STOP is what keeps a runaway capture short.
    for rx in SPONSOR_RE:
        m = rx.search(flat)
        if m and len(m.group(1)) < 2500 and clean(m.group(1)):
            got["sponsors"] = clean(m.group(1))
            break
    for rx in COMMITTEE_RE:
        m = rx.search(flat)
        if m and len(m.group(1)) < 120 and clean(m.group(1)):
            got["committee"] = clean(m.group(1))
            break
    for rx in TITLE_RE:
        m = rx.search(flat)
        if m and 3 < len(m.group(1)) < 400:
            got["title"] = m.group(1).strip(" .,")
            break
    m = ANALYSIS_RE.search(flat)
    if m:
        got["analysis"] = m.group(1).strip()[:600]
    got["_chars"] = len(flat)
    return got


def report():
    """What is on disk, and what the parser makes of it, by year and kind."""
    if not OUT.is_dir():
        sys.exit(f"No {OUT}/. Fetch a sample first.")
    rows = []
    for f in sorted(OUT.rglob("*.html")):
        year = f.parent.name
        bid = f.stem
        kind = (PAD.match(bid) or re.match(r"([A-Z]+)", bid)).group(1)
        rows.append((int(year), kind, bid, parse(decode(f.read_bytes()))))
    if not rows:
        sys.exit(f"{OUT}/ holds no pages yet.")
    print(f"{len(rows):,} saved pages, {len({r[0] for r in rows})} years, "
          f"{len({r[1] for r in rows})} kinds")
    print()
    FIELDS = ["sponsors", "committee", "title", "analysis"]
    print(f"{'era':12}{'pages':>7}" + "".join(f"{f:>11}" for f in FIELDS))
    for lo in range(1989, 2027, 4):
        hi = lo + 3
        era = [r for r in rows if lo <= r[0] <= hi]
        if not era:
            continue
        line = f"{lo}-{str(hi)[2:]:2}{'':6}{len(era):>7}"
        for fld in FIELDS:
            n = sum(1 for r in era if r[3].get(fld))
            line += f"{n:>7}/{len(era):<3}"
        print(line)
    print()
    print(f"{'kind':12}{'pages':>7}" + "".join(f"{f:>11}" for f in FIELDS))
    for kind in sorted({r[1] for r in rows},
                       key=lambda k: -sum(1 for r in rows if r[1] == k)):
        ks = [r for r in rows if r[1] == kind]
        line = f"{kind:12}{len(ks):>7}"
        for fld in FIELDS:
            n = sum(1 for r in ks if r[3].get(fld))
            line += f"{n:>7}/{len(ks):<3}"
        print(line)
    # The ones a parser must be shown, not told about.
    # KIND AGAINST ERA, because whether a thing has a sponsor turns out to
    # depend on both. Printed rather than concluded from.
    kinds = sorted({r[1] for r in rows})
    eras = [(lo, lo + 7) for lo in range(1989, 2027, 8)]
    print()
    print("sponsors found, by kind and era (found/pages):")
    print(f"{'kind':8}" + "".join(f"{f'{lo}-{str(hi)[2:]}':>12}"
                                  for lo, hi in eras))
    for k in kinds:
        line = f"{k:8}"
        for lo, hi in eras:
            cell = [r for r in rows if r[1] == k and lo <= r[0] <= hi]
            if not cell:
                line += f"{'-':>12}"
            else:
                n = sum(1 for r in cell if r[3].get("sponsors"))
                line += f"{f'{n}/{len(cell)}':>12}"
        print(line)
    blank = [r for r in rows if not r[3].get("sponsors")]
    if blank:
        print()
        print(f"{len(blank)} pages yielded no sponsor. Whether that is the "
              "document or the parser\n  is what the table above is for -- a "
              "kind that has none in one era and\n  some in the next is the "
              "document changing, not a bug.")
        # All of them. Six of thirty-five was enough to see there were
        # blanks and not enough to see that most were housekeeping
        # resolutions and budget-category pages -- documents with no
        # sponsor -- and six were a sponsor list longer than the cap.
        for r in blank:
            print(f"    {r[0]} {r[2]:10} {r[3].get('_chars', 0):>7,} chars  "
                  + (r[3].get("title") or "(no title either)")[:52])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=10,
                    help="bills per year, spread across the kinds that year has")
    ap.add_argument("--from", dest="lo", type=int, default=1989)
    ap.add_argument("--to", dest="hi", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=15.0)
    ap.add_argument("--stop-refused", type=int, default=2)
    ap.add_argument("--parse", action="store_true",
                    help="read the saved pages and report; no network")
    a = ap.parse_args()

    if a.parse:
        return report()

    refusal.check("The legislation fetch")
    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    picked = sample(bills, a.sample, a.lo, a.hi)
    # The record travels with the bill because the text address is keyed by an
    # id that only the record carries.
    by_bill = {}
    for _term, bs in bills.items():
        for bid, rec in bs.items():
            y = str(rec.get("year") or rec.get("lsr_year") or "")[:4]
            if y.isdigit():
                by_bill[(int(y), bid)] = rec
    total = sum(len(v) for v in picked.values())
    blocked = sorted({y for y in picked
                      for bid in picked[y]
                      if not address(y, bid, by_bill.get((y, bid)))[0]})
    if blocked:
        print("no address known for: "
              + ", ".join(str(y) for y in blocked)
              + " -- those bills are skipped, not asked for")
    print(f"{total:,} bills across {len(picked)} years, {a.delay:g}s apart "
          f"-- about {total * a.delay / 60:.0f} minutes if none are cached")
    print()
    tally, refused = Counter(), 0
    for year in sorted(picked):
        line = []
        for bid in picked[year]:
            what = fetch(year, bid, a.delay if tally else 0,
                         rec=by_bill.get((year, bid)))
            tally[what] += 1
            line.append(f"{bid}:{what[0]}")
            if what == "refused":
                refused += 1
                if refused >= a.stop_refused:
                    print(f"  {year}: " + " ".join(line))
                    print()
                    print(f"{refused} refusals. Stopping, and refusal.py now "
                          "holds one for 24 hours.")
                    print("python3 netcheck.py says what kind it is without "
                          "making it worse.")
                    return 2
        print(f"  {year}: " + " ".join(line))
    print()
    print(", ".join(f"{v:,} {k}" for k, v in tally.most_common()))
    print(f"-> {OUT}/   then: python3 fetch_legislation.py --parse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
