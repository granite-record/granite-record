#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-17.1
"""
build_members_elect's matching rule, scored on an election already decided.

    python3 src/parse/score_members_elect.py              # the 2024 general election
    python3 src/parse/score_members_elect.py --year 2024 --list

WHY. A winner is linked to a page only on a certain match (the person's rule,
16 October 2026), and the plan said to measure the rule on 2024 first,
against something this project did not make: who actually took each seat.
This runs the rule as it would have run in the weeks after the election of
`--year`, and holds every link it makes to the next term's roll calls.

THE WORLD AS OF ELECTION DAY, built from what the record held then, not from
the roster of today:

  sitting   everyone who cast a roll call in the election's year before
            Election Day, at the seat they held in that term;
  former    everyone who cast one earlier and not that year, at the last
            seat they held before it;
  districts site/districts.json, which parse_sos_results has already held
            every race's seats and towns to.

A SEAT IS THE ONE HELD THEN. The roster files keep one seat per record, the
last one, so a member who sat for Hillsborough 14 in 2024 and for
Hillsborough 38 from 2025 reads Hillsborough 38 in them (Rep. Ralph Boehm,
found by this on 17 October 2026). The seat a member's bills printed in the
term (text_sponsors.json, where it names exactly one) is taken first, as
build_data dates the ballots' labels; the roster's only where that term was
the record's last; and otherwise the roster's, counted as "a later seat"
and said, because it is the one thing in this world that could be
tomorrow's.

THE TRUTH is the next term's roll calls: the members who voted in it, each at
the seat the roster gives them for it, and for each winner the one of their
race's seat holders whose surname is the winner's -- and, where two share
it, whose first name is too. That matcher is written here and not borrowed
from the rule, and it is held to the seat the winner actually took.

WHAT IT SAYS. Each winner is linked correctly (to the record of the person
who took the seat, or another record of the same person: a chamber change
mints a second number, joined by member_links' tests); linked WRONGLY
(to anyone else -- there must be none); linked where the truth could not be
read; or left unlinked, with the rule's reason, as a new person, or as a
person the record already knew, whose name forms it prints so that the
person can decide whether a rule should widen.

WHAT IT READS, and asks nobody: collected/election_<year>.json,
records/rollcalls/, site/legislators.json, site/former.json,
site/districts.json, former_members.json and text_sponsors.json. It writes
nothing.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import json
import re
from collections import Counter, defaultdict

import build_members_elect as BME
import proceedings as P
from member_links import SHORT, same_first

NEEDS = ("records/rollcalls", "site/legislators.json", "site/former.json", "site/districts.json",
         "former_members.json", "text_sponsors.json")


def absent(root, year, results=None):
    """What the score needs and `root` lacks."""
    root = Path(root)
    res = Path(results) if results else root / "collected" / f"election_{year}.json"
    return ([res.as_posix()] if not res.exists() else []) \
        + [x for x in NEEDS if not (root / x).exists()]


def letters(s):
    return re.sub(r"[^a-z]", "", BME.fold(s).lower())


def day_of(when):
    """A roll call's day from RollCallSummary's "1/3/2024 9:25:37 AM"."""
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", when or "")
    return datetime.date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else None


def ballots(root):
    """{id: {(day, chamber), ...}}: the days each member id cast a roll call
    ballot on, in which chamber, from every roll call on file. An id is the
    PersonID the site keys a member by, or the employee number where there
    is none, as build_data takes it."""
    d = Path(root) / "records" / "rollcalls"
    days = {}
    files = sorted(d.glob("RollCallSummary_*.txt"))
    cur = Path(root) / "RollCallSummary.txt"
    for f in files + ([cur] if cur.exists() else []):
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            p = line.split("|", 4)
            if len(p) > 3 and p[2].strip().isdigit():
                days.setdefault((p[0].strip(), p[1].strip(), p[2].strip()), day_of(p[3].strip()))
    held = defaultdict(set)
    files = sorted(d.glob("RollCallHistory_*.txt"))
    cur = Path(root) / "RollCallHistory.txt"
    for f in files + ([cur] if cur.exists() else []):
        with open(f, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                p = line.split("|", 6)
                if len(p) < 7:
                    continue
                day = days.get((p[0].strip(), p[1].strip(), p[2].strip()))
                mid = p[4].strip() or p[3].strip()
                if day and mid:
                    held[mid].add((day, p[1].strip()))
    return held


def term_of_ballot(day):
    """The term a roll call of `day` belongs to: Organization Day's is the next."""
    return P.vote_term(day.year, day.isoformat())


class Record:
    """Who a member id was, as the record held it: names and seats."""

    def __init__(self, root):
        root = Path(root)
        load = lambda p: json.loads((root / p).read_text(encoding="utf-8"))  # noqa: E731
        self.rows = {str(r["id"]): r for r in load("site/former.json")}
        self.rows.update({str(r["id"]): r for r in load("site/legislators.json")})
        self.old = {str(k): v for k, v in load("former_members.json").items()}
        self.text = defaultdict(set)
        for term, bills in load("text_sponsors.json").items():
            for recs in bills.values():
                for r in recs:
                    if r.get("member_id") and r.get("chamber") in ("H", "S"):
                        self.text[(term, str(r["member_id"]))].add(
                            (r["chamber"], BME.full_county(r.get("county")) if r["chamber"] == "H"
                             else "", str(int(r["district"])) if str(r.get("district") or "")
                             .isdigit() else ""))

    def name(self, mid):
        r = self.rows.get(mid) or self.old.get(mid) or {}
        return r.get("name") or f"Member #{mid}"

    def party(self, mid):
        r = self.rows.get(mid) or self.old.get(mid) or {}
        return str(r.get("party") or "").strip()[:1].upper()

    def recorded(self, mid, chamber):
        """The seat the roster files keep for an id: its last."""
        r = self.rows.get(mid) or self.old.get(mid) or {}
        dist = str(r.get("district") or "").strip()
        dist = str(int(dist)) if dist.isdigit() else ""
        return (chamber, BME.full_county(r.get("county")) if chamber == "H" else "", dist)

    def seat(self, mid, term, chamber, last_term):
        """(chamber, county, district, how it is known) of an id in `term`."""
        text = {s for s in self.text.get((term, mid), ()) if s[0] == chamber and s[2]}
        if len(text) == 1:
            return (*next(iter(text)), "the bills of the term")
        how = "the roster, the record's last" if term == last_term else "a later seat"
        return (*self.recorded(mid, chamber), how)


def key_of(chamber, county, district):
    if not district:
        return None
    return f"S|{district}" if chamber == "S" else (f"H|{county}|{district}" if county else None)


def world(year, held, rec):
    """(sitting rows, former rows, next term's seat holders {race: [(id, name)]},
    {id: how its seat is known}) as of Election Day of `year`."""
    election = BME.general_election(year)
    this, nxt = BME.term_before(BME.term_after(year)), BME.term_after(year)
    sitting, former, holders, how = [], [], defaultdict(list), {}

    def row(mid, term, chamber, last_term):
        ch, county, dist, known = rec.seat(mid, term, chamber, last_term)
        how[mid] = known
        r = rec.rows.get(mid) or {}
        return {"id": mid, "name": rec.name(mid), "chamber": ch, "county": county,
                "district": dist, "slug": r.get("slug") or "",
                "display_full": f"{rec.name(mid)} ({ch} {county} {dist})".replace("  ", " ")}
    for mid, bs in held.items():
        terms = defaultdict(Counter)
        for day, ch in bs:
            terms[term_of_ballot(day)][ch] += 1
        last = max(terms)
        before = [(d, ch) for d, ch in bs if d < election]
        if any(d.year == election.year for d, _ in before):
            ch = Counter(c for d, c in before if d.year == election.year).most_common(1)[0][0]
            sitting.append(row(mid, this, ch, last))
        elif before:
            t = max(term_of_ballot(d) for d, _ in before)
            ch = terms[t].most_common(1)[0][0]
            former.append(row(mid, t, ch, last))
        if nxt in terms:
            ch = terms[nxt].most_common(1)[0][0]
            ch, county, dist, _ = rec.seat(mid, nxt, ch, last)
            k = key_of(ch, county, dist)
            if k:
                holders[k].append((mid, rec.name(mid)))
    return sitting, former, holders, how


def first_fits(a, b):
    """The same first name, one the start of the other, or a short form."""
    a, b = letters(a.split()[0]) if a.split() else "", letters(b.split()[0]) if b.split() else ""
    if not a or not b:
        return False
    short, full = sorted((a, b), key=len)
    return a == b or (len(short) >= 3 and full.startswith(short)) or SHORT.get(a) == b \
        or SHORT.get(b) == a


def truth(name, seat_holders):
    """(id, "") of the seat holder a winner is, or (None, why)."""
    words = BME.SUFFIX.sub("", BME.fold(name)).replace('"', " ").split()
    tails = {letters("".join(words[i:])): " ".join(words[:i]) for i in range(len(words))}
    hits = []
    for mid, rname in seat_holders:
        last, first = (rname.split(",", 1) + [""])[:2]
        sur = letters(BME.SUFFIX.sub("", last))
        # A ROSTER SURNAME LONGER THAN THE BALLOT'S is the ballot's and more
        # (17 October 2026): "Matt Sabourin" on the 2024 ballot is "Sabourin
        # dit Choiniere, Matt" in the roster. Its first word is then the
        # ballot's last.
        head = letters(last.split()[0]) if last.split() else ""
        if sur and sur in tails:
            hits.append((mid, first.strip(), tails[sur]))
        elif len(last.split()) > 1 and words and head == letters(words[-1]):
            hits.append((mid, first.strip(), " ".join(words[:-1])))
    if len(hits) > 1:
        hits = [h for h in hits if first_fits(h[1], h[2])]
    if len(hits) == 1:
        return hits[0][0], ""
    return None, (f"{len(hits)} of the seat's members fit" if hits
                  else "no member of the next term in that seat has the surname")


def same_person(a, b, rec, held):
    """Two ids of one person: the same id, or a chamber change's two
    numbers, by member_links' own first four tests -- each id of one chamber
    only, and not the same one; one surname and a first name that fits; no
    day on which both voted; and one party.

    TWO NUMBERS IN ONE CHAMBER ARE TWO PEOPLE (member_links' rule 1): a
    member who comes back to a chamber gets their old number back.
    NOT careers.json, which the first run of this score leaned on and which
    showed why it cannot be, on 17 October 2026: it joins Sen. Pat Long's
    House record, Hillsborough 23, to the first-term Patrick Long of
    Hillsborough 26 -- the error member_links' docstring records -- so the
    score read the freshman as a person the record knew and the senator as
    a new one."""
    if a == b:
        return True
    (sa, fa, ca, da, pa), (sb, fb, cb, db, pb) = profile(a, rec, held), profile(b, rec, held)
    if sa != sb or len(ca) != 1 or len(cb) != 1 or ca == cb or not same_first(fa, fb):
        return False
    return not (da & db) and not (pa and pb and pa != pb)


_PROFILES = {}


def profile(mid, rec, held):
    """(surname, first name, chambers, days, party) of an id, kept once."""
    key = (mid, id(rec), id(held))
    if key not in _PROFILES:
        last, first = (rec.name(mid).split(",", 1) + [""])[:2]
        bs = held.get(mid, ())
        _PROFILES[key] = (letters(BME.SUFFIX.sub("", last)), first.strip(),
                          frozenset(ch for _d, ch in bs), frozenset(d for d, _c in bs),
                          rec.party(mid))
    return _PROFILES[key]


def score(root=".", year=2024, results=None):
    """Everything the report says, as data."""
    root = Path(root)
    results = BME.read_results(Path(results) if results else
                               root / "collected" / f"election_{year}.json")
    districts = json.loads((root / "site" / "districts.json").read_text(encoding="utf-8"))
    held = ballots(root)
    rec = Record(root)
    sitting, former, holders, how = world(year, held, rec)
    sitting_ids = {r["id"] for r in sitting}
    election = BME.general_election(year)
    # EVERY RACE FINAL, SO THAT EVERY LINK CAN BE READ (17 October 2026): the
    # step draws a winner only once the race is final, and draws no link for
    # one it holds back. So a recount deadline the day after the election,
    # and a day two weeks on, before Organization Day.
    hand = {"matches": {}, "not_final": {}, "held": {},
            "recount_deadline": (election + datetime.timedelta(days=1)).isoformat()}
    today = (election + datetime.timedelta(days=14)).isoformat()
    races, report = BME.members_elect(results, sitting, former, districts, hand, today)
    on_file, _ = BME.races_on_file(districts)
    people = BME.People(sitting, former)
    known = {r["id"]: r for r in former}
    known.update({r["id"]: r for r in sitting})
    out = {"correct": [], "wrong": [], "unverified": [], "unlinked_known": [],
           "unlinked_new": [], "unlinked_unread": [], "kinds": Counter(),
           "sitting": len(sitting), "former": len(former),
           "later_seats": sorted(m for m in how if how[m] == "a later seat" and m in sitting_ids),
           "notes": report["notes"]}
    for key, r in results["races"].items():
        drawn = {e["n"]: e for e in races.get(key, {}).get("elected", [])}
        for c in r["candidates"]:
            if c.get("elected") is not True:
                continue
            e = drawn.get(BME.reading_order(c["name"]))
            if e is None:
                raise SystemExit(f"{key}: {c['name']} won and is not drawn: the score cannot "
                                 "read the rule's answer")
            t, why_t = truth(c["name"], holders.get(key, []))
            link = e.get("id")
            _, why = BME.auto_link(key, c["name"], people, on_file)
            row = {"race": key, "name": c["name"], "link": link, "kind": e["k"],
                   "truth": t, "truth_name": rec.name(t) if t else "", "why_not": why}
            if link:
                out["kinds"][e["k"]] += 1
                if t is None:
                    row["why_truth"] = why_t
                    out["unverified"].append(row)
                elif same_person(link, t, rec, held):
                    out["correct"].append(row)
                else:
                    row["link_name"] = rec.name(link)
                    out["wrong"].append(row)
                continue
            if t is None:
                row["why_truth"] = why_t
                out["unlinked_unread"].append(row)
                continue
            was = [m for m in known if same_person(m, t, rec, held)]
            if was:
                row["records"] = [{"id": m, "name": known[m]["name"],
                                   "seat": key_of(known[m]["chamber"], known[m]["county"],
                                                  known[m]["district"]),
                                   "as": "sitting" if m in sitting_ids else "former",
                                   "seat_from": how.get(m)} for m in was]
                out["unlinked_known"].append(row)
            else:
                out["unlinked_new"].append(row)
    return out


def bucket(why):
    """A rule's reason, in a few words."""
    for start, words in (
            ("a sitting member of that name holds another seat", "sits for another seat"),
            ("the one former member of that name sat in", "former member of another county"),
            ("the first name fits only as the start", "first name only a prefix"),
            ("the one former member who might be", "former member by a short form only"),
            ("a Jr. or Sr.", "a Jr. or Sr. on one side"),
            ("the one former member of that name has no county", "former member, no county"),
            (BME.NEW, "no record of that name")):
        if why.startswith(start):
            return words
    if "former members of that name" in why:
        return "two or more former records of that name"
    if "share the surname" in why or "answer to that name" in why:
        return "two of the surname in the seat"
    return why[:60]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--root", default=".", help="where the record is: site/, records/rollcalls/")
    ap.add_argument("--results", default=None, help="default <root>/collected/election_<year>.json")
    ap.add_argument("--list", action="store_true", help="every unlinked winner, not only the "
                                                        "known ones")
    a = ap.parse_args()
    miss = absent(a.root, a.year, a.results)
    if miss:
        print("not here: " + ", ".join(miss))
        return 2
    s = score(a.root, a.year, a.results)
    winners = sum(len(s[k]) for k in ("correct", "wrong", "unverified", "unlinked_known",
                                      "unlinked_new", "unlinked_unread"))
    print(f"the general election of {a.year}, as of its own day: {s['sitting']} sitting, "
          f"{s['former']} former; {winners} winners")
    print(f"  linked correctly   {len(s['correct'])} ({s['kinds']['sitting']} sitting, "
          f"{s['kinds']['former']} returning, among all links)")
    print(f"  linked WRONGLY     {len(s['wrong'])}")
    print(f"  linked, unverified {len(s['unverified'])}")
    print(f"  unlinked, new      {len(s['unlinked_new'])}")
    print(f"  unlinked, known    {len(s['unlinked_known'])}")
    print(f"  unlinked, no truth {len(s['unlinked_unread'])}")
    for r in s["wrong"]:
        print(f"WRONG  {r['race']:<20} {r['name']} -> {r['link_name']} [{r['link']}]; the seat "
              f"went to {r['truth_name']} [{r['truth']}]")
    for r in s["unverified"]:
        print(f"UNVERIFIED  {r['race']:<20} {r['name']} -> [{r['link']}]: {r['why_truth']}")
    if s["unlinked_known"]:
        print("\nUNLINKED, AND THE RECORD KNEW THEM -- the rule's reason, the ballot's name, the "
              "record's:")
        for r in sorted(s["unlinked_known"], key=lambda r: bucket(r["why_not"])):
            recs = "; ".join(f"{x['as']} {x['name']} [{x['id']}] {x['seat']}"
                             + (" (a later seat)" if x["seat_from"] == "a later seat" else "")
                             for x in r["records"])
            print(f"  {r['race']:<20} {r['name']!r}: {bucket(r['why_not'])} -- {recs}")
    c = Counter(bucket(r["why_not"]) for r in s["unlinked_new"])
    print("\nunlinked new people, by the rule's reason: "
          + ", ".join(f"{n} {k}" for k, n in c.most_common()))
    if a.list:
        for r in s["unlinked_new"] + s["unlinked_unread"]:
            print(f"  {r['race']:<20} {r['name']}: {r['why_not'][:100]}"
                  + (f" [truth: {r.get('why_truth')}]" if r.get("why_truth") else ""))
    if s["later_seats"]:
        print(f"\n{len(s['later_seats'])} sitting member(s) placed at a later seat, their term's "
              "bills naming none: " + ", ".join(s["later_seats"][:12]))
    return 1 if s["wrong"] or s["unverified"] else 0


if __name__ == "__main__":
    sys.exit(main())
