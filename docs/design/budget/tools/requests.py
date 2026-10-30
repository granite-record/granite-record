"""Scratch: DAS 'Summary of Budget Submissions by Agency' (9/28/2026, version
2028B01), total funds. Checks every row (efficiency + needs = request), every
column's agencies against the printed subtotals, and the subtotals against
the grand total. Args: pdftotext -layout output, crosswalk text, out json."""
import json, re, sys

COLS = ["FY26 Actuals", "FY27 Adj Auth", "FY28 Efficiency", "FY28 Prioritized Needs",
        "FY28 Request", "FY29 Efficiency", "FY29 Prioritized Needs", "FY29 Request"]
ROW = re.compile(r"^\s*(\d{3})-(.+?)\s{2,}((?:[\d,]+|-)(?:\s+(?:[\d,]+|-)){7})\s*$")
TOT = re.compile(r"^\s*(SUBTOTAL EXCLUDING DHHS|SUBTOTAL DHHS|GRAND TOTAL APPROPRIATIONS)\s+((?:[\d,]+)(?:\s+[\d,]+){7})\s*$")


def n(s):
    return 0 if s == "-" else int(s.replace(",", ""))


rows, tots, group = [], {}, "non-DHHS"
for ln in open(sys.argv[1]).read().splitlines():
    if ln.strip() == "DHHS":
        group = "DHHS"
    m = ROW.match(ln)
    if m:
        v = [n(x) for x in m.group(3).split()]
        name = m.group(2).replace("**", "").strip()
        rows.append({"num": m.group(1), "name": name, "group": group, **dict(zip(COLS, v))})
        continue
    m = TOT.match(ln)
    if m:
        tots[m.group(1)] = dict(zip(COLS, [n(x) for x in m.group(2).split()]))

problems = []
for r in rows:
    for y in ("FY28", "FY29"):
        if r[f"{y} Efficiency"] + r[f"{y} Prioritized Needs"] != r[f"{y} Request"]:
            problems.append(f"{r['num']} {r['name']} {y}: {r[f'{y} Efficiency']} + {r[f'{y} Prioritized Needs']} != {r[f'{y} Request']}")
for g, key in (("non-DHHS", "SUBTOTAL EXCLUDING DHHS"), ("DHHS", "SUBTOTAL DHHS")):
    for c in COLS:
        s = sum(r[c] for r in rows if r["group"] == g)
        if s != tots[key][c]:
            problems.append(f"{key} {c}: rows sum {s:,} printed {tots[key][c]:,} ({tots[key][c] - s:+,})")
for c in COLS:
    if tots["SUBTOTAL EXCLUDING DHHS"][c] + tots["SUBTOTAL DHHS"][c] != tots["GRAND TOTAL APPROPRIATIONS"][c]:
        problems.append(f"GRAND {c}")
print(len(rows), "agency rows;", sum(r["group"] == "DHHS" for r in rows), "of them DHHS")
print("\n".join(problems) or "every row, subtotal and the grand total add up")

# the crosswalk: every agency number in the summary named there?
cw = open(sys.argv[2]).read()
nums = set(re.findall(r"\b000(\d{2})\b", cw)) | {x[1:] for x in re.findall(r"\b(\d{3})-HHS", cw)}
missing = [r["num"] for r in rows if r["num"][1:] not in nums and r["num"] not in re.findall(r"(\d{3})-HHS", cw)]
print("summary agencies not in the crosswalk:", missing)
json.dump({"rows": rows, "totals": tots}, open(sys.argv[3], "w"), indent=1)

g = tots["GRAND TOTAL APPROPRIATIONS"]
print({c: f"{g[c] / 1e6:,.1f}" for c in COLS})
top = sorted(rows, key=lambda r: -r["FY26 Actuals"])[:12]
for r in top:
    print(f"  {r['num']} {r['name']:36s} FY26 {r['FY26 Actuals'] / 1e6:9.1f}  FY27 {r['FY27 Adj Auth'] / 1e6:9.1f}  FY28 req {r['FY28 Request'] / 1e6:9.1f}  FY29 req {r['FY29 Request'] / 1e6:9.1f}")
