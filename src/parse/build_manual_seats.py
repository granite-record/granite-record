#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.1
"""
Who held each seat at the start of a term, 1989 to 1998, from the Manual for the General Court.

    python3 src/parse/build_manual_seats.py            # the coverage, term by term; writes nothing
    python3 src/parse/build_manual_seats.py --measure  # ... and the agreement with what we did not generate
    python3 src/parse/build_manual_seats.py --apply    # writes generated/manual_seats.json

No network. Reads data/manuals/<year>/*.txt (the Internet Archive's OCR text of the six editions the
State printed in 1989, 1991, 1993, 1995, 1997 and 1999; the files are downloaded, untrusted text and
are only ever read as text). A person's run, like build_past_roster.py: the file is rewritten whole
from the six editions, never edited and never written from a subset (a run that cannot read all six
refuses), and git keeps it.

WHAT IS IN AN EDITION, AND WHERE. An edition is printed at the start of a term and shows the election
that term's members came from. Three places say who sat:

    the House     the "REPRESENTATIVES TO THE GENERAL COURT" list of the GENERAL ELECTION returns, by
                  county and district: "District No. 6 (Dover-Wards 4,5 & 6)(5)" and below it every
                  candidate, "Ann M. Torr, r, Dover  3,075" (1991 on: "Ann M. Torr, Dover, r"). The
                  persons elected are marked with an asterisk, which the OCR gives as "*", "<diamond>",
                  a quotation mark or nothing. The district's own seat count, in the last brackets, is
                  the check on the marks: where the marks read equal the seats printed, the district is
                  `clean`; where they do not, it is not, and no decision rests on it.
    the Senate    the returns for State Senate, by district ("Twenty-First District:" and the
                  candidates, the highest vote the winner), and the page of the sitting Senate by
                  district ("FRANKLIN G. TORR / District No. 21"). The two are read side by side and the
                  row says whether they agree. The page prints two columns side by side on its last
                  line; the split of the two names is made only where each half is a name the returns
                  give for that district.
    mid-term      NOTHING. An edition printed at the start of a term does not show a seat that changed
                  hands by death, resignation or a special election, and neither does this table.
                  `mid_term_changes_not_shown` says so in the file. Anyone who took a seat later is not in
                  it, and a seat is known here only as the seat held at the start.

WHAT IS NEVER GUESSED. A row whose mark, name or district the OCR leaves unreadable is marked so
(`status`), and the district's count of marks against its seats is kept (`district_check`). A mark the OCR
turned into something else is counted only to say whether the district could be complete; it does not make
the candidate elected. Every row keeps the edition and the line number in its text and the line as printed.

1999-2000 is in the file for measuring only (`measuring_only`): its House and Senate are checked against
the people with a roll call in that term (generated/careers.json), which is the one independent check of
the OCR reading this table has for a term the sponsor route does not cover.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import difflib
import hashlib
import json
import re
from collections import Counter, defaultdict

import state_settings as ST

OUT = Path("generated/manual_seats.json")
MANUALS = Path("data/manuals")
SEATS = {"H": 400, "S": 24}
COUNTIES = list(ST.COUNTIES)
# year of the edition -> (term, year of the election it prints); 1999-2000 is for measuring.
EDITIONS = {"1989": ("1989-1990", 1988), "1991": ("1991-1992", 1990), "1993": ("1993-1994", 1992),
            "1995": ("1995-1996", 1994), "1997": ("1997-1998", 1996), "1999": ("1999-2000", 1998)}
MEASURING_ONLY = {"1999-2000"}
MID_TERM = ("An edition is printed at the start of a term. It shows who was elected and who sat at the "
            "start, not a seat that changed hands by death, resignation or special election later in "
            "the term; nobody who took a seat after the start is in this table.")
SOURCE = "Manual for the General Court (the State's, Internet Archive OCR text, data/manuals)"
ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
            "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
            "eighteenth", "nineteenth", "twentieth", "twenty-first", "twenty-second", "twenty-third",
            "twenty-fourth"]

SUFFIX = {"jr", "sr", "ii", "iii", "iv", "2nd", "3rd"}
MARKS = set("*♦•◆★^\"“")      # an asterisk as the OCR gives it
PARTY = re.compile(r"(?:[rdil1]|ind|n\.?l|i\.?a)(?:\s*(?:&|and)\s*(?:[rdil1]|ind|n\.?l|i\.?a)){0,2}", re.I)
VOTES = re.compile(r"\s+(?P<v>\d[\d,\.\s'()Xx\-]*)$")


def letters(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def collapse(s):
    return re.sub(r"\s+", " ", s or "").strip()


def county_of(word):
    k = letters(word)
    best = difflib.get_close_matches(k, [c.lower() for c in COUNTIES], n=1, cutoff=0.75)
    return best[0].title() if best else ""


def read_edition(year, root=MANUALS):
    """(path, [lines]) of one edition: exactly one text file in data/manuals/<year>/."""
    files = sorted((Path(root) / year).glob("*.txt"))
    if len(files) != 1:
        raise SystemExit(f"{Path(root) / year}: expected one .txt file, found {len(files)}.")
    return files[0], files[0].read_text(encoding="utf-8", errors="replace").split("\n")


# ------------------------------------------------------------------ the House

def district_no(text):
    """The district number in "District No. 1 1 (Alexandria" -- OCR spaces a two-digit number --
    or None where it cannot be read as digits (l and I are read as 1; nothing else is)."""
    m = re.match(r"\W*District\s+No\.?\s*([0-9lI!|][0-9lI!|\s]{0,4}?)\s*[\(\{\[]", text)
    if not m:
        m = re.match(r"\W*District\s+No\.?\s*([0-9lI][0-9lI]?)\s*$", text)
    if not m:
        return None
    d = re.sub(r"\s", "", m.group(1)).replace("l", "1").replace("I", "1").replace("!", "1").replace("|", "1")
    return str(int(d)) if d.isdigit() else None


def seats_of(header):
    """The seats a district header prints at its end, "(Meredith)(2)", or None where unreadable.

    The count is the last figure in the header. A run of l, I, | or ! standing alone in the last
    brackets is read as the figure 1 would be ("(l)" is 1, "(ll)" is 11); a lone other letter
    ("O)", "d)", "U)") is not read, and neither is a count of 0."""
    m = re.search(r"[\(\)XKMH\s]\s*([0-9lI|!]{1,3})\s*[\)\]\}]?\s*$", header)
    if not m:
        return None
    d = re.sub(r"\s", "", m.group(1))
    if not re.fullmatch(r"[0-9]+|[lI|!]+", d) and not re.fullmatch(r"[0-9lI|!]+", d):
        return None
    d = d.replace("l", "1").replace("I", "1").replace("|", "1").replace("!", "1")
    n = int(d)
    return n if 1 <= n <= 30 else None


def candidate(line):
    """(mark, name, party, town, votes, ok) of a candidate's line, or None where the line is not one.

    `mark` is "known" (an asterisk as the OCR gives it), "garbled" (some other leading character),
    or "". `ok` is False where name, party or town could not be told apart."""
    s = re.sub(r"^\s*\S{1,3}\s{4,}", "", line.rstrip())       # a footnote letter or a stray mark, then a wide gap
    s = collapse(s)
    if not s or re.match(r"(?i)^(total|district|the |for |recount)", s):
        return None
    m = re.match(r"^(?P<junk>[^A-Za-z]*)(?P<body>[A-Za-z].*)$", s)
    if not m:
        return None
    junk, body = m.group("junk").replace(" ", ""), m.group("body")
    v = VOTES.search(body)
    votes = re.sub(r"\D", "", v.group("v")) if v else ""      # some counties' returns print none
    body = body[:v.start()] if v else body
    body = re.sub(r"\([^)]*\)", "", body)                       # "(write-in)"
    body = body.replace(";", ",").strip(" ,.'\"*")
    body = re.sub(r"\b([rdil1])\s+and\s+([rdil1])\b", r"\1&\2", body)       # the 1989 returns: "r and d"
    # The OCR types a full stop for a comma. A word of three or more letters ends no abbreviation
    # ("Jr." and "St." have one lower-case letter, an initial none), so a full stop after one and
    # before a capital or a party is a comma: "Gene G. Chandler, r. Bartlett", "Dan Burnham. Dublin, d".
    body = re.sub(r"(?<=[a-z]{2})\.\s+(?=[A-Z])", ", ", body)
    body = re.sub(r"(?<=[A-Za-z])\.\s+(?=(?:[rdil1]|ind)(?:&(?:[rdil1]|ind))*\s*(?:[,.]|$))", ", ", body)
    body = re.sub(r"(?<=[A-Za-z]),?\s+(?=(?:[rdil1]|ind)(?:&(?:[rdil1]|ind))*$)", ", ", body)   # "Bedford r&d"
    body = re.sub(r"(?<=\.)\s+\.", "", body)
    parts = [p.strip(" .") if not re.fullmatch(r"(?i)(jr|sr)\.?", p.strip()) else p.strip()
             for p in body.split(",")]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return None
    name, rest = [parts[0]], []
    for p in parts[1:]:
        if letters(p) in SUFFIX and len(name) < 3 and not rest:
            name.append(p)
        else:
            rest.append(p)
    if len(rest) < 2 and rest:
        # the OCR often types a full stop for a comma: "Gene G. Chandler, r. Bartlett"
        again = [p.strip(" .") for p in re.split(r",|(?<=[a-z&])\.\s+(?=[A-Z])", ", ".join(rest)) if p.strip(" .")]
        if len(again) == 2:
            rest = again
    ok = len(rest) == 2
    party = town = ""
    if len(rest) == 2:
        a, b = rest
        pa, pb = bool(PARTY.fullmatch(a)), bool(PARTY.fullmatch(b))
        if pa and not pb:
            party, town = a, b
        elif pb and not pa:
            party, town = b, a
        else:
            ok = False
    elif len(rest) == 1:
        if PARTY.fullmatch(rest[0]):
            party = rest[0]
        else:
            town = rest[0]
        ok = False
    else:
        return None
    mark = "known" if any(c in MARKS for c in junk) else ("garbled" if junk else "")
    return {"mark": mark, "name": ", ".join(name), "party": party, "town": town,
            "votes": int(votes) if votes.isdigit() else None, "ok": ok and bool(letters(name[0]))}


def _not_a_candidate(line):
    """True for the rest of a district header: nothing marked and no party in it."""
    c = candidate(line)
    return c is None or (not c["mark"] and not c["party"])


def house_section(lines):
    """(first line, last line), 1-based, of the House returns of the general election."""
    start = next((i for i, l in enumerate(lines, 1)
                  if re.search(r"following\s+list\s+gives\s+the\s+names\s+of\s+the\s+candidates\s+for\s+"
                               r"(?:State\s+)?Representative", l)), None)
    if start is None:
        raise SystemExit("The House returns of the general election were not found.")
    end = next((i for i, l in enumerate(lines, 1)
                if i > start and re.search(r"COUNTY\s+OFFICES", l)), None)
    if end is None:
        raise SystemExit("The end of the House returns was not found.")
    return start, end


def parse_house(lines, edition, a, b):
    """([row], [district]): every candidate marked elected, and every district with its marks
    against its seats."""
    rows, districts = [], []
    county, cur = "", None
    i = a
    while i <= b:
        raw = lines[i - 1]
        s = collapse(raw)
        mc = re.match(r"^\W*([A-Za-z]{4,})\s+COUNTY\W*$", s, re.I)
        if mc and not re.search(r"(?i)OFFICES", s):
            c = county_of(mc.group(1))
            if c:
                county, cur = c, None
            i += 1
            continue
        if re.match(r"\W*District\s+No", s):
            head, j = s, i + 1
            # a header runs on until its seat count: "(... Second College Grant)(3)"
            while seats_of(head) is None and j <= b and j < i + 6 and lines[j - 1].strip() \
                    and _not_a_candidate(lines[j - 1]) and not re.match(r"\W*District\s+No", lines[j - 1]):
                head += " " + collapse(lines[j - 1])
                j += 1
            cur = {"county": county, "district": district_no(s), "seats": seats_of(head), "header": head[:160],
                   "line": i, "marked": 0, "garbled": 0, "rows": []}
            districts.append(cur)
            i = j
            continue
        if cur is not None:
            c = candidate(raw)
            if c is not None:
                cur["rows"].append((i, s, c))
                if c["mark"] == "known":
                    cur["marked"] += 1
                elif c["mark"] == "garbled":
                    cur["garbled"] += 1
        i += 1
    for d in districts:
        seats = d["seats"]
        if seats is None:
            d["check"] = "seats unreadable"
        elif d["marked"] == seats:
            d["check"] = "clean"
        elif d["marked"] < seats and d["marked"] + d["garbled"] == seats:
            d["check"] = "short by garbled marks"
        else:
            d["check"] = "marks differ from seats"
        if d["district"] is None:
            d["check"] = "district number unreadable"
        for ln, printed, c in d["rows"]:
            if c["mark"] == "known":
                status = "elected" if c["ok"] and d["district"] else "unreadable"
            elif c["mark"] == "garbled" and d["check"] == "short by garbled marks":
                status = "mark garbled, count agrees"
            else:
                continue
            rows.append({"county": d["county"], "district": d["district"] or "", "name": c["name"],
                         "town": c["town"], "party": c["party"], "votes": c["votes"], "status": status,
                         "district_check": d["check"], "seats": seats, "edition": edition, "line": ln,
                         "printed": printed[:120]})
    for d in districts:
        d.pop("rows")
    return rows, districts


# ------------------------------------------------------------------ the Senate

def ordinal_no(text):
    k = collapse(text).lower().replace(" ", "").replace("—", "-")
    k = re.sub(r"[^a-z\-]", "", k)
    best = difflib.get_close_matches(k, ORDINALS, n=1, cutoff=0.85)
    return ORDINALS.index(best[0]) + 1 if best else None


def senate_returns(lines):
    """([row], (a, b)): the winner of each of the 24 districts of the general election, by
    the highest vote, from "For State Senate: / First District: / Name, Town, party  votes"."""
    # the general election's, not the primary's: the last such heading before the House returns
    hs = house_section(lines)[0]
    starts = [i for i, l in enumerate(lines, 1) if i < hs and re.search(r"For\s+State\s+Senat", l)
              and any(re.match(r"\s*First\s+District", lines[k - 1]) for k in range(i, i + 3))]
    start = starts[-1] if starts else None
    if start is None:
        raise SystemExit("The State Senate returns were not found.")
    out, d, cands, end = [], None, [], start
    k = start
    while k <= len(lines):
        s = collapse(lines[k - 1])
        m = re.match(r"^([A-Za-z][A-Za-z\- ]{3,22})\s+District\s*:?$", s)
        if m and ordinal_no(m.group(1)):
            if d is not None:
                out.append((d, cands))
            d, cands = ordinal_no(m.group(1)), []
            k += 1
            continue
        if d is not None and (re.match(r"(?i)^(for |county officers)", s) or d == 24 and re.match(r"(?i)total vote", s)):
            out.append((d, cands))
            d = None
            end = k
            break
        if d is not None:
            c = candidate(lines[k - 1])
            if c is not None and not re.match(r"(?i)total", s):
                cands.append((k, s, c))
        k += 1
    if d is not None:
        out.append((d, cands))
    return out, (start, end)


def senate_page(lines):
    """[(district, name as printed, line of the name)] from the page of the sitting Senate:
    "FRANKLIN G. TORR" over "District No. 21". A line of two names over two district numbers is
    returned as ("22/23", the two names run together, line)."""
    # the page of the sitting Senate is the last thing before the Supreme Court's justices
    jl = next((i for i, l in enumerate(lines, 1) if re.search(r"JUSTICES\s+OF\s+THE\s+SUPREME\s+COURT", l)
               and i > 5000), None)
    if jl is None:
        raise SystemExit("The page of the sitting Senate was not found (no Justices heading after it).")
    run = [i for i in range(max(1, jl - 220), jl) if re.match(r"\s*District\s+No\.?\s*\d", lines[i - 1])]
    out = []
    for i in run:
        nums = re.findall(r"District\s+No\.?\s*(\d[\d\s]?\d?)", lines[i - 1])
        nums = [re.sub(r"\s", "", n) for n in nums]
        # the name is the nearest upper-case line above
        j = i - 1
        while j > 0 and not re.fullmatch(r"[A-Z][A-Z\.\,\'\-\s]{3,70}", lines[j - 1].strip().replace("Mc", "MC")):
            j -= 1
            if i - j > 6:
                j = 0
                break
        name = collapse(lines[j - 1]) if j else ""
        out.append((nums, name, j))
    return out


def similar(a, b):
    return difflib.SequenceMatcher(None, letters(a), letters(b)).ratio()


def fits(printed, other):
    """A name on the page of the sitting Senate against a name in the returns: the same
    surname and first name, or letters so near alike (OCR) that nothing else could be meant."""
    if person_key(printed) == person_key(other) and person_key(printed)[0]:
        return True
    if similar(printed, other) >= 0.85:
        return True
    (f1, s1), (f2, _s2) = person_key(printed), person_key(other)
    return bool(f1 and f1 == f2 and s1 and s1 in letters(other))


def build_senate(lines, edition):
    """[row] for the 24 districts. The page of the sitting Senate says who sat; the returns say
    the town and party and whether that name is a candidate in the district. A name on the page
    that no candidate of the district fits is `sources differ`, and so is a page that gives none."""
    rets, (ra, rb) = senate_returns(lines)
    page = senate_page(lines)
    cands = {d: [c for c in cs] for d, cs in rets}
    names = {}
    for nums, name, ln in page:
        if len(nums) == 1:
            names[int(nums[0])] = (name, ln, "")
        elif len(nums) == 2 and name:
            words = name.split()
            hit = None
            for k in range(1, len(words)):
                if letters(words[k]) in SUFFIX:
                    continue
                left, right = " ".join(words[:k]), " ".join(words[k:])
                if (any(fits(left, c[2]["name"]) for c in cands.get(int(nums[0]), []))
                        and any(fits(right, c[2]["name"]) for c in cands.get(int(nums[1]), []))):
                    hit = (left, right)
                    break
            for n, nm in zip(nums, hit or ("", "")):
                names[int(n)] = (nm, ln, "two names on one line, split where each half is a candidate of its district")
    rows = []
    for d in range(1, 25):
        pname, pline, how = names.get(d, ("", 0, ""))
        cs = [c for c in cands.get(d, []) if c[2]["name"]]
        top = max((c for c in cs if c[2]["votes"] is not None), key=lambda c: c[2]["votes"], default=None)
        hit = next((c for c in cs if pname and fits(pname, c[2]["name"])), None)
        if hit:
            status = "elected"
            ag = ("exact" if letters(pname) == letters(hit[2]["name"]) else "near")
            if top is not None and top is not hit:
                how = (how + "; " if how else "") + "the returns' highest vote as read is another candidate (OCR of the figures?)"
        elif pname:
            status, ag = "sources differ", "differs"
        elif top is not None:
            hit, status, ag = top, "returns only", "one source only"
        else:
            status, ag = "unreadable", "none"
        c = hit[2] if hit else {}
        rows.append({"district": str(d), "name": c.get("name") or (collapse(pname).title() if pname else ""),
                     "page_name": pname, "town": c.get("town", ""), "party": c.get("party", ""),
                     "votes": c.get("votes"), "agreement": ag, "status": status, "edition": edition,
                     "returns_line": hit[0] if hit else None, "page_line": pline or None,
                     "printed": hit[1][:120] if hit else "", "note": how})
    return rows, {"returns": [ra, rb]}



# ------------------------------------------------------------------ the table

def district_numbers(districts):
    """{county: {"read": n, "missing": [...], "repeated": [...]}}: whether a county's districts
    read as 1..n each once. A gap or a repeat is where the OCR lost or doubled a header."""
    by = defaultdict(list)
    for d in districts:
        by[d["county"]].append(d["district"])
    out = {}
    for county, nums in by.items():
        got = [int(n) for n in nums if n and n.isdigit()]
        top = max(got, default=0)
        out[county] = {"read": len(nums), "highest": top,
                       "missing": [n for n in range(1, top + 1) if n not in got],
                       "repeated": sorted(n for n, c in Counter(got).items() if c > 1),
                       "unreadable": sum(1 for n in nums if not (n and n.isdigit()))}
    return out


def coverage(terms):
    cov = {}
    for term, t in terms.items():
        h = [r for r in t["house"] if r["status"] == "elected"]
        clean = [r for r in h if r["district_check"] == "clean"]
        s = [r for r in t["senate"] if r["status"] == "elected"]
        cov[term] = {"house_rows": len(t["house"]), "house_elected": len(h), "house_of": SEATS["H"],
                     "house_in_clean_districts": len(clean),
                     "house_districts": len(t["house_districts"]),
                     "house_districts_clean": sum(1 for d in t["house_districts"] if d["check"] == "clean"),
                     "house_seats_printed": sum(d["seats"] or 0 for d in t["house_districts"]),
                     "house_districts_seats_unreadable": sum(1 for d in t["house_districts"] if d["seats"] is None),
                     "senate_rows": len(t["senate"]), "senate_elected": len(s), "senate_of": SEATS["S"]}
    return cov


def build(root=MANUALS):
    terms, editions = {}, {}
    for year, (term, election) in EDITIONS.items():
        path, lines = read_edition(year, root)
        a, b = house_section(lines)
        house, districts = parse_house(lines, year, a, b)
        senate, where = build_senate(lines, year)
        editions[year] = {"file": path.name, "term": term, "election": election,
                          "md5": hashlib.md5(path.read_bytes()).hexdigest(), "lines": len(lines),
                          "house_returns_lines": [a, b], "senate_returns_lines": where["returns"]}
        terms[term] = {"edition": year, "measuring_only": term in MEASURING_ONLY,
                       "house": house, "house_districts": districts,
                       "house_district_numbers": district_numbers(districts), "senate": senate}
    return {"format": 1,
            "what": ("Who was elected to each House seat and each Senate seat at the start of each term "
                     "from 1989-1990 to 1997-1998 (and 1999-2000, for measuring only), read from the Manual "
                     "for the General Court's general-election returns and its page of the sitting Senate. "
                     "Every row keeps its edition, its line in that edition's text and the line as printed."),
            "source": SOURCE, "mid_term_changes_not_shown": MID_TERM, "editions": editions,
            "terms": terms, "coverage": coverage(terms)}


def load(path=OUT):
    """The committed table, or None where it is not on this disk."""
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ------------------------------------------------------------------ measuring

def person_key(name):
    """(first word, surname) of a printed name, in letters: "Ann M. Torr" is ("ann", "torr");
    a suffix is dropped and the surname is the last word."""
    words = [w for w in re.split(r"[\s,]+", name or "") if w]
    words = [w for w in words if letters(w) not in SUFFIX]
    if len(words) < 2:
        return "", letters(words[0]) if words else ""
    return letters(words[0]), letters(words[-1])


def names_agree(a, b):
    """The same person by name: the surname and the first name agree, a lone initial not enough."""
    (fa, sa), (fb, sb) = person_key(a), person_key(b)
    if not sa or sa != sb:
        return False
    if len(fa) < 2 or len(fb) < 2:
        return False
    return fa == fb or similar(fa, fb) >= 0.85


def names_agree_loose(a, b):
    """For MEASURING only (never for a decision): the same surname, and some given name or
    initial of one fits some given name or initial of the other -- "A. Gibb Dodge" and "Arthur G.
    Dodge, Jr.". A hyphen the journal broke a word at ("Ho- ward") is closed first."""
    def parts(n):
        w = [x for x in re.split(r"[\s,]+", re.sub(r"-\s+", "", n or "")) if x]
        w = [letters(x) for x in w if letters(x) and letters(x) not in SUFFIX]
        return (w[:-1], w[-1]) if len(w) > 1 else ([], w[0] if w else "")
    (ga, sa), (gb, sb) = parts(a), parts(b)
    if not sa or not sb or not (sa == sb or similar(sa, sb) >= 0.85):
        return False
    return any(x == y or (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y))
               or (len(x) > 2 and len(y) > 2 and similar(x, y) >= 0.85) for x in ga for y in gb)


EDITIONS_BY_TERM = {t: y for y, (t, _e) in EDITIONS.items()}


def measure_house(doc, root=Path("data/unh/roster")):
    """{term: {...}}: the Manual's House rows against the House Journal's CALL OF THE ROLL of the
    same term (the volume printed at the start of it), seat by seat. Nothing is fixed: every name
    only one of them has is listed with its line in each."""
    import past_roll as ROLL
    out = {}
    for fn, (term, year) in sorted(ROLL.VOLUMES.items(), key=lambda kv: kv[1][1]):
        p = Path(root) / fn
        if not p.exists() or term not in doc["terms"] or year != int(EDITIONS_BY_TERM[term]):
            continue
        by_roll, mine = defaultdict(list), defaultdict(list)
        for en in ROLL.read(p):
            by_roll[(en["county"].title(), en["district"].lstrip("0"))].append(en)
        for r in doc["terms"][term]["house"]:
            if r["status"] == "elected":
                mine[(r["county"], r["district"])].append(r)
        agree, only_roll, only_manual = 0, [], []
        for key in sorted(set(by_roll) | set(mine)):
            left = list(mine.get(key, []))
            for en in by_roll.get(key, []):
                hit = next((r for r in left if names_agree_loose(r["name"], en["name"])), None)
                if hit:
                    left.remove(hit)
                    agree += 1
                else:
                    only_roll.append({"seat": list(key), "roll_name": en["name"], "roll_line": en["line"],
                                      "roll_file": fn})
            for r in left:
                only_manual.append({"seat": list(key), "manual_name": r["name"], "manual_line": r["line"],
                                    "district_check": r["district_check"]})
        out[term] = {"roll_file": fn, "roll_names": sum(len(v) for v in by_roll.values()),
                     "manual_names": sum(len(v) for v in mine.values()), "agree": agree,
                     "only_in_roll": only_roll, "only_in_manual": only_manual}
    return out


def measure_senate(doc, past):
    """{term: {...}}: the Manual's senators against the senators generated/past_roster.json placed
    from the bills' own sponsor rows and the district each bill printed for them."""
    out = {}
    for term, t in doc["terms"].items():
        if t["measuring_only"]:
            continue
        rows = [r for r in past["rows"] if r["term"] == term and r["chamber"] == "S"]
        agree, differ, silent, only_past = 0, [], [], []
        seen = set()
        for s in t["senate"]:
            if s["status"] != "elected":
                continue
            printed = [r for r in rows if any(x["district"] == s["district"] for x in r["seats"])]
            if not printed:
                silent.append({"district": s["district"], "manual_name": s["name"], "manual_line": s["returns_line"]})
                continue
            for r in printed:
                seen.add(r["person"])
                if names_agree_loose(s["name"], r["name"]):
                    agree += 1
                else:
                    differ.append({"district": s["district"], "manual_name": s["name"],
                                   "manual_line": s["returns_line"], "sponsor_route_name": r["name"],
                                   "employee": r["person"],
                                   "bills_printing_that_district": sum(x["bills"] for x in r["seats"] if x["district"] == s["district"])})
        for r in rows:
            if r["person"] not in seen and r["seats"]:
                only_past.append({"employee": r["person"], "name": r["name"],
                                  "districts": [x["district"] for x in r["seats"]]})
        out[term] = {"manual_senators": sum(1 for s in t["senate"] if s["status"] == "elected"),
                     "agree": agree, "name_differs": differ, "manual_district_no_printed_row": silent,
                     "sponsor_route_senator_not_in_manual": only_past}
    return out


def measure_1999(doc, careers, people):
    """The 1999 edition against the people with a recorded roll call in 1999-2000
    (generated/careers.json): a Manual name is matched to one of them by name and chamber."""
    t = doc["terms"]["1999-2000"]
    pool = []
    for k, v in careers.items():
        if "1999-2000" not in v["terms"]:
            continue
        emp = (v.get("employee_nos") or [k])[0]
        names = people.names(emp)
        if not names and v.get("last"):
            names = [(v["last"], v.get("first", ""))]
        pool.append({"employee": emp, "names": [f"{f} {l}".strip() for l, f in names],
                     "chambers": v["by_term"]["1999-2000"]["chambers"]})
    out = {"careers_in_term": len(pool), "careers_without_a_name": sum(1 for p in pool if not p["names"])}
    for ch, rows in (("H", [r for r in t["house"] if r["status"] == "elected"]),
                     ("S", [r for r in t["senate"] if r["status"] == "elected"])):
        used, hits, miss = set(), 0, []
        for r in rows:
            cand = [p for p in pool if ch in p["chambers"] and any(names_agree_loose(r["name"], n) for n in p["names"])]
            if len(cand) == 1:
                hits += 1
                used.add(cand[0]["employee"])
            else:
                miss.append({"name": r["name"], "line": r.get("line") or r.get("returns_line"),
                             "matches": [c["employee"] for c in cand]})
        left = [p for p in pool if ch in p["chambers"] and p["employee"] not in used]
        out[ch] = {"manual_rows": len(rows), "matched_to_one_career": hits, "manual_not_matched": miss,
                   "careers_not_in_manual": [{"employee": p["employee"], "names": p["names"]} for p in left]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write " + OUT.as_posix())
    ap.add_argument("--out", default=str(OUT), help="with --apply: write here instead (a scratch tree)")
    ap.add_argument("--measure", action="store_true", help="also measure against the call of the roll")
    ap.add_argument("--measure-out", help="write the disagreements to this JSON file")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    doc = build()
    print(f"{'term':<11}{'House':>7}{'/400':>6}{'clean':>7}{'dist':>6}{'dclean':>7}{'seats':>7}{'unrd':>6} |{'Senate':>7}{'/24':>5}")
    for term, c in doc["coverage"].items():
        print(f"{term:<11}{c['house_elected']:>7}{'':>6}{c['house_in_clean_districts']:>7}{c['house_districts']:>6}"
              f"{c['house_districts_clean']:>7}{c['house_seats_printed']:>7}{c['house_districts_seats_unreadable']:>6} |"
              f"{c['senate_elected']:>7}")
    if a.measure:
        import past_members
        import past_sponsors as PSP
        m = {"house_vs_call_of_the_roll": measure_house(doc)}
        for term, v in m["house_vs_call_of_the_roll"].items():
            print(f"House {term} vs the call of the roll: roll {v['roll_names']}, manual {v['manual_names']}, "
                  f"agree {v['agree']}, only in roll {len(v['only_in_roll'])}, only in manual {len(v['only_in_manual'])}")
        past = json.loads(Path("generated/past_roster.json").read_text(encoding="utf-8"))
        m["senate_vs_sponsor_route"] = measure_senate(doc, past)
        for term, v in m["senate_vs_sponsor_route"].items():
            print(f"Senate {term} vs the sponsor route: manual {v['manual_senators']}, agree {v['agree']}, "
                  f"name differs {len(v['name_differs'])}, no printed row {len(v['manual_district_no_printed_row'])}, "
                  f"sponsor-route senator not in manual {len(v['sponsor_route_senator_not_in_manual'])}")
        people = PSP.People(PSP.read_legislators(), past_members.roster(PSP.PAST_MEMBERS))
        careers = json.loads(Path("generated/careers.json").read_text(encoding="utf-8"))
        m["manual_1999_vs_careers"] = measure_1999(doc, careers, people)
        c = m["manual_1999_vs_careers"]
        print(f"1999-2000 vs generated/careers.json ({c['careers_in_term']} careers, {c['careers_without_a_name']} unnamed): "
              f"House {c['H']['matched_to_one_career']}/{c['H']['manual_rows']}, Senate {c['S']['matched_to_one_career']}/{c['S']['manual_rows']}")
        if a.measure_out:
            Path(a.measure_out).write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.apply:
        short = [t for t, c in doc["coverage"].items()
                 if c["house_elected"] < 300 or c["senate_elected"] < 20]
        if short:
            sys.exit(f"{short} read far fewer seats than a legislature has; nothing is written.")
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwritten {out}")


if __name__ == "__main__":
    main()
