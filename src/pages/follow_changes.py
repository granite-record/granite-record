#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-07.1
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
released"). The ledger holds every guid the feeds carry with the night it
was first published, so a docket row entered three days after the day it
records goes out the next morning, dated by the record and filed under the
night it appeared. Each item is filed under exactly one night, which is the
contract's rule that a record's item is in at most one night's file.

THE LEDGER, archive/first-seen.json. Carried between nights in the night's
state, as archive/census.json is (cloud_kit.json's "state" list), because
GitHub's machine starts empty and a build may not read a previous run's
site/: a fresh clone must build the same site from the same inputs. It holds

  followable    every key current.json listed, with its label: what tonight
                compares with to find a record that has left, which is owed
                an "ended", and what that ending calls it
  nights        the eight nights the files carry: each night's built stamp,
                sitting term, the guids first seen in it (by the build that
                saw them) and the endings told in it
  carried       every guid the feeds carried on any of the last eight nights,
                by the last night that carried it

Nothing else, so it stays bounded: a guid no feed has carried for eight
nights, and that no kept night files, is let go. The eight-night memory is
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
NIGHTS_KEPT = 8                       # the contract's "the last eight nights at least"
LEDGER = Path("archive/first-seen.json")
CANDIDATE = Path("archive/first-seen.next.json")
FOLDER = "changes"                    # under site/

FIRST_SEEN, RECORD_DATE = "first-seen", "record-date"
ITEM_KINDS = ("action", "hearing", "scheduled", "exec", "vote", "report", "sponsor",
              "sitting", "study")
ENDS = ("bill", "member", "committee")          # the kinds an ending is owed for

# The four kinds of key, as workers/follow/common.js's REF has them.
REF = {
    "bill": re.compile(r"^\d{4}/[A-Z]{2,6}\d{1,4}$"),
    "member": re.compile(r"^\d{1,7}$"),
    "committee": re.compile(r"^[A-Za-z]\d{2,3}(?:-\d{4})?$"),
    "topic": re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
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
REPORT = re.compile(r"^(?:(?:Majority|Minority|Conference) )?Committee Report\b", re.I)
STUDY_REPORT = re.compile(r"^Interim Study Report\b", re.I)


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


def item(guid, day, kind, summary, url="", term="", study=False, recommends=None):
    """One feed item as the changes files carry it, or None where it cannot
    be one (no guid, no date the contract reads). `study` marks a bill's
    interim study report, which its bill's night carries as "study"."""
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
    if not isinstance(led, dict) or led.get("format") != FORMAT or \
            not isinstance(led.get("nights"), dict) or not isinstance(led.get("carried"), dict) \
            or not isinstance(led.get("followable"), dict) or not DAY.match(str(led.get("date"))):
        return None, f"{p.as_posix()} is not a ledger of format {FORMAT}"
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
    # The guids a night may file: those of a record followable tonight, or
    # one that leaves tonight (its last items go with its ending).
    prev_follow = dict((led or {}).get("followable") or {})
    gone = sorted(k for k in prev_follow if k not in followable and kind_of_key(k) in ENDS)
    fileable = {}
    for key in list(followable) + gone:
        for it in lists.get(key) or []:
            fileable.setdefault(it["guid"], it)
    every = {it["guid"]: it for its in lists.values() for it in its}

    nights = {}
    counts = {"new": 0, "ended": 0, "taken_back": 0}
    if led is None:
        new_by = RECORD_DATE
        for d in days:
            nights[d] = {"built": built, "sitting_term": sitting_term,
                         "first_seen": {}, "ended": {}}
        for g, it in sorted(fileable.items()):
            d = day_shift(it["date"], 1)
            if d in keep:
                nights[d]["first_seen"].setdefault(built, []).append(g)
                counts["new"] += 1
        # What record-date placed, and everything older, is known from now on;
        # an item dated tonight or later is not, and is new tomorrow.
        carried = {g: tonight for g, it in every.items() if it["date"] < tonight}
    else:
        new_by = FIRST_SEEN
        known = {}
        for d, gs in (led.get("carried") or {}).items():
            for g in gs:
                known[g] = max(d, known.get(g, ""))
        for d, n in (led.get("nights") or {}).items():
            for gs in (n.get("first_seen") or {}).values():
                for g in gs:
                    known.setdefault(g, d)
            if d in keep:
                nights[d] = {"built": n.get("built") or built,
                             "sitting_term": n.get("sitting_term") or sitting_term,
                             "first_seen": {s: list(gs) for s, gs in
                                            (n.get("first_seen") or {}).items()},
                             "ended": dict(n.get("ended") or {})}
        here = nights.setdefault(tonight, {"built": built, "sitting_term": sitting_term,
                                           "first_seen": {}, "ended": {}})
        here["built"], here["sitting_term"] = built, sitting_term
        new = sorted(g for g in fileable if g not in known)
        if new:
            here["first_seen"].setdefault(built, [])
            here["first_seen"][built] = sorted(set(here["first_seen"][built]) | set(new))
        counts["new"] = len(new)
        # A record that left gets its ending tonight; one that is back has
        # its ending taken back, from whichever kept night told it.
        old_term = led.get("sitting_term") or sitting_term
        turned = old_term != sitting_term
        for k in gone:
            e = ending(k, prev_follow[k], term_turned=turned, old_term=old_term, hints=hints)
            e.setdefault("date", tonight)
            here["ended"][k] = {f: e[f] for f in ("how", "summary", "date", "guid") if e.get(f)}
            counts["ended"] += 1
        for n in nights.values():
            for k in [k for k in n["ended"] if k in followable]:
                del n["ended"][k]
                counts["taken_back"] += 1
        carried = {g: d for g, d in known.items() if d >= days[0]}
        for g in every:
            carried[g] = tonight
    for d in days:
        nights.setdefault(d, {"built": built, "sitting_term": sitting_term,
                              "first_seen": {}, "ended": {}})
    by_day = {}
    for g, d in carried.items():
        by_day.setdefault(d, []).append(g)
    ledger = {
        "format": FORMAT,
        "about": ("The first-seen ledger of the changes files (src/pages/follow_changes.py): "
                  "every guid the feeds carried in the last eight nights, by the last night "
                  "that carried it; the guids first seen in each kept night; the endings "
                  "told; and what tonight listed as followable."),
        "date": tonight, "built": built, "sitting_term": sitting_term, "new_by": new_by,
        "followable": {k: followable[k]["label"] for k in sorted(followable)},
        "nights": {d: {"built": n["built"], "sitting_term": n["sitting_term"],
                       "first_seen": {s: sorted(gs) for s, gs in sorted(n["first_seen"].items())},
                       "ended": {k: n["ended"][k] for k in sorted(n["ended"])}}
                   for d, n in sorted(nights.items()) if d in keep},
        "carried": {d: sorted(gs) for d, gs in sorted(by_day.items())},
    }
    counts["carried"] = len(carried)
    return ledger, new_by, counts


# ---- the files ------------------------------------------------------------------------

def night_file(ledger, d, new_by, followable, lists):
    """One night's file, rewritten from the ledger and tonight's items."""
    n = ledger["nights"][d]
    filed = {g: s for s, gs in n["first_seen"].items() for g in gs}
    later = {k for dd, nn in ledger["nights"].items() if dd >= d for k in nn["ended"]}
    refs = {}
    for key in sorted(set(followable) | later):
        entry, items, studies, had = {}, [], [], set()
        for it in lists.get(key) or []:
            if it["guid"] not in filed or it["guid"] in had:
                continue
            had.add(it["guid"])
            out = {f: it[f] for f in ("guid", "date", "kind", "summary", "url", "term") if f in it}
            if new_by == FIRST_SEEN:
                out["seen"] = filed[it["guid"]]
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
                                     r.get("committee", ""), r.get("venue", "")))
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
    said.append((f"  {counts['new']:,} items placed by their own dates across the eight nights; "
                 if new_by == RECORD_DATE else f"  {counts['new']:,} items new tonight; ")
                + f"{tonight}.json names {len(tonight_refs):,} records, {counts['ended']:,} ended"
                + (f", {counts['taken_back']:,} endings taken back (the record is followable "
                   "again)" if counts["taken_back"] else ""))
    said.append(f"  {len(files) - 1} nights written, {len(stale)} stale file(s) removed; the "
                f"ledger carries {counts['carried']:,} guids -> {Path(ledger_out).as_posix()}")
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
                        for fld in ("committee", "venue"):
                            _text(u.get(fld), 120, f"{w} {fld}", p, required=False)
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
