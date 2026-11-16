#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.3
"""
The register of Granite Record's own ids (generated/gr_ids.json): issuing one, and recording an
official number found later.

    python3 src/ops/gr_register.py                            # what the register holds; writes nothing
    python3 src/ops/gr_register.py --issue "Jane Doe" --evidence "House roll of 1995, Hills 12; no
                                                  employee number in any list on disk"
    python3 src/ops/gr_register.py --found gr-0001 373027     # the General Court's number for gr-0001
    python3 src/ops/gr_register.py --offices                  # who the first offices' ids would go
                                                              #   to, and the ids; writes nothing
    python3 src/ops/gr_register.py --offices --apply          # issue them

No network. A person's run, as src/ops/person_numbers.py --issue is: the nightly reads the
register and never writes it (preflight holds that), and an id once issued is never renumbered,
reissued or deleted (src/lib/gr_ids.py says what the register is, and why the ids are kept apart
from the General Court's numbers).

--issue gives the next serial to a named person. It is never automatic: whether someone the record
names has no General Court number is a person's judgement, made with the evidence, and the
evidence is kept in the entry. --found records the General Court's employee number against an
existing id -- the one change an entry may take. From then on the official number is the person's
key, and the gr- id is kept as an alias; the tables that carry the id say so.

--offices is the owner's decision of 16 November 2026 (the model's question 3): a gr- id for each
holder of the first offices with pages -- the Governor, the Council, Congress, the Secretary of
State, the Treasurer, the Attorney General, and each one's successor -- whom the model links to
no person of the record (build_entities.gr_candidates, which builds the model whole first). A
holder the model links is left out before any id is offered: by the hand file's member page, an
id the register issued for the place, the owner's hand file of links, or the rule of
src/parse/office_links.py -- on 16 November, Joseph D. Kenney, Luz Bay, Melanie Levesque and
Jeanne Shaheen, whom the hand file alone left unlinked. Where the model cannot say whom it links
(the files it is built from, or the rule's evidence, not all here) nothing is offered, and it
says why. Alone it lists them with the ids they would get and writes nothing; with --apply it
issues them, each entry naming the place in the hand file it was issued for ("issued_for"),
which is how the model (src/parse/build_entities.py) puts the id on that holder's tenure, and on
no other: it links an id to the holder of the place it was issued for, under the name it was
issued to, never by a name alone. A name two of the places share gets no id from --offices: one
person in two places is one id, and a name cannot say whether it is one person, so a person
issues it, `--issue NAME --evidence ... --for officials:<path> --for officials:<path>`, or one
for each. Look first: a holder on the owner's list to settle is offered one, and if she links
them to a member later they take that member's number instead, the id staying as their alias.
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


def offices(reg, day, apply=False, root="."):
    """[(id or None, candidate)]: the first offices' holders the model links to no person of the
    record and the register holds no id for (build_entities.gr_candidates), each with the id it
    gets -- issued into `reg`, with the place it was issued for, only where `apply`.
    build_entities.Refused where the model cannot say whom it links, and nothing is offered.

    A NAME TWO PLACES SHARE GETS NO ID HERE (None). One person in two places -- a member of the
    US House who is the US Senate's successor -- is one id, and two people of one name are two;
    a name cannot say which, so neither is issued, and a person issues one by hand for both
    places (--issue NAME --for PLACE --for PLACE) or one for each."""
    import build_entities as BE
    cands = BE.gr_candidates(root, register=reg)
    said = [" ".join(c["name"].split()).lower() for c in cands]
    out = []
    work = reg if apply else json.loads(json.dumps(reg))
    for c, name in zip(cands, said):
        if said.count(name) > 1:
            out.append((None, c))
            continue
        new = issue(work, c["name"], c["evidence"], day)
        work["ids"][-1]["issued_for"] = c["tenure"]
        out.append((new, c))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", metavar="NAME", help="issue the next id to this person")
    ap.add_argument("--evidence", default="", help="why they have no General Court number (with --issue)")
    ap.add_argument("--found", nargs=2, metavar=("GR_ID", "NUMBER"),
                    help="record the General Court's employee number for an id")
    ap.add_argument("--for", dest="places", action="append", default=[], metavar="PLACE",
                    help="with --issue: a place in the hand file the id is issued for "
                         "(officials:<path>, as --offices prints it); again for a second")
    ap.add_argument("--offices", action="store_true",
                    help="the first offices' holders with no General Court record, and the ids they "
                         "would get; writes nothing without --apply")
    ap.add_argument("--apply", action="store_true", help="with --offices: issue them")
    a = ap.parse_args()
    if a.apply and not a.offices:
        ap.error("--apply goes with --offices")
    if a.places and not a.issue:
        ap.error("--for goes with --issue")
    reg = GR.load_register() or {"format": GR.FORMAT, "ids": []}
    if a.offices:
        import build_entities as BE
        try:
            got = offices(reg, build_date.today().isoformat(), apply=a.apply)
        except BE.Refused as e:
            raise SystemExit(f"No id offered and nothing written: {e}")
        for new, c in got:
            print(f"  {new or '(none)':<8} {c['name']:<28} {c['tenure']}"
                  + ("" if new else "   a name two places share: a person issues it, for one "
                                    "place or both (--issue --for)"))
        n = sum(1 for new, _c in got if new)
        if a.apply and n:
            write(reg)
            print(f"issued {n} id(s) into {GR.REGISTER.as_posix()}")
        else:
            print(f"{n} holder(s) of the first offices would get an id and {len(got) - n} wait for a "
                  "person; nothing written" + ("" if a.apply else " (--apply issues them)"))
    elif a.issue:
        new = issue(reg, a.issue, a.evidence, build_date.today().isoformat())
        if a.places:
            reg["ids"][-1]["issued_for"] = a.places[0] if len(a.places) == 1 else list(a.places)
        write(reg)
        print(f"issued {new} to {a.issue}" + (f", for {', '.join(a.places)}" if a.places else ""))
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
