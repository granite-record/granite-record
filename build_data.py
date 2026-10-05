#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.44
"""
Turn the General Court's bulk files into the data the site runs on.

Schemas below were established by running probe_schema.py against the real
files rather than guessed, which matters -- earlier guesses about these were
wrong about a third of the time.

    legislators.txt      id | last | first | middle | body | seat | countyCode |
                         district | party | mailLabel | street | city | state |
                         zip | email
    HouseDistricts.txt   countyCode | district | ward | town
    Counties.txt         code | name | abbreviation
    SubjectCodes.txt     id | code | name
    Committees.txt       code | name | abbreviation
    LsrSponsors.txt      year | lsr | sequence | memberId | flag
    LSRs.txt             39 fields; 0 year, 1 lsr, 2 title, 3 body, 9 padded
                         bill, 10 bill, 12 subjectCode, 13/14 house committee,
                         21/22 senate committee, 31 hearing datetime, 32 room
    RollCallHistory.txt  year | body | voteNumber | recordId | memberId | -- |
                         vote | timestamp
    RollCallSummary.txt  year | body | number | datetime | bill | yea | nay |
                         ... | question | title

RollCallHistory already contains every member's vote, so no page scraping is
needed. fetch_rollcall_details.py is obsolete.

    python3 build_data.py --dir . --out data

Standard library only.
"""

import argparse
import json
import names
import proceedings as P
import rollcall_parser as RP
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PARTY = {"R": "Republican", "D": "Democrat", "I": "Independent", "L": "Libertarian"}



def _unquote(v):
    """One field of Members.txt, with the quoting the file actually uses.

    Members.txt is tab-separated, but it also quotes any field containing a
    comma -- a CSV convention leaking into a TSV. Splitting on tab and
    stripping only whitespace therefore left the quote marks in the value.
    Measured on the 408-row file: 68 Committee1 values, 29 Address and 1
    Committee2 arrive wrapped in double quotes.

    The visible cost was four House committees whose names contain a comma --
    Labor, Industrial and Rehabilitative Services; Health, Human Services and
    Elderly Affairs; Science, Technology and Energy; Resources, Recreation and
    Development -- carrying a quote character in every one of their 68 member
    links, so they matched nothing in Committees.txt.

    A doubled quote inside a quoted field is that convention's escape for a
    literal one, so it is collapsed here rather than left doubled.
    """
    v = (v or "").strip()
    if len(v) > 1 and v.startswith('"') and v.endswith('"'):
        v = v[1:-1].replace('""', '"').strip()
    return v

def rows(path, expect=None):
    p = Path(path)
    if not p.exists():
        print(f"  missing: {p.name}")
        return []
    out = []
    with open(p, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            f = line.split("|")
            if expect and len(f) != expect:
                continue
            out.append([x.strip() for x in f])
    return out


def rows_all(d, base, expect=None, archive=None, finished=None, left=None):
    """base.txt plus every rollcalls/base_<year>.txt beside it -- or beside
    `archive`, where the session's own files are a frozen term's and the past
    years' are where they always were.

    The General Court publishes one bulk file per CURRENT session, so the
    download alone holds no roll call older than this year. fetch_rollcalls_db
    writes a file per past year in the same shape, from the database, and both
    are read together here -- teaching this reader a second format would have
    been the larger change, and it would have let the two disagree about what
    a column means.

    A roll call is taken from the first file that holds it, and the download
    is read first, so a roll call in both keeps the copy the General Court
    publishes directly. Both files begin year|body|number, which is what
    names a roll call. This docstring promised that for years before anything
    kept it: the summaries went into a dict, so an archive copy overwrote the
    download's, and the ballots into a list, so a roll call in both would
    have been counted twice. None is in both today -- the download is 2026
    and rollcalls/ ends at 2025 -- but at the new term 2026 is archived while
    the download may still hold it, and every 2026 ballot would count twice
    on every member's record.

    By roll call and not by year, because the new term's download may carry a
    few of the old year's roll calls -- organization day, if it is filed under
    2026 -- and taking a year from the first file holding any of it would
    then take all of 2026 from those few.
    """
    out = rows(d / f"{base}.txt", expect)
    extra = Path(archive or d) / "rollcalls"
    # A finished term's year whose own file is here comes from that file and
    # not from the session's (5 October 2026): rows of a finished term in
    # new files are counted and left out, never merged. Until the turn the
    # session's year is no finished one, and the download is read first.
    kept = {y for y in (finished or ()) if (extra / f"{base}_{y}.txt").exists()}
    if kept:
        n = len(out)
        out = [r for r in out if r[0] not in kept]
        if left is not None and n > len(out):
            left[f"{base}.txt"] += n - len(out)
    seen = {tuple(r[:3]) for r in out}
    if extra.is_dir():
        for f in sorted(extra.glob(f"{base}_*.txt")):
            got = rows(f, expect)
            new = [r for r in got if tuple(r[:3]) not in seen]
            seen.update(tuple(r[:3]) for r in new)
            print(f"  {f.name}: {len(new):,} rows" + (
                f", {len(got) - len(new):,} left out as roll calls an earlier file holds"
                if len(new) < len(got) else ""))
            out += new
    return out


# The whole field is a lie for these terms, not merely the out-of-term part.
# Asked for session year 2021 or 2022, the legacy Advanced Bill Status Search
# returns the right bills -- 2021-2022 titles, LSRs, statuses, committees and
# rooms -- and fills the DATE of "Next/Last Hearing" from the 2025-2026
# legislation record carrying the same legislationID, an id that restarts each
# term. Measured against db/Legislation.psv, which is the General Court's own
# database and was dumped ninety minutes before that list was fetched: 1,481
# of the 1,485 out-of-term values equal, to the minute, the current-session
# hearing of the bill with that id; the other 4 have no current row with that
# id; NONE disagree.
#
# And the 93 that do fall inside the term are not hearings either. They sit in
# June 2021 and May 2022, and of the 22 whose docket page is on disk, 22 say
# "H Conference Committee Meeting" on that date. So not one of the 1,752 rows
# is the bill's own public hearing, and the term is dropped whole.
#
# Re-fetching does not fix it. The request is a deterministic POST of the
# session year and the values match the server's own database, so the same
# list comes back. The hearings for this term come from its docket instead,
# the way 2017-2018 and 2019-2020 get theirs.
NO_HEARING_FROM_LIST = {"2021-2022"}


def date_ballot_seats(member_votes, legs, path="text_sponsors.json"):
    """Put the seat a member held in that term on that term's ballots.

    A LABEL STATES THE SEAT HELD WHEN THE RECORD WAS MADE. Every ballot took
    its label from `legs`, which is the roster of the House and Senate sitting
    today, and a roster holds one seat per member however many they have held.
    So Rep. Kenneth Weyler read "Rock 14" on his 1999 ballots and on his 2026
    ones alike, though the bills he sponsored print him at Rock 18 in 2001,
    Rock 79 in 2003 and Rock 8 in 2005; and Janet Wall read Straf 11 in a term
    the record has her at Straf 9. 396 member-terms were labelled with a seat
    that term's bills contradict, across 174,588 ballots.

    The bill's own text is the contemporaneous source -- it printed the seat as
    it was on the day -- and text_sponsors.py has already matched those printed
    lines to members. Where it attests exactly one seat for a member in a term,
    that seat goes on that term's ballots. Where it attests none, or two, the
    label is left alone: this corrects what can be shown to be wrong rather
    than blanking everything that cannot be confirmed.

    Nothing else in the label moves. The name, the party and the honorific come
    from the same places they did, except that the honorific follows the
    chamber the text printed -- which is the point, for a member who changed
    chamber.
    """
    p = Path(path)
    if not p.exists():
        return 0
    try:
        text = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    seats = defaultdict(set)
    for term, bills in text.items():
        for recs in bills.values():
            for r in recs:
                if r.get("member_id"):
                    seats[(term, str(r["member_id"]))].add(
                        (r.get("chamber") or "", r.get("county") or "",
                         str(r.get("district") or "")))
    one = {k: next(iter(v)) for k, v in seats.items() if len(v) == 1}
    if not one:
        return 0

    def term_of(year):
        y = int(year)
        t = y if y % 2 else y - 1
        return f"{t}-{t + 1}"

    abbr = {v["county"]: v.get("county_abbr", "") for v in legs.values()
            if v.get("county") and v.get("county_abbr")}
    cache, n = {}, 0
    for row in member_votes:
        key = (term_of(row["year"]), str(row.get("member_id")))
        seat = one.get(key)
        if not seat:
            continue
        ch, county, dist = seat
        m = legs.get(row["member_id"])
        if not m:
            # A member the roster does not hold is named from former_members,
            # whose label is a different shape entirely; rebuilding it here
            # would change how they read rather than where they sat.
            continue
        if (m.get("chamber") == ch and (m.get("county") or "") == county
                and str(m.get("district") or "") == dist):
            continue
        ck = (row["member_id"], ch, county, dist)
        if ck not in cache:
            cache[ck] = names.legislator({
                "first": m.get("first"), "last": m.get("last"),
                "name": m.get("name"), "chamber": ch,
                "party_code": m.get("party_code"),
                "county_abbr": abbr.get(county, ""), "district": dist})
        if cache[ck] and cache[ck] != row["label"]:
            row["label"] = cache[ck]
            n += 1
    return n


# WHAT THE SEARCH PAGE PUT IN A COMMITTEE FIELD THAT IS NOT A COMMITTEE.
# fetch_archive_bills.py reads the row labelled "Next/Last Comm", which is a
# status field rather than a referral, and for 586 bills of 1999-2016 it holds
# one of these. "Committee of Conference" is the last thing that happened to a
# bill, not a committee it was referred to; "Special Committee" and "No
# Committee Assignment" are the General Court's own words for having no
# ordinary referral to report. referrals.NOT_A_NAME already refuses all three
# on the docket side, and this gives the stored side the same filter.
#
# The one thing lost by blanking "Committee of Conference" is that it was the
# only place an archived bill's page said the bill went to conference. That is
# a fact worth keeping and it belongs on the timeline, where the docket
# already records it, rather than in a field labelled committee.
_PLACEHOLDERS = {"committeeofconference", "nocommitteeassignment",
                 "specialcommittee", "committee", "thecommittee"}


def _placeholder(name):
    import re as _re
    return "".join(w for w in _re.findall(r"[a-z]+", (name or "").lower())
                   if w != "and") in _PLACEHOLDERS


def _pick_committee(stored, first, known, in_use=()):
    """The committee of referral, choosing between two sources that disagree.

    `stored` is the General Court search page's "Next/Last Comm" -- the LAST
    committee the bill was with. `first` is the first referral, read out of
    the docket by referrals.py. The site names the FIRST: a later referral to
    Finance is a money pass rather than a change of subject-matter ownership,
    and a bill that goes to Health and Human Services and then to Finance
    belongs to Health and Human Services. 527 bills of 1999-2016 stored a
    money committee for exactly that reason, and 586 more stored something
    that is not a committee at all.

    So the docket wins -- with one exception, which is the reason this is a
    function rather than an `or`.

    THE EXCEPTION: one committee written two ways. The clerks of 1999-2006
    wrote "Public Works" for what the committee tables call "Public Works and
    Highways", and 133 bills differ only in that way; clerks also misspell
    and shorten ("Enviroment", "Child and Fam"). Preferring the
    docket there would trade a right committee for an unlinkable one: the site
    renders a committee the tables do not know as plain text rather than as a
    link, so the reader would lose the route to the committee's page and gain
    nothing. So where the docket's name is one no table knows, and the two
    names can be one committee, the search page's spelling is kept.

    That test was once about LINKABILITY alone, and it was too wide: every
    committee since retired or renamed is one today's tables do not know --
    the Senate's Insurance, Environment, Wildlife and Recreation, Public
    Institutions, Health and Human Services among them -- so for all of those
    the stored LAST committee won, which was overwhelmingly Finance. So the
    two names must also be able to be one committee (_same_committee says
    what that means). Finance against Insurance is not, and the docket wins.

    `in_use` is the set of name keys the docket gives as a first referral
    for three or more bills in this bill's term and chamber: the names the
    clerks were actually using. _same_committee says what it guards against.
    """
    if not first:
        return stored
    if not stored:
        return first
    import referrals as _r
    if _r._key(stored) == _r._key(first):
        return stored
    if known and _r._key(first) in known:
        return first
    return stored if _same_committee(first, stored, known, in_use) else first


JOURNAL_BILLS = "journal_bills.json"
JOURNAL_SOURCE = "House Journal"


def add_journal_bills(by_term, path=JOURNAL_BILLS, skip=()):
    """{term: {bill: record}}: the House's withdrawn bills, from journal_bills.py,
    added to `by_term` -- and only where the General Court's own files have
    nothing for them.

    Nine House bills of 2025-2026 were withdrawn early under House Rule 39(e),
    and every current-term file the General Court publishes has dropped them;
    the House Journal still prints each one's introduction and withdrawal.

    ONLY INTO A TERM THAT IS ALREADY HERE, AND NEVER OVER A BILL THAT IS. A
    term these records created would be "already built from session files" to
    the archive merge above, which would then skip the whole of the real
    term -- 2025-2026 would be nine bills long. And a record the General
    Court's files carry is better than this in every respect.

    lsr and lsr_num stay empty. An invented LSR would send the fetchers, which
    ask only for records that carry one, to the General Court for addresses
    that may not exist. lsr_year is the journal's year, which is what files
    the bill under its term. The journal's own citations travel under
    "journal", which is also what tells the site this record is not the
    General Court's.
    """
    p = Path(path)
    if not p.exists():
        print("=" * 70)
        print(f"NO {p}. The bills the House withdrew in 2025-2026 are in none of")
        print("the General Court's current files, and this is where they come")
        print("from: without it they are not on the site, and nothing else says")
        print("so. Run: python3 journal_bills.py")
        print("=" * 70)
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        print("=" * 70)
        print(f"{p} WILL NOT PARSE ({e}); no withdrawn bill is added from it.")
        print("=" * 70)
        return {}
    added, kept, skipped = defaultdict(dict), [], []
    for term, byb in sorted(data.items()):
        if term in skip:
            # A finished term frozen and built whole, its withdrawn bills
            # with it (finished_builds).
            continue
        if term not in by_term:
            skipped += [f"{b} {term} (no such term here)" for b in byb]
            continue
        archived = any(r.get("archived") for r in by_term[term].values())
        for bid, j in sorted(byb.items()):
            year = str(j.get("year") or "")
            if P.term_of(year) != term:
                skipped.append(f"{bid} {term} (filed in {year or 'no year'})")
                continue
            if bid in by_term[term]:
                kept.append(f"{bid} {term}")
                continue
            # "decided" is the one bill of an earlier term journal_bills reads
            # (its EARLIER): the House's vote on the committee's report,
            # where the nine carry "withdrawn".
            rec = {
                "bill": bid, "lsr": "", "lsr_year": year, "lsr_num": "",
                "title": j.get("title", ""), "chamber": j.get("chamber") or "H",
                "subject_code": "", "subject": "",
                "house_committee": j.get("committee", ""), "senate_committee": "",
                "hearing": "", "hearing_room": "",
                "designation": j.get("designation") or bid,
                "suffix": j.get("suffix", ""),
                "journal": {k: j[k] for k in ("introduced", "withdrawn", "decided",
                                              "sponsors")
                            if k in j},
            }
            if archived:
                rec["archived"] = True
            by_term[term][bid] = rec
            added[term][bid] = rec
    n = sum(len(v) for v in added.values())
    print(f"  {p}: {n} bill(s) the General Court's lists lack added from the House Journal"
          + (f" ({', '.join(f'{b} {t}' for t, bb in added.items() for b in bb)})" if n else "")
          + (f"; {len(kept)} already in the record and left alone ({', '.join(kept)})"
             if kept else ""))
    if skipped:
        print(f"  {p}: {len(skipped)} not added: {', '.join(skipped)}")
    return dict(added)


def journal_sponsor_rows(printed, term, sat, legs, current=None):
    """One withdrawn bill's sponsors, as the journal printed them, in the
    shape data/sponsors.json carries them.

    In the journal's order, the first taken as prime -- it is the prime on
    every one of the 1,643 bills of 2025-2026 the sponsor files can check --
    and marked prime_inferred, because the journal does not say so itself.
    Each name is placed by text_sponsors (split, then Sat.resolve among the
    members who cast a roll call that term), and labelled with the seat the
    roster gives that member, not the one printed: the January 2025 lists
    print some members' 2023-2024 seats. A member who has since left is
    labelled from their own votes. A name nobody fits stays as printed.

    IN A TERM THAT IS NOT THE CURRENT ONE (`current` names it) THE SEAT IS THE
    PRINTED ONE. The roster is today's House and Senate, and a label states
    the seat held when the record was made: HB 459 of 2021 prints "Silber,
    Belk. 2", and Rep. Norman Silber's roll-call label says Belknap 6. The row
    is text_sponsors.record's, as every archived bill's sponsors are, and says
    with seat_source that the seat is the journal's, so that build_site_v2
    does not put the roster's over it.
    """
    import text_sponsors as TS
    out = []
    for i, sp in enumerate(TS.split("; ".join(printed or []))):
        m = sat.resolve(term, sp)[0] if sat else None
        if current is not None and term != current:
            r = TS.record(i, sp, m)
            row = {k: r[k] for k in ("member_id", "name", "party", "chamber", "label",
                                     "county", "district")}
            row.update({"sequence": i, "prime": i == 0, "prime_inferred": True,
                        "source": JOURNAL_SOURCE, "seat_source": JOURNAL_SOURCE,
                        "as_printed": sp["printed"]})
            out.append(row)
            continue
        mine = legs.get(str(m["id"])) if m else None
        if mine:
            row = {"member_id": str(m["id"]), "name": mine["name"],
                   "party": mine.get("party_code", ""), "chamber": mine.get("chamber", ""),
                   "label": mine.get("label", ""), "county": mine.get("county_abbr", ""),
                   "district": mine.get("district", "")}
        elif m:
            ch = sp["chamber"]
            county = TS.ABBR.get(m.get("county") or "", "") if ch == "H" else ""
            dist = str(m.get("number") or "")
            last = " ".join(x for x in (m["last"], m.get("suffix")) if x)
            row = {"member_id": str(m["id"]), "name": f"{last}, {m['first']}".strip(", "),
                   "party": m.get("party", ""), "chamber": ch,
                   "label": names.legislator({"first": m["first"], "last": last,
                                              "chamber": ch, "party": m.get("party", ""),
                                              "district": dist, "county_abbr": county}),
                   "county": county, "district": dist}
        else:
            r = TS.record(i, sp, None)
            row = {k: r[k] for k in ("member_id", "name", "party", "chamber", "label",
                                     "district")}
            row["county"] = TS.ABBR.get(r.get("county") or "", r.get("county") or "")
        row.update({"sequence": i, "prime": i == 0, "prime_inferred": True,
                    "source": JOURNAL_SOURCE, "as_printed": sp["printed"]})
        out.append(row)
    return out


# ------------------------------------------------ the General Court's past tables --
#
# THE ARCHIVED RECORDS CAME FROM THE SEARCH PAGE, AND THE SEARCH PAGE LEAVES
# BILLS OUT (1 October 2026). fetch_archive_bills.py asked the General Court's
# bill search for every bill of a past session year, and 25 measures the
# General Court's own database holds were not in what it answered: bills
# withdrawn before or after they were introduced, two the Senate refused to
# introduce, the House's organizing resolutions of December 2016, a petition
# read in and withdrawn. The person decided they get pages -- "sometimes they
# are withdrawn for political reasons, not just procedural". The dump
# fetch_past_db.py made of the PastLegislation view holds each one's LSR,
# title, chamber, referral codes and status codes; the dockets on this disk
# hold their histories.
PAST_SOURCE = "General Court database"
PAST_LEGISLATION = Path("db") / "past" / "PastLegislation.psv"
PAST_MANIFEST = Path("db") / "past" / "_manifest.json"
# General status 01 is "LEGISLATIVE SERVICES": a request still being drafted.
# SR 2 of 2006, SR 2 of 2008 and SB 27 of 2009 were numbered and stopped
# there, with no docket row between them; they were never before a chamber
# and get no record. 02 and after is a measure a chamber had.
PAST_NOT_BEFORE_A_CHAMBER = "01"
# A chamber's status code 24: it refused to introduce the bill.
REFUSED_INTRODUCTION = "REFUSED INTRODUCTION"

# A MEASURE THE DOCKET HOLDS AND NO TABLE TITLES. HR 69 of 1992 is three
# docket rows of 29 April 1992 under LSR 2737 -- reported Ought to Pass, a
# motion to table lost 74-250, adopted on a voice vote -- and nothing else in
# the General Court's data: no row in PastLegislation (HR 68 and HR 70 are
# there, either side of it), none in PastSponsors, no text, no saved page. Its
# title is printed in the bound House Journal of 1992, which is on this disk as
# the University of New Hampshire's scan (archive/unh/raw/, Internet Archive
# item journalofhouseof1992newh): on the regular calendar of 29 April 1992,
# printed page 1154, "HR 69, establishing procedures and deadlines for the
# filing of bills for the 1993 session. OUGHT TO PASS. Rep. Burns for Rules.",
# and again, in the same words, at the motion to table (1155), at third
# reading (1168), in the roll-call index (1359) and in the numerical index
# (1416). Read on 1 October 2026 and confirmed against the scan's own text;
# preflight reads it again wherever the scan is on disk. The record says where
# its title comes from (title_source), and the page says it in a note.
#
# {(term, bill): what the journal gives it}. The LSR is the docket's, and the
# record is added only where the term's docket carries the bill under it.
TITLED_FROM_JOURNAL = {
    ("1991-1992", "HR69"): {
        "lsr_year": "1992", "lsr_num": "2737", "chamber": "H",
        "title": ("establishing procedures and deadlines for the filing of bills "
                  "for the 1993 session."),
        "title_source": {"journal": "House Journal", "date": "1992-04-29",
                         "page": 1154, "volume": "the bound House Journal of 1992"},
    },
}
DOCKET_SOURCE = "General Court docket"

# WHETHER THE HOUSE INTRODUCED IT, WHERE THE DOCKET IS WRONG OR CANNOT SAY
# (1 October 2026). The House introduces its bills by a resolution that names
# them by number, and the journal prints it (journal_bills.
# introduction_resolutions). Six of the measures add_past_bills adds are
# decided by one, and their dockets are not:
#
#   HB 87 and HB 134 of 2009 each have one docket row, "Introduced 1/7/2009
#   and Referred to ...; HJ 8, PG. 121" -- the row every bill of that day was
#   given ahead of it -- and the resolution of 7 January 2009 reads "House
#   Bills numbered 31 through 86, 88 through 133 and 135 through 223"
#   (journals/2009/HJ002.txt:821). The list beneath goes from HB 86 to HB 88
#   and from HB 133 to HB 135, no resolution of 2009 or 2010 names either
#   number, and the database has no introduction date and no House status for
#   either. They were published as introduced and "In committee".
#   HB 633 of 2007 the same: one row, "Introduced and ref to Health, Human
#   Services and Elderly Affairs;", with no journal page where its neighbours
#   cite one, and the resolution of 4 January 2007 reads "579 through 599, 601
#   through 624, 626 through 632, 634 through 639" (journals/2007/HJ004.txt:
#   1394). The database gives its LSR no bill number at all.
#   HB 1284 and HB 1472 of 2012 are withdrawn on the docket, and the
#   resolution of 4 January 2012 steps over both -- "1126 through 1283, 1285
#   through 1471 and 1473 through 1709" (journals/2012/HJ001.txt:33) -- with
#   "HB 1284 - Withdrawn." and "HB 1472 - Withdrawn." in the list beneath.
#   HB 1512 OF 2012 IS THE OTHER WAY ABOUT. Its docket enters "Withdrawn" at
#   8.49 on the morning of 4 January 2012, as HB 1284's does at 8.11, and
#   read alone says it was never introduced. The same resolution names it --
#   it is inside "1473 through 1709" -- and the list prints its entry in full:
#   "HB 1512-FN, relative to the authority of conservation commissions.
#   (Hoelzel, Rock 2: Municipal and County Government)". It was read a first
#   and second time and referred.
#
# AND FOUR THE BILL SEARCH'S OWN LIST CARRIES: HB 177, HB 273, HB 274 and
# HB 277 of 2017. The resolution of 4 January 2017 reads "House Bills numbered
# 76 through 176, 178 through 272, 275 through 276 and 278 through 286"
# (journals/2017/HJ002.txt:1105), and the list beneath goes from HB 176 to
# HB 178, from HB 272 to HB 275 and from HB 276 to HB 278. None of the 41
# House Journals of 2017 and 2018 names any of the four, by number or in a
# range. Their dockets (Docket_2017-2018.txt lines 7326, 9139-9141, 9164)
# are the rows typed ahead of the day and nothing after them:
#   HB 177  "To Be Introduced 01/04/2017 and referred to Election Law",
#           entered 28 December 2016;
#   HB 273  "Introduced 01/04/2017 and referred to Executive Departments and
#           Administration", entered 30 December, and "Public Hearing:
#           01/10/2017 01:30 PM LOB 306", entered 4 January;
#   HB 274  "Introduced 01/04/2017 and referred to Labor, Industrial and
#           Rehabilitative Services", entered 30 December;
#   HB 277  "To Be Introduced 01/04/2017 and referred to Criminal Justice and
#           Public Safety", entered 30 December
# -- none citing a journal page, where HB 176, HB 178, HB 272 and HB 275 cite
# "HJ 2 P. 19" and "HJ 2 P. 22". In PastLegislation each is LSR status 9,
# alone among the numbered rows of 2017 to 2024 (an introduced bill's is 8),
# and each has no committee of referral, alone among the House Bills of 2017;
# its introduction date there, 4 January, is the date the docket row was
# typed with. The search page gives each the House
# status IN COMMITTEE, and they were published as introduced and "In
# committee" -- HB 273 with a public hearing the committee "held". The
# hearing is a notice: House Calendar 6 of 6 January prints it for 1.30 p.m.
# on the 10th, and the committee filed a report of every other hearing it
# noticed for that day and none of this one. Whether anybody met is on no
# record here, and the page says that rather than either answer.
#
# A TABLE OF WHAT WAS READ, NOT A READING MADE EVERY NIGHT: a number a
# resolution steps over is evidence only beside the rest of a bill's record
# (journal_bills says why), and each of these was read beside its docket and
# its database row. preflight reads the journals again wherever they are on
# disk and fails if one of these, or any other measure add_past_bills adds,
# is told against them. On a record add_past_bills makes, and on a record of
# a term's own list that this table names (journal_introductions); every
# other record's introduction is its docket's, as it was. NOT A RULE FOR A
# TERM: the same resolutions step over HB 650 and HB 651 of 2017, which were
# heard, reported and voted on (HB 650 is Chapter 192), and the reader here
# misses the resolution that names HB 397 through 420.
#
# {(term, bill): {"introduced", the sitting's date, its journal, the House
# Bills the resolution names in its own words}}.
_RES_2009 = {"date": "2009-01-07", "journal": "House Journal No. 2",
             "numbered": "31 through 86, 88 through 133 and 135 through 223"}
_RES_2012 = {"date": "2012-01-04", "journal": "House Journal No. 1",
             "numbered": "1126 through 1283, 1285 through 1471 and 1473 through 1709"}
_RES_2017 = {"date": "2017-01-04", "journal": "House Journal No. 2",
             "numbered": "76 through 176, 178 through 272, 275 through 276 and 278 "
                         "through 286"}
INTRODUCTION_FROM_JOURNAL = {
    ("2007-2008", "HB633"): {
        "introduced": False, "date": "2007-01-04", "journal": "House Journal No. 3",
        "numbered": "579 through 599, 601 through 624, 626 through 632, 634 through 639"},
    ("2009-2010", "HB87"): {"introduced": False, **_RES_2009},
    ("2009-2010", "HB134"): {"introduced": False, **_RES_2009},
    ("2011-2012", "HB1284"): {"introduced": False, **_RES_2012},
    ("2011-2012", "HB1472"): {"introduced": False, **_RES_2012},
    ("2011-2012", "HB1512"): {"introduced": True, **_RES_2012},
    ("2017-2018", "HB177"): {"introduced": False, **_RES_2017},
    ("2017-2018", "HB273"): {"introduced": False, **_RES_2017},
    ("2017-2018", "HB274"): {"introduced": False, **_RES_2017},
    ("2017-2018", "HB277"): {"introduced": False, **_RES_2017},
}


def _bill_number(s):
    """"HB  0169" and "HB169" are both HB169; anything else is ""."""
    m = re.match(r"^([A-Z]+)0*(\d+)$", re.sub(r"\s+", "", (s or "").upper()))
    return f"{m.group(1)}{int(m.group(2))}" if m else ""


def past_legislation(d):
    """[row] of db/past/PastLegislation.psv, each a dict by the column names
    db/past/_manifest.json gives -- or None where the dump is not on this
    machine. The .psv carries no header, so the manifest is the only statement
    of its column order, and a line with another number of fields is counted
    and left out rather than read one column along."""
    d = Path(d)
    path, man = d / PAST_LEGISLATION, d / PAST_MANIFEST
    if not (path.exists() and man.exists()):
        return None
    try:
        cols = json.loads(man.read_text(encoding="utf-8"))["PastLegislation"]["columns"]
    except (ValueError, KeyError):
        print(f"  {man} does not say what PastLegislation's columns are; not read")
        return None
    out, odd = [], 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            if len(f) != len(cols):
                odd += 1
                continue
            out.append({k: v.strip() for k, v in zip(cols, f)})
    if odd:
        print(f"  {path}: {odd:,} line(s) with another number of fields than "
              f"{man.name} names, left out")
    return out


def status_words(d):
    """({general status code: words}, {chamber status code: words}) from the
    General Court's own two tables, GeneralCodes.txt and BodyStatusCodes.txt,
    which arrive with the checkout: "03" is SENATE, "24" REFUSED INTRODUCTION.
    The archive's records carry these words, read off the search page; a
    record made from the database carries the same ones."""
    def table(name):
        return {r[0]: r[1] for r in rows(Path(d) / name) if len(r) >= 2 and r[0]}
    return table("GeneralCodes.txt"), table("BodyStatusCodes.txt")


def _code_committee(code, year, committees):
    """The committee a referral code names in that year, or "".

    committee_names.CODES first, which says what each retired code was and
    when (H45 was Redress of Grievances in 2011-2012 and is in no table
    today); then today's Committees.txt. Never the bare code -- "S29" is not
    a name -- and never the General Court's own word for having none (H29,
    "No Committee Assignment")."""
    code = (code or "").strip().upper()
    if not code:
        return ""
    try:
        import committee_names as CN
        y = int(str(year)[:4])
        for _ch, lo, hi, name, c in CN.CODES:
            if c == code and lo <= y <= hi:
                return name
    except Exception:                               # a table that will not read
        pass
    name = (committees.get(code) or {}).get("name", "")
    return "" if _placeholder(name) else name


def _docket_numbers(paths, wanted):
    """{(term, year, lsr number): {bill number}} for the LSRs in `wanted`,
    from the archived dockets -- the number each docket row files the LSR
    under. `paths` is {term: docket file}."""
    out = defaultdict(set)
    for term, path in paths.items():
        if not any(t == term for t, _y, _n in wanted) or not Path(path).exists():
            continue
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                p = line.split("|")
                if len(p) < 7:
                    continue
                key = (term, p[0].strip(), p[1].strip().lstrip("0"))
                if key in wanted and p[3].strip():
                    out[key].add(p[3].strip())
    return out


def _never_introduced(term, bid, rec, dockets):
    """Whether one of add_past_bills' measures was never introduced, as its
    history will tell it: the House Journal's word where the record carries
    one ("introduction"), and otherwise narrative.build's own reading of the
    bill's rows in the term's docket (its not_introduced) -- "Withdrawn Prior
    to Introduction", or withdrawn before the day its "To Be Introduced" row
    names. ONE RULE, narrative's, asked here rather than written twice: the
    committee this decides and the history beneath it are then one account.
    False where the docket is not on this machine or will not read, which
    leaves the record as it was -- and is said, because a committee kept for
    want of a docket looks exactly like one a bill was referred to."""
    said = rec.get("introduction")
    if said is not None and not said.get("introduced"):
        return True
    path = (dockets or {}).get(term)
    if not path or not Path(path).exists():
        print(f"  {bid} of {term}: no docket of the term on this machine to say whether "
              "it was ever introduced; its committee is left as the record gives it")
        return False
    try:
        import narrative as N
        num = str(rec.get("lsr_num") or "").lstrip("0")
        rows = [r for rr in N.parse_docket(path, want_bill=bid).values() for r in rr]
        own = [r for r in rows if r["lsr"].partition("-")[2].strip().lstrip("0") == num]
        rows = own or rows
        return bool(rows) and bool(
            N.build(bid, rows, introduction=said or {}).get("not_introduced"))
    except Exception as e:                          # noqa: BLE001
        print(f"  {bid} of {term}: its docket in {path} would not read ({e}); its "
              "committee is left as the record gives it")
        return False


def add_past_bills(by_term, past, committees, refs, general, body, current="",
                   known=(), in_use=None, dockets=None, introductions=None):
    """{term: {bill: record}}: the measures the General Court's database holds
    and the term's records lack, added to `by_term`.

    A ROW OF PastLegislation BECOMES A RECORD where it has a title, a status
    past Legislative Services (PAST_NOT_BEFORE_A_CHAMBER) and a bill number
    the term has no record under. ONLY INTO A TERM THAT IS ALREADY HERE, NEVER
    OVER A RECORD THAT IS, AND NEVER INTO THE CURRENT TERM, whose own files
    are the better record and which this view does not cover.

    The number is the row's own. One row has none: LSR 2007-0765, "requiring
    interpreting services upon request for persons receiving medical
    treatment", whose docket row files it under HB633. Where a row carries no
    number, its LSR is on no record, and the term's docket files that LSR
    under exactly one number no record carries, that is its number; 26 other
    such rows are requests no docket row numbers, and stay out.

    The committee is the one the docket's own introduction row names
    (`refs`, referrals.read_dockets), as for every archived bill, and
    otherwise the one the row's referral code names -- and none in a chamber
    whose status is REFUSED INTRODUCTION: the Senate refused to introduce
    SB 267 of 2007 and SB 499 of 2016, so nothing was referred, whatever
    code the row still carries. The statuses are the General Court's own
    words for the row's codes.

    AND NONE FOR A BILL THAT WAS NEVER INTRODUCED, for the same reason: a
    bill is referred when it is introduced. HB 1587 of 2010 carries "To Be
    Introduced 1/6/2010 and Referred to Finance" and "Withdrawn Prior to
    Introduction"; with Finance on its record it was listed among the bills
    referred to Finance, on that committee's page and in the download. The
    row's words stay in its history, which tells them as what was to be.
    _never_introduced says which bills these are; the House Journal's word
    on the six it decides (`introductions`, INTRODUCTION_FROM_JOURNAL) goes on
    the record as "introduction", for narrative.py and the page's note.

    The record says where it comes from ("source"), and carries no hearing
    and no text address: the search page gave the archive's, and nothing gave
    these.
    """
    added, kept = defaultdict(dict), Counter()
    if not past:
        return {}
    in_use = in_use or {}
    lsr_on = {t: {(str(r.get("lsr_year") or "").strip(),
                   str(r.get("lsr_num") or "").strip().lstrip("0"))
                  for r in byb.values()} for t, byb in by_term.items()}
    numbered = defaultdict(set)
    for r in past:
        bid = _bill_number(r.get("CondensedBillNo"))
        if bid:
            numbered[P.term_of(r.get("SessionYear"))].add(bid)

    def wanted(r):
        """Whether the row is a measure a chamber had, with a title."""
        return bool(r.get("lsrtitle")) and \
            (r.get("GeneralStatusCode") or "") > PAST_NOT_BEFORE_A_CHAMBER

    # The unnumbered rows a docket may number.
    loose = {}
    for r in past:
        term = P.term_of(r.get("SessionYear"))
        if term in by_term and term != current and wanted(r) \
                and not _bill_number(r.get("CondensedBillNo")):
            key = (term, r["SessionYear"], (r.get("LSR") or "").lstrip("0"))
            if key[1:] not in lsr_on.get(term, ()):
                loose[key] = r
    if dockets is None:
        try:
            import referrals
            dockets = referrals.term_dockets()
        except Exception:                           # no docket is not a failure
            dockets = {}
    named = _docket_numbers(dockets or {}, loose) if loose else {}
    if introductions is None:
        introductions = INTRODUCTION_FROM_JOURNAL

    for r in past:
        term = P.term_of(r.get("SessionYear"))
        if term not in by_term or term == current or not wanted(r):
            continue
        year, lsr = r["SessionYear"], (r.get("LSR") or "").lstrip("0")
        bid = _bill_number(r.get("CondensedBillNo"))
        from_docket = False
        if not bid:
            got = {_bill_number(x) for x in named.get((term, year, lsr), ())} - {""}
            if len(got) != 1:
                continue
            bid = next(iter(got))
            if bid in numbered[term]:
                continue
            from_docket = True
        if bid in by_term[term]:
            kept[term] += 1
            continue
        if bid in added[term]:
            # Two rows of the database under one number and no record for
            # either: the first by LSR is kept, and the other is said.
            print(f"  {PAST_LEGISLATION}: {bid} of {term} is also LSR {year}-{lsr}; "
                  f"the record keeps LSR {added[term][bid]['lsr']}")
            continue
        # The LSR written the way the term's other records write theirs:
        # "354" before 2017, "0412" from it.
        padded = any(len(str(x.get("lsr_num") or "")) == 4
                     and str(x.get("lsr_num")).startswith("0")
                     for x in by_term[term].values())
        num = lsr.zfill(4) if padded else lsr
        gen = general.get(r.get("GeneralStatusCode") or "", "")
        hs = body.get(r.get("HouseStatusCode") or "", "")
        ss = body.get(r.get("SenateStatusCode") or "", "")
        ref = refs.get((term, bid), {})
        m = re.match(r"([A-Z]+)(\d+)$", bid)
        rec = {
            "bill": bid, "lsr": f"{year}-{num}", "lsr_year": year, "lsr_num": num,
            "title": r.get("lsrtitle", ""),
            "chamber": (r.get("LegislativeBody") or bid[:1])[:1].upper(),
            "subject_code": "", "subject": "",
            "house_committee": "" if hs == REFUSED_INTRODUCTION else _pick_committee(
                _code_committee(r.get("HouseCommitteeReferralCode"), year, committees),
                ref.get("H", ""), known, in_use.get((term, "H"), ())),
            "senate_committee": "" if ss == REFUSED_INTRODUCTION else _pick_committee(
                _code_committee(r.get("SenateCommitteeReferralCode"), year, committees),
                ref.get("S", ""), known, in_use.get((term, "S"), ())),
            "hearing": "", "hearing_room": "",
            "designation": f"{m.group(1)} {m.group(2)}" if m else bid,
            "text_pdf": "",
            "gen_status": gen, "house_status": hs, "senate_status": ss,
            "archived": True,
            "source": PAST_SOURCE,
        }
        if from_docket:
            # The number is the docket's, and the record says so.
            rec["number_source"] = DOCKET_SOURCE
        if (term, bid) in introductions:
            # What the House Journal's resolution of introduction says of it.
            rec["introduction"] = dict(introductions[(term, bid)])
        by_term[term][bid] = rec
        added[term][bid] = rec
    # Nothing was referred of a bill that was never introduced.
    bare = []
    for term, recs in sorted(added.items()):
        for bid, rec in sorted(recs.items()):
            if (rec["house_committee"] or rec["senate_committee"]) \
                    and _never_introduced(term, bid, rec, dockets):
                rec["house_committee"] = rec["senate_committee"] = ""
                bare.append(f"{bid} {term}")
    n = sum(len(v) for v in added.values())
    print(f"  {PAST_LEGISLATION}: {n} measure(s) the terms' own lists lack added from "
          "the General Court's database"
          + (f" ({', '.join(f'{b} {t}' for t, bb in sorted(added.items()) for b in sorted(bb))})"
             if n else "")
          + (f"; {len(bare)} of them never introduced, and given no committee "
             f"({', '.join(bare)})" if bare else ""))
    return dict(added)


def journal_introductions(by_term, current="", introductions=None):
    """[(term, bill)]: the House Journal's word, put on the records of a
    term's own list that INTRODUCTION_FROM_JOURNAL names -- HB 177, HB 273,
    HB 274 and HB 277 of 2017, which the bill search's list carries, so that
    add_past_bills never sees them.

    The record takes the reading as "introduction", for narrative.py and the
    page's note, as one add_past_bills makes does. AND NO COMMITTEE WHERE THE
    JOURNAL SAYS THE BILL WAS NOT INTRODUCED: nothing was referred, whatever
    the row typed ahead of the day names, and with the committee on its
    record HB 273 stood among the bills referred to Executive Departments
    and Administration, on that committee's page and in the download. Never
    on the current term, whose own files are its record, and never over a
    reading a record already carries."""
    table = INTRODUCTION_FROM_JOURNAL if introductions is None else introductions
    done, bare = [], []
    for (term, bid), fact in sorted(table.items()):
        rec = (by_term.get(term) or {}).get(bid)
        if rec is None or term == current or "introduction" in rec:
            continue
        rec["introduction"] = dict(fact)
        done.append((term, bid))
        if not fact.get("introduced"):
            if rec.get("house_committee") or rec.get("senate_committee"):
                bare.append(f"{bid} {term}")
            rec["house_committee"] = rec["senate_committee"] = ""
    if done:
        print(f"  the House Journal's resolution of introduction on {len(done)} bill(s) "
              f"of the terms' own lists ({', '.join(f'{b} {t}' for t, b in done)})"
              + (f"; {len(bare)} of them never introduced, and given no committee "
                 f"({', '.join(bare)})" if bare else ""))
    return done


def add_journal_titled(by_term, began, table=None, current=""):
    """{term: {bill: record}}: the measures TITLED_FROM_JOURNAL names, added
    to `by_term` -- in a term already here, never over a record, and only
    where the term's docket carries the bill (`began`, referrals.read_dockets'
    second answer: the chamber each docket key began in). The record is the
    docket's, with the title the House Journal prints and a statement of that
    (title_source); it carries no committee, hearing, text or status field,
    because nothing on disk gives it one, and its status is read from its
    docket rows like any other bill's."""
    added = defaultdict(dict)
    for (term, bid), j in sorted((TITLED_FROM_JOURNAL if table is None else table).items()):
        if term not in by_term or term == current or bid in by_term[term]:
            continue
        if (term, bid) not in began:
            print(f"  {bid} of {term} has a title from the House Journal and no docket "
                  "row on this machine, so it is not added")
            continue
        m = re.match(r"([A-Z]+)(\d+)$", bid)
        rec = {
            "bill": bid, "lsr": f"{j['lsr_year']}-{j['lsr_num']}",
            "lsr_year": j["lsr_year"], "lsr_num": j["lsr_num"],
            "title": j["title"], "chamber": j.get("chamber") or began[(term, bid)],
            "subject_code": "", "subject": "",
            "house_committee": "", "senate_committee": "",
            "hearing": "", "hearing_room": "",
            "designation": f"{m.group(1)} {m.group(2)}" if m else bid,
            "text_pdf": "",
            "gen_status": "", "house_status": "", "senate_status": "",
            "archived": True,
            "source": DOCKET_SOURCE,
            "title_source": dict(j["title_source"]),
        }
        by_term[term][bid] = rec
        added[term][bid] = rec
    if added:
        print("  the House Journal's title on a measure the docket holds and no table "
              "titles: " + ", ".join(f"{b} {t}" for t, bb in added.items() for b in bb))
    return dict(added)


# WHAT A BILL'S OWN SAVED PAGE CALLS IT. The pages fetch_legislation.py saved
# head the text with the designation, twice:
#     HB 25-FN-A - FINAL VERSION                (the version line)
#     HOUSE BILL                                (the caption, over two lines:
#     25-FN-A                                    legislation/1999/HB0025.html)
# and the 1989-1998 pages write the caption on one, "HOUSE BILL NO. 25-FN-A".
# past_flags holds the database's flags to these. Only a line that is the
# designation and nothing else: the file's own first line, "0226-hb 0025",
# and a bill named in a sentence are neither.
PAGES = Path("legislation")
_FLAGS = r"((?:\s?-\s?FN)?(?:\s?-\s?A)?(?:\s?-\s?(?:LOCAL|L))?)"
# Compiled once and compared in Python: a pattern made for each bill's own
# number was compiled 40,000 times a run.
_VERSION_LINE = re.compile(
    r"^([A-Z]{2,5}) ?(0*)(\d+)" + _FLAGS + r" ?[-\u2013\u2014] ?(?:AS |FINAL|VERSION|CHAPTERED)")
_CAPTION_NUMBER = re.compile(r"^0*(\d+)" + _FLAGS + r"$")
_CAPTION_ONE_LINE = re.compile(
    r"^(?:HOUSE|SENATE|CONSTITUTIONAL)[A-Z ]*(?:BILL|RESOLUTION) ?(?:NO\.?)? ?0*(\d+)"
    + _FLAGS + r"$")
_CAPTION = re.compile(r"\b(?:BILL|RESOLUTION)\b")
# Read this far into a page. The heading is in the first lines of the body,
# after the style sheet, and of the 30,393 pages on disk on 1 October 2026 the
# latest style sheet ends 31,983 characters in (legislation/2017/HB0615.html).
_PAGE_HEAD = 60000


def printed_designations(path, kind, num):
    """{suffix}: every designation the page at `path` prints for the bill in
    its heading -- "" for one printed bare -- or an empty set where it prints
    none this reads, or the page is not there. "-L" is "-LOCAL"."""
    import html as _html
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read(_PAGE_HEAD)
    except OSError:
        return set()
    raw = re.sub(r"(?is)<style.*?(?:</style>|$)", "", raw)
    text = _html.unescape(re.sub(r"<[^>]+>", "\n", raw)).replace("\xa0", " ")
    lines = [x for x in (re.sub(r"[ \t]+", " ", l).strip() for l in text.split("\n")) if x]
    num = int(num)

    def norm(suffix):
        return re.sub(r"-L$", "-LOCAL", re.sub(r"\s", "", suffix))
    seen = set()
    for i, line in enumerate(lines[:60]):
        u = line.upper()
        # The version line. Not "HB 0025 - ...": a padded number is the
        # file's own heading, which carries no flags whatever the bill has.
        m = _VERSION_LINE.match(u)
        if m and m.group(1) == kind and int(m.group(3)) == num and not m.group(2):
            seen.add(norm(m.group(4)))
            continue
        # The caption's second line, under "HOUSE BILL".
        m = _CAPTION_NUMBER.match(u)
        if m and int(m.group(1)) == num and i and _CAPTION.search(lines[i - 1].upper()):
            seen.add(norm(m.group(2)))
            continue
        # The caption on one line.
        m = _CAPTION_ONE_LINE.match(u)
        if m and int(m.group(1)) == num:
            seen.add(norm(m.group(2)))
    return seen


# What the last run of past_flags would not write, for the log and for
# preflight: [(term, bill, the database's suffix, the page's)].
PAST_FLAGS_REFUSED = []


def past_flags(by_term, past, current="", printed=None):
    """Put the fiscal-note, appropriation and local flags on an archived
    bill's designation, from the General Court's database. Returns a Counter
    of the suffixes written.

    The current term's designation is "HB 1442-FN-A-LOCAL": LSRs.txt carries
    three flags and the suffixes are built from them. The archive's records
    came from the search page, which gives the bare number, so 1989-2024 read
    "HB 1442" for a bill its own text heads "HB 1442-FN". PastLegislation
    carries the same three columns by name -- AppropriationCode,
    FiscalImpactCode, LocalCode -- and they are the flags LSRs.txt holds in
    its fields 5, 6 and 7: on the 1,387 current bills both carry, the
    database's Legislation view and the file agree on all three.

    MEASURED AGAINST WHAT THE BILLS PRINT, which neither produced (1 October
    2026). The current term's database flags against the designation the
    House Journal prints in its lists of bills introduced: all three agree on
    1,640 of 1,650 House measures -- the appropriation and local flags on
    every one, the fiscal note on all but ten, nine of them a note the
    database has and the introduction list does not. The archive's flags
    against the designation each saved bill page heads its text with: all
    three agree on 29,435 of 29,629 bills, between 97.1% and 99.9% of a term's.

    ONLY WHERE THE DESIGNATION HAS NONE: an archived record with no flags and
    no suffix of its own, joined by its stored LSR -- and refused where the
    database files that LSR under another bill number, as past_sponsors
    refuses it. A record no flag is set on is left exactly as it was.

    AND NOT AGAINST THE BILL'S OWN PAGE. Those rates leave about one bill in a
    hundred where the two differ, and written from the database the site
    called HB 25 of 1999 "HB 25-A" over a text headed "HB 25-FN-A - FINAL
    VERSION", and HB 1419 of 2022 "HB 1419-FN" over "HB 1419-A - AS
    INTRODUCED". A designation is what the bill prints. So where the saved
    page prints the bill's designation and none of the forms it prints is the
    database's, nothing is written: the designation stays the bare number it
    was, which claims nothing, and the bill is counted and named in the log
    (PAST_FLAGS_REFUSED) for a person to decide and for the Clerk's list. A
    page that prints two forms -- the version line and the caption can differ
    -- agrees where either does. A bill with no saved page, or one whose page
    prints no designation this reads, takes the database's flags: there is
    nothing to hold them to. `printed(term, bill, record)` gives the page's
    forms; preflight's fixtures stand in for it, and the default reads
    legislation/<year>/<KIND><number>.html.
    """
    done = Counter()
    del PAST_FLAGS_REFUSED[:]
    if not past:
        return done

    def on_page(term, bid, rec):
        m = re.match(r"^([A-Z]+)(\d+)$", bid)
        if not m:
            return set()
        year = str(rec.get("lsr_year") or "")[:4]
        for name in (f"{m.group(1)}{int(m.group(2)):04d}", bid):
            for ext in ("html", "htm"):
                f = PAGES / year / f"{name}.{ext}"
                if f.exists():
                    return printed_designations(f, m.group(1), m.group(2))
        return set()
    printed = printed or on_page
    yes = lambda v: (v or "").strip().lower() in ("1", "true")
    said = {}
    for r in past:
        try:
            key = (int(r["SessionYear"]), int(r["LSR"]))
        except (KeyError, ValueError):
            continue
        said[key] = (yes(r.get("AppropriationCode")), yes(r.get("FiscalImpactCode")),
                     yes(r.get("LocalCode")), _bill_number(r.get("CondensedBillNo")))
    for term, byb in by_term.items():
        if term == current:
            continue
        for bid, rec in byb.items():
            des = rec.get("designation") or ""
            if not rec.get("archived") or rec.get("flags") or rec.get("suffix") \
                    or "-" in des:
                continue
            try:
                key = (int(rec.get("lsr_year")), int(rec.get("lsr_num")))
            except (TypeError, ValueError):
                continue
            hit = said.get(key)
            if not hit or (hit[3] and hit[3] != bid):
                continue
            a, fn, local = hit[:3]
            suffix = "".join(x for x, on in (("-FN", fn), ("-A", a), ("-LOCAL", local))
                             if on)
            if not suffix:
                continue
            forms = printed(term, bid, rec)
            if forms and suffix not in forms:
                PAST_FLAGS_REFUSED.append((term, bid, suffix, sorted(forms)))
                continue
            rec["flags"] = {"a": a, "fn": fn, "local": local}
            rec["suffix"] = suffix
            rec["designation"] = (des or re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid)) + suffix
            done[suffix] += 1
    return done


def _official_committees(by_term):
    """Every bill's committees under the one name each had at the time.

    committee_names.official says how, and what it may not do. It runs here,
    after _pick_committee has chosen WHICH committee, and only ever changes
    how that committee is spelt -- so the cards, the Committee filter,
    meta.json, bills.csv and the committee pages' bill lists, which all read
    this file, name it one way. The 1991-1992 filter listed "Child Y and Jj",
    "Child, Y and Jj" and "Children Y and Jj" as three committees, and
    1989-1990 carried 112 values for 39 committees.

    Returns {(was, now): count}, which main prints.
    """
    import committee_names as CN
    moved = Counter()
    for term, byb in by_term.items():
        for rec in byb.values():
            for field, ch in (("house_committee", "H"), ("senate_committee", "S")):
                was = rec.get(field) or ""
                now = CN.official(was, ch, term) if was else was
                if now != was:
                    rec[field] = now
                    moved[(was, now)] += 1
    return moved


# THE ONE LONGER NAME THAT IS THE SAME COMMITTEE AT THE SAME TIME, whatever the
# evidence below says. The clerk of 1999-2006 wrote "Public Works" for the
# committee the tables call "Public Works and Highways", and _pick_committee's
# exception was written for it.
_SAME_COMMITTEE_LONGER = {("publicworks", "publicworkshighways")}


def _same_committee(first, stored, known=(), in_use=()):
    """Whether the docket's name and the search page's are one committee.

    Three shapes, and what each needs:

    ONE MISSPELT, OR SHORTENED WORD FOR WORD: "Enviroment", "Puplic
    Affairs", "Exe Depts and Admin", "State-Fed Relations and Vets Aff".
    Enough by itself; the search page's spelling is the better one. The test
    for a misspelling is a similarity ratio of 0.85 over the whole name, and
    it is not only a misspelling test: ten bills of 2011-2012 were referred
    in the House to the "Special Committee on Public Employee Pensions
    Reform" (the docket) and show the "Special Committee on Public Employee
    Pension Plans" (the search page, and the only name the tables know,
    H47), at a ratio of 0.89. Whether that is one committee renamed, and so whether the
    later name may stand, is the same question as the next paragraph's; the
    ratio answers yes, as it did before 23 September.

    THE SEARCH PAGE'S NAME ADDS WORDS TO THE DOCKET'S. That is how a
    committee is renamed, and the search page can carry the name a committee
    had later in the term: the Senate's "Wildlife, Fish and Game" of 2007 was
    "Wildlife, Fish and Game and Agriculture" by 2008, and fourteen bills the
    docket refers to it under the first name stored the second. In this
    shape a later name never replaces the one the bill was referred to (the
    ratio above is the one place it still can). So the longer name is
    kept only where it is the Public Works pair above, or where the docket
    merely cut a name short: the longer is a name the committee tables know,
    and the docket's shorter form is not one the clerks were using (in_use).
    2005 HB1415's "Executive Departments and Admin" and 2007 SB66's "Criminal
    Justice" are each the only such line in their term, against 155 and 108
    first referrals to the full names. An abbreviation with words missing
    ("Child and Fam", for Children and Family Law) likewise needs the longer
    name to be one the tables know.

    THE DOCKET'S NAME ADDS WORDS: "Ways and Means Committee", "JudiciarySJ".
    The search page's name is kept where the tables know it.
    """
    import difflib
    import referrals as _r
    kf, ks = _r._key(first), _r._key(stored)
    if not kf or not ks:
        return False
    if kf == ks or (kf, ks) in _SAME_COMMITTEE_LONGER:
        return True
    if ks.startswith(kf):                       # the stored name adds words
        return ks in known and kf not in in_use
    if kf.startswith(ks):                       # the docket's name adds words
        return ks in known
    if difflib.SequenceMatcher(None, kf, ks).ratio() >= 0.85:
        return True
    wf = [w for w in re.findall(r"[a-z]+", _r.AMP.sub(" and ", first).lower()) if w != "and"]
    ws = [w for w in re.findall(r"[a-z]+", _r.AMP.sub(" and ", stored).lower()) if w != "and"]
    short, full = (wf, ws) if len(wf) <= len(ws) else (ws, wf)

    def shortens(w, f):
        if f.startswith(w):
            return True
        if len(w) >= 3 and w[0] == f[0]:        # a contraction: "depts", "vets"
            rest = iter(f)
            return all(ch in rest for ch in w)
        return False
    if not (short and all(shortens(w, f) for w, f in zip(short, full))
            and any(w != f for w, f in zip(short, full))):
        return False
    if len(wf) == len(ws):
        return True
    return ks in known                          # words missing as well


def _current_referrals(bills, committees, docket):
    """Correct the current term's committees and chamber from its own docket.

    The committee comes from the General Court's referral codes (LSRs.txt, or
    db/Legislation.psv's House and Senate CommitteeReferralCode). Where the
    docket's introduction line names a committee the tables know, the two
    agree on every current bill but five.

    Four are VACATES: the chamber took the bill away from the committee the
    code still names and sent it elsewhere -- "SB 83 is vacated from Commerce
    and referred to Ways and Means". The archive publishes the committee a
    bill was vacated TO as its committee of referral, because the first
    referral did not stand, and the current term follows the same rule.

    The fifth is HB 165 of 2025. Its Senate code is S26, Health and Human
    Services; its docket reads "Introduced 03/27/2025 and Referred to
    Finance", and the Senate calendar (calendars_senate/2025/SC016.txt) lists
    its hearing before Finance. The docket, with the calendar beside it, is
    taken over the code.

    Only a name the committee tables know replaces a code, spelt as the
    tables spell it, so a clerk's typing never displaces a linkable name.

    And the CHAMBER a bill began in, where the record gives none: a CACR the
    session files do not describe is a stub whose chamber is the letter C,
    and its docket's first row says which chamber it began in (CACR 8 of
    2025 began in the Senate).
    """
    if not bills or not Path(docket).exists():
        return
    import referrals as _r
    term = {b: P.term_of(str(r.get("lsr_year") or "")) for b, r in bills.items()}
    try:
        refs, began = _r.read_dockets(
            {t: str(docket) for t in set(term.values()) if t},
            lsr_of={(term[b], b): r.get("lsr_num", "") for b, r in bills.items()})
    except Exception as e:                       # a docket that will not read
        print(f"  current term: docket referrals not read ({e})")
        return
    named = {(str(code)[:1].upper(), _r._key(c["name"])): c["name"]
             for code, c in committees.items() if c.get("name")}
    moved, placed = [], 0
    for b, rec in bills.items():
        ref = refs.get((term[b], b), {})
        for body, field in (("H", "house_committee"), ("S", "senate_committee")):
            name = named.get((body, _r._key(ref.get(body, ""))))
            if name and _r._key(name) != _r._key(rec.get(field) or ""):
                moved.append(f"{b} {body}: {rec.get(field) or '(none)'} -> {name}")
                rec[field] = name
        if rec.get("chamber") not in ("H", "S") and began.get((term[b], b)):
            rec["chamber"] = began[(term[b], b)]
            placed += 1
    if moved:
        print(f"  current term: {len(moved)} committee(s) taken from the docket "
              "over the referral code: " + "; ".join(moved))
    if placed:
        print(f"  current term: {placed} bill(s) given the chamber they began in "
              "from the docket")


def hearing_in_term(raw, term):
    """A hearing date, or "" -- never a date belonging to another bill.

    Three things are dropped, each measured on archive_bills.json rather than
    reasoned about:

    NO DATE. "Time not specified", sometimes with a room after it. Every bill
    of 1989-1998 has this and nothing else -- 8,524 of 8,525 -- so those five
    terms have no hearing dates at all, and a field that says "Time not
    specified" is a placeholder the search prints where it has nothing, not a
    hearing. 172 in 2015-2016 and a scatter elsewhere.

    OUT OF TERM. A bill number names a different bill in every biennium, which
    is the fact this whole project is keyed around, so a date after the term
    ended belongs to whatever bill wears that number now. This is the rule
    that caught 2021-2022 in the first place.

    A TERM KNOWN TO BE SERVED FROM SOMEBODY ELSE'S RECORD. See above.

    It stayed invisible because nothing renders this field. That is not a
    reason to keep it: data/bills.json is an input to everything, and the
    first thing to read it would have published a 2025 hearing on a 2021 bill
    without anybody noticing.
    """
    import re as _re
    if not raw or not term:
        return raw
    if str(term) in NO_HEARING_FROM_LIST:
        return ""
    m = _re.search(r"(?:19|20)\d{2}", str(raw))
    if not m:
        # No year anywhere in it, so there is no date in it.
        return ""
    try:
        a, b = (int(x) for x in str(term).split("-"))
    except ValueError:
        return raw
    return raw if a <= int(m.group(0)) <= b else ""


def status_for_session(raw, bills):
    """({bill: status record} for the current session's bills, [terms the file
    has no slice for]) -- each bill's record from its own term's slice of
    bill_status.json, found by the term its LSR year names.

    This took the file's newest term, on the reading that the newest term is
    the current session's. That holds until the term turns over: the first
    night the General Court's files show 2027-2028, bill_status.json's newest
    slice is still 2025-2026, and every 2027 bill numbered like a 2025 one
    would have taken that bill's title, committee, chapter, text address and
    sponsors, with no error anywhere -- HB 1 has been the budget every term
    since 1993, and would have been 2025's budget with 2025's sponsors. A term
    with no slice gets nothing, and says so. proceedings.for_term, which took
    the newest term of any file by default, went too: this was its only
    caller, and its default was the fault.

    A file still in the flat shape is the current session's, as it always was.
    """
    if not P.term_keyed(raw):
        return raw, []
    by_term = defaultdict(set)
    for bill, rec in bills.items():
        by_term[P.term_of(str(rec.get("lsr_year") or ""))].add(bill)
    out, missing = {}, []
    for term in sorted(by_term):
        if term not in raw:
            missing.append(term)
            continue
        # In the file's own order, which is the order sponsors.json has
        # always been written in.
        out.update((b, v) for b, v in raw[term].items() if b in by_term[term])
    return out, missing


def build_frozen_terms(d, out):
    """--frozen-terms: each frozen term older than the session's, built from
    its own inputs into <out>/frozen/<term>/, one run of this script apiece.
    0 when there is nothing to build or every term built.

    A FINISHED TERM IS BUILT FROM WHAT IT WAS, EVERY NIGHT (5 October 2026).
    Once the General Court's files turn to 2027-2028 they hold no 2025-2026,
    and this script, reading them, would write none: on a copy it wrote
    eighteen archived terms and 78 bills of 2027 and exited 0. freeze_term.py
    keeps the term's day files as installed (frozen/<term>/day/) and the
    database's view of it (db/term/<term>/), and this builds the term from
    them as the session files once built it -- the same code, the same
    reading of member_corrections.json, bill_status.json and the rest -- so
    the published slice is what it was the day before the turn, and a
    correction made after it still reaches the term. The person chose that
    over freezing the built output on 5 October 2026. Until the session's
    files move on, a term frozen early waits and is not built here: the
    session files are still its source."""
    import subprocess
    import freeze_term
    sess = P.session_term(d)
    frozen = freeze_term.frozen_terms(d)
    terms = [t for t in frozen if sess and t < sess]
    if not terms:
        print("no finished term is frozen here"
              + (f": {', '.join(frozen)} frozen, and the session's files are still "
                 f"{sess}'s, which build it" if frozen else "")
              + " -- nothing to build")
        return 0
    for t in terms:
        bad = freeze_term.intact(d, t) + freeze_term.views_intact(d, t)
        if bad:
            print(f"THE FROZEN TERM {t} IS NOT WHOLE, and is not built: " + "; ".join(bad))
            return 1
        r = subprocess.run([sys.executable, __file__, "--dir", str(d), "--out",
                            str(Path(out) / "frozen" / t), "--frozen", t],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        said = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
        for ln in said[-4:]:
            print(f"  {t}: {ln}")
        if r.returncode:
            print(f"THE FROZEN TERM {t} DID NOT BUILD (exit {r.returncode}): "
                  + ((r.stderr or "").strip().splitlines() or ["no error text"])[-1])
            return r.returncode
    return 0


def frozen_record(d, term):
    """What a frozen term's build is built from: the sha256 of its two
    manifests, which change whenever freeze_term writes either."""
    import hashlib
    out = {}
    for key, p in (("day_files", Path(d) / "frozen" / term / "manifest.json"),
                   ("views", Path(d) / "db" / "term" / term / "manifest.json")):
        out[key] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
    return out


def finished_builds(d, out):
    """{term: (bills, sponsors)} of every frozen term older than the session's,
    from <out>/frozen/<term>/ as build_frozen_terms left it. A term frozen and
    not built -- or built from another freeze than the one on disk -- stops
    the run: without it that term would leave the site with nothing failing,
    which is what this was written against."""
    import freeze_term
    sess = P.session_term(d)
    got = {}
    for t in freeze_term.frozen_terms(d):
        if not sess or t >= sess:
            continue
        base = Path(out) / "frozen" / t
        try:
            rec = json.loads((base / "frozen.json").read_text(encoding="utf-8"))
            bills = json.loads((base / "bills.json").read_text(encoding="utf-8"))[t]
            sponsors = json.loads((base / "sponsors.json").read_text(encoding="utf-8")).get(t) or {}
        except (OSError, ValueError, KeyError):
            rec, bills, sponsors = None, None, None
        if not isinstance(rec, dict) or rec.get("built_from") != frozen_record(d, t) or not bills:
            sys.exit(f"THE FROZEN TERM {t} HAS NOT BEEN BUILT from the freeze on disk ({base}). "
                     "Run build_data.py --frozen-terms first -- build_all.py does, in the step "
                     f"before this one. Without it {t} would leave the site.")
        got[t] = (bills, sponsors)
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--out", default="data")
    ap.add_argument("--frozen", metavar="TERM", default="",
                    help="build TERM alone from its frozen inputs (frozen/TERM/day/ and "
                         "db/term/TERM/), writing only its bills and sponsors to --out")
    ap.add_argument("--frozen-terms", action="store_true",
                    help="build every frozen term older than the session's, each into "
                         "<out>/frozen/<term>/, and nothing else")
    a = ap.parse_args()
    d, out = Path(a.dir), Path(a.out)
    if a.frozen_terms:
        return build_frozen_terms(d, out)
    out.mkdir(parents=True, exist_ok=True)
    report = []
    # WHERE THE SESSION'S OWN FILES ARE. The fourteen the night installs are
    # read from here, and for a frozen term from its freeze; everything else
    # -- the database's past views, the roll calls of past years, the
    # journals' withdrawn bills, the status pages, the corrections a person
    # made -- from --dir and the working folder as ever.
    frozen = a.frozen
    sd = d / "frozen" / frozen / "day" if frozen else d
    if frozen:
        if not P.TERM_RE.match(frozen) or not (sd / "Docket.txt").exists():
            sys.exit(f"no frozen day files for {frozen!r} at {sd}")
        if P.session_term(sd) != frozen:
            sys.exit(f"the frozen files at {sd} are {P.session_term(sd) or 'of no term'}'s, "
                     f"not {frozen}'s")
        print(f"THE FROZEN TERM {frozen}, from {sd} and {d / 'db' / 'term' / frozen}")
    # ROWS OF A FINISHED TERM IN THE SESSION'S FILES ARE COUNTED AND LEFT OUT,
    # NEVER MERGED (5 October 2026). The General Court's files do not all turn
    # on one night, and a turned file can still carry the old term's last rows:
    # on a copy, ten 2026 docket rows left in a 2027 Docket.txt made
    # 2025-2026 "already built from session files", so the archive was
    # skipped for the whole term and it shrank to 19 bills; their sponsors
    # were filed under 2027-2028; and a docket holding 2025, 2026 and 2027
    # together keyed the new term's stubs by number onto 2025's. A term frozen
    # and older than the session's is built from its freeze alone
    # (finished_builds), so its rows here are dropped as they are read, each
    # file's count said. One rule for every place that would otherwise replace
    # or skip a whole term on meeting one such row: senate_hearing_reports,
    # fetch_testimony_db, narrative, build_proceedings and build_bill_versions
    # keep it too. And an older term's rows beside the session's with NO
    # freeze stop the run: that is a turn nobody froze, and building on would
    # lose the term or mix the two.
    import freeze_term
    sess = P.session_term(sd)
    gone_terms = [] if frozen else [t for t in freeze_term.frozen_terms(d) if sess and t < sess]
    gone_years = {y for t in gone_terms for y in freeze_term.term_years(t)}
    left_out = Counter()
    for _name, _col in freeze_term.YEAR_COLUMN.items():
        if not (sd / _name).exists():
            continue
        _older = sorted({r[_col] for r in rows(sd / _name) if len(r) > _col
                         and re.fullmatch(r"\d{4}", r[_col]) and sess
                         and P.term_of(r[_col]) < sess and r[_col] not in gone_years})
        if _older:
            sys.exit(f"THE SESSION'S FILES HOLD {', '.join(_older)} BESIDE {sess} ({_name}), "
                     f"and {P.term_of(_older[0])} is not frozen: a turn nobody froze. "
                     "freeze_term.py --session on the last files of that term, before the switch; "
                     "building on would lose the term or mix the two.")

    # ---------------------------------------------------------- counties ---
    counties = {}
    for r in rows(sd / "Counties.txt", 3):
        counties[r[0]] = {"name": r[1], "abbr": r[2].rstrip(".")}
    print(f"counties: {len(counties)}")

    # ------------------------------------------------------- legislators ---
    legs = {}
    bad_party = Counter()
    for r in rows(sd / "legislators.txt", 15):
        pcode = (r[8] or "").upper()
        if r[8] and r[8] != pcode:
            bad_party[r[8]] += 1          # the file contains a lowercase 'r'
        c = counties.get(r[6].zfill(2), {})
        name = f"{r[1]}, {r[2]}".strip(", ")
        legs[r[0]] = {
            "id": r[0], "last": r[1], "first": r[2], "middle": r[3],
            "name": name, "chamber": r[4],
            "county_code": r[6].zfill(2), "county": c.get("name", ""),
            "county_abbr": c.get("abbr", ""), "district": r[7],
            # THE SEAT ON THE HOUSE FLOOR, which this file has carried all
            # along in field 5 and nothing kept. It agrees with the database's
            # Legislators.seatno on all 406 rows.
            #
            # It reads as division * 1000 + seat: 3084 is division 3, seat 84.
            # The Clerk's plan has five divisions whose highest seats are 43,
            # 101, 119, 99 and 43 -- 405 positions -- and no division has a
            # seat 13, which takes it to exactly the 400 seats the House has.
            # A sixth "division" holds one seat, 6002, and it is the Speaker's
            # chair on the rostrum rather than a place on the floor.
            #
            # Senators have none and never will: only the House has a seating
            # chart. All 382 sitting members have one; the 18 gaps are the
            # vacant seats.
            #
            # Worth carrying because a New Hampshire representative's licence
            # plate is their seat number, so this is the field that answers
            # "who is that?" as well as "where do they sit?".
            "seat": (r[5] or "").strip(),
            "party": PARTY.get(pcode, pcode or "Unknown"), "party_code": pcode,
            "email": r[14],
            "address": ", ".join(x for x in [r[10], r[11], r[12], r[13]] if x),
            # names.legislator, so a member reads the same on a bill, on a
            # committee and on their own page. This was
            # "Abbas, Daryl(R) Rock 22" -- a database row rather than a person.
            "label": names.legislator({
                "first": r[2], "last": r[1], "chamber": r[4],
                "party_code": pcode, "county_abbr": c.get("abbr", ""),
                "district": r[7]}),
            # The parameter is pid, and it takes the id from THIS file -- not
            # the member= id used in roll call page links, which is a different
            # space entirely (Keith Ammon is pid 836 and member 377204).
            # Verified against gc.nh.gov/house/members/member.aspx?pid=836.
            "url": f"https://gc.nh.gov/house/members/member.aspx?pid={r[0]}"
                   if r[4] == "H" else
                   # "district02", not "dist2": the word is spelled out and the
                   # number is zero-padded to two digits. Every senator's link
                   # was a 404.
                   f"https://gc.nh.gov/senate/members/webpages/"
                   f"district{int(r[7] or 0):02d}.aspx",
            # These pages carry a photo, a biography, committee positions and
            # towns, but they only resolve while the member is serving. For
            # anyone who has left, the General Court's own fallback is a search
            # across past members.
            "url_past": "https://gc.nh.gov/bill_Status/byAnyMember.aspx",
        }
    # ---- committee assignments, from Members.txt ---------------------------
    # That file is tab-delimited with a header row and carries five committee
    # columns per member, plus a phone number and their title. It has no member
    # id, so it cannot be joined on the key everything else uses -- but both it
    # and legislators.txt carry the work email, which is unique. Falling back to
    # a name match catches the few where an address differs.
    mp = sd / "Members.txt"
    if mp.exists():
        by_email = {m["email"].lower(): m for m in legs.values() if m.get("email")}
        by_name = {f"{m['last']}|{m['first']}".lower(): m for m in legs.values()}
        matched = unmatched = 0
        with open(mp, encoding="utf-8-sig", errors="replace") as fh:
            head = next(fh).rstrip("\n").split("\t")
            col = {n.strip().lower(): i for i, n in enumerate(head)}
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) < len(head):
                    continue
                get = lambda name: (_unquote(f[col[name]])
                                    if name in col and col[name] < len(f) else "")
                m = by_email.get(get("workemail").lower()) or \
                    by_name.get(f"{get('lastname')}|{get('firstname')}".lower())
                if not m:
                    unmatched += 1
                    continue
                matched += 1
                cs = []
                for i in range(1, 6):
                    c = get(f"committee{i}")
                    if c and c not in cs:
                        cs.append(c)
                m["committees"] = cs
                m["title"] = get("persontitle")
                m["phone"] = get("phone")
                m["elected_status"] = get("electedstatus")
        withc = sum(1 for m in legs.values() if m.get("committees"))
        print(f"committee assignments: {matched} members matched, "
              f"{withc} with at least one committee")
        if unmatched:
            report.append(f"{unmatched} rows in Members.txt matched nobody in the "
                          "roster \u2014 expected, since that file also lists members "
                          "who have left")
        allc = Counter(c for m in legs.values() for c in m.get("committees", []))
        report.append(f"{len(allc)} distinct committees named across the roster; "
                      f"largest is {allc.most_common(1)[0][0]} with "
                      f"{allc.most_common(1)[0][1]} members" if allc else
                      "no committee assignments parsed \u2014 check Members.txt")

    house = sum(1 for m in legs.values() if m["chamber"] == "H")
    print(f"legislators: {len(legs)}  ({house} House, {len(legs)-house} Senate)")
    if bad_party:
        report.append(f"party codes with inconsistent case, normalised: {dict(bad_party)}")

    # ------------------------------------------------------------ towns ---
    # countyCode + district -> towns, and the reverse.
    towns, seats = defaultdict(list), defaultdict(list)

    # districts/house.txt includes the 41 floterial districts that
    # HouseDistricts.txt leaves out entirely, which is why eight sitting members
    # matched no town at all. Prefer it where parse_districts.py has run.
    dj = {}
    djp = Path("site/districts.json")
    if djp.exists():
        dj = json.loads(djp.read_text(encoding="utf-8"))
    if dj:
        cc_of = {v["name"]: k for k, v in counties.items()}
        nflot = 0
        for town, wards in dj.items():
            for ward, v in wards.items():
                for h in v.get("house", []):
                    cc = cc_of.get(h["county"], "")
                    if not cc:
                        continue
                    key = f"{cc}-{str(h['district']).lstrip('0') or '0'}"
                    seats[key].append({"town": town, "ward": ward})
                    towns[town].append({"county_code": cc, "county": h["county"],
                                        "district": str(h["district"]),
                                        "ward": ward,
                                        "floterial": h.get("floterial", False)})
                    nflot += bool(h.get("floterial"))
        print(f"districts: {len(towns)} towns from districts.json "
              f"({nflot} floterial town-district pairs)")

    for r in ([] if dj else rows(sd / "HouseDistricts.txt", 4)):
        cc, dist, ward, town = r[0].zfill(2), r[1].lstrip("0") or "0", r[2], r[3]
        key = f"{cc}-{dist}"
        seats[key].append({"town": town, "ward": ward})
        towns[town].append({"county_code": cc, "county": counties.get(cc, {}).get("name", ""),
                            "district": dist, "ward": ward})
    print(f"towns: {len(towns)} across {len(seats)} House districts")

    sen_towns = {}
    _sp = Path("data/senate_towns.json")
    if _sp.exists():
        sen_towns = json.loads(_sp.read_text(encoding="utf-8"))
        print(f"senate districts: {len(sen_towns)} with towns on file")

    def town_label(seat):
        """"Manchester Ward 3", or just "Manchester" where there is no ward.

        HouseDistricts.txt gives a ward for every town-district pair and puts
        0 where the town is not warded. The ward was being read and dropped on
        the next line, so a member representing one ward of a city was shown
        as representing the whole city -- which in Manchester or Nashua is
        eleven other members' constituents.
        """
        w = str(seat.get("ward") or "0").lstrip("0")
        return f"{seat['town']} Ward {w}" if w else seat["town"]

    for m in legs.values():
        if m["chamber"] == "H":
            k = f"{m['county_code']}-{m['district'].lstrip('0') or '0'}"
            rows_ = seats.get(k, [])
            m["towns"] = sorted({town_label(s) for s in rows_})
            # The parts, kept separately, so a page can group by town rather
            # than reprint the city name once per ward.
            m["town_seats"] = sorted(
                ({"town": s["town"],
                  "ward": str(s.get("ward") or "0").lstrip("0")}
                 for s in {(x["town"], x.get("ward")): x for x in rows_}.values()),
                key=lambda x: (x["town"], int(x["ward"] or 0)))
        else:
            # Senate districts are not in HouseDistricts.txt; they come from
            # the database's senateDistricts table, via
            # fetch_senate_districts_db.py. Before that, every senator's page
            # said nothing at all about the towns they represent.
            rows_ = sen_towns.get(m["district"].lstrip("0") or "0", [])
            m["towns"] = sorted({
                f"{x['town']} Ward {x['ward']}" if x.get("ward") else x["town"]
                for x in rows_})
            m["town_seats"] = [{"town": x["town"], "ward": x.get("ward") or ""}
                               for x in rows_]
    unmatched = [m for m in legs.values() if m["chamber"] == "H" and not m["towns"]]
    if unmatched:
        # Name the actual county and district. NH has floterial districts, which
        # overlay several towns already covered by their own districts and are
        # numbered separately, so they may simply be absent from
        # HouseDistricts.txt rather than mismatched.
        detail = "; ".join(f"{m['name']} = {m['county']} {m['district']}"
                           for m in unmatched)
        report.append(f"{len(unmatched)} House members whose district matched no "
                      f"town: {detail}")
        seats_by_county = defaultdict(set)
        for k in seats:
            cc, dist = k.split("-")
            seats_by_county[cc].add(int(dist))
        for m in unmatched:
            have = sorted(seats_by_county.get(m["county_code"], []))
            # Not `d`: that name holds the working directory Path, and rebinding
            # it here turned every later `d / "SomeFile.txt"` into int / str.
            dist_no = int(m["district"] or 0)
            report.append(f"    {m['county']} has districts "
                          f"{have[0] if have else '-'}\u2013{have[-1] if have else '-'}; "
                          f"this member is district {dist_no}"
                          + (" (above the range, so probably floterial)"
                             if have and dist_no > have[-1] else ""))
    report.append("Senate districts are not in HouseDistricts.txt, so town lookup "
                  "covers representatives only. Senate needs another source.")

    # --------------------------------------------------------- subjects ---
    subjects = {r[1]: {"id": r[0], "code": r[1], "name": r[2]}
                for r in rows(sd / "SubjectCodes.txt", 3)}
    committees = {r[0]: {"code": r[0], "name": r[1], "abbr": r[2]}
                  for r in rows(sd / "Committees.txt", 3)}
    print(f"subjects: {len(subjects)}   committees: {len(committees)}")

    # ------------------------------------------------------------ bills ---
    bills, by_lsr = {}, {}
    for r in rows(sd / "LSRs.txt"):
        if len(r) < 33:
            continue
        if r[0] in gone_years:
            left_out["LSRs.txt"] += 1
            continue
        bill = r[10].upper()
        if not bill:
            continue
        hc, sc = r[13], r[21]
        # LSRs.txt fields 5, 6 and 7 are 0/1 flags with no documentation. The
        # suffixes on a bill number are -FN (has a fiscal note), -A (carries an
        # appropriation) and -LOCAL (has a local impact), and they appear in
        # that order: "HB 1442-FN-A-LOCAL". Three undocumented booleans against
        # three suffixes is a strong fit, but the ORDER of the columns is a
        # guess and needs checking against a bill whose designation you know.
        flags = {"a": r[5] == "1", "fn": r[6] == "1", "local": r[7] == "1"}
        suffix = "".join(x for x, on in
                         (("-FN", flags["fn"]), ("-A", flags["a"]),
                          ("-LOCAL", flags["local"])) if on)
        rec = {
            "bill": bill, "lsr": f"{r[0]}-{r[1]}", "lsr_year": r[0], "lsr_num": r[1],
            "title": r[2], "chamber": r[3],
            "subject_code": r[12],
            "subject": subjects.get(r[12], {}).get("name", ""),
            "house_committee": committees.get(hc, {}).get("name", hc),
            "senate_committee": committees.get(sc, {}).get("name", sc),
            "hearing": r[31] or "", "hearing_room": r[32] or "",
            "suffix": suffix, "flags": flags,
            "designation": re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bill) + suffix,
        }
        bills[bill] = rec
        by_lsr[(r[0], r[1])] = bill
    # LSRs.txt does not cover every bill the docket knows about: 1,387 rows
    # against 2,233 bills with docket history. Building the site's bill list
    # from LSRs.txt alone hides roughly 800 bills that have a real record.
    # Add a stub for anything the docket mentions but LSRs.txt omits, so it is
    # searchable and has a history page even without a subject or committee.
    from_lsrs = len(bills)
    docket_bills, docket_titles = {}, {}
    dp = sd / "Docket.txt"
    if dp.exists():
        with open(dp, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                f = line.split("|")
                if len(f) > 5 and f[3].strip():
                    if f[0].strip() in gone_years:
                        left_out["Docket.txt"] += 1
                        continue
                    b = f[3].strip().upper()
                    docket_bills.setdefault(b, (f[0].strip(), f[1].strip()))
    # Roll call rows carry a title, which is better than nothing for a stub.
    rp = sd / "RollCallSummary.txt"
    if rp.exists():
        with open(rp, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                f = line.split("|")
                if len(f) > 12 and f[4].strip() and f[12].strip() \
                        and f[0].strip() not in gone_years:
                    docket_titles.setdefault(f[4].strip().upper(), f[12].strip())
    # Titles recovered from the legacy docket pages for bills the current
    # session's files no longer describe.
    fetched_titles = {}
    tp = Path("bill_titles.json")
    if tp.exists():
        fetched_titles = json.loads(tp.read_text(encoding="utf-8"))
        print(f"recovered titles on file: {len(fetched_titles):,}")

    added = 0
    for b, (yr, lsr) in docket_bills.items():
        if b in bills:
            continue
        bills[b] = {"bill": b, "lsr": f"{yr}-{lsr}", "lsr_year": yr, "lsr_num": lsr,
                    "title": (fetched_titles.get(b)
                              or docket_titles.get(b, "")), "chamber": b[0],
                    "subject_code": "", "subject": "",
                    "house_committee": "", "senate_committee": "",
                    "hearing": "", "hearing_room": "", "stub": True}
        by_lsr.setdefault((yr, lsr), b)
        added += 1
    for b, t in fetched_titles.items():
        if b in bills and not bills[b].get("title"):
            bills[b]["title"] = t
    # THE WHOLE FIRST YEAR OF THE TERM HAD NO COMMITTEE AND NO SUBJECT.
    # LSRs.txt covers session-year 2026 only, so every bill filed in 2025 --
    # 847 of them -- was a stub above, and the committee pages listed only
    # 2026's: House Election Law showed 73 bills "referred to this committee
    # in 2025-2026" and 2025's HB151 was not among them. The database's
    # Legislation view is the same record for both years. On the 1,387 bills
    # the two carry in common its columns 18, 26 and 12 equal LSRs.txt's 13,
    # 21 and 12 -- House committee, Senate committee, subject -- 1,387 of
    # 1,387 each, as do the LSRs. So it fills the same fields from the same
    # record, only where a bill has none, and only for the bill whose LSR it
    # names.
    lp = (d / "db" / "term" / frozen if frozen else d / "db") / "Legislation.psv"
    if lp.exists():
        leg_filled = Counter()
        with open(lp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                f = line.rstrip("\n").split("|")
                if len(f) < 27:
                    continue
                rec = bills.get(f[14].strip().upper())
                if not rec or str(rec.get("lsr_num") or "").lstrip("0") != \
                        f[3].strip().lstrip("0"):
                    continue
                hc, sc, subj = f[18].strip(), f[26].strip(), f[12].strip()
                if hc and not rec.get("house_committee"):
                    rec["house_committee"] = committees.get(hc, {}).get("name", hc)
                    leg_filled["House committee"] += 1
                if sc and not rec.get("senate_committee"):
                    rec["senate_committee"] = committees.get(sc, {}).get("name", sc)
                    leg_filled["Senate committee"] += 1
                if subj and not rec.get("subject_code"):
                    rec["subject_code"] = subj
                    rec["subject"] = subjects.get(subj, {}).get("name", "")
                    leg_filled["subject"] += 1
        if leg_filled:
            print("db/Legislation.psv, for bills LSRs.txt does not carry: "
                  + ", ".join(f"{v:,} {k}" for k, v in leg_filled.items()))
    _current_referrals(bills, committees, dp)
    nsuf = Counter()
    for b in bills.values():
        if b.get("suffix"):
            nsuf[b["suffix"]] += 1
    if nsuf:
        report.append("bill-number suffixes derived from LSRs.txt columns 5/6/7: "
                      + ", ".join(f"{k} {v}" for k, v in nsuf.most_common(6))
                      + ". VERIFY the column order against a bill whose "
                      "designation you know \u2014 HB 1442 should be -FN.")
    print(f"bills: {len(bills)}  ({from_lsrs} from LSRs.txt, {added} added from "
          f"the docket)")
    untitled = sum(1 for r in bills.values() if not r.get("title"))
    if untitled:
        print(f"  {untitled:,} still have no title - run fetch_bill_titles.py")
    if added:
        titled = sum(1 for b in bills.values() if b.get("stub") and b["title"])
        yrs = Counter(bills[b]["lsr_year"] for b in bills if bills[b].get("stub"))
        report.append(
            f"{added} bills are in Docket.txt but not LSRs.txt, by LSR year "
            f"{dict(yrs)}. LSRs.txt, LsrsOnly.txt and RollCallSummary.txt all "
            "cover the current session only, so these carry a docket history but "
            f"no title, subject or sponsor ({titled} picked up a title from roll "
            "calls). Their titles live on the legacy docket pages.")
    unmapped = sum(1 for b in bills.values()
                   if b.get("subject_code") and not b["subject"])
    if unmapped:
        report.append(f"{unmapped} bills carry a subject code that is not in "
                      "SubjectCodes.txt")

    # --------------------------------------------------------- sponsors ---
    # LsrsOnly.txt is the better sponsor source. It states "Prime" or "Sponsor"
    # outright instead of encoding it in a flag, and carries the bill number and
    # title on every row, so it also supplies titles for bills that LSRs.txt
    # omits entirely.
    #   26-2001|944|1190|2026|Sponsor|SB416|H|relative to the pooling of tips.
    sponsors = defaultdict(list)
    lo = sd / "LsrsOnly.txt"
    lo_rows = [r for r in rows(lo, 8)] if lo.exists() else []
    left_out["LsrsOnly.txt"] += sum(1 for r in lo_rows if r[3] in gone_years)
    lo_rows = [r for r in lo_rows if r[3] not in gone_years]
    if lo_rows:
        seen = set()
        for r in lo_rows:
            bill, mid, role = r[5].upper(), r[1], r[4]
            m = legs.get(mid)
            if not bill or (bill, mid) in seen:
                continue
            seen.add((bill, mid))
            if bill in bills and not bills[bill].get("title"):
                bills[bill]["title"] = r[7]
            sponsors[bill].append({
                "member_id": mid,
                "name": m["name"] if m else f"Former member #{mid}",
                "party": m["party_code"] if m else "X",
                "chamber": r[6],
                "label": m["label"] if m else f"Former member #{mid}",
                "sequence": 0 if role.lower() == "prime" else 1,
                "prime": role.lower() == "prime", "role": role})
        for b in sponsors:
            sponsors[b].sort(key=lambda x: (x["sequence"], x["name"]))
        nprime = sum(1 for v in sponsors.values() for x in v if x["prime"])
        noprime = sum(1 for v in sponsors.values() if not any(x["prime"] for x in v))
        print(f"sponsors: {sum(len(v) for v in sponsors.values()):,} links across "
              f"{len(sponsors):,} bills (from LsrsOnly.txt)")
        report.append(f"sponsors read from LsrsOnly.txt, which labels the prime "
                      f"sponsor explicitly: {nprime:,} primes, {noprime} bills with "
                      "none marked")
        unknown = {x["member_id"] for v in sponsors.values() for x in v
                   if x["party"] == "X"}
        if unknown:
            report.append(f"{len(unknown)} sponsors are not in legislators.txt "
                          "(former members)")

    lo_bills = set(sponsors)
    # LsrsOnly.txt can list a bill's sponsors and mark NONE of them prime --
    # which happens when the prime has left office. The fallback below was then
    # skipped wholesale for that bill ("already covered, and better"), so the
    # prime LsrSponsors.txt does flag never got read, and build_site_v2 fell
    # back to sp_list[0]. Because these rows all carry sequence 1 and are sorted
    # on (sequence, name), position 0 is then the ALPHABETICALLY first surviving
    # sponsor: HB 1036 of 2026 is printed "Rep. Vose, Rock. 5; Rep. DeSimone...;
    # Rep. Kofalt...; Rep. Kuttab...; Rep. Lynn..." and the site credited
    # Rep. Debra DeSimone.
    #
    # LsrsOnly is still better where it speaks. It is only where it says nothing
    # about the prime that the other file is asked, and then only for WHICH of
    # the sponsors already read is the prime -- never to add a row, which would
    # duplicate what LsrsOnly supplied.
    lo_noprime = {b for b, v in sponsors.items()
                  if not any(x.get("prime") for x in v)}
    lo_flagged_prime = {}
    flags, cross, missing_member, missing_lsr = Counter(), Counter(), 0, 0
    # LsrsOnly.txt does not cover every bill -- HB197 and HB104 came back with
    # no sponsors at all. So fall back to LsrSponsors.txt per bill rather than
    # picking one file for everything.
    for r in rows(sd / "LsrSponsors.txt", 5):
        if r[0] in gone_years:
            left_out["LsrSponsors.txt"] += 1
            continue
        bill = by_lsr.get((r[0], r[1].zfill(4)))
        if not bill:
            missing_lsr += 1
            continue
        if bill in lo_bills:
            # Already covered, and better, by LsrsOnly -- except for the one
            # thing LsrsOnly did not say. See lo_noprime above.
            if bill in lo_noprime and r[4] == "1":
                lo_flagged_prime[bill] = r[3]
            continue
        m = legs.get(r[3])
        if not m:
            missing_member += 1
            # A PRIME dropped here is not just a missing name, it is a wrong
            # byline: with no flagged row left, the block below falls back to
            # sequence order and the next sponsor inherits the authorship. Keep
            # the id so it can be restored once `former` can name it.
            if r[4] == "1":
                lo_flagged_prime.setdefault(bill, r[3])
            continue
        flags[r[4]] += 1
        # Hypothesis: the flag marks a sponsor from the OTHER chamber.
        cross[(r[4], m["chamber"] != bills[bill]["chamber"])] += 1
        sponsors[bill].append({"member_id": r[3], "name": m["name"],
                               "party": m["party_code"], "chamber": m["chamber"],
                               "label": m["label"], "sequence": int(r[2] or 0),
                               "flag": r[4]})
    # Field 4 = 1 marks the prime sponsor. There are about as many 1s as there
    # are bills, and it matched the prime sponsor on gencourt for SB566. The
    # earlier cross-chamber reading was wrong.
    # Only relevant to the LsrSponsors.txt fallback. When LsrsOnly.txt supplied
    # the sponsors it already said "Prime" outright, and re-deriving it here
    # from a flag those rows do not have would overwrite the right answer.
    # Runs for bills that came from LsrSponsors.txt, whether or not LsrsOnly.txt
    # supplied others. Guarding the whole block on "LsrsOnly was absent" left the
    # fallback bills with no prime field at all.
    disagree = 0
    if True:
        for b in [x for x in sponsors if x not in lo_bills]:
            sponsors[b].sort(key=lambda x: x["sequence"])
            flagged = [x for x in sponsors[b] if x["flag"] == "1"]
            for x in sponsors[b]:
                x["prime"] = (x["flag"] == "1") if flagged else (x["sequence"] == 1)
            if flagged and flagged[0]["sequence"] != 1:
                disagree += 1
    filled = len(sponsors) - len(lo_bills)
    if filled:
        print(f"sponsors: {filled:,} further bills filled from LsrSponsors.txt")
    print(f"sponsors: {sum(len(v) for v in sponsors.values()):,} links across "
          f"{len(sponsors):,} bills in total")
    # Bills the current session's files do not cover, from the STATUS page --
    # which lists sponsors as labelled links with party and member id, rather
    # than leaving them to be sifted out of docket prose.
    bsp = Path("bill_status.json")
    if bsp.exists():
        # Keyed on the term, and each bill takes its own term's record:
        # status_for_session says why not the newest.
        raw = json.loads(bsp.read_text(encoding="utf-8"))
        st, no_slice = status_for_session(raw, bills)
        if no_slice:
            print(f"bill status page: nothing for {', '.join(t or 'no term' for t in no_slice)}"
                  " -- bill_status.json has no slice for it yet")
        added_sp = added_t = 0

        def status_sponsors(v):
            """One bill's sponsors as the status page lists them.

            Lifted out of the loop below so an ARCHIVED term can use it too.
            Its sponsors arrive the same way and in the same shape; the only
            difference is which term they are filed under, and that used to be
            unrepresentable because sponsors.json was keyed on the bill number
            alone.
            """
            return [
                {"member_id": x.get("web_member_id", ""), "name": x["name"],
                 "party": x.get("party", ""),
                 # The page states a chamber for members it can link and
                 # leaves it blank for the rest -- 361 sponsor entries, all of
                 # them people who have since left, which put them on the page
                 # under a heading about a missing chamber rather than beside
                 # their colleagues.
                 #
                 # It does give a senate district, and only ever to senators:
                 # across the 12,659 entries whose chamber the page DOES state,
                 # all 4,109 senators carry one and none of the 8,550
                 # representatives does. So a blank chamber with no senate
                 # district is a representative, which is a reading of the
                 # page rather than an assumption about who tends to leave.
                 "chamber": (x.get("chamber", "")
                             or ("S" if (x.get("senate_district") or "").strip()
                                 else "H")),
                 "label": (f"{x['name']} ({x['party']})" if x.get("party")
                           else x["name"]),
                 "sequence": i, "prime": i == 0, "url": x.get("url", ""),
                 "source": "bill status page", "prime_inferred": True}
                for i, x in enumerate(v.get("sponsors") or [])]

        for bill, v in st.items():
            if bill in bills:
                if v.get("title") and not bills[bill].get("title"):
                    bills[bill]["title"] = v["title"]
                    added_t += 1
                for k in ("committee_code", "chapter", "text_pdf"):
                    if v.get(k) and not bills[bill].get(k):
                        bills[bill][k] = v[k]
            if not v.get("sponsors") or (sponsors.get(bill)):
                continue
            sponsors[bill] = status_sponsors(v)
            added_sp += 1
        if added_sp or added_t:
            print(f"bill status page: {added_sp:,} bills gained sponsors, "
                  f"{added_t:,} gained a title")
            report.append(f"{added_sp:,} bills took their sponsors from the bill "
                          "status page, because the sponsor files cover the "
                          "current session only. Prime is the first listed there; "
                          "the page does not mark the field.")

    nosp = [b for b in bills if b not in sponsors]
    if nosp:
        report.append(f"{len(nosp)} bills still have no sponsor in either file "
                      f"(e.g. {', '.join(sorted(nosp)[:5])})")
    nflag = flags.get("1", 0)
    # Belt and braces: anything that still lacks the field falls back to first
    # in sequence, so a later change to either source cannot crash the build.
    for b in sponsors:
        for x in sponsors[b]:
            x.setdefault("prime", x.get("sequence", 1) in (0, 1))
    noprime = sum(1 for b in sponsors if not any(x["prime"] for x in sponsors[b]))
    if flags:
        report.append(f"prime sponsor from field 4: {nflag:,} flagged across "
                      f"{len(sponsors):,} bills; {noprime} bills have none flagged "
                      f"(sequence order used there); {disagree} where the flagged "
                      "sponsor was not first in sequence")
    if missing_lsr or missing_member:
        report.append(f"sponsor rows dropped: {missing_lsr} unknown LSR, "
                      f"{missing_member} unknown member")

    # ------------------------------------------------------- roll calls ---
    # Names for members who left mid-term, from resolve_members.py.
    former = {}
    fp = Path("former_members.json")
    if fp.exists():
        former = json.loads(fp.read_text(encoding="utf-8"))
        print(f"former members named: {len(former)}")

    # And beneath it, the General Court's own list of everybody who has served.
    #
    # Twenty-four years of roll calls came off the database dump, and 783,919
    # of their ballots were cast by somebody this site could not name --
    # "Member #330274" -- because the roster views reach 1,081 people and
    # former_members.json 676. past_members.json holds 2,614,
    # keyed by the same Employeeno the roll call history uses, and names
    # 733,474 of those ballots: 93%.
    #
    # It goes UNDER what is already here and never over it. The two files do
    # not currently share a single key -- former_members is PersonID-shaped
    # and this is Employeeno-shaped -- but relying on that would be relying on
    # a coincidence, and a name a person checked beats one read off a dropdown.
    #
    # What it does not carry is a PARTY, and none is invented: a member named
    # only from here votes with no party letter. Guessing one from a later
    # namesake would fabricate the fact a reader is most likely to act on.
    try:
        import past_members
        _past = past_members.roster()
    except Exception as e:
        print(f"  past members: none ({e})")
        _past = {}
    _added = 0
    for _mid, _rec in _past.items():
        if _mid not in former:
            former[_mid] = _rec
            _added += 1
    if _added:
        print(f"past members named from the General Court's own list: {_added:,}")

    # And the party, from the roll call pages.
    #
    # past_members.json names people and carries no party, so 773,506 ballots
    # were named and partyless. The page that has it is the legacy roll call
    # detail, which prints every member's party, county and district beside
    # their vote; fetch_rollcall_parties.py took the fullest vote of each year
    # and chamber -- 54 requests for 2,078 members.
    #
    # This fills a party where there is none and NEVER replaces one. A party
    # already on a record came from the roster the General Court publishes for
    # sitting members; this came from one roll call of one year, and where the
    # two disagree the roster is the better witness. The county and district
    # are taken the same way, because past_members gives both and this
    # confirms them.
    _party = {}
    _pp = Path("member_party.json")
    if _pp.exists():
        _party = json.loads(_pp.read_text(encoding="utf-8"))
    _gave = _new = 0
    for _mid, _rec in _party.items():
        _who = former.get(_mid)
        if _who is None:
            # Nobody names this voter -- not the roster, not former_members,
            # not the General Court's own list of everyone who served. The
            # roll call page prints them, and the solver pinned which
            # employeeno they are by constraint rather than by resemblance:
            # a printed row must be one of that roll call's voters, must have
            # cast the vote printed beside the name, and must be the same
            # person on every page it appears on. Held out against 286 people
            # whose answer was already known, it returned 286 correct and 0
            # wrong. Where it cannot determine an answer it says nothing, and
            # those ballots keep "Member #" and no party.
            if _rec.get("name"):
                former[_mid] = {"name": _rec["name"], "party": _rec.get("party", ""),
                                "county": _rec.get("county", ""),
                                "district": _rec.get("district", "")}
                _new += 1
            continue
        if not (_who.get("party") or "").strip():
            _who["party"] = _rec.get("party", "")
            _who["county"] = _who.get("county") or _rec.get("county", "")
            _who["district"] = _who.get("district") or _rec.get("district", "")
            _gave += 1
    if _gave:
        print(f"past members given a party from the roll call pages: {_gave:,}")
    if _new:
        print(f"voters named only by the solver, from those same pages: {_new:,}")

    # ------------------------------------------ what a person has corrected ---
    #
    # LAST, OVER EVERY GENERATED SOURCE, AND OVER NOTHING ELSE. By this line
    # `former` has been assembled from all three -- former_members.json, then
    # past_members under it, then member_party.json filling blanks -- and no
    # consumer has read it yet, so this is the one place a correction reaches
    # every name the site shows for a member who has left.
    #
    # It exists because a generated name can be wrong and nothing downstream
    # can tell. resolve_members.py cannot look an id up: the General Court's
    # website and its data files number people in two spaces, so it deduces
    # who an id is by intersecting a saved roll call page with the ids that
    # voted. One of its 676 deductions landed on the wrong person, and put
    # Thomas Oppel's name on 4,250 ballots cast between 2005 and 2024,
    # including 362 in which that member presided as Speaker. member_corrections
    # .json carries the correction and the evidence for it.
    #
    # A correction that matches nothing is a correction that has stopped
    # working -- the id space changed, or the defect was fixed upstream and
    # the entry outlived it -- so it says so rather than passing quietly.
    cp = Path("member_corrections.json")
    ballot_fix = {}
    if cp.exists():
        _doc = json.loads(cp.read_text(encoding="utf-8"))
        fixed = _doc.get("members") or {}

        # Corrections keyed by ROLL CALL, not by member. Two 2017 House ballots
        # carry an empty member id in the General Court's own record, and an
        # empty id is one bucket that both fall into -- so a member-keyed
        # correction would put both on whichever person it named. The key is
        # (year, body, vote_number), which names a roll call exactly.
        for _k, _v in (_doc.get("ballots") or {}).items():
            if _k.startswith("_") or not isinstance(_v, dict):
                continue
            _parts = tuple(_k.split("|"))
            if len(_parts) != 3:
                print(f"  WARNING: ballot correction key {_k!r} is not "
                      f"year|body|vote_number; ignored")
                continue
            ballot_fix[_parts] = _v

        hit = named = 0
        for _mid, _fix in fixed.items():
            # The file is written by hand and carries prose for the next person
            # to read. A key starting with "_" is one of those notes, not a
            # member, and a note is a string rather than an object -- which
            # crashed this loop the first time one was added here.
            if _mid.startswith("_") or not isinstance(_fix, dict):
                continue
            _fields = {k: v for k, v in _fix.items() if not k.startswith("_")
                       and k in ("name", "party", "county", "district")}
            if _mid in former:
                former[_mid].update(_fields)
                hit += 1
            else:
                # Not a miss. The generators name a member by deduction and
                # cannot name everybody, so an id with no generated record is
                # the ordinary case for a correction that supplies a name
                # rather than replaces one. Whether it reaches a real ballot
                # is checked below, once the votes are built, which is the
                # only place that question can actually be answered.
                former[_mid] = dict(_fields)
                named += 1
        if hit:
            print(f"member_corrections.json: {hit} generated name(s) corrected")
        if named:
            print(f"member_corrections.json: {named} id(s) named that the "
                  f"generators could not name")
        _corrected_ids = {m for m in fixed if not m.startswith("_")}

    # ------------------------------------------ sponsors, district and all ---
    #
    # A sponsor the status page could not link is a member who has since left,
    # and the page gives their name and party and nothing else. Everyone still
    # sitting picks up their county and district from the roster downstream;
    # they cannot, so they were the only sponsors on the site drawn without a
    # district beside their name.
    #
    # former_members.json already holds it -- resolve_members.py looked these
    # people up to put names on their votes -- so it is joined here, in the one
    # file that reads it. They then render exactly like anybody else. They have
    # no member page, so their name is not a link, and that is the only
    # difference the site draws: some of these members died in office, and
    # their absence is not a fact to annotate.
    def _first_last(name):
        n = (name or "").strip()
        if "," in n:
            last, first = [x.strip() for x in n.split(",", 1)]
            n = f"{first} {last}"
        w = re.sub(r"[^A-Za-z ]", " ", n).lower().split()
        return (w[0], w[-1]) if len(w) >= 2 else None

    former_by_name = {}
    for _mid, _f in former.items():
        _k = _first_last(_f.get("name"))
        if _k:
            former_by_name[_k] = (_mid, _f)

    placed = 0
    for _sp in sponsors.values():
        for _s in _sp:
            if _s.get("district"):
                continue
            hit = former_by_name.get(_first_last(_s.get("name")))
            if not hit:
                continue
            _mid, _f = hit
            _s["member_id"] = _s.get("member_id") or _mid
            _s["party"] = _s.get("party") or (_f.get("party") or "")[:1].upper()
            _s["county"] = _f.get("county", "")
            _s["district"] = _f.get("district", "")
            placed += 1

    # ------------------------- the prime sponsor who is not on the roster ---
    #
    # HERE, AND NOT WHERE THE SPONSORS ARE READ, because up there nothing can
    # put a name to the id. 27 bills of the current term show the wrong author,
    # and the cause is not a missing flag -- it is a missing ROW. LsrSponsors
    # .txt flags the prime, legislators.txt does not hold them (they have left
    # office), so `legs.get(r[3])` comes back empty and the row is dropped
    # before the flag is ever read. LsrsOnly.txt lists the others and marks none
    # of them prime, so build_site_v2 falls back to sp_list[0] -- and since
    # those rows all carry sequence 1 and sort on (sequence, name), that is the
    # ALPHABETICALLY FIRST surviving sponsor.
    #
    # HB 1036 of 2026 is printed "Rep. Vose, Rock. 5; Rep. DeSimone, Rock. 18;
    # Rep. Kofalt...; Rep. Kuttab...; Rep. Lynn..." and the site credited
    # Rep. Debra DeSimone, who is simply first in the alphabet among those left.
    #
    # By this line `former` has been assembled, so the missing member can be
    # named. Where even that fails the row is still added, under the id alone:
    # naming nobody is a smaller error than naming the wrong person, and it is
    # visible rather than silent.
    lo_added = 0
    for _b, _mid in lo_flagged_prime.items():
        _rows = sponsors.get(_b)
        if not _rows or any(str(x.get("member_id")) == str(_mid) for x in _rows):
            continue
        _f = former.get(str(_mid)) or {}
        _name = _f.get("name") or f"Former member #{_mid}"
        for _x in _rows:
            _x["prime"] = False
            _x["sequence"] = 1
        _rows.append({
            "member_id": str(_mid), "name": _name,
            "party": (_f.get("party") or "")[:1].upper(),
            "chamber": _f.get("chamber", ""),
            "label": _name,
            "county": _f.get("county", ""), "district": _f.get("district", ""),
            "sequence": 0, "prime": True, "role": "Prime", "flag": "1",
        })
        _rows.sort(key=lambda x: (x["sequence"], x["name"]))
        lo_added += 1
    if lo_added:
        _named = sum(1 for b in lo_flagged_prime
                     for x in sponsors.get(b, [])
                     if x.get("prime") and not x["name"].startswith("Former member #"))
        print(f"  {lo_added} bill(s) had their prime sponsor restored from "
              f"LsrSponsors.txt, whom the roster does not hold; {_named} of "
              f"them could be named")
    if placed:
        print(f"sponsors given a district from former_members.json: {placed:,}")
        report.append(
            f"{placed:,} sponsor rows took their county and district from "
            "former_members.json, so that a member who has left is named the "
            "same way as one who is still sitting.")

    def _former_label(mid):
        # Members who left mid-term are shown exactly like everyone else. Some
        # died in office, and a colleague reading the record should not have
        # that flagged at them. The vote is the fact; the circumstances of
        # their leaving are not this site's business.
        #
        # THIS STRING IS AN INTERFACE, NOT A DISPLAY LABEL, and its shape is a
        # contract. "Shurtleff, Steve(D) Merrimack 15" never reaches a page --
        # build_site_v2.member_labels re-derives what a reader sees from the
        # bare name, so every voter on every page reads "Rep. Steve Shurtleff".
        # It looks like dead code and is not: build_site_v2.former_roster
        # parses the county and district back OUT of this string
        # (FORMER_LABEL there) to give a former member their seat, and it
        # reads the label rather than former_members.json precisely because
        # this is the only copy that has been through member_corrections.json
        # -- build_data applies those corrections to `former` above and never
        # writes that map out. Taking the seat from the file instead is what
        # published Steve Shurtleff at Grafton 9, the seat of the record his
        # correction replaced.
        #
        # So: the "Name(P) County NN" shape is depended on. Change it in both
        # places or in neither.
        f = former.get(mid)
        if not f:
            return f"Member #{mid}"
        pc = (f.get("party") or "")[:1].upper()
        return (f"{f['name']}({pc}) {f.get('county','')} "
                f"{f.get('district','')}").strip()

    # Keyed (year, body, number): a vote sequence number restarts each session,
    # so the year is what keeps 2025's roll call 112 apart from 2026's. That was
    # already true before past years were readable, which is why adding them
    # needed nothing here beyond the extra files.
    summary = {}
    for r in rows_all(sd, "RollCallSummary", archive=d, finished=gone_years, left=left_out):
        if len(r) < 13:
            continue
        summary[(r[0], r[1], r[2])] = {
            "year": r[0], "body": r[1], "number": r[2], "datetime": r[3],
            # The bill as data/bills.json keys it, so each ballot reaches its
            # bill's page: "SB 406" upper-cased and left spaced linked no
            # member's vote to SB 406. rollcall_parser.bill_number says which
            # seven. A field that names no bill is upper-cased as it was. A
            # roll call on a measure whose number another record of the term
            # holds goes under the name rollcall_parser.OTHER_MEASURE gives
            # it, so no member's ballot on 2009's SR 1 links 2010's.
            "bill": RP.roll_call_bill(r[0], r[1], r[2], r[4]) or r[4].upper(),
            "yea": int(r[5] or 0), "nay": int(r[6] or 0),
            "question": r[11], "title": r[12],
        }
    print(f"roll call summaries: {len(summary):,}")

    member_votes, vote_kinds, hist_bodies = [], Counter(), Counter()
    vnums, unmatched_votes, no_person = set(), 0, Counter()
    ballot_fixed = Counter()
    for r in rows_all(sd, "RollCallHistory", 8, archive=d, finished=gone_years, left=left_out):
        key = (r[0], r[1], r[2])
        hist_bodies[r[1]] += 1
        vnums.add(int(r[2]) if r[2].isdigit() else -1)
        s = summary.get(key)
        if not s:
            unmatched_votes += 1
            continue
        # Field 4 is the roster's PersonID, joined in on the Employeeno in
        # field 3. Three members of the 2023-2024 House have no legislators
        # row at all, so that join comes back empty for all 1,470 of their
        # votes -- and a blank id put the three of them under a single
        # "Member #" row, merging three people's votes into one. The
        # Employeeno is the only identifier the record holds for them, and
        # the two spaces do not overlap: PersonIDs run 48-10904, Employeenos
        # are six digits.
        mid = r[4].strip() or r[3].strip()
        if not mid and key in ballot_fix:
            # ONLY when the id is already empty. That makes the correction
            # self-limiting: if the General Court ever fills the id in, this
            # stops firing rather than adding a second ballot for the same
            # person in the same roll call, and the count below says so.
            mid = str(ballot_fix[key].get("member_id") or "").strip()
            ballot_fixed[key] += 1
        if not r[4].strip() and mid:
            no_person[mid] += 1
        m = legs.get(mid)
        vote_kinds[r[6]] += 1
        member_votes.append({
            # 420 members cast votes but only 406 are in legislators.txt: the
            # file holds current members, and people resign or die mid-term.
            # Their votes are still part of the record.
            "member_id": mid,
            "name": (m["name"] if m else
                     former.get(mid, {}).get("name", f"Member #{mid}")),
            "party": (m["party_code"] if m else
                      (former.get(mid, {}).get("party") or "X")[:1].upper()),
            "label": (m["label"] if m else _former_label(mid)),
            "year": r[0], "body": r[1], "vote_number": r[2],
            "bill": s["bill"], "question": s["question"],
            "date": s["datetime"].split(" ")[0],
            # An unmapped database code reached the site as a bare digit:
            # 411 ballots read "5" and 156 read "7". See
            # rollcall_parser.vote_word, which is the one place that
            # decides what a ballot is called. A declared conflict of
            # interest reads "No vote recorded" like an empty ballot and is
            # not one -- the member was in the room -- so rollcall_parser.
            # ballot flags it, on those few hundred rows only.
            **RP.ballot(r[6]),
        })
    print(f"member votes: {len(member_votes):,}")

    # A correction that reaches no ballot has stopped working -- the id space
    # changed under it, or the defect it answered was fixed upstream and the
    # entry outlived it. That question cannot be asked where the corrections
    # are applied, because the votes do not exist yet at that line; it can only
    # be asked here, against the ballots themselves.
    if _corrected_ids:
        _voting = {v["member_id"] for v in member_votes}
        _dead = sorted(_corrected_ids - _voting)
        if _dead:
            print(f"  WARNING: {len(_dead)} correction(s) in "
                  f"member_corrections.json match no ballot and may have "
                  f"outlived their defect: {', '.join(_dead[:8])}"
                  f"{' ...' if len(_dead) > 8 else ''}")

    if ballot_fix:
        _named = sum(ballot_fixed.values())
        print(f"  {_named} ballot(s) with an empty member id given the member "
              f"the journal names, from {len(ballot_fixed)} roll call(s)")
        # An id that casts this ONE ballot and no other is the signature of a
        # correction written in the wrong id space. The General Court numbers
        # people twice -- PersonID in field 4, Employeeno in field 3 -- and the
        # raw row shows both, so it is easy to copy the wrong one; doing that
        # does not fail, it silently mints a second person holding a single
        # vote while their real record sits beside it. That happened to both of
        # the first two entries and was caught by eye, which is not a method.
        _counts = Counter(v["member_id"] for v in member_votes)
        for _k, _v in ballot_fix.items():
            _id = str(_v.get("member_id") or "").strip()
            if ballot_fixed.get(_k) and _counts.get(_id, 0) <= ballot_fixed[_k]:
                print(f"  WARNING: ballot correction {'|'.join(_k)} names id "
                      f"{_id}, which casts no other ballot. Check it is the id "
                      f"data/member_votes.json uses (the PersonID where the "
                      f"record fills one) and not the Employeeno beside it.")

        _stale = sorted(k for k in ballot_fix if k not in ballot_fixed)
        if _stale:
            # Either the source filled the id in -- in which case the entry is
            # done and should be removed -- or the roll call moved and it is now
            # pointing at nothing. Both need a person; neither is silent.
            print(f"  WARNING: {len(_stale)} ballot correction(s) matched no "
                  f"empty-id ballot: {', '.join('|'.join(k) for k in _stale)}. "
                  f"Either the record now carries the id, or the roll call key "
                  f"has changed.")

    _dated = date_ballot_seats(member_votes, legs)
    if _dated:
        print(f"  {_dated:,} ballots relabelled with the seat that term's bills "
              f"printed, not the one the roster holds now")
    print(f"  vote values: {dict(vote_kinds)}")
    report.append(f"RollCallHistory field 2 ranges {min(vnums) if vnums else 0}"
                  f"\u2013{max(vnums) if vnums else 0}, and joins to RollCallSummary "
                  f"on (year, body, number). Chambers present: {dict(hist_bodies)}.")
    if unmatched_votes:
        report.append(f"{unmatched_votes:,} history rows had no matching summary row "
                      "(likely roll calls from a session the summary file no longer covers)")

    if no_person:
        report.append(
            f"{len(no_person)} member(s) voting in the 2023-2024 House have no "
            "row in the legislators table, so the record carries an Employeeno "
            "for them and no name, party or district: "
            + ", ".join(f"#{k} ({v:,} votes)" for k, v in sorted(no_person.items()))
            + ". They are kept apart by that number rather than merged.")
    former = {v["member_id"] for v in member_votes if v["party"] == "X"}
    if former:
        report.append(f"{len(former)} members cast votes but are not in the current "
                      "roster; names resolved from former_members.json. They are "
                      "displayed no differently from anyone else.")
    per_member = Counter(v["member_id"] for v in member_votes)
    if per_member:
        n = sorted(per_member.values())
        report.append(f"votes per member: median {n[len(n)//2]}, "
                      f"min {n[0]}, max {n[-1]}, members covered {len(per_member)}")

    if left_out:
        print(f"  rows of {', '.join(gone_terms)} left out of the session's files, the "
              "term being built from its freeze: "
              + ", ".join(f"{k} {v:,}" for k, v in sorted(left_out.items())))
    # ------------------------------------------------------------ write ---
    # A frozen term's run writes its own term's bills and sponsors and
    # nothing else (below): the roster and the ballots are the session's.
    if not frozen:
        (out / "legislators.json").write_text(
            json.dumps(sorted(legs.values(), key=lambda m: m["name"]), indent=2), encoding="utf-8")
        (out / "member_votes.json").write_text(json.dumps(member_votes), encoding="utf-8")
        (out / "towns.json").write_text(json.dumps(towns, indent=2), encoding="utf-8")
    # {term: {bill: record}}. A bill number is unique within a term and not
    # across terms, and this is the file every other per-bill lookup is driven
    # from -- the loop in build_site_v2.build_bills iterates it. Keyed on the
    # bill alone, adding an archived term would put two different bills under
    # one key at the very top of the pipeline.
    # The committee of referral for every archived bill, from the docket
    # already on this disk. No network: each archived term's own docket, the
    # file its history is narrated from (referrals.term_dockets). Empty if
    # those files are absent, in which case nothing below changes.
    #
    # Every archived term's docket, not only the database dump: the dump
    # stops part way through 2016, so 2016-2024 took the search page's LAST
    # committee in ONE chamber. referrals.from_dockets says what that cost.
    # Each bill's rows are chosen by the archive record's own LSR, because a
    # resolution's number can carry two measures in one term.
    ap_ = Path("archive_bills.json")
    try:
        arch = json.loads(ap_.read_text(encoding="utf-8")) if ap_.exists() else {}
    except ValueError:
        arch = {}
    try:
        import referrals
        refs, began = referrals.read_dockets(lsr_of={
            (t, b): r.get("lsr", "") for t, bb in arch.items()
            for b, r in bb.items()})
    except Exception as e:                       # a missing docket is not a failure
        print(f"  archive: no docket referrals ({e})")
        refs, began = {}, {}
    # The names the clerks were using, per term and chamber: any the docket
    # gives as the first referral of three or more bills. _same_committee
    # says why a longer stored name must not replace one of these.
    _used = Counter((t, body, referrals._key(c)) for (t, _b), bodies in refs.items()
                    for body, c in bodies.items())
    in_use = defaultdict(set)
    for (t, body, k), n in _used.items():
        if n >= 3:
            in_use[(t, body)].add(k)
    # The committee names the tables know, reduced the way referrals._key
    # reduces them so that "Ways & Means" and "Ways and Means" are one name.
    # _pick_committee says what this is for.
    try:
        known = {referrals._key(c["name"]) for c in committees.values()
                 if c.get("name")}
    except Exception:
        known = set()
    by_term = defaultdict(dict)
    for bid, rec in bills.items():
        by_term[P.term_of(str(rec.get("lsr_year") or ""))][bid] = rec

    # Archived terms, from fetch_archive_bills.py. The General Court's own
    # search answers a past session year with every bill of it -- title,
    # statuses, committee, hearing, text link -- for two requests, which is
    # where the 2023-2024 term comes from. It has no docket and no sponsors,
    # and this does not pretend otherwise: those fields are simply absent, and
    # the page says so rather than showing the CURRENT term's.
    #
    # A term the current session files already cover is left alone. The live
    # data is better than a search-results page in every respect.
    # (archive_bills.json was read above, for the referrals.)
    if ap_.exists():
        added = 0
        for term, byb in arch.items():
            if term in by_term:
                print(f"  archive: {term} is already built from session files, "
                      "left alone")
                continue
            for bid, r in byb.items():
                num = re.match(r"([A-Z]+)(\d+)", bid)
                cm, ch = r.get("committee") or "", r.get("committee_chamber")
                if _placeholder(cm):
                    # NOT A COMMITTEE OF REFERRAL, and treated as absent so
                    # the docket's own answer below is used instead. See
                    # _placeholder for what these are and why they are here.
                    cm = ""
                # The search page gave a committee for 1999 onward and none at
                # all before it, so five terms and 8,525 bills had no committee
                # of any kind. The docket has it: the clerk writes the referral
                # into the description of the introduction line.
                # referrals.from_dockets reads it for every archived term,
                # 1989-2024, from the docket each term's history is narrated
                # from, and _pick_committee lets it win -- except where the two
                # are one committee under two spellings -- because the search
                # page's value is the LAST committee in one chamber, and the
                # docket's is the FIRST in each, or the committee a vacate
                # moved the bill to.
                ref = refs.get((term, bid), {})
                by_term[term][bid] = {
                    "bill": bid,
                    "lsr": f"{r.get('year','')}-{r.get('lsr','')}",
                    "lsr_year": r.get("year", ""), "lsr_num": r.get("lsr", ""),
                    "title": r.get("title", ""),
                    # A CACR's number does not say which chamber it began
                    # in, and the search page files every one under the
                    # House; its own docket's first row says.
                    "chamber": ((began.get((term, bid)) if bid.startswith("CACR")
                                 else "") or r.get("body", "")),
                    "subject_code": "", "subject": "",
                    "house_committee": _pick_committee(
                        cm if ch == "House" else "", ref.get("H", ""), known,
                        in_use.get((term, "H"), ())),
                    "senate_committee": _pick_committee(
                        cm if ch == "Senate" else "", ref.get("S", ""), known,
                        in_use.get((term, "S"), ())),
                    "hearing": hearing_in_term(r.get("last_hearing", ""),
                                               term),
                    "hearing_room": "",
                    "designation": (f"{num.group(1)} {num.group(2)}"
                                    if num else bid),
                    "text_pdf": r.get("text_pdf", ""),
                    # The statuses travel with the bill because an archived
                    # term has no bill_status.json of its own, and the flat one
                    # belongs to a different term.
                    "gen_status": r.get("gen_status", ""),
                    "house_status": r.get("house_status", ""),
                    "senate_status": r.get("senate_status", ""),
                    "archived": True,
                }
                added += 1
        if added:
            print(f"  archive: {added:,} bills added from {ap_}")
        if refs:
            filled = sum(1 for bs in by_term.values() for b in bs.values()
                         if b.get("archived")
                         and (b.get("house_committee") or b.get("senate_committee")))
            print(f"  archive: {filled:,} archived bills carry a committee "
                  f"({len(refs):,} referrals read from the docket)")
    stray = by_term.pop("", None)
    if stray:
        print(f"  {len(stray):,} bills have no filing year and are left out of "
              f"bills.json: {sorted(stray)[:5]}")
    # The term the session's own files describe, known here because nothing
    # below may add to it or change it but the House's own withdrawn bills.
    _session_term = max(by_term) if by_term else ""
    # The measures the General Court's database holds and the search page left
    # out: AFTER every term is in by_term, so one can never stand in for a
    # term, and BEFORE the journal's, so a record the General Court's own
    # table gives is never the journal's instead. add_past_bills says what a
    # row must be to become one.
    past = past_legislation(d)
    if past is None:
        print("=" * 70)
        print(f"NO {d / PAST_LEGISLATION}. The measures the General Court's search")
        print("page left out of a past term are in its database and nowhere else")
        print("this reads, and the fiscal-note, appropriation and local flags of")
        print("every archived designation come from the same table: without it")
        print("those bills are not on the site and the designations are bare.")
        print("fetch_past_db.py dumps it, at a person's word.")
        print("=" * 70)
        past_added = {}
    else:
        _general, _body = status_words(d)
        past_added = add_past_bills(by_term, past, committees, refs, _general, _body,
                                    _session_term, known, in_use)
    # The House Journal's word on the bills of the terms' own lists that its
    # resolutions decide: with the database's dump here or without it, because
    # these records are the search page's and the journals are their evidence.
    journal_introductions(by_term, _session_term)
    # And the one the docket holds with no title in any table, titled from
    # the bound House Journal (TITLED_FROM_JOURNAL).
    add_journal_titled(by_term, began, current=_session_term)
    # The House's withdrawn bills, from its journals: HERE, once every term is
    # in by_term and before the committee names are settled below, so that
    # one of these can never stand in for a term nor over a bill the General
    # Court's files carry. add_journal_bills says why each.
    journal_added = add_journal_bills(by_term, d / JOURNAL_BILLS, skip=gone_terms)
    # The flags on the archive's designations, last of the records' own
    # fields, so the ones just added take theirs too.
    if past:
        _flagged = past_flags(by_term, past, _session_term)
        if _flagged:
            print(f"  designations: {sum(_flagged.values()):,} archived bills given the "
                  "fiscal-note, appropriation and local flags the General Court's "
                  "database carries ("
                  + ", ".join(f"{k} {v:,}" for k, v in _flagged.most_common()) + ")")
        # What was held back, said: the bills whose own saved page prints
        # another designation keep the bare number, for a person to decide.
        if PAST_FLAGS_REFUSED:
            print(f"  designations: {len(PAST_FLAGS_REFUSED):,} left bare, because the "
                  "bill's own saved page prints another designation than the "
                  "database's flags make (" + ", ".join(
                      f"{b} {t}: database {s_}, page {'/'.join(x or 'none' for x in f_)}"
                      for t, b, s_, f_ in PAST_FLAGS_REFUSED[:6])
                  + (", ..." if len(PAST_FLAGS_REFUSED) > 6 else "") + ")")
        elif _flagged and not PAGES.is_dir():
            print(f"  designations: NO {PAGES}/ HERE, so no flag was held to the "
                  "designation a bill's own page prints (133 differed on 1 October 2026)")
    # One name per committee, the one it had at the time: see
    # _official_committees. Said out loud, because a table that stopped
    # matching would otherwise just quietly put the extra spellings back.
    moved = _official_committees(by_term)
    if moved:
        print(f"  committee names: {sum(moved.values()):,} bill-chamber "
              f"labels under {len(moved)} spellings written as the "
              "committee's name at the time")
    # The newest term the pipeline holds, which is the one the current
    # session's own files describe.
    current_term = max(by_term) if by_term else ""
    # THE FINISHED TERMS, FROM THEIR OWN BUILDS (5 October 2026): each frozen
    # term older than the session's, as build_frozen_terms built it from its
    # freeze a step before this run, whole, in place of anything the
    # session's files still say of it. Last, so that nothing above -- the
    # archive, the past views, the journals, the committee names -- touches
    # a term that was built entire, as the session once built it.
    finished = {} if frozen else finished_builds(d, out)
    for _t, (_fb, _fs) in finished.items():
        _was = len(by_term.get(_t) or {})
        by_term[_t] = _fb
        print(f"  {_t}: {len(_fb):,} bills from its frozen inputs"
              + (f", in place of {_was:,} the session's files still gave it" if _was else ""))
    if finished:
        # The session's term first, then the finished ones newest first, then
        # the archive as it was: the order the file had while the session's
        # term was the newest.
        _order = ([current_term] + sorted(finished, reverse=True)
                  + [t for t in by_term if t != current_term and t not in finished])
        by_term = defaultdict(dict, {t: by_term[t] for t in _order if t in by_term})
    # {term: {bill: [sponsor]}}, for the reason bills.json is: HB100 of 2023
    # and HB100 of 2025 have different sponsors, and a flat file gives the
    # second to the first without saying so.
    #
    # `sponsors` is keyed on the bill number and holds the CURRENT session:
    # LsrSponsors.txt and LsrsOnly.txt cover it and nothing else, and the
    # status-page fallback above reads the same term out of bill_status.json.
    # So the term is known, and is not looked up.
    #
    # It must not be looked up. A bill -> term map built from by_term files
    # every repeated number under whichever term the loop reached last, which
    # is the exact confusion this file is being keyed on the term to prevent --
    # it put 1,849 of 2,220 bills' sponsors under 2023-2024 on the first
    # attempt, having read them out of the 2025-2026 files.
    #
    # An archived term's sponsors come from that term's slice of
    # bill_status.json, which is not fetched yet; they go in here when it is.
    sp_by_term = {current_term: sponsors} if sponsors else {}
    # An archived term's sponsors come from ITS slice of bill_status.json, not
    # from the LSR files, which cover the current session only. Until
    # bill_status.json was keyed on the term there was nowhere to put them, so
    # every archived bill showed no sponsors at all and a search for a prime
    # sponsor found nothing before 2025.
    if bsp.exists() and P.term_keyed(raw):
        for _t, _byb in raw.items():
            if _t == current_term or _t in gone_terms:
                continue
            _rows = {bid: status_sponsors(v) for bid, v in _byb.items()
                     if v.get("sponsors")}
            if _rows:
                sp_by_term.setdefault(_t, {}).update(_rows)
                print(f"  sponsors.json {_t}: {len(_rows):,} from the status "
                      "pages")
    # The withdrawn bills' sponsors, as the House Journal printed them, and
    # only where the bill has none from another source.
    if journal_added:
        import text_sponsors as TS
        _sat = TS.Sat(member_votes)
        _jn = _jr = _jt = 0
        for _t, _byb in journal_added.items():
            _slice = sp_by_term.setdefault(_t, {})
            for _b, _rec in _byb.items():
                if _slice.get(_b):
                    continue
                _rows = journal_sponsor_rows(
                    (_rec.get("journal") or {}).get("sponsors"), _t, _sat, legs,
                    current_term)
                if _rows:
                    _slice[_b] = _rows
                    _jn += 1
                    _jt += len(_rows)
                    _jr += sum(1 for r in _rows if r.get("member_id"))
        print(f"  sponsors.json: {_jn} bill(s) took their sponsors from "
              f"the House Journal, {_jr} of {_jt} names placed on a member")
    # A finished term's sponsors are its own build's, every list as it was.
    for _t, (_fb, _fs) in finished.items():
        sp_by_term[_t] = _fs
    if finished:
        sp_by_term = {t: sp_by_term[t] for t in
                      [current_term] + sorted(finished, reverse=True)
                      + [t for t in sp_by_term if t != current_term and t not in finished]
                      if t in sp_by_term}
    if frozen:
        # THE FROZEN TERM'S RUN WRITES ITS TERM AND NOTHING ELSE, with what it
        # was built from, which the session's run checks before it takes it.
        (out / "bills.json").write_text(
            json.dumps({frozen: by_term.get(frozen) or {}}, indent=2), encoding="utf-8")
        (out / "sponsors.json").write_text(
            json.dumps({frozen: sp_by_term.get(frozen) or {}}, indent=2), encoding="utf-8")
        (out / "frozen.json").write_text(json.dumps(
            {"term": frozen, "built_from": frozen_record(d, frozen),
             "bills": len(by_term.get(frozen) or {}),
             "sponsors": len(sp_by_term.get(frozen) or {})}, indent=1), encoding="utf-8")
        print(f"\n{frozen} built from its frozen inputs: {len(by_term.get(frozen) or {}):,} "
              f"bills, {len(sp_by_term.get(frozen) or {}):,} with sponsors -> {out}/")
        return 0
    (out / "bills.json").write_text(
        json.dumps(dict(by_term), indent=2), encoding="utf-8")
    for t in sorted(by_term):
        print(f"  bills.json {t}: {len(by_term[t]):,}")
    (out / "sponsors.json").write_text(
        json.dumps(sp_by_term, indent=2), encoding="utf-8")
    for t in sorted(sp_by_term):
        print(f"  sponsors.json {t}: {len(sp_by_term[t]):,}")
    (out / "subjects.json").write_text(json.dumps(subjects, indent=2), encoding="utf-8")
    (out / "committees.json").write_text(json.dumps(committees, indent=2), encoding="utf-8")

    print(f"\nwritten to {out}/")
    print("\n" + "=" * 70)
    print("THINGS TO CHECK")
    print("=" * 70)
    for r in report:
        # The Windows console is cp1252, so bullets and dashes arrive as noise.
        # Console output is ASCII; the JSON keeps the real characters.
        print("  - " + r.replace("\u2014", "--").replace("\u2013", "-")
                        .replace("\u2019", "'").replace("\u201c", '"')
                        .replace("\u201d", '"'))

    # A concrete spot check beats any amount of schema inference.
    sample = next((b for b in sponsors if sponsors[b]), None)
    if sample:
        print(f"\nSpot check \u2014 {sample}: {bills[sample]['title'][:64]}")
        print(f"  subject: {bills[sample]['subject'] or '(none)'}")
        print(f"  House committee: {bills[sample]['house_committee'] or '(none)'}")
        for s in sponsors[sample][:6]:
            src = s.get("role") or f"flag={s.get('flag', '-')}"
            print(f"  {'PRIME' if s.get('prime') else '     '} {s['label']}  {src}")
        print("\n  Confirm the PRIME line matches the prime sponsor on gencourt.")


if __name__ == "__main__":
    sys.exit(main())
