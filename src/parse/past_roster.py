#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.2
"""
Who the printed sponsors of 1989 to 1998 are, where that is certain.

    python3 src/parse/past_roster.py            # the counts, term by term; writes nothing
    python3 src/parse/past_roster.py --list     # every ambiguous and unmatched row, as printed

No network. It reads db/past/ (the PastSponsors and PastLegislation views),
data/bills.json, past_members.json, db/Legislators.psv and text_sponsors.json.

WHY (historical-roster design, Option A, 13 November 2026). The bills of 1989
to 1998 print their sponsors as a surname, sometimes an initial, and a seat:
"Rep. Guay, Coos 6". No roll call of those years exists, so text_sponsors.py
could place nobody, and the Sponsor filter listed three Allens as one "Allen".
But the General Court's own sponsor record holds, for every one of those bills,
the employee numbers of its sponsors (PastSponsors, keyed by LSR), and the
General Court's list of past members (past_members.json) gives each number a
name -- first name, chamber, last seat. The link was always there:

    printed sponsor -> this bill's PastSponsors rows (by its stored LSR)
                    -> employee number -> full name

WHAT IS CERTAIN. A printed sponsor is placed on a person only where the bill's
OWN sponsor rows settle it: the printed surname (exactly, or with the initial
or first name printed before it) fits one employee number on that bill and
nobody else's. Two of one surname on one bill (D. Lawton, R. Lawton) are told
apart only by an initial or first name that fits one of them. Nothing else
settles a row: no fuzzy spelling, no seat, no name across the state. A misprint
("Buckly"), a row two numbers fit with nothing to choose between them, and a
number the General Court's list does not name are left exactly as printed.

A SECOND STEP FOR A LINE TWO NUMBERS FIT (settle, 13 November 2026). "Rep. Torr of Strafford Dist. 6"
and "Sen. Torr of Dist. 21" on one bill, with Ann Torr and Franklin Torr both among its sponsors, is
told apart only by the seat, and only by a seat list OF THE TERM: past_members.json holds one seat per
number and often a later one. generated/manual_seats.json (build_manual_seats.py) is that list, read from
the Manual for the General Court of the term. The owner's rule: "as accurate as possible and not guess if
we aren't confident". A line is settled only if the printed chamber and seat are the seat the term's list
gives exactly one candidate (joined by the General Court's first name and surname, never an initial) and
every other candidate's seat there is known and different, and the number is of the printed chamber. Anything
less stays as printed, and settle() says why.

THE TWO KINDS OF IDENTIFIER (the owner, 13 November 2026). `employee` is the
General Court's employee number, digits, unchanged. Anyone the record names
with no employee number would get a Granite Record id, `gr-NNNN`, from
src/parse/gr_ids.py, in a field of its own; the two are never written into
each other's field.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
from collections import Counter, defaultdict

import past_members
import past_sponsors as PSP
import text_sponsors as TS

# The terms whose sponsors this places: the bills have no roll call to place them by.
PRE_TERMS = ("1989-1990", "1991-1992", "1993-1994", "1995-1996", "1997-1998")
SOURCE_NAME = "General Court list of members"

CERTAIN, AMBIGUOUS, UNMATCHED = "certain", "ambiguous", "unmatched"
# What a sponsor record placed on a person says in `matched`.
MATCHED = "General Court sponsor record"


def shared_names(term_sponsors, key=lambda n: n):
    """The full names (through `key`) that more than one employee number of a term carries,
    among the sponsors placed by the bill's own record. Two Frank Allens are told apart by
    their seats again; one is the person's name alone."""
    who = defaultdict(set)
    for recs in (term_sponsors or {}).values():
        for r in recs or ():
            if r.get("matched") == MATCHED and r.get("employee"):
                who[key(r.get("name") or "")].add(r["employee"])
    return {n for n, e in who.items() if len(e) > 1}


# ------------------------------------------------------------------ names

def split_label(name):
    """("Dykstra", "Leona", "", "375839") from past_members.json's "Dykstra (SEE Emp #375839), Leona".

    last, first, suffix, and the employee number a "SEE Emp #" note points to (the General
    Court's own statement that two numbers are one person), or "". The name is the General
    Court's: "Calvert (Ziegra)" keeps its parenthesis, "Barnes, Jr., John" gives the suffix."""
    raw = (name or "").strip()
    see = ""
    m = re.search(r"\(\s*SEE\s+Emp\s*#\s*(\d+)\s*\)", raw, re.I)
    if m:
        see = m.group(1)
        raw = (raw[:m.start()] + raw[m.end():]).replace(" ,", ",")
    last, _, rest = raw.partition(",")
    parts = [p.strip() for p in rest.split(",") if p.strip()]
    suffix = [p for p in parts if TS.letters(p) in TS.SUFFIXES]
    first = " ".join(p for p in parts if TS.letters(p) not in TS.SUFFIXES)
    last = re.sub(r"(\S)\(", r"\1 (", last.strip())
    return last, first, " ".join(suffix), see


def full_name(name):
    """"Leona Dykstra": first name first, in the General Court's spelling."""
    last, first, suffix, _see = split_label(name)
    return " ".join(x for x in (first, last, suffix) if x)


# ------------------------------------------------------------------ matching

def _fit(sp, rows, people):
    """([employee numbers], k, how) the printed sponsor fits on the bill's rows: the first way of
    reading the printed words (all of them a surname, then all but the first, ...) that fits
    anybody, and every number it fits. ([], 0, "") where nothing does."""
    emps = list(dict.fromkeys(r["employee"] for r in rows))
    words = sp["words"]
    for k in range(len(words)):
        key = TS.letters("".join(words[k:]))
        if not key:
            continue
        cands = [e for e in emps if key in people.surnames(e)]
        if k:
            cands = [e for e in cands
                     if any(TS.given_fits(words[:k], f) for f in people.firsts(e))]
        if cands:
            return cands, k, key
    return [], 0, ""


def place(sp, rows, people):
    """(state, employee or None, why) for one printed sponsor against one bill's rows.

    `rows` are the bill's PastSponsors rows ({"employee", ...}); `people` is a
    past_sponsors.People. The printed words are tried as past_sponsors and Sat.resolve try
    them: all of them as a surname, then all but the first (the first an initial or a first
    name), and so on, stopping at the first that fits anybody."""
    cands, k, _key = _fit(sp, rows, people)
    words = sp["words"]
    if len(cands) == 1:
        return CERTAIN, cands[0], ("the only number of that surname on the bill's sponsor record"
                                   if not k else "the only number on the bill's record that "
                                   "fits the surname and the initial or first name printed")
    if cands:
        return AMBIGUOUS, None, f"{len(cands)} numbers on the bill's record fit {' '.join(words)!r}"
    return UNMATCHED, None, "no number on the bill's sponsor record fits the printed name"


def place_bill(pieces, rows, people):
    """[(state, employee, why)] for each printed sponsor of one bill."""
    return [place(sp, rows, people) for sp in pieces]


# ------------------------------------------------------------------ the second step: the term's seat list

SEAT_TABLE = Path("generated/manual_seats.json")
SETTLED = "settled"


def seat_table(path=None):
    """generated/manual_seats.json (build_manual_seats.py), or None where it is not on this disk."""
    p = Path(path or SEAT_TABLE)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _manual_rows(table, term):
    t = ((table or {}).get("terms") or {}).get(term)
    if not t or t.get("measuring_only"):
        return []
    return [("H", r) for r in t.get("house") or ()] + [("S", r) for r in t.get("senate") or ()]


def _table_name_fits(row_name, emp, people):
    """The seat list's full name is the General Court's for this number: the surname is one of the
    number's surnames, and the first names are the same word -- a lone initial is not enough on
    either side, and a short form of a name ("Bill" for "William") is not taken for it."""
    words = [w for w in re.split(r"[\s,]+", row_name or "") if w and TS.letters(w) not in TS.SUFFIXES]
    pm = people.pm.get(emp)
    if len(words) < 2 or not pm:
        return False
    mine = people.surnames(emp)
    if not (TS.letters(words[-1]) in mine
            or (len(words) > 2 and TS.letters(words[-2] + words[-1]) in mine)):
        return False
    given = (pm[2] or "").split()
    first = TS.letters(given[0]) if given else ""
    return len(first) >= 2 and len(TS.letters(words[0])) >= 2 and first == TS.letters(words[0])


def term_seat(emp, term, people, table):
    """(seat or None, why, row) for one number: the seat the term's list gives the person of its
    full name, as ("H", county, district) or ("S", "", district). None, and why, unless exactly one
    person in the term's list (either chamber, whatever the state of its row) has that full name and
    that row was read without doubt: a Senate row both pages agree on, a House row in a district
    whose marks equal its seats."""
    hits = [(ch, r) for ch, r in _manual_rows(table, term) if _table_name_fits(r.get("name"), emp, people)]
    if not hits:
        return None, "no person of that full name in the term's seat list", None
    if len(hits) > 1:
        return None, f"{len(hits)} people of that full name in the term's seat list", None
    ch, r = hits[0]
    if r.get("status") != "elected" or (ch == "H" and r.get("district_check") != "clean"):
        return None, f"the seat list's row for the name is not clean ({r.get('status')}; {r.get('district_check')})", r
    return (ch, TS.letters(r.get("county") or ""), str(r.get("district") or "")), "", r


def settle(sp, rows, people, term, table):
    """(state, employee or None, why) for a printed sponsor place() calls AMBIGUOUS.

    THE OWNER'S RULE (13 November 2026): "as accurate as possible and not guess if we aren't
    confident". A line goes to a candidate only on the TERM'S OWN official list of seats, and
    only if all of this holds, else it stays as printed and `why` says which did not:
      - the printed chamber and seat are complete (a county and district for the House, a
        district for the Senate);
      - each candidate's full name (the General Court's first name and surname, past_members.json)
        is joined to exactly one person in the term's seat list, read without doubt;
      - exactly one candidate's seat there is the printed seat, and every other candidate's seat
        is known and is not;
      - that candidate's own number is of the printed chamber (Franklin Torr's House number on
        a Senate line is reported, not settled).
    The seat list is the Manual for the General Court of the term, so it speaks for the start of
    the term only (build_manual_seats.py says so)."""
    cands, _k, _key = _fit(sp, rows, people)
    if len(cands) < 2:
        return place(sp, rows, people)
    stay = lambda why: (AMBIGUOUS, None, f"{len(cands)} numbers on the bill's record fit {' '.join(sp['words'])!r}; {why}")
    if not table or not _manual_rows(table, term):
        return stay("no seat list for the term is on this disk")
    ch, county, dist = sp.get("chamber") or "", TS.letters(sp.get("county") or ""), str(sp.get("district") or "")
    if ch not in ("H", "S") or not dist or (ch == "H" and not county) or (ch == "S" and county):
        return stay("the printed line gives no complete chamber and seat")
    printed = (ch, county, dist)
    seats = {e: term_seat(e, term, people, table) for e in cands}
    unknown = [e for e in cands if seats[e][0] is None]
    hits = [e for e in cands if seats[e][0] == printed]
    if len(hits) > 1:
        return stay("more than one candidate sits in the printed seat")
    if not hits:
        if unknown:
            return stay(f"the seat of {people.pm[unknown[0]][2]} {people.pm[unknown[0]][1]} is not known "
                        f"({seats[unknown[0]][1]})")
        return stay("no candidate's seat in the term's list is the printed seat")
    x = hits[0]
    others = [e for e in cands if e != x]
    for e in others:
        if seats[e][0] is None:
            return stay(f"the other candidate {people.pm[e][2]} {people.pm[e][1]}'s seat is not known ({seats[e][1]})")
    own = (people.pm.get(x) or ("", "", ""))[0]
    if own != ch:
        return stay(f"the number {x} is the General Court's {own or 'unknown'}-chamber number and the line is {ch}")
    edition = table["terms"][term]["edition"]
    line = lambda r: r.get("line") or r.get("returns_line")
    why = (f"{seats[x][2]['name']} is seated at {_seat_words(seats[x][0])} in the {edition} edition of the "
           f"Manual for the General Court (line {line(seats[x][2])}), the printed seat; "
           + "; ".join(f"{people.pm[e][2]} {people.pm[e][1]} is seated at {_seat_words(seats[e][0])} "
                       f"(line {line(seats[e][2])})" for e in others))
    return SETTLED, x, why


def _seat_words(seat):
    ch, county, dist = seat
    return f"Senate district {dist}" if ch == "S" else f"House {county.title()} {dist}"


def name_of(emp, people, sat=None):
    """(full name, linked id or "") for an employee number the General Court's list names.

    A number a later roll call was cast under (Sat.ids) takes the name the site gives that
    member and the id their page is under, so the chip on an old bill and the member's own
    page cannot disagree. Any other number takes the General Court's list's name and no id.
    ("", "") where nobody names the number."""
    vid = people.vid(emp)
    if sat is not None and vid in sat.names:
        last, first, suffix = sat.names[vid]
        return " ".join(x for x in (first, last, suffix) if x), vid
    pm = people.pm.get(emp)
    if pm:
        return full_name(f"{pm[1]}, {pm[2]}"), ""
    if emp in people.leg:
        last, first, _ch = people.leg[emp]
        return " ".join(x for x in (first, last) if x), ""
    return "", ""


def chamber_for(sp, emp, people):
    """The chamber to show for a printed sponsor placed on `emp`: the printed one, unless the
    seat is the other chamber's kind (a bare district is the Senate's, a county and district
    the House's) and the General Court's list agrees with the seat -- "Rep. Blaisdell, Dist 10"
    is Sen. Clesson Blaisdell, as Sat.senator already reads a "Rep." with a Senate district.
    The printed line is kept in as_printed either way."""
    pm = people.pm.get(emp)
    own = pm[0] if pm else (people.leg.get(emp) or ("", "", ""))[2]
    kind = {"district": "S", "county": "H"}.get(sp.get("seat") or "", "")
    if sp["chamber"] and own and sp["chamber"] != own and kind == own:
        return own
    return sp["chamber"]


def enrich(rec, emp, people, sat=None):
    """The sponsor record text_sponsors.record() made for a printed sponsor, given the person.

    The printed seat, chamber and as_printed stay as they were: they are what the bill
    printed. The name becomes the General Court's full name, `employee` is the General
    Court's number, `member_id` is set only where a member page can exist (a later roll
    call), and `matched` says how."""
    name, vid = name_of(emp, people, sat)
    if not name:
        return rec
    ch = rec["chamber"]
    hon = {"H": "Rep.", "S": "Sen."}.get(ch, "")
    tag = (f"SD{rec['district']}" if ch == "S" and rec["district"]
           else f"{TS.ABBR.get(rec['county'], '')} {rec['district']}".strip()
           if rec["county"] and rec["district"] else "")
    rec.update({"name": name, "member_id": vid, "employee": emp,
                "label": f"{hon} {name}".strip() + (f" ({tag})" if tag else ""),
                "matched": MATCHED})
    return rec


# ------------------------------------------------------------------ the whole decade

def survey(bills, joined, people, text, terms=PRE_TERMS, table=None):
    """({term: Counter}, [(term, bill, printed, state, why)]): every printed sponsor of the
    decade against its bill's own sponsor rows, and the second step (settle) for a line two
    numbers fit where `table` is the seat list. A settled line is listed with its evidence."""
    tally, rest = {t: Counter() for t in terms}, []
    for term in terms:
        for bid, recs in (text.get(term) or {}).items():
            rows = ((joined.get(term) or {}).get(bid) or {}).get("rows") or []
            for r in recs:
                if not rows:
                    tally[term]["no sponsor rows for the bill's LSR"] += 1
                    continue
                for sp in TS.split(r.get("as_printed") or ""):
                    state, emp, why = place(sp, rows, people)
                    if state == AMBIGUOUS and table:
                        state, emp, why = settle(sp, rows, people, term, table)
                    if state in (CERTAIN, SETTLED) and not people.names(emp):
                        state, why = UNMATCHED, f"employee {emp} is named by no list on disk"
                    tally[term][state] += 1
                    if state != CERTAIN:
                        rest.append((term, bid, sp["printed"], state, why if state != SETTLED
                                     else f"employee {emp} {people.names(emp)[0][1]} {people.names(emp)[0][0]}: {why}"))
    return tally, rest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="name every row not placed")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    joined, _ = PSP.join(bills, PSP.read_view("PastSponsors"), PSP.read_view("PastLegislation"))
    people = PSP.People(PSP.read_legislators(), past_members.roster(PSP.PAST_MEMBERS))
    text = json.loads(Path(TS.OUT).read_text(encoding="utf-8"))
    tally, rest = survey(bills, joined, people, text, table=seat_table())
    tot = Counter()
    print(f"{'term':<10}{'printed':>9}{'certain':>9}{'settled':>9}{'ambiguous':>10}{'unmatched':>10}{'no rows':>9}")
    for term in PRE_TERMS:
        c = tally[term]
        n = sum(c.values())
        print(f"{term:<10}{n:>9,}{c[CERTAIN]:>9,}{c[SETTLED]:>9,}{c[AMBIGUOUS]:>10,}{c[UNMATCHED]:>10,}"
              f"{c['no sponsor rows for the bill' + chr(39) + 's LSR']:>9,}")
        tot.update(c)
    n = sum(tot.values())
    print(f"{'all':<10}{n:>9,}{tot[CERTAIN]:>9,}{tot[SETTLED]:>9,}{tot[AMBIGUOUS]:>10,}{tot[UNMATCHED]:>10,}"
          f"{tot['no sponsor rows for the bill' + chr(39) + 's LSR']:>9,}")
    if a.list:
        for term, bid, printed, state, why in rest:
            print(f"{term} {bid}: {state}: {printed!r}: {why}")


if __name__ == "__main__":
    main()
