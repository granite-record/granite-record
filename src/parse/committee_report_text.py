#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
A House calendar's text, read and cleaned, and what a committee report's
end says: the vote, and the member who signs.

    import committee_report_text as CRT
    text, how = CRT.extract_text(pdf)        # pdftotext -layout, else pdfplumber, else pypdf
    CRT.clean_pdf_text(text)                 # soft hyphens, broken lines and page furniture gone
    CRT.VOTE_TAIL.search(body)               # "Vote 12-8." and the calendar it was placed on
    CRT.AUTHOR.search(body)                  # "Rep. ... for the Majority of ..."

No network: it reads calendars already on disk. It was part of
fetch_committee_reports.py until 19 November 2026, and extract_amendments and
interim_statements -- parsers -- imported the fetcher for it
(reports/refactor/stage0-code.md, section 2). Moved as it stood;
fetch_committee_reports names every piece as before
(fetch_committee_reports.extract_text, .PAGE_FURNITURE, ...).
"""

import re
import shutil
import sys

import child



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
