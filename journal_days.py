#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.2
"""
What the House journal adds that the record does not: who spoke, and what.

    python3 journal_days.py --date 2018-03-07      # one day, read out
    python3 journal_days.py --coverage             # what it finds, corpus-wide

session_days.py holds what the chamber DID, from narratives.json, and needs no
parser. This holds what was SAID, which exists only as prose in the journal.

HOUSE ONLY, AND THAT IS NOT AN OMISSION. Across all 491 Senate journal files
"spoke in favor" occurs four times and "spoke against" twice, and all six are
ordinary English inside a verbatim speech ("only four people spoke in favor").
Not one is a structural marker. The Senate journal does not record who spoke on
which side; the House journal does it 16,129 times. There is nothing here to
parse for the Senate, so this does not pretend to.

WHY THE MOTION COMES FROM THE RECORD AND NOT FROM THIS FILE

"Rep. Ohm spoke in favor" is not a fact a reader can use, because in 320 cases
the motion was Inexpedient to Legislate and the member was arguing to KILL the
bill. Of 2,934 anchored attributions, 655 -- 22% -- have a plain-English
reading that is the exact opposite of the truth. So an attribution is only ever
published ATTACHED TO ITS MOTION, and the motion is taken from session_days,
which reads it from the parsed record rather than from the sentence above it.

That also sidesteps the thing that breaks every journal parser here: where the
motion sits relative to the speech MOVED. In 1997-2000 speeches precede the
question line 338 times and follow it 66; by 2021-2026 that is 148 to 1,427.
Binding a speech to the nearest question line lands every early attribution on
the previous bill. Binding it to the vote it precedes, and taking the motion
from the record, holds in both eras.

WHAT IT REFUSES TO GUESS

An attribution that cannot be tied to one motion is reported against the bill
with that day's motions listed, and is NOT assigned to one of them. The count
of those is printed by --coverage, because a parser that quietly assigned them
would be wrong 22% of the time in the direction that matters most.
"""

import argparse
import collections
import json
import re
from pathlib import Path

HOUSE = Path("journals")

# ---------------------------------------------------------------- cleaning --
#
# EVERY PATTERN HERE IS MATCHED ON JOINED TEXT, NOT ON LINES. That is the one
# lesson that survived measuring this corpus: thirty-six of forty candidate
# line-anchored patterns were refuted, nearly all of them because the construct
# wraps. "Reps. Bartlett, Groen and Burt spoke against." routinely arrives as
# three physical lines, and a recommendation heading wraps mid-phrase.

# The running head, which lands MID-SENTENCE once columns are flattened:
# "7MARCH2018HOUSERECORD", "6 MARCH 2013 HOUSE RECORD", with or without a page
# number on either side. Absent entirely before 2013, universal from 2019.
_MON = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|"
        "NOVEMBER|DECEMBER")
FURNITURE = re.compile(
    rf"\s*\d{{0,4}}\s*\d{{1,2}}\s*(?i:{_MON})\s*\d{{4}}\s*HOUSE\s*RECORD\s*\d{{0,4}}",
    re.I)

# A word broken by the page break and resumed hyphenated on the next line.
HYPHEN_WRAP = re.compile(r"([A-Za-z])-\n([a-z])")


def clean(text):
    """The file, with the press furniture out and wrapped words rejoined."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = FURNITURE.sub(" ", text)
    text = HYPHEN_WRAP.sub(r"\1\2", text)
    return text


def joined(block):
    """A block with single newlines turned into spaces, paragraphs kept.

    A sentence in this corpus is a paragraph, not a line. Joining first is what
    makes a sentence-level pattern possible at all.
    """
    block = re.sub(r"\n{2,}", "\n\n", block)
    return re.sub(r"(?<!\n)\n(?!\n)", " ", block)


# ------------------------------------------------------------ the day block --
#
# A FILE IS NOT A DAY, and this is the trap that would lose every day's ending.
# 487 of 573 House files end on a bare centred "RECESS" with nothing after it;
# the adjournment lands at the TOP OF THE NEXT FILE under a continuation
# header. 383 files carry "moved that the House adjourn" in their first 30
# lines and only 9 in their last 60.
#
# This module does not need the adjournment, so it does not chase it across
# files. It needs the body of the day, which IS in one file. The continuation
# header at the top is the previous day's tail and is cut off.

DAY_HEADER = re.compile(
    r"^[ \t]*HOUSE\s+JOURNAL\s+N[Oo]\.?\s*(?P<num>\d*)\s*(?P<cont>\([Cc]on'?t\.?'?d?\.?\))?",
    re.M)

DATELINE = re.compile(
    r"^[ \t]*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
    r"(?P<mon>January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(?P<day>\d{1,2}),?\s*(?P<yr>\d{4})",
    re.M | re.I)

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}


def day_blocks(text):
    """[(iso_date, block)] -- the sittings in one file, continuations dropped.

    The continuation header is how the previous day's adjournment reaches this
    file. Its block belongs to the PREVIOUS date and its business is that day's,
    so it is skipped here rather than merged into the day that follows it.
    """
    out = []
    heads = list(DAY_HEADER.finditer(text))
    for i, m in enumerate(heads):
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[start:end]
        if m.group("cont"):
            continue
        d = DATELINE.search(block[:1200])
        if not d:
            continue
        mo = MONTHS.get(d.group("mon").lower())
        if not mo:
            continue
        out.append((f"{d.group('yr')}-{mo:02d}-{int(d.group('day')):02d}", block))
    return out


# --------------------------------------------------------------- the pieces --

# The bill heading that opens a bill's block. Same shape the calendars use, and
# a page break counts as the start of a line here for the same reason it does
# there: pdftotext writes one as a form feed.
BILL_HEAD = re.compile(
    r"(?:\A|[\r\n\f])[ \t\f]*"
    r"(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*)\s*,\s*",
    re.I)

# "YEAS 154 - NAYS 170" and "YEAS 232 NAYS 114". The hyphen form begins in 2013
# and the bare-space form runs 1997-2013, and both appear in 2013-2015.
#
# NOT ANCHORED, deliberately. The header is a centre-column cell and pdftotext
# puts it on a line with names from the columns beside it -- "Arsenault, Beth
# DiMartino, Lisa  YEAS 165 NAYS 124  Huot, David" is a real line. Anchoring
# with ^\s*YEAS loses 10-14% of all House roll calls.
TALLY = re.compile(r"YEAS\s+(?P<yeas>\d+)\s*-?\s*NAYS\s+(?P<nays>\d+)", re.I)

# "Rep. Ohm spoke against and yielded to questions."
# "Reps. Prout, Belcher and Perez spoke in favor."
# The names group is bounded and forbids a verb inside it, because a lazy
# .{1,200}? swallows whole sentences and emits people who never spoke.
_NAME = r"[A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+){0,3}"
SPOKE = re.compile(
    r"\bReps?\.\s+(?P<names>" + _NAME + r"(?:\s*,\s*" + _NAME + r")*"
    r"(?:\s*,?\s+and\s+" + _NAME + r")?)"
    r"\s+spoke\s+(?P<side>in\s+favor|against)\b",
    re.I)

# "Rep. Sanborn moved Ought to Pass and spoke in favor." -- 27% of modern
# speeches carry their motion inline rather than in a question line above.
MOVED_SPOKE = re.compile(
    r"\bRep\.\s+(?P<name>" + _NAME + r")\s+moved\s+(?P<motion>[^.]{3,80}?)"
    r"\s+and\s+spoke\s+(?P<side>in\s+favor|against)\b",
    re.I)

# The debate the chamber voted to keep. The heading's bill number is NOT
# trusted: journals/2026/HJ 13 May 14, 2026.txt reads "DEBATE ON HB 434" for a
# debate the motion three lines above calls SB 434, twice. Seven headings carry
# no bill number at all. The bill comes from the MOTION body.
PRINT_MOTION = re.compile(
    r"moved\s+that\s+the\s+(?:debate|remarks)\b[^.]{0,200}?"
    r"\b(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*)",
    re.I | re.S)
DEBATE_HEAD = re.compile(r"^[ \t]*DEBATE(?:\s+(?:ON|OF))?\b(?P<tail>.*)$", re.M)

# "Rep. Bean: Thank you, Mister Speaker." / "Representative Selig: ..." /
# "Speaker Chandler: ..."
SPEECH = re.compile(
    r"^[ \t]*(?P<who>(?:Rep(?:resentative)?\.?|Speaker|Deputy Speaker|"
    r"Madam Speaker|Mister Speaker)\s+" + _NAME + r")\s*:\s*(?=\S)",
    re.M)

# "Rep. Walz requested Unanimous Consent of the House regarding an apology and
# addressed the House."
UC_HEAD = re.compile(r"^[ \t]*UNANIMOUS\s+CONSENT[ \t]*$", re.M)
# The subject is what follows "regarding" or "concerning"; everything else in
# the sentence is boilerplate. Capturing "[^.]{0,160}" after the boilerplate
# returned "of the House regarding an apology and addressed the House", which
# is the sentence with its own middle removed rather than its subject.
UC_LINE = re.compile(
    r"\bRep(?:s)?\.\s+(?P<name>" + _NAME + r")\s+"
    r"(?:requested\s+Unanimous\s+Consent\s+of\s+the\s+(?:House|Senate)|"
    r"addressed\s+the\s+(?:House|Senate))"
    r"(?:\s+(?:regarding|concerning|on|about)\s+(?P<about>[^.]{2,140}?))?"
    r"\s*(?:and\s+addressed\s+the\s+(?:House|Senate))?\s*\.",
    re.I)

# A centred all-capitals line: the next section. Used only to END a block, and
# only as a hint -- leading whitespace ranges 0 to 58 across the corpus, so
# centring is never the test.
NEXT_HEAD = re.compile(r"^[ \t]{4,}[A-Z][A-Z' ’.,&-]{6,}[ \t]*$", re.M)


def _names(s):
    """The individual members named in one attribution sentence."""
    s = re.sub(r"\s+", " ", s or "").strip()
    parts = re.split(r"\s*,\s*|\s+and\s+", s)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def attributions(block):
    """[(bill_or_None, side, [names], tally_after)] in document order.

    `tally_after` is the (yeas, nays) of the NEXT vote header in the same bill
    block, which is what ties a speech to one motion rather than to the bill in
    general. Where there is none -- a voice vote, or a speech with no vote
    after it -- it is None and the caller must not guess.
    """
    out = []
    marks = [(m.start(), m.group("bill").replace(" ", "").upper())
             for m in BILL_HEAD.finditer(block)]

    def bill_at(pos):
        cur = None
        for at, b in marks:
            if at <= pos:
                cur = b
            else:
                break
        return cur

    tallies = [(m.start(), int(m.group("yeas")), int(m.group("nays")))
               for m in TALLY.finditer(block)]

    def next_bill_at(pos):
        """Where this bill's block ends -- the next bill heading, or the end."""
        for at, _b in marks:
            if at > pos:
                return at
        return len(block)

    def tally_after(pos):
        """The vote this speech precedes, or None.

        BOUNDED BY THE BILL. Without the bound this reached forward into the
        next bill and tied Rep. White's speech on a motion to reconsider --
        which failed on a VOICE vote, with no tally at all -- to a 228-102 roll
        call four bills later. A speech before no vote has no vote, and saying
        so is the whole point of this function returning None.
        """
        stop = next_bill_at(pos)
        for at, y, n in tallies:
            if pos < at < stop:
                return (y, n)
        return None

    text = joined(block)
    # Re-find on the joined text, and map positions back by searching the
    # original for the same sentence -- cheaper and safer than maintaining an
    # offset table through two substitutions.
    for m in SPOKE.finditer(text):
        frag = m.group(0)[:40]
        at = block.find(frag.split()[0])
        pos = block.find(frag) if frag in block else at
        if pos < 0:
            pos = 0
        out.append({"bill": bill_at(pos), "side": "for" if "favor" in
                    m.group("side").lower() else "against",
                    "names": _names(m.group("names")),
                    "tally": tally_after(pos), "inline_motion": None})
    for m in MOVED_SPOKE.finditer(text):
        frag = m.group(0)[:40]
        pos = block.find(frag) if frag in block else 0
        out.append({"bill": bill_at(pos), "side": "for" if "favor" in
                    m.group("side").lower() else "against",
                    "names": [m.group("name").strip()],
                    "tally": tally_after(pos),
                    "inline_motion": re.sub(r"\s+", " ", m.group("motion")).strip()})
    return out


def debates(block):
    """[(bill, [(who, speech)])] -- debates ordered printed in the journal.

    364 motions to print produce only 311 debates: 55 of them LOST. Pairing a
    motion to the next DEBATE heading in the file therefore attaches a debate
    to the wrong bill, so the bill is read from the motion nearest ABOVE each
    heading and the heading's own number is used only when there is none.
    """
    out = []
    heads = list(DEBATE_HEAD.finditer(block))
    for i, h in enumerate(heads):
        start = h.end()
        end = len(block)
        for nh in NEXT_HEAD.finditer(block, start + 40):
            end = nh.start()
            break
        if i + 1 < len(heads):
            end = min(end, heads[i + 1].start())
        body = block[start:end]

        bill = ""
        before = block[max(0, h.start() - 900):h.start()]
        ms = list(PRINT_MOTION.finditer(joined(before)))
        if ms:
            bill = ms[-1].group("bill").replace(" ", "").upper()
        if not bill:
            t = re.search(r"(HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*",
                          h.group("tail") or "", re.I)
            if t:
                bill = t.group(0).replace(" ", "").upper()

        spoken, cuts = [], list(SPEECH.finditer(body))
        for j, s in enumerate(cuts):
            stop = cuts[j + 1].start() if j + 1 < len(cuts) else len(body)
            said = joined(body[s.end():stop]).strip()
            if len(said) > 40:
                spoken.append((re.sub(r"\s+", " ", s.group("who")).strip(), said))
        if spoken:
            out.append({"bill": bill, "speeches": spoken})
    return out


def unanimous_consent(block):
    """[(name, what)] -- the remarks made under unanimous consent.

    Not bills, attached to no bill, and part of the permanent record, so they
    are carried rather than dropped. The journal usually records only THAT a
    member addressed the House and on what subject; where it carries the words
    they arrive as a printed debate instead and are found by debates().
    """
    out = []
    for h in UC_HEAD.finditer(block):
        end = len(block)
        for nh in NEXT_HEAD.finditer(block, h.end() + 20):
            end = nh.start()
            break
        seg = joined(block[h.end():end])
        for m in UC_LINE.finditer(seg):
            what = re.sub(r"\s+", " ", m.group("about") or "").strip(" ,;")
            out.append({"name": m.group("name").strip(),
                        "about": what or "addressed the House"})
    return out


_YEARS = {}


# ------------------------------------------------------------- the opening --
#
# "The House assembled at 10:00 a.m., the hour to which it stood adjourned,
# and was called to order by the Speaker."  541 of 573 files carry it.
ASSEMBLED = re.compile(
    r"The\s+(?P<ch>House|Senate)\s+(?:assembled|met|convened)\s+at\s+"
    r"(?P<t>\d{1,2}(?::\d{2})?)\s*(?P<mer>[ap])\.?\s?m\.?", re.I)

# "Representative James Creighton, member from Antrim, led the Pledge of
# Allegiance."  560 of 573 files. The member is a legislator and is named.
PLEDGE = re.compile(
    r"\b(?:Rep(?:resentative)?\.?|Sen(?:ator)?\.?)\s+(?P<who>" + _NAME + r")"
    r"[^.]{0,60}?\bled\s+the\s+Pledge", re.I)

# THE PRAYER IS NOT PUBLISHED, AND THIS IS NOT AN OVERSIGHT.
#
# The journal prints the chaplain's prayer in full, and a prayer is a pastoral
# act rather than a proceeding: the one on 6 March 2025 asks the House to "pray
# for Rep. Grossman's son, Oscar, and to pray for Shannon Girard and their
# family as they mourn the death of her husband, Christopher." That is a child,
# a bereaved widow and a dead man, named, none of them a public official and
# none of them party to any business before the House.
#
# This site's whole purpose is to make the record findable, which is exactly
# what makes republishing that different in kind from its sitting in a PDF. So
# the page records THAT a prayer was offered and never what was said, and it
# does not name the chaplain, who may be a guest rather than an officer of the
# House. The anthem singer -- "Addyson Cutter of Antrim", frequently a child --
# is not named either.
PRAYER = re.compile(r"\bPrayer\s+was\s+offered\b", re.I)


def opening(block):
    """How the day began: the hour, and the member who led the Pledge."""
    out = {}
    head = block[:6000]
    m = ASSEMBLED.search(head)
    if m:
        hh = m.group("t")
        if ":" not in hh:
            hh += ":00"
        out["assembled"] = f"{hh} {m.group('mer').lower()}.m."
    if PRAYER.search(head):
        out["prayer"] = True
    m = PLEDGE.search(head)
    if m:
        out["pledge"] = re.sub(r"\s+", " ", m.group("who")).strip()
    return out


# ------------------------------------------------------------- the absences --
#
# "Reps. Fracht, Franz, Selig and Tripp, the day, illness."
# "Rep. Grossman, the day, illness in the family."
#
# 563 of 573 files carry a LEAVES OF ABSENCE heading, and the shape has not
# moved between 1999 and 2026. The list wraps freely, so this is matched on
# joined text like everything else here.
LEAVE_HEAD = re.compile(r"^[ \t]*LEAVES?\s+OF\s+ABSENCE[ \t]*$", re.M | re.I)
# CASE-SENSITIVE, DELIBERATELY. _NAME begins with [A-Z], and under re.I that
# matches any word at all -- so the names group ran straight through the
# lower-case "the day" that is supposed to end it and swallowed the next two
# sentences with it. Three groups of absences came back as one, filed under the
# last group's reason. "Reps." and "the day" are the only spellings the journal
# uses, so the literals can carry their own case.
LEAVE_LINE = re.compile(
    r"\bReps?\.\s+(?P<names>" + _NAME + r"(?:\s*,\s*" + _NAME + r")*"
    r"(?:\s*,?\s+and\s+" + _NAME + r")?)\s*,\s*"
    r"(?P<when>the\s+day|the\s+week|the\s+session)\s*,\s*"
    r"(?P<why>[^.]{3,60})\.")


def absences(block):
    """[{names, when, why}] -- who the House excused, and on what ground.

    The ground is the chamber's own formal category -- illness, important
    business, illness in the family -- and not a diagnosis. It is parsed
    because it ends the sentence the names sit in. It is not published:
    build_session_pages prints names only, by the person's decision of 19 and
    23 September 2026.
    """
    out = []
    m = LEAVE_HEAD.search(block)
    if not m:
        return out
    end = len(block)
    nh = NEXT_HEAD.search(block, m.end() + 10)
    if nh:
        end = nh.start()
    for g in LEAVE_LINE.finditer(joined(block[m.end():end])):
        out.append({"names": _names(g.group("names")),
                    "when": re.sub(r"\s+", " ", g.group("when")).lower(),
                    "why": re.sub(r"\s+", " ", g.group("why")).strip().lower()})
    return out


# ------------------------------------------------- the consent calendar ------
#
# "HB 691-FN, prohibiting the addition of fluoridation chemicals to public
# water systems, removed by Reps. Judy Aron, Drew, ..."
#
# A bill on the consent calendar is disposed of without debate as part of one
# motion. Any member may pull one off it, and the journal names the bill and
# the members who did -- which is the only place that is recorded, and the one
# thing needed to keep a removed bill out of the consent list on the page.
CONSENT_HEAD = re.compile(r"^[ \t]*CONSENT\s+CALENDAR[ \t]*$", re.M | re.I)
REMOVED = re.compile(
    r"\b(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*)\s*,"
    r"[^.]{0,300}?\bremoved\s+by\b", re.I | re.S)
ADOPTED = re.compile(r"Consent\s+Calendar\s+was\s+adopted", re.I)


def consent(block):
    """{adopted, removed:[bill]} -- what the House did with its consent list."""
    m = CONSENT_HEAD.search(block)
    if not m:
        return {}
    end = len(block)
    nh = NEXT_HEAD.search(block, m.end() + 10)
    if nh:
        end = nh.start()
    seg = joined(block[m.end():end])
    return {"adopted": bool(ADOPTED.search(seg)),
            "removed": sorted({g.group("bill").replace(" ", "").upper()
                               for g in REMOVED.finditer(seg)})}


def read_year(year, root=HOUSE):
    """{date: found} for one calendar year, parsed once and kept.

    A YEAR IS THE UNIT, NOT A DAY. Finding one day means opening every file in
    its year, because a file holds several sittings and a sitting is not named
    by its filename -- 2026/HJ 11 April 29, 2026.txt contains the journal for
    23 April. Asked day by day across 806 sittings that is some sixteen
    thousand parses of the same twenty files; asked by year it is 573.
    """
    key = (str(root), str(year))
    if key in _YEARS:
        return _YEARS[key]
    out = {}
    d = Path(root) / str(year)
    if d.exists():
        for f in sorted(d.glob("*.txt")):
            try:
                text = clean(f.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            for iso, block in day_blocks(text):
                got = out.setdefault(iso, {"date": iso, "attributions": [],
                                           "debates": [],
                                           "unanimous_consent": [],
                                           "opening": {}, "absences": [],
                                           "consent": {}, "files": []})
                got["files"].append(f.name)
                got["attributions"] += attributions(block)
                got["debates"] += debates(block)
                got["unanimous_consent"] += unanimous_consent(block)
                got["absences"] += absences(block)
                for k, v in opening(block).items():
                    got["opening"].setdefault(k, v)
                for k, v in consent(block).items():
                    if k == "removed":
                        got["consent"].setdefault("removed", [])
                        got["consent"]["removed"] += v
                    else:
                        got["consent"].setdefault(k, v)
    _YEARS[key] = out
    return out


def read_day(date, root=HOUSE):
    """Everything this module can find for one House sitting date."""
    return read_year(date[:4], root).get(
        date, {"date": date, "attributions": [], "debates": [],
               "unanimous_consent": [], "opening": {}, "absences": [],
               "consent": {}, "files": []})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--root", default=str(HOUSE))
    a = ap.parse_args()

    if a.date:
        got = read_day(a.date, a.root)
        print(f"{a.date}: {got['files'] or 'no file holds this day'}")
        print(f"\n{len(got['attributions'])} attributions")
        for x in got["attributions"][:12]:
            t = f" before {x['tally'][0]}-{x['tally'][1]}" if x["tally"] else ""
            im = f"  [moved {x['inline_motion']}]" if x["inline_motion"] else ""
            print(f"  {x['bill'] or '?':10} spoke {x['side']:7} "
                  f"{', '.join(x['names'])[:52]}{t}{im}")
        print(f"\n{len(got['debates'])} printed debates")
        for x in got["debates"]:
            print(f"  {x['bill'] or '(no bill named)'}: {len(x['speeches'])} speeches")
            for who, said in x["speeches"][:2]:
                print(f"      {who}: {said[:88]}...")
        print(f"\n{len(got['unanimous_consent'])} under unanimous consent")
        for x in got["unanimous_consent"]:
            print(f"  {x['name']}: {x['about'][:70]}")
        return 0

    if a.coverage:
        tot = collections.Counter()
        years = collections.Counter()
        root = Path(a.root)
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.txt")):
                text = clean(f.read_text(encoding="utf-8", errors="replace"))
                blocks = day_blocks(text)
                tot["files"] += 1
                tot["days"] += len(blocks)
                for iso, block in blocks:
                    at = attributions(block)
                    db = debates(block)
                    uc = unanimous_consent(block)
                    tot["attributions"] += len(at)
                    tot["anchored"] += sum(1 for x in at if x["tally"])
                    tot["debates"] += len(db)
                    tot["speeches"] += sum(len(x["speeches"]) for x in db)
                    tot["debates_no_bill"] += sum(1 for x in db if not x["bill"])
                    tot["uc"] += len(uc)
                    years[d.name] += len(at)
        print(f"{tot['files']:,} files, {tot['days']:,} sitting days\n")
        print(f"  {tot['attributions']:7,}  attributions")
        print(f"  {tot['anchored']:7,}  of them tied to a specific vote")
        print(f"  {tot['debates']:7,}  printed debates, "
              f"{tot['speeches']:,} speeches")
        print(f"  {tot['debates_no_bill']:7,}  debates naming no bill")
        print(f"  {tot['uc']:7,}  remarks under unanimous consent")
        print("\nattributions by year:")
        for y in sorted(years):
            print(f"  {y} {years[y]:6,}")
        return 0

    ap.error("pass --date or --coverage")


if __name__ == "__main__":
    raise SystemExit(main())
