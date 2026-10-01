#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-30.3
"""
The bills the House withdrew, read from the House Journal itself.

    python3 journal_bills.py            # writes journal_bills.json
    python3 journal_bills.py --check    # every introduction the journals print,
                                        #   against Docket.txt, data/bills.json
                                        #   and data/sponsors.json; writes nothing

No network. The standard library, journal_days.py for a sitting's heading and
dateline, and text_sponsors.py to read a sponsor line in --check.

WHY THIS EXISTS (30 September 2026)

Nine House bills of 2025-2026 were introduced and then withdrawn before they
were heard -- HB 234, 409, 476, 523, 678 and 736 of 2025, HB 1191, 1232 and
1476 of 2026 -- and every one of them has gone from every current-term file
the General Court publishes that is on this disk: Docket.txt, LSRs.txt,
LsrsOnly.txt and the database's Legislation view. The site had no record of
them at all. The House Journal prints each one twice: in the list of bills
introduced, with its title, its sponsors and its committee, and again on the
day it was withdrawn. This reads those two things and nothing else.

What the General Court's system does with a withdrawn bill is not stated
anywhere on disk. HB 431 of 2025, whose motion to withdraw failed 160-207,
is in every file; the nine whose withdrawal stood are in none. That is an
observation, and the page says only what was observed.

WHY FROM 2025 (FIRST_YEAR)

The House amended Rule 39(e) on 8 January 2025 (HJ 2 of 2025): a bill "may be
withdrawn only by a vote of the House prior to any public hearing", and a
request to withdraw goes on the consent calendar. No House journal on disk
from 1997 to 2024 prints a TO BE WITHDRAWN list or a MOTION TO WITHDRAW, and
the introduction lists of earlier years are printed in other shapes -- 1997
puts a blank line between entries, no period after the county and a colon
before the committee. A reader run over years it was never measured against
would be guessing, so it starts where the form starts.

WHAT IT READS

  An introduction: one entry of a list headed INTRODUCTION OF ... and "First,
  second reading and referral" --

    HB 476-FN, relative to restrictions on elective abortion. (Peternel, Carr.
    6; Aures, Merr. 13; ...; Terry, Belk. 7; Judiciary)

  the designation as printed, the title, every sponsor as printed in order,
  and the committee, which is the last piece inside the parenthesis.

  A withdrawal, in one of two forms:
    - the bill listed under TO BE WITHDRAWN inside a consent calendar the
      journal records as adopted that day, and not among the bills members
      removed from that calendar;
    - a MOTION TO WITHDRAW the journal records as adopted ("the motion to
      withdraw was adopted"), unless a later MOTION TO RECONSIDER it carried
      and the motion to withdraw, put again, failed.

  A record is written only for a bill with BOTH an introduction and a
  withdrawal that stood, and with a title, sponsors and a committee read.

THE TRAPS, every one of them met in the 2025-2026 text

  - "not introduced" placeholders, in four spellings on 7 January 2026:
    "HB 1164, - not introduced.", "HB 1437 - not introduced.",
    "HB 1470 - not introduced", "HB 1545- not introduced." The last three have
    no comma; each is its own entry and gives nothing.
  - a word broken at the margin, "(Har-" / "rington", and across a page head:
    HCR 7's "Van-" / form feed and running head / blank / "decasteele".
  - running heads inside a list, and odd-page heads that print the day and
    the page with no space between the day and the month and two spaces
    before the page: "19FEBRUARY2026HOUSERECORD  39". The page number is the
    one set off by whitespace; read loosely, that head is page 1.
  - HB 431's motion to withdraw, whose outcome ("and the motion failed")
    comes after a roll call some two hundred lines long.
  - a CACR's two-sentence title: "relating to X. Providing that ...".

SILENCE IS NOT SUCCESS. Each of these means the reader stopped recognising
what it reads, and every withdrawn bill it should have found would quietly
fall off the site, because the General Court's files no longer carry one. So
each refuses the write, exits non-zero and says where:
  - a year folder that holds a sitting of its own year and yields no
    introduction at all;
  - a file with no HOUSE JOURNAL heading, or a heading with no dateline read;
  - a withdrawal it saw and could not decide: TO BE WITHDRAWN outside a
    consent calendar, or on one not read as adopted; a motion to withdraw or
    to reconsider one with no bill or no outcome read; a reconsideration
    that carried, unless the motion to withdraw then plainly failed;
  - a House measure withdrawn with no introduction read for it, or withdrawn
    before it, or introduced without a title, sponsors or committee read.
What it reads and understands but records nothing for -- a bill members took
off the consent calendar, a Senate measure the House withdrew -- is a note.
A folder holding only December's organization day -- the next term's first
file -- has no introductions yet, and is reported rather than refused.

AND ONE BILL OF AN EARLIER TERM (EARLIER, 1 October 2026)

HB 459 of 2021 was introduced on 6 January 2021 and killed on 24 February,
198-153, on roll call 35 of that year. The General Court's bill search for
2021-2022 does not list it and its table of past bills has no row for it, so
the site had no record of it and that roll call's ballots linked to nothing.
The 2021 journal prints its introduction in the form the 2025 journals use
(HJ 2, page 49), and the vote on its committee's report (HJ 3, page 83). Those
two things are read for that one bill and no other, which is as far as the
reader was measured: its record carries "decided" where the nine carry
"withdrawn".
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import journal_days as JD

ROOT = Path("journals")
OUT = Path("journal_bills.json")
FIRST_YEAR = 2025
# {year: (bill, ...)} -- the bills of years before FIRST_YEAR read from that
# year's journals: the introduction entry, and the House's vote on the
# committee's report. Named one by one, because no list of an earlier year was
# measured beyond the entry named here (read_earlier).
EARLIER = {2021: ("HB459",)}
HOUSE_KINDS = ("HB", "HCR", "HJR", "HR", "CACR")
# A CACR is either chamber's: CACR 8 of 2025 and CACR 11 of 2026 are the
# Senate's, introduced in the House under INTRODUCTION OF SENATE BILLS. The
# list's heading says whose an entry is; these are only the Senate's own.
SENATE_KINDS = ("SB", "SCR", "SJR", "SR")

_MONTHS = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|"
           "OCTOBER|NOVEMBER|DECEMBER")
# The running head, a line of its own after a form feed. Even pages print the
# page first ("4  8JANUARY2025HOUSERECORD"), odd pages last
# ("8JANUARY2025HOUSERECORD  3"), and a few are spread across the line. The
# page number is the one whitespace sets apart from the date.
HEAD = re.compile(
    rf"^\f?[ \t]*(?:(?P<a>\d{{1,4}})[ \t]+)?\d{{1,2}}[ \t]*(?:{_MONTHS})[ \t]*\d{{4}}"
    rf"[ \t]*HOUSE[ \t]*RECORD(?:[ \t]+(?P<b>\d{{1,4}}))?[ \t]*$")

# The start of one entry: the designation at the head of a line, then a comma
# (or, once, a colon) -- or, for a placeholder, "not introduced", after a dash
# of any kind or none: the four spellings of 2026 use a hyphen, and a fifth
# with an en dash or no dash at all would otherwise be glued to the entry
# before it and publish as part of that bill's title.
ENTRY = re.compile(
    r"^(?P<kind>HB|SB|HCR|SCR|HJR|SJR|HR|SR|CACR)[ \t]*(?P<num>\d+)"
    r"(?P<suf>(?:-[A-Z]+)*)[ \t]*(?:(?P<sep>[,:])|"
    r"(?=[-–—]?[ \t]*(?i:not[ \t]+introduced)))")
PLACEHOLDER = re.compile(r"^\W*-?\s*not\s+introduced\.?\s*$", re.I)

READING = re.compile(r"^[ \t]*First,?\s+second\s+reading\s+and\s+referral[ \t]*$", re.I)
CONSENT = re.compile(r"^[ \t]*CONSENT\s+CALENDAR[ \t]*$")
REGULAR = re.compile(r"^[ \t]*REGULAR\s+CALENDAR\b")
# The two headings a withdrawal sits under, in any case: the journal prints
# them in capitals and the House Calendar the same list as "To Be Withdrawn"
# (calendars/2025/HC010.txt), and a heading not recognised is a withdrawal
# missed without a word. Whole lines, so case costs nothing.
TBW = re.compile(r"^[ \t]*TO\s+BE\s+WITHDRAWN[ \t]*$", re.I)
MOTION_W = re.compile(r"^[ \t]*MOTION\s+TO\s+WITHDRAW[ \t]*$", re.I)
MOTION_R = re.compile(r"^[ \t]*MOTION\s+TO\s+RECONSIDER[ \t]*$", re.I)
MOTION_ANY = re.compile(r"^[ \t]*MOTION\s+TO\s+[A-Z]")

ADOPTED = re.compile(r"consent\s+calendar\s+(?:was\s+)?adopted", re.I)
QUESTION = re.compile(r"The\s+question\s+being\b", re.I)
# Any question put, "now" or not: where a reconsideration that carried puts
# the motion to withdraw again ("The question now being adoption of the
# motion to withdraw."), and what that second vote did.
QUESTION_ANY = re.compile(r"The\s+question\s+(?:now\s+)?being\b", re.I)
REVOTE = re.compile(r"The\s+question\s+(?:now\s+)?being\s+(?:the\s+)?adoption\s+of\s+the\s+"
                    r"motion\s+to\s+withdraw\b", re.I)
# What became of a motion. "On a division vote, ... the motion to withdraw was
# adopted"; "... and the motion failed."; "Motion was adopted."; and, 14 times
# in the 2026 journals, "Motion adopted."
OUTCOME = re.compile(
    r"\bmotion(?:\s+to\s+(?:withdraw|reconsider))?\s+(?P<r>(?:was\s+)?not\s+adopted|"
    r"(?:was\s+)?adopted|failed|lost|carried|prevailed|did\s+not\s+prevail)\b", re.I)
TALLY = re.compile(r"YEAS\s+(\d+)\s*-?\s*NAYS\s+(\d+)", re.I)
DIVISION = re.compile(r"with\s+(\d+)\s+members?\s+having\s+voted\s+in\s+the\s+affirmative,?"
                      r"\s+and\s+(\d+)\s+in\s+the\s+negative", re.I)
VOICE = re.compile(r"\bvoice\s+vote\b", re.I)
# Where a removal from the consent calendar is printed, it follows the title:
# "HB 691-FN, prohibiting ..., removed by Reps. ..." and, in 2026, "HB 1446,
# providing .... Removed by Reps. ...". A committee report's own prose comes
# after its recommendation, so only the words before one are looked at.
RECOMMENDS = re.compile(r"\b(?:OUGHT\s+TO\s+PASS|INEXPEDIENT\s+TO|INTERIM\s+STUDY|"
                        r"REFER\s+FOR|MAJORITY:|MINORITY:)")
REMOVED_BY = re.compile(r"\bremoved\s+by\b", re.I)
BILL_IN_TEXT = re.compile(r"\b(HB|HCR|HJR|HR|CACR)\s*(\d+)\b")
FILE_NUMBER = re.compile(r"^HJ\s*0*(\d+)\b", re.I)


def term_of(year):
    y = int(year)
    t = y if y % 2 else y - 1
    return f"{t}-{t + 1}"


def bill_id(kind, num):
    return f"{kind}{int(num)}"


def squash(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ----------------------------------------------------------------- a file --

def read_lines(path):
    """The file as lines, numbered the way grep and an editor number them.

    split("\\n") and not splitlines(): splitlines() also breaks on the form
    feed every page head begins with, and its line numbers then stop matching
    the file's."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def pages(lines):
    """The page each line is on: the number in the last running head above
    it, and 1 before the first."""
    out, cur = [], 1
    for ln in lines:
        m = HEAD.match(ln)
        if m and (m.group("a") or m.group("b")):
            cur = int(m.group("a") or m.group("b"))
        out.append(cur)
    return out


def sittings(lines):
    """[(start, end, iso_date)] -- each HOUSE JOURNAL heading's block of lines.

    A "(Cont'd)" block is the previous sitting's tail and carries that
    sitting's own dateline, so it is read under its own date like any other.
    A block with no dateline is not dated and not read."""
    heads = [i for i, ln in enumerate(lines) if JD.DAY_HEADER.match(ln)]
    out = []
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        d = JD.DATELINE.search("\n".join(lines[i:min(end, i + 40)])[:1200])
        mo = JD.MONTHS.get(d.group("mon").lower()) if d else None
        if not mo:
            continue
        out.append((i, end, f"{d.group('yr')}-{mo:02d}-{int(d.group('day')):02d}"))
    return out


def join_lines(parts):
    """One entry's lines as one string.

    A line ending in a hyphen is a word broken at the margin when the next
    begins in lower case ("Har-" "rington"), and a hyphenated name broken
    after its hyphen when it does not ("Prudhomme-" "O'Brien")."""
    out = ""
    for p in parts:
        p = p.strip(" \t\f")
        if not p:
            continue
        if not out:
            out = p
        elif out.endswith("-") and not out.endswith(" -"):
            out = out[:-1] + p if p[:1].islower() else out + p
        else:
            out += " " + p
    return out


def _closed(text):
    """Whether an entry is finished: its parenthesis closed at the end, or,
    with no parenthesis at all, its sentence ended.

    The closing parenthesis has to be the sponsors' and committee's, not one
    of the title's own. HB 450 of 2025 reads "... resiliency (C-PACER)
    (Packard, Rock. 16; ...": had the page turned after "(C-PACER)", the list
    would have ended there. The sponsors' group carries a district number or
    a semicolon, and a committee alone (every Senate bill's) follows the
    title's full stop; a title's own parenthesis does neither."""
    t = text.rstrip()
    if PLACEHOLDER.match(text[ENTRY.match(text).end():] if ENTRY.match(text) else ""):
        return True
    if "(" in t:
        if not (t.endswith(")") and t.count("(") == t.count(")")):
            return False
        k = t.rfind("(")
        group, before = t[k + 1:-1], t[:k].rstrip()
        return ";" in group or bool(re.search(r"\d", group)) or before.endswith(".")
    return t.endswith(".")


def _open_paren(text):
    return text.count("(") > text.count(")")


def _continues(line, text):
    """Whether `line`, after a blank line, is the rest of the unfinished entry
    `text` rather than what follows the list. The press leaves a blank inside
    an entry now and then -- SB 83 of 2025, "a voluntary statewide" / blank /
    "self-exclusion database." -- and a blank read as the end of the list
    lost every entry after it: 135 of the 188 Senate bills of 27 March 2025.
    The rest of a title starts in lower case; the rest of a sponsor list is
    inside its open parenthesis; a heading is neither."""
    s = line.strip(" \t\f")
    if not s or ENTRY.match(s) or HEAD.match(line) or JD.NEXT_HEAD.match(line):
        return False
    if s.startswith("(") and not _open_paren(text):
        # The entry's own committee or sponsors, alone below a blank, where
        # it has not had them yet: SB 118 of 2025's "(Health, Human Services
        # and Elderly Affairs)". A title's own parenthesis -- "(C-PACER)" --
        # is not them (_closed). Only a committee the General Court's table
        # names, or a sponsor list, so that "(Speaker Packard in the Chair)"
        # is never taken for one.
        if "(" in text and _closed(text):
            return False
        group = s[1:].rstrip(".").rstrip(")")
        return bool(re.search(r"\d|;", group)) or _ckey(group) in _committee_keys()
    return not _closed(text) and (s[:1].islower() or _open_paren(text))


_CKEYS = []


def _committee_keys():
    if not _CKEYS:
        _CKEYS.append(set(committee_names()) | {_ckey(n) for n in committee_names().values()})
    return _CKEYS[0]


def entry_list(lines, start, stop, titles=False):
    """[(first, last, text)] -- the entries of one list, from `start` (its
    first entry's line) to where it ends, which is never past `stop`.

    A running head and the blank lines beside it are the press's, not the
    list's. A blank line otherwise ends the list unless an entry follows it,
    or the entry before it is unfinished and what follows is its rest
    (_continues). A line that begins with a designation starts a new entry
    unless the one before is inside its sponsor parenthesis -- the one place
    a designation could be the middle of an entry rather than the start of
    the next.

    `titles` is for a list of titles alone, TO BE WITHDRAWN's, where an entry
    is one sentence: there a designation also continues a title that has not
    ended -- "... the amendments made in" / "HB 2, the budget." is one bill
    withdrawn, not two."""
    out, cur, i = [], None, start
    broke = False             # a page head since the last line of text
    while i < stop:
        ln = lines[i]
        if HEAD.match(ln):
            broke = True
            i += 1
            continue
        if not ln.strip(" \t\f"):
            if broke:
                i += 1
                continue
            j = i + 1
            while j < stop and (not lines[j].strip(" \t\f") or HEAD.match(lines[j])):
                j += 1
            text = join_lines(cur[2]) if cur else ""
            if j < stop and ENTRY.match(lines[j].lstrip(" \t\f")) and (
                    cur is None or not _open_paren(text)):
                i = j
                continue
            # A blank line before a page head, inside an entry the page broke.
            if cur and not _closed(text) and any(HEAD.match(lines[k]) for k in range(i, j)):
                i = j
                continue
            # A blank line the press put inside an unfinished entry.
            if cur and j < stop and _continues(lines[j], text):
                i = j
                continue
            break
        s = ln.lstrip(" \t\f")
        starts = ENTRY.match(s)
        text = join_lines(cur[2]) if cur else ""
        if starts and (cur is None or not _open_paren(text)) and (
                not titles or cur is None or _closed(text)):
            if cur:
                out.append((cur[0], cur[1], join_lines(cur[2])))
            cur = [i, i, [s]]
        elif cur is None:
            break
        elif _closed(text) and (broke or JD.NEXT_HEAD.match(ln)):
            # A finished entry, and what follows is not an entry: the page
            # turned at the end of the list, or a heading begins the next
            # piece of business.
            break
        else:
            cur[1] = i
            cur[2].append(s)
        broke = False
        i += 1
    if cur:
        out.append((cur[0], cur[1], join_lines(cur[2])))
    return out


def parse_entry(text):
    """{kind, num, bill, designation, suffix, placeholder, title, sponsors,
    committee} from one introduction entry, or None."""
    m = ENTRY.match(text)
    if not m:
        return None
    kind, num, suf = m.group("kind"), m.group("num"), m.group("suf") or ""
    rest = text[m.end():].strip()
    out = {"kind": kind, "bill": bill_id(kind, num),
           "designation": f"{kind} {int(num)}{suf}", "suffix": suf,
           "placeholder": bool(PLACEHOLDER.match(text[m.end():])),
           "title": "", "sponsors": [], "committee": ""}
    if out["placeholder"]:
        return out
    paren = ""
    if rest.endswith(")"):
        # The LAST balanced group: a title can hold a parenthesis of its own.
        depth = 0
        for k in range(len(rest) - 1, -1, -1):
            if rest[k] == ")":
                depth += 1
            elif rest[k] == "(":
                depth -= 1
                if depth == 0:
                    paren, rest = rest[k + 1:-1], rest[:k]
                    break
    out["title"] = squash(rest)
    pieces = [squash(p) for p in paren.split(";") if squash(p)]
    # The committee is the last piece, and the one piece with no number in
    # it: every sponsor carries a county and district or a Senate district.
    if pieces and not re.search(r"\d", pieces[-1]):
        out["committee"] = pieces.pop()
    out["sponsors"] = pieces
    return out


# --------------------------------------------------------- a file's events --

def _blob(lines, a, b):
    return squash(" ".join(x for x in lines[a:b] if not HEAD.match(x)))


def _vote(seg):
    m = TALLY.search(seg)
    if m:
        return f"{m.group(1)}-{m.group(2)}", "roll call"
    m = DIVISION.search(seg)
    if m:
        return f"{m.group(1)}-{m.group(2)}", "division"
    if VOICE.search(seg):
        return "", "voice vote"
    return "", ""


def _carried(o):
    said = o.group("r").lower()
    return not ("not" in said or said in ("failed", "lost"))


def _motion(lines, at, stop):
    """(carried, vote, kind, bills, motion_text, revote) for the MOTION TO ...
    heading at `at`: the bills its text names, and what became of it.

    The outcome is the first one stated after the question is put and before
    the next question -- which, for HB 431, is two hundred lines of roll call
    later -- so it can never be another motion's.

    `revote` is for a reconsideration that carried, which puts the motion to
    withdraw to the House again: True or False for what that second vote did,
    None where the next question put is not that one or has no outcome."""
    blob = _blob(lines, at + 1, stop)
    q = QUESTION.search(blob)
    motion_text = blob[:q.start()] if q else blob[:600]
    after = q.end() if q else 0
    nq = QUESTION.search(blob, after)
    seg = blob[after:nq.start() if nq else len(blob)]
    o = OUTCOME.search(seg)
    if not o:
        return None, "", "", [], motion_text, None
    carried = _carried(o)
    vote, kind = _vote(seg[:o.end()])
    bills = list(dict.fromkeys(bill_id(k, n) for k, n in BILL_IN_TEXT.findall(motion_text)))
    revote = None
    if carried:
        nxt = QUESTION_ANY.search(blob, after + o.end())
        if nxt and REVOTE.match(blob, nxt.start()):
            last = QUESTION_ANY.search(blob, nxt.end())
            o2 = OUTCOME.search(blob[nxt.end():last.start() if last else len(blob)])
            revote = _carried(o2) if o2 else None
    return carried, vote, kind, bills, motion_text, revote


def _removal_window(lines, k, r):
    """The end of the lines that belong to the entry starting at `k` on a
    consent calendar ending at `r`: up to the next entry or a blank line,
    and never more than eleven lines of print. A running head and the blank
    beside it are the press's, not the end of the entry: a "removed by" the
    page turned onto is still this bill's."""
    lim, x, used = min(r, len(lines)), k + 1, 0
    while x < lim and used < 11:
        ln = lines[x]
        if HEAD.match(ln):
            x += 1
            continue
        if ENTRY.match(ln.lstrip(" \t\f")):
            break
        if not ln.strip(" \t\f"):
            if HEAD.match(lines[x - 1]) or (x + 1 < len(lines) and HEAD.match(lines[x + 1])):
                x += 1
                continue
            break
        x += 1
        used += 1
    return x


def read_file(path, year):
    """Everything one journal file says that this module reads:
    {"intros": [...], "withdrawals": [...], "failed": [...],
     "reconsiders": [...], "notes": [...], "problems": [...],
     "sittings": [iso], "lists": n}.

    A note is something read and understood that leaves no record -- a bill
    members took off the consent calendar before it was adopted. A problem is
    something this could not decide -- a withdrawal with no outcome it can
    read, a heading where it does not expect one, a sitting with no date --
    and stops the run, because each is a withdrawn bill that could otherwise
    vanish from the site without a word."""
    lines = read_lines(path)
    pg = pages(lines)
    rel = Path(path).as_posix()
    fm = FILE_NUMBER.match(Path(path).name)
    out = {"intros": [], "withdrawals": [], "failed": [], "reconsiders": [],
           "notes": [], "problems": [], "sittings": [], "lists": 0}

    def cite(date, i, num):
        return {"date": date, "journal": f"HJ {fm.group(1) if fm else num}",
                "page": pg[i], "file": rel, "line": i + 1}

    # EVERY SITTING DATED, or none of the file is trusted. A dateline printed
    # another way ("Thursday,January9,2025", as the masthead prints it) would
    # otherwise skip its sitting -- and a file whose every sitting was skipped
    # would read as a folder with no sitting of its year yet.
    heads = [i for i, ln in enumerate(lines) if JD.DAY_HEADER.match(ln)]
    days = sittings(lines)
    if not heads:
        out["problems"].append(f"{rel}: no HOUSE JOURNAL heading read, so no sitting "
                               "in it is read at all")
    elif len(days) < len(heads):
        out["problems"].append(f"{rel}: {len(heads) - len(days)} of its {len(heads)} "
                               "HOUSE JOURNAL headings carry no dateline read here, so "
                               "those sittings are not read")

    for start, end, date in days:
        out["sittings"].append(date)
        num = (JD.DAY_HEADER.match(lines[start]).group("num") or "").strip()
        # -------------------------------------------------- introductions --
        for i in range(start, end):
            if not READING.match(lines[i]):
                continue
            above = [j for j in range(max(start, i - 8), i) if "INTRODUCTION OF" in lines[j]]
            if not above:
                continue
            # Whose list: "INTRODUCTION OF SENATE BILLS" is the Senate's, and
            # a CACR printed under it is a Senate measure.
            chamber = "S" if "INTRODUCTION OF SENATE" in lines[above[-1]] else "H"
            j = i + 1
            while j < end and (not lines[j].strip(" \t\f") or HEAD.match(lines[j])):
                j += 1
            if j >= end or not ENTRY.match(lines[j].lstrip(" \t\f")):
                continue            # the RESOLUTION comes first; the list follows
            out["lists"] += 1
            for first, _last, text in entry_list(lines, j, end):
                e = parse_entry(text)
                if not e:
                    continue
                e["cite"] = cite(date, first, num)
                e["year"] = str(year)
                e["chamber"] = chamber
                out["intros"].append(e)
        # ------------------------------------------------- consent calendar --
        for t in range(start, end):
            if not TBW.match(lines[t]):
                continue
            c = next((k for k in range(t - 1, start - 1, -1) if CONSENT.match(lines[k])), None)
            if c is None or any(REGULAR.match(lines[k]) for k in range(c, t)):
                out["problems"].append(f"{rel}:{t + 1} TO BE WITHDRAWN outside a consent "
                                       "calendar: its bills are not read as withdrawn or not")
                continue
            r = next((k for k in range(t + 1, end) if REGULAR.match(lines[k])), end)
            adopted = bool(ADOPTED.search(_blob(lines, c, r)))
            removed = set()
            for k in range(c, r):
                s = lines[k].lstrip(" \t\f")
                m = ENTRY.match(s)
                if not m:
                    continue
                head = RECOMMENDS.split(_blob(lines, k, _removal_window(lines, k, r)), 1)[0]
                if REMOVED_BY.search(head):
                    removed.add(bill_id(m.group("kind"), m.group("num")))
            j = t + 1
            while j < r and (not lines[j].strip(" \t\f") or HEAD.match(lines[j])):
                j += 1
            for first, _last, text in entry_list(lines, j, r, titles=True):
                m = ENTRY.match(text)
                if not m:
                    continue
                bid = bill_id(m.group("kind"), m.group("num"))
                if not adopted:
                    out["problems"].append(f"{rel}:{first + 1} {bid} is listed to be withdrawn "
                                           "on a consent calendar the journal is not read "
                                           "as recording adopted")
                    continue
                if bid in removed:
                    out["notes"].append(f"{rel}:{first + 1} {bid} is listed to be withdrawn "
                                        "and was removed from the consent calendar")
                    continue
                out["withdrawals"].append({"bill": bid, "year": str(year),
                                           **cite(date, first, num),
                                           "how": "consent calendar"})
        # ------------------------------------------- motions, and reconsidering --
        for w in range(start, end):
            is_w, is_r = MOTION_W.match(lines[w]), MOTION_R.match(lines[w])
            if not (is_w or is_r):
                continue
            stop = next((k for k in range(w + 1, end) if MOTION_ANY.match(lines[k])), end)
            carried, vote, kind, bills, said, revote = _motion(lines, w, stop)
            if is_w:
                j = w + 1
                while j < stop and (not lines[j].strip(" \t\f") or HEAD.match(lines[j])):
                    j += 1
                m = ENTRY.match(lines[j].lstrip(" \t\f")) if j < stop else None
                if not m:
                    out["problems"].append(f"{rel}:{w + 1} MOTION TO WITHDRAW names no bill "
                                           "read here")
                    continue
                bid = bill_id(m.group("kind"), m.group("num"))
                row = {"bill": bid, "year": str(year), **cite(date, j, num), "how": "motion",
                       "vote": f"{vote}, {kind}" if vote else kind}
                if carried is None:
                    out["problems"].append(f"{rel}:{w + 1} {bid}: no outcome read for the "
                                           "motion to withdraw")
                elif carried:
                    out["withdrawals"].append(row)
                else:
                    out["failed"].append(row)
                continue
            # "the motion to withdraw", "withdrawn", or "whereby it withdrew".
            if not re.search(r"\bwithdr(?:aw|ew)", said, re.I):
                continue
            if not bills:
                out["problems"].append(f"{rel}:{w + 1} a motion to reconsider a withdrawal "
                                       "names no bill read here")
                continue
            for bid in bills:
                out["reconsiders"].append({"bill": bid, "year": str(year),
                                           **cite(date, w, num), "carried": carried,
                                           "vote": vote, "kind": kind, "revote": revote})
    return out


# ---------------------------------------------------------------- the lot --

def _ckey(s):
    """A committee name reduced the way referrals._key reduces one: case,
    punctuation, "&" and the word "and" do not vary a committee."""
    words = re.findall(r"[a-z]+", re.sub(r"\s*[&+]\s*", " and ", s or "").lower())
    return "".join(w for w in words if w != "and")


def committee_names(path="Committees.txt"):
    """{key: name} for the House's committees as the General Court's own
    table names them (code|name|abbreviation, House codes start H)."""
    out = {}
    try:
        for ln in Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines():
            f = ln.split("|")
            if len(f) >= 2 and f[0].strip().upper().startswith("H") and f[1].strip():
                out.setdefault(_ckey(f[1]), f[1].strip())
    except OSError:
        pass
    return out


def years(root=ROOT, first=FIRST_YEAR):
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(int(d.name) for d in root.iterdir()
                  if d.is_dir() and d.name.isdigit() and int(d.name) >= first)


def read_all(root=ROOT, first=FIRST_YEAR):
    """(intros, records, report, problems).

    intros: {(term, bill): entry} for every House measure the lists introduce.
    records: {term: {bill: record}} -- introduced, and withdrawn for good.
    problems: why nothing should be written, or []."""
    root = Path(root)
    problems, report = [], []
    if not root.is_dir():
        return {}, {}, report, [f"there is no {root}/ folder here"]
    ys = years(root, first)
    if not ys:
        return {}, {}, report, [f"no {root}/<year>/ folder from {first} on"]
    intros, events = {}, defaultdict(list)
    senate = set()                    # (term, bill) of a Senate measure introduced
    tally = Counter()
    for y in ys:
        files = sorted((root / str(y)).glob("*.txt"))
        got = Counter()
        own_year = 0
        for order, f in enumerate(files):
            r = read_file(f, y)
            problems += r["problems"]
            got["lists"] += r["lists"]
            own_year += sum(1 for d in r["sittings"] if d[:4] == str(y))
            for e in r["intros"]:
                if e["placeholder"]:
                    got["placeholders"] += 1
                    continue
                if e["kind"] not in HOUSE_KINDS or e.get("chamber") == "S":
                    got["senate"] += 1
                    senate.add((term_of(y), e["bill"]))
                    continue
                got["house"] += 1
                key = (term_of(y), e["bill"])
                if key in intros:
                    got["introduced twice"] += 1
                    report.append(f"{e['designation']} is introduced again at "
                                  f"{e['cite']['file']}:{e['cite']['line']}; the first is kept")
                    continue
                intros[key] = e
            for kind in ("withdrawals", "failed", "reconsiders"):
                for x in r[kind]:
                    got[kind] += 1
                    events[(term_of(y), x["bill"])].append((x["date"], f.name, x["line"], kind, x))
            report += r["notes"]
        tally.update(got)
        line = (f"journals/{y}: {len(files)} files, {got['lists']} introduction lists, "
                f"{got['house']:,} House measures introduced"
                + (f", {got['senate']:,} Senate measures" if got["senate"] else "")
                + (f", {got['placeholders']} 'not introduced' placeholders"
                   if got["placeholders"] else "")
                + f"; {got['withdrawals']} withdrawals, {got['failed']} failed motions to "
                  f"withdraw, {got['reconsiders']} reconsiderations")
        print(line)
        if not files or not own_year:
            print(f"  journals/{y} holds no sitting of {y} yet "
                  f"({'no files' if not files else 'only an earlier sitting'}), so it has "
                  "no introductions to read")
        elif not got["house"]:
            problems.append(f"journals/{y} holds {own_year} sittings of {y} and not one "
                            "introduction was read from it: the list format has changed "
                            "or the files are not what they should be")

    names = committee_names()
    records = defaultdict(dict)
    for key, evs in sorted(events.items()):
        term, bid = key
        standing = None
        for _d, _f, _l, kind, x in sorted(evs, key=lambda v: (v[0], v[1], v[2])):
            if kind == "withdrawals":
                standing = dict(x)
            elif kind == "reconsiders" and standing:
                where = f"{x['file']}:{x['line']}"
                if x["carried"] is None:
                    problems.append(f"{where} {bid} ({term}): no outcome read for the motion "
                                    "to reconsider its withdrawal")
                elif x["carried"] and x.get("revote") is False:
                    report.append(f"{bid} ({term}): its withdrawal of {standing['date']} was "
                                  "reconsidered, the motion carried, and the motion to "
                                  "withdraw then failed, so it does not stand")
                    standing = None
                elif x["carried"]:
                    # The House voted on withdrawing it again, and what it did
                    # is not read here: carried again, it is withdrawn on this
                    # day rather than the first, which nothing here records.
                    problems.append(f"{where} {bid} ({term}): its withdrawal was reconsidered "
                                    "and the motion carried, and the second vote on "
                                    "withdrawing it is "
                                    + ("read as adopted" if x.get("revote") else "not read")
                                    + "; a person should say what stands")
                    standing = None
                else:
                    standing["reconsideration"] = "failed" + (f", {x['vote']}" if x["vote"] else "")
        if not standing:
            continue
        e = intros.get(key)
        if not e:
            # A Senate measure the House withdrew is the Senate's record, not
            # a House record this writes, and its introduction is in a list
            # this does not key. A House measure withdrawn with no
            # introduction read is a list read short, and the bill would
            # vanish from the site.
            if bid.rstrip("0123456789") in SENATE_KINDS or key in senate:
                report.append(f"{bid} ({term}) is withdrawn at {standing['file']}:"
                              f"{standing['line']}, a Senate measure; no House record")
            else:
                problems.append(f"{bid} ({term}) is withdrawn at {standing['file']}:"
                                f"{standing['line']} but no introduction list read here "
                                "prints it: a list was read short")
            continue
        if e["cite"]["date"] > standing["date"]:
            problems.append(f"{bid} ({term}): withdrawn {standing['date']}, before the "
                            f"introduction read on {e['cite']['date']}")
            continue
        # A RECORD IS WHOLE OR NOT WRITTEN. Every House bill's entry names its
        # sponsors and its committee; one without them is two entries glued
        # together or a list that ran into the prose after it, and would
        # publish as a bill titled "... (Smith, Hills. 1; Judiciary) HB 101
        # not introduced".
        if not (e["title"] and e["sponsors"] and e["committee"]):
            problems.append(f"{bid} ({term}): its introduction at {e['cite']['file']}:"
                            f"{e['cite']['line']} is read without a "
                            + " or ".join(k for k in ("title", "sponsors", "committee")
                                          if not e[k]))
            continue
        w = {k: standing[k] for k in ("date", "journal", "page", "file", "line", "how")}
        if standing.get("vote"):
            w["vote"] = standing["vote"]
        if standing.get("reconsideration"):
            w["reconsideration"] = standing["reconsideration"]
        records[term][bid] = {
            "bill": bid, "designation": e["designation"], "suffix": e["suffix"],
            "title": e["title"], "chamber": "H", "year": e["year"],
            "committee": names.get(_ckey(e["committee"]), e["committee"]),
            "sponsors": e["sponsors"],
            "introduced": e["cite"], "withdrawn": w,
        }
    return intros, dict(records), report, problems


# ------------------------------------------------------- one earlier bill --

# The question a committee's report is put on, and what it recommends: "The
# question being adoption of the majority committee report of Inexpedient to
# Legislate."
REPORT_QUESTION = re.compile(
    r"The\s+question\s+being\s+adoption\s+of\s+the\s+(?:majority\s+)?committee\s+"
    r"report\s+of\s+(?P<what>[A-Z][A-Za-z ]+?)\s*\.")
# A roll call prints its members under their counties, each a heading of its
# own; they are not where the business after the vote begins.
COUNTIES = {"BELKNAP", "CARROLL", "CHESHIRE", "COOS", "GRAFTON", "HILLSBOROUGH",
            "MERRIMACK", "ROCKINGHAM", "STRAFFORD", "SULLIVAN"}
# What the House did with the report. Lower case, and matched with case: the
# names of a roll call are capitalised, and no member is called "adopted".
REPORT_CARRIED = re.compile(r"\badopted\b")
REPORT_LOST = re.compile(r"\bnot\s+adopted\b|\bfailed\b|\blost\b")


def _decided(lines, pg, start, end, bid, cite):
    """(record, problem) for the House's vote on `bid`'s committee report in
    one sitting, or (None, None) where the sitting does not take it up.

    The entry is the bill's own line on the regular calendar, the one that
    states the committee's recommendation -- "HB 459, prohibiting ... MAJORITY:
    INEXPEDIENT TO LEGISLATE. MINORITY: OUGHT TO PASS WITH AMENDMENT." -- and
    what is read runs from it to the next bill's entry or the next heading
    after the vote. Three things, each of which must be there: the question
    put, the roll call's count, and what the journal says became of the
    report.

    THE LAST IS PRINTED THROUGH THE ROLL CALL'S COLUMNS. The sentence "and the
    majority committee report was adopted." comes out of the PDF in three
    pieces among the names of Strafford and Sullivan. So the word is looked
    for anywhere after the count, in lower case, and held to the count: a
    report "adopted" on fewer yeas than nays is not read as adopted or as
    anything else.
    """
    at = None
    for i in range(start, end):
        m = ENTRY.match(lines[i].lstrip(" \t\f"))
        if not m or bill_id(m.group("kind"), m.group("num")) != bid:
            continue
        j = i
        while j < end and lines[j].strip(" \t\f"):
            j += 1
        if RECOMMENDS.search(_blob(lines, i, j)):
            at = i
            break
    if at is None:
        return None, None
    where = f"{cite(at)['file']}:{at + 1}"
    stop, voted = end, False
    for k in range(at + 1, end):
        ln = lines[k]
        if TALLY.search(ln):
            voted = True
        m = ENTRY.match(ln.lstrip(" \t\f"))
        if m and bill_id(m.group("kind"), m.group("num")) != bid and (
                voted or RECOMMENDS.search(_blob(lines, k, min(end, k + 4)))):
            stop = k
            break
        if voted and JD.NEXT_HEAD.match(ln) and ln.strip() not in COUNTIES \
                and not HEAD.match(ln):
            stop = k
            break
    text = _blob(lines, at, stop)
    q = REPORT_QUESTION.search(text)
    if not q:
        return None, f"{where} {bid}: no question on its committee's report is read"
    t = TALLY.search(text, q.end())
    if not t:
        return None, (f"{where} {bid}: the question on its committee's report is read "
                      "and no roll call's count after it")
    yeas, nays = int(t.group(1)), int(t.group(2))
    after = text[t.end():]
    carried = bool(REPORT_CARRIED.search(after)) and not REPORT_LOST.search(after)
    if not carried or yeas <= nays:
        return None, (f"{where} {bid}: what became of its committee's report is not "
                      f"read ({yeas}-{nays}, and the journal's words after the roll "
                      "call do not say adopted)")
    return {**cite(at), "question": squash(q.group("what")),
            "vote": f"{yeas}-{nays}", "how": "roll call", "carried": True}, None


def read_earlier(root=ROOT, earlier=None):
    """({term: {bill: record}}, report, problems) for the bills EARLIER names.

    A record is the one read_all writes for a withdrawn bill, with "decided"
    in place of "withdrawn": the vote on the committee's report, the day and
    page it is printed on, the question, the count. It is written only for a
    bill whose introduction and decision are both read. A year whose folder
    is not on this machine is a note; a folder that is here and does not
    give the bill is a problem, like any list read short.
    """
    root = Path(root)
    earlier = EARLIER if earlier is None else earlier
    names = committee_names()
    records, report, problems = defaultdict(dict), [], []
    for year, wanted in sorted(earlier.items()):
        files = sorted((root / str(year)).glob("*.txt"))
        if not files:
            report.append(f"journals/{year} is not here, so {', '.join(wanted)} of "
                          f"{year} is not read from it")
            continue
        intro, decided = {}, {}
        for f in files:
            r = read_file(f, year)
            for e in r["intros"]:
                if e["bill"] in wanted and not e["placeholder"] \
                        and e.get("chamber") != "S":
                    intro.setdefault(e["bill"], e)
            lines = read_lines(f)
            pg = pages(lines)
            fm = FILE_NUMBER.match(f.name)
            for start, end, date in sittings(lines):
                num = (JD.DAY_HEADER.match(lines[start]).group("num") or "").strip()

                def cite(i, date=date, num=num):
                    return {"date": date, "journal": f"HJ {fm.group(1) if fm else num}",
                            "page": pg[i], "file": f.as_posix(), "line": i + 1}
                for bid in wanted:
                    if bid in decided:
                        continue
                    got, why = _decided(lines, pg, start, end, bid, cite)
                    if why:
                        problems.append(why)
                    elif got:
                        decided[bid] = got
        for bid in wanted:
            e, d = intro.get(bid), decided.get(bid)
            if not e or not d:
                problems.append(
                    f"{bid} of {year}: journals/{year} gives no "
                    + " and no ".join(x for x, have in (
                        ("introduction", e), ("vote on its committee's report", d))
                        if not have) + " read here")
                continue
            if not (e["title"] and e["sponsors"] and e["committee"]):
                problems.append(f"{bid} of {year}: its introduction at {e['cite']['file']}:"
                                f"{e['cite']['line']} is read without a title, sponsors "
                                "or committee")
                continue
            if e["cite"]["date"] > d["date"]:
                problems.append(f"{bid} of {year}: decided {d['date']}, before the "
                                f"introduction read on {e['cite']['date']}")
                continue
            records[term_of(year)][bid] = {
                "bill": bid, "designation": e["designation"], "suffix": e["suffix"],
                "title": e["title"], "chamber": "H", "year": e["year"],
                "committee": names.get(_ckey(e["committee"]), e["committee"]),
                "sponsors": e["sponsors"],
                "introduced": e["cite"], "decided": d,
            }
    return dict(records), report, problems


# ------------------------------------------------------------------ --check --

def _letters(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


DOCKET_INTRO = re.compile(
    r"^\s*Introduced\s+(?:\(in\s+recess\s+of\)\s+)?(\d{1,2})/(\d{1,2})/(\d{4})\s+and\s+"
    r"referred\s+to\s+(.+?)\s+HJ\s+(\d+)\s+P\.\s*(\d+)", re.I)


def docket_intros(path="Docket.txt"):
    """{bill: (iso, committee, "HJ n", page)} for the House introductions the
    current term's docket records."""
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        f = ln.split("|")
        if len(f) < 6 or f[4].strip() != "H":
            continue
        m = DOCKET_INTRO.match(f[5])
        if m:
            mo, d, y, cm, j, pg = m.groups()
            out.setdefault(f[3].strip().upper(),
                           (f"{y}-{int(mo):02d}-{int(d):02d}", cm.strip(), f"HJ {int(j)}", int(pg)))
    return out


def check(intros, records):
    """Every introduction the journals print, measured against what this did
    not produce. Prints the counts; returns nothing."""
    bills = {}
    try:
        bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("  data/bills.json is not here: nothing to compare against")
    sponsors = {}
    try:
        sponsors = json.loads(Path("data/sponsors.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    dock = docket_intros()
    sat = None
    try:
        import text_sponsors as TS
        sat = TS.Sat.load()
    except Exception as e:                      # a missing vote file is a skipped count
        print(f"  sponsors not resolved: {type(e).__name__}: {e}")
    names = committee_names()
    c = Counter()
    absent, cm_bad, dk_bad, sp_bad = [], [], [], []
    withdrawn = {(t, b) for t, bb in records.items() for b in bb}
    for (term, bid), e in sorted(intros.items()):
        c["intros"] += 1
        rec = (bills.get(term) or {}).get(bid)
        if not rec:
            c["absent"] += 1
            absent.append(f"{e['designation']} ({term})"
                          + (" -- withdrawn, journal record written" if (term, bid) in withdrawn
                             else " -- NOT WITHDRAWN"))
            continue
        if rec.get("journal"):
            c["journal record"] += 1
            continue
        c["present"] += 1
        # The committee.
        mine = _ckey(names.get(_ckey(e["committee"]), e["committee"]))
        theirs = _ckey(rec.get("house_committee") or "")
        if not theirs:
            c["committee: none on file"] += 1
        elif mine == theirs:
            c["committee: agrees"] += 1
        else:
            c["committee: differs"] += 1
            cm_bad.append(f"{bid} {term}: journal {e['committee']!r}, "
                          f"bills.json {rec.get('house_committee')!r}")
        # The title, which an amendment may since have changed.
        t1 = _letters(re.sub(r"^\(new title\)", "", e["title"], flags=re.I))
        t2 = _letters(re.sub(r"^\(new title\)", "", rec.get("title") or "", flags=re.I))
        c["title: agrees" if t1 == t2 else "title: differs (an amendment can retitle a bill)"] += 1
        # The docket's own introduction line: day, journal and page.
        d = dock.get(bid) if term == max(bills or {"": 0}) else None
        if d:
            c["docket: compared"] += 1
            ok = (d[0] == e["cite"]["date"], d[2] == e["cite"]["journal"],
                  d[3] == e["cite"]["page"])
            for name, good in zip(("day", "journal", "page"), ok):
                c[f"docket {name}: {'agrees' if good else 'differs'}"] += 1
            if not all(ok):
                dk_bad.append(f"{bid}: journal {e['cite']['date']} {e['cite']['journal']} "
                              f"P. {e['cite']['page']}, docket {d[0]} {d[2]} P. {d[3]}")
        # The first printed sponsor against the prime on file.
        rows = (sponsors.get(term) or {}).get(bid) or []
        if sat is None or not e["sponsors"]:
            continue
        if not rows:
            c["sponsors: none on file"] += 1
            continue
        import text_sponsors as TS
        pieces = TS.split("; ".join(e["sponsors"]))
        first = sat.resolve(term, pieces[0])[0] if pieces else None
        prime = next((r for r in rows if r.get("prime")), None)
        if not first:
            c["prime: first name not resolved"] += 1
            continue
        if not prime:
            c["prime: none marked on file"] += 1
            continue
        # By id where the file uses the roster's, and otherwise by the whole
        # surname inside the name on file: "Erica de Vries" and "Charlie St.
        # Clair" have surnames of two words that a last-word key splits.
        same = (str(prime.get("member_id")) == str(first["id"])
                or _letters(first["last"]) in _letters(prime.get("name") or ""))
        c["prime: agrees" if same else "prime: differs"] += 1
        if not same:
            sp_bad.append(f"{bid}: journal {e['sponsors'][0]!r} ({first['first']} "
                          f"{first['last']}), on file {prime.get('name')!r}")
        got = [_letters(m["last"]) for m in (sat.resolve(term, p)[0] for p in pieces) if m]
        have = [_letters(r.get("name") or "") for r in rows]
        extra = [g for g in got if not any(g in h for h in have)]
        short = [h for h in have if not any(g in h for g in got)]
        c["sponsor set: same" if not extra and not short
          else "sponsor set: journal names more" if not short
          else "sponsor set: journal names fewer" if not extra
          else "sponsor set: different people"] += 1

    print(f"\n{c['intros']:,} House measures introduced in the journals read")
    print(f"  in data/bills.json from the General Court's files: {c['present']:,}")
    print(f"  in data/bills.json as a journal record:            {c['journal record']:,}")
    print(f"  not in data/bills.json:                            {c['absent']:,}")
    for x in absent:
        print(f"      {x}")
    for k in sorted(k for k in c if ":" in k):
        print(f"  {k:52} {c[k]:,}")
    for title, rows in (("committee differences", cm_bad), ("docket differences", dk_bad),
                        ("prime sponsor differences", sp_bad)):
        if rows:
            print(f"\n  {title} ({len(rows)}):")
            for x in rows[:12]:
                print(f"      {x}")
            if len(rows) > 12:
                print(f"      ... and {len(rows) - 12} more")


# --------------------------------------------------------------------- main --

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="compare every introduction with the record; write nothing")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    intros, records, report, problems = read_all(a.root)
    n = sum(len(v) for v in records.values())
    # The bills of earlier years named one by one (EARLIER), into the same
    # file: never over a record read_all wrote, which no term of theirs has.
    earlier, e_report, e_problems = read_earlier(a.root)
    report += e_report
    problems += e_problems
    n_earlier = 0
    for t, byb in earlier.items():
        for bid, r in byb.items():
            if bid in records.get(t, {}):
                report.append(f"{bid} ({t}) is read as withdrawn and is also named in "
                              "EARLIER; the withdrawal's record is kept")
                continue
            records.setdefault(t, {})[bid] = r
            n_earlier += 1
    for t in sorted(records):
        for bid, r in sorted(records[t].items(), key=lambda kv: int(re.sub(r"\D", "", kv[0]) or 0)):
            if "withdrawn" not in r:
                d = r["decided"]
                print(f"  {t} {r['designation']:12} introduced {r['introduced']['date']} "
                      f"({r['introduced']['journal']} p.{r['introduced']['page']}), its "
                      f"committee's report of {d['question']} adopted {d['date']} "
                      f"({d['journal']} p.{d['page']}) on a {d['how']}, {d['vote']}")
                continue
            w = r["withdrawn"]
            print(f"  {t} {r['designation']:12} introduced {r['introduced']['date']} "
                  f"({r['introduced']['journal']} p.{r['introduced']['page']}), withdrawn "
                  f"{w['date']} ({w['journal']} p.{w['page']}) by {w['how']}"
                  + (f", {w['vote']}" if w.get("vote") else "")
                  + (f"; reconsideration {w['reconsideration']}" if w.get("reconsideration") else ""))
    for x in report:
        print(f"  note: {x}")
    if problems:
        print("\nREFUSED: journal_bills.json is not written. A withdrawn bill this "
              "could not decide would otherwise vanish from the site without a word:",
              file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        # Last, because build_all prints a failed step's last line of stderr
        # and nothing else of it.
        print(f"REFUSED, {len(problems)} thing(s) for a person to look at; the first: "
              f"{problems[0]}", file=sys.stderr)
        return 2
    if a.check:
        check(intros, records)
        return 0
    out = Path(a.out)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(records, indent=1, sort_keys=True, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(out)
    w_terms = sum(1 for t in records
                  if any("withdrawn" in r for r in records[t].values()))
    print(f"{out}: {n} withdrawn bill(s) across {w_terms} term(s), "
          f"from {len(intros):,} introductions read"
          + (f"; and {n_earlier} bill(s) of earlier years read one by one"
             if n_earlier else "")
          + (f"; {len(report)} note(s) above" if report else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
