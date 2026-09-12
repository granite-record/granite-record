#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.4
"""The committee a bill was referred to, read out of the docket.

    python3 referrals.py            # what it finds, by year, no network
    python3 referrals.py --check    # every expansion, and the evidence for it

WHY THIS EXISTS

Five terms -- 1989 to 1998, 8,525 bills -- had no committee at all on this
site, and the plan was to fetch one web page per bill to get one. The
committee was already on this disk: the General Court's own database dump
holds the docket back to 1989, and the clerk writes the referral into the
description of the introduction line.

    INTRODUCED AND REF TO EXEC & ADMIN     HJ 13 ,P 138
    Introduced 1/4/2012 and Referred to Judiciary; HJ 11, PG. 183
    PASSED AND REF TO FINANCE VV; HJ35,P943

34,000 referrals, 1989 to 2015, for no requests at all. This file is the one
reader of that text; nothing else parses a referral out of a docket line.

WHICH REFERRAL

The FIRST one per chamber -- the committee of referral, the one the bill's
own text prints as "REFERRED TO:". A bill can be re-referred, and for
1999-2015 the field this fills came from the search page's "Next/Last Comm",
which is the LAST one. That difference is real and is why this only ever
fills a field that is empty: it never overwrites what the search page said,
so no term has one bill's last committee sitting beside another's first.

THE ABBREVIATIONS ARE PROVEN, NOT GUESSED

The clerk of 1989 writes "EXEC DEPTS & ADMIN" and the clerk of 2011 writes
"Executive Departments and Administration", and both are in this corpus. So
every expansion below can be checked rather than believed: --check asserts
that each abbreviated form, once expanded, equals a string that appears
spelled out somewhere in the same 34,000 lines. Where no such evidence
exists the abbreviation is LEFT ALONE -- an honest "RES, REC & DEV" beats an
invented expansion, and the site renders a committee with no code as plain
text rather than as a link, so nothing breaks when a 1989 committee has no
page.

A BETTER AUTHORITY THAN THE CORPUS, since 10 September. The General Court
publishes its own key to these abbreviations at
bill_status/legacy/bs2016/docket_abbrev.htm, kept here as docket_abbrev.json.
Where the key speaks it wins, and it settled two that nothing in the corpus
ever spelled out: JUD is Judiciary and Family Law (314 bills read "Judiciary
and F L" until now) and ECON DEVEL is Economic Development (130). Where the
key is silent, "Corr and Cj" still stands as the clerk wrote it.

A FOURTH WITNESS, since 11 September: the resolution each House adopts its
rules by defines every standing committee in one sentence -- "the Committee on
Public Protection and Veterans Affairs to consider all matters affecting
public protection ..." -- and two of them are on this disk as bill text. That
is the body naming its own committees, it names 22 of them, and it settled
"Pub Prot", which the docket abbreviates nine ways across 1989-1996 and never
once writes out. It also corroborates Judiciary and Family Law independently
of the key, and it names "Corrections and Criminal Justice", which is the
evidence "Corr and Cj" has been waiting for.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import names

SRC = Path("db/Docket.psv")

# The three ways a referral is written. Anchored at the start of the
# description so that "Committee Report: Refer to Interim Study" -- a
# disposition, not a committee -- cannot match.
INTRO = re.compile(
    r"^\s*introduce[ds]?\b.{0,30}?\band\s+ref(?:erred)?\.?\s+to\s+(?P<c>.+)$", re.I)
PASSED = re.compile(
    r"^\s*passed(?:\s+with\s+am)?\s+and\s+ref(?:erred)?\.?\s+to\s+(?P<c>.+)$", re.I)
REREF = re.compile(r"^\s*re-?ref(?:erred)?\s+to\s+(?P<c>.+)$", re.I)

# What follows the committee on the same line: the journal citation, a date
# in brackets, a parenthetical, or two spaces used as a column break.
TAIL = re.compile(
    r"\s*[;(\[].*$|\s{2,}.*$|\s+[HS]J\b.*$|\s*,\s*P(?:G|g)?\.?\s*\d.*$"
    r"|\s*,\s*pg.*$|\s+\d{1,2}/\d{1,2}/\d{2,4}.*$", re.I)
# The vote that carried the motion, written after the committee.
VOTE = re.compile(r"(?:[\s,]*\b(?:VV|MA|MF|RC|DV|AA|OTPA?|ITL)\b)+[\s,.;]*$", re.I)
# "Rereferred to Committee" names no committee: it is back to the same one.
NOT_A_NAME = re.compile(r"^(?:committee|the committee|full committee|"
                        r"interim study|committee of conference|"
                        r"no committee assignment)$", re.I)
# The clerks write both "Ways & Means" and "Ways and Means" for the same
# committee in the same year. This is a spelling, not an abbreviation, so it
# needs no evidence -- but it is the single largest source of a committee
# appearing twice in a count, and it runs after the expansions below so that
# their patterns can still match on the ampersand.
AMP = re.compile(r"\s*[&+]\s*")

# Expansions, each verified by --check against a spelled-out form in the same
# corpus. A phrase is tried before its words so that "H & HS" becomes Health
# and Human Services rather than two lone letters.
PHRASES = [
    # ADM as well as ADMIN: the clerk of 1989 wrote "EXEC DEPTS & ADM",
    # which reached the site as "Exec Depts and Adm". EXECUTIVE and the
    # clerk's "EXECTIVE" as well as EXEC, a singular DEPT as well as DEPTS,
    # the "and" optional ("Exec Depts Admin"), and ADMINSTRATION -- which is
    # how the House wrote its own committee's name five times -- because each
    # of those was on the site abbreviated or misspelt on the 11th.
    (r"\bEXEC(?:UTIVE|TIVE)?\.?\s*DEPTS?\.?\s*(?:(?:&|\+|AND)\s*)?"
     r"ADM(?:IN|INISTRATION|INSTRATION)?\.?\b",
     "Executive Departments and Administration"),
    (r"\bMUN(?:ICIPAL)?\.?\s*(?:&|/|\+|AND)?\s*C(?:N?TY|OUNTY)\.?\s*"
     r"(?:(?:&|\+|AND)\s*)?GOVT?\.?\b",
     "Municipal and County Government"),
    (r"\bCRIM\.?\s*JUST\.?\s*(?:&|\+|AND)\s*"
     r"P(?:\.?\s*SFTY|SAFETY|UB\.?\s*SAFETY)\.?\b",
     "Criminal Justice and Public Safety"),
    (r"\bRES\.?\,?\s*REC\.?\,?\s*(?:&|\+|AND)?\s*DEV\.?\b",
     "Resources, Recreation and Development"),
    (r"\bENV\.?\s*(?:&|\+|AND)\s*AGRIC?\.?\b", "Environment and Agriculture"),
    (r"\bWAYS\s*(?:&|\+)\s*MEANS\b", "Ways and Means"),
    (r"\bCON\.?\s*(?:&|\+|AND)\s*STAT\.?\b",
     "Constitutional and Statutory Revision"),
    (r"\bSCI(?:ENCE)?\.?\s*[,/]?\s*TECH\.?\s*(?:&|\+|/|AND)?\s*EN(?:ERGY)?\b",
     "Science, Technology and Energy"),
    (r"\bPUB\.?\s*WORKS\b", "Public Works"),
    # AFFS as well as AFFAIRS. "Internal Affs" and "Public Affs" were on 24
    # pages, and are the same two committees these patterns already cover.
    (r"\bPUB(?:LIC)?\.?\s*AFF(?:AIR)?S\.?\b", "Public Affairs"),
    (r"\bINTERNAL\s*AFF(?:AIR)?S\.?\b", "Internal Affairs"),
    (r"\bELEC\.?\s*LAW\b", "Election Law"),
    (r"\bAPPROP\.?\b", "Appropriations"),
    (r"\bTRANS\.?$", "Transportation"),
    # Added after the first build put these on the site abbreviated. Each is
    # proven the same way -- --check finds it spelled out in the docket or in
    # a bill's own text -- and the ones that are NOT spelled out anywhere are
    # deliberately absent: "Child Y&Jj" and "Pub Instit" keep the clerk's
    # letters, because a plausible expansion of a committee name is still an
    # invented one. ("Pub Instit" is two referrals, and the two candidates on
    # this disk -- Public Institutions, Health and Human Services, and State
    # Institutions and Housing -- are different committees.)
    #
    # "Corr & Cj" came off that list on the same evidence as "Pub Prot": the
    # rules resolution names "the Committee on Corrections and Criminal
    # Justice". 159 referrals on 152 pages, which read "the House Corr and Cj
    # committee" until the 11th.
    (r"\bCORR\.?\s*(?:&|\+|AND)\s*CJ\b", "Corrections and Criminal Justice"),
    #
    # "Pub Prot" was on that list until the 11th, and came off it on
    # evidence rather than on a hunch. The docket never writes it out: a
    # search of all 584 referral strings for "PROTECTION" finds only
    # Consumer Protection, which is a different committee, and one
    # "PUB PROTECTION" of 1991, which is still abbreviated. The bills' own
    # text does write it out, and writes it out as a charter:
    # legislation/1995/HR0001.html -- the House resolution adopting its rules
    # -- names "Public Protection and Veterans Affairs to consider all
    # matters affecting public protection including, but not limited to, law
    # enforcement and the training of law enforcement officers", and
    # legislation/2008/HR0020.html names it again. The docket's own ladder of
    # spellings runs to the same place across 1989-1996: PUB PROT (82),
    # PUBLIC PROT (40), PUB PROTECT (6), PUB PROTEC, PUB PROTECTION, and
    # PUBLIC PROT & VETS AFFS (15), which carries the second half of the name
    # the resolution states in full. 148 referrals on 104 pages.
    (r"\bPUB(?:LIC)?\.?\s*PROT(?:EC|ECT|ECTION)?\b",
     "Public Protection and Veterans Affairs"),
    # Same evidence, different committee: legislation/1993/HBI0002.html
    # writes "Commerce, Small Business and Consumer Affairs", which is this
    # abbreviation element for element and adds nothing to it. By 1995 the
    # House had renamed it -- legislation/1995/HR0001.html has "Commerce,
    # Small Business, Consumer Affairs and Economic Development" -- and the
    # abbreviation is only ever written in 1990, before that, so the
    # three-part name is the one this era means. 49 referrals.
    (r"\bCOMMERCE\s*,?\s*SM\.?\s*BUS\.?\s*(?:&|\+|AND)\s*CONS\.?\s*AFFS?\.?\b",
     "Commerce, Small Business and Consumer Affairs"),
    # Spelled out 258 times in the docket itself, and in the same 1995
    # resolution. SRVCS as well as SVCS: "LABOR, INDUS & REHAB SRVCS" is the
    # clerk of one year dropping a different letter.
    (r"\bLABOR\s*,?\s*INDUS(?:TRIAL)?\.?\s*(?:&|\+|AND)\s*"
     r"REHAB(?:ILITATIVE)?\.?\s*S(?:E?RVI?CE?S|VCS|RVCS)\.?\b",
     "Labor, Industrial and Rehabilitative Services"),
    (r"\bHEALTH\s*[,]?\s*(?:HUMAN\s*)?(?:SVCS?|HS)\s*(?:&|\+|AND)\s*EA\b",
     "Health, Human Services and Elderly Affairs"),
    # HUM for HUMAN, SRVCS for SERVICES and ELD AFFS for ELDERLY AFFAIRS, all
    # in one string: "Health, Hum Srvcs and Eld Affs", on 34 pages.
    (r"\bHEALTH\s*,?\s*HUM(?:AN)?\.?\s*S(?:E?RVI?CE?S|VCS|RVCS)\.?\s*"
     r"(?:&|\+|AND)\s*(?:ELD(?:ERLY)?\.?\s*AFF(?:AIR)?S|EA)\.?\b",
     "Health, Human Services and Elderly Affairs"),
    (r"\bHEALTH\s*,\s*HUMAN\s*SVCS?\.?\s*(?:&|\+|AND)\s*ELDERLY\s*AFFAIRS\b",
     "Health, Human Services and Elderly Affairs"),
    # INSTIT as well as INST and INSTITUTIONS: "Pub. Instit. H and Hs" broke
    # this pattern on the two letters between them, and SB 201 of 1997 named
    # its committee that way on the site.
    (r"\bPUB(?:LIC)?\.?\s*INST(?:IT)?(?:UTIONS)?\.?\s*[,/]?\s*H(?:EALTH)?\s*"
     r"(?:&|\+|AND)\s*H(?:UMAN\s*)?S(?:ERVICES)?\b",
     "Public Institutions, Health and Human Services"),
    (r"\bWILDLIFE\s*(?:&|\+|AND)\s*REC\.?$", "Wildlife and Recreation"),
    (r"\bLEG\.?\s*ADMIN\.?\b", "Legislative Administration"),
    (r"\bLOC\.?\s*(?:&|\+|AND)\s*REG\.?\s*REV\.?\b",
     "Local and Regulated Revenues"),
    (r"\bREG\.?\s*REV\.?$", "Regulated Revenues"),
    # REL optional: "St-Fed and Vets Affs" drops it, and there is no other
    # State-Federal committee for it to be confused with.
    (r"\bST\.?[- ]?FED\.?\s*(?:REL\.?\s*)?(?:&|\+|AND)\s*VETS?\.?\b",
     "State-Federal Relations and Veterans Affairs"),
    (r"\bCHILD(?:REN)?\.?\s*(?:&|\+|AND)\s*FAM(?:ILY)?\.?\s*LAW\b",
     "Children and Family Law"),
    # The name with no "and Administration" after it, however the clerk spelt
    # the first word -- "Exective Dept" included, which is one referral and
    # was one page.
    (r"\bEXEC(?:UTIVE|TIVE)?\.?\s*DEPTS?\.?$",
     "Executive Departments and Administration"),
    (r"\bEXEC\.?\s*(?:&|\+|AND)\s*ADMIN\.?\b",
     "Executive Departments and Administration"),
    # From the General Court's own key (docket_abbrev.json): JUD is Judiciary
    # and Family Law, ECON DEVEL is Economic Development. Both stood as the
    # clerk's letters until the source said otherwise -- which was the right
    # rule, and a published key is the thing that lifts it.
    (r"\bJUDICIARY\s*(?:&|\+|AND)\s*F\.?\s*L\.?$", "Judiciary and Family Law"),
    (r"\bECON\.?\s*DEV(?:EL)?\.?$", "Economic Development"),
]


def _key(s):
    """A committee name reduced to what does not vary between clerks.

    "Wildlife & Recreation" and "Wildlife and Recreation" are one committee,
    so the ampersand and the word it stands for are both dropped, along with
    punctuation and case. Used only to ask whether a source spells a name
    out; never to decide what to publish.
    """
    words = re.findall(r"[a-z]+", AMP.sub(" and ", s).lower())
    return "".join(w for w in words if w != "and")


def clean(s):
    """The committee, with what the clerk wrote after it taken off."""
    s = TAIL.sub("", s)
    s = VOTE.sub("", s)
    s = re.sub(r"[\s.,;:&/+-]+$", "", s).strip()
    return "" if NOT_A_NAME.match(s) else s


def expand(s):
    """An abbreviated committee written out, where the expansion is proven."""
    for pat, full in PHRASES:
        if re.search(pat, s, re.I):
            return full
    return s


def committee(desc):
    """The committee named by one docket description, or "".

    names.committee is the site's one place for turning a shouted name into a
    name, and it runs here rather than only at render time so that the CSV
    exports and data/bills.json carry "Judiciary" as well: the docket writes
    both JUDICIARY and Judiciary across the years, and left alone they are
    two committees in every count.
    """
    for rx in (INTRO, PASSED, REREF):
        m = rx.match(desc or "")
        if m:
            # names.committee first, then the ampersand: it only unshouts a
            # name that is at least 90% upper case, and substituting a
            # lower-case "and" into "JUDICIARY & F L" first drops it below
            # that threshold and leaves the shout standing.
            return AMP.sub(" and ", names.committee(expand(clean(m.group("c")))))
    return ""


def from_docket(path=SRC, lo=1989, hi=2015):
    """{(session year, bill): {body: committee}} -- the FIRST per body.

    The docket arrives in the order the clerk wrote it, so the first referral
    a body records is the committee of referral. setdefault is what keeps it
    first; a re-referral later in the same body does not replace it.
    """
    out = collections.defaultdict(dict)
    if not Path(path).exists():
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 7 or not p[0].isdigit():
                continue
            year = int(p[0])
            if not lo <= year <= hi:
                continue
            c = committee(p[6])
            if c:
                out[(p[0], p[4].strip())].setdefault(p[5].strip(), c)
    return out


def _corpus(path=SRC, lo=1989, hi=2015):
    """Every cleaned, UNexpanded referral string with its count."""
    seen = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 7 or not p[0].isdigit() or not lo <= int(p[0]) <= hi:
                continue
            for rx in (INTRO, PASSED, REREF):
                m = rx.match(p[6])
                if m:
                    c = clean(m.group("c"))
                    if c:
                        seen[c] += 1
                    break
    return seen


ABBREV = Path("docket_abbrev.json")


def _key_names():
    """The committee names in the General Court's own key to its docket.

    docket_abbrev.json, copied verbatim from
    bill_status/legacy/bs2016/docket_abbrev.htm. One entry is corrected: the
    page prints ST&E as "Science. Technology and Energy", with a full stop
    where the comma belongs, and publishing a committee's name with a typo in
    it because the source had one is deference rather than accuracy.
    """
    if not ABBREV.exists():
        return []
    try:
        raw = json.loads(ABBREV.read_text(encoding="utf-8")).get("abbrev", {})
    except ValueError:
        return []
    return [v.replace("Science. Technology", "Science, Technology")
            for v in raw.values()]


# THE HOUSE NAMING ITS OWN STANDING COMMITTEES. The resolution that adopts
# the rules for a term defines each committee in one construction -- "It shall
# be the duty of the Committee on Science, Technology and Energy to consider
# all matters relating to ..." -- and legislation/1995/HR0001.html and
# legislation/1997/HR0001.html carry 22 of them between them.
#
# This is the strongest witness on the disk after the General Court's own key,
# and for the same reason: it is the body saying what its committees are
# called, in a sentence whose whole purpose is to say so. It is also not
# circular. The pattern is the resolution's grammar, not a name this file
# hopes to prove, so it finds committees nothing here asked about -- among
# them "Corrections and Criminal Justice", whose abbreviation "Corr & Cj"
# stands unexpanded a few lines above for want of exactly this evidence.
RULES_COMMITTEE = re.compile(
    r"Committee on ([A-Z][A-Za-z,'&\-. ]{4,70}?)\s+to consider all matters")


def _rules_names():
    """Committee names the chamber's own rules resolution writes out."""
    out = collections.Counter()
    pages = Path("legislation")
    if not pages.is_dir():
        return out
    for f in pages.rglob("*.html"):
        try:
            text = f.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            continue
        if "to consider all matters" not in text:
            continue
        flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))
        for name in RULES_COMMITTEE.findall(flat):
            out[name.strip(" .,")] += 1
    return out


def _spelled_out():
    """Committee names written in full, from the four sources that write them.

    The docket, where a later clerk spelled out what an earlier one
    abbreviated; the bills saved under legislation/, where the committee is
    printed beside REFERRED TO: in the bill's own text; the resolution each
    House adopts its rules by, which defines every standing committee by name;
    and the General Court's own key, which is the best of the four because it
    is the body saying what its own shorthand means rather than this project
    inferring it.

    The bill texts are the only witness to "Constitutional and Statutory
    Revision", which the docket only ever abbreviates. The key is the only
    witness to "Judiciary and Family Law" and "Economic Development", which
    nothing else on this disk ever writes out. The rules resolutions are the
    only witness to "Public Protection and Veterans Affairs", which the
    docket abbreviates nine ways across 1989-1996 and never once writes out.
    """
    out = collections.Counter()
    for name in _key_names():
        out[name] += 1
    for name, n in _corpus().items():
        out[name] += n
    for name, n in _rules_names().items():
        out[name] += n
    pages = Path("legislation")
    if pages.is_dir():
        try:
            import fetch_legislation as FL
        except ImportError:
            return out
        for f in pages.rglob("*.html"):
            got = FL.parse(FL.decode(f.read_bytes()))
            if got.get("committee"):
                out[got["committee"]] += 1
    return out


def check():
    """Every expansion, against a form spelled out by one of the sources."""
    seen = _corpus()
    full_forms = _spelled_out()
    # Every spelling that reduces to the same key, and the total across them:
    # one representative undercounts a name the sources write six ways.
    spelled = collections.defaultdict(int)
    for k, n in full_forms.items():
        spelled[_key(k)] += n
    bad = []
    for pat, full in PHRASES:
        key = _key(full)
        hits = [k for k in seen if re.search(pat, k, re.I)]
        if key not in spelled:
            bad.append(f"{full!r}: nothing spells it out, so the expansion "
                       "is invented and the abbreviation should stand")
        print(f"  {full:46} <- {sum(seen[k] for k in hits):5,} referrals, "
              f"{len(hits):3} spellings, written out {spelled.get(key, 0):,} times")
    if bad:
        print()
        for b in bad:
            print("  UNPROVEN: " + b)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--src", default=str(SRC))
    a = ap.parse_args()
    if not Path(a.src).exists():
        sys.exit(f"No {a.src}. This reads the database dump and nothing else.")
    if a.check:
        print("EXPANSIONS, and the evidence for each:")
        return check()
    got = from_docket(a.src)
    by_year = collections.Counter()
    for (year, _bill), bodies in got.items():
        by_year[year] += 1
    print(f"{len(got):,} bills carry a referral, {sum(by_year.values()):,} rows")
    print()
    for y in sorted(by_year):
        print(f"  {y}: {by_year[y]:,}")
    names = collections.Counter()
    for bodies in got.values():
        for c in bodies.values():
            names[c] += 1
    print()
    print(f"{len(names)} distinct committee names. The twelve most referred:")
    for k, v in names.most_common(12):
        print(f"  {v:6,}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
