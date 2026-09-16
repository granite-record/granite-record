#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-14.3
"""
Sponsors read off each bill's own text, for the bills the database names none for.

    python3 text_sponsors.py            # what the saved pages give, term by term; writes nothing
    python3 text_sponsors.py --score    # measured against the terms the database does cover
    python3 text_sponsors.py --apply    # writes text_sponsors.json

No network. It reads what fetch_legislation.py has saved under legislation/<year>/, so it
fills in as the lane goes: a build after a night's pages reads that night's pages.

WHAT IS MISSING

data/sponsors.json names sponsors for 2023-2024 and 2025-2026, from the General Court's
database, its sponsor files and its bill status pages. The seventeen terms before -- 29,453
bills, 1989 to 2022 -- had none: "No sponsors on file" on every page, and a search for a
member found nothing they sponsored before 2023. The person pointed out on 14 September that
the bill text the lane is fetching carries them.

WHAT THE PAGE SAYS

The text opens with one line naming who introduced it, in the chamber's shorthand. Read off
3,555 saved pages, not assumed:

    1989   Rep. Millard of Merrimack Dist. 4; Sen. Preston of Dist. 23
    1994   Rep. Guay, Coos 6; Sen. Shaheen, Dist 21
    2017   Rep. Itse, Rock. 10; Rep. K. Rice, Hills. 37; Sen. Reagan, Dist 17

A surname -- with an initial or a first name where two members share it, "Rep. W. Riley",
"Rep. Marshall Quandt" -- and a county and House district, or a Senate district. Written
"Barnes, Jr." and once "Muns, C"; "Fuller Clark" and "Fuller-Clark"; with a curly apostrophe
in D'Allesandro on some pages and a straight one on others. The comments in split() say which.

WHO THAT IS

A surname is not a person. It is matched only among the members who cast a roll call in that
chamber in that term, and only when exactly one fits the surname and any initial. Where two
do, the House county and then the district decide it, or nothing does. The roll call record
keeps one seat per member rather than one per term, so its county can refuse a match (see
Sat.resolve) and never prove one.

Where nobody fits, the sponsor stays as the page prints them -- "Rep. C. Brown (Graf 14)",
no party, no link. That is every sponsor before 1999, when the record of roll calls begins,
and a few after. Rep. Shurtleff has no ballot under his name in any term on disk. Rep. Cote
has none in 2023-2024. Belanger, Homola, Littlefield and Moran match nobody in 2021-2022,
where four House numbers vote as "Member #". Whether those are the same people is not
known.

WHAT IT IS WORTH, measured against sources this did not produce (14 September)

    2023-2024, 1,831 saved pages against the database's sponsors:
        8,652 sponsors both name     8,650 placed on the member the database names
                                         0 placed on anybody else
                                         2 not placed (Rep. Cote)
    2025-2026, 2,220 pages in bill_text/ against the sponsor files:
        12,784 sponsors both name   12,783 placed on the member the files name
                                         1 on another of the name: "Rep. K. Murray" was
                                           placed on Kate Murray, where the file lists Megan
                                           Murray. Whether the page and the file disagree or
                                           the placement is wrong is not settled.

THE FIRST NAME ON THE LINE IS THE PRIME SPONSOR on 1,133 of the 1,134 current bills whose
sponsor file marks one, so the first is recorded as prime, and marked prime_inferred.

THE TEXT CAN NAME MORE PEOPLE THAN THE DATABASE. 2023 CACR 1 prints Moffett, Adjutant,
Schultz and Kenney, and the database lists Moffett and Schultz: 1,297 such names in
2023-2024, 235 in 2025-2026. Why is not known -- a cosponsor who later withdrew is one guess,
and it is only a guess. So these are the sponsors named on the bill's text, and the page says
that is where they come from, rather than presenting them as the General Court's list.

NEVER OVER THE DATABASE. merge_into() gives a bill its text's sponsors only when data/
sponsors.json names nobody for it, so the two covered terms keep their own, apart from the 107
bills of 2023-2024 the database names nobody for.
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from member_links import COUNTIES, SHORT, seat as label_seat

PAGES = Path("legislation")
CURRENT_TEXT = Path("bill_text")      # 2025-2026 from billText.aspx; read by --score only
VOTES = Path("data/member_votes.json")
SPONSORS = Path("data/sponsors.json")
BILLS = Path("data/bills.json")
OUT = Path("text_sponsors.json")
SOURCE = "bill text"

ABBR = {"Belknap": "Belk", "Carroll": "Carr", "Cheshire": "Ches", "Coos": "Coos",
        "Grafton": "Graf", "Hillsborough": "Hills", "Merrimack": "Merr",
        "Rockingham": "Rock", "Strafford": "Straf", "Sullivan": "Sull"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

HONORIFIC = re.compile(r"^(Rep|Sen)s?\b\.?\s*", re.I)
# ", Coos 6"   ", Graf. 14"   ", Dist 21"   " of Merrimack Dist. 4"   " of Dist. 23"
# The first seat in the piece ends it: one 2022 line ran on into the page's next heading,
# "Sen. Watters, Dist 4 commission: Resources, Recreation and Development".
SEAT = re.compile(r"(?:,|\s+of)\s+(?:(?P<place>[A-Za-z]+)\.?\s+)?(?:Dist\.?\s*)?"
                  r"(?P<num>\d{1,3})(?![\d])")
NOTE = re.compile(r"\s*\(([^)]*)\)\s*$")


def letters(s):
    """Only the letters, unaccented: "Côté" and "Cote", "D'Allesandro" and "DAllesandro",
    "Fuller-Clark" and "Fuller Clark" are each one key."""
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z]", "", "".join(ch for ch in s if not unicodedata.combining(ch)).lower())


def term_of(year):
    y = int(year)
    t = y if y % 2 else y - 1
    return f"{t}-{t + 1}"


# ------------------------------------------------------------------ reading the line

def split(field):
    """[{chamber, words, suffix, county, district, note, printed}] from a sponsor line."""
    out = []
    for raw in re.split(r"\s*;\s*", field or ""):
        s = raw.strip(" .,")
        if not s:
            continue
        printed, note = s, ""
        m = NOTE.search(s)
        if m:
            note, s = m.group(1).strip(), s[:m.start()]
        h = HONORIFIC.match(s)
        chamber = {"rep": "H", "sen": "S"}[h.group(1).lower()] if h else ""
        lead = h.end() if h else 0
        s = s[lead:]
        county = district = ""
        for m in SEAT.finditer(s):
            place = m.group("place") or ""
            if place and not place.lower().startswith("dist"):
                county = COUNTIES.get(place.lower(), "")
                if not county:
                    continue            # "Jr. 3" is not a seat; look further along
            district = str(int(m.group("num")))
            if s[m.end():].strip(" .,"):
                printed = printed[:lead + m.end()]
            s = s[:m.start()]
            if not chamber:
                chamber = "H" if county else "S"
            break
        # "Barnes, Jr." is a surname and a suffix; "Muns, C" is a surname and an initial,
        # the other way round from "C. Muns".
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if not parts:
            continue
        suffix = [p for p in parts[1:] if letters(p) in SUFFIXES]
        given = [p for p in parts[1:] if letters(p) not in SUFFIXES]
        words = " ".join(given + parts[:1]).split()
        while len(words) > 1 and letters(words[-1]) in SUFFIXES:
            suffix.insert(0, words.pop())
        suffix = [x if x.endswith(".") or letters(x) in ("ii", "iii", "iv") else x + "."
                  for x in suffix]
        out.append({"chamber": chamber, "words": words, "suffix": " ".join(suffix),
                    "county": county, "district": district, "note": note,
                    "printed": printed})
    return out


# ------------------------------------------------------------------ who that is

def vote_name(raw):
    """("Barnes", "John", "Jr.") from "Barnes, Jr., John"; None for "Member #377204"."""
    raw = (raw or "").strip()
    if not raw or raw.lower().startswith(("member #", "(unknown", "former member")):
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) < 2:
        return None
    last, rest = parts[0], parts[1:]
    suffix = [p for p in rest if letters(p) in SUFFIXES]
    rest = [p for p in rest if letters(p) not in SUFFIXES]
    lw = last.split()
    if len(lw) > 1 and letters(lw[-1]) in SUFFIXES:
        suffix.append(lw[-1])
        last = " ".join(lw[:-1])
    return last, (rest[-1] if rest else ""), " ".join(suffix)


def given_fits(given, first):
    """Does an initial or a first name on the page fit a member's first name?"""
    if not given:
        return True
    g = letters(given[0])
    names = [letters(w) for w in re.findall(r"[A-Za-z']+", first or "")]
    names = [w for w in names if w]
    if not g or not names:
        return False
    if len(g) == 1:
        return any(w.startswith(g) for w in names)
    for w in names:
        short, full = sorted((g, w), key=len)
        if g == w or (len(short) >= 3 and full.startswith(short)):
            return True
        if SHORT.get(g) == w or SHORT.get(w) == g:
            return True
    return False


class Sat:
    """Everyone who cast a roll call, by term and chamber, from data/member_votes.json.

    The roll call record keeps ONE label per member -- the seat they held last, not the
    seat they held that term -- so a seat read from it can break a tie between two
    members and cannot, on its own, prove or disprove one.
    """

    def __init__(self, rows):
        seen = {}
        for v in rows:
            y = str(v.get("year") or "")
            if not y.isdigit() or v.get("body") not in ("H", "S"):
                continue
            key = (term_of(y), v["body"], str(v.get("member_id") or ""))
            m = seen.get(key)
            if m is None:
                nm = vote_name(v.get("name"))
                if not nm or not key[2]:
                    seen[key] = False
                    continue
                county, number = label_seat(v.get("label"))
                m = seen[key] = {"id": key[2], "last": nm[0], "first": nm[1], "suffix": nm[2],
                                 "county": county or "", "number": number,
                                 "parties": Counter()}
            if m:
                m["parties"][(v.get("party") or "").strip()[:1].upper()] += 1
        self.pool = defaultdict(lambda: defaultdict(list))
        for (term, body, _id), m in seen.items():
            if m:
                p = [k for k, _n in m["parties"].most_common() if k]
                m["party"] = p[0] if p else ""
                self.pool[(term, body)][letters(m["last"])].append(m)

    @classmethod
    def load(cls, path=VOTES):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def terms(self):
        return {t for t, _b in self.pool}

    def resolve(self, term, sp):
        """(member or None, why)."""
        pool = self.pool.get((term, sp["chamber"]))
        if not pool:
            return None, "no roll call on record for that chamber and term"
        words, cands = sp["words"], []
        for k in range(len(words)):
            cands = [m for m in pool.get(letters("".join(words[k:])), [])
                     if given_fits(words[:k], m["first"])]
            if cands:
                break
        if not cands:
            return None, "nobody of that name cast a roll call in that chamber and term"
        # A HOUSE MEMBER WHOSE LABEL NAMES ANOTHER COUNTY IS NOT PLACED. The label is one
        # seat per member and not always right -- Rep. Wendy Chase's reads Belknap 5 and her
        # bills print Strafford 18 -- so a county that agrees proves nothing. One that
        # disagrees may be that error or may be a second member of the name who cast no
        # roll call; a sponsor left as the page prints them is incomplete, and the wrong
        # member's name on a bill would be false.
        if sp["chamber"] == "H" and sp["county"]:
            cands = [m for m in cands if not m["county"] or m["county"] == sp["county"]]
            if not cands:
                return None, "a member of that name sat for another county"
        if len(cands) == 1:
            return cands[0], "the only member of that name"
        narrowed = cands
        if sp["district"]:
            narrowed = [m for m in cands if str(m["number"] or "") == sp["district"]]
        if len(narrowed) == 1:
            return narrowed[0], "one of several of that name, by district"
        return None, f"{len(cands)} members of that name, and the seat does not settle it"


def record(i, sp, m):
    """One sponsor in the shape data/sponsors.json carries them."""
    ch = sp["chamber"]
    if m:
        name = " ".join(x for x in (m["first"], m["last"], m["suffix"]) if x)
        party = m.get("party", "")
    else:
        name = " ".join(sp["words"] + ([sp["suffix"]] if sp["suffix"] else []))
        party = ""
    hon = {"H": "Rep.", "S": "Sen."}.get(ch, "")
    tag = (f"SD{sp['district']}" if ch == "S" and sp["district"]
           else f"{ABBR.get(sp['county'], '')} {sp['district']}".strip()
           if sp["county"] and sp["district"] else "")
    inside = " - ".join(x for x in (party, tag) if x)
    return {"member_id": m["id"] if m else "", "name": name, "party": party, "chamber": ch,
            "county": sp["county"] if ch == "H" else "", "district": sp["district"],
            "label": f"{hon} {name}".strip() + (f" ({inside})" if inside else ""),
            "sequence": i, "prime": i == 0, "source": SOURCE, "prime_inferred": True,
            "as_printed": sp["printed"]}


# ------------------------------------------------------------------ the pages

def saved_pages(bills):
    """(term, bill, path) for every saved page whose bill is in data/bills.json."""
    import fetch_legislation as FL
    out, strays = [], []
    for f in sorted(PAGES.glob("[0-9][0-9][0-9][0-9]/*.htm*")):
        m = FL.PAD.match(f.stem.upper())
        if not m:
            continue
        term, bid = term_of(f.parent.name), f"{m.group(1)}{int(m.group(2))}"
        rec = (bills.get(term) or {}).get(bid)
        year = str((rec or {}).get("year") or (rec or {}).get("lsr_year") or "")[:4]
        if rec is None or year != f.parent.name:
            strays.append(f"{f.parent.name}/{f.name}")
            continue
        out.append((term, bid, f))
    return out, strays


def read_line(path):
    import fetch_legislation as FL
    return FL.parse(FL.decode(Path(path).read_bytes())).get("sponsors") or ""


def build(bills, sat, only_missing=None):
    """{term: {bill: [records]}}, and a tally of how each sponsor was or was not placed."""
    pages, strays = saved_pages(bills)
    got, tally = defaultdict(dict), Counter()
    for term, bid, f in pages:
        if only_missing is not None and (only_missing.get(term) or {}).get(bid):
            tally["bills the database already names sponsors for"] += 1
            continue
        people = split(read_line(f))
        if not people:
            tally["pages with no sponsor line"] += 1
            continue
        recs = []
        for i, sp in enumerate(people):
            m, why = sat.resolve(term, sp) if sp["chamber"] else (None, "no chamber on the line")
            tally[why] += 1
            recs.append(record(i, sp, m))
        got[term][bid] = recs
    return dict(got), tally, strays


def merge_into(sponsors, path=OUT):
    """Give every bill `sponsors` names nobody for the sponsors its own text names.

    NEVER OVER THE DATABASE. A bill that already has a sponsor record keeps it, whatever the
    text says, so 2023-2024 and 2025-2026 are untouched. Returns how many bills gained them.
    Absent the file, nothing happens.
    """
    p = Path(path)
    if not p.exists():
        return 0
    try:
        extra = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    n = 0
    for term, rows in extra.items():
        have = sponsors.setdefault(term, {})
        for bid, recs in rows.items():
            if recs and not have.get(bid):
                have[bid] = recs
                n += 1
    return n


def seat_into(sponsors, path=OUT, current=None):
    """Date the seat on a database sponsor from the bill's own text.

    A LABEL STATES THE SEAT HELD WHEN THE RECORD WAS MADE. The database's
    sponsor rows for 2023-2024 carry no county and no district at all, so the
    site filled both from `data/legislators.json` -- the roster of the House
    and Senate sitting TODAY. 7,455 of that term's 8,890 sponsor lines were
    labelled with a seat their member holds now, and 167 of the 6,815 that
    can be checked against the bill's own printed line were provably a
    different seat: Matthew Wilhelm sponsored 36 bills from Hills. 40 and the
    site said Hills 21; Nicholas Germana 29 from Ches. 1, printed Ches 15.

    Worse, the database's own `chamber` reads H for six senators across 878
    rows, so 2023 CACR 10 printed "Rep. Donna Soucy" and "Rep. Jeb Bradley" --
    Bradley was the Senate President. The bill prints "Sen. Soucy, Dist 18".

    The bill's text is the contemporaneous source: it printed the seat as it
    was on the day it was filed. So where a saved page names the same sponsor
    the database does, the chamber, county and district come from the page and
    the record keeps everything else -- its name, its party, its sequence, and
    its `source`, because the sponsor is still the database's and only the
    seat is being dated.

    NOT THE CURRENT TERM. `current` names the term whose roster is itself
    contemporaneous, and it is left alone: the 2025-2026 LSR file pairs a
    HOUSE county and number with chamber "S" on 6,405 rows, so the text would
    be overruling the roster with something worse. Mark McConkey comes through
    it as Carr 8 -> SD08 against his real SD3.

    Returns how many sponsor rows were given a dated seat.
    """
    p = Path(path)
    if not p.exists():
        return 0
    try:
        text = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    n = 0
    for term, rows in text.items():
        if term == current:
            continue
        have = sponsors.get(term) or {}
        for bid, printed in rows.items():
            db = have.get(bid)
            if not db or not printed:
                continue
            for rec in db:
                if rec.get("source") == SOURCE:
                    continue            # already the text's own row
                key = _db_name(rec.get("name"))[0]
                # One page sponsor, and only one, whose surname this name ends
                # with. Two of a surname on one bill is a pair this cannot tell
                # apart, and a seat put on the wrong brother is worse than a
                # seat that is merely out of date.
                fits = [s for s in printed
                        if s.get("chamber") and _page_key_of(s)
                        and key.endswith(_page_key_of(s))]
                if len(fits) != 1:
                    continue
                s = fits[0]
                if (rec.get("chamber") == s.get("chamber")
                        and rec.get("county") == s.get("county")
                        and rec.get("district") == s.get("district")):
                    continue
                rec["chamber"] = s["chamber"]
                rec["county"] = s.get("county") or ""
                rec["district"] = s.get("district") or ""
                rec["seat_source"] = SOURCE
                rec["as_printed"] = s.get("as_printed") or rec.get("as_printed")
                n += 1
    return n


def _page_key_of(rec):
    """The surname letters of a record written by record(): see _page_key."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", rec.get("name") or "").strip()
    words = [w for w in name.split() if letters(w) not in SUFFIXES]
    return letters(words[-1]) if words else ""


# ------------------------------------------------------------------ measuring it

def _db_name(raw):
    """Letters of a database name, first name first, without a suffix; and its first word."""
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw or "").strip()
    if "," in raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        parts = [p for p in parts if letters(p) not in SUFFIXES]
        raw = " ".join(parts[1:] + parts[:1])
    words = [w for w in raw.split() if letters(w) not in SUFFIXES]
    return letters("".join(words)), (words[0] if words else "")


def _page_key(sp):
    return letters("".join(w for w in sp["words"] if len(letters(w)) > 1))


def score(bills, sat, sponsors):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sets = []
    pages, _ = saved_pages(bills)
    sets.append(("legislation/ pages of 2023-2024, against its database sponsors",
                 [(t, b, f) for t, b, f in pages if (sponsors.get(t) or {}).get(b)]))
    cur = [("2025-2026", f.stem.upper(), f) for f in sorted(CURRENT_TEXT.glob("*.html"))]
    sets.append(("bill_text/ pages of 2025-2026, against its sponsor files",
                 [(t, b, f) for t, b, f in cur if (sponsors.get(t) or {}).get(b)]))
    for title, rows in sets:
        c, wrong, missed, order_ex = Counter(), [], [], []
        for term, bid, f in rows:
            db = sponsors[term][bid]
            page = split(read_line(f))
            c["bills"] += 1
            c["sponsors in the database"] += len(db)
            c["sponsors on the page"] += len(page)
            dbk = [_db_name(s.get("name")) for s in db]
            pk = [_page_key(s) for s in page]
            fits = lambda a, b: bool(b) and a.endswith(b)
            if len(page) == len(db):
                c["bills with the same number of sponsors"] += 1
                if all(fits(d[0], p) for d, p in zip(dbk, pk)):
                    c["bills with the same sponsors in the same order"] += 1
                elif sorted(pk) and all(any(fits(d[0], p) for d in dbk) for p in pk):
                    c["bills with the same sponsors in another order"] += 1
                    if len(order_ex) < 4:
                        order_ex.append(f"{bid}: page {pk[:4]} db {[d[0] for d in dbk[:4]]}")
            prime = next((s for s in db if (s.get("role") or "").lower() == "prime"), None)
            if prime and page:
                c["bills whose sponsor file marks a prime"] += 1
                c["... and the page lists that prime first"] += fits(_db_name(prime["name"])[0], pk[0])
            for sp in page:
                if not sp["chamber"]:
                    c["page sponsors with no chamber"] += 1
                    continue
                m, why = sat.resolve(term, sp)
                same = [d for d in dbk if fits(d[0], _page_key(sp))]
                if not same:
                    # On the text and not in the database's list: a source difference,
                    # not a reading of the page to be scored.
                    c["page sponsors the database does not list"] += 1
                    c["... of those, placed on a member"] += bool(m)
                    continue
                c["page sponsors the database also lists"] += 1
                if not m:
                    c["... not placed"] += 1
                    if len(missed) < 8:
                        missed.append(f"{term} {bid} {sp['printed']!r}: {why}")
                    continue
                full = letters(m["first"] + m["last"])
                ok = any(d[0] == full or (d[0].endswith(letters(m["last"])) and
                                          given_fits([d[1]], m["first"])) for d in same)
                if ok:
                    c["... placed on the member the database names"] += 1
                else:
                    c["... placed on somebody else of that name"] += 1
                    if len(wrong) < 12:
                        wrong.append(f"{term} {bid} {sp['printed']!r} -> {m['first']} {m['last']} "
                                     f"[{m['id']}] ({why}); database: "
                                     + "; ".join(s.get('name', '') for s in db
                                                 if fits(_db_name(s.get('name'))[0], _page_key(sp))))
        print(f"\n{title}")
        for k, v in c.items():
            print(f"  {k:58} {v:>7,}")
        for label, xs in (("placed on somebody else", wrong), ("not placed, though the database names them", missed),
                          ("another order", order_ex)):
            if xs:
                print(f"  {label}:")
                for x in xs:
                    print(f"    {x}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bills = json.loads(BILLS.read_text(encoding="utf-8"))
    sponsors = json.loads(SPONSORS.read_text(encoding="utf-8")) if SPONSORS.exists() else {}
    sat = Sat.load()
    if a.score:
        return score(bills, sat, sponsors)
    # EVERY BILL WITH A SAVED PAGE, not only the ones the database misses.
    # It used to stop at those, because filling a gap was all this file did.
    # The seat a bill PRINTS is wanted for the bills the database does cover
    # as well -- that is the only contemporaneous record of where a sponsor
    # sat -- and merge_into still refuses to put these names over the
    # database's, so reading more pages adds nothing to a covered bill except
    # the seat seat_into takes from it.
    got, tally, strays = build(bills, sat, only_missing=None)
    covered = sum(1 for t, rows in got.items() for b in rows
                  if (sponsors.get(t) or {}).get(b))
    print(f"{sum(len(v) for v in got.values()):,} bills have sponsors in their own text; "
          f"{covered:,} of them are also in the database, for the seat alone:")
    for term in sorted(got):
        n_recs = sum(len(v) for v in got[term].values())
        placed = sum(1 for v in got[term].values() for r in v if r["member_id"])
        print(f"  {term}: {len(got[term]):>5,} of {len(bills.get(term) or {}):>5,} bills, "
              f"{n_recs:>6,} sponsors, {placed:>6,} placed on a member who cast a roll call")
    print("\nhow each sponsor was placed, or why not:")
    for why, n in tally.most_common():
        print(f"  {n:>7,}  {why}")
    if strays:
        print(f"\n{len(strays)} saved pages match no bill of that year in data/bills.json, "
              f"e.g. {', '.join(strays[:5])}")
    if a.apply:
        OUT.write_text(json.dumps(got, indent=1), encoding="utf-8")
        print(f"\nwritten {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
