#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.1
"""
Granite Record's own identifiers, kept apart from the General Court's.

    import gr_ids as GR
    GR.load_register(path)          # the register, or None
    GR.check_register(reg)          # problems with its shape, as sentences
    GR.check_rows(rows, known)      # problems with a published table's identifier fields
    GR.check_only_grows(then, now)  # problems with a register that lost or moved an id

THE TWO KINDS (the owner, 13 November 2026: "distinguish the IDs assigned by
Granite Record from the official ones so that the two don't get mixed up").

  the General Court's employee number   digits only, e.g. 373027. Official:
                                        the General Court issued it, this site
                                        copies it unchanged, and wherever the
                                        General Court supplies one it is the
                                        person's key.
  Granite Record's id                   `gr-` and a four-digit serial, e.g.
                                        gr-0001. Made here, only for a person
                                        the record names and the General Court
                                        gives no number this site can read.
                                        It can never be taken for an employee
                                        number: it is not digits only, and it
                                        starts with a prefix no number has.

They live in SEPARATE FIELDS, always: `gc_employee_number` and `granite_id`.
Neither is ever written into the other's field, and a page or a file that
shows one says which kind it is.

THE REGISTER (generated/gr_ids.json) is kept the way generated/person_numbers.json
is: entries are only ever added, by a person's run (src/ops/gr_register.py --issue),
the nightly reads it and never writes it, and an id once issued is never
renumbered, reissued or deleted. If the General Court's number for someone
holding a gr- id is found later, `employee_number` is filled in on their entry
-- the one change an entry may take -- the official number becomes the person's
key, and the gr- id stays on, as an alias. That is the whole of what the
register holds:

    {"format": 1,
     "ids": [{"id": "gr-0001", "named_as": "Jane Doe", "issued": "2026-11-13",
              "evidence": "...", "employee_number": "" | "373027"}]}
"""

import json
import re
from pathlib import Path

FORMAT = 1
PREFIX = "gr-"
GR_RE = re.compile(r"^gr-\d{4,}$")
OFFICIAL_RE = re.compile(r"^\d+$")
REGISTER = Path("generated/gr_ids.json")


def is_gr(x):
    """Is x one of Granite Record's own ids?"""
    return bool(GR_RE.match(str(x or "")))


def looks_official(x):
    """Does x have the shape of one of the General Court's numbers: digits only?"""
    return bool(OFFICIAL_RE.match(str(x or "")))


def next_id(reg):
    """The next serial the register would issue: one past its highest."""
    top = max((int(e["id"][len(PREFIX):]) for e in (reg or {}).get("ids") or []
               if is_gr(e.get("id"))), default=0)
    return f"{PREFIX}{top + 1:04d}"


def load_register(path=REGISTER):
    """The register at path: None where there is none; the register where it reads and is well
    formed; and otherwise a stop, because a register that cannot be read would quietly stop
    the ids it holds from being used."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        reg = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"{path} does not read as JSON ({e}); nothing is built without it.")
    bad = check_register(reg)
    if bad:
        raise SystemExit(f"{path} is not well formed:\n  " + "\n  ".join(bad[:10]))
    return reg


def check_register(reg):
    """Problems with a register's own shape, as sentences; empty is well formed."""
    if not isinstance(reg, dict) or not isinstance(reg.get("ids"), list):
        return ["the register is not an object with a list of ids"]
    bad, seen, serials = [], set(), []
    for e in reg["ids"]:
        if not isinstance(e, dict):
            bad.append(f"an entry that is not an object: {e!r}")
            continue
        i = str(e.get("id") or "")
        if not is_gr(i):
            bad.append(f"{i or 'an entry'}: an id that is not gr- and a serial"
                       + (" (an employee number is the General Court's, never issued here)"
                          if looks_official(i) else ""))
            continue
        if i in seen:
            bad.append(f"{i} is issued twice")
        seen.add(i)
        serials.append(int(i[len(PREFIX):]))
        if not (e.get("named_as") or "").strip():
            bad.append(f"{i} is issued to nobody by name")
        emp = str(e.get("employee_number") or "")
        if emp and not looks_official(emp):
            bad.append(f"{i} holds {emp!r} as an employee number, which is digits only")
        if is_gr(emp):
            bad.append(f"{i} holds a gr- id in the employee-number field")
    if serials != sorted(serials):
        bad.append("the ids are not in the order they were issued")
    held = [str(e.get("employee_number")) for e in reg["ids"] if e.get("employee_number")]
    for n in sorted({n for n in held if held.count(n) > 1}):
        bad.append(f"employee number {n} is held by two ids")
    return bad


def check_only_grows(then, now):
    """Problems with `now` against an earlier copy `then`: an id gone, an id issued to another
    name or on another day, an employee number once recorded changed or removed. A newly
    recorded employee number is the one change allowed."""
    here = {e.get("id"): e for e in (now or {}).get("ids") or []}
    bad = []
    for e in (then or {}).get("ids") or []:
        h = here.get(e.get("id"))
        if h is None:
            bad.append(f"{e.get('id')} is gone")
            continue
        for k in ("named_as", "issued"):
            if h.get(k) != e.get(k):
                bad.append(f"{e['id']}'s {k} changed from {e.get(k)!r} to {h.get(k)!r}")
        if e.get("employee_number") and h.get("employee_number") != e["employee_number"]:
            bad.append(f"{e['id']}'s employee number changed from {e['employee_number']!r} "
                       f"to {h.get('employee_number')!r}")
    return bad


def check_rows(rows, known=None, reg=None):
    """Problems with a table of people, each row a dict with `gc_employee_number` and
    `granite_id` (and, for a person the register has since found an official number for,
    `granite_id_aliases`), `person` being the key the row is filed under.

      - a gr- id in the employee-number field, or an employee number in the id field;
      - an employee number that is not digits only, or (when `known`, the set of numbers the
        General Court's own files name, is given) digits only and not among them;
      - a row with both, or neither, set;
      - a row keyed by a gr- id whose register entry holds an official number: the official
        number is the key, and the gr- id an alias;
      - a gr- id the register does not hold.
    Empty is right."""
    held = {e["id"]: e for e in (reg or {}).get("ids") or []} if reg is not None else None
    bad = []
    for r in rows:
        emp, gid = str(r.get("gc_employee_number") or ""), str(r.get("granite_id") or "")
        who = r.get("name") or r.get("person") or "a row"
        if is_gr(emp):
            bad.append(f"{who}: a gr- id ({emp}) sits in the employee-number field")
        elif emp and not looks_official(emp):
            bad.append(f"{who}: {emp!r} in the employee-number field is not digits only")
        elif emp and known is not None and emp not in known:
            bad.append(f"{who}: {emp} is digits only and no list of the General Court's names it")
        if gid and looks_official(gid):
            bad.append(f"{who}: an employee number ({gid}) sits in the Granite Record id field")
        elif gid and not is_gr(gid):
            bad.append(f"{who}: {gid!r} in the Granite Record id field is not gr- and a serial")
        if bool(emp) == bool(gid):
            bad.append(f"{who}: " + ("both an employee number and a Granite Record id"
                                     if emp else "neither an employee number nor a Granite Record id"))
        if is_gr(str(r.get("person") or "")):
            e = (held or {}).get(r["person"])
            if emp or (e or {}).get("employee_number"):
                bad.append(f"{who}: keyed by {r['person']}, though the General Court's number for "
                           f"them is known ({emp or e.get('employee_number')}): the number is the key")
        elif r.get("person") not in (None, "", emp):
            bad.append(f"{who}: keyed by {r['person']!r}, which is not their employee number")
        if held is not None and gid and gid not in held:
            bad.append(f"{who}: {gid} is not in the register")
        for a in r.get("granite_id_aliases") or ():
            if not is_gr(a) or (held is not None and a not in held):
                bad.append(f"{who}: alias {a!r} is not an id in the register")
    return bad
