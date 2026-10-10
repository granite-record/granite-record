#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.56
"""
A page's worth of data for every committee.

    python3 src/pages/build_committees.py --site site --data data

WHAT A COMMITTEE PAGE ANSWERS

Bill-first search answers "what happened to HB 1442". This answers "what did
Legislative Administration do on 3 March", which is the question a reporter or
a member of that committee actually asks, and the site could not answer it at
all.

WHERE EACH PART COMES FROM

  identity, leadership, room   committees.json          fetch_committees.py
  clerk, purpose               committee_details.json   fetch_committee_details.py
                               (joined by committee_details.read, which says
                               which file gives which field)
  who sits on it               data/committee_members.json
                                                        fetch_committee_members_db.py
  bills referred               site/idx/<term>.json     the bill index
                               (site_read.bill_index)
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

WHAT HAPPENED TO EACH BILL AT A MEETING, AND WHAT THE COMMITTEE REPORTED

Each meeting carries `outcomes`, one entry a bill: the kinds of sitting it
had, the online sign-ins at a hearing, and what the committee voted there --
its recommendation with the tally and the minority's, an interim study
report (one not recommending future legislation marked killed), a retention
-- or, where it voted nothing, the day the docket dates its vote. Each bill
of the Bills tab carries `reported`: the committee's acts on it, each dated
by the meeting it was voted at. committee_acts.py says how each is read off
the bill's docket, and why by the docket's vote date (the person's feedback
of 9 October 2026, items 1 and 12, and v8).

Writes site/committees.json and site/committee/<code>.json. It writes no HTML:
the page is app.js with one committee open, the same way a bill's page is.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import json
import re
import types

import proceedings as P
import bill_order as BO
import build_date
import committee_acts as CA
import committee_details as CD
import committee_names as CN
import names
import report_check as RC
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
def fdate(d):
    """"March 3, 2026", in a sentence: shell.date_words."""
    return S.date_words(d or "", "full")


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


def meeting_kinds(kinds):
    """The kinds of sitting a bill had at one meeting, in the order a
    committee day runs (KIND_ORDER), whatever order its rows came in."""
    return [k for k in KIND_ORDER if k in kinds] + [k for k in kinds if k not in KIND_ORDER]


def is_ahead(date):
    """Whether a committee day is still to come on the day the site is built:
    scheduled, not met."""
    return str(date or "")[:10] > build_date.today().isoformat()


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
    ahead = is_ahead(date)
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


def its_own_sitting(r):
    """Is this proceedings row a sitting of the committee it names?

    NOT A COMMITTEE OF CONFERENCE. A conference is the two chambers'
    conferees on one bill, meeting jointly under House Rule 50, and not a
    sitting of either chamber's standing committee -- the rule
    build_pages.meeting_key already keeps on the Calendar, where SB 14's
    conference drawn as a sitting of Senate Judiciary was the mistake it
    records. A conference row carries a committee because a docket row for
    the bill carried the committee it was referred to: the Senate's notice
    names none -- "Committee of Conference Meeting: 06/16/2025, 12:00 pm,
    Room 100, SH" -- and the House's names none either. Filed under that
    name, this page said "The Committee on Finance met on June 12, 2025 for
    committees of conference on HB 1 and HB 2", of a day House Finance did
    not sit, and reading the House's notices (docket_parser) would have added
    50 such days to 16 House committees in 2025-2026 alone. Before them, 1,031
    conference rows were filed so, and 627 of the committee-days they made
    held nothing else -- counted by chamber and name rather than by page, so
    the pages' own count may differ by a renamed committee or two. The
    conference stays on the bill's page and on the Calendar, where it is its
    own card.
    """
    return bool((r.get("committee") or "").strip() and r.get("date")
                and (r.get("kind") or "").strip().lower() != "committee of conference")


# A NOTICE IS NOT A SITTING ON THE BILL (1 October 2026). proceedings.csv
# reads the docket's notices -- "Public Hearing: 1/12/2012 10:30 AM LOB 207",
# entered on 15 December -- and a notice is entered before the day. HB 1284 of
# 2012 was withdrawn on 4 January, never introduced, and Education's page said
# the committee met on January 12, 2012 for a public hearing on it and on the
# 24th for an executive session; HB 273 of 2017, which the House never
# introduced, stood among the bills Executive Departments and Administration
# heard on 10 January 2017. The rule is proceedings.notice_only, asked of each
# bill's own history (narratives.json) through proceedings.sittings: the rule
# build_site_v2 asks for the bill's stations, so this page and the bill's
# agree by it, and the download and the Learn pages' count with them.
#
# IT WAS FIRST TAKEN FROM WHAT THE BILL'S PAGE DID NOT DRAW (a_sitting_on_it):
# a row with no station on its day was a notice. That left off any row a page
# happened not to draw, held only by a count, and a lookup that missed kept
# every row and said nothing. A row is left off for what its bill's history
# says, and the two guards below hold each direction.
#
# How many rows may be left off before the build stops. FOUR OF 95,422 on 1
# October 2026: HB 1284 of 2012's two, the hearing of the 12th on HB 1512 of
# 2012 (introduced, and withdrawn on the 4th) and HB 273 of 2017's. A ceiling
# well above that lets a few more such bills through and stops the build on a
# count of another kind.
#
# 425 ON 6 OCTOBER 2026, when a meeting a later row of the docket cancelled or
# moved stopped being told as held (narrative.overtaken): HB 114 of 2013's
# hearing of 15 January, cancelled the next morning, and some 420 more of
# 1989-2023, against the six before. Still a few hundred of 95,422; a history
# that read whole terms as withdrawn would leave off tens of thousands.
NOTICE_CEILING = 1000


def notice_guard(notices, ceiling=NOTICE_CEILING):
    """What to stop the build with when more of proceedings.csv's rows are
    left off the committees' days than `ceiling`, or "". A history that
    marked whole terms withdrawn or never introduced would take every sitting
    on their bills off every committee's page, and exit 0."""
    if len(notices) <= ceiling:
        return ""
    return (f"{len(notices):,} rows of proceedings.csv are notices its bill's history "
            "does not tell as a meeting held (withdrawn before the day, never introduced, "
            "or cancelled or moved by a later row), past the "
            f"ceiling of {ceiling} (NOTICE_CEILING): " + ", ".join(notices[:6])
            + ". These are meant to be the docket's notices of meetings that did "
            "not sit. Read what narratives.json says of these bills "
            "before raising the ceiling: left off, they take the committees' "
            "sitting days with them.")


# The statuses build_site_v2 gives a bill that was never introduced: its
# NEVER_INTRODUCED, and preflight holds the two alike.
NEVER_INTRODUCED = {"Refused introduction", "Withdrawn prior to introduction",
                    "Proposed for the special session", "Not introduced"}


def untaken_guard(filed):
    """What to stop the build with when a row filed under a committee's day is
    for a bill the site's index says was never introduced, or "".

    THE OTHER DIRECTION, and the silent one. With narratives.json of another
    build, or holding no history for the bill, no row of it is a notice:
    every row is filed, HB 273 of 2017 is back among the bills Executive
    Departments and Administration heard on 10 January 2017, and the build
    exits 0. The index is the second witness -- its status is build_site_v2's
    word for the same history -- and no committee sat on a bill that was
    never introduced. `filed` is [(the row, the bill's row of the index)]."""
    bad = [f"{r.get('bill')} of {r.get('term')} ({r.get('kind')} {r.get('date')}, "
           f"{meta.get('status')})" for r, meta in filed
           if (meta or {}).get("status") in NEVER_INTRODUCED]
    if not bad:
        return ""
    return (f"{len(bad)} row(s) of proceedings.csv are filed under a committee's day "
            "for a bill the bill index (site/idx) says was never introduced: "
            + ", ".join(bad[:6]) + ". No committee sat on such a bill. Its history "
            "in narratives.json does not say what the index says, so the two are "
            "of different builds or the history is missing: run narrative.py "
            "--all and build_site_v2.py again, then this.")


def years(span):
    """["1989-1990", ..., "2023-2024"] -> "1989 to 2024"."""
    first, last = span[0][:4], span[-1][-4:]
    return first if first == last else f"{first} to {last}"


def runs(terms):
    """["1997-1998", "2009-2010"] -> "1997 to 1998 and 2009 to 2010": years()
    of each unbroken run, so a name a committee carried twice is not said to
    have been carried through the terms between."""
    out, cur = [], []
    for t in sorted(terms):
        if cur and t[:4] != str(int(cur[-1][-4:]) + 1):
            out.append(cur)
            cur = []
        cur.append(t)
    if cur:
        out.append(cur)
    return andlist(years(r) for r in out)


def name_on_the_day(page_name, said):
    """The committee's name as the day's own rows give it.

    `said` is a Counter of the names the day's rows carry. A page is headed
    with the name the committee has now, or last had, and its record reaches
    back past a rename: H26's hearings of 1995 were Corrections and Criminal
    Justice's, and "The Committee on Criminal Justice and Public Safety met on
    March 2, 1995" puts a name on a sitting that the committee did not carry
    for two more years. The page's own spelling is kept wherever the two are
    the same name.
    """
    if not said:
        return page_name
    top = said.most_common(1)[0][0]
    return page_name if CN._norm(top) == CN._norm(page_name) else top


def former_names(page_name, by_name):
    """[{"name", "years"}], oldest first, for every name other than the
    page's own that the committee's bills and sitting days carry. `by_name`
    is {name: set of terms}. What the page and the listing label a committee
    with when a reader arrives by a name it no longer has."""
    out = []
    for nm, terms in by_name.items():
        if not terms or CN._norm(nm) == CN._norm(page_name):
            continue
        out.append((min(terms), nm, {"name": nm, "years": runs(terms)}))
    return [x for _, _, x in sorted(out, key=lambda r: (r[0], r[1]))]


def shared_pages(shared, span_of, index):
    """{page: (code, [{"page", "name", "years", "when"}])} for every page
    written for a code the General Court gave more than one committee.

    `shared` is committee_names.shared(); `span_of` is {page: the sorted
    terms of its bills and sitting days}; `index` is the rows of
    committees.json, whose names are the pages' own. Another page is named
    only where it was written, since a page with no record is nowhere to
    send a reader. "when" says whether the other's record comes "later" or
    "earlier" than this one's, which is what the page's sentence turns on,
    and is "" should the two ever overlap."""
    name = {c["code"]: c["name"] for c in index}
    out = {}
    for page, (code, others) in shared.items():
        mine = span_of.get(page) or []
        if page not in name or not mine:
            continue
        them = []
        for o in others:
            span = span_of.get(o) or []
            if o not in name or not span:
                continue
            them.append({"page": o, "name": name[o], "years": runs(span),
                         "when": ("later" if span[0] > mine[-1] else
                                  "earlier" if span[-1] < mine[0] else "")})
        if them:
            out[page] = (code, them)
    return out


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


def committee_card(c, dated=False):
    """One committee on the committees index: its name, and what the record
    holds for it -- its years where `dated`, its earlier names, its chair,
    members, and the bills and sessions of every term, said to be so."""
    bits = []
    if dated and c.get("span"):
        bits.append(runs(c["span"]))
    # The earlier name on the card too, so a reader scanning this page for
    # "Corrections and Criminal Justice" finds where it went.
    if c.get("formerly"):
        bits.append("earlier " + S.E("; ".join(c["formerly"])))
    if c["chair"]:
        bits.append(f"Chaired by {S.E(c['chair'])}")
    if c["n_members"]:
        bits.append(f"{c['n_members']} member"
                    + ("" if c["n_members"] == 1 else "s"))
    counts = []
    if c["n_bills"]:
        counts.append(f"{c['n_bills']:,} bill"
                      + ("" if c["n_bills"] == 1 else "s"))
    if c["n_sessions"]:
        counts.append(f"{c['n_sessions']:,} meeting"
                      + ("" if c["n_sessions"] == 1 else "s"))
    # EVERY TERM'S, AND SAID SO (the survey of 7 October 2026, C10).
    # Beside today's chair and members, "1,257 bills · 577 sessions" read
    # as this term's, and Election Law's page says 144 this term. A card
    # already dated by its years says it there.
    if counts and not dated and c.get("span"):
        counts = [" and ".join(counts) + f" since {c['span'][0][:4]}"]
    bits += counts
    return (f'<a class="ccard" href="committee/{S.E(c["code"])}.html">'
            f'<span class="cc-n">{S.E(c["name"])}</span>'
            f'<span class="cc-m">{" &middot; ".join(bits)}</span></a>')


def feed_link(code, name):
    """The head's link to a committee's feed, written once so it can be taken out
    again exactly as it was put in."""
    return (f'<link rel="alternate" type="application/rss+xml" '
            f'title="{S.E(name)} committee updates" href="/feed/committee/{S.E(code)}.xml">')


def bills_in_order(by_term):
    """A committee's referred bills, per term, by number as bills.html lists
    them. Sorted on the id's text this put HB1003 before HB101 on the page:
    the Bills tab shows this file's order and has no sort control.

    The terms newest first, as meta.json names them. They were in whatever
    order index.json held its rows -- 2025-2026, 2023-2024 and then 1989-1990
    upward, the order build_data met the dockets in -- which the page never
    showed (recordTerms sorts them) and the file should not depend on."""
    return {t: sorted(by_term[t], key=lambda b: BO.bill_key(b["id"]))
            for t in sorted(by_term, key=lambda t: str(t or ""), reverse=True)}


# THE CEILING ON COMMITTEE NAMES THAT REACH NO PAGE. A hearing whose
# committee's name matches nothing in data/committees.json is on no committee
# page, and this used to print six of them and exit 0. On 10 September that
# was 15 names; by 24 September, once every older term's manifest had
# arrived, it was 656 -- and House Executive Departments and Administration
# showed no sitting day at all for 1999-2004 -- with nothing in any log to
# say when it happened. committee_names.official brought it to 112: the
# committees of their day that no page existed for (House Commerce of
# 1997-2008, the Senate's Public Affairs and Insurance ...) and a handful of
# fragments the docket parser leaves. committee_names.CODES then gave the 17
# of those whose General Court code is on this disk pages of their own, and
# it was 95 the next day: House Appropriations, the Senate's Transportation
# and Interstate Cooperation, its Internal Affairs after 1992, and the rest
# whose code no page here gives. The bill-status pages fetched on 25
# September took it to 73, and the person's two decisions of that day, which
# placed the Senate's Internal Affairs after 1992 and its Development,
# Recreation and Environment of 1989-1990, to 71. A ceiling above 112 lets a
# new special committee or two through and stops the build on the next jump.
UNMATCHED_CEILING = 150


def unmatched_guard(unmatched, ceiling=UNMATCHED_CEILING):
    """The message to stop the build with, or "" when the count is in bounds.

    `unmatched` is {"H Exec Depts and Admin": rows}, as main counts it.
    """
    if len(unmatched) <= ceiling:
        return ""
    top = "; ".join(f"{nm!r} on {n:,} rows" for nm, n in unmatched.most_common(8))
    return (f"{len(unmatched)} committee names in proceedings.csv match no "
            f"committee page, over the ceiling of {ceiling} this file states "
            f"(UNMATCHED_CEILING). The hearings under them are on no committee "
            f"page. The most common: {top}. If they are a committee's shorthand "
            "or a new spelling, committee_names.py is where it is settled and "
            "build_proceedings.py writes it; if proceedings.csv predates that, "
            "rebuild it. If they are real committees with no page, raise the "
            "ceiling and say why beside it.")


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


# H29 is "No Committee Assignment" -- the code the General Court files a
# bill under when it has no committee. It is not a committee and must not
# have a page; it had one, with two bills on it and no way in, because the
# index only lists a chamber it can name and H29 has none.
NOT_A_COMMITTEE = {"no committee assignment"}


def committee_name(code, lead, codes):
    """The name a committee's page goes by: the listing's (who_sits' lead),
    else data/committees.json's (codes), else ""."""
    return ((lead.get(code) or {}).get("name")
            or (codes.get(code) or {}).get("name") or "")


def presentable(name):
    """Whether a committee of this name gets a page. A code with no name does
    not: five of them -- H13, H14, H39, H40, H41 -- are in the database's
    CommitteeMembers and in no other source, with no name, no bills and no
    sitting day, and had pages titled "The House Committee on H13". Nor does
    H29 (NOT_A_COMMITTEE)."""
    return bool(name) and name.strip().lower() not in NOT_A_COMMITTEE


def who_sits(site, data):
    """What this step reads to say who sits on each committee today, and the
    helpers it reads it with, as one namespace: the listing with its details
    joined in (web), the seat table (seats), the committees' codes with the
    retired ones added (codes, retired), the roster (legs), the name-to-code
    map and its helpers (by_name, bare, code_of), the listing by code (lead)
    and on_it_today(seat, code).

    ONE PLACE, FOR TWO READERS (10 October 2026). main() builds the pages
    from it, and with_roster() counts the committees it gives a member, for
    the home page's Committees card -- which build_pages writes four steps
    before main() runs, so it cannot read main()'s committees.json, and on a
    build into an empty site (GitHub's nightly) there was none to read.
    Nothing here is a later step's: the files are the fetchers', and
    site/legislators.json is the site data's, which runs first."""
    # committees.json with committee_details.json joined in. Two files since
    # 26 September, because GitHub's weekly job swaps committees.json in whole
    # from the listing pages, which carry no clerk and no purpose: read alone,
    # its first Sunday would have taken both off every page. A missing details
    # file is a warning and a page without them, not a stopped build; one that
    # is there and will not read stops it, saying what to do.
    web = CD.read("committees.json", "committee_details.json")
    seats = load(data / "committee_members.json", {})
    codes = load(data / "committees.json", {})
    # THE COMMITTEES THE GENERAL COURT HAS RETIRED. Its committee table holds
    # the codes it uses now; the codes its own bill-status pages file older
    # bills under -- H33, 1995-2008's Commerce; S18, the Senate's Economic
    # Development and then Energy and Economic Development -- are in
    # committee_names.CODES with their witnesses, and each gets a page here
    # under the name it last carried. Nothing in data/committees.json is
    # replaced: H26 and H47 are in CODES for an older name of theirs, and
    # they keep the name they have today. The keys are pages rather than
    # codes: a code the General Court gave two committees is a page for each
    # (committee_names.GAPS), so S03 is Appropriations' and S03-1989 the
    # Senate's Development, Recreation and Environment of 1989-1990.
    retired = {c: nm for c, nm in CN.retired().items() if c not in codes}
    for c, nm in retired.items():
        codes[c] = {"code": c, "name": nm}
    legs = {str(m.get("id")): m for m in load(site / "legislators.json", [])}

    # (chamber, name) -> code. NOT name alone: both chambers have a
    # Judiciary, a Finance and a Ways and Means, so a name-only map silently
    # gave one chamber's committee the other's roster and sitting days -- the
    # same confusion as a bill number across two terms, in a different file.
    #
    # The code carries the chamber: H05 is a House committee, S30 a Senate
    # one, and that is the only place the chamber is stated for a House
    # committee, whose page does not say.
    #
    # A retired code is not in this map. It is reached only through
    # committee_names.CODES, for the names and terms that file there, so
    # 2017-2018's Election Law and Internal Affairs is still S50's while
    # 2007-2008's, the retired S33, is S33's.
    by_name = {}
    for code, rec in codes.items():
        nm = (rec.get("name") or "").strip()
        ch = code[:1].upper() if code else ""
        if nm and ch in ("H", "S") and code not in retired:
            by_name[(ch, CN._norm(nm))] = code

    def bare(name, chamber):
        """(chamber, name) with the chamber taken off the front of the name
        where the search index put it there: "Senate Judiciary"."""
        nm = (name or "").strip()
        ch = (chamber or "").strip().upper()[:1]
        for pre, c in (("house ", "H"), ("senate ", "S")):
            if nm.lower().startswith(pre):
                return c, nm[len(pre):]
        return ch, nm

    def code_of(name, chamber, term=""):
        """The committee a name means, in the chamber that named it and the
        term it was named in.

        The term matters because a name has not always meant one committee:
        committee_names.page_code asks CODES first, where the General Court's
        own filing says a name meant a different code in an earlier term, and
        today's list after. The web file and the roster name committees as
        they are now and pass no term.
        """
        # The search index writes "Senate Judiciary" and "House Finance";
        # proceedings.csv writes the bare name and carries the chamber in its
        # own column. Both forms end up here.
        ch, nm = bare(name, chamber)
        if not nm:
            return None
        return CN.page_code(nm, ch, term, by_name)
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
    return types.SimpleNamespace(web=web, seats=seats, codes=codes, retired=retired,
                                 legs=legs, by_name=by_name, bare=bare, code_of=code_of,
                                 lead=lead, on_it_today=on_it_today)


def with_roster(site="site", data="data"):
    """How many committees this step gives a member today: the entries of its
    committees.json whose n_members is more than 0, counted as main() fills
    them -- every seat on a committee that gets a page, kept where
    on_it_today keeps it -- without the bills, the meetings or the pages,
    which only main() needs. build_pages asks it for the home page's
    Committees card (build_pages.committees_with_roster), and preflight's
    _home_counts_rosters_cold holds the two to the same number on a build
    into an empty site."""
    R = who_sits(Path(site), Path(data))
    return sum(1 for code, held in R.seats.items()
               if presentable(committee_name(code, R.lead, R.codes))
               and any(R.on_it_today(m, code) for m in held or []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--data", default="data")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site, data = Path(a.site), Path(a.data)

    # Every bill's row, from the term files the pages read; it stops, saying
    # why, where there is no site or the files do not hold together -- the
    # bills a committee heard come from it.
    idx = SR.bill_index_or_stop(site, "build_committees.py")
    # Who sits on each committee today, and what each is called: who_sits,
    # which with_roster reads too, for the home page's count.
    R = who_sits(site, data)
    seats, codes, retired, legs = R.seats, R.codes, R.retired, R.legs
    bare, code_of, lead, on_it_today = R.bare, R.code_of, R.lead, R.on_it_today
    # Both files, CONCATENATED per bill rather than one shadowing the other.
    # setdefault kept only the first: a bill reported by a House committee and
    # then by a Senate one -- which is most bills that pass a chamber -- lost
    # the Senate's report entirely, so a Senate committee narrating its own
    # executive session had nothing of its own to quote and quoted the House's.
    reports = {}
    # The House Calendar's printings, less the reports report_check.py found
    # printed under another bill: a record it drops is not this bill's, and a
    # committee day would otherwise narrate another bill's recommendation.
    house = load("committee_reports.json", {})
    RC.apply(house, load("report_corrections.json", {}))
    for src in (house, load("senate_reports.json", {})):
        for t, byb in src.items():
            for b, v in byb.items():
                reports.setdefault(t, {}).setdefault(b, []).extend(
                    v if isinstance(v, list) else [v])
    load_county_abbr(legs)

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
    # The names each committee's record carries, as it carried them: the
    # day's own name for its narrative, and every name for the page's head.
    day_said = collections.defaultdict(lambda: collections.defaultdict(
        collections.Counter))
    names_at = collections.defaultdict(lambda: collections.defaultdict(set))
    # The rows a committee sat for, and the docket's bare notices left off
    # (proceedings.notice_only), by each bill's own history. SILENCE IS NOT
    # SUCCESS: with no histories here every notice would be filed as a
    # sitting and nothing would say so.
    rows, histories = P.load(), load("narratives.json", {})
    if rows and not histories:
        raise SystemExit("narratives.json is not there, or holds nothing. A docket "
                         "notice for a bill withdrawn or never introduced is told "
                         "apart from a sitting by the bill's history, and without it "
                         "every notice would be filed as a day the committee sat. "
                         "Run python3 src/parse/narrative.py --all first.")
    rows, left_off = P.sittings(rows, histories)
    # WHAT EACH COMMITTEE DID TO EACH BILL, read off its docket while the
    # histories are here (committee_acts.acts): its reports, each with the day
    # the docket dates the vote, its interim study reports and its retentions.
    # A meeting's `outcomes` and a Bills tab row's `reported` are made of them.
    acts_of = {(t, b): CA.acts(rec.get("events")) for t, byb in histories.items()
               for b, rec in byb.items()}
    del histories
    notices = [f"{r.get('bill')} {r.get('kind')} {r.get('date')}"
               for r in left_off if its_own_sitting(r)]
    # Every row filed, with its bill's row of the index (untaken_guard).
    filed = []
    for r in rows:
        if not its_own_sitting(r):
            continue
        meta = bill_meta.get((r.get("term"), r.get("bill"))) or {}
        filed.append((r, meta))
        cname = (r.get("committee") or "").strip()
        code = code_of(cname, r.get("body"), r.get("term"))
        if not code:
            unmatched[f"{r.get('body') or '?'} {cname}"] += 1
            continue
        day_said[code][(r.get("term"), r.get("date"))][cname] += 1
        if r.get("term"):
            names_at[code][cname].add(r["term"])
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
    # Before a page is written: past the ceiling these are not the few
    # notices, and a row filed for a bill that was never introduced is one
    # the rule did not see.
    stop = notice_guard(notices) or untaken_guard(filed)
    if stop:
        raise SystemExit(stop)

    # ---- what happened to each bill at each meeting ---------------------
    # Each bill's meetings, across committees, (date, code, kinds): whose a
    # retention or an interim study report is (committee_acts.owners), and
    # which of a committee's meetings the docket dates its vote to.
    met_on = collections.defaultdict(list)
    for code_, by_day in days.items():
        for (term_, date_), items_ in by_day.items():
            kinds_ = collections.defaultdict(list)
            for it in items_:
                if it["kind"] not in kinds_[it["bill"]]:
                    kinds_[it["bill"]].append(it["kind"])
            for bill_, ks in kinds_.items():
                met_on[(term_, bill_)].append((date_, code_, meeting_kinds(ks)))
    for v in met_on.values():
        v.sort()
    owners_of = {}

    def owners(term, bill):
        """Whose each of the bill's acts is, worked out once a bill."""
        k = (term, bill)
        if k not in owners_of:
            owners_of[k] = CA.owners(acts_of.get(k, []), met_on.get(k, []),
                                     lambda nm, body: code_of(nm, body, term))
        return owners_of[k]

    def mine_of(code, term, bill):
        return {d: ks for d, c, ks in met_on.get((term, bill), []) if c == code}

    def reported_row(code, term, bill):
        """{"reported": [...]}: this committee's acts on the bill, for its
        Bills tab (committee_acts.reported), each with the meeting the
        docket dates it to; {} where it recorded none."""
        got = CA.reported(code, acts_of.get((term, bill), []), owners(term, bill),
                          mine_of(code, term, bill))
        return {"reported": got} if got else {}

    def meeting_outcomes(code, term, date, items):
        """What happened to each bill at one meeting (committee_acts.outcome),
        in the order the meeting took them up: the kinds of sitting it had,
        the online sign-ins where the bill's own page has them for this
        hearing (its station's, matched on the date, so that the two pages
        agree), and what the committee voted there or, where it voted
        nothing, the day the docket dates its vote."""
        order, kinds = [], collections.defaultdict(list)
        for it in items:
            if it["bill"] not in kinds:
                order.append(it["bill"])
            if it["kind"] not in kinds[it["bill"]]:
                kinds[it["bill"]].append(it["kind"])
        out = []
        for b in order:
            ks = meeting_kinds(kinds[b])
            year = next((it["year"] for it in items if it["bill"] == b), "")
            signed = next(((station_of(year, b, date, k) or {}).get("testimony")
                           for k in ks if k in CA.HEARD
                           and (station_of(year, b, date, k) or {}).get("testimony")),
                          None)
            out.append({"bill": b, **CA.outcome(code, date, ks, acts_of.get((term, b), []),
                                                owners(term, b), mine_of(code, term, b),
                                                signed, is_ahead(date))})
            told[out[-1]["outcome"]] += 1
        return out
    told = collections.Counter()

    # ---- bills referred, per term ---------------------------------------
    referred = collections.defaultdict(lambda: collections.defaultdict(list))
    for b in idx:
        for nm in (b.get("committees") or ([b.get("committee")]
                                           if b.get("committee") else [])):
            # The chamber is in the name here -- "Senate Judiciary" -- so
            # code_of takes it from the prefix.
            code = code_of(nm, "", b.get("term"))
            if code:
                if b.get("term"):
                    names_at[code][bare(nm, "")[1]].add(b["term"])
                referred[code][b.get("term")].append({
                    "id": b.get("id"), "n": b.get("n"), "year": b.get("year"),
                    "title": b.get("title", ""), "status": b.get("status", ""),
                    "kind": b.get("kind", ""), "term": b.get("term"),
                    # The word the bill's card shows (build_site_v2.chip_word),
                    # for a card drawn from this row rather than the index's.
                    "chip": b.get("chip", ""),
                    # What this committee reported on it, dated by the meeting
                    # it was voted at (committee_acts.reported): the Bills
                    # tab's card says it (the person, 9 October 2026, item 1).
                    **reported_row(code, b.get("term"), b.get("id")),
                })

    out = site / "committee"
    out.mkdir(parents=True, exist_ok=True)
    t = S.template(site)
    index, written, urls, skipped = [], 0, [], []
    span_of = {}

    for code in sorted(set(list(seats) + list(referred) + list(days))):
        info = lead.get(code, {})
        name = committee_name(code, lead, codes)
        # A code with no name, or H29's, is not a committee this site can
        # present (presentable says which).
        if not presentable(name):
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
            # Under the name the committee had that day, which on H26's page
            # of 1995 is Corrections and Criminal Justice.
            said = name_on_the_day(name, day_said[code].get((term, date)))
            sessions.append({
                "date": date, "term": term,
                "video_id": next((i["video_id"] for i in items
                                  if i["video_id"]), ""),
                "narrative": narrate(said, chamber, date, items, reports),
                "items": items,
                # A DAY STILL TO COME IS NOT A DAY IT MET (the survey of 7
                # October 2026). The docket books sittings ahead of time, and
                # Commerce's Sessions tab said "56 days this committee met in
                # 2025-2026" over a 14 October 2026 still to come. The day is
                # listed, told as scheduled (narrate), and counted apart.
                **({"ahead": True} if is_ahead(date) else {}),
                # WHAT HAPPENED TO EACH BILL AT THIS MEETING (the person,
                # 9 October 2026, item 12: "make clearer what changed on each
                # bill at that meeting, if anything did"), one entry a bill in
                # the order of `items` (meeting_outcomes, committee_acts).
                "outcomes": meeting_outcomes(code, term, date, items),
            })
        met_days = sum(1 for s in sessions if not s.get("ahead"))

        # THE NAMES IT CARRIED BEFORE, with the years each covers on this
        # record. A reader who followed "Corrections and Criminal Justice" off
        # a 1995 bill lands on a page headed Criminal Justice and Public
        # Safety, and this is what tells them it is the same committee. Only
        # committee_names.CODES puts a second name on a page.
        formerly = former_names(name, names_at.get(code, {}))
        rec = {
            "code": code, "name": name, "chamber": chamber,
            **({"names": formerly} if formerly else {}),
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
        # A retired committee has no seats to count, and "0 members" in the
        # line a search result shows would read as a committee nobody sits on
        # today rather than one that no longer sits.
        towns = (f"{len(rec['members'])} members, " if code not in retired
                 else "")
        span_of[code] = sorted({t for t in rec["bills"] if t}
                               | {s["term"] for s in sessions if s.get("term")})
        # And its years beside its name, in the tab and the search result: a
        # retired code can share its name with a later committee -- S33 and
        # S50 are both Election Law and Internal Affairs -- and the years are
        # what tells the two apart before the page is open.
        when = (f" ({runs(span_of[code])})"
                if code in retired and span_of[code] else "")
        desc = (f"The {chamber_word} Committee on {name}{when}. "
                f"{towns}{sum(len(v) for v in rec['bills'].values()):,} bills "
                f"referred and {met_days:,} meetings, each with what "
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
               + "<p>This page draws the committee's bills and meetings "
                 "in the browser, so it needs JavaScript. Everything it "
                 "shows comes from the file linked below, which needs none.</p>"
                 f'<ul><li><a href="/committee/{S.E(code)}.json">this page\'s '
                 "data as JSON</a></li>"
               + (f'<li><a href="{S.E(rec["url"])}" rel="noopener">this '
                  "committee on gencourt</a></li>" if rec.get("url") else "")
               + '</ul><p><a href="/bills.html">All bills</a></p></div></noscript>')
        path = f"/committee/{code}.html"
        (out / f"{code}.html").write_text(S.page(
            t, path=path, base=a.base,
            title=f"{name}{when} — {chamber_word} committee | Granite Record",
            og_title=f"{name}{when} — New Hampshire {chamber_word}",
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
        index.append({
            "code": code, "name": name, "chamber": chamber,
            "chair": rec["chair"], "n_members": len(members),
            "n_bills": sum(len(v) for v in rec["bills"].values()),
            "n_sessions": met_days,
            "terms": sorted(rec["bills"]),
            **({"formerly": [n["name"] for n in formerly]} if formerly else {}),
        })

    (site / "committees.json").write_text(json.dumps(index), encoding="utf-8")

    # The way in. Committee pages were built, sitemapped and unreachable: no
    # link to one existed anywhere on the site.
    _card = committee_card

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
        # By run, not first to last: H47, the House's special committee on
        # public employee pensions, sat in 2011-2012 and again in 2015-2016,
        # and "2011 to 2016" said it sat through the two years between.
        rec["archived"] = {"years": runs(c["span"])}
        f.write_text(json.dumps(rec), encoding="utf-8")
        # And its page stops naming a feed: shell.committee_followable, which
        # build_feeds asks too, says an archived committee has none.
        h = out / f"{c['code']}.html"
        if h.exists():
            h.write_text(h.read_text(encoding="utf-8").replace(
                "\n" + feed_link(c["code"], c["name"]), ""), encoding="utf-8")
    # A NUMBER THE GENERAL COURT GAVE TWO COMMITTEES. Its own records file the
    # Senate's Development, Recreation and Environment of 1989-1990 under S03,
    # the code they later gave the Senate's Appropriations, and the person
    # decided on 25 September 2026 that the two are different committees,
    # listed separately (committee_names.GAPS). So each has its own page, and
    # each page says plainly that it shares the number and names the other,
    # with the other's years: a reader who knows the code, or who came from a
    # bill-status page printing APPROPRIATIONS over a 1989 bill, is told they
    # are two committees rather than left to guess. Written after the fact,
    # like `archived`, because the years are the other page's record.
    for page, (gc, others) in shared_pages(CN.shared(), span_of, index).items():
        f = out / f"{page}.json"
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec["same_code"] = {"code": gc, "others": others}
        f.write_text(json.dumps(rec), encoding="utf-8")
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
        # THE CHAMBER ITSELF FIRST (the person, 9 and 10 October 2026): its
        # session days as a card like its committees', at the top of its
        # column. build_full_sessions.py fills the slot after the session
        # pages, whose term files it reads, are written -- so the column is
        # drawn for both chambers, with or without a committee sitting
        # today, because this step cannot know on an empty site whether the
        # chamber's card will fill it.
        cols.append(f"<section><h2>{word}</h2><div class=\"ccards\">"
                    + f"<!-- chamber:{ch} --><!-- /chamber:{ch} -->"
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
        # .fill: the note takes the width the cards under it take (F9).
        body.append('<h2>No bills or meetings on record</h2>'
                    '<p class="src fill">These committees have a roster, and in '
                    "some cases a chair, but no bill referred to them and no "
                    "meeting in the proceedings this site holds. Whether each "
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
                    '<p class="src fill">Committees on this record that the General '
                    "Court does not list among its committees now, with the "
                    "years their bills and meetings cover. The records "
                    "show when a committee stops appearing, not why&thinsp;&mdash;&thinsp;it may "
                    "have been renamed, divided, merged or ended&thinsp;&mdash;&thinsp;and this "
                    "page does not guess which. Where the General Court&rsquo;s "
                    "own records file one committee&rsquo;s bills under two "
                    "names, the card gives the earlier one. Each keeps its "
                    "page, so the bills it handled still have somewhere to "
                    "point.</p>"
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
                  # No Cite on a hub (D23, 8 October 2026).
                  nav_current="committees.html", sr_title="", cite=False)
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
    # WHAT HAPPENED AT EACH MEETING, said (committee_acts): nothing voted at
    # any meeting would be the docket's vote dates no longer read, and every
    # bill would read as heard and nothing more.
    unowned = sum(1 for k, own in owners_of.items() for a, o in zip(acts_of.get(k, []), own)
                  if o is None and a["act"] == "report")
    print(f"  at the meetings: {told['voted']:,} bills voted on, {told['heard']:,} heard, "
          f"{told['no vote']:,} with no vote dated that day, {told['worked']:,} worked on, "
          f"{told['scheduled']:,} still to come; {unowned:,} committee report(s) name a "
          "committee no page here holds")
    if sum(told.values()) and not told["voted"]:
        print("  WARNING: no meeting records a vote: committee_acts no longer reads the "
              "docket's report rows")
    if unmatched:
        print(f"  {len(unmatched)} committee name(s) in proceedings.csv match "
              f"no committee page, today's or a retired one's (the ceiling is "
              f"{UNMATCHED_CEILING}):")
        for nm, n in unmatched.most_common(6):
            print(f"    {nm!r} on {n:,} rows")
    empty = [i["code"] for i in index if not i["n_sessions"]]
    if empty:
        print(f"  {len(empty)} committee(s) have no sitting day on record: "
              + ", ".join(empty[:8]))
    if notices:
        print(f"  {len(notices)} docket notice(s) left off the committees' days, each "
              "for a bill its history tells as withdrawn before the day or never "
              "introduced, or for a day its history puts no sitting on: "
              + ", ".join(notices[:8])
              + (", ..." if len(notices) > 8 else ""))
    # SILENCE IS NOT SUCCESS: the pages are written, and the build stops here
    # if the names that reach none of them have grown past the ceiling.
    stop = unmatched_guard(unmatched)
    if stop:
        raise SystemExit(stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
