#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.58
"""
Measure the signals in a transcript. Build nothing, tune nothing.

    python3 probe_alignment.py --transcript work/housecmte_2_11.txt \
        --expect HB1082,HB1520,HB1381 --data data

    python3 probe_alignment.py --work work --manifest verification_manifest.csv \
        --data data

WHY THIS EXISTS AND WHAT IT REFUSES TO DO

The aligner in this project was built before anyone read a transcript, and every
parameter in it was reasoned from an imagined hearing. It half-worked, which was
worse than failing, because it looked like something to tune. Three rounds of
widening tolerances later, a quarter of the site's proceedings are placed to
within fifteen minutes.

The marker parser that replaced it reports "23 of 23", "36 of 36", "18 of 18".
Those are RECALL: an announcement was found for every bill. They say nothing
about whether the timestamp is where the bill starts. No marker has ever been
checked against a real start time. Every one of them could be forty-five seconds
early and those numbers would not move.

So this tool measures and does not decide. It prints what the transcript
contains and leaves the modelling for after there is something to model
against.

FOUR QUESTIONS, EACH ANSWERED WITHOUT GROUND TRUTH

  1. Do titles beat numbers?
     Captions mangle "HB 1381" into "HP 1381" but render "enabling
     municipalities to remove political signs" as ordinary English, because
     that is what it is. If titles are found where numbers are not, the
     signal we have been searching for is the one ASR is worst at.

  2. Is the order monotonic?
     If a session takes its bills in agenda order, then finding boundaries is
     cutting a timeline into pieces, and one confident anchor constrains its
     neighbours. If committees skip around, that whole approach is out. This
     counts inversions rather than assuming either way.

  3. Do two independent signals agree?
     Where a number and a title both point at a bill, how far apart are they?
     Agreement between signals that share no code is worth more than either
     one's confidence in itself.

  4. On the floor, where does the spoken tally fall?
     The tallies are in RollCallSummary.txt already. A tally heard in the
     transcript is an anchor this tool did not generate, which makes it the
     only accuracy measurement available before hand-marking.
"""

import argparse
import proceedings as P
import site_read as SR
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

LINE = re.compile(
    r"^(?:(\d+):)?(\d{1,2}):(\d{2})"
    r"(?:\d+\s*hours?)?(?:,?\s*\d+\s*minutes?)?(?:,?\s*\d+\s*seconds?)?"
    r"\s*(.*)$")

BILL_SPOKEN = re.compile(
    r"\b(?:(House|Senate)\s*Bill|(HB|HP|SB|SP|CACR|CAC|HR|SR|HCR|SCR))\s*#?\s*"
    r"(\d[\d\s]{0,5}\d|\d)", re.I)
LETTER_FIX = {"HP": "HB", "SP": "SB", "CAC": "CACR"}

# Words too common to identify anything. Deliberately short: the aim is to keep
# the ordinary words of a title, because ordinary words are what ASR gets right.
STOP = set("""a an the of to in on for and or by with at from as is are be been
being this that these those it its relative certain establishing regarding
concerning act shall may not no any all other such under over into upon""".split())

WS = re.compile(r"\s+")
NONWORD = re.compile(r"[^a-z0-9 ]+")


def norm(s):
    return WS.sub(" ", NONWORD.sub(" ", (s or "").lower())).strip()


# What a work folder holds, in the order worth trying.
#
#   captions.en.json3   YouTube's own format. Each event carries tStartMs, and
#                       each word inside it carries tOffsetMs -- so the timing
#                       is per WORD, not per caption block. A block runs three
#                       to eight seconds, which is a floor on how precisely any
#                       boundary read from one can be placed. That floor has
#                       been in effect this whole time and did not need to be.
#   transcript.json     whatever the aligner wrote from those captions
#   *.txt               the copy-paste format, pasted by hand
WORK_FILES = ["captions.en.json3", "captions.en-orig.json3", "transcript.json"]


def _from_json3(doc):
    out = []
    for ev in doc.get("events") or []:
        base = ev.get("tStartMs")
        if base is None:
            continue
        segs = ev.get("segs") or []
        if not segs:
            continue
        for s in segs:
            w = (s.get("utf8") or "").strip()
            if not w or w == "\n":
                continue
            out.append(((base + (s.get("tOffsetMs") or 0)) / 1000.0, w))
    return out, "per word"


def _from_transcript_json(doc):
    """The aligner's own file. Its shape is not documented here, so several
    plausible ones are tried and an unknown one says so rather than returning
    an empty list that looks like an empty video."""
    rows = doc if isinstance(doc, list) else (
        doc.get("segments") or doc.get("lines") or doc.get("events") or [])
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        t = next((r[k] for k in ("start", "t", "time", "tStartMs", "seconds")
                  if k in r and r[k] is not None), None)
        x = next((r[k] for k in ("text", "utf8", "line", "content")
                  if k in r and r[k]), None)
        if t is None or not x:
            continue
        t = float(t)
        if t > 100000:            # milliseconds
            t /= 1000.0
        out.append((t, str(x).strip()))
    return out, "per line"


def read_floor(path=None):
    """({video_id: [bills]}, {(video, bill): row, "_whole": {videos}}).

    From proceedings.csv now. Same return shape as before, so the callers did
    not change -- only the source did. The floor index and the manifest used
    to be read here separately, and that split is what let five tools in one
    day forget the floor existed.
    """
    rows = P.load()
    bills, ent, whole = defaultdict(list), {}, set()
    for r in P.floor_only(rows):
        v = r["video_id"]
        if not v:
            continue
        if r["whole_video"]:
            whole.add(v)
        if r["bill"] not in bills[v]:
            bills[v].append(r["bill"])
        ent[(v, r["bill"])] = r
    ent["_whole"] = whole
    return dict(bills), ent


def _manifest_rows():
    """Committee rows from proceedings.csv in the manifest's column names.

    Every site below was written against the manifest's columns. Rather than
    rewrite each, the table is presented in that shape. Floor rows are not
    here; read_floor() carries those.
    """
    for r in P.committee_only(P.load()):
        yield {"video_id": r["video_id"], "bill": r["bill"],
               "proceeding": r["kind"], "sched_date": r["date"],
               "sched_time": r["time"], "committee": r["committee"],
               "body": r["body"], "predicted_offset": r["predicted_offset"]}


def suggest(work, manifest):
    """Which recordings to sample, and the exact command to do it.

    Choosing a sample meant knowing which work folder is a Senate floor day and
    which is a House executive session, and nothing said. So this reads the
    manifest, keeps only recordings whose captions are already on disk, and
    groups them by chamber and setting -- then prints the paths, so picking one
    of each is copying a line rather than guessing at a folder name.
    """
    have = {d.name for d in Path(work).iterdir()
            if d.is_dir() and any((d / f).exists() for f in WORK_FILES)}
    floor, _fe = read_floor()
    _fe = dict(_fe)
    if not have:
        print(f"No folder under {work}/ holds captions yet.")
        return
    byvid = defaultdict(lambda: {"kinds": Counter(), "bills": set()})
    for v, bills in floor.items():
        if v in have:
            d = byvid[v]
            d["body"] = "?"
            d["date"] = ""
            d["committee"] = "floor"
            d["kinds"]["floor debate"] += len(bills)
            d["bills"].update(bills)
    for r in _manifest_rows():
        v = str(r.get("video_id") or "").strip()
        if v not in have:
            continue
        d = byvid[v]
        d["body"] = str(r.get("body") or "?")
        d["date"] = str(r.get("sched_date") or "")[:10]
        d["committee"] = str(r.get("committee") or "")
        d["kinds"][str(r.get("proceeding") or "").lower()] += 1
        d["bills"].add(str(r.get("bill") or ""))

    from_man = sum(1 for v in byvid if byvid[v]["committee"] != "floor")
    print(f"{len(have):,} recordings have captions on disk: {from_man:,} in the "
          f"manifest, {len(byvid) - from_man:,} in the floor index\n")
    groups = defaultdict(list)
    for v, d in byvid.items():
        main = d["kinds"].most_common(1)[0][0] if d["kinds"] else "?"
        kind = ("floor" if "floor" in main else
                "executive session" if "executive" in main else
                "hearing" if "hearing" in main else main)
        groups[(d["body"], kind)].append((len(d["bills"]), v, d))

    # What is missing in each direction, since that is the thing to go and
    # fetch rather than to model around.
    inman = {str(r.get("video_id") or "").strip() for r in _manifest_rows()}
    inman.discard("")
    no_caps = inman - have
    unknown = have - inman - set(floor)
    if no_caps:
        print(f"  {len(no_caps):,} recordings the manifest names have NO "
              "captions on disk yet.\n  Those cannot be aligned at all until "
              "they are fetched.\n")
    # The floor separately, because it is a whole setting rather than a
    # scattering of gaps -- and because a category that is entirely missing
    # looks the same as a category that does not exist.
    floor_have = set(floor) & have
    if floor:
        # Recordings whose title names the bill are not sessions to segment --
        # the whole recording IS that one proceeding. Counting them here made
        # floor coverage look far worse than it is: 133 of them are committees
        # of conference, complete as they stand and needing no captions.
        whole = _fe.get("_whole", set()) if isinstance(_fe, dict) else set()
        sessions = {v for v in floor if v not in whole}
        sess_have = sessions & have
        print(f"  FLOOR: {len(sessions):,} session recordings to segment, "
              f"{len(sess_have):,} with captions.")
        if whole:
            print(f"  ({len(whole):,} more name their bill in the title -- the "
                  "whole recording is\n  that proceeding, so there is nothing "
                  "to segment and no captions needed.)")
        floor_have = sess_have
        floor = {v: b for v, b in floor.items() if v in sessions}
        if not floor_have:
            print("  Not one. Every sample taken so far has been a committee "
                  "because a\n  floor session cannot be read at all -- the "
                  "captions were never\n  fetched for any of them.")
            biggest = sorted(floor.items(), key=lambda kv: -len(kv[1]))[:4]
            print("  The busiest, worth fetching first:")
            for v, bs in biggest:
                print(f"    {v}  {len(bs):>3} bills")
        print()
    if unknown:
        print(f"  {len(unknown):,} folders have captions but appear in neither "
              "the manifest nor\n  the floor index. Likely floor sessions, or "
              "recordings nothing was\n  matched to. e.g. "
              + ", ".join(sorted(unknown)[:4]) + "\n")

    for (body, kind), rows in sorted(groups.items()):
        rows.sort(reverse=True)
        who = "House" if body == "H" else "Senate" if body == "S" else body
        print(f"  {who} {kind}  ({len(rows)} recording(s))")
        for nb, v, d in rows[:3]:
            print(f"    {work}/{v:<14} {d['date']}  {nb:>2} bills  "
                  f"{d['committee'][:34]}")
        print()

    # One of each, largest first, which is the sample worth taking.
    pick = []
    for key in sorted(groups):
        rows = sorted(groups[key], reverse=True)
        if rows:
            pick.append(f"{work}/{rows[0][1]}")
    if pick:
        print("One of each, ready to paste:\n")
        # One line, because a continuation character is a shell detail and
        # this has already tripped over cmd once.
        print("python3 probe_alignment.py --data data --context --transcript "
              + " ".join(pick))


class NoTranscript(Exception):
    """This recording cannot be read. One of several should not stop the rest."""


def read_transcript(path):
    """[(seconds, text)] from whatever a work folder actually holds."""
    p = Path(path)
    # A path that is not there at all took a different route out of here than
    # one that is there and empty, and only the second was caught.
    if not p.exists():
        raise NoTranscript("no such folder -- nothing has been fetched for "
                           "this recording")
    if p.is_dir():
        for name in WORK_FILES:
            if (p / name).exists():
                p = p / name
                break
        else:
            txt = sorted(p.glob("*.txt"))
            if not txt:
                inside = [x.name for x in p.iterdir()]
                raise NoTranscript(
                    "empty folder -- captions never fetched for this recording"
                    if not inside else
                    f"holds none of {', '.join(WORK_FILES)}; it has "
                    + ", ".join(inside[:4]))
            p = txt[0]

    if p.suffix.lower() in (".json3", ".json"):
        doc = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        out, how = (_from_json3(doc) if "events" in doc and
                    isinstance(doc.get("events"), list)
                    else _from_transcript_json(doc))
        if not out:
            raise NoTranscript(f"{p.name} parsed but held no timed text; its "
                               f"top-level keys are {list(doc)[:6]}")
        print(f"  {p.name}: {len(out):,} timed items, {how}")
        return out

    out = []
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(raw.strip())
        if not m:
            continue
        h, mn, sc, text = m.groups()
        t = int(h or 0) * 3600 + int(mn) * 60 + int(sc)
        if text.strip():
            out.append((t, text.strip()))
    print(f"  {p.name}: {len(out):,} caption lines, per line")
    return out


def keywords(title):
    """The words in a title that identify it.

    Not a phrase. A phrase fails the moment a caption drops or inserts a word,
    and they do constantly -- "defining citizenship purposes" does not appear
    in "defining citizenship FOR purposes of voter registration", which is what
    the chair actually said. A bag of words survives that; a phrase does not.
    """
    return sorted({w for w in norm(title).split()
                   if w not in STOP and len(w) > 3})


def as_lines(rows, gap=1.2):
    """Group word-level rows into readable lines, keeping the first word's time.

    The matchers look for a bill number or a run of title words, and neither is
    findable one word at a time. But the time kept for a group is the time of
    its FIRST word, not of the caption block it came from -- which is the whole
    gain: a boundary lands where the word was spoken.
    """
    if not rows:
        return rows
    if any(len(x[1].split()) > 3 for x in rows[:40]):
        return rows                       # already lines
    out, cur, t0, last = [], [], rows[0][0], rows[0][0]
    for t, w in rows:
        if t - last > gap and cur:
            out.append((t0, " ".join(cur)))
            cur, t0 = [], t
        cur.append(w)
        last = t
    if cur:
        out.append((t0, " ".join(cur)))
    return out


def find_numbers(lines, candidates):
    """{bill: [seconds]} for every spoken bill number, matched to the docket."""
    bydigits = defaultdict(list)
    for c in candidates:
        bydigits[re.sub(r"[^0-9]", "", c)].append(c)
    hits = defaultdict(list)
    for t, text in lines:
        for m in BILL_SPOKEN.finditer(text):
            kind = (m.group(2) or ("HB" if (m.group(1) or "").lower().startswith("h")
                                   else "SB")).upper()
            kind = LETTER_FIX.get(kind, kind)
            digits = re.sub(r"\s", "", m.group(3))
            same = bydigits.get(digits, [])
            pick = next((c for c in same if c.startswith(kind)), None) \
                or (same[0] if same else None)
            if pick:
                hits[pick].append(t)
    return hits


def find_titles(lines, titles, span=45, need=0.6):
    """{bill: [seconds]} from title wording, which captions handle far better.

    A title is read across several caption lines, so the window is a span of
    seconds rather than a count of lines. A window counts as a hit when it
    holds most of the title's identifying words -- not all, because a caption
    will drop one, and not a fixed number, because titles vary in length.
    """
    words_at = [(t, set(norm(x).split())) for t, x in lines]
    hits = defaultdict(list)
    for bill, title in titles.items():
        kw = set(keywords(title))
        if len(kw) < 3:
            continue
        want = max(3, int(round(len(kw) * need)))
        for i, (t0, _) in enumerate(words_at):
            seen, first = set(), None
            for t, ws in words_at[i:]:
                if t - t0 > span:
                    break
                if ws & kw:
                    # Where a title word was actually said, not where the
                    # window that contains it happens to open. Reporting the
                    # window start put every title up to 45 seconds early --
                    # which read, in the context dump, as a title being spoken
                    # in the middle of the previous bill's roll call.
                    if first is None:
                        first = t
                    seen |= ws
            if len(seen & kw) >= want:
                hits[bill].append(first if first is not None else t0)
    return hits


def best_run(times, gap=180):
    """Where a bill was actually discussed, not where it was first named.

    A bill gets named in passing all day: the chair reads the agenda at the
    start, someone refers back to it later, the clerk lists what is coming.
    Taking the first mention treats an agenda readout as the proceeding, and
    on one real session that put two bills four hours from where they were
    taken up.

    The run that matters is the one with the most mentions packed closest
    together. Ties go to the earlier run, because a bill is discussed before
    it is referred back to.
    """
    runs = cluster(times, gap)
    if not runs:
        return None, 0, 0
    def score(r):
        span = max(1.0, r[-1] - r[0])
        return (len(r), -span)
    best = max(runs, key=score)
    return best[0], len(best), len(runs)


# Spoken tallies, as the captions render them. From one real session:
#   "Vote 16 to zero"      "voting is 16 to zip"    "15 to three"
#   "Vote is 16 to zip"    "16 to nothing"
# "zip" and "nothing" for nought are the chair's, not the captions'.
NUMWORD = {"zero": 0, "zip": 0, "nothing": 0, "none": 0, "one": 1, "two": 2,
           "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
           "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
           "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
           "eighteen": 18, "nineteen": 19, "twenty": 20}
TALLY_RE = re.compile(
    r"(?P<said>\b(?:vote|voting|votes|carries|cares|passes)\b[^.]{0,18}?)?"
    r"\b(?P<y>\d{1,2}|" + "|".join(NUMWORD) + r")\s+(?:to|-)\s+"
    r"(?P<n>\d{1,2}|" + "|".join(NUMWORD) + r")\b", re.I)


def _num(s):
    s = s.strip().lower()
    return int(s) if s.isdigit() else NUMWORD.get(s)


def find_tallies(lines):
    """[(seconds, yeas, nays)] every spoken vote count."""
    out = []
    for t, text in lines:
        for m in TALLY_RE.finditer(text):
            y, nn = _num(m.group("y")), _num(m.group("n"))
            if y is None or nn is None:
                continue
            # "the meeting will resume at 1 to 2 o'clock" is not a vote, and
            # neither is "section 3 to 5". A tally either says so in words, or
            # is large enough that nothing else in a hearing room reads that
            # way -- a House committee has ten to twenty members.
            said = bool(m.group("said"))
            if y + nn > 25:
                continue
            if not said and y + nn < 10:
                continue
            if said and y + nn < 3:
                continue
            out.append((t, y, nn))
    return out


def cluster(times, gap=180):
    """First time of each run of mentions, so one long discussion counts once."""
    out = []
    for t in sorted(times):
        if not out or t - out[-1][-1] > gap:
            out.append([t])
        else:
            out[-1].append(t)
    return out


def hms(s):
    """Word-level times are fractional, so keep the fraction where it matters.

    The whole point of reading json3 is sub-second placement; rounding it away
    in the display would hide the thing being measured.
    """
    s = float(s)
    whole = int(s)
    frac = s - whole
    base = f"{whole//3600}:{(whole%3600)//60:02d}:{whole%60:02d}"
    return base + (f".{int(round(frac*10))}" if 0 < frac < 0.95 else "")


def show_context(lines, expect, nums, tits, around=12, per_bill=4):
    """Print what is actually being said at every mention.

    Every reading of these mentions so far has been a guess: an agenda being
    read, a bill referred back to, a number the captions got wrong. The
    transcript settles it, and it is already on disk. Nothing here decides
    anything -- it is a window onto the evidence, so the next decision is made
    by reading rather than by inferring from a timestamp.
    """
    at = {t: i for i, (t, _) in enumerate(lines)}
    order = sorted(lines, key=lambda x: x[0])

    def words_around(t):
        i = min(range(len(order)), key=lambda k: abs(order[k][0] - t))
        lo, hi = max(0, i - 1), min(len(order), i + 3)
        return " ".join(x for _, x in order[lo:hi])

    print(f"\n{'=' * 74}\nWHAT IS BEING SAID AT EACH MENTION\n{'=' * 74}")
    for b in expect:
        hits = sorted([(x, "number") for x in (nums.get(b) or [])]
                      + [(x, "title") for x in (tits.get(b) or [])])
        if not hits:
            print(f"\n  {b}: never mentioned by either signal")
            continue
        runs = cluster([x for x, _ in hits])
        print(f"\n  {b}  ({len(hits)} mentions in {len(runs)} run(s))")
        seen = 0
        for r in runs:
            if seen >= per_bill:
                print(f"      ... {len(runs) - seen} more run(s)")
                break
            seen += 1
            kinds = {k for x, k in hits if r[0] <= x <= r[-1]}
            txt = WS.sub(" ", words_around(r[0]))
            print(f"    {hms(r[0]):>10}  {len(r):>2} mention(s), "
                  f"{'+'.join(sorted(kinds))}")
            print(f"        ...{txt[:150]}...")


def report(name, lines, expect, titles, context=False, reports=None,
           sched=None, floor_entries=None, is_floor=False):
    print(f"\n{'=' * 74}\n{name}")
    print(f"{'=' * 74}")
    print(f"  {len(lines):,} caption lines, {hms(lines[-1][0]) if lines else '0'} long")
    print(f"  {len(expect)} bills the docket says were taken up")
    # Kept because Question 2 narrows `expect` to the bills the docket puts in
    # a definite order, and the counts above were taken against all of them.
    # Returning the narrowed length made the cross-transcript summary report
    # finding 113% of the bills.
    n_expect = len(expect)

    nums = find_numbers(lines, expect)
    tits = find_titles(lines, {b: titles[b] for b in expect if titles.get(b)})
    no_title = [b for b in expect if not titles.get(b)]
    if no_title:
        print(f"  {len(no_title)} of them have no title on file "
              f"({', '.join(no_title[:3])})")

    both = [b for b in expect if nums.get(b) and tits.get(b)]
    only_n = [b for b in expect if nums.get(b) and not tits.get(b)]
    only_t = [b for b in expect if tits.get(b) and not nums.get(b)]
    neither = [b for b in expect if not nums.get(b) and not tits.get(b)]

    if is_floor and len(expect) > 60:
        print(f"  A floor calendar lists every bill before the chamber that "
              "day. Most pass\n  on the consent calendar without being named "
              "aloud, so a bill nothing\n  mentions is usually a bill nobody "
              "debated, not one this missed.")

    print(f"\n  QUESTION 1  which signal finds the bill")
    print(f"    number and title      {len(both):>3}")
    print(f"    number only           {len(only_n):>3}"
          + (f"   {', '.join(only_n[:5])}" if only_n else ""))
    print(f"    title only            {len(only_t):>3}"
          + (f"   {', '.join(only_t[:5])}" if only_t else ""))
    print(f"    neither               {len(neither):>3}"
          + (f"   {', '.join(neither[:5])}" if neither else ""))
    found_n = len(both) + len(only_n)
    found_t = len(both) + len(only_t)
    print(f"    numbers found {found_n}/{len(expect)}, "
          f"titles found {found_t}/{len(expect)}")

    print(f"\n  QUESTION 3  where the two signals disagree")
    if both:
        gaps = []
        for b in both:
            n0 = cluster(nums[b])[0][0]
            t0 = cluster(tits[b])[0][0]
            gaps.append((abs(n0 - t0), b, n0, t0))
        gaps.sort()
        med = gaps[len(gaps) // 2][0]
        print(f"    median gap between first number and first title: {med:.1f}s")
        print(f"    within 30s: {sum(1 for g,_,_,_ in gaps if g <= 30)}/{len(gaps)}"
              f"   within 3 min: {sum(1 for g,_,_,_ in gaps if g <= 180)}/{len(gaps)}")
        for g, b, n0, t0 in gaps[-3:]:
            print(f"      {b:<9} number at {hms(n0)}, title at {hms(t0)}  "
                  f"apart by {hms(g)}")
    else:
        print("    no bill was found by both signals")

    # How much of a difference the choice of estimator makes.
    print(f"\n  FIRST MENTION versus BUSIEST RUN")
    moved = []
    for b in expect:
        all_t = sorted((tits.get(b) or []) + (nums.get(b) or []))
        if not all_t:
            continue
        first = all_t[0]
        start, size, runs = best_run(all_t)
        if start is not None and abs(start - first) > 120:
            moved.append((abs(start - first), b, first, start, size, runs))
    if moved:
        moved.sort(reverse=True)
        print(f"    {len(moved)} of {len(expect)} bills move by more than two "
              "minutes:")
        for d, b, f, s, size, runs in moved[:5]:
            print(f"      {b:<9} first named {hms(f)}, busiest run starts "
                  f"{hms(s)} ({size} mentions, {runs} runs)  moved {hms(d)}")
        print("      Where a bill is named once early and discussed later, the "
              "early\n      mention is the agenda being read, not the "
              "proceeding.")
    else:
        print("    no bill moves by more than two minutes; first mention and "
              "busiest\n    run agree throughout")

    # A tally the committee report also records is an anchor this tool did
    # not generate -- the strongest kind of evidence available, and the same
    # kind floor_markers.py already uses on the floor.
    if reports:
        tal = find_tallies(lines)
        want = {}
        for b in expect:
            for grp in reports.get(b, []):
                for r in grp.get("reports", []):
                    if r.get("vote_yeas") is not None:
                        want[b] = (r["vote_yeas"], r.get("vote_nays") or 0)
        print(f"\n  QUESTION 4  spoken vote tallies against the committee report")
        print(f"    {len(tal)} tallies heard; {len(want)} of {len(expect)} bills "
              "have a recorded committee vote")
        # A tally only identifies a bill if no other bill that day shares it
        # AND it was heard once. Nine bills reported 16-0 on one session, so a
        # 16-0 in the captions names none of them. Counting those as matches
        # would put a confident timestamp on a guess.
        share = Counter(want.values())
        anchors, ambiguous, unheard = [], [], []
        for b, (y, nn) in sorted(want.items()):
            same = [x for x in tal if x[1] == y and x[2] == nn]
            if not same:
                unheard.append(b)
            elif share[(y, nn)] > 1 or len(same) > 1:
                ambiguous.append((b, y, nn, share[(y, nn)], len(same)))
            else:
                anchors.append((b, y, nn, same[0][0]))
        if anchors:
            print(f"    {len(anchors)} tally is unique to one bill and heard "
                  "once -- an anchor:" if len(anchors) == 1 else
                  f"    {len(anchors)} tallies are unique to one bill and heard "
                  "once -- anchors:")
            for b, y, nn, when in anchors:
                print(f"      {b:<9} {y}-{nn} at {hms(when)}")
        if ambiguous:
            print(f"    {len(ambiguous)} cannot identify a bill:")
            for b, y, nn, nb, nh in ambiguous[:5]:
                why = []
                if nb > 1:
                    why.append(f"{nb} bills that day also voted {y}-{nn}")
                if nh > 1:
                    why.append(f"heard {nh} times")
                print(f"      {b:<9} {y}-{nn}: " + "; ".join(why))
        if unheard:
            print(f"    {len(unheard)} had no matching tally in the captions")
        print(f"\n    So {len(anchors)} of {len(want)} bills can be placed by "
              "their vote. The rest\n    share a tally with another bill or "
              "were not heard clearly, and a\n    tally that names several "
              "bills names none of them.")

    # The floor is the one place with an independent measurement. A roll
    # call's clock time gives the END of that bill's debate to the second, from
    # RollCallSummary rather than from anything read out of a transcript. So
    # transcript evidence can be checked against it instead of against itself.
    if floor_entries:
        rows = []
        for b in expect:
            e = floor_entries.get(b)
            if not e or not e.get("precise"):
                continue
            seen = sorted((tits.get(b) or []) + (nums.get(b) or []))
            if not seen:
                continue
            last = seen[-1]
            rows.append((abs(last - e["debate_end"]), b, last, e["debate_end"],
                         e.get("window_start")))
        if rows:
            rows.sort()
            print(f"\n  QUESTION 5  transcript against the roll call clock")
            print(f"    {len(rows)} bills have a roll-call end time from "
                  "RollCallSummary")
            med = rows[len(rows) // 2][0]
            print(f"    last mention against that end: median {hms(med)} apart")
            for d, b, last, end, ws in rows[:3] + rows[-2:]:
                print(f"      {b:<9} last heard {hms(last)}, roll call at "
                      f"{hms(end)}  ({hms(d)} apart)")
            near = sum(1 for d, *_ in rows if d <= 120)
            print(f"    {near} of {len(rows)} within two minutes")
            print("    A roll call closes the item, so the last mention should "
                  "sit just\n    before it. This is the only check here that "
                  "does not compare the\n    transcript with itself.")

    print(f"\n  QUESTION 2  is the order the docket's order")
    # Only where the docket STATES an order. Bills scheduled at the same
    # minute -- an executive session takes twenty at once -- were sorted by
    # bill number as a tiebreak when the manifest was written. Scoring against
    # that measures a sort key, and reported one session as ignoring an agenda
    # that never existed.
    sched = sched or {}
    slots = Counter(sched.get(b, "") for b in expect)
    tied = sum(v for v in slots.values() if v > 1)
    if tied and len(slots) <= 2:
        print(f"    all {tied} bills share a scheduled time, so the docket "
              "states no order\n    between them. Nothing to compare; skipping.")
        return {"expect": n_expect, "num": found_n, "title": found_t,
                "both": len(both), "either": len(both) + len(only_n) + len(only_t),
                "inversions": 0, "pairs": 0}
    if tied:
        print(f"    {tied} bills share a scheduled time with another; only "
              "bills the docket\n    puts in a definite order are counted")
    ordered = [b for b in expect if slots.get(sched.get(b, ""), 0) == 1]
    if len(ordered) < 3:
        print("    fewer than three bills have a time of their own; nothing to "
              "compare")
        return {"expect": n_expect, "num": found_n, "title": found_t,
                "both": len(both), "either": len(both) + len(only_n) + len(only_t),
                "inversions": 0, "pairs": 0}
    expect = ordered
    pos = {b: i for i, b in enumerate(expect)}

    def inv(pick):
        seq = sorted((pick(b), b) for b in expect
                     if (tits.get(b) or nums.get(b)) and pick(b) is not None)
        o = [b for _, b in seq]
        return o, sum(1 for i in range(len(o)) for j in range(i + 1, len(o))
                      if pos[o[i]] > pos[o[j]])

    def first_of(b):
        all_t = sorted((tits.get(b) or []) + (nums.get(b) or []))
        return all_t[0] if all_t else None

    def busiest_of(b):
        all_t = sorted((tits.get(b) or []) + (nums.get(b) or []))
        return best_run(all_t)[0] if all_t else None

    o_first, i_first = inv(first_of)
    o_busy, i_busy = inv(busiest_of)
    order, inversions = (o_first, i_first) if i_first <= i_busy else (o_busy, i_busy)
    pairs = len(order) * (len(order) - 1) // 2
    # Both, because which estimator is better is a question for the data. The
    # busiest run was assumed to be the improvement and made the ordering twice
    # as bad on the first session it met.
    print(f"    by first mention: {i_first} inverted pairs of {pairs}")
    print(f"    by busiest run:   {i_busy} inverted pairs of {pairs}"
          + ("   <- worse" if i_busy > i_first else
             "   <- better" if i_busy < i_first else ""))
    print(f"    first appearance, in time order:")
    print(f"      {' '.join(order[:12])}" + (" ..." if len(order) > 12 else ""))
    print(f"    the docket's order:")
    print(f"      {' '.join(expect[:12])}" + (" ..." if len(expect) > 12 else ""))
    print(f"    {inversions} inverted pairs out of {pairs}"
          + ("   the session followed the agenda" if not inversions
             else "   the session did NOT follow the agenda" if inversions > pairs * 0.2
             else "   mostly in order, with local swaps"))
    if context:
        show_context(lines, expect, nums, tits)
    return {"expect": n_expect, "num": found_n, "title": found_t,
            "both": len(both), "either": len(both) + len(only_n) + len(only_t),
            "inversions": inversions, "pairs": pairs}



# ---------------------------------------------------------- ground truth --
#
# 35 proceedings in verification_manifest.xlsx carry observed_start and
# observed_end: a person watched the video and wrote down when each bill
# actually began. That is the only thing in this project that was not
# generated by the thing it is used to check.
#
# It has been used once, to calibrate the clustering model. It has never been
# pointed at the marker parser, whose headline numbers -- 23 of 23, 36 of 36,
# 18 of 18 -- are recall and say nothing about accuracy.

CLOCK = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})(?:\.\d+)?\s*$")


def _sec(v):
    """Seconds, from any of the four ways a time gets into these files.

    A spreadsheet keeps a time as a fraction of a day, openpyxl hands it back
    as time or timedelta, and the same column saved as CSV becomes the text
    "0:56:57". All four mean the same thing.
    """
    from datetime import time as _t, timedelta as _td
    if v is None or v == "":
        return None
    if isinstance(v, _td):
        return v.total_seconds()
    if isinstance(v, _t):
        return v.hour * 3600 + v.minute * 60 + v.second
    s = str(v).strip()
    m = CLOCK.match(s)
    if m:
        h, mm, ss = m.groups()
        return int(h or 0) * 3600 + int(mm) * 60 + int(ss)
    try:
        f = float(s)
    except ValueError:
        return None
    # Under 1 it is a fraction of a day; above, already seconds.
    return f * 86400 if 0 < f < 1 else f


def read_rows(path):
    """Every row of the manifest, not just the marked ones."""
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        rows = list(load_workbook(p, read_only=True).active
                    .iter_rows(values_only=True))
    else:
        with p.open(encoding="utf-8-sig", newline="") as fh:
            rows = [tuple(r) for r in csv.reader(fh)]
    h = {str(c).strip(): i for i, c in enumerate(rows[0]) if c}
    out = []
    for r in rows[1:]:
        if len(r) <= max(h.values()):
            continue
        out.append({k: r[i] for k, i in h.items()})
    return out


def compare_manifests(a_path, b_path):
    """Two manifests, side by side.

    build_site_v2.py reads verification_manifest.csv. If a later run of the
    matching wrote a manifest covering a different session, the earlier one's
    proceedings -- and any hand-marked times in it -- simply stop reaching the
    site. Nothing errors. The hearings just stop being there.
    """
    A, B = read_rows(a_path), read_rows(b_path)

    def shape(rows, name):
        yrs = Counter(str(r.get("sched_date") or "")[:4] for r in rows)
        kinds = Counter(str(r.get("proceeding") or "").lower() for r in rows)
        vids = {str(r.get("video_id") or "") for r in rows if r.get("video_id")}
        marks = sum(1 for r in rows if str(r.get("observed_start") or "").strip())
        print(f"\n  {name}")
        print(f"    {len(rows):,} rows, {len(vids):,} videos, "
              f"{marks:,} hand-marked times")
        print("    years:  " + ", ".join(f"{k or '?'} {v:,}"
                                         for k, v in sorted(yrs.items())))
        print("    kinds:  " + ", ".join(f"{k} {v:,}"
                                         for k, v in kinds.most_common(4)))
        return vids, {(str(r.get("bill") or "").upper(),
                       str(r.get("sched_date") or "")[:10],
                       str(r.get("proceeding") or "").lower()) for r in rows}, marks

    va, ka, ma = shape(A, Path(a_path).name)
    vb, kb, mb = shape(B, Path(b_path).name)
    print(f"\n  videos in both: {len(va & vb):,}")
    print(f"  proceedings only in {Path(a_path).name}: {len(ka - kb):,}")
    print(f"  proceedings only in {Path(b_path).name}: {len(kb - ka):,}")
    print(f"  in both: {len(ka & kb):,}")
    lost = ka - kb
    if lost:
        by = Counter(k for _, _, k in lost)
        print("\n  what the second one does not have:")
        for k, v in by.most_common(5):
            print(f"    {v:>5,}  {k}")
    if ma and not mb:
        print(f"\n  {ma} hand-marked times are in {Path(a_path).name} and none "
              f"in {Path(b_path).name}.\n  Those are the only measurements of "
              "this system that a person made.\n  Merging them forward costs "
              "nothing and cannot be recreated.")
    if lost:
        print(f"\n  {len(lost):,} proceedings are in the first and not the "
              "second. If the\n  second is what build_site_v2.py reads, that "
              "is exactly what a reader\n  is not being shown -- and no "
              "alignment work will bring it back.")


def coverage(site, manifest):  # noqa: C901
    """Is every scheduled proceeding on the site?

    The manifest is the docket's own list of what was scheduled, video or no
    video. The site is what a reader can see. Comparing the two says whether a
    proceeding is placed badly or absent -- and those need different fixes.
    """
    want = defaultdict(list)
    for r in _manifest_rows():
        bill = str(r.get("bill") or "").strip().upper()
        when = str(r.get("sched_date") or "")[:10]
        kind = str(r.get("proceeding") or "").strip().lower()
        if bill:
            want[bill].append((when, kind, str(r.get("video_id") or "")))
    have = defaultdict(list)
    for _y, bid, s in site_stations(site):
        have[bid].append((str(s.get("when") or "")[:10],
                          str(s.get("what") or "").lower(),
                          str(s.get("video_id") or "")))

    seen = miss = 0
    bykind = Counter()
    # Two different failures wear the same face. A proceeding missing because
    # no recording was ever matched to it is a job half done; a proceeding
    # missing although the docket names it is a hole in the record, and a
    # reader looking at that bill is not told the hearing happened.
    byyear = defaultdict(lambda: [0, 0])
    byvideo = defaultdict(lambda: [0, 0])
    missing_examples = []
    for bill, rows in want.items():
        hs = have.get(bill, [])
        hkinds = {k for _, k, _ in hs}
        for when, kind, vid in rows:
            # A kind matches loosely: the docket says "public hearing", the
            # site may say "hearing".
            key = kind.split()[-1] if kind else ""
            ok = any(key and key in hk for hk in hkinds)
            yr = when[:4] if when[:4].isdigit() else "(no date)"
            byyear[yr][0 if ok else 1] += 1
            byvideo["a video was matched" if vid else
                    "no video was ever matched"][0 if ok else 1] += 1
            if ok:
                seen += 1
            else:
                miss += 1
                bykind[kind or "(none)"] += 1
                if len(missing_examples) < 4:
                    missing_examples.append((bill, when, kind, hkinds))
    tot = seen + miss
    print(f"\n  IS EVERY SCHEDULED PROCEEDING ON THE SITE  ({tot:,} in the "
          "manifest)")
    print(f"    on the site   {seen:>6,}   {100 * seen / max(1, tot):.0f}%")
    print(f"    absent        {miss:>6,}   {100 * miss / max(1, tot):.0f}%")
    if miss:
        print("    the absent ones, by what the docket called them:")
        for k, v in bykind.most_common(6):
            print(f"      {v:>5,}  {k}")
        print("    for example:")
        for bill, when, kind, hk in missing_examples:
            print(f"      {bill} {kind} on {when} is not there; the site has "
                  + (", ".join(sorted(hk)) if hk else "nothing") + " for it")
        print("\n    by year of the proceeding:")
        for yr, (ok, no) in sorted(byyear.items()):
            tt = ok + no
            print(f"      {yr}   on the site {ok:>5,} of {tt:>5,}"
                  f"   {100 * ok / max(1, tt):>3.0f}%")
        print("\n    by whether a recording was ever found for it:")
        for lab, (ok, no) in sorted(byvideo.items()):
            tt = ok + no
            print(f"      {lab:<26} on the site {ok:>5,} of {tt:>5,}"
                  f"   {100 * ok / max(1, tt):>3.0f}%")
        nv = byvideo.get("no video was ever matched", [0, 0])
        wv = byvideo.get("a video was matched", [0, 0])
        if wv[1] > wv[0]:
            print("\n    Proceedings WITH a recording are missing too, so this "
                  "is not only\n    the video matching being unfinished. The "
                  "docket names these\n    hearings; the site does not list "
                  "them at all, with or without a\n    link. A reader is not "
                  "told the hearing happened.")
        elif nv[1] and not wv[1]:
            print("\n    Every absent one is a proceeding no recording was "
                  "matched to. That\n    is the video matching being "
                  "unfinished, and finishing it fixes\n    this.")
        print("\n    A proceeding that is absent cannot be timed well or "
              "badly. This is\n    a gap in the record before it is a "
              "measurement problem.")


def read_marks(path):
    """[{bill, video, sched, obs, end}] from a .csv or .xlsx manifest."""
    p = Path(path)
    if not p.exists():
        # Only files that could BE a manifest, not scripts that make one.
        near = sorted({x.name for x in list(p.parent.glob("*manifest*"))
                       + list(Path(".").glob("*manifest*"))
                       if x.suffix.lower() in (".csv", ".xlsx", ".xlsm", ".tsv")})
        raise SystemExit(
            f"No {p}.\n"
            + (f"Did you mean one of these?\n  " + "\n  ".join(near)
               if near else "No file with 'manifest' in its name is here.")
            + "\nPass it with --truth.")

    if p.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise SystemExit("openpyxl is needed for .xlsx:\n"
                             "    pip install openpyxl --break-system-packages")
        rows = list(load_workbook(p, read_only=True).active
                    .iter_rows(values_only=True))
    else:
        with p.open(encoding="utf-8-sig", newline="") as fh:
            rows = [tuple(r) for r in csv.reader(fh)]
    if not rows:
        raise SystemExit(f"{p} is empty.")
    h = {str(c).strip(): i for i, c in enumerate(rows[0]) if c}
    # ground_truth.csv names the proceeding in "kind" and carries no
    # predicted_offset, because it is a record of what a person saw and not of
    # what the schedule guessed. The schedule baseline is joined from the
    # manifest below, keyed on what the person watched.
    if "kind" in h and "proceeding" not in h:
        h["proceeding"] = h["kind"]
    if "observed_start" not in h:
        raise SystemExit(
            f"{p} has no observed_start column. It has:\n  "
            + ", ".join(sorted(h)) + "\nThat column is the hand-marked time "
            "this measures against.")
    sec = _sec
    out = []
    for r in rows[1:]:
        if len(r) <= max(h.values()):
            continue
        o = sec(r[h["observed_start"]])
        if o is None:
            continue
        out.append({"bill": r[h["bill"]], "video": r[h.get("video_id", 0)],
                    "committee": r[h.get("committee", 0)],
                    "kind": r[h.get("proceeding", 0)],
                    "sched": sec(r[h["predicted_offset"]]) if "predicted_offset" in h else None,
                    "obs": o,
                    "end": sec(r[h["observed_end"]]) if "observed_end" in h else None,
                    # Which hand-made file this came from. Two sets are read
                    # now and a median that moved because the ruler grew is
                    # not the same event as a median that moved because the
                    # method got worse.
                    "src": p.name})
    if out and all(m["sched"] is None for m in out):
        _join_schedule(out)
    return out


BENCH = Path("review") / "checked.jsonl"


def read_bench(path=BENCH):
    """The bench's timings, in the shape read_marks returns.

    review.py appends one line per judgment and never rewrites one, so this
    is the same kind of thing ground_truth.csv is: a person watched a
    recording and wrote down what they saw. It was not reaching this command,
    which is the only gate a timestamp change has to pass, so the work of
    filling it in could not affect anything.

    THE OBSERVATION IS THE DATUM, NOT THE VERDICT. Until 9 September the
    bench displayed the schedule offset rather than the published time, so
    nine verdicts grade a number no reader was shown. Those verdicts are
    unusable and review.py --report says so. The stopwatch readings beside
    them are unaffected -- a person timing a hearing is not made wrong by
    what the screen said next to the player -- so they are read here and the
    verdict is not read at all.

    A LAST LOOK SUPERSEDES AN EARLIER ONE. The ledger is append-only, so a
    second judgment of the same proceeding is a second line rather than a
    replacement, and the last line is the one that counts.

    Returns (marks, confirmed), where confirmed counts the proceedings a
    person looked at and accepted without timing. Those are real evidence but
    they are NOT marks: "the published time is right" is a weaker claim than
    a stopwatch, and folding it in as an error of zero would flatter every
    method scored here. They are reported on their own line instead.
    """
    p = Path(path)
    if not p.exists():
        return [], 0
    last = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") != "timestamp":
            continue
        shown = e.get("shown") or {}
        key = (shown.get("video_id"), str(shown.get("bill") or "").upper(),
               str(shown.get("proceeding") or "").lower())
        if not key[0]:
            continue
        last[key] = e
    marks, confirmed = [], 0
    for (vid, bill, kind), e in last.items():
        f = e.get("fields") or {}
        shown = e.get("shown") or {}
        obs = _sec(f.get("observed_start"))
        if obs is None:
            # Nothing timed. An accepted time is a confirmation, counted
            # separately; anything else -- wrong with no time, unsure,
            # skipped -- says the published time is doubted and says nothing
            # about where the truth is, so it is not evidence of a number.
            if e.get("verdict") == "correct" and shown.get("start") is not None:
                confirmed += 1
            continue
        marks.append({"bill": bill, "video": vid, "kind": kind,
                      "committee": shown.get("committee") or "",
                      "sched": None, "obs": obs,
                      "end": _sec(f.get("observed_end")),
                      "src": p.name})
    marks.sort(key=lambda m: (m["video"], m["bill"], m["kind"]))
    return marks, confirmed


def _merge_bench(marks, bench):
    """Add the bench's marks to the file's, and say where they disagree.

    ground_truth.csv keeps the proceeding where both have timed it. It is the
    older and more deliberate record, and a generator quietly overruling a
    person's file is the failure this project has had twice. The disagreement
    is printed instead, so whoever owns both files decides.
    """
    have = {(str(m["video"]), str(m["bill"]).strip().upper(),
             str(m["kind"]).strip().lower()) for m in marks}
    added, clash = [], []
    for b in bench:
        k = (str(b["video"]), b["bill"], b["kind"])
        if k in have:
            same = next(m for m in marks
                        if (str(m["video"]), str(m["bill"]).strip().upper(),
                            str(m["kind"]).strip().lower()) == k)
            if abs((same["obs"] or 0) - (b["obs"] or 0)) > 5:
                clash.append((k, same["obs"], b["obs"]))
        else:
            added.append(b)
    return marks + added, added, clash


def _join_schedule(marks):
    """Fill predicted_offset from the manifest, keyed on (video, bill, kind)."""
    if True:
        mp = P.PATH
        by = {}
        for r in P.load():
            k = (r["video_id"], r["bill"], r["kind"])
            by[k] = r["predicted_offset"]
        got = 0
        for m in marks:
            k = (str(m["video"]), str(m["bill"]).strip().upper(),
                 str(m["kind"]).strip().lower())
            if by.get(k) is not None:
                m["sched"] = by[k]
                got += 1
        if got:
            print(f"  schedule baseline for {got} of {len(marks)} joined from "
                  f"{mp.name}")
        return


def _by_source(marks, field):
    """Median error per hand-made file, where more than one is in play."""
    groups = defaultdict(list)
    for m in marks:
        if m.get(field) is None:
            continue
        groups[m.get("src") or "?"].append(abs(m[field] - m["obs"]))
    if len(groups) < 2:
        return
    print("\n    by which hand-made file the mark came from:")
    for src in sorted(groups):
        v = sorted(groups[src])
        near = sum(1 for x in v if x <= 60)
        print(f"      {src:<22} {len(v):>3} placed, median "
              f"{hms(v[len(v) // 2])}, {near}/{len(v)} within a minute")


def hms(s):
    s = int(abs(s))
    return f"{s // 60}m {s % 60:02d}s"


def score(marks, label, get):
    """How far a method's guess is from what a person saw."""
    pairs = [(abs(get(m) - m["obs"]), get(m) - m["obs"], m)
             for m in marks if get(m) is not None]
    if not pairs:
        print(f"  {label}: nothing to compare")
        return
    pairs.sort(key=lambda x: x[0])
    errs = [a for a, _, _ in pairs]
    signed = [s for _, s, _ in pairs]
    print(f"\n  {label}  ({len(pairs)} of {len(marks)} marked proceedings)")
    print(f"    median off by {hms(errs[len(errs) // 2])}, worst {hms(errs[-1])}")
    line = "    "
    for b in (60, 300, 600, 900):
        n = sum(1 for e in errs if e <= b)
        line += f"within {b // 60}min {n}/{len(errs)}   "
    print(line)
    mean = sum(signed) / len(signed)
    early = sum(1 for s in signed if s < -30)
    print(f"    mean {mean:+.0f}s; {early} of {len(signed)} land early"
          + ("  -- a one-sided error, not noise"
             if early > len(signed) * 0.8 else ""))

    # The median says how it does normally; the tail says how it fails. A
    # median of a minute and a half with an outlier of eighty-five minutes is
    # not a model that is slightly off -- it is a model that is right nearly
    # always and occasionally in the wrong place entirely, and those are
    # different problems with different fixes.
    bad = [x for x in pairs if x[0] > 600]
    if bad:
        print(f"\n    {len(bad)} of {len(pairs)} are more than ten minutes "
              "out. Those are not\n    imprecision; something placed them "
              "somewhere else. Worst first:")
        for e, s, m in sorted(bad, key=lambda x: -x[0])[:4]:
            print(f"      {m['bill']:<8} {str(m['kind'])[:17]:<18}"
                  f"{m['video']}  marked {hms(m['obs'])} in, "
                  f"site says {hms(get(m))}")
        print("      Each is one video to open at the marked time. If the bill "
              "is not\n      being taken up there, the recording is wrong, not "
              "the timestamp.")
    # And the ones with no estimate at all, which a median silently omits.
    none = [m for m in marks if get(m) is None]
    if none:
        print(f"\n    {len(none)} marked proceedings have no estimate on the "
              "site at all:")
        for m in none[:4]:
            print(f"      {m['bill']:<8} {str(m['kind'])[:17]:<18}{m['video']}")


_SITE = {}


def site_stations(site):
    """Every proceeding the site publishes, read once per run.

    THE RECORDS ARE IN THE PAGES. Both of the readers below globbed
    site/bills/<year>/<ID>.json, which is where a bill's record lived until it
    moved inside its own page. The glob went on matching -- the 98 records too
    large to inline still live there -- so this reported 519 stations across
    66 bills, and coverage called 96% of the docket absent. Nothing was
    absent. Ten seconds of reading, cached, against a number that was wrong
    by a factor of twenty.
    """
    key = str(site)
    if key not in _SITE:
        _SITE[key] = list(SR.stations(site))
    return _SITE[key]


def census(site):
    """What kinds of proceeding the site actually carries, and from when.

    A measurement that cannot find its subject should say what IS there. The
    marked hearings turned out to be absent entirely -- every station on those
    bills was a floor debate -- and no amount of scoring would have revealed
    that.
    """
    kinds, states, years = Counter(), Counter(), Counter()
    seen = set()
    for _y, bid, s in site_stations(site):
        seen.add(bid)
        kinds[str(s.get("what") or "?")] += 1
        states[str(s.get("state") or "?")] += 1
        years[str(s.get("when") or "")[:4]] += 1
    bills = len(seen)
    total = sum(kinds.values())
    print(f"\n  WHAT THE SITE ACTUALLY CARRIES  ({total:,} stations across "
          f"{bills:,} bills)")
    print("    by kind:")
    for k, v in kinds.most_common(8):
        print(f"      {v:>6,}  {k}")
    print("    by year:")
    for k, v in sorted(years.items()):
        print(f"      {v:>6,}  {k or '(no date)'}")
    print("    by state:")
    for k, v in states.most_common(8):
        print(f"      {v:>6,}  {k}")
    hearings = sum(v for k, v in kinds.items()
                   if "hearing" in k.lower() or "executive" in k.lower())
    if not hearings:
        print("\n    NO committee hearing or executive session is on the site "
              "at all.\n    Only floor debates. That is a missing half of the "
              "record, not a\n    timing problem -- and it is why the marked "
              "proceedings could not be\n    found.")
    elif hearings < total * 0.2:
        print(f"\n    Only {hearings:,} of {total:,} stations are committee "
              "work.\n    The docket schedules far more than that.")


def site_estimates(site, marks):
    """What the site currently claims, for the proceedings that were marked.

    The manifest's predicted_offset is arithmetic -- sched_time minus
    stream_start, identical to the second on all 1,613 rows that have it. So
    scoring it measures the schedule and nothing else. The model's output goes
    into the per-bill files the site serves, and comparing THOSE with the
    marked times is the measurement nobody has run.
    """
    got = 0
    why = Counter()
    seen_vids = set()
    # THE RECORDS ARE IN THE PAGES. This globbed site/bills/<year>/<ID>.json
    # and answered "no file for that bill" for all 43 marks, every run, since
    # the records moved inside the pages -- which made the one measurement
    # that matters, what the SITE claims against what a person saw, silently
    # unavailable while the command still exited zero and printed a report.
    by_bill = defaultdict(list)
    for _y, bid, s in site_stations(site):
        by_bill[bid].append(s)
    for m in marks:
        sts = by_bill.get(str(m["bill"]).strip().upper()) or []
        if not sts:
            why["no page for that bill"] += 1
            continue
        for s in sts:
            if s.get("video_id"):
                seen_vids.add(s["video_id"])
        same = [s for s in sts if s.get("video_id") == m["video"]]
        if not same:
            why["no station on that video"] += 1
            m["_have"] = sts
            continue
        # THE RIGHT PROCEEDING, not merely the right recording. A bill heard
        # in the morning and voted on in the afternoon has two stations on
        # one video, and scoring the hearing against its executive session is
        # a wrong answer wearing the clothes of an imprecise one.
        kind = str(m["kind"]).strip().lower()
        exact = [s for s in same
                 if str(s.get("what") or "").strip().lower() == kind]
        pick = exact or same
        placed = [s for s in pick if s.get("start") is not None]
        if not placed and exact:
            # The kind matches and it is not placed. Falling back to the
            # other proceeding on the same tape would report a number for a
            # thing the site did not place, which is the lie this whole
            # function exists to avoid.
            why[f"station present but not placed "
                f"({exact[0].get('state', 'no state')})"] += 1
            continue
        if not placed:
            why[f"station present but not placed "
                f"({same[0].get('state', 'no state')})"] += 1
            continue
        s = placed[0]
        m["site"] = float(s["start"])
        m["site_end"] = (float(s["end"]) if s.get("end") is not None else None)
        m["site_end_stated"] = bool(s.get("end_stated"))
        m["site_end_from"] = s.get("end_from")
        m["tol"] = s.get("tolerance")
        m["stated"] = bool(s.get("start_stated"))
        m["site_state"] = s.get("state")
        m["site_kind_matched"] = bool(exact)
        got += 1
    if not got:
        # Saying "no match" and stopping leaves the reader to guess between
        # four different problems. Name which one it is.
        print(f"\n  NO STATION MATCHED any of the {len(marks)} marked "
              "proceedings. Why:")
        for k, v in why.most_common():
            print(f"    {v:>3}  {k}")
        want = {m["video"] for m in marks}
        both = want & seen_vids
        print(f"\n    the manifest names {len(want)} videos, the site's "
              f"stations name {len(seen_vids)}")
        print(f"    {len(both)} appear in both"
              + ("   -- so the ids agree and the problem is elsewhere" if both
                 else "   -- the ids do not agree at all"))
        if not both and seen_vids:
            print(f"      manifest: {sorted(want)[:3]}")
            print(f"      site:     {sorted(seen_vids)[:3]}")
        # Which proceedings the site DOES hold for a marked bill. The two
        # disagreeing about the video is a different problem from the site not
        # knowing the bill, and only this tells them apart.
        shown = [m for m in marks if m.get("_have")][:3]
        if shown:
            print("\n    what the site holds for the first few marked bills:")
            for m in shown:
                print(f"      {m['bill']}  marked as {m['kind']} on "
                      f"{m['video']}")
                for s in m["_have"][:4]:
                    st = s.get("start")
                    print(f"        site: {str(s.get('when'))[:10]:<12}"
                          f"{str(s.get('what'))[:18]:<20}"
                          f"{str(s.get('video_id')):<14}"
                          + (f"at {int(st)//60}m" if st is not None
                             else f"({s.get('state')})"))
            print("\n    If the dates match and the video ids do not, the "
                  "manifest and the\n    site matched the same proceeding to "
                  "different recordings, and one\n    of them is wrong. If the "
                  "dates differ, they are different\n    proceedings and the "
                  "marked one is simply absent.")
    return got


def site_ends(marks):
    """The published END against the one a person watched.

    NOTHING HAS EVER SCORED THIS. Every number this project records is about
    where a proceeding STARTS, and the site publishes an end as well -- it is
    what sizes the span a reader is sent to. The end is derived from the last
    time the bill is mentioned on the recording, which fails in one direction
    and only one: a bill named again later in the meeting drags the end past
    where the item actually finished. SB659 publishes a hearing of 4h 31m
    that ran 2h 57m.

    So the SIGN is the finding here, not the size. An error that is symmetric
    is noise to be reduced; an error that is one-sided is a mechanism to be
    fixed, and only reporting the direction tells them apart.
    """
    both = [m for m in marks
            if m.get("site_end") is not None and m.get("end") is not None]
    if not both:
        return
    signed = sorted(m["site_end"] - m["end"] for m in both)
    errs = sorted(abs(x) for x in signed)
    long_ = [x for x in signed if x > 60]
    short = [x for x in signed if x < -60]
    print(f"\n    {len(both)} of them also publish an END, against a person's "
          f"own.\n    Off by {hms(errs[len(errs) // 2])} at the median, worst "
          f"{hms(errs[-1])}.")
    print(f"    {len(long_)} run LONG by more than a minute, {len(short)} "
          f"short.")
    if len(long_) >= 3 * max(1, len(short)):
        print("    That is one-sided. An end taken from the last mention of "
              "the bill\n    cannot stop early and can run on forever, which "
              "is the shape of this.")
    # WHERE THE END CAME FROM, which the site record does not say. Its
    # end_stated is set by bool(said and said.get("end")) -- it means "there
    # is an end", not "the chair closed it" -- so splitting on it puts a
    # boundary the chair spoke and a boundary inferred from the next item in
    # the same bucket. SB659's end is the moment HB1815 was opened, 104
    # minutes after the hearing finished, and the record calls it stated.
    #
    # candidate_segments.json carries the honest field. This reads it rather
    # than trusting the label, and says so when it cannot.
    prov = _end_provenance()
    if prov:
        groups = defaultdict(list)
        for m in both:
            # The record's own end_from first. It is written by the build
            # that decided the end, so it is right even where the candidate
            # file and the site disagree -- which they do wherever the site
            # refused a candidate and fell back to the clustering.
            how = (m.get("site_end_from")
                   or prov.get((m["video"], str(m["bill"]).strip().upper())))
            groups[how or "not recorded"].append(m["site_end"] - m["end"])
        print("      by where the end came from:")
        for how in sorted(groups, key=lambda k: -len(groups[k])):
            signed_ = groups[how]
            v = sorted(abs(x) for x in signed_)
            near = sum(1 for x in v if x <= 60)
            # THE DIRECTION, per source. Overall the ends run short more often
            # than long, and that reads as a contradiction beside a group with
            # a half-hour median unless each source says which way it fails.
            # They fail in opposite directions: an end taken from the last
            # mention stops before the item does, and an end taken from the
            # next boundary cannot stop until the next one is found.
            lo = sum(1 for x in signed_ if x > 60)
            sh = sum(1 for x in signed_ if x < -60)
            # BOTH WAYS IS ITS OWN ANSWER, and the most important one here.
            # A source that is always long can be corrected with an offset. A
            # source that truncates one hearing to 101 seconds and stretches
            # another by 94 minutes cannot be corrected at all, and calling
            # that "runs short" because four beat two would hide the finding.
            way = ("FAILS BOTH WAYS" if min(lo, sh) >= 2
                   else "runs long" if lo > sh
                   else "runs short" if sh else "tight")
            print(f"        {how:<26} {len(v):>3} scored, median "
                  f"{hms(v[len(v) // 2])}, {near}/{len(v)} within a minute"
                  f", {way}")
        if [x for x in groups if "next boundary" in str(x)]:
            for ln in (
                "An end taken from the NEXT boundary inherits every error in",
                "the placement of the item after it. Miss the ones in between",
                "and this one swallows them; match a later mention as an opening",
                "too early and this one is cut off where it had barely started.",
                "Both happen -- one hearing is published as 101 seconds against",
                "the 29 minutes it ran, and another is stretched by 94 -- which",
                "is why no offset can repair it.",
            ):
                print("      " + ln)

    worst = sorted(both, key=lambda m: -(m["site_end"] - m["end"]))[:4]
    over = [m for m in worst if m["site_end"] - m["end"] > 300]
    if over:
        print("\n    the longest overruns -- published span against the one "
              "watched:")
        for m in over:
            print(f"      {m['bill']:<8} {str(m['kind'])[:18]:<19}"
                  f"{m['video']:<14}"
                  f"published {hms(m['site_end'] - m['site'])}, "
                  f"watched {hms(m['end'] - m['obs'])}")


def _end_provenance(path="candidate_segments.json"):
    """{(video, BILL): how the end was decided}, from the segmenter's own file.

    end_from is written by segment_markers.py and is the only place the
    distinction survives: "next boundary", "last mention of the bill", or a
    close the chair actually spoke. It does not reach the site record, which
    is why the site cannot tell a reader either.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        cs = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    out = {}
    for vid, bills in cs.items():
        if not isinstance(bills, dict):
            continue
        for bill, segs in bills.items():
            for s in (segs if isinstance(segs, list) else [segs]):
                if isinstance(s, dict) and s.get("end") is not None:
                    out[(vid, str(bill).strip().upper())] = (
                        s.get("end_from") or "the chair closed it")
                    break
    return out


def load_candidate(path, marks):
    """A candidate method's own output, scored the same way as the site's.

    Any method can be measured against the 35 marks this way, before anything
    it produces goes near a page. That order is the whole point: the tolerances
    now on the site were never checked against anything, and this is what makes
    checking cheap enough that there is no excuse.
    """
    p = Path(path)
    if not p.exists():
        print(f"\n  no candidate at {p}")
        return 0
    doc = json.loads(p.read_text(encoding="utf-8"))
    got = 0
    for m in marks:
        found = (doc.get(str(m["video"])) or {}).get(str(m["bill"]))
        if isinstance(found, dict):
            found = [found]
        if not isinstance(found, list) or not found:
            continue
        # Pick the proceeding of the same KIND. A bill heard in the morning and
        # voted in the afternoon has two, and scoring a hearing against an
        # executive session compares two correct answers to different
        # questions.
        want = str(m.get("kind") or "").lower()
        same = [s for s in found
                if isinstance(s, dict) and s.get("start") is not None
                and (not want or not s.get("what")
                     or s["what"].split()[-1] in want
                     or want.split()[-1] in s["what"])]
        # No substituting one proceeding for another. HB261 was heard AND
        # voted on the same recording; the parser found only the executive
        # session, and falling back to "any segment" handed that timestamp to
        # the public hearing -- 87 minutes wrong, and labelled as confidently
        # as a correct one. Where the right kind is missing, it is missing.
        if want and not same and any(s.get("what") for s in found
                                     if isinstance(s, dict)):
            m["cand_wrongkind"] = True
            continue
        pick = (same or [s for s in found
                         if isinstance(s, dict) and s.get("start") is not None])
        if not pick:
            continue
        best = min(pick, key=lambda s: abs(float(s["start"]) - m["obs"]))
        m["cand"] = float(best["start"])
        m["cand_end"] = best.get("end")
        m["cand_kind"] = best.get("what")
        m["cand_how"] = str(best.get("how") or "")
        got += 1
    return got


def ground_truth(manifest, site=None, candidate=None, bench=True):
    marks = read_marks(manifest)
    n_file, added, clash, confirmed = len(marks), [], [], 0
    if bench:
        bmarks, confirmed = read_bench()
        marks, added, clash = _merge_bench(marks, bmarks)
        if added:
            _join_schedule(added)
    print(f"{'=' * 74}\nGROUND TRUTH: {len(marks)} proceedings a person timed by "
          f"hand\n{'=' * 74}")
    if added or confirmed or clash:
        print(f"  {n_file} from {Path(manifest).name}, {len(added)} from the "
              f"bench ({BENCH})")
        if confirmed:
            print(f"  {confirmed} more were looked at and accepted without "
                  "being timed. Those say\n  the published time is right, "
                  "which is weaker than a stopwatch, so they are\n  counted "
                  "here and nowhere else.")
        for (vid, bill, kind), a, b in clash:
            print(f"  {bill} {kind}: {Path(manifest).name} says {hms(a)} and "
                  f"the bench says {hms(b)}.\n    Keeping the file's. Both are "
                  "a person's; only one can be the mark.")
        print("  --no-bench scores against " + Path(manifest).name
              + " alone, which is what every\n  number recorded before "
                "9 September was measured on.")
    vids = {}
    for m in marks:
        vids.setdefault(m["video"], []).append(m)
    print(f"  {len(vids)} videos, {len({m['committee'] for m in marks})} committees")
    # Can a transcript-based method even be tested against these?
    #
    # The 35 marks are the only measurement of this system a person made. A new
    # method that reads captions can only be scored on recordings whose
    # captions exist. If the marked ones have none, every candidate is
    # unmeasurable no matter how many other recordings get fetched -- and the
    # fetch order should put these first.
    work = Path("work")
    if work.exists():
        readable = {v for v in vids
                    if (work / str(v)).is_dir()
                    and any((work / str(v) / f).exists() for f in WORK_FILES)}
        missing = [v for v in vids if v not in readable]
        print(f"  {len(readable)} of {len(vids)} marked recordings have "
              "captions on disk")
        if missing:
            print("  Without captions, no transcript method can be scored "
                  "against these\n  marks. Fetch these before anything else:")
            for v in missing:
                nb = sum(1 for m in marks if m["video"] == v)
                print(f"    {v}   {nb} marked proceeding(s)")
    durs = sorted(m["end"] - m["obs"] for m in marks if m["end"])
    if durs:
        print(f"  a proceeding runs {hms(durs[len(durs) // 2])} at the median, "
              f"{hms(durs[0])} to {hms(durs[-1])}")

    score(marks, "THE SCHEDULE ALONE  (sched_time minus stream_start)",
          lambda m: m["sched"])

    if candidate:
        got = load_candidate(candidate, marks)
        if got:
            score(marks, f"A CANDIDATE: {Path(candidate).name}",
                  lambda m: m.get("cand"))
            # Split by how the boundary was found. A weak marker -- "Next up",
            # "our first bill is" -- lifts coverage, and whether it does so at
            # the cost of the median is the only thing that decides if the
            # trade is worth taking. Averaging the two together hides exactly
            # that.
            groups = defaultdict(list)
            for m in marks:
                if m.get("cand") is None:
                    continue
                how = m.get("cand_how", "")
                groups["weak marker" if "weak" in how else "stated outright"]\
                    .append(abs(m["cand"] - m["obs"]))
            if len(groups) > 1:
                print("\n    by how the boundary was found:")
                for lab in ("stated outright", "weak marker"):
                    v = sorted(groups.get(lab, []))
                    if not v:
                        continue
                    near = sum(1 for x in v if x <= 60)
                    print(f"      {lab:<17} {len(v):>3} placed, median "
                          f"{hms(v[len(v) // 2])}, {near}/{len(v)} within a "
                          "minute")
                w = sorted(groups.get("weak marker", []))
                s = sorted(groups.get("stated outright", []))
                if w and s and w[len(w) // 2] > max(60, s[len(s) // 2] * 6):
                    print("      The weak markers are markedly worse. They buy "
                          "coverage with\n      accuracy, and that is a trade "
                          "to make deliberately or not at all.")

            # WHICH FILE THE MARKS CAME FROM. The measuring stick grows
            # every time somebody sits down with the bench, and a median that
            # moved because eight harder proceedings joined the set is not
            # the same event as a median that moved because the method got
            # worse. Reported side by side so the two cannot be confused.
            _by_source(marks, "cand")

            ends = [m for m in marks if m.get("cand_end") and m.get("end")]
            if ends:
                e = sorted(abs(m["cand_end"] - m["end"]) for m in ends)
                print(f"\n    {len(ends)} also have a stated END. Those are off "
                      f"by {hms(e[len(e) // 2])} at the median.")
            wrongkind = sum(1 for m in marks if m.get("cand_wrongkind"))
            if wrongkind:
                print(f"\n    {wrongkind} had a boundary for a DIFFERENT "
                      "proceeding of the same bill\n    -- heard in the "
                      "morning and voted in the afternoon, with only one of\n"
                      "    the two found. Not counted: a hearing placed at its "
                      "executive\n    session is wrong, not imprecise.")
            missing = len(marks) - got
            if missing:
                print(f"\n    {missing} of {len(marks)} marked proceedings got "
                      "no boundary from it.\n    A method that places two "
                      "thirds accurately and says nothing about\n    the rest "
                      "is worth more than one that places all of them badly.")
        else:
            print(f"\n  {Path(candidate).name} produced nothing for any marked "
                  "proceeding.")

    if site:
        census(site)
        try:
            coverage(site, manifest)
        except Exception as e:
            print(f"\n  could not compare coverage: {type(e).__name__}: {e}")
        got = site_estimates(site, marks)
        if got:
            score(marks, "WHAT THE SITE CURRENTLY SAYS", lambda m: m.get("site"))
            # The site publishes a tolerance next to every one of these. If the
            # real error is routinely outside it, the tolerance is not a
            # tolerance, it is a decoration.
            inside = [m for m in marks if m.get("site") is not None and m.get("tol")]
            if inside:
                # SECONDS. build_site_v2 sets tolerance in seconds -- 5 for a
                # stated boundary, 180 to 1800 from the aligner -- and says so
                # where it sets it. Multiplying by 60 checked a +/-5 second
                # claim against five minutes and a +/-15 minute claim against
                # fifteen hours, so this passed almost regardless of the data
                # and the warning below could not fire.
                ok = sum(1 for m in inside
                         if abs(m["site"] - m["obs"]) <= m["tol"])
                print(f"\n    the site states a tolerance for {len(inside)} of "
                      f"these.\n    The true error is inside it {ok} times "
                      f"({100 * ok / len(inside):.0f}%).")
                if ok < len(inside) * 0.8:
                    print("    A tolerance that is wrong more than one time in "
                          "five is not\n    a tolerance. That number belongs on "
                          "the site or the claim does not.")
            stated = [m for m in marks if m.get("stated") and m.get("site")]
            if stated:
                e = sorted(abs(m["site"] - m["obs"]) for m in stated)
                print(f"\n    {len(stated)} of them say the boundary was STATED "
                      f"by the chair.\n    Those are off by "
                      f"{hms(e[len(e) // 2])} at the median -- the first "
                      "accuracy\n    number the marker path has ever had.")
            site_ends(marks)

    # The shape of the error matters more than its size. If a day drifts
    # steadily later, one anchor fixes the rest of it; if it jumps about,
    # nothing does.
    print(f"\n  DOES THE ERROR GROW THROUGH A DAY")
    grew = 0
    for vid, ms in vids.items():
        ms.sort(key=lambda x: x["obs"])
        e = [m["sched"] - m["obs"] for m in ms if m["sched"] is not None]
        if len(e) < 3:
            continue
        falling = sum(1 for i in range(len(e) - 1) if e[i + 1] <= e[i] + 1)
        if falling >= len(e) - 2:
            grew += 1
        print(f"    {vid}  " + " -> ".join(hms(x) for x in e[:7]))
    print(f"    {grew} of {sum(1 for v in vids.values() if len(v) >= 3)} videos "
          "drift steadily in one direction.")
    print("    Where they do, one known boundary places the rest of the day.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", nargs="+",
                    help="one or more work folders or files. Several at once, "
                         "so a pattern can be seen across chambers and "
                         "settings rather than read off a single day.")
    ap.add_argument("--expect", help="comma-separated bills the docket "
                                     "scheduled; usually unnecessary")
    ap.add_argument("--context", action="store_true",
                    help="print the words around every mention, so what a "
                         "mention IS can be read rather than guessed")
    ap.add_argument("--video", help="the recording this transcript is, so the "
                                    "bill list comes from the manifest")
    ap.add_argument("--work", default="work")
    ap.add_argument("--manifest", default="verification_manifest.csv")
    ap.add_argument("--data", default="data")
    ap.add_argument("--missing", metavar="FILE", nargs="?", const="missing_captions.txt",
                    help="write the video ids that have no captions yet, "
                         "busiest first, one per line, for a fetcher to read")
    ap.add_argument("--suggest", action="store_true",
                    help="list the recordings that have captions on disk, "
                         "grouped by chamber and setting, with the command to "
                         "sample one of each")
    ap.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"),
                    help="two manifests, side by side: what the second lost")
    ap.add_argument("--candidate", help="a method's own segments, scored "
                                        "against the hand-marked times")
    ap.add_argument("--site", help="score what the site currently publishes "
                                   "against the marked times")
    ap.add_argument("--truth", nargs="?", const="ground_truth.csv",
                    help="score every method against the hand-marked times. "
                         "Reads ground_truth.csv AND review/checked.jsonl by "
                         "default, or a manifest with observed_start filled "
                         "in.")
    ap.add_argument("--no-bench", action="store_true",
                    help="score against the truth file alone, leaving out "
                         "review/checked.jsonl. Use it to compare with a "
                         "number recorded before the bench was read here.")
    a = ap.parse_args()

    if a.missing:
        floor, fe = read_floor()
        # Not the whole-video ones: the title names the bill, there is nothing
        # to segment, and fetch_captions skips them for the same reason.
        floor = {v: b for v, b in floor.items() if v not in fe.get("_whole", ())}
        have = {d.name for d in Path(a.work).iterdir()
                if d.is_dir() and any((d / f).exists() for f in WORK_FILES)}
        counts = Counter()
        for v, bills in floor.items():
            counts[v] = len(bills)
        for r in _manifest_rows():
            v = str(r.get("video_id") or "").strip()
            if v:
                counts[v] += 1
        want = [(c, v) for v, c in counts.items() if v not in have]
        want.sort(reverse=True)
        Path(a.missing).write_text("\n".join(v for _, v in want) + "\n",
                                   encoding="utf-8")
        floor_n = sum(1 for _, v in want if v in floor)
        print(f"{len(want):,} recordings have no captions -> {a.missing}")
        print(f"  {floor_n:,} of them are floor sessions, and they carry the "
              "most bills each")
        print("  busiest first, so a run that is stopped early still gets the "
              "most:")
        for c, v in want[:6]:
            print(f"    {v}  {c:>4} bill appearances"
                  + ("   floor" if v in floor else ""))
        return

    if a.suggest:
        suggest(a.work, a.manifest)
        return

    if a.compare:
        compare_manifests(*a.compare)
        return

    # Coverage needs no hand-marked times, so it can be run against whatever
    # manifest the build actually reads -- which is the comparison that says
    # whether a proceeding was lost between the matching and the site.
    if a.site and not a.truth:
        census(a.site)
        coverage(a.site, a.manifest)
        print("\n  Run this against the manifest build_manifest.py writes, and "
              "again\n  against verification_manifest. If one has the "
              "proceedings and the\n  other does not, the matching was not "
              "lost -- it was not carried\n  forward.")
        return

    if a.truth:
        ground_truth(a.truth, a.site, a.candidate,
                     bench=not a.no_bench)
        return

    rp = Path("committee_reports.json")
    reports = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}
    if reports:
        print(f"{len(reports):,} bills with committee reports loaded")
    bills = json.loads((Path(a.data) / "bills.json").read_text(encoding="utf-8"))
    if P.term_keyed(bills):
        # Every term, since a title is a title whichever term it is from and
        # this only builds a lookup for display.
        bills = [r for byb in bills.values() for r in byb.values()]
    elif isinstance(bills, dict):
        bills = list(bills.values())
    titles = {b.get("id") or b.get("bill"): b.get("title", "") for b in bills}

    def bills_for(video_id):
        """Which bills the docket scheduled on that recording.

        A bill can appear twice on one recording: heard in the morning, voted
        in the afternoon's executive session. Those are two proceedings, and
        treating them as one bill is why several bills showed "2 runs" and got
        read as an agenda readout followed by the real thing. The kinds are
        reported so that is visible.
        """
        out, kinds, when = [], Counter(), {}
        for r in _manifest_rows():
            if str(r.get("video_id") or "").strip() == video_id:
                b = str(r.get("bill") or "").strip().upper()
                if not b:
                    continue
                kinds[(b, str(r.get("proceeding") or "").strip().lower())] += 1
                when.setdefault(b, str(r.get("sched_time") or "").strip())
                if b not in out:
                    out.append(b)
        sched_times.update(when)
        twice = sorted({b for b, _ in kinds} & {b for b, k in kinds}
                       & {b for b in out if sum(1 for x, _ in kinds if x == b) > 1})
        if twice:
            print(f"  {len(twice)} of them are scheduled TWICE on this "
                  "recording, so two\n  runs of mentions is what a bill heard "
                  "and then voted on looks like:")
            for b in twice[:6]:
                ks = [k for x, k in kinds if x == b]
                print(f"    {b}: {', '.join(ks)}")
        return out

    jobs = []
    known = {str(r.get("video_id") or "").strip() for r in _manifest_rows()}
    known.discard("")
    sched_times = {}
    _floor_bills, _fe = read_floor()
    for tpath in (a.transcript or []):
        want = [x.strip().upper() for x in (a.expect or "").split(",") if x.strip()]
        if not want:
            # A transcript is usually work/<videoid>/... or named for its
            # video, so the id is generally already in the path. Split on path
            # separators only: a YouTube id is letters, digits, hyphen and
            # underscore, so splitting on hyphen and underscore takes
            # "_YNaTMx17_k" apart into pieces that match nothing.
            vid = a.video
            if not vid:
                whole = str(tpath).replace("\\", "/")
                allids = known | set(_floor_bills)
                vid = next((x for x in whole.split("/") if x in allids), None)
                if not vid:
                    vid = next((k for k in sorted(allids, key=len, reverse=True)
                                if k in whole), None)
            if vid and vid not in known:
                fl = _floor_bills.get(vid)
                if fl:
                    want = fl
                    print(f"{len(want)} bills on {vid}, a floor session")
                    jobs.append((tpath, want))
                    continue
            if vid:
                want = bills_for(vid)
                print(f"{len(want)} bills scheduled on {vid}, from the manifest")
            else:
                # One unreadable path should not stop the other four.
                print(f"  skipping {tpath}: cannot tell which recording it is."
                      "\n  Pass --video, or name the folder after its video id.")
                continue
        jobs.append((tpath, want))
    if not a.transcript:
        mp = Path(a.manifest)
        if not mp.exists():
            raise SystemExit(f"No {mp} and no --transcript. Give one or the other.")
        byfile = defaultdict(list)
        for row in csv.DictReader(mp.open(encoding="utf-8")):
            f = (row.get("transcript") or row.get("transcript_file") or "").strip()
            b = (row.get("bill") or "").strip().upper()
            if f and b:
                byfile[f].append(b)
        for f, bs in sorted(byfile.items()):
            p = Path(f) if Path(f).exists() else Path(a.work) / f
            if p.exists():
                jobs.append((str(p), bs))
        if not jobs:
            raise SystemExit(f"The manifest named no transcript that exists "
                             f"under {a.work}/.")

    totals, skipped = [], []
    for path, expect in jobs:
        try:
            lines = as_lines(read_transcript(path))
        except NoTranscript as e:
            skipped.append((path, str(e)))
            continue
        if not lines:
            print(f"\n{path}: no caption lines matched the expected format.")
            continue
        if not expect:
            print(f"\n{path}: no bill list. Pass --expect, or add rows to the "
                  "manifest.")
            continue
        vid_here = Path(path).name
        fe = {b: _fe[(vid_here, b)] for b in expect if (vid_here, b) in _fe}
        totals.append(report(vid_here, lines, expect, titles,
                             context=a.context, reports=reports,
                             sched=sched_times, floor_entries=fe,
                             is_floor=vid_here in _floor_bills))

    if skipped:
        print(f"\n{'=' * 74}\n{len(skipped)} of {len(jobs)} could not be read"
              f"\n{'=' * 74}")
        for path, why in skipped:
            print(f"  {path}: {why}")
        if not totals:
            print("\n  Nothing was read. Fetch captions for these recordings "
                  "first --\n  transcribe_and_align.py is what puts them under "
                  "work/<video id>/.")

    if len(totals) > 1:
        e = sum(t["expect"] for t in totals)
        print(f"\n{'=' * 74}\nACROSS {len(totals)} TRANSCRIPTS\n{'=' * 74}")
        print(f"  {e} bills")
        print(f"  found by number  {sum(t['num'] for t in totals):>4}"
              f"  ({100*sum(t['num'] for t in totals)/e:.0f}%)")
        print(f"  found by title   {sum(t['title'] for t in totals):>4}"
              f"  ({100*sum(t['title'] for t in totals)/e:.0f}%)")
        # The number that matters. Neither signal wins across settings -- one
        # chair reads numbers clearly, another reads titles -- but a bill found
        # by either is found, and the two miss different bills.
        ei = sum(t.get("either", 0) for t in totals)
        bo = sum(t.get("both", 0) for t in totals)
        print(f"  found by EITHER  {ei:>4}  ({100*ei/e:.0f}%)"
              f"   -- {bo} by both, {ei-bo} by only one of them")
        inv = sum(t["inversions"] for t in totals)
        pr = sum(t["pairs"] for t in totals)
        print(f"  order inversions {inv} of {pr} pairs"
              + ("   agenda order holds" if inv < pr * 0.05 else ""))

    print("\nNothing was written and nothing was decided. If titles find bills\n"
          "that numbers miss, that is the signal to build on. If the order "
          "holds,\nboundaries can be solved together rather than one bill at a "
          "time.")


if __name__ == "__main__":
    main()
