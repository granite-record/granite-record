#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.3
"""
What the Journals say a vote on no bill was about.

    python3 src/parse/journal_motions.py               # writes journal_motions.json
    python3 src/parse/journal_motions.py --show 2026-H-290
    python3 src/parse/journal_motions.py --check       # the counts, writes nothing

No network. The standard library, rollcall_outcomes.py's pairing of each roll
call with its tally in the Journal, and journal_days.py's patterns for a
running head and a speech.

WHY THIS EXISTS (23 October 2026)

The owner: "Those are often important votes that sometimes get reported on,
but it's very hard to find that information on GenCourt since the vote is
just labeled something like voting whether to approve the committee report
with no other context." 342 roll calls are on no bill -- a rules suspension,
an appeal of the chair's ruling, a member allowed to go on speaking, a
reprimand, a censure -- and the roll-call file names each in two or three
words: the censure of Rep. Corcoran on 21 May 2026 is "Affirm The Report",
288-54. The House and Senate Journals print, above every tally, the motion
that was put. This reads it.

WHERE THE WORDS COME FROM, AND WHERE THEY DO NOT

rollcall_outcomes.journal_links has already paired every roll call with its
tally in the Journal, in order through the year (and journal_tallies now
says where in which file each tally stands). This reads the passage before
THAT tally and nothing else: it never looks for a tally of its own, so the
words shown are the ones at the place the outcome was read from.

From the passage it keeps sentences, verbatim -- the line breaks joined, a
word the press broke at a line's end put back together -- and only of the
kinds that say what was put to the vote: the "moved that ..." sentence, a
ruling of the chair and the challenge to it, an objection to unanimous
consent and the request it objected to, "The question being ...", a
committee's recommendation where the report is the question, and the
Journal's own sentence on the outcome after the tally. Who spoke on which
side is the session page's, from the record; speeches are left out, except a
motion a member made inside one ("Therefore, I move that Representative
Charlie Burns be reprimanded", 20 February 2020).

THE GATES. A passage is shown only where every one of these holds; each
withheld roll call is counted, with its reason, in the file and the log.

  1. THE TALLY. The Journal prints exactly this roll call's count at the
     paired place (HJ 07 of 6 March 2025 prints its tallies one roll call
     out of step, and 2025-H-60's 171-89 is printed nowhere).
  2. THE DATE. The page the tally is printed on is dated the day the
     roll-call file gives the vote, or within three days before it (the
     House's roll calls of 24 and 25 February 2021 are dated the 26th). The
     Senate's twenty-four-nothing housekeeping of 2021 has a run where the
     pairing lands a whole sitting away.
  3. THE QUESTION. Where the roll-call file's own words name a kind of
     question -- a suspension, an adjournment, a rule, a member continuing
     -- the passage must say it too. In the Senate of 6 January 2021 five
     roll calls of 24-0 each were paired with the vote before them.
  4. THE OUTCOME. The Journal's sentence after the tally must agree with the
     outcome on record.
  5. THE PASSAGE. At least one sentence of the kinds above; a quorum call
     puts no question.

And two more on what is SAID about a shown passage:

  6. ONE BILL. Where the passage names two bills -- the motion to make HB
     1609-FN a special order, challenged as "the motion to Special Order HB
     1142" (11 March 2026) -- the quote is shown alone: no bill is named and
     no one-line summary is written.
  7. A MEMBER'S DISCIPLINE (a reprimand, a censure, an expulsion, a
     member's privileges) has its quote and its page, and a one-line summary
     only where a person has approved that line in corrections/vote_lines.json
     for that roll call and that page. Its subject is named only where the
     motion or report and the Journal's line after the vote ("The Speaker
     informed Rep. Corcoran of the censure by the House") name the same
     member.

A one-line summary is a few words of the site's for the kind of question
and words lifted from the passage: every word of a slot is checked to stand
in the excerpt, in order, or the line is not written (gate 8).

VOTES ONLY THE JOURNAL HAS. A division prints a count and no names, and a
voice vote not even a count, so neither is in the roll-call file: the House
reprimanded Rep. Paige Beauchemin on 12 February 2026 on a division, 264-89.
Those taken under the same headings -- discipline, an appeal of a ruling, a
member continuing, a rules suspension, the rules -- are read here too, and
marked as what they are: a division gives the count and not each member's
vote.

A WRITER RUN ON A SUBSET DESTROYS THE REST (CLAUDE.md). This reads every
year whose Journals are on disk and keeps, from the file it is replacing,
the years whose Journals are not -- so a machine without some of them does
not take those votes off the site.

SILENCE IS NOT SUCCESS. A year whose Journals are on disk and whose no-bill
roll calls the pairing placed, and from which nothing at all was read, stops
the step: that is the patterns no longer matching the Journal's layout.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date

import rollcall_outcomes as RO

OUT = Path("journal_motions.json")
# Both kept in the repository, so found through it wherever this runs.
APPROVED = _paths.ROOT / "corrections" / "vote_lines.json"
CAREERS = _paths.ROOT / "generated" / "careers.json"

# ------------------------------------------------------------------ kinds
#
# A CLOSED LIST. Each kind is a heading a reader understands without the
# House Rules to hand; the site's own words, kept here once so the parser,
# the session pages, the member tab and the per-term list say the same.
KINDS = {
    "discipline": "Discipline of a member",
    "privileges": "A member's privileges",
    "member_continue": "Shall the member continue",
    "appeal": "Appeal of the chair's ruling",
    "suspend_rules": "Suspending the rules",
    "rules": "The chamber's own rules",
    "print": "Printing in the Journal",
    "limit_debate": "Limiting debate",
    "adjourn": "Adjourning or recessing",
    "petition": "A petition or remonstrance",
    "justices": "Asking the justices for an opinion",
    "report": "A committee's report on no bill",
    "housekeeping": "The Senate's remote-session business",
    "motion": "A motion on other business",
    "other": "Another question",
}
# Kinds about a person, whose one-line summary only a person may write.
PERSONAL = {"discipline", "privileges"}

# The words that name each kind, in the order they are tried. Read off the
# roll-call file's words and the passage alike; the passage's last question
# decides first (classify).
KIND_WORDS = [
    # "\bcensur", or licensure is a censure (SB 125-FN, 3 June 2015).
    ("discipline", r"reprimand|\bcensur|\bexpel|expulsion"),
    # Not the anterooms of House Rule 63 on weapons (2 January 2019): the
    # privileges a member was barred from, by the Speaker's directive.
    # Not the Senate's "personal privileges", which are its members' speeches.
    ("privileges", r"(?<!personal\s)(?<!personal\s\s)privileges?\b|allow\w*\s+(?:rep\.?\s+\w+\s+)?back into|"
                   r"return\w*\s+to\s+the\s+chamber|back into the (?:house|chamber)|"
                   r"sanctions\s+on\b|speaker's\s+directive"),
    ("member_continue", r"member\s+(?:be\s+allowed\s+to\s+)?continue|continue\s+speaking|"
                        r"disorderly|unanimous\s+consent\s+given|shall\s+member\s+continue|"
                        r"member\s+continue"),
    # Before a suspension or an appeal: "moved that the debate on the motion
    # to suspend House Rules, be printed" (12 March 2020) is printing. Not "as
    # printed in the House Calendar", which every rules amendment of
    # 2015-2017 says of itself.
    ("print", r"\bbe\s+printed\b|\bprint(?:ing)?\s+(?:the\s+)?(?:remarks|debate|speech|inquir)|"
              r"\bprint\s+remarks|permanent\s+journal|amend\w*\s+(?:the\s+)?(?:house\s+|senate\s+)?"
              r"journal|rule\s*2-16|entered\s+into\s+the\s+permanent"),
    # Not a zoning board's "appeal period" (SB 508), nor a resolution
    # "upholding" rights (HJR 1): an appeal of a ruling, said as one.
    ("appeal", r"ruling\s+of\s+(?:the\s+)?chair|decision\s+of\s+(?:the\s+)?(?:chair|president)|"
               r"rul(?:e|ing)\s+of\s+chair|\bappeal(?:ed|s)?\s+(?:of\s+)?the\s+(?:ruling|decision)|"
               r"challenged\s+the\s+ruling|\buphold\s+(?:the\s+)?(?:ruling|decision)|"
               r"\buphold\s+ruling|\bupholding\s+the\s+ruling"),
    ("suspend_rules", r"\bsusp\w*\b[^.]{0,40}\brules?\b|\brules?\s+suspen|suspen\w*\s+of\s+"
                      r"(?:all\s+)?(?:senate\s+|house\s+)?rules|\bsuspend\b|"
                      r"\brules?\s+be\s+(?:so\s+far\s+)?suspended"),
    ("limit_debate", r"limit\w*\s+(?:the\s+)?debate|debate\s+(?:on\s+[^.]{0,80}\s+)?(?:be\s+)?"
                     r"limited|previous\s+question"),
    ("justices", r"justices"),
    ("petition", r"petition|remonstrance"),
    ("rules", r"\b(?:house|senate|joint|special\s+session(?:\s+senate)?)\s+rules?\b|\brules?\s+\d|"
              r"\bh\s*rule|\bflam\s+to\s+house\s+rule|adopt\s+rules|amend\s+rules?|"
              r"\brule\s*#|\brule\s+\d"),
    ("adjourn", r"adjourn|\brecess\b"),
    ("housekeeping", r"finance\s+report|\bFN\s+report|consent\s+calendar|introduction\s+of\s+"
                     r"(?:senate\s+bills|legislation)|personal\s+privil|attendance|"
                     r"select\s+committee"),
    ("report", r"affirm\s+the\s+report|adopt\w*\s+(?:of\s+)?(?:the\s+)?report|ratify"),
    ("motion", r"\btable\b|reconsider|third\s+reading|3rd\s+reading|special\s+order|\brefer|"
               r"\bdivide|\bvacate|\bamend|late\s+drafting|new\s+bill|take\s+up|\bintroduc"),
]
_KIND_RX = [(k, re.compile(p, re.I)) for k, p in KIND_WORDS]


def kinds_in(text):
    """Every kind whose words stand in `text`, in KIND_WORDS order."""
    return [k for k, rx in _KIND_RX if rx.search(text or "")]


def file_kind(words):
    """The kind the roll-call file's own words name, or "" where they name
    none worth checking the passage against ("Table", "Reconsider", blank:
    a motion on whatever was before the chamber)."""
    got = kinds_in(words)
    for k in got:
        if k not in ("motion", "other", "report"):
            return k
    return ""


# ------------------------------------------------------------- the passage

# A running head: "21MAY2026HOUSERECORD 24", "88 2january 2013 HOUSE RECORD",
# "SENATE JOURNAL 3 APRIL 2003  269", "SENATEJOURNAL6JANUARY2021 28".
_MON = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|"
        "NOVEMBER|DECEMBER")
MONTHS = {m.lower(): i for i, m in enumerate(_MON.split("|"), 1)}
RUNNING = re.compile(
    rf"^[ \t\f]*(?:(?P<p1>\d{{1,4}})[ \t]+)?(?:SENATE[ \t]*JOURNAL[ \t]*)?(?P<d>\d{{1,2}})[ \t]*"
    rf"(?P<m>(?i:{_MON}))[ \t]*(?P<y>\d{{4}})[ \t]*(?:HOUSE[ \t]*RECORD)?[ \t]*(?P<p2>\d{{1,4}})?"
    r"[ \t]*$", re.M)
DATELINE = re.compile(
    r"^[ \t]*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
    r"(?P<m>January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(?P<d>\d{1,2}),?\s*(?P<y>\d{4})", re.M | re.I)
S_START = re.compile(r"^[ \t]*The\s+Senate\s+(?:met|reconvened|convened|assembled)\b", re.M)
S_DATE = re.compile(r"(?P<m>January|February|March|April|May|June|July|August|September|"
                    r"October|November|December)\s+(?P<d>\d{1,2}),?\s*(?P<y>\d{4})")
DAY_HEADER = re.compile(r"^[ \t]*HOUSE\s+JOURNAL\s+N[Oo]\.?\s*\d*", re.M)

# A heading: a line in capitals, alone. Not a county of a roll call's list,
# not the tally, not a running head.
HEAD = re.compile(r"^[ \t]*(?P<h>[A-Z][A-Z0-9' ’.,&()/:#-]{4,}[A-Z0-9.)])[ \t]*$", re.M)
COUNTIES = re.compile(r"^(?:BELKNAP|CARROLL|CHESHIRE|COOS|GRAFTON|HILLSBOROUGH|MERRIMACK|"
                      r"ROCKINGHAM|STRAFFORD|SULLIVAN)$")
NOT_A_HEAD = re.compile(r"YEAS|NAYS|HOUSE\s*RECORD|SENATE\s*JOURNAL|HOUSE\s+JOURNAL|"
                        r"^RESOLVED|^(?:HB|SB|HR|SR|CACR|HCR|SCR|HJR)\s*\d")
# Headings of the day's business that are not a question's: what falls under
# one of these is the next thing, not the vote's own heading.
BUSINESS = re.compile(
    r"^(?:RECESS|SENATE MESSAGE|HOUSE MESSAGE|CONCURRENCE|NONCONCURRENCE|REQUESTS? |"
    r"CONSENT CALENDAR|REGULAR CALENDAR|LEAVES? OF ABSENCE|INTRODUCTION OF|AMENDED ANALYSIS|"
    r"INVOCATION|PLEDGE|NATIONAL ANTHEM|ENROLLED BILLS|EARLY SESSION|LATE SESSION|"
    r"THIRD READING|SECOND READING|FIRST|SPECIAL ORDER$|RECONSIDERATION$|COMMITTEE REPORTS|"
    r"REPORTS? OF COMMITTEE|ADJOURNMENT$|IN RECESS|OUT OF RECESS|ANALYSIS$|"
    r"(?:MAJORITY|MINORITY) COMMITTEE REPORT|ACCEDES|ACCEDE|CONFERENCE|TABLED BILLS|"
    r"RETAINED|INTERIM STUDY|VETOED|VETO MESSAGE|GUESTS|INTRODUCTIONS|REMARKS|"
    r"UNANIMOUS CONSENT$)")
# A heading that continues the business before it: an objection to a
# member's unanimous consent, a challenge to a ruling, a motion on a motion.
CONTINUES = re.compile(
    r"^(?:OBJECTION|CHALLENGE|APPEAL|MOTION TO (?:APPEAL|LAY ON THE TABLE|TABLE|INDEFINITELY|"
    r"POSTPONE|REFER|DIVIDE|AMEND|LIMIT)|MOTON TO (?:LAY|TABLE|INDEFINITELY|POSTPONE|REFER))")
UC_HEAD = re.compile(r"^UNANIMOUS CONSENT$")
# The words a question's heading has; the other capitals of a page do not.
QUESTION_HEAD = re.compile(
    r"MOTION|MOTON|RESOLUTION|REPORT|APPEAL|CHALLENGE|OBJECTION|UNANIMOUS|RULES?\b|REPRIMAND|"
    r"CENSURE|EXPUL|EXPEL|SUSPEN|PRIVILEGE|ADJOURN|PRINT|DEBATE|DISORDERLY|PETITION|"
    r"REMONSTRANCE|JUSTICES|AMENDMENT|QUESTION|ORDER|REMOVED|CHAMBER|SANCTION|CONDUCT|ETHICS|"
    r"INQUIRY|POINT OF|CALL OF|QUORUM|RECONSIDER|COMPLAINT|DIVIDE|DIVISION|TABLE|LIMIT")

# A speech: "Speaker Pro Tempore Weber: Mister Speaker, ...",
# "Representative Baldasaro: Thank you", "SENATOR KAHN: Thank you".
SPEECH = re.compile(
    r"^[ \t]*(?P<who>(?:(?:Deputy\s+)?Speaker(?:\s+Pro\s+Tempore)?|Rep(?:resentative)?\.?|"
    r"(?:Mister|Madam|Mr\.|Madame)\s+(?:Speaker|President)|SENATOR|Senator|Sen\.|PRESIDENT|"
    r"President)\s+[A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+){0,3})\s*:\s*(?=\S)", re.M)
I_MOVE = re.compile(r"\bI\s+(?:would\s+)?move\s+that\b", re.I)

# The kinds of sentence kept, tried in order on each sentence of the passage.
SAY = [
    ("uc", re.compile(r"requested\s+unanimous\s+consent", re.I)),
    # Anchored: "Having not objected, and having served notice ..., Rep.
    # Colcombe moved that the House reconsider" (5 March 2026) is a motion.
    ("objection", re.compile(r"^(?:An\s+)?objection\s+was\s+(?:raised|made)|^Objection\b", re.I)),
    ("challenge", re.compile(r"\b(?:challenged|appealed)\b[^.]{0,80}\b(?:ruling|decision)\b|"
                             r"moved\s+to\s+appeal\s+the\s+ruling", re.I)),
    ("ruled", re.compile(r"\bruled\b", re.I)),
    ("moved", re.compile(r"\bmoved?\b|\boffered\b|^RESOLVED\b", re.I)),
    ("question", re.compile(r"\bThe\s+question\s+(?:now\s+)?(?:being|is|was)\b|"
                            r"\bresumed\s+debate\s+on\b")),
    ("withdrew", re.compile(r"\bwithdrew\s+the\s+motion\b", re.I)),
]
# A sentence that says only who spoke, who asked for the roll call, or who
# voted -- the session page's, from the record, or nobody's.
NOISE = re.compile(
    r"^(?:Reps?\.|Representatives?|Sens?\.|Senators?)\s+[^.]{0,120}?\b(?:spoke|requested\s+a\s+"
    r"roll|yielded)|^A\s+roll\s+call\s+(?:was|is)\s+(?:requested|required)|sufficiently\s+"
    r"seconded|^The\s+following\s+Senators|^Recess\.|^Out\s+of\s+recess|declared\s+a\s+quorum|"
    r"^Without\s+objection,\s+the\s+Chair\s+closed|called\s+the\s+question", re.I)
# A committee's recommendation, where a report is the question.
RECOMMENDS = re.compile(r"\brecommends?\b", re.I)

# What settles a question before the next one is put: a verdict.
VERDICT = re.compile(
    r"\b(?:was|were|is)\s+(?:adopted|upheld|sustained|overruled|reprimanded|censured|"
    r"expelled|defeated)\b|\b(?:adopted|failed|prevailed|carried|lost|upheld)\b|"
    # The verbatim debate's own close: "With 191 voting in the affirmative,
    # 155 voting in the negative, the motion passes." (5 March 2026)
    r"\bthe\s+motion\s+(?:passes|fails|carries)\b|"
    r"\bso\s+ordered\b|\bthe\s+Speaker\s+ordered\b", re.I)
NOT_VERDICT = re.compile(r"\b(?:moved|question|requested|spoke|ruled|offered|challenged|"
                         r"appealed|objection|recommends?|shall\s+be|that|RESOLVED)\b", re.I)

# A title's full stop is not the sentence's (journal_days.UC_LINE).
ABBREV = re.compile(r"(?:\b(?:Reps?|Sens?|Dr|Mrs?|Ms|St|Jr|Sr|Gov|Lt|Gen|Mt|No|Nos|Dist|"
                    r"Rock|Hills|Merr|Straf|Ches|Graf|Belk|Carr|Sull|Coos|Inc|vs|Co|"
                    r"Pro|Tem|[A-Z])\.)$")
# "a.m." ends a sentence where a capital follows ("at 9:30 a.m. Rep. Horn
# requested a roll call", 2 May 2018) and is read through where a comma does.
# A special session's bill is its own record: "SS HB 1-FN-A" is SSHB1, not
# the session's HB 1 (7 November 2013).
BILL = re.compile(r"\b(?P<ss>SS\s?)?(?P<k>HB|SB|CACR|HCR|SCR|HJR|SJR|HR|SR)\s?(?P<n>\d{1,4})\b"
                  r"(?P<f>(?:-[A-Z]+)*)")
TALLY_ANY = re.compile(r"YEAS\s*-?\s*\d+\s*-?\s*NAYS\s*-?\s*\d+|Yeas:\s*\d+\s*-\s*Nays:\s*\d+", re.I)


def _read(f, cache):
    """A Journal's text exactly as journal_tallies read it, so its offsets hold."""
    if f not in cache:
        with open(f, encoding="utf-8", errors="replace") as fh:
            cache[f] = fh.read()
    return cache[f]


def _joined(text):
    """A stretch of the Journal as running prose: a word broken at a line's
    end put back together, the running heads out, the white space single."""
    text = RUNNING.sub(" ", text.replace("\f", "\n"))
    text = re.sub(r"(?<=[a-z])-[ \t]*\n[ \t]*(?=[a-z])", "", text)
    # Who took the chair is a line of its own, not part of the motion after it.
    text = CHAIR_LINE.sub("\n", text)
    return re.sub(r"\s+", " ", text).strip()


CHAIR_LINE = re.compile(r"\((?:Speaker|Deputy\s+Speaker|Rep\.|Representative|Senator|Sen\.|"
                        r"President|Vice\s+President)[^()]{0,60}?in\s+the\s+Chair\)|"
                        r"\(The\s+Chair\s+recognized\s+[^()]{0,60}\)", re.I)
# A column of the roll call above, read across into the motion's line:
# "Tanner, Linda Rep. Weber moved the adoption ..." (24 February 2021).
NAMES_BEFORE = re.compile(r"^(?:[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)?,\s+[A-Z][\w'’.-]+"
                          r"(?:\s+(?:Jr|Sr|II|III|IV)\.?)?\s+)+")


def sentences(text):
    """The sentences of a stretch of running prose, a title's stop read
    through: "Rep. Wheeler moved that ..." is one sentence, not two."""
    out, start = [], 0
    for m in re.finditer(r"[.?!](?:[\"”’']+)?(?=\s+(?:[A-Z\"“(]|$))|[.?!][\"”’']*$", text):
        piece = text[start:m.end()].strip()
        if ABBREV.search(text[max(0, m.start() - 6):m.start() + 1]):
            continue
        # A constitutional amendment's title holds a full stop: "CACR 32,
        # relating to independence. Providing that ..." (10 March 2022).
        if re.match(r"\s+Providing\s+that\b", text[m.end():m.end() + 20]):
            continue
        if piece:
            out.append(piece)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def page_at(text, pos):
    """(printed page, pdf page, the page's date) at `pos`: the running head
    that opens the page the offset is on, and how many pages come before it.
    The printed page is None before 2013 in the House, which printed none."""
    ff = text.rfind("\f", 0, pos)
    pdf = text.count("\f", 0, pos) + 1
    head = RUNNING.search(text, ff + 1 if ff >= 0 else 0, (ff if ff >= 0 else 0) + 400)
    if not head:
        # The running head may sit at the foot of the page instead.
        nxt = text.find("\f", pos)
        nxt = len(text) if nxt < 0 else nxt
        heads = list(RUNNING.finditer(text, max(ff, 0), nxt))
        head = heads[-1] if heads else None
    if not head:
        return None, pdf, None
    num = head.group("p1") or head.group("p2")
    try:
        when = date(int(head.group("y")), MONTHS[head.group("m").lower()], int(head.group("d")))
    except (ValueError, KeyError):
        when = None
    return (int(num) if num else None), pdf, when


def sitting_date(text, pos, body):
    """The day of the sitting a passage is in: the running head of its page,
    or the dateline above it where the page has none."""
    _p, _pdf, when = page_at(text, pos)
    if when:
        return when
    rx = DATELINE if body == "H" else S_DATE
    last = None
    lo = 0
    if body == "S":
        starts = [m.start() for m in S_START.finditer(text, 0, pos)]
        lo = max(0, starts[-1] - 1500) if starts else 0
    for m in rx.finditer(text, lo, pos):
        last = m
    if not last:
        return None
    try:
        return date(int(last.group("y")), MONTHS[last.group("m").lower()], int(last.group("d")))
    except (ValueError, KeyError):
        return None


def _heads(text, lo, hi):
    """[(offset, heading)] of the headings between lo and hi."""
    out, end = [], -1
    for m in HEAD.finditer(text, lo, hi):
        h = re.sub(r"\s+", " ", m.group("h")).strip()
        if COUNTIES.match(h) or NOT_A_HEAD.search(h) or RUNNING.match(m.group(0)):
            continue
        if sum(c.isalpha() for c in h) < 5:
            continue
        # A heading set on two lines is one heading: "SPECIAL REPORT TO THE
        # SPEAKER OF THE HOUSE OF REPRESENTATIVES REGARDING" over "COMPLAINT
        # 2026-3" (19 August 2026).
        if out and end >= 0 and not text[end:m.start()].strip():
            out[-1] = (out[-1][0], f"{out[-1][1]} {h}")
        else:
            out.append((m.start(), h))
        end = m.end()
    return out


def last_decision(text, lo, hi):
    """The offset just after the last verdict between lo and hi -- where the
    question this passage ends on was put -- or lo."""
    best = lo
    for m in re.finditer(r"[^.\n]*(?:\n[^.\n]*){0,3}?\.", text[lo:hi]):
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        v = VERDICT.search(s) if s else None
        # A verdict is said early in a short sentence: "Committee report
        # adopted and ordered to third reading." A resolution's "that all
        # titles of bills be the same as adopted" (25 May 2011) is not one.
        if not v or v.start() > 140 or len(s) > 320 or NOT_VERDICT.search(s):
            continue
        # "On a division vote, ... the motion was adopted." is one decision;
        # "I move that ... be reprimanded" is a motion, caught above.
        best = lo + m.end()
    # A division's sentence runs over the line ends, and NOT_VERDICT's
    # "question" never stands in it.
    # "with" or not: "On a division vote, with 206 members having voted"
    # (20 February 2020) is the form since 2013.
    for m in DIV_SENT.finditer(text, lo, hi):
        best = max(best, m.end())
    return best


def _blocks(text, lo, hi):
    """[(heading or None, start, end)] of the passage between lo and hi, cut
    at its headings."""
    hs = _heads(text, lo, hi)
    out = []
    if not hs or hs[0][0] > lo:
        out.append((None, lo, hs[0][0] if hs else hi))
    for i, (at, h) in enumerate(hs):
        out.append((h, at, hs[i + 1][0] if i + 1 < len(hs) else hi))
    return out


def _said(text, lo, hi, report=False, amend=False):
    """[{"k", "t"}] -- the sentences between lo and hi that say what was put,
    verbatim, in order; a motion made inside a speech with its speaker. Under
    a report's heading, its recommendation; under an amendment to the rules,
    the amendment's own first words and the text after them ("Amend House
    Rule 2 by adding the following: 2. (a) When the House is in session, all
    persons in the House chamber shall be dressed in proper business
    attire.")."""
    out = []
    chunk = text[lo:hi]
    # A heading is no part of a sentence: "UNANIMOUS CONSENT Rep. Beauchemin
    # requested ..." is the heading and then the sentence.
    for at, h in reversed(_heads(chunk, 0, len(chunk))):
        # A heading set on several lines ends where its last word does.
        eol = at
        for word in h.split()[-1:]:
            k = chunk.find(word, at)
            eol = k + len(word) if k >= 0 else eol
        nl = chunk.find("\n", eol)
        eol = len(chunk) if nl < 0 else nl
        chunk = chunk[:at] + "\n\x01\n" + chunk[eol:]
    # The speeches out, but for a motion made in one.
    keep, at = [], 0
    for m in SPEECH.finditer(chunk):
        keep.append(chunk[at:m.start()])
        end = re.search(r"\n[ \t]*\n|\n(?=[ \t]*(?:[A-Z][A-Z ]{6,}$|Rep\.|Reps\.|The question|"
                        r"On a division))", chunk[m.end():], re.M)
        stop = m.end() + (end.start() if end else len(chunk) - m.end())
        speech = _joined(chunk[m.end():stop])
        for s in sentences(speech):
            if I_MOVE.search(s):
                keep.append("\n")
                out_s = {"k": "moved", "t": s, "by": re.sub(r"\s+", " ", m.group("who")).strip()}
                keep.append(f"\x00{len(out)}\x00")
                out.append(out_s)
        at = stop
    keep.append(chunk[at:])
    prose = _joined("\n".join(keep))
    ordered = []
    pieces = []
    for piece in re.split(r"\x00(\d+)\x00", prose):
        if piece.isdigit() and int(piece) < len(out):
            pieces.append(piece)
        else:
            pieces += [p for p in piece.split("\x01")]
    for piece in pieces:
        if piece.isdigit() and int(piece) < len(out):
            ordered.append(out[int(piece)])
            continue
        text_left = 0
        for s in sentences(piece.strip()):
            if NOISE.search(s) and not re.search(r"\bmoved\b", s, re.I):
                text_left = 0
                continue
            if TALLY_ANY.search(s):
                continue
            kind = next((k for k, rx in SAY if rx.search(s)), None)
            if kind is None and report and RECOMMENDS.search(s):
                kind = "report"
            if kind is None and amend and re.match(r"Amend\s+(?:the\s+)?(?:House|Senate|Joint)?\s*"
                                                   r"(?:Special\s+Session\s+)?Rules?\b", s):
                kind, text_left = "text", 2
            elif kind is None and text_left:
                kind = "text"
                text_left -= 1
            if kind is None:
                continue
            if kind == "moved":
                who = re.search(r"(?:\bReps?\.|\bRepresentatives?\b|\bSens?\.|\bSenators?\b|"
                                r"\bSpeaker\b|\bPresident\b|\bChair\b)[^.]{0,160}?\b(?:moved|"
                                r"offered)\b|^RESOLVED\b", s)
                if not who:
                    continue
                # A table or a list the press ran into the sentence: begin it
                # where its mover is named ("... Plurality for Gatsas 16,239
                # Senator Bradley offered the following Resolution:").
                if who.start() > 120:
                    s = s[who.start():]
                s = NAMES_BEFORE.sub("", s) if NAMES_BEFORE.match(s) and \
                    who.start() <= len(NAMES_BEFORE.match(s).group(0)) else s
            s = NAMES_BEFORE.sub("", s) if kind in ("question", "uc", "objection") else s
            if kind == "question":
                # "Vote: 10-2 The question was to affirm the report": a
                # committee's vote has no full stop, and its sentence runs on.
                q = dict(SAY)["question"].search(s)
                s = s[q.start():] if q else s
            # A full stop the press left out runs a motion on into who spoke:
            # "... be referred to the Committee on Judiciary Rep. Gary
            # Richardson spoke against." (30 January 2013). The motion ends
            # where the speaker's sentence begins.
            sp = re.search(r"\s(?:Reps?\.|Sens?\.|Senators?)\s+[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+){0,2}"
                           r"(?:,?\s+(?:and\s+)?[A-Z][\w'’-]+){0,4}\s+(?:spoke|requested\s+a\s+roll|"
                           r"yielded)\b", s)
            if sp and sp.start() > 20:
                s = s[:sp.start()].rstrip()
            if kind == "text":
                if sum(1 for x in ordered if x["k"] == "text") >= 3:
                    continue
            if len(s) > 700:
                cut = s[:700].rsplit(" ", 1)[0]
                s = cut + " …"
            if ordered and ordered[-1]["t"] == s:
                continue
            ordered.append({"k": kind, "t": s})
    return ordered


QUESTION_NOW = re.compile(r"^The\s+question\s+now\s+being,?\s*[\"“]?(?P<q>.{12,200}?)[\"”]?[.?]?$",
                          re.I)


def passage(text, at, body):
    """What the Journal prints above the tally at `at`: {"heading", "said",
    "start"} -- the business the vote was on, cut where the question before
    it was settled, the blocks that continue each other kept together."""
    # Back to the tally before this one, or 40,000 characters, whichever is
    # nearer: a committee's report can run several pages.
    prev = None
    for m in TALLY_ANY.finditer(text, max(0, at - 40000), at):
        prev = m
    lo = prev.end() if prev else max(0, at - 40000)
    # A Senate tally comes after its names; a House tally before them. The
    # House's previous tally is followed by its own names and outcome, which
    # the last verdict cuts away.
    start = last_decision(text, lo, at)
    blocks = _blocks(text, start, at)
    sel = [blocks[-1]]
    i = len(blocks) - 1
    while i > 0:
        cur, prv = blocks[i], blocks[i - 1]
        h = cur[0] or ""
        if not CONTINUES.match(h):
            break
        if prv[0] and BUSINESS.match(prv[0]) and not UC_HEAD.match(prv[0]):
            break
        # A motion on a motion continues it; a motion to table a bill is the
        # bill's own business, whatever came before it.
        if h.startswith("MOT"):
            mine = " ".join(x["t"] for x in _said(text, cur[1], cur[2]) if x["k"] == "moved")
            if not re.search(r"\b(?:the|a)\s+motion\b|\bmotion\s+(?:of|to)\b", mine, re.I):
                break
        # And only business still pending: something put and not settled.
        if not any(x["k"] in ("moved", "uc", "ruled", "question", "report")
                   for x in _said(text, prv[1], prv[2], report=bool(prv[0] and "REPORT" in prv[0]))):
            break
        sel.insert(0, prv)
        i -= 1
    # A motion moved just above its heading: "Rep. Hinch moved the adoption
    # of an amendment to House Rule 2, as proposed by the Rules Committee"
    # and then AMENDMENT TO HOUSE RULES and the rule's text (4 January 2017).
    # Or two headings above it: AMENDMENT TO SPECIAL SESSION RULES, OFFERED
    # BY REP. JR HOELL, and the rule (25 July 2018), with "Rep. Hoell offered
    # a floor amendment." before them both.
    PUT = ("moved", "uc", "question", "challenge", "objection", "report")
    j = i
    while j > 0 and j > i - 3 and not any(x["k"] in PUT for b in sel
                                          for x in _said(text, b[1], b[2])):
        sel.insert(0, blocks[j - 1])
        j -= 1
    # The heading the vote was put under: the first of the blocks kept that
    # is not the day's business and reads as a question's heading -- not a
    # committee's name in a list (EXECUTIVE DEPARTMENTS AND ADMINISTRATION),
    # not a line of a table of election returns (FOR GOVERNOR).
    heading = next((b[0] for b in sel if b[0] and not BUSINESS.match(b[0])
                    and QUESTION_HEAD.search(b[0])), None)
    if heading is None and sel[0][0] and UC_HEAD.match(sel[0][0]):
        heading = sel[0][0]
    amend = any(b[0] and re.search(r"AMENDMENT\s+TO\b.*\bRULES?\b", b[0]) for b in sel)
    said = []
    for h, s, e in sel:
        said += _said(text, s, e, report=bool(h and "REPORT" in h), amend=amend)
    out = {"heading": heading, "said": said, "start": sel[0][1]}
    # "The question now being should Representative Charlie Burns be
    # reprimanded ...?" puts again a question put further back, under the
    # heading it was put with: find where it was put, in the same sitting.
    now = next((x for x in said if x["k"] == "question" and QUESTION_NOW.match(x["t"])), None)
    if now and (heading is None or CONTINUES.match(heading or "")):
        q = QUESTION_NOW.match(now["t"]).group("q")
        key = re.sub(r"\W+", " ", q).strip().lower()[:60]
        back_lo = max(0, sel[0][1] - 60000)
        day = list(DAY_HEADER.finditer(text, back_lo, sel[0][1]))
        if day:
            back_lo = day[-1].start()
        flat = text[back_lo:sel[0][1]]
        # Where the same question was first put, read as words.
        words = re.sub(r"\W+", " ", flat).lower()
        k = words.find(key)
        if k >= 0:
            # Map the place in the words back to the text, by counting.
            n_words = len(words[:k].split())
            spans = list(re.finditer(r"\w+", flat))
            if n_words < len(spans):
                at0 = back_lo + spans[n_words].start()
                hs = _heads(text, back_lo, at0)
                hs = [x for x in hs if not BUSINESS.match(x[1]) and not CONTINUES.match(x[1])]
                if hs:
                    h0 = hs[-1]
                    nxt = TALLY_ANY.search(text, h0[0], at0)
                    if not nxt:
                        earlier = _said(text, h0[0], at0 + 400, report="REPORT" in h0[1])
                        earlier = [x for x in earlier if x["k"] in ("moved", "question")][:2]
                        if earlier:
                            for x in earlier:
                                x["earlier"] = True
                            out["said"] = earlier + said
                            out["heading"] = h0[1]
                            out["start"] = h0[0]
    return out


def outcome_after(text, end, body):
    """The Journal's own sentence on what the vote did, from the tally to the
    next one, in its own case: "and the ruling of the Chair was upheld."."""
    nxt = TALLY_ANY.search(text, end)
    stop = nxt.start() if nxt else min(len(text), end + 20000)
    seg = text[end:stop]
    low = seg.lower()
    if len(low) != len(seg):
        return ""
    if body == "S":
        for ln in seg.split("\n")[:8]:
            s = ln.strip()
            if s and RO.J_ANCHOR.search(s.lower()):
                return re.sub(r"\s+", " ", s)
        return ""
    _v, km = RO._first_word(low)
    if not km:
        return ""
    a = max(seg.rfind("\n", 0, km.start()), 0)
    stopm = re.compile(r"\.(?=\s|$)").search(seg, km.end(), km.end() + 300)
    s = re.sub(r"\s+", " ", seg[a:stopm.end() if stopm else km.end()]).strip()
    # Columns of names share the line: keep from the outcome's own opening,
    # and nothing where a name still stands inside it -- "failed lacking the
    # necessary drye, margaret and the motion aron, judy" is the page's
    # columns read across, not a sentence anybody wrote.
    m = re.search(r"\b(?:and\s+the|The\s+motion|Motion|the\s+motion|The\s+ruling)\b.*$", s)
    s = m.group(0) if m else ""
    # Nor one with a count of its own: "The motion passed with a vote of 20 to
    # 14." stood after a roll call of 184-70 (12 May 2022), a committee's.
    if not s.endswith(".") or re.search(r"\b[A-Z][a-z'’-]+,\s+[A-Z][a-z]+\b", s) \
            or re.search(r"\b\d+\s*(?:to|-|–)\s*\d+\b", s):
        return ""
    return s


AFTER = re.compile(
    r"(?:The\s+Speaker\s+informed\s+(?:Rep\.|Representative)\s+(?P<a>[A-Z][\w.'’ -]{1,40}?)\s+of\s+"
    r"the\s+(?:censure|reprimand)|(?:Rep\.|Representative)\s+(?P<b>[A-Z][\w.'’ -]{1,40}?)\s+was\s+"
    r"(?:reprimanded|censured|expelled))[^.]*\.")


def after_line(text, end):
    """The Journal's line after a vote that says what it did to a member:
    "The Speaker informed Rep. Corcoran of the censure by the House." """
    nxt = TALLY_ANY.search(text, end)
    stop = min(nxt.start() if nxt else len(text), end + 30000)
    m = AFTER.search(_joined(text[end:stop]))
    return m.group(0) if m else ""


# ----------------------------------------------------------------- reading


def subject_of(said_text, kind):
    """The member a reprimand, censure or privilege is about, as printed:
    "Travis Corcoran", "Charlie Burns", "Read". "" where not one name."""
    pats = [
        r"(?:censure|reprimand|expel)\w*\s+(?:of\s+)?(?:Rep\.|Representative)\s+(?P<n>[A-Z][\w'’-]+"
        r"(?:\s+[A-Z][\w'’-]+){0,2}?)(?=\s+(?:by|be|for|in|from|and|was|is)\b|[,.;?]|$)",
        r"(?:Rep\.|Representative)\s+(?P<n>[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+){0,2}?)\s+be\s+"
        r"(?:reprimanded|censured|expelled|permitted|allowed)",
        r"directive\s+regarding\s+(?:Rep\.|Representative)\s+(?P<n>[A-Z][\w'’-]+)",
        r"sanctions\s+on\s+(?:Rep\.|Representative)\s+(?P<n>[A-Z][\w'’-]+)",
        r"(?:reprimand|censure)\s+for\s+(?:Rep\.|Representative)\s+(?P<n>[A-Z][\w'’-]+)",
        r"allow\w*\s+(?:Rep\.|Representative)\s+(?P<n>[A-Z][\w'’-]+)\s+(?:to\s+return|back)",
        r"(?:Rep\.|Representative)\s+(?P<n>[A-Z][\w'’-]+)\s+be\s+allowed\s+back",
    ]
    names = []
    for p in pats:
        for m in re.finditer(p, said_text):
            n = m.group("n").strip()
            if n not in names:
                names.append(n)
    surnames = {n.split()[-1] for n in names}
    if len(surnames) != 1:
        return ""
    return max(names, key=len)


def uc_of(said):
    """(name, subject) of the unanimous consent an objection was made to."""
    for x in said:
        if x["k"] == "uc":
            m = re.search(r"(?:Reps?\.|Representative)\s+(?P<n>[A-Z][\w.'’ -]{1,40}?)\s+requested\s+"
                          r"unanimous\s+consent\s+of\s+the\s+(?:House|Senate)(?:\s+(?:regarding|"
                          r"concerning|on|about)\s+(?P<a>.+?))?(?:\s+and\s+addressed\s+the\s+"
                          r"(?:House|Senate))?\.?$", x["t"], re.I)
            if m:
                return m.group("n").strip(), (m.group("a") or "").strip()
    for x in said:
        if x["k"] == "objection":
            m = re.search(r"given\s+by\s+(?:Rep\.|Representative)\s+(?P<n>[A-Z][\w'’-]+)", x["t"])
            if m:
                return m.group("n"), ""
    return "", ""


def classify(heading, said, words):
    """The kind of question: the last question or motion of the passage
    decides, then the heading, then the passage as a whole, then the
    roll-call file's own words. A motion on a reprimand -- to table it, to
    refer it -- is discipline."""
    # The rule's or the report's own text is what is proposed, not the
    # question: a rule on weapons in the anterooms is a rule.
    every = " ".join([heading or ""] + [x["t"] for x in said if x["k"] != "text"])
    found = kinds_in(every)
    if "discipline" in found:
        # An appeal of a ruling made during a reprimand is still an appeal.
        last = [x for x in said if x["k"] in ("question", "challenge") and not x.get("earlier")]
        if last and "appeal" in kinds_in(last[-1]["t"]) and "discipline" not in kinds_in(last[-1]["t"]):
            return "appeal"
        return "discipline"
    if "privileges" in found:
        return "privileges"
    finals = [x for x in said if x["k"] in ("question", "challenge", "objection", "moved")]
    for x in reversed(finals):
        got = [k for k in kinds_in(x["t"]) if k not in ("motion",)]
        # An objection to a member's unanimous consent; an objection to
        # printing a debate (10 June 2021) is the printing's.
        if x["k"] == "objection" and (any(y["k"] == "uc" for y in said)
                                      or "unanimous consent" in x["t"].lower()):
            return "member_continue"
        if x["k"] == "objection":
            continue
        if got:
            return got[0]
    if heading:
        got = kinds_in(heading)
        if got:
            return got[0]
    if found:
        return found[0]
    fk = kinds_in(words)
    return fk[0] if fk else "other"


STOP = set("adoption adopt adopted motion question senate house rule rules that with from "
           "shall this upon into have been being their there where which whom".split())


def shares_words(words, said):
    """Does the last question put above the tally share a word -- its first
    five letters -- with the roll-call file's own words for the vote? The
    mover and seconder the Senate's file names ("Sen. Clegg/Sen. Kenney")
    are not words of the question."""
    w = re.sub(r"\b(?:Sen|Rep)s?\.\s*[A-Z][\w'’-]+", " ", words or "")

    def toks(s):
        # A word of four letters or more, or a number of a rule ("5-3").
        return {t[:5] for t in re.findall(r"[a-z0-9-]+", s.lower())
                if t not in STOP and (len(t) >= 4 or re.search(r"\d", t))}
    mine = toks(w)
    put = [x["t"] for x in said if x["k"] in ("question", "moved", "uc", "objection", "challenge",
                                             "report")]
    if not mine or not put:
        return False
    return bool(mine & toks(put[-1]))


def bills_in(said):
    """The bill numbers the passage names, as data/bills.json keys them."""
    got = []
    for x in said:
        for m in BILL.finditer(x["t"]):
            b = f"{'SS' if m.group('ss') else ''}{m.group('k')}{int(m.group('n'))}"
            if b not in got:
                got.append(b)
    return got


# ------------------------------------------------------------ one line

def _in_order(slot, excerpt):
    """Every word of `slot` stands in `excerpt`, in the same order (gate 8)."""
    words = re.findall(r"[\w'’-]+", slot.lower())
    hay = re.findall(r"[\w'’-]+", excerpt.lower())
    i = 0
    for w in hay:
        if i < len(words) and w == words[i]:
            i += 1
    return i == len(words)


ON_A_MOTION = re.compile(
    r"\b(?:amend|table|reconsider|refer|postpone|divide)\w*\s+(?:the|a)\s+(?:main\s+)?motion\b|"
    r"\bmotion\b[^.]{0,200}\bbe\s+(?:laid\s+on\s+the\s+table|indefinitely\s+postponed|referred|"
    r"divided)\b|\bbe\s+laid\s+on\s+the\s+table\b|\breconsider\b", re.I)


def _trim(s, n=16):
    """At most n words of a slot, ended at a comma where one comes after the
    eighth word: "a bill amending how revenues ... the education trust fund"
    rather than "... trust fund, a …"."""
    w = s.split()
    if len(w) <= n:
        return s
    head = " ".join(w[:n])
    c = head.rfind(",")
    if c > 0 and len(head[:c].split()) >= 8:
        return head[:c] + " …"
    return head + " …"


def one_line(kind, said, uc):
    """(line, slots) -- a few of the site's words for the kind and a few of
    the Journal's for what it was on, or ("", []) where the passage does not
    give them plainly. Never for a member's discipline (gate 7)."""
    if kind in PERSONAL:
        return "", []
    # THE LAST QUESTION PUT IS THE VOTE'S. A motion on a motion -- to table
    # the amendment to House Rule 63 (2 January 2019), to amend the motion to
    # limit debate to two hours a side (5 June 2013) -- is not the motion it
    # is on, and a line written from that motion's words would say the House
    # voted on something it did not.
    put = [x for x in said if x["k"] in ("question", "moved", "challenge", "objection", "uc",
                                         "ruled", "report")]
    last = put[-1]["t"] if put else ""
    if ON_A_MOTION.search(last) or (kind not in ("member_continue", "appeal")
                                    and kind not in kinds_in(last)):
        return "", []
    moved = [x["t"] for x in said if x["k"] == "moved"][-1:]
    quest = [x["t"] for x in said if x["k"] == "question"][-1:]
    if kind == "member_continue":
        name, about = uc
        if not name:
            return "", []
        if about:
            return (f"Whether Rep. {name} could go on with remarks on {_trim(about, 10)}",
                    [name, about])
        return f"Whether Rep. {name} could go on speaking", [name]
    if kind == "appeal":
        for s in [x["t"] for x in said if x["k"] in ("challenge", "ruled")]:
            m = re.search(r"ruled\s+(?P<o>(?:the\s+)?(?:motion|amendment|appeal|sections?)\b[^,.]{0,90}?)"
                          r",?\s+(?P<r>dilatory|out\s+of\s+order|non-?germane|not\s+germane|"
                          r"in\s+order)\b", s)
            if m and m.group("o").strip().lower() not in ("the motion", "the appeal",
                                                         "the amendment"):
                o = m.group("o").strip()
                return f"Uphold the ruling that {o} was {m.group('r')}", [o, m.group("r")]
            m = re.search(r"ruling\s+of\s+the\s+Chair\s+on\s+(?P<o>[^.]{8,300})", s)
            if m:
                o = m.group("o").strip()
                return f"Uphold the chair's ruling on {_trim(o, 14)}", [o]
        return "", []
    if kind == "suspend_rules":
        for s in moved:
            m = re.search(r"(?:be\s+so\s+far\s+suspended\s+as\s+to|to\s+suspend\s+(?:all\s+)?(?:the\s+)?"
                          r"(?:House\s+|Senate\s+)?(?:Rules?|Rule\s+[\d-]+)(?:\s+necessary)?)\s+"
                          r"(?P<p>(?:to\s+)?allow\b[^.;]{4,}|(?:for\s+the\s+purpose\s+of)\b[^.;]{4,})", s)
            if m:
                p = re.sub(r"^to\s+", "", m.group("p").strip())
                return f"Suspend the rules to {_trim(p, 18)}", [p]
        return "", []
    if kind == "print":
        if any(re.search(r"\breconsider", s, re.I) for s in moved + quest):
            return "", []
        for s in moved + quest:
            m = re.search(r"(?:moved\s+that|being\s+to\s+print)\s+(?P<w>the\s+(?:debate|remarks|"
                          r"speech|parliamentary\s+inquiry)\b[^,.]{0,80}?)(?:,|\s+be\s+printed|\s+in\s+"
                          r"the\s+permanent)", s, re.I)
            if m:
                w = m.group("w").strip()
                return f"Print {w} in the permanent Journal", [w]
        return "", []
    if kind == "limit_debate":
        for s in moved:
            m = re.search(r"moved\s+that\s+(?:the\s+)?debate\s+(?P<on>on\s+[^.]{3,100}?)\s+be\s+limited\s+"
                          r"(?P<to>to\s+[^.]{3,80})", s, re.I)
            if m:
                on, to = m.group("on").strip(), m.group("to").strip().rstrip(".")
                return f"Limit debate {on} {to}", [on, to]
        return "", []
    if kind == "rules":
        # Only the adoption of an amendment the passage names.
        for s in [x for x in quest + moved if re.search(r"\badoption\s+of\b|\boffered\b", x)]:
            m = re.search(r"(?P<x>(?:the\s+|an?\s+)?(?:floor\s+)?amendments?\s+to\s+(?:the\s+)?(?:House|Senate|"
                          r"Joint)\s+Rules?(?:\s+[\d-]+[a-z]?)?)", s)
            if m:
                x = m.group("x").strip()
                return f"Adopt {x}", [x]
        return "", []
    if kind == "adjourn":
        # A motion to adjourn or recess, not the early session's resolution,
        # which adjourns it in order to pass every bill ordered to third
        # reading (2 May 2018): that one is told by its own words alone.
        for s in moved + quest:
            if re.search(r"RESOLVED", s):
                continue
            m = re.search(r"\b(?:moved\s+(?:that\s+the\s+(?:House|Senate)\s+(?:now\s+)?|to\s+)|"
                          r"motion\s+to\s+)(?P<x>(?:adjourn|recess|stand\s+in\s+recess)\w*"
                          r"(?:\s+(?:from|to|until)\s+[^,.]{3,60})?)", s, re.I)
            if m:
                x = m.group("x").strip()
                return f"To {x}", [x]
        return "", []
    if kind == "justices":
        for s in moved + quest:
            if re.search(r"opinion\s+of\s+the\s+justices", s, re.I):
                return "Ask the justices of the Supreme Court for an opinion", ["opinion of the justices"]
        return "", []
    return "", []


# ----------------------------------------------------------------- members

def load_careers(path=CAREERS):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def resolve_member(name, body, term, careers):
    """The one member of `body` serving in `term` the printed name can mean,
    by their employee number (careers.json's key, the site's member id), or
    "" where it can mean none or more than one."""
    if not name or not careers:
        return ""
    parts = name.replace(".", " ").split()
    last = parts[-1].lower()
    first = parts[0].lower() if len(parts) > 1 else ""
    hits = []
    for eid, c in careers.items():
        if not c.get("named") or (c.get("last") or "").lower() != last:
            continue
        t = (c.get("by_term") or {}).get(term) or {}
        if body not in (t.get("chambers") or []):
            continue
        if first and not (c.get("first") or "").lower().startswith(first):
            continue
        hits.append(eid)
    return hits[0] if len(hits) == 1 else ""


# ---------------------------------------------------------------- the bills

def load_bills(path=Path("data/bills.json")):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return {t: set(b) for t, b in d.items() if isinstance(b, dict)}
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------- addresses

def addresses(path=Path("archive/queue.csv")):
    """{"journals/2026/HJ 14 May 21, 2026.txt": address} for every Journal
    the drain fetched: the file this read is the one at that address, so the
    link is to the document itself and not to a number in a series."""
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except OSError:
        return {}
    by = defaultdict(list)
    for r in rows:
        if r.get("kind") == "journal" and r.get("state") == "held" and r.get("url"):
            by[r["path"].replace("\\", "/")].append(r)
    out = {}
    for p, rs in by.items():
        pick = rs if len(rs) == 1 else [r for r in rs if r.get("fetched")]
        if len(pick) == 1 and p.lower().endswith(".pdf"):
            out[p[:-4] + ".txt"] = pick[0]["url"]
    return out


def journal_name(f, body):
    """"House Journal 14" from journals/2026/HJ 14 May 21, 2026.txt; the
    file's own name where it carries no number ("HJ NO 21 11-16-2005")."""
    b = Path(f).stem
    b2 = re.sub(r",?\s*(19|20)\d\d", "", b)
    m = re.search(r"[HS]J[\s_]*(?:NO\s*)?0*(\d+)", b2)
    word = "House Journal" if body == "H" else "Senate Journal"
    return f"{word} {int(m.group(1))}" if m else f"{word} ({b})"


def _rel(f, root):
    try:
        return Path(f).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(f).as_posix()


# --------------------------------------------------------------- the votes

def rc_key(r):
    return f'{r.get("year")}-{r.get("body")}-{r.get("number")}'


def load_rollcalls(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    rolls, nobill = [], []
    for term, bills in d.items():
        if not isinstance(bills, dict):
            continue
        for key, rows in bills.items():
            for r in rows or ():
                r = dict(r)
                r["_term"] = term
                rolls.append(r)
                if key == "_procedural":
                    nobill.append(r)
    return rolls, nobill


def read_vote(r, j, root, cache, careers, bills, urls, approved):
    """One roll call on no bill, its tally `j` in the Journal: the entry this
    file holds for it, shown or held back."""
    key = rc_key(r)
    body = r["body"]
    f = j["file"]
    text = _read(f, cache)
    rel = _rel(f, root)
    page, pdf, _d = page_at(text, j["at"])
    e = {"key": key, "body": body, "date": r.get("date") or "", "term": r["_term"],
         "file": rel, "journal": journal_name(f, body), "page": page, "pdf_page": pdf,
         "url": urls.get(rel, ""), "yeas": r["yeas"], "nays": r["nays"],
         "passed": bool(r.get("passed")), "words": r.get("question_raw") or ""}
    held = []
    # 1. The tally printed at the paired place is this roll call's.
    if (j["y"], j["n"]) not in RO._tally_set(r):
        held.append("tally: the Journal's count at the paired place is not this roll call's")
    # 2. The page is dated the day of the vote, or up to three days before.
    when = sitting_date(text, j["at"], body)
    try:
        rd = date.fromisoformat(e["date"])
    except ValueError:
        rd = None
    if when is None or rd is None:
        held.append("date: the Journal page's date could not be read")
    elif not 0 <= (rd - when).days <= 3:
        held.append(f"date: the tally is printed on a page of {when.isoformat()}, "
                    f"and the roll call is dated {e['date']}")
    e["page_date"] = when.isoformat() if when else ""
    # The passage.
    p = passage(text, j["at"], body)
    said = p["said"]
    out = outcome_after(text, j["end"], body)
    if out:
        said = said + [{"k": "outcome", "t": out}]
    if p["start"] < j["at"]:
        e["page_from"] = page_at(text, p["start"])[0]
    e["heading"] = p["heading"] or ""
    e["said"] = said
    kind = classify(p["heading"], [x for x in said if x["k"] != "outcome"], e["words"])
    e["kind"] = kind
    # 3. The roll-call file's own kind of question is in the passage.
    fk = file_kind(e["words"])
    every = " ".join([p["heading"] or ""] + [x["t"] for x in said])
    if fk and fk not in kinds_in(every) and not (fk == "rules" and kind == "suspend_rules"):
        held.append(f"question: the roll-call file names {KINDS[fk].lower()}, and the passage "
                    f"at this tally does not")
    # 3b. A count the Journal prints more than once in the file -- the
    # Senate's 24-0 of a remote session, twenty times a day -- can be paired
    # a vote out of step and pass every gate above. There the question put
    # last must share a word with the roll-call file's own: "Adoption of the
    # Report by the Select Committee" is not "The question is on the
    # adoption of the Resolution." (6 January 2021).
    same = sum(1 for m in RO.J_TALLY[body].finditer(text)
               if (int(m.group(1)), int(m.group(2))) == (j["y"], j["n"]))
    if same > 1 and not shares_words(e["words"], said):
        held.append(f"question: this count is printed {same} times in the Journal, and the "
                    "question put above this one does not share a word with the roll-call "
                    "file's")
    # 4. The Journal's outcome agrees with the record's.
    if j.get("carried") is None:
        held.append("outcome: the Journal's sentence after the tally could not be read")
    elif bool(j["carried"]) != bool(r.get("passed")):
        held.append("outcome: the Journal's sentence after the tally and the outcome on record "
                    "disagree")
    # 5. A sentence that says what was put.
    if not any(x["k"] not in ("outcome",) for x in said):
        held.append("passage: no sentence above the tally says what was put")
    e["held"] = held
    # 6. One bill.
    bs = bills_in([x for x in said if x["k"] != "outcome"])
    e["bills"] = bs
    term_bills = bills.get(r["_term"]) or set()
    e["bill"] = bs[0] if len(bs) == 1 and (not bills or bs[0] in term_bills) else ""
    # The member it is about.
    every_said = " ".join(x["t"] for x in said)
    uc = uc_of(said)
    e["after"] = after_line(text, j["end"]) if kind in PERSONAL else ""
    if kind in PERSONAL:
        name = subject_of(every_said, kind)
        # 7. Named both in the motion or report and in the line after.
        if kind == "discipline" and name:
            a = AFTER.search(e["after"] or "")
            after_name = (a.group("a") or a.group("b") or "") if a else ""
            if not after_name or after_name.split()[-1] != name.split()[-1]:
                name = ""
        e["member"] = name
    elif kind == "member_continue":
        e["member"] = uc[0]
        e["about"] = uc[1]
    else:
        e["member"] = ""
    e["member_id"] = resolve_member(e["member"], body, r["_term"], careers)
    # The one line.
    line, slots = one_line(kind, [x for x in said if x["k"] != "outcome"], uc)
    why = ""
    if len(bs) > 1:
        line, why = "", "the passage names more than one bill"
    elif line and not all(_in_order(s, every_said) for s in slots):
        line, why = "", "a word of the summary is not in the passage"
    elif kind in PERSONAL:
        ok = approved.get(key) or {}
        if ok.get("line") and ok.get("file") == rel and ok.get("page") in (page, None):
            line, why = ok["line"], ""
            e["line_by"] = "person"
        else:
            why = "a member's discipline: only a line a person approved"
    elif not line:
        why = "no summary for this kind of passage"
    e["line"] = line
    if why:
        e["line_held"] = why
    return e


# ------------------------------------------------- votes only the Journal has

DIV_SENT = re.compile(
    r"On\s+a\s+division\s+vote,?\s*(?:with\s+)?(?P<y>\d+)\s+members?\s+having\s+(?:voted|spoken)\s+in"
    r"\s+the\s+affirmative,?\s*(?:and\s+)?(?P<n>\d+)\s+in\s+the\s+negative,?\s*(?P<rest>[^.]{0,240}\.)",
    re.I | re.S)
JOURNAL_ONLY = {"discipline", "privileges", "member_continue", "appeal", "suspend_rules", "rules"}


def journal_only(f, body, root, cache, careers, urls, term_of):
    """[entry] -- the divisions under a heading of a no-bill kind in one House
    Journal, and the voice votes on a member's discipline."""
    if body != "H":
        return []
    text = _read(f, cache)
    rel = _rel(f, root)
    out = []
    for m in DIV_SENT.finditer(text):
        p = passage(text, m.start(), body)
        said = [x for x in p["said"] if x["k"] != "outcome"]
        if not said:
            continue
        kind = classify(p["heading"], said, "")
        if kind not in JOURNAL_ONLY:
            continue
        bs = bills_in(said)
        # A division on a bill's own motion is the bill's: its page has it.
        if bs and kind not in ("appeal", "discipline", "privileges", "member_continue"):
            continue
        # Nor a motion on a bill at all: the question last put names a bill
        # and is not a ruling or a member's consent -- tabling SB 162-FN is
        # SB 162-FN's (3 June 2021), whatever its title says.
        put = [x for x in said if x["k"] in ("question", "moved", "challenge", "uc", "objection")]
        if put and bills_in(put[-1:]) and not re.search(
                r"ruling|decision\s+of|unanimous\s+consent|reprimand|censure", put[-1]["t"], re.I):
            continue
        when = sitting_date(text, m.start(), body)
        if when is None:
            continue
        page, pdf, _d = page_at(text, m.start())
        y, n = int(m.group("y")), int(m.group("n"))
        rest = re.sub(r"\s+", " ", m.group("rest")).strip()
        # The Journal's own words, read as rollcall_outcomes reads them: "the
        # member was not allowed to continue" (25 February 2021) failed.
        carried, _km = RO._first_word(rest.lower())
        if carried is None:
            continue
        carried = bool(carried)
        sent = re.sub(r"\s+", " ", m.group(0)).strip()
        term = term_of(str(when.year), when.isoformat())
        e = {"key": f"{when.isoformat()}-{body}-d{m.start()}", "body": body,
             "date": when.isoformat(), "term": term, "file": rel,
             "journal": journal_name(f, body), "page": page, "pdf_page": pdf,
             "url": urls.get(rel, ""), "how": "division", "yeas": y, "nays": n,
             "passed": carried, "heading": p["heading"] or "",
             "said": said + [{"k": "outcome", "t": sent}], "kind": kind,
             "bills": bs, "bill": bs[0] if len(bs) == 1 else "", "at": m.start()}
        every = " ".join(x["t"] for x in said)
        if kind in PERSONAL:
            name = subject_of(every, kind)
            e["after"] = after_line(text, m.end())
            a = AFTER.search(e["after"] or "")
            after_name = (a.group("a") or a.group("b") or "") if a else ""
            if kind == "discipline" and (not after_name or not name
                                         or after_name.split()[-1] != name.split()[-1]):
                name = ""
            e["member"] = name
        elif kind == "member_continue":
            e["member"], e["about"] = uc_of(said)
        else:
            e["member"] = ""
        e["member_id"] = resolve_member(e["member"], body, term, careers)
        line, slots = one_line(kind, said, uc_of(said))
        if len(bs) > 1 or (line and not all(_in_order(s, every) for s in slots)):
            line = ""
        e["line"] = line
        out.append(e)
    # Voice votes on a member's discipline: "MOTION TO REPRIMAND ... Motion
    # adopted." with no count -- read only for the kinds about a person.
    for h_at, h in _heads(text, 0, len(text)):
        if not re.search(r"REPRIMAND|CENSURE|EXPUL|EXPEL", h):
            continue
        nxt_tally = TALLY_ANY.search(text, h_at)
        nxt_head = next((a for a, _h in _heads(text, h_at + 1, min(len(text), h_at + 8000))), None)
        end = min(x for x in (nxt_tally.start() if nxt_tally else len(text),
                              nxt_head or len(text), h_at + 8000))
        chunk = text[h_at:end]
        if DIV_SENT.search(chunk) or TALLY_ANY.search(chunk):
            continue
        v = re.search(r"(?:^|\n)[ \t]*(?:The\s+)?Motion\s+(?:was\s+)?(?P<v>adopted|failed)\.", chunk, re.I)
        if not v:
            continue
        said = _said(text, h_at, h_at + v.start())
        if not said:
            continue
        when = sitting_date(text, h_at, body)
        if when is None:
            continue
        page, pdf, _d = page_at(text, h_at)
        term = term_of(str(when.year), when.isoformat())
        every = " ".join(x["t"] for x in said)
        name = subject_of(every, "discipline")
        aft = after_line(text, h_at + v.end())
        a = AFTER.search(aft or "")
        after_name = (a.group("a") or a.group("b") or "") if a else ""
        if not after_name or not name or after_name.split()[-1] != name.split()[-1]:
            name = ""
        out.append({"key": f"{when.isoformat()}-{body}-v{h_at}", "body": body,
                    "date": when.isoformat(), "term": term, "file": rel,
                    "journal": journal_name(f, body), "page": page, "pdf_page": pdf,
                    "url": urls.get(rel, ""), "how": "voice", "yeas": None, "nays": None,
                    "passed": v.group("v").lower() == "adopted", "heading": h,
                    "said": said + [{"k": "outcome", "t": v.group(0).strip()}],
                    "kind": "discipline", "bills": [], "bill": "", "after": aft,
                    "member": name, "member_id": resolve_member(name, body, term, careers),
                    "line": "", "at": h_at})
    return out


# ------------------------------------------------------------------- build

def load_approved(path=APPROVED):
    """{roll call key: {"line", "file", "page"}} -- the one-line summaries a
    person approved for a member's discipline. Read, never written."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    lines = d.get("lines") if isinstance(d, dict) else None
    return {k: v for k, v in (lines or {}).items() if isinstance(v, dict) and not k.startswith("_")}


def build(rollcalls_path, root="."):
    """(document, stats): every no-bill roll call the pairing places, read;
    and the votes only the House Journal has."""
    import proceedings as P
    root = Path(root)
    rolls, nobill = load_rollcalls(rollcalls_path)
    links = RO.journal_links(rolls, {id(r) for r in nobill}, root)
    careers = load_careers(CAREERS)
    bills = load_bills(root / "data" / "bills.json")
    urls = addresses(root / "archive" / "queue.csv")
    approved = load_approved(APPROVED)
    cache = {}
    entries, stats = {}, Counter()
    years_read = set()
    for r in sorted(nobill, key=lambda x: (str(x["year"]), x["body"], int(x["number"]))):
        y = str(r["year"])
        if RO.journal_files(root, r["body"], y):
            years_read.add((y, r["body"]))
        stats["no-bill roll calls"] += 1
        j = links.get(id(r))
        if not j:
            stats["not placed in a Journal"] += 1
            continue
        stats["placed"] += 1
        e = read_vote(r, j, root, cache, careers, bills, urls, approved)
        entries[e["key"]] = e
    only = []
    seen_files = set()
    for (y, b) in sorted({(str(r["year"]), "H") for r in rolls}):
        for f in RO.journal_files(root, b, y):
            if f in seen_files:
                continue
            seen_files.add(f)
            years_read.add((y, b))
            only += journal_only(f, b, root, cache, careers, urls, P.vote_term)
    for b in ("H", "S"):
        d = root / RO.JOURNAL_DIRS[b]
        if d.is_dir():
            for yd in d.iterdir():
                if yd.is_dir() and RO.journal_files(root, b, yd.name):
                    years_read.add((yd.name, b))
    return entries, only, years_read, stats


def summarize(entries, only):
    s = Counter()
    why = Counter()
    for e in entries.values():
        shown = not e["held"]
        s["shown"] += shown
        s["held back"] += not shown
        for h in e["held"]:
            why[h.split(":")[0]] += 1
        if shown:
            s["with a kind"] += e["kind"] != "other"
            s["with a one-line summary"] += bool(e["line"])
            if e.get("line_held"):
                why["line: " + e["line_held"]] += 1
    s["journal-only divisions"] = sum(1 for x in only if x["how"] == "division")
    s["journal-only voice votes"] = sum(1 for x in only if x["how"] == "voice")
    return s, why


def write(entries, only, years_read, out=OUT):
    """Merge with the file this replaces: a year read now is replaced whole,
    a year whose Journals are not on this disk is kept as it was."""
    keep_rc, keep_only = {}, []
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except ValueError:
            old = {}
        for k, e in (old.get("rollcalls") or {}).items():
            if (k.split("-")[0], e.get("body")) not in years_read:
                keep_rc[k] = e
        for e in old.get("journal_only") or []:
            if ((e.get("date") or "")[:4], e.get("body")) not in years_read:
                keep_only.append(e)
    rc = dict(keep_rc)
    rc.update(entries)
    jo = keep_only + only
    jo.sort(key=lambda e: (e["date"], e["body"], e.get("at") or 0))
    doc = {"_about": ("What the House and Senate Journals print above each roll call on no bill: "
                      "the heading, the sentences that say what was put (verbatim), the page, the "
                      "kind of question, and a one-line summary where the gates allow one. Written "
                      "by src/parse/journal_motions.py; a roll call with `held` reasons is not shown. "
                      "`journal_only` are divisions and voice votes the roll-call file does not hold."),
           "kinds": KINDS,
           "rollcalls": dict(sorted(rc.items())),
           "journal_only": jo}
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                   encoding="utf-8")
    return doc


def silence(entries, years_read):
    """The years whose Journals are on disk, whose no-bill roll calls were
    placed in them, and from which nothing at all was read."""
    by = defaultdict(lambda: [0, 0])
    for e in entries.values():
        y = e["key"].split("-")[0]
        if (y, e["body"]) not in years_read:
            continue
        by[y][0] += 1
        by[y][1] += any(x["k"] != "outcome" for x in e["said"])
    return sorted(y for y, (n, got) in by.items() if n and not got)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rollcalls", default="rollcalls.json")
    ap.add_argument("--root", default=".", help="where journals/ and journals_senate/ are")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--show", nargs="*", help="print these roll calls' entries; writes nothing")
    ap.add_argument("--check", action="store_true", help="print the counts; writes nothing")
    a = ap.parse_args()
    if not Path(a.rollcalls).exists():
        sys.exit(f"No {a.rollcalls} here: run src/parse/rollcall_parser.py first.")
    entries, only, years_read, stats = build(a.rollcalls, a.root)
    if a.show is not None:
        for k in a.show or sorted(entries):
            e = entries.get(k)
            print(json.dumps(e, ensure_ascii=False, indent=1) if e else f"{k}: not placed")
        return
    s, why = summarize(entries, only)
    print(f"{stats['no-bill roll calls']:,} roll calls on no bill; {stats['placed']:,} placed in "
          f"a Journal by the pairing, {stats['not placed in a Journal']:,} not")
    print(f"  {s['shown']:,} shown with the Journal's words, {s['held back']:,} held back; "
          f"{s['with a kind']:,} of those shown have a kind, {s['with a one-line summary']:,} a "
          "one-line summary")
    for k, v in sorted(why.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {v:4,}  {k}")
    print(f"  {s['journal-only divisions']:,} divisions and {s['journal-only voice votes']:,} "
          "voice votes only the Journal has, under a heading of a vote on no bill")
    quiet = silence(entries, years_read)
    if quiet:
        sys.exit("SILENCE: no passage was read for the no-bill roll calls of "
                 + ", ".join(quiet) + " though their Journals are on disk and the pairing "
                 "placed them -- the patterns have stopped matching the Journal's layout. "
                 "Nothing was written.")
    if a.check:
        return
    write(entries, only, years_read, Path(a.out))
    print(f"  -> {a.out}")


if __name__ == "__main__":
    main()
