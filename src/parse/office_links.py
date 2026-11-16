#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.1
"""
Who holds an office the legislature's record does not number: the rule that links a holder of
an office -- a governor, a councilor, a member of Congress, a county officer -- to a person of
the General Court's record, the evidence each link rests on, and the check that recomputes it.

    import office_links as OL
    OL.by_surname(pool)                       # the pool's people, each name read once
    OL.decide(holder, index, incompatible)    # {"verdict": "link" | "list" | "none", ...}
    OL.verify(tenure, holder, index, incompatible, owner)   # what is wrong with a link held
    OL.name_form(printed, person)             # the form of a name a confirmed holder adds
    OL.hand_key(office, area, year, printed)  # the owner's hand file's key for a holder

src/parse/build_entities.py builds the pool from the files on disk, runs the rule over every
holder the model of people and offices holds, and writes the links into the model, which
nothing reads yet. This module reads no file and asks no network: it decides.

THE RULE (the design study of 16 November 2026, "officials-links", and the owner's answers of
that afternoon). A holder links to a person without the owner's word only when all of these
hold:

  1. exactly one person of the whole pool answers to the name even loosely -- the record's
     people, the 1989-1998 members it gives no page, the members-elect it has not numbered --
     and that one answers by the same first name: a leading initial passed over (C. Jeanne is
     Jeanne), never a short form (Joe for Joseph) or the start of a name (Chris for
     Christopher);
  2. no Jr., Sr. or numeral on one side only, and none that differ;
  3. the middle initials do not differ. Where both print one it must be the same; a missing one
     blocks nothing; and an agreeing one is not counted below, because the owner's answer was
     that it is for checking ("add it for the purpose of checking but not display it
     publicly"): it can refuse a link and never makes one;
  4. one more agreement (AGREEMENTS): the holder's town of residence is the person's home
     town; or, where the town is not an agreement, the person's county or district lies inside
     the office's area; or the same single party (a holder two parties nominated, "R/D",
     counts for nothing);
  5. nothing differs -- town, area, party -- and no seat the person held in a term the office
     was held breaks the state's seat_incompatible setting (New Hampshire's is Pt. 2, Art. 95:
     a councilor, a member of Congress, a judge, the Secretary of State, the Treasurer, the
     Attorney General, a sheriff or a register of deeds has no seat in the House or Senate);
  6. the holder's name comes from an official file. The caller says which files are; a
     secondary source (NHPR's results, which the owner allows for cross-checking only and
     which are never republished) is never one, and nothing here reads it.

Everything else that answers to a name goes to the owner's list (LIST_KINDS), with the reason
and each person who answers: a short form, more than one person answering, a difference of
town, area or party, a lone or differing suffix, a seat the office forbids, too little
evidence -- and, apart, two middle initials that differ (most often two people, as the
Bartletts of Newport and Nottingham are; listed so that the hand file can say so). Her word,
in her hand file, is taken over the rule, as the members-elect hand file's is.

WHY THESE AND NOT A LOOSER RULE. The study tried the exact name with nobody else of it (it
links pairs the evidence shows are two people, among them Benjamin S. Bartlett, a Newport
selectman, to Rep. Benjamin T. Bartlett of Nottingham), and the members-elect rule for a
former member (exact name, county agrees: it takes NHPR's misprinted "Roger R. Berube" to a
sitting representative, against Art. 95). Tried on the record's own namesakes, the rule here
refuses all six pairs who sat together -- two people for certain -- the two Patrick Longs of
Manchester, both Democrats of Hillsborough County, among them: their middle initials differ.

THE RISK THAT REMAINS, plainly: two people of one name, one of whom never sat in the General
Court, of one party or county. No file on disk can rule that out; the owner's hand file and
the check below are the answer to it.

THE CHECK (verify). Every link the rule made carries its evidence in words, and is worked out
again: it fails when the linked person is no longer the only one who answers (a new
member-elect of the name), when any piece of evidence now reads otherwise, when a seat the
office forbids is on the record, when the owner's hand file says the holder is someone else or
no one, and when the holder's file is not an official one.

Nothing of the state is named here but in prose: its offices, its seat_incompatible rule and
its files are the caller's.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import re

from build_members_elect import first_equal, fold, readings, seat_first
from member_links import same_first

# How a person answers to a name, best first: the same first name; a short form the site's
# table lists or the start of a name (member_links.SHORT; build_members_elect.seat_first); three
# letters that begin the other (member_links.same_first). Only "exact" can link.
RANK = {"exact": 3, "short": 2, "loose": 1, "": 0}

# What counts as the one more agreement of rule 4. The middle initial is not one (rule 3).
AGREEMENTS = ("town", "area", "party")

# The owner's list, by kind (the task of 16 November 2026: "short forms, ambiguous,
# middle-initial conflicts").
LIST_KINDS = {
    "a short form only": "short form",
    "the middle initials differ": "middle initial",
}

PARTY_WORDS = {"r": "R", "rep": "R", "republican": "R", "d": "D", "dem": "D", "democratic": "D",
               "democrat": "D", "l": "L", "lib": "L", "libertarian": "L", "i": "I", "ind": "I",
               "independent": "I", "c": "C", "con": "C", "constitution": "C", "g": "G", "green": "G"}


# ---- names -----------------------------------------------------------------------------------

def given(first):
    """The given name a first-name part uses: "C. Jeanne" -> "Jeanne" (a leading initial is
    passed over: the name used is the second); "Joseph D." stays as it is."""
    s = fold(first or "").strip()
    words = s.split()
    if len(words) > 1 and re.fullmatch(r"[A-Za-z]\.?", words[0]):
        return " ".join(words[1:])
    return s


def middle_initials(first):
    """The initials of the words after the given name in a first-name part: "Joseph D." ->
    {"d"}, "Peter John" -> {"j"}, "C. Jeanne" -> set() (the leading initial is passed over),
    "Robert (Bob)" -> set()."""
    s = re.sub(r"\([^)]*\)", " ", fold(first or ""))
    words = re.findall(r"[A-Za-z][A-Za-z'.-]*", s)
    if words and re.fullmatch(r"[A-Za-z]\.?", words[0]) and len(words) > 1:
        words = words[1:]
    return {w[0].lower() for w in words[1:] if w[0].isalpha()}


def relation(f, pf):
    """How a first-name part `f` stands to a person's `pf`: "exact", "short", "loose" or ""."""
    if not f or not pf:
        return ""
    gf, gp = given(f), given(pf)
    if first_equal(f, pf) or first_equal(gf, gp) or first_equal(gf, pf) or first_equal(f, gp):
        return "exact"
    if seat_first(gf, gp) or seat_first(f, pf):
        return "short"
    if same_first(gf, gp) or same_first(f, pf):
        return "loose"
    return ""


def party_set(raw):
    """{"R"}, {"R", "D"} ... from "r", "r&d", "REP/DEM", "Republican", "R/D"."""
    out = set()
    for w in re.split(r"[&/,\s]+", str(raw or "").lower()):
        if w in PARTY_WORDS:
            out.add(PARTY_WORDS[w])
    return out


def town_key(t):
    """A town as two files can be compared on: accents off, lower case, a ward dropped, letters
    and single spaces ("Manchester Ward 5" and "manchester" are one)."""
    t = fold(t or "").lower().strip().replace("-", " ")
    t = re.sub(r"\s+ward\s+\w+$", "", t)
    t = re.sub(r"[^a-z ]", "", t)
    return " ".join(t.split())


def hand_key(office, area, year, printed):
    """The owner's hand file's key for a holder: the office, its area ("statewide", a district's
    number, a county, a commissioner's county and district), the first year of the term held,
    and the name exactly as the record prints it: "executive-council|5|2019|Debora B.
    Pignatelli"."""
    return "|".join((str(office), str(area), str(year), " ".join(str(printed or "").split())))


# ---- the pool ---------------------------------------------------------------------------------

def readings_of(p):
    """Every (surname, first name) a person's names read as, worked out once."""
    if "rd" not in p:
        p["rd"] = {r for n in p.get("names") or [] for r in readings(n)[0]}
    return p["rd"]


def by_surname(pool):
    """{surname: [person]} for the pool's people."""
    out = {}
    for p in pool:
        for s in {s for s, _f in readings_of(p)}:
            out.setdefault(s, []).append(p)
    return out


def answering(printed, index):
    """{key: (relation, person, [the holder's readings that matched])}: everyone of the pool who
    answers to `printed` even loosely, each by the best relation any reading gives."""
    out = {}
    for s, f in readings(printed)[0]:
        for p in index.get(s, ()):
            best = ""
            for ps, pf in readings_of(p):
                if ps == s:
                    r = relation(f, pf)
                    if RANK[r] > RANK[best]:
                        best = r
            if not best:
                continue
            had = out.get(p["key"])
            if had is None or RANK[best] > RANK[had[0]]:
                out[p["key"]] = (best, p, [(s, f)])
            elif RANK[best] == RANK[had[0]]:
                had[2].append((s, f))
    return out


# ---- the evidence -------------------------------------------------------------------------------

def _letters(xs):
    return "/".join(sorted(x.upper() for x in xs)) or "none"


def evidence(holder, p, matched, incompatible=()):
    """{item: (state, words)} for `holder` against person `p`, `matched` the holder's readings
    that answered to them. Each state is "agree", "differ", "unknown" or one of its own
    ("one-side", "cross", "clash", "ok", "none"); the words say what each side gives, and are
    what a link keeps and the check works out again."""
    ev = {}
    hm = {m for _s, f in matched for m in middle_initials(f)}
    pm = set(p.get("middles") or ())
    if hm and pm:
        ev["middle"] = ("agree" if hm & pm else "differ", f"{_letters(hm)} = {_letters(pm)}"
                        if hm & pm else f"{_letters(hm)} against {_letters(pm)}")
    elif hm or pm:
        ev["middle"] = ("unknown", f"{_letters(hm or pm)} on one side only")
    else:
        ev["middle"] = ("unknown", "none printed")
    hs = set(readings(holder["printed"])[1])
    ps = set(p.get("sfx") or ())
    if hs and ps:
        ev["suffix"] = ("agree" if hs & ps else "differ", f"{_letters(hs)} = {_letters(ps)}"
                        if hs & ps else f"{_letters(hs)} against {_letters(ps)}")
    elif hs or ps:
        ev["suffix"] = ("one-side", f"{_letters(hs or ps)} on one side only")
    else:
        ev["suffix"] = ("unknown", "none")
    town = town_key(holder.get("town"))
    homes = {town_key(t): t for t in sorted(p.get("homes") or ())}
    if town and homes:
        ev["town"] = ("agree", f"{holder['town']} = {homes[town]}") if town in homes else (
            "differ", f"{holder['town']} against {', '.join(sorted(homes.values()))}")
    else:
        ev["town"] = ("unknown", f"{holder['town']}; no home town on file" if town else "none printed")
    ev["area"] = _area(holder.get("area") or {}, p)
    hp = party_set(holder.get("party"))
    pp = set(p.get("parties") or ())
    if hp and pp:
        if not hp & pp:
            ev["party"] = ("differ", f"{_letters(hp)} against {_letters(pp)}")
        elif len(hp) == 1:
            ev["party"] = ("agree", f"{_letters(hp)} = {_letters(pp)}" if pp == hp else
                           f"{_letters(hp)} among {_letters(pp)}")
        else:
            ev["party"] = ("cross", f"{_letters(hp)}: nominated by two parties, which says nothing")
    else:
        ev["party"] = ("unknown", "none printed" if not hp else f"{_letters(hp)}; none on file")
    if holder["office"] in incompatible:
        clash = sorted(set(holder.get("terms") or ()) & set(p.get("terms") or ()))
        ev["incompatible"] = ("clash", "a seat in " + ", ".join(clash)) if clash else (
            "ok", "no seat in " + (", ".join(sorted(holder.get("terms") or ())) or "the term held"))
    else:
        ev["incompatible"] = ("none", "not an office the rule names")
    return ev


def _area(area, p):
    kind = area.get("kind")
    if kind == "county":
        mine = set(p.get("counties") or ())
        if not mine:
            return ("unknown", f"{area['county']}; no county on file")
        return ("agree", f"{area['county']} = {area['county']}") if area["county"] in mine else (
            "differ", f"{area['county']} against {', '.join(sorted(mine))}")
    if kind == "district":
        # The office's towns ({town key: name}) against the person's home towns, or where none is
        # on file the towns of a district they hold or were elected to.
        towns = area.get("towns") or {}
        homes = {town_key(t): t for t in p.get("homes") or ()}
        mine = homes or {town_key(t): t for t in p.get("district_towns") or ()}
        if mine and towns:
            got = sorted(towns[t] for t in set(mine) & set(towns))
            return ("agree", f"{', '.join(got)} in {area['id']}") if got else (
                "differ", f"{', '.join(sorted(mine.values()))} not in {area['id']}")
        counties = set(p.get("counties") or ())
        theirs = {area.get("town_county", {}).get(t) for t in towns} - {None}
        if counties and theirs:
            got = sorted(counties & theirs)
            return ("agree", f"{', '.join(got)} County in {area['id']}") if got else (
                "differ", f"{', '.join(sorted(counties))} County not in {area['id']}")
        return ("unknown", f"{area['id']}; no town or county on file")
    if kind == "statewide":
        return ("statewide", "statewide")
    return ("unknown", area.get("why") or "no map of the office's area on file")


def _agreements(ev):
    """The agreements rule 4 counts, each fact once: the town of residence and the area are one
    fact where the town agrees (a selectman of a town living in it says nothing more by living
    in its county), so the area counts only where the town is not an agreement."""
    got = []
    if ev["town"][0] == "agree":
        got.append("town")
    if ev["area"][0] == "agree" and ev["town"][0] != "agree":
        got.append("area")
    if ev["party"][0] == "agree":
        got.append("party")
    return [g for g in got if g in AGREEMENTS]


def _hard(ev):
    return ev["middle"][0] == "differ" or ev["suffix"][0] == "differ" or ev["incompatible"][0] == "clash"


def _words(ev):
    return {k: w for k, (_s, w) in ev.items()}


def _candidate(key, rel, p, ev):
    return {"person": p.get("person"), "key": key, "who": p.get("label") or (p.get("names") or [""])[0],
            "kind": p.get("kind"), "answers": rel,
            "evidence": {k: f"{s}: {w}" for k, (s, w) in ev.items()}}


# ---- the rule -----------------------------------------------------------------------------------

def decide(holder, index, incompatible=()):
    """The rule on one holder ({"printed", "office", "party", "town", "area", "terms"}) against
    the pool's `index` (by_surname): {"verdict": "link", "person", "evidence": {item: words}};
    {"verdict": "list", "why", "kind", "candidates": [...]}; or {"verdict": "none"} where nobody
    answers. `incompatible` is the offices the seat_incompatible setting names."""
    ans = answering(holder["printed"], index)
    if not ans:
        return {"verdict": "none"}
    evs = {k: evidence(holder, p, matched, incompatible) for k, (_r, p, matched) in ans.items()}
    cands = [_candidate(k, r, p, evs[k]) for k, (r, p, _m) in sorted(ans.items())]

    def listed(why):
        return {"verdict": "list", "why": why, "kind": LIST_KINDS.get(why.split(" (")[0], "ambiguous"),
                "candidates": cands}
    if len(ans) > 1:
        return listed(f"{len(ans)} people answer to the name")
    k, (rel, p, _m) = next(iter(ans.items()))
    ev = evs[k]
    if rel != "exact":
        return listed("a short form only")
    if p.get("person") is None:
        # A member-elect the General Court has not numbered has no id to be linked to.
        return listed("the one who answers is a member-elect with no number yet")
    if ev["middle"][0] == "differ":
        return listed("the middle initials differ")
    if ev["suffix"][0] == "differ":
        return listed("the suffixes differ")
    if ev["suffix"][0] == "one-side":
        # A Jr. or Sr. printed on one side announces a namesake of that name, a father or a son.
        return listed("a Jr. or Sr. on one side only")
    if ev["incompatible"][0] == "clash":
        return listed(f"a seat the office forbids ({ev['incompatible'][1]})")
    diff = [x for x in ("town", "area", "party") if ev[x][0] == "differ"]
    if diff:
        return listed(f"a difference ({', '.join(diff)})")
    if not _agreements(ev):
        return listed("too little evidence")
    words = _words(ev)
    words["name"] = f"{holder['printed']}: {p.get('label') or p['names'][0]} answers by the same first name, and nobody else"
    return {"verdict": "link", "person": p.get("person"), "key": k, "evidence": words,
            "agreements": _agreements(ev)}


def name_form(printed, p):
    """{"name", "given", "of"} where `printed` answers to person `p` by a short form or the
    start of a name and not by their own first name (Joe Pitre for Joseph Pitre): the form of the
    name a holder the owner confirmed is them adds to their names; None where the printed first
    name is one of theirs already."""
    best = None
    for s, f in readings(printed)[0]:
        for ps, pf in readings_of(p):
            if ps != s:
                continue
            r = relation(f, pf)
            if r == "exact":
                return None
            if r in ("short", "loose") and best is None:
                best = {"name": " ".join(str(printed).split()), "given": given(f).split()[0] if given(f) else f,
                        "of": given(pf).split()[0] if given(pf) else pf}
    return best


# ---- the check ------------------------------------------------------------------------------------

def verify(tenure, holder, index, incompatible=(), owner=None, official=()):
    """[sentences]: what is wrong with the link `tenure` holds for `holder`, worked out again on
    the pool's `index` now; [] where it holds. `owner` is the owner's hand file's entries
    ({key: entry}), and `official` the files a holder may come from."""
    link = tenure.get("link") or {}
    out = []
    where = f"tenure {tenure.get('tenure')} ({holder['printed']})"
    entry = (owner or {}).get(holder.get("key"))
    files = list(tenure.get("files") or [])
    if link.get("by") == "owner":
        if entry is None:
            out.append(f"{where} is linked by the owner's entry {link.get('key')}, which her hand file no longer has")
        elif str(entry.get("person")) != str(tenure.get("person")):
            out.append(f"{where} is linked to {tenure.get('person')}, and her entry names {entry.get('person')}")
        return out
    if link.get("by") != "rule":
        return out
    if not files or not all(f in official for f in files):
        out.append(f"{where} comes from {files}, and a link by the rule needs an official file alone")
    if any("nhpr" in str(f).lower() for f in files):
        out.append(f"{where} comes from NHPR's results, which are for cross-checking and never a link")
    if entry is not None:
        if entry.get("person") is None:
            out.append(f"{where} is linked to {tenure.get('person')}, and the owner's hand file says "
                       f"{holder['key']} is no one of the record ({entry.get('why') or 'two people'})")
        elif str(entry.get("person")) != str(tenure.get("person")):
            out.append(f"{where} is linked by the rule to {tenure.get('person')}, and the owner's entry "
                       f"names {entry.get('person')}")
    if entry is not None and str(tenure.get("person")) in {str(x) for x in entry.get("not") or ()}:
        out.append(f"{where} is linked to {tenure.get('person')}, whom the owner's hand file says it is not")
    ans = answering(holder["printed"], index)
    if len(ans) != 1:
        out.append(f"{where}: {len(ans)} people answer to the name now ("
                   + ", ".join(f"{p.get('label') or p['names'][0]} ({r})" for _k, (r, p, _m) in sorted(ans.items()))
                   + "), and a link needs exactly one")
        return out
    k, (rel, p, matched) = next(iter(ans.items()))
    if str(p.get("person")) != str(tenure.get("person")):
        out.append(f"{where}: the one who answers now is {p.get('person')}, not {tenure.get('person')}")
        return out
    if rel != "exact":
        out.append(f"{where}: {p.get('label')} answers now by a {rel} form only")
    ev = evidence(holder, p, matched, incompatible)
    for item, (state, words) in ev.items():
        if state in ("differ", "clash", "one-side"):
            out.append(f"{where}: the {item} {'breaks the seat rule' if state == 'clash' else 'differs'} now: {words}")
    if not _agreements(ev):
        out.append(f"{where}: no agreement beyond the name now ({_words(ev)})")
    kept = {k2: v for k2, v in link.items() if k2 in ev}
    now = _words(ev)
    for item in sorted(set(kept) | set(now)):
        if kept.get(item) != now.get(item):
            out.append(f"{where}: the {item} was {kept.get(item)!r} and is {now.get(item)!r} now")
    return out
