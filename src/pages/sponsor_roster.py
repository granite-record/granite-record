#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.3
"""
The members the bill search's Sponsor filter lists, a term at a time:
site/sponsors/<term>.json (the owner, 19 November 2026: "a dropdown list of
the sitting term's State Representatives and Senators that you can scroll and
type into").

    import sponsor_roster as SR
    people = {}
    SR.note_bill(people, term, row, sp_list, prime, person_name)   # each bill
    SR.add_sitting(people, current, legs, former, own_slug, person_name)
    SR.write(out, people)

Each member of a term is one row, keyed as the term's bill index keys them
(`sponsor` and `cosp` of idx/<term>.json, and app.js's spKey), so the page
counts their bills from the index it already holds and the count is always
the number of bills the filter then lists. The file says only who they are:

    k   the key, as the index spells it ("Nancy Murphy", "Allen (Hills 1)")
    l   the label, with the seat held in that term ("Rep. Nancy Murphy (D - Hills 12)")
    c   the chamber, "H" or "S", read off the label's honorific; absent where it gives none
    p   the party letter, where the record gives one
    o   the order a list reads them in, surname first ("murphy, nancy")
    t   the towns of their district, for the term the sitting roster describes
    f   1 for a member of that term who holds no seat now

Who is listed: everyone a bill of the term names, as prime sponsor or
co-sponsor, with the label that bill gives them; and for the term the sitting
roster describes (add_sitting), every sitting member and every member who
served in it and has since left, whether or not they put their name to a bill.
A finished term lists the people its bills name: who served in it and filed or
signed nothing is not on this disk in a form that names them as its bills do.

Twenty files at most, one per term; a term no bill names is no file, and a file
an earlier build left for a term this one does not build is removed.
"""
import json
import re

# The seat a label ends with, as app.js's SEAT_RE reads it.
SEAT_RE = re.compile(r"\(([^()]*)\)\s*$")
HONORIFIC = {"Rep.": "H", "Sen.": "S"}


def sp_key(row):
    """The prime sponsor's key, as app.js's spKey makes it from the same row:
    the name, and for a 1989-1998 sponsor left as printed (no page, no party,
    no person placed) the seat beside it, which tells two of one surname apart."""
    n = row.get("sponsor") or ""
    if not n or row.get("sponsor_slug") or row.get("sponsor_party") or row.get("sponsor_person"):
        return n
    m = SEAT_RE.search(row.get("sponsor_label") or "")
    return f"{n} ({m.group(1)})" if m and re.search(r"\d", m.group(1)) else n


def chamber_of(label):
    """"H" or "S" by the label's honorific (a member-elect's "Rep.-elect" is
    Rep.), or "" where the label names none."""
    head = str(label or "").split(" ", 1)[0].removesuffix("-elect")
    return HONORIFIC.get(head, "")


def _surname_first(name):
    bits = str(name or "").split()
    suffix = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
    while len(bits) > 1 and bits[-1].lower() in suffix:
        bits = bits[:-1]
    return (f"{bits[-1]}, {' '.join(bits[:-1])}" if len(bits) > 1 else " ".join(bits)).lower()


def _seat(tag):
    """A district as one string however the record padded it: the bill status
    page's "Belk 06" is the roster's "Belk 6"."""
    return re.sub(r"(?<!\d)0+(?=\d)", "", str(tag or "").strip())


def _add(book, key, label, party, order, slug, prime):
    party = str(party or "").strip().upper()[:1]
    had = book.get(key)
    # The first label a prime sponsorship gives is the one the filter already
    # prints for them (app.js noteSponsors keeps the first); a co-sponsor's
    # label stands only until a bill of theirs names them as its prime sponsor.
    if had and (had["prime"] or not prime):
        if slug and not had["slug"]:
            had["slug"] = slug
        return
    book[key] = {"k": key, "l": label or key, "c": chamber_of(label), "p": party,
                 "o": order or _surname_first(key), "slug": slug or "", "prime": prime,
                 "t": [], "f": 0}


def note_bill(people, term, row, sp_list, prime, person_name):
    """Everyone this bill's index row names, under its term: the prime sponsor
    by the row's own label, and each co-sponsor (the row's `cosp`, made the same
    way here) by the label their sponsor record carries."""
    if not term:
        return
    book = people.setdefault(term, {})
    k = sp_key(row)
    if k:
        _add(book, k, row.get("sponsor_label"), row.get("sponsor_party"),
             (prime or {}).get("sort"), row.get("sponsor_slug"), True)
    for s in sp_list or []:
        if s is prime:
            continue
        n = person_name(s.get("name") or "")
        if not n or n == row.get("sponsor"):
            continue
        _add(book, n, s.get("display_full") or s.get("display") or n, s.get("party"),
             s.get("sort"), s.get("slug"), False)


def add_sitting(people, term, legs, former, own_slug, person_name, labels=None):
    """The term the sitting roster describes: every sitting member, with their
    towns, whether or not a bill names them; every member who served in it and
    holds no seat now, marked `f`; and each of them already listed, by their
    page, given the towns of their district. A former member's towns are their
    district's as the sitting roster gives it, the term's plan being one.

    `labels` is how the member's own page labels them: a member -> member_labels
    dict, which build_site_v2 passes (sitting_labels). The roster build_site_v2
    reads (data/legislators.json, and former_roster's members) carries no
    display_full -- the built site/legislators.json gains it later -- and on
    the dry run of 19 November 2026 the 31 sitting members and the 2 who left
    that no bill names were listed by their bare names, under no chamber.
    Without `labels`, a member's own display_full or roster label is used."""
    if not term:
        return
    book = people.setdefault(term, {})
    slug_of = lambda m: m.get("slug") or own_slug(m)
    sitting = {slug_of(m): m for m in (legs or {}).values() if slug_of(m)}
    towns_of_seat = {}
    for m in sitting.values():
        # The raw roster has no district_label either; its labels give one.
        tag = ((labels(m) if labels else None) or {}).get("district_label") or m.get("district_label")
        seat = (str(m.get("chamber") or "")[:1].upper(), _seat(tag))
        towns_of_seat.setdefault(seat, set()).update(m.get("towns") or [])
    left = {slug_of(m): m for m in (former or {}).values()
            if slug_of(m) and slug_of(m) not in sitting
            and term in (((m.get("served") or {}).get("terms")) or [])}
    listed = {e["slug"] for e in book.values() if e["slug"]}
    for slug, m in list(sitting.items()) + list(left.items()):
        if slug in listed:
            continue
        k = person_name(m.get("name") or "")
        if not k or k in book:
            continue
        lab = (labels(m) if labels else None) or {}
        label = lab.get("display_full") or m.get("display_full") or m.get("label") or m.get("display") or k
        _add(book, k, label, m.get("party_code") or m.get("party"), lab.get("sort") or m.get("sort"), slug, False)
        # A label that names no chamber still has the roster's.
        if not book[k]["c"] and str(m.get("chamber") or "")[:1].upper() in ("H", "S"):
            book[k]["c"] = str(m.get("chamber"))[:1].upper()
        listed.add(slug)
    for e in book.values():
        m = sitting.get(e["slug"])
        if m:
            e["t"] = sorted(m.get("towns") or [])
        elif e["slug"] in left:
            e["f"] = 1
            seat = (e["c"], _seat((SEAT_RE.search(e["l"]) or [None, ""])[1].split(" - ")[-1]))
            e["t"] = sorted(towns_of_seat.get(seat, ()))


def rows(book):
    """A term's members as the file lists them: the House, the Senate, then
    anyone whose label names no chamber, each by surname."""
    rank = {"H": 0, "S": 1}
    out = []
    for e in sorted(book.values(), key=lambda e: (rank.get(e["c"], 2), e["o"], e["k"])):
        r = {"k": e["k"], "l": e["l"], "o": e["o"]}
        for f in ("c", "p", "t", "f"):
            if e[f]:
                r[f] = e[f]
        out.append(r)
    return out


def write(out, people):
    """site/sponsors/<term>.json for every term `people` holds, and no other:
    a file an earlier build wrote for a term this one has none of is removed."""
    d = out / "sponsors"
    d.mkdir(exist_ok=True)
    for term, book in people.items():
        (d / f"{term}.json").write_text(
            json.dumps({"term": term, "members": rows(book)}, separators=(",", ":"),
                       ensure_ascii=False), encoding="utf-8")
    for stale in sorted(d.glob("*.json")):
        if stale.stem not in people:
            stale.unlink()
    n = sum(len(b) for b in people.values())
    print(f"  sponsors/: {len(people)} terms, {n:,} members the Sponsor filter lists")
