#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.2
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

Every column of every CSV must be described here: build_exports stops on one
that is not, so a column is never published unexplained. A bill record's
field that is not described is listed as undocumented and does not stop the
build, because the records are the pages' and the pages change.
"""

FORMAT = 1

# ---------------------------------------------------------------- the CSVs --
# Each column: (type, description, stability). Types are the Table Schema's.
S, B, P = "stable", "beta", "page"

BILL_KEY = "bill + term is the key: a bill number names a different bill in every term."

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
        "bill": ("string", "The bill voted on; empty for a vote on no bill.", S),
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
    "proceedings.csv": {
        "term": ("string", "The two-year term.", S),
        "bill": ("string", "The bill. " + BILL_KEY, S),
        "body": ("string", "H or S.", S),
        "kind": ("string", "public hearing, executive session, work session, floor session and the like.", S),
        "date": ("date", "The day, YYYY-MM-DD.", S),
        "time": ("string", "The time called, HH:MM.", S),
        "committee": ("string", "The committee.", S),
        "venue": ("string", "The room.", S),
        "video_id": ("string", "The recording's YouTube id, where one was matched.", B),
        "video_title": ("string", "The recording's title on YouTube. YouTube's metadata: the database leaves it out, and it may go (DESIGN.md, Q18).", B),
        "start_seconds": ("number", "Where in the recording this site places the bill's start.", B),
        "end_seconds": ("number", "Where it places the end.", B),
        "how_placed": ("string", "How the start was found: stated, floor_stated, floor_precise, located, whole_video, floor_dated; approximate, consent or empty where no moment was found.", B),
        "end_how": ("string", "How the end was found.", B),
        "scheduled_seconds": ("number", "The called time less the stream's start, which YouTube reports: a schedule, not a finding. The database leaves it out, and it may go (Q18).", B),
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
        "vote": ("string", "Yea, Nay, Not Voting/Excused, Not Voting/Not Excused, Presiding, or No vote recorded.", S),
    },
    "people.csv": {
        "person": ("string", "This site's person number, issued once and never given to anyone else.", S),
        "number_kind": ("string", "employee_number, person_id or member_id; replaced_by on a retired person number.", S),
        "number": ("string", "The number; on a replaced_by row, the person number that replaces it.", S),
        "name": ("string", "The person's name.", S),
        "page": ("string", "Their page on this site.", S),
    },
}

KEYS = {
    "bills.csv": (["term", "bill"], []),
    "rollcalls.csv": (["roll_call"], [(["term", "bill"], "bills", ["term", "bill"])]),
    "votes-<term>.csv": ([], [(["roll_call"], "rollcalls", ["roll_call"])]),
    "sponsors.csv": ([], [(["term", "bill"], "bills", ["term", "bill"])]),
    "proceedings.csv": ([], [(["term", "bill"], "bills", ["term", "bill"])]),
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
    "stations": ("array", "Each sitting on the bill: when, time, what, committee, body, venue, video_id, and where in the recording this site places it (start, end, state). The Senate's hearing reports, YouTube's titles and offsets, and watch links are left out (DESIGN.md, Q18, Q21).", B),
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
    "changed": ("object", "What the bill's text changes, as the page draws it.", P),
}

# ------------------------------------------------------------ the database --
DB_TABLES = {
    "bills": "bills.csv, as written.",
    "rollcalls": "rollcalls.csv, with id, an integer key the votes table uses.",
    "votes": "Every ballot: rollcall (rollcalls.id), member_id, person, party, and vote (vote_values.code).",
    "vote_values": "The words of each vote code.",
    "sponsors": "sponsors.csv, as written.",
    "legislators": "legislators.csv, as written.",
    "proceedings": "proceedings.csv without video_title and scheduled_seconds, YouTube's own metadata.",
    "people": "people.json, one row a person.",
    "person_numbers": "Every number of every person: person, kind (employee_number, person_id, member_id), number.",
    "committee_reports": "Each side of each printed committee report, with its reasoning in text: House calendar reports, Senate committee reports, interim study statements (interim 1).",
    "docket_reports": "Reports the docket records and no printed report carries.",
    "interim_study": "The docket's line on each interim study.",
    "testimony": "Sign-in counts at each public hearing: total, support, oppose, neutral. Counts only; never a name.",
    "meetings": "Every meeting the House and Senate calendars noticed, on a bill or not.",
    "meta": "What the file is, when it was built, and whose the record is.",
}

LICENSES = [
    {"name": "CC0-1.0", "path": "https://creativecommons.org/publicdomain/zero/1.0/",
     "title": "What this site adds -- the keys and joins it makes and its corrections -- "
              "dedicated to the public domain"},
]
RIGHTS = ("The record is the State of New Hampshire's, published by the General Court, and "
          "so are the numbers it gives people and bills; this project claims nothing over "
          "them. What this site adds -- the keys and joins it makes and the corrections made "
          "here by hand -- is dedicated to the public domain under CC0 1.0. "
          "The plain-English histories (narrative, stages) are authored here and offered "
          "under the MIT License, as DATA.md says. The software is MIT licensed.")


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


def _fields(spec):
    return [{"name": n, "type": t, "description": d, "x-stability": st}
            for n, (t, d, st) in spec.items()]


def undescribed_columns(tables):
    """Every CSV column the build wrote that CSV does not describe:
    [(file, column)]. build_exports stops on any."""
    out = []
    for t in tables:
        key = "votes-<term>.csv" if t["file"].startswith("votes-") else t["file"]
        spec = CSV.get(key, {})
        out += [(t["file"], c) for c in t["columns"] if c not in spec]
    return out


def package(tables, files, base, built, record_keys=()):
    """The Data Package: one resource a file. tables are the manifest's
    CSV rows (file, rows, bytes, columns, what); files its "files" rows;
    record_keys every top-level field the bill records carried tonight."""
    res = []
    for t in tables:
        key = "votes-<term>.csv" if t["file"].startswith("votes-") else t["file"]
        pk, fks = KEYS.get(key, ([], []))
        schema = {"fields": [f for f in _fields(CSV[key]) if f["name"] in t["columns"]]}
        if pk:
            schema["primaryKey"] = pk
        if fks:
            schema["foreignKeys"] = [{"fields": a, "reference": {"resource": r, "fields": b}}
                                     for a, r, b in fks]
        res.append({"name": t["file"][:-4].replace("_", "-").lower(), "path": t["file"],
                    "profile": "tabular-data-resource", "format": "csv", "mediatype": "text/csv",
                    "encoding": "utf-8", "bytes": t["bytes"], "x-rows": t["rows"],
                    **({"hash": "sha256:" + t["sha256"]} if t.get("sha256") else {}),
                    "description": t.get("what", ""), "schema": schema})
    keys = set(record_keys)
    for f in files:
        name = f["path"].rsplit("/", 1)[-1]
        r = {"name": name.split(".")[0].lower(), "path": name, "bytes": f.get("bytes"),
             "x-rows": f.get("rows"), **({"hash": "sha256:" + f["sha256"]} if f.get("sha256") else {})}
        if f.get("kind") == "bills":
            known = _fields(BILL_FIELDS)
            extra = [{"name": k, "type": "any", "description": "", "x-stability": "undocumented"}
                     for k in sorted(keys - set(BILL_FIELDS))]
            r.update(format="jsonl", mediatype="application/x-ndjson", compression="gz",
                     description=f"Every bill of {f.get('term')}, one JSON object a line, its "
                                 "full record as its page carries it, keyed term/bill.",
                     schema={"fields": known + extra})
        elif f.get("kind") == "database":
            r.update(format="sqlite", mediatype="application/vnd.sqlite3", compression="xz",
                     description="Every table above and the record's committee reports, in one "
                                 "SQLite database.",
                     **{"x-tables": {t: {"description": d, "rows": (f.get("counts") or {}).get(t)}
                                     for t, d in DB_TABLES.items()}})
        elif name == "people.json":
            r.update(format="json", mediatype="application/json",
                     description="One entry a person, with every number the General Court and "
                                 "this site use for them.",
                     schema={"fields": [
                         {"name": "person", "type": "string", "x-stability": S,
                          "description": "This site's person number, issued once."},
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
            pk, _ = KEYS["people.csv"]
            r.update(format="csv", mediatype="text/csv", profile="tabular-data-resource",
                     description="people.json, one row a number.",
                     schema={"fields": _fields(CSV["people.csv"])})
        res.append(r)
    return {"profile": "data-package", "name": "granite-record",
            "title": "Granite Record: the New Hampshire General Court's record",
            "homepage": "https://graniterecord.org/api", "x-format": FORMAT,
            "x-status": "beta", "x-stable-from": "2027-02-01", "created": built,
            "licenses": LICENSES, "x-rights": RIGHTS,
            "sources": [{"title": "New Hampshire General Court", "path": "https://gc.nh.gov"}],
            "resources": res}
