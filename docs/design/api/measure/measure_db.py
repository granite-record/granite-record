#!/usr/bin/env python3
# Unstamped on purpose: a design aid under docs/, which versions.json (bare names in the code folders) cannot list.
"""A normalised SQLite of the CSV tables: each fact once, votes as integers.

    python3 measure_db.py SITE_DIR OUT_DIR
"""
import csv, gzip, json, re, sqlite3, sys, time
from pathlib import Path

site, out = Path(sys.argv[1]), Path(sys.argv[2])
D = site / "data"
t0 = time.time()
db = out / "norm.sqlite"
db.unlink(missing_ok=True)
con = sqlite3.connect(db)
con.executescript("""
PRAGMA page_size=4096;
CREATE TABLE bills(term TEXT, bill TEXT, year INT, title TEXT, sponsor TEXT,
  committee TEXT, topic TEXT, status TEXT, outcome TEXT, passage TEXT,
  roll_calls INT, chapter TEXT, chip TEXT, PRIMARY KEY(term,bill)) WITHOUT ROWID;
CREATE TABLE rollcalls(id INTEGER PRIMARY KEY, roll_call TEXT UNIQUE, term TEXT,
  year INT, body TEXT, number INT, date TEXT, bill TEXT, question TEXT,
  question_plain TEXT, yeas INT, nays INT, not_voting INT, passed INT,
  procedural INT, threshold_needed TEXT, threshold_rule TEXT, outcome_source TEXT);
CREATE TABLE members(member_id TEXT PRIMARY KEY, name TEXT) WITHOUT ROWID;
CREATE TABLE vote_values(code INTEGER PRIMARY KEY, vote TEXT);
CREATE TABLE votes(rollcall INT, member_id TEXT, party TEXT, vote INT,
  PRIMARY KEY(rollcall, member_id)) WITHOUT ROWID;
""")
ins = lambda t, n, rows: con.executemany(f"INSERT OR IGNORE INTO {t} VALUES ({','.join('?'*n)})", rows)
with (D / "bills.csv").open(encoding="utf-8", newline="") as fh:
    rd = csv.reader(fh); next(rd)
    ins("bills", 13, ([r[0], r[2], r[1], *r[3:]] for r in rd))
rcid = {}
with (D / "rollcalls.csv").open(encoding="utf-8", newline="") as fh:
    rd = csv.reader(fh); next(rd)
    rows = []
    for i, r in enumerate(rd, 1):
        rcid[r[0]] = i
        rows.append([i, *r])
    ins("rollcalls", 18, rows)
codes, members = {}, {}
for f in sorted(D.glob("votes-*.csv")):
    with f.open(encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh); next(rd)
        rows = []
        for r in rd:
            rc = rcid.get(r[0])
            if rc is None:
                continue
            c = codes.setdefault(r[9], len(codes))
            members.setdefault(r[5], r[6])
            rows.append([rc, r[5], r[7], c])
        ins("votes", 4, rows)
ins("vote_values", 2, ((c, v) for v, c in codes.items()))
ins("members", 2, members.items())
for name, n in (("sponsors", 9), ("proceedings", None), ("legislators", 10)):
    with (D / f"{name}.csv").open(encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh); cols = next(rd)
        con.execute(f'CREATE TABLE {name} ({", ".join(chr(34)+c+chr(34) for c in cols)})')
        ins(name, len(cols), rd)
con.commit(); con.execute("VACUUM"); con.close()
raw = db.read_bytes()
with gzip.open(out / "norm.sqlite.gz", "wb", 9) as fh:
    fh.write(raw)
con = sqlite3.connect(db)
sizes = dict(con.execute("SELECT name, SUM(pgsize) FROM dbstat GROUP BY name").fetchall()) \
    if con.execute("SELECT 1 FROM pragma_compile_options WHERE compile_options='ENABLE_DBSTAT_VTAB'").fetchone() else {}
nv = con.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
print(json.dumps({"raw": len(raw), "gz": (out / "norm.sqlite.gz").stat().st_size,
                  "votes": nv, "codes": codes, "seconds": round(time.time() - t0, 1),
                  "by_table": sizes}, indent=1))
