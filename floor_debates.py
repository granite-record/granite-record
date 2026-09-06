#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Find where debate on each bill starts and ends in a House floor session.

Floor sessions are more tractable than committee hearings, because the Speaker
uses uniform language and one person runs the whole room. The structure is:

    Speaker introduces the bill and states the committee's motion
    Chair recognizes a member to speak AGAINST the motion
    Chair recognizes a member to speak FOR the motion
    ... alternating while speakers remain ...
    voice vote, OR if a division or roll call was requested:
        members return to their seats
        one member per side gives a brief parliamentary inquiry
        Speaker: press green to pass, red to fail, stations open thirty seconds
        chimes
        Speaker reads the count and whether the motion was adopted

So only ONE event has to be detected reliably: the Speaker introducing a bill.
Each introduction ends the previous bill's segment and starts the next. The vote
announcement is a useful confirmation, not a separate problem.

Roll call timestamps from RollCallSummary.txt then validate the result for free:
a bill's recorded vote should fall inside the segment assigned to that bill.

IMPORTANT: members speak for or against THE MOTION, not the bill. When the
committee moved Inexpedient to Legislate, speaking against the motion means
speaking for the bill. Positions are reported both ways here.

    python3 floor_debates.py --transcript work/VIDEOID/transcript.json \\
        --summary RollCallSummary.txt --date 2025-03-06 --video VIDEOID

Standard library only. Run transcribe_and_align.py first to get the transcript.
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BILL = re.compile(
    r"\b(?P<kind>HB|SB|CACR|HR|SR|HCR|SCR|HJR|house bill|senate bill)\s*"
    r"(?P<num>\d{1,4})\b", re.I)

# The Speaker opening a bill. Several forms, because the exact wording varies
# and speech recognition drops words. Any one of these near a bill number is
# treated as an introduction.
INTRO = [
    re.compile(r"\bclerk will read\b", re.I),
    re.compile(r"\bthe (?:question|motion) is on\b", re.I),
    re.compile(r"\bwe (?:have|move) (?:on )?(?:before us|to)\b", re.I),
    re.compile(r"\breport of the committee on\b", re.I),
    re.compile(r"\bmajority (?:of the )?committee (?:report|recommends)\b", re.I),
    re.compile(r"\bought to pass|inexpedient to legislate|interim study\b", re.I),
]

# "The Chair recognizes the gentlelady from Concord."
RECOGNIZE = re.compile(
    r"\b(?:chair|speaker) recognizes\s+(?:the\s+)?"
    r"(?P<who>gentleman|gentlelady|gentlewoman|representative|member)"
    r"(?:\s+from\s+(?P<town>[A-Z][A-Za-z.\- ]{2,28}?))?\s*[,.]", re.I)

# End-of-debate markers, in rough order of reliability.
VOTING_OPEN = re.compile(
    r"\b(?:voting stations? (?:are|is) open|press the green button|"
    r"green (?:button )?to (?:pass|adopt)|thirty seconds)\b", re.I)
RESULT = re.compile(
    r"\b(?:the motion is adopted|the motion fails|the ayes have it|"
    r"the nays have it|motion (?:is )?(?:adopted|failed))\b", re.I)
INQUIRY = re.compile(r"\bparliamentary inquiry\b", re.I)

# How a position on the motion maps to a position on the bill.
MOTION_SENSE = {
    "ought to pass": +1, "otp": +1, "otpa": +1,
    "ought to pass with amendment": +1,
    "inexpedient to legislate": -1, "itl": -1,
    "interim study": -1, "refer for interim study": -1,
    "indefinitely postpone": -1, "table": -1, "lay on table": -1,
}


def motion_sense(q):
    q = (q or "").strip().lower()
    for k, v in MOTION_SENSE.items():
        if q.startswith(k):
            return v
    return 0


def on_bill(pos_on_motion, sense):
    """pos_on_motion: 'for' or 'against'. Returns the position on the BILL."""
    if not sense:
        return "unclear"
    d = (1 if pos_on_motion == "for" else -1) * sense
    return "for the bill" if d > 0 else "against the bill"


def hhmmss(s):
    return str(timedelta(seconds=int(s)))


def load_transcript(p):
    segs = json.loads(Path(p).read_text(encoding="utf-8"))
    return sorted(segs, key=lambda s: s["start"])


def load_rollcalls(path, date, body="H"):
    out = []
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 13 or p[1].strip() != body:
                continue
            try:
                when = datetime.strptime(p[3].strip(), "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                continue
            if when.date().isoformat() != date:
                continue
            out.append({"num": p[2].strip(), "when": when, "bill": p[4].strip().upper(),
                        "q": p[11].strip(), "y": int(p[5] or 0), "n": int(p[6] or 0)})
    return sorted(out, key=lambda c: c["when"])


def normalise_bill(kind, num):
    k = kind.upper().replace(" ", "")
    k = {"HOUSEBILL": "HB", "SENATEBILL": "SB"}.get(k, k)
    return f"{k}{int(num)}"


def find_events(tr):
    """Introductions, recognitions, and end-of-debate markers, with times."""
    intros, recogs, ends = [], [], []
    for i, s in enumerate(tr):
        # look at a small window, since the bill number and the framing phrase
        # often land in adjacent transcript segments
        window = " ".join(x["text"] for x in tr[max(0, i - 1): i + 3])
        txt = s["text"]

        m = BILL.search(txt)
        if m and any(p.search(window) for p in INTRO):
            intros.append({"t": s["start"], "bill": normalise_bill(m.group("kind"), m.group("num")),
                           "text": txt.strip()[:140]})

        r = RECOGNIZE.search(txt)
        if r:
            recogs.append({"t": s["start"], "town": (r.group("town") or "").strip(" .,"),
                           "text": txt.strip()[:140]})

        if VOTING_OPEN.search(txt):
            ends.append({"t": s["start"], "kind": "voting opened", "text": txt.strip()[:120]})
        elif RESULT.search(txt):
            ends.append({"t": s["start"], "kind": "result announced", "text": txt.strip()[:120]})
        elif INQUIRY.search(txt):
            ends.append({"t": s["start"], "kind": "parliamentary inquiry", "text": txt.strip()[:120]})

    # collapse repeated introductions of the same bill within four minutes
    merged = []
    for it in intros:
        if merged and it["bill"] == merged[-1]["bill"] and it["t"] - merged[-1]["t"] < 240:
            continue
        merged.append(it)
    return merged, recogs, ends


def build_segments(intros, recogs, ends, rolls, stream_start, total):
    segs = []
    for i, it in enumerate(intros):
        start = it["t"]
        end = intros[i + 1]["t"] if i + 1 < len(intros) else total

        rc = None
        if stream_start:
            for c in rolls:
                off = (c["when"] - stream_start).total_seconds()
                if start <= off < end and c["bill"] == it["bill"]:
                    rc = {**c, "when": c["when"].isoformat(), "offset": off}
                    break

        # Debate proper ends when voting opens; the rest is the mechanics.
        closers = [e for e in ends if start <= e["t"] < end]
        debate_end = next((e["t"] for e in closers if e["kind"] == "voting opened"),
                     next((e["t"] for e in closers if e["kind"] == "parliamentary inquiry"),
                     next((e["t"] for e in closers if e["kind"] == "result announced"), end)))

        sense = motion_sense(rc["q"] if rc else "")
        spoke = []
        for j, r in enumerate([r for r in recogs if start <= r["t"] < debate_end]):
            # First recognised speaks against the motion, then alternating.
            pos = "against" if j % 2 == 0 else "for"
            spoke.append({"t": r["t"], "town": r["town"], "on_motion": pos,
                          "on_bill": on_bill("for" if pos == "for" else "against", sense)})

        segs.append({"bill": it["bill"], "start": start, "debate_end": debate_end,
                     "end": end, "speakers": spoke, "rollcall": rc,
                     "motion": rc["q"] if rc else None, "intro_text": it["text"]})
    return segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--summary", default="RollCallSummary.txt")
    ap.add_argument("--videos", help="channel index csv, for the stream start time")
    ap.add_argument("--video", help="video id, used with --videos")
    ap.add_argument("--date", required=True)
    ap.add_argument("--out", default="floor_debates.json")
    a = ap.parse_args()

    tr = load_transcript(a.transcript)
    total = max(s["end"] for s in tr)
    rolls = load_rollcalls(a.summary, a.date)

    stream_start = None
    if a.videos and a.video:
        for r in csv.DictReader(open(a.videos, encoding="utf-8-sig")):
            if r["video_id"] == a.video and r.get("start_eastern"):
                stream_start = datetime.strptime(r["start_eastern"], "%Y-%m-%d %H:%M:%S")
    if rolls and all((c["when"].hour, c["when"].minute) == (0, 0) for c in rolls):
        stream_start = None      # date-only timestamps cannot anchor

    intros, recogs, ends = find_events(tr)
    print(f"transcript {hhmmss(total)}   {len(tr):,} segments")
    print(f"detected: {len(intros)} bill introductions, {len(recogs)} speaker "
          f"recognitions, {len(ends)} end-of-debate markers")
    print(f"roll calls on {a.date}: {len(rolls)}"
          f"{'  (anchorable)' if stream_start else '  (no usable clock time)'}\n")

    if not intros:
        sys.exit("No introductions found. Send me a few minutes of the transcript "
                 "around a bill being taken up and I will fix the patterns.")

    segs = build_segments(intros, recogs, ends, rolls, stream_start, total)
    Path(a.out).write_text(json.dumps(segs, indent=2), encoding="utf-8")

    print(f"{'bill':<9}{'debate start':>13}{'debate end':>12}{'length':>9}"
          f"{'spk':>5}  motion / check")
    print("-" * 82)
    hits = misses = 0
    for s in segs:
        chk = ""
        if stream_start:
            if s["rollcall"]:
                chk = f"\u2713 roll call {s['rollcall']['num']} inside segment"
                hits += 1
            elif any(c["bill"] == s["bill"] for c in rolls):
                chk = "\u2717 roll call for this bill fell OUTSIDE the segment"
                misses += 1
            else:
                chk = "voice vote (no roll call)"
        print(f"{s['bill']:<9}{hhmmss(s['start']):>13}{hhmmss(s['debate_end']):>12}"
              f"{hhmmss(s['debate_end']-s['start']):>9}{len(s['speakers']):>5}  "
              f"{(s['motion'] or '')[:22]:<22} {chk}")

    if stream_start and (hits or misses):
        print(f"\nRoll call check: {hits} inside the right segment, {misses} outside.")
        print("This is the accuracy measure. Every roll call has a known bill and a")
        print("known time, so a miss means the segmentation is wrong, not the vote.")

    print("\nSpeaker positions, first debate with speakers:")
    for s in segs:
        if not s["speakers"]:
            continue
        print(f"  {s['bill']} \u2014 committee motion: {s['motion'] or 'unknown'}")
        for sp in s["speakers"]:
            town = f" from {sp['town']}" if sp["town"] else ""
            print(f"    {hhmmss(sp['t']):>9}  member{town}: "
                  f"{sp['on_motion']} the motion \u2192 {sp['on_bill']}")
        print("\n  Positions are inferred from the alternating order the Chair uses,")
        print("  not from what was said. Verify before publishing them.")
        break

    print(f"\n\u2192 {a.out}")


if __name__ == "__main__":
    main()
