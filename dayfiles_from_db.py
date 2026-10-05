#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-01.11
"""
The day's seven changing files, rebuilt from the database's views. No network.

    python3 dayfiles_from_db.py --check          # the one pair on this disk: the dump of
                                                 # 8 September against the export of the 6th
    python3 dayfiles_from_db.py                  # .night/dbday/ against the files installed
                                                 # here: what would change, and every guard
    python3 dayfiles_from_db.py --out DIR        # ... and write the seven there, all or none
    python3 dayfiles_from_db.py --nights 3       # ... the installed files three nights old

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
                          25, the Senate status code, differs on 29 bills, and
                          is not taken from the view (below): with the
                          installed file's, byte-identical
    LsrSponsors.txt       byte-identical
    LsrsOnly.txt          6,950 of 6,963 rows. The 13 are two requests with no
                          bill number, which Legislation does not carry and
                          build_data.py skips; and the export breaks one title
                          over two lines where the view has it on one
    legislators.txt       byte-identical
    RollCallSummary.txt   byte-identical
    RollCallHistory.txt   byte-identical

It was a quiet week: the newest docket row in both is 4 September. What a
session day shows is not known.

TWO STATUS CODES IN LSRs.txt, WHICH NOTHING READS

Column 25, the Senate status code, IS NOT THE VIEW'S. On 29 bills the view
and the export disagree, the same 29 on 8 September and on 2 October, and it
is the view that is wrong: the General Court's website (bill_status.json)
has a Senate status for 19 of them and agrees with the export on all 19, and
the Senate's own docket agrees with the export on every one read -- SB 532
was killed 16-8 on 19 February 2026, the export says 09 INEXPEDIENT TO
LEGISLATE and the view 02 IN COMMITTEE. build_data.py does not read the
column, so no page was wrong; but it was a value known to be wrong, written
to a file. So an LSR the installed file holds keeps the installed file's
code, and a new LSR is written with none. The view cannot be shown right for
a new row: no LSR has been added on any pair on this disk. (Where the export
has no Senate status, 646 rows, the view has none either, so a blank is also
what a request with no Senate action most likely carries.)

Column 17, the House status code, IS THE VIEW'S, and that is a decision. On
2 October it differed from the installed export on 16 bills, 04 REPORT FILED
there and 07 INTERIM STUDY in the view: the 16 whose interim study report
had been filed. Unlike column 25 nothing shows the view wrong. On the one
pair of the same state it equals the export's on all 1,387 rows; the view
itself moved (two of the 16 read 04 in it on 8 September, and they are the
only two rows of the whole view to have changed since); it holds no 04 at
all now, the five reports filed on 30 September included; and 07 is where
every such bill ended in the ten terms from 2006 (898 of 898 in the
database's PastLegislation). That reads as the General Court resetting the
code after the last export, which is likely and not proven: the House status
on HB 224's own page at gc.nh.gov settles it in one look. Carrying the
installed code instead would freeze the column for as long as the export is
down, and on a session day that is hundreds of bills known to be stale.
held_said() names the column each night it differs.

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
said so. So the files were held to what the installed ones SAY as well, on
the columns the build reads. Two reviewers then doctored the views 130 ways
and replayed the term night by night, and found what that still let in --
whatever was ADDED: every ballot twice, a wrong roll call filed in front of
the right one, 5,000 sponsors nobody signed, an invented roll call, 20,000
docket rows spread over three weeks; a view in another code page; and a
handful of anything under a ceiling that was a guess, with nobody told
which -- and what it stopped that was right: the Senate's own late entries,
on eight nights of the term. What holds now:

    what no export holds       a character read in the wrong encoding, a field
                               that reads NULL or True (a member's name may:
                               the House has had a Rep. True); a view that is
                               not UTF-8, or begins with a byte-order mark, is
                               not read at all (read_view)
    no row twice               a bill record, a bill number, a member, a roll
                               call, a ballot, a sponsor's row, a request's
                               prime sponsor: once each, or as often as the
                               installed file has it; a docket row, a few
    the view is not behind     its newest docket entry is not older than the
                               installed file's
    the docket's new rows      each under a bill the installed docket or
                               LSRs.txt knows, or tonight's LSRs.txt brings,
                               in one of the two chambers, with words, and an
                               entry time that reads as one; no more than
                               DOCKET_NEW_A_DAY_MOST entered on any one day,
                               nor in the night; entered after the views were
                               asked, DOCKET_AHEAD_MOST, none more than
                               DOCKET_AHEAD_SLACK after; entered more than
                               DOCKET_STAMP_SLACK before the installed file's
                               newest, DOCKET_LATE_MOST if they are the
                               Senate's and not older than their bill, and
                               otherwise none
    the docket's old rows      no bill missing; at most DOCKET_GONE_MOST gone,
                               DOCKET_CITED_MOST with a journal citation
                               written onto them, DOCKET_MARKED_MOST given a
                               mark, DOCKET_REMARKED_MOST of those with other
                               words after it, DOCKET_REWORDED_MOST reworded
                               any other way
    bill records               every (year, LSR) installed is there tonight,
                               with the chamber and the bill number it had;
                               at most LSR_UNBACKED_MOST changed where the
                               build reads them with nothing in the docket to
                               say why, a first committee in a chamber whose
                               docket has no row of the bill yet aside
                               (LSR_ALONE_MOST); LSR_RETITLED_MOST with
                               another title, each named,
                               LSR_REWRITTEN_MOST with a value replaced or
                               lost, LSR_CHANGED_MOST changed at all; and
                               LSR_NEW_MOST new, each with a title, a chamber
                               and a bill number of its own, and all but
                               LSR_UNSPONSORED_MOST with a sponsor
    roll calls                 every one installed is there with the ballots
                               it had, none added; at most
                               ROLLCALLS_CHANGED_MOST read otherwise -- the
                               time, the bill, the question, the title -- as
                               many have other counts, and
                               BALLOTS_CHANGED_MOST ballots are cast
                               otherwise; one whose Yea and Nay ballots were
                               its counts still adds up; at most
                               ROLLCALLS_NEW_MOST new, each numbered on from
                               its chamber's last, taken by the time the views
                               were asked, with counts that are numbers and
                               ballots of members the roster's view knows,
                               which are its counts -- or, on
                               ROLLCALLS_CHANGED_MOST of them, within
                               ROLLCALL_ADRIFT_MOST ballots of them
    the roster                 within ROSTER_TOLERANCE of the installed count,
                               and at most ROSTER_MOVED_MOST joined or left;
                               at most ROSTER_CHANGED_MOST with another name,
                               chamber, county, district or party,
                               ROSTER_TOUCHED_MOST changed in anything else
                               the build reads, another seat or e-mail address
                               that reads as one aside
    sponsors                   LsrSponsors.txt loses at most
                               SPONSORS_GONE_MOST of its rows and gains at
                               most SPONSORS_NEW_MOST, SPONSORS_LATE_MOST of
                               them on a bill long since introduced.
                               LsrsOnly.txt, which lists sitting members
                               only, keeps every row of a member still on
                               tonight's roster that names a bill, and
                               SPONSORS_KEPT_LEAST of their rows that name
                               none
    the shape                  every line has its file's number of columns

A column no reader reads is never judged. The docket's seventh is not
compared at all; a column of LSRs.txt that build_data.py does not read --
the two status codes are the only ones to have differed -- is counted and
said (held_said).

Each threshold is a constant below, with the measurement it came from: the
real exports of September, night against night (eleven pairs, and no session
day among them), and for a session day the stamps the term's own files carry
-- rows entered and rows changed per day across the term, roll calls per day
across 27 years. A ceiling that is a day's work is a night's, and is
multiplied when the installed files are older than a night (SPAN), by what
that many days running really brought. The ones that say GUESS stand above a
measured nothing, and are small on purpose.

WHAT A NIGHT TELLS. Under a ceiling a few rows may differ and the night be
right: a clerk's correction looks like that. Every count that sits under a
ceiling which is a guess, or a correction's, comes with its rows:
judge()'s "told", all of them up to TOLD_MOST, which is as many as the
largest of the handfuls. The night's warning says how many and where they
are named -- "each", or "the first 50" of a longer list -- and the rows
themselves, which are the General Court's words and members' names, go to
the verdict (day_files, told), the log and the what-changed report, never to
the run's page.

A STOP OR A NAME (2 October 2026, the third pass). Two reviewers read the
guards against each other's purpose: one found the honest nights they stop,
the other what still went in unnamed. Where a count could be one of a few
honest rows or one of a few wrong ones and nothing in the files tells them
apart, the night goes through and the rows are named; a whole file, or many
rows, stops. So a tally the clerk corrects, a new roll call a ballot from
its typed counts, every member's e-mail address at another domain and a
first referral typed ahead of its docket row are named now, and no longer
stop; a row reworded behind a mark is counted as reworded, and a title
replaced is named.

LsrsOnly.txt was first held to 98% of ALL its rows. But a member who leaves
takes every row of theirs out of it, in the export as here, and three
members each hold more than 2% of it (155, 153 and 144 of 6,963 on
30 September): one resignation would have stopped the fallback for as long as
the export stayed down. Who has left is the roster guard's question, and it
asks it by person rather than by count alone. Then it was held to 98% of the
rows of the members still sitting, which let the sponsors of ten bills go:
the 13 rows the view cannot give all lack a bill number, so that is what the
allowance is now for.

WHAT STILL PASSES, and is named and not stopped

    one or two of anything a      a docket row gone (5), reworded (40),
    clerk corrects                reworded behind a mark (50) or moved to
                                  another bill; a roll call refiled, a tally
                                  corrected or two ballots exchanged (2
                                  each); a new roll call a ballot or two from
                                  its counts (2); a member's name, party or
                                  district (2); four members joined or left;
                                  five bill records changed with the docket
                                  at rest; two new ones with no sponsor; five
                                  sponsors' rows gone, or added to an old
                                  bill
    any number, if it reads       a member's seat or e-mail address, changed
    as what it is                 to another that reads as one; up to 600
                                  bill records' first committee in a chamber
                                  whose docket has no row of the bill yet,
                                  the code one an installed record holds
    a new Senate docket row       up to 40, each on a bill the files know and
    with an old entry time        not older than the bill: the Senate's own
                                  late entries cannot be told from a row
                                  planted to look like one
    new rows that look like a     new docket rows on real bills, in a real
    day's                         chamber, dated in the days since the
                                  installed file's newest, under 1,000 a day:
                                  the 31 real ones of 2 October filed under
                                  another bill pass, and nothing in the files
                                  could say otherwise
    in session, changes to the    a record whose bill has a docket row in the
    bills that are moving         last fortnight, or a new one tonight, is
                                  held only to the session day's ceilings (40
                                  titles, 170 rewritten, 700 changed). A
                                  title replaced is named; a committee or a
                                  subject code is not, and is in the
                                  what-changed report's own list: 53 such
                                  bills given another of each passed

And NOT named, because nothing in the files tells them from a day's work:
new docket rows on real bills, dated since the installed file's newest and
under 1,000 a day (900 bills each "Signed by Governor" yesterday passed);
and new bill records that each come with a title, a number of their own and
a sponsor's row (300 passed: it is the ones with NO sponsor's row that are
held to two). Both are in the what-changed report's ordinary sections, by
bill, the morning after.

WHAT A RIGHT NIGHT CAN STILL BE STOPPED BY

Every guard fails closed, and some real days are on the wrong side of one:

    the roster at a new term            on Organization Day, the first
                                        Wednesday of December (2 December
                                        2026), about a third of the House is
                                        new: far past the 2% and the four.
                                        Since 5 October 2026 such a roster is
                                        taken, and its members joined and
                                        left named, when tonight's
                                        Members.txt from the website names
                                        the same people (roster_named, the
                                        person's decision); without that it
                                        still stops every database night
                                        until an export installs the roster
    three tallies corrected at          or one changed with no ballot to go
    once                                with it; or a new roll call three
                                        ballots from its typed counts (one in
                                        27 years: the House's first of 2000,
                                        by twelve)
    a bill carried into the             its docket rows are filed again under
    second year                         the new year and request (SB 66, on
                                        19 November 2025): the bill is gone
                                        from the year it was in, and its rows
                                        are all gone and all new
    a late entry in the House           or more than 40 of the Senate's in one
                                        night (the most is 17)
    a sponsor off a numbered bill       or changed from Sponsor to Prime: the
                                        installed row is not there tonight.
                                        No sponsor is marked withdrawn in any
                                        data on this disk
    more than a handful of what         six docket rows deleted, three members'
    is a guess                          parties, five members sworn in on one
                                        day, six records corrected at rest, 41
                                        members' street addresses
    more in a night than the            over 1,000 citations in a night, 100
    days it covers have                 rows marked, 40 reworded, 170 bill
                                        records rewritten, 142 roll calls --
                                        each times SPAN when the installed
                                        files are older than a night

What the night says then: nothing is installed and yesterday's files stay;
the verdict's day_files has source "none", why_code "guard" and "stops", one
sentence a guard, each naming the file, the count and a row, and
"stops_wider", how many of them are on a ceiling that SPAN widens (_Wider);
the run's page, which is public, says how many checks stopped it and where
they are named, that the site still serves the last build, and what the
next night will do. Tonight's files are compared with the installed ones,
and those have not moved: a check on what they hold stops the next night
too. A ceiling on a night's work does not, of itself -- it is wider a night
later, and the same views may pass it with nobody deciding; the page says
which kind stopped it, and the night that then installs says that it did.
The second night the checks stop it is an error on the page
(nightly.DB_STOPPED_MOST). There is no switch that installs a night a
person has read and found right.

And a stop ends the night's asking. The night turns here straight after the
export's first empty try, and after a stop it does not ask the export again
that night (nightly.DB_LOOKED_WRONG): a later try that arrived whole would go
in on the export's own, coarser, checks. So a stop that was wrong costs the
night whatever that second try would have brought, and the page says it was
not made. A view that cannot be read at all -- another encoding, a byte-order
mark, a line of the wrong width -- is a Problem and no stop: the export is
asked once more, as after a connection that failed.

THE SESSION YEAR IS THE INSTALLED FILES'. The export decides what a "current"
file holds; this copies the last good day's years rather than guessing a new
term's. fetch_day_db.py asks for those years and later, so a newer year in
the views is seen, left out, and said (a warning, not a stop).
"""

import argparse
import collections
import contextlib
import functools
import gzip
import hashlib
import io
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
# The Senate status code, from 0: the one column of LSRs.txt the view is known
# to have wrong (29 bills; the docstring). Never the view's: the installed
# file's for an LSR it holds, none for a new one. Compared without it, since a
# new LSR's is not the export's.
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
LSR_ITSELF = (3, 10)                    # the chamber it began in, its bill number
LSR_REFERRAL = {13: "H", 21: "S"}       # a committee of referral, and whose docket says so
ROSTER_WHO = (1, 2, 3, 4, 6, 7, 8)      # last, first, middle, chamber, county, district, party
ROSTER_READ = ROSTER_WHO + (5, 10, 11, 12, 13, 14)      # ... seat, address, e-mail
ROLLCALL_TOLD = (3, 4, 11, 12)          # when, the bill, the question, the title
BALLOT_CAST = (4, 6)                    # the member's PersonID, the vote
# What LSRs.txt's columns are, for a sentence that names one.
LSR_NAMES = {2: "title", 3: "chamber", 4: "bill type", 5: "appropriation flag",
             6: "fiscal flag", 7: "local flag", 8: "request number", 9: "bill number, padded",
             10: "bill number", 11: "chapter", 12: "subject code",
             13: "House committee of referral", 14: "House current committee",
             15: "House date introduced", 16: "House status code", 17: "House status date",
             18: "House due date", 19: "House floor date",
             21: "Senate committee of referral", 22: "Senate current committee",
             23: "Senate date introduced", 24: "Senate status code", 25: "Senate status date",
             26: "Senate due date", 27: "Senate floor date", 29: "general status code",
             30: "hearing committee", 31: "hearing date", 32: "hearing room"}

# A CEILING IS A NIGHT'S, and the installed files are not always a night old:
# a night that installs nothing leaves them where they were, and the next
# night's files are compared with the same ones. What k days running brought,
# against the busiest one day, at most (the largest of four measured on the
# term: docket rows entered 498, 706, 825, 874, 939, 1,072 in seven, 1,530 in
# ten, 1,774 in fourteen; citations written 492, 732, 795, 1,078, 1,082,
# 1,310, 1,342, 1,424; requests made bills 202, 280, 298, 298, 410, 519, 534,
# 675; their sponsors' rows 1,166, 1,593, 1,706 in four, 3,295 in seven). The
# ceilings that are a day's work are multiplied by it (_ceiling); the ones
# that are a handful above nothing are not. Past fourteen nights it grows no
# more.
SPAN = ((1, 1.0), (2, 1.5), (3, 1.7), (5, 2.2), (7, 2.9), (10, 3.1), (14, 3.6))

# Docket.txt. New rows entered on any one day: the busiest day of the term
# had 498 (6 March 2025; September's most is 34). The same number is the most
# a night brings in all, times SPAN: 20,000 invented rows spread at 953 a day
# passed the day's ceiling alone.
DOCKET_NEW_A_DAY_MOST = 1000
# How far before the installed file's newest entry a new row's entry time may
# be and the row be an ordinary one. No new row on the twelve pairs was before
# it at all; but an entry time is not always when the row was written -- a
# conference committee meeting is stamped midnight of the meeting's own day,
# up to 6 days 12 hours ahead (109 rows a day or more ahead) -- so the newest
# entry installed can be a week in the future, and a row written the next
# morning "older" than it by that much. Twice that. It is measured from the
# time the views were asked when that is the earlier: one row stamped a year
# ahead, once installed, made every honest row after it a year "old".
DOCKET_STAMP_SLACK = timedelta(days=14)
# New rows entered earlier than that. THE SENATE WRITES THEM: a row entered
# late carries the day of the action and the clock of the moment it was typed,
# so its third and seventh columns fall on different days at the same second
# (45 Senate rows of the term, where chance gives fewer than one; 34 of them
# more than 14 days back, the most written on one day 17, on 8 July 2025, 33
# days back). Twice that, rounded up, and each is named. A stop at the first
# such row, which this was, stopped eight real nights of the term and every
# database night after each. No House row shows it (two share a clock, which
# is what chance gives of 9,000), so a House row so entered still stops; and
# none was entered before its own bill's first row, so one that is stops too.
DOCKET_LATE_MOST = 40
# New rows entered AFTER the views were asked: the conference meetings above.
# The most written on one day is 40 (21 May 2026), the furthest ahead 6 days
# 12 hours. Twice each.
DOCKET_AHEAD_MOST = 80
DOCKET_AHEAD_SLACK = timedelta(days=14)
# Rows that occur more often than once, or than the installed file has them:
# three pairs in the term, each a conference meeting's notice entered twice,
# two of them on one day. Twice that. (A view joined to something it should
# not be returns every row twice.)
DOCKET_TWICE_MOST = 4
# Installed rows whose words gain a journal or calendar citation ("HJ 3  P.
# 7", "SJ 1"): the journal's page, written onto a row weeks after its day.
# 10,533 of the 11,293 rows changed on a later day than they were entered end
# in one; the most in a day is 492 (18 February 2025). Times SPAN.
DOCKET_CITED_MOST = 1000
# Installed rows given a mark -- ==CANCELLED==, ==RECESSED==, ==RESCHEDULED==
# -- before their words: 477 rows of the term, the most in a day 50
# (23 January 2026), in fourteen days 101.
DOCKET_MARKED_MOST = 100
# ... and of those, the rows whose words AFTER the mark are not the installed
# words. A mark was all that was looked for, so 100 committee reports reworded
# from Ought to Pass to Inexpedient to Legislate behind "==AMENDED==" were
# installed, and nobody told which. A hearing moved is such a row -- its day,
# its hour or its room is in its words: 130 rows of the term are marked
# RESCHEDULED, ROOM CHANGE, TIME CHANGE or RECONVENE, the most changed on one
# day 23 (8 October 2025), in fourteen days 41. Twice the day's, rounded up,
# and each is named. A GUESS as to what such a row was before: no pair on
# this disk shows one being marked.
DOCKET_REMARKED_MOST = 50
# Installed rows reworded any other way -- an amendment's number corrected, a
# room changed: at most 283 rows of the term (changed on a later day, with no
# citation and no mark; some of those only had their stamp moved), the most
# in a day 18 (21 July 2026), in fourteen days 33; and 1 in September (HB
# 1218). It was 100 for marks and these together, which let 100 outcomes be
# rewritten.
DOCKET_REWORDED_MOST = 40
# Installed rows gone and not reworded. None went on any pair, and a
# cancelled meeting is marked, not removed. It was 1% of the file, 253 rows,
# and then 25, which let the last 25 "Signed by Governor" rows go. A GUESS
# above nothing: a deleted row leaves no stamp to count. Each is named.
DOCKET_GONE_MOST = 5

# LSRs.txt. No bill record changed in a read column on any pair, so these are
# a session day's, from the docket, and each is times SPAN. New records: the
# most requests made bills in one day is 202 (25 November 2025,
# Legislation.DateLSRBill).
LSR_NEW_MOST = 400
# New records with no sponsor's row in tonight's LsrSponsors.txt. One of the
# 1,387 installed has none (HR 48, a memorial resolution). Twice that, and
# each is named: 300 invented records, each with a title and a bill number of
# its own, passed. (The docket cannot be asked instead: a request is made a
# bill two days before its first docket row, at the median, and up to 47.)
# With one invented sponsor's row each they pass still, unnamed: nothing in
# the files tells such a record from a request made a bill.
LSR_UNSPONSORED_MOST = 2
# Installed records whose title is replaced by another. A title changes when
# an amendment names a new one, and the most bills with a new title named in
# the docket in one day is 19 (4 March 2026).
LSR_RETITLED_MOST = 40
# Installed records where a read column that held a value holds another, or
# none (a hearing moved to another day aside): a title, a flag, a committee
# corrected. The most bills with an amendment adopted in a day is 83
# (11 March 2026).
LSR_REWRITTEN_MOST = 170
# Installed records with any read column changed, a first referral or a
# hearing scheduled included: the most records with a docket row entered in
# one day is 346 (5 February 2026).
LSR_CHANGED_MOST = 700
# A CHANGED RECORD IS HELD TO THE DOCKET. Whatever changes what the build
# reads of a bill -- a referral, a hearing, an amendment's new title -- is an
# event, and the docket is where events are written. A record that changed
# while its bill's docket is at rest -- no row new, cited, marked or reworded
# tonight, none entered in the LSR_ACTIVE_DAYS before the views were asked --
# or that gained a committee of referral in a chamber whose docket has no row
# for the bill, is not backed by the docket, and more than LSR_UNBACKED_MOST
# of those stop the night. Both GUESSES: no pair on this disk shows a record
# changing at all, so how long after its docket row a title or a flag follows
# is not known (two weeks is the allowance), nor how often a clerk corrects a
# record with no docket row (a handful). On 2 October 2026, out of session,
# 30 of the 1,387 bills had a docket row in the fortnight before: the other
# 1,357 are at rest, and a view that rewrites a column across the file meets
# this long before the session-day ceilings above.
LSR_ACTIVE_DAYS = timedelta(days=14)
LSR_UNBACKED_MOST = 5
# A FIRST REFERRAL AHEAD OF ITS DOCKET ROW is held apart from those, and named
# rather than stopped at a handful. A record whose one change is a committee
# of referral where it had none, in a chamber whose docket has no row of the
# bill yet, counted against the 5 above; and whether the General Court sets
# the code before it types the row is on no copy on this disk. Three bills
# hold a Senate committee today with no Senate docket row at all (HB 216, HB
# 129, HB 133), so the one can be there without the other; and the first
# Senate row of 148 bills was entered on one day (17 March 2026), of 292 in
# the House (1 December 2025; 448 in seven days). If the code comes first,
# each of those nights was 148 or 292 against 5. So up to twice the busiest
# day's pass, the first TOLD_MOST named -- and only with a code some
# installed record already holds in that column: an invented committee is
# still one of the 5. Not multiplied by SPAN: 646 records have no Senate
# committee, and a view that filled every one in must stop however old the
# installed files are. A GUESS that it is ever met at all.
LSR_ALONE_MOST = 600

# The roll calls. One installed roll call changed on the eleven pairs (the
# Senate's 49th of 2026, moved from SB 655 to SB 665, with its title), and no
# ballot in a column the build reads. The other correction on record, SB 331
# of 2018, is one tally and one senator's ballot. Twice the one of each: they
# were 5 and 10, GUESSES, which let five roll calls be refiled and ten tallies
# be changed by a ballot each.
ROLLCALLS_CHANGED_MOST = 2
BALLOTS_CHANGED_MOST = 2
# THE FOUR COUNTS were held to nothing changing, and a roll call's Yea and Nay
# ballots to its counts exactly. Both stopped a right night, and then every
# night after it, since the installed files do not move: the one correction of
# a tally on record (above), and a new roll call whose typed counts are not
# its ballots -- the Senate's are typed, and 14 of the 9,146 roll calls of 27
# years do not add up, two of them since 2015 (2017 S 104, 2018 S 55), every
# one but the House's first of 2000 by one ballot or two. The page's headline is the ballots
# counted (rollcall_parser.py), with the stated tally beside it where the two
# differ. So: an installed roll call's counts may move on
# ROLLCALLS_CHANGED_MOST of them, each named, and never away from its
# ballots -- one that added up and no longer does stops the night, which is
# what a tally changed alone is. And ROLLCALLS_CHANGED_MOST new roll calls
# may be up to ROLLCALL_ADRIFT_MOST ballots from their counts, each named;
# one further off, or with no ballots at all, stops.
ROLLCALL_ADRIFT_MOST = 2
# New roll calls in a night: the most taken in one day in 27 years is 71, both
# chambers (12 March 2020; 114 in any week). Times SPAN. A new one's number
# is no further past its chamber's highest installed than that many: the
# Senate's run 1 to N without a gap in every year since 2013, the House's with
# a handful.
ROLLCALLS_NEW_MOST = 142
# New roll calls on a "bill" no file knows: a question on the House's own
# rules is filed under HRULE64, and five were taken on 4 January 2023. Twice
# that; each is named.
ROLLCALL_STRANGERS_MOST = 10
# How far after the views were asked a new roll call may say it was taken.
ROLLCALL_AHEAD_SLACK = timedelta(days=1)

# The roster. Nobody's row changed on the eleven pairs, nor in the database's
# own view between 8 September and 2 October, and nobody joined or left.
# GUESSES, each above nothing and each named in what the night tells: who a
# member is -- name, chamber, county, district, party -- on two (it was 8,
# which let eight members' parties be changed and nobody told which); members
# joined, and members left, four each, and never more than the 2% the
# roster's count may move by; anything else read of a member, on 40.
ROSTER_TOLERANCE = 0.02
ROSTER_MOVED_MOST = 4
ROSTER_CHANGED_MOST = 2
ROSTER_TOUCHED_MOST = 40
# ... except another seat or e-mail address that reads as one (from 0: the
# sixth column, digits; the fifteenth, name@host). Those are named and not
# counted against the 40: every member's address moved to another domain in
# one night -- which no copy on this disk shows, and which the General Court
# would do in one night if it did -- stopped the fallback, and every night
# after. A column lost or moved along is not let by with it: a blank is not
# an address, what lands in the e-mail column of a row moved along is a ZIP
# code, and the address columns are still held to the 40.
ROSTER_SHAPED = {5: re.compile(r"\s*\d+\s*"),
                 14: re.compile(r"\s*[^@\s|]+@[^@\s|]+\.[^@\s|]+\s*")}

# The sponsors. No row of LsrSponsors.txt came or went on any pair (its rows
# changed order once). New rows in a night, times SPAN: the 202 bills made on
# 25 November 2025 carry 1,166 signed-off sponsors between them.
SPONSORS_NEW_MOST = 2400
# New rows on a bill whose docket began more than SPONSOR_LATE_DAYS before: a
# sponsor added to a bill long since introduced. And installed rows gone.
# GUESSES above nothing, all three, and each row is named: when a sponsor
# signs is on no stamp the views carry. It was 98% of the file kept and no
# ceiling on rows added, which let 170 rows go and 5,000 invented ones in.
SPONSOR_LATE_DAYS = timedelta(days=30)
SPONSORS_LATE_MOST = 5
SPONSORS_GONE_MOST = 5
# Of LsrsOnly.txt, the share of a sitting member's rows with NO bill number
# that may go: the 13 the view cannot give are exactly those, and a row with
# one has never gone.
SPONSORS_KEPT_LEAST = 0.98

# How many rows a count names in what the night tells (judge()'s "told"): as
# many as the largest ceiling that is a handful's, so that all of those are
# named. It was 20 under ceilings of 40, and the night's warning said "each
# named" of 35 rows when 20 were. A longer list names its first TOLD_MOST, and
# the warning says that it does.
TOLD_MOST = 50

# The pair --check is about, and what it found on it. preflight holds
# check_pair()'s answer to these, so a change to a mapping that moves one of
# them is a change somebody made on purpose.
PAIR_DUMP = "2026-09-08"
PAIR_EXPORT = "2026-09-06"
PAIR_MEASURED = {
    "Docket.txt": {"rows": 25279, "export": 25279, "same": 25279, "identical": False},
    "LSRs.txt": {"rows": 1387, "export": 1387, "same": 1387, "identical": True,
                 "senate_status_kept": 29},
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
    wide as the view. The file has no header.

    It is UTF-8 or it is a Problem. Read with every byte that would not
    decode replaced, as it was, a view written in another code page went
    through: fifteen titles, two members' names and 96 sponsors' rows were
    installed with U+FFFD where a no-break space or an é had been, and each
    count was under its ceiling. A byte-order mark is one too: fetch_day_db.py
    writes none, and one left on the first row's first field took that row
    out of its year."""
    cols = columns or VIEWS.get(name) or LOOKUPS[name]
    path = Path(folder) / f"{name}.psv"
    if not path.is_file():
        raise Problem(f"{path.as_posix()} is not there")
    out = []
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        raise Problem(f"{path.as_posix()} is not UTF-8 (byte {e.start:,} is "
                      f"0x{e.object[e.start]:02x}): it was written in another encoding, and a "
                      "character read wrong is a name or a title changed")
    if text.startswith(BOM):
        raise Problem(f"{path.as_posix()} begins with a byte-order mark, which fetch_day_db.py "
                      "does not write: it is not the file that left")
    for n, line in enumerate(io.StringIO(text, newline=None), 1):
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


def senate_status_kept(lines, installed):
    """(LSRs.txt's rebuilt lines with the installed file's Senate status code,
    {"kept": n, "blank": n}): for an LSR the installed file holds, its code
    there; for a new one, none. `kept` counts the rows whose code in the view
    was another, `blank` the new rows whose code in the view was not blank."""
    at = LSR_SENATE_STATUS
    have = {tuple(f[:2]): f[at] for f in (ln.split("|") for ln in installed) if len(f) > at}
    out, kept, blank = [], 0, 0
    for ln in lines:
        f = ln.split("|")
        if len(f) > at:
            mine = have.get(tuple(f[:2]))
            if mine is None:
                blank += bool(f[at].strip())
                mine = ""
            else:
                kept += mine != f[at]
            f[at] = mine
            ln = "|".join(f)
        out.append(ln)
    return out, {"kept": kept, "blank": blank}


def rebuild(views, installed, need_source=True):
    """({name: bytes} for all seven, facts) from the views in `views` and the
    files installed in `installed` -- or Problem, and nothing.

    facts: the years used, the rows of each file, how many rows took the
    installed file's place and how many are new, on how many bill records
    the installed Senate status code was kept over another in the view, and
    any session year the views hold beyond the installed files'."""
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
        if name == "LSRs.txt":
            lines, facts["senate_status"] = senate_status_kept(
                lines, export_lines(was[name], WIDTH[name]))
        bad = next((ln for ln in lines if ln.count("|") != WIDTH[name] - 1), None)
        if bad is not None:
            raise Problem(f"a rebuilt line of {name} has {bad.count('|') + 1} columns, not "
                          f"{WIDTH[name]}: {bad[:120]}")
        facts["rows"][name] = len(lines)
        out[name] = as_bytes(lines)
    return out, facts


# ---- the guards --------------------------------------------------------------

EXPORT_CLOCK = "%m/%d/%Y %I:%M:%S %p"


@functools.lru_cache(maxsize=None)
def _when(s):
    """An export's clock as a time, or None. Remembered: a night reads the
    docket's 25,000 entry times five times over."""
    try:
        return datetime.strptime(s.strip(), EXPORT_CLOCK)
    except ValueError:
        return None


def _newest(lines, col=2):
    best = None
    for ln in lines:
        f = ln.split("|")
        d = _when(f[col]) if len(f) > col else None
        if d is not None and (best is None or d > best):
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


def differences(rows, old):
    """{name: {"rows", "installed", "new", "gone"}} on the shared columns, of
    tonight's rows and the installed ones, each {name: [lines]}."""
    out = {}
    for name in DAY_FILES:
        new, was = rows[name], old[name]
        kept, fresh = (len(was), 0) if new == was else _kept(was, new, shared_columns(name))
        out[name] = {"rows": len(new), "installed": len(was), "new": fresh,
                     "gone": len(was) - kept}
    return out


# A journal or calendar citation at the end of a docket row, in every shape
# the term's 17,290 cited rows have: "HJ 3  P. 7", "SJ 1", "HC 10  P. 98",
# "SC 6", "SC 12A". None is anywhere but the end of its row.
CITATION = re.compile(r"\b(?:HJ|SJ|HC|SC)\s*\d+[A-Za-z]?(?:\s*,?\s*P\.?\s*\d+)?\s*$", re.I)
# A mark put before a docket row's words: ==CANCELLED==, ==ROOM CHANGE==.
MARK = re.compile(r"^\s*==[A-Z][A-Z ]*==")
# Text read in the wrong encoding. U+FFFD is what a byte that could not be
# read becomes; and UTF-8 read as Windows-1252 turns every character outside
# ASCII into two or three, the first of them one of these and the next from
# the block a continuation byte lands in: a no-break space becomes U+00C2 and a
# no-break space, and an e-acute U+00C3 U+00A9. The installed files hold neither (their
# 128 characters outside ASCII are no-break spaces, en dashes, an é and an è).
# As many of the second kind as the first one's byte asks for -- one after
# U+00C2 to U+00DF, two after U+00E0 to U+00EF, three after that: with one
# after any of them, a new docket row that read "Floor Amendment by Rep.
# Côté’s motion" -- an é before a curly quote -- was the wrong encoding, and
# the night stopped. No docket of fifteen terms holds an accented letter at
# all, so that row has not been written yet; a capital one before a quote or
# a no-break space still reads as wrong.
_SECOND = ("[\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013"
           "\u2014\u2018-\u201e\u2020-\u2022\u2026\u2030\u2039\u203a\u20ac\u2122]")
MOJIBAKE = re.compile(f"[\u00c2-\u00df]{_SECOND}|[\u00e0-\u00ef]{_SECOND}{{2}}"
                      f"|[\u00f0-\u00f4]{_SECOND}{{3}}")
# What a field never reads in an export: a database's word for nothing, or a
# bit that was not turned into 1 or 0. No field of the seven installed files
# is one of them.
NO_VALUE = re.compile(r"(?m)(?:^|\|)[ \t]*(?:NULL|null|None|True|False)[ \t]*(?=\||$)")
# ... a member's name aside, where it reads True or False (legislators.txt,
# from 0: last, first, middle): no bit lands in a name. The General Court's
# own table holds a representative True (PersonID 908, of Sandown, not
# sitting on 2 October 2026), and the night he is on the roster again was a
# night stopped, and every night after it. A name that reads NULL still stops.
NO_VALUE_NOT_IN = {"legislators.txt": (1, 2, 3)}
# What a ballot reads: fetch_rollcalls_db.VOTE_WORD's words. A code it does
# not know passes through as its own digit.
VOTE_WORDS = frozenset(RC.VOTE_WORD.values())
# What makes a row of each file the one it is, from 0: no two rows of a file
# share it (none does in any installed file; the docket is held apart, since
# three of its rows are there twice).
ONE_OF = {"LSRs.txt": ((0, 1), "bill records"), "legislators.txt": ((0,), "members"),
          "RollCallSummary.txt": ((0, 1, 2), "roll calls"),
          "RollCallHistory.txt": ((0, 1, 2, 3), "ballots"),
          "LsrSponsors.txt": ((0, 1, 3), "sponsors' rows (year, request, member)"),
          "LsrsOnly.txt": ((0, 1), "sponsors' rows (request, member)")}


def _cited(was, now):
    """Whether a docket row's words `now` are its words `was` with a citation
    written onto the end, or the one it had completed ("HJ 6" to "HJ 6  P.
    2"): what the journal's page does to a row. The row before its citation
    is on no copy on this disk; that it is the same words is read from the
    rows still waiting for one ("Ought to Pass: MA VV 03/05/2026" beside the
    same with "  HJ 6  P. 2"). A citation replaced by ANOTHER is a row
    reworded: 1,000 rows moved to "HJ 99 P. 999" passed as cited."""
    m = CITATION.search(now)
    if not m or now == was:
        return False
    head = now[:m.start()].rstrip()
    w = CITATION.search(was)
    if w is None:
        return was.rstrip() == head
    a, b = " ".join(w.group(0).split()), " ".join(m.group(0).split())
    return was[:w.start()].rstrip() == head and b.startswith(a + " ")


def _marked(was, now):
    """Whether a docket row's words `now` begin with a mark `was` does not."""
    m = MARK.match(now)
    w = MARK.match(was)
    return bool(m) and (w is None or w.group(0).strip() != m.group(0).strip())


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


def _asked(facts):
    """When the views were asked, by fetch_day_db.py's record, or None."""
    try:
        return datetime.fromisoformat(str((facts or {}).get("asked") or ""))
    except ValueError:
        return None


def _nights(facts):
    """How many nights old the installed files are, as the night says
    (nightly.nights_since); one, when nobody says."""
    n = (facts or {}).get("nights")
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 1 else 1


def _ceiling(most, nights):
    """A night's ceiling, for installed files `nights` nights old (SPAN)."""
    by = next((x for k, x in SPAN if nights <= k), SPAN[-1][1])
    return int(round(most * by))


class _Wider(str):
    """A stop on a ceiling that _ceiling() made: one that is wider the older
    the installed files are. A night it stops leaves those files where they
    were, so the next night's ceiling is wider and the same views may pass it
    with nobody deciding (1,631 docket rows: stopped at one night and at two,
    installed at three). Every other stop is on something that does not move
    until the installed files do. judge() counts these ("wider"), and the
    night's page says which kind stopped it."""


def _fields(ln, width):
    f = ln.split("|")
    return f + [""] * (width - len(f))


def _eg(text, most=150):
    """A row, or a sentence about one, short enough for a verdict."""
    text = " ".join(str(text).split())
    return text if len(text) <= most else text[:most - 3] + "..."


def _cut(text, most=240):
    """A sentence that shows a difference, cut short and not tidied."""
    return text if len(text) <= most else text[:most - 3] + "..."


def _differ(a, b, width=60):
    """"'was' now 'is'", each cut round the first place the two differ and
    neither tidied, so that what is shown is where they part: two titles cut
    at 40 characters before that printed as the same words."""
    at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    lo = max(0, at - width // 3)

    def cut(s):
        return ("..." if lo else "") + s[lo:lo + width] + ("..." if len(s) > lo + width else "")
    return (f"{cut(a)!r} now {cut(b)!r}"
            + (f" ({len(a)} characters, now {len(b)})" if len(a) != len(b) else ""))


def _name(rows):
    """Up to TOLD_MOST of `rows`, each cut short and none tidied, and how
    many more there are."""
    return [_cut(r) for r in rows[:TOLD_MOST]] + (
        [f"... and {len(rows) - TOLD_MOST:,} more"] if len(rows) > TOLD_MOST else [])


def _named(n):
    """How a warning says where `n` counted rows are named: all of them, or
    the first TOLD_MOST (_name)."""
    return (("each named" if n <= TOLD_MOST else f"the first {TOLD_MOST} named")
            + " in the night's verdict (day_files, told) and in its what-changed report")


def _hold_text(old, rows):
    """What no export holds, in any of the seven: a character read in the
    wrong encoding, a field that reads NULL or True. [stops]. Each is held to
    the installed file's own count, which is none."""
    stops = []
    for name in DAY_FILES:
        if rows[name] == old[name]:
            continue
        names = NO_VALUE_NOT_IN.get(name, ())

        def valued(ln, names=names):    # the row, without a name that honestly reads True
            return ln if not names else "|".join(
                "" if i in names and x.strip() in BIT else x for i, x in enumerate(ln.split("|")))

        def counted(lines):
            text = "\n".join(lines)
            return (text.count("\ufffd") + len(MOJIBAKE.findall(text)),
                    len(NO_VALUE.findall("\n".join(valued(ln) for ln in lines))))
        (was_bad, was_no), (bad, no) = counted(old[name]), counted(rows[name])
        if bad > was_bad:
            eg = next(ln for ln in rows[name] if "\ufffd" in ln or MOJIBAKE.search(ln))
            m = re.search("\ufffd", eg) or MOJIBAKE.search(eg)
            stops.append(f"{name}: {bad - was_bad:,} characters read in the wrong encoding, which "
                         f"the installed file has {'none' if not was_bad else f'{was_bad:,}'} of: "
                         f"{ascii(eg[max(0, m.start() - 40):m.start() + 20])}")
        if no > was_no:
            eg = next(ln for ln in rows[name] if NO_VALUE.search(valued(ln)))
            stops.append(f"{name}: {no - was_no:,} fields read NULL, None, True or False, which "
                         f"no field of an export does: {_eg(eg)}")
    return stops


def _hold_keys(old, rows):
    """No row twice: (stops, how many docket rows are there once more than a
    row is, what is named).

    A view joined to something it should not be returns a row once for each
    match, and the readers do not agree on which copy they keep: the guards
    here kept the last and rollcall_parser.py keeps the first, so a wrong
    roll call filed in front of the right one passed every guard and was
    published. A key more often tonight than once, or than the installed file
    has it, stops the night."""
    stops, told = [], {}
    for name, (cols, what) in ONE_OF.items():
        if rows[name] == old[name]:     # the installed file, row for row: as it was
            continue

        def key(ln, most=max(cols) + 1):
            f = ln.split("|", most)
            return tuple(f[i] if i < len(f) else "" for i in cols)
        was = collections.Counter(key(ln) for ln in old[name])
        now = collections.Counter(key(ln) for ln in rows[name])
        twice = sorted(k for k, n in now.items() if n > max(1, was.get(k, 0)))
        if twice:
            stops.append(f"{name}: {len(twice):,} {what} are there more than once: "
                         f"{' '.join(twice[0])}, {now[twice[0]]} times")

    def numbers(lines):
        return collections.Counter(b for b in (_fields(ln, 39)[10].strip().upper() for ln in lines)
                                   if b)
    was, now = numbers(old["LSRs.txt"]), numbers(rows["LSRs.txt"])
    twice = sorted(b for b, n in now.items() if n > max(1, was.get(b, 0)))
    if twice:
        stops.append(f"LSRs.txt: {len(twice):,} bill numbers are on more than one bill record: "
                     + ", ".join(twice[:6]))

    def primes(lines):
        return collections.Counter(tuple(f[:2]) for f in (_fields(ln, 5) for ln in lines)
                                   if f[4].strip() == "1")
    was, now = primes(old["LsrSponsors.txt"]), primes(rows["LsrSponsors.txt"])
    twice = sorted(k for k, n in now.items() if n > max(1, was.get(k, 0)))
    if twice:
        stops.append(f"LsrSponsors.txt: {len(twice):,} requests have more than one prime "
                     f"sponsor: {'-'.join(twice[0])}, {now[twice[0]]}")

    # The docket: a conference meeting's notice entered twice is two rows the
    # same (three pairs in the term), so a few are let be, and named.
    six = shared_columns("Docket.txt")
    was, now = collections.Counter(), collections.Counter()
    if rows["Docket.txt"] != old["Docket.txt"]:
        was.update(six(ln) for ln in old["Docket.txt"])
        now.update(six(ln) for ln in rows["Docket.txt"])
    twice = sorted((k for k, n in now.items() if n > max(1, was.get(k, 0))),
                   key=lambda k: (-now[k], k))
    extra = sum(now[k] - max(1, was.get(k, 0)) for k in twice)
    if extra > DOCKET_TWICE_MOST:
        stops.append(f"Docket.txt: {extra:,} rows are there once more than a row is, or than the "
                     f"installed file has them, more than {DOCKET_TWICE_MOST}: {_eg(twice[0])}")
    elif extra:
        told["Docket.txt: rows there more than once, and not so in the installed "
             "file"] = list(twice)
    return stops, extra, told


def _hold_docket(old, rows, records, asked=None, nights=1):
    """The docket, row by row: (stops, what was counted, what is named, the
    bills with a row new or changed tonight).

    A changed row is an installed row and a row of tonight's alike in year,
    request, entry time, bill and chamber and unlike in words -- the same
    pairing its place in the order is given by (ORDER_LOOSE): cited, when the
    words only gained a citation; marked, when they were given a mark and
    are otherwise the installed words; marked and reworded, when they are
    not (DOCKET_REMARKED_MOST); reworded otherwise. What is left of the
    installed rows is gone, and of
    tonight's, new. A new row must sit under a bill somebody knows, in one of
    the two chambers, with words, and carry an entry time that reads as one;
    no one day may bring more of them than a day has, nor the night more than
    its nights have; and a row entered long before the installed file's
    newest, or after the views were asked, is one of a few or the night
    stops."""
    stops, told = [], {}
    if rows == old:                     # the installed docket, row for row
        return stops, {"new": 0, "busiest_day": None, "late": 0, "ahead": 0, "cited": 0,
                       "marked": 0, "remarked": 0, "reworded": 0, "gone": 0}, told, set()
    gone, new = _apart(old, rows, shared_columns("Docket.txt"))
    loose = ORDER_LOOSE["Docket.txt"]
    spare = collections.defaultdict(list)
    for i, ln in enumerate(new):
        spare[loose(ln)].append(i)
    taken, cited, marked, remarked, reworded, vanished, rest = set(), [], [], [], [], [], []

    def unmarked(words):                # a row's words, without the mark before them
        return " ".join(MARK.sub("", words, 1).split())
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
            now = new[q.pop(0)]
            a, b = _fields(ln, 7)[5], _fields(now, 7)[5]
            (reworded if not _marked(a, b) else
             marked if unmarked(a) == unmarked(b) else remarked).append((ln, now))
        else:
            vanished.append(ln)
    fresh = [ln for i, ln in enumerate(new) if i not in taken]

    def bill(f, at):
        return (f[0].strip(), f[1].strip(), f[at].strip().upper())
    known, began = set(), {}
    for f in (_fields(ln, 7) for ln in old):
        known.add(bill(f, 3))
        d = _when(f[2])
        if d and d < began.get((f[0].strip(), f[1].strip()), datetime.max):
            began[(f[0].strip(), f[1].strip())] = d
    known |= {bill(f, 10) for f in (_fields(ln, 39) for ln in records)}
    newest = _newest(old)
    base = min(x for x in (newest, asked) if x) if (newest or asked) else None
    strangers, undated, shapeless, early, late, ahead, far = [], [], [], [], [], [], []
    days = collections.Counter()
    for ln in fresh:
        f = _fields(ln, 7)
        if bill(f, 3) not in known:
            strangers.append(ln)
        if f[4] not in ("H", "S") or not f[5].strip():
            shapeless.append(ln)
        d = _when(f[2])
        if d is None:
            undated.append(ln)
            continue
        days[d.date()] += 1
        if base and d < base - DOCKET_STAMP_SLACK:
            start = began.get((f[0].strip(), f[1].strip()))
            (late if f[4] == "S" and start and d >= start else early).append(ln)
        if asked and d > asked + DOCKET_AHEAD_SLACK:
            far.append(ln)
        elif asked and d > asked:
            ahead.append(ln)

    def six(ln):
        return "|".join(_fields(ln, 7)[:6])

    def first(lines):
        return _eg(six(lines[0]))
    if strangers:
        stops.append(f"Docket.txt: {len(strangers):,} new rows are under a bill that neither "
                     f"the installed docket nor LSRs.txt knows: {first(strangers)}")
    if shapeless:
        stops.append(f"Docket.txt: {len(shapeless):,} new rows have no words, or a chamber that "
                     f"is neither H nor S: {first(shapeless)}")
    if undated:
        stops.append(f"Docket.txt: {len(undated):,} new rows carry an entry time that does not "
                     f"read as one: {first(undated)}")
    if early:
        stops.append(f"Docket.txt: {len(early):,} new rows were entered more than "
                     f"{DOCKET_STAMP_SLACK.days} days before the installed file's newest "
                     f"({base:%Y-%m-%d %H:%M:%S}), and are not the Senate's late entries -- a "
                     f"House row, or one older than its bill's first: {first(early)}")
    if len(late) > DOCKET_LATE_MOST:
        stops.append(f"Docket.txt: {len(late):,} new Senate rows were entered more than "
                     f"{DOCKET_STAMP_SLACK.days} days before the installed file's newest "
                     f"({base:%Y-%m-%d %H:%M:%S}), more than the {DOCKET_LATE_MOST} the Senate "
                     f"enters late: {first(late)}")
    if far:
        stops.append(f"Docket.txt: {len(far):,} new rows are entered more than "
                     f"{DOCKET_AHEAD_SLACK.days} days after the views were asked "
                     f"({asked:%Y-%m-%d %H:%M:%S}): {first(far)}")
    if len(ahead) > DOCKET_AHEAD_MOST:
        stops.append(f"Docket.txt: {len(ahead):,} new rows are entered after the views were "
                     f"asked ({asked:%Y-%m-%d %H:%M:%S}), more than {DOCKET_AHEAD_MOST}: "
                     f"{first(ahead)}")
    busiest = max(days.items(), key=lambda x: (x[1], x[0])) if days else None
    in_all = _ceiling(DOCKET_NEW_A_DAY_MOST, nights)
    if busiest and busiest[1] > DOCKET_NEW_A_DAY_MOST:
        of_day = [ln for ln in fresh if (_when(_fields(ln, 7)[2]) or datetime.min).date()
                  == busiest[0]]
        stops.append(f"Docket.txt: {busiest[1]:,} new rows entered on {busiest[0]}, more than "
                     f"the {DOCKET_NEW_A_DAY_MOST:,} a day brings: {first(of_day)}")
    elif len(fresh) > in_all:
        stops.append(_Wider(
            f"Docket.txt: {len(fresh):,} new rows, more than the {in_all:,} that "
            f"{nights} night{'s bring' if nights != 1 else ' brings'}: {first(fresh)}"))
    most = _ceiling(DOCKET_CITED_MOST, nights)
    if len(cited) > most:
        stops.append(_Wider(f"Docket.txt: {len(cited):,} installed rows gained a journal "
                            f"citation, more than {most:,}: {first([cited[0][1]])}"))
    if len(marked) + len(remarked) > DOCKET_MARKED_MOST:
        stops.append(f"Docket.txt: {len(marked) + len(remarked):,} installed rows are marked in "
                     f"the database's, more than {DOCKET_MARKED_MOST:,}: "
                     f"{first([(marked + remarked)[0][1]])}")

    def turned(pair):
        was, now = pair
        return f"{'|'.join(_fields(was, 7)[:5])}|" + _differ(_fields(was, 7)[5], _fields(now, 7)[5])
    if len(remarked) > DOCKET_REMARKED_MOST:
        stops.append(f"Docket.txt: {len(remarked):,} installed rows are given a mark in the "
                     f"database's and other words after it, more than {DOCKET_REMARKED_MOST:,}: "
                     f"{turned(remarked[0])}")
    elif remarked:
        told["Docket.txt: installed rows given a mark, and other words after it"] = \
            list(turned(p) for p in remarked)
    if len(reworded) > DOCKET_REWORDED_MOST:
        stops.append(f"Docket.txt: {len(reworded):,} installed rows are reworded in the "
                     f"database's, more than {DOCKET_REWORDED_MOST:,}: {turned(reworded[0])}")
    elif reworded:
        told["Docket.txt: installed rows reworded"] = list(turned(p) for p in reworded)
    if len(vanished) > DOCKET_GONE_MOST:
        stops.append(f"Docket.txt: {len(vanished):,} installed rows are not in the database's, "
                     f"more than {DOCKET_GONE_MOST:,}: {first(vanished)}")
    elif vanished:
        told["Docket.txt: installed rows gone"] = list(six(ln) for ln in vanished)
    if late and len(late) <= DOCKET_LATE_MOST:
        told[f"Docket.txt: new Senate rows entered more than {DOCKET_STAMP_SLACK.days} days "
             "before the installed file's newest"] = list(six(ln) for ln in late)
    stirred = {(f[0].strip(), f[1].strip()) for f in (
        _fields(ln, 7) for ln in fresh + [now for _, now in cited + marked + remarked + reworded])}
    return stops, {"new": len(fresh),
                   "busiest_day": [busiest[0].isoformat(), busiest[1]] if busiest else None,
                   "late": len(late), "ahead": len(ahead), "cited": len(cited),
                   "marked": len(marked) + len(remarked), "remarked": len(remarked),
                   "reworded": len(reworded), "gone": len(vanished)}, told, stirred


def _hold_records(old, rows, docket=(), stirred=(), sponsors=(), asked=None, nights=1):
    """LSRs.txt, record by record, on the columns the build reads: (stops,
    what was counted, what is named). A column it does not read is counted
    and never judged: the two status codes are the only ones that have ever
    differed. `docket` is tonight's, and `stirred` its bills with a row new
    or changed tonight: a record that changed is held to them
    (LSR_ACTIVE_DAYS). `sponsors` is tonight's LsrSponsors.txt: a new record
    has a row there."""
    stops, told = [], {}
    was = {tuple(f[:2]): f for f in (_fields(ln, 39) for ln in old)}
    now = {tuple(f[:2]): f for f in (_fields(ln, 39) for ln in rows)}
    fresh = [k for k in now if k not in was]
    # Where each bill's docket stands tonight: its newest entry, its chambers.
    moved, chambers = {}, collections.defaultdict(set)
    for f in (_fields(ln, 7) for ln in docket):
        k = (f[0].strip(), f[1].strip())
        chambers[k].add(f[4])
        d = _when(f[2])
        if d and d > moved.get(k, datetime.min):
            moved[k] = d
    since = (asked or (max(moved.values()) if moved else datetime.max)) - LSR_ACTIVE_DAYS

    changed, rewritten, retitled, itself, unbacked, ahead = [], [], [], [], [], []
    unread = collections.Counter()
    # The committees of referral the installed records hold, a column each.
    codes = {i: {f[i].strip() for f in was.values()} - {""} for i in LSR_REFERRAL}
    for k, a in was.items():
        b = now.get(k)
        if b is None:
            continue
        cols = [i for i in range(39) if a[i] != b[i]]
        read = [i for i in cols if i in LSR_READ]
        for i in cols:
            if i not in LSR_READ:
                unread[i] += 1
        if not read:
            continue
        changed.append((k, read))
        if any(i in LSR_ITSELF for i in read):
            itself.append((k, [i for i in read if i in LSR_ITSELF]))
        if any(a[i].strip() and (i not in LSR_HEARING or not b[i].strip()) for i in read):
            rewritten.append((k, read))
        if 2 in read and a[2].strip() and b[2].strip():
            retitled.append((k, [2]))
        at_rest = k not in stirred and moved.get(k, datetime.min) < since
        alone = [i for i, body in LSR_REFERRAL.items()
                 if i in read and not a[i].strip() and body not in chambers[k]]
        # A first referral ahead of its docket row, and nothing else: held
        # apart (LSR_ALONE_MOST). With a code no installed record has, or
        # anything else changed while the bill's docket is at rest, it is
        # one of the handful.
        if alone and all(b[i].strip() in codes[i] for i in alone) and (
                not at_rest or len(alone) == len(read)):
            ahead.append((k, alone))
        elif at_rest or alone:
            unbacked.append((k, read))

    def said(found, most=2):
        k, cols = found
        a, b = was[k], now[k]
        return (f"{'-'.join(k)} {b[10] or a[10]}, "
                + "; ".join(f"{LSR_NAMES.get(i, f'column {i + 1}')} {_differ(a[i], b[i])}"
                            for i in cols[:most]))
    # A new record: with a title, a chamber and a bill number, as every
    # installed one has.
    bare = [k for k in fresh if not now[k][2].strip() or now[k][3] not in ("H", "S")
            or not now[k][10].strip()]
    most = _ceiling(LSR_NEW_MOST, nights)
    if bare:
        stops.append(f"LSRs.txt: {len(bare):,} new bill records have no title, no bill number, "
                     f"or a chamber that is neither H nor S: {'-'.join(bare[0])} "
                     f"{now[bare[0]][10]}")
    if len(fresh) > most:
        stops.append(_Wider(f"LSRs.txt: {len(fresh):,} new bill records, more than {most:,}: "
                            f"{'-'.join(fresh[0])} {now[fresh[0]][10]}"))
    signed = {(f[0].strip(), f[1].strip().zfill(4)) for f in (_fields(ln, 5) for ln in sponsors)}
    unsigned = [k for k in fresh if (k[0].strip(), k[1].strip().zfill(4)) not in signed]
    if len(unsigned) > LSR_UNSPONSORED_MOST:
        stops.append(f"LSRs.txt: {len(unsigned):,} new bill records have no sponsor in "
                     f"LsrSponsors.txt, more than {LSR_UNSPONSORED_MOST}: "
                     f"{'-'.join(unsigned[0])} {now[unsigned[0]][10]}")
    elif unsigned:
        told["LSRs.txt: new bill records with no sponsor in LsrSponsors.txt"] = [
            f"{'-'.join(k)} {now[k][10]}, {now[k][2]}" for k in unsigned]
    if itself:
        stops.append(f"LSRs.txt: {len(itself):,} installed bill records have another chamber or "
                     f"bill number in the database's, which a bill does not change: "
                     + _cut(said(itself[0])))
    if len(unbacked) > LSR_UNBACKED_MOST:
        stops.append(f"LSRs.txt: {len(unbacked):,} installed bill records changed where the "
                     f"build reads them with nothing in the docket to say why, more than "
                     f"{LSR_UNBACKED_MOST}: {_cut(said(unbacked[0]))} (no row of the bill's "
                     f"is new or changed tonight, nor entered in the {LSR_ACTIVE_DAYS.days} days "
                     "before; or it gained a committee in a chamber whose docket has no row of it)")
    elif unbacked:
        told["LSRs.txt: installed bill records changed with nothing in the docket to say why"] = \
            list(said(x, 4) for x in unbacked)
    if len(ahead) > LSR_ALONE_MOST:
        stops.append(f"LSRs.txt: {len(ahead):,} installed bill records gained a committee in a "
                     f"chamber whose docket has no row of the bill, more than {LSR_ALONE_MOST}: "
                     + _cut(said(ahead[0])))
    elif ahead:
        told["LSRs.txt: installed bill records that gained a committee in a chamber whose "
             "docket has no row of the bill yet"] = list(said(x) for x in ahead)
    for found, ceiling, what in (
            (retitled, LSR_RETITLED_MOST, "have another title"),
            (rewritten, LSR_REWRITTEN_MOST,
             "hold another value, or none, where the build reads one"),
            (changed, LSR_CHANGED_MOST, "changed in a column the build reads")):
        most = _ceiling(ceiling, nights)
        if len(found) > most:
            stops.append(_Wider(f"LSRs.txt: {len(found):,} installed bill records {what}, more "
                                f"than {most:,}: " + _cut(said(found[0]))))
            break
    else:
        # A title is what a page says a bill is, and a night may replace 40:
        # 53 bills with a docket row that fortnight were given another, and 55
        # more each with one new row, and nobody was told which.
        if retitled:
            told["LSRs.txt: installed bill records with another title"] = \
                list(said(x) for x in retitled)
    return stops, {"new": len(fresh), "unsponsored": len(unsigned), "changed": len(changed),
                   "rewritten": len(rewritten), "retitled": len(retitled),
                   "unbacked": len(unbacked), "ahead_of_docket": len(ahead),
                   "unread": {LSR_NAMES.get(i, f"column {i + 1}"): n
                              for i, n in sorted(unread.items())}}, told


def _hold_rollcalls(old_s, new_s, old_h, new_h, known=(), asked=None, nights=1):
    """The roll calls: (stops, what was counted, what is named). A vote does
    not un-happen, and its counts do not change: every installed roll call
    is there tonight with the four counts it had and no fewer ballots. And
    beyond the counts, what a page reads of a roll call -- when, on
    which bill, the question, the title -- and of a ballot -- whose, and which
    way -- is the clerk's to correct, one or two at a time, and never the
    file's to lose or to gain: an installed roll call has tonight the ballots
    it had, and no more. A new one is taken about now, numbered on from its
    chamber's last, on a bill somebody knows, and its ballots are its counts.
    `known` is the bill numbers the docket and the bill records hold."""
    stops, told = [], {}
    if new_s == old_s and new_h == old_h:       # both files as installed, row for row
        return stops, {"calls": 0, "counts": 0, "ballots": 0, "new": 0, "strangers": 0,
                       "unsummed": 0}, told

    def counts(lines):
        return {tuple(f[:3]): tuple(f[5:9]) for f in (ln.split("|") for ln in lines)
                if len(f) > 8}
    was, now = counts(old_s), counts(new_s)
    lost = sorted(k for k in was if k not in now)
    moved = sorted(k for k in was if k in now and was[k] != now[k])
    if lost:
        stops.append(f"{len(lost):,} roll calls installed are not in the database's: "
                     + ", ".join(" ".join(k) for k in lost[:6]))
    # A tally the clerk corrects, one or two; and never away from the ballots
    # (below): a roll call that added up and no longer does stops the night.
    if len(moved) > ROLLCALLS_CHANGED_MOST:
        stops.append(f"{len(moved):,} roll calls have other counts in the database, more than "
                     f"{ROLLCALLS_CHANGED_MOST}: "
                     + ", ".join(f"{' '.join(k)} {'-'.join(was[k])} now {'-'.join(now[k])}"
                                 for k in moved[:4]))
    elif moved:
        told["RollCallSummary.txt: installed roll calls with other counts (Yeas-Nays-Present-"
             "Absent)"] = list(f"{' '.join(k)} {'-'.join(was[k])} now {'-'.join(now[k])}"
                               for k in moved)

    def ballots(lines):
        return collections.Counter(tuple(ln.split("|", 3)[:3]) for ln in lines)
    was, now = ballots(old_h), ballots(new_h)
    fewer = sorted(k for k, n in was.items() if now.get(k, 0) < n)
    if fewer:
        stops.append(f"{len(fewer):,} roll calls have fewer ballots in the database: "
                     + ", ".join(f"{' '.join(k)} {was[k]} now {now.get(k, 0)}"
                                 for k in fewer[:4]))

    def keyed(lines, width, key):
        return {tuple(f[:key]): f for f in (_fields(ln, width) for ln in lines)}
    was_s, now_s = keyed(old_s, 15, 3), keyed(new_s, 15, 3)
    was_h, now_h = keyed(old_h, 8, 4), keyed(new_h, 8, 4)

    # The installed roll calls, as they read.
    calls = sorted(k for k, f in was_s.items() if k in now_s
                   and any(f[i] != now_s[k][i] for i in ROLLCALL_TOLD))

    def read(k):
        a, b = was_s[k], now_s[k]
        cols = zip(ROLLCALL_TOLD, ("time", "bill", "question", "title"))
        return f"{' '.join(k)} " + "; ".join(f"{what} {_differ(a[i], b[i])}"
                                              for i, what in cols if a[i] != b[i])
    if len(calls) > ROLLCALLS_CHANGED_MOST:
        stops.append(f"RollCallSummary.txt: {len(calls):,} installed roll calls read otherwise "
                     f"in the database's, more than {ROLLCALLS_CHANGED_MOST}: "
                     + _cut(read(calls[0])))
    elif calls:
        told["RollCallSummary.txt: installed roll calls that read otherwise"] = \
            list(read(k) for k in calls)

    # Their ballots: each as it was cast, and none added.
    cast = sorted(k for k, f in was_h.items()
                  if k not in now_h or any(f[i] != now_h[k][i] for i in BALLOT_CAST))

    def vote(k):
        a = was_h[k]
        return (f"{' '.join(k[:3])} member {k[3]} {'|'.join(a[i] for i in BALLOT_CAST)} now "
                + ("|".join(now_h[k][i] for i in BALLOT_CAST) if k in now_h else "not there"))
    if len(cast) > BALLOTS_CHANGED_MOST:
        stops.append(f"RollCallHistory.txt: {len(cast):,} installed ballots are cast otherwise "
                     f"in the database's, or by another member, more than "
                     f"{BALLOTS_CHANGED_MOST}: {vote(cast[0])}")
    elif cast:
        told["RollCallHistory.txt: installed ballots cast otherwise"] = list(vote(k) for k in cast)
    added = sorted(k for k in now_h if k not in was_h and k[:3] in was_s)
    if added:
        stops.append(f"RollCallHistory.txt: {len(added):,} ballots are on installed roll calls "
                     f"that did not have them: {' '.join(added[0][:3])} member {added[0][3]}")
    orphans = sorted(k for k in now_h if k[:3] not in now_s)
    if orphans:
        stops.append(f"RollCallHistory.txt: {len(orphans):,} ballots are on a roll call "
                     f"RollCallSummary.txt does not hold: {' '.join(orphans[0][:3])}")

    def unworded(ballots):
        return sorted(k for k, f in ballots.items() if f[6] not in VOTE_WORDS)
    odd = unworded(now_h)
    if len(odd) > len(unworded(was_h)):
        stops.append(f"RollCallHistory.txt: {len(odd):,} ballots are no vote the export "
                     f"writes: {' '.join(odd[0][:3])} member {odd[0][3]} reads "
                     f"{now_h[odd[0]][6]!r}")

    # A roll call's Yea and Nay ballots are its counts, as they were: an
    # installed one that added up still does. A new one may be a ballot or
    # two from its typed counts (ROLLCALL_ADRIFT_MOST), and is named.
    def adrift(summary, ballots):
        """{roll call: (Yea ballots, Nay ballots, how many ballots from its
        counts)} for each whose ballots are not its counts."""
        yn = collections.Counter((k[:3], f[6]) for k, f in ballots.items())
        out = {}
        for k, f in summary.items():
            yea, nay = yn[(k, "Yea")], yn[(k, "Nay")]
            if (str(yea), str(nay)) != (f[5].strip(), f[6].strip()):
                both = f[5].strip().isdigit() and f[6].strip().isdigit()
                out[k] = (yea, nay, abs(int(f[5]) - yea) + abs(int(f[6]) - nay)
                          if both and yea + nay else None)
        return out
    off = adrift(now_s, now_h)

    def unsummed(k):
        return (f"{' '.join(k)} says {now_s[k][5].strip()}-{now_s[k][6].strip()} and has "
                f"{off[k][0]} Yea and {off[k][1]} Nay ballots")
    near = sorted(k for k in off if k not in was_s and off[k][2] is not None
                  and off[k][2] <= ROLLCALL_ADRIFT_MOST)
    if len(near) > ROLLCALLS_CHANGED_MOST:
        near = []
    far = sorted(set(off) - set(adrift(was_s, was_h)) - set(near))
    if far:
        k = far[0]
        stops.append(f"{len(far):,} roll calls' Yea and Nay ballots are not their counts: "
                     + unsummed(k) + ("" if k in was_s else ", a new roll call"))
    if near:
        told["RollCallSummary.txt: new roll calls whose Yea and Nay ballots are not their "
             "counts"] = list(unsummed(k) for k in near)

    # The new ones.
    fresh = sorted(k for k in now_s if k not in was_s)
    most = _ceiling(ROLLCALLS_NEW_MOST, nights)
    if len(fresh) > most:
        stops.append(_Wider(f"RollCallSummary.txt: {len(fresh):,} new roll calls, more than "
                            f"{most:,}: " + " ".join(fresh[0])))
    top = collections.defaultdict(int)
    for k in was_s:
        if k[2].isdigit():
            top[k[:2]] = max(top[k[:2]], int(k[2]))
    astray, beyond, untimed, uncounted, unnamed, strangers = [], [], [], [], [], []
    for k in fresh:
        f = now_s[k]
        if not k[2].isdigit() or int(k[2]) <= 0 or k[1] not in ("H", "S"):
            astray.append(k)
        elif int(k[2]) > top[k[:2]] + most:     # past a run that is longer on a later night
            beyond.append(k)
        d = _when(f[3])
        if d is None or (asked and d > asked + ROLLCALL_AHEAD_SLACK):
            untimed.append(k)
        if not all(x.strip().isdigit() for x in f[5:9]):
            uncounted.append(k)
        if f[4].strip() and f[4].strip().upper() not in known:
            strangers.append(k)
    unnamed = sorted({k[:3] for k, f in now_h.items() if k[:3] not in was_s and not f[4].strip()})
    if astray or beyond:
        k = (astray + beyond)[0]
        stops.append((str if astray else _Wider)(
            f"RollCallSummary.txt: {len(astray) + len(beyond):,} new roll calls are numbered out "
            f"of their chamber's run, which stands at {top[k[:2]]}: {' '.join(k)}"))
    if untimed:
        k = untimed[0]
        stops.append(f"RollCallSummary.txt: {len(untimed):,} new roll calls were taken at no "
                     f"time that reads as one, or after the views were asked: {' '.join(k)} "
                     f"{now_s[k][3]!r}")
    if uncounted:
        k = uncounted[0]
        stops.append(f"RollCallSummary.txt: {len(uncounted):,} new roll calls have a count that "
                     f"is not a number: {' '.join(k)} {'-'.join(now_s[k][5:9])}")
    if unnamed:
        stops.append(f"RollCallHistory.txt: {len(unnamed):,} new roll calls have a ballot of a "
                     f"member the roster's view does not know: {' '.join(unnamed[0])}")
    if len(strangers) > ROLLCALL_STRANGERS_MOST:
        k = strangers[0]
        stops.append(f"RollCallSummary.txt: {len(strangers):,} new roll calls are on a bill "
                     f"that neither the docket nor LSRs.txt knows, more than "
                     f"{ROLLCALL_STRANGERS_MOST}: {' '.join(k)} {now_s[k][4]}")
    elif strangers:
        told["RollCallSummary.txt: new roll calls on a bill no file knows"] = \
            list(f"{' '.join(k)} {now_s[k][4]} {now_s[k][11]}" for k in strangers)
    return stops, {"calls": len(calls), "counts": len(moved), "ballots": len(cast),
                   "new": len(fresh), "strangers": len(strangers), "unsummed": len(near)}, told


# A NEW ROSTER THE WEBSITE NAMES TOO (5 October 2026). Organization Day, the
# first Wednesday of December, seats a new House -- about a third of it new --
# and from that day the database's roster is past every ceiling here, so
# every database night would stop until an export installed the new roster.
# The person decided that a database night may take a changed roster when
# tonight's Members.txt agrees: that file comes from the website's /downloads/,
# not the failing export, and has arrived whole on every failed night. Agrees
# means it names every member on the database's roster, by work e-mail or by
# last and first name, and at most ROSTER_MOVED_MOST people the roster does
# not (on 6 September two of 408). Then the members joined and left are
# named, not stopped on; a member's name, party or district changed is still
# held to its own ceiling.
def roster_named(rows, members):
    """(named, why): whether tonight's Members.txt names the roster `rows`
    (legislators.txt's lines, rebuilt from the database)."""
    if not members:
        return False, "no Members.txt arrived from the website tonight"
    text = members.decode("utf-8-sig", "replace") if isinstance(members, bytes) else members
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False, "tonight's Members.txt is empty"
    col = {n.strip().strip('"').lower(): i for i, n in enumerate(lines[0].split("\t"))}

    def get(f, name):
        i = col.get(name)
        v = f[i].strip() if i is not None and i < len(f) else ""
        return (v[1:-1] if len(v) > 1 and v[0] == v[-1] == '"' else v).strip().lower()
    mails, names = set(), set()
    for ln in lines[1:]:
        f = ln.split("\t")
        if get(f, "workemail"):
            mails.add(get(f, "workemail"))
        names.add((get(f, "lastname"), get(f, "firstname")))
    roster = [_fields(ln, 15) for ln in rows]
    missing = [f for f in roster if f[14].strip().lower() not in mails
               and (f[1].strip().lower(), f[2].strip().lower()) not in names]
    on_roster = {f[14].strip().lower() for f in roster} | \
        {(f[1].strip().lower(), f[2].strip().lower()) for f in roster}
    others = sum(1 for ln in lines[1:]
                 if get(ln.split("\t"), "workemail") not in on_roster
                 and (get(ln.split("\t"), "lastname"), get(ln.split("\t"), "firstname"))
                 not in on_roster)
    if missing:
        return False, (f"tonight's Members.txt does not name {len(missing):,} of the "
                       f"database's {len(roster):,} members")
    if others > ROSTER_MOVED_MOST:
        return False, (f"tonight's Members.txt names {others:,} people the database's roster "
                       f"does not, more than {ROSTER_MOVED_MOST}")
    return True, (f"tonight's Members.txt, from the website, names every one of the "
                  f"database's {len(roster):,} members")


def _hold_roster(old, rows, named=False):
    """The roster, member by member, on what the build reads of each: (stops,
    what was counted, what is named). `named`: tonight's Members.txt names
    the new roster (roster_named), and members joined and left are named
    rather than stopped on."""
    stops, told = [], {}
    was = {f[0]: f for f in (_fields(ln, 15) for ln in old)}
    now = {f[0]: f for f in (_fields(ln, 15) for ln in rows)}
    who = sorted(k for k, a in was.items()
                 if k in now and any(a[i] != now[k][i] for i in ROSTER_WHO))
    any_ = sorted(k for k, a in was.items()
                  if k in now and any(a[i] != now[k][i] for i in ROSTER_READ))
    # ... of whom, the members with nothing changed but a seat or an e-mail
    # address that still reads as one (ROSTER_SHAPED): named, and not counted.
    shaped = {k for k in any_ if k not in set(who) and all(
        i in ROSTER_SHAPED and ROSTER_SHAPED[i].fullmatch(now[k][i])
        for i in ROSTER_READ if was[k][i] != now[k][i])}
    touched = [k for k in any_ if k not in shaped]
    left = sorted(k for k in was if k not in now)
    joined = sorted(k for k in now if k not in was)

    def said(k, cols):
        a, b = was[k], now[k]
        return _eg(f"member {k}, " + "|".join(a[i] for i in cols) + " now "
                   + "|".join(b[i] for i in cols))

    def member(f):
        return f"member {f[0]}, {f[1]}|{f[2]}|{f[3]}|{f[4]}|{f[6]}|{f[7]}|{f[8]}"
    if len(who) > ROSTER_CHANGED_MOST:
        stops.append(f"legislators.txt: {len(who):,} installed members have another name, "
                     f"chamber, county, district or party in the database's, more than "
                     f"{ROSTER_CHANGED_MOST}: {said(who[0], ROSTER_WHO)}")
    elif len(touched) > ROSTER_TOUCHED_MOST:
        k = next((k for k in touched if k not in set(who)), touched[0])
        cols = [i for i in ROSTER_READ if was[k][i] != now[k][i]]
        stops.append(f"legislators.txt: {len(touched):,} installed members changed in a column "
                     f"the build reads, more than {ROSTER_TOUCHED_MOST}: {said(k, cols)} (a "
                     "member with only another seat or e-mail address, each still reading as "
                     "one, is not counted)")
    if who and len(who) <= ROSTER_CHANGED_MOST:
        told["legislators.txt: installed members with another name, chamber, county, district "
             "or party"] = list(said(k, ROSTER_WHO) for k in who)
    rest = [k for k in any_ if k not in set(who)]
    if rest and len(touched) <= ROSTER_TOUCHED_MOST:
        # Which columns, and not what they hold: an address is a person's.
        told["legislators.txt: installed members with another seat, address or e-mail"] = [
            f"member {k}, {was[k][1]}|{was[k][2]}: column "
            + ", ".join(str(i + 1) for i in ROSTER_READ if was[k][i] != now[k][i]) for k in rest]
    for found, side, what in ((left, was, "installed members not on the database's roster"),
                              (joined, now, "members on the database's roster and not the "
                                            "installed one")):
        if len(found) > ROSTER_MOVED_MOST and not named:
            stops.append(f"legislators.txt: {len(found):,} {what}, more than "
                         f"{ROSTER_MOVED_MOST}: {_eg(member(side[found[0]]))}")
        elif found:
            told[f"legislators.txt: {what}"] = list(member(side[k]) for k in found)
    nameless = sorted(k for k in joined if not now[k][1].strip() or now[k][4] not in ("H", "S"))
    if nameless:
        stops.append(f"legislators.txt: {len(nameless):,} new members have no last name, or a "
                     f"chamber that is neither H nor S: {_eg(member(now[nameless[0]]))}")
    return stops, {"who": len(who), "any": len(any_), "seat_or_mail": len(shaped),
                   "left": len(left), "joined": len(joined)}, told


def _hold_sponsors(old, rows, docket, asked=None, nights=1):
    """LsrSponsors.txt, row by row: (stops, what was counted, what is named).
    Its rows are the build's sponsors of a bill LsrsOnly.txt does not list,
    and the order of all of them. A row there last night is there tonight; a
    new one comes with its bill, or soon after it."""
    stops, told = [], {}
    if rows == old:                     # the installed file, row for row
        return stops, {"new": 0, "late": 0, "gone": 0}, told
    gone, new = _apart(old, rows, lambda ln: ln)
    began = {}
    for f in (_fields(ln, 7) for ln in docket):
        d = _when(f[2])
        k = (f[0].strip(), f[1].strip())
        if d and d < began.get(k, datetime.max):
            began[k] = d
    ref = asked or (max(began.values()) if began else None)
    late = []
    for ln in new:
        f = _fields(ln, 5)
        first = began.get((f[0].strip(), f[1].strip().zfill(4)))
        if ref and first and first < ref - SPONSOR_LATE_DAYS:
            late.append(ln)
    most = _ceiling(SPONSORS_NEW_MOST, nights)
    if len(new) > most:
        stops.append(_Wider(f"LsrSponsors.txt: {len(new):,} new rows, more than {most:,}: "
                            f"{_eg(new[0])}"))
    if len(late) > SPONSORS_LATE_MOST:
        stops.append(f"LsrSponsors.txt: {len(late):,} new rows are on a bill whose docket began "
                     f"more than {SPONSOR_LATE_DAYS.days} days before, more than "
                     f"{SPONSORS_LATE_MOST}: {_eg(late[0])} (year, request, place, member, prime)")
    elif late:
        told[f"LsrSponsors.txt: new rows on a bill whose docket began more than "
             f"{SPONSOR_LATE_DAYS.days} days before (year, request, place, member, prime)"] = \
            list(late)
    if len(gone) > SPONSORS_GONE_MOST:
        stops.append(f"LsrSponsors.txt: {len(gone):,} installed rows are not in the database's, "
                     f"more than {SPONSORS_GONE_MOST}: {_eg(gone[0])} (year, request, place, "
                     "member, prime)")
    elif gone:
        told["LsrSponsors.txt: installed rows gone (year, request, place, member, prime)"] = \
            list(gone)
    return stops, {"new": len(new), "late": len(late), "gone": len(gone)}, told


def judge(files, installed, facts=None):
    """{"stops": [...], "warnings": [...], "differences": {...}, "held": {...},
    "told": {...}}: tonight's rebuilt files against the installed ones. Any
    stop, and nothing is installed. `installed` is {name: bytes}, as
    installed_files() gives it (a file of either may be given as its rows,
    already split). `facts` is rebuild()'s, with when the views were asked,
    and "nights", how many nights old the installed files are.

    "held" is what each content guard counted, whether or not it fired.
    "told" is the rows behind every count that sits under a ceiling which is
    a guess, or a correction's: {what they are: [rows]}. A warning says how
    many and that they are named; the rows themselves are the record's own
    words, and go to the verdict and the what-changed report, never to the
    run's page."""
    stops, warnings, held, told = [], [], {}, {}
    asked, nights = _asked(facts), _nights(facts)
    held["nights"] = nights
    def lines(data, n):         # a file may be given as its rows, already split
        return data if isinstance(data, list) else export_lines(data, WIDTH[n])
    rows = {n: lines(files[n], n) for n in DAY_FILES}
    old = {n: lines(installed[n], n) for n in DAY_FILES}
    diff = differences(rows, old)

    for name in DAY_FILES:
        wrong = sum(1 for ln in rows[name] if ln.count("|") != WIDTH[name] - 1)
        if wrong:
            stops.append(f"{name}: {wrong:,} rebuilt lines do not have {WIDTH[name]} columns")
        if old[name] and not rows[name]:
            stops.append(f"{name}: the database gave no rows and the installed file has "
                         f"{len(old[name]):,}")
    stops += _hold_text(old, rows)
    said, twice, named = _hold_keys(old, rows)
    stops += said
    told.update(named)

    # The view is not behind the export.
    a, b = _newest(old["Docket.txt"]), _newest(rows["Docket.txt"])
    if a and b is None:
        stops.append("the database's docket has no dated entry")
    elif a and b < a:
        stops.append(f"the database's docket is behind: its newest entry is "
                     f"{b:%Y-%m-%d %H:%M:%S} and the installed file's is {a:%Y-%m-%d %H:%M:%S}")

    # The docket keeps its rows and its words, and its new rows are a day's.
    said, held["Docket.txt"], named, stirred = _hold_docket(
        old["Docket.txt"], rows["Docket.txt"], old["LSRs.txt"] + rows["LSRs.txt"], asked, nights)
    held["Docket.txt"]["twice"] = twice
    stops += said
    told.update(named)

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
    said, held["LSRs.txt"], named = _hold_records(
        old["LSRs.txt"], rows["LSRs.txt"], rows["Docket.txt"], stirred, rows["LsrSponsors.txt"],
        asked, nights)
    stops += said
    told.update(named)

    # Roll calls: a vote does not un-happen, and its counts do not change.
    known = {f[3].strip().upper() for f in (_fields(ln, 7) for ln in rows["Docket.txt"])}
    known |= {f[10].strip().upper() for f in (_fields(ln, 39) for ln in rows["LSRs.txt"])}
    said, held["roll calls"], named = _hold_rollcalls(
        old["RollCallSummary.txt"], rows["RollCallSummary.txt"],
        old["RollCallHistory.txt"], rows["RollCallHistory.txt"], known, asked, nights)
    stops += said
    told.update(named)

    # The roster: by count, by who is on it, and by what it says of them.
    def people(lines):
        return {ln.split("|")[0] for ln in lines}
    a, b = len(old["legislators.txt"]), len(rows["legislators.txt"])
    sitting = people(rows["legislators.txt"])
    left = people(old["legislators.txt"]) - sitting
    moved = (a and abs(b - a) > ROSTER_TOLERANCE * a) or (a and len(left) > ROSTER_TOLERANCE * a)
    agrees, how = roster_named(rows["legislators.txt"], (facts or {}).get("members")) \
        if moved or left or b != a else (False, "")
    if moved and agrees:
        warnings.append(f"the roster changed: {b:,} members against {a:,} installed, {len(left):,} "
                        f"of them gone; {how}, so it is taken")
    elif a and abs(b - a) > ROSTER_TOLERANCE * a:
        stops.append(f"the roster is {b:,} members against {a:,} installed, more than "
                     f"{ROSTER_TOLERANCE:.0%} apart" + (f" ({how})" if how else ""))
    elif a and len(left) > ROSTER_TOLERANCE * a:
        stops.append(f"{len(left):,} of the {a:,} members installed are not on the "
                     f"database's roster, more than {ROSTER_TOLERANCE:.0%}"
                     + (f" ({how})" if how else ""))
    if moved:
        held["roster_named"] = bool(agrees)
    said, held["legislators.txt"], named = _hold_roster(old["legislators.txt"],
                                                        rows["legislators.txt"], agrees)
    stops += said
    told.update(named)

    # Sponsors.
    said, held["LsrSponsors.txt"], named = _hold_sponsors(
        old["LsrSponsors.txt"], rows["LsrSponsors.txt"], rows["Docket.txt"], asked, nights)
    stops += said
    told.update(named)
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
    held["LsrsOnly.txt"] = {"gone_numbered": len(numbered), "gone_unnumbered": bare,
                            "new": diff["LsrsOnly.txt"]["new"]}
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

    # What sits under a ceiling and is somebody's name or a bill's words: how
    # many, and where each is named.
    for what, named in told.items():
        warnings.append(f"{what}: {len(named):,}, {_named(len(named))}")

    # A row entered while its view was being read (arrived_whole).
    for view, n in sorted(((facts or {}).get("entered") or {}).items()):
        warnings.append(f"{n:,} row{'s' if n != 1 else ''} more than the server had counted "
                        f"arrived from the database's {view} view: entered while it was "
                        "being read, and in tonight's files")

    # The session has not turned -- or, if it has, the night says so: in the
    # nightly's own words for a new term (5 October 2026), since that is what
    # a newer year in the views most often is, and the box is the answer.
    newer = (facts or {}).get("newer_years") or {}
    if newer:
        years = sorted({y for d in newer.values() for y in d})
        warnings.append("the database holds session year "
                        + ", ".join(years) + ", newer than the installed files': tonight's "
                        "files keep the installed files' years. A new term, or a new session "
                        "year? Only a run by hand with New term ticked takes one, from the "
                        "export, once the term being left is frozen")
    return {"stops": [str(s) for s in stops], "warnings": warnings, "differences": diff,
            "held": held, "told": {what: _name(named) for what, named in told.items()},
            "wider": sum(1 for s in stops if isinstance(s, _Wider))}


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
            out[name]["senate_status_kept"] = facts["senate_status"]["kept"]
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
    n = held.get("nights") or 1
    if n > 1:
        out.append(f"  the installed files are {n} nights old, and a night's ceilings are "
                   f"{next((x for k, x in SPAN if n <= k), SPAN[-1][1])} times a day's")
    d = held.get("Docket.txt")
    if d:
        day = d.get("busiest_day")
        out.append(f"  Docket.txt, row by row: {d['new']:,} new"
                   + (f", the most entered on one day {day[1]:,} ({day[0]})" if day else "")
                   + (f", {d['late']:,} of them Senate rows entered long before" if d.get("late")
                      else "")
                   + (f", {d['ahead']:,} entered after the views were asked" if d.get("ahead")
                      else "")
                   + (f", {d['twice']:,} there once more than a row is" if d.get("twice") else "")
                   + f"; of the installed rows {d['cited']:,} gained a citation, "
                     f"{d.get('marked', 0):,} a mark"
                   + (f" ({d['remarked']:,} of them with other words after it)"
                      if d.get("remarked") else "")
                   + f", {d['reworded']:,} reworded, {d['gone']:,} gone")
    d = held.get("LSRs.txt")
    if d:
        out.append(f"  LSRs.txt, on the columns the build reads: {d['new']:,} new records"
                   + (f", {d['unsponsored']:,} of them with no sponsor" if d.get("unsponsored")
                      else "") + "; of "
                   f"the installed {d['changed']:,} changed, {d['rewritten']:,} with a value "
                   f"replaced or lost, {d.get('retitled', 0):,} with another title, "
                   f"{d.get('unbacked', 0):,} with nothing in the docket to say why"
                   + (f", {d['ahead_of_docket']:,} with a first committee in a chamber whose "
                      "docket has no row of the bill yet" if d.get("ahead_of_docket") else "")
                   + ("; in columns it does not read: "
                      + ", ".join(f"{k} on {n:,}" for k, n in d["unread"].items())
                      if d.get("unread") else ""))
    d = held.get("roll calls")
    if d:
        out.append(f"  the roll calls: {d.get('new', 0):,} new"
                   + (f", {d['strangers']:,} of them on a bill no file knows"
                      if d.get("strangers") else "")
                   + (f", {d['unsummed']:,} of them a ballot or two from their counts"
                      if d.get("unsummed") else "")
                   + f"; of the installed {d['calls']:,} read otherwise, "
                   + (f"{d['counts']:,} have other counts, " if d.get("counts") else "")
                   + f"{d['ballots']:,} ballots cast otherwise")
    d = held.get("legislators.txt")
    if d:
        out.append(f"  the members: {d.get('joined', 0):,} joined, {d.get('left', 0):,} left; of "
                   f"the rest {d['who']:,} with another name, district or party, "
                   f"{d['any']:,} changed at all"
                   + (f" ({d['seat_or_mail']:,} of them in a seat or an e-mail address only)"
                      if d.get("seat_or_mail") else ""))
    d = held.get("LsrSponsors.txt")
    if d:
        out.append(f"  LsrSponsors.txt: {d['new']:,} new rows, {d['late']:,} of them on a bill "
                   f"long since introduced; {d['gone']:,} installed rows gone")
    d = held.get("LsrsOnly.txt")
    if d:
        out.append(f"  LsrsOnly.txt, rows of sitting members gone: {d['gone_numbered']:,} on a "
                   f"numbered bill, {d['gone_unnumbered']:,} with no bill number")
    return out


def told_said(told):
    """The rows a night names (judge()'s "told"), for a log or a report:
    [lines]. They are the General Court's words, and are not for the run's
    page."""
    out = []
    for what, rows in (told or {}).items():
        out.append(f"  named, {what}:")
        out += [f"      {r}" for r in rows]
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
    kept = facts.get("senate_status") or {}
    if kept.get("kept") or kept.get("blank"):
        lines.append(f"  LSRs.txt's Senate status code is the installed file's on "
                     f"{kept['kept']:,} records where the database's is another"
                     + (f", and blank on {kept['blank']:,} new ones" if kept.get("blank") else "")
                     + ": the view is known to have it wrong")
    lines += told_said(result.get("told"))
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
    ap.add_argument("--nights", type=int, default=1,
                    help="how many nights old the installed files are (default 1): a night's "
                         "ceilings are that many days' (SPAN)")
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
                  + (f", {g['senate_status_kept']:,} with the export's Senate status code "
                     "where the view's is another" if "senate_status_kept" in g else "")
                  + ("; byte-identical" if g["identical"] else "")
                  + ("" if same else f"   <-- was {want}"))
        for ln in report(result, facts)[len(DAY_FILES):]:
            print(ln)
        print("As measured on 1 and 2 October 2026." if ok else
              "NOT as measured on 1 and 2 October 2026: a mapping here, or the pair, has changed.")
        return 0 if ok and not result["stops"] else 1

    try:
        files, facts = rebuild(a.views, a.installed)
        facts["nights"] = a.nights
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
