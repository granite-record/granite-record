#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.3
"""
The fixture project and site that preflight's checks build and read, and what a
run makes once.

The fixture project (_site_fixture) and the site twenty builders make of it
(_built_site), made once a run (_once_a_run, _fixture_site_shared) or beside
the checks before the first of them (_start_early_builds), and handed to each
check that asks as a copy in a folder of its own. Moved out of preflight.py as
it stood, with the comments above each (16 November 2026, the refactor's
stage 1, step 4). This module uses pf_core and no other module of the suite.
"""

import csv
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import _paths
import child

from pf_core import (_map_kept, _reaching, _run, imp)


# journal_motions.json for the site fixture: the vote on no bill of 6 March
# 2026 in the fixture's rollcalls.json, as the parser writes it from House
# Journal 6 of 5 March 2026 (the passage is that one's, the day the fixture's),
# and a reprimand the Journal records by division alone.
#
# And the owner's review of that day: a committee's report whole under the
# vote on it ("View the report"), the reprimand shown as a "Misc vote", and a
# motion on HB 1442's own debate -- a roll call to divide it the roll-call
# file files under no bill (2026-H-312), and the previous question moved on
# it, carried on a division only the Journal records -- drawn under HB 1442.
_NB_FIXTURE = {
    "kinds": {"reprimand": "Misc vote", "member_continue": "Shall the member continue",
              "suspend_rules": "Rules suspension", "motion": "Misc vote"},
    "groups": {"reprimand": "misc", "privileges": "misc", "motion": "misc", "other": "misc",
               "suspend_rules": "misc", "appeal": "misc"},
    "group_words": {"misc": "Misc votes"},
    "bill_votes": [{
        "key": "2026-03-06-H-m140500", "body": "H", "date": "2026-03-06", "term": "2025-2026",
        "bill": "HB1442", "bill_from": "debate", "motion": "previous_question",
        "words": "Previous Question", "mover": "Sweeney", "how": "division",
        "yeas": 201, "nays": 150, "passed": True,
        "file": "journals/2026/HJ 06 March 5, 2026.txt", "journal": "House Journal 6",
        "page": 141, "pdf_page": 141, "url": "",
        "said": [{"k": "moved", "t": "Rep. Sweeney moved the previous question."},
                 {"k": "outcome", "t": "On a division vote, with 201 members having voted in the "
                                       "affirmative, and 150 in the negative, the motion was "
                                       "adopted."}], "at": 140500},
        # By the Journal's own words: carried "without objection".
        {"key": "2026-03-06-H-m140100", "body": "H", "date": "2026-03-06", "term": "2025-2026",
         "bill": "HB1442", "bill_from": "named", "motion": "limit_debate",
         "words": "Limit Debate", "mover": "Osborne", "how": "without objection",
         "yeas": None, "nays": None, "passed": True,
         "file": "journals/2026/HJ 06 March 5, 2026.txt", "journal": "House Journal 6",
         "page": 140, "pdf_page": 140, "url": "",
         "said": [{"k": "moved", "t": "Without objection, Rep. Osborne moved that debate on HB 1442 "
                                      "be limited to 20 minutes on each side."},
                  {"k": "outcome", "t": "Adopted."}], "at": 140100}],
    "rollcalls": {"2026-H-311": {
        "key": "2026-H-311", "body": "H", "date": "2026-03-06", "term": "2025-2026",
        "file": "journals/2026/HJ 06 March 5, 2026.txt", "journal": "House Journal 6",
        "page": 142, "pdf_page": 142, "page_date": "2026-03-06",
        "url": "https://gc.nh.gov/house/calendars_journals/viewer.aspx?fileName=journals%5C2026"
               "%5CHJ%2006%20March%205%2C%202026.pdf",
        "yeas": 91, "nays": 82, "passed": False, "words": "Shall Member Continue",
        "heading": "OBJECTION", "kind": "member_continue", "held": [],
        "said": [{"k": "uc", "t": "Rep. Nelson requested Unanimous Consent of the House "
                                  "regarding the war in Iran and addressed the House."},
                 {"k": "objection", "t": "An objection was raised to the unanimous consent given "
                                         "by Rep. Nelson; withdrawing unanimous consent."},
                 {"k": "question", "t": "The question being shall the member continue."},
                 {"k": "outcome", "t": "The motion failed lacking the necessary three-fifths "
                                       "vote."}],
        "member": "Nelson", "about": "the war in Iran", "member_id": "377204",
        "bill": "", "bills": [],
        "line": "Whether Rep. Nelson could go on with remarks on the war in Iran",
        "group": "misc"},
        "2026-H-312": {
        "key": "2026-H-312", "body": "H", "date": "2026-03-06", "term": "2025-2026",
        "file": "journals/2026/HJ 06 March 5, 2026.txt", "journal": "House Journal 6",
        "page": 140, "pdf_page": 140, "page_date": "2026-03-06", "url": "",
        "yeas": 150, "nays": 180, "passed": False, "words": "Divide",
        "heading": "MOTION TO DIVIDE", "kind": "motion", "held": [],
        "said": [{"k": "moved", "t": "Rep. Weber moved that section two of HB 1442 be divided from "
                                     "the bill."},
                 {"k": "outcome", "t": "and the motion failed."}],
        "member": "", "member_id": "", "bill": "HB1442", "bills": ["HB1442"], "line": "",
        "line_held": "no summary for this kind of passage", "title": "Divide the Question",
        "bill_motion": "divide", "on_bill": "HB1442"}},
    "journal_only": [{
        "key": "2026-03-06-H-d182020", "body": "H", "date": "2026-03-06", "term": "2025-2026",
        "file": "journals/2026/HJ 06 March 5, 2026.txt", "journal": "House Journal 6",
        "page": 32, "pdf_page": 32, "url": "", "how": "division", "yeas": 264, "nays": 89,
        "passed": True, "heading": "MOTION TO REPRIMAND", "kind": "reprimand", "group": "misc",
        "report": {"heading": "REPORT OF THE COMMITTEE ON LEGISLATIVE ADMINISTRATION",
                   "paras": ["On March 5, Representative Jodi Nelson made two posts on a social "
                             "media platform, and a complaint was filed with the Speaker, who "
                             "referred the matter to this committee for review and report.",
                             "The majority of the committee recommends that Representative Jodi "
                             "Nelson be reprimanded by the House. Rep. Hill for the Committee. "
                             "Vote: 10-2"],
                   "page_from": 31, "page_to": 32, "pdf_from": 31, "pdf_to": 32},
        "said": [{"k": "question", "t": "The question being should Representative Jodi Nelson "
                                        "be reprimanded by the House of Representatives?"},
                 {"k": "outcome", "t": "On a division vote, with 264 members having voted in "
                                       "the affirmative, and 89 in the negative, the motion was "
                                       "adopted."}],
        "member": "Jodi Nelson", "member_id": "377204", "bill": "", "bills": [], "line": "",
        "after": "Representative Jodi Nelson was reprimanded by the House of Representatives.",
        # The motion by name (the owner's third review, 23 October 2026).
        "title": "Reprimand the Member (Rep. Jodi Nelson)",
        "at": 182020}]}


def _site_fixture(root):
    """The smallest project that still exercises every builder.

    Two bills, two members, one recording, one committee report, one roll call,
    one veto the docket settled and the status page did not.
    """
    d = root / "data"
    (root / "work" / "VID1").mkdir(parents=True)
    (root / "work" / "VID4").mkdir(parents=True)
    d.mkdir(parents=True)
    w = lambda p, o: (root / p).write_text(json.dumps(o), encoding="utf-8")

    # {term: {bill: record}}: the file the whole per-bill loop is driven
    # from, so a bill number alone at the top of the pipeline puts two
    # different bills under one key.
    w("data/bills.json", {"2025-2026": {
        "HB1442": {"designation": "HB 1442", "title": "relative to insurance coverage",
                   "lsr_num": "0503", "lsr_year": "2026", "subject": "Insurance",
                   "chamber": "H", "house_committee": "Commerce",
                   "senate_committee": "", "lsr": "2026-0503"},
        "SB434": {"designation": "SB 434", "title": "relative to school materials",
                  "lsr_num": "0611", "lsr_year": "2026", "subject": "Education",
                  "chamber": "S", "senate_committee": "Education",
                  "house_committee": "", "lsr": "2026-0611"},
        # A House Resolution, which the House adopts and which then goes
        # nowhere. Every bill in this fixture used to be an HB or an SB, so
        # nothing here noticed that 36 adopted resolutions were being shown as
        # still in progress, one of them "Pending action in the other chamber".
        "HR10": {"designation": "HR 10", "title": "honouring a retirement",
                 "lsr_num": "0900", "lsr_year": "2026", "subject": "Miscellaneous",
                 "chamber": "H", "house_committee": "Legislative Administration",
                 "senate_committee": "", "lsr": "2026-0900"},
        # Killed on the floor, with a chamber status that never caught up.
        "SB900": {"designation": "SB 900", "title": "relative to a study",
                  "lsr_num": "0901", "lsr_year": "2026", "subject": "Miscellaneous",
                  "chamber": "S", "senate_committee": "Judiciary",
                  "house_committee": "", "lsr": "2026-0901"}}})
    w("data/legislators.json", [
        {"id": "377204", "name": "Nelson, Jodi", "chamber": "H", "party": "Republican",
         # As the real roster writes it. The fixture carried "Rock." with a
         # trailing point, which data/legislators.json has never contained --
         # all ten of its abbreviations are bare -- so this asserted a shape
         # only the fallback table produced.
         "party_code": "R", "county": "Rockingham", "county_abbr": "Rock",
         "district": "13", "label": "Nelson, Jodi(R) Rock 13", "email": "j@gc.nh.gov",
         "url": "", "towns": ["Raymond"], "committees": ["Commerce"], "title": "",
         # A seat on the floor, so the roster under the seating chart is read
         # on the page's own row (the review of 29 October 2026): Division 2,
         # seat 7, which the card shows as "007".
         "seat": "2007", "phone": ""},
        {"id": "377207", "name": "Altschiller, Debra", "chamber": "S",
         "party": "Democrat", "party_code": "D", "county": "Rockingham",
         "county_abbr": "Rock", "district": "24",
         "label": "Altschiller, Debra(D) Rock. 24", "email": "d@gc.nh.gov", "url": "",
         "towns": ["Stratham"], "committees": ["Education"], "title": "", "phone": ""}])
    w("data/sponsors.json", {"HB1442": [
        {"member_id": "377204", "name": "Nelson, Jodi", "party": "R", "chamber": "H",
         "label": "Nelson, Jodi(R) Rock 13", "sequence": 0, "prime": True}]})
    w("data/member_votes.json", [
        {"member_id": "377204", "name": "Nelson, Jodi", "party": "R",
         "label": "Nelson, Jodi(R) Rock 13", "year": "2026", "body": "H",
         "vote_number": "310", "bill": "HB1442", "question": "Ought to Pass",
         "date": "2026-03-06", "vote": "Yea"},
        # The same bill number, the same chamber and the same vote sequence
        # number, in the previous term. Sequence numbers restart every session,
        # so this pair is not contrived -- it is what two terms of the file
        # look like side by side.
        {"member_id": "377204", "name": "Nelson, Jodi", "party": "R",
         "label": "Nelson, Jodi(R) Rock 13", "year": "2024", "body": "H",
         "vote_number": "310", "bill": "HB1442",
         "question": "Inexpedient to Legislate",
         "date": "2024-03-06", "vote": "Nay"},
        # A vote on no bill: the member Votes tab says what it was about.
        {"member_id": "377204", "name": "Nelson, Jodi", "party": "R",
         "label": "Nelson, Jodi(R) Rock 13", "year": "2026", "body": "H",
         "vote_number": "311", "bill": "", "question": "Shall Member Continue",
         "date": "2026-03-06", "vote": "Nay"},
        # A motion to divide HB 1442 the roll-call file files under no bill:
        # the member Votes tab names the bill (vote_passage.move_on_bills).
        {"member_id": "377204", "name": "Nelson, Jodi", "party": "R",
         "label": "Nelson, Jodi(R) Rock 13", "year": "2026", "body": "H",
         "vote_number": "312", "bill": "", "question": "Divide",
         "date": "2026-03-06", "vote": "Nay"}])
    w("data/towns.json", {"Raymond": [{"county": "Rockingham", "district": "13",
                                       "ward": "0", "seats": 2}]})
    # {term: {bill: record}}: bill numbers repeat every biennium, so the
    # file is keyed on the term and a bare bill number is not a key.
    w("narratives.json", {"2025-2026": {
        "SB900": {"narrative": "The Senate voted it down.", "stages": [],
                  "notes": [], "unrecognised": [],
                  "events": [{"date": "2026-02-19", "type": "floor", "body": "S",
                              "cancelled": False, "motion": "MA",
                              "action": "Inexpedient to Legislate, RC 16Y-8N",
                              "vote_kind": "", "yeas": None, "nays": None,
                              "raw": "Inexpedient to Legislate, RC 16Y-8N, "
                                     "MA; 02/19/2026"}]},
        "HB1442": {"narrative": "It was introduced.",
                   "stages": [{"label": "House Committee", "text": "It was introduced."}],
                   "notes": [], "unrecognised": [],
                   "events": [{"date": "2026-03-06", "type": "floor", "body": "H",
                               "cancelled": False, "action": "Ought to Pass",
                               "motion": "MA", "vote_kind": "RC", "yeas": "214",
                               "nays": "119",
                               # As narrative.py writes it: clean() has taken
                               # the citation off the line, and cite_of() has
                               # put it in a field. The fixture used to leave
                               # "HJ 7 P. 55" on the raw line, which no built
                               # narrative ever contains, and so tested a
                               # lookup against a string that is never there.
                               "cite": "HJ 7", "cite_page": "55",
                               "raw": "Ought to Pass: MA RC 214-119 03/06/2026"},
                              # The same volume, a different page. Documents
                              # dedupes on the URL, and a volume has one URL
                              # however many pages are cited, so listing them
                              # per event kept the first page and dropped the
                              # rest silently -- 499 entries on the real site.
                              {"date": "2026-03-06", "type": "amendment",
                               "body": "H", "cancelled": False,
                               "amendment": "2026-0503h", "amend_kind":
                               "Committee Amendment", "motion": "AA",
                               "vote_kind": "VV", "mover": "",
                               "cite": "HJ 7", "cite_page": "56",
                               "raw": "Amendment # 2026-0503h: AA VV 03/06/2026"},
                              # The same volume number in the OTHER year of the
                              # term. Only the 2026 HJ 7 is on file, and the
                              # bare key points at it, so this action keeps its
                              # citation and gets no link: HJ 7 of 2025 is a
                              # different document and does not contain it.
                              {"date": "2025-05-14", "type": "floor", "body": "H",
                               "cancelled": False, "action": "Ought to Pass",
                               "motion": "MA", "vote_kind": "VV",
                               "cite": "HJ 7", "cite_page": "9",
                               "raw": "Ought to Pass: MA VV 05/14/2025"},
                              # A committee report as the docket records it,
                              # with no calendar prose behind it. This is the
                              # Senate's whole shape -- one report, a vote, no
                              # minority -- and 319 bills have nothing else.
                              {"date": "2026-04-16", "type": "report", "body": "S",
                               "cancelled": False, "side": "",
                               "committee": "Senate Commerce",
                               "recommendation": "Referred to Interim Study",
                               "amendment": "", "report_date": "04/16/2026",
                               "yeas": "5", "nays": "0", "new_title": False,
                               "cite": "SC 14", "cite_page": "",
                               "raw": "Committee Report: Referred to Interim "
                                      "Study, 04/16/2026, Vote 5-0, CC"},
                              # A second Senate report, from the day the
                              # committee sent it back. The database has no
                              # written report for this one, so it stays a
                              # docket line -- which is the case the absorbing
                              # of the OTHER one must not break.
                              {"date": "2026-03-10", "type": "report",
                               "body": "S", "committee": "Senate Commerce",
                               "recommendation":
                                   "Re-referred to Committee",
                               "report_date": "03/10/2026", "cite": "SC 9",
                               "side": "", "yeas": "5", "nays": "0",
                               "cancelled": False,
                               "raw": "Committee Report: Re-referred to "
                                      "Committee, 03/10/2026; SC 9"},
                              # And the House report the calendar did print, so
                              # the two are joined on the calendar they cite.
                              {"date": "2026-02-27", "type": "report", "body": "H",
                               "cancelled": False, "side": "",
                               "committee": "Commerce",
                               "recommendation": "Ought to Pass",
                               "amendment": "", "report_date": "02/24/2026",
                               "yeas": "19", "nays": "0", "new_title": False,
                               "cite": "HC 9", "cite_page": "12",
                               "raw": "Committee Report: Ought to Pass "
                                      "02/24/2026 (Vote 19-0; CC)"}]},
        "HR10": {"narrative": "The House adopted it.", "stages": [], "notes": [],
                 "unrecognised": [],
                 "events": [{"date": "2026-03-05", "type": "floor", "body": "H",
                             "cancelled": False, "action": "Ought to Pass",
                             "motion": "MA", "vote_kind": "VV",
                             "raw": "Ought to Pass: MA VV 03/05/2026"}]},
        "SB434": {"narrative": "The governor vetoed it.", "stages": [], "notes": [],
                  "unrecognised": [],
                  "events": [{"date": "2026-08-19", "type": "other", "body": "H",
                              "cancelled": False,
                              "raw": "Veto Sustained 08/19/2026: RC 165-140 "
                                     "Lacking Necessary Two-Thirds Vote"}]}}})
    # {term: {bill: [votes]}}. A bill number is unique within a term and not
    # across terms, so the fixture carries the SAME number in two of them --
    # HB1442 in 2025-2026 with 214-119, and an older HB1442 in 2023-2024 with
    # a different tally. A build that merges them shows the wrong vote count
    # on the current bill, which is what the checks below look for.
    w("rollcalls.json", {"2023-2024": {"HB1442": [
        {"year": "2024", "body": "H", "number": "310", "date": "2024-03-06",
         "time": "09:30", "bill": "HB1442", "procedural": False,
         "question": "Inexpedient to Legislate",
         "question_raw": "Inexpedient to Legislate",
         "question_plain": "kill the bill", "yeas": 190, "nays": 160,
         "voting": 350, "not_voting": 50, "seats": 400, "seated": 400,
         "vacancies": 0, "threshold_needed": None, "threshold_rule": None,
         "passed": True, "threshold_note": None,
         "title": "an entirely different bill of the same number"}]},
                         "2025-2026": {"HB1442": [
        {"year": "2026", "body": "H", "number": "310", "date": "2026-03-06",
         "time": "11:12", "bill": "HB1442", "procedural": False,
         "question": "Ought to Pass", "question_raw": "Ought to Pass",
         "question_plain": "pass the bill", "yeas": 214, "nays": 119, "voting": 333,
         "not_voting": 67, "seats": 400, "seated": 400, "vacancies": 0,
         "threshold_needed": None, "threshold_rule": None, "passed": True,
         "threshold_note": None, "title": "relative to insurance coverage"}],
                         # A VOTE ON NO BILL (23 October 2026): a member's
                         # unanimous consent objected to, and the House's vote
                         # on whether they could go on, the same day as HB
                         # 1442's -- with what the Journal says of it, below.
                         "_procedural": [
        {"year": "2026", "body": "H", "number": "311", "date": "2026-03-06",
         "time": "13:10", "bill": None, "procedural": True,
         "question": "Shall Member Continue", "question_raw": "Shall Member Continue",
         "question_plain": "", "yeas": 91, "nays": 82, "voting": 173,
         "not_voting": 227, "seats": 400, "seated": 400, "vacancies": 0,
         "threshold_needed": None, "threshold_rule": None, "passed": False,
         "threshold_note": None, "title": "", "outcome_source": "journal"},
        {"year": "2026", "body": "H", "number": "312", "date": "2026-03-06",
         "time": "11:05", "bill": None, "procedural": True,
         "question": "Divide", "question_raw": "Divide",
         "question_plain": "", "yeas": 150, "nays": 180, "voting": 330,
         "not_voting": 70, "seats": 400, "seated": 400, "vacancies": 0,
         "threshold_needed": None, "threshold_rule": None, "passed": False,
         "threshold_note": None, "title": "", "outcome_source": "journal"}]}})
    # What the Journal says the vote on no bill was about, as
    # src/parse/journal_motions.py writes it, and a division the Journal
    # alone records: _NB_FIXTURE, beside the checks that read it.
    (root / "journal_motions.json").write_text(json.dumps(_NB_FIXTURE), encoding="utf-8")
    # The Senate's own committee reports, from the General Court's database.
    # Two of them on one bill, which is what a bill re-referred to committee
    # and reported again looks like. The second deliberately shares its
    # recommendation with the HOUSE report event above and has no Senate
    # docket line of its own: joining these to the docket on the wording alone
    # gave 364 real Senate reports a House Calendar citation and the day the
    # House committee signed.
    # {term: {bill: [reports]}}: bill numbers repeat every biennium.
    w("senate_reports.json", {"2025-2026": {"HB1442": [
        {"bill": "HB1442", "title": "AN ACT relative to insurance coverage.",
         "source": "Senate committee report, released 2026-04-17",
         "date": "2026-04-17", "dated": "printed", "body": "S",
         "calendar": "Regular Calendar",
         "majority_recommendation": "REFERRED TO INTERIM STUDY",
         "minority_recommendation": "",
         "reports": [{"side": "Committee", "author": "Senator Debra Altschiller",
                      "committee": "Judiciary", "vote_yeas": 5, "vote_nays": 0,
                      "amendment": "",
                      "text": "The committee heard testimony that the coverage "
                              "question turns on federal rules still in flux, "
                              "and would rather study it than guess."}]},
        {"bill": "HB1442", "title": "AN ACT relative to insurance coverage.",
         "source": "Senate committee report, released 2026-06-02",
         "date": "2026-06-02", "dated": "printed", "body": "S",
         "calendar": "Consent Calendar",
         "majority_recommendation": "OUGHT TO PASS",
         "minority_recommendation": "",
         "reports": [{"side": "Committee", "author": "Senator Tara Reardon",
                      "committee": "Judiciary", "vote_yeas": 4, "vote_nays": 1,
                      "amendment": "", "text": "The study answered it."}]}]}})
    w("bill_status.json", {
        # The database's chamber status is not always advanced once a bill is
        # finished: 21 real ones still read REPORT FILED or NO ACTION on bills
        # signed into law, and SB532, SB533 and SB576 read IN COMMITTEE after
        # the Senate adopted Inexpedient to Legislate on them 16-8. An
        # in-progress status must not outrank a dated floor vote that ended it.
        "SB900": {"gen_status": "SENATE", "house_status": "",
                  "senate_status": "IN COMMITTEE", "text_pdf": "",
                  "chapter": "", "lsr": "2026-0900", "body": "S"},
        "HB1442": {
            "gen_status": "PASSED/ADOPTED", "house_status": "PASSED/ADOPTED",
            "senate_status": "", "text_pdf": "https://gc.nh.gov/x.pdf",
            "chapter": "", "lsr": "2026-0503", "body": "H"},
        "HR10": {"gen_status": "HOUSE", "house_status": "PASSED/ADOPTED",
                 "senate_status": "", "text_pdf": "", "chapter": "",
                 "lsr": "2026-0900", "body": "H"}})
    # {term: {bill: [reports]}}: bill numbers repeat every biennium.
    w("committee_reports.json", {"2025-2026": {"HB1442": [
        {"bill": "HB1442", "title": "insurance coverage",
         "majority_recommendation": "OUGHT TO PASS", "minority_recommendation": None,
         "source": "House Calendar 9, 2026",
         "reports": [{"side": "Committee", "author": "Rep. Jodi Nelson",
                      "committee": "Commerce", "text": "The committee supports this.",
                      "vote_yeas": 19, "vote_nays": 0}]}]}})
    # A floor appearance WITH a boundary the clerk stated. This is not
    # decoration: build_site_v2 used to apply that boundary by rebinding `st`
    # to stations[-1], and `st` was already the bill's status record from 350
    # lines earlier. Every bill that took this branch -- 611 of 2,234 on the
    # real data -- then shipped with no facts block, no text link, and a
    # next_step that fell back to "In progress". The fixture had no floor row
    # at all, so 33 checks passed over it. It has one now.
    w("floor_index.json", {"HB1442": [
        {"date": "2026-03-06", "body": "H", "video_id": "VID2",
         "title": "House Session", "precise": True, "debate_end": 1500,
         "window_start": 100, "motions": ["Ought to Pass"], "tallies": []}]})
    # marks: {video: {bill: [candidate, ...]}}, as segment_markers writes it.
    w("candidate_segments.json", {
        "VID2": {"HB1442": [
            {"start": 600, "end": None, "what": "floor debate",
             "how": "the clerk reads the committee report"}]},
        # A start the chair announced, on a recording where the clustering put
        # the same executive session 80 minutes away. Its end belongs to that
        # other placement, not to this one, and pairing the two is how 429
        # proceedings came to carry an end before their own start.
        "VID4": {"HB1442": [
            {"start": 300, "end": None, "what": "executive session",
             "how": "the chair opens it"}]}})
    # Both files hold a bare key beside the year-suffixed one, because their
    # fetchers write both -- and the bare key holds whichever year was fetched
    # last. Here the bare HJ 7 is the 2026 journal, so a 2025 action citing
    # HJ 7 must NOT be linked to it. That shape put 4,468 of 12,970 links on
    # the real site onto a volume that does not contain the action.
    w("journals.json", {
        "HJ 7": "https://gc.nh.gov/house/calendars_journals/Journals/2026/"
                "HJ%2007%20March%206,%202026.PDF",
        "HJ 7 2026": "https://gc.nh.gov/house/calendars_journals/Journals/2026/"
                     "HJ%2007%20March%206,%202026.PDF"})
    # The viewer link carries the calendar's date in its filename, which is
    # what dates a report the docket did not date. Written once: this file was
    # written twice a few lines apart, and the second copy -- which had no date
    # in the URL -- silently replaced the first.
    w("calendars.json", {
        "HC 9": "https://gc.nh.gov/house/calendars_journals/viewer.aspx"
                "?fileName=calendars%5C2026%5CNo9%20February%2027%202026.pdf",
        "HC 9 2026": "https://gc.nh.gov/house/calendars_journals/viewer.aspx"
                     "?fileName=calendars%5C2026%5CNo9%20February%2027%202026.pdf"})
    w("testimony.json", {"HB1442": {"support": 10, "oppose": 2, "neutral": 0}})
    w("work/VID1/segments.json", [
        {"bill": "HB1442", "kind": "public hearing", "located": True, "why_not": "",
         "short": False, "tolerance": 30, "dp_start": 0, "dp_end": 900,
         "start": 150.0, "end": 900.0, "mentions_inside": 6, "mentions_total": 8,
         "purity": 0.7, "start_stated": True, "end_stated": True}])
    # Same bill, a different day, and the clustering is 4,700 seconds from
    # where the chair opened it -- far outside its own +/-30. Its end is
    # describing a different span and must not be attached to this one.
    w("work/VID4/segments.json", [
        {"bill": "HB1442", "kind": "executive session", "located": True,
         "why_not": "", "short": False, "tolerance": 30, "dp_start": 0,
         "dp_end": 6000, "start": 5000.0, "end": 5600.0, "mentions_inside": 3,
         "mentions_total": 5, "purity": 0.6}])
    row = {"bill": "HB1442", "body": "H", "committee": "Commerce",
           "proceeding": "public hearing", "sched_date": "2026-02-03",
           "sched_time": "10:00", "venue": "LOB 302", "tier": "A-unique-slot",
           "bills_in_slot": "1", "match": "single video", "video_id": "VID1",
           "video_title": "House Commerce", "stream_start": "09:58:00",
           "predicted_offset": "0:02:00",
           "watch_url": "https://youtube.com/watch?v=VID1", "candidates": "",
           "observed_start": "", "observed_end": "", "notes": ""}
    # The same bill's executive session, on a recording where the chair opened
    # it at 0:05:00 and the clustering put it at 1:23:20. Only one of those can
    # be where it happened, and the site takes the chair's -- so the
    # clustering's END, which measures the other one, has nothing to do with
    # this span.
    row4 = dict(row, proceeding="executive session", sched_date="2026-02-10",
                sched_time="13:00", video_id="VID4", video_title="House Commerce",
                stream_start="12:58:00",
                watch_url="https://youtube.com/watch?v=VID4")
    # A HEARING THAT HAS NOT HAPPENED YET, dated from the clock rather than
    # written down, so it is still in the future whenever this runs.
    #
    # home.json's "upcoming" is only built for proceedings in the next
    # fortnight, and every other fixture date here is fixed and in the past, so
    # that code never ran under preflight at all -- see _upcoming_shape for what
    # was waiting in it. A field that is only populated on some days needs a
    # fixture that populates it on all of them.
    from datetime import date as _date, timedelta as _td
    row5 = dict(row, bill="HB1443", proceeding="subcommittee work session",
                sched_date=(_date.today() + _td(days=3)).isoformat(),
                sched_time="09:30", video_id="", video_title="",
                stream_start="", predicted_offset="", watch_url="",
                match="no video found")
    with open(root / "verification_manifest.csv", "w", newline="",
              encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(row))
        wr.writeheader()
        wr.writerow(row)
        wr.writerow(row4)
        wr.writerow(row5)
    # The site reads proceedings.csv, not the manifest. Build it the way
    # build_all does, from the two sources the fixture just wrote.
    import subprocess, sys
    for f in PROCEEDINGS_MODULES:
        if _paths.locate(f).exists():
            (root / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(_paths.locate(f), root / f)
    r = _run([sys.executable, "build_proceedings.py"], cwd=root,
                       capture_output=True, text=True)
    assert r.returncode == 0, "fixture proceedings: " + (r.stderr or r.stdout)[-200:]
    _fixture_videos(root)


# THE FIXTURE'S VIDEO INDEX (the Videos tab, 26 October 2026), as
# fetch_channel_index writes collected/videos/videos_<chamber>_*.csv: the
# three recordings proceedings.csv names (VID1 and VID4, House Commerce's;
# VID2, the House's session of 6 March), and four it does not -- a House
# Commerce meeting no bill row places (the Videos tab lists it by its title),
# a stream of Commerce's still to come (not listed: it has not run), a title
# in the older form (not listed: the index could not parse it) and a
# division of House Finance, a committee the fixture has no page for.
FIXTURE_VIDEO_COLS = ["video_id", "title", "title_parsed", "parsed_committee", "parsed_date",
                      "date_from", "has_start_time", "start_eastern", "actual_start_utc",
                      "actual_end_utc", "duration_iso", "published_at"]
FIXTURE_VIDEOS = {"house": [
    ("VID1", "House Commerce (02/03/2026)", "yes", "Commerce", "2026-02-03",
     "2026-02-03 09:58:00", "PT1H52M3S"),
    ("VID4", "House Commerce (02/10/2026)", "yes", "Commerce", "2026-02-10",
     "2026-02-10 12:58:00", "PT45M"),
    ("VID2", "House Session (03/06/2026)", "yes", "Session", "2026-03-06",
     "2026-03-06 09:58:51", "PT5H2M45S"),
    ("cmteTitleV1", "House Commerce (02/24/2026)", "yes", "Commerce", "2026-02-24",
     "", "PT36M10S"),
    ("cmteSoonV02", "House Commerce (11/30/2026)", "yes", "Commerce", "2026-11-30", "", "P0D"),
    ("cmteOldV003", "Commerce 1/26/21", "NO", "", "", "2021-01-26 10:00:00", "PT1H"),
    ("financeDiv2", "House Finance - Division II (02/24/2026)", "yes", "Finance - Division II",
     "2026-02-24", "2026-02-24 13:00:00", "PT2H"),
    # The fixture commission's meeting of 10 March 2026, which the Calendar's
    # matcher gives it by name and day (build_calendar.study_recordings).
    ("agingVid001", "State Commission on Aging (03/10/2026)", "yes", "State Commission on Aging",
     "2026-03-10", "2026-03-10 10:02:11", "PT1H2M")],
    # The Senate's session of 19 February 2026, which no bill's moment names:
    # the chamber's page takes it by the channel's own title for the day.
    "senate": [
    ("senSessV001", "Senate Session (02/19/2026)", "yes", "Session", "2026-02-19",
     "2026-02-19 09:58:00", "PT3H4M")]}


def _fixture_videos(root):
    """collected/videos/videos_<chamber>_fixture.csv, FIXTURE_VIDEOS."""
    d = Path(root) / "collected" / "videos"
    d.mkdir(parents=True, exist_ok=True)
    for ch, rows in FIXTURE_VIDEOS.items():
        with open(d / f"videos_{ch}_fixture.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(FIXTURE_VIDEO_COLS)
            for vid, title, parsed, cmte, day, start, length in rows:
                w.writerow([vid, title, parsed, cmte, day, "title", "yes" if start else "no",
                            start, "", "", length, ""])


# What build_proceedings.py needs beside it to run in a folder of its own: the
# table's reader, and committee_names.py with the two modules it reads, since
# every committee row's name is settled there before the table is written;
# and _paths.py, which its bootstrap looks for above it. Each is copied from
# whichever code folder holds it, flat: in the fixture's folder every one is
# found by its bare name, as in the repository. terms.py reads the state's
# settings (16 November 2026), so state_settings.py comes too, and its file at
# the place under the root where it looks (each copy makes the folder).
PROCEEDINGS_MODULES = ("_paths.py", "build_proceedings.py", "proceedings.py",
                       "committee_names.py", "referrals.py", "names.py", "terms.py",
                       "state_settings.py", "src/lib/state_settings.json")


CHAIN_NEEDS = ["build_site_v2.py", "build_search_index.py", "build_pages.py",
               "build_bill_pages.py",
               "build_session_pages.py", "session_days.py", "journal_days.py",
               "build_legislator_pages.py", "build_committees.py", "build_study_committees.py",
               "build_civics.py", "build_town_pages.py", "build_indexes.py",
               "build_exports.py", "build_feeds.py", "check_site.py",
               "app.css", "app.js", "bills.html",
               "build_district_map.py", "map.js", "map.css", "build_votes_page.py"]


def _stand_in_png():
    """A real 1x1 PNG, grey with alpha: what a mask file is, as small as one
    can be."""
    import struct
    import zlib

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 4, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\xff"))
            + chunk(b"IEND", b""))


# What the fixture's licensed lockup holds, so a check can tell which of the
# two lockups the build put in the site.
LICENSED_STAND_IN = b"licensed"


def _fixture_brand(here, root, brand=True):
    """The fixture's assets/: the tracked manifest, and stand-ins for the logo.

    THE REAL FILES ARE NOT COPIED ANY MORE (1 October 2026). This used to be
    shutil.copytree(here / "assets"), which made the fixture three different
    sites: the laptop's carried the artist's logo over the clipart, GitHub's
    machine carried whatever the kit had brought, and a clone -- since the
    logo and icons left the repository on 1 October -- carried none, and
    failed _chain ("style.css asks for /lockup.png") and _links_resolve ("312
    links to 4 paths") on a tree with nothing wrong with it.

    So the fixture writes its own: a small stand-in under every name in
    build_pages.BRAND_FILES, laid out as the real ones are -- the clipart in
    assets/, and in assets/licensed/ a lockup that must win over the clipart
    one and the header's mark, which has no clipart twin. No builder opens an
    image, so what is in them does not matter; that they are placed does.
    brand=False is a clone: the manifest, which is tracked, and nothing else.
    """
    sys.path.insert(0, str(here))
    import build_pages as BP
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    manifest = here / "assets" / "site.webmanifest"
    if manifest.exists():
        shutil.copy2(manifest, assets / manifest.name)
    if not brand:
        return
    png = _stand_in_png()
    for name in BP.BRAND_FILES:
        if name == manifest.name:
            continue
        (assets / name).write_bytes(
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>'
            if name.endswith(".svg") else png)
    (assets / "licensed").mkdir(exist_ok=True)
    (assets / "licensed" / "lockup.png").write_bytes(png + LICENSED_STAND_IN)
    (assets / "licensed" / BP.HEADER_MARK).write_bytes(png)


def _study_fixture(root):
    """The fixture's statutory and study committees (18 October 2026), as
    the database copy holds them in db/: a commission set up by a fixture
    bill under a fixture statute, with a sitting representative in its chair,
    a senator, a seat whose member is on no roster, two public members' seats
    described alike and one appointment that has lapsed; a study committee; a
    board the list marks non-legislative; and an archived committee, which
    has no page. Its meetings: one in the Calendar's fixture week, one
    cancelled, one of 1993. Returns {name: CommitteeID} of the active ones."""
    import build_study_committees as SC
    db = Path(root) / "db"
    db.mkdir(exist_ok=True)

    def row(cols, **v):
        return "|".join(str(v.get(c, "")) for c in cols)
    det = [
        dict(CommitteeID=1451, CommitteeYear=2026, CondensedBillNo="SB434",
             CommitteeName="STATE COMMISSION ON AGING", RSAChapter="91-A:4", ChapterLaw="0152:2",
             ReportDueDate="11/01/2026 00:00:00", ReportFiled="False",
             EffectiveDate="07/01/2026 00:00:00", CommitteeStatus="Active Statutory Committee",
             FirstMeeting="The first meeting shall be called by thehouse member.",
             Quorum="5 members", Report="The commission shall report annually.",
             AmendingBills="HB1442(2026)", CommitteeTypeID=7),
        dict(CommitteeID=1740, CommitteeYear=2026, CondensedBillNo="HB1442",
             CommitteeName="COMMITTEE TO STUDY SCHOOL BULLYING",
             CommitteeStatus="Active Chaptered Study Committee", CommitteeTypeID=13),
        dict(CommitteeID=69, CommitteeYear=1967,
             CommitteeName="NH RETIREMENT SYSTEM BOARD OF TRUSTEES ==NON-LEGISLATIVE==",
             RSAChapter="100-A:14", CommitteeStatus="Active Statutory Committee",
             CommitteeTypeID=7),
        dict(CommitteeID=44, CommitteeYear=2014, CondensedBillNo="HB1136",
             CommitteeName="VETERANS HOME STUDY", CommitteeStatus="Archived Chaptered Study Committee",
             CommitteeTypeID=6)]
    (db / "StatStudDetails.psv").write_text(
        "\n".join(row(SC.DETAILS, **d) for d in det) + "\n", encoding="utf-8")
    seat = dict(Active="True", Alternate="False", Designee="False", NonVotingMember="False",
                Chairperson="False")
    mem = [dict(seat, CommitteeID=1451, memberno=377204, MemberType=0, Chairperson="True",
                Organization="(a) Two members of the house, appointed by the speaker.",
                Affiliation="House"),
           dict(seat, CommitteeID=1451, memberno=377207, MemberType=1,
                Organization="(b) One senator.", Affiliation="Senate"),
           dict(seat, CommitteeID=1451, memberno=999999, MemberType=0,
                Organization="(c) A hydrogeologist, appointed by the governor.",
                Affiliation="Geological Survey"),
           dict(seat, CommitteeID=1451, memberno=9001, MemberType=2,
                Organization="(j) Fifteen members of the public, appointed by the governor.",
                Affiliation="Appt. by Governor"),
           dict(seat, CommitteeID=1451, memberno=9002, MemberType=2,
                Organization="(j)  Fifteen members of the public, appointed by the governor. "
                             "(Reappointed 12/12/24)", Affiliation="Appt. by Governor"),
           dict(seat, CommitteeID=1451, memberno=377207, MemberType=1, Active="False",
                Organization="(b) One senator.", Affiliation="Senate"),
           dict(seat, CommitteeID=69, memberno=9003, MemberType=2,
                Organization="2 TEACHERS, APPT BY GOV & COUNCIL", Affiliation="Teacher")]
    (db / "StatStudMembers.psv").write_text(
        "\n".join(row(SC.MEMBERS, **m) for m in mem) + "\n", encoding="utf-8")
    meets = [dict(MeetingID=7001, CommitteeID=1451, MeetingDate="03/10/2026 10:00:00",
                  MeetingLocation="LOB Room 101  Regular Meeting"),
             dict(webtext="==CANCELLED==", MeetingID=7002, CommitteeID=1451,
                  MeetingDate="03/12/2026 13:00:00",
                  MeetingLocation="==CANCELLED==LOB Room 102  Regular Meeting"),
             dict(MeetingID=12, CommitteeID=1451, MeetingDate="01/11/1993 10:00:00",
                  MeetingLocation="RM103, ST"),
             dict(MeetingID=7003, CommitteeID=44, MeetingDate="03/11/2026 10:00:00",
                  MeetingLocation="LOB Room 103  Regular Meeting"),
             # ANOTHER COMMITTEE'S MEETING UNDER THE SAME MeetingID, eighteen
             # years earlier, as the Nuclear Decommissioning Financing
             # Committee's of 2002 is beside a task force's of 2026: it takes
             # nothing of the commission's meeting -- not its room, not its
             # recording (build_study_committees.meetings_of).
             dict(MeetingID=7001, CommitteeID=1740, MeetingDate="06/14/2002 10:00:00",
                  MeetingLocation="LOB Room 104  Regular Meeting")]
    (db / "StatStudMeetings.psv").write_text(
        "\n".join(row(SC.MEETINGS, **m) for m in meets) + "\n", encoding="utf-8")
    (db / "vStatStudTemp.psv").write_text(
        "\n".join(row(SC.TEMP, **{k: d.get(k, "") for k in SC.TEMP}) for d in det) + "\n",
        encoding="utf-8")
    return {"State Commission on Aging": "1451", "Committee to Study School Bullying": "1740",
            "NH Retirement System Board of Trustees": "69"}


def _built_site(here, root, brand=True, env=None):
    """The fixture project, then build_all's builders over it, in build_all's
    order. Returns (the base address they were built with, how many ran).

    Two checks need a whole site and neither may build the real one: _chain,
    because importing a module never enters its main(), and _links_resolve,
    because a link is only a link once a builder has written it. They share
    this so that a builder added to the pipeline is added in one place.

    brand=False builds it as a fresh clone would: with no logo or icon file.
    env is laid over the builders' environment, for the check that states
    the build's date.
    """
    base, steps = _built_site_prepare(here, root, brand)
    return base, _built_site_run(root, steps, env)


def _built_site_prepare(here, root, brand=True):
    """The fixture project in `root`, and (the base address, the builders to
    run over it as (script, arguments, what it makes)): _built_site's first
    half, which a run does before any check so that the builders can go on
    beside the checks (_start_early_builds)."""
    _site_fixture(root)
    (root / "site").mkdir(exist_ok=True)
    shutil.copy2(here / "src/pages/bills.html", root / "site" / "bills.html")
    # What build_pages reads from its working directory, and the drawn
    # assets it copies into site/: without them every page links an icon
    # that is not there. The browser's files go into src/pages/ under the
    # fixture, as they sit in the repository, because that is where the
    # builders read them (_paths, THE BROWSER'S FILES).
    # find.js is in this list because the link check below went looking for it:
    # build_pages writes <script src="/find.js"> on every page and copies the
    # file from src/pages/, so a fixture without it built 33 pages asking for
    # a script that was not there.
    # alignment_score.json is here because about.html states this site's own
    # timing accuracy and about_figures.py refuses to publish a sentence it
    # has no number for -- so without it build_pages exits, and the fixture
    # build fails on a file that has nothing to do with the fixture. It is
    # small, tracked, and written by `probe_alignment.py --truth --score-out`,
    # which is the gate every timestamp method passes before it ships.
    # The district map's module and its committed geometry, which
    # build_district_map publishes with the map's data (9 October 2026).
    for name in ("src/pages/app.css", "src/pages/components.js", "src/pages/app.js",
                 "src/pages/bills.html", "src/pages/find.js", "src/pages/print.js",
                 "src/pages/print.css", "corrections/officials.json",
                 "generated/alignment_score.json",
                 "src/pages/map.js", "src/pages/map.css", "generated/district_geometry.json"):
        if (here / name).exists():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(here / name, root / name)
    _fixture_brand(here, root, brand)
    # The fixture's House committee, as data/committees.json names one, so
    # build_committees has a page to write; and the fixture's two towns, as
    # parse_districts writes them, so build_town_pages does.
    (root / "data" / "committees.json").write_text(json.dumps(
        {"H43": {"code": "H43", "name": "Commerce", "abbr": "COMMERCE"}}), encoding="utf-8")
    seat = {"congress": 1, "council": 3, "senate": 24, "house": [
        {"county": "Rockingham", "district": 13, "floterial": False, "seats": 2}]}
    # AND THE LEARN PAGE'S WORKED EXAMPLE, as the real map has it: Danville,
    # Brentwood and Fremont each a one-town district of their own, with the
    # floterial Rockingham 32 laid over all three. civics.reps_example draws
    # the finding-your-representatives diagram from these and stops the build
    # if its town is missing -- rightly, on the real map -- so the fixture
    # carries it rather than the diagram being skipped where it is absent.
    # Skipping it would have left the one path through that code the fixture
    # never runs, and a link to Danville's page that resolves to nothing.
    def floterial_town(own):
        return {"0": {"congress": 1, "council": 3, "senate": 23, "house": [
            {"county": "Rockingham", "district": own, "floterial": False, "seats": 1},
            {"county": "Rockingham", "district": 32, "floterial": True, "seats": 1}]}}
    (root / "site" / "districts.json").write_text(json.dumps(
        {"Raymond": {"0": seat}, "Stratham": {"0": seat},
         "Brentwood": floterial_town(6), "Fremont": floterial_town(7),
         "Danville": floterial_town(8)}), encoding="utf-8")
    # THE LAWS, FROM A TWO-SECTION TABLE (11 October 2026). Every header
    # links laws.html, so a fixture without the Laws pages is a site of
    # broken links; build_rsa.py reads this folder's table (--db) and a
    # citations file with no bills in it, since the fixture's bills cite none.
    cols = ["id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section", "SourceNote",
            "rsa", "EntireRSA", "titleNumber", "url"]
    (root / "db").mkdir(exist_ok=True)
    (root / "db" / "_columns.json").write_text(json.dumps({"NH_RSA": cols}), encoding="utf-8")
    (root / "db" / "_manifest.json").write_text(json.dumps(
        {"NH_RSA": {"rows": 3, "fetched": "2026-09-08T20:53:02"}}), encoding="utf-8")
    (root / "db" / "NH_RSA.psv").write_text("\n".join("|".join(r) for r in (
        ["1", "VI", "91-A", "91-A-4", "TITLE VI PUBLIC OFFICERS AND EMPLOYEES",
         "CHAPTER 91-A ACCESS TO GOVERNMENTAL RECORDS AND MEETINGS",
         "Section 91-A:4 Minutes and Records Available for Public Inspection.",
         "<p><b>Source.</b> 1967, 251:1. </p>", "",
         # The words the public-records guide's two counts rest on (guides.COUNT,
         # 23 October 2026), as the section prints them, so the guide is
         # published here as on the real table.
         "<codesect> I. Every citizen ... except as otherwise prohibited by RSA 91-A:5. IV. ... (b) "
         "... the public body or agency shall, within 5 business days of a request: (1) Make such "
         "record available ... VIII. ... for requests for electronic communications in excess of "
         "250 communications.</codesect>",
         "6", "VI\\91-A\\91-A-4.htm"],
        ["2", "VI", "91-A", "91-A-5", "TITLE VI PUBLIC OFFICERS AND EMPLOYEES",
         "CHAPTER 91-A ACCESS TO GOVERNMENTAL RECORDS AND MEETINGS", "Section 91-A:5 Exemptions.",
         "", "", "<codesect> The following governmental records are exempted</codesect>", "6",
         "VI\\91-A\\91-A-5.htm"],
        # RSA 404, the one chapter whose page is a folder's and whose address
        # ends in a slash, citing 91-A:4 so that 91-A's page links it back
        # (16 October 2026): _chapter_addresses_one_rule reads every built
        # file for an address of it without its slash.
        ["3", "XXXVII", "404", "404-1", "TITLE XXXVII INSURANCE",
         "CHAPTER 404 SAFETY FUNDS OF FIRE INSURANCE COMPANIES", "Section 404:1 Definitions.",
         "", "", "<codesect> In this chapter, see RSA 91-A:4.</codesect>", "37",
         "XXXVII\\404\\404-1.htm"])) + "\n", encoding="utf-8")
    (root / "rsa_citations.json").write_text(json.dumps(
        {"bills": {}, "enacted": {"91-A:4": [["1967", "251:1", ""]]}, "statute": {"404:1": ["91-A:4"]},
         "asof": {"laws_through": 2025}}), encoding="utf-8")
    _study_fixture(root)
    # THE ADDRESS BOX'S STREETS (24 October 2026): a few of the fixture's two
    # towns', in collected/nh_streets.json's shape, for build_addr_index.
    (root / "collected").mkdir(exist_ok=True)
    (root / "collected" / "nh_streets.json").write_text(json.dumps({"rows": [
        ["Main St", "Raymond", "03077", "1-199 2-198"],
        ["Epping St", "Raymond", "03077", "1-99 2-98"],
        ["Portsmouth Ave", "Stratham", "03885", "1-299 2-298"]]}), encoding="utf-8")
    base = "https://graniterecord.org"
    steps = [
        # meta.json and the term files it names are the bill index; the
        # one-file index.json is retired (_index_json_retired).
        ("build_site_v2.py", ["--data", "data", "--out", "site",
                              "--segments", "work"], "site/meta.json"),
        # IN BUILD_ALL'S ORDER, after the site data whose indexes it reads
        # (2 October). The fixture carries no bill text, which the builder is
        # told and says in its manifest (--allow-no-text); check_site then
        # warns of the term without text and refuses nothing. Without this
        # step check_site refuses the fixture's site as it would a real one:
        # bill indexes and no search index beside them. Until then no check
        # ran this script's main() at all.
        ("build_search_index.py", ["--idx", "site/idx", "--out", "site/sidx",
                                   "--allow-no-text"], "site/sidx/manifest.json"),
        ("build_pages.py", ["--out", "site"], "site/officials.html"),
        ("build_bill_pages.py", ["--site", "site", "--base", base],
         "site/sitemap.xml"),
        ("build_legislator_pages.py", ["--site", "site", "--base", base],
         "site/legislator"),
        # After the bill pages, as in build_all: it reads their stations.
        ("build_committees.py", ["--site", "site", "--data", "data",
                                 "--base", base], "site/committees.json"),
        ("build_civics.py", ["--site", "site", "--base", base], "site/resources.html"),
        ("build_rsa.py", ["--site", "site", "--base", base, "--db", "db"], "site/laws.html"),
        # The statutory and study committees' pages, after the Laws pages
        # whose headings name their statutes, as build_all runs it.
        ("build_study_committees.py", ["--site", "site", "--base", base],
         "site/study_committees.json"),
        ("build_town_pages.py", ["--site", "site", "--base", base], "site/town"),
        # The address box's street files, after the town pages, as in build_all.
        ("build_addr_index.py", ["--site", "site"], "site/addr/ma.json"),
        # The district map's data, after the town pages, as in build_all.
        ("build_district_map.py", ["--site", "site"], "site/district_map.json"),
        ("build_indexes.py", ["--site", "site", "--base", base],
         "site/directory.html"),
        # Before the calendar, whose floor cards link to these, and after the
        # legislator pages it resolves speaker names against. BOTH CHAMBERS,
        # the Senate first, as build_all runs them (2 October 2026): the
        # directory lists every day each chamber sat, so a fixture that built
        # the House's pages alone listed a Senate day with no page behind it.
        # IN ONE RUN since 16 October 2026 (private/BUILD_SPEED.md, D), --body
        # S,H, as build_all runs it now: the sitting days are loaded once.
        ("build_session_pages.py", ["--site", "site", "--base", base, "--body", "S,H"],
         "site/session/H"),
        # The votes not on a bill, a page a term, after the session days whose
        # anchors it links and before the chambers' pages that link it, as
        # build_all runs it (23 October 2026).
        ("build_nobill_votes.py", ["--site", "site", "--base", base], "site/session/nobill"),
        # The votes page, after the votes files it reads (build_all runs it after build_votes).
        ("build_votes_page.py", ["--site", "site", "--base", base], "site/votes.html"),
        # The chambers' cards on the Committees page and their pages, after
        # both chambers' term files, as build_all runs it.
        ("build_full_sessions.py", ["--site", "site", "--base", base], "site/session/house.html"),
        # After the committees, whose codes it needs to link a card, and in
        # build_all's own order. Its output is what the Calendar tab points
        # at, so a fixture without it builds a nav link to nothing -- which
        # is how the link check found this step was missing here at all.
        ("build_calendar.py", ["--site", "site", "--base", base],
         "site/calendar.html"),
        # IN BUILD_ALL'S ORDER, and the order matters here now. data.html
        # describes the feeds, counted off the files on disk, so a chain that
        # ran the exports first would build a page with no Feeds section and
        # test nothing -- which is exactly the shape of the bug this pair was
        # swapped to fix.
        ("build_feeds.py", ["--site", "site", "--base", base],
         "site/feed/all.xml"),
        ("build_exports.py", ["--site", "site", "--base", base],
         "site/data/manifest.json"),
    ]
    return base, steps


def _built_site_run(root, steps, env=None, run=None):
    """_built_site's second half: the builders over the fixture, in order.
    Returns how many ran. `run` is the function that starts them (_run)."""
    run = run or _run
    ran = 0
    for script, args, produces in steps:
        if not _paths.locate(script).exists():
            continue
        r = run([sys.executable, _paths.script(script), *args],
                cwd=root, capture_output=True, text=True, timeout=180, env=env)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout).strip().splitlines()
            raise AssertionError(f"{script}: " + (tail[-1][:120] if tail else "?"))
        assert (root / produces).exists(), f"{script} produced no {produces}"
        ran += 1
    # SILENCE IS NOT SUCCESS. A chain that ran no builder at all would have
    # satisfied every assertion above by never reaching one.
    assert ran == len(steps), f"only {ran} of {len(steps)} builders were there to run"
    return ran


# ONE BUILD OF THE FIXTURE A RUN, FOR THE CHECKS THAT READ IT AS IT IS BUILT (2
# October 2026). build_site_v2.py was started more than a dozen times a run,
# and five of those were the same build of the unchanged fixture, each thrown
# away after one check had read it: _upcoming_shape,
# _disposed_beats_stale_status, _senate_reports, _rollcalls_by_term and
# _chain_output. _chain and _addresses_have_slash each ran all twelve builders
# over it. Those are two builds now -- build_site_v2 alone, whose per-bill
# files the later builders fold into the pages, and the whole chain -- made
# the first time a check asks and deleted when the run ends.
#
# EACH CHECK IS HANDED A COPY, in the folder it made and will delete, so it
# reads and writes there as it always did: copying a fixture's few hundred
# small files takes a tenth of a second, where building them took one to
# four. A check that changes the fixture BEFORE it builds still builds its
# own. And a build that fails, fails every check that takes a copy, in the
# builder's own words: what it raised is kept and raised again.
_MADE_ONCE = {}


def _once_a_run(what, make):
    """make() the first time this run asks for `what`; after that what it
    returned, or raised. Where the run keeps the map, what make() read and
    ran is given to every check that asks (pf_core._map_kept)."""
    with _map_kept(what):
        if what not in _MADE_ONCE:
            try:
                _MADE_ONCE[what] = (make(), None)
            except Exception as e:                              # noqa: BLE001
                _MADE_ONCE[what] = (None, e)
    got, err = _MADE_ONCE[what]
    if err is not None:
        raise err
    return got


def _shared_root(prefix):
    """A folder under the system temp directory that goes when the run ends."""
    import atexit
    root = Path(tempfile.mkdtemp(prefix=prefix))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    return root


def _fixture_site_v2(root):
    """The fixture project with build_site_v2.py run over it, copied into
    `root` -- an empty folder the caller made and deletes -- from the run's
    one build of it. Returns that build's finished run, for the caller to
    assert on as it did on its own."""
    def build():
        here = Path(".").resolve()
        shared = _shared_root("gr-fixture-v2-")
        _site_fixture(shared)
        return shared, _run([sys.executable, _paths.script("build_site_v2.py"),
                             "--data", "data", "--out", "site", "--segments", "work"],
                            cwd=shared, capture_output=True, text=True, timeout=180)
    shared, r = _once_a_run("build_site_v2.py over the fixture", build)
    shutil.copytree(shared, root, dirs_exist_ok=True)
    return r


def _fixture_site_shared():
    """(where it stands, base, how many builders ran, the days it was built
    on): _built_site(), once a run. For reading only -- nothing may write
    under it; a check that writes takes a copy (_fixture_site_whole). The
    days are the build's own, for a check that asks which day a page cites or
    which week the calendar was built in: one day, or two where the builders
    ran across midnight, and then a builder wrote whichever it started on, so
    a check holds what it reads to either."""
    def build():
        from datetime import date
        early = _early_build("shared")
        if early is not None:
            return early[0], early[1], early[2], early[3]
        shared = _shared_root("gr-fixture-site-")
        started = date.today()
        base, ran = _built_site(Path(".").resolve(), shared)
        return shared, base, ran, sorted({started, date.today()})
    return _once_a_run("every builder over the fixture", build)


def _fixture_site_whole(root):
    """_built_site(here, root), from the run's one build: the built project
    is copied into `root`, an empty folder the caller made and deletes, and
    (base, how many builders ran) returned as _built_site returns them."""
    shared, base, ran, _days = _fixture_site_shared()
    shutil.copytree(shared, root, dirs_exist_ok=True)
    return base, ran

# THREE FIXTURE SITES ARE BUILT BESIDE THE CHECKS, NOT IN THEIR WAY (11
# November 2026). A full run builds the fixture site three times, each a
# chain of twenty builders and each by a different check for a reason of its
# own: with its logo and icons (_fixture_site_shared, which most checks read),
# with none, as a clone builds it (_links_resolve), and with a day stated
# (_build_date_stated). They share nothing, so the second and third were built
# by their checks in sequence with the first -- about a minute of the code
# checks' fifteen. main() now prepares all three before the first check runs
# (the fixture's files, a second or two each) and starts their builders in
# threads: the builders are child processes, so the threads only wait. The
# check that wants a site takes the finished one: _fixture_site_shared its
# own, the others a copy of theirs in the folder they made, as every check that
# reads the shared one does. What a check sees is what it saw: the same fixture
# built the same way by the same builders; one that fails fails the check that
# asks for it, in the builder's own words. A run of the built site's checks or
# of the data's (--built, --data) starts none, a run that chooses its checks
# (--changed) starts those its chosen checks take (_early_wanted, below), and a
# site no check asks for is built and deleted unread. Each child is started
# with the environment as main() began it, and by the real child.run: a check
# that sets a variable or stands a stub in for run() for a moment, as several
# do, cannot reach a build that is going on beside it.
_EARLY = {}
# The early builds' threads are named for it, and the run's map (pf_runner, "the
# map") gives what they read and ran to _EARLY_MAP, which every check that takes
# an early build takes.
_EARLY_THREADS = "fixture"
_EARLY_MAP = "the early builds"


def _start_early_builds(only=None):
    """Prepare the fixture sites above and start their builders: every one,
    or those `only` names, and none where it names none; _EARLY holds each as
    (where it stands, base address, environment it is built with, the day it
    was started, its builders' future)."""
    import concurrent.futures
    from datetime import date, timedelta
    if only is not None and not only:
        return
    build_date = imp("build_date")
    here = Path(".").resolve()
    if build_date is None or [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]:
        return
    real_run = child.run
    env = dict(os.environ)
    day = date.today() - timedelta(days=2)
    stated = {build_date.ENV: day.isoformat()}
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix=_EARLY_THREADS)
    for what, brand, made_with in (("shared", True, env), ("nobrand", False, env),
                                   ("stated", True, stated)):
        if only is not None and what not in only:
            continue
        root = _shared_root(f"gr-early-{what}-")
        try:
            base, steps = _built_site_prepare(here, root, brand)
        except Exception:                                       # noqa: BLE001
            continue        # the check that asks builds its own, and says why
        _EARLY[what] = (root, base, made_with, date.today(),
                        pool.submit(_built_site_run, root, steps, made_with, real_run))
    pool.shutdown(wait=False)


def _early_build(what, made_with=None):
    """(where it stands, base address, how many builders ran, the days it was
    built on) of the early build of `what`, waited for, or None where none was
    started, it was taken already, or it was built with another environment
    than `made_with`. A build that failed raises what its builders raised."""
    from datetime import date
    got = _EARLY.get(what)
    if got is None or (made_with is not None and got[2] != made_with):
        return None
    del _EARLY[what]
    root, base, _env, started, future = got
    with _map_kept(_EARLY_MAP):
        ran = future.result()
    return root, base, ran, sorted({started, date.today()})


def _built_nobrand(here, root):
    """_built_site(here, root, brand=False)'s base address, from the early
    build where there is one: the built project is copied into `root`."""
    got = _early_build("nobrand")
    if got is None:
        return _built_site(here, root, brand=False)[0]
    shutil.copytree(got[0], root, dirs_exist_ok=True)
    return got[1]


def _built_stated(here, root, stated):
    """_built_site(here, root, env=stated), from the early build where there is
    one made with that environment."""
    got = _early_build("stated", stated)
    if got is None:
        return _built_site(here, root, env=stated)[0]
    shutil.copytree(got[0], root, dirs_exist_ok=True)
    return got[1]


# WHICH CHECK TAKES WHICH (16 November 2026, the refactor's stage 1, step 2).
# A run that chooses its checks (--changed) built none of the three beside
# them, so the first check that asked for each built it in its own time: 40 s
# for _search_says_counts, 54 to 110 s for _links_resolve and 44 s for
# _build_date_stated in the --changed runs of 8 to 11 November, where a run of
# the suite gave them 1, 18 to 27 and 5 to 9. It starts those its chosen checks
# take, and only those: a check takes one through the function that hands it
# over, which _early_wanted looks for in its code and in every function of the
# suite's it calls (_reaching). What a check is handed is the same either way,
# the early build or one made when it asks, so this decides how long the run
# takes and nothing it finds.
_EARLY_TAKEN_BY = {"shared": "_fixture_site_shared", "nobrand": "_built_nobrand",
                   "stated": "_built_stated"}


def _early_wanted(checks):
    """The early builds, by their names in _EARLY, that some check of
    `checks` takes: one whose code reaches the function that hands it over
    (_EARLY_TAKEN_BY)."""
    return {what for what, by in _EARLY_TAKEN_BY.items() if _reaching({by}, checks=checks)}
