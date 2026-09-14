#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-13.2
"""
Which sitting members voted under an earlier number in the other chamber.

    python3 member_links.py          # the pairs and the near misses, with the evidence
    from member_links import links   # what build_site_v2 joins a member's votes with

A member who moves between the House and the Senate is given a new employee
number and a new PersonID, so a page built from one number shows one chamber.
On 12 September that left Sen. Cindy Rosenwald's page with 1,399 of her 4,218
votes, and Rep. Gary Daniels, who went from the House to the Senate and back,
with his House years only. On the 13th the person decided that a member's page
keeps the history of every chamber they sat in.

THE JOIN IS NOT ON NAME ALONE, because that rule has already been wrong here.
careers.json joined numbers on first and last name where service did not
overlap, and merged two different Rep. Patrick Longs -- Hillsborough 23 from
2007 to 2024 and Hillsborough 26 from 2025 -- while missing Sen. Pat Long,
whom the roster spells "Pat". A stranger's votes on somebody's page is worse
than a partial career, so an earlier number is joined to a sitting member only
when every one of these holds:

  1. it voted in the other chamber only. Two numbers in the same chamber are
     two people: a member who comes back to a chamber gets their old number
     back (Daniels, McConkey), and the two Patrick Longs have two;
  2. the same surname, and the same first name or a short form of it
     (Pat and Patrick, Bill and William);
  3. they never sat at the same time: no day on which both voted, and within
     any term both voted in, one's votes all come before the other's;
  4. the same party on every vote under both numbers (a row with no party
     letter says nothing either way);
  5. the same ground. A House number's county is one of the counties of the
     sitting senator's towns; a Senate number's district is one of the Senate
     districts of the sitting representative's towns. Today's map, because it
     is the only one on disk -- a district redrawn since can fail this, and
     then the pair is left for a person rather than joined;
  6. nobody else fits: exactly one earlier number fits the member, and that
     number fits nobody else.

A candidate that meets 1-3 and fails anything after is reported with the
reason and is not joined. Nothing here reads the network or writes a file.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

COUNTIES = {
    "belknap": "Belknap", "belk": "Belknap", "carroll": "Carroll", "carr": "Carroll",
    "cheshire": "Cheshire", "ches": "Cheshire", "coos": "Coos", "grafton": "Grafton",
    "graf": "Grafton", "hillsborough": "Hillsborough", "hills": "Hillsborough",
    "merrimack": "Merrimack", "merr": "Merrimack", "rockingham": "Rockingham",
    "rock": "Rockingham", "strafford": "Strafford", "straf": "Strafford",
    "sullivan": "Sullivan", "sull": "Sullivan",
}

# Short forms that are not a prefix of the name. A prefix (Pat, Patrick; Tim,
# Timothy) is accepted without being listed.
SHORT = {
    "bill": "william", "will": "william", "bob": "robert", "rob": "robert",
    "dick": "richard", "rick": "richard", "jim": "james", "jack": "john",
    "ted": "edward", "ned": "edward", "chuck": "charles", "peggy": "margaret",
    "liz": "elizabeth", "beth": "elizabeth", "betsy": "elizabeth",
    "sue": "susan", "tony": "anthony", "andy": "andrew", "jerry": "gerald",
    "larry": "lawrence", "mike": "michael", "kathy": "katherine",
    "jenn": "jennifer", "jen": "jennifer", "jeff": "jeffrey", "joe": "joseph",
    "steve": "stephen", "matt": "matthew", "dave": "david", "dan": "daniel",
    "tom": "thomas", "ken": "kenneth", "ron": "ronald", "don": "donald",
}

_SEN_RE = re.compile(r"\([A-Z]\s*-\s*SD\s*(\d+)\)")
_REP_RE = re.compile(r"\([A-Z]\s*-\s*([A-Za-z]+)\.?\s*(\d+)\)")
_OLD_RE = re.compile(r"\([A-Z]\)\s*([A-Za-z]+)?\.?\s*(\d+)\s*$")
_WARD_RE = re.compile(r"^(.*?)\s+Ward\s+(\w+)$", re.I)


def _letters(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def surname(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", (s or "").lower())
    return _letters(s)


def first_names(raw):
    """Every form a first name is written in: "Edward (Ned)" is both."""
    words = re.findall(r"[A-Za-z']+", raw or "")
    out = {_letters(words[0])} if words else set()
    out |= {_letters(w) for w in re.findall(r"\(([A-Za-z']+)\)", raw or "")}
    return {w for w in out if w}


def same_first(a, b):
    for x in first_names(a):
        for y in first_names(b):
            short, full = sorted((x, y), key=len)
            if x == y or (len(short) >= 3 and full.startswith(short)):
                return True
            if SHORT.get(x) == y or SHORT.get(y) == x:
                return True
    return False


def split_name(name):
    """("Long", "Patrick") from "Long, Patrick" or "Rep. Patrick Long (D - Hills 26)"."""
    s = re.sub(r"\s*\(.*$", "", name or "") if "," not in (name or "") else name
    s = re.sub(r"^(?:Rep|Sen)\.\s+", "", s or "").strip()
    if "," in s:
        last, first = [x.strip() for x in s.split(",", 1)]
        first = re.sub(r"\([A-Z]\).*$", "", first).strip()
        return last, first
    bits = s.split()
    return (bits[-1], " ".join(bits[:-1])) if len(bits) > 1 else (s, "")


def seat(label):
    """(county, number) from a roll call label. The number is a House district
    within the county, or a Senate district, by the chamber of the vote."""
    lab = label or ""
    m = _SEN_RE.search(lab)
    if m:
        return None, int(m.group(1))
    m = _REP_RE.search(lab) or _OLD_RE.search(lab)
    if m:
        return COUNTIES.get((m.group(1) or "").lower()), int(m.group(2))
    return None, None


def _day(s):
    p = (s or "").split("/")
    try:
        return f"{int(p[2]):04d}-{int(p[0]):02d}-{int(p[1]):02d}"
    except (IndexError, ValueError):
        return (s or "")[:10]


def _term(year):
    y = int(year)
    return y if y % 2 else y - 1


def profiles(votes_by_member):
    """{id: what the votes cast under that number say about who cast them}."""
    out = {}
    for mid, rows in votes_by_member.items():
        if not rows:
            continue
        names, parties, labels, bodies = Counter(), Counter(), Counter(), Counter()
        days, span = set(), {}
        for v in rows:
            names[v.get("name") or ""] += 1
            parties[(v.get("party") or "").strip()[:1].upper()] += 1
            labels[v.get("label") or ""] += 1
            bodies[v.get("body")] += 1
            d = _day(v.get("date"))
            days.add(d)
            try:
                t = _term(v.get("year") or d[:4])
            except ValueError:
                continue
            lo, hi = span.get(t, (d, d))
            span[t] = (min(lo, d), max(hi, d))
        out[str(mid)] = {"name": names.most_common(1)[0][0],
                         "label": labels.most_common(1)[0][0],
                         "parties": parties, "bodies": set(bodies), "days": days,
                         "span": span, "n": len(rows),
                         "years": sorted({int(d[:4]) for d in days if d[:4].isdigit()})}
    return out


def ground(member, districts):
    """(counties, Senate districts) of the towns a sitting member sits for."""
    seats = [(s.get("town"), str(s.get("ward") or "")) for s in member.get("town_seats") or []]
    if not seats:
        for t in member.get("towns") or []:
            w = _WARD_RE.match(t)
            seats.append((w.group(1), w.group(2)) if w else (t, ""))
    counties, senate = set(), set()
    for town, ward in seats:
        wards = districts.get(town) or {}
        for key, d in wards.items():
            if ward and key not in (ward, "0"):
                continue
            if d.get("senate"):
                senate.add(int(d["senate"]))
            counties |= {h.get("county") for h in d.get("house") or [] if h.get("county")}
    return counties, senate


def sat_together(a, b):
    """True when two numbers were plainly held at once."""
    if a["days"] & b["days"]:
        return True
    for t in set(a["span"]) & set(b["span"]):
        (alo, ahi), (blo, bhi) = a["span"][t], b["span"][t]
        if alo <= bhi and blo <= ahi:
            return True
    return False


def links(roster, votes_by_member, districts, prof=None):
    """({sitting id: [earlier ids]}, [candidates not joined, with the reason]).

    roster is the sitting members (data/legislators.json), votes_by_member
    {id: [member_votes rows]}, districts site/districts.json.
    """
    prof = prof or profiles(votes_by_member)
    by_surname = defaultdict(list)
    for eid, p in prof.items():
        key = surname(split_name(p["name"])[0])
        if key:
            by_surname[key].append(eid)

    fits, missed = defaultdict(list), []
    for m in roster:
        sid, chamber = str(m.get("id")), (m.get("chamber") or "")[:1].upper()
        own = prof.get(sid)
        if not own or chamber not in ("H", "S"):
            continue
        other = "S" if chamber == "H" else "H"
        party = (m.get("party_code") or (m.get("party") or "")[:1]).upper()
        last, first = split_name(m.get("name"))
        last, first = m.get("last") or last, m.get("first") or first
        counties, senate = ground(m, districts)
        for eid in by_surname.get(surname(last), []) if surname(last) else []:
            p = prof[eid]
            if eid == sid or p["bodies"] != {other}:
                continue
            if not same_first(split_name(p["name"])[1], first):
                continue
            if sat_together(own, p):
                continue
            why = []
            then = {x for x in p["parties"] if x}
            now = {x for x in own["parties"] if x}
            if then != {party} or now != {party}:
                why.append("party: " + "/".join(sorted(then)) + " then, "
                           + "/".join(sorted(now)) + " now")
            county, number = seat(p["label"])
            if other == "H" and county not in counties:
                why.append(f"ground: House seat in {county or 'no county'}, "
                           f"the Senate district's towns in {', '.join(sorted(counties)) or 'none on file'}")
            if other == "S" and number not in senate:
                why.append(f"ground: Senate district {number}, the member's towns in "
                           f"{', '.join(map(str, sorted(senate))) or 'none on file'}")
            rec = {"member": sid, "earlier": eid, "label": m.get("label") or m.get("name"),
                   "earlier_label": p["label"], "chamber": other,
                   "years": p["years"], "votes": p["n"], "why": why}
            (missed if why else fits[sid]).append(rec)

    claimed = Counter(r["earlier"] for rs in fits.values() for r in rs)
    linked = {}
    for sid, rs in fits.items():
        if len(rs) == 1 and claimed[rs[0]["earlier"]] == 1:
            linked[sid] = [rs[0]["earlier"]]
            continue
        for r in rs:
            r["why"] = (["more than one earlier number fits this member: "
                         + ", ".join(sorted(x["earlier"] for x in rs))] if len(rs) > 1
                        else ["this number also fits another sitting member"])
            missed.append(r)
    return linked, missed


def seats_held(roster, votes_by_member, linked, current_term):
    """{sitting id: {("2023-2024", "H"), ...}}: each term and chamber a sitting
    member sat in, from the votes under their own number and the numbers joined
    to it -- and the chamber the roster seats them in for the current term,
    which a member elected in a special election holds before their first roll
    call. What a sponsor record matched on a name alone is tested against."""
    out = {}
    for m in roster:
        sid = str(m.get("id"))
        held = set()
        for x in (sid, *linked.get(sid, [])):
            for v in votes_by_member.get(x, []):
                y = str(v.get("year") or "")
                if y.isdigit() and v.get("body") in ("H", "S"):
                    t = _term(y)
                    held.add((f"{t}-{t + 1}", v["body"]))
        if current_term and (m.get("chamber") or "")[:1] in ("H", "S"):
            held.add((current_term, m["chamber"][:1]))
        out[sid] = held
    return out


def service(votes):
    """[{"chamber": "H", "spans": [[1999, 2000], [2007, 2014]]}, ...]

    The years a member has a recorded roll call in each chamber, from member_votes
    rows, with the years of consecutive terms run together: Rep. Gary Daniels
    is House 1999-2000, 2007-2014 and 2025-2026, and Senate 2015-2018 and
    2021-2022. Years with a vote, not years of office -- the record of roll
    calls starts in 1999, and a member who left in 2009 does not end in 2010.
    """
    years = defaultdict(set)
    for v in votes:
        y = str(v.get("year") or "")
        if v.get("body") in ("H", "S") and y.isdigit():
            years[v["body"]].add(int(y))
    out = []
    for body in sorted(years, key=lambda b: min(years[b])):
        spans = []
        for y in sorted(years[body]):
            if spans and _term(y) <= _term(spans[-1][1]) + 2:
                spans[-1][1] = y
            else:
                spans.append([y, y])
        out.append({"chamber": body, "spans": spans})
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    roster = json.loads(Path("data/legislators.json").read_text(encoding="utf-8"))
    districts = json.loads(Path("site/districts.json").read_text(encoding="utf-8"))
    by = defaultdict(list)
    for v in json.loads(Path("data/member_votes.json").read_text(encoding="utf-8")):
        by[str(v["member_id"])].append(v)
    prof = profiles(by)
    linked, missed = links(roster, by, districts, prof)
    who = {str(m["id"]): m for m in roster}
    print(f"{len(linked)} sitting member(s) also voted under a number in the other chamber:\n")
    for sid in sorted(linked, key=lambda s: who[s].get("last") or ""):
        for eid in linked[sid]:
            p, own = prof[eid], prof[sid]
            print(f"  {who[sid].get('label')}  [{sid}, {own['n']:,} votes "
                  f"{own['years'][0]}-{own['years'][-1]}]")
            print(f"      + {p['label']}  [{eid}, {p['n']:,} votes "
                  f"{p['years'][0]}-{p['years'][-1]}]")
    print(f"\n{len(missed)} candidate(s) not joined:")
    for r in missed:
        print(f"  {r['label']} [{r['member']}]  ?  {r['earlier_label']} [{r['earlier']}, "
              f"{r['votes']:,} votes {r['years'][0]}-{r['years'][-1]}]")
        for w in r["why"]:
            print(f"      - {w}")


if __name__ == "__main__":
    main()
