#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.18
"""
The bill itself, from an address that can simply be constructed.

    python3 fetch_legislation.py --plan --from 1989 --to 2024   # no network
    python3 fetch_legislation.py --all --from 2021 --to 2021 --budget 800
    python3 fetch_legislation.py --sample 10 --from 1989 --to 2024
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
import os
import random
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
URL = "https://gc.nh.gov/legislation/{year}/{bill}.{ext}"
# One year of the thirty-eight is served at .htm. Padded and upper-case like
# every other year -- HB0297, not hb297 -- so the extension is the whole of
# the difference.
HTM_YEARS = {1996}
# The same document, served by the application instead of as a file. Proven
# the same document rather than assumed: the 2,234 pages in bill_text/ came
# from here, and today's parser reads sponsors, committee, title and analysis
# out of them exactly as it does out of a legislation/<year>/ page.
TEXT = ("https://gc.nh.gov/bill_status/legacy/bs2016/billText.aspx"
        "?id={id}&txtFormat=html&sy={year}")

# WHICH ADDRESS SERVES WHICH YEAR, and how each line was established.
#
# Every line here was opened in a browser by a person on 10 September. None
# of it was arrived at by a run trying addresses until one answered, which is
# what got this address blocked the first time.
#
# THE STATIC PATH serves 1989-2021, sampled ten bills a year, with two holes:
#
#     legislation/2016/HB1101.html                404
#     legislation/1996/hb297.htm                  404, and that is the
#                                                 archive's OWN published link
#     legislation/1996/HB0297.htm                 serves the bill
#
# So 1996 is not a hole: it is padded and upper-case like every other year and
# served at .htm, and the only address that does not work is the one the
# archive itself publishes. Worth stating plainly, because the reasoning that
# produced the wrong guess was this project's own first rule -- read the
# artefact, take the address from the source rather than inventing it -- and
# the source was wrong. Reading beats guessing still; it is not a guarantee.
#
# and it stops after 2021 -- fifty bills were asked for across 2022-2026 in
# the sample and every one 404'd, which fits the current terms being served
# by the application instead: bill_text/ holds 2,234 of them from billText.
#
# THE APPLICATION serves the same document. Proven rather than assumed: those
# 2,234 pages parse for sponsors, committee, title and analysis exactly as a
# legislation/<year>/ page does. Its id is not one scheme, and data/bills.json
# stores whatever the search results linked, which is not always what the
# address takes:
#
#     2016   stored 882016   used as stored   confirmed in a browser
#     2022   stored 1130     used as stored   confirmed in a browser
#     2023   stored 32       used as stored   confirmed in a browser, 11 Sep
#     2024   stored 4        used as stored   the same form as 2023
#     2025   stored 7        used as stored   the saved status pages
#     2026   stored 6        used as stored   the saved status pages
#
# 2023 AND 2024 SAID "WANTS THE YEAR APPENDED" UNTIL 11 SEPTEMBER, AND THAT WAS
# WRONG FOR 1,826 OF 1,996 BILLS. The saved status pages link lsr_num+year --
# a VERSIONED form ("v=HI&id=20372022") that the court also publishes -- and
# the rule generalised from the first page of each year, where the stored id
# happened to equal the LSR. Stored id + year is a form the court never
# publishes: for 615 bills it is ANOTHER bill's id, whose text would have
# been saved under this bill's name, and for 1,211 it is no bill at all. The
# court's own docket pages (docket_pages/, 1,203/1,203 for 2022, 675/675 and
# 1,321/1,321 for 2023-2024) link the plain form, the stored id as-is with
# sy=<year>; and billText.aspx?sy=2023&id=32 was opened by hand and serves
# 2023 HB42, its bill. So every application year takes the stored id, and
# the session named by sy is what makes a short id unambiguous. The LSR check
# in fetch() is what would catch it if that were ever not so.
#
# 2022 was the year nothing on this disk could answer -- there is no saved
# 2022 status page -- and both candidate forms were opened by hand:
#
#     id=11302022   error: Index 0 is either negative or above rows count
#     id=1130       serves the bill
#
# THAT ERROR IS WORTH KNOWING ON ITS OWN. An id that does not exist comes back
# as an application error inside an HTTP 200, not as a 404. A fetch that
# guessed ids would therefore save thousands of error pages and count them as
# documents, and --parse would report them as bills with no sponsor. This is
# why a year in neither set below returns no address at all rather than a
# guess: here, a wrong guess does not announce itself.
#
# WHICH LEAVES NOTHING. Every bill of every term from 1989 to 2026 now has an
# address: 27,171 by the static path and 6,512 by the application.
STATIC_404 = {2016, 2022, 2023, 2024, 2025, 2026}
ID_AS_STORED = {2022, 2023, 2024, 2025, 2026}
ID_PLUS_YEAR = set()
# 2016 HAS NO ADDRESS RULE THAT HOLDS, and the day it took to find that out is
# worth writing down. The table above said "used as stored, confirmed in a
# browser"; on 16 September a run stopped after three 56-byte answers in a row
# -- billText saying nothing rather than 404ing -- for 2016 HB105, HB110 and
# HB114, whose stored ids are 452016, 792016 and 862016.
#
# The person opened two addresses by hand:
#
#     id=882016&sy=2016   56 bytes, no bill
#     id=88&sy=2016       serves 2016 CACR 2, whose stored id is 882016
#
# which reads as "the year comes off", the mirror of what 2023-2024 turned out
# to need. It was tried, and the LSR check in fetch() refused the second page
# it asked for: id=79&sy=2016 prints LSR 2015-0500, not 2016's HB 110. So the
# stripped number is not this bill's id in a different year's clothes; it is
# another document's id altogether, and sy does not make it unambiguous.
# Two pages, no guessing further: the 1,072 bills of 2016 wait for the archive
# zip the IT office is preparing, or for them to say what id billText wants.
ID_MINUS_YEAR = set()

# The terms this site already has the text of, from the database and
# bill_text/. A run asks for the archive, not for them.
CURRENT_FROM = 2025

# FLOOR RESOLUTIONS HAVE NO TEXT HERE. A resolution introduced on the floor --
# memorials, honourings, organisation-day housekeeping -- carries an LSR in
# the 8000s or 9000s, and the General Court publishes a docket for it and no
# text: legislation/1990/HR0055.html is a 404, and advanced search finds its
# docket (bill_docket.aspx?lsr=9055&sy=1990) and no text either, both opened
# by hand on 11 September. 5 of the 8 sampled were 404. So they are not asked
# for; their one docket line is already on this disk in db/Docket.psv.
# Bills are not in this rule: the 1989 special-session HB1 is LSR 9100 and
# its page serves.
FLOOR_KINDS = {"HR", "SR", "HCR", "SCR", "HJR", "SJR"}
FLOOR_LSR = 8000

# What the firewall and a struggling server send instead of a bill, with a
# 200. The first two are this address being refused, and a run that saved
# them would keep them forever as bills. From fetch_bill_text.NOT_A_BILL.
BLOCKED = re.compile(r"Web Page Blocked|Attack ID", re.I)
BROKEN = re.compile(r"Runtime Error|Server Error in|Service Unavailable", re.I)

# A page names its own LSR near the top -- "05-1078 10/09", "89-0002 08" --
# on 268 of the 269 static pages in the sample that print one and on all
# 2,220 pages in bill_text/ that do. A bill carried into its second year
# prints its first year's: 1990 HB33 is LSR 1990-114 in data/bills.json and
# its page says 89-0114.
PAGE_LSR = re.compile(r"(?<![\d/-])(\d\d)-(\d{4})(?![\d/])")

# Addresses that answered 404 or an application error, kept so that no run
# asks for one twice. A person may delete an entry to have it asked again.
# Keyed by the ADDRESS, not the bill: 70 of the sample's 83 "missing" were
# 1996, 2016 and 2022-2026 bills asked for at a static address those years
# do not have, and a bill is not gone because a wrong address for it was.
GONE = Path("legislation/_gone.json")

# What the application says instead of 404ing. Both were met rather than
# imagined: the first by opening a wrong id by hand on 10 September, the
# second by the scrape that minted txtFormat=pdf links for 4,230 bills and
# got this back from every one of them.
ERROR_PAGE = re.compile(
    r"is either negative or above rows count|is neither a DataColumn", re.I)
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
    if year in ID_MINUS_YEAR:
        # The stored id ends in the session year; without it, it is the LSR the
        # address takes. An id that does not end in the year is left alone
        # rather than trimmed to something shorter that names another bill.
        s = m.group(1)
        return s[:-4] if s.endswith(str(year)) and len(s) > 4 else s
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
        return (URL.format(year=year, bill=pad,
                           ext="htm" if year in HTM_YEARS else "html"),
                "static")
    tid = text_id(rec or {}, year)
    if tid:
        return TEXT.format(id=tid, year=year), "billText"
    return None, f"no id known for {year}; see the table in this file"


def sample(bills, per_year, lo, hi, kinds=None):
    """A stratified draw: every kind a year has, before any kind twice."""
    by_year = defaultdict(lambda: defaultdict(list))
    for _term, bs in bills.items():
        for bid, rec in bs.items():
            y = str(rec.get("year") or rec.get("lsr_year") or "")[:4]
            m = PAD.match(bid.strip().upper())
            if y.isdigit() and lo <= int(y) <= hi and m and (
                    not kinds or m.group(1) in kinds):
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


def lsr_of(rec):
    """(year, number) of a bill's LSR from data/bills.json, or None."""
    rec = rec or {}
    y, n = str(rec.get("lsr_year") or ""), str(rec.get("lsr_num") or "")
    if not (y.isdigit() and n.isdigit()):
        m = re.match(r"^(\d{4})-(\d+)$", str(rec.get("lsr") or ""))
        if not m:
            return None
        y, n = m.groups()
    return int(y), int(n)


def is_floor_resolution(bid, rec):
    m = PAD.match((bid or "").strip().upper())
    lsr = lsr_of(rec)
    return bool(m and m.group(1) in FLOOR_KINDS and lsr and lsr[1] >= FLOOR_LSR)


def page_lsr(text):
    """The LSR a page prints about itself, as (two-digit year, number)."""
    m = PAGE_LSR.search(text[:1500])
    return (int(m.group(1)), int(m.group(2))) if m else None


def same_bill(text, rec):
    """True, False, or None where the page prints no LSR to check."""
    got, want = page_lsr(text), lsr_of(rec)
    if not got or not want:
        return None
    yy, num = got
    return num == want[1] and yy in (want[0] % 100, (want[0] - 1) % 100)


def gone_list():
    """The gone-list, or {} if there is none yet. A file that will not parse
    stops the run: read as empty, the next mark_gone() would rewrite it from
    nothing, and every address known to 404 would be askable again."""
    if not GONE.exists():
        return {}
    try:
        return json.loads(GONE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"{GONE} will not read ({e}). Not asking anything "
                         "until a person looks at it.")


def write_atomically(path, data):
    """Bytes to a temporary name, then into place: a run killed mid-write
    leaves the old file or none, never a truncated one that counts as held."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def mark_gone(url, why):
    """Merge one entry into the gone-list; never rewrite it from a subset."""
    g = gone_list()
    g[url] = f"{why}, {time.strftime('%Y-%m-%d')}"
    write_atomically(GONE, json.dumps(g, indent=1, sort_keys=True).encode("utf-8"))


# NO REDIRECTS. urlopen follows them silently, so one fetch could make
# several requests that are neither paced nor counted against --budget, and a
# redirect to a block or login page would come back as a 200. A 3xx is an
# HTTPError here, and a failure.
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


# The opener, a name so a check can stand a fake server in for the real one.
urlopen = urllib.request.build_opener(_NoRedirect).open

# The lock this run holds, or the lane's; set by main(), asked before every
# request whether the run may still ask.
HOLD = None


def fetch(year, bid, delay, rec=None):
    """One page, saved, or the reason it was not.

    Returns (outcome, detail). Outcomes that asked nothing of the server:
    "cached", "gone" (answered 404 or an error before; never asked twice),
    "floor" (a floor resolution, which has no text), "unreachable" (no
    address is known), "skipped". Outcomes that asked: "saved", "missing"
    (404 or 410), "error page", "failed" (5xx, a timeout, a dropped link),
    "dropped" (accepted and closed with no answer -- this address's sign of
    being refused), "refused" (403, 429 or the firewall's own block page),
    "wrong bill" (the page names another LSR; not saved).

    Both addresses save to the same place, so --parse never learns which one a
    page came from and does not need to: they serve the same document.
    """
    pad = padded(bid)
    if not pad:
        return "skipped", ""
    f = OUT / str(year) / f"{pad}.html"
    if f.exists() and f.stat().st_size > 200:
        return "cached", ""
    if is_floor_resolution(bid, rec):
        return "floor", ""
    url, _why = address(year, bid, rec)
    if not url:
        return "unreachable", _why
    if url in gone_list():
        return "gone", ""
    time.sleep(delay * random.uniform(0.75, 1.25) if delay else 0)
    # A refusal another process met while this one slept is a refusal here
    # too -- so this is asked AFTER the sleep, directly before the request.
    # "halted", not "refused": the record on file is somebody else's and is
    # not to be overwritten with this run's name.
    if refusal.MARK.exists():
        return "halted", "archive/refused.json is on file"
    if HOLD is not None and not HOLD.still():
        return "halted", "the lane holding archive/.lock is gone"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urlopen(req, timeout=30) as r:
            body = r.read()
    except Exception as e:
        # One reading of an error for every fetcher: a reset or a timeout
        # wrapped in a URLError is a dropped connection, not a failure, and
        # a 503 or a Retry-After is the server asking us to go away.
        kind = refusal.classify(e)
        why = (f"HTTP {e.code} on {url}" if isinstance(e, urllib.error.HTTPError)
               else f"{type(e).__name__}: {e}")
        if kind == "missing":
            mark_gone(url, f"HTTP {e.code}")
        return kind, why
    text = decode(body)
    if refusal.classify(body=text) == "refused":
        return "refused", "the firewall's block page, with a 200"
    if BROKEN.search(text[:4000]):
        return "failed", "a server error page, with a 200"
    # Nothing, or a skeleton: not a bill, and not a gap either. Saved, a body
    # over 200 bytes would count as held for good. The shortest real page on
    # disk that prints no LSR still has 139 characters of text.
    if len(flatten(text)) < 100 and page_lsr(flatten(text)) is None:
        return "empty", f"{len(body)} bytes and no bill in them"
    # An error is not a document, and this one arrives wearing HTTP 200.
    # Saved, it would sit in legislation/ looking like a bill and be counted
    # as one -- a page with no sponsor, no committee and no title, which is
    # indistinguishable from the housekeeping resolutions that genuinely have
    # none. Checked before the write so it never reaches the disk.
    if ERROR_PAGE.search(text[:4000]):
        mark_gone(url, "application error")
        return "error page", ""
    # THE PAGE MUST BE THE BILL. 615 bills of 2023-2024 were one address rule
    # away from being saved under another bill's name, and nothing would have
    # said so: --parse would have reported that bill's sponsors as these.
    if same_bill(flatten(text), rec) is False:
        why = (f"prints LSR {page_lsr(flatten(text))}, data/bills.json has "
               f"{lsr_of(rec)}")
        mark_gone(url, why)
        return "wrong bill", f"{url} {why}"
    # The bytes as served. Decoding is decode()'s job at parse time, so a
    # wrong guess about the encoding is corrected by re-parsing, not by
    # asking the General Court for the page again.
    write_atomically(f, body)
    return "saved", ""


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


def every_bill(bills, lo, hi, kinds=None):
    """{year: [bill, ...]} for every bill in the range, kind by kind."""
    by_year = defaultdict(list)
    for _term, bs in bills.items():
        for bid, rec in bs.items():
            y = str(rec.get("year") or rec.get("lsr_year") or "")[:4]
            m = PAD.match(bid.strip().upper())
            if not (y.isdigit() and lo <= int(y) <= hi and m):
                continue
            if kinds and m.group(1) not in kinds:
                continue
            by_year[int(y)].append(bid)
    rank = {k: i for i, k in enumerate(KIND_ORDER)}
    for y in by_year:
        by_year[y].sort(key=lambda b: (rank.get(PAD.match(b).group(1), 99),
                                       PAD.match(b).group(1),
                                       int(PAD.match(b).group(2))))
    return dict(by_year)


# What each outcome means for the run. Asking outcomes count toward --budget.
ASKED = {"saved", "missing", "error page", "failed", "dropped", "refused",
         "wrong bill", "empty"}
FAILURE = {"missing", "error page", "failed", "empty"}
MAX_IN_A_ROW = 3     # consecutive failures that end a run
MAX_MISSING = 10     # 404s (and the application's not-found) that end a run:
                     # past this it is a scan, not a gap
MAX_FAILURES = 10    # failures of any kind in one run, in a row or not: a
                     # server failing every other request is not a server to
                     # keep asking


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=10,
                    help="bills per year, spread across the kinds that year has")
    ap.add_argument("--all", action="store_true",
                    help="every bill in the range, not a sample")
    ap.add_argument("--kinds", default="",
                    help="only these kinds, comma-separated: HB,SB")
    ap.add_argument("--skip-year", dest="skip", action="append", type=int,
                    default=[],
                    help="a year to leave out of the run, repeatable. For a "
                         "year whose address is not settled: 2016's stored ids "
                         "already carry the year (882016) and billText answers "
                         "56 empty bytes to them, which stopped bills-08 after "
                         "three in a row on 15 September. Left out rather than "
                         "asked again with a guess.")
    ap.add_argument("--from", dest="lo", type=int, default=1989)
    # Not the current term: its text is in bill_text/ already, from the
    # database's own route, and asking again would be 2,234 requests for
    # nothing.
    ap.add_argument("--to", dest="hi", type=int, default=CURRENT_FROM - 1)
    ap.add_argument("--delay", type=float, default=15.0,
                    help="seconds between requests, jittered a quarter either way")
    ap.add_argument("--budget", type=int, default=400,
                    help="requests this run may make before it stops")
    ap.add_argument("--stop-refused", type=int, default=2,
                    help="dropped connections that end the run; a 403 ends it at one")
    ap.add_argument("--note", default="",
                    help="a label for the log, so a lane can queue a range twice")
    ap.add_argument("--plan", action="store_true",
                    help="say what would be asked for; no network, no lock")
    # NEWEST FIRST, because the recent terms are the ones people look up:
    # the person asked on 11 September for the text to come down from 2024
    # backwards, all of it eventually. The order within a year is unchanged
    # (bills, then constitutional amendments, then resolutions), and a run
    # still skips what is on disk, so the same line queued again carries on
    # from where the last one stopped.
    ap.add_argument("--newest-first", action="store_true",
                    help="work from the latest year in the range back to the "
                         "earliest")
    ap.add_argument("--parse", action="store_true",
                    help="read the saved pages and report; no network")
    a = ap.parse_args()

    if a.parse:
        return report()

    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    kinds = {k.strip().upper() for k in a.kinds.split(",") if k.strip()}
    picked = (every_bill(bills, a.lo, a.hi, kinds) if a.all
              else sample(bills, a.sample, a.lo, a.hi, kinds))
    for y in set(a.skip or []):
        if picked.pop(y, None):
            print(f"  {y} left out of this run (--skip-year)")
    # The record travels with the bill because the text address is keyed by an
    # id that only the record carries.
    by_bill = {}
    for _term, bs in bills.items():
        for bid, rec in bs.items():
            y = str(rec.get("year") or rec.get("lsr_year") or "")[:4]
            if y.isdigit():
                by_bill[(int(y), bid)] = rec

    # What a run would ask for, from disk alone.
    gone = gone_list()
    plan = {}
    for year in sorted(picked, reverse=a.newest_first):
        c = Counter()
        first = []
        for bid in picked[year]:
            rec = by_bill.get((year, bid))
            pad = padded(bid)
            f = OUT / str(year) / f"{pad}.html" if pad else None
            if not pad:
                c["skipped"] += 1
            elif f.exists() and f.stat().st_size > 200:
                c["cached"] += 1
            elif is_floor_resolution(bid, rec):
                c["floor"] += 1
            else:
                url, why = address(year, bid, rec)
                if not url:
                    c["unreachable"] += 1
                elif url in gone:
                    c["gone"] += 1
                else:
                    c["to ask"] += 1
                    c[why] += 1
                    if len(first) < 2:
                        first.append(url)
        plan[year] = (c, first)
    to_ask = sum(c["to ask"] for c, _ in plan.values())

    if a.plan:
        print(f"{'year':6}{'bills':>7}{'cached':>8}{'gone':>6}{'floor':>7}"
              f"{'no addr':>9}{'to ask':>8}  by")
        for year, (c, first) in plan.items():
            by = "billText" if c["billText"] else ("static" if c["static"] else "-")
            print(f"{year:<6}{len(picked[year]):>7}{c['cached']:>8}{c['gone']:>6}"
                  f"{c['floor']:>7}{c['unreachable']:>9}{c['to ask']:>8}  {by}"
                  + (f"   e.g. {first[0]}" if first else ""))
        hours = to_ask * a.delay / 3600
        print(f"\n{to_ask:,} requests to ask, about {hours:.0f} hours of "
              f"requests at {a.delay:g}s; floor resolutions and addresses "
              f"already answered 404 are not among them.")
        return 0

    # Silence is not success: a range with nothing in it is a mistake in the
    # range, and a lane would record it as done for good.
    if not sum(len(v) for v in picked.values()):
        print(f"no bills in {a.lo}-{a.hi}"
              + (f" of kinds {','.join(sorted(kinds))}" if kinds else "")
              + " in data/bills.json. Nothing to do is not the same as done.")
        return 3

    refusal.check("The legislation fetch")
    global HOLD
    with refusal.hold("fetch_legislation") as held:
        HOLD = held
        return run(a, picked, by_bill, to_ask)


def run(a, picked, by_bill, to_ask):
    t0 = time.time()
    print(f"{to_ask:,} to ask in {a.lo}-{a.hi}"
          + (f" ({a.note})" if a.note else "")
          + f"; this run stops at {a.budget:,} requests. {a.delay:g}s apart, "
          f"jittered. Two dropped connections, or one 403, end it.",
          flush=True)
    tally, asked, in_a_row, dropped, wrong = Counter(), 0, 0, 0, 0

    def summary():
        mins = (time.time() - t0) / 60
        print(f"\n{asked:,} asked in {mins:.0f} min: "
              + ", ".join(f"{v:,} {k}" for k, v in tally.most_common()),
              flush=True)

    for year in sorted(picked, reverse=a.newest_first):
        for bid in picked[year]:
            if asked >= a.budget:
                summary()
                print(f"budget of {a.budget:,} reached. Nothing already on "
                      "disk is asked for again, so the same command continues "
                      "from here.", flush=True)
                return 0
            what, why = fetch(year, bid, a.delay, rec=by_bill.get((year, bid)))
            tally[what] += 1
            if what == "halted":
                summary()
                print(f"\nHALTED before asking: {why}. Nothing more is asked; "
                      "the record on file is left as it is.", flush=True)
                return 2 if "refused" in why else 3
            if what not in ASKED:
                continue
            asked += 1
            if what == "saved":
                in_a_row = 0
            if asked % 25 == 0:
                print(f"  {year} {bid}: {asked:,} asked, {tally['saved']:,} "
                      f"saved, {tally['missing']:,} missing, "
                      f"{(time.time() - t0) / 60:.0f} min", flush=True)
            if what == "refused":
                refusal.note("fetch_legislation", why)
                summary()
                print(f"\nREFUSED: {why}. Stopping, and refusal.py now holds "
                      "one: every fetch stops until a person clears it.\n"
                      "python3 netcheck.py says what kind it is without "
                      "making it worse.", flush=True)
                return 2
            if what == "dropped":
                dropped += 1
                if dropped >= a.stop_refused:
                    refusal.note("fetch_legislation", why)
                    summary()
                    print(f"\n{dropped} dropped connections ({why}): the "
                          "address closing on us without an answer, which is "
                          "what being refused looks like here. Stopping; "
                          "refusal.py holds it.", flush=True)
                    return 2
                print(f"  dropped ({why}) on {year} {bid}; cooling off 120s",
                      flush=True)
                time.sleep(120)
                continue
            if what == "wrong bill":
                # One can be the record rather than the rule: 1989's special
                # session HB1 carries a made-up LSR (9100) in data/bills.json
                # and its page prints the real one. A wrong rule is wrong on
                # every request, so two in a run is the signal.
                wrong += 1
                print(f"  WRONG BILL: {year} {bid} -- {why}. Not saved; on "
                      "the gone-list for a person to read.", flush=True)
                if wrong >= 2:
                    summary()
                    print(f"\n{wrong} pages in one run name another bill. An "
                          "address rule is naming the wrong bill, and every "
                          "page after this would be filed under the wrong "
                          "name. Stopping for a person to look.", flush=True)
                    return 3
                continue
            if what in FAILURE:
                in_a_row += 1
                print(f"  {what} on {year} {bid}"
                      + (f" ({why})" if why else ""), flush=True)
                if in_a_row >= MAX_IN_A_ROW:
                    summary()
                    print(f"\n{in_a_row} failures in a row. Something has "
                          "changed -- the address, the server or this "
                          "script's idea of where a bill lives -- and asking "
                          "on regardless is how the last block was earned. "
                          "Stopping.", flush=True)
                    return 3
                # The application answers a missing id with an error page
                # and a 200, so on its path this IS the 404.
                gone_n = tally["missing"] + tally["error page"]
                if gone_n >= MAX_MISSING:
                    summary()
                    print(f"\n{gone_n} addresses answered 404 or not-found "
                          "in one run. They are on the gone-list and will not "
                          "be asked again, but this many is a rule that is "
                          "wrong about where a year's bills live, and a run "
                          "asking on would be probing. Stopping.", flush=True)
                    return 3
                if sum(tally[k] for k in FAILURE) >= MAX_FAILURES:
                    summary()
                    print(f"\n{MAX_FAILURES} failures in one run, between "
                          "saves. A server failing every other request is "
                          "not one to keep asking. Stopping.", flush=True)
                    return 3
                if what in ("failed", "empty"):
                    # A server that failed gets longer before the next one.
                    time.sleep(a.delay * 3)
    summary()
    # Silence is not success: a run that asked and saved nothing is a run
    # that met a wall it could not name.
    if asked and not tally["saved"]:
        print("asked and saved nothing. Stopping for a person to look.",
              flush=True)
        return 3
    print(f"the range is done. -> {OUT}/   then: python3 fetch_legislation.py "
          "--parse", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
