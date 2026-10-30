"""Scratch: the LBA's FY20-26 General and Education Trust Fund collections
(cash basis, as of 6/30/26). Reads the June Y.T.D. row of each table, sums
the sources and checks the sum against the printed Grand Total.
Args: pdftotext -layout output, out json."""
import json, re, sys

YEARS = ["FY 2026", "FY 2025", "FY 2024", "FY 2023", "FY 2022", "FY 2021", "FY 2020"]
# Each page's tables, left then right, as their headings print them.
PAGES = [["Business Profits Tax", "Business Enterprise Tax"],
         ["Combined Business Taxes (BPT and BET)"],
         ["Meals & Rooms", "Tobacco Tax"],
         ["Liquor Sales and Distribution", "Interest & Dividends"],
         ["Insurance Premium Tax", "Communications Services Tax"],
         ["Real Estate Transfer Tax", "Court Fines & Fees"],
         ["Securities Revenue", "Beer Tax"],
         ["Other", "Lottery"],
         ["Video Lottery Terminal Revenue", "Tobacco Settlement"],
         ["Utility Property Tax", "State Property Tax"],
         ["Medicaid Recoveries", "Grand Total"]]
NUM = re.compile(r"-?\$-?[\d,]+\.\d")


def val(s):
    return float(s.replace("$", "").replace(",", ""))


def months(page):
    """{table: {month: {"monthly": [7], "ytd": [7]}}} from one page."""
    lines = page.splitlines()
    out = {name: {} for name in PAGES_NOW}
    month = None
    for ln in lines:
        m = re.match(r"\s*(July|August|September|October|November|December|January|February|March|April|May|June)\b", ln)
        if m:
            month = m.group(1)
            continue
        kind = "monthly" if "Monthly" in ln else "ytd" if "Y.T.D." in ln else None
        if not (kind and month):
            continue
        nums = [val(x) for x in NUM.findall(ln)]
        for k, name in enumerate(PAGES_NOW):
            chunk = nums[k * 7:(k + 1) * 7]
            if len(chunk) == 7:
                out[name].setdefault(month, {})[kind] = chunk
    return out


text = open(sys.argv[1]).read().split("\f")
tables = {}
for i, names in enumerate(PAGES):
    PAGES_NOW = names
    tables.update(months(text[i]))

problems = []
# 1. each table's twelve monthly figures sum to its June Y.T.D. (to rounding)
for name, t in tables.items():
    for y in range(7):
        ms = sum(t[m]["monthly"][y] for m in t if "monthly" in t[m])
        ytd = t["June"]["ytd"][y]
        if abs(ms - ytd) > 0.35:
            problems.append(f"{name} {YEARS[y]}: months sum {ms:.1f}, June YTD {ytd:.1f}")
# 2. the sources sum to the Grand Total (BPT+BET counted once, via the combined table)
parts = [n for n in tables if n not in ("Business Profits Tax", "Business Enterprise Tax", "Grand Total")]
for y in range(7):
    s = sum(tables[n]["June"]["ytd"][y] for n in parts)
    g = tables["Grand Total"]["June"]["ytd"][y]
    print(f"{YEARS[y]}: sources sum {s:,.1f}; Grand Total printed {g:,.1f}; difference {g - s:+.1f}")
    bb = tables["Business Profits Tax"]["June"]["ytd"][y] + tables["Business Enterprise Tax"]["June"]["ytd"][y]
    cb = tables["Combined Business Taxes (BPT and BET)"]["June"]["ytd"][y]
    if abs(bb - cb) > 0.15:
        problems.append(f"BPT+BET {YEARS[y]} {bb:.1f} vs combined {cb:.1f}")
print({n: sum(1 for m in t if "monthly" in t[m] and "ytd" in t[m]) for n, t in tables.items()})
print("\n".join(problems) or "no problems")
json.dump({n: {YEARS[y]: t["June"]["ytd"][y] for y in range(7)} for n, t in tables.items()},
          open(sys.argv[2], "w"), indent=1)
