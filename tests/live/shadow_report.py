#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.1
"""
What the live Worker saw on one day in shadow, against that day's calendar.
Offline: it reads files the person downloaded and asks nobody anything.

    npx.cmd wrangler r2 object get graniterecord-live/streams/2026-10-30.json --file streams-2026-10-30.json --remote
    npx.cmd wrangler r2 object get graniterecord-live/state.json --file state.json --remote
    python3 tests/live/shadow_report.py streams-2026-10-30.json --state state.json \\
        --calendar <the House calendar's .txt> [--calendar <the Senate's> --chamber S]
    python3 tests/live/shadow_report.py streams-2026-10-30.json --meetings meetings.txt

`--meetings` takes plain lines, "09:30 | HHS Oversight" (a chamber may follow:
"09:30 | HHS Oversight | H"), for meetings a calendar file does not hold or
this reader does not parse (commissions, task forces).

FOR EACH STREAM: its status and times; when the uploads playlist and the
search backstop each first saw it, against YouTube's own actualStartTime
(the shadow measurement of design section 1.1); and the meeting it matches,
with how: "stem", the title's stem equal to the meeting's name as both are
compared (live_gen.stem; the words committee, house, senate and meeting
types set aside); "contains", one inside the other; "past recordings", the
title's stem equal to that of a past recording in collected/videos/ whose
committee is the meeting's. A stream that matches nothing is listed as such.
Then every meeting with no stream, and what state.json held.

The match is the Python's own reading of section 1.2's rule, for evidence
only: it is not the page's code, which a later branch writes. Where they
disagree, the page's is the one to fix or to explain.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

import live_gen

NH = ZoneInfo("America/New_York")
# Words that say what kind of meeting or chamber, not which committee.
SET_ASIDE = {"committee", "house", "senate", "public", "hearing", "hearings", "executive", "session",
             "work", "full", "subcommittee", "meeting", "remote", "the", "of", "on", "and", "nh", "joint"}


def words(s):
    return [w for w in live_gen.stem(s).split() if w not in SET_ASIDE]


def when(iso):
    if not iso:
        return None
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def clock(t):
    return t.astimezone(NH).strftime("%H:%M") if t else "-"


def minutes(a, b):
    return f"{(a - b).total_seconds() / 60:+.0f} min" if a and b else "-"


def meetings_from_lines(path, day):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2 or not parts[1]:
            continue
        out.append({"time": parts[0], "name": parts[1], "body": parts[2] if len(parts) > 2 else "",
                    "from": Path(path).name, "date": day})
    return out


def meetings_from_calendar(path, chamber, day):
    import calendar_meetings as CM
    rows, _pub, _unpaired = CM.parse(Path(path).read_text(encoding="utf-8", errors="replace"), chamber)
    seen, out = set(), []
    for r in rows:
        d = r.get("date")
        d = d.isoformat() if hasattr(d, "isoformat") else str(d or "")
        if d[:10] != day:
            continue
        key = (r.get("time"), r.get("committee"))
        if key in seen:
            continue
        seen.add(key)
        out.append({"time": str(r.get("time") or ""), "name": r.get("committee") or "", "body": chamber,
                    "from": Path(path).name, "date": day})
    return out


def past_titles():
    """{title stem: committee as the index parsed it} from collected/videos/."""
    out = {}
    for p in sorted(Path("collected/videos").glob("videos_*.csv")):
        with p.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                c = (row.get("parsed_committee") or "").strip()
                if c and row.get("title"):
                    out.setdefault(live_gen.stem(row["title"]), c)
    return out


def match(stream, meetings, history):
    """(meeting, how) or (None, None)."""
    sw = words(stream.get("title") or "")
    if not sw:
        return None, None
    same = [m for m in meetings if (not m["body"] or not stream.get("chamber") or m["body"] == stream["chamber"])]
    for m in same:
        if words(m["name"]) == sw:
            return m, "stem"
    for m in same:
        mw = words(m["name"])
        if mw and (" ".join(mw) in " ".join(sw) or " ".join(sw) in " ".join(mw)):
            return m, "contains"
    past = history.get(live_gen.stem(stream.get("title") or ""))
    if past:
        for m in same:
            if words(m["name"]) == words(past):
                return m, "past recordings"
    return None, None


def report(streams_file, state_file, meetings, history):
    f = json.loads(Path(streams_file).read_text(encoding="utf-8"))
    lines = [f"Streams file for {f.get('day')}: checked {f.get('checked')}, next check {f.get('next_check')}, "
             f"status {json.dumps(f.get('status'))}", ""]
    matched = set()
    unmatched = 0
    for s in f.get("streams", []):
        started = when(s.get("started"))
        seen = s.get("seen") or {}
        m, how = match(s, meetings, history)
        if m:
            matched.add(id(m))
        else:
            unmatched += 1
        lines += [f"- {s.get('chamber') or '?'} {s.get('title')!r} ({s.get('video')}), {s.get('status')}"
                  + (", not embeddable" if s.get("embeddable") is False else ""),
                  f"    scheduled {clock(when(s.get('scheduled')))}, started {clock(started)}, "
                  f"ended {clock(when(s.get('ended')))} (New Hampshire time)",
                  f"    first seen: playlist {clock(when(seen.get('playlist')))} "
                  f"({minutes(when(seen.get('playlist')), started)} from its start), "
                  f"search {clock(when(seen.get('search')))} ({minutes(when(seen.get('search')), started)})",
                  f"    meeting: {m['time']} {m['name']} [{m['from']}], by {how}" if m
                  else "    meeting: NONE MATCHED"]
    lines += ["", f"{len(f.get('streams', []))} streams, {unmatched} matched to no meeting.", ""]
    missing = [m for m in meetings if id(m) not in matched]
    lines.append(f"Meetings on the calendar with no stream found ({len(missing)} of {len(meetings)}):")
    lines += [f"- {m['time']} {m['name']} {m['body']} [{m['from']}]" for m in missing] or ["- none"]
    if state_file:
        st = json.loads(Path(state_file).read_text(encoding="utf-8"))
        yt = st.get("yt") or {}
        lines += ["", "state.json:",
                  f"- today's spend: {json.dumps(st.get('count'))}",
                  f"- upcoming ids kept: {len(yt.get('upcoming') or {})}; live now: {len(yt.get('live') or [])}; "
                  f"failed looks in a row: {yt.get('fails', 0)}; hold: {json.dumps(yt.get('held'))}; "
                  f"search held to: {yt.get('search_held')}",
                  f"- uploads playlists confirmed: {json.dumps(yt.get('uploads'))}",
                  f"- last discovery {yt.get('discovery')}, last search {yt.get('search')}, "
                  f"refreshed {yt.get('refreshed')}; lease {json.dumps(st.get('lease'))}",
                  f"- database half: {json.dumps(st.get('sql') or {})[:200]} (shadow: expected empty)"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("streams", help="streams/<date>.json as downloaded")
    ap.add_argument("--state", help="state.json as downloaded")
    ap.add_argument("--calendar", action="append", default=[], help="a calendar's text file (repeatable)")
    ap.add_argument("--chamber", action="append", default=[], help="H or S, one per --calendar (default H)")
    ap.add_argument("--meetings", action="append", default=[], help='plain lines, "09:30 | name [| H]"')
    a = ap.parse_args()
    day = json.loads(Path(a.streams).read_text(encoding="utf-8")).get("day")
    meetings = []
    for i, c in enumerate(a.calendar):
        meetings += meetings_from_calendar(c, (a.chamber[i] if i < len(a.chamber) else "H"), day)
    for m in a.meetings:
        meetings += meetings_from_lines(m, day)
    print(report(a.streams, a.state, meetings, past_titles()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
