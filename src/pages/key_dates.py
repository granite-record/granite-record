#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.3
"""
The key dates: the elections, town meeting day, and the legislature's own
landmarks and deadlines, each with where it comes from. The home page's
Coming up shows those of its week as cards among the week's meetings, its
status box names the next deadline, and the Calendar shows each on its day
under Important Dates.

THEIR NAME ON THE PAGE IS IMPORTANT DATES (the owner, 24 October 2026: "Key
Dates doesn't sound like the right phrase for that category, maybe something
like House Deadlines, but that doesn't encompass things like elections, so
feel free to workshop that name"): a name that holds a deadline, an election,
Organization Day and town meeting alike. The code keeps "key date" for them,
and the category its key, "date".

    import key_dates as KD
    KD.events(today)                   # every key date, in date order
    KD.days(events, lo, hi)            # {day: [(event, role)]} between two days
    KD.ahead(events, after, n)         # the next n (day, event, role) after a day
    KD.next_deadline(events, today)    # the status box's (day, event, role), or None

    python3 src/pages/key_dates.py                     # the list, with sources; no network
    python3 src/pages/key_dates.py --day 2026-10-24    # as on that day

A role is "" for a date of one day, and "first" or "last" for the first and
last days of a filing period, which is one key date shown on both its days.

WHAT WAS ASKED (the owner, 24 October 2026). "Coming up should list major
events like the election days, town meeting days, organization day, etc and
those dates should show up on the calendar page too under a separate meeting
type in the key. Statuses should list the most relevant upcoming deadline like
the deadline for committees to finish interim study reports, filing periods,
etc."

WHERE EACH DATE COMES FROM. No date here is typed from memory, and none is
kept in a second table beside one that already holds it.

  The legislature's own dates are legislative_year's: every dated row of the
  schedule page's timeline, as TERMS holds it for an entered term -- each
  with the House or Senate calendar or journal that prints it, read off the
  PDF's layout -- or as skeleton() gives it for a term not entered yet (the
  days the constitution and the election law fix, computed by their rule).
  That is Organization Day, each session's first day, the filing periods for
  bill requests and their last days, crossover, the last days to act on
  bills, veto days, the interim study reports and the general election (RSA
  653:7). A row verify() finds its document no longer prints is left out
  here, as it is on that page. A row that gathers deadlines of its own (the
  committee deadlines, the committees of conference) is a group rather than a
  date and is left out, and so is a row with no date. Each keeps the source
  line the schedule page gives it (legislative_year.cite_html).

  Two more are fixed by statute and computed here, by the rule as the RSA
  text on this disk gives it (db/NH_RSA.psv, read 24 October 2026):

    Town meeting day, the second Tuesday of March (RSA 39:1; RSA 669:1, I).
    A town that adopted official ballot voting may hold its voting day on
    the second Tuesday in April or May instead (RSA 40:13, VII; RSA 40:14,
    X), and a town on a fiscal year its meeting on the second Tuesday of May
    (RSA 39:1-a). Those two days are key dates too, named as the day some
    towns meet.

    The state primary, the second Tuesday in September of every
    even-numbered year (RSA 653:8). That text is in force until 1 January
    2028: 2026, 44:1 replaces it from then, and the new text is not on this
    disk, so no primary from 2028 on is dated here. PRIMARY_UNTIL says so;
    dating one needs the new text read, not guessed.

  NOT HERE, because no document or rule on this disk fixes them: the
  presidential primary, whose day the Secretary of State sets (RSA 653:9);
  the 2027-2028 term's deadlines, until the chambers' calendars print them
  and legislative_year.TERMS holds them; and city elections.

THE STATUS BOX'S DEADLINE, BY ONE RULE (next_deadline): the nearest deadline
on or after the day. A deadline is the last day of a filing period, or a
one-day row of the schedule that is the last day for something -- not a
sitting (Organization Day, a session's first day, a veto day), not an
election, and not the first day of filing, which its own document calls a
"first day". Elections and town meetings stand in Coming up beside it; they
are dates for voters, not the legislature's deadlines. With no deadline
ahead in what legislative_year holds -- from 16 January 2027 until the
2027-2028 term's calendars are entered -- the box says nothing of one, and
the build says why (no_deadline_line).

WORDS. The names are legislative_year's own, so the schedule page, the
Calendar and the home page call a date the same thing; _names() holds each
in the site's other languages through say(), keyed by the English, and a
name it does not hold is said in English and printed by the build (unnamed),
and preflight's _key_dates_sourced fails until it is held. The
calendar card's sentence and source are the schedule page's, in English, as
the Calendar is.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import html
import re
from collections import namedtuple
from datetime import date, timedelta

import i18n
from i18n import say

# One key date. `day` and `until` are ISO days (`until` "" for a date of one
# day); `kind` is one of KINDS; `name` the English name; `who` "H", "S", "HS"
# or "" for a date that is everybody's; `what` one sentence and `src` its
# source line, both HTML, in English; `rule` the rule's name where the day
# is computed by one; `term` the legislative term it is a date of, or "".
KeyDate = namedtuple("KeyDate", "day until kind name who what src rule term")

# election   a state election
# town       town meeting day, the one the law sets and the two it allows
# session    the chambers sit: Organization Day, a session's first day, veto day
# opens      the first day of filing, where its document names one day
# period     a filing period, first day to last
# deadline   the last day for something
KINDS = ("election", "town", "session", "opens", "period", "deadline")
DEADLINE_KINDS = ("deadline", "period")

# The day the RSA 653:8 this file reads stops being the law (2026, 44:1).
PRIMARY_UNTIL = date(2028, 1, 1)


def _day(iso):
    return date.fromisoformat(str(iso)[:10])


def second_tuesday(year, month):
    """The second Tuesday of a month: the day RSA 39:1 and RSA 669:1 set for
    town meeting in March, RSA 40:13 allows in April and May, and RSA 653:8
    sets for the state primary in September."""
    first = date(int(year), int(month), 1)
    return first + timedelta(days=(1 - first.weekday()) % 7 + 7)


def town_meeting_day(year):
    """The second Tuesday of March (RSA 39:1; RSA 669:1, I)."""
    return second_tuesday(year, 3)


def state_primary(year):
    """The second Tuesday in September of an even-numbered year (RSA 653:8),
    or None: an odd year has none, and from 2028 the day is the new text's,
    which is not on this disk (PRIMARY_UNTIL)."""
    year = int(year)
    if year % 2:
        return None
    d = second_tuesday(year, 9)
    return d if d < PRIMARY_UNTIL else None


_SECTIONS = {}

# THE TABLE THE LAWS PAGES BESIDE THIS ONE ARE BUILT FROM: db/NH_RSA.psv in
# the folder the build runs in. That is rsa.TABLE in a real build, which runs
# from the repository, and the fixture's own two-chapter table where preflight
# builds a site (build_rsa.py --db db). Read from rsa.TABLE whatever the
# folder, the fixture's calendar linked RSA 39:1, 40:13, 653:8 and 669:1 on a
# machine that holds the real table, to Laws pages its build never wrote, and
# the dry run of 24 October 2026 stopped at the link check; here, with no
# table, nothing was linked and the check passed.
TABLE_HERE = Path("db") / "NH_RSA.psv"


def _sections_on_disk():
    """{"39:1", "39:1-A", ...}: the sections of the statute table the Laws
    pages are built from (TABLE_HERE), empty where it is not here. Read once
    a run for each folder, by each row's heading alone, which is a second's
    reading where loading the whole table is not."""
    table = TABLE_HERE.resolve()
    if table not in _SECTIONS:
        got = set()
        try:
            if table.is_file():
                with open(table, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        f = line.split("|", 7)
                        m = re.match(r"Section (\S+?) ", f[6]) if len(f) > 6 else None
                        if m:
                            got.add(m.group(1).upper())
        except Exception:                                    # noqa: BLE001
            got = set()
        _SECTIONS[table] = got
    return _SECTIONS[table]


def _law(*addrs):
    """RSA citations, each a link to the site's own page of its section
    (build_rsa.href, which every address of a chapter's page asks) where the
    table the Laws pages are built from holds it (TABLE_HERE), and plain
    words where it does not, so no link leads to a page the build did not
    write (build_bill_pages.law_href does the same)."""
    try:
        import build_rsa
        link = build_rsa.href
    except Exception:                                        # noqa: BLE001
        link = None
    held = _sections_on_disk() if link else set()
    out = []
    for a in addrs:
        sec = a.split(",")[0]
        words = html.escape(f"RSA {a}")
        out.append(f'<a href="{html.escape(link(sec), quote=True)}">{words}</a>'
                   if sec.upper() in held else words)
    return "; ".join(out)


# The days the law fixes that legislative_year does not hold: (rule, month,
# kind, name, who, what, the law's words, the RSA sections).
TOWN_RULES = (
    ("town-march", 3, "Town meeting day",
     "Towns hold their annual meeting: voters elect town officers and settle the "
     "town's other business.",
     "By law, the second Tuesday of March", ("39:1", "669:1, I")),
    ("town-april", 4, "Town meeting day in towns that chose April",
     "Towns that adopted official ballot voting and chose April hold their voting "
     "day on this day instead of in March.",
     "By law, the second Tuesday in April, where a town chose it",
     ("40:13, VII", "40:14, X")),
    ("town-may", 5, "Town meeting day in towns that chose May",
     "Towns that adopted official ballot voting and chose May, and towns on a fiscal "
     "year that chose May, hold their meeting or voting day on this day.",
     "By law, the second Tuesday in May, where a town chose it",
     ("40:13, VII", "40:14, X", "39:1-a")),
)
PRIMARY = ("primary", "State primary",
           "Voters choose each party's candidates for November's general election.",
           "By law, the second Tuesday in September of an even-numbered year",
           ("653:8",))


def _by_rule(years):
    """The days the statutes fix, for each of `years`."""
    out = []
    for y in years:
        for rule, month, name, what, words, law in TOWN_RULES:
            out.append(KeyDate(second_tuesday(y, month).isoformat(), "", "town", name, "",
                               html.escape(what).replace("&#x27;", "&rsquo;"),
                               f"{words}: {_law(*law)}.", rule, ""))
        d = state_primary(y)
        if d:
            rule, name, what, words, law = PRIMARY
            out.append(KeyDate(d.isoformat(), "", "election", name, "",
                               html.escape(what).replace("&#x27;", "&rsquo;"),
                               f"{words}: {_law(*law)}.", rule, ""))
    return out


def _kind(st):
    """What one of legislative_year's rows is, from its rule and from the
    words its own documents print beside its date."""
    # The 2024 election is dated by the next term's first calendar, which
    # prints it, rather than by its rule: its name says what it is.
    if st.rule == "election" or st.name.lower() == "general election":
        return "election"
    if st.rule in ("org", "open"):
        return "session"
    words = " ".join(w for _doc, _day, w in st.cites).lower()
    if re.search(r"\bveto day\b|\bwill meet\b", words) or st.name.lower().startswith("veto day"):
        return "session"
    if st.until:
        return "period"
    if words.startswith("first day"):
        return "opens"
    return "deadline"


def _from_schedule(today, root):
    """The dated rows of legislative_year's timeline for every term it
    checks on `today`, each once: an entered term's row is kept over the
    skeleton's for the same day and rule (Organization Day ends one term and
    begins the next)."""
    import legislative_year as LY
    links = LY._addresses(root)
    out, seen = [], set()
    for term in LY.checked_terms(today):
        problems, _checked, _absent = LY.verify(root, terms=[term])
        bad = {key: why for key, why in problems if key.startswith(term + " |")}
        for season in LY.seasons_of(term):
            for st in season.steps:
                if not st.day or st.subs or not LY._cited_ok(term, st, bad):
                    continue
                sig = ("rule", st.rule, st.day) if st.rule else ("row", st.name, st.day)
                if sig in seen:
                    continue
                seen.add(sig)
                docs = [doc for doc, _d, _w in st.cites]
                what = LY.T(st.what).replace("{next}", LY._dash(LY._next(term)))
                src = LY.RULE_WORDS.get(st.rule, "") + LY.cite_html(docs, links)
                out.append(KeyDate(st.day, st.until, _kind(st), st.name, st.who, what, src,
                                   st.rule, term))
    return out


_EVENTS = {}


def events(today=None, root=Path(".")):
    """Every key date, in date order: legislative_year's rows for the terms
    it checks on `today`, and the statutes' days from 2025 (the Calendar's
    first year) to the year after `today`'s. Worked out once a run for a
    day and a folder."""
    import build_date
    today = today or build_date.today()
    if isinstance(today, str):
        today = _day(today)
    k = (today.isoformat(), str(Path(root).resolve()))
    if k not in _EVENTS:
        evs = _from_schedule(today, Path(root)) + _by_rule(range(2025, today.year + 2))
        _EVENTS[k] = sorted(evs, key=lambda e: (e.day, KINDS.index(e.kind), e.name))
    return _EVENTS[k]


def occurrences(evs):
    """[(day, event, role)] in date order: each one-day date on its day, and
    a filing period on its first day and on its last."""
    out = []
    for e in evs:
        if e.until and e.until != e.day:
            out += [(e.day, e, "first"), (e.until, e, "last")]
        else:
            out.append((e.day, e, ""))
    return sorted(out, key=lambda x: (x[0], KINDS.index(x[1].kind), x[1].name, x[2]))


def days(evs, lo=None, hi=None):
    """{day: [(event, role)]}: the occurrences from `lo` to `hi`, inclusive,
    either open."""
    lo, hi = (str(x)[:10] if x else "" for x in (lo, hi))
    out = {}
    for d, e, role in occurrences(evs):
        if (not lo or d >= lo) and (not hi or d <= hi):
            out.setdefault(d, []).append((e, role))
    return out


def ahead(evs, after, n):
    """The next `n` occurrences after the day `after`."""
    a = str(after)[:10]
    return [o for o in occurrences(evs) if o[0] > a][:n]


def next_deadline(evs, today):
    """(day, event, role) of the nearest deadline on or after `today`, or
    None: the rule the module's docstring gives."""
    t = str(today)[:10]
    for d, e, role in occurrences(evs):
        if d < t or e.kind not in DEADLINE_KINDS:
            continue
        if e.kind == "period" and role != "last":
            continue
        return d, e, role
    return None


# ---------------------------------------------------------------------------
# THE WORDS. Each name legislative_year gives a dated row, and each this file
# gives a rule's day, in the site's other languages: say() keyed by the
# English, so a name changed there asks for its translation again. Two of
# them carry a year, and are matched by their pattern.
# ---------------------------------------------------------------------------
_YEARLY = (
    (re.compile(r"The (\d{4}) session opens"), "The {year} session opens"),
    (re.compile(r"Senate bill requests for (\d{4})"), "Senate bill requests for {year}"),
    (re.compile(r"House bill requests for (\d{4})"), "House bill requests for {year}"),
)


def _names(lang):
    """{English name: the name in `lang`}."""
    return {
        "General election": say(lang, "cal.kd.general_election", "General election"),
        "State primary": say(lang, "cal.kd.state_primary", "State primary"),
        "Town meeting day": say(lang, "cal.kd.town_meeting", "Town meeting day"),
        "Town meeting day in towns that chose April": say(
            lang, "cal.kd.town_april", "Town meeting day in towns that chose April"),
        "Town meeting day in towns that chose May": say(
            lang, "cal.kd.town_may", "Town meeting day in towns that chose May"),
        "Organization Day": say(lang, "cal.kd.organization_day", "Organization Day"),
        "The session opens": say(lang, "cal.kd.session_opens", "The session opens"),
        "Veto day": say(lang, "cal.kd.veto_day", "Veto day"),
        "Veto day in the House": say(lang, "cal.kd.veto_day_house", "Veto day in the House"),
        "Veto day in the Senate": say(lang, "cal.kd.veto_day_senate", "Veto day in the Senate"),
        "Crossover": say(lang, "cal.kd.crossover", "Crossover"),
        "Crossover in the House": say(lang, "cal.kd.crossover_house", "Crossover in the House"),
        "Crossover in the Senate": say(lang, "cal.kd.crossover_senate", "Crossover in the Senate"),
        "House members running again may file bill requests": say(
            lang, "cal.kd.house_incumbents", "House members running again may file bill requests"),
        "Senators running again may file bill requests": say(
            lang, "cal.kd.senate_incumbents", "Senators running again may file bill requests"),
        "Bill requests open to every representative": say(
            lang, "cal.kd.open_representatives", "Bill requests open to every representative"),
        "Bill requests open to every member": say(
            lang, "cal.kd.open_members", "Bill requests open to every member"),
        "Last day to file bill requests": say(
            lang, "cal.kd.last_requests", "Last day to file bill requests"),
        "Last day to request a Senate bill": say(
            lang, "cal.kd.last_senate_request", "Last day to request a Senate bill"),
        "House sponsors sign off": say(lang, "cal.kd.house_signoff", "House sponsors sign off"),
        "Senate sponsors sign off": say(lang, "cal.kd.senate_signoff", "Senate sponsors sign off"),
        "Last day to introduce House bills": say(
            lang, "cal.kd.introduce_house", "Last day to introduce House bills"),
        "Last day to act on the other chamber's bills": say(
            lang, "cal.kd.act_other", "Last day to act on the other chamber's bills"),
        "Last day to act on committee of conference reports": say(
            lang, "cal.kd.act_conference", "Last day to act on committee of conference reports"),
        "Retained bills reported": say(lang, "cal.kd.retained", "Retained bills reported"),
        "Interim study reports due": say(lang, "cal.kd.interim_study", "Interim study reports due"),
    }


def _yearly(lang, en):
    for pat, form in _YEARLY:
        m = pat.fullmatch(en)
        if not m:
            continue
        y = m.group(1)
        if form.startswith("The"):
            return say(lang, "cal.kd.year_opens", "The {year} session opens", year=y)
        if form.startswith("Senate"):
            return say(lang, "cal.kd.senate_requests", "Senate bill requests for {year}", year=y)
        return say(lang, "cal.kd.house_requests", "House bill requests for {year}", year=y)
    return None


# Names asked for in a language and not held, for the build to say once.
UNNAMED = set()


def name(lang, e, role=""):
    """The key date's name in `lang`, with "(first day)" or "(last day)" for
    a filing period's two days. Plain text, for the caller to escape."""
    n = e.name
    if lang != i18n.DEFAULT:
        got = _names(lang).get(n) or _yearly(lang, n)
        if got is None:
            UNNAMED.add((lang, n))
        else:
            n = got
    if role == "first":
        return say(lang, "cal.kd.first_day", "{name} (first day)", name=n)
    if role == "last":
        return say(lang, "cal.kd.last_day", "{name} (last day)", name=n)
    return n


def named(lang, e):
    """Whether `lang` has the key date's own name (English always does)."""
    return lang == i18n.DEFAULT or e.name in _names(lang) or _yearly(lang, e.name) is not None


def who_word(lang, who):
    """Whose date it is, in words: "" for everybody's."""
    if who == "H":
        return say(lang, "cal.kd.house", "House")
    if who == "S":
        return say(lang, "cal.kd.senate", "Senate")
    if who == "HS":
        return say(lang, "cal.kd.both", "Both chambers")
    return ""


def unnamed(out=print):
    """Say each name a page in another language had to give in English."""
    for lang, n in sorted(UNNAMED):
        out(f"  {lang}: the key date {n!r} has no name in key_dates._names(); "
            "it is said in English")
    return len(UNNAMED)


# ---------------------------------------------------------------------------
# DRAWING. The Calendar's card, and the home page's row, list and line.
# ---------------------------------------------------------------------------
def _esc(s):
    return html.escape(str(s or ""), quote=True).replace("&#x27;", "&rsquo;")


def _attr(s):
    return html.escape(str(s or ""), quote=True)


def card_html(e, role, day, lang="en"):
    """A key date as a card among the day's meetings, on the Calendar and
    in the home page's Coming up alike: its name, the Important Date chip in
    its colour and whose date it is, opening on the schedule page's sentence
    and source. Its own class, never a meeting's (calmeet): WEEK_JS reads it
    as an entry of the Important Dates box, and nothing that counts meetings
    counts it. `day` is the day it is drawn on: its first or last for a
    filing period."""
    from components import chip
    nm = name(lang, e, role)
    body = "H S" if e.who in ("", "HS") else e.who
    who = who_word(lang, e.who)
    return ('<details class="calkd" data-who="date" data-kinds="date"'
            f' data-kd="{_attr(e.kind)}" data-date="{_attr(day)}"'
            f' data-cmte="{_attr(nm.lower())}" data-body="{_attr(body)}"><summary>'
            f'<span class="calcmte">{_esc(nm)}</span>'
            + chip(say(lang, "cal.kd.chip", "Important Date"), "calkind k-date")
            + (f'<span class="calwho">{_esc(who)}</span>' if who else "")
            + '<span class="caret"></span></summary><div class="calbody">'
            f'<p class="calnote">{e.what}</p><p class="kdsrc">{e.src}</p>'
            "</div></details>")


def deadline_html(evs, today, lang="en"):
    """The status box's line: the next deadline (next_deadline), named with
    its chamber where its name does not say it, and its day -- "until" its
    day for a filing period. Retires the day after (until_attrs). "" where
    there is none."""
    from components import date_words, until_attrs
    got = next_deadline(evs, today)
    if not got:
        return ""
    d, e, role = got
    nm = name(lang, e, "")
    if e.who in ("H", "S") and ("House" if e.who == "H" else "Senate") not in e.name:
        nm = f"{nm} ({who_word(lang, e.who)})"
    t = str(today)[:10]
    when = date_words(d, "short" if d[:4] == t[:4] else "medium", lang)
    said = (say(lang, "state.deadline_until", "{name}, until {date}", name=_esc(nm), date=_esc(when))
            if e.kind == "period" else
            say(lang, "state.deadline_on", "{name}, {date}", name=_esc(nm), date=_esc(when)))
    gone = (_day(d) + timedelta(days=1)).isoformat()
    # A Spanish short date ends in its own full stop ("18 nov.").
    return (f'<p class="statenote statedue"{until_attrs(gone, today)}>'
            f'<b>{say(lang, "state.deadline", "Next deadline:")}</b> {said}'
            + ("" if said.endswith(".") else ".") + "</p>")


def no_deadline_line(evs, today):
    """What the build says where the status box names no deadline."""
    if next_deadline(evs, today):
        return ""
    return ("  index.html: no deadline ahead of " + str(today)[:10] + " in "
            "legislative_year.TERMS, so the status box names none; the next term's "
            "deadlines are entered there when the chambers' calendars print them")


# ---------------------------------------------------------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description="The key dates, with their sources. No network.")
    ap.add_argument("--day", default="", help="as on this day (YYYY-MM-DD); the build's day by default")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    import build_date
    today = _day(a.day) if a.day else build_date.today()
    evs = events(today, Path(a.root))
    strip = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s))     # noqa: E731
    for d, e, role in occurrences(evs):
        print(f"{d}  {e.kind:<8} {name('en', e, role)}"
              + (f" [{who_word('en', e.who)}]" if e.who else "")
              + f"\n            {strip(e.src)}")
    got = next_deadline(evs, today)
    print(f"\n{len(evs)} key dates. The status box on {today}: "
          + (f"{name('en', got[1])}, {got[0]}" if got else "no deadline ahead"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
