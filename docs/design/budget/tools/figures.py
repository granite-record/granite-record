"""Scratch: the budget mock's figures from estimates.json, each fund's lines
checked against its printed total. Prints a report; writes figures.json."""
import json, sys
from pathlib import Path

est = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
NAMES = {"GENERAL FUND": "General Fund", "EDUCATION FUND": "Education Fund",
         "HIGHWAY FUND": "Highway Fund", "FISH AND GAME FUND": "Fish and Game Fund"}
# 2025's highway line is printed "$127,7000,000"; num() reads 1277000000.
# The fund's own printed total (259,600,000) is 127.7 + 131.7 + 0.2 million,
# so the figure used is 127,700,000 and the page says the print reads otherwise.
FIX = {("2025", "HIGHWAY FUND", "GASOLINE ROAD TOLL", 0): 127_700_000}

res, problems = {}, []
for term in ("2023", "2025"):
    funds = {}
    for fk, f in est[term]["funds"].items():
        lines, total = [], None
        for name, a, b, raw in f["lines"]:
            if (term, fk, name, 0) in FIX:
                a = FIX[(term, fk, name, 0)]
            if name.startswith("TOTAL"):
                total = (a, b)
            elif name.startswith("SUBTOTAL"):
                continue
            else:
                lines.append({"name": name, "y1": a, "y2": b, "printed": raw})
        # 2023 prints BPT and BET separately with a subtotal; 2025 prints one line.
        s1, s2 = sum(l["y1"] for l in lines), sum(l["y2"] for l in lines)
        ok = total == (s1, s2)
        if not ok:
            problems.append((term, fk, total, (s1, s2)))
        funds[NAMES[fk]] = {"years": f["years"], "lines": lines, "total": total, "sums_match": ok}
    res[term] = funds

for p in problems:
    print("MISMATCH", p)


def by_source(term):
    """Biennium total by source across all four funds, business taxes merged."""
    agg = {}
    for fund, f in res[term].items():
        for l in f["lines"]:
            n = l["name"]
            if n in ("BUSINESS PROFITS TAX", "BUSINESS ENTERPRISE TAX"):
                n = "BUSINESS TAXES"
            agg.setdefault(n, {"total": 0, "by_fund": {}})
            v = l["y1"] + l["y2"]
            agg[n]["total"] += v
            agg[n]["by_fund"][fund] = agg[n]["by_fund"].get(fund, 0) + v
    return agg


summary = {}
for term in ("2023", "2025"):
    ft = {k: v["total"] for k, v in res[term].items()}
    summary[term] = {"fund_totals": ft,
                     "biennium_by_fund": {k: a + b for k, (a, b) in ft.items()},
                     "biennium_all": sum(a + b for a, b in ft.values()),
                     "by_source": by_source(term)}
    print(term, "biennium all four funds", f"{summary[term]['biennium_all']:,}")
    for k, v in summary[term]["biennium_by_fund"].items():
        print("   ", k, f"{v:,}")

print("\nBY SOURCE, biennium, 2024-25 estimate -> 2026-27 estimate")
a, b = summary["2023"]["by_source"], summary["2025"]["by_source"]
for n in sorted(set(a) | set(b), key=lambda n: -b.get(n, {"total": 0})["total"]):
    x, y = a.get(n, {"total": 0})["total"], b.get(n, {"total": 0})["total"]
    print(f"  {n:28s} {x/1e6:9.1f} -> {y/1e6:9.1f}  ({(y-x)/1e6:+8.1f})")
out.write_text(json.dumps({"funds": res, "summary": summary}, indent=1))
