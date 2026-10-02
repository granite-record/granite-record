#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-01.3
"""
The day's seven changing files, rebuilt from the database's views. No network.

    python3 dayfiles_from_db.py --check          # the one pair on this disk: the dump of
                                                 # 8 September against the export of the 6th
    python3 dayfiles_from_db.py                  # .night/dbday/ against the files installed
                                                 # here: what would change, and every guard
    python3 dayfiles_from_db.py --out DIR        # ... and write the seven there, all or none

WHY THIS EXISTS

On 27 and 28 September and on 1 October 2026 the General Court's bulk-file
export failed on their side: its own page printed "Error Generating ... File :
Execution Timeout Expired", thirteen of the fourteen files came back empty on
every try, and nothing was built those days. The same record is in the SQL
host the General Court publishes credentials for, and the person approved the
night asking it, gently, when the export fails. fetch_day_db.py asks; this
turns what came back into the files the build reads, and asks nobody anything.

Seven of the fourteen files change, and all seven come from six views:

    Docket.txt            Docket
    LSRs.txt              Legislation
    LsrSponsors.txt       Sponsors
    LsrsOnly.txt          Sponsors, with Legislation and Legislators
    legislators.txt       Legislators
    RollCallSummary.txt   RollCallSummary
    RollCallHistory.txt   RollCallHistory, with Legislators for the PersonID

The other seven are not rebuilt. Six are lookups that have not changed since
the archive began (one hash each since 6 September) and stay as the last good
export left them; lookup_notes() says where the database disagrees with one.
Members.txt is not part of the failing export and has arrived every time.

WHAT WAS MEASURED, AND ON WHAT

db/*.psv is the dump of 8 September and nh-archive/ holds the export of the
6th, which for these files was still the copy in force on the 8th: the only
pair on this disk where both sources show one state. --check rebuilds the
seven from the one and compares them with the other:

    Docket.txt            25,279 of 25,279 rows identical in columns 1 to 6.
                          Column 7, when a row was last changed, is not in the
                          view; no reader uses it, and the rebuilt file repeats
                          column 3 there
    LSRs.txt              38 of 39 columns identical on all 1,387 rows. Column
                          25, the Senate status code, differs on 29 bills in
                          every export since, so it is a standing difference;
                          build_data.py does not read it
    LsrSponsors.txt       byte-identical
    LsrsOnly.txt          6,950 of 6,963 rows. The 13 are two requests with no
                          bill number, which Legislation does not carry and
                          build_data.py skips; and the export breaks one title
                          over two lines where the view has it on one
    legislators.txt       byte-identical
    RollCallSummary.txt   byte-identical
    RollCallHistory.txt   byte-identical

It was a quiet week: the newest docket row in both is 4 September. What a
session day shows is not known, and the guards below are set loose for it.

ROW ORDER IS THE INSTALLED FILE'S

The export's order of the docket, the two sponsor files and the roster is no
order the views can give, and build_data.py adds docket-only bills and
sponsors in file order: with the views' own order its bills.json and
sponsors.json came out equal as data and in another order, which would change
the site's fingerprint on a day nothing changed. So a rebuilt file keeps the
installed file's order for every row the two share, and puts new rows after
them (the docket's in the view's statusorder). The content of every line is
the database's; only the order is borrowed. That is also how the export
itself grows: across the archive's eight versions of Docket.txt the rows two
versions share never change order, and new rows arrive at the end. The roll
calls need none of it: sorted by chamber, number and member they are the
export's bytes.

A docket row the clerk EDITS stays where it was. One has been, in those eight
versions: between 6 and 15 September HB 1218's amendment number was corrected
from 2026-0596h to 2026-0956h, and the row kept its place, 18,982nd of
25,313. Told apart only on the six columns both sources carry it is a row
gone and a new row, and it went to the end. So a docket row with no place by
those six takes the place of the installed row, taken by no other, with its
year, request, entry time, bill and chamber (ORDER_LOOSE): the same event,
reworded. The differences still count it as one row gone and one new.

THE GUARDS, judge(), before anything is installed

Tonight's files against the installed ones. A guard that fires stops the
night's fallback and nothing is installed.

They were first about rows and keys going missing. On 2 October 2026, after
the one supervised test, two checkers doctored copies of its files and asked
the guards: a wrong committee and title on a third of the bills, 5,000
invented docket rows, 250 reworded ones, a docket row dated a year back,
every Yea and Nay swapped, every roll call filed under HB 1 and every
member's party swapped each passed all of them. That night's files were
right because they had been compared by hand, not because a guard would have
said so. So the files are held to what the installed ones SAY as well, on
the columns the build reads:

    the view is not behind     its newest docket entry is not older than the
                               installed file's
    the docket's new rows      each under a bill the installed docket or
                               LSRs.txt knows, or tonight's LSRs.txt brings;
                               each with an entry time that reads as one, not
                               more than DOCKET_STAMP_SLACK before the
                               installed file's newest; and no more than
                               DOCKET_NEW_A_DAY_MOST entered on any one day
    the docket's old rows      no bill missing; at most DOCKET_GONE_MOST gone,
                               DOCKET_CITED_MOST with a journal citation
                               written onto them, DOCKET_REWORDED_MOST
                               reworded any other way
    bill records               every (year, LSR) installed is there tonight;
                               at most LSR_REWRITTEN_MOST with a value the
                               build reads replaced or lost, LSR_CHANGED_MOST
                               changed in such a column at all, and
                               LSR_NEW_MOST new
    roll calls                 every one installed is there with the same four
                               counts, and none has fewer ballots; at most
                               ROLLCALLS_CHANGED_MOST read otherwise -- the
                               time, the bill, the question, the title -- and
                               BALLOTS_CHANGED_MOST ballots are cast otherwise
    the roster                 within ROSTER_TOLERANCE of the installed count,
                               and at most that share of the installed
                               members gone from it; at most
                               ROSTER_CHANGED_MOST with another name, chamber,
                               county, district or party, ROSTER_TOUCHED_MOST
                               changed in anything the build reads
    sponsors                   LsrSponsors.txt keeps SPONSORS_KEPT_LEAST of its
                               rows. LsrsOnly.txt, which lists sitting members
                               only, keeps every row of a member still on
                               tonight's roster that names a bill, and that
                               share of their rows that name none
    the shape                  every line has its file's number of columns

A column no reader reads -- the docket's seventh, LSRs.txt's two status
codes -- is counted, said (held_said) and never judged.

Each threshold is a constant below, with the measurement it came from: the
real exports of September, night against night (eleven pairs, and no session
day among them), and for a session day the stamps the term's own files carry
-- rows entered and rows changed per day across the term, roll calls per day
across 27 years. The docket's new rows are counted by the day each was
entered, so nights with nothing installed between them do not add up to a
stop. The other ceilings are per night, and do.

LsrsOnly.txt was first held to 98% of ALL its rows. But a member who leaves
takes every row of theirs out of it, in the export as here, and three
members each hold more than 2% of it (155, 153 and 144 of 6,963 on
30 September): one resignation would have stopped the fallback for as long as
the export stayed down. Who has left is the roster guard's question, and it
asks it by person rather than by count alone. Then it was held to 98% of the
rows of the members still sitting, which let the sponsors of ten bills go:
the 13 rows the view cannot give all lack a bill number, so that is what the
allowance is now for.

WHAT A RIGHT NIGHT CAN STILL BE STOPPED BY

Every guard fails closed, and some real days are on the wrong side of one:

    a roll call's tally corrected       the four counts are held to nothing
                                        changing, so one corrected tally stops
                                        every database night until the export
                                        is back
    a docket row moved                  to another bill, or given another entry
                                        time: it is a row gone and a new row
                                        with an old entry time
    a sponsor off a numbered bill       or changed from Sponsor to Prime: the
                                        installed row is not there tonight.
                                        No sponsor has been withdrawn in any
                                        data on this disk
    more in a night than a day has      over 1,000 citations (two of the
                                        term's days running came to 732), 100
                                        rows marked cancelled or reworded (the
                                        most in a day is 51), 170 bill records
                                        rewritten (the most bills amended in a
                                        day is 83); or several nights' worth,
                                        when nothing was installed in between

What the night says then: nothing is installed and yesterday's files stay;
the verdict's day_files has source "none", why_code "guard" and "stops", one
sentence a guard, each naming the file, the count and a row; the run's page,
which is public, says only that what came back did not pass the night's
checks. Tonight's files are compared with the installed ones, and those have
not moved, so the same guard fires every night until the export returns.
There is no switch that installs a night a person has read and found right.

THE SESSION YEAR IS THE INSTALLED FILES'. The export decides what a "current"
file holds; this copies the last good day's years rather than guessing a new
term's. fetch_day_db.py asks for those years and later, so a newer year in
the views is seen, left out, and said (a warning, not a stop).
"""

import argparse
import collections
import contextlib
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import rollcalls_from_db as RC

# Where fetch_day_db.py leaves the views, and nothing else writes.
VIEWS_DIR = Path(".night") / "dbday"
SOURCE = "source.json"

DAY_FILES = ("Docket.txt", "LSRs.txt", "LsrSponsors.txt", "LsrsOnly.txt",
             "legislators.txt", "RollCallSummary.txt", "RollCallHistory.txt")
WIDTH = {"Docket.txt": 7, "LSRs.txt": 39, "LsrSponsors.txt": 5, "LsrsOnly.txt": 8,
         "legislators.txt": 15, "RollCallSummary.txt": 15, "RollCallHistory.txt": 8}

# The six views, each with its columns in the order of the dump
# (db/_columns.json), which is the order fetch_day_db.py selects them in: a
# position here is a position in db/<view>.psv and in .night/dbday/<view>.psv
# alike, so the check against the dump reads the same columns a night does.
# Named one by one so that a renamed column fails the query, loudly.
VIEWS = {
    "Legislators": ["PersonID", "LastName", "FirstName", "Employeeno", "MiddleName",
                    "LegislativeBody", "Active", "seatno", "countycode", "District", "party",
                    "Expr1", "Address", "address2", "city", "Zipcode", "Expr2", "EMailAddress",
                    "GenderCode", "SecretaryID", "database"],
    "RollCallSummary": ["SessionYear", "LegislativeBody", "VoteSequenceNumber", "VoteDate",
                        "CondensedBillNo", "Yeas", "Nays", "Present", "Absent",
                        "AbbreviatedTitle1", "AbbreviatedTitle2", "Question_Motion", "Title1",
                        "Title2", "UserName", "DateModified", "Verified", "CalendarItemID"],
    "Sponsors": ["SessionYear", "lsr", "LSRSequenceNo", "employeeNo", "PrimeSponsor",
                 "SignedOff", "UserName", "DateModified", "SponsorWithdrawn", "LegislationID",
                 "PersonID"],
    "Legislation": ["legislationnbr", "documenttypecode", "sessionyear", "lsr", "LSRTitle",
                    "DateLSREntered", "LegislativeBody", "BillType", "AppropriationCode",
                    "FiscalImpactCode", "LocalCode", "FullLSR", "SubjectCode", "ExpandedBillNo",
                    "CondensedBillNo", "DateLSRBill", "ChapterNo", "SessionType",
                    "HouseCommitteeReferralCode", "HouseCurrentCommitteeCode",
                    "HouseDateIntroduced", "HouseStatusCode", "HouseStatusDate", "houseduedate",
                    "housefloordate", "houseamended", "SenateCommitteeReferralCode",
                    "SenateCurrentCommitteeCode", "SenateDateIntroduced", "SenateStatusCode",
                    "SenateStatusDate", "SenateDueDate ", "SenateFloorDate", "SenateAmended",
                    "GeneralStatusCode", "GeneralStatusDate", "EffectiveDate",
                    "AdditionalEffectiveDates", "Rereferred", "username", "DateModified",
                    "CurrentLSRStatus", "LatestCommitteeHearingCode",
                    "LatestCommitteeHearingDate", "LatestCommitteeHearingPlace", "Retained",
                    "Database", "legislationID"],
    "Docket": ["SessionYear", "LSR", "ExpandedBillNo", "StatusDate", "CondensedBillNo",
               "LegislativeBody", "Description", "DataBase", "legislationid", "OrderDate",
               "statusorder"],
    "RollCallHistory": ["EmployeeNumber", "SessionYear", "LegislativeBody",
                        "VoteSequenceNumber", "CondensedBillNo", "Vote", "UserName",
                        "DateModified", "CalendarItemID"],
}
# The column a view is filtered on: its session year. The roster has none.
YEAR_COLUMN = {"Docket": "SessionYear", "Legislation": "sessionyear",
               "Sponsors": "SessionYear", "RollCallSummary": "SessionYear",
               "RollCallHistory": "SessionYear"}

# The five lookups the database reproduces, for the comparison only: nothing
# here rebuilds a lookup. (HouseDistricts.txt is a different district plan in
# the database and is read by nothing in the night's build.)
LOOKUPS = {
    "Subject": ["SubjectID", "SessionID", "ChamberCode", "Subject", "ParentID",
                "SubjectTypeID", "SubjectCode", "Active", "DateTimeStamp"],
    "GeneralStatusCodes": ["GeneralCode", "GeneralDescription", "GeneralStatusActiveCode"],
    "BodyStatusCodes": ["LocationID", "BodyStatusCode", "Location", "StatusDescription",
                        "ActiveStatus", "LegislativeGroupCode"],
    "County": ["CountyID", "County", "DateTimeStamp", "CountyAbbr"],
    "Committees": ["CommitteeCode", "LongName", "committeename", "committeeabbreviation",
                   "committeelocation", "CommitteePhone", "oldCommitteeSecretary",
                   "ActiveCommittee", "CommitteeResearcher", "CommitteeSecretary",
                   "CommitteeAideEmailAddress", "CommitteeEmailAddress", "CommitteeID",
                   "Database"],
}
LOOKUP_FILE = {"Subject": "SubjectCodes.txt", "GeneralStatusCodes": "GeneralCodes.txt",
               "BodyStatusCodes": "BodyStatusCodes.txt", "County": "Counties.txt",
               "Committees": "Committees.txt"}

# LSRs.txt's 39 columns, each a position in the Legislation view or the text
# the export writes there on every row (the view's houseamended,
# SenateAmended, EffectiveDate, Rereferred and Retained hold values; the
# export writes 0 or nothing).
LSR_MAP = [2, 3, 4, 6, 7, 8, 9, 10, 11, 13, 14, 16, 12, 18, 19, 20, 21, 22, 23, 24, "0",
           26, 27, 28, 29, 30, 31, 32, "0", 34, 42, 43, 44, "", "", "", "0", "0", ""]
LSR_DATES = {20, 23, 24, 28, 32, 43}        # written the export's way, by clock()
LSR_CHAPTER = 16                            # padded to four digits; blank stays blank
# The one column of LSRs.txt the two sources are known to disagree on, from 0:
# the Senate status code. Compared without it.
LSR_SENATE_STATUS = 24

BIT = {"True": "1", "False": "0"}
BOM = "﻿"
EOL = "\r\n"

# ---- what the guards hold the files to ----------------------------------------
#
# Measured on 2 October 2026 on the real exports in nh-archive/: the twelve
# nights of September that arrived whole (eleven night-to-night pairs; the
# docket's thirteen nights, twelve pairs). September has no session day, so
# what one does is read from the stamps the term's own files carry -- when
# each docket row was entered and last changed, when each roll call was taken
# -- and the busiest real day is each ceiling's basis, doubled. Where there is
# nothing behind a number but that quiet month, its comment says GUESS.

# The columns of each file that a reader of the build reads, from 0: a guard
# judges these and reports the rest. LSRs.txt's are build_data.py's thirteen;
# the docket's seventh, the roll calls' stamps and the roster's mail label are
# read by nothing.
LSR_READ = (0, 1, 2, 3, 5, 6, 7, 10, 12, 13, 21, 31, 32)
LSR_HEARING = (31, 32)                  # the latest hearing: its day, its room
ROSTER_WHO = (1, 2, 3, 4, 6, 7, 8)      # last, first, middle, chamber, county, district, party
ROSTER_READ = ROSTER_WHO + (5, 10, 11, 12, 13, 14)      # ... seat, address, e-mail
ROLLCALL_TOLD = (3, 4, 11, 12)          # when, the bill, the question, the title
BALLOT_CAST = (4, 6)                    # the member's PersonID, the vote
# What LSRs.txt's columns are, for a sentence that names one.
LSR_NAMES = {2: "title", 3: "chamber", 5: "appropriation flag", 6: "fiscal flag",
             7: "local flag", 10: "bill number", 12: "subject code",
             13: "House committee of referral", 14: "House current committee",
             16: "House status code", 17: "House status date",
             21: "Senate committee of referral", 22: "Senate current committee",
             24: "Senate status code", 25: "Senate status date", 29: "general status code",
             30: "hearing committee", 31: "hearing date", 32: "hearing room"}

# Docket.txt. New rows entered on any one day: the busiest day of the term
# had 498 (6 March 2025; September's most is 34), and two days running 706.
DOCKET_NEW_A_DAY_MOST = 1000
# How far before the installed file's newest entry a new row's entry time may
# be. No new row on the twelve pairs was before it at all; but an entry time
# is not always when the row was written -- a conference committee meeting is
# stamped midnight of the meeting's own day, up to 6 days 12 hours ahead (193
# rows) -- so the newest entry installed can be a week in the future, and a
# row written the next morning "older" than it by that much. Twice that.
DOCKET_STAMP_SLACK = timedelta(days=14)
# Installed rows whose words gain a journal or calendar citation ("HJ 3  P.
# 7", "SJ 1"): the journal's page, written onto a row weeks after its day.
# 10,533 of the 11,293 rows changed on a later day than they were entered end
# in one; the most in a day is 492 (18 February 2025), two days running 732.
DOCKET_CITED_MOST = 1000
# Installed rows reworded any other way -- a meeting marked ==CANCELLED==, an
# amendment's number corrected: 760 rows in the term, the most in a day 51
# (23 January 2026), and 1 in September (HB 1218).
DOCKET_REWORDED_MOST = 100
# Installed rows gone and not reworded. None went on any pair, and a
# cancelled meeting is marked, not removed (786 rows carry a mark). It was
# 1% of the file, 253 rows, which let a view 200 rows short through. A GUESS
# above nothing: a deleted row leaves no stamp to count.
DOCKET_GONE_MOST = 25

# LSRs.txt. No bill record changed in a read column on any pair, so these are
# a session day's, from the docket. New records: the most requests made bills
# in one day is 202 (25 November 2025, Legislation.DateLSRBill).
LSR_NEW_MOST = 400
# Installed records where a read column that held a value holds another, or
# none (a hearing moved to another day aside): a new title, a flag, a
# committee corrected. Titles change when an amendment is adopted, and the
# most bills with one adopted in a day is 83 (11 March 2026).
LSR_REWRITTEN_MOST = 170
# Installed records with any read column changed, a first referral or a
# hearing scheduled included: the most records with a docket row entered in
# one day is 346 (5 February 2026).
LSR_CHANGED_MOST = 700

# The roll calls. One installed roll call changed on the eleven pairs (the
# Senate's 49th of 2026, moved from SB 655 to SB 665, with its title), and no
# ballot in a column the build reads. The other correction on record, SB 331
# of 2018, is one tally and one senator's ballot. GUESSES above those: a
# handful, never the file. The four counts are held apart, to nothing.
ROLLCALLS_CHANGED_MOST = 5
BALLOTS_CHANGED_MOST = 10

# The roster. Nobody's row changed on the eleven pairs, nor in the database's
# own view between 8 September and 2 October. GUESSES: who a member is --
# name, chamber, county, district, party -- on as many as the roster's count
# may move by (2% of 406 is 8); anything else read of them, on five times that.
ROSTER_TOLERANCE = 0.02
ROSTER_CHANGED_MOST = 8
ROSTER_TOUCHED_MOST = 40

# The sponsors. LsrSponsors.txt keeps this share of its rows. Of LsrsOnly.txt
# it is the allowance for rows with NO bill number only: the 13 the view
# cannot give are exactly those, and a row with one has never gone.
SPONSORS_KEPT_LEAST = 0.98

# The pair --check is about, and what it found on it. preflight holds
# check_pair()'s answer to these, so a change to a mapping that moves one of
# them is a change somebody made on purpose.
PAIR_DUMP = "2026-09-08"
PAIR_EXPORT = "2026-09-06"
PAIR_MEASURED = {
    "Docket.txt": {"rows": 25279, "export": 25279, "same": 25279, "identical": False},
    "LSRs.txt": {"rows": 1387, "export": 1387, "same": 1387, "identical": False,
                 "whole_lines": 1358},
    "LsrSponsors.txt": {"rows": 8571, "export": 8571, "same": 8571, "identical": True},
    "LsrsOnly.txt": {"rows": 6950, "export": 6963, "same": 6950, "identical": False},
    "legislators.txt": {"rows": 406, "export": 406, "same": 406, "identical": True},
    "RollCallSummary.txt": {"rows": 419, "export": 419, "same": 419, "identical": True},
    "RollCallHistory.txt": {"rows": 131199, "export": 131199, "same": 131199,
                            "identical": True},
}


class Problem(Exception):
    """What came back cannot be made into the day's files. Nothing is written."""


# ---- reading ----------------------------------------------------------------

def read_view(folder, name, columns=None):
    """Every row of one view's file, split on the pipe, each checked to be as
    wide as the view. The file has no header."""
    cols = columns or VIEWS.get(name) or LOOKUPS[name]
    path = Path(folder) / f"{name}.psv"
    if not path.is_file():
        raise Problem(f"{path.as_posix()} is not there")
    out = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            line = line.rstrip("\r\n")
            if not line:
                continue
            f = line.split("|")
            if len(f) != len(cols):
                raise Problem(f"{path.as_posix()} line {n:,} has {len(f)} columns and the "
                              f"{name} view has {len(cols)}")
            out.append(f)
    return out


def arrived_whole(count, rows):
    """Whether a view that wrote `rows` rows is the whole of the view the
    server counted `count` rows of.

    Fewer is a view cut short. MORE is not: the count is asked first, on the
    same connection, of tables the clerks are writing to, and a row entered
    while the view was being read is a row the view holds. As first written
    the two had to be equal, so one docket entry made in those seconds lost
    the night its fallback, and nothing is asked twice in one night. The
    guards judge what arrived either way, and the night says how many."""
    def number(x):
        return isinstance(x, int) and not isinstance(x, bool)
    return number(count) and number(rows) and rows >= count


def read_source(folder, views):
    """fetch_day_db.py's record of what it asked, checked: every view named
    answered without an error and wrote the rows the server counted, or more
    (arrived_whole)."""
    path = Path(folder) / SOURCE
    try:
        src = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Problem(f"{path.as_posix()} cannot be read ({type(e).__name__}), so what was "
                      "asked and what came back cannot be compared")
    got = src.get("views") if isinstance(src, dict) else None
    if not isinstance(got, dict):
        raise Problem(f"{path.as_posix()} names no views")
    for v in views:
        e = got.get(v)
        if not isinstance(e, dict):
            raise Problem(f"the {v} view was not asked for")
        if e.get("error"):
            raise Problem(f"the {v} view failed: {str(e['error'])[:160]}")
        if not arrived_whole(e.get("count"), e.get("rows")):
            raise Problem(f"the {v} view wrote {e.get('rows')} rows and the server counted "
                          f"{e.get('count')}")
    return src


def export_lines(data, width=None):
    """The rows of one of the export's files, without its byte-order mark or
    line ends. With width, a line that carries no pipe at all is the rest of
    the row before it: the export breaks a title over two lines where it holds
    a line break (CACR 14's, on every one of its sponsors' rows)."""
    text = data.decode("utf-8-sig", "replace") if isinstance(data, bytes) else data
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            continue
        if width and out and "|" not in line and out[-1].count("|") == width - 1:
            out[-1] += line
        else:
            out.append(line)
    return out


def as_bytes(lines):
    """A file as the export writes one: a byte-order mark, CRLF line ends."""
    return (BOM + "".join(ln + EOL for ln in lines)).encode("utf-8")


def installed_files(folder, names=DAY_FILES):
    """{name: bytes} of the files installed in `folder`; a missing one is a Problem."""
    out = {}
    for name in names:
        p = Path(folder) / name
        if not p.is_file():
            raise Problem(f"{p.as_posix()} is not installed, so there is no last good day "
                          "to take the years and the row order from")
        out[name] = p.read_bytes()
    return out


def years_of(lines, col=0):
    return {ln.split("|")[col].strip() for ln in lines} - {""}


def scope(installed):
    """Which session years each rebuilt file holds: the installed file's own.

    {"docket": [...], "session": [...], "ask": {view: first year to ask for}}.
    The session files -- the bill records, the sponsors and the roll calls --
    hold the current session year; the docket holds the term's two. A session
    file with no rows yet (no roll call taken) takes the bill records' years.
    """
    docket = years_of(export_lines(installed["Docket.txt"]))
    session = years_of(export_lines(installed["LSRs.txt"]))
    for name, years in (("Docket.txt", docket), ("LSRs.txt", session)):
        if not years or not all(y.isdigit() and len(y) == 4 for y in years):
            raise Problem(f"the installed {name} names the session years {sorted(years)}, "
                          "which is not a year or two")
    per = {"LsrSponsors.txt": years_of(export_lines(installed["LsrSponsors.txt"])),
           "RollCallSummary.txt": years_of(export_lines(installed["RollCallSummary.txt"])),
           "RollCallHistory.txt": years_of(export_lines(installed["RollCallHistory.txt"]))}
    for name, years in per.items():
        if not years <= session | docket:
            raise Problem(f"the installed {name} holds the years {sorted(years)} and the "
                          f"bill records {sorted(session)}: not one session's files")
    rc = (per["RollCallSummary.txt"] | per["RollCallHistory.txt"]) or session
    sp = per["LsrSponsors.txt"] or session
    return {"docket": sorted(docket), "session": sorted(session), "sponsors": sorted(sp),
            "rollcalls": sorted(rc),
            "ask": {"Docket": min(docket), "Legislation": min(session | sp),
                    "Sponsors": min(sp), "RollCallSummary": min(rc), "RollCallHistory": min(rc)}}


# ---- the seven files ----------------------------------------------------------

_clock = {}


def clock(s):
    """rollcalls_from_db.clock, remembered: 131,199 ballots share a few
    hundred times."""
    got = _clock.get(s)
    if got is None:
        got = _clock[s] = RC.clock(s)
    return got


def docket_rows(view, years):
    """Docket.txt's seven columns, in the view's statusorder. The seventh
    repeats the third: the view does not carry when a row was last changed."""
    def order(f):
        return int(f[10]) if f[10].strip().lstrip("-").isdigit() else 0
    out = []
    for f in sorted((f for f in view if f[0].strip() in years), key=order):
        when = clock(f[3])
        out.append("|".join([f[0], f[1].strip().zfill(4), when, f[4].strip(), f[5], f[6], when]))
    return out


def lsr_rows(legislation, years):
    out = []
    for b in legislation:
        if b[2].strip() not in years:
            continue
        f = []
        for j in LSR_MAP:
            if isinstance(j, str):
                f.append(j)
                continue
            v = b[j]
            if j in LSR_DATES:
                v = clock(v)
            elif j == LSR_CHAPTER:
                v = v.strip().zfill(4) if v.strip() else ""
            elif v in BIT:
                v = BIT[v]
            f.append(v)
        out.append("|".join(f))
    return out


def sponsor_rows(sponsors, years):
    """LsrSponsors.txt: the sponsors who have signed off. The view's other
    rows are exactly the ones who have not (80 of them on 8 September)."""
    return ["|".join([f[0], f[1], f[2], f[10], f[4]]) for f in sponsors
            if f[0].strip() in years and f[5] == "True"]


def lsrs_only_rows(sponsors, legislation, legislators, years):
    """LsrsOnly.txt: a signed-off sponsor who is a sitting member, on a request
    of this session (FullLSR begins with the year's two digits), with the
    bill, the member's chamber and the title."""
    bill = {b[47]: b for b in legislation}
    person = {p[0]: p for p in legislators}
    prefixes = tuple(y[2:] + "-" for y in years)
    out = []
    for f in sponsors:
        if f[0].strip() not in years or f[5] != "True":
            continue
        b, p = bill.get(f[9]), person.get(f[10])
        if not b or not p or p[6] != "True" or not b[11].startswith(prefixes):
            continue
        out.append("|".join([b[11], f[10], f[9], f[0], "Prime" if f[4] == "1" else "Sponsor",
                             b[14], p[5], b[4]]))
    return out


def legislator_rows(legislators):
    """legislators.txt: the sitting members. County and district without
    their leading zeros; and for a senator the two address columns are the
    other way round in the export (seven senators have both)."""
    def bare(x):
        return x.lstrip("0") or ("0" if x else "")
    out = []
    for f in legislators:
        if f[6] != "True":
            continue
        first, second = (f[13], f[12]) if f[5] == "S" else (f[12], f[13])
        out.append("|".join([f[0], f[1], f[2], f[4], f[5], f[7], bare(f[8]), bare(f[9]), f[10],
                             first, second, f[14], f[16], f[15], f[17]]))
    return out


@contextlib.contextmanager
def _dump_at(folder):
    """rollcalls_from_db reads db/; for one call it reads `folder` instead, so
    its formatter is used and not copied."""
    was = RC.DB
    RC.DB = Path(folder)
    try:
        yield
    finally:
        RC.DB = was


def rollcall_rows(folder, years):
    """(summary, history), sorted as rollcalls_from_db sorts them, year by year."""
    summary, history = [], []
    with _dump_at(folder):
        ids = RC.person_ids()
        for y in sorted(years):
            s, h = RC.build(y, ids)
            summary += s
            history += h
    return summary, history


# How a row is known to be the same row in the installed file, for its place
# in the order: the columns both sources carry.
def _first(n):
    return lambda ln: "|".join(ln.split("|")[:n])


ORDER_KEY = {"Docket.txt": _first(6), "LSRs.txt": _first(2), "LsrSponsors.txt": _first(4),
             "LsrsOnly.txt": _first(7), "legislators.txt": _first(1)}
# A docket row the clerk edited: the same year, request, entry time, bill and
# chamber, with other words. The export keeps it where it was (the docstring's
# HB 1218), so it takes that place here. The docket only: it is the one file
# the archive shows an edit in.
ORDER_LOOSE = {"Docket.txt": _first(5)}


def in_installed_order(new, old, key, loose=None):
    """`new`, with every row the installed file also holds in the installed
    file's place, and the rest after them in the order they came. With
    `loose`, a row with no place by `key` takes the place of an installed row
    no other row took and that `loose` calls the same: an edited row. The
    lines are all `new`'s own. (placed, fresh) counts beside it."""
    where = collections.defaultdict(collections.deque)
    for i, ln in enumerate(old):
        where[key(ln)].append(i)
    placed, fresh = [], []
    for ln in new:
        q = where.get(key(ln))
        if q:
            placed.append((q.popleft(), ln))
        else:
            fresh.append(ln)
    if loose and fresh:
        spare = collections.defaultdict(collections.deque)
        for i in sorted(i for q in where.values() for i in q):
            spare[loose(old[i])].append(i)
        rest = []
        for ln in fresh:
            q = spare.get(loose(ln))
            if q:
                placed.append((q.popleft(), ln))
            else:
                rest.append(ln)
        fresh = rest
    placed.sort(key=lambda x: x[0])
    return [ln for _, ln in placed] + fresh, len(placed), len(fresh)


def rebuild(views, installed, need_source=True):
    """({name: bytes} for all seven, facts) from the views in `views` and the
    files installed in `installed` -- or Problem, and nothing.

    facts: the years used, the rows of each file, how many rows took the
    installed file's place and how many are new, and any session year the
    views hold beyond the installed files'."""
    was = installed_files(installed)
    sc = scope(was)
    src = read_source(views, VIEWS) if need_source else None
    v = {name: read_view(views, name) for name in VIEWS}
    top = max(set(sc["docket"]) | set(sc["session"]))
    newer = {}
    for name, col in YEAR_COLUMN.items():
        i = VIEWS[name].index(col)
        later = collections.Counter(f[i].strip() for f in v[name]
                                    if f[i].strip().isdigit() and f[i].strip() > top)
        if later:
            newer[name] = dict(sorted(later.items()))
    summary, history = rollcall_rows(views, sc["rollcalls"])
    made = {
        "Docket.txt": docket_rows(v["Docket"], set(sc["docket"])),
        "LSRs.txt": lsr_rows(v["Legislation"], set(sc["session"])),
        "LsrSponsors.txt": sponsor_rows(v["Sponsors"], set(sc["sponsors"])),
        "LsrsOnly.txt": lsrs_only_rows(v["Sponsors"], v["Legislation"], v["Legislators"],
                                       set(sc["sponsors"])),
        "legislators.txt": legislator_rows(v["Legislators"]),
        "RollCallSummary.txt": summary,
        "RollCallHistory.txt": history,
    }
    facts = {"years": {k: sc[k] for k in ("docket", "session", "sponsors", "rollcalls")},
             "rows": {}, "order": {}, "newer_years": newer}
    if src is not None:
        facts["asked"] = src.get("asked")
        facts["view_rows"] = {name: (src["views"].get(name) or {}).get("rows") for name in VIEWS}
        # Rows entered while a view was being read (arrived_whole).
        facts["entered"] = {name: e["rows"] - e["count"] for name, e in src["views"].items()
                            if name in VIEWS and e["rows"] > e["count"]}
    out = {}
    for name in DAY_FILES:
        lines = made[name]
        if name in ORDER_KEY:
            lines, placed, fresh = in_installed_order(
                lines, export_lines(was[name], WIDTH[name]), ORDER_KEY[name],
                ORDER_LOOSE.get(name))
            facts["order"][name] = {"placed": placed, "new": fresh}
        bad = next((ln for ln in lines if ln.count("|") != WIDTH[name] - 1), None)
        if bad is not None:
            raise Problem(f"a rebuilt line of {name} has {bad.count('|') + 1} columns, not "
                          f"{WIDTH[name]}: {bad[:120]}")
        facts["rows"][name] = len(lines)
        out[name] = as_bytes(lines)
    return out, facts


# ---- the guards --------------------------------------------------------------

EXPORT_CLOCK = "%m/%d/%Y %I:%M:%S %p"


def _newest(lines, col=2):
    best = None
    for ln in lines:
        f = ln.split("|")
        try:
            d = datetime.strptime(f[col].strip(), EXPORT_CLOCK)
        except (ValueError, IndexError):
            continue
        if best is None or d > best:
            best = d
    return best


def _kept(old, new, key):
    """(rows of `old` still in `new`, rows of `new` not in `old`), by `key`,
    counting a key as many times as it occurs."""
    have = collections.Counter(key(ln) for ln in new)
    was = collections.Counter(key(ln) for ln in old)
    kept = sum(min(n, have.get(k, 0)) for k, n in was.items())
    return kept, sum(have.values()) - kept


def shared_columns(name):
    """The columns both sources carry, as one string: what a row is compared on."""
    if name == "Docket.txt":
        return _first(6)
    if name == "LsrsOnly.txt":
        return _first(7)
    if name == "LSRs.txt":
        return lambda ln: "|".join(x for i, x in enumerate(ln.split("|"))
                                   if i != LSR_SENATE_STATUS)
    return lambda ln: ln


def differences(files, installed):
    """{name: {"rows", "installed", "new", "gone"}} on the shared columns."""
    out = {}
    for name in DAY_FILES:
        new = export_lines(files[name], WIDTH[name])
        old = export_lines(installed[name], WIDTH[name])
        kept, fresh = _kept(old, new, shared_columns(name))
        out[name] = {"rows": len(new), "installed": len(old), "new": fresh,
                     "gone": len(old) - kept}
    return out


# A journal or calendar citation at the end of a docket row, in every shape
# the term's 17,290 cited rows have: "HJ 3  P. 7", "SJ 1", "HC 10  P. 98",
# "SC 6", "SC 12A". None is anywhere but the end of its row.
CITATION = re.compile(r"\b(?:HJ|SJ|HC|SC)\s*\d+[A-Za-z]?(?:\s*,?\s*P\.?\s*\d+)?\s*$", re.I)


def _cited(was, now):
    """Whether a docket row's words `now` are its words `was` with a citation
    written onto the end, or the one it had completed: what the journal's
    page does to a row. The row before its citation is on no copy on this
    disk; that it is the same words is read from the rows still waiting for
    one ("Ought to Pass: MA VV 03/05/2026" beside the same with "  HJ 6  P.
    2")."""
    m = CITATION.search(now)
    return bool(m) and now != was and CITATION.sub("", was).rstrip() == now[:m.start()].rstrip()


def _apart(old, new, key):
    """(rows of `old` not in `new`, rows of `new` not in `old`), by `key`, a
    key counted as many times as it occurs, each in its file's order."""
    def only(mine, theirs):
        left = collections.Counter(key(ln) for ln in theirs)
        out = []
        for ln in mine:
            k = key(ln)
            if left[k] > 0:
                left[k] -= 1
            else:
                out.append(ln)
        return out
    return only(old, new), only(new, old)


def _when(s):
    try:
        return datetime.strptime(s.strip(), EXPORT_CLOCK)
    except ValueError:
        return None


def _fields(ln, width):
    f = ln.split("|")
    return f + [""] * (width - len(f))


def _eg(text, most=150):
    """A row, or a sentence about one, short enough for a verdict."""
    text = " ".join(str(text).split())
    return text if len(text) <= most else text[:most - 3] + "..."


def _hold_docket(old, rows, records):
    """The docket, row by row: (stops, what was counted).

    A reworded row is an installed row and a row of tonight's alike in year,
    request, entry time, bill and chamber and unlike in words -- the same
    pairing its place in the order is given by (ORDER_LOOSE). What is left of
    the installed rows is gone, and of tonight's, new. A new row must sit
    under a bill somebody knows, carry an entry time that reads as one, and
    not be entered long before the installed file's newest; and no one day
    may bring more of them than a day has."""
    stops = []
    gone, new = _apart(old, rows, shared_columns("Docket.txt"))
    loose = ORDER_LOOSE["Docket.txt"]
    spare = collections.defaultdict(list)
    for i, ln in enumerate(new):
        spare[loose(ln)].append(i)
    taken, cited, reworded, vanished, rest = set(), [], [], [], []
    for ln in gone:                     # first the rows that only gained a citation
        q = spare.get(loose(ln)) or []
        words = _fields(ln, 7)[5]
        i = next((i for i in q if _cited(words, _fields(new[i], 7)[5])), None)
        if i is None:
            rest.append(ln)
        else:
            q.remove(i)
            taken.add(i)
            cited.append((ln, new[i]))
    for ln in rest:
        q = spare.get(loose(ln))
        if q:
            taken.add(q[0])
            reworded.append((ln, new[q.pop(0)]))
        else:
            vanished.append(ln)
    fresh = [ln for i, ln in enumerate(new) if i not in taken]

    def bill(f, at):
        return (f[0].strip(), f[1].strip(), f[at].strip().upper())
    known = {bill(f, 3) for f in (_fields(ln, 7) for ln in old)}
    known |= {bill(f, 10) for f in (_fields(ln, 39) for ln in records)}
    newest = _newest(old)
    strangers, undated, early, days = [], [], [], collections.Counter()
    for ln in fresh:
        f = _fields(ln, 7)
        if bill(f, 3) not in known:
            strangers.append(ln)
        d = _when(f[2])
        if d is None:
            undated.append(ln)
            continue
        days[d.date()] += 1
        if newest and d < newest - DOCKET_STAMP_SLACK:
            early.append(ln)

    def first(lines):
        return _eg("|".join(_fields(lines[0], 7)[:6]))
    if strangers:
        stops.append(f"Docket.txt: {len(strangers):,} new rows are under a bill that neither "
                     f"the installed docket nor LSRs.txt knows: {first(strangers)}")
    if undated:
        stops.append(f"Docket.txt: {len(undated):,} new rows carry an entry time that does not "
                     f"read as one: {first(undated)}")
    if early:
        stops.append(f"Docket.txt: {len(early):,} new rows were entered more than "
                     f"{DOCKET_STAMP_SLACK.days} days before the installed file's newest "
                     f"({newest:%Y-%m-%d %H:%M:%S}): {first(early)}")
    busiest = max(days.items(), key=lambda x: (x[1], x[0])) if days else None
    if busiest and busiest[1] > DOCKET_NEW_A_DAY_MOST:
        of_day = [ln for ln in fresh if (_when(_fields(ln, 7)[2]) or datetime.min).date()
                  == busiest[0]]
        stops.append(f"Docket.txt: {busiest[1]:,} new rows entered on {busiest[0]}, more than "
                     f"the {DOCKET_NEW_A_DAY_MOST:,} a day brings: {first(of_day)}")
    if len(cited) > DOCKET_CITED_MOST:
        stops.append(f"Docket.txt: {len(cited):,} installed rows gained a journal citation, "
                     f"more than {DOCKET_CITED_MOST:,}: {first([cited[0][1]])}")
    if len(reworded) > DOCKET_REWORDED_MOST:
        was, now = reworded[0]
        stops.append(f"Docket.txt: {len(reworded):,} installed rows are reworded in the "
                     f"database's, more than {DOCKET_REWORDED_MOST:,}: {first([was])} now reads "
                     f"{_eg(_fields(now, 7)[5], 80)}")
    if len(vanished) > DOCKET_GONE_MOST:
        stops.append(f"Docket.txt: {len(vanished):,} installed rows are not in the database's, "
                     f"more than {DOCKET_GONE_MOST:,}: {first(vanished)}")
    return stops, {"new": len(fresh),
                   "busiest_day": [busiest[0].isoformat(), busiest[1]] if busiest else None,
                   "cited": len(cited), "reworded": len(reworded), "gone": len(vanished)}


def _hold_records(old, rows):
    """LSRs.txt, record by record, on the columns the build reads: (stops,
    what was counted). A column it does not read is counted and never judged:
    the two status codes are the only ones that have ever differed."""
    stops = []
    was = {tuple(f[:2]): f for f in (_fields(ln, 39) for ln in old)}
    now = {tuple(f[:2]): f for f in (_fields(ln, 39) for ln in rows)}
    fresh = [k for k in now if k not in was]
    changed, rewritten, unread = [], [], collections.Counter()
    for k, a in was.items():
        b = now.get(k)
        if b is None:
            continue
        cols = [i for i in range(39) if a[i] != b[i]]
        read = [i for i in cols if i in LSR_READ]
        for i in cols:
            if i not in LSR_READ:
                unread[i] += 1
        if read:
            changed.append((k, read))
            if any(a[i].strip() and (i not in LSR_HEARING or not b[i].strip()) for i in read):
                rewritten.append((k, read))

    def said(found):
        k, cols = found[0]
        a, b = was[k], now[k]
        return _eg(f"{'-'.join(k)} {b[10] or a[10]}, "
                   + "; ".join(f"{LSR_NAMES.get(i, f'column {i + 1}')} {_eg(a[i], 40)!r} now "
                               f"{_eg(b[i], 40)!r}" for i in cols[:2]), 200)
    if len(fresh) > LSR_NEW_MOST:
        stops.append(f"LSRs.txt: {len(fresh):,} new bill records, more than {LSR_NEW_MOST:,}: "
                     f"{'-'.join(fresh[0])} {now[fresh[0]][10]}")
    if len(rewritten) > LSR_REWRITTEN_MOST:
        stops.append(f"LSRs.txt: {len(rewritten):,} installed bill records hold another value, "
                     f"or none, where the build reads one, more than {LSR_REWRITTEN_MOST:,}: "
                     + said(rewritten))
    elif len(changed) > LSR_CHANGED_MOST:
        stops.append(f"LSRs.txt: {len(changed):,} installed bill records changed in a column "
                     f"the build reads, more than {LSR_CHANGED_MOST:,}: " + said(changed))
    return stops, {"new": len(fresh), "changed": len(changed), "rewritten": len(rewritten),
                   "unread": {LSR_NAMES.get(i, f"column {i + 1}"): n
                              for i, n in sorted(unread.items())}}


def _hold_rollcalls(old_s, new_s, old_h, new_h):
    """The roll calls installed, beyond their counts: (stops, what was
    counted). What a page reads of a roll call -- when, on which bill, the
    question, the title -- and of a ballot -- whose, and which way -- is the
    clerk's to correct, one or two at a time, and never the file's to lose."""
    stops = []

    def told(lines, width, key, cols):
        return {tuple(f[:key]): tuple(f[i] for i in cols)
                for f in (_fields(ln, width) for ln in lines)}
    was, now = told(old_s, 15, 3, ROLLCALL_TOLD), told(new_s, 15, 3, ROLLCALL_TOLD)
    calls = sorted(k for k, v in was.items() if k in now and now[k] != v)
    if len(calls) > ROLLCALLS_CHANGED_MOST:
        k = calls[0]
        i = next(i for i in range(len(ROLLCALL_TOLD)) if was[k][i] != now[k][i])
        stops.append(f"RollCallSummary.txt: {len(calls):,} installed roll calls read otherwise "
                     f"in the database's, more than {ROLLCALLS_CHANGED_MOST}: {' '.join(k)} "
                     f"{('time', 'bill', 'question', 'title')[i]} {_eg(was[k][i], 50)!r} now "
                     f"{_eg(now[k][i], 50)!r}")
    was, now = told(old_h, 8, 4, BALLOT_CAST), told(new_h, 8, 4, BALLOT_CAST)
    cast = [k for k, v in was.items() if now.get(k) != v]
    if len(cast) > BALLOTS_CHANGED_MOST:
        k = min(cast)
        stops.append(f"RollCallHistory.txt: {len(cast):,} installed ballots are cast otherwise "
                     f"in the database's, or by another member, more than "
                     f"{BALLOTS_CHANGED_MOST}: {' '.join(k[:3])} member {k[3]} "
                     f"{'|'.join(was[k])} now {'|'.join(now[k]) if k in now else 'not there'}")
    return stops, {"calls": len(calls), "ballots": len(cast)}


def _hold_roster(old, rows):
    """The members installed and still on tonight's roster, on what the build
    reads of them: (stops, what was counted)."""
    stops = []
    was = {f[0]: f for f in (_fields(ln, 15) for ln in old)}
    now = {f[0]: f for f in (_fields(ln, 15) for ln in rows)}
    who = sorted(k for k, a in was.items()
                 if k in now and any(a[i] != now[k][i] for i in ROSTER_WHO))
    any_ = sorted(k for k, a in was.items()
                  if k in now and any(a[i] != now[k][i] for i in ROSTER_READ))

    def said(k, cols):
        a, b = was[k], now[k]
        return _eg(f"member {k}, " + "|".join(a[i] for i in cols) + " now "
                   + "|".join(b[i] for i in cols))
    if len(who) > ROSTER_CHANGED_MOST:
        stops.append(f"legislators.txt: {len(who):,} installed members have another name, "
                     f"chamber, county, district or party in the database's, more than "
                     f"{ROSTER_CHANGED_MOST}: {said(who[0], ROSTER_WHO)}")
    elif len(any_) > ROSTER_TOUCHED_MOST:
        k = any_[0]
        cols = [i for i in ROSTER_READ if was[k][i] != now[k][i]]
        stops.append(f"legislators.txt: {len(any_):,} installed members changed in a column "
                     f"the build reads, more than {ROSTER_TOUCHED_MOST}: {said(k, cols)}")
    return stops, {"who": len(who), "any": len(any_)}


def judge(files, installed, facts=None):
    """{"stops": [...], "warnings": [...], "differences": {...}, "held": {...}}:
    tonight's rebuilt files against the installed ones. Any stop, and nothing
    is installed. `installed` is {name: bytes}, as installed_files() gives it.
    "held" is what each content guard counted, whether or not it fired."""
    stops, warnings, held = [], [], {}
    rows = {n: export_lines(files[n], WIDTH[n]) for n in DAY_FILES}
    old = {n: export_lines(installed[n], WIDTH[n]) for n in DAY_FILES}
    diff = differences(files, installed)

    for name in DAY_FILES:
        wrong = sum(1 for ln in rows[name] if ln.count("|") != WIDTH[name] - 1)
        if wrong:
            stops.append(f"{name}: {wrong:,} rebuilt lines do not have {WIDTH[name]} columns")
        if old[name] and not rows[name]:
            stops.append(f"{name}: the database gave no rows and the installed file has "
                         f"{len(old[name]):,}")

    # The view is not behind the export.
    a, b = _newest(old["Docket.txt"]), _newest(rows["Docket.txt"])
    if a and b is None:
        stops.append("the database's docket has no dated entry")
    elif a and b < a:
        stops.append(f"the database's docket is behind: its newest entry is "
                     f"{b:%Y-%m-%d %H:%M:%S} and the installed file's is {a:%Y-%m-%d %H:%M:%S}")

    # The docket keeps its rows and its words, and its new rows are a day's.
    said, held["Docket.txt"] = _hold_docket(old["Docket.txt"], rows["Docket.txt"],
                                            old["LSRs.txt"] + rows["LSRs.txt"])
    stops += said

    def bills(lines):
        return {(f[0], f[3]) for f in (ln.split("|") for ln in lines) if len(f) > 3 and f[3]}
    lost = sorted(bills(old["Docket.txt"]) - bills(rows["Docket.txt"]))
    if lost:
        stops.append(f"{len(lost):,} bills in the installed docket are not in the database's: "
                     + ", ".join(f"{y} {b}" for y, b in lost[:6]))

    # Bill records: every one is there, and says what it said.
    def lsrs(lines):
        return {tuple(ln.split("|")[:2]) for ln in lines}
    lost = sorted(lsrs(old["LSRs.txt"]) - lsrs(rows["LSRs.txt"]))
    if lost:
        stops.append(f"{len(lost):,} bill records installed are not in the database's: "
                     + ", ".join("-".join(k) for k in lost[:6]))
    said, held["LSRs.txt"] = _hold_records(old["LSRs.txt"], rows["LSRs.txt"])
    stops += said

    # Roll calls: a vote does not un-happen, and its counts do not change.
    def counts(lines):
        return {tuple(f[:3]): tuple(f[5:9]) for f in (ln.split("|") for ln in lines)
                if len(f) > 8}
    was, now = counts(old["RollCallSummary.txt"]), counts(rows["RollCallSummary.txt"])
    lost = sorted(k for k in was if k not in now)
    moved = sorted(k for k in was if k in now and was[k] != now[k])
    if lost:
        stops.append(f"{len(lost):,} roll calls installed are not in the database's: "
                     + ", ".join(" ".join(k) for k in lost[:6]))
    if moved:
        stops.append(f"{len(moved):,} roll calls have other counts in the database: "
                     + ", ".join(f"{' '.join(k)} {'-'.join(was[k])} now {'-'.join(now[k])}"
                                 for k in moved[:4]))

    def ballots(lines):
        return collections.Counter(tuple(ln.split("|")[:3]) for ln in lines)
    was, now = ballots(old["RollCallHistory.txt"]), ballots(rows["RollCallHistory.txt"])
    fewer = sorted(k for k, n in was.items() if now.get(k, 0) < n)
    if fewer:
        stops.append(f"{len(fewer):,} roll calls have fewer ballots in the database: "
                     + ", ".join(f"{' '.join(k)} {was[k]} now {now.get(k, 0)}"
                                 for k in fewer[:4]))
    said, held["roll calls"] = _hold_rollcalls(
        old["RollCallSummary.txt"], rows["RollCallSummary.txt"],
        old["RollCallHistory.txt"], rows["RollCallHistory.txt"])
    stops += said

    # The roster: by count, by who is on it, and by what it says of them.
    def people(lines):
        return {ln.split("|")[0] for ln in lines}
    a, b = len(old["legislators.txt"]), len(rows["legislators.txt"])
    sitting = people(rows["legislators.txt"])
    left = people(old["legislators.txt"]) - sitting
    if a and abs(b - a) > ROSTER_TOLERANCE * a:
        stops.append(f"the roster is {b:,} members against {a:,} installed, more than "
                     f"{ROSTER_TOLERANCE:.0%} apart")
    elif a and len(left) > ROSTER_TOLERANCE * a:
        stops.append(f"{len(left):,} of the {a:,} members installed are not on the "
                     f"database's roster, more than {ROSTER_TOLERANCE:.0%}")
    said, held["legislators.txt"] = _hold_roster(old["legislators.txt"], rows["legislators.txt"])
    stops += said

    # Sponsors.
    a = len(old["LsrSponsors.txt"])
    kept = a - diff["LsrSponsors.txt"]["gone"]
    if a and kept < SPONSORS_KEPT_LEAST * a:
        stops.append(f"LsrSponsors.txt keeps {kept:,} of its {a:,} installed rows, fewer than "
                     f"{SPONSORS_KEPT_LEAST:.0%}")
    # LsrsOnly.txt lists sitting members only, so a member who leaves takes
    # their rows out of it: it is held to the rows of the members still on
    # tonight's roster. Who has left is the roster's question, above. Of
    # those rows, every one on a numbered bill is there tonight: it is a
    # sponsor on a bill's page. The share that may go is for the rows with no
    # bill number, which are what the Legislation view does not carry (two
    # requests, 13 rows) and what build_data.py skips.
    def member(ln):
        f = ln.split("|")
        return f[1] if len(f) > 1 else ""
    only = shared_columns("LsrsOnly.txt")
    theirs = [ln for ln in old["LsrsOnly.txt"] if member(ln) in sitting]
    went = _apart(theirs, rows["LsrsOnly.txt"], only)[0]
    numbered = [ln for ln in went if _fields(ln, 8)[5].strip()]
    bare = len(went) - len(numbered)
    held["LsrsOnly.txt"] = {"gone_numbered": len(numbered), "gone_unnumbered": bare}
    if numbered:
        stops.append(f"LsrsOnly.txt: {len(numbered):,} installed rows of members still sitting, "
                     f"each on a numbered bill, are not in the database's: {_eg(only(numbered[0]))}")
    if theirs and bare > (1 - SPONSORS_KEPT_LEAST) * len(theirs):
        stops.append(f"LsrsOnly.txt: {bare:,} installed rows with no bill number are not in the "
                     f"database's, more than {1 - SPONSORS_KEPT_LEAST:.0%} of the "
                     f"{len(theirs):,} rows of members still sitting")
    others = [ln for ln in old["LsrsOnly.txt"] if member(ln) not in sitting]
    went = len(others) - _kept(others, rows["LsrsOnly.txt"], only)[0]
    if left and went:
        warnings.append(f"{len(left):,} member{'s' if len(left) != 1 else ''} installed "
                        f"{'are' if len(left) != 1 else 'is'} not on the database's roster, "
                        f"and {went:,} rows of LsrsOnly.txt went with them")

    # A row entered while its view was being read (arrived_whole).
    for view, n in sorted(((facts or {}).get("entered") or {}).items()):
        warnings.append(f"{n:,} row{'s' if n != 1 else ''} more than the server had counted "
                        f"arrived from the database's {view} view: entered while it was "
                        "being read, and in tonight's files")

    # The session has not turned -- or, if it has, the night says so.
    newer = (facts or {}).get("newer_years") or {}
    if newer:
        years = sorted({y for d in newer.values() for y in d})
        warnings.append("the database holds session year "
                        + ", ".join(years) + ", newer than the installed files': tonight's "
                        "files keep the installed files' years, and a new term is a person's "
                        "decision")
    return {"stops": stops, "warnings": warnings, "differences": diff, "held": held}


def lookup_notes(views, installed):
    """Where a lookup installed here disagrees with the database: [sentences].
    A warning each, and the installed file stays. A lookup view that is not
    there, or will not read, is one too."""
    def lines(name):
        p = Path(installed) / name
        return set(export_lines(p.read_bytes())) if p.is_file() else None
    shapes = {
        "Subject": lambda f: "|".join([f[0], f[6], f[3]]),
        "GeneralStatusCodes": lambda f: "|".join([f[0], f[1]]),
        "BodyStatusCodes": lambda f: "|".join([f[1], f[3]]) if f[5] == "Senate" else None,
        "County": lambda f: "|".join([f[0].zfill(2), f[1], f[3]]) if f[1].strip() else None,
        "Committees": lambda f: "|".join([f[0], f[1], f[3]]),
    }
    notes = []
    for view, shape in shapes.items():
        name = LOOKUP_FILE[view]
        have = lines(name)
        if have is None:
            notes.append(f"{name} is not installed")
            continue
        try:
            theirs = {s for s in (shape(f) for f in read_view(views, view)) if s is not None}
        except Problem as e:
            notes.append(f"{name} was not compared with the database: {e}")
            continue
        extra = theirs - have
        missing = have - theirs
        # The export may hold committees the view lacks (H53, a joint
        # committee nothing names today); the other way round is news.
        if view == "Committees":
            missing = set()
        if extra or missing:
            notes.append(f"{name} differs from the database's {view} ("
                         + "; ".join(x for x in (
                             f"{len(extra)} rows only in the database" if extra else "",
                             f"{len(missing)} rows only in the installed file" if missing else "")
                             if x) + "): the installed file stays")
    return notes


# ---- the pair on this disk ----------------------------------------------------

def export_of(archive, day, names=DAY_FILES):
    """{name: bytes} of one day's export, from the content-addressed archive."""
    root = Path(archive)
    out = {}
    for name in names:
        ref = root / "snapshots" / day / f"{name}.sha256"
        if not ref.is_file():
            raise Problem(f"{ref.as_posix()} is not there")
        digest = ref.read_text(encoding="utf-8").strip()
        blob = root / "store" / f"{digest}.gz"
        if not blob.is_file():
            raise Problem(f"{blob.as_posix()} is not there")
        with gzip.open(blob, "rb") as fh:
            data = fh.read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise Problem(f"{blob.as_posix()} is not the file its name says")
        out[name] = data
    return out


def pair_here(db="db", archive="nh-archive"):
    """Why the pair --check compares is not on this disk, or "" when it is:
    the six views as dumped on 8 September, and the export of the 6th."""
    db, man = Path(db), None
    try:
        man = json.loads((db / "_manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"no {(db / '_manifest.json').as_posix()} here"
    for v in VIEWS:
        if not (db / f"{v}.psv").is_file():
            return f"no {(db / (v + '.psv')).as_posix()} here"
        when = str((man.get(v) or {}).get("fetched") or "")
        if not when.startswith(PAIR_DUMP):
            return (f"db/{v}.psv was dumped {when[:10] or 'at no recorded time'}, not on "
                    f"{PAIR_DUMP}: it and the export of {PAIR_EXPORT} do not show one state")
    if not (Path(archive) / "snapshots" / PAIR_EXPORT).is_dir():
        return f"no {archive}/snapshots/{PAIR_EXPORT} here"
    return ""


def check_pair(db="db", archive="nh-archive"):
    """{name: {"rows", "export", "same", "identical", ...}}: the seven rebuilt
    from the dump against the export of the same state. `same` is rows equal
    on the columns both carry; `identical` is the whole file, byte for byte."""
    was = export_of(archive, PAIR_EXPORT)
    tmp = Path(tempfile.mkdtemp(prefix="gr-dayfiles-"))
    try:
        for name, data in was.items():
            (tmp / name).write_bytes(data)
        files, facts = rebuild(db, tmp, need_source=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = {}
    for name in DAY_FILES:
        new = export_lines(files[name], WIDTH[name])
        old = export_lines(was[name], WIDTH[name])
        kept, _ = _kept(old, new, shared_columns(name))
        out[name] = {"rows": len(new), "export": len(old), "same": kept,
                     "identical": files[name] == was[name]}
        if name == "LSRs.txt":
            out[name]["whole_lines"] = _kept(old, new, lambda ln: ln)[0]
    return out, judge(files, was, facts), facts


# ---- the command --------------------------------------------------------------

def write_all(files, out):
    """All seven into `out`, or none: each is written beside its place and
    moved in only when every one is written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    parts = []
    try:
        for name in DAY_FILES:
            part = out / (name + ".part")
            part.write_bytes(files[name])
            parts.append((part, out / name))
    except OSError:
        for part, _ in parts:
            part.unlink(missing_ok=True)
        raise
    for part, dst in parts:
        os.replace(part, dst)


def held_said(held):
    """What the content guards counted, a line a file: [lines]."""
    out = []
    d = held.get("Docket.txt")
    if d:
        day = d.get("busiest_day")
        out.append(f"  Docket.txt, row by row: {d['new']:,} new"
                   + (f", the most entered on one day {day[1]:,} ({day[0]})" if day else "")
                   + f"; of the installed rows {d['cited']:,} gained a citation, "
                     f"{d['reworded']:,} reworded, {d['gone']:,} gone")
    d = held.get("LSRs.txt")
    if d:
        out.append(f"  LSRs.txt, on the columns the build reads: {d['new']:,} new records; of "
                   f"the installed {d['changed']:,} changed, {d['rewritten']:,} with a value "
                   "replaced or lost"
                   + ("; in columns it does not read: "
                      + ", ".join(f"{k} on {n:,}" for k, n in d["unread"].items())
                      if d.get("unread") else ""))
    d = held.get("roll calls")
    if d:
        out.append(f"  the roll calls installed: {d['calls']:,} read otherwise, "
                   f"{d['ballots']:,} ballots cast otherwise")
    d = held.get("legislators.txt")
    if d:
        out.append(f"  the members installed: {d['who']:,} with another name, district or party, "
                   f"{d['any']:,} changed at all")
    d = held.get("LsrsOnly.txt")
    if d:
        out.append(f"  LsrsOnly.txt, rows of sitting members gone: {d['gone_numbered']:,} on a "
                   f"numbered bill, {d['gone_unnumbered']:,} with no bill number")
    return out


def report(result, facts, notes=()):
    lines = []
    for name in DAY_FILES:
        d = result["differences"][name]
        o = (facts.get("order") or {}).get(name)
        lines.append(f"  {name:22} {d['rows']:>8,} rows ({d['installed']:,} installed): "
                     f"{d['new']:,} new, {d['gone']:,} gone"
                     + (f"; {o['placed']:,} in the installed order, {o['new']:,} after them"
                        if o else ""))
    lines += held_said(result.get("held") or {})
    for w in list(result["warnings"]) + list(notes):
        lines.append(f"  warning: {w}")
    for s in result["stops"]:
        lines.append(f"  STOP: {s}")
    lines.append("  every guard passed" if not result["stops"] else
                 f"  {len(result['stops'])} guard(s) fired: nothing would be installed")
    return lines


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default=str(VIEWS_DIR),
                    help="the folder of views fetch_day_db.py wrote (default .night/dbday)")
    ap.add_argument("--installed", default=".",
                    help="where the last good day's files are installed (default here)")
    ap.add_argument("--out", help="write the seven files here, all or none, if every "
                                  "guard passes")
    ap.add_argument("--check", action="store_true",
                    help="the dump of 8 September in db/ against the export of the 6th")
    ap.add_argument("--db", default="db", help="(--check) the dump")
    ap.add_argument("--archive", default="nh-archive", help="(--check) the archive")
    a = ap.parse_args()

    if a.check:
        why = pair_here(a.db, a.archive)
        if why:
            print(f"The pair is not on this disk: {why}. Nothing compared.")
            return 1
        try:
            got, result, facts = check_pair(a.db, a.archive)
        except Problem as e:
            print(f"NOT REBUILT: {e}")
            return 1
        print(f"The seven day files rebuilt from the dump of {PAIR_DUMP} ({a.db}/), against "
              f"the export of {PAIR_EXPORT} ({a.archive}/):")
        ok = True
        for name in DAY_FILES:
            g = got[name]
            want = PAIR_MEASURED[name]
            same = all(g.get(k) == v for k, v in want.items())
            ok = ok and same
            print(f"  {name:22} {g['rows']:>8,} rebuilt, {g['export']:>8,} in the export, "
                  f"{g['same']:>8,} the same on the columns both carry"
                  + (f", {g['whole_lines']:,} whole lines" if "whole_lines" in g else "")
                  + ("; byte-identical" if g["identical"] else "")
                  + ("" if same else f"   <-- was {want}"))
        for ln in report(result, facts)[len(DAY_FILES):]:
            print(ln)
        print("As measured on 1 October 2026." if ok else
              "NOT as measured on 1 October 2026: a mapping here, or the pair, has changed.")
        return 0 if ok and not result["stops"] else 1

    try:
        files, facts = rebuild(a.views, a.installed)
        result = judge(files, installed_files(a.installed), facts)
    except Problem as e:
        print(f"NOT REBUILT: {e}. Nothing written.")
        return 1
    print(f"The seven day files from {Path(a.views).as_posix()}/, against the files installed "
          f"in {Path(a.installed).as_posix()}/ (years {', '.join(facts['years']['docket'])}):")
    for ln in report(result, facts, lookup_notes(a.views, a.installed)):
        print(ln)
    if result["stops"]:
        print("Nothing written.")
        return 1
    if a.out:
        write_all(files, a.out)
        print(f"All seven written to {Path(a.out).as_posix()}/. Nothing was installed.")
    else:
        print("Nothing written: no --out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
