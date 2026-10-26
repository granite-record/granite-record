#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-07.11
"""
The nightly "what changed" files the email sender reads, and the first-seen
ledger that decides what is new in them.

    import follow_changes as FC        # build_feeds.py's; nothing runs it by name

    site/changes/current.json          what can be followed tonight, what each
                                       record is called, and what is scheduled
    site/changes/<YYYY-MM-DD>.json     what was new on one night, by record: the
                                       last eight nights, all rewritten by every
                                       build
    archive/first-seen.next.json       the ledger this build leaves; nightly.py
                                       keeps it (archive/first-seen.json) only
                                       for a build it accepts, as it keeps the
                                       census

THE CONTRACT is workers/follow/CHANGES_FORMAT.md, on the email-follow branch:
the sender reads nothing of the record but these files, and its changes.js
drops or refuses anything that breaks the format. check() below holds a
folder to the same rules in Python, and preflight also runs that branch's own
tests/follow/check_changes.js where the file is in the tree.

THE ITEMS ARE THE FEEDS' OWN. build_feeds.py hands over, for every record a
reader can follow, the items it writes into that record's feed: the same
guids, the same titles as summaries, the same cut (a feed's newest sixty, a
topic's newest three a bill). An email and a feed reader are told the same
thing. Public data only: nothing here knows who follows anything.

WHAT "NEW" MEANS: THE NIGHT AN ITEM FIRST APPEARED (the person, 7 October
2026: "since sometimes there is a delay until the calendar for that week is
released"). The ledger holds every item each record's feed carries with the
night it was first published there, so a docket row entered three days after
the day it records goes out the next morning, dated by the record and filed
under the night it appeared. Each record's item is filed under exactly one
night, which is the contract's rule that a record's item is in at most one
night's file.

BY RECORD, NOT BY GUID ALONE (the review of 7 October 2026). A topic's feed
carries what has happened, so an executive session scheduled a week ahead
enters it on the day it sits -- a week after its bill's feed carried it as
scheduled. Kept by guid alone it was known by then, and a topic's follower
was never told of a hearing or a session announced in advance, which is
nearly all of them, while the topic's RSS reader was. Kept by record, the
bill's follower hears of it when it is scheduled and the topic's when it
enters the topic, as their two feeds tell it; someone following both hears
twice, once of each.

THE LEDGER, archive/first-seen.json. Carried between nights in the night's
state, as archive/census.json is (cloud_kit.json's "state" list), because
GitHub's machine starts empty and a build may not read a previous run's
site/: a fresh clone must build the same site from the same inputs. It holds

  followable    every key current.json listed, with its label: what tonight
                compares with to find a record that has left, which is owed
                an "ended", and what that ending calls it
  nights        the eight nights the files carry: each night's built stamp,
                sitting term, the guids first seen in it under each record
                (by the build that saw them) and the endings told in it
  carried       every guid each record's feed carried on any of the last
                eight nights, by the last night that carried it

Nothing else, so it stays bounded: a record's guid its feed has not carried
for eight nights, and that no kept night files, is let go. The eight-night memory is
what keeps one bad build from flooding anyone: a build whose member files
came out empty forgets nothing, and when they come back their votes are not
new. A night's files are rewritten from the ledger and from tonight's feeds,
so an item that has left every feed since it was filed (a member with more
than sixty votes in a week) leaves that night's file too; the weekly email
counts at most twenty items a record, and an RSS reader polling weekly would
miss the same items.

NO LEDGER (the first night, or a lost state): NEVER A FLOOD. Every item the
feeds carry would be "new", so the build falls back to the record's own dates
for that night, as the contract allows (new_by "record-date"): the night named
D holds exactly the items dated D - 1, and every one of the eight files is
written that way. The ledger is seeded from what record-date placed and from
everything older; an item dated tonight or later waits for tomorrow's night,
where it is new. It says so in a WARNING, and nightly.py puts it in the
night's verdict: silence is not success.

A RECORD THAT LEAVES gets an "ended" the night it leaves: a bill by its
feed's closing item, or by the turn of its term; a member or committee as
"left", or "term-ended" on the night the sitting term changes. A record that
comes back -- a build that lost it, then found it -- has its ending taken
back, so a night that was never published cannot end anyone's follow later.

THE TURN OF A TERM (nightly.py --new-term). The sitting term is the newest
term the bill index holds, as the feeds take it. The night it changes, every
bill of the old term still followable ends as "term-ended", topics carry the
new term's items only, and nothing of the old term is new: its guids are in
the ledger already, and an old-term bill that is no longer followable files
nothing more. A New term run's ledger is kept only once its build is
published (nightly.py), so a switch the person rejects leaves the old term's
ledger as it was.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path

FORMAT = 1
# The ledger's own shape: 2 keeps each guid under the record whose feed
# carried it. A ledger of 1, by guid alone, is refused and the night goes by
# the record's dates, rather than being read in a shape it is not.
LEDGER_FORMAT = 2
NIGHTS_KEPT = 8                      # the contract's "the last eight nights at least"
LEDGER = Path("archive/first-seen.json")
CANDIDATE = Path("archive/first-seen.next.json")
FOLDER = "changes"                    # under site/

FIRST_SEEN, RECORD_DATE = "first-seen", "record-date"
ITEM_KINDS = ("action", "hearing", "scheduled", "exec", "vote", "report", "sponsor",
              "sitting", "study")
ENDS = ("bill", "member", "committee", "lsr")   # the kinds an ending is owed for

# The five kinds of key, as workers/follow/common.js's REF has them. A law is
# a chapter of the statutes as its /laws page names it, in capitals: 91-A,
# 674, 21-J (the person, 11 October 2026: "Following a law sounds like a good
# idea").
REF = {
    "law": re.compile(r"^\d{1,3}(?:-[A-Z]{1,2})?$"),
    "bill": re.compile(r"^\d{4}/[A-Z]{2,6}\d{1,4}$"),
    "member": re.compile(r"^\d{1,7}$"),
    "committee": re.compile(r"^[A-Za-z]\d{2,3}(?:-\d{4})?$"),
    "topic": re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
    # A bill request by its number, 2027-0001 (22 October 2026: build_feeds,
    # BILL REQUESTS, FOLLOWED UNTIL THEY ARE BILLS).
    "lsr": re.compile(r"^\d{4}-\d{4,5}$"),
}
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TERM = re.compile(r"^\d{4}-\d{4}$")
TIME = re.compile(r"^\d{2}:\d{2}$")
HOW = re.compile(r"^[a-z][a-z-]{0,30}$")
PATH = re.compile(r"^/(?!/)[A-Za-z0-9\-._~/?=&%+]*$")


def key_ok(key):
    kind, _, ref = str(key or "").partition(":")
    return kind in REF and len(ref) <= 80 and bool(REF[kind].match(ref))


def kind_of_key(key):
    return str(key).partition(":")[0]


def line(s, room):
    """One line of plain text, at most `room` characters, cut at a word."""
    s = " ".join(str(s or "").split())
    if len(s) <= room:
        return s
    cut = s[:room - 1]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > room * 0.6 else cut).rstrip(" ,;:-–—") + "…"


# ---- what a followed record is called, and how the manage page lists it ------------
# A COMMITTEE IS NAMED AS THE SEARCH NAMES IT (16 October 2026). The person
# asked the search to say "House Housing Committee" rather than "Housing", so
# that a committee is not taken for the subject of the same name (find.js
# findName). The manage page sets committees and topics side by side, and the
# emails name both, so current.json's label for a committee follows the same
# rule: "Committee" where the name does not already say it, and the chamber
# in front unless the name begins with it. A committee's label is the whole of
# what an email or the manage page calls it.
CHAMBERS = {"H": "House", "S": "Senate"}


def committee_label(name, chamber=""):
    """A committee's name as the search draws it: "House Housing Committee",
    "House Special Committee on Housing", "Senate Special Committee on
    Redistricting". Text, not markup."""
    name, chamber = " ".join(str(name or "").split()), str(chamber or "")
    named = name if re.search(r"\bcommittee\b", name, re.I) else f"{name} Committee"
    return named if not chamber or name.startswith(chamber + " ") else f"{chamber} {named}"


def stamp(dt):
    """A UTC moment as the contract writes one: 2026-10-08T09:02:40Z."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def day_shift(d, n):
    return (date.fromisoformat(d) + timedelta(days=n)).isoformat()


def window(tonight):
    """The eight nights the files carry, oldest first, ending tonight."""
    return [day_shift(tonight, n) for n in range(1 - NIGHTS_KEPT, 1)]


# ---- what kind of thing a docket row is -----------------------------------------
# Read off the rows of 2025-2026 (7 October 2026): "Public Hearing: 02/20/2026
# 11:00 am GP 231", "Hearing: 04/02/2026, Room 100, SH, 01:50 pm" (the Senate's),
# "Executive Session: ...", five kinds of work session and two of conference
# meeting, each dated by the meeting itself; a floor roll call as "MA RC 181-164"
# or the Senate's "RC 15Y-9N"; a committee's report, majority, minority or of
# conference, whose "(Vote 10-8; RC)" is the committee's own roll and not the
# floor's; and the interim study committee's report, "Interim Study Report:
# Recommended for Future Legislation" or "Not Recommended for ...".
MEETING = re.compile(r"^(?:Public Hearing|Hearing|Executive Session|(?:Full Committee|Subcommittee"
                     r"|Division [IV]+) Work Session|Conference Committee Meeting|Committee of "
                     r"Conference Meeting)\b", re.I)
HEARING = re.compile(r"^(?:Public Hearing|Hearing)\b", re.I)
EXEC = re.compile(r"^Executive Session\b", re.I)
FLOOR_ROLL = re.compile(r"\bRC\s*\d")
# A floor roll call's count on its docket line, "MA RC 201-163": the yeas and
# the nays, which find the roll call the line records (build_feeds).
FLOOR_COUNT = re.compile(r"\bRC\s*(\d+)\s*-\s*(\d+)")
REPORT = re.compile(r"^(?:(?:Majority|Minority|Conference) )?Committee Report\b", re.I)
STUDY_REPORT = re.compile(r"^Interim Study Report\b", re.I)


# WHAT "MILESTONES ONLY" SENDS (the person, 11 October 2026: the design's
# "Hearings scheduled, committee votes, floor votes, and how a bill ended").
# Every scheduled proceeding, executive session, committee report, roll call
# and interim study step; and a docket entry of another kind only where it
# decides something -- passes, adopts, kills, tables, signs, vetoes, enacts.
MILESTONE_KINDS = ("scheduled", "exec", "report", "vote", "study")
DECIDES = re.compile(
    r"\b(?:passed|adopted|signed|vetoed|veto|law|chaptered|enrolled|tabled|laid on the table|"
    r"indefinitely postponed|inexpedient to legislate|ought to pass|ought not to pass|killed|"
    r"failed|concur(?:s|red)?|non-concur(?:s|red)?|died|withdrawn|override)\b", re.I)


def milestone(kind, text=""):
    """Whether an item of this kind and these words is a milestone."""
    return kind in MILESTONE_KINDS or (kind == "action" and bool(DECIDES.search(str(text or ""))))


def event_kind(text, day, tonight):
    """The contract's kind for one docket row. A meeting dated after tonight
    is "scheduled", whatever meeting it is: it is news that it will happen,
    and the weekly email counts an executive session that has not sat yet as
    nothing."""
    t = str(text or "").strip()
    if STUDY_REPORT.match(t):
        return "study"
    if MEETING.match(t):
        if day > tonight:
            return "scheduled"
        return "hearing" if HEARING.match(t) else "exec" if EXEC.match(t) else "action"
    if FLOOR_ROLL.search(t):
        return "vote"
    if REPORT.match(t):
        return "report"
    return "action"


def study_says(text):
    """An interim study report's recommendation: True, False, or None where
    the row does not say. None too for a row that is not one."""
    t = str(text or "")
    if not STUDY_REPORT.match(t.strip()):
        return None
    if re.search(r"\bNot Recommended\b", t, re.I):
        return False
    return True if re.search(r"\bRecommended\b", t, re.I) else None


# A MEMBER'S BALLOT, SAID WITH THE ROLL CALL IT WAS CAST IN (the person, 11
# October 2026: "it should show all roll call votes they made the previous
# week if any, how they voted vs the overall outcome of the vote, and the bill
# title with links"). Optional on a vote item; every value plain text.
VOTE_FIELDS = {"ballot": 20, "result": 10, "tally": 20, "motion": 160, "bill": 40, "title": 300}
RESULTS = ("passed", "failed")


def vote_detail(ballot, *, result="", tally="", motion="", bill="", title=""):
    """A vote item's "vote", or None where there is no ballot to tell."""
    out = {}
    for f, v in (("ballot", ballot), ("result", result), ("tally", tally), ("motion", motion),
                 ("bill", bill), ("title", title)):
        v = line(v or "", VOTE_FIELDS[f])
        if v and (f != "result" or v in RESULTS):
            out[f] = v
    return out if out.get("ballot") else None


# A FLOOR ROLL CALL, COUNTED, FOR THE EMAIL TO DRAW (the person, 22 October
# 2026: bill emails should have "similar elements to what's on the bill pages
# with the vote diagrams"). The bill page's ring is the roll call's record:
# yeas and nays, whether it passed, what the yes side needed and by what
# rule, and each party's yes and no. The email draws a bar of the two sides
# and says the rest in words, so the build hands it those facts and no
# member's name. Optional on a bill's vote item.
ROLLCALL_PARTIES = 6
PARTY_ORDER = {"R": 0, "D": 1}


def rollcall_detail(rc):
    """An item's "rollcall" from one of a bill record's rollcalls, or None
    where it has no count to draw."""
    if not isinstance(rc, dict):
        return None
    y, n, passed = rc.get("yeas"), rc.get("nays"), rc.get("passed")
    if not (type(y) is int and type(n) is int and y >= 0 and n >= 0 and y + n > 0
            and isinstance(passed, bool)):
        return None
    out = {"yeas": y, "nays": n, "passed": passed}
    need = rc.get("threshold_needed")
    if type(need) is int and need > 0 and not rc.get("threshold_unknown"):
        out["need"] = need
        rule = line(rc.get("threshold_rule") or "", 120)
        if rule:
            out["rule"] = rule
    parties = []
    for p, t in (rc.get("tally") or {}).items():
        if not (isinstance(p, str) and re.fullmatch(r"[A-Z]{1,2}", p) and isinstance(t, dict)):
            continue
        a, b = t.get("Yea") or 0, t.get("Nay") or 0
        if type(a) is int and type(b) is int and a >= 0 and b >= 0 and a + b:
            parties.append([p, a, b])
    parties.sort(key=lambda x: (PARTY_ORDER.get(x[0], 9), x[0]))
    if parties:
        out["parties"] = parties[:ROLLCALL_PARTIES]
    return out


def rollcall_ok(r):
    """Whether an item's "rollcall" is the shape rollcall_detail writes."""
    if not isinstance(r, dict) or set(r) - {"yeas", "nays", "passed", "need", "rule", "parties"}:
        return False
    if not all(type(r.get(k)) is int and r[k] >= 0 for k in ("yeas", "nays")) \
            or r["yeas"] + r["nays"] == 0 or not isinstance(r.get("passed"), bool):
        return False
    if "need" in r and not (type(r["need"]) is int and r["need"] > 0):
        return False
    if "rule" in r and (not isinstance(r["rule"], str) or line(r["rule"], 120) != r["rule"]
                        or "need" not in r):
        return False
    ps = r.get("parties", [])
    return isinstance(ps, list) and len(ps) <= ROLLCALL_PARTIES and all(
        isinstance(x, list) and len(x) == 3 and isinstance(x[0], str)
        and re.fullmatch(r"[A-Z]{1,2}", x[0]) and all(type(v) is int and v >= 0 for v in x[1:])
        for x in ps)


# A MEETING THE LINE SETS, FOR THE EMAIL TO SAY IN ITS OWN WORDS (17 October
# 2026). The person approved plain words for an email's hearing entries; the
# build knows the clerk's rooms (plain_action.place) and the email knows how
# it writes a day, so the build hands over the facts and the email words them.
# Optional on any item; plain_action.meeting is what makes one.
MEETING_STATES = ("rescheduled", "recessed", "cancelled", "time changed", "room changed")


def meeting_detail(m):
    """An item's "meeting", or None where there is no kind and day to tell."""
    if not isinstance(m, dict) or not DAY.match(str(m.get("date") or "")):
        return None
    what = line(m.get("what") or "", 120)
    if not what:
        return None
    out = {"what": what, "date": m["date"]}
    if TIME.match(str(m.get("time") or "")):
        out["time"] = m["time"]
    venue = line(m.get("venue") or "", 120)
    if venue:
        out["venue"] = venue
    if m.get("state") in MEETING_STATES:
        out["state"] = m["state"]
    return out


def item(guid, day, kind, summary, url="", term="", study=False, recommends=None,
         milestone=False, vote=None, plain="", meeting=None, rollcall=None):
    """One feed item as the changes files carry it, or None where it cannot
    be one (no guid, no date the contract reads). `study` marks a bill's
    interim study report, which its bill's night carries as "study".
    `milestone` marks what a reader who asked for milestones only is sent;
    `vote` is a member's ballot with its roll call (vote_detail); `plain` the
    line in plain words (plain_action.py), which the email prints first;
    `meeting` the meeting the line sets (meeting_detail), which the email
    words before either; `rollcall` a floor roll call's count
    (rollcall_detail), which the email draws."""
    guid = str(guid or "")
    if not guid or len(guid) > 300 or not DAY.match(str(day or "")):
        return None
    summary = line(summary, 300)
    if not summary:
        return None
    out = {"guid": guid, "date": day, "kind": kind if kind in ITEM_KINDS else "action",
           "summary": summary}
    if url and PATH.match(url):
        out["url"] = url
    if term and TERM.match(term):
        out["term"] = term
    if study:
        out["_study"] = recommends
    if milestone:
        out["milestone"] = True
    if vote:
        out["vote"] = vote
    plain = line(plain, 300)
    if plain:
        out["plain"] = plain
    meeting = meeting_detail(meeting)
    if meeting:
        out["meeting"] = meeting
    if rollcall and rollcall_ok(rollcall):
        out["rollcall"] = rollcall
    return out


# ---- the ledger -----------------------------------------------------------------------

def load(path=LEDGER, tonight=None):
    """(ledger, why): the ledger, or None with the reason there is none to use."""
    p = Path(path)
    if not p.exists():
        return None, f"no {p.as_posix()}"
    try:
        led = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"{p.as_posix()} will not read ({type(e).__name__})"
    if not isinstance(led, dict) or led.get("format") != LEDGER_FORMAT or \
            not isinstance(led.get("nights"), dict) or not isinstance(led.get("carried"), dict) \
            or not isinstance(led.get("followable"), dict) or not DAY.match(str(led.get("date"))):
        return None, f"{p.as_posix()} is not a ledger of format {LEDGER_FORMAT}"
    if tonight and led["date"] > tonight:
        return None, (f"{p.as_posix()} is of {led['date']}, after tonight's {tonight}: a build "
                      "dated earlier than the ledger cannot say what is new since")
    return led, ""


def wanted(led, tonight):
    """The keys whose items the build should hand over beside tonight's
    followable ones: what the ledger listed last (a record leaving tonight
    takes its last items with its ending) and what ended in a kept night."""
    if not led:
        return set()
    keep = set(window(tonight))
    out = set(led.get("followable") or {})
    for d, n in (led.get("nights") or {}).items():
        if d in keep:
            out |= set((n.get("ended") or {}))
    return out


def ending(key, label, *, term_turned, old_term, hints):
    """The "ended" a record that left tonight is owed. `hints` is
    build_feeds' word on what it knows: a bill's closing item, a bill's
    row, a committee's record."""
    kind, _, ref = key.partition(":")
    h = hints.get(key) or {}
    if kind == "lsr":
        # Drafted and introduced: the follow moves to the bill ("becomes",
        # which the sender reads); withdrawn, or gone without a word, it ends.
        if h.get("becomes") and key_ok(h["becomes"]):
            return {"how": "drafted", "becomes": h["becomes"],
                    "summary": f"{label} has been drafted and introduced as {h.get('bill') or 'a bill'}.",
                    "guid": f"{key}:ended:drafted"}
        how = "withdrawn" if h.get("withdrawn") else "left"
        said = (f"{label} was withdrawn before it was drafted." if h.get("withdrawn")
                else f"{label} is no longer among the bill requests on record.")
        return {"how": how, "summary": said, "guid": f"{key}:ended:{how}"}
    if kind == "bill":
        if term_turned:
            return {"how": "term-ended", "summary": f"{label} ended with the {old_term} term.",
                    "guid": f"{old_term}:{ref.split('/')[-1]}:closed:term-ended"}
        if h.get("closing"):
            return dict(h["closing"])
        how = h.get("kind") if HOW.match(str(h.get("kind") or "")) else "done"
        return {"how": how, "summary": h.get("said") or f"{label} is no longer moving.",
                "guid": f"{h.get('term') or old_term}:{ref.split('/')[-1]}:closed:{how}"}
    how = "term-ended" if term_turned else "left"
    if kind == "member":
        said = f"{label} is no longer among the sitting legislators."
    elif h.get("archived"):
        said = f"{label} is no longer on the General Court's list of committees."
    else:
        said = f"{label} no longer has a sitting or a bill on record to follow."
    return {"how": how, "summary": said, "guid": f"{key}:ended:{how}"}


def decide(led, *, tonight, built, sitting_term, followable, lists, hints):
    """Tonight's ledger, from the last one (or None) and tonight's feeds.
    Returns (ledger, new_by, counts)."""
    days = window(tonight)
    keep = set(days)
    # What a night may file: the items of a record followable tonight, or of
    # one that leaves tonight (its last items go with its ending), each as
    # (record, guid) -- the ledger knows an item under each record whose feed
    # carried it, not once for them all (BY RECORD, above).
    prev_follow = dict((led or {}).get("followable") or {})
    gone = sorted(k for k in prev_follow if k not in followable and kind_of_key(k) in ENDS)
    fileable = {}
    for key in list(followable) + gone:
        for it in lists.get(key) or []:
            fileable.setdefault((key, it["guid"]), it)
    every = {(key, it["guid"]): it for key, its in lists.items() for it in its}

    def file_under(first_seen, stamp, pairs):
        """Add (record, guid) pairs to one night's first_seen under `stamp`."""
        by_key = first_seen.setdefault(stamp, {})
        for k, g in pairs:
            by_key.setdefault(k, []).append(g)
        for k in by_key:
            by_key[k] = sorted(set(by_key[k]))

    nights = {}
    counts = {"new": 0, "ended": 0, "taken_back": 0}
    if led is None:
        new_by = RECORD_DATE
        for d in days:
            nights[d] = {"built": built, "sitting_term": sitting_term,
                         "first_seen": {}, "ended": {}}
        for (k, g), it in sorted(fileable.items()):
            d = day_shift(it["date"], 1)
            if d in keep:
                file_under(nights[d]["first_seen"], built, [(k, g)])
                counts["new"] += 1
        # What record-date placed, and everything older, is known from now on;
        # an item dated tonight or later is not, and is new tomorrow.
        carried = {kg: tonight for kg, it in every.items() if it["date"] < tonight}
    else:
        new_by = FIRST_SEEN
        known = {}
        for d, by_key in (led.get("carried") or {}).items():
            for k, gs in (by_key or {}).items():
                for g in gs:
                    known[(k, g)] = max(d, known.get((k, g), ""))
        for d, n in (led.get("nights") or {}).items():
            for by_key in (n.get("first_seen") or {}).values():
                for k, gs in (by_key or {}).items():
                    for g in gs:
                        known.setdefault((k, g), d)
            if d in keep:
                nights[d] = {"built": n.get("built") or built,
                             "sitting_term": n.get("sitting_term") or sitting_term,
                             "first_seen": {s: {k: list(gs) for k, gs in (by_key or {}).items()}
                                            for s, by_key in (n.get("first_seen") or {}).items()},
                             "ended": dict(n.get("ended") or {})}
        here = nights.setdefault(tonight, {"built": built, "sitting_term": sitting_term,
                                           "first_seen": {}, "ended": {}})
        here["built"], here["sitting_term"] = built, sitting_term
        # NEW TO THE RECORD, NOT NEW TO A LIST (17 October 2026). The person's
        # weekly email listed under Laws "a bunch of entries from months ago as
        # new". A law's items are the items of the bills that cite it, its
        # newest sixty across them all (build_feeds.py), so an item enters a
        # law's list whenever a bill comes to cite the chapter, whenever a
        # bill above it in that sixty stops moving and leaves room, and on the
        # night laws could first be followed -- and each time it was first seen
        # under the law, with tonight's stamp, though its bill's follower had
        # it long before. "New" means new since the reader's last email, so an
        # item another record already had is not new to a law or a topic when
        # it is dated before the nights the files carry: a bill filed under a
        # new subject, or newly citing a chapter, brings its old items with it,
        # and they are not news. One dated within those nights still is (the
        # review of 17 October 2026): a hearing its bill's follower heard of on
        # Monday is news to a reader who follows only RSA 91-A when the bill
        # comes to cite it on Wednesday, as a meeting is a topic's news the
        # night it sits (BY RECORD, above).
        had = {g for _, g in known}
        new = sorted(kg for kg in fileable if kg not in known and not (
            kg[1] in had and kind_of_key(kg[0]) in ("law", "topic")
            and fileable[kg]["date"] < days[0]))
        if new:
            file_under(here["first_seen"], built, new)
        counts["new"] = len(new)
        # A record that left gets its ending tonight; one that is back has
        # its ending taken back, from whichever kept night told it.
        old_term = led.get("sitting_term") or sitting_term
        turned = old_term != sitting_term
        for k in gone:
            e = ending(k, prev_follow[k], term_turned=turned, old_term=old_term, hints=hints)
            e.setdefault("date", tonight)
            here["ended"][k] = {f: e[f] for f in ("how", "summary", "date", "guid", "becomes")
                                if e.get(f)}
            counts["ended"] += 1
        for n in nights.values():
            for k in [k for k in n["ended"] if k in followable]:
                del n["ended"][k]
                counts["taken_back"] += 1
        carried = {kg: d for kg, d in known.items() if d >= days[0]}
        for kg in every:
            carried[kg] = tonight
    for d in days:
        nights.setdefault(d, {"built": built, "sitting_term": sitting_term,
                              "first_seen": {}, "ended": {}})
    by_day = {}
    for (k, g), d in carried.items():
        by_day.setdefault(d, {}).setdefault(k, []).append(g)
    ledger = {
        "format": LEDGER_FORMAT,
        "about": ("The first-seen ledger of the changes files (src/pages/follow_changes.py): "
                  "every guid each record's feed carried in the last eight nights, by the "
                  "last night that carried it; the guids first seen under each record in "
                  "each kept night; the endings told; and what tonight listed as followable."),
        "date": tonight, "built": built, "sitting_term": sitting_term, "new_by": new_by,
        "followable": {k: followable[k]["label"] for k in sorted(followable)},
        "nights": {d: {"built": n["built"], "sitting_term": n["sitting_term"],
                       "first_seen": {s: {k: sorted(gs) for k, gs in sorted(by_key.items()) if gs}
                                      for s, by_key in sorted(n["first_seen"].items())},
                       "ended": {k: n["ended"][k] for k in sorted(n["ended"])}}
                   for d, n in sorted(nights.items()) if d in keep},
        "carried": {d: {k: sorted(gs) for k, gs in sorted(by_key.items())}
                    for d, by_key in sorted(by_day.items())},
    }
    counts["carried"] = len(carried)
    return ledger, new_by, counts


# ---- the files ------------------------------------------------------------------------

def night_file(ledger, d, new_by, followable, lists):
    """One night's file, rewritten from the ledger and tonight's items."""
    n = ledger["nights"][d]
    filed = {(k, g): s for s, by_key in n["first_seen"].items()
             for k, gs in by_key.items() for g in gs}
    later = {k for dd, nn in ledger["nights"].items() if dd >= d for k in nn["ended"]}
    refs = {}
    for key in sorted(set(followable) | later):
        entry, items, studies, had = {}, [], [], set()
        for it in lists.get(key) or []:
            if (key, it["guid"]) not in filed or it["guid"] in had:
                continue
            had.add(it["guid"])
            out = {f: it[f] for f in ("guid", "date", "kind", "summary", "plain", "url", "term",
                                      "milestone", "vote", "meeting", "rollcall") if f in it}
            if new_by == FIRST_SEEN:
                out["seen"] = filed[(key, it["guid"])]
            if "_study" in it and kind_of_key(key) == "bill":
                studies.append((it, out))
            else:
                items.append(out)
        if studies:
            # The newest report is the bill's study; an older one, first seen
            # the same night, stays an item.
            studies.sort(key=lambda p: (p[0]["date"], p[0]["guid"]), reverse=True)
            it, out = studies[0]
            entry["study"] = {"recommends": it["_study"], "summary": out["summary"],
                              "date": out["date"], "guid": out["guid"],
                              **({"seen": out["seen"]} if "seen" in out else {})}
            items += [o for _, o in studies[1:]]
        if items:
            entry["items"] = items
        if key in n["ended"]:
            entry["ended"] = n["ended"][key]
        if entry:
            refs[key] = entry
    return {"format": FORMAT, "date": d, "built": n["built"], "sitting_term": n["sitting_term"],
            "new_by": new_by, "refs": refs}


def current_file(tonight, built, sitting_term, new_by, followable, upcoming):
    up = {}
    for key in sorted(upcoming):
        if key not in followable:
            continue
        # One row a sitting: a committee hearing eight bills at ten is one
        # proceeding to its followers, as it is one card on the calendar.
        rows = sorted({json.dumps(r, sort_keys=True): r for r in upcoming[key]
                       if r.get("date", "") >= tonight}.values(),
                      key=lambda r: (r["date"], r.get("time", ""), r["what"],
                                     r.get("committee", ""), r.get("venue", ""),
                                     r.get("amendment", ""), r.get("form", "")))
        if rows:
            up[key] = rows
    return {"format": FORMAT, "date": tonight, "built": built, "sitting_term": sitting_term,
            "new_by": new_by,
            "followable": {k: followable[k] for k in sorted(followable)}, "upcoming": up}


def upcoming_row(day, what, time="", committee="", venue=""):
    """One proceeding scheduled, as current.json's upcoming carries it, or
    None where it has no date or no words for what it is."""
    what = line(what, 120)
    if not DAY.match(str(day or "")) or not what:
        return None
    row = {"date": day, "what": what}
    if time and TIME.match(str(time)):
        row["time"] = time
    for f, v in (("committee", committee), ("venue", venue)):
        v = line(v, 120)
        if v:
            row[f] = v
    return row


# ---- the hearings a bill's Testify button counts, for the emails ---------------------
# EMAILS SAY WHAT THE SITE'S TESTIFY SAYS (the person, 26 October 2026:
# "Emails should stay in sync with how the site displays the testify
# button"). The button (app.js testifyButton) reads a bill's record: its
# stations' public hearings, the hearings on a proposed amendment that only
# its docket lines carry (testifyHearings), the committee that has the bill
# that day (testifyHouseCommittee), and whether it can still be heard at all
# (testifyMoving). The email read current.json's upcoming, which was
# home.json's calendar rows -- the first eighty of the fortnight, where a
# fortnight in session holds hundreds (607 hearings from 20 January 2026
# alone), so most bills' hearings never reached it -- and none of the
# amendment hearings, and a hearing whose station names no committee had no
# chamber and so no form. So the rows a bill's followers are sent are read
# here from the same record by the same rules, and the ones its Testify
# counts as live carry the form to send them to: these are app.js's
# functions in Python, and preflight's _testify_email_in_sync runs both on
# the same records -- every record a check of preflight draws a Testify
# button for, so that a record exercising a rule of app.js's exercises this
# copy's too -- and holds the email's words to the pane's.
TESTIFY_WORD = re.compile(r"^(public )?hearing$", re.I)
# A sitting of the floor, a conference, a recording naming the bill: none is
# a committee's meeting on the calendar (proceedings.FLOOR_KINDS, and the
# floor index's third kind).
NOT_A_MEETING = ("floor debate", "committee of conference", "recording naming this bill")
AMENDMENT_HEARING = re.compile(
    r"^Public\s+Hearing\s+on\s+(?:Proposed\s+)?(Non-?\s?Germane\s+)?(?:Amendment|AM)\b([^:]*):\s*"
    r"(\d{1,2})/(\d{1,2})/(\d{4})\b\s*(?:(\d{1,2}):(\d{2})\s*([ap])\.?\s?m\b\.?)?\s*(.*)$", re.I)
AMENDMENT_NUM = re.compile(r"(?:\d{4}-)?\d{3,4}[a-z]+", re.I)
# What the Bill Text tab opens at its address (app.js AMENDMENT_HASH).
AMENDMENT_OPENS = re.compile(r"^(?:\d{4}-)?\d{3,4}[a-z]{1,2}$", re.I)
AMENDMENT_ROOM = re.compile(r"^[A-Za-z0-9-][A-Za-z0-9 ,.'&-]{0,79}$")
REFERRED = re.compile(r"\b(?:re-?)?referred\s+to\s+(.+?)\s*(?:[(:;]|\b\d{1,2}/\d{1,2}/\d{4}\b|$)", re.I)


def testify_body(s):
    """app.js testifyBody: the station's chamber, or where it names neither,
    the chamber whose word it uses ("public hearing" the House's)."""
    if s.get("body") in CHAMBERS:
        return s["body"]
    return "H" if re.match(r"public ", str(s.get("what") or ""), re.I) else "S"


def _order(s):
    return (str(s.get("when") or ""), str(s.get("time") or ""))


def _report_dated(s):
    return s.get("dated_by") == "report"


def testify_house_committee(rec, when, time, room):
    """app.js testifyHouseCommittee: the House committee that has the bill on
    the day -- the one meeting on it that day (in the line's room, then
    nearest its time), else the later of its last House referral and its last
    House meeting before the day, else house_committee."""
    def flat(v):
        return re.sub(r"\s+", "", str(v or "")).lower()

    def mins(t):
        m = re.match(r"(\d{1,2}):(\d{2})", str(t or ""))
        return int(m.group(1)) * 60 + int(m.group(2)) if m else None

    meets = [s for s in rec.get("stations") or []
             if s.get("body") == "H" and s.get("when") and s["when"] <= when
             and str(s.get("committee") or "").strip()
             and not re.fullmatch(r"(house|senate)", str(s["committee"]).strip(), re.I)]

    def near(s):
        a, b = mins(s.get("time")), mins(time)
        return ((0 if room and flat(s.get("venue")) == flat(room) else 100000)
                + (50000 if a is None or b is None else abs(a - b)))
    that = sorted((s for s in meets if s["when"] == when), key=near)
    if that:
        return str(that[0]["committee"]).strip()
    before = sorted((s for s in meets if s["when"] < when), key=_order)
    met = before[-1] if before else None
    sent = None
    for e in rec.get("events") or []:
        if e.get("called_off") or re.match(r"S[JC]\b", str(e.get("cite") or "").strip()) \
                or not e.get("date") or str(e["date"]) > when:
            continue
        m = REFERRED.search(str(e.get("text") or "").strip())
        if not m or re.match(r"(committee|interim study)\b", m.group(1), re.I):
            continue
        if not sent or str(e["date"]) >= sent[0]:
            sent = (str(e["date"]), m.group(1).strip())
    if sent and (not met or sent[0] >= met["when"]):
        return sent[1]
    if met:
        return str(met["committee"]).strip()
    return rec.get("house_committee") or ""


def testify_hearings(rec):
    """app.js testifyHearings: the record's public hearings -- its stations',
    a report's only where the docket has no Senate hearing of the bill, and
    each hearing on a proposed amendment its docket lines set that no House
    station stands for -- each a station-like dict; an amendment's carries
    "amendment" (its words) and "amendment_num"."""
    heard = [s for s in rec.get("stations") or []
             if TESTIFY_WORD.match(str(s.get("what") or "")) and s.get("when")
             and not (_report_dated(s) and s.get("docket_heard"))]
    for e in rec.get("events") or []:
        m = AMENDMENT_HEARING.match(str(e.get("text") or "").strip())
        if not m or e.get("called_off"):
            continue
        when = (str(e["date"]) if e.get("date_as_recorded") and e.get("date")
                else f"{m.group(5)}-{m.group(3).zfill(2)}-{m.group(4).zfill(2)}")
        time = (f"{int(m.group(6)) % 12 + (12 if m.group(8).lower() == 'p' else 0):02d}:{m.group(7)}"
                if m.group(6) else "")
        if any(testify_body(s) == "H" and s.get("when") == when and str(s.get("time") or "") == time
               for s in heard):
            continue
        room = re.split(r"\s*(?:[(\[;*]|https?:)", m.group(9) or "")[0].strip()
        num = AMENDMENT_NUM.search(m.group(2))
        num = num.group(0) if num else ""
        heard.append({"what": "public hearing", "body": "H", "when": when, "time": time,
                      "committee": testify_house_committee(rec, when, time, room),
                      "venue": room if AMENDMENT_ROOM.match(room) else "",
                      "amendment": f"a proposed {'non-germane ' if m.group(1) else ''}amendment"
                                   + (f" ({num})" if num else ""),
                      "amendment_num": num})
    return heard


def testify_moving(rec, kind, today):
    """app.js testifyMoving: whether a hearing can still come -- not once the
    term's last session day has gone, and then by the index row's kind
    ("active" alone), or where there is none, by the rail."""
    if rec.get("session_over") and str(rec["session_over"]) < today:
        return False
    if kind:
        return kind == "active"
    rail = (rec.get("journey") or {}).get("rail") or []
    return (not any(s.get("mark") == "x" for s in rail)
            and any(s.get("stop") in ("House", "Senate") and s.get("mark") == "h" for s in rail))


def testify_committee(house, c):
    """app.js testifyCommittee: "House Housing Committee" -- the chamber, the
    name, and "Committee" where the name does not say it."""
    n = str(c or "").strip()
    if not n:
        return ""
    named = n if n.lower().startswith(house.lower() + " ") else f"{house} {n}"
    return named if re.search(r"\bcommittee\b", n, re.I) else f"{named} Committee"


def bill_upcoming(rec, *, kind, today, place=lambda v: " ".join(str(v or "").split())):
    """Every meeting on the bill still to come, as current.json's upcoming
    rows, from its record: [{"row", "body", "name"}], where "name" is the
    committee that will sit as the record names it, for filing the row
    under that committee too (committee_row). A public hearing the bill's
    Testify button counts while the bill can still be heard carries "form",
    "H" or "S": the chamber whose online sign-in takes testimony for it, in
    the words the button's pane uses -- its committee the pane's, its room
    in place()'s words (roomWords), and on a proposed amendment "amendment",
    with "amendment_num" where the bill's Bill Text tab can open it (namd).
    `kind` is the bill's index row's; `today` New Hampshire's day."""
    heard = testify_hearings(rec)
    moving = testify_moving(rec, kind, today)
    out = []

    def add(s, testify):
        body = testify_body(s) if testify else str(s.get("body") or "").strip().upper()
        house = CHAMBERS.get(body, "")
        name = str(s.get("committee") or "").strip()
        if testify and not name:
            # The committee where the station names none (app.js
            # testifyButton): the House's that has the bill that day, the
            # Senate's of its referral.
            name = (testify_house_committee(rec, s["when"], str(s.get("time") or ""), s.get("venue") or "")
                    if body == "H" else str(rec.get("senate_committee") or "").strip())
        label = (testify_committee(house, name) if testify else
                 committee_label(name, house) if name else "")
        row = upcoming_row(s["when"], s.get("what") or "hearing", str(s.get("time") or ""),
                           label, place(s.get("venue") or ""))
        if not row:
            return
        if s.get("amendment"):
            row["amendment"] = line(s["amendment"], 120)
            num = s.get("amendment_num") or ""
            if num and rec.get("namd") and AMENDMENT_OPENS.match(num):
                row["amendment_num"] = num
        if testify and moving:
            row["form"] = body
        out.append({"row": row, "body": body, "name": name})

    counted = [id(s) for s in heard]
    for s in rec.get("stations") or []:
        what = str(s.get("what") or "").strip().lower()
        if what in NOT_A_MEETING or _report_dated(s) or not s.get("when") or s["when"] < today:
            continue
        add(s, id(s) in counted)
    for s in heard:
        if s.get("amendment") and s["when"] >= today:
            add(s, True)
    return out


def committee_row(row, bill=""):
    """A bill's row as its committee's followers are sent it: the meeting,
    without what is the bill's alone (its form, its amendment's link). A
    committee's row names no bill, and a hearing on a proposed amendment
    named the amendment alone -- "a proposed non-germane amendment
    (2026-0422h)", which tells a reader nothing (the review of 26 October
    2026) -- so its words name `bill`, the bill's label, as the Testify
    pane does: "a proposed non-germane amendment (2026-0422h) to HB
    1560-FN". mail.js weekAhead takes it for the same meeting as the bill's
    own row, for a reader who follows both."""
    out = {k: v for k, v in row.items() if k not in ("form", "amendment_num")}
    if out.get("amendment") and bill:
        out["amendment"] = line(f"{out['amendment']} to {bill}", 120)
    return out


def dump(obj, compact=True):
    if compact:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def write(site, *, built, sitting_term, followable, lists, upcoming, hints, led, why="",
          ledger_out=CANDIDATE):
    """Decide what is new, write site/changes/ and the ledger this build
    leaves (`led` is load()'s, None where there is none, and `why` its
    reason). Returns the lines to print."""
    tonight = built[:10]
    ledger, new_by, counts = decide(led, tonight=tonight, built=built, sitting_term=sitting_term,
                                    followable=followable, lists=lists, hints=hints)
    out = Path(site) / FOLDER
    out.mkdir(parents=True, exist_ok=True)
    files = {"current.json": current_file(tonight, built, sitting_term, new_by, followable,
                                          upcoming)}
    for d in window(tonight):
        files[f"{d}.json"] = night_file(ledger, d, new_by, followable, lists)
    for name, obj in files.items():
        (out / name).write_text(dump(obj), encoding="utf-8", newline="\n")
    # The folder is this build's alone: a night it did not write is a gap or a
    # second way of deciding "new", both of which the sender refuses.
    stale = sorted(p for p in out.glob("*") if p.is_file() and p.name not in files)
    for p in stale:
        p.unlink()
    Path(ledger_out).parent.mkdir(parents=True, exist_ok=True)
    Path(ledger_out).write_text(dump(ledger, compact=False), encoding="utf-8", newline="\n")

    said = []
    tonight_refs = files[f"{tonight}.json"]["refs"]
    by_kind = {}
    for k in followable:
        by_kind[kind_of_key(k)] = by_kind.get(kind_of_key(k), 0) + 1
    said.append(f"changes/: {len(followable):,} followable ("
                + ", ".join(f"{n:,} {k}s" for k, n in sorted(by_kind.items())) + f"), {new_by}")
    # Counted by record: a roll call new to its bill and its topic is two.
    said.append((f"  {counts['new']:,} records' items placed by their own dates across the "
                  "eight nights; " if new_by == RECORD_DATE
                  else f"  {counts['new']:,} records' items new tonight; ")
                + f"{tonight}.json names {len(tonight_refs):,} records, {counts['ended']:,} ended"
                + (f", {counts['taken_back']:,} endings taken back (the record is followable "
                   "again)" if counts["taken_back"] else ""))
    said.append(f"  {len(files) - 1} nights written, {len(stale)} stale file(s) removed; the "
                f"ledger carries {counts['carried']:,} records' items -> "
                f"{Path(ledger_out).as_posix()}")
    if new_by == RECORD_DATE:
        said.append(f"  WARNING: the changes files go by the record's dates tonight, not by "
                    f"first-seen: {why}. Each night holds the items dated the day before it, so "
                    "an item that arrived late is not sent; the ledger is seeded from what is "
                    "here, and the next night goes by first-seen again once nightly.py keeps it")
    if not followable:
        said.append("  WARNING: nothing is followable tonight: no bill, member, committee or "
                    "topic passed its test, so the sender has nothing to offer")
    problems = check(out)
    for p in problems[:10]:
        said.append(f"  WARNING: the changes files break their contract: {p}")
    if len(problems) > 10:
        said.append(f"  ... and {len(problems) - 10} more")
    return said


# ---- the contract, held in Python ------------------------------------------------------
# The rules of workers/follow/changes.js (each file) and check_changes.js (the
# folder), so that a build is held to them on a branch without the sender's
# code. Every note the sender would make about an entry is a problem here:
# the build should write nothing the sender has to forgive.

def _text(v, room, where, out, required=True):
    if v is None or v == "":
        if required:
            out.append(f"{where}: missing")
        return
    if not isinstance(v, str):
        out.append(f"{where}: not text")
        return
    if len(v) > room:
        out.append(f"{where}: longer than {room}")
    if required and not " ".join(v.split()):
        out.append(f"{where}: empty")


def _head(obj, out):
    if not isinstance(obj, dict):
        out.append("the file is not a JSON object")
        return False
    ok = True
    for f, rx, said in (("date", DAY, "date is not YYYY-MM-DD"),
                        ("built", STAMP, "built is not YYYY-MM-DDTHH:MM:SSZ"),
                        ("sitting_term", TERM, "sitting_term is not YYYY-YYYY")):
        if not (isinstance(obj.get(f), str) and rx.match(obj[f])):
            out.append(said)
            ok = False
    if obj.get("format") != 1:
        out.append("format is not 1")
        ok = False
    if obj.get("new_by") not in (FIRST_SEEN, RECORD_DATE):
        out.append("new_by is neither first-seen nor record-date")
        ok = False
    return ok


def _item(it, where, first_seen, topic, out):
    if not isinstance(it, dict):
        out.append(f"{where}: not an object")
        return None
    g = it.get("guid")
    if not (isinstance(g, str) and g and len(g) <= 300):
        out.append(f"{where}: no usable guid")
        return None
    if not (isinstance(it.get("date"), str) and DAY.match(it["date"])):
        out.append(f"{where}: date is not YYYY-MM-DD")
        return None
    _text(it.get("summary"), 300, f"{where} summary", out)
    if "plain" in it:
        _text(it.get("plain"), 300, f"{where} plain", out)
    if not isinstance(it.get("kind"), str) or not it["kind"]:
        out.append(f"{where}: no kind")
    if "term" in it and not (isinstance(it["term"], str) and TERM.match(it["term"])):
        out.append(f"{where}: term is not YYYY-YYYY")
    if topic and not it.get("term"):
        out.append(f"{where}: a topic's item has no term")
    if "seen" in it and not (isinstance(it["seen"], str) and STAMP.match(it["seen"])):
        out.append(f"{where}: seen is not a UTC timestamp")
    if first_seen and not it.get("seen"):
        out.append(f"{where}: no seen, under first-seen")
    if it.get("url") not in (None, "") and not (isinstance(it["url"], str) and PATH.match(it["url"])):
        out.append(f"{where}: url is not a path on the site")
    if "milestone" in it and it["milestone"] is not True:
        out.append(f"{where}: milestone is not true")
    if "vote" in it:
        v = it["vote"]
        if not isinstance(v, dict) or not v.get("ballot"):
            out.append(f"{where}: vote has no ballot")
        else:
            for f, room in VOTE_FIELDS.items():
                _text(v.get(f), room, f"{where} vote {f}", out, required=f == "ballot")
            if v.get("result") not in (None, "") and v["result"] not in RESULTS:
                out.append(f"{where}: vote result is neither passed nor failed")
    if "rollcall" in it and not rollcall_ok(it["rollcall"]):
        out.append(f"{where}: rollcall is not yeas, nays and passed, with an optional need, "
                   "rule and parties")
    if "meeting" in it:
        m = it["meeting"]
        if meeting_detail(m) != m:
            out.append(f"{where}: meeting is not a kind and a day, with an optional time, "
                       "venue and state")
    return it


def check_files(files):
    """files: {name: parsed JSON, or None for a file that is not JSON}.
    Every problem the sender's code would note, and every rule across files."""
    out = []
    names = sorted(files)
    nights_n = [f for f in names if re.match(r"^\d{4}-\d{2}-\d{2}\.json$", f)]
    if "current.json" not in names:
        out.append("current.json: missing")
    if not nights_n:
        out.append("no night's file at all")
    current, nights = None, []
    for f in names:
        obj, p = files[f], []
        if obj is None:
            out.append(f"{f}: not JSON")
            continue
        if f == "current.json":
            if _head(obj, p) and not isinstance(obj.get("followable"), dict):
                p.append("followable is not an object")
            elif isinstance(obj, dict) and "upcoming" in obj and not isinstance(obj["upcoming"], dict):
                p.append("upcoming is not an object")
            if not p:
                for k, v in obj["followable"].items():
                    if not key_ok(k):
                        p.append(f"followable {k[:40]}: not a record key")
                        continue
                    if not isinstance(v, dict):
                        p.append(f"followable {k}: not an object")
                        continue
                    _text(v.get("label"), 120, f"followable {k} label", p)
                    _text(v.get("title"), 300, f"followable {k} title", p, required=False)
                    _text(v.get("now"), 120, f"followable {k} now", p, required=False)
                    _text(v.get("sort"), 120, f"followable {k} sort", p, required=False)
                    if v.get("chamber") not in (None, "") and v["chamber"] not in CHAMBERS.values():
                        p.append(f"followable {k}: chamber is neither House nor Senate")
                    u = v.get("url")
                    if u not in (None, "") and not (isinstance(u, str) and PATH.match(u)):
                        p.append(f"followable {k}: url is not a path on the site")
                for k, rows in (obj.get("upcoming") or {}).items():
                    if not key_ok(k):
                        p.append(f"upcoming {k[:40]}: not a record key")
                        continue
                    if not isinstance(rows, list):
                        p.append(f"upcoming {k}: not a list")
                        continue
                    for i, u in enumerate(rows):
                        w = f"upcoming {k}[{i}]"
                        if not isinstance(u, dict) or not DAY.match(str(u.get("date") or "")):
                            p.append(f"{w}: no date")
                            continue
                        _text(u.get("what"), 120, f"{w} what", p)
                        if u.get("time") not in (None, "") and not TIME.match(str(u["time"])):
                            p.append(f"{w}: time is not HH:MM")
                        for fld in ("committee", "venue", "amendment"):
                            _text(u.get(fld), 120, f"{w} {fld}", p, required=False)
                        if u.get("form") not in (None, "") and u["form"] not in CHAMBERS:
                            p.append(f"{w}: form is neither H nor S")
                        if u.get("amendment_num") not in (None, "") and not (
                                isinstance(u["amendment_num"], str)
                                and AMENDMENT_OPENS.match(u["amendment_num"])):
                            p.append(f"{w}: amendment_num is not an amendment's number")
                current = obj if not p else None
        elif f in nights_n:
            if _head(obj, p):
                if not isinstance(obj.get("refs"), dict):
                    p.append("refs is not an object")
                if obj.get("date") != f[:10]:
                    p.append(f"date {str(obj.get('date'))[:10]} is not the file's own {f[:10]}")
            if not p:
                fs = obj["new_by"] == FIRST_SEEN
                for k, r in obj["refs"].items():
                    if not key_ok(k):
                        p.append(f"refs {k[:40]}: not a record key")
                        continue
                    if not isinstance(r, dict):
                        p.append(f"refs {k}: not an object")
                        continue
                    if "items" in r and not isinstance(r["items"], list):
                        p.append(f"refs {k} items: not a list")
                    for i, it in enumerate(r.get("items") or []):
                        _item(it, f"refs {k} items[{i}]", fs, kind_of_key(k) == "topic", p)
                    s = r.get("study")
                    if s is not None:
                        if not isinstance(s, dict) or s.get("recommends", 0) not in (True, False, None) \
                                or "recommends" not in s:
                            p.append(f"refs {k} study: recommends is not true, false or null")
                        else:
                            _item(dict(s, kind="study"), f"refs {k} study", fs, False, p)
                    e = r.get("ended")
                    if e is not None:
                        if not isinstance(e, dict) or not HOW.match(str(e.get("how") or "")):
                            p.append(f"refs {k} ended: how is not a word")
                        if isinstance(e, dict):
                            _text(e.get("summary"), 300, f"refs {k} ended summary", p,
                                  required=False)
                            if not DAY.match(str(e.get("date") or "")):
                                p.append(f"refs {k} ended: date is not YYYY-MM-DD")
                            if e.get("becomes") is not None and not (
                                    kind_of_key(k) == "lsr" and key_ok(e["becomes"])
                                    and kind_of_key(e["becomes"]) == "bill"):
                                p.append(f"refs {k} ended: becomes is not a bill's key")
                nights.append(obj)
        else:
            p.append("not a changes file's name")
        out += [f"{f}: {x}" for x in p]

    bases = {o["new_by"] for o in [current, *nights] if o}
    if len(bases) > 1:
        out.append(f"new_by differs between files: {', '.join(sorted(bases))}")
    nights.sort(key=lambda o: o["date"])
    if nights:
        if current and nights[-1]["date"] != current["date"]:
            out.append(f"the newest night is {nights[-1]['date']} and current.json's date is "
                       f"{current['date']}")
        for a, b in zip(nights, nights[1:]):
            if day_shift(b["date"], -1) != a["date"]:
                out.append(f"no night between {a['date']} and {b['date']}")
        if len(nights) < NIGHTS_KEPT:
            out.append(f"{len(nights)} night(s) kept, fewer than {NIGHTS_KEPT}")
    seen, ended, named = {}, set(), set()

    def once(key, guid, d, what):
        if (key, guid) in seen:
            out.append(f"{key}: {what} {guid[:80]} is in {seen[(key, guid)]} and {d}")
        else:
            seen[(key, guid)] = d
    for n in nights:
        want = day_shift(n["date"], -1) if n["new_by"] == RECORD_DATE else None
        for k, r in n["refs"].items():
            if not isinstance(r, dict):
                continue
            named.add(k)
            for it in r.get("items") or []:
                if isinstance(it, dict) and isinstance(it.get("guid"), str):
                    once(k, it["guid"], n["date"], "item")
                    if want and it.get("date") != want:
                        out.append(f"{n['date']}.json: {k} item {it['guid'][:60]} is dated "
                                   f"{it.get('date')}; under record-date this night holds "
                                   f"{want} only")
            if isinstance(r.get("study"), dict):
                once(k, r["study"].get("guid") or "study", n["date"], "study report")
                if want and r["study"].get("date") != want:
                    out.append(f"{n['date']}.json: {k} study is dated {r['study'].get('date')}; "
                               f"under record-date this night holds {want} only")
            if r.get("ended") is not None:
                once(k, "(ended)", n["date"], "ending")
                ended.add(k)
    if current:
        for k in sorted(named):
            if kind_of_key(k) in ENDS and k not in current["followable"] and k not in ended:
                out.append(f"{k}: named by a night, no longer followable, and no night says "
                           "it ended")
    return out


def check(folder):
    """check_files() over a folder of changes files, as written."""
    files = {}
    for p in sorted(Path(folder).glob("*.json")):
        try:
            files[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            files[p.name] = None
    return check_files(files)


def ended_owed(last_current, current, night):
    """The rule a folder cannot hold, held across two builds: every bill,
    member or committee last night's current.json listed and tonight's does
    not carries an "ended" in tonight's night. Returns the keys that do not."""
    gone = [k for k in (last_current.get("followable") or {})
            if k not in (current.get("followable") or {}) and kind_of_key(k) in ENDS]
    refs = night.get("refs") or {}
    return sorted(k for k in gone if not (refs.get(k) or {}).get("ended"))
