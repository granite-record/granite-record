#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.27
"""
A page's worth of data for every committee.

    python3 build_committees.py --site site --data data

WHAT A COMMITTEE PAGE ANSWERS

Bill-first search answers "what happened to HB 1442". This answers "what did
Legislative Administration do on 3 March", which is the question a reporter or
a member of that committee actually asks, and the site could not answer it at
all.

WHERE EACH PART COMES FROM

  identity, leadership, room   committees.json          fetch_committees.py
  who sits on it               data/committee_members.json
                                                        fetch_committee_members_db.py
  bills referred               site/index.json          the search index
  what happened on a day       proceedings.csv          one row per
                                                        (bill, date, kind, recording)
  what the committee decided   committee_reports.json, senate_reports.json

The web pages give the chair and the room and not the House rosters; the
database gives both chambers' rosters and no leadership. Neither alone is a
committee page.

THE DAY NARRATIVE

Composed from proceedings.csv rather than written, in the same spirit as the
bill narratives: every clause is a row somebody can check. A day reads

    The Committee on Education met on January 28, 2026 for public hearings on
    HB1123, HB319 and HB722. It also held an executive session on HB1142, and
    recommended that the House find it inexpedient to legislate, 12-2.

and the recommendation half only appears when committee_reports.json has one
for that bill. A committee that met and whose report is not on file gets the
first sentence and nothing more, which is the honest outcome.

Writes site/committees.json and site/committee/<code>.json. It writes no HTML:
the page is app.js with one committee open, the same way a bill's page is.
"""

import argparse
import collections
import json
import re
from pathlib import Path

import proceedings as P
import bill_order as BO
import names
import shell as S
import structured as LD
import site_read as SR

# The kinds proceedings.csv records, in the order a committee day runs, with
# the plural the narrative needs.
KIND_ORDER = ["public hearing", "hearing", "executive session",
              "full committee work session", "subcommittee work session",
              "work session", "committee of conference"]
PLURAL = {
    "public hearing": "public hearings",
    "hearing": "hearings",
    "executive session": "executive sessions",
    "full committee work session": "full committee work sessions",
    "subcommittee work session": "subcommittee work sessions",
    "work session": "work sessions",
    "committee of conference": "committees of conference",
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def fdate(d):
    if not d or len(d) < 10:
        return d or ""
    try:
        return f"{MONTHS[int(d[5:7]) - 1]} {int(d[8:10])}, {d[:4]}"
    except (ValueError, IndexError):
        return d


def plain_name(nm):
    """"Thomas, Douglas" as "Douglas Thomas", which is how a committee page
    names its chair. The roster files a person surname-first; the committee
    pages do not, and the two are matched on this."""
    a = (nm or "").split(",")
    return f"{a[1].strip()} {a[0].strip()}" if len(a) > 1 else (nm or "")


def andlist(xs):
    xs = list(xs)
    if not xs:
        return ""
    if len(xs) == 1:
        return xs[0]
    return ", ".join(xs[:-1]) + " and " + xs[-1]


def spaced(bill):
    """HB1123 as "HB 1123", the way the site writes a bill number."""
    m = re.match(r"^([A-Z]+)\s*(\d+.*)$", (bill or "").upper())
    return f"{m.group(1)} {m.group(2)}" if m else (bill or "")


def recommendation(reports, term, bill, committee=""):
    """What THIS committee recommended, and the vote, if it is on file.

    The committee name is not optional. A bill is reported by a House
    committee and then, if it passes, by a Senate one; several bills are also
    re-referred and reported twice by different committees of the same
    chamber. Taking the first report on file gave a committee another
    committee's recommendation -- 8 executive sessions of the current term,
    including one where a House committee was credited with a decision made
    across the building.

    Where no report on file is this committee's, nothing is said. A sitting
    day with a hearing and no attributable report is the ordinary case, and
    silence is the honest form of it.
    """
    want = (committee or "").strip().lower()
    for rec in (reports.get(term, {}) or {}).get(bill, []) or []:
        maj = (rec.get("majority_recommendation") or "").strip()
        if not maj:
            continue
        if want:
            said = [(r.get("committee") or "").strip().lower()
                    for r in rec.get("reports") or []]
            if said and want not in said:
                continue
        vote = ""
        for r in rec.get("reports") or []:
            if (r.get("side") or "").lower().startswith(("majority", "committee")):
                y, n = r.get("vote_yeas"), r.get("vote_nays")
                if y is not None and n is not None:
                    vote = f"{y}–{n}"
                break
        return maj.lower(), (rec.get("minority_recommendation") or "").strip().lower(), vote
    return "", "", ""


def narrate(name, chamber, date, items, reports):
    """One committee day, in sentences, from the rows themselves."""
    by_kind = collections.defaultdict(list)
    for it in items:
        by_kind[it["kind"]].append(it)
    kinds = [k for k in KIND_ORDER if k in by_kind] + \
            [k for k in by_kind if k not in KIND_ORDER]
    if not kinds:
        return ""

    who = f"The Committee on {name}" if not name.lower().startswith("committee") \
        else name
    out = []
    first = kinds[0]
    bills = andlist(spaced(i["n"] or i["bill"]) for i in by_kind[first])
    many = len(by_kind[first]) > 1
    noun = PLURAL[first] if many and first in PLURAL else first
    # "met on April 30, 2026 for public hearing on SB 624-FN" -- the singular
    # needs its article. 248 sitting days of the current term read that way,
    # which is the site speaking in its own voice and getting it wrong.
    art = "" if many else ("an " if noun[:1] in "aeiou" else "a ")
    # A day still to come is scheduled, not met. The docket carries sittings
    # ahead of time -- a committee's executive session booked for the end of
    # the month -- and the page said the committee "met" on a day seventeen
    # days off.
    ahead = str(date)[:10] > __import__("datetime").date.today().isoformat()
    met, held = (("is scheduled to meet", "It is also scheduled to hold") if ahead
                 else ("met", "It also held"))
    out.append(f"{who} {met} on {fdate(date)} for {art}{noun} on {bills}.")

    for k in kinds[1:]:
        bs = andlist(spaced(i["n"] or i["bill"]) for i in by_kind[k])
        noun = PLURAL[k] if len(by_kind[k]) > 1 and k in PLURAL else k
        out.append(f"{held} {'an' if noun[0] in 'aeiou' else 'a'} "
                   f"{noun} on {bs}." if len(by_kind[k]) == 1
                   else f"{held} {noun} on {bs}.")

    # What it decided, where a report says so. Only executive sessions produce
    # a recommendation, and only some of those have a report on file yet.
    #
    # NOT FOR A SITTING THAT HAS NOT HAPPENED. `ahead` was worked out above and
    # used only to choose the verb, so a committee page read "is scheduled to
    # meet on September 30, 2026 ... On HB 1292-FN it recommended refer for
    # interim study, 17-1" -- a tally under a meeting seventeen days off.
    #
    # The vote itself is real and stays where it belongs. A bill voted on in
    # one executive session can have a SECOND booked months later -- for the
    # interim study the report itself asks for -- and committee_reports.json
    # carries no date, so recommendation() cannot tell the two sittings apart
    # and attached the first vote to both. Suppressing it on the future one
    # leaves it on the page of the meeting it was taken at.
    #
    # 23 recommendations across 4 committee pages were being narrated this way.
    said = []
    for it in ([] if ahead else by_kind.get("executive session", [])):
        maj, minor, vote = recommendation(reports, it["term"], it["bill"], name)
        if not maj:
            continue
        body = "House" if chamber == "H" else "Senate"
        bit = (f"On {spaced(it['n'] or it['bill'])} it recommended that the "
               f"{body} find it {maj}" if maj.startswith("inexpedient")
               else f"On {spaced(it['n'] or it['bill'])} it recommended "
                    f"{maj}")
        if vote:
            bit += f", {vote}"
        if minor and minor != maj:
            bit += f", with a minority recommending {minor}"
        said.append(bit + ".")
    out += said
    return " ".join(out)


# A committee of conference is named for one bill whenever the chambers
# disagree, every session. It is on no list of standing committees and it has
# not gone anywhere, so it is never filed as archived.
NEVER_ARCHIVED = {"committee of conference"}


def years(span):
    """["1989-1990", ..., "2023-2024"] -> "1989 to 2024"."""
    first, last = span[0][:4], span[-1][-4:]
    return first if first == last else f"{first} to {last}"


def listing_groups(index, listed, current_term):
    """The committees page's three lists, from what the record can say.

    ARCHIVED IS TWO FACTS, NOT A GUESS. A committee goes to the bottom of the
    page when the General Court's own list of committees today does not
    include it AND everything this record holds for it -- bills referred,
    sitting days -- ends before the term now sitting. That is H05 Education,
    1,530 bills from 1989 to 2024, and the special committees of a term.
    "Disbanded" is not claimed: the records show when a committee stops
    appearing, not whether it was renamed, divided, merged or ended.

    Not on the list is not enough alone. The roster table holds special
    committees -- Commissions, the Family Division, DCYF -- that are on no
    list and have no record at all, and whose members are mostly sitting
    legislators; its "sitting" flag is about the legislator, not the seat, so
    nothing here can say those have ended. They go with the other committees
    that have no record, under a heading that makes no claim either way.

    `index` rows carry "span", the sorted terms of their bills and sitting
    days; `listed` is the codes the General Court's page names. Returns
    (live, idle, archived).
    """
    live, idle, archived = [], [], []
    for c in index:
        span = c.get("span") or []
        if not span:
            idle.append(c)
        elif (c["code"] in listed or c["name"].strip().lower() in NEVER_ARCHIVED
              or span[-1] >= current_term):
            live.append(c)
        else:
            archived.append(c)
    return live, idle, archived


def feed_link(code, name):
    """The head's link to a committee's feed, written once so it can be taken out
    again exactly as it was put in."""
    return (f'<link rel="alternate" type="application/rss+xml" '
            f'title="{S.E(name)} committee updates" href="/feed/committee/{S.E(code)}.xml">')


def bills_in_order(by_term):
    """A committee's referred bills, per term, by number as bills.html lists
    them. Sorted on the id's text this put HB1003 before HB101 on the page:
    the Bills tab shows this file's order and has no sort control."""
    return {t: sorted(v, key=lambda b: BO.bill_key(b["id"]))
            for t, v in by_term.items()}


def load(p, default):
    f = Path(p)
    if not f.exists():
        return default
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return default


# County code to the abbreviation a district is written with. Taken from the
# roster rather than repeated here, so it cannot drift from it.
CABBR = {}


def load_county_abbr(legislators):
    for r in (legislators.values() if isinstance(legislators, dict)
              else legislators):
        if isinstance(r, dict) and r.get("county_code") and r.get("county_abbr"):
            CABBR.setdefault(str(r["county_code"]).zfill(2), r["county_abbr"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--data", default="data")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site, data = Path(a.site), Path(a.data)

    idx = load(site / "index.json", [])
    if not idx:
        raise SystemExit(f"{site}/index.json is not there. Run build_site_v2 "
                         "first -- the bills a committee heard come from it.")
    web = load("committees.json", {})
    seats = load(data / "committee_members.json", {})
    codes = load(data / "committees.json", {})
    # Both files, CONCATENATED per bill rather than one shadowing the other.
    # setdefault kept only the first: a bill reported by a House committee and
    # then by a Senate one -- which is most bills that pass a chamber -- lost
    # the Senate's report entirely, so a Senate committee narrating its own
    # executive session had nothing of its own to quote and quoted the House's.
    reports = {}
    for src in (load("committee_reports.json", {}), load("senate_reports.json", {})):
        for t, byb in src.items():
            for b, v in byb.items():
                reports.setdefault(t, {}).setdefault(b, []).extend(
                    v if isinstance(v, list) else [v])
    legs = {str(m.get("id")): m for m in load(site / "legislators.json", [])}
    load_county_abbr(legs)

    # (chamber, name) -> code. NOT name alone: both chambers have a
    # Judiciary, a Finance and a Ways and Means, so a name-only map silently
    # gave one chamber's committee the other's roster and sitting days -- the
    # same confusion as a bill number across two terms, in a different file.
    #
    # The code carries the chamber: H05 is a House committee, S30 a Senate
    # one, and that is the only place the chamber is stated for a House
    # committee, whose page does not say.
    by_name = {}
    for code, rec in codes.items():
        nm = (rec.get("name") or "").strip().lower()
        ch = code[:1].upper() if code else ""
        if nm and ch in ("H", "S"):
            by_name[(ch, nm)] = code

    def code_of(name, chamber):
        """The committee a name means, in the chamber that named it."""
        nm = (name or "").strip().lower()
        ch = (chamber or "").strip().upper()[:1]
        if not nm:
            return None
        # The search index writes "Senate Judiciary" and "House Finance";
        # proceedings.csv writes the bare name and carries the chamber in its
        # own column. Both forms end up here.
        for pre, c in (("house ", "H"), ("senate ", "S")):
            if nm.startswith(pre):
                nm, ch = nm[len(pre):], c
                break
        return by_name.get((ch, nm))
    # The web file carries the chamber and the leadership.
    lead = {}
    for chamber, rows in (web.items() if isinstance(web, dict) else []):
        for c in rows:
            code = code_of(c.get("name"), chamber)
            if code:
                lead[code] = {**c, "chamber": chamber}

    # ---- who is on each committee TODAY ------------------------------------
    # THE SEAT TABLE IS EVERY SEAT EVER HELD, NOT TODAY'S ROSTER. The
    # database's CommitteeMembers keeps a seat after its term: Senate Finance
    # listed 24 members, 9 of them still in the Senate, where the Senate's own
    # roster names 8 on it, and Senate Judiciary 11 sitting where it names 5.
    # Staff reading the site found wrong rosters. So a seat is current only
    # where the member's own roster entry -- data/legislators.json, from the
    # General Court's daily Members file -- lists this committee. The House's
    # Finance divisions are Finance.
    #
    # AN EMPTY LIST IS AN ANSWER, NOT A SILENCE, and reading it as a silence is
    # what put Joe Barton on Legislative Administration after he had left it.
    # A sitting member whose roster named no committee used to keep every seat
    # the table still held for them, on the reasoning that there was no better
    # source. There is: the empty list itself. build_data sets committees only
    # after matching the member in the General Court's daily Members file, so
    # [] means "matched, and the file names none" -- 32 of the 406 sitting
    # members are in that state and every one of them is a positive statement.
    # A MISSING key would be a silence and still falls back; a present and
    # empty one no longer does.
    #
    # It published 14 seats across 12 committees for 13 people. All 14 carry
    # ActiveMember = 0 in the database's own dump and none appears on the
    # committee's own web roster, so both other sources independently condemn
    # every one; the cell "the roster names this committee AND ActiveMember=0"
    # is empty across all 473 published seats, so the two signals never
    # disagree.
    assigned = {}
    for mid, lg in legs.items():
        names_ = lg.get("committees")
        if names_ is None:
            continue
        ch = (lg.get("chamber") or "")[:1].upper()
        assigned[mid] = {code_of(re.sub(r"\s+-\s+Division\s+[IVX]+$", "", nm), ch)
                         for nm in names_} - {None}

    def on_it_today(seat, code):
        # "sitting" is Legislators.Active on the PERSON, not on the seat: it
        # says they are still in the building, not that they are still on this
        # committee. The roster, refreshed daily, is what says the second.
        if not seat.get("sitting") or code not in lead or str(seat.get("id")) not in legs:
            return False
        # AND THE SEAT'S OWN FLAG, where the data carries it. seat_active is
        # CommitteeMembers.ActiveMember, which the fetcher did not ask for
        # until 20 September, so it is absent from every record written before
        # then and this line does nothing until the next pull. It is here
        # because it is the source's own answer to exactly this question, and
        # because a seat the database has retired should not need a second
        # source to be dropped.
        if seat.get("seat_active") is False:
            return False
        mine = assigned.get(str(seat.get("id")))
        return True if mine is None else code in mine

    # ---- what each committee heard, day by day --------------------------
    days = collections.defaultdict(lambda: collections.defaultdict(list))
    bill_meta = {(b.get("term"), b.get("id")): b for b in idx}

    # Every bill's stations, read from the pages themselves. This used to open
    # site/bills/<year>/<ID>.json one bill at a time, and since the records
    # moved inside the pages that file exists only for the few too large to
    # inline -- so for two days a missing file read as "no station", and these
    # pages printed no time for 9,672 proceedings their bill pages timed.
    _stations = SR.by_bill(site, fields=("stations",))

    def station_of(year, bill, date, kind):
        """The bill page's own station for this proceeding, or None.

        One source for a proceeding's start, because two sources disagreed by
        four hours and neither page said which was which.
        """
        rec = _stations.get((str(year or ""), (bill or "").upper())) or {}
        want = (kind or "").strip().lower()
        for st in (rec.get("stations") or []):
            if st.get("when") != date:
                continue
            if want and want not in (st.get("what") or "").strip().lower():
                continue
            return st
        return None
    unmatched = collections.Counter()
    for r in P.load():
        cname = (r.get("committee") or "").strip()
        if not cname or not r.get("date"):
            continue
        code = code_of(cname, r.get("body"))
        if not code:
            unmatched[f"{r.get('body') or '?'} {cname}"] += 1
            continue
        meta = bill_meta.get((r.get("term"), r.get("bill"))) or {}
        st = station_of(meta.get("year", ""), r.get("bill"), r.get("date"),
                        r.get("kind"))
        days[code][(r.get("term"), r.get("date"))].append({
            "bill": r.get("bill"), "n": meta.get("n") or spaced(r.get("bill")),
            "title": meta.get("title", ""), "year": meta.get("year", ""),
            "term": r.get("term"), "kind": r.get("kind"),
            "video_id": (st or {}).get("video_id") or r.get("video_id") or "",
            # From the bill's own station, so the two pages agree by
            # construction. None where the bill has no station for that day:
            # no time is true, and the schedule guess was out by hours.
            "start": (st or {}).get("start"),
            "end": (st or {}).get("end"),
            # What the bill page says about how the start was arrived at, so
            # this page can say the same thing rather than imply certainty.
            "state": (st or {}).get("state") or "",
            "time": r.get("time") or "", "venue": r.get("venue") or "",
        })

    # ---- bills referred, per term ---------------------------------------
    referred = collections.defaultdict(lambda: collections.defaultdict(list))
    for b in idx:
        for nm in (b.get("committees") or ([b.get("committee")]
                                           if b.get("committee") else [])):
            # The chamber is in the name here -- "Senate Judiciary" -- so
            # code_of takes it from the prefix.
            code = code_of(nm, "")
            if code:
                referred[code][b.get("term")].append({
                    "id": b.get("id"), "n": b.get("n"), "year": b.get("year"),
                    "title": b.get("title", ""), "status": b.get("status", ""),
                    "kind": b.get("kind", ""), "term": b.get("term"),
                })

    out = site / "committee"
    out.mkdir(parents=True, exist_ok=True)
    t = S.template(site)
    index, written, urls, skipped = [], 0, [], []
    span_of = {}

    # H29 is "No Committee Assignment" -- the code the General Court files a
    # bill under when it has no committee. It is not a committee and must not
    # have a page; it had one, with two bills on it and no way in, because the
    # index only lists a chamber it can name and H29 has none.
    NOT_A_COMMITTEE = {"no committee assignment"}
    for code in sorted(set(list(seats) + list(referred) + list(days))):
        info = lead.get(code, {})
        name = (info.get("name") or (codes.get(code) or {}).get("name") or "")
        # A code with no name is not a committee this site can present. Five
        # of them -- H13, H14, H39, H40, H41 -- are in the database's
        # CommitteeMembers and in no other source: no name, no bills, no
        # sitting day, and pages titled "The House Committee on H13".
        if not name or name.strip().lower() in NOT_A_COMMITTEE:
            skipped.append(f"{code}" + (f" ({name})" if name else " (unnamed)"))
            continue
        # The code carries the chamber where nothing else states it.
        chamber = (info.get("chamber")
                   or (seats.get(code) or [{}])[0].get("chamber")
                   or (code[:1].upper() if code[:1].upper() in "HS" else ""))
        members = []
        for m in seats.get(code, []):
            if not on_it_today(m, code):
                continue
            lg = legs.get(m["id"]) or {}
            # A MEMBER WHO HAS LEFT IS NAMED LIKE ONE WHO HAS NOT. The roster
            # holds the 406 sitting members, and a committee's record reaches
            # back past them -- so 173 seats across 85 people fell through to
            # the source's own spelling and read "Soucy, Donna" beside
            # "Sen. Sharon Carson (R - SD14)". Everything the name needs is on
            # the seat already: chamber, party and district.
            members.append({**m,
                            "slug": lg.get("slug", ""),
                            "label": lg.get("display_full") or names.legislator({
                                "name": m.get("name"),
                                "chamber": m.get("chamber"),
                                "party_code": m.get("party_code"),
                                "district": m.get("district"),
                                "county_abbr": CABBR.get(
                                    str(m.get("county_code") or "").zfill(2), ""),
                            }) or m["name"],
                            "county": lg.get("county", ""),
                            # Baked in rather than joined on the page: a
                            # committee page loads its own 67 KB of JSON and
                            # not the 335 KB roster, so a client-side join
                            # would cost every reader the whole roster to
                            # write one email. 622 of the 625 sitting seats
                            # have an address on file; a member who has left
                            # has none, and gets none here.
                            "email": lg.get("email", "")})
        # Leadership comes from the web pages, which name a person rather than
        # an id, so it is matched on the name the roster prints.
        offices = [("Chair", (info.get("chair") or "").strip()),
                   ("Vice Chair", (info.get("vice_chair") or "").strip()),
                   ("Clerk", (info.get("clerk") or "").strip())]
        for m in members:
            m["role"] = next((role for role, nm in offices
                              if nm and nm == plain_name(m["name"])), "Member")
        # The officers as their own list, in the order a committee names them,
        # each carrying the slug of the member's own page.
        #
        # An officer the roster does not contain is still named. The two come
        # from different places -- the roster from the database, the officers
        # from the committee's web page -- and one being short of the other is
        # a reason to link less, not to say less.
        officers = []
        for role, nm in offices:
            if not nm:
                continue
            seat = next((x for x in members if plain_name(x["name"]) == nm), None)
            officers.append({"role": role, "name": nm,
                             "slug": (seat or {}).get("slug", ""),
                             "label": (seat or {}).get("label") or nm})

        sessions = []
        for (term, date), items in sorted(days.get(code, {}).items(),
                                          key=lambda kv: (kv[0][1] or ""),
                                          reverse=True):
            items.sort(key=lambda i: (i["start"] if i["start"] is not None
                                      else 1e9))
            sessions.append({
                "date": date, "term": term,
                "video_id": next((i["video_id"] for i in items
                                  if i["video_id"]), ""),
                "narrative": narrate(name, chamber, date, items, reports),
                "items": items,
            })

        rec = {
            "code": code, "name": name, "chamber": chamber,
            "chair": info.get("chair", ""), "vice_chair": info.get("vice_chair", ""),
            "clerk": info.get("clerk", ""), "officers": officers,
            "aide": info.get("aide", ""),
            "researcher": info.get("researcher", ""),
            # The House listing calls it "location" and the Senate's says
            # nothing, so a key named "room" was read and written empty for
            # every one of the 27 House committees that had a room on file.
            "room": info.get("room") or info.get("location") or "",
            "phone": info.get("phone", ""), "url": info.get("url", ""),
            # {"rule": "House Rule 31", "text": "It shall be the duty of..."}
            # or None. What a committee is FOR is the one thing a reader who
            # does not already know the General Court cannot work out from a
            # list of bills.
            "purpose": info.get("purpose") or None,
            "members": members,
            "bills": bills_in_order(referred.get(code, {})),
            "sessions": sessions,
        }
        (out / f"{code}.json").write_text(json.dumps(rec), encoding="utf-8")

        # The page, which is bills.html with this committee open. Same shell
        # as a bill's and a member's, from shell.py, so the three cannot drift.
        chamber_word = "Senate" if chamber == "S" else "House"
        towns = f"{len(rec['members'])} members"
        desc = (f"The {chamber_word} Committee on {name}. "
                f"{towns}, {sum(len(v) for v in rec['bills'].values()):,} bills "
                f"referred and {len(sessions):,} sitting days, each with what "
                "was taken up and when. From the New Hampshire General Court's "
                "own records.")
        nos = ('<noscript><div class="wrap" style="max-width:70ch;'
               'padding:26px 20px">'
               f"<h1>{S.E(name)}</h1><p>The {chamber_word} Committee on "
               f"{S.E(name)}"
               + (f", chaired by {S.E(rec['chair'])}" if rec["chair"] else "")
               + ".</p>"
               + (f"<p>{S.E(rec['purpose']['text'])}</p>"
                  if rec.get("purpose") else "")
               + "<p>This page draws the committee's bills and sitting "
                 "days in the browser, so it needs JavaScript. Everything it "
                 "shows comes from the file linked below, which needs none.</p>"
                 f'<ul><li><a href="/committee/{S.E(code)}.json">this page\'s '
                 "data as JSON</a></li>"
               + (f'<li><a href="{S.E(rec["url"])}" rel="noopener">this '
                  "committee on gencourt</a></li>" if rec.get("url") else "")
               + '</ul><p><a href="/bills.html">All bills</a></p></div></noscript>')
        path = f"/committee/{code}.html"
        (out / f"{code}.html").write_text(S.page(
            t, path=path, base=a.base,
            title=f"{name} — {chamber_word} committee | Granite Record",
            og_title=f"{name} — New Hampshire {chamber_word}",
            og_image="og-committee.png", og_alt="Granite Record: committees and hearings",
            description=desc,
            # The committee's feed, named in its head the way a bill's and a
            # member's are, so the Follow control finds it there. Taken out
            # again below for a committee found to be archived, which is
            # only known once every committee has been read.
            alternate=feed_link(code, name) if S.committee_followable(rec) else "",
            jsonld=LD.committee(code, name, a.base, S.canon(path)),
            globals={"GR_COMMITTEE": code, "GR_STANDALONE": True},
            noscript=nos, skip_label="Skip to this committee",
                  # Without this the template's own marker stays on Bills,
                  # and every committee page told a screen reader it was
                  # Bills. shell.page only moves the marker when told where.
                  nav_current="committees.html",
                  # The page draws the committee's own <h1>; the template's
                  # hidden "New Hampshire bills" one went first until now.
                  sr_title=""),
            encoding="utf-8")
        urls.append(a.base + S.canon(path))
        written += 1
        span_of[code] = sorted({t for t in rec["bills"] if t}
                               | {s["term"] for s in sessions if s.get("term")})
        index.append({
            "code": code, "name": name, "chamber": chamber,
            "chair": rec["chair"], "n_members": len(members),
            "n_bills": sum(len(v) for v in rec["bills"].values()),
            "n_sessions": len(sessions),
            "terms": sorted(rec["bills"]),
        })

    (site / "committees.json").write_text(json.dumps(index), encoding="utf-8")

    # The way in. Committee pages were built, sitemapped and unreachable: no
    # link to one existed anywhere on the site.
    def _card(c, dated=False):
        bits = []
        if dated and c.get("span"):
            bits.append(years(c["span"]))
        if c["chair"]:
            bits.append(f"Chaired by {S.E(c['chair'])}")
        if c["n_members"]:
            bits.append(f"{c['n_members']} member"
                        + ("" if c["n_members"] == 1 else "s"))
        if c["n_bills"]:
            bits.append(f"{c['n_bills']:,} bill"
                        + ("" if c["n_bills"] == 1 else "s"))
        if c["n_sessions"]:
            bits.append(f"{c['n_sessions']:,} session"
                        + ("" if c["n_sessions"] == 1 else "s"))
        return (f'<a class="ccard" href="committee/{S.E(c["code"])}.html">'
                f'<span class="cc-n">{S.E(c["name"])}</span>'
                f'<span class="cc-m">{" &middot; ".join(bits)}</span></a>')

    rows = [{**c, "span": span_of.get(c["code"], [])} for c in index]
    current_term = max((s[-1] for s in span_of.values() if s), default="")
    live, past, archived = listing_groups(rows, set(lead), current_term)
    # The committee's own page says so as well. A reader who arrives at
    # /committee/H05 from a search never sees this listing, and the page drew
    # Education with 22 members as if it sat today. Written into the JSON the
    # page draws, after the fact, because which committees are archived is
    # only known once every committee's record has been read.
    for c in archived:
        f = out / f"{c['code']}.json"
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec["archived"] = {"years": years(c["span"])}
        f.write_text(json.dumps(rec), encoding="utf-8")
        # And its page stops naming a feed: shell.committee_followable, which
        # build_feeds asks too, says an archived committee has none.
        h = out / f"{c['code']}.html"
        if h.exists():
            h.write_text(h.read_text(encoding="utf-8").replace(
                "\n" + feed_link(c["code"], c["name"]), ""), encoding="utf-8")
    body = []
    # THE TWO CHAMBERS SIDE BY SIDE. 25 House committees and 14 Senate ones
    # in one column put the Senate below a screen and a half of scrolling,
    # for a reader who very likely came looking for one of the 14. They are
    # two independent lists and nothing is served by stacking them.
    #
    # The columns are a grid on the container rather than a width on each
    # section, so they collapse to one on a narrow screen without either
    # column knowing about the other.
    cols = []
    for ch, word in (("H", "House"), ("S", "Senate")):
        rows_ = [c for c in live if c["chamber"] == ch]
        if not rows_:
            continue
        cols.append(f"<section><h2>{word}</h2><div class=\"ccards\">"
                    + "".join(_card(c) for c in
                              sorted(rows_, key=lambda x: x["name"]))
                    + "</div></section>")
    if cols:
        body.append('<div class="ctwo">' + "".join(cols) + "</div>")
    if past:
        # NOT "no longer meeting". House Rules is here with the Speaker as
        # its chair and nine members; so is a special committee with a chair
        # named on the General Court's own page today. What the site knows is
        # that no bill was referred and no sitting day is on record -- which
        # is a statement about this record, and true. Whether the committee
        # meets is not something these files can say.
        # No committee is named as an example here: which ones land in this
        # list changes as bills are referred.
        body.append('<h2>No bills or sessions on record</h2>'
                    '<p class="src">These committees have a roster, and in '
                    "some cases a chair, but no bill referred to them and no "
                    "session in the proceedings this site holds. Whether each "
                    "still meets is not something those records say."
                    '</p><div class="ccards">'
                    + "".join(_card(c) for c in
                              sorted(past, key=lambda x: x["name"]))
                    + "</div>")
    if archived:
        # At the bottom, in the same two columns, most recent first. The
        # chamber labels are h2 like the columns above: the stylesheet styles
        # `.clist h2` and nothing else, and an h3 drew at 18.7px over 14px
        # labels. By the outline they belong under this section's heading; an
        # h3 rule in app.css is the visuals session's to add, then these follow.
        cols = []
        for ch, word in (("H", "House"), ("S", "Senate")):
            rows_ = sorted((c for c in archived if c["chamber"] == ch),
                           key=lambda x: (x["span"][-1], x["name"]), reverse=True)
            if rows_:
                cols.append(f"<section><h2>{word}</h2><div class=\"ccards\">"
                            + "".join(_card(c, dated=True) for c in rows_)
                            + "</div></section>")
        body.append('<h2 id="archived">Not on the General Court&rsquo;s list today</h2>'
                    '<p class="src">Committees on this record that the General '
                    "Court does not list among its committees now, with the "
                    "years their bills and sitting days cover. The records "
                    "show when a committee stops appearing, not why&thinsp;&mdash;&thinsp;it may "
                    "have been renamed, divided, merged or ended&thinsp;&mdash;&thinsp;and this "
                    "page does not guess which. Each keeps its page, so the "
                    "bills it handled still have somewhere to point.</p>"
                    '<div class="ctwo">' + "".join(cols) + "</div>")

    page_html = S.page(
        S.template(site), path="/committees.html", base=a.base,
        title="Committees | Granite Record",
        og_title="New Hampshire General Court committees",
        og_image="og-committee.png", og_alt="Granite Record: committees and hearings",
        description=("Every committee of the New Hampshire General Court: who "
                     "sits on it, the bills referred to it, and what it did on "
                     "each day it met."),
        globals={"GR_STATIC": True}, og_type="website",
        jsonld=LD.listing("New Hampshire General Court committees",
                          "Every committee of the New Hampshire General Court.",
                          a.base, S.canon("/committees.html")),
        noscript="", skip_label="Skip to the committees",
                  nav_current="committees.html", sr_title="")
    # A plain listing rather than an app view: there is nothing to filter and
    # 56 links do not need JavaScript to draw.
    page_html = page_html.replace(
        '<div id="results"></div>',
        f'<div id="results"><div class="clist"><h1>Committees</h1>'
        f'<p class="src">Bill-first search answers what happened to a bill. '
        f'These answer what a committee did on a day.</p>'
        + "".join(body) + "</div></div>", 1)
    (site / "committees.html").write_text(page_html, encoding="utf-8")
    print("committees.html written")

    assert written, ("no committee page was written. That means no committee "
                     "name in proceedings.csv matched data/committees.json, "
                     "which is a parse problem rather than an empty session.")
    # sitemap.xml is written by build_bill_pages.py, which runs first.
    # Appended rather than replaced: rewriting it here would drop every other
    # URL on the site.
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{S.E(u)}</loc></url>\n" for u in urls
                      if S.E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"{len(add.splitlines())} added to sitemap.xml")

    print(f"{written} committees -> {out}/")
    if skipped:
        print(f"  {len(skipped)} code(s) skipped as not a nameable committee: "
              + ", ".join(skipped))
    print(f"  {sum(i['n_members'] for i in index):,} seats, "
          f"{sum(i['n_bills'] for i in index):,} bill referrals, "
          f"{sum(i['n_sessions'] for i in index):,} sitting days")
    lead_n = sum(1 for i in index if i["chair"])
    print(f"  {lead_n} of {written} have a chair on file")
    if unmatched:
        print(f"  {len(unmatched)} committee name(s) in proceedings.csv match "
              "nothing in data/committees.json:")
        for nm, n in unmatched.most_common(6):
            print(f"    {nm!r} on {n:,} rows")
    empty = [i["code"] for i in index if not i["n_sessions"]]
    if empty:
        print(f"  {len(empty)} committee(s) have no sitting day on record: "
              + ", ".join(empty[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
