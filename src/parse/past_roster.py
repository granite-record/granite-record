#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.1
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

def place(sp, rows, people):
    """(state, employee or None, why) for one printed sponsor against one bill's rows.

    `rows` are the bill's PastSponsors rows ({"employee", ...}); `people` is a
    past_sponsors.People. The printed words are tried as past_sponsors and Sat.resolve try
    them: all of them as a surname, then all but the first (the first an initial or a first
    name), and so on, stopping at the first that fits anybody."""
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
        if not cands:
            continue
        if len(cands) == 1:
            return CERTAIN, cands[0], ("the only number of that surname on the bill's sponsor record"
                                       if not k else "the only number on the bill's record that "
                                       "fits the surname and the initial or first name printed")
        return AMBIGUOUS, None, f"{len(cands)} numbers on the bill's record fit {' '.join(words)!r}"
    return UNMATCHED, None, "no number on the bill's sponsor record fits the printed name"


def place_bill(pieces, rows, people):
    """[(state, employee, why)] for each printed sponsor of one bill."""
    return [place(sp, rows, people) for sp in pieces]


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

def survey(bills, joined, people, text, terms=PRE_TERMS):
    """({term: Counter}, [(term, bill, printed, state, why)]): every printed sponsor of the
    decade against its bill's own sponsor rows."""
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
                    if state == CERTAIN and not people.names(emp):
                        state, why = UNMATCHED, f"employee {emp} is named by no list on disk"
                    tally[term][state] += 1
                    if state != CERTAIN:
                        rest.append((term, bid, sp["printed"], state, why))
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
    tally, rest = survey(bills, joined, people, text)
    tot = Counter()
    print(f"{'term':<10}{'printed':>9}{'certain':>9}{'ambiguous':>10}{'unmatched':>10}{'no rows':>9}")
    for term in PRE_TERMS:
        c = tally[term]
        n = sum(c.values())
        print(f"{term:<10}{n:>9,}{c[CERTAIN]:>9,}{c[AMBIGUOUS]:>10,}{c[UNMATCHED]:>10,}"
              f"{c['no sponsor rows for the bill' + chr(39) + 's LSR']:>9,}")
        tot.update(c)
    n = sum(tot.values())
    print(f"{'all':<10}{n:>9,}{tot[CERTAIN]:>9,}{tot[AMBIGUOUS]:>10,}{tot[UNMATCHED]:>10,}"
          f"{tot['no sponsor rows for the bill' + chr(39) + 's LSR']:>9,}")
    if a.list:
        for term, bid, printed, state, why in rest:
            print(f"{term} {bid}: {state}: {printed!r}: {why}")


if __name__ == "__main__":
    main()
