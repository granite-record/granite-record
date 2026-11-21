#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-10.16
"""
Each member's Elections tab: the general elections on file in which the member
is recorded, newest first (the owner's design of 10 November 2026,
reports/design-elections-tab.md, approved with its defaults).

    python3 src/pages/build_member_elections.py --site site [--collected collected]
                                                [--report reports/elections_uncertain.md]

WHAT IT DOES. After build_elections.py, it adds an "elections" list to the
member's own file, site/legislators/<id>.json, which app.js draws the tab from
(a member with no row gets no key, and so no tab). Nothing else is written
but the report below. A key it wrote on an earlier run and no longer has a
row for is removed, so a rerun never leaves a stale one. No page, no
sitemap entry and no file is added to the deploy.

WHAT IT READS. The same things build_elections.py reads, and decides nothing
about who won: collected/election_<year>.json; the roster files; the owner's
corrections/members_elect.json (read, never written); and, for each election,
build_elections.decided(), which is build_members_elect.members_elect, the one
rule for who is elected, final or not, and whom a winner is.

THE MATCHING (the owner's approval of 10 November 2026):

  A WIN is the elections page's own: the winner members_elect links to a
  member by id. No second matcher is written here.

  A LOSS carries no person number, and is shown on a member's tab only where
  it is certain: the candidate's name, read first name first
  (build_members_elect.reading_order), is the member's name letter for
  letter, AND the race is a seat the member held in the term before or after
  that election. The roster holds one seat for each member -- a sitting
  member's, for the newest term, and a former member's, for the last term they
  served -- so "held" is that seat, in that term. The owner's
  corrections/members_elect.json "matches" for the race and the printed name
  settles it either way: an id shows the race on that member's tab, null keeps
  it off.

  A MIDDLE INITIAL ON ONE SIDE ONLY (the owner's report of 20 November 2026:
  the 2026 primary prints "Wayne M. Burton", the roster "Burton, Wayne", and
  his Strafford 10 card marked his two colleagues and not him). Where no
  member has the name letter for letter, the bill requests' matcher decides
  whether the two names can be one person (build_lsrs.compatible: the same
  surname, the same first name or a pair its NICKNAMES tables, a middle name
  only where one side has none and the other's is an initial) -- and the rest
  must be certain: the very seat held in the term before or after, the party
  the candidate filed under where both give one, a suffix that agrees, no
  other candidate in the race of the member's surname, and one member only
  (Roster.initial_match). A general's candidates and a primary's are read so;
  a special's are not: THE SPECIAL ELECTIONS, below, sends a middle initial
  to the owner's list, and widening that is hers to say.

  TWO FORMS OF ONE NAME THE OWNER TIED (20 November 2026: "Marty Jack and
  Michael Costable can be linked"). A printed name the owner's
  corrections/name_forms.json gives a form for is read as that form
  (Roster's `forms`, build_lsrs.name_forms, the file the bill requests'
  matcher reads): "Marty Jack" as "Martin Jack", "Michael Costable Jr." as
  "Michael Costable". The rest of the rule is unchanged -- the very seat held
  in the term before or after, one member only -- so the file ties a name,
  never a race.

  The same rule reads a race that is not final -- all of them, until the
  recount deadline has passed -- because members_elect draws no winner for
  one, and a winner it does not draw has no link to take. A winner it DOES
  draw and cannot link is left alone: that is its refusal, and a name match
  here must not override it.

  THE SEAT IN EACH TERM (10 November 2026). "The seat the member held" is the
  seat they printed on a bill of that term (text_sponsors.json, through
  build_members_elect.seat_history), with the roster's one seat for the term it
  belongs to, so that a former member of 2016 is matched to the seat they held
  in 2017-2018. A seat of a term on the 2012 districts is no evidence for an
  election held on the 2022 ones (build_members_elect.on_this_map).

  THE 2016-2022 HOUSE FILES PRINT A SURNAME ONLY, so "the same name" cannot be
  asked of them. A loss there is shown only on the weaker match this module
  says so about: the surname, the very seat held in the term before or after,
  the party where both give one, and no other candidate of the surname in the
  race (Roster.surname_match). A win there is linked by the elections page's own
  matching, which for these years is the seat held (by_history).

  Never a looser string match. A candidate who could be a member and is not
  certain is not shown; the report names the race, the printed name, the likely
  member and why it is not certain, for the owner to settle in the hand file.

WHAT A ROW SAYS. The race as it was that year (its key: chamber, county and
district, seats, floterial), the result in the elections page's own words, the
member's votes, and -- for a race of one seat -- the share of every vote cast
in it, write-ins included, as the elections page does; a race of more than one
seat gives none, because a voter could choose several. The place among the
candidates. A race whose winner the owner holds back has neither. Where a race
is a recount's, the row says so; the first count is not on file. And "c", the
race's card as the elections page draws it (build_elections.race_card, the
same function), with the member's own row marked, which is what the tab
draws (the owner, 18 November 2026), its margin's label and figures with it
(build_elections.margin_chip, election_margin.py's one rule, 19 November
2026); the fields above stay for a reader of the JSON and for a row with no
card.

THE PRIMARIES (the owner, 19 November 2026). collected/primary_<year>.json
(src/parse/parse_sos_primary_results.py) is read too: a member's candidacy on
their own party's ballot is a row ("st": "primary", "pp": the party), matched
by the same certain rule as a loss above, never by the hand file (its matches
are the general's), and never on another party's ballot: the votes a file
lists for another party's candidates are left off the card and said in its
note. Each leader, as many as the seats, is marked "Nominated" (the owner,
20 November 2026; "Most votes" until then); the label has no letter. A
nominee placed by that rule links to their page, as a general's winner does,
and a candidate who lost links nowhere, as on a general's card
(nominee_links; the owner, 20 November 2026).
A race with no more candidates than seats is a card too, labelled Unopposed.

THE SPECIAL ELECTIONS (the owner, 19 November 2026, "Yes to all 9" of
reports/money-specials-design/specials-and-upcoming.md, A2 and A5).
collected/specials.json (src/parse/parse_sos_specials.py, read from the
Secretary of State's pages) is read too: each special a card ("st":
"special"), and each of its party primaries one ("st": "special-primary",
"pp" the party), by the same race_card and margin. A member is linked only on
the certain rule above, around the term the special fills: the name theirs
letter for letter and the seat theirs in that term or the one before or after
on the same lines (special_window, which says why the winner's rule is no
narrower). A middle initial the
roster does not carry is not the same name: such a winner goes to the
owner's list, never a looser match. Each row carries "cy", the cycle of the
general that elected the term whose seat it fills, and "u", the
Secretary of State's page; a tie's re-run "tie" (the tied year and the House
resolution). Nothing is said of whom a winner replaced: no page says (A5.5).
Nobody on a special's card is marked an incumbent: held_on is of a general
election's term.

THE ORDER (the owner, 19 November 2026): strictly newest first, under a
heading for each election cycle (app.js), a cycle's general and then its
primary; one column of cards. A special is under the cycle of the term whose
seat it fills, by its day (A5.4): the March 2026 special under 2024, above
that cycle's general, its primary under it.

UPCOMING ELECTIONS, ONLY FOR A MEMBER WHO HAS FILED (the owner, 19 November
2026: "Upcoming elections doesn't need to be included on members pages unless
they have actually filed to run again in 2028"; the dates themselves are on the
Calendar and the elections page, key_dates.election_dates). "up" in the
member's own file, which app.js draws above the newest cycle: the race the
member filed for, and the next state general election's filing period, primary
and general still ahead, each a day key_dates works out from the text of the
law in force on it (RSA 655:14, 653:8, 653:7) and cites. Written only for a
member with a filing on record in collected/filings_<year>.json
(filings_on_file, which says the file's shape) and a row on the tab. No such
file is on disk: the Secretary of State's filing lists are published from the
filing period (March 2028) and a later step is to read them. Until then no tab
has the card. A new member-elect's provisional page is held to the same
(build_elect_pages).

Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import unicodedata
from collections import defaultdict

import build_date
import build_elections as BE
import build_lsrs as BL
import build_members_elect as BME
import key_dates as KD

# The tab's rows are kept to what the page draws; the rest is in the race's card.
REPORT_DEFAULT = Path("reports") / "elections_uncertain.md"


def nfc_fold(name):
    """A name as compared: reading order, one form of each letter, case
    ignored. Accents are NOT taken off: Choiniere is not Choinière here."""
    return unicodedata.normalize("NFC", BME.reading_order(name)).casefold()


def differs(printed, member):
    """Whether two names build_lsrs.compatible takes as one differ by what
    Roster.initial_match is for -- a middle initial, or a first name's tabled
    short form -- and not by a suffix alone ("Michael Costable Jr." and
    "Costable, Michael": a father and a son can share the rest) or by
    punctuation alone, which stay the letter-for-letter rule's."""
    a, b = BL._parts(BME.reading_order(printed)), BL._parts(BME.reading_order(member))
    return bool(a and b) and (a[0] != b[0] or a[1] != b[1])


class Roster:
    """The sitting and former members, read for the one question: who is this
    printed name in this race. `terms` is the site's terms, newest first."""

    def __init__(self, sitting, former, terms, history=None, forms=None):
        self.members, self.by_name = {}, defaultdict(list)
        # {folded printed form: the form the owner tied it to} (build_lsrs.name_forms).
        self.forms = dict(forms or {})
        # {(term, seat)} each member held: the roster's one seat for the term it
        # is the seat of, and every seat the member printed on a bill of a term
        # (BME.seat_history), which is how a former member of an older term, and a
        # sitting member's earlier seats, are matched to the seat they held then.
        seats = (history or {}).get("seats") or {}
        self.surnames = defaultdict(list)
        newest = terms[0] if terms else None
        for kind, rows in (("sitting", sitting), ("former", former)):
            for m in rows or []:
                served = (m.get("served") or {}).get("terms") or []
                held_in = newest if kind == "sitting" else (served[-1] if served else None)
                p = {"id": str(m.get("id")), "slug": m.get("slug") or "", "kind": kind,
                     "name": m.get("name") or "", "seat": BME.seat_of(m),
                     "term": held_in, "label": m.get("display_full") or m.get("name") or ""}
                if not p["id"] or p["id"] in self.members:
                    continue
                p["held"] = {(t, k) for t, ks in (seats.get(p["id"]) or {}).items() for k in ks}
                for other in m.get("member_ids") or []:
                    p["held"] |= {(t, k) for t, ks in (seats.get(str(other)) or {}).items()
                                  for k in ks}
                if p["seat"] and p["term"]:
                    p["held"].add((p["term"], p["seat"]))
                # A former member's last recorded day, and their last term: who left early.
                p["last"], p["last_term"] = (m.get("served") or {}).get("last") or "", served[-1] if served else ""
                p["readings"], p["sfx"] = BME.readings(p["name"])
                p["party"] = str(m.get("party") or "")[:1].upper()
                self.members[p["id"]] = p
                self.by_name[nfc_fold(p["name"])].append(p)
                for sur in {x for x, _f in p["readings"]}:
                    self.surnames[sur].append(p)

    def surname_match(self, name, key, window, race, party):
        """([members], why not) for a candidate the results print as a surname
        (a House race of 2016-2022, race["surnames"]). The weaker kind of match,
        said so in the report: the surname, the very seat held in the term
        before or after the election, the party the candidate filed under
        where both give one, and no other candidate of the surname in the race.
        One member only is a match."""
        rd, sfx = BME.surname_readings(name)
        if len(str(name).split()) > 1:
            rd = rd + BME.readings(name)[0]
        held = [p for p in self.members.values() if any((t, key) in p["held"] for t in window)]
        fits = BME.by_name(held, [(s, f) for s, f in rd], sfx)
        letters = {x for x in str(party or "").upper().replace("/", "")}
        fits = [p for p in fits if not p["party"] or not letters or p["party"] in letters]
        sur = {s for s, _f in rd}
        twins = [c for c in (race or {}).get("candidates") or []
                 if c["name"] != name and sur & {s for s, _f in BME.surname_readings(c["name"])[0]}]
        if twins and fits:
            return [], "another candidate of that surname is in the race"
        if len(fits) == 1:
            return fits, ""
        if len(fits) > 1:
            return [], "more than one member of that surname held the seat"
        return [], ""

    def surname_near(self, name, key):
        """The members who share a surname-only candidate's surname and have
        sat in the race's county (or, for the Senate, any), as labels with ids,
        for the report; never a link."""
        rd, _sfx = BME.surname_readings(name)
        m = BME.KEY_RE.match(key)
        county = m.group(1) if m else None
        found = []
        for sur in {s for s, _f in rd}:
            for p in self.surnames.get(sur, []):
                if county and not any(k.startswith(f"H|{county}|") for _t, k in p["held"]) \
                        and p["seat"] and not p["seat"].startswith(f"H|{county}|"):
                    continue
                found.append(f"{p['label']} [{p['id']}]")
        return ", ".join(sorted(set(found)))

    def initial_match(self, name, key, window, race, party):
        """([members], why not) for a printed name no member has letter for
        letter: one member who held the race's very seat in `window`, whose
        name build_lsrs.compatible says can be the printed one (a middle
        initial on one side only, or a NICKNAMES pair; never a bare prefix),
        with a suffix that agrees, of the party the candidate filed under
        where both give one, and no other candidate in the race of their
        surname. Anything less is nobody."""
        printed = BME.reading_order(name)
        _rd, sfx = BME.readings(name)
        held = [p for p in self.members.values() if any((t, key) in p["held"] for t in window)]
        fits = [p for p in held if BL.compatible(printed, BME.reading_order(p["name"]))[0]
                and BME.suffixes_agree(p["sfx"], sfx) and differs(printed, p["name"])]
        letters = set(BME.party_letters(party).replace("/", ""))
        fits = [p for p in fits if not p["party"] or not letters or p["party"] in letters]
        if len(fits) > 1:
            return [], "more than one member whose name fits held the seat"
        if not fits:
            return [], ""
        sur = {s for s, _f in fits[0]["readings"]}
        if any(c["name"] != name and sur & {s for s, _f in BME.readings(c["name"])[0]}
               for c in (race or {}).get("candidates") or []):
            return [], (f"{fits[0]['label']} [{fits[0]['id']}] fits but for a middle initial or a short "
                        "form, and another candidate of that surname is in the race")
        return fits, ""

    def certain(self, name, key, election, race=None, party="", window=None, initials=False):
        """([members], why not): the members a printed name in race `key` is,
        by the strict rule. One member only is a match. `window`, the terms a
        seat held counts in, is the general election's (the term before and
        the term after) unless given: a special's is its own (special_window).
        `initials`: where no member has the name letter for letter, a middle
        initial on one side only may still be certain (initial_match) -- a
        general's and a primary's candidates, never a special's."""
        year = int(election[:4])
        after = BME.term_after(year)
        # The term before is on the old districts for the election of 2022: no
        # evidence of a seat in the new map (BME.on_this_map).
        given = window is not None
        if not given:
            window = {t for t in (BME.term_before(after), after) if BME.on_this_map(t, year)}
        if (race or {}).get("surnames"):
            return self.surname_match(name, key, window, race, party)
        # A form the owner tied to another is read as that one (TWO FORMS OF ONE NAME).
        name = self.forms.get(BL._fold(name), name)
        same = self.by_name.get(nfc_fold(name), [])
        fits = [p for p in same if any((t, key) in p["held"] for t in window)]
        if len(fits) == 1:
            return fits, ""
        if len(fits) > 1:
            return [], "more than one member of that name held the seat"
        if not same:
            return self.initial_match(name, key, window, race, party) if initials else ([], "")
        why = []
        for p in same:
            if key not in {k for _t, k in p["held"]}:
                why.append(f"{p['label']} [{p['id']}] has {BME.race_words(p['seat']) if p['seat'] else 'no seat'} "
                           f"on record, not {BME.race_words(key)}")
            else:
                terms = sorted(t for t, k in p["held"] if k == key)
                why.append(f"{p['label']} [{p['id']}] held {BME.race_words(key)} in {', '.join(terms) or 'a term not on record'}, "
                           + (f"not {' or '.join(sorted(window))}" if given else
                              f"not the term before or after {election[:4]}"))
        return [], "; ".join(why)


def rank_of(race, cand, held):
    """(place, of) among the candidates the page shows: 1 + those with more votes."""
    shown = [c for c in race["candidates"] if BE.same_name(c["name"]) not in held]
    return 1 + sum(1 for c in shown if c["votes"] > cand["votes"]), len(shown)


def result_of(cand, me, drawn):
    """won | lost | tie | open, in the elections page's meaning: Elected only
    where members_elect draws the winner; a tie is a tie; a race with any seat
    not final reads Result not final for the rest."""
    if cand.get("elected") is None:
        return "tie"
    if cand["elected"] is True:
        return "won" if drawn else "open"
    return "open" if me.get("not_final") else "lost"


def race_row(election, key, race, me, cand, drawn, held):
    """One row of the Elections tab, for candidate `cand` of race `key`: the
    race as it was that year, the result in the elections page's own words
    (result_of; `drawn` is whether members_elect draws them as a winner), the
    votes, the seats, and -- where no winner of the race is held back
    (`held`) -- the place among the candidates shown and, for a race of one
    seat, the share of every vote cast. `me` is members_elect's answer for
    the race. A member's tab draws it (app.js electionRow), and so does a new
    member-elect's provisional page (build_elect_pages)."""
    seats = race["seats"]
    row = {"d": election, "k": key, "a": BE.race_id(key), "r": result_of(cand, me, drawn),
           "v": cand["votes"], "s": seats}
    if race.get("floterial"):
        row["fl"] = 1
    if race.get("recounted"):
        row["rc"] = 1
    if me.get("recount"):
        row["rq"] = 1
    if not held:
        row["pl"], row["of"] = rank_of(race, cand, held)
        counted = sum(x["votes"] for x in race["candidates"]) + int(race.get("scatter") or 0)
        if seats == 1 and counted:
            row["sh"] = round(100 * cand["votes"] / counted, 1)
    return row


def election_rows(election, results, races_me, hand, roster, people):
    """({member id: [row, ...]}, [report line, ...]) for one election. Each
    row carries "c", the race's card as the elections page draws it
    (build_elections.race_card, the one function), the member's row marked."""
    rows, report = defaultdict(list), []
    matches = hand.get("matches") or {}
    tnotes = BE.totals_notes(results)
    for key in sorted(results["races"], key=BME.race_order):
        race, me = results["races"][key], races_me.get(key)
        if me is None:
            continue
        held = BE.held_names(hand, key)
        drawn = {e["n"]: e for e in me.get("elected") or []}
        said = matches.get(key) or {}
        for c in race["candidates"]:
            if BE.same_name(c["name"]) in held:
                continue
            won = drawn.get(BE.same_name(c["name"])) if c.get("elected") is True else None
            member = None
            if won is not None:
                # A drawn winner: the elections page's link, or none.
                member = roster.members.get(str(won["id"])) if won.get("id") else None
                if member is None and c["name"] not in said:
                    continue
            if member is None and c["name"] in said:
                v = said[c["name"]]
                if v is None:
                    continue
                member = roster.members.get(str(v))
                if member is None:
                    report.append((election, key, c["name"], "",
                                   f"the hand file names {v}, who is no sitting or former member"))
                    continue
            if member is None:
                got, why = roster.certain(c["name"], key, election, race, c.get("party"), initials=True)
                if got:
                    member = got[0]
                else:
                    near = (roster.surname_near(c["name"], key) if race.get("surnames")
                            else near_members(c["name"], key, people))
                    if near or why:
                        report.append((election, key, c["name"], near,
                                       why or "no member of exactly that name; the name fits "
                                              "only loosely"))
                    continue
            row = race_row(election, key, race, me, c, won is not None, held)
            inc = incumbents(key, race, election, roster, drawn, said) - held
            row["c"] = BE.race_card(key, race, me, results, tnotes, election, hand,
                                    mine=BE.same_name(c["name"]), anchor=False, inc=inc)
            if inc:
                row["inc"] = key[0]
            rows[member["id"]].append(row)
    return rows, report


def member_for(c, key, race, election, drawn, said, roster):
    """The member candidate `c` of race `key` is, or None: the elections page's
    own link for a drawn winner, the owner's hand-file match, else the certain
    rule (Roster.certain) -- the order election_rows takes, with nothing
    reported. `drawn` is {name: members_elect's winner}, `said` the hand file's
    matches for the race."""
    won = drawn.get(BE.same_name(c["name"])) if c.get("elected") is True else None
    if won is not None and won.get("id"):
        return roster.members.get(str(won["id"]))
    if won is not None and c["name"] not in said:
        return None  # a winner the elections page draws and does not link: its refusal stands
    if c["name"] in said:
        return roster.members.get(str(said[c["name"]])) if said[c["name"]] is not None else None
    got, _why = roster.certain(c["name"], key, election, race, c.get("party"), initials=True)
    return got[0] if len(got) == 1 else None


def _day_of(mdy):
    """"6/4/2026" -> "2026-06-04", or "" where it is not such a day."""
    try:
        m, d, y = (int(x) for x in str(mdy).split("/"))
        return f"{y:04d}-{m:02d}-{d:02d}"
    except ValueError:
        return ""


def held_on(member, chamber, day):
    """Whether `member` held a seat of `chamber` ("H" or "S") in the term sitting
    on `day`: a seat of it in that term among the seats the record gives them
    (the roster's seat for its term, and every seat their bills of a term print,
    entities.printed_tenures through BME.seat_history). A former member whose last
    recorded day is before the election's year, in that term, had left it."""
    term = BME.term_before(BME.term_after(int(day[:4])))
    if not any(t == term and k.startswith(chamber + "|") for t, k in member["held"]):
        return False
    gone = _day_of(member.get("last"))
    return not (member["kind"] == "former" and member.get("last_term") == term and gone
                and gone < f"{day[:4]}-01-01")


def incumbents(key, race, election, roster, drawn=None, said=None):
    """The candidates of race `key` (same_name) who held a seat in its chamber
    on election day (the owner, 19 November 2026: marked on the card, by the
    Incumbent chip since 21 November, build_elections.inc_chip), each
    by a certain match only (member_for) and held_on; a wrong mark is worse than
    none, so a candidate the rule cannot place is not marked."""
    chamber = key.split("|", 1)[0]
    out = set()
    for c in race["candidates"]:
        m = member_for(c, key, race, election, drawn or {}, said or {}, roster)
        if m and held_on(m, chamber, election):
            out.add(BE.same_name(c["name"]))
    return frozenset(out)


PRIMARY_RE = "primary_*.json"


def primaries_on_file(collected):
    """[(primary day, document)] of every collected/primary_<year>.json
    (src/parse/parse_sos_primary_results.py), oldest first."""
    out = []
    for p in sorted(Path(collected).glob(PRIMARY_RE)):
        doc = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and doc.get("election") and isinstance(doc.get("races"), dict):
            out.append((doc["election"], doc))
    return out


def primary_race(race):
    """A primary's race as its card draws it: the candidates on that party's
    ballot -- of its party, or of none the file prints -- and, as
    "other_votes", the votes for candidates of another party, which the file
    lists (a few written in, 2026's Republican Strafford 21 printing three
    Democrats with 3 to 5 votes; a 0 for 2024's Democratic Strafford 15's
    Republican) and which are no campaign on this ballot."""
    ballot = str(race.get("party") or "").lower()
    keep = [c for c in race["candidates"] if str(c.get("party") or "").lower() in (ballot, "")]
    gone = [c for c in race["candidates"] if c not in keep]
    out = dict(race, candidates=keep)
    if gone:
        out["other_votes"], out["other_rows"] = sum(c["votes"] for c in gone), len(gone)
    return out


def primary_rows(day, doc, roster):
    """({member id: [row, ...]}, [report line, ...]) for one primary day: a
    member's candidacy on their own party's ballot, by the general cards' own
    certain rule (Roster.certain: the whole name, or it but for a middle
    initial, and a seat held the term before or after; the stricter surname
    rule where the file prints surnames),
    never on another party's ballot. A candidate the file prints with no party
    is the member only where the member is of the ballot's party. Each row is
    the general's shape with "st": "primary" and "pp", the ballot's party, and
    "c", the race's card (build_elections.race_card with primary=)."""
    rows, report = defaultdict(list), []
    for key in sorted(doc["races"], key=lambda k: (k.split("|", 1)[0],) + tuple(
            BME.race_order(k.split("|", 1)[1]) if BME.KEY_RE.match(k.split("|", 1)[1]) else (9,))):
        party, gkey = key.split("|", 1)
        if not BME.KEY_RE.match(gkey):
            continue
        race = primary_race(doc["races"][key])
        ballot = party.upper()
        found = {}
        for c in race["candidates"]:
            printed = str(c.get("party") or "").upper()
            got, why = roster.certain(c["name"], gkey, day, race, c.get("party"), initials=True)
            if got and not printed and got[0]["party"] != ballot:
                got, why = [], f"printed with no party on the {ballot} ballot; the member is not of it"
            found[c["name"]] = (got, why)
        links = nominee_links(race, {n: g[0] if g else None for n, (g, _w) in found.items()})
        for c in race["candidates"]:
            got, why = found[c["name"]]
            if not got:
                if why:
                    report.append((day, f"{ballot} primary {gkey}", c["name"],
                                   roster.surname_near(c["name"], gkey) if race.get("surnames") else "", why))
                continue
            member = got[0]
            row = {"d": day, "st": "primary", "pp": ballot, "k": gkey, "a": BE.race_id(gkey),
                   "r": "most" if c.get("nominated") is True else "not", "v": c["votes"],
                   "s": race["seats"]}
            if race.get("floterial"):
                row["fl"] = 1
            inc = incumbents(gkey, race, day, roster)
            row["c"] = BE.race_card(gkey, race, {}, doc, {}, day, {}, mine=BE.same_name(c["name"]),
                                    anchor=False, primary=ballot, inc=inc, links=links)
            if inc:
                row["inc"] = gkey[0]
            rows[member["id"]].append(row)
    return rows, report


def nominee_links(race, matched):
    """{same_name: the member's page} for a primary's card: each nominee
    ("nominated": true) whom `matched` ({printed name: member or None}, the
    certain rule's answer for each candidate) places, as a general's card
    links the winner members_elect places (the owner, 20 November 2026: a
    sitting member's chip on a primary's card was not a link). A candidate
    who was not nominated links nowhere, as a general's loser does not."""
    return {BE.same_name(c["name"]): m["slug"] for c in race["candidates"]
            for m in [matched.get(c["name"])] if m and m.get("slug") and c.get("nominated") is True}


def near_members(name, key, people):
    """The members a printed name might be, for the report only: the same
    surname and a first name that fits even loosely, in the race's county (or
    any, for the Senate). A list of labels with ids; never a link."""
    rd, _sfx = BME.readings(name)
    found = []
    m = BME.KEY_RE.match(key)
    county = m.group(1) if m else None
    for kind in ("sitting", "former"):
        for p in people.named(kind, rd):
            if not BME.answers(p, rd):
                continue
            if county and p["county"] and p["county"] != county and p["seat"] != key:
                continue
            found.append(f"{p['label']} [{p['id']}]")
    return ", ".join(sorted(set(found)))


def next_general(today):
    """The next state general election on or after `today` (ISO), by RSA
    653:7, or None (key_dates.next_general)."""
    return KD.next_general(today)


FILINGS = "filings_{year}.json"


def filings_on_file(collected, year):
    """{"person": {member id: race key}, "slug": {provisional page slug: race
    key}}: who has filed for `year`'s state primary, from
    collected/filings_<year>.json; both empty where there is no such file.

    THE FILE IS A LATER STEP'S, AND NONE IS ON DISK (19 November 2026). It is
    to be read from the Secretary of State's own lists of the filing period --
    "Cumulative Filings", "Declarations of Intent" and "Withdrawals", PDFs on
    the year's Election Details page -- each saved by a person with its
    address, day and sha256, read whole or refused, as the results are. This
    reads the shape that step is to write, and nothing else:

        {"election": "2028-11-07", "primary": "2028-06-13",
         "_source": [{"file": "records/sources/...pdf", "url": "...",
                      "saved": "2028-03-11", "sha256": "..."}],
         "filings": [{"race": "H|Strafford|21", "office": "State Representative",
                      "name": "Alice Wade", "party": "d", "filed": "2028-03-06",
                      "kind": "declaration of candidacy", "withdrew": "",
                      "person": "11286"}]}

    "race" is the race key the results use; "person" a member's id, or "slug"
    a new member's provisional page, written only on a certain match (the
    elections tab's rule); "withdrew" the day of a withdrawal, which takes the
    filing off. A campaign-finance registration is never a filing. A file this
    cannot read is refused (BME.Refused), never read in part."""
    out = {"person": {}, "slug": {}}
    p = Path(collected) / FILINGS.format(year=year)
    if not p.is_file():
        return out
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        rows = doc["filings"]
        assert isinstance(rows, list)
    except (ValueError, KeyError, TypeError, AssertionError) as e:
        raise BME.Refused(f"{p.as_posix()} is no list of filings ({type(e).__name__}): "
                          "no member's tab is given upcoming elections from it") from e
    for f in rows:
        race = str((f or {}).get("race") or "")
        if not BME.KEY_RE.match(race) or f.get("withdrew"):
            continue
        if f.get("person"):
            out["person"][str(f["person"])] = race
        elif f.get("slug"):
            out["slug"][str(f["slug"])] = race
    return out


def upcoming(key, races, today):
    """The next state elections for seat `key` after `today` (ISO): {"k" the
    seat, "s" its seats, "fl" 1 for a floterial, "e": [{"w" filing, primary or
    general, "d" its day, "u" a period's last day, "sec" the RSA section, "act"
    and "from" for a text an act put in force from a day, "href" its Laws page
    where the build has it}, ...]}, soonest first, only those not yet past.
    None where the seat is not in `races` (BME.races_on_file) or nothing is
    ahead."""
    race = (races or {}).get(key)
    g = next_general(today)
    if not race or g is None:
        return None
    out = []
    for w, sec in (("filing", "655:14"), ("primary", "653:8"), ("general", "653:7")):
        got = KD.in_force(sec, g.year)
        if got is None or (w == "filing" and KD.state_primary(g.year) is None):
            continue
        first, last, law = got
        if last.isoformat() < today:
            continue
        e = {"w": w, "d": first.isoformat()}
        if last != first:
            e["u"] = last.isoformat()
        e["sec"] = sec
        if law.act and law.since:
            e["act"], e["from"] = law.act, law.since
        href = KD.law_href(sec)
        if href:
            e["href"] = href
        out.append(e)
    if not out:
        return None
    up = {"k": key, "s": race["seats"]}
    if race.get("floterial"):
        up["fl"] = 1
    up["e"] = out
    return up


def upcoming_for(by_member, collected, districts, today):
    """{member id: upcoming()} of each member with a row on the tab (`by_member`)
    who has filed for the next general's primary (filings_on_file), for the
    race filed for. {} with no filing list: no card without a filing."""
    g = next_general(today)
    if g is None:
        return {}
    races, _clash = BME.races_on_file(districts)
    out = {}
    for mid, key in filings_on_file(collected, g.year)["person"].items():
        got = upcoming(key, races, today) if mid in by_member else None
        if got:
            out[mid] = got
    return out


def cycle_of(row):
    """The election cycle a row is drawn under on the tab (app.js groups by it):
    a general's or a primary's own year. A special election and its primary
    carry the cycle of the term whose seat it fills ("cy"), and so sit among
    that cycle's rows by their day."""
    return row.get("cy") or row["d"][:4]


SPECIALS = "specials.json"


def specials_on_file(collected):
    """[(special, [its candidacies], [(primary, [its candidacies]), ...], the
    Secretary of State's page)] of collected/specials.json
    (src/parse/parse_sos_specials.py), oldest first; [] where it is not there."""
    p = Path(collected) / SPECIALS
    if not p.is_file():
        return []
    doc = json.loads(p.read_text(encoding="utf-8"))
    pages = {s["file"]: s.get("address") or "" for s in doc.get("_source") or []}
    cands = defaultdict(list)
    for x in doc.get("candidacy") or []:
        cands[x["contest"]].append(x)
    contests = doc.get("contest") or []
    out = []
    for c in sorted((c for c in contests if c.get("stage") == "special"), key=lambda c: c["contest"]):
        prims = [(q, cands[q["contest"]]) for q in contests if q.get("for") == c["contest"]]
        out.append((c, cands[c["contest"]], sorted(prims, key=lambda q: q[0]["contest"]),
                    pages.get(c.get("source"), "")))
    return out


def special_race(contest, cands, general):
    """A special's race, or its primary's, as race_card draws one: its candidacies
    as a results file's candidates (most votes first), one seat, the district's
    towns and floterial from the race of the general that elected the term
    (`general`), "recounted" where its votes are a recount's. A primary's leader
    is "nominated", as the State Primary reader marks one: the most votes, alone;
    a tie at the top settles nothing (null)."""
    out = [{"name": x["printed"], "party": x.get("party") or "", "votes": x["votes"],
            "write_in": bool(x.get("write_in"))} for x in cands]
    out.sort(key=lambda c: (-c["votes"], c["name"]))
    if contest["stage"] == "primary":
        top = max((c["votes"] for c in out), default=0)
        lead = [c for c in out if c["votes"] == top and top > 0]
        for c in out:
            c["nominated"] = (True if len(lead) == 1 else None) if any(c is x for x in lead) else False
    else:
        won = {x["printed"] for x in cands if x.get("elected")}
        for c in out:
            c["elected"] = c["name"] in won
    race = {"seats": contest["seats"], "floterial": bool((general or {}).get("floterial")),
            "towns": list((general or {}).get("towns") or []), "scatter": 0, "candidates": out}
    if contest.get("recounted"):
        race["recounted"] = True
    return race


def special_window(term, cycle):
    """The terms in which a seat held is evidence for a candidate of a special in
    `term`: that term and the one before and after, each on the lines the term
    was elected on (BME.on_this_map) -- the general's rule (a seat held the term
    before or after), around the term the special fills. The winner too: the
    design's "the seat in that term" alone links few, because a member sworn in
    mid-term often prints no seat on a bill of that term (David Fracht, sworn in
    on 6 September 2023, has Grafton 16 on record for 2025-2026 only), and the
    same name letter for letter in the same district on the same lines a term
    later is the evidence a general election's loss is shown on."""
    a = int(term[:4])
    return {t for t in (BME.term_before(term), term, f"{a + 2}-{a + 3}") if BME.on_this_map(t, cycle)}


def special_rows(specials, generals, roster, people=None):
    """({member id: [row, ...]}, [report line, ...]) of the special elections
    (specials_on_file), each candidate linked by the certain rule in the term
    the special fills (special_window) and nowhere else. `generals` is {term:
    collected/election_<year>.json} of the generals on file, which give each
    district's towns and the tie a re-run follows."""
    rows, report = defaultdict(list), []
    for sp, cands, prims, page in specials:
        term, key = sp["term"], (sp.get("keys") or {}).get("results")
        cycle = int(term[:4]) - 1
        if not key or not BME.KEY_RE.match(key):
            continue
        general = ((generals.get(term) or {}).get("races") or {}).get(key)
        extra = {"cy": str(cycle)}
        if page:
            extra["u"] = page
        tie = {}
        cause = sp.get("cause") or {}
        if cause.get("kind") == "tie" and cause.get("of") and cause.get("resolution"):
            tie = {"y": cause["of"][:4], "hr": cause["resolution"].rsplit(" ", 1)[-1]}

        def link(c, day, race, where):
            got, why = roster.certain(c["name"], key, day, race, c.get("party"),
                                      window=special_window(term, cycle))
            if got:
                return got[0]
            near = near_members(c["name"], key, people) if people else ""
            if near or why:
                report.append((day, where, c["name"], near,
                               why or "no member of exactly that name; the name fits only loosely"))
            return None

        race = special_race(sp, cands, general)
        winner = next((c for c in race["candidates"] if c.get("elected")), None)
        found = {c["name"]: link(c, sp["election"], race, key) for c in race["candidates"]}
        me = {"seats": race["seats"], "elected": []}
        if winner is not None:
            e = {"n": BE.same_name(winner["name"])}
            m = found.get(winner["name"])
            if m:
                e.update(id=m["id"], s=m["slug"])
            me["elected"].append(e)
        for c in race["candidates"]:
            m = found.get(c["name"])
            if m is None:
                continue
            row = race_row(sp["election"], key, race, me, c, c is winner, frozenset())
            row.update(st="special", **extra)
            if tie:
                row["tie"] = tie
            row["c"] = BE.race_card(key, race, me, {}, {}, sp["election"], {}, mine=BE.same_name(c["name"]),
                                    anchor=False)
            rows[m["id"]].append(row)
        for pc, pcands in prims:
            ballot = str(pc.get("party") or "").upper()
            prace = special_race(pc, pcands, general)
            placed = {c["name"]: link(c, pc["election"], prace, f"{ballot} special primary {key}")
                      for c in prace["candidates"]}
            links = nominee_links(prace, placed)
            for c in prace["candidates"]:
                m = placed[c["name"]]
                if m is None:
                    continue
                row = {"d": pc["election"], "st": "special-primary", "pp": ballot, "k": key,
                       "a": BE.race_id(key), "r": "most" if c.get("nominated") is True else "not",
                       "v": c["votes"], "s": prace["seats"]}
                if prace.get("floterial"):
                    row["fl"] = 1
                row.update(extra)
                row["c"] = BE.race_card(key, prace, {}, {}, {}, pc["election"], {}, mine=BE.same_name(c["name"]),
                                        anchor=False, primary=ballot, links=links)
                rows[m["id"]].append(row)
    return rows, report


def sort_rows(rows):
    """Strictly newest first (the owner, 19 November 2026): a cycle's general,
    then its primary under it; within one election, the Senate before the House."""
    return sorted(rows, key=lambda r: (cycle_of(r), r["d"], r["k"].startswith("S|")), reverse=True)


def build(site, collected, hand_path, today, sponsors=BME.SPONSORS_DEFAULT, up=None):
    """(rows by member id, report lines, elections) for the site folder.
    Given a dict `up`, fills it with the upcoming elections of each member with
    a row who has filed for the next general's primary ({member id:
    upcoming() of the race filed for}; filings_on_file)."""
    site = Path(site)
    sitting = BME.load_json(site / "legislators.json", "the sitting roster")
    former = BME.load_json(site / "former.json", "the former members")
    districts = BME.load_json(site / "districts.json", "the district table")
    meta = BME.load_json(site / "meta.json", "the site's meta.json, which names its terms")
    terms = meta.get("terms") if isinstance(meta, dict) else None
    history = BME.load_history(sponsors)
    roster = Roster(sitting, former, terms if isinstance(terms, list) else [], history,
                    BL.name_forms())
    items = BE.elections_on_file(collected)
    by_member, report = defaultdict(list), []
    pages = BE.provisional(site)
    for election, _p, results in items:
        races_me, _rep, hand = BE.decided(results, sitting, former, districts, hand_path, today,
                                          BE.settled_in(items, election), history)
        # A new winner's chip links to their provisional page, as on the elections page's card.
        BE.with_pages(races_me, pages.get(election))
        people = BME.People(sitting, former, BME.ballot_of(results))
        got, rep = election_rows(election, results, races_me, hand, roster, people)
        for mid, rows in got.items():
            by_member[mid] += rows
        report += rep
    # The primaries (the owner, 19 November 2026): each on the member's own party's ballot.
    for day, doc in primaries_on_file(collected):
        got, rep = primary_rows(day, doc, roster)
        for mid, rows in got.items():
            by_member[mid] += rows
        report += rep
    # The special elections and their primaries (the owner, 19 November 2026).
    specials = specials_on_file(collected)
    if specials:
        got, rep = special_rows(specials, {r.get("term"): r for _e, _p, r in items}, roster,
                                BME.People(sitting, former, ()))
        for mid, rows in got.items():
            by_member[mid] += rows
        report += rep
    # One row for each member and election. Two in one election would be two
    # races for one person, which a seat count cannot allow: neither is shown.
    clash = []
    for mid, rows in list(by_member.items()):
        seen = defaultdict(list)
        for r in rows:
            seen[r["d"]].append(r)
        for d, rs in seen.items():
            if len(rs) > 1:
                clash.append((d, mid, [r["k"] for r in rs]))
                by_member[mid] = [r for r in by_member[mid] if r["d"] != d]
        if not by_member[mid]:
            del by_member[mid]
    for d, mid, keys in clash:
        p = roster.members.get(mid, {})
        report.append((d, ", ".join(keys), p.get("name", ""), f"{p.get('label', mid)} [{mid}]",
                       "matched to more than one race of one election; shown in none"))
    if up is not None:
        up.update(upcoming_for(by_member, collected, districts, today))
    return {mid: sort_rows(rs) for mid, rs in by_member.items()}, report, [i[0] for i in items]


def write_member_files(site, by_member, up=None):
    """Set "elections" in each member's own file, and "up" (upcoming) where
    `up` has the member and the member has a row; remove either from any that
    no longer has one. Returns (files changed, ids with no file)."""
    folder = Path(site) / "legislators"
    changed, missing = 0, []
    for mid in sorted(by_member):
        if not (folder / f"{mid}.json").is_file():
            missing.append(mid)
    for f in sorted(folder.glob("*.json")):
        mid = f.stem
        doc = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        want = by_member.get(mid)
        ahead = (up or {}).get(mid) if want else None
        if doc.get("elections") == want and doc.get("up") == ahead:
            continue
        for k, v in (("elections", want), ("up", ahead)):
            if v:
                doc[k] = v
            else:
                doc.pop(k, None)
        f.write_text(json.dumps(doc), encoding="utf-8")
        changed += 1
    return changed, missing


def report_text(report, elections):
    """The owner's list, as markdown: every candidate who could be a member
    and is not certain."""
    out = ["# Races not shown on a member's Elections tab",
           "",
           "Each is a candidate whose name could be a sitting or former member's and is not "
           "certain by the rule (the same name read first name first, and a seat the member "
           "held in the term before or after the election). To settle one, add the race and "
           "the name exactly as printed to `corrections/members_elect.json` under the "
           "election's day, in `matches`: a member id shows it on that member's tab, null "
           "keeps it off.",
           "",
           f"Elections read: {', '.join(elections) or 'none'}. {len(report)} to settle.",
           "",
           "| Election | Race | Printed name | Likely member | Why not certain |",
           "|---|---|---|---|---|"]
    for d, key, name, near, why in sorted(report, key=lambda x: (x[0], BME.race_order(x[1]) if BME.KEY_RE.match(x[1]) else (9,), x[2])):
        out.append(f"| {d} | {key} | {name} | {near or 'none found'} | {why.replace('|', '/')} |")
    return "\n".join(out) + "\n"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--site", default="site")
    ap.add_argument("--collected", default="collected")
    ap.add_argument("--hand", default=str(BME.HAND_DEFAULT))
    ap.add_argument("--report", default=str(REPORT_DEFAULT))
    ap.add_argument("--sponsors", default=str(BME.SPONSORS_DEFAULT),
                    help="text_sponsors.json, which holds the seat each member printed each term")
    a = ap.parse_args()
    today = build_date.today().isoformat()
    up = {}
    try:
        by_member, report, elections = build(a.site, a.collected, Path(a.hand), today, a.sponsors, up)
    except BME.Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    # Said loudly, not skipped: the older elections are linked by the seat held.
    gaps = BME.history_gaps(a.sponsors, BME.PAST_SPONSORS_DEFAULT, BME.CAREERS_DEFAULT)
    if gaps:
        n = sum(len(r["candidates"]) for _e, _p, doc in BE.elections_on_file(a.collected)
                if int(doc["election"][:4]) <= BME.HISTORY_UNTIL
                for r in doc["races"].values() if r.get("surnames"))
        print("member elections: " + BME.gap_line(gaps, n, "candidate(s)"), file=sys.stderr)
    if not elections:
        # No results on file: no tab anywhere, and none left from an earlier run.
        write_member_files(a.site, {})
        print(f"member elections: no results in {a.collected}/ (election_<year>.json): no tab")
        return 0
    if not by_member:
        print("member elections: FAILED: results are on file and no member has a row, which "
              "no roster explains", file=sys.stderr)
        return 1
    changed, missing = write_member_files(a.site, by_member, up)
    if missing:
        # Said, not fatal: one member without a file is no reason to hold the build.
        print(f"member elections: WARNING {len(missing)} member(s) with rows have no "
              f"{a.site}/legislators/<id>.json, so no tab: {', '.join(missing[:8])}", file=sys.stderr)
    wins = sum(1 for rs in by_member.values() for r in rs if r["r"] == "won")
    lost = sum(1 for rs in by_member.values() for r in rs if r["r"] == "lost")
    prim = sum(1 for rs in by_member.values() for r in rs if r.get("st") == "primary")
    spec = sum(1 for rs in by_member.values() for r in rs if r.get("st") in ("special", "special-primary"))
    rows = sum(len(rs) for rs in by_member.values()) - prim - spec
    rp = Path(a.report)
    try:
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(report_text(report, elections), encoding="utf-8")
        said = f"{len(report)} to settle in {rp.as_posix()}"
    except OSError as e:
        said = f"{len(report)} to settle (the report could not be written: {e})"
    wins -= sum(1 for rs in by_member.values() for r in rs if r.get("st") == "special" and r["r"] == "won")
    lost -= sum(1 for rs in by_member.values() for r in rs if r.get("st") == "special" and r["r"] == "lost")
    print(f"member elections: {len(by_member)} members, {rows} rows ({wins} won, {lost} lost, "
          f"{rows - wins - lost} not final or tied), {prim} primary rows and {spec} special-election "
          f"rows; {changed} member files changed; {said}")
    nxt = next_general(today)
    filed = (Path(a.collected) / FILINGS.format(year=nxt.year)) if nxt else None
    print(f"member elections: upcoming elections on {len(up)} members' tabs"
          + (f", for the general election of {nxt.isoformat()}; " if nxt else
             "; RSA 653:7 gives no general election ahead; ")
          + (f"filings from {filed.as_posix()}" if filed and filed.is_file() else
             "no filing list on disk, so no member has filed on record"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
