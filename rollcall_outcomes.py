#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-23.1
"""
What each roll call decided, from the General Court's own record, and what it
needed to carry.

rollcall_parser.py used to decide `passed` itself: a simple majority, three
fifths of all 400 (or 24) seats for anything on a CACR, and two thirds of
those voting for a question it recognised as a veto override. Three things
were wrong with that, and each put "Failed" beside a vote the chamber carried
or "Adopted" beside one it did not:

1. THREE FIFTHS WAS APPLIED TO EVERY MOTION ON A CACR. The constitution's
   three fifths is for passing one. Killing it, tabling it, amending it,
   sending it to interim study are majority questions -- except where the
   House's own rules said otherwise (Rule 20(b), amended 8 January 2009,
   HJ 2: three fifths to table or indefinitely postpone a CACR), and the
   docket says so on exactly those lines. 71 roll calls, 2026's CACR25 kill
   among them ("fell 64 short" of a bar it never faced).

2. THE DENOMINATOR IS THE MEMBERS IN OFFICE, NOT THE SEATS. 239 of 397 carried
   2012's CACR26, "By Necessary Three-Fifths Vote". Of the 104 CACR roll calls
   whose docket line names three fifths, 104 are explained by three fifths of
   the ballots on that roll call and 101 by three fifths of 400 or 24. The
   Journals agree: every CACR vote they record as needing three fifths fits
   the members in office, and 2012-H-182 fits nothing else.

3. A VETO OVERRIDE WAS RECOGNISED BY TWO WORDINGS OF ITS QUESTION. The record
   has a dozen ("OVERRIDE GOVERNOR'S VETO", "SHALL HB 474 BECOME LAW?",
   "Notwithstanding the Governor's veto..."), and 49 sustained vetoes read as
   overridden. Rules suspensions (two thirds) were not recognised at all --
   and the House roll-call files of 1999-2005 write one as "SUSP RULES", so a
   pattern for "suspen" alone would still miss them.

SO THE RECORD DECIDES, where it can be read and where it can be right.

  THE DOCKET FIRST. Each roll call is paired with its docket line -- within a
  day, the pairing that agrees on the most tallies and keeps both files'
  order, the same pairing build_site_v2.vote_chronology makes when the counts
  agree -- and the outcome the clerk recorded (MA/MF, AA/AF, Adopted, Failed,
  Veto Sustained ...) is the outcome.

  THEN THE JOURNAL, for a roll call no docket line names: 413 procedural votes
  carry no bill at all. The House Journal (1997 on) and the Senate Journal
  (2003 on) print every roll call's tally with the outcome in the sentence
  after it, and a tally lines up with its roll call in order through the
  year. The thresholds of those votes change with each term's rules -- "Print
  debate" carried by a majority in 2000, amending the House Rules needed two
  thirds in 2015 and 2020 and a majority in 2025, a member was allowed to
  continue by three fifths in 2025-2026 -- so no rule about the question's
  words can know them. The Journal states them.

  THE RULE LAST, and for three things the record cannot do:
    - a roll call neither names;
    - the threshold note and the chart's tick, which need a number;
    - an outcome no rule allows on the record's own tally. Five docket lines:
      HB 435 of 2014 "MA RC 129-156" (the Journal: the report failed), HB 1212
      of 2024 "MF RC 187-181" (the Journal: the motion was adopted), SB 82 of
      2005 (the Journal: "Motion failed."), SB 105 of 2002 and CACR 16 of 1999.
      There the count decides and the disagreement is kept on the record as
      `outcome_conflict`, in words a reader sees.

THE COUNTS ARE NOT TOUCHED. The ballots stay the headline (16 September);
this sets only what the vote decided and what it needed. Where the record's
tally differs from the ballots and the record's outcome follows its own tally
-- SB 331 of 2018, 12-12 on the ballots and 13-11 in the Senate Permanent
Journal, per a Senate Clerk's note -- the outcome is the record's and the
difference is said beside it.

Standard library only; reads the docket and journal files on disk, asks
nobody anything.
"""

import glob
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------- the dockets


def docket_paths(root="."):
    """{term: path}: the fetched docket over the database's, as
    narrate_archive.dockets() chooses, and Docket.txt for the current term."""
    root = Path(root)
    out = {}
    for p in sorted(root.glob("Docket_db_*.txt")) + sorted(root.glob("Docket_[0-9]*.txt")):
        m = re.match(r"^Docket(?:_db)?_(\d{4}-\d{4})\.txt$", p.name)
        if m:
            out[m.group(1)] = p
    cur = root / "Docket.txt"
    if cur.exists():
        with open(cur, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                y = line.split("|", 1)[0].strip()
                if y.isdigit():
                    s = int(y) if int(y) % 2 else int(y) - 1
                    out[f"{s}-{s + 1}"] = cur
                    break
    return out


def norm_bill(b):
    return re.sub(r"\s+", "", (b or "").upper())


# "03/21/2012 02:52:45 PM", the entry stamp, read by hand: strptime over the
# 309,000 rows of nineteen dockets was six seconds of every run.
ENTRY = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2}):(\d{2}) ([AaPp][Mm])\s*$")


def _entry(s):
    m = ENTRY.match(s)
    if not m or not (1 <= int(m.group(4)) <= 12 and int(m.group(5)) < 60
                     and int(m.group(6)) < 62):
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2))).date()
    except ValueError:
        return None


def load_docket(paths, terms=None):
    """{(term, bill, body): [row, ...]} in file order."""
    rows = defaultdict(list)
    for term, p in paths.items():
        if terms and term not in terms:
            continue
        with open(p, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                f = line.rstrip("\n").split("|")
                if len(f) < 6:
                    continue
                rows[(term, norm_bill(f[3]), f[4].strip())].append(
                    {"text": f[5], "entry": _entry(f[2])})
    return rows


# A floor tally with its kind in front, in every punctuation the clerks use:
# "RC 239-114", "RC(207-145)", "RC 16Y-6N", "RC: 16Y-8N", "RC 12y - 12n".
# A committee vote is "(Vote 11-5; RC)" and never has the kind first.
TALLY = re.compile(
    r"\b(?P<kind>RC|DIV|DV)\b\s*[:,(]?\s*\(?\s*(?P<y>\d{1,3})\s*[Yy]?\s*[-–]\s*"
    r"(?P<n>\d{1,3})\s*[Nn]?\s*\)?")
DATE_IN = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def tallies(rows):
    occ = []
    for j, row in enumerate(rows):
        t = row["text"]
        for m in TALLY.finditer(t):
            d = None
            dm = DATE_IN.search(t, m.end())
            if dm:
                try:
                    d = datetime(int(dm.group(3)), int(dm.group(1)), int(dm.group(2))).date()
                except ValueError:
                    d = None
            occ.append({"row": j, "kind": m.group("kind").upper(),
                        "y": int(m.group("y")), "n": int(m.group("n")),
                        "start": m.start(), "end": m.end(),
                        "date": d or row["entry"], "text": t})
    return occ


# ----------------------------------------------------------------- outcomes

# (pattern, carried?). The two-letter codes are case-sensitive: "ma" is a
# word in a name as often as it is a motion.
WORDS = [
    (re.compile(r"\b(MA|AA)\b"), True),
    (re.compile(r"\b(MF|ML|AF|AL)\b"), False),
    (re.compile(r"\bma(?=\s+(?:RC|DIV|VV)\b)"), True),
    (re.compile(r"\b(?:ml|mf)(?=\s+(?:RC|DIV|VV)\b)"), False),
    (re.compile(r"\bVeto\s+Overrid+en\b|\bOverrid+en\b", re.I), True),
    (re.compile(r"\boverturned\b|\bfails\b", re.I), False),
    (re.compile(r"\bVeto\s+Sustained\b|\bSustained\b", re.I), False),
    (re.compile(r"\bNon[- ]?Adopt(?:ed)?\b|\bNot Adopted\b", re.I), None),
    (re.compile(r"\b(?:Adopted|Adpoted)\b", re.I), True),
    (re.compile(r"\bPassed\b", re.I), True),
    (re.compile(r"\bUpheld\b", re.I), True),
    (re.compile(r"\bVeto Override\b", re.I), True),
    (re.compile(r"\b(?:Failed|Lost|Defeated)\b", re.I), False),
]
IMPLIED = re.compile(r"OT3rdg|Ordered to 3rd|KILLED|Refer(?:red)? to Finance|"
                     r"for Interim Study|Re-?Referred to|Laid on the Table|Adopted", re.I)


def _read(rows, o, wrap):
    t, s, e = o["text"], o["start"], o["end"]
    # The database's rows wrap: "OTP/AM failed 3/5" ends one and "RC(186-172)"
    # opens the next.
    if (wrap or s <= 3) and o["row"] > 0:
        prev = rows[o["row"] - 1]["text"]
        t, s, e = prev + " " + t, s + len(prev) + 1, e + len(prev) + 1
    cs = t.rfind(";", 0, s) + 1
    ce = t.find(";", e)
    ce = len(t) if ce < 0 else ce
    # The Senate sometimes writes the outcome as a segment of its own:
    # "RC 12 - 11; AA;".
    if ce < len(t):
        nxt = t[ce + 1:]
        if (re.match(r"\s*(?:MA|MF|AA|AF|AL|ML|Adopted|=+\s*VETO)\b", nxt, re.I)
                and not any(rx.search(t[e:ce]) for rx, _ in WORDS)):
            n2 = nxt.find(";")
            ce = ce + 1 + (len(nxt) if n2 < 0 else n2)
    clause = t[cs:ce]
    rs, re_ = s - cs, e - cs
    cands = []
    for rx, val in WORDS:
        for m in rx.finditer(clause):
            if m.start() >= rs and m.end() <= re_:
                continue
            lo, hi = (m.end(), rs) if m.end() <= rs else (re_, m.start())
            if TALLY.search(clause[lo:hi]):
                continue            # that word belongs to another tally
            dist = rs - m.end() if m.end() <= rs else m.start() - re_
            cands.append((dist, m.start(), m.group(0), val))
    if not cands:
        return None, clause, "none"
    cands.sort()
    best = cands[0]
    if best[3] is None:
        return None, clause, "unreadable"
    if len(cands) > 1 and cands[1][0] == best[0] and cands[1][3] != best[3]:
        return None, clause, "unreadable"
    return best[3], clause, "explicit"


def outcome(rows, o):
    """(carried or None, clause, how) -- how is explicit, implied or none."""
    v = _read(rows, o, False)
    if v[2] == "none" and o["row"] > 0 and o["start"] <= 45:
        w = _read(rows, o, True)
        if w[0] is not None:
            # The previous row's OUTCOME, and this row's own words for the
            # threshold. 2005's SB 228 "Motion: OTP RC(332-4)" sits under a
            # separate voice vote "Susp Rules ... MA 2/3 VV", and borrowing
            # that row's words gave a plain majority vote a two-thirds note.
            return w[0], v[1], w[2]
    if v[2] == "none":
        if o["y"] == 0:
            return False, v[1], "implied"
        if o["n"] == 0:
            return True, v[1], "implied"
        t = o["text"]
        nxt = t[t.find(";", o["end"]) + 1:] if ";" in t[o["end"]:] else ""
        if IMPLIED.search(v[1]) or IMPLIED.search(nxt[:40]):
            return True, v[1], "implied"
    return v


NEXT_ACTION = re.compile(r"OT3rdg|Ordered to third|\bRC\b|\bDIV\b|\bDV\b|\bSen\.|"
                         r"\bRep\.?\s|;|\bHJ\b|\bSJ\b", re.I)


def own_words(clause, y, n):
    """The clause up to this tally, and after it only to the next action:
    "Floor Amendment RC 17Y-7N, AA, OT3rdg, 3/5 nec." names the third
    reading's three fifths, not the amendment's."""
    for m in TALLY.finditer(clause):
        if (int(m.group("y")), int(m.group("n"))) == (y, n):
            after = clause[m.end():]
            b = NEXT_ACTION.search(after)
            return clause[:m.end()] + (after[:b.start()] if b else after)
    return clause


# ------------------------------------------------------------------ pairing


def _assign(cost):
    """Minimum-cost assignment on a square matrix (Hungarian); [(row, col)]."""
    n = len(cost)
    INF = float("inf")
    u, v, p, way = [0] * (n + 1), [0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [INF] * (n + 1), [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return [(p[j] - 1, j - 1) for j in range(1, n + 1) if p[j]]


def _tally_set(r):
    s = {(r["yeas"], r["nays"])}
    if "yeas_stated" in r:
        s.add((r["yeas_stated"], r["nays_stated"]))
    return s


def pair(rs, occ):
    """{id(roll call): occurrence index} for one (term, bill, body).

    Within a day, the assignment that agrees on the most tallies and, among
    those, keeps both files in order. SB 331 of 2018 is why order matters:
    three roll calls, 12-12, 13-11, 12-12, against a docket of 13-11, 13-11,
    12-12 -- the Senate's Permanent Journal corrected the first from 12-12 to
    13-11, and only the pairing in order puts each outcome on its own vote.
    A pair that disagrees on the tally is kept only when the day's counts
    match. What is left is paired on an exact tally anywhere in the term: the
    2003 veto session's docket lines are entered in September, the votes are
    in January -- but only with a line about the same KIND of motion, since
    CACR 19 of 2007's tabling, 17-7 on 14 June, otherwise found a rules
    suspension of 7 June that happened to have the same count.
    """
    got, used = {}, set()
    day_r, day_o = defaultdict(list), defaultdict(list)
    for r in rs:
        day_r[r["date"]].append(r)
    for k, o in enumerate(occ):
        if o["kind"] == "RC" and o["date"]:
            day_o[o["date"].isoformat()].append(k)
    for day, rr in day_r.items():
        ks = day_o.get(day, [])
        if not ks:
            continue
        rr = sorted(rr, key=lambda x: x["number"])
        n = max(len(rr), len(ks))
        cost = [[0] * n for _ in range(n)]
        for i in range(min(n, len(rr))):
            for j in range(min(n, len(ks))):
                o = occ[ks[j]]
                cost[i][j] = (0 if (o["y"], o["n"]) in _tally_set(rr[i]) else 1000) + abs(i - j)
        for i, j in _assign(cost):
            if i < len(rr) and j < len(ks) and (cost[i][j] < 1000 or len(rr) == len(ks)):
                got[id(rr[i])] = ks[j]
                used.add(ks[j])
    for r in sorted(rs, key=lambda x: (x["date"], x["number"])):
        if id(r) in got:
            continue
        try:
            rd = datetime.strptime(r["date"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            rd = None
        q = r.get("question_raw") or ""
        best = None
        for k, o in enumerate(occ):
            if k in used or (o["y"], o["n"]) not in _tally_set(r):
                continue
            if (bool(VETO.search(q)) != bool(VETO.search(o["text"]))
                    or bool(SUSPEND.search(q)) != bool(SUSPEND.search(o["text"]))):
                continue
            dd = abs((o["date"] - rd).days) if (o["date"] and rd) else 99999
            cand = (0 if o["kind"] == "RC" else 1, dd, k)
            if best is None or cand < best:
                best = cand
        if best:
            got[id(r)] = best[2]
            used.add(best[2])
    return got


# --------------------------------------------------------------- the rules

THREE_FIFTHS = re.compile(r"3/5|three.fifths", re.I)
TWO_THIRDS = re.compile(r"2/3|two.thirds", re.I)
VETO = re.compile(r"veto|become law", re.I)
# "SUSP RULES FOR HEARING" is how the House roll-call files of 1999-2005 name
# a suspension; "Rules Suspension" is the later wording. Both begin "susp".
SUSPEND = re.compile(r"\bsusp", re.I)
SUPER = re.compile(r"2/3|two.thirds|3/5|three.fifths|suspen|(?:lacking|by|not getting)\s+(?:the\s+)?(?:necess|requir)", re.I)
AMEND_ONLY = re.compile(
    r"^\s*(?:adopt(?:ion of)?\s+(?:the\s+)?)?(?:floor\s+|committee\s+|comm\s+)?amendment|"
    r"^\s*FLAM\b|^\s*AM\s+\d|floor amendment|committee amendment|"
    r"adoption of (?:the\s+)?(?:floor\s+|committee\s+)?amendment", re.I)
NOT_PASSAGE = re.compile(
    r"inexpedient|\bITL\b|table|interim study|\bRFS\b|recommit|re-?refer|special order|"
    r"indefinite|postpone|reconsider|non-?concur|print|limit debate|ruling|previous question",
    re.I)
PASSAGE = re.compile(
    r"ought to pass|\bOTP|final passage|third reading|3rd reading|\bconcur|conference|"
    r"\bC OF C\b|adopt as amended|adoption\b|\bpassage\b", re.I)


def cacr_passage(bill, question):
    """Is this the question of passing a CACR -- the one Part II, Article 100
    puts at three fifths? Read off the roll call's own question, which every
    roll call has, so the answer is the same with or without a docket line."""
    if not norm_bill(bill).startswith("CACR"):
        return False
    q = question or ""
    if AMEND_ONLY.search(q) or NOT_PASSAGE.search(q):
        return False
    return bool(PASSAGE.search(q))


def two_thirds(y, n):
    v = y + n
    return -(-2 * v // 3), f"two thirds of the {v} members voting"


def threshold(r, words=""):
    """(needed, rule) for a vote that needed more than a majority, else
    (None, None). `words` is the record's own text for this tally.

    Two thirds is of those voting, which is how every docket line and every
    Journal line naming two thirds was decided (and what 2014 HB 1475's says
    in so many words: "2/3 Present and Voting"). Three fifths is of the
    members in office -- the ballots on the roll call, every seated member
    named once -- never of the seats.
    """
    y, n, seated = r["yeas"], r["nays"], r.get("seated")
    q = r.get("question_raw") or r.get("question") or ""
    said3 = bool(THREE_FIFTHS.search(words) or THREE_FIFTHS.search(q))
    said2 = bool(TWO_THIRDS.search(words) or TWO_THIRDS.search(q))
    suspension = bool(SUSPEND.search(q)) and not re.search(r"reconsider", q, re.I)
    if VETO.search(q) or suspension or (said2 and not said3):
        return two_thirds(y, n)
    if seated and (cacr_passage(r.get("bill"), q)
                   or (said3 and norm_bill(r.get("bill")).startswith("CACR"))):
        return -(-3 * seated // 5), f"three fifths of the {seated} members in office"
    return None, None


def plausible(carried, y, n, need, words, question):
    """Could the record's outcome be right on the record's own tally?"""
    if carried:
        return y >= need if need else y > n
    if y <= n:
        return True
    if need:
        return y < need
    return bool(SUPER.search(f"{words} {question or ''}"))


def note(carried, y, n, need, rule):
    if need is None:
        return None
    if not carried and y > n:
        return (f"A majority voted yes, but this needed {need} ({rule}) "
                f"and fell {need - y} short.")
    return f"Needed {need} — {rule}."


# ------------------------------------------------------------- the Journals
#
# For a roll call no docket line names. Every roll call is printed in its
# chamber's Journal with its tally and, in the sentence after it, what became
# of the motion: "YEAS 91 - NAYS 82 ... The motion failed lacking the
# necessary three-fifths vote" (House, 5 March 2026), "Yeas: 13 - Nays: 11.
# Motion adopted." (Senate). The tallies are lined up with the roll calls in
# order through the year and chamber, the way a reader would do it by hand.

JOURNAL_DIRS = {"H": "journals", "S": "journals_senate"}
# The House prints "YEAS 91 - NAYS 82"; the Senate "Yeas: 13 - Nays: 11."
J_TALLY = {"H": re.compile(r"YEAS\s*-?\s*(\d+)\s*-?\s*NAYS\s*-?\s*(\d+)"),
           "S": re.compile(r"Yeas:\s*(\d+)\s*-\s*Nays:\s*(\d+)\.?", re.I)}
J_YES = (r"(?:was|were|is|be)\s+adopted|\badopted\b|prevailed|overridden|overriden|"
         r"allowed to continue|(?<!not )became law|\bpassed\b|was upheld|\bupheld\b|\bcarried\b")
J_NO = (r"\bfailed\b|\bfails\b|sustained|not adopted|did not prevail|\blost\b|defeated|"
        r"did not pass|did not become law|not allowed|lacking")
# Matched on lower-cased text. Every match of J_WORD contains a match of
# J_ANCHOR, which is cheap enough to find first: searching thousands of
# characters of member names with the full pattern was most of a run.
J_WORD = re.compile(f"(?P<no>{J_NO})|(?P<yes>{J_YES})")
J_ANCHOR = re.compile(r"adopted|prevail|overrid|allowed to continue|became law|passed|"
                      r"upheld|carried|fail|sustained|did not|lost|defeated|not allowed|lacking")
J_FURNITURE = re.compile(r"SENATE\s*JOURNAL|^- Page|^\d+$", re.I)
# "The roll call vote below on SB 331 was inadvertently entered in the Daily
# Journal and has been corrected in the Senate Permanent Journal from 12-12 to
# 13-11." -- a Senate Clerk's note, 15 March 2018.
J_CORRECTED = re.compile(
    r"roll\s+call\s+vote\s+below\s+on\s+(?P<bill>[A-Z]{2,4})\s*(?P<num>\d+)\s+was\s+"
    r"inadvertently\s+entered.{0,120}?corrected\s+in\s+the\s+(?:Senate\s+)?Permanent\s+"
    r"Journal\s+from\s+(?P<y0>\d+)\s*-\s*(?P<n0>\d+)\s+to\s+(?P<y1>\d+)\s*-\s*(?P<n1>\d+)",
    re.I | re.S)


def _journal_order(f):
    """A journal's place in the year: "HJ 06 March 5, 2026", "HJ003",
    "SJ 10", "HJ NO 21 11-16-2005" -- the number after the letters, with the
    year taken out first so it is not read as one. A special session's
    journal sorts after the regular ones."""
    b = Path(f).name
    b2 = re.sub(r",?\s*(19|20)\d\d", "", b)
    m = re.search(r"[HS]J[\s_]*(?:NO\s*)?0*(\d+)", b2)
    ss = 1 if re.search(r"\bSS\b|_SS", b) else 0
    return (ss, int(m.group(1)) if m else 999, b)


def journal_files(root, body, year):
    d = Path(root) / JOURNAL_DIRS[body] / str(year)
    if not d.is_dir():
        return []
    # "Verbatim" is the same day's debate printed again word for word, with
    # the same tallies: read twice, every roll call would line up twice.
    fs = [f for f in glob.glob(str(d / "*.txt")) if "erbatim" not in Path(f).name]
    return sorted(fs, key=_journal_order)


def _first_word(low):
    """(carried, match) for the first outcome words in lower-cased text."""
    c = J_ANCHOR.search(low)
    if not c:
        return None, None
    # The longest thing J_WORD puts before its anchor is "were" and a run of
    # white space, so the first match cannot start further back than this.
    m = J_WORD.search(low, max(0, c.start() - 200))
    if not m:
        return None, None
    return (m.group("yes") is not None), m


def journal_tallies(root, body, year):
    """[{"y", "n", "carried", "said"}] in the order the Journal prints them;
    `said` is the sentence the outcome was read from."""
    out = []
    rx = J_TALLY[body]
    for f in journal_files(root, body, year):
        with open(f, encoding="utf-8", errors="replace") as fh:
            t = fh.read()
        ms = list(rx.finditer(t))
        for i, m in enumerate(ms):
            val, said = None, ""
            if body == "H":
                end = ms[i + 1].start() if i + 1 < len(ms) else min(len(t), m.end() + 20000)
                w = t[m.end():end].lower()
                val, km = _first_word(w)
                if km:
                    a = max(w.rfind("\n", 0, km.start()), 0)
                    # To the end of that sentence and no further: 2002's
                    # "and the motion failed. CLERK'S NOTE When less than
                    # two-thirds of the elected membership is present ..." is
                    # a note about a quorum, not the motion's threshold.
                    stop = re.compile(r"\.(?=\s|$)").search(w, km.end(), km.end() + 160)
                    said = re.sub(r"\s+", " ", w[a:stop.end() if stop else km.end() + 160]).strip()
            else:
                lines = [ln.strip() for ln in t[m.end():m.end() + 600].split("\n")]
                lines = [ln for ln in lines if ln and not J_FURNITURE.search(ln)]
                for ln in lines[:3]:
                    v, km = _first_word(ln.lower())
                    if km:
                        val, said = v, ln
                        break
            out.append({"y": int(m.group(1)), "n": int(m.group(2)),
                        "carried": val, "said": said[:240]})
    return out


def journal_corrections(root, year):
    """{(bill, (y, n)): (y, n)}: a Senate Clerk's note that the Permanent
    Journal corrected a roll call's tally."""
    out = {}
    for f in journal_files(root, "S", year):
        with open(f, encoding="utf-8", errors="replace") as fh:
            t = fh.read()
        for m in J_CORRECTED.finditer(t):
            out[(f"{m.group('bill').upper()}{int(m.group('num'))}",
                 (int(m.group("y0")), int(m.group("n0"))))] = (
                int(m.group("y1")), int(m.group("n1")))
    return out


def _align(rs, js):
    """[(i, k)]: the longest run of roll calls and Journal tallies that agree,
    each file kept in its own order."""
    A, B = len(rs), len(js)
    E = [[(js[k]["y"], js[k]["n"]) in _tally_set(rs[i]) for k in range(B)] for i in range(A)]
    dp = [[0] * (B + 1) for _ in range(A + 1)]
    for i in range(A - 1, -1, -1):
        for k in range(B - 1, -1, -1):
            dp[i][k] = dp[i + 1][k + 1] + 1 if E[i][k] else max(dp[i + 1][k], dp[i][k + 1])
    i = k = 0
    pairs = []
    while i < A and k < B:
        if E[i][k] and dp[i][k] == dp[i + 1][k + 1] + 1:
            pairs.append((i, k))
            i += 1
            k += 1
        elif dp[i + 1][k] >= dp[i][k + 1]:
            i += 1
        else:
            k += 1
    return pairs


def journal_links(rolls, want, root="."):
    """{id(roll call): Journal tally} for the roll calls in `want`.

    Aligned per year and chamber over EVERY roll call of that year, since the
    order is the evidence, then any roll call left over is matched on a tally
    that occurs exactly once on each side."""
    by_yb = defaultdict(list)
    for r in rolls:
        by_yb[(str(r["year"]), r["body"])].append(r)
    need = {(str(r["year"]), r["body"]) for r in rolls if id(r) in want}
    got = {}
    for yb in sorted(need):
        if yb[1] not in JOURNAL_DIRS:
            continue
        js = journal_tallies(root, yb[1], yb[0])
        if not js:
            continue
        rs = sorted(by_yb[yb], key=lambda x: x["number"])
        used = set()
        for i, k in _align(rs, js):
            got[id(rs[i])] = js[k]
            used.add(k)
        jc = Counter((j["y"], j["n"]) for j in js)
        rc = Counter(t for r in rs for t in _tally_set(r))
        for r in rs:
            if id(r) in got:
                continue
            for t in _tally_set(r):
                if jc[t] == 1 and rc[t] == 1:
                    k = next(x for x, j in enumerate(js) if (j["y"], j["n"]) == t)
                    if k not in used:
                        got[id(r)] = js[k]
                        used.add(k)
                        break
    return {k: v for k, v in got.items() if k in want}


def journal_decides(j, r, need, rule):
    """(carried, need, rule, note) from a Journal line, or None where its
    outcome is not one the tally allows. An adoption needs more yeas than
    nays; a failure over a majority needs the sentence to say why.

    `need` and `rule` are the rule's, and are kept where the Journal's
    outcome agrees with them -- a rules suspension is two thirds whether or
    not the sentence repeats it. Otherwise the number comes from the Journal
    or not at all: two thirds where it names two thirds, which is of those
    voting; three fifths it names without saying of what, so no number."""
    y, n = r["yeas"], r["nays"]
    carried, said = j.get("carried"), j.get("said") or ""
    if carried is None:
        return None
    # A tally lined up with the wrong vote: the same count on a veto the
    # question does not mention, or the other way round.
    if bool(VETO.search(said)) != bool(VETO.search(r.get("question_raw") or "")):
        return None
    if carried and y <= n:
        return None
    three, two = bool(THREE_FIFTHS.search(said)), bool(TWO_THIRDS.search(said))
    if not carried and y > n and not (three or two or re.search(r"lacking", said, re.I)):
        return None
    chamber = "House" if r.get("body") == "H" else "Senate"
    if need is not None and (y >= need) == carried:
        return carried, need, rule, note(carried, y, n, need, rule)
    if two and not three:
        need, rule = two_thirds(y, n)
        if (y >= need) != carried:
            return None
        return carried, need, rule, note(carried, y, n, need, rule)
    if three:
        # The Journal names three fifths without saying of what, and on a
        # procedural question the House Rules of the day decide that. The
        # site says what the Journal says and invents no number.
        how = "carried" if carried else "failed"
        lead = "A majority voted yes, but " if (not carried and y > n) else ""
        return carried, None, None, (
            f"{lead}{'t' if lead else 'T'}he {chamber} Journal records that "
            f"this needed three fifths, and it {how}.")
    if not carried and y > n:
        return carried, None, None, (
            f"A majority voted yes, but the {chamber} Journal records that the "
            f"motion failed, short of the larger majority it needed.")
    return carried, None, None, None


# ------------------------------------------------------------------ apply


def apply(rolls, root=".", paths=None):
    """Set passed, threshold_*, outcome_source and outcome_conflict on every
    roll call, in place. Returns a count of each outcome_source."""
    root = Path(root)
    paths = paths if paths is not None else docket_paths(root)
    terms = {term_of(r["year"]) for r in rolls}
    dk = load_docket(paths, terms)
    groups = defaultdict(list)
    for r in rolls:
        b = norm_bill(r.get("bill"))
        if b:
            groups[(term_of(r["year"]), b, r["body"])].append(r)
    link = {}
    for key, rs in groups.items():
        rows = dk.get(key)
        if not rows:
            continue
        occ = tallies(rows)
        for rid, k in pair(rs, occ).items():
            link[rid] = (rows, occ[k])
    # The Journal, for the roll calls no docket line names.
    jl = journal_links(rolls, {id(r) for r in rolls if id(r) not in link}, root)
    stats = Counter()
    for r in rolls:
        y, n = r["yeas"], r["nays"]
        r["outcome_conflict"] = None
        r.pop("threshold_unknown", None)
        found = link.get(id(r))
        words, carried, how = "", None, "none"
        if found:
            rows, o = found
            carried, clause, how = outcome(rows, o)
            words = own_words(clause, o["y"], o["n"])
        need, rule = threshold(r, words)
        by_count = y >= need if need else y > n
        journal_note = None
        if carried is not None:
            dneed, _ = threshold(dict(r, yeas=o["y"], nays=o["n"]), words)
            if plausible(carried, o["y"], o["n"], dneed, words, r.get("question_raw")):
                r["passed"] = carried
                r["outcome_source"] = "docket" if how == "explicit" else "docket, implied"
                if carried != by_count:
                    r["outcome_conflict"] = (
                        f"The General Court's docket records this vote as {o['y']}–{o['n']} and "
                        f"the motion {'adopted' if carried else 'failed'}; the members' "
                        f"votes on this roll call add up to {y}–{n}.")
            elif carried == by_count:
                # a slip in the docket's tally ("RC 1Y-7N" for 17-7), not in
                # its outcome: nothing to disagree about
                r["passed"] = carried
                r["outcome_source"] = "docket"
            else:
                r["passed"] = by_count
                r["outcome_source"] = "count"
                r["outcome_conflict"] = (
                    f"The General Court's docket records this motion as "
                    f"{'adopted' if carried else 'failed'} on {o['y']}–{o['n']}, "
                    f"which that count does not allow; the outcome shown here "
                    f"follows the count.")
        elif id(r) in jl:
            said = journal_decides(jl[id(r)], r, need, rule)
            if said:
                r["passed"], need, rule, journal_note = said
                r["outcome_source"] = "journal"
                if need is None and journal_note:
                    # More than a majority, of a count the record does not
                    # give: the chart draws no mark rather than a wrong one.
                    r["threshold_unknown"] = True
            else:
                r["passed"] = by_count
                r["outcome_source"] = "rule"
        else:
            r["passed"] = by_count
            r["outcome_source"] = "rule"
        r["threshold_needed"], r["threshold_rule"] = need, rule
        r["threshold_note"] = journal_note or note(r["passed"], y, n, need, rule)
        stats[r["outcome_source"]] += 1
    _clerks_corrections(rolls, root, stats)
    return dict(stats)


def _clerks_corrections(rolls, root, stats):
    """Where the Senate Clerk has noted that the Permanent Journal corrected a
    roll call's tally, the outcome is the corrected one and the note says so.

    SB 331 of 2018: the General Court's roll-call files carry 12-12, and the
    docket and the Senate Journal (SJ 8) carry 13-11 with the motion adopted.
    The ballots stay what is shown -- they are the record of who voted which
    way that the site has -- and the reader is told the Journal corrected
    the count."""
    years = {str(r["year"]) for r in rolls
             if r["body"] == "S" and r.get("outcome_conflict")}
    fixes = {}
    for yr in sorted(years):
        for (bill, was), now in journal_corrections(root, yr).items():
            fixes[(yr, bill, was)] = now
    if not fixes:
        return
    for r in rolls:
        # Only the roll call whose record already disagrees with its ballots:
        # SB 331 had two 12-12 votes that day, and the second really was 12-12.
        if r["body"] != "S" or not r.get("outcome_conflict"):
            continue
        now = fixes.get((str(r["year"]), norm_bill(r.get("bill")), (r["yeas"], r["nays"])))
        if not now:
            continue
        carried = now[0] > now[1]
        stats[r["outcome_source"]] -= 1
        r["passed"] = carried
        r["outcome_source"] = "journal"
        stats["journal"] += 1
        r["threshold_note"] = note(carried, r["yeas"], r["nays"],
                                   r["threshold_needed"], r["threshold_rule"])
        r["outcome_conflict"] = (
            f"A Senate Clerk's note in the Senate Journal says this roll call was "
            f"corrected in the Permanent Journal from {r['yeas']}–{r['nays']} "
            f"to {now[0]}–{now[1]}, and the motion "
            f"{'was adopted' if carried else 'failed'}. The members' votes shown "
            f"here are the General Court's roll-call file, which still adds up "
            f"to {r['yeas']}–{r['nays']}.")


def term_of(year):
    y = int(str(year)[:4])
    s = y if y % 2 else y - 1
    return f"{s}-{s + 1}"
