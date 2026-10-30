"""Scratch: pull 'Estimates of Unrestricted Revenue' out of each HB 1 final page.
Args: kit folder, 2025 chaptered text file, output json. Reads only."""
import html, json, re, sys
from pathlib import Path

kit, t2025, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])


def text_of(raw):
    raw = re.sub(r"<style.*?</style>", "", raw, flags=re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", t)


FUND = re.compile(r"(GENERAL FUND|EDUCATION (?:TRUST )?FUND|HIGHWAY FUND|FISH AND GAME FUND)\s+FY ?(\d{2,4}) ?(?:-\s*)?FY ?(\d ?\d{1,3})")
LINE = re.compile(r"([A-Z][A-Z&,.'()/ \-]+?)\s+\$?\s*([\d][\d, ]*\d|0)\s+\$?\s*([\d][\d, ]*\d|0)(?=\s|$)")


def num(s):
    return int(re.sub(r"[^\d]", "", s))


def parse(t):
    i = t.upper().find("ESTIMATES OF UNRESTRICTED REVENUE")
    if i < 0:
        return None, ""
    seg = t[i:]
    end = re.search(r"\d+:\d+ Effective Date|Effective Date\.", seg)
    seg = seg[: end.start()] if end else seg[:6000]
    funds = {}
    parts = list(FUND.finditer(seg))
    for k, m in enumerate(parts):
        body = seg[m.end(): parts[k + 1].start() if k + 1 < len(parts) else len(seg)]
        lines = []
        for lm in LINE.finditer(body):
            lines.append([lm.group(1).strip(), num(lm.group(2)), num(lm.group(3)), lm.group(0).strip()])
        funds[m.group(1)] = {"years": [m.group(2), m.group(3).replace(" ", "")], "lines": lines}
    return funds, seg


res = {}
for y in range(1993, 2025, 2):
    p = kit / "legislation" / str(y) / "HB0001.html"
    if p.exists():
        f, seg = parse(text_of(p.read_text(encoding="utf-8", errors="replace")))
        res[str(y)] = {"source": str(p.relative_to(kit)), "funds": f, "raw": seg[:5000]}
f, seg = parse(re.sub(r"\s+", " ", t2025.read_text(encoding="utf-8")))
res["2025"] = {"source": "db/LegislationText.psv CHAPTERED FINAL VERSION", "funds": f, "raw": seg[:5000]}
out.write_text(json.dumps(res, indent=1))
for y, r in res.items():
    fs = r["funds"] or {}
    tot = {k: [l for l in v["lines"] if l[0].startswith("TOTAL")] for k, v in fs.items()}
    print(y, {k: (v["years"], [(l[1], l[2]) for l in tot[k]]) for k, v in fs.items()})
