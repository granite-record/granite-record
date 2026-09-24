#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.26
"""
The civics section: a hub and one page per topic, in order.

    python3 build_civics.py --site site --base https://graniterecord.org

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

import argparse
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import civics
import learn_numbers
import proceedings as P
import shell as S


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


def _cacr_record(cacrs, narr, term):
    """The term's CACRs, every one in exactly one clause: the voters, a
    three-fifths failure on the House floor where the docket records one,
    and otherwise its status."""
    if not cacrs:
        return f"The {term.replace('-', '&ndash;')} term filed no CACRs."
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

    clauses = []
    if by["Killed"]:
        clauses.append(f"{n_(by['Killed'])} {'was' if by['Killed'] == 1 else 'were'} killed outright")
    if short:
        sen = sum(1 for r in short if (r.get("passage") or "")[:2] == "Sp")
        tail = ""
        if sen:
            tail = (f", {sen:,} of them after passing the Senate" if len(short) > 1
                    else ", after passing the Senate")
        clauses.append(f"{n_(len(short))} fell short of three fifths on the House floor{tail}")
    failed = [r for r in rest if r.get("status") == "Failed to pass"]
    if failed:
        clauses.append(f"{n_(len(failed))} failed a floor vote")
    if by["Died on the table"]:
        clauses.append(f"{n_(by['Died on the table'])} died on the table")
    ended = [r for r in rest if r.get("status") == "Died when the session ended"]
    if ended:
        after = Counter((r.get("passage") or "")[:1] for r in ended
                        if (r.get("passage") or "")[1:2] == "p")
        tail = ""
        if sum(after.values()):
            where = " or ".join(("the Senate" if c == "S" else "the House")
                                for c in sorted(after))
            tail = (f", {sum(after.values()):,} of them after passing {where}"
                    if len(ended) > 1 else f", after passing {where}")
        clauses.append(f"{n_(len(ended))} died when the session ended{tail}")
    done = {"Killed", "Failed to pass", "Died on the table",
            "Died when the session ended", *voters}
    for s in sorted(s for s in by if s not in done):
        clauses.append(f"{n_(by[s])} {'is' if by[s] == 1 else 'are'} listed as “{s}”")
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
    idx = _load(Path(site) / "index.json", [])
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
    procs = P.load()
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
        "municipalities": len(_load(Path(root) / "town_officials.json", {})),
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
        # machine made true: the page states the one date it can know.
        "built_on": S.BUILT,
    }
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


def fill(text, figures):
    """[[name]] -> its figure. A name with no figure stops the build: a page
    that printed "[[killed]]", or nothing where a number was, would publish."""
    unknown = sorted(set(re.findall(r"\[\[(\w+)\]\]", text or "")) - set(figures))
    if unknown:
        raise SystemExit(f"civics.py names figures build_civics does not count: {unknown}")
    return dashes(re.sub(r"\[\[(\w+)\]\]",
                         lambda m: str(figures[m.group(1)]), text or ""))


def sources_block(sources):
    if not sources:
        return ""
    # A SOURCE ON THIS SITE IS NOT AN OUTWARD LINK. Every entry here used to be
    # somebody else's page, so every one got target="_blank" and the arrow this
    # site uses to mean "this leaves the record". One of them is now our own
    # directory -- the General Court's address lookup answers 404 and the town
    # pages already hold what it gave -- and sending a reader to our own page in
    # a new tab, marked as though it were elsewhere, tells them something untrue
    # about where they are going.
    def one(label, u):
        away = u.startswith("http")
        mark = ' target="_blank" rel="noopener"' if away else ""
        arrow = " &#8599;" if away else ""
        return f'<li><a href="{E(u)}"{mark}>{E(label)}</a>{arrow}</li>'

    items = "".join(one(label, u) for label, u in sources)
    return (f'<section class="srcs"><h2>Where this comes from</h2>'
            f'<ul class="reading">{items}</ul></section>')


# Three destinations beside a three-section page is the page printed twice,
# which is the mistake already recorded above rail() for the hub. Seven of the
# fourteen pages clear this; the other seven still get ids, because an address
# costs nothing and a deep link into a 267-word page still lands somewhere.
CONTENTS_MIN = 4


def _slug(inner):
    """A heading's own words, as an address."""
    bare = html.unescape(re.sub(r"<[^>]+>", "", inner))
    flat = unicodedata.normalize("NFKD", bare).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", flat.lower()).strip("-")
    if not s:
        raise SystemExit("a learn heading has no words to make an address "
                         "from: " + inner[:60])
    return s


def anchored(article, prefix="s-"):
    """Give every h2 an address; return the article and the list of them.

    DERIVED, NOT AUTHORED. Nothing links to a learn heading today because
    there has never been anything to link to -- all fifteen built pages carry
    zero ids on any h1-h6 -- so there is no contract to break, and sixty-two
    hand-written ids would put the machinery into civics.py, which is the
    writing. A heading that already has an id keeps it: that is how an author
    pins an address whose wording is going to change.

    h2 ONLY, and not every h2. SHOWS puts an h3 "In the record" callout label
    on eight pages, so a list off both levels would be a transcript of the
    page rather than a map of it -- and flow_diagram writes its phase names as
    <hN class="phname">, at level 2 on how-a-bill-becomes-law. Those four are
    the COLUMNS of one diagram, sitting side by side in a single horizontal
    row: listing them gave that page nine entries of which the first four all
    scrolled to the same place. A contents list that offers four destinations
    and delivers one is worse than none, so a phase name gets an address --
    a deep link to a column of the diagram is still a real place -- and stays
    out of the list.

    html.unescape is not optional -- these headings carry &mdash; and &ndash;,
    and without it "2025&ndash;2026" slugs as "2025-ndash-2026".
    """
    out, seen, items, pos = [], set(), [], 0
    for m in re.finditer(r"<h2([^>]*)>(.*?)</h2>", article, re.S):
        attrs, inner = m.group(1), m.group(2)
        out.append(article[pos:m.start()])
        pos = m.end()
        listed = "phname" not in attrs
        got = re.search(r'id="([^"]+)"', attrs)
        if got:
            hid = got.group(1)
            out.append(m.group(0))
        else:
            base = prefix + _slug(inner)
            hid, n = base, 2
            while hid in seen:
                hid, n = f"{base}-{n}", n + 1
            out.append(f'<h2 id="{hid}"{attrs}>{inner}</h2>')
        seen.add(hid)
        # The label is the heading's own text with the tags out and the
        # entities LEFT ALONE. E() here would publish "2025&amp;ndash;2026".
        if listed:
            items.append((hid, re.sub(r"<[^>]+>", "", inner).strip()))
    out.append(article[pos:])
    return "".join(out), items


def contents(items, slug):
    """The page's own sections, for a reader who arrived on one of them.

    EVERY HREF CARRIES ITS PATH. These pages are built from bills.html, which
    sets <base href="/">, so href="#s-vetoes" would resolve against the base
    and send the reader to the home page. preflight would not catch it on its
    own: _links_resolve urldefrags every href before resolving it, so a bare
    fragment reads as the site root and passes. footer_nav's docstring records
    the same trap being sprung once already, with "../learn.html".
    """
    if len(items) < CONTENTS_MIN:
        return ""
    here = S.canon("learn/" + slug + ".html")
    li = "".join(f'<li><a href="{E(here)}#{E(hid)}">{text}</a></li>'
                 for hid, text in items)
    return ('<nav class="ctoc" aria-labelledby="ctoc-head">'
            '<h2 id="ctoc-head">On this page</h2>'
            f'<ol>{li}</ol></nav>')


def rail(topics, here=None):
    """The eleven pages, beside whichever one is open.

    THE SECTION READS AS A BOOK OR AS ELEVEN DEAD ENDS. Each page ended with the
    next one by name and nothing else, so a reader who wanted the third page
    from the second had to go back to the hub; and since these pages line up on
    the site's left edge, the right two thirds of a Learn page was empty, which
    is the shape this project treats as broken. The rail fills it with the one
    thing a reader of a civics section wants: where they are among the rest.
    It is the same list the hub draws, in the same order.
    """
    items = "".join(
        f'<li><a href="{E(S.canon("learn/" + t["slug"] + ".html"))}"'
        + (' aria-current="page"' if t["slug"] == here else "")
        + f'>{E(t["title"])}</a></li>' for t in topics)
    # The count comes from the list, like every other number on these pages, and
    # it is spelled the way the prose spells a small number.
    words = ["no", "one", "two", "three", "four", "five", "six", "seven",
             "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
             "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
    n = len(topics)
    return ('<aside class="lrail" aria-label="The pages of this section">'
            f'<h2>The {words[n] if n < len(words) else n} pages</h2>'
            f'<ol>{items}</ol></aside>')


def footer_nav(i, topics):
    """The next topic by name, and the way back to the hub.

    Every href here is written from the SITE ROOT, not relative to /learn/.
    bills.html carries <base href="/"> -- it has to, because opening a bill on
    the search page pushes /bill/2026/hb1123 and re-bases every link on it --
    and these pages are built from that same template. So "../learn.html"
    would resolve to /../learn.html and a sibling "courts.html" to /courts.html.
    """
    # PREVIOUS ON THE LEFT, NEXT ON THE RIGHT, in the order a reader reads.
    # The markup is in the order it is drawn, so the keyboard meets them the
    # same way round.
    bits = ['<nav class="tnav">']
    if i:
        prev = topics[i - 1]
        bits.append(f'<a class="prev" href="learn/{E(prev["slug"])}.html">'
                    f'<span>Previous</span><b>{E(prev["title"])}</b></a>')
    bits.append('<a class="all" href="learn.html">All topics</a>')
    if i + 1 < len(topics):
        nxt = topics[i + 1]
        bits.append(f'<a class="next" href="learn/{E(nxt["slug"])}.html">'
                    f'<span>Next topic</span><b>{E(nxt["title"])}</b></a>')
    else:
        bits.append('<a class="next" href="learn.html">'
                    '<span>Back to</span><b>All topics</b></a>')
    bits.append("</nav>")
    return "".join(bits)


# Spelled out, because "11 short pages" in a sentence reads like a list
# heading rather than prose. Falls back to the digits past twenty, by which
# point the section is a different thing and the sentence needs rewriting
# anyway.
NUMBER_WORD = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
    7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven",
    12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen",
    16: "Sixteen", 17: "Seventeen", 18: "Eighteen", 19: "Nineteen",
    20: "Twenty",
}


def hub(topics):
    # COUNTED, NOT TYPED. This read "Eleven short pages" while civics.TOPICS
    # held eleven, and the sentence is one edit to that list away from being
    # false -- on a page whose whole argument is that its figures come from
    # the record rather than from someone's memory.
    n = len(topics)
    out = ['<h1>How New Hampshire works</h1>',
           f'<p class="lead">{NUMBER_WORD.get(n, n)} short pages on the parts '
           'of state and local government, each one linked to where you can '
           'watch it happening in the record.</p>',
           # WHAT THIS IS FOR, SAID ONCE. The hub was a numbered list and
           # nothing else: a reader arriving cold could not tell whether
           # these were explainers written from a textbook or written from
           # the record, and that distinction is the only reason this section
           # exists rather than linking to somebody else's civics site.
           '<p>Every figure on these pages is one this site can produce from '
           'the record, and every page says what it counts and over what '
           'period. Where the record holds nothing &mdash; the courts, the '
           'Executive Council &mdash; the page is short and says so rather '
           'than being padded with prose nobody here can check.</p>',
           # THE THREE PAGES MOST PEOPLE WANT. Thirteen equal rows made the
           # reader choose before they knew what they were choosing between,
           # and the answer is nearly always one of three. This replaced a
           # single promoted link in a tinted box, which had two faults: it
           # named one page where a newcomer has three different first
           # questions -- how does this work, who are these people, how do I
           # say something -- and it was the heaviest object on the page while
           # being a second copy of item 2 in the list below it.
           #
           # WHY THESE THREE, AND IN THIS ORDER. How a bill becomes law is the
           # spine everything else hangs off. The General Court answers "who
           # are they", which is the other cold-open question. Testifying is
           # the one page that tells a reader they can do something, and it is
           # the least known thing in the whole section.
           '<h2>Start here</h2><div class="startrow">']
    START = [("how-a-bill-becomes-law",
              "The course a bill runs, and the stages it can die at."),
             ("general-court",
              "Who the 424 of them are, and how a two-year term is shaped."),
             ("testifying",
              "Anyone may speak on any bill. This is how.")]
    by_slug = {t["slug"]: t for t in topics}
    for slug, why in START:
        t = by_slug.get(slug)
        if not t:
            continue
        out.append(f'<a class="startcard" href="learn/{E(slug)}.html">'
                   f'<b>{E(t["title"])}</b><span>{E(why)}</span></a>')
    out.append("</div>")
    for group, note in civics.GROUPS:
        rows = [(i, t) for i, t in enumerate(topics) if t["group"] == group]
        if not rows:
            continue
        # THE ROW COUNT IS THE STYLESHEET'S, COMPUTED HERE. The two columns
        # fill downward rather than across, which needs grid-template-rows to
        # know how many rows to make. That number is this list's own length
        # halved and rounded up, and it is written into the element so the
        # page needs no script to be right -- the same reason every other
        # figure on these pages is counted at build time rather than drawn in
        # the browser.
        rowspan = (len(rows) + 1) // 2
        out.append(f'<h2>{E(group)}</h2><p class="src">{E(note)}</p>'
                   f'<ol class="tlist" style="--rows:{rowspan}">')
        for n, (i, t) in enumerate(rows, 1):
            out.append(
                f'<li><a href="learn/{E(t["slug"])}.html">'
                f'<b>{E(t["title"])}</b>'
                f'<span>{dashes(E(t["blurb"]))}</span></a></li>')
        out.append("</ol>")
    # NOT ONE OF THE NUMBERED PAGES. The topics above are short explanations
    # meant to be read in order, and each ends by naming the next. This is a
    # long table of statistics counted from the record -- a different kind of
    # thing for a different reader, and putting it in the sequence would
    # interrupt the sequence. It sits after them, named for what it is.
    out.append(
        '<h2>The record in numbers</h2>'
        '<p class="src">Counted from the General Court\'s own record, at '
        'build time, every time this site is built.</p>'
        '<ol class="tlist" style="--rows:1"><li>'
        '<a href="learn/by-the-numbers.html">'
        '<b>The record in numbers</b>'
        '<span>Vetoes and what happens to them, the closest votes on record, '
        'how often a chamber overrules its own committee, and how the two '
        'chambers differ in the way they take a vote.</span></a></li></ol>')
    out.append(
        '<p class="note">Every page here ends with its sources. If something '
        'is wrong, <a href="mailto:contact@graniterecord.org">tell us</a> '
        '&mdash; that address exists for this.</p>')
    return "".join(out)


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
    out = site / "learn"
    out.mkdir(parents=True, exist_ok=True)

    tmpl = S.template(site)
    urls = [a.base + S.canon("/learn.html")]
    figures = record_figures(site)
    print(f"figures from the record: {figures['all_bills']} bills, {figures['terms']} terms, "
          f"{figures['vetoed']} vetoed, {figures['bills']} in {figures['term'].replace('&ndash;', '-')}")

    # ---- the hub -------------------------------------------------------
    page = S.page(tmpl, path="/learn.html", base=a.base,
                  title="How New Hampshire works | Granite Record",
                  og_title="How New Hampshire works",
                  og_image="og-learn.png", og_alt="Granite Record: how New Hampshire works",
                  description=("Short, plain explanations of the parts of New "
                               "Hampshire state government, each linked to "
                               "where you can watch it happening."),
                  globals={"GR_STATIC": True}, noscript="",
                  skip_label="Skip to the topics",
                  sr_title="", nav_current="learn.html")
    # NO RAIL ON THE HUB. Every topic page carries a rail of the other ten,
    # because a reader inside the section needs a way across it. The hub IS
    # that list: drawing the rail here printed all eleven titles twice on one
    # page, the second time in grey at half the size, and left the whole right
    # half of a 1440px window empty while the eleven entries queued up in a
    # 560px column. Without it the hub is one thing at full width.
    page = page.replace('<div id="results"></div>',
                        f'<div id="results">'
                        f'<div class="civics hubpage">{hub(topics)}</div>'
                        f'</div>', 1)
    (site / "learn.html").write_text(page, encoding="utf-8")

    # ---- one page a topic ----------------------------------------------
    for i, t in enumerate(topics):
        # THE HEADING BLOCK IS ITS OWN ELEMENT, so that a narrow screen can
        # put the contents list between it and the prose. Inside .civics, the
        # only orders available were "contents above the title" and "contents
        # under 1,900 words", and both are wrong.
        #
        # NOT chead. app.js has drawn every bill card's head button with
        # that class since long before this, and app.css styles it from
        # line 1056. A second rule of the same name lower in the stylesheet
        # won on source order and took 24px of left padding off all 33,683
        # bill cards. preflight freezes the set of names both renderers use,
        # so the next one of these fails a check instead of shipping.
        head = (f'<p class="crumb"><a href="learn.html">How New Hampshire '
                f'works</a></p><h1>{E(t["title"])}</h1>'
                + (f'<p class="lead">{dashes(E(t["blurb"]))}</p>'
                   if t["blurb"] else ""))
        body = [fill(t["body"], figures)]
        if t.get("holds"):
            body.append(f'<p class="caveat">{fill(t["holds"], figures)}</p>')
        # The ids and the contents come off the ARTICLE, before the
        # sources block and the pager are appended: "Where this comes from" is
        # an h2 too, and a contents list that names the list of sources under
        # it is describing the furniture rather than the page.
        article, sections = anchored("".join(body))
        body = [article, sources_block(t["sources"]), footer_nav(i, topics)]

        p = S.page(tmpl, path=f"/learn/{t['slug']}.html", base=a.base,
                   # THE SITE'S NAME LAST, on every page. These eleven ended
                   # "| How New Hampshire works" while the other 34,000 ended
                   # "| Granite Record", so a search result for a civics page
                   # did not look like it came from the same site. The section
                   # is worth naming, so it goes in front of the brand rather
                   # than instead of it.
                   title=S.title_of(t["title"],
                                    "How New Hampshire works"),
                   og_title=t["title"], description=t["blurb"],
                   og_image="og-learn.png", og_alt="Granite Record: how New Hampshire works",
                   globals={"GR_STATIC": True}, noscript="",
                   skip_label="Skip to the page", sr_title="",
                   nav_current="learn.html")
        p = p.replace('<div id="results"></div>',
                      f'<div id="results"><div class="lcols">'
                      f'<header class="civhead">{head}</header>'
                      f'<div class="civics">{"".join(body)}</div>'
                      f'<div class="lside">{contents(sections, t["slug"])}'
                      f'{rail(topics, t["slug"])}</div>'
                      f'</div></div>', 1)
        if "[[" in p:
            raise SystemExit(f"learn/{t['slug']}.html would publish an unfilled figure: "
                             + p[p.index("[["):p.index("[[") + 40])
        (out / f"{t['slug']}.html").write_text(p, encoding="utf-8")
        urls.append(a.base + S.canon(f"/learn/{t['slug']}.html"))

    # ---- the record in numbers ------------------------------------------
    # learn_numbers.py says what it is. It began as a draft -- noindex, absent
    # from the hub and from the sitemap -- and is public now: in the hub, in
    # the sitemap, and no longer noindex.
    #
    # It is NOT in civics.TOPICS. The topics are short explanations that end by
    # naming the next one, and this is a long table of counts; hub() puts it
    # after them under its own heading rather than in the sequence.
    path = "/learn/by-the-numbers.html"
    p = S.page(tmpl, path=path, base=a.base,
               title=S.title_of("The record in numbers", "How New Hampshire works"),
               og_title="The record in numbers",
               description=("Statistics counted from the New Hampshire General Court's own "
                            "record: vetoes, the closest votes, how votes are taken, and how "
                            "often a chamber overrules its committee."),
               og_image="og-learn.png", og_alt="Granite Record: how New Hampshire works",
               globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the page",
               sr_title="", nav_current="learn.html")
    # THE PAGE A SEARCH ENGINE SENDS PEOPLE TO, and until now the one page
    # of the fourteen with no way off it but the crumb: no contents, no pager,
    # no rail, and the whole right of the window empty. "The closest votes of
    # 2025-2026" is the kind of thing somebody types into Google. It gets the
    # same two lists the topic pages get. rail() with no `here` marks nothing
    # as current, which is right: this page is not one of the thirteen.
    nbody, nsections = anchored(learn_numbers.body(site))
    p = p.replace('<div id="results"></div>',
                  '<div id="results"><div class="lcols">'
                  '<header class="civhead"><p class="crumb"><a href="learn.html">'
                  'How New Hampshire works</a></p>'
                  '<h1>The record in numbers</h1></header>'
                  '<div class="civics">' + nbody + '</div>'
                  f'<div class="lside">{contents(nsections, "by-the-numbers")}'
                  f'{rail(topics)}</div>'
                  '</div></div>', 1)
    (out / "by-the-numbers.html").write_text(p, encoding="utf-8")
    urls.append(a.base + S.canon(path))
    print("  learn/by-the-numbers.html: the page of statistics (public since 17 Sep)")

    # ---- the sitemap, appended rather than rewritten -------------------
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{S.E(u)}</loc></url>\n"
                      for u in urls if S.E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"  {len(add.splitlines())} added to sitemap.xml")

    n_src = sum(len(t["sources"]) for t in topics)
    print(f"{len(topics)} topics -> {out}/ and learn.html")
    print(f"  {n_src} sources linked, "
          f"{sum(1 for t in topics if t.get('holds'))} pages state a limit")
    missing = [t["slug"] for t in topics if not t["sources"]]
    if missing:
        print(f"  NO SOURCES on: {', '.join(missing)} -- every page needs "
              "somewhere a reader can check it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
