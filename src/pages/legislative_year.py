#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-17.8
"""
The legislature's year: a two-year term as a timeline, with this term's dates
where the chambers' own calendars print them, and the usual pattern where
they do not.

    import legislative_year as LY
    LY.SLUG, LY.TITLE, LY.HOME_LINK     # the page's address and the home box's words
    LY.figures(today, root)             # the page's figures, for build_civics
    LY.verify(root, pdf=False)          # every cited date against the text on disk

    python3 src/pages/legislative_year.py           # the same, said; no network
    python3 src/pages/legislative_year.py --pdf     # and each pairing read off its PDF

WHAT WAS ASKED (the person, 17 October 2026). "There should be a diagram or
page explaining the schedule of the legislature with the various deadlines
like crossover and interim study season, which links to the homepage status
in some way so that folks understand when the legislature is in session and
the various deadlines around filing bills." It is a Learn topic, in
civics.TOPICS beside How a Bill Becomes Law, and the home page's status box
links to it. This file is its machinery and its dates; civics.BODY_YEAR is
its prose.

WHERE THE DATES COME FROM. Every date the page states as this term's is
printed in a House or Senate calendar or journal on this disk, named in DOCS,
and the page names the document under the date -- "House Calendar 1, January
2, 2026" -- linked to the General Court's own copy where calendar_documents
holds its address. Two kinds of row are fixed by rule rather than printed:
Organization Day, the first Wednesday of December, and a session's opening
day, the first Wednesday after the first Tuesday of January. Both rules are
quoted in a calendar on disk (Part II, Article 3), so each such date is
computed from its rule and checked against it. One row, the 2026 general
election, is printed in no document on this disk: it is the day
corrections/status/status.txt names (the person's file, read and never
written), and the page cites the session status for it rather than a
document. If the status file stops naming it, the row loses its date and
says when the election usually falls.

THE TEXT BESIDE A PDF CANNOT PAIR A DATE WITH ITS DEADLINE. The House prints
its deadlines in two columns, and the .txt beside the PDF loses the pairing:
in every 2026 House calendar on disk the text puts "CROSSOVER" beside May 7
or May 14, and the PDF, read by word position, puts it beside March 26 --
the day both chambers sat to finish their own bills (House Journal 9 and
Senate Journal 7 are both of March 26). So the rows below were read off each
PDF's layout on 17 October 2026, a row being the words at one height, and
verify() holds them to the documents in two ways: the text on disk must
print the date and the words, which catches a mistyped date or the wrong
document; and with --pdf, where pdfplumber and the PDFs are on this disk,
the words must stand in the date's own block of rows, which catches a
pairing. The night holds the text but not the PDFs, so it checks the first.

WHEN THE TERM TURNS OVER (18 October 2026). TERMS holds the 2025-2026 term.
On 2 December 2026 the next one begins, and its deadlines will be printed in
calendars this disk does not hold yet. A term TERMS does not hold is drawn
from skeleton(): the four days the constitution fixes -- the Organization
Day that begins it, each session's opening day and the Organization Day
that ends it -- computed by their rules and cited to the calendars that
quote them, and every other landmark as it usually falls, undated, from
PATTERN. So the page is always the term the day falls in, the turn and the
turn of the year need nothing done to this file, and the build prints a line
saying the current term's printed deadlines are not entered. Entering them in
TERMS when the chambers' calendars print them makes the page fuller, not
right. (Until 18 October the page went on showing 2025-2026's dates after
the turn, saying whose they were, and from 15 January 2027 its Coming Next
had nothing in it.)
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import html
import re
from collections import namedtuple
from datetime import date, timedelta

import i18n as I

# THE PAGE'S ADDRESS AND NAME, in one place: civics.TOPICS gives the topic
# this slug, and build_pages' status box links to it.
SLUG = "legislative-year"
TITLE = "NH Legislative Schedule"   # the person, 22 October 2026, as the home box says it
HREF = f"learn/{SLUG}.html"
# The words of the home status box's link, alone (the person, 22 October
# 2026: "just say 'NH Legislature Schedule'"; and 25 October 2026: "NH
# Legislature Schedule should be NH Legislative Schedule").
HOME_LINK = "NH Legislative Schedule"
# The timeline's You Are Here, the anchor the page's own links go to.
HERE_ID = "now"

# ---------------------------------------------------------------------------
# THE DOCUMENTS CITED. key: (set, the date it prints, its number, the text
# beside its PDF, the PDF page its deadline list starts on, 0 for a notice).
# The set is calendar_documents' -- "hc" a House calendar, "sc" a Senate
# calendar, "sj" a Senate journal -- and with the date and the number it
# finds the document's address in the General Court's list. "status" is the
# person's own file, cited as the session status rather than as a document.
# ---------------------------------------------------------------------------
Doc = namedtuple("Doc", "set day number path page")
DOCS = {
    "hc30-2024": Doc("hc", "2024-08-30", 30, "calendars/2024/HC030.txt", 2),
    "hc41-2024": Doc("hc", "2024-11-15", 41, "calendars/2024/HC041.txt", 2),
    "hc1-2025": Doc("hc", "2024-11-26", 1, "calendars/2025/HC001.txt", 0),
    "sc1-2025": Doc("sc", "2024-12-05", 1, "calendars_senate/2025/SC001.txt", 5),
    "sj2-2025": Doc("sj", "2025-01-08", 2,
                    "journals_senate/2025/SJ 02 January 8, 2025 Convening Day.txt", 0),
    "hc7-2025": Doc("hc", "2025-01-10", 7, "calendars/2025/HC007.txt", 2),
    "hc30-2025": Doc("hc", "2025-06-20", 30, "calendars/2025/HC030.txt", 2),
    "sc28-2025": Doc("sc", "2025-06-26", 28, "calendars_senate/2025/SC028.txt", 5),
    "sc35-2025": Doc("sc", "2025-09-18", 35, "calendars_senate/2025/SC035.txt", 0),
    "hc40-2025": Doc("hc", "2025-09-26", 40, "calendars/2025/HC040.txt", 0),
    "hc1-2026": Doc("hc", "2026-01-02", 1, "calendars/2026/HC001.txt", 2),
    "sc1-2026": Doc("sc", "2026-01-08", 1, "calendars_senate/2026/SC001.txt", 14),
    "sc27-2026": Doc("sc", "2026-08-06", 27, "calendars_senate/2026/SC027.txt", 0),
    "hc30-2026": Doc("hc", "2026-08-14", 30, "calendars/2026/HC030.txt", 0),
    "sc29-2026": Doc("sc", "2026-09-03", 29, "calendars_senate/2026/SC029.txt", 8),
    "status": Doc("status", "", 0, "corrections/status/status.txt", 0),
}
ONE = {"hc": "House Calendar", "sc": "Senate Calendar", "hj": "House Journal",
       "sj": "Senate Journal"}

# ---------------------------------------------------------------------------
# THE TERM, SEASON BY SEASON. A step is one row of the timeline:
#
#   day    the date, ISO, or "" for a step the record gives no one date for
#   until  the last day of a span ("Sep 15-19"), or ""
#   who    "H", "S" or "HS": whose deadline it is ("" for the election)
#   name   what it is, in a few words
#   what   one sentence, for a reader who has never heard of it
#   cites  ((doc, day, words), ...): each date the step states, with the
#          words its document prints beside that date
#   key    one of the term's landmarks: drawn heavier, and the kind of step
#          Where Things Stand names as the last thing to have happened
#   subs   ((day, who, words, ((doc, words), ...)), ...): the deadlines a
#          step gathers, each with its own date and source
#   when   for a step with no date, when it usually falls; for a dated one,
#          what to say instead if its source stops printing it
#   rule   "org" or "open": a date fixed by rule, computed and checked
# ---------------------------------------------------------------------------
Step = namedtuple("Step", "day until who name what cites key subs when rule")
Step.__new__.__defaults__ = ("", "", "", "", "", (), False, (), "", "")
# A season: its name, when it falls in words, the day it starts (it ends the
# day before the next starts), what Where Things Stand says while the day is
# in it, and its steps.
Season = namedtuple("Season", "name when start stands steps")

GOVERNOR = ("Each bill both chambers passed goes to the Governor, who signs it, vetoes it, "
            "or leaves it to become law without a signature.")

TERMS = {
    "2025-2026": [
        Season("The Election", "Fall 2024", "2024-09-01",
               "The {term} term has not begun: its members are being elected.", [
            Step("2024-09-03", "2024-09-13", "H", "House members running again may file bill requests",
                 "A request for a bill is a Legislative Service Request, or LSR. Members seeking "
                 "re-election may file theirs before the election.",
                 (("hc30-2024", "2024-09-03", "First day for incumbents running for re-election to file LSRs"),
                  ("hc30-2024", "2024-09-13", "Last day prior to the General Election for incumbents running"))),
            Step("2024-11-05", "", "", "General election",
                 "Voters choose all 400 representatives and 24 senators for the two-year term.",
                 (("hc1-2025", "2024-11-05", "biennial election held November 5, 2024"),), True),
            Step("2024-11-06", "2024-11-22", "H", "Bill requests open to every representative",
                 "Filing opens to all members the day after the election and closes in late November.",
                 (("hc30-2024", "2024-11-06", "First day for all Representatives to file LSRs"),
                  ("hc41-2024", "2024-11-22", "Last day to file LSRs with complete information"))),
        ]),
        Season("The First Session", "December 2024 to June 2025", "2024-12-04",
               "In session: the {y1} session.", [
            Step("2024-12-04", "", "HS", "Organization Day",
                 "The new members are sworn in, the House elects its Speaker and the Senate its "
                 "President, and the term begins.",
                 (("hc1-2025", "2024-12-04", "Organize on the first Wednesday in December (December 4, 2024)"),),
                 True, rule="org"),
            Step("2024-12-11", "", "S", "Last day to request a Senate bill",
                 "Senators' requests must reach the Office of Legislative Services, which drafts "
                 "the bills, by this day.",
                 (("sc1-2025", "2024-12-11", "Deadline for the Office of Legislative Services to accept drafting"),)),
            Step("2025-01-02", "", "H", "House sponsors sign off",
                 "Each sponsor approves the drafted text of their bill before it is introduced.",
                 (("hc41-2024", "2025-01-02", "Last day to sign-off on all LSRs"),)),
            Step("2025-01-08", "", "HS", "The session opens",
                 "Convening day: the chambers begin taking up the new bills.",
                 (("sj2-2025", "2025-01-08", "CONVENING DAY - JANUARY 8, 2025"),), True, rule="open"),
            Step("2025-01-24", "", "H", "Last day to introduce House bills",
                 "A bill is introduced when it is read in and sent to a committee.",
                 (("hc7-2025", "2025-01-24", "Last day to introduce House Bills"),)),
            Step("2025-03-06", "2025-04-03", "HS", "Committee deadlines, first chamber",
                 "Committees report on each bill, and the chamber votes on the report a week "
                 "later, in steps. Bills going on to a second committee go first.",
                 subs=(("2025-03-06", "H", "Report House bills going to a second committee",
                        (("hc7-2025", "Last day to report HBs going to a second committee"),)),
                       ("2025-03-06", "S", "Senate committees act on Senate bills with a fiscal impact",
                        (("sc1-2025", "Deadline for Policy Committees to ACT on all Senate bills with a"),)),
                       ("2025-03-13", "H", "The House acts on those bills",
                        (("hc7-2025", "Last day to act on HBs going to a second committee"),)),
                       ("2025-03-20", "H", "Report the other House bills, except budget bills",
                        (("hc7-2025", "Last day to report all HBs not in a second committee"),)),
                       ("2025-03-27", "H", "The House acts on those bills",
                        (("hc7-2025", "Last day to act on HBs not in a second committee"),)),
                       ("2025-04-03", "H", "Report every remaining House bill, and the list of those retained",
                        (("hc7-2025", "Last day to report list of retained HBs"),)))),
            Step("2025-03-27", "", "S", "Crossover in the Senate",
                 "The last day for the Senate to act on its own bills. Those it passes go to the House.",
                 (("sc1-2025", "2025-03-27", "Deadline to ACT on all Senate bills"),), True),
            Step("2025-04-10", "", "H", "Crossover in the House",
                 "The last day for the House to act on its own bills. Those it passes go to the "
                 "Senate; those a committee retained wait for the second year.",
                 (("hc7-2025", "2025-04-10", "CROSSOVER Last day to act on all bills"),), True),
            Step("2025-05-08", "2025-05-29", "HS", "Committee deadlines, second chamber",
                 "The same steps again, for the bills that crossed.",
                 subs=(("2025-05-08", "H", "Report Senate bills going to a second committee",
                        (("hc7-2025", "Last day to report Senate Bills going to a second committee"),)),
                       ("2025-05-15", "H", "The House acts on those bills",
                        (("hc7-2025", "Last day to act on SBs going to a second committee"),)),
                       ("2025-05-15", "S", "Senate committees act on House bills with a fiscal impact",
                        (("sc1-2025", "Deadline for Policy Committees to ACT on all House bills with a"),)),
                       ("2025-05-29", "H", "Report every remaining Senate bill",
                        (("hc7-2025", "Last day to report all remaining SBs"),)))),
            Step("2025-06-05", "", "HS", "Last day to act on the other chamber's bills",
                 "Each chamber's last vote on the bills that crossed to it.",
                 (("hc7-2025", "2025-06-05", "Last day to act on SBs"),
                  ("sc1-2025", "2025-06-05", "Deadline to ACT on all House bills"))),
            Step("2025-06-12", "2025-06-19", "HS", "Committees of conference",
                 "Where one chamber will not accept the other's changes to a bill, members of "
                 "both try to write a version each will pass.",
                 subs=(("2025-06-12", "HS", "Last day to form committees of conference",
                        (("hc7-2025", "Last day to form Committees of Conference"),
                         ("sc1-2025", "Deadline to FORM Committees of Conference"))),
                       ("2025-06-19", "HS", "Last day to sign their reports",
                        (("hc7-2025", "Last day to sign Committee of Conference reports"),
                         ("sc1-2025", "Deadline to SIGN Committee of Conference Reports"))))),
            Step("2025-06-26", "", "HS", "Last day to act on committee of conference reports",
                 "Both chambers vote on the conference versions. It is the session's last deadline.",
                 (("hc7-2025", "2025-06-26", "Last day to act on Committee of Conference reports"),
                  ("sc1-2025", "2025-06-26", "Deadline to ACT on Committee of Conference Reports")), True),
        ]),
        Season("Between the Sessions", "Summer and fall 2025", "2025-06-27",
               "Between sessions. The {y2} session opens in January.", [
            Step("", "", "", "Bills go to the Governor", GOVERNOR, when="summer"),
            Step("2025-09-03", "2025-09-12", "S", "Senate bill requests for 2026",
                 "The window for senators' requests for the second session's bills.",
                 (("sc28-2025", "2025-09-03", "First Day to FILE legislation for 2026 Senate Session"),
                  ("sc28-2025", "2025-09-12", "Deadline for the Office of Legislative Services to accept drafting"))),
            Step("2025-09-15", "2025-09-19", "H", "House bill requests for 2026",
                 "The window for representatives' requests for the second session's bills.",
                 (("hc30-2025", "2025-09-15", "First Day to file LSRs for 2026 Session"),
                  ("hc30-2025", "2025-09-19", "Last Day to file LSRs for 2026 Session"))),
            Step("2025-10-23", "", "S", "Veto day in the Senate",
                 "The Senate meets to take up the Governor's vetoes.",
                 (("sc35-2025", "2025-10-23",
                   "SENATE WILL MEET IN SESSION FOR VETO DAY ON THURSDAY, OCTOBER 23, 2025"),), True),
            Step("2025-11-21", "", "H", "Retained bills reported",
                 "House committees report the bills they kept over the fall, for a vote in the "
                 "second session. It is also the House sponsors' last day to sign off on "
                 "2026's requests.",
                 (("hc30-2025", "2025-11-21", "Last Day to report all retained bills"),)),
            Step("2025-12-17", "", "H", "Veto day in the House",
                 "The House meets to take up the Governor's vetoes.",
                 (("hc40-2025", "2025-12-17", "Veto Day will be on Wednesday, December 17, 2025"),), True),
        ]),
        Season("The Second Session", "January to June 2026", "2026-01-07",
               "In session: the {y2} session.", [
            Step("2026-01-07", "", "HS", "The session opens",
                 "The second session's first day.",
                 (("hc1-2026", "2026-01-07", "The House will meet on Wednesday, January 7, 2026"),),
                 True, rule="open"),
            Step("2026-01-08", "", "H", "Last day to introduce House bills",
                 "The second year's new House bills are introduced and sent to committees.",
                 (("hc1-2026", "2026-01-08", "Last day to introduce House Bills"),)),
            Step("2026-02-12", "2026-03-19", "HS", "Committee deadlines, first chamber",
                 "Committees report on each bill, and the chamber votes on the report a week "
                 "later, in steps. Bills going on to a second committee go first.",
                 subs=(("2026-02-12", "H", "Report House bills going to a second committee",
                        (("hc1-2026", "Last day to report House Bills going to a second committee"),)),
                       ("2026-02-19", "H", "The House acts on those bills",
                        (("hc1-2026", "Last day to act on House Bills going to a second committee"),)),
                       ("2026-03-05", "H", "Report the other House bills",
                        (("hc1-2026", "Last day to report House Bills not in a second committee"),)),
                       ("2026-03-05", "S", "Senate committees act on Senate bills with a fiscal impact",
                        (("sc1-2026", "Deadline for Policy Committees to ACT on all Senate bills with a"),)),
                       ("2026-03-12", "H", "The House acts on those bills",
                        (("hc1-2026", "Last day to act on House Bills not in a second committee"),)),
                       ("2026-03-19", "H", "Report every House bill",
                        (("hc1-2026", "Last day to report all House Bills"),)))),
            Step("2026-03-26", "", "HS", "Crossover",
                 "The last day for each chamber to act on its own bills. What passes goes to "
                 "the other chamber.",
                 (("hc1-2026", "2026-03-26", "Last day to act on all House Bills"),
                  ("sc1-2026", "2026-03-26", "Deadline to ACT on all Senate bills")), True),
            Step("2026-04-16", "2026-05-07", "HS", "Committee deadlines, second chamber",
                 "The same steps again, for the bills that crossed.",
                 subs=(("2026-04-16", "H", "Report Senate bills going to a second committee",
                        (("hc1-2026", "Last day to report Senate Bills going to a second committee"),)),
                       ("2026-04-23", "H", "The House acts on those bills",
                        (("hc1-2026", "Last day to act on Senate Bills going to a second committee"),)),
                       ("2026-04-30", "S", "Senate committees act on House bills with a fiscal impact",
                        (("sc1-2026", "Deadline for Policy Committees to ACT on all House bills with a"),)),
                       ("2026-05-07", "H", "Report every Senate bill",
                        (("hc1-2026", "Last day to report all Senate Bills"),)))),
            Step("2026-05-14", "", "HS", "Last day to act on the other chamber's bills",
                 "Each chamber's last vote on the bills that crossed to it.",
                 (("hc1-2026", "2026-05-14", "Last day to act on all Senate Bills"),
                  ("sc1-2026", "2026-05-14", "Deadline to ACT on all House bills"))),
            Step("2026-05-21", "2026-05-28", "HS", "Committees of conference",
                 "Where one chamber will not accept the other's changes to a bill, members of "
                 "both try to write a version each will pass.",
                 subs=(("2026-05-21", "HS", "Last day to form committees of conference",
                        (("hc1-2026", "Last day to form committee of conference"),
                         ("sc1-2026", "Deadline to FORM Committees of Conference"))),
                       ("2026-05-28", "HS", "Last day to sign their reports",
                        (("hc1-2026", "Last day to sign committee of conference reports"),
                         ("sc1-2026", "Deadline to SIGN Committee of Conference Reports"))))),
            Step("2026-06-04", "", "HS", "Last day to act on committee of conference reports",
                 "Both chambers vote on the conference versions. It is the session's last deadline.",
                 (("hc1-2026", "2026-06-04", "Last day to act on committee of conference reports"),
                  ("sc1-2026", "2026-06-04", "Deadline to ACT on Committee of Conference Reports")), True),
        ]),
        Season("After the Session", "Summer and fall 2026", "2026-06-05",
               "Out of session until the new legislature takes office on Organization Day, "
               "December 2.", [
            Step("", "", "", "Bills go to the Governor", GOVERNOR, when="summer"),
            Step("2026-08-19", "", "HS", "Veto day",
                 "Both chambers meet to take up the Governor's vetoes. Overriding one takes two "
                 "thirds of each chamber.",
                 (("hc30-2026", "2026-08-19", "The House will meet on Wednesday, August 19th"),
                  ("sc27-2026", "2026-08-19",
                   "SENATE WILL MEET IN SESSION FOR VETO DAY ON WEDNESDAY, AUGUST 19, 2026")), True),
            Step("2026-09-01", "2026-09-11", "H", "House members running again may file bill requests",
                 "The first requests for the next term's bills.",
                 (("hc1-2026", "2026-09-01", "First day for incumbents running for re-election to file LSRs"),
                  ("hc1-2026", "2026-09-11", "Last day prior to the General Election for incumbents running"))),
            Step("2026-09-21", "2026-09-25", "S", "Senators running again may file bill requests",
                 "The Senate's window for the same.",
                 (("sc29-2026", "2026-09-21", "First day for incumbents seeking re-election to file Legislative"),
                  ("sc29-2026", "2026-09-25", "Last day for incumbents seeking re-election to file Legislative"))),
            Step("", "", "HS", "Interim study",
                 "Committees study the subjects of the bills sent to interim study. The bills "
                 "themselves go no further; a report may recommend a new bill next term.",
                 when="summer and fall"),
            Step("2026-10-23", "", "H", "Interim study reports due",
                 "The last day for House committees to file their reports on the bills sent to "
                 "interim study.",
                 (("hc1-2026", "2026-10-23", "Last day to file 2026 Interim Study reports"),), True),
            # BY LAW, NOT BY THE STATUS FILE (23 October 2026). This row cited a
            # sentence of corrections/status/status.txt, and when the person
            # had that sentence cut on 22 October the row failed its check and
            # the election fell out of "Coming up". No calendar of the term
            # prints the day -- the next term's first House calendar does, as
            # HC 1 of 2025 did for 2024 -- so it is dated by its rule, RSA
            # 653:7, as Organization Day is by Part II, Article 3.
            Step("2026-11-03", "", "", "General election",
                 "Voters choose all 400 representatives and 24 senators for the next term.",
                 (("hc1-2026", "2026-11-03", "Last day prior to the General Election for incumbents running"),),
                 True, rule="election"),
            Step("2026-11-04", "", "HS", "Bill requests open to every member",
                 "Filing opens to all members the day after the election.",
                 (("hc1-2026", "2026-11-04", "First day for all Representatives to file LSRs"),
                  ("sc29-2026", "2026-11-04", "First day for Senators to file Legislative Service Requests"))),
            Step("2026-11-18", "", "HS", "Last day to file bill requests",
                 "Representatives' last day to file requests for 2027's bills, and the last day "
                 "for senators' drafting requests.",
                 (("hc1-2026", "2026-11-18", "Last day to file LSRs with complete information"),
                  ("sc29-2026", "2026-11-18",
                   "Last day for the Office Legislative Services to accept drafting"))),
        ]),
        Season("The Next Term Begins", "December 2026 to January 2027", "2026-12-02",
               "The {next} term has begun. Its first session opens in January.", [
            Step("2026-12-02", "", "HS", "Organization Day",
                 "The members elected in November are sworn in, and the {next} term begins.",
                 (("hc1-2025", "2026-12-02", "Organize on the first Wednesday in December"),),
                 True, rule="org"),
            Step("2026-12-18", "", "S", "Senate sponsors sign off",
                 "Senators approve the drafted text of their bills.",
                 (("sc29-2026", "2026-12-18", "Last day for prime sponsors to sign off on legislation"),)),
            Step("2027-01-05", "", "H", "House sponsors sign off",
                 "Each sponsor approves the drafted text of their bill.",
                 (("hc1-2026", "2027-01-05", "Last day to sign-off on all LSRs"),)),
            Step("2027-01-06", "", "HS", "The 2027 session opens",
                 "The new term's first session begins.",
                 (("hc1-2026", "2027-01-06", "opening day of the 2026 Session will be on the first Wednesday"),),
                 True, rule="open"),
            Step("2027-01-15", "", "H", "Last day to introduce House bills",
                 "The new term's House bills are introduced and sent to committees.",
                 (("hc1-2026", "2027-01-15", "Last day to introduce House Bills"),)),
        ]),
    ],
}

# ---------------------------------------------------------------------------
# THE USUAL PATTERN, a year to a bar: (first month, last month, class, the
# months in words, what, more). No date here is any one term's. The months
# are where the steps above fell in this term and in the calendars on disk
# before it, and a sentence says "usually" where one term can differ.
# ---------------------------------------------------------------------------
PATTERN = (
    ("First year", (
        (1, 6, "is-ses", "January to June", "In session",
         "Bills are introduced in January, cross to the other chamber in late March or "
         "April, and are finished by the end of June."),
        (7, 8, "is-off", "July and August", "Bills to the Governor",
         "The Governor signs or vetoes the last of the year's bills."),
        (9, 12, "is-fall", "September to December", "Retained bills, new requests, veto day",
         "House committees work on the bills they retained, members file requests for next "
         "year's bills, and each chamber meets for a veto day."),
    )),
    ("Second year", (
        (1, 6, "is-ses", "January to June", "In session",
         "Usually a shorter session, with crossover again in late March or April."),
        (7, 10, "is-study", "July to October", "Veto day and interim study",
         "The chambers meet for veto day, and committees study the bills sent to interim study."),
        (11, 11, "is-vote", "November", "The election",
         "Every seat in both chambers is on the ballot, and filing for the next term's bills "
         "opens the next day."),
        (12, 12, "is-org", "December", "Organization Day",
         "The new legislature is sworn in, and the next term begins."),
    )),
)
MONTH_LETTERS = "JFMAMJJASOND"
# The months' first letters in another language, for the bar's axis.
MONTH_LETTERS_LANG = {"es": "EFMAMJJASOND"}
WHO = {"H": "House", "S": "Senate", "HS": "Both chambers", "": ""}
RULE_WORDS = {"org": "By rule, the first Wednesday of December. ",
              "open": "By rule, the first Wednesday after the first Tuesday of January. ",
              "election": "By law (RSA 653:7), the Tuesday after the first Monday of November. "}


def T(s):
    """Text for the page: escaped, with the apostrophe a reader sees."""
    return html.escape(str(s or ""), quote=True).replace("&#x27;", "&rsquo;")


def _day(iso):
    return date.fromisoformat(str(iso)[:10])


def _dash(term):
    return term.replace("-", "&ndash;")


def _next(term):
    b = int(term.split("-")[1])
    return f"{b + 1}-{b + 2}"


def organization_day(year):
    """The first Wednesday of December of an even year (Part II, Article 3)."""
    first = date(int(year), 12, 1)
    return first + timedelta(days=(2 - first.weekday()) % 7)


def opening_day(year):
    """The first Wednesday after the first Tuesday of January (Part II,
    Article 3, as House Calendar 1 of 2026 quotes it)."""
    first = date(int(year), 1, 1)
    return first + timedelta(days=(1 - first.weekday()) % 7 + 1)


def general_election(year):
    """The state general election: the first Tuesday after the first Monday
    of November (RSA 653:7, read in db/NH_RSA.psv on 16 October 2026; see
    build_town_pages.next_possible_election)."""
    first = date(int(year), 11, 1)
    return first + timedelta(days=(0 - first.weekday()) % 7 + 1)


def term_of(today):
    """The term `today` falls in, by Organization Day: "2025-2026" from
    4 December 2024 to 1 December 2026."""
    y = today.year
    if y % 2:
        return f"{y}-{y + 1}"
    return f"{y + 1}-{y + 2}" if today >= organization_day(y) else f"{y - 1}-{y}"


def shown_term(today):
    """(the term whose dates the page shows, the term today falls in): the
    term today falls in -- from TERMS where it is entered, else from its
    skeleton -- unless that is older than every term TERMS holds, and then
    the oldest TERMS holds."""
    now = term_of(today)
    held = sorted(TERMS)
    return (now if now >= held[0] else held[0]), now


# ---------------------------------------------------------------------------
# A TERM NOBODY HAS ENTERED. The constitution fixes four of its days (Part
# II, Article 3, which House Calendar 1 of 2025 and of 2026 quote): each
# Organization Day, the first Wednesday of December of the even year, and
# each session's opening day, the first Wednesday after the first Tuesday of
# January. Those are dated, computed by their rule and cited to the calendar
# that quotes it, as the entered term's rule rows are. Everything else a
# term's calendars print is a step with no date, saying when it usually
# falls, as PATTERN does. Its seasons begin only on those fixed days -- a
# session's last day is the chambers' to set, so no season here claims a
# session has ended -- and the first is the term's own first year: a
# skeleton is drawn only for a term that has begun, so the election before
# it is the term before's. The drawn timeline says no calendar of the term
# has been read yet (SKELETON_CAPTION).
# ---------------------------------------------------------------------------
RULE_CITES = {"org": ("hc1-2025", "Organize on the first Wednesday in December"),
              "open": ("hc1-2026", "opening day of the 2026 Session will be on the first Wednesday"),
              "election": ("hc1-2026", "Last day prior to the General Election for incumbents running")}


def skeleton(term, lang=I.DEFAULT):
    """The seasons of a term TERMS does not hold, from the rules and the
    usual pattern alone, in `lang` (the Learn pages in Spanish, 25 October
    2026): each of its words is the catalog's, the years filled in after."""
    a, b = (int(x) for x in term.split("-"))

    def ruled(rule, day, who, name, what):
        doc, words = RULE_CITES[rule]
        return Step(day, "", who, name, what, ((doc, day, words),), True, rule=rule)

    org0, org1 = organization_day(a - 1).isoformat(), organization_day(b).isoformat()
    open_a, open_b, open_next = (opening_day(y).isoformat() for y in (a, b, b + 1))
    org_name = I.say(lang, "year.sk.org", "Organization Day")
    opens = I.say(lang, "year.sk.opens", "The session opens")
    governor = I.say(lang, "year.sk.governor", "Each bill both chambers passed goes to the Governor, "
                     "who signs it, vetoes it, or leaves it to become law without a signature.")
    to_governor = I.say(lang, "year.sk.to_governor", "Bills go to the Governor")
    veto_day = I.say(lang, "year.sk.veto_day", "Veto day")
    summer = I.say(lang, "year.sk.summer", "summer")
    crossover = Step("", "", "HS", I.say(lang, "year.sk.crossover", "Crossover"),
                     I.say(lang, "year.sk.crossover_what", "The last day for each chamber to act on its "
                           "own bills. What passes goes to the other chamber."),
                     when=I.say(lang, "year.sk.crossover_when", "late March or April"))
    conference = Step("", "", "HS", I.say(lang, "year.sk.conference", "Last day to act on committee "
                                          "of conference reports"),
                      I.say(lang, "year.sk.conference_what", "Both chambers vote on the conference "
                            "versions. It is the session's last deadline."),
                      when=I.say(lang, "year.sk.conference_when", "June"))
    sworn = I.say(lang, "year.sk.sworn", "The new members are sworn in, the House elects its Speaker "
                  "and the Senate its President, and the term begins.")
    return [
        Season(I.say(lang, "year.sk.first_year", "The First Year"),
               I.say(lang, "year.sk.first_when", "December {a} through {b}", a=a - 1, b=a), org0,
               I.say(lang, "year.sk.first_stands", "The {y1} session runs from January to about June."), [
            ruled("org", org0, "HS", org_name, sworn),
            ruled("open", open_a, "HS", opens,
                  I.say(lang, "year.sk.convening", "Convening day: the chambers begin taking up the "
                        "new bills.")),
            crossover, conference,
            Step("", "", "", to_governor, governor, when=summer),
            Step("", "", "HS", veto_day,
                 I.say(lang, "year.sk.veto_what", "Each chamber meets to take up the Governor's vetoes."),
                 when=I.say(lang, "year.sk.in_fall", "in the fall")),
        ]),
        Season(I.say(lang, "year.sk.second_year", "The Second Year"),
               I.say(lang, "year.sk.second_when", "{b}, until Organization Day", b=b), open_b,
               I.say(lang, "year.sk.second_stands", "The {y2} session runs from January to about June."), [
            ruled("open", open_b, "HS", opens,
                  I.say(lang, "year.sk.second_first", "The second session's first day.")),
            crossover, conference,
            Step("", "", "", to_governor, governor, when=summer),
            Step("", "", "HS", veto_day,
                 I.say(lang, "year.sk.veto_two", "Both chambers meet to take up the Governor's vetoes. "
                       "Overriding one takes two thirds of each chamber."),
                 when=I.say(lang, "year.sk.late_summer", "late summer or fall")),
            Step("", "", "HS", I.say(lang, "year.sk.study", "Interim study"),
                 I.say(lang, "year.sk.study_what", "Committees study the subjects of the bills sent to "
                       "interim study. The bills themselves go no further; a report may recommend a "
                       "new bill next term."),
                 when=I.say(lang, "year.sk.summer_fall", "summer and fall")),
            ruled("election", general_election(b).isoformat(), "",
                  I.say(lang, "year.sk.election", "General election"),
                  I.say(lang, "year.sk.election_what", "Voters choose all 400 representatives and 24 "
                        "senators for the next term.")),
        ]),
        Season(I.say(lang, "year.sk.next", "The Next Term Begins"),
               I.say(lang, "year.sk.next_when", "December {b} to January {c}", b=b, c=b + 1), org1,
               I.say(lang, "year.sk.next_stands", "The {next} term has begun. Its first session opens "
                     "in January."), [
            ruled("org", org1, "HS", org_name,
                  I.say(lang, "year.sk.next_sworn", "The members elected in November are sworn in, and "
                        "the {next} term begins.")),
            ruled("open", open_next, "HS",
                  I.say(lang, "year.sk.next_opens", "The {year} session opens", year=b + 1),
                  I.say(lang, "year.sk.next_first", "The new term's first session begins.")),
        ]),
    ]


SKELETON_CAPTION = ("No calendar of the {term} term has been read for this page yet, so its "
                    "dates are the ones the constitution and the election law fix, each with the calendar that "
                    "quotes the rule, and the rest of the term is described as it usually falls. "
                    "A season that is over is folded shut: open it to read its dates.")


def entered(term):
    """Whether TERMS holds the term's own dates, read off its calendars."""
    return term in TERMS


def seasons_of(term, lang=I.DEFAULT):
    """The term's seasons: TERMS's where it is entered, else its skeleton,
    their words in `lang`."""
    if not entered(term):
        return skeleton(term, lang)
    if lang == I.DEFAULT:
        return TERMS[term]
    return [_season_in(se, lang) for se in TERMS[term]]


# THE SCHEDULE'S OWN WORDS IN ANOTHER LANGUAGE (the Learn pages in Spanish,
# 25 October 2026). TERMS's words -- a season's name and when it falls, a
# step's name and sentence, a deadline it gathers -- and PATTERN's and
# RULE_WORDS' are data, each keyed year.<its first words> (year_words), and
# i18n.code_words asks a catalog for them where the language has this page.
# The words a calendar prints beside a date (a step's cites) are the
# record's, and are not among them.
def _data_words():
    """Every word TERMS, PATTERN and RULE_WORDS say, in reading order, once."""
    seen = []

    def add(x):
        if x and x not in seen:
            seen.append(x)
    for term in sorted(TERMS):
        for se in TERMS[term]:
            add(se.name), add(se.when), add(se.stands)
            for st in se.steps:
                add(st.name), add(st.what), add(st.when)
                for _day_, _who, name, _c in st.subs:
                    add(name)
    for label, segs in PATTERN:
        add(label)
        for _a, _b, _cls, when, what, more in segs:
            add(when), add(what), add(more)
    for v in RULE_WORDS.values():
        add(v)
    return seen


_KEYS = {}


def year_words():
    """[(key, English, where)] of the schedule's data words (_data_words),
    each under year.<a slug of its first words>, numbered where two begin
    alike."""
    out, used = [], {}
    for en in _data_words():
        base = "year." + I.slug_words(I.norm(en))
        key, n = base, 2
        while used.get(key, en) != en:
            key, n = f"{base}-{n}", n + 1
        used[key] = en
        out.append((key, I.norm(en), f"learn/{SLUG}: the schedule"))
    return out


def _w(lang, en):
    """One of the schedule's data words in `lang`: the catalog's where it is
    current, else the English, the miss kept for the build to say."""
    if lang == I.DEFAULT or not en:
        return en
    if not _KEYS:
        _KEYS.update({e: k for k, e, _w_ in year_words()})
    key = _KEYS.get(I.norm(en))
    got = I.say_piece(lang, key, I.norm(en)) if key else None
    if got is None:
        I.MISSES.add((lang, key or f"(no key for {en[:40]!r})", "missing"))
        return en
    return got


def _season_in(se, lang):
    return se._replace(name=_w(lang, se.name), when=_w(lang, se.when), stands=_w(lang, se.stands),
                       steps=[st._replace(name=_w(lang, st.name), what=_w(lang, st.what),
                                          when=_w(lang, st.when),
                                          subs=tuple((d, who, _w(lang, n), c) for d, who, n, c in st.subs))
                              for st in se.steps])


def checked_terms(today=None):
    """The terms verify() holds to their documents by default: every term
    TERMS holds, the term after the newest of them, and the term `today`
    falls in -- the skeletons the page draws next and now."""
    held = sorted(TERMS)
    out = held + [_next(held[-1])]
    if today is not None:
        out.append(term_of(today))
    return sorted(set(out))


# ---------------------------------------------------------------------------
# THE DATES AGAINST THE DOCUMENTS ON DISK.
# ---------------------------------------------------------------------------
_MONTHS = ("January February March April May June July August September October "
           "November December").split()


def _flat(text):
    return re.sub(r"\s+", " ", (text or "").replace("–", "-").replace("—", "-")).lower()


def _printed(iso):
    """The date as a calendar prints it, as a pattern over flat text:
    "march 26, 2026", "march 05, 2026"."""
    d = _day(iso)
    return re.compile(rf"\b{_MONTHS[d.month - 1].lower()}\s+0?{d.day},?\s+{d.year}\b")


def _says_day(words, iso):
    """Whether the words name the day themselves ("August 19th", "December
    4, 2024")."""
    d = _day(iso)
    return bool(re.search(rf"\b{_MONTHS[d.month - 1]}\s+0?{d.day}(?:st|nd|rd|th)?\b", words, re.I))


def cite_key(term, step, day, sub=""):
    """The name verify() files a cited date under, and the page looks up."""
    return f"{term} | {step.name}{': ' + sub if sub else ''} | {day}"


def all_cites(term=None, terms=None):
    """Every (key, day, doc, words, rule) a term cites: `term`'s, or each of
    `terms`', or by default every term checked_terms() names -- each from
    TERMS where it is entered, else from its skeleton."""
    out = []
    for t in ([term] if term else terms or checked_terms()):
        seasons = seasons_of(t)
        for s in seasons:
            for st in s.steps:
                for doc, day, words in st.cites:
                    out.append((cite_key(t, st, day), day, doc, words, st.rule))
                for day, _who, name, cites in st.subs:
                    for doc, words in cites:
                        out.append((cite_key(t, st, day, name), day, doc, words, ""))
    return out


def _rule_ok(step):
    if step.rule == "org":
        return step.day == organization_day(step.day[:4]).isoformat()
    if step.rule == "open":
        return step.day == opening_day(step.day[:4]).isoformat()
    if step.rule == "election":
        return step.day == general_election(step.day[:4]).isoformat()
    return True


def verify(root=Path("."), pdf=False, terms=None):
    """(problems, checked, absent): every cited date of `terms` (by default
    checked_terms()) against the text beside its document. problems is
    [(key, why)]; checked counts the cites whose text was on disk, absent
    those whose text was not. With pdf, a table's date and words are also
    held to one block of rows on the PDF's page."""
    root = Path(root)
    terms = terms or checked_terms()
    problems, checked, absent, texts = [], 0, 0, {}
    for key, day, doc, words, rule in all_cites(terms=terms):
        d = DOCS.get(doc)
        if d is None:
            problems.append((key, f"cites {doc}, which DOCS does not name"))
            continue
        if doc not in texts:
            p = root / d.path
            texts[doc] = _flat(p.read_text(encoding="utf-8", errors="replace")) if p.is_file() else None
        text = texts[doc]
        if text is None:
            absent += 1
            continue
        checked += 1
        if _flat(words) not in text:
            problems.append((key, f"{d.path} does not print {words!r}"))
        elif not (rule or d.set == "status" or _says_day(words, day) or _printed(day).search(text)):
            problems.append((key, f"{d.path} does not print {day}"))
        elif pdf and d.page and not rule and not _says_day(words, day):
            why = paired(root / d.path.replace(".txt", ".pdf"), d.page, day, words)
            if why:
                problems.append((key, why))
    for t in terms:
        for s in seasons_of(t):
            for st in s.steps:
                if st.day and not _rule_ok(st):
                    problems.append((cite_key(t, st, st.day), f"{st.day} is not the day its rule gives"))
    return problems, checked, absent


def paired(pdf_path, page, day, words):
    """"" where `words` stand in the block of rows that starts with `day` on
    the PDF's `page` or the next, else why not. A row is the words at one
    height; a block runs from a row printing the date to the next row that
    prints a weekday. Nothing here asks the network."""
    rows = _rows(str(pdf_path), page)
    if rows is None:
        return ""
    want, at = _flat(words), _printed(day)
    weekday = re.compile(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b")
    for i, row in enumerate(rows):
        if not at.search(row):
            continue
        block = [row]
        for nxt in rows[i + 1:]:
            if weekday.search(nxt):
                break
            block.append(nxt)
        if want in " ".join(block):
            return ""
    return f"{Path(pdf_path).name} page {page}: {words!r} is not in the block of rows dated {day}"


_ROWS = {}


def _rows(pdf_path, page):
    """The rows of a PDF's `page` and the next, as flat text, or None where
    pdfplumber or the PDF is not here. Read once a run: one calendar is cited
    for a score of dates, and reading it again for each took half a minute."""
    if (pdf_path, page) not in _ROWS:
        try:
            import pdfplumber
        except ImportError:
            return None
        if not Path(pdf_path).is_file():
            return None
        rows = []
        with pdfplumber.open(pdf_path) as doc:
            for n in (page, page + 1):
                if n - 1 >= len(doc.pages):
                    break
                by = {}
                for w in doc.pages[n - 1].extract_words():
                    by.setdefault(round(w["top"] / 3.0), []).append(w)
                rows += [_flat(" ".join(w["text"] for w in sorted(by[k], key=lambda w: w["x0"])))
                         for k in sorted(by)]
        _ROWS[(pdf_path, page)] = rows
    return _ROWS[(pdf_path, page)]


# ---------------------------------------------------------------------------
# DRAWING THE FIGURES.
# ---------------------------------------------------------------------------
def _addresses(root):
    """{(set, day, number): the General Court's address} from the list
    calendar_documents reads, or {} where that list is not on this disk."""
    try:
        import calendar_documents as CD
        docs, _out = CD.read(Path(root) / CD.QUEUE, root=Path(root))
    except Exception:                                        # noqa: BLE001
        return {}
    return {(d.set, d.date, d.number[0]): d.url for d in docs if d.date and d.number[0]}


def _words(iso, form="full", lang=I.DEFAULT):
    import components
    return components.date_words(iso, form) if lang == I.DEFAULT else components.date_words(
        iso, form, lang)


def _span(a, b, form="full", lang=I.DEFAULT):
    import components
    return components.date_span(a, b, form) if lang == I.DEFAULT else components.date_span(
        a, b, form, lang)


def doc_label(doc):
    d = DOCS[doc]
    return f"{ONE[d.set]} {d.number}, {_words(d.day)}"


def cite_html(docs, links, lang=I.DEFAULT):
    """The documents a step cites, as the line under it. In another language
    a document's name is the record's, marked as English, and its date in
    the language."""
    out, seen = [], []
    for doc in docs:
        if doc in seen:
            continue
        seen.append(doc)
        d = DOCS[doc]
        if d.set == "status":
            out.append('<a href="/#state">' + I.say(lang, "year.ui.status", "the session status on "
                                                     "the home page") + "</a>")
            continue
        url = links.get((d.set, d.day, d.number))
        label = (T(doc_label(doc)) if lang == I.DEFAULT else
                 f'<span lang="en">{T(ONE[d.set])} {d.number}</span>, {T(_words(d.day, "full", lang))}')
        out.append(f'<a href="{T(url)}" target="_blank" rel="noopener"'
                   + ("" if lang == I.DEFAULT else ' hreflang="en"') + f">{label}</a>"
                   if url else label)
    return ((I.say(lang, "year.ui.source", "Source:") if len(out) == 1 else
             I.say(lang, "year.ui.sources", "Sources:")) + " " + "; ".join(out) + ".")


def _who(who, lang=I.DEFAULT):
    if not who:
        return ""
    name = (WHO[who] if lang == I.DEFAULT else
            {"H": I.say(lang, "year.ui.house", "House"), "S": I.say(lang, "year.ui.senate", "Senate"),
             "HS": I.say(lang, "year.ui.both", "Both chambers")}[who])
    return f'<span class="l-tlwho">{name}</span>'


def _cited_ok(term, st, bad):
    """Whether every date the step cites is still printed where it says."""
    keys = [cite_key(term, st, day) for _doc, day, _w in st.cites]
    keys += [cite_key(term, st, day, name) for day, _who, name, _c in st.subs]
    return not any(k in bad for k in keys)


def _step_html(st, today, links, term, ok=True, lang=I.DEFAULT):
    """One row: the date, then what it is and whose, a sentence, the
    deadlines it gathers, and the documents it comes from. `st`'s words are
    already in `lang` (seasons_of)."""
    dated = bool(st.day) and ok
    past = dated and _day(st.until or st.day) < today
    cls = (["l-tlstep"] + (["is-key"] if st.key else []) + (["is-past"] if past else [])
           + ([] if dated else ["is-usual"]))
    if dated:
        shown = (_span(st.day, st.until, "medium", lang) if st.until
                 else _words(st.day, "medium", lang))
        when = f'<time datetime="{st.day}">{T(shown)}</time>'
    else:
        when = ('<span class="l-tlus">' + I.say(lang, "year.ui.usually", "Usually")
                + f"</span> {T(st.when)}")
    what = T(st.what).replace("{next}", _dash(_next(term)))
    body = [f'<p class="l-tln"><b>{T(st.name)}</b>{_who(st.who, lang)}</p>',
            f'<p class="l-tlw">{what}</p>']
    if st.subs and dated:
        body.append('<ol class="l-tlsub">' + "".join(
            f'<li><time datetime="{day}">{T(_words(day, "short", lang))}</time>'
            f'<span>{T(name)}{_who(who, lang)}</span></li>' for day, who, name, _c in st.subs) + "</ol>")
    docs = [doc for doc, _d, _w in st.cites] + [doc for _d, _w, _n, cs in st.subs for doc, _x in cs]
    if dated and docs:
        rule = _w(lang, RULE_WORDS.get(st.rule, ""))
        if lang != I.DEFAULT and rule:
            rule = rule.rstrip() + " "      # the catalog keeps a piece's words without the space
        body.append(f'<p class="l-tls">{rule}{cite_html(docs, links, lang)}</p>')
    return (f'<li class="{" ".join(cls)}"><p class="l-tld">{when}</p>'
            f'<div class="l-tlb">{"".join(body)}</div></li>')


def _here_html(today, lang=I.DEFAULT):
    return (f'<li class="l-tlstep l-tlnow" id="{HERE_ID}"><p class="l-tld">'
            f'<time datetime="{today.isoformat()}">{T(_words(today, "medium", lang))}</time></p>'
            '<div class="l-tlb"><p class="l-tln"><b>' + I.say(lang, "year.ui.here", "You are here")
            + '</b></p><p class="l-tlw">' + I.say(lang, "year.ui.built", "The day this page was built.")
            + "</p></div></li>")


def _where(seasons, today):
    """The index of the season `today` falls in, -1 before the first."""
    k = -1
    for i, s in enumerate(seasons):
        if _day(s.start) <= today:
            k = i
    return k


def timeline(term, today, links, bad=None, lang=I.DEFAULT):
    """The term, season by season: an ordered list of seasons each holding an
    ordered list of steps, with You Are Here among them. A season wholly past
    is folded shut; the one the day falls in, and those to come, are open."""
    seasons = seasons_of(term, lang)
    bad = bad or {}
    here = _where(seasons, today)
    out = []
    for i, s in enumerate(seasons):
        end = _day(seasons[i + 1].start) - timedelta(days=1) if i + 1 < len(seasons) else None
        past = end is not None and end < today
        rows, placed, prev = [], False, s.start
        for st in s.steps:
            ok = _cited_ok(term, st, bad)
            if st.day and not ok and not st.when:
                continue
            at = (st.day if ok else "") or prev
            if i == here and not placed and _day(at) > today:
                rows.append(_here_html(today, lang))
                placed = True
            rows.append(_step_html(st, today, links, term, ok, lang))
            prev = at
        if i == here and not placed:
            rows.append(_here_html(today, lang))
        n = sum(1 for st in s.steps if st.day)
        if lang == I.DEFAULT:
            state = "all past" if past else "you are here" if i == here else "to come"
            count = f'{n} date{"" if n == 1 else "s"}, {state}'
        else:
            state = (I.say(lang, "year.ui.all_past", "all past") if past else
                     I.say(lang, "year.ui.here_lc", "you are here") if i == here else
                     I.say(lang, "year.ui.to_come", "to come"))
            count = (I.say(lang, "year.ui.one_date", "1 date, {state}", state=state) if n == 1 else
                     I.say(lang, "year.ui.dates", "{n} dates, {state}", n=n, state=state))
        out.append(
            f'<li class="l-tlseason{" is-past" if past else ""}{" is-here" if i == here else ""}">'
            f'<details{" open" if i == max(here, 0) else ""}><summary>'
            f'<h3 class="l-tlh">{T(s.name)}</h3>'
            f'<span class="l-tlwhen">{T(s.when)} &middot; {count}</span></summary>'
            f'<ol class="l-tlsteps">{"".join(rows)}</ol></details></li>')
    if here < 0:
        out.insert(0, f'<li class="l-tlseason is-here"><ol class="l-tlsteps">{_here_html(today, lang)}'
                   "</ol></li>")
    # SHORTER (the person, 22 October 2026: "significantly simplified and
    # streamlined"): only the season the day falls in is open.
    if lang == I.DEFAULT:
        caption = (T(SKELETON_CAPTION.format(term=term)).replace(term, _dash(term))
                   if not entered(term) else
                   'Each date is from the House or Senate calendar or journal named under it; '
                   '<b>Usually</b> marks a step with no one date. Open a season to read its dates.')
        label = f"The {_dash(term)} term, date by date"
    else:
        caption = (I.say(lang, "year.ui.skeleton", "No calendar of the {term} term has been read for "
                         "this page yet, so its dates are the ones the constitution and the election "
                         "law fix, each with the calendar that quotes the rule, and the rest of the "
                         "term is described as it usually falls. A season that is over is folded "
                         "shut: open it to read its dates.", term=_dash(term))
                   if not entered(term) else
                   I.say(lang, "year.ui.caption", "Each date is from the House or Senate calendar or "
                         "journal named under it; <b>Usually</b> marks a step with no one date. Open "
                         "a season to read its dates."))
        label = I.say(lang, "year.ui.label", "The {term} term, date by date", term=_dash(term))
    return (f'<figure class="l-fig l-tl" role="group" aria-label="{label}">'
            f'<ol class="l-tlseasons">{"".join(out)}</ol>'
            f'<figcaption class="l-cap">{caption}</figcaption></figure>')


def shape(today, lang=I.DEFAULT):
    """The usual pattern of a term, a year to a bar, with the day the page
    was built pinned on its own year. The years named are the odd year and
    the even year around that day, as a term's first and second."""
    y = today.year
    years = (y, y + 1) if y % 2 else (y - 1, y)
    term = f"{years[0]}-{years[1]}"
    out = []
    for k, (label, segs) in enumerate(PATTERN):
        year = years[k]
        bars = "".join(f'<i class="{cls}" style="flex:{b - a + 1}"></i>' for a, b, cls, *_r in segs)
        pin = ""
        if y == year:
            jan1 = date(year, 1, 1)
            pos = 100 * ((today - jan1).days + 0.5) / (date(year + 1, 1, 1) - jan1).days
            side = " is-r" if pos > 70 else " is-l" if pos < 30 else ""
            pin = (f'<span class="l-yrpin{side}" style="left:{pos:.2f}%"><span>'
                   + I.say(lang, "year.ui.here", "You are here") + "</span></span>")
        key = "".join(
            f'<li><span class="l-sw {cls}" aria-hidden="true"></span><span><b>{T(_w(lang, when))}:</b> '
            f'{T(_w(lang, what))}.</span></li>'
            for _a, _b, cls, when, what, more in segs)
        the_year = (f"the {T(label.lower())}" if lang == I.DEFAULT else
                    I.say(lang, "year.ui.the_first", "the first year") if k == 0 else
                    I.say(lang, "year.ui.the_second", "the second year"))
        out.append(
            f'<div class="l-yrrow{" is-now" if pin else ""}"><p class="l-yrh"><b>{year}</b> '
            f'{the_year}</p>'
            f'<div class="l-yrbar"><div class="l-barb" aria-hidden="true">{bars}</div>{pin}</div>'
            '<ol class="l-yrmon" aria-hidden="true">'
            + "".join(f"<li>{m}</li>" for m in (MONTH_LETTERS if lang == I.DEFAULT else
                                                MONTH_LETTERS_LANG.get(lang, MONTH_LETTERS))) + "</ol>"
            f'<ul class="l-barkey">{key}</ul></div>')
    if lang == I.DEFAULT:
        if y % 2 == 0 and today >= organization_day(y):
            where = (f"after Organization Day, which began the {_dash(_next(term))} term")
        else:
            where = (f"in the {'first' if y == years[0] else 'second'} year of the "
                     f"{_dash(term)} term")
        return (f'<figure class="l-fig l-yr" role="group" aria-label="The usual shape of a two-year term">'
                + "".join(out)
                + f'<figcaption class="l-cap"><b>You are here: {T(_words(today))}</b>, {where}. '
                'The usual pattern; this term&rsquo;s dates are below.</figcaption></figure>')
    if y % 2 == 0 and today >= organization_day(y):
        where = I.say(lang, "year.ui.after_org", "after Organization Day, which began the {term} term",
                      term=_dash(_next(term)))
    elif y == years[0]:
        where = I.say(lang, "year.ui.in_first", "in the first year of the {term} term", term=_dash(term))
    else:
        where = I.say(lang, "year.ui.in_second", "in the second year of the {term} term", term=_dash(term))
    return ('<figure class="l-fig l-yr" role="group" aria-label="'
            + I.say(lang, "year.ui.shape", "The usual shape of a two-year term") + '">'
            + "".join(out) + '<figcaption class="l-cap">'
            + I.say(lang, "year.ui.shape_cap", "<b>You are here: {day}</b>, {where}. The usual "
                    "pattern; this term&rsquo;s dates are below.", day=T(_words(today, "full", lang)),
                    where=where)
            + "</figcaption></figure>")


# The dates Right Now lists (22 October 2026: the next eight, each with its
# chamber; the documents they come from are in the full schedule below).
SOON = 8


# SHORT (the person, 22 October 2026: "shorten the Right Now sentence"): each
# season's line says only where the legislature is, and Coming up says what
# is next.
def now_html(term, today, here, bad=None, lang=I.DEFAULT):
    """Where Things Stand: the season the day falls in, the last landmark to
    have passed, and the next three dated steps. `here` is the page's own
    address, which an anchor needs under the template's <base href="/">."""
    seasons = seasons_of(term, lang)
    a, b = term.split("-")
    cur = term_of(today)
    words = {"term": _dash(term), "y1": a, "y2": b, "next": _dash(_next(term))}
    bad = bad or {}
    i = _where(seasons, today)
    if lang == I.DEFAULT:
        out = [f'<p class="l-yrhere"><b>You are here: {T(_words(today))}.</b> ']
    else:
        out = ['<p class="l-yrhere"><b>' + I.say(lang, "year.ui.here_day", "You are here: {day}.",
                                                 day=T(_words(today, "full", lang))) + "</b> "]
    if cur != term:
        out.append((f"The {_dash(cur)} term has begun. Its deadlines are added here once the "
                    f"chambers&rsquo; calendars print them; until then the dates below are the "
                    f"{_dash(term)} term&rsquo;s." if lang == I.DEFAULT else
                    I.say(lang, "year.ui.begun", "The {cur} term has begun. Its deadlines are added "
                          "here once the chambers&rsquo; calendars print them; until then the dates "
                          "below are the {term} term&rsquo;s.", cur=_dash(cur), term=_dash(term)))
                   + "</p>")
    elif i < 0:
        out.append((f"The {_dash(term)} term has not begun." if lang == I.DEFAULT else
                    I.say(lang, "year.ui.not_begun", "The {term} term has not begun.",
                          term=_dash(term))) + "</p>")
    else:
        out.append(seasons[i].stands.format(**words).replace("'", "&rsquo;") + "</p>")
    steps = [st for s in seasons for st in s.steps if st.day and _cited_ok(term, st, bad)]
    soon = [st for st in steps if _day(st.until or st.day) >= today][:SOON]
    if soon:
        out.append('<p class="l-yrnext">' + I.say(lang, "year.ui.coming", "Coming up:")
                   + '</p><ol class="l-yrsoon">' + "".join(
            f'<li><time datetime="{st.day}">'
            f'{T(_span(st.day, st.until, "full", lang) if st.until else _words(st.day, "full", lang))}'
            f'</time><span>{T(st.name)}{_who(st.who, lang)}</span></li>' for st in soon) + "</ol>")
    out.append("<p>" + I.say(lang, "year.ui.this_week", "This week&rsquo;s hearings and sessions are "
                             'on <a href="calendar.html">the Calendar</a>.') + "</p>")
    return "".join(out)


def figures(today, root=Path("."), lang=I.DEFAULT):
    """The page's figures, for build_civics to fill civics.BODY_YEAR with:
    year_now (Where Things Stand), year_shape (the usual pattern), year_dates
    (the term, date by date) and year_term (whose dates those are). Says what
    it leaves out: a date whose own document on disk no longer prints it,
    and a current term with no deadlines entered."""
    import civics
    import shell
    term, cur = shown_term(today)
    links = _addresses(root)
    problems, _checked, _absent = verify(root, terms=[term])
    bad = {key: why for key, why in problems if key.startswith(term + " |")}
    if lang != I.DEFAULT:
        return {"year_now": now_html(term, today, shell.canon("/" + HREF), bad, lang),
                "year_shape": civics.wide(shape(today, lang)),
                "year_dates": civics.wide(timeline(term, today, links, bad, lang)),
                "year_term": _dash(term)}
    for key, why in bad.items():
        print(f"  learn/{SLUG}.html LEAVES OUT a date its document does not print: {key}: {why}")
    if cur != term:
        print(f"  learn/{SLUG}.html: no deadlines entered for the {cur} term; it shows "
              f"{term}'s (legislative_year.TERMS)")
    elif not entered(term):
        print(f"  learn/{SLUG}.html: the {term} term's printed deadlines are not entered "
              "(legislative_year.TERMS); it shows the days the constitution fixes and the "
              "usual pattern")
    here = shell.canon("/" + HREF)
    return {"year_now": now_html(term, today, here, bad),
            "year_shape": civics.wide(shape(today)),
            "year_dates": civics.wide(timeline(term, today, links, bad)),
            "year_term": _dash(term)}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Check the year page's dates against the documents on disk.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--pdf", action="store_true",
                    help="also read each pairing off the PDF's rows (pdfplumber)")
    a = ap.parse_args()
    problems, checked, absent = verify(Path(a.root), pdf=a.pdf)
    for key, why in problems:
        print(f"  {key}: {why}")
    print(f"{checked} cited dates checked against the text on disk"
          + (" and the PDFs' rows" if a.pdf else "")
          + f"; {absent} with no text here; {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
