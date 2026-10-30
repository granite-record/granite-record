#!/usr/bin/env python3
# Unstamped on purpose: a design aid under docs/, which versions.json (bare names in the code folders) cannot list.
"""A prototype people file: one row per person, every number they carry.

    python3 measure_people.py BUILD_DIR OUT_DIR       (BUILD_DIR holds site/, db/, generated/)
"""
import csv, gzip, io, json, sys
from pathlib import Path

root, out = Path(sys.argv[1]), Path(sys.argv[2])
careers = json.loads((root / "generated/careers.json").read_text(encoding="utf-8"))
cols = json.loads((root / "db/_columns.json").read_text(encoding="utf-8"))
lc = cols.get("Legislators") or cols.get("legislators")
lc = lc if isinstance(lc, list) else lc.get("columns")
iE, iP = lc.index("Employeeno"), lc.index("PersonID")
emp2pid = {}
with (root / "db/Legislators.psv").open(encoding="utf-8") as fh:
    for line in fh:
        f = line.rstrip("\n").split("|")
        if len(f) > max(iE, iP) and f[iE].strip():
            emp2pid[f[iE].strip()] = f[iP].strip()
site = root / "site"
rows = {str(m["id"]): m for m in json.loads((site / "legislators.json").read_text())}
rows.update({str(m["id"]): m for m in json.loads((site / "former.json").read_text())
             if str(m["id"]) not in rows})
people, unmatched_site = [], set(rows)
for key, c in careers.items():
    emps = sorted(c.get("employee_nos") or [key], key=lambda e: min(
        [t for t, v in c["by_term"].items() if e in v.get("employee_nos", [])] or ["9999"]))
    pids = [emp2pid[e] for e in emps if emp2pid.get(e)]
    site_ids = [i for i in dict.fromkeys(pids + emps) if i in rows]
    unmatched_site -= set(site_ids)
    page = next((rows[i].get("slug") for i in site_ids if rows[i].get("slug")), None)
    people.append({
        "person": f"p{emps[0]}",
        "name": next((rows[i].get("display_plain") or rows[i].get("name") for i in site_ids), None),
        "employee_numbers": emps, "person_ids": list(dict.fromkeys(pids)),
        "member_ids": site_ids,
        "page": f"/legislator/{page}" if page else None,
        "sitting": any(not rows[i].get("former") for i in site_ids),
        "first_term": c.get("first_term"), "last_term": c.get("last_term"),
        "chambers": sorted({ch for v in c["by_term"].values() for ch in v.get("chambers", [])}),
    })
data = json.dumps({"format": 1, "people": people}, ensure_ascii=False, separators=(",", ":")).encode()
(out / "people.json").write_bytes(data)
s = io.StringIO(); w = csv.writer(s)
w.writerow(["person", "number_kind", "number", "name", "page"])
for p in people:
    for k, field in (("employee_number", "employee_numbers"), ("person_id", "person_ids"), ("member_id", "member_ids")):
        for n in p[field]:
            w.writerow([p["person"], k, n, p["name"] or "", p["page"] or ""])
(out / "people.csv").write_text(s.getvalue(), encoding="utf-8")
print(json.dumps({
    "people": len(people), "json_bytes": len(data), "json_gz": len(gzip.compress(data, 9)),
    "csv_bytes": len(s.getvalue().encode()),
    "with_page": sum(1 for p in people if p["page"]),
    "with_name": sum(1 for p in people if p["name"]),
    "two_plus_employee_numbers": sum(1 for p in people if len(p["employee_numbers"]) > 1),
    "two_plus_member_ids": sum(1 for p in people if len(p["member_ids"]) > 1),
    "no_member_id": sum(1 for p in people if not p["member_ids"]),
    "site_ids_in_no_person": len(unmatched_site),
    "site_ids_in_no_person_sample": sorted(unmatched_site)[:10],
    "sample": [p for p in people if len(p["employee_numbers"]) > 1][:2],
}, indent=1))
