#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.29
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


def rows_all(d, base, expect=None):
    """base.txt plus every rollcalls/base_<year>.txt beside it.

    The General Court publishes one bulk file per CURRENT session, so the
    download alone holds no roll call older than this year. fetch_rollcalls_db
    writes a file per past year in the same shape, from the database, and both
    are read together here -- teaching this reader a second format would have
    been the larger change, and it would have let the two disagree about what
    a column means.

    The download is read first, so a year present in both keeps the copy the
    General Court publishes directly.
    """
    out = rows(d / f"{base}.txt", expect)
    extra = d / "rollcalls"
    if extra.is_dir():
        for f in sorted(extra.glob(f"{base}_*.txt")):
            got = rows(f, expect)
            print(f"  {f.name}: {len(got):,} rows")
            out += got
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


def _pick_committee(stored, first, known):
    """The committee of referral, choosing between two sources that disagree.

    `stored` is the General Court search page's "Next/Last Comm" -- the LAST
    committee the bill was with. `first` is the first referral, read out of
    the docket by referrals.py. The person settled in September 2026 that the
    site names the FIRST: a later referral to Finance is a money pass rather
    than a change of subject-matter ownership, and a bill that goes to Health
    and Human Services and then to Finance belongs to Health and Human
    Services. 527 bills of 1999-2016 stored a money committee for exactly that
    reason, and 586 more stored something that is not a committee at all.

    So the docket wins -- with one exception, which is the reason this is a
    function rather than an `or`.

    THE EXCEPTION: the same committee under an older name. The clerk of 1999
    wrote "Public Works" for what the committee tables call "Public Works and
    Highways", and about 170 bills differ only in that way. Preferring the
    docket there would trade a right committee for an unlinkable one: the site
    renders a committee the tables do not know as plain text rather than as a
    link, so the reader would lose the route to the committee's page and gain
    nothing. Where the docket's name is one no table knows and the stored name
    is, the two are taken to be the same committee and the linkable spelling
    wins.

    That test is deliberately about LINKABILITY and not about similarity. Two
    genuinely different committees -- Finance against Education -- are both
    known, so the exception does not fire and the docket wins, which is the
    whole point of the change.
    """
    if not first:
        return stored
    if not stored:
        return first
    import referrals as _r
    if _r._key(stored) == _r._key(first):
        return stored
    if known and _r._key(first) not in known and _r._key(stored) in known:
        return stored
    return first


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    d, out = Path(a.dir), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = []

    # ---------------------------------------------------------- counties ---
    counties = {}
    for r in rows(d / "Counties.txt", 3):
        counties[r[0]] = {"name": r[1], "abbr": r[2].rstrip(".")}
    print(f"counties: {len(counties)}")

    # ------------------------------------------------------- legislators ---
    legs = {}
    bad_party = Counter()
    for r in rows(d / "legislators.txt", 15):
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
    mp = d / "Members.txt"
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

    for r in ([] if dj else rows(d / "HouseDistricts.txt", 4)):
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
                for r in rows(d / "SubjectCodes.txt", 3)}
    committees = {r[0]: {"code": r[0], "name": r[1], "abbr": r[2]}
                  for r in rows(d / "Committees.txt", 3)}
    print(f"subjects: {len(subjects)}   committees: {len(committees)}")

    # ------------------------------------------------------------ bills ---
    bills, by_lsr = {}, {}
    for r in rows(d / "LSRs.txt"):
        if len(r) < 33:
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
    dp = d / "Docket.txt"
    if dp.exists():
        with open(dp, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                f = line.split("|")
                if len(f) > 5 and f[3].strip():
                    b = f[3].strip().upper()
                    docket_bills.setdefault(b, (f[0].strip(), f[1].strip()))
    # Roll call rows carry a title, which is better than nothing for a stub.
    rp = d / "RollCallSummary.txt"
    if rp.exists():
        with open(rp, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                f = line.split("|")
                if len(f) > 12 and f[4].strip() and f[12].strip():
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
    lp = d / "db" / "Legislation.psv"
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
    lo = d / "LsrsOnly.txt"
    lo_rows = [r for r in rows(lo, 8)] if lo.exists() else []
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
    for r in rows(d / "LsrSponsors.txt", 5):
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
        # Keyed on the term. `bills` here is the current session's, so it is
        # the newest term that belongs on it; a file still in the flat shape
        # is that term already.
        raw = json.loads(bsp.read_text(encoding="utf-8"))
        st = P.for_term(raw) if P.term_keyed(raw) else raw
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
    # Twenty-four years of roll calls came off the database dump on 10
    # September, and 783,919 of their ballots were cast by somebody this site
    # could not name -- "Member #330274" -- because the roster views reach
    # 1,081 people and former_members.json 676. past_members.json holds 2,614,
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
    # were named and partyless. A person found the page that has it: the
    # legacy roll call detail prints every member's party, county and district
    # beside their vote, and fetch_rollcall_parties.py took the fullest vote
    # of each year and chamber -- 54 requests for 2,078 members.
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
    for r in rows_all(d, "RollCallSummary"):
        if len(r) < 13:
            continue
        summary[(r[0], r[1], r[2])] = {
            "year": r[0], "body": r[1], "number": r[2], "datetime": r[3],
            "bill": r[4].upper(), "yea": int(r[5] or 0), "nay": int(r[6] or 0),
            "question": r[11], "title": r[12],
        }
    print(f"roll call summaries: {len(summary):,}")

    member_votes, vote_kinds, hist_bodies = [], Counter(), Counter()
    vnums, unmatched_votes, no_person = set(), 0, Counter()
    ballot_fixed = Counter()
    for r in rows_all(d, "RollCallHistory", 8):
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
            # decides what a ballot is called.
            "vote": RP.vote_word(r[6]),
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

    # ------------------------------------------------------------ write ---
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
    # already on this disk. No network: db/Docket.psv is the General Court's
    # own database dump and covers 1989-2015. Empty if that file is absent,
    # in which case nothing below changes.
    try:
        import referrals
        refs = referrals.from_docket()
    except Exception as e:                       # a missing dump is not a failure
        print(f"  archive: no docket referrals ({e})")
        refs = {}
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
    ap_ = Path("archive_bills.json")
    if ap_.exists():
        try:
            arch = json.loads(ap_.read_text(encoding="utf-8"))
        except ValueError:
            arch = {}
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
                # into the description of the introduction line, and the
                # database's own docket goes back to 1989. referrals.py reads
                # it; this fills only what is empty, because the search page's
                # value is the LAST committee and the docket's is the FIRST,
                # and a term holding some of each would be two facts under one
                # label.
                ref = refs.get((str(r.get("year", "")), bid), {})
                by_term[term][bid] = {
                    "bill": bid,
                    "lsr": f"{r.get('year','')}-{r.get('lsr','')}",
                    "lsr_year": r.get("year", ""), "lsr_num": r.get("lsr", ""),
                    "title": r.get("title", ""),
                    "chamber": r.get("body", ""),
                    "subject_code": "", "subject": "",
                    "house_committee": _pick_committee(
                        cm if ch == "House" else "", ref.get("H", ""), known),
                    "senate_committee": _pick_committee(
                        cm if ch == "Senate" else "", ref.get("S", ""), known),
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
    # The newest term the pipeline holds, which is the one the current
    # session's own files describe.
    current_term = max(by_term) if by_term else ""
    (out / "bills.json").write_text(
        json.dumps(dict(by_term), indent=2), encoding="utf-8")
    for t in sorted(by_term):
        print(f"  bills.json {t}: {len(by_term[t]):,}")
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
            if _t == current_term:
                continue
            _rows = {bid: status_sponsors(v) for bid, v in _byb.items()
                     if v.get("sponsors")}
            if _rows:
                sp_by_term.setdefault(_t, {}).update(_rows)
                print(f"  sponsors.json {_t}: {len(_rows):,} from the status "
                      "pages")
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
    main()
