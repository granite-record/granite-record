#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.81
"""
The civics section: a hub and one page per topic, in order.

    python3 src/pages/build_civics.py --site site --base https://graniterecord.org

Writes site/learn.html (the hub) and site/learn/<slug>.html (the topics).
No network. Reads civics.py for the writing and shell.py for the page frame.

WHY THE HUB KEEPS THE OLD ADDRESS

learn.html was one page called "How it works" and is now the way into eleven.
It keeps its address because the nav links to it, the home page links to it,
and anything already pointing at it should still arrive somewhere sensible
rather than at a 404. The topics live under /learn/ beneath it.

THE ORDER MATTERS

Each page ends with the next one by name -- "Next: How a bill becomes law" --
because a reader who has just learned what the General Court is has a natural
next question, and a menu does not answer it. The order is civics.TOPICS and
nothing else; the hub, the footers and the sitemap all read it, so there is
one place to reorder the section.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import html
import json
import re
import unicodedata
from collections import Counter

import build_date
import civics
import i18n as I
import components as C
import constitution_tab as CT
import guides as G
import parse_constitution as PCON
import learn_numbers
import legislative_year
import proceedings as P
import shell as S
import structured as LD
import site_read as SR


def E(s):
    return html.escape(str(s or ""), quote=True)


def _follows_committee(narr):
    """The percentage of this term's floor decisions that went the committee's way.

    Rounded to a whole number, because a tenth of a point on a claim like this
    is precision the sentence cannot carry. It counts only bills where a
    committee reported and the chamber then took a majority-recommendation
    vote -- the cases where the two can be compared at all.
    """
    stats, _ = learn_numbers.overturned(narr)
    decided = sum(v[0] for v in stats.values())
    against = sum(v[1] for v in stats.values())
    return round(100 * (decided - against) / decided) if decided else 0


def _load(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# "shall adopt rules", "may adopt rules pursuant to RSA 541-A" -- the sentence
# by which the legislature hands an agency the detail. Written out rather than
# counted by hand because the administrative rules page's whole argument is
# that this happens constantly and invisibly, and a reader is entitled to the
# number behind it.
_DELEGATES = re.compile(r"(?:shall|may)\s+adopt\s+rules?", re.I)


def _rules_delegated(root, term):
    """Bills of this term whose own text delegates rulemaking to an agency."""
    texts = _load(Path(root) / "bill_text.json", {}).get(term) or {}
    n = 0
    for rec in texts.values():
        body = rec.get("text") if isinstance(rec, dict) else rec
        if body and _DELEGATES.search(body):
            n += 1
    return n


def _notice(root, term, _seen={}):
    """(hearings counted, median days) between a calendar's publication and the
    hearing it announced, over this term.

    The testifying page says how much warning a reader actually gets, and that
    is a promise about the future, so it has to be measured rather than
    guessed. A hearing is counted once however many calendars carried it.
    Cached because two figures are taken from one pass.
    """
    if term in _seen:
        return _seen[term]
    rows = _load(Path(root) / "meetings.json", [])
    gaps, seen = [], set()
    years = set()
    if "-" in term:
        a, b = term.split("-")[0], term.split("-")[-1]
        years = {a, b}
    for r in rows:
        if r.get("kind") != "public hearing":
            continue
        day, noticed = (r.get("date") or "")[:10], (r.get("noticed") or "")[:10]
        if not (day and noticed) or day[:4] not in years:
            continue
        key = (r.get("body"), r.get("bill"), day, r.get("committee"))
        if key in seen:
            continue
        seen.add(key)
        try:
            from datetime import date
            d1 = date(*map(int, noticed.split("-")))
            d2 = date(*map(int, day.split("-")))
        except (TypeError, ValueError):
            continue
        gap = (d2 - d1).days
        if gap >= 0:
            gaps.append(gap)
    gaps.sort()
    med = gaps[len(gaps) // 2] if gaps else 0
    _seen[term] = (len(gaps), med)
    return _seen[term]


# WHAT BECAME OF A TERM'S CONSTITUTIONAL AMENDMENTS, as a partition of them.
#
# The page used to say "N were killed outright, N died when the session ended,
# N passed one chamber and stopped, and the rest are still in committee or
# were postponed" -- and for 2025-2026 the same three CACRs were in two of
# those counts, "the rest" were six three-fifths failures and one death on the
# table, and the rail it counted from called CACR 13 stopped in the Senate that
# passed it 23-1. Every CACR is in exactly one clause, and a clause with
# nothing in it is left out rather than printed as "0".
#
# THE CLAUSE IS WHAT ENDED IT. A CACR that won a majority on the House floor
# and fell short of three fifths is counted there, whatever its status then
# became: CACR 11 of 2026 passed the Senate 23-1, fell short in the House
# 199-157, and its status is "Died when the session ended" because nothing
# moved it after. The paragraph above this one counts the same failures by
# the same test (_fell_short), so the page cannot give two numbers for them.
_FLOOR_TALLY = re.compile(r"\b(?:RC|DIV|DV)\b\s*[:(]?\s*(\d{1,3})\s*Y?\s*[-–]\s*(\d{1,3})\s*N?\b",
                          re.I)
_PASSING = re.compile(r"ought to pass|\bOTP\b|passage|third reading|3rd reading|\bpassed\b", re.I)
_NOT_PASSING = re.compile(r"table|reconsider|postpone|interim|refer", re.I)
_FAILED = re.compile(r"\bM[FL]\b|lacking|\bfail", re.I)
_NUM = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
        7: "Seven", 8: "Eight", 9: "Nine"}


def _passage_votes(rec):
    """[(body, yeas, nays, carried)] -- the floor votes on passing a CACR,
    with the tally the docket line prints, WHATEVER THRESHOLD THE LINE NAMES.

    Passing one always takes three fifths, so a failed motion to pass with
    more yeas than nays fell short of it, and the line is not needed to say
    so. It used to be: CACR 8 of 2025's "Ought to Pass: MF DV 203-158 Lacking
    Necessary Two-Thirds Vote" is a clerk's slip -- the House Journal of 8 May
    2025 says "lacking the necessary 3/5ths vote" -- and 2016's CACR 17, "MF
    RC 188-135", names no threshold at all. Both were missed."""
    out = []
    for e in (rec or {}).get("events", []) or []:
        raw = e.get("raw") or ""
        if e.get("cancelled"):
            continue
        if not _PASSING.search(raw) or _NOT_PASSING.search(raw):
            continue
        m = _FLOOR_TALLY.search(raw)
        if not m:
            continue
        failed = bool(_FAILED.search(raw))
        carried = not failed and bool(re.search(r"\bMA\b|adopted", raw, re.I))
        if failed or carried:
            out.append(((e.get("body") or "").upper(), int(m.group(1)),
                        int(m.group(2)), carried))
    return out


def _fell_short(rec, status=""):
    """True when a House vote on passing this CACR had more yeas than nays
    and failed, and no House vote on passing it carried. A CACR the House
    then carried on another vote (CACR 26 of 2012 fell two short, was
    reconsidered and carried 239-114) did not fall short, and nor did one
    both chambers passed."""
    if (status or "").startswith("Passed both chambers"):
        return False
    house = [v for v in _passage_votes(rec) if v[0] == "H"]
    return (any(not c and y > n for _, y, n, c in house)
            and not any(c for *_, c in house))


def _cacr_hurdle(idx, every_narr, term):
    """What the record shows about the three-fifths step: how few CACRs get
    through, and how many this term won a House majority and still failed.

    It used to add that the ones that get through "tend to pass by wide
    margins", from the share of those voting: 68% to 97% yes. Against the
    bar itself -- three fifths of the members in office -- two of those eight
    House votes had not one vote to spare: CACR 26 of 2012 carried 239-114
    when 239 was the number needed, the day it had failed 237-115, and CACR
    16 of 2018 carried 235-96 with 391 members in office. A margin measured
    against those voting is the measure the sentence before it says is not
    the one that counts."""
    all_cacrs = [r for r in idx if (r.get("id") or "").startswith("CACR")]
    if not all_cacrs:
        return ""
    through = [r for r in all_cacrs if (r.get("status") or "").startswith("Passed both chambers")]
    first = min((r.get("term") or "" for r in all_cacrs), default="").split("-")[0]
    shown = term.replace("-", "&ndash;")
    out = (f"Of the {len(all_cacrs):,} CACRs filed since {first}, "
           + (f"{len(through):,} passed both chambers." if through
              else "none passed both chambers."))
    out += (" Three fifths is counted against the members in office rather than "
            "against those voting, so a member who does not vote counts against "
            "it, and a CACR can win even three fifths of those voting and still "
            "fail.")
    narr = every_narr.get(term, {})
    short = [r for r in all_cacrs if r.get("term") == term
             and _fell_short(narr.get(r.get("id")), r.get("status"))]
    if short:
        out += (f" In the {shown} term, {len(short):,} "
                f"{'CACR' if len(short) == 1 else 'CACRs'} won a majority of those "
                "voting in the House and still fell short.")
    return out


def _cacr_hurdle_lang(idx, every_narr, term, lang):
    """_cacr_hurdle in `lang` (the Learn pages in Spanish, 25 October 2026):
    the same counts, by the same tests, in the catalog's words."""
    all_cacrs = [r for r in idx if (r.get("id") or "").startswith("CACR")]
    if not all_cacrs:
        return ""
    through = [r for r in all_cacrs if (r.get("status") or "").startswith("Passed both chambers")]
    first = min((r.get("term") or "" for r in all_cacrs), default="").split("-")[0]
    out = (I.say(lang, "learn.cacr.since", "Of the {n} CACRs filed since {year},", n=f"{len(all_cacrs):,}",
                 year=first) + " "
           + (I.say(lang, "learn.cacr.through_one", "one passed both chambers.") if len(through) == 1
              else I.say(lang, "learn.cacr.through", "{n} passed both chambers.", n=f"{len(through):,}")
              if through else I.say(lang, "learn.cacr.none_through", "none passed both chambers.")))
    out += " " + I.say(lang, "learn.cacr.counted", "Three fifths is counted against the members in "
                       "office rather than against those voting, so a member who does not vote "
                       "counts against it, and a CACR can win even three fifths of those voting and "
                       "still fail.")
    narr = every_narr.get(term, {})
    short = [r for r in all_cacrs if r.get("term") == term
             and _fell_short(narr.get(r.get("id")), r.get("status"))]
    if short:
        out += " " + (I.say(lang, "learn.cacr.short_one", "In the {term} term, one CACR won a majority "
                            "of those voting in the House and still fell short.",
                            term=term.replace("-", "&ndash;")) if len(short) == 1 else
                      I.say(lang, "learn.cacr.short", "In the {term} term, {n} CACRs won a majority of "
                            "those voting in the House and still fell short.",
                            term=term.replace("-", "&ndash;"), n=f"{len(short):,}"))
    return out


def org_day(today, lang=I.DEFAULT):
    """"The next is December 2, 2026, for the legislature elected on November
    3." -- the next Organization Day on or after `today`, and the election
    before it (the person, approved 17 October 2026: the General Court page
    never named the day the new legislature takes office)."""
    y = today.year if today.year % 2 == 0 else today.year + 1
    od = P.organization_day(y)
    if today > od:
        y += 2
        od = P.organization_day(y)
    vote = datetime.date(y, 11, 2)
    while vote.weekday() != 1:
        vote += datetime.timedelta(days=1)
    if lang != I.DEFAULT:
        return I.say(lang, "learn.org_day", "The next is {day}, for the legislature elected on "
                     "{vote}.", day=C.date_words(od, "full", lang), vote=C.date_words(vote, "full", lang))
    return (f"The next is {S.date_words(od, 'full')}, for the legislature elected on "
            f"{S.date_words(vote, 'full')}.")


PROBATE_CACR = ("2025-2026", "CACR13")


def probate_vote(rows, today, lang=I.DEFAULT):
    """The register of probate paragraph's last sentence (civics.py,
    [[probate_vote]]), in the tense the build's day gives it: CACR 13's
    election ahead, past with its count not on the site yet, or past with the
    count a person entered in ballot_results.json. `rows` is that file's rows.

    WRITTEN BY THE DAY, NOT BY HAND (17 October 2026). The sentence said the
    question went to the voters "at the November 2026 general election" and
    would have gone on saying so after the vote; a reminder failing preflight
    from 4 November was what was to catch it, on the eve of a release freeze.
    Nothing here is a result the file does not hold.

    In another language (the Learn pages in Spanish, 25 October 2026) each
    sentence is the catalog's, the bill's name the record's own."""
    link = '<a href="bill/2026/cacr13.html">CACR 13 (2026)</a>'
    row = next((r for r in rows or () if (r.get("term"), r.get("bill")) == PROBATE_CACR), None)
    try:
        day = datetime.date.fromisoformat((row or {}).get("election") or "")
    except ValueError:
        return I.say(lang, "learn.probate.sent", "In 2026 the legislature sent the question to the "
                     "voters again, as {link}.", link=link)
    on = S.date_words(day, "full") if lang == I.DEFAULT else C.date_words(day, "full", lang)
    y, n = row.get("yes"), row.get("no")
    if y is None or n is None or y + n <= 0:
        if today <= day:
            return I.say(lang, "learn.probate.ahead", "In 2026 the legislature sent the question to "
                         "the voters again, as {link}, at the general election of {on}.",
                         link=link, on=on)
        return I.say(lang, "learn.probate.counting", "In 2026 the legislature sent the question to "
                     "the voters again, as {link}. The vote was on {on}; the Secretary of "
                     "State&rsquo;s count is not on the site yet.", link=link, on=on)
    share = f"{100 * y / (y + n):.1f}%"
    if 3 * y >= 2 * (y + n):
        return I.say(lang, "learn.probate.ratified", "In 2026 the legislature sent the question to "
                     "the voters again, as {link}, and on {on} the voters ratified it: {share} "
                     "voted yes, where two thirds was needed.", link=link, on=on, share=share)
    return I.say(lang, "learn.probate.failed", "In 2026 the legislature sent the question to the "
                 "voters again, as {link}, and on {on} it did not reach the two thirds it needed: "
                 "{share} of those voting on it voted yes.", link=link, on=on, share=share)


def _voters_verb(label, n):
    """"Passed both chambers, goes to the voters in November 2026" -> "goes to
    the voters at the state general election in November 2026", agreeing
    with n."""
    s = label.split(", ", 1)[1] if ", " in label else "went to the voters"
    s = re.sub(r"to the voters in (?=[A-Z])", "to the voters at the state general election in ", s)
    if s.startswith(("ratified", "not ratified")):
        return ("was " if n == 1 else "were ") + s
    if s.startswith("goes") and n != 1:
        return "go" + s[4:]
    return s


def _cacr_parts(cacrs, narr, term):
    """(head, lead, voters, items): the term's CACRs, every one in exactly one
    part -- the voters, a three-fifths failure on the House floor where the
    docket records one, and otherwise its status. voters is [(status, n)];
    items is [(clause, label, n, tail)], the clause as the sentence says it and
    the label and tail as the table's row does."""
    shown = term.replace("-", "&ndash;")
    short = [r for r in cacrs if _fell_short(narr.get(r.get("id")), r.get("status"))]
    rest = [r for r in cacrs if all(r is not s for s in short)]
    by = Counter(r.get("status") or "" for r in rest)
    head = f"The {shown} term filed <b>{len(cacrs):,} {'CACR' if len(cacrs) == 1 else 'CACRs'}</b>."
    voters = sorted(s for s in by if s.startswith("Passed both chambers"))
    nv = sum(by[s] for s in voters)
    if not nv:
        lead = "None passed both chambers."
    elif len(voters) == 1:
        lead = (f"{_NUM.get(nv, f'{nv:,}')} passed both chambers and "
                f"{_voters_verb(voters[0], nv)}.")
    else:
        lead = (f"{nv:,} passed both chambers: "
                + ", ".join(f"{by[s]:,} {_voters_verb(s, by[s])}" for s in voters) + ".")

    def n_(k):
        return f"{k:,}"

    items = []
    if by["Killed"]:
        items.append((f"{n_(by['Killed'])} {'was' if by['Killed'] == 1 else 'were'} killed outright",
                      "Killed outright", by["Killed"], ""))
    if short:
        sen = sum(1 for r in short if (r.get("passage") or "")[:2] == "Sp")
        tail = ""
        if sen:
            tail = (f"{sen:,} of them after passing the Senate" if len(short) > 1
                    else "after passing the Senate")
        items.append((f"{n_(len(short))} fell short of three fifths on the House floor"
                      + (f", {tail}" if tail else ""),
                      "Fell short of three fifths on the House floor", len(short), tail))
    failed = [r for r in rest if r.get("status") == "Failed to pass"]
    if failed:
        items.append((f"{n_(len(failed))} failed a floor vote", "Failed a floor vote",
                      len(failed), ""))
    if by["Died on the table"]:
        items.append((f"{n_(by['Died on the table'])} died on the table", "Died on the table",
                      by["Died on the table"], ""))
    ended = [r for r in rest if r.get("status") == "Died when the session ended"]
    if ended:
        after = Counter((r.get("passage") or "")[:1] for r in ended
                        if (r.get("passage") or "")[1:2] == "p")
        tail = ""
        if sum(after.values()):
            where = " or ".join(("the Senate" if c == "S" else "the House")
                                for c in sorted(after))
            tail = (f"{sum(after.values()):,} of them after passing {where}"
                    if len(ended) > 1 else f"after passing {where}")
        items.append((f"{n_(len(ended))} died when the session ended" + (f", {tail}" if tail else ""),
                      "Died when the session ended", len(ended), tail))
    done = {"Killed", "Failed to pass", "Died on the table",
            "Died when the session ended", *voters}
    for s in sorted(s for s in by if s not in done):
        items.append((f"{n_(by[s])} {'is' if by[s] == 1 else 'are'} listed as “{s}”",
                      f"Listed as “{s}”", by[s], ""))
    return head, lead, [(s, by[s]) for s in voters], items


_MONTHS_ES = {"January": "enero", "February": "febrero", "March": "marzo", "April": "abril",
              "May": "mayo", "June": "junio", "July": "julio", "August": "agosto",
              "September": "septiembre", "October": "octubre", "November": "noviembre",
              "December": "diciembre"}


def _voters_lang(label, lang):
    """A CACR status that reached the voters, as the table's row says it in
    `lang`: "Passed both chambers, goes to the voters in November 2026" and
    the rest (build_site_v2.TO_THE_VOTERS, RATIFIED, NOT_RATIFIED)."""
    m = re.match(r"Passed both chambers, (goes|went) to the voters(?: in (\w+) (\d{4}))?$", label)
    if m:
        when = (I.say(lang, "learn.cacr.at_election", "at the state general election in {when}",
                      when=f"{_MONTHS_ES.get(m.group(2), m.group(2))} de {m.group(3)}"
                      if lang == "es" else f"{m.group(2)} {m.group(3)}") if m.group(2) else "")
        verb = (I.say(lang, "learn.cacr.goes", "Passed both chambers; goes to the voters")
                if m.group(1) == "goes" else
                I.say(lang, "learn.cacr.went", "Passed both chambers; went to the voters"))
        return verb + (" " + when if when else "")
    if label == "Passed both chambers, ratified by the voters":
        return I.say(lang, "learn.cacr.ratified", "Passed both chambers; ratified by the voters")
    if label == "Passed both chambers, not ratified by the voters":
        return I.say(lang, "learn.cacr.not_ratified", "Passed both chambers; not ratified by the voters")
    return f'<span lang="en">{label}</span>'


def _cacr_parts_lang(cacrs, narr, term, lang):
    """_cacr_parts' table rows and lead in `lang`: (lead, rows), each row
    (label, n, tail, needs) as _cacr_table draws it, every CACR of the term
    in exactly one, by the same tests as the English."""
    shown = term.replace("-", "&ndash;")
    short = [r for r in cacrs if _fell_short(narr.get(r.get("id")), r.get("status"))]
    rest = [r for r in cacrs if all(r is not s for s in short)]
    by = Counter(r.get("status") or "" for r in rest)
    voters = sorted(s for s in by if s.startswith("Passed both chambers"))
    nv = sum(by[s] for s in voters)
    head = (I.say(lang, "learn.cacr.filed_one", "The {term} term filed <b>1 CACR</b>.", term=shown)
            if len(cacrs) == 1 else
            I.say(lang, "learn.cacr.filed", "The {term} term filed <b>{n} CACRs</b>.", term=shown,
                  n=f"{len(cacrs):,}"))
    if not nv:
        lead = I.say(lang, "learn.cacr.none", "None passed both chambers.")
    elif nv == 1:
        lead = I.say(lang, "learn.cacr.passed_one", "One passed both chambers.")
    else:
        lead = I.say(lang, "learn.cacr.passed", "{n} passed both chambers.", n=f"{nv:,}")
    rows = [(_voters_lang(st, lang), by[st], "", False) for st in voters]
    if by["Killed"]:
        rows.append((I.say(lang, "learn.cacr.killed", "Killed outright"), by["Killed"], "", False))
    if short:
        sen = sum(1 for r in short if (r.get("passage") or "")[:2] == "Sp")
        tail = ""
        if sen:
            tail = (I.say(lang, "learn.cacr.of_them_senate", "{n} of them after passing the Senate",
                          n=f"{sen:,}") if len(short) > 1 else
                    I.say(lang, "learn.cacr.after_senate", "after passing the Senate"))
        rows.append((I.say(lang, "learn.cacr.fell_short", "Fell short of three fifths on the House floor"),
                     len(short), tail, True))
    failed = [r for r in rest if r.get("status") == "Failed to pass"]
    if failed:
        rows.append((I.say(lang, "learn.cacr.failed", "Failed a floor vote"), len(failed), "", False))
    if by["Died on the table"]:
        rows.append((I.say(lang, "learn.cacr.table", "Died on the table"), by["Died on the table"],
                     "", False))
    ended = [r for r in rest if r.get("status") == "Died when the session ended"]
    if ended:
        after = Counter((r.get("passage") or "")[:1] for r in ended
                        if (r.get("passage") or "")[1:2] == "p")
        tail = ""
        if sum(after.values()):
            where = (" " + I.say(lang, "learn.or", "or") + " ").join(
                (I.say(lang, "learn.the_senate", "the Senate") if c == "S"
                 else I.say(lang, "learn.the_house", "the House")) for c in sorted(after))
            tail = (I.say(lang, "learn.cacr.of_them_after", "{n} of them after passing {where}",
                          n=f"{sum(after.values()):,}", where=where) if len(ended) > 1 else
                    I.say(lang, "learn.cacr.after", "after passing {where}", where=where))
        rows.append((I.say(lang, "learn.cacr.ended", "Died when the session ended"), len(ended), tail,
                     False))
    done = {"Killed", "Failed to pass", "Died on the table", "Died when the session ended", *voters}
    for st in sorted(st for st in by if st not in done):
        rows.append((I.say(lang, "learn.cacr.listed", "Listed as {status}",
                           status=f'<span lang="en">“{st}”</span>'), by[st], "", False))
    return f"{head} {lead}", rows


def _cacr_lang(cacrs, narr, term, lang):
    """(cacr_lead, cacr_table) in `lang`."""
    shown = term.replace("-", "&ndash;")
    if not cacrs:
        none = I.say(lang, "learn.cacr.no_cacrs", "The {term} term filed no CACRs.", term=shown)
        return none, ""
    lead, rows = _cacr_parts_lang(cacrs, narr, term, lang)
    assert sum(n for _, n, _, _ in rows) == len(cacrs), "the CACR table does not add up to the term"
    trs = "".join(
        f'<tr{" class=\"needs\"" if needs else ""}><th scope="row" class="is-text">{label}'
        + (f'<span class="l-sub">{tail}</span>' if tail else "")
        + f'</th><td class="l-num">{n:,}</td></tr>' for label, n, tail, needs in rows)
    table = ('<div class="l-tablewrap"><table class="l-table"><caption>'
             + (I.say(lang, "learn.cacr.caption_one", "The one CACR of the {term} term", term=shown)
                if len(cacrs) == 1 else
                I.say(lang, "learn.cacr.caption", "The {n} CACRs of the {term} term", n=f"{len(cacrs):,}",
                      term=shown))
             + '</caption><thead><tr><th scope="col">'
             + I.say(lang, "learn.cacr.became", "What became of them") + "</th>"
             '<th scope="col" class="l-num">CACR</th></tr></thead>'
             f"<tbody>{trs}</tbody></table></div>")
    return lead, table


def _cacr_record(cacrs, narr, term):
    """The term's CACRs as one paragraph: what it filed, what reached the
    voters, and then every other CACR in exactly one clause."""
    if not cacrs:
        return f"The {term.replace('-', '&ndash;')} term filed no CACRs."
    head, lead, _voters, items = _cacr_parts(cacrs, narr, term)
    clauses = [c for c, *_ in items]
    body = ""
    if clauses:
        # A clause with a comma of its own ("10 fell short ..., 3 of them after
        # passing the Senate") would run into the next; semicolons keep a
        # reader from counting the tail as another clause.
        sep = "; " if any("," in c for c in clauses) else ", "
        body = " " + (clauses[0] if len(clauses) == 1
                      else sep.join(clauses[:-1]) + sep + "and " + clauses[-1]) + "."
        body = " " + body[1].upper() + body[2:]
    return f"{head} {lead}{body}"


def _cacr_lead(cacrs, narr, term):
    """The paragraph over the table: what the term filed and what reached the
    voters, the first two sentences of _cacr_record."""
    if not cacrs:
        return f"The {term.replace('-', '&ndash;')} term filed no CACRs."
    head, lead, _voters, _items = _cacr_parts(cacrs, narr, term)
    return f"{head} {lead}"


def _cacr_table(cacrs, narr, term):
    """The rest of _cacr_record's paragraph as a table, a row a part, the
    passed ones first: every CACR of the term in exactly one row, which the
    table's total says (the first round's prototype, which the person liked on
    9 October 2026). A three-fifths failure carries the threshold's amber."""
    if not cacrs:
        return ""
    _head, _lead, voters, items = _cacr_parts(cacrs, narr, term)
    rows = ([(st.replace(", ", "; ", 1), n, "", False) for st, n in voters]
            + [(label, n, tail, label.startswith("Fell short")) for _c, label, n, tail in items])
    assert sum(n for _, n, _, _ in rows) == len(cacrs), "the CACR table does not add up to the term"
    shown = term.replace("-", "&ndash;")
    trs = "".join(
        f'<tr{" class=\"needs\"" if needs else ""}><th scope="row" class="is-text">{label}'
        + (f'<span class="l-sub">{tail}</span>' if tail else "")
        + f'</th><td class="l-num">{n:,}</td></tr>' for label, n, tail, needs in rows)
    return ('<div class="l-tablewrap"><table class="l-table">'
            f"<caption>The {len(cacrs):,} CACRs of the {shown} term</caption>"
            '<thead><tr><th scope="col">What became of them</th>'
            '<th scope="col" class="l-num">CACRs</th></tr></thead>'
            f"<tbody>{trs}</tbody></table></div>")


def sitting_term(idx):
    """The term still sitting: the newest term the bill index holds, which
    the bill search opens on -- not site_read.figures_term, the term the
    Learn pages describe, which is the one before it from the first bill of
    a new term until most of that term's bills are decided."""
    return max((r.get("term") for r in idx if SR.TERM_FILE.fullmatch(r.get("term") or "")),
               default="")


def filmed_from(per_term, filmed_term, sitting):
    """The earliest term from which every later term has nine bills in ten
    with a filmed hearing, the term still sitting passed over where it does
    not yet clear the bar; "" where none does. per_term and filmed_term are
    {term: bills} and {term: bills with a filmed hearing}."""
    video_from = ""
    for t in sorted(per_term, reverse=True):
        if filmed_term.get(t, 0) < 0.9 * per_term[t]:
            if t == sitting:
                continue
            break
        video_from = t
    return video_from


def record_figures(site, root=Path(".")):
    """Every count the Learn pages state, from what the build has just written.

    THEY WERE TYPED, AND THEY DRIFTED. Measured against the built site, the
    pages said "4,230 bills on this site" of a site holding 33,683, "68 vetoed
    bills" across "two terms" of nineteen, and "855 were killed" of a term the
    record now puts at 853 -- each true on the day it was written. civics.py
    names a figure as [[name]] and this fills it, each by the definition the
    typed number had been counted by: every one reproduced the typed figure
    wherever that was still right.
    """
    # Every bill's row, from the term files the pages read (site_read). It
    # stops where there is none: from a missing file this read [] and filled
    # every figure with a count of nothing.
    idx = SR.bill_index_or_stop(site, "build_civics.py")
    # Not simply the newest term: one whose bills are mostly still to be
    # decided has no story yet to tell (site_read.figures_term).
    term = SR.figures_term(idx)
    cur = [r for r in idx if r.get("term") == term]
    # THE TERM STILL SITTING IS THE NEWEST, NOT THE ONE DESCRIBED (18 October
    # 2026). Since figures_term the term the figures tell is the one before
    # the newest from the first 2027 bill until most of 2027's are decided,
    # and two rules below that mean the term still sitting -- the vetoes that
    # can still be waiting, and the term the filmed-hearing run passes over --
    # read `term` for it. Rehearsed on preflight's fixture with a few 2027
    # bills, the second stopped the build: 2027-2028, a term with most of its
    # hearings still to come, was held to nine bills in ten filmed as a
    # finished term, and the build exits when no term clears the bar. So
    # every night from the first 2027 bill to the summer would have built
    # nothing.
    still_sitting = sitting_term(idx) or term
    status = Counter(r.get("status") for r in cur)
    kind = Counter(r.get("kind") for r in cur)
    prefix = Counter(re.match(r"[A-Z]*", r.get("id") or "").group(0) for r in cur)

    # The House from the district map, as build_composition counts it: seats per
    # (county, district), and the sitting members from the roster.
    house = {}
    senate = set()
    dist = _load(Path(site) / "districts.json", {})
    for wards in dist.values():
        for w in wards.values():
            if w.get("senate"):
                senate.add(w["senate"])
            for h in w.get("house") or []:
                house[(h.get("county"), h.get("district"))] = h
    ordinary = [h for h in house.values() if not h.get("floterial")]
    seats = sum(h.get("seats") or 1 for h in house.values())
    sitting = sum(1 for m in _load(Path(site) / "legislators.json", []) if m.get("chamber") == "H")

    # How many members each House roll call of the term recorded, voting or not.
    first = term.split("-")[0]
    seated = Counter()
    if first.isdigit():
        years = {first, str(int(first) + 1)}
        for v in _load(Path(root) / "data" / "member_votes.json", []):
            if v.get("body") == "H" and str(v.get("year")) in years:
                seated[(v.get("year"), v.get("vote_number"))] += 1

    senate_sitting = sum(1 for m in _load(Path(site) / "legislators.json", [])
                         if m.get("chamber") == "S")
    every_narr = _load(Path(root) / "narratives.json", {})
    narr = every_narr.get(term, {})

    def chambers(rec):
        labels = [" " + (s.get("label") or "") + " " for s in rec.get("stages") or []]
        return {c for c, word in (("H", " House "), ("S", " Senate ")) if any(word in x for x in labels)}

    vetoed = {(r.get("term"), r.get("id")) for r in idx
              if r.get("status") in ("Vetoed, override failed", "Veto overridden, became law", "Vetoed")}
    messages = _load(Path(root) / "veto_messages.json", {})
    # ONLY THE CURRENT TERM CAN STILL BE WAITING. A veto from a finished term
    # with no override recorded was tabled or never taken up, and the veto
    # stood: 1992's HB 1407 was laid on the table 254-78 and died there, and
    # this counted it as "still awaiting its override vote". The term still
    # sitting, not the one the figures describe (`still_sitting`, above).
    pending = sum(1 for r in idx if r.get("status") == "Vetoed" and r.get("term") == still_sitting)
    stood = sum(1 for r in idx if r.get("status") == "Vetoed, override failed"
                or (r.get("status") == "Vetoed" and r.get("term") != still_sitting))
    # Constitutional amendments of the term, read from their statuses -- what
    # each page asserts -- and from the docket's own floor lines for the votes.
    cacrs = [r for r in cur if (r.get("id") or "").startswith("CACR")]
    # A hearing of a bill, once however many recordings it was matched against.
    # Not the docket's notice of one for a bill withdrawn before the day or
    # never introduced, which no page of the site calls a hearing
    # (proceedings.notice_only): three of the rows this counted.
    procs, _notices = P.sittings(P.load(), every_narr)
    hearings = len({(r.get("term"), r.get("bill"), r.get("body"), r.get("date")) for r in procs
                    if r.get("kind") in ("public hearing", "hearing")})
    # WHICH BILLS HAVE A HEARING ON VIDEO, and the term from which nearly all
    # do. Two pages said "every bill's Videos tab" links its hearing, of a
    # record where 5,903 of 33,683 bills have one and none before 2019. The
    # term named is the earliest from which EVERY later term has nine bills
    # in ten filmed, so one well-recorded old term cannot stand for a run.
    #
    # THE TERM STILL SITTING IS NOT HELD TO IT. Its bills are heard across
    # two years, so in January most have had no hearing to film: the first
    # draft of this loop started from that term, stopped on it, and named no
    # year at all, and both pages would have printed "nearly every one since"
    # followed by nothing. The term still sitting counts towards the run when
    # it already clears the bar and is passed over when it does not; every
    # finished term is held to it.
    filmed = {(r.get("term"), r.get("bill")) for r in procs
              if r.get("kind") in ("public hearing", "hearing") and r.get("video_id")}
    per_term = Counter(r.get("term") for r in idx if r.get("term"))
    filmed_term = Counter(t for t, _ in filmed)
    video_from = filmed_from(per_term, filmed_term, still_sitting)
    # SILENCE IS NOT SUCCESS. A record of finished terms that names no year
    # has lost its recordings rather than stopped making them, and the pages
    # would quietly drop the year they give; this stops the build instead. A
    # record of one term, which preflight's fixture site is, has no finished
    # term to judge, and its pages say only how many bills were filmed.
    if not video_from and len(per_term) > 1:
        newest = "; ".join(f"{t}: {filmed_term[t]:,} of {per_term[t]:,}"
                           for t in sorted(per_term, reverse=True)[:3])
        raise SystemExit(
            "the newest finished term does not have nine bills in ten with a filmed "
            f"hearing ({newest}), so the Learn pages can name no year from which "
            "hearings are on video. Check proceedings.csv's video_id column.")
    # ROLL CALLS IN THIS RECORD BEGIN IN ONE YEAR. A bill from before it has
    # none here because none were collected, not because none were taken: the
    # 1989-1990 docket names roll calls, and the 1997 journals print them.
    rc_years = [int(x["year"]) for bills_ in _load(Path(root) / "rollcalls.json", {}).values()
                for rows_ in bills_.values() for x in rows_ or []
                if str(x.get("year") or "").isdigit()]
    rc_first = min(rc_years, default=0)
    # With no roll calls to read, two pages would say this record's roll calls
    # begin "from 0 on" and count the bills "from before 0". Nothing true can
    # be said without the file, so the build stops rather than print that.
    if not rc_first:
        raise SystemExit(f"{Path(root) / 'rollcalls.json'} holds no roll call with a year; "
                         "the Learn pages would say the record's roll calls begin in 0")
    figures = {
        "term": term.replace("-", "&ndash;"),
        "bills": len(cur), "hb": prefix["HB"], "sb": prefix["SB"], "cacr": prefix["CACR"],
        "resolutions": sum(n for p, n in prefix.items() if p.endswith("R") and p != "CACR"),
        "killed": status["Killed"], "signed": status["Signed into law"],
        "study": status["Referred for interim study"], "tabled": status["Died on the table"],
        "session_end": status["Died when the session ended"],
        "unsigned": status["Became law unsigned"], "overridden": status["Veto overridden, became law"],
        "law": kind["law"],
        "house_seats": seats, "house_sitting": sitting, "house_vacant": max(seats - sitting, 0),
        "seated_most": max(seated.values(), default=0), "seated_fewest": min(seated.values(), default=0),
        "house_districts": len(house), "senate_districts": len(senate), "ordinary": len(ordinary),
        "single": sum(1 for h in ordinary if h.get("seats") == 1),
        "two": sum(1 for h in ordinary if h.get("seats") == 2),
        "largest": max((h.get("seats") or 1 for h in house.values()), default=0),
        "floterial": len(house) - len(ordinary),
        # How often a chamber went the way its committee recommended, from the
        # record rather than from an impression. learn_numbers.overturned pairs
        # each committee report with the floor vote that followed it and is
        # what the draft page of numbers reports at length; this is the one
        # figure of it the Learn page states. The prose used to say "usually
        # follows it", which is true and says nothing: it is 98%, and the 2%
        # is the interesting part.
        "follows_committee": _follows_committee(narr),
        # Not a count: what Using This Site says of email, which changes the
        # day email following goes live (civics.FOLLOW_EMAIL).
        "follow_email": civics.FOLLOW_EMAIL[S.follow_live()],
        # Nor this: the next Organization Day, from the build's day (org_day).
        "org_day": org_day(build_date.today()),
        # Nor this: the register of probate paragraph's last sentence, told
        # in the tense the build's day gives CACR 13's vote (probate_vote).
        "probate_vote": probate_vote(
            _load(Path(root) / "corrections" / "ballot_results.json", {}).get("rows"),
            build_date.today()),
        # Eight more the rewritten pages asked for, each counted from the file
        # named beside it rather than typed. A page may state a figure only if
        # the site can produce it, which is the rule that keeps this section
        # worth believing.
        "municipalities": len(_load(Path(root) / "collected" / "town_officials.json", {})),
        "members_sitting": len(_load(Path(site) / "legislators.json", [])),
        "members_email": sum(1 for m in _load(Path(site) / "legislators.json", [])
                             if (m.get("email") or "").strip()),
        "floterial_seats": sum(h.get("seats") or 1 for h in house.values()
                               if h.get("floterial")),
        # How many places -- towns and city wards, 320 of them -- have more
        # than one state representative, whether from a district of several
        # seats, a floterial over it, or both. The page used to explain this
        # with a sentence about whole towns and equal population that the
        # constitution contradicts; this is the count instead.
        "multi_rep_places": sum(
            1 for ws in dist.values() for w in ws.values()
            if sum(h.get("seats") or 1 for h in w.get("house") or []) > 1),
        "all_places": sum(len(ws) for ws in dist.values()),
        # The '1989' in 'back to 1989', from the terms themselves.
        "first_year": min((r.get("term") or "" for r in idx if r.get("term")),
                          default="-").split("-")[0],
        "rules_delegated": _rules_delegated(root, term),
        "notice_hearings": _notice(root, term)[0],
        "notice_median": _notice(root, term)[1],
        "all_bills": len(idx), "all_rollcall": sum(1 for r in idx if (r.get("nrc") or 0) > 0),
        "all_no_rollcall": sum(1 for r in idx if not (r.get("nrc") or 0) > 0),
        "hb2_rollcalls": len(_load(Path(root) / "rollcalls.json", {}).get(term, {}).get("HB2", [])),
        "narrated": len(narr), "both_chambers": sum(1 for v in narr.values() if chambers(v) == {"H", "S"}),
        "conference": sum(1 for v in narr.values()
                          if any("conference" in (s.get("label") or "").lower() for s in v.get("stages") or [])),
        "terms": len({r.get("term") for r in idx if r.get("term")}),
        "vetoed": len(vetoed),
        # Every veto that stood: an override that failed, and a veto of a
        # finished term that no override vote ever reached.
        "veto_failed": stood,
        "veto_overridden": sum(1 for r in idx if r.get("status") == "Veto overridden, became law"),
        "veto_messages": sum(1 for t, b in vetoed if b in messages.get(t, {})),
        "veto_pending": ("" if not pending else " One is still awaiting its override vote."
                         if pending == 1 else f" {pending} are still awaiting their override votes."),
        # The constitution page's two CACR paragraphs, each a sentence built
        # here because its clauses come and go with the counts.
        "cacr_hurdle": _cacr_hurdle(idx, every_narr, term),
        "cacr_record": _cacr_record(cacrs, every_narr.get(term, {}), term),
        "cacr_lead": _cacr_lead(cacrs, every_narr.get(term, {}), term),
        "cacr_table": _cacr_table(cacrs, every_narr.get(term, {}), term),
        "hearings": hearings,
        "hearing_video_bills": len(filmed),
        "hearing_video_from": video_from.split("-")[0],
        # The clause the pages print, so that a record with no year to name
        # drops the clause rather than printing "since" and a gap.
        "hearing_video_since": (f", nearly every one since {video_from.split('-')[0]}"
                                if video_from else ""),
        "rollcall_first_year": str(rc_first),
        "pre_rollcall_bills": sum(1 for r in idx if not (r.get("nrc") or 0)
                                  and (r.get("term") or "")[-4:].isdigit()
                                  and int((r.get("term") or "")[-4:]) < rc_first),
        # Laws of the current term that no roll call on either floor touched.
        "law_no_rollcall": sum(1 for r in cur if r.get("kind") == "law"
                               and not (r.get("nrc") or 0)),
        # Said instead of "rebuilt every night", which no schedule on this
        # machine made true: the page states the one date it can know. In
        # the site's own words, month first; S.BUILT is a citation's form.
        "built_on": S.date_words(build_date.today(), "full"),
    }
    # THE FIGURES THE PAGES DRAW, from the counts above (civics.bar and the
    # rest say how each is drawn). Counted here so that no figure carries a
    # number typed beside the sentence that states it.
    shown = figures["term"]
    rest = (len(cur) - status["Killed"] - status["Signed into law"]
            - status["Referred for interim study"] - status["Died on the table"]
            - status["Died when the session ended"])
    figures["fig_ends"] = civics.bar(
        f"The {len(cur):,} bills and resolutions of the {shown} term",
        f"How the {len(cur):,} bills and resolutions of the {term} term ended",
        [(status["Killed"], "c-died", "killed (ITL)"),
         (status["Signed into law"], "c-law", "signed into law"),
         (status["Referred for interim study"], "c-study", "sent for interim study"),
         (status["Died on the table"], "c-table", "died on the table"),
         (status["Died when the session ended"], "c-end", "died when the session ended"),
         (rest, "c-rest", "every other outcome", False)])
    no_rc = figures["all_no_rollcall"]
    figures["fig_rollcalls"] = civics.bar(
        f"The {figures['all_bills']:,} bills in this record",
        "Bills with and without a recorded roll call",
        [(figures["all_rollcall"], "c-rc", "with at least one recorded roll call"),
         (no_rc - figures["pre_rollcall_bills"], "c-none",
          f"<b>{no_rc:,}</b> with none (the gray and the hatched)", False),
         (figures["pre_rollcall_bills"], "c-old",
          f'<span class="l-sub">of those from before {rc_first}, where this record&rsquo;s '
          "roll calls begin</span>")])
    pending_n = sum(1 for r in idx if r.get("status") == "Vetoed" and r.get("term") == term)
    figures["fig_vetoes"] = civics.bar(
        f"The {len(vetoed):,} vetoed bills across the {figures['terms']} terms on this site",
        f"What became of the {len(vetoed):,} vetoed bills",
        [(stood, "c-died", "the veto stood"),
         (figures["veto_overridden"], "c-law", "overridden, and the bill became law"),
         (pending_n, "c-rest", "still awaiting the override vote")])
    figures["fig_seats"] = civics.seats_figure(seats, sitting, len(senate), senate_sitting)
    figures["fig_term"] = civics.term_figure(term)

    # THE FIGURES WITH WORDS IN THEM, IN EACH OTHER LANGUAGE (the Learn pages
    # in Spanish, 25 October 2026): the same counts, drawn again in the
    # catalog's words and kept beside the English as name@lang, which
    # figures_lang puts in the English one's place. The English above is
    # drawn by its own lines, untouched, so an English page cannot change by
    # a word for this.
    def drawn(lang):
        f = figures

        n_ = lambda k: f"{k:,}"  # noqa: E731
        return {
            "org_day": org_day(build_date.today(), lang),
            "veto_pending": ("" if not pending else " " + (
                I.say(lang, "learn.veto.pending_one", "One is still awaiting its override vote.")
                if pending == 1 else
                I.say(lang, "learn.veto.pending", "{n} are still awaiting their override votes.",
                    n=n_(pending)))),
            "cacr_hurdle": _cacr_hurdle_lang(idx, every_narr, term, lang),
            "cacr_lead": _cacr_lang(cacrs, every_narr.get(term, {}), term, lang)[0],
            "cacr_table": _cacr_lang(cacrs, every_narr.get(term, {}), term, lang)[1],
            "fig_ends": civics.bar(
                I.say(lang, "learn.ends.caption", "The {n} bills and resolutions of the {term} term",
                    n=n_(len(cur)), term=shown),
                I.say(lang, "learn.ends.label", "How the {n} bills and resolutions of the {term} term ended",
                    n=n_(len(cur)), term=term),
                [(status["Killed"], "c-died", I.say(lang, "learn.ends.killed", "killed (ITL)")),
                 (status["Signed into law"], "c-law", I.say(lang, "learn.ends.signed", "signed into law")),
                 (status["Referred for interim study"], "c-study",
                  I.say(lang, "learn.ends.study", "sent for interim study")),
                 (status["Died on the table"], "c-table", I.say(lang, "learn.ends.table", "died on the table")),
                 (status["Died when the session ended"], "c-end",
                  I.say(lang, "learn.ends.session", "died when the session ended")),
                 (rest, "c-rest", I.say(lang, "learn.ends.rest", "every other outcome"), False)]),
            "fig_rollcalls": civics.bar(
                I.say(lang, "learn.rc.caption", "The {n} bills in this record", n=n_(f["all_bills"])),
                I.say(lang, "learn.rc.label", "Bills with and without a recorded roll call"),
                [(f["all_rollcall"], "c-rc", I.say(lang, "learn.rc.with", "with at least one recorded roll call")),
                 (no_rc - f["pre_rollcall_bills"], "c-none",
                  I.say(lang, "learn.rc.none", "<b>{n}</b> with none (the gray and the hatched)", n=n_(no_rc)),
                  False),
                 (f["pre_rollcall_bills"], "c-old",
                  '<span class="l-sub">' + I.say(lang, "learn.rc.old", "of those from before {year}, where "
                                               "this record&rsquo;s roll calls begin", year=rc_first)
                  + "</span>")]),
            "fig_vetoes": civics.bar(
                I.say(lang, "learn.veto.caption", "The {n} vetoed bills across the {terms} terms on this site",
                    n=n_(len(vetoed)), terms=f["terms"]),
                I.say(lang, "learn.veto.label", "What became of the {n} vetoed bills", n=n_(len(vetoed))),
                [(stood, "c-died", I.say(lang, "learn.veto.stood", "the veto stood")),
                 (f["veto_overridden"], "c-law",
                  I.say(lang, "learn.veto.overridden", "overridden, and the bill became law")),
                 (pending_n, "c-rest", I.say(lang, "learn.veto.awaiting", "still awaiting the override vote"))]),
            "fig_seats": civics.seats_figure(seats, sitting, len(senate), senate_sitting, lang),
            "fig_term": civics.term_figure(term, lang),
        }
    for lang in I.LANGS:
        if lang != I.DEFAULT:
            figures.update({f"{k}@{lang}": v for k, v in drawn(lang).items()})
    # THE WORKED EXAMPLE on the finding-your-representatives page, drawn from
    # the map rather than typed: the diagram, and every fact the prose beside
    # it names. civics.reps_example stops the build if the example town stops
    # illustrating a floterial at all. The link to the town's own page comes
    # from build_town_pages rather than being rebuilt here, because three
    # places once built that address themselves and one built it wrongly.
    if dist:
        import build_town_pages
        figures.update(civics.reps_example(dist))
        figures["reps_town_url"] = build_town_pages.town_file(
            figures["reps_town"], "0").lstrip("/")
    # THE LEGISLATURE'S YEAR, from the build's day (17 October 2026): where
    # the term stands, the usual shape of a term with that day pinned on it,
    # and the term's dates with the calendar each is printed in. The day is
    # build_date's, as org_day's is, so a build that states its date draws
    # You Are Here on that date.
    figures.update(legislative_year.figures(build_date.today(), Path(root)))
    # And in each other language that has the schedule's page, as name@lang.
    for lang in I.LANGS:
        if lang != I.DEFAULT and I.has(lang, legislative_year.HREF):
            figures.update({f"{k}@{lang}": v for k, v in legislative_year.figures(
                build_date.today(), Path(root), lang).items()})
    return {k: (f"{v:,}" if isinstance(v, int) else v) for k, v in figures.items()}


def dashes(text):
    """" -- " as the dash it is meant to be.

    The Learn prose is written in the plain-text shorthand this repository's own
    documents use, and it was published that way: "The Council -- five members,
    elected by district -- approves contracts", 5 times on the hub and 54
    across the eleven pages. Nowhere else on the site prints it. Only a hyphen
    pair with a space on each side is touched, so "Education - General", a
    range, and anything inside a tag are left alone.
    """
    return re.sub(r"(?<=\s)--(?=\s)", "—", text or "")


# A BILL KEEPS ITS SUFFIX WHEREVER IT HAS ONE (the person's D7, 8 October
# 2026: -FN, -A, -LOCAL are part of the official name). The prose names a bill
# by its number as a link to its page -- "HB 349" -- and the suffix is the
# record's, so it comes from the bill's own row rather than being typed: a
# bill renumbered or given a fiscal note later changes its name here too. A
# year the prose gives in brackets stays, and a link whose words are not a
# bill's number ("the 1995 bill") is left as it was written.
_BILL_LINK = re.compile(r'<a href="bill/(\d{4})/([a-z]+\d+)\.html">\s*([A-Z]+)\s+(\d+)'
                        r'((?:\s+\(\d{4}\))?)\s*</a>')


def suffixed(text, names):
    """Every link to a bill whose words are its number, given the number the
    bill's own row writes ("HB 349-FN"). names is {(year, "hb349"): "HB 349-FN"}."""
    def one(m):
        year, bid, letters, num, yr = m.groups()
        name = names.get((year, bid))
        if not name or not name.replace(" ", "").upper().startswith(f"{letters}{num}"):
            return m.group(0)
        return f'<a href="bill/{year}/{bid}.html">{name}{yr}</a>'
    return _BILL_LINK.sub(one, text or "")


def fill(text, figures):
    """[[name]] -> its figure. A name with no figure stops the build: a page
    that printed "[[killed]]", or nothing where a number was, would publish."""
    unknown = sorted(set(re.findall(r"\[\[(\w+)\]\]", text or "")) - set(figures))
    if unknown:
        raise SystemExit(f"civics.py names figures build_civics does not count: {unknown}")
    return dashes(re.sub(r"\[\[(\w+)\]\]",
                         lambda m: str(figures[m.group(1)]), text or ""))


# ---------------------------------------------------------------------------
# WHERE THE PAGES LIVE, AND HOW THEY HANG TOGETHER (the person, 9 October
# 2026: "an initial hub linking to the learn pages, the how to guides, and
# official sources with tabs for each"; the approved prototypes in
# private/design/polish/proto/resources.html and learn/*.html).
#
# THE HUB IS /resources, with a tab each for Learn, the How-To Guides and the
# Official Sources, and each tab its own address (#learn, #guides, #sources).
# /learn, which was the Learn hub, redirects there (decision 128 of 8 October:
# a line in build_pages.REDIRECTS), and the articles keep their /learn/<page>
# addresses, so nothing already pointing at one breaks. Every href below is
# written from the site's root, because these pages are built from bills.html,
# which carries <base href="/">: "../learn.html" resolved to /../learn.html
# once, and a bare "#s-vetoes" resolves to the home page.
# ---------------------------------------------------------------------------
HUB_PAGE = "resources.html"
HUB = S.canon("/" + HUB_PAGE)
LEARN_DIR = "learn"
# The hub's three tabs, in the person's order: (address, name). HOW-TO GUIDES
# FIRST (the person, 17 October 2026: "How to guides should be the default
# tab when opening the resources page"). The first tab is the one the hub
# opens on (build_town_pages.TABS_JS shows tabs[0] when the address names
# none), and without JavaScript the panels are read in this order, so the
# guides lead there too. An address naming a tab -- /resources#learn -- still
# opens that one.
HUB_TABS = (("guides", "How-To Guides"), ("learn", "Learn"), ("sources", "Official Sources"))
OG_ALT = "Granite Record: how New Hampshire works"

# THE RECORD IN NUMBERS, named once: its page's title and lead and its entry
# on the hub say the same thing. The hub's old blurb promised "the closest
# votes on record" and how "the two chambers differ in the way they take a
# vote", neither of which the page holds (the cohesion review of 9 October
# 2026); the page's own description says what it does.
NUMBERS_SLUG = "by-the-numbers"
NUMBERS_TITLE = "The Record in Numbers"
NUMBERS_WHAT = ("how bills end, committees' workloads and passage rates, amendments, "
                "hearings, attendance, vetoes, the closest votes and the amendments sent to "
                "the voters")
NUMBERS_DESC = ("Statistics counted from the New Hampshire General Court's own record: "
                + NUMBERS_WHAT + ".")


# THE GLOSSARY (14 October 2026, the person's ask): every entry of
# src/pages/words/glossary.json -- the file the term popovers read -- on one
# page, A to Z by its name in full with the abbreviation after it, so the page
# and a popover can never say two things. Like The Record in Numbers it is not
# one of the numbered topics: it is looked things up in, not read in order,
# and the footer links it on every page.
GLOSSARY_SLUG = "glossary"
GLOSSARY_TITLE = "Glossary"
GLOSSARY_DESC = ("The words and abbreviations of the New Hampshire General Court's record, "
                 "from ITL and OTP to crossover and committee of conference, each in plain English.")


def _gloss_abbr(key, name):
    """The abbreviation a key stands for, or "" where the key is a word: OTP
    and RC-calendar are abbreviations (RC), Reconsider and Chaptered are not."""
    k = key.split("-")[0]
    if k == name or " " in k or not (k.upper() == k or any(ch.isdigit() for ch in k)):
        return ""
    return k


def glossary_secs():
    """[(id, heading, content)], one section a letter, each a table of terms."""
    rows = []
    for key, e in C.WORDBOOK["glossary"].items():
        says = (e.get("says") or "").strip()
        if not says:
            raise SystemExit(f"glossary.json: {key} has nothing to say on the glossary page")
        abbr = _gloss_abbr(key, e["name"])
        says = says[0].upper() + says[1:] + ("" if says.endswith(".") else ".")
        rows.append((e["name"].casefold(), key, e["name"], abbr, says))
    by = {}
    for sort, key, name, abbr, says in sorted(rows):
        by.setdefault(name[0].upper(), []).append(
            f'<tr id="t-{_slug(key)}"><th scope="row"><b>{E(name)}</b>'
            + (f' ({E(abbr)})' if abbr else "") + f'</th><td>{dashes(curly(says))}</td></tr>')
    return [(f"s-{L.lower()}", L, "<table><tbody>" + "".join(trs) + "</tbody></table>\n")
            for L, trs in sorted(by.items())]


# THE GLOSSARY IN ANOTHER LANGUAGE (the owner, 24 October 2026: "The
# glossary should also be translated into spanish"). The record stays in
# English -- a bill page says "Inexpedient to Legislate", and so does the
# docket -- so each row gives the term as the record prints it, then its name
# and what it means in the page's language (i18n.say_gloss), A to Z by the
# English, which is the word a reader has in front of them. Drawn in the
# frame the home page is (build_pages.shell), which says the header, the
# footer and Settings in that language, with the Learn pages' own styles.
def glossary_page_lang(lang, base):
    """The glossary page in `lang`, written at i18n.href(lang, GLOSSARY_PAGE)."""
    import build_pages as BP
    rows = []
    for key, e in C.WORDBOOK["glossary"].items():
        says = (e.get("says") or "").strip()
        if not says:
            raise SystemExit(f"glossary.json: {key} has nothing to say on the glossary page")
        name_l = I.say_gloss(lang, key, "name", e["name"])
        says_l = I.say_gloss(lang, key, "says", says)
        says_l = says_l[0].upper() + says_l[1:] + ("" if says_l.endswith(".") else ".")
        rows.append((e["name"].casefold(), key, e["name"], _gloss_abbr(key, e["name"]), name_l, says_l))
    by = {}
    for _sort, key, name, abbr, name_l, says_l in sorted(rows):
        by.setdefault(name[0].upper(), []).append(
            f'<tr id="t-{_slug(key)}"><th scope="row"><b lang="en">{E(name)}</b>'
            + (f' ({E(abbr)})' if abbr else "")
            + (f'<span class="glsl">{E(name_l)}</span>' if name_l != name else "")
            + f'</th><td>{dashes(curly(says_l))}</td></tr>')
    secs = "".join(section(f"s-{L.lower()}", L, "<table><tbody>" + "".join(trs) + "</tbody></table>\n")
                   for L, trs in sorted(by.items()))
    title = I.say(lang, "gloss.page.title", "Glossary")
    lead = I.say(lang, "gloss.page.lead",
                 "The words and abbreviations of the New Hampshire General Court's record. The "
                 "record is in English, so each term is given as it prints it, with its name and "
                 "what it means in plain words.")
    body = (f'<div class="l-page"><header class="l-head"><h1>{E(title)}</h1>'
            f'<p class="l-lead">{curly(lead)}</p></header>'
            f'<div class="l-art">{secs}</div></div>')
    return BP.shell(f"{E(title)} \u2014 Granite Record", GLOSSARY_PAGE, body, desc=lead,
                    base=base, lang=lang)


def name_versions(page, english):
    """`english`, the page at `page` in English, naming its versions in
    the other languages: on <html> (data-alt-<code>, which the language
    script reads), in the footer's link to each, and to a search engine
    (hreflang) once every version is offered (i18n.offered)."""
    alts = {c: S.canon(I.href(c, page)) for c in I.LANGS
            if c != I.DEFAULT and I.has(c, page)}
    for c, h in alts.items():
        english = english.replace('<html lang="en"', f'<html lang="en" data-alt-{c}="{h}"', 1)
        english = english.replace(f'lang="{c}" data-href="{I.href(c, "index.html")}"',
                                  f'lang="{c}" data-href="{h}"', 1)
    if alts and all(I.offered(c) for c in alts):
        base = "https://graniterecord.org"
        links = "".join(f'<link rel="alternate" hreflang="{c}" href="{base}{h}">'
                        for c, h in {I.DEFAULT: S.canon(I.href(I.DEFAULT, page)), **alts}.items())
        english = english.replace("</head>", links + "</head>", 1)
    return english


GLOSSARY_PAGE = "learn/glossary.html"


def curly(text):
    """Escaped for the page, with the apostrophe a reader sees (the meta
    description keeps the plain one it has always had)."""
    return E(text).replace("&#x27;", "&rsquo;")


def learn_href(slug):
    return f"{LEARN_DIR}/{slug}.html"


def article_href(slug):
    """Where a civics topic is written. THE THREE THAT BECAME GUIDES
    (civics.HOW_TO, 17 October 2026) are at /guides/<slug>, beside the
    step-by-step guides on the How-To Guides tab; the rest at /learn/<slug>."""
    return guide_href(slug) if slug in civics.HOW_TO else learn_href(slug)


def learn_topics(topics):
    """The topics Learn lists and walks in order: all but civics.HOW_TO."""
    return [t for t in topics if t["slug"] not in civics.HOW_TO]


def how_to_topics(topics):
    """The topics that are how-to guides now, in civics.HOW_TO's order."""
    by = {t["slug"]: t for t in topics}
    return [by[s] for s in civics.HOW_TO if s in by]


# A small number in a sentence or a heading is spelled out ("Thirteen short
# pages", "The Thirteen Pages"), and falls back to the digits past twenty, by
# which point the section is a different thing and the sentence needs
# rewriting anyway. COUNTED, NOT TYPED: "Eleven short pages" once sat over a
# list of thirteen.
NUMBER_WORD = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
    7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven",
    12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen",
    16: "Sixteen", 17: "Seventeen", 18: "Eighteen", 19: "Nineteen",
    20: "Twenty",
}


def _plain(inner):
    """A heading's words with its tags out and its entities LEFT ALONE: E()
    here would publish "2025&amp;ndash;2026"."""
    return re.sub(r"<[^>]+>", "", inner).strip()


def _slug(inner):
    """A heading's own words, as an address."""
    bare = html.unescape(re.sub(r"<[^>]+>", "", inner))
    flat = unicodedata.normalize("NFKD", bare).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", flat.lower()).strip("-")
    if not s:
        raise SystemExit("a learn heading has no words to make an address "
                         "from: " + inner[:60])
    return s


_H2 = re.compile(r"<h2([^>]*)>(.*?)</h2>", re.S)
_WIDE = re.compile(r"<!--wide-->(.*?)<!--/wide-->", re.S)


def split_sections(article, where):
    """[(id, heading, content)]: the page cut at its h2s.

    DERIVED, NOT AUTHORED. Each heading's address is "s-" and its own words
    -- the addresses the pages have had since contents lists were added, so a
    deep link made then still lands -- unless the heading carries an id of
    its own, which is how an author pins an address whose wording will change.

    EVERY WORD IS UNDER A HEADING. W4 sets each heading in the margin beside
    its prose, so words before the first one would sit beside nothing; the
    build stops on them rather than publishing a page that starts in the
    middle.
    """
    parts = _H2.split(article)
    if parts[0].strip():
        raise SystemExit(f"{where} has words before its first heading: "
                         + re.sub(r"\s+", " ", parts[0].strip())[:80])
    out, seen = [], set()
    for k in range(1, len(parts), 3):
        attrs, inner, content = parts[k], parts[k + 1], parts[k + 2]
        got = re.search(r'id="([^"]+)"', attrs)
        base = got.group(1) if got else "s-" + _slug(inner)
        sid, n = base, 2
        while sid in seen:
            sid, n = f"{base}-{n}", n + 1
        seen.add(sid)
        out.append((sid, inner.strip(), content))
    return out


def tables(content):
    """A table written in the prose as a bare <table> takes the Learn table's
    box: it scrolls inside its own frame on a phone rather than pushing the
    page sideways. A figure's table carries its own class and is left alone."""
    return (content.replace("<table>", '<div class="l-tablewrap"><table class="l-table l-deftab">')
            .replace("</tbody></table>\n", "</tbody></table></div>\n")
            if "<table>" in content else content)


def section(sid, heading, content, level=2):
    """One W4 section: the heading in the margin, the prose beside it at
    about 100 characters, and a figure marked wide (civics.wide) across both
    columns where it falls, the prose resuming beside the margin under it."""
    content = tables(content)
    blocks, pos = [], 0
    for m in _WIDE.finditer(content):
        blocks.append(("col", content[pos:m.start()]))
        blocks.append(("wide", m.group(1)))
        pos = m.end()
    blocks.append(("col", content[pos:]))
    body = "".join(f'<div class="l-wide">{b}</div>' if kind == "wide"
                   else f'<div class="l-secb">{b}</div>'
                   for kind, b in blocks if b.strip())
    return (f'<section class="l-sec" id="{E(sid)}">'
            f'<h{level} class="l-sech">{heading}</h{level}>{body}</section>')


def sources_list(sources):
    """Where This Comes From, as document rows: the name as the link and the
    host beside it ("gc.nh.gov · PDF").

    A SOURCE ON THIS SITE IS NOT AN OUTWARD LINK. One of them is our own town
    directory -- the General Court's address lookup answers 404 and the town
    pages already hold what it gave -- and sending a reader to our own page
    in a new tab, marked as though it were elsewhere, tells them something
    untrue about where they are going. Its row says Granite Record.

    A SOURCE WITH NO ADDRESS IS NAMED, NOT LINKED (17 October 2026). The
    Senate's written guidance, kept byte for byte in records/sources/, and the
    editor's own account of how hearings run in practice have no page to send
    a reader to. The row names the source, and the bracket at the end of its
    name, where there is one, says who published it.
    """
    def one(label, u):
        if not u:
            m = re.match(r"^(.*?) \(([^()]*)\)$", label)
            name, meta = (m.group(1), m.group(2)) if m else (label, "Granite Record")
            return (f'<li class="l-doc"><span>{E(name)}</span>'
                    f'<span class="l-dmeta">{E(meta)}</span></li>')
        if not u.startswith("http"):
            return (f'<li class="l-doc"><a href="{E(u)}">{E(label)}</a>'
                    f'<span class="l-dmeta">Granite Record</span></li>')
        host = re.sub(r"^https?://(?:www\.)?([^/]+).*$", r"\1", u)
        meta = host + (" &middot; PDF" if u.lower().endswith(".pdf") else "")
        return (f'<li class="l-doc"><a href="{E(u)}" target="_blank" rel="noopener">'
                f'{E(label)}</a><span class="l-dmeta">{meta}</span></li>')
    return '<ul class="l-docs">' + "".join(one(label, u) for label, u in sources) + "</ul>"


def hub_bar(current="learn"):
    """The Resources bar over every Learn page: the hub by name, then its three
    tabs as links, with Learn marked as where the reader is."""
    tabs = "".join(
        f'<a class="l-hubtab" href="{HUB}#{pid}"'
        + (' aria-current="true"' if pid == current else "")
        + f">{E(name)}</a>" for pid, name in HUB_TABS)
    return (f'<nav class="l-hub" aria-label="Resources"><p class="l-hubname">'
            f'<a href="{HUB}">Resources</a></p><div class="l-hubtabs">{tabs}</div></nav>')


def head(path, slug, title, lead, secs, base):
    """The article's head: the title, its line, then On this page and Cite
    this page side by side.

    ON THIS PAGE FOLDS INTO THE HEAD (the component plan, approved 9 October
    2026). It was a rail down the right beside the prose, which repeated the
    margin's headings once W4 put them there. It is the first control in the
    row shell.py writes Cite this page into, so app.js's rule of one pane
    open at a time in that row covers both, and every href in it carries the
    page's own path (see HUB above).
    """
    # The page's own address, as it is written: /learn/ or, for the pages
    # that became guides, /guides/ (article_href).
    here = S.canon(path.lstrip("/"))
    items = "".join(f'<li><a href="{E(here)}#{E(sid)}">{_plain(h)}</a></li>'
                    for sid, h, _ in secs)
    otp = ('<details class="l-otp"><summary>On this page</summary>'
           f'<nav class="l-otpb" aria-label="On this page"><ol>{items}</ol></nav></details>')
    acts = S.cite_block(path, title, base, S.BUILT)
    row = '<div class="pageacts" id="pageacts">'
    assert acts.startswith(row), "shell.cite_block no longer opens with the row"
    acts = row + otp + acts[len(row):]
    return (f'<header class="l-head"><h1>{E(title)}</h1>'
            + (f'<p class="l-lead">{lead}</p>' if lead else "")
            + acts + "</header>")


def pager(i, topics):
    """Previous Topic on the left, Next Topic on the right, each with its
    title under it, and All Topics between them back to the hub's Learn tab
    (previous-left-next-right; Title Case, item 17). The markup is in the
    order it is drawn, so the keyboard meets them the same way round. The
    first topic has no previous and the last no next: an empty cell keeps
    the other where it belongs."""
    def side(k, cls, word):
        if k is None or not 0 <= k < len(topics):
            return f'<span class="{cls}"></span>'
        t = topics[k]
        return (f'<a class="{cls}" href="{E(learn_href(t["slug"]))}"><span class="l-pgw">{word}</span>'
                f'<span class="l-pgd">{E(t["title"])}</span></a>')
    return ('<nav class="l-pager" aria-label="Other topics">'
            + side(None if i is None else i - 1, "l-pgp", "Previous Topic")
            + f'<a class="l-pgm" href="{HUB}#learn">All Topics</a>'
            + side(None if i is None else i + 1, "l-pgn", "Next Topic") + "</nav>")


def guides_foot():
    """The foot of a page that became a guide (civics.HOW_TO): no Previous or
    Next Topic, since it is no longer one of Learn's pages read in order, and
    the way back to every guide where All Topics stood."""
    return ('<nav class="l-pager" aria-label="Other guides"><span class="l-pgp"></span>'
            f'<a class="l-pgm" href="{HUB}#guides">All How-To Guides</a>'
            '<span class="l-pgn"></span></nav>')


def all_topics(topics, here=None):
    """The thirteen pages at the foot of each, in the hub's two groups, with
    the one open marked: a reader inside the section needs a way across it,
    and this was the rail down the right of every page."""
    n = len(topics)
    groups = []
    for group, _note in civics.GROUPS:
        lis = "".join(
            f'<li><span aria-current="page">{E(t["title"])}</span></li>' if t["slug"] == here
            else f'<li><a href="{E(learn_href(t["slug"]))}">{E(t["title"])}</a></li>'
            for t in topics if t["group"] == group)
        if lis:
            groups.append(f'<div><h3>{E(group)}</h3><ol>{lis}</ol></div>')
    return ("all-topics", f"The {NUMBER_WORD.get(n, n)} Pages",
            f'<nav class="l-all" aria-label="The pages of this section">{"".join(groups)}</nav>')


def learn_page(tmpl, *, slug, title, lead, description, secs, foot, base, after=None,
               hub="learn"):
    """A Learn article: the Resources bar, the head, the sections, the pager
    (foot) and, after it, The Thirteen Pages (after). A page that became a
    guide (civics.HOW_TO) is drawn the same way at its /guides/ address, with
    How-To Guides marked on the bar (`hub`)."""
    path = "/" + article_href(slug)
    p = S.page(tmpl, path=path, base=base,
               # THE SITE'S NAME LAST, on every page; the section is worth
               # naming, so it goes in front of the brand rather than instead.
               title=S.title_of(title, "Learn" if hub == "learn" else "How-To Guides"),
               og_title=title, description=description,
               og_image="og-learn.png", og_alt=OG_ALT,
               globals={"GR_STATIC": True}, noscript="",
               skip_label="Skip to the page", sr_title="",
               nav_current="resources.html", cite=False)
    every = secs + ([after] if after else [])
    article = ("".join(section(*s) for s in secs) + foot
               + (section(*after) if after else ""))
    out = p.replace('<div id="results"></div>',
                    '<div id="results"><div class="l-page">' + hub_bar(hub)
                    + head(path, slug, title, lead, every, base)
                    + f'<div class="l-art">{article}</div></div>{OTP_JS}</div>', 1)
    if "[[" in out:
        raise SystemExit(f"{path} would publish an unfilled figure: "
                         + out[out.index("[["):out.index("[[") + 40])
    return out


# ON THIS PAGE CLOSES when one of its links is chosen, on a click outside it,
# or on Escape (focus back on its button), as the approved prototype's does.
# Inline, after the page, so it needs no file of its own; a page read without
# JavaScript has a <details> that opens and closes by itself.
OTP_JS = """<script>
(function(){
  var d=document.querySelector(".l-otp");
  if(!d)return;
  document.addEventListener("click",function(e){
    if(!d.open)return;
    if(e.target.closest(".l-otpb a")||!e.target.closest(".l-otp"))d.open=false;
  });
  document.addEventListener("keydown",function(e){
    if(e.key==="Escape"&&d.open){d.open=false;d.querySelector("summary").focus();}
  });
  // Common Questions print open (civics.faq).
  window.addEventListener("beforeprint",function(){
    document.querySelectorAll(".l-faq details").forEach(function(x){x.open=true;});
  });
  // The same list beside the page, where app.css gives it a column
  // (.l-sidewrap), the section being read marked as the reader scrolls.
  var page=document.querySelector(".l-page"),src=d.querySelector(".l-otpb");
  if(!page||!src)return;
  var wrap=document.createElement("div"),nav=document.createElement("nav"),h=document.createElement("p");
  wrap.className="l-sidewrap";nav.className="l-side";
  nav.setAttribute("aria-label",src.getAttribute("aria-label")||"On this page");
  h.className="l-sidehead";h.textContent=d.querySelector("summary").textContent;
  nav.appendChild(h);nav.appendChild(src.querySelector("ol").cloneNode(true));
  wrap.appendChild(nav);page.insertBefore(wrap,page.firstChild);
  var links={};
  nav.querySelectorAll("a").forEach(function(a){var i=a.href.indexOf("#");if(i>=0)links[decodeURIComponent(a.href.slice(i+1))]=a;});
  var secs=[].slice.call(document.querySelectorAll(".l-art > .l-sec[id]")).filter(function(s){return links[s.id];});
  if(!secs.length||!("IntersectionObserver" in window))return;
  var cur=null;
  function mark(){
    var y=window.innerHeight*0.25,best=secs[0];
    secs.forEach(function(s){if(s.getBoundingClientRect().top<=y)best=s;});
    if(best===cur)return;
    if(cur)links[cur.id].removeAttribute("aria-current");
    cur=best;links[cur.id].setAttribute("aria-current","location");
  }
  var io=new IntersectionObserver(mark,{rootMargin:"0px 0px -75% 0px"});
  secs.forEach(function(s){io.observe(s);});
  window.addEventListener("scroll",mark,{passive:true});mark();
})();
</script>"""


# ---------------------------------------------------------------------------
# THE HUB'S THREE TABS.
# ---------------------------------------------------------------------------

# THE THREE PAGES MOST PEOPLE WANT, as cards above the lists. Thirteen equal
# rows made the reader choose before they knew what they were choosing
# between, and the answer is nearly always one of three: how a bill becomes
# law is the spine everything else hangs off, the General Court answers "who
# are they", and testifying is the one page that tells a reader they can do
# something. Each is listed once: the lists below leave these out.
#
# THE LEGISLATURE'S YEAR, WHERE TESTIFYING STOOD (17 October 2026).
# Testifying and Attending is a how-to guide now (civics.HOW_TO), so Learn's
# third card is the page that lays the course of a bill on the calendar; the
# guides that tell a reader what they can do are on the How-To Guides tab.
START = [("how-a-bill-becomes-law",
          "The course a bill runs, and the stages it can die at."),
         ("general-court",
          "The 400 representatives and 24 senators, and how a two-year term is shaped."),
         (legislative_year.SLUG,
          "When bills are filed, when the House and Senate sit, and the deadlines between.")]


def official_sources(extra=()):
    """[(group, [(name, url, meta)])]: every outside source a Learn page cites,
    grouped by who publishes it (civics.SOURCE_GROUPS), and then the Secretary
    of State's results pages The Record in Numbers cites (`extra`, read from
    the rows its table shows). A source a page cites that is in no group and
    not set aside as unofficial stops the build, so a page cannot cite a
    source the hub forgets."""
    cited = {u for t in civics.TOPICS for _, u in t["sources"] if u.startswith("http")}
    grouped = [u for _, srcs in civics.SOURCE_GROUPS for _, u in srcs]
    left = sorted(cited - set(grouped) - {u for _, u in civics.NOT_OFFICIAL})
    if left:
        raise SystemExit("a Learn page cites a source the Resources hub lists nowhere: "
                         + ", ".join(left) + " (civics.SOURCE_GROUPS)")
    stale = sorted(set(grouped) - cited)
    if stale:
        raise SystemExit("civics.SOURCE_GROUPS lists a source no Learn page cites: "
                         + ", ".join(stale))

    def row(label, u):
        # "Guidance for towns and cities (New Hampshire Municipal Association,
        # a membership body)": the bracket is what the source is, said beside it
        m = re.match(r"^(.*?) \((.*)\)$", label)
        host = re.sub(r"^https?://(?:www\.)?([^/]+).*$", r"\1", u)
        meta = (m.group(2) if m else host + (" &middot; PDF" if u.lower().endswith(".pdf") else ""))
        return (E(m.group(1) if m else label), u, E(html.unescape(meta)) if m else meta)
    out = []
    for group, srcs in civics.SOURCE_GROUPS:
        rows = [row(label, u) for label, u in srcs]
        if group == civics.ELECTIONS_GROUP:
            rows += [(E(label), u, "sos.nh.gov") for label, u in extra]
        out.append((group, rows))
    return out


def numbers_results(root):
    """[(label, url)]: the Secretary of State's own results pages that the
    page of numbers cites for the amendments the voters decided, in the order
    of the elections, each once ("2024 general election results")."""
    rows = _load(Path(root) / "corrections" / "ballot_results.json", {}).get("rows") or []
    shown, _held, _to_come = learn_numbers.ballots(rows)
    out, seen = [], set()
    for r in sorted(shown, key=lambda r: r.get("election") or "", reverse=True):
        u = r.get("source") or ""
        if re.match(r"https?://(?:www\.)?sos\.nh\.gov/", u) and u not in seen:
            seen.add(u)
            out.append((re.sub(r",\s*sos\.nh\.gov\s*$", "", r.get("cite") or u), u))
    return out


def hub_section(sid, heading, content):
    return section(sid, heading, content, level=3)


# THE RESOURCES HUB'S TOPICS, EACH WITH A PICTURE (the person, 24 October
# 2026: "the visuals could use another pass ... maybe adding icons for each
# topic?"). One drawing per topic, in the line the nav's icons are drawn in
# (components.ICON_PAINT), on a round badge beside the topic's name. Every
# drawing is components.icon's, as every icon on the site must be: the ones
# the hub added are in components.ICONS with the nav's, and in components.js,
# which preflight holds to it byte for byte. Each is aria-hidden: the topic's
# name beside it is what a screen reader reads.
# A card's own picture where its topic's would mislead -- a car beside moving
# to New Hampshire -- by the slug of the guide or page it links.
CARD_ICON = {
    "how-to-vote": "ballot", "renew-drivers-license": "idcard", "register-a-car": "car",
    "your-representatives": "person", "submit-testimony": "testify",
    "new-to-new-hampshire": "box", "food-and-health-assistance": "heart",
    "how-a-bill-becomes-law": "bill", "general-court": "capitol", "legislative-year": "calendar",
}
# Each topic's picture, by the name the tab heads it with.
TOPIC_ICON = {
    # the How-To Guides tab (guides.TASKS)
    "Take Part in the Legislature": "testify", "Voting and Elections": "ballot",
    "Driving and Vehicles": "car", "Help and Benefits": "heart", "Property and Records": "house",
    "Federal Benefits": "idcard", "Know Your Rights": "law",
    "Outdoors and Recreation": "tree",
    "Around Your Town": "pin", "Visiting the State House": "capitol", G.MORE: "grid",
    # the Learn tab (civics.GROUPS, and what follows them)
    "How the State Works": "columns", "How to Take Part": "testify", "Taking Part": "testify",
    "Start Here": "signpost", NUMBERS_TITLE: "chart", GLOSSARY_TITLE: "book", "Laws (RSA)": "law",
    # the Official Sources tab (official_sources' groups)
    "The General Court": "capitol", "The Governor and State Agencies": "columns",
    "The Courts": "gavel", "Elections and the Constitution": "ballot", "Towns and Counties": "map",
    "Other Ways to Follow New Hampshire Legislation": "follow",
}


def badge(name):
    """The picture for `name` -- a topic's name, or a drawing's own key -- on
    its round badge, or a book where there is none, hidden from screen
    readers."""
    key = TOPIC_ICON.get(name, name)
    return f'<span class="g-ic">{C.icon(key if key in C.ICONS else "book")}</span>'


def fold(fid, name, label, count, body):
    """One topic of a Resources tab, folded shut: a <details> whose summary is
    its badge (by `name`, the English topic), its `label` as the page prints
    it, and how many it holds, and whose body is `body`. Opened by its
    heading, with or without a script."""
    return (f'<details class="g-topic" id="{fid}"><summary>{badge(name)}'
            f'<span class="g-tname">{label}</span> <span class="g-tn">({count})</span></summary>'
            f'<div class="g-body">{body}</div></details>')


def cards(items):
    """A row of short cards, each a link with its topic's badge, a title and,
    where given, a line: [(href, topic name, title html, line html)]."""
    return ('<ul class="g-cards">' + "".join(
        f'<li><a href="{E(h)}">{badge(n)}<span class="g-ct"><b>{t}</b>'
        + (f'<span>{dashes(line)}</span>' if line else "") + '</span></a></li>'
        for h, n, t, line in items) + "</ul>")


# THE LEARN AND OFFICIAL SOURCES TABS IN EVERY LANGUAGE (the person, 25
# October 2026: "Go ahead with the spanish versions of the learn and sources
# tabs"). The tabs' own words -- a heading, a line, a topic's title and
# description, a source's label -- are written once, here and in civics.py,
# and said in the page's language from the catalog (hub_words lists every one
# for i18n.code_words); the names of the sites and of the trackers are their
# own and stay as they are. The Learn pages and the official sites are in
# English, and each tab says so once at its top.
FOLLOW_HEADING = "Other Ways to Follow New Hampshire Legislation"


HUB_FIXED = {
    "hub.learn.intro": ("{n} short pages on the parts of state and local government, each one "
                        "linked to where you can watch it happening in the record."),
    "hub.learn.start": "Start Here",
    "hub.learn.by_topic": "By Topic",
    "hub.learn.reference": "Reference",
    "hub.learn.numbers_title": NUMBERS_TITLE,
    "hub.learn.numbers_line": curly(NUMBERS_WHAT[0].upper() + NUMBERS_WHAT[1:]) + ".",
    "hub.learn.glossary_title": GLOSSARY_TITLE,
    "hub.learn.glossary_line": "The record&rsquo;s words and abbreviations, A to Z.",
    "hub.learn.in_english": ("The Learn pages are in English; their names and descriptions are "
                             "given here in this page&rsquo;s language."),
    "hub.learn.some_english": ("A page marked &ldquo;in English&rdquo; is not translated yet; its "
                               "name and description are given here in this page&rsquo;s "
                               "language."),
    "hub.src.intro": "The sites the Learn pages cite as their sources. Each opens in a new tab.",
    "hub.src.by_branch": "By Branch",
    "hub.src.in_english": "The official sites are in English.",
    "hub.src.close": ('Every page here ends with its sources. If something is wrong, '
                      '<a href="mailto:contact@graniterecord.org">tell us</a> &mdash; that address '
                      'exists for this.'),
    "hub.follow.heading": FOLLOW_HEADING,
    "hub.follow.official": "From the legislature itself:",
    "hub.follow.independent": ("And from independent sites, run apart from the General Court and "
                               "from Granite Record, in alphabetical order:"),
}


def _tw(lang, key, en):
    """`en`, the tabs' own words, in `lang`: the English for English, the
    catalog's where it is current, and the English marked as English where it
    is not."""
    if lang == I.DEFAULT:
        return en
    got = I.say_piece(lang, key, I.norm(en))
    return got if got is not None else f'<span lang="en">{en}</span>'


def _hf(lang, key):
    return _tw(lang, key, HUB_FIXED[key])


def _src_label(label):
    """A source's label as the tab shows it: its name, and what it is where
    the label says so in brackets ("Guidance for towns and cities (New
    Hampshire Municipal Association, a membership body)")."""
    m = re.match(r"^(.*?) \((.*)\)$", label)
    return (E(m.group(1)), E(html.unescape(m.group(2)))) if m else (E(label), None)


def hub_words():
    """[(key, English, where)] of every word the Learn and Official Sources
    tabs say in their own words, for i18n.code_words: HUB_FIXED, each Learn
    page's title and description, the groups and their notes, Start Here's
    lines, the source groups and labels, and the trackers' lines."""
    where = "the Resources hub"
    out = [(k, I.norm(v), where) for k, v in HUB_FIXED.items()]
    for t in learn_topics(civics.TOPICS):
        out += [(f"hub.learn.{t['slug']}.title", I.norm(E(t["title"])), where),
                (f"hub.learn.{t['slug']}.blurb", I.norm(E(t["blurb"])), where)]
    for group, note in civics.GROUPS:
        k = f"hub.learn.group.{I.slug_words(group)}"
        out += [(k + ".name", I.norm(E(group)), where), (k + ".note", I.norm(E(note)), where)]
    out += [(f"hub.learn.{slug}.why", I.norm(E(why)), where) for slug, why in START]
    for group, srcs in civics.SOURCE_GROUPS:
        out.append((f"hub.src.group.{I.slug_words(group)}", I.norm(E(group)), where))
        for label, _u in srcs:
            name, what = _src_label(label)
            k = f"hub.src.{I.slug_words(html.unescape(name))}"
            out.append((k + ".name", I.norm(name), where))
            if what:
                out.append((k + ".what", I.norm(what), where))
    for name, _u, line in civics.FOLLOW_OFFICIAL + civics.FOLLOW_INDEPENDENT:
        out.append((f"hub.follow.{I.slug_words(name)}.line", I.norm(line), where))
    seen, uniq = set(), []
    for row in out:
        if row[0] not in seen:
            seen.add(row[0])
            uniq.append(row)
    return uniq


def hub_learn(topics, lang=I.DEFAULT):
    """The Learn tab, in English or in `lang` (24 October 2026, the person's
    second pass on the hub's look): Start Here as three cards; each of
    civics.GROUPS folded shut under its badge; then the reference pages --
    The Record in Numbers and the Glossary -- as cards of their own, since
    they are looked things up in rather than read in order."""
    by_slug = {t["slug"]: t for t in topics}
    n = len(topics)

    # A LEARN PAGE NOT YET IN THE LANGUAGE SAYS SO (25 October 2026): the
    # pages are translated a few at a time, and the link to one still in
    # English goes to the English page (lang_links), so its name carries
    # "in English" and the note above the list says what that means.
    done = set(G.learn_translated(lang)) if lang != I.DEFAULT else set()
    english = "" if lang == I.DEFAULT else (
        '<span class="r-en">(' + I.say(lang, "guides.in_english", "in English") + ")</span>")

    def title(slug):
        return (_tw(lang, f"hub.learn.{slug}.title", E(by_slug[slug]["title"]))
                + ("" if lang == I.DEFAULT or slug in done else english))
    start = cards([(learn_href(slug), CARD_ICON.get(slug, "Start Here"), title(slug),
                    _tw(lang, f"hub.learn.{slug}.why", E(why)))
                   for slug, why in START if slug in by_slug])
    started = {slug for slug, _ in START}
    count = NUMBER_WORD.get(n, n) if lang == I.DEFAULT else str(n)
    out = [f'<p class="r-intro">{_hf(lang, "hub.learn.intro").replace("{n}", str(count))}</p>']
    if lang != I.DEFAULT and not done & set(by_slug):
        out.append(f'<p class="langnote">{_hf(lang, "hub.learn.in_english")}</p>')
    elif lang != I.DEFAULT and set(by_slug) - done:
        out.append(f'<p class="langnote">{_hf(lang, "hub.learn.some_english")}</p>')
    out.append(hub_section("start", _hf(lang, "hub.learn.start"), start))
    folds = []
    for group, note in civics.GROUPS:
        mine = [t for t in topics if t["group"] == group and t["slug"] not in started]
        k = f"hub.learn.group.{I.slug_words(group)}"
        lis = "".join(
            f'<li><a href="{E(learn_href(t["slug"]))}">{title(t["slug"])}</a>'
            f'<p>{dashes(_tw(lang, "hub.learn." + t["slug"] + ".blurb", E(t["blurb"])))}</p></li>'
            for t in mine)
        if lis:
            folds.append(fold("s-" + _slug(group), group, _tw(lang, k + ".name", E(group)), len(mine),
                              f'<p class="r-intro">{_tw(lang, k + ".note", E(note))}</p>'
                              f'<ul class="r-topics">{lis}</ul>'))
    out.append(hub_section("s-topics", _hf(lang, "hub.learn.by_topic"), "".join(folds)))
    # NOT ONE OF THE NUMBERED PAGES. The topics are short explanations meant
    # to be read in order; these are looked things up in, for a different
    # reader, so they sit after them as cards of their own.
    ref = [(learn_href(NUMBERS_SLUG), NUMBERS_TITLE, _hf(lang, "hub.learn.numbers_title"),
            _hf(lang, "hub.learn.numbers_line")),
           (learn_href(GLOSSARY_SLUG), GLOSSARY_TITLE, _hf(lang, "hub.learn.glossary_title"),
            _hf(lang, "hub.learn.glossary_line"))]
    # NO TAKING PART, NO LAWS CARD (the hub audit, 25 October 2026): the tab's
    # count was of seventeen links, four of them repeats -- the three guides
    # Taking Part named, which the How-To Guides tab lists, and the Laws, which
    # the header names on every page. Learn's pages still name the guides that
    # do what they explain (civics.GUIDES_FOR).
    out.append(hub_section("reference", _hf(lang, "hub.learn.reference"), cards(ref)))
    return "".join(out)


def guides_tab(lang, published=(), articles=()):
    """The How-To Guides tab, in English or in `lang` (the person, 24 October
    2026: guides.COMMON says why): a search that suggests guides as a reader
    types what they need, in their own words; the most common errands; and
    every guide under guides.TASKS' groups, each group folded shut and each
    guide by its short headline ("How to vote") with its line under it. One
    function for every language, so the English tab and the Spanish one can
    never be laid out differently.

    WITHOUT JAVASCRIPT the search is a form that asks the site's own search
    (/search?q=), and every group opens when its heading is pressed, so nothing
    on the tab needs the script. The suggestions read a list of the tab's
    guides written into the page (GFIND_JS says how they are ranked)."""
    en = lang == I.DEFAULT
    here = {g["slug"]: g for g in published}
    here.update({t["slug"]: t for t in articles})

    def said(key, text, plain=False):
        got = I.say_piece(lang, key, I.norm(text))
        if got is not None:
            return E(got) if plain else got
        return f'<span lang="en">{E(text) if plain else text}</span>'

    def href(slug):
        return E(guide_href(slug) if en else I.href(lang, guide_href(slug)))

    def bare(h):
        return html.unescape(re.sub(r"<[^>]+>", "", h))

    rows, listed = [], set()
    for group, tasks in G.TASKS:
        listed |= {t["slug"] for t in tasks}
        gname = said(f"guide.group.{I.slug_words(group)}", group, plain=True)
        for t in tasks:
            if t["slug"] in here:
                k = f"guide.task.{t['slug']}"
                rows.append((group, gname, t["slug"], said(k + ".head", t["head"]),
                             said(k + ".line", t["line"]), t))
    for g in published:
        if g["slug"] not in listed:
            w = Words(lang, g["slug"])
            rows.append((G.MORE, said("guide.group.more", G.MORE, plain=True), g["slug"],
                         w.t(g["title"]), w.t(g["blurb"]), None))
    if not rows:
        return None

    # THE SEARCH. A form first, so it works with no script at all.
    find = ('<form class="g-find" role="search" action="/search" method="get">'
            '<label for="gfind">' + I.say(lang, "guides.find_label", "What do you need to do?")
            + '</label><div class="g-findbox"><input id="gfind" name="q" type="search" '
            'autocomplete="off" spellcheck="false" aria-describedby="gfind-status" placeholder="'
            + E(html.unescape(I.say(lang, "guides.find_hint",
                                    "For example: renew my license")))
            + '"><ul id="gfind-list" class="g-findlist" role="listbox" aria-label="'
            + E(html.unescape(I.say(lang, "guides.find_list", "Suggested guides")))
            + '" hidden></ul></div><p id="gfind-status" class="g-findstat" aria-live="polite">'
            '</p></form>')
    # MOST COMMON, by headline, as a row of short boxes.
    by_slug = {r[2]: r for r in rows}
    common = "".join(f'<li><a href="{href(s)}">{badge(CARD_ICON.get(s, by_slug[s][0]))}'
                     f'<span>{by_slug[s][3]}</span></a></li>'
                     for s in G.COMMON if s in by_slug)
    # EVERY GUIDE BY TOPIC, each group a <details> shut until opened.
    topics, order = [], []
    for r in rows:
        if r[0] not in order:
            order.append(r[0])
    for group in order:
        mine = [r for r in rows if r[0] == group]
        lis = "".join(f'<li><a href="{href(r[2])}">{r[3]}</a><span>{dashes(r[4])}</span></li>'
                      for r in mine)
        topics.append(fold(f"g-{_slug(group)}", group, mine[0][1], len(mine),
                           f'<ul class="g-list">{lis}</ul>'))
    # What the suggestions read: each guide's headline and line as shown, and
    # every word it is known by, in English and, on another language's tab,
    # in that language too, so a reader may type either.
    data = []
    for group, gname, slug, head, line, t in rows:
        g = here.get(slug)
        words = [group, bare(head), bare(line), " ".join(G.WORDS.get(slug, ()))]
        if t:
            words += [t["does"], t["head"], t["line"]]
        if g is not None and "title" in g:
            words += [g["title"], g.get("blurb", "")]
        data.append({"h": href(slug).replace("&amp;", "&"), "t": bare(head), "l": bare(line),
                     "k": bare(" ".join(words))})
    strings = {
        "one": html.unescape(I.say(lang, "guides.find_one", "1 guide matches")),
        "many": html.unescape(I.say(lang, "guides.find_many", "{n} guides match")),
        "none": html.unescape(I.say(lang, "guides.find_none",
                                    "No guide matches. Press Enter to search the whole site.")),
        "all": html.unescape(I.say(lang, "guides.find_all", "Search the whole site for “{q}”")),
    }
    blob = json.dumps({"s": strings, "g": data}, ensure_ascii=False).replace("</", "<\\/")
    intro = ('<p class="r-intro">' + I.say(
        lang, "guides.hub_intro", "Step-by-step help with things people do with the state, and with "
        "taking part in the legislature. Each step-by-step guide links the official page that has the "
        "final word, and says when it was last checked against it.") + "</p>")
    return (intro + find
            + hub_section("g-common", I.say(lang, "guides.common", "Most Common"),
                          f'<ul class="g-common">{common}</ul>')
            + hub_section("g-topics", I.say(lang, "guides.by_topic", "All Guides by Topic"),
                          "".join(topics))
            + f'<script type="application/json" id="gfind-data">{blob}</script>' + GFIND_JS)


# THE GUIDE SEARCH'S SUGGESTIONS (guides_tab). A reader types what they need
# in their own words -- "how to get updated driver's license" -- and the
# guides are ranked by how many of the words that matter they share: the
# little words (how, to, my, the; cómo, para, mi) are dropped, a word is cut
# to its stem ("drivers", "renewing", "testifying"), a few words are read as
# the word the guides use ("updated" as renew, "testimony" as testify), and a
# word still being typed matches the start of one. A word in a guide's
# headline counts three, in the words it is known by two, in its line one.
# Arrow keys move through the suggestions, Enter opens one, or the first, or,
# with none, asks the site's search; Escape closes them. The last suggestion
# is always the site's search for what was typed.
GFIND_JS = """<script>
(function(){
  var box=document.getElementById("gfind"), list=document.getElementById("gfind-list"),
      stat=document.getElementById("gfind-status"), src=document.getElementById("gfind-data");
  if(!box||!list||!src)return;
  var D=JSON.parse(src.textContent), S=D.s, G=D.g, act=-1, opts=[];
  var STOP={};
  ("a an the to how do does i im my me can could get for of in on is it its what where when who "
   +"and or with need want about your you be am are we our at from as by this that should "
   +"como de del la el los las un una mi mis para que en y o con por se puedo quiero necesito "
   +"sobre su sus al lo le hacer").split(" ").forEach(function(w){STOP[w]=1;});
  var SYN={updat:"renew",renewal:"renew",expir:"renew",licence:"license",testimony:"testify",
    testimoni:"testify",testif:"testify",dump:"transfer",garbage:"trash",rubbish:"trash",
    homeles:"homeless",evict:"eviction",daycare:"child",childcare:"child",snap:"food",
    rep:"representative",reps:"representative",sen:"senator"};
  function norm(s){return String(s||"").toLowerCase().normalize("NFD")
    .replace(/[\\u0300-\\u036f]/g,"").replace(/['\\u2019]/g,"").replace(/[^a-z0-9]+/g," ").trim();}
  function stem(w){
    if(SYN[w])return SYN[w];
    if(w.length>5&&/ies$/.test(w))w=w.slice(0,-3)+"y";
    else if(w.length>5&&/ing$/.test(w))w=w.slice(0,-3);
    else if(w.length>4&&/ed$/.test(w))w=w.slice(0,-2);
    else if(w.length>3&&/s$/.test(w)&&!/ss$/.test(w))w=w.slice(0,-1);
    return SYN[w]||w;
  }
  function toks(s){var o=[];norm(s).split(" ").forEach(function(w){if(w&&!STOP[w])o.push(stem(w));});return o;}
  G.forEach(function(g){
    g.w={};
    [[g.t,3],[g.k,2],[g.l,1]].forEach(function(p){
      toks(p[0]).forEach(function(w){if(!(g.w[w]>=p[1]))g.w[w]=p[1];});
    });
  });
  function score(g,q){
    var s=0,hit=0;
    q.forEach(function(w){
      var best=g.w[w]||0;
      if(!best&&w.length>=3){for(var k in g.w){if(k.indexOf(w)===0&&g.w[k]*0.8>best)best=g.w[k]*0.8;}}
      if(best){s+=best;hit++;}
    });
    return hit?s+(hit===q.length?2:0):0;
  }
  function pick(i){
    opts.forEach(function(li,k){li.setAttribute("aria-selected",k===i?"true":"false");});
    act=i;
    if(i>=0){box.setAttribute("aria-activedescendant",opts[i].id);opts[i].scrollIntoView({block:"nearest"});}
    else box.removeAttribute("aria-activedescendant");
  }
  function close(){list.hidden=true;box.setAttribute("aria-expanded","false");pick(-1);}
  function option(i,href,head,line,cls){
    var li=document.createElement("li"),a=document.createElement("a"),b=document.createElement("b");
    li.id="gfind-o"+i;li.setAttribute("role","option");li.setAttribute("aria-selected","false");
    if(cls)li.className=cls;
    a.href=href;a.tabIndex=-1;b.textContent=head;a.appendChild(b);
    if(line){var sp=document.createElement("span");sp.textContent=line;a.appendChild(sp);}
    li.appendChild(a);list.appendChild(li);return li;
  }
  var found=[];
  function draw(){
    var raw=box.value.trim();
    list.innerHTML="";opts=[];act=-1;
    if(!raw){close();stat.textContent="";return;}
    var q=toks(raw);
    found=G.map(function(g){return [q.length?score(g,q):0,g];})
      .filter(function(x){return x[0]>0;})
      .sort(function(a,b){return b[0]-a[0]||a[1].t.length-b[1].t.length;}).slice(0,6);
    found.forEach(function(x,i){opts.push(option(i,x[1].h,x[1].t,x[1].l));});
    opts.push(option(found.length,"/search?q="+encodeURIComponent(raw),
      S.all.replace("{q}",raw),"","g-findall"));
    list.hidden=false;box.setAttribute("aria-expanded","true");
    stat.textContent=found.length?(found.length===1?S.one:S.many.replace("{n}",found.length)):S.none;
  }
  box.setAttribute("role","combobox");box.setAttribute("aria-autocomplete","list");
  box.setAttribute("aria-controls","gfind-list");box.setAttribute("aria-expanded","false");
  box.addEventListener("input",draw);
  box.addEventListener("focus",function(){if(box.value.trim())draw();});
  box.addEventListener("keydown",function(e){
    if(e.key==="ArrowDown"||e.key==="ArrowUp"){
      if(list.hidden)draw();
      if(!opts.length)return;
      e.preventDefault();
      var n=opts.length,i=e.key==="ArrowDown"?(act+1)%n:(act<=0?n-1:act-1);
      pick(i);
    }else if(e.key==="Enter"){
      var li=act>=0?opts[act]:(found.length?opts[0]:null);
      if(li){e.preventDefault();location.href=li.querySelector("a").href;}
    }else if(e.key==="Escape"){if(!list.hidden){e.preventDefault();close();}}
  });
  document.addEventListener("click",function(e){if(!e.target.closest||!e.target.closest(".g-findbox"))close();});
})();
</script>"""


def hub_guides(published=(), articles=()):
    """The How-To Guides tab in English (guides_tab): the guides that passed
    guides.py's checks, and the pages that became guides (`articles`,
    civics.HOW_TO).

    WHILE THERE ARE NONE, THE TAB SAYS SO: the list of guides coming stays
    hidden until the first one exists (8 October 2026), and the tab is drawn
    anyway, because the person asked for a tab for each, and points to the
    other two."""
    tab = guides_tab(I.DEFAULT, published, articles)
    if tab:
        return tab
    return ('<p class="r-none">There are no how-to guides yet.</p>'
            '<p class="r-sub">Each guide will be listed here once it is written and checked '
            'against the official sources it cites.</p>'
            '<ul class="r-goto">'
            f'<li><a href="{HUB}#learn"><b>Learn</b><span>How each part of state and local '
            'government works.</span></a></li>'
            f'<li><a href="{HUB}#sources"><b>Official Sources</b><span>The state&rsquo;s own '
            'sites, where its records and services are.</span></a></li></ul>')


# ---------------------------------------------------------------------------
# THE HOW-TO GUIDES (guides.py says what they are and how each is checked).
# A guide is written to /guides/<slug> only when every claim in it is checked
# and every outside address it links is one guide_sources.py reads; --drafts
# writes the rest too, marked, for a person to read, and is never the
# night's.
# ---------------------------------------------------------------------------
GUIDE_DIR = "guides"
LAWS_LINK = re.compile(r'href="/laws/([0-9a-z-]+)')


def guide_href(slug):
    return f"{GUIDE_DIR}/{slug}.html"


def _day(iso):
    import datetime
    return datetime.date.fromisoformat(iso)


def guide_ready(g, fetched, chapters, sections=None):
    """Why the guide may not be published yet, or "" when it may: a claim
    not checked, an outside address the laptop's run does not read (so no
    link check covers it), or a Laws page the statute table does not hold."""
    if G.unchecked(g):
        return f"{len(G.unchecked(g))} of {len(g['claims'])} claims not yet checked"
    loose = [u for u in G.outside(g) if u not in fetched]
    if loose:
        return "not in guide_sources.SOURCES: " + ", ".join(loose)
    laws = set(LAWS_LINK.findall(G.text(g) + " ".join(f'href="{u}"' for _l, u in g["sources"])))
    gone = sorted(c for c in laws if c.upper() not in chapters)
    if gone:
        return "links a Laws page the statute table does not hold: " + ", ".join(gone)
    # A FIGURE ONLY AS THE LAW STATES IT, AND ONLY WHILE IT STILL DOES (the
    # person, 12 October 2026). Every dollar or percentage printed is a
    # guides.fig, and its section's words are found in this build's table.
    loose = G.unbacked(g)
    if loose:
        return "prints a figure no statute it cites is checked for: " + ", ".join(loose)
    # A COUNT ON A CLAIM OF THE GUIDE'S OWN (guides.COUNT, 23 October 2026):
    # its words are the claim's, not a section's, and fig_faults holds them.
    wrong = G.fig_faults(g)
    if wrong:
        return "a figure does not rest on what it cites: " + wrong[0]
    for f in g.get("figures") or []:
        if not f["ref"].startswith("RSA "):
            continue
        m = re.match(r"RSA ([0-9A-Z-]+):([0-9a-z-]+)", f["ref"])
        sec = (sections or {}).get(f"{m.group(1)}:{m.group(2)}") if m else None
        said = re.sub(r"\s+", " ", (sec.text if sec else "") or "")
        if f["says"] not in said:
            return (f'{f["ref"]} no longer says "{f["says"]}", which its figure {f["text"]} '
                    "rests on: check the figure against the law before publishing")
    return ""


def guide_record(g, data, bills, chapters, lang=I.DEFAULT):
    """IN THE RECORD: what the legislature is doing to the law the guide
    describes, by rule and without a word about it -- the bills now moving
    that would change its chapters, and the laws that changed them most
    recently, each with its chapter's own page. The plan: "here is how the
    program works, and here is the legislature changing it".

    In another language the sentences are translated and the record's own
    words -- a chapter's name, a bill's number and status -- are printed as
    the record has them, marked lang="en" (i18n.py, the first kind)."""
    if lang != I.DEFAULT:
        return _record_lang(guide_record(g, data, bills, chapters), lang)
    import build_rsa as BR
    rows = []
    pend = BR.chapter_pending(data, bills)
    # PASSED IS NOT PENDING (the audit before the November webinar, 25
    # October 2026: guides listed laws already passed under "Bills now before
    # the General Court"). chapter_pending holds both, as the Laws page's
    # Pending does; a guide says them apart, the passed ones under the Laws
    # page's own words, "Passed, not yet in effect", and out of the laws that
    # changed the chapter, which they have not yet done.
    passing = set(bills.passing(data))
    for ch in g["laws"]:
        if ch not in chapters:
            continue
        name = BR.chapter_label(ch, chapters[ch]["name"])
        now = [k for k in pend.get(ch, []) if k not in passing]
        passed = [k for k in pend.get(ch, []) if k in passing]
        recent = {}
        for addr, hist in data.get("enacted", {}).items():
            if addr == ch or addr.startswith(ch + ":"):
                for y, _law, b in hist:
                    if b and b not in passing and str(y).isdigit() and int(y) >= RECENT_FROM:
                        recent[b] = int(y)
        past = sorted(recent, key=lambda k: (-recent[k], BR.bill_order(k)))[:RECENT_SHOWN]
        bits = [f'<h3 class="g-ch"><a href="{E(BR.chapter_path(ch))}">{E(name)}</a></h3>']
        if now:
            bits.append('<p class="g-what">Bills now before the General Court that would change it:</p>'
                        + BR.folded([bills.chip(k) for k in now]))
        if passed:
            bits.append('<p class="g-what">Passed, not yet in effect:</p>'
                        + BR.folded([bills.chip(k) for k in passed]))
        if past:
            bits.append(f'<p class="g-what">Laws that changed it since {RECENT_FROM}, newest first:</p>'
                        + BR.folded([bills.chip(k) for k in past]))
        if not now and not passed and not past:
            bits.append(f'<p class="g-what">No bill has changed it since {RECENT_FROM}, and none now '
                        'before the General Court would.</p>')
        rows.append("".join(bits))
    return "".join(rows)


RECENT_FROM = 2020
RECENT_SHOWN = 8


def _record_lang(english, lang):
    """In the Record (guide_record) in `lang`: its sentences translated, the
    chapters' names and the bills' lists marked as the record's English."""
    if not english:
        return english
    now = I.say(lang, "guides.rec_now", "Bills now before the General Court that would change it:")
    since = I.say(lang, "guides.rec_since", "Laws that changed it since {year}, newest first:",
                  year=RECENT_FROM)
    none = I.say(lang, "guides.rec_none", "No bill has changed it since {year}, and none now "
                 "before the General Court would.", year=RECENT_FROM)
    passed = I.say(lang, "guides.rec_passed", "Passed, not yet in effect:")
    out = english.replace(
        '<p class="g-what">Bills now before the General Court that would change it:</p>',
        f'<p class="g-what">{now}</p>').replace(
        '<p class="g-what">Passed, not yet in effect:</p>', f'<p class="g-what">{passed}</p>').replace(
        f'<p class="g-what">Laws that changed it since {RECENT_FROM}, newest first:</p>',
        f'<p class="g-what">{since}</p>').replace(
        f'<p class="g-what">No bill has changed it since {RECENT_FROM}, and none now before the '
        'General Court would.</p>', f'<p class="g-what">{none}</p>')
    out = re.sub(r'<h3 class="g-ch"><a href="([^"]*)">Chapter ([^:<]+)(?:: ([^<]*))?</a></h3>',
                 lambda m: (f'<h3 class="g-ch"><a href="{m.group(1)}">'
                            + I.say(lang, "guides.rec_chapter", "Chapter {n}", n=m.group(2))
                            + (f': <span lang="en">{m.group(3)}</span>' if m.group(3) else "")
                            + "</a></h3>"), out)
    out = re.sub(r"<summary>Show all (\d+)</summary>",
                 lambda m: "<summary>" + I.say(lang, "guides.rec_all", "Show all {n}", n=m.group(1))
                 + "</summary>", out)
    return out.replace('<ul class="rs-list">', '<ul class="rs-list" lang="en">')


class Words:
    """A guide's own words in one language (the owner, 24 October 2026: "The
    how to pages are the next important section I think is worth
    translating."). h(html) is a piece of the page's HTML, t(text) a plain
    text of it (a title, a button's label) escaped for the page. In English
    both are the words as written; in another language each piece is its
    translation where the catalog has one translated from this English
    (i18n.say_html, guides.page_keys), and the English, marked lang="en",
    where it has none -- never words translated from English the page no
    longer says."""

    def __init__(self, lang=I.DEFAULT, slug=""):
        self.lang = lang
        self.keys = G.page_keys(slug) if slug and lang != I.DEFAULT else {}

    def h(self, html_):
        return I.say_html(self.lang, html_, self.keys)

    def t(self, text, attr=False):
        """`text` escaped; in another language its translation, or the
        English in <span lang="en"> (bare where `attr`: an attribute)."""
        if self.lang == I.DEFAULT:
            return E(text)
        en = I.norm(text)
        key = self.keys.get(en)
        got = I.say_piece(self.lang, key, en) if key else None
        if got is not None:
            return E(got)
        if not key:
            I.MISSES.add((self.lang, f"(no key for {en[:50]!r})", "unkeyed"))
        return E(text) if attr else f'<span lang="en">{E(text)}</span>'


def guide_flow(g, w=Words()):
    """THE DIAGRAM: the path through the guide, box to box, a question's
    answers side by side. HTML rather than a picture, so a screen reader
    reads it as the list it is, and it reflows on a phone."""
    items = []
    for node in g["flow"]:
        if node[0] == "box":
            items.append(f'<li class="g-fbox"><span>{w.h(node[1])}</span></li>')
        else:
            answers = "".join(f'<li><b>{w.h(a)}</b><span>{w.h(then)}</span></li>' for a, then in node[2])
            items.append(f'<li class="g-fask"><p class="g-fq">{w.h(node[1])}</p>'
                         f'<ul class="g-fans">{answers}</ul></li>')
    label = (E(g["title"]) + ", in short" if w.lang == I.DEFAULT else
             E(I.say(w.lang, "guides.in_short", "{title}, in short",
                     title=html.unescape(w.t(g["title"], attr=True)))))
    return (f'<figure class="g-flow" role="group" aria-label="{label}">'
            f'<ol>{"".join(items)}</ol></figure>')


def guide_steps(g, w=Words()):
    """THE STEPS, numbered: each one's words, a note set apart where
    something has changed, a button to the official page it needs, and the
    sections of law it rests on, each linked to its place on the Laws
    pages. An outside page is in English (hreflang) on a page in another
    language, which says so once at its top."""
    out = []
    the_law = I.say(w.lang, "guides.the_law", "The law:")
    for s_ in g["steps"]:
        acts = "".join(f'<a class="g-btn" href="{E(u)}"'
                       + ('' if u.startswith("/") else ' target="_blank" rel="noopener"'
                          + ('' if w.lang == I.DEFAULT else ' hreflang="en"'))
                       + f'>{w.t(label)}</a>' for label, u in s_["actions"])
        law = ", ".join(f'<a href="{E(G.law_href(r))}">{E(r)}</a>' for r in s_["law"])
        out.append(f'<li class="g-step"><h3 class="g-sh">{w.t(s_["title"])}</h3>{w.h(s_["text"])}'
                   + (f'<p class="g-note" role="note">{w.h(s_["note"])}</p>' if s_["note"] else "")
                   + (f'<p class="g-acts">{acts}</p>' if acts else "")
                   + (f'<p class="g-law">{the_law} {law}</p>' if law else "") + "</li>")
    return f'<ol class="g-steps">{"".join(out)}</ol>'


def guide_page(tmpl, g, base, record, draft_why=""):
    """A guide: the Resources bar with How-To Guides marked, the head with
    when it was checked, its sections, what the record holds on it, and its
    sources. A check older than guides.STALE_DAYS puts a notice above it."""
    path = "/" + guide_href(g["slug"])
    secs = [("at-a-glance", "At a Glance",
             f'<p class="g-glance">{g["glance"]}</p>' + guide_flow(g)),
            ("steps", "Step by Step", guide_steps(g))]
    if g["more"]:
        secs += split_sections(g["more"], path)
    if record:
        secs.append(("in-the-record", "In the Record", record))
    if g["see"]:
        secs.append(("see-also", "See Also", '<ul class="g-see">' + "".join(
            f'<li><a href="{E(u)}">{E(label)}</a></li>' for label, u in g["see"]) + "</ul>"))
    secs.append(("sources", "Where This Comes From", sources_list(g["sources"])))
    when = G.checked_on(g)
    note = ""
    if draft_why:
        note = (f'<p class="g-draft" role="note"><strong>Draft, not published.</strong> '
                f'{E(draft_why)}.</p>')
    elif when and (build_date.today() - _day(when)).days > G.STALE_DAYS:
        note = ('<p class="g-stale" role="note"><strong>This guide may be out of date.</strong> It was '
                f'last checked {E(C.date_words(_day(when), "full"))}. Check each step against the '
                'official page it links before you rely on it.</p>')
    checked = (f'<p class="g-checked">Checked against its sources '
               f'{E(C.date_words(_day(when), "full"))}.</p>' if when and not draft_why else "")
    # THE STATE IN THE TITLE (the SEO review, 12 October 2026): a reader
    # searches "how to get a public record in NH", and a guide whose name
    # does not already say New Hampshire says it in the title a search
    # result shows. The heading on the page is the guide's own name.
    seo = g["title"] if "New Hampshire" in g["title"] else f'{g["title"]} in New Hampshire'
    p = S.page(tmpl, path=path, base=base, title=S.title_of(seo),
               og_title=seo, description=g["blurb"], og_image="og-learn.png", og_alt=OG_ALT,
               jsonld=None if draft_why else LD.howto(g, base, S.canon(path), when or ""),
               globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the guide", sr_title="",
               nav_current="resources.html", cite=False)
    items = "".join(f'<li><a href="{E(S.canon(path))}#{E(sid)}">{_plain(h)}</a></li>' for sid, h, _ in secs)
    otp = ('<details class="l-otp"><summary>On this page</summary>'
           f'<nav class="l-otpb" aria-label="On this page"><ol>{items}</ol></nav></details>')
    acts = S.cite_block(path, g["title"], base, S.BUILT)
    row = '<div class="pageacts" id="pageacts">'
    assert acts.startswith(row), "shell.cite_block no longer opens with the row"
    acts = row + otp + acts[len(row):]
    headx = (f'<header class="l-head"><h1>{E(g["title"])}</h1><p class="l-lead">{dashes(E(g["blurb"]))}</p>'
             + note + checked + acts + "</header>")
    article = "".join(section(*s_) for s_ in secs)
    return p.replace('<div id="results"></div>',
                     '<div id="results"><div class="l-page g-page">' + hub_bar("guides") + headx
                     + f'<div class="l-art">{article}</div></div>{OTP_JS}</div>', 1)


# ---------------------------------------------------------------------------
# THE HOW-TO GUIDES IN ANOTHER LANGUAGE (the owner, 24 October 2026: "The how
# to pages are the next important section I think is worth translating.").
# Every guide a language has (i18n.PAGES) is written at its English address
# under /<code>/, and the Resources hub's How-To Guides with them, drawn in
# the frame the home page is (build_pages.shell), so the header, the footer
# and Settings are in that language. Each piece of a guide's words is its
# translation where the catalog has one made from the English the guide says
# now, and the English, marked so, where it has not (Words, i18n.say_html);
# the record's own words stay English, and so does every page the guides send
# a reader to outside this site, which the page says once at its top. A link
# to a page the language has goes to that page in it (lang_links).
# ---------------------------------------------------------------------------
def lang_links(html_, lang):
    """`html_` with every link to a page `lang` has (i18n.has) sent to that
    page in `lang`; every other link left as it is, to the English page.
    i18n.lang_links, which the Officials page uses too."""
    return I.lang_links(html_, lang)


def lang_sections(english, translated, where):
    """`translated` cut at its h2s as split_sections cuts a page, each
    section keeping the address its English has, so a link to a section --
    a guide's button to Testifying and Attending's #s-how-hearings-are-
    announced -- reaches it in either language."""
    en, out = split_sections(english, where), split_sections(translated, where)
    if len(en) != len(out):
        raise SystemExit(f"{where}: the translation has {len(out)} sections where the English has "
                         f"{len(en)}")
    return [(eid, h, c) for (eid, _h, _c), (_sid, h, c) in zip(en, out)]


def lang_hub_bar(lang, current="guides"):
    """The Resources bar over a page in `lang`: the hub and its three tabs in
    that language, the one the page belongs to (`current`) marked. All three
    tabs are in the language since 25 October 2026 (hub_tabs), so none is
    sent to the English hub."""
    hub = I.href(lang, HUB_PAGE)
    tabs = "".join(
        f'<a class="l-hubtab" href="{hub}#{tab}"' + (' aria-current="true"' if tab == current else "")
        + f">{name}</a>"
        for tab, name in (("guides", I.say(lang, "guides.hub_guides", "How-To Guides")),
                          ("learn", I.say(lang, "guides.hub_learn", "Learn")),
                          ("sources", I.say(lang, "guides.hub_sources", "Official Sources"))))
    name = I.say(lang, "guides.hub", "Resources")
    return (f'<nav class="l-hub" aria-label="{E(name)}"><p class="l-hubname">'
            f'<a href="{hub}">{name}</a></p><div class="l-hubtabs">{tabs}</div></nav>')


def lang_note(lang):
    """The line under a guide's title in another language: what is in it."""
    return ('<p class="langnote">' + I.say(
        lang, "guides.lang_note", "This guide is in Spanish. The official pages it links to, and "
        "the record itself, are in English.") + "</p>")


def lang_sources(sources, w):
    """Where This Comes From in `w`'s language: each source by its name in
    that language, the page itself as it is (sources_list)."""
    return lang_links(sources_list([(html.unescape(w.t(label, attr=True)), u) for label, u in sources]),
                      w.lang).replace('target="_blank" rel="noopener">',
                                      'target="_blank" rel="noopener" hreflang="en">')


def lang_otp(secs, path, lang):
    """On This Page, in `lang`, for a page drawn in the home page's frame."""
    here = I.href(lang, path)
    items = "".join(f'<li><a href="{E(here)}#{E(sid)}">{_plain(h)}</a></li>' for sid, h, _ in secs)
    on = I.say(lang, "guides.on_page", "On this page")
    return (f'<div class="pageacts" id="pageacts"><details class="l-otp"><summary>{on}</summary>'
            f'<nav class="l-otpb" aria-label="{E(on)}"><ol>{items}</ol></nav></details></div>')


def guide_page_lang(g, lang, base, record=""):
    """The guide `g` in `lang`, written at i18n.href(lang, its page): the
    page guide_page draws, piece by piece in that language, in the home
    page's frame. `record` is In the Record in that language (guide_record)."""
    import build_pages as BP
    page = guide_href(g["slug"])
    w = Words(lang, g["slug"])
    title = w.t(g["title"])
    secs = [("at-a-glance", I.say(lang, "guides.glance", "At a Glance"),
             f'<p class="g-glance">{w.h(g["glance"])}</p>' + guide_flow(g, w)),
            ("steps", I.say(lang, "guides.steps", "Step by Step"), guide_steps(g, w))]
    if g["more"]:
        secs += lang_sections(g["more"], w.h(g["more"]), I.href(lang, page))
    if record:
        secs.append(("in-the-record", I.say(lang, "guides.record", "In the Record"), record))
    if g["see"]:
        secs.append(("see-also", I.say(lang, "guides.see", "See Also"), '<ul class="g-see">' + "".join(
            f'<li><a href="{E(u)}">{w.t(label)}</a></li>' for label, u in g["see"]) + "</ul>"))
    secs.append(("sources", I.say(lang, "guides.sources", "Where This Comes From"),
                 lang_sources(g["sources"], w)))
    when = G.checked_on(g)
    note = ""
    if when and (build_date.today() - _day(when)).days > G.STALE_DAYS:
        note = ('<p class="g-stale" role="note">' + I.say(
            lang, "guides.stale", "<strong>This guide may be out of date.</strong> It was last checked "
            "{date}. Check each step against the official page it links before you rely on it.",
            date=E(C.date_words(_day(when), "full", lang))) + "</p>")
    checked = ('<p class="g-checked">' + I.say(lang, "guides.checked", "Checked against its sources {date}.",
                                                date=E(C.date_words(_day(when), "full", lang)))
               + "</p>" if when else "")
    head_ = (f'<header class="l-head"><h1>{title}</h1>'
             f'<p class="l-lead">{dashes(w.t(g["blurb"]))}</p>' + lang_note(lang) + note + checked
             + lang_otp(secs, page, lang) + "</header>")
    article = lang_links("".join(section(*s_) for s_ in secs), lang)
    body = ('<div class="l-page g-page">' + lang_hub_bar(lang) + head_
            + f'<div class="l-art">{article}</div></div>{OTP_JS}')
    plain = html.unescape(re.sub(r"<[^>]+>", "", title))
    return BP.shell(f"{E(plain)} — Granite Record", page, body,
                    desc=html.unescape(re.sub(r"<[^>]+>", "", w.t(g["blurb"], attr=True))),
                    base=base, lang=lang)


def figures_lang(figures, lang, dist):
    """The figures a page of civics.HOW_TO fills, with those that are words
    rather than a number said in `lang`: the email sentence, the year video
    began, the day the page was built, and the worked example of a town's
    representatives (civics.reps_example)."""
    if lang == I.DEFAULT:
        return figures
    out = dict(figures)
    # The figures record_figures drew again in this language (name@lang).
    for k in [k for k in figures if k.endswith(f"@{lang}")]:
        out[k[:-len(lang) - 1]] = figures[k]
    out["follow_email"] = (
        I.say(lang, "guides.follow_email_live", "A feed needs no account and no email address. "
              "Updates can also come by email: sign up in the same <b>Follow</b> control, and the "
              '<a href="data.html#privacy">Data page</a> says what is kept and for how long.')
        if S.follow_live() else
        I.say(lang, "guides.follow_email_off", "There is no email option yet. No account, no email "
              "address, nothing to leak."))
    if figures.get("hearing_video_since"):
        out["hearing_video_since"] = I.say(lang, "guides.video_since", ", nearly every one since {year}",
                                           year=figures["hearing_video_from"])
    out["built_on"] = C.date_words(build_date.today(), "full", lang)
    if "probate_vote" in figures:
        out["probate_vote"] = probate_vote(
            _load(Path(".") / "corrections" / "ballot_results.json", {}).get("rows"),
            build_date.today(), lang)
    if dist:
        got = civics.reps_example(dist, lang=lang)
        out.update({k: (f"{v:,}" if isinstance(v, int) else v) for k, v in got.items()})
    return out


def article_page_lang(t, lang, base, figures, names=None, con=None):
    """A page of civics.HOW_TO in `lang`, at i18n.href(lang, its page): its
    words piece by piece (Words), the paragraphs guides.SAID writes once
    among them, the shorthand table from the glossary's translations, and
    the figures filled in after, in the language's forms (figures_lang)."""
    import build_pages as BP
    page = guide_href(t["slug"])
    w = Words(lang, t["slug"])
    english = G.reused(G.topic_body(t))
    body = w.h(english)
    body = body.replace(G.SHORTHAND_SLOT, civics.shorthand_table(lang))
    body = fill(body, figures)
    if names is not None:
        body = suffixed(body, names)
    if con is not None:
        body = CT.link_citations(body, con)
    secs = lang_sections(english, body, I.href(lang, page))
    if t.get("holds"):
        sid, h, c = secs[-1]
        secs[-1] = (sid, h, c + f'<p class="l-note">{fill(w.h(t["holds"]), figures)}</p>')
    if t["sources"]:
        secs.append(("sources", I.say(lang, "guides.sources", "Where This Comes From"),
                     lang_sources(t["sources"], w)))
    title = w.t(t["title"])
    lead = dashes(w.t(t["blurb"])) if t["blurb"] else ""
    foot = ('<nav class="l-pager" aria-label="' + E(I.say(lang, "guides.other", "Other guides"))
            + '"><span class="l-pgp"></span>'
            f'<a class="l-pgm" href="{I.href(lang, HUB_PAGE)}#guides">'
            + I.say(lang, "guides.all", "All How-To Guides") + '</a><span class="l-pgn"></span></nav>')
    head_ = (f'<header class="l-head"><h1>{title}</h1>'
             + (f'<p class="l-lead">{lead}</p>' if lead else "") + lang_note(lang)
             + lang_otp(secs, page, lang) + "</header>")
    article = lang_links("".join(section(*s_) for s_ in secs), lang) + foot
    out = BP.shell(f"{E(html.unescape(re.sub(r'<[^>]+>', '', title)))} — Granite Record", page,
                   '<div class="l-page">' + lang_hub_bar(lang) + head_
                   + f'<div class="l-art">{article}</div></div>{OTP_JS}',
                   desc=html.unescape(re.sub(r"<[^>]+>", "", w.t(t["blurb"], attr=True))),
                   base=base, lang=lang)
    if "[[" in out:
        raise SystemExit(f"{I.href(lang, page)} would publish an unfilled figure: "
                         + out[out.index("[["):out.index("[[") + 40])
    return out


def _still_english(lang, slug):
    """" (in English)" after a Learn page's name where `lang` has no version
    of it yet, as the hub's Learn tab marks one; "" where it has."""
    if lang == I.DEFAULT or slug in G.learn_translated(lang):
        return ""
    return '<span class="r-en">(' + I.say(lang, "guides.in_english", "in English") + ")</span>"


def pager_lang(i, topics, lang):
    """pager, in `lang`: Previous Topic and Next Topic with each one's title
    as the hub's Learn tab gives it, and All Topics back to that tab."""
    hub = I.href(lang, HUB_PAGE)

    def side(k, cls, word):
        if k is None or not 0 <= k < len(topics):
            return f'<span class="{cls}"></span>'
        t = topics[k]
        name = (_tw(lang, f"hub.learn.{t['slug']}.title", I.norm(E(t["title"])))
                + _still_english(lang, t["slug"]))
        return (f'<a class="{cls}" href="{E(learn_href(t["slug"]))}"><span class="l-pgw">{word}</span>'
                f'<span class="l-pgd">{name}</span></a>')
    return (f'<nav class="l-pager" aria-label="{E(I.say(lang, "learn.other", "Other topics"))}">'
            + side(None if i is None else i - 1, "l-pgp", I.say(lang, "learn.prev", "Previous Topic"))
            + f'<a class="l-pgm" href="{hub}#learn">' + I.say(lang, "learn.all", "All Topics") + "</a>"
            + side(None if i is None else i + 1, "l-pgn", I.say(lang, "learn.next", "Next Topic"))
            + "</nav>")


def all_topics_lang(topics, here, lang):
    """all_topics, in `lang`: the pages in the hub's two groups, each by the
    name the hub's Learn tab gives it, the one open marked."""
    groups = []
    for group, _note in civics.GROUPS:
        lis = "".join(
            f'<li><span aria-current="page">'
            f'{_tw(lang, "hub.learn." + t["slug"] + ".title", I.norm(E(t["title"])))}</span></li>'
            if t["slug"] == here else
            f'<li><a href="{E(learn_href(t["slug"]))}">'
            f'{_tw(lang, "hub.learn." + t["slug"] + ".title", I.norm(E(t["title"])))}'
            f'{_still_english(lang, t["slug"])}</a></li>'
            for t in topics if t["group"] == group)
        if lis:
            name = _tw(lang, f"hub.learn.group.{I.slug_words(group)}.name", I.norm(E(group)))
            groups.append(f'<div><h3>{name}</h3><ol>{lis}</ol></div>')
    label = I.say(lang, "learn.pages_label", "The pages of this section")
    return ("all-topics", I.say(lang, "learn.all_pages", "The {n} Pages", n=len(topics)),
            f'<nav class="l-all" aria-label="{E(label)}">{"".join(groups)}</nav>')


def learn_page_lang(t, lang, base, figures, topics, open_=(), names=None, con=None):
    """One of Learn's own pages in `lang`, at i18n.href(lang, its page) (the
    person, 25 October 2026: "start on the Learn pages"): its words piece by
    piece (Words, keyed learn.<slug>.*), the paragraphs guides.SAID writes
    once among them, its figures filled in after in the language's forms
    (figures_lang), the guides that do what it explains by the How-To tab's
    words, and the pager and The Pages as the hub's Learn tab names them.
    The record's own words in it -- a bill's number in a link -- are as the
    record has them."""
    import build_pages as BP
    page = learn_href(t["slug"])
    w = Words(lang, t["slug"])
    english = G.reused(G.topic_body(t))
    body = w.h(english).replace(G.SHORTHAND_SLOT, civics.shorthand_table(lang))
    body = fill(body, figures)
    if names is not None:
        body = suffixed(body, names)
    if con is not None:
        body = CT.link_citations(body, con)
    secs = lang_sections(english, body, I.href(lang, page))
    if t.get("holds"):
        sid, h, c = secs[-1]
        secs[-1] = (sid, h, c + f'<p class="l-note">{fill(w.h(t["holds"]), figures)}</p>')
    lis = "".join(
        f'<li><a href="{E(guide_href(s_))}">'
        f'{_tw(lang, "guide.task." + s_ + ".does", I.norm(G.task_of(s_)[1]["does"]))}</a></li>'
        for s_ in civics.GUIDES_FOR.get(t["slug"], ()) if s_ in open_ and G.task_of(s_)[1])
    if lis:
        secs.append(("how-to-guides", I.say(lang, "guides.hub_guides", "How-To Guides"),
                     f'<ul class="l-guides">{lis}</ul>'))
    if t["sources"]:
        secs.append(("sources", I.say(lang, "guides.sources", "Where This Comes From"),
                     lang_sources(t["sources"], w)))
    after = all_topics_lang(topics, t["slug"], lang)
    title = w.t(t["title"])
    lead = dashes(w.t(t["blurb"])) if t["blurb"] else ""
    head_ = (f'<header class="l-head"><h1>{title}</h1>'
             + (f'<p class="l-lead">{lead}</p>' if lead else "")
             + '<p class="langnote">' + I.say(
                 lang, "learn.lang_note", "This page is in Spanish. The official pages it links "
                 "to, and the record itself, are in English.") + "</p>"
             + lang_otp(secs + [after], page, lang) + "</header>")
    i = next((k for k, x in enumerate(topics) if x["slug"] == t["slug"]), None)
    article = lang_links("".join(section(*s_) for s_ in secs) + pager_lang(i, topics, lang)
                         + section(*after), lang)
    out = BP.shell(f"{E(html.unescape(re.sub(r'<[^>]+>', '', title)))} — Granite Record", page,
                   '<div class="l-page">' + lang_hub_bar(lang, "learn") + head_
                   + f'<div class="l-art">{article}</div></div>{OTP_JS}',
                   desc=html.unescape(re.sub(r"<[^>]+>", "", w.t(t["blurb"], attr=True))),
                   base=base, lang=lang)
    if "[[" in out:
        raise SystemExit(f"{I.href(lang, page)} would publish an unfilled figure: "
                         + out[out.index("[["):out.index("[[") + 40])
    return out


def hub_guides_lang(lang, published=(), articles=()):
    """The How-To Guides tab in `lang`: guides_tab, the English tab's own
    layout, each word from the catalog where it is current and in English,
    marked, where it is not."""
    return guides_tab(lang, published, articles) or ""


def hub_page_lang(lang, base, published=(), articles=(), topics=None, groups=None):
    """The Resources hub in `lang`, at i18n.href(lang, HUB_PAGE): the English
    hub's three tabs in that language (hub_tabs, 25 October 2026), each link
    to a page `lang` has sent there, and the rest to the English page."""
    import build_pages as BP
    topics = learn_topics(civics.TOPICS) if topics is None else topics
    groups = official_sources(numbers_results(Path("."))) if groups is None else groups
    title = I.say(lang, "guides.hub", "Resources")
    lead = I.say(lang, "guides.hub_lead", "How to get things done with New Hampshire&rsquo;s state "
                 "and local government, how it works, and where to find what it publishes itself.")
    body = ('<div class="l-page r-hub"><header class="l-head r-head">'
            f'<h1>{title}</h1><p class="l-lead">{lead}</p><p class="langnote">' + I.say(
                lang, "guides.hub_lang_note", "This page is in Spanish, and so are the guides it "
                "lists. The official pages they link to, and the record itself, are in English.")
            + '</p></header>'
            + lang_links(hub_tabs(lang, topics, groups, published, articles), lang))
    return BP.shell(f"{title} — Granite Record", HUB_PAGE, body,
                    desc=html.unescape(re.sub(r"<[^>]+>", "", lead)), base=base, lang=lang)


def write_lang(site, page, make):
    """Each other language's version of `page` that i18n.PAGES names, as
    make(lang) draws it, at i18n.href(lang, page). Returns the languages."""
    done = []
    for lang in I.LANGS:
        if lang == I.DEFAULT or not I.has(lang, page):
            continue
        dst = site / I.href(lang, page).lstrip("/")
        if page.endswith("index.html"):
            dst = dst / "index.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(make(lang), encoding="utf-8")
        done.append(lang)
    return done


HOME_SLOT = re.compile(r"<!-- guides -->.*?<!-- /guides -->", re.S)


# THE HOME PAGE'S COMMON QUESTIONS ARE ON. The person, 18 October 2026,
# turned the "How do I...?" row of one-word buttons off ("I don't like the
# way that the how to guides are presented") and then said what reads wrong:
# "the phrasing is too vague to understand what's useful about it", and
# asked for a few guides to the most common inquiries instead. Those are
# common_questions, below. The flag stays so that the block can be taken off
# the page in one line without its code going with it; while it is False,
# home_guides writes the slot empty and the Resources card is the way to the
# guides. Preflight's _home_cards fails while it is False, because the
# person asked for the block: turning it off is a decision for them, made by
# changing that check too.
HOME_GUIDES = True


def common_questions(published):
    """THE HOME PAGE'S COMMON QUESTIONS, under its cards (the person, 18
    October 2026: "a sort of top 3-5 guides for the most common inquiries").
    Each guide in guides.HOME as a row whose whole box is the link: its plain
    title over a line saying what the reader will learn or be able to do
    there, the way the How-To Guides tab lists every task, so a reader who
    follows All guides meets the same form. All guides opens the hub on that
    tab. A pick whose guide is held back is left off; the pages that became
    guides (civics.HOW_TO) are always there."""
    open_ = {g["slug"] for g in published} | set(civics.HOW_TO)
    picks = [t for t in G.HOME if t["slug"] in open_]
    if not picks:
        return ""
    return ('<nav class="hguides" aria-labelledby="hguides-h">'
            '<h2 id="hguides-h">Common Questions</h2><ul>'
            + "".join(f'<li><a href="{E(S.canon("/" + guide_href(t["slug"])))}"><b>{t["does"]}</b>'
                      f'<span>{dashes(t["line"])}</span></a></li>'
                      for t in picks)
            + '</ul><a class="hgall" href="/resources#guides">All guides</a></nav>')


def home_guides(site, published):
    """The home page's Common Questions (common_questions), under its cards.
    The home page is build_pages' and is written before this runs, so its
    slot is filled here, and filled again rather than doubled on a second
    run."""
    home = site / "index.html"
    if not home.is_file():
        return
    text = home.read_text(encoding="utf-8")
    if not HOME_SLOT.search(text):
        print("  index.html has no guides slot: the home page lists no guides")
        return
    block = common_questions(published) if HOME_GUIDES else ""
    home.write_text(HOME_SLOT.sub(lambda _m: f"<!-- guides -->{block}<!-- /guides -->", text, count=1),
                    encoding="utf-8")
    n = block.count("<li>")
    print(f"  index.html: Common Questions with {n} guide{'s' if n != 1 else ''} under the cards"
          if HOME_GUIDES else "  index.html: Common Questions are off (build_civics.HOME_GUIDES)")


def unlinked(g, held):
    """The guide without its buttons and See Also lines to the pages in
    `held`: the guides this build does not publish."""
    if not held:
        return g
    keep = lambda u: u.split("#")[0] not in held  # noqa: E731
    return dict(g, see=[(label, u) for label, u in g["see"] if keep(u)],
                steps=[dict(s_, actions=[(label, u) for label, u in s_["actions"] if keep(u)])
                       for s_ in g["steps"]])


def build_guides(site, tmpl, base, drafts=False):
    """Writes the guides that may be published (and, with drafts, the rest,
    marked) and returns (published, urls). Says why each one held back is."""
    import build_rsa as BR
    import guide_sources
    # The General Court's two sign-in forms, which a guide links and nothing
    # here fetches, are civics.py's (guides.GENERAL_COURT_LINKS says why).
    fetched = guide_sources.cited() | G.GENERAL_COURT_LINKS
    table = None
    try:
        import rsa
        # THE TABLE OF THE PROJECT BEING BUILT, from the working folder, as
        # build_rsa.py reads it with --db db: the Laws pages a guide links are
        # built from that table, so the guide is held to the same one.
        table = rsa.load(Path("db") / "NH_RSA.psv", Path("db") / "_columns.json")
    except Exception as e:                      # noqa: BLE001 -- said, and no guide links a law then
        print(f"  guides: the statute table could not be read ({type(e).__name__})")
    chapters = table.chapters if table else {}
    cit = Path("rsa_citations.json")
    data = json.loads(cit.read_text(encoding="utf-8")) if cit.is_file() else {}
    bills = BR.Bills(site, BR.term_of_year(build_date.today().year))
    out = site / GUIDE_DIR
    published, urls = [], []
    ready = {g["slug"]: guide_ready(g, fetched, chapters, table.sections if table else {})
             for g in G.GUIDES}
    # A GUIDE HELD BACK IS NOT LINKED (17 October 2026). The four civic
    # guides send a reader on to one another, and a guide held back is not
    # written, so a published guide's button or See Also line to it would be
    # a dead link -- as on the fixture, whose statute table holds the Right-
    # to-Know Law and not RSA 14 or 662. A draft build writes every guide,
    # so there nothing is held and every link stays.
    held = set() if drafts else {"/" + guide_href(s) for s, why in ready.items() if why}
    for g in G.GUIDES:
        why = ready[g["slug"]]
        if why and not drafts:
            print(f"  guides/{g['slug']}.html HELD BACK: {why}")
            continue
        out.mkdir(parents=True, exist_ok=True)
        record = guide_record(g, data, bills, chapters)
        page = guide_page(tmpl, unlinked(g, held), base, record, why)
        # AND IN EACH OTHER LANGUAGE THE GUIDE IS IN (i18n.PAGES; the owner,
        # 24 October 2026), which the English names as its twin. Only a
        # published guide: a draft is for a person to read in English.
        langs = [] if why else write_lang(site, guide_href(g["slug"]), lambda lang: guide_page_lang(
            unlinked(g, held), lang, base, guide_record(g, data, bills, chapters, lang)))
        if langs:
            page = name_versions(guide_href(g["slug"]), page)
        (out / f"{g['slug']}.html").write_text(S.clean_links(page), encoding="utf-8")
        if not why:
            published.append(g)
            urls.append(base + S.canon("/" + guide_href(g["slug"])))
        print(f"  guides/{g['slug']}.html" + (f" (DRAFT: {why})" if why else ", checked "
                                                + G.checked_on(g))
              + (f"; and in {', '.join(langs)}" if langs else ""))
    # A GUIDE HELD BACK LEAVES NO OLD COPY: a page written by an earlier build
    # whose claims have since been unset is not served in its place.
    # The pages that became guides (civics.HOW_TO) are written into the same
    # folder by main(), after this, and are not this function's to remove.
    if out.is_dir() and not drafts:
        keep = {f"{g['slug']}.html" for g in published} | {f"{s}.html" for s in civics.HOW_TO}
        for f in out.glob("*.html"):
            if f.name not in keep:
                f.unlink()
                print(f"  guides/{f.name}: removed, no longer published")
        # And its copy in another language, which is written only beside a
        # published English one.
        for lang in I.LANGS:
            there = site / lang / GUIDE_DIR
            if lang == I.DEFAULT or not there.is_dir():
                continue
            for f in there.glob("*.html"):
                if f.name not in keep:
                    f.unlink()
                    print(f"  {lang}/guides/{f.name}: removed, no longer published")
    return published, urls




def follow_elsewhere(lang=I.DEFAULT):
    """OTHER WAYS TO FOLLOW NEW HAMPSHIRE LEGISLATION (the person, 17 October
    2026), at the foot of the Official Sources tab: the General Court's own
    site first, then the independent trackers civics.FOLLOW_INDEPENDENT
    lists, each with its line and its host, in alphabetical order, no logo,
    and nothing said for or against any of them.

    ON THIS TAB RATHER THAN A FOURTH ONE. The section begins with the
    legislature's own site, which is what this tab holds, and it is short; a
    fourth tab would put a fourth name in the strip a phone already lays out
    in three columns, for six links. Its heading names it, and the line under
    the trackers says they are independent, so a reader of an "Official
    Sources" tab is never left to take them for the state's.

    A GENERAL COURT ADDRESS IS ONE OF guides.GENERAL_COURT_LINKS, the list of
    the Court's pages this part of the site links and never asks, or the build
    stops: the same rule as the guides' sign-in links."""
    def li(name, url, line):
        host = re.sub(r"^https?://(?:www\.)?([^/]+).*$", r"\1", url)
        line = _tw(lang, f"hub.follow.{I.slug_words(name)}.line", line)
        return (f'<li><a href="{E(url)}" target="_blank" rel="noopener">{E(name)}</a>'
                f'<span class="r-fline">{dashes(line)}</span><span class="l-dmeta">{E(host)}</span></li>')
    court = [u for _n, u, _l in civics.FOLLOW_OFFICIAL + civics.FOLLOW_INDEPENDENT
             if re.match(r"https?://(?:[^/]*\.)?gc\.nh\.gov(?:/|$)", u)]
    loose = sorted(set(court) - G.GENERAL_COURT_LINKS)
    if loose:
        raise SystemExit("the Resources hub links a General Court page that is not one of "
                         "guides.GENERAL_COURT_LINKS: " + ", ".join(loose))
    names = [n for n, _u, _l in civics.FOLLOW_INDEPENDENT]
    if names != sorted(names, key=str.casefold):
        raise SystemExit("civics.FOLLOW_INDEPENDENT is not in alphabetical order, which is "
                         "the only order that ranks none of them: " + ", ".join(names))
    n = len(civics.FOLLOW_OFFICIAL) + len(civics.FOLLOW_INDEPENDENT)
    return fold(
        "follow-elsewhere", FOLLOW_HEADING, _hf(lang, "hub.follow.heading"), n,
        f'<p class="r-intro">{_hf(lang, "hub.follow.official")}</p>'
        '<ul class="r-srcs r-follow">' + "".join(li(*r) for r in civics.FOLLOW_OFFICIAL) + "</ul>"
        f'<p class="r-intro">{_hf(lang, "hub.follow.independent")}</p>'
        '<ul class="r-srcs r-follow">' + "".join(li(*r) for r in civics.FOLLOW_INDEPENDENT) + "</ul>")


def hub_sources(groups, lang=I.DEFAULT):
    """The Official Sources tab, in English or in `lang`: each group of
    official_sources folded shut under its badge, as the other two tabs'
    topics are (24 October 2026), and the other ways to follow legislation
    last, folded the same way. A source's name and what it is are the tab's
    own words; a host, and a results page The Record in Numbers adds, are
    left as they are."""
    labels = {u: label for _g, srcs in civics.SOURCE_GROUPS for label, u in srcs}

    def row(name, u, meta):
        if u in labels:
            en_name, what = _src_label(labels[u])
            k = f"hub.src.{I.slug_words(html.unescape(en_name))}"
            name = _tw(lang, k + ".name", en_name)
            if what:
                meta = _tw(lang, k + ".what", what)
        return (f'<li><a href="{E(u)}" target="_blank" rel="noopener">{name}</a>'
                f'<span class="l-dmeta">{meta}</span></li>')
    folds = "".join(fold(
        "src-" + _slug(group), group, _tw(lang, f"hub.src.group.{I.slug_words(group)}", E(group)),
        len(rows), '<ul class="r-srcs">' + "".join(row(*r) for r in rows) + "</ul>")
        for group, rows in groups)
    note = (f'<p class="langnote">{_hf(lang, "hub.src.in_english")}</p>'
            if lang != I.DEFAULT else "")
    return (f'<p class="r-intro">{_hf(lang, "hub.src.intro")}</p>' + note
            + hub_section("src-all", _hf(lang, "hub.src.by_branch"), folds + follow_elsewhere(lang))
            + f'<p class="r-close">{_hf(lang, "hub.src.close")}</p>')


def hub_tabs(lang, topics, groups, published=(), articles=()):
    """The Resources hub's three tabs in `lang`, the strip and the panels.

    THE TOWN PAGES' TABS, THE SAME PATTERN AND THE SAME SCRIPT
    (build_town_pages.TABS_JS): a role=tablist of buttons with a roving
    tabindex, panels with role=tabpanel, each panel's id its address, so
    /resources#sources opens Official Sources. WITHOUT JAVASCRIPT EVERY PANEL
    IS SHOWN, in order, each under its own heading, and the strip is not: it is
    written hidden and the script shows it. One function for every language
    (25 October 2026), so the Spanish hub has the English one's three tabs."""
    import build_town_pages
    # THE PAGES THE PANEL LINKS, COUNTED OFF THE PANEL (16 October 2026). This
    # was len(topics) + 1 -- the topics and By the Numbers, when those were
    # all the panel held -- and the glossary and Laws arrived after it, so the
    # tab read "Learn (14)" over a panel of sixteen links whose first line
    # says "Thirteen short pages" (the webinar's phone check). Counted from
    # what is drawn, each page once, it cannot fall behind the panel again.
    learn = hub_learn(topics, lang)
    n_learn = len(set(re.findall(r'<a href="([^"]+)"', learn)))
    n_src = sum(len(rows) for _, rows in groups)
    guides = hub_guides(published, articles) if lang == I.DEFAULT else hub_guides_lang(
        lang, published, articles)
    panels = [("guides", "How-To Guides", len(published) + len(articles), guides),
              ("learn", "Learn", n_learn, learn),
              ("sources", "Official Sources", n_src, hub_sources(groups, lang))]
    assert [p[:2] for p in panels] == list(HUB_TABS), "the hub's panels and HUB_TABS disagree"
    names = {"guides": I.say(lang, "guides.hub_guides", "How-To Guides"),
             "learn": I.say(lang, "guides.hub_learn", "Learn"),
             "sources": I.say(lang, "guides.hub_sources", "Official Sources")}
    strip = ('<div class="twntabs r-tabs" role="tablist" aria-label="'
             + E(html.unescape(I.say(lang, "guides.hub", "Resources"))) + '" hidden>'
             + "".join(
                 f'<button type="button" role="tab" id="tab-{pid}" data-pane="{pid}" '
                 f'aria-controls="{pid}" aria-selected="{"true" if k == 0 else "false"}" '
                 f'tabindex="{0 if k == 0 else -1}">{names[pid]} <span class="r-n">({count})</span></button>'
                 for k, (pid, _name, count, _) in enumerate(panels)) + "</div>")
    panes = "".join(
        f'<div class="twnpane r-sheet" id="{pid}" role="tabpanel" aria-labelledby="tab-{pid}">'
        f'<h2 class="twnph">{names[pid]}</h2>{body}</div>' for pid, _name, _, body in panels)
    return strip + panes + "</div>" + build_town_pages.TABS_JS + LAND_JS


def hub_page(tmpl, base, topics, groups, published=(), articles=()):
    """The Resources hub: a list head (its title and one line; no trail and no
    Cite this page, which a hub does not carry), then the three tabs
    (hub_tabs)."""
    p = S.page(tmpl, path="/" + HUB_PAGE, base=base,
               title="Resources | Granite Record", og_title="Resources",
               og_type="website", og_image="og-learn.png", og_alt=OG_ALT,
               description=("Step-by-step guides to voting, licenses, benefits, records and "
                            "taking part in the legislature in New Hampshire; how its state and "
                            "local government works; and the official sources it publishes."),
               globals={"GR_STATIC": True}, noscript="",
               skip_label="Skip to the page", sr_title="",
               nav_current="resources.html", cite=False)
    return p.replace(
        '<div id="results"></div>',
        '<div id="results"><div class="l-page r-hub">'
        '<header class="l-head r-head"><h1>Resources</h1>'
        '<p class="l-lead">How to get things done with New Hampshire&rsquo;s state and local '
        'government, how it works, and where to find what it publishes itself.</p></header>'
        + hub_tabs(I.DEFAULT, topics, groups, published, articles) + "</div>", 1)


# AN ADDRESS NAMING A TAB LANDS ON THE STRIP. The browser's own jump to a
# panel's id put the strip above the top of a phone's screen, at a large text
# size, so the reader saw a panel with no way to tell it was one of three (the
# approved prototype's fix).
LAND_JS = """<script>
(function(){
  var s=document.querySelector(".r-tabs");
  if(!s)return;
  function land(){
    var h=(location.hash||"").slice(1);
    if(!h||!document.getElementById("tab-"+h))return;
    window.scrollTo(0,Math.max(0,s.getBoundingClientRect().top+window.scrollY-8));
  }
  addEventListener("load",function(){land();setTimeout(land,0);});
})();
</script>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--drafts", action="store_true",
                    help="also write the guides not yet checked, marked as drafts (for a person to read; "
                         "never the night's)")
    a = ap.parse_args()

    site = Path(a.site)
    topics = civics.TOPICS
    if not topics:
        print("civics.TOPICS is empty; nothing written.")
        return 0
    out = site / LEARN_DIR
    out.mkdir(parents=True, exist_ok=True)

    tmpl = S.template(site)
    figures = record_figures(site)
    names = {(str(r.get("year") or ""), (r.get("id") or "").lower()): r.get("n")
             for r in SR.bill_index_or_stop(site, "build_civics.py") if r.get("n")}
    print(f"figures from the record: {figures['all_bills']} bills, {figures['terms']} terms, "
          f"{figures['vetoed']} vetoed, {figures['bills']} in {figures['term'].replace('&ndash;', '-')}")
    urls = [a.base + HUB]

    # ---- the how-to guides -------------------------------------------------
    # FIRST, BEFORE THE TOPICS (17 October 2026): a Learn page ends with the
    # guides that do what it explains (civics.GUIDES_FOR), and only the guides
    # this build publishes may be named there.
    published, gurls = build_guides(site, tmpl, a.base, a.drafts)
    open_ = {g["slug"] for g in published} | set(civics.HOW_TO)
    articles = how_to_topics(topics)

    # ---- one page a topic ----------------------------------------------
    # Learn's own pages walk their order with Previous and Next; the three
    # that became guides (civics.HOW_TO) are written at /guides/<slug> with a
    # way back to every guide instead.
    # AN ARTICLE A PAGE CITES OPENS ON THE LAWS PAGE (17 October 2026): "Part
    # Second, Article 44" becomes a link to that article's text on the
    # Constitution tab, wherever the Constitution as read holds it.
    con = PCON.load()
    learn = learn_topics(topics)
    # The district map, for the worked example of a town's representatives
    # in another language (figures_lang).
    dist = _load(site / "districts.json", {})
    for t in topics:
        moved = t["slug"] in civics.HOW_TO
        # A PARAGRAPH A GUIDE ALSO SAYS IS THE GUIDE'S (23 October 2026):
        # where a page marks one, guides.reused writes in guides.SAID's words,
        # which the guide's own claims source, rather than a copy of them.
        secs = split_sections(CT.link_citations(suffixed(fill(G.reused(t["body"]), figures), names),
                                                con),
                              article_href(t["slug"]))
        # A LIMIT STATED PLAINLY closes the page's last section of prose --
        # In the Record where the page has one, which is where it says what
        # this site holds.
        if t.get("holds"):
            sid, h, c = secs[-1]
            secs[-1] = (sid, h, c + f'<p class="l-note">'
                        f'{CT.link_citations(suffixed(fill(t["holds"], figures), names), con)}</p>')
        # THE GUIDES THAT DO WHAT THE PAGE EXPLAINS, before its sources.
        lis = "".join(
            f'<li><a href="{E(guide_href(s_))}">{G.task_of(s_)[1]["does"]}</a></li>'
            for s_ in civics.GUIDES_FOR.get(t["slug"], ()) if s_ in open_ and G.task_of(s_)[1])
        if lis and not moved:
            secs.append(("how-to-guides", "How-To Guides",
                         f'<ul class="l-guides">{lis}</ul>'))
        if t["sources"]:
            secs.append(("sources", "Where This Comes From", sources_list(t["sources"])))
        if moved:
            page = learn_page(tmpl, slug=t["slug"], title=t["title"],
                              lead=dashes(E(t["blurb"])) if t["blurb"] else "",
                              description=t["blurb"], secs=secs, foot=guides_foot(),
                              base=a.base, hub="guides")
            # AND IN EACH OTHER LANGUAGE IT IS IN (i18n.PAGES; the owner, 24
            # October 2026), its figures in that language's forms.
            if write_lang(site, guide_href(t["slug"]), lambda lang: article_page_lang(
                    t, lang, a.base, figures_lang(figures, lang, dist), names, con)):
                page = name_versions(guide_href(t["slug"]), page)
            (site / GUIDE_DIR).mkdir(parents=True, exist_ok=True)
            (site / GUIDE_DIR / f"{t['slug']}.html").write_text(S.clean_links(page), encoding="utf-8")
            gurls.append(a.base + S.canon("/" + guide_href(t["slug"])))
            # THE OLD ADDRESS IS A REDIRECT (build_pages.MOVED), and a copy an
            # earlier build left at it would be served in the redirect's place.
            old = out / f"{t['slug']}.html"
            if old.exists():
                old.unlink()
                print(f"  learn/{t['slug']}.html: removed; /learn/{t['slug']} redirects to "
                      f"/guides/{t['slug']}")
            continue
        i = learn.index(t)
        page = learn_page(tmpl, slug=t["slug"], title=t["title"],
                          lead=dashes(E(t["blurb"])) if t["blurb"] else "",
                          description=t["blurb"], secs=secs, foot=pager(i, learn),
                          base=a.base, after=all_topics(learn, t["slug"]))
        # AND IN EACH OTHER LANGUAGE IT IS IN (i18n.PAGES; the person, 25
        # October 2026: "start on the Learn pages"), its figures in that
        # language's forms.
        if write_lang(site, learn_href(t["slug"]), lambda lang: learn_page_lang(
                t, lang, a.base, figures_lang(figures, lang, dist), learn, open_, names, con)):
            page = name_versions(learn_href(t["slug"]), page)
        (out / f"{t['slug']}.html").write_text(S.clean_links(page), encoding="utf-8")
        urls.append(a.base + S.canon("/" + learn_href(t["slug"])))
    print(f"  {len(learn)} Learn pages; {len(articles)} pages that became guides, at /guides/: "
          + ", ".join(t["slug"] for t in articles))

    # ---- the record in numbers ------------------------------------------
    # learn_numbers.py says what it is. It is NOT in civics.TOPICS: the topics
    # are short explanations that end by naming the next one, and this is a
    # long table of counts, so it has no Previous or Next, only All Topics.
    nsecs = split_sections(learn_numbers.body(site), "learn/by-the-numbers.html")
    # A SECTION LEFT OUT IS SAID. learn_numbers leaves out a figure whose input
    # is not on this disk rather than stop every build on it -- the builders'
    # fixture site holds none of them -- and names each one here, so a night
    # that lost testimony_db.json from its kit says so in its log.
    for f, what in learn_numbers.MISSING:
        print(f"  learn/by-the-numbers.html LEAVES OUT {what}: {f} is not here")
    # And a row it cannot cite: a constitutional amendment the voters decided
    # whose row of ballot_results.json names no source or no cite is left off
    # the table, and said here rather than to the reader.
    for what in learn_numbers.HELD:
        print(f"  learn/by-the-numbers.html LEAVES OFF {what}")
    page = learn_page(tmpl, slug=NUMBERS_SLUG, title=NUMBERS_TITLE,
                      lead=curly(NUMBERS_DESC), description=NUMBERS_DESC, secs=nsecs,
                      foot=pager(None, topics), base=a.base)
    (out / f"{NUMBERS_SLUG}.html").write_text(S.clean_links(page), encoding="utf-8")
    urls.append(a.base + S.canon("/" + learn_href(NUMBERS_SLUG)))
    print("  learn/by-the-numbers.html: the page of statistics")

    # ---- the glossary -----------------------------------------------------
    page = learn_page(tmpl, slug=GLOSSARY_SLUG, title=GLOSSARY_TITLE,
                      lead=curly(GLOSSARY_DESC), description=GLOSSARY_DESC,
                      secs=glossary_secs(), foot=pager(None, topics), base=a.base)
    page = name_versions(GLOSSARY_PAGE, page)
    (out / f"{GLOSSARY_SLUG}.html").write_text(S.clean_links(page), encoding="utf-8")
    urls.append(a.base + S.canon("/" + learn_href(GLOSSARY_SLUG)))
    print(f"  learn/{GLOSSARY_SLUG}.html: {len(C.WORDBOOK['glossary'])} terms")
    # And in each other language the site is built in (i18n.PAGES).
    for lang in I.LANGS:
        if lang == I.DEFAULT or not I.has(lang, GLOSSARY_PAGE):
            continue
        dst = site / I.href(lang, GLOSSARY_PAGE).lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(glossary_page_lang(lang, a.base), encoding="utf-8")
        print(f"  {dst.relative_to(site).as_posix()}: the glossary in {lang}")

    # ---- the home page's guides (the guides themselves are written above) --
    home_guides(site, published)

    # ---- the hub ----------------------------------------------------------
    groups = official_sources(numbers_results(Path(".")))
    hub = hub_page(tmpl, a.base, learn, groups, published, articles)
    # Its How-To Guides in each other language the hub is in (i18n.PAGES).
    langs = write_lang(site, HUB_PAGE, lambda lang: hub_page_lang(lang, a.base, published, articles,
                                                                  learn, groups))
    if langs:
        hub = name_versions(HUB_PAGE, hub)
        print(f"  {HUB_PAGE}: its How-To Guides in {', '.join(langs)} too")
    (site / HUB_PAGE).write_text(S.clean_links(hub), encoding="utf-8")
    # THE OLD HUB'S FILE GOES. /learn redirects to the hub (_redirects), and a
    # learn.html left in the folder by an earlier build would be served in
    # the redirect's place by a host that prefers a file.
    old = site / "learn.html"
    if old.exists():
        old.unlink()
        print("  learn.html: removed; /learn redirects to /resources")

    # ---- the sitemap: this builder's addresses in, its stale ones out -----
    added, dropped = S.sitemap_merge(site, a.base, urls, owns="/" + LEARN_DIR)
    if added or dropped:
        print(f"  sitemap.xml: {added} added, {dropped} dropped")
    # A guide's sitemap date is the day it was last checked against its
    # sources: the day what it says last changed.
    added, dropped = S.sitemap_merge(
        site, a.base, gurls, owns="/" + GUIDE_DIR,
        # never later than the build's own day, as a bill's is not
        # (build_bill_pages.lastmod)
        lastmod={a.base + S.canon("/" + guide_href(g["slug"])):
                 min(G.checked_on(g), build_date.today().isoformat())
                 for g in published if G.checked_on(g)})
    if added or dropped:
        print(f"  sitemap.xml: {added} guides added, {dropped} dropped")

    n_src = sum(len(t["sources"]) for t in topics)
    print(f"{len(topics)} topics -> {out}/, and {HUB_PAGE}: "
          f"{sum(len(r) for _, r in groups)} official sources in "
          f"{len(groups)} groups")
    print(f"  {n_src} sources linked, "
          f"{sum(1 for t in topics if t.get('holds'))} pages state a limit")
    missing = [t["slug"] for t in topics if not t["sources"]]
    if missing:
        print(f"  NO SOURCES on: {', '.join(missing)} -- every page needs "
              "somewhere a reader can check it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
