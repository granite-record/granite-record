#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.41
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
import html
import json
import re
import unicodedata
from collections import Counter

import build_date
import civics
import learn_numbers
import proceedings as P
import shell as S
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
    term = max((r.get("term") or "" for r in idx), default="")
    cur = [r for r in idx if r.get("term") == term]
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
    # this counted it as "still awaiting its override vote".
    pending = sum(1 for r in idx if r.get("status") == "Vetoed" and r.get("term") == term)
    stood = sum(1 for r in idx if r.get("status") == "Vetoed, override failed"
                or (r.get("status") == "Vetoed" and r.get("term") != term))
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
    video_from = ""
    for t in sorted(per_term, reverse=True):
        if filmed_term[t] < 0.9 * per_term[t]:
            if t == term:
                continue
            break
        video_from = t
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
          f"<b>{no_rc:,}</b> with none (the grey and the hatched)", False),
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
# The hub's three tabs, in the person's order: (address, name).
HUB_TABS = (("learn", "Learn"), ("guides", "How-To Guides"), ("sources", "Official Sources"))
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


def curly(text):
    """Escaped for the page, with the apostrophe a reader sees (the meta
    description keeps the plain one it has always had)."""
    return E(text).replace("&#x27;", "&rsquo;")


def learn_href(slug):
    return f"{LEARN_DIR}/{slug}.html"


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
    """
    def one(label, u):
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
    here = S.canon(learn_href(slug))
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


def learn_page(tmpl, *, slug, title, lead, description, secs, foot, base, after=None):
    """A Learn article: the Resources bar, the head, the sections, the pager
    (foot) and, after it, The Thirteen Pages (after)."""
    path = "/" + learn_href(slug)
    p = S.page(tmpl, path=path, base=base,
               # THE SITE'S NAME LAST, on every page; the section is worth
               # naming, so it goes in front of the brand rather than instead.
               title=S.title_of(title, "Learn"),
               og_title=title, description=description,
               og_image="og-learn.png", og_alt=OG_ALT,
               globals={"GR_STATIC": True}, noscript="",
               skip_label="Skip to the page", sr_title="",
               nav_current="resources.html", cite=False)
    every = secs + ([after] if after else [])
    article = ("".join(section(*s) for s in secs) + foot
               + (section(*after) if after else ""))
    out = p.replace('<div id="results"></div>',
                    '<div id="results"><div class="l-page">' + hub_bar()
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
START = [("how-a-bill-becomes-law",
          "The course a bill runs, and the stages it can die at."),
         ("general-court",
          "Who the 424 of them are, and how a two-year term is shaped."),
         ("testifying",
          "Anyone may speak on any bill. This is how.")]


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


def hub_learn(topics):
    by_slug = {t["slug"]: t for t in topics}
    n = len(topics)
    start = "".join(
        f'<li><a href="{E(learn_href(slug))}"><b>{E(by_slug[slug]["title"])}</b>'
        f'<span>{E(why)}</span></a></li>' for slug, why in START if slug in by_slug)
    started = {slug for slug, _ in START}
    out = [f'<p class="r-intro">{NUMBER_WORD.get(n, n)} short pages on the parts of state '
           'and local government, each one linked to where you can watch it happening in '
           'the record.</p>',
           hub_section("start", "Start Here", f'<ul class="r-start">{start}</ul>')]
    for group, note in civics.GROUPS:
        lis = "".join(
            f'<li><a href="{E(learn_href(t["slug"]))}">{E(t["title"])}</a>'
            f'<p>{dashes(E(t["blurb"]))}</p></li>'
            for t in topics if t["group"] == group and t["slug"] not in started)
        if lis:
            out.append(hub_section("s-" + _slug(group), E(group),
                                   f'<p class="r-intro">{E(note)}</p><ul class="r-topics">{lis}</ul>'))
    # NOT ONE OF THE NUMBERED PAGES. The topics are short explanations meant
    # to be read in order; this is a long table of statistics counted from the
    # record, for a different reader, so it sits after them under its own
    # heading, which is its link.
    out.append(hub_section(
        "numbers", f'<a href="{E(learn_href(NUMBERS_SLUG))}">{NUMBERS_TITLE}</a>',
        '<p class="r-intro">Counted from the General Court&rsquo;s own record.</p>'
        f'<p class="r-one">{curly(NUMBERS_WHAT[0].upper() + NUMBERS_WHAT[1:])}.</p>'))
    return "".join(out)


def hub_guides():
    """THERE ARE NONE YET, AND THE TAB SAYS SO. The list of guides coming
    stays hidden until the first one exists (8 October 2026); the tab is
    drawn anyway, because the person asked for a tab for each, and points to
    the other two."""
    return ('<p class="r-none">There are no how-to guides yet.</p>'
            '<p class="r-sub">Each guide will be listed here once it is written and checked '
            'against the official sources it cites.</p>'
            '<ul class="r-goto">'
            f'<li><a href="{HUB}#learn"><b>Learn</b><span>How each part of state and local '
            'government works.</span></a></li>'
            f'<li><a href="{HUB}#sources"><b>Official Sources</b><span>The state&rsquo;s own '
            'sites, where its records and services are.</span></a></li></ul>')


def hub_sources(groups):
    secs = "".join(hub_section(
        "src-" + _slug(group), E(group),
        '<ul class="r-srcs">' + "".join(
            f'<li><a href="{E(u)}" target="_blank" rel="noopener">{name}</a>'
            f'<span class="l-dmeta">{meta}</span></li>' for name, u, meta in rows) + "</ul>")
        for group, rows in groups)
    return ('<p class="r-intro">The sites the Learn pages cite as their sources. Each opens in '
            'a new tab.</p>' + secs
            + '<p class="r-close">Every page here ends with its sources. If something is wrong, '
            '<a href="mailto:contact@graniterecord.org">tell us</a> &mdash; that address exists '
            'for this.</p>')


def hub_page(tmpl, base, topics, groups):
    """The Resources hub: a list head (its title and one line; no trail and no
    Cite this page, which a hub does not carry), then the three tabs.

    THE TOWN PAGES' TABS, THE SAME PATTERN AND THE SAME SCRIPT
    (build_town_pages.TABS_JS): a role=tablist of buttons with a roving
    tabindex, panels with role=tabpanel, each panel's id its address, so
    /resources#sources opens Official Sources. WITHOUT JAVASCRIPT EVERY PANEL
    IS SHOWN, in order, each under its own heading, and the strip is not: it is
    written hidden and the script shows it.
    """
    import build_town_pages
    n_learn = len(topics) + 1
    n_src = sum(len(rows) for _, rows in groups)
    panels = [("learn", "Learn", n_learn, hub_learn(topics)),
              ("guides", "How-To Guides", 0, hub_guides()),
              ("sources", "Official Sources", n_src, hub_sources(groups))]
    assert [p[:2] for p in panels] == list(HUB_TABS), "the hub's panels and HUB_TABS disagree"
    strip = ('<div class="twntabs r-tabs" role="tablist" aria-label="Resources" hidden>'
             + "".join(
                 f'<button type="button" role="tab" id="tab-{pid}" data-pane="{pid}" '
                 f'aria-controls="{pid}" aria-selected="{"true" if k == 0 else "false"}" '
                 f'tabindex="{0 if k == 0 else -1}">{E(name)} <span class="r-n">({count})</span></button>'
                 for k, (pid, name, count, _) in enumerate(panels)) + "</div>")
    panes = "".join(
        f'<div class="twnpane r-sheet" id="{pid}" role="tabpanel" aria-labelledby="tab-{pid}">'
        f'<h2 class="twnph">{E(name)}</h2>{body}</div>' for pid, name, _, body in panels)
    p = S.page(tmpl, path="/" + HUB_PAGE, base=base,
               title="Resources | Granite Record", og_title="Resources",
               og_type="website", og_image="og-learn.png", og_alt=OG_ALT,
               description=("How New Hampshire's state and local government works, and the "
                            "official sources it publishes."),
               globals={"GR_STATIC": True}, noscript="",
               skip_label="Skip to the page", sr_title="",
               nav_current="resources.html", cite=False)
    return p.replace(
        '<div id="results"></div>',
        '<div id="results"><div class="l-page r-hub">'
        '<header class="l-head r-head"><h1>Resources</h1>'
        '<p class="l-lead">How New Hampshire&rsquo;s state and local government works, and '
        'where to find what it publishes itself.</p></header>'
        + strip + panes + "</div>" + build_town_pages.TABS_JS + LAND_JS + "</div>", 1)


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

    # ---- one page a topic ----------------------------------------------
    for i, t in enumerate(topics):
        secs = split_sections(suffixed(fill(t["body"], figures), names),
                              f"learn/{t['slug']}.html")
        # A LIMIT STATED PLAINLY closes the page's last section of prose --
        # In the Record where the page has one, which is where it says what
        # this site holds.
        if t.get("holds"):
            sid, h, c = secs[-1]
            secs[-1] = (sid, h, c + f'<p class="l-note">{suffixed(fill(t["holds"], figures), names)}</p>')
        if t["sources"]:
            secs.append(("sources", "Where This Comes From", sources_list(t["sources"])))
        page = learn_page(tmpl, slug=t["slug"], title=t["title"],
                          lead=dashes(E(t["blurb"])) if t["blurb"] else "",
                          description=t["blurb"], secs=secs, foot=pager(i, topics),
                          base=a.base, after=all_topics(topics, t["slug"]))
        (out / f"{t['slug']}.html").write_text(page, encoding="utf-8")
        urls.append(a.base + S.canon("/" + learn_href(t["slug"])))

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
    (out / f"{NUMBERS_SLUG}.html").write_text(page, encoding="utf-8")
    urls.append(a.base + S.canon("/" + learn_href(NUMBERS_SLUG)))
    print("  learn/by-the-numbers.html: the page of statistics")

    # ---- the hub ----------------------------------------------------------
    groups = official_sources(numbers_results(Path(".")))
    (site / HUB_PAGE).write_text(hub_page(tmpl, a.base, topics, groups), encoding="utf-8")
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
