#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.8
"""
What every file of the data API holds, field by field: /data/schema.json.

    import api_schema
    api_schema.package(tables, files)   -> the Data Package schema.json is

docs/design/api/DESIGN.md, 2.2 and 4. A Frictionless Data Package
(datapackage v1), so that pandas, R and the frictionless tools read it, with
one field of this project's own on every field, "x-stability":

  stable     after 1 February 2027 it is only ever added to, never renamed,
             retyped or removed
  beta       may still change; the change is announced first (Q11)
  page       a bill's page draws it; present and described, promised nothing
  undocumented  a field a bill record carries that this file has not
             described yet: listed so a reader knows it is there

Every column of every API CSV, of people.csv and of every table in the
database must be described here: build_exports stops on one that is not, so
a column is never published unexplained. So it does on a foreign key
tonight's files break. A bill record's field, or a field inside its
stations, that is not described is listed as undocumented and does not stop
the build, because the records are the pages' and the pages change.

No file carries YouTube's own metadata (Q18): a recording is its id, and
the moment in it is this site's.
"""

FORMAT = 1

# ---------------------------------------------------------------- the CSVs --
# Each column: (type, description, stability). Types are the Table Schema's.
S, B, P = "stable", "beta", "page"

BILL_KEY = "bill + term is the key: a bill number names a different bill in every term."
PERSON = ("One of the General Court's own numbers for the person: their earliest PersonID, "
          "else their earliest employee number (the ones they first voted under). Chosen "
          "once, and never given to anyone else.")

CSV = {
    "bills.csv": {
        "term": ("string", "The two-year term, 2025-2026.", S),
        "year": ("integer", "The year the bill was filed under.", S),
        "bill": ("string", "The bill's number, HB1442. " + BILL_KEY, S),
        "title": ("string", "The bill's title.", S),
        "sponsor": ("string", "The prime sponsor's name, where the record names one.", S),
        "committee": ("string", "The committees it was referred to, joined by '; '.", S),
        "topic": ("string", "The topic it is filed under.", S),
        "status": ("string", "How it stands or how it ended, in full: Killed, Vetoed, override failed.", S),
        "outcome": ("string", "The kind of that status: active, law, done, veto, study or adopted.", S),
        "passage": ("string", "Where it started (H or S), then one character a stop: p passed, x stopped, h is there now, - not reached.", S),
        "roll_calls": ("integer", "Roll calls on the bill itself, procedural ones left out.", S),
        "chapter": ("string", "The chapter of that year's session laws it became.", S),
        "chip": ("string", "The word its card shows: Became Law, Died, Interim Study, Tabled, Vetoed, Withdrawn, or its stage.", S),
    },
    "legislators.csv": {
        "id": ("string", "This site's member id: the General Court's PersonID, or its employee number where there is none.", S),
        "name": ("string", "The member's name as the roster gives it.", S),
        "chamber": ("string", "House or Senate.", S),
        "party": ("string", "Party.", S),
        "district": ("string", "District.", S),
        "county": ("string", "County.", S),
        "email": ("string", "The official address the General Court publishes.", S),
        "committees": ("string", "Committee seats, joined by '; '.", S),
        "bills_sponsored": ("integer", "Bills they have put their name to.", S),
        "recorded_votes": ("integer", "Roll calls they voted in.", S),
        "person": ("string", "Their person number in people.json.", S),
    },
    "rollcalls.csv": {
        "roll_call": ("string", "year-body-number, the key the vote files use.", S),
        "term": ("string", "The two-year term.", S),
        "year": ("integer", "The year of the vote.", S),
        "body": ("string", "H or S.", S),
        "number": ("integer", "The roll call's number in that chamber's year.", S),
        "date": ("date", "The day, YYYY-MM-DD.", S),
        "bill": ("string", "The bill voted on, as the record writes it; empty for a vote on no "
                           "bill. Some name what bills.csv has no row for -- a House resolution "
                           "(HR), a motion to suspend the rules (SUSPRULE) -- so not every one "
                           "joins bills.csv.", S),
        "question": ("string", "The question in the record's words.", S),
        "question_plain": ("string", "The question in plain English, where one could be made.", S),
        "yeas": ("integer", "Yeas.", S),
        "nays": ("integer", "Nays.", S),
        "not_voting": ("integer", "Members recorded as not voting.", S),
        "passed": ("integer", "1 where the motion carried, as the record states it (outcome_source).", S),
        "procedural": ("integer", "1 for a procedural vote, such as suspending the rules.", S),
        "threshold_needed": ("string", "What it needed where that was more than a majority.", S),
        "threshold_rule": ("string", "The rule that set that threshold.", S),
        "outcome_source": ("string", "Where passed comes from: docket, docket, implied, journal, count or rule.", S),
    },
    # No YouTube metadata (a recording's title, the stream's scheduled
    # offset): no download carries it (the owner, 5 November 2026; Q18).
    "proceedings.csv": {
        "term": ("string", "The two-year term.", S),
        "bill": ("string", "The bill, as the docket or the calendar writes it. " + BILL_KEY
                 + " A few rows of the oldest terms write it otherwise (HB 0306) and do not join "
                 "bills.csv.", S),
        "body": ("string", "H or S.", S),
        "kind": ("string", "public hearing, executive session, work session, floor session and the like.", S),
        "date": ("date", "The day, YYYY-MM-DD.", S),
        "time": ("string", "The time called, HH:MM.", S),
        "committee": ("string", "The committee.", S),
        "venue": ("string", "The room.", S),
        "video_id": ("string", "The recording's YouTube id, where one was matched.", B),
        "start_seconds": ("number", "Where in the recording this site places the bill's start.", B),
        "end_seconds": ("number", "Where it places the end.", B),
        "how_placed": ("string", "How the start was found: stated, floor_stated, floor_precise, located, whole_video, floor_dated; approximate, consent or empty where no moment was found.", B),
        "end_how": ("string", "How the end was found.", B),
    },
    "sponsors.csv": {
        "term": ("string", "The two-year term.", S),
        "bill": ("string", "The bill. " + BILL_KEY, S),
        "member_id": ("string", "This site's member id; empty where the name is not matched to a member.", S),
        "member": ("string", "The sponsor as the record names them.", S),
        "party": ("string", "Party.", S),
        "chamber": ("string", "H or S, the chamber they sat in for this bill.", S),
        "prime": ("integer", "1 for the prime sponsor.", S),
        "role": ("string", "Their role where the record gives one.", S),
        "source": ("string", "Where the name was read: the sponsor file, the sponsor record, the bill's printed text, or the House Journal.", S),
        "person": ("string", "Their person number in people.json; empty where member_id is.", S),
    },
    "votes-<term>.csv": {
        "roll_call": ("string", "year-body-number; joins rollcalls.csv.", S),
        "term": ("string", "The two-year term.", S),
        "date": ("date", "The day, YYYY-MM-DD.", S),
        "bill": ("string", "The bill voted on; empty for a vote on no bill.", S),
        "question": ("string", "The question in the record's words.", S),
        "member_id": ("string", "This site's member id; people.csv gives the person.", S),
        "member": ("string", "The member's name.", S),
        "party": ("string", "Party at the vote.", S),
        "chamber": ("string", "House or Senate.", S),
        "vote": ("string", "Yea, Nay, Not Voting/Excused, Not Voting/Not Excused, Presiding, or No vote recorded; empty on the few ballots the record leaves blank.", S),
    },
    "people.csv": {
        "person": ("string", PERSON, S),
        "number_kind": ("string", "employee_number, person_id or member_id; replaced_by on a retired person number.", S),
        "number": ("string", "The number; on a replaced_by row, the person number that replaces it.", S),
        "name": ("string", "The person's name.", S),
        "page": ("string", "Their page on this site.", S),
    },
}

# Only the keys every row keeps: a foreign key a tool checks must hold on
# every row, and rollcalls.csv's bill does not (it names resolutions and
# motions bills.csv has no row for). build_exports checks each one against
# tonight's files and stops on a break.
KEYS = {
    "bills.csv": (["term", "bill"], []),
    "rollcalls.csv": (["roll_call"], []),
    "votes-<term>.csv": ([], [(["roll_call"], "rollcalls", ["roll_call"])]),
    "sponsors.csv": ([], [(["term", "bill"], "bills", ["term", "bill"])]),
    "legislators.csv": (["id"], []),
    "people.csv": ([], []),
}

# --------------------------------------------------- a bill's full record --
BILL_FIELDS = {
    "key": ("string", "term/bill, 2025-2026/HB1442: the bill's key everywhere in the API.", S),
    "id": ("string", "The bill's number, HB1442.", S),
    "year": ("integer", "The year it was filed under.", S),
    "term": ("string", "The two-year term.", S),
    "title": ("string", "Its title.", S),
    "sponsors": ("array", "Who put their name to it, prime first: member_id, name, party, chamber, prime, and display labels.", S),
    "events": ("array", "The docket, line by line: date, text, plain (the line in plain words), cite and cite_url (the journal or calendar it is printed in), and on a public hearing testimony, the sign-in counts.", S),
    "rollcalls": ("array", "Each floor vote on it: date, body, question, yeas, nays, passed, threshold, and tally, the votes by party.", S),
    "reports": ("array", "Committee reports with their reasoning: House calendar reports, Senate committee reports and interim study statements (interim true), each with its sides (majority, minority) and their text, author and vote.", S),
    "docket_reports": ("array", "Reports the docket records that no printed report carries: committee, side, recommendation, vote, amendment.", S),
    "report_actions": ("array", "What the chamber did between one report and the next.", S),
    "study_report": ("object", "The docket's line on an interim study: recommended or not, and the vote.", S),
    "amendments": ("array", "The amendments it went through, in order: number, kind, date, body, adopted, and the text where a calendar printed it.", S),
    "billtext": ("object", "The text of the current printing: version, title, analysis, fiscal note and body.", S),
    "chapter": ("string", "The chapter of the session laws it became.", S),
    "veto_message": ("object", "The governor's veto message, in the governor's own words, from the House calendar it was read into.", S),
    "rsa": ("object", "Every statute cited by the bill, its reports and amendments, each with its page on this site.", S),
    "amends": ("object", "The statutes the bill's own text says it changes.", S),
    "stations": ("array", "Each sitting on the bill, one object each; x-fields names every field one carries. The Senate's hearing reports, YouTube's titles and offsets, and watch links are left out (DESIGN.md, Q18, Q21).", B),
    "documents": ("array", "Links to the General Court's own documents for the bill.", S),
    "text_url": ("string", "The General Court's page for the bill's text.", S),
    "docket_url": ("string", "The General Court's docket page for the bill.", S),
    "lsr": ("string", "Its legislative service request number.", S),
    "subject": ("string", "The subject the General Court files it under.", S),
    "subject_source": ("string", "Where subject came from.", S),
    "house_committee": ("string", "Its House committee.", S),
    "senate_committee": ("string", "Its Senate committee.", S),
    "facts": ("object", "The rest of what the General Court's status page states: lsr, body, local, gen_status, house_status, senate_status, date_introduced, floor_date, committee_code, in its own words and dates.", B),
    "nver": ("integer", "How many printings of the text there are.", S),
    "namd": ("integer", "How many amendments have a text.", S),
    "related": ("array", "Other bills that share its language, and where that language went.", B),
    "ballot": ("object", "A constitutional amendment's vote by the voters, or the day of one still to come, with its source.", S),
    "constitution": ("array", "The parts of the State Constitution a constitutional amendment would change.", S),
    "narrative": ("string", "The bill's history in plain English, written by this site.", P),
    "stages": ("array", "That history by stage, as the page draws it.", P),
    "journey": ("object", "The floor decisions, governor and chapter, one line each, and the stops of the card's rail.", P),
    "next_step": ("string", "What happens next, or how it ended, as the page says it.", P),
    "status_source": ("string", "Where the page's status is from.", P),
    "vote_note": ("string", "The note the page's Votes tab opens with.", P),
    "notes": ("array", "Notes the page shows on where the record comes from.", P),
    "story_people": ("array", "Members the plain-English history names, for its links.", P),
    "archived": ("object", "For a bill of a finished term: which parts of its record this site has collected.", P),
    "session_over": ("string", "Why nothing follows, on a bill of the sitting term that ran out of days.", P),
    "bill_note": ("object", "A note written by this site on what a recurring bill number means.", P),
    "same_number": ("array", "For a bill number with such a note, the same number in each other term the note is true of: year, number, title and outcome.", P),
    "changed": ("object", "What the bill's text changes, as the page draws it.", P),
}

# Inside each of a bill's stations. A field tonight's records carry that is
# not here is listed as undocumented, as a bill's own fields are.
STATION_FIELDS = {
    "when": ("string", "The day, YYYY-MM-DD.", B),
    "time": ("string", "The time called, HH:MM, where the record gives one.", B),
    "what": ("string", "The kind of sitting: public hearing, executive session, work session, floor debate, consent calendar and the like.", B),
    "committee": ("string", "The committee.", B),
    "body": ("string", "H or S.", B),
    "venue": ("string", "The room, as the record writes it.", B),
    "video_id": ("string", "The recording's YouTube id; empty where none was matched.", B),
    "seconds": ("integer", "How long its recording runs, in seconds, where the video index says.", P),
    "start": ("number", "Seconds into the recording where this site places the bill's start; null where it places none.", B),
    "end": ("number", "Seconds into the recording where it places the end; null where it places none.", B),
    "state": ("string", "How the start was placed, or why there is none: stated, floor_stated, floor_precise, floor_dated, located, approximate, whole_video, consent, candidates (several recordings, none chosen), novideo, prestream (before the chamber streamed).", B),
    "start_stated": ("boolean", "True where the chair's own words placed the start.", P),
    "end_stated": ("boolean", "True where the chair's own words placed the end.", P),
    "end_stated_cluster": ("boolean", "True where the clustering model marked its end as stated.", P),
    "end_from": ("string", "How the end was decided; where end is null, the candidate this site would not publish.", P),
    "said_how": ("string", "How the chair's words were found, by method; the words themselves are never published.", P),
    "candidate": ("number", "The start the clustering model found, in seconds, whether or not it is the one shown in start.", P),
    "tolerance": ("number", "The margin the page gives the start: the model's own for its segment, and usually 5 where the chair's words placed it. The page reads its unit from start_stated.", P),
    "short": ("boolean", "True where the model judged the span short.", P),
    "testimony": ("object", "The hearing's sign-in counts: date, total, support, oppose, neutral, and dated (whether the date is the record's). Counts only; never a name.", S),
    "debate_start": ("number", "On the floor: seconds into the recording where the debate opens, where the chair said so.", P),
    "debate_end": ("number", "On the floor: where the debate ends, from the roll call's clock.", P),
    "window_start": ("number", "On the floor: where the stretch that ends at the bill's roll call opens, which is the roll call before it.", P),
    "motions": ("array", "On the floor: the motions voted on, in the record's words.", P),
    "tallies": ("array", "On the floor: each motion's yeas-nays, in the same order.", P),
    "mks": ("array", "Those motions as the keys the page's words are looked up by.", P),
    "candidate_ids": ("array", "Where the day held several recordings and none was chosen: their YouTube ids.", P),
    "not_named": ("boolean", "True where the recording never names the bill, by number or by title.", P),
    "dated_by": ("string", "report: a Senate hearing dated from its committee report.", P),
    "docket_heard": ("array", "On such a hearing: the days the docket gives for it.", P),
}

# ------------------------------------------------------------ the database --
DB_TABLES = {
    "bills": "bills.csv's rows and columns.",
    "rollcalls": "rollcalls.csv, with id, an integer key the votes table uses.",
    "votes": "Every ballot, one row each.",
    "vote_values": "The words of each vote code.",
    "sponsors": "sponsors.csv, as written.",
    "legislators": "legislators.csv, as written.",
    "proceedings": "Every sitting on a bill, with where this site places it in the recording. "
                   "YouTube's own metadata (a recording's title, its scheduled offset) is left out.",
    "people": "people.json, one row a person.",
    "person_numbers": "Every number of every person, one row a number.",
    "committee_reports": "Each side of each printed committee report, with its reasoning in text: House calendar reports, Senate committee reports, interim study statements.",
    "docket_reports": "Reports the docket records and no printed report carries.",
    "interim_study": "The docket's line on each interim study.",
    "testimony": "Sign-in counts at each public hearing. Counts only; never a name.",
    "meetings": "Every meeting the House and Senate calendars noticed, on a bill or not.",
    "meta": "What the file is and whose the record is. Not when it was built: the manifest says that.",
}

# Every column of every table, where the table is not a CSV's (those take
# the CSV's descriptions). build_exports stops on a column described nowhere.
_T, _I = "string", "integer"
DB_COLUMNS = {
    "rollcalls": {"id": (_I, "This file's key for the roll call, which votes.rollcall uses. Not stable between nights: join on roll_call.", S)},
    "votes": {
        "rollcall": (_I, "rollcalls.id.", S),
        "member_id": (_T, "This site's member id.", S),
        "person": (_T, "Their person number; empty where they have none.", S),
        "party": (_T, "Party at the vote.", S),
        "vote": (_I, "vote_values.code.", S),
    },
    "vote_values": {"code": (_I, "The code votes.vote uses.", S),
                    "vote": (_T, "Its words, as the vote files write them: Yea, Nay, Not Voting/Excused "
                                 "and so on, and empty for a ballot the record leaves blank.", S)},
    "people": {
        "person": (_T, PERSON, S),
        "name": (_T, "Their name.", S),
        "page": (_T, "Their page on this site.", S),
        "sitting": (_I, "1 where they sit now.", S),
        "chambers": (_T, "H, S or HS.", S),
        "first_term": (_T, "Their first term with a recorded vote.", S),
        "last_term": (_T, "Their last.", S),
        "provisional": (_I, "1 until the person number is issued into the register; it may change until then.", S),
        "replaced_by": (_T, "On a retired person number: the one that replaces it.", S),
        "split_from": (_T, "On a person found to be two: the number they were split from.", S),
    },
    "person_numbers": {
        "person": (_T, "The person number.", S),
        "kind": (_T, "employee_number, person_id or member_id.", S),
        "number": (_T, "The number.", S),
    },
    "committee_reports": {
        "term": (_T, "The two-year term.", S),
        "bill": (_T, "The bill. " + BILL_KEY, S),
        "chamber": (_T, "H or S, the chamber whose committee reported.", S),
        "source": (_T, "Where it is printed: House Calendar 15, 2013; Senate committee report, released 2025-05-13.", S),
        "cite": (_T, "The short citation, HC 15.", S),
        "date": (_T, "The report's date, YYYY-MM-DD; empty where the printing gives none.", S),
        "interim": (_I, "1 for an interim study statement.", S),
        "majority_recommendation": (_T, "The committee's recommendation, as printed.", S),
        "minority_recommendation": (_T, "The minority's, where there is one.", S),
        "side": (_T, "Whose this row is: Majority, Minority, Committee (a report with no minority) or Interim study report.", S),
        "committee": (_T, "The committee.", S),
        "author": (_T, "The member who wrote it, as printed.", S),
        "vote_yeas": (_I, "The committee's vote for, where printed.", S),
        "vote_nays": (_I, "And against.", S),
        "amendment": (_T, "The amendment it recommends, where it names one.", S),
        "text": (_T, "The reasoning, in the report's words.", S),
    },
    "docket_reports": {
        "term": (_T, "The two-year term.", S),
        "bill": (_T, "The bill. " + BILL_KEY, S),
        "date": (_T, "The day, YYYY-MM-DD.", S),
        "dated": (_T, "Which day date is: signed (the report's own date) or recorded (the day the docket recorded it).", S),
        "chamber": (_T, "H or S.", S),
        "committee": (_T, "The committee.", S),
        "side": (_T, "Majority, Minority, or empty where the docket names no side.", S),
        "recommendation": (_T, "The recommendation, in the docket's words.", S),
        "vote_yeas": (_I, "The committee's vote for, where the docket gives it.", S),
        "vote_nays": (_I, "And against.", S),
        "amendment": (_T, "The amendment it recommends, where named.", S),
        "cite": (_T, "Where the docket says it is printed, as the docket writes it: a calendar or a "
                     "journal (SC 11, SC 15A, SJ 11); empty where it names none.", S),
    },
    "interim_study": {
        "term": (_T, "The two-year term.", S),
        "bill": (_T, "The bill. " + BILL_KEY, S),
        "date": (_T, "The day, YYYY-MM-DD.", S),
        "chamber": (_T, "H or S.", S),
        "rec": (_T, "What the committee said of future legislation: rec (recommended), not (not recommended) or without (without recommendation).", S),
        "recommended": (_I, "1 where it recommended future legislation.", S),
        "vote": (_T, "The committee's vote, yeas–nays.", S),
    },
    "testimony": {
        "term": (_T, "The two-year term.", S),
        "bill": (_T, "The bill. " + BILL_KEY, S),
        "date": (_T, "The hearing's day, YYYY-MM-DD.", S),
        "date_known": (_I, "1 where the sign-in record gives the day; 0 where the day is the sitting's.", S),
        "chamber": (_T, "H or S.", S),
        "committee": (_T, "The committee.", S),
        "total": (_I, "Everyone who signed in.", S),
        "support": (_I, "In support.", S),
        "oppose": (_I, "Opposed.", S),
        "neutral": (_I, "Neither.", S),
    },
    "meetings": {
        "date": (_T, "The day, YYYY-MM-DD.", S),
        "time": (_T, "The time, HH:MM.", S),
        "chamber": (_T, "H or S.", S),
        "committee": (_T, "The committee.", S),
        "kind": (_T, "public hearing, executive session, work session and the like; other for the rest.", S),
        "venue": (_T, "What the calendar prints where the room would be, when it is not a room: usually "
                      "a place, but on some notices the bill's title. "
                      "Read it as text, not as an address.", B),
        "room": (_T, "The room, written as the docket writes it: LOB 206-208.", S),
        "bill": (_T, "The bill, where the meeting is on one.", S),
        "noticed": (_T, "The day of the calendar that noticed it, YYYY-MM-DD.", S),
        "calendar": (_T, "That calendar: year/HC010 for the House's, year/SC005 for the Senate's, with a "
                         "letter after the number for a supplement (2023/HC010A).", S),
    },
    "meta": {"key": (_T, "format, what, rights or upstream.", S), "value": (_T, "Its value.", S)},
}
DB_FROM_CSV = {"bills": "bills.csv", "rollcalls": "rollcalls.csv", "sponsors": "sponsors.csv",
               "legislators": "legislators.csv", "proceedings": "proceedings.csv"}

# The one rights line every download states (manifest.json, the database's
# meta, and here schema.json): api_db.RIGHTS, the owner's words.
from api_db import RIGHTS  # noqa: E402
LICENSES = [
    {"name": "CC0-1.0", "path": "https://creativecommons.org/publicdomain/zero/1.0/",
     "title": "What this site adds: the keys and joins it makes and the corrections made "
              "here by hand"},
    {"name": "MIT", "path": "https://opensource.org/license/mit",
     "title": "The plain-English histories (a bill's narrative and stages) and the software"},
]


# Every General Court source the pipeline reads, and where it lands
# (DESIGN.md, 2.11). Counts are not kept here: they are the dump's, and go
# stale; the manifest names the table and the place.
SOURCES = [
    ("Docket", "each bill's events, stages and chapter; proceedings; docket_reports; bills.csv status and chapter"),
    ("Legislation", "bills.csv; each bill's title, committees and subject"),
    ("Sponsors", "sponsors.csv; each bill's sponsors"),
    ("Legislators", "legislators.csv; people.json; the names in the vote files"),
    ("RollCallSummary", "rollcalls.csv; each bill's rollcalls"),
    ("RollCallHistory", "votes-<term>.csv; the database's votes"),
    ("CandH_Reports", "the Senate's committee reports in committee_reports and each bill's reports"),
    ("LegislationText", "each bill's billtext, the current printing"),
    ("NH_RSA", "each bill's rsa; the /laws pages, not a /data file"),
    ("houseRemoteTestify", "testimony: counts only. Names, towns and written testimony are never collected"),
    ("Committees, CommitteeMembers", "legislators.csv committees; the committee pages, not a /data file"),
    ("StatStudDetails, StatStudMembers, StatStudMeetings", "the statutory and study committee pages, not a /data file"),
    ("HouseDistricts, senateDistricts, County, Towns", "legislators.csv district and county; the town pages, not a /data file"),
    ("Subject, GeneralStatusCodes, BodyStatusCodes", "as words in bills.csv topic and status, not as code tables"),
    ("PastLegislation, PastSponsors, PastDocket, PastLegislationText", "the same places as their current-term tables, for 1989 to 2024"),
    ("PastCommitteeReports", "not published itself: it corrects misprinted House reports in committee_reports"),
    ("PastAmendments", "each bill's related"),
    ("DocumentVersion", "not published: it only orders and names the printings"),
    ("VHearings", "not published: read by nothing; hearings come from the Docket and the calendars"),
    ("hearingType, committeeType, DistrictPast", "not published: dumped and read by nothing"),
    ("The House and Senate calendars (not the database)", "the House committee reports and their reasoning, interim study statements, and meetings"),
]


def _fields(spec, only=None):
    """The Table Schema fields of spec, in spec's order; only those in
    `only` where it is given (the columns the file really has)."""
    return [{"name": n, "type": t, "description": d, "x-stability": st}
            for n, (t, d, st) in spec.items() if only is None or n in only]


def _key(file):
    return "votes-<term>.csv" if file.startswith("votes-") else file


def db_spec(table):
    """Every column of a database table, described: a CSV's table takes the
    CSV's descriptions, the rest DB_COLUMNS."""
    spec = dict(CSV.get(DB_FROM_CSV.get(table, ""), {}))
    spec.update(DB_COLUMNS.get(table, {}))
    return spec


def undescribed_columns(tables, people_columns=(), db_columns=None):
    """Every column the build wrote that this file does not describe:
    [(file, column)]. tables are the API's CSVs; people_columns people.csv's
    header; db_columns {table: [column]} of the database. build_exports
    stops on any, so nothing is published unexplained."""
    out = []
    for t in tables:
        spec = CSV.get(_key(t["file"]), {})
        out += [(t["file"], c) for c in t["columns"] if c not in spec]
    out += [("people.csv", c) for c in people_columns if c not in CSV["people.csv"]]
    for table, cols in (db_columns or {}).items():
        if table not in DB_TABLES:
            out.append(("the database", table))
            continue
        spec = db_spec(table)
        out += [(f"the database's {table}", c) for c in cols if c not in spec]
    return out


def broken_keys(out, tables):
    """Every foreign key KEYS declares, checked against tonight's files:
    [(file, columns, how many rows do not join)]. A tool that checks the
    schema checks every row, so build_exports stops on any."""
    import csv
    from pathlib import Path
    files = {t["file"]: t for t in tables}
    bad = []
    for t in tables:
        _, fks = KEYS.get(_key(t["file"]), ([], []))
        for cols, ref, refcols in fks:
            ref_file = f"{ref}.csv"
            if ref_file not in files:
                bad.append((t["file"], cols, f"refers to {ref_file}, which is not an API file"))
                continue
            with (Path(out) / ref_file).open(encoding="utf-8", newline="") as fh:
                have = {tuple(r[c] for c in refcols) for r in csv.DictReader(fh)}
            miss = 0
            with (Path(out) / t["file"]).open(encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    if tuple(r[c] for c in cols) not in have:
                        miss += 1
            if miss:
                bad.append((t["file"], cols, f"{miss:,} rows do not join {ref_file}"))
    return bad


def _name(path, used):
    """A resource's name, unique as Data Package v1 requires: the file's
    stem, or the whole name where two files share a stem (people.json and
    people.csv)."""
    stem = path.split(".")[0].lower().replace("_", "-")
    name = stem if stem not in used else path.lower().replace(".", "-").replace("_", "-")
    if name in used:
        raise SystemExit(f"schema.json would name two files {name}; Data Package names are unique.")
    used.add(name)
    return name


def package(tables, files, base, built, record_keys=(), station_keys=(),
            db_columns=None, people_columns=None):
    """The Data Package: one resource a file. tables are the API's CSV
    rows (file, rows, bytes, columns, what, sha256); files the manifest's
    other "files" rows; record_keys every top-level field the bill records
    carried tonight, station_keys every field inside their stations;
    db_columns the database's {table: [column]}; people_columns
    people.csv's header."""
    res, used = [], set()
    for t in tables:
        pk, fks = KEYS.get(_key(t["file"]), ([], []))
        schema = {"fields": _fields(CSV[_key(t["file"])], set(t["columns"]))}
        if pk:
            schema["primaryKey"] = pk
        if fks:
            schema["foreignKeys"] = [{"fields": a, "reference": {"resource": r, "fields": b}}
                                     for a, r, b in fks]
        res.append({"name": _name(t["file"], used), "path": t["file"],
                    "profile": "tabular-data-resource", "format": "csv", "mediatype": "text/csv",
                    "encoding": "utf-8", "bytes": t["bytes"], "x-rows": t["rows"],
                    **({"hash": "sha256:" + t["sha256"]} if t.get("sha256") else {}),
                    "description": t.get("what", ""), "schema": schema})
    keys, skeys = set(record_keys), set(station_keys)
    for f in files:
        name = f["path"].rsplit("/", 1)[-1]
        r = {"name": _name(name, used), "path": name, "bytes": f.get("bytes"),
             "x-rows": f.get("rows"), **({"hash": "sha256:" + f["sha256"]} if f.get("sha256") else {})}
        if f.get("kind") == "bills":
            known = _fields(BILL_FIELDS)
            for k in known:
                if k["name"] == "stations":
                    k["x-fields"] = _fields(STATION_FIELDS) + [
                        {"name": s, "type": "any", "description": "", "x-stability": "undocumented"}
                        for s in sorted(skeys - set(STATION_FIELDS))]
            extra = [{"name": k, "type": "any", "description": "", "x-stability": "undocumented"}
                     for k in sorted(keys - set(BILL_FIELDS))]
            r.update(format="jsonl", mediatype="application/x-ndjson", compression="gz",
                     description=f"Every bill of {f.get('term')}, one JSON object a line, its "
                                 "full record as its page carries it, keyed term/bill.",
                     schema={"fields": known + extra})
        elif f.get("kind") == "bill_texts":
            r.update(format="jsonl", mediatype="application/x-ndjson", compression="gz",
                     description=f"The text of every bill of {f.get('term')}, one JSON object a "
                                 "line, keyed term/bill: every version its Bill Text tab shows, "
                                 "with its name and date (api_records.py).",
                     schema={"fields": _described(API_BILL_TEXTS_LINE,
                                                  {"versions": API_BILL_VERSION})})
        elif f.get("kind") == "database":
            cols = db_columns or {}
            r.update(format="sqlite", mediatype="application/vnd.sqlite3", compression="xz",
                     description="Every table above and the record's committee reports, in one "
                                 "SQLite database.",
                     **{"x-tables": {t: {"description": d, "rows": (f.get("counts") or {}).get(t),
                                         "fields": _fields(db_spec(t), set(cols.get(t) or ()))}
                                     for t, d in DB_TABLES.items()}})
        elif name == "people.json":
            r.update(format="json", mediatype="application/json",
                     description="One entry a person, with every number the General Court and "
                                 "this site use for them.",
                     schema={"fields": [
                         {"name": "person", "type": "string", "x-stability": S, "description": PERSON},
                         {"name": "name", "type": "string", "x-stability": S, "description": "Their name."},
                         {"name": "employee_numbers", "type": "array", "x-stability": S,
                          "description": "The General Court's employee numbers, earliest first."},
                         {"name": "person_ids", "type": "array", "x-stability": S,
                          "description": "The General Court's PersonIDs."},
                         {"name": "member_ids", "type": "array", "x-stability": S,
                          "description": "The ids this site's other files use for them."},
                         {"name": "page", "type": "string", "x-stability": S, "description": "Their page here."},
                         {"name": "sitting", "type": "boolean", "x-stability": S, "description": "Whether they sit now."},
                         {"name": "chambers", "type": "array", "x-stability": S, "description": "H, S or both."},
                         {"name": "first_term", "type": "string", "x-stability": S, "description": "Their first term with a recorded vote."},
                         {"name": "last_term", "type": "string", "x-stability": S, "description": "Their last."},
                         {"name": "provisional", "type": "boolean", "x-stability": S,
                          "description": "True until the person number is issued into the register; it may change until then."},
                         {"name": "replaced_by", "type": "string", "x-stability": S,
                          "description": "On a retired person number: the one that replaces it."},
                         {"name": "split_from", "type": "string", "x-stability": S,
                          "description": "On a person found to be two: the number they were split from."}]})
        elif name == "people.csv":
            r.update(format="csv", mediatype="text/csv", profile="tabular-data-resource",
                     encoding="utf-8", description="people.json, one row a number.",
                     schema={"fields": _fields(CSV["people.csv"],
                                               set(people_columns) if people_columns else None)})
        res.append(r)
    # The terms of each file, on the file itself (DATA.md: "schema.json names
    # the terms of each file"). Every download carries the same line today.
    for r in res:
        r["licenses"] = LICENSES
    return {"profile": "data-package", "name": "granite-record",
            "title": "Granite Record: the New Hampshire General Court's record",
            "homepage": "https://graniterecord.org/api", "x-format": FORMAT,
            "x-status": "beta", "x-stable-from": "2027-02-01", "created": built,
            "licenses": LICENSES, "x-rights": RIGHTS,
            "sources": [{"title": "New Hampshire General Court", "path": "https://gc.nh.gov"}],
            "resources": res,
            # The API's records under /api/ (below): thousands of files, so
            # described as resources of their own kind, not as Data Package
            # resources, which are one file each.
            "x-api-records": api_records_schema()}


# ------------------------------------------- the API's records, one file each --
# /api/ (api_records.py; the owner's word of 16 November 2026): a file a
# record for the sitting term's bills and roll calls, for every member, every
# bill request the site lists and every chapter of the statutes, beside a file
# of rows for each. These say what each file holds, field by field, and
# api_records writes a field only where it is here and marked stable: a
# record's file is a promise, and a page's field is not one. Every field here
# is stable; the bill record's beta and page fields (stations, facts,
# related, narrative and the rest) are in no file under /api/. schema.json
# carries them under "x-api-records", and /api/index.json lists them with
# tonight's counts.
_BC = CSV["bills.csv"]
API_BILL_ROW = {
    "key": BILL_FIELDS["key"],
    "id": BILL_FIELDS["id"],
    "year": _BC["year"], "term": _BC["term"], "title": _BC["title"], "sponsor": _BC["sponsor"],
    "committees": ("array", "The committees it was referred to, in order.", S),
    "topic": _BC["topic"], "status": _BC["status"], "outcome": _BC["outcome"],
    "passage": _BC["passage"], "roll_calls": _BC["roll_calls"], "chapter": _BC["chapter"],
    "chip": _BC["chip"],
}
# THE TEXT OF EVERY VERSION THE BILL TEXT TAB SHOWS (the owner, 16 November
# 2026: "laws and bills carry their text through the API"), from the same
# files the tab reads: the versions build_bill_versions.py writes for a bill
# with more than one version or with amendments, else the record's own
# printing (billtext). Where this site holds no text, versions is empty and
# text_on_file false: no text is made up, and none is fetched.
API_BILL_VERSION = {
    "name": ("string", "The version's name, as the Bill Text tab shows it: Introduced, As Amended by "
                       "the House, CHAPTERED FINAL VERSION and the like.", S),
    "date": ("date", "The day the General Court dated that printing, YYYY-MM-DD; null where the "
                     "record gives none.", S),
    "text": ("string", "Its text, as the Bill Text tab shows it; null where this site holds no "
                       "text of that version.", S),
}
API_BILL_TEXT = {
    "versions": ("array", "The text of every version the bill's Bill Text tab shows, oldest first, "
                          "each with its name and date; empty where this site holds no text of the "
                          "bill.", S),
    "text_on_file": ("boolean", "False where this site holds no text of the bill, and versions is "
                                "empty.", S),
}
# A bill's own file: its row, then every stable field of its record, in the
# record's order, then its text. Where both have a field the row's is kept,
# so a bill says the same in its file as in its term's rows and in bills.csv:
# the record's title carries the docket's "(New Title)", which the rows do not.
API_BILL = {**API_BILL_ROW, **{k: v for k, v in BILL_FIELDS.items()
                               if v[2] == S and k not in API_BILL_ROW}, **API_BILL_TEXT}
# A line of /data/bill-texts-<term>.jsonl.gz: every term's bills' text, a
# line a bill, beside the bill files, which stay as they were.
API_BILL_TEXTS_LINE = {"key": BILL_FIELDS["key"], **API_BILL_TEXT}

_RC = CSV["rollcalls.csv"]
API_ROLLCALL_ROW = {
    **{k: _RC[k] for k in ("roll_call", "term", "year", "body", "number", "date", "bill",
                           "question", "question_plain", "yeas", "nays", "not_voting")},
    "passed": ("boolean", "True where the motion carried, as the record states it (outcome_source).", S),
    "procedural": ("boolean", "True for a procedural vote, such as suspending the rules.", S),
    "threshold_needed": ("integer", "What it needed where that was more than a majority; null where "
                                    "a majority was enough.", S),
    "threshold_rule": _RC["threshold_rule"], "outcome_source": _RC["outcome_source"],
}
API_ROLLCALL = {**API_ROLLCALL_ROW,
                "ballots": ("array", "How each member voted, in the order the General Court's "
                                     "file lists them.", S)}
_VC = CSV["votes-<term>.csv"]
API_BALLOT = {"member_id": _VC["member_id"],
              "person": ("string", "Their person number in people.json; empty where they have none.", S),
              "member": _VC["member"], "party": _VC["party"], "vote": _VC["vote"]}

API_PERSON = {
    "person": ("string", PERSON, S),
    "name": ("string", "Their name.", S),
    "employee_numbers": ("array", "The General Court's employee numbers, earliest first.", S),
    "person_ids": ("array", "The General Court's PersonIDs.", S),
    "member_ids": ("array", "The ids this site's other files use for them.", S),
    "page": ("string", "Their page here.", S),
    "sitting": ("boolean", "Whether they sit now.", S),
    "chambers": ("array", "H, S or both.", S),
    "first_term": ("string", "Their first term with a recorded vote.", S),
    "last_term": ("string", "Their last.", S),
    "provisional": ("boolean", "True until the person number is issued into the register; it may "
                               "change until then.", S),
    "replaced_by": ("string", "On a retired person number: the one that replaces it.", S),
    "split_from": ("string", "On a person found to be two: the number they were split from.", S),
}
API_MEMBER_ROW = {k: API_PERSON[k] for k in ("person", "name", "sitting", "chambers", "first_term",
                                             "last_term", "replaced_by")}
API_MEMBER = {**API_PERSON,
              "seat": ("object", "Where they sit now, as legislators.csv has it; absent for someone "
                                 "who does not sit now.", S),
              "sponsored": ("array", "Every bill they put their name to, as sponsors.csv has it, "
                                     "oldest term first.", S)}
_LC = CSV["legislators.csv"]
API_SEAT = {**{k: _LC[k] for k in ("id", "chamber", "party", "district", "county", "email")},
            "committees": ("array", "Committee seats.", S),
            "bills_sponsored": _LC["bills_sponsored"], "recorded_votes": _LC["recorded_votes"]}
API_SPONSORED = {"key": ("string", "The bill, term/bill: 2025-2026/HB1442.", S),
                 "prime": ("boolean", "True where they were its prime sponsor.", S)}

API_REQUEST = {
    "lsr": ("string", "The request's number, 2027-0001: the session's year and the number the "
                      "General Court gave the request.", S),
    "year": ("integer", "The session it is a request for.", S),
    "title": ("string", "Its title.", S),
    "sponsor": ("string", "The prime sponsor, as the General Court's list names them.", S),
    "cosponsors": ("array", "Its co-sponsors, as the list names them; empty where it names none.", S),
    "body": ("string", "The kind of bill it would be: HB, SB, HR, HCR, SCR, CACR and the like.", S),
    "status": ("string", "Requested, Filed or Withdrawn.", S),
    "withdrawn": ("boolean", "True where it was withdrawn before it became a bill.", S),
    "bill": ("string", "The bill it became, term/bill, once it is one; empty until then.", S),
}

API_LAW_ROW = {
    "chapter": ("string", "The chapter's number, as the statutes print it: 91-A.", S),
    "name": ("string", "The chapter's name.", S),
    "title_no": ("string", "The number of the title it is in: VI.", S),
    "title": ("string", "That title's name.", S),
    "repealed": ("boolean", "True where the whole chapter is repealed or has moved.", S),
    "page": ("string", "Its page on this site.", S),
}
# THE STATUTES' TEXT (the owner, 16 November 2026): each section's, in the
# words its chapter's page shows (build_rsa reads the table and sets the text
# a paragraph a line), with the day the table was taken and where from.
API_LAW = {**API_LAW_ROW,
           "official": ("string", "The General Court's own page for the chapter, where the official "
                                  "text is.", S),
           "text_source": ("string", "Where the sections' text comes from: the General Court's "
                                     "statute table, from its database, as this site's Laws pages "
                                     "show it.", S),
           "text_taken": ("date", "The day the statute table was taken from the General Court's "
                                  "database, YYYY-MM-DD: the text is as it stood that day. Null where "
                                  "the day is not on record.", S),
           "laws_through": ("integer", "The latest year of session laws the text includes; null "
                                       "where that is not on record.", S),
           "sections": ("array", "Its sections in order: each one's number, heading, text and "
                                 "history.", S)}
API_SECTION = {
    "section": ("string", "The section's number: 91-A:4.", S),
    "heading": ("string", "Its heading, as the statutes print it.", S),
    "repealed": ("boolean", "True for a repealed section.", S),
    "text": ("string", "Its text, a paragraph a line, in the words its chapter's page shows; null "
                       "for a repealed section, which the page shows by its heading alone.", S),
    "note": ("string", "Its source note, the session laws that wrote and changed it, in the "
                       "statutes' words; empty where it has none, and null for a repealed "
                       "section.", S),
    "changed_by": ("array", "The session laws that wrote or changed it, in the order its source "
                            "note lists them: oldest first.", S),
}
API_LAW_CHANGE = {
    "year": ("integer", "The year of the session laws.", S),
    "law": ("string", "The chapter and section of that year's laws, 49:1, as the source note cites "
                      "them; the chapter alone where it names no section.", S),
    "bill": ("string", "The bill that law was, term/bill, where this site has it; empty where it "
                       "does not, as for most laws before 1989.", S),
    "effective": ("date", "The day it took or takes effect, YYYY-MM-DD, where the source note "
                          "gives one; null where it does not.", S),
}

# Every file's first field, and the fields a file of rows has around them.
API_FORMAT = {"format": ("integer", "The file's format: 1. Read a file of any other format as not "
                                    "this one: a change that cannot be made by adding becomes a "
                                    "new file name beside the old.", S)}


def _rows_file(context, rows_in, what):
    """A file of rows: its format, what the rows are of, and the rows."""
    return {**API_FORMAT, **context, rows_in: ("array", what, S)}


# Each resource: its name, what it is, the field that names one of its
# records, and its two kinds of file -- a file of rows and a file a record --
# each with every field it holds, in order, and the fields inside its arrays
# and objects ("inside", by the field's name, at any depth).
API_RESOURCES = (
    {"name": "bills", "key": "key",
     "what": "Every bill: a file of rows for each term, a file for each bill of the term now "
             "sitting with its whole record and the text of every version, and every term's text "
             "in one file a term beside the bill files under /data/.",
     "files": (("rows", "/api/bills/{term}/index.json", "every term",
                _rows_file({"term": ("string", "The term these are the bills of.", S)}, "bills",
                           "Each bill's row, in the order the site lists bills.")),
               ("record", "/api/bills/{sitting_term}/{id}.json", "the term now sitting",
                {**API_FORMAT, **API_BILL}),
               ("texts", "/data/bill-texts-{term}.jsonl.gz", "every term, a line a bill, gzipped",
                API_BILL_TEXTS_LINE)),
     "inside": {"bills": API_BILL_ROW, "versions": API_BILL_VERSION}},
    {"name": "rollcalls", "key": "roll_call",
     "what": "Every roll call since 1999: a file of rows for each term, and a file for each roll "
             "call of the term now sitting, with every member's vote.",
     "files": (("rows", "/api/rollcalls/{term}.json", "every term with roll calls",
                _rows_file({"term": ("string", "The term these are the roll calls of.", S)},
                           "rollcalls", "Each roll call's row, by year, chamber and number.")),
               ("record", "/api/rollcalls/{sitting_term}/{roll_call}.json", "the term now sitting",
                {**API_FORMAT, **API_ROLLCALL})),
     "inside": {"rollcalls": API_ROLLCALL_ROW, "ballots": API_BALLOT}},
    {"name": "members", "key": "person",
     "what": "Everyone with a recorded vote since 1999, a file each: the numbers the General Court "
             "gives them, their terms, their seat if they sit now, and the bills they sponsored.",
     "files": (("rows", "/api/members/index.json", "everyone",
                _rows_file({}, "members", "Each person's row, as people.json orders them.")),
               ("record", "/api/members/{person}.json", "everyone", {**API_FORMAT, **API_MEMBER})),
     "inside": {"members": API_MEMBER_ROW, "seat": API_SEAT, "sponsored": API_SPONSORED}},
    {"name": "requests", "key": "lsr",
     "what": "The bill requests of the next session, before they are bills: a file of rows, and a "
             "file for each.",
     "files": (("rows", "/api/requests/{year}/index.json", "the session the site lists",
                _rows_file({"year": ("integer", "The session these are requests for.", S)},
                           "requests", "Each request's row, by number.")),
               ("record", "/api/requests/{year}/{number}.json", "the session the site lists",
                {**API_FORMAT, **API_REQUEST})),
     "inside": {"requests": API_REQUEST}},
    {"name": "laws", "key": "chapter",
     "what": "Every chapter of the statutes: each section's heading and text, as this site's Laws "
             "pages show them and as of the day the General Court's table was taken, the session "
             "laws that changed it, the bill each was, and when each took effect.",
     "files": (("rows", "/api/laws/index.json", "every chapter",
                _rows_file({}, "chapters", "Each chapter's row, in the statutes' order.")),
               ("record", "/api/laws/{chapter}.json", "every chapter", {**API_FORMAT, **API_LAW})),
     "inside": {"chapters": API_LAW_ROW, "sections": API_SECTION, "changed_by": API_LAW_CHANGE}},
)


def _described(spec, inside, depth=0):
    """spec's fields as _fields gives them, each array or object named in
    `inside` with its own fields under "x-fields", to any depth."""
    out = _fields(spec)
    for f in out:
        if f["name"] in inside and depth < 4:
            f["x-fields"] = _described(inside[f["name"]], inside, depth + 1)
    return out


def api_records_schema():
    """The API's records as schema.json describes them, and as
    /api/index.json does beside tonight's counts: each resource, its files,
    and every field of each, with its type, description and stability."""
    return [{"name": r["name"], "description": r["what"], "key": r["key"],
             "files": [{"holds": holds, "path": path, "for": of,
                        "fields": _described(spec, r["inside"])}
                       for holds, path, of, spec in r["files"]]}
            for r in API_RESOURCES]


def api_file_fields(name, holds):
    """{field: (type, description, stability)} of one resource's file of
    rows or file a record, and the specs inside it: what api_records holds
    each file it writes to."""
    r = next(x for x in API_RESOURCES if x["name"] == name)
    return next(spec for h, _p, _o, spec in r["files"] if h == holds), r["inside"]
