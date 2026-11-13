#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.1
"""
The register of Granite Record's own ids (generated/gr_ids.json): issuing one, and recording an
official number found later.

    python3 src/ops/gr_register.py                            # what the register holds; writes nothing
    python3 src/ops/gr_register.py --issue "Jane Doe" --evidence "House roll of 1995, Hills 12; no
                                                  employee number in any list on disk"
    python3 src/ops/gr_register.py --found gr-0001 373027     # the General Court's number for gr-0001

No network. A person's run, as src/ops/person_numbers.py --issue is: the nightly reads the
register and never writes it (preflight holds that), and an id once issued is never renumbered,
reissued or deleted (src/lib/gr_ids.py says what the register is, and why the ids are kept apart
from the General Court's numbers).

--issue gives the next serial to a named person. It is never automatic: whether someone the record
names has no General Court number is a person's judgement, made with the evidence, and the
evidence is kept in the entry. --found records the General Court's employee number against an
existing id -- the one change an entry may take. From then on the official number is the person's
key, and the gr- id is kept as an alias; the tables that carry the id say so.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json

import build_date
import gr_ids as GR


def write(reg, path=GR.REGISTER):
    bad = GR.check_register(reg)
    if bad:
        raise SystemExit("Refusing to write a register that is not well formed:\n  " + "\n  ".join(bad))
    Path(path).write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def issue(reg, name, evidence, day):
    """The register with one more id, issued to `name`; the id is returned beside it."""
    name = " ".join((name or "").split())
    if not name or not (evidence or "").strip():
        raise SystemExit("--issue needs the person's name and the evidence for it.")
    new = GR.next_id(reg)
    reg.setdefault("ids", []).append({"id": new, "named_as": name, "issued": day,
                                      "evidence": evidence.strip(), "employee_number": ""})
    return new


def found(reg, gid, number):
    """Record `number`, the General Court's, for `gid`. Never over a number already recorded."""
    if not GR.looks_official(number):
        raise SystemExit(f"{number!r} is not an employee number: digits only.")
    e = next((x for x in reg.get("ids") or [] if x.get("id") == gid), None)
    if e is None:
        raise SystemExit(f"{gid} is not in the register.")
    if e.get("employee_number") and e["employee_number"] != number:
        raise SystemExit(f"{gid} already holds {e['employee_number']}; a recorded number is not changed.")
    e["employee_number"] = number


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", metavar="NAME", help="issue the next id to this person")
    ap.add_argument("--evidence", default="", help="why they have no General Court number (with --issue)")
    ap.add_argument("--found", nargs=2, metavar=("GR_ID", "NUMBER"),
                    help="record the General Court's employee number for an id")
    a = ap.parse_args()
    reg = GR.load_register() or {"format": GR.FORMAT, "ids": []}
    if a.issue:
        new = issue(reg, a.issue, a.evidence, build_date.today().isoformat())
        write(reg)
        print(f"issued {new} to {a.issue}")
    elif a.found:
        found(reg, *a.found)
        write(reg)
        print(f"{a.found[0]} now holds the General Court's number {a.found[1]}; it is their key, "
              f"and {a.found[0]} stays as an alias")
    else:
        print(f"{len(reg['ids'])} Granite Record id(s) issued; the next is {GR.next_id(reg)}")
        for e in reg["ids"]:
            print(f"  {e['id']}  {e['named_as']}  {e.get('employee_number') or '(no General Court number)'}")


if __name__ == "__main__":
    main()
