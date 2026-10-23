#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-16.7
"""
Who November's election sent to the General Court, for the weeks before they sit.

    python3 src/parse/build_members_elect.py                # site/members_elect.json, or none, and why
    python3 src/parse/build_members_elect.py --site site --collected collected

WHAT IT READS. The newest collected/election_<year>.json, which is what the
Secretary of State said about the State Representative and State Senate
races of one general election, in this project's shape (below); the site
data's roster, site/legislators.json and site/former.json; the district
table, site/districts.json; site/meta.json for the newest term the site
describes; and the person's corrections/members_elect.json, which it reads
and never writes, and which may be absent.

WHAT IT WRITES. site/members_elect.json, the one file every page draws a
member-elect from, or nothing. Nothing else: the roster files are read and
left byte for byte as the site data wrote them. Every page reads the file
through for_pages(), below, which holds the same window, and through
nothing else.

THE PERSON'S DECISIONS OF 16 OCTOBER 2026, which this holds and does not
reopen:

  1. A MEMBER-ELECT NEVER ENTERS THE ROSTER. A dozen builders read
     site/legislators.json as "who sits now" and the night's census gates
     count it; site/former.json is kept apart from it for the same reason. So
     members-elect have their own file and no other.
  2. THEY RETIRE BY THEMSELVES. The file is written only while the build's
     day (build_date.today()) is after the election and before Organization
     Day -- the first Wednesday of December, 2 December 2026
     (proceedings.organization_day) -- and the site's newest term
     (site/meta.json terms[0]) is still the one before theirs. A build on
     Organization Day, a build once the New term run has turned terms[0] to
     their term, and a build before the election each delete the file and say
     why. Retiring on 2 December holds even if the General Court's files have
     not turned by then: the old roster then shows alone until they do.
  3. A LINK ONLY ON A CERTAIN MATCH. A stranger's record under a
     member-elect's name is worse than a missing link (member_links.py says
     why, from the two Patrick Longs). A winner is linked to a page only as
     a sitting member in the same seat, as exactly one former member of
     that name whose recorded county is the race's, or -- widened at the
     person's word on 17 October 2026, after the 2024 test -- as the one
     sitting member of exactly that name, who ran for another seat
     (auto_link and moved() say on what); anything less is drawn unlinked
     and printed here for the person to settle in the hand file.
  4. A RACE COUNTS AS FINAL once posted and past its recount deadline, or
     once its recount result is out. The deadline is the person's to enter
     in the hand file ("recount_deadline", the last day a recount may be
     asked for), because it is not in the Secretary of State's results and
     this does not guess it; until the build's day is after it, every race
     is not final but one whose count the results file marks a recount's
     ("recounted"). Past it, the person marks a race whose recount was asked
     for not final in the hand file, until its result is out. A tie for the
     last seat is not final by itself.
  5. STATE REPRESENTATIVE AND STATE SENATOR ONLY. The Governor, the Council
     and Congress are the person's corrections/officials.json, and take
     office in January. Since 23 October 2026 their successors are that
     file's too, each record's "elect", and this module holds the file's one
     reader, read_officials(), which puts a successor in office on its day
     (THE OFFICES THE HAND FILE KEEPS, below); nothing of it reaches
     site/members_elect.json.

THE RESULTS FILE, collected/election_<year>.json -- written by
src/parse/parse_sos_results.py, the reader of the Secretary of State's own
files, run by a person and committed so the diff is the review. It was
written against the 2024 files on 17 October 2026, and
src/parse/score_members_elect.py scores this rule on them;
tests/election_fixture.json is the shape, made up:

    {"_source": [{"file": "records/sources/...", "url": "...",
                  "saved": "2026-11-05", "sha256": "..."}],
     "election": "2026-11-03", "term": "2027-2028",
     "races": {"H|Rockingham|13": {"seats": 2, "floterial": false,
                                   "towns": ["Raymond", "Stratham"],
                                   "candidates": [{"name": "Jodi Nelson",
                                       "party": "r", "votes": 5120,
                                       "write_in": false, "elected": true}],
                                   "scatter": 12},
               "S|24": {...}}}

A race's key is site/districts.json's: "H|<County>|<district>" for the
House, "S|<district>" for the Senate. A name is first name first, as the
Secretary of State prints it. A party is its letters in lower case, joined
by "/" where the candidate was cross-nominated ("r/d"); "" where none was
printed (a write-in). `elected` is true, false, or null where the count does
not decide it: a tie for the last seat. Scatter is counted and never drawn.
A race may carry "recounted": true where its count is a recount's result,
which makes it final before the recount deadline has passed. Each _source's
sha256 is held to the saved file when it is on disk.

THE FILE IT WRITES, site/members_elect.json:

    {"election": "2026-11-03", "takes_office": "2026-12-02",
     "term": "2027-2028", "sources": ["https://..."],
     "races": {"S|24": {"seats": 1, "not_final": 0, "held": 0,
                        "elected": [{"n": "Debra Altschiller", "p": "D",
                                     "k": "sitting", "id": "377207",
                                     "s": "debra-altschiller-sd-24"}]},
               "H|Rockingham|32": {"seats": 1, "not_final": 0, "held": 0,
                                   "elected": [{"n": "Pat Newell", "p": "R/D",
                                                "k": "new"}]}, ...}}

Every race the district table names is there, the Senate first. `k` is
sitting, former or new; `id` and `s` (the page's slug) are there only on a
link. `not_final` and `held` count seats; `recount` is true where the hand
file says one was requested. A race's seats less its elected and its not
final is the number of seats with no member-elect on file, held ones among
them, and the pages say so. No reason the person gave is in it: those are
private.

THE HAND FILE, corrections/members_elect.json, keyed by the election it
settles so that one election's answers never reach another's:

    {"2026-11-03": {
        "recount_deadline": "2026-11-13",
        "matches":   {"H|Rockingham|13": {"John Smith": "900002",
                                          "Pat Newell": null}},
        "not_final": {"H|Rockingham|8": {"recount": true, "seats": 1,
                                         "why": "private"}},
        "held":      {"S|24": {"Debra Altschiller": "private"}}}}

`recount_deadline` is the last day a recount may be asked for, as the
Secretary of State gives it; null or absent until the person knows it, and
until then no race is final but a recounted one (rule 4). `matches` names
the member a winner is (a sitting or a former member's id), or null for
"confirmed new"; it is the person's word and is taken over the rule, which
is printed where the two differ. `not_final` marks seats of a race not final
-- all of them where `seats` is not given -- and the winners with the fewest
votes give way to them. `held` keeps a winner off the pages.

IT PRINTS, FOR THE PERSON, every winner it could not link with certainty and
why, every new person, and every race whose elected, not final and held do
not add up to its seats -- silence is not success -- and, while the recount
deadline has not passed, that no race is final yet. A results file or a hand
file it cannot read, or a source whose sha256 is not the one the results
name, stops it, having removed any file the last build left, and says why on
stderr, where build_all reads a failed step's reason: a hand file it could
not read might have marked a race not final. So does any error nobody
foresaw.

Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import hashlib
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

import build_date
import proceedings
from member_links import COUNTIES, SHORT, first_names, same_first, split_name, surname

# The file every page draws from, in site/. Named once, apart from where it
# is written: the hand file has the same name in corrections/, and preflight's
# guard over that folder reads a build_ script's lines for the name.
OUT_NAME = "members_elect.json"
HAND_DEFAULT = Path("corrections") / "members_elect.json"

RESULTS_RE = re.compile(r"^election_(\d{4})\.json$")
# A county is any run of letters, accented ones too: a "Coös" in the district
# table would otherwise be no key, and stop the step on a race it cannot order.
KEY_RE = re.compile(r"^(?:H\|([^\W\d_]+)\|([1-9]\d*)|S\|([1-9]\d*))$")
DAY_RE = re.compile(r"^\d{4}-\d\d-\d\d$")

# A SUFFIX ON ONE SIDE ONLY IS PASSED OVER; TWO THAT DIFFER ARE NOT A MATCH.
# Until 17 October 2026 a suffix on one side alone refused the link, and the
# 2024 test showed what that cost: four members re-elected to their own seats
# were printed with a suffix their record does not carry ("Dick H. Thackston
# III", "James W. Tierney Jr.", "Charles R. Melvin Sr.", "Thomas L. Kaczynski
# Jr."), and all four went to the person, who widened the rule. A father and a
# son who have both sat still part: written each with his own suffix they
# differ, and written without one both answer to the name, and two records
# answering is never a link (suffixes_agree).
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv)\b\.?", re.I)
# The words that begin a surname of more than one and never end a first name:
# "Charlie St. Clair" is St. Clair, not Clair, and a record of a "Clair,
# Charlie" is somebody else.
PARTICLES = {"van", "von", "de", "del", "della", "der", "di", "da", "du", "des", "la",
             "le", "st", "ste", "saint", "mac", "mc", "o", "ten", "ter", "dos", "das"}

NEW = "no sitting or former member of that name"


class Refused(Exception):
    """An input this cannot use: nothing is written, and the build stops."""


# ---- the election's dates --------------------------------------------------

def general_election(year):
    """The state general election of `year`: the Tuesday after the first
    Monday in November (build_site_v2.election_day says the same)."""
    d = datetime.date(int(year), 11, 2)
    while d.weekday() != 1:
        d += datetime.timedelta(days=1)
    return d


def term_after(year):
    """The term an even year's general election elects: 2026 elects 2027-2028."""
    return f"{int(year) + 1}-{int(year) + 2}"


def term_before(term):
    """"2027-2028" -> "2025-2026"."""
    a = int(str(term)[:4])
    return f"{a - 2}-{a - 1}"


def dates_why(today, election, takes_office):
    """Why no member-elect is shown on `today`, by the calendar alone, or ""
    between the day after the election and the day before Organization Day."""
    if today <= election:
        return (f"the build's day, {today}, is not after the election of {election}: a build "
                "before the results shows none")
    if today >= takes_office:
        return (f"the build's day, {today}, is on or after Organization Day, {takes_office}, "
                "when they take office: they retire that day")
    return ""


def term_why(newest, term):
    """Why no member-elect is shown while the site's newest term is
    `newest`, or "" while it is the one before theirs."""
    if newest == term_before(term):
        return ""
    return (f"the site's newest term is {newest or 'not on file'}, not {term_before(term)}: "
            + ("the term is theirs now, and the roster says who sits" if newest == term
               else "the site is not the one this election's members-elect follow"))


def window(today, election, takes_office, newest, term):
    """Why no member-elect is shown, or "" while they are: after the
    election, before Organization Day, and while the site's newest term is
    the one before theirs (rule 2)."""
    return dates_why(today, election, takes_office) or term_why(newest, term)


# ---- names -----------------------------------------------------------------

def fold(s):
    """A name with its accents taken off the letters, so that "Choinière" on
    one side and "Choiniere" on the other read as one name."""
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")


def readings(raw):
    """([(surname, first name as written), ...], suffixes): each way a name
    can be read, the surname as member_links.surname's letters.

    "Nelson, Jodi" says where its surname is, and has one reading. "Jodi
    Nelson", as a ballot prints a name, does not, and a surname can be more
    than one word -- "Rebecca Perkins Kwoka", "Matt Sabourin dit Choinière",
    both sitting -- so every split is a reading: Kwoka with Rebecca Perkins,
    and Perkins Kwoka with Rebecca. A split that would end a first name of
    more than one word on a particle is not one ("Charlie St. Clair" is St.
    Clair). Each reading
    still has to be a member's whole surname and fitting first name to
    match, and more than one member matching is never a link. A nickname in
    quotes is read as the roster writes one, in brackets: "Robert \"Bob\"
    Smith" is Robert (Bob)."""
    s = re.sub(r'"([^"]+)"', r"(\1)", fold(raw))
    sfx = frozenset(m.lower() for m in SUFFIX.findall(s))
    s = SUFFIX.sub("", s)
    s = re.sub(r"\s*,(?:\s*,)+", ",", s)
    s = " ".join(s.split()).strip(" ,")
    if "," in s:
        last, first = split_name(s)
        return ([(surname(last), first)] if surname(last) else []), sfx
    words = s.split()
    # A first name of one word is a first name, particle or not: Mac
    # Kittredge, a former member, is Mac.
    out = [(surname(" ".join(words[i:])), " ".join(words[:i])) for i in range(1, len(words))
           if i == 1 or re.sub(r"[^a-z]", "", words[i - 1].lower()) not in PARTICLES]
    if len(words) == 1:
        out.append((surname(words[0]), ""))
    return [(sur, first) for sur, first in out if sur], sfx


def answers(p, rd, test=same_first):
    """Does member `p` answer to a name read as `rd`: a reading's surname
    theirs, and its first name theirs by `test` -- first_equal, known_first,
    or member_links.same_first, the loosest, which also takes a bare prefix?"""
    return any(ps == s and test(f, pf) for s, f in rd for ps, pf in p["readings"])


def first_equal(a, b):
    """The same first name, letter for letter, in some form either gives
    ("Robert (Bob)" gives both): the rule for a former member, and where two
    members of one seat share a surname."""
    return bool(first_names(a) & first_names(b))


def known_first(a, b):
    """The same first name, or a short form member_links.SHORT lists for it
    (Bob and Robert, Sue and Susan): the rule for the seat's one sitting
    member of that surname.

    NEVER A BARE PREFIX (the review of 16 October 2026). same_first also
    takes any three letters that begin the other name, which is right for
    rejoining one member's two records of votes and wrong for a ballot: on
    the real roster it took "Joelle Alexander" to Rep. Joe Alexander's page
    and "Pat Cote" to Patricia Cote's. Pat may be Patrick or Patricia, so a
    name that fits only that way goes to the person."""
    xa, xb = first_names(a), first_names(b)
    return bool(xa & xb) or any(SHORT.get(x) == y or SHORT.get(y) == x for x in xa for y in xb)


def seat_first(a, b):
    """known_first, or a first name of four letters or more that the other
    begins with and runs on from by two letters or more: the rule for the
    seat's one sitting member of that surname, and for nobody else.

    Widened at the person's word on 17 October 2026, after the 2024 test.
    Three members re-elected to their own seats were printed under the start
    of the first name their record gives ("Chris Herbert" for Christopher,
    "Greg Hill" for Gregory, "Doug Thomas" for Douglas), which no list of
    short forms will ever hold whole. Four letters and never three, because
    three is Joe and Joelle, Pat and Patricia: the pages the review of 16
    October found a bare prefix taking. And two letters more, not one,
    because a name with one letter added is most often another person's name
    -- Louis and Louise, Paul and Paula, Robert and Roberta -- and that
    review held Louis Andrus off Rep. Louise Andrus's page."""
    if known_first(a, b):
        return True
    for x in first_names(a):
        for y in first_names(b):
            short, full = sorted((x, y), key=len)
            if len(short) >= 4 and len(full) >= len(short) + 2 and full.startswith(short):
                return True
    return False


def suffixes_agree(a, b):
    """No suffix on one side, or the same on both (the SUFFIX rule above):
    "Dick H. Thackston III" and "Thackston, Dick" agree; "John Smith Jr."
    and "Smith, Sr., John" do not."""
    return not a or not b or a == b


def reading_order(raw):
    """A name as the pages draw it, first name first: "Nelson, Jodi" is
    "Jodi Nelson", and "Smith, Jr., John" is "John Smith Jr."; a name
    already that way round is left as it is."""
    s = " ".join(str(raw or "").split())
    parts = [p.strip() for p in s.split(",") if p.strip()]
    sfx = [p for p in parts if SUFFIX.fullmatch(p)]
    rest = [p for p in parts if not SUFFIX.fullmatch(p)]
    if "," in s and len(rest) == 2:
        return " ".join([rest[1], rest[0]] + sfx)
    return s


def party_letters(raw):
    """"r" -> "R", "r/d" -> "R/D": a cross-nominated candidate keeps both."""
    return "/".join(p.strip().upper() for p in str(raw or "").split("/") if p.strip())


# ---- the races the district table names ------------------------------------

def number(x):
    """A district or a count of seats as a whole number above nought, or None:
    13, "13" and " 013 " are 13."""
    s = str(x if x is not None else "").strip()
    return int(s) if s.isdecimal() and s.isascii() and int(s) > 0 else None


def races_on_file(districts):
    """{race key: {"seats", "floterial", "towns", "counties"}} from
    site/districts.json, which keys a race as the results do. A town with
    wards is listed by ward, "Manchester Ward 6", as the roster lists it."""
    out, clash = {}, []
    for town in sorted(districts or {}):
        wards = districts[town] or {}
        for ward in sorted(wards, key=lambda w: (len(str(w)), str(w))):
            d = wards[ward] or {}
            place = town if str(ward) in ("", "0") else f"{town} Ward {ward}"
            counties = {h.get("county") for h in d.get("house") or [] if h.get("county")}
            for h in d.get("house") or []:
                n, seats = number(h.get("district")), number(h.get("seats"))
                key = f"H|{h.get('county')}|{n}"
                # A district the table cannot name is said and left out,
                # never a crash: a crash would stop the build on a table a
                # page could still draw.
                if n is None or seats is None or not KEY_RE.match(key):
                    clash.append(f"{place} names a House district that is no race: county "
                                 f"{h.get('county')!r}, district {h.get('district')!r}, seats "
                                 f"{h.get('seats')!r}")
                    continue
                r = out.setdefault(key, {"seats": seats,
                                         "floterial": bool(h.get("floterial")),
                                         "towns": [], "counties": {h.get("county")}})
                if r["seats"] != seats:
                    clash.append(f"{key} is {r['seats']} seats in one town and "
                                 f"{seats} in {place}")
                r["towns"].append(place)
            if d.get("senate") and number(d["senate"]) is None:
                clash.append(f"{place} names a Senate district that is no number: "
                             f"{d['senate']!r}")
            elif d.get("senate"):
                key = f"S|{number(d['senate'])}"
                r = out.setdefault(key, {"seats": 1, "floterial": False, "towns": [],
                                         "counties": set()})
                r["towns"].append(place)
                r["counties"] |= counties
    return out, clash


def race_order(key):
    """The Senate first by number, then the House by county and number."""
    m = KEY_RE.match(key)
    return (0, "", int(m.group(3))) if m.group(3) else (1, m.group(1), int(m.group(2)))


def race_words(key):
    """"H|Rockingham|13" -> "Rockingham 13"; "S|24" -> "Senate district 24"."""
    m = KEY_RE.match(key)
    return f"Senate district {m.group(3)}" if m.group(3) else f"{m.group(1)} {m.group(2)}"


# ---- the results file ------------------------------------------------------

def newest_results(collected):
    """The newest collected/election_<year>.json, or None."""
    found = [(int(m.group(1)), p) for p in Path(collected).glob("election_*.json")
             if (m := RESULTS_RE.match(p.name)) and p.is_file()]
    return max(found)[1] if found else None


def read_results(path):
    """The results file, its election and term checked against each other
    and its races against the shape above. Refused when it cannot be used."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{path} will not read as JSON: {e}")
    if not isinstance(doc, dict):
        raise Refused(f"{path} is not an object")
    election = str(doc.get("election") or "")
    if not DAY_RE.match(election):
        raise Refused(f"{path} names no election day (\"election\": \"YYYY-MM-DD\")")
    year = int(election[:4])
    if year % 2 or general_election(year).isoformat() != election:
        raise Refused(f"{path}'s election, {election}, is not a state general election: that is "
                      f"{general_election(year - year % 2)} in its even year")
    if doc.get("term") != term_after(year):
        raise Refused(f"{path} says its winners serve {doc.get('term')!r}; the election of "
                      f"{election} elects {term_after(year)}")
    races = doc.get("races")
    if not isinstance(races, dict) or not races:
        raise Refused(f"{path} holds no races")
    bad = []
    for key, r in races.items():
        if not KEY_RE.match(str(key)):
            bad.append(f"{key!r} is not a race's key (H|<County>|<n> or S|<n>)")
            continue
        if not isinstance(r, dict) or not isinstance(r.get("seats"), int) or r["seats"] < 1:
            bad.append(f"{key} has no number of seats")
            continue
        cands = r.get("candidates")
        if not isinstance(cands, list):
            bad.append(f"{key} has no list of candidates")
            continue
        for c in cands:
            if not isinstance(c, dict) or not str(c.get("name") or "").strip():
                bad.append(f"{key} has a candidate with no name")
            elif "elected" not in c or c["elected"] not in (True, False, None):
                bad.append(f"{key}'s {c.get('name')} is neither elected, nor not, nor tied "
                           "(\"elected\": true, false or null)")
            elif not isinstance(c.get("votes"), int):
                bad.append(f"{key}'s {c.get('name')} has no count of votes")
        if not isinstance(r.get("recounted", False), bool):
            bad.append(f"{key}'s \"recounted\" is neither true nor false")
    if bad:
        raise Refused(f"{path}: " + "; ".join(bad[:6]) + (" ..." if len(bad) > 6 else ""))
    sources = doc.get("_source") or []
    if not isinstance(sources, list) or not sources:
        raise Refused(f"{path} names no _source: what the Secretary of State published, saved")
    return doc


def sources_hold(doc, root, notes):
    """Each _source's sha256 against the saved file, where it is on disk.
    A file changed since the reader ran is refused: the results would no
    longer be what it says."""
    for s in doc.get("_source") or []:
        f = Path(root) / str(s.get("file") or "")
        if not s.get("file") or not f.is_file():
            notes.append(f"the source {s.get('file')!r} is not on disk here, so its sha256 was "
                         "not checked")
            continue
        got = hashlib.sha256(f.read_bytes()).hexdigest()
        if got != s.get("sha256"):
            raise Refused(f"{s.get('file')} is not the file the results were read from: its "
                          f"sha256 is {got}, the results say {s.get('sha256')}. Run the reader "
                          "again over it")


def read_hand(path, election):
    """The person's entries for this election: {"matches", "not_final",
    "held"}, each a dict, empty where the file or the election is absent,
    and "recount_deadline", a day or None."""
    empty = {"matches": {}, "not_final": {}, "held": {}}
    p = Path(path)
    if not p.is_file():
        return dict(empty, recount_deadline=None), f"no {p.as_posix()}: nothing settled by hand"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{p.as_posix()} will not read as JSON ({e}); it may mark a race not "
                      "final, so nothing is drawn until it reads")
    mine = doc.get(election) if isinstance(doc, dict) else None
    if mine is None:
        return dict(empty, recount_deadline=None), f"{p.as_posix()} settles nothing for {election}"
    shape = (f"{p.as_posix()}'s \"{election}\" is not {{\"recount_deadline\": \"YYYY-MM-DD\" or "
             "null, \"matches\": {race: {name: id or null}}, \"not_final\": {race: {\"seats\": "
             "n, \"recount\": true, \"why\": \"...\"}}, \"held\": {race: {name: \"why\"}}}")
    if not isinstance(mine, dict) or any(not isinstance(mine.get(k) or {}, dict) for k in empty):
        raise Refused(shape)
    got = {k: mine.get(k) or {} for k in empty}
    # A DEADLINE THAT IS NO DAY, OR NOT AFTER THE ELECTION, IS REFUSED rather
    # than read as none: read as none it would hold every race back, and read
    # as a day it would let them all through, and either is a guess.
    deadline = mine.get("recount_deadline")
    if deadline is not None:
        try:
            ok = DAY_RE.match(str(deadline)) and \
                datetime.date.fromisoformat(deadline).isoformat() > election
        except (TypeError, ValueError):
            ok = False
        if not ok:
            raise Refused(f"{p.as_posix()}'s \"{election}\" -> \"recount_deadline\" is "
                          f"{deadline!r}: a day after the election (\"YYYY-MM-DD\"), or null "
                          "until it is known")
    got["recount_deadline"] = deadline
    # EVERY ENTRY IS READ OR REFUSED, never passed over. A not-final mark the
    # step could not read and went on without would put a race's winners on
    # the pages that the person had held back.
    bad = []
    for key, v in got["matches"].items():
        if not isinstance(v, dict) or any(x is not None and not isinstance(x, (str, int))
                                          for x in v.values()):
            bad.append(f"matches[{key!r}]")
    for key, v in got["not_final"].items():
        if not isinstance(v, dict) or ("seats" in v and not (
                isinstance(v["seats"], int) and v["seats"] >= 1)) or \
                not isinstance(v.get("recount", False), bool):
            bad.append(f"not_final[{key!r}]")
    for key, v in got["held"].items():
        if not isinstance(v, dict):
            bad.append(f"held[{key!r}]")
    if bad:
        raise Refused(shape + "; these are not: " + ", ".join(bad))
    return got, ""


# ---- who a winner is -------------------------------------------------------

def full_county(raw):
    """A county as the district table names it. The roster files write it
    both ways -- on 16 October 2026, 953 of former.json's 1,785 rows said
    "Hills", "Rock", "Straf" where the rest said Hillsborough -- and
    member_links.COUNTIES knows both."""
    s = str(raw or "").strip()
    return COUNTIES.get(re.sub(r"[^a-z]", "", s.lower()), s)


def seat_of(m):
    """A roster row's race key, or None where its seat is not one."""
    ch, dist = (m.get("chamber") or "")[:1].upper(), str(m.get("district") or "").strip()
    if not dist.isdigit():
        return None
    if ch == "S":
        return f"S|{int(dist)}"
    if ch == "H" and m.get("county"):
        return f"H|{full_county(m['county'])}|{int(dist)}"
    return None


class People:
    """The sitting and former members, read for matching: by seat and by
    surname, each row with its name's readings; and the election's ballot,
    every candidate of every race, winning or not, by surname (ballot_of)."""

    def __init__(self, sitting, former, ballot=()):
        self.by_id, self.by_seat = {}, defaultdict(list)
        self.by_sur = {"sitting": defaultdict(list), "former": defaultdict(list)}
        # The ballot is read for one rule, moved(): a sitting member who ran
        # for another seat links only where no other candidate answers to
        # their name. Without it that rule cannot be certain, and refuses.
        self.ballot, self.on_ballot = defaultdict(list), set()
        for key, name in ballot or ():
            self.on_ballot.add((key, name))
            rd, _sfx = readings(name)
            for sur in {s for s, _f in rd}:
                self.ballot[sur].append((key, name, rd))
        for kind, rows in (("sitting", sitting), ("former", former)):
            for m in rows or []:
                rd, sfx = readings(m.get("name"))
                p = {"kind": kind, "id": str(m.get("id")), "slug": m.get("slug") or "",
                     "readings": rd, "sfx": sfx, "county": full_county(m.get("county")),
                     "seat": seat_of(m), "label": m.get("display_full") or m.get("name") or ""}
                self.by_id.setdefault(p["id"], p)
                for sur in {s for s, _f in rd}:
                    self.by_sur[kind][sur].append(p)
                if kind == "sitting" and p["seat"]:
                    self.by_seat[p["seat"]].append(p)

    def named(self, kind, rd):
        """The sitting or former members a name read as `rd` might be, by
        surname alone, each once."""
        out = {}
        for s, _f in rd:
            for p in self.by_sur[kind].get(s, []):
                out.setdefault(p["id"], p)
        return list(out.values())

    def rivals(self, p, but):
        """The candidates on the ballot but `but` (race, name) who answer to
        member `p`'s name even loosely (member_links.same_first), each once."""
        out = {}
        for s, _f in p["readings"]:
            for key, name, rd in self.ballot.get(s, []):
                if (key, name) != but and answers(p, rd):
                    out.setdefault((key, name), None)
        return list(out)


def ballot_of(results):
    """[(race, name), ...]: every candidate the results file names, in every
    race, winning or not, for People's ballot."""
    return [(key, str(c.get("name"))) for key, r in (results.get("races") or {}).items()
            for c in (r or {}).get("candidates") or [] if str(c.get("name") or "").strip()]


def who(p):
    return f"{p['label']} [{p['id']}]"


def auto_link(key, name, people, races):
    """(the member a winner is, "") on a certain match, or (None, why not).

    1. Sitting, same seat: the same surname and the same first name, or a
       short form member_links.SHORT lists for it, or a first name of four
       letters or more the other begins with (seat_first) -- and, where two
       members of the seat share the surname (Hillsborough 1's two
       Mannions), the same first name.
    2. Former, returning: no sitting member of that name anywhere, and
       exactly one former record that answers to the name even loosely, whose
       first name is the same (first_equal) and whose recorded county is the
       race's (for the Senate, a county of its towns). "The same name and
       county" is the person's rule (16 October 2026), and the plan's rule 2
       says the same first name: Bob is not certainly that Robert, and Don
       was Donna Sytek.
    3. Sitting, another seat: the one sitting member of exactly that name,
       moved from the House, and no other candidate who answers to it
       (moved(), widened at the person's word on 17 October 2026).
    In each, a Jr., Sr. or numeral on one side only is passed over, and two
    that differ are no match (suffixes_agree; 17 October 2026).
    Never linked by rule: a first name that fits only by three letters, or
    by one letter more (Pat, Patricia; Louis, Louise); a sitting member of
    that name in another seat by a short form, or as a senator; a former
    member with no county; and a changed surname, which reads as a new
    person. Where the rule refuses, the test that refuses is the loose one,
    same_first: what might be somebody else is enough to send a name to the
    person."""
    rd, sfx = readings(name)
    if not rd:
        return None, "no surname could be read from the name"
    surs = {s for s, _f in rd}
    seat = [p for p in people.by_seat.get(key, [])
            if surs & {s for s, _f in p["readings"]}]
    fits = [p for p in seat if answers(p, rd, first_equal if len(seat) > 1 else seat_first)]
    if len(fits) > 1:
        return None, (f"{len(fits)} sitting members of {race_words(key)} answer to that name: "
                      + ", ".join(who(p) for p in fits))
    if fits:
        p = fits[0]
        if not suffixes_agree(p["sfx"], sfx):
            return None, (f"a Jr. or Sr. on each side, and not the same one: {who(p)} sits for "
                          f"{race_words(key)}")
        return p, ""
    near = [p for p in seat if answers(p, rd)]
    if near and len(seat) > 1:
        return None, (f"{len(seat)} sitting members of {race_words(key)} share the surname, and "
                      "the name fits only by a short form: " + ", ".join(who(p) for p in near))
    if near:
        return None, ("the first name fits only as the start of the sitting member's, by three "
                      "letters or one letter more, which may be somebody else's (Pat is Patrick "
                      f"or Patricia, Louis is not Louise): {who(near[0])} sits for "
                      f"{race_words(key)}")
    elsewhere = [p for p in people.named("sitting", rd) if p["seat"] != key and answers(p, rd)]
    if elsewhere:
        return moved(key, name, rd, sfx, elsewhere, people)
    former = [p for p in people.named("former", rd) if answers(p, rd)]
    if not former:
        return None, NEW
    loose = [p for p in former if not answers(p, rd, first_equal)]
    if len(former) > 1:
        return None, (f"{len(former)} former members of that name"
                      + (f", {len(loose)} of them by a short form or the start of the first name"
                         if loose else "") + ": "
                      + ", ".join(f"{who(p)} ({p['county'] or 'no county'})" for p in former))
    p = former[0]
    if loose:
        return None, ("the one former member who might be this winner has the first name only by "
                      f"a short form or as the start of it, which is not the same name: {who(p)}")
    if not p["county"]:
        return None, f"the one former member of that name has no county on record: {who(p)}"
    if p["county"] not in races[key]["counties"]:
        return None, (f"the one former member of that name sat in {p['county']}, not in "
                      f"{race_words(key)}'s county: {who(p)}")
    if not suffixes_agree(p["sfx"], sfx):
        return None, f"a Jr. or Sr. on each side, and not the same one: {who(p)}"
    return p, ""


def moved(key, name, rd, sfx, elsewhere, people):
    """(the sitting member, "") where a winner of race `key` is the one
    sitting member of exactly their name, who ran for another seat; or
    (None, why not). `elsewhere` is every sitting member of another seat who
    answers to the name even loosely.

    WIDENED AT THE PERSON'S WORD ON 17 OCTOBER 2026. Until then a sitting
    member of the name in another seat sent the winner to the person every
    time, and in 2024 that was eleven members who had moved. Ten link now --
    three representatives elected to the Senate, and seven to another House
    district of their own county -- on every one of these, and the eleventh,
    "Pat Long" for Rep. Patrick Long, does not, by the second:

      - exactly one sitting member, anywhere, answers to the name even
        loosely, by a short form or the start of the first name, and no
        former member does, as rule 2 asks of a former member that no
        sitting one answer: a former namesake might be the winner, coming
        back, while the sitting one retired;
      - their first name and surname are the winner's letter for letter
        (first_equal: "Richard R. Brown" is Richard, the initial no part of
        it), and a suffix agrees (suffixes_agree);
      - the move is from the House, either to another House district of the
        member's own county, or to the Senate, whose districts may cross a
        county line, so that there the name and its being the only one
        decide. A senator elected to another seat is the person's to settle;
      - and no other candidate on the ballot, in any race, winning or not,
        answers to that member's name even loosely. In 2024 Rep. Patrick
        Long ran for Senate 20 as "Pat Long" while a first-term Patrick N.
        Long won Hillsborough 26, in the county Rep. Long sat for: the exact
        name was the stranger's, and only the ballot shows there were two.
        So where the ballot was not given, the rule cannot know, and does
        not link."""
    if len(elsewhere) > 1:
        return None, ("two or more sitting members of that name hold other seats: "
                      + ", ".join(who(p) for p in elsewhere))
    p = elsewhere[0]
    there = p["seat"] or ""
    namesakes = [f for f in people.named("former", rd) if answers(f, rd)]
    if namesakes:
        return None, ("a sitting member of that name holds another seat, and a former member "
                      f"answers to it too: {who(p)}; "
                      + ", ".join(f"{who(f)} ({f['county'] or 'no county'})" for f in namesakes))
    if not answers(p, rd, first_equal):
        return None, ("a sitting member of that name holds another seat, and the first name is "
                      f"theirs only by a short form or its start: {who(p)}")
    if not suffixes_agree(p["sfx"], sfx):
        return None, (f"a sitting member of that name holds another seat, with a Jr. or Sr. not "
                      f"the winner's: {who(p)}")
    if not there:
        return None, f"a sitting member of that name has no seat on record: {who(p)}"
    if not there.startswith("H|"):
        return None, ("a sitting senator of that name, elected to another seat, which is the "
                      f"person's to settle: {who(p)}")
    county = KEY_RE.match(key).group(1)
    if county and county != there.split("|")[1]:
        return None, (f"a sitting member of that name sits for {race_words(there)}, in another "
                      f"county than {race_words(key)}: {who(p)}")
    if (key, name) not in people.on_ballot:
        return None, ("a sitting member of that name holds another seat, and the ballot was not "
                      f"read to show they are the one candidate of it: {who(p)}")
    rivals = people.rivals(p, (key, name))
    if rivals:
        return None, ("another candidate on the ballot answers to the name of the sitting member "
                      f"this might be, {who(p)}: "
                      + ", ".join(f"{n} ({race_words(k)})" for k, n in rivals))
    return p, ""


# ---- the races, decided ----------------------------------------------------

def recount_open(today, deadline, election):
    """Why no race is final yet on `today` but a recounted one, or "" once
    `today` is past the hand file's recount deadline (rule 4)."""
    if not deadline:
        return (f"no recount deadline is entered for the election of {election} "
                "(\"recount_deadline\" in the hand file), so no race is final but a recounted "
                "one, and every other is drawn as not final until it is")
    if str(today) <= str(deadline):
        return (f"the recount deadline, {deadline}, has not passed on {today}: no race is final "
                "but a recounted one, and every other is drawn as not final until it has")
    return ""


def members_elect(results, sitting, former, districts, hand, today):
    """(races, report): what site/members_elect.json says of each race, and
    what the person is to read, on the build's day `today`. Pure: nothing is
    read or written here."""
    on_file, clash = races_on_file(districts)
    people = People(sitting, former, ballot_of(results))
    pending = recount_open(today, hand.get("recount_deadline"), results.get("election"))
    report = {"unlinked": [], "new": [], "short": [], "notes": list(clash), "pending": pending}
    races_in = results.get("races") or {}
    for key in sorted(set(races_in) - set(on_file), key=race_order):
        report["notes"].append(f"{key} is in the results and in no district on file: not drawn")
    for kind in ("matches", "not_final", "held"):
        for key in sorted(set(hand[kind]) - set(races_in)):
            report["notes"].append(f"the hand file's {kind} names {key}, which the results "
                                   "do not hold")
    out, claims = {}, defaultdict(list)
    for key in sorted(on_file, key=race_order):
        seats = on_file[key]["seats"]
        r = races_in.get(key)
        row = {"seats": seats, "elected": [], "not_final": 0, "held": 0}
        out[key] = row
        if r is None:
            continue
        if r.get("seats") != seats:
            report["notes"].append(f"{key}: the results say {r.get('seats')} seat(s), the "
                                   f"district table {seats}")
        towns = sorted(r.get("towns") or [])
        if towns and towns != sorted(on_file[key]["towns"]):
            report["notes"].append(f"{key}: the results list {', '.join(towns)}; the district "
                                   f"table {', '.join(sorted(on_file[key]['towns']))}")
        cands = r.get("candidates") or []
        won = sorted((c for c in cands if c.get("elected") is True),
                     key=lambda c: (-c["votes"], c["name"]))
        tied = any(c.get("elected") is None for c in cands)
        if len(won) > seats:
            # More winners than seats is a reading gone wrong, not a result:
            # nobody is drawn, and the seats say no member-elect is on file.
            report["notes"].append(f"{key}: {len(won)} winners for {seats} seat(s); none drawn")
            won, tied = [], False
        not_final = seats - len(won) if tied else 0
        if not_final:
            report["notes"].append(f"{key}: the count ties for {not_final} seat(s), which are "
                                   "not final until a recount says who won")
        mine = hand["held"].get(key) or {}
        held = [c for c in won if c["name"] in mine]
        won = [c for c in won if c["name"] not in mine]
        for name in sorted(set(mine) - {c["name"] for c in held}):
            report["notes"].append(f"{key}: the hand file holds {name}, who is not a winner here")
        nf = hand["not_final"].get(key)
        if nf is not None:
            not_final = max(not_final, min(nf.get("seats") or seats, seats - len(held)))
            if nf.get("recount"):
                row["recount"] = True
        # BEFORE THE RECOUNT DEADLINE NO RACE IS FINAL but one the results
        # mark recounted (the person's rule, 16 October 2026): a winner drawn
        # the day after the count, before anyone could ask for a recount,
        # would be drawn as final when the rule says it is not.
        if pending and r.get("recounted") is not True:
            not_final = seats - len(held)
        drawn = max(0, seats - len(held) - not_final)
        row["not_final"], row["held"] = not_final, len(held)
        named = hand["matches"].get(key) or {}
        for name in sorted(set(named) - {c["name"] for c in cands if c.get("elected") is True}):
            report["notes"].append(f"{key}: the hand file matches {name}, who is not a "
                                   "winner here")
        # EVERY WINNER IS MATCHED, DRAWN OR NOT, so that a name the rule
        # cannot settle is put to the person while its race is still not
        # final, and is settled by the day it is drawn.
        for i, c in enumerate(won):
            entry = {"n": reading_order(c["name"]), "p": party_letters(c.get("party"))}
            rule, why = auto_link(key, c["name"], people, on_file)
            if c["name"] in named:
                v = named[c["name"]]
                p = people.by_id.get(str(v)) if v is not None else None
                if v is not None and p is None:
                    report["unlinked"].append((key, c["name"], f"the hand file names {v}, "
                                               "who is no sitting or former member"))
                elif (p or {}).get("id") != (rule or {}).get("id") and rule:
                    report["notes"].append(f"{key}: the hand file takes {c['name']} to be "
                                           f"{who(p) if p else 'new'}; the rule had {who(rule)}")
            else:
                p = rule
                if not p:
                    report["new" if why == NEW else "unlinked"].append((key, c["name"], why))
            if i >= drawn:
                continue
            entry["k"] = p["kind"] if p else "new"
            if p:
                entry["id"], entry["s"] = p["id"], p["slug"]
                claims[p["id"]].append((key, c["name"], entry))
            row["elected"].append(entry)
        if len(row["elected"]) + row["not_final"] + row["held"] != seats:
            report["short"].append((key, seats, len(row["elected"]), row["not_final"],
                                    row["held"], True))
    # ONE PERSON, ONE SEAT. Two winners taken to one member are neither linked.
    for mid, hits in claims.items():
        if len(hits) > 1:
            for key, name, entry in hits:
                entry["k"] = "new"
                entry.pop("id", None)
                entry.pop("s", None)
                report["unlinked"].append((key, name, f"{len(hits)} winners were taken to "
                                           f"{who(people.by_id[mid])}"))
    for key in sorted(set(on_file) - set(races_in), key=race_order):
        report["short"].append((key, on_file[key]["seats"], 0, 0, 0, False))
    report["short"].sort(key=lambda x: race_order(x[0]))
    return out, report


# ---- what the pages read ---------------------------------------------------

def for_pages(site):
    """site/members_elect.json as every page draws it, or None where there
    is nothing to draw.

    ONE READER, BESIDE THE ONE WRITER (the pages' pass, 16 October 2026).
    The town pages and places.json, the Officials page's tab, the legislator
    pages and the district map each draw a member-elect from this and from
    nothing else -- never from the roster -- so that no two of them can come
    to read the file differently, and none of them names the file itself.

    THE PAGES HOLD THE WINDOW TOO. The step removes the file outside the
    weeks between the election and Organization Day, and check_site refuses
    one left on the night. But a page builder is also run on its own, by a
    person, on a site the step has not touched since: a file written on 1
    December and a town page built from it on the 2nd would put members-elect
    in the page the day they take office, hidden by until_attrs and still
    there. So a file outside the window, by the step's own rule (window()),
    is not drawn, and the builder says why.

    A FILE THAT WILL NOT READ STOPS THE BUILDER. The step writes it whole, so
    one that does not parse, or names no days or no races, is a fault to
    look at -- silence is not success -- and not a block to leave out."""
    p = Path(site) / OUT_NAME
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        election = datetime.date.fromisoformat(doc["election"])
        takes_office = datetime.date.fromisoformat(doc["takes_office"])
        term, races = str(doc["term"]), doc["races"]
        bad = [k for k, r in races.items()
               if not KEY_RE.match(k) or not isinstance(r, dict)
               or not isinstance(r.get("elected"), list) or not isinstance(r.get("seats"), int)]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise SystemExit(f"{p.as_posix()} will not read as the members-elect ({type(e).__name__}: "
                         f"{e}): build_members_elect.py writes it whole, so this is a fault to look "
                         "at, not a block to leave out")
    if bad:
        raise SystemExit(f"{p.as_posix()} holds {len(bad)} race(s) not in the shape the step "
                         f"writes, {', '.join(map(repr, bad[:4]))}: a fault to look at, not a block "
                         "to leave out")
    try:
        meta = json.loads((Path(site) / "meta.json").read_text(encoding="utf-8"))
        terms = meta.get("terms") if isinstance(meta, dict) else None
    except (OSError, ValueError):
        terms = None
    newest = terms[0] if isinstance(terms, list) and terms else None
    why = window(build_date.today(), election, takes_office, newest, term)
    if why:
        print(f"  members-elect: {p.as_posix()} is not drawn -- {why}")
        return None
    n = sum(len(r["elected"]) for r in races.values())
    print(f"  members-elect: drawn from {p.as_posix()}, {len(races)} races, {n} elected, "
          f"until {doc['takes_office']}")
    return doc


# ---- the offices the hand file keeps ---------------------------------------
#
# THE OFFICES THE HAND FILE KEEPS, AND WHO HOLDS EACH ON THE BUILD'S DAY (the
# person's approval of 23 October 2026). corrections/officials.json is the
# person's file of the offices no General Court file names: the Governor and
# the Council, Congress, the Secretary of State, the Treasurer, the Attorney
# General, the department heads, the judges and the county officers. Their
# holders change at an election, or when the legislature chooses in
# December, and take office weeks later: Congress on 3 January (the
# Twentieth Amendment); the Governor and the Council in January, though the
# Constitution on this disk (Part Second, Articles 42 and 60) fixes only the
# day their votes are laid before the House and Senate, the first Wednesday
# after the first Tuesday, and no day for the oath. So the day is never
# worked out here: a record carries its successor under "elect" with the day
# they take office, the person's to enter, and from that day every page
# draws the successor as the holder. The file is edited once, when the
# result is certified, and nobody has to touch it on the day.
#
# ONE READER. The Officials page's tabs (build_pages), the town pages and
# places.json (build_town_pages), the district map (build_district_map) and
# the officers' hand entries (officers) all read the file through
# read_officials() and through nothing else, so no two pages can differ
# about who holds an office; preflight reads the code for it.

OFFICIALS = Path("corrections") / "officials.json"
# What a record says of the office, and keeps when a successor takes it. Its
# other plain fields -- the name, the party, the ways to reach them, where and
# when they were read -- are the holder's, and leave with them.
OFFICE_FIELDS = frozenset({"office", "scope", "about", "district", "title", "department"})


def _day(today):
    """`today` as a date: the build's day where it is None."""
    if today is None:
        return build_date.today()
    if isinstance(today, datetime.datetime):
        return today.date()
    if isinstance(today, datetime.date):
        return today
    return datetime.date.fromisoformat(str(today)[:10])


def _takes_office(e, where, what):
    """The day successor `e`, at `where` in the file `what`, takes office;
    SystemExit where it names nobody or no day."""
    if not isinstance(e, dict) or not str(e.get("name") or "").strip():
        raise SystemExit(f"{what}: the successor at {where} (\"elect\") names nobody. A "
                         "successor is an object with a holder's fields, a name first, and "
                         "takes_office (corrections/README.md)")
    if "elect" in e:
        raise SystemExit(f"{what}: the successor at {where}, {e['name']}, has a successor of "
                         "its own; give the record one at a time")
    raw = str(e.get("takes_office") or "")
    try:
        if DAY_RE.match(raw):
            return datetime.date.fromisoformat(raw)
    except ValueError:
        pass
    raise SystemExit(f"{what}: the successor at {where}, {e['name']}, takes office on "
                     + (repr(raw) if raw else "no day") + ": write takes_office as YYYY-MM-DD, "
                     "the day they take the office. No page is built on a guess at it")


def officials_on(doc, today=None, what=OFFICIALS.as_posix()):
    """The hand file's `doc` as it stands on `today` (the build's day by
    default): each record whose successor's day has come is the successor's.

    A RECORD'S SUCCESSOR is an object under its "elect": the fields a holder
    of that record has -- name, party, phone, phone_dc, email, official_url,
    contact_url, source, read, as the record uses them -- and takes_office,
    the day they take the office, "YYYY-MM-DD":

        "2": {"name": "A. Holder", "party": "R", "official_url": "https://...",
              "elect": {"name": "B. Successor", "party": "D",
                        "official_url": "https://...", "source": "https://...",
                        "read": "2026-11-20", "takes_office": "2027-01-07"}}

    Before that day the record is the file's, "elect" and all, and the
    Officials page's tabs say under the holder who takes the office and when
    (officials_tabs.successor). From it the record is the successor's own
    fields over what the record says of the office (OFFICE_FIELDS) and
    whatever it holds inside it; nothing of the predecessor's is carried
    over, not a phone and not an address, so a successor names every way to
    reach them, the office's own address included where the record gives
    one. A successor whose day has passed is simply the holder. Any record
    in the file may carry one.

    A successor with no name, a successor of its own, or a takes_office that
    is no day stops the builder that reads it (SystemExit): the file would
    say somebody takes an office and not who or when, and a page that
    guessed would put a name against an office on the wrong day. `doc` is
    not changed."""
    day = _day(today)

    def walk(x, where):
        if isinstance(x, list):
            return [walk(v, f"{where}[{i}]") for i, v in enumerate(x)]
        if not isinstance(x, dict):
            return x
        out = {k: walk(v, f"{where}.{k}" if where else str(k)) for k, v in x.items()
               if k != "elect"}
        if "elect" not in x:
            return out
        e = x["elect"]
        if day < _takes_office(e, where or "the top", what):
            return {**out, "elect": dict(e)}
        kept = {k: v for k, v in out.items() if k in OFFICE_FIELDS or isinstance(v, (dict, list))}
        return {**kept, **{k: v for k, v in e.items() if k != "takes_office"}}
    return walk(doc, "")


def read_officials(path=None, today=None):
    """corrections/officials.json (or `path`), as every page draws it on
    `today`: read, and officials_on() applied. THE ONE READER (above). A
    file that is not there or will not parse raises as reading it always
    did (OSError, ValueError), for the caller to decide; a successor that
    will not read stops it (officials_on)."""
    p = Path(path) if path else OFFICIALS
    return officials_on(json.loads(p.read_text(encoding="utf-8")), today, p.as_posix())


# THE FILE READ AGAIN AFTER AN ELECTION (the person's approval of 23 October
# 2026). "_checked" is the day a person last read the Governor, the Council
# and Congress against their own pages. After a general election the names
# may be stale and nothing else says so, so from a week after the vote a
# _checked dated before that week was out is a reminder -- preflight's
# _officials_rechecked, one of its REMINDERS, which on the night warns and
# never holds the site. The week is the approval's: nothing is asked of the
# person while the count is coming in, and a reading in it is not the one
# asked for.
RECHECK_AFTER = datetime.timedelta(days=7)


def last_general_election(today):
    """The latest general election before `today`, a date."""
    year = today.year - today.year % 2
    held = general_election(year)
    return held if held < today else general_election(year - 2)


def recheck_due(checked, today=None):
    """What the person is to do about the hand file's _checked (`checked`),
    or "" while nothing is due: from a week after the latest general
    election, a _checked dated before that week was out (RECHECK_AFTER), or
    none, or no day, is due a reading of the offices again; one after today
    is no reading at all."""
    day = _day(today)
    held = last_general_election(day)
    due = held + RECHECK_AFTER
    if day < due:
        return ""
    raw = str(checked or "").strip()
    try:
        when = datetime.date.fromisoformat(raw) if DAY_RE.match(raw) else None
    except ValueError:
        when = None
    if when is not None and when > day:
        return (f"{OFFICIALS.as_posix()}'s _checked is {raw}, after today: it records a "
                "reading that happened, not one planned")
    if when is not None and when >= due:
        return ""
    words = lambda d: f"{d:%B} {d.day}, {d.year}"      # noqa: E731
    return (f"the officials in {OFFICIALS.as_posix()} have not been rechecked since the general "
            f"election of {words(held)}: "
            + (f"_checked is {raw!r}" if raw else "it has no _checked")
            + f", and a reading counts from {words(due)}, a week after the vote. Read each "
            "office's page again, give "
            "each seat that changes hands its successor under \"elect\" with the day they take "
            "office (corrections/README.md says how), and set _checked to the day of that "
            "reading")


# ---- the step --------------------------------------------------------------

def remove_stale(site, why):
    """No file, and a line that says why: the pages then draw nobody."""
    dest = Path(site) / OUT_NAME
    gone = dest.exists()
    if gone:
        dest.unlink()
    print(f"members-elect: none shown -- {why}"
          + (f". Removed the {dest.as_posix()} an earlier build left." if gone else "."))


def load_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{what} ({Path(path).as_posix()}) will not read: {e}")


def say_report(report, hand_path, election):
    for title, rows in (("NOT LINKED -- settle each in " + hand_path.as_posix() + f" under "
                         f"\"{election}\" -> \"matches\" (an id, or null for a new member):",
                         report["unlinked"]),
                        ("NEW -- no sitting or former member of that name; confirm each "
                         "with null in \"matches\", or name who they are:", report["new"])):
        if rows:
            print(f"\n{title}")
            for key, name, why in rows:
                print(f"  {key:<20} {name}: {why}")
    if report["short"]:
        print("\nDO NOT ADD UP -- elected, not final and held against the seats:")
        for key, seats, n, nf, held, present in report["short"]:
            print(f"  {key:<20} {seats} seat(s): {n} elected, {nf} not final, {held} held"
                  + ("" if present else " -- not in the results"))
    if report["notes"]:
        print("\nNOTES:")
        for n in report["notes"]:
            print(f"  {n}")


def decide(a, site, hand_path):
    """(the results file, what it says, the file to write, the report), or
    None where no member-elect is shown, the reason said. Refused where an
    input cannot be used."""
    path = newest_results(a.collected)
    if path is None:
        remove_stale(site, f"no election results in {Path(a.collected).as_posix()}/ "
                           "(election_<year>.json)")
        return None
    results = read_results(path)
    election = datetime.date.fromisoformat(results["election"])
    takes_office = proceedings.organization_day(election.year)
    today = build_date.today()
    why = dates_why(today, election, takes_office)
    if not why:
        meta = load_json(site / "meta.json", "the site's meta.json, which names its terms")
        terms = meta.get("terms") if isinstance(meta, dict) else None
        why = term_why(terms[0] if isinstance(terms, list) and terms else None,
                       results["term"])
    if why:
        remove_stale(site, f"{path.as_posix()}: {why}")
        return None
    notes = []
    sources_hold(results, ".", notes)
    hand, hand_note = read_hand(hand_path, results["election"])
    sitting = load_json(site / "legislators.json", "the sitting roster")
    former = load_json(site / "former.json", "the former members")
    districts = load_json(site / "districts.json", "the district table")
    races, report = members_elect(results, sitting, former, districts, hand, today.isoformat())
    report["notes"][:0] = notes + ([hand_note] if hand_note else [])
    doc = {"election": results["election"], "takes_office": takes_office.isoformat(),
           "term": results["term"],
           "sources": [s.get("url") for s in results.get("_source") or [] if s.get("url")],
           "races": races}
    # NO ADDRESS IS SAID (23 October 2026): parse_sos_results wrote no url
    # until it took --url, and a file with none publishes no address for the
    # results and an Officials tab citing the count unlinked, with nothing
    # to say so.
    if not doc["sources"]:
        report["notes"].append(f"{path.as_posix()} names no address for the results (each "
                               "_source's url): the file names none, and the Officials tab cites "
                               "the Secretary of State's count unlinked. Run "
                               "src/parse/parse_sos_results.py again with --url")
    return path, results, doc, report


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--site", default="site")
    ap.add_argument("--collected", default="collected")
    ap.add_argument("--hand", default=str(HAND_DEFAULT))
    a = ap.parse_args()
    site, hand_path = Path(a.site), Path(a.hand)
    # A REFUSAL IS SAID ON STDERR (the review of 16 October 2026): build_all
    # prints a failed step's last line of stderr and keeps its stderr in
    # build.json, so a refusal said only on stdout stopped the night with "no
    # error text". And whatever stops the step, foreseen or not, first
    # removes the file the last build left: a step that cannot decide must
    # not leave last night's members-elect on the pages.
    dest = site / OUT_NAME
    try:
        got = decide(a, site, hand_path)
        if got is None:
            return 0
        path, results, doc, report = got
        tmp = dest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
        os.replace(tmp, dest)
    except Refused as e:
        remove_stale(site, "nothing could be decided")
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    except Exception:
        remove_stale(site, "the step failed before it could write")
        raise
    races = doc["races"]
    say_report(report, hand_path, results["election"])
    # The summary comes last, where build_all's tail of a step that passed
    # shows it.
    seats = sum(r["seats"] for r in races.values())
    elected = [e for r in races.values() for e in r["elected"]]
    kinds = Counter(e["k"] for e in elected)
    print(f"\nmembers-elect: {path.as_posix()}, the general election of {results['election']} "
          f"for {results['term']}")
    print(f"  {len(races)} races, {seats} seats: {len(elected)} elected ({kinds['sitting']} "
          f"sitting, {kinds['former']} returning, {kinds['new']} drawn unlinked), "
          f"{sum(r['not_final'] for r in races.values())} not final, "
          f"{sum(r['held'] for r in races.values())} held")
    if report["pending"]:
        print(f"  NOT FINAL YET: {report['pending']}")
    print(f"  wrote {dest.as_posix()}; it is shown until {doc['takes_office']}, "
          "Organization Day")
    return 0


if __name__ == "__main__":
    sys.exit(main())
