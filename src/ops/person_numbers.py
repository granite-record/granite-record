#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.5
"""
The register of person numbers: what it would issue, and issuing it.

    python3 src/ops/person_numbers.py              # what tonight's join says, and what
                                                   # an issue would add; writes nothing
    python3 src/ops/person_numbers.py --issue      # add those to the register

Run from the repository root, after a build (it reads site/ and data/ as the
build left them, db/ and generated/careers.json). No network.

WHY A REGISTER (docs/design/api/DESIGN.md, 2.5; the owner's decision of 30
October 2026, Q14). A person number published in /data/people.json is
something other sites store. Worked out afresh each night from the joins, it
would move whenever a join is corrected -- and joins are corrected: the first
prototype gave Sen. Pat Long's House number to a freshman. So a number is
issued once, here, by a person's run, into generated/person_numbers.json,
which git keeps. The nightly reads it and never writes it (preflight holds
that), and numbers anybody it does not hold yet by the rule, the same night
(people.py says how).

WHAT --issue DOES, AND WHAT IT LEAVES FOR A PERSON

  adds     every person the night numbered by the rule people.py states
           (their earliest General Court PersonID, else their earliest
           employee number), so that the number is frozen; and an issued person's numbers that the register does
           not hold yet (a member's new number after a chamber change)
  never    issues a provisional number (one made here, for a person the
           General Court numbers nowhere this site can read), issues a number
           someone already holds, changes or removes an issued number, merges two issued people or
           splits one. Those are printed, with the join's reasons, for a
           person to make by hand in the register: a merge keeps the earlier
           number and gives the other "replaced_by"; a split keeps the number
           with the Employeeno it was first issued for and gives the other a
           new number with "split_from". The design says why.

  refuses  a group the joins put together with two numbers of one chamber
           (two people, by member_links.py's first rule), and a person
           numbered by an employee number who sits in the newest term: the
           roster dump not naming a sitting member is a stale dump, and their
           PersonID will come with the next one.

    --except PERSON     do not issue this person (repeatable): the owner holds
                        someone back while a question about them is open,
                        and the night goes on numbering them by the rule
    --only-person-ids   issue only the people numbered by a PersonID, and
                        leave those numbered by an employee number to the
                        nightly's rule, unfrozen (an employee number is a
                        person's number only for want of a link to their
                        PersonID; people.py says why)

It prints everything it found before it writes, and writes nothing on a run
without --issue.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json

import build_date
import people as PE

REGISTER = Path("generated/person_numbers.json")


def load_register(path=REGISTER):
    return PE.load_register(path) or {"format": PE.FORMAT, "people": []}


def check_register(reg):
    """The register's shape (people.check_register, one rule for the build
    and for this)."""
    return PE.check_register(reg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", action="store_true", help="write the register")
    ap.add_argument("--site", default="site")
    ap.add_argument("--data", default="data")
    ap.add_argument("--db", default="db")
    ap.add_argument("--careers", default="generated/careers.json")
    ap.add_argument("--except", dest="exempt", action="append", default=[],
                    metavar="PERSON", help="do not issue this person (repeatable)")
    ap.add_argument("--only-person-ids", action="store_true",
                    help="issue only people numbered by a PersonID")
    a = ap.parse_args()

    reg = load_register()
    bad = check_register(reg)
    if bad:
        raise SystemExit("The register is not well formed; fix it by hand first:\n  "
                         + "\n  ".join(bad))
    careers = json.loads(Path(a.careers).read_text(encoding="utf-8"))
    if PE.emp_to_pid(a.db) is None:
        raise SystemExit(f"No roster view in {a.db}/ (Legislators.psv): run after kit-down.")
    people, rep = PE.build(a.site, a.data, a.db, careers, reg)
    if not any(p.get("member_ids") for p in people):
        raise SystemExit("No person carries a site id: is site/ built? Nothing issued.")

    print(f"Tonight's join: {len(people):,} people; the register holds "
          f"{len(reg.get('people') or []):,}.")
    for c in rep["careers_not_joined"]:
        print(f"  not joined, for a person to look at: {c['name']} {c['numbers']}: {c['why']}")
    for d in rep["register_disagrees"]:
        print(f"  the register disagrees with tonight, left for a person: {d}")
    if rep["unknown_ids"]:
        print(f"  {len(rep['unknown_ids'])} site id(s) stand for no Employeeno or PersonID "
              f"the roster knows: {rep['unknown_ids'][:10]}")
    new = rep["by_rule"]
    unknown = [x for x in a.exempt if x not in {g["person"] for g in new}]
    if unknown:
        raise SystemExit(f"--except names no one tonight's join would issue: {', '.join(unknown)}")
    newest = max((t for p in people for t in [p.get("last_term") or ""]), default="")
    held_back = {}
    split = {tuple(sorted(g["numbers"])) for g in rep.get("one_chamber") or []}
    for g in rep.get("one_chamber") or []:
        print(f"  REFUSED, two numbers of one chamber in one group: {g['numbers']} {g['same_chamber']}")
    by_person = {p["person"]: p for p in people}
    for g in new:
        p = by_person.get(g["person"]) or {}
        emps = tuple(sorted(n for n in g["numbers"] if not n.startswith("m")))
        if emps in split:
            held_back[g["person"]] = "two numbers of one chamber"
        elif not p.get("person_ids") and p.get("last_term") == newest:
            held_back[g["person"]] = "sits in the newest term with no PersonID: a stale roster dump"
        elif g["person"] in a.exempt:
            held_back[g["person"]] = "held back by --except"
        elif a.only_person_ids and not p.get("person_ids"):
            held_back[g["person"]] = "numbered by an employee number (--only-person-ids)"
    for person, why in sorted(held_back.items()):
        if not why.startswith("numbered by an employee"):
            print(f"  not issued: {person}: {why}")
    if rep.get("missing_issued"):
        print(f"  WARNING: {len(rep['missing_issued'])} issued person(s) not in tonight's record: "
              f"{rep['missing_issued'][:10]}")
    for c in rep["clashes"]:
        print(f"  REFUSED, a number someone already holds: {c['person']} for {c['numbers']}")
    if rep["provisional"]:
        print(f"  not issued, provisional: {len(rep['provisional'])} with no General Court "
              f"number this site can read: {[g['numbers'] for g in rep['provisional'][:5]]}")
    bad = PE.check_unique(people)
    if bad:
        raise SystemExit("Tonight's people hold a number twice; nothing issued:\n  " + "\n  ".join(bad[:10]))
    more = [u for u in rep["unissued_numbers"] if u.get("person")]
    for u in more:
        print(f"    a new number for issued person {u['person']}: {u['number']} "
              "(a person should be sure it is theirs: the join may be by name alone)")
    print(f"  to issue: {len(new):,} new people, {len(more):,} new numbers of issued people")
    kinds = {"PersonID": 0, "employee number": 0}
    for g in new:
        kinds["employee number" if g["person"] in g["numbers"] else "PersonID"] += 1
    print(f"    numbered by a PersonID: {kinds['PersonID']:,}; by an employee number: "
          f"{kinds['employee number']:,}; made here: 0")
    for g in new:
        print(f"    {g['person']:>8}  {', '.join(g['numbers'])}")

    print(f"  an issue would freeze {len(new) - len(held_back):,} of {len(new):,}; "
          f"{len(held_back):,} held back")
    if not a.issue:
        print("\nNothing written. --issue writes these to the register.")
        return
    day = build_date.today().isoformat()
    issuing = [g for g in new if g["person"] not in held_back]
    print(f"  issuing {len(issuing):,} of {len(new):,}; {len(held_back):,} held back")
    by_person = {e["person"]: e for e in reg.setdefault("people", [])}
    for g in issuing:
        if g["person"] in by_person:
            raise SystemExit(f"{g['person']} is already issued to someone else; "
                             "a person must choose this one's number by hand.")
        e = {"person": g["person"], "numbers": g["numbers"], "issued": day}
        reg["people"].append(e)
        by_person[g["person"]] = e
    for u in more:
        by_person[u["person"]]["numbers"] = sorted(set(by_person[u["person"]]["numbers"]) | {u["number"]})
    reg["format"] = PE.FORMAT
    reg["people"].sort(key=lambda e: PE.person_key(e["person"]))
    bad = check_register(reg)
    if bad:
        raise SystemExit("Refusing to write a register that is not well formed:\n  " + "\n  ".join(bad))
    REGISTER.parent.mkdir(parents=True, exist_ok=True)
    REGISTER.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {REGISTER}: {len(reg['people']):,} people.")


if __name__ == "__main__":
    main()
