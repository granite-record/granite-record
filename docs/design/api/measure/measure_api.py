#!/usr/bin/env python3
# Unstamped on purpose: a design aid under docs/, which versions.json (bare names in the code folders) cannot list.
"""Prototype the API's new files from a built site and measure them.

    python3 measure_api.py SITE_DIR OUT_DIR

Reads only the built site (and generated/careers.json beside it). Writes
prototypes into OUT_DIR, never into the site. Prints JSON of the measurements.
"""
import csv, gzip, json, re, sqlite3, sys, time, zlib
from pathlib import Path

site, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
EMB = re.compile(r'<script type="application/json" id="gr-data">(.*?)</script>', re.S)
R = {}


def gz(path, data):
    with gzip.open(path, "wb", compresslevel=9) as fh:
        fh.write(data)
    return path.stat().st_size


# ---- 1. per-term bill bundles, JSON Lines, gzip -9 ----
t0 = time.time()
terms = {}
for f in sorted((site / "idx").glob("*-*.json")):
    term = f.stem
    rows = json.loads(f.read_text(encoding="utf-8"))
    lines, nb, ntext, missing = [], 0, 0, 0
    for b in rows:
        yr, bid = str(b.get("year") or ""), b["id"]
        p = site / "bills" / yr / f"{bid}.json"
        if p.exists():
            raw = p.read_text(encoding="utf-8")
        else:
            pg = site / "bill" / yr / f"{bid.lower()}.html"
            m = EMB.search(pg.read_text(encoding="utf-8")) if pg.exists() else None
            if not m:
                missing += 1
                continue
            raw = m.group(1)
        d = json.loads(raw)
        if (d.get("billtext") or {}).get("body"):
            ntext += 1
        rec = {"key": f"{term}/{bid}", **d}
        lines.append(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
        nb += 1
    data = ("\n".join(lines) + "\n").encode("utf-8")
    size_gz = gz(out / f"bills-{term}.jsonl.gz", data)
    terms[term] = {"bills": nb, "with_text": ntext, "missing": missing,
                   "raw": len(data), "gz": size_gz}
R["bundles"] = terms
R["bundles_seconds"] = round(time.time() - t0, 1)

# ---- 2. one SQLite of the CSV tables ----
t0 = time.time()
db = out / "granite-record.sqlite"
db.unlink(missing_ok=True)
con = sqlite3.connect(db)
for c in sorted((site / "data").glob("*.csv")):
    name = c.stem
    table = "votes" if name.startswith("votes-") else name
    with c.open(encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        cols = next(rd)
        con.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(chr(34)+x+chr(34) for x in cols)})')
        con.executemany(f'INSERT INTO "{table}" VALUES ({",".join("?" * len(cols))})', rd)
con.commit()
con.execute("VACUUM")
con.close()
raw = db.read_bytes()
R["sqlite"] = {"raw": len(raw), "gz": gz(out / "granite-record.sqlite.gz", raw),
               "seconds": round(time.time() - t0, 1)}
db.unlink()

# ---- 3. the CSVs as they stand, gzipped, for comparison ----
R["csv"] = {c.name: {"raw": c.stat().st_size, "gz": len(zlib.compress(c.read_bytes(), 9))}
            for c in sorted((site / "data").glob("*.csv"))}

# ---- 4. people ----
careers = json.loads((site.parent / "generated" / "careers.json").read_text(encoding="utf-8"))
legs = json.loads((site / "legislators.json").read_text(encoding="utf-8"))
former = json.loads((site / "former.json").read_text(encoding="utf-8"))
multi = sum(1 for p in careers.values() if len(p.get("employee_nos") or []) > 1)
named = sum(1 for p in careers.values() if p.get("named"))
with_pid = sum(1 for p in careers.values() if p.get("person_id"))
R["people"] = {"careers": len(careers), "with_two_or_more_numbers": multi,
               "named": named, "with_person_id": with_pid,
               "sitting": len(legs), "former": len(former)}
mids = {str(m.get("id")) for m in legs + former}
R["people"]["site_ids"] = len(mids)

# ---- 5. date formats in the CSVs ----
fmt = {}
DATEISH = re.compile(r"date|day", re.I)
for c in sorted((site / "data").glob("*.csv")):
    with c.open(encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        for i, r in enumerate(rd):
            for k, v in r.items():
                if DATEISH.search(k) and v:
                    shape = re.sub(r"\d", "9", v)
                    fmt.setdefault(f"{c.name if not c.name.startswith('votes-') else 'votes-*'}:{k}", {}).setdefault(shape, 0)
                    fmt[f"{c.name if not c.name.startswith('votes-') else 'votes-*'}:{k}"][shape] += 1
            if i > 200000:
                break
R["date_shapes"] = fmt
print(json.dumps(R, indent=1))
