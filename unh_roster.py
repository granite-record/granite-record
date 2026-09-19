#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.2
"""
Who was in the House, out of the House's own roll. No network.

    python3 unh_roster.py journalofhouseof1997newh            # write the roster
    python3 unh_roster.py journalofhouseof1997newh --check    # score it
    python3 unh_roster.py journalofhouseof1997newh --against journals/1997

WHY THE ROSTER IS THE NEXT THING AFTER THE VOTES

unh_measure.py puts the reflowed scan at 95.80% of member votes carried under
the right name, with another 2.72% present but damaged in the way 2009 OCR
damages this typeface -- Adler read as Adier, Cushing as Gushing, Vogl as
VogI, MacIntyre as Maclntyre. Those are l/i, C/G and rn/m confusions, and
they are only repairable against a CLOSED set of the people who could
possibly be named. Four hundred known members is a small enough set that
"Adier" has exactly one plausible reading; the whole English language is not.

The journals carry that set themselves. Every volume opens with the CALL OF
THE ROLL: every member, by county and district, with a full name and the
party or parties that nominated them. So the thing needed to repair the scan
is printed in the same book as the damage, which means no external roster has
to be found for 1989-1996, where this project has none.

THE SEAT COUNT IS THE CHECK, AND IT COMES FREE

Each district states how many seats it has:

    Dist. No. 7(6)  Robert G. Holbrook, r; Robert M. Lawton, r; ...

so a district that declares six seats and yields five names is wrong by one,
and says so with nothing to compare against. The House had 400 seats in 1997.
--check reports both, per district and in total. A roster extractor that
quietly returned 380 people would otherwise look exactly like one that worked.

--against additionally takes every surname the General Court's own digital
journals record as voting that year, and asks whether the roster has them. A
member who cast a vote and is not on the roll is a failure of one or the
other, and that is a source this project did not generate.

WHAT THE ROLL IS WORTH, MEASURED

Against the 1997 House, and the General Court's own digital journals for the
same year:

    seats the journal declares                 400
    seats this reads out of it                 400   0 districts disagree
    surnames that actually cast a vote         368
    of those, on this roll                     347   95.92% of member votes

The 21 it misses are not missing members. They are the same name, spelled two
ways, and the roll is the one that is wrong:

    Colburn      the roll reads  Colbum          Coes      reads  Goes
    Burnham                      Bumham          Fraser    reads  Eraser
    O'Hearn                      O'Heam          MacIntyre reads  Maclntyre
    Letourneau                   Letoumeau

which is rn read as m, and C as G, and F as E, and I as l. The useful part is
that the roll and the roll calls are damaged INDEPENDENTLY -- Colbum appears
once in the roll and Colburn 58 times in the votes of that year -- so the two
halves of the same book correct each other, and neither needs an outside
source. That is what makes 1989-1996 tractable, where no outside source
exists.

WHAT THE PARTY LETTERS MEAN

New Hampshire lets a candidate be nominated by more than one party, and the
journal prints it: "r" Republican, "d" Democrat, "l" Libertarian, and "r&d"
for a member who carried both nominations. They are recorded here exactly as
printed rather than resolved to one party, because which nomination to treat
as the member's own is a judgment this file should not be making.
"""

import argparse
import csv
import glob
import re
import sys
from collections import Counter
from pathlib import Path

REFLOW = Path("data/unh/reflow")
OUT = Path("data/unh/roster")

START = re.compile(r"^\s*CALL\s+OF\s+THE\s+ROLL\s*$", re.I)
# Where the roll ends. The roll is followed by the sitting's business, and
# these are the headings that have been seen to open it. Rather than trust
# the list, stop_at() also stops at a long run of lines that hold no district
# and no name, so an unfamiliar heading in another year ends the roll too.
STOP = re.compile(r"^\s*(RESOLUTION|INTRODUCTION OF GUESTS|OATH OF OFFICE|"
                  r"ELECTION OF|PRAYER|LEAVES OF ABSENCE)", re.I)
COUNTY = re.compile(r"^\s*([A-Z][A-Za-z]+)\s+COUNTY\s*$")
# "Dist. No. 7(6)", "Dist. No. 10 (1)" -- the space comes and goes -- and, in
# 1991, "Dist. No. 1" with no seat count at all. The count is what --check
# scores against, so where the volume does not print one there is nothing to
# score and QUORUM below is the guard instead.
DIST = re.compile(r"^\s*Dist\.\s*No\.\s*(\d+)\s*(?:\((\d+)\))?\s*(.*)$")

# "With 392 members having answered the call of the roll, a quorum was
# declared present." The journal counting itself, a few hundred lines after
# the roll it is counting. It is the only check available on a volume that
# prints no seat counts, and it is a good one: it comes from the Clerk.
QUORUM = re.compile(r"With\s+(\d+)\s+members\s+having\s+answered\s+the\s+call",
                    re.I)

# A member and the party that nominated them, found by locating the PARTY and
# taking what precedes it as the name.
#
# Splitting on the semicolon works for 1997 and fails for 1991, which prints
#
#     Dist. No. 6  Arnold P. Shibley. r. Alice S. Ziegra, r&d
#     Dist. No. 8  Thomas E.P. Rice, Jr.. r
#
# where the separator between one member and the next is a full stop, the
# separator between a name and its party is a full stop, and a name may end
# in a full stop of its own. The party code is the one fixed landmark: one to
# four of the letters r, d, l, i and n joined by ampersands, standing alone.
# So the parties are found and the names are whatever lies between them.
#
# Two details in the pattern, each of which cost a member before it was there:
#
#   The lookahead bars an apostrophe as well as a letter. "Robert J.
#   L'Heureux, r&l" otherwise yields a party "l" at the L of L'Heureux --
#   the character after it is an apostrophe, which is not a letter -- and
#   splits one member into "Robert J" and "'Heureux".
#
#   It is CASE-SENSITIVE. The journal prints the party in lower case, and a
#   capital in that position is a middle initial: matched case-insensitively,
#   "Suzan L. R. Franks, r" reads the ". R." as a party and splits her into
#   "Suzan L" and "Franks". 1991 prints a middle initial for nearly everyone
#   and was full of it.
MEMBER = re.compile(r"[,.]\s*([rdlin](?:\s*&\s*[rdlin])*)(?![A-Za-z&'’])")
# A note set into the roll in brackets, sometimes opened with an asterisk.
FOOTNOTE = re.compile(r"^\s*[*•]?\s*\(")

# A running head dropped into the middle of the roll by the page break.
FURNITURE = re.compile(r"^\s*(?:\d{1,4}\s+)?House\s+Journal\b.*$|^\s*\d{1,4}\s*$",
                       re.I)
# The party letters, as printed: r, d, l, i, and combinations joined by &.
PARTY = re.compile(r"^[rdlin](?:\s*&\s*[rdlin])*$", re.I)
# The same field after the scan has had a go at the ampersand. Short, all
# letters, in the position a party sits in. Matched only after PARTY fails.
SHORT_CODE = re.compile(r"^[a-z]{2,4}$", re.I)

COLS = ["county", "district", "seats", "name", "party", "town", "note", "source"]

# "Coos 7, Paul St. Hilaire, r, Berlin (404 Church Street) 03570"
#
# The seats the CALL OF THE ROLL holds open are filled later in the volume, by
# a COMMUNICATION from the Secretary of State naming who was sworn and when.
# That is how the record works and it is why the roll alone is short: Philip
# Cobbin of Grafton 11 cast 77 votes in 1997 and is not in the December roll,
# because on organisation day he had not yet taken the oath.
#
# The street address in brackets is deliberately not captured. The town is
# useful and is the district's own; the house number is a legislator's home
# address in 1996, this site has no use for it, and not reading it at all is
# a shorter argument than deciding later not to publish it.
SWORN = re.compile(
    r"^\s*([A-Z][A-Za-z]+)\s+(\d+)\s*,\s*"          # county and district
    r"([^,]+?)\s*,\s*"                                # name
    r"([rdlin](?:\s*&\s*[rdlin])*)\s*[,.]\s*"        # party, then , or . (OCR)
    r"([A-Za-z .'\-]+?)\s*[(\d]",                     # town, up to the address
    re.M)
SWEARING = re.compile(r"sworn\s+into\s+office", re.I)


def reflow_path(identifier):
    p = REFLOW / f"{identifier}.txt"
    if not p.exists():
        sys.exit(f"{p} is not there; unh_rollcalls.py --reflow {identifier} writes it")
    return p


def roll_lines(text):
    """The lines between CALL OF THE ROLL and the business that follows it."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if START.match(line):
            start = i + 1
            break
    if start is None:
        sys.exit("no CALL OF THE ROLL in this volume; nothing to read")
    out = []
    barren = 0
    in_footnote = False
    for line in lines[start:]:
        # A parenthetical note set inside the roll. 1991's Rockingham 20
        # carries one about a member-elect who took a federal job and would
        # not be sworn; it has commas in it, so it reads as a continuation
        # line and became a member 170 characters long. It runs until its
        # bracket closes or the roll resumes with a district.
        if in_footnote:
            if ")" in line:
                in_footnote = False
            if not DIST.match(line) and not COUNTY.match(line):
                continue
            in_footnote = False
        if FOOTNOTE.match(line):
            in_footnote = ")" not in line
            continue
        if STOP.match(line):
            break
        # The Clerk counting the roll is the end of the roll, and it is the
        # only terminator that means what it says in every volume.
        if QUORUM.search(line):
            break
        if FURNITURE.match(line):
            continue
        if not line.strip():
            continue
        if DIST.match(line) or COUNTY.match(line):
            barren = 0
        else:
            # A continuation line carries names, so it has a semicolon or a
            # comma in it. A run of lines with neither is the roll being over
            # under a heading this parser has not met.
            #
            # Eight, not three. The 1991 roll carries a footnote in the middle
            # of Rockingham -- a member-elect who took a federal job and would
            # not be sworn -- whose three comma-free lines ended the roll at
            # district 20 and cost two whole counties. The quorum sentence
            # above is the real terminator; this is only a backstop for a
            # volume that does not print one.
            barren = 0 if ("," in line or ";" in line) else barren + 1
            if barren >= 8:
                break
        out.append(line)
    return out


def split_members(blob):
    """The members named in one district's text.

    Anchored on the party code rather than on a separator -- see MEMBER for
    why the separator cannot be trusted across volumes. Each party found ends
    a member; what lies between it and the one before is that member's name.
    Anything after the last party is a fragment and is put through the old
    semicolon split, which is where a seat with no party -- "Elected, not
    sworn" -- comes from.
    """
    blob = " ".join(blob.split())
    out = []
    last = 0
    for m in MEMBER.finditer(blob):
        chunk = _plain(blob[last:m.start()])
        last = m.end()
        party = m.group(1).lower().replace(" ", "")
        # The party sits directly after ONE name. Where a chunk yielded more
        # than one -- which happens when a member before it carried no party
        # at all -- it belongs to the last.
        for i, (name, _p, note) in enumerate(chunk):
            out.append((name, party if i == len(chunk) - 1 and name else "",
                        note))
    tail = blob[last:]
    out.extend(_plain(tail))
    return [(n, p, note) for n, p, note in out if n or note]


def _plain(blob):
    """The fallback split, on the semicolon, for text carrying no party."""
    out = []
    for part in blob.split(";"):
        part = " ".join(part.split()).strip(" ,.")
        if not part:
            continue
        # "Dist. No. 11 (2) Elected, not sworn; Phil A. Weber, r&d"
        #
        # This is a SEAT, not a remark about the member before it. On the
        # organisation day of 4 December 1996 seven districts had a member
        # who had been elected and had not yet taken the oath, and the
        # journal holds their place without printing a name. Treated as a
        # note on the previous member, the roll yielded 392 people against
        # 399 declared seats and the shortfall looked like OCR damage. It is
        # the record saying something, so it gets a row of its own with no
        # name in it.
        # "Dist. No. 2  None" -- 1991's way of printing a seat with nobody in
        # it, where 1997 writes "Elected, not sworn". Both are the record
        # saying something and neither is a person, so both get a row with no
        # name. Three of these, plus the footnote FOOTNOTE drops, are exactly
        # the four by which the 1991 roll exceeded the Clerk's count of 388.
        if re.match(r"^(Elected|Sworn|Deceased|Resigned|Vacan|None$)",
                    part, re.I):
            out.append(("", "", part))
            continue
        bits = [b.strip() for b in part.split(",")]
        party = ""
        if len(bits) > 1 and PARTY.match(bits[-1]):
            party = bits.pop().lower().replace(" ", "")
        elif len(bits) > 1 and SHORT_CODE.match(bits[-1]):
            # "Ralph L. Akins, idr" -- r&d with the ampersand misread. Kept
            # verbatim rather than corrected: it is plainly a party code by
            # its position and length, and what it should say is a judgment
            # for a person with the page in front of them, not for this file.
            party = bits.pop().lower().replace(" ", "")
        name = ", ".join(b for b in bits if b)
        # A person's name has letters in it. What this throws out is the
        # wreckage the scan leaves behind a damaged party code: "Charles D.
        # Stritch, r?&d" is one member, and the "?&d" left over after "r" was
        # taken became a second one reading "<<&d".
        if len(re.sub(r"[^A-Za-z]", "", name)) < 2:
            continue
        out.append((name, party, ""))
    return out


def parse(identifier):
    text = reflow_path(identifier).read_text(encoding="utf-8", errors="replace")
    rows = []
    county = ""
    pending = None          # (district, seats, [text parts])

    def flush():
        if not pending:
            return
        dist, seats, parts = pending
        for name, party, note in split_members(" ".join(parts)):
            rows.append({"county": county, "district": dist, "seats": seats,
                         "name": name, "party": party, "town": "",
                         "note": note, "source": "call of the roll"})

    for line in roll_lines(text):
        m = COUNTY.match(line)
        if m:
            flush()
            pending = None
            county = m.group(1).upper()
            continue
        m = DIST.match(line)
        if m:
            flush()
            pending = (int(m.group(1)),
                       int(m.group(2)) if m.group(2) else 0,
                       [m.group(3)])
            continue
        if pending:
            pending[2].append(line.strip())
    flush()
    # Silence is not success.
    if not rows:
        sys.exit("the roll was found and yielded no member; nothing written")
    fill_sworn(text, rows)
    return rows


def fill_sworn(text, rows):
    """Put the later-sworn members into the seats the roll held open.

    Only into those seats. A COMMUNICATION naming somebody for a district
    that already has every seat named is a mid-term replacement, which is a
    different thing from a slow start and is left alone here rather than
    silently overwriting a member who served.
    """
    open_seats = {(r["county"], r["district"]): r
                  for r in rows if not r["name"]}
    if not open_seats:
        return 0
    filled = 0
    for block in re.split(r"^\s*COMMUNICATION\s*$", text, flags=re.M)[1:]:
        block = block[:2000]
        if not SWEARING.search(block):
            continue
        for county, dist, name, party, town in SWORN.findall(block):
            key = (county.upper(), int(dist))
            seat = open_seats.get(key)
            if seat is None or seat["name"]:
                continue
            seat["name"] = " ".join(name.split())
            seat["party"] = party.lower().replace(" ", "")
            seat["town"] = town.strip(" .")
            seat["source"] = "sworn later, by communication"
            filled += 1
    return filled


def write(identifier, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{identifier}.csv"
    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    return dest


def check(rows, quorum=None):
    """Seats declared against members found, per district and in total.

    Where the volume prints no seat counts -- 1991 does not -- there is
    nothing to compare per district, and the Clerk's own count of who
    answered the roll is the check instead.
    """
    by_dist = {}
    for r in rows:
        key = (r["county"], r["district"])
        by_dist.setdefault(key, [int(r["seats"] or 0), 0])[1] += 1
    seats = sum(v[0] for v in by_dist.values())
    found = sum(v[1] for v in by_dist.values())
    named = sum(1 for r in rows if r["name"])
    print(f"{len(by_dist)} districts across "
          f"{len({r['county'] for r in rows})} counties")
    if seats:
        wrong = {k: v for k, v in by_dist.items() if v[0] != v[1]}
        print(f"  seats the journal declares: {seats}")
        print(f"  members the roll yields:    {found}")
        print(f"  districts that disagree:    {len(wrong)} of {len(by_dist)}"
              f"  ({100*(len(by_dist)-len(wrong))/len(by_dist):.1f}% exact)")
        if wrong:
            print("\n  where they differ:")
            for (c, d), (s, n) in sorted(wrong.items())[:20]:
                print(f"    {c} {d}: declares {s}, yields {n}")
    else:
        print("  this volume prints no seat counts, so there is nothing to "
              "check per district")
        print(f"  seats the roll yields:      {found}")
        wrong = {}
    if quorum:
        print(f"\n  the Clerk counted:          {quorum} answering the roll")
        print(f"  this reads:                 {named} named"
              f"  ({named - quorum:+d})")
    return seats, found, wrong


def against(rows, journal_glob):
    """Every surname the General Court's digital journals record as voting.

    A name that cast a vote and is not on the roll is a failure of one of the
    two, and the digital journals are a source this project did not generate.
    Matched on surname alone: the roll prints "Thomas J. Boriso" and a roll
    call prints "Boriso, Thomas", so the given names line up differently and
    the surname is what both agree on.
    """
    files = sorted(glob.glob(f"{journal_glob}/*.txt"))
    if not files:
        sys.exit(f"nothing matched {journal_glob}/*.txt")
    # Only names inside a roll call's vote list, through the extractor that
    # was already built and scored for exactly that. Sweeping the whole
    # journal for anything shaped like a name instead counted "Health, Human
    # Services" and "Wednesday, March 12" as members who voted, which made
    # the roster look worse than it is against a yardstick that was wrong.
    import unh_measure as M
    voted = Counter()
    for f in files:
        text = open(f, encoding="utf-8", errors="replace").read()
        for _y, _n, yb, nb in M.rollcalls(text):
            for name in M.names_in(yb) + M.names_in(nb):
                voted[name.split(",")[0]] += 1
    roll = set()
    for r in rows:
        # "Thomas E. P. Rice, Jr." -> rice ; "Gene G. Chandler" -> chandler
        base = r["name"].split(",")[0].strip()
        parts = [p for p in base.split() if not p.endswith(".")]
        if parts:
            # Folded exactly as unh_measure.norm folds the vote side, or the
            # two never meet: it strips punctuation, so O'Hearn becomes
            # ohearn there and stayed o'hearn here. Three of the names this
            # check reported as missing from the roll -- O'Hearn, L'Heureux
            # and D'Allesandro -- were on it, and the apostrophe was the
            # whole of the disagreement.
            roll.add(re.sub(r"[^a-z]", "", parts[-1].lower()))
    missing = {n: c for n, c in voted.items() if n not in roll}
    hit = sum(c for n, c in voted.items() if n in roll)
    tot = sum(voted.values())
    print(f"\n{len(voted)} distinct surnames appear in {len(files)} digital "
          f"journal files, {tot:,} times")
    print(f"  on the roll:     {len(voted)-len(missing):>5} names, "
          f"{hit:>7,} mentions  ({100*hit/tot:.2f}%)")
    print(f"  not on the roll: {len(missing):>5} names, "
          f"{tot-hit:>7,} mentions  ({100*(tot-hit)/tot:.2f}%)")
    if missing:
        print("\n  the most frequent not on the roll (a miss in either source,"
              "\n  or a word that merely looks like a name):")
        for n, c in sorted(missing.items(), key=lambda kv: -kv[1])[:15]:
            print(f"    {c:>5}x  {n}")
    return hit, tot


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("identifier")
    ap.add_argument("--check", action="store_true",
                    help="seats declared against members found")
    ap.add_argument("--against", metavar="DIR",
                    help="a directory of the General Court's own journal text")
    a = ap.parse_args()

    rows = parse(a.identifier)
    dest = write(a.identifier, rows)
    print(f"{len(rows)} members -> {dest}\n")

    if a.check or a.against:
        text = reflow_path(a.identifier).read_text(encoding="utf-8",
                                                   errors="replace")
        m = QUORUM.search(text)
        check(rows, int(m.group(1)) if m else None)
    if a.against:
        against(rows, a.against)


if __name__ == "__main__":
    main()
