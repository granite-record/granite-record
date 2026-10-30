"""Scratch: General Fund and Education Fund estimates, six budgets (2015-2025),
each fund's lines summed against its printed total. Reads estimates.json."""
import json, re, sys
from pathlib import Path

est = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
# Printed totals the line regex cannot read, as printed (checked by eye
# against estimates.json's raw text): 2017's General Fund total is printed
# "1,538,700,000 , 1,572,700,000".
TOTALS = {("2017", "GENERAL FUND"): (1_538_700_000, 1_572_700_000)}
FIX = {("2025", "HIGHWAY FUND", "GASOLINE ROAD TOLL"): (127_700_000, 127_900_000)}

rows = []
for term in ("2015", "2017", "2019", "2021", "2023", "2025"):
    row = {"term": term}
    for fk in ("GENERAL FUND", "EDUCATION FUND"):
        f = est[term]["funds"][fk]
        total, s1, s2 = TOTALS.get((term, fk)), 0, 0
        for name, a, b, raw in f["lines"]:
            if name.startswith("TOTAL"):
                total = total or (a, b)
            elif name.startswith("SUBTOTAL") or name == "SUBTOTAL":
                continue
            else:
                s1, s2 = s1 + a, s2 + b
        ok = total == (s1, s2)
        row[fk] = {"years": f["years"], "total": total, "lines_sum": (s1, s2), "ok": ok}
        if not ok:
            print("CHECK", term, fk, total, (s1, s2))
    y = row["GENERAL FUND"]["years"]
    row["label"] = f"{y[0]}–{int(y[0]) + 1}"
    row["gf"] = sum(row["GENERAL FUND"]["total"])
    row["ef"] = sum(row["EDUCATION FUND"]["total"])
    rows.append(row)
    print(term, row["label"], f"GF {row['gf']/1e6:,.1f}  EF {row['ef']/1e6:,.1f}  both {(row['gf']+row['ef'])/1e6:,.1f}")
out.write_text(json.dumps(rows, indent=1))
