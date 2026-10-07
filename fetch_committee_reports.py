#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.32
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

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import difflib
import json
import proceedings as P
import re
import refusal
import shutil
import subprocess
import time
import urllib.parse
import urllib.error
import urllib.request
import child
from collections import defaultdict

INDEX = "https://gc.nh.gov/house/calendars_journals/"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}

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
# A PAGE BREAK IS THE START OF A LINE. pdftotext writes one as a form feed,
# and where an entry begins at the top of a page the heading is preceded by
# that form feed rather than by a newline -- so this pattern, which allowed
# only spaces and tabs after the line break, did not see it, and the
# PREVIOUS committee's report swallowed the whole entry. House Calendar 70
# of 2011 reads
#
#     ...it, not the federal government. Vote 12-0.
#                                                    6
#     <form feed>HB 633, preventing prescribing practitioners from owning
#
# and HB 619's report on this site carried HB 633's number, title and
# recommendation on the end of it. 405 headings across 1,579 calendars are
# hidden this way, all but two of them in 2003-2012, which is why the oldest
# reports were the worst affected.
#
# THE LINE ANCHOR ITSELF STAYS, and the comment above says why. The price of
# admitting the form feed is one known false positive in 405: a meetings
# notice reading "work session on HB 111, ... and HB 1601, ..." where the
# page happens to break before the second bill. That one falls inside
# COMMITTEE MEETINGS, which SECTION_END has already terminated, so it
# reaches no report -- but it is the same shape as the SB 2 sentence above,
# so if a heading ever appears from nowhere, look here first.
#
# A HEADING THIS DID NOT KNOW WAS NO HEADING, and the report under it went to
# the bill above. The calendars print a hyphen after the kind now and then
# ("HB-604-FN," in House Calendar 32 of 2001, "SJR-2," in 51 of 1997), a
# doubled one before the suffix ("SB 131--FN," in 56 of 1997), and kinds this
# list left out: SJR, the House's addresses for removal from office ("HA 1,"
# in 43 of 2010), "HCO 1,", and the 2016 calendars' "HCACR 15," and "SCACR
# 5,", which are CACR 15 and CACR 5. So HB 218's page carried the Fish and
# Game fees HB 604's report argues for, SB 106's carried SB 131's Red Cross
# leave, SB 138's a Senate joint resolution's, SB 497's and HB 2010's the
# addresses to remove two marital masters and a judge, HB 1813's an address's
# reasoning and its vote of 17-0 for its own 22-0, and HB 1281's and HB
# 1350's the report on electing judges: 36 bills lost another item's report
# when the 1,580 calendars were re-read, and 24 gained their own. bill_key()
# puts the number back into the form the rest of the site uses.
BILL_START = re.compile(
    r"(?:\A|[\r\n\f])[ \t\f]*"
    r"(?P<bill>(?:HB|SB|CACR|HCACR|SCACR|HR|SR|HCR|SCR|HJR|SJR|HA|HCO)"
    r"[ \t]?-?[ \t]?\d+(?:--?[A-Z]+)*)\s*,\s*",
    re.I)

# An address or an order ends the report above it and is no bill. An
# address's committee recommends OUGHT NOT TO PASS, which RECS does not read,
# so a record made for one carried the minority's recommendation as the
# majority's. It is a boundary and nothing more.
BOUNDARY_ONLY = ("HA", "HCO")

# What the calendar prints, and the key the site files the bill under.
_KEY = re.compile(r"([A-Z]+)[\s-]*(\d+)")
_KIND = {"HCACR": "CACR", "SCACR": "CACR"}


def bill_key(bill):
    """'HB 660-FN-LOCAL' -> 'HB660', 'HB-604-FN' -> 'HB604', 'HCACR 15' ->
    'CACR15': the kind and the number as printed, and nothing else."""
    m = _KEY.match(re.sub(r"\s+", " ", bill.upper()).strip())
    if not m:
        return re.sub(r"\s+", "", bill.upper()).split("-")[0]
    return f"{_KIND.get(m.group(1), m.group(1))}{m.group(2)}"


# THE HEADING THE PRINTOUT CUT IN TWO. The 1998 calendars are a browser's
# printout, and four times the page broke inside a heading: the title stayed
# at the foot of one page with a gap where the number was, and the number went
# to the top of the next with nothing after it --
#
#                          , appropriating startup funds for the Governors ...
#     file:///C/Users/.../houcal7.htm[11/8/2021 1:47:35 PM]
#     <form feed>House Calendar 7
#        HB 1211-FN-A
#        WITH AMENDMENT
#
# -- so no heading was read, and HB 1211's report went to HB 1206, HB 1234's
# to HB 1233, HB 1156's to HB 1597 and HB 1241's to HB 1040. The number is put
# back in front of its title. Only across the printout's own page footer, and
# only a number standing alone on its line.
SPLIT_HEADING = re.compile(
    r"^[ \t]{6,}(?P<title>,[ \t]+[^\n]*)\n"
    r"(?P<gap>(?:[^\n]*\n){0,3}?[^\n]*file:///[^\n]*\n(?:[^\n]*\n){0,3}?)"
    r"[ \t\f]*(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR|SJR)[ \t]?\d+(?:-[A-Z]+)*)[ \t]*\n",
    re.M)


def rejoin_split_headings(text):
    return SPLIT_HEADING.sub(
        lambda m: f"   {m.group('bill')}{m.group('title')}\n{m.group('gap')}", text)


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
_DATE = rf"\d{{1,2}}\s*(?:{_MON})\s*\d{{4}}"
# THE HEADER ARRIVES JAMMED TOGETHER. pdftotext -layout emits the House's
# running header as "19 DECEMBER2025HOUSERECORD": a space after the day and
# none at all between the month, the year and the two words of the record's
# name. Every gap here wanted \s+, so 542 headers survived into the text and
# landed mid-sentence inside members' own reasoning -- "What matters is
# legislative approval -- such 44 19 DECEMBER2025HOUSERECORD as an
# authorization for the use of military force".
#
# Every separator is optional now. The day still needs its digits and the year
# still needs four of them, and every branch but the last requires the words
# HOUSE RECORD, which do not follow a date in a member's sentence.
#
# 2013-2016 PRINT THE MONTH IN LOWER CASE AND NUMBER PAGES PAST 999: "13
# december 2013 HOUSE RECORD 1920", "1927 13 december 2013 HOUSE RECORD",
# "6 3 january 2014 HOUSE RECORD". None of it matched, and 254 of the 3,270
# reports those four years print carried a header mid-sentence. The lower-case
# month is accepted only where HOUSE RECORD is part of the match; the last
# branch, which has no such anchor, keeps to capitals and three digits, so a
# date in a member's own sentence is never read as a header.
_DATE_ANY = rf"\d{{1,2}}\s*(?i:{_MON})\s*\d{{4}}"
PAGE_FURNITURE = re.compile(
    r"\s*(?:"
    rf"\d{{1,4}}\s*HOUSE\s*RECORD\s*{_DATE_ANY}"
    rf"|HOUSE\s*RECORD\s*\d{{1,4}}\s*{_DATE_ANY}"
    rf"|\d{{1,4}}\s*{_DATE_ANY}\s*HOUSE\s*RECORD(?:\s*\d{{1,4}}\b)?"
    rf"|{_DATE_ANY}\s*\d{{1,4}}\s*HOUSE\s*RECORD"
    rf"|{_DATE_ANY}\s*HOUSE\s*RECORD(?:\s*\d{{1,4}}\b)?"
    rf"|HOUSE\s*RECORD\s*{_DATE_ANY}"
    rf"|\d{{1,3}}\s*{_DATE}(?:\s*HOUSE\s*RECORD)?"
    r")\s*")

# The header carries the calendar's date from about 2005 -- "House Calendar
# No. 22 - March 17, 2006" -- and landed mid-sentence in 158 reports of
# 2005-2008 until the pattern allowed it. Still only after a form feed.
PRINTOUT = re.compile(
    r"^[^\n]*file:///[^\n]*$"
    r"|^\x0c[ \t]*House\s+Calendar(?:\s+No\.?)?\s*\d*[A-Za-z]?"
    r"(?:\s*[-–]\s*[A-Z][a-z]+\s+\d{1,2},\s*\d{4})?[ \t]*$", re.M)

# Enough to notice a consent-calendar section, not enough to classify one.
CONSENT_HINT = re.compile(r"consent calendar", re.I)

RECS = (r"OUGHT TO PASS WITH AMENDMENT|OUGHT TO PASS W/ ?AMENDMENT|OUGHT TO PASS|"
        r"INEXPEDIENT TO LEGISLATE|INTERIM STUDY|REFER FOR INTERIM STUDY|"
        r"RETAIN(?:ED)?(?: IN COMMITTEE)?|WITHOUT RECOMMENDATION|"
        r"RE-?REFER TO COMMITTEE")

MAJ_MIN = re.compile(rf"MAJORITY\s*:\s*(?P<maj>{RECS})\s*\.?\s*"
                     rf"(?:MINORITY\s*:\s*(?P<min>{RECS})\s*\.?)?", re.I)
# The recommendation ends in a full stop -- or, in the calendars of the
# 2000s, stands on its own line with none, straight before the member who
# signs: "INEXPEDIENT TO LEGISLATE / Rep. Eric G. Stohl for ...".
SOLO_REC = re.compile(rf"(?<![:\w])(?P<rec>{RECS})\s*(?:\.|(?=\s*(?:Rep|Sen)\.\s))",
                      re.I)

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

# A surname can carry a lower-case particle, and a letter the PDF's font
# cannot name: "Rep. Matt Sabourin dit Choini�re" signs two 2026 reports,
# the e-grave arriving from pdftotext as U+FFFD. A name made only of
# capitalised word characters stopped at "dit", and at the U+FFFD, and a
# re-read of the calendars lost both reports.
# ...and the member's line ends in a full stop from 2015, a COLON before it:
# "Rep. Debra L DeSimone for Children and Family Law: The committee
# believes...". Wanting the full stop, the parser read not one report out of
# a calendar of 1997-2014.
AUTHOR = re.compile(
    r"(?P<who>(?:Rep|Sen)\.\s+[A-Z][\w'’.\-�]*"
    r"(?:\s+(?:(?:dit|de|du|da|di|van|von|der|des|la|le)\s+)?[A-Z][\w'’.\-�]*){0,3})\s+for\s+"
    r"(?:the\s+(?P<side>Majority|Minority)\s+of\s+)?"
    r"(?P<committee>[A-Z][A-Za-z,&\-\s]{2,60}?)\s*[.:]\s+",
    re.I)


def clean_pdf_text(t):
    """PDF extraction artefacts: soft hyphens, hyphenated line breaks, column dots.

    Order matters. Words broken across lines are marked with a soft hyphen, so
    the rejoin has to happen BEFORE soft hyphens are stripped, or "ef<shy>fect"
    silently becomes "ef fect".
    """
    # The 1997-2000 calendars are browser printouts: every page break is the
    # browser's "file:///C/Users/..." footer, a form feed, and a "House
    # Calendar No. 7" header. Gone before the lines are joined, or they land
    # mid-sentence in a member's reasoning. The header only after a form
    # feed, so a sentence citing a calendar is left alone.
    t = PRINTOUT.sub("", t)
    t = re.sub(r"(\w)[\u00ad\-\u2010\u2011]\s*\n\s*(\w)", r"\1\2", t)  # rejoin first
    t = t.replace("\u00ad", "")
    t = re.sub(r"[·•]\s*", " ", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    t = PAGE_FURNITURE.sub(" ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def extract_text(pdf):
    if shutil.which("pdftotext"):
        out = child.run(["pdftotext", "-layout", str(pdf), "-"],
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


# THE CALENDAR'S OWN TERM (27 September 2026). The General Court's list for
# 1999 carries three calendars of 1998 as well -- "1a", "2a" and "4a", whose
# mastheads read "Vol. 20 Concord N.H. Wednesday, January 7, 1998 No. 1" and
# so on -- and read as 1999's, their 155 reports sat on the 1999-2000 bills
# that share their numbers: 2000's HB 555, on a child's representation,
# carried 1998's report on exempting pensions. The 1998 list has its own copy
# of each. The masthead's volume is the calendar's year -- Vol. 20 is 1998,
# Vol. 47 is 2025 -- and a December calendar is already the next year's
# volume, so the term is compared and not the year. Of the 1,579 calendars on
# disk, 1,496 print a masthead of this form, 1,493 of them naming a volume of
# their own list's term; the 83 that print none are read as before.
MASTHEAD = re.compile(r"\bVol\.?\s*(\d{1,3})\s+Concord\b", re.I)


def masthead_year(text):
    """The year a calendar's masthead volume names, or None: Vol. 20 is 1998."""
    m = MASTHEAD.search((text or "")[:6000])
    return 1978 + int(m.group(1)) if m else None


def printed_for_another_term(text, year):
    """The masthead's year where it names a volume of a term other than
    `year`'s, else None: such a calendar's reports are not this year's."""
    own = masthead_year(text)
    return own if own and P.term_of(str(own)) != P.term_of(str(year)) else None


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


# A committee's vote, anywhere in a section -- VOTE_TAIL without the anchoring
# to the end of a report body.
VOTE_ANY = re.compile(r"\bVote[:\s]\s*\d{1,3}\s*[-–]\s*\d{1,3}", re.I)


def _section(text, pos, end):
    """One section's text as parse_reports reads it: cleaned, and cut where
    the calendar turns to another kind of business."""
    chunk = clean_pdf_text(text[pos:end])
    cut = SECTION_END.search(chunk, 60)
    return chunk[:cut.start()] if cut else chunk


def continues(prev, chunk):
    """True where `chunk`, opened by a bill number at the start of a line, is
    the report above it still going rather than a heading.

    BILL_START only asks for a bill number and a comma at the start of a line,
    and a sentence that wraps can put one there. House Calendar 20 of 2024
    prints SB 453's majority report as

        ... The problem is that the companion bill that implements these policies,
        HB 463, may not be passed, and therefore we would have allocated $450,000
        ... so that they can rise or fall together. Vote 13-12. Rep. Karen Ebel
        for the Minority of Finance. This bill would make a $450,000 ...

    and "HB 463," was read as a heading. SB 453's majority report lost its
    last two sentences and its vote, its minority report was lost altogether,
    and HB 463's page gained a report the House never made on it: "OUGHT TO
    PASS", by Rep. Ebel, reasoning about SB 453.

    A heading's first report cannot be preceded by a committee vote -- the vote
    is how a report ENDS -- and the other side of a divided committee signs for
    the same committee as the side above it. So a section that reaches a vote
    before its first signature, with no recommendation before that vote, and
    whose first signer is for the same committee as the last signer above it,
    is that report continuing. Across the 1,580 calendars on disk this is 7
    places: four inside another bill's report (HB 176 in HB 306 of 2003,
    "HB 2004" in HB 304 of 2005, HB 1262 in HB 407 of 2021, HB 463 in SB 453
    of 2024) and three inside the same bill's (HB 1594 of 2014, twice, and
    HCR 9 of 2024), each of which had lost the rest of its report. The
    committee test is what keeps out the grievance reports printed after a
    conference report in 2012, which also reach a vote before a signature.
    """
    first = AUTHOR.search(chunk)
    if not first:
        return False
    vote = VOTE_ANY.search(chunk, 0, first.start())
    if not vote:
        return False
    rec = MAJ_MIN.search(chunk) or SOLO_REC.search(chunk)
    if rec and rec.start() < vote.start():
        return False
    signed = list(AUTHOR.finditer(prev))
    if not signed:
        return False

    # Near enough rather than equal: House Calendar 9 of 2014 signs HB 1594's
    # majority "for the Majority of Executive Departments and Adminstration"
    # and its minority with the word spelled right.
    def committee(m):
        return " ".join(m.group("committee").split()).lower()
    return difflib.SequenceMatcher(
        None, committee(signed[-1]), committee(first)).ratio() >= 0.9


def parse_reports(text, source, skipped=None, skipped_samples=None):
    """Split into bill sections, then read the recommendations and signed prose."""
    skipped = skipped if skipped is not None else [0]
    skipped_samples = skipped_samples if skipped_samples is not None else []
    text = rejoin_split_headings(text)
    # start("bill"), not start() -- the pattern matches the line break before
    # the number too, and slicing from the wrong offset eats a digit off it.
    found = [(m.start("bill"), m.group("bill")) for m in BILL_START.finditer(text)]
    # A number that only continues the report above it is not a heading, and
    # the report above it runs on through it. continues() says why.
    marks = []
    for i, (pos, bill) in enumerate(found):
        if marks:
            end = found[i + 1][0] if i + 1 < len(found) else len(text)
            if continues(_section(text, marks[-1][0], pos),
                         _section(text, pos, end)):
                continue
        marks.append((pos, bill))
    reports = defaultdict(list)

    for i, (pos, bill) in enumerate(marks):
        if bill_key(bill).rstrip("0123456789") in BOUNDARY_ONLY:
            continue
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
                # THE SENTENCE KEEPS ITS OWN FULL STOP. This was
                # .strip(" .;,"), which took the period off both ends -- and
                # the period at the END belongs to the report's last
                # sentence, not to the vote line being cut off. 25,499 of
                # 30,588 report texts ended without one, which reads on the
                # page exactly like a text that was truncated, and is what
                # the bench kept reporting as "missing a period and looks
                # like it got cut off". Nothing was cut off: the calendar
                # says "...our NH National Guard.Vote 11-6." and the period
                # is the sentence's.
                #
                # A semicolon or comma before the vote is the clerk's
                # punctuation joining two clauses and is still dropped. Where
                # the cut lands on one of those the text simply has no
                # terminal period, because the source gave it none, and
                # inventing one would be writing punctuation into a quotation.
                body = body[:v.start()].lstrip(" .;,").rstrip()
                body = body.rstrip(";,").rstrip()
            entry["text"] = body
            entries.append(entry)

        key = bill_key(bill)
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
    # Only the fetching mode asks the General Court. --offline, and --pdf with
    # a file on this disk, read what is here, so a refusal on file or GitHub's
    # night has nothing to stop in them -- and they were stopped all the same
    # until 27 September, when the offline re-read of every calendar met it.
    if not (a.offline or (a.pdf and Path(a.pdf).exists())):
        refusal.check("The committee reports fetch")

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
        own = printed_for_another_term(text, a.year)
        if own:
            print(f"  HC {num or path.name}: left out -- its masthead is volume "
                  f"{own - 1978}, {own}'s, so its reports are {P.term_of(str(own))}'s")
            continue
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
    # The file is {term: {bill: [reports]}}. A calendar year identifies the
    # year; the TERM is what a bill number is unique within, and both years of
    # a biennium print reports on the same bills.
    term = P.term_of(str(a.year))
    out_path = Path(a.out)
    year_mark = re.compile(r",\s*" + str(a.year) + r"\b")
    prior = {}
    if out_path.exists():
        try:
            prior = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            prior = {}
        if prior and not all(re.match(r"^\d{4}-\d{4}$", k) for k in prior):
            sys.exit(f"{a.out} is keyed on bill number, not on term. Delete it "
                     "and re-run this once for each year of the term.")
        mine = prior.get(term, {})
        kept = 0
        for bid, recs in mine.items():
            older = [r for r in recs
                     if not year_mark.search(r.get("source") or "")]
            if older:
                allrep[bid] = older + [
                    r for r in allrep.get(bid, [])
                    if r.get("source") not in {x.get("source") for x in older}]
                kept += len(older)
        if kept:
            print(f"\n{kept:,} reports from the other year of {term} kept; "
                  f"this run rebuilt {a.year}")

        had = len(mine)
        if had and len(allrep) < had * 0.5:
            print(f"\nNOT WRITING {a.out}: this run found reports for "
                  f"{len(allrep):,} bills,\nagainst {had:,} on file for {term}. "
                  "That is a fetch that failed, not a session\nthat lost its "
                  "committee reports. The existing file is untouched.\n"
                  "Re-run when the General Court is answering, or pass "
                  "--force-write.")
            if not a.force_write:
                return

    # Other terms are left exactly as they are. This run saw one year of one
    # term and has nothing to say about any other.
    prior[term] = allrep
    out_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
    others = sorted(k for k in prior if k != term)
    print(f"\n{term}: {len(allrep):,} bills"
          + (f"; other terms on file: {', '.join(others)}" if others else ""))

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
