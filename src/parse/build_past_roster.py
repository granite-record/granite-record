#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.2
"""
Who sat, term by term, 1989 to 1998, as the sponsor route gives it.

    python3 src/parse/build_past_roster.py            # the coverage, term by term; writes nothing
    python3 src/parse/build_past_roster.py --apply    # writes generated/past_roster.json

No network, no hand data. A person's run, like build_careers.py: the file is rewritten whole
from the inputs below, never edited, and git keeps it.

    db/past/PastSponsors.psv, PastLegislation.psv   who sponsored each bill, by employee number
    data/bills.json                                  the LSR each bill is filed under
    past_members.json, db/Legislators.psv            the name the General Court gives a number
    text_sponsors.json                               the seat each bill PRINTED for each sponsor
                                                     (past_roster.py placed them; run
                                                     text_sponsors.py --apply first)
    generated/careers.json                           who cast a roll call from 1999 on

WHAT A ROW IS. One person in one chamber in one term, from the sponsor route: someone with a live
sponsor row on a bill of the term. `gc_employee_number` is the General Court's number for them,
unchanged; `granite_id` is Granite Record's own (gr-NNNN, generated/gr_ids.json) and is set only
for a person the record names with no General Court number, in which case the first is empty.
The two are never written into each other's field (src/lib/gr_ids.py). `person` is the key the
row is filed under: the employee number wherever there is one.

WHAT IT IS NOT. It is not the roster. A House of 400 is not read off sponsorship: someone who
sponsored nothing in the term has no row, and a seat is only the one(s) a bill printed. The
coverage printed against 400 House and 24 Senate seats says how far it falls short, term by term.
The chamber of a person none of the term's bills printed is the list of members' (the last seat
they held), marked as that. No party: nothing here states one.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
from collections import Counter, defaultdict

import gr_ids as GR
import past_members
import past_roll as ROLL
import past_roster as PR
import past_sponsors as PSP

OUT = Path("generated/past_roster.json")
CAREERS = Path("generated/careers.json")
TEXT = Path("text_sponsors.json")
SEATS = {"H": 400, "S": 24}
SOURCE = ("General Court sponsor record (PastSponsors), by the bill's stored LSR; the seat is the one "
          "the bill printed")
LIST_NAME = "General Court list of members (past_members.json)"
TABLE_NAME = "General Court legislators table (Legislators.psv)"
ROLL_SOURCE = "House Journal call of the roll (a second source; no sponsor row of the term)"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def name_source(emp, people):
    """(name, where it is from) for an employee number: the General Court's list of members,
    else its legislators table, else ("", "")."""
    pm = people.pm.get(emp)
    if pm:
        return PR.full_name(f"{pm[1]}, {pm[2]}"), LIST_NAME
    if emp in people.leg:
        last, first, _ch = people.leg[emp]
        return " ".join(x for x in (first, last) if x), TABLE_NAME
    return "", ""


def chamber_of(emp, people):
    pm = people.pm.get(emp)
    return pm[0] if pm and pm[0] in ("H", "S") else (people.leg.get(emp) or ("", "", ""))[2]


def rows_of(joined, text, people, voters, terms=PR.PRE_TERMS):
    """[row] for the sponsor route, in (term, chamber, employee number) order."""
    out = []
    for term in terms:
        sponsored = defaultdict(set)
        for bid, v in (joined.get(term) or {}).items():
            for r in v["rows"]:
                if not r["withdrawn"] and r["employee"]:
                    sponsored[r["employee"]].add(bid)
        seats = defaultdict(Counter)      # (employee, chamber) -> {(county, district): bills}
        printed = defaultdict(set)        # (employee, chamber) -> {bill}
        for bid, recs in (text.get(term) or {}).items():
            for rec in recs:
                emp = rec.get("employee")
                if not emp or rec.get("matched") != PR.MATCHED:
                    continue
                ch = (rec.get("chamber") or "")[:1]
                seats[(emp, ch)][(rec.get("county") or "", rec.get("district") or "")] += 1
                printed[(emp, ch)].add(bid)
        for emp in sorted(sponsored, key=int):
            nm, where = name_source(emp, people)
            chambers = sorted({ch for (e, ch) in printed if e == emp and ch}) or [""]
            for ch in chambers:
                row = {"term": term, "chamber": ch or chamber_of(emp, people),
                       "person": emp, "gc_employee_number": emp, "granite_id": "",
                       "name": nm, "name_source": where,
                       "seats": [{"county": c, "district": d, "bills": n}
                                 for (c, d), n in sorted(seats[(emp, ch)].items(),
                                                         key=lambda kv: (-kv[1], kv[0]))],
                       "chamber_source": ("the bill's printed sponsor line" if ch
                                          else "the list of members: the last seat they held"),
                       "bills": len(sponsored[emp]), "bills_printed": len(printed[(emp, ch)]),
                       "voted_since_1999": emp in voters, "source": SOURCE}
                pm = people.pm.get(emp)
                # The General Court's own note that two of its numbers are one person
                # ("Dykstra (SEE Emp #375839), Leona"); the second is not made a key here.
                see = PR.split_label(f"{pm[1]}, {pm[2]}")[3] if pm else ""
                if see:
                    row["same_person_as_employee_number"] = see
                out.append(row)
    out.sort(key=lambda r: (r["term"], r["chamber"], int(r["person"])))
    return out


def add_roll(rows, got, people, voters):
    """(rows with the call of the roll merged in, [seat disagreements], [roll names placed on nobody]).

    `got` is past_roll.survey's {volume: [(entry, state, employee)]}. A name the roll places on a person
    who has a row for that term in the House gets the volume and the seat the roll gave, and a note of
    whether a printed seat could be compared; one it places on a person with no row for the term (a House
    member who sponsored nothing) gets a row of their own, from the roll alone, in the House; a name whose
    seat contradicts the person's printed one, and a name placed on nobody, are listed and attached to no
    one. Party is not read: the roll prints a nominating party and none is given before 1999."""
    rows = [dict(r) for r in rows]
    by = {(r["term"], r["chamber"], r["person"]): r for r in rows}
    clash, loose = [], []
    for fn, res in got.items():
        term, year = ROLL.VOLUMES[fn]
        for en, state, emp in res:
            if state == "placed":
                r = by.get((term, "H", emp))
                if r is None:
                    nm, where = name_source(emp, people)
                    r = by[(term, "H", emp)] = {
                        "term": term, "chamber": "H", "person": emp, "gc_employee_number": emp,
                        "granite_id": "", "name": nm, "name_source": where, "seats": [],
                        "chamber_source": "the call of the roll", "bills": 0, "bills_printed": 0,
                        "voted_since_1999": emp in voters, "source": ROLL_SOURCE}
                    rows.append(r)
                r.setdefault("roll", []).append(
                    {"volume": year, "county": en["county"], "district": en["district"],
                     "seat_checked_against_a_printed_seat": bool(r["seats"])})
                if r["source"] == ROLL_SOURCE and not any(
                        s["county"] == en["county"] and s["district"] == en["district"] for s in r["seats"]):
                    r["seats"].append({"county": en["county"], "district": en["district"], "bills": 0})
            elif state == "seat differs":
                clash.append({"term": term, "volume": year, "roll_name": en["name"],
                              "roll_seat": [en["county"], en["district"]], "gc_employee_number": emp,
                              "printed_seats": [[s["county"], s["district"]]
                                                for r in rows if r["person"] == emp and r["term"] == term
                                                for s in r["seats"]]})
            else:
                loose.append({"term": term, "volume": year, "roll_name": en["name"],
                              "roll_seat": [en["county"], en["district"]], "why": state})
    rows.sort(key=lambda r: (r["term"], r["chamber"], int(r["person"])))
    return rows, clash, loose


def coverage(rows, terms=PR.PRE_TERMS):
    """{term: {chamber: {people, printed_a_seat, seats, nameless}}}: people against the chamber's
    seats (400 House, 24 Senate), how many have a seat a bill printed, how many seats' worth of
    distinct districts those printed, and how many the General Court's lists give no name."""
    cov = {}
    for term in terms:
        cov[term] = {}
        for ch in ("H", "S"):
            rs = [r for r in rows if r["term"] == term and r["chamber"] == ch]
            districts = {(s["county"], s["district"]) for r in rs for s in r["seats"]}
            cov[term][ch] = {"people": len(rs), "of_seats": SEATS[ch],
                             "with_a_printed_seat": sum(1 for r in rs if r["seats"]),
                             "districts_printed": len(districts),
                             "roll_only": sum(1 for r in rs if r["source"] == ROLL_SOURCE),
                             "nameless": sum(1 for r in rs if not r["name"])}
        cov[term]["no_chamber"] = sum(1 for r in rows if r["term"] == term and r["chamber"] not in ("H", "S"))
    return cov


def build(bills, joined, text, people, voters, register=None, roll=None):
    """The document generated/past_roster.json holds. `roll` is past_roll.survey's answer, or None
    where the volumes are not on this disk: the table is then the sponsor route's alone."""
    rows = rows_of(joined, text, people, voters)
    clash, loose = [], []
    if roll:
        rows, clash, loose = add_roll(rows, roll, people, voters)
    bad = GR.check_rows(rows, reg=register if register is not None else {"ids": []})
    if bad:
        raise SystemExit("The table puts an identifier in the wrong place:\n  " + "\n  ".join(bad[:10]))
    return {"format": 1,
            "what": ("Who sponsored a bill in each term from 1989 to 1998, by chamber, from the General "
                     "Court's sponsor record: their employee number (gc_employee_number, the General "
                     "Court's, unchanged), the name its list of members gives, and the seat each bill "
                     "printed. Not a roster: a member who sponsored nothing has no row. A person the "
                     "record names with no employee number has a Granite Record id (granite_id, gr- "
                     "and a serial) in its own field instead; none yet."),
            "source": SOURCE, "coverage": coverage(rows), "rows": rows,
            "roll_seat_disagreements": clash, "roll_names_placed_on_nobody": loose}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write " + OUT.as_posix())
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for need in (PSP.PAST / "_manifest.json", PSP.BILLS, TEXT, CAREERS, PSP.PAST_MEMBERS):
        if not Path(need).exists():
            sys.exit(f"{need} is not here; nothing is written from part of the inputs.")
    bills = _load(PSP.BILLS)
    missing = [t for t in PR.PRE_TERMS if t not in bills]
    if missing:
        sys.exit(f"data/bills.json lacks {missing}; a table of some terms would replace the rest.")
    joined, _ = PSP.join(bills, PSP.read_view("PastSponsors"), PSP.read_view("PastLegislation"))
    text = _load(TEXT)
    if not any(r.get("matched") == PR.MATCHED for t in PR.PRE_TERMS
               for recs in (text.get(t) or {}).values() for r in recs):
        sys.exit(f"{TEXT} holds no sponsor placed by past_roster.py: run text_sponsors.py --apply first.")
    people = PSP.People(PSP.read_legislators() if PSP.LEGISLATORS.exists() else [],
                        past_members.roster(PSP.PAST_MEMBERS))
    voters = {e for c in _load(CAREERS).values() for e in c.get("employee_nos") or []}
    roll = ROLL.survey(rows_of(joined, text, people, voters), people) if ROLL.ROLL.is_dir() else None
    doc = build(bills, joined, text, people, voters, GR.load_register(), roll)
    print(f"{len(doc['rows']):,} person-terms, {len({r['person'] for r in doc['rows']}):,} people")
    print(f"{'term':<11}{'House':>7}{'/400':>6}{'seat':>6}{'dist':>6}{'roll':>6} |{'Senate':>7}{'/24':>5}{'seat':>6} |"
          f"{'no chamber':>11}{'nameless':>9}")
    for term, c in doc["coverage"].items():
        h, s = c["H"], c["S"]
        print(f"{term:<11}{h['people']:>7}{'':>6}{h['with_a_printed_seat']:>6}{h['districts_printed']:>6}{h['roll_only']:>6} |"
              f"{s['people']:>7}{'':>5}{s['with_a_printed_seat']:>6} |{c['no_chamber']:>11}"
              f"{h['nameless'] + s['nameless']:>9}")
    if a.apply:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwritten {OUT}")


if __name__ == "__main__":
    main()
