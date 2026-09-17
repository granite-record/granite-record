#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.4
"""
Build a per-bill index of floor debates, keyed to the session recordings.

    python3 build_floor_index.py --videos videos_house_2026-01-01_to_2026-06-30.csv \\
        --summary RollCallSummary.txt --narratives narratives.json

Writes floor_index.json, which build_site_v2.py merges into each bill's
hearings tab alongside its committee proceedings.

How the timing works, from watching a real session:

A roll call CLOSES the item it belongs to. The Speaker reads the count and moves
on, so a roll call's clock time is the END of that bill's floor debate, accurate
to seconds once the stream's start time is known. Checked against hand-marked
boundaries on 2026-03-05: HB1225 within 7 seconds, HB1048 within 3, HB1635 exact.

Several consecutive roll calls on one bill -- table, then interim study, then an
amendment, then passage -- are one debate, so they are grouped. The gap since the
previous bill's last roll call bounds where the debate began, and may also hold
bills decided on voice votes, which leave no timestamp anywhere.

Bills that never got a roll call still get a link. The docket records the date of
the floor action, and the session video for that date is known, so the entry says
which recording and that the moment could not be identified automatically.

Senate roll calls in RollCallSummary.txt carry a date but a midnight time, so
Senate floor debates get the recording and no offset.
"""

import argparse
import csv
import json
import narrative
import re
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# "Committee of Conference on SB 534 (05/22/2026)" and similar. When a title
# names its bill, the whole recording is that one proceeding -- no alignment
# needed at all. Conference committees are also where the final compromise on a
# contested bill gets written, so they are worth more per minute than almost
# anything else on the channel.
BILL_IN_TITLE = re.compile(r"\b(HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?(\d+)\b", re.I)
CONFERENCE = re.compile(r"committee of conference|conference committee", re.I)


def load_bill_named_videos(paths):
    """Recordings whose title names the bill they cover."""
    out = []
    for p in paths:
        if not Path(p).exists():
            continue
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            title = r.get("title", "")
            bills = {f"{m.group(1).upper()}{m.group(2)}"
                     for m in BILL_IN_TITLE.finditer(title)}
            if not bills:
                continue
            out.append({"video_id": r["video_id"], "title": title,
                        "date": r.get("parsed_date") or "",
                        "bills": sorted(bills),
                        "conference": bool(CONFERENCE.search(title)),
                        "body": "S" if "senate" in p.lower() else "H"})
    return out


def load_session_videos(paths):
    """Floor session recordings by (date, chamber). Committee videos excluded.

    KEYED ON THE CHAMBER AS WELL AS THE DAY, and it has to be. This was keyed
    on the date alone, with "prefer the longest recording when a day has more
    than one" to break ties -- which reads as a sensible rule right up until
    you notice that the two recordings on such a day are usually not two takes
    of one sitting. They are the House and the Senate, both of which met.

    So the longer chamber's video won the day and was handed to the other
    chamber's rows as well: 1,338 rows of proceedings.csv across 24 dates and
    993 bills, where a reader following a Senate vote was shown the House
    sitting instead. The correct recording existed every one of those 24 times
    and was passed over.

    The tie-break is kept, because a chamber really can have two recordings of
    one day; it now only ever compares a chamber against itself.
    """
    out = {}
    for p in paths:
        if not Path(p).exists():
            print(f"  missing: {p}")
            continue
        # The file names the chamber, and so does the title. Title first, since
        # a recording is what it says it is; the path is the fallback for a
        # title that does not say.
        path_body = "S" if "senate" in str(p).lower() else "H"
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            if r.get("title_parsed") != "yes":
                continue
            if "session" not in (r.get("parsed_committee") or "").lower():
                continue
            d = r["parsed_date"]
            t = (r.get("title") or "").lower()
            body = ("S" if "senate" in t else "H" if "house" in t else path_body)
            start = None
            if r.get("start_eastern"):
                try:
                    start = datetime.strptime(r["start_eastern"], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            # Prefer the longest recording when ONE CHAMBER has more than one.
            prev = out.get((d, body))
            if prev is None or len(r.get("duration_iso", "")) > len(prev["duration"]):
                out[(d, body)] = {"video_id": r["video_id"], "start": start,
                                  "title": r["title"],
                                  "duration": r.get("duration_iso", "")}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", nargs="+", required=True)
    ap.add_argument("--summary", default="RollCallSummary.txt")
    ap.add_argument("--narratives", default="narratives.json")
    ap.add_argument("--out", default="floor_index.json")
    a = ap.parse_args()

    vids = load_session_videos(a.videos)
    # The keys are (date, chamber) now, so the span is over the dates in them.
    _days = sorted({d for d, _ in vids})
    print(f"{len(vids)} session recordings across "
          f"{_days[0] if _days else '-'} to {_days[-1] if _days else '-'}"
          f" ({sum(1 for _, c in vids if c == 'H')} House, "
          f"{sum(1 for _, c in vids if c == 'S')} Senate)")

    # ---- roll calls, grouped into runs per bill within a day ---------------
    calls = defaultdict(list)
    with open(a.summary, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) < 13:
                continue
            try:
                when = datetime.strptime(p[3].strip(), "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                continue
            calls[(p[1].strip(), when.date().isoformat())].append({
                "num": int(p[2] or 0), "when": when, "bill": p[4].strip().upper(),
                "q": p[11].strip(), "y": p[5].strip(), "n": p[6].strip()})

    index = defaultdict(list)
    precise = dated = 0
    for (body, date), cs in sorted(calls.items()):
        cs.sort(key=lambda c: (c["when"], c["num"]))
        # (date, body): this loop has known the chamber all along -- it is the
        # first half of the key it is iterating -- and looked the recording up
        # by the day alone anyway.
        vid = vids.get((date, body))
        if not vid:
            continue
        # A whole chamber's roll calls timestamped midnight means the file
        # records the date only. Real for the Senate.
        clocked = any((c["when"].hour, c["when"].minute) != (0, 0) for c in cs)
        anchor = vid["start"] if (clocked and vid["start"]) else None

        runs = []
        for c in cs:
            if not c["bill"]:
                continue
            if runs and runs[-1]["bill"] == c["bill"]:
                runs[-1]["last"] = c["when"]
                runs[-1]["motions"].append(c["q"])
                runs[-1]["tallies"].append(f"{c['y']}-{c['n']}")
            else:
                runs.append({"bill": c["bill"], "last": c["when"],
                             "motions": [c["q"]], "tallies": [f"{c['y']}-{c['n']}"]})
        for i, r in enumerate(runs):
            entry = {"date": date, "body": body, "video_id": vid["video_id"],
                     "motions": r["motions"], "tallies": r["tallies"],
                     "kind": "floor debate"}
            if anchor:
                end = (r["last"] - anchor).total_seconds()
                prev_end = ((runs[i - 1]["last"] - anchor).total_seconds()
                            if i else 0.0)
                if end > 0:
                    entry.update({"debate_end": round(end, 1),
                                  "window_start": round(max(prev_end, 0), 1),
                                  "precise": True})
                    precise += 1
            if "precise" not in entry:
                entry["precise"] = False
                dated += 1
            index[r["bill"]].append(entry)

    # ---- floor actions with no roll call -----------------------------------
    # A voice or division vote leaves no timestamp, but the docket gives the
    # date, so the right recording is still known.
    seen = {(b, e["date"]) for b, es in index.items() for e in es}
    novote = 0
    # One term's worth: narratives.json is keyed on the term now, and this
    # tool works on the session it was pointed at.
    nar = narrative.load_narratives(a.narratives)
    for bill, rec in nar.items():
        b = bill.upper()
        for e in rec.get("events", []):
            if e.get("type") != "floor" or e.get("cancelled"):
                continue
            if e.get("vote_kind") == "RC":
                continue
            d = e.get("date")
            # The event says which chamber acted; the recording must be that
            # chamber's. An event with no body cannot be paired at all now --
            # better silent than confidently showing the other chamber.
            ebody = (e.get("body") or "").strip().upper()[:1]
            if not d or not ebody or (b, d) in seen or (d, ebody) not in vids:
                continue
            index[b].append({
                "date": d, "body": e.get("body"),
                "video_id": vids[(d, ebody)]["video_id"],
                "motions": [e.get("action") or "Floor action"], "tallies": [],
                "kind": "floor debate", "precise": False,
                "vote_kind": e.get("vote_kind")})
            seen.add((b, d))
            novote += 1

    # ---- recordings that name their bill -----------------------------------
    named = load_bill_named_videos(a.videos)
    nconf = 0
    for v in named:
        for b in v["bills"]:
            if any(e.get("video_id") == v["video_id"] and e["date"] == v["date"]
                   for e in index.get(b, [])):
                continue
            index[b].append({
                "date": v["date"], "body": v["body"], "video_id": v["video_id"],
                "motions": [], "tallies": [], "precise": False,
                # Only when the title names ONE bill. "Committee of
                # Conference on HB 144, HB 67, HB 154, HB 464, HB 613" is five
                # proceedings in one recording with boundaries between them,
                # and calling it whole-video told the pipeline there was
                # nothing to segment -- so all five bills pointed at the same
                # two hours and the recording was skipped for captions.
                # 36 of the 59 name more than one.
                "whole_video": len(v["bills"]) == 1, "title": v["title"],
                "kind": "committee of conference" if v["conference"]
                        else "recording naming this bill"})
            nconf += 1

    for b in index:
        index[b].sort(key=lambda e: (e["date"], e.get("debate_end") or 0))
    Path(a.out).write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(f"\n{len(index):,} bills with a floor appearance -> {a.out}")
    print(f"  {precise:,} with a precise end time from a roll call")
    print(f"  {dated:,} roll call entries with no usable clock time")
    print(f"  {novote:,} voice or division votes, recording linked by date only")
    print(f"  {nconf:,} recordings that name their bill in the title "
          "(whole recording is that bill)")
    multi = sum(1 for b, es in index.items() if len(es) > 1)
    print(f"  {multi:,} bills reached the floor on more than one day")

    sample = [(b, es) for b, es in index.items()
              if any(e.get("precise") for e in es)][:3]
    if sample:
        print("\nsample:")
        for b, es in sample:
            for e in es:
                if not e.get("precise"):
                    continue
                s, t = int(e["window_start"]), int(e["debate_end"])
                print(f"  {b:<9} {e['date']}  debate ends {t//3600}:{(t%3600)//60:02d}:"
                      f"{t%60:02d}, window opens {s//3600}:{(s%3600)//60:02d}:{s%60:02d}"
                      f"  ({len(e['motions'])} motion"
                      f"{'s' if len(e['motions'])!=1 else ''})")


if __name__ == "__main__":
    main()
