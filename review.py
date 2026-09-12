#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.12
"""
The bench: one sample at a time, judged by a person, written down for good.

    python3 review.py                 # opens on http://127.0.0.1:8799
    python3 review.py --port 9000
    python3 review.py --report        # what has been judged so far, no server

LOCAL ONLY, AND NOT PART OF THE SITE. It binds 127.0.0.1, writes nothing into
site/, and site/ is never served from here. Nothing this tool produces reaches
graniterecord.org except by a person deciding it should.

WHY IT EXISTS

Every derived thing on this site is measured against something a person
checked, and there is very little of that: ground_truth.csv holds 35
proceedings somebody timed by watching, and it is the ONLY independent measure
this project has. CLAUDE.md requires every timestamp method be scored against
it. A set of 35 can be fitted without anyone noticing.

The same problem is arriving twice more. Related bills and narrative quality
both need a judgment no generator can make, and both are about to be built.
One bench, three uses.

WHAT IT WILL NOT DO

It will not overwrite an answer. review/checked.jsonl is append-only: every
judgment is a new line, and a second look at the same item is a second line
rather than a replacement. Nothing here rewrites ground_truth.csv either --
that file is a person's, and preflight fails if a generator opens it for
writing. This writes its own file and probe_alignment.py can read both.

THE KINDS

Each kind knows how to pick an item nobody has judged, how to show it, and
what to ask. Adding one is a dict in KINDS; nothing else changes.
"""

import argparse
import csv
import html
import json
import random
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import site_read as SR

OUT = Path("review")
LEDGER = OUT / "checked.jsonl"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


# ------------------------------------------------------------------ storage

def judged():
    """Every key already judged, and how many times."""
    seen = {}
    if not LEDGER.exists():
        return seen
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        seen.setdefault((d.get("kind"), d.get("key")), []).append(d)
    return seen


def record(entry):
    """APPEND. Never rewrite: a judgment is evidence, and a later look at the
    same item is a second piece of evidence rather than a correction of the
    first. Which one to believe is a question for whoever reads the file."""
    OUT.mkdir(exist_ok=True)
    entry["at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# -------------------------------------------------------------------- kinds

def _hms(sec):
    try:
        s = int(float(sec))
    except (TypeError, ValueError):
        return ""
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _yt(vid, sec=None):
    u = f"https://www.youtube.com/watch?v={vid}"
    try:
        return u + f"&t={int(float(sec))}s"
    except (TypeError, ValueError):
        return u


# The page's own word for how sure it is, said the way a person can judge it.
# The bench asks "is this right", and that question is different for a
# boundary somebody spoke and a boundary a model guessed.
STATE_SAID = {
    "stated": "the chair said it &mdash; a quoted boundary",
    "floor_stated": "the presiding officer said it, on the floor",
    "floor_precise": "a roll call's clock time, from the written record",
    "located": "<b>inferred</b> &mdash; nobody said it; the model placed it",
    "whole_video": "the whole recording is this one bill",
}


def _site_records(site=Path("site")):
    """Every bill page's record, as the reader receives it.

    THE PAGE, NOT THE TABLE BEHIND IT. This sampler used to read
    proceedings.csv's predicted_offset, and that field is the SCHEDULE: the
    meeting was called for 09:00, the stream began at 08:54:21, so it reads
    339 seconds. The page never prints that. It prints what build_site_v2
    resolved by laying the stated boundaries over the schedule, and for
    HB1118 that is 58:07 against the schedule's 5:39.

    Nine judgments were entered against a number no reader has ever been
    shown before anybody noticed. A bench that grades something other than
    what is published is worse than no bench, because its verdicts look like
    evidence.

    The walk itself now lives in site_read.py, because this was the second
    reader of the same convention and probe_alignment wanted a third. Only
    the years with recordings are read: 2,234 pages rather than 33,683.
    """
    return SR.records(site, years=SR.video_years())


def sample_timestamps():
    """A proceeding the site prints a time for, and the recording it is in.

    Only the ones that print a start: those are the claims a stopwatch can
    settle. A consent-calendar bill and a proceeding marked "approximate"
    print no time at all, so there is nothing there to be right or wrong
    about -- finding when those happened is a different and much longer job
    than checking a claim, and mixing the two would make every draw a gamble
    on how long it takes.
    """
    out = []
    for year, bid, rec in _site_records():
        for st in (rec.get("stations") or []):
            vid = st.get("video_id")
            if not vid or st.get("start") is None:
                continue
            out.append({
                # The same key shape the ledger already holds, so an item
                # judged before this change is still recognised as judged.
                "key": f'{vid}|{bid}|{st.get("what") or ""}',
                "bill": bid, "year": year, "video_id": vid,
                "committee": st.get("committee") or "",
                "date": st.get("when") or "",
                "proceeding": st.get("what") or "",
                "title": st.get("title") or "",
                # WHAT THE PAGE PRINTS. These are the numbers under judgment.
                "start": st.get("start"), "end": st.get("end"),
                "state": st.get("state") or "",
                "said_how": st.get("said_how") or "",
                "tolerance": st.get("tolerance"),
                "end_stated": bool(st.get("end_stated")),
                # The schedule offset, kept beside them and labelled. It is
                # what this sampler used to show on its own, and seeing the
                # two together is how the next mix-up gets caught early.
                "scheduled": st.get("predicted"),
            })
    return out


def show_timestamps(it):
    start, end = it.get("start"), it.get("end")

    def sec(x):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return None

    s0, s1 = sec(start), sec(end)
    claim = STATE_SAID.get(it.get("state"), E(it.get("state") or "unknown"))
    if it.get("said_how"):
        claim += f' <span class="dim">({E(it["said_how"])})</span>'
    sched = sec(it.get("scheduled"))
    # An end the model guessed and an end the chair closed are different
    # claims, and the page distinguishes them, so the bench does too.
    end_note = "" if it.get("end_stated") else " &middot; end inferred"
    span = (f'<b class="t">{E(_hms(start))}</b> &nbsp;&nbsp;'
            f'<span class="dim">to</span>&nbsp;&nbsp;'
            f'<b class="t">{E(_hms(end))}</b>'
            f'<span class="dim">{end_note}</span>') if s1 is not None else (
        f'<b class="t">{E(_hms(start))}</b> &nbsp; '
        '<span class="dim">no end published</span>')
    rows = [
        ("Bill", f'{E(it["bill"])} <span class="dim">({E(it.get("year") or "")})</span>'),
        ("Proceeding", f'{E(it["proceeding"])} &middot; {E(it["committee"])}'
                       f' &middot; {E(it["date"])}'),
        ("Recording", f'<a href="{E(_yt(it["video_id"]))}" target="_blank" '
                      f'rel="noopener">{E(it["title"] or it["video_id"])}</a>'),
        # NOT THE TOLERANCE. The record carries one, and app.js stopped
        # printing it on purpose -- "methodology in the reader's way" -- so a
        # reader is never told "within 5 minutes" and the bench must not
        # invent the claim in order to grade it. What the reader does see is
        # the single word "approximate", and only where the start was not
        # spoken. That is the claim, and this says which it is.
        ("How the page places it", claim),
        ("What a reader is told",
         '<span class="dim">nothing &mdash; the time is given plainly</span>'
         if it.get("state") in ("stated", "floor_stated", "floor_precise")
         else '<span class="dim">the word <b>approximate</b> beside the '
              'time</span>'),
        # BOTH TIMES, SIDE BY SIDE. Checking whether a proceeding ran to where
        # the site says it did used to mean opening a second tab and losing
        # the first.
        ("Published start", span),
    ]
    # Only where it differs enough to be worth a line. The schedule agreeing
    # with the published time says nothing; the schedule being an hour away
    # is the whole reason this row exists.
    if sched is not None and s0 is not None and abs(sched - s0) >= 60:
        rows.append(("For contrast, the schedule",
                     f'<span class="dim">{E(_hms(sched))} &mdash; when the '
                     f'meeting was called for. Not what the page prints, and '
                     f'not what you are judging.</span>'))
    body = "".join(f'<tr><th>{E(k)}</th><td>{v}</td></tr>' for k, v in rows)

    # The player itself, so the whole judgment happens on one screen. The
    # IFrame API is what makes "use the current time" possible: without it the
    # only way to report a moment is to read it off the player and retype it.
    player = (f'<div class="player"><div id="ytplayer"></div></div>'
              f'<div id="ytdata" data-video="{E(it["video_id"])}" '
              f'data-start="{s0 if s0 is not None else 0}" '
              f'data-end="{s1 if s1 is not None else ""}"></div>')

    controls = (
        '<p class="jump">'
        '<button type="button" class="btn" data-seek="start">'
        f'Play from the published start &mdash; {E(_hms(start))}</button>'
        + (f'<button type="button" class="btn" data-seek="end">'
           f'Play from the published end &mdash; {E(_hms(end))}</button>'
           if s1 is not None else "")
        + '<button type="button" class="btn grab" data-grab="observed_start">'
          'Use what is playing as the start</button>'
          '<button type="button" class="btn grab" data-grab="observed_end">'
          'Use what is playing as the end</button>'
        + f'<a class="btn" href="{E(_yt(it["video_id"], start))}" target="_blank" '
          'rel="noopener">Open on YouTube</a></p>')

    return (f'<table class="facts">{body}</table>{player}{controls}'
            '<p class="ask">Play it, pause where the chair takes this bill up, '
            'and press <b>Use what is playing as the start</b>. Same for the '
            'end. Leave a box empty to say the published time is right.</p>')


def sample_late():
    """Every proceeding on a recording whose captions run an hour behind it.

    Nine recordings of 2024-2026 carry a YouTube caption track an hour
    behind its own video -- seen in YouTube's own player on 11 September:
    "going to open the hearing on House Bill 1130" is captioned at 0:17:28
    over the blue starting slate, and said at 1:17:28. build_site_v2
    withholds every time read off those captions, so their stations print no
    start, and sample_timestamps() -- which only draws a station that prints
    one -- could never offer them. Shifting them by 3,600 seconds would put
    76 stated starts back, and that is a new way of making a timestamp, so it
    is timed here first.

    The same key shape as a timing item, so probe_alignment reads the
    stopwatch readings beside every other bench mark.
    """
    import caption_span as CS
    work = Path("work")
    if not work.is_dir():
        return []
    late, _compared, _undated = CS.out_of_step(
        [d.name for d in work.iterdir() if d.is_dir()])
    if not late:
        return []
    # Already timed with a stopwatch under the timing kind -- HB1130 on
    # 28 January was, on the 10th, which is how the hour was found -- is not
    # asked for twice.
    timed = {key for (kd, key), es in judged().items() if kd == "timestamp"
             and any((e.get("fields") or {}).get("observed_start") for e in es)}
    out = []
    for year, bid, rec in _site_records():
        for st in (rec.get("stations") or []):
            vid = st.get("video_id")
            if vid not in late:
                continue
            if f'{vid}|{bid}|{st.get("what") or ""}' in timed:
                continue
            last, dur = late[vid]
            out.append({
                "key": f'{vid}|{bid}|{st.get("what") or ""}',
                "bill": bid, "year": year, "video_id": vid,
                "committee": st.get("committee") or "",
                "date": st.get("when") or "",
                "proceeding": st.get("what") or "",
                "title": st.get("title") or "",
                # Nothing published to judge; the schedule, only to start the
                # player somewhere near. The number under test -- the stated
                # boundary plus an hour -- is deliberately not shown, so the
                # stopwatch is not anchored on it.
                "start": None, "end": None,
                "scheduled": st.get("predicted"),
                "short_by": round(dur - last),
            })
    return out


def show_late(it):
    def sec(x):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return None
    sched = sec(it.get("scheduled"))
    open_at = max(0, (sched or 0) - 300)
    rows = [
        ("Bill", f'{E(it["bill"])} <span class="dim">({E(it.get("year") or "")})</span>'),
        ("Proceeding", f'{E(it["proceeding"])} &middot; {E(it["committee"])}'
                       f' &middot; {E(it["date"])}'),
        ("Recording", f'<a href="{E(_yt(it["video_id"]))}" target="_blank" '
                      f'rel="noopener">{E(it["title"] or it["video_id"])}</a>'),
        ("Why it is here", '<span class="dim">this recording\'s captions stop '
                           f'{E(_hms(it.get("short_by")))} before the video does '
                           '&mdash; an hour behind it &mdash; so the site prints '
                           'no time for it. Nothing published is being judged: '
                           'you are finding the time.</span>'),
        ("The schedule", f'<span class="dim">{E(_hms(sched))} &mdash; when the '
                         'meeting was called for. The player opens five minutes '
                         'before it.</span>' if sched is not None else
                         '<span class="dim">none</span>'),
    ]
    body = "".join(f'<tr><th>{E(k)}</th><td>{v}</td></tr>' for k, v in rows)
    player = (f'<div class="player"><div id="ytplayer"></div></div>'
              f'<div id="ytdata" data-video="{E(it["video_id"])}" '
              f'data-start="{open_at}" data-end=""></div>')
    controls = (
        '<p class="jump">'
        '<button type="button" class="btn" data-seek="start">'
        f'Play from {E(_hms(open_at))}</button>'
        '<button type="button" class="btn grab" data-grab="observed_start">'
        'Use what is playing as the start</button>'
        '<button type="button" class="btn grab" data-grab="observed_end">'
        'Use what is playing as the end</button>'
        f'<a class="btn" href="{E(_yt(it["video_id"], open_at))}" target="_blank" '
        'rel="noopener">Open on YouTube</a></p>')
    return (f'<table class="facts">{body}</table>{player}{controls}'
            '<p class="ask">Find where the chair opens this bill, press <b>Use '
            'what is playing as the start</b>, and the same where they close it. '
            'Go by the sound: the captions on this recording are an hour out.</p>')


def sample_narratives():
    """A bill's plain-language history, beside the docket it was built from."""
    p = Path("narratives.json")
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for term, bills in d.items():
        if not isinstance(bills, dict):
            continue
        for bid, rec in bills.items():
            text = (rec or {}).get("narrative") or ""
            if len(text.split()) < 25:
                continue
            out.append({"key": f"{term}/{bid}", "term": term, "bill": bid,
                        "narrative": text})
    return out


def sample_older():
    """A published timing on a recording from before 2025.

    Every stopwatch reading this project has -- 35 in ground_truth.csv and
    the bench's own -- is of a 2025 or 2026 recording, so the boundaries
    published for 2021-2024 have never been scored, and the 2020-2022
    recordings being matched now cannot be. These are the same items the
    "Bill hearing timings" pool draws, restricted to the older years.
    """
    return [it for it in pool_for("timestamp")
            if (it.get("date") or "9999")[:4] < "2025"]


def sample_archive():
    """A history of 1989-2016, beside the docket rows it was written from.

    Those terms had no history at all until 11 September, when a vocabulary
    for the older dockets was written: 24% of their lines were recognised
    before it and 85% after. Every check run on it so far is internal -- it
    catches a page contradicting itself, not a sentence that reads well and
    says something the docket does not.
    """
    return [it for it in sample_narratives() if it["term"] <= "2015-2016"]


def _docket_lines(term, bill):
    """The raw rows the narrative was written from, so the two can be read
    against each other. This is the whole point: a narrative that reads well
    and says something the docket does not is the failure worth catching."""
    # THE RIGHT TERM'S DOCKET, OR NONE. Falling back to Docket.txt showed an
    # archived bill beside the CURRENT term's rows of the same number --
    # HB171 of 1993 against HB171 of 2026 -- which is a reviewer being asked
    # to check a narrative against another bill. The database's own file is
    # named Docket_db_<term>.txt and was never looked for at all, so every
    # bill of 1989-2014 showed "no docket rows".
    for name in (f"Docket_{term}.txt", f"Docket_db_{term}.txt"):
        p = Path(name)
        if not p.exists():
            continue
        got = []
        for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            f = line.split("|")
            if len(f) >= 7 and f[3].strip().upper() == bill.upper():
                got.append(f"{f[2].split()[0]}  {f[4]}  {f[5]}")
        if got:
            return got
    return []


def sample_topics():
    """A topic this project assigned, for a bill the General Court never
    labelled.

    47 topics exist and the General Court's own assignment reaches one term:
    2,221 bills of 2025-2026. topics.py learns from those and answers for the
    other 29,449, or says Miscellaneous where it cannot.

    Scored against a held-out half of the labelled term it is right 60.9% of
    the time overall and 74.2% of the time on the bills it is confident enough
    to place at all -- which is a measurement against the General Court's
    labelling, not against whether a reader would agree with it. That second
    question is this kind's whole purpose.

    Newest terms first, because that is where the committee still exists and
    so where the answers are strongest, and because those are the bills a
    reader is likeliest to be looking for.
    """
    p = Path("topics_assigned.json")
    if not p.exists():
        return []
    assigned = json.loads(p.read_text(encoding="utf-8"))
    bills = json.loads(Path("data/bills.json").read_text(encoding="utf-8"))
    out = []
    for term in sorted(assigned, reverse=True):
        for bill, got in assigned[term].items():
            rec = bills.get(term, {}).get(bill) or {}
            out.append({
                "key": f"topic|{term}|{bill}",
                "kind": "topic",
                "term": term,
                "bill": bill,
                "title": rec.get("title") or "",
                "committee": (rec.get("house_committee")
                              or rec.get("senate_committee") or ""),
                "topic": got.get("subject") or "",
                "margin": got.get("margin"),
                "why": got.get("why") or [],
            })
    return out


def show_topics(it):
    why = ", ".join(str(w).replace("CMTE:", "the committee ").replace("_", " ")
                    for w in it["why"])
    misc = it["topic"] == "Miscellaneous"
    verdict_hint = (
        "This one it declined to place. Is that right -- is there really no "
        "good topic for it -- or is there an obvious one it missed?"
        if misc else
        "Is that the topic a reader looking for this bill would expect? A "
        "defensible second choice still counts as right; a topic that would "
        "send someone to the wrong list does not.")
    return (f'<table class="facts">'
            f'<tr><th>Bill</th><td>{E(it["bill"])} &middot; {E(it["term"])}</td></tr>'
            f'<tr><th>Title</th><td>{E(it["title"])}</td></tr>'
            f'<tr><th>Committee</th><td>{E(it["committee"] or "none on record")}'
            f'</td></tr></table>'
            f'<h3>The topic this site would give it</h3>'
            f'<p class="prose"><strong>{E(it["topic"])}</strong></p>'
            + (f'<h3>Why</h3><p class="prose">{E(why)}</p>' if why else "")
            + f'<p class="note">confidence margin {E(it["margin"])}; '
              f'below 4 the answer is withheld as Miscellaneous</p>'
            f'<p class="ask">{verdict_hint}</p>')


def show_narratives(it):
    lines = _docket_lines(it["term"], it["bill"])
    raw = ("".join(f"<li>{E(x)}</li>" for x in lines) if lines
           else "<li>No docket rows found for this bill on this disk.</li>")
    return (f'<table class="facts"><tr><th>Bill</th><td>{E(it["bill"])} '
            f'&middot; {E(it["term"])}</td></tr></table>'
            f'<h3>The narrative as published</h3>'
            f'<p class="prose">{E(it["narrative"])}</p>'
            f'<h3>The docket it was built from</h3>'
            f'<ul class="raw">{raw}</ul>'
            '<p class="ask">Does the narrative say what the docket says, in the '
            'right order, without adding anything? A sentence in the wrong '
            'tense counts as wrong.</p>')


def sample_hearings():
    """A hearing read out of a calendar: bill, committee, day, time, room."""
    try:
        import calendar_meetings as CM
    except ImportError:
        return []
    # load() walks one chamber's calendars; parse() is per file and takes the
    # text. Both chambers, because a Senate hearing is as worth checking as a
    # House one and the Senate parse is the newer of the two.
    rows = []
    for chamber in ("H", "S"):
        try:
            rows += CM.load(chamber)
        except Exception:                                   # noqa: BLE001
            pass
    out = []
    for r in rows if isinstance(rows, list) else []:
        if not r.get("bill"):
            continue
        out.append({"key": f'{r.get("bill")}|{r.get("date")}|{r.get("kind")}',
                    "bill": r["bill"], "date": r.get("date") or "",
                    "committee": r.get("committee") or "",
                    "time": r.get("time") or "", "room": r.get("room")
                    or r.get("venue") or "", "kind": r.get("kind") or "",
                    "calendar": r.get("calendar") or ""})
    return out


def show_hearings(it):
    rows = [("Bill", it["bill"]), ("Committee", it["committee"]),
            ("Date", it["date"]), ("Time", it["time"] or "not stated"),
            ("Room", it["room"] or "not stated"),
            ("Kind", it["kind"]), ("From calendar", it["calendar"])]
    body = "".join(f"<tr><th>{E(k)}</th><td>{E(v)}</td></tr>" for k, v in rows)
    return (f'<table class="facts">{body}</table>'
            '<p class="ask">This was read out of a printed calendar. Does it '
            'match what the calendar says? Correct anything that is wrong.</p>')


def sample_vetoes():
    p = Path("veto_messages.json")
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for term, bills in d.items():
        if not isinstance(bills, dict):
            continue
        for bid, rec in bills.items():
            if not isinstance(rec, dict):
                continue
            out.append({"key": f"{term}/{bid}", "term": term, "bill": bid,
                        "text": " ".join(rec.get("text") or []),
                        "governor": rec.get("governor") or "",
                        "date": rec.get("date") or "",
                        "source": (rec.get("source") or {}).get("name") or "",
                        "url": (rec.get("source") or {}).get("url") or ""})
    return out


def show_vetoes(it):
    cite = (f'<a href="{E(it["url"])}" target="_blank" rel="noopener">'
            f'{E(it["source"])}</a>' if it["url"] else E(it["source"]))
    return (f'<table class="facts">'
            f'<tr><th>Bill</th><td>{E(it["bill"])} &middot; {E(it["term"])}</td></tr>'
            f'<tr><th>Attributed to</th><td>{E(it["governor"])}</td></tr>'
            f'<tr><th>Dated</th><td>{E(it["date"])}</td></tr>'
            f'<tr><th>Cited to</th><td>{cite}</td></tr></table>'
            f'<h3>The message as published</h3>'
            f'<p class="prose">{E(it["text"])}</p>'
            '<p class="ask">Open the calendar and read it there. Is this the '
            'whole message, is it the right Governor, and does it start and '
            'end where the calendar does?</p>')


def sample_reports():
    p = Path("committee_reports.json")
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for term, bills in d.items():
        if not isinstance(bills, dict):
            continue
        for bid, entries in bills.items():
            for e in (entries if isinstance(entries, list) else [entries]):
                for r in ((e or {}).get("reports") or []):
                    txt = r.get("text") or ""
                    if len(txt.split()) < 25:
                        continue
                    side = r.get("side") or ""
                    out.append({
                        "key": f'{term}/{bid}/{side}',
                        "term": term, "bill": bid, "text": txt,
                        "signer": r.get("author") or "",
                        "committee": r.get("committee") or "",
                        "rec": " ".join(x for x in (
                            side,
                            (e or {}).get(f"{side.lower()}_recommendation") or "",
                            (f'vote {r.get("vote_yeas")}-{r.get("vote_nays")}'
                             if r.get("vote_yeas") else "")) if x)})
    return out


def show_reports(it):
    return (f'<table class="facts">'
            f'<tr><th>Bill</th><td>{E(it["bill"])} &middot; {E(it["term"])}</td></tr>'
            f'<tr><th>Written by</th><td>{E(it["signer"]) or "not recorded"}</td></tr>'
            f'<tr><th>Committee</th><td>{E(it.get("committee"))}</td></tr>'
            f'<tr><th>Report</th><td>{E(it["rec"]) or "not recorded"}</td></tr>'
            f'</table><h3>The reasoning as published</h3>'
            f'<p class="prose">{E(it["text"])}</p>'
            '<p class="ask">Is this one member\'s reasoning, whole, with no '
            'page headers or another section\'s text inside it, and attributed '
            'to the right person?</p>')


# Each kind: where the samples come from, how to show one, and what to ask.
# A field is (name, label, placeholder).
KINDS = {
    "topic": {
        "label": "Topics for bills that never had one",
        "blurb": "The General Court assigned topics to one term out of "
                 "nineteen. topics.py learns from those 2,221 bills and "
                 "answers for the other 29,449, or says Miscellaneous where "
                 "it cannot. It is right 74% of the time on the ones it "
                 "places, scored against the General Court's own labels -- "
                 "what that score cannot say is whether the answers are ones "
                 "a reader would accept. Newest terms first.",
        "sample": sample_topics, "show": show_topics,
        "fields": [("better_topic", "A better topic, if this one is wrong",
                    "Elections"),
                   ("note", "Anything else worth recording", "")],
        # "Right" here means defensible, not identical to what the General
        # Court would have said -- there is no General Court answer for these
        # bills, which is the entire reason the topic is being guessed.
        "verdicts": [("correct", "Defensible"), ("wrong", "Wrong topic"),
                     ("unsure", "Cannot tell")],
    },
    "timestamp": {
        "label": "Bill hearing timings",
        # No HTML entities here: the template escapes a blurb, so "&mdash;"
        # reached the page as those eight characters.
        "blurb": "The moment the site says a bill was taken up, against the "
                 "recording. The time the page actually prints, not the "
                 "schedule behind it. This is what ground_truth.csv "
                 "measures, and there are 35 of those against 6,279 "
                 "published boundaries.",
        "sample": sample_timestamps, "show": show_timestamps,
        "fields": [("observed_start", "The real start", "1:10:01 or 4201"),
                   ("observed_end", "The real end", "1:24:30 or 5070")],
    },
    "late": {
        "label": "Hour-late recordings (time withheld)",
        "blurb": "Nine recordings whose captions run an hour behind the video, "
                 "so the site prints no time for them. Time where the chair "
                 "opens each bill; enough of these decide whether an hour's "
                 "shift can put 76 starts back.",
        "sample": sample_late, "show": show_late,
        "fields": [("observed_start", "The real start", "1:17:48 or 4668"),
                   ("observed_end", "The real end", "1:58:29 or 7109")],
        # Nothing is published to be right or wrong, so the verdict is only
        # whether it could be timed.
        "verdicts": [("timed", "Timed it"), ("unsure", "Cannot tell")],
    },
    "older": {
        "label": "Timings before 2025",
        "blurb": "The same judgment as the hearing timings, on recordings of "
                 "2020-2024. Every timed reading this project has is of a "
                 "2025 or 2026 recording, so nothing older has ever been "
                 "scored. Six or ten of these make the older years "
                 "measurable.",
        "sample": sample_older, "show": show_timestamps,
        "fields": [("observed_start", "The real start", "1:10:01 or 4201"),
                   ("observed_end", "The real end", "1:24:30 or 5070")],
    },
    "archive": {
        "label": "Histories of 1989-2016",
        "blurb": "The histories written on 11 September for the terms that "
                 "had none, beside the docket rows they were built from. "
                 "Does the sentence say what the docket says, in the right "
                 "order, without adding anything?",
        "sample": sample_archive, "show": show_narratives,
        "fields": [("wrong_sentence", "A sentence that is wrong, if one is",
                    "paste it")],
    },
    "narrative": {
        "label": "Plain-language histories",
        "blurb": "The sentences the site writes about a bill, against the "
                 "docket rows they were built from.",
        "sample": sample_narratives, "show": show_narratives,
        "fields": [("wrong_sentence", "A sentence that is wrong, if one is",
                    "paste it")],
    },
    "hearing": {
        "label": "Hearings read from calendars",
        "blurb": "61,429 bill-days parsed out of printed calendars back to "
                 "1997. Kind agrees with the docket 98% and room 100%, but "
                 "the docket only covers a fraction of them.",
        "sample": sample_hearings, "show": show_hearings,
        "fields": [("real_time", "The right time, if this one is wrong", "10:00 am"),
                   ("real_room", "The right room, if this one is wrong", "LOB 302")],
    },
    "veto": {
        "label": "Governors' veto messages",
        "blurb": "175 messages quoted from the calendars, each cited to the "
                 "calendar it was printed in.",
        "sample": sample_vetoes, "show": show_vetoes,
        "fields": [("missing_text", "Anything cut off the start or end",
                    "the first or last words that should be there")],
    },
    "report": {
        "label": "Committee report reasoning",
        "blurb": "A member's own explanation of a committee's recommendation, "
                 "lifted out of the calendar.",
        "sample": sample_reports, "show": show_reports,
        "fields": [("real_signer", "The right member, if this one is wrong",
                    "Rep. Jane Smith")],
    },
}


def pool_for(kind, refresh=False):
    """The samples of one kind, cached on disk.

    THE HEARINGS SAMPLER READS 2,564 CALENDARS. It produced 97,158 rows and
    took long enough that the first request for that kind timed out before a
    page was drawn -- and it would have done it again on every restart. The
    pool is a derived list, not a judgment, so caching it costs nothing and
    --refresh rebuilds it when the underlying data has moved.
    """
    OUT.mkdir(exist_ok=True)
    cache = OUT / f".pool-{kind}.json"
    if not refresh and cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            pass
    items = KINDS[kind]["sample"]()
    cache.write_text(json.dumps(items), encoding="utf-8")
    return items


# ---------------------------------------------------------------- the page

PAGE = """<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Granite Record &mdash; the bench</title>
<style>
:root{--ink:#22251f;--ink-2:#5c6156;--paper:#f5f4ef;--card:#fff;--rule:#dcdbd2;
 --pine:#2f5d47;--pine-soft:#e6efe9;--rust:#8c3a2b}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
 font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{background:var(--card);border-bottom:1px solid var(--rule);padding:14px 20px}
.wrap{max-width:820px;margin:0 auto;padding:20px}
h1{font-size:17px;margin:0 0 4px}
h3{font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink-2);
 margin:22px 0 6px}
.sub{color:var(--ink-2);font-size:13px;margin:0}
select,input,textarea,button{font:inherit}
select{padding:6px 8px;border:1px solid var(--rule);border-radius:6px;background:#fff}
.card{background:var(--card);border:1px solid var(--rule);border-radius:10px;
 padding:20px;margin:18px 0}
table.facts{border-collapse:collapse;width:100%;margin:0 0 12px}
table.facts th{text-align:left;color:var(--ink-2);font-weight:600;font-size:12px;
 letter-spacing:.04em;text-transform:uppercase;padding:5px 12px 5px 0;
 white-space:nowrap;vertical-align:top;width:1%}
table.facts td{padding:5px 0;vertical-align:top}
.prose{background:var(--paper);border-left:3px solid var(--rule);padding:12px 14px;
 border-radius:0 6px 6px 0;font-size:15px;line-height:1.65;white-space:pre-wrap}
ul.raw{font-size:13px;color:var(--ink-2);background:var(--paper);padding:12px 14px 12px 30px;
 border-radius:6px;max-height:260px;overflow:auto;margin:0}
ul.raw li{margin:0 0 3px}
.ask{color:var(--ink-2);font-size:14px;margin:14px 0 0}
.jump{margin:12px 0 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.player{margin:14px 0 0;background:#000;border-radius:8px;overflow:hidden;
 aspect-ratio:16/9}
.player iframe,.player>div{width:100%;height:100%;border:0;display:block}
b.t{font-variant-numeric:tabular-nums;font-size:16px}
.dim{color:var(--ink-2);font-weight:400}
.btn.grab{background:#fff;border-color:var(--rule);color:var(--ink)}
.btn.grab:hover{border-color:var(--pine);color:var(--pine)}
button.btn{cursor:pointer}
.btn{display:inline-block;background:var(--pine-soft);color:var(--pine);
 border:1px solid var(--pine-soft);border-radius:6px;padding:7px 12px;
 text-decoration:none;font-size:14px;margin:0 6px 6px 0}
label.f{display:block;margin:12px 0 0;font-size:13px;color:var(--ink-2)}
label.f input,label.f textarea{width:100%;margin-top:4px;padding:8px 10px;
 border:1px solid var(--rule);border-radius:6px;background:#fff}
textarea{min-height:74px;resize:vertical}
.verdicts{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 0}
.verdicts label{border:1px solid var(--rule);border-radius:999px;padding:7px 14px;
 background:#fff;cursor:pointer;font-size:14px}
.verdicts input{margin-right:6px}
.actions{display:flex;gap:10px;margin:20px 0 0;flex-wrap:wrap}
button{padding:10px 18px;border-radius:8px;border:1px solid var(--pine);
 background:var(--pine);color:#fff;cursor:pointer;font-size:15px}
button.ghost{background:#fff;color:var(--ink-2);border-color:var(--rule)}
.count{color:var(--ink-2);font-size:13px}
.empty{color:var(--ink-2)}
.saved{background:var(--pine-soft);color:var(--pine);border-radius:6px;
 padding:8px 12px;font-size:14px;margin:0 0 12px}
</style>
<script>
// THE RECORDING IN THE PAGE. Loaded only when a sample has one, so the other
// four kinds do not fetch YouTube's player to show a paragraph of prose.
// AFTER THE DOCUMENT, not with it. This sat in the head and ran before the
// body existed, so getElementById("ytdata") was null every time and the whole
// function returned without building a player -- silently, which is why the
// page looked finished and had no video in it.
document.addEventListener("DOMContentLoaded", function(){
  var d = document.getElementById("ytdata");
  if(!d) return;
  var player = null, ready = false;
  window.onYouTubeIframeAPIReady = function(){
    player = new YT.Player("ytplayer", {
      videoId: d.dataset.video,
      playerVars: {start: parseInt(d.dataset.start || "0", 10), rel: 0},
      events: {onReady: function(){ ready = true; }}
    });
  };
  var s = document.createElement("script");
  s.src = "https://www.youtube.com/iframe_api";
  document.head.appendChild(s);

  function hms(x){
    x = Math.max(0, Math.round(x));
    var h = Math.floor(x/3600), m = Math.floor((x%3600)/60), s2 = x%60;
    return h + ":" + String(m).padStart(2,"0") + ":" + String(s2).padStart(2,"0");
  }
  document.addEventListener("click", function(e){
    var seek = e.target.closest("[data-seek]");
    if(seek && ready){
      var to = seek.dataset.seek === "end" ? d.dataset.end : d.dataset.start;
      if(to !== ""){ player.seekTo(parseInt(to,10), true); player.playVideo(); }
      return;
    }
    // WHAT IS PLAYING, NOT WHAT WAS TYPED. Reading a time off the player and
    // retyping it is where a digit gets dropped, and this is a file measured
    // in seconds.
    var grab = e.target.closest("[data-grab]");
    if(grab && ready){
      var f = document.querySelector('[name="' + grab.dataset.grab + '"]');
      if(f){ f.value = hms(player.getCurrentTime()); f.focus(); }
    }
  });
});
</script>
<header><div class="wrap" style="padding:0">
<h1>The bench</h1>
<p class="sub">One sample at a time, judged by a person, written to
review/checked.jsonl and never overwritten. Local only.</p>
</div></header>
<div class="wrap">
<form method="get" action="/" style="margin:0 0 6px">
  <label class="count">Checking:
  <select name="kind" onchange="this.form.submit()">__OPTIONS__</select></label>
</form>
<p class="count">__BLURB__</p>
<p class="count"><b>__DONE__</b> judged &middot; __LEFT__ not yet looked at</p>
__SAVED__
<div class="card">__ITEM__</div>
</div>
"""


def form_html(kind, item):
    k = KINDS[kind]
    fields = "".join(
        f'<label class="f">{E(lab)}'
        f'<input name="{E(nm)}" placeholder="{E(ph)}" autocomplete="off"></label>'
        for nm, lab, ph in k["fields"])
    return (
        f'<form method="post" action="/save">'
        f'<input type="hidden" name="kind" value="{E(kind)}">'
        f'<input type="hidden" name="key" value="{E(item["key"])}">'
        f'<input type="hidden" name="shown" value="{E(json.dumps(item))}">'
        + k["show"](item)
        + '<div class="verdicts">'
        + "".join(f'<label><input type="radio" name="verdict" value="{E(v)}"'
                  f'{" checked" if i == 0 else ""}>{E(lab)}</label>'
                  for i, (v, lab) in enumerate(k.get("verdicts") or [
                      ("correct", "Correct as published"), ("wrong", "Wrong"),
                      ("unsure", "Cannot tell")]))
        + '</div>'
        + fields
        + '<label class="f">Notes'
          '<textarea name="note" placeholder="Anything worth saying about this '
          'one. What you write here is read by a person, not parsed."></textarea>'
          '</label>'
        + '<div class="actions">'
          '<button type="submit" name="action" value="save">Save and next</button>'
          '<button type="submit" name="action" value="skip" class="ghost">'
          'Skip &mdash; I cannot identify this one</button>'
          '</div></form>')


class Bench(BaseHTTPRequestHandler):
    pool = {}

    def log_message(self, *a):
        pass

    def _send(self, body, code=200, ctype="text/html; charset=utf-8"):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        kind = (q.get("kind") or ["timestamp"])[0]
        if kind not in KINDS:
            kind = "timestamp"
        saved = "<p class=\"saved\">Saved.</p>" if q.get("saved") else ""
        self._send(self.render(kind, saved))

    def render(self, kind, saved=""):
        k = KINDS[kind]
        if kind not in self.pool:
            self.pool[kind] = pool_for(kind)
        items = self.pool[kind]
        seen = judged()
        done = [key for (kd, key) in seen if kd == kind]
        left = [it for it in items if (kind, it["key"]) not in seen]
        opts = "".join(
            f'<option value="{E(n)}"{" selected" if n == kind else ""}>'
            f'{E(v["label"])}</option>' for n, v in KINDS.items())
        if not items:
            body = ('<p class="empty">Nothing to judge here yet. This kind '
                    'reads a file that is not built on this disk.</p>')
        elif not left:
            body = ('<p class="empty">Every sample of this kind has been '
                    'judged. Pick another, or look at review/checked.jsonl.</p>')
        else:
            body = form_html(kind, random.choice(left))
        return (PAGE.replace("__OPTIONS__", opts)
                    .replace("__BLURB__", E(k["blurb"]))
                    .replace("__DONE__", f"{len(done):,}")
                    .replace("__LEFT__", f"{len(left):,}")
                    .replace("__SAVED__", saved)
                    .replace("__ITEM__", body))

    def do_POST(self):
        from urllib.parse import parse_qs
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode("utf-8"))
        g = lambda f, d="": (form.get(f) or [d])[0]
        kind = g("kind", "timestamp")
        if kind not in KINDS:
            self._send("unknown kind", 400, "text/plain")
            return
        action = g("action", "save")
        entry = {"kind": kind, "key": g("key"),
                 "verdict": "skipped" if action == "skip" else g("verdict"),
                 "note": g("note"), "by": "hand"}
        for nm, _, _ in KINDS[kind]["fields"]:
            v = g(nm).strip()
            if v:
                entry.setdefault("fields", {})[nm] = v
        try:
            entry["shown"] = json.loads(g("shown") or "{}")
        except ValueError:
            entry["shown"] = {}
        record(entry)
        self.send_response(303)
        self.send_header("Location", f"/?kind={kind}&saved=1")
        self.end_headers()


def report():
    seen = judged()
    if not seen:
        print("review/checked.jsonl is empty. Nothing has been judged yet.")
        return 0
    from collections import Counter
    per = Counter()
    verd = Counter()
    for (kind, key), entries in seen.items():
        per[kind] += 1
        verd[(kind, entries[-1].get("verdict"))] += 1
    print(f"{sum(per.values()):,} items judged, "
          f"{sum(len(v) for v in seen.values()):,} judgments in total")
    for kind in KINDS:
        if not per[kind]:
            continue
        bits = ", ".join(f"{v} {w}" for (k, w), v in sorted(verd.items())
                         if k == kind)
        print(f"  {KINDS[kind]['label']:32} {per[kind]:5,}   {bits}")

    # WHICH TIMESTAMP VERDICTS WERE GRADED AGAINST THE WRONG NUMBER. Until
    # 9 September this bench showed proceedings.csv's predicted_offset, which
    # is the schedule -- the meeting was called for 09:00 and the stream began
    # at 08:54:21, so 5:39 -- and not the time the page prints. Nine items
    # were judged against it. HB1118 was marked wrong at 5:39 when the page
    # says 58:07 and the person's own stopwatch said 58:06.
    #
    # The ledger is append-only and nothing rewrites it, so the entries stay
    # exactly as they were entered. What can be done is say so every time
    # anybody reads it: an entry whose "shown" carries no published start was
    # graded against the schedule, and its VERDICT means nothing. The
    # observed times in it are a person's own stopwatch and are as good as
    # any other.
    stale = [e for (kind, key), entries in seen.items() if kind == "timestamp"
             for e in entries if (e.get("shown") or {}).get("start") is None]
    if stale:
        obs = sum(1 for e in stale
                  if (e.get("fields") or {}).get("observed_start"))
        print()
        print(f"  {len(stale)} timestamp judgment(s) were graded against the "
              "SCHEDULE, not the published time.")
        print("  Their verdict column cannot be used. The hand-timed values "
              f"in them can: {obs} carry an observed start.")
        for e in stale:
            s = e.get("shown") or {}
            f = e.get("fields") or {}
            print(f"    {s.get('bill', '?'):9} {s.get('proceeding', ''):26} "
                  f"observed {f.get('observed_start') or '-'}"
                  f" to {f.get('observed_end') or '-'}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--report", action="store_true",
                    help="what has been judged, and stop")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="rebuild the sample pools from the data on disk")
    a = ap.parse_args()
    if a.report:
        return report()

    OUT.mkdir(exist_ok=True)
    # WARMED BEFORE THE FIRST REQUEST, not during it. Building a pool inside a
    # request meant the browser waited on it, and the hearings pool takes long
    # enough to time out.
    for name in KINDS:
        t0 = time.time()
        items = pool_for(name, refresh=a.refresh)
        Bench.pool[name] = items
        took = time.time() - t0
        print(f"  {KINDS[name]['label']:32} {len(items):7,}"
              + (f"  ({took:.0f}s)" if took > 2 else ""))
    # 127.0.0.1 AND NOT 0.0.0.0. This shows unpublished judgments and writes a
    # file the site is measured against; it has no business on a network.
    srv = HTTPServer(("127.0.0.1", a.port), Bench)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"the bench is at {url}")
    print(f"  writing to {LEDGER} (append only)")
    print("  ctrl-c to stop")
    if not a.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
