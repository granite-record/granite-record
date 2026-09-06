#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.8
"""
Reconcile stated boundaries against estimated ones, and adopt the stated ones
where they hold up.

    python3 apply_markers.py                    # every transcript on disk, report only
    python3 apply_markers.py --video 5shDhTjyqHU --verbose
    python3 apply_markers.py --apply            # write the accepted ones into segments.json

Nothing is written to segments.json unless --apply is given. The default run
answers the question first -- do chairs state boundaries, and do the stated ones
agree with the estimates -- and changes nothing.

WHAT THIS DOES

floor_markers.py finds the sentences where a chair opens and closes a
proceeding. transcribe_and_align.py estimates the same boundaries from where
bill numbers cluster. This reads both for every video that has a transcript,
compares them, and where the stated boundary survives the checks below, writes
it into segments.json with the fields that say it was stated rather than
estimated.

The transcripts are already on disk from the caption runs, so this needs no
network and nothing pasted by hand.

WHY IT IS NOT JUST "PREFER THE MARKER"

A marker is a quotation, but it is a quotation of a caption, and captions
mishear. Chairs vary their phrasing, skip the announcement, and occasionally
announce the wrong bill. So a marker is treated as evidence, not as an answer,
and it is published only when something already known agrees with it:

  1. The bill it names is on the docket for that video. The manifest says which
     bills the committee took up, and best_match() resolves HP for HB and lost
     spaces against that list. A marker naming a bill that was not scheduled is
     a misheard number, not a discovery, and is dropped.

  2. Either the bill was spoken, or the estimate independently agrees. Where a
     close does not name its bill, floor_markers fills it from the docket's
     published order -- a reasonable guess, but a guess. It is accepted only
     when the mention clustering put that bill in an overlapping span. Two
     methods agreeing is a fact; one method guessing is not.

  3. A disagreement wider than the estimate's own tolerance is reported, and
     accepted only when the bill was spoken and its close stated. Clustering is
     bimodal -- usually within 90 seconds, occasionally out by an hour -- so a
     wide disagreement means one of the two is badly wrong, and a stated close
     naming its own bill is the better of the two. It is still listed, because
     a run with many of these is a finding about the parser, not about chairs.

WHAT GETS CLAIMED, PER END

The two ends of a proceeding are not equally well known, and the site should not
average them into one number.

  House committee   chair states both ends           -> start stated, end stated
  Senate committee  only the close is announced      -> end stated, start bounded
                                                        by the previous close

A bounded start is not a stated one. Where only the end is stated the start
keeps the estimate, and the tolerance is narrowed only as far as the bound
allows -- if the whole window between the last close and this one is eight
minutes, a plus or minus thirty minute tolerance was never true, but a stated
one is not true either.

A stated boundary is given a 30 second tolerance rather than none. The timestamp
comes from a caption cue, cues are merged into chunks of up to about 220
characters before matching, and the words can start anywhere inside one. Seconds
of slack, not zero.

FLOOR SESSIONS ARE NOT DONE HERE

Floor recordings are not in the manifest and have no segments.json, and their
ends already come exactly from roll calls in build_floor_index.py. What the
clerk's reading adds there is the START, which is a different merge into a
different file. Committee first, since that is where the tolerance language on
the site actually lives.

REVERSING IT

The first --apply run copies segments.json to segments.pre_markers.json. Every
patched segment also keeps the estimate it replaced under "marker", so a rerun
recomputes from the original numbers rather than from its own output, and
`--apply` is safe to run repeatedly.
"""

import argparse
import csv
import json
import shutil
import statistics
from pathlib import Path

import floor_markers

# A stated boundary is a caption cue's start time, and cues are merged into
# chunks before matching, so the words can begin a little after the cue does.
STATED_TOL = 30

# align() trims a segment back to its first clustered mention and then pads
# this many seconds, because a chair names the bill a little after opening it.
# So a stated start and a good estimate differ by +90s, and measuring their
# agreement against zero measures the padding rather than the error.
PAD = 90.0


def hms(s):
    s = int(s or 0)
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def caps_from_transcript(path):
    """floor_markers wants (seconds, text); transcript.json holds cues."""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(float(r["start"]), (r.get("text") or "").strip())
            for r in rows if (r.get("text") or "").strip()]


def sched_key(r):
    t = r.get("sched_time") or "99:99"
    return t if len(t) == 5 else "0" + t


def expected_bills(rows):
    """The bills the docket says this video covers, in scheduled order.

    This is the candidate list best_match() corrects garbled numbers against,
    and it is what the manifest already knows -- the same list the --expect
    flag takes by hand.
    """
    out = []
    for r in sorted(rows, key=sched_key):
        b = (r.get("bill") or "").strip().upper().replace(" ", "")
        if b and b not in out:
            out.append(b)
    return tuple(out)


def is_exec(text):
    return "exec" in (text or "").lower()


def quote_at(caps, t, width=140):
    """The caption text at a boundary, verbatim.

    floor_markers describes some boundaries rather than quoting them -- the
    Senate path records "closed by the chair" -- and a description is not
    evidence. The caption line at that second is, so it is carried alongside
    and is what the site can show when it says a boundary was stated.
    """
    best = ""
    for ts, txt in caps:
        if ts <= t:
            best = txt
        else:
            break
    return best[:width]


def restore(seg):
    """Undo a previous --apply so this run starts from the estimate again.

    Clip first, then marker. The clip was recorded against the PATCHED values,
    so undoing them the other way round would restore the estimate and then
    overwrite it with the patched numbers again.
    """
    c = seg.pop("clip", None)
    if c:
        seg["start"], seg["end"] = c["start"], c["end"]
        seg["tolerance"] = c["tolerance"]
    m = seg.get("marker")
    if not m or "cluster_start" not in m:
        return seg
    seg["start"] = m["cluster_start"]
    seg["end"] = m["cluster_end"]
    seg["tolerance"] = m["cluster_tolerance"]
    seg["located"] = m["cluster_located"]
    seg["short"] = m.get("cluster_short", False)
    seg["why_not"] = m.get("cluster_why_not", "")
    for k in ("marker", "start_stated", "end_stated", "bill_stated", "said"):
        seg.pop(k, None)
    return seg


def overlaps(a0, a1, b0, b1):
    return a0 <= b1 and b0 <= a1


def span_overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def assign(mks, dp_segs):
    """Match every marker in a video to a segment, best pair first.

    Two things went wrong when this matched one marker at a time, and both
    showed up in the first real run over 349 videos.

    A bill announced TWICE in one recording got the earlier announcement,
    because the first marker to arrive claimed the segment. On 0rS9_QHUHbo,
    HR 41 is announced at 0:15:59 and again at 0:34:23, and the estimate says
    0:32:53 -- so the wrong one won and the right one was reported as if it
    were a misheard number.

    And matching on the bill alone attached an executive session's marker to
    that morning's PUBLIC HEARING. A kind check existed but only ran when a
    bill had more than one segment, so a bill docketed once took whichever
    announcement the parser found. That is where the three- and five-hour
    disagreements came from: not a bad estimate and not a bad marker, but a
    marker describing a different proceeding from the segment it patched.

    So: score every compatible pair, sort, and take them best-first. A kind
    mismatch is allowed only when the two spans actually overlap -- which is
    the docket recording a hearing and an executive session for one bill at
    the same minute, one event in the room.
    """
    dp = [(i, s) for i, s in enumerate(dp_segs) if "located" in s]
    scored = []
    for mi, mk in enumerate(mks):
        if not mk.get("bill"):
            continue
        for i, s in dp:
            if (s.get("bill") or "").upper() != mk["bill"]:
                continue
            same_kind = is_exec(s.get("kind")) == is_exec(mk.get("kind"))
            tol = s.get("tolerance") or 900
            ov = span_overlap(mk["start"], mk["end"],
                              (s.get("start") or 0) - tol,
                              (s.get("end") or 0) + tol)
            if not same_kind and ov <= 0:
                continue
            scored.append((0 if same_kind else 1, -ov,
                           abs(mk["start"] - (s.get("start") or 0)), mi, i))
    scored.sort()
    pairs, used_mk, used_dp = {}, set(), set()
    for _, _, _, mi, i in scored:
        if mi in used_mk or i in used_dp:
            continue
        used_mk.add(mi)
        used_dp.add(i)
        pairs[mi] = i
    return pairs


def reconcile(video, work, rows, verbose=False):
    """Compare stated boundaries with estimated ones for one video."""
    d = work / video
    tpath, spath = d / "transcript.json", d / "segments.json"
    if not tpath.exists() or not spath.exists():
        return None

    caps = caps_from_transcript(tpath)
    if len(caps) < 2:
        return {"video": video, "markers": [], "records": [], "no_caps": True}

    expect = expected_bills(rows)
    try:
        mks, events = floor_markers.committee_segments(caps, expect)
    except Exception as e:                      # one bad transcript is not a run
        return {"video": video, "markers": [], "records": [], "error": str(e)}

    dp_segs = [restore(s) for s in json.loads(spath.read_text(encoding="utf-8"))]

    pairs = assign(mks, dp_segs)
    bills_here = {(s.get("bill") or "").upper() for s in dp_segs if "located" in s}
    records = []
    for mi, mk in enumerate(mks):
        if not mk.get("bill"):
            continue
        i = pairs.get(mi)
        dp = dp_segs[i] if i is not None else None
        rec = {
            "bill": mk["bill"], "kind": mk.get("kind", ""),
            "stated_start": bool(mk.get("stated_start")),
            "stated_end": bool(mk.get("stated_end")),
            "bill_stated": not mk.get("bill_from_docket", False),
            "marker_start": mk["start"], "marker_end": mk["end"],
            "said": mk.get("said", ""), "dp_index": i,
            "quote_start": quote_at(caps, mk["start"]) if mk.get("stated_start") else "",
            "quote_end": quote_at(caps, mk["end"]) if mk.get("stated_end") else "",
        }
        if dp is None:
            # Two different things end up here and they are not the same
            # finding, so they are not reported as the same thing.
            if mk["bill"] in bills_here:
                rec.update(verdict="dropped",
                           why="a second announcement of a bill whose segment "
                               "is already matched, or a proceeding the docket "
                               "does not have for this video")
            else:
                # best_match has already tried this against the scheduled
                # list. What is left is a misheard number.
                rec.update(verdict="dropped",
                           why="not on the docket for this video")
            records.append(rec)
            continue
        rec.update(dp_start=dp.get("start"), dp_end=dp.get("end"),
                   dp_tol=dp.get("tolerance"), dp_located=bool(dp.get("located")),
                   dp_kind=dp.get("kind", ""))

        tol = dp.get("tolerance") or 900
        rec["delta"] = (mk["start"] - dp["start"]) if dp.get("located") else None

        # Agreement is about the BOUNDARY THE SITE PUBLISHES, measured against
        # the tolerance the aligner claimed for itself.
        #
        # This used to ask whether the marker's span overlapped the estimate's
        # span widened by the tolerance. On a forty-minute segment carrying a
        # +/-30 minute tolerance that window is nearly two hours wide, so a
        # marker an hour from the start still "agreed" -- which is how 111
        # accepted boundaries ended up more than ten minutes from the estimate.
        #
        # The rule now: a marker is adopted when it does not CONTRADICT what
        # the aligner already admitted about itself. If the aligner said it
        # knew the start to +/-30 minutes and the marker lands 25 minutes away,
        # nothing is contradicted and the tolerance collapses from 30 minutes
        # to 30 seconds. If it lands 90 minutes away, one of the two is wrong
        # beyond anything either of them claims, and neither is publishable.
        #
        # PAD is the 90 seconds align() subtracts when it trims a span back to
        # its first clustered mention, so a perfect agreement reads as +90s,
        # not as zero.
        if not dp.get("located"):
            agrees = False
        elif rec["stated_start"]:
            agrees = abs(rec["delta"] - PAD) <= tol
        else:
            # Only the close was stated, so the close is what to compare.
            agrees = abs(mk["end"] - (dp.get("end") or 0)) <= tol
        rec["agrees"] = agrees

        # Whether the estimate had anything to say at all.
        #
        # NOT "no mentions inside the span". transcribe_and_align.py calibrated
        # that against 34 hand-marked proceedings and found the opposite: all
        # seven segments it had been rejecting for having no mentions were
        # accurate, median error 1m33s, because the monotonic pass places a
        # bill from the structure around it even when its number is never
        # spoken in its own span. Treating those as blind let every large
        # disagreement through this gate -- the worst was unchanged at 335
        # minutes between two runs, which is how it was caught.
        #
        # Genuine blindness is the aligner refusing to publish at all: the bill
        # was never mentioned anywhere in the recording. Nothing competes with
        # a marker there, and the site shows no time for it today.
        blind = not dp.get("located")
        rec["blind"] = blind

        if not rec["bill_stated"] and not agrees:
            rec.update(verdict="held", why="bill filled from docket order, "
                                           "and the estimate does not agree")
        elif agrees:
            rec.update(verdict="apply", why="")
        elif blind:
            rec.update(verdict="apply",
                       why="the estimate had no mentions to work from, so the "
                           "marker is the only evidence")
        else:
            # Was: applied when the bill was spoken and its close stated. The
            # first real run showed that tier is where the damage lives -- a
            # marker and an estimate hours apart, both internally plausible,
            # with no way to tell from here which one is describing the
            # proceeding. Refusing beats guessing.
            rec.update(verdict="held",
                       why="disagrees with an estimate that had evidence; "
                           "one of the two is describing a different sitting")
        records.append(rec)

    return {"video": video, "records": records, "n_markers": len(mks),
            "n_events": len(events), "dp_segs": dp_segs, "path": spath,
            # Where the captions stop, which is as close to the length of the
            # recording as this can get without asking YouTube again. caps are
            # (seconds, text) pairs, not cue dicts.
            "tape_end": caps[-1][0] if caps else 0,
            "n_dp": sum(1 for s in dp_segs if "located" in s)}


def clip_neighbours(segs, tape_end=None):
    """Trim inferred spans back to the stated boundaries beside them.

    This is where the overlaps came from. Patching some proceedings in a
    recording and leaving the rest on mention density mixes two kinds of
    boundary, and a clustered span can run straight back through a neighbour's
    stated close -- so two bills claim the same minutes and the site would show
    both. The first real run put 1,098 minutes of tape in that state.

    A clustered span that crosses a stated close is not a tie. The chair said
    that hearing ended; the next one did not begin before it. So the inferred
    boundary moves and the stated one never does, which makes this a narrowing
    of an estimate using evidence rather than a tidy-up of a warning.

    Where BOTH boundaries are stated and they still overlap, nothing here can
    say which is right, so both are left alone and the conflict is reported.
    """
    clipped, conflicts = 0, []
    pub = [s for s in segs if s.get("located")]

    # Nothing may run past the end of the recording. A stated boundary beyond
    # it is not a boundary -- the chair cannot have said it on tape that does
    # not exist -- so a segment that STARTS after the tape ends gives its
    # marker back, and one that merely runs over is trimmed. Ten segments
    # ended up outside their recording on the first run; this is where they
    # came from.
    if tape_end and tape_end > 60:
        # Every segment, not only the located ones. The segments that ran past
        # the end of the recording included one with no bill attached at all,
        # which a located-only sweep never looked at.
        for s in segs:
            if s.get("start") is None or s.get("end") is None:
                continue
            if s["start"] >= tape_end - 1:
                m = s.pop("marker", None)
                if m:
                    s["start"] = m.get("cluster_start", s["start"])
                    s["end"] = m.get("cluster_end", s["end"])
                    s["tolerance"] = m.get("cluster_tolerance", s.get("tolerance"))
                    s.pop("start_stated", None)
                    s.pop("end_stated", None)
                    s["reverted"] = "started after the recording ended"
                    clipped += 1
            elif s["end"] > tape_end:
                s.setdefault("clip", {"start": s["start"], "end": s["end"],
                                      "tolerance": s.get("tolerance")})
                s["end"] = round(tape_end, 1)
                clipped += 1

    # SORTED BY TIME, not by position in the file. The file is in docket order,
    # and adopting a stated boundary moves a segment within the recording, so
    # the segment before this one in the list is very often not the one before
    # it on the tape. Pairing on list order left most overlaps unexamined and
    # occasionally "clipped" a segment against one somewhere else entirely,
    # which is why the first attempt at this moved the count so little.
    #
    # Run to a fixed point, because moving one boundary can uncover an overlap
    # with the segment after it.
    for _ in range(4):
        pub.sort(key=lambda s: (s["start"], s["end"]))
        before = clipped
        clipped, conflicts = _clip_pass(pub, clipped, conflicts)
        if clipped == before:
            break

    # Last resort: give the marker back.
    #
    # Clipping can only move the INFERRED side of a seam, and two attempts at
    # it moved the overlap count by one, so the overlaps that survive are not
    # ones this can reason about. What is certain is that the aligner's own
    # estimates did not overlap -- that was guaranteed before any of this ran.
    # So where a patched segment still shares minutes with a neighbour, the
    # marker is the thing that introduced the contradiction, and it goes back.
    #
    # This costs precision on exactly the segments that had contradicted
    # something, and nowhere else. A boundary that cannot be reconciled with
    # its neighbour is not one to publish at thirty seconds.
    reverted = 0
    for _ in range(3):
        pub.sort(key=lambda s: (s["start"], s["end"]))
        hit = None
        for i in range(1, len(pub)):
            a, b = pub[i - 1], pub[i]
            if min(a["end"], b["end"]) - max(a["start"], b["start"]) > 1:
                hit = b if b.get("marker") else (a if a.get("marker") else None)
                if hit:
                    break
        if not hit:
            break
        m = hit.pop("marker")
        hit["start"] = m.get("cluster_start", hit["start"])
        hit["end"] = m.get("cluster_end", hit["end"])
        hit["tolerance"] = m.get("cluster_tolerance", hit.get("tolerance"))
        hit.pop("start_stated", None)
        hit.pop("end_stated", None)
        hit.pop("clip", None)
        hit["reverted"] = "overlapped a neighbour after clipping"
        reverted += 1
    return clipped, conflicts, reverted


def _clip_pass(pub, clipped, conflicts):
    """One sorted sweep. Only the inferred side of a seam ever moves."""
    for i in range(1, len(pub)):
        a, b = pub[i - 1], pub[i]
        if min(a["end"], b["end"]) - max(a["start"], b["start"]) <= 1:
            continue
        if a.get("end_stated") and not b.get("start_stated"):
            if a["end"] < b["end"]:
                b.setdefault("clip", {"start": b["start"], "end": b["end"],
                                      "tolerance": b.get("tolerance")})
                b["start"] = round(a["end"], 1)
                half = max(60, int((b["end"] - b["start"]) / 2))
                b["tolerance"] = min(b.get("tolerance") or half, half)
                clipped += 1
        elif b.get("start_stated") and not a.get("end_stated"):
            if b["start"] > a["start"]:
                a.setdefault("clip", {"start": a["start"], "end": a["end"],
                                      "tolerance": a.get("tolerance")})
                a["end"] = round(b["start"], 1)
                clipped += 1
        elif a.get("end_stated") and b.get("start_stated"):
            conflicts.append((a.get("bill"), b.get("bill")))
        elif a.get("marker") and not a.get("end_stated"):
            # Neither boundary at this seam is stated, so nothing above can
            # anchor to it -- and this is where the overlaps that survived the
            # first pass live. A marker with a stated START keeps the aligner's
            # end, so a patched segment can now run past the neighbour it never
            # reached before. The overlap is one we introduced by moving the
            # start, and the aligner guaranteed no overlap before that, so the
            # end goes back to where it has to be.
            if b["start"] > a["start"]:
                a.setdefault("clip", {"start": a["start"], "end": a["end"],
                                      "tolerance": a.get("tolerance")})
                a["end"] = round(b["start"], 1)
                clipped += 1
    return clipped, conflicts


def patch(res):
    """Write accepted markers into the segments, keeping what they replaced."""
    n = 0
    for rec in res["records"]:
        if rec["verdict"] != "apply":
            continue
        seg = res["dp_segs"][rec["dp_index"]]
        keep = {"cluster_start": seg.get("start"), "cluster_end": seg.get("end"),
                "cluster_tolerance": seg.get("tolerance"),
                "cluster_located": bool(seg.get("located")),
                "cluster_short": bool(seg.get("short")),
                "cluster_why_not": seg.get("why_not", ""),
                "delta": rec["delta"], "agreed": rec["agrees"],
                "said": rec["said"]}
        quotes = {k: rec[k] for k in ("quote_start", "quote_end") if rec[k]}

        start, end = rec["marker_start"], rec["marker_end"]
        if rec["stated_start"] and not rec["stated_end"]:
            # floor_markers ends a segment at the next announcement, or at the
            # end of the recording when there is no next one. That is weaker
            # than the aligner's end, which is trimmed to the mention cluster,
            # and it is what produced a five-hour "hearing".
            ce = keep["cluster_end"]
            if ce and ce > start:
                end = ce
        if rec["stated_start"]:
            tol = STATED_TOL
        else:
            # Only the close is stated. The start is somewhere between the
            # previous close and this one; keep the estimate if it falls in
            # that window, and narrow the tolerance no further than the window
            # itself allows.
            half = max(60, int((end - start) / 2))
            if rec["dp_located"] and start <= rec["dp_start"] <= end:
                start = rec["dp_start"]
                tol = min(rec["dp_tol"] or half, half)
            else:
                tol = half
                keep["start_bounded_by"] = "previous close"

        seg.update(start=round(start, 1), end=round(end, 1), tolerance=int(tol),
                   located=True, why_not="",
                   short=bool(rec["stated_start"] is False and (end - start) < 120),
                   start_stated=rec["stated_start"], end_stated=rec["stated_end"],
                   bill_stated=rec["bill_stated"], said=rec["said"], marker=keep,
                   **quotes)
        n += 1

    clipped, conflicts, reverted = clip_neighbours(res["dp_segs"],
                                                   res.get("tape_end"))
    if n or clipped:
        bak = res["path"].with_name("segments.pre_markers.json")
        if not bak.exists():
            shutil.copy2(res["path"], bak)
        res["path"].write_text(json.dumps(res["dp_segs"], indent=2),
                               encoding="utf-8")
    return n, clipped, conflicts, reverted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default="work")
    ap.add_argument("--manifest", default="verification_manifest.csv")
    ap.add_argument("--video", help="one video id")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true",
                    help="write accepted markers into segments.json")
    ap.add_argument("--verbose", action="store_true",
                    help="print the sentence each boundary came from")
    a = ap.parse_args()

    work = Path(a.workdir)
    if not work.exists():
        raise SystemExit(f"No {work}/ here. Run this beside the scripts.")

    by_video = {}
    for r in csv.DictReader(open(a.manifest, encoding="utf-8-sig")):
        v = (r.get("video_id") or "").strip()
        if v:
            by_video.setdefault(v, []).append(r)

    vids = [a.video] if a.video else sorted(
        d.name for d in work.iterdir()
        if d.is_dir() and (d / "transcript.json").exists()
        and (d / "segments.json").exists())
    missing = [v for v in vids if v not in by_video]
    vids = [v for v in vids if v in by_video]
    if a.limit:
        vids = vids[:a.limit]
    print(f"{len(vids):,} videos with a transcript, a segments file and manifest rows")
    if not vids:
        if missing:
            print(f"\n{', '.join(missing[:4])} has no rows in {a.manifest}, so "
                  "there is no\nlist of scheduled bills to check a spoken number "
                  "against. Floor session\nrecordings are the usual reason: they "
                  "are not in the manifest at all.")
        else:
            print("\nNothing to compare. This reads what align_all.py has already "
                  "written,\nso run that first.")
        return

    all_recs, silent, applied_total = [], [], 0
    clipped_total, conflicts_total, reverted_total = 0, [], 0
    print(f"\n{'video':<13}{'bill':<9}{'ends':<7}{'stated start':<14}"
          f"{'estimate':<11}{'delta':>8}  verdict")
    print("-" * 78)
    for v in vids:
        res = reconcile(v, work, by_video[v], a.verbose)
        if res is None:
            continue
        if res.get("error"):
            print(f"{v:<13}  could not be read: {res['error'][:44]}")
            continue
        if not res["records"]:
            silent.append(v)
            continue
        for rec in res["records"]:
            ends = ("both" if rec["stated_start"] and rec["stated_end"]
                    else "end" if rec["stated_end"] else "start")
            dl = rec.get("delta")
            print(f"{v:<13}{rec['bill']:<9}{ends:<7}"
                  f"{hms(rec['marker_start']):<14}"
                  f"{(hms(rec['dp_start']) if rec.get('dp_located') else '-'):<11}"
                  f"{(f'{int(dl)//60:+d}m{abs(int(dl))%60:02d}s' if dl is not None else '-'):>8}"
                  f"  {rec['verdict']}"
                  + (f" - {rec['why']}" if rec.get("why") else ""))
            if a.verbose:
                for lbl, key in (("opens", "quote_start"), ("closes", "quote_end")):
                    if rec.get(key):
                        print(f"{'':<15}{lbl}: \u201c{rec[key][:66]}\u201d")
        all_recs += res["records"]
        if a.apply:
            got, cl, conf, rev = patch(res)
            applied_total += got
            clipped_total += cl
            conflicts_total += conf
            reverted_total += rev

    # ---- what the run found ------------------------------------------------
    ok = [r for r in all_recs if r["verdict"] == "apply"]
    held = [r for r in all_recs if r["verdict"] == "held"]
    dropped = [r for r in all_recs if r["verdict"] == "dropped"]
    deltas = [abs(r["delta"]) for r in ok if r.get("delta") is not None]

    print("\n" + "=" * 78)
    print(f"{len(vids):,} videos read, {len(silent):,} with no announcement "
          f"the parser recognised")
    print(f"{len(all_recs):,} stated boundaries found")
    print(f"  {len(ok):,} accepted "
          f"({sum(1 for r in ok if r['stated_start'] and r['stated_end']):,} with "
          f"both ends stated, {sum(1 for r in ok if not r['stated_start']):,} "
          f"with the close only)")
    print(f"  {len(held):,} held back, {len(dropped):,} dropped as misheard")
    signed = [r["delta"] for r in ok if r.get("delta") is not None]
    if deltas:
        med = statistics.median(signed)
        print(f"\nstated minus estimated: median {med:+.0f}s, "
              f"worst {int(max(deltas))//60}m{int(max(deltas))%60:02d}s")
        # align() trims a span back to its first clustered mention and then
        # pads 90 seconds, because a chair names the bill a little after
        # opening it. So the expected difference between a stated boundary and
        # a good estimate is +90s, not zero, and measuring agreement against
        # zero understates it.
        pad = sum(1 for d in signed if 60 <= d <= 120)
        near = sum(1 for d in signed if abs(d - 90) <= 120)
        print(f"{pad:,} land within a few seconds of +90s exactly, which is the "
              "aligner's\nown padding -- those are not disagreements, they are "
              "the two methods\nfinding the same instant.")
        print(f"{near:,} of {len(signed):,} agree once that padding is allowed for.")
        # What is left after the gate: how far the ACCEPTED ones sit from the
        # pad. This is the residual risk, and it belongs in the summary rather
        # than only in a table nobody reads to the end.
        bands = [("within 2 min of the pad", lambda d: abs(d - 90) <= 120),
                 ("2 to 10 min out", lambda d: 120 < abs(d - 90) <= 600),
                 ("10 to 60 min out", lambda d: 600 < abs(d - 90) <= 3600),
                 ("over an hour out", lambda d: abs(d - 90) > 3600)]
        print("\naccepted, by distance from the pad:")
        for label, f in bands:
            c = sum(1 for d in signed if f(d))
            if c:
                print(f"  {c:>5,}  {label}")
        wide = sum(1 for r in ok if r.get("agrees") and r.get("delta") is not None
                   and abs(r["delta"] - PAD) > 600)
        if wide:
            print(f"\n{wide:,} of those sit outside ten minutes but INSIDE the "
                  "tolerance the\naligner claimed for itself, so the marker "
                  "contradicts nothing it said.")
        far = sum(1 for d in signed if abs(d - 90) > 600)
        if far:
            print(f"\n{far:,} accepted boundaries are more than ten minutes from "
                  "the estimate.\nEvery one is a place where two methods "
                  "disagree and the site would\nstate one of them. Spot-check "
                  "a few before publishing.")
    if a.apply:
        print(f"\n{applied_total:,} segments rewritten. The estimate each one "
              "replaced is kept\nunder \"marker\", and the original file is "
              "beside it as segments.pre_markers.json.")
        if clipped_total:
            print(f"\n{clipped_total:,} neighbouring estimates were trimmed back to a "
                  "stated boundary,\nbecause a span that crosses a close the chair "
                  "announced is wrong about\nwhere it began. Each keeps what it had "
                  "under \"clip\".")
        if reverted_total:
            print(f"\n{reverted_total:,} markers were given back, because after "
                  "clipping the segment\nstill shared minutes with its "
                  "neighbour. The aligner's estimates did not\noverlap, so a "
                  "marker that leaves one is the thing that introduced it. "
                  "Those\nsegments are back on mention density and say so.")
        if conflicts_total:
            print(f"\n{len(conflicts_total):,} pairs overlap with BOTH boundaries "
                  "stated. Nothing here can say\nwhich is right, so both were left "
                  "as they are:")
            for x, y in conflicts_total[:6]:
                print(f"  {x} and {y}")
        print("Run build_site_v2.py to pick these up, then publish.")
    else:
        print("\nNothing was written. Add --apply once the numbers above look "
              "right.")
    print("=" * 78)


if __name__ == "__main__":
    main()
