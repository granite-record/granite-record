#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.5
"""
Score what can be read out of a scanned journal. Touches no network.

    python3 unh_measure.py                # all four, in order
    python3 unh_measure.py --tallies      # do the YEAS/NAYS lines agree
    python3 unh_measure.py --names        # do the member names agree
    python3 unh_measure.py --headroom     # is a missing name damaged, or gone
    python3 unh_measure.py --split        # is a name on the right side
    python3 unh_measure.py --names --show 20   # and print the disagreements

WHAT IS BEING MEASURED, AND AGAINST WHAT

journals/1997/ holds sixteen sitting days of the 1997 House, in text, from the
General Court's own digital copy. The Internet Archive holds the same year as
a 1,156-page book scanned in 2008 and read by ABBYY FineReader 8.0. One of
those two this project did not generate, and it covers the same roll calls, so
it can say how much of the other is right.

That is the whole point of doing 1997 first. Nothing here is needed for 1997 --
the site already has it. It is needed for 1989 through 1996, where the scan is
the only copy there is and nothing exists to check it against. A number
measured on 1997 is the only honest claim that can be made about those.

TWO CHECKS, AND THE FIRST ONE NEEDS NO SECOND SOURCE

  --tallies  A roll call states its own result: YEAS 232 NAYS 114. Both texts
             print it, so the two can simply be compared.

  --names    The stated tally also says how many names must follow it. An
             extractor that finds 230 names under a heading that says 232 is
             wrong by two, and says so without anything to compare against.
             Then, where the digital copy has the same roll call, the two name
             sets are compared outright.

WHAT THE SCAN DOES TO A FOUR-COLUMN VOTE LIST, AND WHY IT MATTERS

The journals print roll calls in four columns under a county heading. The
General Court's text flattens them row by row, so a line holds four names. The
DjVu text of the scan flattens them column by column, so the reading order is
scrambled, the county headings land away from their names, and page furniture
-- a page number, a running head like "House Journal March 18, 1997" -- lands
in the middle of a vote list.

An earlier draft of this file said here that both flattenings were recoverable,
because a vote needs only the set of names under YEAS and the set under NAYS,
and neither ordering loses that. --split was written to confirm it and showed
the opposite: the totals survive and the SPLIT does not. 62% of the scan's
roll calls hold within three names of yeas+nays between them, and only 11%
have each side within three of its own heading. A roll call the House decided
186-185 comes out of this file as 232 names under YEAS and 137 under NAYS,
because the NAYS heading is itself a thing on the page with a position, and
column-major reading order puts it somewhere that is not between the two
lists.

That is the finding this whole exercise exists to produce, and it was a stop
sign. The flattened text can say what a roll call's result was -- --tallies
gets that exactly right, 53 times out of 53. It cannot say how a named member
voted. Publishing the second from this file would put the wrong members on the
wrong side of votes that are already the hardest thing on this site to check,
which is worse than publishing nothing.

AND THE GEOMETRY CLEARS IT

The item's _djvu.xml carries a bounding box per word, so the printed order can
be rebuilt: unh_rollcalls.py --reflow groups words into lines by y and sorts
each line by x, which is the whole of the fix. Point --ocr at the result and
this same code scores it:

                          flat _djvu.txt   reflowed   repaired
    names carried exactly         85.26%      95.74%     96.31%
    each side within 3              7%         87%        96%

(The flat text scored 11% on the split when it was first measured, against an
extractor that has since been generalised to a second volume. All three
numbers above come from the code as it stands, which is the only way they can
be compared.)

Same extractor, same roll calls, one difference. Reading order was worth all
of that.

AND A SECOND VOLUME, WHICH IS WHERE THE PATTERNS WERE FOUND OUT

Everything above is one book. The 1991 House volume, which is in the decade
this is actually for, scored 0% on the split when the 1997-shaped patterns
were pointed at it, and now scores 98% -- better than 1997. Four things had
been fitted to one volume without anyone noticing:

  * 1991 sets THREE columns where 1997 sets four, and is_list_line allowed
    two leftover words per line. Three names with middle initials leave three
    initials behind, the line read as prose, and the vote list ended 623
    characters into a 3,372-character block. It is a fraction now.
  * 1991 prints the comma as a full stop about half the time.
  * 1991 prints middle initials, and "Campbell, Richard H., Jr" gave a second
    person called "H., Jr".
  * both volumes carry a running head into the middle of a vote list, and
    1991's reads "76 HorsK JoruNAi, Fiohruaky 5, 19})1", out of which a name
    can be read. unh_rollcalls.py drops it by geometry now, not by wording.

What was left at 87% on 1997 was a steady undercount of a few names per list,
and it was dropped commas: page 452 prints "Kibbey David" with no comma at
all. unh_repair.py puts those back against the roster -- which is what the
closed set of four hundred members is for -- and takes the split to 96%.
Loosening this pattern to do the same job was tried and cost thirty-four
points; the comment on NAME records it so it is not tried again.
"""

import argparse
import glob
import re
import sys
from collections import Counter

# The Internet Archive's own flattened text layer, which is the thing being
# judged. --ocr points this at another rendering of the same volume -- in
# practice the one unh_rollcalls.py reflows out of the _djvu.xml -- so that
# both reading orders are scored by this identical code and the difference
# between the two numbers is reading order and nothing else.
OCR = ("archive/unh/raw/0_items_journalofhouseof1997newh_"
       "journalofhouseof1997newh_djvu.txt.a27f4e64")
DIGITAL = "journals/1997/*.txt"

TALLY = re.compile(r"YEAS\s+(\d+)\s+NAYS\s+(\d+)")
# A heading on its own that opens one side's list: "YEAS 232" / "NAYS 114".
SIDE = re.compile(r"^\s*(YEAS|NAYS)\s+(\d+)\s*$", re.M)

# Surname, Given -- with the suffixes the House prints, which are part of the
# name and not a separate field: Rice, Thomas, Jr. and Steere, Myron, III.
# The surname character class admits the mangling ABBYY produces on this
# typeface, so a misread name is COUNTED and then scored as wrong, rather
# than silently dropped and never counted at all. Phiibricl(, Donald is
# Philbrick; if the pattern refused it the name would go missing instead of
# being reported as misread, and the score would flatter the scan.
#
# THE COMMA IS REQUIRED, AND THAT COSTS REAL VOTES. The scan loses commas:
# the 1997 nay list on page 446 prints
#
#     McCarthy  William        Reidy  Frank        Burney  Carol
#
# for three members the General Court's copy spells with them, and this
# pattern drops all three. Letting two-or-more spaces stand in for the comma
# was tried, on the reasoning that the digital copy separates one name from
# the next with a single space and so would not be affected. That reasoning
# was wrong -- it is column-aligned, and wide gaps inside a line are common --
# and the measured agreement fell from 85.27% to 51.29%, because "Gordon
# Boyce" out of "Bartlett, Gordon Boyce, Robert" became a name.
#
# So the comma stays required, the dropped-comma votes stay lost, and the
# number below is honest about it. Recovering them needs the column geometry,
# which the DjVu XML has and this flattened text does not.
#
# THE SEPARATOR IS A COMMA OR A FULL STOP. 1997 prints "Hunt, John" and the
# 1991 volume of the same series prints
#
#     Hunt. John B.   Kingsbury, H. Thayer   Met/ger. Kathcrine H.
#     Pearson. Cicrtiudc B.   Perry. David M.   Riley. William A.
#
# on one line -- the comma read as a full stop about as often as not. A
# comma-only pattern finds three names there and misses three, and 1991 is
# the era this is actually for. Allowing the stop is narrow: it is one
# character in the separator position, not the two-or-more-spaces rule tried
# earlier, which matched across the boundary between two names and cost
# thirty-four points.
#
# What it does admit is "Rep. Benton" and "Dist. No", so TITLES below throws
# those out after the match rather than contorting the pattern to exclude
# them.
#
# A SURNAME'S FIRST TWO CHARACTERS ARE BOTH LETTERS, and the given name is
# never a suffix. Both rules exist because 1991 prints the middle initial and
# the pattern read the leftovers as further people:
#
#     Campbell, Richard H., Jr      gave  Campbell, Richard  AND  H., Jr
#     Rice, Thomas E. P., Jr.       gave  Rice, Thomas       AND  P., Jr.
#     Dodge, A. Gibb, Jr.           gave  Dodge, A.          AND  Gibb, Jr.
#
# which is how 1991 came to read 210 yeas where the House recorded 195. "H."
# is not a surname because its second character is a full stop; "Gibb, Jr."
# is not a person because nobody's given name is Jr. The apostrophe stays
# admissible in the second position so that O'Hearn survives.
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "2nd", "3rd"}
NAME = re.compile(
    r"\b([A-Z][A-Za-z'’\-][A-Za-z'’()\[\]\-.]{0,23})\s*[,.]\s+"
    r"([A-Z][A-Za-z'’()\[\]\-.]{0,20}\.?)"
    r"(?:\s*,\s*(Jr|Sr|II|III|IV|2nd|3rd)\.?)?")

# Not surnames, whatever follows them. "Rep." and "Reps." open most sentences
# in a journal; "Dist. No." opens every line of the roll of members.
TITLES = {"rep", "reps", "sen", "sens", "mr", "mrs", "ms", "dr", "hon",
          "dist", "no", "nos", "vol", "ch", "sec", "art", "gov", "messrs"}

# The scan drops these into the middle of a vote list. A running head matches
# NAME's shape ("Journal March" does not, but a stray "House Journal" line
# next to a county can), so they are removed before names are looked for.
# SENATE JOURNAL is here too: the reflow drops running heads by geometry, but
# the General Court's own digital Senate journals keep theirs, and one lands
# in the middle of the vote on 27 March 2003.
FURNITURE = re.compile(
    r"^\s*(?:\d{1,4}|(?:House|Senate)\s+Journal.*|Journal\s+of\s+the.*|"
    r"\d{1,4}\s+(?:House|Senate)\s+Journal.*|"
    r"(?:House|Senate)\s+Journal\s+\d{1,4})\s*$", re.M | re.I)

#
# THE SENATE DOES NOT DO ANY OF THIS
#
# Every pattern above was built for the House and none of it fires on a Senate
# volume: the 2003 Senate journal contains the word YEAS exactly zero times.
# Twenty-four members do not need four columns under county headings, so the
# Senate simply writes a sentence:
#
#     A roll call was requested by Senator Cohen.
#     Seconded by Senator Larsen.
#     The following Senators voted Yes: Below, Foster, Larsen,
#     D'Allesandro, Estabrook, Cohen.
#     The following Senators voted No: Gallus, Johnson, Kenney, Boyce,
#     Green, Flanders, Odell, Roberge, Eaton, Peterson, O'Heam, Clegg,
#     Gatsas, Barnes, Martel, Sapareto, Morse, Prescott.
#     Yeas: 6 - Nays: 18
#
# Surnames only, comma separated, wrapped as prose, and the tally printed
# AFTER the lists rather than before them. It is easier than the House in
# every respect, and the General Court's own digital Senate journals print it
# identically, so it can be scored the same way.
SENATE_MARK = re.compile(r"following\s+Senators\s+voted", re.I)
SENATE_RC = re.compile(
    r"following\s+Senators\s+voted\s+Yes\s*:\s*(.*?)"
    r"following\s+Senators\s+voted\s+No\s*:\s*(.*?)"
    r"Yeas\s*:\s*(\d+)\s*[-–]\s*Nays\s*:\s*(\d+)", re.S | re.I)
# A senator, as the Senate writes one: a surname on its own.
SENATE_NAME = re.compile(r"\b([A-Z][A-Za-z'’—\-]{1,24})\b")
# Words that appear in these lists and are not senators.
# "None." is what the Senate prints where a side has nobody on it, and it
# was being counted as a senator -- which is the whole of the +1 that both
# the scan and the General Court's own copy showed on 7 vote lists each.
SENATE_STOP = {"senate", "journal", "january", "february", "march", "april",
               "may", "june", "july", "august", "september", "october",
               "november", "december", "yeas", "nays", "the", "and",
               "following", "senators", "voted", "yes", "no", "none"}


def chamber_of(text):
    """Which chamber wrote this, from how it records a roll call."""
    return "senate" if SENATE_MARK.search(text) else "house"


def names_senate(block):
    """The senators named in one side of a Senate roll call."""
    block = FURNITURE.sub(" ", block)
    out = []
    for m in SENATE_NAME.finditer(block):
        w = re.sub(r"[^a-z]", "", m.group(1).lower())
        if w and w not in SENATE_STOP and len(w) > 1:
            out.append(w)
    return out


def rollcalls_senate(text):
    """Each Senate roll call as (yeas, nays, yea_block, nay_block)."""
    return [(int(m.group(3)), int(m.group(4)), m.group(1), m.group(2))
            for m in SENATE_RC.finditer(text)]

COUNTIES = {"BELKNAP", "CARROLL", "CHESHIRE", "COOS", "GRAFTON", "HILLSBOROUGH",
            "MERRIMACK", "ROCKINGHAM", "STRAFFORD", "SULLIVAN"}


def is_list_line(line):
    """Is this line part of a vote list rather than the journal's prose?

    Decided by what is left over. A vote list line is made of names, a county
    heading, or page furniture and nothing else; strike those out and almost
    no letters remain. A line of prose -- "Rep. Cobbin requested that the
    question be divided." -- still has most of its words afterwards.

    This rule, rather than a list of the phrases a vote list ends before,
    because the phrases differ by decade and the thing being aimed at is
    1989-1996, which nobody here has read yet. What does not change is that a
    vote list is made of names.
    """
    bare = line.strip()
    if not bare or bare in COUNTIES or FURNITURE.match(line):
        return True
    letters = len(re.sub(r"[^A-Za-z]", "", bare))
    if letters == 0:
        return True
    rest = re.sub(r"[^A-Za-z]", "", NAME.sub(" ", bare))
    # HOW MUCH OF THE LINE THE NAMES ACCOUNT FOR, not how many words are left
    # over. The first version allowed two leftover words, which is fine for
    # 1997, where a vote list reads "Bartlett, Gordon Boyce, Robert" and
    # nothing is left. 1991 prints the middle initial --
    #
    #     Maviglio, Steven R.  Rice, Thomas E. P., Jr.  Salatiello, Thomas B.
    #
    # -- so every name leaves an initial behind, three names leave three, the
    # line was ruled prose, and three such lines in a row ended the vote list
    # 623 characters into a 3,372-character block. A fraction does not care
    # how many names share a line, which is the thing that varies: 1997 sets
    # four columns and 1991 sets three.
    return (letters - len(rest)) / letters >= 0.6


def vote_list(block):
    """The head of this block that is still a vote list.

    A nay list ends where the journal goes back to reporting the sitting, and
    nothing in the text says so explicitly. Bounded here rather than in
    rollcalls(), because the same rule has to hold for a block that runs to
    the next roll call four thousand lines away.
    """
    kept = []
    prose_run = 0
    for line in block.splitlines():
        if is_list_line(line):
            prose_run = 0
            kept.append(line)
            continue
        # One stray line is a column that flattened badly; three in a row is
        # the journal talking again.
        prose_run += 1
        if prose_run >= 3:
            break
        kept.append(line)
    return "\n".join(kept)


def norm(surname, given, suffix):
    """One spelling for one person, so two sources can be compared.

    Case is folded and punctuation dropped. What is NOT done here is any
    repair of OCR damage: Phiibricl( stays Phiibricl( and is scored as a miss.
    A normaliser that quietly fixed it would be measuring itself.
    """
    def clean(s):
        return re.sub(r"[^a-z]", "", (s or "").lower())
    out = f"{clean(surname)},{clean(given)}"
    if suffix:
        out += f",{clean(suffix)}"
    return out


def names_in(block, chamber="house"):
    """Every name in the vote-list part of this block, normalised.

    The chamber is passed rather than sniffed, because a single side of a
    Senate roll call -- six surnames and a comma between each -- carries
    nothing that says which chamber it came from. rollcalls() knows, because
    it read the whole volume, so it says.
    """
    if chamber == "senate":
        return names_senate(block)
    block = FURNITURE.sub(" ", vote_list(block))
    out = []
    for m in NAME.finditer(block):
        if re.sub(r"[^a-z]", "", m.group(1).lower()) in TITLES:
            continue
        if re.sub(r"[^a-z0-9]", "", m.group(2).lower()) in SUFFIXES:
            continue
        out.append(norm(*m.groups()))
    return out


def rollcalls(text):
    """Each roll call as (yeas, nays, yea_block, nay_block, chamber).

    In the House: a 'YEAS n NAYS m' line, then a 'YEAS n' heading opening the
    yea list, then a 'NAYS m' heading opening the nay list. The nay list ends
    where the next heading of any kind begins.

    In the Senate: a sentence. See SENATE_RC.

    The chamber travels with each row so that callers holding one side of one
    roll call still know how to read the names in it.
    """
    if chamber_of(text) == "senate":
        return [(y, n, yb, nb, "senate") for y, n, yb, nb
                in rollcalls_senate(text)]
    out = []
    heads = [(m.start(), m.end(), m.group(1), int(m.group(2)))
             for m in SIDE.finditer(text)]
    for i, (start, end, side, count) in enumerate(heads):
        if side != "YEAS":
            continue
        # The matching NAYS heading is the next one, if it is a NAYS.
        if i + 1 >= len(heads) or heads[i + 1][2] != "NAYS":
            continue
        n_start, n_end, _n_side, nays = heads[i + 1]
        stop = heads[i + 2][0] if i + 2 < len(heads) else len(text)
        out.append((count, nays, text[end:n_start], text[n_end:stop], "house"))
    return out


def load_digital():
    parts = []
    for f in sorted(glob.glob(DIGITAL)):
        parts.append(open(f, encoding="utf-8", errors="replace").read())
    if not parts:
        sys.exit(f"nothing matched {DIGITAL}")
    return "\n".join(parts)


def load_ocr():
    try:
        return open(OCR, encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        sys.exit(f"{OCR} is not on disk; unh_survey.py --get fetches it")


def tallies():
    # Taken from rollcalls() rather than from a TALLY pattern of its own, so
    # that it works on a Senate volume without a second regex: the Senate
    # prints "Yeas: 6 - Nays: 18" after its lists where the House prints
    # "YEAS 232 NAYS 114" before them, and rollcalls() already knows both.
    o = Counter((str(y), str(n)) for y, n, _a, _b, _c in rollcalls(load_ocr()))
    d = Counter((str(y), str(n)) for y, n, _a, _b, _c
                in rollcalls(load_digital()))
    print(f"the scan:        {sum(o.values()):>4} roll calls, {len(o)} distinct tallies")
    print(f"{DIGITAL:<16} {sum(d.values()):>4} roll calls, {len(d)} distinct tallies")
    missing = sorted(set(d) - set(o))
    print(f"\nin the digital copy but not in the scan: {len(missing)}"
          + (f"  {missing}" if missing else ""))
    print(f"in the scan but not in the digital copy: {len(set(o) - set(d))}"
          f"  -- expected where the scan covers more sitting days")
    if missing:
        print("\nA tally the digital copy has and the scan does not means the scan "
              "misread a number. Each one is a roll call that cannot be trusted.")
    else:
        print("\nEvery tally the digital copy states, the scan states identically.")
    return len(missing) == 0


def side_counts(text, label):
    """Does the extractor find as many names as the heading says there are?"""
    exact = off = 0
    drift = Counter()
    for yeas, nays, yb, nb, ch in rollcalls(text):
        for stated, block in ((yeas, yb), (nays, nb)):
            got = len(names_in(block, ch))
            if got == stated:
                exact += 1
            else:
                off += 1
                drift[got - stated] += 1
    total = exact + off
    pct = 100 * exact / total if total else 0
    print(f"{label:<16} {exact:>4}/{total} vote lists hold exactly as many names "
          f"as their heading states  ({pct:.1f}%)")
    if drift:
        worst = ", ".join(f"{k:+d}: {v}" for k, v in sorted(drift.items())[:8])
        print(f"{'':<16} where it differs: {worst}")
    return exact, total


def unique_by_tally(rows):
    """{(yeas, nays): row} for tallies that occur exactly once in this source.

    THE TALLY IS ONLY SOMETIMES AN IDENTIFIER. In the 1997 House it nearly
    always is -- 81 distinct tallies across 82 roll calls, because 400
    members divide 400 ways. In the 2003 Senate it is not: 72 roll calls
    share 31 tallies, since twenty-four senators produce 24-0 and 13-11 over
    and over.

    Keeping the first roll call for each tally and comparing every other
    against it, which is what this did at first, silently compared unrelated
    votes and reported 89.41% agreement for the Senate -- a number about
    nothing. Dropping the ambiguous ones costs sample size and measures the
    right thing. What it does NOT do is pretend the smaller sample is the
    whole: matched counts are printed beside the percentage.
    """
    seen = Counter((y, n) for y, n, *_ in rows)
    return {(y, n): (yb, nb, ch) for y, n, yb, nb, ch in rows
            if seen[(y, n)] == 1}


def compare_names(show=0):
    ocr, dig = load_ocr(), load_digital()
    o_uni = unique_by_tally(rollcalls(ocr))
    o_by = {k: (names_in(yb, ch), names_in(nb, ch))
            for k, (yb, nb, ch) in o_uni.items()}
    d_uni = unique_by_tally(rollcalls(dig))
    matched = 0
    tot_d = tot_hit = 0
    misses = Counter()
    for key, (yb, nb, ch) in d_uni.items():
        if key not in o_by:
            continue
        matched += 1
        o_yea, o_nay = o_by[key]
        for d_names, o_names in ((names_in(yb, ch), o_yea),
                                 (names_in(nb, ch), o_nay)):
            oset = set(o_names)
            for n in d_names:
                tot_d += 1
                if n in oset:
                    tot_hit += 1
                else:
                    misses[n] += 1
    if not matched:
        sys.exit("no roll call matched between the two sources; nothing measured")
    pct = 100 * tot_hit / tot_d if tot_d else 0
    print(f"\n{matched} roll calls appear in both sources under a tally that is "
          f"unique in each,\nout of {len(rollcalls(ocr))} in the scan and "
          f"{len(rollcalls(dig))} in the digital copy. Where two roll calls "
          f"share\na tally nothing here can say which is which, so they are "
          f"left out -- see\nunique_by_tally. In the Senate that is most of "
          f"them, and the sample is small.")
    print(f"Of {tot_d:,} member votes the General Court's copy records, the scan "
          f"carries {tot_hit:,} under the same name -- {pct:.2f}%.")
    print(f"{tot_d - tot_hit:,} do not match, over {len(misses)} distinct names.")
    if show and misses:
        print(f"\nThe {min(show, len(misses))} most frequent, as the digital copy "
              f"spells them:")
        for name, n in misses.most_common(show):
            print(f"  {n:>3}x  {name}")
    return pct


def split_check():
    """The names are nearly all there. The trouble is which side they are on.

    This is the finding that decides whether the flattened text is usable, so
    it is a check rather than a paragraph. For each roll call it compares the
    number of names found against yeas+nays -- ignoring the split -- and then
    against the split itself. If the totals are right and the split is not,
    the scan has the votes and the flattening has lost the one thing a vote
    means.
    """
    rows = []
    for yeas, nays, yb, nb, ch in rollcalls(load_ocr()):
        got_y, got_n = len(names_in(yb, ch)), len(names_in(nb, ch))
        rows.append((yeas + nays, got_y + got_n, yeas, got_y, nays, got_n))
    if not rows:
        sys.exit("no roll call parsed from the scan; nothing measured")
    tot_ok = sum(1 for t, g, *_ in rows if abs(g - t) <= 3)
    split_ok = sum(1 for _t, _g, y, gy, n, gn in rows
                   if abs(gy - y) <= 3 and abs(gn - n) <= 3)
    n = len(rows)
    print(f"{n} roll calls in the scan.")
    print(f"  the TOTAL number of names is within 3 of yeas+nays:  "
          f"{tot_ok:>3}  ({100*tot_ok/n:.0f}%)")
    print(f"  and each SIDE is within 3 of its own heading:        "
          f"{split_ok:>3}  ({100*split_ok/n:.0f}%)")
    # Reported from the numbers, not narrated. The first version of this
    # printed a fixed paragraph saying the split was lost -- true of the
    # flattened text it was written against, and false the moment --ocr was
    # pointed at the reflow, where the same measurement reads 87%.
    if split_ok < n * 0.5:
        print(f"\n  The names are here and the SPLIT IS NOT. A parser on this "
              f"text would\n  publish confident, wrong votes against named "
              f"members, which is worse\n  than publishing none. The column "
              f"geometry that settles it is in the\n  item's _djvu.xml; "
              f"unh_rollcalls.py --reflow reads it.")
    else:
        print(f"\n  Both sides survive this reading order. What is left is a "
              f"steady small\n  undercount rather than a scramble -- names the "
              f"extractor does not pick\n  up, not names on the wrong side of "
              f"the vote.")
    worst = sorted(rows, key=lambda r: -abs(r[3] - r[2]))[:5]
    print(f"\n  the five worst splits:")
    for t, g, y, gy, nn, gn in worst:
        print(f"    stated {y:>3}-{nn:<3}  read as {gy:>3}-{gn:<3}"
              f"   (total {t} vs {g})")
    return split_ok, n


def headroom(show=0):
    """How much of the shortfall is a misread name rather than a lost one.

    Not a repair, and deliberately not one. It answers a different question:
    when the scan fails to carry a vote under the right name, is the name
    nearby-but-damaged, or gone? Those need different work and only one of
    them is cheap, so the number decides whether this is worth doing.

    Generic string distance is used here rather than a match against the
    roster of that House, which is what a real repair would use and would do
    better. This is therefore a FLOOR on what is recoverable, not a forecast.
    """
    import difflib
    ocr, dig = load_ocr(), load_digital()
    o_by = {k: (names_in(yb, ch), names_in(nb, ch))
            for k, (yb, nb, ch) in unique_by_tally(rollcalls(ocr)).items()}
    tot = hit = near = 0
    pairs = Counter()
    for k, (yb, nb, ch) in unique_by_tally(rollcalls(dig)).items():
        if k not in o_by:
            continue
        o_yea, o_nay = o_by[k]
        for d_names, o_names in ((names_in(yb, ch), o_yea),
                                 (names_in(nb, ch), o_nay)):
            oset = set(o_names)
            for name in d_names:
                tot += 1
                if name in oset:
                    hit += 1
                    continue
                m = difflib.get_close_matches(name, oset, n=1, cutoff=0.82)
                if m:
                    near += 1
                    pairs[(name, m[0])] += 1
    if not tot:
        sys.exit("nothing matched between the two sources; nothing measured")
    print(f"{tot:,} member votes in the General Court's copy")
    print(f"  the scan has the name exactly:   {hit:>6,}  {100*hit/tot:6.2f}%")
    print(f"  the scan has it damaged:         {near:>6,}  {100*near/tot:6.2f}%")
    print(f"  the scan does not have it:       {tot-hit-near:>6,}  "
          f"{100*(tot-hit-near)/tot:6.2f}%")
    print(f"\n  A name-repair pass against the roster of that House therefore "
          f"starts from\n  {100*(hit+near)/tot:.2f}% and would do better than "
          f"that, because it matches against\n  four hundred known members "
          f"rather than against whatever the scan produced.")
    # What the unreachable share actually is, counted rather than asserted.
    # This line used to claim it was "mostly commas the scan dropped"; the
    # count below was written to back that up and refuted it -- on the
    # flattened text the figure was 3.2%, not most of it.
    print(f"  The {100*(tot-hit-near)/tot:.2f}% it cannot reach is not damaged "
          f"spelling. It is names this\n  rendering does not carry in a form "
          f"the extractor recognises at all.")
    if show and pairs:
        print(f"\nWhat the damage is:")
        for (d, o), c in pairs.most_common(show):
            print(f"  {c:>3}x  {d:<28} read as  {o}")
    return 100 * (hit + near) / tot


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tallies", action="store_true")
    ap.add_argument("--names", action="store_true")
    ap.add_argument("--headroom", action="store_true",
                    help="is a missing name damaged, or gone")
    ap.add_argument("--split", action="store_true",
                    help="are the names on the right side of the vote")
    ap.add_argument("--show", type=int, default=0,
                    help="print this many of the names that did not match")
    ap.add_argument("--ocr", metavar="PATH",
                    help="score this rendering of the volume instead of the "
                         "Internet Archive's flattened text layer")
    ap.add_argument("--digital", metavar="GLOB",
                    help="check against this directory of the General Court's "
                         "own journal text instead of journals/1997")
    a = ap.parse_args()
    if a.digital:
        global DIGITAL
        DIGITAL = a.digital.rstrip("/") + "/*.txt" if "*" not in a.digital else a.digital
        print(f"checking against {DIGITAL}")
    if a.ocr:
        global OCR
        OCR = a.ocr
        print(f"scoring {OCR}\n")
    if not (a.tallies or a.names or a.headroom or a.split):
        a.tallies = a.names = a.headroom = a.split = True

    if a.tallies:
        print("=== THE STATED RESULT ===")
        tallies()
        print()

    if a.names:
        print("=== THE NAMES UNDER IT ===")
        print("First, without any second source: a vote list must hold as many")
        print("names as its own heading says.\n")
        side_counts(load_digital(), "the digital copy")
        side_counts(load_ocr(), "the scan")
        print("\nThen, against the copy this project did not generate:")
        compare_names(show=a.show)
        print()

    if a.headroom:
        print("=== IS A MISSING NAME DAMAGED, OR GONE ===")
        headroom(show=a.show)
        print()

    if a.split:
        print("=== AND WHICH SIDE WAS IT ON ===")
        split_check()


if __name__ == "__main__":
    main()
