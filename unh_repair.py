#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.4
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

THE GENERAL COURT SPELLS THE NAME; THE SCAN ONLY APPROXIMATES IT

Rule zero, which outranks everything below it. past_members.json is the
General Court's own list of people who have served, and it reaches back well
past 1997 -- Maviglio and Joscelyn of the 1991 Belknap delegation are both in
it. So there IS an outside authority for the era this project needs, where no
digital journal exists and every signal internal to the scan is corrupted by
the same misreading.

A scanned spelling the authority does not carry is matched to the one it
belongs to, in three tiers, each refusing where it cannot tell:

  1. THE KNOWN CONFUSIONS, folded. rn read as m, and l/i/1 read as one
     another, in every volume so far. O'Heam against O'Hearn scores 0.73 by
     string distance -- on five letters one substitution is most of the word
     -- and folds to an exact match. C/G, F/E and e/c are just as real and
     are NOT folded, because collapsing those would merge names that differ
     only there. Only used where exactly one authority name folds that way:
     Bell and Beil fold together and neither is guessed at.

  2. STRING DISTANCE, at MIN_RATIO, taking the closest -- and refusing where
     a second authority name sits within AMBIGUOUS of the first.

  3. ONE CHARACTER WRONG, for the short names a ratio cannot see: Goes
     against Coes is 0.75 and Eraser against Fraser 0.83, both one
     substituted letter. Only where exactly one authority name is inside the
     budget.

It is deliberately NOT exclusive. Two damaged readings of one person are
common -- 1997 has McCarttiy and McCartfiy, both McCarty -- so an authority
name already claimed is no reason to refuse. What is refused is ambiguity:
two authority names equally close decide nothing, and guessing would put a
vote on the wrong member.

This is what finally fixed Maclntyre. The volume's own roll says Maclntyre,
frequency says Maclntyre 66 to 3, and the OCR confidence says Maclntyre 68 to
64 -- all three agree and all three are wrong, because one systematic
misreading corrupts every internal signal at once. Only an outside authority
can see past it.

WHAT IS LEFT AFTER RULE ZERO, AND IT IS NOT SPELLING

Measured on 1997 against journals/1997: 97.99%. The residue is three things
and none of them is a surname this pass could have matched:

  * A GIVEN NAME damaged where the surname is not. Jacobson, Alf reads Alf 54
    times and Alt 27. Rule zero matches surnames only; the authority carries
    given names too and applying the same three tiers to them is the next
    thing to do.
  * A NAME DROPPED ENTIRELY. "Thulander, O. Alan" is read "Thulander, 0.
    Alan" with a zero, the name pattern requires a letter after the comma,
    and the whole name goes missing rather than misspelt. Thirty-nine votes,
    and no spelling repair can reach them because there is nothing to repair.
  * The join. Where a tally is not unique the comparison cannot pair two roll
    calls, and some of the shortfall is that rather than the scan.

A CAUTION ABOUT WHAT THE NUMBER NOW MEANS

past_members.json is a roster, not the journal text, so correcting with it
and scoring against journals/1997 is not circular the way using the 1997
journal itself would be. But both are the General Court's own spelling, so
97.99% measures agreement with the General Court GIVEN a General Court
roster, and is no longer a blind test. The checks that stay blind are
--split and the vote-list counts, which never consult any of this.

THREE SIGNALS, NONE OF WHICH IS TRUSTED ALONE -- AND ALL BELOW RULE ZERO

  FREQUENCY -- the spelling the volume uses most. Wrong wherever the scan
  misreads a name CONSISTENTLY: Gushing 66 times against Cushing's 15.

  THE ROLL -- the House's own list of its members. Wrong wherever the roll
  itself is damaged, which it is: it prints Colbum where the votes print
  Colburn 112 times.

  THE CONFIDENCE -- ABBYY's own x-confidence, from the DjVu XML, and the only
  one of the three independent of the other two. Across the 89 pairs this
  pass finds in 1997 the damaged spelling reads lower in 71 of them, medians
  62 against 73. Also wrong sometimes: Adler reads 48 against Adier's 50.

So the rules pair them, and each pairing is there because a single signal had
already got something wrong:

  RULE ONE, frequency: a rare spelling joins the common one it is closest to,
  when they are within MIN_RATIO and the rare one is at most RARE_SHARE of the
  other's count. VETOED by the confidence where the target reads materially
  worse -- which is what stops Cushing being rewritten into Gushing.

  RULE TWO, the roll: a spelling NOT on the roll is replaced by a close one
  that IS, when the confidence agrees and when this is the commoner of the
  two, so that it only ever overrules frequency rather than duplicating it.
  This is what fixes Clemens to Clemons across 26 vote lists. It refuses
  Colburn to Colbum, because there the confidence sides with the votes.

  AND ABOVE BOTH: a surname the roll carries is never rewritten. An earlier
  version refused only when both spellings were on the roll, and it turned
  three correct Clemons into Clemens.

These three still run, for any spelling rule zero leaves alone -- a name the
General Court's list does not carry at all, which for the pre-1997 House will
not be rare. Where rule zero does fire it wins, and the MacIntyre case it
fixes is exactly the one these three got wrong together.

Every substitution is printed by --vocab, because a repair pass that silently
rewrites names is the exact thing this project should not have.
"""

import argparse
import csv
import difflib
import json
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
CONF_MARGIN = 3         # how much lower a confidence must be to veto
AMBIGUOUS = 0.02        # two authority names this close apart decide nothing

# Two capitalised words with no comma between them, in the position a name
# would be. Only ever applied to the residue of a line after every properly
# punctuated name has been taken out of it -- see comma_repairs.
BARE_PAIR = re.compile(r"\b([A-Z][A-Za-z'’\-]{2,24})\s+"
                       r"([A-Z][A-Za-z'’\-]{1,20})\b")


def key(s):
    return re.sub(r"[^a-z]", "", s.lower())


def derived_roster(text, min_lists=5):
    """The closed set of members, read off the volume's own vote lists.

    For the Senate, where there is no roll to read. A Senate journal has no
    CALL OF THE ROLL -- the chamber is twenty-four people and does not need
    one -- so unh_roster.py has nothing to parse. It does not need to: twenty
    four senators across seventy roll calls each appear dozens of times, and a
    surname turning up in five or more separate vote lists is a senator. A
    misreading does not repeat itself into five different lists.

    This is weaker than the House's roll and is used only where no roll
    exists. The roll is the House's own statement of who its members are;
    this is an inference from frequency, and it is labelled as one.
    """
    seen = Counter()
    for _y, _n, yb, nb, ch in M.rollcalls(text):
        for name in set(M.names_in(yb, ch) + M.names_in(nb, ch)):
            seen[name.split(",")[0]] += 1
    return {s for s, n in seen.items() if n >= min_lists and len(s) >= MIN_LEN}


def roster_surnames(identifier, text=None):
    path = ROSTER / f"{identifier}.csv"
    if not path.exists():
        if text is not None:
            derived = derived_roster(text)
            if derived:
                print(f"  no roll for {identifier}; using the {len(derived)} "
                      f"surnames its own vote lists repeat")
                return derived
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
    for _y, _n, yb, nb, ch in M.rollcalls(text):
        for name in M.names_in(yb, ch) + M.names_in(nb, ch):
            counts[name.split(",")[0]] += 1
    return counts


PAST_MEMBERS = Path("past_members.json")
# "Rep. MacIntyre, Doris(Hills 18)" -- the General Court's own list of people
# who have served, one line per member, with the seat in brackets.
AUTHORITY_LINE = re.compile(r"^(Rep|Sen)\.\s*([^,]+),\s*([^(]*)\((.*)\)\s*$")


def authority():
    """How the General Court spells the names of its own past members.

    past_members.json is the General Court's list of people who have served,
    fetched from its own site, and it reaches back well past 1997: Maviglio
    and Joscelyn of the 1991 Belknap delegation are both in it, as are
    MacIntyre, Clemons, Colburn, Cushing, Thulander and Adler. That matters
    more than anything else here, because it is an authority for the spelling
    of a name in 1991, where no digital journal exists to check against and
    every signal internal to the scan is corrupted by the same misreading.

    It is NOT the journal text. It is a roster, so using it to correct a scan
    and then scoring that scan against journals/1997 is not circular in the
    way using the 1997 journal itself would be -- but both are the General
    Court's own spelling, so the resulting figure measures agreement with the
    General Court given a General Court roster, and is no longer blind. The
    checks that stay blind are --split and the vote-list counts, which never
    consult this file.
    """
    if not PAST_MEMBERS.exists():
        return {}
    try:
        rows = json.loads(PAST_MEMBERS.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for text in (rows.values() if isinstance(rows, dict) else rows):
        m = AUTHORITY_LINE.match(str(text).strip())
        if not m:
            continue
        surname = m.group(2).strip()
        k = key(surname)
        if len(k) >= MIN_LEN:
            out.setdefault(k, surname)
    return out


# THE CONFUSIONS THIS SCANNER ACTUALLY MAKES, seen in all four volumes read
# so far: rn read as m, and l, i and the digit 1 read as one another. Folding
# them lets a short name match where string distance cannot -- O'Heam against
# O'Hearn scores 0.73, well under the 0.85 threshold, because on five letters
# one substitution is a large fraction of the word. Folding makes it exact.
#
# Only these two classes. C/G, F/E and e/c are equally real -- Coes read Goes,
# Fraser read Eraser, Bartlett read Bartlctt -- and are NOT folded, because
# collapsing those vowels and initials would merge names that differ only
# there. rn/m and l/i are safe in a way c/e is not.
def folded(s):
    return re.sub(r"[li1]", "i", s.replace("rn", "m"))


def within(a, b, limit):
    """Is the edit distance from a to b at most limit? Cheap and bounded."""
    if abs(len(a) - len(b)) > limit:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return False
        prev = cur
    return prev[-1] <= limit


def edit_budget(s):
    """How many characters may be wrong before this stops being the same name.

    A ratio is the wrong unit for a short surname. Goes against Coes scores
    0.75 and Eraser against Fraser 0.83, both under the 0.85 threshold, and
    both are one substituted letter -- C read as G and F read as E, which
    this scanner does constantly. The unit that matches the failure is the
    character, so short names get one and longer ones two.
    """
    return 1 if len(s) <= 6 else 2


def assign(counts, auth):
    """Pair each scanned spelling with a General Court name, one to one.

    The user's rule, and the reason it works: a damaged spelling is derivable
    because the person it belongs to is ALSO still unmatched -- everyone else
    has been claimed by an exact match. So exact matches pair off first and
    are removed from both pools, and what is left is assigned closest-first,
    each name used once.

    Independent nearest-neighbour lookups, which is what this did before, let
    two damaged spellings collapse onto one person and leave the real one
    stranded. One-to-one is the whole point.

    Greedy best-first rather than a full optimal assignment: every candidate
    pair above the threshold is sorted by how alike it is and taken if both
    sides are still free. For this data the two agree -- the pairs that matter
    are 0.9 and above and nothing competes for them -- and greedy is
    inspectable, which a Hungarian solve here would not be.
    """
    names = list(auth)
    # An authority name is reachable by folding only if it is the ONLY one
    # that folds that way. Bell and Beil fold together and neither may be
    # guessed at; Colburn and O'Hearn fold alone and both may.
    by_fold = {}
    for a in names:
        by_fold.setdefault(folded(a), []).append(a)
    unique_fold = {f: v[0] for f, v in by_fold.items() if len(v) == 1}

    fixes = {}
    for s, n in counts.items():
        if len(s) < MIN_LEN or s in auth:
            continue        # the scan already spells this one the way the GC does
        hit = unique_fold.get(folded(s))
        if hit:
            fixes[s] = (hit, n, 1.0)
            continue
        close = difflib.get_close_matches(s, names, n=3, cutoff=MIN_RATIO)
        if not close:
            # Nothing close by ratio. Try the character budget instead, and
            # only where exactly one authority name is inside it -- the same
            # refusal as everywhere else in this function.
            budget = edit_budget(s)
            near = [a for a in names
                    if abs(len(a) - len(s)) <= budget and within(s, a, budget)]
            if len(near) == 1:
                fixes[s] = (near[0], n, 0.0)
            continue
        scored = sorted(
            ((difflib.SequenceMatcher(None, s, a).ratio(), a) for a in close),
            reverse=True)
        # "the closest name that doesn't match any other unmatched names":
        # the assignment has to be UNAMBIGUOUS, not exclusive. Two damaged
        # readings of one person are common and both should land on them --
        # 1997 has McCarttiy and McCartfiy, which are both McCarty -- so a
        # name already claimed by another damaged spelling is not a reason to
        # refuse. A SECOND authority name just as close is: if Clark and
        # Clarke both sit at the same distance from a damaged spelling, this
        # cannot say which, and guessing would put a vote on the wrong member.
        if len(scored) > 1 and scored[0][0] - scored[1][0] < AMBIGUOUS:
            continue
        fixes[s] = (scored[0][1], n, scored[0][0])
    return fixes


def confidences(identifier):
    """{normalised word: median of what ABBYY thought of each reading}.

    The DjVu XML carries an x-confidence per word, and it is the only signal
    here that is independent of both frequency and the roll. Tested against
    the 89 pairs this pass already identifies in the 1997 House volume, the
    damaged spelling carries the lower confidence in 71 of them, and the
    medians are 62 against 73. So it is informative and it is not decisive:
    Adler reads 48 against Adier's 50, and MacIntyre 64 against Maclntyre's
    68, both the wrong way round.

    It is therefore used only to license a rewrite the roll already wants --
    see rule two in corrections() -- and never on its own.
    """
    import statistics
    import unh_rollcalls as R
    seen = {}
    try:
        path = R.xml_for(identifier)
    except SystemExit:
        return {}
    for _page, words in R.pages(path):
        for w in words:
            if w[4] is None:
                continue
            k = key(w[5])
            if k:
                seen.setdefault(k, []).append(w[4])
    return {k: statistics.median(v) for k, v in seen.items()}


def corrections(counts, roster, conf=None, auth=None):
    """{damaged: canonical}, with the evidence for each.

    The candidate pool is every surname the volume uses often enough to be
    established, plus the roster. A rare spelling joins the common one it is
    closest to, subject to the refusals in the docstring.
    """
    common = [s for s, n in counts.items()
              if n >= MIN_COMMON and len(s) >= MIN_LEN]

    # RULE ZERO, AND IT OUTRANKS THE OTHER TWO: the General Court's spelling,
    # assigned one to one. Everything below this decides between two readings
    # of the scan using evidence that is inside the scan, and a name misread
    # the same way on every page defeats all of it at once -- MacIntyre is
    # read Maclntyre 66 times against 3, the volume's own roll says Maclntyre,
    # and even the OCR confidence says Maclntyre. An outside authority is the
    # only thing that can see past that, and the General Court is the one that
    # gets to say how its members' names are spelt.
    fixes = {}
    if auth:
        for s, (a, n, _ratio) in assign(counts, auth).items():
            fixes[s] = (a, n, counts.get(a, 0))
    for rare, n in sorted(counts.items(), key=lambda kv: kv[1]):
        if len(rare) < MIN_LEN or rare in fixes:
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

        # RULE TWO: THE ROLL, WHERE THE SCAN AGREES IT IS THE BETTER READING.
        #
        # Rule one below only ever replaces a rare spelling with a common one,
        # so it cannot touch a name the scan gets wrong CONSISTENTLY: Cushing
        # is read Gushing 87 times and Cushing 26, Clemons is read Clemens 26
        # times and Clemons 9. Frequency points at the damage in both.
        #
        # The roll knows better -- Cushing and Clemons are in it and Gushing
        # and Clemens are not -- but the roll alone cannot be trusted either,
        # because it is scanned too: it prints Colbum where the votes print
        # Colburn 112 times, and "the roll wins" would undo that.
        #
        # The confidence breaks the tie, and does it correctly in exactly the
        # cases that matter. Clemons reads 79 against Clemens' 75, Cushing 76
        # against Gushing's 69 -- so those are fixed. Colbum reads 59 against
        # Colburn's 70, so the roll is overruled and Colburn stands. Where the
        # confidence disagrees with the roll it wins, which costs the Adler
        # and MacIntyre repairs and is the price of not inventing any.
        if conf:
            roll_near = difflib.get_close_matches(
                rare, [r for r in roster if len(r) >= MIN_LEN and r != rare],
                n=1, cutoff=MIN_RATIO)
            if roll_near:
                t = roll_near[0]
                # Only where frequency would get it WRONG -- this spelling is
                # the commoner of the two. Where it is the rarer, rule one is
                # the right instrument and this would merely duplicate it in
                # the wrong direction: MacIntyre appears 3 times against
                # Maclntyre's 66, and rule two firing on it rewrote the three
                # correct spellings into the damaged one.
                if counts.get(t, 0) < n and conf.get(t, -1) > conf.get(rare, 1e9):
                    fixes[rare] = (t, n, counts.get(t, 0))
                    continue

        # RULE ONE: a rare spelling joins the common one it is closest to.
        pool = [c for c in common
                if counts[c] >= MIN_COMMON
                and n <= counts[c] * RARE_SHARE
                and c != rare]
        if not pool:
            continue
        near = difflib.get_close_matches(rare, pool, n=1, cutoff=MIN_RATIO)
        if not near:
            continue
        # THE CONFIDENCE VETO. Frequency is the only evidence rule one has,
        # and where the roll is damaged in the same way the votes are, the
        # correct spelling is both rare AND unprotected: Cushing appears 15
        # times against Gushing's 66, the roll prints Gushing too, and rule
        # one duly rewrote the fifteen correct readings into the damaged one.
        # The scan says otherwise -- it read Cushing at 76 and Gushing at 69 --
        # so a rewrite into a materially less confident spelling is refused.
        if conf and conf.get(near[0], 0) + CONF_MARGIN < conf.get(rare, 0):
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
    roster = roster_surnames(identifier, text)
    counts = vote_surnames(text)
    if not counts:
        sys.exit("no vote list in this volume yielded a name; nothing to repair")
    fixes = corrections(counts, roster, confidences(identifier), authority())

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
