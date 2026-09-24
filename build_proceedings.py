#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.8
"""
Build proceedings.csv: one row per (bill, date, kind, recording), whether it
is a committee hearing or a floor debate.

    python3 build_proceedings.py

Reads every verification_manifest*.csv -- one per term, from build_manifest.py:
the committee proceedings read from the docket and, for a term built with
--calendar, the meetings only a calendar announced -- and floor_index.json
(floor debates, from build_floor_index.py), and writes one table in one shape.
The producers stay as they are for now; this is the file everything
downstream reads. Once every reader has moved, the producers can be merged
too.

Why: the two sources have different shapes and keys, and every tool that read
one had to be separately taught the other. Five times in one day a tool
silently excluded the floor. This is the fix for the cause rather than for
the fifth instance.

What it refuses: to write a smaller table than last time without being told
it may. A rebuild that halves the proceedings is a rebuild that lost a source.
The same goes for one term's rows from one source, because the table holds
every term and a whole term can leave it while the total barely moves.

EVERY ROW LEAVES HERE WITH A TERM, or is dropped and counted. build_site_v2
keys every per-bill payload on (term, bill), so a row whose term is empty is
a proceeding this table holds and no page on the site can show -- invisible
in both directions, since nothing errors either. Ten rows of 98,965 were in
that state, which was the whole of the site's proceedings gap. See
recover_terms for where a missing term is found and what happens to a row
that has none to find.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import proceedings as P


def as_seconds(v):
    """'1:23:45' or '83:45' or '5025' -> seconds, else None."""
    if v in (None, ""):
        return None
    s = str(v).strip()
    try:
        return float(s)
    except ValueError:
        pass
    try:
        parts = [float(x) for x in s.split(":")]
    except ValueError:
        return None
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def manifest_paths(patterns):
    """Every manifest named or matched, in a stable order, without repeats.

    ONE PER TERM, AND THE TABLE BUILT WHOLE FROM ALL OF THEM. build_manifest
    writes one manifest per docket it is given, so 2023-2024 lands beside
    2025-2026 rather than on top of it. The alternative was a --term flag
    here that rebuilt one term's rows inside a file holding every term, and
    that is a writer running on a subset of what it rewrites -- which is how
    the manifest lost the 35 hand-marked times, and how segment_markers
    --transcript once discarded 842 recordings' results. Reading all of them
    every time means no writer here ever sees a subset, and the shrink guard
    below goes on comparing whole tables.
    """
    out, seen = [], set()
    for pat in patterns:
        hits = (sorted(Path(".").glob(pat))
                if any(c in pat for c in "*?[") else [Path(pat)])
        for f in hits:
            k = f.resolve()
            if f.exists() and k not in seen:
                seen.add(k)
                out.append(f)
    return out


def term_in_name(path):
    """'verification_manifest_2023-2024.csv' -> '2023-2024', else ''.

    A manifest is one term's and says so in its name: build_manifest refuses
    to write an archived term's docket to plain verification_manifest.csv
    precisely so that this stays true. So a row in it whose sched_date is
    empty still has a term, and it is this one -- the file it came out of.
    Nothing needs it today (all ten of the termless rows were the floor
    index's, and the current term's manifest has no term in its name to
    take), which is why the count below prints only when it is not zero.
    """
    m = re.search(r"(\d{4}-\d{4})", Path(path).stem)
    return m.group(1) if m else ""


def from_manifest(path):
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            bill = (r.get("bill") or "").strip().upper()
            if not bill:
                continue
            date = (r.get("sched_date") or "")[:10]
            rows.append({
                "term": P.term_of(date), "bill": bill,
                "body": (r.get("body") or "").strip(),
                "kind": (r.get("proceeding") or "").strip().lower(),
                "date": date, "time": (r.get("sched_time") or "").strip(),
                "committee": (r.get("committee") or "").strip(),
                "venue": (r.get("venue") or "").strip(),
                "video_id": (r.get("video_id") or "").strip(),
                "video_title": (r.get("video_title") or "").strip(),
                "stream_start": (r.get("stream_start") or "").strip(),
                "predicted_offset": as_seconds(r.get("predicted_offset")),
                "match": (r.get("match") or "").strip(),
                # WHICH RECORDINGS THIS SITTING COULD BE, when the matcher
                # would not name one. build_manifest writes every candidate's
                # id whenever more than one recording of that committee exists
                # on the day, and 563 of the 100,556 events here carry them.
                # On 317 video_id is empty because no pick was made -- 236
                # Finance, whose divisions stream separately and which the
                # docket does not tell apart, and 81 the clock could not
                # separate -- and those 317 are the rows build_site_v2 filed
                # as "novideo" and app.js drew as "No recording matched to
                # this proceeding.", over a committee that was filmed.
                #
                # The ids and not the manifest's `candidates` titles: a title
                # is for a person reading the manifest, an id is a link.
                "candidate_ids": (r.get("candidate_ids") or "").strip(),
                "debate_end": None, "window_start": None, "precise": False,
                "motions": [], "tallies": [], "whole_video": False,
                # A manifest row is the docket's unless build_manifest
                # --calendar wrote it from a calendar's notice. A manifest
                # with no source column predates calendar rows, and every
                # row in it is the docket's.
                "source": ("calendar"
                           if (r.get("source") or "").strip() == "calendar"
                           else "docket"),
                "calendar": (r.get("calendar") or "").strip(),
                "noticed": (r.get("noticed") or "").strip(),
                "committee_from": (r.get("committee_from") or "").strip(),
                "notice_times": (r.get("notice_times") or "").strip(),
            })
    return rows


def from_floor_index(path):
    p = Path(path)
    if not p.exists():
        return []
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    rows = []
    for bill, entries in (doc.items() if isinstance(doc, dict) else []):
        b = str(bill).strip().upper()
        for e in (entries if isinstance(entries, list) else [entries]):
            if not isinstance(e, dict):
                continue
            date = str(e.get("date") or "")[:10]
            kind = str(e.get("kind") or "floor debate").strip().lower()
            if kind not in P.FLOOR_KINDS:
                # A recording whose title names a bill is not automatically a
                # floor debate. Five of them are committee work sessions and a
                # study committee -- "House Health, Human Services and Elderly
                # Affairs Work Session on HB 54" was on the site as a floor
                # debate. The title says what it is, so read it.
                title = str(e.get("title") or "").lower()
                if "conference" in kind or "conference" in title:
                    kind = "committee of conference"
                elif "work session" in title:
                    kind = "work session"
                elif "committee to study" in title or "study committee" in title:
                    kind = "study committee"
                elif "executive session" in title:
                    kind = "executive session"
                elif "subcommittee" in title:
                    kind = "subcommittee work session"
                else:
                    kind = "floor debate"
            rows.append({
                "term": P.term_of(date), "bill": b,
                "body": str(e.get("body") or ""),
                "kind": kind, "date": date, "time": "",
                "committee": "", "venue": "",
                "video_id": str(e.get("video_id") or ""),
                "video_title": str(e.get("title") or ""),
                "stream_start": "",
                "predicted_offset": e.get("window_start"),
                "match": "roll call clock" if e.get("precise") else
                         ("title names the bill" if e.get("whole_video")
                          else "session that day"),
                "debate_end": e.get("debate_end"),
                "window_start": e.get("window_start"),
                "precise": bool(e.get("precise")),
                "motions": list(e.get("motions") or []),
                "tallies": list(e.get("tallies") or []),
                "whole_video": bool(e.get("whole_video")),
                "source": "floor_index",
            })
    return rows


def video_days(paths):
    """{video_id: (date, "stream"|"published")} out of the video indexes.

    Read for ONE thing: a row that arrived here with no date at all. The
    indexes parse the day out of the recording's title, and a title that
    names its bill instead of its date leaves parsed_date empty --
    "Committee of Conference, HB1, Part 2 (LOB 210-211)", "Senate Finance
    Committee HB 2 Deliberations-May 26", "REMOTE MEETING OF HB 4
    LEGISLATIVE COMMITTEE ON APPORTIONMENT". build_floor_index copies that
    empty string into the entry, and ten entries of floor_index.json carry
    it. Every one is a real recording of a real proceeding.

    TWO ANSWERS OF DIFFERENT STRENGTH, and they are not used for the same
    thing. start_eastern is the livestream's own start, so it IS the
    sitting, to the second; eight of the ten have one and it fills the date.
    published_at is when the recording went up, which is that day or the
    next: enough to name the biennium, not enough to name the day. The two
    HB1 budget conference parts are that case -- both published 2021-06-11
    at 14:5x Eastern, part 2 five minutes BEFORE part 1, so they were
    uploaded together after a sitting that may well have been the day
    before. They get the term and keep an empty date rather than a guessed
    one.
    """
    out = {}
    for p in paths:
        try:
            fh = Path(p).open(encoding="utf-8-sig", newline="")
        except OSError:
            continue
        with fh:
            for r in csv.DictReader(fh):
                vid = (r.get("video_id") or "").strip()
                if not vid or vid in out:
                    continue
                start = (r.get("start_eastern") or "").strip()
                pub = (r.get("published_at") or "").strip()
                if len(start) >= 10:
                    out[vid] = (start[:10], "stream")
                elif len(pub) >= 10:
                    out[vid] = (pub[:10], "published")
    return out


def recover_terms(rows, days):
    """Give a row with no term the one its recording was made in.

    Returns (from_stream, from_published, [rows that still have none]).

    A term comes from the date and nothing else -- P.term_of reads the year
    and rounds it down to the odd one -- so a row with no term is a row with
    no date, and a row with no date but a video_id has its date sitting in
    the video index under that id. The site keys on (term, bill), so this is
    the difference between a proceeding having a page and having nowhere at
    all to appear.

    The caller drops whatever comes back in the third slot, and says how
    many. Filtering it away in here would put the number back where it was
    found: in a one-off measurement, a year after the fact.
    """
    stream = published = 0
    for r in rows:
        if r.get("term") or not r.get("video_id"):
            continue
        day, how = days.get(r["video_id"], ("", ""))
        term = P.term_of(day)
        if not term:
            continue
        r["term"] = term
        if how == "stream":
            r["date"] = day
            stream += 1
        else:
            published += 1
    return stream, published, [r for r in rows if not r.get("term")]


def per_term_source(rows):
    """{(term, source): rows}, with a `manifest` row counted as `docket`.

    manifest is what every table written before calendar rows existed says of
    the docket's rows. The first rebuild after the rename must not read that
    as the whole docket leaving and a new source arriving.
    """
    n = Counter()
    for r in rows:
        src = (r.get("source") or "").strip()
        n[(r.get("term") or "", "docket" if src == "manifest" else src)] += 1
    return n


def shrunk_groups(prior, rows, least=100, keep=0.8):
    """[(term, source, was, now)] for every (term, source) of `prior` holding
    at least `least` rows of which `rows` keeps fewer than `keep`."""
    was, now = per_term_source(prior), per_term_source(rows)
    return [(t, s, n, now.get((t, s), 0)) for (t, s), n in sorted(was.items())
            if n >= least and now.get((t, s), 0) < keep * n]


# ---------------------------------------------------------------------------
# One row per event
# ---------------------------------------------------------------------------
#
# Kinds that name ONE proceeding under more than one word. The House docket
# writes "Public Hearing"; the Senate's and the 1989-1998 archive's write
# "Hearing"; and a House line that the House pattern cannot read -- a time
# written "9:00 a.m." rather than "09:00 am", a Zoom link after the room,
# "=RECESSED=" stuck to the end -- falls through to the archive's pattern in
# docket_parser, which calls whatever it matched a "hearing". So one sitting
# reaches this file twice, once under each word.
#
# That is where the duplicate videos came from. The docket announces a
# hearing and then restates it on the day it happens; both lines are the
# same sitting, both matched the same recording, and build_site_v2 draws one
# card per row -- so 26 bills of 2021-2022 showed the same recording under
# two hearings, on seven House committee days.
#
# ONLY the hearings are a family. The three work-session kinds are NOT: a
# subcommittee work session at 09:30 and the full committee's at 10:00 are
# two meetings that happen to share a recording, and 18 bills have exactly
# that pair. Nor are a public hearing and the executive session that follows
# it on the same tape -- 936 bills have that, and it is two events, which is
# why the kind is in the key at all.
KIND_FAMILY = {"public hearing": "hearing", "hearing": "hearing"}

# Within a family, the spelling that says most about the proceeding: 0 wins.
# The House's own word beats the fallback's, so a folded row carries the
# chamber's wording and the room as the chamber wrote it, rather than the
# "a.m. LOB205-207" the archive pattern leaves behind when it swallows the
# meridiem into the venue.
KIND_RANK = {"public hearing": 0}


def _fam(kind):
    return KIND_FAMILY.get(kind, kind)


def _cmte(name):
    return " ".join((name or "").split()).lower()


def same_committee(a, b):
    """Do these two rows name the same committee, or does one not say?

    A blank name makes no claim, so it does not contradict a row that names
    one -- four pre-1999 hearings have that pair, and a floor row names no
    committee at all. Two DIFFERENT names do contradict and the rows stay
    apart: a bill referred to two committees is heard by both, sometimes on
    the same day. Seven pre-1999 bill-days carry two names, five of them
    plainly two committees; the other two are the legacy docket's own
    shorthand for one ("En", "Crim Just and Ps"), and those now draw two
    cards rather than one. Neither has a recording, so neither is a
    duplicate video; expanding that shorthand is a separate job.
    """
    ca, cb = _cmte(a.get("committee")), _cmte(b.get("committee"))
    return not ca or not cb or ca == cb


def official_names(rows):
    """Each committee row's committee under the name it had at the time.

    The manifests carry what the docket's clerk wrote: "Exec Depts and Admin",
    "Crim Just and PSfty", "Mun and Cnty Govt" on 1999-2006's hearings, and
    "for Interim Study", a journal citation or a vote after the name on
    thousands more. build_committees matches a name exactly, so some 22,200
    rows under 656 such names reached no committee page, and House Executive
    Departments and Administration, Criminal Justice and Public Safety and
    Election Law showed no sitting at all for 1999-2004. committee_names.
    official is the one place a name is settled -- the bills' committees go
    through it too, in build_data -- and it only ever returns the row's own
    committee, spelt as that chamber spelt it that term.

    Before fold_to_events, which keys on the name: "EDUCATION VV" and
    "Education" on one bill's one sitting are one event, and after this they
    say so. Returns how many rows were renamed.
    """
    import committee_names as CN
    n = 0
    for r in rows:
        was = r.get("committee") or ""
        if was:
            now = CN.official(was, r.get("body"), r.get("term"))
            if now != was:
                r["committee"] = now
                n += 1
    return n


def _specificity(r):
    """Lower is more specific. Ties keep whichever row was read first."""
    return (KIND_RANK.get(r["kind"], 1), 0 if _cmte(r.get("committee")) else 1)


def fold_to_events(rows):
    """One row per event: this bill, this committee, this day, this kind of
    proceeding, this recording.

    NOT the time and NOT the venue. The docket's announcement and its
    restatement on the day name one sitting while spelling the room two ways
    ("LOB 205-207" against "LOB205-207") and, on three bills, giving two
    different times. Keying on either would make the pair two events again.
    Keying on the video URL alone would do the opposite and eat the executive
    session that shares the hearing's tape.

    WHAT A LEGITIMATE SECOND ROW LOOKS LIKE, and what this therefore keeps:

      * a different kind of proceeding on the same recording -- the hearing
        and the executive session that follows it;
      * a different committee on the same day -- a bill referred to two of
        them, or heard by the House's and the Senate's;
      * a different day -- a hearing continued or re-noticed;
      * a different recording on the same day -- a sitting that ran into a
        second video, which arrives here as two rows and stays two.

    Only a second spelling of one sitting is folded away.

    The row kept is the most specific one whole, never a blend of the two:
    a row here is what one line of the docket said, and a time taken from one
    line beside a room taken from another is a row the record does not
    contain. Where the two lines give two times -- three bills of 2021-2022
    -- the kept time is the announcement's, which is the time the rest of
    that sitting's rows are keyed to.
    """
    kept, where = [], defaultdict(list)
    for r in rows:
        k = (r["term"], r["bill"], r["date"], _fam(r["kind"]), r["video_id"])
        for i in where[k]:
            if same_committee(kept[i], r):
                if _specificity(r) < _specificity(kept[i]):
                    kept[i] = r
                break
        else:
            where[k].append(len(kept))
            kept.append(r)
    return kept


def main():
    ap = argparse.ArgumentParser()
    # A GLOB, NOT A FILE. verification_manifest.csv is the current term and
    # verification_manifest_2023-2024.csv is what build_manifest writes when
    # given that term's docket; both are read, and any later term's too,
    # without this default needing to change again.
    ap.add_argument("--manifest", nargs="+",
                    default=["verification_manifest*.csv"],
                    help="one or more manifests, or a pattern matching them")
    ap.add_argument("--floor", default="floor_index.json")
    # Not a source of proceedings -- a source of DATES, for the handful of
    # rows that reached here without one. See video_days.
    ap.add_argument("--videos", nargs="+", default=["videos_*.csv"],
                    help="video indexes, read only to date a row whose "
                         "source gave it no date")
    ap.add_argument("--out", default=str(P.PATH))
    ap.add_argument("--allow-shrink", action="store_true",
                    help="write even if this table, or one term's rows from "
                         "one source, is a fifth smaller than the last")
    a = ap.parse_args()

    files = manifest_paths(a.manifest)
    cm, per_file, by_filename = [], [], 0
    for f in files:
        got = from_manifest(f)
        # A row with no sched_date still belongs to the term the file is
        # named for, and that name is the only place it is written down.
        named = term_in_name(f)
        if named:
            for r in got:
                if not r["term"]:
                    r["term"] = named
                    by_filename += 1
        per_file.append((f.name, len(got)))
        cm.extend(got)
    fl = from_floor_index(a.floor)
    if not cm and not fl:
        sys.exit(f"Nothing matches {' '.join(a.manifest)} and no {a.floor} is "
                 "here. Nothing to build.")
    if not cm:
        print(f"  WARNING: nothing matches {' '.join(a.manifest)} "
              "-- no committee proceedings")
    if not fl:
        print(f"  WARNING: {a.floor} not found -- no floor debates")

    rows = cm + fl
    # EVERY ROW NEEDS A TERM. build_site_v2 keys on (term, bill), so a row
    # with an empty term reaches no page at all -- and nothing raises,
    # because the key simply never matches. A measurement on 17 September
    # found 10 such rows in 98,965, and those 10 were the whole of the gap
    # between the table and the site: 98,955 already reached a page.
    #
    # Same globbing as the manifests above, and for the same reason: read
    # every index there is rather than one, so this never runs on a subset
    # of what it is correcting.
    vfiles = manifest_paths(a.videos)
    stream, published, termless = recover_terms(rows, video_days(vfiles))
    if by_filename:
        print(f"  {by_filename:,} manifest rows had no date; took the term "
              "their manifest is named for")
    if stream or published:
        print(f"  {stream + published:,} rows had no date and so no term, and "
              f"a recording that knows it: {stream:,} took the day their "
              f"stream started, {published:,} the biennium their recording "
              "was published in (the day itself stays blank)")
    if termless:
        # DROPPED OUT LOUD. A row that reaches no page is a proceeding this
        # table holds and cannot show, and the only thing that keeps that
        # number from going quiet again is printing it on every build.
        rows = [r for r in rows if r.get("term")]
        print(f"  {len(termless):,} rows DROPPED: no date, so no term, so no "
              "page to reach"
              + ("" if vfiles else
                 f" (and nothing matches {' '.join(a.videos)} here, so no "
                 "recording could date them either)"))
        for r in termless[:10]:
            print(f"      {r['bill']:<9} {r['kind']:<26} {r['source']:<12} "
                  f"{(r['video_title'] or r['video_id'])[:44]}")
        if len(termless) > 10:
            print(f"      ... and {len(termless) - 10:,} more")
    # One name per committee, before the fold that keys on it.
    renamed = official_names(rows)
    print(f"  {renamed:,} rows' committee written as its name at the time "
          "(committee_names.official)")
    # One row per event, not per line of the sources. The floor index can
    # list a bill twice on one day when it had two runs of roll calls, and
    # the docket announces a hearing and then restates it on the day -- the
    # second of those arriving under a second spelling of "hearing", which
    # the old key on the kind's literal word could not see. See
    # fold_to_events for what counts as one event and what does not.
    uniq = fold_to_events(rows)
    folded = len(rows) - len(uniq)
    uniq.sort(key=lambda r: (r["date"], r["time"] or "~", r["bill"]))

    prior = P.load(a.out)
    if prior and len(uniq) < 0.8 * len(prior) and not a.allow_shrink:
        sys.exit(f"Refusing: {len(uniq):,} rows, but {a.out} already holds "
                 f"{len(prior):,}.\nA table that shrinks by a fifth lost a "
                 "source. Pass --allow-shrink if that is intended.")
    # ONE TERM AND ONE SOURCE AT A TIME, TOO. The guard above compares whole
    # tables, and the table holds every term: leaving
    # verification_manifest_2023-2024.csv out of a rebuild takes 6,998 docket
    # rows with it and keeps 87% of the table, so that term would have left
    # the site without a word. A term's manifest rebuilt by a parser that
    # reads less, or with its calendar rows gone, is the same loss inside one
    # term. Fewer than 100 rows is too few for a fifth to mean a lost file.
    lost = shrunk_groups(prior, uniq)
    if lost and not a.allow_shrink:
        sys.exit(f"Refusing: {len(uniq):,} rows is "
                 f"{100 * len(uniq) / len(prior):.0f}% of the {len(prior):,} "
                 f"in {a.out}, but these lose a fifth or more of their rows:\n"
                 + "\n".join(f"  {t or '(no date)'}  {s}: {was:,} rows, now "
                             f"{now:,}" for t, s, was, now in lost)
                 + "\nA term's rows from one source falling by a fifth means "
                 "a manifest or the floor index went missing, or was rebuilt "
                 "from less. Pass --allow-shrink if that is intended.")

    # THE COLUMN HAS TO BE IN proceedings.COLS OR CARRYING IT IS A NO-OP.
    # P.write emits {c: row.get(c, "") for c in COLS}, so a field this file
    # puts on a row and that list does not name is dropped without a word --
    # and the 317 sittings that know which recordings they might be would go
    # on reaching app.js as "No recording matched to this proceeding.", which
    # is the whole reason for carrying them. One line in proceedings.py, which
    # is not this file's to edit; saying so beats writing a second writer
    # beside P.write, which is how a table grows two shapes.
    unnamed = sum(1 for r in uniq if r.get("candidate_ids"))
    if unnamed and "candidate_ids" not in P.COLS:
        print(f"  WARNING: {unnamed:,} rows name the recordings their sitting "
              "could be, and proceedings.py's COLS does not list "
              "candidate_ids, so proceedings.write is about to drop every one "
              "of them.\n           Add \"candidate_ids\" to COLS in "
              "proceedings.py. Nothing else is needed.")

    P.write(uniq, a.out)

    with_video = sum(1 for r in uniq if r["video_id"])
    floor = [r for r in uniq if r["kind"] in P.FLOOR_KINDS]
    per_term = defaultdict(Counter)
    for r in uniq:
        per_term[r["term"]][r["source"]] += 1
    print(f"{len(uniq):,} proceedings -> {a.out}")
    print(f"  {len(cm):,} from {len(files)} manifest(s), "
          f"{len(fl):,} from the floor index")
    for name, n in per_file:
        print(f"      {n:>7,}  {name}")
    # A fold that folds nothing is a fold that stopped working, and the two
    # spellings of a hearing would be back on the Videos tab without a word.
    print(f"  {folded:,} second mentions of an event folded into the first")
    print(f"  {with_video:,} have a recording; "
          f"{len({r['video_id'] for r in uniq if r['video_id']}):,} distinct")
    # A number that can quietly become zero -- a manifest rebuilt by an older
    # build_manifest.py writes no candidate_ids column at all -- and the site
    # says "no recording" over a filmed sitting again with nothing in any log
    # to say when it started. 317 on 17 September, across 64 committee-days
    # and 269 bills.
    undecided = [r for r in uniq if r.get("candidate_ids") and not r["video_id"]]
    print(f"  {len(undecided):,} chose no recording but name the ones it could "
          f"be, across {len({(r['date'], r['committee']) for r in undecided}):,}"
          " committee-days")
    print(f"  {len(floor):,} floor rows, "
          f"{sum(1 for r in floor if r['precise']):,} with a roll-call end, "
          f"{sum(1 for r in floor if r['whole_video']):,} whole-video")
    print("  rows per term:")
    line = "      {:<11} {:>8}  {:>8}  {:>11}"
    print(line.format("", "docket", "calendar", "floor_index"))
    for t in sorted(per_term):
        c = per_term[t]
        print(line.format(t or "(no date)", f"{c['docket']:,}",
                          f"{c['calendar']:,}", f"{c['floor_index']:,}"))
    if prior:
        print(f"  (was {len(prior):,})")


if __name__ == "__main__":
    main()
