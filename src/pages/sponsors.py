#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
The members a bill's record names: its sponsors, each with the seat and the
party the term's Manual gives where the General Court's own record has none
(bill_sponsor_list, manual_seats, manual_parties, party_record), and the
members its docket names -- each ballot's voter (vote_member), a motion's
mover (mover_member, mover_pool), a committee report's author
(report_authors) and a member the story names (story_people).

    import sponsors as SP
    SP.bill_sponsor_list(bid, b, year, term, current, sponsors, legs, leg_by_sort,
                         leg_by_name, sponsored)   # [{"display_full", "slug", ...}]
    SP.manual_seats(pages)                     # the seats the Manuals of 1989-1998 print
    SP.vote_member(m, body, legs, unnamed)       # a ballot's member, labelled once
    SP.mover_member(mover, body, legs)           # the sitting member a docket's "Rep. X" means

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: sponsors and the Manual's seats). It
moved here as it stood, comments and all, from the kept labels of a ballot's
member (_VOTE_LABELS, vote_member) to bill_sponsor_list. It imports no
builder (_import_cycles_cut): how a member is named and the order of a
service are members.py's, the House Journal's source status.py's.
build_site_v2 imports every name here back under its own, so
build_site_v2.bill_sponsor_list and the rest answer as they did, for
bill_rollcalls, build_bills, main and the checks.
"""

import re
from collections import Counter, defaultdict, namedtuple

import member_links as ML
import past_sponsors as PSP
import proceedings as P
import spellings
import state_settings as ST
import text_sponsors as TS
from past_roster import MATCHED as PAST_ROSTER_MATCH
# How a member is named, the address of their page and a ballot's place in a service
# (members.py), and the status a bill takes from the House Journal (status.py).
from members import (PARTY_INITIALS, member_labels, member_slug, name_key, own_slug,
                     service_order, sort_name)
from status import JOURNAL_SOURCE


# ONE LABEL A NAME, CHAMBER AND PARTY (16 October 2026,
# private/SITE_DATA_PROFILE.md, P3). bill_rollcalls asks vote_member for each
# of 2.2 million ballots, and each asking ran member_labels -- person_name,
# sort_name and three patterns -- for the same few thousand people. The pair
# vote_member uses, the name drawn and the name sorted, depends only on the
# name it settles on, the chamber and the party, so the pair is kept by those
# three. The entry is built fresh around it on every call and the dict
# member_labels returns is never kept, so no caller can change what the next
# is given. The unnamed member is noted before the pair is looked up, so that
# every ballot naming nobody is noted, kept pair or not. A key no dict can hold
# is labelled afresh, as before.
_VOTE_LABELS = {}


def vote_member(m, body, legs, unnamed):
    """One member's entry in a roll call.

    This was nested inside build_bills and captured legs and unnamed from the
    enclosing scope; they are parameters now. unnamed is still mutated, which
    is why it is passed explicitly rather than quietly closed over.

    The name comes from the VOTE record, which build_data.py has already
    resolved against the roster and against former_members.json. The roster
    is the fallback rather than the source, because it holds sitting members
    only.

    Not "label": that field is a composite of name, party and seat, and the
    roll call grid wants a name.

    The party letter comes from the vote too, so the name agrees with the
    party segment the member is shown under.
    """
    raw = (m.get("name") or "").strip()
    if not raw or raw.lower().startswith(("member #", "former member")):
        rec = legs.get(m.get("member_id"), {})
        raw = (rec.get("name") or raw or "").strip()
    if not raw or raw.lower().startswith(("member #", "former member")):
        unnamed.add(str(m.get("member_id")))
        raw = f"Member #{m.get('member_id')}"
    chamber = legs.get(m.get("member_id"), {}).get("chamber") or body
    key = (raw, chamber, m.get("party"))
    try:
        display, sort = _VOTE_LABELS[key]
    except KeyError:
        lab = member_labels(raw, chamber=chamber, party=m.get("party"))
        display, sort = _VOTE_LABELS[key] = (lab["display"], lab["sort"] or sort_name(raw))
    except TypeError:
        lab = member_labels(raw, chamber=chamber, party=m.get("party"))
        display, sort = lab["display"], lab["sort"] or sort_name(raw)
    return {"n": display, "s": sort, "p": m.get("party") or "X", "v": m.get("vote")}


MOVER_HONORIFIC = re.compile(r"^(?:Rep|Sen|Representative|Senator)s?\.?\s+", re.I)
MOVER_SUFFIX = re.compile(r",?\s+(?:Jr|Sr|II|III|IV)\.?$", re.I)


_SPELLINGS = []


def _spellings():
    """member_corrections.json's spellings, read once a run."""
    if not _SPELLINGS:
        _SPELLINGS.append(spellings.load())
    return _SPELLINGS[0]


def mover_member(mover, body, legs, pages=None):
    """{"label", "slug"} of the one sitting member of `body` the docket's
    mover can mean -- "Rep. Alexander Jr." is Rep. Joe Alexander (R - Hills
    29), the only Alexander in the House -- or None where the name is no
    one's or more than one's. A WRONG LINK IS WORSE THAN NO LINK: a surname
    two members of the chamber share is left as the docket wrote it, and a
    full name ("Peter Schmidt") is tried before the surname alone.

    `legs` is the members the name is looked for among (mover_pool says
    which), and `pages` {id: member}, where given, whose page each of them
    links to now: `legs` is then a term's own roster as it was frozen, which
    gives the seat held in that term, and the link goes to the person's own
    page as it is now (own_slug), or nowhere where they have none. A member
    of term_voters' carries `held`, the seat of the term, which names them; a
    voter with no seat of the term is not linked."""
    n = MOVER_SUFFIX.sub("", MOVER_HONORIFIC.sub("", (mover or "").strip())).strip().strip(".")
    ch = (body or "").strip().upper()[:1]
    if not n or not ch:
        return None
    # A name the record misspells, as a person put it right (spellings.py):
    # "Rep. Poloszaj" is looked up as Ploszaj.
    n = spellings.respell(ch, n, _spellings())
    pool = []
    for m in (legs or {}).values():
        if (m.get("chamber") or "").strip().upper()[:1] != ch or "," not in (m.get("name") or ""):
            continue
        last, first = (x.strip() for x in m["name"].split(",", 1))
        pool.append((MOVER_SUFFIX.sub("", last).lower(), f"{first.split()[0] if first.split() else ''} "
                     f"{MOVER_SUFFIX.sub('', last)}".lower(), m))
    want = n.lower()
    cands = [m for _l, full, m in pool if full == want] or (
        [m for last, _f, m in pool if last == want] if " " not in want else [])
    if len(cands) != 1:
        return None
    m = cands[0]
    lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                        party=m.get("party_code") or m.get("party"), district=m.get("district"),
                        county=m.get("county"), county_abbr=m.get("county_abbr"))
    label = lab.get("display_full") or m.get("label") or ""
    # A TERM'S VOTER (term_voters) is named by the seat the term gives them,
    # and by no other: one with no seat of the term stays words.
    if "held" in m:
        label = m["held"]
        if not label:
            return None
    if pages is not None:
        page = pages.get(str(m.get("id") or ""))
        slug = own_slug(page) if page else ""
        return {"label": label, "slug": slug} if slug else None
    return {"label": label,
            "slug": m.get("slug") or member_slug(m, lab)}


# "(D - Rock 37)" at the end of a member's label: the party's letter.
_LABEL_PARTY = re.compile(r"\(([A-Z])\b[^()]*\)\s*$")


def report_author(author, body, legs, pages=None):
    """{"label", "slug", "party_code"} for the member a committee report says
    wrote it -- "Rep. David Meuse", "Senator Daryl Abbas" -- or None. A WRONG
    MEMBER IN A CHIP IS A FACTUAL ERROR AND A MISSING CHIP IS NOT: the name is
    taken only where mover_member finds exactly one member of the report's
    chamber it can mean, among `legs` and `pages` as mover_pool gives them
    (the term's own members, with the seat each held then), and only a name
    with its chamber's title; anything else stays the report's words. The
    party is the label's own, so the chip's colour is the seat's of the term."""
    said = (author or "").strip()
    if not MOVER_HONORIFIC.match(said):
        return None
    who = mover_member(said, body, legs, pages=pages)
    if not who or not who.get("label") or not who.get("slug"):
        return None
    m = _LABEL_PARTY.search(who["label"])
    return {**who, "party_code": m.group(1) if m else ""}


def report_authors(written, legs, pages=None):
    """Each written report's sides gain `author_m` (report_author) where the
    author can be named; a House Calendar report is the House's, a report
    that says "S" the Senate's."""
    for r in written or ():
        body = "S" if (r.get("body") or "").upper().startswith("S") else "H"
        for e in r.get("reports") or ():
            if e.get("author"):
                who = report_author(e["author"], body, legs, pages)
                if who:
                    e["author_m"] = who


def term_voters(votes_by_member, seats):
    """{term: {"<id>|<chamber>": member}}: THE MEMBERS OF EACH TERM'S CHAMBERS,
    AS THEIR OWN BALLOTS OF THE TERM GIVE THEM -- everyone who voted in that
    chamber that term, those who left mid-term and those who came in among
    them -- each with `held`, the seat the term gives them (term_seats, the
    seats a session day names them by), or "" where it gives none, or gives
    the other chamber's. For mover_pool, in the terms no frozen roster
    describes. The name and party are the term's last ballot's."""
    out = defaultdict(dict)
    for mid, rows in votes_by_member.items():
        mid = str(mid)
        for v in sorted(rows, key=service_order):
            body = (v.get("body") or "").strip().upper()[:1]
            if body not in ("H", "S") or "," not in str(v.get("name") or ""):
                continue
            t = P.vote_term(v["year"], v.get("date"))
            held = (seats.get(t) or {}).get(mid) or ""
            out[t][f"{mid}|{body}"] = {
                "id": mid, "name": v["name"], "chamber": body,
                "party_code": v.get("party") or "",
                "held": held if held.startswith(("Sen. " if body == "S" else "Rep. ")) else ""}
    return dict(out)


def mover_pool(term, current, legs, term_rosters, people, voters=None):
    """(members, pages) a mover of `term` is looked for among, for
    mover_member: THE TERM'S OWN MEMBERS, WITH THE SEAT EACH HELD IN IT
    (labels-use-the-seat-held-at-the-time). A term whose own roster is frozen
    and is not the sitting one (`term_rosters`, freeze_term.own_roster_terms)
    takes that roster, linked to each person's page as it is now (`people`,
    build_bills' every member and former member); the current term, while its
    roster is the sitting one, takes `legs`; a term before it, its own voters
    (`voters`, term_voters: the owner, 19 November 2026, "Yes, link them"),
    each named by the seat of the term and linked to the page their ballots
    are on (`people`); any other term -- 1989-1998, with no ballots -- nobody,
    and the docket's words stand.

    The rehearsal of the turn (19 November 2026): matched against the sitting
    roster for the current term alone, 2025-2026 lost the link on 843 movers
    of 647 bills the night 2027-2028 became the current term, and between
    Organization Day and the switch, with the next House installed and the
    term still current, a name would have been looked for among the next
    House, where a member who left at the election is nobody, or a newcomer
    who shares the surname."""
    if term in (term_rosters or {}):
        return term_rosters[term], people
    if term == current:
        return legs, None
    if term in (voters or {}):
        return voters[term], people
    return None, None


# A MEMBER NAMED IN THE STORY: "offered by Rep. Jane Smith", "Sen. Bradley
# moved". The honorific, then up to three capitalised words, tried longest
# first, so "Rep. Smith Amendment" falls back to "Rep. Smith".
STORY_PERSON = re.compile(r"\b(Rep|Sen)\.\s+((?:[A-Z][\w'\u2019.-]*)(?:\s+[A-Z][\w'\u2019.-]*){0,2})")


def story_people(texts, legs, pages=None):
    """[{"text", "label", "slug"}]: each member the story names as the docket
    did -- a mover, the member who offered an amendment -- where the words
    can mean one sitting member of that chamber (mover_member). The page
    links them where they stand (the person, 10 October 2026: "movers in
    story text not linked"). A WRONG LINK IS WORSE THAN NO LINK, so a name
    two members share stays words. `legs` and `pages` are mover_pool's, as
    for a roll call's mover."""
    out, seen = [], set()
    for text in texts:
        for m in STORY_PERSON.finditer(text or ""):
            hon, words = m.group(1), m.group(2).split()
            for k in range(len(words), 0, -1):
                said = f"{hon}. {' '.join(words[:k])}".rstrip(".,")
                if said in seen:
                    break
                who = mover_member(said, "H" if hon == "Rep" else "S", legs, pages=pages)
                if who and who.get("slug") and who.get("label"):
                    seen.add(said)
                    out.append({"text": said, **who})
                    break
    return out


def sponsor_record_chambers(sponsors, table="auto", people=None):
    """{(employee number, term): "H" | "S"}: the chamber the Manual for the General Court of
    the term seats a 1989-1998 sponsor in, for each row the General Court's sponsor record
    supplies itself (past_sponsors.filled) that is linked to a member, where the term's seat
    list names that one person and was read without doubt (past_roster.term_seat). For the
    member's "On Record" line: bill_sponsor_list's `ch`.

    A ROW OF THE RECORD HOLDS A CHAMBER AND NO SEAT, and before 1999 the chamber is the
    member's last (the review before the release of 16 November 2026): past_sponsors gives a
    row the chamber its number voted in that term, else the roster's, the legislators table's
    or the list of members', and no number voted before 1999. Measured for that review, on
    past_sponsors.json of 7 November, the Manual seated 402 of the 486 linked rows of those
    terms, each in the row's own chamber; the other 84 it does not name without doubt, and
    they keep their own. {} where no such row is linked to a member, or the seat list is not
    on this disk. `table` and `people` stand in for generated/manual_seats.json and the files
    past_sponsors.load_people reads."""
    import past_roster as PR
    want = {(str(s["employee"]), term) for term, s in sponsor_record_rows(sponsors)}
    table = (PR.seat_table() if table == "auto" else table) if want else None
    if not table:
        return {}
    people = people if people is not None else PSP.load_people(with_votes=False)
    out = {}
    for emp, term in sorted(want):
        seat, _why, _row = PR.term_seat(emp, term, people, table)
        if seat:
            out[(emp, term)] = seat[0]
    return out


def sponsor_record_rows(sponsors):
    """[(term, row)]: each 1989-1998 row the General Court's sponsor record supplies itself
    that is linked to a member and carries its employee number, the rows
    sponsor_record_chambers looks up in the term's Manual."""
    import past_roster as PR
    if not P.term_keyed(sponsors or {}):
        return []
    return [(term, s) for term in PR.PRE_TERMS
            for rows in (sponsors.get(term) or {}).values() for s in rows or ()
            if s.get("source") == PSP.SOURCE and s.get("employee") and s.get("member_id")]


def sponsor_record_said(sponsors, record_chambers):
    """What the build says of sponsor_record_chambers' answer, so that it never falls back in
    silence (the review before the release of 16 November 2026): how many it seated; that no
    seat list was read, where the record has rows to seat and none was; and how many rows the
    Manual seats in another chamber than the row's own, which their bill pages still name
    (bill_sponsor_list labels a row of the record by its own chamber; only `ch` takes the
    Manual's)."""
    rows = sponsor_record_rows(sponsors)
    out = []
    if record_chambers:
        out.append(f"  sponsors: {len(record_chambers):,} member-terms of 1989-1998 from the "
                   "General Court's sponsor record seated by that term's Manual, for the On "
                   "Record line")
    elif rows:
        out.append("  sponsors: no Manual seat list read; every 1989-1998 row of the General "
                   "Court's sponsor record keeps its own chamber")
    moved = sum(1 for term, s in rows
                if (record_chambers or {}).get((str(s["employee"]), term))
                not in (None, (s.get("chamber") or "")[:1]))
    if moved:
        out.append(f"  sponsors: {moved:,} 1989-1998 row(s) of the General Court's sponsor record "
                   "seated by the term's Manual in another chamber than the row's own; their "
                   "bill pages still name the row's own chamber")
    return out


def _manual_name_keys(name):
    """The surname keys past_roster._table_name_fits tests a seat list's full name by: its last
    word, and its last two run together where it has three or more (suffixes left out)."""
    w = [x for x in re.split(r"[\s,]+", name or "") if x and TS.letters(x) not in TS.SUFFIXES]
    if len(w) < 2:
        return set()
    return {TS.letters(w[-1])} | ({TS.letters(w[-2] + w[-1])} if len(w) > 2 else set())


def manual_seats(pages, links=None, sponsored=None, votes_by_member=None, table="auto",
                 people=None, counties=None):
    """THE TERMS OF 1989-1998 THE MANUAL FOR THE GENERAL COURT SEATS A MEMBER IN, whether or not
    they have a bill that term (the owner, 14 November 2026: "If we can address the manual gaps
    now, I'd rather just do it"). Francis Vincent's line read "House, 1989–1992, 1995–2000",
    and the 1993 Manual seats Francis C. Vincent at Strafford 14: his bills skip a term his
    seat does not.

    Returns ({page id: {chamber: [term]}}, [(page id, term, kind, words)]): for each member
    page, the terms the Manual seats them in that their 1989-1998 bills (`sponsored`, with the
    `ch` bill_sponsor_list gives) do not show, each in the Manual's chamber; and every seat
    left out, and why. The terms from 1999 on are the roll calls' and are not touched.

    A SEAT COUNTS where past_roster.term_seat -- the call sponsor_record_chambers makes --
    seats one of the member's own General Court numbers without doubt: one person of that full
    name in the term's list, its row read cleanly. A member's numbers are the employee numbers
    whose site id (the PersonID the legislators table gives a number, else the number) is the
    page's own or one joined to it (`links`).

    AND NEVER, AS FAR AS THE RECORD CAN TELL, ANOTHER PERSON'S. Left out, and said:
      - "doubtful": term_seat's own doubt (two people of that full name in the term's list, a
        row not read cleanly), or the member's numbers seated at two seats, or doubted, in the
        same term;
      - "perhaps another person": another number of the General Court's list has the same full
        name; the Manual's House seat is in a county the member's own record does not name; its
        chamber is one the member's record has nowhere (their numbers, their votes, their bills,
        their page); or their bills of that term print the other chamber.
    A term their bills of the same chamber already show adds nothing. `table`, `people` and
    `counties` ({number: county}) stand in for generated/manual_seats.json and the files
    past_sponsors.load_people and past_members.roster read."""
    import past_roster as PR
    import past_members as PM
    table = PR.seat_table() if table == "auto" else table
    if not pages:
        return {}, []
    if not table:
        return {}, [(None, None, "unread", "no Manual seat list read")]
    people = people if people is not None else PSP.load_people(with_votes=False)
    if counties is None:
        counties = {e: r.get("county") or "" for e, r in PM.roster(PSP.PAST_MEMBERS).items()}
    abbr = lambda c: ST.COUNTY_ABBR.get(c or "", c or "")
    by_site, by_key = defaultdict(set), defaultdict(set)
    for e in people.pm:
        by_site[str(people.vid(e))].add(e)
        for k in people.surnames(e):
            by_key[k].add(e)
    term_keys = {t: {k for _c, r in PR._manual_rows(table, t) for k in _manual_name_keys(r.get("name"))}
                 for t in PR.PRE_TERMS}
    seat_words = lambda s: (f"Senate district {s[2]}" if s[0] == "S"
                            else f"House {s[1].title()} {s[2]}")
    out, left = {}, []
    for pid, m in pages.items():
        ids = [str(pid), *(str(x) for x in (links or {}).get(pid, []))]
        nums = set().union(*(by_site.get(i, set()) for i in ids))
        if not nums:
            continue
        bills = ML.earlier_terms((sponsored or {}).get(pid, []))
        bill_ch = defaultdict(set)
        for ch, ts in bills.items():
            for t in ts:
                bill_ch[t].add(ch)
        known_ch = ({str(m.get("chamber") or "")[:1]} | {people.pm[e][0] for e in nums} | set(bills)
                    | {v.get("body") for i in ids for v in (votes_by_member or {}).get(i, ())})
        known_co = {abbr(m.get("county")), m.get("county_abbr") or ""} | {abbr(counties.get(e))
                                                                          for e in nums}
        known_co.discard("")
        for term in PR.PRE_TERMS:
            seats, doubts = {}, []
            for e in sorted(nums):
                if not people.surnames(e) & term_keys[term]:
                    continue
                seat, why, row = PR.term_seat(e, term, people, table)
                if seat:
                    seats[e] = (seat, row)
                elif not why.startswith("no person"):
                    doubts.append(f"{why} (number {e})")
            if not seats:
                left += [(pid, term, "doubtful", d) for d in doubts]
                continue
            if doubts or len({s for s, _r in seats.values()}) > 1:
                left.append((pid, term, "doubtful", "; ".join(
                    doubts + [f"number {e} at {seat_words(s)}" for e, (s, _r) in sorted(seats.items())])))
                continue
            e, (seat, row) = sorted(seats.items())[0]
            ch, at = seat[0], seat_words(seat)
            others = sorted(x for k in _manual_name_keys(row.get("name")) for x in by_key.get(k, ())
                            if x not in nums and PR._table_name_fits(row.get("name"), x, people))
            why = ""
            if others:
                why = (f"number {others[0]} of the General Court's list has the full name "
                       f"{row.get('name')!r} too")
            elif ch == "H" and known_co and abbr(row.get("county")) not in known_co:
                why = (f"{at} is in a county the member's record does not name "
                       f"({', '.join(sorted(known_co))})")
            elif ch not in known_ch:
                why = f"the member's record has no {'Senate' if ch == 'S' else 'House'} anywhere"
            elif bill_ch.get(term) and ch not in bill_ch[term]:
                why = f"their bills of {term} print the other chamber"
            if why:
                left.append((pid, term, "perhaps another person", f"{row.get('name')} at {at}: {why}"))
            elif not bill_ch.get(term):
                out.setdefault(pid, {}).setdefault(ch, []).append(term)
    return {k: {ch: sorted(ts) for ch, ts in sorted(v.items())} for k, v in out.items()}, left


def manual_said(manual, left):
    """What the build says of manual_seats' answer: how many pages gain how many terms, and how
    many seats were left out, by why; or that no seat list was read -- never in silence."""
    if any(k == "unread" for _p, _t, k, _w in left):
        return ["  members: no Manual seat list read; the 1989-1998 terms on record are their "
                "bills' alone"]
    n = sum(len(ts) for v in manual.values() for ts in v.values())
    kinds = Counter(k for _p, _t, k, _w in left)
    return [f"  members: {len(manual):,} page(s) take {n:,} term(s) of 1989-1998 their Manual "
            "for the General Court seats them in, with no bill that term"
            + (f"; left out: {', '.join(f'{v:,} {k}' for k, v in sorted(kinds.items()))}"
               if kinds else "")]


# ------------------------------------------------------- the party of a 1989-1998 sponsor

# The party letters the Manual for the General Court's returns print for a candidate of one
# party (build_manual_seats.PARTY). A line of two or three ("d&r", "r&d&l") is a candidate
# more than one party nominated, and names no one party. Read by the state's one table of
# parties, whole: "d&r" is no form of it.
MANUAL_PARTY = ST.party_lookup()


def party_letter(party):
    """The letter a chip and a label draw for `party` -- "R" for "R", "r" or "Republican" -- as
    member_labels draws it: the first letter, where it is one of PARTY_INITIALS; else ""."""
    pc = (party or "").strip()[:1].upper()
    return pc if pc in PARTY_INITIALS else ""


# What the records give as a person's party, for early_party -- party_ids keys it by the ids
# the records use, party_record by the page each id reaches: `person`, {id: {party letter}},
# every party any record of them gives; `term`, {(id, term): {party letter}}, the party each
# 1989-1998 term's Manual for the General Court prints beside their name, where the line names
# one party (manual_parties).
Parties = namedtuple("Parties", "person term")


def early_party(page, record, term=""):
    """THE PARTY ON THE CHIP OF A 1989-1998 SPONSOR PLACED ON A PERSON WITH A PAGE.

    THE OWNER'S DECISIONS, both of 15 November 2026:
      - show on their 1989-1998 chips the party the person's own page gives, and leave it off
        for anyone the record shows in more than one party;
      - and, for a person the record shows in more than one party, a bill of 1989-1998 shows
        the party that bill's term's Manual for the General Court gives them (the general
        election's returns), where it settles the term with a single letter. A
        cross-nomination ("d&r") settles nothing, and a term the Manual does not seat them in
        gives nothing: no party for that term.
    No roll call of 1989-1998 is on this site, so no sponsor row of those years carries a party
    of its own -- the bill's own sponsor rows place the printed name (past_roster.py), or the
    General Court's sponsor record supplies the list (past_sponsors.filled) -- and Rep. Donna
    Sytek, R on her page, was drawn with no party on the 34 bills of 1993-1994 she is prime
    sponsor of. The page's party is today's. It is said of 1993 only where nothing the site holds
    of the person says otherwise; where something does, only the term's own Manual speaks for
    that term.

    `page` is the member record the row is placed on (bill_sponsor_list's `_m`), `term` the
    bill's term. `record` is party_record's Parties: in `person`, the parties of the labels and
    chips of their bills of 1999-2026, their ballots, the legislators table's party
    (generated/careers.json) and every term's Manual; in `term`, each term's Manual on its own
    (manual_parties). Measured on the live site and these files on 15 November 2026: 343 of the
    353 people with a page on 1989-1998 bills give one party, and their Manual lines agree with
    it by construction; Michael Downing's own bills give two (D in 1999-2000, R from 2007), and
    nine more give two only by a Manual -- Steve Vaillancourt, R on his page, is a Democrat in
    the 1997 Manual's returns, and so his 1997-1998 bills read D.

    Returns a party letter, or "": where the row is placed on no page (the people who served
    only before 1999 have none, and keep no party and no link), where the page gives no party
    and no record another, where the record shows two parties and the term's Manual names none
    of its own, and where no record was read at all (`record` None), since then nothing can say
    the person was of one party. The seat is never this function's: it stays the one the bill
    printed."""
    if record is None or not (page or {}).get("id"):
        return ""
    pid = str(page["id"])
    own = party_letter(page.get("party_code") or page.get("party"))
    if len({own, *record.person.get(pid, ())} - {""}) <= 1:
        return own
    got = record.term.get((pid, term)) or set()
    return min(got) if len(got) == 1 else ""


def manual_parties(table="auto", people=None):
    """{site id: {term: {party letter}}}: the party the general election's returns print, in the
    Manual for the General Court of each 1989-1998 term (generated/manual_seats.json), for the
    one person of a number's full name the term's seat list holds -- the row
    past_roster.term_seat joins the number to -- for every number the General Court's list of
    members names, keyed by the id the number's ballots are cast under
    (past_sponsors.People.vid). For early_party, as the record of the person's party in that
    term; a term with two letters (two numbers of one person seated apart) settles none.

    A row term_seat calls unclean still counts: its doubt is about the seat (a mark, a district
    count), not the party printed beside the name. A line of two nominations ("d&r") names no one
    party and counts for nothing, and so does a term whose list holds nobody, or two people, of
    that full name. None where the seat list is not on this disk.

    Each number is held only to the rows its own surnames could fit (_manual_name_keys: a row
    _table_name_fits fits carries one of the number's surnames as one of its keys), which is
    term_seat's answer over the whole list at a fraction of its cost -- 16 ms a call over a
    term's 424 rows. `table` and `people` stand in for generated/manual_seats.json and the files
    past_sponsors.load_people reads."""
    import past_roster as PR
    table = PR.seat_table() if table == "auto" else table
    if not table:
        return None
    people = people if people is not None else PSP.load_people(with_votes=False)
    near_rows = {}
    for term in PR.PRE_TERMS:
        k = defaultdict(dict)
        for ch, r in PR._manual_rows(table, term):
            for key in _manual_name_keys(r.get("name")):
                k[key][id(r)] = (ch, r)
        near_rows[term] = k
    out = defaultdict(lambda: defaultdict(set))
    for e in sorted(people.pm):
        keys = people.surnames(e)
        for term in PR.PRE_TERMS:
            near = {}
            for key in keys:
                near.update(near_rows[term].get(key) or {})
            if not near:
                continue
            one = {"terms": {term: {"house": [r for ch, r in near.values() if ch == "H"],
                                    "senate": [r for ch, r in near.values() if ch == "S"]}}}
            _seat, _why, row = PR.term_seat(e, term, people, one)
            p = MANUAL_PARTY.get(str((row or {}).get("party") or "").strip().lower(), "")
            if p:
                out[str(people.vid(e))][term].add(p)
    return {i: dict(ts) for i, ts in out.items()}


def party_ids(votes_by_member=None, careers=None, manual=None):
    """Parties keyed by the ids the records use, for party_record. `person`: the party of every
    ballot cast under an id (votes_by_member), the legislators table's party for each id
    generated/careers.json joins to a person (their PersonID and each of their employee
    numbers), and every party manual_parties' answer (`manual`) gives the id in any term.
    `term`: that answer, term by term."""
    out, by_term = defaultdict(set), {}
    for mid, vs in (votes_by_member or {}).items():
        got = {party_letter(p) for p in {v.get("party") for v in vs}} - {""}
        if got:
            out[str(mid)] |= got
    for key, c in (careers or {}).items():
        p = party_letter((c or {}).get("party"))
        if p:
            for i in {str(key), str(c.get("person_id") or ""), *map(str, c.get("employee_nos") or ())}:
                if i:
                    out[i].add(p)
    for i, terms in (manual or {}).items():
        for t, ps in terms.items():
            out[str(i)] |= set(ps)
            by_term[(str(i), t)] = set(ps)
    return Parties(dict(out), by_term)


def party_record(people, labelled=None, ids=None):
    """Parties keyed by page id, for early_party: each party a record of the person gives, and
    the Manual's term by term. The labels and chips of their bills of 1999-2026 (`labelled`,
    keyed by page id already, as bill_sponsor_list draws them), and party_ids' answer (`ids`),
    each id joined to the page it reaches through `people` -- build_bills' `_people`, the lookup
    that places a sponsor row on a page, so a record of an earlier number reaches the page that
    number's bills link to, and two numbers of one person seated apart in a term give that term
    two letters."""
    out, by_term = defaultdict(set), defaultdict(set)
    ids = ids or Parties({}, {})
    for pid, ps in (labelled or {}).items():
        out[str(pid)] |= set(ps) - {""}
    for i, ps in ids.person.items():
        page = people.get(str(i)) or {}
        if page.get("id"):
            out[str(page["id"])] |= set(ps) - {""}
    for (i, t), ps in ids.term.items():
        page = people.get(str(i)) or {}
        if page.get("id"):
            by_term[(str(page["id"]), t)] |= set(ps) - {""}
    return Parties(dict(out), dict(by_term))


def early_party_said(sponsored, people, record):
    """What the build says of early_party's answer, so it never falls back in silence: how many
    people with a page take its party on how many of their 1989-1998 bills; and each the record
    shows in more than one party, with the parties and, term by term, the Manual's party their
    bills of that term take (early_party), or none, and on how many. [] where no 1989-1998 bill
    is filed under a page, or no record was read."""
    took, bills_, two = 0, 0, []
    for pid in sorted(sponsored or {}):
        terms = Counter(str(x.get("term") or "") for x in sponsored[pid]
                        if str(x.get("term") or "")[:4] < "1999")
        page = (people or {}).get(str(pid)) or {}
        if record is None or not terms or not page.get("id"):
            continue
        own = party_letter(page.get("party_code") or page.get("party"))
        seen = sorted({own, *record.person.get(str(page["id"]), ())} - {""})
        if len(seen) <= 1:
            if own:
                took, bills_ = took + 1, bills_ + sum(terms.values())
            continue
        two.append((page.get("name") or pid, seen,
                    [(t, early_party(page, record, t), n) for t, n in sorted(terms.items())]))
    if not (took or two):
        return []
    out = [f"  sponsors: {took:,} people with a page take its party on {bills_:,} of their "
           "1989-1998 bills (early_party)"]
    if two:
        given = sum(n for _w, _s, ts in two for _t, p, n in ts if p)
        none = sum(n for _w, _s, ts in two for _t, p, n in ts if not p)
        out.append(f"  sponsors: {len(two):,} the record shows in more than one party take the party "
                   f"their bill's term's Manual gives on {given:,} bills and none on {none:,}: "
                   + "; ".join(f"{w} ({', '.join(s)}): "
                               + ", ".join(f"{t} {p or 'none'} on {n:,}" for t, p, n in ts)
                               for w, s, ts in two))
    return out


def bill_sponsor_list(bid, b, year, term, current, sponsors, legs,
                      leg_by_sort, leg_by_name, sponsored, seats=None, left=None,
                      term_roster=None, record_chambers=None, labelled=None,
                      parties=None):
    """Who put their name to this bill, and their own bill list, both.

    It mutates `sponsored`, which is the caller's accumulator of what
    each member has sponsored, the same way vote_member mutates
    `unnamed`. That is why it is passed explicitly rather than closed
    over: a function that changes something belonging to its caller
    should say so in its signature.

    `left` is ({sort name: [member]}, {name key: [member]}) of the members
    who hold no seat now, and `term_roster` {id: member} the term's own
    roster as it was frozen, both passed only for a term whose frozen roster
    is not the sitting one (build_bills says which); None everywhere else,
    which is every term before the first Organization Day.

    `record_chambers` is sponsor_record_chambers': the chamber the term's
    Manual seats a 1989-1998 sponsor of the General Court's record in.

    `parties` is party_record's Parties, from which a 1989-1998 row placed
    on a page takes that page's party, or the bill's term's Manual's for a
    person of two parties (early_party); None gives it none. `labelled`,
    where given, is filled with the party letters this list's labels and
    chips draw for each page on a bill of 1999 on -- build_bills reads those
    first, for `parties`.

    `prime` stays in the loop. It is one line and it reads better
    beside the payload that uses it than as an extra return value.
    """
    sp_list, filed = [], set()
    for _s in P.per_term(sponsors, term, current).get(bid, []):
        _m = legs.get(_s.get("member_id"))
        if not _m:
            _m = (leg_by_sort.get(sort_name(_s.get("name") or ""))
                  or leg_by_name.get(name_key(_s.get("name") or "") or ("", "")))
            # A NAME IS A PERSON ONLY WHERE THAT PERSON SAT. A record matched on
            # its name alone is the member only if they held a seat in that
            # chamber that term (member_links.seats_held); otherwise it is
            # somebody else of the same name, and stays unlinked the way a
            # former member does. When it was added it turned nobody away.
            ch = (_s.get("chamber") or "")[:1]
            if _m and seats is not None and not any(
                    t == term and (not ch or c == ch)
                    for t, c in seats.get(str(_m.get("id")), ())):
                _m = None
            # A FINISHED TERM'S MEMBERS WHO HOLD NO SEAT NOW (5 October 2026).
            # While 2025-2026 was the session's, this name fell back on the
            # roster, which was that term's. After the turn the roster is the
            # next House, and on the rehearsal of the turn 900 sponsor names
            # on 491 of the term's bills -- a third of the House, gone at the
            # election -- lost their link and read their seat as the record
            # pads it ("Belk 07"), though each of them has a page under
            # `former`. So for a term frozen and finished (`left`), a name
            # the sitting roster does not answer is looked for among those
            # members too, under the same rule: only one who sat in that
            # chamber that term.
            if not _m and left:
                for _f in (*left[0].get(sort_name(_s.get("name") or ""), ()),
                           *left[1].get(name_key(_s.get("name") or "") or ("", ""), ())):
                    if seats is None or any(
                            t == term and (not ch or c == ch)
                            for t, c in seats.get(str(_f.get("id")), ())):
                        _m = _f
                        break
        _m = _m or {}
        # The roster first, then whatever the sponsor record carries in
        # its own right. build_data fills the county and district in for a
        # member who has left, from former_members.json, so that they are
        # named the same way as anyone else: "Rep. Suzanne Vail (D - Hills
        # 6)", not a bare name under a heading about a missing chamber.
        #
        # EXCEPT A SPONSOR READ OFF THE BILL'S TEXT, which carries the seat the
        # text printed and the party of that term's roll calls -- the seat they
        # held when they signed it. Built from the roster, 2023 HB 25's "Rep.
        # McConkey, Carr. 8" read "Sen. Mark McConkey (R - SD3)" under the
        # heading Representatives, and every House bill of a member now in the
        # Senate would have done the same. The link still goes to their page.
        # ... or whose seat was dated from it: seat_into puts the bill's own
        # printed chamber, county and district on a database sponsor, and the
        # roster must not then be preferred over the thing that corrected it.
        # ... AND A ROW WHOSE SEAT IS ITS OWN RECORD'S AND NOTHING ELSE'S: the
        # General Court's sponsor record filling a bill no other source names
        # a sponsor for (past_sponsors.filled), which holds a chamber and no
        # district, and the House Journal's list on a bill of a past term
        # (build_data.journal_sponsor_rows), which prints the seat of the
        # day. Neither takes a seat from the roster: a 1993 bill's sponsor
        # who sits in the Senate today was drawn "Sen." at today's district.
        # One with no party on that term's ballots is given none -- save a
        # 1989-1998 row placed on a page, below.
        #
        # AND A TERM WHOSE OWN ROSTER IS FROZEN (`term_roster`, the review of
        # 5 October 2026): its member as that roster has them, the seat they
        # sat in, before the record of whoever they are today. After the turn
        # `_m` is the sitting record, and a Representative elected to the
        # Senate under a new id is joined to it by member_links: all 93 of
        # Rep. Sabourin dit Choinière's 2025-2026 bills would have read "Sen.
        # ... (R - SD23)". The link still goes to their own page, through `_m`.
        _t = ((term_roster or {}).get(str(_s.get("member_id") or ""))
              or (term_roster or {}).get(str(_m.get("id") or "")) or _m)
        # ... AND A 1989-1998 SPONSOR PLACED BY THE BILL'S OWN SPONSOR ROWS
        # (past_roster.py), or supplied by the record itself: the seat is the
        # one the bill printed, and the party the person's own page gives,
        # where every record of them gives that one party; where a record
        # gives another, the party the bill's term's Manual gives them, where
        # it names one; and none where it does not, or there is no page
        # (early_party: the owner's decisions, 15 November 2026). The row has
        # none of its own; the page's is said of 1993 only where nothing the
        # site holds says otherwise.
        _gave = ""
        if (_s.get("seat_source") in (PSP.SOURCE, JOURNAL_SOURCE)
                or _s.get("matched") == PAST_ROSTER_MATCH):
            if not _s.get("party") and term[:4] < "1999":
                _gave = early_party(_m, parties, term)
            _party = _s.get("party") or _gave
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber") or _m.get("chamber"),
                party=_party,
                district=_s.get("district"), county=_s.get("county"))
        elif _s.get("source") == TS.SOURCE or _s.get("seat_source") == TS.SOURCE:
            _party = _s.get("party") or _t.get("party_code")
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber") or _t.get("chamber"),
                party=_party,
                district=_s.get("district") or _t.get("district"),
                county=_s.get("county") or _t.get("county"),
                county_abbr=None if _s.get("district") else _t.get("county_abbr"))
        elif ((_s.get("chamber") or "")[:1].upper() in ("H", "S")
              and (_t.get("chamber") or "")[:1].upper() in ("H", "S")
              and (_s.get("chamber") or "")[:1].upper() != (_t.get("chamber") or "")[:1].upper()
              and _s.get("district")):
            # THE SEAT THE RECORD PRINTS, WHERE THE MEMBER HAS SINCE MOVED
            # CHAMBER (9 November 2026): a bill filed as Rep. for Grafton 1 reads
            # so, linked to the page the member has now as a senator.
            _party = _s.get("party") or _t.get("party_code")
            _lab = member_labels(
                _s.get("name"),
                chamber=_s.get("chamber"),
                party=_party,
                district=_s.get("district"), county=_s.get("county"))
        else:
            _party = _t.get("party_code") or _s.get("party")
            _lab = member_labels(
                _s.get("name"),
                chamber=_t.get("chamber") or _s.get("chamber"),
                party=_party,
                district=_t.get("district") or _s.get("district"),
                county=_t.get("county") or _s.get("county"),
                county_abbr=_t.get("county_abbr"))
        # The address of this member's own page, where the sponsor was
        # matched to the roster. Where they were not -- a former member,
        # or a name the join missed -- there is no page and no link, which
        # is the honest outcome rather than a link that goes nowhere.
        # The member's OWN address, not one derived from the label above --
        # own_slug says why that distinction is not cosmetic.
        _slug = own_slug(_m) if _m.get("id") else ""
        # The party given (early_party) is the row's too, so that the chip on
        # the bill's Sponsors tab, the card's (the index row's sponsor_party)
        # and the bill search's party filter read the party the label does.
        sp_list.append({**_s, **_lab, "slug": _slug, **({"party": _gave} if _gave else {})})
        # WHAT A PAGE'S BILLS OF 1999 ON DRAW THEM WITH, for early_party: the
        # label's party and the row's own, which the chip and the card read.
        if labelled is not None and _m.get("id") and term[:4] >= "1999":
            labelled.setdefault(str(_m["id"]), set()).update(
                {party_letter(_party), party_letter(_s.get("party"))} - {""})
        # FILED UNDER THE MEMBER THE PAGE LINKS. This used the record's own id,
        # and every 2023-2024 record, with 4,569 of 2025-2026's, carries an
        # employee number or none: 349 of 406 members' Sponsored tabs missed
        # 11,855 bills their bill pages credited them with. A record matched to
        # nobody keeps its own id, as before; one member twice on a bill is
        # filed once.
        _mid = str(_m.get("id") or _s.get("member_id") or "")
        if _mid and _mid not in filed:
            filed.add(_mid)
            # THE CHAMBER OF A 1989-1998 TERM THE GENERAL COURT'S SPONSOR RECORD PUTS THIS
            # PERSON IN, for their "On Record" line (ML.earlier_terms), on every such row: the
            # line covers the terms the TERM picker lists, and the picker lists them all. Only
            # the printed rows had one, and Donna Sytek, Speaker in 1997-1998, whose bills of
            # that term are all the record's own rows, read "House, 1989–1996, 1999–2000" (the
            # review before the release of 16 November 2026). A sponsor the bill printed and
            # its sponsor rows placed (past_roster.py) takes the chamber the bill printed; a
            # row the record supplies itself (past_sponsors.filled), the chamber the term's
            # Manual seats them in (sponsor_record_chambers), else the row's own.
            # build_legislators takes it out again.
            if _s.get("matched") == PAST_ROSTER_MATCH:
                _ch = (_s.get("chamber") or "")[:1]
            elif _s.get("source") == PSP.SOURCE and term[:4] < "1999":
                _ch = ((record_chambers or {}).get((str(_s.get("employee") or ""), term))
                       or (_s.get("chamber") or "")[:1])
            else:
                _ch = ""
            sponsored[_mid].append({
                "bill": bid, "n": b.get("designation") or bid,
                "title": b.get("title", ""), "year": year, "term": term,
                "prime": bool(_s.get("prime")),
                **({"ch": _ch} if _ch else {})})
    return sp_list
