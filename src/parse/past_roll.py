#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.1
"""
The House's CALL OF THE ROLL of 1989 to 1997, matched to the General Court's employee numbers only where certain.

    python3 src/parse/past_roll.py            # agreement with the sponsor route, newest term first; writes nothing

No network. Reads data/unh/roster/*.csv (unh_roster.py read the seven House volumes' call of the roll:
county, district, name as the OCR gave it), past_members.json, db/past/ and text_sponsors.json.

WHAT IT IS FOR. A second source for who sat, which does not depend on a member having sponsored a bill: a
House member who sponsored nothing has no row from the sponsor route, and the roll names every seat. It is
read as a SECOND SOURCE: the sponsor route (build_past_roster.py) is checked against it, and it adds the
people the sponsor route cannot see. It states no party (the roll prints the nominating party, and no party
is given before 1999 at this stage).

WHAT IS CERTAIN. A roll entry is placed on an employee number only where the surname is exactly a surname of
exactly one person who sponsored in that term (the sponsor route's own people, so there is evidence the
person sat then), their first name is the roll's (the same name or a short form of it, never a bare prefix),
and the roll's seat is not a seat that person's own bills printed some other district for. Everything else
stays as the roll gives it, with no number: an OCR spelling, a name two of the term's sponsors fit, a seat
that contradicts the printed one, a member who sponsored nothing. A name the General Court's whole list of
members fits just once is counted and reported but NOT used: that a member of that name is somewhere on a
list of two thousand people does not say they sat in this seat that term.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import csv
import json
import re
from collections import Counter, defaultdict

import member_links as ML
import past_members
import past_roster as PR
import past_sponsors as PSP
import text_sponsors as TS

ROLL = Path("data/unh/roster")
# Volume file -> (term, year of the volume). The three second-year volumes of 1994, 1996 and 1998
# have not been read: they are the next piece of work.
VOLUMES = {"journalofhouseof1997newh.csv": ("1997-1998", 1997),
           "journalofhouseof1995newh.csv": ("1995-1996", 1995),
           "vol1993journalofthehouseofrepresentativesofthestateofnewhampshireattheirsession.csv":
               ("1993-1994", 1993),
           "journalofhouseof1992newh.csv": ("1991-1992", 1992),
           "journalofhouseof1991newh.csv": ("1991-1992", 1991),
           "journalofhouseof8990newh.csv": ("1989-1990", 1990),
           "journalofhouseof1989newh.csv": ("1989-1990", 1989)}
JUNK = re.compile(r"(?i)\bvacan|\bseats?\)|quorum|\bresolved\b|^\W*$|^dist\b")
LEAD = re.compile(r"^(?:\d+\s+|Dist\.?,?\s*No\.?\s*[\d\s()]+)")
SFX = {"jr", "sr", "ii", "iii", "iv"}


def read(path):
    """[{county, district, name, seats, town, note, line}] of one volume's call of the roll: the
    rows that name a person, the OCR's name kept as it is."""
    out = []
    with open(path, encoding="utf-8", newline="") as fh:
        for n, r in enumerate(csv.DictReader(fh), 2):
            name = LEAD.sub("", (r.get("name") or "").strip()).strip()
            if not name or JUNK.search(name) or len(name) > 60:
                continue
            out.append({"county": (r.get("county") or "").title(), "district": (r.get("district") or "").strip(),
                        "name": name, "town": r.get("town") or "", "note": r.get("note") or "",
                        "source": r.get("source") or "", "line": n})
    return out


def split(name):
    """(surname keys, first name) of a roll name: "Howard C. Dickinson Jr" is Dickinson and Howard; the
    surname is the last word, and the last two where the first of them is a particle ("St. Hilaire")."""
    words = [w for w in re.split(r"\s+", name.replace(",", " ").strip()) if w]
    words = [w for w in words if TS.letters(w) not in SFX]
    if len(words) < 2:
        return set(), ""
    keys = {TS.letters(words[-1])}
    if len(words) >= 3:
        keys.add(TS.letters(words[-2] + words[-1]))
    return {k for k in keys if k}, words[0]


def same_name(a, b):
    """The same first name, or a short form of it (Bob and Robert); never a bare prefix."""
    xa, xb = ML.first_names(a), ML.first_names(b)
    return bool(xa & xb) or any(ML.SHORT.get(x) == y or ML.SHORT.get(y) == x for x in xa for y in xb)


def pool(rows, people, term):
    """{employee: (surname keys, first name, {(county, district)} the term's bills printed it at)} of the
    term's House sponsors, from the sponsor route's rows (build_past_roster.rows_of)."""
    out = {}
    for r in rows:
        if r["term"] != term or r["chamber"] not in ("H", "") or not r["name"]:
            continue
        e = r["person"]
        pm = people.pm.get(e)
        first = pm[2] if pm else r["name"].split()[0]
        out[e] = (people.surnames(e), first,
                  {(s["county"], s["district"]) for s in r["seats"]})
    return out


def place(entry, who, everyone):
    """(state, employee or None): 'placed' where one sponsor of the term fits the surname and first
    name and the seat does not contradict; 'seat differs' where the one that fits printed another
    district; 'ambiguous'; 'list only' where nobody of the term's does but one person on the whole
    list of members does (not used); 'none'."""
    keys, first = split(entry["name"])
    if not keys:
        return "none", None
    fit = [e for e, (sur, f, _s) in who.items() if keys & sur and same_name(first, f)]
    if len(fit) > 1:
        return "ambiguous", None
    if fit:
        seats = who[fit[0]][2]
        mine = (entry["county"], entry["district"].lstrip("0"))
        if seats and mine not in {(c, d.lstrip("0")) for c, d in seats}:
            return "seat differs", fit[0]
        return "placed", fit[0]
    whole = [e for e, (sur, f) in everyone.items() if keys & sur and same_name(first, f)]
    return ("list only", whole[0]) if len(whole) == 1 else ("none", None)


def match_volume(entries, who, everyone):
    """[(entry, state, employee)] for one volume."""
    return [(en, *place(en, who, everyone)) for en in entries]


def everyone_of(people):
    return {e: (people.surnames(e), pm[2]) for e, pm in people.pm.items()}


def survey(rows, people, root=ROLL):
    """{volume file: [(entry, state, employee)]}, newest term first."""
    who_all = everyone_of(people)
    out = {}
    for fn, (term, _y) in sorted(VOLUMES.items(), key=lambda kv: (kv[1][0], kv[1][1]), reverse=True):
        p = Path(root) / fn
        if not p.exists():
            continue
        out[fn] = match_volume(read(p), pool(rows, people, term), who_all)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import build_past_roster as BPR
    doc = json.loads(BPR.OUT.read_text(encoding="utf-8"))
    people = PSP.People(PSP.read_legislators(), past_members.roster(PSP.PAST_MEMBERS))
    got = survey(doc["rows"], people)
    print(f"{'volume':<14}{'term':<11}{'names':>6}{'placed':>8}{'seat differs':>13}{'ambiguous':>10}"
          f"{'list only':>10}{'none':>6}")
    for fn, res in got.items():
        term, y = VOLUMES[fn]
        c = Counter(s for _e, s, _n in res)
        print(f"{y:<14}{term:<11}{len(res):>6}{c['placed']:>8}{c['seat differs']:>13}{c['ambiguous']:>10}"
              f"{c['list only']:>10}{c['none']:>6}")


if __name__ == "__main__":
    main()
