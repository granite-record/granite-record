#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.1
"""
The Secretary of State's count of the questions on a general election's
ballot, read into collected/ballot_questions.json, for 2022, 2024 and 2026.

    python3 src/parse/parse_sos_questions.py          # write collected/ballot_questions.json
    python3 src/parse/parse_sos_questions.py --check  # compare again; write nothing

WHAT IT READS, in records/sources/, saved by a person in a browser byte for
byte (nothing here asks the network):

    2022-ge-concon-questions.xls                    both of 2022's questions: a summary
                                                    of the counties, then a sheet per county
    2024-ge-constitutional-questions_3.xls          2024's one question: a summary sheet
    2026-ge-constitutional-question-summary.xlsx    2026's Question No. 1 only, by county
    2026-ge-constitutional-questions-<county>.xlsx  2026's two questions, town by town, one
                                                    file a county: the ONLY place the count
                                                    of Question No. 2 (HB 1300) is printed

WHAT IT WRITES. For each election day, each question's yes and no -- the
statewide figure the Secretary of State prints where it prints one (2022,
2024, 2026's Question No. 1) and, where it does not (2026's Question No. 2),
the sum of the ten counties' Totals rows, said so in "how" -- and each
county's yes and no. Which sort of question each is (a constitutional
amendment, the convention question, the school local tax cap) is KINDS below,
the one place this file decides anything: the files do not say. The names of
a measure come from the file ("HB 1300" is a cell of the 2026 files).

IT REFUSES RATHER THAN GUESSES: a question number KINDS does not know; a
county missing or twice; a county's towns that do not add up to its own
Totals row; ten counties that do not add up to the statewide summary
(2022, 2024), and, for 2026's Question No. 1, a difference is not refused
but kept in "county_sum" beside the summary's figure, because the
Secretary of State's own files disagree there (the page says so).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import hashlib
import json
import re

import parse_sos_results as PSR
import state_settings as ST

SOURCES = Path("records") / "sources"
OUT = Path("collected") / "ballot_questions.json"
COUNTIES = ST.COUNTIES_LOWER

# What each question is, by (election day, question number). The files print
# "Question No. 2" and nothing of what it asks; the 2022 workbook is named
# "concon", and its second question is the one Part Second, Article 100(b) of
# the constitution has the Secretary of State submit every ten years. 2026's
# second is the one its files head "HB 1300" (chapter 324 of 2026). The
# first of each year is a constitutional amendment, which
# corrections/ballot_results.json holds as a CACR.
KINDS = {
    ("2022-11-08", 1): "cacr", ("2022-11-08", 2): "convention",
    ("2024-11-05", 1): "cacr",
    ("2026-11-03", 1): "cacr", ("2026-11-03", 2): "local_cap",
}


class Refused(Exception):
    pass


def title_day(rows, where):
    m = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", str(rows[0][0] or ""))
    if not m:
        raise Refused(f"{where}: no election day in its first cell {rows[0][0]!r}")
    return datetime.datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()


def question_columns(row, where):
    """{number: yes column} from the row that names the questions ("Question
    No. 2"), whose Yes sits there and whose No sits beside it."""
    cols = {}
    for c, v in enumerate(row):
        m = re.fullmatch(r"Question No\. (\d+)", str(v or ""))
        if m:
            cols[int(m.group(1))] = c
    if not cols:
        raise Refused(f"{where}: no 'Question No. N' on the row {row!r}")
    return cols


def county_of(name, where):
    m = re.fullmatch(r"(\w+) County", str(name or ""))
    if not m or m.group(1).lower() not in COUNTIES:
        raise Refused(f"{where}: {name!r} is not a county")
    return m.group(1)


def summary_block(rows, where):
    """(election, {question: {county: [yes, no]}}, {question: [yes, no]} or
    None) from a sheet that lists the counties: the 2022 and 2024 summaries
    and 2026's summary of Question No. 1."""
    day = None
    for i, r in enumerate(rows):
        if any(re.fullmatch(r"Question No\. \d+", str(v or "")) for v in r):
            head = i
            break
    else:
        raise Refused(f"{where}: no row of questions")
    cols = question_columns(rows[head], where)
    day = title_day(rows, where)
    per = {q: {} for q in cols}
    totals = None
    for r in rows[head + 2:]:
        first = r[0] if r else None
        if first is None:
            continue
        if str(first).lower() == "totals":
            totals = {q: [r[c], r[c + 1]] for q, c in cols.items()}
            break
        county = county_of(first, where)
        if county in per[next(iter(per))]:
            raise Refused(f"{where}: {county} twice")
        for q, c in cols.items():
            per[q][county] = [r[c], r[c + 1]]
    return day, per, totals


def sums(per):
    return [sum(v[0] for v in per.values()), sum(v[1] for v in per.values())]


def county_file(path):
    """(election, county, {question: [yes, no]}, {question: measure}) from
    one of 2026's county files, its towns held to its TOTALS row."""
    (name, rows), = PSR.sheets(path)
    where = f"{Path(path).name}, sheet {name!r}"
    county = county_of(rows[0][0], where)
    m = re.fullmatch(r"([A-Z][a-z]+ \d{1,2}, \d{4})", str(rows[1][0]).replace("  ", " "))
    if not m:
        raise Refused(f"{where}: no election day in {rows[1][0]!r}")
    day = datetime.datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
    cols = question_columns(rows[1], where)
    measure = {}
    for q, c in cols.items():
        head = rows[0][c]
        if head and re.fullmatch(r"[A-Z]{2} \d+", str(head)):
            measure[q] = str(head)
    towns = {q: [0, 0] for q in cols}
    totals = None
    for i, r in enumerate(rows[3:], start=4):
        if r[0] is None:
            continue
        if str(r[0]).upper() == "TOTALS":
            totals = {q: [r[c], r[c + 1]] for q, c in cols.items()}
            continue
        for q, c in cols.items():
            for j in (0, 1):
                v = r[c + j]
                if not isinstance(v, int) or isinstance(v, bool):
                    raise Refused(f"{where}, row {i}: {r[0]!r} has {v!r} where a count belongs")
                towns[q][j] += v
    if totals is None:
        raise Refused(f"{where}: no TOTALS row")
    for q in cols:
        if towns[q] != totals[q]:
            raise Refused(f"{where}: the towns add up to {towns[q]} for Question No. {q}, "
                          f"the file's TOTALS say {totals[q]}")
    return day, county, totals, measure


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_all(root="."):
    src = Path(root) / SOURCES
    out, used = {}, []

    def take(path):
        used.append({"file": Path(path).name, "sha256": digest(path)})

    def add(day, number, yes, no, counties, how, measure=None, county_sum=None):
        kind = KINDS.get((day, number))
        if kind is None:
            raise Refused(f"{day} Question No. {number} is in the files and KINDS does not say "
                          "what it is: add it there, from the question's own words")
        q = {"number": number, "label": f"Question No. {number}", "kind": kind,
             "yes": yes, "no": no, "how": how,
             "counties": dict(sorted(counties.items()))}
        if measure:
            q["measure"] = measure
        if county_sum is not None:
            q["county_sum"] = county_sum
        out.setdefault(day, []).append(q)

    # 2022 and 2024: a summary sheet, its Totals row the statewide figure.
    for name, first in (("2022-ge-concon-questions.xls", True),
                        ("2024-ge-constitutional-questions_3.xls", True)):
        p = src / name
        if not p.exists():
            raise Refused(f"{p.as_posix()} is not here")
        take(p)
        sheet_name, rows = PSR.sheets(p)[0]
        where = f"{name}, sheet {sheet_name!r}"
        day, per, totals = summary_block(rows, where)
        for q in per:
            if totals is None:
                raise Refused(f"{where}: no Totals row")
            if sums(per[q]) != totals[q]:
                raise Refused(f"{where}: the counties add up to {sums(per[q])} for Question "
                              f"No. {q}, the Totals row says {totals[q]}")
            if len(per[q]) != len(COUNTIES):
                raise Refused(f"{where}: {len(per[q])} counties, not {len(COUNTIES)}")
            add(day, q, totals[q][0], totals[q][1], per[q],
                "the Totals row of the Secretary of State's statewide summary")

    # 2026: Question No. 1 has a summary; both questions are in the county files.
    p = src / "2026-ge-constitutional-question-summary.xlsx"
    take(p)
    sheet_name, rows = PSR.sheets(p)[0]
    where1 = f"{p.name}, sheet {sheet_name!r}"
    # Its layout is its own: the title, "Question No. 1" alone in the first column, Yes and
    # No on the row below, then a row a county, in the columns beside.
    day1 = title_day(rows, where1)
    if rows[2][0] != "Question No. 1" or rows[3][1:3] != ["Yes", "No"]:
        raise Refused(f"{where1}: not the layout this reads: {rows[2]!r}, {rows[3]!r}")
    per1 = {1: {}}
    tot1 = None
    for r in rows[4:]:
        if r[0] is None:
            continue
        if str(r[0]).lower() == "totals":
            tot1 = {1: [r[1], r[2]]}
            break
        per1[1][county_of(r[0], where1)] = [r[1], r[2]]
    if tot1 is None or sums(per1[1]) != tot1[1] or len(per1[1]) != len(COUNTIES):
        raise Refused(f"{where1}: its ten counties do not add up to its Totals row")
    files = {}
    measures = {}
    for county in COUNTIES:
        f = src / f"2026-ge-constitutional-questions-{county}.xlsx"
        if not f.exists():
            raise Refused(f"{f.as_posix()} is not here")
        take(f)
        day, c, totals, measure = county_file(f)
        if c.lower() != county or day != day1:
            raise Refused(f"{f.name} is {c} County on {day}, not {county} on {day1}")
        files[c] = totals
        measures.update(measure)
    numbers = sorted({q for t in files.values() for q in t})
    for q in numbers:
        per = {c: t[q] for c, t in files.items()}
        county_total = sums(per)
        if q in per1:
            if q != 1:
                raise Refused("the 2026 summary holds a question this reads as Question No. 1 only")
            yes, no = tot1[q]
            how = "the Totals row of the Secretary of State's statewide summary"
            # The summary's counties are its own; the county files' are the ones kept in
            # "counties", so the pages can say where the two differ.
            add(day1, q, yes, no, per, how, measures.get(q),
                county_sum=county_total if county_total != [yes, no] else None)
        else:
            add(day1, q, county_total[0], county_total[1], per,
                "the sum of the ten county files' TOTALS rows: the statewide summary does "
                "not hold this question", measures.get(q))
    for day in out:
        out[day].sort(key=lambda q: q["number"])
    return {"_about": ABOUT, "_source": sorted(used, key=lambda s: s["file"]),
            "elections": dict(sorted(out.items()))}


ABOUT = ("The Secretary of State's count of the questions on the ballot at the 2022, 2024 and "
         "2026 general elections, read from the spreadsheets saved in records/sources/ by "
         "src/parse/parse_sos_questions.py, which says what it reads, what 'how' means and what "
         "it refuses. Nothing here is the person's: a person runs the script and commits the "
         "file, so the diff is the review. 'kind' is the script's KINDS table, from the "
         "question's own words, not from a file. A constitutional amendment's count is also in "
         "corrections/ballot_results.json, which the pages read for it.")


def dumps(doc):
    lines = ["{", ' "_about": ' + json.dumps(doc["_about"], ensure_ascii=False) + ",",
             ' "_source": [',
             ",\n".join("  " + json.dumps(s) for s in doc["_source"]), " ],", ' "elections": {']
    days = list(doc["elections"])
    for i, d in enumerate(days):
        lines.append(f"  {json.dumps(d)}: [")
        qs = doc["elections"][d]
        for j, q in enumerate(qs):
            lines.append("   " + json.dumps(q, ensure_ascii=False) + ("," if j < len(qs) - 1 else ""))
        lines.append("  ]" + ("," if i < len(days) - 1 else ""))
    lines += [" }", "}"]
    return "\n".join(lines) + "\n"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--check", action="store_true", help="compare with the committed file; "
                                                         "write nothing")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    try:
        doc = read_all(".")
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    except PSR.Unreadable as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    out = Path(a.out)
    text = dumps(doc)
    if a.check:
        try:
            now = json.loads(text)
            was = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"REFUSED: {out.as_posix()} will not read: {e}", file=sys.stderr)
            return 1
        if now != was:
            print(f"{out.as_posix()} is not what the saved files say", file=sys.stderr)
            return 1
        print(f"{out.as_posix()} is what the saved files say.")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    n = sum(len(v) for v in doc["elections"].values())
    print(f"wrote {out.as_posix()}: {n} questions on {len(doc['elections'])} ballots")
    for d, qs in doc["elections"].items():
        for q in qs:
            print(f"  {d} {q['label']} ({q['kind']}): yes {q['yes']:,}, no {q['no']:,}"
                  + (f"; the ten county files say {q['county_sum']}" if q.get("county_sum") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
