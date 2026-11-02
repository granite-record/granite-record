#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.6
"""
One entry a person, joining every number the General Court uses for them.

    import people as PE
    PE.build(site, data, db, careers, register)  ->  (people, report)

The public data API's people file (docs/design/api/DESIGN.md, 2.5) and the
register of person numbers (person_numbers.py) both come from here, so the
night and the run that issues numbers cannot join two people differently.
Nothing here writes a file or asks the network.

WHY A PERSON IS NOT ANY OF THE GENERAL COURT'S NUMBERS

The General Court numbers a member twice, an Employeeno (six digits, the roll
calls') and a PersonID (the roster's), and mints new ones of both when a member
moves between the House and the Senate. This site's member_id is the PersonID
where there is one and the Employeeno where there is not (build_data.py). So
Cindy Rosenwald votes as 515 in the House and 9406 in the Senate, and every
file keyed by one of those numbers breaks her in two. A person number joins
them, and is issued once (generated/person_numbers.json) and never reissued
to anybody else.

WHICH NUMBER IS A PERSON'S (the owner, 30 October 2026: "consistent with the
General Court's where possible", since the General Court issues numbers). One
of the General Court's own, by a fixed rule:

  1. their earliest PersonID -- the one under which they first cast a
     recorded vote: the PersonID of their employee number with the
     earliest term, and of two that first voted in the same term, the
     lower employee number's; else
  2. their earliest employee number, by the same order; else
  3. "s" and the site id, made here, for a person the General Court numbers
     nowhere this site can read (nobody, on 30 October 2026).

Earliest rather than latest, because a member's latest number changes every
time they move between the chambers and their earliest never does. The two
kinds cannot be taken for each other: PersonIDs run 27 to 11,524 and employee
numbers are six digits (201723 to 999999), and the register refuses a number
held by two people. Measured on 30 October 2026: 1,056 people by a PersonID,
1,131 by an employee number, none made here. The 1,131 are everyone the
General Court's roster view (Legislators.psv) does not name -- nearly all
whose service ended before 2015, and 44 who served later -- and some of them
have a PersonID the General Court holds that nothing here links to their
employee number (Joyce Fulweiler, 800061, is PersonID 1444 in
former_members.json, which has no employee numbers). So an employee number
is a person's number only for want of a link, and person_numbers.py --issue
says so before it freezes one.

WHICH NUMBERS ARE ONE PERSON: TWO JOINS, AND ONE RULE OVER BOTH

  careers.json   joins Employeenos on the same first and last name where the
                 service never overlaps (build_careers.py). It reaches anyone
                 the roster names, which is nobody whose service ended before
                 2015.
  member_ids     each member's own file (site/legislators/<id>.json) lists the
                 earlier numbers member_links.py joined to them, by six rules
                 and with the names of byAnyMember.aspx, so it reaches back
                 before 2015 -- but only for a member who sits now.

They are unioned, under member_links's first rule: TWO NUMBERS IN ONE CHAMBER
ARE TWO PEOPLE, because a member who returns to a chamber gets their old
number back. careers.json breaks that rule twice. It attaches Sen. Pat Long's
House record (376696, 2007-2024) to a freshman representative, Patrick Long of
Hillsborough 26 (409256, from 2025) -- member_links.py says whose it is, as the
person settled on 17 September 2026 -- and it joins two House numbers for Mark
Pearson, Rockingham 4 in 2007-2008 and Rockingham 34 from 2017. A careers
group holding two numbers of one chamber is not joined at all, and the report
names it, so that a person decides.

THE REGISTER WINS. Once a number is issued it is what the night publishes,
whatever tonight's join says: a join that now disagrees (two issued people
it would merge, or one it would split) is reported and left alone, because
moving a published number is the thing the register exists to prevent.

A NEW MEMBER NEEDS NOBODY (the owner's condition, 30 October 2026). Numbers
the register does not hold yet are grouped by the join, and a group with no
issued number is published the same night with the number the rule gives
it: a new member with a PersonID gets their PersonID; one with only an
employee number gets that; neither is marked provisional, because the rule
leaves no choice to make. Only someone the General Court numbers nowhere this
site can read gets a number made here, "s" and their site id, marked
"provisional" -- and the night a General Court number appears for them, the
rule gives them that instead. The next issue of the register freezes the
night's numbers; person_numbers.py --issue never freezes a provisional one.

NEVER TWO PEOPLE UNDER ONE NUMBER. A group whose rule number is already
someone's -- issued, or given to another group tonight -- is held back and
reported (report["clashes"]), never published under a number another person
holds; build_exports says so, and check_unique() is the proof that what is
published holds no number twice.
"""

import csv
import json
from pathlib import Path

FORMAT = 1


def _load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def emp_to_pid(db):
    """Employeeno -> PersonID, from the roster view the database dump holds."""
    db = Path(db)
    cols = _load(db / "_columns.json", {}).get("Legislators")
    cols = cols if isinstance(cols, list) else (cols or {}).get("columns") or []
    if "Employeeno" not in cols or not (db / "Legislators.psv").exists():
        return None
    iE, iP = cols.index("Employeeno"), cols.index("PersonID")
    out = {}
    with (db / "Legislators.psv").open(encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("|")
            if len(f) > max(iE, iP) and f[iE].strip() and f[iP].strip():
                out[f[iE].strip()] = f[iP].strip()
    return out


class _Union:
    def __init__(self):
        self.up = {}

    def find(self, x):
        self.up.setdefault(x, x)
        while self.up[x] != x:
            self.up[x] = self.up[self.up[x]]
            x = self.up[x]
        return x

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.up[max(ra, rb)] = min(ra, rb)


def _term_key(e, careers_by_emp):
    """When a number first voted: its earliest term, then the number itself."""
    terms = careers_by_emp.get(e, {}).get("terms") or ["9999"]
    return (min(terms), int(e) if e.isdigit() else 0, e)


def choose(nums, by_emp, e2p):
    """The person number the rule gives a group of numbers (the docstring
    above): its earliest PersonID, else its earliest employee number, else
    one made here."""
    emps = sorted((n for n in nums if not n.startswith("m")), key=lambda e: _term_key(e, by_emp))
    pids = [e2p[e] for e in emps if e in e2p]
    if pids:
        return pids[0]
    if emps:
        return emps[0]
    return "s" + sorted(nums)[0].lstrip("m")


def person_key(p):
    """Person numbers in number order: 27 before 515 before 376312."""
    p = str(p)
    return (0, int(p), p) if p.isdigit() else (1, 0, p)


def load_links(path):
    """generated/person_links.json's links, {employee number: PersonID}: the
    pairs no General Court view this site reads makes, each settled by a
    person with its evidence and written by hand (preflight holds that no code
    writes it). None where there is no file; a stop where one does not read or
    a link is not whole, because a link dropped in silence would renumber its
    person."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"{path} does not read as JSON ({e}).")
    out = {}
    for x in d.get("links") or []:
        e, p = str(x.get("employee_number") or ""), str(x.get("person_id") or "")
        if not (len(e) == 6 and e.isdigit() and p.isdigit() and len(p) < 6 and x.get("evidence")):
            raise SystemExit(f"{path}: a link without an employee number, a PersonID and its "
                             f"evidence: {x}")
        if e in out:
            raise SystemExit(f"{path}: {e} is linked twice.")
        out[e] = p
    return out


def build(site, data, db, careers, register, links=None):
    """(people, report). people is the list people.json publishes; report is
    what a person should know: the joins left undone and why, the register's
    disagreements with tonight, and the provisional numbers."""
    site, data = Path(site), Path(data)
    e2p = emp_to_pid(db) or {}
    # A HAND LINK (load_links) is read as the roster would be. It stops where
    # it contradicts the roster's own pairing of that employee number, or
    # where the roster gives the PersonID to another employee number that
    # has votes of its own: that would join two voting numbers, which is a
    # person's merge, not a link. A roster number with no votes (Joyce
    # Fulweiler's 800404, under the 1444 she voted as 800061) joins nobody.
    voters = {e for c in (careers or {}).values() for e in c.get("employee_nos") or []}
    for e, p in (links or {}).items():
        others = [x for x, q in e2p.items() if q == p and x != e]
        if e2p.get(e, p) != p or any(x in voters for x in others):
            raise SystemExit(f"person_links.json links {e} to {p}, and the General Court's "
                             f"roster pairs them otherwise ({e2p.get(e)}, {others}); a "
                             "person must look.")
        e2p[e] = p
    p2e = {}
    for e, p in e2p.items():
        p2e.setdefault(p, e)

    # What each Employeeno is, from careers.json: its terms and chambers.
    by_emp = {}
    for key, c in (careers or {}).items():
        for term, v in (c.get("by_term") or {}).items():
            for e in v.get("employee_nos") or []:
                b = by_emp.setdefault(e, {"terms": set(), "chambers": set(), "first": c.get("first") or "",
                                          "last": c.get("last") or ""})
                b["terms"].add(term)
                b["chambers"].update(v.get("chambers") or [])

    # Every id the site's files use for a member, and the rows that carry a page.
    rows = {}
    for f in ("legislators.json", "former.json"):
        for m in _load(site / f, []):
            rows.setdefault(str(m.get("id")), dict(m, _sitting=(f == "legislators.json")))
    used = set(rows)
    for v in _load(data / "member_votes.json", []):
        if v.get("member_id"):
            used.add(str(v["member_id"]))
    sp = _load(data / "sponsors.json", {})
    for bills in (sp.values() if isinstance(sp, dict) else []):
        for people_ in (bills.values() if isinstance(bills, dict) else []):
            for m in (people_ if isinstance(people_, list) else []):
                if m.get("member_id"):
                    used.add(str(m["member_id"]))

    def emp_of(mid):
        """The Employeeno an id stands for: itself when it is one, its
        Employeeno when it is a PersonID, and None when neither is known."""
        if mid in by_emp or mid in e2p:
            return mid
        return p2e.get(mid)

    U = _Union()
    report = {"careers_not_joined": [], "unknown_ids": [], "register_disagrees": [],
              "provisional": [], "by_rule": [], "clashes": [], "unissued_numbers": []}
    # Every Employeeno is a node, and so is any id that stands for none.
    for e in by_emp:
        U.find("e" + e)
    for mid in sorted(used):
        e = emp_of(mid)
        if e is None:
            report["unknown_ids"].append(mid)
            U.find("m" + mid)
        else:
            U.find("e" + e)

    # careers.json's join, under the one-chamber rule.
    for key, c in sorted((careers or {}).items()):
        emps = list(dict.fromkeys(c.get("employee_nos") or []))
        if len(emps) < 2:
            continue
        ch = [frozenset(by_emp.get(e, {}).get("chambers") or ()) for e in emps]
        clash = any(len(x) != 1 for x in ch) or len(set(ch)) != len(ch)
        if clash:
            report["careers_not_joined"].append({
                "numbers": emps, "name": f'{c.get("first", "")} {c.get("last", "")}'.strip(),
                "why": "two of its numbers voted in one chamber, which is two people "
                       "(member_links.py, rule 1)"})
            continue
        for e in emps[1:]:
            U.join("e" + emps[0], "e" + e)

    # member_links.py's joins, as each member's own file carries them.
    for f in sorted((site / "legislators").glob("*.json")):
        ids = [str(i) for i in (_load(f, {}).get("member_ids") or [])]
        nodes = [("e" + emp_of(i)) if emp_of(i) else ("m" + i) for i in ids]
        for n in nodes[1:]:
            U.join(nodes[0], n)

    groups = {}
    for node in list(U.up):
        groups.setdefault(U.find(node), []).append(node)
    # THE ONE-CHAMBER RULE OVER BOTH JOINS, not only careers.json's: a group
    # the two joins built between them with two numbers of one chamber is two
    # people put together. It is reported, published as tonight's join made
    # it, and never issued until a person has looked (person_numbers.py).
    report["one_chamber"] = []
    for root, nodes in sorted(groups.items()):
        emps = [n[1:] for n in nodes if n[0] == "e"]
        seen = {}
        for e in emps:
            for ch in by_emp.get(e, {}).get("chambers") or ():
                seen.setdefault(ch, []).append(e)
        twice = {ch: sorted(es) for ch, es in seen.items() if len(es) > 1}
        if twice:
            report["one_chamber"].append({"numbers": sorted(emps), "same_chamber": twice})

    # The register: every issued number, and which person holds it.
    reg = register or {"format": FORMAT, "people": []}
    issued = {}
    issued_to = set()
    for entry in reg.get("people") or []:
        issued_to.add(entry["person"])
        for n in entry.get("numbers") or []:
            issued[n] = entry["person"]

    def label(node):
        return node[1:] if node[0] == "e" else "m" + node[1:]

    people = {}
    for root, nodes in sorted(groups.items()):
        nums = sorted({label(n) for n in nodes})
        held = sorted({issued[n] for n in nums if n in issued})
        if len(held) > 1:
            report["register_disagrees"].append({
                "numbers": nums, "issued_to": held,
                "why": "tonight's join puts numbers of two issued people together; "
                       "they stay apart until a person merges them"})
        if held:
            for n in nums:
                person = issued.get(n) or (held[0] if len(held) == 1 else None)
                if person is None:
                    # Between two issued people and issued to neither: not
                    # published tonight, and said, until a person places it.
                    report["unissued_numbers"].append({"number": n, "person": None})
                    continue
                if n not in issued:
                    report["unissued_numbers"].append({"number": n, "person": person})
                people.setdefault(person, {"numbers": set(), "provisional": False})["numbers"].add(n)
        else:
            # NOT IN THE REGISTER YET: a new member, or the night before the
            # first issue. The rule leaves no choice, so the night gives them
            # their number itself (the owner's condition, 30 October 2026):
            # the General Court's own, published as theirs, and frozen the
            # next time the register is issued. Provisional only when the
            # General Court numbers them nowhere this site can read, and then
            # only until it does.
            person = choose(nums, by_emp, e2p)
            site_made = person.startswith("s")
            if person in issued_to or person in people:
                # NEVER TWO PEOPLE UNDER ONE NUMBER. A General Court number is
                # one person's, so this is a fault in the record or the join;
                # the group is held back and said, not published.
                report["clashes"].append({"person": person, "numbers": nums})
                continue
            people[person] = {"numbers": set(nums), "provisional": site_made}
            report["provisional" if site_made else "by_rule"].append({"person": person, "numbers": nums})
    # A register person tonight's join split across groups is still one person
    # (the loop above gathers its numbers wherever they fell); say so.
    seen_in = {}
    for root, nodes in groups.items():
        for n in {label(x) for x in nodes}:
            if n in issued:
                seen_in.setdefault(issued[n], set()).add(root)
    for person, roots in sorted(seen_in.items()):
        if len(roots) > 1:
            report["register_disagrees"].append({
                "person": person,
                "why": "tonight's join splits this issued person; they stay one "
                       "until a person splits them"})

    # AN ISSUED PERSON IS NEVER DROPPED. Every person the register holds (and
    # has not retired) must be published tonight; one that is not -- every
    # number of theirs gone from tonight's record, or an entry with none --
    # is reported, and build_exports stops on it rather than let a published
    # number vanish or come back as someone else's.
    report["missing_issued"] = sorted(
        (e["person"] for e in reg.get("people") or []
         if not e.get("replaced_by") and e["person"] not in people), key=person_key)

    # Each person's published entry.
    out = []
    for person, p in sorted(people.items(), key=lambda kv: person_key(kv[0])):
        nums = p["numbers"]
        emps = sorted((n for n in nums if not n.startswith("m")), key=lambda e: _term_key(e, by_emp))
        pids = list(dict.fromkeys(e2p[e] for e in emps if e in e2p))
        cand = list(dict.fromkeys(pids + emps + [n[1:] for n in nums if n.startswith("m")]))
        mids = [i for i in cand if i in used]
        own = [rows[i] for i in mids if i in rows]
        sitting = [r for r in own if r["_sitting"]]
        best = (sitting or own or [None])[0]
        terms = sorted({t for e in emps for t in by_emp.get(e, {}).get("terms", ())})
        name = None
        if best and best.get("name"):
            last, _, first = str(best["name"]).partition(", ")
            name = f"{first} {last}".strip() if first else last
        elif emps and (by_emp.get(emps[0], {}).get("first") or by_emp.get(emps[0], {}).get("last")):
            b = by_emp[emps[0]]
            name = f'{b["first"]} {b["last"]}'.strip()
        entry = {
            "person": person,
            "name": name,
            "employee_numbers": emps,
            "person_ids": pids,
            "member_ids": mids,
            "page": f'/legislator/{best["slug"]}' if best and best.get("slug") else None,
            "sitting": bool(sitting),
            "chambers": sorted({c for e in emps for c in by_emp.get(e, {}).get("chambers", ())}),
            "first_term": terms[0] if terms else None,
            "last_term": terms[-1] if terms else None,
        }
        if p["provisional"]:
            entry["provisional"] = True
        out.append(entry)
    # A person the register retired, or split from another, keeps an entry.
    for e in reg.get("people") or []:
        if e.get("replaced_by"):
            out.append({"person": e["person"], "replaced_by": e["replaced_by"]})
    for entry in out:
        r = next((x for x in reg.get("people") or [] if x["person"] == entry["person"]), None)
        if r and r.get("split_from"):
            entry["split_from"] = r["split_from"]
    out.sort(key=lambda x: person_key(x["person"]))
    return out, report


def check_register(reg):
    """Problems with a register's own shape, as sentences; empty is well
    formed. A person issued twice; a number held by two people; a person
    number that is someone else's number; an entry with no numbers that is
    not retired; a number made here (an "s" person), which is never issued;
    an employee-number person whose number is not among its own."""
    if not isinstance(reg, dict) or not isinstance(reg.get("people"), list):
        return ["the register is not an object with a list of people"]
    bad, seen_p, seen_n = [], set(), {}
    for e in reg["people"]:
        if not isinstance(e, dict):
            bad.append(f"an entry that is not an object: {e!r}")
            continue
        p = str(e.get("person") or "")
        nums = [str(n) for n in e.get("numbers") or []]
        if not p.isdigit():
            bad.append(f"{p or 'an entry'}: a person number that is not one of the General Court's"
                       + (" (one made here is never issued)" if p.startswith("s") else ""))
            continue
        if p in seen_p:
            bad.append(f"{p} is issued twice")
        seen_p.add(p)
        if e.get("replaced_by"):
            if nums:
                bad.append(f"{p} is replaced and still holds numbers")
            continue
        if not nums:
            bad.append(f"{p} holds no numbers")
        if len(p) == 6 and p not in nums:
            bad.append(f"{p} is an employee number it does not hold")
        for n in nums:
            if n in seen_n:
                bad.append(f"{n} is held by {seen_n[n]} and {p}")
            seen_n[n] = p
    for p in seen_p:
        if p in seen_n and seen_n[p] != p:
            bad.append(f"{p} is a person number and also {seen_n[p]}'s number")
    return bad


def load_register(path):
    """The register at path: None where there is none; the register where it
    reads and is well formed; and otherwise a stop, because a register that
    cannot be read would quietly stop the register winning."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        reg = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"{path} does not read as JSON ({e}); the build stops rather "
                         "than number people without it.")
    bad = check_register(reg)
    if bad:
        raise SystemExit(f"{path} is not well formed, and the build stops rather than "
                         "number people without it:\n  " + "\n  ".join(bad[:10]))
    return reg


def check_unique(people):
    """Problems with a set of published people: a person number twice, or a
    General Court or site number held by two people. Empty is right."""
    bad, seen_p, seen_n = [], set(), {}
    for p in people:
        if p["person"] in seen_p:
            bad.append(f"person {p['person']} is published twice")
        seen_p.add(p["person"])
        if p.get("replaced_by"):
            continue
        for field in ("employee_numbers", "person_ids", "member_ids"):
            for n in p.get(field) or []:
                k = (field, n)
                if k in seen_n and seen_n[k] != p["person"]:
                    bad.append(f"{field[:-1]} {n} is held by {seen_n[k]} and {p['person']}")
                seen_n[k] = p["person"]
    return bad


def write(people, out_dir):
    """people.json and people.csv into out_dir; returns their manifest rows."""
    out_dir = Path(out_dir)
    doc = {"format": FORMAT,
           "what": "One entry for each person with a recorded vote since 1999, and "
                   "every number the General Court and this site use for them. "
                   "person is one of the General Court's own numbers for them, "
                   "chosen once by a fixed rule: their earliest PersonID, else their "
                   "earliest employee number. See "
                   "/data/schema.json.",
           "people": people}
    pj = out_dir / "people.json"
    pj.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pc = out_dir / "people.csv"
    n = 0
    with pc.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["person", "number_kind", "number", "name", "page"])
        for p in people:
            if p.get("replaced_by"):
                w.writerow([p["person"], "replaced_by", p["replaced_by"], "", ""])
                n += 1
                continue
            for kind, field in (("employee_number", "employee_numbers"),
                                ("person_id", "person_ids"), ("member_id", "member_ids")):
                for num in p.get(field) or []:
                    w.writerow([p["person"], kind, num, p.get("name") or "", p.get("page") or ""])
                    n += 1
    return [{"path": "/data/people.json", "rows": len(people), "bytes": pj.stat().st_size},
            {"path": "/data/people.csv", "rows": n, "bytes": pc.stat().st_size}]
