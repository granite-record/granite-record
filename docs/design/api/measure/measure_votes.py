#!/usr/bin/env python3
# Unstamped on purpose: a design aid under docs/, which versions.json (bare names in the code folders) cannot list.
"""The vote spreadsheets with the proposed changes, measured against the cap,
and every ballot's member id joined to a person.

    python3 measure_votes.py BUILD_DIR > results/measure_votes.json

BUILD_DIR holds site/, db/ and generated/. Reads only; writes nothing but its
output. Person here is the prototype's rule (p and the person's first
Employeeno); the design issues numbers from a register instead, which does not
change any size measured here (a person number is the same width).
"""
import csv, glob, io, json, re, sys, collections
from pathlib import Path

root = Path(sys.argv[1])
careers = json.loads((root / "generated/careers.json").read_text(encoding="utf-8"))
cols = json.loads((root / "db/_columns.json").read_text(encoding="utf-8"))
lc = cols["Legislators"]
lc = lc if isinstance(lc, list) else lc["columns"]
iE, iP = lc.index("Employeeno"), lc.index("PersonID")
e2p = {}
for line in (root / "db/Legislators.psv").open(encoding="utf-8"):
    f = line.rstrip("\n").split("|")
    if len(f) > max(iE, iP) and f[iE].strip():
        e2p[f[iE].strip()] = f[iP].strip()
num2person = {}
for key, c in careers.items():
    emps = c.get("employee_nos") or [key]
    first = min(emps, key=lambda e: min(
        [t for t, v in c["by_term"].items() if e in v.get("employee_nos", [])] or ["9999"]))
    for e in emps:
        num2person.setdefault(e, set()).add("p" + first)
        if e2p.get(e):
            num2person.setdefault(e2p[e], set()).add("p" + first)
SAFE = int(25 * 1024 * 1024 * 0.9)


def iso(d):
    m = re.match(r"(\d+)/(\d+)/(\d{4})$", d)
    return f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}" if m else d


def size(rows):
    s = io.StringIO()
    csv.writer(s).writerows(rows)
    return len(s.getvalue().encode())


out, unmatched, ambiguous, short = {}, collections.Counter(), collections.Counter(), set()
for f in sorted(glob.glob(str(root / "site/data/votes-*.csv"))):
    rows = list(csv.reader(open(f, encoding="utf-8", newline="")))
    iso_only = [rows[0]]
    a = [rows[0] + ["person"]]
    b = [rows[0] + ["date_iso", "person"]]
    for r in rows[1:]:
        mid = r[5]
        if mid.isdigit() and len(mid) < 6:
            short.add(int(mid))
        ps = num2person.get(mid, set())
        if not ps:
            unmatched[mid] += 1
        if len(ps) > 1:
            ambiguous[mid] += 1
        p = next(iter(ps)) if len(ps) == 1 else ""
        iso_only.append([r[0], r[1], iso(r[2]), *r[3:]])
        a.append([r[0], r[1], iso(r[2]), *r[3:], p])
        b.append([*r, iso(r[2]), p])
    out[Path(f).name] = {"now": Path(f).stat().st_size, "iso_in_place": size(iso_only),
                         "iso_in_place_plus_person": size(a),
                         "date_iso_plus_person": size(b), "safe": SAFE}
print(json.dumps({"files": out, "member_ids_with_no_person": len(unmatched),
                  "ballots_with_no_person": sum(unmatched.values()),
                  "member_ids_in_two_people": len(ambiguous),
                  "short_id_range": [min(short), max(short)]}, indent=1))
