"""Scratch: list and save every printing of HB1/HB2 for 2025 from the kit's dump.
Reads only; writes into the scratch out folder given."""
import json, sys, re, html
from pathlib import Path

kit, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
cols = json.loads((kit / "db/_columns.json").read_text())


def rows(path, names):
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        for ln in fh:
            f = ln.rstrip("\r\n").split("|")
            if len(f) == len(names):
                yield dict(zip(names, f))


want = {}
for r in rows(kit / "db/Legislation.psv", cols["Legislation"]):
    b = r["CondensedBillNo"].replace(" ", "").upper()
    if b in ("HB1", "HB2") and r["sessionyear"].strip() in ("2025", "2026"):
        want[r["legislationID"].strip()] = (b, r["sessionyear"].strip())
        print("LEG", b, r["sessionyear"], r["LSRTitle"][:120], "| approp", r["AppropriationCode"],
              "| fiscal", r["FiscalImpactCode"], "| chapter", r["ChapterNo"], "| eff", r["EffectiveDate"])

for r in rows(kit / "db/LegislationText.psv", cols["LegislationText"]):
    k = r["LegislationID"].strip()
    if k in want:
        b, y = want[k]
        h = r["HTMLText"]
        name = f"{b}_{y}_{r['LegislationTextID'].strip()}_{re.sub(r'[^A-Za-z0-9]+', '_', r['DocumentVersion'])[:40]}"
        (out / f"{name}.html").write_text(h, encoding="utf-8")
        t = re.sub(r"<[^>]+>", " ", h)
        t = html.unescape(re.sub(r"[ \t]+", " ", t))
        (out / f"{name}.txt").write_text(t, encoding="utf-8")
        print("TXT", b, y, r["DocumentVersion"], "|", r["TextDescription"][:60], "|", r["DateTimeStamp"],
              "| html", len(h), "| text", len(r["Text"]))
