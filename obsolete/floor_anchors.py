#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Test whether House roll call timestamps line up with the floor session video.

RollCallSummary.txt records the wall-clock time of every House roll call
("1/7/2026 11:12:09 AM"). The livestream archive records when the stream
started. Subtract one from the other and you have an exact offset into the
video -- no transcription, no scheduled-time guesswork, no reliance on the
calendar's intended order.

If that holds, floor alignment is largely solved:
  - Each roll call is a fixed anchor with a known bill and question.
  - Special orders stop mattering, because the timestamps give the order
    business was ACTUALLY taken up, not the order the calendar planned.
  - Bills passed on voice votes fall between two anchors, in a bounded
    window a transcript scan can search cheaply.

    python3 floor_anchors.py --summary RollCallSummary.txt \\
        --videos videos_house_2025-01-01_to_2025-03-31.csv --date 2025-03-06

Standard library only.
"""

import argparse
import csv
import glob
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def ampm(dt):
    """%-I is a glibc extension and %#I is Windows-only. Strip the pad instead."""
    return dt.strftime("%I:%M:%S %p").lstrip("0")


def hhmmss(sec):
    sign = "-" if sec < 0 else ""
    return sign + str(timedelta(seconds=abs(int(sec))))


def load_session_videos(path):
    """Floor sessions, not committee meetings. The title parses to 'Session'."""
    out = defaultdict(list)
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        if r.get("title_parsed") != "yes":
            continue
        cm = (r.get("parsed_committee") or "").strip().lower()
        if "session" not in cm:
            continue
        out[r["parsed_date"]].append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="RollCallSummary.txt")
    ap.add_argument("--videos", required=True)
    ap.add_argument("--date", required=True, help="session day, YYYY-MM-DD")
    ap.add_argument("--body", default="H", choices=["H", "S"])
    a = ap.parse_args()

    # Windows cmd.exe does not expand wildcards, so the shell hands the script
    # the literal string. Expand it here.
    paths = sorted(glob.glob(a.videos)) or [a.videos]
    vids = {}
    for pth in paths:
        for d, v in load_session_videos(pth).items():
            vids.setdefault(d, []).extend(v)
    if a.date not in vids:
        print(f"No floor session video found for {a.date}.")
        print("Days that do have one:")
        for d in sorted(vids)[:25]:
            print(f"  {d}  {vids[d][0]['title']}")
        sys.exit(1)

    v = vids[a.date][0]
    if len(vids[a.date]) > 1:
        print(f"Note: {len(vids[a.date])} session videos that day; using the first.\n")
    if not v.get("start_eastern"):
        sys.exit("That video has no livestream start time, so it cannot be anchored.")
    start = datetime.strptime(v["start_eastern"], "%Y-%m-%d %H:%M:%S")

    calls = []
    with open(a.summary, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 13 or p[1].strip() != a.body:
                continue
            try:
                when = datetime.strptime(p[3].strip(), "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                continue
            if when.date().isoformat() != a.date:
                continue
            calls.append({"num": p[2].strip(), "when": when, "bill": p[4].strip(),
                          "q": p[11].strip(), "y": p[5].strip(), "n": p[6].strip()})
    calls.sort(key=lambda c: c["when"])

    if not calls:
        sys.exit(f"No {a.body} roll calls found on {a.date} in {a.summary}.")

    midnight = sum(1 for c in calls if (c["when"].hour, c["when"].minute) == (0, 0))
    print(f"{v['title']}")
    print(f"video id {v['video_id']}   stream started {ampm(start)}")
    print(f"{len(calls)} roll calls on {a.date}\n")

    if midnight == len(calls):
        print("Every roll call is timestamped midnight -- this file records the date")
        print("only for this chamber, with no clock time. Anchoring will not work here.")
        print("(Expected for the Senate. If you see it for the House, tell me.)")
        return

    print(f"{'#':>4}  {'clock':>11}  {'offset':>9}  {'bill':<9} {'tally':>9}  question")
    print("-" * 78)
    prev = None
    for c in calls:
        off = (c["when"] - start).total_seconds()
        gap = "" if prev is None else f"  (+{hhmmss(off - prev)})"
        prev = off
        flag = ""
        if off < 0:
            flag = "  <-- BEFORE the stream started"
        print(f"{c['num']:>4}  {ampm(c['when']):>11}  {hhmmss(off):>9}  "
              f"{c['bill'] or '(procedural)':<9} {c['y']+'-'+c['n']:>9}  {c['q'][:26]}{flag}")

    # ---- debate windows -----------------------------------------------
    # A roll call closes the item it belongs to: the Speaker reads the count
    # and moves on. So a roll call offset is the END of that bill's floor
    # debate, accurate to seconds. Several consecutive roll calls on one bill
    # (table, then interim study, then amendment, then passage) are one debate.
    # The window between the previous bill's last roll call and this one's
    # bounds the start, and may also contain bills decided on voice votes,
    # which leave no timestamp anywhere.
    runs, prev = [], None
    for c in calls:
        if not c["bill"]:
            prev = c
            continue
        off = (c["when"] - start).total_seconds()
        if runs and runs[-1]["bill"] == c["bill"]:
            runs[-1]["end"] = off
            runs[-1]["motions"].append(c["q"])
        else:
            runs.append({"bill": c["bill"], "end": off, "motions": [c["q"]],
                         "first": off})
    for i, r in enumerate(runs):
        r["window_start"] = runs[i - 1]["end"] if i else 0.0
        r["gap"] = r["end"] - r["window_start"]

    print(f"\n{'bill':<9}{'debate ends':>13}{'window opens':>14}{'window':>9}"
          f"{'motions':>9}  note")
    print("-" * 76)
    for r in runs:
        note = ""
        if r["gap"] > 2400:
            note = "long gap - a recess or several voice-vote bills sit in here"
        elif r["gap"] > 900:
            note = "wide window - probably other bills inside it"
        print(f"{r['bill']:<9}{hhmmss(r['end']):>13}{hhmmss(r['window_start']):>14}"
              f"{hhmmss(r['gap']):>9}{len(r['motions']):>9}  {note}")

    out = [{"bill": r["bill"], "debate_end": round(r["end"], 1),
            "window_start": round(r["window_start"], 1),
            "motions": r["motions"], "video_id": v["video_id"],
            "date": a.date, "body": a.body,
            "end_url": f"https://www.youtube.com/watch?v={v['video_id']}"
                       f"&t={max(int(r['end']) - 240, 0)}s"} for r in runs]
    Path(f"floor_{a.body}_{a.date}.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n{len(runs)} bills with a precise end time -> "
          f"floor_{a.body}_{a.date}.json")
    print("Bills decided on voice votes leave no timestamp and fall inside the")
    print("windows above; those still need the transcript.")

    print("\nOpen these and check that the Clerk really is calling that vote.")
    print("Three spread across the day is enough to prove or disprove it.\n")
    for c in [calls[0], calls[len(calls)//2], calls[-1]]:
        off = int((c["when"] - start).total_seconds())
        t = max(off - 45, 0)      # start slightly early, the bells run first
        print(f"  roll call {c['num']} ({c['bill'] or 'procedural'}, {c['q'][:30]})")
        print(f"    https://www.youtube.com/watch?v={v['video_id']}&t={t}s")

    print("\nWhat the answer means:")
    print("  Within ~1 minute  -> floor alignment is essentially solved. Roll calls")
    print("                       become fixed anchors and voice-vote bills sit in")
    print("                       bounded windows between them.")
    print("  Off by a constant -> the clock is running against a different reference.")
    print("                       Tell me the offset; it is a one-line correction.")
    print("  Off unpredictably -> timestamps are entered after the fact, and the floor")
    print("                       needs the same transcript approach as committees.")


if __name__ == "__main__":
    main()
