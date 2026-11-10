#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-10.1
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

  The same rule reads a race that is not final -- all of them, until the
  recount deadline has passed -- because members_elect draws no winner for
  one, and a winner it does not draw has no link to take. A winner it DOES
  draw and cannot link is left alone: that is its refusal, and a name match
  here must not override it.

  Never a looser string match. A candidate who could be a member and is not
  certain is not shown; the report names the race, the printed name, the likely
  member and why it is not certain, for the owner to settle in the hand file.

WHAT A ROW SAYS. The race as it was that year (its key: chamber, county and
district, seats, floterial), the result in the elections page's own words, the
member's votes, and -- for a race of one seat -- the share of every vote cast
in it, write-ins included, as the elections page does; a race of more than one
seat gives none, because a voter could choose several. The place among the
candidates. A race whose winner the owner holds back has neither. Where a race
is a recount's, the row says so; the first count is not on file.

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
import build_members_elect as BME

# The tab's rows are kept to what the page draws; the rest is in the race's card.
REPORT_DEFAULT = Path("reports") / "elections_uncertain.md"


def nfc_fold(name):
    """A name as compared: reading order, one form of each letter, case
    ignored. Accents are NOT taken off: Choiniere is not Choinière here."""
    return unicodedata.normalize("NFC", BME.reading_order(name)).casefold()


class Roster:
    """The sitting and former members, read for the one question: who is this
    printed name in this race. `terms` is the site's terms, newest first."""

    def __init__(self, sitting, former, terms):
        self.members, self.by_name = {}, defaultdict(list)
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
                self.members[p["id"]] = p
                self.by_name[nfc_fold(p["name"])].append(p)

    def certain(self, name, key, election):
        """([members], why not): the members a printed name in race `key` is,
        by the strict rule. One member only is a match."""
        year = int(election[:4])
        after = BME.term_after(year)
        window = {BME.term_before(after), after}
        same = self.by_name.get(nfc_fold(name), [])
        fits = [p for p in same if p["seat"] == key and p["term"] in window]
        if len(fits) == 1:
            return fits, ""
        if len(fits) > 1:
            return [], "more than one member of that name held the seat"
        if not same:
            return [], ""
        why = []
        for p in same:
            if p["seat"] != key:
                why.append(f"{p['label']} [{p['id']}] has {BME.race_words(p['seat']) if p['seat'] else 'no seat'} "
                           f"on record, not {BME.race_words(key)}")
            else:
                why.append(f"{p['label']} [{p['id']}] held {BME.race_words(key)} in {p['term'] or 'a term not on record'}, "
                           f"not the term before or after {election[:4]}")
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


def election_rows(election, results, races_me, hand, roster, people):
    """({member id: [row, ...]}, [report line, ...]) for one election."""
    rows, report = defaultdict(list), []
    matches = hand.get("matches") or {}
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
                got, why = roster.certain(c["name"], key, election)
                if got:
                    member = got[0]
                else:
                    near = near_members(c["name"], key, people)
                    if near or why:
                        report.append((election, key, c["name"], near,
                                       why or "no member of exactly that name; the name fits "
                                              "only loosely"))
                    continue
            res = result_of(c, me, won is not None)
            seats = race["seats"]
            row = {"d": election, "k": key, "a": BE.race_id(key), "r": res, "v": c["votes"],
                   "s": seats}
            if race.get("floterial"):
                row["fl"] = 1
            if race.get("recounted"):
                row["rc"] = 1
            if me.get("recount"):
                row["rq"] = 1
            if not held:
                row["pl"], row["of"] = rank_of(race, c, held)
                counted = sum(x["votes"] for x in race["candidates"]) + int(race.get("scatter") or 0)
                if seats == 1 and counted:
                    row["sh"] = round(100 * c["votes"] / counted, 1)
            rows[member["id"]].append(row)
    return rows, report


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


def sort_rows(rows):
    """Newest election first; within one, the Senate before the House."""
    return sorted(rows, key=lambda r: (r["d"], r["k"].startswith("S|")), reverse=True)


def build(site, collected, hand_path, today):
    """(rows by member id, report lines, elections) for the site folder."""
    site = Path(site)
    sitting = BME.load_json(site / "legislators.json", "the sitting roster")
    former = BME.load_json(site / "former.json", "the former members")
    districts = BME.load_json(site / "districts.json", "the district table")
    meta = BME.load_json(site / "meta.json", "the site's meta.json, which names its terms")
    terms = meta.get("terms") if isinstance(meta, dict) else None
    roster = Roster(sitting, former, terms if isinstance(terms, list) else [])
    items = BE.elections_on_file(collected)
    by_member, report = defaultdict(list), []
    for election, _p, results in items:
        races_me, _rep, hand = BE.decided(results, sitting, former, districts, hand_path, today)
        people = BME.People(sitting, former, BME.ballot_of(results))
        got, rep = election_rows(election, results, races_me, hand, roster, people)
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
    return {mid: sort_rows(rs) for mid, rs in by_member.items()}, report, [i[0] for i in items]


def write_member_files(site, by_member):
    """Set "elections" in each member's own file; remove it from any that no
    longer has one. Returns (files with rows, files changed, ids with no file)."""
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
        if want:
            if doc.get("elections") == want:
                continue
            doc["elections"] = want
        elif "elections" in doc:
            del doc["elections"]
        else:
            continue
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
    a = ap.parse_args()
    today = build_date.today().isoformat()
    try:
        by_member, report, elections = build(a.site, a.collected, Path(a.hand), today)
    except BME.Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    if not elections:
        # No results on file: no tab anywhere, and none left from an earlier run.
        write_member_files(a.site, {})
        print(f"member elections: no results in {a.collected}/ (election_<year>.json): no tab")
        return 0
    if not by_member:
        print("member elections: FAILED: results are on file and no member has a row, which "
              "no roster explains", file=sys.stderr)
        return 1
    changed, missing = write_member_files(a.site, by_member)
    if missing:
        # Said, not fatal: one member without a file is no reason to hold the build.
        print(f"member elections: WARNING {len(missing)} member(s) with rows have no "
              f"{a.site}/legislators/<id>.json, so no tab: {', '.join(missing[:8])}", file=sys.stderr)
    wins = sum(1 for rs in by_member.values() for r in rs if r["r"] == "won")
    lost = sum(1 for rs in by_member.values() for r in rs if r["r"] == "lost")
    rows = sum(len(rs) for rs in by_member.values())
    rp = Path(a.report)
    try:
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(report_text(report, elections), encoding="utf-8")
        said = f"{len(report)} to settle in {rp.as_posix()}"
    except OSError as e:
        said = f"{len(report)} to settle (the report could not be written: {e})"
    print(f"member elections: {len(by_member)} members, {rows} rows ({wins} won, {lost} lost, "
          f"{rows - wins - lost} not final or tied); {changed} member files changed; {said}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
