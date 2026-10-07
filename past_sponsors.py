#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-26.5
"""
Who the General Court's own sponsor record says put their name to each bill.

    python3 past_sponsors.py            # what the record gives, term by term; writes nothing
    python3 past_sponsors.py --check    # 2023-2024 against the saved pages, every exception named
    python3 past_sponsors.py --apply    # writes past_sponsors.json

No network. It reads the PastSponsors and PastLegislation views fetch_past_db.py dumped into
db/past/, the legislators table in db/Legislators.psv, data/bills.json, and -- for the check
-- the pages fetch_legislation.py saved under legislation/.

WHAT THE RECORD IS

PastSponsors holds one row per sponsor per LSR for 1989 to 2024: the session year, the LSR
number, the member's employee number, whether they are the prime sponsor, the order they
signed in, and whether they withdrew. It is keyed by LSR, not by bill number.

HOW A ROW REACHES A BILL. By the LSR the site already stores for the bill (data/bills.json
lsr_year and lsr_num), and by nothing else. A bill number repeats every term and an LSR can
change its number between years, so (term, bill) finds the wrong bill: 2011 SR 5 would be
given Sen. Chuck Morse. PastLegislation's own bill number for that LSR is read only as a
guard -- where it names another bill the row is refused and counted. Withdrawn sponsors are
kept apart; only a live row is a sponsor.

WHO AN EMPLOYEE NUMBER IS. The site names a member by the id their roll calls are cast
under: the PersonID where db/Legislators.psv has one for that employee number, the employee
number itself where it has none -- every ballot in data/member_votes.json is under one or
the other, never both. A number that maps to no id the site has anyone under stays
unlinked; it is never matched to somebody by name. A member who changed chambers has two
numbers, and member_links.py joins the earlier one to the sitting member when the build
runs, so a row under the earlier number reaches the member's own page through it.

WHAT IS MERGED, AND WHERE. Only 2023-2024, where the site's list came from the bill status
page and this record was measured against the bills' printed sponsor lines first
(--check). Against the 1,938 saved pages of that term it is the printed list on every bill
but the ones --check names, and the status page was not: it left Rep. Steve Shurtleff off
29 bills, Rep. Kimberly Abare off 4 and Rep. Lorrie J. Carey off 4, made Rep. Mark Paige
the prime sponsor of 2023 HB 32 and Rep. Terry Roy the only sponsor of 2024 HB 1713 --
both are Shurtleff's -- listed Rep. Dawn Johnson on 2023 HB 104, which neither the record
nor the bill names, and carried no link for 5,900 of its 10,310 names. build_site_v2 and
build_exports call merge_into(), so the page and the download agree.

WHAT IS FILLED, AND WHERE (1 October 2026). Every other past term keeps the sponsor line
of its own text, and takes the record's list ONLY FOR A BILL NOTHING ELSE NAMES A SPONSOR
FOR: no row in data/sponsors.json and none read off its text. 918 bills of 1989-2022 were
that -- a bill with no saved page, mostly -- beside the measures build_data adds from the
database, which have no page either. The person decided it: sponsors are filled in
wherever the records have them. Never over a list: a bill whose text names anybody keeps
its text's.

WHAT A FILLED ROW IS WORTH, measured on the bills that do have a page, where the record's
rows can be held to the printed line (each term's 1,400 to 1,900 bills):
  - the people: 99.3% or more of a term's live rows are a printed sponsor, by surname, in
    every term, and the record's prime is the first name printed on all but seven bills
    of a term at most;
  - the chamber: the one the row is given -- the one its number voted in that term, else
    the legislators table's, else the General Court's list of members -- is the printed
    one on 99.4% or more of a term's rows, and where it is not, the print says "Rep." of
    a Senate district, or "Sen." of a House one, or the number has no chamber on file
    and the row carries none;
  - the link: where the site has a member under the number, the site's own name for them
    fits the printed surname on all but sixteen of a term's rows at most, and most of
    those are the print's spelling ("Rep. Paluzzo" for Palazzo);
  - AND ONE TERM IS SHORT. In 1999-2000 the record lists fewer sponsors than the bill
    prints: 156 of 1,586 bills differ, by 337 printed names the record does not have
    (HB 68 of 1999 prints seven sponsors and the record holds its prime alone). The
    prime is still the first printed on 1,581. So a filled list of that term names the
    prime and may not name every co-sponsor; it is for the Clerk's list, and the page of
    each filled bill of that term says so (SHORT_TERMS).
A filled row says where it is from (source) and that its seat is the record's
(seat_source), which is a chamber and no district: the record holds none, and the roster's
is today's. Before 1999 a row has no party either -- no roll call of the term exists to
take one from -- and is linked only where its number is one a later roll call was cast
under.

A BILL WHERE THE RECORD AND THE PRINT DISAGREE is published as the page prints it: the
sponsors text_sponsors.py read off that bill's text. --check names every one.

WHAT A PUBLISHED ROW SAYS (records). The name, party and link are those of the status
page's row for the same member where one pairs. The party of a row none pairs with is the
one the member's own ballots carry that term: the status page left Shurtleff and Abare off,
and their 30 restored rows were published with no party. The chamber is the one the bill
prints, then the one the member voted in that term, and the status page's only after both,
because the status page files six sitting senators under the House.

A ROW PAIRED ONLY BY ELIMINATION AT ANOTHER SEAT IS NOT LINKED. Where the only printed
sponsor left over is at another seat than the one the site gives the only row left over,
the site's name for the number is not the one the bill prints, and the row is shown as the
page prints it, linked to nobody. Employee 377080 was that case -- every bill prints "Rep.
Carey", and the site named the number H. Robert Menear of Strafford 25, a vote-pattern
guess in member_party.json -- until member_corrections.json named her Rep. Lorrie J. Carey
of Merrimack 1 on 26 September. Her rows now pair by name and link to her own page.
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

import member_links as ML
import names
import past_members
import text_sponsors as TS

PAST = Path("db/past")
LEGISLATORS = Path("db/Legislators.psv")
COLUMNS = Path("db/_columns.json")
BILLS = Path("data/bills.json")
SPONSORS = Path("data/sponsors.json")
VOTES = Path("data/member_votes.json")
ROSTER = Path("data/legislators.json")
PAST_MEMBERS = Path("past_members.json")
OUT = Path("past_sponsors.json")
SOURCE = "General Court sponsor record"
# The terms whose published sponsor lists are this record's, over the list the site had.
# Every other past term is FILLED: the record's list for a bill no other source names a
# sponsor for, and for no other bill (see the module docstring).
MERGED = ("2023-2024",)
# THE TERM WHOSE RECORD IS SHORT OF CO-SPONSORS (the docstring's "AND ONE TERM IS SHORT").
# On the bills that have a page, 156 of 1,586 print sponsors the record does not hold. On
# the filled ones it is worse. The review of 1 October 2026 held the fills to the House
# Journal's lists of bills introduced, the only print there is for a bill with no page,
# and counted 15 of the 41 filled bills of 1999-2000 the journals list short of printed
# co-sponsors, 11 of them of every Senate co-sponsor: HCR 34 of 2000 prints ten sponsors
# where the record holds its prime alone (journals/2000/HJ008.txt, line 3874). In no
# other term did it find a fill short by more than a name. The prime is right, and the
# names given are sponsors; the list is not
# known to be whole. build_site_v2 says so in a note on each filled bill of these terms,
# and build_exports in the table's description.
SHORT_TERMS = ("1999-2000",)
SUFFIXES = TS.SUFFIXES


# ------------------------------------------------------------------ reading the dump

def read_view(name, root=PAST):
    """The rows of one Past* view, keyed by the columns db/past/_manifest.json names.

    The .psv files carry no header; the manifest is the only statement of their column
    order, so a line with another number of fields stops the run rather than shifting
    every value one column along."""
    man = json.loads((Path(root) / "_manifest.json").read_text(encoding="utf-8"))
    ent = man[name]
    cols, path = ent["columns"], Path(root) / ent["file"]
    out = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            parts = line.rstrip("\r\n").split("|")
            if len(parts) != len(cols):
                raise SystemExit(f"{path} line {n}: {len(parts)} fields where "
                                 f"{root}/_manifest.json names {len(cols)}")
            out.append(dict(zip(cols, parts)))
    return out


def read_legislators(path=LEGISLATORS, columns=COLUMNS):
    """[row] of db/Legislators.psv, by the column order db/_columns.json records."""
    cols = json.loads(Path(columns).read_text(encoding="utf-8"))["Legislators"]
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\r\n").split("|")
            if len(parts) == len(cols):
                out.append({k: v.strip() for k, v in zip(cols, parts)})
    return out


def bill_no(s):
    """"HB  0169" and "HB169" are both HB169."""
    m = re.match(r"^([A-Z]+)0*(\d+)$", re.sub(r"\s+", "", (s or "").upper()))
    return f"{m.group(1)}{int(m.group(2))}" if m else ""


def _flag(v):
    return (v or "").strip().lower() in ("1", "true")


def join(bills, sponsor_rows, legislation_rows):
    """({term: {bill: {"lsr", "rows"}}}, tally).

    rows are every sponsor row of the bill's stored LSR in the order the record numbers
    them, each {"employee", "sequence", "prime", "withdrawn"}."""
    tally = Counter()
    by_lsr = defaultdict(list)
    for r in sponsor_rows:
        try:
            key = (int(r["SessionYear"]), int(r["lsr"]))
        except ValueError:
            tally["sponsor rows with no year or LSR"] += 1
            continue
        emp = (r.get("employeeNo") or "").strip()
        if not emp:
            tally["sponsor rows with no employee number"] += 1
            continue
        try:
            seq = int(r.get("LSRSequenceNo") or 0)
        except ValueError:
            seq = 0
        by_lsr[key].append({"employee": emp, "sequence": seq,
                            "prime": _flag(r.get("PrimeSponsor")),
                            "withdrawn": _flag(r.get("SponsorWithdrawn"))})
    named = {}
    for r in legislation_rows:
        try:
            named[(int(r["SessionYear"]), int(r["LSR"]))] = bill_no(r.get("CondensedBillNo"))
        except ValueError:
            continue
    out, used = defaultdict(dict), set()
    for term, recs in bills.items():
        for bid, b in recs.items():
            try:
                key = (int(b.get("lsr_year")), int(b.get("lsr_num")))
            except (TypeError, ValueError):
                tally["bills with no stored LSR"] += 1
                continue
            rows = by_lsr.get(key)
            if not rows:
                tally["bills whose LSR has no sponsor row"] += 1
                continue
            if named.get(key) and named[key] != bid:
                # The guard: PastLegislation files this LSR under another number.
                tally["bills whose LSR PastLegislation files under another number"] += 1
                continue
            used.add(key)
            out[term][bid] = {"lsr": f"{key[0]}-{key[1]:04d}",
                              "rows": sorted(rows, key=lambda x: (x["sequence"], not x["prime"]))}
            tally["bills joined"] += 1
    tally["sponsor rows on no bill of the site"] = sum(
        len(v) for k, v in by_lsr.items() if k not in used)
    return dict(out), tally


# ------------------------------------------------------------------ who a number is

def _split_last(last):
    """Surname keys: "Calvert (Ziegra)" is Calvert and Ziegra; "Garrish-Thomas" is both
    halves and the whole; "Barnes, Jr." is Barnes."""
    last = re.sub(r",?\s*\b(?:jr|sr|ii|iii|iv)\b\.?", "", last or "", flags=re.I)
    keys = {TS.letters(re.sub(r"\(.*?\)", "", last))}
    keys |= {TS.letters(x) for x in re.findall(r"\((.*?)\)", last)}
    keys |= {TS.letters(w) for w in re.split(r"[\s\-()]+", last) if len(TS.letters(w)) >= 3}
    return {k for k in keys if k}


class People:
    """Everything the files on disk say about an employee number: the site's id for it,
    the names each source gives it, the chamber it voted in and the party its ballots carry
    each term, and its roll-call seat. votes and roster may be None where a caller needs
    names only."""

    def __init__(self, legislators, past_members=None, votes=None, roster=None):
        self.emp2pid, self.leg = {}, {}
        for r in legislators:
            emp = r.get("Employeeno") or ""
            if emp:
                self.emp2pid[emp] = r.get("PersonID") or ""
                self.leg[emp] = (r.get("LastName") or "", r.get("FirstName") or "",
                                 (r.get("LegislativeBody") or "")[:1].upper())
        # past_members.roster()'s shape: {Employeeno: {name: "Last, First", chamber, ...}}.
        self.pm = {}
        for emp, rec in (past_members or {}).items():
            last, _, first = (rec.get("name") or "").partition(",")
            if last.strip():
                self.pm[str(emp)] = (rec.get("chamber") or "", last.strip(), first.strip())
        self.vote, self.bodies, self.parties = {}, defaultdict(Counter), defaultdict(Counter)
        for v in votes or ():
            vid = str(v.get("member_id") or "")
            if not vid:
                continue
            if vid not in self.vote:
                self.vote[vid] = (TS.vote_name(v.get("name")), v.get("label") or "")
            y = str(v.get("year") or "")
            if not y.isdigit():
                continue
            if v.get("body") in ("H", "S"):
                self.bodies[(vid, TS.term_of(y))][v["body"]] += 1
            # build_data writes X where it knows no party; that is not one.
            p = (v.get("party") or "").strip()[:1].upper()
            if p and p in "RDILU":
                self.parties[(vid, TS.term_of(y))][p] += 1
        self.roster = {str(m.get("id")): m for m in (roster or ())}
        self.known = set(self.vote) | set(self.roster)

    def vid(self, emp):
        """The id this number's ballots are cast under, known to the site or not."""
        return self.emp2pid.get(emp) or emp

    def site_id(self, emp):
        """The site's id for this number, or "" where the site has nobody under it."""
        v = self.vid(emp)
        return v if v in self.known else ""

    def names(self, emp):
        """[(last, first)] from every source that names the number."""
        out = []
        v = self.vid(emp)
        if v in self.vote and self.vote[v][0]:
            last, first, _suffix = self.vote[v][0]
            out.append((last, first))
        if v in self.roster:
            last, first = ML.split_name(self.roster[v].get("name"))
            out.append((self.roster[v].get("last") or last, self.roster[v].get("first") or first))
        if emp in self.leg:
            out.append(self.leg[emp][:2])
        if emp in self.pm:
            out.append(self.pm[emp][1:])
        return out

    def surnames(self, emp):
        keys = set()
        for last, _first in self.names(emp):
            keys |= _split_last(last)
        return keys

    def firsts(self, emp):
        return [first for _last, first in self.names(emp) if first]

    def site_name(self, emp):
        """"Steve Shurtleff": the name the site's own record of the number gives -- the
        ballots' name, which member_corrections.json has been applied to -- else the
        legislators table's, else the General Court's list of members."""
        v = self.vid(emp)
        if v in self.vote and self.vote[v][0]:
            last, first, suffix = self.vote[v][0]
            return " ".join(x for x in (first, last, suffix) if x)
        for last, first in self.names(emp):
            return " ".join(x for x in (first, last) if x)
        return ""

    def voted_chamber(self, emp, term):
        """The chamber the number's ballots were cast in that term -- the one most of them
        were, for a member who changed chambers mid-term -- or "" where it cast none."""
        c = self.bodies.get((self.vid(emp), term))
        return c.most_common(1)[0][0] if c else ""

    def party(self, emp, term):
        """The party the number's ballots carry that term, most of them where they differ,
        or "" where none carries one."""
        c = self.parties.get((self.vid(emp), term))
        return c.most_common(1)[0][0] if c else ""

    def chamber(self, emp, term):
        """The chamber the number voted in that term, else the one the tables give it."""
        voted = self.voted_chamber(emp, term)
        if voted:
            return voted
        r = self.roster.get(self.vid(emp))
        if r and (r.get("chamber") or "")[:1] in ("H", "S"):
            return r["chamber"][:1]
        if emp in self.leg and self.leg[emp][2] in ("H", "S"):
            return self.leg[emp][2]
        return self.pm.get(emp, ("",))[0]

    def seat(self, emp):
        """(county, number) of the number's roll-call label -- one per member, the last."""
        v = self.vid(emp)
        return ML.seat(self.vote[v][1]) if v in self.vote else (None, None)


def load_people(with_votes=True):
    """People from the files on disk; any that is missing is simply not a source."""
    def js(p, default):
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default
    legs = read_legislators() if LEGISLATORS.exists() and COLUMNS.exists() else []
    return People(legs, past_members.roster(PAST_MEMBERS),
                  js(VOTES, []) if with_votes else None,
                  js(ROSTER, []) if with_votes else None)


def load_record(bills):
    """(joined, people) for text_sponsors.py -- the same rows past_sponsors.json lists,
    read from the dump rather than from the file, so the two steps need no order between
    them -- or None where the dump or the legislators table is not on disk, which leaves
    every sponsor to the printed line alone."""
    if not all(Path(p).exists() for p in (PAST / "_manifest.json", LEGISLATORS, COLUMNS)):
        return None
    joined, _ = join(bills, read_view("PastSponsors"), read_view("PastLegislation"))
    return joined, load_people(with_votes=False)


# ------------------------------------------------------------------ against the page

def _fits(piece_key, keys):
    return bool(piece_key) and any(
        k == piece_key or (len(k) >= 4 and piece_key.endswith(k))
        or (len(piece_key) >= 4 and k.endswith(piece_key)) for k in keys)


def _initials(sp):
    """The given names or initials printed before a surname: "M." of "M. Paige"."""
    return [w for w in sp["words"][:-1] if len(TS.letters(w)) <= 1] or \
        [w for w in sp["words"][:1] if len(sp["words"]) > 1]


def _same_seat(sp, seat):
    county, number = seat
    if not sp.get("district") or number is None:
        return False
    if str(number) != str(int(sp["district"])):
        return False
    return sp["chamber"] == "S" or (county or "") == (sp.get("county") or "")


def _seat_of(sp):
    return (sp.get("chamber"), sp.get("county") or "", sp.get("district") or "")


def pair(rows, pieces, people, term, others=None):
    """([(row, piece index, how)], rows left over, piece indexes left over, [twice printed]).

    Each printed sponsor is paired with the one live row whose number any source names by
    that surname -- an initial, then the chamber, then the seat deciding between two.

    Once every name has been tried, a single row left over is paired with a single printed
    sponsor left over, BUT ONLY IF THE PRINTED SURNAME IS NOBODY ELSE'S. `others(emp)` gives
    the surnames of every other number in the term's record: 2023 HB 10 prints "Rep. Hoell,
    Merr. 27" where the record lists Mark Alliegro, and Hoell is a member in his own right,
    so that is a disagreement and not a member printed under another name. `how` says
    which: "name", or "elimination" with whether the printed seat is the one the site
    gives the number.

    A sponsor printed twice (2024 SB 217 prints "Sen. Perkins Kwoka, Dist 21" twice, where
    the record has her once live and once withdrawn) is one sponsor, not a second one the
    record lacks."""
    free = list(range(len(rows)))
    pairs, lone, twice = [], [], []
    for i, sp in enumerate(pieces):
        pk = TS._page_key(sp)
        cands = [j for j in free if _fits(pk, people.surnames(rows[j]["employee"]))]
        if len(cands) > 1:
            ini = _initials(sp)
            if ini:
                c2 = [j for j in cands if any(TS.given_fits(ini, f)
                                              for f in people.firsts(rows[j]["employee"]))]
                cands = c2 or cands
        if len(cands) > 1 and sp.get("chamber"):
            c2 = [j for j in cands if people.chamber(rows[j]["employee"], term) == sp["chamber"]]
            cands = c2 or cands
        if len(cands) > 1:
            c2 = [j for j in cands if _same_seat(sp, people.seat(rows[j]["employee"]))]
            cands = c2 or cands
        if len(cands) == 1:
            pairs.append((rows[cands[0]], i, "name"))
            free.remove(cands[0])
        elif any(TS._page_key(pieces[k]) == pk and _seat_of(pieces[k]) == _seat_of(sp)
                 for _r, k, _h in pairs):
            twice.append(i)
        else:
            lone.append(i)
    if len(free) == 1 and len(lone) == 1:
        r, i = rows[free[0]], lone[0]
        pk = TS._page_key(pieces[i])
        if not (others and _fits(pk, others(r["employee"]))):
            seat = people.seat(r["employee"])
            pairs.append((r, i, "elimination, seat agrees" if _same_seat(pieces[i], seat)
                          else "elimination, seat differs"))
            free, lone = [], []
    return pairs, [rows[j] for j in free], lone, twice


def verdict(rows, pieces, people, term, others=None):
    """(state, pairs, notes, tally): the record against the print.

    state is "agrees" when every live row is printed, every printed sponsor is a live row,
    and the record's prime sponsor is the first name printed; else "differs", and the notes
    say why. tally counts the three parts of that for the bar --check reports."""
    live = [r for r in rows if not r["withdrawn"]]
    pairs, lone_rows, lone_pieces, twice = pair(live, pieces, people, term, others)
    why = []
    for r in lone_rows:
        why.append(f"the record lists {r['employee']} ({people.site_name(r['employee']) or 'no name'})"
                   ", and the page prints nobody it can be")
    for i in lone_pieces:
        why.append(f"the page prints {pieces[i]['printed']!r}, and the record lists nobody it can be")
    primes = [r for r in live if r["prime"]]
    at = {id(r): i for r, i, _how in pairs}
    first = len(primes) == 1 and at.get(id(primes[0])) == 0
    if len(primes) != 1:
        why.append(f"the record marks {len(primes)} live prime sponsors")
    elif id(primes[0]) in at and at[id(primes[0])] != 0:
        why.append(f"the record's prime, {people.site_name(primes[0]['employee'])}, is printed "
                   f"at place {at[id(primes[0])] + 1}")
    tally = Counter({"live": len(live), "live printed": len(live) - len(lone_rows),
                     "printed": len(pieces) - len(twice),
                     "printed live": len(pieces) - len(twice) - len(lone_pieces),
                     "prime printed first": int(first)})
    if why:
        return "differs", pairs, why, tally
    notes = [f"{r['employee']} printed as {pieces[i]['printed']!r}; the site names the number "
             f"{people.site_name(r['employee']) or 'nobody'}"
             + ("" if how == "elimination, seat agrees" else
                f" at {'/'.join(str(x) for x in people.seat(r['employee']) if x) or 'no seat'}"
                ", so it is shown as printed and not linked")
             for r, i, how in pairs if how != "name"]
    notes += [f"{pieces[i]['printed']!r} is printed twice" for i in twice]
    return "agrees", pairs, notes, tally


# ------------------------------------------------------------------ what is published

def _db_pairs(rows, db, people):
    """{employee: the data/sponsors.json record of the same member}: by the employee
    number the status page's link carries, then by first and last name among the bill's
    own rows. Only used for the name, the party and the link the record already had."""
    out, left = {}, [r for r in db if r.get("name")]
    emps = {r["employee"] for r in rows}
    for d in list(left):
        e = str(d.get("member_id") or "")
        if e in emps and e not in out:
            out[e] = d
            left.remove(d)
    for d in left:
        full = TS.letters(d["name"])
        c = [e for e in emps - set(out)
             if any(TS.letters(f + l) == full or TS.letters((f.split() or [""])[0] + l) == full
                    for l, f in people.names(e) if f)]
        if len(c) == 1:
            out[c[0]] = d
    return out


def records(rows, db, people, term, pieces=None, pairs=None):
    """The published list: data/sponsors.json's shape, one record per live row.

    In the order the page prints them where there is a page (the record's prime is the
    first printed, or the bill would not be here), else the record's own order with the
    prime first.

    THE CHAMBER IS THE ONE THE BILL PRINTS, then the one the member voted in that term, and
    the status page's last -- for a resolution with no page, the ballots' first. The status
    page files six sitting senators under the House (Donna Soucy, Jeb Bradley, Carrie
    Gendreau, Lou D'Allesandro, Shannon Chandley, Rebecca Whitley), and taken first it put
    "Sen. Donna Soucy (D - SD18)" under Representatives on 34 rows that seat_into cannot
    date: resolutions with no text, and Senate bills that print two Soucys.

    A ROW NO STATUS-PAGE ROW PAIRS WITH takes its party from the member's own ballots that
    term, and is labelled as names.legislator labels a member: "Rep. Steve Shurtleff (D -
    Merr 15)", with the seat the bill prints, and no seat where there is no page, because a
    label states the seat held when the record was made. Of the rows the status page left
    off, 26 of Shurtleff's and 4 of Kimberly Abare's were published with no party at all."""
    live = [r for r in rows if not r["withdrawn"]]
    printed = {id(r): (i, how) for r, i, how in (pairs or ())}
    if printed:
        live.sort(key=lambda r: printed[id(r)][0])
    else:
        live.sort(key=lambda r: (not r["prime"], r["sequence"]))
    have = _db_pairs(live, db or [], people)
    out = []
    for n, r in enumerate(live):
        emp, d = r["employee"], have.get(r["employee"]) or {}
        i, how = printed.get(id(r), (None, ""))
        sp = pieces[i] if i is not None else None
        sid = people.site_id(emp)
        rec = {"member_id": sid, "employee": emp,
               "name": d.get("name") or people.site_name(emp),
               "party": d.get("party") or people.party(emp, term),
               "chamber": ((sp or {}).get("chamber") or people.voted_chamber(emp, term)
                           or d.get("chamber") or people.chamber(emp, term)),
               "sequence": n, "prime": bool(r["prime"]), "prime_inferred": False,
               "source": SOURCE, "url": d.get("url") or ""}
        if sp:
            rec["as_printed"] = sp["printed"]
        if how == "elimination, seat differs":
            # THE SITE'S NAME FOR THE NUMBER IS NOT THE ONE ON THE BILL, and its seat is not
            # the printed one either: shown as printed, linked to nobody.
            rec.update({"member_id": "", "party": "", "chamber": sp["chamber"],
                        "name": " ".join(sp["words"] + ([sp["suffix"]] if sp["suffix"] else [])),
                        "county": sp["county"] if sp["chamber"] == "H" else "",
                        "district": sp["district"],
                        "unlinked": "the site's record of this employee number names another "
                                    "member at another seat"})
        if d or how == "elimination, seat differs":
            rec["label"] = f"{rec['name']} ({rec['party']})" if rec["party"] else rec["name"]
        else:
            seat = sp if sp and sp.get("chamber") == rec["chamber"] else {}
            rec["label"] = names.legislator({
                "name": rec["name"], "chamber": rec["chamber"], "party": rec["party"],
                "district": seat.get("district") or "",
                "county_abbr": TS.ABBR.get(seat.get("county") or "", "")})
        out.append(rec)
    return out


def page_line(term, bid, bill):
    """The sponsor line of the bill's saved page, or None where there is no page."""
    import fetch_legislation as FL
    m = FL.PAD.match(bid)
    if not m:
        return None
    year = str(bill.get("lsr_year") or "")[:4]
    for name in (f"{m.group(1)}{int(m.group(2)):04d}", bid):
        for ext in ("html", "htm"):
            f = TS.PAGES / year / f"{name}.{ext}"
            if f.exists():
                return TS.read_line(f)
    return None


def filled(rows, people, term):
    """The list a bill no other source names a sponsor for takes from the record: its live
    rows, the prime first, each as records() names a row with no page and no status-page
    row to pair with -- the name and id the site has the number under, the party of its
    ballots that term, the chamber it voted in that term or the tables give it.

    seat_source says the seat is the record's own, which is a chamber and nothing more:
    build_site_v2 would otherwise label the row from today's roster, and a label states
    the seat held when the record was made.

    ONE NUMBER LISTED TWICE IS ONE SPONSOR. HB 3 of 2003 carries employee 209058, Sen.
    Robert Clegg, on rows 3 and 8, both live, and the filled list named him twice. The
    first in the list's own order is kept -- the prime's row, where one of them is prime.

    AND A LIST THE RECORD MARKS NO PRIME ON takes its first name as prime, and says it was
    taken (prime_inferred), as a list read off a bill's text does. HR 60, HR 63 and HR 65
    of 1990 and SCR 7 of 1998 have no row marked: the index and the download named the
    first sponsor as the bill's sponsor regardless, from rows that said nobody was."""
    live = sorted((r for r in rows if not r["withdrawn"]),
                  key=lambda r: (not r["prime"], r["sequence"]))
    seen, once = set(), []
    for r in live:
        if r["employee"] and r["employee"] in seen:
            continue
        seen.add(r["employee"])
        once.append(r)
    out = records(once, [], people, term)
    for r in out:
        r["seat_source"] = SOURCE
    if out and not any(r["prime"] for r in out):
        out[0]["prime"], out[0]["prime_inferred"] = True, True
    return out


def build(bills, sponsors, people, joined, terms=MERGED, line_of=None, named=None,
          current=None):
    """{term: {bill: entry}}, with the verdict and the published list for the merged terms,
    and the list to fill with ("fill") for a bill of any other past term that has no
    sponsor in `sponsors` (data/sponsors.json) and none in `named` (text_sponsors.json, the
    names read off each bill's own text). `current` is the term the session's own files
    describe, which is never filled.

    `line_of(term, bill, record)` gives the bill's printed sponsor line, or None where it
    has no page; page_line reads the saved pages, and preflight's fixtures stand in."""
    line_of = line_of or page_line
    named = named or {}
    out = defaultdict(dict)
    for term, recs in joined.items():
        keys = {}
        if term in terms:
            for v in recs.values():
                for r in v["rows"]:
                    if r["employee"] not in keys:
                        keys[r["employee"]] = people.surnames(r["employee"])

        def others(emp, keys=keys):
            return {k for e, ks in keys.items() if e != emp for k in ks}
        for bid, v in recs.items():
            live = [r for r in v["rows"] if not r["withdrawn"]]
            e = {"lsr": v["lsr"],
                 "sponsors": [{"employee": r["employee"],
                               "member_id": people.site_id(r["employee"]),
                               "name": people.site_name(r["employee"]),
                               "chamber": people.chamber(r["employee"], term),
                               "prime": r["prime"], "sequence": r["sequence"]} for r in live],
                 "withdrawn": [r["employee"] for r in v["rows"] if r["withdrawn"]]}
            if term in terms:
                db = (sponsors.get(term) or {}).get(bid) or []
                line = line_of(term, bid, bills[term][bid])
                if line is None:
                    e["page"], e["why"] = "no page", []
                    e["publish"] = records(v["rows"], db, people, term)
                else:
                    pieces = TS.split(line)
                    state, pairs, why, tally = verdict(v["rows"], pieces, people, term, others)
                    e["page"], e["why"], e["printed"] = state, why, line
                    e["tally"] = dict(tally)
                    if state == "agrees":
                        e["publish"] = records(v["rows"], db, people, term, pieces, pairs)
            elif term != current and live \
                    and not (sponsors.get(term) or {}).get(bid) \
                    and not (named.get(term) or {}).get(bid):
                e["fill"] = filled(v["rows"], people, term)
            out[term][bid] = e
    return dict(out)


def _load(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return default


def merge(sponsors, doc, printed, terms=MERGED, fill=True):
    """Give each bill of `terms` the list the record publishes for it, and (`fill`) each
    bill of any other term that has no sponsor the list the record fills it with; see
    merge_into."""
    got = Counter()
    for term in terms:
        have = sponsors.setdefault(term, {})
        for bid, e in (doc.get(term) or {}).items():
            if e.get("publish"):
                have[bid] = [dict(r) for r in e["publish"]]
                got["record"] += 1
            elif e.get("page") == "differs":
                page = (printed.get(term) or {}).get(bid)
                if page:
                    have[bid] = [dict(r) for r in page]
                    got["page"] += 1
                else:
                    got["differs, and no page list to publish"] += 1
    if not fill:
        return got
    # NEVER OVER A LIST. A bill of another term takes the record's only while it has
    # none -- asked here, when the lists are merged, not when the file was written.
    for term, rows in doc.items():
        if term in terms:
            continue
        for bid, e in rows.items():
            if e.get("fill") and not (sponsors.get(term) or {}).get(bid):
                sponsors.setdefault(term, {})[bid] = [dict(r) for r in e["fill"]]
                got["filled"] += 1
    return got


def merge_into(sponsors, path=OUT, text=TS.OUT, terms=MERGED):
    """Give each bill of `terms` the list this record publishes for it, and each bill of
    any other past term that still has no sponsor the record's list.

    IN `terms`: where the record agrees with the printed page -- or there is no page to
    hold it to -- the record's list. Where they disagree, the sponsors text_sponsors.py
    read off the page, from `text`; with no such list the bill keeps what it had.

    IN EVERY OTHER TERM: the record's list for a bill `sponsors` names nobody for, and
    nothing for a bill it names anybody for. Called after text_sponsors.merge_into, so a
    bill whose text names its sponsors has them by then.

    Returns a Counter of how many bills took which ({"record": n, "page": n, "filled":
    n}); absent the file, nothing happens and the Counter is empty."""
    doc = _load(path, None)
    if not isinstance(doc, dict):
        return Counter()
    return merge(sponsors, doc, _load(text, {}), terms)


# ------------------------------------------------------------------ reporting

def _name_key(name):
    """The letters of a name without a suffix: "Joe Alexander Jr." is "joealexander"."""
    return TS.letters(" ".join(w for w in re.split(r"[\s,]+", name or "")
                               if TS.letters(w) not in SUFFIXES))


def check(doc, sponsors, printed=None, terms=MERGED):
    """The bar, every exception to it, and what the merge changes. Returns the number of
    bills that differ."""
    differ = 0
    for term in terms:
        rows = doc.get(term) or {}
        c = Counter(e.get("page") for e in rows.values())
        t = Counter()
        for e in rows.values():
            t.update(e.get("tally") or {})
        print(f"\n{term}: {len(rows):,} bills in the sponsor record, "
              f"{c['agrees'] + c['differs']:,} with a saved page")
        print("  THE BAR, against the saved pages:")
        print(f"    live sponsors of the record that the page prints  {t['live printed']:>6,} of {t['live']:,}")
        print(f"    printed sponsors that are live in the record      {t['printed live']:>6,} of {t['printed']:,}")
        print(f"    bills whose prime the page prints first           {t['prime printed first']:>6,} of "
              f"{c['agrees'] + c['differs']:,}")
        print(f"    bills on which all three hold                     {c['agrees']:>6,} of "
              f"{c['agrees'] + c['differs']:,}")
        notes = [f"    {bid}: {x}" for bid, e in sorted(rows.items())
                 if e.get("page") == "agrees" for x in e.get("why") or ()]
        if notes:
            print(f"  on bills that agree, {len(notes)} sponsor(s) printed another way:")
            for x in notes:
                print(x)
        bad = [(b, e) for b, e in sorted(rows.items()) if e.get("page") == "differs"]
        differ += len(bad)
        print(f"  EXCEPTIONS, published as the page prints them: {len(bad)}")
        for bid, e in bad:
            print(f"    {bid} (LSR {e['lsr']}): " + "; ".join(e["why"]))
            print(f"        printed: {e.get('printed')}")
        none = sorted(b for b, e in rows.items() if e.get("page") == "no page")
        if none:
            print(f"  no saved page, published from the record unchecked: {len(none)}: "
                  + ", ".join(none))
        # What the merge changes against the list the site had.
        before = sponsors.get(term) or {}
        after = {term: {b: list(v) for b, v in before.items()}}
        took = merge(after, doc, printed or {}, (term,), fill=False)
        after = after[term]
        print(f"  published: {took['record']:,} bills from the record, {took['page']:,} as "
              f"their page prints them"
              + (f", {took['differs, and no page list to publish']:,} left as they were "
                 "(no page list on disk)" if took['differs, and no page list to publish'] else ""))
        ch = Counter()
        for bid in sorted(set(before) | set(after)):
            old, new = before.get(bid) or [], after.get(bid) or []
            op = next((r for r in old if r.get("prime")), None)
            np_ = next((r for r in new if r.get("prime")), None)
            if op and np_ and TS.letters(op.get("name")) != TS.letters(np_.get("name")):
                ch["prime sponsors corrected"] += 1
                print(f"    prime: {bid}: {op.get('name')} -> {np_.get('name')}")
            ok_ = {_name_key(r.get("name")): r.get("name") for r in old}
            nk = {_name_key(r.get("name")): r.get("name") for r in new}
            for x in sorted(set(nk) - set(ok_)):
                ch["sponsorships added"] += 1
                print(f"    added: {bid}: {nk[x]}")
            for x in sorted(set(ok_) - set(nk)):
                ch["sponsorships removed"] += 1
                print(f"    removed: {bid}: {ok_[x]}")
            ch["rows before"] += len(old)
            ch["rows after"] += len(new)
            ch["unlinked before"] += sum(1 for r in old if not r.get("member_id"))
            ch["unlinked after"] += sum(1 for r in new if not r.get("member_id"))
        for k, v in ch.items():
            print(f"  {k:52} {v:>7,}")
    return differ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # Every one, or nothing: without the ballots or the roster no number has an id the
    # site knows, and the whole term would be published unlinked.
    for need in (PAST / "_manifest.json", LEGISLATORS, COLUMNS, BILLS, VOTES, ROSTER):
        if not Path(need).exists():
            sys.exit(f"{need} is not here: this reads the dump fetch_past_db.py makes, the "
                     "legislators table, data/bills.json and the ballots and roster "
                     "build_data.py writes, and writes nothing without them.")
    bills = json.loads(BILLS.read_text(encoding="utf-8"))
    sponsors = json.loads(SPONSORS.read_text(encoding="utf-8")) if SPONSORS.exists() else {}
    joined, tally = join(bills, read_view("PastSponsors"), read_view("PastLegislation"))
    people = load_people()
    # The names read off each bill's own text, which a filled list never replaces. Read
    # as it stands: text_sponsors.py --apply runs before this in a build, and merge()
    # asks again when the lists are merged.
    named = _load(TS.OUT, None)
    if named is None:
        print(f"{TS.OUT} is not here, so every bill of a past term with no sponsor in "
              f"{SPONSORS} is given a list to fill with; the merge still fills only a "
              "bill that has none")
    doc = build(bills, sponsors, people, joined, named=named or {},
                current=max(bills) if bills else None)
    print("the sponsor record, joined by each bill's stored LSR:")
    for k, v in tally.most_common():
        print(f"  {v:>7,}  {k}")
    for term in sorted(doc):
        live = [s for e in doc[term].values() for s in e["sponsors"]]
        fill = [e["fill"] for e in doc[term].values() if e.get("fill")]
        names_ = [r for rows in fill for r in rows]
        print(f"  {term}: {len(doc[term]):>5,} of {len(bills.get(term) or {}):>5,} bills, "
              f"{len(live):>6,} live sponsors, {sum(1 for s in live if s['member_id']):>6,} "
              "under an id the site has"
              + (f"; {len(fill):>3,} bills with no other sponsor filled, "
                 f"{sum(1 for r in names_ if r['member_id']):,} of {len(names_):,} names "
                 "a member's, the rest as the record names them" if fill else ""))
    n_fill = sum(1 for t in doc.values() for e in t.values() if e.get("fill"))
    print(f"  {n_fill:,} bills of the terms outside {', '.join(MERGED)} have no sponsor "
          "from any other source and take the record's")
    differ = check(doc, sponsors, _load(TS.OUT, {})) if a.check else 0
    if a.apply:
        OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        print(f"\nwritten {OUT}")
    # A bill the record and its page disagree on is published as the page prints it and
    # is not a failure; --check exits non-zero so a person reading it sees there are some.
    return 1 if a.check and differ else 0


if __name__ == "__main__":
    sys.exit(main())
