#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.2
"""
The data API's database: every table on the data page, and the record's
committee reports, in one SQLite file, compressed with xz.

    import api_db
    c = api_db.Collector()                 # handed every bill record, by
    build_exports.bill_files(..., collect=c.add)
    api_db.write(out, c, people)               -> the manifest's row

docs/design/api/DESIGN.md, 2.3 and 2.9; the owner's OK of 30 October 2026.
Nothing here asks the network.

WHAT IT HOLDS

  bills, rollcalls, sponsors, legislators   the CSVs beside it, as written
  votes, vote_values      the vote CSVs, each ballot as its roll call's id,
                          its member, their person and a value code: each
                          roll call and each member is stored once, which is
                          what keeps 2.3 million ballots under the host's
                          limit
  proceedings             proceedings.csv without video_title and
                          scheduled_seconds, the two columns that are
                          YouTube's own metadata (Q18)
  people, person_numbers  people.json, as one row a person and one a number
  committee_reports       each side of each printed committee report, with
                          its reasoning: House calendar reports, Senate
                          committee reports, interim study statements
  docket_reports          reports the docket records and no print carries
  interim_study           the docket's line on each interim study
  testimony               sign-in counts at each public hearing; never a name
  meetings                every meeting the calendars noticed
  meta                    what this file is and whose. Not when: the
                          manifest says that, and a time inside the file
                          would change its bytes every night

The tables read from the bill records read the records the pages draw, in
the same pass that writes the bill files, so a table and a page cannot
disagree. The CSVs are read back as written, so the database and the
spreadsheets cannot either.

WHY XZ. With the report tables the file is about 109 MB opened: 26.9 MB in
gzip, past the 25 MiB a file may be on the host, and 13.2 MB in xz
(measured 30 October 2026). Python's lzma, R, and xz on Linux and macOS read
it with what they already have.

THE SAME ROWS GIVE THE SAME BYTES. Rows go in in a stated order, the file is
vacuumed, and xz writes no time, so the manifest's sha256 moves only when
the data does -- on one machine's SQLite. Another version of SQLite may lay
out the same rows differently; the build compares nights on one machine.
"""

import csv
import hashlib
import json
import lzma
import sqlite3
from pathlib import Path

FORMAT = 1
NAME = "granite-record.sqlite.xz"
PROCEEDINGS_DROP = ("video_title", "scheduled_seconds")


class Collector:
    """The rows the bill records give, gathered as bill_files reads them."""

    def __init__(self):
        self.reports, self.docket, self.study, self.testimony = [], [], [], []
        self.bills = 0

    def add(self, term, r):
        self.bills += 1
        bill = r.get("id")
        for rep in r.get("reports") or []:
            src = rep.get("source") or ""
            chamber = rep.get("body") or ("S" if src.startswith("Senate") else "H")
            for side in rep.get("reports") or []:
                self.reports.append((
                    term, bill, chamber, src, rep.get("cite") or "", rep.get("date") or "",
                    1 if rep.get("interim") else 0,
                    rep.get("majority_recommendation") or "", rep.get("minority_recommendation") or "",
                    side.get("side") or "", side.get("committee") or "", side.get("author") or "",
                    side.get("vote_yeas"), side.get("vote_nays"), side.get("amendment") or "",
                    side.get("text") or ""))
        for d in r.get("docket_reports") or []:
            self.docket.append((
                term, bill, d.get("date") or "", d.get("dated") or "", d.get("body") or "",
                d.get("committee") or "", d.get("side") or "", d.get("recommendation") or "",
                d.get("vote_yeas"), d.get("vote_nays"), d.get("amendment") or "", d.get("cite") or ""))
        s = r.get("study_report")
        if s:
            self.study.append((term, bill, s.get("date") or "", s.get("body") or "",
                               s.get("rec") or "", 1 if s.get("recommended") else 0, s.get("vote") or ""))
        for st in r.get("stations") or []:
            t = isinstance(st, dict) and st.get("testimony")
            if t:
                self.testimony.append((term, bill, t.get("date") or st.get("when") or "",
                                       1 if t.get("date") else 0, st.get("body") or "",
                                       st.get("committee") or "",
                                       t.get("total"), t.get("support"), t.get("oppose"), t.get("neutral")))


SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID;
CREATE TABLE bills(term TEXT, bill TEXT, year INT, title TEXT, sponsor TEXT,
  committee TEXT, topic TEXT, status TEXT, outcome TEXT, passage TEXT,
  roll_calls INT, chapter TEXT, chip TEXT, PRIMARY KEY(term, bill)) WITHOUT ROWID;
CREATE TABLE rollcalls(id INTEGER PRIMARY KEY, roll_call TEXT UNIQUE, term TEXT,
  year INT, body TEXT, number INT, date TEXT, bill TEXT, question TEXT,
  question_plain TEXT, yeas INT, nays INT, not_voting INT, passed INT,
  procedural INT, threshold_needed TEXT, threshold_rule TEXT, outcome_source TEXT);
CREATE TABLE vote_values(code INTEGER PRIMARY KEY, vote TEXT);
CREATE TABLE votes(rollcall INT, member_id TEXT, person TEXT, party TEXT, vote INT,
  PRIMARY KEY(rollcall, member_id)) WITHOUT ROWID;
CREATE TABLE people(person TEXT PRIMARY KEY, name TEXT, page TEXT, sitting INT,
  chambers TEXT, first_term TEXT, last_term TEXT, provisional INT,
  replaced_by TEXT, split_from TEXT) WITHOUT ROWID;
CREATE TABLE person_numbers(person TEXT, kind TEXT, number TEXT,
  PRIMARY KEY(kind, number, person)) WITHOUT ROWID;
CREATE TABLE committee_reports(term TEXT, bill TEXT, chamber TEXT, source TEXT,
  cite TEXT, date TEXT, interim INT, majority_recommendation TEXT,
  minority_recommendation TEXT, side TEXT, committee TEXT, author TEXT,
  vote_yeas INT, vote_nays INT, amendment TEXT, text TEXT);
CREATE TABLE docket_reports(term TEXT, bill TEXT, date TEXT, dated TEXT, chamber TEXT,
  committee TEXT, side TEXT, recommendation TEXT, vote_yeas INT, vote_nays INT,
  amendment TEXT, cite TEXT);
CREATE TABLE interim_study(term TEXT, bill TEXT, date TEXT, chamber TEXT, rec TEXT,
  recommended INT, vote TEXT);
CREATE TABLE testimony(term TEXT, bill TEXT, date TEXT, date_known INT, chamber TEXT, committee TEXT,
  total INT, support INT, oppose INT, neutral INT);
CREATE TABLE meetings(date TEXT, time TEXT, chamber TEXT, committee TEXT, kind TEXT,
  venue TEXT, room TEXT, bill TEXT, noticed TEXT, calendar TEXT);
"""


def _csv(path):
    with Path(path).open(encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        cols = next(rd)
        for r in rd:
            yield dict(zip(cols, r))


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def write(out, collector, people, meetings_path="meetings.json"):
    """Build the database (_write), and whatever happens, leave no
    temporary file behind: a stop part-way would otherwise leave about
    100 MB of half-built database in site/data/."""
    tmp = Path(out) / "granite-record.sqlite.part"
    try:
        return _write(Path(out), collector, people, meetings_path, tmp)
    except sqlite3.IntegrityError as e:
        raise SystemExit(f"The database is not written: a row repeats a key ({e}). The "
                         "table it names has two rows for one bill, or one ballot twice, "
                         "which the CSVs beside it hold too.")
    finally:
        tmp.unlink(missing_ok=True)


def _write(out, collector, people, meetings_path, tmp):
    """Build the database from the CSVs in out and the collector's rows;
    write out/NAME and return its manifest row (with "counts", the rows of
    each table). The CSVs must have been written first."""
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript("PRAGMA page_size=4096; PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;")
    con.executescript(SCHEMA)
    ins = lambda t, n, rows: con.executemany(f"INSERT INTO {t} VALUES ({','.join('?' * n)})", rows)
    counts = {}

    ins("meta", 2, sorted({
        "format": str(FORMAT),
        "what": "Granite Record: the public record of the New Hampshire General Court, "
                "as one database. See https://graniterecord.org/api",
        "rights": "The record is the State of New Hampshire's. What this site adds -- its ids, "
                  "joins and corrections -- is dedicated to the public domain under CC0 1.0; "
                  "the plain-English histories and the software are MIT licensed. DATA.md "
                  "says which is which.",
        "upstream": "https://gc.nh.gov",
    }.items()))

    rows = [(r["term"], r["bill"], _int(r["year"]), r["title"], r["sponsor"], r["committee"],
             r["topic"], r["status"], r["outcome"], r["passage"], _int(r["roll_calls"]),
             r["chapter"], r["chip"]) for r in _csv(out / "bills.csv")]
    # INSERT OR IGNORE nowhere: a duplicate key is a fault in bills.csv, and
    # stops the build here rather than vanishing into the database.
    ins("bills", 13, rows)
    counts["bills"] = len(rows)

    rc_id, rows = {}, []
    for i, r in enumerate(_csv(out / "rollcalls.csv"), 1):
        rc_id[r["roll_call"]] = i
        rows.append((i, r["roll_call"], r["term"], _int(r["year"]), r["body"], _int(r["number"]),
                     r["date"], r["bill"], r["question"], r["question_plain"], _int(r["yeas"]),
                     _int(r["nays"]), _int(r["not_voting"]), _int(r["passed"]), _int(r["procedural"]),
                     r["threshold_needed"], r["threshold_rule"], r["outcome_source"]))
    ins("rollcalls", 18, rows)
    counts["rollcalls"] = len(rows)

    person_of = {mid: p["person"] for p in people for mid in p.get("member_ids") or ()}
    codes, n, orphans = {}, 0, 0
    for f in sorted(out.glob("votes-*.csv")):
        rows = []
        for r in _csv(f):
            rc = rc_id.get(r["roll_call"])
            if rc is None:
                orphans += 1
                continue
            code = codes.setdefault(r["vote"], len(codes))
            rows.append((rc, r["member_id"], person_of.get(r["member_id"], ""), r["party"], code))
        ins("votes", 5, rows)
        n += len(rows)
    if orphans:
        raise SystemExit(f"{orphans:,} ballots name a roll call rollcalls.csv does not hold; "
                         "the database is not written.")
    ins("vote_values", 2, sorted((c, v) for v, c in codes.items()))
    counts["votes"], counts["vote_values"] = n, len(codes)

    for name in ("sponsors", "legislators"):
        cols = None
        rows = []
        for r in _csv(out / f"{name}.csv"):
            cols = cols or list(r)
            rows.append(tuple(r[c] for c in cols))
        if cols:
            con.execute(f'CREATE TABLE {name} ({", ".join(chr(34) + c + chr(34) + " TEXT" for c in cols)})')
            ins(name, len(cols), rows)
        counts[name] = len(rows)

    cols, rows = None, []
    for r in _csv(out / "proceedings.csv"):
        cols = cols or [c for c in r if c not in PROCEEDINGS_DROP]
        rows.append(tuple(r[c] for c in cols))
    if cols:
        con.execute(f'CREATE TABLE proceedings ({", ".join(chr(34) + c + chr(34) + " TEXT" for c in cols)})')
        ins("proceedings", len(cols), rows)
    counts["proceedings"] = len(rows)

    prow, nrow = [], []
    for p in people:
        prow.append((p["person"], p.get("name"), p.get("page"), 1 if p.get("sitting") else 0,
                     "".join(p.get("chambers") or []), p.get("first_term"), p.get("last_term"),
                     1 if p.get("provisional") else 0, p.get("replaced_by"), p.get("split_from")))
        for kind, field in (("employee_number", "employee_numbers"),
                            ("person_id", "person_ids"), ("member_id", "member_ids")):
            for num in p.get(field) or []:
                nrow.append((p["person"], kind, num))
    ins("people", 10, prow)
    ins("person_numbers", 3, nrow)
    counts["people"], counts["person_numbers"] = len(prow), len(nrow)

    ins("committee_reports", 16, collector.reports)
    ins("docket_reports", 12, collector.docket)
    ins("interim_study", 7, collector.study)
    ins("testimony", 10, collector.testimony)
    counts.update(committee_reports=len(collector.reports), docket_reports=len(collector.docket),
                  interim_study=len(collector.study), testimony=len(collector.testimony))

    meet = json.loads(Path(meetings_path).read_text(encoding="utf-8")) if Path(meetings_path).exists() else []
    meet = sorted(meet, key=lambda m: (m.get("date") or "", m.get("time") or "", m.get("body") or "",
                                       m.get("committee") or "", m.get("bill") or ""))
    ins("meetings", 10, [(m.get("date"), m.get("time"), m.get("body"), m.get("committee"),
                         m.get("kind"), m.get("venue"), m.get("room"), m.get("bill"),
                         m.get("noticed"), m.get("calendar")) for m in meet])
    counts["meetings"] = len(meet)

    con.commit()
    con.execute("VACUUM")
    con.close()
    raw = tmp.read_bytes()
    opened = len(raw)
    packed = lzma.compress(raw, format=lzma.FORMAT_XZ, preset=6)
    del raw
    tmp.unlink()
    (out / NAME).write_bytes(packed)
    return {"path": f"/data/{NAME}", "kind": "database", "rows": sum(counts.values()),
            "bytes": len(packed), "opened_bytes": opened,
            "sha256": hashlib.sha256(packed).hexdigest(), "encoding": "xz",
            "media_type": "application/vnd.sqlite3", "counts": counts}
