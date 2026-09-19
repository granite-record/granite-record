#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.1
"""
Let the book correct itself. No network.

    python3 unh_repair.py journalofhouseof1997newh              # write the repair
    python3 unh_repair.py journalofhouseof1997newh --vocab      # what it would change
    python3 unh_repair.py journalofhouseof1991newh

    python3 unh_measure.py --ocr data/unh/repaired/journalofhouseof1997newh.txt

WHAT IS LEFT TO FIX, AND WHY IT IS FIXABLE

After unh_rollcalls.py --reflow, the 1997 House volume carries 95.7% of the
member votes the General Court's own copy records, under the same name. The
rest is two things and neither is a lost name:

  A SPELLING THE SCAN DAMAGED.  Adler read as Adier, Colburn as Colbum,
  MacIntyre as Maclntyre, Coes as Goes, Fraser as Eraser, Burnham as Bumham,
  O'Hearn as O'Heam. That is l/i, rn/m, C/G and F/E -- the confusions of a
  2009 OCR engine on 1990s photo-offset type.

  A COMMA THE SCAN DROPPED.  Page 452 prints "Kibbey David" where every other
  line prints "Surname, Given", and the name extractor requires the comma for
  a reason measured elsewhere: letting whitespace stand in for it cost
  thirty-four points.

Both are repairable because the set of people who could possibly be named is
CLOSED and small. Four hundred members sat in that House, the journal prints
all four hundred in its own CALL OF THE ROLL, and unh_roster.py reads them
out. Against four hundred candidates "Adier" has one plausible reading.

AND THE ROSTER IS DAMAGED TOO, WHICH IS THE WHOLE TRICK

The roll at the front of the book was scanned by the same machine on the same
day, so it carries the same kind of damage: it prints Colbum, Bumham, O'Heam,
Letoumeau. A repair that simply trusted the roster would replace good
spellings with bad ones.

What saves it is that the two halves are damaged INDEPENDENTLY. Colburn's
name appears once in the roll and fifty-eight times in that year's votes; the
roll has it wrong and the votes have it right, and the reverse happens
elsewhere. So the canonical spelling is not "whatever the roster says" but
the one the whole volume prefers, and the roster's job is to say which
surnames are real people rather than how they are spelt.

THE RULE, AND WHAT IT REFUSES TO DO

A rare spelling is replaced by a common one when all of these hold:

  * they are close -- edit ratio at least MIN_RATIO;
  * the rare one is at most RARE_SHARE of the common one's count, so two
    spellings of similar frequency are left alone;
  * and NOT BOTH are in the roster. Two surnames that both appear in the
    House's own roll are two different people, however alike they look, and
    nothing here may merge them. That is the guard that keeps Lawton from
    eating Lawson.

Every substitution it makes is printed by --vocab, because a repair pass that
silently rewrites names is the exact thing this project should not have.
"""

import argparse
import csv
import difflib
import re
import sys
from collections import Counter
from pathlib import Path

import unh_measure as M

REFLOW = Path("data/unh/reflow")
ROSTER = Path("data/unh/roster")
OUT = Path("data/unh/repaired")

MIN_RATIO = 0.85        # how alike two spellings must be
RARE_SHARE = 0.34       # the rare one, as a share of the common one
MIN_LEN = 4             # short surnames are too easy to confuse
MIN_COMMON = 3          # the common spelling must be established

# Two capitalised words with no comma between them, in the position a name
# would be. Only ever applied to the residue of a line after every properly
# punctuated name has been taken out of it -- see comma_repairs.
BARE_PAIR = re.compile(r"\b([A-Z][A-Za-z'’\-]{2,24})\s+"
                       r"([A-Z][A-Za-z'’\-]{1,20})\b")


def key(s):
    return re.sub(r"[^a-z]", "", s.lower())


def roster_surnames(identifier):
    path = ROSTER / f"{identifier}.csv"
    if not path.exists():
        sys.exit(f"{path} is not there; unh_roster.py {identifier} writes it")
    out = set()
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            base = r["name"].split(",")[0].strip()
            parts = [p for p in base.split() if not p.endswith(".")]
            if parts:
                out.add(key(parts[-1]))
    if not out:
        sys.exit(f"{path} yielded no surname; nothing to repair against")
    return out


def vote_surnames(text):
    """Every surname cast in a vote list in this volume, with its count."""
    counts = Counter()
    for _y, _n, yb, nb in M.rollcalls(text):
        for name in M.names_in(yb) + M.names_in(nb):
            counts[name.split(",")[0]] += 1
    return counts


def corrections(counts, roster):
    """{damaged: canonical}, with the evidence for each.

    The candidate pool is every surname the volume uses often enough to be
    established, plus the roster. A rare spelling joins the common one it is
    closest to, subject to the refusals in the docstring.
    """
    common = [s for s, n in counts.items()
              if n >= MIN_COMMON and len(s) >= MIN_LEN]
    fixes = {}
    for rare, n in sorted(counts.items(), key=lambda kv: kv[1]):
        if len(rare) < MIN_LEN:
            continue
        # THE REFUSAL: a surname the House's own roll carries is never
        # rewritten, however rare it is in the votes and however common
        # something near it looks.
        #
        # The first version refused only when BOTH spellings were on the
        # roll, and it rewrote Clemons to Clemens. Jane A. Clemons and Kevin
        # Clemons, Sr. sat in that House and are printed in its roll; the
        # scan reads their name as Clemens in twenty-six vote lists and
        # Clemons in three, so frequency pointed the wrong way and the pass
        # turned three correct spellings into nought. Putting a real
        # legislator's name wrong is the worst thing in this project's
        # triage order, and it is worth losing repairs to avoid.
        if rare in roster:
            continue
        pool = [c for c in common
                if counts[c] >= MIN_COMMON
                and n <= counts[c] * RARE_SHARE
                and c != rare]
        if not pool:
            continue
        near = difflib.get_close_matches(rare, pool, n=1, cutoff=MIN_RATIO)
        if not near:
            continue
        fixes[rare] = (near[0], n, counts[near[0]])
    return fixes


def comma_repairs(line, roster, known):
    """Put back a comma the scan dropped, and only where it is safe.

    The line is first stripped of every name that IS properly punctuated, so
    that "Bartlett, Gordon Boyce, Robert" cannot be read as "Gordon Boyce" --
    both real names are matched and consumed, and no residue is left between
    them. Only what remains is considered, and only when its first word is a
    surname the House's roll or this volume's own votes know.
    """
    spans = [m.span() for m in M.NAME.finditer(line)]
    out, last = [], 0
    for a, b in spans + [(len(line), len(line))]:
        residue = line[last:a]
        rebuilt = residue
        for m in BARE_PAIR.finditer(residue):
            first, second = key(m.group(1)), key(m.group(2))
            if first in roster or (first in known and known[first] >= MIN_COMMON):
                # Not if the second word is itself an established surname:
                # that is two members side by side, not one name split.
                if second in roster and second not in (first,):
                    continue
                rebuilt = rebuilt.replace(
                    m.group(0), f"{m.group(1)}, {m.group(2)}", 1)
        out.append(rebuilt)
        out.append(line[a:b])
        last = b
    return "".join(out)


def apply_fixes(line, fixes):
    """Rewrite damaged surnames on this line, keeping the printed casing."""
    def sub(m):
        k = key(m.group(1))
        if k not in fixes:
            return m.group(0)
        canon = fixes[k][0]
        return m.group(0).replace(m.group(1), canon.capitalize(), 1)
    return M.NAME.sub(sub, line)


def repair(identifier, verbose=False):
    src = REFLOW / f"{identifier}.txt"
    if not src.exists():
        sys.exit(f"{src} is not there; unh_rollcalls.py --reflow {identifier} writes it")
    text = src.read_text(encoding="utf-8", errors="replace")
    roster = roster_surnames(identifier)
    counts = vote_surnames(text)
    if not counts:
        sys.exit("no vote list in this volume yielded a name; nothing to repair")
    fixes = corrections(counts, roster)

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{identifier}.txt"
    n_lines = n_commas = n_names = 0
    with dest.open("w", encoding="utf-8") as fh:
        for line in text.splitlines():
            if M.is_list_line(line) and line.strip():
                before = line
                line = comma_repairs(line, roster, counts)
                if line != before:
                    n_commas += 1
                before = line
                line = apply_fixes(line, fixes)
                if line != before:
                    n_names += 1
            n_lines += 1
            fh.write(line + "\n")
    # Silence is not success.
    if n_commas == 0 and n_names == 0:
        print("WARNING: the repair changed nothing at all. That is either a "
              "clean volume\n  or a broken pass, and the two look identical "
              "from here.", file=sys.stderr)
    print(f"{identifier}: {len(counts)} distinct surnames in vote lists, "
          f"{len(roster)} on the roll")
    print(f"  {len(fixes)} spellings judged damaged; "
          f"{n_names} lines had one rewritten, {n_commas} had a comma put back")
    print(f"  -> {dest}  ({dest.stat().st_size:,} bytes)")
    if verbose:
        print(f"\n  {'damaged':<22} {'read as':<22} seen  against")
        for rare, (canon, n, cn) in sorted(fixes.items(),
                                           key=lambda kv: -kv[1][2]):
            mark = "  (on the roll)" if rare in roster else ""
            print(f"  {rare:<22} {canon:<22} {n:>4}  {cn:>7}{mark}")
    return dest, fixes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("identifier")
    ap.add_argument("--vocab", action="store_true",
                    help="print every substitution it makes")
    a = ap.parse_args()
    repair(a.identifier, verbose=a.vocab)


if __name__ == "__main__":
    main()
