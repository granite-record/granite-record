#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.2
"""
Fill in what the bill status pages did not say, from the General Court's
own database.

    python3 fetch_status_db.py --dry-run
    python3 fetch_status_db.py

WHY THIS EXISTS

bill_status.json is built by fetch_bill_status.py from 2,234 requests to
gc.nh.gov -- one page per bill, on the server that has blocked this address
twice. Every fact on those pages is a column in the database, reachable in one
SELECT, and the database has a great deal the pages left blank:

    gen_status      blank on 577 bills
    house_status    blank on 311
    senate_status   blank on 121
    committee_code  blank on 188

WHY IT FILLS RATHER THAN REPLACES

Because the comparison said so. Measured on all 2,234 bills, the two sources
agree on every date introduced, every floor date, every LSR number and every
chamber; the 649 chapter numbers and 38 titles that "differ" differ by a
leading zero or a double space. But 21 chamber statuses genuinely disagree,
and on those the DATABASE is behind: HB592 reads NO ACTION in the Senate and
was signed into law as Chapter 3 in March 2025. The status columns are not
always advanced once a bill is finished.

Six general statuses disagree the other way. The database calls HB1102 LAW
WITHOUT SIGNATURE and the page calls it VETO OVERRIDDEN, and the docket shows
both are true: the House and Senate overrode the veto, and it was then enacted
under Article 44 Part II without the governor's signature. The database is
describing the constitutional mechanism and the page is describing what
happened. "Became law unsigned" would hide a legislature reversing a governor,
so the page's answer is the better headline -- and build_site_v2.docket_outcome
already reaches it from the docket for all six regardless.

So: a field the pages filled is left exactly as it is. A field they left empty
is filled from the database. A bill they do not have at all is added whole.
Nothing gets worse and about a thousand fields get better.

For a past term, where there are no pages and no scrape, this is simply the
source.

WHAT IT CANNOT SUPPLY

text_pdf, and the text_id and text_year it is built from. Those come from the
legacy bill-text URL and the database's LegislationText carries a different id
space -- HB1442 is 1937 in the page's URL and 23441 in the database. The
database does hold the full text of every version, which is a better answer
than the link and a larger change than this.

THIS IS NOT THE WEB SERVER. It is the SQL host the General Court publishes
credentials for, at gc.nh.gov/downloads. Nothing here touches gc.nh.gov, and
every statement is a SELECT.
"""

import argparse
import collections
import json
import sys
import tempfile
from pathlib import Path

import probe_db
import proceedings as P

SQL = """
SELECT ISNULL(CondensedBillNo,''),
       CAST(ISNULL(sessionyear,0) AS varchar(4)),
       ISNULL(LSRTitle,''),
       ISNULL(CAST(lsr AS varchar(20)),''),
       ISNULL(LegislativeBody,''),
       ISNULL(CAST(LocalCode AS varchar(10)),''),
       ISNULL(GeneralStatusCode,''),
       ISNULL(HouseStatusCode,''),
       ISNULL(SenateStatusCode,''),
       ISNULL(FORMAT(HouseDateIntroduced,'M/d/yyyy'),''),
       ISNULL(FORMAT(SenateDateIntroduced,'M/d/yyyy'),''),
       ISNULL(FORMAT(housefloordate,'M/d/yyyy'),''),
       ISNULL(FORMAT(SenateFloorDate,'M/d/yyyy'),''),
       ISNULL(HouseCurrentCommitteeCode,''),
       ISNULL(SenateCurrentCommitteeCode,''),
       ISNULL(CAST(ChapterNo AS varchar(20)),'')
FROM Legislation
WHERE (%s = 0 OR sessionyear IN (%d, %d))
ORDER BY sessionyear, CondensedBillNo
"""

COLS = ["bill", "year", "title", "lsr", "body", "local", "gcode", "hcode",
        "scode", "hintro", "sintro", "hfloor", "sfloor", "hcmte", "scmte",
        "chapter"]

# The fields this fills, and where each comes from. Anything not on this list
# -- text_pdf, text_id, text_year, sponsors -- the database does not carry and
# this does not touch.
FILLS = ["title", "lsr", "body", "local", "gen_status", "house_status",
         "senate_status", "date_introduced", "floor_date", "committee_code",
         "chapter"]


def codes(path):
    """GeneralCodes.txt and BodyStatusCodes.txt: '05' -> 'SIGNED BY GOVERNOR'."""
    out = {}
    for line in Path(path).open(encoding="utf-8-sig", errors="replace"):
        p = line.strip().split("|")
        if len(p) >= 2:
            out[p[0].strip()] = p[1].strip()
    return out


def differs(a, b):
    """Do these two say different things, rather than spell one thing two ways?

    The pages write an LSR number as 20 and the database writes 0020; the pages
    write chapter 0140 and the database writes 140; a title runs "probate.
    Providing" in one and "probate.  Providing" in the other, and the pages put
    a full stop on the end of every title whether or not it already has one --
    SB629 ends 'Oliveira Circle.".' there and 'Oliveira Circle."' here.
    Counting those as disagreements put the number at 2,005 and buried the 27
    that are real.
    """
    a, b = " ".join((a or "").split()), " ".join((b or "").split())
    if a == b:
        return False
    if a.rstrip(". ") == b.rstrip(". "):
        return False
    if a.lstrip("0") == b.lstrip("0") and (a + b).strip("0").isdigit():
        return False
    return True


def record(r, gen, body):
    """One database row in bill_status.json's shape."""
    house = r["body"] == "H"
    return {
        "title": r["title"],
        "lsr": r["lsr"],
        "body": r["body"],
        # The pages write N and Y; the column is a bit.
        "local": {"True": "Y", "False": "N"}.get(r["local"], ""),
        "gen_status": gen.get(r["gcode"], ""),
        "house_status": body.get(r["hcode"], ""),
        "senate_status": body.get(r["scode"], ""),
        "date_introduced": r["hintro"] if house else r["sintro"],
        "floor_date": r["hfloor"] if house else r["sfloor"],
        # The bill's own chamber first. The database holds both, and a bill
        # that has crossed over is with a committee in the other chamber; the
        # page shows one code and does not say which chamber it belongs to.
        "committee_code": (r["hcmte"] or r["scmte"]) if house
                          else (r["scmte"] or r["hcmte"]),
        "chapter": r["chapter"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="bill_status.json")
    ap.add_argument("--term-start", type=int, default=0,
                    help="the odd year a term begins in; 0 reads every year "
                         "the database has")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would be filled and write nothing")
    a = ap.parse_args()

    base = (f"Database={probe_db.DATABASE};User ID={probe_db.USER};"
            f"Password={probe_db.PASSWORD};Encrypt=False;"
            "TrustServerCertificate=True;Connect Timeout=20")
    cs = f"Server={probe_db.HOST};{base}"

    ts = a.term_start
    sql = SQL % (1 if ts else 0, ts, ts + 1)
    print("SELECT only, one connection: every bill's status row"
          + (f", term {ts}-{ts + 1}" if ts else ""))
    tmp = tempfile.TemporaryDirectory()
    raw = Path(tmp.name) / "legislation.txt"
    n, err = probe_db.run_to_file(cs, sql, raw, newline=" ", every=2000,
                                  label="bills ")
    if err:
        sys.exit(f"  the database refused: {err}")
    print(f"  {n:,} bills")
    if not n:
        sys.exit("  nothing came back. Legislation held 2,234 on 6 September.")

    gen, body = codes("GeneralCodes.txt"), codes("BodyStatusCodes.txt")
    # {term: {bill: row}}. A bill number is unique within a term and not across
    # them, so the term the row's own session year puts it in is what it has to
    # be filed under. Legislation holds the current session only today, but the
    # grouping costs nothing and is what stops a future run of two terms
    # merging HB100 of one into HB100 of the other.
    db = collections.defaultdict(dict)
    for line in raw.open(encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("|")
        if len(p) == len(COLS):
            r = dict(zip(COLS, p))
            db[P.term_of(r.get("year") or "")][r["bill"].upper()] = r
    tmp.cleanup()
    db.pop("", None)
    print("  " + ", ".join(f"{t}: {len(v):,}" for t, v in sorted(db.items())))

    out_path = Path(a.out)
    have = {}
    if out_path.exists():
        try:
            have = json.loads(out_path.read_text(encoding="utf-8"))
        except ValueError:
            have = {}
    # bill_status.json is {term: {bill: record}}. A file still in the flat
    # shape is the newest term's, which is what it was.
    newest = max(db) if db else ""
    have = P.in_term(have, newest)
    print("  already on file: "
          + (", ".join(f"{t}: {len(v):,}" for t, v in sorted(have.items()))
             or "nothing"))

    filled = collections.Counter()
    added, kept = [], collections.Counter()
    for term, rows in db.items():
        slot = have.setdefault(term, {})
        for bid, r in rows.items():
            want = record(r, gen, body)
            cur = slot.get(bid)
            if cur is None:
                slot[bid] = want
                added.append(bid)
                continue
            for f in FILLS:
                if (cur.get(f) or "").strip():
                    # A field the pages filled is the pages' answer. On the
                    # 21 chamber statuses that disagree the database is the
                    # one that is behind, so this is not a tie being broken at
                    # random.
                    if (want.get(f) or "").strip() and differs(want[f], cur[f]):
                        kept[f] += 1
                    continue
                if (want.get(f) or "").strip():
                    cur[f] = want[f]
                    filled[f] += 1

    print(f"\n  {len(added):,} bills the pages do not have, added whole")
    if filled:
        print("  fields filled where the pages were blank:")
        for f, c in filled.most_common():
            print(f"    {c:6,}  {f}")
    else:
        print("  nothing was blank; nothing filled")
    if kept:
        print("  fields where the two sources genuinely disagree, the pages' "
              "answer kept:")
        for f, c in kept.most_common():
            print(f"    {c:6,}  {f}")

    if a.dry_run:
        print(f"\n--dry-run: nothing written to {a.out}")
        return 0
    if not added and not filled:
        # Not an error -- a second run has nothing to do -- but say it, rather
        # than rewriting the file and reporting success.
        print(f"\n{a.out} is unchanged.")
        return 0
    out_path.write_text(json.dumps(have, indent=1), encoding="utf-8")
    print(f"\n  -> {a.out}  ("
          + ", ".join(f"{t}: {len(v):,}" for t, v in sorted(have.items())) + ")")
    print("Re-running fetch_bill_status.py rebuilds this file from the pages "
          "and drops what was filled here, so run this after it, not before.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
