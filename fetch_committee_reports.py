#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.19
"""
Pull committee majority and minority reports out of the House Calendars.

These are the written reasoning behind a committee's recommendation, and they
exist ONLY in the calendars. The docket records that a committee voted 10-8 for
ought-to-pass; the calendar records why the majority thought so and why the
minority disagreed, signed by name. For anyone asking what the legislature
intended -- which is the question a court asks -- this is the primary evidence,
and it is currently locked in PDFs that nobody indexes.

The docket gives the join key. A House committee report entry ends with
"HC 17", meaning House Calendar edition 17.

    python3 fetch_committee_reports.py --year 2025
    python3 fetch_committee_reports.py --year 2025 --pdf "No16 March 14 2025.PDF"

Text extraction, best first:
    pdftotext -layout   (poppler; much the best on two-column calendars)
    pdfplumber          (pip install pdfplumber)
    pypdf               (pip install pypdf; last resort, columns may interleave)
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

INDEX = "https://gc.nh.gov/house/calendars_journals/"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}

# Bill numbers carry stacked suffixes: HB 660-FN-LOCAL, HB 1442-FN-A-LOCAL.
# Matching only -FN, -A and -L meant "HB 660-FN-LOCAL," never registered as the
# start of a new section, so the previous committee's report swallowed it.
# And a heading BEGINS A LINE. That is what tells it apart from a bill number
# inside a sentence: House Calendar 10 of 2026 contains "...has effectively
# prevented many towns and school districts from adopting SB 2, concentrating
# budgetary and governance decisions among a relatively small number of
# attendees...", which split a real minority report in half and filed the
# second half under a bill called SB2. There is no SB2 this term; the phrase
# is the name New Hampshire gives the ballot-vote form of town meeting.
#
# So the sections are cut from the RAW text, before clean_pdf_text collapses
# every newline to a space, and each section is cleaned afterwards.
BILL_START = re.compile(
    r"(?:\A|[\r\n])[ \t]*"
    r"(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*)\s*,\s*",
    re.I)

# A report also ends when the calendar moves to another kind of business. These
# headings are the terminators; without them the last report on a page absorbs
# the meeting notices, fiscal notes and everything after.
# Headings that end a report. CONSENT CALENDAR and REGULAR CALENDAR are NOT
# among them: those are the headings the reports live under, and treating them
# as terminators silently dropped every report on the consent calendar --
# which is most unanimous committee reports.
SECTION_END = re.compile(
    r"\b(COMMITTEE MEETINGS|REVISED FISCAL NOTES|NOTICES|AMENDMENTS?\s+TO\s+"
    r"HOUSE RULES|SPECIAL ORDERS|UNANIMOUS CONSENT|"
    r"MEMBERS[\u2019\']?\s+NOTICES|ANNOUNCEMENTS|LATE SESSION|"
    r"DAILY CALENDAR|SPEAKER[\u2019\']?S? ANNOUNCEMENTS)\b")

# Running page furniture, e.g. "2 JANUARY 2026 HOUSE RECORD 5", lands in the
# middle of sentences once the columns are flattened.
# The running header, in every arrangement the page puts it in. Read as text a
# PDF lays the header into the middle of whatever sentence spans the page
# break, so this has to strip inline, not by line:
#
#     ... by replacing it with the following: 31 JANUARY 2025 HOUSE RECORD 29
#         II. A student who has obtained ...
#     ... and unanimously voted yea. Vote 16-0. 4 31 JANUARY 2025
#
# The old pattern wanted the full "date HOUSE RECORD page" and so missed the
# second, which is a page number and a date with nothing between them.
#
# A page number or the title must be adjacent: an all-capital date on its own
# is not enough to delete, because bill text is sometimes set in capitals and
# deleting a real clause is far worse than leaving a header in one.
_MON = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|"
        "NOVEMBER|DECEMBER")
_DATE = rf"\d{{1,2}}\s+(?:{_MON})\s+\d{{4}}"
PAGE_FURNITURE = re.compile(
    r"\s*(?:"
    rf"\d{{1,3}}\s+{_DATE}(?:\s+HOUSE\s+RECORD)?"
    rf"|{_DATE}\s+HOUSE\s+RECORD(?:\s+\d{{1,3}})?"
    rf"|HOUSE\s+RECORD\s+\d{{1,3}}\s+{_DATE}"
    rf"|{_DATE}\s+\d{{1,3}}\s+HOUSE\s+RECORD"
    rf"|HOUSE\s+RECORD\s+{_DATE}"
    rf"|\d{{1,3}}\s+HOUSE\s+RECORD\s+{_DATE}"
    r")\s*")

# Enough to notice a consent-calendar section, not enough to classify one.
CONSENT_HINT = re.compile(r"consent calendar", re.I)

RECS = (r"OUGHT TO PASS WITH AMENDMENT|OUGHT TO PASS W/ ?AMENDMENT|OUGHT TO PASS|"
        r"INEXPEDIENT TO LEGISLATE|INTERIM STUDY|REFER FOR INTERIM STUDY|"
        r"RETAIN(?:ED)?(?: IN COMMITTEE)?|WITHOUT RECOMMENDATION|"
        r"RE-?REFER TO COMMITTEE")

MAJ_MIN = re.compile(rf"MAJORITY\s*:\s*(?P<maj>{RECS})\s*\.?\s*"
                     rf"(?:MINORITY\s*:\s*(?P<min>{RECS})\s*\.?)?", re.I)
SOLO_REC = re.compile(rf"(?<![:\w])(?P<rec>{RECS})\s*\.", re.I)

# "Rep. Rick Ladd for the Majority of Education Funding."
# "Rep. Jennifer Rhodes for the Majority of Criminal Justice and Public Safety."
# "Rep. Cassandra Levesque for the Minority of Education Funding."
# "Rep. Susan Almy for Ways and Means."   (unanimous -- no majority/minority)
# The committee's vote, printed at the END of the report body rather than in a
# field of its own. Real forms the General Court uses, in the calendars and in
# the docket line that mirrors them:
#
#     Vote 12-8.        Vote: 12-8        (Vote 12-8; CC)       Vote 19-0; RC
#
# Captured and cut out of the text, so the number can sit beside the label it
# belongs to instead of trailing a paragraph of prose. The trailing letters are
# the calendar the report was placed on -- Consent or Regular -- not a roll
# call, which is the one abbreviation in these files that means two things.
VOTE_TAIL = re.compile(
    r"[\s(]*\bVote[:\s]\s*(?P<y>\d{1,3})\s*[-\u2013]\s*(?P<n>\d{1,3})"
    r"\s*(?:[;,]\s*(?P<cal>CC|RC))?\s*[).]?", re.I)
# How much may follow the vote and still be furniture rather than report. A
# page number and a running date header is about twenty characters; sixty is
# generous and still far short of a paragraph.
VOTE_TAIL_SLACK = 60

AUTHOR = re.compile(
    r"(?P<who>(?:Rep|Sen)\.\s+[A-Z][\w'’.\-]*(?:\s+[A-Z][\w'’.\-]*){0,3})\s+for\s+"
    r"(?:the\s+(?P<side>Majority|Minority)\s+of\s+)?"
    r"(?P<committee>[A-Z][A-Za-z,&\-\s]{2,60}?)\s*\.\s+",
    re.I)


def clean_pdf_text(t):
    """PDF extraction artefacts: soft hyphens, hyphenated line breaks, column dots.

    Order matters. Words broken across lines are marked with a soft hyphen, so
    the rejoin has to happen BEFORE soft hyphens are stripped, or "ef<shy>fect"
    silently becomes "ef fect".
    """
    t = re.sub(r"(\w)[\u00ad\-\u2010\u2011]\s*\n\s*(\w)", r"\1\2", t)  # rejoin first
    t = t.replace("\u00ad", "")
    t = re.sub(r"[·•]\s*", " ", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    t = PAGE_FURNITURE.sub(" ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def extract_text(pdf):
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                             capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout, "pdftotext -layout"
    try:
        import pdfplumber
        with pdfplumber.open(pdf) as d:
            return "\n".join(p.extract_text() or "" for p in d.pages), "pdfplumber"
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        r = PdfReader(str(pdf))
        return "\n".join(p.extract_text() or "" for p in r.pages), "pypdf"
    except ImportError:
        sys.exit("No PDF text extractor. Install poppler (pdftotext) or "
                 "run: pip install pdfplumber")


# The page's own list, rather than a guess at what the files are called.
#
# gc.nh.gov/house/calendars_journals is an ASP.NET page with three dropdowns:
# calendars or journals, the year back to 1997, and the document. The document
# options carry the FILENAME as their value, so there is nothing to work out.
#
# This matters because there is no filename convention to work out. Within one
# year the values run:
#
#     HC 32.pdf                     No 32 September 4 2026
#     HC 31.pdf                     No 31 August 28 2026
#     No30 August 14 2026.pdf       No30 August 14 2026
#
# and 2025 uses the dated form throughout while 2026 switched to the short one
# partway through the session. Discovery used to probe thirty-two spellings a
# week against that, about a thousand requests for files that mostly did not
# exist -- which is a directory scan, and was read as one, and got the address
# blocked. It also found nothing for 2025, whose fifty-four calendars were in
# the dropdown the whole time.
#
# Now: one request to load the page, one more to switch the year, and the list
# is exact. Nothing is asked for that does not exist.
SEL_YEAR = "ctl00$pageBody$ddlYears"
SEL_KIND = "ctl00$pageBody$ddlCalJourn"
SEL_DOC = "ctl00$pageBody$ddlDoc"

SELECT_RE = re.compile(r"<select\b[^>]*\bname=[\"'](?P<name>[^\"']+)[\"'][^>]*>"
                       r"(?P<body>.*?)</select>", re.S | re.I)
OPTION_RE = re.compile(r"<option\b(?P<attrs>[^>]*)>(?P<text>.*?)</option>", re.S | re.I)
HIDDEN_RE = re.compile(r"<input\b[^>]*type=[\"']hidden[\"'][^>]*>", re.I)
ATTR_RE = re.compile(r"([\w:-]+)\s*=\s*[\"']([^\"']*)[\"']")
# "No 32 September 4 2026", "No10A March 6 2026", "No 8a February 20 2026"
DOCNUM_RE = re.compile(r"\bNo\s*(\d+[A-Za-z]?)\b")
WS = re.compile(r"\s+")


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
                     WS.sub(" ", re.sub(r"<[^>]+>", "", o.group("text"))).strip())
                    for o in OPTION_RE.finditer(m.group("body"))]
    return []


def calendar_urls(year, delay=2.0, rediscover=False):
    """{number: url} for every House calendar of one year, from the index page.

    Two requests at most, and both for pages that exist.
    """
    def fetch(data=None):
        req = urllib.request.Request(
            INDEX, data=data,
            headers=dict(UA, **({"Content-Type":
                                 "application/x-www-form-urlencoded"}
                                if data else {})))
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", errors="replace")

    print(f"  reading the calendar list for {year}")
    page = fetch()
    docs = _options(page, SEL_DOC)
    listed = [v for v, _ in _options(page, SEL_YEAR)]
    shown = next((v for v, txt in _options(page, SEL_DOC)
                  if str(year) in txt), None)

    if not shown:
        if str(year) not in listed:
            print(f"  {year} is not offered; the page lists "
                  f"{listed[0]} back to {listed[-1]}")
            return {}
        fields = _hidden(page)
        fields[SEL_KIND] = "Calendar"
        fields[SEL_YEAR] = str(year)
        fields["__EVENTTARGET"] = SEL_YEAR
        fields["__EVENTARGUMENT"] = ""
        time.sleep(delay)
        page = fetch(urllib.parse.urlencode(fields).encode())
        docs = _options(page, SEL_DOC)

    out = {}
    for value, label in docs:
        if not value or str(year) not in label:
            continue
        m = DOCNUM_RE.search(label) or DOCNUM_RE.search(value)
        if not m:
            continue
        key = m.group(1)
        key = int(key) if key.isdigit() else key
        out[key] = (INDEX + "viewer.aspx?fileName="
                    + urllib.parse.quote(f"calendars\\{year}\\{value}"))

    nums = [k for k in out if isinstance(k, int)]
    extra = [k for k in out if not isinstance(k, int)]
    print(f"  {len(out)} calendars listed for {year}"
          + (f", numbered {min(nums)} to {max(nums)}" if nums else "")
          + (f", plus {len(extra)} supplements" if extra else ""))
    if not out:
        print("  Nothing in the list for that year. Send the output of "
              "probe_calendars.py.")

    cal = {}
    cp = Path("calendars.json")
    if cp.exists():
        try:
            cal = json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            cal = {}
    cal.update({f"HC {k} {year}": u for k, u in out.items()})
    cal.update({f"HC {k}": u for k, u in out.items()})
    cp.write_text(json.dumps(cal, indent=2, sort_keys=True), encoding="utf-8")
    print(f"  {len(cal)} calendar links -> calendars.json")
    return out


def parse_reports(text, source, skipped=None, skipped_samples=None):
    """Split into bill sections, then read the recommendations and signed prose."""
    skipped = skipped if skipped is not None else [0]
    skipped_samples = skipped_samples if skipped_samples is not None else []
    # start("bill"), not start() -- the pattern matches the line break before
    # the number too, and slicing from the wrong offset eats a digit off it.
    marks = [(m.start("bill"), m.group("bill")) for m in BILL_START.finditer(text)]
    reports = defaultdict(list)

    for i, (pos, bill) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        chunk = clean_pdf_text(text[pos:end])
        # Cut at the first heading that starts a different kind of business.
        cut = SECTION_END.search(chunk, 60)
        if cut:
            chunk = chunk[:cut.start()]
        if len(chunk) < 120:
            continue

        mm = MAJ_MIN.search(chunk)
        if mm:
            maj = (mm.group("maj") or "").upper()
            mino = (mm.group("min") or "").upper() or None
        else:
            s = SOLO_REC.search(chunk)
            if not s:
                continue
            maj, mino = s.group("rec").upper(), None

        title = chunk[len(bill):].split(".")[0].strip(" ,.")
        blocks = list(AUTHOR.finditer(chunk))
        entries = []
        for j, a in enumerate(blocks):
            body = chunk[a.end(): blocks[j + 1].start() if j + 1 < len(blocks) else len(chunk)]
            body = body.strip()
            # Trailing committee heading in caps belongs to the next section.
            body = re.sub(r"\s+(?:[A-Z][A-Z&,\-]{1,}(?:\s+|$)){1,6}$", "", body).strip()
            if len(body) < 40:
                continue
            entry = {
                "side": (a.group("side") or "Committee").title(),
                "author": " ".join(a.group("who").split()),
                "committee": " ".join(a.group("committee").split()),
            }
            # The vote is not always the last thing on the page: a page
            # number, the running date header, an editorial note -- all of it
            # lands after the vote when the PDF is read as text.
            #
            #     ... and unanimously voted yea. Vote 16-0. 4 31 JANUARY 2025
            #     ... to external creators. Vote 18-0. To Be Withdrawn
            #
            # Requiring the vote at the very end missed every one of those,
            # 345 reports in 2025 alone. So: the LAST vote that has only
            # furniture after it. A report may quote an earlier vote in its
            # own prose, and that one is not its own.
            v = None
            for cand in VOTE_TAIL.finditer(body):
                if len(body) - cand.end() <= VOTE_TAIL_SLACK:
                    v = cand
            if v:
                entry["vote_yeas"] = int(v.group("y"))
                entry["vote_nays"] = int(v.group("n"))
                if v.group("cal"):
                    entry["calendar"] = v.group("cal").upper()
                body = body[:v.start()].strip(" .;,")
            entry["text"] = body
            entries.append(entry)

        key = re.sub(r"\s+", "", bill.upper()).split("-")[0]
        # A bill sitting on the table is reprinted in every calendar that
        # follows, and each reprint matched a recommendation without carrying
        # any signed prose. Those were stored anyway, so HCR 11 showed
        # "Committee reports (0)" above twenty-four "Source: House Calendar N"
        # lines: a citation for a report that is not there.
        #
        # A record with no report in it says nothing the docket has not already
        # said, so it is not kept.
        if not entries:
            # WHY it carried no signed report is not something this knows. It
            # has been reported as "a reprint of a bill still on the table"
            # since the HCR 11 fix, and that was an inference from one case,
            # printed ever since as though it were a finding. A consent
            # calendar entry may simply be laid out differently -- a short
            # recommendation with no "Rep. X for the Committee" line to sign
            # it -- and if so these are real reports being dropped.
            #
            # So the sections are kept for inspection rather than counted and
            # discarded. Whether they are reprints is a question the calendars
            # can answer.
            skipped[0] += 1
            if len(skipped_samples) < 400:
                skipped_samples.append((bill, WS.sub(" ", chunk).strip()[:260]))
            continue
        reports[key].append({
            "bill": key, "title": title[:300],
            "majority_recommendation": maj,
            "minority_recommendation": mino,
            "reports": entries, "source": source,
        })
    return reports


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=2.0,
                    help="seconds between probes (default 2; the firewall "
                         "blocked us at 0.7)")
    ap.add_argument("--force-write", action="store_true",
                    help="write the output even if it collapsed")
    ap.add_argument("--rediscover", action="store_true",
                    help="probe the whole filename space again, ignoring "
                         "calendars.json")
    ap.add_argument("--year", required=True)
    ap.add_argument("--pdf", help="one local or named calendar; omit to do the year")
    ap.add_argument("--offline", action="store_true",
                    help="re-read the calendars already in the cache and make "
                         "no network request at all")
    ap.add_argument("--cache", default="calendars")
    ap.add_argument("--out", default="committee_reports.json")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    cache = Path(a.cache) / a.year
    cache.mkdir(parents=True, exist_ok=True)

    if a.pdf and Path(a.pdf).exists():
        targets = [(0, Path(a.pdf))]
    elif a.offline:
        # Every calendar already in the cache, and not one request. This exists
        # so a PARSER change can be applied to what is already downloaded: the
        # network half of this script is discovery and download, and neither is
        # needed to re-read a PDF sitting on the disk.
        targets = []
        for f in sorted(cache.glob("HC*.pdf")):
            m = re.match(r"HC0*(\d+)([A-Z]*)\.pdf$", f.name)
            if m:
                targets.append((f"{m.group(1)}{m.group(2)}", f))
        if not targets:
            sys.exit(f"--offline, and no calendars in {cache}/ to read.")
        print(f"offline: {len(targets)} calendars from {cache}/, no requests")
    else:
        print(f"Listing {a.year} calendars...")
        try:
            urls = calendar_urls(a.year, delay=a.delay,
                                 rediscover=a.rediscover)
        except Exception as e:
            if type(e).__name__ != "Refused":
                raise
            print(f"\n  discovery stopped: {e}.\n"
                  "  The General Court is refusing connections, which says "
                  "nothing about\n  which calendars exist. Parsing the ones "
                  "already downloaded instead.")
            urls = {}
        print(f"  {len(urls)} editions found")
        if not urls:
            sys.exit("No calendar PDFs found. Check the year.")
        # Base editions are ints, supplements are strings like "5A", so they
        # cannot be compared directly. Sort on the numeric part, then the suffix.
        def order(k):
            m = re.match(r"(\d+)([A-Z]*)", str(k))
            return (int(m.group(1)), m.group(2))

        targets = []
        for num in sorted(urls, key=order):
            n, suf = order(num)
            local = cache / f"HC{n:03d}{suf}.pdf"
            if not local.exists():
                try:
                    req = urllib.request.Request(urls[num], headers=UA)
                    with urllib.request.urlopen(req, timeout=120) as r, open(local, "wb") as fh:
                        shutil.copyfileobj(r, fh)
                    print(f"  downloaded HC {num}")
                except Exception as e:
                    print(f"  ! HC {num}: {e}")
                    continue
            targets.append((num, local))
            if a.limit and len(targets) >= a.limit:
                break

        # A calendar already downloaded is a calendar, whether or not this run
        # could reach the General Court to be told about it again.
        have = {str(x[0]) for x in targets}
        for f in sorted(cache.glob("HC*.pdf")):
            m = re.match(r"HC0*(\d+)([A-Z]*)\.pdf$", f.name)
            if m and f"{m.group(1)}{m.group(2)}" not in have:
                targets.append((f"{m.group(1)}{m.group(2)}", f))
        if not urls and targets:
            print(f"  {len(targets)} calendars read from {cache}/")

    allrep, methods = defaultdict(list), set()
    seen, skipped, skipped_samples = defaultdict(set), [0], []
    for num, path in targets:
        text, how = extract_text(path)
        methods.add(how)
        got = parse_reports(text, f"House Calendar {num}, {a.year}" if num
                            else path.name, skipped, skipped_samples)
        for k, v in got.items():
            # Keep the first printing. A report that appears again in a later
            # calendar is the same report, and listing its source once is the
            # difference between a citation and a log.
            for r in v:
                sig = (r["majority_recommendation"], r["minority_recommendation"],
                       tuple(e.get("text", "")[:120] for e in r["reports"]))
                if sig in seen[k]:
                    continue
                seen[k].add(sig)
                allrep[k].append(r)
        print(f"  HC {num or path.name}: {len(got)} bills with reports")

    # ---- merge, do not replace -------------------------------------------
    #
    # A session is two years and the reports are printed in the calendars of
    # both, so a bill retained in 2025 and reported in 2026 has one in each.
    # Each run only ever sees one year, and writing the whole file meant the
    # second run replaced the first: 829 bills of 2025 became 1,084 of 2026,
    # and the collapse guard let it through because 1,084 is not a collapse.
    #
    # So: everything already on file is kept, except records that came from
    # THIS year's calendars, which the run has just rebuilt.
    out_path = Path(a.out)
    year_mark = re.compile(rf",\s*{a.year}\b")
    if out_path.exists():
        try:
            prior = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            prior = {}
        kept = 0
        for bid, recs in prior.items():
            older = [r for r in recs
                     if not year_mark.search(r.get("source") or "")]
            if older:
                allrep[bid] = older + [
                    r for r in allrep.get(bid, [])
                    if r.get("source") not in {x.get("source") for x in older}]
                kept += len(older)
            elif bid not in allrep:
                pass
        if kept:
            print(f"\n{kept:,} reports from other years kept; this run "
                  f"rebuilt {a.year}")

    if out_path.exists():
        try:
            had = len(json.loads(out_path.read_text(encoding="utf-8")))
        except Exception:
            had = 0
        if had and len(allrep) < had * 0.5:
            print(f"\nNOT WRITING {a.out}: this run found reports for "
                  f"{len(allrep):,} bills,\nagainst {had:,} already on file. "
                  "That is a fetch that failed, not a session\nthat lost its "
                  "committee reports. The existing file is untouched.\n"
                  "Re-run when the General Court is answering, or pass "
                  "--force-write.")
            if not a.force_write:
                return
    out_path.write_text(json.dumps(allrep, indent=2), encoding="utf-8")

    total = sum(len(v) for v in allrep.values())
    with_min = sum(1 for v in allrep.values() for r in v if r["minority_recommendation"])
    if skipped[0]:
        # Say what is true -- that they carried no signed report -- and not
        # why, which has not been checked.
        consent = [x for x in skipped_samples if CONSENT_HINT.search(x[1])]
        print(f"\n{skipped[0]:,} calendar sections named a bill and a "
              "recommendation but carried no\nsigned report, so they are not "
              "stored: a source line for a report that is\nnot there is worse "
              "than no source line.")
        if consent:
            print(f"\n  {len(consent)} of the sampled ones mention the consent "
                  "calendar. If a consent\n  entry prints its report without a "
                  '"Rep. X for the Committee" line to sign\n  it, these are '
                  "real reports being dropped rather than reprints.")
        print("\n  Three of them, so the shape can be judged rather than "
              "assumed:")
        for bill, sample in skipped_samples[:3]:
            print(f"    [{bill}] {sample[:150]}")
    ents = [e for v in allrep.values() for r in v for e in r.get("reports", [])]
    voted = [e for e in ents if "vote_yeas" in e]
    print(f"\n{len(voted):,} of {len(ents):,} report bodies ended with a vote "
          "the pattern recognised")
    if len(voted) < len(ents):
        print("The rest end some other way. These are the last 60 characters of "
              "three of\nthem -- if a vote is visible in there, send this and "
              "the pattern can be\nfixed without refetching a single calendar:")
        shown = 0
        for e in ents:
            if "vote_yeas" not in e and len(e.get("text", "")) > 60:
                print(f"    ...{e['text'][-60:]!r}")
                shown += 1
                if shown == 3:
                    break
    signed = sum(len(r["reports"]) for v in allrep.values() for r in v)
    print(f"\n{len(allrep):,} bills, {total:,} reports -> {a.out}")
    print(f"{with_min:,} had a minority report (a divided committee)")
    print(f"{signed:,} signed narrative blocks extracted")
    print(f"extraction method: {', '.join(methods)}")
    if "pypdf" in methods:
        print("\npypdf interleaves two-column pages. Install poppler for pdftotext,")
        print("or pip install pdfplumber, and rerun for materially better text.")


if __name__ == "__main__":
    main()
