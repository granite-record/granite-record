#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.32
"""
Segment a recording on what the chair says, not on where bill numbers cluster.

    python3 segment_markers.py --transcript work/RE4RWUbmVz4
    python3 segment_markers.py --all --out candidate_segments.json

Then score it against the only ground truth there is:

    python3 probe_alignment.py --truth \\
        --candidate candidate_segments.json

WHERE THE PATTERNS COME FROM

Every phrasing below was read out of a real transcript. Seven recordings, four
settings, both chambers. Nothing here was imagined, and nothing was
generalised from a single example -- that mistake has been made twice on this
project and both times it half-worked, which is worse than failing.

  House executive session, one chair, thirty-nine times:
    "And with that, the chair will close the executive session on House Bill
     1386. At this time, the chair will open the executive session on House
     Bill 1181..."

  House executive session, a different chair, looser:
    "we'll open up the um executive session. First bill I have here is HP 1080"
    "Next up, HP 1558 requiring..."

  House hearings, three chairs:
    "I am opening the hearing on House Bill 1491"
    "I'll open the hearing on House Bill 1498"
    "I'm going to open up the hearing on uh House Bill 1789"
    "It is 1:45 and I'm going to open up the public hearing for House Bill 1097"
    "having no other pink cards, I will close the public hearing on HB..."

  Senate hearings, from TRANSCRIPT_MARKERS.md:
    "Senate Judiciary is now hearing House Bill 1637"
    "We're going to go on to House Bill 1416"
    "Does anyone else wish to testify on 1419? Seeing no one, that'll end the
     hearing"

WHAT IT REFUSES TO DO

A marker is only accepted when it names a bill the docket says was scheduled on
that recording. The captions render "HB 1381" as "HP 1381", "HB1 1444", "HB6006"
and "House Bill 11:35" -- so a number read in isolation is unreliable, and a
number checked against a list of twenty candidates is not. Where the number is
unreadable the title is used instead: across seven recordings, number and title
each found 83% and together they found 94%.

Where no marker is found, this says so and stops. It does not fall back to
guessing, because a guess wearing the same label as a quotation is how the
current site came to publish tolerances nobody had checked.
"""

import argparse
import proceedings as P
import bisect
import hashlib
import io
import json
import re
import sys
import time
import tokenize
from collections import Counter, defaultdict
from pathlib import Path

WORK_FILES = ["captions.en.json3", "captions.en-orig.json3", "transcript.json"]
WS = re.compile(r"\s+")
NONWORD = re.compile(r"[^a-z0-9 ]+")

# The thing being opened or closed. "hearing" alone is common; so is
# "executive session"; "public hearing" is the formal version of the first.
# "session" on its own is last, so the longer names still win the alternation.
# It is here because one chair says "we're opening the session on House Bill
# 1123" and nothing else in this list is the word they used -- the whole
# recording came back with no boundary for want of it.
SUBJECT = (r"(?P<what>public\s+hearing|executive\s+session|exec\s+session|"
           r"exact\s+session|hearing|work\s+session|testimony|session)")
SUBJECT_BARE = r"(?:public\s+hearing|executive\s+session|hearing|work\s+session)"
# "we'll open up the um executive session" -- the filler sits between the
# article and the noun, and a pattern with no room for it misses the marker
# entirely. These are people speaking, not reading.
FILLER = r"(?:(?:um|uh|er|ah|okay|alright|all\s+right)[\s,]+)*"
# "the house election Law Public hearing for House Bill 474" -- the committee's
# own name sits between the article and the noun. Up to four words, so a
# sentence that merely contains "hearing" much later does not qualify.
QUAL = r"(?:[A-Za-z]+\s+){0,4}"
ART = r"(?:the\s+|a\s+|an\s+)?"

# "open", in every form seen. The chair may be the subject ("the chair will
# open"), or the speaker ("I'm going to open up"), or the room ("we are going
# to open").
# Every verb seen introducing a proceeding, across sixty recordings. "turn
# to", "start", "take testimony on", "do the work session on" and "the next
# hearing is on" were all missed by the first version, and each of them opens
# a real proceeding in a real transcript.
OPEN_RE = re.compile(
    r"(?:will\s+open|going\s+to\s+open|opening|i'?ll\s+open|we'?ll\s+open|"
    r"open\s+up|now\s+open|like\s+to\s+open|open\b|"
    r"will\s+start|going\s+to\s+start|start(?:ing)?\b|"
    r"turn\s+to|going\s+to\s+do|take\s+testimony\s+on|"
    r"next\s+" + SUBJECT_BARE + r"\s+is(?:\s+on)?)"
    r"\s*(?:up\s+)?" + ART + FILLER + QUAL + SUBJECT +
    r"(?:\s+(?:for|on|of))?", re.I)

CLOSE_RE = re.compile(
    r"(?:will\s+close|going\s+to\s+close|closing|i'?ll\s+close|we'?ll\s+close|"
    r"close\s+out|close\s+up|close\s+down|that'?ll\s+end|end\s+the)\s+(?:up\s+|down\s+)?"
    r"(?:the\s+|a\s+|this\s+)?" + FILLER + SUBJECT + r"(?:\s+(?:for|on|of))?", re.I)

# Looser openings that name no proceeding. Real, and weaker: "Next up" also
# introduces a speaker, a document, or a recess.
# Openings whose verb takes the BILL directly, with no proceeding noun after
# it: "turn to HP 253", "the next hearing is on House Bill 269", "take
# testimony on HB 138". The first version required a noun after the verb and
# so could not match any of these, which is a shape rather than a vocabulary
# problem -- and three real openings fell through it.
# Read on recordings that came back with nothing at all. Each of these opens a
# real proceeding and none of them names one, so OPEN_RE -- which demands the
# noun -- could not reach any of them:
#
#   "I'll open HP 369. Representative Patenza, good to see you"
#   "we're going to start HB 602 requiring certain offenders to participate"
#   "Senator Eler is going to introduce SB 269"
#   "The next bill up on the docket is 1586 allowing the commissioner"
#   "first up we have Senate I'm sorry, House Bill 206 and 204"
#   "So we'll move now to HB 1398, establishing a committee to study"
#
# The bill still has to be named right after, and the agenda-readout guard
# still applies, so these cannot fire on a chair listing the day's business.
OPEN_DIRECT_RE = re.compile(
    r"(?:going\s+to\s+turn\s+to|now\s+turn\s+to|turn(?:ing)?\s+to|"
    r"take\s+testimony\s+on|taking\s+testimony\s+on|"
    r"(?:i'?ll\s+|we'?ll\s+|will\s+|going\s+to\s+|now\s+)?open(?:\s+up)?|"
    r"going\s+to\s+start|we'?re\s+going\s+to\s+start|"
    r"introduc(?:e|ing)|"
    r"next\s+bill\s+up(?:\s+on\s+the\s+docket)?\s+is|"
    r"first\s+up\s+we\s+have|"
    r"mov(?:e|ing)\s+now\s+(?:to|on\s+to)|"
    # A second --gaps pass, once the batch above was in.
    r"we'?re\s+doing|"
    r"begin(?:ning)?|"
    r"start\s+a\s+discussion\s+(?:about|on)|"
    r"we'?re\s+on\s+to|"
    r"get\s+(?:it\s+)?right\s+into|"
    r"next\s+(?P<what2>public\s+hearing|executive\s+session|hearing|"
    r"work\s+session)\s+is(?:\s+on)?)", re.I)

# Transitions the chairs actually use, counted across every unmarked
# proceeding rather than chosen by eye. Each appeared 15 times or more:
# "move on to" 37, "going to start" 25, "the next one" 24, "going to hear" 20,
# "last but not least" 19, "take up" 17. They name a bill rather than a
# proceeding, so they count as weak -- but they are the commonest way a bill
# gets introduced and not one of them was known.
NEXT2_RE = re.compile(
    r"(?:mov(?:e|ing)\s+(?:on\s+)?(?:to|into|right\s+along)|"
    r"next\s+one\s+is|take\s+up\b|hear\s+from\s+the\s+prime|"
    r"going\s+to\s+hear\b|start\s+(?:off\s+)?with|get\s+started\s+with|"
    r"last\s+but\s+not\s+least|"
    r"to\s+be\s+heard\s+(?:today|this\s+morning|this\s+afternoon)|"
    r"here\s+to\s+introduce)", re.I)

# ---------------------------------------------------------------- floor --
#
# The floor is the one setting with a script. The clerk reads a committee
# report to open every bill, in a form that varies less than any committee
# chair's:
#
#   "Majority of the Committee on Finance to which was referred Senate Bill
#    408, relative to insurance coverage for prosthetics, having considered
#    the same, report the same with the following amendment..."
#
# All three of these occur in one session, so "of the" is optional, "to" is
# optional, and a comma may sit before "which". These patterns are taken
# unchanged from floor_markers.py, which was written against a real transcript
# and found the opening for 23 of 23 House bills and 36 of 36 Senate bills.
FLOOR_OPEN_RE = re.compile(
    r"(?:majority|minority)?\s*(?:of\s+the\s+)?committee\s+on\s+"
    r"(?P<cmte>[\w ,\-]{4,70}?)\s*,?\s*"
    r"(?:to\s+)?which\s+(?:was|is|has\s+been|has|had)?\s*"
    r"(?:referr?ed|referr?al)", re.I)

# TRIED AND REJECTED: the chair putting the question.
#
# The floor script has a second fixed form besides the clerk's reading above,
# and it is the one that names the bill outright:
#
#   "Motion before us is majority committee report of ought to pass on
#    house bill 198."
#   "Question is on the majority committee report of ought to pass as amended
#    on Senate Bill 586."
#
# 346 of these across 20 of the 41 floor recordings with captions on disk, 95%
# followed immediately by a bill number. By the standard this file uses -- a
# convention shows up as a number rather than a hunch -- it qualifies, and it
# was added as an opening.
#
# It is not an opening. Measured against the clerk's reading of the same bill,
# it comes a median of 512 seconds AFTER it (2 of 230 before). It is the
# moment the vote is called, near the END of the debate.
#
# It is not usable as a close either. Against the 90 bills that already have a
# close the chair stated, it is off by a median of 204 seconds and lands
# within 30 seconds exactly once. The stated ends on this site score 4 seconds
# against the hand-marked record; adopting this would have replaced a
# four-second claim with a three-and-a-half-minute one on the 71 bills it
# would otherwise have "gained".
#
# As an opening it also destroyed data. A second open marker for a bill 20
# minutes after the first took the close away from the first, and 9 floor
# appearances dropped from a stated span to a date alone -- which is how this
# was caught, since the hand-marked record is all committee proceedings and
# scored 0m 01s either way.
#
# The phrase is real and worth knowing about. It is not a boundary.

# The outcome, which closes the item. The House says "the committee report is
# adopted"; the Senate says "the motion of ought to pass is adopted". A voice
# vote falls back on "the ayes have it", which the captions render "the eyes
# have it" every single time.
FLOOR_CLOSE_RE = re.compile(
    r"\b(?:the\s+)?(?:committee\s+report|motion(?:\s+of\s+\w[\w\s]{0,24})?|"
    r"amendment|reports?)s?\s*(?:'s|\s+is|\s+are|\s+was)?\s*"
    r"(?:adopted|fails?|passed|defeated|carries)\b"
    r"|\b(?:the\s+)?(?:eyes|ayes|I's)\s+have\s+it\b", re.I)

# Weaker: these introduce an item without naming a proceeding, so they also
# introduce speakers, documents and recesses. Used only where nothing stronger
# fired, and labelled as weak in the output.
NEXT_RE = re.compile(
    r"(?:next\s+up|next\s+bill\s+is|first\s+bill\s+i\s+have|"
    r"(?:our|the)\s+first\s+bill\s+is|first\s+one\s+we'?ll\s+take\s+up\s+is|"
    r"now\s+hearing|going\s+to\s+go\s+on\s+to|moving\s+on\s+to|"
    r"we\s+have\s+(?:uh\s+)?scheduled|ready\s+for\s+our\s+next\s+bill|"
    r"sponsors?\s+to\s+(?:um\s+)?introduce)", re.I)

BILL_SPOKEN = re.compile(
    r"\b(?:(House|Senate)\s*Bill|(HB|HP|SB|SP|CACR|CAC|HR|SR|HCR|SCR|HJR))\s*#?\s*"
    r"(\d[\d\s:]{0,6}\d|\d)", re.I)
BARE_NUM = re.compile(r"\b(\d{2,4})\b")
LETTER_FIX = {"HP": "HB", "SP": "SB", "CAC": "CACR"}

STOP = set("""a an the of to in on for and or by with at from as is are be been
being this that these those it its relative certain establishing regarding
concerning act shall may not no any all other such under over into upon""".split())


def norm(s):
    return WS.sub(" ", NONWORD.sub(" ", (s or "").lower())).strip()


def pattern_signature():
    """A fingerprint of everything in this file that can change an answer.

    The cache must expire when the method changes and not otherwise. This
    used to hash the patterns and the stop list, on the stated assumption
    that "nothing else in this file affects the result". That was false, and
    it is the second time this file has had a cache that keys on the wrong
    thing. Change the dedupe rule, the window size, the bill-matching
    threshold or any branch of find_markers, and every recording kept the
    answer the old code gave -- served back looking fresh, and, worse,
    scored as though it were the new method's work.

    So: the whole module, with comments and blank lines stripped out by the
    tokeniser. Anything that can alter behaviour alters this; a comment, a
    docstring rewrite or a reflow does not, which matters in a file that is
    documented as heavily as this one and would otherwise re-read 10 GB of
    captions every time a sentence was clarified.

    Crude and correct, in ARCHITECTURE's words. If the source cannot be read
    -- frozen, zipped -- it falls back to the patterns, which is the old
    behaviour and better than no key at all.
    """
    try:
        src = Path(__file__).resolve().read_text(encoding="utf-8")
        parts = []
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.NL):
                continue
            parts.append(tok.string)
        blob = "".join(parts)
    except (OSError, ValueError, tokenize.TokenError, SyntaxError):
        pats = [OPEN_RE, CLOSE_RE, OPEN_DIRECT_RE, NEXT_RE, NEXT2_RE,
                FLOOR_OPEN_RE, FLOOR_CLOSE_RE, BILL_SPOKEN, BARE_NUM]
        blob = "|".join(r.pattern for r in pats) + "|".join(sorted(STOP))
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def cache_key(folder, candidates, sig):
    """What can make a recording's answer stale: its captions, its bill list,
    and this module's own code -- see pattern_signature, which is where the
    claim that nothing else mattered used to live."""
    p = Path(folder)
    for name in WORK_FILES:
        f = p / name
        if f.exists():
            st = f.stat()
            return f"{sig}|{','.join(sorted(candidates))}|{name}:{st.st_size}:{int(st.st_mtime)}"
    return f"{sig}|{','.join(sorted(candidates))}|none"


def read_words(folder):
    """[(seconds, word)] with per-word timing where the captions carry it."""
    p = Path(folder)
    for name in WORK_FILES:
        f = p / name
        if not f.exists():
            continue
        doc = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        if isinstance(doc, dict) and isinstance(doc.get("events"), list):
            out = []
            for ev in doc["events"]:
                base = ev.get("tStartMs")
                if base is None:
                    continue
                for s in ev.get("segs") or []:
                    w = (s.get("utf8") or "").strip()
                    if w and w != "\n":
                        out.append(((base + (s.get("tOffsetMs") or 0)) / 1000.0, w))
            if out:
                return out
        # Whisper's own output, which transcribe_and_align.py writes as a LIST
        # of {"start","end","text"} rather than YouTube's {"events": [...]}.
        # The parser above skipped it silently, so every whisper-transcribed
        # recording read as zero words and was counted under "no captions" --
        # the exact case the note further down warns about, where silence and
        # failure look the same. Eight folders were already dark this way, and
        # the recordings YouTube has no captions for can ONLY come this way.
        #
        # The timing is per LINE, not per word: whisper gives one start for a
        # whole sentence. So a marker found here is accurate to the line it sits
        # in, not to the word, and callers are told by the second return value.
        if isinstance(doc, list) and doc and isinstance(doc[0], dict) \
                and "text" in doc[0]:
            out = []
            for seg in doc:
                t = seg.get("start")
                if t is None:
                    continue
                # Every word of the line carries the line's start. That is the
                # honest resolution: pretending to know where inside a sentence
                # a word fell would be inventing precision.
                for w in str(seg.get("text") or "").split():
                    out.append((float(t), w))
            if out:
                return out
    return []


def match_bill(text, candidates, titles):
    """Which scheduled bill this stretch of words names, if any.

    Checked against the day's list rather than read in isolation: the captions
    write HB 1381 as HP 1381 and House Bill 1135 as "House Bill 11:35", and a
    garbled number only has to pick one out of twenty.
    """
    bydigits = defaultdict(list)
    for c in candidates:
        bydigits[re.sub(r"[^0-9]", "", c)].append(c)

    for m in BILL_SPOKEN.finditer(text):
        kind = (m.group(2) or ("HB" if (m.group(1) or "").lower().startswith("h")
                               else "SB")).upper()
        kind = LETTER_FIX.get(kind, kind)
        digits = re.sub(r"[^0-9]", "", m.group(3))
        same = bydigits.get(digits, [])
        pick = next((c for c in same if c.startswith(kind)), None) \
            or (same[0] if same else None)
        if pick:
            return pick, "number"
    for m in BARE_NUM.finditer(text):
        same = bydigits.get(m.group(1), [])
        if len(same) == 1:
            return same[0], "bare number"

    # Title words, which the captions handle far better than digits.
    words = set(norm(text).split())
    best, score = None, 0.0
    for b in candidates:
        kw = {w for w in norm(titles.get(b, "")).split()
              if w not in STOP and len(w) > 3}
        if len(kw) < 3:
            continue
        hit = len(kw & words) / len(kw)
        if hit > score:
            best, score = b, hit
    if best and score >= 0.6:
        return best, "title"
    return None, ""


def find_markers(words, candidates, titles, span=28, floor=False):
    """Every stated opening and closing, with the bill it names.

    One pass over one string, not a window per word.

    The first version rebuilt a fifty-word window at every word position and
    ran four patterns over each -- 160,000 regex searches on a single
    recording, 57 million across the set, and several minutes a run. Joining
    the words once and searching that gives the same matches: a pattern that
    would have matched inside some window still matches in the whole text, and
    the character offset maps straight back to the word that was spoken.
    """
    if not words:
        return []
    parts, starts, pos = [], [], 0
    for t, w in words:
        starts.append((pos, t))
        parts.append(w)
        pos += len(w) + 1
    text = " ".join(parts)
    char_at = [c for c, _ in starts]
    time_at_ = [tt for _, tt in starts]

    def when(char):
        k = bisect.bisect_right(char_at, char) - 1
        return time_at_[max(0, k)]

    out, seen = [], set()
    pats = ([(FLOOR_OPEN_RE, "open", False),
             (FLOOR_CLOSE_RE, "close", False)] if floor else [])
    for rx, kind, weak in pats + [(OPEN_RE, "open", False),
                           (CLOSE_RE, "close", False),
                           (OPEN_DIRECT_RE, "open", False),
                           (NEXT_RE, "open", True),
                           (NEXT2_RE, "open", True)]:
        for m in rx.finditer(text):
            # The words after the phrase only: "close the hearing on X. Open
            # the hearing on Y" names two bills and the second belongs to the
            # opening.
            after = text[m.end():m.end() + 220]
            bill, how = match_bill(after, candidates, titles)
            if not bill:
                continue
            # An agenda being read is not an opening. "these are in numerical
            # order house bill 27 289 323 365 385 418" names six bills in one
            # breath; a phrase followed by a list of them is a chair running
            # through the day, not starting an item.
            named = {c for c in candidates
                     if re.search(r"\b" + re.sub(r"[^0-9]", "", c) + r"\b",
                                  after[:120])}
            if len(named) >= 3:
                continue
            t = when(m.start())
            # Within a minute of one already found for the same bill and the
            # same kind is the same moment. Bucketing by round(t/30) let
            # 1:11:44 and 1:11:48 fall either side of a boundary and both be
            # kept -- the clerk reading the majority report and then the
            # minority is one debate, not two.
            if any(o["bill"] == bill and o["kind"] == kind
                   and abs(o["t"] - t) < 60 for o in out):
                continue
            key = (kind, bill, round(t / 30))
            if key in seen:
                continue
            if weak and any(o["bill"] == bill and o["kind"] == kind
                            for o in out):
                continue          # something stronger already placed it
            seen.add(key)
            what = "floor debate" if rx in (FLOOR_OPEN_RE, FLOOR_CLOSE_RE) else ""
            for g in ("what", "what2"):
                if g in (rx.groupindex or {}) and m.group(g):
                    what = WS.sub(" ", m.group(g)).lower()
                    break
            out.append({"t": round(t, 1), "kind": kind, "bill": bill,
                        "what": "" if weak else what,
                        "how": how + (" (weak marker)" if weak else ""),
                        "said": WS.sub(" ", text[m.start():m.start() + 130])})
    out.sort(key=lambda x: x["t"])
    return out


def never_named(words, candidates, titles, found, step=12):
    """Bills the recording never mentions at all.

    A floor calendar lists every bill before the chamber that day, and most
    pass on the consent calendar as a block: never read out, never debated,
    never voted on separately. Counting those as boundaries this failed to find
    made coverage read 18% on a recording where the clerk's script matched
    every time it was actually spoken.

    They are not a gap. They are bills that did not happen on this recording,
    and a link offering to play nine hours of floor session for one is an
    invitation to listen for something that is not there.
    """
    if not words:
        return []
    out = []
    for b in candidates:
        if b in found:
            continue
        seen = False
        for i in range(0, len(words), step):
            tt = words[i][0]
            j = i
            while j < len(words) and words[j][0] - tt <= 20:
                j += 1
            if j - i < 4:
                continue
            got, _ = match_bill(" ".join(w for _, w in words[i:j]), [b], titles)
            if got == b:
                seen = True
                break
        if not seen:
            out.append(b)
    return out


def last_mentions(words, candidates):
    """{bill: the last second at which it was spoken of}.

    Used to cap an inferred end. Same digits-only comparison the bill matcher
    uses, so "hb1 127" and "H B 513" still count as the bill being named.
    """
    pats = {b: re.compile(r"(?<!\d)" + r"[\s,]*".join(
        list(re.sub(r"[^0-9]", "", b))) + r"(?!\d)")
        for b in candidates if re.sub(r"[^0-9]", "", b)}
    out = {}
    text_at = []
    for t, w in words:
        text_at.append((t, w))
    joined = " ".join(w for _, w in text_at)
    # Cheap enough: one pass per bill over the joined text, mapping the match
    # back to a word time by counting spaces.
    starts = []
    pos = 0
    for t, w in text_at:
        starts.append((pos, t))
        pos += len(w) + 1
    import bisect as _b
    keys = [p for p, _ in starts]
    for b, pat in pats.items():
        last = None
        for m in pat.finditer(joined):
            k = _b.bisect_right(keys, m.start()) - 1
            last = starts[max(0, k)][1]
        if last is not None:
            out[b] = last
    return out


def fill_ends(byb, last_seen=None):
    """A segment with no close ends where the next one begins.

    The chair announces a close far less often than an opening: 1,687 of 4,537
    placed bills have one. Where they do not, the honest end is not a fixed
    duration -- the old site added 35 minutes and was a minute and a half wrong
    on HB1123 -- but the moment the room moved on, which is the next boundary
    on the same recording whoever it belongs to.

    Ordered across the whole recording rather than per bill, because the next
    thing to happen is usually a different bill. A segment already carrying a
    stated close keeps it: that is a quotation and this is an inference.

    Returns the count filled, so a run can say how many ends it invented.
    """
    flat = sorted(((s["start"], b, s) for b, segs in byb.items() for s in segs),
                  key=lambda x: x[0])
    n = 0
    for i, (start, _b_, seg) in enumerate(flat):
        if seg.get("end") is not None:
            continue
        nxt = next((st for st, _, _ in flat[i + 1:] if st > start), None)
        if nxt is None:
            continue
        # Capped by the last time this bill was spoken of. Without the cap a
        # recording that breaks for lunch hands the morning's bill the whole
        # gap: HB1123's hearing ran 32 minutes and the next bill came two
        # hours later, so the uncapped rule called it a two-hour hearing.
        cap = (last_seen or {}).get(_b_)
        end = nxt if cap is None else min(nxt, cap + 60)
        if end > start:
            seg["end"] = round(end, 1)
            seg["end_from"] = ("next boundary" if end == nxt
                               else "last mention of the bill")
            n += 1
    return n


def sequence_of(byb):
    """The recording as an ordered list of what was taken up, in order.

    The per-bill map loses two things a reader of a whole committee day wants:
    the order, and the gaps between items. This keeps both, so a committee page
    can show a day's recording with the bills under it in the order they were
    heard without reconstructing that from a map keyed on bill number.
    """
    return [{"bill": b, "what": seg.get("what") or "", "start": seg["start"],
             "end": seg.get("end"), "how": seg.get("how")}
            for start, b, seg in
            sorted(((s["start"], b, s) for b, segs in byb.items() for s in segs),
                   key=lambda x: x[0])]


def to_segments(markers, candidates):
    """Openings become starts; a close of the same bill becomes its end.

    A LIST per bill, not one entry. A bill is commonly heard in the morning and
    voted in the afternoon's executive session -- two proceedings on one
    recording. Keeping only the first put the hearing's timestamp on the
    executive session and vice versa, which showed up as two of the three worst
    errors when this was first scored: HB261 marked at 63m and placed at 150m,
    HB160 marked at 140m and placed at 93m. Neither was a bad timestamp. Both
    were the right timestamp for the other proceeding.
    """
    segs = defaultdict(list)
    for m in markers:
        b = m["bill"]
        if m["kind"] == "open":
            segs[b].append({"start": m["t"], "end": None, "how": m["how"],
                            "what": m["what"], "said": m["said"]})
        else:
            open_ones = [s for s in segs.get(b, [])
                         if s["end"] is None and m["t"] > s["start"]]
            if open_ones:
                open_ones[-1]["end"] = m["t"]
    return {b: v for b, v in segs.items() if v}


def show_gaps(words, segs, candidates, titles, per=3):
    """What the chair says where a marker was expected and not found.

    54% of scheduled proceedings have no stated boundary. That is either a
    convention the patterns do not know, or a bill that was never taken up --
    and those need opposite responses. Guessing which is how the last two
    parsers in this project went wrong, so this prints the words instead.

    A day runs in order, so an unmarked bill sits between the bills either
    side of it in the docket. The gap between two stated openings is where it
    must be, and the start of that gap is where its own opening would have
    been said.
    """
    missing = [b for b in candidates if b not in segs]
    if not missing:
        return
    print(f"    {len(missing)} of {len(candidates)} had no stated boundary: "
          + ", ".join(missing[:8]))

    # Where the bill IS named, marker or not. A bill with no recognised
    # opening is usually still mentioned -- number or title finds 91% of
    # committee bills -- so the words at its first mention are the words the
    # chair used to introduce it, which is precisely what the patterns are
    # missing. A bill mentioned nowhere is a different case and says so.
    shown = 0
    for b in missing:
        if shown >= per:
            break
        hits = []
        kw = {w for w in norm(titles.get(b, "")).split()
              if w not in STOP and len(w) > 3}
        # Bounded by TIME, not by a count of words. Forty words can span a
        # ten-minute silence, and a window that does will match a title spoken
        # on the far side of it while reporting the time on this side. That is
        # the fourth time this project has reported a window's start as if it
        # were a match's time.
        # Every eighth word, not every word. A 20-second window is forty or
        # fifty words wide, so consecutive starts overlap almost entirely and
        # scanning each one re-reads the same text eight times over. On a
        # 40,000-word recording with twenty unmarked bills that is millions of
        # string joins, which is why this had to be interrupted rather than
        # waited out.
        step = 8
        for i in range(0, len(words), step):
            tt = words[i][0]
            j = i
            while j < len(words) and words[j][0] - tt <= 20:
                j += 1
            if j - i < 4:
                continue
            got, _how = match_bill(" ".join(w for _, w in words[i:j]),
                                   [b], titles)
            if got == b:
                hits.append(tt)
                break
        if not hits:
            print(f"      {b}: never named anywhere on this recording. "
                  "Probably not taken up.")
            shown += 1
            continue
        t0 = hits[0]
        lead = [w for tt, w in words if t0 - 14 <= tt < t0 + 26]
        shown += 1
        print(f"      {b} first named at {int(t0)//60}m {int(t0)%60:02d}s. "
              "What is said around it:")
        print(f"        \"{WS.sub(' ', ' '.join(lead))[:210]}\"")


def collect_phrases(words, segs, candidates, titles, bag):
    """The words just before each unmarked bill is named, gathered for counting.

    Reading one transcript at a time found twelve missing patterns and took an
    evening. There are several hundred recordings with no boundary at all, and
    the useful question is not what any one chair said but what many of them
    say that the patterns do not know.

    So: for every proceeding with no stated boundary, take the words
    immediately before the bill is first named -- which is where an opening
    would be -- and count the phrases across the whole set. A convention used
    by thirty chairs rises to the top; a one-off does not.
    """
    missing = [b for b in candidates if b not in segs]
    if not missing or not words:
        return
    parts, starts, pos = [], [], 0
    for tt, w in words:
        starts.append(pos)
        parts.append(w)
        pos += len(w) + 1
    text = " ".join(parts)

    for b in missing:
        found_at = None
        step = 8
        for i in range(0, len(words), step):
            tt = words[i][0]
            j = i
            while j < len(words) and words[j][0] - tt <= 20:
                j += 1
            if j - i < 4:
                continue
            got, _ = match_bill(" ".join(w for _, w in words[i:j]), [b], titles)
            if got == b:
                # WHERE in the window, not the window's start. The window is
                # fifty words wide, so its start is up to twenty seconds before
                # the bill is named -- and the words before the bill are the
                # whole point of collecting this.
                digits = re.sub(r"[^0-9]", "", b)
                kw = {w for w in norm(titles.get(b, "")).split()
                      if w not in STOP and len(w) > 3}
                for k in range(i, j):
                    bare = re.sub(r"[^a-z0-9]", "", words[k][1].lower())
                    if digits and digits in bare:
                        found_at = k
                        break
                    if bare in kw:
                        found_at = k
                        break
                if found_at is None:
                    found_at = i
                break
        if found_at is None:
            bag["never named"] += 1
            continue
        lead = [w.lower() for _, w in words[max(0, found_at - 14):found_at + 2]]
        lead = [re.sub(r"[^a-z0-9]", "", w) for w in lead]
        lead = [w for w in lead if w]
        for size in (3, 4, 5):
            for k in range(len(lead) - size + 1):
                bag[" ".join(lead[k:k + size])] += 1


def report_phrases(bag, out_path="missing_phrases.txt"):
    never = bag.pop("never named", 0)
    # Phrases that already appear in a pattern are not news.
    known = re.compile(r"open|clos|hearing|executive session|work session|"
                       r"next up|next bill|first bill|turn to|testimony", re.I)
    rows = [(c, ph) for ph, c in bag.items()
            if c >= 5 and len(ph.split()) >= 3 and not known.search(ph)]
    # Longest first at each count, then drop anything contained in a phrase
    # already shown with the same count -- those are fragments of it, not
    # separate findings. Thirty rows of one convention hid a second one
    # entirely on the first run.
    rows.sort(key=lambda r: (-r[0], -len(r[1].split()), r[1]))
    kept, shown = [], []
    for c, ph in rows:
        if any(c == c2 and ph in ph2 for c2, ph2 in shown):
            continue
        shown.append((c, ph))
        kept.append((c, ph))
    rows = kept
    print(f"\n{'=' * 70}\nWHAT IS SAID WHERE NO BOUNDARY WAS FOUND\n{'=' * 70}")
    print(f"  {never:,} proceedings were never named at all -- probably not "
          "taken up.\n")
    if not rows:
        print("  No phrase recurs five times or more. The remaining gaps are "
              "not a\n  shared convention this is missing.")
        return
    print("  Phrases just before an unmarked bill is named, most common first.")
    print("  Anything already covered by a pattern is left out.\n")
    for c, ph in rows[:30]:
        print(f"    {c:>5}  {ph}")
    Path(out_path).write_text(
        "\n".join(f"{c}\t{ph}" for c, ph in rows), encoding="utf-8")
    print(f"\n  {len(rows):,} phrases -> {out_path}")
    print("  A phrase used by many chairs is a convention worth a pattern. One "
          "used\n  twice is not, and adding it would be fitting to noise.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", nargs="+")
    ap.add_argument("--all", action="store_true",
                    help="every recording the manifest or floor index names")
    ap.add_argument("--work", default="work")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="candidate_segments.json")
    ap.add_argument("--phrases", action="store_true",
                    help="count what is said before every unmarked bill, "
                         "across all recordings, so a shared convention "
                         "shows up as a number rather than a hunch")
    ap.add_argument("--gaps", action="store_true",
                    help="for proceedings with no stated boundary, print what "
                         "the chair says where one was expected")
    ap.add_argument("--cache", default=".segment_cache.json",
                    help="results per recording, reused where its captions, "
                         "bill list and the patterns are all unchanged")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the cache and read every recording again")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    import csv
    bills = json.loads((Path(a.data) / "bills.json").read_text(encoding="utf-8"))
    if isinstance(bills, dict):
        bills = list(bills.values())
    titles = {b.get("id") or b.get("bill"): b.get("title", "") for b in bills}

    # One table, one reader. Committee proceedings and floor debates in the
    # same shape, so the floor cannot be silently left out again -- which it
    # was, four separate times, while the two lived in different files.
    prows = P.load()
    if not prows:
        sys.exit("No proceedings.csv. Run: python3 build_proceedings.py")
    byvid = defaultdict(list)
    for v, rs in P.by_video(prows).items():
        for r in rs:
            if r["bill"] not in byvid[v]:
                byvid[v].append(r["bill"])
    floor_vids = P.floor_videos(prows)
    # (video, bill) -> the floor row, for the roll-call end.
    floor_ent = {(r["video_id"], r["bill"]): r for r in P.floor_only(prows)
                 if r["video_id"] and not r["whole_video"]}
    print(f"{len(prows):,} proceedings on {len(byvid):,} recordings, "
          f"{len(floor_vids):,} of them floor sessions")

    if a.all:
        folders = [str(d) for d in sorted(Path(a.work).iterdir())
                   if d.is_dir() and d.name in byvid]
    else:
        folders = a.transcript or []
    if not folders:
        sys.exit("Nothing to do. Pass --transcript work/<id> or --all.")

    t_start = time.time()
    unread = {}
    result, stats, phrase_bag = {}, Counter(), Counter()
    sig = pattern_signature()
    cache_path = Path(a.cache)
    cache = {}
    if cache_path.exists() and not a.refresh:
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            cache = {}

    for folder in folders:
        vid = Path(folder).name
        cands = byvid.get(vid, [])
        if not cands:
            stats["no scheduled bills"] += 1
            continue
        key = cache_key(folder, cands, sig)
        hit = cache.get(vid)
        if hit and hit.get("key") == key and not a.gaps and not a.phrases:
            segs = hit["segs"]
            if hit.get("absent"):
                result.setdefault("_absent", {})[vid] = hit["absent"]
                stats["never named on the recording"] += len(hit["absent"])
            result[vid] = segs
            stats["recordings read"] += 1
            stats["unchanged since last run"] += 1
            stats["bills with a stated start"] += len(segs)
            stats["proceedings found"] += sum(len(v) for v in segs.values())
            stats["also with a stated end"] += sum(
                1 for v in segs.values() for s in v if s.get("end") is not None)
            stats["bills scheduled"] += len(cands)
            continue

        words = read_words(folder)
        if not words:
            # Name what IS in the folder. A recording transcribed by whisper
            # writes whatever transcribe_and_align calls it, and if that is not
            # in WORK_FILES the file is ignored -- forty minutes of local
            # transcription counted as "no captions" and no way to tell from
            # the summary. Silence and failure look the same again.
            here = sorted(x.name for x in Path(folder).iterdir()
                          if x.is_file()) if Path(folder).is_dir() else []
            stats["no captions"] += 1
            if here:
                unread.setdefault(", ".join(here[:3]), []).append(vid)
            continue
        is_floor = vid in floor_vids
        markers = find_markers(words, cands, titles, floor=is_floor)
        segs = to_segments(markers, cands)
        # A roll call closes the item, and its clock time is known to the
        # second from a source that has nothing to do with captions. Where one
        # exists it replaces a transcript-derived end outright.
        if is_floor:
            for b, ss in segs.items():
                e = floor_ent.get((vid, b))
                if e and e["precise"] and e["debate_end"]:
                    for s in ss:
                        if s["start"] < e["debate_end"]:
                            s["end"] = float(e["debate_end"])
                            s["end_from"] = "roll call clock"
                            stats["ends from the roll call clock"] += 1
                            break
        # Ends the chair did not state: the next boundary on the recording,
        # after the roll call clock has had its say above. Counted separately,
        # because one is a quotation and the other is an inference.
        stats["ends the chair stated"] += sum(
            1 for v in segs.values() for x in v if x.get("end") is not None)
        stats["ends from the next boundary"] += fill_ends(
            segs, last_mentions(words, cands))
        result[vid] = segs
        result.setdefault("_sequence", {})[vid] = sequence_of(segs)
        if a.phrases:
            collect_phrases(words, segs, cands, titles, phrase_bag)
        if a.gaps and not a.quiet:
            print(f"\n{vid}")
            show_gaps(words, segs, cands, titles)
        # On a floor recording, separate "no boundary found" from "not on this
        # recording at all". Only the first is a shortcoming.
        absent = never_named(words, cands, titles, set(segs)) if is_floor else []
        if absent:
            stats["never named on the recording"] += len(absent)
            result.setdefault("_absent", {})[vid] = absent
        cache[vid] = {"key": key, "segs": segs, "absent": absent}
        stats["recordings read"] += 1
        stats["bills with a stated start"] += len(segs)
        stats["proceedings found"] += sum(len(v) for v in segs.values())
        stats["with an end of either kind"] += sum(
            1 for v in segs.values() for s in v if s.get("end") is not None)
        stats["bills scheduled"] += len(cands)
        if not a.quiet:
            print(f"\n{vid}  {len(segs)} of {len(cands)} bills have a stated "
                  f"boundary")
            flat = sorted(((s["start"], b, s) for b, ss in segs.items()
                           for s in ss))[:6]
            for _, b, s in flat:
                t = int(s["start"])
                end = f" to {int(s['end'])//60}m" if s.get("end") else ""
                print(f"    {b:<9} {t//3600}:{(t%3600)//60:02d}:{t%60:02d}{end}"
                      f"   {s['what']}, by {s['how']}")
                print(f"      \"{s['said'][:96]}\"")

    # Merge, never replace. Running this on ONE recording used to write a
    # candidate file containing only that recording -- so a single debugging
    # run silently discarded every boundary found for the other 842, and the
    # next build published "the moment was not identified" for all of them.
    # Nothing warned, because writing a complete file is what the code was
    # asked to do.
    prior = {}
    op = Path(a.out)
    if op.exists():
        try:
            prior = json.loads(op.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            prior = {}
    kept = len(set(prior) - set(result))
    if kept:
        print(f"\n{kept:,} recordings already in {op.name} were left alone; "
              f"{len(result):,} updated")
    merged = dict(prior)
    merged.update(result)
    result = merged

    if not a.gaps and not a.phrases:
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    if a.phrases:
        report_phrases(phrase_bag)
    Path(a.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    took = time.time() - t_start
    read_fresh = stats["recordings read"] - stats.get("unchanged since last run", 0)
    if unread:
        print(f"\n  {sum(len(v) for v in unread.values())} folders hold files "
              f"this cannot read. It looks for "
              f"{', '.join(WORK_FILES)}:")
        for names, vids in sorted(unread.items(), key=lambda kv: -len(kv[1]))[:4]:
            print(f"    {len(vids):>4} folders contain: {names}")
            print(f"         e.g. {vids[0]}")

    print(f"\n{'=' * 70}")
    # Say plainly what was and was not re-read. "Is it redoing everything?"
    # should be answerable from the screen, not from a stopwatch.
    if a.refresh:
        print(f"  --refresh: every recording re-read ({took:.0f}s). The next run "
              "without it\n  reuses these results for anything unchanged.")
    elif stats.get("unchanged since last run"):
        print(f"  {stats['unchanged since last run']:,} recordings unchanged and "
              f"taken from the cache; {read_fresh:,} re-read ({took:.0f}s)")
    else:
        print(f"  every recording re-read ({took:.0f}s) -- no cache yet, or the "
              "patterns\n  changed and it expired")
    for k, v in stats.items():
        print(f"  {v:>6,}  {k}")
    got = stats["bills with a stated start"]
    tot = stats["bills scheduled"]
    absent_n = stats.get("never named on the recording", 0)
    taken_up = max(1, tot - absent_n)
    if tot:
        print(f"\n  {100 * got / taken_up:.0f}% of bills actually taken up have "
              "a boundary the chair stated.")
        if absent_n:
            print(f"  ({absent_n:,} of {tot:,} scheduled bills are never named "
                  "on their recording.\n  A floor calendar lists everything and "
                  "most passes on consent as a block;\n  those are not missing "
                  "boundaries, they are bills that were not debated.)")
        print("  Where a bill was taken up and no boundary was stated, this "
              "says so\n  rather than estimating one.")
    print(f"\n-> {a.out}")
    print("\nNothing is on the site until this is scored:\n"
          "  python3 probe_alignment.py --truth "
          f"--candidate {a.out}")


if __name__ == "__main__":
    main()
