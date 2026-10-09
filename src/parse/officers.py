#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.1
"""
Who held the chair's offices, and on which days, from the record on disk.

    python3 src/parse/officers.py                    # every tenure found, with its source
    python3 src/parse/officers.py --date 2025-05-08  # who held what that day, and who holds it now

THE OFFICES. The Speaker of the House and the President of the Senate, whom
each chamber elects; the Deputy Speaker and the Speaker Pro Tempore, whom the
Speaker appoints. The person, 9 October 2026: "Sharon Carson is the Senate
President and should also have some indicator similar to how you did the
Speaker of the House", and "For why Steve Smith shows up as speaker/presiding
sometimes, he is the deputy speaker and sometimes fills in for Sherman
Packard if he has other business, as does Jim Kofalt occasionally as speaker
pro temp."

WHY IT IS NEEDED. The House Journal heads whoever is in the chair "Speaker":
"Speaker Steven Smith:" 251 times in 2025-2026 and "Speaker Kofalt:" 59,
beside "Speaker Packard:" 428 -- and its own notes say "(Rep. Steven Smith in
the Chair)". The session pages printed the heading as it stood, so the
Deputy Speaker was "Speaker Steven Smith" on 33 sittings of 2021-2026, and
Reps. Kofalt, Rice and Shurtleff "Speaker" on six: 35 sittings in all.

WHERE EACH COMES FROM, and nothing here is inferred from who presided:

  The Speaker      the House Journal's declaration of the election -- "The
                   Chair declared Rep. Sherman Packard the duly elected
                   Speaker of the House for the 2025-2026 biennium" (HJ 1,
                   4 December 2024) -- from 1996 on.
  The President    the Senate Journal's -- "Senator Sharon M. Carson was
  of the Senate    elected President of the Senate" (SJ 1, 4 December 2024)
                   -- and the Senate's message the House Journal prints that
                   day ("President of the Senate: Senator Sharon M. Carson").
  The Deputy       the House Journal naming them in it -- "Deputy Speaker
  Speaker and the  Steven Smith:" (HJ 14, 8 May 2025), "(Deputy Speaker
  Speaker Pro      Weyler in the Chair)", "called to order by Deputy Speaker
  Tempore          Steven Smith" (HJ 7, 7 March 2024) -- and the House
                   Calendar's notices: "Rep. Steve Smith of Charlestown has
                   been reappointed as Deputy Speaker. Rep. Laurie Sanborn of
                   Bedford has been appointed Speaker Pro Tempore" (HC 2,
                   9 December 2022), "sponsored by Speaker Packard, Speaker
                   Pro Tem Kofalt, and Senate President Carson" (HC 22,
                   29 May 2026).

HOW LONG AN OFFICE IS HELD. An elected officer holds it from the day of the
election until the next election of that office, and never past the term it
was won in: a term whose election is not on disk (the House's of December
2002) has no Speaker here rather than the last one carried on. An appointed
officer named in one term, and the only one named in that office that term,
holds it for the term: the Speaker appoints the leadership at its start, as
the notice of 9 December 2022 shows. Where the record names two people in
one appointed office in one term, it does not say when it changed hands, and
each holds it here only on the days the record names them in it. 2025-2026
is that case: "Fred Doucette, who served as Speaker Pro Tem earlier this
term" (HC 28, 31 July 2026) and "Speaker Pro Tem Kofalt" (HC 22, 29 May
2026). A person's entry in corrections/officials.json (legislative_officers)
can give the days the record does not; nothing writes that file.

WHO HOLDS AN OFFICE NOW, for a member's own page: the elected officer whose
tenure covers the day, and for an appointed office the member named in it
latest in the day's term, so Rep. Kofalt is the Speaker Pro Tempore on the
strength of the notice of 29 May 2026.

Nothing here asks the network or writes anything.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime as _dt
import json
import re

import journal_days as JD
import proceedings as P

HOUSE = Path("journals")
SENATE = Path("journals_senate")
CALENDARS = Path("calendars")
HAND = Path("corrections/officials.json")

# The offices, the title a person is given in the chair, and how the page
# names the office. The House's Speaker Pro Tempore is written "Speaker Pro
# Tem" as often as not; it is one office.
OFFICE = {("H", "Speaker"): "Speaker of the House",
          ("H", "Deputy Speaker"): "Deputy Speaker of the House",
          ("H", "Speaker Pro Tempore"): "Speaker Pro Tempore of the House",
          ("S", "President"): "President of the Senate"}
ELECTED = (("H", "Speaker"), ("S", "President"))
APPOINTED = (("H", "Deputy Speaker"), ("H", "Speaker Pro Tempore"))
# When two offices are named for one person on one day, the higher first.
RANK = {"Speaker": 0, "President": 0, "Deputy Speaker": 1, "Speaker Pro Tempore": 2}

# A name as the record writes one: capitalised words, none of them a title
# or the word that ends the phrase. "President of the Senate: Senator Sharon
# M. Carson Clerk of the Senate" is Sharon M. Carson.
_DAYS = ("Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|"
         "March|April|May|June|July|August|September|October|November|December")
_STOP = (r"(?!(?:Clerk|Secretary|Senator|Sen|Rep|Representative|Speaker|President|"
         r"Deputy|Assistant|Majority|Minority|The|Chair|Pro|Tem|Tempore|" + _DAYS + r")\b)")
# A word of a name is an initial ("M."), or a capitalised word with a small
# letter in it -- "O'Brien", "McGough", "D.Whalley" -- and never ending in a
# full stop: "called to order by Deputy Speaker Steven Smith. Prayer was
# offered" names Steven Smith, and a calendar's "Deputy Speaker NOTICE" and
# "Deputy Speaker HOUSE DEADLINES" name nobody.
_WORD = _STOP + (r"(?:[A-Z]\.(?:[A-Z][A-Za-z'’\-]*[a-z][A-Za-z'’\-]*)?"
                 r"|[A-Z](?=[A-Za-z'’\-]*[a-z])[A-Za-z'’\-]*)")
NAME = _WORD + r"(?:\s+" + _WORD + r"){0,3}"
LINE_NAME = _WORD + r"(?:[ \t]+" + _WORD + r"){0,3}"
_APPT = r"(?P<t>Deputy\s+Speaker|Speaker\s+Pro\s+Tem(?:pore)?)\b"
_REP = r"(?:Rep\.|Representative)"

# THE SPEAKER'S ELECTION, as the House Journal declares it. Case-sensitive,
# because a name is capitalised and "declared that nominations" is not one.
H_SPEAKER = [
    # "The Chair declared Rep. Sherman Packard the duly elected Speaker of the
    # House" (2024); "declared Rep. Sytek duly elected Speaker" (1998).
    re.compile(r"declared\s+(?:" + _REP + r"\s+)?(?P<n>" + NAME + r")\s+(?:the\s+)?"
               r"duly[-\s]+elected\s+Speaker\b(?!\s+Pro)"),
    # "Rep. William L. O'Brien was declared the duly-elected Speaker" (2010);
    # "Rep. Donna P. Sytek is the duly-elected Speaker" (1996).
    re.compile(_REP + r"\s+(?P<n>" + NAME + r")\s+(?:is|was)\s+(?:declared\s+)?"
               r"(?:the\s+)?duly[-\s]+elected\s+Speaker\b(?!\s+Pro)"),
    # "Representative Dick Hinch and he was declared the duly-elected Speaker"
    # (2 December 2020).
    re.compile(_REP + r"\s+(?P<n>" + NAME + r")\s+and\s+(?:he|she)\s+was\s+declared\s+"
               r"the\s+duly[-\s]+elected\s+Speaker\b(?!\s+Pro)"),
]
# 4 December 2002 declares nobody: the House voted "that Gene G. Chandler be
# unanimously elected as Speaker of the House", and then "The Sergeant-at-Arms
# escorted Speaker Chandler to the rostrum". Every organization day since
# says the same of the Speaker it has just elected, and only a day the
# Speaker was elected on is read for it (H_ELECTION).
H_ROSTRUM = re.compile(r"escorted\s+Speaker\s+(?P<n>" + NAME + r")\s+to\s+the\s+rostrum")
H_ELECTION = re.compile(r"nominations\s+for\s+Speaker\b(?!\s+Pro)")
# THE SENATE'S. "Senator Sharon M. Carson was elected President of the
# Senate" (2024), "Senator Theodore L. Gatsas is elected the President of
# the Senate" (9 September 2005), "The Honorable Sylvia B. Larsen was
# elected President of the New Hampshire Senate" (2008).
S_PRESIDENT = re.compile(
    r"(?:Senator|Sen\.|The\s+Honorable)\s+(?P<n>" + NAME + r")\s+(?:is|was)\s+"
    r"(?:duly\s+)?elected\s+(?:as\s+)?(?:the\s+)?"
    r"(?:President\s+of\s+the\s+(?:New\s+Hampshire\s+)?Senate|Senate\s+President)\b")
# The Senate's message the House Journal prints at the organization:
# "President of the Senate: Senator Sharon M. Carson" (2024), "President of
# the Senate, Senator Chuck Morse and Clerk of the Senate" (2014).
S_MESSAGE = re.compile(
    r"President\s+of\s+the\s+Senate\s*[:,]\s*(?:Senator|Sen\.)\s+(?P<n>" + NAME + r")")
# THE APPOINTED OFFICES, where the House Journal names a person in one: a
# speech's heading ("Deputy Speaker Steven Smith: ..."), a note of who is in
# the chair, and who called the House to order.
H_NAMED = [
    re.compile(r"^[ \t]*" + _APPT + r"[ \t]+(?P<n>" + LINE_NAME + r")[ \t]*:", re.M),
    re.compile(r"\(\s*" + _APPT + r"\s+(?P<n>" + NAME + r")\s+in\s+the\s+Chair\s*\)"),
    re.compile(r"called\s+to\s+order\s+by\s+" + _APPT + r"\s+(?P<n>" + NAME + r")"),
]
# And the House Calendar's notices. "Rep. Steve Smith of Charlestown has
# been reappointed as Deputy Speaker" (HC 2, 9 December 2022); and a title
# before a name that a comma, "of", "and" or a full stop ends -- "Speaker Pro
# Tem Kofalt, and Senate President Carson" (HC 22, 29 May 2026), "Deputy
# Speaker Michael Whalley of Bow" (HC 3, 14 December 2000) -- and never a
# former one's ("former Deputy Speaker Linda Foster's family"), an assistant
# one's ("Assistant Deputy Speaker Keith Herman"), or a list that gives the
# title after the name: 1997's "Donnalee Lozeau Deputy Speaker Channing T.
# Brown Speaker Pro Tempore" made Rep. Brown the Deputy Speaker, read the
# other way round.
C_NAMED = [
    re.compile(_REP + r"\s+(?P<n>" + NAME + r")\s+of\s+[A-Z][A-Za-z.'’\- ]{1,30}?\s+"
               r"has\s+been\s+(?:re)?appointed\s+(?:as\s+)?(?:the\s+)?" + _APPT),
    re.compile(r"(?<![Ff]ormer )(?<!Assistant )\b" + _APPT + r"\s+(?P<n>" + NAME + r")"
               r"(?=\s*(?:,|\.|;|\)|\bof\b|\band\b))(?!['’]s\b)"),
]
# "our former colleague Fred Doucette, who served as Speaker Pro Tem earlier
# this term" (HC 28, 31 July 2026): an officer of the term, on no day it names.
C_EARLIER = re.compile(r"(?P<n>" + NAME + r"),\s+who\s+served\s+as\s+(?:the\s+)?" + _APPT
                       + r"\s+earlier\s+this\s+term")

MONTHS = JD.MONTHS
_MON = "|".join(m.upper() for m in MONTHS)
# A Senate Journal's running head ("SENATEJOURNAL4DECEMBER2024", "SENATE
# JOURNAL 29 JUNE 2005") and its datelines ("September 9, 2005"): the last
# one above a sentence is its day. An organization day opens with neither
# "The Senate met" nor a heading journal_days reads.
S_HEAD = re.compile(r"SENATE\s*JOURNAL\s*(?P<day>\d{1,2})\s*(?P<mon>" + _MON + r")\s*"
                    r"(?P<yr>\d{4})")
S_LINE = re.compile(r"^[ \t]*(?:SENATE[ \t]+)?(?P<mon>" + "|".join(
    m.capitalize() for m in MONTHS) + r")[ \t]+(?P<day>\d{1,2}),?[ \t]*(?P<yr>\d{4})[ \t]*$",
    re.M)
# The House Calendar's masthead: "Concord,N.H.  Friday,May29,2026".
C_DATE = re.compile(r"Concord\s*,?\s*N\.?\s*H\.?\s*[,.]?\s+(?:[A-Za-z]+day)\s*,?\s*"
                    r"(?P<mon>[A-Za-z]+)\s*(?P<day>\d{1,2})\s*,?\s*(?P<yr>\d{4})", re.I)


def _iso(m):
    mo = MONTHS.get(m.group("mon").lower())
    if not mo:
        return ""
    try:
        return _dt.date(int(m.group("yr")), mo, int(m.group("day"))).isoformat()
    except ValueError:
        return ""


def _clean_name(n):
    return re.sub(r"\s+", " ", n or "").strip().strip(",.;:").replace("’", "'")


def surname(name):
    """"steven smith" -> "smith"; "D.Whalley" -> "whalley"; "O'Brien" ->
    "o'brien". The last word, which for these offices is the surname."""
    words = _clean_name(name).split()
    if not words:
        return ""
    last = words[-1]
    if "." in last.rstrip("."):
        last = last.rstrip(".").split(".")[-1]
    return re.sub(r"['’]s$", "", last).strip(".").lower()


def given(name):
    """The first word of the name that is not an initial, or ""."""
    words = _clean_name(name).split()[:-1]
    for w in words:
        if len(w.rstrip(".")) > 1:
            return w.lower()
    return ""


def same_person(a, b):
    """The same officer, by the surname and, where both give one, the given
    name's first letter: "Steve Smith" and "Steven Smith", "Jim Kofalt" and
    "Kofalt", and the journal's one "Speaker Stevn Smith". chair_label asks
    it among the handful of officers of one chamber on one day, where a
    surname is enough to tell them apart; resolve() names a member by it only
    where exactly one member of that chamber that term answers."""
    if not surname(a) or surname(a) != surname(b):
        return False
    ga, gb = given(a), given(b)
    return not ga or not gb or ga[0] == gb[0]


def term_of(iso):
    """The term a day belongs to: Organization Day is the next term's."""
    return P.vote_term(iso[:4], iso) if iso else ""


def term_start(term):
    """The day a term begins here: Organization Day of the even year before."""
    return P.organization_day(int(term[:4]) - 1).isoformat()


def term_end(term):
    """The first day of the next term."""
    return P.organization_day(int(term[5:])).isoformat()


def _mention(body, title, name, iso, kind, path, quote, book):
    """`book` is whose record it was read from: "H" the House Journal, "S"
    the Senate Journal, "C" the House Calendar."""
    return {"body": body, "title": title, "name": _clean_name(name), "date": iso,
            "kind": kind, "cite": str(path).replace("\\", "/"), "book": book,
            "quote": re.sub(r"\s+", " ", quote).strip()[:240]}


def _title(t):
    return "Deputy Speaker" if t.lower().startswith("deputy") else "Speaker Pro Tempore"


# A sitting's date under its "HOUSE JOURNAL No. 1" heading, with or without
# its weekday: an organization day of 1996 and 2000 prints "December 4, 1996"
# and "(December 6, 2000)" alone, which journal_days.DATELINE, asking for the
# weekday, does not read -- and those two are where Speakers Sytek and
# Chandler were elected.
H_DATE = re.compile(
    r"^[ \t]*\(?(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+)?"
    r"(?P<mon>January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(?P<day>\d{1,2}),?\s*(?P<yr>\d{4})\)?[ \t]*$", re.M)


def house_blocks(text):
    """[(iso_date, block)] -- journal_days.day_blocks, reading a dateline
    with no weekday too. A continuation is the previous day's and is left
    out, as there."""
    out = []
    heads = list(JD.DAY_HEADER.finditer(text))
    for i, m in enumerate(heads):
        if m.group("cont"):
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[m.end():end]
        d = H_DATE.search(block[:1200])
        if d and _iso(d):
            out.append((_iso(d), block))
    return out


def house_mentions(root=HOUSE):
    """Every election of a Speaker, every appointed officer the House Journal
    names, and every President of the Senate its message names, each dated
    by the sitting it is printed under (house_blocks)."""
    out = []
    for f in sorted(Path(root).glob("*/*.txt")):
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not re.search(r"Speaker|President of the Senate", raw):
            continue
        for iso, block in house_blocks(JD.clean(raw, lines=True)):
            for rx in H_SPEAKER + ([H_ROSTRUM] if H_ELECTION.search(block) else []):
                for m in rx.finditer(block):
                    out.append(_mention("H", "Speaker", m.group("n"), iso, "elected", f,
                                        m.group(0), "H"))
            for rx in H_NAMED:
                for m in rx.finditer(block):
                    out.append(_mention("H", _title(m.group("t")), m.group("n"), iso,
                                        "named", f, m.group(0), "H"))
            for m in S_MESSAGE.finditer(block):
                out.append(_mention("S", "President", m.group("n"), iso, "elected", f,
                                    m.group(0), "H"))
    return out


def senate_mentions(root=SENATE):
    """Every election of a President in the Senate Journal, dated by the
    running head or dateline above it, or by the file's name."""
    out = []
    for f in sorted(Path(root).glob("*/*.txt")):
        if "erbatim" in f.name:
            continue
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "elected" not in raw:
            continue
        raw = JD.HYPHEN_WRAP.sub(r"\1\2", raw.replace("\r\n", "\n").replace("\r", "\n"))
        marks = sorted([(m.start(), _iso(m)) for m in S_HEAD.finditer(raw)]
                       + [(m.start(), _iso(m)) for m in S_LINE.finditer(raw)])
        named = JD.S_DATE.search(f.name)
        fallback = JD._iso(named) if named else ""
        for m in S_PRESIDENT.finditer(raw):
            above = [d for p, d in marks if p < m.start() and d]
            iso = above[-1] if above else fallback
            if iso:
                out.append(_mention("S", "President", m.group("n"), iso, "elected", f,
                                    m.group(0), "S"))
    return out


def calendar_mentions(root=CALENDARS):
    """The House Calendar's notices naming an appointed officer, dated by the
    calendar's masthead."""
    out = []
    for f in sorted(Path(root).glob("*/HC*.txt")):
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not re.search(r"Deputy\s+Speaker|Speaker\s+Pro\s+Tem", raw):
            continue
        d = C_DATE.search(raw[:6000])
        iso = _iso(d) if d else ""
        if not iso:
            continue
        text = re.sub(r"\s+", " ", JD.HYPHEN_WRAP.sub(r"\1\2", raw.replace("\r\n", "\n")))
        seen = set()
        for rx in C_NAMED:
            for m in rx.finditer(text):
                if (m.start("n"), m.group("t")) in seen:
                    continue
                seen.add((m.start("n"), m.group("t")))
                out.append(_mention("H", _title(m.group("t")), m.group("n"), iso, "named",
                                    f, m.group(0), "C"))
        for m in C_EARLIER.finditer(text):
            out.append(_mention("H", _title(m.group("t")), m.group("n"), iso, "earlier",
                                f, m.group(0), "C"))
    return out


def hand_entries(path=HAND):
    """corrections/officials.json's legislative_officers: what a person
    states that the record on disk does not, each with its source. Read,
    never written. An entry that does not hold together is reported and
    left out rather than half applied."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], []
    block = doc.get("legislative_officers") or {}
    rows = block.get("entries") if isinstance(block, dict) else block
    good, bad = [], []
    for e in rows or []:
        if not isinstance(e, dict):
            bad.append((e, "not an object"))
            continue
        body, title = (e.get("chamber") or "")[:1].upper(), e.get("title") or ""
        start, stop = e.get("from") or "", e.get("to") or ""
        why = ("an office this file does not know" if (body, title) not in OFFICE else
               "no name" if not e.get("name") else
               "no source" if not e.get("source") else
               "no day it began, as YYYY-MM-DD" if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start)
               else "an end that is not YYYY-MM-DD" if stop and not re.fullmatch(
                   r"\d{4}-\d{2}-\d{2}", stop) else "")
        if why:
            bad.append((e, why))
            continue
        good.append({"body": body, "title": title, "office": OFFICE[(body, title)],
                     "name": _clean_name(e["name"]), "member_id": str(e.get("member_id") or ""),
                     "from": start, "to": stop or term_end(term_of(start)),
                     "kind": "hand", "source": e["source"]})
    return good, bad


def _source(m):
    return f'{m["cite"]}, {m["date"]}: "{m["quote"]}"'


def tenures(mentions, hand=()):
    """[{body, title, office, name, from, to, kind, source}], `to` the first
    day the office is no longer theirs. HOW LONG AN OFFICE IS HELD, above."""
    out = []
    for body, title in ELECTED:
        # The chamber's own journal first where both print the day: the
        # Senate's election before the message the House was sent of it.
        ms = sorted((m for m in mentions if (m["body"], m["title"]) == (body, title)
                     and m["kind"] == "elected"),
                    key=lambda m: (m["date"], m["book"] != body))
        runs = []
        for m in ms:
            # One election read twice -- the Senate's own journal and its
            # message in the House's, or two sentences of one day.
            if runs and same_person(runs[-1]["name"], m["name"]) and (
                    term_of(runs[-1]["date"]) == term_of(m["date"])):
                if len(m["name"]) > len(runs[-1]["name"]) and m["date"] == runs[-1]["date"]:
                    runs[-1] = {**runs[-1], "name": m["name"]}
                continue
            runs.append(m)
        for i, m in enumerate(runs):
            end = term_end(term_of(m["date"]))
            nxt = runs[i + 1]["date"] if i + 1 < len(runs) else ""
            out.append({"body": body, "title": title, "office": OFFICE[(body, title)],
                        "name": m["name"], "from": m["date"],
                        "to": min(end, nxt) if nxt else end, "kind": "elected",
                        "source": _source(m)})
    for body, title in APPOINTED:
        by_term = {}
        for m in mentions:
            if (m["body"], m["title"]) == (body, title):
                by_term.setdefault(term_of(m["date"]), []).append(m)
        for term, ms in sorted(by_term.items()):
            people = []
            for m in sorted(ms, key=lambda m: m["date"]):
                if not any(same_person(p, m["name"]) for p in people):
                    people.append(m["name"])
            named = sorted((m for m in ms if m["kind"] == "named"), key=lambda m: m["date"])
            if len(people) == 1 and named:
                # The form the record uses most, then the fullest.
                forms = [m["name"] for m in ms]
                full = max(forms, key=lambda n: (forms.count(n), len(n.split()), len(n), n))
                out.append({"body": body, "title": title, "office": OFFICE[(body, title)],
                            "name": full, "from": term_start(term), "to": term_end(term),
                            "kind": "term", "source": _source(named[0])})
                continue
            for m in named:
                day = _dt.date.fromisoformat(m["date"])
                out.append({"body": body, "title": title, "office": OFFICE[(body, title)],
                            "name": m["name"], "from": m["date"],
                            "to": (day + _dt.timedelta(days=1)).isoformat(),
                            "kind": "day", "source": _source(m)})
    out += list(hand)
    return sorted(out, key=lambda t: (t["body"], RANK[t["title"]], t["from"], t["name"]))


_CACHE = {}


def load(house=HOUSE, senate=SENATE, calendars=CALENDARS, hand=HAND):
    """(tenures, mentions, rejected hand entries), read once per process."""
    key = (str(house), str(senate), str(calendars), str(hand))
    if key not in _CACHE:
        ms = house_mentions(house) + senate_mentions(senate) + calendar_mentions(calendars)
        good, bad = hand_entries(hand)
        _CACHE[key] = (tenures(ms, good), ms, bad)
    return _CACHE[key]


def on(tens, body, iso):
    """The tenures of `body` that cover the day."""
    return [t for t in tens if t["body"] == body and t["from"] <= iso < t["to"]]


def holders(tens, mentions, iso):
    """{(body, title): tenure-like} -- who holds each office on the day, as a
    member's own page names it (WHO HOLDS AN OFFICE NOW, above)."""
    out = {}
    for t in tens:
        if t["from"] <= iso < t["to"] and (t["body"], t["title"]) not in out:
            out[(t["body"], t["title"])] = t
    term = term_of(iso)
    for body, title in APPOINTED:
        if any(t["kind"] == "hand" and (t["body"], t["title"]) == (body, title)
               and t["from"] <= iso < t["to"] for t in tens):
            continue
        named = [m for m in mentions if (m["body"], m["title"]) == (body, title)
                 and m["kind"] == "named" and m["date"] <= iso and term_of(m["date"]) == term]
        if named:
            m = max(named, key=lambda m: m["date"])
            full = next((t["name"] for t in tens if (t["body"], t["title"]) == (body, title)
                         and same_person(t["name"], m["name"]) and term_of(t["from"]) == term),
                        m["name"])
            out[(body, title)] = {"body": body, "title": title, "office": OFFICE[(body, title)],
                                  "name": full, "from": m["date"], "to": term_end(term),
                                  "kind": "named", "source": _source(m)}
    return out


CHAIR = re.compile(r"^Speaker\s+(?!Pro\s+Tem)(?P<n>\S.*)$")


def chair_label(who, iso, tens):
    """The heading of a turn the House Journal gives the chair, as the page
    prints it on the day `iso`.

    The journal heads whoever is in the chair "Speaker": "Speaker Packard:",
    and on the same pages "Speaker Steven Smith:" and "Speaker Kofalt:". The
    Speaker's heading stands. Anyone else in the chair is given the office
    the record says they held that day -- "Deputy Speaker Steven Smith" --
    and otherwise is a member in the chair, as the journal's own note puts
    them: "(Rep. Kofalt in the Chair)" is "Rep. Kofalt, in the chair". On a
    day the record names no Speaker for, the heading is left as printed,
    because there is then nothing to tell the Speaker from anyone else by.
    Any heading that is not "Speaker <name>" is returned as it came."""
    m = CHAIR.match(who or "")
    if not m:
        return who
    name = m.group("n").strip()
    here = on(tens, "H", iso)
    if not any(t["title"] == "Speaker" for t in here):
        return who
    hit = sorted((t for t in here if same_person(t["name"], name)),
                 key=lambda t: RANK[t["title"]])
    if hit and hit[0]["title"] == "Speaker":
        return who
    if hit:
        return f'{hit[0]["title"]} {name}'
    return f"Rep. {name}, in the chair"


def ballot_people(votes_by_member):
    """{(body, term): {member_id: "Last, First"}} -- who sat in each chamber
    in each term, from their ballots, to name an officer the record names."""
    out = {}
    for rows in votes_by_member.values():
        for v in rows:
            t = P.vote_term(str(v.get("year") or ""), v.get("date"))
            mid, nm = str(v.get("member_id") or ""), v.get("name") or ""
            if t and mid and nm and not nm.lower().startswith(("member #", "former member")):
                out.setdefault((v.get("body"), t), {}).setdefault(mid, nm)
    return out


def _roster_name(nm):
    """"Smith, Steven" -> "Steven Smith"."""
    if "," in nm:
        last, first = (x.strip() for x in nm.split(",", 1))
        return f"{first} {last}"
    return nm


def resolve(tens, people, roster=None, current=""):
    """The tenures with the member each one names: member_id and their
    ballot name, where exactly one member of that chamber that term matches.
    `roster` ({id: member}) answers for the current term too, where a member
    elected at Organization Day has no ballot yet. A hand entry's member_id
    is taken as it is given."""
    out, missed = [], []
    for t in tens:
        term = term_of(t["from"])
        who = dict(people.get((t["body"], term), {}))
        if roster and term == current:
            for mid, m in roster.items():
                if (m.get("chamber") or "")[:1] == t["body"] and m.get("name"):
                    who.setdefault(str(mid), m["name"])
        if t.get("member_id"):
            mid = t["member_id"]
            out.append({**t, "member_id": mid, "ballot_name": who.get(mid, "")})
            continue
        hit = [mid for mid, nm in who.items() if same_person(_roster_name(nm), t["name"])]
        if len(hit) == 1:
            out.append({**t, "member_id": hit[0], "ballot_name": who[hit[0]]})
        else:
            out.append({**t, "member_id": "", "ballot_name": ""})
            missed.append((t, len(hit)))
    return out, missed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="YYYY-MM-DD: who held what that day")
    a = ap.parse_args()
    tens, ms, bad = load()
    for e, why in bad:
        print(f"  corrections/officials.json: an entry left out, {why}: {e}")
    if a.date:
        for t in sorted(on(tens, "H", a.date) + on(tens, "S", a.date),
                        key=lambda t: (t["body"], RANK[t["title"]])):
            print(f'{a.date}  {t["office"]:34} {t["name"]:24} [{t["kind"]}] {t["source"]}')
        print("held now, as a member's page names it:")
        for (b, ti), t in sorted(holders(tens, ms, a.date).items()):
            print(f'  {t["office"]:34} {t["name"]:24} [{t["kind"]}] {t["source"]}')
        return 0
    for t in tens:
        print(f'{t["from"]} to {t["to"]}  {t["office"]:34} {t["name"]:24} [{t["kind"]}]')
        print(f'      {t["source"]}')
    print(f"{len(tens)} tenures from {len(ms)} mentions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
