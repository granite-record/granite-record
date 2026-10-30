#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.1
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
that), and publishes anybody it does not hold yet as provisional.

WHAT --issue DOES, AND WHAT IT LEAVES FOR A PERSON

  adds     a person for every provisional group, numbered "p" and its first
           Employeeno; and an issued person's numbers that the register does
           not hold yet (a member's new number after a chamber change)
  never    changes or removes an issued number, merges two issued people or
           splits one. Those are printed, with the join's reasons, for a
           person to make by hand in the register: a merge keeps the earlier
           number and gives the other "replaced_by"; a split keeps the number
           with the Employeeno it was first issued for and gives the other a
           new number with "split_from". The design says why.

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
    if not path.exists():
        return {"format": PE.FORMAT, "people": []}
    return json.loads(path.read_text(encoding="utf-8"))


def check_register(reg):
    """Problems with the register's own shape: a person twice, a number held
    by two people. Returns a list of sentences; empty is well formed."""
    bad, seen_p, seen_n = [], set(), {}
    for e in reg.get("people") or []:
        p = e.get("person")
        if not p or not str(p).startswith("p"):
            bad.append(f"an entry with no person number: {e}")
            continue
        if p in seen_p:
            bad.append(f"{p} is issued twice")
        seen_p.add(p)
        for n in e.get("numbers") or []:
            if n in seen_n:
                bad.append(f"{n} is held by {seen_n[n]} and {p}")
            seen_n[n] = p
        if e.get("replaced_by") and e.get("numbers"):
            bad.append(f"{p} is replaced and still holds numbers")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", action="store_true", help="write the register")
    ap.add_argument("--site", default="site")
    ap.add_argument("--data", default="data")
    ap.add_argument("--db", default="db")
    ap.add_argument("--careers", default="generated/careers.json")
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
    new = rep["provisional"]
    more = [u for u in rep["unissued_numbers"] if u.get("person")]
    print(f"  to issue: {len(new):,} new people, {len(more):,} new numbers of issued people")
    for g in new[:15]:
        print(f"    {g['person']}  {g['numbers']}")
    if len(new) > 15:
        print(f"    ... and {len(new) - 15:,} more")

    if not a.issue:
        print("\nNothing written. --issue writes these to the register.")
        return
    day = build_date.today().isoformat()
    by_person = {e["person"]: e for e in reg.setdefault("people", [])}
    for g in new:
        if g["person"] in by_person:
            raise SystemExit(f"{g['person']} is already issued to someone else; "
                             "a person must choose this one's number by hand.")
        e = {"person": g["person"], "numbers": g["numbers"], "issued": day}
        reg["people"].append(e)
        by_person[g["person"]] = e
    for u in more:
        by_person[u["person"]]["numbers"] = sorted(set(by_person[u["person"]]["numbers"]) | {u["number"]})
    reg["format"] = PE.FORMAT
    reg["people"].sort(key=lambda e: e["person"])
    bad = check_register(reg)
    if bad:
        raise SystemExit("Refusing to write a register that is not well formed:\n  " + "\n  ".join(bad))
    REGISTER.parent.mkdir(parents=True, exist_ok=True)
    REGISTER.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {REGISTER}: {len(reg['people']):,} people.")


if __name__ == "__main__":
    main()
