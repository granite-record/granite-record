#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
The General Court database's status codes, where the status page states
nothing: the dump's own codes in the status page's words, a term's rows read
from whichever dump holds them, its own frozen copy first (db_statuses),
the terms no dump holds (terms_without_a_dump, no_dump_for), and a status
page record with each field it left blank filled from the database
(fill_status_from_db). Read from db/ on this disk; it asks no network.

    import db_status as DBS
    DBS.fill_status_from_db(st, b, bid, term, current)   # the filled record, or None
    DBS.no_dump_for(term)                                # what to say, or ""

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited: the
section headed "the database's status codes, where the status page states
nothing", from its comment to fill_status_from_db, one block. A term's
reading is proceedings.py's (term_of, per_term). It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

import json
from pathlib import Path

import proceedings as P


# ---- the database's status codes, where the status page states nothing ------
#
# bill_status.json is the status pages, and they leave fields blank: of the
# 2,243 records of 2025-2026, 577 have no general status there, 311 no House
# status and 121 no Senate status. The General Court's own database has a
# code in every one of those columns, and its dump is on this disk
# (db/Legislation.psv, read with GeneralCodes.txt and BodyStatusCodes.txt; no
# network). HB 1708 and HB 1824 of 2026 were reported to the floor, met a
# failed motion to take them up at once, and were never voted on: the
# database says DIED, SESSION ENDED for each, the page says nothing, and they
# read "In committee".
#
# FILLED, NEVER REPLACED. The dump is older than the pages and behind them
# where both have a value -- HB 592 of 2025 reads NO ACTION in the Senate
# there and is Chapter 3 -- so a field the page filled is left exactly as it
# is.
#
# AND IT ANSWERS ONLY WHERE THIS SITE WOULD OTHERWISE GUESS (bill_disposition:
# the page's fields state nothing, and the docket gives classify() nothing
# better than "In committee" or "In progress"). A database code beside a page
# field that already answers would outrank it by STATED's order alone: HB 751
# and HB 1709 of 2026 are LAID ON TABLE on the page's Senate field, which is
# what their dockets end on, and the database's House code for both is DIED,
# SESSION ENDED. A reading of the docket's own decisions outranks it too --
# CACR 10 of 2026 lost its vote, and the database says DIED, SESSION ENDED --
# and so does every dated row that outranks a page field: a refusal to
# concur, a conference's outcome. And a code the bill's own journey
# contradicts is not taken: the database is stale on some bills (SB 532 of
# 2026 reads IN COMMITTEE and was killed 16-8), and "In committee" over a
# chamber's passage would be worse than the guess.
#
# The page's table of the General Court's fields still shows what the status
# page says, and the status's source is "General Court database".
DB_LEGISLATION = Path("db") / "Legislation.psv"
DB_STATUS_COLUMNS = {"sessionyear": 2, "lsr": 3, "CondensedBillNo": 14,
                     "HouseStatusCode": 21, "SenateStatusCode": 29, "GeneralStatusCode": 34}
_DB_STATUS = {}


def _status_codes(path):
    """GeneralCodes.txt or BodyStatusCodes.txt: {"31": "DIED, SESSION ENDED"}."""
    out = {}
    try:
        for line in Path(path).open(encoding="utf-8-sig", errors="replace"):
            p = line.rstrip("\n").split("|")
            if len(p) >= 2 and p[0].strip():
                out[p[0].strip()] = p[1].strip()
    except OSError:
        pass
    return out


# A TERM'S ROWS, WHEREVER THEY ARE, AND NOT "THE CURRENT TERM'S". The dump is
# read by each row's own session year, and a term whose views the General
# Court has turned over to the next is read from the copy frozen at its end
# (db/term/<term>/Legislation.psv, with the _columns.json it was dumped with:
# cloud_kit.json's "frozen" list, which build_bill_versions.py reads the same
# way). The first version of this answered only for the term that was current
# on the night of the build, so on the first night of 2027-2028 the five
# records it settles -- HB 1708 and HB 1824 of 2026, HCR 1, HCR 4 and HCR 9 of
# 2025 -- would have gone back to "In committee" and "In progress", in a term
# by then finished, with nothing failing. Where both hold a measure the
# current dump is the later word, and is read last.
DB_FROZEN = Path("db") / "term"


def db_statuses(term, folder="."):
    """{BILL: {"lsr", "gen_status", "house_status", "senate_status"}} for the
    measures of `term` in the database dump under `folder` -- the term's own
    frozen copy, then the current dump -- in the status page's own words; {}
    where no dump holds the term or a code table is not there."""
    folder = Path(folder)
    gen = _status_codes(folder / "GeneralCodes.txt")
    body = _status_codes(folder / "BodyStatusCodes.txt")
    out = {}
    if not (gen and body):
        return out
    for dump in (folder / DB_FROZEN / term, folder / "db"):
        at = dict(DB_STATUS_COLUMNS)
        for cols_at in (dump / "_columns.json", folder / "db" / "_columns.json"):
            try:
                cols = json.loads(cols_at.read_text(encoding="utf-8")).get("Legislation") or []
            except (OSError, ValueError):
                continue
            at.update({n: cols.index(n) for n in at if n in cols})
            break
        try:
            fh = (dump / DB_LEGISLATION.name).open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                f = line.rstrip("\n").split("|")
                if len(f) <= max(at.values()):
                    continue
                year = f[at["sessionyear"]].strip()
                if not year.isdigit() or P.term_of(year) != term:
                    continue
                out[f[at["CondensedBillNo"]].strip().upper()] = {
                    "lsr": f[at["lsr"]].strip().lstrip("0"),
                    "gen_status": gen.get(f[at["GeneralStatusCode"]].strip(), ""),
                    "house_status": body.get(f[at["HouseStatusCode"]].strip(), ""),
                    "senate_status": body.get(f[at["SenateStatusCode"]].strip(), "")}
    return out


def terms_without_a_dump(bills, pages):
    """[(term, its measures whose status page states nothing)] for each of
    the two newest terms that has such measures and that no database dump
    holds.

    THE NIGHT THE GENERAL COURT'S VIEWS TURN OVER, the dump on disk holds the
    new term and, unless a copy was frozen under db/term/, nothing holds the
    one just finished: HB 1708 and HB 1824 of 2026 and HCR 1, HCR 4 and HCR 9
    of 2025 go back to "In committee" and "In progress". The build asked only
    about the newest term, which the new dump answers, and said nothing; the
    check that asks about both (preflight's "a database dump on this disk
    holds each of the two newest terms ...") is a data check, which the night
    does not run. main() says this as its last lines.
    """
    if not bills:
        return []
    current = max(bills)
    fields = ("gen_status", "house_status", "senate_status")
    out = []
    for term in sorted(bills)[-2:]:
        page = P.per_term(pages, term, current)
        blank = sorted(b for b, rec in bills[term].items()
                       if not any(((page.get(b) or {}).get(f) or rec.get(f) or "").strip()
                                  for f in fields))
        if blank and no_dump_for(term):
            out.append((term, blank))
    return out


def no_dump_for(term):
    """What to say of a term no database dump holds, or "" where one does."""
    if not term:
        return ""
    if term not in _DB_STATUS:
        _DB_STATUS[term] = db_statuses(term)
    if _DB_STATUS[term]:
        return ""
    return (f"NO DATABASE DUMP HOLDS {term} ({DB_LEGISLATION.as_posix()}, or "
            f"{(DB_FROZEN / term / DB_LEGISLATION.name).as_posix()}): a bill of it whose "
            "status page states nothing keeps what the docket alone gives it")


def fill_status_from_db(st, b, bid, term, current, db=None):
    """The status page's record with each field it left blank taken from the
    database's row for the same measure, or None where there is nothing to
    fill: no dump holding the measure's term, no row for this bill and this
    LSR, or no blank the database has a word for. `current` is not asked:
    a term is read from whichever dump holds its rows (db_statuses)."""
    if db is None:
        if term not in _DB_STATUS:
            _DB_STATUS[term] = db_statuses(term)
        db = _DB_STATUS[term]
    row = db.get(str(bid).upper())
    if not row or row["lsr"] != str((b or {}).get("lsr_num") or "").lstrip("0"):
        return None
    fill = {k: row[k] for k in ("gen_status", "house_status", "senate_status")
            if row.get(k) and not ((st or {}).get(k) or "").strip()}
    return {**(st or {}), **fill} if fill else None
