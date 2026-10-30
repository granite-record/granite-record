#!/usr/bin/env python3
# Unstamped on purpose: a design aid under docs/, which versions.json (bare names in the code folders) cannot list.
"""Committee reports, docket reports, interim study, testimony counts and
non-bill meetings as database tables, measured.

    python3 measure_reports.py PROTO_DIR BUILD_DIR > results/measure_reports.json

PROTO_DIR holds the bills-<term>.jsonl.gz prototypes (measure_api.py) and
norm.sqlite (measure_db.py); BUILD_DIR holds meetings.json. The tables are
read from the bill records, the same records the pages draw, so a table and a
page cannot disagree. Writes only norm_plus.sqlite(.gz) into PROTO_DIR.
"""
import gzip, json, shutil, sqlite3, sys, time
from pathlib import Path

proto, build = Path(sys.argv[1]), Path(sys.argv[2])
t0 = time.time()
db = proto / "norm_plus.sqlite"
shutil.copy(proto / "norm.sqlite", db)
con = sqlite3.connect(db)
con.executescript("""
CREATE TABLE committee_reports(term TEXT, bill TEXT, source TEXT, chamber TEXT,
  report_date TEXT, majority_recommendation TEXT, minority_recommendation TEXT,
  side TEXT, committee TEXT, author TEXT, vote_yeas INT, vote_nays INT,
  amendment TEXT, text TEXT);
CREATE TABLE docket_reports(term TEXT, bill TEXT, date TEXT, dated TEXT, chamber TEXT,
  committee TEXT, side TEXT, recommendation TEXT, vote_yeas INT, vote_nays INT,
  amendment TEXT);
CREATE TABLE interim_study(term TEXT, bill TEXT, date TEXT, chamber TEXT, rec TEXT,
  recommended INT, vote TEXT);
CREATE TABLE testimony(term TEXT, bill TEXT, date TEXT, committee TEXT, total INT,
  support INT, oppose INT, neutral INT);
CREATE TABLE meetings(date TEXT, time TEXT, chamber TEXT, committee TEXT, kind TEXT,
  venue TEXT, bill TEXT, noticed TEXT, calendar TEXT);
""")
n = {"committee_reports": 0, "docket_reports": 0, "interim_study": 0, "testimony": 0}
for f in sorted(proto.glob("bills-*.jsonl.gz")):
    for line in gzip.open(f):
        if not line.strip():
            continue
        b = json.loads(line)
        term, bill = b["term"], b["id"]
        for r in b.get("reports") or []:
            for s in r.get("reports") or []:
                con.execute("INSERT INTO committee_reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (term, bill, r.get("source"), r.get("body") or ("S" if "Senate" in (r.get("source") or "") else "H"),
                             r.get("date"), r.get("majority_recommendation"), r.get("minority_recommendation"),
                             s.get("side"), s.get("committee"), s.get("author"), s.get("vote_yeas"),
                             s.get("vote_nays"), s.get("amendment"), s.get("text")))
                n["committee_reports"] += 1
        for r in b.get("docket_reports") or []:
            con.execute("INSERT INTO docket_reports VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (term, bill, r.get("date"), r.get("dated"), r.get("body"), r.get("committee"),
                         r.get("side"), r.get("recommendation"), r.get("vote_yeas"), r.get("vote_nays"),
                         r.get("amendment")))
            n["docket_reports"] += 1
        s = b.get("study_report")
        if s:
            con.execute("INSERT INTO interim_study VALUES (?,?,?,?,?,?,?)",
                        (term, bill, s.get("date"), s.get("body"), s.get("rec"),
                         1 if s.get("recommended") else 0, s.get("vote")))
            n["interim_study"] += 1
        for st in b.get("stations") or []:
            t = st.get("testimony")
            if t:
                con.execute("INSERT INTO testimony VALUES (?,?,?,?,?,?,?,?)",
                            (term, bill, t.get("date") or st.get("when"), st.get("committee"),
                             t.get("total"), t.get("support"), t.get("oppose"), t.get("neutral")))
                n["testimony"] += 1
meet = json.loads((build / "meetings.json").read_text(encoding="utf-8"))
con.executemany("INSERT INTO meetings VALUES (?,?,?,?,?,?,?,?,?)",
                [(m.get("date"), m.get("time"), m.get("body"), m.get("committee"), m.get("kind"),
                  m.get("venue") or m.get("room"), m.get("bill"), m.get("noticed"), m.get("calendar"))
                 for m in meet])
n["meetings"] = len(meet)
con.commit()
con.execute("VACUUM")
sizes = dict(con.execute("SELECT name, SUM(pgsize) FROM dbstat GROUP BY name").fetchall())
con.close()
raw = db.read_bytes()
with gzip.open(proto / "norm_plus.sqlite.gz", "wb", 9) as fh:
    fh.write(raw)
print(json.dumps({"rows": n, "raw": len(raw), "gz": (proto / "norm_plus.sqlite.gz").stat().st_size,
                  "seconds": round(time.time() - t0, 1),
                  "new_tables_bytes": {k: sizes.get(k) for k in list(n)}}, indent=1))
