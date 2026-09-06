#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.4
"""
Find the journal and calendar PDFs so docket citations become links.

Keys carry the year: "HJ 7 2026" as well as "HJ 7". The same journal number
comes round every session, so a key without a year makes 2025's HJ 7 and
2026's HJ 7 the same entry, and adding a second session would quietly
repoint one year's citations at the other's documents. The bare key is
written too, so nothing that already depends on it breaks.

    python3 fetch_journals.py --year 2026

Almost every docket action ends in a citation: "HJ 7 P. 55", "SC 11", "HC 10".
Those name the House or Senate Journal, or the Calendar, and the page within it
-- the official record of that action. We parse them today only to strip them
out, which throws away the best provenance in the whole dataset.

    Ought to Pass with Amendment 2026-0503h: MA VV 03/11/2026  HJ 7  P. 55
                                                               ^^^^^^^^^^^
                                          the authoritative source for that line

Journals are published per session day and numbered in order, so the same trick
that found the calendars works here: walk the session dates, try the next
journal number at each, keep what returns a PDF. Session dates come from the
roll call file, which records one per sitting.

Writes journals.json: {"HJ 7": "https://...", "SC 11": "https://...", ...}
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}

# Real examples, both chambers:
#   /house/calendars_journals/Journals/2026/HJ 07 March 11, 2026.PDF
#   /senate/calendars_journals/Journals/2026/SJ 11 May 7, 2026.PDF
#   /senate/calendars_journals/Calendars/2026/No 11 March 19 2026.PDF
BASE = "https://gc.nh.gov/{chamber}/calendars_journals/"


# Read the list; do not guess at the filenames.
#
# gc.nh.gov/{chamber}/calendars_journals is the same page the calendars come
# from, with a first dropdown that switches between Calendars and Journals. Its
# document options carry the FILENAME as their value and the number and date as
# their label, for every year back to 1997.
#
# This replaces a search that guessed: eight filename spellings per journal,
# multiplied by a window of candidate numbers per sitting, against a name that
# has to have the right date in it. That is hundreds of requests for files that
# mostly do not exist, which is the shape the General Court's firewall read as
# an attack when the calendar fetcher did the same thing -- and it blocked the
# address for it.
#
# Three requests now: load the page, switch to Journals, switch the year.
SEL_YEAR = "ctl00$pageBody$ddlYears"
SEL_KIND = "ctl00$pageBody$ddlCalJourn"
SEL_DOC = "ctl00$pageBody$ddlDoc"

SELECT_RE = re.compile(r"<select\b[^>]*\bname=[\"'](?P<name>[^\"']+)[\"'][^>]*>"
                       r"(?P<body>.*?)</select>", re.S | re.I)
OPTION_RE = re.compile(r"<option\b(?P<attrs>[^>]*)>(?P<text>.*?)</option>", re.S | re.I)
HIDDEN_RE = re.compile(r"<input\b[^>]*type=[\"']hidden[\"'][^>]*>", re.I)
ATTR_RE = re.compile(r"([\w:-]+)\s*=\s*[\"']([^\"']*)[\"']")
# "HJ 11 April 29, 2026", "No 7 February 13 2026", "J 4 January 8 2026"
DOCNUM_RE = re.compile(r"\b(?:No|[HS]?J)\s*(\d+[A-Za-z]?)\b", re.I)
WS_J = re.compile(r"\s+")


def _attrs(s):
    return {k.lower(): v for k, v in ATTR_RE.findall(s or "")}


def _hidden(page):
    out = {}
    for m in HIDDEN_RE.finditer(page):
        a = _attrs(m.group(0))
        if a.get("name"):
            out[a["name"]] = a.get("value", "")
    return out


def _options(page, name):
    for m in SELECT_RE.finditer(page):
        if m.group("name") == name:
            return [(_attrs(o.group("attrs")).get("value", ""),
                     WS_J.sub(" ", re.sub(r"<[^>]+>", "", o.group("text"))).strip())
                    for o in OPTION_RE.finditer(m.group("body"))]
    return []


def journal_urls(chamber, letter, year, delay=2.0):
    """{number: url} for one chamber's journals in one year, from the index."""
    index = BASE.format(chamber=chamber)

    def fetch(data=None):
        req = urllib.request.Request(
            index, data=data,
            headers=dict(UA, **({"Content-Type":
                                 "application/x-www-form-urlencoded"} if data
                                else {})))
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", errors="replace")

    print(f"  reading the {chamber} journal list for {year}")
    page = fetch()
    years = [v for v, _ in _options(page, SEL_YEAR)]
    if years and str(year) not in years:
        print(f"    {year} is not offered; the page lists {years[0]} back to "
              f"{years[-1]}")
        return {}

    # Journals, and the right year. One post does both.
    fields = _hidden(page)
    fields[SEL_KIND] = "Journal"
    fields[SEL_YEAR] = str(year)
    fields["__EVENTTARGET"] = SEL_KIND
    fields["__EVENTARGUMENT"] = ""
    time.sleep(delay)
    page = fetch(urllib.parse.urlencode(fields).encode())
    docs = _options(page, SEL_DOC)

    # Switching two dropdowns at once can leave the year behind, so if the
    # labels do not name the year asked for, ask again for the year alone.
    if docs and not any(str(year) in lbl for _, lbl in docs):
        fields = _hidden(page)
        fields[SEL_KIND] = "Journal"
        fields[SEL_YEAR] = str(year)
        fields["__EVENTTARGET"] = SEL_YEAR
        fields["__EVENTARGUMENT"] = ""
        time.sleep(delay)
        docs = _options(fetch(urllib.parse.urlencode(fields).encode()), SEL_DOC)

    out = {}
    for value, label in docs:
        if not value or str(year) not in label:
            continue
        m = DOCNUM_RE.search(label) or DOCNUM_RE.search(value)
        if not m:
            continue
        key = m.group(1)
        out[int(key) if key.isdigit() else key] = (
            index + "viewer.aspx?fileName="
            + urllib.parse.quote(f"journals\\{year}\\{value}"))
    nums = [k for k in out if isinstance(k, int)]
    print(f"    {len(out)} journals listed"
          + (f", numbered {min(nums)} to {max(nums)}" if nums else ""))
    if not out:
        print("    Nothing in the list. Send the output of "
              "probe_calendars.py, which reads the same page.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True)
    ap.add_argument("--out", default="journals.json")
    ap.add_argument("--delay", type=float, default=0.7)
    a = ap.parse_args()

    found = {}
    if Path(a.out).exists():
        found = json.loads(Path(a.out).read_text(encoding="utf-8"))
        print(f"{len(found)} already known in {a.out}")

    failed, counts = [], {}
    for body, chamber, letter in (("H", "house", "H"), ("S", "senate", "S")):
        try:
            urls = journal_urls(chamber, letter, a.year, a.delay)
        except Exception as e:
            print(f"  {chamber}: could not read the list: "
                  f"{type(e).__name__}: {e}")
            failed.append(chamber)
            continue
        counts[chamber] = len(urls)
        for num, url in sorted(urls.items(), key=lambda x: str(x[0])):
            # Keyed with the year as well as the number, because the same
            # journal number comes round every session and one key for both
            # would repoint a 2025 citation at a 2026 document.
            found[f"{letter}J {num} {a.year}"] = url
            found.setdefault(f"{letter}J {num}", url)

    Path(a.out).write_text(json.dumps(found, indent=2, sort_keys=True),
                           encoding="utf-8")
    print()
    print(f"{len(found)} journal links -> {a.out}")
    for chamber, n in counts.items():
        print(f"  {chamber}: {n} listed for {a.year}")
    print("build_site_v2.py reads this and turns 'HJ 7 P. 55' in a docket line")
    print("into a link to that journal, which is the official record of the")
    print("action being described.")

    # A chamber that could not be read leaves this file looking finished. The
    # count above is the whole file, not the whole year, so one chamber missing
    # is invisible in it -- the Senate 500 on 6 September left every Senate
    # journal on its bare key while the House gained year-keyed ones, and the
    # closing line still said 46 links. Say so, and exit non-zero.
    if failed:
        print()
        print(f"INCOMPLETE: {', '.join(failed)} could not be read, so {a.out}")
        print(f"holds nothing new for that chamber in {a.year} and the total")
        print("above is not the whole of it. This merges, so re-running when")
        print("the server answers loses nothing already fetched.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
