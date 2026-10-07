#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.12
"""
What the House journal adds that the record does not: who spoke, and what.

    python3 src/parse/journal_days.py --date 2018-03-07      # one day, read out
    python3 src/parse/journal_days.py --coverage             # what it finds, corpus-wide

session_days.py holds what the chamber DID, from narratives.json, and needs no
parser. This holds what was SAID, which exists only as prose in the journal.

HOUSE ONLY, AND THAT IS NOT AN OMISSION. Across all 491 Senate journal files
"spoke in favor" occurs four times and "spoke against" twice, and all six are
ordinary English inside a verbatim speech ("only four people spoke in favor").
Not one is a structural marker. The Senate journal does not record who spoke on
which side; the House journal does it 16,129 times. There is nothing here to
parse for the Senate, so this does not pretend to. The one exception is the
Senate's leave list -- who it excused for the day -- which read_senate_day
reads from each sitting's opening.

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

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import bisect
import collections
import json
import re

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
# Each run of white space taken whole (\s*+): none of what follows one can be
# white space, so giving any back never makes a match, and trying to -- at
# every point of the long runs of spaces a centred line is -- took five
# minutes of every read of the journals. The same matches in all 573 files.
FURNITURE = re.compile(
    rf"\s*+\d{{0,4}}\s*+\d{{1,2}}\s*+(?i:{_MON})\s*+\d{{4}}\s*+HOUSE\s*+RECORD\s*+\d{{0,4}}",
    re.I)

# A word broken by the page break and resumed hyphenated on the next line.
HYPHEN_WRAP = re.compile(r"([A-Za-z])-\n([a-z])")


def clean(text, lines=False):
    """The file, with the press furniture out and wrapped words rejoined.

    With `lines`, A RUNNING HEAD BETWEEN TWO LINES LEAVES THE LINE BREAK IT
    SAT IN. Taken out with the breaks around it, it glues a page's first line
    to the last line of the page before, and a bill heading that opens a page
    stops being at the start of a line: "and the majority committee report
    was adopted. HB 422-FN, increasing penalties ..." (13 February 2025). Its
    speeches were read as the bill before's, and HB 334's page had Rep.
    Donnelly speaking for a motion she spoke on under HB 422. The speeches
    are read with the lines kept (read_year); the debates, the leave list and
    the consent calendar, which were measured without them, are not yet.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = FURNITURE.sub((lambda m: "\n" if re.search(r"[\n\f]", m.group(0)) else " ")
                         if lines else " ", text)
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
# A SPEAKER'S NAME HOLDS NO VERB AND NO TITLE. Matched without regard to case,
# a "name" of four words was "Mirski moved Recommit and" -- the sentence that
# MOVED_SPOKE reads -- and, where a roll call's columns share the line,
# "Prudhomme-O'Brien spoke against. Hunt" (2016); and "Rep. Sweeney Rep.
# spoke in favor" (8 January 2026) named a Rep. "Sweeney Rep". 44 such
# fragments stood on the pages beside the member they repeat.
_SWORD = r"(?!(?:spoke|moved|Reps?)\b)[A-Z][A-Za-z.'’-]+"
_SNAME = _SWORD + r"(?:\s+" + _SWORD + r"){0,3}"
SPOKE = re.compile(
    r"\bReps?\.\s+(?P<names>" + _SNAME + r"(?:\s*,\s*" + _SNAME + r")*"
    r"(?:\s*,?\s+and\s+" + _SNAME + r")?)"
    r"(?:\s+Reps?\.)?\s+spoke\s+(?P<side>in\s+favor|against)\b",
    re.I)

# "Rep. Sanborn moved Ought to Pass and spoke in favor." -- 27% of modern
# speeches carry their motion inline rather than in a question line above.
# The name is a speaker's name (_SNAME), as SPOKE's is: read with _NAME it ran
# back over the right-aligned signature of the committee statement above --
# "Rep. Leah Cushman" -- and the blank line, and made one speaker of two,
# "Leah Cushman Rep. Cannon", on the side Rep. Cushman argued against (HB 264,
# 4 January 2024; sixteen such names on the pages of 2016-2024). And a comma
# before "spoke" is the same sentence: "Rep. Alukonis moved that the House
# concur, spoke in favor" (HB 1268, 25 April 2002), read by neither pattern,
# left five movers of 2002-2020 named on no motion.
MOVED_SPOKE = re.compile(
    r"\bRep\.\s+(?P<name>" + _SNAME + r")\s+moved\s+(?P<motion>[^.]{3,80}?)"
    r"(?:\s*,|\s+and)\s+spoke\s+(?P<side>in\s+favor|against)\b",
    re.I)

# A MOTION MADE AFTER THE SPEECH IS NOT WHAT THE SPEECH WAS ON. The vote a
# speech precedes ties it to a motion (attributions, below), and the House
# often puts another motion between the two: "Rep. Arndt moved that the House
# concur and spoke in favor. ... Rep. Rice moved that the request for
# concurrence with amendment on HB 374 ... be laid on the table. ... YEAS 62
# NAYS 273" (9 June 1999). The roll call is on Rep. Rice's motion, made after
# Rep. Arndt spoke for concurring, and by its count alone that speech was
# "for" tabling the bill. So every motion moved between a speech and the vote
# after it is kept with the speech (`moved_since`), in the journal's words,
# and the page does not credit a speech to a motion of a kind that was only
# made after it (build_session_pages.made_after).
#
# Read from the end of the speech's own sentence, so "Rep. Mock moved Re-commit
# to Committee and spoke in favor" (14 April 1999) does not count its own
# motion.
#
# A motion's words run to the period that ends a line, not to the first
# one: a constitutional amendment's title holds a period -- "Rep. Hutchinson
# moved that CACR 34, relating to the definition of marriage. Providing that
# marriage between one man and one woman ..., be laid on the table."
# (21 March 2006) -- and read to it the motion was to do nothing.
MOVED_SINCE = re.compile(
    r"\bmoved\b\s*(?P<what>(?:[^.]|\.(?![ \t]*(?:\n|$))){0,700})", re.I)
SPOKE_END = re.compile(r"\bspoke\s+(?:in\s+favor|against)\b", re.I)

# WHAT DECIDED THE QUESTION A SPEECH WAS ON, where the journal prints it
# before the roll call that follows the speech. A roll call is not the only
# way a question closes: "The question being adoption of floor amendment
# (0786h). Rep. Read spoke in favor. Floor amendment (0786h) failed." and only
# then the roll call on the report, 184-183 (HB 94, 6 March 2025), which
# Rep. Read's speech was read as preceding; and a division -- "On a division
# vote, with 160 members having voted in the affirmative, and 191 in the
# negative, the amendment failed" (SB 624, 14 May 2026) -- names no one and
# was not read at all. The division's count is session_days.JOURNAL_DIVISION's
# pattern; a question decided by voice is a sentence that names what was put
# (an amendment, a report, a motion) and says it carried or lost.
# Three more wordings the journal prints a division in: no "and" before the
# negative ("185 members having voted in the affirmative, 107 in the
# negative", HB 503 of 25 April 2001), no space after the comma ("On a
# division vote,273 members", HB 311 of 2003), and "having spoken in the
# affirmative" (HB 405 of 15 January 1998). Unread, the division decided
# nothing, and six counts the journal prints were held to be printed nowhere.
DIVISION = re.compile(
    r"division\s+vote,?\s*(?:with\s+)?(?P<yeas>\d+)\s+members?\s+(?:having\s+)?"
    r"(?:vot|spok)\w*\s+in\s+the\s+affirmative,?\s+(?:and\s+)?(?P<nays>\d+)", re.I)
# The verdict can stand alone, as it does through 2012: "Rep. Quandt spoke
# against. Rep. Fields spoke in favor. Adopted." (SCR 6, 31 May 2000).
# A page break can stand before it: "Rep. John Flanders moved the previous
# question. \fMotion adopted." (HB 1692, 22 March 2006).
DECIDED = re.compile(
    r"(?:^|(?<=[.;]\s)|(?<=\n))[ \t\f]*(?P<s>"
    r"(?:Adopted|Failed|Carried|Prevailed|Lost)\b[^.;]{0,80}\."
    r"|(?=[A-Z])[^.;]{0,120}?"
    r"\b(?i:amendment|report|motion|reconsideration|ought\s+to\s+pass|sections?|"
    r"remainder)\b[^.;]{0,60}?\b(?i:adopted|failed|prevailed|carried|defeated|lost)\b"
    r"[^.]{0,160}\.)")
# Nor a roll call's own outcome, joined to the last names of its list: "Osgood,
# Philip Sr    Converse, Larry ... and the committee report was adopted."
# (CACR 19, 23 March 2005), "Jillette, Arthur Jr and the motion failed." (SB
# 235, 16 May 2007), read as the next question decided by voice.
NOT_DECIDED = re.compile(
    r"\b(?:moved|requested|question|spoke|yielded|division|YEAS|NAYS)\b|"
    r"(?-i:[A-Z][a-z'’-]+,\s+[A-Z][a-z]+(?:\s+\w+)?\s+[A-Z][a-z'’-]+,\s+[A-Z])|"
    r"(?-i:^(?!(?:Adopted|Failed|Carried|Prevailed|Lost|Motion|Report|Amendment|Majority|"
    r"Minority|Committee|Floor|Reconsideration)\b)[A-Z][\w'’.-]*(?:,\s+[A-Z][\w'’.-]*"
    r"(?:\s+[A-Z][\w'’.-]*)?)?\s+and\s+the\b)", re.I)

# WHAT COMES BETWEEN A SPEECH AND ITS DECISION, AND WHAT IT DOES TO THE TIE.
# The speech's question is the one the journal decides next -- unless another
# question is put first. A motion made or an amendment offered after the
# speech, an appeal of the chair's ruling, a withdrawal: each puts a question
# of its own, and the next decision is that question's. Read past one, a
# speech was put on whatever was decided after it: on 15 February 2012 Rep.
# Rowe spoke for HB 1670's committee amendment, a Call of the House was
# moved, the amendment carried 177-99 on a division, and Rep. Vaillancourt
# then offered floor amendment 0725h, lost 96-179 on the roll call -- under
# which the page named Rep. Rowe, because a "moved" stood between his speech
# and the 177-99 and the speech fell through to the next roll call.
#
# Two kinds are read through, because the record says where the question
# then stands:
#   - a Call of the House, or a quorum, decides nothing;
#   - the previous question, or a motion to limit or extend debate, decides
#     only whether debate goes on, and the decision printed straight after it
#     is its own where it plainly is -- a bare verdict, or one that names the
#     limit on debate ("Rep. John Flanders moved the previous question.
#     Adopted. Floor amendment (1206h) failed.", HB 2, 20 April 2005); a roll
#     call the journal does not label may be either question's, and ties the
#     speech to nothing (HB 1570, 20 March 2014).
# And one is read past when it fails: a motion to table, postpone, make a
# special order, recommit, refer or divide sets the question aside if it
# carries and leaves it standing if it does not -- HR 20's report was
# debated, a motion to table it failed on a division, and the roll call that
# followed, 162-179, was on the report (23 March 2000).
# Anything else, or anything not read for certain, ties the speech to
# nothing: the page names its speaker as having spoken during the bill.
MOTION_EVENT = re.compile(
    r"\b(?:moved|offered|appealed|challenged)\b"
    r"|\bwithdrew\s+(?:his|her|their|the)\s+(?:floor\s+)?(?:amendment|motion)\b"
    r"|\brequested\s+that\s+(?:the\s+question|sections?\b)[^.]{0,80}?\bdivided\b",
    re.I)
CALL_OF_HOUSE = re.compile(r"^moved\s+(?:a|the)\s+call\s+of\s+the\s+house\b", re.I)
CLOSES_DEBATE = re.compile(
    r"^moved\s+(?:(?:the|a)\s+)?previous\s+question\b|^moved\s+(?:to|that)\s+(?:the\s+)?"
    r"(?:limit|extend)\w*\s+(?:the\s+)?debate\b|^moved\s+that\s+(?:the\s+)?debate\s+"
    r"(?:on\s+[^.]{0,120}?\s+)?(?:now\s+)?be\s+(?:limited|extended)\b", re.I)
# A motion to print remarks, a debate or an inquiry in the journal decides
# nothing about the question either: "Rep. William O'Brien moved that the
# Parliamentary Inquiry made by Rep. Hoell and the answer by Speaker Jasper be
# printed in the Permanent Journal. Without objection, the Speaker so
# ordered. ... The question now being adoption of the majority committee
# report" (HB 1696, 10 February 2016). The question put again after it is the
# speech's; a bare verdict straight after it is its own; anything else ties
# the speech to nothing.
PRINTS = re.compile(r"^moved\s+that\s+.{0,300}?\bbe\s+printed\b", re.I | re.S)
QUESTION_PUT = re.compile(r"\bquestion\s+(?:now\s+)?being\b", re.I)
OUT_OF_ORDER = re.compile(r"\bruled\b[^.]{0,80}\bout\s+of\s+order\b", re.I)
ITS_DECISION = re.compile(
    r"previous\s+question|limit\w*\s+debate|debate\s+(?:now\s+)?be\s+limited|"
    r"extend\w*\s+debate|debate\s+(?:was\s+)?(?:limited|extended)", re.I)
BARE_VERDICT = re.compile(
    r"^(?:(?:The\s+)?motion\s+(?:was\s+)?)?(?:Adopted|Failed|Carried|Prevailed|Lost)\b"
    r"[^.]{0,20}\.?$", re.I)
SUBSIDIARY = re.compile(
    r"\b(?:laid\s+on\s+the\s+table|lay\b[^.]{0,80}?\bon\s+the\s+table|tabled?|"
    r"postpon\w*|special\s+order\w*|re-?\s*commit\w*|re-?\s*refer\w*|referred|"
    r"interim\s+study|divided)\b", re.I)
NOT_SUBSIDIARY = re.compile(
    r"\breconsider|\b(?:non-?\s*)?concur|\b(?:remove\w*|taken?)\s+from\s+the\s+table|"
    r"\bvacate|\bsuspend|\brecess|\badjourn", re.I)
# Only a motion of these is carried by more yeas than nays; a special order can
# need two thirds, so it is read as carried only where the journal says so.
MAJORITY_SUBSIDIARY = re.compile(
    r"\b(?:laid\s+on\s+the\s+table|lay\b[^.]{0,80}?\bon\s+the\s+table|tabled?|"
    r"postpon\w*|re-?\s*commit\w*|re-?\s*refer\w*|referred|interim\s+study|divided)\b",
    re.I)
CARRIED_WORDS = re.compile(r"\b(?:adopted|prevailed|carried|passed)\b", re.I)
LOST_WORDS = re.compile(r"\b(?:failed|lost|defeated)\b", re.I)
# A bare "Adopted." decides the question pending at the speech, and that is an
# amendment where one was offered or put since the last decision: "Rep.
# Emerton offered floor amendment (0929h). ... Rep. Emerton spoke in favor.
# Adopted." (HB 1563, 5 March 1998) is the amendment adopted, not the report.
AMENDMENT_PENDING = re.compile(
    r"\boffered\b[^.]{0,80}\bamendment|\bquestion\s+(?:now\s+)?being\s+(?:the\s+)?"
    r"adoption\s+of\s+(?:the\s+)?floor\s+amendment|^\s*Floor\s+Amendment\s*\(", re.I | re.M)


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
    """The individual members named in one attribution sentence.

    A comma before the "and" is read as one separator: "Reps. Nancy Wall, and
    Dickinson spoke in favor" (14 April 1999) put a member called "and
    Dickinson" on the page.
    """
    s = re.sub(r"\s+", " ", s or "").strip()
    parts = re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", s)
    out = []
    # A dangling "and" is the journal's own slip -- "Reps. Abramson and
    # Comtois and spoke against." (HB 2, 27 June 2019), "Rep. Stevens and
    # spoke in favor." (HB 643, 15 June 2005) -- and not part of a name.
    for p in (re.sub(r"\s+and$", "", p.strip(" .")) for p in parts):
        # "Rep. W. Douglas Scamman, Jr spoke against" (9 April 2009) is one
        # member, and the comma made a second called "Jr".
        if p and not (out and re.fullmatch(r"(?:Jr|Sr|II|III|IV)", p)):
            out.append(p)
    return out


# A RECONSIDERATION OF ANOTHER BILL ENDS THE BILL BEFORE IT. "Having voted with
# the prevailing side, Rep. Bickford moved that the House reconsider its action
# whereby it voted HB 737, ..." opens no bill heading, so the speeches on it
# were read as the previous bill's: on 14 April 1999 the five members who
# spoke on HB 737's reconsideration, and its 120-225 roll call, were put on
# HB 605, which the House had just sent back to committee on a voice vote --
# and the same sentence did it on dozens of days of 1998-2026. What follows
# one, up to the next bill heading, is no bill's: it is not ALWAYS the bill it
# names, because unheaded business can follow it before the next heading (on
# 23 April 1998 Rep. Kurk spoke on vacating SB 428's reference, after HB
# 1520's reconsideration). A bill's reconsideration of itself is its own, as
# it was.
RECONSIDER = re.compile(
    r"(?:\bReps?\.\s+" + _NAME + r"\s+)?\bmoved\s+that\s+the\s+House\s+"
    r"reconsider\s+its\s+action\s+whereby\s+it\b[^.]{0,250}?"
    r"\b(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*)",
    re.I | re.S)


# A COMMITTEE OF CONFERENCE REPORT OPENS ITS BILL'S STRETCH. Its section is
# headed "COMMITTEE OF CONFERENCE REPORT ON SB 449" and opened "Committee of
# Conference Report on SB 449, relative to ...", and neither is a bill heading,
# so its speeches were read as the bill before's: on 25 May 2004 Reps. Hagan
# and Paul Harrington spoke against SB 449's report and were named on SB
# 478's. Every House journal of 1997-2026 prints its conference reports this
# way, and none opens one with a bill heading.
CONFERENCE_HEAD = re.compile(
    r"(?:\A|[\r\n\f])[ \t\f]*committee\s+of\s+conference\s+report\s+on\s+"
    r"(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*)\b", re.I)


# AND A RESOLUTION OFFERED FROM THE FLOOR ENDS THE BILL BEFORE IT: "Reps.
# Wallner and Whalley offered the following: RESOLVED, that the House adopt
# amendments to House Rules 30 and 64." follows HB 87 on 31 January 2007 with
# no heading of its own, and the two who spoke for it were named on HB 87's
# report.
RESOLUTION_OFFERED = re.compile(r"\boffered\s+the\s+following\s*:?\s*RESOLVED\b", re.I)


def bill_marks(block):
    """[(position, bill or None)] in order: each bill heading or conference
    report's heading, and each reconsideration of a bill other than the one
    whose stretch it falls in, or resolution offered from the floor, which
    starts a stretch that is no bill's."""
    marks = sorted([(m.start(), m.group("bill").replace(" ", "").upper())
                    for m in BILL_HEAD.finditer(block)]
                   + [(m.start(), m.group("bill").replace(" ", "").upper())
                      for m in CONFERENCE_HEAD.finditer(block)], key=lambda x: x[0])
    base = lambda b: (b or "").split("-")[0]
    ends = []
    for m in RECONSIDER.finditer(block):
        cur = None
        for at, mb in marks:
            if at <= m.start():
                cur = mb
            else:
                break
        if cur and base(cur) != base(m.group("bill").replace(" ", "").upper()):
            ends.append((m.start(), None))
    ends += [(m.start(), None) for m in RESOLUTION_OFFERED.finditer(block)]
    return sorted(marks + ends, key=lambda x: x[0])


def attributions(block):
    """[(bill_or_None, side, [names], tally_after)] in document order.

    `tally_after` is the (yeas, nays) of the NEXT vote header in the same bill
    block, which is what ties a speech to one motion rather than to the bill in
    general. Where there is none -- a voice vote, or a speech with no vote
    after it -- it is None and the caller must not guess. `decided` is what
    the journal prints as deciding the speech's question where that is not
    the roll call -- a division, a later roll call, or a question carried or
    lost by voice -- and then it, and not `tally`, is the speech's; or that
    another question was put first and nothing is (`untied`): decided().
    build_session_pages.claims reads it.
    """
    out = []
    marks = bill_marks(block)

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
        """Where this bill's block ends -- the next bill heading or
        reconsideration of another bill (bill_marks), or the end."""
        for at, _b in marks:
            if at > pos:
                return at
        return len(block)

    def tally_after(pos, at=False):
        """The vote this speech precedes, or None; with `at`, where the
        journal prints it instead.

        BOUNDED BY THE BILL. Without the bound this reached forward into the
        next bill and tied Rep. White's speech on a motion to reconsider --
        which failed on a VOICE vote, with no tally at all -- to a 228-102 roll
        call four bills later. A speech before no vote has no vote, and saying
        so is the whole point of this function returning None.
        """
        stop = next_bill_at(pos)
        for where, y, n in tallies:
            if pos < where < stop:
                return where if at else (y, n)
        return None

    # EACH SPEECH WHERE IT IS. The sentences are matched on the block with its
    # single line breaks made spaces, which leaves every character where it
    # was, so a match's own position is the speech's. They were found again in
    # the block by their first forty characters, which is the FIRST sentence
    # that begins the same way: Rep. Verville's second "spoke in favor" of
    # 5 June 2025 was read at his first, and took that motion's 217-164.
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", block)
    divisions = [(m.start(), (int(m.group("yeas")), int(m.group("nays"))), m.end())
                 for m in DIVISION.finditer(block)]
    voices = [(m.start("s"), re.sub(r"\s+", " ", m.group("s")).strip(), m.end("s"))
              for m in DECIDED.finditer(text) if not NOT_DECIDED.search(m.group("s"))]

    def _motion(m):
        """("move", at, (verb, words), end): a motion's own words, read past a
        period inside a title (MOVED_SINCE), from "moved" to the end of its
        sentence, which is where what follows it begins."""
        verb = m.group(0).lower()
        if verb != "moved":
            return "move", m.start(), (verb, m.group(0)), m.end()
        w = MOVED_SINCE.match(block, m.start())
        return ("move", m.start(), (verb, re.sub(r"\s+", " ", w.group(0) if w else m.group(0))),
                w.end() if w else m.end())

    # Every decision and every question put, in the journal's order
    # (MOTION_EVENT, above): ("tally" | "division" | "voice", at, value, end)
    # and ("move", at, (verb, words), end).
    events = sorted(
        [("tally", at, (y, n), at) for at, y, n in tallies]
        + [("division", at, c, end) for at, c, end in divisions]
        + [("voice", at, w, end) for at, w, end in voices]
        + [_motion(m) for m in MOTION_EVENT.finditer(text)],
        key=lambda e: e[1])

    starts = [e[1] for e in events]

    def _carried(ev, words):
        """True, False, or None where the journal does not say for certain,
        for the decision `ev` of the motion `words`."""
        kind, at, val, end = ev
        if kind == "voice":
            said = val
        elif kind == "division":
            said = re.split(r"(?<=[a-z)])\.(?:\s|$)", text[end:end + 300], maxsplit=1)[0]
        else:
            said = ""
        if LOST_WORDS.search(said):
            return False
        if CARRIED_WORDS.search(said):
            return True
        if kind in ("division", "tally"):
            y, n = val
            if y < n:
                return False
            if y > n and MAJORITY_SUBSIDIARY.search(words):
                return True
        return None

    UNTIED = {"untied": True}

    def walk(pos):
        """The event that decided the question of the speech at pos -- an
        ("tally" | "division" | "voice", at, value, end) -- or UNTIED where a
        question of another kind was put first, or None where the journal
        decides nothing after it within the bill."""
        said = SPOKE_END.search(text, pos)
        start = said.end() if said else pos
        stop = next_bill_at(pos)
        pending, put_at = None, None
        for ev in events[bisect.bisect_left(starts, start):]:
            kind, at, val, end = ev
            if at >= stop:
                break
            # A motion the chair rules out of order was never put: "The
            # Speaker ruled the motion out of order because the House was
            # already in the voting mode" (HB 437's tabling, 21 March 2012).
            if pending is not None and OUT_OF_ORDER.search(text, put_at, at):
                pending = None
            if kind == "move":
                verb, words = val
                if CALL_OF_HOUSE.search(words):
                    continue
                # The motion made after the speech withdrawn: the question
                # stands again (HB 1696's tabling, 10 February 2016).
                if verb.startswith("withdrew") and pending is not None and \
                        "motion" in verb:
                    pending = None
                    continue
                if pending is not None:
                    return UNTIED
                if verb == "moved" and CLOSES_DEBATE.search(words):
                    pending, put_at = ("closes", words), end
                    continue
                if verb == "moved" and PRINTS.search(words):
                    pending, put_at = ("print", words), end
                    continue
                if verb == "moved" and SUBSIDIARY.search(words) and \
                        not NOT_SUBSIDIARY.search(words):
                    pending, put_at = ("aside", words), end
                    continue
                return UNTIED
            if pending is None:
                return ev
            what, words = pending
            if what == "print":
                pending = None
                if QUESTION_PUT.search(text[put_at:at]):
                    return ev
                if kind == "voice" and BARE_VERDICT.search(val):
                    continue
                return UNTIED
            if what == "closes":
                # A division says what it decided after its count: "On a
                # division vote, 179 members ... the motion to limit debate
                # was adopted." (HB 235, 28 March 2007).
                said = (str(val) if kind != "division" else
                        re.split(r"(?<=[a-z)])\.(?:\s|$)", text[at:end + 300], maxsplit=1)[0])
                if ITS_DECISION.search(text[put_at:at] + " " + said) or \
                        (kind == "voice" and BARE_VERDICT.search(val)):
                    pending = None
                    continue
                return UNTIED
            if _carried(ev, words) is False:
                pending = None
                continue
            return UNTIED
        return None if pending is None else UNTIED

    def amendment_pending(pos):
        """Was an amendment offered or put between the last decision before
        the speech at pos and the speech?"""
        lo = 0
        for at, _b in marks:
            if at <= pos:
                lo = at
        for kind, at, _v, end in events:
            if kind != "move" and lo <= at < pos:
                lo = end
        return bool(AMENDMENT_PENDING.search(block, lo, pos))

    def decided(pos):
        """What decided the speech's question, where it is not the roll call
        tally_after gives: {"count": (yeas, nays)} for a division or a later
        roll call, {"words": ...} for a question decided by voice (with
        "amendment" where that question was an amendment the journal does
        not name in the verdict), {"untied": True} where another question was
        put first (walk), and None where the next roll call decided it or
        nothing after it does."""
        ev = walk(pos)
        if ev is None or ev is UNTIED:
            return ev
        kind, at, val, _end = ev
        if kind == "tally":
            return (None if at == tally_after(pos, at=True)
                    else {"count": val, "roll_call": True})
        if kind == "division":
            return {"count": val}
        if BARE_VERDICT.search(val) and amendment_pending(pos):
            return {"words": val, "amendment": True}
        return {"words": val}

    def first_decision(pos):
        """(where, {"count": (yeas, nays)} or {"words": ...}, start): the
        first division or question decided by voice (DECIDED) the journal
        prints after the speech at pos and before the roll call after it, or
        the end of the bill; None where there is none. `start` is where the
        speech's own sentence ends. Only where moved_since reads to."""
        said = SPOKE_END.search(text, pos)
        start = said.end() if said else pos
        stop = tally_after(pos, at=True) or next_bill_at(pos)
        first = None
        for where, count, _end in divisions:
            if start <= where < stop:
                first = (where, {"count": count})
                break
        for where, words, _end in voices:
            if start <= where < stop:
                if first is None or where < first[0]:
                    first = (where, {"words": words})
                break
        return first + (start,) if first else None

    def moved_since(pos):
        """What was moved between the speech at pos and the vote after it
        (MOVED_SINCE), each motion in the journal's words; where no roll call
        follows, to the first question decided after it, or the end of the
        bill. "The question being adoption of the majority committee report
        of Inexpedient to Legislate. Rep. Ladd spoke in favor." and then a
        motion to table SB 294, adopted by voice (22 May 2025): the tabling,
        the one motion the record holds for the bill that day, had Rep. Ladd
        speaking for it."""
        vote = tally_after(pos, at=True)
        if vote is None:
            first = first_decision(pos)
            vote = first[0] if first else next_bill_at(pos)
        said = SPOKE_END.search(block, pos, vote)
        return [re.sub(r"\s+", " ", m.group("what")).strip()
                for m in MOVED_SINCE.finditer(block, said.end() if said else pos, vote)]

    def speech(m, names, inline):
        pos = m.start()
        d = decided(pos)
        return {"bill": bill_at(pos), "side": "for" if "favor" in
                m.group("side").lower() else "against",
                "names": names, "tally": tally_after(pos),
                "inline_motion": inline,
                "moved_since": moved_since(pos), "decided": d}

    for m in SPOKE.finditer(text):
        out.append(speech(m, _names(m.group("names")), None))
    for m in MOVED_SPOKE.finditer(text):
        out.append(speech(m, _names(m.group("name")),
                          re.sub(r"\s+", " ", m.group("motion")).strip()))
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
# A colon as well as a comma after the bill: "HB 1602: ..., removed by Reps.
# ..." is how 19 February 2026 printed one.
# A period ends an entry only where the next bill begins: a title holds one --
# "HB 1446, providing that ... possession of a firearm. Removed by Reps. H.
# Howard" (5 February 2026, four bills the note left out), "... carbon
# sequestration., removed by" (HB 123, 13 March 2025), "CACR 2, relating to
# natural rights of children. Providing that ..., removed by Rep. Hoell"
# (8 March 2017). Not into a committee's recommendation, "OUGHT TO PASS.", or
# its report: "HB 286, relative to the removal of political advertising.
# OUGHT TO PASS. ... campaign items removed by" (16 March 2023) is no removal.
REMOVED = re.compile(
    r"\b(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*)\s*[,:]"
    r"(?:[^.]|\.(?!\s*(?:(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d|(?-i:[A-Z]{2,})\b|Reps?\.)))"
    r"{0,300}?\bremoved\s+by\b", re.I | re.S)
ADOPTED = re.compile(r"Consent\s+Calendar\s+was\s+adopted", re.I)
# THE SAME LINE OUTSIDE THE SEGMENT. On 14 April 1999 the House reconsidered
# Part II of its consent calendar and adopted it again under a heading of its
# own, "CONSENT CALENDAR - Part II", which CONSENT_HEAD does not read -- and
# "HB 605-FN, affirming sovereign immunity ..., removed by Rep. Mock." sits
# there, so the day's page listed HB 605 among the bills adopted without
# debate on the day the House took it off and sent it back to committee
# (HJ 40, p. 943, and the docket's own row). A paragraph that opens
# with a bill and says a member removed it, anywhere on the day. The House
# prints 143 of these outside the segment, under a motion to vacate, to
# withdraw, a guests' heading, so one counts only for a bill already on that
# day's consent list: taken_off() is the one place that is decided.
REMOVED_LINE = re.compile(
    r"(?:\A|\n)[ \t]*(?P<bill>(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?\d+(?:-[A-Z]+)*)"
    r"\s*[,:][^.]{0,300}?\bremoved\s+by\s+Rep", re.I | re.S)


def _removed_bill(g):
    return g.group("bill").replace(" ", "").upper()


def consent(block):
    """{adopted, removed:[bill], removed_elsewhere:[bill]} -- what the House
    did with its consent list. removed_elsewhere, only where there is one, is
    the bills a "removed by" paragraph names outside the consent segment;
    taken_off() says when one counts."""
    out = {}
    m = CONSENT_HEAD.search(block)
    if m:
        end = len(block)
        nh = NEXT_HEAD.search(block, m.end() + 10)
        if nh:
            end = nh.start()
        seg = joined(block[m.end():end])
        out = {"adopted": bool(ADOPTED.search(seg)),
               "removed": sorted({_removed_bill(g) for g in REMOVED.finditer(seg)})}
    elsewhere = ({_removed_bill(g) for g in REMOVED_LINE.finditer(block)}
                 - set(out.get("removed") or ()))
    if elsewhere:
        out["removed_elsewhere"] = sorted(elsewhere)
    return out


def taken_off(found, on_list):
    """[bill] -- the bills taken off one day's consent calendar.

    `found` is read_day()'s answer for the day and `on_list` the bills the
    record puts on that day's consent calendar. Every removal the consent
    segment prints counts, as it always has; one printed anywhere else on the
    day counts only for a bill on the list, so that it can take a bill off and
    never put one into the note about bills that came off.
    """
    c = (found or {}).get("consent") or {}
    on = {str(b).split("-")[0].upper() for b in on_list}
    return sorted(set(c.get("removed") or ())
                  | {b for b in c.get("removed_elsewhere") or ()
                     if b.split("-")[0] in on})


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
                raw = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            text = clean(raw)
            # The speeches from the file with its lines kept (clean): the
            # same sittings in the same order, or the block read for the rest.
            lined = day_blocks(clean(raw, lines=True))
            for i, (iso, block) in enumerate(day_blocks(text)):
                got = out.setdefault(iso, {"date": iso, "attributions": [],
                                           "debates": [],
                                           "unanimous_consent": [],
                                           "opening": {}, "absences": [],
                                           "consent": {}, "files": []})
                got["files"].append(f.name)
                got["attributions"] += attributions(
                    lined[i][1] if i < len(lined) and lined[i][0] == iso else block)
                got["debates"] += debates(block)
                got["unanimous_consent"] += unanimous_consent(block)
                got["absences"] += absences(block)
                for k, v in opening(block).items():
                    got["opening"].setdefault(k, v)
                for k, v in consent(block).items():
                    if k in ("removed", "removed_elsewhere"):
                        got["consent"].setdefault(k, [])
                        got["consent"][k] += v
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


# ------------------------------------------------- the Senate's leave list --
#
# THE ONE THING THE SENATE JOURNAL GIVES THE PAGE: WHO WAS EXCUSED. It records
# no speakers (above), but every sitting on disk, 2003 to 2026, opens the same
# way -- the Senate meets, a quorum is present, the prayer, the Pledge -- and
# the senators excused for the day are named there, before the first bill:
#
#   "Senator Prescott is excused for the day."                      2003
#   "Sen. Merrill is excused from today's session."                 2010
#   "Sens. Boutin, Reagan, and Prescott were excused for the day."  2015
#   "Senators Avard, Carson and Ricciardi are excused."             2026
#
# There is no LEAVES OF ABSENCE heading to find, so the opening is bounded by
# what ends it: the first bill or roll call, or the next sitting.
#
# ONLY THE OPENING, BECAUSE THE SAME SENTENCE MEANS SOMETHING ELSE LATER. Past
# the first bill it is a senator leaving partway, or excused from one vote:
# "Senators Carson and D'Allesandro are excused for the day." after the
# consent calendar of 22 February 2018; "Sen. Houde is excused." before each
# of seven roll calls of 7 March 2012; and from 2017 every roll call prints
# "The following Senators were excused: ...". The person decided on
# 24 September 2026 that a page names the members excused for the day and not
# those excused for part of it, so an opening excuse that names part of the
# day -- "for the afternoon", "for the morning", "for the moment" -- is left
# out too.
#
# NAMES ONLY, AS FOR THE HOUSE. The Senate seldom gives a reason, and where it
# does -- "is excused due to medical necessity", 11 April 2024 -- it is health
# information about a named person; nothing here keeps it.
SENATE = Path("journals_senate")

_MONTH_ALT = "|".join(m.capitalize() for m in MONTHS)
# The sitting's date: at the end of the line that opens it ("The Senate met at
# 10:00 a.m.      March 20, 2003", 2003), or else in the heading just above
# it -- "SENATE      May 1, 2014", "JOURNAL 21      June 7, 2007", or
# "March 27, 2003" alone. JUST above: a floor amendment prints its own date on
# a line alone ("Sen. Hennessey, Dist 5 / February 22, 2018 / 2018-0827s"),
# and with the JOURNAL line unread, the sitting of 9 February 2006 took a date
# from the business 2,241 characters above it. The heading is never more than
# 538 characters above the sitting's first line, 2003 to 2026.
S_DATE = re.compile(rf"(?P<mon>{_MONTH_ALT})\s+(?P<day>\d{{1,2}}),?\s*(?P<yr>\d{{4}})")
S_DATELINE = re.compile(
    rf"^[ \t]*(?:SENATE[ \t]+|JOURNAL\s*\d+[A-Z]?[ \t]+)?(?:{_MONTH_ALT})[ \t]+"
    rf"\d{{1,2}},?[ \t]*\d{{4}}[ \t]*$", re.M)
S_HEAD_REACH = 1200
# A HEADING CAN BE MISPRINTED, and one is. Senate Journal 4 of 2006 heads its
# sitting "JOURNAL 4      February 2, 2006", but that sitting is 9 February:
# the issue's masthead reads "COMMENCEMENT - FEBRUARY 9, 2006 SESSION", every
# page of it is headed "SENATE JOURNAL 9 FEBRUARY 2006", and Senator Kenney,
# excused as it opens, is recorded excused on all three roll calls of
# 9 February. So where the heading above a sitting that MET disagrees with the
# running head of the page after it, and the masthead agrees with the running
# head, the two are believed over the one. Neither alone is: SJ 9 of 2005
# prints 2004 in every running head, and a sitting that reconvened is headed
# by the day it resumed while its pages keep the day it began. Across the
# 460 openings on disk, 2003 to 2026, this moves that one.
_MONTH_UP = "|".join(m.upper() for m in MONTHS)
S_RUNNING = re.compile(
    rf"SENATE\s+JOURNAL\s+(?P<day>\d{{1,2}})\s+(?P<mon>{_MONTH_UP})\s+(?P<yr>\d{{4}})")
S_COMMENCES = re.compile(
    rf"COMMENCEMENT\s*-\s*(?P<mon>{_MONTH_UP})\s+(?P<day>\d{{1,2}}),?\s*"
    r"(?P<yr>\d{4})\s+SESSION")
S_RUNNING_REACH = 3000
S_START = re.compile(
    r"^[ \t]*The\s+Senate\s+(?:met|reconvened|convened|assembled)\b[^\n]*", re.M)
# What ends the opening: a bill's heading at the start of a line, or a roll
# call ("The following Senators voted Yes:", "Yeas: 12 - Nays: 9").
S_BUSINESS = re.compile(
    r"^[ \t]*(?:(?:HB|SB|CACR|HCR|SCR|SR|HR|HJR|SJR)\s?\d+\b|"
    r"The\s+following\s+Senators\s+voted|(?:Roll\s+Call,\s+)?Yeas:)", re.M)
# CASE-SENSITIVE, like LEAVE_LINE and for its reason: a name is capitalised
# and "is excused" is not, and under re.I the names ran on into the verb.
_SEN = r"(?:Sen(?:ator)?s?\.?\s+)?"
_SLIST = (_SEN + _NAME + r"(?:\s*,\s*" + _SEN + _NAME + r")*"
          r"(?:\s*,?\s+and\s+" + _SEN + _NAME + r")?")
S_EXCUSED = re.compile(
    r"\b(?:The\s+following\s+Senators\s+(?:are|were)\s+excused(?P<t1>[^:.]{0,40}):"
    r"\s*(?P<l1>" + _SLIST + r")"
    r"|(?:Senators?|Sens?\.)\s+(?P<l2>" + _SLIST + r")\s+(?:is|are|was|were)\s+"
    r"excused(?P<t2>[^.]{0,60}))\s*\.")
PART_OF_DAY = re.compile(
    r"\b(?:morning|afternoon|evening|moment|votes?|voting|balance|rest|remainder)\b",
    re.I)


def _iso(m):
    return (f"{m.group('yr')}-{MONTHS[m.group('mon').lower()]:02d}-"
            f"{int(m.group('day')):02d}")


def senate_openings(text):
    """[(iso_date, opening)] -- each sitting's opening in one Senate file."""
    out = []
    for iso, s, end in _senate_spans(text):
        b = S_BUSINESS.search(text, s, end)
        out.append((iso, text[s:b.start() if b else end]))
    return out


def senate_sittings(text):
    """[(iso_date, block)] -- each sitting in one Senate file, whole: from
    the line that opens it to the line that opens the next, dated as
    senate_openings dates it. A sitting the Senate reconvened later the same
    day is a block of its own with the same date."""
    return [(iso, text[s:end]) for iso, s, end in _senate_spans(text)]


def _senate_spans(text):
    """[(iso_date, start, end)] -- where each dated sitting runs: its
    opening begins at `start`, after the line that opens it."""
    out = []
    starts = list(S_START.finditer(text))
    commences = {_iso(c) for c in S_COMMENCES.finditer(text)}
    for i, s in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        m = S_DATE.search(s.group(0))
        headed = False
        if not m:
            above = list(S_DATELINE.finditer(
                text, max(0, s.start() - S_HEAD_REACH), s.start()))
            m = S_DATE.search(above[-1].group(0)) if above else None
            headed = True
        if not m:
            continue
        iso = _iso(m)
        run = S_RUNNING.search(text, s.end(), s.end() + S_RUNNING_REACH)
        if (headed and run and " met" in s.group(0) and _iso(run) != iso
                and _iso(run) in commences):
            iso = _iso(run)
        out.append((iso, s.end(), end))
    return out


def senate_absences(opening):
    """[name] -- the senators excused for the day in one sitting's opening."""
    out = []
    for g in S_EXCUSED.finditer(joined(opening)):
        if PART_OF_DAY.search((g.group("t1") if g.group("l1") else g.group("t2")) or ""):
            continue
        for nm in _names(g.group("l1") or g.group("l2")):
            # "Forrester, Luther, Larsen, and Merrill": the comma is split
            # on first, which leaves the "and" on the last name.
            nm = re.sub(r"^(?:and\s+)?(?:Sen(?:ator)?s?\.?\s+)?", "", nm).strip()
            if nm and nm not in out:
                out.append(nm)
    return out


def read_senate_year(year, root=SENATE):
    """{date: [name]} -- every Senate sitting's leave list in one folder.

    "Verbatim" files are a day's debate printed a second time, and are
    skipped; a day printed twice otherwise (a long and a short version of
    27 June 2007) gives the same names twice, which are kept once.
    """
    key = ("S", str(root), str(year))
    if key in _YEARS:
        return _YEARS[key]
    out = {}
    d = Path(root) / str(year)
    if d.exists():
        for f in sorted(d.glob("*.txt")):
            if "erbatim" in f.name:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            for iso, opening in senate_openings(text):
                got = out.setdefault(iso, [])
                for nm in senate_absences(opening):
                    if nm not in got:
                        got.append(nm)
    _YEARS[key] = out
    return out


def read_senate_day(date, root=SENATE):
    """{"absences": [{"names": [...]}]} for one Senate sitting -- the shape
    read_day gives the House, so the page draws both the same way.

    A December organization day opens the next year's journal
    (journals_senate/2025/SJ 01 December 4, 2024 Organization Day.txt), so
    both folders are read.
    """
    names = []
    for year in dict.fromkeys((date[:4], str(int(date[:4]) + 1)
                               if date[5:7] == "12" else date[:4])):
        for nm in read_senate_year(year, root).get(date, []):
            if nm not in names:
                names.append(nm)
    return {"date": date, "attributions": [], "debates": [],
            "unanimous_consent": [], "opening": {},
            "absences": [{"names": names}] if names else [], "consent": {}}


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
